# U1 performance, correctness and interaction requirements

Date: 2026-10-11. Unit: `u1-integrated-paper-journey`.
Status: required behavior and measurement design; no benchmark or implementation
acceptance has run in this stage.

## Scope and authority

This document derives NFR1, NFR2 and NFR6 from the
[inception requirements](../../../inception/requirements-analysis/requirements.md).
It applies to the real P1/P2 find → understand → save → revisit contribution in
[Functional Design](../functional-design/functional-spec.md), its
[rules](../functional-design/rules.md) and
[frontend specification](../functional-design/frontend-components.md).
All later-unit capability variants remain required for the first v2 release.
The [confirmed NFR proposal](nfr-requirements-questions.md) preserves baseline-first
target selection: no response-time, throughput or success-rate target is invented
here. Correct ownership, source binding, truthful feedback and durable saves are
already binding invariants, regardless of eventual speed targets.

## Detailed requirements

| ID | Accountable owner and scope | Observable obligation | Verification and source mapping | Status / prerequisite |
| --- | --- | --- | --- | --- |
| NFR1.1 | WebWorkspace coordinates; each domain owns its outcome. Complete U1 journey, including fresh authenticated return. | A normal task succeeds only when the research query finds the intended version, source-bound assistance meets its rubric, paper/query saves are acknowledged and persistent, and the same owner rediscovers the saved work and retained result. Negative/recovery cases must produce their specified disposition with no unauthorized, lost acknowledged or duplicate intended effect. A passing intermediate screen cannot stand in for task completion. | Execute the P1/P2 protocol below through the actual browser, service, store and executor; inspect committed identities and effects. Count normal, negative and recovery attempts separately. WF1–WF7; BR2.1, BR3.2–BR3.3, BR4.1, BR4.5, BR5.1, BR7.5; LC02–LC09/LC14 and FUI-02/FUI-05–FUI-09. | Binding; unexecuted. Permitted fixtures, canonical contract coordination, finite policy, real runtime and baseline evidence are prerequisites. Human agrees any numeric success target after the baseline. |
| NFR1.2 | PaperAssistance owns useful output; CorpusContent owns source identity/eligibility; a competent reviewer assesses meaning. Summary and a supported translation. | Published output must preserve exact paper/version/content and accepted options, distinguish limitations/partial evidence/abstention, and satisfy the approved source rubric. Fluency, model completion or a valid response shape alone is insufficient. Unsupported or insufficient input yields an explicit disposition, never invented source support. | Preserve eligible source hashes, input/options/model configuration, output and reviewer findings. Check P1 and P2 concepts and anchors below; compare a supported translation pair against the same source for meaning and terminology. Include missing/insufficient-content and malformed-output cases. WF3–WF6; BR2.1–BR2.2, BR5.1, BR5.8–BR5.9; LC04/LC06 and FUI-05/FUI-07. | Binding; output evaluation not yet executed. Processing rights, supported vocabulary, empty-glossary revision and exact result binding must be resolved before the affected run. No model selection follows from this requirement. |
| NFR2.1 | ServiceOperations maintains the measurement record; WebWorkspace and each timed domain supply boundaries. Normal operation, queueing and recovery. | Record end-to-end timing and its constituent waits using the boundaries below, alongside outcome, workload and resource use. Preserve failed, rejected, timed-out and incomplete attempts. Propose response-time, throughput and latency budgets only from the measured environment and complete-task evidence; obtain human agreement before treating them as readiness thresholds. | Repeat cold/warm P1/P2 and declared mixed-load cases; record counts, raw samples and distributions, accepted/completed/rejected throughput, CPU/memory/storage/network conditions and timing uncertainty. WF1–WF7; BR5.2, BR5.7, BR5.9, BR7.2–BR7.3; LC10/LC13/LC14 and FUI-13. | Measurement method defined; numeric targets deferred. Immutable original acceptance time and authoritative timing semantics require canonical coordination before instrumentation is accepted. |
| NFR2.2 | WebWorkspace, with Discovery, Library and PaperAssistance authoritative states. Feedback, overlapping requests and interrupted interaction. | Keep query controls and committed context usable during loading, empty, degraded and failed states. Separate edited query from submitted result context; suppress superseded/account-mismatched responses. Distinguish pending, unknown, committed, stale and terminal outcomes; bounded reconnect/read recovery cannot submit new work, debit or overwrite a concurrent edit. | Record interaction feedback delays and state traces during rapid submissions, slow old responses, two tabs, lost acknowledgement, expiry, sleep and SSE interruption. Verify no indefinite loading after the applicable finite deadline/recovery disposition. WF1–WF2/WF4/WF6–WF7; BR1.5, BR3.4, BR4.2–BR4.3, BR5.7/BR5.9–BR5.10, BR6.1–BR6.2; LC06–LC09/LC11 and FUI-03/FUI-06–FUI-12. | Binding state behavior; timing targets await baseline. Recovery and admission deadlines must be finite and configured before enabling affected operations; an unset latency target is not permission for unbounded waiting. |
| NFR6.1 | WebWorkspace owns rendered interaction; content owners supply meaningful structure and alternatives. U1 pages and state transitions. | Implement and assess the approved WCAG 2.2 AA target across the accessibility matrix below, including accessible authentication, keyboard/focus, labels/errors, status announcements, contrast, reflow/zoom and long paper content. Passing automated checks alone does not establish conformance. | Combine automated rendered checks with recorded manual keyboard and assistive-technology runs, versioned browser/OS/assistive tools and criterion-level findings. WF1–WF7; BR2.3, BR6.1–BR6.4; LC11 and FUI-12. | Approved design target; implementation verification pending. Applicable criteria and any justified exceptions require evidence, not a blanket claim from the prototype or token palette. |
| NFR6.2 | WebWorkspace owns integrated presentation and navigation. Korean desktop-first interface with complete U1 phone/tablet use. | Preserve inherited blue/neutral tokens, Apple HIG web adaptations, Light/Dark/System, context and readable research content across layouts. Navigation, source/result return and authentication recovery preserve authorized committed context without automatic mutations. Theme-storage failure remains usable and truthful about persistence. | Exercise the complete journey in the responsive/state matrix, including dynamic system appearance, long Korean/English content, back/forward, resize, failed storage and same-/different-account return. Compare displayed identities/options with acknowledged domain records. WF1–WF7; BR1.5, BR3.4, BR4.5–BR4.6, BR6.1–BR6.4; LC07/LC09/LC11 and FUI-08/FUI-11/FUI-12. | Binding; rendered and task-based usability evidence pending. Mockups and engineering checks do not imply end-user validation. Durable research/manuscript draft recovery remains U4. |

## Repeatable correctness and useful-output benchmark

Use synthetic accounts A and B in an isolated test environment, permitted fixed
paper fixtures and real normal-path retrieval, persistence and model execution.
Mocks may inject a fault but cannot replace the normal journey's business path.
Record whether the environment reconstructs the service or is its established
authority; a local email sink proves only that test integration.

1. Pin P1 to `1706.03762v7` and search `self attention sequence transduction
   without recurrence`. Verify usable exact-version content. The explanation
   must connect scaling by the square root of key dimension to large dot
   products and very small softmax gradients, and describe positional signals
   added to embeddings and the paper's sinusoidal choice. Check §3.2.1 equation
   (1) and §3.5 using the approved source rubric.
2. Pin P2 to `2005.11401v4` and search `retrieval augmented generation parametric
   non parametric memory`. The explanation must distinguish BART's learned
   parameters from the retrieved Wikipedia index and RAG-Sequence from RAG-Token.
   Do not accept the claim that Sequence retrieves only one candidate. Check
   Figure 1 and §2.1–§2.3. Identifier/title lookup is diagnostic, not a substitute
   for either research query.
3. Exercise a returned, supported translation language pair on eligible source
   text. Record chosen pair, exact source/output spans, terminology, material
   omissions or distortions and the competent reviewer's judgment. Both papers'
   understanding checks and the additional translation check are required; one
   generic fluent result does not close them. All remaining action/language/level
   variants stay in downstream capability parity.
4. Save the paper and submitted query, inspect acknowledged owner records, lose
   and reconcile a save response, then close/reopen and authenticate afresh as A.
   Rediscover work through owner lists, including the planned retained-assistance
   history path; choose the intended prior result explicitly. Verify source and
   option binding, and truthful expiry without silent generation. B must be
   denied through both views and direct boundaries.
5. Run separate negative/recovery scenarios for unavailable/insufficient source,
   dependency failure, duplicate requests, expired login, stream interruption,
   worker/service restart and concurrent edits. A truthful unavailable response
   may pass that negative case; it cannot count as a successful normal paper task.

For each run record attempted steps, outcome and reason, fixture/content identity,
source eligibility evidence, operation/job/result/record identifiers, exact
runtime/model/configuration revisions, timestamps, observed committed state and
review findings. Keep synthetic text/output evidence in its approved access and
retention scope. Report task success as successful complete normal runs divided
by attempted normal runs; retain blocked preparation separately with its cause.
Never omit a started run because it timed out or produced poor output. Record
wrong version, unsupported claim, false save, lost work and cross-owner exposure
as failures; required unresolved failures prevent a readiness claim.

## Timing boundaries, throughput and latency budgets

| Measure | Start → stop and reporting unit | Important distinction |
| --- | --- | --- |
| Input/action feedback | Explicit user input/action → corresponding visible and accessible pending/validation state; milliseconds | Feedback is not acceptance or success; capture main-thread stalls separately. |
| Usable search | Explicit submission → current matching result/empty/degraded/error state with query controls usable; milliseconds | Report outcome class and actual mode. Wrong/stale results are failures, not faster samples. |
| Usable content | Open exact paper/version → intended authorized text/anchors usable, or explicit availability failure; milliseconds | Separate missing optional asset timing and selected source-only state from complete readable content. |
| Save acknowledgement | Explicit save/remove → durable owner acknowledgement reflected in UI; milliseconds | Unknown replies are incomplete observations; report reconciliation time to verified original outcome separately. |
| Acceptance | Explicit work submission → durable original acceptance receipt; milliseconds | Include server admission and reservation cost; transport receipt without committed obligation is invalid. |
| Queue and execution | Immutable owner acceptance time → first valid claim; and each claim → owner-recorded attempt disposition; milliseconds | Replacement attempts retain original acceptance time; report all attempts and overlapping wasted computation. |
| Job and usable result | Original acceptance → authoritative terminal state; and explicit result read → authorized usable prepared result; milliseconds | Also report submission → useful rendered result. Terminal failure, expired result and completed but unusable output remain distinct. |
| Revisit | Authorized saved-work navigation → same intended paper/query/prior-result usable; milliseconds | Record authentication and human selection time separately, plus overall task time; never time a guessed in-memory job ID as fresh rediscovery. |
| Recovery | Fault/last known loss of service → verified recovery of the original operation and visible correct state; milliseconds and manual action count | Report detection, restoration, reconciliation and user recovery intervals separately where observed. |

Use monotonic elapsed time within one process/browser. Across boundaries record
authoritative timestamps and clock source/offset uncertainty; do not subtract
unrelated clocks into precise latency. Preserve wall-clock timestamps for
correlation. Immutable original acceptance time must be committed once and used
for history ordering and queue age, including duplicate/replacement recovery.
Measurement must not invent an unapproved wire field to obtain it.

For each workload report attempt count, successes, truthful rejections, failures,
timeouts, incomplete observations, min/median/p95/p99/max where sample size supports
interpretation, and raw distributions with sample size. Label small-sample
percentiles as descriptive, not statistically established service promises.
Report throughput as accepted and completed logical operations per elapsed
second and completed paper journeys per elapsed minute; report attempts,
rejections, retries and duplicate deliveries separately. Warm-ups are declared
before collection and retained as a separate set. Cold/warm cache, model loading,
parallel-user/job levels, fixture corpus size, network conditions and idle/busy
hardware state are explicit strata, never silently pooled.

After measurement, propose end-to-end budgets and component contributions for
the tested workload, with normal/recovery distributions and resource headroom.
The human agrees numeric quality targets; ServiceOperations records rationale,
environment, acceptance check and review trigger. If no viable budget fits $0
and useful complete-task behavior, present that conflict rather than lowering
quality or cutting capabilities silently. The separately approved cumulative
v2 verification command is still unset; this protocol does not select it.

## Accessibility and integrated-interaction matrix

| Dimension | Required coverage and evidence |
| --- | --- |
| Entry and account changes | Labeled authentication fields, linked errors, password-manager/paste support, keyboard entry/verification; same-owner return and B switch with late A responses; private DOM/accessibility content removed when authority expires. |
| Navigation and controls | Complete keyboard journey; meaningful headings/landmarks and skip link; visible unobscured focus; deliberate route focus, stable background-update focus, modal containment/close/return and scoped destructive confirmation. |
| Feedback | Loading/empty/error/degraded/conflict/unknown/accepted/running/terminal/expired states; material changes announced once with appropriate urgency, no announcement flood or unsupported percentage. |
| Layout and reading | Phone/tablet/desktop across approved breakpoints, 320 CSS-pixel reflow and text resize/zoom; long Korean/English titles, errors, identifiers, equations and figures. Only genuinely two-dimensional material uses labeled bounded scrolling. |
| Appearance and perception | Light/Dark/System including OS changes, reduced motion, text/control/state contrast and non-color indicators; verify rendered combinations and applicable target size/spacing. Carry the approved 44px design preference without treating it alone as AA conformance. |
| Context and recovery | Reader → evidence → result and reader → submitted search return; pagination changes truthful; saved/unknown/conflict states consistent across views/tabs; resizing and failed theme storage preserve a usable interface. |

Each check names browser, OS, viewport/zoom, appearance, assistive technology and
version, fixture, state transition and observed result. Combine automated coverage
with manual reading/focus/announcement checks; a screenshot cannot establish
keyboard or screen-reader behavior. Any failed criterion or task remains visible
with owner and correction evidence. The matrix assesses the approved target;
it is not a conformance assertion or independent user endorsement.

## Assumptions and open decisions

Source/model permissions, canonical browser/worker/history bindings, finite
operating policies, glossary snapshot revision, retained-result policy and
resource envelope remain prerequisites. Numeric service targets require measured
baseline and human agreement. Existing-user continuity remains outside the
synthetic benchmark until authority and recoverable backups are established.
Capacity and failure pressure follow [scalability requirements](scalability-requirements.md);
durability and safe instrumentation are specified in
[reliability](reliability-requirements.md) and
[observability](observability-requirements.md).
