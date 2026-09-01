use axum::{
    extract::{Path, Request, State},
    response::Response,
};

use crate::{
    error::GatewayError,
    routes::rest::{DataPlaneProtocol, PolicyPath, rest_policy_then_proxy},
    state::AppState,
};

#[derive(Clone, Debug)]
pub struct GrpcWebTarget {
    pub service: String,
    pub method: String,
}

pub async fn grpc_web_policy_then_execute(
    State(state): State<AppState>,
    Path((api_name, service, method)): Path<(String, String, String)>,
    mut request: Request,
) -> Result<Response, GatewayError> {
    if !matches!(
        request.method(),
        &http::Method::POST | &http::Method::OPTIONS
    ) {
        return Ok(http::StatusCode::METHOD_NOT_ALLOWED.into_response());
    }
    let version = request
        .headers()
        .get("x-api-version")
        .and_then(|value| value.to_str().ok())
        .unwrap_or("v1")
        .to_owned();
    request
        .extensions_mut()
        .insert(PolicyPath(format!("/api/rest/{api_name}/{version}/grpc")));
    request.extensions_mut().insert(DataPlaneProtocol::GrpcWeb);
    request
        .extensions_mut()
        .insert(GrpcWebTarget { service, method });
    rest_policy_then_proxy(State(state), request).await
}

use axum::response::IntoResponse;
