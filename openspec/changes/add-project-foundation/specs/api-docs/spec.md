# Spec Delta

## Purpose

Publishes a machine-readable and browsable description of the API contract, so reviewers and the passenger-facing layer can rely on documented endpoints, schemas, error responses and the authentication scheme (brief §6, "contrato" for the complementary layer).

All steps in this capability are **deterministic**.

## ADDED Requirements

### Requirement: Documentation is available only when enabled
When documentation is enabled by configuration, the API SHALL serve the OpenAPI document at `GET /openapi.json` and an interactive viewer at `GET /docs`, both without a token. When it is disabled, which is the default, both paths SHALL return 404.

#### Scenario: Enabled
- **GIVEN** documentation is enabled
- **WHEN** a client calls `GET /openapi.json` without an `Authorization` header
- **THEN** the response status is 200 and the body is a valid OpenAPI 3 document

#### Scenario: Disabled by default
- **GIVEN** the documentation setting is not configured
- **WHEN** a client calls `GET /docs` or `GET /openapi.json`
- **THEN** both responses have status 404

#### Scenario: No alternative viewer
- **GIVEN** documentation is enabled
- **WHEN** a client calls `GET /redoc`
- **THEN** the response status is 404

### Requirement: Every operation documents all its responses
Each operation in the OpenAPI document SHALL list every status code it can return, each with a response schema: success codes plus 401 for protected operations, 404, 422 and 500 for all operations, and 503 for readiness.

#### Scenario: Protected operation
- **GIVEN** documentation is enabled
- **WHEN** the OpenAPI document is inspected for `GET /api/v1/ping`
- **THEN** it lists responses 200, 401, 404, 422 and 500, and the 401 response uses the error schema with `error`

#### Scenario: Readiness operation
- **GIVEN** documentation is enabled
- **WHEN** the OpenAPI document is inspected for `GET /health/ready`
- **THEN** it lists responses 200 and 503 with the readiness schema

### Requirement: The authentication scheme is documented
The OpenAPI document SHALL declare an HTTP Bearer security scheme, apply it to every operation under `/api/`, and apply no security to operations under `/health/`.

#### Scenario: Security per operation
- **GIVEN** documentation is enabled
- **WHEN** the OpenAPI document is inspected
- **THEN** `GET /api/v1/ping` requires the Bearer scheme and `GET /health/live` has no security requirement

### Requirement: Documentation is not exposed through the web service
The web service SHALL NOT forward `/docs` or `/openapi.json` to the API; documentation is reachable only on the API's local port.

#### Scenario: Docs through the web service
- **WHEN** a browser requests `http://localhost:8080/docs`
- **THEN** the request is not forwarded to the API and the response status is 404

### Requirement: Documentation contains no secrets or personal data
The OpenAPI document SHALL NOT contain token values, connection details, or real personal data; any examples MUST use placeholder values.

#### Scenario: Document inspected for secrets
- **GIVEN** documentation is enabled and the API token is `test-token-0123456789abcdef0123456789`
- **WHEN** the OpenAPI document is retrieved
- **THEN** it does not contain the token value or the database URL
