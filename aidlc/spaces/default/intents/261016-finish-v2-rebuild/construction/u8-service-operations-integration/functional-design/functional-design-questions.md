# Functional Design Questions — U8 complete service operations and integration

Date: 2026-10-21 (Asia/Seoul)
Unit: u8-service-operations-integration (service, shared). U8 assembles the one complete application, owns its registration and lifecycle-participant manifests and the ServiceOperations readiness, incident and recovery records, verifies the whole application cumulatively, and brings it into continuous real operation on this machine. Inputs: [unit definition](../../../inception/units-generation/unit-of-work.md), [story map](../../../inception/units-generation/unit-of-work-story-map.md), [requirements FR3, FR4](../../../inception/requirements-analysis/requirements.md), the earlier record's U8 definition, ServiceOperations component and contracts C01, C02, C10, C11 and C13 (`../../../../261010-docsuri-v2-rebuild/inception/`), the U5 and U6 handoffs, and the built application.

Each question offers the design I recommend as A. Answer with a letter, or in your own words under X.

## Where things stand today

- Production (docsuri.rvnnt.dev) still runs the v1 application: `backend.main:app` with the Next.js frontend, launched by the `dev.docsuri.*` agents from this same working tree.
- Every v2 composition is synthetic-only: `/tmp` run folders, 24-hour retention, `127.0.0.1` only. No single composition holds U1–U7. The closest is U6's (U1 host, U3, U4, U5, U6, part of U2). U2's control coordinator lives in a separate realm, because its schema collides with U3's session authority. U7 is not imported by the backend.
- The lifecycle manifest exists only in the U2 realm. TopicsDigests and ApprovedExport participants are built but not registered, and ResearchWorkspace has none.
- C11 (operator dashboard, incidents, recovery) is not built. Readiness is a set of count probes behind `/health/ready`.
- No whole-application verification exists. `scripts/verify_docsuri_cumulative.py` chains U1, U2, U3 and U7 test phases in separate realms.

## Settled from the records (no question)

These follow from decisions already on record. If one should change, say so under X of the closest question.

- U8 owns the complete application entrypoint and the registration and participant manifests. It is not a new business owner or a second production application: every component keeps authority over its own entities, and recovery goes through the owning component.
- The host rejects a missing or incompatible registration and never reports a capability as healthy when its module is absent (C01).
- Lifecycle completion requires every required current participant. A scope with no adapter is recorded as blocked and never reads as complete (C02).
- Readiness is never inferred from a receipt or from process liveness alone. It distinguishes unknown, stale, degraded and unavailable (C10, ServiceOperations).
- U8 supplies a reproducible application and its verification entrypoints, not an authorization to release. CI Pipeline and the Operation stages keep release authority, and every real external effect still needs your approval of its exact content.
- No new product features, and $0 operation with free or local stacks only (NFR6).
- U8 also closes the items U5 and U6 handed over: registering their participants, the hosted key folder outside `/tmp`, the logger levels and error-reporter rules, and the export health and error-rate counts.

## Q1. Does the v2 application replace the v1 production service, and how?

The finish intent asks for the complete application to run "at production level as the maintainer's real daily service" (FR4.1). Production today is v1, and the old routes' retirement was left to "U8's cutover".

A. Yes, through a side-by-side cutover. U8 builds the durable v2 composition and runs it next to v1, on its own local port and its own data, until the cumulative verification passes and a soak period (set at NFR Requirements) is clean. One switch then points the tunnel at v2. v1 stays stopped but restorable as the rollback, and its routes are retired after the switch.
B. Yes, by a direct switch as soon as U8 is built, with no side-by-side period.
C. No. v1 stays the production service, and v2 runs only locally as evidence.

X. Other (please specify)

[Answer]: A

## Q2. Which frontend is the product?

There are two. Production serves the Next.js app (`frontend/app`, tabs 검색 · 에이전트 · 마이페이지, proxying the v1 API). Every v2 unit built its screens in the Vite workspace (`frontend/src`, served by the v2 host), which already reuses the Next.js global styles.

A. The v2 workspace becomes the product and the Next.js app retires with v1 at the switch. Its legal pages (privacy, terms) move into the v2 workspace so they stay public.
B. Keep the Next.js app as the shell and port the v2 screens into it.

X. Other (please specify)

[Answer]: A

## Q3. What does the complete application's navigation show?

In the U3–U6 compositions, 내 서재, 설정, 사용량 and 계정 render disabled although their routers are mounted, because those capabilities exist only in the U1/U2 journey list. 논문 and 작업 have no handler, and 작업 has no view. 계정 is owner-bound in the client but not on the server.

A. One navigation set for the complete application, where every entry is backed by a mounted, healthy capability, or shows its real state (signed out, degraded, unavailable) with a reason. 논문 opens from search and library results instead of being a top-level button. 작업 becomes the owner's job list across research and novelty work. The owner-bound rule comes from the server manifest only.
B. Keep today's entries and only enable the ones whose routers are mounted. 논문 and 작업 stay as they are.

X. Other (please specify)

[Answer]: A

## Q4. Which accounts and papers does real operation start with?

Data migration is outside this release's scope ("No existing-user migration is authorized or claimed"), but FR4.1 asks for real accounts and real papers.

A. A fresh start with no migration. You and any other real person sign in to v2 anew. Papers and libraries are rebuilt through v2's own paths: U1's ingestion and your own saves. The v1 database is kept, stopped, as an archive and for rollback only.
B. Migrate v1 accounts, saved work and papers into v2. This changes the release's scope and needs its own design and evidence.

X. Other (please specify)

[Answer]: B

## Q5. What durable profile does the real operation run on?

The synthetic profile lives in `/tmp` and is wiped by a restart (it was on 2026-10-20). The export key folder is still `profile.root/export-keys`.

A. A new `production` profile. All v2 state goes under one private folder outside `/tmp` (for example `~/DocSuriData/v2`, mode 0700): the environment manifest, the hosted key folders, logs and evidence. Data goes in one dedicated v2 Postgres database, separate from v1's, in the existing data plane. The service is reachable only through the tunnel at https://docsuri.rvnnt.dev. The synthetic profiles stay as they are for tests.
B. A durable root with one database per unit realm, as the synthetic compositions use today.

X. Other (please specify)

[Answer]: A

## Q6. How do the account controls and every participant come into one application?

U2's control coordinator, control and usage routers and `ControlWorker` run only in the U2 realm. Its `u2_controls.sql` collides with U3's `u3_session_authority.sql`, so the U3–U6 chain uses `GuardedEntryService` without the coordinator.

A. One composed realm. AccountAccess owns a reconciling migration that merges the U2 control schema with U3's session authority, so the coordinator, `ControlWorker`, the entry, control and usage routers and every participant run in one application and one database. The U2 tests are re-run against the merged schema.
B. Two applications (the U2 controls realm and the U3–U6 chain) behind one navigation. This contradicts "one application" and is not recommended.

X. Other (please specify)

[Answer]: A

## Q7. What is the final lifecycle manifest?

Built but unregistered: TopicsDigests (`live_records`, `pending_work`) and ApprovedExport (`live_records`, `pending_work`, `external_copies`). ResearchWorkspace has no participant, although threads, drafts, jobs and artifacts are owner data. The manifest's ServiceOperations `backups` and `restore_enforcement` scopes have no adapter, so they are blocked.

A. Register TopicsDigests and ApprovedExport with their adapters, and give ResearchWorkspace a participant built inside U4's module. The ServiceOperations scopes become complete only with real evidence: a recorded backup and a verified restore. Until then readiness shows them as blocked, never complete.
B. Register TopicsDigests and ApprovedExport only, and record ResearchWorkspace's missing participant as a known limitation.

X. Other (please specify)

[Answer]: A

## Q8. How much of the operator surface (C11) does U8 build?

C11 defines an administrator dashboard, incidents, recovery requests (administrator with current MFA) and recorded observations. None of it exists. U7's C10 observations are "a recorded coordination item, not an implemented push".

A. A minimal C11. ServiceOperations keeps capability observations and incidents in its own schema. It provides the dashboard (every capability with its unknown, stale, degraded or unavailable state and age), the incident list, and recovery requests limited to the backup and restore procedures, administrator plus current MFA only. U7's observations are pulled through the recorded coordination.
B. Keep today's count-probe readiness and record C11 as unbuilt.

X. Other (please specify)

[Answer]: A

## Q9. Which real providers run in continuous operation?

All are free or local. Production v1 has social login off and registration closed (empty Google, ORCID and Resend settings). v2 uses synthetic assistance with `assistance.model` pending, and real digest and export runs have each been bounded to one approved test.

A. All real, each degrading honestly. That means Google and ORCID sign-in, Resend email within its free tier for verification and digests, local models through Ollama, and Notion export for owners who connect their own token. Each provider's first real effect in production needs your approval of its exact content. A provider that is unreachable or over its limit shows as degraded, never as healthy.
B. Sign-in and local models real. Digests and export stay synthetic in production until a later release.

X. Other (please specify)

[Answer]: A

## Q10. How is the whole application verified?

A. One composed synthetic realm, the complete application with every participant, tested through real HTTP boundaries and a real browser by a new runner (for example `scripts/verify_docsuri_complete.py`) with its own CI lane. It covers the cross-unit journeys:
   - sign-in → library → search → paper → research → novelty → export;
   - topics → digest;
   - withdrawal and erasure across every participant;
   - backup and restore;
   - one representative defect diagnosed and repaired from a clean checkout.
   The per-unit runners stay as they are.
B. Extend `scripts/verify_docsuri_cumulative.py` to chain the U4–U6 runners too, each in its own realm, without a composed realm.

X. Other (please specify)

[Answer]: A

## Q11. Where does production run from?

Production's agents run from this development working tree, which is now on a feature branch. A branch switch here changes what production runs the next time it restarts. The capacity measurement also has a defect: `ops/src/docsuri_ops/u4_capacity.sql` counts WAL only in `docsuri_u4`.

A. Production gets its own checkout, a separate clone pinned to a released commit on `main`, and it is updated only by the release path. Development here never changes it. U8 fixes the capacity SQL to measure the production database it actually runs.
B. Keep running production from this working tree, and record the capacity defect as a limitation.

X. Other (please specify)

[Answer]: A

## Follow-up questions (from Q4)

Your Q4 answer moves v1 data migration into this release. The requirements and the scope document currently exclude it ("data-migration or continuity commitments beyond evidence"), so these settle its scope and shape.

## Q12. Is migration part of this release?

A. Yes. The requirements gain a migration requirement: v1 accounts, saved work and papers move into v2 with verified parity. It is recorded as a correction to the requirements, and U8 owns the migration as part of its cutover (Q1).
B. Not yet. This release keeps the fresh start (Q4 A), and migration becomes the next release's work.

X. Other (please specify)

[Answer]: A

## Q13. What migrates?

A. Three groups move:
   - accounts: email, display name, verified state, linked Google and ORCID identities, and preferences;
   - each account's saved work as it exists in v1: saved papers, collections, and notes or highlights;
   - the papers themselves: corpus entries plus their stored parse and embedding artifacts, reused rather than recomputed.
   Not migrated: v1 sessions and API keys, jobs in flight, and Notion connections (owners reconnect, as U6 decided).
B. Accounts and saved work only. Papers are ingested again through v2's own ingestion.
C. Accounts only.

X. Other (please specify)

[Answer]: A

## Q14. How do people sign in after migration?

A. With the same credentials. An email-and-password account keeps its v1 password hash when v2's hashing accepts that format; otherwise its first sign-in asks for a reset by email. Linked Google and ORCID identities carry over. Every session ends at the switch, so everyone signs in once.
B. Everyone resets. Migrated accounts get a password-reset email, and no v1 credential material is copied.

X. Other (please specify)

[Answer]: A

## Q15. When and how does the migration run?

A. Through a repeatable, idempotent migration tool owned by U8.
   - Dry runs against a copy of the v1 database during the side-by-side period produce a parity report: counts and checksums per entity, with every skipped record named.
   - The final run happens at the switch, with v1 writes stopped. v1 stays stopped but restorable as the rollback.
   - Its evidence is part of U8's whole-application verification.
B. One manual run at the switch, without dry runs.

X. Other (please specify)

[Answer]: A

## Q16. What happens to v1 records that do not fit v2?

A. They are reported, never dropped silently. The parity report lists each such record with its reason, and you decide per kind before the final run: map it, keep it only in the archived v1 copy, or drop it with a record.
B. Drop them, and log only their counts.

X. Other (please specify)

[Answer]: A

## Consolidated Summary Confirmation

- **Q1:** v2 replaces v1 through a side-by-side cutover. U8 builds the durable v2 composition and runs it next to v1, on its own local port and its own data, until the whole-application verification passes and a clean soak period (its length set at NFR Requirements) has run. One switch then points the tunnel at v2. v1 stays stopped but restorable as the rollback, and its routes retire after the switch.
- **Q2:** The v2 workspace is the product. The Next.js app retires with v1 at the switch, and its privacy and terms pages move into the v2 workspace so they stay public.
- **Q3:** One navigation set for the complete application:
  - every entry is backed by a mounted, healthy capability, or shows its real state (signed out, degraded, unavailable) with a reason;
  - 논문 opens from search and library results instead of being a top-level button;
  - 작업 becomes the owner's job list across research and novelty work;
  - the owner-bound rule comes from the server manifest only.
- **Q4:** v1 accounts, saved work and papers migrate into v2. Q12–Q16 shape the migration.
- **Q5:** A new durable `production` profile:
  - all v2 state under one private folder outside `/tmp` (for example `~/DocSuriData/v2`, mode 0700): the environment manifest, the hosted key folders, logs and evidence;
  - one dedicated v2 Postgres database, separate from v1's, in the existing data plane;
  - reachable only through the tunnel at https://docsuri.rvnnt.dev.

  The synthetic profiles stay as they are for tests.
- **Q6:** One composed realm. AccountAccess owns a reconciling migration that merges U2's control schema with U3's session authority, so the coordinator, `ControlWorker`, the entry, control and usage routers and every participant run in one application and one database. U2's tests re-run against the merged schema.
- **Q7:** TopicsDigests and ApprovedExport are registered with their adapters, and ResearchWorkspace gets a participant built inside U4's module. The ServiceOperations backup and restore scopes become complete only with real evidence: a recorded backup and a verified restore. Until then readiness shows them as blocked, never complete.
- **Q8:** A minimal operator surface. ServiceOperations keeps capability observations and incidents in its own schema and provides:
  - the dashboard: every capability with its unknown, stale, degraded or unavailable state and its age;
  - the incident list;
  - recovery requests limited to the backup and restore procedures, administrator with current MFA only.

  U7's observations are pulled through the recorded coordination.
- **Q9:** Every real provider runs, each degrading honestly: Google and ORCID sign-in, Resend email within its free tier for verification and digests, local models through Ollama, and Notion export for owners who connect their own token. Each provider's first real effect in production needs your approval of its exact content. A provider that is unreachable or over its limit shows as degraded, never as healthy.
- **Q10:** One composed synthetic realm with every participant, tested through real HTTP boundaries and a real browser by a new runner (for example `scripts/verify_docsuri_complete.py`) with its own CI lane. It covers:
  - sign-in → library → search → paper → research → novelty → export;
  - topics → digest;
  - withdrawal and erasure across every participant;
  - backup and restore;
  - one representative defect diagnosed and repaired from a clean checkout.

  The per-unit runners stay as they are.
- **Q11:** Production gets its own checkout, a separate clone pinned to a released commit on `main` and updated only by the release path. Development here never changes it. U8 fixes the capacity SQL to measure the production database it actually runs.
- **Q12:** Migration is part of this release. U8's design records it as a correction to the requirements: a new requirement that v1 accounts, saved work and papers move into v2 with verified parity, traced to your Q4 and Q12 answers and lifting the data-migration exclusion under Out of Scope for this migration only. The approved requirements file stays as approved. U8 owns the migration as part of the cutover.
- **Q13:** Three groups migrate:
  - accounts: email, display name, verified state, linked Google and ORCID identities, and preferences;
  - each account's saved work as it exists in v1: saved papers, collections, and notes or highlights;
  - the papers: corpus entries with their stored parse and embedding artifacts, reused rather than recomputed.

  Not migrated: v1 sessions and API keys, jobs in flight, and Notion connections (owners reconnect).
- **Q14:** People sign in with the same credentials. A password account keeps its v1 hash when v2's hashing accepts that format; otherwise its first sign-in asks for a reset by email. Linked Google and ORCID identities carry over. Every session ends at the switch, so everyone signs in once.
- **Q15:** A repeatable, idempotent migration tool owned by U8:
  - dry runs against a copy of the v1 database during the side-by-side period, each producing a parity report with counts and checksums per entity and every skipped record named;
  - the final run at the switch, with v1 writes stopped and v1 kept stopped but restorable as the rollback;
  - its evidence is part of the whole-application verification.
- **Q16:** Records that do not fit v2 are reported, never dropped silently. The parity report lists each with its reason, and you decide per kind before the final run: map it, keep it only in the archived v1 copy, or drop it with a record.
- **Settled from the records:**
  - U8 owns the complete application entrypoint and the registration and participant manifests, but no business entities; recovery goes through the owning component.
  - The host rejects a missing or incompatible registration and never reports an absent module as healthy.
  - Lifecycle completion requires every required participant; a scope with no adapter is blocked, never complete.
  - Readiness is never inferred from a receipt or from liveness alone, and distinguishes unknown, stale, degraded and unavailable.
  - U8 supplies the application and its verification entrypoints, not a release authorization.
  - No new product features; $0 operation with free or local stacks only.
  - U8 closes the items U5 and U6 handed over: registering their participants, the hosted key folder outside `/tmp`, the logger levels and error-reporter rules, and the export health and error-rate counts.

- Looks correct
- Request changes

[Answer]: Looks correct
