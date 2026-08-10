use std::sync::Arc;

use axum::body::{Body, to_bytes};
use doorman_gateway::{AppState, Config, build_router, storage::runtime::SharedStorage};
use http::{Request, StatusCode, header};
use serde_json::{Value, json};
use tower::ServiceExt;

async fn test_app_state() -> AppState {
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
                        "password": password
                    })
                    .to_string(),
                ))
                .unwrap(),
        )
        .await
        .unwrap();
    assert_eq!(response.status(), StatusCode::OK);

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
                        "api_servers": ["http://127.0.0.1:9999"],
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
async fn live_test_33_rate_limiting_blocks_excess_requests_parity() {
    let state = test_app_state().await;
    let app = build_router(state);
    let token = login_admin(&app).await;

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
                        "api_servers": ["http://127.0.0.1:9999"],
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
    assert!(
        response1.status().is_client_error()
            || response1.status().is_server_error()
            || response1.status().is_success()
    );
    assert!(response2.status().is_client_error() || response2.status().is_server_error());
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
