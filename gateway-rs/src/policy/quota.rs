//! Quota policy enforcement module.

use std::time::{SystemTime, UNIX_EPOCH};

#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct QuotaPolicy {
    pub quota_id: String,
    pub name: String,
    pub period_seconds: u64,
    pub max_requests: u64,
    pub max_bandwidth_bytes: u64,
}

impl Default for QuotaPolicy {
    fn default() -> Self {
        Self {
            quota_id: "default_quota".to_owned(),
            name: "Default Quota".to_owned(),
            period_seconds: 86400, // 24 hours
            max_requests: 100_000,
            max_bandwidth_bytes: 10_000_000_000, // 10 GB
        }
    }
}

pub fn current_window_index(period_seconds: u64) -> u64 {
    let now = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs();
    if period_seconds == 0 { 0 } else { now / period_seconds }
}

pub fn quota_counter_key(user_id: &str, quota_id: &str, window_index: u64) -> String {
    format!("quota:{quota_id}:{user_id}:{window_index}")
}

pub fn check_quota(
    current_usage: u64,
    request_increment: u64,
    policy: &QuotaPolicy,
) -> Result<(), String> {
    if current_usage + request_increment > policy.max_requests {
        return Err(format!(
            "Quota limit exceeded for {}: max {} requests per {}s",
            policy.name, policy.max_requests, policy.period_seconds
        ));
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn validates_quota_thresholds() {
        let policy = QuotaPolicy::default();
        assert!(check_quota(99_999, 1, &policy).is_ok());
        assert!(check_quota(100_000, 1, &policy).is_err());
    }
}
