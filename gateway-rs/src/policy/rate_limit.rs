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
    let window_millis = window * 1000;
    let window_index = now_millis / window_millis;
    let now_seconds = now_millis / 1000;

    let count = counter.incr(
        &rate_limit_key(username, window_index),
        window * 2,
        now_seconds,
    );

    let algorithm = string_field(user, "rate_limit_algorithm").unwrap_or("fixed_window");
    let effective_count = if algorithm.eq_ignore_ascii_case("sliding_window") && window_index > 0 {
        let prev_index = window_index - 1;
        let prev_key = rate_limit_key(username, prev_index);
        let prev_count = counter.get(&prev_key, now_seconds);
        let time_into_current_window = (now_millis % window_millis) as f64 / window_millis as f64;
        let weight = (1.0 - time_into_current_window).max(0.0);
        (prev_count as f64 * weight + count as f64).ceil() as u64
    } else {
        count
    };

    if effective_count > limit {
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

    #[test]
    fn enforces_sliding_window() {
        let user = json!({
            "rate_limit_enabled": true,
            "rate_limit_duration": 5,
            "rate_limit_duration_type": "minute",
            "rate_limit_algorithm": "sliding_window"
        });
        let counter = WindowCounter::default();
        for _ in 0..5 {
            counter.incr(&rate_limit_key("bob", 0), 120, 0);
        }
        assert!(enforce_rate_limit("bob", &user, &counter, 60_001).is_err());
    }
}
