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
# The Alpine CSP build cannot evaluate x-model's assignment: inputs would never reach the
# request. Values are read from the submitted form instead.
check "page uses no x-model (unsupported by the Alpine CSP build)" "no" \
  "$(curl -s "$FE/" | grep -q 'x-model' && echo yes || echo no)"

echo "API through the proxy"
check "ping without token -> 401" "401" "$(status "$FE/api/v1/ping")"
check "ping with token -> 200" "200" "$(status -H @"$header_file" "$FE/api/v1/ping")"
check "401 body is uniform" '{"error":"unauthorized"}' "$(curl -s "$FE/api/v1/ping")"

echo "Trip lookup through the proxy (PostgreSQL rules + mock-tools)"
lookup() { # lookup <booking> <surname> [curl args...]
  local booking="$1" surname="$2"; shift 2
  curl -s -H 'Content-Type: application/json' \
    -d "{\"booking_id\":\"$booking\",\"last_name\":\"$surname\"}" "$@" "$FE/api/v1/trips/lookup"
}
brief="$(lookup ABC123 Silva -H @"$header_file")"
check "ABC123/Silva -> DISRUPTIVE" "yes" "$(grep -q '"relevance":"DISRUPTIVE"' <<<"$brief" && echo yes || echo no)"
check "ABC123/Silva uses REL-2026-09" "yes" "$(grep -q '"rules_version":"REL-2026-09"' <<<"$brief" && echo yes || echo no)"
check "ABC123/Silva has no email" "no" "$(grep -q 'maria.silva@example.com' <<<"$brief" && echo yes || echo no)"
check "NOTF01 -> 404" "404" "$(lookup NOTF01 Silva -H @"$header_file" -o /dev/null -w '%{http_code}')"
check "lookup without token -> 401" "401" "$(lookup ABC123 Silva -o /dev/null -w '%{http_code}')"

echo "Recommendation and human case (policy, options, case tool, human_cases)"
post() { # post <path> <json> [curl args...]
  local path="$1" body="$2"; shift 2
  curl -s -H 'Content-Type: application/json' -H @"$header_file" -d "$body" "$@" "$FE/api/v1/trips/$path"
}
reco="$(post recommendation '{"booking_id":"ABC123","last_name":"Silva"}')"
check "ABC123 recommendation -> PROPOSED" "yes" "$(grep -q '"status":"PROPOSED"' <<<"$reco" && echo yes || echo no)"
check "ABC123 recommends O1 only" "yes" "$(grep -q '"option_id":"O1"' <<<"$reco" && ! grep -q '"O2"' <<<"$reco" && echo yes || echo no)"
first="$(post human-case '{"booking_id":"ABC123","last_name":"Silva","option_id":"O1"}' -o /dev/null -w '%{http_code}')"
check "first ABC123 case -> 201 (or 200 if one is already open)" "yes" "$([[ $first == 201 || $first == 200 ]] && echo yes || echo no)"
check "repeat ABC123 case -> 200 (same case)" "200" "$(post human-case '{"booking_id":"ABC123","last_name":"Silva","option_id":"O1"}' -o /dev/null -w '%{http_code}')"
caserr="$(post human-case '{"booking_id":"CASERR","last_name":"Silva","option_id":"O1"}')"
check "CASERR case -> INDETERMINATE" "yes" "$(grep -q '"status":"INDETERMINATE"' <<<"$caserr" && echo yes || echo no)"
check "ineligible option -> 409" "409" "$(post human-case '{"booking_id":"ABC123","last_name":"Silva","option_id":"O2"}' -o /dev/null -w '%{http_code}')"

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
# Leave the limiter refilled (burst 20 at 10 r/s) so a run started right after this one
# does not fail on 429s caused by this burst.
sleep 2.5

echo
echo "$pass passed, $fail failed"
[[ $fail -eq 0 ]]
