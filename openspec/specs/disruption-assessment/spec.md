# disruption-assessment Specification

## Purpose
Decides from booking and operational events whether a trip had a relevant change and what it implies operationally. It reconciles sources, computes impact on connections, and applies versioned relevance rules. Policy entitlements are out of scope.

Every step in this capability is **deterministic**. No step uses AI. Business record: `docs/internal/disruption_companion.pdf` §1 items 1–2, §2 (sample payloads), §4 (ambiguities). Thresholds and windows are documented assumptions (proposal, Assumptions).

Unless a scenario says otherwise, scenarios use the brief's `ABC123` payloads, rule set `REL-2026-09` (freshness window 30 min, `MINOR_DELAY` 15 min, `LONG_DELAY` 120 min, MCT 60 min at SCL and LIM, 90 min at MEX), and an assessment time (`now`) of `2026-09-15T11:03:00Z`.

## Requirements

### Requirement: Only accepted evidence is used
An event SHALL be accepted only if its source is in `_meta.sources_available`, is not in `_meta.sources_degraded`, and its `recorded_at` is no more than the rule set's freshness window before `now`. Rejected events MUST NOT influence the assessment, and each rejection SHALL be recorded with a reason code (`SOURCE_DEGRADED`, `SOURCE_UNKNOWN`, `STALE`).

#### Scenario: Degraded source is discarded
- **GIVEN** event `E-1012` (S1, STATUS `ON_TIME`, source `LEGACY_MIRROR`, recorded `2026-09-15T09:30:00Z`) and `LEGACY_MIRROR` listed in `sources_degraded`
- **WHEN** the trip is assessed
- **THEN** `E-1012` is rejected with reason `SOURCE_DEGRADED` and S1's status is derived from `E-1001` only

#### Scenario: Stale event is discarded
- **GIVEN** an OPS_CORE STATUS event for S1 recorded at `2026-09-15T10:20:00Z`
- **WHEN** the trip is assessed at `2026-09-15T11:03:00Z`
- **THEN** the event is rejected with reason `STALE`

#### Scenario: Source not listed as available
- **GIVEN** an event from source `CREW_APP`, which is not in `sources_available`
- **WHEN** the trip is assessed
- **THEN** the event is rejected with reason `SOURCE_UNKNOWN`

### Requirement: Newer reports from the same source supersede older ones
When one accepted source reports several timing events (DELAY or STATUS) for a segment, only the one with the latest `recorded_at` SHALL be used for that segment.

#### Scenario: Updated delay from the same source
- **GIVEN** two OPS_CORE DELAY events for S1: 90 min recorded at `10:40:00Z` and 160 min recorded at `10:48:00Z`
- **WHEN** the trip is assessed
- **THEN** S1 is `DELAYED` by 160 minutes

### Requirement: Conflicting trusted sources make a segment unverified
If accepted timing events from different sources disagree about a segment's state (on schedule, delayed by a given number of minutes, or cancelled), that segment's status SHALL be `UNVERIFIED` with reason `SOURCE_CONFLICT`, and the system MUST NOT pick one of them.

#### Scenario: OPS_CORE and AIRPORT_FEED disagree
- **GIVEN** an accepted OPS_CORE DELAY of 90 min for S1 recorded at `10:50:00Z` and an accepted AIRPORT_FEED STATUS `ON_TIME` for S1 recorded at `10:52:00Z`
- **WHEN** the trip is assessed
- **THEN** S1 is `UNVERIFIED`, the reasons include `SOURCE_CONFLICT` citing both event ids, and no delay is reported for S1

### Requirement: Delay reports must be internally consistent
When a DELAY event carries both `delay_minutes` and `new_departure`, the scheduled departure plus `delay_minutes` SHALL equal `new_departure` in local time, rolling over midnight if needed. Otherwise the segment SHALL be `UNVERIFIED` with reason `INCONSISTENT_EVENT`.

#### Scenario: Consistent brief event
- **GIVEN** S1 scheduled at 14:30 and `E-1001` with `delay_minutes` 160 and `new_departure` 17:10
- **WHEN** the trip is assessed
- **THEN** S1 is `DELAYED` by 160 minutes with estimated departure `2026-09-15T17:10:00-03:00`

#### Scenario: Inconsistent event
- **GIVEN** S1 scheduled at 14:30 and a DELAY event with `delay_minutes` 160 and `new_departure` 16:00
- **WHEN** the trip is assessed
- **THEN** S1 is `UNVERIFIED` with reason `INCONSISTENT_EVENT`

### Requirement: Times are resolved with airport time zones
Segment times SHALL be read as local time at the airport they refer to: departure at the origin, arrival at the destination. They SHALL be converted with that airport's IANA time zone and compared as UTC instants. The arrival is the first matching local time after departure. If an airport has no time zone in the reference data, segments touching it SHALL be `UNVERIFIED` with reason `AIRPORT_UNKNOWN`.

#### Scenario: Brief segment in two time zones
- **GIVEN** S1 SCL→LIM on `2026-09-15`, departing 14:30 and arriving 17:55
- **WHEN** times are resolved
- **THEN** departure is `2026-09-15T14:30:00-03:00` (America/Santiago) and arrival is `2026-09-15T17:55:00-05:00` (America/Lima)

#### Scenario: Airport missing from reference data
- **GIVEN** a segment whose destination is `XXX`, which is not in the airport reference data
- **WHEN** the trip is assessed
- **THEN** that segment is `UNVERIFIED` with reason `AIRPORT_UNKNOWN`

### Requirement: Estimated arrival follows the delay
For a delayed segment, the estimated arrival SHALL be the scheduled arrival plus `delay_minutes`. This assumes the flight duration does not change.

#### Scenario: Brief S1 estimated arrival
- **GIVEN** S1 arriving at 17:55 Lima time and delayed by 160 minutes
- **WHEN** the impact is computed
- **THEN** S1's estimated arrival is `2026-09-15T20:35:00-05:00`

### Requirement: Connections are checked against the minimum connection time
For each pair of consecutive segments where the first one's destination is the second one's origin, the connection SHALL be `MISSED` when the first segment's estimated (or scheduled) arrival plus the MCT of the connecting airport is later than the second segment's departure. Otherwise it SHALL be `OK`. If either segment is `UNVERIFIED`, the connection SHALL be `UNKNOWN`.

#### Scenario: Brief missed connection
- **GIVEN** S1 estimated to arrive in LIM at `20:35-05:00` and S2 departing LIM at `2026-09-15T19:05:00-05:00`, with a 60-minute MCT at LIM
- **WHEN** the impact is computed
- **THEN** the connection S1→S2 is `MISSED`

#### Scenario: Delayed arrival after midnight
- **GIVEN** S1 SCL→LIM on `2026-09-15`, departing 20:25 and arriving 22:30, delayed 120 minutes, and S2 LIM→MEX on `2026-09-15` departing 23:50
- **WHEN** the impact is computed
- **THEN** S1's estimated arrival is `2026-09-16T00:30:00-05:00` and the connection S1→S2 is `MISSED`

#### Scenario: Delay absorbed by the layover
- **GIVEN** S1 arriving in LIM at 17:55 and delayed 30 minutes, and S2 departing LIM at 20:00, with a 60-minute MCT (estimated arrival 18:25 plus 60 minutes is 19:25)
- **WHEN** the impact is computed
- **THEN** the connection S1→S2 is `OK`

### Requirement: A cancellation makes later segments unreachable
A segment with an accepted STATUS of `CANCELLED` SHALL be `CANCELLED`, and every later segment of the itinerary SHALL have connection status `UNREACHABLE`.

#### Scenario: First segment cancelled
- **GIVEN** an accepted OPS_CORE STATUS `CANCELLED` for S1
- **WHEN** the trip is assessed
- **THEN** S1 is `CANCELLED`, the connection to S2 is `UNREACHABLE`, and no estimated times are reported for S1

### Requirement: Relevance tiers and precedence
The assessment SHALL have exactly one relevance: `DISRUPTIVE` if any enabled `DISRUPTIVE` criterion matches; otherwise `UNVERIFIED` if any segment needed for the itinerary is `UNVERIFIED` or has no accepted timing evidence; otherwise `INFORMATIONAL` if any `INFORMATIONAL` criterion matches; otherwise `NONE`. The reasons SHALL be the matched criteria of the resulting tier (or, for `UNVERIFIED`, the segment reasons), each with its segment and the event ids it relies on.

#### Scenario: Brief case is disruptive for two reasons
- **WHEN** `ABC123` is assessed
- **THEN** relevance is `DISRUPTIVE`, and the reasons are `MISSED_CONNECTION` (S1→S2, evidence `E-1001`) and `LONG_DELAY` (S1, evidence `E-1001`)

#### Scenario: Gate change only
- **GIVEN** accepted OPS_CORE STATUS `ON_TIME` for S1 and S2 and an accepted AIRPORT_FEED GATE_CHANGE to gate `24` for S1
- **WHEN** the trip is assessed
- **THEN** relevance is `INFORMATIONAL` with reason `GATE_CHANGE` (S1)

#### Scenario: Nothing to report
- **GIVEN** accepted OPS_CORE STATUS `ON_TIME` for S1 and `SCHEDULED` for S2, and no other events
- **WHEN** the trip is assessed
- **THEN** relevance is `NONE` with no reasons

#### Scenario: A confirmed disruption is not hidden by uncertainty elsewhere
- **GIVEN** an accepted OPS_CORE STATUS `CANCELLED` for S1 and no accepted events for S2
- **WHEN** the trip is assessed
- **THEN** relevance is `DISRUPTIVE` with reason `CANCELLATION` (S1)

#### Scenario: Only stale evidence
- **GIVEN** every event for S1 and S2 was recorded more than 30 minutes before `now`
- **WHEN** the trip is assessed
- **THEN** relevance is `UNVERIFIED` with reason `NO_FRESH_EVIDENCE` for each segment

### Requirement: Relevance rules are versioned data
Criteria, their parameters, the tier each criterion yields, the freshness window, and airport MCTs SHALL come from the rule set version in effect at `now`, stored in the database. Rule set versions are immutable. Every assessment SHALL report the `rules_version` it used.

#### Scenario: Version recorded on the result
- **WHEN** `ABC123` is assessed
- **THEN** the assessment reports `rules_version` `REL-2026-09`

#### Scenario: A newer version changes the outcome
- **GIVEN** a rule set `REL-TEST-B`, in effect at `now`, with `MISSED_CONNECTION` disabled and `LONG_DELAY` at 180 minutes
- **WHEN** `ABC123` is assessed
- **THEN** relevance is `INFORMATIONAL` with reasons `MINOR_DELAY` (S1) and `GATE_CHANGE` (S1, `E-1007`), the connection S1→S2 is still reported `MISSED`, and `rules_version` is `REL-TEST-B`

### Requirement: The assessment fails closed without usable rules
If no rule set is in effect at `now`, it cannot be read, or one of its criteria has an unknown key or invalid parameters, relevance SHALL be `UNVERIFIED` with reason `RULES_UNAVAILABLE`, and no rule hard-coded in the service SHALL be used.

#### Scenario: Rules database unavailable
- **GIVEN** the rule set cannot be read
- **WHEN** `ABC123` is assessed
- **THEN** relevance is `UNVERIFIED` with reason `RULES_UNAVAILABLE`

#### Scenario: Unknown criterion key
- **GIVEN** the rule set in effect contains a criterion with key `MOON_PHASE`
- **WHEN** a trip is assessed
- **THEN** relevance is `UNVERIFIED` with reason `RULES_UNAVAILABLE`

### Requirement: Partial context is never filled in with defaults
When the trip context is `PARTIAL`, missing fields SHALL be treated as unknown. If a field needed for the assessment (a segment's date, origin, destination, or scheduled times) is missing, the affected segment SHALL be `UNVERIFIED` with reason `CONTEXT_INCOMPLETE`. A missing field that the assessment does not use SHALL NOT change the result.

#### Scenario: Missing fare field does not matter here
- **GIVEN** `ABC123` with `missing_fields` `["fare_conditions.change_penalty_amount"]`
- **WHEN** the trip is assessed
- **THEN** relevance is still `DISRUPTIVE`

#### Scenario: Missing scheduled arrival
- **GIVEN** `ABC123` with S1's `scheduled_arrival` absent and listed in `missing_fields`
- **WHEN** the trip is assessed
- **THEN** S1 is `UNVERIFIED` with reason `CONTEXT_INCOMPLETE` and the connection S1→S2 is `UNKNOWN`

### Requirement: Explanations are templated from verified facts only
The passenger explanation SHALL be generated from fixed templates chosen by relevance and reasons. It SHALL mention only accepted facts (segment status, estimated times, gate, connection outcome), and SHALL NOT mention rejected events, source names, entitlements, compensation, or personal data.

#### Scenario: Brief case explanation
- **WHEN** `ABC123` is assessed
- **THEN** the explanation states that LA500 is delayed and now estimated to arrive in Lima at 20:35, and that the connection to LA2410 at 19:05 will be missed. It does not mention `LEGACY_MIRROR`, `ON_TIME`, a fee, or a refund

#### Scenario: Unverified explanation
- **GIVEN** the `SOURCE_CONFLICT` case for S1
- **WHEN** the trip is assessed
- **THEN** the explanation says the flight's status is being confirmed and states no delay, cancellation, or time
