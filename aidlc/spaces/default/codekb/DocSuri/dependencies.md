# DocSuri Dependencies

## Internal dependency map

| Producer / caller | Consumer / dependency | Contract and impact |
|---|---|---|
| Backend shell | all mounted backend modules, ops/shared | composition and dependency overrides determine real versus mock/persistent behavior |
| Frontend pages/job UI | BFF, contentJobApi/contracts, backend | cookie-authenticated HTTP/SSE/results; drift can break whole journeys despite isolated tests |
| Discovery | OpenSearch retrieval, embedding, shared DTO/vector spec, ops grounding/cost, personalization | retrieval failures, model dimensions and degraded states affect search |
| Discovery event seam | library history | authenticated search history delivery is part of revisit continuity |
| Library rerun / citation save | discovery / library services | query/paper identity and owner-scoped metadata bridge modules |
| Summarization | full text/doc models, LLM, glossary/cache/job stores, queue, ops | summary and durable-job paths have separate composition; Q-01–Q-04 |
| Evidence/research | discovery, doc-model tool/private coordinator, extraction/assembly, persistence, quota | grounded claims and messages depend on both retrieval and source identity |
| Novelty | discovery/evidence, private coordinator, model/artifact/queue adapters, Notion | manuscript analysis/export spans several persistence and external boundaries |
| Onboarding | accounts/ORCID, personalization event recorder | missing recorder can degrade to state-only completion |
| Plans | account admin authorization, agent quota middleware | tier grants and daily consumption affect analysis availability |
| Ingestion | shared vector/index/doc schemas, source adapters, control state, embedding/storage/index | writer/reader specification mismatch requires explicit corpus compatibility treatment |
| Ops | shared ports and platform integrity | operational guards/evidence are separate from application result contracts |
| Platform integrity | contracts/domain, authority/read adapters, local clock/filesystem/PostgreSQL | exact artifact/generation/config/role bindings govern operational eligibility |

The graph supplied candidate relationships; exact source resolved dynamic composition. Heuristic cross-language edges were rejected (for example a platform API edge to frontend middleware). Do not infer dependency completeness from graph fan-out counts.

## External integration inventory

| Integration | Purpose visible in source | Free/local and continuity question |
|---|---|---|
| arXiv and other corpus-source adapters | metadata/full text and refresh/backfill | terms, license eligibility, rate limits and reproducible corpus identity |
| OpenSearch | lexical/vector search and ingestion writes | local RAM/disk capacity, index rebuild and vector specification compatibility |
| PostgreSQL | user, research/job, corpus-control and operational state | authoritative instances, migration state, backup/restore, role isolation |
| Redis | sessions and optional caches/profile/summary support | restart behavior, session loss and durable versus disposable keys |
| S3-compatible objects | full text/doc models/assets/private uploads/results | authoritative buckets/prefixes, local compatibility, backup and access boundaries |
| SQS-compatible queues | ingestion/doc-model/summary/evidence/novelty work | dispatch wiring, replay/idempotency, DLQ and interruption recovery |
| Bedrock / OpenAI-compatible endpoints | language and embedding tasks | select only free/local operation within measured hardware/quality limits; current cloud path is not budget approval |
| Semantic Scholar | citation references | free access/rate limits, degraded cache behavior |
| Google and ORCID | social identity, ORCID public profile/interests | required registration/settings, privacy/terms and identity migration |
| Email adapters | account verification/reset and trend digests | free/local delivery feasibility and failure visibility |
| Notion | user-approved novelty export | tokens/encryption key continuity, API availability and free limits |
| Observability/cloud integrations | CloudWatch/EventBridge and other operational adapter seams | which are actually used; free/local replacement must preserve outcomes |
| Local OS/containers | launchd, Colima/Docker, filesystem/keychain/TLS/clock mechanisms | one-maintainer repairability, startup and resource/restore proof |

This is an integration inventory, not a declaration that providers are live, required for v2, free at all volumes or legally approved. Provider-specific implementations outside inspected entrypoints are shallow coverage.

## Contract ownership

Shared schemas/catalogs, vector specification and authored ports are central source contracts; generated Python/TS files are outputs. Several application-specific runtime parsers/domain models also exist. The mounted content-job API and frontend have demonstrable disagreement, so generation alone is not sufficient compatibility evidence.

Changing vector model/dimensions/specification affects both ingestion and discovery and may require corpus re-embedding. Changing private document IDs, owner mappings, job IDs or result shape affects persisted state and replay, not merely a TypeScript type. Preserve exact old behavior evidence before selecting new implementations.

## Packaging and supply-chain observations

Python package manifests and frontend package manifest were read; uv/pnpm lockfile presence was inventoried, not fully audited. CI has independent package lanes, schema drift and consumer checks, security audits and a closure audit with pending-package handling. A green lane can only prove its configured scope; module extras and test plugins must be present in the actual interpreter.

No network provider call, package installation, vulnerability lookup, artifact deployment or service mutation was performed by this scan. The isolated SSE check used existing local dependencies and no external service.
