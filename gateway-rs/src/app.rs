use axum::{Router, middleware as axum_middleware, routing::any};
use tower_http::{catch_panic::CatchPanicLayer, trace::TraceLayer};

use crate::{
    middleware::{request_id::request_id, security_headers::security_headers},
    proxy::platform::proxy_to_python,
    routes::{
        graphql::graphql_policy_then_execute,
        grpc::grpc_policy_then_execute,
        operations::{caches, health, status},
        rest::rest_policy_then_proxy,
        soap::soap_policy_then_execute,
    },
    state::AppState,
};

pub fn build_router(state: AppState) -> Router {
    if state.config.mode.proxies_all_routes() {
        return Router::new().fallback(proxy_to_python).with_state(state);
    }

    let mut api = Router::new();

    if state.config.mode.evaluates_policies() {
        api = api
            .route("/rest/{*path}", any(rest_policy_then_proxy))
            .route("/graphql/{*path}", any(graphql_policy_then_execute))
            .route("/soap/{*path}", any(soap_policy_then_execute))
            .route("/grpc/{*path}", any(grpc_policy_then_execute));
    }

    if state.config.mode.should_serve_rust_route(true) {
        api = api
            .route("/health", any(health))
            .route("/status", any(status))
            .route("/caches", any(caches));
    }

    let api = api
        .fallback(proxy_to_python)
        .layer(axum_middleware::from_fn_with_state(
            state.clone(),
            security_headers,
        ))
        .layer(axum_middleware::from_fn(request_id))
        .layer(TraceLayer::new_for_http())
        .layer(CatchPanicLayer::new());

    Router::new()
        .nest("/api", api)
        .fallback(proxy_to_python)
        .with_state(state)
}
