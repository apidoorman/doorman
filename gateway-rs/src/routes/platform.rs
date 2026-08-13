use std::{
    collections::HashMap,
    env, fs,
    io::Read,
    net::SocketAddr,
    process::{Command, Stdio},
    sync::OnceLock,
    time::{SystemTime, UNIX_EPOCH},
};

use axum::{
    body::{Body, to_bytes},
    extract::{ConnectInfo, OriginalUri, Request, State},
    response::{IntoResponse, Response},
};
use base64::{Engine as _, engine::general_purpose::STANDARD as BASE64_STANDARD};
use http::{HeaderMap, HeaderValue, Method, StatusCode, header};
use jsonwebtoken::{Algorithm, EncodingKey, Header, encode};
use serde::Serialize;
use serde_json::{Map, Value, json};
use uuid::Uuid;

const PYTHON_OPENAPI_GZIP_BASE64: &str =
    include_str!("../../../parity/openapi/python-openapi.json.gz.b64");
static PYTHON_OPENAPI: OnceLock<Value> = OnceLock::new();

use crate::{
    middleware::{
        body_limit::BodyLimits,
        chaos::{
            CHAOS_ENABLED, CHAOS_ERROR_BUDGET_BURN, CHAOS_ERROR_STATUS, CHAOS_EVENTS_COUNT,
            CHAOS_LATENCY_MS, CHAOS_MONGO_OUTAGE, CHAOS_REDIS_OUTAGE,
        },
        response_compat::MessageEnvelope,
    },
    observability::analytics_aggregator::{AggregatedPoint, EntityCounter, global_analytics},
    platform_contract::{normalize_create_api, normalize_update_api},
    policy::{
        auth::{AuthClaims, verify_request_token},
        ip::enforce_api_ip_policy,
    },
    state::AppState,
    storage::models::strip_mongo_id,
};

#[derive(Serialize)]
struct AccessClaims {
    sub: String,
    role: String,
    jti: String,
    iat: usize,
    exp: usize,
}

#[derive(Clone, Copy)]
struct EntitySpec {
    collection: &'static str,
    key: &'static str,
    permission: &'static str,
    permission_code: &'static str,
    id_field: Option<&'static str>,
    created: &'static str,
    updated: &'static str,
    deleted: &'static str,
    duplicate_code: &'static str,
    not_found_code: &'static str,
}

pub async fn platform_dispatch(
    State(state): State<AppState>,
    OriginalUri(uri): OriginalUri,
    request: Request,
) -> Response {
    let direct_addr = request
        .extensions()
        .get::<ConnectInfo<SocketAddr>>()
        .map(|value| value.0);
    let method = request.method().clone();
    let headers = request.headers().clone();
    let request_id = request_id_from(&headers);
    let query = parse_query(uri.query());
    let path = uri.path().strip_prefix("/platform").unwrap_or(uri.path());
    if let Some(response) = platform_ip_filter(&state, &headers, direct_addr, &request_id).await
    {
        return response;
    }
    let body_limit = BodyLimits::for_path(uri.path(), BodyLimits::from_env().default);
    let body = match to_bytes(request.into_body(), body_limit).await {
        Ok(bytes) => bytes,
        Err(_) => {
            return error(
                StatusCode::PAYLOAD_TOO_LARGE,
                "GTW013",
                "Request body too large",
                &request_id,
            );
        }
    };
    let payload = if body.is_empty() {
        Value::Object(Map::new())
    } else {
        serde_json::from_slice(&body).unwrap_or(Value::Null)
    };

    if path == "/authorization" && method == Method::POST {
        if let Some(response) = auth_ip_rate_limit(
            &state,
            &headers,
            direct_addr,
            "LOGIN_IP_RATE_LIMIT",
            5,
            "LOGIN_IP_RATE_WINDOW",
            300,
            &request_id,
        )
        .await
        {
            return response;
        }
        return login(&state, &headers, payload, &request_id).await;
    }
    if path == "/authorization/register" && method == Method::POST {
        if !env_bool("DOORMAN_ALLOW_PUBLIC_REGISTRATION", false) {
            return error(
                StatusCode::FORBIDDEN,
                "AUTH006",
                "Public registration is disabled",
                &request_id,
            );
        }
        if let Some(response) = auth_ip_rate_limit(
            &state,
            &headers,
            direct_addr,
            "REGISTER_IP_RATE_LIMIT",
            5,
            "REGISTER_IP_RATE_WINDOW",
            3600,
            &request_id,
        )
        .await
        {
            return response;
        }
        return register(&state, payload, &request_id).await;
    }
    if path == "/monitor/liveness" && method == Method::GET {
        return success(StatusCode::OK, json!({"status": "alive"}), &request_id);
    }
    if path == "/monitor/readiness" && method == Method::GET {
        let privileged = match authorize(&state, &headers, path, &request_id).await {
            Ok(claims) => {
                let username = claims.sub.as_deref().unwrap_or_default();
                has_permission(&state, username, "manage_gateway").await
            }
            Err(_) => false,
        };
        return readiness(&state, privileged, &request_id).await;
    }

    let claims = match authorize(&state, &headers, path, &request_id).await {
        Ok(claims) => claims,
        Err(response) => return response,
    };
    let username = claims.sub.clone().unwrap_or_default();

    if path.starts_with("/authorization") {
        return authorization_routes(
            &state,
            &headers,
            path,
            method,
            payload,
            &claims,
            &request_id,
        )
        .await;
    }

    if let Some(response) = dispatch_core_entities(
        &state,
        path,
        &method,
        payload.clone(),
        &query,
        &username,
        &request_id,
    )
    .await
    {
        return response;
    }

    match (method.clone(), path) {
        (Method::GET, "/openapi.json") => {
            if !has_permission(&state, &username, "manage_apis").await {
                error(
                    StatusCode::FORBIDDEN,
                    "API008",
                    "You do not have permission to view API documentation",
                    &request_id,
                )
            } else {
                platform_openapi(&request_id)
            }
        }
        (Method::GET, "/docs") | (Method::GET, "/redoc") => {
            if !has_permission(&state, &username, "manage_apis").await {
                error(
                    StatusCode::FORBIDDEN,
                    "API008",
                    "You do not have permission to view API documentation",
                    &request_id,
                )
            } else {
                platform_docs(path, &request_id)
            }
        }
        (Method::POST, "/memory/dump") => {
            memory_dump(&state, payload, &username, &request_id).await
        }
        (Method::POST, "/memory/restore") => {
            memory_restore(&state, payload, &username, &request_id).await
        }
        (Method::GET, "/dashboard") => {
            if !has_permission(&state, &username, "view_analytics").await {
                analytics_denied(&request_id)
            } else {
                dashboard(&state, &request_id).await
            }
        },
        (Method::GET, "/monitor/metrics") => {
            if !has_permission(&state, &username, "manage_gateway").await {
                error(
                    StatusCode::FORBIDDEN,
                    "MON001",
                    "You do not have permission to view monitor metrics",
                    &request_id,
                )
            } else {
                monitor_metrics(&state, &request_id).await
            }
        }
        (Method::GET, "/monitor/report") => {
            if !has_permission(&state, &username, "manage_gateway").await {
                error(
                    StatusCode::FORBIDDEN,
                    "MON002",
                    "You do not have permission to generate reports",
                    &request_id,
                )
            } else {
                monitor_report(&state, &request_id).await
            }
        }
        (Method::GET, "/analytics/overview") => {
            analytics_overview(&state, &username, &query, &request_id).await
        }
        (Method::GET, "/analytics/timeseries") => {
            if !has_permission(&state, &username, "view_analytics").await {
                analytics_denied(&request_id)
            } else {
                analytics_timeseries(&query, &request_id)
            }
        }
        (Method::GET, "/analytics/top-apis") => {
            if !has_permission(&state, &username, "view_analytics").await {
                analytics_denied(&request_id)
            } else {
                analytics_top("api", &query, &request_id)
            }
        }
        (Method::GET, "/analytics/top-users") => {
            if !has_permission(&state, &username, "view_analytics").await {
                analytics_denied(&request_id)
            } else {
                analytics_top("user", &query, &request_id)
            }
        }
        (Method::GET, "/analytics/top-endpoints") => {
            if !has_permission(&state, &username, "view_analytics").await {
                analytics_denied(&request_id)
            } else {
                analytics_top("endpoint", &query, &request_id)
            }
        }
        (Method::GET, detail) if detail.starts_with("/analytics/api/") => {
            analytics_detail(
                &state,
                &username,
                "api",
                detail.trim_start_matches("/analytics/api/"),
                &query,
                &request_id,
            )
            .await
        }
        (Method::GET, detail) if detail.starts_with("/analytics/user/") => {
            analytics_detail(
                &state,
                &username,
                "user",
                detail.trim_start_matches("/analytics/user/"),
                &query,
                &request_id,
            )
            .await
        }
        (Method::GET, "/security/settings") => {
            if !has_permission(&state, &username, "manage_security").await {
                error(
                    StatusCode::FORBIDDEN,
                    "SEC001",
                    "You do not have permission to view security settings",
                    &request_id,
                )
            } else {
                get_security_settings(&state, &request_id).await
            }
        }
        (Method::PUT, "/security/settings") => {
            if !has_permission(&state, &username, "manage_security").await {
                error(
                    StatusCode::FORBIDDEN,
                    "SEC002",
                    "You do not have permission to update security settings",
                    &request_id,
                )
            } else {
                upsert_singleton(&state, "settings", payload, &request_id).await
            }
        }
        (Method::POST, "/security/restart") => {
            if !has_permission(&state, &username, "manage_security").await {
                error(
                    StatusCode::FORBIDDEN,
                    "SEC003",
                    "You do not have permission to restart the gateway",
                    &request_id,
                )
            } else {
                match schedule_restart() {
                    Ok(()) => message(StatusCode::ACCEPTED, "Restart scheduled", &request_id),
                    Err(("SEC004", message_text)) => {
                        error(StatusCode::CONFLICT, "SEC004", message_text, &request_id)
                    }
                    Err((code, message_text)) => error(
                        StatusCode::INTERNAL_SERVER_ERROR,
                        code,
                        message_text,
                        &request_id,
                    ),
                }
            }
        }
        (Method::GET, "/config/export/all") => {
            config_export(&state, &username, None, &query, &request_id).await
        }
        (Method::GET, "/config/export/apis") => {
            config_export(&state, &username, Some("apis"), &query, &request_id).await
        }
        (Method::GET, "/config/export/roles") => {
            config_export(&state, &username, Some("roles"), &query, &request_id).await
        }
        (Method::GET, "/config/export/groups") => {
            config_export(&state, &username, Some("groups"), &query, &request_id).await
        }
        (Method::GET, "/config/export/routings") => {
            config_export(&state, &username, Some("routings"), &query, &request_id).await
        }
        (Method::GET, "/config/export/endpoints") => {
            config_export(&state, &username, Some("endpoints"), &query, &request_id).await
        }
        (Method::POST, "/config/import") => {
            config_import(&state, &username, payload, &request_id).await
        }
        (Method::POST, "/config/rollback") => config_rollback(&state, &username, &request_id).await,
        (Method::GET, "/config/current") => {
            if !has_permission(&state, &username, "manage_gateway").await {
                http_detail(
                    StatusCode::FORBIDDEN,
                    "Insufficient permissions: manage_gateway required",
                    &request_id,
                )
            } else {
                config_current(&state, &request_id)
            }
        }
        (Method::GET, "/config/reloadable-keys") => {
            if !has_permission(&state, &username, "manage_gateway").await {
                http_detail(
                    StatusCode::FORBIDDEN,
                    "Insufficient permissions: manage_gateway required",
                    &request_id,
                )
            } else {
                success(
                    StatusCode::OK,
                    json!({
                        "reloadable_keys": reloadable_keys(),
                        "total": 22,
                        "notes": [
                            "Environment variables always override config file values",
                            "Changes take effect immediately after reload",
                            "Reload via: kill -HUP $(cat doorman.pid)",
                            "Or use: POST /config/reload"
                        ]
                    }),
                    &request_id,
                )
            }
        },
        (Method::POST, "/config/reload") => {
            if !has_permission(&state, &username, "manage_gateway").await {
                http_detail(
                    StatusCode::FORBIDDEN,
                    "Insufficient permissions: manage_gateway required",
                    &request_id,
                )
            } else {
                state.hot_reload.reload();
                success(
                    StatusCode::OK,
                    json!({
                        "message": "Configuration reloaded successfully",
                        "config": state.hot_reload.dump()
                    }),
                    &request_id,
                )
            }
        }
        (Method::POST, "/demo/seed") => demo_seed(&state, &username, &request_id).await,
        (Method::POST, "/tools/cors/check") => {
            if !has_permission(&state, &username, "manage_security").await {
                error(
                    StatusCode::FORBIDDEN,
                    "TLS001",
                    "You do not have permission to use tools",
                    &request_id,
                )
            } else {
                cors_check(payload, &request_id)
            }
        }
        (Method::GET, "/tools/grpc/check") => {
            if !has_permission(&state, &username, "manage_security").await {
                error(
                    StatusCode::FORBIDDEN,
                    "TLS001",
                    "You do not have permission to use tools",
                    &request_id,
                )
            } else {
                let reflection_enabled = env_bool("DOORMAN_ENABLE_GRPC_REFLECTION", false);
                let notes = if reflection_enabled {
                    Vec::<&str>::new()
                } else {
                    vec![
                        "Reflection is disabled by default. Enable with DOORMAN_ENABLE_GRPC_REFLECTION=true",
                    ]
                };
                success(
                    StatusCode::OK,
                    json!({
                        "available": {
                            "grpc": true,
                            "grpc_tools_protoc": true
                        },
                        "reflection_enabled": reflection_enabled,
                        "notes": notes,
                        "details": {}
                    }),
                    &request_id,
                )
            }
        }
        (Method::POST, "/tools/chaos/toggle") => {
            if !has_permission(&state, &username, "manage_gateway").await {
                error(
                    StatusCode::FORBIDDEN,
                    "TLS001",
                    "You do not have permission to use tools",
                    &request_id,
                )
            } else if let Some(backend) = payload.get("backend").and_then(Value::as_str) {
                let backend = backend.trim().to_ascii_lowercase();
                let target = match backend.as_str() {
                    "redis" => &CHAOS_REDIS_OUTAGE,
                    "mongo" => &CHAOS_MONGO_OUTAGE,
                    _ => {
                        return error(
                            StatusCode::BAD_REQUEST,
                            "TLS002",
                            "backend must be redis or mongo",
                            &request_id,
                        );
                    }
                };
                let Some(enabled) = payload.get("enabled").and_then(Value::as_bool) else {
                    return validation_errors(
                        vec![json!({
                            "loc": ["body", "enabled"],
                            "msg": "field required",
                            "type": "value_error.missing"
                        })],
                        &request_id,
                    );
                };
                let duration_ms = payload
                    .get("duration_ms")
                    .and_then(Value::as_u64)
                    .unwrap_or(0);
                if duration_ms > 0 {
                    target.store(true, std::sync::atomic::Ordering::Relaxed);
                    tokio::spawn(async move {
                        tokio::time::sleep(std::time::Duration::from_millis(duration_ms)).await;
                        target.store(false, std::sync::atomic::Ordering::Relaxed);
                    });
                } else {
                    target.store(enabled, std::sync::atomic::Ordering::Relaxed);
                }
                success(
                    StatusCode::OK,
                    json!({
                        "backend": backend,
                        "enabled": target.load(std::sync::atomic::Ordering::Relaxed)
                    }),
                    &request_id,
                )
            } else {
                // Retain the additive v2 latency/error injection extension.
                let enabled = payload
                    .get("enabled")
                    .and_then(Value::as_bool)
                    .unwrap_or(false);
                let latency = payload
                    .get("latency_ms")
                    .and_then(Value::as_u64)
                    .unwrap_or(0);
                let error_status = payload
                    .get("error_status")
                    .and_then(Value::as_u64)
                    .unwrap_or(0) as u32;
                CHAOS_ENABLED.store(enabled, std::sync::atomic::Ordering::Relaxed);
                CHAOS_LATENCY_MS.store(latency, std::sync::atomic::Ordering::Relaxed);
                CHAOS_ERROR_STATUS.store(error_status, std::sync::atomic::Ordering::Relaxed);
                success(
                    StatusCode::OK,
                    json!({
                        "enabled": enabled,
                        "latency_ms": latency,
                        "error_status": error_status
                    }),
                    &request_id,
                )
            }
        }
        (Method::GET, "/tools/chaos/stats") => {
            if !has_permission(&state, &username, "manage_gateway").await {
                error(
                    StatusCode::FORBIDDEN,
                    "TLS001",
                    "You do not have permission to use tools",
                    &request_id,
                )
            } else {
                success(
                    StatusCode::OK,
                    json!({
                        "redis_outage": CHAOS_REDIS_OUTAGE.load(std::sync::atomic::Ordering::Relaxed),
                        "mongo_outage": CHAOS_MONGO_OUTAGE.load(std::sync::atomic::Ordering::Relaxed),
                        "error_budget_burn": CHAOS_ERROR_BUDGET_BURN.load(std::sync::atomic::Ordering::Relaxed),
                        "enabled": CHAOS_ENABLED.load(std::sync::atomic::Ordering::Relaxed),
                        "latency_ms": CHAOS_LATENCY_MS.load(std::sync::atomic::Ordering::Relaxed),
                        "error_status": CHAOS_ERROR_STATUS.load(std::sync::atomic::Ordering::Relaxed),
                        "events": CHAOS_EVENTS_COUNT.load(std::sync::atomic::Ordering::Relaxed)
                    }),
                    &request_id,
                )
            }
        }
        (Method::POST, "/tools/rate-limit-simulator") => {
            if !has_permission(&state, &username, "manage_rate_limits").await {
                return error(
                    StatusCode::FORBIDDEN,
                    "RATE001",
                    "You do not have permission to use the rate limit simulator",
                    &request_id,
                );
            }
            let max_requests = payload
                .get("max_requests")
                .and_then(Value::as_u64)
                .unwrap_or(100);
            let duration_seconds = payload
                .get("duration_seconds")
                .and_then(Value::as_u64)
                .unwrap_or(60);
            let simulated_requests = payload
                .get("simulated_requests")
                .and_then(Value::as_u64)
                .unwrap_or(120);

            let allowed = simulated_requests.min(max_requests);
            let blocked = simulated_requests.saturating_sub(max_requests);

            success(
                StatusCode::OK,
                json!({
                    "max_requests": max_requests,
                    "duration_seconds": duration_seconds,
                    "simulated_requests": simulated_requests,
                    "allowed_requests": allowed,
                    "blocked_requests": blocked,
                    "would_exceed": blocked > 0
                }),
                &request_id,
            )
        }
        _ => {
            if path.starts_with("/subscription") {
                subscription_routes(&state, path, &method, payload, &username, &request_id).await
            } else if path.starts_with("/credit") {
                credit_routes(&state, path, &method, payload, &username, &request_id).await
            } else if path.starts_with("/vault") {
                vault_routes(&state, path, &method, payload, &username, &request_id).await
            } else if path.starts_with("/quota") {
                quota_routes(&state, path, &method, &username, &request_id).await
            } else if path.starts_with("/proto") {
                proto_routes(
                    &state,
                    path,
                    &method,
                    &headers,
                    &body,
                    &username,
                    &request_id,
                )
                .await
            } else if path.starts_with("/logging") {
                logging_routes(&state, path, &method, &username, &request_id).await
            } else if path.starts_with("/openapi") || path.starts_with("/wsdl") {
                discovery_parse(
                    &state,
                    path,
                    &method,
                    payload,
                    &body,
                    &username,
                    &request_id,
                )
                .await
            } else {
                error(
                    StatusCode::NOT_FOUND,
                    "GTW003",
                    "Platform route does not exist",
                    &request_id,
                )
            }
        }
    }
}

async fn dispatch_core_entities(
    state: &AppState,
    path: &str,
    method: &Method,
    payload: Value,
    query: &HashMap<String, String>,
    username: &str,
    request_id: &str,
) -> Option<Response> {
    if path == "/tiers" || path == "/tiers/" || path.starts_with("/tiers/") {
        let suffix = path.trim_start_matches("/tiers").trim_matches('/');
        let basic = suffix.is_empty()
            || (!suffix.contains('/')
                && !matches!(
                    suffix,
                    "upgrade" | "downgrade" | "temporary-upgrade" | "compare" | "assignments"
                ));
        if basic {
            let spec = EntitySpec {
                collection: "tiers",
                key: "tier_id",
                permission: "manage_tiers",
                permission_code: "TIER001",
                id_field: Some("tier_id"),
                created: "Tier created successfully",
                updated: "Tier updated successfully",
                deleted: "Tier deleted successfully",
                duplicate_code: "TIER001",
                not_found_code: "TIER404",
            };
            return Some(
                entity_routes(
                    state, "/tiers", spec, path, method, payload, query, username, request_id,
                )
                .await,
            );
        }
        return Some(
            tier_management_routes(state, path, method, payload, username, request_id).await,
        );
    }
    if path == "/rate-limits" || path == "/rate-limits/" || path.starts_with("/rate-limits/") {
        let suffix = path.trim_start_matches("/rate-limits").trim_matches('/');
        let basic =
            suffix.is_empty() || (!suffix.contains('/') && !matches!(suffix, "search" | "status"));
        if basic {
            let spec = EntitySpec {
                collection: "rate_limit_rules",
                key: "rule_id",
                permission: "manage_rate_limits",
                permission_code: "RATE001",
                id_field: Some("rule_id"),
                created: "Rate limit rule created successfully",
                updated: "Rate limit rule updated successfully",
                deleted: "Rate limit rule deleted successfully",
                duplicate_code: "RATE001",
                not_found_code: "RATE404",
            };
            return Some(
                entity_routes(
                    state,
                    "/rate-limits",
                    spec,
                    path,
                    method,
                    payload,
                    query,
                    username,
                    request_id,
                )
                .await,
            );
        }
        return Some(
            rate_limit_management_routes(state, path, method, payload, query, username, request_id)
                .await,
        );
    }

    let specs = [
        (
            "/group",
            EntitySpec {
                collection: "groups",
                key: "group_name",
                permission: "manage_groups",
                permission_code: "GRP008",
                id_field: None,
                created: "Group created successfully",
                updated: "Group updated successfully",
                deleted: "Group deleted successfully",
                duplicate_code: "GRP001",
                not_found_code: "GRP002",
            },
        ),
        (
            "/role",
            EntitySpec {
                collection: "roles",
                key: "role_name",
                permission: "manage_roles",
                permission_code: "ROLE009",
                id_field: None,
                created: "Role created successfully",
                updated: "Role updated successfully",
                deleted: "Role deleted successfully",
                duplicate_code: "ROL001",
                not_found_code: "ROL002",
            },
        ),
        (
            "/routing",
            EntitySpec {
                collection: "routings",
                key: "client_key",
                permission: "manage_routings",
                permission_code: "RTG012",
                id_field: None,
                created: "Routing created successfully",
                updated: "Routing updated successfully",
                deleted: "Routing deleted successfully",
                duplicate_code: "RTE001",
                not_found_code: "RTE002",
            },
        ),
    ];
    for (prefix, spec) in specs {
        if path == prefix || path == format!("{prefix}/") || path.starts_with(&format!("{prefix}/"))
        {
            return Some(
                entity_routes(
                    state, prefix, spec, path, method, payload, query, username, request_id,
                )
                .await,
            );
        }
    }
    if path == "/api" || path.starts_with("/api/") || path == "/apis" || path.starts_with("/apis/")
    {
        return Some(
            api_routes(
                state,
                path.trim_start_matches('s'),
                method,
                payload,
                query,
                username,
                request_id,
            )
            .await,
        );
    }
    if path == "/user"
        || path.starts_with("/user/")
        || path == "/users"
        || path.starts_with("/users/")
    {
        return Some(user_routes(state, path, method, payload, query, username, request_id).await);
    }
    if path == "/endpoint"
        || path.starts_with("/endpoint/")
        || path == "/endpoints"
        || path.starts_with("/endpoints/")
    {
        return Some(
            endpoint_routes(state, path, method, payload, query, username, request_id).await,
        );
    }
    None
}

async fn tier_management_routes(
    state: &AppState,
    path: &str,
    method: &Method,
    payload: Value,
    username: &str,
    request_id: &str,
) -> Response {
    if !has_permission(state, username, "manage_tiers").await {
        return error(
            StatusCode::FORBIDDEN,
            "TIER001",
            "You do not have permission to manage tiers",
            request_id,
        );
    }
    let Some(storage) = &state.storage else {
        return unexpected(request_id);
    };
    let suffix = path.trim_start_matches("/tiers/");
    if suffix == "assignments" && method == Method::GET {
        let items = storage
            .find_many("user_tier_assignments", &json!({}))
            .await
            .unwrap_or_default()
            .into_iter()
            .map(strip_internal)
            .collect::<Vec<_>>();
        return success(StatusCode::OK, json!({"response": items}), request_id);
    }
    if suffix == "assignments" && method == Method::POST {
        let user_id = payload
            .get("user_id")
            .and_then(Value::as_str)
            .unwrap_or("")
            .to_owned();
        let tier_id = payload
            .get("tier_id")
            .and_then(Value::as_str)
            .unwrap_or("")
            .to_owned();
        if user_id.is_empty() || tier_id.is_empty() {
            return error(
                StatusCode::BAD_REQUEST,
                "TIER002",
                "user_id and tier_id are required",
                request_id,
            );
        }
        if storage
            .find_one("tiers", &json!({"tier_id": &tier_id}))
            .await
            .ok()
            .flatten()
            .is_none()
        {
            return error(
                StatusCode::NOT_FOUND,
                "TIER404",
                "Tier not found",
                request_id,
            );
        }
        let existing = storage
            .find_one("user_tier_assignments", &json!({"user_id": &user_id}))
            .await
            .ok()
            .flatten();
        let mut assignment = payload;
        assignment["assigned_at"] = json!(unix_seconds().to_string());
        let result = if existing.is_some() {
            storage
                .update_one(
                    "user_tier_assignments",
                    &json!({"user_id": &user_id}),
                    &assignment,
                )
                .await
                .map(|_| ())
        } else {
            storage
                .insert_one("user_tier_assignments", assignment)
                .await
                .map(|_| ())
        };
        return match result {
            Ok(()) => message(
                StatusCode::OK,
                "User assigned to tier successfully",
                request_id,
            ),
            Err(_) => unexpected(request_id),
        };
    }
    if let Some(rest) = suffix.strip_prefix("assignments/") {
        let user_id = rest.trim_end_matches("/tier");
        if method == Method::DELETE {
            return match storage
                .delete_one("user_tier_assignments", &json!({"user_id": user_id}))
                .await
            {
                Ok(true) => message(StatusCode::OK, "User tier assignment removed", request_id),
                _ => error(
                    StatusCode::NOT_FOUND,
                    "TIER404",
                    "Assignment not found",
                    request_id,
                ),
            };
        }
        if method == Method::GET {
            let assignment = storage
                .find_one("user_tier_assignments", &json!({"user_id": user_id}))
                .await
                .ok()
                .flatten();
            if rest.ends_with("/tier") {
                let Some(assignment) = assignment else {
                    return error(
                        StatusCode::NOT_FOUND,
                        "TIER404",
                        "Assignment not found",
                        request_id,
                    );
                };
                let Some(tier_id) = assignment.get("tier_id") else {
                    return error(
                        StatusCode::NOT_FOUND,
                        "TIER404",
                        "Tier not found",
                        request_id,
                    );
                };
                return match storage
                    .find_one("tiers", &json!({"tier_id": tier_id}))
                    .await
                {
                    Ok(Some(tier)) => success(StatusCode::OK, strip_internal(tier), request_id),
                    _ => error(
                        StatusCode::NOT_FOUND,
                        "TIER404",
                        "Tier not found",
                        request_id,
                    ),
                };
            }
            return match assignment {
                Some(value) => success(StatusCode::OK, strip_internal(value), request_id),
                None => error(
                    StatusCode::NOT_FOUND,
                    "TIER404",
                    "Assignment not found",
                    request_id,
                ),
            };
        }
    }
    if suffix.ends_with("/users") && method == Method::GET {
        let tier_id = suffix.trim_end_matches("/users");
        let users = storage
            .find_many("user_tier_assignments", &json!({"tier_id": tier_id}))
            .await
            .unwrap_or_default()
            .into_iter()
            .map(strip_internal)
            .collect::<Vec<_>>();
        return success(
            StatusCode::OK,
            json!({"users": users, "count": users.len()}),
            request_id,
        );
    }
    if (suffix.ends_with("/statistics") || suffix == "statistics/all") && method == Method::GET {
        let assignments = storage
            .find_many("user_tier_assignments", &json!({}))
            .await
            .unwrap_or_default();
        return success(
            StatusCode::OK,
            json!({"assignments": assignments.len()}),
            request_id,
        );
    }
    if suffix == "compare" && method == Method::POST {
        let ids = payload
            .get("tier_ids")
            .or_else(|| payload.get("tiers"))
            .and_then(Value::as_array)
            .cloned()
            .unwrap_or_default();
        let tiers = storage
            .find_many("tiers", &json!({}))
            .await
            .unwrap_or_default()
            .into_iter()
            .filter(|tier| ids.contains(tier.get("tier_id").unwrap_or(&Value::Null)))
            .map(strip_internal)
            .collect::<Vec<_>>();
        return success(StatusCode::OK, json!({"tiers": tiers}), request_id);
    }
    let action_tier = match suffix {
        "upgrade" | "downgrade" => payload.get("new_tier_id"),
        "temporary-upgrade" => payload.get("temp_tier_id"),
        "trial/start" => payload.get("tier_id"),
        _ => None,
    };
    if method == Method::POST && (action_tier.is_some() || suffix == "payment/failure") {
        let user_id = payload.get("user_id").and_then(Value::as_str).unwrap_or("");
        if user_id.is_empty() {
            return error(
                StatusCode::BAD_REQUEST,
                "TIER002",
                "user_id is required",
                request_id,
            );
        }
        let mut updates = json!({"updated_at": unix_seconds().to_string()});
        if let Some(tier_id) = action_tier {
            updates["tier_id"] = tier_id.clone();
        }
        if suffix == "temporary-upgrade" {
            updates["temporary"] = json!(true);
            updates["duration_days"] = payload.get("duration_days").cloned().unwrap_or(json!(0));
        }
        if suffix == "trial/start" {
            updates["trial"] = json!(true);
            updates["trial_days"] = payload.get("days").cloned().unwrap_or(json!(14));
        }
        if suffix == "payment/failure" {
            updates["payment_status"] = json!("failed");
            updates["payment_failure_reason"] =
                payload.get("reason").cloned().unwrap_or(Value::Null);
        }
        let existing = storage
            .find_one("user_tier_assignments", &json!({"user_id": user_id}))
            .await
            .ok()
            .flatten();
        let result = if existing.is_some() {
            storage
                .update_one(
                    "user_tier_assignments",
                    &json!({"user_id": user_id}),
                    &updates,
                )
                .await
                .map(|_| ())
        } else {
            updates["user_id"] = json!(user_id);
            storage
                .insert_one("user_tier_assignments", updates)
                .await
                .map(|_| ())
        };
        return match result {
            Ok(()) => message(
                StatusCode::OK,
                "Tier assignment updated successfully",
                request_id,
            ),
            Err(_) => unexpected(request_id),
        };
    }
    error(
        StatusCode::NOT_FOUND,
        "GTW003",
        "Platform route does not exist",
        request_id,
    )
}

async fn rate_limit_management_routes(
    state: &AppState,
    path: &str,
    method: &Method,
    payload: Value,
    query: &HashMap<String, String>,
    username: &str,
    request_id: &str,
) -> Response {
    if !has_permission(state, username, "manage_rate_limits").await {
        return error(
            StatusCode::FORBIDDEN,
            "RATE001",
            "You do not have permission to manage rate limits",
            request_id,
        );
    }
    let Some(storage) = &state.storage else {
        return unexpected(request_id);
    };
    let suffix = path.trim_start_matches("/rate-limits/");
    if suffix == "search" && method == Method::GET {
        let term = query
            .get("q")
            .map(|value| value.to_ascii_lowercase())
            .unwrap_or_default();
        let rules = storage
            .find_many("rate_limit_rules", &json!({}))
            .await
            .unwrap_or_default()
            .into_iter()
            .filter(|rule| rule.to_string().to_ascii_lowercase().contains(&term))
            .map(strip_internal)
            .collect::<Vec<_>>();
        return success(StatusCode::OK, json!(rules), request_id);
    }
    if suffix == "statistics/summary" && method == Method::GET {
        let rules = storage
            .find_many("rate_limit_rules", &json!({}))
            .await
            .unwrap_or_default();
        let enabled = rules
            .iter()
            .filter(|rule| rule.get("enabled").and_then(Value::as_bool).unwrap_or(true))
            .count();
        return success(
            StatusCode::OK,
            json!({"total": rules.len(), "enabled": enabled, "disabled": rules.len() - enabled}),
            request_id,
        );
    }
    if suffix == "status" && method == Method::GET {
        return success(
            StatusCode::OK,
            json!({"enabled": true, "rules": storage.find_many("rate_limit_rules", &json!({})).await.unwrap_or_default().len()}),
            request_id,
        );
    }
    if let Some(operation) = suffix.strip_prefix("bulk/") {
        let ids = payload
            .get("rule_ids")
            .and_then(Value::as_array)
            .cloned()
            .unwrap_or_default();
        let mut affected = 0_u64;
        for id in ids.iter().filter_map(Value::as_str) {
            let changed = if operation == "delete" {
                storage
                    .delete_one("rate_limit_rules", &json!({"rule_id": id}))
                    .await
                    .ok()
                    == Some(true)
            } else {
                storage
                    .update_one(
                        "rate_limit_rules",
                        &json!({"rule_id": id}),
                        &json!({"enabled": operation == "enable"}),
                    )
                    .await
                    .ok()
                    .flatten()
                    .is_some()
            };
            if changed {
                affected += 1;
            }
        }
        return success(StatusCode::OK, json!({"affected": affected}), request_id);
    }
    let parts = suffix.split('/').collect::<Vec<_>>();
    if parts.len() == 2 && method == Method::POST {
        let id = parts[0];
        if parts[1] == "enable" || parts[1] == "disable" {
            return match storage
                .update_one(
                    "rate_limit_rules",
                    &json!({"rule_id": id}),
                    &json!({"enabled": parts[1] == "enable"}),
                )
                .await
            {
                Ok(Some(rule)) => success(StatusCode::OK, strip_internal(rule), request_id),
                _ => error(
                    StatusCode::NOT_FOUND,
                    "RATE404",
                    "Rule not found",
                    request_id,
                ),
            };
        }
        if parts[1] == "duplicate" {
            let Some(mut rule) = storage
                .find_one("rate_limit_rules", &json!({"rule_id": id}))
                .await
                .ok()
                .flatten()
            else {
                return error(
                    StatusCode::NOT_FOUND,
                    "RATE404",
                    "Rule not found",
                    request_id,
                );
            };
            rule["rule_id"] = payload
                .get("new_rule_id")
                .cloned()
                .unwrap_or_else(|| json!(Uuid::new_v4().to_string()));
            if let Some(map) = rule.as_object_mut() {
                map.remove("_id");
            }
            return match storage.insert_one("rate_limit_rules", rule).await {
                Ok(rule) => success(StatusCode::CREATED, strip_internal(rule), request_id),
                Err(_) => unexpected(request_id),
            };
        }
    }
    error(
        StatusCode::NOT_FOUND,
        "GTW003",
        "Platform route does not exist",
        request_id,
    )
}

#[allow(clippy::too_many_arguments)]
async fn entity_routes(
    state: &AppState,
    prefix: &str,
    spec: EntitySpec,
    path: &str,
    method: &Method,
    mut payload: Value,
    query: &HashMap<String, String>,
    username: &str,
    request_id: &str,
) -> Response {
    let Some(storage) = &state.storage else {
        return unexpected(request_id);
    };
    let suffix = path.strip_prefix(prefix).unwrap_or("").trim_matches('/');
    if method == Method::GET && (suffix.is_empty() || suffix == "all") {
        if !has_permission(state, username, spec.permission).await {
            return error(
                StatusCode::FORBIDDEN,
                spec.permission_code,
                "Insufficient permissions",
                request_id,
            );
        }
        let items = match storage.find_many(spec.collection, &json!({})).await {
            Ok(items) => items.into_iter().map(strip_internal).collect::<Vec<_>>(),
            Err(_) => return unexpected(request_id),
        };
        return success(StatusCode::OK, paginate(items, query), request_id);
    }
    if method == Method::POST && suffix.is_empty() {
        if !has_permission(state, username, spec.permission).await {
            return error(
                StatusCode::FORBIDDEN,
                spec.permission_code,
                "Insufficient permissions",
                request_id,
            );
        }
        let Some(key) = payload
            .get(spec.key)
            .and_then(Value::as_str)
            .map(str::to_owned)
        else {
            return error(
                StatusCode::UNPROCESSABLE_ENTITY,
                "VAL001",
                "Missing required field",
                request_id,
            );
        };
        if matches!(
            storage
                .find_one(spec.collection, &json!({spec.key: key}))
                .await,
            Ok(Some(_))
        ) {
            return error(
                StatusCode::BAD_REQUEST,
                spec.duplicate_code,
                "Resource already exists",
                request_id,
            );
        }
        if let Some(id_field) = spec.id_field {
            if payload
                .get(id_field)
                .and_then(Value::as_str)
                .is_none_or(str::is_empty)
            {
                payload[id_field] = json!(Uuid::new_v4().to_string());
            }
        }
        return match storage.insert_one(spec.collection, payload).await {
            Ok(_) => message(StatusCode::CREATED, spec.created, request_id),
            Err(_) => unexpected(request_id),
        };
    }
    let key = suffix.split('/').next().unwrap_or("");
    if key.is_empty() {
        return error(
            StatusCode::NOT_FOUND,
            "GTW003",
            "Platform route does not exist",
            request_id,
        );
    }
    let filter = json!({spec.key: key});
    if method == Method::GET {
        return match storage.find_one(spec.collection, &filter).await {
            Ok(Some(item)) => success(StatusCode::OK, strip_internal(item), request_id),
            Ok(None) => error(
                StatusCode::NOT_FOUND,
                spec.not_found_code,
                "Resource not found",
                request_id,
            ),
            Err(_) => unexpected(request_id),
        };
    }
    if !has_permission(state, username, spec.permission).await {
        return error(
            StatusCode::FORBIDDEN,
            "AUTH006",
            "Insufficient permissions",
            request_id,
        );
    }
    if method == Method::PUT {
        if payload
            .get(spec.key)
            .is_some_and(|value| value.as_str() != Some(key))
        {
            return error(
                StatusCode::BAD_REQUEST,
                "VAL001",
                "Resource identifier cannot be updated",
                request_id,
            );
        }
        return match storage.update_one(spec.collection, &filter, &payload).await {
            Ok(Some(_)) => message(StatusCode::OK, spec.updated, request_id),
            Ok(None) => error(
                StatusCode::NOT_FOUND,
                spec.not_found_code,
                "Resource not found",
                request_id,
            ),
            Err(_) => unexpected(request_id),
        };
    }
    if method == Method::DELETE {
        if (spec.collection == "roles" || spec.collection == "groups")
            && (key == "admin" || key == "ALL")
        {
            return error(
                StatusCode::BAD_REQUEST,
                "AUTH900",
                "Protected resource cannot be deleted",
                request_id,
            );
        }
        return match storage.delete_one(spec.collection, &filter).await {
            Ok(true) => message(StatusCode::OK, spec.deleted, request_id),
            Ok(false) => error(
                StatusCode::NOT_FOUND,
                spec.not_found_code,
                "Resource not found",
                request_id,
            ),
            Err(_) => unexpected(request_id),
        };
    }
    error(
        StatusCode::METHOD_NOT_ALLOWED,
        "GTW004",
        "Method not allowed",
        request_id,
    )
}

fn merge_proto_metadata(target: &mut Value, source: &Value) {
    for key in [
        "api_grpc_proto_source",
        "api_grpc_descriptor_set",
        "api_grpc_descriptor_sha256",
    ] {
        if let Some(value) = source.get(key) {
            target[key] = value.clone();
        }
    }
    if target.get("api_grpc_package").is_none_or(Value::is_null) {
        if let Some(value) = source.get("api_grpc_package") {
            target["api_grpc_package"] = value.clone();
        }
    }
}

async fn api_routes(
    state: &AppState,
    path: &str,
    method: &Method,
    mut payload: Value,
    query: &HashMap<String, String>,
    username: &str,
    request_id: &str,
) -> Response {
    let Some(storage) = &state.storage else {
        return unexpected(request_id);
    };
    let suffix = path.strip_prefix("/api").unwrap_or("").trim_matches('/');
    if method == Method::GET && (suffix.is_empty() || suffix == "all") {
        return match storage.find_many("apis", &json!({})).await {
            Ok(items) => success(
                StatusCode::OK,
                paginate(items.into_iter().map(strip_internal).collect(), query),
                request_id,
            ),
            Err(_) => unexpected(request_id),
        };
    }
    let parts = suffix
        .split('/')
        .filter(|part| !part.is_empty())
        .collect::<Vec<_>>();
    if parts.len() >= 3 {
        return api_discovery_routes(state, &parts, method, username, request_id).await;
    }
    if method == Method::POST && parts.is_empty() {
        if !has_permission(state, username, "manage_apis").await {
            return error(
                StatusCode::FORBIDDEN,
                "API007",
                "You do not have permission to create APIs",
                request_id,
            );
        }
        payload = match normalize_create_api(&payload) {
            Ok(payload) => payload,
            Err(errors) => return validation_errors(errors, request_id),
        };
        let name = payload["api_name"]
            .as_str()
            .expect("validated API name")
            .to_owned();
        let version = payload["api_version"]
            .as_str()
            .expect("validated API version")
            .to_owned();
        if payload["api_public"].as_bool().unwrap_or(false)
            && payload["api_credits_enabled"].as_bool().unwrap_or(false)
        {
            return error(
                StatusCode::BAD_REQUEST,
                "API013",
                "Public API cannot have credits enabled",
                request_id,
            );
        }
        let filter = json!({"api_name": name, "api_version": version});
        let existing = storage.find_one("apis", &filter).await.ok().flatten();
        if let Some(existing) = existing {
            let descriptor_only =
                existing.get("api_id").is_none() && existing.get("api_grpc_proto_source").is_some();
            if !descriptor_only {
                return message(StatusCode::OK, "API already exists", request_id);
            }
            merge_proto_metadata(&mut payload, &existing);
            payload["api_id"] = json!(Uuid::new_v4().to_string());
            payload["api_path"] = json!(format!("/{name}/{version}"));
            return match storage.update_one("apis", &filter, &payload).await {
                Ok(Some(api)) => success(
                    StatusCode::CREATED,
                    json!({"api": strip_internal(api)}),
                    request_id,
                ),
                _ => unexpected(request_id),
            };
        }
        if let Ok(Some(pending)) = storage.find_one("grpc_proto_uploads", &filter).await {
            merge_proto_metadata(&mut payload, &pending);
        }
        payload["api_id"] = json!(Uuid::new_v4().to_string());
        payload["api_path"] = json!(format!("/{name}/{version}"));
        return match storage.insert_one("apis", payload).await {
            Ok(api) => {
                let _ = storage.delete_one("grpc_proto_uploads", &filter).await;
                success(
                    StatusCode::CREATED,
                    json!({"api": strip_internal(api)}),
                    request_id,
                )
            }
            Err(_) => unexpected(request_id),
        };
    }
    if parts.len() != 2 {
        return error(
            StatusCode::NOT_FOUND,
            "GTW003",
            "Platform route does not exist",
            request_id,
        );
    }
    let filter = json!({"api_name": parts[0], "api_version": parts[1]});
    if method == Method::GET {
        return match storage.find_one("apis", &filter).await {
            Ok(Some(api)) => success(StatusCode::OK, strip_internal(api), request_id),
            Ok(None) => error(
                StatusCode::NOT_FOUND,
                "API003",
                "API does not exist for the requested name and version",
                request_id,
            ),
            Err(_) => unexpected(request_id),
        };
    }
    if !has_permission(state, username, "manage_apis").await {
        return error(
            StatusCode::FORBIDDEN,
            "API008",
            "You do not have permission to update APIs",
            request_id,
        );
    }
    if method == Method::PUT {
        payload = match normalize_update_api(&payload) {
            Ok(payload) => payload,
            Err(errors) => return validation_errors(errors, request_id),
        };
        let Some(updates) = payload.as_object() else {
            return unexpected(request_id);
        };
        if updates.is_empty() {
            return error(
                StatusCode::BAD_REQUEST,
                "API006",
                "No data to update",
                request_id,
            );
        }
        for key in ["api_name", "api_version", "api_path"] {
            if payload.get(key).is_some() {
                let expected = if key == "api_name" {
                    parts[0].to_owned()
                } else if key == "api_version" {
                    parts[1].to_owned()
                } else {
                    format!("/{}/{}", parts[0], parts[1])
                };
                if payload.get(key).and_then(Value::as_str) != Some(expected.as_str()) {
                    return error(
                        StatusCode::BAD_REQUEST,
                        "API005",
                        "API name and version cannot be updated",
                        request_id,
                    );
                }
            }
        }
        let existing = match storage.find_one("apis", &filter).await {
            Ok(Some(existing)) => existing,
            Ok(None) => {
                return error(
                    StatusCode::BAD_REQUEST,
                    "API003",
                    "API does not exist for the requested name and version",
                    request_id,
                );
            }
            Err(_) => return unexpected(request_id),
        };
        let desired_public = payload
            .get("api_public")
            .and_then(Value::as_bool)
            .or_else(|| existing.get("api_public").and_then(Value::as_bool))
            .unwrap_or(false);
        let desired_credits = payload
            .get("api_credits_enabled")
            .and_then(Value::as_bool)
            .or_else(|| existing.get("api_credits_enabled").and_then(Value::as_bool))
            .unwrap_or(false);
        if desired_public && desired_credits {
            return error(
                StatusCode::BAD_REQUEST,
                "API013",
                "Public API cannot have credits enabled",
                request_id,
            );
        }
        let changed = updates
            .iter()
            .any(|(key, value)| existing.get(key) != Some(value));
        if !changed {
            return error(
                StatusCode::BAD_REQUEST,
                "API002",
                "Unable to update api",
                request_id,
            );
        }
        return match storage.update_one("apis", &filter, &payload).await {
            Ok(Some(_)) => message(StatusCode::OK, "API updated successfully", request_id),
            Ok(None) => error(
                StatusCode::BAD_REQUEST,
                "API003",
                "API does not exist for the requested name and version",
                request_id,
            ),
            Err(_) => unexpected(request_id),
        };
    }
    if method == Method::DELETE {
        return match storage.delete_one("apis", &filter).await {
            Ok(true) => message(StatusCode::OK, "API deleted successfully", request_id),
            Ok(false) => error(
                StatusCode::BAD_REQUEST,
                "API003",
                "API does not exist for the requested name and version",
                request_id,
            ),
            Err(_) => unexpected(request_id),
        };
    }
    error(
        StatusCode::METHOD_NOT_ALLOWED,
        "GTW004",
        "Method not allowed",
        request_id,
    )
}

async fn user_routes(
    state: &AppState,
    path: &str,
    method: &Method,
    mut payload: Value,
    query: &HashMap<String, String>,
    active_user: &str,
    request_id: &str,
) -> Response {
    let Some(storage) = &state.storage else {
        return unexpected(request_id);
    };
    let suffix = path
        .strip_prefix("/users")
        .or_else(|| path.strip_prefix("/user"))
        .unwrap_or("")
        .trim_matches('/');
    if method == Method::GET && (suffix.is_empty() || suffix == "all") {
        if !has_permission(state, active_user, "manage_users").await {
            return error(
                StatusCode::FORBIDDEN,
                "USR008",
                "Unable to retrieve users",
                request_id,
            );
        }
        return match storage.find_many("users", &json!({})).await {
            Ok(items) => success(
                StatusCode::OK,
                paginate(items.into_iter().map(public_user).collect(), query),
                request_id,
            ),
            Err(_) => unexpected(request_id),
        };
    }
    if method == Method::GET && suffix == "me" {
        return user_by(state, "username", active_user, active_user, request_id).await;
    }
    if method == Method::GET && suffix.starts_with("email/") {
        return user_by(
            state,
            "email",
            suffix.trim_start_matches("email/"),
            active_user,
            request_id,
        )
        .await;
    }
    if method == Method::POST && suffix.is_empty() {
        if !has_permission(state, active_user, "manage_users").await {
            return error(
                StatusCode::FORBIDDEN,
                "USR006",
                "You do not have permission to create users",
                request_id,
            );
        }
        return create_user(state, &mut payload, request_id).await;
    }
    let target = suffix.split('/').next().unwrap_or("");
    if target.is_empty() {
        return error(
            StatusCode::NOT_FOUND,
            "USR002",
            "User not found",
            request_id,
        );
    }
    if method == Method::GET {
        return user_by(state, "username", target, active_user, request_id).await;
    }
    if active_user != target && !has_permission(state, active_user, "manage_users").await {
        return error(
            StatusCode::FORBIDDEN,
            "USR008",
            "Unable to update user",
            request_id,
        );
    }
    if method == Method::PUT {
        if suffix.ends_with("/update-password") {
            let Some(password) = payload.get("password").and_then(Value::as_str) else {
                return error(
                    StatusCode::BAD_REQUEST,
                    "USR005",
                    "Password is required",
                    request_id,
                );
            };
            if !secure_password(password) {
                return error(
                    StatusCode::BAD_REQUEST,
                    "USR005",
                    password_policy(),
                    request_id,
                );
            }
            payload = json!({"password": bcrypt::hash(password, bcrypt::DEFAULT_COST).unwrap_or_default()});
        } else if let Some(password) = payload.get("password").and_then(Value::as_str) {
            if !secure_password(password) {
                return error(
                    StatusCode::BAD_REQUEST,
                    "USR005",
                    password_policy(),
                    request_id,
                );
            }
            payload["password"] =
                json!(bcrypt::hash(password, bcrypt::DEFAULT_COST).unwrap_or_default());
        }
        return match storage
            .update_one("users", &json!({"username": target}), &payload)
            .await
        {
            Ok(Some(_)) => message(StatusCode::OK, "User updated successfully", request_id),
            Ok(None) => error(
                StatusCode::NOT_FOUND,
                "USR002",
                "User not found",
                request_id,
            ),
            Err(_) => unexpected(request_id),
        };
    }
    if method == Method::DELETE {
        if target == "admin" {
            return error(
                StatusCode::BAD_REQUEST,
                "USR009",
                "Admin user cannot be deleted",
                request_id,
            );
        }
        return match storage
            .delete_one("users", &json!({"username": target}))
            .await
        {
            Ok(true) => message(StatusCode::OK, "User deleted successfully", request_id),
            Ok(false) => error(
                StatusCode::NOT_FOUND,
                "USR002",
                "User not found",
                request_id,
            ),
            Err(_) => unexpected(request_id),
        };
    }
    error(
        StatusCode::METHOD_NOT_ALLOWED,
        "GTW004",
        "Method not allowed",
        request_id,
    )
}

async fn endpoint_routes(
    state: &AppState,
    path: &str,
    method: &Method,
    mut payload: Value,
    query: &HashMap<String, String>,
    username: &str,
    request_id: &str,
) -> Response {
    let Some(storage) = &state.storage else {
        return unexpected(request_id);
    };
    let suffix = path
        .strip_prefix("/endpoint")
        .unwrap_or("")
        .trim_matches('/');
    let validation_suffix = suffix
        .strip_prefix("endpoint/validation/")
        .or_else(|| suffix.strip_prefix("validation/"));
    if let Some(endpoint_id) = validation_suffix {
        let filter = json!({"endpoint_id": endpoint_id});
        return document_by_method(
            state,
            "endpoint_validations",
            filter,
            method,
            payload,
            username,
            "manage_endpoints",
            "Endpoint validation",
            request_id,
        )
        .await;
    }
    if (suffix == "endpoint/validation" || suffix == "validation") && method == Method::POST {
        if !has_permission(state, username, "manage_endpoints").await {
            return error(
                StatusCode::FORBIDDEN,
                "END010",
                "Insufficient permissions",
                request_id,
            );
        }
        if payload.get("endpoint_id").is_none() {
            return error(
                StatusCode::BAD_REQUEST,
                "VAL001",
                "endpoint_id is required",
                request_id,
            );
        }
        return match storage.insert_one("endpoint_validations", payload).await {
            Ok(_) => message(
                StatusCode::CREATED,
                "Endpoint validation created successfully",
                request_id,
            ),
            Err(_) => unexpected(request_id),
        };
    }
    if method == Method::POST && suffix.is_empty() {
        if !has_permission(state, username, "manage_endpoints").await {
            return error(
                StatusCode::FORBIDDEN,
                "END010",
                "You do not have permission to create endpoints",
                request_id,
            );
        }
        for field in [
            "api_name",
            "api_version",
            "endpoint_method",
            "endpoint_uri",
            "endpoint_description",
        ] {
            if payload.get(field).and_then(Value::as_str).is_none() {
                return error(
                    StatusCode::UNPROCESSABLE_ENTITY,
                    "VAL001",
                    "Missing required field",
                    request_id,
                );
            }
        }
        payload["endpoint_id"] = json!(Uuid::new_v4().to_string());
        if payload.get("client_uri").is_none() {
            payload["client_uri"] = payload["endpoint_uri"].clone();
        }
        return match storage.insert_one("endpoints", payload).await {
            Ok(_) => message(
                StatusCode::CREATED,
                "Endpoint created successfully",
                request_id,
            ),
            Err(_) => unexpected(request_id),
        };
    }
    let parts = suffix.split('/').collect::<Vec<_>>();
    if method == Method::GET && parts.len() == 2 {
        return match storage
            .find_many(
                "endpoints",
                &json!({"api_name": parts[0], "api_version": parts[1]}),
            )
            .await
        {
            Ok(items) => success(
                StatusCode::OK,
                paginate(items.into_iter().map(strip_internal).collect(), query),
                request_id,
            ),
            Err(_) => unexpected(request_id),
        };
    }
    if parts.len() >= 4 {
        let uri = format!("/{}", parts[3..].join("/"));
        let filter = json!({"endpoint_method": parts[0], "api_name": parts[1], "api_version": parts[2], "endpoint_uri": uri});
        return document_by_method(
            state,
            "endpoints",
            filter,
            method,
            payload,
            username,
            "manage_endpoints",
            "Endpoint",
            request_id,
        )
        .await;
    }
    error(
        StatusCode::NOT_FOUND,
        "EPT002",
        "Endpoint not found",
        request_id,
    )
}

#[allow(clippy::too_many_arguments)]
async fn document_by_method(
    state: &AppState,
    collection: &str,
    filter: Value,
    method: &Method,
    payload: Value,
    username: &str,
    permission: &str,
    label: &str,
    request_id: &str,
) -> Response {
    let Some(storage) = &state.storage else {
        return unexpected(request_id);
    };
    if method == Method::GET {
        return match storage.find_one(collection, &filter).await {
            Ok(Some(item)) => success(StatusCode::OK, strip_internal(item), request_id),
            Ok(None) => error(
                StatusCode::NOT_FOUND,
                "EPT002",
                &format!("{label} not found"),
                request_id,
            ),
            Err(_) => unexpected(request_id),
        };
    }
    if !has_permission(state, username, permission).await {
        return error(
            StatusCode::FORBIDDEN,
            "END010",
            "Insufficient permissions",
            request_id,
        );
    }
    if method == Method::PUT {
        return match storage.update_one(collection, &filter, &payload).await {
            Ok(Some(_)) => message(
                StatusCode::OK,
                &format!("{label} updated successfully"),
                request_id,
            ),
            Ok(None) => error(
                StatusCode::NOT_FOUND,
                "EPT002",
                &format!("{label} not found"),
                request_id,
            ),
            Err(_) => unexpected(request_id),
        };
    }
    if method == Method::DELETE {
        return match storage.delete_one(collection, &filter).await {
            Ok(true) => message(
                StatusCode::OK,
                &format!("{label} deleted successfully"),
                request_id,
            ),
            Ok(false) => error(
                StatusCode::NOT_FOUND,
                "EPT002",
                &format!("{label} not found"),
                request_id,
            ),
            Err(_) => unexpected(request_id),
        };
    }
    error(
        StatusCode::METHOD_NOT_ALLOWED,
        "GTW004",
        "Method not allowed",
        request_id,
    )
}

async fn login(
    state: &AppState,
    headers: &HeaderMap,
    payload: Value,
    request_id: &str,
) -> Response {
    let Some(storage) = &state.storage else {
        return unexpected(request_id);
    };
    let Some(email) = payload.get("email").and_then(Value::as_str) else {
        return error(
            StatusCode::BAD_REQUEST,
            "AUTH001",
            "Missing email or password",
            request_id,
        );
    };
    let Some(password) = payload.get("password").and_then(Value::as_str) else {
        return error(
            StatusCode::BAD_REQUEST,
            "AUTH001",
            "Missing email or password",
            request_id,
        );
    };
    let user = match storage.find_one("users", &json!({"email": email})).await {
        Ok(Some(user)) => user,
        _ => match storage.find_one("users", &json!({"username": email})).await {
            Ok(Some(user)) => user,
            _ => {
                return error(
                    StatusCode::BAD_REQUEST,
                    "AUTH002",
                    "Invalid email or password",
                    request_id,
                );
            }
        },
    };
    let hash = password_hash(&user);
    if hash
        .as_deref()
        .is_none_or(|hash| !bcrypt::verify(password, hash).unwrap_or(false))
    {
        return error(
            StatusCode::BAD_REQUEST,
            "AUTH002",
            "Invalid email or password",
            request_id,
        );
    }
    if user.get("active").and_then(Value::as_bool) == Some(false) {
        return error(
            StatusCode::BAD_REQUEST,
            "AUTH007",
            "User is not active",
            request_id,
        );
    }
    let username = user
        .get("username")
        .and_then(Value::as_str)
        .unwrap_or(email)
        .to_owned();
    let role = user
        .get("role")
        .and_then(Value::as_str)
        .unwrap_or("user")
        .to_owned();
    let now = unix_seconds() as usize;
    let expiry_seconds = auth_expiry_seconds();
    let claims = AccessClaims {
        sub: username.clone(),
        role,
        jti: Uuid::new_v4().to_string(),
        iat: now,
        exp: now + expiry_seconds,
    };
    let token = match sign_token(state, &claims) {
        Ok(token) => token,
        Err(_) => {
            return error(
                StatusCode::INTERNAL_SERVER_ERROR,
                "GTW999",
                "An unexpected error occurred",
                request_id,
            );
        }
    };
    let csrf = Uuid::new_v4().to_string();
    let _ = storage
        .set_ephemeral(
            &format!("csrf_token_map:{username}"),
            Value::String(csrf.clone()),
            expiry_seconds as u64,
        )
        .await;
    let secure = cookie_secure(headers);
    let same_site = cookie_same_site(secure);
    let domain_attribute = cookie_domain(headers)
        .map(|domain| format!("; Domain={domain}"))
        .unwrap_or_default();
    let mut response = success(StatusCode::OK, json!({"access_token": token}), request_id);
    let cookie_headers = response.headers_mut();
    cookie_headers.append(
        header::SET_COOKIE,
        HeaderValue::from_str(&format!(
            "csrf_token={csrf}; Path=/; Max-Age=1800; SameSite={same_site}{}{}",
            if secure { "; Secure" } else { "" },
            domain_attribute
        ))
        .unwrap(),
    );
    cookie_headers.append(
        header::SET_COOKIE,
        HeaderValue::from_str(&format!(
            "access_token_cookie={token}; Path=/; Max-Age=1800; HttpOnly; SameSite={same_site}{}{}",
            if secure { "; Secure" } else { "" },
            domain_attribute
        ))
        .unwrap(),
    );
    response
}

async fn register(state: &AppState, mut payload: Value, request_id: &str) -> Response {
    let email = payload
        .get("email")
        .and_then(Value::as_str)
        .unwrap_or("")
        .to_owned();
    let password = payload
        .get("password")
        .and_then(Value::as_str)
        .unwrap_or("")
        .to_owned();
    if email.is_empty() || password.is_empty() {
        return error(
            StatusCode::BAD_REQUEST,
            "AUTH001",
            "Missing email or password",
            request_id,
        );
    }
    payload["username"] = json!(email.split('@').next().unwrap_or(""));
    payload["role"] = json!("user");
    payload["active"] = json!(true);
    create_user(state, &mut payload, request_id).await
}

async fn create_user(state: &AppState, payload: &mut Value, request_id: &str) -> Response {
    let Some(storage) = &state.storage else {
        return unexpected(request_id);
    };
    let username = payload
        .get("username")
        .and_then(Value::as_str)
        .unwrap_or("")
        .to_owned();
    let email = payload
        .get("email")
        .and_then(Value::as_str)
        .unwrap_or("")
        .to_owned();
    let password = payload
        .get("password")
        .and_then(Value::as_str)
        .unwrap_or("")
        .to_owned();
    if username.len() < 3 || email.len() < 3 || !secure_password(&password) {
        return error(
            StatusCode::BAD_REQUEST,
            "USR005",
            password_policy(),
            request_id,
        );
    }
    if matches!(
        storage
            .find_one("users", &json!({"username": username}))
            .await,
        Ok(Some(_))
    ) || matches!(
        storage.find_one("users", &json!({"email": email})).await,
        Ok(Some(_))
    ) {
        return error(
            StatusCode::BAD_REQUEST,
            "USR001",
            "Username or email already exists",
            request_id,
        );
    }
    if payload
        .get("custom_attributes")
        .and_then(Value::as_object)
        .is_some_and(|attrs| attrs.len() > 10)
    {
        return error(
            StatusCode::BAD_REQUEST,
            "USR016",
            "Maximum 10 custom attributes allowed. Please replace an existing one.",
            request_id,
        );
    }
    payload["password"] = json!(bcrypt::hash(password, bcrypt::DEFAULT_COST).unwrap_or_default());
    set_default(payload, "groups", json!([]));
    set_default(payload, "active", json!(true));
    set_default(payload, "ui_access", json!(false));
    match storage.insert_one("users", payload.clone()).await {
        Ok(_) => message(StatusCode::CREATED, "User created successfully", request_id),
        Err(_) => unexpected(request_id),
    }
}

async fn user_by(
    state: &AppState,
    field: &str,
    value: &str,
    active_user: &str,
    request_id: &str,
) -> Response {
    let Some(storage) = &state.storage else {
        return unexpected(request_id);
    };
    let user = match storage.find_one("users", &json!({field: value})).await {
        Ok(Some(user)) => user,
        Ok(None) => {
            return error(
                StatusCode::NOT_FOUND,
                "USR002",
                "User not found",
                request_id,
            );
        }
        Err(_) => return unexpected(request_id),
    };
    if user.get("username").and_then(Value::as_str) != Some(active_user)
        && !has_permission(state, active_user, "manage_users").await
    {
        return error(
            StatusCode::FORBIDDEN,
            "USR008",
            "Unable to retrieve information for user",
            request_id,
        );
    }
    success(StatusCode::OK, public_user(user), request_id)
}

async fn authorization_routes(
    state: &AppState,
    headers: &HeaderMap,
    path: &str,
    method: Method,
    _payload: Value,
    claims: &AuthClaims,
    request_id: &str,
) -> Response {
    let username = claims.sub.as_deref().unwrap_or("");
    if path == "/authorization/refresh" && method == Method::POST {
        let now = unix_seconds() as usize;
        let expiry_seconds = refresh_expiry_seconds();
        let token_claims = AccessClaims {
            sub: username.to_owned(),
            role: claims.role.clone().unwrap_or_else(|| "user".to_owned()),
            jti: Uuid::new_v4().to_string(),
            iat: now,
            exp: now + expiry_seconds,
        };
        let token = match sign_token(state, &token_claims) {
            Ok(token) => token,
            Err(_) => return unexpected(request_id),
        };
        let csrf = Uuid::new_v4().to_string();
        if let Some(storage) = &state.storage {
            let _ = storage
                .set_ephemeral(
                    &format!("csrf_token_map:{username}"),
                    Value::String(csrf.clone()),
                    expiry_seconds as u64,
                )
                .await;
        }
        let secure = cookie_secure(headers);
        let same_site = cookie_same_site(secure);
        let domain_attribute = cookie_domain(headers)
            .map(|domain| format!("; Domain={domain}"))
            .unwrap_or_default();
        let mut response = success(StatusCode::OK, json!({"refresh_token": token}), request_id);
        response.headers_mut().append(
            header::SET_COOKIE,
            HeaderValue::from_str(&format!(
                "csrf_token={csrf}; Path=/; Max-Age=604800; SameSite={same_site}{}{}",
                if secure { "; Secure" } else { "" },
                domain_attribute
            ))
            .unwrap(),
        );
        response.headers_mut().append(header::SET_COOKIE, HeaderValue::from_str(&format!("access_token_cookie={token}; Path=/; Max-Age=604800; HttpOnly; SameSite={same_site}{}{}", if secure {"; Secure"} else {""}, domain_attribute)).unwrap());
        return response;
    }
    if path == "/authorization/status" && method == Method::GET {
        return success(
            StatusCode::OK,
            json!({"authenticated": true, "username": username, "role": claims.role}),
            request_id,
        );
    }
    if path == "/authorization/invalidate" && method == Method::POST {
        if let Some(storage) = &state.storage {
            let _ = storage.insert_one("revocations", json!({
                "type": "jti", "username": username, "jti": claims.jti, "expires_at": claims.exp
            })).await;
        }
        let mut response = message(StatusCode::OK, "Token invalidated successfully", request_id);
        response.headers_mut().append(
            header::SET_COOKIE,
            HeaderValue::from_static("access_token_cookie=; Path=/; Max-Age=0; HttpOnly"),
        );
        return response;
    }
    let parts = path
        .trim_start_matches("/authorization/admin/")
        .split('/')
        .collect::<Vec<_>>();
    if parts.len() == 2 && has_permission(state, username, "manage_auth").await {
        let target = parts[1];
        if parts[0] == "status" {
            let Some(storage) = &state.storage else {
                return unexpected(request_id);
            };
            let Some(user) = storage
                .find_one("users", &json!({"username": target}))
                .await
                .ok()
                .flatten()
            else {
                return error(
                    StatusCode::NOT_FOUND,
                    "USR002",
                    "User not found",
                    request_id,
                );
            };
            let revoked = storage
                .find_one(
                    "revocations",
                    &json!({"type": "revoke_all", "username": target}),
                )
                .await
                .ok()
                .flatten()
                .is_some();
            return success(
                StatusCode::OK,
                json!({"username": target, "active": user.get("active").and_then(Value::as_bool).unwrap_or(true), "revoked": revoked}),
                request_id,
            );
        }
        if parts[0] == "disable" || parts[0] == "enable" {
            let active = parts[0] == "enable";
            if let Some(storage) = &state.storage {
                return match storage
                    .update_one(
                        "users",
                        &json!({"username": target}),
                        &json!({"active": active}),
                    )
                    .await
                {
                    Ok(Some(_)) => message(
                        StatusCode::OK,
                        if active {
                            "User enabled successfully"
                        } else {
                            "User disabled successfully"
                        },
                        request_id,
                    ),
                    Ok(None) => error(
                        StatusCode::NOT_FOUND,
                        "USR002",
                        "User not found",
                        request_id,
                    ),
                    Err(_) => unexpected(request_id),
                };
            }
        }
        if parts[0] == "revoke" || parts[0] == "unrevoke" {
            if let Some(storage) = &state.storage {
                if parts[0] == "revoke" {
                    let _ = storage
                        .insert_one(
                            "revocations",
                            json!({"type": "revoke_all", "username": target, "revoke_all": true}),
                        )
                        .await;
                } else {
                    let _ = storage
                        .delete_one(
                            "revocations",
                            &json!({"type": "revoke_all", "username": target}),
                        )
                        .await;
                }
            }
            return message(
                StatusCode::OK,
                if parts[0] == "revoke" {
                    "All tokens revoked"
                } else {
                    "Token revocation cleared"
                },
                request_id,
            );
        }
    }
    error(
        StatusCode::NOT_FOUND,
        "GTW003",
        "Platform route does not exist",
        request_id,
    )
}

async fn platform_ip_filter(
    state: &AppState,
    headers: &HeaderMap,
    direct_addr: Option<SocketAddr>,
    request_id: &str,
) -> Option<Response> {
    let storage = state.storage.as_ref()?;
    let settings = storage
        .find_one("settings", &json!({}))
        .await
        .ok()
        .flatten();
    let whitelist = settings
        .as_ref()
        .and_then(|value| value.get("ip_whitelist"))
        .and_then(Value::as_array)
        .cloned()
        .unwrap_or_default();
    let blacklist = settings
        .as_ref()
        .and_then(|value| value.get("ip_blacklist"))
        .and_then(Value::as_array)
        .cloned()
        .unwrap_or_default();
    if whitelist.is_empty() && blacklist.is_empty() {
        return None;
    }
    let api = json!({
        "api_ip_mode": if whitelist.is_empty() {"allow_all"} else {"whitelist"},
        "api_ip_whitelist": whitelist,
        "api_ip_blacklist": blacklist,
        "api_trust_x_forwarded_for": settings
            .as_ref()
            .and_then(|value| value.get("trust_x_forwarded_for"))
            .and_then(Value::as_bool)
            .unwrap_or(state.config.shared_storage.trust_x_forwarded_for)
    });
    match enforce_api_ip_policy(
        &api,
        settings.as_ref(),
        headers,
        direct_addr.map(|addr| addr.ip()),
        state.config.shared_storage.trust_x_forwarded_for,
        state.config.shared_storage.local_host_ip_bypass,
    ) {
        Ok(()) => None,
        Err(failure) => Some(error(
            StatusCode::FORBIDDEN,
            if failure.error_code == "API011" {
                "SEC011"
            } else {
                "SEC010"
            },
            if failure.error_code == "API011" {
                "IP blocked"
            } else {
                "IP not allowed"
            },
            request_id,
        )),
    }
}

fn platform_openapi(request_id: &str) -> Response {
    match python_openapi_contract() {
        Ok(contract) => success(StatusCode::OK, contract.clone(), request_id),
        Err(message) => error(
            StatusCode::INTERNAL_SERVER_ERROR,
            "GTW999",
            message,
            request_id,
        ),
    }
}

fn python_openapi_contract() -> Result<&'static Value, &'static str> {
    if let Some(contract) = PYTHON_OPENAPI.get() {
        return Ok(contract);
    }
    let compressed = BASE64_STANDARD
        .decode(PYTHON_OPENAPI_GZIP_BASE64.trim())
        .map_err(|_| "Failed to decode embedded OpenAPI contract")?;
    let mut decoder = flate2::read::GzDecoder::new(compressed.as_slice());
    let mut decoded = Vec::new();
    decoder
        .read_to_end(&mut decoded)
        .map_err(|_| "Failed to decompress embedded OpenAPI contract")?;
    let contract = serde_json::from_slice(&decoded)
        .map_err(|_| "Failed to parse embedded OpenAPI contract")?;
    let _ = PYTHON_OPENAPI.set(contract);
    PYTHON_OPENAPI
        .get()
        .ok_or("Failed to initialize embedded OpenAPI contract")
}

fn platform_docs(path: &str, request_id: &str) -> Response {
    let html = if path == "/redoc" {
        r#"<!doctype html><html><head><title>Doorman API</title><script src="https://cdn.jsdelivr.net/npm/redoc@2.5.2/bundles/redoc.standalone.js"></script></head><body><redoc spec-url="/platform/openapi.json"></redoc></body></html>"#
    } else {
        r#"<!doctype html><html><head><title>Doorman API</title><link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.17.14/swagger-ui.css"></head><body><div id="swagger-ui"></div><script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.17.14/swagger-ui-bundle.js"></script><script>SwaggerUIBundle({url:'/platform/openapi.json',dom_id:'#swagger-ui'});</script></body></html>"#
    };
    let mut response = axum::response::Html(html).into_response();
    if let Ok(value) = HeaderValue::from_str(request_id) {
        response.headers_mut().insert("x-request-id", value.clone());
        response.headers_mut().insert("request_id", value);
    }
    response
}

async fn authorize(
    state: &AppState,
    headers: &HeaderMap,
    path: &str,
    request_id: &str,
) -> Result<AuthClaims, Response> {
    let claims = verify_request_token(headers, &state.config.shared_storage).map_err(|_| {
        error(
            StatusCode::UNAUTHORIZED,
            "AUTH003",
            "Unauthorized",
            request_id,
        )
    })?;
    let username = claims.sub.as_deref().unwrap_or("");
    let Some(storage) = &state.storage else {
        return Err(unexpected(request_id));
    };
    if state.config.https_only
        && path != "/user/admin"
        && !path.starts_with("/authorization")
        && !csrf_matches(headers, storage, username).await
    {
        return Err(error(
            StatusCode::UNAUTHORIZED,
            "AUTH003",
            "Invalid CSRF token",
            request_id,
        ));
    }
    if matches!(
        storage
            .find_one(
                "revocations",
                &json!({"type": "revoke_all", "username": username})
            )
            .await,
        Ok(Some(_))
    ) {
        return Err(error(
            StatusCode::UNAUTHORIZED,
            "AUTH003",
            "Token has been revoked",
            request_id,
        ));
    }
    if let Some(jti) = claims.jti.as_deref()
        && matches!(
            storage
                .find_one(
                    "revocations",
                    &json!({"type": "jti", "username": username, "jti": jti})
                )
                .await,
            Ok(Some(_))
        )
    {
        return Err(error(
            StatusCode::UNAUTHORIZED,
            "AUTH003",
            "Token has been revoked",
            request_id,
        ));
    }
    match storage
        .find_one("users", &json!({"username": username}))
        .await
    {
        Ok(Some(user)) if user.get("active").and_then(Value::as_bool) != Some(false) => Ok(claims),
        Ok(Some(_)) => Err(error(
            StatusCode::UNAUTHORIZED,
            "AUTH003",
            "User is inactive",
            request_id,
        )),
        _ => Err(error(
            StatusCode::NOT_FOUND,
            "USR002",
            "User not found",
            request_id,
        )),
    }
}

async fn has_permission(state: &AppState, username: &str, permission: &str) -> bool {
    let Some(storage) = &state.storage else {
        return false;
    };
    let Ok(Some(user)) = storage
        .find_one("users", &json!({"username": username}))
        .await
    else {
        return false;
    };
    if user.get("role").and_then(Value::as_str) == Some("admin") {
        return true;
    }
    let Some(role_name) = user.get("role").and_then(Value::as_str) else {
        return false;
    };
    matches!(storage.find_one("roles", &json!({"role_name": role_name})).await, Ok(Some(role)) if role.get(permission).and_then(Value::as_bool).unwrap_or(false))
}

async fn memory_dump(
    state: &AppState,
    payload: Value,
    username: &str,
    request_id: &str,
) -> Response {
    if !has_permission(state, username, "manage_security").await {
        return error(
            StatusCode::FORBIDDEN,
            "SEC003",
            "You do not have permission to perform memory dump",
            request_id,
        );
    }
    let Some(storage) = &state.storage else {
        return unexpected(request_id);
    };
    if !storage.is_memory() {
        return error(
            StatusCode::BAD_REQUEST,
            "MEM001",
            "Memory dump available only in memory-only mode",
            request_id,
        );
    }
    let path = payload.get("path").and_then(Value::as_str);
    match crate::storage::snapshot::dump(storage, path).await {
        Ok(path) => success(
            StatusCode::OK,
            json!({"response": {"path": path}}),
            request_id,
        ),
        Err(crate::storage::snapshot::SnapshotError::MissingKey) => error(
            StatusCode::BAD_REQUEST,
            "MEM002",
            "MEM_ENCRYPTION_KEY is not configured",
            request_id,
        ),
        Err(_) => unexpected(request_id),
    }
}

async fn memory_restore(
    state: &AppState,
    payload: Value,
    username: &str,
    request_id: &str,
) -> Response {
    if !has_permission(state, username, "manage_security").await {
        return error(
            StatusCode::FORBIDDEN,
            "SEC004",
            "You do not have permission to perform memory restore",
            request_id,
        );
    }
    let Some(storage) = &state.storage else {
        return unexpected(request_id);
    };
    if !storage.is_memory() {
        return error(
            StatusCode::BAD_REQUEST,
            "MEM001",
            "Memory restore available only in memory-only mode",
            request_id,
        );
    }
    let path = payload.get("path").and_then(Value::as_str);
    match crate::storage::snapshot::restore(storage, path).await {
        Ok((version, created_at)) => success(
            StatusCode::OK,
            json!({"response": {"version": version, "created_at": created_at}}),
            request_id,
        ),
        Err(crate::storage::snapshot::SnapshotError::MissingKey) => error(
            StatusCode::BAD_REQUEST,
            "MEM002",
            "MEM_ENCRYPTION_KEY is not configured",
            request_id,
        ),
        Err(crate::storage::snapshot::SnapshotError::Io(error_value))
            if error_value.kind() == std::io::ErrorKind::NotFound =>
        {
            error(
                StatusCode::NOT_FOUND,
                "MEM003",
                "Dump file not found",
                request_id,
            )
        }
        Err(_) => unexpected(request_id),
    }
}

async fn readiness(state: &AppState, privileged: bool, request_id: &str) -> Response {
    let (mongo_ok, redis_ok, memory_only) = if let Some(storage) = &state.storage {
        (
            storage.mongo_healthy().await,
            storage.redis_healthy().await,
            storage.is_memory(),
        )
    } else {
        (false, false, false)
    };
    let ready = mongo_ok && redis_ok;
    let status = if ready { "ready" } else { "degraded" };
    if !privileged {
        return success(StatusCode::OK, json!({"status": status}), request_id);
    }
    success(
        StatusCode::OK,
        json!({
            "status": status,
            "mongodb": mongo_ok,
            "redis": redis_ok,
            "mode": if memory_only { "memory" } else { "mongodb" },
            "cache_backend": if memory_only { "memory" } else { "redis" },
            "missing_grpc_descriptors": 0,
            "grpc_descriptor_errors": []
        }),
        request_id,
    )
}

async fn dashboard(state: &AppState, request_id: &str) -> Response {
    let Some(storage) = &state.storage else {
        return unexpected(request_id);
    };
    let new_apis = storage
        .find_many("apis", &json!({}))
        .await
        .unwrap_or_default()
        .len();
    let subscriptions = storage
        .find_many("subscriptions", &json!({}))
        .await
        .unwrap_or_default();

    let analytics = global_analytics();
    let mut monthly_usage = Map::new();
    for point in analytics.get_timeseries() {
        let Ok(timestamp) = time::OffsetDateTime::from_unix_timestamp(point.timestamp as i64)
        else {
            continue;
        };
        let month = match u8::from(timestamp.month()) {
            1 => "Jan",
            2 => "Feb",
            3 => "Mar",
            4 => "Apr",
            5 => "May",
            6 => "Jun",
            7 => "Jul",
            8 => "Aug",
            9 => "Sep",
            10 => "Oct",
            11 => "Nov",
            _ => "Dec",
        };
        let count = monthly_usage
            .get(month)
            .and_then(Value::as_u64)
            .unwrap_or_default()
            .saturating_add(point.requests);
        monthly_usage.insert(month.to_owned(), json!(count));
    }
    let total_requests = monthly_usage
        .values()
        .filter_map(Value::as_u64)
        .sum::<u64>();

    let active_users_list = analytics
        .get_top_users(5)
        .into_iter()
        .map(|user| {
            let subscriber_count = subscriptions
                .iter()
                .find(|subscription| subscription["username"].as_str() == Some(&user.name))
                .and_then(|subscription| subscription["apis"].as_array())
                .map(Vec::len)
                .unwrap_or_default();
            json!({
                "username": user.name,
                "requests": format_dashboard_count(user.count),
                "subscribers": subscriber_count
            })
        })
        .collect::<Vec<_>>();

    let popular_apis = analytics
        .get_top_apis(10)
        .into_iter()
        .map(|api| {
            let api_suffix = api.name.rsplit(':').next().unwrap_or(&api.name);
            let subscriber_count = subscriptions
                .iter()
                .filter(|subscription| {
                    subscription["apis"].as_array().is_some_and(|entries| {
                        entries
                            .iter()
                            .any(|entry| entry.to_string().contains(api_suffix))
                    })
                })
                .count();
            json!({
                "name": api.name,
                "requests": format_dashboard_count(api.count),
                "subscribers": subscriber_count
            })
        })
        .collect::<Vec<_>>();

    success(
        StatusCode::OK,
        json!({
            "totalRequests": total_requests,
            "activeUsers": analytics.user_count(),
            "newApis": new_apis,
            "monthlyUsage": monthly_usage,
            "activeUsersList": active_users_list,
            "popularApis": popular_apis
        }),
        request_id,
    )
}

fn format_dashboard_count(value: u64) -> String {
    let digits = value.to_string();
    let mut formatted = String::with_capacity(digits.len() + digits.len() / 3);
    for (index, character) in digits.chars().enumerate() {
        if index > 0 && (digits.len() - index).is_multiple_of(3) {
            formatted.push(',');
        }
        formatted.push(character);
    }
    formatted
}

async fn monitor_metrics(state: &AppState, request_id: &str) -> Response {
    success(
        StatusCode::OK,
        json!({
            "uptime_seconds": state.runtime.started_at.elapsed().as_secs(),
            "active_requests": state.runtime.active_requests.load(std::sync::atomic::Ordering::Relaxed),
            "total_requests": state.runtime.request_total.load(std::sync::atomic::Ordering::Relaxed)
        }),
        request_id,
    )
}

async fn monitor_report(state: &AppState, request_id: &str) -> Response {
    let storage_mode = state
        .storage
        .as_ref()
        .map(|storage| {
            if storage.is_memory() {
                "memory_only"
            } else {
                "external"
            }
        })
        .unwrap_or("unavailable");
    success(
        StatusCode::OK,
        json!({"status": "healthy", "storage_mode": storage_mode, "uptime_seconds": state.runtime.started_at.elapsed().as_secs()}),
        request_id,
    )
}
fn analytics_denied(request_id: &str) -> Response {
    error(
        StatusCode::FORBIDDEN,
        "ANALYTICS001",
        "You do not have permission to view analytics",
        request_id,
    )
}

fn analytics_time_range(query: &HashMap<String, String>) -> (u64, u64) {
    if let (Some(start), Some(end)) = (
        query.get("start_ts").and_then(|value| value.parse().ok()),
        query.get("end_ts").and_then(|value| value.parse().ok()),
    ) {
        return (start, end);
    }
    let end = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs();
    let duration = match query.get("range").map(String::as_str).unwrap_or("24h") {
        "1h" => 3_600,
        "7d" => 604_800,
        "30d" => 2_592_000,
        _ => 86_400,
    };
    (end.saturating_sub(duration), end)
}

fn analytics_limit(query: &HashMap<String, String>) -> usize {
    query
        .get("limit")
        .and_then(|value| value.parse::<usize>().ok())
        .unwrap_or(10)
        .clamp(1, 100)
}

fn analytics_percentiles(points: &[AggregatedPoint]) -> Value {
    let mut values = points
        .iter()
        .map(|point| point.latency_ms)
        .collect::<Vec<_>>();
    values.sort_by(|left, right| left.total_cmp(right));
    let percentile = |fraction: f64| {
        if values.is_empty() {
            0.0
        } else {
            let index = ((values.len() - 1) as f64 * fraction).round() as usize;
            values[index]
        }
    };
    json!({
        "p50": percentile(0.50),
        "p75": percentile(0.75),
        "p90": percentile(0.90),
        "p95": percentile(0.95),
        "p99": percentile(0.99)
    })
}

fn analytics_entity(entity: &EntityCounter, key: &str) -> Value {
    json!({key: entity.name, "count": entity.count})
}

fn analytics_endpoint(entity: &EntityCounter) -> Value {
    let error_rate = if entity.count == 0 {
        0.0
    } else {
        entity.error_count as f64 / entity.count as f64
    };
    json!({
        "endpoint_uri": entity.name,
        "count": entity.count,
        "error_count": entity.error_count,
        "error_rate": error_rate,
        "avg_ms": 0.0,
        "percentiles": {"p50": 0.0, "p75": 0.0, "p90": 0.0, "p95": 0.0, "p99": 0.0}
    })
}

fn analytics_series_point(point: &AggregatedPoint, metric_type: Option<&str>) -> Value {
    let error_rate = if point.requests == 0 {
        0.0
    } else {
        point.errors as f64 / point.requests as f64
    };
    let mut value = Map::new();
    value.insert("timestamp".to_owned(), json!(point.timestamp));
    match metric_type {
        Some("request_count") => {
            value.insert("count".to_owned(), json!(point.requests));
        }
        Some("error_rate") => {
            value.insert("error_rate".to_owned(), json!(error_rate));
            value.insert("error_count".to_owned(), json!(point.errors));
        }
        Some("latency") => {
            value.insert("avg_ms".to_owned(), json!(point.latency_ms));
            value.insert(
                "percentiles".to_owned(),
                json!({
                    "p50": point.latency_ms,
                    "p75": point.latency_ms,
                    "p90": point.latency_ms,
                    "p95": point.latency_ms,
                    "p99": point.latency_ms
                }),
            );
        }
        Some("bandwidth") => {
            value.insert("bytes_in".to_owned(), json!(point.bytes_in));
            value.insert("bytes_out".to_owned(), json!(point.bytes_out));
        }
        Some(_) => {}
        None => {
            value.insert("count".to_owned(), json!(point.requests));
            value.insert("error_count".to_owned(), json!(point.errors));
            value.insert("error_rate".to_owned(), json!(error_rate));
            value.insert("avg_ms".to_owned(), json!(point.latency_ms));
            value.insert(
                "percentiles".to_owned(),
                json!({
                    "p50": point.latency_ms,
                    "p75": point.latency_ms,
                    "p90": point.latency_ms,
                    "p95": point.latency_ms,
                    "p99": point.latency_ms
                }),
            );
            value.insert("bytes_in".to_owned(), json!(point.bytes_in));
            value.insert("bytes_out".to_owned(), json!(point.bytes_out));
            value.insert("unique_users".to_owned(), json!(0));
        }
    }
    Value::Object(value)
}

fn analytics_timeseries(query: &HashMap<String, String>, request_id: &str) -> Response {
    let (start_ts, end_ts) = analytics_time_range(query);
    let points = global_analytics().get_timeseries_range(start_ts, end_ts);
    let metric_type = query.get("metric_type").map(String::as_str);
    let series = points
        .iter()
        .map(|point| analytics_series_point(point, metric_type))
        .collect::<Vec<_>>();
    success(
        StatusCode::OK,
        json!({
            "time_range": {"start_ts": start_ts, "end_ts": end_ts},
            "granularity": query.get("granularity").map(String::as_str).unwrap_or("auto"),
            "series": series,
            "data_points": series.len()
        }),
        request_id,
    )
}

fn analytics_top(kind: &str, query: &HashMap<String, String>, request_id: &str) -> Response {
    let (start_ts, end_ts) = analytics_time_range(query);
    let limit = analytics_limit(query);
    let analytics = global_analytics();
    let response = match kind {
        "api" => {
            let entries = analytics
                .get_top_apis(limit)
                .iter()
                .map(|entry| analytics_entity(entry, "api"))
                .collect::<Vec<_>>();
            json!({
                "time_range": {"start_ts": start_ts, "end_ts": end_ts},
                "top_apis": entries,
                "total_apis": analytics.api_count()
            })
        }
        "user" => {
            let entries = analytics
                .get_top_users(limit)
                .iter()
                .map(|entry| analytics_entity(entry, "user"))
                .collect::<Vec<_>>();
            json!({
                "time_range": {"start_ts": start_ts, "end_ts": end_ts},
                "top_users": entries,
                "total_users": analytics.user_count()
            })
        }
        _ => {
            let mut entries = analytics
                .get_top_endpoints(analytics.endpoint_count())
                .iter()
                .map(analytics_endpoint)
                .collect::<Vec<_>>();
            let sort_by = query.get("sort_by").map(String::as_str).unwrap_or("count");
            if sort_by == "error_rate" {
                entries.sort_by(|left, right| {
                    right["error_rate"]
                        .as_f64()
                        .unwrap_or_default()
                        .total_cmp(&left["error_rate"].as_f64().unwrap_or_default())
                });
            }
            entries.truncate(limit);
            json!({
                "time_range": {"start_ts": start_ts, "end_ts": end_ts},
                "sort_by": sort_by,
                "top_endpoints": entries,
                "total_endpoints": analytics.endpoint_count()
            })
        }
    };
    success(StatusCode::OK, response, request_id)
}

async fn analytics_overview(
    state: &AppState,
    username: &str,
    query: &HashMap<String, String>,
    request_id: &str,
) -> Response {
    if !has_permission(state, username, "view_analytics").await {
        return analytics_denied(request_id);
    }
    let (start_ts, end_ts) = analytics_time_range(query);
    let analytics = global_analytics();
    let points = analytics.get_timeseries_range(start_ts, end_ts);
    let total_requests = points.iter().map(|point| point.requests).sum::<u64>();
    let total_errors = points.iter().map(|point| point.errors).sum::<u64>();
    let total_ms = points
        .iter()
        .map(|point| point.latency_ms * point.requests as f64)
        .sum::<f64>();
    let total_bytes_in = points.iter().map(|point| point.bytes_in).sum::<u64>();
    let total_bytes_out = points.iter().map(|point| point.bytes_out).sum::<u64>();
    let error_rate = if total_requests == 0 {
        0.0
    } else {
        total_errors as f64 / total_requests as f64
    };
    let avg_response_ms = if total_requests == 0 {
        0.0
    } else {
        total_ms / total_requests as f64
    };
    let top_apis = analytics
        .get_top_apis(10)
        .iter()
        .map(|entry| analytics_entity(entry, "api"))
        .collect::<Vec<_>>();
    let top_users = analytics
        .get_top_users(10)
        .iter()
        .map(|entry| analytics_entity(entry, "user"))
        .collect::<Vec<_>>();
    success(
        StatusCode::OK,
        json!({
            "time_range": {
                "start_ts": start_ts,
                "end_ts": end_ts,
                "duration_seconds": end_ts.saturating_sub(start_ts)
            },
            "summary": {
                "total_requests": total_requests,
                "total_errors": total_errors,
                "error_rate": error_rate,
                "avg_response_ms": avg_response_ms,
                "unique_users": analytics.user_count(),
                "total_bandwidth": total_bytes_in + total_bytes_out,
                "bandwidth_in": total_bytes_in,
                "bandwidth_out": total_bytes_out
            },
            "percentiles": analytics_percentiles(&points),
            "top_apis": top_apis,
            "top_users": top_users,
            "status_distribution": analytics.get_status_distribution()
        }),
        request_id,
    )
}

async fn get_security_settings(state: &AppState, request_id: &str) -> Response {
    let Some(storage) = &state.storage else {
        return unexpected(request_id);
    };
    let is_memory = state.config.shared_storage.storage_mode.to_uppercase() == "MEM";
    match storage.find_many("settings", &json!({})).await {
        Ok(items) => {
            let mut settings = items.into_iter().next().unwrap_or_else(|| json!({}));
            if let Value::Object(ref mut map) = settings {
                map.insert("memory_only".to_owned(), json!(is_memory));
            }
            success(StatusCode::OK, settings, request_id)
        }
        Err(_) => unexpected(request_id),
    }
}

async fn upsert_singleton(
    state: &AppState,
    collection: &str,
    payload: Value,
    request_id: &str,
) -> Response {
    let Some(storage) = &state.storage else {
        return unexpected(request_id);
    };
    let existing = storage
        .find_many(collection, &json!({}))
        .await
        .unwrap_or_default();
    let is_memory = state.config.shared_storage.storage_mode.to_uppercase() == "MEM";
    let mut updated_doc = payload.clone();
    let result = if let Some(first) = existing.first() {
        if let Some(id) = first.get("_id") {
            let mut merged = first.clone();
            if let (Value::Object(base), Value::Object(new_vals)) = (&mut merged, payload) {
                for (k, v) in new_vals {
                    base.insert(k, v);
                }
            }
            updated_doc = merged.clone();
            storage
                .update_one(collection, &json!({"_id": id}), &updated_doc)
                .await
                .map(|_| ())
        } else {
            storage
                .replace_collection(collection, vec![payload.clone()])
                .await
        }
    } else {
        storage
            .insert_one(collection, payload.clone())
            .await
            .map(|_| ())
    };
    match result {
        Ok(()) => {
            let mut settings = strip_internal(updated_doc);
            if let Value::Object(ref mut map) = settings {
                map.insert("memory_only".to_owned(), json!(is_memory));
            }
            success(StatusCode::OK, settings, request_id)
        }
        Err(_) => unexpected(request_id),
    }
}

async fn config_export(
    state: &AppState,
    username: &str,
    only: Option<&str>,
    query: &HashMap<String, String>,
    request_id: &str,
) -> Response {
    let permission = match only {
        None => "manage_gateway",
        Some("apis") => "manage_apis",
        Some("endpoints") => "manage_endpoints",
        Some("roles") => "manage_roles",
        Some("groups") => "manage_groups",
        Some("routings") => "manage_routings",
        Some(_) => {
            return error(StatusCode::NOT_FOUND, "CFG404", "Configuration export not found", request_id);
        }
    };
    if !has_permission(state, username, permission).await {
        return error(
            StatusCode::FORBIDDEN,
            "CFG001",
            "Insufficient permissions",
            request_id,
        );
    }
    let Some(storage) = &state.storage else {
        return unexpected(request_id);
    };
    if let Some("apis") = only {
        if let Some(api_name) = query.get("api_name") {
            let api_version = query
                .get("api_version")
                .cloned()
                .unwrap_or_else(|| "v1".to_owned());
            let filter = json!({"api_name": api_name, "api_version": api_version});
            let api = storage.find_one("apis", &filter).await.ok().flatten();
            if let Some(api) = api {
                let endpoints = storage
                    .find_many("endpoints", &filter)
                    .await
                    .unwrap_or_default()
                    .into_iter()
                    .map(strip_internal)
                    .collect::<Vec<_>>();
                return success(
                    StatusCode::OK,
                    json!({
                        "api": strip_internal(api),
                        "endpoints": endpoints
                    }),
                    request_id,
                );
            } else {
                return error(StatusCode::NOT_FOUND, "CFG404", "API not found", request_id);
            }
        }
    }
    if let Some(collection) = only {
        let values = storage
            .find_many(collection, &json!({}))
            .await
            .unwrap_or_default()
            .into_iter()
            .map(strip_internal)
            .collect::<Vec<_>>();
        return success(StatusCode::OK, json!({collection: values}), request_id);
    }
    let mut output = Map::new();
    for collection in ["apis", "endpoints", "roles", "groups", "routings"] {
        output.insert(
            collection.to_owned(),
            json!(
                storage
                    .find_many(collection, &json!({}))
                    .await
                    .unwrap_or_default()
                    .into_iter()
                    .map(strip_internal)
                    .collect::<Vec<_>>()
            ),
        );
    }
    success(StatusCode::OK, Value::Object(output), request_id)
}

async fn config_import(
    state: &AppState,
    username: &str,
    payload: Value,
    request_id: &str,
) -> Response {
    if !has_permission(state, username, "manage_gateway").await {
        return error(
            StatusCode::FORBIDDEN,
            "CFG001",
            "Insufficient permissions",
            request_id,
        );
    }
    let Some(storage) = &state.storage else {
        return unexpected(request_id);
    };
    let mut previous = Map::new();
    for collection in ["apis", "endpoints", "roles", "groups", "routings"] {
        previous.insert(
            collection.to_owned(),
            json!(
                storage
                    .find_many(collection, &json!({}))
                    .await
                    .unwrap_or_default()
            ),
        );
    }
    if storage
        .insert_one(
            "config_snapshots",
            json!({
                "snapshot_id": Uuid::new_v4().to_string(),
                "created_at": timestamp_now(),
                "actor": username,
                "data": previous
            }),
        )
        .await
        .is_err()
    {
        return unexpected(request_id);
    }
    let mut imported = Map::new();
    for collection in ["apis", "endpoints", "roles", "groups", "routings"] {
        if let Some(values) = payload.get(collection).and_then(Value::as_array) {
            if storage
                .replace_collection(collection, values.clone())
                .await
                .is_err()
            {
                return unexpected(request_id);
            }
            imported.insert(collection.to_owned(), json!(values.len()));
        } else {
            imported.insert(collection.to_owned(), json!(0));
        }
    }
    success(StatusCode::OK, json!({"imported": imported}), request_id)
}

async fn config_rollback(state: &AppState, username: &str, request_id: &str) -> Response {
    if !has_permission(state, username, "manage_gateway").await {
        return error(
            StatusCode::FORBIDDEN,
            "CFG006",
            "Insufficient permissions",
            request_id,
        );
    }
    let Some(storage) = &state.storage else {
        return unexpected(request_id);
    };
    let Some(snapshot) = storage
        .find_many("config_snapshots", &json!({}))
        .await
        .unwrap_or_default()
        .into_iter()
        .last()
    else {
        return error(
            StatusCode::BAD_REQUEST,
            "CFG007",
            "No configuration snapshot available",
            request_id,
        );
    };
    let Some(data) = snapshot.get("data") else {
        return error(
            StatusCode::BAD_REQUEST,
            "CFG007",
            "Configuration snapshot is invalid",
            request_id,
        );
    };
    for collection in ["apis", "endpoints", "roles", "groups", "routings"] {
        let values = data
            .get(collection)
            .and_then(Value::as_array)
            .cloned()
            .unwrap_or_default();
        if storage
            .replace_collection(collection, values)
            .await
            .is_err()
        {
            return unexpected(request_id);
        }
    }
    let restored_to = snapshot.get("created_at").cloned().unwrap_or(Value::Null);
    success(
        StatusCode::OK,
        json!({"message": format!("Configuration rolled back to {}", restored_to.as_str().unwrap_or("latest")), "restored_to": restored_to}),
        request_id,
    )
}

async fn analytics_detail(
    state: &AppState,
    username: &str,
    kind: &str,
    key: &str,
    query: &HashMap<String, String>,
    request_id: &str,
) -> Response {
    if !has_permission(state, username, "view_analytics").await {
        return analytics_denied(request_id);
    }
    let (start_ts, end_ts) = analytics_time_range(query);
    let analytics = global_analytics();
    if kind == "api" {
        let (api_name, version) = key.split_once('/').unwrap_or((key, ""));
        let api_key = format!("rest:{api_name}");
        let entry = analytics
            .get_top_apis(analytics.api_count())
            .into_iter()
            .find(|entry| entry.name == api_key);
        let Some(entry) = entry else {
            return error(
                StatusCode::NOT_FOUND,
                "ANALYTICS404",
                &format!("No data found for API: {api_name}/{version}"),
                request_id,
            );
        };
        let endpoint_prefix = format!("/{api_name}/{version}");
        let gateway_prefix = format!("/api/rest/{api_name}/{version}");
        let endpoints = analytics
            .get_top_endpoints(analytics.endpoint_count())
            .iter()
            .filter(|endpoint| {
                endpoint.name.starts_with(&endpoint_prefix)
                    || endpoint.name.starts_with(&gateway_prefix)
            })
            .map(analytics_endpoint)
            .collect::<Vec<_>>();
        return success(
            StatusCode::OK,
            json!({
                "api_name": api_name,
                "version": version,
                "time_range": {"start_ts": start_ts, "end_ts": end_ts},
                "summary": analytics_entity(&entry, "api"),
                "endpoints": endpoints
            }),
            request_id,
        );
    }

    let entry = analytics
        .get_top_users(analytics.user_count())
        .into_iter()
        .find(|entry| entry.name == key);
    let Some(entry) = entry else {
        return error(
            StatusCode::NOT_FOUND,
            "ANALYTICS404",
            &format!("No data found for user: {key}"),
            request_id,
        );
    };
    success(
        StatusCode::OK,
        json!({
            "username": key,
            "time_range": {"start_ts": start_ts, "end_ts": end_ts},
            "summary": analytics_entity(&entry, "user")
        }),
        request_id,
    )
}

fn config_current(state: &AppState, request_id: &str) -> Response {
    success(
        StatusCode::OK,
        json!({
            "config": state.hot_reload.dump(),
            "source": "Environment variables override config file values",
            "reload_command": "kill -HUP $(cat doorman.pid)"
        }),
        request_id,
    )
}

fn reloadable_keys() -> Value {
    json!([
        {
            "key": "LOG_LEVEL",
            "description": "Log level (DEBUG, INFO, WARNING, ERROR)",
            "example": "INFO"
        },
        {"key": "LOG_FORMAT", "description": "Log format (json, text)", "example": "json"},
        {"key": "LOG_FILE", "description": "Log file path", "example": "logs/doorman.log"},
        {"key": "GATEWAY_TIMEOUT", "description": "Gateway timeout in seconds", "example": "30"},
        {"key": "UPSTREAM_TIMEOUT", "description": "Upstream timeout in seconds", "example": "30"},
        {"key": "CONNECTION_TIMEOUT", "description": "Connection timeout in seconds", "example": "10"},
        {"key": "RATE_LIMIT_ENABLED", "description": "Enable rate limiting", "example": "true"},
        {"key": "RATE_LIMIT_REQUESTS", "description": "Requests per window", "example": "100"},
        {"key": "RATE_LIMIT_WINDOW", "description": "Window size in seconds", "example": "60"},
        {"key": "CACHE_TTL", "description": "Cache TTL in seconds", "example": "300"},
        {"key": "CACHE_MAX_SIZE", "description": "Maximum cache entries", "example": "1000"},
        {"key": "CIRCUIT_BREAKER_ENABLED", "description": "Enable circuit breaker", "example": "true"},
        {"key": "CIRCUIT_BREAKER_THRESHOLD", "description": "Failures before opening", "example": "5"},
        {"key": "CIRCUIT_BREAKER_TIMEOUT", "description": "Timeout before retry (seconds)", "example": "60"},
        {"key": "RETRY_ENABLED", "description": "Enable retry logic", "example": "true"},
        {"key": "RETRY_MAX_ATTEMPTS", "description": "Maximum retry attempts", "example": "3"},
        {"key": "RETRY_BACKOFF", "description": "Backoff multiplier", "example": "1.0"},
        {"key": "METRICS_ENABLED", "description": "Enable metrics collection", "example": "true"},
        {"key": "METRICS_INTERVAL", "description": "Metrics interval (seconds)", "example": "60"},
        {"key": "FEATURE_REQUEST_REPLAY", "description": "Enable request replay", "example": "false"},
        {"key": "FEATURE_AB_TESTING", "description": "Enable A/B testing", "example": "false"},
        {"key": "FEATURE_COST_ANALYTICS", "description": "Enable cost analytics", "example": "false"}
    ])
}

async fn demo_seed(state: &AppState, username: &str, request_id: &str) -> Response {
    if username != "admin" {
        return error(
            StatusCode::FORBIDDEN,
            "AUTH006",
            "Admin access required",
            request_id,
        );
    }
    let Some(storage) = &state.storage else {
        return unexpected(request_id);
    };
    if !storage.is_memory() {
        return error(
            StatusCode::BAD_REQUEST,
            "DEMO001",
            "Demo seed is available only in memory mode",
            request_id,
        );
    }
    for (name, version, server) in [
        ("customers", "v1", "http://localhost:8080"),
        ("orders", "v1", "http://localhost:8081"),
        ("weather", "v1", "http://localhost:8082"),
    ] {
        if storage
            .find_one("apis", &json!({"api_name": name, "api_version": version}))
            .await
            .ok()
            .flatten()
            .is_none()
        {
            let _ = storage.insert_one("apis", json!({"api_name": name, "api_version": version, "api_id": Uuid::new_v4().to_string(), "api_path": format!("/{name}/{version}"), "api_servers": [server], "api_type": "REST", "api_public": false, "api_auth_required": true, "active": true})).await;
            let _ = storage.insert_one("endpoints", json!({"api_name": name, "api_version": version, "endpoint_id": Uuid::new_v4().to_string(), "endpoint_method": "GET", "endpoint_uri": "/status", "client_uri": "/status", "endpoint_description": "Demo status"})).await;
        }
    }
    message(StatusCode::OK, "Demo data seeded successfully", request_id)
}

fn cors_check(payload: Value, request_id: &str) -> Response {
    let origin = payload
        .get("origin")
        .and_then(Value::as_str)
        .unwrap_or("")
        .trim()
        .to_owned();
    let method = payload
        .get("method")
        .and_then(Value::as_str)
        .unwrap_or("")
        .trim()
        .to_uppercase();
    let request_headers: Vec<String> = payload
        .get("request_headers")
        .and_then(Value::as_array)
        .map(|arr| {
            arr.iter()
                .filter_map(Value::as_str)
                .map(|s| s.trim().to_owned())
                .filter(|s| !s.is_empty())
                .collect()
        })
        .unwrap_or_default();
    let cors_strict = env_bool("CORS_STRICT", true);

    let allowed_origins_str =
        env::var("ALLOWED_ORIGINS").unwrap_or_else(|_| "http://localhost:3000".to_owned());
    let origins: Vec<String> = allowed_origins_str
        .split(',')
        .map(|s| s.trim().to_owned())
        .collect();
    let allow_credentials = env_bool("ALLOW_CREDENTIALS", false);
    let methods: Vec<String> = env::var("ALLOW_METHODS")
        .unwrap_or_else(|_| "GET,POST,PUT,DELETE,PATCH,HEAD,OPTIONS".to_owned())
        .split(',')
        .map(|s| s.trim().to_owned())
        .collect();
    let headers: Vec<String> = env::var("ALLOW_HEADERS")
        .unwrap_or_else(|_| "Accept,Content-Type,X-CSRF-Token,Authorization".to_owned())
        .split(',')
        .map(|s| s.trim().to_owned())
        .collect();

    let safe_origins: Vec<String> = origins.iter().filter(|o| *o != "*").cloned().collect();
    let with_credentials = payload
        .get("with_credentials")
        .and_then(Value::as_bool)
        .unwrap_or(allow_credentials);

    let origin_allowed =
        safe_origins.contains(&origin) || (!cors_strict && origins.iter().any(|o| o == "*"));
    let method_allowed = methods.iter().any(|m| m.eq_ignore_ascii_case(&method));
    let allowed_headers_lower: Vec<String> = headers.iter().map(|h| h.to_lowercase()).collect();
    let not_allowed_headers: Vec<String> = request_headers
        .iter()
        .filter(|h| !allowed_headers_lower.contains(&h.to_lowercase()))
        .cloned()
        .collect();
    let headers_allowed = not_allowed_headers.is_empty();
    let preflight_allowed = origin_allowed && method_allowed && headers_allowed;

    let mut notes: Vec<String> = Vec::new();
    if allow_credentials && origins.iter().any(|o| o == "*") && !cors_strict {
        notes.push("Wildcard origins with credentials can be rejected by browsers; prefer explicit origins or set CORS_STRICT=true.".into());
    }
    if !origin_allowed {
        notes.push("Origin is not allowed based on current configuration.".into());
    }
    if !method_allowed {
        notes.push("Requested method is not in ALLOW_METHODS.".into());
    }
    if !headers_allowed {
        notes.push(format!(
            "Some requested headers are not allowed: {}",
            not_allowed_headers.join(", ")
        ));
    }

    let preflight_headers = json!({
        "Access-Control-Allow-Origin": if origin_allowed { &origin } else { "" },
        "Access-Control-Allow-Methods": methods.join(", "),
        "Access-Control-Allow-Headers": headers.join(", "),
        "Access-Control-Allow-Credentials": if with_credentials && allow_credentials { "true" } else { "false" },
        "Vary": "Origin",
    });
    let actual_headers = json!({
        "Access-Control-Allow-Origin": if origin_allowed { &origin } else { "" },
        "Access-Control-Allow-Credentials": if with_credentials && allow_credentials { "true" } else { "false" },
        "Vary": "Origin",
    });

    success(
        StatusCode::OK,
        json!({
            "config": {
                "allowed_origins": origins,
                "effective_allowed_origins": safe_origins,
                "allow_credentials": allow_credentials,
                "allow_methods": methods,
                "allow_headers": headers,
                "cors_strict": cors_strict,
            },
            "input": {
                "origin": origin,
                "method": method,
                "request_headers": request_headers,
                "request_headers_normalized": request_headers.iter().map(|h| h.to_lowercase()).collect::<Vec<_>>(),
                "with_credentials": with_credentials,
            },
            "preflight": {
                "allowed": preflight_allowed,
                "allow_origin": origin_allowed,
                "method_allowed": method_allowed,
                "headers_allowed": headers_allowed,
                "not_allowed_headers": not_allowed_headers,
                "response_headers": preflight_headers,
            },
            "actual": {
                "allowed": origin_allowed,
                "response_headers": actual_headers,
            },
            "notes": notes,
        }),
        request_id,
    )
}

async fn subscription_routes(
    state: &AppState,
    path: &str,
    method: &Method,
    payload: Value,
    username: &str,
    request_id: &str,
) -> Response {
    let Some(storage) = &state.storage else {
        return unexpected(request_id);
    };
    if method == Method::GET && path.starts_with("/subscription/available-apis/") {
        let target = path.trim_start_matches("/subscription/available-apis/");
        if target != username && !has_permission(state, username, "manage_subscriptions").await {
            return error(
                StatusCode::FORBIDDEN,
                "SUB011",
                "You do not have permission to view another user's APIs",
                request_id,
            );
        }
        let apis = storage
            .find_many("apis", &json!({}))
            .await
            .unwrap_or_default()
            .into_iter()
            .map(|api| {
                json!({
                    "api_name": api.get("api_name"),
                    "api_version": api.get("api_version"),
                    "api_description": api.get("api_description")
                })
            })
            .collect::<Vec<_>>();
        return success(StatusCode::OK, json!({"apis": apis}), request_id);
    }
    if method == Method::GET && path.starts_with("/subscription/subscriptions") {
        let target = path
            .strip_prefix("/subscription/subscriptions/")
            .filter(|value| !value.is_empty())
            .unwrap_or(username);
        if target != username && !has_permission(state, username, "manage_subscriptions").await {
            return error(
                StatusCode::FORBIDDEN,
                "SUB011",
                "You do not have permission to view another user's subscriptions",
                request_id,
            );
        }
        let apis = storage
            .find_one("subscriptions", &json!({"username": target}))
            .await
            .ok()
            .flatten()
            .and_then(|doc| doc.get("apis").cloned())
            .unwrap_or_else(|| json!([]));
        return success(
            StatusCode::OK,
            json!({"apis": apis, "subscriptions": {"apis": apis}}),
            request_id,
        );
    }
    let operation = if method == Method::POST && path.ends_with("/subscribe") {
        Some(true)
    } else if method == Method::POST && path.ends_with("/unsubscribe") {
        Some(false)
    } else {
        None
    };
    if let Some(subscribe) = operation {
        let target = payload
            .get("username")
            .and_then(Value::as_str)
            .unwrap_or(username);
        if target != username && !has_permission(state, username, "manage_subscriptions").await {
            return error(
                StatusCode::FORBIDDEN,
                if subscribe { "SUB009" } else { "SUB010" },
                "Insufficient permissions",
                request_id,
            );
        }
        let api_name = payload
            .get("api_name")
            .and_then(Value::as_str)
            .unwrap_or("");
        let api_version = payload
            .get("api_version")
            .and_then(Value::as_str)
            .unwrap_or("");
        if storage
            .find_one(
                "apis",
                &json!({"api_name": api_name, "api_version": api_version}),
            )
            .await
            .ok()
            .flatten()
            .is_none()
        {
            return error(
                StatusCode::NOT_FOUND,
                if subscribe { "SUB003" } else { "SUB005" },
                "API does not exist for the requested name and version",
                request_id,
            );
        }
        let api = format!("{api_name}/{api_version}");
        let existing = storage
            .find_one("subscriptions", &json!({"username": target}))
            .await
            .ok()
            .flatten();
        let mut apis = existing
            .as_ref()
            .and_then(|doc| doc.get("apis"))
            .and_then(Value::as_array)
            .cloned()
            .unwrap_or_default();
        let present = apis.iter().any(|value| value.as_str() == Some(&api));
        if subscribe && present {
            return error(
                StatusCode::BAD_REQUEST,
                "SUB004",
                "User is already subscribed to the API",
                request_id,
            );
        }
        if !subscribe && !present {
            return error(
                StatusCode::BAD_REQUEST,
                "SUB006",
                "User is not subscribed to the API",
                request_id,
            );
        }
        if subscribe {
            apis.push(json!(api));
        } else {
            apis.retain(|value| value.as_str() != Some(&api));
        }
        let result = if existing.is_some() {
            storage
                .update_one(
                    "subscriptions",
                    &json!({"username": target}),
                    &json!({"apis": apis}),
                )
                .await
                .map(|_| ())
        } else {
            storage
                .insert_one("subscriptions", json!({"username": target, "apis": apis}))
                .await
                .map(|_| ())
        };
        return match result {
            Ok(()) => message(
                StatusCode::OK,
                if subscribe {
                    "Successfully subscribed to the API"
                } else {
                    "Successfully unsubscribed from the API"
                },
                request_id,
            ),
            Err(_) => unexpected(request_id),
        };
    }
    error(
        StatusCode::NOT_FOUND,
        "GTW003",
        "Platform route does not exist",
        request_id,
    )
}

async fn credit_routes(
    state: &AppState,
    path: &str,
    method: &Method,
    payload: Value,
    username: &str,
    request_id: &str,
) -> Response {
    let Some(storage) = &state.storage else {
        return unexpected(request_id);
    };
    let suffix = path.strip_prefix("/credit").unwrap_or("").trim_matches('/');
    if method == Method::POST && suffix == "rotate-key" {
        let Some(group) = payload.get("api_credit_group").and_then(Value::as_str) else {
            return error(
                StatusCode::BAD_REQUEST,
                "CRD020",
                "api_credit_group is required",
                request_id,
            );
        };
        let Some(mut credits) = storage
            .find_one("user_credits", &json!({"username": username}))
            .await
            .ok()
            .flatten()
        else {
            return error(
                StatusCode::NOT_FOUND,
                "CRD005",
                "Credits not found",
                request_id,
            );
        };
        let key = Uuid::new_v4().to_string().replace('-', "");
        credits["users_credits"][group]["api_key"] = json!(key);
        return match storage
            .update_one("user_credits", &json!({"username": username}), &credits)
            .await
        {
            Ok(Some(_)) => success(StatusCode::OK, json!({"api_key": key}), request_id),
            _ => unexpected(request_id),
        };
    }
    if method == Method::GET && (suffix == "defs" || suffix.is_empty()) {
        let values = storage
            .find_many("credit_defs", &json!({}))
            .await
            .unwrap_or_default()
            .into_iter()
            .map(strip_internal)
            .collect::<Vec<_>>();
        return success(StatusCode::OK, json!(values), request_id);
    }
    if method == Method::GET && suffix == "all" {
        if !has_permission(state, username, "manage_credits").await {
            return error(
                StatusCode::FORBIDDEN,
                "CRD002",
                "Unable to retrieve credits for all users",
                request_id,
            );
        }
        let values = storage
            .find_many("user_credits", &json!({}))
            .await
            .unwrap_or_default()
            .into_iter()
            .map(strip_internal)
            .collect::<Vec<_>>();
        return success(StatusCode::OK, json!(values), request_id);
    }
    if method == Method::POST && suffix.is_empty() {
        if !has_permission(state, username, "manage_credits").await {
            return error(
                StatusCode::FORBIDDEN,
                "CRD001",
                "You do not have permission to manage credits",
                request_id,
            );
        }
        let group = payload
            .get("api_credit_group")
            .and_then(Value::as_str)
            .unwrap_or("");
        if storage
            .find_one("credit_defs", &json!({"api_credit_group": group}))
            .await
            .ok()
            .flatten()
            .is_some()
        {
            return error(
                StatusCode::BAD_REQUEST,
                "CRD004",
                "Credit definition already exists",
                request_id,
            );
        }
        return match storage.insert_one("credit_defs", payload).await {
            Ok(_) => message(
                StatusCode::CREATED,
                "Credit definition created successfully",
                request_id,
            ),
            Err(_) => unexpected(request_id),
        };
    }
    if let Some(group) = suffix.strip_prefix("defs/") {
        let filter = json!({"api_credit_group": group});
        if method == Method::GET {
            return match storage.find_one("credit_defs", &filter).await {
                Ok(Some(value)) => success(StatusCode::OK, strip_internal(value), request_id),
                _ => error(
                    StatusCode::NOT_FOUND,
                    "CRD002",
                    "Credit definition not found",
                    request_id,
                ),
            };
        }
    }
    if method == Method::PUT || method == Method::DELETE {
        if !has_permission(state, username, "manage_credits").await {
            return error(
                StatusCode::FORBIDDEN,
                "CRD001",
                "You do not have permission to manage credits",
                request_id,
            );
        }
        let filter = json!({"api_credit_group": suffix});
        if method == Method::PUT {
            return match storage.update_one("credit_defs", &filter, &payload).await {
                Ok(Some(_)) => message(
                    StatusCode::OK,
                    "Credit definition updated successfully",
                    request_id,
                ),
                _ => error(
                    StatusCode::NOT_FOUND,
                    "CRD002",
                    "Credit definition not found",
                    request_id,
                ),
            };
        }
        return match storage.delete_one("credit_defs", &filter).await {
            Ok(true) => message(
                StatusCode::OK,
                "Credit definition deleted successfully",
                request_id,
            ),
            _ => error(
                StatusCode::NOT_FOUND,
                "CRD002",
                "Credit definition not found",
                request_id,
            ),
        };
    }
    if method == Method::POST && !suffix.is_empty() {
        if !has_permission(state, username, "manage_credits").await {
            return error(
                StatusCode::FORBIDDEN,
                "CRD001",
                "You do not have permission to manage credits",
                request_id,
            );
        }
        let mut value = payload;
        value["username"] = json!(suffix);
        let existing = storage
            .find_one("user_credits", &json!({"username": suffix}))
            .await
            .ok()
            .flatten();
        let result = if existing.is_some() {
            storage
                .update_one("user_credits", &json!({"username": suffix}), &value)
                .await
                .map(|_| ())
        } else {
            storage.insert_one("user_credits", value).await.map(|_| ())
        };
        return match result {
            Ok(()) => message(StatusCode::OK, "Credits saved successfully", request_id),
            Err(_) => unexpected(request_id),
        };
    }
    if method == Method::GET && !suffix.is_empty() {
        if suffix != username && !has_permission(state, username, "manage_credits").await {
            return error(
                StatusCode::FORBIDDEN,
                "CRD003",
                "Unable to retrieve credits for user",
                request_id,
            );
        }
        return match storage
            .find_one("user_credits", &json!({"username": suffix}))
            .await
        {
            Ok(Some(value)) => success(StatusCode::OK, strip_internal(value), request_id),
            _ => error(
                StatusCode::NOT_FOUND,
                "CRD005",
                "Credits not found",
                request_id,
            ),
        };
    }
    error(
        StatusCode::NOT_FOUND,
        "GTW003",
        "Platform route does not exist",
        request_id,
    )
}

async fn vault_routes(
    state: &AppState,
    path: &str,
    method: &Method,
    payload: Value,
    username: &str,
    request_id: &str,
) -> Response {
    let Some(storage) = &state.storage else {
        return unexpected(request_id);
    };
    let key = path.strip_prefix("/vault").unwrap_or("").trim_matches('/');
    if method == Method::GET && key.is_empty() {
        let entries = storage
            .find_many("vault_entries", &json!({"username": username}))
            .await
            .unwrap_or_default()
            .into_iter()
            .map(clean_vault_entry)
            .collect::<Vec<_>>();
        return success(
            StatusCode::OK,
            json!({"entries": entries, "count": entries.len()}),
            request_id,
        );
    }
    if method == Method::POST && key.is_empty() {
        let key_name = payload
            .get("key_name")
            .and_then(Value::as_str)
            .unwrap_or("");
        let value = payload.get("value").and_then(Value::as_str).unwrap_or("");
        if key_name.is_empty() || value.is_empty() {
            return error(
                StatusCode::BAD_REQUEST,
                "VAULT003",
                "key_name and value are required",
                request_id,
            );
        }
        if storage
            .find_one(
                "vault_entries",
                &json!({"username": username, "key_name": key_name}),
            )
            .await
            .ok()
            .flatten()
            .is_some()
        {
            return error(
                StatusCode::CONFLICT,
                "VAULT004",
                &format!("Vault entry with key_name \"{key_name}\" already exists"),
                request_id,
            );
        }
        let Some(user) = storage
            .find_one("users", &json!({"username": username}))
            .await
            .ok()
            .flatten()
        else {
            return error(
                StatusCode::NOT_FOUND,
                "VAULT002",
                "User not found",
                request_id,
            );
        };
        let Some(email) = user.get("email").and_then(Value::as_str) else {
            return error(
                StatusCode::BAD_REQUEST,
                "VAULT003",
                "User email is required for vault encryption",
                request_id,
            );
        };
        let encrypted_value = match crate::storage::vault::encrypt(value, email, username) {
            Ok(value) => value,
            Err(crate::storage::vault::VaultError::MissingKey) => {
                return error(
                    StatusCode::INTERNAL_SERVER_ERROR,
                    "VAULT001",
                    "Vault encryption is not configured. Set VAULT_KEY in environment variables.",
                    request_id,
                );
            }
            Err(_) => {
                return error(
                    StatusCode::INTERNAL_SERVER_ERROR,
                    "VAULT005",
                    "Failed to encrypt vault value",
                    request_id,
                );
            }
        };
        let now = unix_seconds().to_string();
        let entry = json!({"username": username, "key_name": key_name, "encrypted_value": encrypted_value, "description": payload.get("description").cloned().unwrap_or(Value::Null), "created_at": now, "updated_at": now});
        return match storage.insert_one("vault_entries", entry).await {
            Ok(_) => message(
                StatusCode::CREATED,
                "Vault entry created successfully",
                request_id,
            ),
            Err(_) => unexpected(request_id),
        };
    }
    if !key.is_empty() {
        let filter = json!({"username": username, "key_name": key});
        if method == Method::GET {
            return match storage.find_one("vault_entries", &filter).await {
                Ok(Some(entry)) => success(StatusCode::OK, clean_vault_entry(entry), request_id),
                _ => error(
                    StatusCode::NOT_FOUND,
                    "VAULT007",
                    "Vault entry not found",
                    request_id,
                ),
            };
        }
        if method == Method::PUT {
            let update = json!({"description": payload.get("description").cloned().unwrap_or(Value::Null), "updated_at": unix_seconds().to_string()});
            return match storage.update_one("vault_entries", &filter, &update).await {
                Ok(Some(_)) => message(
                    StatusCode::OK,
                    "Vault entry updated successfully",
                    request_id,
                ),
                _ => error(
                    StatusCode::NOT_FOUND,
                    "VAULT007",
                    "Vault entry not found",
                    request_id,
                ),
            };
        }
        if method == Method::DELETE {
            return match storage.delete_one("vault_entries", &filter).await {
                Ok(true) => message(
                    StatusCode::OK,
                    "Vault entry deleted successfully",
                    request_id,
                ),
                _ => error(
                    StatusCode::NOT_FOUND,
                    "VAULT007",
                    "Vault entry not found",
                    request_id,
                ),
            };
        }
    }
    error(
        StatusCode::NOT_FOUND,
        "GTW003",
        "Platform route does not exist",
        request_id,
    )
}

fn clean_vault_entry(mut entry: Value) -> Value {
    if let Some(map) = entry.as_object_mut() {
        map.remove("_id");
        map.remove("encrypted_value");
        map.remove("value");
    }
    entry
}

async fn quota_routes(
    state: &AppState,
    path: &str,
    method: &Method,
    username: &str,
    request_id: &str,
) -> Response {
    let Some(storage) = &state.storage else {
        return unexpected(request_id);
    };
    let assignment = storage
        .find_one("user_tier_assignments", &json!({"user_id": username}))
        .await
        .ok()
        .flatten();
    let tier = if let Some(tier_id) = assignment.as_ref().and_then(|doc| doc.get("tier_id")) {
        storage
            .find_one("tiers", &json!({"tier_id": tier_id}))
            .await
            .ok()
            .flatten()
    } else {
        None
    };
    if path == "/quota/usage/history" && method == Method::GET {
        return success(
            StatusCode::OK,
            json!({"user_id": username, "history": [], "note": "Historical tracking not yet fully implemented"}),
            request_id,
        );
    }
    if path == "/quota/usage/export" && method == Method::POST {
        return success(
            StatusCode::OK,
            json!({"user_id": username, "export_date": timestamp_now(), "quotas": quota_values(tier.as_ref())}),
            request_id,
        );
    }
    if path == "/quota/tier/info" && method == Method::GET {
        return match tier {
            Some(value) => success(StatusCode::OK, strip_internal(value), request_id),
            None => error(
                StatusCode::NOT_FOUND,
                "QUOTA404",
                "No tier found for user",
                request_id,
            ),
        };
    }
    if path == "/quota/burst/status" && method == Method::GET {
        let enabled = tier
            .as_ref()
            .and_then(|value| value.get("burst_enabled"))
            .and_then(Value::as_bool)
            .unwrap_or(false);
        let limit = tier
            .as_ref()
            .and_then(|value| value.get("burst_limit"))
            .cloned()
            .unwrap_or(json!(0));
        return success(
            StatusCode::OK,
            json!({"enabled": enabled, "limit": limit, "current_usage": 0, "remaining": limit}),
            request_id,
        );
    }
    if path == "/quota/status" && method == Method::GET {
        return success(
            StatusCode::OK,
            json!({"user_id": username, "quotas": quota_values(tier.as_ref())}),
            request_id,
        );
    }
    if let Some(quota_type) = path.strip_prefix("/quota/status/")
        && method == Method::GET
    {
        let field = match quota_type {
            "monthly_requests" => "monthly_request_quota",
            "daily_requests" => "daily_request_quota",
            "monthly_bandwidth" => "monthly_bandwidth_quota",
            _ => {
                return error(
                    StatusCode::BAD_REQUEST,
                    "QUOTA001",
                    &format!("Invalid quota type: {quota_type}"),
                    request_id,
                );
            }
        };
        let Some(limit) = tier
            .as_ref()
            .and_then(|value| value.get(field))
            .and_then(Value::as_u64)
        else {
            return error(
                StatusCode::NOT_FOUND,
                "QUOTA404",
                "Quota not configured for user",
                request_id,
            );
        };
        return success(StatusCode::OK, quota_status(quota_type, limit), request_id);
    }
    error(
        StatusCode::NOT_FOUND,
        "GTW003",
        "Platform route does not exist",
        request_id,
    )
}

fn quota_values(tier: Option<&Value>) -> Vec<Value> {
    [
        ("monthly_requests", "monthly_request_quota"),
        ("daily_requests", "daily_request_quota"),
        ("monthly_bandwidth", "monthly_bandwidth_quota"),
    ]
    .into_iter()
    .filter_map(|(name, field)| {
        tier.and_then(|value| value.get(field))
            .and_then(Value::as_u64)
            .map(|limit| quota_status(name, limit))
    })
    .collect()
}

fn quota_status(name: &str, limit: u64) -> Value {
    json!({
        "quota_type": name,
        "current_usage": 0,
        "limit": limit,
        "remaining": limit,
        "percentage_used": 0.0,
        "reset_at": Value::Null,
        "is_warning": false,
        "is_critical": false,
        "is_exhausted": false
    })
}

async fn api_discovery_routes(
    state: &AppState,
    parts: &[&str],
    method: &Method,
    username: &str,
    request_id: &str,
) -> Response {
    let Some(storage) = &state.storage else {
        return unexpected(request_id);
    };
    let filter = json!({"api_name": parts[0], "api_version": parts[1]});
    let Some(api) = storage.find_one("apis", &filter).await.ok().flatten() else {
        return error(StatusCode::NOT_FOUND, "API003", "API not found", request_id);
    };
    let kind = parts[2];
    let action = parts.get(3).copied().unwrap_or("");
    if kind == "grpc" && action == "services" && method == Method::GET {
        use base64::Engine as _;
        let Some(raw) = api.get("api_grpc_descriptor_set").and_then(Value::as_str) else {
            return success(StatusCode::OK, json!({"services": []}), request_id);
        };
        let services = base64::engine::general_purpose::STANDARD.decode(raw).ok().and_then(|bytes| prost_reflect::DescriptorPool::decode(bytes.as_slice()).ok()).map(|pool| pool.services().map(|service| json!({"name": service.name(), "full_name": service.full_name(), "methods": service.methods().map(|method_value| method_value.name().to_owned()).collect::<Vec<_>>() })).collect::<Vec<_>>()).unwrap_or_default();
        return success(StatusCode::OK, json!({"services": services}), request_id);
    }
    if kind == "graphql" {
        let field = "api_graphql_schema";
        if action == "types" && method == Method::GET {
            let schema = api.get(field).cloned().unwrap_or(Value::Null);
            let types = schema
                .pointer("/data/__schema/types")
                .and_then(Value::as_array)
                .cloned()
                .unwrap_or_default();
            return success(StatusCode::OK, json!({"types": types}), request_id);
        }
        if method == Method::GET && action == "schema" {
            return success(
                StatusCode::OK,
                api.get(field).cloned().unwrap_or(Value::Null),
                request_id,
            );
        }
        if (parts.get(4) == Some(&"refresh") || action == "refresh") && method == Method::POST {
            if !has_permission(state, username, "manage_apis").await {
                return error(
                    StatusCode::FORBIDDEN,
                    "API008",
                    "Insufficient permissions",
                    request_id,
                );
            }
            let Some(server) = api
                .get("api_servers")
                .and_then(Value::as_array)
                .and_then(|items| items.first())
                .and_then(Value::as_str)
            else {
                return error(
                    StatusCode::BAD_REQUEST,
                    "API003",
                    "API server is not configured",
                    request_id,
                );
            };
            let path = api
                .get("api_graphql_schema_url")
                .and_then(Value::as_str)
                .unwrap_or("/graphql");
            let target = format!(
                "{}{}",
                server.trim_end_matches('/'),
                if path.starts_with('/') {
                    path.to_owned()
                } else {
                    format!("/{path}")
                }
            );
            let query = json!({"query": "query IntrospectionQuery { __schema { types { name kind } queryType { name } mutationType { name } } }"});
            return match state.proxy_client.post(target).json(&query).send().await {
                Ok(response) => match response.json::<Value>().await {
                    Ok(schema) => {
                        let _ = storage
                            .update_one("apis", &filter, &json!({field: schema.clone()}))
                            .await;
                        success(StatusCode::OK, schema, request_id)
                    }
                    Err(_) => error(
                        StatusCode::BAD_GATEWAY,
                        "GQL002",
                        "Invalid GraphQL schema response",
                        request_id,
                    ),
                },
                Err(_) => error(
                    StatusCode::BAD_GATEWAY,
                    "GQL001",
                    "Unable to fetch GraphQL schema",
                    request_id,
                ),
            };
        }
    }
    let (field, configured_url) = if kind == "openapi" {
        ("api_openapi_spec", "api_openapi_url")
    } else if kind == "wsdl" {
        ("api_wsdl_content", "api_wsdl_url")
    } else {
        return error(
            StatusCode::NOT_FOUND,
            "GTW003",
            "Platform route does not exist",
            request_id,
        );
    };
    if method == Method::GET && action.is_empty() {
        return match api.get(field) {
            Some(value) if !value.is_null() => success(StatusCode::OK, value.clone(), request_id),
            _ => error(
                StatusCode::NOT_FOUND,
                "API003",
                &format!("{} document not found", kind.to_ascii_uppercase()),
                request_id,
            ),
        };
    }
    if method == Method::POST && action == "refresh" {
        if !has_permission(state, username, "manage_apis").await {
            return error(
                StatusCode::FORBIDDEN,
                "API008",
                "Insufficient permissions",
                request_id,
            );
        }
        let Some(server) = api
            .get("api_servers")
            .and_then(Value::as_array)
            .and_then(|items| items.first())
            .and_then(Value::as_str)
        else {
            return error(
                StatusCode::BAD_REQUEST,
                "API003",
                "API server is not configured",
                request_id,
            );
        };
        let Some(path) = api.get(configured_url).and_then(Value::as_str) else {
            return error(
                StatusCode::BAD_REQUEST,
                "API003",
                "Discovery URL is not configured",
                request_id,
            );
        };
        let target = if path.starts_with("http://") || path.starts_with("https://") {
            path.to_owned()
        } else {
            format!(
                "{}{}",
                server.trim_end_matches('/'),
                if path.starts_with('/') {
                    path.to_owned()
                } else {
                    format!("/{path}")
                }
            )
        };
        return match state.proxy_client.get(target).send().await {
            Ok(response) if response.status().is_success() => match response.text().await {
                Ok(text) => {
                    let value = if kind == "openapi" {
                        serde_json::from_str(&text).unwrap_or_else(|_| json!({"raw": text}))
                    } else {
                        Value::String(text)
                    };
                    let _ = storage
                        .update_one("apis", &filter, &json!({field: value.clone()}))
                        .await;
                    success(StatusCode::OK, value, request_id)
                }
                Err(_) => error(
                    StatusCode::BAD_GATEWAY,
                    "API003",
                    "Invalid discovery response",
                    request_id,
                ),
            },
            _ => error(
                StatusCode::BAD_GATEWAY,
                "API003",
                "Unable to fetch discovery document",
                request_id,
            ),
        };
    }
    if method == Method::POST && action == "import" {
        if !has_permission(state, username, "manage_endpoints").await {
            return error(
                StatusCode::FORBIDDEN,
                "END010",
                "Insufficient permissions",
                request_id,
            );
        }
        let (candidates, service_name, operations_found) = if kind == "openapi" {
            (
                crate::routes::discovery::openapi_endpoints(api.get(field).unwrap_or(&Value::Null)),
                String::new(),
                0,
            )
        } else {
            let Some(content) = api.get(field).and_then(Value::as_str) else {
                return error(
                    StatusCode::NOT_FOUND,
                    "WSDL003",
                    "No WSDL available",
                    request_id,
                );
            };
            let parsed = match crate::routes::discovery::parse_wsdl(content) {
                Ok(parsed) => parsed,
                Err(message) => {
                    return error(StatusCode::BAD_REQUEST, "WSDL004", &message, request_id);
                }
            };
            let service_name = parsed
                .get("service_name")
                .and_then(Value::as_str)
                .unwrap_or("")
                .to_owned();
            let operations_found = parsed
                .get("operations")
                .and_then(Value::as_array)
                .map(Vec::len)
                .unwrap_or(0);
            (
                parsed
                    .get("endpoints")
                    .and_then(Value::as_array)
                    .cloned()
                    .unwrap_or_default(),
                service_name,
                operations_found,
            )
        };
        let endpoints_found = candidates.len();
        let mut imported = 0_u64;
        let mut skipped = 0_u64;
        for candidate in candidates {
            let uri = candidate
                .get("endpoint_uri")
                .or_else(|| candidate.get("uri"))
                .and_then(Value::as_str)
                .unwrap_or("");
            let verb = candidate
                .get("endpoint_method")
                .or_else(|| candidate.get("method"))
                .and_then(Value::as_str)
                .unwrap_or("POST")
                .to_ascii_uppercase();
            if uri.is_empty() {
                skipped += 1;
                continue;
            }
            let duplicate = storage
                .find_one(
                    "endpoints",
                    &json!({
                        "api_name": parts[0],
                        "api_version": parts[1],
                        "endpoint_method": &verb,
                        "endpoint_uri": uri,
                    }),
                )
                .await
                .ok()
                .flatten()
                .is_some();
            if duplicate {
                skipped += 1;
                continue;
            }
            let endpoint = json!({
                "api_name": parts[0],
                "api_version": parts[1],
                "api_id": api.get("api_id").cloned().unwrap_or(Value::Null),
                "endpoint_id": Uuid::new_v4().to_string(),
                "endpoint_method": verb,
                "endpoint_uri": uri,
                "client_uri": uri,
                "endpoint_description": candidate.get("endpoint_description").or_else(|| candidate.get("description")).and_then(Value::as_str).unwrap_or(""),
                "endpoint_soap_action": candidate.get("soap_action").cloned().unwrap_or(Value::String(String::new())),
            });
            if storage.insert_one("endpoints", endpoint).await.is_ok() {
                imported += 1;
            } else {
                skipped += 1;
            }
        }
        return if kind == "openapi" {
            success(
                StatusCode::OK,
                json!({
                    "message": "OpenAPI import completed",
                    "endpoints_found": endpoints_found,
                    "endpoints_imported": imported,
                    "endpoints_skipped": skipped,
                }),
                request_id,
            )
        } else {
            success(
                StatusCode::OK,
                json!({
                    "message": "WSDL import completed",
                    "service_name": service_name,
                    "operations_found": operations_found,
                    "endpoints_imported": imported,
                    "endpoints_skipped": skipped,
                }),
                request_id,
            )
        };
    }
    error(
        StatusCode::NOT_FOUND,
        "GTW003",
        "Platform route does not exist",
        request_id,
    )
}

async fn proto_routes(
    state: &AppState,
    path: &str,
    method: &Method,
    headers: &HeaderMap,
    body: &[u8],
    username: &str,
    request_id: &str,
) -> Response {
    if !has_permission(state, username, "manage_apis").await {
        return error(
            StatusCode::FORBIDDEN,
            "API008",
            "You do not have permission to manage proto files",
            request_id,
        );
    }
    let Some(storage) = &state.storage else {
        return unexpected(request_id);
    };
    if path == "/proto/descriptors/backfill" && method == Method::POST {
        let apis = storage
            .find_many("apis", &json!({}))
            .await
            .unwrap_or_default();
        let mut scanned = 0_u64;
        let mut updated = 0_u64;
        let mut skipped = 0_u64;
        let mut errors = Vec::new();
        for api in apis {
            let source = api.get("api_grpc_proto_source").and_then(Value::as_str);
            if source.is_none() {
                continue;
            }
            scanned += 1;
            if api
                .get("api_grpc_descriptor_set")
                .and_then(Value::as_str)
                .is_some()
            {
                skipped += 1;
                continue;
            }
            match compile_proto(source.unwrap()) {
                Ok((descriptor, digest)) => {
                    let filter = json!({"api_name": api.get("api_name"), "api_version": api.get("api_version")});
                    let _ = storage.update_one("apis", &filter, &json!({"api_grpc_descriptor_set": descriptor, "api_grpc_descriptor_sha256": digest})).await;
                    updated += 1;
                }
                Err(error_value) => {
                    errors.push(json!({"api": api.get("api_name"), "error": error_value}))
                }
            }
        }
        return success(
            StatusCode::OK,
            json!({"scanned": scanned, "updated": updated, "skipped": skipped, "missing": errors.len(), "errors": errors}),
            request_id,
        );
    }
    let parts = path
        .trim_start_matches("/proto/")
        .split('/')
        .collect::<Vec<_>>();
    if parts.len() != 2 {
        return error(StatusCode::NOT_FOUND, "API003", "API not found", request_id);
    }
    let filter = json!({"api_name": parts[0], "api_version": parts[1]});
    if method == Method::GET {
        let proto_record = storage
            .find_one("apis", &filter)
            .await
            .ok()
            .flatten()
            .or(storage
                .find_one("grpc_proto_uploads", &filter)
                .await
                .ok()
                .flatten());
        let Some(proto_record) = proto_record else {
            return error(StatusCode::NOT_FOUND, "API003", "API not found", request_id);
        };
        return match proto_record
            .get("api_grpc_proto_source")
            .and_then(Value::as_str)
        {
            Some(source) => success(StatusCode::OK, json!({"content": source}), request_id),
            None => error(
                StatusCode::NOT_FOUND,
                "API003",
                "Proto file not found",
                request_id,
            ),
        };
    }
    if method == Method::DELETE {
        let cleared_api = matches!(
            storage
                .update_one(
                    "apis",
                    &filter,
                    &json!({
                        "api_grpc_proto_source": "",
                        "api_grpc_descriptor_set": "",
                        "api_grpc_descriptor_sha256": ""
                    }),
                )
                .await,
            Ok(Some(_))
        );
        let cleared_pending = storage
            .delete_one("grpc_proto_uploads", &filter)
            .await
            .unwrap_or(false);
        return if cleared_api || cleared_pending {
            message(
                StatusCode::OK,
                "Proto file deleted successfully",
                request_id,
            )
        } else {
            error(
                StatusCode::NOT_FOUND,
                "API003",
                "Proto file not found",
                request_id,
            )
        };
    }
    if method == Method::POST || method == Method::PUT {
        let max_size = env::var("MAX_PROTO_SIZE_BYTES")
            .ok()
            .and_then(|value| value.parse::<usize>().ok())
            .unwrap_or(1024 * 1024);
        let source = match extract_proto_source(headers, body) {
            Ok(source) if source.len() <= max_size => source,
            Ok(_) => {
                return error(
                    StatusCode::PAYLOAD_TOO_LARGE,
                    "GTW013",
                    "File too large",
                    request_id,
                );
            }
            Err(error_value) => {
                return error(StatusCode::BAD_REQUEST, "REQ002", &error_value, request_id);
            }
        };
        if source.contains('`')
            || source.contains("$(")
            || !(source.contains("syntax")
                || source.contains("message")
                || source.contains("service"))
        {
            return error(
                StatusCode::BAD_REQUEST,
                "REQ002",
                "Invalid proto file",
                request_id,
            );
        }
        let (descriptor, digest) = match compile_proto(&source) {
            Ok(result) => result,
            Err(error_value) => {
                return error(
                    StatusCode::INTERNAL_SERVER_ERROR,
                    "API009",
                    &format!("Failed to generate gRPC descriptor: {error_value}"),
                    request_id,
                );
            }
        };
        let mut proto_map = serde_json::Map::new();
        proto_map.insert("api_grpc_proto_source".to_string(), json!(source));
        proto_map.insert("api_grpc_descriptor_set".to_string(), json!(descriptor));
        proto_map.insert("api_grpc_descriptor_sha256".to_string(), json!(digest));
        if let Some(pkg) = extract_proto_package(&source) {
            proto_map.insert("api_grpc_package".to_string(), json!(pkg));
        }
        let proto_fields = Value::Object(proto_map);
        let result = storage.update_one("apis", &filter, &proto_fields).await;
        return match result {
            Ok(Some(_)) => message(
                StatusCode::OK,
                "Proto file uploaded and gRPC code generated successfully",
                request_id,
            ),
            Ok(None) => {
                let pending_exists = storage
                    .find_one("grpc_proto_uploads", &filter)
                    .await
                    .ok()
                    .flatten()
                    .is_some();
                let saved = if pending_exists {
                    matches!(
                        storage
                            .update_one("grpc_proto_uploads", &filter, &proto_fields)
                            .await,
                        Ok(Some(_))
                    )
                } else {
                    let mut pending = filter.clone();
                    if let (Value::Object(base), Value::Object(proto)) =
                        (&mut pending, &proto_fields)
                    {
                        for (key, value) in proto {
                            base.insert(key.clone(), value.clone());
                        }
                    }
                    storage
                        .insert_one("grpc_proto_uploads", pending)
                        .await
                        .is_ok()
                };
                if saved {
                    message(
                        StatusCode::OK,
                        "Proto file uploaded and gRPC code generated successfully",
                        request_id,
                    )
                } else {
                    unexpected(request_id)
                }
            }
            Err(_) => unexpected(request_id),
        };
    }
    error(
        StatusCode::METHOD_NOT_ALLOWED,
        "GTW004",
        "Method not allowed",
        request_id,
    )
}

fn extract_proto_source(headers: &HeaderMap, body: &[u8]) -> Result<String, String> {
    let content_type = headers
        .get(header::CONTENT_TYPE)
        .and_then(|value| value.to_str().ok())
        .unwrap_or("");
    if !content_type.starts_with("multipart/form-data") {
        return String::from_utf8(body.to_vec()).map_err(|_| "Proto file must be UTF-8".to_owned());
    }
    let boundary = content_type
        .split("boundary=")
        .nth(1)
        .map(str::trim)
        .map(|value| value.trim_matches('"'))
        .ok_or_else(|| "Multipart boundary is missing".to_owned())?;
    let text =
        String::from_utf8(body.to_vec()).map_err(|_| "Proto file must be UTF-8".to_owned())?;
    if !text.to_ascii_lowercase().contains("filename=")
        || !text.to_ascii_lowercase().contains(".proto")
    {
        return Err("Only .proto files are allowed".to_owned());
    }
    let header_end = text
        .find("\r\n\r\n")
        .or_else(|| text.find("\n\n"))
        .ok_or_else(|| "Invalid multipart body".to_owned())?;
    let separator = if text[header_end..].starts_with("\r\n\r\n") {
        4
    } else {
        2
    };
    let content = &text[header_end + separator..];
    let marker = format!("\r\n--{boundary}");
    Ok(content
        .split(&marker)
        .next()
        .unwrap_or(content)
        .trim_end_matches(['\r', '\n'])
        .to_owned())
}

fn extract_proto_package(source: &str) -> Option<String> {
    for line in source.lines() {
        let trimmed = line.trim();
        if let Some(rest) = trimmed.strip_prefix("package") {
            let pkg = rest.trim().trim_matches(';').trim();
            if !pkg.is_empty()
                && pkg
                    .chars()
                    .all(|c| c.is_alphanumeric() || c == '_' || c == '.')
            {
                return Some(pkg.to_owned());
            }
        }
    }
    None
}

fn compile_proto(source: &str) -> Result<(String, String), String> {
    let directory = std::env::temp_dir().join(format!("doorman-proto-{}", Uuid::new_v4()));
    fs::create_dir_all(&directory).map_err(|error_value| error_value.to_string())?;
    let source_path = directory.join("api.proto");
    let descriptor_path = directory.join("api.descriptor.pb");
    fs::write(&source_path, source).map_err(|error_value| error_value.to_string())?;
    let protoc_res = std::panic::catch_unwind(protoc_bin_vendored::protoc_bin_path);
    let protoc = match protoc_res {
        Ok(Ok(path)) => path,
        _ => std::path::PathBuf::from("protoc"),
    };
    let mut cmd = Command::new(&protoc);
    cmd.arg(format!("--proto_path={}", directory.display()));
    if let Ok(Ok(includes)) = std::panic::catch_unwind(protoc_bin_vendored::include_path) {
        if includes.exists() {
            cmd.arg(format!("--proto_path={}", includes.display()));
        }
    }
    if std::path::Path::new("/usr/include").exists() {
        cmd.arg("--proto_path=/usr/include");
    }
    if std::path::Path::new("/usr/local/include").exists() {
        cmd.arg("--proto_path=/usr/local/include");
    }
    cmd.arg(format!(
        "--descriptor_set_out={}",
        descriptor_path.display()
    ))
    .arg("--include_imports")
    .arg(&source_path);

    let output = cmd
        .output()
        .map_err(|error_value| error_value.to_string())?;
    if !output.status.success() {
        let _ = fs::remove_dir_all(&directory);
        return Err(String::from_utf8_lossy(&output.stderr).trim().to_owned());
    }
    let bytes = fs::read(&descriptor_path).map_err(|error_value| error_value.to_string())?;
    let _ = fs::remove_dir_all(&directory);
    use base64::Engine as _;
    use sha2::Digest as _;
    Ok((
        base64::engine::general_purpose::STANDARD.encode(&bytes),
        format!("{:x}", sha2::Sha256::digest(&bytes)),
    ))
}

async fn logging_routes(
    state: &AppState,
    path: &str,
    method: &Method,
    username: &str,
    request_id: &str,
) -> Response {
    if method != Method::GET {
        return error(
            StatusCode::METHOD_NOT_ALLOWED,
            "GTW004",
            "Method not allowed",
            request_id,
        );
    }
    let export = matches!(path, "/logging/logs/export" | "/logging/logs/download");
    let permission = if export { "export_logs" } else { "view_logs" };
    if !has_permission(state, username, permission).await {
        let (code, message_text) = match path {
            "/logging/logs/export" => ("LOG003", "You do not have permission to export logs"),
            "/logging/logs/download" => ("LOG004", "You do not have permission to download logs"),
            _ => ("LOG001", "You do not have permission to view logs"),
        };
        return error(StatusCode::FORBIDDEN, code, message_text, request_id);
    }
    let directory = state
        .config
        .logs_dir
        .clone()
        .unwrap_or_else(|| std::path::PathBuf::from("platform-logs"));
    let files = fs::read_dir(&directory)
        .ok()
        .into_iter()
        .flatten()
        .filter_map(Result::ok)
        .filter(|entry| entry.path().is_file())
        .map(|entry| entry.file_name().to_string_lossy().into_owned())
        .collect::<Vec<_>>();
    match path {
        "/logging/logs/files" => {
            let count = files.len();
            success(
                StatusCode::OK,
                json!({"log_files": files, "count": count}),
                request_id,
            )
        }
        "/logging/logs/statistics" => {
            success(StatusCode::OK, json!({"files": files.len()}), request_id)
        }
        "/logging/logs" => {
            let entries = files
                .iter()
                .filter_map(|name| fs::read_to_string(directory.join(name)).ok())
                .flat_map(|content| content.lines().map(str::to_owned).collect::<Vec<_>>())
                .collect::<Vec<_>>();
            success(StatusCode::OK, json!({"logs": entries}), request_id)
        }
        "/logging/logs/export" | "/logging/logs/download" => {
            success(StatusCode::OK, json!({"files": files}), request_id)
        }
        _ => error(
            StatusCode::NOT_FOUND,
            "GTW003",
            "Platform route does not exist",
            request_id,
        ),
    }
}

async fn discovery_parse(
    state: &AppState,
    path: &str,
    method: &Method,
    payload: Value,
    raw_body: &[u8],
    username: &str,
    request_id: &str,
) -> Response {
    if method != Method::POST {
        return error(
            StatusCode::METHOD_NOT_ALLOWED,
            "GTW004",
            "Method not allowed",
            request_id,
        );
    }
    if !has_permission(state, username, "manage_apis").await {
        return error(
            StatusCode::FORBIDDEN,
            "AUTHZ001",
            "Not authorized",
            request_id,
        );
    }
    if path == "/openapi/parse" {
        return match crate::routes::discovery::parse_openapi(&payload) {
            Ok(parsed) => success(StatusCode::OK, parsed, request_id),
            Err(message) => error(StatusCode::BAD_REQUEST, "OPENAPI004", &message, request_id),
        };
    }

    let content = payload
        .get("content")
        .or_else(|| payload.get("wsdl"))
        .and_then(Value::as_str)
        .map(str::to_owned)
        .or_else(|| payload.as_str().map(str::to_owned))
        .unwrap_or_else(|| String::from_utf8_lossy(raw_body).into_owned());
    match crate::routes::discovery::parse_wsdl(&content) {
        Ok(parsed) => success(
            StatusCode::OK,
            json!({
                "service_name": parsed.get("service_name").cloned().unwrap_or(Value::String(String::new())),
                "target_namespace": parsed.get("target_namespace").cloned().unwrap_or(Value::String(String::new())),
                "operations": parsed.get("operations").cloned().unwrap_or_else(|| json!([])),
                "endpoints_count": parsed.get("endpoints").and_then(Value::as_array).map(Vec::len).unwrap_or(0),
            }),
            request_id,
        ),
        Err(message) => error(StatusCode::BAD_REQUEST, "WSDL004", &message, request_id),
    }
}

fn sign_token(
    state: &AppState,
    claims: &AccessClaims,
) -> Result<String, jsonwebtoken::errors::Error> {
    let config = &state.config.shared_storage;
    if let Some(raw) = &config.jwt_keys_json {
        if let Ok(value) = serde_json::from_str::<Value>(raw) {
            let entries = value
                .get("keys")
                .and_then(Value::as_array)
                .cloned()
                .or_else(|| value.as_array().cloned())
                .unwrap_or_else(|| vec![value]);
            for entry in entries {
                if entry.get("active").and_then(Value::as_bool) == Some(false) {
                    continue;
                }
                let algorithm = entry
                    .get("algorithm")
                    .and_then(Value::as_str)
                    .unwrap_or("HS256");
                let kid = entry.get("kid").and_then(Value::as_str).map(str::to_owned);
                let mut header = Header::new(if algorithm.eq_ignore_ascii_case("RS256") {
                    Algorithm::RS256
                } else {
                    Algorithm::HS256
                });
                header.kid = kid;
                if algorithm.eq_ignore_ascii_case("RS256") {
                    if let Some(key) = entry.get("private_key").and_then(Value::as_str) {
                        return encode(
                            &header,
                            claims,
                            &EncodingKey::from_rsa_pem(key.as_bytes())?,
                        );
                    }
                } else if let Some(key) = entry
                    .get("secret")
                    .or_else(|| entry.get("key"))
                    .and_then(Value::as_str)
                {
                    return encode(&header, claims, &EncodingKey::from_secret(key.as_bytes()));
                }
            }
        }
    }
    encode(
        &Header::default(),
        claims,
        &EncodingKey::from_secret(
            config
                .jwt_secret
                .as_deref()
                .unwrap_or("insecure-test-key")
                .as_bytes(),
        ),
    )
}

fn password_hash(user: &Value) -> Option<String> {
    match user.get("password")? {
        Value::String(value) => Some(value.clone()),
        Value::Array(values) => String::from_utf8(
            values
                .iter()
                .filter_map(Value::as_u64)
                .map(|value| value as u8)
                .collect(),
        )
        .ok(),
        Value::Object(map) => map
            .get("$binary")
            .and_then(|binary| binary.get("base64"))
            .and_then(Value::as_str)
            .and_then(|raw| {
                base64::Engine::decode(&base64::engine::general_purpose::STANDARD, raw).ok()
            })
            .and_then(|bytes| String::from_utf8(bytes).ok()),
        _ => None,
    }
}

fn secure_password(password: &str) -> bool {
    password.len() >= 16
        && password.chars().any(|c| c.is_ascii_uppercase())
        && password.chars().any(|c| c.is_ascii_lowercase())
        && password.chars().any(|c| c.is_ascii_digit())
        && password
            .chars()
            .any(|c| "!@#$%^&*()-_=+[]{};:,.<>?/".contains(c))
}

fn password_policy() -> &'static str {
    "Password must include at least 16 characters, one uppercase letter, one lowercase letter, one digit, and one special character"
}

fn cookie_secure(headers: &HeaderMap) -> bool {
    env::var("COOKIE_SECURE")
        .ok()
        .map(|value| value.eq_ignore_ascii_case("true"))
        .unwrap_or_else(|| {
            env_bool("HTTPS_ONLY", false)
                || headers
                    .get("x-forwarded-proto")
                    .and_then(|value| value.to_str().ok())
                    .is_some_and(|value| value.eq_ignore_ascii_case("https"))
        })
}

fn cookie_same_site(secure: bool) -> &'static str {
    match env::var("COOKIE_SAMESITE")
        .unwrap_or_else(|_| "strict".to_owned())
        .to_ascii_lowercase()
        .as_str()
    {
        "none" if secure => "None",
        "lax" | "none" => "Lax",
        _ => "Strict",
    }
}

async fn csrf_matches(
    headers: &HeaderMap,
    storage: &crate::storage::runtime::SharedStorage,
    username: &str,
) -> bool {
    let Some(header_token) = headers
        .get("x-csrf-token")
        .and_then(|value| value.to_str().ok())
        .filter(|value| !value.is_empty())
    else {
        return false;
    };
    if cookie_value(headers, "csrf_token").as_deref() == Some(header_token) {
        return true;
    }
    matches!(
        storage.get_ephemeral(&format!("csrf_token_map:{username}")).await,
        Ok(Some(Value::String(value))) if value == header_token
    )
}

fn cookie_value(headers: &HeaderMap, name: &str) -> Option<String> {
    headers
        .get_all(header::COOKIE)
        .iter()
        .filter_map(|value| value.to_str().ok())
        .flat_map(|value| value.split(';'))
        .filter_map(|cookie| cookie.trim().split_once('='))
        .find_map(|(cookie_name, value)| (cookie_name == name).then(|| value.to_owned()))
}

fn cookie_domain(headers: &HeaderMap) -> Option<String> {
    let domain = env::var("COOKIE_DOMAIN").ok()?.trim().to_owned();
    if !domain.contains('.') {
        return None;
    }
    let host = headers
        .get("x-forwarded-host")
        .or_else(|| headers.get(header::HOST))
        .and_then(|value| value.to_str().ok())?
        .split(':')
        .next()
        .unwrap_or_default();
    (host == domain || host.ends_with(&format!(".{domain}"))).then_some(domain)
}

fn auth_expiry_seconds() -> usize {
    let value = env::var("AUTH_EXPIRE_TIME")
        .ok()
        .and_then(|value| value.trim().parse::<usize>().ok())
        .filter(|value| *value > 0)
        .unwrap_or(30);
    let multiplier = match env::var("AUTH_EXPIRE_TIME_FREQ")
        .unwrap_or_else(|_| "minutes".to_owned())
        .trim()
        .to_ascii_lowercase()
        .as_str()
    {
        "s" | "sec" | "second" | "seconds" => 1,
        "h" | "hr" | "hour" | "hours" => 60 * 60,
        "d" | "day" | "days" => 24 * 60 * 60,
        "w" | "wk" | "week" | "weeks" => 7 * 24 * 60 * 60,
        _ => 60,
    };
    value.saturating_mul(multiplier)
}

fn refresh_expiry_seconds() -> usize {
    let value = env::var("AUTH_REFRESH_EXPIRE_TIME")
        .ok()
        .and_then(|value| value.trim().parse::<usize>().ok())
        .filter(|value| *value > 0)
        .unwrap_or(7);
    let multiplier = match env::var("AUTH_REFRESH_EXPIRE_FREQ")
        .unwrap_or_else(|_| "days".to_owned())
        .trim()
        .to_ascii_lowercase()
        .as_str()
    {
        "s" | "sec" | "second" | "seconds" => 1,
        "m" | "min" | "minute" | "minutes" => 60,
        "h" | "hr" | "hour" | "hours" => 60 * 60,
        "w" | "wk" | "week" | "weeks" => 7 * 24 * 60 * 60,
        _ => 24 * 60 * 60,
    };
    value.saturating_mul(multiplier)
}

fn request_id_from(headers: &HeaderMap) -> String {
    headers
        .get("x-request-id")
        .or_else(|| headers.get("request_id"))
        .and_then(|value| value.to_str().ok())
        .filter(|value| !value.is_empty())
        .map(str::to_owned)
        .unwrap_or_else(|| Uuid::new_v4().to_string())
}

#[allow(clippy::too_many_arguments)]
async fn auth_ip_rate_limit(
    state: &AppState,
    headers: &HeaderMap,
    direct_addr: Option<SocketAddr>,
    limit_name: &str,
    default_limit: u64,
    window_name: &str,
    default_window: u64,
    request_id: &str,
) -> Option<Response> {
    if env_bool("LOGIN_IP_RATE_DISABLED", false) {
        return None;
    }
    let storage = state.storage.as_ref()?;
    let client_ip = ["x-forwarded-for", "x-real-ip", "cf-connecting-ip"]
        .into_iter()
        .find_map(|name| {
            headers
                .get(name)
                .and_then(|value| value.to_str().ok())
                .and_then(|value| value.split(',').next())
                .map(str::trim)
                .filter(|value| !value.is_empty())
                .map(str::to_owned)
        })
        .or_else(|| direct_addr.map(|value| value.ip().to_string()))?;
    let limit = env::var(limit_name)
        .ok()
        .and_then(|value| value.parse::<u64>().ok())
        .unwrap_or(default_limit);
    let window = env::var(window_name)
        .ok()
        .and_then(|value| value.parse::<u64>().ok())
        .unwrap_or(default_window)
        .max(1);
    let now = unix_seconds();
    let bucket = now / window;
    let count = storage
        .increment_window(&format!("ip_rate_limit:{client_ip}:{bucket}"), window)
        .await
        .ok()?;
    if count <= limit {
        return None;
    }
    let reset = (bucket + 1) * window;
    let retry_after = window - (now % window);
    let mut response = json_response(
        StatusCode::TOO_MANY_REQUESTS,
        json!({
            "detail": {
                "error_code": "IP_RATE_LIMIT",
                "message": format!(
                    "Too many requests from your IP address. Please wait {retry_after} seconds before trying again. Limit: {limit} requests per {window} seconds."
                ),
                "retry_after": retry_after
            }
        }),
        request_id,
    );
    for (name, value) in [
        ("retry-after", retry_after),
        ("x-ratelimit-limit", limit),
        ("x-ratelimit-remaining", 0),
        ("x-ratelimit-reset", reset),
    ] {
        if let Ok(value) = HeaderValue::from_str(&value.to_string()) {
            response.headers_mut().insert(name, value);
        }
    }
    Some(response)
}

fn parse_query(query: Option<&str>) -> HashMap<String, String> {
    url::form_urlencoded::parse(query.unwrap_or("").as_bytes())
        .into_owned()
        .collect()
}

fn paginate(items: Vec<Value>, query: &HashMap<String, String>) -> Value {
    let page = query
        .get("page")
        .and_then(|value| value.parse::<usize>().ok())
        .unwrap_or(1)
        .max(1);
    let page_size = query
        .get("page_size")
        .and_then(|value| value.parse::<usize>().ok())
        .unwrap_or(100)
        .clamp(1, 1000);
    let start = (page - 1).saturating_mul(page_size);
    json!({
        "response": items
            .into_iter()
            .skip(start)
            .take(page_size)
            .collect::<Vec<_>>()
    })
}

fn strip_internal(mut value: Value) -> Value {
    strip_mongo_id(&mut value);
    value
}

fn public_user(mut value: Value) -> Value {
    if let Some(map) = value.as_object_mut() {
        map.remove("_id");
        map.remove("password");
    }
    value
}

fn schedule_restart() -> Result<(), (&'static str, &'static str)> {
    let mut candidates = Vec::new();
    if let Some(path) = env::var_os("DOORMAN_PID_FILE") {
        candidates.push(std::path::PathBuf::from(path));
    }
    if let Ok(current_dir) = env::current_dir() {
        candidates.push(current_dir.join("doorman.pid"));
    }
    if let Ok(executable) = env::current_exe()
        && let Some(parent) = executable.parent()
    {
        candidates.push(parent.join("doorman.pid"));
    }
    let Some(pid_file) = candidates.into_iter().find(|path| path.exists()) else {
        return Err((
            "SEC004",
            "Restart not supported: no PID file found (run using 'doorman start' or contact your admin)",
        ));
    };
    let pid = fs::read_to_string(&pid_file)
        .ok()
        .and_then(|value| value.trim().parse::<u32>().ok())
        .filter(|pid| *pid > 0)
        .ok_or(("SEC005", "Failed to schedule restart"))?;
    let executable = env::current_exe().map_err(|_| ("SEC005", "Failed to schedule restart"))?;

    #[cfg(unix)]
    {
        Command::new("sh")
            .arg("-c")
            .arg(
                "sleep 1; kill -TERM \"$1\" || exit 1; while kill -0 \"$1\" 2>/dev/null; do sleep 0.2; done; echo $$ > \"$3\"; exec \"$2\"",
            )
            .arg("doorman-restart")
            .arg(pid.to_string())
            .arg(executable)
            .arg(pid_file)
            .stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .spawn()
            .map_err(|_| ("SEC005", "Failed to schedule restart"))?;
        Ok(())
    }
    #[cfg(not(unix))]
    {
        let _ = (pid, executable, pid_file);
        Err(("SEC005", "Failed to schedule restart"))
    }
}

fn set_default(target: &mut Value, key: &str, value: Value) {
    if target.get(key).is_none() {
        target[key] = value;
    }
}

fn success(status: StatusCode, payload: Value, request_id: &str) -> Response {
    json_response(status, payload, request_id)
}

fn message(status: StatusCode, text: &str, request_id: &str) -> Response {
    let mut response = json_response(status, json!({"message": text}), request_id);
    response.extensions_mut().insert(MessageEnvelope);
    response
}

fn error(status: StatusCode, code: &str, text: &str, request_id: &str) -> Response {
    json_response(
        status,
        json!({"error_code": code, "error_message": text}),
        request_id,
    )
}
fn http_detail(status: StatusCode, detail: &str, request_id: &str) -> Response {
    json_response(status, json!({"detail": detail}), request_id)
}

fn validation_errors(errors: Vec<Value>, request_id: &str) -> Response {
    json_response(
        StatusCode::UNPROCESSABLE_ENTITY,
        json!({"detail": errors}),
        request_id,
    )
}

fn unexpected(request_id: &str) -> Response {
    error(
        StatusCode::INTERNAL_SERVER_ERROR,
        "GTW999",
        "An unexpected error occurred",
        request_id,
    )
}

fn json_response(status: StatusCode, payload: Value, request_id: &str) -> Response {
    let body = serde_json::to_vec(&payload).unwrap_or_else(|_| b"{}".to_vec());
    let length = body.len().to_string();
    let mut response = (
        status,
        [(header::CONTENT_TYPE, "application/json")],
        Body::from(body),
    )
        .into_response();
    if let Ok(value) = HeaderValue::from_str(request_id) {
        response.headers_mut().insert("request_id", value.clone());
        response.headers_mut().insert("x-request-id", value);
    }
    if let Ok(value) = HeaderValue::from_str(&length) {
        response
            .headers_mut()
            .insert(header::CONTENT_LENGTH, value.clone());
        response.headers_mut().insert("x-body-length", value);
    }
    response
}

fn env_bool(name: &str, default: bool) -> bool {
    env::var(name)
        .ok()
        .map(|value| {
            matches!(
                value.to_ascii_lowercase().as_str(),
                "1" | "true" | "yes" | "on"
            )
        })
        .unwrap_or(default)
}

fn timestamp_now() -> String {
    time::OffsetDateTime::now_utc()
        .format(&time::format_description::well_known::Rfc3339)
        .unwrap_or_else(|_| "1970-01-01T00:00:00Z".to_owned())
}

fn unix_seconds() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn enforces_the_python_password_policy() {
        assert!(secure_password("SecurePassword@123"));
        assert!(!secure_password("short"));
        assert!(!secure_password("NoSpecialCharacter123"));
    }

    #[test]
    fn pagination_is_one_based_and_capped() {
        let items = (0..5).map(|value| json!(value)).collect();
        let query = HashMap::from([
            ("page".to_owned(), "2".to_owned()),
            ("page_size".to_owned(), "2".to_owned()),
        ]);
        assert_eq!(paginate(items, &query), json!({"response": [2, 3]}));
    }
}
