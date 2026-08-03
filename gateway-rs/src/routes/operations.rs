use axum::{
    Json,
    extract::{Request, State},
    http::{HeaderMap, Method, StatusCode, header},
    response::{IntoResponse, Response},
};
use serde::Serialize;

use crate::{error::GatewayError, proxy::platform::proxy_to_python, state::AppState};

#[derive(Serialize)]
pub struct HealthResponse {
    status: &'static str,
}

#[derive(Serialize)]
struct ErrorResponse {
    error_code: &'static str,
    error_message: &'static str,
}

pub async fn health(
    State(state): State<AppState>,
    request: Request,
) -> Result<Response, GatewayError> {
    if request.method() == Method::GET {
        return Ok(Json(HealthResponse { status: "online" }).into_response());
    }

    proxy_to_python(State(state), request).await
}

pub async fn status(
    State(state): State<AppState>,
    request: Request,
) -> Result<Response, GatewayError> {
    if request.method() == Method::GET && !has_platform_auth(request.headers()) {
        return Ok((
            StatusCode::UNAUTHORIZED,
            Json(ErrorResponse {
                error_code: "GTW401",
                error_message: "Unauthorized",
            }),
        )
            .into_response());
    }

    proxy_to_python(State(state), request).await
}

pub async fn caches(
    State(state): State<AppState>,
    request: Request,
) -> Result<Response, GatewayError> {
    if request.method() == Method::OPTIONS {
        return Ok(StatusCode::NO_CONTENT.into_response());
    }

    if matches!(
        request.method(),
        &Method::POST | &Method::PUT | &Method::PATCH | &Method::DELETE
    ) {
        if let Some(storage) = &state.storage {
            storage.invalidate_policy_cache().await;
        }
    }

    proxy_to_python(State(state), request).await
}

fn has_platform_auth(headers: &HeaderMap) -> bool {
    headers
        .get(header::AUTHORIZATION)
        .and_then(|value| value.to_str().ok())
        .is_some_and(|value| !value.trim().is_empty())
        || headers
            .get_all(header::COOKIE)
            .iter()
            .filter_map(|value| value.to_str().ok())
            .any(has_access_token_cookie)
}

fn has_access_token_cookie(cookies: &str) -> bool {
    cookies
        .split(';')
        .map(str::trim)
        .any(|cookie| cookie.starts_with("access_token_cookie="))
}

#[cfg(test)]
mod tests {
    use super::*;
    use axum::http::HeaderValue;

    #[test]
    fn detects_platform_auth_header_or_cookie() {
        let mut headers = HeaderMap::new();
        headers.insert(
            header::AUTHORIZATION,
            HeaderValue::from_static("Bearer token"),
        );
        assert!(has_platform_auth(&headers));

        let mut headers = HeaderMap::new();
        headers.insert(
            header::COOKIE,
            HeaderValue::from_static("theme=dark; access_token_cookie=token"),
        );
        assert!(has_platform_auth(&headers));
    }

    #[test]
    fn ignores_missing_or_blank_platform_auth() {
        assert!(!has_platform_auth(&HeaderMap::new()));

        let mut headers = HeaderMap::new();
        headers.insert(header::AUTHORIZATION, HeaderValue::from_static("   "));
        headers.insert(header::COOKIE, HeaderValue::from_static("theme=dark"));
        assert!(!has_platform_auth(&headers));
    }
}
