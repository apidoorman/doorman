use std::env;

use axum::{
    extract::Request,
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

impl PlatformCorsConfig {
    fn from_env() -> Self {
        let origins = csv_env("ALLOWED_ORIGINS", &["*"]);
        let methods = csv_env(
            "ALLOW_METHODS",
            &["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH", "HEAD"],
        );
        let default_headers = [
            "Accept",
            "Content-Type",
            "X-CSRF-Token",
            "Authorization",
            "X-Requested-With",
        ];
        let headers = match env::var("ALLOW_HEADERS") {
            Ok(value) if value.trim() != "*" && !value.trim().is_empty() => value
                .split(',')
                .map(str::trim)
                .filter(|value| !value.is_empty())
                .map(str::to_owned)
                .collect(),
            _ => default_headers.map(str::to_owned).to_vec(),
        };
        Self {
            strict: env_bool("CORS_STRICT", false),
            origins,
            credentials: env_bool("ALLOW_CREDENTIALS", true),
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

fn csv_env(name: &str, defaults: &[&str]) -> Vec<String> {
    env::var(name)
        .ok()
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
    env::var(name)
        .ok()
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
}
