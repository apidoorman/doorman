use axum::{
    Json, Router, middleware as axum_middleware,
    response::{IntoResponse, Response},
    routing::{any, get},
};
use http::StatusCode;
use tower_http::{
    catch_panic::CatchPanicLayer,
    compression::{CompressionLayer, CompressionLevel, predicate::SizeAbove},
    trace::TraceLayer,
};

use crate::{
    middleware::{
        activity::track_active_requests, chaos::chaos_middleware, platform_cors::platform_cors,
        request_id::request_id, response_compat::response_compat,
        security_headers::security_headers,
    },
    policy::PolicyErrorBody,
    routes::{
        graphql::graphql_policy_then_execute,
        grpc::grpc_policy_then_execute,
        grpc_web::grpc_web_policy_then_execute,
        metrics::metrics,
        operations::{caches, health, status},
        platform::platform_dispatch,
        rest::rest_policy_then_proxy,
        soap::soap_policy_then_execute,
    },
    state::AppState,
};

pub fn build_router(state: AppState) -> Router {
    let compression = CompressionLayer::new()
        .gzip(state.config.compression_enabled)
        .no_br()
        .no_deflate()
        .no_zstd()
        .quality(CompressionLevel::Precise(state.config.compression_level))
        // Starlette treats the legacy gateway responses as streaming and emits
        // gzip whenever the client accepts it, even below its configured size.
        // Preserve that observed public wire contract during the Rust cutover.
        .compress_when(SizeAbove::new(1));
    let api = Router::new()
        .route("/rest/{*path}", any(rest_policy_then_proxy))
        .route("/graphql/{*path}", any(graphql_policy_then_execute))
        .route("/soap/{*path}", any(soap_policy_then_execute))
        .route("/grpc/{*path}", any(grpc_policy_then_execute))
        .route("/health", any(health))
        .route("/status", any(status))
        .route("/caches", any(caches))
        .fallback(gateway_route_not_found)
        .layer(axum_middleware::from_fn(chaos_middleware))
        .layer(axum_middleware::from_fn_with_state(
            state.clone(),
            response_compat,
        ))
        .layer(axum_middleware::from_fn_with_state(
            state.clone(),
            security_headers,
        ))
        .layer(axum_middleware::from_fn(request_id))
        .layer(TraceLayer::new_for_http())
        .layer(CatchPanicLayer::new());
    let platform = Router::new()
        .route("/", any(platform_dispatch))
        .route("/{*path}", any(platform_dispatch))
        .layer(axum_middleware::from_fn_with_state(
            state.clone(),
            response_compat,
        ))
        .layer(axum_middleware::from_fn_with_state(
            state.clone(),
            security_headers,
        ))
        .layer(axum_middleware::from_fn(platform_cors))
        .layer(axum_middleware::from_fn(request_id))
        .layer(TraceLayer::new_for_http())
        .layer(CatchPanicLayer::new());

    Router::new()
        .nest("/api", api)
        .nest("/platform", platform)
        .route(
            "/grpc-web/{api_name}/{service}/{method}",
            any(grpc_web_policy_then_execute),
        )
        .route("/metrics", get(metrics))
        .fallback(not_found)
        .layer(axum_middleware::from_fn_with_state(
            state.clone(),
            track_active_requests,
        ))
        .layer(compression)
        .with_state(state)
}

async fn gateway_route_not_found() -> Response {
    (
        StatusCode::NOT_FOUND,
        Json(PolicyErrorBody {
            error_code: "GTW003".to_owned(),
            error_message: "Gateway route does not exist".to_owned(),
        }),
    )
        .into_response()
}

async fn not_found() -> Response {
    StatusCode::NOT_FOUND.into_response()
}
