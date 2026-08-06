use axum::response::{IntoResponse, Response};
use http::{HeaderMap, HeaderName, HeaderValue, StatusCode, header};

use crate::policy::PolicyDecision;

#[derive(Clone, Debug, Default, Eq, PartialEq)]
pub struct ApiCorsConfig {
    pub allow_origins: Option<Vec<String>>,
    pub allow_methods: Option<Vec<String>>,
    pub allow_headers: Option<Vec<String>>,
    pub allow_credentials: bool,
    pub expose_headers: Option<Vec<String>>,
}

impl From<&PolicyDecision> for ApiCorsConfig {
    fn from(decision: &PolicyDecision) -> Self {
        Self {
            allow_origins: decision.cors_allow_origins.clone(),
            allow_methods: decision.cors_allow_methods.clone(),
            allow_headers: decision.cors_allow_headers.clone(),
            allow_credentials: decision.cors_allow_credentials,
            expose_headers: Some(decision.cors_expose_headers.clone()),
        }
    }
}

pub fn preflight_response(decision: &PolicyDecision, request_headers: &HeaderMap) -> Response {
    let mut response = StatusCode::NO_CONTENT.into_response();
    apply(
        response.headers_mut(),
        &ApiCorsConfig::from(decision),
        request_headers
            .get(header::ORIGIN)
            .and_then(|value| value.to_str().ok()),
        request_headers
            .get(header::ACCESS_CONTROL_REQUEST_METHOD)
            .and_then(|value| value.to_str().ok()),
        request_headers
            .get(header::ACCESS_CONTROL_REQUEST_HEADERS)
            .and_then(|value| value.to_str().ok()),
    );
    response
}

pub fn apply_actual_response(
    response: &mut Response,
    decision: &PolicyDecision,
    origin: Option<&str>,
) {
    apply(
        response.headers_mut(),
        &ApiCorsConfig::from(decision),
        origin,
        None,
        None,
    );
}

fn apply(
    target: &mut HeaderMap,
    config: &ApiCorsConfig,
    origin: Option<&str>,
    requested_method: Option<&str>,
    requested_headers: Option<&str>,
) {
    let origin = origin.unwrap_or_default().trim();
    let allow_origins = config
        .allow_origins
        .clone()
        .unwrap_or_else(|| vec!["*".to_owned()]);
    let mut allow_methods = config.allow_methods.clone().unwrap_or_else(|| {
        ["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"]
            .map(str::to_owned)
            .to_vec()
    });
    for method in &mut allow_methods {
        *method = method.trim().to_ascii_uppercase();
    }
    if !allow_methods.iter().any(|method| method == "OPTIONS") {
        allow_methods.push("OPTIONS".to_owned());
    }
    let allow_headers = config
        .allow_headers
        .clone()
        .unwrap_or_else(|| vec!["*".to_owned()]);
    let origin_allowed = origin_allowed(origin, &allow_origins);
    let method_allowed = requested_method.is_none_or(|method| {
        allow_methods
            .iter()
            .any(|allowed| allowed.eq_ignore_ascii_case(method.trim()))
    });
    let headers_allowed = requested_headers.is_none_or(|headers| {
        allow_headers.iter().any(|header| header == "*")
            || headers
                .split(',')
                .map(str::trim)
                .filter(|header| !header.is_empty())
                .all(|requested| {
                    allow_headers
                        .iter()
                        .any(|allowed| allowed.eq_ignore_ascii_case(requested))
                })
    });
    if origin_allowed && method_allowed && headers_allowed && !origin.is_empty() {
        insert(target, header::ACCESS_CONTROL_ALLOW_ORIGIN, origin);
        append_vary_origin(target);
    }
    if config.allow_credentials {
        insert(target, header::ACCESS_CONTROL_ALLOW_CREDENTIALS, "true");
    }
    if requested_method.is_some() {
        insert(
            target,
            header::ACCESS_CONTROL_ALLOW_METHODS,
            &allow_methods.join(", "),
        );
    }
    if requested_headers.is_some() {
        insert(
            target,
            header::ACCESS_CONTROL_ALLOW_HEADERS,
            &allow_headers.join(", "),
        );
    }
    if let Some(expose) = config
        .expose_headers
        .as_ref()
        .filter(|items| !items.is_empty())
    {
        insert(
            target,
            header::ACCESS_CONTROL_EXPOSE_HEADERS,
            &expose.join(", "),
        );
    }
}

fn origin_allowed(origin: &str, allowed: &[String]) -> bool {
    allowed.iter().any(|entry| {
        let entry = entry.trim();
        if entry == "*" || entry == origin {
            return true;
        }
        let Some((scheme, suffix)) = entry.split_once("://*.") else {
            return false;
        };
        let Some((origin_scheme, origin_host)) = origin.split_once("://") else {
            return false;
        };
        origin_scheme == scheme
            && origin_host.ends_with(&format!(".{suffix}"))
            && origin_host.len() > suffix.len() + 1
    })
}

fn insert(headers: &mut HeaderMap, name: HeaderName, value: &str) {
    if let Ok(value) = HeaderValue::from_str(value) {
        headers.insert(name, value);
    }
}

fn append_vary_origin(headers: &mut HeaderMap) {
    let already_varies = headers
        .get_all(header::VARY)
        .iter()
        .filter_map(|value| value.to_str().ok())
        .flat_map(|value| value.split(','))
        .any(|value| value.trim().eq_ignore_ascii_case("origin"));
    if !already_varies {
        headers.append(header::VARY, HeaderValue::from_static("Origin"));
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn supports_wildcard_subdomains_and_case_insensitive_headers() {
        assert!(origin_allowed(
            "https://api.example.com",
            &["https://*.example.com".to_owned()]
        ));
        assert!(!origin_allowed(
            "https://example.com",
            &["https://*.example.com".to_owned()]
        ));
    }
}
