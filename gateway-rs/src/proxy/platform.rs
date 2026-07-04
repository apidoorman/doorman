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
    if let Some(host) = headers.get(header::HOST).cloned() {
        headers.entry("x-forwarded-host").or_insert(host);
    }
    headers.remove(header::HOST);
    for name in [
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailer",
        "transfer-encoding",
        "upgrade",
    ] {
        headers.remove(name);
    }
    if let Some(peer) = peer {
        append_forwarded_for(&mut headers, peer.ip().to_string());
    }
    headers
}

fn append_forwarded_for(headers: &mut HeaderMap, peer_ip: String) {
    let value = match headers
        .get("x-forwarded-for")
        .and_then(|value| value.to_str().ok())
    {
        Some(existing) if !existing.trim().is_empty() => format!("{existing}, {peer_ip}"),
        _ => peer_ip,
    };
    if let Ok(value) = HeaderValue::from_str(&value) {
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
    fn appends_peer_to_forwarded_for_chain() {
        let mut headers = HeaderMap::new();
        headers.insert("x-forwarded-for", HeaderValue::from_static("203.0.113.10"));
        append_forwarded_for(&mut headers, "198.51.100.20".to_owned());
        assert_eq!(
            headers.get("x-forwarded-for").unwrap(),
            "203.0.113.10, 198.51.100.20"
        );
    }
}
