use std::sync::Arc;

use axum::body::{Body, to_bytes};
use doorman_gateway::{AppState, Config, build_router, storage::runtime::SharedStorage};
use http::{Method, Request, StatusCode, header};
use serde_json::{Value, json};
use tower::ServiceExt;

const ADMIN_EMAIL: &str = "admin@doorman.dev";
const ADMIN_PASSWORD: &str = "AdminPassword123!";
const LIMITED_EMAIL: &str = "limited@doorman.dev";
const LIMITED_PASSWORD: &str = "LimitedPassword123!";
const MANAGER_EMAIL: &str = "security-manager@doorman.dev";
const MANAGER_PASSWORD: &str = "SecurityManagerPassword123!";

async fn parity_state() -> AppState {
    let mut config = Config::for_test("removed-internal-backend".to_owned());
    config.https_only = false;
    let storage = SharedStorage::connect(&config.shared_storage)
        .await
        .unwrap();

    for role in [
        json!({
            "role_name": "admin",
            "manage_gateway": true,
            "manage_security": true,
            "view_logs": true,
            "export_logs": true
        }),
        json!({
            "role_name": "limited",
            "manage_gateway": false,
            "manage_security": false,
            "view_logs": false,
            "export_logs": false
        }),
        json!({
            "role_name": "security-manager",
            "manage_gateway": false,
            "manage_security": true,
            "view_logs": false,
            "export_logs": false
        }),
    ] {
        storage.insert_one("roles", role).await.unwrap();
    }

    for (username, email, password, role) in [
        ("admin", ADMIN_EMAIL, ADMIN_PASSWORD, "admin"),
        ("limited", LIMITED_EMAIL, LIMITED_PASSWORD, "limited"),
        (
            "security-manager",
            MANAGER_EMAIL,
            MANAGER_PASSWORD,
            "security-manager",
        ),
    ] {
        storage
            .insert_one(
                "users",
                json!({
                    "username": username,
                    "email": email,
                    "password": bcrypt::hash(password, bcrypt::DEFAULT_COST).unwrap(),
                    "role": role,
                    "groups": [],
                    "active": true,
                    "ui_access": true
                }),
            )
            .await
            .unwrap();
    }

    let mut state = AppState::new(config).unwrap();
    state.storage = Some(Arc::new(storage));
    state
}

async fn response_json(response: axum::response::Response) -> Value {
    serde_json::from_slice(&to_bytes(response.into_body(), 1024 * 1024).await.unwrap()).unwrap()
}

fn response_payload(body: &Value) -> &Value {
    body.get("response").unwrap_or(body)
}

async fn login(app: &axum::Router, email: &str, password: &str) -> String {
    let response = app
        .clone()
        .oneshot(
            Request::builder()
                .method(Method::POST)
                .uri("/platform/authorization")
                .header(header::CONTENT_TYPE, "application/json")
                .body(Body::from(
                    json!({"email": email, "password": password}).to_string(),
                ))
                .unwrap(),
        )
        .await
        .unwrap();
    assert_eq!(response.status(), StatusCode::OK);
    let body = response_json(response).await;
    response_payload(&body)["access_token"]
        .as_str()
        .expect("login response access_token")
        .to_owned()
}

async fn request(
    app: &axum::Router,
    method: Method,
    path: &str,
    token: &str,
    payload: Option<Value>,
) -> axum::response::Response {
    let mut builder = Request::builder()
        .method(method)
        .uri(path)
        .header(header::AUTHORIZATION, format!("Bearer {token}"));
    let body = match payload {
        Some(payload) => {
            builder = builder.header(header::CONTENT_TYPE, "application/json");
            Body::from(payload.to_string())
        }
        None => Body::empty(),
    };
    app.clone()
        .oneshot(builder.body(body).unwrap())
        .await
        .unwrap()
}

// Python: backend-services/live-tests/test_90_security_tools_logging.py::test_security_settings_get_put
#[tokio::test]
async fn live_security_settings_get_put_matches_python() {
    let app = build_router(parity_state().await);
    let token = login(&app, ADMIN_EMAIL, ADMIN_PASSWORD).await;

    let get = request(
        &app,
        Method::GET,
        "/platform/security/settings",
        &token,
        None,
    )
    .await;
    assert_eq!(get.status(), StatusCode::OK);
    let get = response_json(get).await;
    let settings = response_payload(&get);
    assert!(settings.get("memory_only").is_some());

    let desired = !settings
        .get("enable_auto_save")
        .and_then(Value::as_bool)
        .unwrap_or(false);
    let put = request(
        &app,
        Method::PUT,
        "/platform/security/settings",
        &token,
        Some(json!({"enable_auto_save": desired})),
    )
    .await;
    assert_eq!(put.status(), StatusCode::OK);
    let put = response_json(put).await;
    assert_eq!(
        response_payload(&put)["enable_auto_save"].as_bool(),
        Some(desired)
    );

    let get_again = request(
        &app,
        Method::GET,
        "/platform/security/settings",
        &token,
        None,
    )
    .await;
    let get_again = response_json(get_again).await;
    assert_eq!(
        response_payload(&get_again)["enable_auto_save"].as_bool(),
        Some(desired)
    );
}

// Python: backend-services/live-tests/test_90_security_tools_logging.py::test_tools_cors_check
#[tokio::test]
async fn live_tools_cors_check_matches_python() {
    let app = build_router(parity_state().await);
    let token = login(&app, ADMIN_EMAIL, ADMIN_PASSWORD).await;
    let response = request(
        &app,
        Method::POST,
        "/platform/tools/cors/check",
        &token,
        Some(json!({
            "origin": "http://localhost:3000",
            "method": "GET",
            "request_headers": ["Content-Type"]
        })),
    )
    .await;

    assert_eq!(response.status(), StatusCode::OK);
    let body = response_json(response).await;
    let payload = response_payload(&body);
    assert!(payload.get("config").is_some());
    assert!(payload.get("preflight").is_some());
}

// Python: backend-services/live-tests/test_90_security_tools_logging.py::test_logging_endpoints
#[tokio::test]
async fn live_logging_endpoints_match_python() {
    let app = build_router(parity_state().await);
    let token = login(&app, ADMIN_EMAIL, ADMIN_PASSWORD).await;

    let logs = request(
        &app,
        Method::GET,
        "/platform/logging/logs?limit=10",
        &token,
        None,
    )
    .await;
    assert_eq!(logs.status(), StatusCode::OK);
    let logs = response_json(logs).await;
    assert!(response_payload(&logs).is_object() || response_payload(&logs).is_array());

    let files = request(
        &app,
        Method::GET,
        "/platform/logging/logs/files",
        &token,
        None,
    )
    .await;
    assert_eq!(files.status(), StatusCode::OK);
    let files = response_json(files).await;
    assert!(response_payload(&files).get("count").is_some());
}

// Python: backend-services/live-tests/test_90_security_tools_logging.py::test_clear_all_caches
#[tokio::test]
async fn live_clear_all_caches_matches_python() {
    let app = build_router(parity_state().await);
    let token = login(&app, ADMIN_EMAIL, ADMIN_PASSWORD).await;
    let response = request(&app, Method::DELETE, "/api/caches", &token, None).await;

    assert_eq!(response.status(), StatusCode::OK);
    let body = response_json(response).await;
    let payload = response_payload(&body);
    assert!(
        payload["message"]
            .as_str()
            .or_else(|| payload["error_message"].as_str())
            .unwrap_or("All caches cleared")
            .contains("All caches cleared")
    );
}

// Python:
// - backend-services/tests/test_security_permissions.py::test_security_settings_requires_permission
// - backend-services/tests/test_security_settings_permissions.py::test_security_settings_get_put_permissions
#[tokio::test]
async fn security_settings_require_manage_security_permission() {
    let app = build_router(parity_state().await);
    let limited = login(&app, LIMITED_EMAIL, LIMITED_PASSWORD).await;
    let manager = login(&app, MANAGER_EMAIL, MANAGER_PASSWORD).await;

    for method in [Method::GET, Method::PUT] {
        let payload = (method == Method::PUT).then(|| json!({"trust_x_forwarded_for": true}));
        let response = request(
            &app,
            method,
            "/platform/security/settings",
            &limited,
            payload,
        )
        .await;
        assert_eq!(response.status(), StatusCode::FORBIDDEN);
    }

    let get = request(
        &app,
        Method::GET,
        "/platform/security/settings",
        &manager,
        None,
    )
    .await;
    assert_eq!(get.status(), StatusCode::OK);

    let put = request(
        &app,
        Method::PUT,
        "/platform/security/settings",
        &manager,
        Some(json!({"trust_x_forwarded_for": true})),
    )
    .await;
    assert_eq!(put.status(), StatusCode::OK);
    let put = response_json(put).await;
    assert_eq!(
        response_payload(&put)["trust_x_forwarded_for"].as_bool(),
        Some(true)
    );
}
