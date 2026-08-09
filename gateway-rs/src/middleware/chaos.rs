use std::sync::atomic::{AtomicBool, AtomicU32, AtomicU64, Ordering};
use std::time::Duration;
use axum::{
    extract::Request,
    middleware::Next,
    response::{IntoResponse, Response},
};
use http::StatusCode;

pub static CHAOS_ENABLED: AtomicBool = AtomicBool::new(false);
pub static CHAOS_LATENCY_MS: AtomicU64 = AtomicU64::new(0);
pub static CHAOS_ERROR_STATUS: AtomicU32 = AtomicU32::new(0);
pub static CHAOS_EVENTS_COUNT: AtomicU64 = AtomicU64::new(0);
pub static CHAOS_ERROR_BUDGET_BURN: AtomicU64 = AtomicU64::new(0);
pub static CHAOS_REDIS_OUTAGE: AtomicBool = AtomicBool::new(false);
pub static CHAOS_MONGO_OUTAGE: AtomicBool = AtomicBool::new(false);

pub async fn chaos_middleware(req: Request, next: Next) -> Response {
    if !CHAOS_ENABLED.load(Ordering::Relaxed) {
        return next.run(req).await;
    }

    CHAOS_EVENTS_COUNT.fetch_add(1, Ordering::Relaxed);

    let latency = CHAOS_LATENCY_MS.load(Ordering::Relaxed);
    if latency > 0 {
        tokio::time::sleep(Duration::from_millis(latency)).await;
    }

    let error_status = CHAOS_ERROR_STATUS.load(Ordering::Relaxed);
    if error_status >= 400 {
        let status = StatusCode::from_u16(error_status as u16)
            .unwrap_or(StatusCode::INTERNAL_SERVER_ERROR);
        return (status, "Chaos engineering fault injected").into_response();
    }

    next.run(req).await
}
