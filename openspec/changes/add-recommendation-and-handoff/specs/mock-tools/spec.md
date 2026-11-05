# Spec Delta

## ADDED Requirements

### Requirement: Policy rules follow the brief's contract
`POST /tools/get_policy_rules` with `{"scenario": "<name>"}` SHALL require the tools token and return the brief's `get_policy_rules` shape (`scenario`, `version`, `effective_from`, `rules` with `rule_id`, `condition`, `entitlement`, `requires_human_approval`, and `_meta` with `retrieved_at` and `superseded_versions`). `DELAY` returns the brief's `POL-DELAY-2026-03`; any other scenario returns 404 `{"error": "POLICY_NOT_FOUND"}`.

#### Scenario: Delay policy
- **WHEN** `{"scenario": "DELAY"}` is requested
- **THEN** the body has `version` `POL-DELAY-2026-03`, rules R1 to R5 as in the brief, and `superseded_versions` `["POL-DELAY-2025-11"]`

#### Scenario: Cancellation has no policy
- **WHEN** `{"scenario": "CANCELLATION"}` is requested
- **THEN** the response is 404 `{"error": "POLICY_NOT_FOUND"}`

### Requirement: Eligible options follow the brief's contract
`POST /tools/get_eligible_options` with a trip context body SHALL require the tools token and return `options` (`option_id`, `type`, and for `REBOOK` `flight_number`, `origin`, `destination`, `date`, `departure`, `fare_difference`, optional `currency`, `seats_available`; plus `policy_ref` and `confidence`) and `_meta` with `retrieved_at` and `ttl_seconds` 120. The scenario is chosen by the body's `booking_id`; option dates move with the request date like segment dates.

#### Scenario: Brief options
- **WHEN** the `ABC123` trip context is posted
- **THEN** the body contains O1 (LA2412, 08:15 next day, 4 seats, no fare difference, `HIGH`), O2 (LA2450, 23:40, 1 seat, 180000 CLP, `MEDIUM`), and O3 (`REFUND`, `POL-REFUND-2026-01`, `LOW`), with `ttl_seconds` 120

#### Scenario: Booking without options
- **WHEN** the `OKAY01` trip context is posted
- **THEN** the body has `options` `[]`

### Requirement: Human case creation follows the brief's contract
`POST /tools/create_human_case` with `{"reason", "evidence"}` SHALL require the tools token and return 201 `{"case_id", "queue": "DISRUPTION_L2", "sla_minutes": 45}` with a new `case_id` per call. When `evidence.booking_id` is `CASERR`, it SHALL return 503 `{"error": "UPSTREAM_TIMEOUT"}`. It keeps no state between calls.

#### Scenario: Case created
- **WHEN** a case is posted for `ABC123`
- **THEN** the response is 201 with a `case_id` starting `HC-`, `queue` `DISRUPTION_L2`, and `sla_minutes` 45

#### Scenario: Indeterminate outcome fixture
- **WHEN** a case is posted for `CASERR`
- **THEN** the response is 503 `{"error": "UPSTREAM_TIMEOUT"}`

## MODIFIED Requirements

### Requirement: Scenario catalog
The service SHALL serve exactly eleven scenarios: `ABC123`, `OKAY01`, `GATE01`, `CONF01`, `STAL01`, `CANC01`, `NITE01`, `NOTF01`, `CTXERR`, `EVTERR`, `CASERR` (full catalog in design D9 of add-trip-status and D10 of add-recommendation-and-handoff). `CASERR` is `ABC123` with its own segment ids, whose case creation returns 503. Each uses the brief's passengers and SCL→LIM→MEX route unless a scenario below says otherwise. Segment ids are `S1`/`S2` for `ABC123` and `<code>-S1`/`<code>-S2` for the others.

#### Scenario: On-time fixture
- **WHEN** events for `["OKAY01-S1", "OKAY01-S2"]` are requested
- **THEN** the body contains fresh OPS_CORE STATUS events `ON_TIME` for `OKAY01-S1` and `SCHEDULED` for `OKAY01-S2`, and nothing else

#### Scenario: Gate change fixture
- **WHEN** events for `["GATE01-S1", "GATE01-S2"]` are requested
- **THEN** the body contains the `OKAY01` events for these segments plus an AIRPORT_FEED GATE_CHANGE to gate `31` for `GATE01-S1`

#### Scenario: Conflict fixture
- **WHEN** events for `["CONF01-S1", "CONF01-S2"]` are requested
- **THEN** the body contains a fresh OPS_CORE DELAY of 90 minutes with `new_departure` `16:00` and a fresh AIRPORT_FEED STATUS `ON_TIME`, both for `CONF01-S1`, and neither source is degraded

#### Scenario: Stale fixture
- **WHEN** events for `["STAL01-S1", "STAL01-S2"]` are requested
- **THEN** every event has `recorded_at` 2 hours before `_meta.retrieved_at`

#### Scenario: Cancellation fixture
- **WHEN** events for `["CANC01-S1", "CANC01-S2"]` are requested
- **THEN** the body contains an OPS_CORE event for `CANC01-S1` with `type` `STATUS` and `status` `CANCELLED`, and no `new_departure`

#### Scenario: Overnight fixture
- **WHEN** the trip context for `NITE01` is requested
- **THEN** S1 has `scheduled_departure` `20:25` and `scheduled_arrival` `22:30`, and S2 has `date` equal to S1's `date` and `scheduled_departure` `23:50`

#### Scenario: Upstream outage fixture
- **WHEN** events for `["EVTERR-S1", "EVTERR-S2"]` are requested
- **THEN** the response is 503 `{"error": "UPSTREAM_UNAVAILABLE"}`

#### Scenario: Trip context outage fixture
- **WHEN** the trip context for `CTXERR` is requested
- **THEN** the response is 503 `{"error": "UPSTREAM_UNAVAILABLE"}`

#### Scenario: Case outage fixture
- **WHEN** the trip context for `CASERR` is requested
- **THEN** it matches `ABC123` except for `booking_id` and segment ids `CASERR-S1`/`CASERR-S2`, and its events and options mirror `ABC123`'s

