# Spec Delta

## Purpose

Hands a passenger's situation to a person through a human case. In this version the case is the approval mechanism for every action: nothing is rebooked, refunded, or compensated without a person. Protects against duplicate cases and never retries an indeterminate outcome.

Classification: re-verification, choosing the reason, building the evidence, deduplication, and state transitions are **deterministic**; creating the case is a passenger-initiated, low-impact write; approving it is **human**. Business record: `docs/internal/disruption_companion.pdf` §1 item 4, §2 (`create_human_case` sample), §3, §4.

## ADDED Requirements

### Requirement: Hand-off endpoint requires the token and the booking owner
`POST /api/v1/trips/human-case` with `{"booking_id", "last_name", "option_id"?}` SHALL apply the same token, input validation, and surname check as the trip lookup: 401 before any tool call, 422 without echoing input, and the same 404 for an unknown booking or wrong surname. No case SHALL be created in those cases.

#### Scenario: Wrong surname creates nothing
- **WHEN** the body is `{"booking_id": "ABC123", "last_name": "Rojas", "option_id": "O1"}`
- **THEN** the response is 404 `{"error": "not_found"}`, the case tool is not called, and no case row exists

### Requirement: The server decides whether and why to escalate
The endpoint SHALL recompute the assessment and, for `DISRUPTIVE`, the recommendation. The reason SHALL be `OPTION_APPROVAL` when `option_id` names a currently eligible option, `ASSISTANCE_REQUIRED` for a `DISRUPTIVE` trip without `option_id`, and `STATUS_VERIFICATION` for an `UNVERIFIED` trip. Any other combination SHALL be rejected with 409 and no case.

#### Scenario: Approval request for the recommended option
- **WHEN** `ABC123` / `Silva` sends `option_id` `O1`
- **THEN** a case is created with reason `OPTION_APPROVAL`

#### Scenario: Option that is not eligible
- **WHEN** `ABC123` / `Silva` sends `option_id` `O2`
- **THEN** the response is 409 `{"error": "option_not_eligible"}` and no case is created

#### Scenario: Unverified trip
- **WHEN** `CONF01` / `Silva` sends no `option_id`
- **THEN** a case is created with reason `STATUS_VERIFICATION`

#### Scenario: Nothing to escalate
- **WHEN** `OKAY01` / `Silva` asks for a case
- **THEN** the response is 409 `{"error": "nothing_to_escalate"}` and no case is created

### Requirement: Evidence references verified data without personal data
The evidence SHALL contain the booking code, the `trip_assessments` record id, relevance, reasons with segment and event ids, `rules_version`, and, when a recommendation was computed, the policy version, entitlements with rule ids and approval flags, the chosen option snapshot with `options_expire_at`, excluded options with reasons, and the party composition (counts by type and whether it includes a minor). It MUST NOT contain names, surname, email, phone, document, or age.

#### Scenario: Brief evidence
- **WHEN** `ABC123` / `Silva` requests `O1`
- **THEN** the evidence sent contains `ABC123`, `R3`, `R5`, `POL-DELAY-2026-03`, `O1`, `E-1001`, and `"includes_minor": true`, and contains none of `Silva`, `María`, `maria.silva@example.com`, `12.345.678-9`

### Requirement: The intent is recorded before the case tool is called
Before calling the case tool, the endpoint SHALL have the assessment record id and SHALL record the request locally with status `REQUESTED`. If either record cannot be written, the response SHALL be 503 `{"error": "handoff_unavailable"}` and the case tool SHALL NOT be called.

#### Scenario: Assessment record fails
- **GIVEN** the assessment record cannot be written
- **WHEN** `ABC123` / `Silva` requests `O1`
- **THEN** the response is 503 `{"error": "handoff_unavailable"}` and the case tool is not called

#### Scenario: Local record fails
- **GIVEN** the case table cannot be written
- **WHEN** `ABC123` / `Silva` requests `O1`
- **THEN** the response is 503 `{"error": "handoff_unavailable"}` and the case tool is not called

### Requirement: Case outcomes follow an explicit state machine
The case status SHALL move only `REQUESTED → OPEN` (tool returned 201), `REQUESTED → INDETERMINATE` (timeout, connection error, 5xx, or a 201 whose body cannot be read), or `REQUESTED → FAILED` (any other response). Any other transition SHALL be rejected. `OPEN` returns 201 with `case_id`, `queue`, and `sla_minutes`; `INDETERMINATE` returns 202; `FAILED` returns 503 `{"error": "handoff_unavailable"}`.

#### Scenario: Case opened
- **GIVEN** the case tool returns 201 `{"case_id": "HC-4471", "queue": "DISRUPTION_L2", "sla_minutes": 45}`
- **WHEN** `ABC123` / `Silva` requests `O1`
- **THEN** the response is 201 with status `OPEN`, `case_id` `HC-4471`, and `sla_minutes` 45

#### Scenario: Illegal transition
- **GIVEN** a case in status `OPEN`
- **WHEN** it is moved to `INDETERMINATE`
- **THEN** the transition is rejected

### Requirement: Indeterminate outcomes are never retried
When the case tool times out or returns 5xx, the system SHALL NOT retry the call. The response SHALL be 202 with status `INDETERMINATE`, no `case_id`, and a message telling the passenger the request is being registered and to contact the call center if they hear nothing within the expected time.

#### Scenario: Case tool times out
- **GIVEN** the case tool returns 503 for `CASERR`
- **WHEN** `CASERR` / `Silva` requests `O1`
- **THEN** the response is 202 with status `INDETERMINATE`, the case tool was called exactly once, and the row stays `INDETERMINATE`

### Requirement: One active case per booking
While a booking has a case in `REQUESTED`, `OPEN`, or `INDETERMINATE`, a new request SHALL return that case with 200 and SHALL NOT call the case tool. This SHALL hold under concurrent requests. A `FAILED` case does not block a new request.

#### Scenario: Double click
- **WHEN** `ABC123` / `Silva` requests `O1` twice
- **THEN** the case tool is called once, the first response is 201 and the second is 200 with the same `case_id`

#### Scenario: Retry after an indeterminate outcome
- **GIVEN** `CASERR` has an `INDETERMINATE` case
- **WHEN** `CASERR` / `Silva` asks again
- **THEN** the response is 200 with status `INDETERMINATE` and the case tool is not called again

#### Scenario: Retry after a definite failure
- **GIVEN** `ABC123` has a `FAILED` case
- **WHEN** `ABC123` / `Silva` requests `O1`
- **THEN** a new case is created

### Requirement: Hand-off never logs personal data
The endpoint SHALL log the booking code, reason, case status, and `case_id` with the request ID, and MUST NOT log the request body, surname, names, contact data, or the evidence content beyond ids.

#### Scenario: Logs after a case
- **WHEN** `ABC123` / `Silva` requests `O1` and the logs are captured
- **THEN** the logs contain `ABC123`, `OPTION_APPROVAL`, and `OPEN`, and do not contain `Silva` or `María`
