use std::{io::Read, path::PathBuf, sync::Arc};

use axum::{
    Json, Router,
    body::{Body, to_bytes},
    extract::{Request as AxumRequest, State},
    response::IntoResponse,
    routing::any,
};
use doorman_gateway::{
    AppState, Config, build_router,
    storage::{models::PolicyDocuments, runtime::SharedStorage},
};
use flate2::read::GzDecoder;
use http::{Method, Request};
use serde_json::{Map, Value, json};
use tower::ServiceExt;

const REQUEST_ID_TOKEN: &str = "<request-id>";

#[tokio::test]
async fn rust_matches_checked_in_wire_contracts() {
    for name in [
        "health_public",
        "status_unauthorized",
        "gateway_caches_preflight",
        "rest_happy_path",
        "rest_not_found",
        "rest_request_id",
        "rest_round_robin_state",
        "rest_route_precedence",
    ] {
        let fixture = load_fixture(name);
        let expected = fixture
            .pointer("/approved_rust_divergence/rust_response")
            .or_else(|| fixture.pointer("/expected/response"))
            .unwrap();
        let request_contract = fixture.get("request").unwrap();
        let method =
            Method::from_bytes(request_contract["method"].as_str().unwrap().as_bytes()).unwrap();
        let path = request_contract["path"].as_str().unwrap();
        let (state, servers) = contract_state(name).await;
        let app = build_router(state.clone());
        let repeat = request_contract
            .get("repeat")
            .and_then(Value::as_u64)
            .unwrap_or(1);
        let mut response = None;
        for iteration in 0..repeat {
            let mut builder = Request::builder().method(method.clone()).uri(path);
            for (header_name, value) in request_contract["headers"].as_object().unwrap() {
                builder = builder.header(header_name, value.as_str().unwrap());
            }
            response = Some(
                app.clone()
                    .oneshot(builder.body(Body::empty()).unwrap())
                    .await
                    .unwrap(),
            );
            if name == "rest_round_robin_state" {
                let index = state
                    .storage
                    .as_ref()
                    .unwrap()
                    .current_routing_index("endpoint_server_cache:parityrr:GET:/rr")
                    .await
                    .unwrap();
                assert_eq!(index, (iteration as usize + 1) % 2);
            }
        }
        let response = response.unwrap();
        let actual = response_contract(response).await;
        assert_eq!(
            &actual, expected,
            "Rust response drifted from frozen contract fixture {name}"
        );
        for server in servers {
            server.abort();
        }
    }
}

#[derive(Clone)]
struct EchoConfig {
    public_url: &'static str,
    upstream_request_id: bool,
}

async fn echo_upstream(
    State(config): State<EchoConfig>,
    request: AxumRequest,
) -> axum::response::Response {
    let request_id = request
        .headers()
        .get("x-request-id")
        .and_then(|value| value.to_str().ok())
        .unwrap_or_default()
        .to_owned();
    let mut response = Json(json!({
        "ok": true,
        "method": request.method().as_str(),
        "url": config.public_url,
        "headers": {"x-request-id": request_id},
        "params": {},
        "body": null
    }))
    .into_response();
    if config.upstream_request_id {
        response.headers_mut().insert(
            "x-upstream-request-id",
            http::HeaderValue::from_str(&request_id).unwrap(),
        );
    }
    response
}

async fn spawn_upstream(
    public_url: &'static str,
    upstream_request_id: bool,
) -> (String, tokio::task::JoinHandle<()>) {
    let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
    let address = listener.local_addr().unwrap();
    let app = Router::new()
        .fallback(any(echo_upstream))
        .with_state(EchoConfig {
            public_url,
            upstream_request_id,
        });
    let server = tokio::spawn(async move { axum::serve(listener, app).await.unwrap() });
    (format!("http://{address}"), server)
}

async fn contract_state(name: &str) -> (AppState, Vec<tokio::task::JoinHandle<()>>) {
    let config = Config::for_test("http://127.0.0.1:9".to_owned());
    let mut servers = Vec::new();
    let documents = match name {
        "rest_happy_path" | "rest_request_id" => {
            let public_url = if name == "rest_happy_path" {
                "http://upstream.test/hello"
            } else {
                "http://upstream.test/echo"
            };
            let uri = if name == "rest_happy_path" {
                "/hello"
            } else {
                "/echo"
            };
            let api_name = if name == "rest_happy_path" {
                "parityhappy"
            } else {
                "parityrid"
            };
            let (upstream, server) = spawn_upstream(public_url, name == "rest_request_id").await;
            servers.push(server);
            PolicyDocuments {
                apis: vec![json!({
                    "api_id": api_name,
                    "api_name": api_name,
                    "api_version": "v1",
                    "api_public": true,
                    "api_allowed_headers": ["X-Upstream-Request-ID"]
                })],
                endpoints: vec![json!({
                    "api_name": api_name,
                    "api_version": "v1",
                    "endpoint_method": "GET",
                    "client_uri": uri,
                    "endpoint_uri": uri,
                    "endpoint_servers": [upstream]
                })],
                ..Default::default()
            }
        }
        "rest_round_robin_state" => {
            let (first, first_server) = spawn_upstream("http://rr-a/rr", false).await;
            let (second, second_server) = spawn_upstream("http://rr-b/rr", false).await;
            servers.extend([first_server, second_server]);
            PolicyDocuments {
                apis: vec![json!({
                    "api_id": "parityrr",
                    "api_name": "parityrr",
                    "api_version": "v1",
                    "api_public": true
                })],
                endpoints: vec![json!({
                    "api_name": "parityrr",
                    "api_version": "v1",
                    "endpoint_method": "GET",
                    "client_uri": "/rr",
                    "endpoint_uri": "/rr",
                    "endpoint_servers": [first, second]
                })],
                ..Default::default()
            }
        }
        "rest_route_precedence" => {
            let (endpoint, endpoint_server) = spawn_upstream("http://ep-a/ping", false).await;
            let (routing, routing_server) = spawn_upstream("http://route-a/ping", false).await;
            servers.extend([endpoint_server, routing_server]);
            PolicyDocuments {
                apis: vec![json!({
                    "api_id": "parityroute",
                    "api_name": "parityroute",
                    "api_version": "v1",
                    "api_public": true
                })],
                endpoints: vec![json!({
                    "api_name": "parityroute",
                    "api_version": "v1",
                    "endpoint_method": "GET",
                    "client_uri": "/ping",
                    "endpoint_uri": "/ping",
                    "endpoint_servers": [endpoint]
                })],
                routings: vec![json!({
                    "client_key": "contract-client",
                    "routing_servers": [routing],
                    "server_index": 0
                })],
                ..Default::default()
            }
        }
        "rest_not_found" => PolicyDocuments {
            apis: vec![json!({
                "api_id": "parity-missing",
                "api_name": "paritymissing",
                "api_version": "v1",
                "api_public": true
            })],
            endpoints: vec![json!({
                "api_name": "paritymissing",
                "api_version": "v1",
                "endpoint_method": "GET",
                "client_uri": "/exists",
                "endpoint_uri": "/exists",
                "endpoint_servers": ["http://upstream.test"]
            })],
            ..Default::default()
        },
        _ => PolicyDocuments::default(),
    };
    let storage = SharedStorage::connect(&config.shared_storage)
        .await
        .unwrap();
    let mut state = AppState::new(config)
        .unwrap()
        .with_policy_documents(documents);
    state.storage = Some(Arc::new(storage));
    (state, servers)
}

async fn response_contract(response: axum::response::Response) -> Value {
    let status = response.status().as_u16();
    let content_type = response
        .headers()
        .get("content-type")
        .and_then(|value| value.to_str().ok())
        .unwrap_or_default()
        .split(';')
        .next()
        .unwrap_or_default()
        .to_owned();
    let headers = normalize_headers(response.headers());
    let gzip = response
        .headers()
        .get("content-encoding")
        .is_some_and(|value| value == "gzip");
    let bytes = to_bytes(response.into_body(), 1024 * 1024).await.unwrap();
    let decoded = if gzip {
        let mut output = Vec::new();
        GzDecoder::new(bytes.as_ref())
            .read_to_end(&mut output)
            .unwrap();
        output
    } else {
        bytes.to_vec()
    };
    let mut body = if content_type == "application/json" {
        serde_json::from_slice(&decoded).unwrap()
    } else {
        Value::String(String::from_utf8_lossy(&decoded).into_owned())
    };
    normalize_volatile_values(&mut body, None);
    json!({
        "status": status,
        "content_type": content_type,
        "headers": headers,
        "body": body,
    })
}

fn normalize_volatile_values(value: &mut Value, key: Option<&str>) {
    if key.is_some_and(|key| {
        matches!(
            key.to_ascii_lowercase().as_str(),
            "request_id" | "x-request-id" | "x-upstream-request-id"
        )
    }) {
        *value = Value::String(REQUEST_ID_TOKEN.to_owned());
        return;
    }
    match value {
        Value::Object(values) => {
            for (key, value) in values {
                normalize_volatile_values(value, Some(key));
            }
        }
        Value::Array(values) => {
            for value in values {
                normalize_volatile_values(value, None);
            }
        }
        _ => {}
    }
}

fn normalize_headers(headers: &http::HeaderMap) -> Value {
    let mut output = Map::new();
    for name in [
        "access-control-allow-credentials",
        "access-control-allow-headers",
        "access-control-allow-methods",
        "access-control-allow-origin",
        "content-encoding",
        "content-type",
        "request_id",
        "vary",
        "x-request-id",
        "x-upstream-request-id",
    ] {
        let Some(value) = headers.get(name).and_then(|value| value.to_str().ok()) else {
            continue;
        };
        let normalized = if matches!(
            name,
            "request_id" | "x-request-id" | "x-upstream-request-id"
        ) {
            REQUEST_ID_TOKEN.to_owned()
        } else if name == "vary" {
            value
                .split(',')
                .map(str::trim)
                .map(str::to_ascii_lowercase)
                .collect::<Vec<_>>()
                .join(", ")
        } else {
            value.to_owned()
        };
        output.insert(name.to_owned(), Value::String(normalized));
    }
    Value::Object(output)
}

fn load_fixture(name: &str) -> Value {
    let path = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("../parity/contracts/fixtures")
        .join(format!("{name}.json"));
    serde_json::from_slice(&std::fs::read(path).unwrap()).unwrap()
}
