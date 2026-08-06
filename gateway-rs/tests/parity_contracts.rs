use std::{io::Read, path::PathBuf};

use axum::body::{Body, to_bytes};
use doorman_gateway::{AppState, Config, build_router, storage::models::PolicyDocuments};
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
        "rest_not_found",
    ] {
        let fixture = load_fixture(name);
        let expected = fixture.pointer("/expected/response").unwrap();
        let request_contract = fixture.get("request").unwrap();
        let method =
            Method::from_bytes(request_contract["method"].as_str().unwrap().as_bytes()).unwrap();
        let path = request_contract["path"].as_str().unwrap();
        let mut builder = Request::builder().method(method).uri(path);
        for (name, value) in request_contract["headers"].as_object().unwrap() {
            builder = builder.header(name, value.as_str().unwrap());
        }

        let state = if name == "rest_not_found" {
            AppState::new(Config::for_test("http://127.0.0.1:9".to_owned()))
                .unwrap()
                .with_policy_documents(PolicyDocuments {
                    apis: vec![json!({
                        "api_id": "parity-missing",
                        "api_name": "paritymissing",
                        "api_version": "v1",
                        "api_public": true,
                    })],
                    endpoints: vec![json!({
                        "api_name": "paritymissing",
                        "api_version": "v1",
                        "endpoint_method": "GET",
                        "client_uri": "/exists",
                        "endpoint_uri": "/exists",
                        "endpoint_servers": ["http://upstream.test"],
                    })],
                    ..Default::default()
                })
        } else {
            AppState::new(Config::for_test("http://127.0.0.1:9".to_owned())).unwrap()
        };
        let response = build_router(state)
            .oneshot(builder.body(Body::empty()).unwrap())
            .await
            .unwrap();
        let actual = response_contract(response).await;
        assert_eq!(
            &actual, expected,
            "Rust response drifted from Python contract fixture {name}"
        );
    }
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
    let body = if content_type == "application/json" {
        serde_json::from_slice(&decoded).unwrap()
    } else {
        Value::String(String::from_utf8_lossy(&decoded).into_owned())
    };
    json!({
        "status": status,
        "content_type": content_type,
        "headers": headers,
        "body": body,
    })
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
