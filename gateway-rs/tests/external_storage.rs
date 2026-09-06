use std::sync::Arc;

use axum::{
    Router,
    body::{Body, to_bytes},
    response::Response,
    routing::post,
};
use doorman_gateway::{
    AppState, Config, build_router, config::SharedStorageConfig, storage::runtime::SharedStorage,
};
use http::{Method, Request, StatusCode, header};
use serde_json::json;
use tokio::task::JoinHandle;
use tokio::time::{Duration, sleep};
use tower::ServiceExt;
use uuid::Uuid;

fn enabled() -> bool {
    std::env::var("DOORMAN_EXTERNAL_STORAGE_TEST").as_deref() == Ok("1")
}

#[tokio::test]
async fn external_storage_shares_mongo_documents_and_redis_state() {
    if !enabled() {
        eprintln!("set DOORMAN_EXTERNAL_STORAGE_TEST=1 to run external storage coverage");
        return;
    }

    let mongo_port =
        std::env::var("DOORMAN_TEST_MONGO_PORT").unwrap_or_else(|_| "27018".to_owned());
    let redis_port =
        std::env::var("DOORMAN_TEST_REDIS_PORT").unwrap_or_else(|_| "16379".to_owned());
    let nonce = Uuid::new_v4().simple().to_string();
    let config = SharedStorageConfig {
        storage_mode: "REDIS".to_owned(),
        mongo_uri_override: Some(format!("mongodb://127.0.0.1:{mongo_port}/?replicaSet=rs0")),
        mongo_database: format!("doorman_external_test_{nonce}"),
        redis_host: "127.0.0.1".to_owned(),
        redis_port: redis_port.parse().unwrap(),
        redis_password: None,
        ..Default::default()
    };

    let first = SharedStorage::connect(&config).await.unwrap();
    let second = SharedStorage::connect(&config).await.unwrap();
    assert!(!first.is_memory());
    let marker = format!("external-{nonce}");
    first
        .insert_one("apis", json!({"api_name": marker, "api_version": "v1"}))
        .await
        .unwrap();
    assert!(
        second
            .find_one("apis", &json!({"api_name": marker, "api_version": "v1"}))
            .await
            .unwrap()
            .is_some()
    );
    assert!(
        second
            .insert_one("apis", json!({"api_name": marker, "api_version": "v1"}))
            .await
            .is_err()
    );

    let ephemeral_key = format!("external-storage:ephemeral:{nonce}");
    first
        .set_ephemeral(&ephemeral_key, json!({"source": "first"}), 60)
        .await
        .unwrap();
    assert_eq!(
        second.get_ephemeral(&ephemeral_key).await.unwrap(),
        Some(json!({"source": "first"}))
    );
    let counter_key = format!("external-storage:counter:{nonce}");
    assert_eq!(first.increment_window(&counter_key, 60).await.unwrap(), 1);
    assert_eq!(second.increment_window(&counter_key, 60).await.unwrap(), 2);
    let routing_key = format!("external-storage:routing:{nonce}");
    assert_eq!(first.next_routing_index(&routing_key, 2).await.unwrap(), 0);
    assert_eq!(second.next_routing_index(&routing_key, 2).await.unwrap(), 1);

    let ttl_key = format!("external-storage:ttl:{nonce}");
    first.set_ephemeral(&ttl_key, json!(true), 1).await.unwrap();
    assert_eq!(
        second.get_ephemeral(&ttl_key).await.unwrap(),
        Some(json!(true))
    );
    sleep(Duration::from_secs(2)).await;
    assert_eq!(second.get_ephemeral(&ttl_key).await.unwrap(), None);
}

#[tokio::test]
async fn external_revocation_is_shared_and_expired_record_is_removed() {
    if !enabled() {
        eprintln!("set DOORMAN_EXTERNAL_STORAGE_TEST=1 to run external storage coverage");
        return;
    }

    let mongo_port =
        std::env::var("DOORMAN_TEST_MONGO_PORT").unwrap_or_else(|_| "27018".to_owned());
    let redis_port =
        std::env::var("DOORMAN_TEST_REDIS_PORT").unwrap_or_else(|_| "16379".to_owned());
    let nonce = Uuid::new_v4().simple().to_string();
    let storage_config = SharedStorageConfig {
        storage_mode: "REDIS".to_owned(),
        mongo_uri_override: Some(format!("mongodb://127.0.0.1:{mongo_port}/?replicaSet=rs0")),
        mongo_database: format!("doorman_external_auth_{nonce}"),
        redis_host: "127.0.0.1".to_owned(),
        redis_port: redis_port.parse().unwrap(),
        redis_password: None,
        ..Default::default()
    };

    let first = SharedStorage::connect(&storage_config).await.unwrap();
    let second = SharedStorage::connect(&storage_config).await.unwrap();
    let username = format!("external-auth-{nonce}");
    let password = "ExternalPassword123!";
    first
        .insert_one("roles", json!({"role_name": "user"}))
        .await
        .unwrap();
    first
        .insert_one(
            "users",
            json!({
                "username": username,
                "email": format!("{username}@example.test"),
                "password": bcrypt::hash(password, bcrypt::DEFAULT_COST).unwrap(),
                "role": "user",
                "groups": ["ALL"],
                "active": true,
                "ui_access": true
            }),
        )
        .await
        .unwrap();

    let mut first_config = Config::for_test("removed-internal-backend".to_owned());
    first_config.shared_storage = storage_config.clone();
    let mut first_state = AppState::new(first_config).unwrap();
    first_state.storage = Some(Arc::new(first));
    let first_app = build_router(first_state);

    let mut second_config = Config::for_test("removed-internal-backend".to_owned());
    second_config.shared_storage = storage_config;
    let mut second_state = AppState::new(second_config).unwrap();
    second_state.storage = Some(Arc::new(second.clone()));
    let second_app = build_router(second_state);

    let login = first_app
        .clone()
        .oneshot(
            Request::builder()
                .method(Method::POST)
                .uri("/platform/authorization")
                .header(header::CONTENT_TYPE, "application/json")
                .body(Body::from(
                    json!({
                        "email": format!("{username}@example.test"),
                        "password": password
                    })
                    .to_string(),
                ))
                .unwrap(),
        )
        .await
        .unwrap();
    assert_eq!(login.status(), StatusCode::OK);
    let cookie = login
        .headers()
        .get_all(header::SET_COOKIE)
        .iter()
        .filter_map(|value| value.to_str().ok())
        .map(|value| value.split(';').next().unwrap().to_owned())
        .find(|cookie| cookie.starts_with("access_token_cookie="))
        .unwrap();

    let invalidate = first_app
        .clone()
        .oneshot(
            Request::builder()
                .method(Method::POST)
                .uri("/platform/authorization/invalidate")
                .header(header::COOKIE, &cookie)
                .header(header::CONTENT_TYPE, "application/json")
                .body(Body::from("{}"))
                .unwrap(),
        )
        .await
        .unwrap();
    assert_eq!(invalidate.status(), StatusCode::OK);

    let rejected = second_app
        .clone()
        .oneshot(
            Request::builder()
                .method(Method::GET)
                .uri("/platform/authorization/status")
                .header(header::COOKIE, &cookie)
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();
    assert_eq!(rejected.status(), StatusCode::UNAUTHORIZED);

    let revocation = second
        .find_one("revocations", &json!({"type": "jti", "username": username}))
        .await
        .unwrap()
        .unwrap();
    let filter = json!({
        "type": "jti",
        "username": username,
        "jti": revocation["jti"].clone()
    });
    second
        .update_one("revocations", &filter, &json!({"expires_at": 0}))
        .await
        .unwrap();

    let restored = second_app
        .clone()
        .oneshot(
            Request::builder()
                .method(Method::GET)
                .uri("/platform/authorization/status")
                .header(header::COOKIE, &cookie)
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();
    assert_eq!(restored.status(), StatusCode::OK);
    assert!(
        second
            .find_one("revocations", &filter)
            .await
            .unwrap()
            .is_none()
    );
}
#[tokio::test]
async fn external_api_and_endpoint_survive_router_restart() {
    if !enabled() {
        eprintln!("set DOORMAN_EXTERNAL_STORAGE_TEST=1 to run external storage coverage");
        return;
    }

    let mongo_port =
        std::env::var("DOORMAN_TEST_MONGO_PORT").unwrap_or_else(|_| "27018".to_owned());
    let redis_port =
        std::env::var("DOORMAN_TEST_REDIS_PORT").unwrap_or_else(|_| "16379".to_owned());
    let nonce = Uuid::new_v4().simple().to_string();
    let storage_config = SharedStorageConfig {
        storage_mode: "REDIS".to_owned(),
        mongo_uri_override: Some(format!("mongodb://127.0.0.1:{mongo_port}/?replicaSet=rs0")),
        mongo_database: format!("doorman_external_restart_{nonce}"),
        redis_host: "127.0.0.1".to_owned(),
        redis_port: redis_port.parse().unwrap(),
        redis_password: None,
        ..Default::default()
    };
    let username = format!("restart-admin-{nonce}");
    let password = "ExternalPassword123!";
    let storage = SharedStorage::connect(&storage_config).await.unwrap();
    storage
        .insert_one(
            "roles",
            json!({
                "role_name": "admin",
                "manage_apis": true,
                "manage_endpoints": true,
                "manage_gateway": true
            }),
        )
        .await
        .unwrap();
    storage
        .insert_one(
            "users",
            json!({
                "username": username,
                "email": format!("{username}@example.test"),
                "password": bcrypt::hash(password, bcrypt::DEFAULT_COST).unwrap(),
                "role": "admin",
                "groups": ["ALL", "admin"],
                "active": true,
                "ui_access": true
            }),
        )
        .await
        .unwrap();

    let mut config = Config::for_test("removed-internal-backend".to_owned());
    config.shared_storage = storage_config.clone();
    let mut state = AppState::new(config).unwrap();
    state.storage = Some(Arc::new(storage));
    let app = build_router(state);
    let login = app
        .clone()
        .oneshot(
            Request::builder()
                .method(Method::POST)
                .uri("/platform/authorization")
                .header(header::CONTENT_TYPE, "application/json")
                .body(Body::from(
                    json!({
                        "email": format!("{username}@example.test"),
                        "password": password
                    })
                    .to_string(),
                ))
                .unwrap(),
        )
        .await
        .unwrap();
    assert_eq!(login.status(), StatusCode::OK);
    let cookie = login
        .headers()
        .get_all(header::SET_COOKIE)
        .iter()
        .filter_map(|value| value.to_str().ok())
        .map(|value| value.split(';').next().unwrap().to_owned())
        .find(|value| value.starts_with("access_token_cookie="))
        .unwrap();

    let api_name = format!("restart-api-{nonce}");
    let api = app
        .clone()
        .oneshot(
            Request::builder()
                .method(Method::POST)
                .uri("/platform/api")
                .header(header::COOKIE, &cookie)
                .header(header::CONTENT_TYPE, "application/json")
                .body(Body::from(
                    json!({
                        "api_name": api_name,
                        "api_version": "v1",
                        "api_description": "external restart coverage",
                        "api_servers": ["http://upstream.example.test"],
                        "api_type": "REST"
                    })
                    .to_string(),
                ))
                .unwrap(),
        )
        .await
        .unwrap();
    assert_eq!(api.status(), StatusCode::CREATED);
    let endpoint = app
        .clone()
        .oneshot(
            Request::builder()
                .method(Method::POST)
                .uri("/platform/endpoint")
                .header(header::COOKIE, &cookie)
                .header(header::CONTENT_TYPE, "application/json")
                .body(Body::from(
                    json!({
                        "api_name": api_name,
                        "api_version": "v1",
                        "endpoint_method": "GET",
                        "endpoint_uri": "/health",
                        "endpoint_description": "restart endpoint"
                    })
                    .to_string(),
                ))
                .unwrap(),
        )
        .await
        .unwrap();
    assert_eq!(endpoint.status(), StatusCode::CREATED);

    let replacement = app
        .clone()
        .oneshot(
            Request::builder()
                .method(Method::POST)
                .uri("/platform/config/import")
                .header(header::COOKIE, &cookie)
                .header(header::CONTENT_TYPE, "application/json")
                .body(Body::from(
                    json!({
                        "apis": [{
                            "api_name": format!("replacement-{nonce}"),
                            "api_version": "v1",
                            "api_type": "REST"
                        }]
                    })
                    .to_string(),
                ))
                .unwrap(),
        )
        .await
        .unwrap();
    assert_eq!(replacement.status(), StatusCode::OK);
    let rollback = app
        .clone()
        .oneshot(
            Request::builder()
                .method(Method::POST)
                .uri("/platform/config/rollback")
                .header(header::COOKIE, &cookie)
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();
    assert_eq!(rollback.status(), StatusCode::OK);

    let restarted_storage = SharedStorage::connect(&storage_config).await.unwrap();
    let mut restarted_config = Config::for_test("removed-internal-backend".to_owned());
    restarted_config.shared_storage = storage_config;
    let mut restarted_state = AppState::new(restarted_config).unwrap();
    restarted_state.storage = Some(Arc::new(restarted_storage));
    let restarted_app = build_router(restarted_state);
    for path in [
        format!("/platform/api/{api_name}/v1"),
        format!("/platform/endpoint/GET/{api_name}/v1/health"),
    ] {
        let response = restarted_app
            .clone()
            .oneshot(
                Request::builder()
                    .method(Method::GET)
                    .uri(&path)
                    .header(header::COOKIE, &cookie)
                    .body(Body::empty())
                    .unwrap(),
            )
            .await
            .unwrap();
        assert_eq!(response.status(), StatusCode::OK, "{path}");
        let response_json: serde_json::Value =
            serde_json::from_slice(&to_bytes(response.into_body(), 16 * 1024).await.unwrap())
                .unwrap();
        assert!(
            response_json.get("_id").is_none(),
            "{path} leaked storage ID"
        );
    }
}

async fn external_grpc_upstream(request: axum::extract::Request) -> Response {
    assert_eq!(request.version(), http::Version::HTTP_2);
    let body = to_bytes(request.into_body(), 1024).await.unwrap();
    assert_eq!(body.as_ref(), b"\x00\x00\x00\x00\x09\x0a\x07Doorman");
    let reply = b"Hello, Doorman!";
    let mut framed = vec![0, 0, 0, 0, (reply.len() + 2) as u8, 0x0a, reply.len() as u8];
    framed.extend_from_slice(reply);
    Response::builder()
        .status(StatusCode::OK)
        .header(header::CONTENT_TYPE, "application/grpc")
        .header("grpc-status", "0")
        .body(Body::from(framed))
        .unwrap()
}

async fn start_external_grpc_upstream() -> (String, JoinHandle<()>) {
    let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
    let address = listener.local_addr().unwrap();
    let server = tokio::spawn(async move {
        axum::serve(
            listener,
            Router::new().route(
                "/externalgrpc_v1.Greeter/Hello",
                post(external_grpc_upstream),
            ),
        )
        .await
        .unwrap();
    });
    (format!("grpc://{address}"), server)
}

#[tokio::test]
async fn external_grpc_descriptor_and_subscription_survive_router_restart() {
    if !enabled() {
        eprintln!("set DOORMAN_EXTERNAL_STORAGE_TEST=1 to run external storage coverage");
        return;
    }

    let mongo_port =
        std::env::var("DOORMAN_TEST_MONGO_PORT").unwrap_or_else(|_| "27018".to_owned());
    let redis_port =
        std::env::var("DOORMAN_TEST_REDIS_PORT").unwrap_or_else(|_| "16379".to_owned());
    let nonce = Uuid::new_v4().simple().to_string();
    let storage_config = SharedStorageConfig {
        storage_mode: "REDIS".to_owned(),
        mongo_uri_override: Some(format!("mongodb://127.0.0.1:{mongo_port}/?replicaSet=rs0")),
        mongo_database: format!("doorman_external_grpc_{nonce}"),
        redis_host: "127.0.0.1".to_owned(),
        redis_port: redis_port.parse().unwrap(),
        redis_password: None,
        ..Default::default()
    };
    let username = format!("grpc-admin-{nonce}");
    let password = "ExternalGrpcPassword123!";
    let storage = SharedStorage::connect(&storage_config).await.unwrap();
    storage
        .insert_one(
            "roles",
            json!({
                "role_name": "admin",
                "manage_apis": true,
                "manage_endpoints": true,
                "manage_subscriptions": true
            }),
        )
        .await
        .unwrap();
    storage
        .insert_one(
            "users",
            json!({
                "username": username,
                "email": format!("{username}@example.test"),
                "password": bcrypt::hash(password, bcrypt::DEFAULT_COST).unwrap(),
                "role": "admin",
                "groups": ["ALL", "admin"],
                "active": true,
                "ui_access": true
            }),
        )
        .await
        .unwrap();

    let mut first_config = Config::for_test("removed-internal-backend".to_owned());
    first_config.shared_storage = storage_config.clone();
    let mut first_state = AppState::new(first_config).unwrap();
    first_state.storage = Some(Arc::new(storage));
    let first_app = build_router(first_state);
    let login = first_app
        .clone()
        .oneshot(
            Request::builder()
                .method(Method::POST)
                .uri("/platform/authorization")
                .header(header::CONTENT_TYPE, "application/json")
                .body(Body::from(
                    json!({
                        "email": format!("{username}@example.test"),
                        "password": password
                    })
                    .to_string(),
                ))
                .unwrap(),
        )
        .await
        .unwrap();
    assert_eq!(login.status(), StatusCode::OK);
    let cookie = login
        .headers()
        .get_all(header::SET_COOKIE)
        .iter()
        .filter_map(|value| value.to_str().ok())
        .map(|value| value.split(';').next().unwrap().to_owned())
        .find(|value| value.starts_with("access_token_cookie="))
        .unwrap();

    let (upstream_url, upstream) = start_external_grpc_upstream().await;
    let api_name = format!("external-grpc-{nonce}");
    let api_version = "v1";
    let api = first_app
        .clone()
        .oneshot(
            Request::builder()
                .method(Method::POST)
                .uri("/platform/api")
                .header(header::COOKIE, &cookie)
                .header(header::CONTENT_TYPE, "application/json")
                .body(Body::from(
                    json!({
                        "api_name": api_name,
                        "api_version": api_version,
                        "api_description": "external gRPC restart coverage",
                        "api_allowed_roles": ["admin"],
                        "api_allowed_groups": ["ALL"],
                        "api_servers": [upstream_url],
                        "api_type": "GRPC",
                        "active": true
                    })
                    .to_string(),
                ))
                .unwrap(),
        )
        .await
        .unwrap();
    assert_eq!(api.status(), StatusCode::CREATED);

    let proto = r#"
syntax = "proto3";
package externalgrpc_v1;
service Greeter { rpc Hello (HelloRequest) returns (HelloReply) {} }
message HelloRequest { string name = 1; }
message HelloReply { string message = 1; }
"#;
    let uploaded = first_app
        .clone()
        .oneshot(
            Request::builder()
                .method(Method::POST)
                .uri(format!("/platform/proto/{api_name}/{api_version}"))
                .header(header::COOKIE, &cookie)
                .header(header::CONTENT_TYPE, "text/plain")
                .body(Body::from(proto))
                .unwrap(),
        )
        .await
        .unwrap();
    assert_eq!(uploaded.status(), StatusCode::OK);

    for payload in [
        json!({
            "api_name": api_name,
            "api_version": api_version,
            "endpoint_method": "POST",
            "endpoint_uri": "/grpc",
            "endpoint_description": "external gRPC endpoint"
        }),
        json!({"username": username, "api_name": api_name, "api_version": api_version}),
    ] {
        let path = if payload.get("endpoint_uri").is_some() {
            "/platform/endpoint"
        } else {
            "/platform/subscription/subscribe"
        };
        let response = first_app
            .clone()
            .oneshot(
                Request::builder()
                    .method(Method::POST)
                    .uri(path)
                    .header(header::COOKIE, &cookie)
                    .header(header::CONTENT_TYPE, "application/json")
                    .body(Body::from(payload.to_string()))
                    .unwrap(),
            )
            .await
            .unwrap();
        assert!(
            response.status().is_success(),
            "{path}: {}",
            response.status()
        );
    }

    let restarted_storage = SharedStorage::connect(&storage_config).await.unwrap();
    let mut restarted_config = Config::for_test("removed-internal-backend".to_owned());
    restarted_config.shared_storage = storage_config;
    let mut restarted_state = AppState::new(restarted_config).unwrap();
    restarted_state.storage = Some(Arc::new(restarted_storage));
    let restarted_app = build_router(restarted_state);
    let response = restarted_app
        .clone()
        .oneshot(
            Request::builder()
                .method(Method::POST)
                .uri(format!("/api/grpc/{api_name}"))
                .header(header::COOKIE, &cookie)
                .header("x-api-version", api_version)
                .header(header::CONTENT_TYPE, "application/json")
                .body(Body::from(
                    json!({"method": "Greeter.Hello", "message": {"name": "Doorman"}}).to_string(),
                ))
                .unwrap(),
        )
        .await
        .unwrap();
    assert_eq!(response.status(), StatusCode::OK);
    let body: serde_json::Value =
        serde_json::from_slice(&to_bytes(response.into_body(), 16 * 1024).await.unwrap()).unwrap();
    assert_eq!(body, json!({"message": "Hello, Doorman!"}));
    upstream.abort();
}

#[tokio::test]
async fn external_control_plane_collections_persist_mutations_across_reconnect() {
    if !enabled() {
        eprintln!("set DOORMAN_EXTERNAL_STORAGE_TEST=1 to run external storage coverage");
        return;
    }

    let mongo_port =
        std::env::var("DOORMAN_TEST_MONGO_PORT").unwrap_or_else(|_| "27018".to_owned());
    let redis_port =
        std::env::var("DOORMAN_TEST_REDIS_PORT").unwrap_or_else(|_| "16379".to_owned());
    let nonce = Uuid::new_v4().simple().to_string();
    let config = SharedStorageConfig {
        storage_mode: "REDIS".to_owned(),
        mongo_uri_override: Some(format!("mongodb://127.0.0.1:{mongo_port}/?replicaSet=rs0")),
        mongo_database: format!("doorman_external_collections_{nonce}"),
        redis_host: "127.0.0.1".to_owned(),
        redis_port: redis_port.parse().unwrap(),
        redis_password: None,
        ..Default::default()
    };
    let marker = format!("external-collection-{nonce}");
    let records = vec![
        (
            "roles",
            json!({"external_id": marker, "role_name": format!("role-{nonce}")}),
        ),
        (
            "groups",
            json!({"external_id": marker, "group_name": format!("group-{nonce}")}),
        ),
        (
            "users",
            json!({"external_id": marker, "username": format!("user-{nonce}")}),
        ),
        (
            "subscriptions",
            json!({"external_id": marker, "username": format!("subscription-{nonce}"), "apis": []}),
        ),
        (
            "credit_defs",
            json!({"external_id": marker, "api_credit_group": format!("credit-{nonce}")}),
        ),
        (
            "user_credits",
            json!({"external_id": marker, "username": format!("credit-user-{nonce}")}),
        ),
        (
            "tiers",
            json!({"external_id": marker, "tier_name": format!("tier-{nonce}")}),
        ),
        (
            "user_tier_assignments",
            json!({"external_id": marker, "user_id": format!("tier-user-{nonce}")}),
        ),
        (
            "routings",
            json!({"external_id": marker, "client_key": format!("client-{nonce}")}),
        ),
        (
            "settings",
            json!({"external_id": marker, "setting_name": format!("settings-{nonce}"), "revision": 1}),
        ),
        (
            "config_snapshots",
            json!({"external_id": marker, "snapshot_id": format!("snapshot-{nonce}")}),
        ),
        (
            "vault_entries",
            json!({
                "external_id": marker,
                "username": format!("vault-user-{nonce}"),
                "key_name": format!("vault-key-{nonce}"),
                "encrypted_value": "v1:external-test-ciphertext"
            }),
        ),
    ];

    let first = SharedStorage::connect(&config).await.unwrap();
    for (collection, record) in &records {
        first.insert_one(collection, record.clone()).await.unwrap();
    }

    let second = SharedStorage::connect(&config).await.unwrap();
    let filter = json!({"external_id": marker});
    for (collection, _) in &records {
        let persisted = second.find_one(collection, &filter).await.unwrap();
        assert!(persisted.is_some(), "{collection} was not persisted");
    }
    second
        .update_one("settings", &filter, &json!({"revision": 2}))
        .await
        .unwrap();
    assert!(second.delete_one("routings", &filter).await.unwrap());

    let third = SharedStorage::connect(&config).await.unwrap();
    let settings = third.find_one("settings", &filter).await.unwrap().unwrap();
    assert_eq!(settings["revision"], 2);
    assert!(third.find_one("routings", &filter).await.unwrap().is_none());
}
#[tokio::test]
async fn external_concurrent_policy_state_is_atomic_and_invalidates_across_instances() {
    if !enabled() {
        eprintln!("set DOORMAN_EXTERNAL_STORAGE_TEST=1 to run external storage coverage");
        return;
    }

    let mongo_port =
        std::env::var("DOORMAN_TEST_MONGO_PORT").unwrap_or_else(|_| "27018".to_owned());
    let redis_port =
        std::env::var("DOORMAN_TEST_REDIS_PORT").unwrap_or_else(|_| "16379".to_owned());
    let nonce = Uuid::new_v4().simple().to_string();
    let config = SharedStorageConfig {
        storage_mode: "REDIS".to_owned(),
        mongo_uri_override: Some(format!("mongodb://127.0.0.1:{mongo_port}/?replicaSet=rs0")),
        mongo_database: format!("doorman_external_concurrent_{nonce}"),
        redis_host: "127.0.0.1".to_owned(),
        redis_port: redis_port.parse().unwrap(),
        redis_password: None,
        ..Default::default()
    };
    let first = SharedStorage::connect(&config).await.unwrap();
    let second = SharedStorage::connect(&config).await.unwrap();
    let counter_key = format!("external-concurrent:counter:{nonce}");
    let mut counter_tasks = Vec::new();
    for index in 0..20 {
        let storage = if index % 2 == 0 {
            first.clone()
        } else {
            second.clone()
        };
        let key = counter_key.clone();
        counter_tasks.push(tokio::spawn(async move {
            storage.increment_window(&key, 60).await.unwrap()
        }));
    }
    let mut counter_values = Vec::new();
    for task in counter_tasks {
        counter_values.push(task.await.unwrap());
    }
    counter_values.sort_unstable();
    assert_eq!(counter_values, (1..=20).collect::<Vec<_>>());

    let bandwidth_key = format!("external-concurrent:bandwidth:{nonce}");
    let mut bandwidth_tasks = Vec::new();
    for index in 0..10 {
        let storage = if index % 2 == 0 {
            first.clone()
        } else {
            second.clone()
        };
        let key = bandwidth_key.clone();
        bandwidth_tasks.push(tokio::spawn(async move {
            storage.add_bandwidth(&key, 10, 60).await.unwrap()
        }));
    }
    let mut bandwidth_values = Vec::new();
    for task in bandwidth_tasks {
        bandwidth_values.push(task.await.unwrap());
    }
    assert_eq!(bandwidth_values.into_iter().max(), Some(100));

    let routing_key = format!("external-concurrent:routing:{nonce}");
    let mut routing_tasks = Vec::new();
    for index in 0..12 {
        let storage = if index % 2 == 0 {
            first.clone()
        } else {
            second.clone()
        };
        let key = routing_key.clone();
        routing_tasks.push(tokio::spawn(async move {
            storage.next_routing_index(&key, 3).await.unwrap()
        }));
    }
    let mut routing_counts = [0; 3];
    for task in routing_tasks {
        routing_counts[task.await.unwrap()] += 1;
    }
    assert_eq!(routing_counts, [4, 4, 4]);

    let api_name = format!("cache-api-{nonce}");
    first
        .insert_one(
            "apis",
            json!({
                "api_name": api_name,
                "api_version": "v1",
                "api_description": "before"
            }),
        )
        .await
        .unwrap();
    assert_eq!(
        second
            .load_policy_documents()
            .await
            .unwrap()
            .apis
            .iter()
            .find(|api| api["api_name"] == api_name)
            .unwrap()["api_description"],
        "before"
    );
    first
        .update_one(
            "apis",
            &json!({"api_name": api_name, "api_version": "v1"}),
            &json!({"api_description": "after"}),
        )
        .await
        .unwrap();
    assert_eq!(
        second
            .load_policy_documents()
            .await
            .unwrap()
            .apis
            .iter()
            .find(|api| api["api_name"] == api_name)
            .unwrap()["api_description"],
        "after"
    );
}
#[tokio::test]
async fn external_storage_unavailable_dependencies_fail_closed() {
    if !enabled() {
        eprintln!("set DOORMAN_EXTERNAL_STORAGE_TEST=1 to run external storage coverage");
        return;
    }

    let mongo_port =
        std::env::var("DOORMAN_TEST_MONGO_PORT").unwrap_or_else(|_| "27018".to_owned());
    let redis_port =
        std::env::var("DOORMAN_TEST_REDIS_PORT").unwrap_or_else(|_| "16379".to_owned());
    let base = SharedStorageConfig {
        storage_mode: "REDIS".to_owned(),
        mongo_uri_override: Some(format!("mongodb://127.0.0.1:{mongo_port}/?replicaSet=rs0")),
        mongo_database: format!("doorman_external_failure_{}", Uuid::new_v4().simple()),
        redis_host: "127.0.0.1".to_owned(),
        redis_port: redis_port.parse().unwrap(),
        redis_password: None,
        ..Default::default()
    };

    let mut redis_unavailable = base.clone();
    redis_unavailable.redis_port = 1;
    assert!(matches!(
        tokio::time::timeout(
            Duration::from_secs(2),
            SharedStorage::connect(&redis_unavailable)
        )
        .await,
        Ok(Err(_)) | Err(_)
    ));

    let mut mongo_unavailable = base;
    mongo_unavailable.mongo_uri_override =
        Some("mongodb://127.0.0.1:1/?replicaSet=rs0&serverSelectionTimeoutMS=1000".to_owned());
    assert!(matches!(
        tokio::time::timeout(
            Duration::from_secs(2),
            SharedStorage::connect(&mongo_unavailable)
        )
        .await,
        Ok(Err(_)) | Err(_)
    ));
}
