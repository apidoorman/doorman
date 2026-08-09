use axum::{
    Json, Router,
    body::{Body, to_bytes},
    http::{Method, Uri},
    routing::{any, get},
};
use doorman_gateway::storage::models::PolicyDocuments;
use doorman_gateway::{AppState, Config, build_router};
use http::{Request, StatusCode};
use serde_json::{Value, json};
use tower::ServiceExt;

#[tokio::test]
async fn rust_health_matches_public_contract() {
    let config = Config::for_test("http://127.0.0.1:9".to_owned());
    let app = build_router(AppState::new(config).unwrap());
    let response = app
        .oneshot(
            Request::builder()
                .uri("/api/health")
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();

    assert_eq!(response.status(), StatusCode::OK);
    assert!(response.headers().contains_key("x-request-id"));
    assert!(response.headers().contains_key("request_id"));
    assert_eq!(
        to_bytes(response.into_body(), 1024).await.unwrap(),
        r#"{"status":"online"}"#
    );
}

#[tokio::test]
async fn platform_routes_are_native_and_never_use_an_internal_backend() {
    let (upstream_url, server) =
        spawn_upstream(Router::new().route("/platform/ping", get(|| async { "upstream" }))).await;
    let app = build_router(AppState::new(Config::for_test(upstream_url)).unwrap());
    let response = app
        .oneshot(
            Request::builder()
                .uri("/platform/ping")
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();

    assert_eq!(response.status(), StatusCode::UNAUTHORIZED);
    server.abort();
}

#[tokio::test]
async fn public_health_never_uses_an_internal_backend() {
    let (upstream_url, server) = spawn_upstream(Router::new().route(
        "/api/health",
        get(|| async { Json(json!({ "status": "upstream" })) }),
    ))
    .await;
    let config = Config::for_test(upstream_url);
    let app = build_router(AppState::new(config).unwrap());
    let response = app
        .oneshot(
            Request::builder()
                .uri("/api/health")
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();

    assert_eq!(response.status(), StatusCode::OK);
    assert_eq!(
        to_bytes(response.into_body(), 1024).await.unwrap(),
        r#"{"status":"online"}"#
    );
    server.abort();
}

#[tokio::test]
async fn public_health_never_uses_an_alternate_backend() {
    let (upstream_url, server) = spawn_upstream(Router::new().route(
        "/api/health",
        get(|| async { Json(json!({ "status": "upstream" })) }),
    ))
    .await;
    let config = Config::for_test(upstream_url);
    let app = build_router(AppState::new(config).unwrap());
    let response = app
        .oneshot(
            Request::builder()
                .uri("/api/health")
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();

    assert_eq!(response.status(), StatusCode::OK);
    assert_eq!(
        to_bytes(response.into_body(), 1024).await.unwrap(),
        r#"{"status":"online"}"#
    );
    server.abort();
}

#[tokio::test]
async fn rust_serves_health_independent_of_removed_rollout_flags() {
    let config = Config::for_test("http://127.0.0.1:9".to_owned());
    let app = build_router(AppState::new(config).unwrap());
    let response = app
        .oneshot(
            Request::builder()
                .uri("/api/health")
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();

    assert_eq!(response.status(), StatusCode::OK);
    assert_eq!(
        to_bytes(response.into_body(), 1024).await.unwrap(),
        r#"{"status":"online"}"#
    );
}

#[tokio::test]
async fn platform_requests_are_not_forwarded_to_an_internal_backend() {
    let (upstream_url, server) = spawn_upstream(
        Router::new().route("/platform/echo", any(|| async { StatusCode::IM_A_TEAPOT })),
    )
    .await;
    let app = build_router(AppState::new(Config::for_test(upstream_url)).unwrap());
    let response = app
        .oneshot(
            Request::builder()
                .method(Method::POST)
                .uri("/platform/echo?value=1")
                .body(Body::from("payload"))
                .unwrap(),
        )
        .await
        .unwrap();

    assert_eq!(response.status(), StatusCode::UNAUTHORIZED);
    server.abort();
}

#[tokio::test]
async fn spoofed_forwarding_headers_do_not_enable_platform_access() {
    let (upstream_url, server) =
        spawn_upstream(Router::new().route("/platform/headers", any(|| async { StatusCode::OK })))
            .await;
    let app = build_router(AppState::new(Config::for_test(upstream_url)).unwrap());
    let response = app
        .oneshot(
            Request::builder()
                .uri("/platform/headers")
                .header("x-forwarded-for", "203.0.113.10")
                .header("x-real-ip", "203.0.113.11")
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();

    assert_eq!(response.status(), StatusCode::UNAUTHORIZED);
    server.abort();
}

#[tokio::test]
async fn rust_fails_closed_without_policy_storage() {
    async fn echo_uri(uri: Uri) -> String {
        uri.path_and_query().unwrap().as_str().to_owned()
    }

    let (upstream_url, server) =
        spawn_upstream(Router::new().route("/api/rest/demo/v1/items", any(echo_uri))).await;
    let app = build_router(AppState::new(Config::for_test(upstream_url)).unwrap());
    let response = app
        .oneshot(
            Request::builder()
                .uri("/api/rest/demo/v1/items?page=2")
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();

    assert_eq!(response.status(), StatusCode::SERVICE_UNAVAILABLE);
    assert_eq!(
        to_bytes(response.into_body(), 1024).await.unwrap(),
        r#"{"error_code":"GTW006","error_message":"Gateway state store unavailable"}"#
    );
    server.abort();
}

#[tokio::test]
async fn rust_serves_status_unauthorized_from_rust() {
    let config = Config::for_test("http://127.0.0.1:9".to_owned());
    let app = build_router(AppState::new(config).unwrap());
    let response = app
        .oneshot(
            Request::builder()
                .uri("/api/status")
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();

    assert_eq!(response.status(), StatusCode::UNAUTHORIZED);
    assert!(response.headers().contains_key("x-request-id"));
    assert!(response.headers().contains_key("request_id"));
    assert_eq!(
        to_bytes(response.into_body(), 1024).await.unwrap(),
        r#"{"error_code":"GTW401","error_message":"Unauthorized"}"#
    );
}

#[tokio::test]
async fn rust_handles_invalid_status_auth_locally() {
    let (upstream_url, server) = spawn_upstream(Router::new().route(
        "/api/status",
        any(|| async { Json(json!({ "status": "upstream" })) }),
    ))
    .await;
    let app = build_router(AppState::new(Config::for_test(upstream_url)).unwrap());
    let response = app
        .oneshot(
            Request::builder()
                .uri("/api/status")
                .header("cookie", "theme=dark; access_token_cookie=token")
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();

    assert_eq!(response.status(), StatusCode::UNAUTHORIZED);
    assert_eq!(
        to_bytes(response.into_body(), 1024).await.unwrap(),
        r#"{"error_code":"GTW401","error_message":"Unauthorized"}"#
    );
    server.abort();
}

#[tokio::test]
async fn rust_serves_caches_preflight_from_rust() {
    let config = Config::for_test("http://127.0.0.1:9".to_owned());
    let app = build_router(AppState::new(config).unwrap());
    let response = app
        .oneshot(
            Request::builder()
                .method(Method::OPTIONS)
                .uri("/api/caches")
                .header("origin", "http://localhost:3000")
                .header("access-control-request-method", "DELETE")
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();

    assert_eq!(response.status(), StatusCode::NO_CONTENT);
    assert!(response.headers().contains_key("x-request-id"));
    assert!(response.headers().contains_key("request_id"));
    assert_eq!(to_bytes(response.into_body(), 1024).await.unwrap(), "");
}

#[tokio::test]
async fn rust_handles_cache_delete_locally() {
    async fn echo_method(method: Method) -> Json<Value> {
        Json(json!({ "method": method.as_str() }))
    }

    let (upstream_url, server) =
        spawn_upstream(Router::new().route("/api/caches", any(echo_method))).await;
    let app = build_router(AppState::new(Config::for_test(upstream_url)).unwrap());
    let response = app
        .oneshot(
            Request::builder()
                .method(Method::DELETE)
                .uri("/api/caches")
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();

    assert_eq!(response.status(), StatusCode::UNAUTHORIZED);
    assert_eq!(
        to_bytes(response.into_body(), 1024).await.unwrap(),
        r#"{"error_code":"GTW401","error_message":"Unauthorized"}"#
    );
    server.abort();
}

#[tokio::test]
async fn rust_preflight_fails_closed_without_policy_storage() {
    async fn echo_uri(method: Method, uri: Uri) -> String {
        format!(
            "{} {}",
            method.as_str(),
            uri.path_and_query().unwrap().as_str()
        )
    }

    let (upstream_url, server) =
        spawn_upstream(Router::new().route("/api/rest/demo/v1/items", any(echo_uri))).await;
    let app = build_router(AppState::new(Config::for_test(upstream_url)).unwrap());
    let response = app
        .oneshot(
            Request::builder()
                .method(Method::OPTIONS)
                .uri("/api/rest/demo/v1/items?page=2")
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();

    assert_eq!(response.status(), StatusCode::SERVICE_UNAVAILABLE);
    assert_eq!(
        to_bytes(response.into_body(), 1024).await.unwrap(),
        r#"{"error_code":"GTW006","error_message":"Gateway state store unavailable"}"#
    );
    server.abort();
}

#[tokio::test]
async fn rust_rejects_unported_health_methods_in_rust() {
    let (upstream_url, server) = spawn_upstream(
        Router::new().route("/api/health", any(|| async { "upstream health method" })),
    )
    .await;
    let app = build_router(AppState::new(Config::for_test(upstream_url)).unwrap());
    let response = app
        .oneshot(
            Request::builder()
                .method(Method::POST)
                .uri("/api/health")
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();

    assert_eq!(response.status(), StatusCode::METHOD_NOT_ALLOWED);
    assert!(
        to_bytes(response.into_body(), 1024)
            .await
            .unwrap()
            .is_empty()
    );
    server.abort();
}

#[tokio::test]
async fn missing_endpoint_fails_closed_without_a_fallback() {
    let (upstream_url, server) = spawn_upstream(Router::new().route(
        "/api/rest/demo/v1/missing",
        any(|| async { "upstream fallback" }),
    ))
    .await;
    let config = Config::for_test(upstream_url);
    let state = AppState::new(config)
        .unwrap()
        .with_policy_documents(PolicyDocuments {
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
        });
    let app = build_router(state);
    let response = app
        .oneshot(
            Request::builder()
                .uri("/api/rest/demo/v1/missing")
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();

    assert_eq!(response.status(), StatusCode::NOT_FOUND);
    assert_eq!(
        to_bytes(response.into_body(), 1024).await.unwrap(),
        r#"{"error_code":"GTW003","error_message":"Endpoint does not exist for the requested API"}"#
    );
    server.abort();
}

#[tokio::test]
async fn rust_policy_enforcement_rejects_rest_before_upstream() {
    let (upstream_url, server) = spawn_upstream(Router::new().route(
        "/api/rest/demo/v1/missing",
        any(|| async { "upstream fallback" }),
    ))
    .await;
    let config = Config::for_test(upstream_url);
    let state = AppState::new(config)
        .unwrap()
        .with_policy_documents(PolicyDocuments {
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
        });
    let app = build_router(state);
    let response = app
        .oneshot(
            Request::builder()
                .uri("/api/rest/demo/v1/missing")
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();

    assert_eq!(response.status(), StatusCode::NOT_FOUND);
    assert_eq!(
        to_bytes(response.into_body(), 1024).await.unwrap(),
        r#"{"error_code":"GTW003","error_message":"Endpoint does not exist for the requested API"}"#
    );
    server.abort();
}

#[tokio::test]
async fn graphql_nested_route_uses_the_original_public_uri() {
    let (upstream_url, server) = spawn_upstream(Router::new().route(
        "/graphql",
        any(|| async { Json(json!({"data": {"ok": true}})) }),
    ))
    .await;
    let state = AppState::new(Config::for_test("http://127.0.0.1:9".to_owned()))
        .unwrap()
        .with_policy_documents(PolicyDocuments {
            apis: vec![json!({
                "api_id": "api-graphql",
                "api_name": "catalog",
                "api_version": "v1",
                "api_public": true,
                "api_servers": [upstream_url],
            })],
            endpoints: vec![json!({
                "api_name": "catalog",
                "api_version": "v1",
                "endpoint_method": "POST",
                "client_uri": "/graphql",
                "endpoint_uri": "/graphql",
            })],
            ..Default::default()
        });
    let response = build_router(state)
        .oneshot(
            Request::builder()
                .method(Method::POST)
                .uri("/api/graphql/catalog")
                .header("content-type", "application/json")
                .header("x-api-version", "v1")
                .body(Body::from(r#"{"query":"{ ok }"}"#))
                .unwrap(),
        )
        .await
        .unwrap();

    assert_eq!(response.status(), StatusCode::OK);
    let body: Value =
        serde_json::from_slice(&to_bytes(response.into_body(), 4096).await.unwrap()).unwrap();
    assert_eq!(body, json!({"data": {"ok": true}}));
    server.abort();
}

#[tokio::test]
async fn soap_nested_route_uses_the_original_public_uri() {
    let (upstream_url, server) = spawn_upstream(Router::new().route(
        "/soap",
        any(|| async {
            (
                [("content-type", "application/xml")],
                "<Envelope><Body><Pong/></Body></Envelope>",
            )
        }),
    ))
    .await;
    let state = AppState::new(Config::for_test("http://127.0.0.1:9".to_owned()))
        .unwrap()
        .with_policy_documents(PolicyDocuments {
            apis: vec![json!({
                "api_id": "api-soap",
                "api_name": "billing",
                "api_version": "v1",
                "api_public": true,
                "api_servers": [upstream_url],
            })],
            endpoints: vec![json!({
                "api_name": "billing",
                "api_version": "v1",
                "endpoint_method": "POST",
                "client_uri": "/soap",
                "endpoint_uri": "/soap",
            })],
            ..Default::default()
        });
    let envelope = r#"<?xml version="1.0"?><soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"><soap:Body><Ping/></soap:Body></soap:Envelope>"#;
    let response = build_router(state)
        .oneshot(
            Request::builder()
                .method(Method::POST)
                .uri("/api/soap/billing/v1/soap")
                .header("content-type", "text/xml")
                .body(Body::from(envelope))
                .unwrap(),
        )
        .await
        .unwrap();

    assert_eq!(response.status(), StatusCode::OK);
    let body = to_bytes(response.into_body(), 4096).await.unwrap();
    assert_eq!(body, "<Envelope><Body><Pong/></Body></Envelope>");
    server.abort();
}

#[tokio::test]
async fn rust_compresses_large_gateway_responses_when_requested() {
    let (upstream_url, server) =
        spawn_upstream(Router::new().route("/large", get(|| async { "x".repeat(800) }))).await;
    let config = Config::for_test("http://127.0.0.1:9".to_owned());
    let state = AppState::new(config)
        .unwrap()
        .with_policy_documents(PolicyDocuments {
            apis: vec![json!({
                "api_id": "api-compression",
                "api_name": "compressed",
                "api_version": "v1",
                "api_public": true,
                "api_servers": [upstream_url],
            })],
            endpoints: vec![json!({
                "api_name": "compressed",
                "api_version": "v1",
                "endpoint_method": "GET",
                "client_uri": "/large",
                "endpoint_uri": "/large",
            })],
            ..Default::default()
        });
    let response = build_router(state)
        .oneshot(
            Request::builder()
                .uri("/api/rest/compressed/v1/large")
                .header("accept-encoding", "gzip")
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();

    assert_eq!(response.status(), StatusCode::OK);
    assert_eq!(response.headers()["content-encoding"], "gzip");
    assert!(
        response.headers()["vary"]
            .to_str()
            .unwrap()
            .contains("accept-encoding")
    );
    let body = to_bytes(response.into_body(), 4096).await.unwrap();
    assert_eq!(&body[..2], &[0x1f, 0x8b]);
    server.abort();
}

async fn spawn_upstream(app: Router) -> (String, tokio::task::JoinHandle<()>) {
    let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
    let address = listener.local_addr().unwrap();
    let server = tokio::spawn(async move { axum::serve(listener, app).await.unwrap() });
    (format!("http://{address}"), server)
}

#[tokio::test]
async fn preflight_fails_closed_without_storage() {
    async fn upstream_options(method: Method) -> String {
        format!("upstream {}", method.as_str())
    }

    let (upstream_url, server) =
        spawn_upstream(Router::new().route("/api/rest/demo/v1/items", any(upstream_options))).await;
    let app = build_router(AppState::new(Config::for_test(upstream_url)).unwrap());
    let response = app
        .oneshot(
            Request::builder()
                .method(Method::OPTIONS)
                .uri("/api/rest/demo/v1/items")
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();

    assert_eq!(response.status(), StatusCode::SERVICE_UNAVAILABLE);
    assert_eq!(
        to_bytes(response.into_body(), 1024).await.unwrap(),
        r#"{"error_code":"GTW006","error_message":"Gateway state store unavailable"}"#
    );
    server.abort();
}

#[tokio::test]
async fn oversized_rest_body_returns_legacy_413_without_reaching_upstream() {
    let (upstream_url, server) =
        spawn_upstream(Router::new().route("/items", any(|| async { StatusCode::IM_A_TEAPOT })))
            .await;
    let state = AppState::new(Config::for_test("removed-internal-backend".to_owned()))
        .unwrap()
        .with_policy_documents(PolicyDocuments {
            apis: vec![json!({
                "api_id": "api-body-limit",
                "api_name": "limited",
                "api_version": "v1",
                "api_public": true,
                "api_servers": [upstream_url],
            })],
            endpoints: vec![json!({
                "api_name": "limited",
                "api_version": "v1",
                "endpoint_method": "POST",
                "client_uri": "/items",
                "endpoint_uri": "/items",
            })],
            ..Default::default()
        });
    let response = build_router(state)
        .oneshot(
            Request::builder()
                .method(Method::POST)
                .uri("/api/rest/limited/v1/items")
                .header("content-type", "application/json")
                .body(Body::from(vec![b'x'; 1024 * 1024 + 1]))
                .unwrap(),
        )
        .await
        .unwrap();

    assert_eq!(response.status(), StatusCode::PAYLOAD_TOO_LARGE);
    let body: Value =
        serde_json::from_slice(&to_bytes(response.into_body(), 1024).await.unwrap()).unwrap();
    assert_eq!(body["error_code"], "GTW013");
    assert_eq!(body["error_message"], "Request body too large");
    server.abort();
}
