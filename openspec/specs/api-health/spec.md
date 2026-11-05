# api-health Specification

## Purpose
Reports whether the API process is alive and whether it can serve requests, so that a small team can operate the stack and the orchestrator can start services in the right order (brief §3, "operada por un equipo pequeño").

All steps in this capability are **deterministic**.

## Requirements

### Requirement: Liveness
`GET /health/live` SHALL return status 200 with body `{"status": "ok"}` whenever the API process is running, without checking any dependency.

#### Scenario: Process running, database down
- **GIVEN** the database is unreachable
- **WHEN** a client calls `GET /health/live`
- **THEN** the response status is 200 and the body is `{"status": "ok"}`

### Requirement: Readiness reflects the database
`GET /health/ready` SHALL return status 200 with body `{"status": "ready"}` when the database answers a trivial query, and status 503 with body `{"status": "not_ready"}` otherwise.

#### Scenario: Database reachable
- **GIVEN** the database answers queries
- **WHEN** a client calls `GET /health/ready`
- **THEN** the response status is 200 and the body is `{"status": "ready"}`

#### Scenario: Database unreachable
- **GIVEN** the database connection fails
- **WHEN** a client calls `GET /health/ready`
- **THEN** the response status is 503 and the body is `{"status": "not_ready"}`

### Requirement: Health responses expose no internals
Health responses SHALL NOT include connection strings, hostnames, exception messages, versions, or environment names.

#### Scenario: Failure detail stays internal
- **GIVEN** the database connection fails with an error that includes the database host name
- **WHEN** a client calls `GET /health/ready`
- **THEN** the response body is exactly `{"status": "not_ready"}`
