# Spec Delta

## MODIFIED Requirements

### Requirement: Next-step callout
The page SHALL show a callout chosen by `next_step`. For `RECOMMENDATION`, it shows an enabled "See my options" button that asks for the recommendation. For `HUMAN_ASSISTANCE`, it shows an enabled "Talk to an agent" button that asks for a human case without an option. The page never offers "See my options" for an unverified trip. For `NONE`, it shows no callout.

#### Scenario: Disruptive trip
- **WHEN** `ABC123` / `Silva` is looked up
- **THEN** an enabled "See my options" button is shown

#### Scenario: Unverified trip
- **WHEN** `CONF01` / `Silva` is looked up
- **THEN** an enabled "Talk to an agent" button is shown, no "See my options" button is shown, and no delay is shown

#### Scenario: On-time trip
- **WHEN** `OKAY01` / `Silva` is looked up
- **THEN** no next-step callout is shown

## ADDED Requirements

### Requirement: Follow-up calls resend the booking and surname from memory
The recommendation and human-case calls SHALL send the booking code and last name of the current lookup in the JSON body, kept only in the page's memory. They SHALL NOT be stored in `localStorage`, `sessionStorage`, cookies, or the URL, and SHALL be cleared when a new lookup starts. The page never sends a relevance or next step to the API.

#### Scenario: Options request body
- **WHEN** the passenger clicks "See my options" after looking up `ABC123` / `Silva`
- **THEN** the page sends `POST /api/v1/trips/recommendation` with `{"booking_id": "ABC123", "last_name": "Silva"}` and nothing is persisted

### Requirement: Recommendation view
For `status` `PROPOSED`, the page SHALL show the entitlements in plain words with their rule and policy version, each eligible option with flight, route, local departure with airport code, and fare difference, a note that an agent confirms the change, and a "Request this option" button per option. For `NEEDS_AGENT` or `NOT_APPLICABLE`, it SHALL show the explanation and a "Talk to an agent" button.

#### Scenario: Brief recommendation
- **WHEN** `ABC123` / `Silva` clicks "See my options"
- **THEN** the page shows "Rebook at no fee" citing R3 and `POL-DELAY-2026-03`, option LA2412 LIM→MEX departing `08:15 LIM`, a note that an agent confirms it, and a "Request this option" button; O2 and O3 are not shown

#### Scenario: Cancellation without policy
- **WHEN** `CANC01` / `Silva` clicks "See my options"
- **THEN** the page shows no options and a "Talk to an agent" button

### Requirement: Case confirmation view
After a human-case call, the page SHALL show, for 201 or 200 with status `OPEN`, the case id, the expected response time in minutes, and that an agent will confirm; for 202 or 200 with status `INDETERMINATE`, that the request is being registered and to contact the call center if there is no answer within 45 minutes; for 409 or 503, an error message that does not repeat submitted values. Buttons that create cases SHALL be disabled while a call is in flight.

#### Scenario: Case opened
- **WHEN** `ABC123` / `Silva` clicks "Request this option" on O1
- **THEN** the page shows a case id starting `HC-` and "an agent will confirm within 45 minutes"

#### Scenario: Indeterminate outcome
- **WHEN** `CASERR` / `Silva` clicks "Request this option" on O1
- **THEN** the page says the request is being registered and to contact the call center if there is no answer within 45 minutes, and shows no case id
