# Tasks

TDD throughout: every "test" task is written and run to see it fail for the expected reason before its implementation task. All tests are unit tests in `api/tests/unit/` unless stated otherwise.

## 1. Tooling scaffold

- [x] 1.1 Create `api/pyproject.toml` with uv: runtime deps (fastapi, uvicorn, pydantic, pydantic-settings, sqlalchemy, alembic, psycopg[binary]), dev deps (pytest, httpx, ruff, import-linter), ruff and pytest config, and the four import-linter contracts from design D7; generate `uv.lock`. Verify that `uv lock` succeeds and that the `companion` package skeleton (empty `presentation/`, `services/`, `ports/`, `repositories/sql/`, `schemas/` packages) imports
- [x] 1.2 Create `api/Dockerfile` with `runtime` and `dev` targets, pinned `python:3.12-slim`, non-root user. Verify that both targets build with `docker build --target ...`
- [x] 1.3 Create `docker-compose.yml` with only the `tools` service (`dev` profile, source mounted), plus `.env.example` with placeholders (`API_TOKEN`, `POSTGRES_PASSWORD`, `POSTGRES_USER`, `POSTGRES_DB`, `ENABLE_DOCS=true`, `LOG_LEVEL`). Verify that `docker compose --profile dev run --rm tools python -c "import companion"` succeeds
- [x] 1.4 Create the `Makefile` with `env`, `test`, `lint`, `format`, `check` (design D6); `make env` refuses to overwrite an existing `.env`. Verify that `make env` creates `.env` with random values, a second `make env` fails without changing it, and `make check` runs ruff and lint-imports cleanly
- [x] 1.5 Update the Commands section of `CLAUDE.md` with the targets that now exist. Verify that each documented command runs as written

## 2. Configuration

- [x] 2.1 Test `Settings`: valid construction from explicit values; missing `API_TOKEN` raises; a token under 32 characters raises; `repr(settings)` contains neither the token nor the database URL. Verify that the tests fail before 2.2
- [x] 2.2 Implement `companion/config.py` (design D3). Verify that the tests from 2.1 pass with `make test ARGS="tests/unit/test_config.py"`

## 3. Health: schemas, service, port, adapter

- [x] 3.1 Test `HealthService.readiness()` with a `FakeDatabaseProbe`: reachable → `ReadyStatus("ready")`, unreachable → `ReadyStatus("not_ready")`. Verify that the tests fail before 3.2
- [x] 3.2 Implement `schemas/health.py` (`LiveStatus`, `ReadyStatus`), `ports/database.py` (`DatabaseProbe`) and `services/health.py`. Verify that the tests from 3.1 pass
- [x] 3.3 Test `SqlDatabaseProbe`: `True` against a SQLite file in `tmp_path`; `False` (no exception raised) against an unreachable URL, with the failure logged without the URL. Verify that the tests fail before 3.4
- [x] 3.4 Implement `repositories/sql/engine.py` and `repositories/sql/probe.py` (`SELECT 1`, 2-second timeout). Verify that the tests from 3.3 pass and `make lint` shows no layer-contract violations

## 4. Database migrations (expand phase: baseline)

- [x] 4.1 Test that `alembic upgrade head` then `alembic downgrade base` succeed against a SQLite file in `tmp_path`, and that `alembic_version` holds `0001` after the upgrade. Verify that the test fails before 4.2
- [x] 4.2 Create `alembic.ini`, `migrations/env.py` (URL from `Settings`, `target_metadata` from `repositories/sql/tables.py`, `render_as_batch=True`) and the empty revision `0001_baseline` (expand phase, with a `downgrade()`). Verify that the test from 4.1 passes

## 5. Presentation: request IDs, errors, auth, routes

- [x] 5.1 Test the request ID middleware: generated when absent, reused when valid (`demo-123`), replaced when invalid (`<script>`), and present in log records. Verify that the tests fail before 5.2
- [x] 5.2 Implement `presentation/request_id.py` (pure ASGI middleware, `contextvars`, logging filter). Verify that the tests from 5.1 pass
- [x] 5.3 Test the error contract with a test-only router: a `RuntimeError("db password=secret")` gives a 500 with `internal_error` and the request ID, and `secret` is not in the body; an unknown path gives a 404 `not_found`; `limit=maria.silva@example.com` gives a 422 with `fields` and the email address is not in the body. Verify that the tests fail before 5.4
- [x] 5.4 Implement `schemas/errors.py` and `presentation/errors.py` (exception handlers, design D5). Verify that the tests from 5.3 pass
- [x] 5.5 Test authentication with `TestClient`: the valid-token, missing-header, wrong-scheme and wrong-token scenarios; the three 401s identical, with `WWW-Authenticate: Bearer`; `/health/live` without a token gives 200; `wrong-token` is absent from `caplog`. Verify that the tests fail before 5.6
- [x] 5.6 Implement `presentation/auth.py` (`require_token`, `hmac.compare_digest`), `schemas/ping.py` and `presentation/routers/ping.py` on the `/api/v1` router. Verify that the tests from 5.5 pass
- [x] 5.7 Test the health routes via a dependency override: `/health/live` gives 200 `ok`; `/health/ready` gives 200 `ready` or 503 `not_ready` with the exact body. Verify that the tests fail before 5.8
- [x] 5.8 Implement `presentation/routers/health.py`, `composition.py` (builds `SqlDatabaseProbe` and `HealthService` from `Settings`) and `main.py` `create_app()` (docs only when `ENABLE_DOCS=true`). Verify that the tests from 5.7 pass and `make check` is green, including all four import-linter contracts
- [x] 5.9 Test API docs (spec `api-docs`): with `ENABLE_DOCS=true`, `/openapi.json` and `/docs` return 200 without a token; with the default, both return 404; `/redoc` always returns 404; a contract test over `app.openapi()` checks every operation's documented status codes and schemas, Bearer security on `/api/` and none on `/health/`, and the absence of the token and database URL. Verify that the tests fail before 5.10
- [x] 5.10 Implement `presentation/responses.py` (`PROTECTED_RESPONSES`, `PUBLIC_RESPONSES`), attach them to both routers, switch `require_token` to `HTTPBearer(auto_error=False)`, and wire the docs URLs in `create_app()` (design D12). Verify that the tests from 5.9 pass and the auth tests from 5.5 still pass

## 6. Containers

- [x] 6.1 Create the `mock-tools` skeleton (`pyproject.toml`, Dockerfile, `/health/live`) with one unit test for its health endpoint. Verify that the test passes in its own `tools` run
- [x] 6.2 Add `db`, `migrate`, `api` and `mock-tools` to `docker-compose.yml` (design D8: health checks, `depends_on` conditions, a named volume, ports bound to `127.0.0.1`, `DATABASE_URL` built from env interpolation). Verify that `docker compose up -d` brings `api` to healthy and `curl 127.0.0.1:8000/health/ready` returns 200
- [x] 6.3 Add `up`, `down`, `logs`, `migrate` and `migration name=...` to the `Makefile` and to the Commands section of `CLAUDE.md`. Verify that `make down && make up` works and `make migrate` reports the database at `0001`

## 7. Frontend shell

- [x] 7.1 Create `fe/nginx.conf` (design D9: `/api/` pass-through, rate limit, body limit, `server_tokens off`, security headers with `always`, no `/health` location) and add the `fe` service to compose. Verify that `curl -I 127.0.0.1:8080/` shows the four security headers and no server version
- [x] 7.2 Vendor the Alpine.js CSP build into `fe/public/vendor/` (pinned version, noted in a comment) and create `index.html` + `app.js`: call `/api/v1/ping` on load and show "Connected", "Missing or invalid token" or "Service unavailable"; no inline scripts and no credential handling. Verify manually in the browser for all three states (extension on, extension off, `api` stopped) with no CSP errors in the console

## 8. Smoke check and run instructions

- [x] 8.1 Write `scripts/smoke.sh` and the `make smoke` target, covering the `passenger-web` and auth checks listed in the design's test strategy (page 200 + headers, 401 without a token, 200 with the `.env` token, `/health/ready` and `/docs` 404 through nginx, `127.0.0.1:8000/docs` 200 with `ENABLE_DOCS=true`, at least one 429 in a 50-request burst). The token is read from `.env` and never echoed. Verify that `make smoke` passes against a fresh `make up`
- [x] 8.2 Add a "Run locally" section to `README.md` (prerequisites, `make env`, `make up`, header-extension setup scoped to `http://localhost:8080/*`, `make check`, `make smoke`) and add `smoke` to the Commands section of `CLAUDE.md`. Verify by following the README from a clean clone

## 9. Final verification

- [x] 9.1 From a clean state (`make down -v`), run `make env` (if needed), `make up`, `make check` and `make smoke`. Verify that all pass, and record the results and any known limitations in the change summary

## Workflow follow-up

- Archive the change with `/opsx:archive` once all tasks are checked and `make check` passes.
- Next changes: tool contracts in `mock-tools` + the disruption decision engine; then write actions (rebooking with idempotency, human case, notifications) and the passenger views.
