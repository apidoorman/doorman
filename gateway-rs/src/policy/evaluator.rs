use std::net::IpAddr;

use http::{HeaderMap, Method, StatusCode};
use serde_json::Value;

use super::{
    PolicyDecision, PolicyFailure, PolicyStage, auth::verify_request_token,
    bandwidth::enforce_pre_request_limit, credits::evaluate_credits, groups::enforce_group_access,
    ip::enforce_api_ip_policy, rate_limit::enforce_rate_limit, roles::enforce_allowed_roles,
    subscription::enforce_subscription, throttle::enforce_throttle,
};
use crate::{
    config::SharedStorageConfig,
    gateway::{
        resolution::{endpoint_pattern_matches, resolve_rest_path},
        routing::select_upstream,
    },
    storage::{
        cache::WindowCounter,
        models::{
            PolicyDocuments, bool_field, bool_field_default, find_api, find_endpoint, string_field,
            u64_field,
        },
        redis::{bandwidth_key, rate_limit_key, throttle_key},
        runtime::SharedStorage,
    },
};

#[derive(Clone, Debug)]
pub struct PolicyRequest {
    pub method: Method,
    pub path: String,
    pub headers: HeaderMap,
    pub direct_ip: Option<IpAddr>,
    pub now_millis: u64,
    pub content_length: u64,
}

#[derive(Clone, Debug, Default)]
pub struct PolicyRuntime {
    pub rate_counter: WindowCounter,
    pub throttle_counter: WindowCounter,
    pub bandwidth_counter: WindowCounter,
}

pub fn evaluate_rest_policy(
    documents: &mut PolicyDocuments,
    request: &PolicyRequest,
    storage_config: &SharedStorageConfig,
    runtime: &PolicyRuntime,
) -> Result<Option<PolicyDecision>, PolicyFailure> {
    let Some(route) = resolve_rest_path(&request.path, &request.headers) else {
        return Ok(None);
    };
    let Some(api) = find_api(&documents.apis, &route.api_name, &route.api_version).cloned() else {
        return Ok(None);
    };
    if bool_field(&api, "active") == Some(false) {
        return Err(PolicyFailure::new(
            PolicyStage::Resolution,
            StatusCode::FORBIDDEN,
            "GTW012",
            "API is disabled",
        ));
    }
    let settings = documents.settings.first();
    enforce_api_ip_policy(
        &api,
        settings,
        &request.headers,
        request.direct_ip,
        storage_config.trust_x_forwarded_for,
        storage_config.local_host_ip_bypass,
    )?;

    let method = if request.method == Method::HEAD {
        "GET"
    } else {
        request.method.as_str()
    };
    if !endpoint_exists(&documents.endpoints, &api, method, &route.endpoint_uri) {
        return Err(PolicyFailure::new(
            PolicyStage::Resolution,
            StatusCode::NOT_FOUND,
            "GTW003",
            "Endpoint does not exist for the requested API",
        ));
    }
    let endpoint = find_endpoint(&documents.endpoints, &api, method, &route.endpoint_uri).cloned();

    let api_public = bool_field(&api, "api_public").unwrap_or(false);
    let api_auth_required = bool_field(&api, "api_auth_required").unwrap_or(true);
    let mut decision = PolicyDecision {
        route: Some("gateway.rest".to_owned()),
        api_id: string_field(&api, "api_id").map(str::to_owned),
        upstream_path: Some(
            endpoint
                .as_ref()
                .and_then(|item| string_field(item, "endpoint_uri"))
                .unwrap_or(&route.endpoint_uri)
                .to_owned(),
        ),
        allowed_headers: crate::storage::models::string_list_field(&api, "api_allowed_headers"),
        retry_count: u64_field(&api, "api_allowed_retry_count")
            .unwrap_or(0)
            .min(10) as u32,
        request_timeout_ms: api
            .get("api_read_timeout")
            .and_then(Value::as_f64)
            .map(|seconds| (seconds.max(0.001) * 1000.0) as u64)
            .unwrap_or(30_000),
        graphql_max_depth: u64_field(&api, "api_graphql_max_depth").unwrap_or(10),
        authorization_field_swap: string_field(&api, "api_authorization_field_swap")
            .map(str::to_owned),
        is_crud: bool_field_default(&api, "api_is_crud", false),
        crud_collection: string_field(&api, "api_crud_collection")
            .map(str::to_owned)
            .or_else(|| {
                bool_field_default(&api, "api_is_crud", false).then(|| {
                    format!(
                        "crud_data_{}",
                        string_field(&api, "api_id")
                            .unwrap_or("default")
                            .replace('-', "_")
                    )
                })
            }),
        crud_schema: api.get("api_crud_schema").cloned(),
        ..Default::default()
    };

    if !api_public && api_auth_required {
        let claims = verify_request_token(&request.headers, storage_config)?;
        let username = claims.sub.as_deref().unwrap_or_default();
        if is_revoked(&documents.revocations, username, claims.jti.as_deref()) {
            return Err(super::auth::unauthorized("Token has been revoked"));
        }
        let user = documents
            .users
            .iter()
            .find(|item| string_field(item, "username") == Some(username))
            .cloned()
            .ok_or_else(|| {
                PolicyFailure::new(
                    PolicyStage::Authentication,
                    StatusCode::NOT_FOUND,
                    "User not found",
                    "User not found",
                )
            })?;
        if bool_field(&user, "active") == Some(false) {
            return Err(super::auth::unauthorized("User is inactive"));
        }

        enforce_subscription(
            &format!("{}/{}", route.api_name, route.api_version),
            &user,
            &documents.roles,
            &documents.subscriptions,
            false,
        )?;
        enforce_group_access(&api, &user)?;
        enforce_rate_limit(username, &user, &runtime.rate_counter, request.now_millis)?;
        let throttle = enforce_throttle(
            username,
            &user,
            &runtime.throttle_counter,
            request.now_millis,
        )?;
        enforce_allowed_roles(&api, &user)?;
        enforce_pre_request_limit(
            username,
            &user,
            &runtime.bandwidth_counter,
            request.now_millis / 1000,
            request.content_length,
        )?;
        let credit = evaluate_credits(
            &api,
            Some(username),
            &documents.credit_defs,
            &documents.user_credits,
        )?;
        decision.username = Some(username.to_owned());
        decision.throttle_delay_ms = throttle.delay_ms;
        decision.credit_required = credit.required;
        decision.credit_group = string_field(&api, "api_credit_group").map(str::to_owned);
        decision.credit_header_name = credit.header_name;
        decision.credit_header_value = credit.header_value;
        decision.user_credit_header_value = credit.user_header_value;
    }

    let client_key = request
        .headers
        .get("client-key")
        .and_then(|value| value.to_str().ok())
        .filter(|value| !value.trim().is_empty());
    if let Some(upstream) = select_upstream(
        documents,
        &api,
        endpoint.as_ref(),
        method,
        &route.endpoint_uri,
        client_key,
    ) {
        decision.upstream = Some(upstream.url);
        decision.routing_key = Some(upstream.key);
        decision.routing_servers = upstream.servers;
        decision.routing_cache_value = upstream.cache_value;
    }

    Ok(Some(decision))
}

pub async fn evaluate_shared_effects(
    documents: &PolicyDocuments,
    request: &PolicyRequest,
    decision: &mut PolicyDecision,
    storage: &SharedStorage,
    mutate: bool,
) -> Result<(), PolicyFailure> {
    if let Some(username) = decision.username.as_deref() {
        let user = documents
            .users
            .iter()
            .find(|item| string_field(item, "username") == Some(username))
            .ok_or_else(|| {
                PolicyFailure::new(
                    PolicyStage::Authentication,
                    StatusCode::NOT_FOUND,
                    "User not found",
                    "User not found",
                )
            })?;

        let rate_enabled = bool_field_default(user, "rate_limit_enabled", false)
            || user.get("rate_limit_duration").is_some();
        if rate_enabled {
            let limit = u64_field(user, "rate_limit_duration").unwrap_or(60);
            let window = super::rate_limit::duration_to_seconds(
                string_field(user, "rate_limit_duration_type").unwrap_or("minute"),
            )
            .max(1);
            let key = rate_limit_key(username, request.now_millis / (window * 1000));
            let count = shared_counter(storage, &key, window, mutate).await?;
            if count > limit {
                return Err(PolicyFailure::new(
                    PolicyStage::RateLimit,
                    StatusCode::TOO_MANY_REQUESTS,
                    "Rate limit exceeded",
                    "Rate limit exceeded",
                ));
            }
        }

        let throttle_enabled = bool_field_default(user, "throttle_enabled", false)
            || user.get("throttle_duration").is_some()
            || user.get("throttle_queue_limit").is_some();
        if throttle_enabled {
            let limit = u64_field(user, "throttle_duration").unwrap_or(10);
            let window = super::rate_limit::duration_to_seconds(
                string_field(user, "throttle_duration_type").unwrap_or("second"),
            )
            .max(1);
            let key = throttle_key(username, request.now_millis / (window * 1000));
            let count = shared_counter(storage, &key, window, mutate).await?;
            let queue_limit = u64_field(user, "throttle_queue_limit").unwrap_or(10);
            let excess = count.saturating_sub(limit);
            if queue_limit > 0 && (count > queue_limit || excess > queue_limit) {
                return Err(PolicyFailure::new(
                    PolicyStage::Throttle,
                    StatusCode::TOO_MANY_REQUESTS,
                    "Throttle queue limit exceeded",
                    "Throttle queue limit exceeded",
                ));
            }
            if count > limit {
                let wait = u64_field(user, "throttle_wait_duration")
                    .unwrap_or(1)
                    .max(1);
                let wait_seconds = super::rate_limit::duration_to_seconds(
                    string_field(user, "throttle_wait_duration_type").unwrap_or("second"),
                );
                decision.throttle_delay_ms = Some(wait * wait_seconds * 1000 * excess.max(1));
            }
        }

        if bool_field(user, "bandwidth_limit_enabled") != Some(false) {
            if let Some(limit) = u64_field(user, "bandwidth_limit_bytes").filter(|limit| *limit > 0)
            {
                let window = super::rate_limit::duration_to_seconds(
                    string_field(user, "bandwidth_limit_window").unwrap_or("day"),
                )
                .max(1);
                let now_seconds = request.now_millis / 1000;
                let bucket = (now_seconds / window) * window;
                let key = bandwidth_key(username, window, bucket);
                let total = storage
                    .current_counter(&key)
                    .await
                    .map_err(storage_failure)?
                    .saturating_add(request.content_length);
                decision.bandwidth_key = Some(key);
                decision.bandwidth_ttl_seconds = Some(window);
                if total > limit {
                    return Err(PolicyFailure::new(
                        PolicyStage::Bandwidth,
                        StatusCode::TOO_MANY_REQUESTS,
                        "Bandwidth limit exceeded",
                        "Bandwidth limit exceeded",
                    ));
                }
            }
        }

        if mutate && decision.credit_required {
            let group = decision.credit_group.as_deref().unwrap_or_default();
            if group.is_empty()
                || !storage
                    .deduct_credit(username, group)
                    .await
                    .map_err(storage_failure)?
            {
                return Err(PolicyFailure::new(
                    PolicyStage::Credits,
                    StatusCode::UNAUTHORIZED,
                    "GTW008",
                    "User does not have any credits",
                ));
            }
        }
    }

    if let (Some(key), false) = (
        decision.routing_key.as_deref(),
        decision.routing_servers.is_empty(),
    ) {
        tracing::warn!(routing_key = key, "routing intent has no servers");
    } else if let Some(key) = decision.routing_key.as_deref() {
        let index = if let Some(initial) = decision.routing_cache_value.as_ref() {
            if mutate {
                storage
                    .next_client_routing_index(key, initial, decision.routing_servers.len())
                    .await
            } else {
                storage.current_client_routing_index(key, initial).await
            }
        } else if mutate {
            storage
                .next_routing_index(key, decision.routing_servers.len())
                .await
        } else {
            storage.current_routing_index(key).await
        }
        .map_err(storage_failure)?;
        decision.upstream = decision
            .routing_servers
            .get(index % decision.routing_servers.len())
            .cloned();
    }

    Ok(())
}

async fn shared_counter(
    storage: &SharedStorage,
    key: &str,
    ttl_seconds: u64,
    mutate: bool,
) -> Result<u64, PolicyFailure> {
    if mutate {
        storage
            .increment_window(key, ttl_seconds)
            .await
            .map_err(storage_failure)
    } else {
        storage
            .current_counter(key)
            .await
            .map(|count| count.saturating_add(1))
            .map_err(storage_failure)
    }
}

fn storage_failure(error: crate::storage::runtime::StorageError) -> PolicyFailure {
    tracing::error!(error = %error, "shared policy storage operation failed");
    PolicyFailure::new(
        PolicyStage::Resolution,
        StatusCode::SERVICE_UNAVAILABLE,
        "GTW006",
        "Gateway state store unavailable",
    )
}

fn endpoint_exists(endpoints: &[Value], api: &Value, method: &str, endpoint_uri: &str) -> bool {
    endpoints.iter().any(|endpoint| {
        let same_api = string_field(endpoint, "api_name") == string_field(api, "api_name")
            && string_field(endpoint, "api_version") == string_field(api, "api_version");
        let same_method = string_field(endpoint, "endpoint_method")
            .is_some_and(|actual| actual.eq_ignore_ascii_case(method));
        let uri =
            string_field(endpoint, "client_uri").or_else(|| string_field(endpoint, "endpoint_uri"));
        same_api
            && same_method
            && uri.is_some_and(|pattern| endpoint_pattern_matches(pattern, endpoint_uri))
    })
}

fn is_revoked(revocations: &[Value], username: &str, jti: Option<&str>) -> bool {
    revocations
        .iter()
        .any(|revocation| match string_field(revocation, "type") {
            Some("revoke_all") => {
                string_field(revocation, "username") == Some(username)
                    && bool_field(revocation, "revoke_all").unwrap_or(true)
            }
            Some("jti") => {
                string_field(revocation, "username") == Some(username)
                    && jti.is_some_and(|jti| string_field(revocation, "jti") == Some(jti))
            }
            _ => false,
        })
}

#[cfg(test)]
mod tests {
    use super::*;
    use http::HeaderValue;
    use serde_json::json;

    #[test]
    fn returns_endpoint_not_found_for_missing_endpoint() {
        let mut documents = PolicyDocuments {
            apis: vec![json!({
                "api_id": "api-1",
                "api_name": "demo",
                "api_version": "v1",
                "api_public": true,
            })],
            endpoints: vec![json!({
                "api_name": "demo",
                "api_version": "v1",
                "endpoint_method": "GET",
                "client_uri": "/known",
            })],
            ..Default::default()
        };
        let request = PolicyRequest {
            method: Method::GET,
            path: "/api/rest/demo/v1/missing".to_owned(),
            headers: HeaderMap::new(),
            direct_ip: None,
            now_millis: 0,
            content_length: 0,
        };
        let failure = evaluate_rest_policy(
            &mut documents,
            &request,
            &SharedStorageConfig::default(),
            &PolicyRuntime::default(),
        )
        .unwrap_err();
        assert_eq!(failure.error_code, "GTW003");
    }

    #[test]
    fn records_client_key_upstream_selection() {
        let mut headers = HeaderMap::new();
        headers.insert("client-key", HeaderValue::from_static("client-a"));
        let mut documents = PolicyDocuments {
            apis: vec![json!({
                "api_id": "api-1",
                "api_name": "demo",
                "api_version": "v1",
                "api_public": true,
            })],
            endpoints: vec![json!({
                "api_name": "demo",
                "api_version": "v1",
                "endpoint_method": "GET",
                "client_uri": "/items",
            })],
            routings: vec![json!({
                "client_key": "client-a",
                "routing_servers": ["http://route-a", "http://route-b"],
                "server_index": 0,
            })],
            ..Default::default()
        };
        let request = PolicyRequest {
            method: Method::GET,
            path: "/api/rest/demo/v1/items".to_owned(),
            headers,
            direct_ip: None,
            now_millis: 0,
            content_length: 0,
        };
        let decision = evaluate_rest_policy(
            &mut documents,
            &request,
            &SharedStorageConfig::default(),
            &PolicyRuntime::default(),
        )
        .unwrap()
        .unwrap();
        assert_eq!(decision.upstream, Some("http://route-a".to_owned()));
    }
}
