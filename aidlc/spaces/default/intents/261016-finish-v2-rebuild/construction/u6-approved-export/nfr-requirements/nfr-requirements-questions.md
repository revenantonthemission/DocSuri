# NFR Requirements Questions — U6 approved export

Date: 2026-10-20 (Asia/Seoul)
Unit: u6-approved-export (embedded library). Inputs: [functional spec](../functional-design/functional-spec.md) and [rules](../functional-design/rules.md), [requirements NFR1–NFR6](../../../inception/requirements-analysis/requirements.md), [technology stack](../../../../../codekb/DocSuri/technology-stack.md).

This unit stores an owner's Notion credential and writes to an external service, so the security and technology decisions are the substance here. Throughput, availability and monitoring targets belong to the service that hosts the library (U8).

Each question offers the design I recommend as A. Answer with a letter, or in your own words under X.

## Q1. How is the stored Notion token protected?

The token gives write access to the owner's Notion pages and must never be readable from the database alone (requirement NFR3). The application has one reversible protection mechanism today: U2's account-controls keyring. It is bound to U2's own data directory.

A. U6 keeps its own versioned key file:
   - The file has owner-only permissions and lives in the application's private data directory, never in the repository or the database.
   - Each token is sealed with authenticated encryption, bound to its account and connection.
   - Rotating the key re-seals tokens; old keys are kept only for unsealing.
   - If the key is lost, connections become unavailable and owners connect again. Nothing is exposed.
B. Reuse U2's keyring, sharing one key between account controls and Notion tokens. This couples U6 to U2's data directory.
C. Take the key from an environment variable at start-up. This is simpler, but the key then lives in the service's launch configuration.

X. Other (please specify)

[Answer]: A

## Q2. Which Notion workspace receives the one real test export?

Notion's free terms differ by workspace. Since September 2026, a Free workspace with more than one member has a lifetime limit of 1,000 blocks for integrations. Each export uses roughly 40–150 blocks. A single-member (personal) Free workspace has no such limit.

A. Your own single-member Free workspace. The block limit does not apply. I record the plan and the date of this check as the free-terms evidence before the real export.
B. A Free workspace with other members. The 1,000-block lifetime limit applies, and I record the remaining allowance before the export.
C. A workspace on a paid plan. Its free terms still have to be shown for $0 operation.

X. Other (please specify)

[Answer]: A

## Q3. Which operating values should U6 use?

The functional design left these as values to fix here:

| Value | Proposed |
|---|---|
| Write request timeout | 90 seconds (above Notion's 60-second server deadline) |
| Settling wait before the first check of an unclear export | 3 minutes |
| Check schedule for an unclear export | after 3, 10 and 30 minutes, then hourly, then every 3 hours, for 24 hours in total; then the owner is asked |
| Rate-limit retries | up to 3 retries, honouring Notion's stated wait, within 10 minutes of the first rate-limit answer |
| Waiting on a check that cannot complete (U4 or Notion unreachable) | 24 hours before an export that has not started is marked failed; an export already in a rate-limit wait follows the 10-minute window |
| Abandoned request detection | 15 minutes |
| Clock margin for finding exported pages | 5 minutes |
| Per-owner pace | 1 export at a time, 20 per hour |
| Unapproved preview retention | 7 days |

A. Use the values above.
B. Change some of them (say which under X).

X. Other (please specify)

[Answer]: A

## Q4. Technology choices for the Notion connection?

A. No new dependencies:
   - The adapter calls Notion's REST API directly through the backend's existing HTTP client, pinned to API version 2026-03-11 (the latest documented, checked 2026-10-19).
   - It reaches only `api.notion.com`, over verified TLS, without following redirects, with response size caps.
   - The local fake Notion used by every automated test is an in-process stand-in with the same operations.
   - Token sealing uses the `cryptography` library already in the backend.
   - The screens use the established frontend patterns.
B. Add Notion's official SDK. It exists for JavaScript only, so it would mean a second runtime path.

X. Other (please specify)

[Answer]: B

## Q5. Follow-up to Q4: where should the Notion SDK run?

You chose Notion's official SDK (Q4 B). It is a JavaScript library, while U6's backend is Python, so it needs a home. Where it runs decides where your Notion token travels.

A. A small local Node.js adapter process beside the backend, used only for Notion calls:
   - The backend unseals the token and hands it over for each request through a private, owner-only local socket. The adapter keeps no copy and never logs it.
   - The SDK's automatic retries are turned off and its timeout is set to 90 seconds. DocSuri therefore keeps exact control of every write: one write per recorded attempt.
   - The adapter starts and stops with the backend and is tested through the same fake Notion.
B. Notion's community Python SDK (`notion-client`, maintained by volunteers, not by Notion) inside the backend. This keeps one runtime and uses the same retry and timeout settings.
C. No SDK after all: direct REST calls from the backend, as in Q4's option A.

X. Other (please specify)

[Answer]: B

## Consolidated Summary Confirmation

- **Q1:** U6 keeps its own versioned key file: owner-only permissions, in the application's private data directory, never in the repository or the database. Each token is sealed with authenticated encryption bound to its account and connection. Rotation re-seals tokens, and old keys only unseal. A lost key makes connections unavailable, and owners reconnect.
- **Q2:** The one real test export goes to your own single-member Free workspace, where the block limit does not apply. Its plan and the date of the check are recorded as free-terms evidence before the export.
- **Q3:** Operating values:
  - write timeout 90 s; settling wait 3 min;
  - checks after 3, 10 and 30 min, then hourly, then every 3 h, for 24 h, then the owner is asked;
  - rate-limit retries up to 3 within 10 min of the first rate-limit answer;
  - a check that cannot complete waits 24 h for an export not yet started, or the 10-min window for one in a rate-limit wait;
  - abandoned-request detection 15 min; clock margin 5 min;
  - 1 export at a time and 20 per hour per owner;
  - unapproved previews kept 7 days.
- **Q4/Q5:** An SDK is used, specifically Notion's community Python SDK `notion-client` inside the backend, not Notion's JavaScript SDK. It is pinned at 3.1.0, checked 2026-10-19. U6 overrides its defaults:
  - Notion API version 2026-03-11;
  - automatic retries off, so DocSuri makes every retry decision;
  - its own silent logger, with the HTTP library's request logging also kept quiet;
  - a 90 s timeout on an injected HTTP client that reaches only `api.notion.com`, over verified TLS, without redirects;
  - manual pagination;
  - Notion's 529 overload answer read from the status, because the SDK does not recognise it;
  - errors reduced to fixed categories, with their request chain, which carries the token, never passed on.

- Looks correct
- Request changes

[Answer]: Looks correct
