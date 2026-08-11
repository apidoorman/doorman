use axum::body::{Body, to_bytes};
use doorman_gateway::{AppState, Config, build_router};
use http::{Request, StatusCode};
use serde_json::Value;
use tower::ServiceExt;

#[tokio::test]
async fn openapi_matches_the_pinned_python_surface() {
    let app = build_router(
        AppState::new(Config::for_test("removed-internal-backend".to_owned())).unwrap(),
    );
    let response = app
        .oneshot(
            Request::builder()
                .uri("/platform/openapi.json")
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
