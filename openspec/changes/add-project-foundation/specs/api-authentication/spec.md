# Spec Delta

## Purpose

Ensures that only callers holding the configured API token can reach the Disruption Companion API, protecting passenger data (brief §3, "Deben protegerse los datos personales y aplicarse mínimo privilegio").

All steps in this capability are **deterministic**.

## ADDED Requirements

### Requirement: Protected endpoints require a valid Bearer token
Every API endpoint under `/api/` SHALL require an `Authorization: Bearer <token>` header whose token exactly matches the configured API token. The comparison MUST take the same time regardless of where the tokens differ.

#### Scenario: Valid token
- **GIVEN** the API token is configured as `test-token-0123456789abcdef0123456789`
- **WHEN** a client calls `GET /api/v1/ping` with `Authorization: Bearer test-token-0123456789abcdef0123456789`
- **THEN** the response status is 200 and the body is `{"status": "ok"}`

#### Scenario: Missing header
- **WHEN** a client calls `GET /api/v1/ping` without an `Authorization` header
- **THEN** the response status is 401

#### Scenario: Wrong scheme
- **WHEN** a client calls `GET /api/v1/ping` with `Authorization: Basic dXNlcjpwYXNz`
- **THEN** the response status is 401

#### Scenario: Wrong token
- **GIVEN** the API token is configured as `test-token-0123456789abcdef0123456789`
- **WHEN** a client calls `GET /api/v1/ping` with `Authorization: Bearer wrong-token`
- **THEN** the response status is 401

### Requirement: Uniform 401 response
Every authentication failure SHALL return the same response: status 401, header `WWW-Authenticate: Bearer`, and body `{"error": "unauthorized"}`. The response MUST NOT reveal which check failed or echo any part of the submitted token.

#### Scenario: Failures are indistinguishable
- **WHEN** a client sends a missing header, a wrong scheme, and a wrong token in three separate requests
- **THEN** all three responses have identical status, `WWW-Authenticate` header, and body

### Requirement: Health endpoints are public
The endpoints under `/health/` SHALL be reachable without a token, so that container orchestration can probe them.

#### Scenario: Health without a token
- **WHEN** a client calls `GET /health/live` without an `Authorization` header
- **THEN** the response status is 200

### Requirement: The API fails closed without a usable token
The API SHALL refuse to start when the API token setting is missing or shorter than 32 characters.

#### Scenario: Missing token configuration
- **GIVEN** the API token environment variable is not set
- **WHEN** the API starts
- **THEN** startup fails with an error naming the missing setting, and the token value is not printed

#### Scenario: Token too short
- **GIVEN** the API token environment variable is set to `short`
- **WHEN** the API starts
- **THEN** startup fails

### Requirement: Tokens are never recorded
The API SHALL NOT write the configured token or any submitted `Authorization` header value to logs, error responses, or persisted data.

#### Scenario: Rejected request is logged without the token
- **WHEN** a client calls `GET /api/v1/ping` with `Authorization: Bearer wrong-token`
- **THEN** the log output for that request does not contain `wrong-token`
