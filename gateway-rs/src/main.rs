use std::{env, sync::Arc, time::Duration};

use doorman_gateway::{
    AppState, Config, build_router,
    storage::{runtime::SharedStorage, snapshot},
};
use tokio::net::TcpListener;
use tracing::{error, info, warn};

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    doorman_gateway::observability::init();

    let config = Config::from_env()?;
    let bind_addr = config.bind_addr();
    let state = AppState::from_config(config).await?;
    let storage = state.storage.clone();

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
            Err(error_value) => error!(error = %error_value, "memory snapshot restore failed"),
        }
        spawn_memory_autosave(storage.clone());
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

fn spawn_memory_autosave(storage: Arc<SharedStorage>) {
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
                Ok(path) => info!(path = %path.display(), "memory autosave completed"),
                Err(error_value) => error!(error = %error_value, "memory autosave failed"),
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
