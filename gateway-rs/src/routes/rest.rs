use std::{
    net::SocketAddr,
    time::{SystemTime, UNIX_EPOCH},
};

use axum::{
    Json,
    body::{Body, to_bytes},
    extract::{ConnectInfo, OriginalUri, Request, State},
    response::{IntoResponse, Response},
};
use http::{HeaderMap, HeaderName, StatusCode, header};
use serde_json::Value;

use crate::{
    error::GatewayError,
    middleware::body_limit::BodyLimits,
    policy::{
        PolicyErrorBody,
        evaluator::{PolicyRequest, PolicyRuntime, evaluate_rest_policy, evaluate_shared_effects},
    },
    proxy::platform::proxy_to_python,
    state::AppState,
};

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum DataPlaneProtocol {
    Rest,
    Graphql,
    Soap,
    Grpc,
}

#[derive(Clone, Debug)]
pub struct PolicyPath(pub String);

pub async fn rest_policy_then_proxy(
    State(state): State<AppState>,
    request: Request,
) -> Result<Response, GatewayError> {
    if request.method() == http::Method::OPTIONS {
        if state.config.mode.enforces_policies() {
            return Ok(StatusCode::NO_CONTENT.into_response());
        }
        return proxy_to_python(State(state), request).await;
    }

    if state.config.mode.evaluates_policies() {
        let protocol = request
            .extensions()
            .get::<DataPlaneProtocol>()
            .copied()
            .unwrap_or(DataPlaneProtocol::Rest);
        let enforce = state.config.mode.enforces_policies();
        let path = request
            .extensions()
            .get::<PolicyPath>()
            .map(|value| value.0.clone())
            .or_else(|| {
                request
                    .extensions()
                    .get::<OriginalUri>()
                    .map(|value| value.0.path().to_owned())
            })
            .unwrap_or_else(|| request.uri().path().to_owned());
        let peer = request
            .extensions()
            .get::<ConnectInfo<SocketAddr>>()
            .map(|value| value.0.ip());
        let headers = request.headers().clone();
        let content_length = headers
            .get(header::CONTENT_LENGTH)
            .and_then(|value| value.to_str().ok())
            .and_then(|value| value.parse::<u64>().ok())
            .unwrap_or(0);
        let policy_request = PolicyRequest {
            method: request.method().clone(),
            path,
            headers,
            direct_ip: peer,
            now_millis: now_millis(),
            content_length,
        };

        let documents = if let Some(injected) = &state.policy_documents {
            injected
                .lock()
                .map(|documents| documents.clone())
                .map_err(|error| error.to_string())
        } else if let Some(storage) = &state.storage {
            storage
                .load_policy_documents()
                .await
                .map_err(|error| error.to_string())
        } else {
            Err("shared policy storage is unavailable".to_owned())
        };
        let result = match documents {
            Ok(mut documents) => match evaluate_rest_policy(
                &mut documents,
                &policy_request,
                &state.config.shared_storage,
                &PolicyRuntime::default(),
            ) {
                Ok(Some(mut decision)) => {
                    if let Some(storage) = &state.storage {
                        evaluate_shared_effects(
                            &documents,
                            &policy_request,
                            &mut decision,
                            storage,
                            enforce,
                        )
                        .await
                        .map(|()| Some(decision))
                    } else if enforce {
                        Err(crate::policy::PolicyFailure::new(
                            crate::policy::PolicyStage::Resolution,
                            StatusCode::SERVICE_UNAVAILABLE,
                            "GTW006",
                            "Gateway state store unavailable",
                        ))
                    } else {
                        Ok(Some(decision))
                    }
                }
                other => other,
            },
            Err(error) => {
                tracing::error!(error = %error, "rust policy storage unavailable");
                if enforce {
                    Err(crate::policy::PolicyFailure::new(
                        crate::policy::PolicyStage::Resolution,
                        StatusCode::SERVICE_UNAVAILABLE,
                        "GTW006",
                        "Gateway state store unavailable",
                    ))
                } else {
                    return proxy_to_python(State(state), request).await;
                }
            }
        };
        match result {
            Ok(Some(decision)) => {
                tracing::debug!(?decision, "rust policy shadow decision");
                if enforce {
                    return execute_rest(&state, request, decision, protocol).await;
                }
            }
            Ok(None) => {
                tracing::debug!("rust policy could not resolve API");
                if enforce {
                    return Ok((
                        StatusCode::NOT_FOUND,
                        Json(PolicyErrorBody {
                            error_code: "GTW001".to_owned(),
                            error_message: "API does not exist for the requested name and version"
                                .to_owned(),
                        }),
                    )
                        .into_response());
                }
            }
            Err(failure) => {
                tracing::debug!(?failure, "rust policy shadow failure");
                if enforce {
                    return Ok((
                        failure.status,
                        Json(PolicyErrorBody {
                            error_code: failure.error_code,
                            error_message: failure.error_message,
                        }),
                    )
                        .into_response());
                }
            }
        }
    }

    proxy_to_python(State(state), request).await
}

async fn execute_rest(
    state: &AppState,
    request: Request,
    decision: crate::policy::PolicyDecision,
    protocol: DataPlaneProtocol,
) -> Result<Response, GatewayError> {
    if let Some(delay_ms) = decision.throttle_delay_ms.filter(|delay| *delay > 0) {
        tokio::time::sleep(std::time::Duration::from_millis(delay_ms)).await;
    }
    if decision.is_crud && protocol == DataPlaneProtocol::Rest {
        return execute_crud(state, request, &decision).await;
    }

    let Some(base_url) = decision.upstream else {
        return Ok((
            StatusCode::NOT_FOUND,
            Json(PolicyErrorBody {
                error_code: "GTW001".to_owned(),
                error_message: "No upstream servers configured".to_owned(),
            }),
        )
            .into_response());
    };
    let upstream_path = decision.upstream_path.unwrap_or_else(|| "/".to_owned());
    let query = request
        .uri()
        .query()
        .map(|value| format!("?{value}"))
        .unwrap_or_default();
    let target = format!(
        "{}/{}{}",
        base_url.trim_end_matches('/'),
        upstream_path.trim_start_matches('/'),
        query
    );
    let (parts, body) = request.into_parts();
    let limits = BodyLimits::from_env();
    let body_limit = match protocol {
        DataPlaneProtocol::Rest => limits.rest,
        DataPlaneProtocol::Graphql => limits.graphql,
        DataPlaneProtocol::Soap => limits.soap,
        DataPlaneProtocol::Grpc => limits.grpc,
    };
    let body = to_bytes(body, body_limit).await?;
    if let Err(failure) =
        validate_protocol_request(protocol, &parts.method, &body, decision.graphql_max_depth)
    {
        return Ok((
            failure.status,
            Json(PolicyErrorBody {
                error_code: failure.error_code,
                error_message: failure.error_message,
            }),
        )
            .into_response());
    }
    let request_header_bytes = parts
        .headers
        .iter()
        .map(|(name, value)| name.as_str().len() + value.as_bytes().len())
        .sum::<usize>();
    let request_body_bytes = body.len();
    let allowed = decision
        .allowed_headers
        .iter()
        .map(|value| value.to_ascii_lowercase())
        .collect::<Vec<_>>();
    let mut headers = HeaderMap::new();
    for (name, value) in &parts.headers {
        let lower = name.as_str().to_ascii_lowercase();
        let always_forward = matches!(lower.as_str(), "content-type" | "accept" | "x-request-id");
        let protocol_default = protocol == DataPlaneProtocol::Soap
            && matches!(
                lower.as_str(),
                "soapaction" | "user-agent" | "accept-encoding"
            );
        if (always_forward || protocol_default || allowed.iter().any(|item| item == &lower))
            && !is_hop_by_hop(name)
            && name != header::HOST
        {
            headers.append(name.clone(), value.clone());
        }
    }
    if let Some(source_name) = decision
        .authorization_field_swap
        .as_deref()
        .and_then(|name| HeaderName::try_from(name).ok())
    {
        let swapped = headers
            .get(&source_name)
            .filter(|value| !value.as_bytes().iter().all(u8::is_ascii_whitespace))
            .cloned()
            .or_else(|| parts.headers.get(header::AUTHORIZATION).cloned());
        if let Some(value) = swapped {
            headers.insert(header::AUTHORIZATION, value);
        }
    }
    if protocol == DataPlaneProtocol::Graphql {
        headers.insert(
            header::CONTENT_TYPE,
            http::HeaderValue::from_static("application/json"),
        );
        headers.insert(
            header::ACCEPT,
            http::HeaderValue::from_static("application/json"),
        );
    }
    if let Some(username) = decision.username.as_deref() {
        if let Ok(value) = http::HeaderValue::from_str(username) {
            headers.insert("x-user-email", value.clone());
            headers.insert("x-doorman-user", value);
        }
    }
    if let Some(name) = decision
        .credit_header_name
        .as_deref()
        .and_then(|name| HeaderName::try_from(name).ok())
    {
        let value = decision
            .user_credit_header_value
            .as_deref()
            .or(decision.credit_header_value.as_deref());
        if let Some(value) = value.and_then(|value| http::HeaderValue::from_str(value).ok()) {
            headers.insert(name, value);
        }
    }
    let attempts = decision.retry_count.saturating_add(1);
    let mut attempt = 0_u32;
    let upstream = loop {
        attempt += 1;
        let result = state
            .proxy_client
            .request(parts.method.clone(), target.clone())
            .headers(headers.clone())
            .timeout(std::time::Duration::from_millis(
                decision.request_timeout_ms.max(1),
            ))
            .body(body.clone())
            .send()
            .await;
        match result {
            Ok(response)
                if matches!(response.status().as_u16(), 500 | 502 | 503 | 504)
                    && attempt < attempts =>
            {
                retry_backoff(attempt).await;
            }
            Ok(response) => break response,
            Err(_) if attempt < attempts => retry_backoff(attempt).await,
            Err(error) if error.is_timeout() => {
                return Ok((
                    StatusCode::GATEWAY_TIMEOUT,
                    Json(PolicyErrorBody {
                        error_code: "GTW010".to_owned(),
                        error_message: "Gateway timeout".to_owned(),
                    }),
                )
                    .into_response());
            }
            Err(error) => return Err(error.into()),
        }
    };
    let status = upstream.status();
    if status == StatusCode::NOT_FOUND {
        return Ok((
            StatusCode::NOT_FOUND,
            Json(PolicyErrorBody {
                error_code: "GTW005".to_owned(),
                error_message: "Endpoint does not exist in backend service".to_owned(),
            }),
        )
            .into_response());
    }
    let upstream_headers = upstream.headers().clone();
    let is_json = upstream_headers
        .get(header::CONTENT_TYPE)
        .and_then(|value| value.to_str().ok())
        .is_some_and(|value| value.to_ascii_lowercase().contains("application/json"));
    let upstream_content_type = upstream_headers
        .get(header::CONTENT_TYPE)
        .and_then(|value| value.to_str().ok())
        .unwrap_or(match protocol {
            DataPlaneProtocol::Soap => "application/xml",
            DataPlaneProtocol::Grpc => "application/grpc",
            DataPlaneProtocol::Rest | DataPlaneProtocol::Graphql => "application/json",
        })
        .to_owned();
    let bytes = upstream.bytes().await?;
    if let (Some(storage), Some(key), Some(ttl)) = (
        state.storage.as_ref(),
        decision.bandwidth_key.as_deref(),
        decision.bandwidth_ttl_seconds,
    ) {
        let response_header_bytes = upstream_headers
            .iter()
            .map(|(name, value)| name.as_str().len() + value.as_bytes().len())
            .sum::<usize>();
        let accounted = request_header_bytes
            .saturating_add(request_body_bytes)
            .saturating_add(response_header_bytes)
            .saturating_add(bytes.len()) as u64;
        if let Err(error) = storage.add_bandwidth(key, accounted, ttl).await {
            tracing::error!(error = %error, "bandwidth accounting failed");
            return Ok((
                StatusCode::SERVICE_UNAVAILABLE,
                Json(PolicyErrorBody {
                    error_code: "GTW006".to_owned(),
                    error_message: "Gateway state store unavailable".to_owned(),
                }),
            )
                .into_response());
        }
    }
    let (body, content_type) = match protocol {
        DataPlaneProtocol::Soap | DataPlaneProtocol::Graphql | DataPlaneProtocol::Grpc => {
            (bytes.to_vec(), upstream_content_type)
        }
        DataPlaneProtocol::Rest if !is_json => (
            serde_json::to_vec(&String::from_utf8_lossy(&bytes))
                .unwrap_or_else(|_| b"null".to_vec()),
            "application/json".to_owned(),
        ),
        DataPlaneProtocol::Rest => (bytes.to_vec(), upstream_content_type),
    };
    let mut response = Response::builder()
        .status(status)
        .header(header::CONTENT_TYPE, content_type);
    for name in [
        "grpc-status",
        "grpc-message",
        "grpc-encoding",
        "grpc-accept-encoding",
    ] {
        if protocol == DataPlaneProtocol::Grpc {
            if let Some(value) = upstream_headers.get(name) {
                response = response.header(name, value);
            }
        }
    }
    for name in &decision.allowed_headers {
        if let Ok(header_name) = HeaderName::try_from(name) {
            if let Some(value) = upstream_headers.get(&header_name) {
                response = response.header(header_name, value);
            }
        }
    }
    Ok(response.body(Body::from(body))?)
}

async fn execute_crud(
    state: &AppState,
    request: Request,
    decision: &crate::policy::PolicyDecision,
) -> Result<Response, GatewayError> {
    let Some(storage) = state.storage.as_ref() else {
        return Ok(policy_error_response(
            StatusCode::SERVICE_UNAVAILABLE,
            "GTW006",
            "Gateway state store unavailable",
        ));
    };
    let Some(collection) = decision
        .crud_collection
        .as_deref()
        .filter(|name| valid_collection_name(name))
    else {
        return Ok(policy_error_response(
            StatusCode::INTERNAL_SERVER_ERROR,
            "CRUD500",
            "CRUD collection is not configured",
        ));
    };

    let method = request.method().clone();
    let resource_id = crud_resource_id(request.uri().path()).map(str::to_owned);
    let (_, body) = request.into_parts();
    let body = to_bytes(body, BodyLimits::from_env().rest).await?;
    let operation = async {
        match method {
            http::Method::GET => {
                if let Some(resource_id) = resource_id.as_deref() {
                    storage
                        .crud_find_one(collection, resource_id)
                        .await
                        .map(|value| match value {
                            Some(value) => crud_success(StatusCode::OK, value),
                            None => policy_error_response(
                                StatusCode::NOT_FOUND,
                                "CRUD404",
                                "Resource not found",
                            ),
                        })
                } else {
                    storage.crud_list(collection).await.map(|items| {
                        crud_success(StatusCode::OK, serde_json::json!({ "items": items }))
                    })
                }
            }
            http::Method::POST => {
                let mut value = parse_crud_body(&body)?;
                if value.get("_id").is_none() {
                    value["_id"] = Value::String(uuid::Uuid::new_v4().to_string());
                }
                validate_crud_schema(decision.crud_schema.as_ref(), &value, false)?;
                storage
                    .crud_insert(collection, &value)
                    .await
                    .map(|()| crud_success(StatusCode::CREATED, value))
            }
            http::Method::PUT | http::Method::PATCH => {
                let Some(resource_id) = resource_id.as_deref() else {
                    return Ok(policy_error_response(
                        StatusCode::BAD_REQUEST,
                        "CRUD400",
                        "Resource ID required for update",
                    ));
                };
                let value = parse_crud_body(&body)?;
                validate_crud_schema(decision.crud_schema.as_ref(), &value, true)?;
                storage
                    .crud_update(collection, resource_id, &value)
                    .await
                    .map(|value| match value {
                        Some(value) => crud_success(StatusCode::OK, value),
                        None => policy_error_response(
                            StatusCode::NOT_FOUND,
                            "CRUD404",
                            "Resource not found",
                        ),
                    })
            }
            http::Method::DELETE => {
                let Some(resource_id) = resource_id.as_deref() else {
                    return Ok(policy_error_response(
                        StatusCode::BAD_REQUEST,
                        "CRUD400",
                        "Resource ID required for deletion",
                    ));
                };
                storage
                    .crud_delete(collection, resource_id)
                    .await
                    .map(|deleted| {
                        if deleted {
                            crud_success(
                                StatusCode::OK,
                                serde_json::json!({ "message": "Resource deleted successfully" }),
                            )
                        } else {
                            policy_error_response(
                                StatusCode::NOT_FOUND,
                                "CRUD404",
                                "Resource not found",
                            )
                        }
                    })
            }
            _ => Ok(policy_error_response(
                StatusCode::METHOD_NOT_ALLOWED,
                "CRUD405",
                "Method not allowed",
            )),
        }
    }
    .await;

    match operation {
        Ok(response) => Ok(response),
        Err(crate::storage::runtime::StorageError::InvalidDocument(error)) => {
            tracing::debug!(error = %error, "CRUD validation failed");
            Ok(policy_error_response(
                StatusCode::BAD_REQUEST,
                "CRUD400",
                "Validation failed",
            ))
        }
        Err(error) => {
            tracing::error!(error = %error, "CRUD storage operation failed");
            Ok(policy_error_response(
                StatusCode::SERVICE_UNAVAILABLE,
                "GTW006",
                "Gateway state store unavailable",
            ))
        }
    }
}

fn valid_collection_name(name: &str) -> bool {
    !name.is_empty()
        && name.len() <= 120
        && !name.starts_with("system.")
        && name
            .chars()
            .all(|character| character.is_ascii_alphanumeric() || matches!(character, '_' | '-'))
}

fn crud_resource_id(path: &str) -> Option<&str> {
    let segments = path
        .split('/')
        .filter(|segment| !segment.is_empty())
        .collect::<Vec<_>>();
    let rest = segments.iter().position(|segment| *segment == "rest")?;
    let endpoint = segments.get(rest + 3..)?;
    (endpoint.len() > 1).then(|| *endpoint.last().expect("endpoint is non-empty"))
}

fn parse_crud_body(body: &[u8]) -> Result<Value, crate::storage::runtime::StorageError> {
    let value: Value = serde_json::from_slice(body)?;
    if !value.is_object() {
        return Err(crate::storage::runtime::StorageError::InvalidDocument(
            "CRUD request body must be a JSON object".to_owned(),
        ));
    }
    Ok(value)
}

fn validate_crud_schema(
    schema: Option<&Value>,
    value: &Value,
    partial: bool,
) -> Result<(), crate::storage::runtime::StorageError> {
    let Some(schema) = schema.and_then(Value::as_object) else {
        return Ok(());
    };
    let Some(value) = value.as_object() else {
        return Err(crate::storage::runtime::StorageError::InvalidDocument(
            "CRUD request body must be a JSON object".to_owned(),
        ));
    };
    let mut errors = Vec::new();
    validate_crud_fields(schema, value, partial, "", &mut errors);
    if errors.is_empty() {
        Ok(())
    } else {
        Err(crate::storage::runtime::StorageError::InvalidDocument(
            errors.join("; "),
        ))
    }
}

fn validate_crud_fields(
    schema: &serde_json::Map<String, Value>,
    value: &serde_json::Map<String, Value>,
    partial: bool,
    prefix: &str,
    errors: &mut Vec<String>,
) {
    for (field, rules) in schema {
        let Some(rules) = rules.as_object() else {
            continue;
        };
        let path = if prefix.is_empty() {
            field.clone()
        } else {
            format!("{prefix}.{field}")
        };
        let field_value = value.get(field).filter(|value| !value.is_null());
        if field_value.is_none() {
            if !partial && rules.get("required").and_then(Value::as_bool) == Some(true) {
                errors.push(format!("Field '{path}' is required"));
            }
            continue;
        }
        let field_value = field_value.expect("checked above");
        let expected = rules.get("type").and_then(Value::as_str);
        let valid_type = match expected {
            Some("string") => field_value.is_string(),
            Some("number") => field_value.is_number(),
            Some("integer") => field_value.as_i64().is_some() || field_value.as_u64().is_some(),
            Some("boolean") => field_value.is_boolean(),
            Some("array") => field_value.is_array(),
            Some("object") => field_value.is_object(),
            _ => true,
        };
        if !valid_type {
            errors.push(format!(
                "Field '{path}' must be of type {}",
                expected.unwrap_or_default()
            ));
            continue;
        }
        if let Some(text) = field_value.as_str() {
            if rules
                .get("min_length")
                .and_then(Value::as_u64)
                .is_some_and(|min| text.chars().count() < min as usize)
            {
                errors.push(format!("Field '{path}' is shorter than min_length"));
            }
            if rules
                .get("max_length")
                .and_then(Value::as_u64)
                .is_some_and(|max| text.chars().count() > max as usize)
            {
                errors.push(format!("Field '{path}' is longer than max_length"));
            }
        }
        if let Some(allowed) = rules.get("enum").and_then(Value::as_array) {
            if !allowed.contains(field_value) {
                errors.push(format!("Field '{path}' is not an allowed value"));
            }
        }
        if let (Some(properties), Some(object)) = (
            rules.get("properties").and_then(Value::as_object),
            field_value.as_object(),
        ) {
            validate_crud_fields(properties, object, false, &path, errors);
        }
    }
}

fn crud_success(status: StatusCode, value: Value) -> Response {
    (status, Json(value)).into_response()
}

fn policy_error_response(status: StatusCode, code: &str, message: &str) -> Response {
    (
        status,
        Json(PolicyErrorBody {
            error_code: code.to_owned(),
            error_message: message.to_owned(),
        }),
    )
        .into_response()
}

fn validate_protocol_request(
    protocol: DataPlaneProtocol,
    method: &http::Method,
    body: &[u8],
    graphql_max_depth: u64,
) -> Result<(), crate::policy::PolicyFailure> {
    match protocol {
        DataPlaneProtocol::Rest => Ok(()),
        DataPlaneProtocol::Graphql => {
            let document: serde_json::Value = serde_json::from_slice(body)
                .map_err(|_| protocol_failure("GTW011", "Invalid GraphQL request body"))?;
            let query = document
                .get("query")
                .and_then(serde_json::Value::as_str)
                .filter(|query| !query.trim().is_empty())
                .ok_or_else(|| protocol_failure("GTW011", "GraphQL query is required"))?;
            let depth = graphql_depth(query)
                .ok_or_else(|| protocol_failure("GTW011", "Invalid GraphQL query"))?;
            if graphql_max_depth > 0 && depth > graphql_max_depth {
                return Err(protocol_failure(
                    "GTW013",
                    format!(
                        "Query depth {depth} exceeds maximum allowed depth of {graphql_max_depth}"
                    ),
                ));
            }
            Ok(())
        }
        DataPlaneProtocol::Soap if *method == http::Method::GET && body.is_empty() => Ok(()),
        DataPlaneProtocol::Soap => {
            let xml = std::str::from_utf8(body)
                .map_err(|_| protocol_failure("GTW011", "Invalid SOAP envelope"))?;
            let lower = xml.to_ascii_lowercase();
            let unsafe_declaration = lower.contains("<!doctype") || lower.contains("<!entity");
            let envelope = lower.contains(":envelope") || lower.contains("<envelope");
            let soap_namespace = lower.contains("http://schemas.xmlsoap.org/soap/envelope/")
                || lower.contains("http://www.w3.org/2003/05/soap-envelope");
            let soap_body = lower.contains(":body") || lower.contains("<body");
            if unsafe_declaration || !envelope || !soap_namespace || !soap_body {
                return Err(protocol_failure("GTW011", "Invalid SOAP envelope"));
            }
            Ok(())
        }
        DataPlaneProtocol::Grpc => {
            let document: serde_json::Value = serde_json::from_slice(body)
                .map_err(|_| protocol_failure("GTW011", "Invalid JSON in request body"))?;
            let grpc_method = document
                .get("method")
                .and_then(serde_json::Value::as_str)
                .unwrap_or_default();
            let mut parts = grpc_method.split('.');
            let valid_part = |part: &str| {
                !part.is_empty()
                    && part
                        .chars()
                        .all(|character| character.is_ascii_alphanumeric() || character == '_')
            };
            if !parts.next().is_some_and(valid_part)
                || !parts.next().is_some_and(valid_part)
                || parts.next().is_some()
            {
                return Err(protocol_failure(
                    "GTW011",
                    "Invalid gRPC method. Use Service.Method with alphanumerics/underscore.",
                ));
            }
            Ok(())
        }
    }
}

fn graphql_depth(query: &str) -> Option<u64> {
    let mut depth = 0_u64;
    let mut maximum = 0_u64;
    let mut quote = None;
    let mut comment = false;
    let mut escaped = false;
    for character in query.chars() {
        if comment {
            if character == '\n' {
                comment = false;
            }
            continue;
        }
        if let Some(delimiter) = quote {
            if escaped {
                escaped = false;
            } else if character == '\\' {
                escaped = true;
            } else if character == delimiter {
                quote = None;
            }
            continue;
        }
        match character {
            '#' => comment = true,
            '\'' | '"' => quote = Some(character),
            '{' => {
                depth += 1;
                maximum = maximum.max(depth);
            }
            '}' if depth == 0 => return None,
            '}' => depth -= 1,
            _ => {}
        }
    }
    (quote.is_none() && depth == 0).then_some(maximum)
}

fn protocol_failure(
    code: impl Into<String>,
    message: impl Into<String>,
) -> crate::policy::PolicyFailure {
    crate::policy::PolicyFailure::new(
        crate::policy::PolicyStage::Resolution,
        StatusCode::BAD_REQUEST,
        code,
        message,
    )
}

async fn retry_backoff(attempt: u32) {
    let delay_ms = 250_u64
        .saturating_mul(1_u64 << attempt.saturating_sub(1).min(3))
        .min(2_000);
    tokio::time::sleep(std::time::Duration::from_millis(delay_ms)).await;
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

fn now_millis() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|duration| duration.as_millis() as u64)
        .unwrap_or(0)
}

#[cfg(test)]
mod tests {
    use super::*;
    use axum::{Router, body::to_bytes, routing::any};
    use http::{Method, Request};
    use serde_json::{Value, json};

    #[tokio::test]
    async fn executes_selected_upstream_with_filtered_and_credit_headers() {
        async fn upstream(
            method: Method,
            headers: HeaderMap,
            body: axum::body::Bytes,
        ) -> (StatusCode, [(String, String); 1], Json<Value>) {
            (
                StatusCode::CREATED,
                [("x-upstream".to_owned(), "kept".to_owned())],
                Json(json!({
                    "method": method.as_str(),
                    "body": String::from_utf8_lossy(&body),
                    "x-test": headers.get("x-test").and_then(|value| value.to_str().ok()),
                    "x-api-key": headers.get("x-api-key").and_then(|value| value.to_str().ok()),
                    "x-user-email": headers.get("x-user-email").and_then(|value| value.to_str().ok()),
                })),
            )
        }

        let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
        let address = listener.local_addr().unwrap();
        let server = tokio::spawn(async move {
            axum::serve(listener, Router::new().route("/items", any(upstream)))
                .await
                .unwrap();
        });
        let state = AppState::new(crate::Config::for_test(
            crate::GatewayMode::On,
            "http://127.0.0.1:9".to_owned(),
        ))
        .unwrap();
        let decision = crate::policy::PolicyDecision {
            upstream: Some(format!("http://{address}")),
            upstream_path: Some("/items".to_owned()),
            allowed_headers: vec!["x-test".to_owned(), "x-upstream".to_owned()],
            username: Some("alice".to_owned()),
            credit_header_name: Some("x-api-key".to_owned()),
            credit_header_value: Some("system-key".to_owned()),
            user_credit_header_value: Some("user-key".to_owned()),
            ..Default::default()
        };
        let request = Request::builder()
            .method(Method::POST)
            .uri("/api/rest/demo/v1/items")
            .header("content-type", "application/json")
            .header("x-test", "forwarded")
            .header("x-secret", "dropped")
            .body(Body::from(r#"{"hello":"world"}"#))
            .unwrap();

        let response = execute_rest(&state, request, decision, DataPlaneProtocol::Rest)
            .await
            .unwrap();
        assert_eq!(response.status(), StatusCode::CREATED);
        assert_eq!(response.headers().get("x-upstream").unwrap(), "kept");
        let body: Value =
            serde_json::from_slice(&to_bytes(response.into_body(), 4096).await.unwrap()).unwrap();
        assert_eq!(body["method"], "POST");
        assert_eq!(body["x-test"], "forwarded");
        assert_eq!(body["x-api-key"], "user-key");
        assert_eq!(body["x-user-email"], "alice");
        assert_eq!(body["body"], r#"{"hello":"world"}"#);
        server.abort();
    }

    #[tokio::test]
    async fn retries_transient_upstream_statuses() {
        use std::sync::{
            Arc,
            atomic::{AtomicUsize, Ordering},
        };

        async fn flaky(State(attempts): State<Arc<AtomicUsize>>) -> (StatusCode, Json<Value>) {
            let attempt = attempts.fetch_add(1, Ordering::SeqCst);
            if attempt == 0 {
                (
                    StatusCode::SERVICE_UNAVAILABLE,
                    Json(json!({ "attempt": 1 })),
                )
            } else {
                (StatusCode::OK, Json(json!({ "attempt": 2 })))
            }
        }

        let attempts = Arc::new(AtomicUsize::new(0));
        let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
        let address = listener.local_addr().unwrap();
        let server_attempts = attempts.clone();
        let server = tokio::spawn(async move {
            axum::serve(
                listener,
                Router::new()
                    .route("/retry", any(flaky))
                    .with_state(server_attempts),
            )
            .await
            .unwrap();
        });
        let state = AppState::new(crate::Config::for_test(
            crate::GatewayMode::On,
            "http://127.0.0.1:9".to_owned(),
        ))
        .unwrap();
        let decision = crate::policy::PolicyDecision {
            upstream: Some(format!("http://{address}")),
            upstream_path: Some("/retry".to_owned()),
            retry_count: 1,
            request_timeout_ms: 1_000,
            ..Default::default()
        };
        let request = Request::builder()
            .uri("/api/rest/demo/v1/retry")
            .body(Body::empty())
            .unwrap();

        let response = execute_rest(&state, request, decision, DataPlaneProtocol::Rest)
            .await
            .unwrap();
        assert_eq!(response.status(), StatusCode::OK);
        assert_eq!(attempts.load(Ordering::SeqCst), 2);
        server.abort();
    }

    #[test]
    fn enforces_graphql_depth_while_ignoring_strings_and_comments() {
        let accepted = br##"{"query":"{ viewer { label(text: \"{ignored}\") # {ignored}\n } }"}"##;
        assert!(
            validate_protocol_request(DataPlaneProtocol::Graphql, &Method::POST, accepted, 2,)
                .is_ok()
        );

        let rejected = br#"{"query":"{ viewer { team { name } } }"}"#;
        let failure =
            validate_protocol_request(DataPlaneProtocol::Graphql, &Method::POST, rejected, 2)
                .unwrap_err();
        assert_eq!(failure.error_code, "GTW013");
    }

    #[test]
    fn rejects_unsafe_or_malformed_soap_envelopes() {
        let valid = br#"<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"><soap:Body/></soap:Envelope>"#;
        assert!(
            validate_protocol_request(DataPlaneProtocol::Soap, &Method::POST, valid, 0,).is_ok()
        );
        let unsafe_xml = br#"<!DOCTYPE x [<!ENTITY y SYSTEM "file:///etc/passwd">]><Envelope/>"#;
        assert!(
            validate_protocol_request(DataPlaneProtocol::Soap, &Method::POST, unsafe_xml, 0,)
                .is_err()
        );
    }

    #[test]
    fn validates_http_to_grpc_method_shape() {
        let valid = br#"{"method":"Greeter.SayHello","message":{"name":"Ada"}}"#;
        assert!(
            validate_protocol_request(DataPlaneProtocol::Grpc, &Method::POST, valid, 0,).is_ok()
        );
        let invalid = br#"{"method":"bad/method"}"#;
        assert!(
            validate_protocol_request(DataPlaneProtocol::Grpc, &Method::POST, invalid, 0,).is_err()
        );
    }

    #[test]
    fn validates_crud_schema_and_extracts_resource_ids() {
        let schema = json!({
            "name": { "type": "string", "required": true, "min_length": 2 },
            "count": { "type": "integer" },
            "profile": {
                "type": "object",
                "properties": { "enabled": { "type": "boolean", "required": true } }
            }
        });
        let valid = json!({ "name": "Ada", "count": 2, "profile": { "enabled": true } });
        assert!(validate_crud_schema(Some(&schema), &valid, false).is_ok());

        let missing = json!({ "count": 2 });
        assert!(validate_crud_schema(Some(&schema), &missing, false).is_err());
        assert!(validate_crud_schema(Some(&schema), &missing, true).is_ok());

        let wrong_type = json!({ "name": "Ada", "count": "two" });
        assert!(validate_crud_schema(Some(&schema), &wrong_type, false).is_err());
        assert_eq!(
            crud_resource_id("/api/rest/demo/v1/items/resource-1"),
            Some("resource-1")
        );
        assert_eq!(crud_resource_id("/api/rest/demo/v1/items"), None);
    }

    #[test]
    fn rejects_unsafe_crud_collection_names() {
        assert!(valid_collection_name("crud_data_accounts"));
        assert!(!valid_collection_name("system.users"));
        assert!(!valid_collection_name("../../users"));
    }
}
