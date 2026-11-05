# trip-status Specification

## Purpose
Lets a passenger look up their trip by booking code and last name and get one verified status: trip context, per-segment status, the disruption assessment, an explanation, and the next step.

Every step is **deterministic**: input validation, booking verification, data retrieval, mapping to the response, and choosing the next step. No step uses AI or takes an action. The assessment itself is specified in `disruption-assessment`. Business record: `docs/internal/disruption_companion.pdf` §1 items 1–2, §3 (personal data, least privilege), §4 (what may be shown).

## Requirements

### Requirement: Lookup endpoint requires the API token
`POST /api/v1/trips/lookup` SHALL require `Authorization: Bearer <token>` as specified in `api-authentication`. A missing or invalid token SHALL return the uniform 401 before any tool is called.

#### Scenario: No token
- **WHEN** a client sends `POST /api/v1/trips/lookup` with body `{"booking_id": "ABC123", "last_name": "Silva"}` and no `Authorization` header
- **THEN** the response is 401 `{"error": "unauthorized"}` and no tool is called

#### Scenario: Wrong token
- **WHEN** the same request is sent with `Authorization: Bearer wrong`
- **THEN** the response is 401 `{"error": "unauthorized"}` and no tool is called

### Requirement: Lookup input is validated
The JSON body SHALL contain `booking_id` (6 letters or digits, case-insensitive, normalized to upper case) and `last_name` (1 to 60 characters: letters, spaces, hyphens, apostrophes). Any other input SHALL return 422 as specified in `api-errors`, without echoing the submitted values and without calling any tool. The lookup MUST NOT accept these values in the URL or query string.

#### Scenario: Lower-case booking code
- **WHEN** the body is `{"booking_id": "abc123", "last_name": "Silva"}`
- **THEN** the lookup proceeds for booking `ABC123`

#### Scenario: Malformed booking code
- **WHEN** the body is `{"booking_id": "ABC-12", "last_name": "Silva"}`
- **THEN** the response is 422, the body does not contain `ABC-12`, and no tool is called

### Requirement: The last name must match a passenger on the booking
The lookup SHALL succeed only if `last_name`, after case folding, accent removal, and whitespace normalization, equals the trailing word or words of the `name` of at least one passenger on the booking. Otherwise it SHALL return 404 `{"error": "not_found"}`, identical in status, body, and headers to the response for an unknown booking.

#### Scenario: Matching surname without accents or case
- **GIVEN** booking `ABC123` with passenger `María Silva`
- **WHEN** `last_name` is `silva`
- **THEN** the response is 200

#### Scenario: Compound surname
- **GIVEN** a passenger named `Ana Silva Pérez`
- **WHEN** `last_name` is `Silva Perez`
- **THEN** the lookup succeeds

#### Scenario: Wrong surname
- **GIVEN** booking `ABC123`
- **WHEN** `last_name` is `Rojas`
- **THEN** the response is 404 `{"error": "not_found"}`, and the operational events tool is not called

#### Scenario: Unknown booking
- **GIVEN** the trip context tool returns 404 for `NOTF01`
- **WHEN** the body is `{"booking_id": "NOTF01", "last_name": "Silva"}`
- **THEN** the response is 404 `{"error": "not_found"}`, the same as for a wrong surname

### Requirement: Response contains the passenger-safe trip status
A successful lookup SHALL return 200 with `booking_id`; per passenger, `first_name` and `type`; per segment, `segment_id`, `flight_number`, `origin`, `destination`, scheduled and estimated departure and arrival, `status`, `delay_minutes`, `gate`, and `connection` to the next segment; the assessment (`relevance`, `reasons` with segment and event ids, `rules_version`, `assessed_at`); `explanation`; and `next_step`. No other field is returned.

#### Scenario: Brief booking response
- **WHEN** `ABC123` / `Silva` is looked up
- **THEN** passengers are `[{"first_name": "María", "type": "ADULT"}, {"first_name": "Tomás", "type": "CHILD"}]`, S1 has status `DELAYED`, `delay_minutes` 160, gate `24`, and connection `MISSED`, and relevance is `DISRUPTIVE`

### Requirement: Response never exposes personal or internal data
The lookup response MUST NOT contain `email`, `phone`, `document_id`, `loyalty_tier`, `age`, `passenger_id`, full names, `fare_conditions`, rejected events, or source names.

#### Scenario: No personal data or rejected evidence in the body
- **WHEN** `ABC123` / `Silva` is looked up
- **THEN** the response body contains none of `maria.silva@example.com`, `+56 9 8765 4321`, `12.345.678-9`, `GOLD`, `LEGACY_MIRROR`, `E-1012`

### Requirement: Times are returned as local times with their offset
Every time in the response SHALL be an ISO 8601 date-time with the UTC offset of the airport it refers to. `assessed_at` SHALL be in UTC.

#### Scenario: Brief S1 times
- **WHEN** `ABC123` / `Silva` is looked up
- **THEN** S1 `scheduled_departure` is `2026-09-15T14:30:00-03:00` and `estimated_arrival` is `2026-09-15T20:35:00-05:00`

### Requirement: Next step follows relevance
`next_step` SHALL be `RECOMMENDATION` when relevance is `DISRUPTIVE`, `HUMAN_ASSISTANCE` when it is `UNVERIFIED`, and `NONE` otherwise. `next_step` is a hint for the page only. A later recommendation or action MUST recompute the assessment on the server and MUST NOT trust a client-supplied relevance or next step.

#### Scenario: Disruptive brief case
- **WHEN** `ABC123` / `Silva` is looked up
- **THEN** `next_step` is `RECOMMENDATION`

#### Scenario: Conflicting sources
- **WHEN** `CONF01` / `Silva` is looked up
- **THEN** `next_step` is `HUMAN_ASSISTANCE`

#### Scenario: On-time trip
- **WHEN** `OKAY01` / `Silva` is looked up
- **THEN** `next_step` is `NONE`

### Requirement: Upstream failures are handled without guessing
If the trip context tool fails (timeout, 5xx, or a response that does not match the contract), the lookup SHALL return 503 `{"error": "trip_context_unavailable"}`. If only the operational events tool fails, the lookup SHALL return 200 with the trip context, every segment `UNVERIFIED`, relevance `UNVERIFIED` with reason `EVENTS_UNAVAILABLE`, and `next_step` `HUMAN_ASSISTANCE`. Read tools SHALL be called with a timeout and are not retried.

#### Scenario: Trip context unavailable
- **GIVEN** the trip context tool returns 503 for `CTXERR`
- **WHEN** `CTXERR` / `Silva` is looked up
- **THEN** the response is 503 `{"error": "trip_context_unavailable"}`

#### Scenario: Events unavailable
- **GIVEN** the operational events tool returns 503 for the segments of `EVTERR`
- **WHEN** `EVTERR` / `Silva` is looked up
- **THEN** the response is 200 with the segments listed, relevance `UNVERIFIED`, reason `EVENTS_UNAVAILABLE`, and no delay or cancellation reported

#### Scenario: Tool timeout
- **GIVEN** the trip context tool does not answer within the configured timeout
- **WHEN** a lookup is made
- **THEN** the response is 503 `{"error": "trip_context_unavailable"}` and the tool was called once

### Requirement: Lookups never log personal data
The lookup MUST NOT log the request body, `last_name`, passenger names, email, phone, or `document_id`. It SHALL log the booking code, relevance, reason codes, `rules_version`, and the ids and reasons of rejected events, together with the request ID.

#### Scenario: Surname absent from logs
- **WHEN** `ABC123` / `Silva` is looked up and the logs are captured
- **THEN** the captured logs contain `ABC123`, `DISRUPTIVE`, `E-1012`, and `SOURCE_DEGRADED`, and do not contain `Silva`, `María`, or `maria.silva@example.com`

### Requirement: Upstream responses are bounded
A tool response larger than 256 KiB, or an events response with more than 200 events, SHALL be treated as a failure of that tool and handled as in "Upstream failures are handled without guessing". The response body SHALL NOT be read past the size limit.

#### Scenario: Oversized events response
- **GIVEN** the operational events tool returns 201 events for `ABC123`
- **WHEN** `ABC123` / `Silva` is looked up
- **THEN** the response is 200 with relevance `UNVERIFIED` and reason `EVENTS_UNAVAILABLE`

#### Scenario: Oversized trip context
- **GIVEN** the trip context tool returns a 300 KiB body
- **WHEN** a lookup is made
- **THEN** the response is 503 `{"error": "trip_context_unavailable"}`

### Requirement: Every assessment is recorded
Each lookup that reaches an assessment SHALL append one record with the booking code, relevance, reasons with segment and event ids, rejected event ids with their reasons, `rules_version`, `assessed_at`, and the request ID. The record MUST NOT contain the surname, names, contact or document data. The application never updates or deletes records; in this demo they are kept indefinitely.

#### Scenario: Brief lookup is recorded
- **WHEN** `ABC123` / `Silva` is looked up with request ID `req-1`
- **THEN** one record exists with booking `ABC123`, relevance `DISRUPTIVE`, reasons `LONG_DELAY` and `MISSED_CONNECTION`, rejected `E-1012` with `SOURCE_DEGRADED`, `rules_version` `REL-2026-09`, and request ID `req-1`, and it contains neither `Silva` nor `María`

#### Scenario: Unknown booking is not recorded
- **WHEN** `NOTF01` / `Silva` or `ABC123` / `Rojas` is looked up
- **THEN** no record is written

### Requirement: A failed record does not block the lookup
If the assessment record cannot be written, the lookup SHALL still return its result and log the failure, because a lookup executes no action.

#### Scenario: Recording fails
- **GIVEN** the assessment record cannot be written
- **WHEN** `ABC123` / `Silva` is looked up
- **THEN** the response is 200 with relevance `DISRUPTIVE` and the failure is logged
