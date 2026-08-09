use std::sync::Arc;

use axum::body::{Body, to_bytes};
use doorman_gateway::{AppState, Config, build_router, storage::runtime::SharedStorage};
use http::{Request, StatusCode, header};
use serde_json::{Value, json};
use tower::ServiceExt;

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

#[tokio::test]
async fn platform_preflight_is_public_and_uses_legacy_cors_defaults() {
    let app = build_router(memory_state(false).await);
    let response = app
        .oneshot(
            Request::builder()
                .method("OPTIONS")
                .uri("/platform/api")
                .header(header::ORIGIN, "https://client.example")
                .header(header::ACCESS_CONTROL_REQUEST_METHOD, "GET")
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();

    assert_eq!(response.status(), StatusCode::NO_CONTENT);
    assert_eq!(
        response.headers()[header::ACCESS_CONTROL_ALLOW_ORIGIN],
        "https://client.example"
    );
    assert_eq!(
        response.headers()[header::ACCESS_CONTROL_ALLOW_CREDENTIALS],
        "true"
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

    let accepted = app
        .oneshot(
            Request::builder()
                .uri("/platform/user/me")
                .header(header::COOKIE, cookie)
                .header("x-csrf-token", csrf)
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();
    assert_eq!(accepted.status(), StatusCode::OK);
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
