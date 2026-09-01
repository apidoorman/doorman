use serde::{Deserialize, Serialize};
use serde_json::{Map, Value};
use std::collections::HashMap;

pub type Document = Map<String, Value>;

#[derive(Clone, Debug, Default, Deserialize, Serialize)]
pub struct ApiDocument {
    #[serde(flatten)]
    pub fields: HashMap<String, Value>,
}

#[derive(Clone, Debug, Default)]
pub struct PolicyDocuments {
    pub apis: Vec<Value>,
    pub endpoints: Vec<Value>,
    pub endpoint_validations: Vec<Value>,
    pub users: Vec<Value>,
    pub roles: Vec<Value>,
    pub subscriptions: Vec<Value>,
    pub routings: Vec<Value>,
    pub credit_defs: Vec<Value>,
    pub user_credits: Vec<Value>,
    pub settings: Vec<Value>,
    pub revocations: Vec<Value>,
    pub tiers: Vec<Value>,
    pub tier_assignments: Vec<Value>,
}

pub fn api_name_version(name: &str, version: &str, leading_slash: bool) -> String {
    if leading_slash {
        format!("/{name}/{version}")
    } else {
        format!("{name}/{version}")
    }
}

pub fn strip_mongo_id(value: &mut Value) {
    if let Value::Object(map) = value {
        map.remove("_id");
    }
}

pub fn string_field<'a>(value: &'a Value, field: &str) -> Option<&'a str> {
    value.get(field).and_then(Value::as_str)
}

pub fn owned_string_field(value: &Value, field: &str) -> Option<String> {
    string_field(value, field).map(str::to_owned)
}

pub fn bool_field(value: &Value, field: &str) -> Option<bool> {
    value.get(field).and_then(Value::as_bool)
}

pub fn bool_field_default(value: &Value, field: &str, default: bool) -> bool {
    bool_field(value, field).unwrap_or(default)
}

pub fn i64_field(value: &Value, field: &str) -> Option<i64> {
    match value.get(field) {
        Some(Value::Number(number)) => number.as_i64(),
        Some(Value::String(raw)) => raw.parse().ok(),
        _ => None,
    }
}

pub fn u64_field(value: &Value, field: &str) -> Option<u64> {
    match value.get(field) {
        Some(Value::Number(number)) => number.as_u64(),
        Some(Value::String(raw)) => raw.parse().ok(),
        _ => None,
    }
}

pub fn string_list_field(value: &Value, field: &str) -> Vec<String> {
    value
        .get(field)
        .and_then(Value::as_array)
        .map(|items| {
            items
                .iter()
                .filter_map(Value::as_str)
                .map(str::to_owned)
                .collect()
        })
        .unwrap_or_default()
}

pub fn object_field<'a>(value: &'a Value, field: &str) -> Option<&'a Map<String, Value>> {
    value.get(field).and_then(Value::as_object)
}

pub fn find_by_string<'a>(items: &'a [Value], field: &str, expected: &str) -> Option<&'a Value> {
    items
        .iter()
        .find(|item| string_field(item, field).is_some_and(|actual| actual == expected))
}

pub fn find_api<'a>(items: &'a [Value], name: &str, version: &str) -> Option<&'a Value> {
    items.iter().find(|item| {
        string_field(item, "api_name").is_some_and(|actual| actual == name)
            && string_field(item, "api_version").is_some_and(|actual| actual == version)
    })
}

pub fn find_endpoint<'a>(
    items: &'a [Value],
    api: &Value,
    method: &str,
    routing_uri: &str,
) -> Option<&'a Value> {
    let api_name = string_field(api, "api_name");
    let api_version = string_field(api, "api_version");
    items.iter().find(|item| {
        string_field(item, "api_name") == api_name
            && string_field(item, "api_version") == api_version
            && string_field(item, "endpoint_method")
                .is_some_and(|actual| actual.eq_ignore_ascii_case(method))
            && (string_field(item, "client_uri") == Some(routing_uri)
                || string_field(item, "endpoint_uri") == Some(routing_uri))
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn builds_api_name_version_keys() {
        assert_eq!(api_name_version("demo", "v1", true), "/demo/v1");
        assert_eq!(api_name_version("demo", "v1", false), "demo/v1");
    }

    #[test]
    fn coerces_string_lists() {
        let value = json!({ "groups": ["admin", 1, "ops"] });
        assert_eq!(string_list_field(&value, "groups"), vec!["admin", "ops"]);
    }
}
