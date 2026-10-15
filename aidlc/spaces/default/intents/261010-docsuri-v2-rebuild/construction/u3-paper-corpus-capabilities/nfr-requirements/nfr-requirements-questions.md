# U3 NFR Requirements — proposal and confirmation

Date: 2026-10-15 (Asia/Seoul). Unit: `u3-paper-corpus-capabilities`, an embedded library with web contributions inside the existing application. This is a proposal for the requirements pass, not the generated requirements or an implementation approval.

## Sources

| ID | Source | Consequence for this pass |
|---|---|---|
| FD | [Functional specification](../functional-design/functional-spec.md) and [rules](../functional-design/rules.md) | Canonical identity/eligibility precedence, verified completions and watermarks, disclosed lexical/semantic degradation, snapshot-bound windows, bounded citations, durable assistance acceptance with ordered progress and bound results, glossary CAS and honest refusal states. |
| REVIEW | [Independent functional design review](../functional-design/reviews/review-01.md) | Two Major findings carried as closure tasks: U3's FR6.3 lifecycle participation is not yet reflected in a deliverable, and `traceability.json` is missing upstream rows (FR19.1–FR19.3 among unit-named rows) while two artifacts fall below the required-sections floor and three consumed sources are unreferenced. Resolve before the affected gate; implementations must not inherit the gap. |
| REQ | [Inception requirements](../../../inception/requirements-analysis/requirements.md) | All ten NFRs remain applicable; FR1–FR4/FR9/FR18 and the Q-01–Q-04 defect dispositions are this unit's principal acceptance surface. Numeric task, latency and recovery targets follow the measured baseline and human agreement. |
| UNIT | [Unit catalogue](../../../inception/units-generation/unit-of-work.md) and [requirement assignment map](../../../inception/units-generation/unit-of-work-story-map.md) | U3 completes CorpusContent, Discovery and PaperAssistance inside one shared application; full parity remains distributed across the approved units and U8 integration. |
| CONTRACT | [Canonical contracts](../../../inception/contract-design/contract-summary.md) | C04–C06 pin projection-writer authority, eligibility precedence, snapshot semantics, assistance claim/fence/progress/result bindings and glossary revisions; C13/C14 pin the mounted transport and accepted-work delivery. Contract coordination precedes affected code. |
| UI | [Frontend specification](../functional-design/frontend-components.md) and [approved visual mapping](../../../inception/refined-mockups/design-system-mapping.md) | Korean responsive discovery/reading/assistance surfaces, inherited colors, Apple HIG web adaptations, appearance modes and WCAG 2.2 AA target. |
| TECH | [CodeKB technology inventory](../../../../../codekb/DocSuri/technology-stack.md) | Dated manifest evidence only; it does not establish current runtime, security support, public capacity, provider terms or v2 selection. |
| U1U2 | [Existing application infrastructure design](../../u1-integrated-paper-journey/infrastructure-design/infrastructure-specification.md) and the completed U2 contribution | U1 selected the common PostgreSQL transaction facility for local implementation and native Python/API plus static React/TypeScript web bindings; U2 completed the account/authority foundation on the same owners. Verify actual current adapters/versions and incremental fit before extending them; historical design statements are not live operating proof. |
| HUMAN | Confirmed rebuild constraints and the U3 functional confirmation | Retain every current capability; $0 free/local only; one human maintainer with agents; no fixed deadline; no implicit migration, retention, provider or paid fallback. |
| GIT | [CONVENTIONS.md](../../../../../../../../CONVENTIONS.md) | Completed branches merge by PR into develop under the interim CI policy; main promotion remains separate. |

## Resolved decisions and ambiguity analysis

- The user already selected baseline-first numeric quality targets. Do not ask for arbitrary latency, availability or recovery numbers now. Define the measurement, environment, workloads, evidence and decision checkpoint; finite admission policies must still exist before operation.
- The user already selected the $0 free/local budget, one human maintainer, full-capability scope, serial construction and automatic ordinary completion. None is reopened by this pass.
- Enabled summary/plan confirmations and verification/failure decisions still apply. This summary is the remaining human decision before generation.
- The model-readiness evidence (P1/P2 grounding), source-permission resolution, citation-provider terms, finite accounting/capacity policy and quantitative targets are real evidence prerequisites. Unresolved states yield explicit refusal/degradation; they never justify fabricated output or paid fallback.
- U1's recorded normal-assistance, semantic-search and figure limitations remain explicit; U3's requirements must make their closure verifiable, not restate them as complete.
- The functional-design review findings are explicit closure tasks for that stage's revision/gate (participation row, traceability completeness, section floors, upstream references, restore path, vocabulary); this pass must not silently absorb or contradict them.

## Proposed assessment and evidence

| Category | U3 requirements to derive | Verification evidence to require |
|---|---|---|
| Complete-task correctness | Find/refine, read, cite, understand, glossary and corpus-maintenance outcomes; distinguish acknowledgement, accepted work, completed effects and unknown states across the mounted browser/service/worker path | Real mounted positive, negative and recovery scenarios with authoritative state/effect assertions; fixture providers clearly distinguished from public behavior; the four recorded job defects exercised through the real transport. |
| Responsiveness and capacity | Time to usable search/content, input feedback, job acceptance, first progress, prepared-result read and bounded page reads; contention between ingestion/projection publication and concurrent reads; bounded queue/retry/embedding/model work | Cold/warm distributions, sample sizes and representative/concurrent boundary workloads; finite pools, batch/queue sizes, retries, page/traversal limits and storage with recovery headroom. |
| Security and privacy | Current authority and ownership at every read/command/event/asset boundary; opaque asset handles; guest anonymity; source permission and consent enforcement before processing; untrusted document/query input; secret-free delivery | Positive/negative access matrix at every applicable boundary, stale/withdrawn/foreign-source checks, replay and fence checks on worker events, traversal/URL/unsafe-markup checks and secret-redaction checks. |
| Durability and interruption recovery | One intended effect per accepted command; durable acceptance with recoverable dispatch; ordered progress that survives reconnect/sleep/restart; no completion or watermark past verified work; repeatable non-corrupting rebuild/retry | Store/connection/restart/clock/late-event/interrupted-batch fault injection; unchanged eligibility boundary on recovery; isolated restore replaying current withdrawal boundaries; duplicate/lost-response reconciliation. |
| Corpus and retrieval integrity | Canonical identity/versioning across duplicate/reordered records; eligibility dominance over caches/indexes/restores; snapshot-bound pagination; disclosed degradation; bounded labelled citation traversal | Duplicate/reordered batch properties, withdrawal-versus-cache checks, snapshot expiry and stable-window checks, lexical/semantic fixture relevance, bounded cyclic graphs, provider-limit schedules. |
| Assistance job integrity | Immutable accepted binding; single claim/fence with no late regression; progress not proof of completion; prepared-result binding and read-only semantics; idempotent settlement; honest refusal | Crash-after-acceptance, duplicate delivery/completion, replaced-worker, expired-result, unknown-settlement and ineligible-source checks through real execution and the mounted transport. |
| Accessibility and smooth interaction | Korean labels, focus, announced status/errors, deliberate confirmation for effectful actions, keyboard/zoom/reflow, readable inherited colors and Light/Dark/System; preserved context across interruption and re-authentication | Implemented browser and assistive-technology matrix with recorded observations; no former-owner or stale-generation flash; no automatic command replay; no conformance claim from design prose. |
| Repairability and observability | One-maintainer reproducible setup/repair of the corpus/search/assistance paths; exact dependency/configuration identities; safe correlation of user-visible failures to service/job/dependency evidence; truthful capability readiness incl. unavailable model/index | Clean setup and representative defect/recovery exercise; safe correlation without credentials/private text; bounded telemetry; readiness distinguishing observed, estimated, unknown and stale. |
| Technology and integration | Reuse/extend the existing application through owner contracts; evaluate needed free/local projection, embedding, parsing and model choices against required guarantees; citation-provider terms and limits | Current source/configuration/lockfile checks, focused compatibility and capacity evidence, verified permitted use and free limits before selection; C04–C06 operation/binding checks on the real boundary. No paid fallback or separate service by assumption. |

## Artifact plan

For this library unit the applicable outputs are:

1. `security-requirements.md`: owner/source/guest authority, projection-writer and eligibility enforcement, assistant claim/fence/result bindings, transport framing/reconnect, provider and untrusted-input handling, and data-protection requirements, with explicit cross-cutting correctness, recovery, accessibility, capacity and observation requirements for this unit's interfaces.
2. `tech-stack-decisions.md`: the existing integration baseline, alternatives and evidence-backed decisions or unresolved choices for corpus storage/parsing, retrieval projection, embeddings, local model execution, citation providers and job delivery; bounded measurement requirements, contract coordination and one-maintainer repairability. Performance, scalability, reliability and observation obligations remain covered here and in the security requirements even though this unit has no separate service deployment.
3. `traceability.json`: NFR1–NFR10 to unit-scoped derived `NFRx.y` IDs, with no unexplained exclusions. IDs indicate requirement coverage, not test completion.

Validate IDs, references, cross-contract consistency and unresolved prerequisites, then obtain the required independent architecture review. No implementation or public deployment follows merely from this document generation.

## Assumptions & Open Questions

No new product assumption is adopted. Required evidence/decisions remain: source copying/parsing/embedding/model permissions per paper and provider; model-readiness evidence for the P1/P2 understanding path; citation-provider terms and freshness bounds; finite workload/accounting/capacity policy; quantitative targets after baseline. Resolve each before its affected choice or implementation. The functional-design review findings remain explicit closure tasks for that stage, not silent exceptions.

## Consolidated Summary Confirmation

- Define U3's quality and security requirements for corpus ingestion/publication, source-change and withdrawal propagation, discovery and citations, reading, assistance work and the owner glossary, preserving all ten inception NFRs and every current capability.
- Require current authority, ownership and source eligibility at every affected boundary; opaque asset delivery; guest anonymity; untrusted-input handling; and one intended durable effect per accepted command with honest unknown states.
- Require canonical identity, eligibility dominance over caches/indexes/restores, snapshot-bound windows, disclosed lexical/semantic degradation, bounded labelled citations, and completion/watermark integrity that never advances past verified work.
- Require durable assistance acceptance with recoverable dispatch, single claims with monotonic progress, results bound to the accepted request with reads that never regenerate work, idempotent settlement and honest refusal when model/content/capacity evidence is unresolved.
- Define repeatable measurements for complete-task success, responsiveness, interruption recovery and defect reproduction/repair; the Q-01–Q-04 defects close through the real mounted transport. Numeric service targets follow the baseline and your agreement; finite limits remain mandatory before operation.
- Build on the existing shared application and verify its current bindings. Evaluate needed free/local projection, embedding, parsing and model extensions against security, permitted use, resource fit and repairability; distinguish selected, candidate and evidence-blocked choices. Preserve the $0 budget and one-maintainer model without paid fallback or silent feature cuts.
- Keep source permissions, model readiness, citation-provider terms, accounting/capacity policy and quantitative targets as explicit prerequisites. U1's recorded assistance/search/figure limitations remain open until their verification closes here. Carry the functional-design review findings as explicit closure tasks, not silent exceptions.
- Preserve the Korean responsive workspace, inherited colors, Apple HIG web adaptations, Light/Dark/System and WCAG 2.2 AA target. Produce the library unit's security requirements, technology decisions and traceability, covering its performance/capacity/reliability/observability contributions; validate them and obtain independent review. Continue serially with automatic ordinary completion and the existing human decision points. Follow CONVENTIONS.md: fulfilled branches merge through PRs into develop; main promotion remains separate.

Does this all look correct before I generate the artifact?

- Looks correct
- Request changes

[Answer]: Looks correct
