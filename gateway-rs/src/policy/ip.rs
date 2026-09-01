use std::net::{IpAddr, Ipv6Addr};

use http::{HeaderMap, StatusCode};
use serde_json::Value;

use super::{PolicyFailure, PolicyStage};
use crate::storage::models::{bool_field, string_list_field};

pub fn enforce_api_ip_policy(
    api: &Value,
    settings: Option<&Value>,
    headers: &HeaderMap,
    direct_ip: Option<IpAddr>,
    configured_trust_xff: bool,
    local_host_ip_bypass: bool,
) -> Result<(), PolicyFailure> {
    let trust_xff = bool_field(api, "api_trust_x_forwarded_for")
        .or_else(|| settings.and_then(|value| bool_field(value, "trust_x_forwarded_for")))
        .unwrap_or(configured_trust_xff);
    let client_ip = effective_client_ip_for_settings(settings, headers, direct_ip, trust_xff);

    let allow_localhost_bypass = settings
        .and_then(|value| bool_field(value, "allow_localhost_bypass"))
        .unwrap_or(local_host_ip_bypass);
    if allow_localhost_bypass
        && !has_forwarding_headers(headers)
        && direct_ip.is_some_and(is_loopback)
    {
        return Ok(());
    }

    let Some(client_ip) = client_ip else {
        return Ok(());
    };
    let blacklist = string_list_field(api, "api_ip_blacklist");
    if ip_in_list(client_ip, &blacklist) {
        return Err(PolicyFailure::new(
            PolicyStage::Ip,
            StatusCode::FORBIDDEN,
            "API011",
            "IP restricted",
        ));
    }

    let mode = api
        .get("api_ip_mode")
        .and_then(Value::as_str)
        .unwrap_or("allow_all")
        .trim()
        .to_ascii_lowercase();
    if mode == "whitelist" {
        let whitelist = string_list_field(api, "api_ip_whitelist");
        if whitelist.is_empty() || !ip_in_list(client_ip, &whitelist) {
            return Err(PolicyFailure::new(
                PolicyStage::Ip,
                StatusCode::FORBIDDEN,
                "API010",
                "IP restricted",
            ));
        }
    }

    Ok(())
}

pub fn effective_client_ip_for_settings(
    settings: Option<&Value>,
    headers: &HeaderMap,
    direct_ip: Option<IpAddr>,
    trust_xff: bool,
) -> Option<IpAddr> {
    let trusted_proxies = settings
        .map(|value| string_list_field(value, "xff_trusted_proxies"))
        .unwrap_or_default();
    let trust_forwarded_headers = trust_xff
        && (trusted_proxies.is_empty()
            || direct_ip.is_some_and(|ip| ip_in_list(ip, &trusted_proxies)));
    effective_client_ip(headers, direct_ip, trust_forwarded_headers)
}

fn has_forwarding_headers(headers: &HeaderMap) -> bool {
    [
        "x-forwarded-for",
        "x-real-ip",
        "cf-connecting-ip",
        "forwarded",
    ]
    .iter()
    .any(|name| headers.contains_key(*name))
}

pub fn effective_client_ip(
    headers: &HeaderMap,
    direct_ip: Option<IpAddr>,
    trust_xff: bool,
) -> Option<IpAddr> {
    if trust_xff {
        for name in ["x-forwarded-for", "x-real-ip", "cf-connecting-ip"] {
            if let Some(ip) = headers
                .get(name)
                .and_then(|value| value.to_str().ok())
                .and_then(|value| value.split(',').next())
                .map(str::trim)
                .and_then(|value| value.parse::<IpAddr>().ok())
            {
                return Some(ip);
            }
        }
    }
    direct_ip
}

fn is_loopback(ip: IpAddr) -> bool {
    ip.is_loopback()
}

fn ip_in_list(ip: IpAddr, patterns: &[String]) -> bool {
    patterns.iter().any(|pattern| ip_matches(ip, pattern))
}

fn ip_matches(ip: IpAddr, pattern: &str) -> bool {
    let pattern = pattern.trim();
    if pattern.is_empty() {
        return false;
    }
    if let Some((network, prefix)) = pattern.split_once('/') {
        let Ok(prefix) = prefix.parse::<u8>() else {
            return false;
        };
        return cidr_contains(ip, network, prefix);
    }
    pattern
        .parse::<IpAddr>()
        .is_ok_and(|candidate| candidate == ip)
}

fn cidr_contains(ip: IpAddr, network: &str, prefix: u8) -> bool {
    match (ip, network.parse::<IpAddr>()) {
        (IpAddr::V4(ip), Ok(IpAddr::V4(network))) if prefix <= 32 => {
            let mask = if prefix == 0 {
                0
            } else {
                u32::MAX << (32 - prefix)
            };
            u32::from(ip) & mask == u32::from(network) & mask
        }
        (IpAddr::V6(ip), Ok(IpAddr::V6(network))) if prefix <= 128 => {
            let mask = if prefix == 0 {
                0
            } else {
                u128::MAX << (128 - prefix)
            };
            ipv6_to_u128(ip) & mask == ipv6_to_u128(network) & mask
        }
        _ => false,
    }
}

fn ipv6_to_u128(ip: Ipv6Addr) -> u128 {
    u128::from_be_bytes(ip.octets())
}

#[cfg(test)]
mod tests {
    use super::*;
    use http::HeaderValue;
    use serde_json::json;
    use std::net::Ipv4Addr;

    #[test]
    fn localhost_host_header_cannot_bypass_an_ip_allowlist() {
        let mut headers = HeaderMap::new();
        headers.insert("host", HeaderValue::from_static("localhost"));
        let api = json!({"api_ip_mode": "whitelist", "api_ip_whitelist": ["127.0.0.1"]});
        assert!(
            enforce_api_ip_policy(
                &api,
                None,
                &headers,
                Some("203.0.113.5".parse().unwrap()),
                false,
                true,
            )
            .is_err()
        );
    }

    #[test]
    fn trusts_forwarding_headers_when_enabled() {
        let mut headers = HeaderMap::new();
        headers.insert(
            "x-forwarded-for",
            HeaderValue::from_static("203.0.113.5, 10.0.0.1"),
        );
        assert_eq!(
            effective_client_ip(&headers, Some(IpAddr::V4(Ipv4Addr::LOCALHOST)), true),
            Some("203.0.113.5".parse().unwrap())
        );
    }

    #[test]
    fn enforces_blacklist_and_whitelist() {
        let api = json!({
            "api_ip_mode": "whitelist",
            "api_ip_whitelist": ["203.0.113.0/24"],
            "api_ip_blacklist": ["203.0.113.99"],
        });
        assert!(
            enforce_api_ip_policy(
                &api,
                None,
                &HeaderMap::new(),
                Some("203.0.113.5".parse().unwrap()),
                false,
                false,
            )
            .is_ok()
        );
        assert!(
            enforce_api_ip_policy(
                &api,
                None,
                &HeaderMap::new(),
                Some("203.0.113.99".parse().unwrap()),
                false,
                false,
            )
            .is_err()
        );
    }

    fn enforce_for(api: &Value, client_ip: &str) -> Result<(), PolicyFailure> {
        enforce_api_ip_policy(
            api,
            None,
            &HeaderMap::new(),
            Some(client_ip.parse().unwrap()),
            false,
            false,
        )
    }

    #[test]
    fn python_ip_policy_allows_exact_ip() {
        let api = json!({"api_ip_mode": "whitelist", "api_ip_whitelist": ["127.0.0.1"]});
        assert!(enforce_for(&api, "127.0.0.1").is_ok());
    }

    #[test]
    fn python_ip_policy_denies_exact_ip() {
        let api = json!({"api_ip_mode": "allow_all", "api_ip_blacklist": ["127.0.0.1"]});
        let failure = enforce_for(&api, "127.0.0.1").unwrap_err();
        assert_eq!(failure.status, StatusCode::FORBIDDEN);
        assert_eq!(failure.error_code, "API011");
    }

    #[test]
    fn python_ip_policy_allows_cidr() {
        let api = json!({"api_ip_mode": "whitelist", "api_ip_whitelist": ["127.0.0.0/24"]});
        assert!(enforce_for(&api, "127.0.0.1").is_ok());
    }

    #[test]
    fn python_ip_policy_denies_cidr() {
        let api = json!({"api_ip_mode": "allow_all", "api_ip_blacklist": ["127.0.0.0/24"]});
        let failure = enforce_for(&api, "127.0.0.1").unwrap_err();
        assert_eq!(failure.status, StatusCode::FORBIDDEN);
        assert_eq!(failure.error_code, "API011");
    }

    #[test]
    fn python_ip_policy_denylist_precedes_allowlist() {
        let api = json!({
            "api_ip_mode": "whitelist",
            "api_ip_whitelist": ["127.0.0.1"],
            "api_ip_blacklist": ["127.0.0.1"],
        });
        let failure = enforce_for(&api, "127.0.0.1").unwrap_err();
        assert_eq!(failure.status, StatusCode::FORBIDDEN);
        assert_eq!(failure.error_code, "API011");
    }

    #[test]
    fn python_ip_policy_returns_whitelist_error_before_upstream() {
        let api = json!({"api_ip_mode": "whitelist", "api_ip_whitelist": ["203.0.113.5"]});
        let failure = enforce_for(&api, "127.0.0.1").unwrap_err();
        assert_eq!(failure.stage, PolicyStage::Ip);
        assert_eq!(failure.status, StatusCode::FORBIDDEN);
        assert_eq!(failure.error_code, "API010");
    }

    #[test]
    fn localhost_host_header_does_not_bypass_behind_container_nat() {
        let api = json!({
            "api_ip_mode": "whitelist",
            "api_ip_whitelist": [],
        });
        let mut headers = HeaderMap::new();
        headers.insert("host", HeaderValue::from_static("localhost:3001"));

        assert!(
            enforce_api_ip_policy(
                &api,
                None,
                &headers,
                Some("172.18.0.1".parse().unwrap()),
                false,
                true,
            )
            .is_err()
        );
    }
}
