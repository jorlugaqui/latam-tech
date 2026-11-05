# Tasks

Branch first (`feat/add-recommendation-and-handoff`). TDD throughout: each "test" task is run and must fail for the expected reason before its implementation task. Run tests with `make test ARGS="..."`. Use exact edits (not blind text replacement) on files `ruff format` may have reflowed. Keep a note of AI output accepted, modified, or rejected for the AI Usage Note.

## 1. Dev containers and docs layout

- [x] 1.1 Rename compose services `tools` → `api-dev` and `mock-tools-tools` → `mock-tools-dev`; update the Makefile variables and CLAUDE.md mentions. Verify `make check` still runs both suites and `grep -rn "mock-tools-tools\|run --rm tools" Makefile docker-compose.yml CLAUDE.md` finds nothing
- [x] 1.2 Move the README "Architecture decision record" table to `docs/decisions.md` (unchanged rows 1–25) and link it from the README. Verify `git check-ignore docs/decisions.md` prints nothing and the README still renders

## 2. Schemas

- [x] 2.1 Test the upstream DTOs for `get_policy_rules` and `get_eligible_options` against the brief samples (REBOOK and REFUND shapes, optional fields, `ttl_seconds`). Verify the tests fail before 2.2
- [x] 2.2 Add `PolicyRules`, `PolicyRule`, `EligibleOptions`, `EligibleOption` to `schemas/tools.py`. Verify that the 2.1 tests pass
- [x] 2.3 Test `RecommendationRequest`/`HumanCaseRequest` (`extra="forbid"`, `option_id` pattern) and that the response models have no personal-data field. Verify the tests fail before 2.4
- [x] 2.4 Implement `schemas/recommendation.py` and `schemas/handoff.py` (D11). Verify that the 2.3 tests pass

## 3. Policy evaluation (pure)

- [x] 3.1 Test `conditions.py` (spec "Rule conditions are evaluated safely"): every brief condition, Kleene `AND`, unknown fact, unparsable condition, and injection strings that stay `UNKNOWN`. Verify the tests fail before 3.2
- [x] 3.2 Implement the tokenizer, parser (AST `Comparison`/`And`), and evaluator. Verify that the 3.1 tests pass
- [x] 3.3 Test the fact providers and entitlement evaluation: ABC123 → R3 `REBOOK_NO_FEE`, R5 `PRIORITY_HANDLING`; R1, R2, R4 do not apply. Verify the tests fail before 3.4
- [x] 3.4 Implement `services/policy/facts.py` and `entitlements.py`. Add the import-linter contract making `services.policy` and `services.options` pure. Verify that the 3.3 tests pass and `make lint` keeps every contract

## 4. Option selection (pure)

- [x] 4.1 Test each option specification and the selector: the O1–O3 matrix (O1 eligible; O2 `INSUFFICIENT_SEATS` + `FEE_CONFLICTS_ENTITLEMENT`; O3 `NOT_ENTITLED` + `LOW_CONFIDENCE`), `DEPARTS_TOO_EARLY` at 20:50, `WRONG_ROUTE`, `POLICY_SUPERSEDED`, ranking by confidence then departure. Verify the tests fail before 4.2
- [x] 4.2 Implement `services/options/specifications.py` and `selection.py`. Verify that the 4.1 tests pass

## 5. Verified trip access (refactor)

- [x] 5.1 Test `AssessmentLog.record` returning the record id (SQL and fake), and `TripAccess.verified_assessment` (surname mismatch, recording, `assessment_id` `null` when recording fails). Verify the new tests fail before 5.2
- [x] 5.2 Extract `services/trip_access.py` from `TripStatusService` and make `record` return the id. Verify that every existing trip-status, router, and service test passes unchanged

## 6. Recommendation service and tool reads

- [x] 6.1 Test `HttpToolsClient` policy and options reads with `httpx.MockTransport`: 200, policy 404 → `PolicyNotFound`, 503/invalid/oversized → `ToolUnavailable`. Verify the tests fail before 6.2
- [x] 6.2 Implement the reads and the `PolicyReader`/`OptionsReader` ports. Verify that the 6.1 tests pass
- [x] 6.3 Test `RecommendationService` with fakes, covering every `recommendation` scenario: brief `PROPOSED` with O1, `NOT_APPLICABLE` for CONF01/OKAY01 without policy or options calls, CANC01 `POLICY_UNAVAILABLE`, superseded policy option, TTL expiry reported and one refetch, options down, excluded options logged but not returned. Verify the tests fail before 6.4
- [x] 6.4 Implement `services/recommendation.py` and its templated explanation citing rules and the policy version. Verify that the 6.3 tests pass

## 7. Human hand-off (expand: `0005`)

- [x] 7.1 Test `case_states.transition` (allowed and rejected transitions). Verify the tests fail before 7.2
- [x] 7.2 Implement `schemas/case_states.py` (moved from `services/` so the repository can use it). Verify that the 7.1 tests pass
- [x] 7.3 Test revision `0005_human_cases` (**expand**) upgrade/downgrade and `SqlCaseRepository` on SQLite: insert `REQUESTED`, a second active insert for the same booking returns the existing case, `FAILED` clears the active slot, transitions only through the table. Verify the tests fail before 7.4
- [x] 7.4 Add `human_cases` to `tables.py`, revision `0005`, `ports/cases.py`, and `repositories/sql/cases.py`. Verify that the 7.3 tests pass
- [x] 7.5 Test `HttpCaseWriter` with `httpx.MockTransport`: 201 → created case; timeout/connect error/5xx → `HandoffIndeterminate`; 4xx/invalid → `HandoffRejected`; exactly one call (no retry); evidence absent from logs. Verify the tests fail before 7.6
- [x] 7.6 Implement `ports/handoff.py` and `HttpCaseWriter`. Add the contract "read-only services never import `companion.ports.handoff`". Verify that the 7.5 tests pass and `make lint` keeps every contract
- [x] 7.7 Test `HumanCaseService` with fakes, covering every `human-handoff` scenario: reasons (`OPTION_APPROVAL`, `ASSISTANCE_REQUIRED`, `STATUS_VERIFICATION`), 409s, evidence with `R3`, `R5`, `O1`, `E-1001`, `includes_minor` and no PII, intent recorded first, assessment-record failure → 503 without a tool call, 201/202/503 mapping, duplicate → 200 without a call, no retry after `INDETERMINATE`, retry after `FAILED`, logs without PII. Verify the tests fail before 7.8
- [x] 7.8 Implement `services/handoff.py`. Verify that the 7.7 tests pass

## 8. Presentation and wiring

- [x] 8.1 Test both routes with `TestClient` and fakes: 401 without calling tools, 422 without echo (including a client `relevance` field), 404 for wrong surname, 409 bodies, 201/200/202 status codes, 503 bodies, no PII in bodies; the OpenAPI contract test covers both routes. Verify the tests fail before 8.2
- [x] 8.2 Add the routes and error handlers; wire `RecommendationService`, `HumanCaseService`, `HttpCaseWriter`, and `SqlCaseRepository` in `composition.py`. Verify that the 8.1 tests pass and `make lint` keeps every contract

## 9. Mock tools

- [x] 9.1 Test the three tools and `CASERR` (spec `mock-tools`): DELAY policy, CANCELLATION 404, options per booking with time-shifted dates, `[]` for OKAY01, case 201 with `HC-` ids, CASERR 503, CASERR trip context and events mirroring ABC123. Verify the tests fail before 9.2
- [x] 9.2 Implement the fixtures and endpoints. Verify that the 9.1 tests pass and `make check-mock-tools` passes

## 10. Frontend, smoke, and docs

- [ ] 10.1 Implement the enabled buttons, recommendation view, "Request this option" (option id from a `data-option` attribute), case confirmation view, and in-flight disabling (spec `passenger-web`); keep booking and surname in memory only, reset on a new lookup. Verify manually in the browser with `ABC123` (O1 → case, repeat → same case), `CONF01` (agent), `CANC01` (agent), `CASERR` (indeterminate)
- [x] 10.2 Extend `scripts/smoke.sh`: ABC123 recommendation `PROPOSED` with `O1`; a case → 201 then 200 on repeat; `CASERR` case → 202. Verify `make smoke` passes on a fresh database
- [x] 10.3 Write `docs/future-work.md` (D14) and append rows 26–31 to `docs/decisions.md`. Rewrite the README around the problem, run instructions, demo codes (with `CASERR`), one end-to-end flow diagram, and the demo-vs-future automation matrix, linking both docs. Update the `passenger-web` main spec Purpose (it still says "shell only"). Verify the README fits about two printed pages and every link resolves

## 11. Verification

- [x] 11.1 Run `make check` and `make smoke` on a fresh database (`make clean && make up`), and confirm one `human_cases` row per booking after repeated requests. Verify that both pass and report the results faithfully

## Workflow follow-up

- Archive with `/opsx:archive` after review, the browser check, and a passing `make check`.
