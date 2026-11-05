# Disruption Companion

Backend-first vertical slice that helps passengers whose flight was disrupted understand what happened and what their next step is, without surfacing unverified information and without executing high-impact actions without controls.

## Run locally

**Prerequisites:** Docker with Compose v2, `make`, `openssl` and `curl`. No Python toolchain is needed; tests and lint run in containers.

```bash
make env      # creates .env with random secrets (never overwrites an existing one)
make up       # builds and starts db, migrate, api, mock-tools, fe; waits until healthy
make check    # ruff + import-linter layer contracts + unit tests
make smoke    # checks the running stack: security headers, proxy, internal paths, rate limit
make down     # stop (make clean also deletes the database volume)
```

| URL | What |
|---|---|
| `http://localhost:8080/` | Passenger page: trip lookup by booking code and last name |
| `http://127.0.0.1:8000/docs` | OpenAPI docs (only when `ENABLE_DOCS=true` in `.env`; not exposed through 8080) |

**Token in the browser.** Every `/api` call needs `Authorization: Bearer <API_TOKEN>` (the value is in `.env`). The page never handles the token itself. Add it with a header-modifier browser extension and **scope the rule to `http://localhost:8080/*` only**, so the token is not sent to other sites. Without it, the page shows "Missing or invalid token".

From a terminal: `curl -H "Authorization: Bearer $(grep ^API_TOKEN= .env | cut -d= -f2-)" http://localhost:8080/api/v1/ping`

**Upgrading an older `.env`.** `mock-tools` needs its own `TOOLS_API_TOKEN` (not the API token). A `.env` created before it existed makes `api` and `mock-tools` refuse to start: recreate it with `rm .env && make env`, or append `TOOLS_API_TOKEN=$(openssl rand -hex 32)`.

## Demo scenarios

Look up any of these booking codes with the last name **Silva** (case and accents are ignored). Each one exercises a decision of the trip status assessment; mock timestamps are shifted to the request time, so freshness holds during a live demo.

| Booking | What it shows | Expected |
|---|---|---|
| `ABC123` | The brief's sample: partial context, degraded LEGACY_MIRROR contradicting OPS_CORE, 160-minute delay | `DISRUPTIVE`: missed connection (LA2410 19:05) and long delay; `E-1012` rejected |
| `OKAY01` | Everything on time | `NONE` |
| `GATE01` | Gate change only | `INFORMATIONAL` |
| `CONF01` | Two trusted sources disagree | `UNVERIFIED` (no delay asserted), agent hand-off |
| `STAL01` | Only stale events | `UNVERIFIED` |
| `CANC01` | First segment cancelled | `DISRUPTIVE`, onward flight unreachable |
| `NITE01` | Delay pushes the arrival past midnight | `DISRUPTIVE`: arrives 00:30 next day, connection at 23:50 missed |
| `EVTERR` | Events tool returns 503 | Trip shown, `UNVERIFIED`, no guessing |
| `CTXERR` | Trip context tool returns 503 | "Service unavailable" (503) |
| `NOTF01` | Unknown booking | "We couldn't find a booking" (404, same as a wrong surname) |

## Architecture decision record

Each decision is recorded with its classification. **Category** is one of: `deterministic`, `AI-assisted`, `agentic`, `human`, or `general` (foundation and cross-cutting decisions).

| # | Step (phase) | Category | Decision | Alternatives discarded | Risk | Control / fallback |
|---|---|---|---|---|---|---|
| 1 | Foundation | general | Backend/Integration track, with a minimal frontend | Frontend/Experience track | Thin passenger experience | Minimal Alpine.js page plus a written screen/message spec for the passenger layer |
| 2 | Foundation | general | Python 3.12 + FastAPI + Pydantic v2 | Spring Boot (the team's stack) | Mismatch with the team's stack | Framework-free domain services, portable to any framework |
| 3 | Foundation | general | Local-only docker compose: `api`, `mock-tools`, `db`, `migrate`, `fe` | Cloud deployment | Submission guidelines may expect a public API URL | Confirm with the recruiter; the compose setup is portable to any container host |
| 4 | Foundation | general | Tool contracts served by a separate `mock-tools` service with switchable scenarios | In-process mocks; a generic mock server (WireMock) | Mocks drift from real behavior | Contracts follow the brief's sample payloads; failure scenarios (409/503/422) can be demonstrated live |
| 5 | Data | general | PostgreSQL at runtime, SQLite in unit tests | Postgres in tests (testcontainers); SQLite everywhere | Dialect differences go undetected | Portable column types only; docker compose smoke check against Postgres |
| 6 | Data | general | Alembic migrations following expand → migrate → contract, one revision per phase | Hand-written SQL scripts; `create_all` at startup | SQLite's limited `ALTER` support | `render_as_batch=True`; a unit test runs upgrade and downgrade on SQLite |
| 7 | Data | general | SQLAlchemy Core; repositories return Pydantic DTOs | SQLAlchemy ORM; SQLModel (merges DTO and table, breaking the layer split) | Less familiar to a JPA-oriented team | Contained behind repository Protocols (DIP): switching affects one module |
| 8 | Architecture | general | Clean architecture (presentation, services, repositories, schemas) + SOLID; read and write tool interfaces split (ISP) | Layering by convention only; a single tool client | Over-engineering for a 3-hour budget | Abstractions only at real boundaries; read-only services never receive a write client (least privilege) |
| 9 | Architecture | general | Layer rules enforced by import-linter in `make check` | Code review only | Python `Protocol`s are not enforced at runtime | A broken layer contract fails the build |
| 10 | Quality | general | TDD with unit tests only (pytest) | Unit + integration suite | Integration defects missed | Endpoints via `TestClient`, tool calls via `httpx.MockTransport`; compose smoke check; documented limitation |
| 11 | Security | general | Bearer token from environment variables, compared in constant time | No auth; API keys in query strings; OAuth2/OIDC | A single shared token, no passenger identity | `.env` gitignored, only `.env.example` committed; passenger authentication is a next step |
| 12 | Security | general | In the browser, a header-modifier extension adds the token; the frontend code never handles it | Token embedded in the page; nginx injecting the token (BFF) | Extension sends the token to other sites if misconfigured | Extension rule scoped to `http://localhost:8080/*` only |
| 13 | Security | general | OWASP API Security Top 10 (2023) and OWASP Top 10 addressed in every design | Ad-hoc security review | A risk is overlooked | Each change's design lists the OWASP risks it touches and the control for each |
| 14 | Experience | general | Static HTML + Alpine.js, vendored in the repo, no build step | React/Vue + Vite; HTMX with server-rendered templates | Limited interactivity | Only four UI states are needed (loading, disruption, recommendation, escalated to a human) |
| 15 | Experience | general | nginx serves the page and passes `/api/*` through to the API unchanged (same origin) | Separate origins with a CORS allowlist; BFF token injection | The proxy becomes a single point of failure | Local demo only; security headers (CSP and others) set in one place; no CORS needed |
| 16 | Process | general | OpenSpec spec-driven workflow | Ad-hoc development | Process overhead within 3 hours | Small changes; spec scenarios double as unit test cases |
| 17 | Trip status | deterministic | Relevance tiers `NONE` / `INFORMATIONAL` / `DISRUPTIVE` / `UNVERIFIED`. `DISRUPTIVE` = cancellation, missed connection (MCT included) or delay ≥ 120 min, using accepted evidence only. Precedence DISRUPTIVE > UNVERIFIED > INFORMATIONAL > NONE; `DISRUPTIVE` only opens the gate to a recommendation, which must recompute on the server | R1's 180 min as the threshold (couples relevance to entitlement policy); every change counts as relevant | Thresholds differ from Ops' view | Parameters are versioned data (row 19), to be confirmed with PM + Ops; the version is reported on every result |
| 18 | Trip status | deterministic | Accepted evidence: source listed as available and not degraded, recorded within the freshness window (30 min), and not contradicted by another trusted source. Conflict between trusted sources → `UNVERIFIED`; trust comes from each response's `_meta` | The most recent event wins regardless of source; a fixed source ranking | A real disruption is hidden behind `UNVERIFIED` | `UNVERIFIED` sends the passenger to a person (`HUMAN_ASSISTANCE`), never to silence |
| 19 | Trip status | general | Relevance rules (criteria, tier, params, freshness, MCTs) stored in PostgreSQL as immutable versions (`REL-2026-09`), one row per criterion; airport IANA zones as reference data | Constants in code; a versioned file in the repo; typed columns per parameter | Bad rule data reaches passengers | Params validated per criterion on load; unknown key, invalid params or no version → `UNVERIFIED/RULES_UNAVAILABLE` (fail closed); no write endpoint |
| 20 | Trip status | deterministic | Solver and explanation composer are Strategy seams; the demo ships only `DeterministicSolver` (criteria registry, OCP) and `TemplateComposer` | LLM classification; a monolithic solver; an unwired LLM stub | A future AI composer states something false | Next step only: an LLM composer that rewords the structured claims, wrapped by a deterministic verifier that falls back to the template, rolled out in shadow mode; it would receive `TripFacts`, which hold no personal data |
| 21 | Trip status | deterministic | Times computed as aware UTC from local schedule fields with IANA airport zones (arrival = first local occurrence after departure); responses carry the airport's offset | Fixed offsets; comparing naive `HH:MM` | Chile's DST change; arrivals after midnight | `tzdata` pinned; `NITE01`; `scheduled + delay == new_departure` consistency check (`INCONSISTENT_EVENT`) |
| 22 | Security | general | Lookup is `POST /api/v1/trips/lookup {booking_id, last_name}`; the surname must match a passenger's trailing name words (accent/case-insensitive, constant-time); unknown booking and wrong surname give the same 404; events are read only after a match | Booking code alone (BOLA); surname in the query string (lands in access logs) | Compound or unusual surnames rejected; enumeration | Body never logged; nginx rate limit; a real surname field and per-booking lockout are next steps |
| 23 | Trip status | deterministic | Tool responses are bounded: bodies are streamed and abandoned past 256 KiB, and more than 200 events is rejected; both count as the tool being unavailable | Trusting upstream size; paging events | A legitimate long itinerary exceeds the cap | Fails closed (`EVENTS_UNAVAILABLE` → agent hand-off; trip context → 503); limits are constants to revisit with real volumes |
| 24 | Trip status | general | Every assessment is appended to `trip_assessments` (booking, relevance, reasons with event ids, rejected events, `rules_version`, `assessed_at`, request ID); no personal data; kept indefinitely in this demo | Logs only (not queryable); storing the full response (carries names and text); using it as a cache | Retention of booking codes; audit outage | Insert-only, no update/delete path; a failed insert is logged and the lookup still answers (it executes nothing), while future actions must not proceed without their record; retention to be set by PM/Legal |
| 25 | Experience | human | Each outcome has its own next action: `DISRUPTIVE` → "See my options"; `UNVERIFIED` → "Talk to an agent" (both disabled until their features exist) | "See my options" for every outcome | Options computed on unverified data give wrong entitlements | The recommendation never runs on unverified data; the agent hand-off will open a human case (`create_human_case`) with the assessment as evidence |
