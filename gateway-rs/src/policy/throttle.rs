use http::StatusCode;
use serde_json::Value;

use super::{PolicyFailure, PolicyStage, rate_limit::duration_to_seconds};
use crate::storage::{
    cache::WindowCounter,
    models::{bool_field_default, f64_field, string_field, u64_field},
    redis::throttle_key,
};

#[derive(Clone, Copy, Debug, Default, Eq, PartialEq)]
pub struct ThrottleOutcome {
    pub delay_ms: Option<u64>,
}

pub fn enforce_throttle(
    username: &str,
    user: &Value,
    counter: &WindowCounter,
    now_millis: u64,
) -> Result<ThrottleOutcome, PolicyFailure> {
    let enabled = bool_field_default(user, "throttle_enabled", false)
        || user.get("throttle_duration").is_some()
        || user.get("throttle_queue_limit").is_some();
    if !enabled {
        return Ok(ThrottleOutcome::default());
    }

    let throttle_limit = u64_field(user, "throttle_duration").unwrap_or(10);
    let duration = string_field(user, "throttle_duration_type").unwrap_or("second");
    let window = duration_to_seconds(duration);
    let window_ms = window.max(1) * 1000;
    let window_index = now_millis / window_ms;
    let count = counter.incr(
        &throttle_key(username, window_index),
        window,
        now_millis / 1000,
    );
    let queue_limit = u64_field(user, "throttle_queue_limit").unwrap_or(10);
    if queue_limit > 0 && count > queue_limit {
        return Err(queue_limit_exceeded());
    }
    let excess = count.saturating_sub(throttle_limit);
    if queue_limit > 0 && excess > queue_limit {
        return Err(queue_limit_exceeded());
    }
    if count > throttle_limit {
        let delay_ms = throttle_wait_millis(user, excess);
        return Ok(ThrottleOutcome {
            delay_ms: Some(delay_ms),
        });
    }
    Ok(ThrottleOutcome::default())
}

pub fn throttle_wait_millis(user: &Value, excess: u64) -> u64 {
    let wait = f64_field(user, "throttle_wait_duration")
        .filter(|value| value.is_finite() && *value > 0.0)
        .unwrap_or(0.5);
    let wait_unit = string_field(user, "throttle_wait_duration_type").unwrap_or("second");
    (wait * duration_to_seconds(wait_unit) as f64 * 1_000.0 * excess.max(1) as f64).round() as u64
}
fn queue_limit_exceeded() -> PolicyFailure {
    PolicyFailure::new(
        PolicyStage::Throttle,
        StatusCode::TOO_MANY_REQUESTS,
        "Throttle queue limit exceeded",
        "Throttle queue limit exceeded",
    )
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn returns_delay_before_queue_limit() {
        let user = json!({
            "throttle_enabled": true,
            "throttle_duration": 1,
            "throttle_duration_type": "minute",
            "throttle_queue_limit": 3,
            "throttle_wait_duration": 1,
            "throttle_wait_duration_type": "second",
        });
        let counter = WindowCounter::default();
        assert_eq!(
            enforce_throttle("alice", &user, &counter, 0)
                .unwrap()
                .delay_ms,
            None
        );
        assert_eq!(
            enforce_throttle("alice", &user, &counter, 1)
                .unwrap()
                .delay_ms,
            Some(1000)
        );
    }
    #[test]
    fn python_test_throttle_queue_limit_exceeded_returns_429() {
        let user = json!({"throttle_duration": 1, "throttle_duration_type": "second", "throttle_queue_limit": 1});
        let counter = WindowCounter::default();
        assert_eq!(
            enforce_throttle("admin", &user, &counter, 1_000)
                .unwrap()
                .delay_ms,
            None
        );
        let failure = enforce_throttle("admin", &user, &counter, 1_001).unwrap_err();
        assert_eq!(failure.stage, PolicyStage::Throttle);
        assert_eq!(failure.status, StatusCode::TOO_MANY_REQUESTS);
        assert_eq!(failure.error_message, "Throttle queue limit exceeded");
    }
    #[test]
    fn python_test_throttle_dynamic_wait_uses_fractional_seconds() {
        let user = json!({"throttle_duration": 1, "throttle_duration_type": "second", "throttle_queue_limit": 10, "throttle_wait_duration": 0.1, "throttle_wait_duration_type": "second"});
        let counter = WindowCounter::default();
        assert_eq!(
            enforce_throttle("admin", &user, &counter, 1_000)
                .unwrap()
                .delay_ms,
            None
        );
        assert_eq!(
            enforce_throttle("admin", &user, &counter, 1_001)
                .unwrap()
                .delay_ms,
            Some(100)
        );
    }
}
