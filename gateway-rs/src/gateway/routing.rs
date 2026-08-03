use serde_json::Value;

use crate::storage::models::{PolicyDocuments, string_field, string_list_field};

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct Upstream {
    pub url: String,
    pub key: String,
    pub servers: Vec<String>,
    pub cache_value: Option<Value>,
}

pub fn select_upstream(
    documents: &mut PolicyDocuments,
    api: &Value,
    endpoint: Option<&Value>,
    method: &str,
    endpoint_uri: &str,
    client_key: Option<&str>,
) -> Option<Upstream> {
    if let Some(client_key) = client_key {
        if let Some((server, servers, cache_value)) = select_client_routing(documents, client_key) {
            return Some(Upstream {
                url: server,
                key: format!("client_routing_cache:{client_key}"),
                servers,
                cache_value: Some(cache_value),
            });
        }
    }

    if let Some(endpoint) = endpoint {
        let servers = string_list_field(endpoint, "endpoint_servers");
        if !servers.is_empty() {
            let key = string_field(endpoint, "endpoint_id")
                .map(str::to_owned)
                .unwrap_or_else(|| {
                    format!(
                        "{}:{method}:{endpoint_uri}",
                        string_field(api, "api_id").unwrap_or_default()
                    )
                });
            return Some(Upstream {
                url: select_round_robin(&servers, &key, &mut documents.routings),
                key: format!("endpoint_server_cache:{key}"),
                servers,
                cache_value: None,
            });
        }
    }

    let servers = string_list_field(api, "api_servers");
    if servers.is_empty() {
        return None;
    }
    let key = string_field(api, "api_id").unwrap_or_default();
    Some(Upstream {
        url: select_round_robin(&servers, key, &mut documents.routings),
        key: format!("endpoint_server_cache:{key}"),
        servers,
        cache_value: None,
    })
}

fn select_client_routing(
    documents: &mut PolicyDocuments,
    client_key: &str,
) -> Option<(String, Vec<String>, Value)> {
    let routing = documents
        .routings
        .iter_mut()
        .find(|item| string_field(item, "client_key") == Some(client_key))?;
    let servers = string_list_field(routing, "routing_servers");
    if servers.is_empty() {
        return None;
    }
    let cache_value = routing.clone();
    let index = routing
        .get("server_index")
        .and_then(Value::as_u64)
        .unwrap_or(0) as usize;
    let server = servers[index % servers.len()].clone();
    if let Value::Object(map) = routing {
        map.insert(
            "server_index".to_owned(),
            Value::from(((index + 1) % servers.len()) as u64),
        );
    }
    Some((server, servers, cache_value))
}

fn select_round_robin(servers: &[String], key: &str, state: &mut Vec<Value>) -> String {
    let item = state.iter_mut().find(|item| {
        string_field(item, "cache_kind") == Some("endpoint_server_cache")
            && string_field(item, "cache_key") == Some(key)
    });
    let index = item
        .as_ref()
        .and_then(|item| item.get("server_index"))
        .and_then(Value::as_u64)
        .unwrap_or(0) as usize;
    let server = servers[index % servers.len()].clone();
    let next = ((index + 1) % servers.len()) as u64;

    match item {
        Some(Value::Object(map)) => {
            map.insert("server_index".to_owned(), Value::from(next));
        }
        _ => state.push(serde_json::json!({
            "cache_kind": "endpoint_server_cache",
            "cache_key": key,
            "server_index": next,
        })),
    }

    server
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn client_routing_precedes_endpoint_and_api_servers() {
        let api = json!({ "api_id": "api-1", "api_servers": ["https://api"] });
        let endpoint = json!({ "endpoint_servers": ["https://endpoint"] });
        let mut documents = PolicyDocuments {
            routings: vec![json!({
                "client_key": "client-a",
                "routing_servers": ["https://route-a", "https://route-b"],
                "server_index": 0,
            })],
            ..Default::default()
        };

        let first = select_upstream(
            &mut documents,
            &api,
            Some(&endpoint),
            "GET",
            "/items",
            Some("client-a"),
        )
        .unwrap();
        let second = select_upstream(
            &mut documents,
            &api,
            Some(&endpoint),
            "GET",
            "/items",
            Some("client-a"),
        )
        .unwrap();

        assert_eq!(first.url, "https://route-a");
        assert_eq!(second.url, "https://route-b");
    }
}
