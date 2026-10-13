# U1 implementation impact inventory

Date: 2026-10-11. Baseline application bytes are pinned in
[regression-baseline.md](regression-baseline.md). This is a task-directed Tier 2
inventory, not proof of exhaustive graph coverage. Refresh candidate coverage and
read exact changed functions before each implementation layer; append actual paths
to the final source manifest, including generated files.

## Source boundaries and consumers

| Owner | Existing source and integration | U1 impact and compatibility boundary |
| --- | --- | --- |
| Assembly | backend/app.py create_app; backend/config.py Settings; backend/db.py engine/session; backend/wiring.py mount_modules and 14 mount functions | Explicit manifest-driven synthetic profile must avoid ambient production DSN/provider configuration and optional mock/no-op fallbacks. Keep legacy assembly callable while selected U1 routes are proven. |
| AccountAccess | accounts/controller.py; repository/credential.py CredentialRepository; repository/session.py SessionRepository; services/signup.py, auth.py, session_manager.py | Current sessions use Redis; synthetic profile needs authoritative persistent sessions and same-transaction guard barriers in the Accounts owner. Preserve legacy account lifecycle/provider callers for U2. Never mirror authority in Library or Assistance. |
| CorpusContent | ingestion/docmodel/{builder,parser,mathml,tei}.py; backend/modules/user_docmodel/coordinator.py; existing discovery paper metadata adapter | Versioned eligible corpus facade belongs to CorpusContent; it alone publishes/withdraws projection records. Existing private upload coordination remains U4. Reuse safe extraction lineage and verify math/anchor semantics against exact P1/P2 source. |
| Discovery | discovery/real_wiring.py; service/orchestrator.py; domain retriever/ranker/validator; existing OpenSearch and OpenAI-compatible embedding ports | Current production assembly requires OpenSearch and configured embedding; absent settings select mock assembly. U1 must select bounded real local lexical/embedding adapters explicitly, with real execution facts and truthful degradation. U3 retains full modes/filter parity. |
| Library | library/ports.py; repository/sql.py and memory.py; services/library.py, saved_search.py, history.py; history_consumer.py/retraction_consumer.py | Current LibraryService deduplicates owner/arxiv identity and SQL adapters share shell sessions. Introduce exact version/CAS/receipt/history-cut behavior through this owner and bounded owner-role transactions. Existing controller/gateway consumers stay compatible until replaced. |
| Personalization/onboarding | personalization/{repository,service}.py; onboarding/{repository,service,controller}.py; wiring _mount_personalization/_mount_onboarding | Defaults and current permission stay in Personalization. Existing onboarding seeds via personalization_record_event; do not create a separate U1 preference authority or overwrite prior settings. Full lifecycle/enrichment remains U2/U3. |
| UsageEntitlements | plans/{models,repository,service}.py; _mount_plans | Add finite synthetic reservation/settlement with separate durable obligation and guarded authority. Current plan assignment/daily spend consumers remain for later complete parity. No paid tier or provider activates. |
| PaperAssistance | summarization/service/job_service.py ContentJobService; adapters/rds_job_store.py RdsJobStore; content-job API; existing migrations | Current submit persists then calls volatile enqueue callback; shell currently supplies a no-op callback. Replace U1 dispatch with durable owner obligations and claims. Preserve old request/result routes until actual new bindings prove compatibility. Real model output, not a canned normal result. |
| ServiceOperations | ops/src/docsuri_ops/{worker,observability,health,incidents}.py; adapters/{local,backup}.py; ops/local-stack | Manifest-scoped local supervisor/readiness/incidents/restore; no environment-wide prune or existing-service mutation. Existing platform-integrity/controlled operator protocol remains U7. |
| WebWorkspace | frontend/components/{PaperDetailIsland,JobStatus,SummaryModal}.tsx; lib/api/contentJobApi.ts; existing session/theme/navigation/form components and app routes | contentJobApi currently targets /bff/api/content-jobs; JobSubmissionForm submits, SummaryModal reads prepared result, JobStatus handles events. Retain these responsibilities in coherent Korean workspace, replacing bindings only in the explicit local assembly. No automatic re-execution on result navigation. |
| Shared types | shared/{dtos,events,vector-spec}, schema-catalog.json/mjs; Python tools/generate.py; frontend/scripts/gen-types.mjs; Python/TS consumer inventories | Generate canonical browser and internal closure through existing catalogue/generators. Separate browser-safe types from worker/context shapes. Preserve legacy schema identities and generated aliases for retained callers. Exact release-2.0.0 schema extraction must be drift checked against the canonical document. |

Current create_app calls `_apply_startup_migrations`, but exact source shows this
legacy-named function only inspects registry readiness and performs no DDL.
Earlier planning shorthand that described startup migrations must not be read as
a current write finding. The U1 profile still must bypass ambient configuration
and target only its newly owned manifest database. It must never weaken existing
readiness checks for a production database.

The existing direct search-history publisher uses a process-local executor and
logs dropped/failed events. U1's acknowledged history obligations cannot rely on
that fire-and-forget mechanism. Anonymous search has a fixed public principal;
never persist strangers' histories/preferences under that shared identity.

## Graph evidence and source fallback

Project: Users-revenantonthemission-Projects-DocSuri. Initial parent evidence was
refreshed through generation 2026-10-11T11:03:17Z. create_app and _mount_* searches
were fully returned for their narrow queries. Account classes required two pages
(54 results), Library classes two pages (39); Personalization (26), Plans (16),
Onboarding (14), user-docmodel (2), docmodel files (6) and ops files (25) completed
their bounded queries. These are inventory counts, not tests or capability counts.

Relevant call evidence includes create_app's test/host consumers, module assembly,
submitJob's JobSubmissionForm caller and getJobResult's SummaryModal caller.
Exact source reads of app/config/db/wiring, ContentJobService, contentJobApi,
Library ports/service, SessionRepository, real discovery assembly and generators
resolve material behavior. Graph call edges occasionally resolved similarly named
functions to unrelated modules; exact imports and snippets take precedence.

Coverage checks reported metadata_match/no_recorded_issue for the shell, affected
baseline suite/config paths, generator/catalogue paths and 25 owner/frontend
candidates. This is best-effort, not completeness. Known parse gaps in existing
summarization migrations 002/003 and generated frontend wire must receive direct
source fallback before affected edits. Caches, virtual environments and generated
build outputs are deliberately outside source discovery. No negative claim is
made about these excluded trees. New helpers have no prior index coverage and
will be checked from source and tests after creation.

## Database authorization decision

Adopt the approved plan's owner-specific runtime roles/pools and narrow
AccountAccess/CorpusContent SECURITY DEFINER guard functions on the target owner's
existing transaction connection. Non-login schema roles own fixed, schema-qualified
functions with fixed search_path; PUBLIC execute/create and foreign direct DML
are denied. No dynamic SQL, role switching, arbitrary predicates or credentials
returned to consumers. Lock account/session/consent, then source/version, then
target through commit. Revocation locks the same barriers. Expensive inference
holds no guard transaction. Migration authority is separate and manifest scoped.

This resolves the design choice, not Infrastructure R-01's execution finding.
Step 4 must prove both commit/revocation orderings with two real connections,
legitimate guarded commits, denied foreign mutation/function abuse, rollback and
fence behavior under actual runtime grants on persistent PostgreSQL 16.15.

## Generated consumer policy

The coordinated [amendment](contract-amendment.md) declares release 2.0.0 and later
consumer obligations. Public browser schemas are derived from the named C13
bindings and their reference closure; trusted contexts/claims remain internal.
The existing Python catalogue requires all registered resources; TypeScript uses
public consumer roots. Use distinct resources in those existing groups, not a
parallel handwritten binding system. Existing source schema identities are not
silently changed to new incompatible shapes. Checks must compare exact schemas,
Python and TypeScript generated output and imported consumer origins.

## Initial finite allocation

Read-only measurements: host available disk 13,440,000 KiB (about 12.82 GiB),
backend environment 202 MiB, frontend dependencies 685 MiB, shared Python 63 MiB,
existing Next output 335 MiB. Proposed incremental install/build allocation is
2 GiB, synthetic runtime including PostgreSQL/WAL/files/logs 1 GiB, and isolated
recovery reserve 1 GiB. Combined 4 GiB leaves more than the mandatory 8 GiB host
floor at this observation. Recheck immediately before provisioning and monitor
actual growth; allocation is a refusal boundary, not a prediction or permission
to delete other data. No cached model download/copy or VM enlargement is included.

Installed versions observed: Python 3.13.7, uv 0.9.0, FastAPI 0.137.1,
Starlette 1.3.1, Uvicorn 0.49.0, psycopg 3.3.4, psycopg-pool 3.3.1,
argon2-cffi 25.1.0, Pydantic 2.13.4, HTTPX 0.28.1, pytest 9.1.0;
React/ReactDOM 19.0.0, Vite 6.4.3, Vitest 3.2.6, Playwright 1.55.1;
Docker client/server 29.9.0/29.5.2 and Ollama 0.40.2. Package declarations do
not prove mounted compatibility. The backend environment lacks pytest-cov and
coverage despite declared dev requirements; Step 2 must reconcile locked tooling
within the allocation before coverage runs. pnpm's actual 11.9.0 differs from the
declared 9.15.9 and must be pinned for reproducibility.
