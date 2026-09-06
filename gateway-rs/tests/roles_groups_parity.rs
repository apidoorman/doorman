use std::sync::{Arc, OnceLock};

use axum::body::{Body, to_bytes};
use doorman_gateway::{AppState, Config, build_router, storage::runtime::SharedStorage};
use http::{Method, Request, StatusCode, header};
use serde_json::{Value, json};
use tower::ServiceExt;
use uuid::Uuid;
fn fixture_password() -> &'static str {
    static PASSWORD: OnceLock<String> = OnceLock::new();
    PASSWORD.get_or_init(random_password).as_str()
}

fn random_password() -> String {
    let bytes = Uuid::new_v4().into_bytes();
    let uppercase = char::from(bytes[0] % 26 + b'A');
    let lowercase = char::from(bytes[1] % 26 + b'a');
    let digit = char::from(bytes[2] % 10 + b'0');
    let special = char::from(bytes[3] % 15 + b'!');
    format!("{uppercase}{lowercase}{digit}{special}{}", Uuid::new_v4())
}

async fn app() -> axum::Router {
    let config = Config::for_test("removed-internal-backend".to_owned());
    let storage = SharedStorage::connect(&config.shared_storage)
        .await
        .unwrap();
    storage
        .insert_one(
            "roles",
            json!({
                "role_name": "admin",
                "manage_users": true, "manage_apis": true, "manage_endpoints": true,
                "manage_groups": true, "manage_roles": true, "manage_routings": true,
                "manage_gateway": true, "manage_subscriptions": true, "manage_credits": true,
                "manage_auth": true, "manage_security": true, "manage_tiers": true,
                "manage_rate_limits": true, "view_analytics": true, "view_logs": true,
                "export_logs": true
            }),
        )
        .await
        .unwrap();
    storage
        .insert_one(
            "users",
            json!({
                "username": "admin", "email": "admin@doorman.dev",
                "password": bcrypt::hash(fixture_password(), bcrypt::DEFAULT_COST).unwrap(),
                "role": "admin", "groups": ["ALL", "admin"], "active": true, "ui_access": true
            }),
        )
        .await
        .unwrap();
    let mut state = AppState::new(config).unwrap();
    state.storage = Some(Arc::new(storage));
    build_router(state)
}

async fn request(
    app: &axum::Router,
    method: Method,
    path: &str,
    auth: Option<&(String, String)>,
    payload: Option<Value>,
) -> axum::response::Response {
    let mut builder = Request::builder().method(method).uri(path);
    if let Some((cookie, csrf)) = auth {
        builder = builder
            .header(header::COOKIE, cookie)
            .header("x-csrf-token", csrf);
    }
    let body = if let Some(payload) = payload {
        builder = builder.header(header::CONTENT_TYPE, "application/json");
        Body::from(payload.to_string())
    } else {
        Body::empty()
    };
    app.clone()
        .oneshot(builder.body(body).unwrap())
        .await
        .unwrap()
}

async fn login(app: &axum::Router, email: &str, password: &str) -> (String, String) {
    let response = request(
        app,
        Method::POST,
        "/platform/authorization",
        None,
        Some(json!({"email": email, "password": password})),
    )
    .await;
    assert_eq!(response.status(), StatusCode::OK);
    let cookies = response
        .headers()
        .get_all(header::SET_COOKIE)
        .iter()
        .map(|value| {
            value
                .to_str()
                .unwrap()
                .split(';')
                .next()
                .unwrap()
                .to_owned()
        })
        .collect::<Vec<_>>();
    let csrf = cookies
        .iter()
        .find_map(|cookie| cookie.strip_prefix("csrf_token="))
        .unwrap()
        .to_owned();
    (cookies.join("; "), csrf)
}

async fn json_body(response: axum::response::Response) -> Value {
    serde_json::from_slice(&to_bytes(response.into_body(), 16 * 1024).await.unwrap()).unwrap()
}

async fn create_user(
    app: &axum::Router,
    admin: &(String, String),
    username: &str,
    role: &str,
) -> (String, String) {
    let email = format!("{username}@example.com");
    let password = fixture_password();
    let response = request(
        app,
        Method::POST,
        "/platform/user",
        Some(admin),
        Some(json!({
            "username": username, "email": email, "password": password, "role": role,
            "groups": ["ALL"], "ui_access": true
        })),
    )
    .await;
    assert_eq!(response.status(), StatusCode::CREATED);
    login(app, &email, password).await
}

async fn management_attempt(
    app: &axum::Router,
    auth: &(String, String),
    permission: &str,
    index: usize,
    role: &str,
) -> axum::response::Response {
    let (path, payload) = match permission {
        "manage_apis" => (
            "/platform/api",
            json!({
                "api_name": format!("managed-api-{index}"), "api_version": "v1",
                "api_description": "managed", "api_allowed_roles": ["admin"],
                "api_allowed_groups": ["ALL"], "api_servers": ["http://127.0.0.1:9"],
                "api_type": "REST"
            }),
        ),
        "manage_endpoints" => (
            "/platform/endpoint",
            json!({
                "api_name": "permission-matrix-api", "api_version": "v1",
                "endpoint_method": "GET", "endpoint_uri": format!("/managed-{index}"),
                "endpoint_description": "managed"
            }),
        ),
        "manage_users" => (
            "/platform/user",
            json!({
                "username": format!("managed-user-{index}"),
                "email": format!("managed-user-{index}@example.com"),
                "password": fixture_password(), "role": role,
                "groups": ["ALL"], "ui_access": false
            }),
        ),
        "manage_groups" => (
            "/platform/group",
            json!({
                "group_name": format!("managed-group-{index}"), "group_description": "x"
            }),
        ),
        "manage_roles" => (
            "/platform/role",
            json!({
                "role_name": format!("managed-role-{index}"), "role_description": "x"
            }),
        ),
        _ => unreachable!(),
    };
    request(app, Method::POST, path, Some(auth), Some(payload)).await
}

#[tokio::test]
async fn live_role_permission_matrix_blocks_then_allows_each_management_operation() {
    let app = app().await;
    let admin = login(&app, "admin@doorman.dev", fixture_password()).await;
    let api = request(
        &app,
        Method::POST,
        "/platform/api",
        Some(&admin),
        Some(json!({
            "api_name": "permission-matrix-api", "api_version": "v1",
            "api_description": "permission matrix fixture", "api_allowed_roles": ["admin"],
            "api_allowed_groups": ["ALL"], "api_servers": ["http://127.0.0.1:9"],
            "api_type": "REST", "active": true
        })),
    )
    .await;
    assert_eq!(api.status(), StatusCode::CREATED);

    for (index, (permission, expected_code)) in [
        ("manage_apis", "API007"),
        ("manage_endpoints", "END010"),
        ("manage_users", "USR006"),
        ("manage_groups", "GRP008"),
        ("manage_roles", "ROLE009"),
    ]
    .into_iter()
    .enumerate()
    {
        let role = format!("matrix-{index}");
        let mut role_payload = json!({"role_name": role});
        role_payload[permission] = json!(false);
        let created = request(
            &app,
            Method::POST,
            "/platform/role",
            Some(&admin),
            Some(role_payload),
        )
        .await;
        assert_eq!(created.status(), StatusCode::CREATED, "{permission}");
        let user = create_user(&app, &admin, &format!("matrix-user-{index}"), &role).await;

        let attempt = management_attempt(&app, &user, permission, index, &role).await;
        assert_eq!(attempt.status(), StatusCode::FORBIDDEN, "{permission}");
        assert_eq!(
            json_body(attempt).await["error_code"],
            expected_code,
            "{permission}"
        );

        let mut update = json!({});
        update[permission] = json!(true);
        let enabled = request(
            &app,
            Method::PUT,
            &format!("/platform/role/{role}"),
            Some(&admin),
            Some(update),
        )
        .await;
        assert_eq!(enabled.status(), StatusCode::OK, "{permission}");
        let allowed = management_attempt(&app, &user, permission, index + 10, &role).await;
        assert_ne!(allowed.status(), StatusCode::FORBIDDEN, "{permission}");
    }
}

#[tokio::test]
async fn group_crud_requires_manage_groups_and_allows_group_manager() {
    let app = app().await;
    let admin = login(&app, "admin@doorman.dev", fixture_password()).await;
    for (role, manage_groups) in [("limited", false), ("group-manager", true)] {
        let response = request(
            &app,
            Method::POST,
            "/platform/role",
            Some(&admin),
            Some(json!({
                "role_name": role, "manage_groups": manage_groups
            })),
        )
        .await;
        assert_eq!(response.status(), StatusCode::CREATED);
    }
    let limited = create_user(&app, &admin, "limited-user", "limited").await;
    let manager = create_user(&app, &admin, "group-manager-user", "group-manager").await;

    let forbidden = request(
        &app,
        Method::POST,
        "/platform/group",
        Some(&limited),
        Some(json!({
            "group_name": "parity-group", "group_description": "x"
        })),
    )
    .await;
    assert_eq!(forbidden.status(), StatusCode::FORBIDDEN);
    assert_eq!(json_body(forbidden).await["error_code"], "GRP008");

    let created = request(
        &app,
        Method::POST,
        "/platform/group",
        Some(&manager),
        Some(json!({
            "group_name": "parity-group", "group_description": "x"
        })),
    )
    .await;
    assert_eq!(created.status(), StatusCode::CREATED);
    let fetched = request(
        &app,
        Method::GET,
        "/platform/group/parity-group",
        Some(&manager),
        None,
    )
    .await;
    assert_eq!(fetched.status(), StatusCode::OK);
    assert_eq!(json_body(fetched).await["group_description"], "x");
    let updated = request(
        &app,
        Method::PUT,
        "/platform/group/parity-group",
        Some(&manager),
        Some(json!({"group_description": "y"})),
    )
    .await;
    assert_eq!(updated.status(), StatusCode::OK);
    let deleted = request(
        &app,
        Method::DELETE,
        "/platform/group/parity-group",
        Some(&manager),
        None,
    )
    .await;
    assert_eq!(deleted.status(), StatusCode::OK);
}

#[tokio::test]
async fn missing_group_and_role_reads_and_deletes_return_not_found() {
    let app = app().await;
    let admin = login(&app, "admin@doorman.dev", fixture_password()).await;
    for (method, path, code) in [
        (Method::GET, "/platform/group/not-a-group", "GRP002"),
        (Method::GET, "/platform/role/not-a-role", "ROL002"),
        (Method::DELETE, "/platform/group/not-a-group", "GRP002"),
        (Method::DELETE, "/platform/role/not-a-role", "ROL002"),
    ] {
        let response = request(&app, method, path, Some(&admin), None).await;
        assert_eq!(response.status(), StatusCode::NOT_FOUND, "{path}");
        assert_eq!(json_body(response).await["error_code"], code, "{path}");
    }
}

#[tokio::test]
async fn non_admin_role_manager_cannot_create_admin_role() {
    let app = app().await;
    let admin = login(&app, "admin@doorman.dev", fixture_password()).await;
    let role = request(
        &app,
        Method::POST,
        "/platform/role",
        Some(&admin),
        Some(json!({
            "role_name": "role-manager", "manage_roles": true
        })),
    )
    .await;
    assert_eq!(role.status(), StatusCode::CREATED);
    let manager = create_user(&app, &admin, "role-manager-user", "role-manager").await;
    let response = request(
        &app,
        Method::POST,
        "/platform/role",
        Some(&manager),
        Some(json!({
            "role_name": "admin", "manage_roles": true
        })),
    )
    .await;
    assert_eq!(response.status(), StatusCode::FORBIDDEN);
    assert_eq!(json_body(response).await["error_code"], "ROLE009");
}
