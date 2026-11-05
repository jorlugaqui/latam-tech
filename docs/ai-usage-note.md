# AI Usage & Decision Note

## Tools and what for

- **Claude Code (Claude Opus 5.5)** as a coding agent in the terminal, driven through a spec-first workflow (OpenSpec: explore → propose → apply → archive). Used to analyze the brief, discuss options, write proposals, specs, designs and task lists, implement them test-first, run tests and smoke checks in Docker, and draft documentation.
- **OpenSpec** to force every change through a written spec, design and task list before any code, so each AI output had a contract to be checked against.

## Outputs accepted, modified or rejected, and how I validated them

Validation stack: tests written before code and watched failing first; import-linter layer contracts; `make smoke` against the real PostgreSQL, nginx and mocks; strict spec validation; and my own checks in the browser.

| AI output | Outcome | Caught by |
|---|---|---|
| Spec example: a 30-min delay "absorbed" by a 70-min layover | **Rejected**: 17:55 + 30 + 60 MCT is after 19:05; scenario corrected | Failing test |
| Policy grammar without bare facts, which R2 (`... AND international`) uses | **Modified**: grammar extended, spec updated | Writing the tests |
| Unreadable 201 from `create_human_case` treated as a definite failure | **Modified** to "indeterminate", since a retry could duplicate the case | Design review during implementation |
| Repository importing the transition table from the services layer | **Modified**: moved to schemas | Import-linter |
| Page form using Alpine's `x-model`, which does nothing in the CSP build: fields were sent empty | **Rejected**: values read from the form; smoke check added so it cannot return | **Me, in the browser** |
| Scripted edits that silently did not apply after the formatter reflowed lines | **Rejected**: switched to exact edits and verified every replacement | Failing test |
| Two fixes for a flaky smoke run (rate limiter) | **Rejected** twice; the third (refill after the burst) held across repeated runs | Running it repeatedly |
| Source reconciliation, time-zone handling, criteria, option filters, hand-off | **Accepted** after their tests passed and I reviewed each spec | Tests + review |

## Decisions I took personally

- Backend/Integration track, Python for time-to-demo, everything local in Docker.
- Delivering outcomes 1 and 2 as one action, and the recommendation as a separate one.
- Versioned relevance rules **in the database** (the AI suggested a versioned file).
- Saving every assessment now, kept indefinitely for the demo (the AI suggested deferring it).
- The **human case as the approval mechanism**: in v1 every action needs a person; automatic approval only later, for rules that do not require approval and high-confidence options.
- A case is opened only when the passenger asks for a specific option; unverified trips go to an agent, never to options.
- Re-verifying the surname on every call (signed token later); cancellations without a policy go to a person; rebooking and notifications stay as design.
- No AI at runtime in this version (reasons in [complex-query.md](complex-query.md#ai-in-the-product)).

## What I would never give a model

- Passenger personal data: names, emails, phones, document numbers, ages, or the booking code together with the surname.
- Secrets: the API and tools tokens, database credentials, the `.env` file. The agent ran local commands that read `.env` (for example, smoke checks), but no secret value was ever printed into the conversation or committed.
- The private brief: it stays in `docs/internal/` (gitignored) and is cited, not copied.
- In the product: raw tool payloads, and any power to trigger a write tool from model output.
