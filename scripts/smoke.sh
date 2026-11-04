#!/usr/bin/env bash
# Smoke check against the running stack (`make up` first). Covers what unit tests cannot:
# nginx headers, the /api pass-through, internal-only paths, rate limiting, and readiness
# against the real PostgreSQL. The token is read from .env and never printed.
set -euo pipefail

FE="${FE_URL:-http://127.0.0.1:8080}"
API="${API_URL:-http://127.0.0.1:8000}"
ENV_FILE="${ENV_FILE:-.env}"

pass=0
fail=0
check() { # check <description> <expected> <actual>
  if [[ "$2" == "$3" ]]; then
    echo "  ok    $1"
    pass=$((pass + 1))
  else
    echo "  FAIL  $1 (expected $2, got $3)"
    fail=$((fail + 1))
  fi
}
status() { curl -s -o /dev/null -w '%{http_code}' "$@"; }
env_value() { grep -E "^$1=" "$ENV_FILE" | head -1 | cut -d= -f2-; }

[[ -f "$ENV_FILE" ]] || { echo "missing $ENV_FILE: run make env" >&2; exit 1; }

# The Authorization header goes through a private temp file, not argv (hidden from `ps`).
header_file="$(umask 077; mktemp)"
trap 'rm -f "$header_file"' EXIT
printf 'Authorization: Bearer %s\n' "$(env_value API_TOKEN)" > "$header_file"

echo "Page and security headers ($FE)"
headers="$(curl -s -D - -o /dev/null "$FE/")"
check "page returns 200" "200" "$(status "$FE/")"
for name in Content-Security-Policy X-Content-Type-Options Referrer-Policy X-Frame-Options; do
  present=$(grep -qi "^$name:" <<<"$headers" && echo yes || echo no)
  check "header $name" "yes" "$present"
done
server="$(grep -i '^server:' <<<"$headers" | tr -d '\r' | cut -d' ' -f2-)"
check "Server header without version" "nginx" "$server"
csp="$(grep -i '^content-security-policy:' <<<"$headers")"
check "CSP has frame-ancestors 'none'" "yes" "$(grep -q "frame-ancestors 'none'" <<<"$csp" && echo yes || echo no)"

echo "API through the proxy"
check "ping without token -> 401" "401" "$(status "$FE/api/v1/ping")"
check "ping with token -> 200" "200" "$(status -H @"$header_file" "$FE/api/v1/ping")"
check "401 body is uniform" '{"error":"unauthorized"}' "$(curl -s "$FE/api/v1/ping")"

echo "Internal-only paths"
check "/health/ready through fe -> 404" "404" "$(status "$FE/health/ready")"
check "/docs through fe -> 404" "404" "$(status "$FE/docs")"
check "readiness on api port (PostgreSQL) -> 200" "200" "$(status "$API/health/ready")"
if [[ "$(env_value ENABLE_DOCS)" == "true" ]]; then
  check "/docs on api port -> 200 (ENABLE_DOCS=true)" "200" "$(status "$API/docs")"
else
  check "/docs on api port -> 404 (docs disabled)" "404" "$(status "$API/docs")"
fi

echo "Rate limiting (50 parallel requests)"
codes="$(seq 50 | xargs -P 50 -I{} curl -s -o /dev/null -w '%{http_code}\n' "$FE/api/v1/ping")"
limited=$(grep -c '^429$' <<<"$codes" || true)
check "at least one 429" "yes" "$([[ $limited -ge 1 ]] && echo yes || echo no)"

echo
echo "$pass passed, $fail failed"
[[ $fail -eq 0 ]]
