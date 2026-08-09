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

use crate::{
    config::SharedStorageConfig,
    storage::{memory::MemoryStorage, models::PolicyDocuments},
};

#[derive(Clone)]
pub struct SharedStorage {
    mongo: Option<Database>,
    redis: Option<ConnectionManager>,
    memory: Option<MemoryStorage>,
    policy_cache: Arc<tokio::sync::RwLock<Option<CachedPolicyDocuments>>>,
    policy_cache_ttl: Duration,
}

#[derive(Clone)]
struct CachedPolicyDocuments {
    loaded_at: Instant,
    revision: u64,
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

pub struct GatewayMetric<'a> {
    pub minute_start: u64,
    pub status: u16,
    pub duration_micros: u64,
    pub bytes_in: u64,
    pub bytes_out: u64,
    pub api_key: Option<&'a str>,
    pub username: Option<&'a str>,
    pub endpoint: Option<&'a str>,
    pub is_test: bool,
}

impl SharedStorage {
    pub async fn connect(config: &SharedStorageConfig) -> Result<Self, StorageError> {
        if config.storage_mode.eq_ignore_ascii_case("MEM") {
            return Ok(Self {
                mongo: None,
                redis: None,
                memory: Some(MemoryStorage::new()),
                policy_cache: Arc::new(tokio::sync::RwLock::new(None)),
                policy_cache_ttl: Duration::from_secs(config.policy_cache_ttl_seconds),
            });
        }
        let client = Client::with_uri_str(config.mongo_uri()).await?;
        let mongo = client.database(&config.mongo_database);
        mongo.run_command(doc! { "ping": 1 }).await?;

        let redis_client = redis::Client::open(config.redis_url())?;
        let mut redis = ConnectionManager::new(redis_client).await?;
        let _: String = redis::cmd("PING").query_async(&mut redis).await?;
        Ok(Self {
            mongo: Some(mongo),
            redis: Some(redis),
            memory: None,
            policy_cache: Arc::new(tokio::sync::RwLock::new(None)),
            policy_cache_ttl: Duration::from_secs(config.policy_cache_ttl_seconds),
        })
    }

    pub async fn initialize_core(&self) -> Result<(), StorageError> {
        let admin_role = serde_json::json!({
            "role_name": "admin", "role_description": "Administrator role",
            "manage_users": true, "manage_apis": true, "manage_endpoints": true,
            "manage_groups": true, "manage_roles": true, "manage_routings": true,
            "manage_gateway": true, "manage_subscriptions": true, "manage_credits": true,
            "manage_auth": true, "manage_security": true, "manage_tiers": true,
            "manage_rate_limits": true, "view_analytics": true, "view_logs": true,
            "export_logs": true, "ui_access": true
        });
        if self
            .find_one("roles", &serde_json::json!({"role_name": "admin"}))
            .await?
            .is_none()
        {
            self.insert_one("roles", admin_role).await?;
        }
        for (name, description) in [
            ("admin", "Administrator group with full access"),
            ("ALL", "Default group with access to all APIs"),
        ] {
            if self
                .find_one("groups", &serde_json::json!({"group_name": name}))
                .await?
                .is_none()
            {
                self.insert_one(
                    "groups",
                    serde_json::json!({
                        "group_name": name, "group_description": description, "api_access": []
                    }),
                )
                .await?;
            }
        }
        if self
            .find_one("users", &serde_json::json!({"username": "admin"}))
            .await?
            .is_none()
        {
            let password = std::env::var("DOORMAN_ADMIN_PASSWORD").map_err(|_| {
                StorageError::InvalidDocument(
                    "DOORMAN_ADMIN_PASSWORD is required for admin initialization".to_owned(),
                )
            })?;
            let password = bcrypt::hash(password, bcrypt::DEFAULT_COST).map_err(|error| {
                StorageError::InvalidDocument(format!("failed to hash admin password: {error}"))
            })?;
            self.insert_one("users", serde_json::json!({
                "username": "admin",
                "email": std::env::var("DOORMAN_ADMIN_EMAIL").unwrap_or_else(|_| "admin@doorman.dev".to_owned()),
                "password": password,
                "role": "admin", "groups": ["ALL", "admin"], "ui_access": true,
                "rate_limit_duration": 1, "rate_limit_duration_type": "second",
                "throttle_duration": 1, "throttle_duration_type": "second",
                "throttle_wait_duration": 0, "throttle_wait_duration_type": "second",
                "throttle_queue_limit": 1, "throttle_enabled": null,
                "custom_attributes": {"custom_key": "custom_value"}, "active": true
            })).await?;
        }
        Ok(())
    }

    pub async fn dump_memory_data(
        &self,
    ) -> Result<std::collections::HashMap<String, Vec<Value>>, StorageError> {
        let Some(memory) = &self.memory else {
            return Err(StorageError::InvalidDocument(
                "Memory dump is available only in memory mode".to_owned(),
            ));
        };
        Ok(memory.collections.read().await.clone())
    }

    pub async fn restore_memory_data(
        &self,
        collections: std::collections::HashMap<String, Vec<Value>>,
    ) -> Result<(), StorageError> {
        let Some(memory) = &self.memory else {
            return Err(StorageError::InvalidDocument(
                "Memory restore is available only in memory mode".to_owned(),
            ));
        };
        *memory.collections.write().await = collections;
        memory.clear_runtime().await;
        self.invalidate_policy_cache().await;
        Ok(())
    }

    pub fn is_memory(&self) -> bool {
        self.memory.is_some()
    }

    pub async fn set_ephemeral(
        &self,
        key: &str,
        value: Value,
        ttl_seconds: u64,
    ) -> Result<(), StorageError> {
        if let Some(memory) = &self.memory {
            memory.set_value(key, value, ttl_seconds).await;
            return Ok(());
        }
        let encoded = serde_json::to_string(&value)?;
        let mut redis = self.redis()?;
        let _: () = redis.set_ex(key, encoded, ttl_seconds.max(1)).await?;
        Ok(())
    }

    pub async fn get_ephemeral(&self, key: &str) -> Result<Option<Value>, StorageError> {
        if let Some(memory) = &self.memory {
            return Ok(memory.get_value(key).await);
        }
        let mut redis = self.redis()?;
        let encoded: Option<String> = redis.get(key).await?;
        encoded
            .map(|value| serde_json::from_str(&value))
            .transpose()
            .map_err(StorageError::from)
    }

    fn mongo(&self) -> Result<&Database, StorageError> {
        self.mongo.as_ref().ok_or_else(|| {
            StorageError::InvalidDocument("MongoDB unavailable in memory mode".to_owned())
        })
    }

    fn redis(&self) -> Result<ConnectionManager, StorageError> {
        self.redis.clone().ok_or_else(|| {
            StorageError::InvalidDocument("Redis unavailable in memory mode".to_owned())
        })
    }

    pub async fn load_policy_documents(&self) -> Result<PolicyDocuments, StorageError> {
        let revision = self.policy_revision().await?;
        if let Some(memory) = &self.memory {
            return Ok(memory.load_policy_documents().await);
        }
        if let Some(cached) = self.policy_cache.read().await.as_ref()
            && cached.revision == revision
            && cached.loaded_at.elapsed() < self.policy_cache_ttl
        {
            return Ok(cached.documents.clone());
        }

        let (
            apis,
            endpoints,
            endpoint_validations,
            users,
            roles,
            subscriptions,
            routings,
            credit_defs,
            user_credits,
            settings,
            revocations,
            tiers,
            tier_assignments,
        ) = tokio::try_join!(
            self.load_collection("apis"),
            self.load_collection("endpoints"),
            self.load_collection("endpoint_validations"),
            self.load_collection("users"),
            self.load_collection("roles"),
            self.load_collection("subscriptions"),
            self.load_collection("routings"),
            self.load_collection("credit_defs"),
            self.load_collection("user_credits"),
            self.load_collection("settings"),
            self.load_collection("revocations"),
            self.load_collection("tiers"),
            self.load_collection("user_tier_assignments"),
        )?;
        let documents = PolicyDocuments {
            apis,
            endpoints,
            endpoint_validations,
            users,
            roles,
            subscriptions,
            routings,
            credit_defs,
            user_credits,
            settings,
            revocations,
            tiers,
            tier_assignments,
        };
        *self.policy_cache.write().await = Some(CachedPolicyDocuments {
            loaded_at: Instant::now(),
            revision,
            documents: documents.clone(),
        });
        Ok(documents)
    }

    pub async fn invalidate_policy_cache(&self) {
        *self.policy_cache.write().await = None;
    }

    async fn policy_revision(&self) -> Result<u64, StorageError> {
        if let Some(memory) = &self.memory {
            return Ok(memory.revision());
        }
        let mut redis = self.redis()?;
        Ok(redis
            .get::<_, Option<u64>>("gateway:policy_revision")
            .await?
            .unwrap_or(0))
    }

    pub async fn bump_policy_revision(&self) -> Result<u64, StorageError> {
        if let Some(memory) = &self.memory {
            return Ok(memory.bump_revision());
        }
        let mut redis = self.redis()?;
        Ok(redis.incr("gateway:policy_revision", 1_u64).await?)
    }

    async fn load_collection(&self, name: &str) -> Result<Vec<Value>, StorageError> {
        let mut cursor = self
            .mongo()?
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
        if let Some(memory) = &self.memory {
            return Ok(memory.increment(key, 1, ttl_seconds).await);
        }
        let mut redis = self.redis()?;
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

    pub async fn check_tier_window(
        &self,
        key: &str,
        limit: u64,
        ttl_seconds: u64,
    ) -> Result<u64, StorageError> {
        if let Some(memory) = &self.memory {
            let current = memory
                .get_value(key)
                .await
                .and_then(|value| value.as_u64())
                .unwrap_or(0);
            if current >= limit {
                return Ok(current + 1);
            }
            return Ok(memory.increment(key, 1, ttl_seconds).await);
        }
        let mut redis = self.redis()?;
        Ok(redis::Script::new(
            r#"
            local current = tonumber(redis.call('GET', KEYS[1]) or '0')
            if current >= tonumber(ARGV[1]) then
                return current + 1
            end
            local count = redis.call('INCR', KEYS[1])
            if count == 1 then redis.call('EXPIRE', KEYS[1], ARGV[2]) end
            return count
            "#,
        )
        .key(key)
        .arg(limit)
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
        if let Some(memory) = &self.memory {
            return Ok(memory.increment(key, bytes, ttl_seconds).await);
        }
        let mut redis = self.redis()?;
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
        if let Some(memory) = &self.memory {
            let current = memory
                .get_value(key)
                .await
                .and_then(|value| value.as_u64())
                .unwrap_or(0);
            memory
                .set_value(
                    key,
                    serde_json::json!((current + 1) % server_count.max(1) as u64),
                    86400,
                )
                .await;
            return Ok(current as usize);
        }
        let mut redis = self.redis()?;
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
        if let Some(memory) = &self.memory {
            let mut value = memory
                .get_value(key)
                .await
                .unwrap_or_else(|| initial.clone());
            let current = value
                .get("server_index")
                .and_then(Value::as_u64)
                .unwrap_or(0);
            value["server_index"] = serde_json::json!((current + 1) % server_count.max(1) as u64);
            memory.set_value(key, value, 86400).await;
            return Ok(current as usize);
        }
        let mut redis = self.redis()?;
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
        if let Some(memory) = &self.memory {
            let value = memory
                .get_value(key)
                .await
                .unwrap_or_else(|| initial.clone());
            return Ok(value
                .get("server_index")
                .and_then(Value::as_u64)
                .unwrap_or(0) as usize);
        }
        let mut redis = self.redis()?;
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
        if let Some(memory) = &self.memory {
            return Ok(memory
                .get_value(key)
                .await
                .and_then(|value| value.as_u64())
                .unwrap_or(0));
        }
        let mut redis = self.redis()?;
        Ok(redis.get::<_, Option<u64>>(key).await?.unwrap_or(0))
    }

    pub async fn deduct_credit(&self, username: &str, group: &str) -> Result<bool, StorageError> {
        if let Some(memory) = &self.memory {
            let mut collections = memory.collections.write().await;
            let documents = collections.entry("user_credits".to_owned()).or_default();
            let Some(document) = documents
                .iter_mut()
                .find(|doc| doc.get("username").and_then(Value::as_str) == Some(username))
            else {
                return Ok(false);
            };
            let Some(available) =
                document.pointer_mut(&format!("/users_credits/{group}/available_credits"))
            else {
                return Ok(false);
            };
            let current = available.as_i64().unwrap_or(0);
            if current <= 0 {
                return Ok(false);
            }
            *available = serde_json::json!(current - 1);
            memory.bump_revision();
            return Ok(true);
        }
        let path = format!("users_credits.{group}.available_credits");
        let mut filter = doc! { "username": username };
        filter.insert(path.clone(), doc! { "$gt": 0 });
        let mut increment = Document::new();
        increment.insert(path, -1_i32);
        let result = self
            .mongo()?
            .collection::<Document>("user_credits")
            .update_one(filter, doc! { "$inc": increment })
            .await?;
        Ok(result.modified_count == 1)
    }

    pub async fn find_many(
        &self,
        collection: &str,
        filter: &Value,
    ) -> Result<Vec<Value>, StorageError> {
        if let Some(memory) = &self.memory {
            let collections = memory.collections.read().await;
            return Ok(collections
                .get(collection)
                .into_iter()
                .flatten()
                .filter(|item| value_matches(item, filter))
                .cloned()
                .collect());
        }
        let filter = mongodb::bson::to_document(filter)?;
        let mut cursor = self
            .mongo()?
            .collection::<Document>(collection)
            .find(filter)
            .await?;
        let mut values = Vec::new();
        while let Some(document) = cursor.try_next().await? {
            values.push(serde_json::to_value(document)?);
        }
        Ok(values)
    }

    pub async fn find_one(
        &self,
        collection: &str,
        filter: &Value,
    ) -> Result<Option<Value>, StorageError> {
        if let Some(memory) = &self.memory {
            let collections = memory.collections.read().await;
            return Ok(collections
                .get(collection)
                .and_then(|items| items.iter().find(|item| value_matches(item, filter)))
                .cloned());
        }
        let filter = mongodb::bson::to_document(filter)?;
        self.mongo()?
            .collection::<Document>(collection)
            .find_one(filter)
            .await?
            .map(serde_json::to_value)
            .transpose()
            .map_err(Into::into)
    }

    pub async fn insert_one(
        &self,
        collection: &str,
        mut value: Value,
    ) -> Result<Value, StorageError> {
        if value.get("_id").is_none() {
            value["_id"] = Value::String(uuid::Uuid::new_v4().to_string());
        }
        if let Some(memory) = &self.memory {
            memory
                .collections
                .write()
                .await
                .entry(collection.to_owned())
                .or_default()
                .push(value.clone());
            memory.bump_revision();
            self.invalidate_policy_cache().await;
            return Ok(value);
        }
        self.mongo()?
            .collection::<Document>(collection)
            .insert_one(mongodb::bson::to_document(&value)?)
            .await?;
        self.bump_policy_revision().await?;
        self.invalidate_policy_cache().await;
        Ok(value)
    }

    pub async fn update_one(
        &self,
        collection: &str,
        filter: &Value,
        updates: &Value,
    ) -> Result<Option<Value>, StorageError> {
        if let Some(memory) = &self.memory {
            let mut collections = memory.collections.write().await;
            let Some(item) = collections
                .entry(collection.to_owned())
                .or_default()
                .iter_mut()
                .find(|item| value_matches(item, filter))
            else {
                return Ok(None);
            };
            merge_object(item, updates);
            let result = item.clone();
            memory.bump_revision();
            self.invalidate_policy_cache().await;
            return Ok(Some(result));
        }
        let filter_document = mongodb::bson::to_document(filter)?;
        let mut update_document = mongodb::bson::to_document(updates)?;
        update_document.remove("_id");
        let result = self
            .mongo()?
            .collection::<Document>(collection)
            .update_one(filter_document.clone(), doc! { "$set": update_document })
            .await?;
        if result.matched_count == 0 {
            return Ok(None);
        }
        self.bump_policy_revision().await?;
        self.invalidate_policy_cache().await;
        self.mongo()?
            .collection::<Document>(collection)
            .find_one(filter_document)
            .await?
            .map(serde_json::to_value)
            .transpose()
            .map_err(Into::into)
    }

    pub async fn delete_one(&self, collection: &str, filter: &Value) -> Result<bool, StorageError> {
        if let Some(memory) = &self.memory {
            let mut collections = memory.collections.write().await;
            let items = collections.entry(collection.to_owned()).or_default();
            let before = items.len();
            items.retain(|item| !value_matches(item, filter));
            let deleted = before != items.len();
            if deleted {
                memory.bump_revision();
                self.invalidate_policy_cache().await;
            }
            return Ok(deleted);
        }
        let result = self
            .mongo()?
            .collection::<Document>(collection)
            .delete_one(mongodb::bson::to_document(filter)?)
            .await?;
        if result.deleted_count > 0 {
            self.bump_policy_revision().await?;
            self.invalidate_policy_cache().await;
        }
        Ok(result.deleted_count > 0)
    }

    pub async fn replace_collection(
        &self,
        collection: &str,
        values: Vec<Value>,
    ) -> Result<(), StorageError> {
        if let Some(memory) = &self.memory {
            memory
                .collections
                .write()
                .await
                .insert(collection.to_owned(), values);
            memory.bump_revision();
            self.invalidate_policy_cache().await;
            return Ok(());
        }
        let target = self.mongo()?.collection::<Document>(collection);
        target.delete_many(doc! {}).await?;
        if !values.is_empty() {
            let documents = values
                .iter()
                .map(mongodb::bson::to_document)
                .collect::<Result<Vec<_>, _>>()?;
            target.insert_many(documents).await?;
        }
        self.bump_policy_revision().await?;
        self.invalidate_policy_cache().await;
        Ok(())
    }

    pub async fn crud_find_one(
        &self,
        collection: &str,
        resource_id: &str,
    ) -> Result<Option<Value>, StorageError> {
        if let Some(memory) = &self.memory {
            let collections = memory.collections.read().await;
            return Ok(collections
                .get(collection)
                .and_then(|items| {
                    items
                        .iter()
                        .find(|item| item.get("_id").and_then(Value::as_str) == Some(resource_id))
                })
                .cloned());
        }
        let document = self
            .mongo()?
            .collection::<Document>(collection)
            .find_one(doc! { "_id": resource_id })
            .await?;
        document
            .map(serde_json::to_value)
            .transpose()
            .map_err(Into::into)
    }

    pub async fn crud_list(&self, collection: &str) -> Result<Vec<Value>, StorageError> {
        if let Some(memory) = &self.memory {
            return Ok(memory
                .collections
                .read()
                .await
                .get(collection)
                .cloned()
                .unwrap_or_default());
        }
        let mut cursor = self
            .mongo()?
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
        if let Some(memory) = &self.memory {
            memory
                .collections
                .write()
                .await
                .entry(collection.to_owned())
                .or_default()
                .push(value.clone());
            memory.bump_revision();
            return Ok(());
        }
        let document = mongodb::bson::to_document(value)?;
        self.mongo()?
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
        if let Some(memory) = &self.memory {
            let mut collections = memory.collections.write().await;
            let Some(item) = collections
                .entry(collection.to_owned())
                .or_default()
                .iter_mut()
                .find(|item| item.get("_id").and_then(Value::as_str) == Some(resource_id))
            else {
                return Ok(None);
            };
            if let (Some(target), Some(update)) = (item.as_object_mut(), value.as_object()) {
                for (key, value) in update {
                    if key != "_id" {
                        target.insert(key.clone(), value.clone());
                    }
                }
            }
            let result = item.clone();
            memory.bump_revision();
            return Ok(Some(result));
        }
        let mut update = mongodb::bson::to_document(value)?;
        update.remove("_id");
        let result = self
            .mongo()?
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
        if let Some(memory) = &self.memory {
            let mut collections = memory.collections.write().await;
            let items = collections.entry(collection.to_owned()).or_default();
            let before = items.len();
            items.retain(|item| item.get("_id").and_then(Value::as_str) != Some(resource_id));
            let deleted = before != items.len();
            if deleted {
                memory.bump_revision();
            }
            return Ok(deleted);
        }
        let result = self
            .mongo()?
            .collection::<Document>(collection)
            .delete_one(doc! { "_id": resource_id })
            .await?;
        Ok(result.deleted_count > 0)
    }

    pub async fn record_gateway_metric(
        &self,
        metric: GatewayMetric<'_>,
    ) -> Result<(), StorageError> {
        let key = format!("gateway_metrics:{}", metric.minute_start);
        if let Some(memory) = &self.memory {
            let _ = memory.increment(&format!("{key}:count"), 1, 2678400).await;
            let _ = memory
                .increment(
                    &format!("{key}:total_micros"),
                    metric.duration_micros,
                    2678400,
                )
                .await;
            return Ok(());
        }
        let mut redis = self.redis()?;
        let script = redis::Script::new(
            r#"
            redis.call('HINCRBY', KEYS[1], 'count', 1)
            redis.call('HINCRBY', KEYS[1], 'test_count', ARGV[1])
            redis.call('HINCRBY', KEYS[1], 'error_count', ARGV[2])
            redis.call('HINCRBY', KEYS[1], 'total_micros', ARGV[3])
            redis.call('HINCRBY', KEYS[1], 'bytes_in', ARGV[4])
            redis.call('HINCRBY', KEYS[1], 'bytes_out', ARGV[5])
            redis.call('HINCRBY', KEYS[1], 'status:' .. ARGV[6], 1)
            if ARGV[7] ~= '' and ARGV[1] == '0' then
                redis.call('HINCRBY', KEYS[1], 'api:' .. ARGV[7], 1)
            end
            if ARGV[8] ~= '' and ARGV[1] == '0' then
                redis.call('HINCRBY', KEYS[1], 'user:' .. ARGV[8], 1)
            end
            if ARGV[9] ~= '' and ARGV[1] == '0' then
                redis.call('HINCRBY', KEYS[1], 'endpoint:' .. ARGV[9], 1)
            end
            redis.call('EXPIRE', KEYS[1], 2678400)
            return 1
            "#,
        );
        let _: u64 = script
            .key(key)
            .arg(u8::from(metric.is_test))
            .arg(u8::from(metric.status >= 400))
            .arg(metric.duration_micros)
            .arg(metric.bytes_in)
            .arg(metric.bytes_out)
            .arg(metric.status)
            .arg(metric.api_key.unwrap_or_default())
            .arg(metric.username.unwrap_or_default())
            .arg(metric.endpoint.unwrap_or_default())
            .invoke_async(&mut redis)
            .await?;
        Ok(())
    }

    pub async fn mongo_healthy(&self) -> bool {
        if self.is_memory() {
            return true;
        }
        match self.mongo() {
            Ok(mongo) => mongo.run_command(doc! { "ping": 1 }).await.is_ok(),
            Err(_) => false,
        }
    }

    pub async fn redis_healthy(&self) -> bool {
        if self.is_memory() {
            return true;
        }
        let Ok(mut redis) = self.redis() else {
            return false;
        };
        redis::cmd("PING")
            .query_async::<String>(&mut redis)
            .await
            .is_ok()
    }

    pub async fn clear_gateway_state(&self) -> Result<(), StorageError> {
        if let Some(memory) = &self.memory {
            memory.clear_runtime().await;
            self.invalidate_policy_cache().await;
            return Ok(());
        }
        const PATTERNS: &[&str] = &[
            "api_cache:*",
            "api_endpoint_cache:*",
            "api_id_cache:*",
            "endpoint_cache:*",
            "endpoint_validation_cache:*",
            "graphql_schema_cache:*",
            "group_cache:*",
            "openapi_cache:*",
            "role_cache:*",
            "user_subscription_cache:*",
            "user_cache:*",
            "user_group_cache:*",
            "user_role_cache:*",
            "endpoint_load_balancer:*",
            "endpoint_server_cache:*",
            "client_routing_cache:*",
            "token_def_cache:*",
            "credit_def_cache:*",
            "csrf_token_map:*",
            "wsdl_cache:*",
            "rate_limit:*",
            "throttle_limit:*",
            "bandwidth_usage:*",
            "ip_rate_limit:*",
            "tier_rate_limit:*",
            "gateway_metrics:*",
        ];
        let mut redis = self.redis()?;
        for pattern in PATTERNS {
            let mut cursor = 0_u64;
            loop {
                let (next, keys): (u64, Vec<String>) = redis::cmd("SCAN")
                    .arg(cursor)
                    .arg("MATCH")
                    .arg(pattern)
                    .arg("COUNT")
                    .arg(500_u64)
                    .query_async(&mut redis)
                    .await?;
                if !keys.is_empty() {
                    let _: usize = redis::cmd("DEL").arg(keys).query_async(&mut redis).await?;
                }
                cursor = next;
                if cursor == 0 {
                    break;
                }
            }
        }
        self.bump_policy_revision().await?;
        self.invalidate_policy_cache().await;
        Ok(())
    }
}

fn value_matches(item: &Value, filter: &Value) -> bool {
    let Some(filter) = filter.as_object() else {
        return true;
    };
    filter
        .iter()
        .all(|(key, expected)| item.get(key) == Some(expected))
}

fn merge_object(target: &mut Value, updates: &Value) {
    if let (Some(target), Some(updates)) = (target.as_object_mut(), updates.as_object()) {
        for (key, value) in updates {
            if key != "_id" && !value.is_null() {
                target.insert(key.clone(), value.clone());
            }
        }
    }
}
