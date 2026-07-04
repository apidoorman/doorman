use axum::{Router, middleware as axum_middleware, routing::get};
use tower_http::{catch_panic::CatchPanicLayer, trace::TraceLayer};

use crate::{
    middleware::{request_id::request_id, security_headers::security_headers},
    proxy::platform::proxy_to_python,
    routes::operations::health,
    state::AppState,
};

pub fn build_router(state: AppState) -> Router {
    if !state.config.mode.rust_routes_enabled() {
        return Router::new().fallback(proxy_to_python).with_state(state);
    }

    let api = Router::new()
        .route("/health", get(health))
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
