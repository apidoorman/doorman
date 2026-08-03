use std::{
    sync::Arc,
    time::{Duration, Instant},
};

use futures_util::TryStreamExt;
use mongodb::{
    Client, Database,
    bson::{Document, doc},
};
use redis::{AsyncCommands, aio::ConnectionManager};
use serde_json::Value;
use thiserror::Error;

use crate::{config::SharedStorageConfig, storage::models::PolicyDocuments};

#[derive(Clone)]
pub struct SharedStorage {
    mongo: Database,
    redis: ConnectionManager,
    policy_cache: Arc<tokio::sync::RwLock<Option<CachedPolicyDocuments>>>,
    policy_cache_ttl: Duration,
}

#[derive(Clone)]
struct CachedPolicyDocuments {
    loaded_at: Instant,
    documents: PolicyDocuments,
}

#[derive(Debug, Error)]
pub enum StorageError {
    #[error("MongoDB operation failed: {0}")]
    Mongo(#[from] mongodb::error::Error),
    #[error("Redis operation failed: {0}")]
    Redis(#[from] redis::RedisError),
    #[error("MongoDB document conversion failed: {0}")]
    Bson(#[from] mongodb::bson::ser::Error),
    #[error("stored document cannot be represented as JSON: {0}")]
    Json(#[from] serde_json::Error),
    #[error("invalid stored document: {0}")]
    InvalidDocument(String),
}

impl SharedStorage {
    pub async fn connect(config: &SharedStorageConfig) -> Result<Self, StorageError> {
        let client = Client::with_uri_str(config.mongo_uri()).await?;
        let mongo = client.database(&config.mongo_database);
        mongo.run_command(doc! { "ping": 1 }).await?;

        let redis_client = redis::Client::open(config.redis_url())?;
        let mut redis = ConnectionManager::new(redis_client).await?;
        let _: String = redis::cmd("PING").query_async(&mut redis).await?;
        Ok(Self {
            mongo,
            redis,
            policy_cache: Arc::new(tokio::sync::RwLock::new(None)),
            policy_cache_ttl: Duration::from_secs(config.policy_cache_ttl_seconds),
        })
    }

    pub async fn load_policy_documents(&self) -> Result<PolicyDocuments, StorageError> {
        if let Some(cached) = self.policy_cache.read().await.as_ref() {
            if cached.loaded_at.elapsed() < self.policy_cache_ttl {
                return Ok(cached.documents.clone());
            }
        }

        let (
            apis,
            endpoints,
            users,
            roles,
            subscriptions,
            routings,
            credit_defs,
            user_credits,
            settings,
            revocations,
        ) = tokio::try_join!(
            self.load_collection("apis"),
            self.load_collection("endpoints"),
            self.load_collection("users"),
            self.load_collection("roles"),
            self.load_collection("subscriptions"),
            self.load_collection("routings"),
            self.load_collection("credit_defs"),
            self.load_collection("user_credits"),
            self.load_collection("settings"),
            self.load_collection("revocations"),
        )?;
        let documents = PolicyDocuments {
            apis,
            endpoints,
            users,
            roles,
            subscriptions,
            routings,
            credit_defs,
            user_credits,
            settings,
            revocations,
        };
        *self.policy_cache.write().await = Some(CachedPolicyDocuments {
            loaded_at: Instant::now(),
            documents: documents.clone(),
        });
        Ok(documents)
    }

    pub async fn invalidate_policy_cache(&self) {
        *self.policy_cache.write().await = None;
    }

    async fn load_collection(&self, name: &str) -> Result<Vec<Value>, StorageError> {
        let mut cursor = self
            .mongo
            .collection::<Document>(name)
            .find(doc! {})
            .await?;
        let mut values = Vec::new();
        while let Some(mut document) = cursor.try_next().await? {
            document.remove("_id");
            values.push(serde_json::to_value(document)?);
        }
        Ok(values)
    }

    pub async fn increment_window(&self, key: &str, ttl_seconds: u64) -> Result<u64, StorageError> {
        let mut redis = self.redis.clone();
        Ok(redis::Script::new(
            r#"
            local count = redis.call('INCR', KEYS[1])
            if count == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end
            return count
            "#,
        )
        .key(key)
        .arg(ttl_seconds.max(1))
        .invoke_async(&mut redis)
        .await?)
    }

    pub async fn add_bandwidth(
        &self,
        key: &str,
        bytes: u64,
        ttl_seconds: u64,
    ) -> Result<u64, StorageError> {
        let mut redis = self.redis.clone();
        Ok(redis::Script::new(
            r#"
            local total = redis.call('INCRBY', KEYS[1], ARGV[1])
            if redis.call('TTL', KEYS[1]) < 0 then
                redis.call('EXPIRE', KEYS[1], ARGV[2])
            end
            return total
            "#,
        )
        .key(key)
        .arg(bytes)
        .arg(ttl_seconds.max(1))
        .invoke_async(&mut redis)
        .await?)
    }

    pub async fn next_routing_index(
        &self,
        key: &str,
        server_count: usize,
    ) -> Result<usize, StorageError> {
        let mut redis = self.redis.clone();
        let index: u64 = redis::Script::new(
            r#"
            local current = redis.call('GET', KEYS[1])
            if not current then current = 0 else current = tonumber(current) end
            local next = (current + 1) % tonumber(ARGV[1])
            redis.call('SET', KEYS[1], next, 'EX', ARGV[2])
            return current
            "#,
        )
        .key(key)
        .arg(server_count.max(1))
        .arg(86400_u64)
        .invoke_async(&mut redis)
        .await?;
        Ok(index as usize)
    }

    pub async fn current_routing_index(&self, key: &str) -> Result<usize, StorageError> {
        Ok(self.current_counter(key).await? as usize)
    }

    pub async fn next_client_routing_index(
        &self,
        key: &str,
        initial: &Value,
        server_count: usize,
    ) -> Result<usize, StorageError> {
        let mut redis = self.redis.clone();
        let initial = serde_json::to_string(initial)?;
        let index: u64 = redis::Script::new(
            r#"
            local raw = redis.call('GET', KEYS[1])
            if not raw then raw = ARGV[1] end
            local ok, routing = pcall(cjson.decode, raw)
            if not ok or type(routing) ~= 'table' then
                return redis.error_reply('invalid client routing cache value')
            end
            local current = tonumber(routing.server_index) or 0
            routing.server_index = (current + 1) % tonumber(ARGV[2])
            redis.call('SET', KEYS[1], cjson.encode(routing), 'EX', ARGV[3])
            return current
            "#,
        )
        .key(key)
        .arg(initial)
        .arg(server_count.max(1))
        .arg(86400_u64)
        .invoke_async(&mut redis)
        .await?;
        Ok(index as usize)
    }

    pub async fn current_client_routing_index(
        &self,
        key: &str,
        initial: &Value,
    ) -> Result<usize, StorageError> {
        let mut redis = self.redis.clone();
        let raw: Option<String> = redis.get(key).await?;
        let value = match raw {
            Some(raw) => serde_json::from_str::<Value>(&raw)?,
            None => initial.clone(),
        };
        Ok(value
            .get("server_index")
            .and_then(Value::as_u64)
            .unwrap_or(0) as usize)
    }

    pub async fn current_counter(&self, key: &str) -> Result<u64, StorageError> {
        let mut redis = self.redis.clone();
        Ok(redis.get::<_, Option<u64>>(key).await?.unwrap_or(0))
    }

    pub async fn deduct_credit(&self, username: &str, group: &str) -> Result<bool, StorageError> {
        let path = format!("users_credits.{group}.available_credits");
        let mut filter = doc! { "username": username };
        filter.insert(path.clone(), doc! { "$gt": 0 });
        let mut increment = Document::new();
        increment.insert(path, -1_i32);
        let result = self
            .mongo
            .collection::<Document>("user_credits")
            .update_one(filter, doc! { "$inc": increment })
            .await?;
        Ok(result.modified_count == 1)
    }

    pub async fn crud_find_one(
        &self,
        collection: &str,
        resource_id: &str,
    ) -> Result<Option<Value>, StorageError> {
        let document = self
            .mongo
            .collection::<Document>(collection)
            .find_one(doc! { "_id": resource_id })
            .await?;
        document
            .map(serde_json::to_value)
            .transpose()
            .map_err(Into::into)
    }

    pub async fn crud_list(&self, collection: &str) -> Result<Vec<Value>, StorageError> {
        let mut cursor = self
            .mongo
            .collection::<Document>(collection)
            .find(doc! {})
            .await?;
        let mut values = Vec::new();
        while let Some(document) = cursor.try_next().await? {
            values.push(serde_json::to_value(document)?);
        }
        Ok(values)
    }

    pub async fn crud_insert(&self, collection: &str, value: &Value) -> Result<(), StorageError> {
        let document = mongodb::bson::to_document(value)?;
        self.mongo
            .collection::<Document>(collection)
            .insert_one(document)
            .await?;
        Ok(())
    }

    pub async fn crud_update(
        &self,
        collection: &str,
        resource_id: &str,
        value: &Value,
    ) -> Result<Option<Value>, StorageError> {
        let mut update = mongodb::bson::to_document(value)?;
        update.remove("_id");
        let result = self
            .mongo
            .collection::<Document>(collection)
            .update_one(doc! { "_id": resource_id }, doc! { "$set": update })
            .await?;
        if result.matched_count == 0 {
            return Ok(None);
        }
        self.crud_find_one(collection, resource_id).await
    }

    pub async fn crud_delete(
        &self,
        collection: &str,
        resource_id: &str,
    ) -> Result<bool, StorageError> {
        let result = self
            .mongo
            .collection::<Document>(collection)
            .delete_one(doc! { "_id": resource_id })
            .await?;
        Ok(result.deleted_count > 0)
    }

    pub async fn clear_gateway_counters(&self) -> Result<(), StorageError> {
        let mut redis = self.redis.clone();
        for pattern in ["rate_limit:*", "throttle_limit:*", "bandwidth_usage:*"] {
            let keys: Vec<String> = redis.keys(pattern).await?;
            if !keys.is_empty() {
                let _: usize = redis.del(keys).await?;
            }
        }
        Ok(())
    }
}
