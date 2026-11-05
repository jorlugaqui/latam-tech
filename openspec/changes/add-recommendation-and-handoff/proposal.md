# Proposal

## Why

The brief's outcomes 3 and 4 (`docs/internal/disruption_companion.pdf`, §1) are an actionable recommendation and a hand-off to a person or a controlled action. Today a disrupted passenger sees what happened but has two disabled buttons. The traps in §2 live here: R3 applies although R1 does not, O2 lacks seats for the party and charges a fee, O3 refunds a non-refundable fare, options expire after 120 s, R5 (a minor) requires approval, and `create_human_case` has no idempotency key.

**Outcome:** a disrupted passenger gets a policy-backed proposal and one place to ask a person, without any high-impact action executed automatically. Measured by: ABC123 recommends only O1 citing R3 under `POL-DELAY-2026-03`; every request yields one case (never two); an indeterminate case creation is never retried.

## What Changes

- `POST /api/v1/trips/recommendation`: entitlements from versioned policy rules (parsed, never evaluated as code) and filtered eligible options, for `DISRUPTIVE` trips only.
- `POST /api/v1/trips/human-case`: opens a case as the approval mechanism (v1: every action needs human approval), with duplicate protection and an `INDETERMINATE` state.
- `mock-tools` adds `get_policy_rules`, `get_eligible_options`, `create_human_case`, and scenario `CASERR`.
- The page enables "See my options" and "Talk to an agent".
- Docs: README keeps the flow and automation matrix; `docs/decisions.md` takes the decision table; `docs/future-work.md` holds the back office, rebooking, notifications, auto-approval, and signed lookup tokens. Dev containers are renamed `api-dev` and `mock-tools-dev`.

## Capabilities

### New Capabilities
- `recommendation`: entitlement evaluation, option filtering, and the recommendation endpoint.
- `human-handoff`: case creation, its reasons and evidence, duplicates, and indeterminate outcomes.

### Modified Capabilities
- `passenger-web`: enabled next-step buttons, recommendation and case views.
- `mock-tools`: three new tools and an eleventh scenario.

## Scope

**Out:** `create_rebooking_request`, `notify_passenger`, automatic approval, back office, signed tokens (design only, in `docs/future-work.md`).

## Assumptions

- Cancellations have no policy yet, so they go to an agent. Policy/Legal to provide one.
- R5 gates only its own entitlement (matters only once auto-approval exists). PM to confirm.
- The party is never split across options.

## High-impact actions

`create_human_case` (low impact) is guarded by passenger intent, re-verification, a local intent record, deduplication, and no retry on indeterminate outcomes. No rebooking, refund, or compensation is executed.

## Database

`0005` **expand**: `human_cases` table. No contract phase.

## Impact

`api`, `mock-tools`, `fe`, Makefile, compose, CLAUDE.md, README, `docs/`.
