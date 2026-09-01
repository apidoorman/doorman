use std::env;

use axum::{
    extract::{OriginalUri, Request},
    middleware::Next,
    response::{IntoResponse, Response},
};
use http::{HeaderMap, HeaderValue, Method, StatusCode, header};

#[derive(Debug)]
struct PlatformCorsConfig {
    strict: bool,
    origins: Vec<String>,
    credentials: bool,
    methods: Vec<String>,
    headers: Vec<String>,
}

pub async fn platform_cors(request: Request, next: Next) -> Response {
    if env_bool("DISABLE_PLATFORM_CORS_ASGI", false) {
        return next.run(request).await;
    }

    let config = PlatformCorsConfig::from_env();
    let origin = request
        .headers()
        .get(header::ORIGIN)
        .and_then(|value| value.to_str().ok())
        .map(str::to_owned);

    if request.method() == Method::OPTIONS {
        let mut response = StatusCode::NO_CONTENT.into_response();
        apply_headers(response.headers_mut(), &config, origin.as_deref(), true);
        return response;
    }

    let mut response = next.run(request).await;
    apply_headers(response.headers_mut(), &config, origin.as_deref(), false);
    response
}

pub async fn force_platform_vary(request: Request, next: Next) -> Response {
    let is_platform = request
        .extensions()
        .get::<OriginalUri>()
        .map(|uri| uri.0.path().starts_with("/platform"))
        .unwrap_or_else(|| request.uri().path().starts_with("/platform"));
    let mut response = next.run(request).await;
    if is_platform {
        response
            .headers_mut()
            .insert(header::VARY, HeaderValue::from_static("Origin"));
    }
    response
}

impl PlatformCorsConfig {
    fn from_env() -> Self {
        Self::from_values(
            env::var("ALLOWED_ORIGINS").ok().as_deref(),
            env::var("ALLOW_CREDENTIALS").ok().as_deref(),
            env::var("CORS_STRICT").ok().as_deref(),
            env::var("ALLOW_METHODS").ok().as_deref(),
            env::var("ALLOW_HEADERS").ok().as_deref(),
        )
    }

    fn from_values(
        origins: Option<&str>,
        credentials: Option<&str>,
        strict: Option<&str>,
        methods: Option<&str>,
        headers: Option<&str>,
    ) -> Self {
        let origins = csv_value(origins, &["http://localhost:3000"]);
        let methods = csv_value(
            methods,
            &["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH", "HEAD"],
        );
        let default_headers = [
            "Accept",
            "Content-Type",
            "X-CSRF-Token",
            "Authorization",
            "X-Requested-With",
        ];
        let headers = match headers {
            Some(value) if value.trim() != "*" && !value.trim().is_empty() => value
                .split(',')
                .map(str::trim)
                .filter(|value| !value.is_empty())
                .map(str::to_owned)
                .collect(),
            _ => default_headers.map(str::to_owned).to_vec(),
        };
        Self {
            strict: bool_value(strict, true),
            origins,
            credentials: bool_value(credentials, false),
            methods,
            headers,
        }
    }

    fn origin_allowed(&self, origin: &str) -> bool {
        if self.origins.iter().any(|allowed| allowed == "*") {
            if self.strict && self.credentials {
                let origin = origin.to_ascii_lowercase();
                return origin.starts_with("http://localhost")
                    || origin.starts_with("https://localhost")
                    || origin.starts_with("http://127.0.0.1")
                    || origin.starts_with("https://127.0.0.1");
            }
            return true;
        }
        self.origins.iter().any(|allowed| allowed == origin)
    }
}

fn apply_headers(
    headers: &mut HeaderMap,
    config: &PlatformCorsConfig,
    origin: Option<&str>,
    preflight: bool,
) {
    if let Some(origin) = origin.filter(|origin| config.origin_allowed(origin)) {
        if let Ok(value) = HeaderValue::from_str(origin) {
            headers.insert(header::ACCESS_CONTROL_ALLOW_ORIGIN, value);
            headers.insert(header::VARY, HeaderValue::from_static("Origin"));
        }
    } else if preflight
        && origin.is_some()
        && config.strict
        && config.credentials
        && config.origins.iter().any(|allowed| allowed == "*")
    {
        headers.insert(
            header::ACCESS_CONTROL_ALLOW_ORIGIN,
            HeaderValue::from_static(""),
        );
    }
    if config.credentials {
        headers.insert(
            header::ACCESS_CONTROL_ALLOW_CREDENTIALS,
            HeaderValue::from_static("true"),
        );
    }
    if preflight {
        insert_joined(
            headers,
            header::ACCESS_CONTROL_ALLOW_METHODS,
            &config.methods,
        );
        insert_joined(
            headers,
            header::ACCESS_CONTROL_ALLOW_HEADERS,
            &config.headers,
        );
    }
}

fn insert_joined(headers: &mut HeaderMap, name: http::HeaderName, values: &[String]) {
    if let Ok(value) = HeaderValue::from_str(&values.join(", ")) {
        headers.insert(name, value);
    }
}

fn csv_value(value: Option<&str>, defaults: &[&str]) -> Vec<String> {
    value
        .map(|value| {
            value
                .split(',')
                .map(str::trim)
                .filter(|value| !value.is_empty())
                .map(str::to_owned)
                .collect::<Vec<_>>()
        })
        .filter(|values| !values.is_empty())
        .unwrap_or_else(|| defaults.iter().map(|value| (*value).to_owned()).collect())
}

fn env_bool(name: &str, default: bool) -> bool {
    bool_value(env::var(name).ok().as_deref(), default)
}

fn bool_value(value: Option<&str>, default: bool) -> bool {
    value
        .map(|value| {
            matches!(
                value.to_ascii_lowercase().as_str(),
                "1" | "true" | "yes" | "on"
            )
        })
        .unwrap_or(default)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn strict_wildcard_allows_only_local_origins_with_credentials() {
        let config = PlatformCorsConfig {
            strict: true,
            origins: vec!["*".to_owned()],
            credentials: true,
            methods: Vec::new(),
            headers: Vec::new(),
        };
        assert!(config.origin_allowed("https://localhost:3000"));
        assert!(config.origin_allowed("http://127.0.0.1:3000"));
        assert!(!config.origin_allowed("https://evil.example"));
    }

    #[test]
    fn platform_cors_wildcard_origin_with_credentials_non_strict_echoes_origin() {
        let config =
            PlatformCorsConfig::from_values(Some("*"), Some("true"), Some("false"), None, None);
        let mut headers = HeaderMap::new();
        apply_headers(&mut headers, &config, Some("http://evil.example"), true);

        assert_eq!(
            headers[header::ACCESS_CONTROL_ALLOW_ORIGIN],
            "http://evil.example"
        );
        assert_eq!(headers[header::ACCESS_CONTROL_ALLOW_CREDENTIALS], "true");
        assert_eq!(headers[header::VARY], "Origin");
    }

    #[test]
    fn platform_cors_wildcard_origin_with_credentials_strict_rejects_origin() {
        let config =
            PlatformCorsConfig::from_values(Some("*"), Some("true"), Some("true"), None, None);
        let mut headers = HeaderMap::new();
        apply_headers(&mut headers, &config, Some("http://evil.example"), true);

        assert_eq!(headers[header::ACCESS_CONTROL_ALLOW_ORIGIN], "");
    }

    #[test]
    fn platform_cors_empty_methods_use_python_defaults() {
        let config = PlatformCorsConfig::from_values(
            Some("http://localhost:3000"),
            None,
            None,
            Some(""),
            None,
        );
        assert_eq!(
            config.methods,
            ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH", "HEAD"]
        );
    }

    #[test]
    fn platform_cors_wildcard_headers_use_known_list() {
        let config = PlatformCorsConfig::from_values(
            Some("http://localhost:3000"),
            None,
            None,
            None,
            Some("*"),
        );
        assert_eq!(
            config.headers,
            [
                "Accept",
                "Content-Type",
                "X-CSRF-Token",
                "Authorization",
                "X-Requested-With",
            ]
        );
    }

    #[test]
    fn platform_cors_actual_response_sets_vary_origin() {
        let config =
            PlatformCorsConfig::from_values(Some("http://ok.example"), None, None, None, None);
        let mut headers = HeaderMap::new();
        apply_headers(&mut headers, &config, Some("http://ok.example"), false);

        assert_eq!(
            headers[header::ACCESS_CONTROL_ALLOW_ORIGIN],
            "http://ok.example"
        );
        assert_eq!(headers[header::VARY], "Origin");
    }

    #[test]
    fn platform_cors_replaces_instead_of_duplicating_allow_origin() {
        let config =
            PlatformCorsConfig::from_values(Some("http://ok.example"), None, None, None, None);
        let mut headers = HeaderMap::new();
        headers.append(
            header::ACCESS_CONTROL_ALLOW_ORIGIN,
            HeaderValue::from_static("http://stale.example"),
        );
        apply_headers(&mut headers, &config, Some("http://ok.example"), false);

        let values = headers
            .get_all(header::ACCESS_CONTROL_ALLOW_ORIGIN)
            .iter()
            .collect::<Vec<_>>();
        assert_eq!(values.len(), 1);
        assert_eq!(values[0], "http://ok.example");
    }
}
