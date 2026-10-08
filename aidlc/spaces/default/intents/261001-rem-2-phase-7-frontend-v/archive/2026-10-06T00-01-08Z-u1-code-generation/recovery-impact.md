# U1 Schema-Prerequisite Recovery Impact

## Verified Evidence and Boundaries

The human chose Retry in `code-generation-questions.md` Q2. `code-summary.md` records the actual partial implementation and failing schema lane. Existing `backend/migrations/__init__.py` admits only conservative atomic scripts and retains explicit current-authority/digest/transaction guards; migration 003 contains PL/pgSQL trigger functions whose internal BEGIN/END and trigger EXECUTE FUNCTION are rejected by that admission. No new guard or raw-SQL bypass has been applied.

Shared SSOT `shared/dtos/summarization.schema.json#/$defs/Reproducibility` requires an object with string `code` and `data`; actual `SummaryResultDTO.to_dict()` preserves that object. The approved C2 SummaryContent instead declares a string. Exact prepared content cannot be made conformant by silently flattening it. This is a verified prior-contract contradiction, not a new product requirement.

The current continuation check also returned `execution_allowed: false` for the plan's content binding. Read-only status still reports relaxed policy with plan-approval off; doctor reports no integrity problem and advisory warnings. Do not lower settings, edit framework implementation or assume that a prior receipt permits execution despite the refusal. Resolve the planning/contract boundary through its proper route and obtain whatever current-attempt exact-plan authority the returned workflow requires.

## Proposed C2 Correction and Workflow Impact

Correct only `SummaryContent.summary.reproducibility` to the existing shared Reproducibility object, preferably through the resolving shared schema reference. Preserve `code`/`data` exactly, reject malformed objects and do not expose server-only metadata. Retain preparedResult v1, owner/TTL/error precedence, immutable final content and zero generation/enqueue during reads. The new envelope is not deployed; do not assert an existing consumer accepts a changed wire shape without actual compatibility tests.

| Record/source | Proposed impact | Verification/handoff |
|---|---|---|
| Inception Contract Design | Reopen the owning boundary and modify the one C2 field/reference plus its complete-envelope summary fixtures/source rationale | Human-backed questions/summary, independent contract review and normal approval |
| U1 Functional/NFR/Infrastructure records | Revalidate after corrected contract through returned routing; preserve unchanged choices and applicable reusable artifacts | No silent source edit or old review receipt relabelled current; human chooses required reuse/reapproval |
| U1 code-generation plan/instructions | Reconcile added migration-admission source footprint and corrected C2 shape; retain implementation/source snapshot and all tests/floors | Current binding and any new-attempt initial Plan Approval follow native tools; original approval is not overwritten as a new answer |
| Current models/fixtures | Align successful summary capture/validation with the corrected authoritative object and add complete-envelope positive/negative tests | Exact actual DTO output retained; string-only legacy data gets explicit supported/unavailable treatment, not guessed conversion |
| Existing 29 implementation writes | Preserve while the design correction is approved/replayed | No reset, discard, automatic commit or dependent Unit advancement |

No requirement/story/task/deployment/Unit expansion is proposed. A backward move can invalidate downstream approvals/reviews; the returned workflow must decide the exact affected work. Existing records and partial source remain preserved, and the original 395-file pre-write snapshot remains immutable.

## Bounded Migration Admission Repair Direction

Extend only the existing application migration-admission path required by the registered U1 authority schema. Add `backend/migrations/__init__.py` and any necessary narrow admission-policy module/tests to the implementation footprint, with supplemental original-byte/digest capture checked against the original approved source listing before writing; never overwrite the original baseline.

Prefer an explicitly reviewed, owner/identity/full-script-digest-bound atomic-script policy for this procedural migration over a broad keyword-regex relaxation. The default conservative path still rejects unknown/ambiguous scripts. Admission must prove the supplied registered definition/payload identity; allow only reviewed transaction-contained table/index/function/trigger definitions, not arbitrary CLI/HTTP SQL. Retain rejection of top-level transaction escape, concurrent/nontransactional operations, external COPY/program/procedure effects and unauthorized role/system/database changes. Procedural-body or trigger syntax is not a generic exemption for executable SQL.

`apply_migrations` retains its same-connection current-authority guard, definition-digest check, canonical lock, per-step transaction/ledger and guarded commit. Review the concrete policy/003 source together, with positive registered-script, changed-digest/unknown identity, top-level escape/external-effect and revoked-authority negatives. Actual PostgreSQL syntax/constraint/publication/deletion proof still uses the qualified isolated realm. No live apply, adopted baseline claim or safety waiver follows from this repair proposal.

## Real Realm Prerequisite

The existing guard fixture requires operator-bound public manifest/receipt locations and trusted digests through the authorized Linux launcher, distinct authority/minimal-purge databases, scoped role and network/workload identity. No such verified configuration has been supplied. A fabricated JSON `verified` flag, mocked connection or development-only database is not that proof.

If a realm already exists, the accountable operator can identify its non-secret configuration location and bind the required variables in the authorized launcher. If not, prepare a concrete isolated-bootstrap plan with actual artifact/runtime availability and independently measured allow/deny/identity proof, then obtain operational authorization before creating/applying it. Do not mutate production, source its `.env`, ask for credential contents in chat, skip missing-real tests or advance the ordered store/worker/browser work as if schema verification passed.
