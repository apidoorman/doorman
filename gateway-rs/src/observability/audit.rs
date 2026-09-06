use std::collections::BTreeMap;

use http::HeaderMap;

#[derive(Clone, Debug)]
pub struct AuditEvent {
    pub action: String,
    pub target: String,
    pub status: String,
}

const REDACTED: &str = "[REDACTED]";

/// Return a structured header view that is safe to attach to an audit record.
/// Audit callers must use this instead of logging a `HeaderMap` directly.
pub fn redacted_headers(headers: &HeaderMap) -> BTreeMap<String, String> {
    headers
        .iter()
        .map(|(name, value)| {
            let name = name.as_str().to_ascii_lowercase();
            let value = if is_sensitive_name(&name) {
                REDACTED.to_owned()
            } else {
                value.to_str().unwrap_or("[BINARY]").to_owned()
            };
            (name, value)
        })
        .collect()
}

/// Redact a user-provided value before including it in an audit record.
pub fn redacted_value(field: &str, value: &str) -> String {
    if is_sensitive_name(field) {
        REDACTED.to_owned()
    } else {
        value.to_owned()
    }
}

pub fn management_mutation(actor: &str, action: &str, target: &str, status: &str) {
    tracing::info!(
        actor = %redacted_value("actor", actor),
        action,
        target = %redacted_value("target", target),
        status,
        "platform audit event"
    );
}

pub fn global_ip_deny(target: &str, reason: &str, source_ip: Option<&str>) {
    tracing::info!(
        action = "ip.global_deny",
        target,
        status = "blocked",
        reason,
        source_ip,
        "platform audit event"
    );
}

pub fn config_export(actor: &str, section: Option<&str>) {
    management_mutation(actor, "config.export", section.unwrap_or("all"), "success");
}

fn is_sensitive_name(name: &str) -> bool {
    let normalized = name.to_ascii_lowercase();
    matches!(
        normalized.as_str(),
        "authorization" | "proxy-authorization" | "cookie" | "set-cookie"
    ) || normalized.contains("password")
        || normalized.contains("secret")
        || normalized.contains("token")
        || normalized.contains("api-key")
        || normalized.contains("apikey")
        || normalized.contains("credential")
}

#[cfg(test)]
mod tests {
    use http::{HeaderMap, HeaderValue, header};

    use super::{REDACTED, redacted_headers, redacted_value};

    #[test]
    fn audit_header_redaction_never_exposes_credentials() {
        let mut headers = HeaderMap::new();
        headers.insert(
            header::AUTHORIZATION,
            HeaderValue::from_static("Bearer secret-token"),
        );
        headers.insert(
            header::COOKIE,
            HeaderValue::from_static("access_token_cookie=secret"),
        );
        headers.insert("x-api-key", HeaderValue::from_static("secret-api-key"));
        headers.insert("x-password", HeaderValue::from_static("secret-password"));
        headers.insert("x-request-id", HeaderValue::from_static("safe-id"));

        let redacted = redacted_headers(&headers);
        assert_eq!(redacted["authorization"], REDACTED);
        assert_eq!(redacted["cookie"], REDACTED);
        assert_eq!(redacted["x-api-key"], REDACTED);
        assert_eq!(redacted["x-password"], REDACTED);
        assert_eq!(redacted["x-request-id"], "safe-id");
        assert_eq!(redacted_value("token", "secret"), REDACTED);
    }
}
