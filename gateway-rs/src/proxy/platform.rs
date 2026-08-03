use std::net::SocketAddr;

use axum::{
    body::Body,
    extract::{ConnectInfo, OriginalUri, Request, State},
    response::Response,
};
use http::{HeaderMap, HeaderName, HeaderValue, Uri, header};

use crate::{error::GatewayError, state::AppState};

pub async fn proxy_to_python(
    State(state): State<AppState>,
    request: Request,
) -> Result<Response, GatewayError> {
    let original_uri = request
        .extensions()
        .get::<OriginalUri>()
        .map(|value| value.0.clone())
        .unwrap_or_else(|| request.uri().clone());
    let peer = request
        .extensions()
        .get::<ConnectInfo<SocketAddr>>()
        .map(|value| value.0);
    let target = target_url(&state.config.python_base_url, &original_uri);
    let (parts, body) = request.into_parts();
    let headers = forwarded_headers(parts.headers, peer);

    let upstream = state
        .proxy_client
        .request(parts.method, target)
        .headers(headers)
        .body(reqwest::Body::wrap_stream(body.into_data_stream()))
        .send()
        .await?;

    let status = upstream.status();
    let upstream_headers = upstream.headers().clone();
    let stream = upstream.bytes_stream();
    let mut response = Response::builder().status(status);
    let response_headers = response
        .headers_mut()
        .expect("response builder has headers");
    for (name, value) in &upstream_headers {
        if !is_hop_by_hop(name) {
            response_headers.append(name, value.clone());
        }
    }

    Ok(response.body(Body::from_stream(stream))?)
}

fn target_url(base_url: &str, uri: &Uri) -> String {
    let path_and_query = uri
        .path_and_query()
        .map(|value| value.as_str())
        .unwrap_or("/");
    format!("{}{}", base_url.trim_end_matches('/'), path_and_query)
}

fn forwarded_headers(mut headers: HeaderMap, peer: Option<SocketAddr>) -> HeaderMap {
    let original_host = headers.get(header::HOST).cloned();
    headers.remove(header::HOST);

    for name in HOP_BY_HOP_HEADERS {
        headers.remove(*name);
    }
    for name in SPOOFABLE_FORWARDING_HEADERS {
        headers.remove(*name);
    }

    if let Some(host) = original_host {
        headers.insert("x-forwarded-host", host);
    }
    if let Some(peer) = peer {
        set_forwarded_for(&mut headers, peer.ip().to_string());
    }
    headers
}

const HOP_BY_HOP_HEADERS: &[&str] = &[
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
];

const SPOOFABLE_FORWARDING_HEADERS: &[&str] = &[
    "x-forwarded-for",
    "x-real-ip",
    "cf-connecting-ip",
    "forwarded",
    "x-forwarded-host",
];

fn set_forwarded_for(headers: &mut HeaderMap, peer_ip: String) {
    if let Ok(value) = HeaderValue::from_str(&peer_ip) {
        headers.insert("x-forwarded-for", value);
    }
}

fn is_hop_by_hop(name: &HeaderName) -> bool {
    matches!(
        name.as_str().to_ascii_lowercase().as_str(),
        "connection"
            | "keep-alive"
            | "proxy-authenticate"
            | "proxy-authorization"
            | "te"
            | "trailer"
            | "transfer-encoding"
            | "upgrade"
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn preserves_path_and_query() {
        let uri: Uri = "/platform/users?page=2".parse().unwrap();
        assert_eq!(
            target_url("http://127.0.0.1:3002/", &uri),
            "http://127.0.0.1:3002/platform/users?page=2"
        );
    }

    #[test]
    fn replaces_spoofable_forwarding_headers() {
        let mut headers = HeaderMap::new();
        headers.insert(header::HOST, HeaderValue::from_static("public.example"));
        headers.insert(
            "x-forwarded-host",
            HeaderValue::from_static("spoofed.example"),
        );
        headers.insert("x-forwarded-for", HeaderValue::from_static("203.0.113.10"));
        headers.insert("x-real-ip", HeaderValue::from_static("203.0.113.11"));
        headers.insert("cf-connecting-ip", HeaderValue::from_static("203.0.113.12"));
        headers.insert("forwarded", HeaderValue::from_static("for=203.0.113.13"));

        let forwarded = forwarded_headers(
            headers,
            Some("198.51.100.20:12345".parse::<SocketAddr>().unwrap()),
        );

        assert!(!forwarded.contains_key(header::HOST));
        assert_eq!(forwarded.get("x-forwarded-host").unwrap(), "public.example");
        assert_eq!(forwarded.get("x-forwarded-for").unwrap(), "198.51.100.20");
        assert!(!forwarded.contains_key("x-real-ip"));
        assert!(!forwarded.contains_key("cf-connecting-ip"));
        assert!(!forwarded.contains_key("forwarded"));
    }
}
