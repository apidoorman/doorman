use http::StatusCode;
use serde_json::Value;

use super::{PolicyFailure, PolicyStage};
use crate::storage::{
    cache::WindowCounter,
    models::{bool_field_default, string_field, u64_field},
    redis::rate_limit_key,
};

pub fn duration_to_seconds(duration: &str) -> u64 {
    let duration = duration.trim().trim_end_matches('s').to_ascii_lowercase();
    match duration.as_str() {
        "second" => 1,
        "minute" => 60,
        "hour" => 3600,
        "day" => 86400,
        "week" => 604800,
        "month" => 2592000,
        "year" => 31536000,
        _ => 60,
    }
}

pub fn enforce_rate_limit(
    username: &str,
    user: &Value,
    counter: &WindowCounter,
    now_millis: u64,
) -> Result<(), PolicyFailure> {
    let rate_enabled = bool_field_default(user, "rate_limit_enabled", false)
        || user.get("rate_limit_duration").is_some();
    if !rate_enabled {
        return Ok(());
    }
    let limit = u64_field(user, "rate_limit_duration").unwrap_or(60);
    let duration = string_field(user, "rate_limit_duration_type").unwrap_or("minute");
    let window = duration_to_seconds(duration);
    let window_index = now_millis / (window * 1000);
    let count = counter.incr(
        &rate_limit_key(username, window_index),
        window,
        now_millis / 1000,
    );
    if count > limit {
        Err(PolicyFailure::new(
            PolicyStage::RateLimit,
            StatusCode::TOO_MANY_REQUESTS,
            "Rate limit exceeded",
            "Rate limit exceeded",
        ))
    } else {
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn enforces_user_rate_window() {
        let user = json!({
            "rate_limit_enabled": true,
            "rate_limit_duration": 1,
            "rate_limit_duration_type": "minute",
        });
        let counter = WindowCounter::default();
        assert!(enforce_rate_limit("alice", &user, &counter, 60_000).is_ok());
        assert!(enforce_rate_limit("alice", &user, &counter, 61_000).is_err());
    }
}
