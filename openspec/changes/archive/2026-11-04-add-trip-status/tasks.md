# Tasks

TDD throughout: each "test" task is written and run, and must fail for the expected reason, before its implementation task. Tests run with `make test ARGS="..."`. Brief payloads used as test data live in `api/tests/unit/data/` (rewritten as fixtures, not copied from the PDF). Keep a note of AI output accepted, modified or rejected, for the AI Usage Note.

## 1. Dependencies and configuration

- [x] 1.1 Move `httpx` to runtime dependencies and add `tzdata` in `api/pyproject.toml`; add `pydantic-settings` to `mock-tools/pyproject.toml`; run `uv lock` in both and rebuild the `tools` images. Verify with `docker compose --profile dev run --rm tools python -c "import httpx, zoneinfo; zoneinfo.ZoneInfo('America/Santiago')"`
- [x] 1.2 Test `Settings` additions (design D14): `TOOLS_BASE_URL` required and a valid URL, `TOOLS_API_TOKEN` at least 32 characters and masked in `repr`, `TOOLS_TIMEOUT_SECONDS` default 3. Verify the tests fail before 1.3
- [x] 1.3 Implement the `Settings` fields; add `TOOLS_API_TOKEN` and `TOOLS_BASE_URL` placeholders to `.env.example`; make `make env` generate `TOOLS_API_TOKEN`. Verify that the 1.2 tests pass and a fresh `make env` (in a scratch copy) fills the token

## 2. Schemas

- [x] 2.1 Test the upstream DTOs in `schemas/tools.py` against the brief payloads: `ABC123` context parses (PARTIAL, optional PII fields, `_meta`); events parse all four types including `STATUS CANCELLED`; unknown extra fields are ignored. Verify the tests fail before 2.2
- [x] 2.2 Implement `schemas/tools.py`. Verify that the 2.1 tests pass
- [x] 2.3 Test `TripLookupRequest` (upper-casing, pattern, length, `extra="forbid"`) and that `TripStatusResponse` has no field named after any forbidden item in spec `trip-status`. Verify the tests fail before 2.4
- [x] 2.4 Implement `schemas/trip_status.py` and `schemas/assessment.py` (enums, `TripFacts`, `RelevanceRuleSet`, `CriterionConfig`, `AirportInfo`, `Assessment`, `Reason`, `RejectedEvent`, `Explanation`). Verify that the 2.3 tests pass

## 3. Assessment services (pure)

- [x] 3.1 Test `SourceReconciler` (spec: accepted evidence, supersession, conflict): `E-1012` → `SOURCE_DEGRADED`; stale → `STALE`; `CREW_APP` → `SOURCE_UNKNOWN`; 90→160 supersession; CONF01 conflict. Verify the tests fail before 3.2
- [x] 3.2 Implement `services/assessment/reconciliation.py`. Verify that the 3.1 tests pass
- [x] 3.3 Test `Timeline` (spec: airport time zones, estimated arrival, consistency): brief S1 offsets −03:00/−05:00 on 2026-09-15; estimated arrival `20:35-05:00`; NITE01 → `2026-09-16T00:30-05:00`; inconsistent `new_departure` → `INCONSISTENT_EVENT`; unknown airport → `AIRPORT_UNKNOWN`; missing `scheduled_arrival` → `CONTEXT_INCOMPLETE`. Verify the tests fail before 3.4
- [x] 3.4 Implement `services/assessment/timeline.py` with `zoneinfo`. Verify that the 3.3 tests pass
- [x] 3.5 Test each criterion and the registry: CANCELLATION (later segments `UNREACHABLE`), MISSED_CONNECTION with MCT from params (brief missed, 30-min delay OK, NITE01 missed), LONG_DELAY, MINOR_DELAY, GATE_CHANGE; invalid params and unknown key `MOON_PHASE` raise `RulesUnavailable`. Verify the tests fail before 3.6
- [x] 3.6 Implement `services/assessment/criteria.py` (`Criterion` Protocol, five classes with Pydantic `Params`, registry). Verify that the 3.5 tests pass
- [x] 3.7 Test `DeterministicSolver` with every relevance scenario in spec `disruption-assessment`: ABC123 (two reasons, no `MINOR_DELAY`), gate only, nothing, cancellation plus unknown S2, only stale, `REL-TEST-B`, `rules=None` → `RULES_UNAVAILABLE`, events `None` → `EVENTS_UNAVAILABLE`, missing fare field ignored. Verify the tests fail before 3.8
- [x] 3.8 Implement `services/assessment/solver.py` (`DisruptionSolver` Protocol and `DeterministicSolver`). Verify that the 3.7 tests pass
- [x] 3.9 Test `TemplateComposer`: ABC123 mentions LA500, 20:35 and LA2410 19:05, and contains none of `LEGACY_MIRROR`, `ON_TIME`, `fee`, `refund`; the UNVERIFIED text states no time or delay; one template per tier. Verify the tests fail before 3.10
- [x] 3.10 Implement `services/assessment/explanation.py`. Add the import-linter contract "`companion.services.assessment` must not import `companion.ports`". Verify that the 3.9 tests pass and `make lint` keeps every contract

## 4. Trip status service

- [x] 4.1 Test `surname_matches`: `silva` vs `María Silva`, `Silva Perez` vs `Ana Silva Pérez`, `Rojas` fails, whitespace collapsing. Verify the tests fail before 4.2
- [x] 4.2 Implement `services/surname.py`, plus ports `ports/tools.py`, `ports/rules.py`, `ports/clock.py`, and the fakes in `tests/unit/fakes.py`. Verify that the 4.1 tests pass
- [x] 4.3 Test `TripStatusService.lookup` with fakes: ABC123 response (passenger first names, S1 DELAYED 160, gate 24, connection MISSED, `RECOMMENDATION`); wrong surname → `TripNotFound` with the events reader never called; `BookingNotFound` → `TripNotFound`; context `ToolUnavailable` → `TripContextUnavailable`; events/rules failure → UNVERIFIED with `HUMAN_ASSISTANCE`; `caplog` contains `ABC123`, `DISRUPTIVE`, `E-1012`, `SOURCE_DEGRADED` and not `Silva`, `María`, or the email. Verify the tests fail before 4.4
- [x] 4.4 Implement `services/trip_status.py`. Verify that the 4.3 tests pass

## 5. Repositories and database (expand → migrate)

- [x] 5.1 Extend `test_migrations.py`: upgrade to head creates the three tables and seeds `REL-2026-09` (five criteria) and SCL/LIM/MEX; downgrade to `0002` removes only the seed; downgrade to `0001` removes the tables. Verify the test fails before 5.2
- [x] 5.2 Add the tables to `repositories/sql/tables.py`; create revision `0002_relevance_rules` (**expand**, batch ops) and `0003_seed_rel_2026_09` (**migrate**), each with a downgrade and its phase in the docstring. Verify that the 5.1 test passes
- [x] 5.3 Test `SqlRuleSetRepository` and `SqlAirportDirectory` on a SQLite file: version selection by effective window (two versions, picks the later one in effect), none in effect → `RulesUnavailable`, DB error → `RulesUnavailable`, datetimes returned aware in UTC, unknown airport omitted. Verify the tests fail before 5.4
- [x] 5.4 Implement `repositories/sql/rules.py` and `repositories/clock.py`. Verify that the 5.3 tests pass
- [x] 5.5 Test `HttpToolsClient` with `httpx.MockTransport`: sends the tools Bearer token and the JSON body; 200 → DTO; 404 → `BookingNotFound`; 503, timeout, connection error and invalid body → `ToolUnavailable`; exactly one call per lookup (no retry). Verify the tests fail before 5.6
- [x] 5.6 Implement `repositories/tools/http.py`. Verify that the 5.5 tests pass

## 6. Presentation and wiring

- [x] 6.1 Test the router with `TestClient` and a faked service: 401 without or with a wrong token and the service not called; 422 without echoing `ABC-12`; 404 `not_found` identical for unknown booking and wrong surname; 503 `trip_context_unavailable`; 200 body free of the brief's PII and `LEGACY_MIRROR`; the OpenAPI contract test covers the route with 503. Verify the tests fail before 6.2
- [x] 6.2 Implement `presentation/routers/trips.py` on the `/api/v1` router, add the `TripNotFound` and `TripContextUnavailable` handlers and the 503 response declaration. Wire `HttpToolsClient` (closed in the lifespan), the SQL repositories, `SystemClock`, `DeterministicSolver` and `TemplateComposer` in `composition.py`. Verify that the 6.1 tests pass and `make lint` keeps every contract

## 7. Mock tools

- [x] 7.1 Test mock-tools auth and settings: 401 without a token or with another token; `/health/live` public; startup fails without a 32-character `TOOLS_API_TOKEN`. Verify the tests fail before 7.2
- [x] 7.2 Implement `settings.py` and `auth.py` (constant-time compare). Verify that the 7.1 tests pass
- [x] 7.3 Test `timeshift` with a fixed clock: `E-1001.recorded_at` is `2026-11-04T14:45:27Z` at `2026-11-04T15:00:00Z`; S1 `date` is `2026-11-04`; local times unchanged. Verify the tests fail before 7.4
- [x] 7.4 Implement `timeshift.py`. Verify that the 7.3 tests pass
- [x] 7.5 Test both tool endpoints against the catalog (design D9): the brief samples for ABC123/S1/S2; each fixture's distinguishing events; `ZZZ999`/`NOTF01` → 404; `CTXERR` and `EVTERR` → 503; unknown segments → `[]`. Verify the tests fail before 7.6
- [x] 7.6 Implement `fixtures.py` and the endpoints in `main.py` with an injectable clock. Verify that the 7.5 tests pass and `make check` passes for mock-tools

## 8. Compose, frontend and smoke

- [x] 8.1 Update `docker-compose.yml`: `TOOLS_API_TOKEN` to `mock-tools`; `TOOLS_BASE_URL=http://mock-tools:8001` and `TOOLS_API_TOKEN` to `api`; `api` depends on `mock-tools` being healthy. Verify that `make up` starts every service healthy and `make migrate` prints revision `0003`
- [x] 8.2 Implement the `tripLookup` Alpine component and markup (spec `passenger-web`): form, status view with local `HH:MM` and airport code, the next-step callouts, and error messages; no storage and no URL change. Verify manually in the browser with `ABC123`, `OKAY01`, `GATE01`, `CONF01`, `CANC01`, `NITE01`, `NOTF01`, `CTXERR`, and `ABC123`/`Rojas`
- [x] 8.3 Extend `scripts/smoke.sh`: `ABC123`/`Silva` through nginx → 200 with `DISRUPTIVE`; `NOTF01` → 404; the lookup without a token → 401. Verify that `make smoke` passes

## 9. Documentation

- [x] 9.1 Add rows 17–22 to the README "Architecture decision record" table (design D1–D6), a demo section listing the scenario codes with the surname `Silva`, the note on recreating `.env`, and the future `LlmComposer` with verifier under next steps. Verify that the README renders and the rows match design.md
- [x] 9.2 Update the CLAUDE.md "Domain contracts and traps" or Commands section only if a new command or convention was introduced (for example, `TOOLS_API_TOKEN`). Verify that the documented commands run as written

## 10. Verification

- [x] 10.1 Run `make check` (ruff, import-linter, all api and mock-tools unit tests) and `make smoke` against a fresh stack (`make clean && make env && make up`). Verify that both pass and report the results faithfully

## 11. Review follow-ups

- [x] 11.1 Test response bounds in `test_tools_client.py`: a 300 KiB body and 201 events → `ToolUnavailable`; a body of exactly 200 events parses. Verify the tests fail before 11.2
- [x] 11.2 Stream tool responses with a 256 KiB cap and reject more than 200 events in `HttpToolsClient`. Verify that the 11.1 tests pass
- [x] 11.3 Test revision `0004_trip_assessments` (**expand**): upgrade creates the table, downgrade to `0003` drops it and keeps the seed. Verify the test fails before 11.4
- [x] 11.4 Add `trip_assessments` to `tables.py` and revision `0004`. Verify that the 11.3 test passes
- [x] 11.5 Test `SqlAssessmentLog` on SQLite: one appended row per call with the JSON reasons and rejections, aware `assessed_at`, and no name in any column; a database error raises. Verify the tests fail before 11.6
- [x] 11.6 Implement `ports/audit.py` (`AssessmentLog`) and `repositories/sql/assessments.py`. Verify that the 11.5 tests pass
- [x] 11.7 Test the service and router: brief lookup records the decision with request ID; not-found records nothing; a failing log still returns 200 and logs the error. Verify the tests fail before 11.8
- [x] 11.8 Record from `TripStatusService` (request ID passed by the router), wire `SqlAssessmentLog` in `composition.py`. Verify that the 11.7 tests pass and `make lint` keeps every contract
- [x] 11.9 Replace the `HUMAN_ASSISTANCE` text with a disabled "Talk to an agent" button (spec `passenger-web`). Verify with `CONF01` in the browser and that `make smoke` passes
- [x] 11.10 Add README ADR rows 23 (bounded responses) and 24 (assessment record), and update the "save the assessment" next step. Verify that the rows match design D7 and D15
- [x] 11.11 Run `make check` and `make smoke` on a fresh database; confirm `trip_assessments` gets a row per lookup. Verify that both pass and report the results faithfully

## Workflow follow-up

- Archive the change with `/opsx:archive` once review is done and `make check` passes.
