//! CCP Digital Marketing - Telemetry Cache Proxy
//!
//! HTTP proxy that intercepts Composio API calls and captures telemetry to SQLite

use ccp_cache_proxy::{ProxyServer, SqliteCacheRepository};
use std::net::SocketAddr;
use std::path::PathBuf;
use tokio::sync::mpsc;
use tracing::{error, info};
use tracing_subscriber;

use ccp_cache_proxy::persistence::{spawn_persistence_writer, PersistenceMessage};

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Initialize tracing
    tracing_subscriber::fmt::init();

    // Configuration from environment
    let proxy_port = std::env::var("CCP_PROXY_PORT")
        .unwrap_or_else(|_| "8765".to_string())
        .parse::<u16>()?;

    let upstream_base = std::env::var("CCP_COMPOSIO_API_BASE")
        .unwrap_or_else(|_| "https://backend.composio.dev/api/v1".to_string());

    let db_path = std::env::var("CCP_CACHE_DB_PATH")
        .unwrap_or_else(|_| {
            dirs::home_dir()
                .unwrap_or_else(|| PathBuf::from("."))
                .join(".claude/cache/state.db")
                .display()
                .to_string()
        });

    info!("CCP Digital Marketing - Telemetry Cache Proxy");
    info!("Proxy port: {}", proxy_port);
    info!("Upstream: {}", upstream_base);
    info!("Database: {}", db_path);

    // Initialize SQLite repository
    let repo = SqliteCacheRepository::new(&PathBuf::from(&db_path)).await?;
    info!("SQLite repository initialized (WAL mode enabled)");

    // Create persistence channel
    let (persistence_tx, persistence_rx) = mpsc::channel::<PersistenceMessage>(100);

    // Spawn persistence writer task
    tokio::spawn(spawn_persistence_writer(repo, persistence_rx));

    // Create and start proxy server
    let listen_addr: SocketAddr = ([0, 0, 0, 0], proxy_port).into();
    let proxy = ProxyServer::new(listen_addr, upstream_base, persistence_tx);

    info!("Starting proxy server...");
    if let Err(e) = proxy.start().await {
        error!("Proxy server error: {}", e);
        return Err(e);
    }

    Ok(())
}
