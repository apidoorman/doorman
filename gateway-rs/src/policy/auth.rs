use http::{HeaderMap, StatusCode, header};
use jsonwebtoken::{Algorithm, DecodingKey, Validation, decode, decode_header};
use serde::Deserialize;
use serde_json::Value;

use super::{PolicyFailure, PolicyStage};
use crate::config::SharedStorageConfig;

#[derive(Clone, Debug, Deserialize, Eq, PartialEq)]
pub struct AuthClaims {
    pub sub: Option<String>,
    pub jti: Option<String>,
    pub role: Option<String>,
    pub exp: Option<usize>,
}

#[derive(Clone, Debug, Deserialize)]
struct JwtKeyConfig {
    kid: Option<String>,
    algorithm: Option<String>,
    secret: Option<String>,
    key: Option<String>,
    public_key: Option<String>,
    verification_key: Option<String>,
    active: Option<bool>,
}

pub fn extract_token(headers: &HeaderMap) -> Option<String> {
    extract_cookie(headers, "access_token_cookie").or_else(|| extract_authorization(headers))
}

pub fn verify_request_token(
    headers: &HeaderMap,
    config: &SharedStorageConfig,
) -> Result<AuthClaims, PolicyFailure> {
    let token = extract_token(headers).ok_or_else(|| unauthorized("Unauthorized"))?;
    let header = decode_header(&token).map_err(|_| unauthorized("Unauthorized"))?;
    let key = select_key(config, header.kid.as_deref())
        .ok_or_else(|| unauthorized("Invalid token signature"))?;
    let algorithm = key.algorithm();
    let mut validation = Validation::new(algorithm);
    validation.validate_exp = true;

    let data = decode::<AuthClaims>(&token, &key.decoding_key()?, &validation)
        .map_err(|_| unauthorized("Unauthorized"))?;
    if data.claims.sub.as_deref().unwrap_or_default().is_empty()
        || data.claims.jti.as_deref().unwrap_or_default().is_empty()
    {
        return Err(unauthorized("Invalid token"));
    }
    Ok(data.claims)
}

fn extract_authorization(headers: &HeaderMap) -> Option<String> {
    let value = headers
        .get(header::AUTHORIZATION)
        .and_then(|value| value.to_str().ok())?
        .trim();
    if value.is_empty() {
        return None;
    }
    let parts: Vec<&str> = value.split_whitespace().collect();
    match parts.as_slice() {
        [scheme, token] if scheme.eq_ignore_ascii_case("bearer") => Some((*token).to_owned()),
        [token] => Some((*token).to_owned()),
        _ => None,
    }
}

fn extract_cookie(headers: &HeaderMap, name: &str) -> Option<String> {
    headers
        .get_all(header::COOKIE)
        .iter()
        .filter_map(|value| value.to_str().ok())
        .flat_map(|value| value.split(';'))
        .filter_map(|cookie| cookie.trim().split_once('='))
        .find_map(|(cookie_name, cookie_value)| {
            (cookie_name == name && !cookie_value.trim().is_empty())
                .then(|| cookie_value.to_owned())
        })
}

#[derive(Clone, Debug)]
struct VerificationKey {
    algorithm: String,
    secret: String,
    rsa: bool,
}

impl VerificationKey {
    fn algorithm(&self) -> Algorithm {
        match self.algorithm.to_ascii_uppercase().as_str() {
            "RS256" => Algorithm::RS256,
            _ => Algorithm::HS256,
        }
    }

    fn decoding_key(&self) -> Result<DecodingKey, PolicyFailure> {
        if self.rsa {
            DecodingKey::from_rsa_pem(self.secret.as_bytes())
                .map_err(|_| unauthorized("Invalid token signature"))
        } else {
            Ok(DecodingKey::from_secret(self.secret.as_bytes()))
        }
    }
}

fn select_key(config: &SharedStorageConfig, kid: Option<&str>) -> Option<VerificationKey> {
    if let Some(raw) = &config.jwt_keys_json {
        if let Some(key) = select_configured_key(raw, kid) {
            return Some(key);
        }
    }
    config.jwt_secret.as_ref().map(|secret| VerificationKey {
        algorithm: "HS256".to_owned(),
        secret: secret.clone(),
        rsa: false,
    })
}

fn select_configured_key(raw: &str, kid: Option<&str>) -> Option<VerificationKey> {
    let value: Value = serde_json::from_str(raw).ok()?;
    let configs = match value {
        Value::Array(items) => items,
        Value::Object(mut map) => match map.remove("keys") {
            Some(Value::Array(items)) => items,
            _ => vec![Value::Object(map)],
        },
        _ => return None,
    };

    configs
        .into_iter()
        .filter_map(|value| serde_json::from_value::<JwtKeyConfig>(value).ok())
        .filter(|config| config.active.unwrap_or(true))
        .find_map(|config| {
            if let Some(expected) = kid {
                if config.kid.as_deref() != Some(expected) {
                    return None;
                }
            }
            let algorithm = config.algorithm.unwrap_or_else(|| "HS256".to_owned());
            let secret = if algorithm.eq_ignore_ascii_case("RS256") {
                config.public_key.or(config.verification_key)
            } else {
                config.secret.or(config.key).or(config.verification_key)
            }?;
            Some(VerificationKey {
                rsa: algorithm.eq_ignore_ascii_case("RS256"),
                algorithm,
                secret,
            })
        })
}

pub fn unauthorized(message: &str) -> PolicyFailure {
    PolicyFailure::new(
        PolicyStage::Authentication,
        StatusCode::UNAUTHORIZED,
        message,
        message,
    )
}

#[cfg(test)]
mod tests {
    use super::*;
    use http::HeaderValue;

    #[test]
    fn extracts_cookie_before_authorization() {
        let mut headers = HeaderMap::new();
        headers.insert(
            header::AUTHORIZATION,
            HeaderValue::from_static("Bearer header-token"),
        );
        headers.insert(
            header::COOKIE,
            HeaderValue::from_static("theme=dark; access_token_cookie=cookie-token"),
        );
        assert_eq!(extract_token(&headers), Some("cookie-token".to_owned()));
    }

    #[test]
    fn accepts_bare_authorization_token() {
        let mut headers = HeaderMap::new();
        headers.insert(header::AUTHORIZATION, HeaderValue::from_static("raw-token"));
        assert_eq!(extract_token(&headers), Some("raw-token".to_owned()));
    }
}
