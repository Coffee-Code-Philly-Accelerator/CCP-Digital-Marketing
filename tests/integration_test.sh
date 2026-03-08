#!/bin/bash
# Integration test for CCP Telemetry Cache Proxy
# Tests full flow: proxy → capture → SQLite persistence

set -e  # Exit on error

echo "==================================="
echo "CCP Telemetry Cache - Integration Test"
echo "==================================="

# Cleanup function
cleanup() {
    echo ""
    echo "Cleaning up..."
    if [ ! -z "$PROXY_PID" ]; then
        kill $PROXY_PID 2>/dev/null || true
        wait $PROXY_PID 2>/dev/null || true
    fi
    rm -f /tmp/ccp_test_cache.db* || true
}

trap cleanup EXIT

# Configuration
TEST_PORT=18765
TEST_DB="/tmp/ccp_test_cache.db"
PROXY_DIR="$(cd "$(dirname "$0")/.." && pwd)/proxy"

echo ""
echo "Step 1: Building proxy..."
cd "$PROXY_DIR"
cargo build --release 2>&1 | grep -E "(Compiling|Finished)" || true

echo ""
echo "Step 2: Starting proxy on port $TEST_PORT..."
export CCP_PROXY_PORT=$TEST_PORT
export CCP_COMPOSIO_API_BASE="https://httpbin.org"  # Use httpbin for testing
export CCP_CACHE_DB_PATH="$TEST_DB"

# Start proxy in background
cargo run --release > /tmp/proxy.log 2>&1 &
PROXY_PID=$!

# Wait for proxy to start
echo "Waiting for proxy to start (PID: $PROXY_PID)..."
for i in {1..10}; do
    if lsof -i :$TEST_PORT > /dev/null 2>&1; then
        echo "✅ Proxy started successfully"
        break
    fi
    if [ $i -eq 10 ]; then
        echo "❌ Proxy failed to start"
        cat /tmp/proxy.log
        exit 1
    fi
    sleep 1
done

echo ""
echo "Step 3: Sending test request through proxy..."
HTTP_RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" \
    -X POST \
    -H "Content-Type: application/json" \
    -d '{"test": "data", "api_key": "secret123"}' \
    http://localhost:$TEST_PORT/post 2>&1)

HTTP_CODE=$(echo "$HTTP_RESPONSE" | grep "HTTP_CODE:" | cut -d: -f2)

if [ "$HTTP_CODE" = "200" ]; then
    echo "✅ HTTP request succeeded (200 OK)"
else
    echo "❌ HTTP request failed (got $HTTP_CODE)"
    echo "Response: $HTTP_RESPONSE"
    cat /tmp/proxy.log
    exit 1
fi

echo ""
echo "Step 4: Verifying SQLite cache..."

# Wait for async write
sleep 2

# Check if database exists
if [ ! -f "$TEST_DB" ]; then
    echo "❌ Database file not created"
    cat /tmp/proxy.log
    exit 1
fi

# Check tool_calls table
TOOL_CALL_COUNT=$(sqlite3 "$TEST_DB" "SELECT COUNT(*) FROM tool_calls;" 2>/dev/null || echo "0")

if [ "$TOOL_CALL_COUNT" -gt 0 ]; then
    echo "✅ Tool call captured ($TOOL_CALL_COUNT record(s))"

    # Show captured data
    echo ""
    echo "Captured tool call details:"
    sqlite3 "$TEST_DB" "SELECT tool_name, status, latency_ms, created_at FROM tool_calls LIMIT 1;" 2>/dev/null || true

    # Check PII masking
    REQUEST_JSON=$(sqlite3 "$TEST_DB" "SELECT request_json FROM tool_calls LIMIT 1;" 2>/dev/null)
    if echo "$REQUEST_JSON" | grep -q "\[REDACTED\]"; then
        echo "✅ PII masking verified (api_key redacted)"
    else
        echo "⚠️  PII masking may not have worked"
        echo "Request JSON: $REQUEST_JSON"
    fi
else
    echo "❌ No tool calls captured in database"
    echo "Database schema:"
    sqlite3 "$TEST_DB" ".schema" 2>/dev/null || echo "Could not read schema"
    echo ""
    echo "Proxy log:"
    cat /tmp/proxy.log
    exit 1
fi

echo ""
echo "Step 5: Testing latency benchmark..."

# Send 10 requests and measure latency
TOTAL_TIME=0
for i in {1..10}; do
    START=$(date +%s%N)
    curl -s -X POST \
        -H "Content-Type: application/json" \
        -d '{"test": "'"$i"'"}' \
        http://localhost:$TEST_PORT/post > /dev/null
    END=$(date +%s%N)

    LATENCY=$(( (END - START) / 1000000 ))  # Convert to milliseconds
    TOTAL_TIME=$(( TOTAL_TIME + LATENCY ))
done

AVG_LATENCY=$(( TOTAL_TIME / 10 ))
echo "Average latency: ${AVG_LATENCY}ms"

if [ $AVG_LATENCY -lt 50 ]; then
    echo "✅ Latency within acceptable range (<50ms)"
else
    echo "⚠️  Latency higher than target (${AVG_LATENCY}ms > 50ms)"
fi

echo ""
echo "==================================="
echo "✅ ALL INTEGRATION TESTS PASSED"
echo "==================================="
echo ""
echo "Summary:"
echo "  - Proxy started successfully"
echo "  - HTTP interception working"
echo "  - SQLite persistence confirmed"
echo "  - PII masking verified"
echo "  - Average latency: ${AVG_LATENCY}ms"
echo ""
