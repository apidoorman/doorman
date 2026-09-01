use std::{
    env,
    net::{IpAddr, SocketAddr},
};

use axum::{
    body::Body,
    extract::{ConnectInfo, Request, State},
    response::{IntoResponse, Response},
};
use http::{StatusCode, header};

use crate::{
    middleware::client_ip::effective_client_ip, observability::metrics::render, state::AppState,
};

const CONTENT_TYPE: &str = "text/plain; version=0.0.4; charset=utf-8";

pub async fn metrics(State(state): State<AppState>, request: Request) -> Response {
    if !env_flag("PROMETHEUS_ENABLED", true) {
        return metric_response(StatusCode::SERVICE_UNAVAILABLE, "prometheus_disabled 1\n");
    }
    if !metrics_allowed(&request) {
        return metric_response(StatusCode::FORBIDDEN, "prometheus_forbidden 1\n");
    }
    metric_response(StatusCode::OK, render(&state.runtime))
}

fn metrics_allowed(request: &Request) -> bool {
    if env_flag("PROMETHEUS_PUBLIC", false) {
        return true;
    }
    if let Some(required) =
        env_non_empty("PROMETHEUS_BEARER_TOKEN").or_else(|| env_non_empty("PROMETHEUS_TOKEN"))
    {
        if extract_token(request) != Some(required.as_str()) {
            return false;
        }
    }
    let direct_ip = request
        .extensions()
        .get::<ConnectInfo<SocketAddr>>()
        .map(|peer| peer.0.ip());
    let client_ip = effective_client_ip(
        request.headers(),
        direct_ip,
        env_flag("PROMETHEUS_TRUST_XFF", false),
    );
    let allowlist = env_non_empty("PROMETHEUS_ALLOWLIST")
        .or_else(|| env_non_empty("PROMETHEUS_IP_ALLOWLIST"))
        .map(|raw| {
            raw.split(',')
                .map(str::trim)
                .filter(|item| !item.is_empty())
                .map(str::to_owned)
                .collect::<Vec<_>>()
        })
        .unwrap_or_default();
    if allowlist.is_empty() {
        return client_ip.is_some_and(|ip| ip.is_loopback());
    }
    client_ip.is_some_and(|ip| allowlist.iter().any(|rule| ip_in_rule(ip, rule)))
}

fn extract_token(request: &Request) -> Option<&str> {
    request
        .headers()
        .get(header::AUTHORIZATION)
        .and_then(|value| value.to_str().ok())
        .and_then(|value| value.trim().strip_prefix("Bearer "))
        .map(str::trim)
        .filter(|value| !value.is_empty())
        .or_else(|| {
            request
                .headers()
                .get("x-prometheus-token")
                .and_then(|value| value.to_str().ok())
                .map(str::trim)
                .filter(|value| !value.is_empty())
        })
}

fn ip_in_rule(ip: IpAddr, rule: &str) -> bool {
    let Some((network, prefix)) = rule.split_once('/') else {
        return rule.parse::<IpAddr>().ok() == Some(ip);
    };
    let Ok(network) = network.parse::<IpAddr>() else {
        return false;
    };
    let Ok(prefix) = prefix.parse::<u32>() else {
        return false;
    };
    match (ip, network) {
        (IpAddr::V4(ip), IpAddr::V4(network)) if prefix <= 32 => {
            let mask = if prefix == 0 {
                0
            } else {
                u32::MAX << (32 - prefix)
            };
            u32::from(ip) & mask == u32::from(network) & mask
        }
        (IpAddr::V6(ip), IpAddr::V6(network)) if prefix <= 128 => {
            let mask = if prefix == 0 {
                0
            } else {
                u128::MAX << (128 - prefix)
            };
            u128::from(ip) & mask == u128::from(network) & mask
        }
        _ => false,
    }
}

fn metric_response(status: StatusCode, body: impl Into<Body>) -> Response {
    (status, [(header::CONTENT_TYPE, CONTENT_TYPE)], body.into()).into_response()
}

fn env_flag(name: &str, default: bool) -> bool {
    env::var(name)
        .ok()
        .map(|value| {
            matches!(
                value.trim().to_ascii_lowercase().as_str(),
                "1" | "true" | "yes" | "on"
            )
        })
        .unwrap_or(default)
}

fn env_non_empty(name: &str) -> Option<String> {
    env::var(name)
        .ok()
        .map(|value| value.trim().to_owned())
        .filter(|value| !value.is_empty())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn matches_exact_and_cidr_ip_rules() {
        assert!(ip_in_rule("10.1.2.3".parse().unwrap(), "10.0.0.0/8"));
        assert!(!ip_in_rule("203.0.113.1".parse().unwrap(), "10.0.0.0/8"));
        assert!(ip_in_rule("::1".parse().unwrap(), "::1/128"));
    }
}
