//! SOAP 1.1/1.2 request preparation and WS-Security injection.

use base64::{Engine as _, engine::general_purpose::STANDARD};
use http::{HeaderMap, HeaderValue, header};
use serde_json::Value;
use sha1::Digest as _;
use time::{Duration, OffsetDateTime, format_description::well_known::Rfc3339};

const SOAP_11_NS: &str = "http://schemas.xmlsoap.org/soap/envelope/";
const SOAP_12_NS: &str = "http://www.w3.org/2003/05/soap-envelope";
const WSSE_NS: &str =
    "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd";
const WSU_NS: &str =
    "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd";

pub fn prepare_request(
    headers: &mut HeaderMap,
    body: Vec<u8>,
    configured_version: Option<&str>,
    ws_security: Option<&Value>,
) -> Vec<u8> {
    let text = String::from_utf8_lossy(&body);
    let version = match configured_version {
        Some("1.1") => "1.1",
        Some("1.2") => "1.2",
        _ if text.contains(SOAP_12_NS) => "1.2",
        _ => "1.1",
    };
    let action = headers
        .get("soapaction")
        .and_then(|value| value.to_str().ok())
        .map(|value| value.trim_matches('"'))
        .filter(|value| !value.is_empty());

    let incoming_content_type = headers
        .get(header::CONTENT_TYPE)
        .and_then(|value| value.to_str().ok())
        .map(str::to_owned);
    let content_type = match incoming_content_type {
        Some(value) if value.to_ascii_lowercase().starts_with("application/xml") => {
            "text/xml; charset=utf-8".to_owned()
        }
        Some(value) => value,
        None if version == "1.2" && action.is_some() => {
            format!(
                "application/soap+xml; charset=utf-8; action=\"{}\"",
                action.unwrap_or_default()
            )
        }
        None if version == "1.2" => "application/soap+xml; charset=utf-8".to_owned(),
        None => "text/xml; charset=utf-8".to_owned(),
    };
    if let Ok(value) = HeaderValue::from_str(&content_type) {
        headers.insert(header::CONTENT_TYPE, value);
    }
    if version == "1.1" && !headers.contains_key("soapaction") {
        headers.insert("soapaction", HeaderValue::from_static("\"\""));
    }

    let Some(config) = ws_security.and_then(Value::as_object) else {
        return body;
    };
    let security = create_security_header(config);
    inject_security_header(&text, version, &security)
        .map(String::into_bytes)
        .unwrap_or(body)
}

fn create_security_header(config: &serde_json::Map<String, Value>) -> String {
    let now = OffsetDateTime::now_utc();
    let ttl = config
        .get("timestamp_ttl_seconds")
        .and_then(Value::as_i64)
        .unwrap_or(300)
        .max(0);
    let created = timestamp(now);
    let expires = timestamp(now + Duration::seconds(ttl));
    let timestamp_id = format!("Timestamp-{}", uuid::Uuid::new_v4());
    let add_timestamp = config
        .get("add_timestamp")
        .and_then(Value::as_bool)
        .unwrap_or(true);
    let username = config.get("username").and_then(Value::as_str);
    let password = config.get("password").and_then(Value::as_str);
    let password_type = config
        .get("password_type")
        .and_then(Value::as_str)
        .unwrap_or("PasswordText");
    let add_nonce = config
        .get("add_nonce")
        .and_then(Value::as_bool)
        .unwrap_or(true);

    let mut output = format!("<wsse:Security xmlns:wsse=\"{WSSE_NS}\" xmlns:wsu=\"{WSU_NS}\">");
    if add_timestamp {
        output.push_str(&format!(
            "<wsu:Timestamp wsu:Id=\"{}\"><wsu:Created>{created}</wsu:Created><wsu:Expires>{expires}</wsu:Expires></wsu:Timestamp>",
            xml_escape(&timestamp_id)
        ));
    }
    if let Some(username) = username {
        let nonce = *uuid::Uuid::new_v4().as_bytes();
        let nonce_b64 = STANDARD.encode(nonce);
        let password_element = match (password, password_type) {
            (Some(password), "PasswordDigest") => {
                let digest = sha1::Sha1::digest(
                    [nonce.as_slice(), created.as_bytes(), password.as_bytes()].concat(),
                );
                format!(
                    "<wsse:Password Type=\"http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-username-token-profile-1.0#PasswordDigest\">{}</wsse:Password>",
                    STANDARD.encode(digest)
                )
            }
            (Some(password), "PasswordDigestSHA256") => {
                let digest = sha2::Sha256::digest(
                    [nonce.as_slice(), created.as_bytes(), password.as_bytes()].concat(),
                );
                format!(
                    "<wsse:Password Type=\"http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-username-token-profile-1.1#PasswordDigestSHA256\">{}</wsse:Password>",
                    STANDARD.encode(digest)
                )
            }
            (Some(password), _) => format!(
                "<wsse:Password Type=\"http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-username-token-profile-1.0#PasswordText\">{}</wsse:Password>",
                xml_escape(password)
            ),
            (None, _) => String::new(),
        };
        let nonce_element = if add_nonce {
            format!(
                "<wsse:Nonce EncodingType=\"http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-soap-message-security-1.0#Base64Binary\">{nonce_b64}</wsse:Nonce>"
            )
        } else {
            String::new()
        };
        output.push_str(&format!(
            "<wsse:UsernameToken wsu:Id=\"UsernameToken-{}\"><wsse:Username>{}</wsse:Username>{password_element}{nonce_element}<wsu:Created>{created}</wsu:Created></wsse:UsernameToken>",
            uuid::Uuid::new_v4(),
            xml_escape(username)
        ));
    }
    output.push_str("</wsse:Security>");
    output
}

fn inject_security_header(envelope: &str, version: &str, security: &str) -> Option<String> {
    let envelope_name = envelope.to_ascii_lowercase().find("envelope")?;
    let envelope_start = envelope[..envelope_name].rfind('<')?;
    let envelope_end = envelope[envelope_name..].find('>')? + envelope_name;
    let opening = &envelope[envelope_start + 1..envelope_end];
    let qualified_name = opening.split_whitespace().next()?;
    if !qualified_name.to_ascii_lowercase().ends_with("envelope") {
        return None;
    }
    let prefix = qualified_name
        .strip_suffix("Envelope")
        .unwrap_or_default()
        .trim_end_matches(':');
    let header_name = if prefix.is_empty() {
        "Header".to_owned()
    } else {
        format!("{prefix}:Header")
    };
    let opening_header = format!("<{header_name}");
    if let Some(start) = envelope.find(&opening_header) {
        let end = envelope[start..].find('>')? + start + 1;
        let mut result = envelope.to_owned();
        result.insert_str(end, security);
        return Some(result);
    }

    let namespace = if version == "1.2" {
        SOAP_12_NS
    } else {
        SOAP_11_NS
    };
    let header = if prefix.is_empty() {
        format!("<Header xmlns=\"{namespace}\">{security}</Header>")
    } else {
        format!("<{prefix}:Header>{security}</{prefix}:Header>")
    };
    let mut result = envelope.to_owned();
    result.insert_str(envelope_end + 1, &header);
    Some(result)
}

fn timestamp(value: OffsetDateTime) -> String {
    value
        .replace_nanosecond(0)
        .unwrap_or(value)
        .format(&Rfc3339)
        .unwrap_or_default()
}

fn xml_escape(value: &str) -> String {
    value
        .replace('&', "&amp;")
        .replace('<', "&lt;")
        .replace('>', "&gt;")
        .replace('"', "&quot;")
        .replace('\'', "&apos;")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn maps_content_types_and_injects_ws_security() {
        let mut headers = HeaderMap::new();
        headers.insert(
            header::CONTENT_TYPE,
            HeaderValue::from_static("application/xml"),
        );
        let body = br#"<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"><soap:Body/></soap:Envelope>"#.to_vec();
        let output = prepare_request(
            &mut headers,
            body,
            Some("1.1"),
            Some(&serde_json::json!({
                "username": "alice",
                "password": "secret",
                "add_timestamp": true
            })),
        );
        assert_eq!(headers[header::CONTENT_TYPE], "text/xml; charset=utf-8");
        assert_eq!(headers["soapaction"], "\"\"");
        let output = String::from_utf8(output).unwrap();
        assert!(output.contains("<soap:Header>"));
        assert!(output.contains("<wsse:Username>alice</wsse:Username>"));
        assert!(output.contains("PasswordText"));
    }

    #[test]
    fn preserves_explicit_soap_twelve_content_type() {
        let mut headers = HeaderMap::new();
        headers.insert(
            header::CONTENT_TYPE,
            HeaderValue::from_static("application/soap+xml; action=\"go\""),
        );
        let body = format!("<Envelope xmlns=\"{SOAP_12_NS}\"><Body/></Envelope>").into_bytes();
        let _ = prepare_request(&mut headers, body, None, None);
        assert_eq!(
            headers[header::CONTENT_TYPE],
            "application/soap+xml; action=\"go\""
        );
        assert!(!headers.contains_key("soapaction"));
    }
}
