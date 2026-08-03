use axum::extract::{Request, State};
use axum::response::Response;

use crate::{
    error::GatewayError,
    routes::rest::{DataPlaneProtocol, PolicyPath, rest_policy_then_proxy},
    state::AppState,
};

pub async fn grpc_policy_then_execute(
    State(state): State<AppState>,
    mut request: Request,
) -> Result<Response, GatewayError> {
    let api_name = request
        .uri()
        .path()
        .trim_start_matches("/api/grpc/")
        .trim_matches('/')
        .rsplit('/')
        .next()
        .unwrap_or_default()
        .to_owned();
    let version = request
        .headers()
        .get("x-api-version")
        .and_then(|value| value.to_str().ok())
        .unwrap_or("v1")
        .to_owned();
    request
        .extensions_mut()
        .insert(PolicyPath(format!("/api/rest/{api_name}/{version}/grpc")));
    request.extensions_mut().insert(DataPlaneProtocol::Grpc);
    rest_policy_then_proxy(State(state), request).await
}
