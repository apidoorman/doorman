use http::HeaderMap;

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct ResolvedApi {
    pub name: String,
    pub version: String,
    pub api_id: String,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct RestRouteParts {
    pub api_name: String,
    pub api_version: String,
    pub endpoint_uri: String,
    pub api_lookup_key: String,
}

pub fn resolve_rest_path(path: &str, headers: &HeaderMap) -> Option<RestRouteParts> {
    let rest_path = path.strip_prefix("/api/rest/")?;
    let parts: Vec<&str> = rest_path
        .split('/')
        .filter(|part| !part.is_empty())
        .collect();

    if parts.len() >= 2 && is_path_version(parts[1]) {
        return Some(route_parts(parts[0], parts[1], &parts[2..]));
    }

    let version = headers
        .get("x-api-version")
        .and_then(|value| value.to_str().ok())
        .filter(|value| !value.trim().is_empty())?;
    let api_name = parts.first()?;
    Some(route_parts(api_name, version, &parts[1..]))
}

fn route_parts(api_name: &str, api_version: &str, endpoint_parts: &[&str]) -> RestRouteParts {
    let endpoint_uri = if endpoint_parts.is_empty() {
        "/".to_owned()
    } else {
        format!("/{}", endpoint_parts.join("/"))
    };
    RestRouteParts {
        api_name: api_name.to_owned(),
        api_version: api_version.to_owned(),
        endpoint_uri,
        api_lookup_key: format!("/{api_name}/{api_version}"),
    }
}

fn is_path_version(value: &str) -> bool {
    value
        .strip_prefix('v')
        .is_some_and(|suffix| !suffix.is_empty() && suffix.chars().all(|ch| ch.is_ascii_digit()))
}

pub fn endpoint_pattern_matches(pattern: &str, actual: &str) -> bool {
    let pattern = pattern.trim_matches('/');
    let actual = actual.trim_matches('/');
    if pattern.is_empty() || actual.is_empty() {
        return pattern == actual;
    }

    let pattern_parts: Vec<&str> = pattern.split('/').collect();
    let actual_parts: Vec<&str> = actual.split('/').collect();
    pattern_parts.len() == actual_parts.len()
        && pattern_parts
            .iter()
            .zip(actual_parts.iter())
            .all(|(left, right)| (left.starts_with('{') && left.ends_with('}')) || left == right)
}

#[cfg(test)]
mod tests {
    use super::*;
    use http::HeaderValue;

    #[test]
    fn resolves_path_version_rest_routes() {
        let route = resolve_rest_path("/api/rest/demo/v1/items/7", &HeaderMap::new()).unwrap();
        assert_eq!(route.api_name, "demo");
        assert_eq!(route.api_version, "v1");
        assert_eq!(route.endpoint_uri, "/items/7");
        assert_eq!(route.api_lookup_key, "/demo/v1");
    }

    #[test]
    fn resolves_header_version_rest_routes() {
        let mut headers = HeaderMap::new();
        headers.insert("x-api-version", HeaderValue::from_static("v2"));
        let route = resolve_rest_path("/api/rest/demo/items", &headers).unwrap();
        assert_eq!(route.api_name, "demo");
        assert_eq!(route.api_version, "v2");
        assert_eq!(route.endpoint_uri, "/items");
    }

    #[test]
    fn matches_python_path_parameters() {
        assert!(endpoint_pattern_matches("/items/{id}", "/items/7"));
        assert!(!endpoint_pattern_matches("/items/{id}", "/items/7/extra"));
    }
}
