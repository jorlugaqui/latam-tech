# Future work

What the demo deliberately does not build, and how it would. Each item names who must confirm it.

## 1. From an approved case to a rebooking

v1 stops at an `OPEN` human case: the case is the approval. The next step extends the case state machine (`api/src/companion/schemas/case_states.py`) and adds an agent-only approval endpoint with its own role (OWASP API5).

```
OPEN --agent approves--> APPROVED --refetch options (TTL 120 s), still eligible?--+
                                                                                   v
   create_rebooking_request(option, idempotency_key = hash(case_id, option_id))
      201 PENDING_CONFIRMATION --> REBOOK_REQUESTED --> notify_passenger (section 2)
      409 DUPLICATE_REQUEST    --> adopt the returned request_id --> REBOOK_REQUESTED
      503 UPSTREAM_TIMEOUT     --> REBOOK_INDETERMINATE: never retried; reconcile
   option gone or no longer eligible --> back to the agent (NEEDS_NEW_OPTION)
OPEN --agent rejects--> REJECTED --> notify_passenger
```

- The action is recorded before it is attempted (as the hand-off already does), so an indeterminate outcome is visible and can be reconciled.
- The idempotency key is derived from the case and option, so a retry after a crash cannot create a second rebooking.
- `PENDING_CONFIRMATION` expires (`expires_at`): the passenger confirms before it lapses; expiry returns the case to the agent.
- The approval endpoint must re-verify that the approving agent may act on that booking.

## 2. Passenger notifications

`notify_passenger(message)` after a rebooking request, a rejection, or an `INDETERMINATE` reconciliation.

- Messages come only from templates over verified facts and always carry a `policy_ref` (the recommendation explanation already cites the rule and policy version).
- A `422 UNVALIDATED_CONTENT` is our bug: fix the template; never strip the check.
- AI-written text only behind the verifier of section 4.

## 3. Automatic approval

Turn the human approval into an automatic one when it is safe:

- every applying rule has `requires_human_approval: false`;
- the top option is `HIGH` confidence, has seats for the whole party, and no fare difference;
- the assessment is fresh and `DISRUPTIVE` with accepted evidence.

Then the flow of section 1 runs without the agent step. **To confirm with the PM:** whether R5 (a minor in the group, needs approval) gates the whole case or only its own entitlement. The default assumed: only its own (the rebook can be automatic; priority handling is still reviewed).

## 4. AI in the product

- **LLM explanation composer** behind the `ExplanationComposer` strategy: it rewords the structured, evidence-backed claims; a deterministic verifier rejects any text with a claim not in the assessment and falls back to the template; rolled out in shadow mode. It would receive `TripFacts`, which hold no personal data.
- Decisions (relevance, entitlements, options) stay deterministic.

## 5. Back office

For ops, PM, agents, and admins, with roles and permissions per function:

- **Agents / ops:** the human case queue: approve, reject, reassign, reconcile `INDETERMINATE` cases.
- **PM / admins:** author policies, relevance rules (`relevance_rule_sets`, `relevance_criteria`), and airport reference data (time zones, MCTs) as **new versions** with an `effective_from`, never edits in place; a second person approves each change (four eyes).
- **Audit:** every admin action records who, what, when; admin actions are high impact too.
- **Data:** every SQL entity is viewable; retention policies for `trip_assessments` and `human_cases`.

## 6. Authentication and abuse

- **Signed lookup token:** the lookup returns a short-lived HMAC-signed token (booking + expiry); follow-up calls send it instead of resending the surname.
- Real passenger authentication instead of the shared API token.
- Per-booking lockout against surname guessing, on top of the rate limit.

## 7. Open questions and data gaps

| Question | Who confirms |
|---|---|
| Relevance thresholds (15/120 min), freshness window (30 min), MCT per airport | PM + Ops |
| A cancellation policy (today cancellations go to an agent) | Policy / Legal |
| A surname field upstream (today: trailing words of `name`) | Identity owner |
| Retention of `trip_assessments` and `human_cases` (today: kept indefinitely) | PM / Legal |
| Airport countries, so `international` (R2) can be evaluated | Ops / data owner |
| Collecting `compensation_requested` (R4) from the passenger | PM |
| Tool response limits (256 KiB, 200 events) with real volumes | Platform |
| Clock skew: compare option TTLs against our receipt time instead of `retrieved_at` | Integration owner |
