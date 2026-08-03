use axum::extract::{Request, State};
use axum::response::Response;

use crate::{
    error::GatewayError,
    routes::rest::{DataPlaneProtocol, PolicyPath, rest_policy_then_proxy},
    state::AppState,
};

pub async fn soap_policy_then_execute(
    State(state): State<AppState>,
    mut request: Request,
) -> Result<Response, GatewayError> {
    let suffix = request
        .uri()
        .path()
        .trim_start_matches("/api/soap/")
        .trim_start_matches('/')
        .to_owned();
    request
        .extensions_mut()
        .insert(PolicyPath(format!("/api/rest/{suffix}")));
    request.extensions_mut().insert(DataPlaneProtocol::Soap);
    rest_policy_then_proxy(State(state), request).await
}
