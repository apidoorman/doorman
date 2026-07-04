use reqwest::{Client, redirect::Policy};

use crate::config::Config;

#[derive(Clone)]
pub struct AppState {
    pub config: Config,
    pub proxy_client: Client,
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
        })
    }
}
