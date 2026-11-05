# passenger-web Specification

## Purpose
Delivers the passenger-facing web page and gives it same-origin access to the API, with security headers and rate limiting at the edge. This change provides the shell only; trip, disruption, and recommendation views come with later changes.

All steps in this capability are **deterministic**.

## Requirements

### Requirement: The page is served at the root
`GET /` on the web service SHALL return status 200 with an HTML page.

#### Scenario: Page loads
- **WHEN** a browser requests `http://localhost:8080/`
- **THEN** the response status is 200 and `Content-Type` starts with `text/html`

### Requirement: API pass-through on the same origin
Requests to `/api/*` on the web service SHALL be forwarded to the API with the same path, query, method, body, and `Authorization` header. The web service MUST NOT add, remove, or replace the `Authorization` header.

#### Scenario: Authorized call through the proxy
- **GIVEN** the browser adds `Authorization: Bearer <valid token>` to requests for `http://localhost:8080/*`
- **WHEN** the page calls `GET /api/v1/ping`
- **THEN** the response status is 200 and the body is `{"status": "ok"}`

#### Scenario: No token added by the proxy
- **GIVEN** the browser sends no `Authorization` header
- **WHEN** the page calls `GET /api/v1/ping`
- **THEN** the response status is 401

#### Scenario: Health is not exposed through the web service
- **WHEN** a browser requests `http://localhost:8080/health/ready`
- **THEN** the request is not forwarded to the API and the response status is 404

### Requirement: The page never handles the token
The page SHALL NOT read, store, embed, or send the API token itself. It relies on the browser adding the `Authorization` header and does not use `localStorage`, `sessionStorage`, cookies, or URL parameters for credentials.

#### Scenario: Page source contains no credential
- **WHEN** the served HTML and JavaScript are inspected
- **THEN** they contain no token value and no code that sets an `Authorization` header

### Requirement: The page shows the API connection state
The page SHALL call `GET /api/v1/ping` on load and display one of three states: "Connected" on 200, "Missing or invalid token" on 401, and "Service unavailable" on any other status or a network error.

#### Scenario: Token missing
- **GIVEN** the browser sends no `Authorization` header
- **WHEN** the page loads
- **THEN** the page displays "Missing or invalid token"

#### Scenario: API down
- **GIVEN** the API container is stopped
- **WHEN** the page loads
- **THEN** the page displays "Service unavailable"

### Requirement: Security headers on every response
Every response from the web service SHALL include `Content-Security-Policy` with `default-src 'self'` and `frame-ancestors 'none'`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, and SHALL NOT disclose the server version.

#### Scenario: Headers present on the page
- **WHEN** a browser requests `http://localhost:8080/`
- **THEN** the response includes the four security headers and the `Server` header carries no version number

### Requirement: Rate limiting on API calls
The web service SHALL limit each client IP to 10 API requests per second, with a burst of 20, and return status 429 beyond that.

#### Scenario: Burst exceeded
- **WHEN** one client sends 50 requests to `/api/v1/ping` within one second
- **THEN** at least one response has status 429

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
