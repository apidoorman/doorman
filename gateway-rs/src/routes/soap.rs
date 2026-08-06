use axum::extract::{OriginalUri, Request, State};
use axum::response::{IntoResponse, Response};

use crate::{
    error::GatewayError,
    routes::rest::{DataPlaneProtocol, PolicyPath, rest_policy_then_proxy},
    state::AppState,
};

pub async fn soap_policy_then_execute(
    State(state): State<AppState>,
    mut request: Request,
) -> Result<Response, GatewayError> {
    if !matches!(
        request.method(),
        &http::Method::GET | &http::Method::POST | &http::Method::OPTIONS
    ) {
        return Ok(http::StatusCode::METHOD_NOT_ALLOWED.into_response());
    }

    let original_path = request
        .extensions()
        .get::<OriginalUri>()
        .map(|uri| uri.0.path().to_owned())
        .unwrap_or_else(|| request.uri().path().to_owned());
    let suffix = original_path
        .trim_start_matches("/api/soap/")
        .trim_start_matches('/')
        .to_owned();
    request
        .extensions_mut()
        .insert(PolicyPath(format!("/api/rest/{suffix}")));
    request.extensions_mut().insert(DataPlaneProtocol::Soap);
    rest_policy_then_proxy(State(state), request).await
}
