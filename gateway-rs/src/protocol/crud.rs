use axum::{
    Json,
    body::to_bytes,
    extract::Request,
    response::{IntoResponse, Response},
};
use base64::Engine;
use http::{StatusCode, header};
use prost::Message;
use regex::Regex;
use serde_json::Value;

use crate::{
    error::GatewayError,
    middleware::body_limit::BodyLimits,
    policy::{PolicyDecision, PolicyErrorBody},
    routes::rest::{DataPlaneProtocol, graphql_depth, valid_collection_name, validate_crud_schema},
    state::AppState,
    storage::runtime::StorageError,
};

#[derive(Clone, PartialEq, Message)]
struct CrudGrpcRequest {
    #[prost(string, tag = "1")]
    id: String,
    #[prost(string, tag = "2")]
    input: String,
}

#[derive(Clone, PartialEq, Message)]
struct CrudGrpcReply {
    #[prost(string, tag = "1")]
    result: String,
    #[prost(bool, tag = "2")]
    ok: bool,
}

pub async fn execute(
    state: &AppState,
    request: Request,
    decision: &PolicyDecision,
    protocol: DataPlaneProtocol,
) -> Result<Response, GatewayError> {
    if state.storage.is_none() {
        return Ok(policy_error(
            StatusCode::SERVICE_UNAVAILABLE,
            "GTW006",
            "Gateway state store unavailable",
        ));
    }
    let query = request.uri().query().unwrap_or_default().to_owned();
    let grpc_web_target = request
        .extensions()
        .get::<crate::routes::grpc_web::GrpcWebTarget>()
        .cloned();
    let content_type = request
        .headers()
        .get(header::CONTENT_TYPE)
        .and_then(|value| value.to_str().ok())
        .unwrap_or_default()
        .to_ascii_lowercase();
    let (_, body) = request.into_parts();
    let limit = match protocol {
        DataPlaneProtocol::Graphql => BodyLimits::from_env().graphql,
        DataPlaneProtocol::Soap => BodyLimits::from_env().soap,
        DataPlaneProtocol::Grpc | DataPlaneProtocol::GrpcWeb => BodyLimits::from_env().grpc,
        DataPlaneProtocol::Rest => BodyLimits::from_env().rest,
    };
    let body = match to_bytes(body, limit).await {
        Ok(body) => body,
        Err(_) => {
            return Ok(policy_error(
                StatusCode::PAYLOAD_TOO_LARGE,
                "GTW013",
                "Request body too large",
            ));
        }
    };
    let response = match protocol {
        DataPlaneProtocol::Graphql => execute_graphql(state, decision, &body).await,
        DataPlaneProtocol::Soap => execute_soap(state, decision, &query, &body).await,
        DataPlaneProtocol::Grpc => execute_grpc(state, decision, &query, &body).await,
        DataPlaneProtocol::GrpcWeb => {
            execute_grpc_web(
                state,
                decision,
                grpc_web_target.as_ref(),
                &content_type,
                &body,
            )
            .await
        }
        DataPlaneProtocol::Rest => Ok(policy_error(
            StatusCode::NOT_IMPLEMENTED,
            "CRUD501",
            "CRUD is not supported for this protocol",
        )),
    };
    Ok(match response {
        Ok(response) => response,
        Err(StorageError::InvalidDocument(error)) => {
            if protocol == DataPlaneProtocol::GrpcWeb {
                crate::protocol::grpc::web_trailer_response(
                    content_type.starts_with("application/grpc-web-text"),
                    tonic::Code::InvalidArgument,
                    &error,
                )
            } else {
                protocol_error(protocol, StatusCode::BAD_REQUEST, "CRUD400", &error)
            }
        }
        Err(error) => {
            tracing::error!(error = %error, "protocol CRUD storage operation failed");
            if protocol == DataPlaneProtocol::GrpcWeb {
                crate::protocol::grpc::web_trailer_response(
                    content_type.starts_with("application/grpc-web-text"),
                    tonic::Code::Unavailable,
                    "Gateway state store unavailable",
                )
            } else {
                policy_error(
                    StatusCode::SERVICE_UNAVAILABLE,
                    "GTW006",
                    "Gateway state store unavailable",
                )
            }
        }
    })
}

async fn execute_grpc_web(
    state: &AppState,
    decision: &PolicyDecision,
    target: Option<&crate::routes::grpc_web::GrpcWebTarget>,
    content_type: &str,
    body: &[u8],
) -> Result<Response, StorageError> {
    let text_mode = content_type.starts_with("application/grpc-web-text");
    if !content_type.starts_with("application/grpc-web") {
        return Ok((StatusCode::UNSUPPORTED_MEDIA_TYPE, "Invalid Content-Type").into_response());
    }
    if !decision.grpc_web_enabled {
        return Ok(crate::protocol::grpc::web_trailer_response(
            text_mode,
            tonic::Code::PermissionDenied,
            "gRPC-Web disabled",
        ));
    }
    let target = target
        .ok_or_else(|| StorageError::InvalidDocument("Invalid gRPC-Web CRUD target".to_owned()))?;
    if target
        .service
        .rsplit('.')
        .next()
        .is_none_or(|name| name != "CrudService")
    {
        return Ok(crate::protocol::grpc::web_trailer_response(
            text_mode,
            tonic::Code::Unimplemented,
            "CRUD service not found",
        ));
    }
    let raw = if text_mode {
        let compact = body
            .iter()
            .copied()
            .filter(|byte| !byte.is_ascii_whitespace())
            .collect::<Vec<_>>();
        base64::engine::general_purpose::STANDARD
            .decode(compact)
            .map_err(|_| StorageError::InvalidDocument("Invalid base64 body".to_owned()))?
    } else {
        body.to_vec()
    };
    let payload = crate::protocol::grpc::decode_web_data_frame(&raw)
        .map_err(|message| StorageError::InvalidDocument(message.to_owned()))?;
    let request = CrudGrpcRequest::decode(payload.as_slice())
        .map_err(|_| StorageError::InvalidDocument("Invalid protobuf request".to_owned()))?;
    let (storage, collection) = storage_collection(state, decision)?;
    let reply = match target.method.as_str() {
        "ListItems" | "List" => CrudGrpcReply {
            result: serde_json::to_string(&storage.crud_list(collection).await?)?,
            ok: true,
        },
        "GetItem" | "Read" => {
            if request.id.is_empty() {
                return Err(StorageError::InvalidDocument("id is required".to_owned()));
            }
            let value = storage.crud_find_one(collection, &request.id).await?;
            CrudGrpcReply {
                result: serde_json::to_string(&value.clone().unwrap_or(Value::Null))?,
                ok: value.is_some(),
            }
        }
        "CreateItem" | "Create" => {
            let mut input: Value = serde_json::from_str(&request.input)?;
            validate_crud_schema(decision.crud_schema.as_ref(), &input, false)?;
            if input.get("_id").is_none() {
                input["_id"] = Value::String(uuid::Uuid::new_v4().to_string());
            }
            storage.crud_insert(collection, &input).await?;
            CrudGrpcReply {
                result: serde_json::to_string(&input)?,
                ok: true,
            }
        }
        "UpdateItem" | "Update" => {
            if request.id.is_empty() {
                return Err(StorageError::InvalidDocument("id is required".to_owned()));
            }
            let input: Value = serde_json::from_str(&request.input)?;
            validate_crud_schema(decision.crud_schema.as_ref(), &input, true)?;
            let value = storage.crud_update(collection, &request.id, &input).await?;
            CrudGrpcReply {
                result: serde_json::to_string(&value.clone().unwrap_or(Value::Null))?,
                ok: value.is_some(),
            }
        }
        "DeleteItem" | "Delete" => CrudGrpcReply {
            result: String::new(),
            ok: if request.id.is_empty() {
                return Err(StorageError::InvalidDocument("id is required".to_owned()));
            } else {
                storage.crud_delete(collection, &request.id).await?
            },
        },
        _ => {
            return Ok(crate::protocol::grpc::web_trailer_response(
                text_mode,
                tonic::Code::Unimplemented,
                "Unknown gRPC CRUD operation",
            ));
        }
    };
    let mut framed = crate::protocol::grpc::web_data_frame(&reply.encode_to_vec());
    let trailer = b"grpc-status: 0\r\ngrpc-message: \r\n";
    framed.push(0x80);
    framed.extend((trailer.len() as u32).to_be_bytes());
    framed.extend(trailer);
    Ok(crate::protocol::grpc::web_body_response(text_mode, framed))
}

async fn execute_graphql(
    state: &AppState,
    decision: &PolicyDecision,
    body: &[u8],
) -> Result<Response, StorageError> {
    let document: Value = serde_json::from_slice(body)
        .map_err(|error| StorageError::InvalidDocument(error.to_string()))?;
    let query = document
        .get("query")
        .and_then(Value::as_str)
        .unwrap_or_default();
    let variables = document
        .get("variables")
        .and_then(Value::as_object)
        .cloned()
        .unwrap_or_default();
    let depth = graphql_depth(query)
        .ok_or_else(|| StorageError::InvalidDocument("Invalid GraphQL query".to_owned()))?;
    if decision.graphql_max_depth > 0 && depth > decision.graphql_max_depth {
        return Err(StorageError::InvalidDocument(format!(
            "Query depth {depth} exceeds maximum allowed depth of {}",
            decision.graphql_max_depth
        )));
    }
    if let Some(schema) = decision.endpoint_validation.as_ref() {
        crate::validation::json::validate_json(&Value::Object(variables.clone()), schema)
            .map_err(|error| StorageError::InvalidDocument(error.to_owned()))?;
    }
    let (storage, collection) = storage_collection(state, decision)?;
    let (field, value) = if has_operation(query, "listItems") {
        (
            "listItems",
            Value::Array(storage.crud_list(collection).await?),
        )
    } else if has_operation(query, "getItem") {
        let id = variable_string(&variables, "id")?;
        (
            "getItem",
            storage
                .crud_find_one(collection, id)
                .await?
                .unwrap_or(Value::Null),
        )
    } else if has_operation(query, "createItem") {
        let mut input = variable_object(&variables, "input")?;
        validate_crud_schema(decision.crud_schema.as_ref(), &input, false)?;
        if input.get("_id").is_none() {
            input["_id"] = Value::String(uuid::Uuid::new_v4().to_string());
        }
        storage.crud_insert(collection, &input).await?;
        ("createItem", input)
    } else if has_operation(query, "updateItem") {
        let id = variable_string(&variables, "id")?;
        let input = variable_object(&variables, "input")?;
        validate_crud_schema(decision.crud_schema.as_ref(), &input, true)?;
        (
            "updateItem",
            storage
                .crud_update(collection, id, &input)
                .await?
                .unwrap_or(Value::Null),
        )
    } else if has_operation(query, "deleteItem") {
        let id = variable_string(&variables, "id")?;
        (
            "deleteItem",
            Value::Bool(storage.crud_delete(collection, id).await?),
        )
    } else {
        return Err(StorageError::InvalidDocument(
            "Unknown GraphQL CRUD operation".to_owned(),
        ));
    };
    Ok(Json(serde_json::json!({ "data": { field: value } })).into_response())
}

async fn execute_soap(
    state: &AppState,
    decision: &PolicyDecision,
    query: &str,
    body: &[u8],
) -> Result<Response, StorageError> {
    if query
        .split('&')
        .any(|part| part.eq_ignore_ascii_case("wsdl"))
    {
        return Ok(xml_response(StatusCode::OK, soap_wsdl(decision)));
    }
    let xml = std::str::from_utf8(body)
        .map_err(|error| StorageError::InvalidDocument(error.to_string()))?;
    let lower = xml.to_ascii_lowercase();
    if lower.contains("<!doctype") || lower.contains("<!entity") {
        return Err(StorageError::InvalidDocument(
            "XML DTD/entities are not allowed".to_owned(),
        ));
    }
    if !(lower.contains(":envelope") || lower.contains("<envelope"))
        || !(lower.contains("http://schemas.xmlsoap.org/soap/envelope/")
            || lower.contains("http://www.w3.org/2003/05/soap-envelope"))
        || !(lower.contains(":body") || lower.contains("<body"))
    {
        return Err(StorageError::InvalidDocument(
            "Invalid SOAP envelope".to_owned(),
        ));
    }
    let operation = Regex::new(
        r"(?s)<(?:[A-Za-z_][A-Za-z0-9_.-]*:)?(createItem|listItems|getItem|updateItem|deleteItem)\b",
    )
    .expect("static SOAP operation regex")
    .captures(xml)
    .and_then(|captures| captures.get(1))
    .map(|value| value.as_str())
    .ok_or_else(|| StorageError::InvalidDocument("Unknown SOAP CRUD operation".to_owned()))?;
    let (storage, collection) = storage_collection(state, decision)?;
    let result = match operation {
        "listItems" => Value::Array(storage.crud_list(collection).await?),
        "getItem" => {
            let id = xml_element(xml, "id")?;
            storage
                .crud_find_one(collection, &id)
                .await?
                .unwrap_or(Value::Null)
        }
        "createItem" => {
            let input = xml_element(xml, "input")?;
            let mut input: Value = serde_json::from_str(&xml_unescape(&input))?;
            validate_crud_schema(decision.crud_schema.as_ref(), &input, false)?;
            if input.get("_id").is_none() {
                input["_id"] = Value::String(uuid::Uuid::new_v4().to_string());
            }
            storage.crud_insert(collection, &input).await?;
            input
        }
        "updateItem" => {
            let id = xml_element(xml, "id")?;
            let input = xml_element(xml, "input")?;
            let input: Value = serde_json::from_str(&xml_unescape(&input))?;
            validate_crud_schema(decision.crud_schema.as_ref(), &input, true)?;
            storage
                .crud_update(collection, &id, &input)
                .await?
                .unwrap_or(Value::Null)
        }
        "deleteItem" => {
            let id = xml_element(xml, "id")?;
            Value::Bool(storage.crud_delete(collection, &id).await?)
        }
        _ => unreachable!(),
    };
    let response_tag = format!("{operation}Response");
    let json = serde_json::to_string(&result)?;
    Ok(xml_response(
        StatusCode::OK,
        format!(
            "<?xml version=\"1.0\" encoding=\"UTF-8\"?><soap:Envelope xmlns:soap=\"http://schemas.xmlsoap.org/soap/envelope/\"><soap:Body><tns:{response_tag} xmlns:tns=\"http://doorman.dev/crud\"><tns:result>{}</tns:result></tns:{response_tag}></soap:Body></soap:Envelope>",
            xml_escape(&json)
        ),
    ))
}

async fn execute_grpc(
    state: &AppState,
    decision: &PolicyDecision,
    query: &str,
    body: &[u8],
) -> Result<Response, StorageError> {
    if query
        .split('&')
        .any(|part| part.eq_ignore_ascii_case("proto"))
    {
        return Ok((
            StatusCode::OK,
            [(header::CONTENT_TYPE, "text/plain")],
            crud_proto(decision),
        )
            .into_response());
    }
    let document: Value = serde_json::from_slice(body)?;
    let method = document
        .get("method")
        .and_then(Value::as_str)
        .and_then(|method| method.rsplit('.').next())
        .unwrap_or_default();
    let message = document.get("message").cloned().unwrap_or(Value::Null);
    let (storage, collection) = storage_collection(state, decision)?;
    let result = match method {
        "ListItems" | "List" => {
            serde_json::json!({ "items": storage.crud_list(collection).await? })
        }
        "GetItem" | "Read" => {
            let id = message
                .get("id")
                .and_then(Value::as_str)
                .ok_or_else(|| StorageError::InvalidDocument("id is required".to_owned()))?;
            storage
                .crud_find_one(collection, id)
                .await?
                .unwrap_or(Value::Null)
        }
        "CreateItem" | "Create" => {
            let mut input = message.get("input").cloned().unwrap_or(message);
            validate_crud_schema(decision.crud_schema.as_ref(), &input, false)?;
            if input.get("_id").is_none() {
                input["_id"] = Value::String(uuid::Uuid::new_v4().to_string());
            }
            storage.crud_insert(collection, &input).await?;
            input
        }
        "UpdateItem" | "Update" => {
            let id = message
                .get("id")
                .and_then(Value::as_str)
                .ok_or_else(|| StorageError::InvalidDocument("id is required".to_owned()))?;
            let input = message
                .get("input")
                .cloned()
                .unwrap_or_else(|| message.clone());
            validate_crud_schema(decision.crud_schema.as_ref(), &input, true)?;
            storage
                .crud_update(collection, id, &input)
                .await?
                .unwrap_or(Value::Null)
        }
        "DeleteItem" | "Delete" => {
            let id = message
                .get("id")
                .and_then(Value::as_str)
                .ok_or_else(|| StorageError::InvalidDocument("id is required".to_owned()))?;
            serde_json::json!({ "ok": storage.crud_delete(collection, id).await? })
        }
        _ => {
            return Err(StorageError::InvalidDocument(
                "Unknown gRPC CRUD operation".to_owned(),
            ));
        }
    };
    Ok(Json(result).into_response())
}

fn storage_collection<'a>(
    state: &'a AppState,
    decision: &'a PolicyDecision,
) -> Result<(&'a crate::storage::runtime::SharedStorage, &'a str), StorageError> {
    let storage = state.storage.as_deref().ok_or_else(|| {
        StorageError::InvalidDocument("Gateway state store unavailable".to_owned())
    })?;
    let collection = decision
        .crud_collection
        .as_deref()
        .filter(|name| valid_collection_name(name))
        .ok_or_else(|| {
            StorageError::InvalidDocument("CRUD collection is not configured".to_owned())
        })?;
    Ok((storage, collection))
}

fn has_operation(query: &str, operation: &str) -> bool {
    Regex::new(&format!(r"\b{}\b", regex::escape(operation)))
        .is_ok_and(|regex| regex.is_match(query))
}

fn variable_string<'a>(
    variables: &'a serde_json::Map<String, Value>,
    name: &str,
) -> Result<&'a str, StorageError> {
    variables
        .get(name)
        .and_then(Value::as_str)
        .ok_or_else(|| StorageError::InvalidDocument(format!("Variable '{name}' is required")))
}

fn variable_object(
    variables: &serde_json::Map<String, Value>,
    name: &str,
) -> Result<Value, StorageError> {
    variables
        .get(name)
        .filter(|value| value.is_object())
        .cloned()
        .ok_or_else(|| {
            StorageError::InvalidDocument(format!("Variable '{name}' must be an object"))
        })
}

fn xml_element(xml: &str, name: &str) -> Result<String, StorageError> {
    Regex::new(&format!(
        r"(?s)<(?:[A-Za-z_][A-Za-z0-9_.-]*:)?{0}\b[^>]*>(.*?)</(?:[A-Za-z_][A-Za-z0-9_.-]*:)?{0}\s*>",
        regex::escape(name)
    ))
    .expect("escaped XML element regex")
    .captures(xml)
    .and_then(|captures| captures.get(1))
    .map(|value| value.as_str().trim().to_owned())
    .ok_or_else(|| StorageError::InvalidDocument(format!("Missing {name} element")))
}

fn xml_escape(value: &str) -> String {
    value
        .replace('&', "&amp;")
        .replace('<', "&lt;")
        .replace('>', "&gt;")
        .replace('"', "&quot;")
        .replace('\'', "&apos;")
}

fn xml_unescape(value: &str) -> String {
    value
        .replace("&quot;", "\"")
        .replace("&apos;", "'")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&amp;", "&")
}

fn xml_response(status: StatusCode, body: String) -> Response {
    (
        status,
        [(header::CONTENT_TYPE, "text/xml; charset=utf-8")],
        body,
    )
        .into_response()
}

fn soap_wsdl(decision: &PolicyDecision) -> String {
    let name = xml_escape(decision.api_name.as_deref().unwrap_or("Crud"));
    format!(
        "<?xml version=\"1.0\"?><definitions xmlns=\"http://schemas.xmlsoap.org/wsdl/\" xmlns:soap=\"http://schemas.xmlsoap.org/wsdl/soap/\" name=\"{name}Service\"><portType name=\"{name}PortType\"><operation name=\"createItem\"/><operation name=\"listItems\"/><operation name=\"getItem\"/><operation name=\"updateItem\"/><operation name=\"deleteItem\"/></portType></definitions>"
    )
}

fn crud_proto(decision: &PolicyDecision) -> String {
    let mut package = decision
        .api_name
        .as_deref()
        .unwrap_or("crud")
        .chars()
        .map(|character| {
            if character.is_ascii_alphanumeric() || character == '_' {
                character
            } else {
                '_'
            }
        })
        .collect::<String>();
    if package.is_empty() {
        package.push_str("crud");
    } else if package.starts_with(|character: char| character.is_ascii_digit()) {
        package.insert(0, '_');
    }
    format!(
        "syntax = \"proto3\";\npackage {package};\nservice CrudService {{ rpc CreateItem (CrudRequest) returns (CrudReply); rpc ListItems (CrudRequest) returns (CrudReply); rpc GetItem (CrudRequest) returns (CrudReply); rpc UpdateItem (CrudRequest) returns (CrudReply); rpc DeleteItem (CrudRequest) returns (CrudReply); }}\nmessage CrudRequest {{ string id = 1; string input = 2; }}\nmessage CrudReply {{ string result = 1; bool ok = 2; }}\n"
    )
}

fn protocol_error(
    protocol: DataPlaneProtocol,
    status: StatusCode,
    code: &str,
    message: &str,
) -> Response {
    match protocol {
        DataPlaneProtocol::Graphql => {
            Json(serde_json::json!({ "errors": [{ "message": message, "code": code }] }))
                .into_response()
        }
        DataPlaneProtocol::Soap => xml_response(
            status,
            format!(
                "<?xml version=\"1.0\"?><soap:Envelope xmlns:soap=\"http://schemas.xmlsoap.org/soap/envelope/\"><soap:Body><soap:Fault><faultcode>{code}</faultcode><faultstring>{}</faultstring></soap:Fault></soap:Body></soap:Envelope>",
                xml_escape(message)
            ),
        ),
        _ => policy_error(status, code, message),
    }
}

fn policy_error(status: StatusCode, code: &str, message: &str) -> Response {
    (
        status,
        Json(PolicyErrorBody {
            error_code: code.to_owned(),
            error_message: message.to_owned(),
        }),
    )
        .into_response()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn discovers_all_crud_operations() {
        let decision = PolicyDecision {
            api_name: Some("customer-api".to_owned()),
            ..Default::default()
        };
        let wsdl = soap_wsdl(&decision);
        let proto = crud_proto(&decision);
        for operation in [
            "createItem",
            "listItems",
            "getItem",
            "updateItem",
            "deleteItem",
        ] {
            assert!(wsdl.contains(operation));
        }
        for operation in [
            "CreateItem",
            "ListItems",
            "GetItem",
            "UpdateItem",
            "DeleteItem",
        ] {
            assert!(proto.contains(operation));
        }
        assert!(proto.contains("package customer_api;"));
    }

    #[test]
    fn escapes_or_sanitizes_api_names_in_discovery_documents() {
        let decision = PolicyDecision {
            api_name: Some("9<&bad-name".to_owned()),
            ..Default::default()
        };
        assert!(soap_wsdl(&decision).contains("9&lt;&amp;bad-nameService"));
        assert!(crud_proto(&decision).contains("package _9__bad_name;"));
    }
}
