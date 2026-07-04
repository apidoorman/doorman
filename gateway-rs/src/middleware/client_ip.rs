use std::net::IpAddr;

use http::HeaderMap;

pub fn effective_client_ip(
    headers: &HeaderMap,
    direct_ip: Option<IpAddr>,
    trust_forwarded_for: bool,
) -> Option<IpAddr> {
    if trust_forwarded_for {
        if let Some(ip) = headers
            .get("x-forwarded-for")
            .and_then(|value| value.to_str().ok())
            .and_then(|value| value.split(',').next())
            .and_then(|value| value.trim().parse().ok())
        {
            return Some(ip);
        }
    }
    direct_ip
}

#[cfg(test)]
mod tests {
    use super::*;
    use http::HeaderValue;

    #[test]
    fn uses_first_forwarded_address_only_when_trusted() {
        let mut headers = HeaderMap::new();
        headers.insert(
            "x-forwarded-for",
            HeaderValue::from_static("203.0.113.5, 198.51.100.4"),
        );
        let direct = Some("127.0.0.1".parse().unwrap());
        assert_eq!(
            effective_client_ip(&headers, direct, true),
            Some("203.0.113.5".parse().unwrap())
        );
        assert_eq!(effective_client_ip(&headers, direct, false), direct);
    }
}
