//! CCP Digital Marketing - HTTP Proxy for Telemetry Capture
//!
//! This library provides transparent HTTP interception for Composio API calls.
//! It captures request/response pairs with timing and persists to SQLite asynchronously.

pub mod interceptor;
pub mod persistence;
pub mod pii_mask;

pub use interceptor::ProxyServer;
pub use persistence::SqliteCacheRepository;
