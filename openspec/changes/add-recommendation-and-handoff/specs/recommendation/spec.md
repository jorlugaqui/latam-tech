# Spec Delta

## Purpose

Turns a verified disruption into a policy-backed proposal: which entitlements the versioned policy grants and which eligible options satisfy them. It never executes anything; in v1 every proposal is approved by a person through `human-handoff`.

Every step is **deterministic**: re-verification, recomputing the assessment, choosing the policy scenario, evaluating rule conditions, filtering and ranking options. No step uses AI. Business record: `docs/internal/disruption_companion.pdf` §1 item 3, §2 (`get_policy_rules`, `get_eligible_options` samples), §4.

Unless a scenario says otherwise, scenarios use `ABC123` / `Silva`, the brief's policy `POL-DELAY-2026-03` (R1–R5) and options O1–O3 (`ttl_seconds` 120), assessed at `2026-09-15T11:03:00Z`.

## ADDED Requirements

### Requirement: Recommendation endpoint requires the token and the booking owner
`POST /api/v1/trips/recommendation` with `{"booking_id", "last_name"}` SHALL apply the same token, input validation, and surname check as the trip lookup (spec `trip-status`): 401 before any tool call, 422 without echoing input, and the same 404 for an unknown booking or a wrong surname.

#### Scenario: Wrong surname
- **WHEN** the body is `{"booking_id": "ABC123", "last_name": "Rojas"}`
- **THEN** the response is 404 `{"error": "not_found"}` and neither the policy nor the options tool is called

#### Scenario: No token
- **WHEN** the request has no `Authorization` header
- **THEN** the response is 401 and no tool is called

### Requirement: The assessment is recomputed on the server
The endpoint SHALL recompute the disruption assessment from fresh tool data and record it (spec `trip-status`, "Every assessment is recorded"). It MUST NOT accept a relevance, reason, or option from the client.

#### Scenario: Client cannot assert relevance
- **WHEN** the body includes `"relevance": "DISRUPTIVE"`
- **THEN** the response is 422

### Requirement: Only disruptive trips get a recommendation
When the recomputed relevance is not `DISRUPTIVE`, the response SHALL be 200 with `status` `NOT_APPLICABLE`, no entitlements, no options, and the `next_step` of the assessment. The policy and options tools SHALL NOT be called.

#### Scenario: Unverified trip
- **WHEN** `CONF01` / `Silva` asks for a recommendation
- **THEN** `status` is `NOT_APPLICABLE`, `next_step` is `HUMAN_ASSISTANCE`, and no options are returned

#### Scenario: On-time trip
- **WHEN** `OKAY01` / `Silva` asks for a recommendation
- **THEN** `status` is `NOT_APPLICABLE` and `next_step` is `NONE`

### Requirement: The policy scenario follows the assessment reasons
The policy scenario SHALL be `DELAY` when the reasons include `MISSED_CONNECTION` or `LONG_DELAY` and no `CANCELLATION`, and `CANCELLATION` when they include `CANCELLATION`. If no policy exists for the scenario, or the policy tool fails, the response SHALL be 200 with `status` `NEEDS_AGENT`, reason `POLICY_UNAVAILABLE`, no options, and `next_step` `HUMAN_ASSISTANCE`.

#### Scenario: Cancellation has no policy
- **GIVEN** the policy tool returns not found for `CANCELLATION`
- **WHEN** `CANC01` / `Silva` asks for a recommendation
- **THEN** `status` is `NEEDS_AGENT` with reason `POLICY_UNAVAILABLE` and `next_step` `HUMAN_ASSISTANCE`

### Requirement: The policy version must be in effect
The policy SHALL be used only if its `effective_from` is on or before the assessment date. The response SHALL report the policy `version`. An option whose `policy_ref` names a version listed in `superseded_versions` SHALL be excluded with reason `POLICY_SUPERSEDED`.

#### Scenario: Version reported
- **WHEN** `ABC123` / `Silva` asks for a recommendation
- **THEN** the response reports `policy_version` `POL-DELAY-2026-03`

#### Scenario: Option on a superseded policy
- **GIVEN** an option with `policy_ref` `POL-DELAY-2025-11`
- **WHEN** the recommendation is computed
- **THEN** that option is excluded with reason `POLICY_SUPERSEDED`

### Requirement: Rule conditions are evaluated safely
Each rule `condition` SHALL be parsed as `<fact> <op> <literal>` clauses (a bare `<fact>` means `<fact> == true`, as in R2) joined by `AND`, with `op` in `>=`, `>`, `<=`, `<`, `==`, and evaluated over the known facts `delay_minutes`, `missed_connection`, `international`, `compensation_requested`, `group_includes_minor`. A condition MUST NOT be executed as code. An unknown fact is UNKNOWN; `AND` uses three-valued logic; a rule applies only when its condition is TRUE.

#### Scenario: Brief rules for ABC123
- **GIVEN** facts `delay_minutes` 160, `missed_connection` true, `international` unknown, `compensation_requested` false, `group_includes_minor` true
- **WHEN** the rules are evaluated
- **THEN** R1 is FALSE, R2 is FALSE (because `160 >= 240` is FALSE), R3 is TRUE, R4 is FALSE, and R5 is TRUE

#### Scenario: Unknown fact makes a rule unknown
- **GIVEN** a rule with condition `is_vip == true`
- **WHEN** the rules are evaluated
- **THEN** that rule is UNKNOWN, does not apply, and the response lists it under `unevaluated_rules`

#### Scenario: Code is never executed
- **GIVEN** a rule with condition `__import__('os').system('x')`
- **WHEN** the rules are evaluated
- **THEN** the rule is UNKNOWN and nothing is executed

### Requirement: Entitlements come only from applying rules
The entitlements SHALL be the `entitlement` of each applying rule, with its `rule_id` and `requires_human_approval`. Facts SHALL come from the recomputed assessment and the trip: `delay_minutes` is the largest accepted delay, `missed_connection` is true if any connection is `MISSED`, `group_includes_minor` is true if any passenger type is `CHILD` or `INFANT`, `compensation_requested` is false (not collected in this version), and `international` is unknown.

#### Scenario: Brief entitlements
- **WHEN** `ABC123` / `Silva` asks for a recommendation
- **THEN** the entitlements are `REBOOK_NO_FEE` (R3, no approval required) and `PRIORITY_HANDLING` (R5, approval required)

### Requirement: Options are filtered with a reason for every exclusion
Each option SHALL be kept only if every check passes, and each excluded option SHALL carry all its failed reason codes: `NOT_ENTITLED` (type not covered; `REFUND` never in this version), `INSUFFICIENT_SEATS` (fewer seats than passengers), `FEE_CONFLICTS_ENTITLEMENT` (fare difference under `REBOOK_NO_FEE`), `WRONG_ROUTE`, `DEPARTS_TOO_EARLY` (before arrival plus MCT), `POLICY_SUPERSEDED`, and `LOW_CONFIDENCE`.

#### Scenario: Brief options
- **WHEN** `ABC123` / `Silva` asks for a recommendation
- **THEN** only O1 is eligible; O2 is excluded with `INSUFFICIENT_SEATS` and `FEE_CONFLICTS_ENTITLEMENT`; O3 is excluded with `NOT_ENTITLED` and `LOW_CONFIDENCE`

#### Scenario: Option departs before the passenger can connect
- **GIVEN** an option LIM→MEX departing `2026-09-15` at 20:50, and S1 estimated to arrive at 20:35 with a 60-minute MCT
- **WHEN** the recommendation is computed
- **THEN** that option is excluded with `DEPARTS_TOO_EARLY`

### Requirement: Expired options are fetched again
Options SHALL be used only within `_meta.retrieved_at` plus `ttl_seconds`. If they have expired by the time they are evaluated, they SHALL be fetched once more; if they are still expired, the response SHALL be `NEEDS_AGENT` with reason `OPTIONS_EXPIRED`. The response SHALL report `options_expire_at`.

#### Scenario: Expiry reported
- **GIVEN** options retrieved at `2026-09-15T11:02:35Z` with `ttl_seconds` 120
- **WHEN** the recommendation is computed at `11:03:00Z`
- **THEN** `options_expire_at` is `2026-09-15T11:04:35Z`

#### Scenario: Stale options are refetched
- **GIVEN** the first options response is already expired and the second is fresh
- **WHEN** the recommendation is computed
- **THEN** the options tool is called twice and the fresh options are used

### Requirement: Eligible options are ranked and the result states the approval
Eligible options SHALL be ordered by confidence (`HIGH` before `MEDIUM`), then by earliest departure. The response SHALL have `status` `PROPOSED` when at least one option is eligible and `NEEDS_AGENT` with reason `NO_ELIGIBLE_OPTION` otherwise. In this version `approval` SHALL always be `HUMAN_REQUIRED`.

#### Scenario: Brief recommendation
- **WHEN** `ABC123` / `Silva` asks for a recommendation
- **THEN** `status` is `PROPOSED`, the first option is O1 (LA2412, `2026-09-16` 08:15 LIM), and `approval` is `HUMAN_REQUIRED`

### Requirement: Recommendation response is passenger-safe
The response SHALL contain `status`, `reason`, `policy_version`, `entitlements` (code, rule id, approval flag), eligible `options` (id, type, flight, route, local departure with offset, fare difference and currency, confidence), `options_expire_at`, `approval`, an explanation citing the policy, and `next_step`. Excluded options and their reasons SHALL be logged but not returned. It MUST NOT contain personal data.

#### Scenario: Excluded options are not shown
- **WHEN** `ABC123` / `Silva` asks for a recommendation
- **THEN** the body contains `O1`, `POL-DELAY-2026-03`, and `R3`, and contains neither `O2`, `O3`, `maria.silva@example.com`, nor `Silva`

### Requirement: Upstream failures in recommendation fail closed
If the trip context tool fails, the response SHALL be 503 `{"error": "trip_context_unavailable"}`. If the options tool fails or returns a response outside its contract or over the size limit, the response SHALL be `NEEDS_AGENT` with reason `OPTIONS_UNAVAILABLE`. Read tools are not retried except the single TTL refetch.

#### Scenario: Options tool down
- **GIVEN** the options tool returns 503
- **WHEN** `ABC123` / `Silva` asks for a recommendation
- **THEN** `status` is `NEEDS_AGENT` with reason `OPTIONS_UNAVAILABLE` and `next_step` `HUMAN_ASSISTANCE`
