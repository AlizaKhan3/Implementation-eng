#!/usr/bin/env bash
# Simple repeatable health check for the MiniPay stack.
# Usage: ./healthcheck.sh [api_url]
set -uo pipefail
API_URL="${1:-http://localhost:8080}"
FAIL=0

echo "== MiniPay health check =="
echo "-- API: $API_URL/health --"
if curl -sf --max-time 3 "$API_URL/health" | grep -q '"status":"ok"'; then
    echo "OK"
else
    echo "FAIL: API not healthy or unreachable"
    FAIL=1
fi

echo "-- Database: TCP connect to \${DB_HOST:-localhost}:\${DB_PORT:-5432} --"
if timeout 3 bash -c "cat < /dev/null > /dev/tcp/${DB_HOST:-localhost}/${DB_PORT:-5432}" 2>/dev/null; then
    echo "OK"
else
    echo "FAIL: database port unreachable"
    FAIL=1
fi

echo "-- Disk space on / --"
USE_PCT=$(df -P / | awk 'NR==2 {gsub("%","",$5); print $5}')
echo "Used: ${USE_PCT}%"
if [ "$USE_PCT" -ge 90 ]; then
    echo "FAIL: disk usage >= 90%"
    FAIL=1
else
    echo "OK"
fi

if [ "$FAIL" -eq 0 ]; then
    echo "== RESULT: HEALTHY =="
else
    echo "== RESULT: UNHEALTHY =="
fi
exit "$FAIL"
