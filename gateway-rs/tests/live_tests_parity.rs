use std::{
    net::SocketAddr,
    sync::Arc,
    time::{Duration, SystemTime, UNIX_EPOCH},
};

use axum::body::{Body, to_bytes};
use axum::{Json, Router, extract::ConnectInfo, response::Response, routing::any};
use doorman_gateway::{
    AppState, Config, build_router,
    storage::{redis::bandwidth_key, runtime::SharedStorage},
};
use http::{HeaderMap, Method, Uri};
use http::{Request, StatusCode, header};
use serde_json::{Value, json};
use tokio::task::JoinHandle;
use tower::ServiceExt;

async fn test_app_state() -> AppState {
    test_app_state_with(|_| {}).await
}

async fn test_app_state_with(configure: impl FnOnce(&mut Config)) -> AppState {
    let mut config = Config::for_test("removed-internal-backend".to_owned());
    config.https_only = false;
    configure(&mut config);
    let storage = SharedStorage::connect(&config.shared_storage)
        .await
        .unwrap();

    storage
        .insert_one(
            "roles",
            json!({
                "role_name": "admin",
                "manage_users": true,
                "manage_apis": true,
                "manage_endpoints": true,
                "manage_groups": true,
                "manage_roles": true,
                "manage_routings": true,
                "manage_gateway": true,
                "manage_subscriptions": true,
                "manage_credits": true,
                "manage_auth": true,
                "manage_security": true,
                "manage_tiers": true,
                "manage_rate_limits": true,
                "view_analytics": true,
                "view_logs": true,
                "export_logs": true
            }),
        )
        .await
        .unwrap();

    storage
        .insert_one(
            "users",
            json!({
                "username": "admin",
                "email": "admin@doorman.dev",
                "password": bcrypt::hash("AdminPassword123!", bcrypt::DEFAULT_COST).unwrap(),
                "role": "admin",
                "groups": ["ALL", "admin"],
                "active": true,
                "ui_access": true
            }),
        )
        .await
        .unwrap();

    let mut state = AppState::new(config).unwrap();
    state.storage = Some(Arc::new(storage));
    state
}

async fn login_admin(app: &axum::Router) -> String {
    let response = app
        .clone()
        .oneshot(
            Request::builder()
                .method("POST")
                .uri("/platform/authorization")
                .header(header::CONTENT_TYPE, "application/json")
                .body(Body::from(
                    json!({
                        "email": "admin@doorman.dev",
                        "password": "AdminPassword123!"
                    })
                    .to_string(),
                ))
                .unwrap(),
        )
        .await
        .unwrap();
    assert_eq!(response.status(), StatusCode::OK);
    let bytes = to_bytes(response.into_body(), usize::MAX).await.unwrap();
    let body: Value = serde_json::from_slice(&bytes).unwrap();
    body["access_token"].as_str().unwrap().to_owned()
}
async fn response_json(response: Response) -> (StatusCode, Value) {
    let status = response.status();
    let bytes = to_bytes(response.into_body(), usize::MAX).await.unwrap();
    let body = serde_json::from_slice(&bytes).unwrap();
    (status, body)
}

async fn authed_json_response(
    app: &axum::Router,
    token: &str,
    method: Method,
    uri: impl AsRef<str>,
    payload: Value,
) -> (StatusCode, Value) {
    let response = app
        .clone()
        .oneshot(
            Request::builder()
                .method(method)
                .uri(uri.as_ref())
                .header(header::AUTHORIZATION, format!("Bearer {token}"))
                .header(header::CONTENT_TYPE, "application/json")
                .body(Body::from(payload.to_string()))
                .unwrap(),
        )
        .await
        .unwrap();
    response_json(response).await
}

async fn authed_empty_response(
    app: &axum::Router,
    token: &str,
    method: Method,
    uri: impl AsRef<str>,
) -> (StatusCode, Value) {
    let response = app
        .clone()
        .oneshot(
            Request::builder()
                .method(method)
                .uri(uri.as_ref())
                .header(header::AUTHORIZATION, format!("Bearer {token}"))
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();
    response_json(response).await
}

async fn echo_upstream(method: Method, uri: Uri, headers: HeaderMap) -> Json<Value> {
    Json(json!({
        "method": method.as_str(),
        "path": uri.path(),
        "x_api_key": headers.get("x-api-key").and_then(|value| value.to_str().ok()),
    }))
}

async fn start_echo_upstream() -> (String, JoinHandle<()>) {
    let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
    let address = listener.local_addr().unwrap();
    let server = tokio::spawn(async move {
        axum::serve(
            listener,
            Router::new()
                .route("/status", any(echo_upstream))
                .route("/ping", any(echo_upstream))
                .route("/echo", any(echo_upstream))
                .route("/whoami", any(echo_upstream))
                .route("/hit", any(echo_upstream))
                .route("/p", any(echo_upstream))
                .route("/items", any(echo_upstream)),
        )
        .await
        .unwrap();
    });
    (format!("http://{address}"), server)
}

async fn configure_ip_gateway(
    app: &axum::Router,
    token: &str,
    upstream_url: &str,
    api_name: &str,
    ip_mode: &str,
    whitelist: Value,
    blacklist: Value,
) {
    let api = json!({
        "api_name": api_name,
        "api_version": "v1",
        "api_description": format!("{api_name} v1"),
        "api_allowed_roles": ["admin"],
        "api_allowed_groups": ["ALL"],
        "api_servers": [upstream_url],
        "api_type": "REST",
        "api_allowed_retry_count": 0,
        "api_ip_mode": ip_mode,
        "api_ip_whitelist": whitelist,
        "api_ip_blacklist": blacklist,
        "api_trust_x_forwarded_for": true,
        "active": true,
    });
    let (status, _) = authed_json_response(app, token, Method::POST, "/platform/api", api).await;
    assert!(status.is_success());

    let endpoint = json!({
        "api_name": api_name,
        "api_version": "v1",
        "endpoint_method": "GET",
        "endpoint_uri": "/p",
        "endpoint_description": "p",
    });
    let (status, _) =
        authed_json_response(app, token, Method::POST, "/platform/endpoint", endpoint).await;
    assert!(status.is_success());

    let subscription = json!({
        "api_name": api_name,
        "api_version": "v1",
        "username": "admin",
    });
    let (status, body) = authed_json_response(
        app,
        token,
        Method::POST,
        "/platform/subscription/subscribe",
        subscription,
    )
    .await;
    assert!(status.is_success() || body["error_code"] == "SUB004");
}

async fn ip_gateway_response(
    app: &axum::Router,
    token: &str,
    api_name: &str,
    real_ip: Option<&str>,
) -> (StatusCode, Value) {
    let mut builder = Request::builder()
        .method(Method::GET)
        .uri(format!("/api/rest/{api_name}/v1/p"))
        .extension(ConnectInfo(SocketAddr::new(
            "127.0.0.1".parse().unwrap(),
            42000,
        )))
        .header(header::AUTHORIZATION, format!("Bearer {token}"));
    if let Some(real_ip) = real_ip {
        builder = builder.header("x-real-ip", real_ip);
    }
    let response = app
        .clone()
        .oneshot(builder.body(Body::empty()).unwrap())
        .await
        .unwrap();
    response_json(response).await
}

#[tokio::test]
async fn live_test_61_api_ip_whitelist_and_blacklist_parity() {
    let app = build_router(test_app_state().await);
    let token = login_admin(&app).await;
    let (upstream_url, upstream) = start_echo_upstream().await;
    let api_name = "ip-policy-live-61";
    configure_ip_gateway(
        &app,
        &token,
        &upstream_url,
        api_name,
        "whitelist",
        json!(["1.2.3.4/32", "10.0.0.0/8"]),
        json!(["8.8.8.8/32"]),
    )
    .await;

    for allowed_ip in ["1.2.3.4", "10.23.45.6"] {
        let (status, body) = ip_gateway_response(&app, &token, api_name, Some(allowed_ip)).await;
        assert_eq!(status, StatusCode::OK, "allowed IP {allowed_ip}");
        assert_eq!(body["method"], "GET");
        assert_eq!(body["path"], "/p");
    }
    let (status, body) = ip_gateway_response(&app, &token, api_name, Some("8.8.8.8")).await;
    assert_eq!(status, StatusCode::FORBIDDEN);
    assert_eq!(body["error_code"], "API011");
    upstream.abort();
}

#[tokio::test]
async fn live_test_61_localhost_bypass_when_no_forward_headers_parity() {
    let state = test_app_state_with(|config| {
        config.shared_storage.local_host_ip_bypass = true;
    })
    .await;
    let app = build_router(state);
    let token = login_admin(&app).await;
    let (upstream_url, upstream) = start_echo_upstream().await;
    let api_name = "ip-bypass-live-61";
    configure_ip_gateway(
        &app,
        &token,
        &upstream_url,
        api_name,
        "whitelist",
        json!([]),
        json!([]),
    )
    .await;

    let (status, body) = ip_gateway_response(&app, &token, api_name, None).await;
    assert_eq!(status, StatusCode::OK);
    assert_eq!(body["method"], "GET");
    assert_eq!(body["path"], "/p");
    upstream.abort();
}

async fn configure_bandwidth_gateway(
    app: &axum::Router,
    token: &str,
    upstream_url: &str,
    api_name: &str,
    method: Method,
    limit: u64,
    window: &str,
) {
    let (status, _) = authed_json_response(
        app,
        token,
        Method::PUT,
        "/platform/user/admin",
        json!({
            "bandwidth_limit_bytes": limit,
            "bandwidth_limit_window": window,
            "bandwidth_limit_enabled": true,
        }),
    )
    .await;
    assert!(status.is_success());

    let api = json!({
        "api_name": api_name,
        "api_version": "v1",
        "api_description": format!("{api_name} bandwidth"),
        "api_allowed_roles": ["admin"],
        "api_allowed_groups": ["ALL"],
        "api_servers": [upstream_url],
        "api_type": "REST",
        "api_allowed_retry_count": 0,
        "active": true,
    });
    let (status, _) = authed_json_response(app, token, Method::POST, "/platform/api", api).await;
    assert!(status.is_success());

    let endpoint = json!({
        "api_name": api_name,
        "api_version": "v1",
        "endpoint_method": method.as_str(),
        "endpoint_uri": "/p",
        "endpoint_description": "bandwidth endpoint",
    });
    let (status, _) =
        authed_json_response(app, token, Method::POST, "/platform/endpoint", endpoint).await;
    assert!(status.is_success());

    let subscription = json!({"api_name": api_name, "api_version": "v1", "username": "admin"});
    let (status, body) = authed_json_response(
        app,
        token,
        Method::POST,
        "/platform/subscription/subscribe",
        subscription,
    )
    .await;
    assert!(status.is_success() || body["error_code"] == "SUB004");
}

async fn configure_cors_gateway(
    app: &axum::Router,
    token: &str,
    api_name: &str,
    upstream_url: &str,
    origins: Value,
    credentials: bool,
) {
    let api = json!({
        "api_name": api_name,
        "api_version": "v1",
        "api_description": format!("{api_name} CORS parity"),
        "api_allowed_roles": ["admin"],
        "api_allowed_groups": ["ALL"],
        "api_servers": [upstream_url],
        "api_type": "REST",
        "api_allowed_retry_count": 0,
        "api_cors_allow_origins": origins,
        "api_cors_allow_methods": ["GET", "POST"],
        "api_cors_allow_headers": ["Content-Type", "X-CSRF-Token"],
        "api_cors_allow_credentials": credentials,
        "active": true,
    });
    let (status, _) = authed_json_response(app, token, Method::POST, "/platform/api", api).await;
    assert!(status.is_success());

    let endpoint = json!({
        "api_name": api_name,
        "api_version": "v1",
        "endpoint_method": "GET",
        "endpoint_uri": "/echo",
        "endpoint_description": "CORS echo",
    });
    let (status, _) =
        authed_json_response(app, token, Method::POST, "/platform/endpoint", endpoint).await;
    assert!(status.is_success());

    let subscription = json!({
        "api_name": api_name,
        "api_version": "v1",
        "username": "admin",
    });
    let (status, _) = authed_json_response(
        app,
        token,
        Method::POST,
        "/platform/subscription/subscribe",
        subscription,
    )
    .await;
    assert!(status.is_success());
}

async fn cors_preflight(app: &axum::Router, token: &str, api_name: &str, origin: &str) -> Response {
    app.clone()
        .oneshot(
            Request::builder()
                .method(Method::OPTIONS)
                .uri(format!("/api/rest/{api_name}/v1/echo"))
                .header(header::AUTHORIZATION, format!("Bearer {token}"))
                .header(header::ORIGIN, origin)
                .header(header::ACCESS_CONTROL_REQUEST_METHOD, "GET")
                .header(header::ACCESS_CONTROL_REQUEST_HEADERS, "X-CSRF-Token")
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap()
}

#[tokio::test]
async fn live_test_98_api_cors_preflight_and_actual_response_headers_parity() {
    let app = build_router(test_app_state().await);
    let token = login_admin(&app).await;
    let (upstream_url, upstream) = start_echo_upstream().await;
    let api_name = "cors-preflight-98";
    configure_cors_gateway(
        &app,
        &token,
        api_name,
        &upstream_url,
        json!(["http://example.com"]),
        true,
    )
    .await;

    let response = cors_preflight(&app, &token, api_name, "http://example.com").await;
    assert_eq!(response.status(), StatusCode::NO_CONTENT);
    assert_eq!(
        response.headers()[header::ACCESS_CONTROL_ALLOW_ORIGIN],
        "http://example.com"
    );
    assert_eq!(
        response.headers()[header::ACCESS_CONTROL_ALLOW_CREDENTIALS],
        "true"
    );
    assert!(
        response.headers()[header::ACCESS_CONTROL_ALLOW_METHODS]
            .to_str()
            .unwrap()
            .split(',')
            .any(|method| method.trim() == "OPTIONS")
    );

    let response = app
        .clone()
        .oneshot(
            Request::builder()
                .method(Method::GET)
                .uri(format!("/api/rest/{api_name}/v1/echo"))
                .header(header::AUTHORIZATION, format!("Bearer {token}"))
                .header(header::ORIGIN, "http://example.com")
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();
    assert_eq!(response.status(), StatusCode::OK);
    assert_eq!(
        response.headers()[header::ACCESS_CONTROL_ALLOW_ORIGIN],
        "http://example.com"
    );
    assert_eq!(
        response.headers()[header::ACCESS_CONTROL_ALLOW_CREDENTIALS],
        "true"
    );
    upstream.abort();
}

#[tokio::test]
async fn live_test_99_cors_credentialed_wildcard_is_rejected_as_approved_security_divergence() {
    let app = build_router(test_app_state().await);
    let token = login_admin(&app).await;
    let api = json!({
        "api_name": "cors-wildcard-99",
        "api_version": "v1",
        "api_description": "credentialed wildcard",
        "api_allowed_roles": ["admin"],
        "api_allowed_groups": ["ALL"],
        "api_servers": ["http://127.0.0.1:9"],
        "api_type": "REST",
        "api_cors_allow_origins": ["*"],
        "api_cors_allow_methods": ["GET", "OPTIONS"],
        "api_cors_allow_headers": ["Content-Type"],
        "api_cors_allow_credentials": true,
        "active": true,
    });

    let (status, body) =
        authed_json_response(&app, &token, Method::POST, "/platform/api", api).await;
    assert_eq!(status, StatusCode::UNPROCESSABLE_ENTITY);
    assert_eq!(body["detail"][0]["type"], "value_error.cors_origins");
}

#[tokio::test]
async fn live_test_99_cors_specific_origin_and_headers_parity() {
    let app = build_router(test_app_state().await);
    let token = login_admin(&app).await;
    let (upstream_url, upstream) = start_echo_upstream().await;
    let api_name = "cors-specific-99";
    configure_cors_gateway(
        &app,
        &token,
        api_name,
        &upstream_url,
        json!(["http://ok.example"]),
        false,
    )
    .await;

    let allowed = cors_preflight(&app, &token, api_name, "http://ok.example").await;
    assert_eq!(allowed.status(), StatusCode::NO_CONTENT);
    assert_eq!(
        allowed.headers()[header::ACCESS_CONTROL_ALLOW_ORIGIN],
        "http://ok.example"
    );
    assert_eq!(
        allowed.headers()[header::ACCESS_CONTROL_ALLOW_HEADERS],
        "Content-Type, X-CSRF-Token"
    );

    let denied = cors_preflight(&app, &token, api_name, "http://bad.example").await;
    assert_eq!(denied.status(), StatusCode::NO_CONTENT);
    assert!(
        !denied
            .headers()
            .contains_key(header::ACCESS_CONTROL_ALLOW_ORIGIN)
    );
    upstream.abort();
}

#[tokio::test]
async fn live_platform_cors_default_preflight_parity() {
    let app = build_router(test_app_state().await);
    let response = app
        .oneshot(
            Request::builder()
                .method(Method::OPTIONS)
                .uri("/platform/api")
                .header(header::ORIGIN, "http://localhost:3000")
                .header(header::ACCESS_CONTROL_REQUEST_METHOD, "GET")
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();

    assert_eq!(response.status(), StatusCode::NO_CONTENT);
    assert_eq!(
        response.headers()[header::ACCESS_CONTROL_ALLOW_ORIGIN],
        "http://localhost:3000"
    );
}

#[tokio::test]
async fn live_platform_cors_tools_checker_default_methods_parity() {
    let app = build_router(test_app_state().await);
    let token = login_admin(&app).await;
    let (status, body) = authed_json_response(
        &app,
        &token,
        Method::POST,
        "/platform/tools/cors/check",
        json!({
            "origin": "http://localhost:3000",
            "method": "GET",
            "request_headers": ["X-Rand"],
        }),
    )
    .await;
    assert_eq!(status, StatusCode::OK);
    let payload = body.get("response").unwrap_or(&body);
    let mut methods = payload["config"]["allow_methods"]
        .as_array()
        .unwrap()
        .iter()
        .map(|method| method.as_str().unwrap())
        .collect::<Vec<_>>();
    methods.sort_unstable();
    assert_eq!(
        methods,
        ["DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"]
    );
}

async fn monitor_gateway_get(app: &axum::Router, token: &str, api_name: &str) -> StatusCode {
    app.clone()
        .oneshot(
            Request::builder()
                .method(Method::GET)
                .uri(format!("/api/rest/{api_name}/v1/echo"))
                .header(header::AUTHORIZATION, format!("Bearer {token}"))
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap()
        .status()
}

#[tokio::test]
async fn monitor_dashboard_liveness_readiness_and_metrics_parity() {
    let app = build_router(test_app_state().await);
    let token = login_admin(&app).await;

    let (status, dashboard) =
        authed_empty_response(&app, &token, Method::GET, "/platform/dashboard").await;
    assert_eq!(status, StatusCode::OK);
    assert!(dashboard.get("activeUsers").is_some());
    assert!(dashboard.get("newApis").is_some());

    let (status, metrics) = authed_empty_response(
        &app,
        &token,
        Method::GET,
        "/platform/monitor/metrics?range=24h",
    )
    .await;
    assert_eq!(status, StatusCode::OK);
    assert!(metrics.is_object());

    let liveness = app
        .clone()
        .oneshot(
            Request::builder()
                .uri("/platform/monitor/liveness")
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();
    assert_eq!(liveness.status(), StatusCode::OK);
    let (_, liveness) = response_json(liveness).await;
    assert_eq!(liveness["status"], "alive");

    let readiness = app
        .clone()
        .oneshot(
            Request::builder()
                .uri("/platform/monitor/readiness")
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();
    assert_eq!(readiness.status(), StatusCode::OK);
    let (_, readiness) = response_json(readiness).await;
    assert!(matches!(
        readiness["status"].as_str(),
        Some("ready" | "degraded")
    ));
}

#[tokio::test]
async fn monitor_metrics_increment_status_series_and_top_apis_parity() {
    let app = build_router(test_app_state().await);
    let token = login_admin(&app).await;
    let (upstream_url, upstream) = start_echo_upstream().await;

    for api_name in ["monitor-mapi1", "monitor-mapi2"] {
        configure_cors_gateway(
            &app,
            &token,
            api_name,
            &upstream_url,
            json!(["http://localhost:3000"]),
            false,
        )
        .await;
    }
    assert_eq!(
        monitor_gateway_get(&app, &token, "monitor-mapi1").await,
        StatusCode::OK
    );
    for _ in 0..2 {
        assert_eq!(
            monitor_gateway_get(&app, &token, "monitor-mapi2").await,
            StatusCode::OK
        );
    }

    let (status, metrics) =
        authed_empty_response(&app, &token, Method::GET, "/platform/monitor/metrics").await;
    assert_eq!(status, StatusCode::OK);
    assert!(metrics["total_requests"].as_u64().unwrap_or(0) >= 3);
    assert!(metrics["status_counts"]["200"].as_u64().unwrap_or(0) >= 3);
    assert!(metrics["series"].is_array());
    assert!(metrics["top_apis"].as_array().unwrap().iter().any(|entry| {
        entry["name"]
            .as_str()
            .is_some_and(|name| name.starts_with("rest:"))
    }));
    upstream.abort();
}

#[tokio::test]
async fn monitor_report_returns_python_compatible_csv_sections() {
    let app = build_router(test_app_state().await);
    let token = login_admin(&app).await;
    let (upstream_url, upstream) = start_echo_upstream().await;
    let api_name = "monitor-report";
    configure_cors_gateway(
        &app,
        &token,
        api_name,
        &upstream_url,
        json!(["http://localhost:3000"]),
        false,
    )
    .await;
    assert_eq!(
        monitor_gateway_get(&app, &token, api_name).await,
        StatusCode::OK
    );

    let response = app
        .clone()
        .oneshot(
            Request::builder()
                .method(Method::GET)
                .uri("/platform/monitor/report?start=2026-08-26T12:00&end=2026-08-26T12:00")
                .header(header::AUTHORIZATION, format!("Bearer {token}"))
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();
    assert_eq!(response.status(), StatusCode::OK);
    assert!(
        response.headers()[header::CONTENT_TYPE]
            .to_str()
            .unwrap()
            .starts_with("text/csv")
    );
    let text = String::from_utf8(
        to_bytes(response.into_body(), usize::MAX)
            .await
            .unwrap()
            .to_vec(),
    )
    .unwrap();
    for section in ["Report", "Overview", "Status Codes", "API Usage"] {
        assert!(text.contains(section), "missing CSV section {section}");
    }
    upstream.abort();
}

async fn bandwidth_gateway_response(
    app: &axum::Router,
    token: &str,
    api_name: &str,
    method: Method,
    payload: Option<Value>,
) -> (StatusCode, Value) {
    let body = payload.map(|value| value.to_string()).unwrap_or_default();
    let mut builder = Request::builder()
        .method(method)
        .uri(format!("/api/rest/{api_name}/v1/p"))
        .header(header::AUTHORIZATION, format!("Bearer {token}"))
        .header(header::CONTENT_LENGTH, body.len());
    if !body.is_empty() {
        builder = builder.header(header::CONTENT_TYPE, "application/json");
    }
    let response = app
        .clone()
        .oneshot(builder.body(Body::from(body)).unwrap())
        .await
        .unwrap();
    response_json(response).await
}

#[tokio::test]
async fn bandwidth_enforcement_and_usage_tracking_parity() {
    let state = test_app_state().await;
    let app = build_router(state);
    let token = login_admin(&app).await;
    let (upstream_url, upstream) = start_echo_upstream().await;
    let api_name = "bandwidth-usage";
    configure_bandwidth_gateway(
        &app,
        &token,
        &upstream_url,
        api_name,
        Method::POST,
        80,
        "minute",
    )
    .await;

    let payload = json!({"data": "x".repeat(50)});
    let (first, _) =
        bandwidth_gateway_response(&app, &token, api_name, Method::POST, Some(payload.clone()))
            .await;
    let (second, _) =
        bandwidth_gateway_response(&app, &token, api_name, Method::POST, Some(payload)).await;
    assert_eq!(first, StatusCode::OK);
    assert_eq!(second, StatusCode::TOO_MANY_REQUESTS);

    let (status, user) =
        authed_empty_response(&app, &token, Method::GET, "/platform/user/me").await;
    assert_eq!(status, StatusCode::OK);
    assert!(user["bandwidth_usage_bytes"].as_u64().unwrap_or(0) > 0);
    assert!(user["bandwidth_resets_at"].as_u64().unwrap_or(0) > 0);
    upstream.abort();
}

#[tokio::test]
async fn monitor_tracks_gateway_bytes_in_and_out_parity() {
    let app = build_router(test_app_state().await);
    let token = login_admin(&app).await;
    let (upstream_url, upstream) = start_echo_upstream().await;
    let api_name = "bandwidth-monitor";
    configure_bandwidth_gateway(
        &app,
        &token,
        &upstream_url,
        api_name,
        Method::POST,
        1_000_000,
        "minute",
    )
    .await;
    let (_, before) =
        authed_empty_response(&app, &token, Method::GET, "/platform/monitor/metrics").await;
    let payload = json!({"pad": "z".repeat(30)});
    let payload_size = payload.to_string().len() as u64;

    for _ in 0..2 {
        let (status, _) =
            bandwidth_gateway_response(&app, &token, api_name, Method::POST, Some(payload.clone()))
                .await;
        assert_eq!(status, StatusCode::OK);
    }
    let (_, after) =
        authed_empty_response(&app, &token, Method::GET, "/platform/monitor/metrics").await;
    assert!(
        after["total_bytes_in"].as_u64().unwrap_or(0)
            - before["total_bytes_in"].as_u64().unwrap_or(0)
            >= payload_size * 2
    );
    assert!(
        after["total_bytes_out"].as_u64().unwrap_or(0)
            > before["total_bytes_out"].as_u64().unwrap_or(0)
    );
    upstream.abort();
}

#[tokio::test]
async fn bandwidth_counts_request_and_response_bytes_parity() {
    let state = test_app_state().await;
    let storage = state.storage.clone().unwrap();
    let app = build_router(state);
    let token = login_admin(&app).await;
    let (upstream_url, upstream) = start_echo_upstream().await;
    let api_name = "bandwidth-counting";
    configure_bandwidth_gateway(
        &app,
        &token,
        &upstream_url,
        api_name,
        Method::POST,
        1_000_000,
        "minute",
    )
    .await;
    let now = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs();
    let key = bandwidth_key("admin", 60, (now / 60) * 60);
    let before = storage.current_counter(&key).await.unwrap();
    let payload = "x".repeat(1234);
    let (status, _) = bandwidth_gateway_response(
        &app,
        &token,
        api_name,
        Method::POST,
        Some(json!({"data": payload})),
    )
    .await;
    assert_eq!(status, StatusCode::OK);
    let after = storage.current_counter(&key).await.unwrap();
    assert!(after - before >= 1234);
    assert!(after - before > 1234);
    upstream.abort();
}

#[tokio::test]
async fn live_bandwidth_limit_enforced_and_window_resets_parity() {
    let app = build_router(test_app_state().await);
    let token = login_admin(&app).await;
    let (upstream_url, upstream) = start_echo_upstream().await;
    let api_name = "bandwidth-window-live";
    configure_bandwidth_gateway(
        &app,
        &token,
        &upstream_url,
        api_name,
        Method::GET,
        1,
        "second",
    )
    .await;

    let (first, _) = bandwidth_gateway_response(&app, &token, api_name, Method::GET, None).await;
    let (second, _) = bandwidth_gateway_response(&app, &token, api_name, Method::GET, None).await;
    assert_eq!(first, StatusCode::OK);
    assert_eq!(second, StatusCode::TOO_MANY_REQUESTS);
    tokio::time::sleep(Duration::from_millis(1100)).await;
    let (third, _) = bandwidth_gateway_response(&app, &token, api_name, Method::GET, None).await;
    assert_eq!(third, StatusCode::OK);
    upstream.abort();
}

struct CreditGatewaySetup<'a> {
    api_name: &'a str,
    credit_group: &'a str,
    group_key: &'a str,
    user_key: Option<&'a str>,
    upstream_url: &'a str,
    endpoint_method: Method,
    endpoint_uri: &'a str,
    available_credits: u64,
}

async fn configure_credit_gateway(app: &axum::Router, token: &str, setup: &CreditGatewaySetup<'_>) {
    let CreditGatewaySetup {
        api_name,
        credit_group,
        group_key,
        user_key,
        upstream_url,
        endpoint_method,
        endpoint_uri,
        available_credits,
    } = setup;

    let credit_definition = json!({"api_credit_group": credit_group, "api_key": group_key, "api_key_header": "x-api-key", "credit_tiers": [{"tier_name": "default", "credits": available_credits, "input_limit": 0, "output_limit": 0, "reset_frequency": "monthly"}]});
    let (status, _) = authed_json_response(
        app,
        token,
        Method::POST,
        "/platform/credit",
        credit_definition,
    )
    .await;
    assert!(status.is_success());

    let mut user_credit = json!({"tier_name": "default", "available_credits": available_credits});
    if let Some(user_key) = user_key {
        user_credit["user_api_key"] = json!(user_key);
    }
    let credit_assignment =
        json!({"username": "admin", "users_credits": {(*credit_group): user_credit}});
    let (status, _) = authed_json_response(
        app,
        token,
        Method::POST,
        "/platform/credit/admin",
        credit_assignment,
    )
    .await;
    assert!(status.is_success());

    let api = json!({"api_name": api_name, "api_version": "v1", "api_description": "credit gateway", "api_allowed_roles": ["admin"], "api_allowed_groups": ["ALL"], "api_servers": [upstream_url], "api_type": "REST", "api_allowed_retry_count": 0, "active": true, "api_credits_enabled": true, "api_credit_group": credit_group});
    let (status, _) = authed_json_response(app, token, Method::POST, "/platform/api", api).await;
    assert!(status.is_success());

    let endpoint = json!({"api_name": api_name, "api_version": "v1", "endpoint_method": endpoint_method.as_str(), "endpoint_uri": endpoint_uri, "endpoint_description": "credit gateway endpoint"});
    let (status, _) =
        authed_json_response(app, token, Method::POST, "/platform/endpoint", endpoint).await;
    assert!(status.is_success());

    let subscription = json!({"api_name": api_name, "api_version": "v1", "username": "admin"});
    let (status, _) = authed_json_response(
        app,
        token,
        Method::POST,
        "/platform/subscription/subscribe",
        subscription,
    )
    .await;
    assert!(status.is_success());
}

#[tokio::test]
async fn live_test_00_health_and_auth_status_me_parity() {
    let state = test_app_state().await;
    let app = build_router(state);
    let token = login_admin(&app).await;

    // test_status_ok: GET /api/health -> 200 OK
    let response = app
        .clone()
        .oneshot(
            Request::builder()
                .method("GET")
                .uri("/api/health")
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();
    assert_eq!(response.status(), StatusCode::OK);
    let bytes = to_bytes(response.into_body(), usize::MAX).await.unwrap();
    let body: Value = serde_json::from_slice(&bytes).unwrap();
    assert_eq!(body["status"], "online");

    // test_auth_status_me: GET /platform/authorization/status -> 200 OK
    let response = app
        .clone()
        .oneshot(
            Request::builder()
                .method("GET")
                .uri("/platform/authorization/status")
                .header(header::AUTHORIZATION, format!("Bearer {token}"))
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();
    assert_eq!(response.status(), StatusCode::OK);

    // GET /platform/user/me -> username == "admin", ui_access == true
    let response = app
        .clone()
        .oneshot(
            Request::builder()
                .method("GET")
                .uri("/platform/user/me")
                .header(header::AUTHORIZATION, format!("Bearer {token}"))
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();
    assert_eq!(response.status(), StatusCode::OK);
    let bytes = to_bytes(response.into_body(), usize::MAX).await.unwrap();
    let body: Value = serde_json::from_slice(&bytes).unwrap();
    assert_eq!(body["username"], "admin");
    assert_eq!(body["ui_access"], true);
}

#[tokio::test]
async fn live_test_10_user_onboarding_lifecycle_parity() {
    let state = test_app_state().await;
    let app = build_router(state);
    let token = login_admin(&app).await;

    let username = "user_onboarding_10";
    let email = "user10@example.com";
    let password = "StrongUserPassword123!";

    // Create user: POST /platform/user
    let response = app
        .clone()
        .oneshot(
            Request::builder()
                .method("POST")
                .uri("/platform/user")
                .header(header::AUTHORIZATION, format!("Bearer {token}"))
                .header(header::CONTENT_TYPE, "application/json")
                .body(Body::from(
                    json!({
                        "username": username,
                        "email": email,
                        "password": password,
                        "role": "developer",
                        "groups": ["ALL"],
                        "ui_access": false
                    })
                    .to_string(),
                ))
                .unwrap(),
        )
        .await
        .unwrap();
    assert!(response.status().is_success());

    // GET /platform/user/{username} -> verify email & ui_access: false
    let response = app
        .clone()
        .oneshot(
            Request::builder()
                .method("GET")
                .uri(format!("/platform/user/{username}"))
                .header(header::AUTHORIZATION, format!("Bearer {token}"))
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();
    assert_eq!(response.status(), StatusCode::OK);
    let bytes = to_bytes(response.into_body(), usize::MAX).await.unwrap();
    let body: Value = serde_json::from_slice(&bytes).unwrap();
    assert_eq!(body["email"], email);
    assert_eq!(body["ui_access"], false);

    // PUT /platform/user/{username} -> update ui_access: true
    let response = app
        .clone()
        .oneshot(
            Request::builder()
                .method("PUT")
                .uri(format!("/platform/user/{username}"))
                .header(header::AUTHORIZATION, format!("Bearer {token}"))
                .header(header::CONTENT_TYPE, "application/json")
                .body(Body::from(json!({"ui_access": true}).to_string()))
                .unwrap(),
        )
        .await
        .unwrap();
    assert!(response.status().is_success());

    let new_password = "UpdatedUserPassword123!";
    let (password_status, _) = authed_json_response(
        &app,
        &token,
        Method::PUT,
        &format!("/platform/user/{username}/update-password"),
        json!({"old_password": password, "new_password": new_password}),
    )
    .await;
    assert!(password_status.is_success() || password_status == StatusCode::BAD_REQUEST);
    let login_password = if password_status.is_success() {
        new_password
    } else {
        password
    };

    // Login as user_onboarding_10
    let response = app
        .clone()
        .oneshot(
            Request::builder()
                .method("POST")
                .uri("/platform/authorization")
                .header(header::CONTENT_TYPE, "application/json")
                .body(Body::from(
                    json!({
                        "email": email,
                        "password": login_password
                    })
                    .to_string(),
                ))
                .unwrap(),
        )
        .await
        .unwrap();
    assert_eq!(response.status(), StatusCode::OK);
    let bytes = to_bytes(response.into_body(), usize::MAX).await.unwrap();
    let body: Value = serde_json::from_slice(&bytes).unwrap();
    let user_token = body["access_token"].as_str().unwrap();
    let (status, me) =
        authed_empty_response(&app, user_token, Method::GET, "/platform/user/me").await;
    assert_eq!(status, StatusCode::OK);
    assert_eq!(me["username"], username);
    assert_eq!(me["ui_access"], true);

    // DELETE /platform/user/{username}
    let response = app
        .clone()
        .oneshot(
            Request::builder()
                .method("DELETE")
                .uri(format!("/platform/user/{username}"))
                .header(header::AUTHORIZATION, format!("Bearer {token}"))
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();
    assert!(response.status().is_success());
}

#[tokio::test]
async fn live_test_20_credit_defs_and_user_overrides_parity() {
    let state = test_app_state().await;
    let app = build_router(state);
    let token = login_admin(&app).await;

    let credit_group = "cg-test-20";
    let api_key_val = "DUMMY_KEY_20";

    // POST /platform/credit
    let response = app
        .clone()
        .oneshot(
            Request::builder()
                .method("POST")
                .uri("/platform/credit")
                .header(header::AUTHORIZATION, format!("Bearer {token}"))
                .header(header::CONTENT_TYPE, "application/json")
                .body(Body::from(
                    json!({
                        "api_credit_group": credit_group,
                        "api_key": api_key_val,
                        "api_key_header": "x-api-key",
                        "credit_tiers": [{
                            "tier_name": "default",
                            "credits": 10,
                            "input_limit": 0,
                            "output_limit": 0,
                            "reset_frequency": "monthly"
                        }]
                    })
                    .to_string(),
                ))
                .unwrap(),
        )
        .await
        .unwrap();
    assert!(response.status().is_success());

    let (status, _) = authed_empty_response(
        &app,
        &token,
        Method::GET,
        &format!("/platform/credit/defs/{credit_group}"),
    )
    .await;
    assert_eq!(status, StatusCode::OK);

    // POST /platform/credit/admin
    let response = app
        .clone()
        .oneshot(
            Request::builder()
                .method("POST")
                .uri("/platform/credit/admin")
                .header(header::AUTHORIZATION, format!("Bearer {token}"))
                .header(header::CONTENT_TYPE, "application/json")
                .body(Body::from(
                    json!({
                        "username": "admin",
                        "users_credits": {
                            credit_group: {
                                "tier_name": "default",
                                "available_credits": 10
                            }
                        }
                    })
                    .to_string(),
                ))
                .unwrap(),
        )
        .await
        .unwrap();
    assert!(response.status().is_success());

    // GET /platform/credit/admin
    let response = app
        .clone()
        .oneshot(
            Request::builder()
                .method("GET")
                .uri("/platform/credit/admin")
                .header(header::AUTHORIZATION, format!("Bearer {token}"))
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();
    assert_eq!(response.status(), StatusCode::OK);
    let bytes = to_bytes(response.into_body(), usize::MAX).await.unwrap();
    let body: Value = serde_json::from_slice(&bytes).unwrap();
    assert!(body["users_credits"].get(credit_group).is_some());
}

#[tokio::test]
async fn live_test_30_rest_gateway_basic_crud_and_subscription_parity() {
    let state = test_app_state().await;
    let app = build_router(state);
    let token = login_admin(&app).await;
    let (upstream_url, upstream) = start_echo_upstream().await;

    let api_name = "rest-crud-api";
    let api_version = "v1";

    // Create API: POST /platform/api
    let response = app
        .clone()
        .oneshot(
            Request::builder()
                .method("POST")
                .uri("/platform/api")
                .header(header::AUTHORIZATION, format!("Bearer {token}"))
                .header(header::CONTENT_TYPE, "application/json")
                .body(Body::from(
                    json!({
                        "api_name": api_name,
                        "api_version": api_version,
                        "api_description": "REST crud demo",
                        "api_allowed_roles": ["admin"],
                        "api_allowed_groups": ["ALL"],
                        "api_servers": [upstream_url],
                        "api_type": "REST",
                        "active": true
                    })
                    .to_string(),
                ))
                .unwrap(),
        )
        .await
        .unwrap();
    assert!(response.status().is_success());

    // Create Endpoint: POST /platform/endpoint
    let response = app
        .clone()
        .oneshot(
            Request::builder()
                .method("POST")
                .uri("/platform/endpoint")
                .header(header::AUTHORIZATION, format!("Bearer {token}"))
                .header(header::CONTENT_TYPE, "application/json")
                .body(Body::from(
                    json!({
                        "api_name": api_name,
                        "api_version": api_version,
                        "endpoint_method": "GET",
                        "endpoint_uri": "/status",
                        "endpoint_description": "status"
                    })
                    .to_string(),
                ))
                .unwrap(),
        )
        .await
        .unwrap();
    assert!(response.status().is_success());

    // Subscribe: POST /platform/subscription/subscribe
    let response = app
        .clone()
        .oneshot(
            Request::builder()
                .method("POST")
                .uri("/platform/subscription/subscribe")
                .header(header::AUTHORIZATION, format!("Bearer {token}"))
                .header(header::CONTENT_TYPE, "application/json")
                .body(Body::from(
                    json!({
                        "api_name": api_name,
                        "api_version": api_version,
                        "username": "admin"
                    })
                    .to_string(),
                ))
                .unwrap(),
        )
        .await
        .unwrap();
    assert!(response.status().is_success());

    // Gateway request must reach the configured upstream with the registered path.
    let (status, body) = authed_empty_response(
        &app,
        &token,
        Method::GET,
        &format!("/api/rest/{api_name}/{api_version}/status"),
    )
    .await;
    assert_eq!(status, StatusCode::OK);
    assert_eq!(body["method"], "GET");
    assert_eq!(body["path"], "/status");
    upstream.abort();
    // DELETE Endpoint & API
    let response = app
        .clone()
        .oneshot(
            Request::builder()
                .method("DELETE")
                .uri(format!(
                    "/platform/endpoint/GET/{api_name}/{api_version}/status"
                ))
                .header(header::AUTHORIZATION, format!("Bearer {token}"))
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();
    assert!(response.status().is_success());

    let response = app
        .clone()
        .oneshot(
            Request::builder()
                .method("DELETE")
                .uri(format!("/platform/api/{api_name}/{api_version}"))
                .header(header::AUTHORIZATION, format!("Bearer {token}"))
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();
    assert!(response.status().is_success());
}

#[tokio::test]
async fn live_test_21_subscription_list_unsubscribe_parity() {
    let app = build_router(test_app_state().await);
    let token = login_admin(&app).await;
    let api_name = "subs-test-21";
    let api_version = "v1";

    let api = json!({
        "api_name": api_name,
        "api_version": api_version,
        "api_description": "subscription flow",
        "api_allowed_roles": ["admin"],
        "api_allowed_groups": ["ALL"],
        "api_servers": ["http://127.0.0.1:9"],
        "api_type": "REST",
        "active": true,
    });
    let (status, _) = authed_json_response(&app, &token, Method::POST, "/platform/api", api).await;
    assert!(status.is_success());

    let subscription =
        json!({"api_name": api_name, "api_version": api_version, "username": "admin"});
    let (status, _) = authed_json_response(
        &app,
        &token,
        Method::POST,
        "/platform/subscription/subscribe",
        subscription.clone(),
    )
    .await;
    assert!(status.is_success());

    let (status, body) = authed_empty_response(
        &app,
        &token,
        Method::GET,
        "/platform/subscription/subscriptions",
    )
    .await;
    assert_eq!(status, StatusCode::OK);
    let apis = body["apis"].as_array().unwrap();
    let expected = Value::String(format!("{api_name}/{api_version}"));
    assert!(apis.iter().any(|api| api == &expected));

    let (status, _) = authed_json_response(
        &app,
        &token,
        Method::POST,
        "/platform/subscription/unsubscribe",
        subscription,
    )
    .await;
    assert!(status.is_success());

    let (status, _) = authed_empty_response(
        &app,
        &token,
        Method::DELETE,
        &format!("/platform/api/{api_name}/{api_version}"),
    )
    .await;
    assert!(status.is_success());
}

#[tokio::test]
async fn live_test_31_endpoint_update_list_delete_parity() {
    let app = build_router(test_app_state().await);
    let token = login_admin(&app).await;
    let api_name = "endpoint-crud-31";
    let api_version = "v1";

    let api = json!({"api_name": api_name, "api_version": api_version, "api_description": "endpoint CRUD", "api_allowed_roles": ["admin"], "api_allowed_groups": ["ALL"], "api_servers": ["http://127.0.0.1:9"], "api_type": "REST", "active": true});
    let (status, _) = authed_json_response(&app, &token, Method::POST, "/platform/api", api).await;
    assert!(status.is_success());

    let endpoint = json!({"api_name": api_name, "api_version": api_version, "endpoint_method": "GET", "endpoint_uri": "/z", "endpoint_description": "z"});
    let (status, _) =
        authed_json_response(&app, &token, Method::POST, "/platform/endpoint", endpoint).await;
    assert!(status.is_success());

    let (status, _) = authed_json_response(
        &app,
        &token,
        Method::PUT,
        &format!("/platform/endpoint/GET/{api_name}/{api_version}/z"),
        json!({"endpoint_description": "zzz"}),
    )
    .await;
    assert!(status.is_success());

    let (status, body) = authed_empty_response(
        &app,
        &token,
        Method::GET,
        &format!("/platform/endpoint/{api_name}/{api_version}"),
    )
    .await;
    assert_eq!(status, StatusCode::OK);
    let endpoints = body
        .as_array()
        .or_else(|| body.get("endpoints").and_then(Value::as_array))
        .or_else(|| {
            body.pointer("/response/endpoints")
                .and_then(Value::as_array)
        })
        .or_else(|| body.get("response").and_then(Value::as_array))
        .expect("endpoint list response must be an array");
    assert!(
        endpoints
            .iter()
            .any(|endpoint| endpoint["endpoint_description"] == "zzz")
    );

    let (status, _) = authed_empty_response(
        &app,
        &token,
        Method::DELETE,
        &format!("/platform/endpoint/GET/{api_name}/{api_version}/z"),
    )
    .await;
    assert!(status.is_success());

    let (status, _) = authed_empty_response(
        &app,
        &token,
        Method::GET,
        &format!("/api/rest/{api_name}/{api_version}/z"),
    )
    .await;
    assert!(status.is_client_error() || status.is_server_error());

    let (status, _) = authed_empty_response(
        &app,
        &token,
        Method::DELETE,
        &format!("/platform/api/{api_name}/{api_version}"),
    )
    .await;
    assert!(status.is_success());
}

#[tokio::test]
async fn live_test_30_credits_and_header_injection_parity() {
    let app = build_router(test_app_state().await);
    let token = login_admin(&app).await;
    let (upstream_url, upstream) = start_echo_upstream().await;
    let api_name = "credit-gateway-30";
    let credit_group = "credit-group-30";
    let group_key = "DUMMY_API_KEY_ABC";

    let setup = CreditGatewaySetup {
        api_name,
        credit_group,
        group_key,
        user_key: None,
        upstream_url: &upstream_url,
        endpoint_method: Method::POST,
        endpoint_uri: "/echo",
        available_credits: 2,
    };
    configure_credit_gateway(&app, &token, &setup).await;

    let (status, body) = authed_json_response(
        &app,
        &token,
        Method::POST,
        &format!("/api/rest/{api_name}/v1/echo"),
        json!({"ping": "pong"}),
    )
    .await;
    assert_eq!(status, StatusCode::OK);
    assert_eq!(body["x_api_key"], group_key);

    let (status, credits) =
        authed_empty_response(&app, &token, Method::GET, "/platform/credit/admin").await;
    assert_eq!(status, StatusCode::OK);
    assert_eq!(
        credits["users_credits"][credit_group]["available_credits"],
        1
    );

    upstream.abort();
    let (status, _) = authed_empty_response(
        &app,
        &token,
        Method::DELETE,
        &format!("/platform/endpoint/POST/{api_name}/v1/echo"),
    )
    .await;
    assert!(status.is_success());
    let (status, _) = authed_empty_response(
        &app,
        &token,
        Method::DELETE,
        &format!("/platform/api/{api_name}/v1"),
    )
    .await;
    assert!(status.is_success());
}

#[tokio::test]
async fn live_test_32_user_credit_key_override_parity() {
    let app = build_router(test_app_state().await);
    let token = login_admin(&app).await;
    let (upstream_url, upstream) = start_echo_upstream().await;
    let api_name = "credit-override-32";
    let credit_group = "credit-group-32";
    let group_key = "GROUP_KEY_ABC";
    let user_key = "USER_KEY_DEF";

    let setup = CreditGatewaySetup {
        api_name,
        credit_group,
        group_key,
        user_key: Some(user_key),
        upstream_url: &upstream_url,
        endpoint_method: Method::GET,
        endpoint_uri: "/whoami",
        available_credits: 3,
    };
    configure_credit_gateway(&app, &token, &setup).await;

    let (status, body) = authed_empty_response(
        &app,
        &token,
        Method::GET,
        &format!("/api/rest/{api_name}/v1/whoami"),
    )
    .await;
    assert_eq!(status, StatusCode::OK);
    assert_eq!(body["x_api_key"], user_key);
    upstream.abort();
    let (status, _) = authed_empty_response(
        &app,
        &token,
        Method::DELETE,
        &format!("/platform/endpoint/GET/{api_name}/v1/whoami"),
    )
    .await;
    assert!(status.is_success());
    let (status, _) = authed_empty_response(
        &app,
        &token,
        Method::DELETE,
        &format!("/platform/api/{api_name}/v1"),
    )
    .await;
    assert!(status.is_success());
}

#[tokio::test]
async fn live_test_33_rate_limiting_blocks_excess_requests_parity() {
    let state = test_app_state().await;
    let app = build_router(state);
    let token = login_admin(&app).await;

    let (upstream_url, upstream) = start_echo_upstream().await;
    let api_name = "rl-test-api";
    let api_version = "v1";

    // Set user rate limit: 1 request / 60 seconds
    let response = app
        .clone()
        .oneshot(
            Request::builder()
                .method("PUT")
                .uri("/platform/user/admin")
                .header(header::AUTHORIZATION, format!("Bearer {token}"))
                .header(header::CONTENT_TYPE, "application/json")
                .body(Body::from(
                    json!({
                        "rate_limit_duration": 1,
                        "rate_limit_duration_type": "second",
                        "throttle_duration": 999,
                        "throttle_duration_type": "second",
                        "throttle_queue_limit": 999,
                        "throttle_wait_duration": 0,
                        "throttle_wait_duration_type": "second"
                    })
                    .to_string(),
                ))
                .unwrap(),
        )
        .await
        .unwrap();
    assert!(response.status().is_success());

    // Clear caches: DELETE /api/caches
    let response = app
        .clone()
        .oneshot(
            Request::builder()
                .method("DELETE")
                .uri("/api/caches")
                .header(header::AUTHORIZATION, format!("Bearer {token}"))
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();
    assert!(response.status().is_success());

    // Create API & endpoint
    let _ = app
        .clone()
        .oneshot(
            Request::builder()
                .method("POST")
                .uri("/platform/api")
                .header(header::AUTHORIZATION, format!("Bearer {token}"))
                .header(header::CONTENT_TYPE, "application/json")
                .body(Body::from(
                    json!({
                        "api_name": api_name,
                        "api_version": api_version,
                        "api_description": "rl test",
                        "api_allowed_roles": ["admin"],
                        "api_allowed_groups": ["ALL"],
                        "api_servers": [upstream_url],
                        "api_type": "REST",
                        "active": true
                    })
                    .to_string(),
                ))
                .unwrap(),
        )
        .await;

    let _ = app
        .clone()
        .oneshot(
            Request::builder()
                .method("POST")
                .uri("/platform/endpoint")
                .header(header::AUTHORIZATION, format!("Bearer {token}"))
                .header(header::CONTENT_TYPE, "application/json")
                .body(Body::from(
                    json!({
                        "api_name": api_name,
                        "api_version": api_version,
                        "endpoint_method": "GET",
                        "endpoint_uri": "/hit",
                        "endpoint_description": "hit"
                    })
                    .to_string(),
                ))
                .unwrap(),
        )
        .await;

    let _ = app
        .clone()
        .oneshot(
            Request::builder()
                .method("POST")
                .uri("/platform/subscription/subscribe")
                .header(header::AUTHORIZATION, format!("Bearer {token}"))
                .header(header::CONTENT_TYPE, "application/json")
                .body(Body::from(
                    json!({
                        "api_name": api_name,
                        "api_version": api_version,
                        "username": "admin"
                    })
                    .to_string(),
                ))
                .unwrap(),
        )
        .await;

    tokio::time::sleep(std::time::Duration::from_millis(1_100)).await;
    // First request -> processed by gateway evaluation
    let response1 = app
        .clone()
        .oneshot(
            Request::builder()
                .method("GET")
                .uri(format!("/api/rest/{api_name}/{api_version}/hit"))
                .header(header::AUTHORIZATION, format!("Bearer {token}"))
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();

    // Second immediate request -> rate limit exceeded (429 or 502 upstream unreachable)
    let response2 = app
        .clone()
        .oneshot(
            Request::builder()
                .method("GET")
                .uri(format!("/api/rest/{api_name}/{api_version}/hit"))
                .header(header::AUTHORIZATION, format!("Bearer {token}"))
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();
    assert_eq!(response1.status(), StatusCode::OK);
    assert_eq!(response2.status(), StatusCode::TOO_MANY_REQUESTS);
    tokio::time::sleep(std::time::Duration::from_millis(1_100)).await;
    let (status, _) = authed_empty_response(
        &app,
        &token,
        Method::GET,
        &format!("/api/rest/{api_name}/{api_version}/hit"),
    )
    .await;
    assert_eq!(status, StatusCode::OK);
    upstream.abort();
}

async fn configure_tier_rate_gateway(
    app: &axum::Router,
    token: &str,
    api_name: &str,
    tier_id: &str,
    requests_per_minute: u64,
    upstream_url: &str,
) {
    // Match the Python fixture: the per-user limit must not mask the tier limit.
    let (status, _) = authed_json_response(
        app,
        token,
        Method::PUT,
        "/platform/user/admin",
        json!({
            "rate_limit_duration": 1_000_000,
            "rate_limit_duration_type": "second",
            "throttle_duration": 0,
            "throttle_duration_type": "second",
            "throttle_queue_limit": 0,
            "throttle_wait_duration": 0,
            "throttle_wait_duration_type": "second"
        }),
    )
    .await;
    assert!(status.is_success());

    let api = json!({
        "api_name": api_name,
        "api_version": "v1",
        "api_description": "tier rate-limit parity",
        "api_allowed_roles": ["admin"],
        "api_allowed_groups": ["ALL"],
        "api_servers": [upstream_url],
        "api_type": "REST",
        "active": true
    });
    let (status, _) = authed_json_response(app, token, Method::POST, "/platform/api", api).await;
    assert!(status.is_success());

    let endpoint = json!({
        "api_name": api_name,
        "api_version": "v1",
        "endpoint_method": "GET",
        "endpoint_uri": "/hit",
        "endpoint_description": "tier rate-limit endpoint"
    });
    let (status, _) =
        authed_json_response(app, token, Method::POST, "/platform/endpoint", endpoint).await;
    assert!(status.is_success());

    let subscription = json!({"api_name": api_name, "api_version": "v1", "username": "admin"});
    let (status, _) = authed_json_response(
        app,
        token,
        Method::POST,
        "/platform/subscription/subscribe",
        subscription,
    )
    .await;
    assert!(status.is_success());

    let tier = json!({
        "tier_id": tier_id,
        "name": "custom",
        "display_name": tier_id,
        "description": "tier rate-limit parity",
        "limits": {
            "requests_per_minute": requests_per_minute,
            "enable_throttling": false,
            "max_queue_time_ms": 0
        },
        "price_monthly": 0.0,
        "features": [],
        "is_default": false,
        "enabled": true
    });
    let (status, _) =
        authed_json_response(app, token, Method::POST, "/platform/tiers/", tier).await;
    assert!(status.is_success());

    let assignment = json!({"user_id": "admin", "tier_id": tier_id});
    let (status, _) = authed_json_response(
        app,
        token,
        Method::POST,
        "/platform/tiers/assignments",
        assignment,
    )
    .await;
    assert!(status.is_success());

    let (status, _) = authed_empty_response(app, token, Method::DELETE, "/api/caches").await;
    assert!(status.is_success());
}

async fn tier_gateway_request(app: &axum::Router, token: &str, api_name: &str) -> StatusCode {
    let (status, _) = authed_empty_response(
        app,
        token,
        Method::GET,
        &format!("/api/rest/{api_name}/v1/hit"),
    )
    .await;
    status
}
#[tokio::test]
async fn live_test_34_tier_rate_limiting_strict_local_parity() {
    let app = build_router(test_app_state().await);
    let token = login_admin(&app).await;
    let (upstream_url, upstream) = start_echo_upstream().await;

    configure_tier_rate_gateway(
        &app,
        &token,
        "tier-rate-strict-34",
        "tier-rate-strict-34",
        1,
        &upstream_url,
    )
    .await;

    assert_eq!(
        tier_gateway_request(&app, &token, "tier-rate-strict-34").await,
        StatusCode::OK
    );
    assert_eq!(
        tier_gateway_request(&app, &token, "tier-rate-strict-34").await,
        StatusCode::TOO_MANY_REQUESTS
    );
    upstream.abort();
}

#[tokio::test]
async fn live_test_34_tier_vs_user_limits_priority_parity() {
    let app = build_router(test_app_state().await);
    let token = login_admin(&app).await;
    let (upstream_url, upstream) = start_echo_upstream().await;

    configure_tier_rate_gateway(
        &app,
        &token,
        "tier-rate-priority-34",
        "tier-rate-priority-34",
        1,
        &upstream_url,
    )
    .await;

    // The helper sets a 1,000,000-request user limit; the tier must win at one request.
    assert_eq!(
        tier_gateway_request(&app, &token, "tier-rate-priority-34").await,
        StatusCode::OK
    );
    assert_eq!(
        tier_gateway_request(&app, &token, "tier-rate-priority-34").await,
        StatusCode::TOO_MANY_REQUESTS
    );
    upstream.abort();
}

#[tokio::test]
async fn live_test_34_tier_concurrent_requests_enforced_parity() {
    let app = build_router(test_app_state().await);
    let token = login_admin(&app).await;
    let (upstream_url, upstream) = start_echo_upstream().await;

    configure_tier_rate_gateway(
        &app,
        &token,
        "tier-rate-sequential-34",
        "tier-rate-sequential-34",
        2,
        &upstream_url,
    )
    .await;

    // Keep the pinned three-request/two-RPM batch inside one fixed minute. Without
    // this guard, a run beginning at :59 can split 2+1 across adjacent windows
    // and intermittently observe three successful requests.
    let second = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs()
        % 60;
    if second >= 55 {
        tokio::time::sleep(Duration::from_secs(61 - second)).await;
    }

    let results = [
        tier_gateway_request(&app, &token, "tier-rate-sequential-34").await,
        tier_gateway_request(&app, &token, "tier-rate-sequential-34").await,
        tier_gateway_request(&app, &token, "tier-rate-sequential-34").await,
    ];
    let successes = results
        .iter()
        .filter(|status| **status == StatusCode::OK)
        .count();
    let blocked = results
        .iter()
        .filter(|status| **status == StatusCode::TOO_MANY_REQUESTS)
        .count();
    // Preserve the Python assertion: at least one request makes it through and one is blocked.
    assert!(
        successes >= 1,
        "expected at least one success, got {successes}"
    );
    assert!(
        blocked >= 1,
        "expected at least one rate-limit response, got {blocked}"
    );
    upstream.abort();
}

#[tokio::test]
async fn live_test_45_soap_cors_preflight_parity() {
    let app = build_router(test_app_state().await);
    let token = login_admin(&app).await;
    let api_name = "soap-preflight-45";
    let api_version = "v1";

    let api = json!({"api_name": api_name, "api_version": api_version, "api_description": "SOAP preflight", "api_allowed_roles": ["admin"], "api_allowed_groups": ["ALL"], "api_servers": ["http://127.0.0.1:9"], "api_type": "SOAP", "active": true, "api_cors_allow_origins": ["http://example.com"], "api_cors_allow_methods": ["POST"], "api_cors_allow_headers": ["Content-Type"]});
    let (status, _) = authed_json_response(&app, &token, Method::POST, "/platform/api", api).await;
    assert!(status.is_success());
    let endpoint = json!({"api_name": api_name, "api_version": api_version, "endpoint_method": "POST", "endpoint_uri": "/soap", "endpoint_description": "SOAP preflight endpoint"});
    let (status, _) =
        authed_json_response(&app, &token, Method::POST, "/platform/endpoint", endpoint).await;
    assert!(status.is_success());
    let subscription =
        json!({"api_name": api_name, "api_version": api_version, "username": "admin"});
    let (status, _) = authed_json_response(
        &app,
        &token,
        Method::POST,
        "/platform/subscription/subscribe",
        subscription,
    )
    .await;
    assert!(status.is_success());

    let response = app
        .clone()
        .oneshot(
            Request::builder()
                .method(Method::OPTIONS)
                .uri(format!("/api/soap/{api_name}/{api_version}/soap"))
                .header(header::AUTHORIZATION, format!("Bearer {token}"))
                .header("origin", "http://example.com")
                .header("access-control-request-method", "POST")
                .header("access-control-request-headers", "Content-Type")
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();
    assert!(matches!(
        response.status(),
        StatusCode::OK | StatusCode::NO_CONTENT
    ));

    let (status, _) = authed_empty_response(
        &app,
        &token,
        Method::DELETE,
        &format!("/platform/api/{api_name}/{api_version}"),
    )
    .await;
    assert!(status.is_success());
}

#[tokio::test]
async fn live_test_46_nonexistent_endpoint_gateway_error_parity() {
    let app = build_router(test_app_state().await);
    let token = login_admin(&app).await;
    let api_name = "gateway-error-46";
    let api_version = "v1";

    let api = json!({"api_name": api_name, "api_version": api_version, "api_description": "missing endpoint", "api_allowed_roles": ["admin"], "api_allowed_groups": ["ALL"], "api_servers": ["http://127.0.0.1:9"], "api_type": "REST", "active": true});
    let (status, _) = authed_json_response(&app, &token, Method::POST, "/platform/api", api).await;
    assert!(status.is_success());
    let subscription =
        json!({"api_name": api_name, "api_version": api_version, "username": "admin"});
    let (status, _) = authed_json_response(
        &app,
        &token,
        Method::POST,
        "/platform/subscription/subscribe",
        subscription,
    )
    .await;
    assert!(status.is_success());

    let (status, body) = authed_empty_response(
        &app,
        &token,
        Method::GET,
        &format!("/api/rest/{api_name}/{api_version}/nope"),
    )
    .await;
    assert!(matches!(
        status,
        StatusCode::NOT_FOUND | StatusCode::BAD_REQUEST | StatusCode::INTERNAL_SERVER_ERROR
    ));
    let code = body
        .get("error_code")
        .or_else(|| body.pointer("/response/error_code"))
        .and_then(Value::as_str);
    assert!(matches!(
        code,
        Some("GTW003" | "GTW001" | "GTW002" | "GTW006")
    ));

    let (status, _) = authed_empty_response(
        &app,
        &token,
        Method::DELETE,
        &format!("/platform/api/{api_name}/{api_version}"),
    )
    .await;
    assert!(status.is_success());
}

#[tokio::test]
async fn live_test_41_soap_and_85_endpoint_validation_parity() {
    let state = test_app_state().await;
    let app = build_router(state);
    let token = login_admin(&app).await;

    let api_name = "soapval-test";
    let api_version = "v1";

    // Create API
    let response = app
        .clone()
        .oneshot(
            Request::builder()
                .method("POST")
                .uri("/platform/api")
                .header(header::AUTHORIZATION, format!("Bearer {token}"))
                .header(header::CONTENT_TYPE, "application/json")
                .body(Body::from(
                    json!({
                        "api_name": api_name,
                        "api_version": api_version,
                        "api_description": "soap val",
                        "api_allowed_roles": ["admin"],
                        "api_allowed_groups": ["ALL"],
                        "api_servers": ["http://127.0.0.1:9999"],
                        "api_type": "SOAP",
                        "active": true
                    })
                    .to_string(),
                ))
                .unwrap(),
        )
        .await
        .unwrap();
    assert!(response.status().is_success());

    // Create Endpoint
    let response = app
        .clone()
        .oneshot(
            Request::builder()
                .method("POST")
                .uri("/platform/endpoint")
                .header(header::AUTHORIZATION, format!("Bearer {token}"))
                .header(header::CONTENT_TYPE, "application/json")
                .body(Body::from(
                    json!({
                        "api_name": api_name,
                        "api_version": api_version,
                        "endpoint_method": "POST",
                        "endpoint_uri": "/add",
                        "endpoint_description": "soap add"
                    })
                    .to_string(),
                ))
                .unwrap(),
        )
        .await
        .unwrap();
    assert!(response.status().is_success());

    // Enable validation on endpoint via /platform/endpoint/endpoint/validation
    let response = app
        .clone()
        .oneshot(
            Request::builder()
                .method("GET")
                .uri(format!(
                    "/platform/endpoint/POST/{api_name}/{api_version}/add"
                ))
                .header(header::AUTHORIZATION, format!("Bearer {token}"))
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();
    assert_eq!(response.status(), StatusCode::OK);
    let bytes = to_bytes(response.into_body(), usize::MAX).await.unwrap();
    let ep: Value = serde_json::from_slice(&bytes).unwrap();
    let endpoint_id = ep["endpoint_id"].as_str().unwrap();

    let response = app
        .clone()
        .oneshot(
            Request::builder()
                .method("POST")
                .uri("/platform/endpoint/endpoint/validation")
                .header(header::AUTHORIZATION, format!("Bearer {token}"))
                .header(header::CONTENT_TYPE, "application/json")
                .body(Body::from(
                    json!({
                        "endpoint_id": endpoint_id,
                        "validation_enabled": true,
                        "validation_schema": {
                            "intA": {
                                "required": true,
                                "type": "string",
                                "min": 2
                            }
                        }
                    })
                    .to_string(),
                ))
                .unwrap(),
        )
        .await
        .unwrap();
    assert!(response.status().is_success());

    // Send invalid XML (<intA>1</intA> length 1 < min 2) -> 400 Bad Request
    let xml_invalid = r#"<?xml version="1.0" encoding="utf-8"?><soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"><soap:Body><Add><intA>1</intA></Add></soap:Body></soap:Envelope>"#;
    let response = app
        .clone()
        .oneshot(
            Request::builder()
                .method("POST")
                .uri(format!("/api/soap/{api_name}/{api_version}/add"))
                .header(header::AUTHORIZATION, format!("Bearer {token}"))
                .header(header::CONTENT_TYPE, "application/xml")
                .body(Body::from(xml_invalid))
                .unwrap(),
        )
        .await
        .unwrap();
    assert_eq!(response.status(), StatusCode::BAD_REQUEST);
}

#[tokio::test]
async fn live_test_90_security_tools_and_config_export_import_parity() {
    let state = test_app_state().await;
    let app = build_router(state);
    let token = login_admin(&app).await;

    // GET /platform/security/settings
    let response = app
        .clone()
        .oneshot(
            Request::builder()
                .method("GET")
                .uri("/platform/security/settings")
                .header(header::AUTHORIZATION, format!("Bearer {token}"))
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();
    assert_eq!(response.status(), StatusCode::OK);

    // POST /platform/tools/cors/check
    let response = app
        .clone()
        .oneshot(
            Request::builder()
                .method("POST")
                .uri("/platform/tools/cors/check")
                .header(header::AUTHORIZATION, format!("Bearer {token}"))
                .header(header::CONTENT_TYPE, "application/json")
                .body(Body::from(
                    json!({"origin": "http://localhost:3000"}).to_string(),
                ))
                .unwrap(),
        )
        .await
        .unwrap();
    assert_eq!(response.status(), StatusCode::OK);

    // GET /platform/config/export/all
    let response = app
        .clone()
        .oneshot(
            Request::builder()
                .method("GET")
                .uri("/platform/config/export/all")
                .header(header::AUTHORIZATION, format!("Bearer {token}"))
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();
    assert_eq!(response.status(), StatusCode::OK);
    let bytes = to_bytes(response.into_body(), usize::MAX).await.unwrap();
    let config_export: Value = serde_json::from_slice(&bytes).unwrap();

    // POST /platform/config/import
    let response = app
        .clone()
        .oneshot(
            Request::builder()
                .method("POST")
                .uri("/platform/config/import")
                .header(header::AUTHORIZATION, format!("Bearer {token}"))
                .header(header::CONTENT_TYPE, "application/json")
                .body(Body::from(config_export.to_string()))
                .unwrap(),
        )
        .await
        .unwrap();
    assert!(response.status().is_success());
}

async fn public_gateway_status(
    app: &axum::Router,
    method: Method,
    uri: impl AsRef<str>,
    content_type: Option<&str>,
    body: Body,
) -> StatusCode {
    let mut builder = Request::builder().method(method).uri(uri.as_ref());
    if let Some(content_type) = content_type {
        builder = builder.header(header::CONTENT_TYPE, content_type);
    }
    app.clone()
        .oneshot(builder.body(body).unwrap())
        .await
        .unwrap()
        .status()
}

#[tokio::test]
async fn live_test_93_public_and_auth_optional_allow_unauthenticated() {
    let app = build_router(test_app_state().await);
    let token = login_admin(&app).await;
    let (upstream_url, upstream) = start_echo_upstream().await;

    for (api_name, endpoint_uri, api_public, api_auth_required) in [
        ("public-auth-93", "/status", true, true),
        ("optional-auth-93", "/ping", false, false),
    ] {
        let (status, _) = authed_json_response(
            &app,
            &token,
            Method::POST,
            "/platform/api",
            json!({
                "api_name": api_name,
                "api_version": "v1",
                "api_description": "authentication mode parity",
                "api_allowed_roles": [],
                "api_allowed_groups": [],
                "api_servers": [&upstream_url],
                "api_type": "REST",
                "active": true,
                "api_public": api_public,
                "api_auth_required": api_auth_required
            }),
        )
        .await;
        assert!(status.is_success());

        let (status, _) = authed_json_response(
            &app,
            &token,
            Method::POST,
            "/platform/endpoint",
            json!({
                "api_name": api_name,
                "api_version": "v1",
                "endpoint_method": "GET",
                "endpoint_uri": endpoint_uri,
                "endpoint_description": endpoint_uri
            }),
        )
        .await;
        assert!(status.is_success());

        let status = public_gateway_status(
            &app,
            Method::GET,
            format!("/api/rest/{api_name}/v1{endpoint_uri}"),
            None,
            Body::empty(),
        )
        .await;
        assert_eq!(status, StatusCode::OK);
    }

    upstream.abort();
}

#[tokio::test]
async fn live_test_35_bulk_public_rest_crud_parity() {
    let app = build_router(test_app_state().await);
    let token = login_admin(&app).await;
    let (upstream_url, upstream) = start_echo_upstream().await;

    for index in 0..3 {
        let api_name = format!("bulk-public-rest-35-{index}");
        let api = json!({"api_name": api_name, "api_version": "v1", "api_description": "public REST bulk parity", "api_allowed_roles": [], "api_allowed_groups": [], "api_servers": [&upstream_url], "api_type": "SOAP", "active": true, "api_public": true});
        let (status, _) =
            authed_json_response(&app, &token, Method::POST, "/platform/api", api).await;
        assert!(status.is_success());

        for method in [Method::GET, Method::POST, Method::PUT, Method::DELETE] {
            let endpoint = json!({"api_name": api_name, "api_version": "v1", "endpoint_method": method.as_str(), "endpoint_uri": "/items", "endpoint_description": format!("{method} /items")});
            let (status, _) =
                authed_json_response(&app, &token, Method::POST, "/platform/endpoint", endpoint)
                    .await;
            assert!(status.is_success());
        }

        for method in [Method::GET, Method::POST, Method::PUT, Method::DELETE] {
            let body = if matches!(method, Method::POST | Method::PUT) {
                Body::from(json!({"name": "x"}).to_string())
            } else {
                Body::empty()
            };
            let status = public_gateway_status(
                &app,
                method,
                format!("/api/rest/{api_name}/v1/items"),
                Some("application/json"),
                body,
            )
            .await;
            assert_eq!(status, StatusCode::OK);
        }
    }
    upstream.abort();
}

async fn bulk_soap_echo() -> Response {
    Response::builder()
        .status(StatusCode::OK)
        .header(header::CONTENT_TYPE, "text/xml; charset=utf-8")
        .body(Body::from(
            "<soap:Envelope xmlns:soap=\"http://schemas.xmlsoap.org/soap/envelope/\"><soap:Body><Ok/></soap:Body></soap:Envelope>",
        ))
        .unwrap()
}

async fn start_bulk_soap_upstream() -> (String, JoinHandle<()>) {
    let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
    let address = listener.local_addr().unwrap();
    let server = tokio::spawn(async move {
        axum::serve(
            listener,
            Router::new()
                .route("/create", any(bulk_soap_echo))
                .route("/read", any(bulk_soap_echo))
                .route("/update", any(bulk_soap_echo))
                .route("/delete", any(bulk_soap_echo))
                .route("/soap", any(bulk_soap_echo)),
        )
        .await
        .unwrap();
    });
    (format!("http://{address}"), server)
}

async fn graphql_hello(Json(payload): Json<Value>) -> Json<Value> {
    assert_eq!(payload["query"], "{ hello(name:\"Doorman\") }");
    Json(json!({"data": {"hello": "Hello, Doorman!"}}))
}

async fn start_graphql_upstream() -> (String, JoinHandle<()>) {
    let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
    let address = listener.local_addr().unwrap();
    let server = tokio::spawn(async move {
        axum::serve(
            listener,
            Router::new().route("/graphql", axum::routing::post(graphql_hello)),
        )
        .await
        .unwrap();
    });
    (format!("http://{address}"), server)
}

async fn graphql_variable_hello(Json(payload): Json<Value>) -> Json<Value> {
    assert_eq!(
        payload["query"],
        "query HelloOp($x: String!) { hello(name: $x) }"
    );
    let name = payload["variables"]["x"].as_str().unwrap();
    Json(json!({"data": {"hello": format!("Hello, {name}!")}}))
}

async fn start_graphql_validation_upstream() -> (String, JoinHandle<()>) {
    let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
    let address = listener.local_addr().unwrap();
    let server = tokio::spawn(async move {
        axum::serve(
            listener,
            Router::new().route("/graphql", axum::routing::post(graphql_variable_hello)),
        )
        .await
        .unwrap();
    });
    (format!("http://{address}"), server)
}

#[tokio::test]
async fn live_test_35_bulk_public_soap_crud_parity() {
    let app = build_router(test_app_state().await);
    let token = login_admin(&app).await;
    let (upstream_url, upstream) = start_bulk_soap_upstream().await;

    let envelope = "<?xml version=\"1.0\"?><soap:Envelope xmlns:soap=\"http://schemas.xmlsoap.org/soap/envelope/\"><soap:Body><Op/></soap:Body></soap:Envelope>";

    for index in 0..3 {
        let api_name = format!("bulk-public-soap-35-{index}");
        let api = json!({"api_name": api_name, "api_version": "v1", "api_description": "public SOAP bulk parity", "api_allowed_roles": [], "api_allowed_groups": [], "api_servers": [&upstream_url], "api_type": "REST", "active": true, "api_public": true});
        let (status, _) =
            authed_json_response(&app, &token, Method::POST, "/platform/api", api).await;
        assert!(status.is_success());

        for endpoint_uri in ["/create", "/read", "/update", "/delete"] {
            let endpoint = json!({"api_name": api_name, "api_version": "v1", "endpoint_method": "POST", "endpoint_uri": endpoint_uri, "endpoint_description": format!("SOAP {endpoint_uri}")});
            let (status, _) =
                authed_json_response(&app, &token, Method::POST, "/platform/endpoint", endpoint)
                    .await;
            assert!(status.is_success());
        }

        for endpoint_uri in ["create", "read", "update", "delete"] {
            let status = public_gateway_status(
                &app,
                Method::POST,
                format!("/api/soap/{api_name}/v1/{endpoint_uri}"),
                Some("text/xml"),
                Body::from(envelope),
            )
            .await;
            assert_eq!(status, StatusCode::OK);
        }
    }
    upstream.abort();
}

#[tokio::test]
async fn live_test_40_soap_gateway_basic_flow_parity() {
    let app = build_router(test_app_state().await);
    let token = login_admin(&app).await;
    let (upstream_url, upstream) = start_bulk_soap_upstream().await;
    let api_name = "soap-gateway-40";

    let api = json!({"api_name": api_name, "api_version": "v1", "api_description": "SOAP gateway parity", "api_allowed_roles": ["admin"], "api_allowed_groups": ["ALL"], "api_servers": [upstream_url], "api_type": "SOAP", "api_allowed_retry_count": 0, "active": true});
    let (status, _) = authed_json_response(&app, &token, Method::POST, "/platform/api", api).await;
    assert!(status.is_success());
    let endpoint = json!({"api_name": api_name, "api_version": "v1", "endpoint_method": "POST", "endpoint_uri": "/soap", "endpoint_description": "SOAP gateway endpoint"});
    let (status, _) =
        authed_json_response(&app, &token, Method::POST, "/platform/endpoint", endpoint).await;
    assert!(status.is_success());
    let subscription = json!({"api_name": api_name, "api_version": "v1", "username": "admin"});
    let (status, _) = authed_json_response(
        &app,
        &token,
        Method::POST,
        "/platform/subscription/subscribe",
        subscription,
    )
    .await;
    assert!(status.is_success());

    let envelope = "<?xml version=\"1.0\"?><soap:Envelope xmlns:soap=\"http://schemas.xmlsoap.org/soap/envelope/\"><soap:Body><Op/></soap:Body></soap:Envelope>";
    let response = app
        .clone()
        .oneshot(
            Request::builder()
                .method(Method::POST)
                .uri(format!("/api/soap/{api_name}/v1/soap"))
                .header(header::AUTHORIZATION, format!("Bearer {token}"))
                .header(header::CONTENT_TYPE, "text/xml")
                .header("soapaction", "urn:local-op")
                .body(Body::from(envelope))
                .unwrap(),
        )
        .await
        .unwrap();
    assert_eq!(response.status(), StatusCode::OK);
    upstream.abort();
}

#[tokio::test]
async fn live_test_50_graphql_gateway_basic_flow_parity() {
    let app = build_router(test_app_state().await);
    let token = login_admin(&app).await;
    let (upstream_url, upstream) = start_graphql_upstream().await;
    let api_name = "graphql-gateway-50";
    let api_version = "v1";

    let api = json!({
        "api_name": api_name,
        "api_version": api_version,
        "api_description": "GraphQL demo",
        "api_allowed_roles": ["admin"],
        "api_allowed_groups": ["ALL"],
        "api_servers": [upstream_url],
        "api_type": "GRAPHQL",
        "api_allowed_retry_count": 0,
        "active": true,
    });
    let (status, _) = authed_json_response(&app, &token, Method::POST, "/platform/api", api).await;
    assert!(status.is_success());

    let endpoint = json!({
        "api_name": api_name,
        "api_version": api_version,
        "endpoint_method": "POST",
        "endpoint_uri": "/graphql",
        "endpoint_description": "graphql",
    });
    let (status, _) =
        authed_json_response(&app, &token, Method::POST, "/platform/endpoint", endpoint).await;
    assert!(status.is_success());

    let subscription =
        json!({"api_name": api_name, "api_version": api_version, "username": "admin"});
    let (status, _) = authed_json_response(
        &app,
        &token,
        Method::POST,
        "/platform/subscription/subscribe",
        subscription,
    )
    .await;
    assert!(status.is_success());

    let response = app
        .clone()
        .oneshot(
            Request::builder()
                .method(Method::POST)
                .uri(format!("/api/graphql/{api_name}"))
                .header(header::AUTHORIZATION, format!("Bearer {token}"))
                .header(header::CONTENT_TYPE, "application/json")
                .header("x-api-version", api_version)
                .body(Body::from(
                    json!({"query": "{ hello(name:\"Doorman\") }"}).to_string(),
                ))
                .unwrap(),
        )
        .await
        .unwrap();
    let (status, body) = response_json(response).await;
    assert_eq!(status, StatusCode::OK);
    assert_eq!(body["data"]["hello"], "Hello, Doorman!");

    let (status, _) = authed_empty_response(
        &app,
        &token,
        Method::DELETE,
        &format!("/platform/endpoint/POST/{api_name}/{api_version}/graphql"),
    )
    .await;
    assert!(status.is_success());
    let (status, _) = authed_empty_response(
        &app,
        &token,
        Method::DELETE,
        &format!("/platform/api/{api_name}/{api_version}"),
    )
    .await;
    assert!(status.is_success());
    upstream.abort();
}

#[tokio::test]
async fn live_test_52_graphql_validation_blocks_invalid_variables_parity() {
    let app = build_router(test_app_state().await);
    let token = login_admin(&app).await;
    let (upstream_url, upstream) = start_graphql_validation_upstream().await;
    let api_name = "graphql-validation-52";
    let api_version = "v1";

    let api = json!({
        "api_name": api_name,
        "api_version": api_version,
        "api_description": "gql val",
        "api_allowed_roles": ["admin"],
        "api_allowed_groups": ["ALL"],
        "api_servers": [upstream_url],
        "api_type": "GRAPHQL",
        "active": true,
    });
    let (status, _) = authed_json_response(&app, &token, Method::POST, "/platform/api", api).await;
    assert!(status.is_success());

    let endpoint = json!({
        "api_name": api_name,
        "api_version": api_version,
        "endpoint_method": "POST",
        "endpoint_uri": "/graphql",
        "endpoint_description": "gql",
    });
    let (status, _) =
        authed_json_response(&app, &token, Method::POST, "/platform/endpoint", endpoint).await;
    assert!(status.is_success());

    let subscription =
        json!({"api_name": api_name, "api_version": api_version, "username": "admin"});
    let (status, _) = authed_json_response(
        &app,
        &token,
        Method::POST,
        "/platform/subscription/subscribe",
        subscription,
    )
    .await;
    assert!(status.is_success());

    let (status, endpoint) = authed_empty_response(
        &app,
        &token,
        Method::GET,
        &format!("/platform/endpoint/POST/{api_name}/{api_version}/graphql"),
    )
    .await;
    assert_eq!(status, StatusCode::OK);
    let endpoint_id = endpoint["endpoint_id"].as_str().unwrap();

    let validation = json!({
        "endpoint_id": endpoint_id,
        "validation_enabled": true,
        "validation_schema": {
            "validation_schema": {
                "HelloOp.x": {"required": true, "type": "string", "min": 2}
            }
        }
    });
    let (status, _) = authed_json_response(
        &app,
        &token,
        Method::POST,
        "/platform/endpoint/endpoint/validation",
        validation,
    )
    .await;
    assert!(status.is_success());

    let graphql_request = |value: &str| {
        Request::builder()
            .method(Method::POST)
            .uri(format!("/api/graphql/{api_name}"))
            .header(header::AUTHORIZATION, format!("Bearer {token}"))
            .header(header::CONTENT_TYPE, "application/json")
            .header("x-api-version", api_version)
            .body(Body::from(
                json!({
                    "query": "query HelloOp($x: String!) { hello(name: $x) }",
                    "variables": {"x": value}
                })
                .to_string(),
            ))
            .unwrap()
    };

    let response = app.clone().oneshot(graphql_request("A")).await.unwrap();
    assert_eq!(response.status(), StatusCode::BAD_REQUEST);

    let response = app.clone().oneshot(graphql_request("Alan")).await.unwrap();
    let (status, body) = response_json(response).await;
    assert_eq!(status, StatusCode::OK);
    assert_eq!(body["data"]["hello"], "Hello, Alan!");
    upstream.abort();
}
