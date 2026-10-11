# U1 security, privacy and accessible authentication requirements

Date: 2026-10-11 (Asia/Seoul). Unit: `u1-integrated-paper-journey`.
Status: requirements and verification design; implementation and operating evidence
are pending. The human confirmed the [NFR proposal](nfr-requirements-questions.md).

## Scope and authority

These requirements derive from inception **NFR4**, **NFR5** and the authentication
contribution to **NFR6**. They apply to the real find → understand → save → revisit
journey, public registration and U1's installed owners. Full account/MFA controls
remain U2, complete corpus variants U3, durable research/manuscript drafts U4,
export U6, controlled platform protocols U7 and cumulative service coverage U8.
Every mounted U1 boundary must already enforce its applicable protection; a
later-unit assignment is not permission to mount an unprotected placeholder.

The [functional specification](../functional-design/functional-spec.md) owns
workflow/access semantics, [rules](../functional-design/rules.md) own business
decisions, and [frontend specification](../functional-design/frontend-components.md)
owns presentation. The [canonical contracts](../../../inception/contract-design/contract-summary.md)
and [coordination plan](../functional-design/contract-revision-plan.md) distinguish
existing bindings from required amendments. Internal claims, payload access and
the planned retained-assistance history require canonical coordination before
implementation; the prose here does not make them existing endpoints.

Required security outcomes do not wait for a latency baseline: a denied actor
must receive no protected material or effect, and an acknowledged outcome must
describe its actual state. Numeric abuse, token/lease, retention and resource
policies remain evidence-dependent. Missing required policy blocks the affected
operation before work or sensitive persistence; it never means unlimited access.
The $0 constraint does not weaken these outcomes or permit a paid fallback.

## Detailed requirements

Each row is a primary definition. Its referenced SEC checks below are local
verification cases, not invented upstream acceptance IDs. No check is reported
as passed by this document.

| ID | Requirement and accountable owner | Observable acceptance and evidence | Source and prerequisite |
|---|---|---|---|
| NFR4.1 | **Public identity and current sessions.** AccountAccess derives ordinary identity from validated registration/verification/login, never client owner, role, tier or expiry. Proofs are purpose-bound, finite, single intended use and cannot substitute for a session. Session issuance/rotation/revocation uses the trusted transport and protected origin-bound cookies. Registration/resend/recovery replies are existence-neutral; failed delivery never verifies an account. | SEC-01 exercises synthetic A/B, malformed/duplicate registration, wrong-purpose/wrong-account/used/expired proof, concurrent consumption, forged verification, stale session and lost acknowledgement. Inspect durable identity/session state and safe response/cookie metadata without copying secrets. Login as a different user cannot inherit an earlier session identity. Local email-sink success proves only that fixture path. | NFR4; FR6.1/FR6.4; WF1; BR1.1–BR1.5; LC01/LC09. Before enablement: credential/proof/session policies and permitted account-data handling; before public operation: demonstrated free public email/network path. |
| NFR4.2 | **Server-enforced owner and source boundaries.** Each domain owner checks current verified actor, resource owner, operation and purpose-specific source eligibility on all applicable lists, reads, mutations, events, assets, payloads and results. Stored IDs, cursors, accepted jobs, old authorization decisions and hidden UI controls confer no authority. Application administrators receive only their explicit operation scope. | SEC-02 instantiates the boundary matrix for every mounted operation, including the planned history read once added. A/B/anonymous/unverified/expired/revoked/administrator tests verify denied data and unchanged state. Absent and foreign private IDs have the same safe external not-found disposition; cursor swapping/tampering and source withdrawal cannot enumerate another owner's data. Positive own-account cases prevent a deny-everything false pass. | NFR4/NFR5; FR2.2/FR3.4/FR5.3/FR6.4; WF1–WF8; BR1.2/BR2.2/BR2.4; LC09. Requires the implemented access manifest and current account/source authority; LC07 history amendment before that path's code. |
| NFR4.3 | **Untrusted input, content and destinations.** WebWorkspace and each accepting owner validate bounded typed input and render corpus/model output as untrusted material. Unsafe markup, URLs, redirects, paths, asset handles and model instructions cannot execute active content, select private/internal resources, acquire tools or change authority. Provider fetches use the source adapter's permitted target policy rather than accepting arbitrary destinations. | SEC-03 covers malicious metadata/sections/model output, malformed nested structures, path escape, cross-source/version asset handles, unsafe link schemes, hostile return destinations and instructions asking for secrets or other accounts' content. Observe browser/network/effect outcomes as well as rejection. Preserve safe reading/navigation and Korean field errors; no private input or raw stack is reflected. | NFR4; FR1.3/FR2.1/FR2.2/FR3.1; WF2–WF6; BR1.3/BR2.3/BR6.4; LC02/LC03/LC11. Approved input, renderer, content-fetch and destination policies are required before handling; no particular sanitizing library is selected. |
| NFR4.4 | **Trusted worker claims and current effect authority.** PaperAssistance is the claim/job/result authority; UsageEntitlements owns accounting. Acquire/renew/reclaim/payload read and proposed progress/failure/success require authenticated executor identity, immutable operation/input binding and the current owner-issued lease/fence. Recheck current account/consent/source authority at protected payload access and the owner-defined effect commit boundary. | SEC-04 races replacement, lease expiry, revocation and source withdrawal against payload/progress/failure/success/settlement. Late old-worker facts cannot alter the replacement's job or publish/debit. Forged owner/payload reference/attempt cannot obtain input. Exact committed fact replay may recover an authorized old receipt but never authorize a new effect. Capture owner ordering, fences and result/accounting identities without private payloads. | NFR4/NFR3/NFR5; FR3.2–FR3.4/FR17.2; WF4–WF6; BR5.5–BR5.9; LC05/LC09/LC10. Contract R-03 amendment and finite owner-time lease/retry policy before implementation/enablement; executable closure remains outstanding. |
| NFR4.5 | **Secrets and separate privileged authorities.** AccountAccess, owning adapters and ServiceOperations protect credential/proof/key material in storage, transport and diagnostics. Ordinary sessions never grant administrator/MFA or platform-operator authority. Worker credentials are not browser credentials. Observation access does not authorize direct domain repair; recovery invokes the owning domain's authorized procedure. | SEC-05 seeds recognizable synthetic secrets, attempts ordinary-user elevation, browser calls to internal methods and administrator-to-platform escalation, and inspects responses, telemetry, build/client artifacts, safe configuration exports and restore access for leaks. Verify restricted secret access and rotation/revocation behavior in the chosen implementation. Stored passwords cannot be retained in recoverable plaintext. Document each actual privileged operation's required identity/MFA and negative test. | NFR4/NFR9; FR6.4/FR17.1/FR19.1/FR19.3; WF1/WF5/WF9; BR1.3/BR6.4/BR7.3; LC09/LC10/LC13. Secret storage, protected transport and recovery/key-access design before handling; absent U2/U7 operations remain unavailable rather than partially privileged. |
| NFR4.6 | **Bounded public admission and request integrity.** AccountAccess and the shared browser boundary enforce the canonical same-origin, Origin/CSRF and session-or-anonymous-bootstrap binding for browser POSTs, including entry flows and POST queries. Owning domains enforce finite abuse/admission limits before expensive work or growth, using trusted context rather than client-provided rate identity or entitlement. GET/read/recovery paths cannot start work or debit. | SEC-06 sends missing/foreign/old CSRF tokens, forged Origin/identity headers, cross-context replay, concurrent registration/search/job attempts and malformed/oversized bodies. Test configured boundaries, exhaustion and recovery without bypass, unbounded retries, duplicate effects or paid fallback. An error must expose only safe retry information. Count attempts/admissions/effects against the actual configured policy; do not invent target numbers. | NFR4/NFR8; FR6.1/FR17.1–FR17.2; WF1/WF2/WF4; BR1.3/BR3.1/BR5.4; LC01/LC02/LC10. Finite policy evidence under the capacity requirements before enablement; framework choice cannot silently relax request protections. |
| NFR5.1 | **Classified, purpose-permitted handling.** Each data owner records classification, provenance, owner/scope, purpose, permitted storage/display/translation/model processing, recipient/location, derived copies and applicable obligations before using data in that way. CorpusContent governs source eligibility and projection withdrawal. Unknown ownership or rights are quarantined from public serving and model use; public accessibility alone grants no general processing permission. | SEC-07 follows each actual fixture/data flow through the classification register below, including derived results, indices, caches and telemetry. Demonstrate allowed and denied uses, changed permission and unresolved policy. A missing permission record blocks only affected handling; a synthetic fixture has its own documented permission and isolation evidence. No real user data is reset or reused as a convenient fixture. | NFR5/NFR4; FR2.2/FR3.1/FR5.3; WF3–WF5; BR2.2/BR2.4/BR7.4; LC03/LC04/LC09. Functional prerequisite E2 before source/model use; E1 before existing-data transition. Applicable obligations and jurisdiction remain investigation items, not a compliance assertion. |
| NFR5.2 | **Retention, deletion and controlled restore.** AccountAccess coordinates applicable lifecycle participants; each installed owner records retention/access/erasure responsibilities for primary data, derived artifacts, caches, queued work, telemetry and backups before affected persistence. Immediate access revocation, logical removal and physical erasure are distinct states. Restoring old data must preserve current revocation/deletion boundaries and owner relationships. | SEC-08 inventories installed participants; exercises revoked access, history clear with late facts, withheld result material, policy-governed expiry/cleanup and isolated restore. Check identity, source binding, relationships, artifacts, restrictions and suppressed effects, not row count alone. Missing/failed participants keep lifecycle completion pending. Demonstrate that restore cannot make removed/restricted data visible or resume forbidden effects without the defined reconciliation. | NFR5/NFR3; FR5.2/FR5.3/FR6.3; WF1/WF7–WF9; BR1.4/BR4.4/BR7.1; LC08/LC09/LC12. E1 authoritative inventory/backup evidence and E4 retention/deletion/restore policy before affected operation; full account lifecycle remains U2 and cumulative continuity U8. |
| NFR5.3 | **Shared-device isolation and truthful recovery.** WebWorkspace clears prior-owner private rendering, response caches, subscriptions, pending form data and presentation identity on expiry/logout/account switch. Every late response is bound to the current owner/session epoch; Back/restored pages revalidate before private display. Owner-bound recovery for uncertain U1 operations requires an approved persistence policy before storage. | SEC-09 switches A→B with delayed responses/events, browser Back, restored page state, concurrent tabs and a fresh browser. Inspect DOM, accessibility tree and browser storage/network observations for A's private data. Fresh A return re-reads committed saves and retained results without replaying writes. Failed logout hides local private content but does not claim server revocation. Unsent input is not labeled saved; no durable research composer is introduced. | NFR5/NFR4/NFR3; FR3.4/FR5.3/FR6.4; WF1/WF6/WF7; BR1.5/BR5.9/BR6.2; LC07/LC09 and FUI-11. E4 shared-device/private-recovery storage and retention policy before persistence; canonical retained-result discovery before fresh-return implementation. U4 retains durable research-draft requirements. |
| NFR6.3 | **Accessible authentication and safe return.** WebWorkspace and AccountAccess preserve the approved Korean interface, inherited colors, Apple HIG web adaptations, Light/Dark/System and WCAG 2.2 AA target through registration, verification, login, expiry and recovery. Use meaningful labels, linked field errors, keyboard/focus behavior and native credential controls supporting paste/password managers. Security challenges cannot silently substitute an inaccessible path. | SEC-10 exercises success/error/expired/delivery-failed/rate-limited and reauthentication states with keyboard and assistive technology, responsive reflow/zoom and both appearances. Check focus destination, announced errors/status, preserved safe context and explicit actions; sign-in return cannot replay a save/job. Measure final contrast/target behavior in rendered UI. A mockup or automated scan alone is not conformance evidence. | NFR6/NFR2/NFR4; FR6.1/FR6.4; WF1; BR1.5/BR6.3; LC01/LC11 and FUI-01/FUI-11/FUI-12. Approved presentation target is carried forward; selected identity/provider integration must be included in the actual verification matrix. |

## Authorization model and verification matrix

Before execution, expand this matrix to the actual mounted C13/module operation
manifest, including all aliases and generic job dispatch routes. Record an
operation as absent when it is not mounted; this is not evidence of later-unit
parity. Each applicable cell requires a positive permitted case and a denial or
conditional case, with response shape and durable state/effect observations.
Do not reduce coverage to checking whether navigation links are hidden.

| Boundary family | Anonymous and unverified | Current verified A / B | Expired or revoked | Worker / administrator / operator |
|---|---|---|---|---|
| Entry, registration, proof, session and safe capabilities | Only declared public entry/search and purpose-bound proof flows; no account principal from malformed credentials | Current own session; explicit verified transition; B never resumes A | Public-safe state, fresh eligible authentication; no stale private bootstrap | Service status exposes no internal secret; worker/platform credential cannot impersonate browser entry |
| Discovery query and pages | Retain existing anonymous search, bounded and source-eligible; no private history principal | Own permitted query/history contribution; no caller-selected owner | No private cached response; only declared public search path | Administrative role does not broaden source eligibility; no projection writes from query interfaces |
| Exact paper/content/asset reads, including asset bytes | No broader guest reading/processing introduced | Current read purpose and exact paper/version/asset binding; test foreign/private source references | Deny private/restricted delivery before bytes or cached rendering | Worker payload capability is distinct from browser asset access; service admin has no implicit content bypass |
| Library paper/query lists, direct reads, create/remove; history/read/clear; defaults and usage | Deny protected boundaries | A sees/mutates A only; B IDs/cursors/operation receipts denied; own conflict/replay checks preserve current authorization | Deny new mutation and replay disclosure; stale pages cannot authorize | Admin entitlement operations require their explicit role/MFA contract; ordinary own-usage read is not an admin read |
| Assistance options, accept, status, events, prepared result and planned history | Deny protected journey | Current owner and source use for every path; choose exact retained binding; listing is read-only | Reject subscription/replay and enforce revocation during delivery; late private events suppressed | Generic job wrappers route to same owner checks; no browser-accessible claim/complete method |
| Internal acquire/renew/reclaim, payload, progress/failure/completion and settlement | Never exposed as generic browser calls | User identity, job ID or payload reference alone is insufficient | Current authorization and fence at the effect boundary; old receipt lookup has no new mutation authority | Only explicit trusted executor/component authority with immutable binding; ordinary admin/operator status alone is insufficient |
| Service observation and owner-provided recovery | Public capability view only where declared; no private operational evidence | Ordinary account sees only permitted own-safe outcome | No stale elevated session | Explicit observation versus recovery permissions; application admin, worker and U7 platform operator are separate principals/scopes |

A revoked request already in flight requires a recorded owner ordering. If
revocation/withdrawal wins the effect boundary, subsequent protected publication
or processing is refused; if publication committed earlier, current read policy
still controls its visibility. Both race orderings must be exercised. This does
not assert that material already legitimately delivered to an external browser
can be recalled or that process isolation alone erases it.

## Data protection and obligation register

The rows below define the minimum investigation coverage, not final legal
classifications or retention periods. The completed register must reference
actual data flow, source/version and policy evidence; record unresolved items
and the operation they block. The human remains the scope/priority decision
maker. Establish applicable obligations before choosing affected processing or
hosting; no jurisdiction or compliance certification is selected here.

| Data class / responsible component | Required handling boundary and evidence | U1 status and blocked decision |
|---|---|---|
| Corpus metadata, pinned P1/P2 source text and figures — CorpusContent | Record source/version/hash, acquisition provenance, permission for each actual storage/display/translation/model use, withdrawal behavior and allowed recipients/location. Index/embedding/cache copies inherit their source disposition. | Fixtures are proposed public-paper examples, not blanket licensed assets. E2 evidence precedes loading/processing; unknown rights or origin remain unserved. |
| Identity, session, verification and credential material — AccountAccess | Distinguish profile/account data from secrets; specify recipient, protected transport/storage, privileged access, proof/session lifetime, rotation/revocation and backup/key handling. No credentials in URLs chosen by the app, browser-readable token storage, analytics or logs. | Synthetic A/B still need bounded fixture handling. Real-user authority/continuity is unestablished. Public email fitness remains separate from local-sink proof. |
| Saved paper/query references, search history, preferences and behavior — Library / Personalization | Scope to verified owner and authorized purpose. Even a query about a public paper is private behavioral data when associated with an account. Define consent/recording, clear boundaries, permitted derived signals, retention and deletion dispositions independently. | U1 essential slices only. History clear does not claim deletion of independent saved work or all Personalization records. Unresolved sensitive persistence policy blocks that storage. |
| Accepted job, immutable payload, staged/prepared result, receipt and usage — PaperAssistance / UsageEntitlements | Preserve owner, exact source, intended use and result eligibility; record execution recipients, payload protections, staged-artifact quarantine, result/receipt retention and settlement evidence. Retained metadata and retained result content may have distinct approved lifetimes. | No payload/reference becomes a bearer credential. Metadata with unknown owner is quarantined from serving and processing; it is not reassigned to a public orphan bucket. |
| Private uploads, research questions/manuscripts and durable drafts — later CorpusContent / ResearchWork owners | Preserve private owner, consent/purpose and permitted processing; define retention/discard/deletion, acknowledged saves and shared-device restart isolation before persistence. | Retained product capabilities, not U1 input surfaces. U4 owns durable research draft allocation/rediscovery. Do not create a U1 composer to manufacture draft coverage. |
| Correlation, operational records and security evidence — ServiceOperations plus originating owner | Minimize fields, scope observation access and define retention, redaction and export/restore access. Use safe IDs rather than raw query/paper/private text. Synthetic secret markers verify that collectors and errors do not accidentally capture secrets. | Actual telemetry adapter/storage selection remains open. Required durable business receipts are distinct from optional telemetry; observation failure cannot erase recovery responsibility. |
| Backups, restore artifacts and keys — installed owners with authorized recovery coordination | Establish authoritative source, inventory, ownership relationships, encryption/access/key recovery where applicable, isolated restore and current deletion/revocation reconciliation. Record every restored secondary copy and queued effect. | Existing-user/data/backup authority is unresolved (E1). No reset/migration/restore into a live environment is authorized by this design. |

Only permitted metadata may remain visible after source withdrawal. A saved
reference's existence does not authorize re-serving deleted content, and a job's
historical success does not authorize reading an expired result. Cache, index,
derived result and backup dispositions must be named rather than omitted from
the lifecycle record. A new persisted owner joins the applicable lifecycle
manifest before its first writes; missing acknowledgements prohibit a claim of
completed cleanup.

## Threat considerations and concrete checks

SEC identifiers are local check names. Their complete evidence must include
application/contract versions, configured policy revision, synthetic actor and
resource identifiers, source eligibility, steps/concurrency ordering, expected
and observed response, durable outcome and a redacted evidence location. A
negative test that never reaches the boundary or lacks a corresponding valid
control is inconclusive. Tests operate on isolated synthetic data.

| Check / threat | Required exercise and evidence that changes the decision |
|---|---|
| SEC-01 identity confusion, proof/session replay and enumeration | Valid A/B registration/login controls alongside duplicate/wrong-purpose/used/expired proof and simultaneous proof use. Compare outward account-existence responses and inspect server-authoritative ordinary role. Verify old sessions after logout/revocation and loss of the response. Record configured expiry behavior without selecting a duration here. |
| SEC-02 cross-owner disclosure, cursor forgery and stale authorization | Complete the matrix for real mounted routes and module calls, including list and direct ID, generic and owner-specific job reads, live/replayed events, asset bytes and planned history. Assert no protected response/body or side effect, not just an HTTP code. Pair foreign and absent IDs; swap owner/paper/version/snapshot cursors. |
| SEC-03 active content, injection and destination abuse | Synthetic malicious text/markup/model instructions and paths must not execute, escape the designated content root, access another version/private resource or cause an unapproved network destination. Observe requests and effects while exercising legitimate paper text/math/figures, Korean input and safe links as controls. |
| SEC-04 forged/replaced executor and revocation race | Pause around payload read and effect commit; revoke account/source, expire/replace the claim and release the stale worker. Test stale progress, failure and success separately, plus forged worker clock/fence/input. A permitted positive control commits one intended result/accounting effect; the winning revocation blocks forbidden later effects, and all attempts together produce at most one valid result/debit. An old receipt can be retrieved only with current permission and cannot advance the job. |
| SEC-05 secret leakage and privilege confusion | Seed synthetic canaries in secret-bearing fields and examine allowed/denied responses, error paths, logs, traces, browser/client bundles, safe exports and backup permissions. Attempt admin operations with ordinary session, operator operations with application admin and worker methods with browser context. The chosen implementation must show protected storage/transport and credential rotation/revocation evidence. |
| SEC-06 cross-site requests and resource abuse | Check current anonymous/session CSRF binding, foreign/missing Origin/token and rotation/account-switch replay for every applicable POST. Attempt forged authority headers and bounded concurrent registration/search/acceptance at selected limits. Observe rejection before expensive execution/growth and accurate exhaustion/retry behavior. Verify read/reconnect/history listing causes no job, claim or debit. |
| SEC-07 unresolved or changed data permission | Block fixture/content/model handling with absent or wrong-purpose evidence; allow the properly evidenced synthetic control. Change eligibility during queued work, cached read and source/result revisit. Inspect projection/cache/payload/result consequences without silently changing paper/version or treating unsupported use as an empty success. |
| SEC-08 deletion/restore resurrection and missing lifecycle participant | Advance owner revocation/history-clear boundary and replay old facts/receipts, then restore a permitted isolated snapshot using the selected policy. Verify current restrictions, relationship integrity, retained/erased content and queued work dispositions. Omit/fail a participant and ensure completion remains pending. Report recovery evidence gaps explicitly. |
| SEC-09 shared-device and late-response disclosure | Delay A requests/events across expiry, B login, Back/restored page, tab changes and browser restart. Check rendered/accessibility/private cache surfaces, protected storage and current-epoch filtering. A fresh authorized return uses own lists/history to rediscover committed work without transient IDs; no unsafe client token/payload storage or automatic mutation replay. |
| SEC-10 inaccessible or misleading authentication recovery | Traverse entry/proof expiry/delivery failure/rate limit/login expiry with keyboard and assistive technology; check meaningful labels, focus and status on responsive layouts and both appearances. Use password-manager/paste and test safe navigation return. Capture actual rendered evidence and exceptions against the approved accessibility target; no conformance claim from design. |

Recovery tests preserve the distinction between an **acknowledged server save**,
an **unknown operation outcome** and **unsent local input**. Unknown acceptance
reconciles the original immutable identity/input under current permission; it
does not create a new job. Any persisted recovery record must be owner-bound,
not readable before appropriate authentication, and governed by declared
retention/discard/shared-device rules. The storage mechanism is deliberately
unselected. Durable research draft recovery remains the approved U4 obligation,
including restart rediscovery; it is not weakened by U1's narrower surfaces.

## Evidence prerequisites and completion boundary

| Decision/evidence item | Owner and required record | Consequence while unresolved |
|---|---|---|
| Identity, session, secret and request protection | AccountAccess / host: canonical-bound configuration, purpose/lifetime/rotation, safe credential persistence, cookie/Origin/CSRF and privileged-operation matrix; executable SEC-01/05/06 evidence | No affected identity/private operation may be enabled with an unspecified protection. Public-service fitness additionally needs real free delivery/network evidence. |
| Source/model/data obligations | Each data owner with maintainer decision: actual provenance, investigated permission/consent/location/recipient obligations and permitted fixture/model processing | No affected source load, sensitive transfer, model use or hosting choice. Unrelated logical work can continue; public availability is insufficient evidence. |
| Finite admission and runtime bounds | Domain owners: measured workload/resource fit and approved policy values; connect to capacity requirements and configured boundary checks | Unknown is not unlimited. Refuse affected admission truthfully and retain full-capability scope for resolution. |
| Retention, shared-device treatment and restore | Installed owners: per-class primary/derived/cache/receipt/telemetry/backup lifecycle, participant manifest, authoritative inventory and isolated recovery evidence | No affected sensitive persistence, cleanup/erasure completion claim or real-user continuity choice. A synthetic demo is not a migration decision. |
| Canonical coordination and actual boundary verification | U1 owner implementations: coordinated browser/worker/history amendments, compatible bindings and SEC/LC/FUI evidence on real mounted paths | Design rows do not close Contract R-01/R-03 or LC07. Later-unit bindings and U8 cumulative checks remain required. |

Numeric thresholds follow the approved evidence/decision process; this does not
defer non-disclosure, current authority, safe explicit effects or truthful
acknowledgement. The two Minor Functional Design details (empty-glossary revision
and immutable acceptance time) remain assigned to coordinated contract/design
closure in the technology record. They must not be guessed by security adapters.

This package establishes testable requirements. It does not claim deployed
multi-user isolation, audited compliance, actual source/model rights, verified
backup recovery or accessibility conformance. Local document/schema validation
cannot replace the separately approved runnable cumulative v2 verification
command or the evidence for each mounted protection.

## Sources

- [Confirmed U1 NFR proposal](nfr-requirements-questions.md).
- [Inception requirements](../../../inception/requirements-analysis/requirements.md),
  NFR4–NFR6 and related functional acceptance boundaries.
- [U1 functional specification](../functional-design/functional-spec.md), access
  matrix, WF1–WF9, LC01–LC14 and evidence prerequisites E1–E7.
- [U1 business rules](../functional-design/rules.md), particularly BR1, BR2,
  BR4.4, BR5.5–BR5.10, BR6 and BR7.
- [U1 frontend specification](../functional-design/frontend-components.md),
  identity/navigation, request integration, safe recovery, FUI-01/FUI-11/FUI-12.
- [Contract coordination plan](../functional-design/contract-revision-plan.md),
  browser preconditions, trusted execution and owner-bound retained history.
- [Canonical contracts](../../../inception/contract-design/contract-summary.md),
  common authority/HTTP/SSE rules and C02 identity boundaries; coordinated
  amendments must supersede the known gaps before affected code.
