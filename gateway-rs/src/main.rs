use std::{
    env,
    path::PathBuf,
    sync::{Arc, atomic::Ordering},
    time::Duration,
};

use doorman_gateway::{
    AppState, Config, build_router,
    observability::analytics_aggregator::global_analytics,
    state::GatewayRuntime,
    storage::{runtime::SharedStorage, snapshot},
};
use tokio::net::TcpListener;
use tracing::{error, info, warn};

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    doorman_gateway::observability::init();
    restore_metrics();

    let config = Config::from_env()?;
    let bind_addr = config.bind_addr();
    let state = AppState::from_config(config).await?;
    let storage = state.storage.clone();
    spawn_metrics_autosave(state.runtime.clone());

    if let Some(storage) = storage.as_ref().filter(|storage| storage.is_memory()) {
        match snapshot::restore(storage, None).await {
            Ok((version, created_at)) => info!(version, created_at, "restored memory snapshot"),
            Err(snapshot::SnapshotError::Io(error_value))
                if error_value.kind() == std::io::ErrorKind::NotFound =>
            {
                info!("no existing memory snapshot found")
            }
            Err(snapshot::SnapshotError::MissingKey) => {
                warn!("MEM_ENCRYPTION_KEY is not configured; restore and autosave are disabled")
            }
            Err(error_value) => {
                error!(error = %error_value, "memory snapshot restore failed; refusing to start with empty state");
                return Err(error_value.into());
            }
        }
        spawn_memory_autosave(storage.clone(), state.runtime.clone());
        spawn_sigusr1_dump(storage.clone());
    }

    let app = build_router(state);
    let listener = TcpListener::bind(&bind_addr).await?;

    info!(address = %bind_addr, "Doorman Rust gateway listening");
    axum::serve(
        listener,
        app.into_make_service_with_connect_info::<std::net::SocketAddr>(),
    )
    .with_graceful_shutdown(shutdown_signal(storage))
    .await?;
    Ok(())
}

fn spawn_memory_autosave(storage: Arc<SharedStorage>, runtime: Arc<GatewayRuntime>) {
    if !env_bool("MEM_AUTO_SAVE_ENABLED", true) || env::var("MEM_ENCRYPTION_KEY").is_err() {
        return;
    }
    let seconds = env::var("MEM_AUTO_SAVE_FREQ")
        .ok()
        .and_then(|value| value.parse::<u64>().ok())
        .unwrap_or(300)
        .max(1);
    tokio::spawn(async move {
        let mut interval = tokio::time::interval(Duration::from_secs(seconds));
        interval.tick().await;
        loop {
            interval.tick().await;
            match snapshot::dump(&storage, None).await {
                Ok(path) => {
                    runtime
                        .memory_snapshot_healthy
                        .store(true, Ordering::Relaxed);
                    info!(path = %path.display(), "memory autosave completed");
                }
                Err(error_value) => {
                    runtime
                        .memory_snapshot_healthy
                        .store(false, Ordering::Relaxed);
                    error!(error = %error_value, "memory autosave failed");
                }
            }
        }
    });
}

#[cfg(unix)]
fn spawn_sigusr1_dump(storage: Arc<SharedStorage>) {
    tokio::spawn(async move {
        let mut signal =
            match tokio::signal::unix::signal(tokio::signal::unix::SignalKind::user_defined1()) {
                Ok(signal) => signal,
                Err(error_value) => {
                    warn!(error = %error_value, "failed to register SIGUSR1 memory dump handler");
                    return;
                }
            };
        while signal.recv().await.is_some() {
            match snapshot::dump(&storage, None).await {
                Ok(path) => info!(path = %path.display(), "SIGUSR1 memory dump completed"),
                Err(error_value) => error!(error = %error_value, "SIGUSR1 memory dump failed"),
            }
        }
    });
}

#[cfg(not(unix))]
fn spawn_sigusr1_dump(_storage: Arc<SharedStorage>) {}

async fn shutdown_signal(storage: Option<Arc<SharedStorage>>) {
    let ctrl_c = async {
        tokio::signal::ctrl_c()
            .await
            .expect("failed to install Ctrl+C handler");
    };

    #[cfg(unix)]
    let terminate = async {
        tokio::signal::unix::signal(tokio::signal::unix::SignalKind::terminate())
            .expect("failed to install SIGTERM handler")
            .recv()
            .await;
    };

    #[cfg(not(unix))]
    let terminate = std::future::pending::<()>();

    tokio::select! {
        () = ctrl_c => {},
        () = terminate => {},
    }

    if let Some(storage) = storage.filter(|storage| storage.is_memory()) {
        match snapshot::dump(&storage, None).await {
            Ok(path) => info!(path = %path.display(), "shutdown memory dump completed"),
            Err(snapshot::SnapshotError::MissingKey) => {}
            Err(error_value) => error!(error = %error_value, "shutdown memory dump failed"),
        }
    }
    persist_metrics();
}

fn metrics_paths() -> [PathBuf; 2] {
    let directory = env::var_os("LOGS_DIR")
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from("platform-logs"));
    [
        directory.join("enhanced_metrics.json"),
        directory.join("metrics.json"),
    ]
}

fn restore_metrics() {
    for path in metrics_paths() {
        if !path.exists() {
            continue;
        }
        match global_analytics().load_from_file(&path) {
            Ok(()) => {
                info!(path = %path.display(), "restored gateway metrics");
                return;
            }
            Err(error_value) => {
                warn!(path = %path.display(), error = %error_value, "gateway metrics restore skipped");
            }
        }
    }
}

fn persist_metrics() -> bool {
    let mut persisted = true;
    for path in metrics_paths() {
        if let Err(error_value) = global_analytics().save_to_file(&path) {
            persisted = false;
            warn!(path = %path.display(), error = %error_value, "gateway metrics persistence failed");
        }
    }
    persisted
}

fn spawn_metrics_autosave(runtime: Arc<GatewayRuntime>) {
    let seconds = env::var("METRICS_SAVE_INTERVAL")
        .ok()
        .and_then(|value| value.parse::<u64>().ok())
        .unwrap_or(60)
        .max(1);
    tokio::spawn(async move {
        let mut interval = tokio::time::interval(Duration::from_secs(seconds));
        interval.tick().await;
        loop {
            interval.tick().await;
            runtime
                .metrics_persistence_healthy
                .store(persist_metrics(), Ordering::Relaxed);
        }
    });
}

fn env_bool(name: &str, default: bool) -> bool {
    env::var(name)
        .ok()
        .map(|value| {
            matches!(
                value.to_ascii_lowercase().as_str(),
                "1" | "true" | "yes" | "on"
            )
        })
        .unwrap_or(default)
}
