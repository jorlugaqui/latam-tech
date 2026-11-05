# Spec Delta

## Purpose

Delivers the passenger-facing web page and gives it same-origin access to the API, with security headers and rate limiting at the edge. This change provides the shell only; trip, disruption, and recommendation views come with later changes.

All steps in this capability are **deterministic**.

## ADDED Requirements

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
