# U2 consumer, policy and participant inventory

Observed 2026-10-14 on branch `feature/docsuri-v2-u2-account-personal-controls` at source `a62bb26e` plus the bounded-work commit. This record establishes the mounted consumer surface, owner/policy/vocabulary boundaries and participant scopes before implementation evidence. Presence of a route is composition evidence, not behavior success.

## Mounted composition (actual, not planned)

`backend/local_host.py::assemble_journey` mounts one owner transaction facility and these routers:

| Owner surface | Mounted routes | Realm |
|---|---|---|
| Accounts entry (U1 compatibility) | `GET /api/v2/session`; `access-inspect-session`, `access-register`, `access-request-verification`, `access-verify-email`, `access-login`, `access-logout` | journey + account-controls |
| Accounts controls (U2) | `access-read-profile`, `access-update-profile`, `access-list-consents`, `access-update-consent`, password reset/change, email change, MFA begin/material/confirm/verify/recover, `access-prepare-lifecycle`, `lifecycle-request`, `lifecycle-inspect`, `access-request-reactivation`, `lifecycle-reactivate`, identity begin/callback/list/unlink/ORCID read | account-controls only |
| Library | `library-save-paper`, `library-list-saved-papers`, `library-read-saved-paper`, `library-remove-saved-paper`, `library-save-search`, `library-list-saved-searches`, `library-remove-saved-search`, `library-list-history`, `library-read-history`, `library-clear-history` | journey + account-controls |
| Personalization | `settings-read`, `settings-update`, `settings-update-onboarding`, `settings-list-suggestions`, `settings-list-recent-papers`, `settings-prepare-reset`, `settings-reset`, `GET settings-resets`, `GET settings-resets/{resetId}` (SD2-05) | journey + account-controls |
| Usage | `usage-inspect`, `usage-list-records`, `usage-read-assignment`, `usage-grant-entitlement`, `usage-revoke-entitlement`, `usage-read-plan` | journey + account-controls |
| Discovery / Corpus / Assistance | C05 `search`; C04 `resolve-paper`, `read-content`, asset route; C06 assistance accept/read/history/result with `GET /api/v2/jobs/{id}(/result|/events)` | journey + account-controls |
| Host | `POST /api/v2/c01/host-resolve-navigation`, `GET /api/v2/capabilities`, `GET /health/live`, `GET /health/ready` | both |

`controls = realm == "account-controls" and origin == "https://127.0.0.1:18049"`. The `journey` realm (`https://127.0.0.1:18037`) is the retained U1 compatibility composition; it mounts the same owner routers with `GuardedEntryService` and U1-owned policies. U7 (`/tmp/docsuri-u7-run`) is a separate realm and is not re-pointed by U2.

## Authority and vocabulary boundaries

- The eight registered owners are the only roles the transaction facility opens pools for: `accounts, corpus, library, personalization, discovery, usage, assistance, operations` (`backend/transactions.py::OWNERS`). Owner passwords live in the mode-600 run manifest; a mismatched run identity refuses connection.
- The `account-controls` realm binds the sole finite policy `u2-synthetic-v1` (`backend/modules/accounts/control_policy.py`): 20 accounts, 64 KiB bodies, page ≤ 50, 300 s proofs, 60 s MFA material, 15 s leases, 900 s period, quota 3. `public_evidence()` names G1–G8 gates for credentials/google/orcid/email/mfa-recovery/lifecycle/public-quota/public-capacity; synthetic success never clears them.
- Journey-realm policies remain U1-owned: `synthetic-paper-search`, `local-research`, `synthetic-local-library`, `synthetic-personal-settings`, `synthetic-four-no-reset`, `synthetic-local-entry`. U2 changed none of them; the U2 wallet capability advertises `u2-synthetic-v1` only under the controls realm.
- Browser authority is always server-established (`Authority(account_id, session_id)`); body-supplied owner/role/quantity is never authority. Session cookies are `session_id` plus per-session CSRF presented as `X-CSRF-Token`; lifecycle-limited continuations are separate scoped cookies.
- Readiness derives from recorded owner observations (`local_observation`) plus, for the controls realm, the supervised control loop state and fail-closed capacity (`capacity_footprint()` over `database_bytes + wal_bytes` under 80% of the 512 MiB live allowance).

## Required participant scopes

The controls realm registers one lifecycle manifest with these participants/scopes (13): `AccountAccess: live_records, derived_artifacts`; `Library: live_records`; `Personalization: live_records, derived_artifacts, pending_work`; `UsageEntitlements: live_records`; `PaperAssistance: live_records, derived_artifacts, pending_work`; `DiscoveryCitations: live_records`; `ServiceOperations: backups, restore_enforcement`. Worker adapters exist for the six feature owners; `ServiceOperations` intentionally has no runtime adapter and is acknowledged `blocked` with `required-scope-evidence-unavailable`, so a missing restore/backup responsibility can never read as complete.

## Legacy routes versus current v2 owners

- Legacy: `GuardedEntryService` registration/verification/login/logout for the U1 journey realm; its four-operation rejection-proof ledger remains authoritative for U1 and is extended, not rewritten, by U2.
- Current v2: `ControlEntryService` under the controls realm owns credentials, proofs, MFA, identity links, consent, lifecycle and reset confirmations; `ControlUsageService`/`GuardedUsageRepository` retain U1 reservation identity while adding accepting-owner admission inspection; Library/Personalization/Discovery extend their existing owner repositories.
- The intent predicates `NOT_READY/capacity.exhausted` (503), `UNAUTHENTICATED` (401), `FORBIDDEN` (403), `INVALID_ARGUMENT` (413/422), `CONFLICT` (409), `NOT_FOUND` (404) form the finite error vocabulary shared by the browser boundary.

## Rollback and source boundaries

- Application base is develop merge `295a3d19`; every unit change is additive on this branch. Migrations apply in a fixed order recorded in `scripts/verify_docsuri_u2.py::MIGRATIONS`; applied bytes are hashed into `public.docsuri_local_identity` and any changed applied file is refused, so rollback is a new ordered amendment, not an edit.
- The quarantine restore database (`docsuri_u2_restore`) is disposable and explicitly dropped only by the coordinator's owned cleanup; the original realm is never named for drop.
- U2 must not edit the AI-DLC installation or unrelated legacy features; the U7 realm, U1 runner and U1 policies remain untouched.

## Carried-forward U1 limitations

Per the functional specification (W-scope section): U1's recorded normal-assistance, semantic-search and figure limitations remain open; U2 setting a preferred mode, permitting an action or rendering a result does not resolve them. U3/U4/U5/U6 supply those features; U8 verifies cumulative integration. No search-projection writer moves to U2, and no U2 account/quota action grants export approval or durable research-draft recovery. These limitations are carried into the code summary and traceability rather than relabelled complete.
