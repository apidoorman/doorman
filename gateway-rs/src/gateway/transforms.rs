use serde_json::Value;

#[derive(Clone, Debug, Default)]
pub struct TransformConfig {
    pub request: Option<Value>,
    pub response: Option<Value>,
}
