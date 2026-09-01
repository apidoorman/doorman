use std::{
    collections::{BTreeMap, HashMap},
    sync::{Arc, Mutex, atomic::AtomicU64},
    time::Instant,
};

use reqwest::{Client, redirect::Policy};
use thiserror::Error;

use crate::{
    config::Config,
    gateway::circuit_breaker::CircuitEntry,
    hot_reload::HotReloadConfig,
    storage::{
        models::PolicyDocuments,
        runtime::{SharedStorage, StorageError},
    },
    validation::json::ValidatorRegistry,
};

#[derive(Debug, Error)]
pub enum StateError {
    #[error("failed to construct gateway HTTP client: {0}")]
    Http(#[from] reqwest::Error),
    #[error("required shared storage is unavailable: {0}")]
    Storage(#[from] StorageError),
}

#[derive(Clone)]
pub struct AppState {
    pub config: Config,
    pub proxy_client: Client,
    pub policy_documents: Option<Arc<Mutex<PolicyDocuments>>>,
    pub storage: Option<Arc<SharedStorage>>,
    pub runtime: Arc<GatewayRuntime>,
    pub hot_reload: Arc<HotReloadConfig>,
    pub validators: Arc<ValidatorRegistry>,
}

pub struct GatewayRuntime {
    pub started_at: Instant,
    pub active_requests: AtomicU64,
    pub request_total: AtomicU64,
    pub request_duration_micros: AtomicU64,
    pub request_duration_buckets: [AtomicU64; 11],
    pub total_bytes_in: AtomicU64,
    pub total_bytes_out: AtomicU64,
    pub responses_by_status: Mutex<BTreeMap<u16, u64>>,
    pub circuits: Mutex<HashMap<String, CircuitEntry>>,
    pub retries_total: AtomicU64,
    pub upstream_timeouts_total: AtomicU64,
}

impl Default for GatewayRuntime {
    fn default() -> Self {
        Self {
            started_at: Instant::now(),
            active_requests: AtomicU64::new(0),
            request_total: AtomicU64::new(0),
            request_duration_micros: AtomicU64::new(0),
            request_duration_buckets: std::array::from_fn(|_| AtomicU64::new(0)),
            total_bytes_in: AtomicU64::new(0),
            total_bytes_out: AtomicU64::new(0),
            responses_by_status: Mutex::new(BTreeMap::new()),
            circuits: Mutex::new(HashMap::new()),
            retries_total: AtomicU64::new(0),
            upstream_timeouts_total: AtomicU64::new(0),
        }
    }
}

impl AppState {
    pub fn new(config: Config) -> Result<Self, reqwest::Error> {
        let proxy_client = Client::builder()
            .user_agent("doorman-gateway/2.0.0 (compatible; httpx/0.27)")
            .connect_timeout(config.connect_timeout)
            .redirect(Policy::none())
            .pool_max_idle_per_host(32)
            .tcp_keepalive(std::time::Duration::from_secs(60))
            .build()?;
        Ok(Self {
            config,
            proxy_client,
            policy_documents: None,
            storage: None,
            runtime: Arc::new(GatewayRuntime::default()),
            hot_reload: Arc::new(HotReloadConfig::from_env()),
            validators: Arc::new(ValidatorRegistry::default()),
        })
    }

    pub async fn from_config(config: Config) -> Result<Self, StateError> {
        let mut state = Self::new(config)?;
        let storage = SharedStorage::connect(&state.config.shared_storage).await?;
        storage.initialize_core().await?;
        state.storage = Some(Arc::new(storage));
        Ok(state)
    }

    pub fn with_policy_documents(mut self, documents: PolicyDocuments) -> Self {
        self.policy_documents = Some(Arc::new(Mutex::new(documents)));
        self
    }

    pub fn with_validator(
        mut self,
        name: impl Into<String>,
        validator: impl Fn(&serde_json::Value, &serde_json::Value) -> Result<(), String>
        + Send
        + Sync
        + 'static,
    ) -> Self {
        Arc::make_mut(&mut self.validators).register(name, validator);
        self
    }
}
