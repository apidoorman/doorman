use std::sync::{Arc, Mutex};

use reqwest::{Client, redirect::Policy};
use thiserror::Error;

use crate::{
    config::{Config, GatewayMode},
    storage::{
        models::PolicyDocuments,
        runtime::{SharedStorage, StorageError},
    },
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
}

impl AppState {
    pub fn new(config: Config) -> Result<Self, reqwest::Error> {
        let proxy_client = Client::builder()
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
        })
    }

    pub async fn from_config(config: Config) -> Result<Self, StateError> {
        let mut state = Self::new(config)?;
        if state.config.mode != GatewayMode::Off {
            match SharedStorage::connect(&state.config.shared_storage).await {
                Ok(storage) => state.storage = Some(Arc::new(storage)),
                Err(error) if state.config.mode.requires_shared_storage() => {
                    return Err(StateError::Storage(error));
                }
                Err(error) => {
                    tracing::warn!(error = %error, "shadow policy storage unavailable");
                }
            }
        }
        Ok(state)
    }

    pub fn with_policy_documents(mut self, documents: PolicyDocuments) -> Self {
        self.policy_documents = Some(Arc::new(Mutex::new(documents)));
        self
    }
}
