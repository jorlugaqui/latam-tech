# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Take-home technical challenge for a Senior Software Engineer hiring process ("Caso A · Disruption Companion"), **Backend/Integration track**. It is a service that helps passengers whose flight was disrupted understand what happened and what their next step is, **without surfacing unverified information and without executing high-impact actions without controls.** A minimal frontend exists only to show the result.

The full brief is `docs/internal/disruption_companion.pdf` (Spanish; extract with `pdftotext -layout`). `docs/internal/` is gitignored, so never copy its contents verbatim into tracked files.

- **Time budget: max 3 effective hours total** (analysis, implementation, validation, docs). Prefer less, well-reasoned scope over breadth; the evaluation weighs judgment and explainability over amount of code.
- **Deliverables:** (1) the slice plus a design for the passenger-facing layer, run instructions, scope, tests and limitations; (2) an engineering README (≤2 pages) covering what is deterministic, AI-assisted, agentic or human-controlled, plus decisions and discarded alternatives; (3) an AI Usage & Decision Note (≤1 page). Keep track of AI output that was accepted, modified or rejected as you work, because deliverable 3 needs it.
- Runs **locally only** via docker compose. Nothing is deployed to any cloud.

## Workflow

All feature work goes through OpenSpec (`/opsx:explore` → `/opsx:propose` → `/opsx:apply` → `/opsx:archive`). `openspec/config.yaml` holds the per-artifact rules (proposal, specs, design, tasks) and apply/archive guidance; this file holds everything else. Current specs live in `openspec/specs/` and in-flight changes in `openspec/changes/`.

## Stack

| Component | Technology |
|---|---|
| `api` | Python 3.12, FastAPI, Pydantic v2, httpx; managed with uv; ruff for lint and format |
| `mock-tools` | separate FastAPI service implementing the tool contracts below; scenarios are selected by booking code (catalog in the README), timestamps are shifted to the request time, and calls need their own `TOOLS_API_TOKEN` (never the API token) |
| `db` | PostgreSQL at runtime, SQLite in unit tests; SQLAlchemy Core (no ORM) with portable types only |
| `migrate` | one-shot service running `alembic upgrade head` before `api` starts |
| `fe` | static HTML + Alpine.js (vendored in the repo, no build step) served by nginx; kept minimal; holds no credentials |

The Python stack is a deliberate choice for time-to-demo, even though the hiring team uses Spring Boot. The domain services are framework-free, so the logic is portable. Keep it that way.

## Commands

The Makefile is the single entry point (`make help` lists targets). Only Docker is required: tests and lint run in the `api-dev` and `mock-tools-dev` compose services (profile `dev`, source bind-mounted, so no rebuild per run). They are dev toolboxes, unrelated to the airline tools that `mock-tools` imitates.

```bash
make env                 # create .env from .env.example with random secrets (never overwrites)
make up                  # build + start db, migrate, api, mock-tools; waits until healthy
make down                # stop (keeps the database volume); `make clean` also deletes it
make logs ARGS="api"     # follow logs, optionally for some services
make migrate             # alembic upgrade head + print current revision
make migration name=add_x  # autogenerate a revision (stack must be up); then state its phase
make test                # all api unit tests
make test ARGS="tests/unit/test_config.py::test_name"   # a single test (any pytest args)
make test ARGS="-k missed_connection"
make lint                # ruff check + ruff format --check + lint-imports (layer contracts)
make format              # ruff format + ruff check --fix
make check               # lint + test, plus ruff + tests for mock-tools
make smoke               # scripts/smoke.sh against the running stack (nginx headers, proxy, 429s)
```

The `test` and `lint` targets first walk the source tree inside the container. Docker Desktop on macOS briefly caches "file not found" on bind mounts, so in TDD a module created right after its test failed can otherwise stay invisible to the next run. Keep that step if you edit these targets.

Python dependencies are managed with uv in `api/pyproject.toml` (lockfile `api/uv.lock`); after changing them run `uv lock` in `api/` and rebuild the `api-dev` image (`docker compose --profile dev build api-dev`).

## Architecture

Clean architecture; dependencies point inward:

- **presentation** (FastAPI routers): HTTP only, meaning parsing, auth and status codes. No business logic.
- **services**: business logic and decisions. Framework-free: no FastAPI, SQLAlchemy or httpx imports. Time (`now`) and all collaborators are injected.
- **repositories**: all data access (Postgres and the tool HTTP clients) behind `typing.Protocol` interfaces.
- **schemas**: Pydantic models used as DTOs at layer boundaries.

SOLID as applied here:
- **SRP:** source reconciliation, rule evaluation, option filtering and message composition are separate services.
- **OCP:** policy conditions are pluggable evaluators in a registry. A new rule adds a class; it does not edit the engine.
- **LSP:** fakes and real implementations of a Protocol must be interchangeable.
- **ISP:** read and write tool interfaces are separate. A service receives only what it needs, so read-only services never get a write client (least privilege).
- **DIP:** concrete classes are wired in a single composition root (FastAPI dependencies).

Layer rules are enforced by **import-linter** contracts run in `make check`, because Python `Protocol`s are not enforced at runtime. At minimum: services must not import presentation or infrastructure (FastAPI, SQLAlchemy, httpx), and read-only services must not import write interfaces.

**Database changes** use expand → migrate → contract (zero downtime): one Alembic revision per phase. Expand is additive only; contract ships in a later change. Never edit an applied revision. `render_as_batch=True` and batch operations keep migrations working on both SQLite and Postgres.

## Testing

TDD: write the failing test first, then implement. **Unit tests only** (pytest, `tests/unit/`), with no integration suite:
- Repositories and Alembic upgrade/downgrade run against in-memory SQLite.
- Endpoints are tested with `TestClient` and fake dependencies.
- Outbound tool calls are tested with `httpx.MockTransport`.
- Postgres itself is exercised only by the docker compose smoke check; this is a known limitation.

## Security

- **OWASP compliance:** code and designs must address the OWASP API Security Top 10 (2023) and the OWASP Top 10, for example authorization on every object, input validation via Pydantic, no sensitive data in errors or logs, rate limits, restrictive CORS and secure headers.
- Every endpoint except health requires `Authorization: Bearer <token>`, compared in constant time. In the browser the token is added by a header-modifier extension, so the frontend code never reads, stores or embeds it.
- **Zero recorded credentials:** secrets come only from environment variables. Commit only `.env.example`, with placeholders; `.env` is gitignored.
- PII (email, phone, `document_id`) never goes to logs, LLM prompts, or passenger output beyond what a spec allows.

## Domain contracts and traps

Read tools: `get_trip_context(booking_id)`, `get_operational_events(segment_ids)`, `get_eligible_options(trip_context)`, `get_policy_rules(scenario)`.
Write tools: `create_rebooking_request(option, idempotency_key)`, `create_human_case(reason, evidence)`, `notify_passenger(message)`.

Example payloads are in section 2 of the PDF. The sample data contains traps that any design must handle:
- Trip context returns `_meta.completeness: "PARTIAL"` with `missing_fields`.
- Events **contradict** each other. OPS_CORE reports a 160-minute DELAY on S1, while LEGACY_MIRROR reports ON_TIME; the LEGACY_MIRROR event is older and that source is listed in `sources_degraded`. Resolve source trust and freshness (`recorded_at`) explicitly.
- 160 minutes doesn't meet R1 (`>= 180`), but the new arrival in LIM (~20:35) misses S2 (19:05), which triggers R3 (missed connection → REBOOK_NO_FEE). Scheduled times are local with no offset; `recorded_at` is UTC.
- Options are candidates, not decisions: they carry `confidence` and `_meta.ttl_seconds` (120s), so re-fetch them before any write. O2 has 1 seat for 2 passengers and a fare difference despite R3. O3 is a refund on a non-refundable fare.
- Policies are versioned (`POL-DELAY-2026-03`). R4 (cash compensation) and R5 (group includes a minor; the booking has a 7-year-old) require human approval.
- `create_rebooking_request`: 409 means a duplicate, so adopt the existing `request_id`. 503 means an **indeterminate outcome**, so never retry blindly.
- `notify_passenger` returns 422 `UNVALIDATED_CONTENT` if a message lacks a `policy_ref`.

The brief leaves these open on purpose (decide and document, or state who you'd ask): what counts as a relevant disruption, what may be shown to the passenger, when a recommendation can be automatic, when a human must intervene, and how to resolve conflicting sources.

## Submission

Submission is a one-shot HTTP POST to an external API, described in `docs/internal/instructions.txt`. It **must be sent only once and only by the user.** Never send it, retry it, or test it from this environment.
