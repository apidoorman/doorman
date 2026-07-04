use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::HashMap;

#[derive(Clone, Debug, Default, Deserialize, Serialize)]
pub struct ApiDocument {
    #[serde(flatten)]
    pub fields: HashMap<String, Value>,
}
