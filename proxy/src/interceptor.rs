//! HTTP interceptor for Composio API calls
//!
//! Transparently forwards requests to Composio API while capturing telemetry

use crate::persistence::{PersistenceMessage, ToolCall};
use crate::pii_mask::mask_pii;
use http_body_util::{BodyExt, Full};
use hyper::body::Bytes;
use hyper::server::conn::http1;
use hyper::service::service_fn;
use hyper::{Request, Response, StatusCode};
use hyper_util::client::legacy::Client;
use hyper_util::rt::{TokioExecutor, TokioIo};
use std::convert::Infallible;
use std::net::SocketAddr;
use std::time::SystemTime;
use tokio::net::TcpListener;
use tokio::sync::mpsc;
use tracing::{error, info, warn};

/// Proxy server configuration
pub struct ProxyServer {
    listen_addr: SocketAddr,
    upstream_base: String,
    persistence_tx: mpsc::Sender<PersistenceMessage>,
}

impl ProxyServer {
    /// Create new proxy server
    pub fn new(
        listen_addr: SocketAddr,
        upstream_base: String,
        persistence_tx: mpsc::Sender<PersistenceMessage>,
    ) -> Self {
        Self {
            listen_addr,
            upstream_base,
            persistence_tx,
        }
    }

    /// Start the proxy server
    ///
    /// Binds to listen_addr and forwards all requests to upstream_base
    pub async fn start(self) -> Result<(), Box<dyn std::error::Error>> {
        let listener = TcpListener::bind(self.listen_addr).await?;
        info!("Proxy server listening on {}", self.listen_addr);
        info!("Forwarding to {}", self.upstream_base);

        loop {
            let (stream, _) = listener.accept().await?;
            let upstream_base = self.upstream_base.clone();
            let persistence_tx = self.persistence_tx.clone();

            tokio::spawn(async move {
                // Wrap TcpStream in TokioIo for hyper 1.x compatibility
                let io = TokioIo::new(stream);

                let service = service_fn(move |req| {
                    handle_request(req, upstream_base.clone(), persistence_tx.clone())
                });

                if let Err(e) = http1::Builder::new()
                    .serve_connection(io, service)
                    .await
                {
                    error!("Error serving connection: {}", e);
                }
            });
        }
    }
}

/// Handle individual HTTP request
///
/// Captures request, forwards to upstream, captures response, sends to persistence
async fn handle_request(
    req: Request<hyper::body::Incoming>,
    upstream_base: String,
    persistence_tx: mpsc::Sender<PersistenceMessage>,
) -> Result<Response<Full<Bytes>>, Infallible> {
    let start_time = SystemTime::now();
    let method = req.method().clone();
    let uri = req.uri().clone();
    let path = uri.path();

    info!("Intercepted: {} {}", method, path);

    // Extract request body
    let (parts, body) = req.into_parts();
    let body_bytes = match body.collect().await {
        Ok(collected) => collected.to_bytes(),
        Err(e) => {
            error!("Failed to read request body: {}", e);
            return Ok(Response::builder()
                .status(StatusCode::BAD_REQUEST)
                .body(Full::new(Bytes::from("Failed to read request body")))
                .unwrap());
        }
    };

    let request_json = String::from_utf8_lossy(&body_bytes).to_string();
    let masked_request = mask_pii(&request_json);

    // Build upstream request
    let upstream_url = format!("{}{}", upstream_base, path);
    let mut upstream_req = Request::builder()
        .method(method.clone())
        .uri(&upstream_url);

    // Copy headers
    for (key, value) in parts.headers.iter() {
        upstream_req = upstream_req.header(key, value);
    }

    let upstream_req = upstream_req
        .body(Full::new(body_bytes.clone()))
        .unwrap();

    // Forward request to upstream
    let https = hyper_rustls::HttpsConnectorBuilder::new()
        .with_native_roots()
        .unwrap()
        .https_only()
        .enable_http1()
        .build();
    let client: Client<_, Full<Bytes>> = Client::builder(TokioExecutor::new()).build(https);

    let upstream_response = match client.request(upstream_req).await {
        Ok(resp) => resp,
        Err(e) => {
            error!("Failed to forward request to upstream: {}", e);
            return Ok(Response::builder()
                .status(StatusCode::BAD_GATEWAY)
                .body(Full::new(Bytes::from(format!(
                    "Failed to forward request: {}",
                    e
                ))))
                .unwrap());
        }
    };

    // Extract response
    let status = upstream_response.status();
    let response_headers = upstream_response.headers().clone();
    let response_body = match upstream_response.into_body().collect().await {
        Ok(collected) => collected.to_bytes(),
        Err(e) => {
            error!("Failed to read upstream response: {}", e);
            return Ok(Response::builder()
                .status(StatusCode::BAD_GATEWAY)
                .body(Full::new(Bytes::from("Failed to read upstream response")))
                .unwrap());
        }
    };

    let response_json = String::from_utf8_lossy(&response_body).to_string();
    let masked_response = mask_pii(&response_json);

    // Calculate latency
    let latency_ms = start_time
        .elapsed()
        .map(|d| d.as_millis() as i64)
        .unwrap_or(0);

    info!(
        "Forwarded: {} {} -> {} ({}ms)",
        method, path, status, latency_ms
    );

    // Extract tool name from path (e.g., /api/v1/actions/TOOL_NAME/execute)
    let tool_name = path
        .split('/')
        .nth_back(1)
        .unwrap_or("UNKNOWN_TOOL")
        .to_string();

    // Send to persistence (non-blocking)
    let tool_call = ToolCall {
        id: None,
        workflow_id: 1, // TODO: Extract from request context
        phase_id: None,
        tool_name,
        request_json: masked_request,
        response_json: Some(masked_response),
        status: if status.is_success() {
            "success".to_string()
        } else {
            "error".to_string()
        },
        latency_ms: Some(latency_ms),
        created_at: SystemTime::now()
            .duration_since(SystemTime::UNIX_EPOCH)
            .unwrap()
            .as_secs() as i64,
    };

    if let Err(e) = persistence_tx.send(PersistenceMessage::ToolCall(tool_call)).await {
        // Let It Crash: Log error but don't fail the request
        warn!("Failed to send to persistence channel: {}", e);
    }

    // Build response to client
    let mut response_builder = Response::builder().status(status);
    for (key, value) in response_headers.iter() {
        response_builder = response_builder.header(key, value);
    }

    Ok(response_builder
        .body(Full::new(response_body))
        .unwrap())
}
