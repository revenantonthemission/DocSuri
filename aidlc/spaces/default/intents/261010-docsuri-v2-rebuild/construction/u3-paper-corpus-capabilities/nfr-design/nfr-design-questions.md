# U3 NFR Design — proposal and confirmation

Date: 2026-10-15 (Asia/Seoul). Unit: `u3-paper-corpus-capabilities`, an embedded library with browser contributions inside the existing application. This is a proposal for the design pass, not the generated design or an implementation approval.

## Sources

| ID | Source | Consequence for this pass |
|---|---|---|
| NR | [Security requirements](../nfr-requirements/security-requirements.md) and [technology decisions](../nfr-requirements/tech-stack-decisions.md) | NFR1–NFR10 derive 34 unit-scoped requirements; every one needs a concrete design solution here. Evidence gates (permissions, model readiness, provider terms, capacity) stay explicit. |
| REVIEW | [NFR requirements review](../nfr-requirements/reviews/review-01.md) | Carried closure tasks: the owner glossary needs derived requirement rows, and the CodeKB technology inventory needs a deliverable reference (upstream-coverage). The functional-design review's findings (FR6.3 participation row, traceability completeness, section floors, upstream references, eligibility-restore path, vocabulary) remain open for that stage. This design must not contradict them. |
| FD | [Functional specification](../functional-design/functional-spec.md) and [rules](../functional-design/rules.md) | Workflows W1–W11, the three state machines, eligibility dominance, watermark/completion integrity, ordered progress and bound results drive the resilience and failure-domain design. |
| CONTRACT | [Canonical contracts](../../../inception/contract-design/contract-summary.md) | C04 projection-writer/publication CAS and change facts; C05 snapshot/history facts; C06 claim/fence/progress/result bindings and settlement; C13 browser binding; C14 accepted-work delivery. The design realizes these mechanisms; it does not redesign the contracts. |
| UNIT | [Unit catalogue](../../../inception/units-generation/unit-of-work.md) and [requirement assignment map](../../../inception/units-generation/unit-of-work-story-map.md) | U3 completes CorpusContent, Discovery and PaperAssistance inside one shared application; U8 verifies the full assembly. |
| UI | [Frontend specification](../functional-design/frontend-components.md) | Discovery/reading/assistance surfaces, distinct announced states, preserved context on reconnect, deliberate confirmations. |
| BASE | Existing U1/U2 assembly | Shared host, PostgreSQL owner transactions, worker control loop, Transport/EventSource web binding. Reuse and extend; no parallel store or delivery mechanism. |
| HUMAN | Confirmed U3 functional and NFR summaries | Retain every current capability; $0 free/local only; one human maintainer with agents; no implicit policy, permission or paid fallback. |
| GIT | [CONVENTIONS.md](../../../../../../../../CONVENTIONS.md) | Fulfilled branches merge by PR into develop; main promotion remains separate. |

## Resolved decisions and ambiguity analysis

- No new human question is needed: the confirmed requirements and contracts already settle the behaviours, degradation states and evidence gates this design must realize. This summary is the remaining human decision before generation.
- Numeric latency/throughput/capacity targets remain measurement-first; this pass designs the measurement-visible surfaces (progress, status, readiness, bounded limits), not numeric values.
- The design must not silently resolve open evidence gates: unresolved source permissions, model readiness, provider terms or capacity appear as designed refusal/degradation states (BR3.1, BR7.6), never as fabricated success.
- The carried review findings are explicit closure tasks for their stages; this pass may rely on their subjects but must not contradict or mask them.

## Proposed design coverage

| Area | Design solutions to specify |
|---|---|
| Authority, eligibility and projection integrity | Current-authority/eligibility enforcement points across read/command/event/asset boundaries; CorpusContent-only projection writing with CAS publication and manifest/receipt completeness; ordered change-fact propagation and restore replay (BR1.1, BR2.3, BR3.1–3.3; NFR4.1, NFR5.2, NFR3.3–3.4). |
| Trust boundaries and input handling | Untrusted query/source/document/render handling with bounded validation and no fabricated content; opaque authorized asset delivery; guest anonymity; private/public identity separation; secret-free receipts and logs (NFR4.3–4.4, NFR5.3, BR6.3). |
| Assisted-work delivery | Durable acceptance with recoverable dispatch; single claim/fence with monotonic ordered progress and snapshot recovery; prepared-result binding and read-only semantics; idempotent settlement reconciliation across owner commits (BR7.2–7.5; NFR1.2, NFR3.1–3.2, NFR3.5, NFR4.2, NFR10.1). |
| Degradation and capacity | Disclosed lexical/semantic fallback; explicit unavailable/refused states for model, provider and capacity shortfalls; finite batch/queue/retry/page/traversal/model-concurrency bounds with clean rejection and backpressure; $0 guardrails against paid fallback (BR4.2, BR7.6; NFR8.1–8.2, NFR2.3). |
| Progress, status and smooth use | One executable state/event contract through the mounted transport (closing Q-01–Q-04 in design terms); reconnect/poll/sleep recovery; distinct announced states; preserved context (NFR2.1, NFR9.2, NFR10.1). |
| Observability and repairability | Safe correlation from user-visible failure to capability/job/dependency evidence; observed/estimated/unknown/stale distinction in readiness; bounded telemetry; one-maintainer diagnosis of representative corpus/search/assistance failures (NFR9.1–9.2, NFR7.1–7.3). |
| Logical components and failure domains | Component-level view: CorpusContent writer/worker boundary, Discovery read path, PaperAssistance acceptance/execution, shared PostgreSQL and worker resources; blast radius of run/publication failure versus read availability; which failures degrade versus halt; where each NFR pattern applies, bridging to Infrastructure Design. |

Performance, scalability, reliability and observability obligations are covered inside these solutions even though this library unit produces no separately deployed service artifacts.

## Artifact plan

1. `security-design.md`: the concrete design for the areas above — enforcement points, trust boundaries, publication/claim/fence mechanics, degradation and capacity behavior, progress/observability surfaces — each mapping back to the derived `NFRx.y` requirements it realizes.
2. `logical-components.md`: the logical component inventory and failure-domain/blast-radius view inside the three owners, identifying shared resources and the isolation strategy.
3. `traceability.json`: every derived `NFRx.y` from NFR Requirements mapped to its concrete design solution, with no unexplained gaps.

Validate IDs, references, cross-contract consistency and unresolved prerequisites, then obtain the required independent architecture review. No implementation or public deployment follows merely from this document generation.

## Assumptions & Open Questions

No new product assumption is adopted. Open evidence gates remain: source copying/parsing/embedding/model permissions; model-readiness evidence for the P1/P2 path; citation-provider terms and freshness; finite workload/accounting/capacity policy; quantitative targets after baseline. The design renders each as an explicit state. Carried review findings stay with their owning stages.

## Consolidated Summary Confirmation

- Define U3's NFR design for authority/eligibility enforcement, CorpusContent-only projection publication with CAS integrity, ordered change-fact propagation and restore replay, realizing every derived NFRx.y requirement.
- Design untrusted-input handling, opaque asset delivery, guest anonymity and private/public separation; secret-free receipts and bounded, truthful error surfaces.
- Design durable assistance acceptance with recoverable dispatch, single claim/fence with monotonic ordered progress, prepared-result binding with read-only semantics and idempotent settlement across owner commits — closing the four recorded job defects in design terms through one executable state/event contract.
- Design disclosed degradation and capacity behavior: lexical fallback, explicit unavailable/refusal states for unresolved permissions/model/providers/capacity, finite bounds with clean backpressure and no paid fallback.
- Design the progress/status/readiness surfaces for smooth use and truthfulness: distinct announced states, reconnect/poll/sleep recovery, observed/estimated/unknown/stale distinction, safe correlation to evidence.
- Provide the logical component inventory and failure-domain view inside CorpusContent, Discovery and PaperAssistance, identifying shared resources (PostgreSQL transactions, worker capacity, model runtime) and the isolation/blast-radius strategy, bridging to Infrastructure Design.
- Keep every evidence gate explicit and carry the review findings as closure tasks for their stages; do not contradict or mask them.
- Produce security design, logical components and traceability; validate them and obtain independent review. Continue serially with automatic ordinary completion and the existing human decision points. Follow CONVENTIONS.md: fulfilled branches merge through PRs into develop; main promotion remains separate.

Does this all look correct before I generate the artifact?

- Looks correct
- Request changes

[Answer]: Looks correct
