# Security Requirements — U6 approved export

Date: 2026-10-20 (Asia/Seoul)
Unit: u6-approved-export. Sources:

- confirmed [nfr-requirements-questions.md](nfr-requirements-questions.md) (Q1–Q5);
- inception [requirements NFR1–NFR6](../../../inception/requirements-analysis/requirements.md);
- this Unit's [functional spec](../functional-design/functional-spec.md) and [rules](../functional-design/rules.md), including the functional-design review's open points R-13 to R-16 (carried here where noted);
- the [technology stack](../../../../../codekb/DocSuri/technology-stack.md) and the built keyring `backend/modules/accounts/control_keys.py`;
- Notion's developer documentation and the `notion-client` 3.1.0 source, both checked 2026-10-19.

U6 is an embedded library. The service that hosts it (U8) owns throughput, availability and monitoring targets, so this file and [tech-stack-decisions.md](tech-stack-decisions.md) carry the Unit's non-functional requirements. The operating values in NFR4.10 fix the "policy" values that the functional design's rules left as starting points, and they supersede those starting points where they differ.

## Authentication and authorization (NFR1)

- **NFR1.1** — Every export operation runs under the authenticated owner's current session, and every connection, preview, approval and effect it references is checked to belong to that owner on every access. Another owner's identifier behaves exactly like a nonexistent one (BR7.1). [Q1]
- **NFR1.2** — The export worker, reconciliation and housekeeping act as the service. They read and write only the records of the effect or approval they are handling. A write re-checks the approving owner's session and reads the source through U4 with that owner's authority (BR3.3). No background path touches another owner's data. [Q1]
- **NFR1.3** — Every mutating export call goes through the browser boundary's existing protections: same origin, CSRF token, an idempotency key scoped per owner and operation (BR3.2), and the request-size allowlist. The token is accepted only on the configure call over that channel (BR1.1). [Q1]
- **NFR1.4** — Lifecycle participation runs under the participant role that AccountAccess maps for ApprovedExport (amendment A8). It writes only U6's records, once per request and scope, and never defers (BR6.5). [Q1]
- **NFR1.5** — Retention and erasure:
  - A rendered copy of a research result is kept only while it can still be approved or its export is unsettled (BR2.6). An unapproved preview is kept at most 7 days. An unconsumed approval keeps its copy at most 7 days, and after that it can no longer be continued: the history offers a fresh preview instead.
  - The approving session's own lifetime bounds every unconsumed approval. When the session ends, housekeeping invalidates the approval (authority-revoked), because that is a definite answer.
  - The connected workspace's name is removed with its connection.
  - Erasure removes every U6 record for the account and keeps count-only evidence (BR6.2). [Q3]

## Credential protection (NFR3)

- **NFR3.1** — Sealing. Each token is sealed with authenticated encryption: AES-256-GCM, a fresh random 96-bit nonce per seal, and associated data binding the account, the connection and the connection revision. A sealed token copied to another row, account or revision fails to unseal. [Q1]
- **NFR3.2** — Key custody. U6 keeps its own key file, its own key versions and its own directory. It uses the same reviewed implementation as the built account-controls keyring, through one shared, parameterised keyring helper, not a second implementation. The built keyring's guarantees therefore apply:
  - an exclusive lock around creation and rotation;
  - atomic creation, writing to a temporary file created exclusively and then linking it into place, with the directory synced;
  - no symlink followed, and owner, mode 0600 and size verified on every read;
  - at most three key versions; new seals use the newest, and older versions only unseal;
  - a never-in-the-repository rule: the file lives only in the application's private data directory, never in the repository, the database, a database backup or a log. [Q1]
- **NFR3.3** — First start, loss and rotation:
  - An "initialized" marker records that the key file has existed. A missing file without the marker is a first start and creates the first key. A missing file after the marker is a loss: every connection becomes unavailable (BR1.6), nothing is invalidated and no new key is created silently.
  - After a loss, an operator command creates a fresh key explicitly, and owners connect again. A token is never recoverable from the database alone.
  - Rotation is an operator command run under the lock. It re-seals every stored token under the newest version and reports how many tokens are still sealed under each version. The oldest version is retired only when its count is zero. [Q1]
- **NFR3.4** — Exposure. The token is never:
  - returned, shown again, or put in browser storage or a URL;
  - written to a log, an error message, evidence or any other record.

  The input field is cleared after every submit. Responses never relay Notion's error text (BR1.1, BR7.2). [Q1]
- **NFR3.5** — One client per use (closes the shared-client risk). For each single operation that uses a token, the adapter creates a dedicated HTTP client and SDK client, uses it, and closes both in a `finally` step. A single operation is a validation, a listing, a read, a write, a read-back or a whole scan. The SDK writes `Authorization: Bearer <token>` into that client's default headers, so these clients are never shared, pooled or reused across operations, owners or tokens. The token is unsealed only inside that operation, and the clients, their headers and the token are dropped together. [Q1, Q5]
- **NFR3.6** — Error reduction:
  - Every exception raised inside the adapter is reduced to a fixed outcome category at the adapter boundary. That covers the SDK's response and timeout errors, transport errors, decoding errors, JSON errors, cancellation and anything unexpected. For a write, any exception not classified by NFR4.3 or NFR4.4 is uncertain.
  - The exception object and its chain, which carry the original request with its `Authorization` header, never reach a log, an error reporter or a response.
  - Error reporting (for example Sentry) is configured not to send local variables or default personal data, and frames of the adapter that hold the token are scrubbed. [Q5]
- **NFR3.7** — Disconnect, revocation, withdrawal and erasure delete the sealed token in the same step that ends the connection's use (BR1.4, BR6.1, BR6.2). [Q1]
- **NFR3.8** — The provider boundary:
  - The token can reach only `https://api.notion.com`. The adapter validates every page and block identifier as a Notion identifier (32 hexadecimal digits, with or without hyphens) before it builds a request path. The injected transport refuses any request whose scheme, host or port is not exactly that origin.
  - TLS certificates are verified. Redirects are never followed. Proxy and certificate settings are not taken from the environment (`trust_env` off) unless a proxy is deliberately configured.
  - The transport streams each response and aborts once it exceeds the cap (policy: 2 MB). An over-cap, truncated or unparsable answer is handled under NFR4.4 for writes and NFR4.6 for reads.
  - Provider-supplied text such as page titles and messages is untrusted data. It is escaped wherever it is shown and never interpreted. [Q4, Q5]
- **NFR3.9** — Quiet logging:
  - The SDK always gets a dedicated logger with a null handler that does not propagate.
  - The HTTP library's own loggers (`httpx` and `httpcore`) are kept at WARNING or above, so request URLs, cursors and headers stay out of logs. [Q5]

## Integrity, idempotency and reconciliation (NFR4)

- **NFR4.1** — One effect per approval, durably recorded before any write (BR3.2). Approve and execute replays return their originals, recognised by the call's own idempotency key or by the approval already having an effect. [Q5]
- **NFR4.2** — Exactly the bound content (carries R-13).
  - The canonical block tree is exactly the Notion page-creation body's `properties.title` and `children`, as they will be sent. `renderedContentHash` is the SHA-256 of their canonical JSON, the same form U4 uses for its content hashes: sorted keys, compact separators, UTF-8.
  - The write request carries that value as `contentHash`, together with the `marker`; the reconcile request carries the `marker` (the A6 extension in tech-stack-decisions.md).
  - The adapter takes the tree from U6's store through an internal port keyed by the effect. It recomputes the hash and writes only when it equals the bound `renderedContentHash`.
  - Adapter tests check that the body the fake Notion receives hashes to the bound value, and the fake can be set to reject a body that does not.
  - `bindingHash` (sent as `previewHash`) stays the approval binding over owner, source, destination, connection revision, render policy and `renderedContentHash`. [Q5]
- **NFR4.3** — Write retries:
  - Only Notion's two documented retry answers are retried: HTTP 429 `rate_limited` not marked as blocked (`public_api_request_blocked`), and HTTP 529 `service_overload`.
  - The SDK's own retries are off (`retry=False`, as a boolean). Because `notion-client` 3.1.0 does not recognise 529, the classification reads the HTTP status and the response body's code itself.
  - Every other answer that does not confirm the page is uncertain, the effect becomes unknown, and nothing is written again automatically (BR4.2, BR4.3). [Q3, Q5]
- **NFR4.4** — The write attempt deadline:
  - The worker enforces an overall wall-clock deadline of 90 seconds around each write attempt, covering connection, sending, waiting and reading, and cancels the request when it expires. The SDK's per-phase timeout is set to the same value but is not relied on as the bound.
  - An expired deadline, a cancelled request, or an over-cap, truncated or unparsable answer is uncertain. The effect becomes unknown and is never failed on that basis, because the page may exist.
  - The settling wait before the first check is counted from the attempt's deadline (NFR4.10). [Q3]
- **NFR4.5** — The rate-limit window (carries R-15):
  - A rate-limited effect may make up to 3 retries, so at most 4 attempts, within 10 minutes of its first rate-limit answer.
  - The window can end an effect only while its latest attempt carries a rate-limited answer and no attempt is outstanding. Then it fails (rate-limit-budget-spent); if a pre-write check could not complete, it fails as dependency-unavailable.
  - An outstanding attempt follows its own deadline (NFR4.4) and the abandoned-request rule (BR4.6).
  - When Notion's stated wait would end after the window, the effect fails at once (rate-limit-budget-spent).
  - These values supersede the starting point "about 3 attempts within 3 minutes" in rules BR4.2. [Q3]
- **NFR4.6** — Reads (identify, list destinations, read a page, scan):
  - All Notion calls of one connection share a client-side pace of at most 2 requests per second on average, below Notion's documented 3 per second.
  - A read is retried on 429 (not blocked) or 529 after the stated wait, up to 3 times within the operation's own time budget.
  - A scan whose retries are spent, or whose answer is over-cap, truncated or unparsable, is recorded as listing-incomplete and never as complete.
  - The other reads report could-not-check (BR3.3). [Q3]
- **NFR4.7** — Reconciliation scans:
  - A scan pages manually through every result (`page_size=100`), never using the SDK's pagination helpers.
  - It matches the integration identity recorded on the attempt, and the marker.
  - Two complete scans with no marker, at least one settling interval apart, are needed before an effect fails as not found.
  - The owner settles once the check schedule ends (BR4.4, BR4.5). [Q3]
- **NFR4.8** — Atomic start. Moving an effect to executing and recording its attempt happen in one transaction, so no executing effect lacks its attempt (BR3.3). [Q3]
- **NFR4.9** — Definite answers only (carries R-14). Housekeeping invalidates an unconsumed approval only on a definite answer:
  - U4 says the source is absent, not exportable or changed; or
  - AccountAccess says the approving session is no longer current.

  A could-not-check answer leaves the approval approved, to be checked again on a later pass. Its rendered copy still follows NFR1.5. [Q3]
- **NFR4.10** — Operating values (policy). Each row names the requirement it serves.

| Value | Policy | Serves |
|---|---|---|
| Write attempt deadline | 90 s wall clock per attempt, above Notion's 60 s server deadline | NFR4.4 |
| Read request timeout | 30 s per request | NFR4.6 |
| Settling wait before the first check of an unclear export | 3 min after the attempt's deadline | NFR4.4, NFR4.7 |
| Check schedule for an unclear export | after 3, 10 and 30 min, then hourly, then every 3 h, for 24 h in total; then owner settlement | NFR4.7 |
| Rate-limit retries for a write | up to 3 (at most 4 attempts) within 10 min of the first rate-limit answer | NFR4.5 |
| Read retries | up to 3 per read within the operation's time budget | NFR4.6 |
| Client-side pace per connection | at most 2 requests per second on average | NFR4.6, NFR6.4 |
| Could-not-check wait for an accepted export | 24 h from the first could-not-check | NFR4.4 (BR3.3) |
| Abandoned request detection | 15 min | NFR4.8 (BR4.6) |
| Clock margin for finding exported pages | 5 min | NFR4.7 |
| Per-owner limits | 1 export in flight; 20 bound per rolling hour | NFR4.11, NFR6.4 |
| Rendered copy retention | unapproved previews and unconsumed approvals: 7 days | NFR1.5 |
| Response size cap | 2 MB, enforced while streaming | NFR3.8 |

- **NFR4.11** — Limits are enforced when the effect is bound, never when the approval is recorded. A refusal leaves the approval unconsumed (BR5.1, BR5.2). [Q3]

## Accessibility (NFR5)

- **NFR5.1** — The export view, the stepped flow, the history and both dialogs keep the established Korean labels and responsive layout. They meet WCAG 2.2 AA, verified by tests or checks against these success criteria:

| Criterion | What is checked |
|---|---|
| 1.3.1 Info and relationships | headings, lists and form labels |
| 1.4.1 Use of color | status never shown by color alone |
| 1.4.3 Contrast (minimum) | text contrast at least 4.5:1, large text at least 3:1 |
| 1.4.10 Reflow | no two-dimensional scrolling at 320 CSS px |
| 2.1.1 Keyboard | every action works from the keyboard |
| 2.4.3 Focus order | focus order follows the flow, and focus is trapped and returned in dialogs |
| 2.4.7 Focus visible | focus is always visible |
| 2.4.11 Focus not obscured (minimum) | focus is never hidden by other content |
| 2.5.8 Target size (minimum) | targets at least 24×24 CSS px |
| 3.3.1 Error identification and 3.3.2 Labels or instructions | field errors name the problem |
| 4.1.3 Status messages | status changes go through one polite live region |

[Q4]

## $0 operation (NFR6)

- **NFR6.1** — No paid dependency. The new library `notion-client` is MIT-licensed and free, the cryptography library is already in the backend, and Notion is used on its Free plan. [Q2, Q5]
- **NFR6.2** — Free-terms evidence. Before the real composition is activated, the owner's single-member Free workspace and the date of the check are recorded, together with Notion's published limits that apply: the block limit for free workspaces with more than one member, and the rate limits. Without that record the real composition is blocked with POLICY_UNRESOLVED (BR8.3). [Q2]
- **NFR6.3** — Testing never reaches Notion. Every automated test and CI run uses the local fake Notion: an HTTP-level stand-in placed under the real SDK client, so the SDK and its settings are exercised (BR8.1). The single real export follows the owner's explicit approval of its exact content (BR8.2). [Q2]
- **NFR6.4** — The client-side pace and the per-owner limits keep usage well inside the free integration's limits (NFR4.10). [Q3]

## Required verification

These security-relevant behaviours are proven by tests in code generation, against the HTTP-level fake Notion and the real SDK:

- Two consecutive operations with different tokens never send each other's `Authorization` header (NFR3.5).
- After forced failures of every kind, no token appears in logs, exception text, reported error events or responses (NFR3.6, NFR3.9).
- The SDK traps behave as configured (NFR4.3, NFR4.4):
  - a dict retry setting would re-enable retries, so only `retry=False` is used and a check proves a single attempt;
  - entering the SDK client with `with` would replace the injected client, so it is never done;
  - a 529 answer is recognised;
  - an over-cap response is aborted;
  - a response lost after the page was created leads to unknown, not to a second page.
- A request to any origin other than `https://api.notion.com`, or with a malformed identifier, is refused before it leaves (NFR3.8).
- The written body hashes to the bound `renderedContentHash`, and a mismatch writes nothing (NFR4.2).
- A missing key file after first use leads to unavailable connections, not a new key (NFR3.3).

## Threats considered

| Threat | Example | Covered by |
|---|---|---|
| Spoofing | A forged cross-site export request; another owner's identifiers | NFR1.1, NFR1.3 |
| Tampering | Content changed between preview and write; a sealed token moved to another account; the key file swapped through a symlink | NFR4.2, NFR3.1, NFR3.2 |
| Repudiation | Disputing who approved or settled an export | Approval and effect records with request keys and timestamps; owner settlement records the named assumption (BR4.5) |
| Information disclosure | Token in logs, errors, exception chains, error-reporter frames, a shared client or a followed redirect | NFR3.4–NFR3.6, NFR3.8, NFR3.9 |
| Denial of service | Export floods; a slow, rate-limited or oversized Notion answer | NFR4.4–NFR4.6, NFR4.10, NFR4.11 |
| Elevation of privilege | The token used beyond U6's own operations or sent anywhere but Notion | NFR3.5, NFR3.8 |

## Out of scope for this Unit

- **NFR2** (consent for digests) does not apply: U6 sends no digests. It is recorded as N/A in traceability.
- Performance, scalability, reliability and observability targets belong to the hosting service (U8). For a library unit those files are not produced.
