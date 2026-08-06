use std::{
    collections::HashMap,
    env,
    sync::Mutex,
    time::{Duration, Instant},
};

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum CircuitState {
    Closed,
    Open,
    HalfOpen,
}

#[derive(Clone, Debug)]
pub struct CircuitEntry {
    pub failures: u64,
    pub opened_at: Option<Instant>,
    pub state: CircuitState,
}

impl Default for CircuitEntry {
    fn default() -> Self {
        Self {
            failures: 0,
            opened_at: None,
            state: CircuitState::Closed,
        }
    }
}

pub fn check(circuits: &Mutex<HashMap<String, CircuitEntry>>, key: &str) -> bool {
    if !enabled() {
        return true;
    }
    let Ok(mut circuits) = circuits.lock() else {
        return false;
    };
    let entry = circuits.entry(key.to_owned()).or_default();
    if entry.state != CircuitState::Open {
        return true;
    }
    let elapsed = entry.opened_at.map(|opened| opened.elapsed());
    if elapsed.is_some_and(|elapsed| elapsed >= open_duration()) {
        entry.state = CircuitState::HalfOpen;
        entry.failures = 0;
        true
    } else {
        false
    }
}

pub fn record_success(circuits: &Mutex<HashMap<String, CircuitEntry>>, key: &str) {
    if !enabled() {
        return;
    }
    if let Ok(mut circuits) = circuits.lock() {
        let entry = circuits.entry(key.to_owned()).or_default();
        entry.failures = 0;
        entry.opened_at = None;
        entry.state = CircuitState::Closed;
    }
}

pub fn record_failure(circuits: &Mutex<HashMap<String, CircuitEntry>>, key: &str) {
    if !enabled() {
        return;
    }
    if let Ok(mut circuits) = circuits.lock() {
        let entry = circuits.entry(key.to_owned()).or_default();
        entry.failures = entry.failures.saturating_add(1);
        if entry.state == CircuitState::HalfOpen || entry.failures >= threshold() {
            entry.state = CircuitState::Open;
            entry.opened_at = Some(Instant::now());
        }
    }
}

pub fn reset(circuits: &Mutex<HashMap<String, CircuitEntry>>) {
    if let Ok(mut circuits) = circuits.lock() {
        circuits.clear();
    }
}

fn enabled() -> bool {
    !env::var("CIRCUIT_BREAKER_ENABLED")
        .ok()
        .is_some_and(|value| value.trim().eq_ignore_ascii_case("false"))
}

fn threshold() -> u64 {
    env::var("CIRCUIT_BREAKER_THRESHOLD")
        .ok()
        .and_then(|value| value.parse().ok())
        .unwrap_or(5)
        .max(1)
}

fn open_duration() -> Duration {
    Duration::from_secs_f64(
        env::var("CIRCUIT_BREAKER_TIMEOUT")
            .ok()
            .and_then(|value| value.parse().ok())
            .unwrap_or(30.0_f64)
            .max(0.0),
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn closes_on_success() {
        let circuits = Mutex::new(HashMap::new());
        record_failure(&circuits, "api");
        record_success(&circuits, "api");
        assert_eq!(circuits.lock().unwrap()["api"].state, CircuitState::Closed);
    }
}
