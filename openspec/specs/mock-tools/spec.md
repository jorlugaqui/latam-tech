# mock-tools Specification

## Purpose
Serves the read tool contracts `get_trip_context` and `get_operational_events` from the brief, with a fixed catalog of happy-path and failure scenarios selected by booking code, so the API can be built and demonstrated without real airline systems.

Every step is **deterministic**: each scenario returns fixed data. Business record: `docs/internal/disruption_companion.pdf` §2 (tool table, sample payloads; "si trabajas con mocks propios, mantén estos contratos").

## Requirements

### Requirement: Tool endpoints require the tools token
`POST /tools/get_trip_context` and `POST /tools/get_operational_events` SHALL require `Authorization: Bearer <tools token>`, compared in constant time. The tools token is read from an environment variable and is different from the API token. Missing or wrong tokens SHALL return 401. `/health/live` stays public. The service SHALL refuse to start without a tools token of at least 32 characters.

#### Scenario: Tool call without token
- **WHEN** a client sends `POST /tools/get_trip_context` with `{"booking_id": "ABC123"}` and no `Authorization` header
- **THEN** the response is 401

#### Scenario: API token is not accepted
- **WHEN** the request carries the API token instead of the tools token
- **THEN** the response is 401

### Requirement: Trip context follows the brief's contract
`POST /tools/get_trip_context` with `{"booking_id": "<code>"}` SHALL return 200 with a body that has the field names and nesting of the brief's `get_trip_context` sample (`booking_id`, `passengers`, `segments`, `fare_conditions`, `_meta`). An unknown booking code SHALL return 404 `{"error": "BOOKING_NOT_FOUND"}`.

#### Scenario: Brief booking
- **WHEN** `ABC123` is requested
- **THEN** the body matches the brief's sample, including `_meta.completeness` `PARTIAL` and `missing_fields` `["fare_conditions.change_penalty_amount"]`, with `_meta.retrieved_at` equal to the request time

#### Scenario: Code not in the catalog
- **WHEN** `ZZZ999` is requested
- **THEN** the response is 404 `{"error": "BOOKING_NOT_FOUND"}`

### Requirement: Operational events follow the brief's contract
`POST /tools/get_operational_events` with `{"segment_ids": [...]}` SHALL return 200 with `events` (`event_id`, `segment_id`, `type` among `DELAY`, `GATE_CHANGE`, `STATUS`, `source`, `recorded_at`, and per type `delay_minutes`, `new_departure`, `gate`, `status`) and `_meta` (`retrieved_at`, `sources_available`, `sources_degraded`). Cancellations use `type` `STATUS` with `status` `CANCELLED`. Segment ids not in the catalog SHALL yield no events.

#### Scenario: Brief events
- **WHEN** `["S1", "S2"]` is requested
- **THEN** the body contains `E-1001`, `E-1007`, `E-1012`, `E-2003` as in the brief, with `sources_degraded` `["LEGACY_MIRROR"]`

#### Scenario: Unknown segments
- **WHEN** `["NOPE-S1"]` is requested
- **THEN** the response is 200 with `events` `[]`

### Requirement: Timestamps are relative to the request time
Each scenario is written against the brief's reference instant `2026-09-15T11:02:33Z`. When served, every UTC instant SHALL be shifted so that `_meta.retrieved_at` equals the request time, keeping every other instant at the same distance from it, and every segment `date` SHALL move by the same number of whole days. Local scheduled times SHALL NOT change. The clock is injectable for tests.

#### Scenario: Freshness survives a live demo
- **GIVEN** the clock reads `2026-11-04T15:00:00Z`
- **WHEN** events for `["S1", "S2"]` are requested
- **THEN** `E-1001.recorded_at` is `2026-11-04T14:45:27Z` (14 min 33 s before retrieval, as in the brief) and S1's `date` in the trip context is `2026-11-04`

### Requirement: Scenario catalog
The service SHALL serve exactly ten scenarios: `ABC123`, `OKAY01`, `GATE01`, `CONF01`, `STAL01`, `CANC01`, `NITE01`, `NOTF01`, `CTXERR`, `EVTERR` (full catalog in design D9). Each uses the brief's passengers and SCL→LIM→MEX route unless a scenario below says otherwise. Segment ids are `S1`/`S2` for `ABC123` and `<code>-S1`/`<code>-S2` for the others.

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
