# Tech Stack Decisions — U6 approved export

Date: 2026-10-20 (Asia/Seoul)
Unit: u6-approved-export. Sources:

- confirmed [nfr-requirements-questions.md](nfr-requirements-questions.md) (Q1, Q4, Q5);
- the [technology stack](../../../../../codekb/DocSuri/technology-stack.md) (brownfield constraint: the Python backend already depends on HTTPX and `cryptography`);
- the `notion-client` 3.1.0 release, verified on 2026-10-19 against PyPI, its GitHub tag and an offline test run;
- the built keyring `backend/modules/accounts/control_keys.py`;
- [security-requirements.md](security-requirements.md).

## Decision

U6 joins the built backend as a module using the established patterns. Its one new dependency is Notion's community Python SDK, `notion-client`, pinned and configured below. No paid service is introduced. [Q4, Q5]

| Area | Choice | Rationale |
|---|---|---|
| Backend module | Python + FastAPI patterns of the built modules (as U5): one module owning its records through its own repository, its own database owner and login roles, cross-module reads only through granted functions | Proven by U1–U5; one writer per owned record; no second store |
| Persistence | The shared PostgreSQL, in a schema owned by U6 | Ownership model; matches U5's schema and role pattern |
| Worker | The application's shared control loop runs the export worker (execute, resume, reconcile, housekeeping) and enforces each write attempt's wall-clock deadline | No new scheduler or broker; $0 (NFR6); NFR4.4 |
| Notion access | `notion-client==3.1.0` (MIT; one runtime dependency, `httpx>=0.23`; supports Python 3.8–3.14, so 3.13 is covered), configured per [SDK configuration](#sdk-configuration) | Q4 and Q5: an SDK in the backend's own runtime |
| HTTP transport | A dedicated HTTPX client created for each operation that uses a token, never shared or pooled, closed afterwards (NFR3.5). Its custom transport admits only `https://api.notion.com`, verifies TLS, follows no redirects, ignores environment proxy settings (`trust_env` off) and aborts responses past 2 MB while streaming (NFR3.8). | The SDK writes the token into the client's default headers; the token must reach only Notion |
| Notion API version | `2026-03-11`, set explicitly (the SDK's default is `2025-09-03`) | Latest documented version on 2026-10-19; reads trash state from `in_trash` |
| Token sealing | `cryptography`'s AES-GCM. Keys are held in U6's own key file through a shared, parameterised keyring helper extracted from the built account-controls keyring, so both units use one reviewed implementation (NFR3.1–NFR3.3). | Already a backend dependency; Q1 option A; one hardened implementation, not two |
| Content hashing | SHA-256 of canonical JSON (sorted keys, compact separators, UTF-8), the same form U4 uses, over the page body's `properties.title` and `children` | U6, the adapter and the fake Notion compute the same value (NFR4.2) |
| Local fake Notion | An HTTP-level stand-in transport placed under the real SDK client. Every automated test and synthetic profile uses it, so the SDK and its settings are exercised (BR8.1, NFR6.3). | No test reaches Notion; refusals, 429/529, saved-but-busy answers, oversize, slow and lost responses can be simulated |
| Frontend contribution | The established workspace-frontend patterns of U5 (a `u6-export` module, the shared Transport client, dialogs, status line) | Consistency, accessibility conventions, no new UI stack (NFR5) |

## SDK configuration

These settings are requirements, because the SDK's defaults conflict with the design. Each was checked against the 3.1.0 source, and the behaviour was tested offline on 2026-10-19.

- **API version:** `notion_version="2026-03-11"` on every client. The default `2025-09-03` is never used.
- **Retries:** `retry=False`, as a boolean. The default retries a rate-limited page creation by itself. A dict form such as `{"max_retries": 0}` is silently ignored and the defaults return. DocSuri alone makes every retry decision (NFR4.3, NFR4.6).
- **Timeouts:**
  - `timeout_ms` is one value applied to each phase, not a total: 90 000 for writes and 30 000 for reads.
  - The bound that counts is the worker's wall-clock deadline around the whole attempt (NFR4.4).
- **Client lifecycle:**
  - Inject the per-operation HTTPX client (NFR3.5) and build the SDK client around it for that operation only.
  - Never enter the SDK client with `with` or `async with`, because that silently replaces the injected client with a default one.
  - Close the injected client in a `finally` step.
- **Logging:**
  - Always pass a dedicated logger with a null handler that does not propagate. Without one, the SDK adds a stderr handler for every client it creates.
  - Keep the `httpx` and `httpcore` loggers at WARNING or above, so URLs, cursors and headers stay out of logs (NFR3.9).
- **Pagination:** page manually through `has_more` and `next_cursor` with `page_size=100`. Do not use the SDK's pagination helpers: the async one in 3.1.0 fails when `has_more` is missing.
- **Errors:**
  - Catch everything at the adapter boundary and reduce it to a fixed category (NFR3.6). That includes the SDK's `notion_client.errors.HTTPResponseError` (status, headers, raw body, `additional_data`) and `RequestTimeoutError`, `httpx.TransportError` and other HTTPX errors, JSON decoding errors, cancellation and anything unexpected.
  - For codes the SDK does not recognise, such as 529 `service_overload`, read `json.loads(error.body)`, because `additional_data` is empty for them.
  - `NotionClientError` is a typing union and cannot be used in an `except` clause.
  - The exception and its chain are dropped. Error reporting does not send local variables or default personal data.
- **Page creation body:**
  - The SDK keeps only these top-level fields for `pages.create`: `parent`, `properties`, `icon`, `cover`, `content`, `children`, `markdown`, `template` and `position`.
  - U6 uses only `parent`, `properties` and `children`. A field outside that list would need the SDK's generic request call.
- **Upgrades:** the version stays pinned. Upstream `main` already changes retry and pagination behaviour, so an upgrade is reviewed against this list.

## Contract changes

U6's wire changes are additive to the shared contract release, as a minor version step:

- **A1–A7 and A9**, as listed in the [functional spec](../functional-design/functional-spec.md).
- **The A6 extension**, which carries the functional-design review's open point R-13. The write request (`ProviderNotionRequest`) adds `contentHash`, the canonical block tree's hash (NFR4.2), and `marker`. The reconcile request (`ProviderEffectReconcile`) adds `marker` as its search key.
- **A10**, which carries the functional-design review's open point R-16. C09's cancel also cancels an accepted effect, using the effect revision as `expectedRevision`. The client then reads the effect to see the cancelled state, because cancel returns the consumed approval.

Two cross-unit changes are made in U2's own code, each with U2's tests kept green:

- **A8**, in AccountAccess: the external-copies reason is reported as retained by policy, and the export participant is mapped in the lifecycle guard.
- **The keyring helper:** the built account-controls keyring's mechanics move into the shared, parameterised helper that U6 also uses. U2's behaviour does not change.

## Rejected alternatives

- **Direct REST calls through HTTPX (Q4 A).** No new dependency, but rejected by the owner in favour of an SDK. [Q4]
- **Notion's official JavaScript SDK in a local Node.js adapter (Q5 A).** It would put a second runtime and a cross-process token hand-over on the write path. [Q5]
- **U2's account-controls keyring and key as they are (Q1 B).** They would couple U6 to U2's data directory and key lifecycle. Sharing the implementation, but not the key, keeps the hardening without the coupling. [Q1]
- **A key from an environment variable (Q1 C).** The key would live in the service's launch configuration. [Q1]
- **A separately written U6 keyring.** It would duplicate reviewed custody code and its edge cases, such as locks, symlinks, the initialized marker and rotation.

## Verification notes

`notion-client` is maintained by volunteers, not by Notion. Three checks keep it safe here:

- its behaviour on the paths U6 uses is proven by U6's adapter tests, which run the real SDK over the HTTP-level fake Notion, including the "Required verification" list in [security-requirements.md](security-requirements.md);
- it is pinned;
- an upgrade is a reviewed change.
