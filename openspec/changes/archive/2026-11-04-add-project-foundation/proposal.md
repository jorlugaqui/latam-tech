# Proposal

## Why

The Disruption Companion slice needs a runnable, secured base before any decision logic is built. The brief requires protecting personal data, applying least privilege, and keeping the first version operable by a small team (`docs/internal/disruption_companion.pdf`, §3 "Restricciones"). It also requires run instructions and tests as evidence (§6, Entregable 1). Building the foundation first keeps the later engine change focused on business logic, which is what the evaluation weighs (§8).

**Business outcome:** a reviewer can run `make up`, reach an authenticated API and a frontend shell, and run `make check`. Measured by: one command starts every service; `make check` passes; an unauthenticated request receives 401.

## What Changes

- Docker compose stack with five services: `api`, `mock-tools` (skeleton with a health endpoint only), `db` (PostgreSQL), `migrate` (one-shot Alembic run), and `fe` (nginx).
- `api` skeleton in the four-layer layout (presentation, services, repositories, schemas), with a composition root.
- Bearer token authentication for every `api` endpoint except health; the token comes from an environment variable.
- Liveness and readiness endpoints; readiness checks the database.
- Alembic configured for PostgreSQL and SQLite (batch mode), with an empty baseline revision.
- Generic error responses that never leak stack traces or internal details.
- OpenAPI documentation (`/openapi.json` and `/docs`), off by default and enabled for the local demo through configuration.
- `fe`: a static Alpine.js shell served by nginx, which passes `/api/*` through to `api` unchanged, sets security headers, and rate-limits API calls.
- Makefile (`up`, `down`, `logs`, `migrate`, `migration`, `test`, `lint`, `format`, `check`), pytest unit-test setup, ruff, import-linter layer contracts, and `.env.example`.

## Capabilities

### New Capabilities
- `api-authentication`: Bearer token requirement on API endpoints, the exempt health endpoints, and the 401 response contract.
- `api-health`: liveness and readiness reporting, including the database dependency.
- `api-errors`: the error response contract (unknown routes, unhandled failures) and request correlation, without leaking internals.
- `api-docs`: the OpenAPI document and interactive viewer, toggled by configuration, documenting every response and the Bearer scheme.
- `passenger-web`: the passenger-facing page delivery, the same-origin `/api` pass-through, security headers, and rate limiting at the edge.

### Modified Capabilities
None (no existing specs).

## Scope

**In scope:** everything listed under What Changes.
**Out of scope:** the tool contracts in `mock-tools` (they come with the decision engine change), the disruption decision engine, write actions (rebooking, human case, notifications), application tables, passenger identity and authentication, and runtime AI.

## Assumptions

- A single shared API token is enough for a local demo. Real passenger authentication is a next step; the Product/Security owner would confirm it.
- The reviewer's browser adds the `Authorization` header with a header-modifier extension scoped to `http://localhost:8080/*`.
- Local-only execution is acceptable, even though the submission guidelines may expect a public API URL. The recruiter must confirm this.

## High-impact actions

None. This change adds no write tool calls.

## Database

Touches the schema tooling only: an empty baseline revision. It is an **expand** phase (additive, nothing created or removed).

## Impact

New repository layout, five containers, development dependencies (FastAPI, Pydantic, SQLAlchemy Core, Alembic, psycopg, httpx, pytest, ruff, import-linter), and the Makefile as the entry point for every command. Once this ships, CLAUDE.md's Commands section is updated with the real targets.
