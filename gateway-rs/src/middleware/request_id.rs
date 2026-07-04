use axum::{extract::Request, middleware::Next, response::Response};
use http::{HeaderValue, header::HeaderName};
use uuid::Uuid;

pub static REQUEST_ID: HeaderName = HeaderName::from_static("request_id");

#[derive(Clone, Debug)]
pub struct RequestId(pub String);

pub async fn request_id(mut request: Request, next: Next) -> Response {
    let id = request
        .headers()
        .get("x-request-id")
        .or_else(|| request.headers().get("request-id"))
        .and_then(|value| value.to_str().ok())
        .filter(|value| !value.is_empty())
        .map(str::to_owned)
        .unwrap_or_else(|| Uuid::new_v4().to_string());
    let value = HeaderValue::from_str(&id).unwrap_or_else(|_| HeaderValue::from_static("invalid"));

    request.headers_mut().insert("x-request-id", value.clone());
    request.extensions_mut().insert(RequestId(id));
    let mut response = next.run(request).await;
    response.headers_mut().insert("x-request-id", value.clone());
    response.headers_mut().insert(REQUEST_ID.clone(), value);
    response
}
