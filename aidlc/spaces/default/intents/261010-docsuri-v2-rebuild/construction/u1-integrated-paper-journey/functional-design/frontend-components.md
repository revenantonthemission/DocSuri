# U1 — Frontend components and interactions

Date: 2026-10-11. Unit: `u1-integrated-paper-journey`.
Status: functional design; no implementation, rendered accessibility verification
or successful journey is asserted.

## Scope and authority

This specifies WebWorkspace's U1 contribution to the approved C01–C04, C06–C08
and C10 conceptual UI families. The browser presents AccountAccess,
CorpusContent, Discovery, Library, Personalization, PaperAssistance and
UsageEntitlements outcomes; it owns no competing business record. ServiceOperations
supplies safe capability/failure information through the host's public view.

U1 demonstrates registration and safe entry, research-query discovery, exact
paper/version reading, source-bound summary and a supported translation, committed
paper/query saving and fresh authenticated return. U1 remains a contribution to
all-capability v2; absent later modules are never presented as completed features.
Durable research/manuscript composers and their restart rediscovery belong to U4.
There is no new free-text research composer, note-taking feature, or paper-job
cancellation control here.

The [functional specification](functional-spec.md) owns ordered behavior and
state machines. [Entities](entities.md) and [rules](rules.md) own the logical
model and business decisions. The input/state names below describe conceptual
presentation boundaries, not additional HTTP properties. Rule groups are BR1
access, BR2 corpus, BR3 discovery, BR4 saved work/preferences/revisions, BR5
accepted work/accounting, BR6 presentation and BR7 operations/evidence.

## Component hierarchy and inputs

WorkspaceShell contains the entry or authenticated workspace. Its main region
selects SearchWorkspace, PaperWorkspace or SavedWorkWorkspace. AccountEntry and
SafeEntryPanel handle identity and minimal entry. AppearanceControl,
CapabilityNotice and the shared StatusMessage remain shell contributions.
PaperWorkspace contains PaperIdentity, ReadingSurface, SaveControl and
AssistancePanel; AssistancePanel contains AssistanceChoices, ActivityCard and
PreparedResultView. SearchWorkspace contains QueryForm, SearchStatus,
ResultList and SaveControl. SavedWorkWorkspace contains SavedPaperList,
SavedSearchList and the U1 history/recent-work contribution. RecoveryPanel is a
shared interaction surface, not a separate business owner.

| Component | Required conceptual inputs and callbacks | Local state and invariants |
| --- | --- | --- |
| WorkspaceShell | Safe session state, current route/manifest, permitted navigation contributions, authorized return context; navigate, authenticate, logout | Bootstrapping/anonymous/authenticated/locked; current focus destination and presentation epoch. Private children stay absent until authority is known. Route visibility is never authorization. |
| AccountEntry | Resolved registration/credential policy, verification disposition, safe return route; register, request verification, verify, login | Mode, non-secret form values, validation errors, one current submission identity and outcome. Password/proof are transient secrets; never stored in return context, URLs chosen by the application, telemetry or error copy. |
| SafeEntryPanel | Acknowledged settings/onboarding state and actual installed entry choices; read/update permitted default or skip | Cold start/default/manual/skip states remain usable. Missing suggestions do not block paper use. Never overwrite known choices during background hydration or create redirect loops. |
| QueryForm | Editable `LibraryQueryContext` vocabulary, last submitted context, policy limits; search, reset refinements, save submitted query | Edited values and submitted values are separate. A response is keyed to submission identity, authorization epoch and vocabulary/snapshot. A field edit does not search, save or rewrite the displayed response's provenance. |
| SearchStatus / ResultList | Accepted submitted context, `SearchResponse`, outstanding request identity, pagination; open exact paper, next page, retry search | Idle/loading/ready/empty/degraded/error/snapshot-expired. Controls are persistent siblings of this region in every state. A failed request is never an empty result. Late responses for superseded searches cannot replace the active result set. |
| PaperIdentity / ReadingSurface | Authorized `CorpusIdentity` and `CorpusContentRead`, paper/version, source eligibility/disposition, sections/asset references; follow anchor/source, return to query | Loading/readable/source-only/partial/unsupported/building/failed/withdrawn/restricted. Metadata, content, assets and source anchors use the same intended version. Missing one figure is a bounded local error, not fabricated content or a permanent whole-page spinner. |
| AssistanceChoices / PriorAssistanceList | `AssistanceOptions`, exact paper/content revision/hash and current permitted glossary/policy context; explicit submit or select a prior authorized job | Selected option is an allowed returned option for summary or translation, language pair and presentation level. Prior jobs come from the planned owner-authorized history contract described below, never guessed IDs. An unavailable/empty option list is explained; it does not establish capability parity. Changed source/options require fresh validation before new work. |
| ActivityCard | `JobReceipt`/`JobSnapshot`, request/owner/job identity, connection state; refresh status, read result, reconcile uncertain acceptance | Request idle/accepting/unknown is separate from authoritative accepted/running/succeeded/failed and live/reconnecting/offline transport. Terminal work never regresses because a stream closes or a stale frame arrives. No fabricated percentage or cancellation button. |
| PreparedResultView | Authorized `AssistanceResultRead` or the C13 prepared-job wrapper; read again, follow source, explicitly request new work | Reading/ready/pending/failed/expired/withdrawn/restricted and transport error are distinct. Show operation, selected option, source identity/version, coverage and limitations. Opening, refreshing, retrying a read or following evidence cannot submit assistance. |
| SaveControl | Current authoritative saved record or confirmed absence, intended paper/query, revision and original operation identity; save/remove/reconcile | Committed, pending, unknown, failed or conflict. Pending is not saved. A failed change preserves the last committed display. Reader and saved list converge from the same acknowledged record, not independent optimistic booleans. |
| SavedWorkWorkspace | Owner-bound saved-paper/search pages, history/recent pages, revisions/dispositions; read, explicitly rerun, confirm removal/clear | Loading/confirmed empty/ready/degraded/error/snapshot-expired. Query read and rerun are distinct actions. Withdrawal/canonicalization does not erase the saved original identity or redirect it to unrelated content. |
| AppearanceControl | Light/Dark/System preference and actual effective appearance; select appearance | System follows current OS changes. Browser-local storage failure permits a usable temporary selection but no persistence promise. Appearance is not implicitly account-synchronized. |
| CapabilityNotice / UsageView | Safe declared capability status, known usage with period/unit/policy or unknown, last known freshness; retry read | Distinguish disabled, degraded, exhausted, unknown and stale. A cached balance cannot authorize work. Public view never exposes worker secrets, private operational evidence or administrative controls. |
| RecoveryPanel / StatusMessage | Scope-safe error `code`, `messageKey`, `requestId`, optional `retryAfterSeconds`/`details.fieldNames`, affected action; deliberate named recovery | One bounded error explanation and applicable action. No raw stack, input echo or secret. Read-only inspector has no mutation confirm handler. Close returns focus; closing a submitted-work view does not cancel its job. |

## State ownership, validation and recovery

### Identity and navigation

Entry begins with session inspection and the safe capability catalogue. Anonymous
users may use the existing guest search; paper reading, personal saved work,
assistance and private progress/results require current authenticated authority.
Selecting protected work from guest search offers sign-in and retains only the
safe intended paper/version and approved return context. Completing authentication
returns to that context after validation; it does not save, start assistance or
repeat a previously interrupted mutation automatically.

Every private request and callback is bound to the current presentation epoch as
well as its server resource identity. Expiry immediately removes private content
from rendered and accessibility surfaces and suspends owner writes. Logout or
account change clears prior-owner private view models, response caches, pending
form state and subscriptions; late A responses cannot populate B's workspace.
Reauthentication as A performs fresh authorized reads before offering recovery.
A browser's locally hidden state is not proof of server logout: a failed revoke
remains an explicit unresolved server outcome, while private local content stays
hidden. Browser Back and restored page history must revalidate before exposing a
protected view.

Credentials use labeled native password/email controls with autocomplete and
paste/password-manager support. Client checks explain malformed/empty fields;
the server remains authoritative for normalization, password policy, proof
validity, abuse bounds and admission. Registration and recovery messages must
remain existence-neutral. Verification delivery pending, failed, expired or used
proof is distinguished from verified status. A local email sink is identified
in test evidence as a local path; the product must not claim public delivery
merely because that sink accepted a message.

### Search and reading

Query text, filters, mode, order, vocabulary revision and policy form one canonical
submitted `LibraryQueryContext`. Explain empty/whitespace-only, oversized,
unsupported vocabulary and malformed filter input beside the offending control.
Unicode and punctuation are not rejected simply for being non-Latin. Display the
chosen policy's actual bounds when known; unresolved required policy makes the
affected operation explicitly unavailable. No numeric limit is invented here.

The results region identifies the context it answers while the editable form can
hold a newer draft query. “검색” submits the current form; “검색 다시 시도” retries
the failed submitted context. “검색 조건 저장” saves a clearly identified submitted
context, not silently edited values. Previous results may remain visible during
replacement retrieval only with a clear previous-results label. Do not label them
as the new search's response. Requested and actual search mode/fallback and
coverage/freshness remain visible; unsupported semantic execution cannot masquerade
as a normal semantic result.

Pagination preserves snapshot, canonical context and response identity. On expired
or changed snapshot, keep the form and explain that results changed; offer an
explicit fresh search. Do not append incompatible pages or silently skip/duplicate
identities. Returning from a paper restores the prior query, refinements, order
and result position where still valid; a changed result set gets a freshness
explanation rather than a false exact-position claim.

Paper links carry exact identity/version. Corpus authorization and purpose
eligibility are checked again before rendering or fetching assets; stale caches
cannot override withdrawal. Render untrusted sections as safe content with
allowed links, meaningful heading/figure structure, anchor targets and readable
math fallback. An asset handle is opaque; the UI never builds storage paths or
uses private-attachment identifiers through public-paper asset routes. Unsupported
or missing content retains useful authorized metadata/source navigation where
permitted. External source links remain distinguishable from material actually
read by the service.

### Assistance acceptance, progress and result reading

The options read determines the allowed summary/translation operation, supported
language pair and presentation level. “요약 시작” and “번역 시작” create intended
work with the exact paper/version/content/options context. Buttons are disabled
only for the affected operation during admission and explain missing eligibility,
configuration or capacity. No default model answer appears if no prepared output
exists. Usage is rechecked at admission and settled by its owner, not by the UI.

While an acceptance response is unknown, preserve the original key and immutable
submitted input in the authorized recovery context. If a job identity is known,
read its authoritative status. If none is known, the existing acceptance contract
can reconcile by replaying exactly the same key/input; do not invent a lookup
endpoint or use a new key. Changes to intent or a deliberate new attempt after a
terminal failure require an explicit new submission identity. Same-key replay is
not a command to restart terminal work. Recovery storage and safe restart location
must be bound to the owner and approved policy; unauthenticated shared browser
storage is not a shortcut.

The event channel carries ordered snapshots from the same owner as status reads.
Validate job, owner, kind and increasing sequence before adopting an update;
discard duplicate/stale frames and mismatched late responses. A reset or replay
gap requires the current snapshot. Stream interruption or tab sleep marks only
the connection stale; bounded reconnect/polling recovers the authoritative state.
Do not turn a closed stream into succeeded, failed or cancelled. Expose the last
confirmed state separately from a locally observed receipt time; do not invent a
server update timestamp absent from the DTO. Worker replacement/fencing is enforced
behind this boundary; browser sequence checks are not a substitute for it.

“결과 보기” reads the retained prepared result. “결과 다시 읽기” repeats only that
read. A ready result displays original source/version, operation, language and
level resolved from its recorded option, complete/partial/abstained coverage and
limitations. Evidence links return to the exact accessible source anchor, then
back to the result without starting work. Expired or withdrawn is not a blank
successful answer; offer an explicit new request only when current eligibility and
options allow it. New work is never started on open, close, reconnect, refresh or
expiry. The first useful result remains readable if a separate new submission
fails, subject to its current permissions and retention.

### Saving, conflicts and fresh return

Saving a paper binds its original paper/version; saving a query binds the shown
canonical submitted context. Only an authoritative durable acknowledgement changes
the indicator to “저장됨”. “저장 중…” and “저장 여부 확인 중” never imply committed
success. Failed storage keeps the prior committed state, displays the failure and
offers safe recovery with the original identity. A replay with changed intended
input is a conflict, not a duplicate success. Removal deletes the owned saved
reference, never corpus content. History clear separately previews its scope and
does not delete saved papers or searches.

Revision-sensitive browser mutations carry the coordinated contract's required
`expectedRevision`; a client cannot silently substitute the server's latest
revision. A null revision is used only for an explicitly supported create-if-absent
case. Missing/malformed revision is validation failure. On stale conflict, keep
the pending local intent, read the current authorized record through its named
read operation and offer explicit use-current or revise-and-submit behavior.
`Error.details` currently permits `fieldNames` only: do not assume the error
contains a `latestRevision` or current record. The complete revision envelope and
replay rules must agree with the canonical C00/C13 amendment before implementation.

Two tabs refresh to the acknowledged state; a stale tab may not overwrite another
tab's update or recreate a removed record. Unknown write outcome reconciles before
offering a new identity. A fresh browser signs in before listing A's committed
papers and queries. Reading a saved query alone does not execute it or add history;
“다시 검색” is a separate deliberate search. Source identity/disposition is re-read
on revisit, and unavailable original content stays recognizable as that saved
reference.

Returning to a retained prepared result uses the **planned C06
`readAssistanceHistory` operation**: a bounded, cursor-based list scoped to the
current owner and exact paper/version, with each job's recorded input/source and
option context plus current result disposition. After opening the saved paper,
PriorAssistanceList shows those authorized prior jobs; the user chooses the
intended result explicitly, and the existing status/result read uses that job ID.
Do not silently select the latest job, attach a newly computed result to an old
save, or infer an expired result is available. Listing neither executes assistance
nor changes the library reference. Failed history reads are not an empty list.

This is a proposed canonical contract addition coordinated in the
[functional specification](functional-spec.md) and
[contract summary](../../../inception/contract-design/contract-summary.md), not
an already available C13 endpoint. Its typed request/response, owner/source checks,
stable cursor semantics, retention and exact browser binding must be added and
validated together before implementation. The existing C13 job reads require
`jobId`; neither a fabricated `LibrarySavedPaper` field nor browser memory supplies
the fresh-browser evidence. Implementation of the revisit path is blocked until
that formal addition and its permitted persistence policy are complete.

## HTTP and module integration points

These are exact operations and paths in the approved
[contract summary](../../../inception/contract-design/contract-summary.md), not
new routes. All listed operation POSTs use the existing C13 JSON, session/anonymous
bootstrap, Origin/CSRF and idempotency conventions. Being a POST does not make a
query an effect: saved-record, options, content and status reads remain reads.
Trusted identity/context is supplied by the boundary, never an editable browser
body. Safe errors use the common typed envelope; private responses are not shared
cache entries. The generic C13 job route dispatches to the same recorded operation
owner rather than creating a parallel status/result store.

| UI boundary | C13 binding | Owning contract operation / response |
| --- | --- | --- |
| Bootstrap and safe choices | `GET /api/v2/session`; `GET /api/v2/capabilities` | `sessionBootstrap` → `SessionBootstrap`; `capabilityCatalog` → `CapabilityCatalog` |
| Navigation | `POST /api/v2/c01/host-resolve-navigation` | C01 `host.resolveNavigation` → `HostNavigationResult` |
| Registration and verification | `POST /api/v2/c02/access-register`; `/api/v2/c02/access-request-verification`; `/api/v2/c02/access-verify-email` | C02 `access.register`, `access.requestVerification`, `access.verifyEmail`; delivery receipt differs from verified acknowledgement |
| Session entry/exit | `POST /api/v2/c02/access-inspect-session`; `/api/v2/c02/access-login`; `/api/v2/c02/access-logout` | C02 `access.inspectSession`, `access.login`, `access.logout`; cookie handling stays in trusted transport |
| Entry/default state | `POST /api/v2/c03/settings-read`; `/api/v2/c03/settings-update`; `/api/v2/c03/settings-update-onboarding` | C03 `settings.read`, `settings.update`, `settings.updateOnboarding` → `SettingsSnapshot`; required revision convention applies to mutations |
| Search | `POST /api/v2/c05/search` | C05 `search` → `SearchResponse`; guest authority differs from authenticated history behavior |
| Paper identity and content | `POST /api/v2/c04/resolve-paper`; `/api/v2/c04/read-content`; `/api/v2/c04/read-asset` | C04 `resolvePaper`, `readContent`, `readAsset`; only authorized adapter resolves returned asset handles |
| Paper asset bytes | `GET /api/v2/papers/{paperId}/versions/{versionId}/assets/{assetId}` | C13 `deliverPaperidAsset`; current source/owner check on every delivery |
| Assistance choices/admission | `POST /api/v2/c06/read-assistance-options`; `/api/v2/c06/accept-assistance` | C06 `readAssistanceOptions` → `AssistanceOptions`; `acceptAssistance` → `JobReceipt` |
| Status read | `GET /api/v2/jobs/{jobId}` or `POST /api/v2/c06/read-assistance-job` | C13 `jobSnapshot` dispatches to C06 `readAssistanceJob` → `JobSnapshot`; no new execution |
| Ordered progress | `GET /api/v2/jobs/{jobId}/events` | C13 `jobEvents`, authenticated SSE snapshot/reset events; `Last-Event-ID` or `afterSeq` resumes the declared sequence |
| Prepared result read | `GET /api/v2/jobs/{jobId}/result` or `POST /api/v2/c06/read-prepared-assistance` | C13 `preparedJobRead` → `PreparedJobRead` wrapper; C06 `readPreparedAssistance` → `AssistanceResultRead`; normalize the documented wrapper explicitly, not as interchangeable JSON |
| Paper saved references | `POST /api/v2/c03/library-save-paper`; `/api/v2/c03/library-read-saved-paper`; `/api/v2/c03/library-list-saved-papers`; `/api/v2/c03/library-remove-saved-paper` | C03 `library.savePaper`, `library.readSavedPaper`, `library.listSavedPapers`, `library.removeSavedPaper` |
| Saved queries | `POST /api/v2/c03/library-save-search`; `/api/v2/c03/library-read-saved-search`; `/api/v2/c03/library-list-saved-searches`; `/api/v2/c03/library-remove-saved-search` | C03 `library.saveSearch`, `library.readSavedSearch`, `library.listSavedSearches`, `library.removeSavedSearch` |
| History/recent contribution | `POST /api/v2/c03/library-list-history`; `/api/v2/c03/library-read-history`; `/api/v2/c03/library-clear-history`; `/api/v2/c03/settings-list-recent-papers` | C03 `library.listHistory`, `library.readHistory`, `library.clearHistory`, `settings.listRecentPapers`; history fact recording remains internal |
| Usage | `POST /api/v2/c03/usage-inspect`; `/api/v2/c03/usage-read-plan` | C03 `usage.inspect` → `UsageMeasurePage`; `usage.readPlan` → `UsagePlanPresentation`; no client-selected admin entitlement |

The planned `readAssistanceHistory` binding is deliberately absent from the table
of existing paths above. Its eventual formal C13 path must be taken from the
coordinated canonical amendment, not derived from a route-name guess in the UI.

Wire schemas, operation IDs and the exact source/error vocabulary are generated
or validated together with the canonical contract. Browser calls to worker
claims, payload retrieval, completion facts, quota settlement, projection writers
or lifecycle acknowledgements are forbidden. Numeric retry, lease, timeout and
poll bounds remain approved policy prerequisites rather than UI constants selected
by this design. R-01 browser revision and R-03 worker claim corrections require
coordinated formal contracts and executable evidence; these tables alone close
neither finding.

## Korean interaction copy and error presentation

| Meaning | Reference copy | Applicable action |
| --- | --- | --- |
| Search in progress | “검색 중이에요” | Keep query and filter controls visible and editable |
| Confirmed empty response | “일치하는 논문이 없어요” | Edit query / clear filters; no-match only after successful retrieval |
| Fallback/partial results | “일부 결과만 표시하고 있어요” | Explain actual mode and limitation; no false full result claim |
| Retrieval failed | “검색 결과를 불러오지 못했어요” | “검색 다시 시도”; retain submitted context |
| Accepted work | “요청을 접수했어요” | Show authoritative status; no completion claim |
| Acceptance unknown | “요청 접수 여부를 확인 중이에요” | Reconcile original identity; no blind new request |
| Interrupted progress | “연결이 끊겼어요. 마지막으로 확인된 상태를 표시해요” | Reconnect / read current status; work state remains separate |
| Prepared result expired | “결과 보관 기간이 지났어요” | Explain actual declared policy; eligible new work is a separate explicit action |
| Save pending / unknown | “저장 중…” / “저장 여부 확인 중” | Keep prior committed state identifiable |
| Confirmed save | “저장됨” | Acknowledged revision only; confirmed time only if provided |
| Failed save | “저장하지 못했어요” | Explain prior committed state; safe retry/reconciliation |
| Stale mutation | “다른 곳에서 변경되었어요” | Fresh authorized read, explicit comparison/choice |
| Session expired | “다시 로그인해 주세요” | Neutral sign-in surface; no private preview |
| Unknown usage | “사용량을 확인할 수 없어요” | Read again; never render zero remaining/used by assumption |
| Operation unavailable | “현재 이 작업을 사용할 수 없어요” | Specific safe reason and known recovery, no paid fallback |

Reference copy is a meaning contract. Final labels must reflect selected policy
and actual server disposition; expiry copy cannot invent a retention duration.
Show rate-limit waiting only when the response provides a valid retry interval.
Long server messages are not rendered as raw markup. Provide a selectable safe
support/request identifier where useful without exposing private input.

## Visual, responsive and accessibility contract

Inherit the approved semantic tokens: blue accent `#2f6df6` light / `#5b8bff`
dark, neutral canvas/surfaces, accessible light blue text `#2963df`, and the
specified strong control borders. Apply the approved palette's full state pairs;
do not reduce near-threshold enabled text opacity or use decorative separators
as the sole required control boundary. This carries the earlier measured palette
forward; it is not a new rendered contrast pass.

Use Korean-capable system typography, a stable context header, grouped controls,
selective primary emphasis and opaque reading surfaces. Apple HIG adaptations
support clarity, hierarchy and restrained depth in the browser; they add no
native toolkit, Apple-only gesture or paid asset dependency. Preserve browser
Back, links, text selection, keyboard conventions and appearance settings.

Desktop starts with the approved rail and readable paper column; assistance is
secondary. At compact widths it moves below where needed; on phones all U1
destinations remain reachable through a labeled menu, reading is a single column,
and filters/contents use labeled disclosures. Breakpoint starting points remain
<768, 768–1199 and ≥1200 CSS pixels, with content-driven reflow. Preserve active
paper, selected option, query context and focus when layouts change. Long mixed
Korean/English titles, identifiers and errors wrap without fixed-height clipping.
Only genuinely two-dimensional figures, tables or math use named bounded scroll
regions; ordinary text never requires two-dimensional scrolling.

WCAG 2.2 AA remains the proposed verification target. Required checks include
the complete keyboard path, a skip link/single main region and meaningful
headings, visible focus not hidden by sticky actions, labeled fields with linked
errors, browser zoom/reflow at 320 CSS pixels and text resizing, both themes,
reduced motion and meaningful content alternatives. Primary controls follow the
approved 44px design preference; the applicable 24px target/spacing criterion
still needs its own check. Do not infer conformance from these dimensions.

Deliberate route navigation focuses the destination heading. Background refresh,
typing and job updates preserve focus. Search-result counts and material status
changes use bounded polite announcements; terminal actionable errors are alerted
once. Error summaries after explicit failed submission link to affected fields.
Modal result/recovery views contain focus, identify title/description, keep Close
reachable and restore the trigger or logical successor on exit. A destructive
confirmation starts on Cancel and names the exact scope. Closing a result or
status panel has no business effect. No progressbar is used unless a meaningful
current/total pair is supplied.

## Local verification cases and remaining dependencies

The following FUI IDs are local design checks, not invented upstream acceptance
IDs. They supplement the canonical U1 requirement traceability and must exercise
the selected real browser/service/store/worker path later.

| Local check | Required evidence | Upstream contribution |
| --- | --- | --- |
| FUI-01 | A and B register/verify; safe entry works; malformed/duplicate registration, failed delivery, expired/used proof and login expiry remain truthful and existence-neutral | FR6.1/FR6.4; NFR4/NFR8 |
| FUI-02 | P1/P2 research queries locate the fixed intended versions; relevant source text is readable and source links/anchors resolve | FR1.1/FR2.1; NFR1 |
| FUI-03 | Loading/empty/error retains query controls; whitespace/Unicode/oversize validation; late first response cannot replace second search; changed cursor snapshot is explicit | FR1.3; NFR2/NFR10 |
| FUI-04 | Requested versus actual mode/fallback is disclosed; missing model/index/content, broken asset and withdrawn source never yield fabricated success | FR1.2/FR2.2/FR3.1/FR19.2 |
| FUI-05 | Useful summary meets P1/P2 source rubric; a returned supported translation pair preserves meaning/terminology according to competent review; coverage and limitations visible | FR3.1; NFR1/NFR5 |
| FUI-06 | Duplicate/lost acceptance, worker/service restart, sleep, replay gaps and interrupted SSE recover one job/result; late replaced-worker output is rejected before the browser receives an authoritative success | FR3.2/FR3.3/FR17.2; NFR3/NFR10 |
| FUI-07 | Prepared result reads/refresh/revisit issue no new admission; pending/failed/expired/withdrawn/restricted are distinct; evidence returns to same paper/version | FR3.4; NFR1/NFR4 |
| FUI-08 | Save paper/query, lose acknowledgement, reconcile, reload and fresh-login A; inspect durable records; B denied in UI and direct requests; failed save never displays confirmed success | FR5.1/FR5.3; NFR3/NFR4 |
| FUI-09 | Concurrent update/remove/clear uses explicit revision and truthful conflict recovery; clearing history cannot remove saved work or allow delayed cleared history to revive | FR5.2/FR5.3; NFR3/NFR10 |
| FUI-10 | Defaults/recent contribution is truthful; unknown/exhausted/stale usage distinct; denied admin entitlement and no paid fallback under resource pressure | FR10.1/FR17.1/FR17.2/FR19.1; NFR8 |
| FUI-11 | Expire A then login B while A responses/events arrive; no A private text appears in DOM/accessibility tree/history-restored screen; same-owner return never replays mutations | FR6.3/FR6.4; NFR3/NFR4/NFR5 |
| FUI-12 | Complete journey with keyboard, assistive technology, long mixed text, zoom/reflow, phone/tablet/desktop, both appearances and dynamic System changes; blocked preference storage stays usable | NFR2/NFR6 |
| FUI-13 | A controlled failure has safe request/job identity and reproducible state; diagnostics distinguish current/stale/unknown capability evidence; UI never reports full readiness from process liveness | FR19.1/FR19.2/FR19.3; NFR7/NFR9 |

P1 understanding must connect scaled dot products to softmax gradients and identify
positional signals/sinusoidal encoding (§3.2.1 equation 1 and §3.5,
1706.03762v7). P2 must distinguish BART parameters from retrieved Wikipedia and
RAG-Sequence versus RAG-Token without claiming only one retrieved candidate
(Figure 1, §2.1–2.3, 2005.11401v4). A generic fluent summary that misses those
rubrics fails the complete-task demonstration. Record exact fixtures, eligibility,
selected options, output, source checks, timing and recovery actions; no pass is
claimed by this design.

Before implementation acceptance, resolve the canonical browser revision envelope,
durable authorized assistance rediscovery, selected input/action vocabulary,
permitted processing and retention/shared-device policy, finite retry/admission
limits and actual free/local public-service capacity. No existing user data is
reset or migrated for this demonstration. Runtime verification must use the exact
cumulative command separately approved by the human once it exists. Later units
complete all remaining retained variants and cumulative parity; these U1 checks
are not the first-release completion boundary.

## Sources

- [Confirmed U1 plan](functional-design-questions.md).
- [Requirements](../../../inception/requirements-analysis/requirements.md), FR1–3,
  FR5–6, FR10, FR17, FR19, NFR1–10 and P1/P2 shared procedure.
- [Approved U1 boundary](../../../inception/units-generation/unit-of-work.md#u1--integrated-paper-journey).
- [Interaction specification](../../../inception/refined-mockups/interaction-spec.md),
  invariants, C01–C04, C06–C08 and common responsive/accessibility contract.
- [Design system mapping](../../../inception/refined-mockups/design-system-mapping.md),
  inherited semantic colors, HIG web mapping, appearance and responsive decisions.
- [Canonical contracts](../../../inception/contract-design/contract-summary.md),
  C00, C01–C06 and C13. Exact binding reads were made on 2026-10-11;
  coordinated amendments remain authoritative over derived presentation tables.
