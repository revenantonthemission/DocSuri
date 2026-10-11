# U1 business rules

Date: 2026-10-11. Unit: `u1-integrated-paper-journey`.

## Scope and source of truth

The YAML below is authoritative for decisions. The [entity model](entities.md) owns data shapes and [functional specification](functional-spec.md) owns workflow order and state transitions. These rules elaborate U1's contribution from the [confirmed proposal](functional-design-questions.md), [requirements](../../../inception/requirements-analysis/requirements.md), [unit boundary](../../../inception/units-generation/unit-of-work.md), [domain owners](../../../inception/domain-design/components.md) and [contracts](../../../inception/contract-design/contract-summary.md). FR/NFR references are stable approved IDs; there are no invented upstream acceptance IDs. Parent FR references are rollups, not additional feature counts.

Each rule states its trigger, IF/THEN decision and observable violation behavior. U1 uses the required slices for a real paper journey; these rules neither declare every retained variant implemented nor close a requirement solely because a design exists. All ten NFRs have explicit rule contributions. Finite policy values and evidence prerequisites are required before enabling affected behavior; none are guessed here.

## Authoritative rules

```yaml
unit: u1-integrated-paper-journey
rules:
  - id: BR1.1
    statement: "Public registration creates only an eligible ordinary identity; verified entry is explicit and recoverable."
    category: "policy"
    applies_to: ["Account","IdentityChallenge","AuthenticationSession"]
    trigger: "Registration, challenge issue/delivery, verification and login."
    logic: "IF submitted identity is valid and admission policy permits registration THEN establish the ordinary account and purpose-bound challenge; IF current unexpired unused proof matches THEN consume it once and permit verified login. IF delivery fails or its outcome is unknown THEN preserve a recoverable challenge/delivery disposition without claiming verification."
    violation: "Use safe invalid/duplicate/unverified/expired responses without exposing another account; no privileged role assignment, forged verification or automatic identity substitution."
    source: ["FR6.1","FR6.4","NFR3","NFR4","NFR8"]
  - id: BR1.2
    statement: "Every protected boundary enforces current authority and owner scope."
    category: "authorization"
    applies_to: ["Account","AuthenticationSession","SavedPaper","SavedSearch","SearchHistory","AssistanceJob","AssistanceResult"]
    trigger: "Private list, direct read, mutation, asset, progress connection, payload retrieval and effect publication."
    logic: "IF the trusted actor currently has the required authority and the resource belongs to that actor's permitted scope THEN proceed under that boundary's owner; ELSE deny even when the identifier, old response, session or accepted job once worked. IF no authenticated actor exists THEN permit only explicitly retained anonymous search and other declared public authentication entrypoints."
    violation: "Missing/foreign private identities use the same safe not-found disposition where required; do not leak data before checking authority."
    source: ["FR1.1","FR3.4","FR5.3","FR6.4","NFR4","NFR5"]
  - id: BR1.3
    statement: "Client input never establishes identity, privilege, time or policy authority."
    category: "validation"
    applies_to: ["Account","AuthenticationSession","IdentityChallenge","NavigationContext"]
    trigger: "Public form processing, command mapping and session validation."
    logic: "IF request fields are supported, bounded and well-formed THEN map only permitted data and derive account, role, trusted time, policy and session context on the server. IF credential/session or request-origin protections fail, unknown authority fields appear, or bounded abuse policy rejects admission THEN stop before protected effects."
    violation: "Return bounded validation/authentication or configured abuse response; never trust a supplied owner, tier, role, expiry or external return destination."
    source: ["FR6.1","FR6.4","FR17.1","NFR4","NFR8","NFR10"]
  - id: BR1.4
    statement: "Revocation fences future access and effects; cleanup completion requires each installed owner."
    category: "authorization"
    applies_to: ["Account","AuthenticationSession","ConsentRecord","AccountLifecycleRequest","AssistanceJob"]
    trigger: "Logout, account/consent revocation, withdrawal and supported lifecycle disposition."
    logic: "IF current authority is revoked THEN invalidate affected sessions and future reads/processing/effects at the owner-defined commit boundary; IF a supported lifecycle request is enabled by resolved policy THEN require dispositions from its complete installed participant manifest. IF cleanup or reactivation rules remain unresolved THEN do not enable or claim their completion."
    violation: "A stale session/claim cannot regain access; pending cleanup stays pending, and permanent erasure is never described as recoverable."
    source: ["FR6.3","FR6.4","FR3.2","FR19.2","NFR3","NFR4","NFR5"]
  - id: BR1.5
    statement: "Authenticated return restores only permitted context and cannot replay a mutation."
    category: "authorization"
    applies_to: ["NavigationContext","AuthenticationSession","SavedPaper","SavedSearch","AssistanceJob"]
    trigger: "Session expiry, logout, account switch and reauthentication."
    logic: "IF authentication changes THEN clear private rendering/subscriptions and reject old-account responses; IF the same owner authenticates again THEN reread authorized committed state and reconcile original pending identities before offering any new action. Restore only validated return locations and public-safe navigation context."
    violation: "Do not show another account's cached work, interpret a return link as execution approval, or claim unsent input was durably saved."
    source: ["FR3.4","FR5.1","FR5.3","FR6.4","NFR3","NFR4","NFR6"]
  - id: BR2.1
    statement: "Paper identity, source version and content representation remain explicit."
    category: "constraint"
    applies_to: ["Paper","PaperVersion","PublicContent","SavedPaper","AssistanceResult"]
    trigger: "Resolve search result, reader, saved reference or assistance input/output."
    logic: "IF a reference is resolved THEN preserve canonical paper, original source/version, content hash and proven alias mapping together; IF an alias changes THEN follow only verified equivalence and retain the saved version context. P1/P2 checks use their pinned fixture versions."
    violation: "Never silently substitute current version, unrelated paper, figure or source; report unresolved identity or unavailable version."
    source: ["FR1.1","FR2.1","FR3.1","FR3.4","FR5.3","NFR1","NFR10"]
  - id: BR2.2
    statement: "Current purpose-specific eligibility governs source display and processing."
    category: "authorization"
    applies_to: ["PaperVersion","PublicContent","ConsentRecord","AssistanceJob","AssistanceResult"]
    trigger: "Content/asset read, assistance admission, payload release, result publication and later result read."
    logic: "IF current account/consent and source policy permit the exact use THEN authorize the bound source representation; ELSE stop the affected use even if an old index, cached result or accepted request was eligible. Public accessibility alone does not prove storage, translation or model-processing permission."
    violation: "Return safe source-ineligible/restricted/policy-unresolved disposition and preserve only permitted metadata; do not make withdrawn content public through saved copies."
    source: ["FR2.2","FR3.1","FR3.4","FR5.3","NFR4","NFR5"]
  - id: BR2.3
    statement: "Content and asset failures have bounded truthful dispositions."
    category: "validation"
    applies_to: ["PublicContent","NavigationContext"]
    trigger: "Read or render structured paper content, section, figure or asset."
    logic: "IF requested content is available and its bounded structure/path/URL is valid THEN show only authorized sections/assets for that version; ELSE distinguish absent, building, unsupported, failed, withdrawn and restricted states with useful permitted metadata and navigation. A failed figure need not erase independent readable content."
    violation: "Reject path escape, unsafe active content and malformed structures; do not invent text or leave indefinite loading."
    source: ["FR2.1","FR2.2","NFR2","NFR4","NFR6"]
  - id: BR2.4
    statement: "CorpusContent exclusively publishes and withdraws search/content projections."
    category: "constraint"
    applies_to: ["Paper","PaperVersion","PublicContent","SearchExecution"]
    trigger: "Fixture publication, retrieval projection refresh and source withdrawal."
    logic: "IF a corpus projection is published/rebuilt/withdrawn THEN CorpusContent owns its generation and disposition; Discovery consumes the identified eligible projection without independently changing corpus truth. IF withdrawal or eligibility revision invalidates a stale representation THEN reads and processing honor the current decision before use."
    violation: "Do not serve a stale index/cache as authority or let another component write canonical/projection state; report degraded/unavailable projection explicitly."
    source: ["FR1.2","FR1.3","FR2.2","FR5.3","NFR5","NFR7","NFR10"]
  - id: BR3.1
    statement: "Submitted query intent is validated and separate from editable form state."
    category: "validation"
    applies_to: ["SearchExecution","NavigationContext"]
    trigger: "Explicit search/refinement/rerun submission."
    logic: "IF nonempty research query, filters, mode and ordering pass supported Unicode/normalization and finite size rules THEN freeze QueryContext and request identity for that execution. Reject whitespace-only, malformed or oversized values on the server. Saved-query rerun requires an explicit invocation and creates a new search execution."
    violation: "Preserve editable values and field errors; no hidden coercion of unsupported filters, accidental search from typing or loss of meaningful punctuation/Unicode intent."
    source: ["FR1.1","FR1.3","FR5.2","NFR2","NFR4","NFR10"]
  - id: BR3.2
    statement: "Retrieval mode and degradation match what actually ran."
    category: "policy"
    applies_to: ["SearchExecution"]
    trigger: "Lexical/semantic retrieval completion or dependency failure."
    logic: "IF requested retrieval mode is available THEN return that mode's observed result; IF an approved supported fallback is used THEN name the fallback and limitation; IF no usable path exists THEN return actionable unavailability. A successful no-match response requires completed retrieval, not timeout or missing index."
    violation: "Never label fallback as normal semantic success, fabricate matches, or turn a retrieval failure into an empty result."
    source: ["FR1.2","FR1.3","FR19.2","NFR1","NFR2","NFR9"]
  - id: BR3.3
    statement: "Pagination retains an identified snapshot and deterministic ordering."
    category: "constraint"
    applies_to: ["SearchExecution"]
    trigger: "Retrieve the next window or revisit an existing result window."
    logic: "IF cursor, query context, access scope and source snapshot match THEN continue stable ordering with deterministic tie-break identity; ELSE signal changed/expired snapshot and offer an explicit refresh. Revalidate current eligibility before exposing individual results without pretending withdrawn items remain available."
    violation: "Reject mismatched cursors and silent mixing of generations; explain a changed result set rather than inventing stable completeness."
    source: ["FR1.1","FR1.3","NFR1","NFR10"]
  - id: BR3.4
    statement: "Only the active submitted context may replace the current search display."
    category: "constraint"
    applies_to: ["SearchExecution","NavigationContext"]
    trigger: "Search response, retry response, pagination response or account switch."
    logic: "IF returned execution/request identity, submitted context and account partition match the currently displayed request THEN apply its outcome; ELSE ignore it for current display. Form edits can coexist with the old submitted results, but the distinction stays visible until explicit resubmission."
    violation: "Late older results cannot overwrite newer results or change the visible controls; failed retry retains the submitted query/filter context."
    source: ["FR1.1","FR1.3","NFR2","NFR3","NFR6"]
  - id: BR3.5
    statement: "Qualifying search history derives from a recoverable deduplicated completion fact."
    category: "constraint"
    applies_to: ["SearchExecution","SearchHistory"]
    trigger: "Authenticated search completion and history delivery/replay."
    logic: "IF current policy permits recording a completed authenticated search THEN Discovery durably records its original fact identity, query context and captured history eligibility boundary with delivery responsibility; Library consumes that fact once if still eligible. Anonymous searches do not acquire private history identity."
    violation: "History failure or delayed delivery cannot fabricate a completed search, block truthful search outcome, or bypass a later clear/withdrawal boundary."
    source: ["FR5.2","FR5.3","FR1.1","NFR3","NFR5","NFR10"]
  - id: BR4.1
    statement: "Confirmed saves/removals reflect durable owner commits and deduplicated intent."
    category: "constraint"
    applies_to: ["SavedPaper","SavedSearch"]
    trigger: "Add/list/remove saved paper or query."
    logic: "IF current owner and exact resource/query identity are valid and revision preconditions hold THEN commit one intended save/remove and its recoverable receipt before acknowledging. Repeating the same intended save resolves the same active entry; listing/rereading cannot mutate it."
    violation: "Failed or uncertain persistence retains last known committed state plus explicit pending/failed/unknown status; no false saved badge or unintended duplicate."
    source: ["FR5.1","FR5.3","NFR1","NFR3"]
  - id: BR4.2
    statement: "Browser mutations convey the owner's exact revision precondition."
    category: "constraint"
    applies_to: ["SavedPaper","SavedSearch","SearchHistory","PersonalSettings"]
    trigger: "Revision-sensitive browser write and trusted mapping to domain command."
    logic: "IF an operation requires expectedRevision THEN the browser supplies the exact last acknowledged token; only an explicitly declared create-if-absent operation accepts explicit null. Validate presence/type before execution; compare atomically with current owner state. An exact previously committed idempotent replay may return its original receipt after current authorization without becoming a new write."
    violation: "Missing/malformed precondition is invalid; stale/existence mismatch conflicts with no overwrite. Recover through fresh authorized read and visible user reconciliation. Do not invent latestRevision in the current Error.details schema or silently fetch/substitute latest for the command."
    source: ["FR5.1","FR5.2","FR5.3","FR10.1","NFR3","NFR10"]
  - id: BR4.3
    statement: "Unknown write outcomes reconcile the original intention before any new attempt."
    category: "constraint"
    applies_to: ["SavedPaper","SavedSearch","SearchHistory","PersonalSettings","AssistanceJob"]
    trigger: "Lost acknowledgement, timeout, duplicate request or uncertain commit."
    logic: "IF the same owner/kind/logical key and normalized input are retried THEN resolve or replay the original receipt under current authorization; IF that key is reused with changed input THEN conflict. IF an outcome remains unknown THEN keep it unknown and use the owner read/reconciliation path, not an unrelated new key or guessed rollback."
    violation: "Never claim failure proves no commit; do not allocate duplicate work, undo a real save or resurrect deleted data from stale replay."
    source: ["FR3.2","FR5.1","FR5.3","NFR3","NFR10"]
  - id: BR4.4
    statement: "History clear fences delayed facts and preserves independent saved work."
    category: "constraint"
    applies_to: ["SearchHistory","SavedPaper","SavedSearch"]
    trigger: "Clear, history delivery, list or rerun."
    logic: "IF an authorized clear commits THEN atomically advance Library's owner clear boundary and hide affected history. IF a delayed fact belongs before that boundary THEN reject it even if delivered later. Stable history ordering/listing and explicit rerun retain the recorded query/refinements."
    violation: "A failed clear reports actual remaining state; another owner's history and all saved papers/queries remain intact."
    source: ["FR5.2","FR5.3","NFR3","NFR4","NFR5"]
  - id: BR4.5
    statement: "Changed source availability does not erase or misdirect an owner's saved reference."
    category: "policy"
    applies_to: ["SavedPaper","Paper","PaperVersion"]
    trigger: "Revisit after canonicalization, withdrawal, restriction or missing source."
    logic: "IF source identity has a verified equivalent THEN resolve that identity while retaining saved version; IF content is no longer available/permitted THEN show explicit reference disposition with permitted identity information. Access to source content remains independently checked."
    violation: "No silent redirect to unrelated/current content and no disappearance of the saved entry merely because source retrieval failed."
    source: ["FR5.3","FR2.2","NFR1","NFR5"]
  - id: BR4.6
    statement: "Explicit defaults persist and cold start remains usable."
    category: "policy"
    applies_to: ["PersonalSettings","BehaviorRecord","NavigationContext"]
    trigger: "Default read/update, new search/assistance action and recent-paper read."
    logic: "IF acknowledged supported settings exist THEN apply them only to unset values of the next explicit action; IF optional enrichment or settings are absent THEN provide a supported default/manual path with truthful degradation where relevant. IF permitted recent activity exists THEN order by its defined fact identity/time and resolve exact eligible versions."
    violation: "Failed setting writes do not replace committed defaults; stale or prohibited activity cannot recreate erased data; full U2 personal-control parity is not claimed by U1."
    source: ["FR10.1","FR1.1","FR3.1","NFR2","NFR5"]
  - id: BR5.1
    statement: "Understanding uses supported choices, exact sources and actual useful output."
    category: "validation"
    applies_to: ["AssistanceJob","AssistanceResult","PaperVersion"]
    trigger: "Read supported options, accept summary/translation and validate generated output."
    logic: "IF action, language, presentation level and vocabulary revision are supported for eligible bound input THEN execute the actual free/local capability and validate source association, structure and usefulness before publication. U1 includes useful P1/P2 understanding plus a supported translation check; absent content/model, insufficient source or malformed output yields explicit limitation/failure."
    violation: "No fabricated successful answer or empty option list as proof of parity. Retained variants remain assigned to later units with executable checks."
    source: ["FR3.1","FR3.4","NFR1","NFR5","NFR10"]
  - id: BR5.2
    statement: "Accepted work has durable execution responsibility and admission reconciliation."
    category: "constraint"
    applies_to: ["AssistanceJob","UsageRecord"]
    trigger: "Submission acknowledgement, crash between reserve/accept/dispatch and recovery."
    logic: "IF admission succeeds THEN bind stable operation identity, immutable payload, original reservation and durable dispatch/recovery obligation before returning accepted. Any reservation created before acceptance is reconciled into that same job or a definitive rejection with policy-allowed release; uncertain acceptance is never guessed absent. Recover accepted/running work through its existing identity until terminal outcome."
    violation: "Do not acknowledge a no-op dispatcher, lose work after a transport outage, or release a reservation solely on timeout; expose actionable failure when bounded recovery is exhausted."
    source: ["FR3.2","FR17.2","FR19.3","NFR3","NFR8","NFR10"]
  - id: BR5.3
    statement: "Idempotency binds original operation identity and immutable intended input."
    category: "constraint"
    applies_to: ["AssistanceJob","AssistanceResult","UsageRecord"]
    trigger: "Duplicate submission/delivery, receipt recovery or intentional rerun."
    logic: "IF owner/kind/key and normalized immutable input match an existing operation THEN return its authorized original acceptance/outcome; IF input differs THEN reject key reuse. Once terminal, retrying the same key returns that terminal outcome. Explicit new work after a failed/expired result uses a new logical identity and fresh admission only when policy permits."
    violation: "No duplicate job/result/debit, no terminal regression and no implicit rerun on result read or reconnect."
    source: ["FR3.2","FR3.4","FR17.2","NFR3","NFR10"]
  - id: BR5.4
    statement: "Finite approved resource policy governs reservation, exhaustion and reset."
    category: "policy"
    applies_to: ["Entitlement","UsageRecord","AssistanceJob"]
    trigger: "Protected work admission, concurrent submissions and accounting-period transition."
    logic: "IF current entitlement, source/model use and finite resource/accounting policies are known and capacity is available THEN reserve once for the intended operation in the defined period. Check concurrent reservations under UsageEntitlements authority. Reset/time-zone and failure/refund rules must be resolved before enablement and preserve original operation-period binding."
    violation: "Unknown is neither zero usage nor unlimited capacity; exhausted/unresolved capacity returns an explicit bounded outcome, with no billable fallback or client-selected privilege."
    source: ["FR17.1","FR17.2","FR3.2","NFR8","NFR9"]
  - id: BR5.5
    statement: "Only the current owner-issued fenced execution claim can advance a job."
    category: "authorization"
    applies_to: ["AssistanceJob"]
    trigger: "Acquire, renew, expire, reclaim, submit progress or complete."
    logic: "IF a trusted permitted worker claims eligible accepted/running work THEN PaperAssistance atomically grants a lease bound to original operation/input, worker, attempt, monotonic fence and owner-time expiry. Renewal compares a distinct leaseRevision and cannot restore an expired/replaced claim. Reclaim after expiry issues a larger fence; all later mutating facts must present the current active claim and authoritative business revision."
    violation: "Reject stale/replaced/expired or wrong-worker claims; worker timestamps/fences have no authority. Lease heartbeats cannot conflict with or independently advance business progress revision."
    source: ["FR3.2","FR3.3","FR17.2","NFR3","NFR4","NFR10"]
  - id: BR5.6
    statement: "Payload retrieval requires both current execution authority and immutable binding."
    category: "authorization"
    applies_to: ["AssistanceJob","PaperVersion","PublicContent"]
    trigger: "Worker reads payload or source before processing."
    logic: "IF authenticated worker, current lease/fence/operation/input and current account/source permissions all match THEN release only the immutable accepted payload and eligible source representation. Recheck applicable authority at processing and publication; a revoked account or source revision cannot be bypassed by a retained reference."
    violation: "Payload reference, operation ID and owner ID alone grant no access; wrong input/source/options or stale claim fails safely without exposing private context."
    source: ["FR3.1","FR3.2","FR3.4","NFR4","NFR5","NFR10"]
  - id: BR5.7
    statement: "Progress is an owner-ordered view of one authoritative job."
    category: "constraint"
    applies_to: ["AssistanceJob","NavigationContext"]
    trigger: "Worker progress/failure facts, event delivery, reconnect and snapshot read."
    logic: "IF a valid current claim submits a new fact against the current business revision THEN the owner records the resulting state and allocates monotonic revision/sequence. Client applies only matching operation/account and newer valid snapshots; a replay gap obtains a current snapshot before following events. Terminal states never regress and a repeated fact returns its original receipt without authorizing a new stale mutation."
    violation: "Drop duplicate/out-of-order client events; reject invalid worker facts. Socket close, sleep, timeout or last progress message never implies completion; use current snapshot/poll recovery."
    source: ["FR3.3","FR3.2","NFR2","NFR3","NFR10"]
  - id: BR5.8
    statement: "Completion publishes one valid result and a recoverable single accounting obligation."
    category: "constraint"
    applies_to: ["AssistanceJob","AssistanceResult","UsageRecord"]
    trigger: "Worker completion/failure, duplicate fact and interrupted settlement."
    logic: "IF current claim/fence, current account/source permission, immutable input/output binding and output validation all pass THEN the PaperAssistance owner commits one result/terminal outcome with durable settlement intent. UsageEntitlements consumes the original reservation idempotently using accepted-operation identity and resolved policy; crashes leave pending reconciliation. C14 work facts and direct C06 completion use the same owner validation/commit path."
    violation: "Reject late replaced-worker publication and mismatched output. No cross-owner atomic transaction is presumed; no second debit or release on unknown outcome. Success cannot be published without durable usable result; an acknowledged failure follows only the authoritative failure/accounting policy."
    source: ["FR3.2","FR3.4","FR17.2","NFR3","NFR4","NFR10"]
  - id: BR5.9
    statement: "Prepared-result reads distinguish job state, availability and authority without starting work."
    category: "policy"
    applies_to: ["AssistanceJob","AssistanceResult","NavigationContext"]
    trigger: "Open, refresh or revisit a prepared result."
    logic: "IF the original job succeeded and its exact owner/operation/paper/version-bound result is retained and currently permitted THEN return that content. Otherwise report pending, failed, expired, withdrawn/restricted or unauthorized disposition truthfully. An expired retained-result reference does not undo the job's historical terminal success."
    violation: "Read/retry-read must not regenerate, reserve or debit; a new result requires an explicit new-work action and new admission."
    source: ["FR3.4","FR3.2","FR5.3","NFR2","NFR3","NFR5"]
  - id: BR5.10
    statement: "Transport interruption and closing a view do not cancel accepted assistance."
    category: "policy"
    applies_to: ["AssistanceJob","NavigationContext"]
    trigger: "Disconnect, navigation, cancellation vocabulary or lifecycle revocation."
    logic: "IF the view closes or transport stops THEN accepted/running assistance retains its durable obligation and reconnect reads the same job. U1 AssistanceJob follows accepted to running to succeeded/failed, with accepted-to-failed allowed; no generic shared cancellation vocabulary creates a paper-job action. Only an owning operation with an existing supported cancellation contract may acknowledge cancellation, and current lifecycle revocation still fences forbidden effects."
    violation: "Do not display canceled because a request/view was abandoned, add a paper-job cancel button, or let a cancellation request alone claim effects stopped."
    source: ["FR3.2","FR3.3","FR3.4","FR6.3","NFR3","NFR10"]
  - id: BR6.1
    statement: "Search controls and committed context survive every recoverable view state."
    category: "policy"
    applies_to: ["NavigationContext","SearchExecution","SavedPaper","SavedSearch"]
    trigger: "Render loading, no-match, partial, failed, pending-save and conflict states."
    logic: "IF an action is in progress, degraded or failed THEN retain query/filter controls and useful last acknowledged context, expose precise status and an appropriate safe recovery action. Distinguish saving, saved, failed and unknown; a partial result states what is missing."
    violation: "No empty page that hides recovery controls, false saved state, infinite loading or overwritten query from stale response."
    source: ["FR1.3","FR3.3","FR5.1","NFR2","NFR3","NFR6"]
  - id: BR6.2
    statement: "Visible actions describe their effect and require explicit intent for new work."
    category: "policy"
    applies_to: ["NavigationContext","AssistanceJob","AssistanceResult","SavedSearch"]
    trigger: "Action labeling, retry, sign-in return and navigation."
    logic: "IF an action reads or recovers an existing result THEN label and execute a read/reconciliation; IF it starts new assistance, reruns search or mutates saved work THEN require that explicit intent and guard repeat submission with the same pending operation identity. Show conflicts before the user elects a fresh write."
    violation: "No hidden mutation from render/reopen/login, repeated accidental submissions, or new execution disguised as retrying a read."
    source: ["FR3.2","FR3.4","FR5.1","FR5.2","NFR2","NFR6"]
  - id: BR6.3
    statement: "The integrated Korean workspace retains appearance, access and responsive behavior."
    category: "policy"
    applies_to: ["NavigationContext"]
    trigger: "Render all U1 routes/forms/long content/status and appearance change."
    logic: "IF a retained U1 interaction is available THEN provide understandable Korean labels, keyboard/focus operation, announced statuses/errors, readable measured contrast, accessible authentication and reflow/zoom support under the approved WCAG 2.2 AA design target. Use inherited blue/neutral colors with accessible variants, HIG-informed hierarchy/grouping, and light/dark/system behavior; system follows environment change."
    violation: "Do not hide required controls on small screens, trap focus, rely only on color or imply conformance from a mockup; storage failure cannot claim appearance persistence."
    source: ["FR1","FR2","FR3","FR5","FR6","NFR2","NFR6"]
  - id: BR6.4
    statement: "Rendered research content and client diagnostics remain untrusted and bounded."
    category: "validation"
    applies_to: ["PublicContent","AssistanceResult","NavigationContext","CapabilityObservation"]
    trigger: "Display metadata/text/model output/links or report a failure."
    logic: "IF content is displayed THEN render only allowed bounded structures and validated destinations, treating any embedded instructions as evidence rather than authority. IF a diagnostic is shown THEN use safe message/correlation identifiers rather than private text, credentials or internal capabilities."
    violation: "Unsafe markup, paths or redirects cannot execute or cross scope; malformed output receives a bounded error without leaking secrets or destroying navigation."
    source: ["FR2.1","FR2.2","FR3.1","FR19.1","NFR4","NFR6","NFR9"]
  - id: BR7.1
    statement: "Host composition and lifecycle participants reflect installed authoritative owners."
    category: "constraint"
    applies_to: ["AccountLifecycleRequest","CapabilityObservation"]
    trigger: "Module registration/startup and first owner persistence."
    logic: "IF a module joins the shared application THEN declare its provided/required contracts, capability checks and relevant lifecycle participant before persisting owner data; validate compatibility and required dependencies. The U1 host runs independently of absent future implementations and registers all present owners without duplicating stores or domain authority."
    violation: "Missing required module/participant or incompatible contract blocks its affected capability and lifecycle completion; absence never means full release parity."
    source: ["FR6.3","FR19.2","NFR7","NFR10"]
  - id: BR7.2
    statement: "Readiness reports actual capability evidence and limitations."
    category: "policy"
    applies_to: ["CapabilityObservation","ServiceIncident"]
    trigger: "Startup, dependency outage, check expiry and recovery."
    logic: "IF required capability checks with current evidence succeed THEN report their specific readiness; IF optional feature, store, execution or policy is absent/failing THEN report the relevant not-installed/unavailable/degraded/unknown state to affected users and maintainers. Mark stale observations explicitly."
    violation: "Process liveness cannot imply working paper journey or complete retained capabilities; recovery readiness waits for successful relevant checks."
    source: ["FR19.1","FR19.2","NFR1","NFR8","NFR9"]
  - id: BR7.3
    statement: "Diagnosis and repair preserve safe evidence and verify domain outcomes."
    category: "policy"
    applies_to: ["ServiceIncident","CapabilityObservation","AssistanceJob"]
    trigger: "Failure observation, authorized recovery and verification."
    logic: "IF a fault occurs THEN correlate safe request/job/dependency identity, time, outcome and evidence scope; IF an authorized recovery is attempted THEN invoke the owning domain's procedure and record its result plus fresh user/domain verification. Keep telemetry failure visible and distinguish measured, estimated, unknown and stale resource/cost values."
    violation: "No direct cross-owner state rewrite, private-content dump, zero-cost claim from absent measurement or verified-repair claim based only on restart."
    source: ["FR19.1","FR19.3","NFR7","NFR9"]
  - id: BR7.4
    statement: "Unresolved evidence blocks only affected choices within the zero-budget constraint."
    category: "policy"
    applies_to: ["CapabilityObservation","Entitlement","PublicContent","AccountLifecycleRequest"]
    trigger: "Enable processing/persistence/public integration or choose operating configuration."
    logic: "IF source/model permission, retention/location/consent obligations, finite free/local capacity, recovery authority and required policy for a capability are evidenced THEN enable that scope with its evidence reference; ELSE retain explicit prerequisite and typed unavailable/policy-unresolved behavior. Existing-user continuity waits for authoritative inventory and recoverable backups; no synthetic demonstration resets existing data."
    violation: "No paid fallback, invented numeric limit/target, silent scope reduction or local-sink claim of public delivery feasibility."
    source: ["FR3.1","FR6.1","FR6.3","FR17.2","FR19.2","NFR3","NFR5","NFR8"]
  - id: BR7.5
    statement: "Design coverage and schema agreement require later executable proof at real boundaries."
    category: "constraint"
    applies_to: ["CapabilityObservation","ServiceIncident"]
    trigger: "U1 implementation readiness and accepted contract finding closure."
    logic: "IF browser revision and worker claim/payload rules are taken into implementation THEN first coordinate affected canonical contracts, generated/browser/worker bindings and compatibility before code; require actual browser-service-worker-result and recovery checks to close findings. Record synthetic P1/P2 environment, fixture hashes, useful source-bound output, supported translation, owner denial, save/revisit and interrupted/restarted behavior."
    violation: "Document checks are not application parity; full R-01 later bindings, R-02 drafts in U4 and cumulative U8 remain explicit. Exact construction completion verification command stays unset until separately approved."
    source: ["FR1.1","FR2.1","FR3.1","FR3.2","FR3.3","FR3.4","FR5.1","FR19.3","NFR1","NFR7","NFR10"]
```

## Derived rules summary

| Rule | Required behavior | Upstream sources |
| --- | --- | --- |
| BR1.1 | Public registration creates only an eligible ordinary identity; verified entry is explicit and recoverable. | FR6.1, FR6.4, NFR3, NFR4, NFR8 |
| BR1.2 | Every protected boundary enforces current authority and owner scope. | FR1.1, FR3.4, FR5.3, FR6.4, NFR4, NFR5 |
| BR1.3 | Client input never establishes identity, privilege, time or policy authority. | FR6.1, FR6.4, FR17.1, NFR4, NFR8, NFR10 |
| BR1.4 | Revocation fences future access and effects; cleanup completion requires each installed owner. | FR6.3, FR6.4, FR3.2, FR19.2, NFR3, NFR4, NFR5 |
| BR1.5 | Authenticated return restores only permitted context and cannot replay a mutation. | FR3.4, FR5.1, FR5.3, FR6.4, NFR3, NFR4, NFR6 |
| BR2.1 | Paper identity, source version and content representation remain explicit. | FR1.1, FR2.1, FR3.1, FR3.4, FR5.3, NFR1, NFR10 |
| BR2.2 | Current purpose-specific eligibility governs source display and processing. | FR2.2, FR3.1, FR3.4, FR5.3, NFR4, NFR5 |
| BR2.3 | Content and asset failures have bounded truthful dispositions. | FR2.1, FR2.2, NFR2, NFR4, NFR6 |
| BR2.4 | CorpusContent exclusively publishes and withdraws search/content projections. | FR1.2, FR1.3, FR2.2, FR5.3, NFR5, NFR7, NFR10 |
| BR3.1 | Submitted query intent is validated and separate from editable form state. | FR1.1, FR1.3, FR5.2, NFR2, NFR4, NFR10 |
| BR3.2 | Retrieval mode and degradation match what actually ran. | FR1.2, FR1.3, FR19.2, NFR1, NFR2, NFR9 |
| BR3.3 | Pagination retains an identified snapshot and deterministic ordering. | FR1.1, FR1.3, NFR1, NFR10 |
| BR3.4 | Only the active submitted context may replace the current search display. | FR1.1, FR1.3, NFR2, NFR3, NFR6 |
| BR3.5 | Qualifying search history derives from a recoverable deduplicated completion fact. | FR5.2, FR5.3, FR1.1, NFR3, NFR5, NFR10 |
| BR4.1 | Confirmed saves/removals reflect durable owner commits and deduplicated intent. | FR5.1, FR5.3, NFR1, NFR3 |
| BR4.2 | Browser mutations convey the owner's exact revision precondition. | FR5.1, FR5.2, FR5.3, FR10.1, NFR3, NFR10 |
| BR4.3 | Unknown write outcomes reconcile the original intention before any new attempt. | FR3.2, FR5.1, FR5.3, NFR3, NFR10 |
| BR4.4 | History clear fences delayed facts and preserves independent saved work. | FR5.2, FR5.3, NFR3, NFR4, NFR5 |
| BR4.5 | Changed source availability does not erase or misdirect an owner's saved reference. | FR5.3, FR2.2, NFR1, NFR5 |
| BR4.6 | Explicit defaults persist and cold start remains usable. | FR10.1, FR1.1, FR3.1, NFR2, NFR5 |
| BR5.1 | Understanding uses supported choices, exact sources and actual useful output. | FR3.1, FR3.4, NFR1, NFR5, NFR10 |
| BR5.2 | Accepted work has durable execution responsibility and admission reconciliation. | FR3.2, FR17.2, FR19.3, NFR3, NFR8, NFR10 |
| BR5.3 | Idempotency binds original operation identity and immutable intended input. | FR3.2, FR3.4, FR17.2, NFR3, NFR10 |
| BR5.4 | Finite approved resource policy governs reservation, exhaustion and reset. | FR17.1, FR17.2, FR3.2, NFR8, NFR9 |
| BR5.5 | Only the current owner-issued fenced execution claim can advance a job. | FR3.2, FR3.3, FR17.2, NFR3, NFR4, NFR10 |
| BR5.6 | Payload retrieval requires both current execution authority and immutable binding. | FR3.1, FR3.2, FR3.4, NFR4, NFR5, NFR10 |
| BR5.7 | Progress is an owner-ordered view of one authoritative job. | FR3.3, FR3.2, NFR2, NFR3, NFR10 |
| BR5.8 | Completion publishes one valid result and a recoverable single accounting obligation. | FR3.2, FR3.4, FR17.2, NFR3, NFR4, NFR10 |
| BR5.9 | Prepared-result reads distinguish job state, availability and authority without starting work. | FR3.4, FR3.2, FR5.3, NFR2, NFR3, NFR5 |
| BR5.10 | Transport interruption and closing a view do not cancel accepted assistance. | FR3.2, FR3.3, FR3.4, FR6.3, NFR3, NFR10 |
| BR6.1 | Search controls and committed context survive every recoverable view state. | FR1.3, FR3.3, FR5.1, NFR2, NFR3, NFR6 |
| BR6.2 | Visible actions describe their effect and require explicit intent for new work. | FR3.2, FR3.4, FR5.1, FR5.2, NFR2, NFR6 |
| BR6.3 | The integrated Korean workspace retains appearance, access and responsive behavior. | FR1, FR2, FR3, FR5, FR6, NFR2, NFR6 |
| BR6.4 | Rendered research content and client diagnostics remain untrusted and bounded. | FR2.1, FR2.2, FR3.1, FR19.1, NFR4, NFR6, NFR9 |
| BR7.1 | Host composition and lifecycle participants reflect installed authoritative owners. | FR6.3, FR19.2, NFR7, NFR10 |
| BR7.2 | Readiness reports actual capability evidence and limitations. | FR19.1, FR19.2, NFR1, NFR8, NFR9 |
| BR7.3 | Diagnosis and repair preserve safe evidence and verify domain outcomes. | FR19.1, FR19.3, NFR7, NFR9 |
| BR7.4 | Unresolved evidence blocks only affected choices within the zero-budget constraint. | FR3.1, FR6.1, FR6.3, FR17.2, FR19.2, NFR3, NFR5, NFR8 |
| BR7.5 | Design coverage and schema agreement require later executable proof at real boundaries. | FR1.1, FR2.1, FR3.1, FR3.2, FR3.3, FR3.4, FR5.1, FR19.3, NFR1, NFR7, NFR10 |

## Interpretation and implementation handoff

BR4.2 resolves the U1 decision for browser revision preconditions, including missing, stale, create and replay cases. The current common error schema allows field names, not an invented latest-revision field; conflict recovery performs a fresh authorized read. Canonical request bindings must carry the required precondition coherently before implementation. This is the design portion of accepted Contract R-01; complete affected later-unit bindings and executable evidence remain required.

BR5.5–BR5.8 resolve the U1 decision for claim acquisition/renewal/replacement, protected payload retrieval and fenced completion. PaperAssistance remains the job/result authority; UsageEntitlements remains the accounting authority. Durable owner obligations and idempotent settlement provide recovery without asserting one transaction across owners. A repeated terminal fact can recover its original receipt but never gives a replaced worker new authority. This is the design portion of accepted Contract R-03 and requires coordinated formal contracts plus executable crash/concurrency checks.

Research drafts and restart rediscovery (Contract R-02) remain U4, and no U1 research composer is added. Generic shared cancellation states do not add paper-job cancellation. Supported lifecycle revocation still applies at current access and effect boundaries. Numeric retention, session/claim durations, queue/concurrency limits, cost envelope and service-quality targets remain evidence-dependent; unresolved values prevent the affected operation from being enabled.

