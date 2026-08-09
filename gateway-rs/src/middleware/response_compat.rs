use axum::{
    body::{Body, to_bytes},
    extract::{OriginalUri, Request, State},
    middleware::Next,
    response::Response,
};
use http::{HeaderValue, StatusCode, header};
use serde_json::{Map, Value};

use crate::state::AppState;

#[derive(Clone, Copy, Debug)]
pub struct MessageEnvelope;

pub async fn response_compat(
    State(state): State<AppState>,
    request: Request,
    next: Next,
) -> Response {
    let path = request
        .extensions()
        .get::<OriginalUri>()
        .map(|uri| uri.0.path().to_owned())
        .unwrap_or_else(|| request.uri().path().to_owned());
    let response = next.run(request).await;

    if matches!(
        path.as_str(),
        "/api/health"
            | "/platform/monitor/liveness"
            | "/platform/monitor/readiness"
            | "/platform/openapi.json"
    ) || path.starts_with("/api/soap/")
    {
        return response;
    }
    let is_json = response
        .headers()
        .get(header::CONTENT_TYPE)
        .and_then(|value| value.to_str().ok())
        .is_some_and(|value| value.to_ascii_lowercase().contains("application/json"));
    if !is_json {
        return response;
    }

    let (mut parts, body) = response.into_parts();
    let Ok(bytes) = to_bytes(body, usize::MAX).await else {
        return Response::from_parts(parts, Body::empty());
    };
    let mut output = bytes.to_vec();
    let message_envelope = parts.extensions.get::<MessageEnvelope>().is_some()
        || (path == "/api/caches" && is_message_payload_bytes(&bytes));

    if state.config.strict_response_envelope
        && let Ok(payload) = serde_json::from_slice::<Value>(&bytes)
    {
        let original_status = parts.status;
        let mut envelope = Map::new();
        envelope.insert(
            "status_code".to_owned(),
            Value::Number(serde_json::Number::from(original_status.as_u16())),
        );
        if original_status.is_success() {
            if message_envelope {
                if let Value::Object(values) = payload {
                    envelope.extend(values);
                }
            } else {
                if let Value::Object(values) = &payload {
                    for key in ["access_token", "refresh_token"] {
                        if let Some(value) = values.get(key) {
                            envelope.insert(key.to_owned(), value.clone());
                        }
                    }
                }
                envelope.insert("response".to_owned(), payload);
            }
        } else if let Value::Object(values) = payload {
            envelope.extend(values);
        } else {
            envelope.insert(
                "error_message".to_owned(),
                Value::String("Request failed".to_owned()),
            );
        }
        output = serde_json::to_vec(&Value::Object(envelope)).unwrap_or(output);
        parts.status = StatusCode::OK;
    }

    set_body_length(&mut parts.headers, output.len());
    Response::from_parts(parts, Body::from(output))
}

fn is_message_payload_bytes(bytes: &[u8]) -> bool {
    serde_json::from_slice::<Value>(bytes)
        .ok()
        .and_then(|payload| payload.as_object().cloned())
        .is_some_and(|values| values.len() == 1 && values.contains_key("message"))
}

fn set_body_length(headers: &mut http::HeaderMap, length: usize) {
    let Ok(value) = HeaderValue::from_str(&length.to_string()) else {
        return;
    };
    headers.insert(header::CONTENT_LENGTH, value.clone());
    headers.insert("x-body-length", value);
}

#[cfg(test)]
mod tests {
    use super::is_message_payload_bytes;
    use serde_json::json;

    #[test]
    fn only_plain_message_payloads_use_message_envelope() {
        assert!(is_message_payload_bytes(
            json!({"message": "done"}).to_string().as_bytes()
        ));
        assert!(!is_message_payload_bytes(
            json!({"message": "done", "id": 1}).to_string().as_bytes()
        ));
        assert!(!is_message_payload_bytes(
            json!({"ok": true}).to_string().as_bytes()
        ));
    }
}
