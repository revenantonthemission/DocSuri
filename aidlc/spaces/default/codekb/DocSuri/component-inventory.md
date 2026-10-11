# DocSuri Component Inventory

Each heading is a stable component name for this scan. “Deep anchors” refers to inspected boundaries; a component can have deep anchors and shallow internals. Only the 13 components with specific fully read boundaries appear in analyzed.components; Accounts, Evidence/Research, Novelty, Ingestion and Reliability/Ops remain breadth-only coverage. Their selected snippets, declarations, manifests or external composition are not deep component evidence. Dependencies are source relationships, not deployment claims. Capability IDs map to [business overview](business-overview.md).

## Application Shell and Middleware

`backend/app.py`, `wiring.py`, `health.py`, `middleware/`. Composes fourteen module groups, session/auth, observability/cost/rate authorities and repository overrides. Deep shell/auth anchors; remaining middleware shallow. Depends on backend modules, shared authz, ops and configured Redis/PostgreSQL. CAP-06/19. Readiness and optional mounts: Q-05.

## Frontend and BFF

`frontend/app/`, `components/`, `lib/`. Next.js pages/client islands, browser state, same-origin upstream transport, SSE and image proxy. Deep BFF and job contracts/state/tests; other UI shallow. Depends on backend HTTP contracts and generated/shared schemas. CAP-01–17.

## Accounts and Identity

`backend/modules/accounts/`. Credential lifecycle, verification/reset, social login/linking, session/MFA/admin authorization and account withdrawal/reactivation. Controller declarations and persistence model inventory shallow; app auth wiring deep. Depends on PostgreSQL, Redis, email, Google/ORCID and shared authz. CAP-06/07. No existing user population inferred.

## Discovery

`backend/modules/discovery/`. Query validation/expansion, lexical/semantic retrieval, ranking/reranking, grounding, paper metadata and search events. The complete `src/discovery/api/router.py` HTTP/identity/error boundary was deeply read; the central search method was traced and read as a selected range, while remaining orchestration/provider internals are shallow. The analyzed component entry is limited to that router boundary. Depends on shared vector/DTO contracts, OpenSearch, embedding and ops authorities; optional personalization. CAP-01.

## Library and History

`backend/modules/library/`. Owner-scoped saved searches/items/history, quota/validation, pagination and rerun. Controller deep; SQL/service internals shallow. Depends on accounts principal, discovery gateway, SQL or memory, history event seam. CAP-05.

## Summarization and Content Jobs

`backend/modules/summarization/`. Summary/translation, glossary, document-model/assets reads, async job acceptance/state/events/result, queue/store/model adapters. Deep mounted router, service, job model, real wiring, queue and focused tests; preparation protocol/store SQL/worker internals partly read or shallow. Depends on shared contracts, cost guard, object storage, Redis, DB, LLM, queues and ingestion builders. CAP-02–04. Q-01–Q-04 are release-relevant boundary defects.

## Citation Graph

`backend/modules/citation_graph/controller.py`. Bounded reference tree, cache, degraded provider results and library save. Deep controller/provider/cache file. Depends on Semantic Scholar, optional Redis, discovery metadata and library. CAP-09. Feature gated.

## Personalization

`backend/modules/personalization/`. Behavior recording, profile/decision computation, settings/opt-out/deletion/reset and recent papers. Deep controller and integration wiring; profile computation/repository internals shallow. Depends on owner principal, DB and paper category lookup. CAP-10. Search enrichment is bounded; feature/shadow settings affect use.

## Onboarding

`backend/modules/onboarding/`. Pending/completed/skipped state, interest selection and optional ORCID suggestions. Deep controller/wiring, shallow repository/service. Depends on account identity, personalization recorder and ORCID. CAP-11.

## Trends and Digests

`backend/modules/trends/`. Topic following, digest settings, opt-in/watermark/send log and unsubscribe; digest execution outside HTTP mount. The complete `controller.py` was deeply read, including principal/token access, request/response and error mappings; schemas/repository/service/scheduling remain shallow. The analyzed component entry is limited to the controller boundary, not digest operation. Depends on DB, discovery/embeddings and email. CAP-12. Scheduler operation unverified.

## My Page and Plans

`backend/modules/mypage/`, `plans/`. Profile/consents/ORCID and mock subscription presentation; separate tier/quota/grant/revoke service. Both complete `controller.py` files and composition wiring were deeply read; repository/service internals remain shallow. The analyzed component entry is limited to those HTTP/access boundaries. Depends on account repository, plan DB/daily spend, shared admin authorization/MFA. CAP-08/17. No real billing inference.

## Evidence and Research Sessions

`backend/modules/evidence/`, including `sessions/`. Search/document tools, grounded extraction/comparison, literal quote path, optional web references, attachments, conversations, streaming/pending jobs. Controller declarations and central orchestration flow inspected; remaining extractors/workers/repositories shallow. Depends on discovery, document models/private coordinator, LLM, SQL/object/queue and quota/cost authorities. CAP-13/14.

## Novelty and Notion Export

`backend/modules/novelty/`. Topic/manuscript analysis jobs, state/progress/cancel, artifacts, messages and approved external export. Service lifecycle/export path and controller declarations inspected; large adapters/worker shallow. Depends on discovery/evidence, private documents, DB/object/queue/model, encrypted token and Notion. CAP-15/16.

## Private Document Coordinator

`backend/modules/user_docmodel/coordinator.py`. Deep file: owner/scope/attachment identity derivation, validated 10 MiB PDF upload, build enqueue and bounded owner-scoped document readiness. Depends on object store, doc-model reader and optional build queue. Shared by evidence/novelty; public document routes reject private IDs. CAP-02/13/15.

## Ingestion and Corpus Control

`ingestion/`. arXiv and external-source intake, OA parsing, document models/assets, canonical dedup, embedding/index writes, watermarks, rebuild/refresh and DLQ. Central ingest/index flow traced/read; source adapters, SQL semantics and rebuild internals shallow. Depends on sources, shared vector spec, PostgreSQL control state, S3-compatible objects, queue, embedding and OpenSearch. CAP-18.

## Reliability and Operations

`ops/src/docsuri_ops/`, `backend/modules/ops/`, deployment/server tooling. Telemetry, cost/grounding guards, detectors/incidents, reliability evaluations, admin dashboard and operational scripts. CLI/config/interface inventory shallow; application authority wiring deep. Depends on shared ports, platform integrity and configured local/cloud integrations. CAP-19.

## Platform Integrity

`platform_integrity/`, `ops/platform-integrity/`. Operational authority/run/evidence/receipt protocols, compatibility, backup/retention and local deployment controls. Deep readonly API, evidence observation service and compatibility evaluator; remaining protocols/adapters/migrations/tooling shallow. Depends on PostgreSQL, filesystem, keychain/TLS/clock/credential mechanisms and exact release artifacts. CAP-20. Its eligibility is not application journey success.

## Shared Contracts and Build Governance

`shared/`, application manifests and user-authored `.github/`. JSON schema/catalog, generated Python/TS consumers, vector spec, ports, IDs/authz, schema drift checks, CI/security/release definitions. Deep manifests/CI and contract overview; schemas/tool internals shallow; generated bodies excluded. All components consume some of these boundaries. Current declared versions: [technology stack](technology-stack.md); process/quality caveats: [quality assessment](code-quality-assessment.md).
