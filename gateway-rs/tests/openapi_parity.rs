use std::sync::Arc;

use axum::body::{Body, to_bytes};
use doorman_gateway::{AppState, Config, build_router, storage::runtime::SharedStorage};
use http::{Request, StatusCode, header};
use serde_json::{Value, json};
use tower::ServiceExt;

async fn platform_app() -> axum::Router {
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
                "manage_apis": true
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
                "active": true
            }),
        )
        .await
        .unwrap();

    let mut state = AppState::new(config).unwrap();
    state.storage = Some(Arc::new(storage));
    build_router(state)
}

async fn login(app: &axum::Router) -> String {
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
    let body = to_bytes(response.into_body(), usize::MAX).await.unwrap();
    let body: Value =
        serde_json::from_slice(&body).expect("login response must contain valid JSON");
    body["access_token"].as_str().unwrap().to_owned()
}

#[tokio::test]
async fn openapi_matches_the_pinned_python_surface() {
    let app = platform_app().await;
    let token = login(&app).await;
    let response = app
        .oneshot(
            Request::builder()
                .uri("/platform/openapi.json")
                .header(header::AUTHORIZATION, format!("Bearer {token}"))
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();
    assert_eq!(response.status(), StatusCode::OK);
    let body = to_bytes(response.into_body(), usize::MAX).await.unwrap();
    let contract: Value = serde_json::from_slice(&body).unwrap();
    let paths = contract["paths"].as_object().unwrap();
    let operations = paths
        .values()
        .flat_map(|path| path.as_object().unwrap().keys())
        .filter(|method| {
            matches!(
                method.as_str(),
                "get" | "post" | "put" | "patch" | "delete" | "options" | "head" | "trace"
            )
        })
        .count();
    let parameters = paths
        .values()
        .flat_map(|path| path.as_object().unwrap().values())
        .filter_map(Value::as_object)
        .filter_map(|operation| operation.get("parameters"))
        .filter_map(Value::as_array)
        .map(Vec::len)
        .sum::<usize>();
    assert_eq!(paths.len(), 136);
    assert_eq!(operations, 178);
    assert_eq!(
        contract["components"]["schemas"].as_object().unwrap().len(),
        60
    );
    assert_eq!(parameters, 216);
}
