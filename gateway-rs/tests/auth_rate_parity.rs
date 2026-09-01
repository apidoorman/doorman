use std::sync::Arc;

use axum::body::{Body, to_bytes};
use doorman_gateway::{AppState, Config, build_router, storage::runtime::SharedStorage};
use http::{Request, StatusCode, header};
use serde_json::{Value, json};
use tower::ServiceExt;

#[tokio::test]
async fn login_ip_window_matches_python_error_contract() {
    let mut config = Config::for_test("removed-internal-backend".to_owned());
    config.shared_storage.trust_x_forwarded_for = true;
    let storage = SharedStorage::connect(&config.shared_storage)
        .await
        .unwrap();
    let mut state = AppState::new(config).unwrap();
    state.storage = Some(Arc::new(storage));
    let app = build_router(state);

    for attempt in 1..=6 {
        let response = app
            .clone()
            .oneshot(
                Request::builder()
                    .method("POST")
                    .uri("/platform/authorization")
                    .header(header::CONTENT_TYPE, "application/json")
                    .header("x-forwarded-for", "198.51.100.91")
                    .body(Body::from(json!({}).to_string()))
                    .unwrap(),
            )
            .await
            .unwrap();
        if attempt <= 5 {
            assert_eq!(response.status(), StatusCode::BAD_REQUEST);
            continue;
        }
        assert_eq!(response.status(), StatusCode::TOO_MANY_REQUESTS);
        assert_eq!(response.headers()["x-ratelimit-limit"], "5");
        assert_eq!(response.headers()["x-ratelimit-remaining"], "0");
        assert!(response.headers().contains_key("retry-after"));
        assert!(response.headers().contains_key("x-ratelimit-reset"));
        let body = to_bytes(response.into_body(), 4096).await.unwrap();
        let body: Value = serde_json::from_slice(&body).unwrap();
        assert_eq!(body["detail"]["error_code"], "IP_RATE_LIMIT");
        assert!(body["detail"]["retry_after"].as_u64().is_some());
    }
}
