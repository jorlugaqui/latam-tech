# api-errors Specification

## Purpose
Defines how the API reports errors so that clients get a stable contract and no internal detail (stack traces, queries, personal data) leaks through an error, in line with the brief's data-protection constraint (§3).

All steps in this capability are **deterministic**.

## Requirements

### Requirement: Every response carries a request ID
Every API response SHALL include an `X-Request-ID` header. When the request carries an `X-Request-ID` matching `^[A-Za-z0-9-]{1,64}$`, the API SHALL reuse it; otherwise it SHALL generate a new one.

#### Scenario: Request ID generated
- **WHEN** a client calls `GET /health/live` without an `X-Request-ID` header
- **THEN** the response includes a non-empty `X-Request-ID` header

#### Scenario: Valid request ID reused
- **WHEN** a client calls `GET /health/live` with `X-Request-ID: demo-123`
- **THEN** the response header `X-Request-ID` is `demo-123`

#### Scenario: Invalid request ID replaced
- **WHEN** a client calls `GET /health/live` with `X-Request-ID: <script>`
- **THEN** the response header `X-Request-ID` is a newly generated value, not `<script>`

### Requirement: Unhandled failures return a generic 500
When an unexpected exception occurs, the API SHALL return status 500 with body `{"error": "internal_error", "request_id": "<id>"}`, where `<id>` equals the response's `X-Request-ID`. The body MUST NOT contain the exception message or a stack trace.

#### Scenario: Exception during a request
- **GIVEN** an authenticated endpoint raises `RuntimeError("db password=secret")`
- **WHEN** a client calls it with a valid token
- **THEN** the response status is 500, the body is `{"error": "internal_error", "request_id": "<id>"}`, and the body does not contain `secret`

### Requirement: Unknown routes return a JSON 404
A request to a path the API does not serve SHALL return status 404 with body `{"error": "not_found"}`.

#### Scenario: Unknown path
- **WHEN** a client calls `GET /api/v1/does-not-exist` with a valid token
- **THEN** the response status is 404 and the body is `{"error": "not_found"}`

### Requirement: Invalid input does not echo submitted values
A request that fails input validation SHALL return status 422 with body `{"error": "validation_error", "fields": [...]}`, where each item names the field location and the problem. The response MUST NOT echo the submitted values.

#### Scenario: Value not echoed
- **GIVEN** an endpoint that expects an integer query parameter `limit`
- **WHEN** a client sends `limit=maria.silva@example.com`
- **THEN** the response status is 422 and the body does not contain `maria.silva@example.com`
