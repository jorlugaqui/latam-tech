# Passenger experience

The complementary layer of the Backend track: what the passenger sees and reads. A minimal version is built (`fe/public/`); this document is its specification, including the parts a production screen would add. The page **only renders what the API decided**: it never computes relevance, entitlements or options.

## Principles

1. **Verified facts only.** If a fact is not confirmed, the screen says it is being confirmed; it never shows a guess or the conflicting reports.
2. **One clear next step** per state, chosen by the API (`next_step`).
3. **Local times with the airport code** (`20:35 LIM`), never converted to the phone's time zone.
4. **Every entitlement cites its rule and policy version**, so the passenger, the agent and any notification say the same thing.
5. **No action without a person** in this version: the passenger requests, an agent confirms.

## Screens

### Lookup
```
+------------------------------------------+
| Disruption Companion                     |
| Check your trip status and what it means |
|                                          |
| Booking code  [ABC123      ]             |
| Last name     [Silva       ]             |
| [ Check my trip ]                        |
+------------------------------------------+
```

### Update (`INFORMATIONAL`, e.g. `GATE01`)
```
+------------------------------------------+
| There's an update to your trip.          |
| - LA500 departs from gate 31.            |
| Passengers: Maria (adult), Tomas (child) |
| +--------------------------------------+ |
| | LA500 SCL -> LIM        [On schedule]| |
| | Scheduled 14:30 SCL -> 17:55 LIM     | |
| | Gate 31                              | |
| +--------------------------------------+ |
+------------------------------------------+
```
`NONE` looks the same with the headline "Your trip is on schedule." and no gate line. No button in either: nothing to do.

### Disrupted (`DISRUPTIVE`)
```
+------------------------------------------+
| Your trip has been affected by a change. |
| - LA500 from SCL to LIM is delayed by    |
|   160 minutes. It is now expected to     |
|   depart at 17:10 and arrive in LIM at   |
|   20:35 (local times).                   |
| - With this change you will miss your    |
|   connection LA2410 departing LIM at     |
|   19:05.                                 |
| +--------------------------------------+ |
| | LA500 SCL -> LIM            [Delayed]| |
| | Scheduled 14:30 SCL -> 17:55 LIM     | |
| | Now expected 17:10 SCL -> 20:35 LIM  | |
| | Gate 24                              | |
| | Connection: will be missed           | |
| +--------------------------------------+ |
| [ See my options ]                       |
+------------------------------------------+
```

### Being confirmed (`UNVERIFIED`)
```
+------------------------------------------+
| We're confirming your flight status.     |
| - Some information about your trip could |
|   not be verified yet, so we are not     |
|   showing changes until they are         |
|   confirmed.                             |
| LA500 SCL -> LIM      [Being confirmed]  |
| [ Talk to an agent ]                     |
+------------------------------------------+
```
No delay, time or cancellation is shown. Never "See my options".

### Options (recommendation `PROPOSED`)
```
+------------------------------------------+
| Here is what your fare's policy gives you|
| - Rebook at no fee                       |
|   (rule R3, POL-DELAY-2026-03)           |
| - Priority handling, reviewed by an agent|
|   (rule R5, POL-DELAY-2026-03)           |
| +--------------------------------------+ |
| | LA2412 LIM -> MEX  No fare difference| |
| | Departs 08:15 LIM on 2026-09-16      | |
| | [ Request this option ]              | |
| +--------------------------------------+ |
| An agent confirms this change before it  |
| is made.                                 |
+------------------------------------------+
```
Only eligible options. Excluded ones (O2, O3) are not shown; their reasons go to the agent.

### Needs an agent (recommendation `NEEDS_AGENT`)
```
+------------------------------------------+
| An agent needs to review your options.   |
| - We can't confirm which policy applies  |
|   to your trip automatically.            |
| - An agent can help you with your trip.  |
| [ Talk to an agent ]                     |
+------------------------------------------+
```

### Case opened / being registered
```
+------------------------------------------+     +------------------------------------------+
| Case HC-4471                             |     | Request being registered                 |
| Your request was sent to an agent (case  |     | We're registering your request. If you   |
| HC-4471). An agent will confirm within   |     | don't hear from us within 45 minutes,    |
| 45 minutes.                              |     | please contact the call center.          |
+------------------------------------------+     +------------------------------------------+
         201 / 200 (same case again)                      202 (outcome unknown, never retried)
```

## Message catalog

Every message is a fixed template filled with verified fields. `{...}` are values from the API.

| Where | Message | Filled from |
|---|---|---|
| Status headline | "Your trip has been affected by a change." / "We're confirming your flight status." / "There's an update to your trip." / "Your trip is on schedule." | relevance |
| Delay | "{flight} from {origin} to {destination} is delayed by {n} minutes. It is now expected to depart at {HH:MM} and arrive in {destination} at {HH:MM} (local times)." | accepted DELAY event, airport zones |
| Cancellation | "{flight} from {origin} to {destination} has been cancelled." | accepted STATUS event |
| Gate | "{flight} departs from gate {gate}." | accepted GATE_CHANGE |
| Connection | "With this change you will miss your connection {flight} departing {airport} at {HH:MM}." / "Your onward flight {...} is affected by this change." | connection check (MCT) |
| Unverified | "Some information about your trip could not be verified yet, so we are not showing changes until they are confirmed." | — |
| Entitlement | "Under policy {version}, rule {rule_id} gives you {entitlement}[, reviewed by an agent]." | applying rules |
| Recommendation | "Recommended: {flight} from {origin} to {destination}, departing {date} at {HH:MM} (local time)." + "An agent confirms any change before it is made." | first eligible option |
| Needs an agent | "We can't confirm which policy applies to your trip automatically." / "We can't load alternative flights right now." / "The available flights changed while we checked." / "None of the available flights fits your trip and your entitlements." | recommendation reason |
| Case | "Your request was sent to an agent (case {case_id}). An agent will confirm within {sla} minutes." / "We're registering your request. If you don't hear from us within 45 minutes, please contact the call center." | human case |
| Errors | "We couldn't find a booking with those details" (404) · "Please check the booking code and last name" (422) · "Too many attempts, please wait a moment" (429) · "This option is no longer available. Please check your options again." (409) · "We couldn't send your request right now. Please try again or contact the call center." (503 case) · "Service unavailable, please try again shortly" | HTTP status |

Error messages never repeat what the passenger typed.

## What is never shown

- Email, phone, document number, loyalty tier, age, full names (first names only).
- Event sources, rejected or conflicting reports, event ids, reason codes, rule-set versions.
- Excluded options and why they were excluded.
- Internal errors, request bodies, the API token.
- An entitlement without its rule and policy version.

## Same messages, other channels [design]

The templates above are channel-neutral. When `notify_passenger` is built (docs/future-work.md §2), the push or SMS message reuses them, with `policy_ref` set to the policy version they cite: for example, after an agent approves O1, *"Your new flight LA2412 LIM -> MEX departs 08:15 LIM on 16 Sep. Rebooked at no fee under POL-DELAY-2026-03 (R3)."* A message without a `policy_ref` is rejected by the tool (422), and that is treated as a bug in the template, never worked around.

## Production additions [design]

- Spanish and Portuguese templates (same fields; translations reviewed, never machine-generated at runtime).
- Accessibility: status conveyed by text, not only color; live regions already announce updates.
- A "Check again" button for `UNVERIFIED` when the cause is a tool outage or stale data.
- Showing the case status later (requires the back office, docs/future-work.md §5).
