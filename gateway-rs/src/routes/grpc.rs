use axum::extract::{Request, State};
use axum::response::{IntoResponse, Response};

use crate::{
    error::GatewayError,
    routes::rest::{DataPlaneProtocol, PolicyPath, rest_policy_then_proxy},
    state::AppState,
};

pub async fn grpc_policy_then_execute(
    State(state): State<AppState>,
    mut request: Request,
) -> Result<Response, GatewayError> {
    let proto_discovery = request.method() == http::Method::GET
        && request.uri().query().is_some_and(|query| {
            query
                .split('&')
                .any(|part| part.eq_ignore_ascii_case("proto"))
        });
    if !matches!(
        request.method(),
        &http::Method::POST | &http::Method::OPTIONS
    ) && !proto_discovery
    {
        return Ok(http::StatusCode::METHOD_NOT_ALLOWED.into_response());
    }
    let path = request.uri().path();
    let subpath = path
        .strip_prefix("/api/grpc/")
        .or_else(|| path.strip_prefix("/grpc/"))
        .unwrap_or(path)
        .trim_matches('/');
    let api_name = subpath
        .split('/')
        .next()
        .unwrap_or_default()
        .to_owned();
    let version = request
        .headers()
        .get("x-api-version")
        .and_then(|value| value.to_str().ok())
        .unwrap_or("v1")
        .to_owned();
    tracing::info!(path = %path, subpath = %subpath, api_name = %api_name, version = %version, "grpc_policy_then_execute");
    request
        .extensions_mut()
        .insert(PolicyPath(format!("/api/rest/{api_name}/{version}/grpc")));
    request.extensions_mut().insert(DataPlaneProtocol::Grpc);
    rest_policy_then_proxy(State(state), request).await
}
