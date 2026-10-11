# U1 performance and interaction design

Date: 2026-10-11. Unit: `u1-integrated-paper-journey`.
Status: logical design; implementation, useful-output evaluation and operating
conformance are unverified. The [confirmed proposal](nfr-design-questions.md)
authorizes these patterns; it does not select a stack or numerical service target.

## Scope, ownership and requirement mapping

The shared application keeps all 13 [domain owners](../../../inception/domain-design/components.md#component-summary)
and the eight-unit release scope. U1 proves the real paper journey with $0
free/local resources and one human maintainer. Research drafts remain U4.
[Performance requirements](../nfr-requirements/performance-requirements.md),
[functional workflows](../functional-design/functional-spec.md),
[rules](../functional-design/rules.md) and the
[frontend contract](../functional-design/frontend-components.md) govern outcomes.

| Requirement | Solution | Accountable owner / designed outcome |
|---|---|---|
| NFR1.1 | P01 | WebWorkspace coordinates complete mounted journey; owners supply durable, authorized outcomes. |
| NFR1.2 | P02 | PaperAssistance validates source-bound useful output and supported translation. |
| NFR2.1 | P03 | ServiceOperations measures complete latency, bounded acceleration and resource contention. |
| NFR2.2 | P04 | WebWorkspace separates explicit commands, truthful state and bounded original-operation recovery. |
| NFR6.1 | P05 | WebWorkspace preserves accessible interaction through asynchronous transitions. |
| NFR6.2 | P06 | WebWorkspace preserves Korean responsive context, appearance and readable research content. |

## Concrete solutions

### P01 — Commit-backed complete journey

Use an integrated browser journey over owner ports, with UI acknowledgements
derived from committed owner receipts. Library commits saved paper/query identity,
revision and replay receipt together; PaperAssistance commits accepted identity,
immutable input, original acceptance time and durable dispatch responsibility
before presenting acceptance. A transport acknowledgement or optimistic icon
cannot establish either outcome. Reliability design supplies the detailed
[commit and recovery mechanisms](reliability-design.md).

WebWorkspace holds edited query state separately from submitted context. A save
names the displayed submitted query or exact selected paper/version. Discovery
returns the actual retrieval mode, stable identified results and source
dispositions; dependency failure cannot become an empty successful search.
Library's history-write failure leaves a truthful history-not-saved state while
preserving usable search results and the deduplicated original history fact.

Fresh return authenticates the owner, reads Library pages, then uses the planned
PaperAssistance retained-history read for the exact paper/version. That owner
orders by immutable acceptance time descending with job ID as deterministic tie
break. Selecting an existing result performs current authorized reads only.
No cache, transient browser job ID or newest-version substitution satisfies revisit.
History/result reads create neither a job nor an accounting effect.

Verification: run both research queries, useful assistance, supported translation,
paper/query saves and fresh authenticated revisit through real browser, stores
and executor. Discard transient job IDs before revisit. Inspect committed
identities and effects; repeat lost acknowledgements, two-tab conflicts,
same-owner recovery and account-B direct/view denial. Normal journey success
requires every intended step; truthful negative-case refusal is scored separately.
The canonical browser/history amendments remain prerequisites, not implemented APIs.

### P02 — Source-bound usefulness and explicit coverage

PaperAssistance binds the accepted request to exact paper/version/content hash,
action, language pair, returned option/vocabulary revision and immutable glossary
snapshot. PaperAssistance owns the initial empty glossary and non-null revision;
Personalization supplies defaults for the next explicit action only. This corrects
the ownership error in the historical technology requirement; [C06](../../../inception/contract-design/contract-summary.md#c06--paper-assistance-glossary-and-prepared-result-boundary)
and the confirmed proposal are authoritative. Later edits cannot rewrite a result.
[LOG04](logical-components.md) defines a side-effect-free virtual initial empty glossary revision scoped
to owner and normalization policy. Acceptance persists that exact empty snapshot;
the first U3 edit compares absent storage plus initial revision atomically. Reading
the glossary never creates a record or performs a mutation.

Before publishing, the owner validates result shape, bounded size, exact binding,
allowed coverage disposition and source-anchor references. Source text is untrusted
evidence. Insufficient material, malformed output and unavailable processing have
explicit dispositions; plausible fluent text cannot substitute for grounding.
Automated checks establish structure and binding, while a competent reviewer
assesses meaning, unsupported claims, material omissions and translation fidelity.
This review rubric is acceptance evidence, not a claim that a runtime validator
can prove semantic correctness for every future answer.

| Required experiment | Meaning and source checks |
|---|---|
| P1 `1706.03762v7` | Research query `self attention sequence transduction without recurrence`; explain square-root key-dimension scaling, large dot products and small softmax gradients at §3.2.1 equation (1), plus positional signals added to embeddings and sinusoidal choice at §3.5. |
| P2 `2005.11401v4` | Research query `retrieval augmented generation parametric non parametric memory`; distinguish BART parameters from retrieved Wikipedia memory and RAG-Sequence from RAG-Token against Figure 1 and §2.1–§2.3. Reject “Sequence retrieves only one candidate.” |
| Supported translation | Record returned supported language pair, exact eligible source/output spans, terminology, omissions, distortions and competent-review judgment in addition to both understanding checks. |

Record permitted fixture hashes, model/runtime/template identities, accepted
options, output, reviewer findings and failed/abstained attempts in the resolved
evidence-access/retention scope. Identifier lookup and a prefilled answer are
diagnostic substitutes only; they cannot pass the normal journey. Context-window
pressure uses a declared coverage limitation only if the approved operation
supports it; silently truncating the source or cutting a capability is prohibited.
Candidate comparison and processing prerequisites remain in
[technology decisions](../nfr-requirements/tech-stack-decisions.md).

### P03 — Bounded acceleration with measured latency budgets

Use cache-aside only for reconstructible derived data. Authoritative eligibility,
identity, accepted jobs, reservations, results, saved work and recovery receipts
remain in their owners' durable stores. A result is read from its authoritative
retained binding; a render cache cannot recreate an expired result.

| Derived object | Complete key and invalidation boundary | Miss/failure behavior |
|---|---|---|
| Safe paper rendering | Exact paper/version/content hash, representation/schema revision and language; owner/access partition when required | Revalidate current read eligibility, read authoritative eligible representation, derive within bounds; expose unavailable if authority is unknown. |
| Retrieval acceleration | Normalized submitted query, filters/order, actual mode, vocabulary, published projection/snapshot and relevant owner/preferences revision | Requery the same eligible snapshot within limits. CorpusContent alone publishes/rebuilds projections; Discovery never repairs by writing corpus data. |
| Prepared-result rendering | Verified owner, original result/job/source/options/glossary revisions and renderer revision | Recheck current job/result retention and account/source eligibility before deriving from the retained result; expiry stays expired. |
| Browser private view model | Current authenticated presentation epoch plus resource revision and submitted request identity | Clear on expiry/logout/account change; authorized refetch after restoration. No persistent private-browser cache is enabled before shared-device/storage policy is resolved. |

Every read checks current authority before consulting private data and checks
current source-purpose eligibility at delivery; a cached positive decision is
never permission. Authorization changes racing delivery use the security design's
ordered AccountAccess/CorpusContent guard and owner commit/delivery boundary;
long inference stays outside that short guard. Entries have finite bytes/count/age, bounded
single-flight rebuild and bounded waiters. Cache failure bypasses acceleration
only if authoritative reads have capacity; otherwise report a dependency/capacity
disposition. Eviction removes only permitted derived data. No new CDN is required;
public static bundle caching may use content hashes, while private responses use
the canonical no-store policy and cannot enter a shared CDN.

Discovery and owner list adapters require indexed/selective owner-and-resource
lookup, bounded projections, deterministic order and cursor seek semantics. The
cursor binds verified owner where private, canonical query/schema, snapshot,
order/tie-break and finite expiry; its authenticity is validated server-side.
No unbounded offset scan or full result materialization is an assumed fallback.
Recheck current eligibility per page; withdrawn rows are never served to preserve
page size. Invalid/expired snapshots require explicit restart. If an adapter
cannot retain bounded snapshot membership, it must invalidate the cursor rather
than mix generations. Benchmark real plans and growing data; index names and
physical storage remain unselected.

Separate finite foreground, execution and recovery resource budgets. Connection
and model pools have finite active/waiter counts and acquisition deadlines; one
slow model call cannot retain a foreground transaction or database connection.
Acquire only for the short owner read/commit, release before remote/model wait,
and reacquire for fenced effects. [SC02–SC04](scalability-design.md) define admission,
headroom and exhaustion. Pool/pagination/cache sizes must fit that same envelope.

Measure action feedback; usable search/content; durable save acknowledgement;
durable admission; original acceptance-to-first-claim; every attempt; terminal
outcome; useful rendered result; fresh revisit; and fault-to-verified recovery.
Include validation, authority, pool wait, reservation, storage, queue, model-load,
execution, transfer and rendering components where observable. Use local monotonic
elapsed clocks; correlate cross-process authoritative timestamps with measured
clock uncertainty. Original acceptance time is committed once, never replaced
by retry or claim time. Do not add unapproved wire fields for instrumentation.

Retain raw samples/outcomes and counts, with cold/warm, workload, corpus, model,
hardware and failed/incomplete strata. Report offered/admitted/completed/failed/
rejected work, logical operations and complete journeys separately from attempts.
Report distributions and sample size; percentiles from small samples remain
descriptive. After useful complete-task baselines, propose end-to-end budgets
and component contributions under the tested envelope for human agreement.
No numerical target or sustainable capacity is asserted by this design.

### P04 — Asynchronous execution and epoch-scoped recovery

Explicit summary/translation commands enter bounded durable admission and return
an owner receipt; model computation runs outside the foreground request. While
admission is unknown, retain the original authorized intent/key and distinguish
unknown from rejected. Known receipts recover by job snapshot/result reads. With
no receipt, the canonical same-key/same-input acceptance replay reconciles the
original operation under current authority; it is not a new job or debit.
Never substitute a guessed lookup endpoint or a fresh operation key on timeout.

Each browser request captures presentation epoch and submission/resource identity.
On response or event, both must still match before any UI/cache write. Expiry,
logout or switch first invalidates the epoch, hides private DOM/accessibility
content, closes subscriptions and clears private view state. Abort is an optional
resource optimization; identity checks still discard late callbacks. Browser Back,
page restoration and same-owner reauthentication require current authorized reads.

Use owner snapshots and monotonic event sequence, ignoring duplicates/older frames.
Gaps/reset trigger snapshot recovery. SSE reconnect and fallback polling share a
finite attempt/elapsed budget with bounded backoff; supported policy exhaustion
ends automatic activity in a visible stale/unknown state with explicit read retry.
A closed stream, sleep, local timer or closed panel never establishes job failure,
success or cancellation. Result expiry leaves terminal job history truthful and
offers new work only as a separate explicit eligible command.

Verify slow old search responses, request reversal, two tabs, account switch,
lost acceptance/save reply, stream gap, restart and exhausted recovery budget.
Inspect operation/reservation counts before and after each read-only recovery.
Keep query controls, committed context and safe retry actions usable throughout.

### P05 — Accessible asynchronous state transitions

Implement semantic landmarks/headings, skip navigation, native labeled account
fields with autocomplete/paste support, linked validation errors and accessible
controls. Deliberate route navigation focuses its heading; background results,
progress and layout changes retain focus. Modal views contain focus, name their
purpose, expose Close and restore the trigger/logical successor. Scoped destructive
confirmation initially focuses Cancel.

Announce material pending/unknown/conflict/terminal changes once, with bounded
polite status updates and actionable errors when needed; do not announce every
token/event. Use progress bars only for meaningful current/total data. Lazy-load
below-fold figures/sections without removing reading order, reachable anchors,
text alternatives or keyboard access; critical source/result text is not hidden
behind decorative loading. Virtualization requires equivalent accessible reading
and find/anchor behavior before adoption.

Verify the full keyboard and assistive-technology journey, labels, error linkage,
focus visibility, reduced motion, contrast in rendered states, reflow at 320 CSS
pixels, zoom/text resizing and long Korean/English content. Record browser/OS/tool
versions and criterion findings alongside automated rendered checks. WCAG 2.2 AA
is the approved target; automated checks or the inherited 44px preference alone
do not establish conformance. Safe rendering/privacy details remain in
[security design](security-design.md).

### P06 — Stable Korean context and responsive appearance

Use the approved blue/neutral semantic tokens, including light accent `#2f6df6`,
dark accent `#5b8bff` and accessible light-blue text `#2963df`, with their full
state/contrast pairs. HIG web adaptations supply hierarchy, grouped controls,
restrained depth and Korean-capable system typography while preserving browser
navigation, text selection and keyboard conventions.

Keep paper/version, selected option, submitted query and focus in a stable view
model independent of layout. Start from approved <768, 768–1199 and ≥1200 CSS-pixel
layouts, adjust for content reflow, and keep every U1 destination reachable.
Phone reading is single-column with labeled menu/disclosures; assistance moves
below as needed. Wrap long identifiers/titles; restrict bounded horizontal scroll
to genuinely two-dimensional math/figures/tables with meaningful labels.

Light/Dark/System is a presentation preference: System follows environment
changes, and failed storage keeps the current usable appearance while disclosing
that persistence failed. Persisting theme must not persist private paper state.
Navigation preserves only currently authorized context; resizing/back-forward
cannot submit or replay a mutation. Verify complete phone/tablet/desktop journeys,
appearance changes, storage failure and same-/different-owner returns against
acknowledged domain identities, not screenshots alone.

## Prerequisites, alternatives and closure evidence

| Decision / tradeoff | Owner and required evidence before affected enablement |
|---|---|
| Cache-aside adds invalidation complexity; no-cache authoritative reads are the comparison baseline | Data owners: permission-race, version/hash mismatch, eviction and cache outage tests plus measured benefit; finite cache/rebuild limits. |
| Stable cursors consume bounded snapshot state or adapter support | Discovery/Library/PaperAssistance: equal-time ties, growth, withdrawal and expired-generation checks; prove bounded query behavior on selected storage. |
| Async acceptance lowers foreground occupancy but adds durable recovery work | PaperAssistance/UsageEntitlements: canonical claim, browser, history, glossary and acceptance-time coordination; real crash/replay/effect checks. |
| Useful output may conflict with time or memory envelope | CorpusContent/PaperAssistance/quality: permitted exact fixtures, real model/output review and resource evidence; human resolves evidenced $0/quality/scope conflicts. |
| Privacy and authority restrict client/server cache persistence | AccountAccess and data owners: resolved source-purpose, shared-device, retention and lifecycle policies; unknown authority blocks the affected read. |
| Numeric budgets depend on the measured environment | ServiceOperations: bounded manifest, raw normal/recovery outcomes and human-agreed targets; exact completion command remains separately unapproved. |

All checks above are planned evidence. This document neither changes canonical
contracts nor closes their executable findings. Physical bindings stay open under
the [technology decision record](../nfr-requirements/tech-stack-decisions.md), and
interface changes follow the [coordination plan](../functional-design/contract-revision-plan.md).
