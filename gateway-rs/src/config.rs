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
    pub fn proxies_all_routes(self) -> bool {
        matches!(self, Self::Off)
    }

    pub fn should_serve_rust_route(self, canary_safe: bool) -> bool {
        match self {
            Self::Off | Self::Shadow => false,
            Self::Canary => canary_safe,
            Self::On => true,
        }
    }

    pub fn requires_shared_storage(self) -> bool {
        matches!(self, Self::Canary | Self::On)
    }

    pub fn evaluates_policies(self) -> bool {
        !matches!(self, Self::Off)
    }

    pub fn enforces_policies(self) -> bool {
        matches!(self, Self::Canary | Self::On)
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
    pub shared_storage: SharedStorageConfig,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct SharedStorageConfig {
    pub storage_mode: String,
    pub mongo_hosts: String,
    pub mongo_replica_set: Option<String>,
    pub mongo_user: Option<String>,
    pub mongo_password: Option<String>,
    pub mongo_database: String,
    pub mongo_auth_source: Option<String>,
    pub redis_host: String,
    pub redis_port: u16,
    pub redis_db: u32,
    pub redis_password: Option<String>,
    pub jwt_keys_json: Option<String>,
    pub jwt_secret: Option<String>,
    pub token_encryption_key: Option<String>,
    pub trust_x_forwarded_for: bool,
    pub local_host_ip_bypass: bool,
    pub policy_cache_ttl_seconds: u64,
}

impl SharedStorageConfig {
    fn from_env() -> Result<Self, ConfigError> {
        Ok(Self {
            storage_mode: env::var("MEM_OR_EXTERNAL")
                .or_else(|_| env::var("MEM_OR_REDIS"))
                .unwrap_or_else(|_| "MEM".to_owned()),
            mongo_hosts: env::var("MONGO_DB_HOSTS")
                .unwrap_or_else(|_| "localhost:27017".to_owned()),
            mongo_replica_set: env_non_empty("MONGO_REPLICA_SET_NAME"),
            mongo_user: env_non_empty("MONGO_DB_USER"),
            mongo_password: env_non_empty("MONGO_DB_PASSWORD"),
            mongo_database: env::var("MONGO_DB_NAME").unwrap_or_else(|_| "doorman".to_owned()),
            mongo_auth_source: env_non_empty("MONGO_DB_AUTH_SOURCE"),
            redis_host: env::var("REDIS_HOST").unwrap_or_else(|_| "localhost".to_owned()),
            redis_port: env_parse("REDIS_PORT", 6379)?,
            redis_db: env_parse("REDIS_DB", 0)?,
            redis_password: env_non_empty("REDIS_PASSWORD"),
            jwt_keys_json: env_non_empty("JWT_KEYS"),
            jwt_secret: env_non_empty("JWT_SECRET_KEY"),
            token_encryption_key: env_non_empty("TOKEN_ENCRYPTION_KEY")
                .or_else(|| env_non_empty("MEM_ENCRYPTION_KEY")),
            trust_x_forwarded_for: env_bool("TRUST_X_FORWARDED_FOR", false),
            local_host_ip_bypass: env_bool("LOCAL_HOST_IP_BYPASS", true),
            policy_cache_ttl_seconds: env_parse("GATEWAY_POLICY_CACHE_TTL_SECONDS", 1)?,
        })
    }

    pub fn mongo_uri(&self) -> String {
        let auth = match (&self.mongo_user, &self.mongo_password) {
            (Some(user), Some(password)) => format!("{user}:{password}@"),
            _ => String::new(),
        };
        let mut options = Vec::new();
        if self.mongo_hosts.contains(',')
            && let Some(value) = self
                .mongo_replica_set
                .as_deref()
                .filter(|value| !value.is_empty())
        {
            options.push(format!("replicaSet={value}"));
        }
        if let Some(value) = self
            .mongo_auth_source
            .as_deref()
            .filter(|value| !value.is_empty())
        {
            options.push(format!("authSource={value}"));
        }
        let query = if options.is_empty() {
            String::new()
        } else {
            format!("?{}", options.join("&"))
        };
        format!(
            "mongodb://{auth}{}/{database}{query}",
            self.mongo_hosts,
            database = self.mongo_database
        )
    }

    pub fn redis_url(&self) -> String {
        match &self.redis_password {
            Some(password) => format!(
                "redis://:{}@{}:{}/{}",
                password, self.redis_host, self.redis_port, self.redis_db
            ),
            None => format!(
                "redis://{}:{}/{}",
                self.redis_host, self.redis_port, self.redis_db
            ),
        }
    }

    fn validate_required(&self) -> Result<(), ConfigError> {
        if self.storage_mode.eq_ignore_ascii_case("MEM") {
            return Err(ConfigError::MemoryModeUnsupported);
        }
        if self.mongo_user.is_none() {
            return Err(ConfigError::MissingEnv("MONGO_DB_USER"));
        }
        if self.mongo_password.is_none() {
            return Err(ConfigError::MissingEnv("MONGO_DB_PASSWORD"));
        }
        if self.jwt_keys_json.is_none() && self.jwt_secret.is_none() {
            return Err(ConfigError::MissingEnv("JWT_SECRET_KEY or JWT_KEYS"));
        }
        Ok(())
    }
}

impl Default for SharedStorageConfig {
    fn default() -> Self {
        Self {
            storage_mode: "MEM".to_owned(),
            mongo_hosts: "localhost:27017".to_owned(),
            mongo_replica_set: Some("rs0".to_owned()),
            mongo_user: Some("doorman_admin".to_owned()),
            mongo_password: Some("changeme".to_owned()),
            mongo_database: "doorman".to_owned(),
            mongo_auth_source: Some("admin".to_owned()),
            redis_host: "localhost".to_owned(),
            redis_port: 6379,
            redis_db: 0,
            redis_password: None,
            jwt_keys_json: None,
            jwt_secret: Some("insecure-test-key".to_owned()),
            token_encryption_key: None,
            trust_x_forwarded_for: false,
            local_host_ip_bypass: true,
            policy_cache_ttl_seconds: 1,
        }
    }
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
        let shared_storage = SharedStorageConfig::from_env()?;

        if mode.requires_shared_storage() {
            shared_storage.validate_required()?;
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
            shared_storage,
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
            shared_storage: SharedStorageConfig::default(),
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

fn env_non_empty(name: &str) -> Option<String> {
    env::var(name).ok().filter(|value| !value.trim().is_empty())
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
    #[error("Rust route mode requires shared storage; MEM_OR_EXTERNAL=MEM is unsupported")]
    MemoryModeUnsupported,
    #[error("missing required environment variable for Rust gateway mode: {0}")]
    MissingEnv(&'static str),
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_gateway_modes() {
        assert_eq!("off".parse::<GatewayMode>().unwrap(), GatewayMode::Off);
        assert_eq!(
            "shadow".parse::<GatewayMode>().unwrap(),
            GatewayMode::Shadow
        );
        assert_eq!(
            "canary".parse::<GatewayMode>().unwrap(),
            GatewayMode::Canary
        );
        assert_eq!("ON".parse::<GatewayMode>().unwrap(), GatewayMode::On);
        assert!("invalid".parse::<GatewayMode>().is_err());
    }

    #[test]
    fn mode_route_decisions_are_distinct() {
        assert!(GatewayMode::Off.proxies_all_routes());
        assert!(!GatewayMode::Shadow.proxies_all_routes());
        assert!(!GatewayMode::Canary.proxies_all_routes());
        assert!(!GatewayMode::On.proxies_all_routes());

        assert!(!GatewayMode::Off.should_serve_rust_route(true));
        assert!(!GatewayMode::Shadow.should_serve_rust_route(true));
        assert!(GatewayMode::Canary.should_serve_rust_route(true));
        assert!(!GatewayMode::Canary.should_serve_rust_route(false));
        assert!(GatewayMode::On.should_serve_rust_route(true));
        assert!(GatewayMode::On.should_serve_rust_route(false));

        assert!(!GatewayMode::Off.evaluates_policies());
        assert!(GatewayMode::Shadow.evaluates_policies());
        assert!(!GatewayMode::Shadow.enforces_policies());
        assert!(GatewayMode::Canary.enforces_policies());
        assert!(GatewayMode::On.enforces_policies());

        assert!(!GatewayMode::Shadow.requires_shared_storage());
        assert!(GatewayMode::Canary.requires_shared_storage());
        assert!(GatewayMode::On.requires_shared_storage());
    }

    #[test]
    fn builds_python_compatible_storage_urls() {
        let storage = SharedStorageConfig {
            storage_mode: "REDIS".to_owned(),
            mongo_hosts: "mongo-a:27017,mongo-b:27017".to_owned(),
            mongo_replica_set: Some("rs0".to_owned()),
            mongo_user: Some("doorman".to_owned()),
            mongo_password: Some("secret".to_owned()),
            mongo_database: "doorman".to_owned(),
            mongo_auth_source: Some("admin".to_owned()),
            redis_host: "redis".to_owned(),
            redis_port: 6380,
            redis_db: 2,
            redis_password: Some("redis-secret".to_owned()),
            jwt_keys_json: None,
            jwt_secret: Some("jwt".to_owned()),
            token_encryption_key: None,
            trust_x_forwarded_for: false,
            local_host_ip_bypass: true,
            policy_cache_ttl_seconds: 1,
        };

        assert_eq!(
            storage.mongo_uri(),
            "mongodb://doorman:secret@mongo-a:27017,mongo-b:27017/doorman?replicaSet=rs0&authSource=admin"
        );
        assert_eq!(storage.redis_url(), "redis://:redis-secret@redis:6380/2");
    }
}
