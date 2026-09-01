use crate::config::SharedStorageConfig;

#[derive(Clone, Debug)]
pub struct RedisRepositoryConfig {
    pub url: String,
}

impl RedisRepositoryConfig {
    pub fn from_shared_config(config: &SharedStorageConfig) -> Self {
        Self {
            url: config.redis_url(),
        }
    }
}

pub fn rate_limit_key(username: &str, window_index: u64) -> String {
    format!("rate_limit:{username}:{window_index}")
}

pub fn throttle_key(username: &str, window_index: u64) -> String {
    format!("throttle_limit:{username}:{window_index}")
}

pub fn bandwidth_key(username: &str, seconds: u64, bucket_start: u64) -> String {
    format!("bandwidth_usage:{username}:{seconds}:{bucket_start}")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn matches_python_counter_keys() {
        assert_eq!(rate_limit_key("admin", 10), "rate_limit:admin:10");
        assert_eq!(throttle_key("admin", 10), "throttle_limit:admin:10");
        assert_eq!(
            bandwidth_key("admin", 86400, 172800),
            "bandwidth_usage:admin:86400:172800"
        );
    }
}
