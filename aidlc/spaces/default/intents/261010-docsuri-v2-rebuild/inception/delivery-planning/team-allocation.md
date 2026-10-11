# DocSuri v2 — Construction responsibility allocation

Date: 2026-10-11 (Asia/Seoul). Basis: the human-confirmed
[Delivery Planning answers and summary](delivery-planning-questions.md#consolidated-summary-confirmation).
A **Bolt** is one build pass over a piece of work, ending in something that runs.
The approved arrangement is eight Bolts, one unit per Bolt, executed serially
from this session with one human maintainer and coding agents.

## Staffing and decision authority

Team Formation was skipped. This allocation creates no additional human team,
independent unit approver, staffing commitment or calendar reservation.
`aidlc-developer-agent` is the default implementation executor for every Bolt.
The relevant design, quality and operations roles contribute only through the
approved workflow; their work does not grant approval authority.

| Responsibility | Accountable decision or outcome | Execution and evidence |
|---|---|---|
| Scope, priority and policy decisions | Human maintainer; sole approver | Agents investigate options, preserve the full retained scope and present concrete decisions at recorded review points |
| Serial construction coordination | This session, within the approved workflow | Carry each unit through its applicable designs, implementation and completion checkpoint before starting the next unit |
| Implementation and repair | `aidlc-developer-agent`, for the active Bolt | Identify affected component owners, files, consumers and checks; produce runnable behavior and repair evidence |
| Domain authority and persistence | The existing component named in the catalogue | The active executor implements that owner's rules; unit labels never create duplicate stores or business authorities |
| Verification | Active executor assembles evidence; human approves the exact checkpoint command | Exercise real mounted boundaries and cumulative behavior; preserve failures, unknowns and required closure work |
| External access and policy choices | Human maintainer supplies authorized access and decides product tradeoffs | Agents research primary evidence and run permitted checks; provider availability is not a promised service agreement |
| Operational or external effects | The relevant current owner/operator authority | Apply explicit action approval where required; this plan does not authorize deployment, migration, real exports or destructive operator actions |

The recorded execution policy remains **unit-major, serial, checkpoints enabled**.
There is no separate walking-skeleton ceremony. The first complete paper journey
is delivered inside B01; later Bolts finish every remaining retained capability.
Agent assistance within a stage does not change unit ordering or human gates.

## Bolt allocation

The order below follows the confirmed summary and approved prerequisites.
Detailed demonstrations and completion conditions are in the
[Bolt plan](bolt-plan.md); uncertainty and ordering rationale are in the
[sequencing rationale](risk-and-sequencing-rationale.md).

| Bolt / unit | Default executor | Principal component work | Runnable integration responsibility |
|---|---|---|---|
| B01 / U1 — integrated paper journey | `aidlc-developer-agent` | Initial AccountAccess, CorpusContent, Discovery, PaperAssistance, Library, Personalization, UsageEntitlements, WebWorkspace and ServiceOperations slices | Establish one real application host; permitted paper processing, persistence, current-owner checks, accepted-work execution and fresh authenticated revisit |
| B02 / U7 — controlled platform protocols | `aidlc-developer-agent` | PlatformControl | Independently runnable operator executable with actual required native semantics and bounded evidence/receipt interface; no application-login shortcut to operator authority |
| B03 / U2 — account and personal controls | `aidlc-developer-agent` | Complete AccountAccess, Library, Personalization and UsageEntitlements contributions | Mount complete retained controls in the shared application and verify current lifecycle participants, identities, consent and concurrency |
| B04 / U3 — full paper/corpus capabilities | `aidlc-developer-agent` | Complete CorpusContent, Discovery and PaperAssistance contributions | Mount the complete corpus, retrieval, citation and understanding paths; verify projection publication/withdrawal, saved references and recoverable work |
| B05 / U4 — research and novelty | `aidlc-developer-agent` | ResearchWorkspace | Integrate private evidence, distinct research/novelty lifecycles, acknowledged draft recovery and immutable artifact identity in the shared application |
| B06 / U5 — topics and digests | `aidlc-developer-agent` | TopicsDigests | Integrate subscriptions, current-consent delivery, unsubscribe and uncertain-send reconciliation with existing account and source owners |
| B07 / U6 — approved export | `aidlc-developer-agent` | ApprovedExport | Integrate retained Notion token connection, preview, exact revision/destination approval and reconciled effects with ResearchWorkspace |
| B08 / U8 — operations and integration | `aidlc-developer-agent` | Complete ServiceOperations and WebWorkspace composition; verify every owner | Assemble the same application release, consume bounded platform evidence and prove full parity, cumulative recovery and maintainer repairability |

U1 and U8 are successive assemblies of one application. U2–U6 supply embedded
code, their required UI contributions and real integration checks; they do not
become separately operated services. U7 remains independently controlled.
No permanent technology, physical source layout or hosting choice is made here.

## Component accountability through the increments

These are authoritative business owners from the
[component catalogue](../domain-design/components.md#component-catalogue),
not people or newly created teams. Each active executor maintains their identity
and modifies their existing implementation as the unit contribution expands.

| Component owner | Initial and completion responsibility | Required cross-owner discipline |
|---|---|---|
| AccountAccess | B01 safe initial identity; B03 complete identity, profile, consent and lifecycle coordination | Coordinate participant acknowledgements; never edit another owner's data or claim erasure without its disposition |
| CorpusContent | B01 eligible fixtures; B04 complete ingestion, canonical identity, versions and recovery | Own public content/eligibility and projection build, publication, atomic generation switch and withdrawal; Discovery consumes published generations |
| Personalization | B01 safe defaults; B03 complete settings, onboarding and permitted projections | Consume current consent and account lifecycle; no second profile authority |
| Discovery | B01 actual query path; B04 complete discovery and citation behavior | Own query semantics, read only published generations and recheck current withdrawal eligibility; preserve authorized reference identity without writing corpus projections |
| Library | B01 saves/revisit; B03 complete saved work/history controls | Preserve owner-bound references as corpus identity or eligibility changes; failed writes must not erase committed saves |
| UsageEntitlements | B01 bounded accounting; B03 complete controls and grants | Each operation owner reconciles its own accepted effects against stable accounting identities |
| PaperAssistance | B01 actual understanding and recoverable jobs; B04 complete retained modes | Own assistance claims/results and current access checks; reusable transport cannot bypass domain authority |
| ResearchWorkspace | B05 complete private research, drafts, novelty and evidence | Own private attachments, draft discovery and immutable artifact revisions; expose authorized source identity to ApprovedExport |
| TopicsDigests | B06 complete subscription and delivery lifecycle | Check current account consent before effects, including queued work; reconcile unknown remote sends |
| ApprovedExport | B07 complete connection, approval and remote-effect authority | Bind explicit approval to exact source revision and destination; analysis completion cannot authorize export |
| PlatformControl | B02 complete controlled operator protocol behavior | Preserve separate actor/target authority and native semantics; provide bounded evidence to B08 |
| ServiceOperations | B01 essential diagnosis; B08 complete operations and readiness | Observe and request authorized recovery through owning domains; telemetry does not transfer mutation authority |
| WebWorkspace | B01 common shell; B03–B07 coherent contributions; B08 complete experience | Preserve Korean UI, inherited colors, Apple HIG web adaptations, responsive layouts, appearance modes and accessible interaction |

Account-lifecycle manifests cover every owner that actually persists data.
B03 verifies the participants present then; each later owner joins and proves
its own disposition before persisting affected data. B08 checks the complete
manifest. Earlier units cannot promise cleanup for absent future features.

## Accepted findings and closure responsibility

The human accepted the three Major findings in the
[Contract Design review](../contract-design/reviews/review-01.md#findings).
Acceptance permits downstream work; it does not resolve the findings or waive
their required behavior. Update affected contracts and consumers through the
applicable change process before implementing the dependent boundary.

| Finding | Earliest accountable component work | Required closure evidence and follow-through |
|---|---|---|
| R-01 — browser revision preconditions | B01: WebWorkspace establishes browser/server revision conventions with each mutation owner. B03: AccountAccess, Library, Personalization and UsageEntitlements complete affected bindings. | Client-observed revision reaches the owning command while identity remains server-derived; create/null rules are explicit; two clients editing one revision cause one success and one visible stale conflict. B04–B07 apply the convention; B08 repeats cumulative checks. |
| R-02 — durable draft allocation and rediscovery | B05: ResearchWorkspace defines allocation, context/kind association and authenticated discovery before draft persistence; WebWorkspace exposes truthful recovery. | A browser restart with no in-memory identifiers discovers only the authenticated owner's retained, acknowledged, unconsumed draft. Cover pre-session/pre-job drafts, logout/account switch, conflict and policy deletion. B08 repeats isolation and recovery. |
| R-03 — execution claims, payload and fencing | B01: PaperAssistance owns initial worker claim/payload/revision/fence rules; executor integration honors them. B04: remaining accepted-work owners extend them. B05: ResearchWorkspace applies its own authority. | Replacement worker acquires a valid claim; late old-worker progress/failure/completion and duplicates cannot publish a second result or duplicate usage effects. Delivery facts cannot bypass owning-domain completion checks. B08 repeats interruption and cumulative recovery. |

CorpusContent's projection writer and ResearchWorkspace/ApprovedExport immutable
revision binding follow the approved contract clarification. Their runtime
correctness still needs the B04 and B05/B07 checks; a document assertion is not
implementation closure.

## Maintainer handoff and completion evidence

For each Bolt, the executor supplies a runnable demonstration, changed ownership
and contract notes, reproducible setup, relevant recovery/repair instructions,
test results with fixture/configuration identity and an explicit open-condition
list. Preserve the source ledger for all 20 capability groups, 70 functional
IDs and ten NFRs. Unit completion proves the assigned contribution; full release
readiness requires all retained capabilities and cross-unit evidence.

The **construction verification command is deliberately unset**. Once a real v2
check exists, present its exact invocation for the human's separate approval
before the first unit completion checkpoint runs verification. This deferral
does not approve a placeholder, suppress a checkpoint or substitute document
validation or legacy CI for a working cumulative application check.

One-maintainer capacity remains a constraint to measure. Before schedule or
release commitments, record actual implementation and operating burden,
availability, measured quality baselines and free/local resource fit. No dates,
additional staff, spending or automatic approval are inferred from this table.

Completed branches merge through PRs into `develop` under
[CONVENTIONS.md](../../../../../../../CONVENTIONS.md) and the interim CI policy.
Record exact-head/base comparisons for inherited CI failures, delete completed
branches and start the next work from `develop`. Dedicated CI/CD work remains in
its approved later stages; promotion to `main` is a separate release action.

## Sources

- [Confirmed planning choices](delivery-planning-questions.md#answer-analysis-and-proposed-sequence).
- [Unit catalogue and component responsibility](../units-generation/unit-of-work.md#component-responsibility-across-increments).
- [Requirements and acceptance boundaries](../requirements-analysis/requirements.md#constraints).
- [Contracts and ownership rules](../contract-design/contract-summary.md#contract-ownership-rules).
- [External dependency map](external-dependency-map.md) for evidence, access and provider responsibilities.
