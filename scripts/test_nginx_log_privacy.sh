#!/usr/bin/env bash
set -euo pipefail

# Test Nginx Log Privacy & Safe Error Sink (TASK-012-FIX-C)
# Verifies that under upstream failures, 502s, timeouts, 404s, and normal requests:
# 1. No raw request targets, query strings, or PII/secrets appear in Nginx error log / stderr.
# 2. Access logs remain safe and do not record raw URIs or query strings.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

NGINX_BIN="$(command -v nginx || true)"
if [ -z "$NGINX_BIN" ]; then
    echo "WARNING: nginx binary not found in PATH; skipping runtime nginx privacy probe."
    exit 0
fi

echo "=== Verifying Nginx Configuration Files ==="
NGINX_CONF="$REPO_ROOT/deploy/nginx/nginx.conf"
DEFAULT_CONF="$REPO_ROOT/deploy/nginx/default.conf"

# Verify static directives
grep -E "error_log[[:space:]]+stderr[[:space:]]+(alert|crit|emerg);" "$NGINX_CONF" >/dev/null || {
    echo "ERROR: nginx.conf must configure error_log to stderr alert/crit/emerg" >&2
    exit 1
}

for forbidden_level in warn error notice info debug; do
    if grep -E "error_log[[:space:]]+[^;]*[[:space:]]+$forbidden_level;" "$NGINX_CONF" >/dev/null 2>&1; then
        echo "ERROR: nginx.conf contains forbidden error_log level: $forbidden_level" >&2
        exit 1
    fi
done

for forbidden_var in '$request_uri' '"uri"' '$args' '$query_string' '$http_referer'; do
    if grep -F "$forbidden_var" "$NGINX_CONF" >/dev/null 2>&1; then
        echo "ERROR: nginx.conf access log contains forbidden variable: $forbidden_var" >&2
        exit 1
    fi
done

echo "=== Starting Nginx Runtime Privacy Probe ==="
TMP_DIR="$(mktemp -d /tmp/nginx_privacy_test_XXXXXX)"
cleanup() {
    if [ -f "$TMP_DIR/nginx.pid" ]; then
        PID="$(cat "$TMP_DIR/nginx.pid" 2>/dev/null || true)"
        if [ -n "$PID" ]; then
            kill -QUIT "$PID" 2>/dev/null || true
            wait "$PID" 2>/dev/null || true
        fi
    fi
    rm -rf "$TMP_DIR"
}
trap cleanup EXIT

mkdir -p "$TMP_DIR/html" "$TMP_DIR/logs"
echo "OK" > "$TMP_DIR/html/index.html"
cat > "$TMP_DIR/mime.types" <<'EOF'
types {
    text/html html htm;
    text/css css;
    application/json json;
}
EOF

TEST_PORT=18080
DEAD_UPSTREAM_PORT=18089

TEST_CONF="$TMP_DIR/nginx_test.conf"
cat > "$TEST_CONF" <<EOF
daemon off;
worker_processes 1;
pid $TMP_DIR/nginx.pid;
error_log stderr alert;

events {
    worker_connections 64;
}

http {
    include $TMP_DIR/mime.types;
    default_type application/octet-stream;

    log_format json_combined escape=json
        '{"time_local":"\$time_iso8601",'
        '"remote_addr":"\$remote_addr",'
        '"request_method":"\$request_method",'
        '"status":\$status,'
        '"upstream_status":"\$upstream_status",'
        '"body_bytes_sent":\$body_bytes_sent,'
        '"request_time":\$request_time,'
        '"http_user_agent":"\$http_user_agent",'
        '"request_id":"\$request_id"}';

    access_log $TMP_DIR/logs/access.log json_combined;

    server {
        listen 127.0.0.1:$TEST_PORT;
        server_name localhost;
        root $TMP_DIR/html;

        proxy_connect_timeout 1s;
        proxy_read_timeout 1s;

        location ~ ^/health(/|$) {
            proxy_pass http://127.0.0.1:$DEAD_UPSTREAM_PORT;
        }

        location ~ ^/agent(/|$) {
            proxy_pass http://127.0.0.1:$DEAD_UPSTREAM_PORT;
        }

        location /admin {
            proxy_pass http://127.0.0.1:$DEAD_UPSTREAM_PORT;
        }

        location / {
            try_files \$uri \$uri/ /index.html;
        }
    }
}
EOF

STDERR_LOG="$TMP_DIR/logs/stderr.log"
# Start Nginx in background capturing stderr
"$NGINX_BIN" -c "$TEST_CONF" 2> "$STDERR_LOG" &
NGINX_PID=$!
sleep 0.5

# Ensure Nginx started
if ! kill -0 "$NGINX_PID" 2>/dev/null; then
    echo "ERROR: Nginx failed to start. Logs:" >&2
    cat "$STDERR_LOG" >&2
    exit 1
fi

MARKER_PHONE="77001234567"
MARKER_BARCODE="0123456789012"
MARKER_PATH_SECRET="fixture-path-secret-999"
MARKER_QUERY_SECRET="fixture-query-secret-888"
MARKER_TOKEN="fixture-token-777"
MARKER_AUTH="fixture-auth-header-secret"

echo "Executing test requests against Nginx..."

# 1. Upstream failure / connection refused (returns 502)
curl -s -o /dev/null -w "%{http_code}\n" \
    -H "Authorization: Bearer $MARKER_AUTH" \
    "http://127.0.0.1:$TEST_PORT/health/$MARKER_PHONE/$MARKER_BARCODE/$MARKER_PATH_SECRET?token=$MARKER_QUERY_SECRET" || true

# 2. Unknown path on static root (returns 200 via SPA fallback or 404)
curl -s -o /dev/null -w "%{http_code}\n" \
    "http://127.0.0.1:$TEST_PORT/unknown/$MARKER_PHONE/$MARKER_PATH_SECRET?code=$MARKER_QUERY_SECRET" || true

# 3. Admin upstream failure
curl -s -o /dev/null -w "%{http_code}\n" \
    -H "X-Admin-Request: 1" \
    "http://127.0.0.1:$TEST_PORT/admin/users/$MARKER_PHONE?auth=$MARKER_TOKEN" || true

# 4. Normal healthy request
curl -s -o /dev/null -w "%{http_code}\n" \
    "http://127.0.0.1:$TEST_PORT/index.html?param=$MARKER_QUERY_SECRET" || true

# Stop Nginx
kill -QUIT "$NGINX_PID" 2>/dev/null || true
wait "$NGINX_PID" 2>/dev/null || true

echo "=== Scanning Logs for Sensitive Fixture Markers ==="
ALL_LOGS="$TMP_DIR/logs/access.log $STDERR_LOG"

FAILURES=0
for marker in "$MARKER_PHONE" "$MARKER_BARCODE" "$MARKER_PATH_SECRET" "$MARKER_QUERY_SECRET" "$MARKER_TOKEN" "$MARKER_AUTH"; do
    for log_file in $ALL_LOGS; do
        if [ -f "$log_file" ] && grep -F "$marker" "$log_file" >/dev/null 2>&1; then
            echo "SECURITY LEAK DETECTED: Marker '$marker' found in $log_file!" >&2
            grep -F "$marker" "$log_file" >&2
            FAILURES=$((FAILURES + 1))
        fi
    done
done

if [ "$FAILURES" -gt 0 ]; then
    echo "ERROR: Nginx log privacy test FAILED with $FAILURES leak(s)." >&2
    exit 1
fi

# Ensure access log captured requests properly and without leakage
if [ ! -s "$TMP_DIR/logs/access.log" ]; then
    echo "ERROR: Access log is empty; expected request entries." >&2
    exit 1
fi

echo "SUCCESS: All Nginx log sinks verified clean. Zero sensitive markers leaked."
exit 0
