# Risk and Sequencing Rationale — Phase 7

## Chosen Strategy

A **Bolt**, one build pass ending in a runnable increment, follows the approved sequence U1 → U2 → U3. The first is a **walking skeleton**, the smallest integrated demonstration of the actual submission-to-result path. The heuristic is skeleton-first risk reduction (the walking-skeleton approach), followed by job-workflow continuity, as selected by the human. No numerical value/urgency scores or duration estimates were supplied, so none are manufactured.

U1 contains the highest integration uncertainty: real dispatch, worker outcomes, exact result identity, effect fencing and cross-runtime compatibility. Finishing U2 next applies that knowledge to translation/reload/replay rather than switching context immediately. U3 then completes the asset journey. This sequence is permitted by the DAG; U3 does not architecturally depend on U2. The scheduled Week 2 security review is independent of the U3 build position so security consideration is not postponed until the end.

## Alternatives Considered

| Alternative | Benefit | Why not selected |
|---|---|---|
| U1 → U3 → U2 | Earlier asset integration/security evidence | Human selected job continuity; retain the October 14 review and pre-release asset follow-up |
| Parallel U2/U3 | Potential elapsed-time reduction | Current single-session serial setting and shared-file coordination remain selected; no measured staffing benefit justifies changing them |
| Isolated backend layer as first finished unit | Smaller apparent first task | Would not meet the approved full submit → SSE → COMPLETED → exact result skeleton |

## Risk Register

Likelihood/impact below are qualitative planning judgments, not measured probabilities. Reassess after the next relevant evidence point.

| Risk | Likelihood / impact | Affected work | Mitigation and evidence | Accountable follow-up |
|---|---|---|---|---|
| Durable effect or prepared-result design cannot safely reconcile a crash | Medium / High | U1, C7 | Design all interruption windows, atomic fencing and durable binding; fail safely without regeneration when exact output is unavailable; prove concurrency/crash fixtures before checkpoint | AI architect/developer; revenantonthemission for scope decisions |
| Current no-op dispatch or legacy adapter duplicates submission | High / High, based on inspected source | U1, C1/C6 | Wire one authoritative dispatch path, verify actual queue/worker progression and retained versus released bindings | AI developer; human readiness contact |
| RDS event IDs mistaken for per-job sequence or malformed SSE frames | High / High, based on inspected source | U1/U2, C3 | Authorized cursor lookup, actual delimiters, watermark reconciliation and multiple-job replay tests | AI developer/QA |
| Translation snapshot captures base rather than final personalization | Medium / High | U1/U2, C2/C7 | Persist final safe payload; verify unchanged exact output after preference changes; use corrected bare DocModel schema fixtures | AI developer/QA |
| API/worker/frontend mixed versions process incompatible work | Medium / High | U1 exposure | C8 compatibility matrix, reader/worker readiness before message/UI activation, old-worker drain/isolation and tested rollback | revenantonthemission with pipeline/deployment work |
| Missing staging/session/queue/persistence access | Unknown / High | Integrated U1 verification | Kickoff readiness check and repeat before integrated run; escalate access dependency, never substitute mocks as end-to-end proof | revenantonthemission |
| Existing test scripts differ from affirmed tooling claims | High / Medium, source mismatch observed | All units | Inspect and reconcile actual runnable lint/typecheck/coverage/E2E commands during approved implementation; preserve coverage floor | AI developer/QA |
| XL first Unit stretches schedule | Medium / High | U1 and later dates | Internal design/backend/frontend milestones, evidence-based estimate updates, no invented completion date or unapproved decomposition | revenantonthemission with delivery role |
| Week 2 review occurs before asset code exists | Medium / Medium | U3 security evidence | Keep October 14 available-work review; require code-based follow-up and disposition before asset release | revenantonthemission |
| Missing meaningful image/table equivalents | Unknown / High for accessibility | U3 | Verify actual authorized data; surface gaps before conformance claims, do not invent OCR scope | revenantonthemission with design/QA |
| Staging latency targets fail | Unknown / High for acceptance | U2/U3 and release | Measure approved profile/raw samples; investigate without relaxing limits or counting failed operations as fast successes | AI QA; human resolves remediation |

## Schedule and Escalation

Construction starts 2026-10-05; security review is 2026-10-14. No target completion dates exist for U1/U2/U3. External lead times remain unverified until owners confirm them. A slipped prerequisite moves the relevant verification/exposure milestone, not the requirement. Escalate concrete blockers with evidence and the affected contract or acceptance criterion. A need for new backend behavior outside the bounded amendment or new deployment architecture requires an explicit scope decision.

## Acceptance and Historical Findings

Requirements review R-01/R-02 remain accepted wording risks upstream. This plan carries the exact full skeleton path and runtime SSE connection-latency instrumentation (construction-to-open, milliseconds) into execution criteria; it does not claim those upstream findings were rewritten. Later story/mockup/domain/contract corrections have recorded resolved findings. Runtime verification and implementation reviews remain separate obligations.
