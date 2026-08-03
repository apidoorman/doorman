use http::StatusCode;
use serde::Serialize;
use serde_json::Value;

pub mod auth;
pub mod bandwidth;
pub mod credits;
pub mod evaluator;
pub mod groups;
pub mod ip;
pub mod quota;
pub mod rate_limit;
pub mod roles;
pub mod subscription;
pub mod throttle;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum PolicyStage {
    Resolution,
    Ip,
    Subscription,
    Group,
    RateLimit,
    Throttle,
    Authentication,
    Role,
    Bandwidth,
    Credits,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct PolicyFailure {
    pub stage: PolicyStage,
    pub status: StatusCode,
    pub error_code: String,
    pub error_message: String,
}

impl PolicyFailure {
    pub fn new(
        stage: PolicyStage,
        status: StatusCode,
        error_code: impl Into<String>,
        error_message: impl Into<String>,
    ) -> Self {
        Self {
            stage,
            status,
            error_code: error_code.into(),
            error_message: error_message.into(),
        }
    }
}

#[derive(Clone, Debug, Default, Eq, PartialEq)]
pub struct PolicyDecision {
    pub route: Option<String>,
    pub api_id: Option<String>,
    pub username: Option<String>,
    pub upstream: Option<String>,
    pub upstream_path: Option<String>,
    pub allowed_headers: Vec<String>,
    pub throttle_delay_ms: Option<u64>,
    pub credit_required: bool,
    pub credit_group: Option<String>,
    pub credit_header_name: Option<String>,
    pub credit_header_value: Option<String>,
    pub user_credit_header_value: Option<String>,
    pub routing_key: Option<String>,
    pub routing_servers: Vec<String>,
    pub routing_cache_value: Option<Value>,
    pub bandwidth_key: Option<String>,
    pub bandwidth_ttl_seconds: Option<u64>,
    pub retry_count: u32,
    pub request_timeout_ms: u64,
    pub graphql_max_depth: u64,
    pub authorization_field_swap: Option<String>,
    pub is_crud: bool,
    pub crud_collection: Option<String>,
    pub crud_schema: Option<Value>,
}

#[derive(Serialize)]
pub struct PolicyErrorBody {
    pub error_code: String,
    pub error_message: String,
}
