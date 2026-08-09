use std::collections::{HashMap, VecDeque};
use std::sync::{Arc, RwLock};
use std::time::{SystemTime, UNIX_EPOCH};
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct AggregatedPoint {
    pub timestamp: u64,
    pub requests: u64,
    pub errors: u64,
    pub latency_ms: f64,
    pub bytes_in: u64,
    pub bytes_out: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct EntityCounter {
    pub name: String,
    pub count: u64,
    pub error_count: u64,
}

pub struct AnalyticsAggregator {
    points: RwLock<VecDeque<AggregatedPoint>>,
    api_counters: RwLock<HashMap<String, u64>>,
    user_counters: RwLock<HashMap<String, u64>>,
    endpoint_counters: RwLock<HashMap<String, u64>>,
}

impl AnalyticsAggregator {
    pub fn new() -> Self {
        Self {
            points: RwLock::new(VecDeque::with_capacity(1440)), // 24 hours of minute buckets
            api_counters: RwLock::new(HashMap::new()),
            user_counters: RwLock::new(HashMap::new()),
            endpoint_counters: RwLock::new(HashMap::new()),
        }
    }

    pub fn record_request(
        &self,
        api_name: Option<&str>,
        username: Option<&str>,
        endpoint: Option<&str>,
        status: u16,
        duration_ms: f64,
        bytes_in: u64,
        bytes_out: u64,
    ) {
        let now = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs();
        let minute_ts = (now / 60) * 60;
        let is_error = status >= 400;

        if let Some(api) = api_name {
            if let Ok(mut map) = self.api_counters.write() {
                *map.entry(api.to_owned()).or_insert(0) += 1;
            }
        }
        if let Some(user) = username {
            if let Ok(mut map) = self.user_counters.write() {
                *map.entry(user.to_owned()).or_insert(0) += 1;
            }
        }
        if let Some(ep) = endpoint {
            if let Ok(mut map) = self.endpoint_counters.write() {
                *map.entry(ep.to_owned()).or_insert(0) += 1;
            }
        }

        if let Ok(mut pts) = self.points.write() {
            if let Some(last) = pts.back_mut() {
                if last.timestamp == minute_ts {
                    last.requests += 1;
                    if is_error {
                        last.errors += 1;
                    }
                    last.bytes_in += bytes_in;
                    last.bytes_out += bytes_out;
                    last.latency_ms = (last.latency_ms + duration_ms) / 2.0;
                    return;
                }
            }
            if pts.len() >= 1440 {
                pts.pop_front();
            }
            pts.push_back(AggregatedPoint {
                timestamp: minute_ts,
                requests: 1,
                errors: if is_error { 1 } else { 0 },
                latency_ms: duration_ms,
                bytes_in,
                bytes_out,
            });
        }
    }

    pub fn get_timeseries(&self) -> Vec<AggregatedPoint> {
        self.points
            .read()
            .map(|pts| pts.iter().cloned().collect())
            .unwrap_or_default()
    }

    pub fn get_top_apis(&self, limit: usize) -> Vec<EntityCounter> {
        let mut items: Vec<EntityCounter> = self
            .api_counters
            .read()
            .map(|map| {
                map.iter()
                    .map(|(k, v)| EntityCounter {
                        name: k.clone(),
                        count: *v,
                        error_count: 0,
                    })
                    .collect()
            })
            .unwrap_or_default();
        items.sort_by(|a, b| b.count.cmp(&a.count));
        items.truncate(limit);
        items
    }

    pub fn get_top_users(&self, limit: usize) -> Vec<EntityCounter> {
        let mut items: Vec<EntityCounter> = self
            .user_counters
            .read()
            .map(|map| {
                map.iter()
                    .map(|(k, v)| EntityCounter {
                        name: k.clone(),
                        count: *v,
                        error_count: 0,
                    })
                    .collect()
            })
            .unwrap_or_default();
        items.sort_by(|a, b| b.count.cmp(&a.count));
        items.truncate(limit);
        items
    }

    pub fn get_top_endpoints(&self, limit: usize) -> Vec<EntityCounter> {
        let mut items: Vec<EntityCounter> = self
            .endpoint_counters
            .read()
            .map(|map| {
                map.iter()
                    .map(|(k, v)| EntityCounter {
                        name: k.clone(),
                        count: *v,
                        error_count: 0,
                    })
                    .collect()
            })
            .unwrap_or_default();
        items.sort_by(|a, b| b.count.cmp(&a.count));
        items.truncate(limit);
        items
    }
}

pub static GLOBAL_ANALYTICS: std::sync::OnceLock<Arc<AnalyticsAggregator>> = std::sync::OnceLock::new();

pub fn global_analytics() -> &'static Arc<AnalyticsAggregator> {
    GLOBAL_ANALYTICS.get_or_init(|| Arc::new(AnalyticsAggregator::new()))
}
