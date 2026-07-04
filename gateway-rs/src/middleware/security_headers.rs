use axum::{
    extract::{Request, State},
    middleware::Next,
    response::Response,
};
use http::{HeaderName, HeaderValue};

use crate::state::AppState;

pub async fn security_headers(
    State(state): State<AppState>,
    request: Request,
    next: Next,
) -> Response {
    let mut response = next.run(request).await;
    let headers = response.headers_mut();

    insert_default(headers, "x-content-type-options", "nosniff");
    insert_default(headers, "x-frame-options", "DENY");
    insert_default(headers, "referrer-policy", "no-referrer");
    insert_default(
        headers,
        "permissions-policy",
        "geolocation=(), microphone=(), camera=()",
    );
    let csp = state.config.content_security_policy.as_deref().unwrap_or(
        "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'; img-src 'self' data:; connect-src 'self';",
    );
    insert_value_default(headers, "content-security-policy", csp);
    if state.config.https_only {
        insert_default(
            headers,
            "strict-transport-security",
            "max-age=15552000; includeSubDomains; preload",
        );
    }
    response
}

fn insert_default(headers: &mut http::HeaderMap, name: &'static str, value: &'static str) {
    insert_value_default(headers, name, value);
}

fn insert_value_default(headers: &mut http::HeaderMap, name: &'static str, value: &str) {
    let name = HeaderName::from_static(name);
    if !headers.contains_key(&name) {
        if let Ok(value) = HeaderValue::from_str(value) {
            headers.insert(name, value);
        }
    }
}
