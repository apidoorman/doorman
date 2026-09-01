use axum::{
    Json,
    extract::{OriginalUri, Request, State},
    response::{IntoResponse, Response},
};
use http::StatusCode;

use crate::{
    error::GatewayError,
    policy::PolicyErrorBody,
    routes::rest::{DataPlaneProtocol, PolicyPath, rest_policy_then_proxy},
    state::AppState,
};

pub async fn graphql_policy_then_execute(
    State(state): State<AppState>,
    mut request: Request,
) -> Result<Response, GatewayError> {
    if !matches!(
        request.method(),
        &http::Method::POST | &http::Method::OPTIONS
    ) {
        return Ok(StatusCode::METHOD_NOT_ALLOWED.into_response());
    }
    let version = request
        .headers()
        .get("x-api-version")
        .and_then(|value| value.to_str().ok())
        .map(str::to_owned)
        .or_else(|| (request.method() == http::Method::OPTIONS).then(|| "v1".to_owned()));
    let Some(version) = version else {
        return Ok((
            StatusCode::BAD_REQUEST,
            Json(PolicyErrorBody {
                error_code: "X-API-Version header is required".to_owned(),
                error_message: "X-API-Version header is required".to_owned(),
            }),
        )
            .into_response());
    };
    let original_path = request
        .extensions()
        .get::<OriginalUri>()
        .map(|uri| uri.0.path().to_owned())
        .unwrap_or_else(|| request.uri().path().to_owned());
    let api_name = original_path
        .trim_start_matches("/api/graphql/")
        .trim_matches('/')
        .to_owned();
    request.extensions_mut().insert(PolicyPath(format!(
        "/api/rest/{api_name}/{version}/graphql"
    )));
    request.extensions_mut().insert(DataPlaneProtocol::Graphql);
    rest_policy_then_proxy(State(state), request).await
}
