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
| `http://localhost:8080/` | Passenger page (shows whether the API accepts your token) |
| `http://127.0.0.1:8000/docs` | OpenAPI docs (only when `ENABLE_DOCS=true` in `.env`; not exposed through 8080) |

**Token in the browser.** Every `/api` call needs `Authorization: Bearer <API_TOKEN>` (the value is in `.env`). The page never handles the token itself. Add it with a header-modifier browser extension and **scope the rule to `http://localhost:8080/*` only**, so the token is not sent to other sites. Without it, the page shows "Missing or invalid token".

From a terminal: `curl -H "Authorization: Bearer $(grep ^API_TOKEN= .env | cut -d= -f2-)" http://localhost:8080/api/v1/ping`

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
