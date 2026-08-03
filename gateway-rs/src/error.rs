use axum::{
    Json,
    response::{IntoResponse, Response},
};
use http::StatusCode;
use serde::Serialize;
use thiserror::Error;

#[derive(Debug, Error)]
pub enum GatewayError {
    #[error("platform proxy request failed: {0}")]
    Proxy(#[from] reqwest::Error),
    #[error("failed to build proxy response: {0}")]
    Response(#[from] http::Error),
    #[error("failed to read gateway request body: {0}")]
    Body(#[from] axum::Error),
}

#[derive(Serialize)]
struct ErrorBody {
    error_code: &'static str,
    error_message: &'static str,
}

impl IntoResponse for GatewayError {
    fn into_response(self) -> Response {
        tracing::error!(error = %self, "gateway request failed");
        (
            StatusCode::BAD_GATEWAY,
            Json(ErrorBody {
                error_code: "GTW006",
                error_message: "Platform service unavailable",
            }),
        )
            .into_response()
    }
}
