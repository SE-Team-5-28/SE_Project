#!/bin/sh
set -eu

url="${HEALTHCHECK_URL:-http://127.0.0.1:8000/healthz}"

if curl --fail --silent --show-error --max-time 5 "$url" >/dev/null; then
    printf 'Health check succeeded: %s\n' "$url"
    exit 0
fi

printf 'Health check failed; restarting hostel-management.service\n' >&2
systemctl restart hostel-management.service
sleep 2

if curl --fail --silent --show-error --max-time 5 "$url" >/dev/null; then
    printf 'Health check recovered after restart: %s\n' "$url"
    exit 0
fi

printf 'Health check still failing after restart: %s\n' "$url" >&2
exit 1
