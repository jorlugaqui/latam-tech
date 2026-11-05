# Spec Delta

## ADDED Requirements

### Requirement: Trip lookup form
The page SHALL offer a form with a booking code and a last name that calls `POST /api/v1/trips/lookup` with a JSON body. The form SHALL NOT navigate, put either value in the URL, or store either value in `localStorage`, `sessionStorage`, or cookies. All steps on the page are **deterministic**; the page makes no decisions and only renders what the API returns.

#### Scenario: Submit the brief booking
- **GIVEN** the browser adds a valid token
- **WHEN** the passenger enters `ABC123` and `Silva` and submits
- **THEN** the page sends `POST /api/v1/trips/lookup` with `{"booking_id": "ABC123", "last_name": "Silva"}` and the URL does not change

#### Scenario: Nothing persisted
- **WHEN** a lookup has completed
- **THEN** `localStorage`, `sessionStorage`, and `document.cookie` contain neither `ABC123` nor `Silva`

### Requirement: Trip status view
On a 200 response the page SHALL show the explanation, each passenger's first name, and each segment with its flight number, route, scheduled and estimated local times with the airport code, status, gate when present, and connection outcome. Times SHALL be displayed as the local wall time contained in the API value, without converting to the browser's time zone. The page SHALL NOT display reason codes, event ids, or `rules_version`.

#### Scenario: Brief booking rendered
- **WHEN** `ABC123` / `Silva` is looked up
- **THEN** the page shows LA500 SCL→LIM as delayed with estimated arrival `20:35 LIM` and gate `24`, and LA2410 LIM→MEX with the connection marked as missed

#### Scenario: Browser in another time zone
- **GIVEN** the browser's time zone is `Europe/Madrid`
- **WHEN** `ABC123` / `Silva` is looked up
- **THEN** S1's scheduled departure is shown as `14:30 SCL`

### Requirement: Next-step callout
The page SHALL show a callout chosen by `next_step`. For `RECOMMENDATION`, it shows a "See my options" button that stays disabled and says the option is coming soon, until the recommendation feature exists. For `HUMAN_ASSISTANCE`, it shows a "Talk to an agent" button that stays disabled and says the option is coming soon, until the agent hand-off feature exists. The page never offers "See my options" for an unverified trip. For `NONE`, it shows no callout.

#### Scenario: Disruptive trip
- **WHEN** `ABC123` / `Silva` is looked up
- **THEN** a disabled "See my options" button is shown

#### Scenario: Unverified trip
- **WHEN** `CONF01` / `Silva` is looked up
- **THEN** a disabled "Talk to an agent" button is shown, no "See my options" button is shown, and no delay is shown

#### Scenario: On-time trip
- **WHEN** `OKAY01` / `Silva` is looked up
- **THEN** no next-step callout is shown

### Requirement: Lookup error messages
The page SHALL show "We couldn't find a booking with those details" on 404, "Please check the booking code and last name" on 422, "Missing or invalid token" on 401, "Too many attempts, please wait a moment" on 429, and "Service unavailable, please try again shortly" on any other status or a network error. The messages SHALL NOT repeat the submitted values.

#### Scenario: Wrong surname
- **WHEN** `ABC123` / `Rojas` is looked up
- **THEN** the page shows "We couldn't find a booking with those details"

#### Scenario: Trip context outage
- **WHEN** `CTXERR` / `Silva` is looked up
- **THEN** the page shows "Service unavailable, please try again shortly"
