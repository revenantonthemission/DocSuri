# Project-Level Rules

> Project-specific specialisation and corrections. Loaded after `org.md` and
> `team.md` as strict-additive guidance; contradictions with broader policy
> are rejected. Populated by practices-discovery and the self-learning loop.
>
> Use sparingly: most teams don't need a project layer. Reach for it
> only when this specific project needs stable, durable guidance beyond the
> team practice (for example, package-specific release checks or an additional
> regression suite for a legacy component).

## Way of Working

<!-- Project-specific specialisation. Example: -->
<!-- This monorepo requires package-scoped branch names and a package owner -->
<!-- review in addition to the team's normal merge policy. -->

## Walking Skeleton

<!-- Project-specific specialisation. Example: -->
<!-- The walking skeleton must exercise the legacy service adapter as well -->
<!-- as the new service boundary. -->

## Testing Posture

<!-- Project-specific specialisation. -->

- U5's component lane needs its own fresh realm: a coverage pass exhausts the realm's authentication-attempt allocation, so the runner refuses a later lane on that realm. Preserve the refused realm as a failed prerequisite and re-run on a fresh one; never relabel it. Ruff format drift in files no step touched is recorded, not fixed, when CI runs ruff check only and a file must keep pinned bytes. (learned 2026-10-28) <!-- cid:261016-finish-v2-rebuild:code-generation:73fb39e48f7545bcb479e379cb8909b8febb23e2c61b3677d976b67033a7e3b8 -->

- Tick a Code Generation plan box only after the run its own text asks for has passed, including when restoring ticks after a new Plan Approval clears them. A box whose run is owed to ci.yml's macos-filesystem job, an installation or a browser lane stays open, with the owed run named in the code summary, because editing the plan's text voids its approval. Before a checkpoint, check every verified and not-yet-verified line in the code summary against the runs' start times and source digest. (learned 2026-11-14) <!-- cid:261016-finish-v2-rebuild:code-generation:ef6aa6531055111913f965926a5fbe4247d11314a66bd06f97daee08e78ab5a1 -->

- Before U8's realm runs, keep free disk less the realm database above J09's 20 GiB guard and never lower the guard: with the person's approval remove only stopped docsuri-u8-<id> containers and volumes and run Colima's fstrim twice (the second pass releases what the first misses), and if swap still leaves too little, copy the preserved folders out of /tmp and ask the person to restart the Mac. Run realm B (setup, migrate, fixtures --corpus skip, verification-run) without the operations lane, which runs alone on a fresh realm, record that move as a deviation while the approved instructions still put the lane on realm B, and wait about 90 s after each archive before the next setup. (learned 2026-11-14) <!-- cid:261016-finish-v2-rebuild:code-generation:5b2816ee0e788c52480368b7260f79f9401abdbfd6bf269381d655fa749bfcca -->

- For local runs on this Mac, give every DocSuri test-tool command DOCKER_HOST=unix://$HOME/.colima/default/docker.sock and DOCKER_CONFIG=$HOME/.docsuri-u8/docker-config, and confirm the run's containers through Colima's socket before recording any run or measurement as evidence, because OrbStack holds the default Docker socket after restarts. A test tool or child process that builds its own environment keeps DOCKER_HOST whenever its caller set it, and changing another Unit's tool for that waits for the person's answer. (learned 2026-11-14) <!-- cid:261016-finish-v2-rebuild:code-generation:bb98624de1916d044cbc7ebc3c665b441928899e8db192373296766ae1121e26 -->

- Before a record says a new or changed test catches its defect, run it once against the old code or with the awaited event withheld (edit, run, restore exactly), outside any recorded verification run, confirm the restore by digest or diff, and record the failure it gave. A test checked only by reading the code is recorded as not run and is not claimed to catch the defect. (learned 2026-11-14) <!-- cid:261016-finish-v2-rebuild:code-generation:0bbca5b8ee6b016452b46f4d77cc5634b8940c899837301bf9145bb1db752b1e -->

- In every timing or capacity measurement on synthetic papers, give each run and each paper texts of their own, drawn from a seed derived from the measurement's token, the size and the run number, because repeated text adds no new vector to the HNSW index and makes later runs look fast. Count every run, the first included, and treat a slow first run as a finding to explain, never as a cold start to set aside. (learned 2026-11-14) <!-- cid:261016-finish-v2-rebuild:code-generation:78ce7483a1d379c7c20fd7149685c39e62a09792d6e7836a151c9e0b36def4cb -->

- Make a DocSuri test tool's setup wait for PostgreSQL over TCP, the way its bootstrap and migrate connect, not on docker exec pg_isready over the container's Unix socket, which can pass against the image's socket-only init server. Until the U1, U2, U3 and U7 setups wait that way, check a refusal at their bootstrap or base-only migrate against the stopped container's log for the init-server restart, keep it as a failed prerequisite and rerun on a fresh environment, never relabelled. (learned 2026-11-14) <!-- cid:261016-finish-v2-rebuild:code-generation:a03949296155368e7e67369edf9e2e05c8c4d6a76f37df7e30dd0f22717887b3 -->

## Guard Policy

<!-- Project-specific. Mode: strict, relaxed, or off. Strict here holds for every intent and cannot be changed from chat. A section under the retired Change Control heading, written by an earlier release, is still read. -->

## Deployment

<!-- Project-specific specialisation. -->

## Code Style

<!-- Project-specific specialisation. -->

## Tech Stack

<!-- Technology choices locked for this project. -->

## Decided

<!-- Decisions made in earlier stages that should not be re-asked. -->
<!-- Format: DECIDED: [decision] (Stage [slug], [date]) -->

## Scope Overrides

<!-- Custom scope rules for this project. -->

## Forbidden

<!-- Populated by practices-discovery affirmation gate. -->
<!-- Format: NEVER [behavior] (affirmed [date]) -->
<!-- Example: NEVER throw exceptions across service layer boundaries (affirmed 2026-05-17) -->

- NEVER route content-job API calls directly to `/api/content-jobs/*` (bypasses BFF, violates SEC-8) (affirmed 2026-10-02)

- NEVER use presigned URLs for asset delivery (violates SECURITY-08) (affirmed 2026-10-02)

- NEVER skip auth re-check at asset delivery time (violates SEC-9) (affirmed 2026-10-02)

- NEVER use `axios` for HTTP — use native `fetch` + custom Transport (affirmed 2026-10-02)

- NEVER use `@tanstack/react-query` — use SWR (lighter, already in stack) (affirmed 2026-10-02)

- NEVER use `lodash` — use native JavaScript (affirmed 2026-10-02)

- NEVER use `moment.js` — use native `Date` / `Intl` APIs (affirmed 2026-10-02)

- NEVER use `classnames` — use `clsx` (lighter, same API) (affirmed 2026-10-02)

- NEVER use `styled-components` or `@emotion/*` — use CSS Modules + Tailwind (affirmed 2026-10-02)

- NEVER use `moment` or `date-fns` — use native `Intl.DateTimeFormat` (affirmed 2026-10-02)

- NEVER hardcode API base URLs — use `/bff/api/content-jobs` constant (affirmed 2026-10-02)

- NEVER skip Error Boundary on SSE-consuming components (affirmed 2026-10-02)

- NEVER skip ARIA live region on real-time status components (affirmed 2026-10-02)

- NEVER skip polling fallback on SSE connections (affirmed 2026-10-02)

- NEVER store secrets in client-side code or localStorage (affirmed 2026-10-02)

- NEVER commit `.env` files or secrets to git (affirmed 2026-10-02)

- NEVER skip lint, typecheck, or test:coverage in CI (affirmed 2026-10-02)

- NEVER reduce coverage floor below 80% for feature scope (affirmed 2026-10-02)

- NEVER merge without CI passing (lint + typecheck + test + e2e) (affirmed 2026-10-02)

## Mandated

<!-- Populated by practices-discovery affirmation gate. -->
<!-- Format: ALWAYS [behavior] (affirmed [date]) -->
<!-- Example: ALWAYS use Result<T,E> for fallible operations in service layer (affirmed 2026-05-17) -->

- ALWAYS route all content-job API calls through `/bff/api/content-jobs/*` (SEC-8 compliance — gateway injects principal) (affirmed 2026-10-02)

- ALWAYS generate idempotency keys as SHA-256 hash of `userId:paperId:taskType:JSON.stringify(params)` for deterministic retry (affirmed 2026-10-02)

- ALWAYS store idempotency keys in `localStorage` with key format `idempotency:{paperId}:{taskType}` (survives page reload) (affirmed 2026-10-02)

- ALWAYS use native `EventSource` for SSE with `Last-Event-ID` header for resume on reconnect (affirmed 2026-10-02)

- ALWAYS implement polling fallback (SWR 2s fixed interval) when SSE fails (affirmed 2026-10-02)

- ALWAYS wrap JobStatus in React Error Boundary for graceful degradation (affirmed 2026-10-02)

- ALWAYS use same-origin asset delivery via `/bff/api/papers/{paperId}/assets/{assetId}` (no presigned URLs) (affirmed 2026-10-02)

- ALWAYS forward session cookie through BFF proxy for gateway authentication (affirmed 2026-10-02)

- ALWAYS relay Set-Cookie headers from gateway back to browser (affirmed 2026-10-02)

- ALWAYS use native `fetch` + custom Transport interface for all API calls (affirmed 2026-10-02)

- ALWAYS use SWR for server state management (stale-while-revalidate) (affirmed 2026-10-02)

- ALWAYS use `clsx` + `tailwind-merge` for conditional className composition (affirmed 2026-10-02)

- ALWAYS use CSS Modules + Tailwind CSS for styling (affirmed 2026-10-02)

- ALWAYS use native `crypto.subtle` for cryptographic operations (SHA-256 hashing) (affirmed 2026-10-02)

- ALWAYS use native `EventSource` API for SSE consumption (affirmed 2026-10-02)

- ALWAYS use strict TypeScript — no `any`, no implicit any, strict null checks (affirmed 2026-10-02)

- ALWAYS run lint, typecheck, and test:coverage before merge (CI gate) (affirmed 2026-10-02)

- ALWAYS maintain ≥80% line coverage for new code (feature scope floor) (affirmed 2026-10-02)

- ALWAYS keep existing test suites green (473 backend + 356 frontend) (affirmed 2026-10-02)

- ALWAYS run walking skeleton ceremony for this feature — first Unit is smallest working slice, run through all stages, verify with Construction Verification Command, require human checkpoint approval (affirmed 2026-10-02)

- ALWAYS follow test-last per component ordering — implement component fully, then write tests (affirmed 2026-10-02)

- ALWAYS deploy continuously to production on merge — every commit passing CI auto-deploys to production (affirmed 2026-10-02)

- ALWAYS conduct security review mid-implementation (Week 2) for AssetViewer migration (SEC-8/SEC-9) (affirmed 2026-10-02)

- ALWAYS integrate Sentry for client-side error tracking in Phase 7 (affirmed 2026-10-02)

--- (affirmed 2026-10-02)

## Corrections

<!-- Project-specific corrections from human feedback. -->
<!-- Format: NEVER/ALWAYS [behavior] (learned [date]) -->
- Separated same-key submission recovery from re-execution of a terminal failed job. The human selected same-parameter recovery only; requirements must not promise a restart that the backend idempotency contract does not provide. (learned 2026-10-03) <!-- cid:261001-rem-2-phase-7-frontend-v:requirements-analysis:79a69179587122017ed67c5c697f9d6272aa2d67a3c3b42293bb3df3efca4140 -->
- Treat historical CodeKB readiness claims as evidence to recheck against the current code and contracts before planning integration work; source spot-checks found BFF streaming and result-reference gaps that the old inventory described as ready, so the story handoff now names those prerequisites instead of claiming compatibility. (learned 2026-10-03) <!-- cid:261001-rem-2-phase-7-frontend-v:user-stories:a8b6d990cfe455319c63807a39afcb083c5f90757b4a2ace3a2056fffdc6439a -->
- Inspect existing UI request triggers before reusing a component as a read-only result view; SummaryModal currently requests work on mount and persona changes, so result-view design must explicitly separate reading a completed result from initiating work and preserve the intended initial parameter choices. (learned 2026-10-03) <!-- cid:261001-rem-2-phase-7-frontend-v:refined-mockups:cc0070bab92cff94bbec22a049f657822c7cf78cc6be0780c20eb2b4b94e1153 -->
- The human approved the proposed rebuild plan with the explicit choice "Approve". Start the plan for this piece of work; no reusable scope was requested by that choice. (learned 2026-10-10) <!-- cid:261010-docsuri-v2-rebuild:intent-capture:0f939d6637c59a9249475cee236b2d208d661c99a47328f845c26e685c1f4178 -->
- Use CONVENTIONS.md as the authoritative Git workflow for DocSuri: working branches merge into develop through a GitHub PR, and releases promote develop to main. The human explicitly selected this workflow after the conflicting direct-to-main convention was presented; this decision supersedes that conflicting convention for this project. Follow the branch naming and version-tag conventions in CONVENTIONS.md as well. (learned 2026-10-10) <!-- cid:261010-docsuri-v2-rebuild:intent-capture:3a31e57dcfd7ff133d1b6205f3117d0fa923ad3a508da079a6e10905ddafb1b7 -->
- The budget should be $0. Only use free or local stacks. (learned 2026-10-10) <!-- cid:261010-docsuri-v2-rebuild:feasibility:8b97e6556b76d33fa4e38c3faa2ca4217b7aa1760d372575de50908d31dd9781 -->
- Our highest priority is to make a stable, smooth, integrated user experience. Also, the codebase should be structured cleanly not only from the file perspective, but also from the code perspective so that the codebase is comprehensible and repairable. (learned 2026-10-16) <!-- cid:261016-finish-v2-rebuild:intent-capture:3182c6e1579a20ca0f1baa1dc916a89d85c7e8beff4036337b53263b6be3c6a1 -->
- The adversarial review loop for u5 ran four passes: each round's repairs were verified before the next. The loop converged only when every finding was fixed at the model level (state-machine guards, cardinalities, recovery paths), not narrated away. Two Majors still ride to the human at the gate (undefined eligibility/language-level consumption; last-digest view carrier) — accepted-open at the review, for the person to weigh. (learned 2026-10-20) <!-- cid:261016-finish-v2-rebuild:functional-design:3f20e1eebe88cadb22b2f713b7b4b09d77eb2b8ff66c1e1d150f726506684e59 -->
- The migration requirement the person added (Q4 B, Q12 A) is recorded in U8's own design as requirements correction RC1 and traced under FR4.1 (real accounts and real papers), not written into the approved requirements file: editing that file would flag every stage built on it for a re-check, and the traceability check only accepts upstream IDs that exist. (learned 2026-10-21) <!-- cid:261016-finish-v2-rebuild:functional-design:f3451ba0e8a01d1b6cb1244e57aceefa815bea9932f0903a8d958870e15dff7e -->
- Migration writes every record through its owning component's import operation under trusted composition authority: the migration tool owns only its run, parity and misfit records, because the contracts forbid one owner writing another owner's tables. (learned 2026-10-21) <!-- cid:261016-finish-v2-rebuild:functional-design:ce96a7d8b4bc545ff0b3820f4de353a9e76b8252bb5cf9b67c1da13f8b4c4a10 -->
- Q13 named collections and notes, but v1 has neither (no tables), while v1 does hold followed topics with digest settings, a glossary, saved searches, search history, private uploads and research/novelty history that Q13 did not name. The design migrates exactly Q13's groups that exist, lists every other v1 personal-data kind in the parity report as not migrated, and defaults those kinds to archive-only, decided per kind by the person before the final run (Q16's mechanism), instead of silently widening or narrowing Q13. (learned 2026-10-21) <!-- cid:261016-finish-v2-rebuild:functional-design:73db9265e70bd72666be94f9a668fa99c075d5b47c36b0cad27dff1ffb365fb5 -->
- Q9 A (every real provider) is read as U8 delivering the missing real adapters inside their owners' modules: Google and ORCID sign-in (v2 has only test stand-ins in the U2 realm), real account mail (verification mail goes to a local mailbox today), and a model executor on the local Ollama runtime (no assembled composition calls it). Public registration stays governed by AccountAccess's existing public-activation evidence policy rather than being opened by U8. (learned 2026-10-21) <!-- cid:261016-finish-v2-rebuild:functional-design:723724f5965955e4b2689c6abdfeba10d31f406afd06598f37d533bf0a366af4 -->
- Backup sets no longer carry key material: U6's security design keeps export keys out of every dump with no recovery copy, so a restore leaves the key folders untouched and each owner's own loss rule applies (U6 reconnect, U2 key recovery, an AccountAccess verifier replacement that ends every session). The first draft paired keys with their database, which the review showed contradicts U6. (learned 2026-10-21) <!-- cid:261016-finish-v2-rebuild:functional-design:68a9f7444b8be94cd28cc3c02aae9dc5019512af1f934c3fb18a668063487079 -->
- Dry runs and the soak use a disposable rehearsal copy, and the final run starts from an empty production database: a final run on top of soak data would mix test actions with migrated data, and an empty start makes the final parity report exact. (learned 2026-10-21) <!-- cid:261016-finish-v2-rebuild:functional-design:00bbae8be5ff50a19380282b8f5a85e4f60d0a77c82d084ecd769e9594268fdc -->
- Backup and restore run as named platform operations under the separate operator authority (C10), with ServiceOperations only recording requests and evidence: C11 requires independent operator authority for platform effects, so an administrator request alone never restores. (learned 2026-10-21) <!-- cid:261016-finish-v2-rebuild:functional-design:d0d294172307374d391a045098307bc05eaaf143d67ddcad54f8ecd033763dc5 -->
- The switch gains a maintainer-only window: the tunnel moves to v2 while only the administrator can sign in, so real Google and ORCID callbacks and each outward provider's first approved effect are exercised before anyone else arrives: the alternative of a second hostname would have widened the public surface Q5 limited to one address. (learned 2026-10-21) <!-- cid:261016-finish-v2-rebuild:functional-design:3d861c0cfa19ac8be42ee98fb137739404dac70e726fcddec494454ea3c894a5 -->
- Switch, abort and rollback effects run as bound PlatformControl protocols (named services, two registered tunnel origins plus a static maintenance origin, database recreate) rather than manual commands, so every effect leaves a receipt and no generic command exists, as C10 requires. (learned 2026-10-21) <!-- cid:261016-finish-v2-rebuild:functional-design:70352e40fe8e77a9fa0cd12987dbcf3afab0df51ebf4d57120249d00c03e4090 -->
- After the per-unit review budget was spent, the sanctioned path back to a fresh check was the person's explicit Request Changes (their "fix the U5 design now and re-check" choice recorded as the report reason), which reset the stage attempt; a fresh attempt then verified all 22 accumulated findings as fixed. (learned 2026-10-25) <!-- cid:261016-finish-v2-rebuild:functional-design:7c21826f5e15ecd4f65f8fbe01a8dbf67114a8bf9007f3d3d6ac8e2467c001f6 -->
- Reusing the earlier backup tool meant designing around what it really does: it writes one regular file per call and deletes only by age in folders it marked as its own, so U8 keeps an unmarked folder, packages every copy as one archive built in a recorded staging folder, and deletes only through a record-driven per-location disposal; the first version of this change described the tool as deleting by record, which the review showed it does not. (learned 2026-10-27) <!-- cid:261016-finish-v2-rebuild:functional-design:4239feb73232dc07f24290c49909c554b7d7d29439530e9bcbeb5fda75e2a984 -->
- A Code Generation build resumed after a session restart may arrive with no progress section in the developer's brief when the plan grew after the build started; continue from the plan file's own ticks and the code summary's status lines, hand the developer an explicit progress note, and never redo the steps already ticked. (learned 2026-10-28) <!-- cid:261016-finish-v2-rebuild:code-generation:b754c894a5eca31e0e946d579a2769330ab4ab81dcbdb0f871fb2eea815b5d65 -->
- U5's Build and Test loop-back 1 decisions (2026-10-28): a definite provider refusal keeps the provider's HTTP status and validated error name beside the plain-language category, amending the security requirement's 'category only' wording in the plan and code summary rather than the approved requirements file; the shared shell files frontend/src/App.tsx and frontend/src/api.ts are measured by U2's cumulative Vitest lane, not U5's; only backend files no report measured join U5's coverage include list, and removing the unused send_digest_email returned email.py to its pre-U5 bytes so local_observation.py alone joined. (learned 2026-10-28) <!-- cid:261016-finish-v2-rebuild:code-generation:c36948060566636aed147d330b47108557f2bb26c14b0069f1633938c4f37f2f -->
- Check the actual disk usage before treating the free disk as short: beside the free bytes J09's guard reads, read macOS's own figures (available capacity with purgeable space) and what fills the disk (for example unused simulator runtimes or stray copies) before asking to free realms or restart the Mac. (learned 2026-11-17) <!-- cid:261016-finish-v2-rebuild:code-generation:f3cddd763ca8ac82bf763318e7287345fd47f20b4ee3ce83abcd2d5edc288ce0 -->
- While doing the work, check whether we are moving through the same states in a circle, and tell the person what you find. (learned 2026-11-22) <!-- cid:261016-finish-v2-rebuild:code-generation:4c23e7ce7892d7277776744509625d47af76f27aba7a8e50225a7e715084ce23 -->
