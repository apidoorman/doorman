use axum::{
    Json, Router,
    body::{Body, Bytes, to_bytes},
    http::{HeaderMap, Method, Uri},
    routing::{any, get},
};
use doorman_gateway::{AppState, Config, GatewayMode, build_router};
use http::{Request, StatusCode};
use serde_json::{Value, json};
use tower::ServiceExt;

#[tokio::test]
async fn rust_health_matches_public_contract() {
    let config = Config::for_test(GatewayMode::On, "http://127.0.0.1:9".to_owned());
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
async fn off_mode_proxies_to_python() {
    let (python_url, server) =
        spawn_python(Router::new().route("/platform/ping", get(|| async { "python" }))).await;
    let config = Config::for_test(GatewayMode::Off, python_url);
    let app = build_router(AppState::new(config).unwrap());
    let response = app
        .oneshot(
            Request::builder()
                .uri("/platform/ping")
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();

    assert_eq!(response.status(), StatusCode::OK);
    assert_eq!(
        to_bytes(response.into_body(), 1024).await.unwrap(),
        "python"
    );
    server.abort();
}

#[tokio::test]
async fn proxy_preserves_method_query_headers_body_and_response_headers() {
    async fn echo(
        method: Method,
        uri: Uri,
        headers: HeaderMap,
        body: Bytes,
    ) -> (StatusCode, [(String, String); 1], Json<Value>) {
        (
            StatusCode::CREATED,
            [("x-python".to_owned(), "true".to_owned())],
            Json(json!({
                "method": method.as_str(),
                "path_and_query": uri.path_and_query().unwrap().as_str(),
                "x-test": headers.get("x-test").unwrap().to_str().unwrap(),
                "body": String::from_utf8(body.to_vec()).unwrap(),
            })),
        )
    }

    let (python_url, server) = spawn_python(Router::new().route("/platform/echo", any(echo))).await;
    let app = build_router(AppState::new(Config::for_test(GatewayMode::Off, python_url)).unwrap());
    let response = app
        .oneshot(
            Request::builder()
                .method(Method::POST)
                .uri("/platform/echo?value=1")
                .header("x-test", "forwarded")
                .body(Body::from("payload"))
                .unwrap(),
        )
        .await
        .unwrap();

    assert_eq!(response.status(), StatusCode::CREATED);
    assert_eq!(response.headers().get("x-python").unwrap(), "true");
    let body: Value =
        serde_json::from_slice(&to_bytes(response.into_body(), 4096).await.unwrap()).unwrap();
    assert_eq!(body["method"], "POST");
    assert_eq!(body["path_and_query"], "/platform/echo?value=1");
    assert_eq!(body["x-test"], "forwarded");
    assert_eq!(body["body"], "payload");
    server.abort();
}

#[tokio::test]
async fn enabled_mode_preserves_original_uri_for_unported_api_routes() {
    async fn echo_uri(uri: Uri) -> String {
        uri.path_and_query().unwrap().as_str().to_owned()
    }

    let (python_url, server) =
        spawn_python(Router::new().route("/api/rest/demo/v1/items", any(echo_uri))).await;
    let app = build_router(AppState::new(Config::for_test(GatewayMode::On, python_url)).unwrap());
    let response = app
        .oneshot(
            Request::builder()
                .uri("/api/rest/demo/v1/items?page=2")
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();

    assert_eq!(response.status(), StatusCode::OK);
    assert_eq!(
        to_bytes(response.into_body(), 1024).await.unwrap(),
        "/api/rest/demo/v1/items?page=2"
    );
    server.abort();
}

async fn spawn_python(app: Router) -> (String, tokio::task::JoinHandle<()>) {
    let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
    let address = listener.local_addr().unwrap();
    let server = tokio::spawn(async move { axum::serve(listener, app).await.unwrap() });
    (format!("http://{address}"), server)
}
