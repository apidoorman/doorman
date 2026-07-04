use std::{env, net::SocketAddr, str::FromStr, time::Duration};

use thiserror::Error;

#[derive(Clone, Copy, Debug, Default, Eq, PartialEq)]
pub enum GatewayMode {
    #[default]
    Off,
    Shadow,
    Canary,
    On,
}

impl GatewayMode {
    pub fn rust_routes_enabled(self) -> bool {
        !matches!(self, Self::Off)
    }
}

impl FromStr for GatewayMode {
    type Err = ConfigError;

    fn from_str(value: &str) -> Result<Self, Self::Err> {
        match value.trim().to_ascii_lowercase().as_str() {
            "off" => Ok(Self::Off),
            "shadow" => Ok(Self::Shadow),
            "canary" => Ok(Self::Canary),
            "on" => Ok(Self::On),
            other => Err(ConfigError::InvalidMode(other.to_owned())),
        }
    }
}

#[derive(Clone, Debug)]
pub struct Config {
    pub host: String,
    pub port: u16,
    pub python_base_url: String,
    pub mode: GatewayMode,
    pub connect_timeout: Duration,
    pub https_only: bool,
    pub content_security_policy: Option<String>,
}

impl Config {
    pub fn from_env() -> Result<Self, ConfigError> {
        let enabled = env_bool("GATEWAY_RUST_ENABLED", false);
        let explicit_mode = env::var("GATEWAY_RUST_MODE").ok();
        let mode = match explicit_mode {
            Some(value) => value.parse()?,
            None if enabled => GatewayMode::On,
            None => GatewayMode::Off,
        };

        if mode.rust_routes_enabled() {
            let storage = env::var("MEM_OR_EXTERNAL")
                .or_else(|_| env::var("MEM_OR_REDIS"))
                .unwrap_or_else(|_| "MEM".to_owned());
            if storage.eq_ignore_ascii_case("MEM") {
                return Err(ConfigError::MemoryModeUnsupported);
            }
        }

        Ok(Self {
            host: env::var("GATEWAY_RUST_HOST").unwrap_or_else(|_| "0.0.0.0".to_owned()),
            port: env_parse("PORT", 3001)?,
            python_base_url: env::var("PYTHON_INTERNAL_URL")
                .unwrap_or_else(|_| "http://127.0.0.1:3002".to_owned()),
            mode,
            connect_timeout: Duration::from_secs(env_parse("GATEWAY_CONNECT_TIMEOUT_SECONDS", 10)?),
            https_only: env_bool("HTTPS_ONLY", false),
            content_security_policy: env::var("CONTENT_SECURITY_POLICY")
                .ok()
                .filter(|value| !value.trim().is_empty()),
        })
    }

    pub fn bind_addr(&self) -> String {
        format!("{}:{}", self.host, self.port)
    }

    pub fn socket_addr(&self) -> Result<SocketAddr, ConfigError> {
        self.bind_addr()
            .parse()
            .map_err(|_| ConfigError::InvalidAddress(self.bind_addr()))
    }

    pub fn for_test(mode: GatewayMode, python_base_url: String) -> Self {
        Self {
            host: "127.0.0.1".to_owned(),
            port: 0,
            python_base_url,
            mode,
            connect_timeout: Duration::from_secs(1),
            https_only: false,
            content_security_policy: None,
        }
    }
}

fn env_bool(name: &str, default: bool) -> bool {
    env::var(name)
        .ok()
        .map(|value| {
            matches!(
                value.to_ascii_lowercase().as_str(),
                "1" | "true" | "yes" | "on"
            )
        })
        .unwrap_or(default)
}

fn env_parse<T>(name: &str, default: T) -> Result<T, ConfigError>
where
    T: FromStr + Copy,
{
    match env::var(name) {
        Ok(value) => value
            .parse()
            .map_err(|_| ConfigError::InvalidValue(name.to_owned(), value)),
        Err(_) => Ok(default),
    }
}

#[derive(Debug, Error)]
pub enum ConfigError {
    #[error("invalid GATEWAY_RUST_MODE: {0}")]
    InvalidMode(String),
    #[error("invalid value for {0}: {1}")]
    InvalidValue(String, String),
    #[error("invalid gateway bind address: {0}")]
    InvalidAddress(String),
    #[error("Rust gateway mode requires shared storage; MEM_OR_EXTERNAL=MEM is unsupported")]
    MemoryModeUnsupported,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_gateway_modes() {
        assert_eq!("off".parse::<GatewayMode>().unwrap(), GatewayMode::Off);
        assert_eq!("ON".parse::<GatewayMode>().unwrap(), GatewayMode::On);
        assert!("invalid".parse::<GatewayMode>().is_err());
    }
}
