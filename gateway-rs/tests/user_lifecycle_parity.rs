use std::sync::Arc;

use axum::{
    Router,
    body::{Body, to_bytes},
    response::Response,
};
use doorman_gateway::{AppState, Config, build_router, storage::runtime::SharedStorage};
use http::{Method, Request, StatusCode, header};
use serde_json::{Value, json};
use tower::ServiceExt;

async fn test_app() -> Router {
    let mut config = Config::for_test("removed-internal-backend".to_owned());
    config.https_only = false;
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
    build_router(state)
}

async fn response_json(response: Response) -> (StatusCode, Value) {
    let status = response.status();
    let bytes = to_bytes(response.into_body(), usize::MAX).await.unwrap();
    let body = serde_json::from_slice(&bytes).unwrap_or(Value::Null);
    (status, body)
}

async fn json_request(
    app: &Router,
    token: Option<&str>,
    method: Method,
    uri: &str,
    payload: Option<Value>,
) -> (StatusCode, Value) {
    let mut builder = Request::builder().method(method).uri(uri);
    if let Some(token) = token {
        builder = builder.header(header::AUTHORIZATION, format!("Bearer {token}"));
    }
    let body = match payload {
        Some(payload) => {
            builder = builder.header(header::CONTENT_TYPE, "application/json");
            Body::from(payload.to_string())
        }
        None => Body::empty(),
    };
    response_json(
        app.clone()
            .oneshot(builder.body(body).unwrap())
            .await
            .unwrap(),
    )
    .await
}

async fn login_admin(app: &Router) -> String {
    let (status, body) = json_request(
        app,
        None,
        Method::POST,
        "/platform/authorization",
        Some(json!({
            "email": "admin@doorman.dev",
            "password": "AdminPassword123!"
        })),
    )
    .await;
    assert_eq!(status, StatusCode::OK, "{body}");
    body["access_token"].as_str().unwrap().to_owned()
}

// Python source: backend-services/tests/test_user_endpoints.py::test_user_me_and_crud
#[tokio::test]
async fn python_test_user_me_and_crud() {
    let app = test_app().await;
    let token = login_admin(&app).await;

    let (status, me) =
        json_request(&app, Some(&token), Method::GET, "/platform/user/me", None).await;
    assert_eq!(status, StatusCode::OK, "{me}");
    assert_eq!(me["username"], "admin");

    let (status, body) = json_request(
        &app,
        Some(&token),
        Method::POST,
        "/platform/user",
        Some(json!({
            "username": "testuser1",
            "email": "testuser1@example.com",
            "password": "ThisIsAStrongPwd!123",
            "role": "admin",
            "groups": ["ALL"],
            "active": true,
            "ui_access": false
        })),
    )
    .await;
    assert!(
        status == StatusCode::OK || status == StatusCode::CREATED,
        "{body}"
    );

    let (status, body) = json_request(
        &app,
        Some(&token),
        Method::PUT,
        "/platform/user/testuser1",
        Some(json!({"email": "new@mail.com"})),
    )
    .await;
    assert_eq!(status, StatusCode::OK, "{body}");

    let (status, body) = json_request(
        &app,
        Some(&token),
        Method::PUT,
        "/platform/user/testuser1/update-password",
        Some(json!({"new_password": "ThisIsANewPwd!456"})),
    )
    .await;
    assert_eq!(status, StatusCode::OK, "{body}");

    let (status, body) = json_request(
        &app,
        Some(&token),
        Method::DELETE,
        "/platform/user/testuser1",
        None,
    )
    .await;
    assert_eq!(status, StatusCode::OK, "{body}");
}

// Python source:
// backend-services/tests/test_user_permissions_negative.py::test_update_other_user_denied_without_permission
#[tokio::test]
async fn python_test_update_other_user_denied_without_permission() {
    let app = test_app().await;
    let token = login_admin(&app).await;

    let (status, body) = json_request(
        &app,
        Some(&token),
        Method::POST,
        "/platform/role",
        Some(json!({
            "role_name": "user",
            "role_description": "Standard user"
        })),
    )
    .await;
    assert!(
        status == StatusCode::OK || status == StatusCode::CREATED,
        "{body}"
    );

    let (status, body) = json_request(
        &app,
        Some(&token),
        Method::POST,
        "/platform/user",
        Some(json!({
            "username": "qa_user",
            "email": "qa@doorman.dev",
            "password": "QaPass123_ValidLen!!",
            "role": "user"
        })),
    )
    .await;
    assert!(
        status == StatusCode::OK || status == StatusCode::CREATED,
        "{body}"
    );

    let (status, body) = json_request(
        &app,
        Some(&token),
        Method::PUT,
        "/platform/role/admin",
        Some(json!({"manage_users": false})),
    )
    .await;
    assert!(
        status == StatusCode::OK || status == StatusCode::CREATED,
        "{body}"
    );

    let (status, _) = json_request(
        &app,
        Some(&token),
        Method::PUT,
        "/platform/user/qa_user",
        Some(json!({"email": "qa2@doorman.dev"})),
    )
    .await;
    assert_eq!(status, StatusCode::FORBIDDEN);

    let (status, body) = json_request(
        &app,
        Some(&token),
        Method::PUT,
        "/platform/role/admin",
        Some(json!({"manage_users": true})),
    )
    .await;
    assert!(
        status == StatusCode::OK || status == StatusCode::CREATED,
        "{body}"
    );

    let (status, body) = json_request(
        &app,
        Some(&token),
        Method::PUT,
        "/platform/user/qa_user",
        Some(json!({"email": "qa3@doorman.dev"})),
    )
    .await;
    assert!(
        status == StatusCode::OK || status == StatusCode::CREATED,
        "{body}"
    );
}
