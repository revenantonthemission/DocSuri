# DocSuri Business Overview

## Purpose and evidence boundary

DocSuri combines scholarly paper discovery, reading assistance and a personal research workspace. The approved v2 audience is researchers and engineers who need to find and understand papers. The anchor journey is **find → understand → save → revisit**; first-release parity includes the other capabilities below, not just that journey.

This is a fresh source-based inventory at Standard depth, dated 2026-10-11. “Present” means implemented source or a declared interface, not a verified deployment, adoption claim or passing user journey. Feature flags, configuration, optional dependencies and mock/in-memory adapters affect availability. [Coverage](reverse-engineering-timestamp.md) distinguishes deep reading from shallow inventory. [Quality assessment](code-quality-assessment.md) owns defects and verification limits.

## Capability inventory for parity

| ID | Capability and user outcome | Current source surface | Availability / continuity dependency |
|---|---|---|---|
| CAP-01 | Search papers, view metadata, refine and rerun queries | discovery search API; frontend search and paper pages | OpenSearch corpus; lexical/semantic configuration; embedding degradation path |
| CAP-02 | Read structured full text, figures and document anchors, or follow source links | summarization document-model/assets routes; frontend document viewer | ingestion-built artifacts, storage, version identity and feature/license gates |
| CAP-03 | Request summaries and translation, choose presentation level, track work and retrieve results | summarization orchestration and content-job API; frontend paper/translation actions | LLM, storage, queues, durable jobs; current integration defects in Q-01–Q-04 |
| CAP-04 | Maintain terminology/glossary preferences | GET/POST glossary | authenticated account and glossary persistence |
| CAP-05 | Save papers, save searches, inspect/clear history and rerun past searches | library controllers and services | owner-scoped saved rows, search gateway and history event delivery |
| CAP-06 | Register, verify email, log in/out, reset/change password, change email, delete/reactivate account | accounts controller and lifecycle services | account DB, session store, email provider, retention/restore semantics |
| CAP-07 | Link Google/ORCID identities, inspect ORCID profile; use administrator MFA | account OIDC/MFA surfaces and mypage | provider credentials/settings, identity mappings, administrator policy |
| CAP-08 | Manage account profile, consents and subscription presentation | mypage | subscription adapter is mock; no inference of real billing |
| CAP-09 | Explore citation relationships and save eligible referenced papers | citation-tree controller | Semantic Scholar, Redis or process cache, library integration; feature gated |
| CAP-10 | Personalize search/summary defaults, inspect recent papers, opt out/delete behavior/reset profile | personalization; frontend settings/recent views | behavior events/profiles/settings, bounded enrichment and feature flags |
| CAP-11 | Select or skip onboarding interests, derive optional ORCID suggestions | onboarding | stored onboarding state; personalization event seam; ORCID best-effort suggestions |
| CAP-12 | Follow topics, configure research digests and unsubscribe | trends controller, digest machinery | followed topics, digest watermarks/send log, email and scheduler configuration |
| CAP-13 | Ask evidence-grounded research questions, compare claims and quotations, include attachments and web references | evidence agent and research sessions | search, document models, extraction/assembly, local or external LLM, owner-scoped attachments |
| CAP-14 | Save/reopen research sessions and messages, observe progress and pending work, delete one/all sessions | research session controllers and repositories | durable session/message rows and worker completion |
| CAP-15 | Analyze topic/manuscript novelty, track/cancel jobs, discuss results and inspect artifacts | novelty controller/service/worker | manuscript text/PDF, retrieval/evidence, queue, artifact/event/message stores |
| CAP-16 | Connect Notion, preview and explicitly approve novelty export | novelty service and adapters | encrypted per-owner token, export state, Notion availability and external limits |
| CAP-17 | Inspect plan quotas; administrator grants/revokes a tier | plans; shared agent quota middleware | assignments and daily usage; no payment endpoint |
| CAP-18 | Operate corpus ingestion, refresh/rebuild, canonical deduplication, withdrawal handling and recovery | ingestion CLI/worker/application | control-plane state, source terms, embedding/index compatibility, object storage and queues |
| CAP-19 | Observe incidents, cost/grounding/reliability signals and service health | ops package and administrator APIs | configured telemetry/adapters; in-memory fallbacks do not prove durable operations |
| CAP-20 | Assess platform evidence/compatibility and execute controlled operational protocols | platform_integrity package and ops tooling | local authority, evidence, receipts, clock, PostgreSQL/filesystem and operator bindings |

Evidence anchors: `backend/wiring.py:1010` mount registry; source-declared endpoint inventory in [API documentation](api-documentation.md); component paths in [component inventory](component-inventory.md). Operational CAP-18–20 are preservation dependencies as well as maintainer capabilities; they are not new proposed product features.

## Core journey and stored state

1. Find a paper through search. Discovery validates the request, chooses lexical or semantic retrieval, ranks and applies grounding before returning cards. Authenticated searches can feed history.
2. Understand it using metadata, structured text/assets, summary/translation, citations or research/evidence interactions. Each route can be unavailable, building, pending or abstaining; v2 must preserve truthful states.
3. Save the paper or query in the owner-scoped library.
4. Revisit saved items/history, recent papers or research sessions using stable paper/job/account identities.

The current implementation contains browser and server contracts that disagree on the paper-job boundary; the existence of these screens and tests does not prove this journey works. See Q-01–Q-04.

## Business rules visible in source

- Owner identity comes from an authenticated principal; user-owned repositories and private document identities must preserve isolation.
- Private uploads are separate from public corpus document reads. The upload coordinator re-derives private identity from owner, scope and attachment.
- Citation display bounds node count and degrades on provider failure. Only eligible nodes can be saved.
- Evidence generation can abstain for missing corpus, insufficient evidence, unavailable model or cost degradation. Optional web references are appended after evidence extraction, not fed into it.
- Novelty export follows preview and explicit approval before external publication.
- Mock subscription presentation and administrator-assigned plans must not be described as a functioning paid billing system.
- The approved v2 constraint is $0, free/local stacks only. Existing cloud adapters are evidence to evaluate, not permission to keep paid dependencies.

## Open business and continuity evidence

No user count, revenue, usage frequency, market validation or stakeholder endorsement was established. No authoritative deployment, existing-user inventory, restore-tested backup or retention/legal decision was established. Inventory candidate data classes in [architecture](architecture.md) before deciding migration. Preserve all capability outcomes while evaluating free/local feasibility; bring evidenced conflicts to the human approver rather than silently removing features.
