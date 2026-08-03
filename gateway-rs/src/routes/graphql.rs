use axum::{
    Json,
    extract::{Request, State},
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
    let enforce = state.config.mode.enforces_policies();
    if enforce && request.method() == http::Method::OPTIONS {
        return Ok(StatusCode::NO_CONTENT.into_response());
    }
    if enforce && request.method() != http::Method::POST {
        return Ok(StatusCode::METHOD_NOT_ALLOWED.into_response());
    }
    let version = request
        .headers()
        .get("x-api-version")
        .and_then(|value| value.to_str().ok())
        .map(str::to_owned)
        .or_else(|| (!enforce).then(|| "v1".to_owned()));
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
    let api_name = request
        .uri()
        .path()
        .trim_start_matches("/api/graphql/")
        .trim_matches('/')
        .to_owned();
    request.extensions_mut().insert(PolicyPath(format!(
        "/api/rest/{api_name}/{version}/graphql"
    )));
    request.extensions_mut().insert(DataPlaneProtocol::Graphql);
    rest_policy_then_proxy(State(state), request).await
}
