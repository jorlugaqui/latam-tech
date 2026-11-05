# Proposal

## Why

The first two outcomes in the brief are that a passenger can see their trip context and understand whether a relevant change happened and what it implies (`docs/internal/disruption_companion.pdf`, §1 "Objetivo de negocio", items 1–2). The sample data contains partial context, contradictory sources, and a delay that breaks a connection (§2). This change turns booking and operational events into one verified, explainable trip status.

**Outcome:** fewer avoidable call-center contacts, because the passenger gets one answer that never asserts unverified data. Measured by: each of the ten mock scenarios produces its expected relevance, and in none of them is an unverified fact shown as true.

## What Changes

- `POST /api/v1/trips/lookup` (booking code + last name) returns trip context, per-segment status, a relevance tier (`NONE`, `INFORMATIONAL`, `DISRUPTIVE`, `UNVERIFIED`), reasons with evidence, an explanation, and the next step.
- Source reconciliation (trust, freshness, conflicts), impact calculation in UTC using IANA airport time zones, and relevance criteria driven by a versioned rule set stored in PostgreSQL.
- `mock-tools` serves `get_trip_context` and `get_operational_events` with ten scenarios selected by booking code.
- Each assessment is recorded append-only in `trip_assessments` (no personal data) for traceability.
- The page gets a lookup form and a status view.

## Capabilities

### New Capabilities
- `trip-status`: the lookup endpoint, verification, response contract, upstream failures, and the assessment record.
- `disruption-assessment`: reconciliation, impact, relevance tiers, versioned rules, and explanation.
- `mock-tools`: the read tool contracts and the scenario catalog.

### Modified Capabilities
- `passenger-web`: adds the lookup form and status view.

## Scope

**In:** the items above. **Out:** policies and entitlements (`get_policy_rules`), options, every write tool, editing rules, runtime AI (an LLM explanation composer is documented as future work).

## Assumptions

- Relevance thresholds (15/120 min), MCT, and a 30-minute freshness window are proposals, to be confirmed by PM + Ops.
- The surname is the trailing word(s) of `name`. PM / identity owner to confirm whether a surname field exists.
- `scheduled_arrival` is local time at the destination. Ops to confirm.

## High-impact actions

None executed. `DISRUPTIVE` only gates the next feature's recommendation, which must recompute the assessment on the server.

## Database

`0002` **expand** (rule set, criteria, airports), `0003` **migrate** (seeds `REL-2026-09`), `0004` **expand** (`trip_assessments`, kept indefinitely in this demo; retention to confirm with PM/Legal). No contract phase.

## Impact

`api` (runtime `httpx`, `tzdata`), `mock-tools`, `fe`, compose, `.env.example` (`TOOLS_*`), and README ADR rows 17–25.
