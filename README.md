# Disruption Companion

## Problem and expected outcome

A passenger whose flight changed needs to know what happened and what to do next. The data is partial, sources contradict each other, a wrong answer costs money or a claim, and rebooking is a high-impact action. **Outcome:** less uncertainty and fewer avoidable call-center contacts, without ever asserting unverified data or acting without control. **Measured by:** every demo scenario reaches its expected result, no unverified fact is shown as true, every action is traceable to a recorded decision, and no case is duplicated or blindly retried.

## Track and why

**Backend/Integration.** The brief's traps (contradictory sources, time zones, R3 vs R1, seats for the party, fees, TTLs, 409/503) are integration and decision logic, so that is where depth pays off. The passenger layer is a minimal page plus a written spec ([passenger-experience.md](docs/passenger-experience.md)).

## Run and try it

Prerequisites: Docker with Compose v2, `make`, `openssl`, `curl`.

```bash
make env && make up   # .env with random secrets; db, migrate, api, mock-tools, fe
make check            # ruff + import-linter layer contracts + unit tests
make smoke            # the running stack end to end
```

Open `http://localhost:8080/` with a header-modifier extension adding `Authorization: Bearer <API_TOKEN from .env>`, scoped to `http://localhost:8080/*`. Last name **Silva**:

| Booking | Expected |
|---|---|
| `ABC123` (brief sample) | Delayed 160 min, connection missed. Options: only O1 (O2 lacks seats for 2 and charges a fee; O3 refunds a non-refundable fare). Request O1 → case; again → same case |
| `CASERR` | Same trip; case creation times out → "being registered", never retried |
| `CONF01` | Trusted sources disagree → nothing asserted → "Talk to an agent" |
| `CANC01` | Cancelled, no cancellation policy → "Talk to an agent" |

More codes (on time, gate change, overnight, stale data, tool outages, unknown booking) are in `openspec/specs/mock-tools/spec.md`.

## Scope

**Built:** trip lookup with booking + surname; disruption assessment (source trust and freshness, UTC with airport time zones, versioned relevance rules in PostgreSQL); recommendation from versioned policy rules and filtered options; human case as the approval step, with an audit trail; mocks for the five tools used; a minimal page.
**Not built (designed in [future-work.md](docs/future-work.md)):** `create_rebooking_request`, `notify_passenger`, automatic approval, back office, free-text questions, runtime AI.

## Assumptions (and who confirms)

- Relevance: delay ≥ 120 min, missed connection or cancellation is disruptive; events older than 30 min are stale; MCT 60 min (90 at MEX). → PM + Ops
- The surname is the trailing word(s) of `name` (no surname field). → identity owner
- Cancellations have no policy yet, so they go to a person. → Policy / Legal
- R5 (a minor) gates only its own entitlement once auto-approval exists. → PM
- The party is never split; records are kept indefinitely in the demo. → PM / Legal

## Main decisions and discarded alternatives

| Decision | Discarded |
|---|---|
| Trust comes from each response's `_meta`; conflicting trusted sources → `UNVERIFIED`, never a guess | Latest event wins; fixed source ranking |
| Relevance rules and policy are versioned data; conditions parsed with a strict grammar and three-valued logic | Constants in code; `eval` of conditions |
| Options filtered by one specification per rule, each exclusion with its reason | One `if` chain; showing every candidate |
| v1: every action needs a person; the human case is the approval; one active case per booking, intent recorded first, unknown outcomes never retried | Automatic rebooking; trusting the tool for idempotency |
| Every call re-verifies the surname and recomputes on the server | Trusting what the page sends |
| No AI at runtime ([why](docs/complex-query.md#ai-in-the-product)) | LLM classification or answers |

All 31 decisions with risk and control: [decisions.md](docs/decisions.md).

## Deterministic, AI-assisted, agentic, human

| Step | Now | Future |
|---|---|---|
| Status, relevance, entitlements, option filtering | Deterministic | Same |
| Explanation text | Deterministic templates citing the policy | AI-assisted rewording behind a verifier |
| Understanding a free-text question | Not offered (buttons) | AI-assisted intent labels; low confidence → agent |
| Tool orchestration | Fixed order, no agent | Same; a read-only agentic copilot for agents at most |
| Opening a case | Automatic on the passenger's request | Same |
| Approving any rebooking; R4 cash, R5 minor; unverified data; unknown write outcomes | **Human** | Rebook without fee automatic when no rule needs approval and the option is HIGH confidence; the rest stays human |

A full walk-through of an ambiguous query: [complex-query.md](docs/complex-query.md).

## Validation

Tests written first and seen failing (320 api, 38 mock-tools) cover every spec scenario with fakes and `httpx.MockTransport`; migrations run up and down on SQLite; import-linter enforces the layers, including "read-only services never see the write port"; `make smoke` (27 checks) runs against the real PostgreSQL, nginx and mocks; the page was checked by hand in a browser.

## Risks, limitations and next steps

- **Risks:** thresholds not yet confirmed by Ops; every disruption needs an agent in v1 (works against fewer contacts until auto-approval); a case created upstream that we never learned about (`INDETERMINATE`, reconciled by hand).
- **Limitations:** mocks instead of real systems; one shared API token, no passenger login; surname heuristic; `international` unknown (no airport countries); no integration test suite; page checked manually; local only.
- **Next steps:** rebooking after approval and notifications, automatic approval for safe cases, back office, signed lookup tokens ([future-work.md](docs/future-work.md)).

AI usage and personal decisions: [ai-usage-note.md](docs/ai-usage-note.md). Behavior contracts: `openspec/specs/`.
