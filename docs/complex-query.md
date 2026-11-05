# An ambiguous query, end to end

How the system handles a query that has to combine booking, operational events and policies to be answered, and where it stops for a person. Each step is marked **[built]** if it exists in this repository or **[design]** if it is described but not built.

## The query

> *"Mi vuelo está atrasado, ¿me pueden devolver el dinero? Viajo con mi hijo de 7 años y no quiero perder la conexión a México."*
> (booking `ABC123`, last name Silva)

It looks like one question but holds four, and one of them (the refund) does not have the answer the passenger expects:

| Intent | What the passenger means | What the data says |
|---|---|---|
| `STATUS` | "my flight is late" | LA500 is delayed 160 min (OPS_CORE); an older report says on time, but it comes from a degraded source |
| `CONNECTION` | "I don't want to miss Mexico" | Estimated arrival in Lima 20:35; LA2410 leaves 19:05: the connection **will** be missed |
| `REFUND` | "give me my money back" | Fare `LIGHT`, `refundable: false`; no applying rule grants a refund; the refund option O3 is LOW confidence |
| `MINOR` | "I travel with my 7-year-old" | R5 applies: priority handling, **requires human approval**; the family must not be split (O2 has 1 seat) |

## How the work is split

```
 free text --> [1 identify + verify] --> [2 intents] --> [3 context] --> [4 resolve per intent]
                                                                               |
                         [6 stop for a person] <-- [5 compose the answer] <----+
```

### 1. Identify and verify the booking [built]
Booking code and surname are checked before anything else (`TripAccess`). A wrong surname and an unknown booking give the same 404, so no data is read for someone who does not own the booking.

### 2. Understand the intents [design]
In v1 there is **no free-text input**: the page offers the intents as buttons ("See my options", "Talk to an agent"), so this step is replaced by the passenger's click, which is deterministic and needs no model. With free text, this is the one step where AI earns its place (see "AI in the product"): an LLM classifies the text into a **closed** set of intents (`STATUS`, `CONNECTION`, `REFUND`, `MINOR`, `COMPENSATION`, `OTHER`). It only labels; it decides nothing. Names and numbers are removed from the text before it reaches the model.

### 3. Retrieve the context [built]
Always the same tools, in a fixed order, because each step needs the previous one:

| Order | Source | Why | If it fails |
|---|---|---|---|
| 1 | `get_trip_context` | passengers, segments, fare; needed to verify the surname | 503: nothing can be said |
| 2 | `get_operational_events` | what actually happened | `UNVERIFIED`: nothing asserted, agent offered |
| 3 | relevance rules + airports (database, versioned) | thresholds, MCT, time zones | `UNVERIFIED` (fail closed) |
| 4 | `get_policy_rules(scenario)` | entitlements; scenario chosen from the assessment | agent ("no policy we can confirm") |
| 5 | `get_eligible_options(trip_context)` | candidates, not decisions; TTL 120 s | agent; expired options fetched once more |

### 4. Resolve each intent deterministically [built]
- **STATUS:** sources reconciled (the degraded `LEGACY_MIRROR` report is rejected), times computed in UTC with each airport's zone: delayed 160 min, new departure 17:10, arrival 20:35 Lima.
- **CONNECTION:** 20:35 + 60 min MCT is after 19:05: missed. Relevance `DISRUPTIVE`.
- **Policy:** conditions evaluated over facts (`delay_minutes` 160, `missed_connection` true, `group_includes_minor` true): R3 → rebook at no fee; R5 → priority handling (approval required); R1, R2, R4 do not apply.
- **Options:** O1 (LA2412, next day 08:15, 4 seats, no fee) is the only eligible one. O2 is excluded (1 seat for 2 passengers, and a fee under a no-fee entitlement). O3, the refund, is excluded (not entitled, LOW confidence).
- **REFUND [design]:** answered from the same facts: the fare is not refundable and the policy grants a free rebooking instead. The system never promises a refund it cannot back with a rule. If the passenger insists, it becomes an agent case (`ASSISTANCE_REQUIRED`) with the refund request noted.
- **MINOR:** R5 is attached to the case and the party is never split.

### 5. Compose the answer [built, template]
Built from verified facts only, citing the rule and policy version (the future `notify_passenger` rejects messages without a `policy_ref`):

> Your trip has been affected by a change. LA500 from SCL to LIM is delayed by 160 minutes [...] With this change you will miss your connection LA2410 departing LIM at 19:05.
> Under policy POL-DELAY-2026-03, rule R3 gives you rebooking at no extra cost. Under policy POL-DELAY-2026-03, rule R5 gives you priority handling, reviewed by an agent. Recommended: LA2412 from LIM to MEX [...] at 08:15 (local time). An agent confirms any change before it is made.

The refund part [design] would add: *"Your fare is not refundable; the policy offers you a rebooking at no extra cost instead. An agent can review your request."*

### 6. Stop for a person [built]
The system stops and hands over (a human case with evidence and no personal data) when:
- any action would be taken: in v1 **every** rebooking needs an agent's approval;
- a rule requires approval (R5 here, R4 if compensation is requested);
- the data cannot be verified (conflicting or stale sources, a tool down);
- no policy covers the case (cancellations) or no option fits;
- the passenger asks for something no rule grants (the refund, if they insist) [design].

## Classification of each step

| Step | Classification | Reason | Risk | Control / fallback |
|---|---|---|---|---|
| Verify booking + surname | deterministic | Access control must be exact | Enumeration of bookings | Identical 404, rate limit, no data read before the match |
| Understand intents (free text) | AI-assisted [design] | Free text is varied and multilingual | Wrong intent | Closed label set, confidence threshold, low confidence → agent; buttons in v1 |
| Retrieve context | deterministic | Fixed order, fixed tools | Tool down or slow | Timeouts, bounded responses, fail closed |
| Reconcile sources, compute times | deterministic | Facts, not opinions | Conflicting or stale data | `UNVERIFIED`, never a guess |
| Evaluate policy rules | deterministic | Entitlements cost money | Misread condition | Strict grammar, three-valued logic, unknown → not granted |
| Filter and rank options | deterministic | Seats, fees and times are checkable | A valid option excluded | Each exclusion logged with its reason and sent to the agent |
| Compose the answer | deterministic (template); AI-assisted wording [design] | Tone and language | A false claim | The model only rewords structured claims; a verifier rejects anything else |
| Approve any action | human | High impact | Delay for the passenger | Human case with SLA; automatic approval designed for safe cases |
| Execute rebooking / notify | deterministic after approval [design] | Must be idempotent | Duplicate or unknown outcome | Idempotency key, 409 adopted, 503 never retried |

**Agentic:** no step is agentic, by choice. The tools and their order are always the same, so an agent choosing tools would add nondeterminism, latency and cost, and would risk calling a write tool, with nothing gained. The one agentic use worth a pilot is a **read-only copilot for agents** that summarizes a case's evidence; it never holds a write tool.

## AI in the product

The demo runs no model at runtime. This is a decision, not an omission.

**Expected benefit**
- Understanding free text and several languages (Spanish, Portuguese, English) instead of buttons.
- Warmer, clearer explanations.
- Fewer contacts, by answering mixed questions like the one above in one go.
- For agents: a summary of each case's evidence.

**Why not now**
- **Risk:** every decision here maps to money or a promise (rebooking, compensation, refund). A plausible but wrong answer creates a claim; a deterministic rule can be verified and versioned.
- **Latency and cost:** a model call adds about 1–3 s and a per-interaction cost to a flow that is milliseconds and free.
- **Dependency:** a model outage needs a deterministic fallback anyway, and that fallback is the system already built.
- **Data:** free text and trip data carry personal data; sending it to a model needs redaction and a data-processing review.
- **Validation:** a model needs an evaluation set and shadow-mode metrics before it touches passengers. The 3-hour budget is better spent on correct rules.

**When it would be justified:** in shadow mode, intent classification agrees with agents' labels above a threshold set with the PM, and the reworded explanations pass the verifier at a rate that makes them worth it. Even then, decisions stay deterministic: the model labels and words, it never decides.

**What a model never receives:** emails, phones, document numbers, full names, ages, the booking code together with the surname, tokens or secrets, raw tool payloads. It sees `TripFacts`-level data (first names stripped too), intent text with names and numbers removed, and the structured claims it must word. Model output never triggers a write tool.
