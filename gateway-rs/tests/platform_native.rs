use std::{
    io::{self, Write},
    net::SocketAddr,
    sync::{Arc, Mutex},
};

use axum::{
    body::{Body, to_bytes},
    extract::ConnectInfo,
};
use doorman_gateway::{AppState, Config, build_router, storage::runtime::SharedStorage};
use http::{Method, Request, StatusCode, header};
use serde_json::{Value, json};
use tower::ServiceExt;
use tracing::instrument::WithSubscriber;
use tracing_subscriber::fmt::MakeWriter;

async fn memory_state(https_only: bool) -> AppState {
    let mut config = Config::for_test("removed-internal-backend".to_owned());
    config.https_only = https_only;
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

async fn login(app: &axum::Router) -> (String, String) {
    login_as(app, "admin@doorman.dev", "AdminPassword123!").await
}

async fn login_as(app: &axum::Router, email: &str, password: &str) -> (String, String) {
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
                        "password": password
                    })
                    .to_string(),
                ))
                .unwrap(),
        )
        .await
        .unwrap();
    assert_eq!(response.status(), StatusCode::OK);
    let cookies = response
        .headers()
        .get_all(header::SET_COOKIE)
        .iter()
        .filter_map(|value| value.to_str().ok())
        .map(|value| value.split(';').next().unwrap().to_owned())
        .collect::<Vec<_>>();
    let csrf = cookies
        .iter()
        .find_map(|cookie| cookie.strip_prefix("csrf_token="))
        .unwrap()
        .to_owned();
    (cookies.join("; "), csrf)
}

async fn state_with_security_settings(settings: Value) -> AppState {
    let state = memory_state(false).await;
    state
        .storage
        .as_ref()
        .unwrap()
        .insert_one("settings", settings)
        .await
        .unwrap();
    state
}

fn platform_liveness_request(peer_ip: &str, forwarded_ip: Option<&str>) -> Request<Body> {
    let peer = SocketAddr::new(peer_ip.parse().unwrap(), 41000);
    let mut builder = Request::builder()
        .uri("/platform/monitor/liveness")
        .extension(ConnectInfo(peer));
    if let Some(forwarded_ip) = forwarded_ip {
        builder = builder.header("x-forwarded-for", forwarded_ip);
    }
    builder.body(Body::empty()).unwrap()
}

async fn response_json(response: axum::response::Response) -> Value {
    serde_json::from_slice(&to_bytes(response.into_body(), 16 * 1024).await.unwrap()).unwrap()
}

async fn platform_request(
    app: &axum::Router,
    method: Method,
    path: &str,
    cookie: Option<&str>,
    csrf: Option<&str>,
    payload: Option<Value>,
) -> axum::response::Response {
    let mut builder = Request::builder().method(method).uri(path);
    if let Some(cookie) = cookie {
        builder = builder.header(header::COOKIE, cookie);
    }
    if let Some(csrf) = csrf {
        builder = builder.header("x-csrf-token", csrf);
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

#[tokio::test]
async fn authorization_login_status_invalid_and_guards_match_python() {
    let app = build_router(memory_state(false).await);

    let invalid = platform_request(
        &app,
        Method::POST,
        "/platform/authorization",
        None,
        None,
        Some(json!({"email": "unknown@example.com", "password": "bad"})),
    )
    .await;
    assert_eq!(invalid.status(), StatusCode::BAD_REQUEST);

    for (method, path) in [
        (Method::GET, "/platform/user/me"),
        (Method::POST, "/platform/authorization/refresh"),
    ] {
        let response = platform_request(&app, method, path, None, None, None).await;
        assert_eq!(response.status(), StatusCode::UNAUTHORIZED, "{path}");
    }

    let response = platform_request(
        &app,
        Method::POST,
        "/platform/authorization",
        None,
        None,
        Some(json!({
            "email": "admin@doorman.dev",
            "password": "AdminPassword123!"
        })),
    )
    .await;
    assert_eq!(response.status(), StatusCode::OK);
    let cookies = response
        .headers()
        .get_all(header::SET_COOKIE)
        .iter()
        .map(|value| value.to_str().unwrap().split(';').next().unwrap())
        .collect::<Vec<_>>();
    assert!(
        cookies
            .iter()
            .any(|cookie| cookie.starts_with("access_token_cookie="))
    );
    let cookie = cookies.join("; ");

    let status = platform_request(
        &app,
        Method::GET,
        "/platform/authorization/status",
        Some(&cookie),
        None,
        None,
    )
    .await;
    assert_eq!(status.status(), StatusCode::OK);
    assert_eq!(response_json(status).await["message"], "Token is valid");
}

#[tokio::test]
async fn authorization_refresh_and_invalidate_match_python() {
    let app = build_router(memory_state(false).await);
    let (cookie, _) = login(&app).await;

    let refresh = platform_request(
        &app,
        Method::POST,
        "/platform/authorization/refresh",
        Some(&cookie),
        None,
        Some(json!({})),
    )
    .await;
    assert_eq!(refresh.status(), StatusCode::OK);
    let refreshed_cookie = refresh
        .headers()
        .get_all(header::SET_COOKIE)
        .iter()
        .map(|value| value.to_str().unwrap().split(';').next().unwrap())
        .collect::<Vec<_>>()
        .join("; ");
    assert!(
        refreshed_cookie
            .split("; ")
            .any(|cookie| cookie.starts_with("access_token_cookie="))
    );

    let status = platform_request(
        &app,
        Method::GET,
        "/platform/authorization/status",
        Some(&refreshed_cookie),
        None,
        None,
    )
    .await;
    assert_eq!(status.status(), StatusCode::OK);

    let invalidate = platform_request(
        &app,
        Method::POST,
        "/platform/authorization/invalidate",
        Some(&refreshed_cookie),
        None,
        Some(json!({})),
    )
    .await;
    assert_eq!(invalidate.status(), StatusCode::OK);

    let rejected = platform_request(
        &app,
        Method::GET,
        "/platform/user/me",
        Some(&refreshed_cookie),
        None,
        None,
    )
    .await;
    assert_eq!(rejected.status(), StatusCode::UNAUTHORIZED);
}

#[tokio::test]
async fn authorization_admin_lifecycle_and_revoke_match_python() {
    let app = build_router(memory_state(false).await);
    let (admin_cookie, _) = login(&app).await;
    let username = "qa-auth";
    let email = "qa-auth@example.com";
    let password = "VerySecurePassword!123";

    let create = platform_request(
        &app,
        Method::POST,
        "/platform/user",
        Some(&admin_cookie),
        None,
        Some(json!({
            "username": username,
            "email": email,
            "password": password,
            "role": "admin",
            "groups": ["ALL"],
            "active": true
        })),
    )
    .await;
    assert_eq!(create.status(), StatusCode::CREATED);
    let (user_cookie, _) = login_as(&app, email, password).await;

    let status_path = format!("/platform/authorization/admin/status/{username}");
    let status = platform_request(
        &app,
        Method::GET,
        &status_path,
        Some(&admin_cookie),
        None,
        None,
    )
    .await;
    assert_eq!(status.status(), StatusCode::OK);
    let status = response_json(status).await;
    assert_eq!(status["active"], true);
    assert_eq!(status["revoked"], false);

    let revoke_path = format!("/platform/authorization/admin/revoke/{username}");
    let revoke = platform_request(
        &app,
        Method::POST,
        &revoke_path,
        Some(&admin_cookie),
        None,
        Some(json!({})),
    )
    .await;
    assert_eq!(revoke.status(), StatusCode::OK);
    let rejected = platform_request(
        &app,
        Method::GET,
        "/platform/user/me",
        Some(&user_cookie),
        None,
        None,
    )
    .await;
    assert_eq!(rejected.status(), StatusCode::UNAUTHORIZED);

    let disable_path = format!("/platform/authorization/admin/disable/{username}");
    let disable = platform_request(
        &app,
        Method::POST,
        &disable_path,
        Some(&admin_cookie),
        None,
        Some(json!({})),
    )
    .await;
    assert_eq!(disable.status(), StatusCode::OK);
    let status = platform_request(
        &app,
        Method::GET,
        &status_path,
        Some(&admin_cookie),
        None,
        None,
    )
    .await;
    let status = response_json(status).await;
    assert_eq!(status["active"], false);
    assert_eq!(status["revoked"], true);

    let enable_path = format!("/platform/authorization/admin/enable/{username}");
    let enable = platform_request(
        &app,
        Method::POST,
        &enable_path,
        Some(&admin_cookie),
        None,
        Some(json!({})),
    )
    .await;
    assert_eq!(enable.status(), StatusCode::OK);
    let unrevoke_path = format!("/platform/authorization/admin/unrevoke/{username}");
    let unrevoke = platform_request(
        &app,
        Method::POST,
        &unrevoke_path,
        Some(&admin_cookie),
        None,
        Some(json!({})),
    )
    .await;
    assert_eq!(unrevoke.status(), StatusCode::OK);
    let status = platform_request(
        &app,
        Method::GET,
        &status_path,
        Some(&admin_cookie),
        None,
        None,
    )
    .await;
    let status = response_json(status).await;
    assert_eq!(status["active"], true);
    assert_eq!(status["revoked"], false);
}

#[derive(Clone, Default)]
struct CapturedTrace(Arc<Mutex<Vec<u8>>>);

impl Write for CapturedTrace {
    fn write(&mut self, bytes: &[u8]) -> io::Result<usize> {
        self.0.lock().unwrap().extend_from_slice(bytes);
        Ok(bytes.len())
    }

    fn flush(&mut self) -> io::Result<()> {
        Ok(())
    }
}

impl<'writer> MakeWriter<'writer> for CapturedTrace {
    type Writer = Self;

    fn make_writer(&'writer self) -> Self::Writer {
        self.clone()
    }
}

impl CapturedTrace {
    fn text(&self) -> String {
        String::from_utf8(self.0.lock().unwrap().clone()).unwrap()
    }
}

#[tokio::test]
async fn global_whitelist_blocks_non_whitelisted_with_trusted_proxy() {
    let app = build_router(
        state_with_security_settings(json!({
            "trust_x_forwarded_for": true,
            "xff_trusted_proxies": ["127.0.0.1"],
            "ip_whitelist": ["198.51.100.10"],
            "ip_blacklist": [],
            "allow_localhost_bypass": false,
        }))
        .await,
    );
    let response = app
        .oneshot(platform_liveness_request("127.0.0.1", Some("203.0.113.10")))
        .await
        .unwrap();

    assert_eq!(response.status(), StatusCode::FORBIDDEN);
    assert_eq!(response_json(response).await["error_code"], "SEC010");
}

#[tokio::test]
async fn global_blacklist_blocks_with_trusted_proxy() {
    let app = build_router(
        state_with_security_settings(json!({
            "trust_x_forwarded_for": true,
            "xff_trusted_proxies": ["127.0.0.1"],
            "ip_whitelist": [],
            "ip_blacklist": ["203.0.113.10"],
            "allow_localhost_bypass": false,
        }))
        .await,
    );
    let response = app
        .oneshot(platform_liveness_request("127.0.0.1", Some("203.0.113.10")))
        .await
        .unwrap();

    assert_eq!(response.status(), StatusCode::FORBIDDEN);
    assert_eq!(response_json(response).await["error_code"], "SEC011");
}

#[tokio::test]
async fn global_xff_is_ignored_when_the_direct_proxy_is_not_trusted() {
    let app = build_router(
        state_with_security_settings(json!({
            "trust_x_forwarded_for": true,
            "xff_trusted_proxies": ["10.0.0.1"],
            "ip_whitelist": ["198.51.100.10"],
            "ip_blacklist": [],
            "allow_localhost_bypass": false,
        }))
        .await,
    );
    let response = app
        .oneshot(platform_liveness_request(
            "127.0.0.1",
            Some("198.51.100.10"),
        ))
        .await
        .unwrap();

    assert_eq!(response.status(), StatusCode::FORBIDDEN);
    assert_eq!(response_json(response).await["error_code"], "SEC010");
}

#[tokio::test]
async fn global_localhost_bypass_enabled_allows_without_forwarding_headers() {
    let app = build_router(
        state_with_security_settings(json!({
            "trust_x_forwarded_for": false,
            "ip_whitelist": ["198.51.100.10"],
            "ip_blacklist": [],
            "allow_localhost_bypass": true,
        }))
        .await,
    );
    let response = app
        .oneshot(platform_liveness_request("127.0.0.1", None))
        .await
        .unwrap();

    assert_eq!(response.status(), StatusCode::OK);
}

#[tokio::test]
async fn global_localhost_bypass_disabled_blocks_without_forwarding_headers() {
    let app = build_router(
        state_with_security_settings(json!({
            "trust_x_forwarded_for": false,
            "ip_whitelist": ["198.51.100.10"],
            "ip_blacklist": [],
            "allow_localhost_bypass": false,
        }))
        .await,
    );
    let response = app
        .clone()
        .oneshot(platform_liveness_request("127.0.0.1", None))
        .await
        .unwrap();
    assert_eq!(response.status(), StatusCode::FORBIDDEN);
    assert_eq!(response_json(response).await["error_code"], "SEC010");

    let settings_response = app
        .oneshot(
            Request::builder()
                .method("PUT")
                .uri("/platform/security/settings")
                .extension(ConnectInfo(SocketAddr::new(
                    "127.0.0.1".parse().unwrap(),
                    41000,
                )))
                .header(header::CONTENT_TYPE, "application/json")
                .body(Body::from("{}"))
                .unwrap(),
        )
        .await
        .unwrap();
    assert_eq!(settings_response.status(), StatusCode::UNAUTHORIZED);
}

#[tokio::test]
async fn global_ip_denial_emits_the_python_audit_action() {
    let app = build_router(
        state_with_security_settings(json!({
            "trust_x_forwarded_for": true,
            "xff_trusted_proxies": ["127.0.0.1"],
            "ip_whitelist": ["198.51.100.10"],
            "ip_blacklist": [],
            "allow_localhost_bypass": false,
        }))
        .await,
    );
    let capture = CapturedTrace::default();
    let subscriber = tracing_subscriber::fmt()
        .json()
        .with_writer(capture.clone())
        .finish();
    let response = app
        .oneshot(platform_liveness_request("127.0.0.1", Some("203.0.113.10")))
        .with_subscriber(subscriber)
        .await
        .unwrap();

    assert_eq!(response.status(), StatusCode::FORBIDDEN);
    let events = capture.text();
    assert!(
        events.contains("ip.global_deny"),
        "captured events: {events}"
    );
    assert!(
        events.contains("not_in_whitelist"),
        "captured events: {events}"
    );
    assert!(events.contains("203.0.113.10"), "captured events: {events}");
}

#[tokio::test]
async fn platform_documentation_and_registration_are_private_by_default() {
    let app = build_router(memory_state(false).await);

    for path in [
        "/platform/openapi.json",
        "/platform/docs",
        "/platform/redoc",
    ] {
        let response = app
            .clone()
            .oneshot(Request::builder().uri(path).body(Body::empty()).unwrap())
            .await
            .unwrap();
        assert_eq!(response.status(), StatusCode::UNAUTHORIZED, "{path}");
    }

    let registration = app
        .clone()
        .oneshot(
            Request::builder()
                .method("POST")
                .uri("/platform/authorization/register")
                .header(header::CONTENT_TYPE, "application/json")
                .body(Body::from(
                    json!({
                        "email": "public@example.com",
                        "password": "PublicPassword123!"
                    })
                    .to_string(),
                ))
                .unwrap(),
        )
        .await
        .unwrap();
    assert_eq!(registration.status(), StatusCode::FORBIDDEN);
    let registration: Value =
        serde_json::from_slice(&to_bytes(registration.into_body(), 4096).await.unwrap()).unwrap();
    assert_eq!(registration["error_code"], "AUTH006");

    let (admin_cookie, _) = login(&app).await;
    for path in [
        "/platform/openapi.json",
        "/platform/docs",
        "/platform/redoc",
    ] {
        let response = app
            .clone()
            .oneshot(
                Request::builder()
                    .uri(path)
                    .header(header::COOKIE, &admin_cookie)
                    .body(Body::empty())
                    .unwrap(),
            )
            .await
            .unwrap();
        assert_eq!(response.status(), StatusCode::OK, "{path}");
    }
}

#[tokio::test]
async fn user_managers_cannot_assign_or_escalate_to_admin() {
    let state = memory_state(false).await;
    let storage = state.storage.clone().unwrap();
    storage
        .insert_one(
            "roles",
            json!({"role_name": "user-manager", "manage_users": true}),
        )
        .await
        .unwrap();
    storage
        .insert_one(
            "users",
            json!({
                "username": "manager",
                "email": "manager@example.com",
                "password": bcrypt::hash("ManagerPassword123!", bcrypt::DEFAULT_COST).unwrap(),
                "role": "user-manager",
                "active": true
            }),
        )
        .await
        .unwrap();
    let app = build_router(state);
    let (cookie, _) = login_as(&app, "manager@example.com", "ManagerPassword123!").await;

    for (method, path, payload) in [
        (
            "POST",
            "/platform/users",
            json!({
                "username": "new-admin",
                "email": "new-admin@example.com",
                "password": "NewAdminPassword123!",
                "role": "admin"
            }),
        ),
        ("PUT", "/platform/users/manager", json!({"role": "admin"})),
    ] {
        let response = app
            .clone()
            .oneshot(
                Request::builder()
                    .method(method)
                    .uri(path)
                    .header(header::CONTENT_TYPE, "application/json")
                    .header(header::COOKIE, &cookie)
                    .body(Body::from(payload.to_string()))
                    .unwrap(),
            )
            .await
            .unwrap();
        assert_eq!(response.status(), StatusCode::FORBIDDEN, "{path}");
    }
}

#[tokio::test]
async fn platform_preflight_is_public_with_safe_defaults() {
    let app = build_router(memory_state(false).await);
    let response = app
        .oneshot(
            Request::builder()
                .method("OPTIONS")
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
    assert!(
        !response
            .headers()
            .contains_key(header::ACCESS_CONTROL_ALLOW_CREDENTIALS)
    );
    assert!(response.headers().contains_key("request_id"));
    assert!(response.headers().contains_key("x-request-id"));
}

#[tokio::test]
async fn memory_mode_login_crud_import_and_rollback_are_native() {
    let app = build_router(memory_state(false).await);
    let (cookie, _) = login(&app).await;

    let create = app
        .clone()
        .oneshot(
            Request::builder()
                .method("POST")
                .uri("/platform/api")
                .header(header::CONTENT_TYPE, "application/json")
                .header(header::COOKIE, &cookie)
                .body(Body::from(
                    json!({
                        "api_name": "native",
                        "api_version": "v1",
                        "api_type": "REST",
                        "api_public": true,
                        "api_auth_required": false
                    })
                    .to_string(),
                ))
                .unwrap(),
        )
        .await
        .unwrap();
    assert_eq!(create.status(), StatusCode::CREATED);

    let imported = app
        .clone()
        .oneshot(
            Request::builder()
                .method("POST")
                .uri("/platform/config/import")
                .header(header::CONTENT_TYPE, "application/json")
                .header(header::COOKIE, &cookie)
                .body(Body::from(
                    json!({
                        "apis": [{
                            "api_name": "replacement",
                            "api_version": "v1",
                            "api_id": "replacement-id",
                            "api_public": true
                        }]
                    })
                    .to_string(),
                ))
                .unwrap(),
        )
        .await
        .unwrap();
    assert_eq!(imported.status(), StatusCode::OK);

    let rollback = app
        .clone()
        .oneshot(
            Request::builder()
                .method("POST")
                .uri("/platform/config/rollback")
                .header(header::COOKIE, &cookie)
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();
    assert_eq!(rollback.status(), StatusCode::OK);

    let restored = app
        .oneshot(
            Request::builder()
                .uri("/platform/api/native/v1")
                .header(header::COOKIE, cookie)
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();
    assert_eq!(restored.status(), StatusCode::OK);
    let body: Value =
        serde_json::from_slice(&to_bytes(restored.into_body(), 16 * 1024).await.unwrap()).unwrap();
    assert_eq!(body["api_name"], "native");
}

#[tokio::test]
async fn https_mode_requires_matching_csrf_and_preserves_request_id() {
    let app = build_router(memory_state(true).await);
    let (cookie, csrf) = login(&app).await;

    let rejected = app
        .clone()
        .oneshot(
            Request::builder()
                .uri("/platform/user/me")
                .header(header::COOKIE, &cookie)
                .header("x-request-id", "csrf-rejected")
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();
    assert_eq!(rejected.status(), StatusCode::UNAUTHORIZED);
    assert_eq!(rejected.headers()["request_id"], "csrf-rejected");

    let mismatched = platform_request(
        &app,
        Method::GET,
        "/platform/user/me",
        Some(&cookie),
        Some("not-the-cookie"),
        None,
    )
    .await;
    assert_eq!(mismatched.status(), StatusCode::UNAUTHORIZED);

    let accepted = platform_request(
        &app,
        Method::GET,
        "/platform/user/me",
        Some(&cookie),
        Some(&csrf),
        None,
    )
    .await;
    assert_eq!(accepted.status(), StatusCode::OK);

    let http_app = build_router(memory_state(false).await);
    let (http_cookie, _) = login(&http_app).await;
    let accepted_without_csrf = platform_request(
        &http_app,
        Method::GET,
        "/platform/user/me",
        Some(&http_cookie),
        None,
        None,
    )
    .await;
    assert_eq!(accepted_without_csrf.status(), StatusCode::OK);
}

#[tokio::test]
async fn strict_envelope_preserves_legacy_status_tokens_and_probe_shape() {
    let mut state = memory_state(false).await;
    state.config.strict_response_envelope = true;
    let app = build_router(state);

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
    assert!(response.headers().contains_key("x-body-length"));
    let body: Value =
        serde_json::from_slice(&to_bytes(response.into_body(), 64 * 1024).await.unwrap()).unwrap();
    assert_eq!(body["status_code"], 200);
    assert_eq!(body["access_token"], body["response"]["access_token"]);
    assert_eq!(body["refresh_token"], body["response"]["refresh_token"]);

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
                        "password": "wrong-password"
                    })
                    .to_string(),
                ))
                .unwrap(),
        )
        .await
        .unwrap();
    assert_eq!(response.status(), StatusCode::OK);
    let body: Value =
        serde_json::from_slice(&to_bytes(response.into_body(), 64 * 1024).await.unwrap()).unwrap();
    assert_eq!(body["status_code"], 400);
    assert!(body.get("error_code").is_some());

    let response = app
        .oneshot(
            Request::builder()
                .uri("/api/health")
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();
    let body: Value =
        serde_json::from_slice(&to_bytes(response.into_body(), 1024).await.unwrap()).unwrap();
    assert_eq!(body, json!({"status": "online"}));
}

#[tokio::test]
async fn platform_uses_the_configured_default_request_body_limit() {
    let app = build_router(memory_state(false).await);
    let response = app
        .oneshot(
            Request::builder()
                .method("POST")
                .uri("/platform/authorization")
                .header(header::CONTENT_TYPE, "application/json")
                .body(Body::from(vec![b'x'; 1024 * 1024 + 1]))
                .unwrap(),
        )
        .await
        .unwrap();

    assert_eq!(response.status(), StatusCode::PAYLOAD_TOO_LARGE);
    let body: Value =
        serde_json::from_slice(&to_bytes(response.into_body(), 1024).await.unwrap()).unwrap();
    assert_eq!(body["error_code"], "GTW013");
}

#[tokio::test]
async fn memory_mode_parses_and_imports_wsdl_without_an_external_service() {
    let app = build_router(memory_state(false).await);
    let (cookie, _) = login(&app).await;
    let wsdl = r#"<definitions xmlns="http://schemas.xmlsoap.org/wsdl/" xmlns:soap="http://schemas.xmlsoap.org/wsdl/soap/" targetNamespace="urn:billing"><service name="Billing"/><portType name="BillingPort"><operation name="Charge"><input message="tns:ChargeRequest"/><output message="tns:ChargeResponse"/></operation></portType><binding name="BillingBinding"><operation name="Charge"><soap:operation soapAction="urn:charge"/></operation></binding></definitions>"#;

    let preview = app
        .clone()
        .oneshot(
            Request::builder()
                .method("POST")
                .uri("/platform/wsdl/parse")
                .header(header::CONTENT_TYPE, "application/xml")
                .header(header::COOKIE, &cookie)
                .body(Body::from(wsdl))
                .unwrap(),
        )
        .await
        .unwrap();
    assert_eq!(preview.status(), StatusCode::OK);
    let preview: Value =
        serde_json::from_slice(&to_bytes(preview.into_body(), 64 * 1024).await.unwrap()).unwrap();
    assert_eq!(preview["service_name"], "Billing");
    assert_eq!(preview["operations"][0]["soap_action"], "urn:charge");

    let created = app
        .clone()
        .oneshot(
            Request::builder()
                .method("POST")
                .uri("/platform/api")
                .header(header::CONTENT_TYPE, "application/json")
                .header(header::COOKIE, &cookie)
                .body(Body::from(
                    json!({
                        "api_name": "soap",
                        "api_version": "v1",
                        "api_type": "SOAP",
                        "api_public": true,
                        "api_auth_required": false,
                        "api_wsdl_content": wsdl
                    })
                    .to_string(),
                ))
                .unwrap(),
        )
        .await
        .unwrap();
    assert_eq!(created.status(), StatusCode::CREATED);

    let imported = app
        .oneshot(
            Request::builder()
                .method("POST")
                .uri("/platform/api/soap/v1/wsdl/import")
                .header(header::COOKIE, cookie)
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();
    assert_eq!(imported.status(), StatusCode::OK);
    let imported: Value =
        serde_json::from_slice(&to_bytes(imported.into_body(), 64 * 1024).await.unwrap()).unwrap();
    assert_eq!(imported["service_name"], "Billing");
    assert_eq!(imported["operations_found"], 1);
    assert_eq!(imported["endpoints_imported"], 1);
}

#[tokio::test]
async fn config_reload_routes_preserve_legacy_values_metadata_and_permissions() {
    let state = memory_state(false).await;
    let storage = state.storage.clone().unwrap();
    storage
        .insert_one(
            "roles",
            json!({"role_name": "viewer", "manage_gateway": false}),
        )
        .await
        .unwrap();
    storage
        .insert_one(
            "users",
            json!({
                "username": "viewer",
                "email": "viewer@doorman.dev",
                "password": bcrypt::hash("ViewerPassword123!", bcrypt::DEFAULT_COST).unwrap(),
                "role": "viewer",
                "groups": [],
                "active": true
            }),
        )
        .await
        .unwrap();
    let app = build_router(state);
    let (admin_cookie, _) = login(&app).await;
    let (viewer_cookie, _) = login_as(&app, "viewer@doorman.dev", "ViewerPassword123!").await;

    let keys = app
        .clone()
        .oneshot(
            Request::builder()
                .uri("/platform/config/reloadable-keys")
                .header(header::COOKIE, &viewer_cookie)
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();
    assert_eq!(keys.status(), StatusCode::FORBIDDEN);

    let keys = app
        .clone()
        .oneshot(
            Request::builder()
                .uri("/platform/config/reloadable-keys")
                .header(header::COOKIE, &admin_cookie)
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();
    assert_eq!(keys.status(), StatusCode::OK);
    let keys: Value =
        serde_json::from_slice(&to_bytes(keys.into_body(), 64 * 1024).await.unwrap()).unwrap();
    assert_eq!(keys["total"], 22);
    assert_eq!(keys["reloadable_keys"][0]["key"], "LOG_LEVEL");
    assert_eq!(keys["notes"].as_array().unwrap().len(), 4);

    for (method, path) in [
        ("GET", "/platform/config/current"),
        ("POST", "/platform/config/reload"),
        ("GET", "/platform/config/export/apis"),
        ("GET", "/platform/config/export/endpoints"),
        ("GET", "/platform/config/export/roles"),
        ("GET", "/platform/config/export/groups"),
        ("GET", "/platform/config/export/routings"),
    ] {
        let denied = app
            .clone()
            .oneshot(
                Request::builder()
                    .method(method)
                    .uri(path)
                    .header(header::COOKIE, &viewer_cookie)
                    .body(Body::empty())
                    .unwrap(),
            )
            .await
            .unwrap();
        assert_eq!(denied.status(), StatusCode::FORBIDDEN);
    }

    let current = app
        .clone()
        .oneshot(
            Request::builder()
                .uri("/platform/config/current")
                .header(header::COOKIE, &admin_cookie)
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();
    assert_eq!(current.status(), StatusCode::OK);
    let current: Value =
        serde_json::from_slice(&to_bytes(current.into_body(), 64 * 1024).await.unwrap()).unwrap();
    assert!(current["config"].is_object());
    assert_eq!(
        current["source"],
        "Environment variables override config file values"
    );

    let reload = app
        .oneshot(
            Request::builder()
                .method("POST")
                .uri("/platform/config/reload")
                .header(header::COOKIE, admin_cookie)
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();
    assert_eq!(reload.status(), StatusCode::OK);
    let reload: Value =
        serde_json::from_slice(&to_bytes(reload.into_body(), 64 * 1024).await.unwrap()).unwrap();
    assert_eq!(reload["message"], "Configuration reloaded successfully");
    assert!(reload["config"].is_object());
}

#[tokio::test]
async fn api_create_and_update_preserve_python_pydantic_and_duplicate_contracts() {
    let state = memory_state(false).await;
    let app = build_router(state);
    let (cookie, _) = login(&app).await;

    let create_payload = json!({
        "api_name": "contract",
        "api_version": "v1",
        "api_description": "original",
        "api_credits_enabled": true,
        "unknown_field": "ignored"
    });
    let created = app
        .clone()
        .oneshot(
            Request::builder()
                .method("POST")
                .uri("/platform/api")
                .header(header::CONTENT_TYPE, "application/json")
                .header(header::COOKIE, &cookie)
                .body(Body::from(create_payload.to_string()))
                .unwrap(),
        )
        .await
        .unwrap();
    assert_eq!(created.status(), StatusCode::CREATED);
    let created: Value =
        serde_json::from_slice(&to_bytes(created.into_body(), 64 * 1024).await.unwrap()).unwrap();
    assert_eq!(created["api"]["api_allowed_roles"], json!([]));
    assert_eq!(created["api"]["api_auth_required"], true);
    assert_eq!(created["api"]["api_ip_mode"], "allow_all");
    assert!(created["api"].get("unknown_field").is_none());

    let duplicate = app
        .clone()
        .oneshot(
            Request::builder()
                .method("POST")
                .uri("/platform/api")
                .header(header::CONTENT_TYPE, "application/json")
                .header(header::COOKIE, &cookie)
                .body(Body::from(
                    json!({
                        "api_name": "contract",
                        "api_version": "v1",
                        "api_description": "must-not-overwrite",
                        "api_credits_enabled": false
                    })
                    .to_string(),
                ))
                .unwrap(),
        )
        .await
        .unwrap();
    assert_eq!(duplicate.status(), StatusCode::OK);

    let stored = app
        .clone()
        .oneshot(
            Request::builder()
                .uri("/platform/api/contract/v1")
                .header(header::COOKIE, &cookie)
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();
    let stored: Value =
        serde_json::from_slice(&to_bytes(stored.into_body(), 64 * 1024).await.unwrap()).unwrap();
    assert_eq!(stored["api_description"], "original");
    assert_eq!(stored["api_credits_enabled"], true);

    let invalid = app
        .clone()
        .oneshot(
            Request::builder()
                .method("POST")
                .uri("/platform/api")
                .header(header::CONTENT_TYPE, "application/json")
                .header(header::COOKIE, &cookie)
                .body(Body::from(
                    json!({"api_name": "", "api_version": "version-too-long"}).to_string(),
                ))
                .unwrap(),
        )
        .await
        .unwrap();
    assert_eq!(invalid.status(), StatusCode::UNPROCESSABLE_ENTITY);
    let invalid: Value =
        serde_json::from_slice(&to_bytes(invalid.into_body(), 64 * 1024).await.unwrap()).unwrap();
    assert_eq!(invalid["detail"].as_array().unwrap().len(), 2);

    let empty_update = app
        .clone()
        .oneshot(
            Request::builder()
                .method("PUT")
                .uri("/platform/api/contract/v1")
                .header(header::CONTENT_TYPE, "application/json")
                .header(header::COOKIE, &cookie)
                .body(Body::from(json!({"api_description": null}).to_string()))
                .unwrap(),
        )
        .await
        .unwrap();
    assert_eq!(empty_update.status(), StatusCode::BAD_REQUEST);
    let empty_update: Value =
        serde_json::from_slice(&to_bytes(empty_update.into_body(), 4096).await.unwrap()).unwrap();
    assert_eq!(empty_update["error_code"], "API006");

    let conflict = app
        .oneshot(
            Request::builder()
                .method("PUT")
                .uri("/platform/api/contract/v1")
                .header(header::CONTENT_TYPE, "application/json")
                .header(header::COOKIE, cookie)
                .body(Body::from(json!({"api_public": true}).to_string()))
                .unwrap(),
        )
        .await
        .unwrap();
    assert_eq!(conflict.status(), StatusCode::BAD_REQUEST);
    let conflict: Value =
        serde_json::from_slice(&to_bytes(conflict.into_body(), 4096).await.unwrap()).unwrap();
    assert_eq!(conflict["error_code"], "API013");
}

#[tokio::test]
async fn management_permissions_readiness_tools_and_restart_preserve_contract() {
    let state = memory_state(false).await;
    let storage = state.storage.clone().unwrap();
    storage
        .insert_one(
            "roles",
            json!({
                "role_name": "limited",
                "manage_gateway": false,
                "manage_security": false,
                "view_analytics": false,
                "view_logs": false,
                "export_logs": false
            }),
        )
        .await
        .unwrap();
    storage
        .insert_one(
            "users",
            json!({
                "username": "limited",
                "email": "limited@doorman.dev",
                "password": bcrypt::hash("LimitedPassword123!", bcrypt::DEFAULT_COST).unwrap(),
                "role": "limited",
                "groups": [],
                "active": true
            }),
        )
        .await
        .unwrap();
    let app = build_router(state);
    let (admin_cookie, _) = login(&app).await;
    let (limited_cookie, _) = login_as(&app, "limited@doorman.dev", "LimitedPassword123!").await;

    let public_readiness = app
        .clone()
        .oneshot(
            Request::builder()
                .uri("/platform/monitor/readiness")
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();
    assert_eq!(public_readiness.status(), StatusCode::OK);
    let public_readiness: Value =
        serde_json::from_slice(&to_bytes(public_readiness.into_body(), 4096).await.unwrap())
            .unwrap();
    assert_eq!(public_readiness.as_object().unwrap().len(), 1);
    assert!(matches!(
        public_readiness["status"].as_str(),
        Some("ready" | "degraded")
    ));

    let admin_readiness = app
        .clone()
        .oneshot(
            Request::builder()
                .uri("/platform/monitor/readiness")
                .header(header::COOKIE, &admin_cookie)
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();
    let admin_readiness: Value =
        serde_json::from_slice(&to_bytes(admin_readiness.into_body(), 4096).await.unwrap())
            .unwrap();
    assert!(admin_readiness.get("mongodb").is_some());
    assert!(admin_readiness.get("cache_backend").is_some());

    for (method, path, code) in [
        ("GET", "/platform/security/settings", "SEC001"),
        ("GET", "/platform/monitor/metrics", "MON001"),
        ("GET", "/platform/monitor/report", "MON002"),
        ("GET", "/platform/analytics/timeseries", "ANALYTICS001"),
        ("GET", "/platform/analytics/top-apis", "ANALYTICS001"),
        ("GET", "/platform/dashboard", "ANALYTICS001"),
        ("POST", "/platform/tools/rate-limit-simulator", "RATE001"),
        ("GET", "/platform/openapi.json", "API008"),
        ("GET", "/platform/docs", "API008"),
        ("GET", "/platform/redoc", "API008"),
        ("POST", "/platform/tools/cors/check", "TLS001"),
        ("GET", "/platform/tools/grpc/check", "TLS001"),
        ("GET", "/platform/tools/chaos/stats", "TLS001"),
    ] {
        let denied = app
            .clone()
            .oneshot(
                Request::builder()
                    .method(method)
                    .uri(path)
                    .header(header::CONTENT_TYPE, "application/json")
                    .header(header::COOKIE, &limited_cookie)
                    .body(Body::from(
                        json!({"origin": "http://localhost:3000", "method": "GET"}).to_string(),
                    ))
                    .unwrap(),
            )
            .await
            .unwrap();
        assert_eq!(denied.status(), StatusCode::FORBIDDEN, "{path}");
        let denied: Value =
            serde_json::from_slice(&to_bytes(denied.into_body(), 4096).await.unwrap()).unwrap();
        assert_eq!(denied["error_code"], code, "{path}");
    }

    let grpc_check = app
        .clone()
        .oneshot(
            Request::builder()
                .uri("/platform/tools/grpc/check")
                .header(header::COOKIE, &admin_cookie)
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();
    assert_eq!(grpc_check.status(), StatusCode::OK);
    let grpc_check: Value =
        serde_json::from_slice(&to_bytes(grpc_check.into_body(), 4096).await.unwrap()).unwrap();
    assert_eq!(grpc_check["available"]["grpc"], true);
    assert_eq!(grpc_check["available"]["grpc_tools_protoc"], true);
    assert!(grpc_check["notes"].is_array());
    assert!(grpc_check["details"].is_object());

    let chaos = app
        .clone()
        .oneshot(
            Request::builder()
                .method("POST")
                .uri("/platform/tools/chaos/toggle")
                .header(header::CONTENT_TYPE, "application/json")
                .header(header::COOKIE, &admin_cookie)
                .body(Body::from(
                    json!({"backend": "redis", "enabled": true, "duration_ms": 5}).to_string(),
                ))
                .unwrap(),
        )
        .await
        .unwrap();
    assert_eq!(chaos.status(), StatusCode::OK);
    let chaos: Value =
        serde_json::from_slice(&to_bytes(chaos.into_body(), 4096).await.unwrap()).unwrap();
    assert_eq!(chaos, json!({"backend": "redis", "enabled": true}));
    tokio::time::sleep(std::time::Duration::from_millis(20)).await;

    let chaos_stats = app
        .clone()
        .oneshot(
            Request::builder()
                .uri("/platform/tools/chaos/stats")
                .header(header::COOKIE, &admin_cookie)
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();
    let chaos_stats: Value =
        serde_json::from_slice(&to_bytes(chaos_stats.into_body(), 4096).await.unwrap()).unwrap();
    assert_eq!(chaos_stats["redis_outage"], false);
    assert!(chaos_stats["error_budget_burn"].is_number());

    let restart = app
        .oneshot(
            Request::builder()
                .method("POST")
                .uri("/platform/security/restart")
                .header(header::COOKIE, admin_cookie)
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();
    assert_eq!(restart.status(), StatusCode::CONFLICT);
    let restart: Value =
        serde_json::from_slice(&to_bytes(restart.into_body(), 4096).await.unwrap()).unwrap();
    assert_eq!(restart["error_code"], "SEC004");
}

#[tokio::test]
async fn dashboard_preserves_python_v2_response_contract() {
    let app = build_router(memory_state(false).await);
    let (cookie, _) = login(&app).await;

    let response = app
        .oneshot(
            Request::builder()
                .uri("/platform/dashboard")
                .header(header::COOKIE, cookie)
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();
    assert_eq!(response.status(), StatusCode::OK);
    let body: Value =
        serde_json::from_slice(&to_bytes(response.into_body(), 64 * 1024).await.unwrap()).unwrap();

    for key in [
        "totalRequests",
        "activeUsers",
        "newApis",
        "monthlyUsage",
        "activeUsersList",
        "popularApis",
    ] {
        assert!(body.get(key).is_some(), "missing dashboard field {key}");
    }
    assert!(body["totalRequests"].is_number());
    assert!(body["monthlyUsage"].is_object());
    assert!(body.get("users").is_none());
}

#[tokio::test]
async fn analytics_routes_preserve_python_v2_response_contracts() {
    use doorman_gateway::observability::analytics_aggregator::global_analytics;

    global_analytics().record_request(
        Some("rest:contract-analytics"),
        Some("analytics-user"),
        Some("/contract-analytics/v1/items"),
        503,
        25.0,
        11,
        29,
    );

    let app = build_router(memory_state(false).await);
    let (cookie, _) = login(&app).await;

    let overview = app
        .clone()
        .oneshot(
            Request::builder()
                .uri("/platform/analytics/overview?range=1h")
                .header(header::COOKIE, &cookie)
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();
    assert_eq!(overview.status(), StatusCode::OK);
    let overview: Value =
        serde_json::from_slice(&to_bytes(overview.into_body(), 64 * 1024).await.unwrap()).unwrap();
    assert!(overview["summary"]["total_requests"].as_u64().unwrap() >= 1);
    assert!(overview["time_range"]["duration_seconds"].is_number());
    assert!(overview["percentiles"]["p95"].is_number());
    assert!(overview["top_apis"].is_array());
    assert!(overview["status_distribution"].is_object());

    let timeseries = app
        .clone()
        .oneshot(
            Request::builder()
                .uri("/platform/analytics/timeseries?range=1h&metric_type=error_rate")
                .header(header::COOKIE, &cookie)
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();
    let timeseries: Value =
        serde_json::from_slice(&to_bytes(timeseries.into_body(), 64 * 1024).await.unwrap())
            .unwrap();
    assert_eq!(timeseries["granularity"], "auto");
    assert_eq!(
        timeseries["data_points"],
        timeseries["series"].as_array().unwrap().len()
    );
    assert!(timeseries["series"][0]["error_rate"].is_number());

    let top = app
        .clone()
        .oneshot(
            Request::builder()
                .uri("/platform/analytics/top-apis?limit=1")
                .header(header::COOKIE, &cookie)
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();
    let top: Value =
        serde_json::from_slice(&to_bytes(top.into_body(), 64 * 1024).await.unwrap()).unwrap();
    assert!(top["top_apis"][0]["api"].is_string());
    assert!(top["total_apis"].is_number());

    let detail = app
        .oneshot(
            Request::builder()
                .uri("/platform/analytics/api/contract-analytics/v1?range=1h")
                .header(header::COOKIE, cookie)
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();
    assert_eq!(detail.status(), StatusCode::OK);
    let detail: Value =
        serde_json::from_slice(&to_bytes(detail.into_body(), 64 * 1024).await.unwrap()).unwrap();
    assert_eq!(detail["api_name"], "contract-analytics");
    assert_eq!(detail["version"], "v1");
    assert_eq!(detail["summary"]["api"], "rest:contract-analytics");
}
