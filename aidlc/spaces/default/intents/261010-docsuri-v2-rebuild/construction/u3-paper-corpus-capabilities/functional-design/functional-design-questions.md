# DocSuri v2 — U3 Functional Design proposal

Date: 2026-10-15 (Asia/Seoul).
Unit: `u3-paper-corpus-capabilities`.

## Context and carried-forward decisions

The workflow resumes Construction on the current working branch
`feature/docsuri-v2-u2-account-personal-controls`, which carries the integration
assembly: U1 (PR #44, commit `1c2cbd5c`) and U7 (PR #45, `5fbccc1f`), plus the
completed U2 contribution whose checkpoint was approved on 2026-10-15. U2's
PR/merge handoff into `develop` under CONVENTIONS.md remains a separate human
step; this proposal is a design record and changes no application behavior.

The approved unit catalogue assigns U3 the completion of **CorpusContent**,
**Discovery** and **PaperAssistance**, with their WebWorkspace views, and the
reference's retained public-paper actions, filters, modes, languages and
presentation levels, glossary, citations, assets and source-only or
unavailable-content states. The shared component owners remain authoritative;
U3 is an embedded contribution to the same application, not another corpus,
search or job service.

The existing question records and U3-scoped answer history were checked
(`functional-design` for this unit has no recorded answer). Earlier answers
already establish:

- A multi-user web service with public registration and existing anonymous
  search, retaining every current capability for the first v2 release.
- A $0 budget, free/local choices, one human maintainer with coding agents,
  serial construction, and automatic ordinary completion checkpoints.
- A Korean responsive workspace with inherited blue/neutral colors, Apple HIG
  web adaptations, Light/Dark/System and the WCAG 2.2 AA target.
- Evidence-dependent model, provider, capacity and corpus-permission decisions;
  numeric quality targets follow baseline measurement and human agreement.
- CONVENTIONS.md governs Git: working branch through a PR into develop;
  fulfilled branches merge, and release promotion to main remains separate.

U2 owns complete library/canonical-disposition consumption and account/lifecycle
participants; U3 supplies the corpus-change implementation and the complete
eligible-source/retrieval contracts consumed later by U4/U5. U1's recorded
normal-assistance, semantic-search and figure limitations remain explicit; U3
must reconcile them rather than restate them as complete.

## Proposed design coverage

| Area | Functional design responsibility |
|---|---|
| Corpus ingestion and publication | Source scope, eligibility, canonical identity/version, deduplication, incremental refresh, rebuild, watermarks, publication generations and completion evidence (FR18.1, FR18.3; C04 `acceptCorpusRun`–`readPublishedProjection`). |
| Source change and withdrawal | Authoritative eligibility revisions, change facts and withdrawal propagation; current eligibility wins over stale caches/indexes/restores; saved references receive explicit dispositions through the change facts (FR18.2, FR5.3; C04 `changeSourceEligibility`, `readSourceChanges`). |
| Discovery and refinement | Query vocabulary, lexical and semantic outcomes with disclosed fallback, filters/order/rerun, snapshot-bound pagination, truthful empty/partial/error states and bounded recovery (FR1.1–1.3; C05 `search`). |
| Citations | Cited/citing exploration, bounded traversal, freshness behavior, unknown/stale/partial sources and eligible saves through Library (FR9.1–9.2; C05 `readCitations`). |
| Reading and assets | Structured text, figures, anchors and source links for the exact paper/version; absent/building/unsupported/failed/withdrawn/restricted dispositions with bounded malformed-content behavior and no fabricated text (FR2.1–2.2; C04 `resolvePaper`, `readContent`, `readAsset`). |
| Assistance work | Complete summary/translation/presentation choices, durable acceptance and dispatch responsibility, ordered progress and terminal recovery through the mounted transport, prepared-result semantics and the four recorded job defects (FR3.1–3.4; C06, C14). |
| Owner glossary | Normalization, uniqueness, CAS update behavior and use by eligible output; committed terms survive failed or concurrent writes (FR4.1–4.2; C06 `readGlossary`, `replaceGlossary`). |
| Shared browser surfaces | Query/filter/result list, paper identity/reading surface, activity card and prepared result, glossary and citation panels with the approved Korean responsive/accessibility contract (interaction specification C02–C04; NFR2/NFR6). |

Trace every U3 assignment and contribution in the requirement-to-unit map.
Distinguish U3's own closure evidence from later consumer integration: U2 owns
saved-reference records and lifecycle coordination; U4/U5 consume the published
eligible-source/retrieval contracts; U8 verifies the full assembly. Do not
create reverse construction dependencies to claim premature parity.

## Current evidence and unresolved policy boundaries

C04 (v2.0.0) already records the accepted projection-writer closure: R-01 makes
CorpusContent the sole logical projection writer and publication authority, and
`writeProjectionBatch`/`publishProjectionGeneration` define the compatibility
and completion evidence, including withdrawal propagation. U3 carries the
Contract Design re-check when that behavior lands in code; it is not reopened
as a design question here. C05/C06 likewise record the search-fact, glossary
and assisted-work semantics.

A bounded reference check confirms the four recorded job defects are acceptance
obligations, not wire-format instructions: mounted job state omitting the
browser's ordering field (Q-01), result-endpoint/browser shape disagreement
(Q-02), a no-op acceptance callback (Q-03) and escaped-newline stream frames
(Q-04). They close through FR3.2–3.4/NFR10's one executable state/event and
prepared-result contract.

Keep these prerequisites explicit, with responsible owner and closure evidence:

- Permitted source copying, parsing, embedding and model use per paper and
  provider before affected processing; unresolved permissions yield a truthful
  `POLICY_UNRESOLVED`/ineligible outcome, never fabricated content (NFR5).
- Model readiness evidence for the P1/P2 understanding path before normal
  summary/translation output is claimed; unavailable execution remains an
  explicit, recoverable state (FR3.1, NFR1/NFR8).
- Citation-provider terms, rate limits and freshness bounds before public
  acceptance; a fixture exchange establishes only its limited test path.
- Finite workload, accounting and capacity policy for protected assisted work
  before enforcement; no paid fallback and no invented numeric limits.

The logical design can specify eligibility checks, option vocabularies,
dispositions and refusal/recovery states without choosing these unresolved
values. If a workflow cannot be described coherently without a new product
decision, ask that focused question before generating the affected design. No
additional interview is needed for the already-approved component boundaries
and contract semantics above.

## Corner-case and validation plan

Sweep each U3 component against malformed/oversized/Unicode queries and source
records, empty/one/many results, duplicate and reordered source batches,
partial writes between object/control/index states, index or model
incompatibility, snapshot expiry and changed windows, withdrawal racing
in-flight reads or publication, provider rate limits and stale citation data,
worker restart and reconnect after missed stream events, sleeping tabs,
repeated/out-of-order events, expired results, and guest-versus-owner boundary
attempts. Distinguish confirmed completion, explicit failure and unknown
outcome; never advance a watermark or completion flag past verified work.

Produce entities.md and rules.md with authoritative YAML, functional-spec.md
with ordered workflows/state machines and derived diagrams,
frontend-components.md for the embedded public-paper views, and
traceability.json. Check identifiers, ownership, canonical bindings,
transitions, dependency direction and requirement coverage, validate
diagrams/escaping, and obtain an independent architecture review. This stage
changes design records, not application behavior or user data.

## Sources

- [UC] [Unit catalogue](../../../inception/units-generation/unit-of-work.md), U3 and component responsibilities.
- [UM] [Requirement-to-unit map](../../../inception/units-generation/unit-of-work-story-map.md), all rows naming U3 and applicable NFRs.
- [RQ] [Requirements](../../../inception/requirements-analysis/requirements.md), especially FR1–FR4, FR9, FR18, the Q-01–Q-04 defect dispositions and open policy dependencies.
- [DC] [Component catalogue](../../../inception/domain-design/components.md), CorpusContent, Discovery, PaperAssistance and their consumers.
- [CT] [Canonical contracts](../../../inception/contract-design/contract-summary.md), C04–C06, C13 browser binding, C14 accepted-work delivery and open questions.
- [UX] [Interaction specification](../../../inception/refined-mockups/interaction-spec.md) and [design-system mapping](../../../inception/refined-mockups/design-system-mapping.md), public-paper surfaces.
- [RE] Reverse-engineering capability records for CAP-01–CAP-03, CAP-09 and CAP-18 in `aidlc/spaces/default/codekb/DocSuri/`; bounded reference evidence, not an exhaustive parity audit.
- [U1] [U1 code evidence](../../u1-integrated-paper-journey/code-generation/code-summary.md), implemented assembly and carried limitations.
- [Git] CONVENTIONS.md and current local Git history; no main promotion is authorized by this design step.

## Consolidated Summary Confirmation

- Complete U3's public paper, discovery and corpus capabilities within the
  existing owners — CorpusContent, Discovery, PaperAssistance and their
  WebWorkspace views. Retain every current capability and the $0 free/local
  constraint.
- Specify ingestion, incremental refresh, rebuild, canonical identity, version
  handling, deduplication, watermarks and retry/recovery. A publication is not
  a source-of-truth backup and no watermark or completion state may advance
  past verified work.
- Specify withdrawal and source-change propagation: current eligibility wins
  over stale caches, indexes and restores; saved references receive explicit
  dispositions through the corpus-change facts while U2 keeps the reference
  records.
- Specify discovery and citations: lexical and semantic outcomes with explicit
  disclosed fallback, filters/refinement/order/rerun, snapshot-bound pagination,
  truthful empty/partial/error states, and bounded citation traversal with
  provider freshness and degradation that never fabricates edges.
- Specify reading and assistance: structured content, figures, anchors and
  source links; source-only and unavailable dispositions; the complete
  summary/translation/presentation-choice set with durable acceptance,
  recoverable dispatch, ordered progress and honest prepared-result semantics.
  Close the four recorded job defects through one executable state/event and
  result contract; reads and reconnects never start work.
- Keep owner glossary semantics, truthful option availability and refusal
  states explicit while model and content-permission evidence is unresolved; no
  fabricated output and no hidden paid fallback.
- Extend the approved Korean responsive workspace, inherited colors, Apple HIG
  adaptations, appearance modes and accessibility target across the
  discovery, reading and assistance flows; preserve context across
  interruption, reconnect and sign-in changes.
- Produce entity/rule models, behavioral and frontend specifications and U3
  traceability, check consistency and obtain independent architecture review.
  Continue serially with automatic ordinary completion and the existing human
  decision points. Merge completed branches through PRs into develop under
  CONVENTIONS.md; main promotion remains separate.

Does this all look correct before I generate the artifact?

- Looks correct
- Request changes

[Answer]: Looks correct
