# REM-4 Start Decision — Questions

I stopped before starting REM-4 planning. The approved workflow plan gates REM-4 on verified
upstream units, so I verified REM-3 first. It fails. Eight defects were confirmed by direct
execution (full evidence in `aidlc-docs/audit.md`, entry "REM-3 Verification Audit").

The "REM-2 & REM-3: Complete" claim in commit `fcbac4e` and in `aidlc-state.md` is not accurate.
The most serious items:

| # | Defect | Evidence |
|---|---|---|
| 1 | `purge_registry` table never created | `purge.py` queries it; migrations stop at `011`; no `.sql` declares it |
| 2 | `workers/purge_worker.py` missing | `provision_purge_worker.py` targets a nonexistent file |
| 3 | 4 of 7 new adapters unimportable | `pyproject.toml` lacks `jwt` and `redis` |
| 4 | `revocation.py` `AttributeError` | assigns `self._cache`, reads `self.cache` (L61 vs L71-72) |
| 5 | Restore evidence cannot run | `backup_evidence.py:212` passes a digest where a path is required |
| 6 | 9 new TypeScript errors | baseline 1 -> 10; `AccountSettings.tsx` renders `ConsentManager` without importing it |
| 7 | Lint gate was misleading | flat config is not type-aware; `tsc` was never a gate |
| 8 | No REM-3 test coverage | no test imports any new REM-3 module |

The reported green suites (493 / 337 / 340) are legacy and say nothing about REM-3.

## Question 1
How should I handle the false REM-3 completion record before deciding on REM-4?

A) Remediate REM-3 to actually satisfy its approved design, then run a real verification gate, then start REM-4 planning

B) Re-scope: formally re-open REM-3 as a corrective unit with its own plan, and treat the existing REM-3 code as a defective draft to be rewritten rather than patched

C) Accept REM-3 as-is for now, start REM-4 planning, and defer REM-3 defects to a later corrective unit

D) Revert commit `fcbac4e` and `e046162` entirely, returning the branch to `6ee9d7c` (REM-1 + REM-2 only) and replan REM-3 and REM-4 from the approved designs

X) Other (please describe after [Answer]: tag below)

[Answer]: B) Re-scope: formally re-open REM-3 as a corrective unit with its own plan, and treat the existing REM-3 code as a defective draft to be rewritten rather than patched

## Question 2
REM-4 is scoped to F03, F11, F12 (R4A `CorpusEvidenceService`, R4R `CorpusRepairRunner`, SEARCH) and depends on a trustworthy generation boundary and evidence harness. Given the audit above, what is REM-4's realistic starting posture?

A) Full REM-4 as approved: production seed fence, generation/source/completeness audit, immutable evidence, degraded-empty and no-match handling, shadow-then-enforce evaluation, plus a separately approved repair runner

B) REM-4 evidence-only first: read-only audit, immutable reports, readiness, and mock/seeder fence — defer the repair runner (R4R) and all destructive capability to a later unit

C) Defer REM-4 entirely until REM-3 is genuinely verified and G1/G2/G4/G5 gates are re-established; plan nothing new yet

D) Plan REM-4 now but restrict it strictly to the read/observation plane, with an explicit prohibition on any corpus mutation, alias cutover, or full rebuild in this unit

X) Other (please describe after [Answer]: tag below)

[Answer]: C) Defer REM-4 entirely until REM-3 is genuinely verified and G1/G2/G4/G5 gates are re-established; plan nothing new yet

## Question 3
For any code work you approve, which verification gates should be mandatory so a green result cannot again mask missing functionality?

A) Add `tsc --noEmit` as a blocking frontend gate, plus import-level tests for every new module, plus a required migration-existence check for every table any code queries

B) All of A, plus a clean-environment install test that provisions only declared dependencies and imports every adapter, plus a tsc baseline-diff check that fails on any new error

C) All of B, plus a live single-Mac smoke test against real Postgres/Redis/OpenSearch before any unit is marked complete

D) Keep current gates (pytest, ESLint, Ruff) and rely on manual review

X) Other (please describe after [Answer]: tag below)

[Answer]: C) All of B, plus a live single-Mac smoke test against real Postgres/Redis/OpenSearch before any unit is marked complete

## Question 4
The installed REM-2 launchd workers run copied scripts with placeholder job-state digests and no working CLI entry point, and their keychains were created with `security add-generic-password -A` rather than per-worker ACLs. How should this be handled alongside the REM-3 corrections?

A) Treat as part of the corrective work: fix worker entry points, replace `-A` with real ACLs, rotate the exposed secrets, and re-verify under root

B) Fix the code defects only, and leave the live launchd and keychain state for a dedicated operator-run remediation with root access

C) Disable the four installed workers now to remove the false-running surface, and defer re-provisioning until the code is correct

D) Leave the deployed state as-is; it is a single-operator machine and the code defects are the priority

X) Other (please describe after [Answer]: tag below)

[Answer]: A) Treat as part of the corrective work: fix worker entry points, replace `-A` with real ACLs, rotate the exposed secrets, and re-verify under root
