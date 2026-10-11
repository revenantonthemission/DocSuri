# DocSuri v2 — Refined Mockups

Date: 2026-10-11 (Asia/Seoul). Design proposal derived from the [approved requirements](../requirements-analysis/requirements.md) and [confirmed design answers](refined-mockups-questions.md). The complete first release retains all current capabilities. These are reviewable designs, not implemented features or measured service results.

## Design intent

A stable, smooth, integrated research workspace: clear paper titles, generous reading space, DocSuri's inherited blue accents and neutral surfaces, and persistent context for the selected paper, account and task. Keep the DocSuri name and current color identity while improving hierarchy, navigation, typography and consistent controls through documented Apple Human Interface Guidelines (HIG) adaptations for the web. The light accent is `#2f6df6`; the dark accent is `#5b8bff`. Accessible text and control-boundary variants complement these inherited colors; [the mapping](design-system-mapping.md) records exact pairs and limits.

Prioritize desktop/laptop reading, then adapt all retained web capabilities to small screens. Use one Korean-capable system sans family, aligned content groups and selective blue emphasis for important actions and selection. Reading surfaces remain opaque and steady; restrained depth distinguishes functional overlays without decorating paper content with glass effects. Operational command-line capabilities retain an operator-facing text specification rather than acquiring a new phone application.

The core sequence is Search → Paper → Understand → Save → Library → Reopen. Research, novelty and citations remain first-class destinations around that sequence. A successful-looking toast never substitutes for an acknowledged write. Reading an existing result never starts a job. A preview never authorizes export.

Integration means preserving useful context across that sequence: retain the query, applied refinements, order and result position when returning from a paper; retain paper/version and source anchors when opening an understanding result or citation; reflect the acknowledged save consistently in the reader and library. Responsive panels change placement without changing the active object. Authentication restores only an authorized destination and owner context. Private input stays out of navigation URLs, and a different account never inherits the prior account's workspace.

HIG guides the hierarchy, grouping, action emphasis, feedback and appearance treatment. This is an explicit web adaptation, with semantic HTML, browser navigation and WCAG verification; it does not select an Apple framework or claim full HIG conformance. The bounded [HIG mapping](design-system-mapping.md#apple-hig-to-web-mapping) identifies sources and deliberate platform differences, including retention of Light / Dark / System.

## Visual artifact and review guide

Open [the local interactive screen atlas](prototype/index.html). It contains 16 composed web screens and two operator record examples, a light/dark/system selector, and selectable normal, loading, empty, failure, partial, interrupted, access-denied and expired examples. The prototype uses only synthetic content and inline/local assets; its action feedback is explicitly a simulation. It does not register accounts, persist drafts, run models, send messages or export anything.

The atlas is a design navigation aid, not a fully implemented click-through service. Use its screen selector to inspect each composition; use the numbered scenarios below to assess behavior. Detailed component states, ownership rules and keyboard behavior are normative in [interaction-spec.md](interaction-spec.md). Component reuse and visual tokens are in [design-system-mapping.md](design-system-mapping.md). The [accessibility checklist](accessibility-checklist.md) separates design decisions from future implementation verification.

Review in this order:
1. M03 → M04 → M05 → M06: find, understand, save and revisit the pinned paper.
2. M08 and M09: long research/manuscript input, draft recovery and interrupted work.
3. M01/M12/M16: public registration, identity changes, privacy and administrative boundaries.
4. M07/M10/M11/M13/M14/M15, then O01/O02: remaining capability coverage.
5. Repeat representative screens at 390 CSS pixels, 200% zoom, in dark appearance and with the keyboard. Rendered checks are recorded separately; none proves WCAG conformance or full capability parity.

## Information architecture

| Area | Destinations and context |
| --- | --- |
| Public entry | DocSuri introduction; registration, login, verification, password recovery, account reactivation and unsubscribe landing states |
| Research workspace | Search; Library with Papers / Searches / History / Recent; Research sessions; Novelty; Followed topics |
| Within a paper | Read; Summary/translation activity and results; Citations; save/remove; source/version and content availability |
| Account | Profile/consent; preferences/appearance; glossary; identity/security; draft recovery controls; usage/plan status |
| Administration | Separate authorized entry, MFA where required; quota grants/revocation and existing administrative views/actions |
| Operations | Existing authorized operational view or CLI, with corpus, readiness, incidents, resource evidence and controlled-protocol records |

Proposed entry boundary: registration and recovery entry points are public; owner-specific work requires authentication, and administration requires the relevant role and MFA. Anonymous corpus reading/search behavior remains subject to the current-access reconciliation in the requirements; this proposal does not add anonymous capabilities or remove an existing one without evidence. Direct links preserve the intended non-sensitive destination through sign-in. Never encode private manuscript/question text in a URL.

Desktop navigation uses a 224px left rail, a compact context/header row, and a content area up to 1440px. A paper uses a flexible reading column and an approximately 320px assistance rail where space permits. At 768–1199px the rail becomes compact navigation and assistance moves below or into a labeled panel. Below 768px use a menu plus the current destination label, one column and full-width dialogs. These are proposed layout breakpoints, not device exclusions or measured performance thresholds.

Text fallback for the paper layout:
```text
DocSuri / account                         paper title / version / Save
Search   Library   Research               section index | paper text | assistance
Novelty  Topics                          source status | figures    | job/result
Settings / Usage                         citations     | anchors    | source links
```

## Screen compositions and state requirements

All screens inherit the shared state contract below. The entries specify additional cases; they are not optional omissions when the normal mockup is displayed.

### M01 — Public entry and authentication

Split desktop composition: an editorial DocSuri panel with the paper journey, and a narrow form card. On phones the introduction becomes a short heading above the form. Login and registration are explicit modes; label email/password, show password rules before entry, allow paste/password managers, and retain non-secret fields after a failed submission. Google and ORCID options identify the provider.

Related panels cover email verification/resend, reset request/new password, email change verification, withdrawal/reactivation and invalid/expired/used links. Show neutral account-discovery responses, bounded resend status and provider-denial/collision recovery without silently creating another account. Verification pending is distinct from delivery failed. A trusted destination is restored after authentication; no automatic export/job submission follows login. Secret inputs clear on terminal session change. M12 contains authenticated security actions.

### M02 — Onboarding

A single interest-selection panel with selected chips, optional ORCID suggestions identified as such, Continue and Skip. Skipping is visually available and never a failure. Interrupted onboarding resumes the committed state; a provider outage leaves manual selection and skip usable. Existing preferences are not overwritten by a refreshed suggestion list. Loading suggested interests does not block navigation to the normal service.

### M03 — Search workspace

Header: “논문을 찾고, 맥락을 이해하세요” (find papers and understand their context). A labeled query field sits above visible mode/refinement controls, result count/freshness and Save search. Result rows show title, authors/year, paper/version identity, availability, source and separate Open / Save actions. Filters use removable chips and a labeled all-filters region; full retained filter/order vocabulary is reconciled under IB-01 before implementation.

Normal fixture: P1, “Attention Is All You Need”, 1706.03762v7. The sample query is the approved research query, not a title-only replacement. The query form, mode/order controls, applied filters and access to refinements remain visible and usable during loading, no-match and retrieval failure; only the results region changes state. Loading labels that region busy while retaining the submitted context. No match offers Edit query / Clear filters; failure offers Retry search and query editing without displaying zero results. Editing does not silently launch a request or overwrite the last submitted context. Semantic fallback is labeled with the actual mode. Pagination retains ordering/context; source changes display a refresh notice rather than silently claiming a fixed result set. Saved-search success requires a write acknowledgement; failure retains the query.

### M04 — Paper reader

A stable paper heading includes version/source status and a save button. A section index, readable text column, anchored figures and source links lead; assistance occupies a secondary rail. Distinguish Read source, Start summary/translation and Open prepared result. Display language and presentation choices with the relevant understanding action; their exact retained choices require reference reconciliation.

Private documents display a private-owner/context indicator and never reuse public-corpus URLs. Source-only, building, unsupported, failed, withdrawn and restricted material each explain availability. An authorized source link can remain when full text is unavailable. No invented body text or endless spinner. On narrow screens, contents becomes a disclosure and assistance follows reading or opens as a named panel; selecting an evidence link closes the panel if needed and moves focus to the referenced section without changing paper/version.

### M05 — Activity and prepared result

One job card shows paper/version, requested action/language, plain-language state, last confirmed update and an optional connection notice. Show queued, running, succeeded, failed, cancelled where supported, and unknown/unreachable state distinctly. Do not fabricate percentages or queue position. A duplicate submission returns the same intended activity. Reconnect refreshes the authoritative job without regressing a terminal state.

The result inspector presents summary or translation with source anchors, coverage/abstention and language. Opening or retrying a result read only rereads. An expired result offers a separate “Request again” action with quota implications and explicit new submission. Missing/unauthorized results disclose no private identifiers. Retryable failed work has a separately named Retry job action; its effect must follow the job contract. Cancellation is exposed only for operations whose retained capability supports it.

### M06 — Library, saved searches and history

Tabs: Saved papers, Saved searches, History and Recent. Each row preserves identity/version, provenance and availability, with separate Open, Rerun or Remove. A changed canonical identity is explained; a withdrawn reference remains identifiable rather than being silently replaced. Reopen prepared results only while retained.

Save/remove remains pending until confirmed; ambiguous outcomes reconcile before another effect. Clear history opens a scope-specific confirmation and does not remove saved papers/searches. History pagination and concurrent tabs converge after refresh. An empty library invites search; an unavailable store shows failure, not an empty collection. B cannot see A's list, counts, previews or direct links.

### M07 — Citations

A paper-context heading, direction controls (cited by / references) and a visual neighborhood are paired with an equivalent linear list. Each item carries its known identity and an eligible Save action or explanation. Bound the displayed graph and provide an explicit load-more action. Mark missing metadata, incomplete/stale relationships, cycles and provider limits; never imply the graph is exhaustive. Keyboard users can perform all exploration/saving through the list without dragging.

### M08 — Research sessions and evidence

Session list on the left; conversation/evidence in the center; source details on demand. A new-question composer names the document scope, attachments and optional web references. Sources distinguish uploaded, corpus and web material, including whether it was actually read. The durable draft status appears beside the input, not buried in a toast. Both its primary status and helper text reflect the same save state: only the last acknowledged revision is recoverable after restart, with its confirmed time when known; saving, failure or conflict never claims the newest text is saved. M08's action is “질문 보내기” (Send question). On phones, the session list is a separate panel and source details follow their claim.

Answers group claims, quotations, disagreements and limitations, each with a source/section link. Missing evidence yields an abstention or labeled partial response. Attachments show type, progress, validation failure or truncation; rejected material cannot appear as accepted context. Committed messages and accepted turns survive reopen independently of unsent drafts. Deleting one/all sessions names its scope and pending-work consequences; a late event cannot recreate a deleted session.

### M09 — Novelty workspace

Topic / Manuscript input mode, evidence-scope controls, a long text area with the same acknowledged-revision draft status as M08, and an explicit “분석 시작” (Start analysis) button. Its visible label, accessible name and action feedback all identify analysis rather than sending a research question. File inputs follow the same private-material and validation contract as research attachments. Results separate evidence, comparison, limitations, artifacts and discussion. Scores, if supported, carry their method/limitations and are never labeled proof of originality.

Progress and cancellation use M05's authoritative state rules. A cancellation request displays “Cancellation requested”; only the acknowledged result says cancelled. If completion wins, show the completed outcome. Artifacts/chat are owner-scoped and can expire. Export always leads to M10; completion never initiates external publication.

### M10 — Notion connection, preview and export

A stepped composition: connection/destination → exact content preview → explicit export confirmation → outcome. The destination/account and content revision remain visible above the final button. A changed destination/content invalidates approval and returns to preview. Connection failure or revoked credentials offers repair without exposing tokens.

Buttons name effects: “Preview” is read-only; “Approve and export” is the only publishing action. An ambiguous remote outcome says “Checking whether export completed” and disables blind repeat publication while reconciliation runs. Confirmed success links the actual destination; failure and unknown are distinct. Closing or cancelling the preview never publishes. These are visual simulations only; no external action occurs in this stage.

### M11 — Profile, preferences and privacy

A section navigation with Profile, Research defaults, Appearance, Consent/personalization and Drafts. Inline save status is tied to each committed setting. Appearance offers Light / Dark / System and reflects operating-system changes while System is selected. Korean is the reference UI language; paper/source titles retain their original language. The complete supported-language matrix remains to be verified; no speculative language switch is introduced.

Opt-out explains future processing scope. Event deletion/profile reset explain affected data and library independence before confirmation. Unavailable usage/consent state is unknown, not zero/off. The Drafts panel explains recovery and provides delete/discard controls for the authenticated owner; retention wording is a dependent policy item, not an invented duration. A storage conflict retains both available versions for an explicit owner choice.

### M12 — Account and security

Sections for password/email change, linked Google/ORCID identities, session/logout, and account withdrawal/reactivation. Sensitive changes require appropriate identity checks, neutral errors and visible completion. Link collisions/provider denial do not silently switch identity. Unlink consequences and admin recovery must be defined by the retained reference/security design.

Account deletion confirms its exact scope, pending jobs, saved/private data and the selected retention/reactivation policy. The final destructive action cannot be implemented from placeholder policy text. Logout removes private content from visible/accessibility surfaces and prevents a different account restoring the prior draft. M16's administrative MFA is a distinct authorization step, never inferred from a normal login.

### M13 — Glossary

A searchable term/preferred-form table with Add, Edit and Remove; row-level validation and acknowledged save state. Unicode terms remain readable. Duplicate/conflicting/empty/oversized entries use documented normalization rules. A concurrent edit is shown as a conflict with the prior committed value; a failed save preserves it. Explain which subsequent understanding actions use the glossary rather than claiming a retroactive result rewrite.

### M14 — Topics and digests

Followed topics list, topic input, follow/unfollow state and digest preferences. Display the configured time zone/window and latest confirmed subscription state; exact schedules/limits are future policy values. No new content differs from delivery failure. Unsubscribe has a clear public link landing state with appropriately bounded identity proof and no leakage of other subscription data.

Consent withdrawal/unsubscribe affects queued eligible sends before dispatch. Failure to commit the change is visible and retry reconciles the same intended operation. Delivery diagnostics belong in O01; a UI toggle is not proof that public email delivery works within $0.

### M15 — Usage and plan

Current allocation, observed usage, reset time with time zone, and explanation of limited actions. Unknown usage displays “Unavailable”, never 0. Exhaustion offers retry at the truthful reset/recovery condition or a permitted alternative; there is no purchase CTA. Existing subscription presentation is explicitly a mock/administrative assignment where applicable, with no implied real charge. Repeated work does not debit twice; disputed/uncertain accounting remains visible.

### M16 — Administration and MFA

Separate privileged context with account/role identity, MFA challenge and only authorized actions. An ordinary user gets safe denial without sensitive counts or identifiers. Tier grant/revoke presents target, current state, proposed change and confirmation; concurrent/stale changes revalidate before effect. Show audited success/failure and a safe correlation identifier, not secret or private manuscript content. Administrative entitlement cannot activate paid resources.

### O01 — Corpus and service operations (existing interface)

A text record or existing operational view, not a newly required web product:
```text
Target / operator / observation time / evidence freshness
Capability status: available | degraded | failed | unknown
Corpus action: refresh | rebuild | withdrawal | retry/reprocess
Authoritative input + checkpoint + eligibility + affected identities
Dependency/resource/grounding signals; incident and recovery evidence
Proposed action -> authority/precondition check -> recorded outcome -> verification
```
Preserve incremental refresh, dedup/version handling, withdrawals, dead-letter recovery and partial-batch inspection. A failed stage cannot advance completion/watermarks. Surface missing mounts/execution paths, not just process health. Distinguish measured zero, estimate, stale and unknown resource information. Verify recovery before clearing an incident; retain privacy-safe trace context.

### O02 — Platform evidence and controlled operations (existing interface)

Record actor/role, exact target, evidence version/age, compatibility, preconditions, intended effect and durable outcome. Current/stale/mismatched/missing evidence are different states. An unchanged readable report does not authorize a destructive or release effect. Wrong actor, stale input, disk/permission failure or unknown remote outcome prevents a completed claim. Retry reconciles the original outcome before another effect. This specification introduces no runnable operator commands and authorizes no operational change.

## Shared state and responsive contract

| State | Visible behavior and safe next action |
| --- | --- |
| Loading | Preserve committed context; label the region as busy; skeleton dimensions resemble final content; no fake data/counts |
| Empty | State what was successfully checked and absent; offer a relevant action; never use this for errors |
| Success | Show the actual committed/authoritative result and stable identity; announce once |
| Error | Plain explanation, preserved permitted input, safe correlation ID, distinct Retry read / Retry operation when needed |
| Partial/degraded | Identify missing coverage/mode/freshness and usable remainder; do not bury limitations |
| Interrupted | Distinguish lost connection from lost work; recover authoritative status; no automatic repeated external effect |
| Unauthorized | Clear private visible/accessibility content; require the correct owner/role, with no existence leak |
| Expired | Identify expired session/link/result/approval separately; reauthenticate or explicitly create new work as appropriate |

At <768px, every retained web action remains reachable through labeled menus/panels, not hidden permanently. Forms stack; lists/cards wrap; secondary information follows primary content. At 320 CSS pixels and 400% desktop zoom, normal content must reflow; genuinely two-dimensional figures/tables may scroll within labeled regions. Long titles, Korean/Latin mixed text, math, URLs and unbroken identifiers must not force whole-page horizontal scrolling. Modal primary actions stay reachable without obscuring focus. Reading text targets approximately 65–75 Latin characters per line with Korean-specific visual checks; source figures keep intrinsic aspect ratio.

## Requirement-to-screen traceability

| Capability / stable requirements | Screens | Specific design verification |
| --- | --- | --- |
| CAP-01: FR1.1, FR1.2, FR1.3 | M03 | Retained filters/order, mode/fallback, snapshot/pagination, failure vs empty, query recovery |
| CAP-02: FR2.1, FR2.2, FR2.3 | M04, M08 | Version/anchors/figures, all availability states, private asset isolation |
| CAP-03: FR3.1, FR3.2, FR3.3, FR3.4 | M04, M05 | Action/language/level, duplicate/restart recovery, monotonic status, result read vs new work |
| CAP-04: FR4.1, FR4.2 | M13 | Owner persistence, normalization, conflict/failure, downstream use |
| CAP-05: FR5.1, FR5.2, FR5.3 | M03, M04, M06 | Save/remove/rerun/clear, source disposition, separate history/library, simultaneous tabs |
| CAP-06: FR6.1, FR6.2, FR6.3, FR6.4 | M01, M12 | Public registration, delivery/link errors, identity/revocation, policy-bound withdrawal/reactivation, abuse feedback |
| CAP-07: FR7.1, FR7.2 | M01, M02, M12, M16 | Provider collision/callback/recovery, ORCID profile/suggestions, unlink, admin MFA |
| CAP-08: FR8.1, FR8.2 | M11, M15 | Consent persistence, owner boundary, explicit mock assignment/no charge |
| CAP-09: FR9.1, FR9.2 | M07 | Graph/list equivalence, eligible save, partial/unknown/stale/provider limits |
| CAP-10: FR10.1, FR10.2 | M06, M11 | Defaults/recent, cold start, opt-out, reset/delete without library loss |
| CAP-11: FR11.1, FR11.2 | M02 | Continue/skip/resume, no redirect loop, optional ORCID failure |
| CAP-12: FR12.1, FR12.2 | M14, O01 | Follow/configure, time zone/no new content, unsubscribe/queued-send revocation, delivery diagnostics |
| CAP-13: FR13.1, FR13.2, FR13.3 | M08 | Evidence/quotes/comparison, private attachments/web provenance, malformed/partial/abstained response |
| CAP-14: FR14.1, FR14.2 | M08 | Committed turn and pending status recovery, delete one/all, late completion |
| CAP-15: FR15.1, FR15.2 | M09, M05 | Both input modes, evidence/artifacts/chat, cancellation race and expiry |
| CAP-16: FR16.1, FR16.2 | M10 | Owner connection, current destination/content preview, explicit approval, ambiguous export reconciliation |
| CAP-17: FR17.1, FR17.2 | M15, M16 | Grant/revoke, unknown/exhausted/concurrent use, reset/time-zone/refund semantics |
| CAP-18: FR18.1, FR18.2, FR18.3 | O01, M04, M06 | Eligible refresh/rebuild/version/dedup, withdrawal, partial/retry recovery |
| CAP-19: FR19.1, FR19.2, FR19.3 | O01, M05 | Capability readiness, privacy-safe incidents/resource/grounding signals, verified recovery |
| CAP-20: FR20.1, FR20.2 | O02 | Freshness/compatibility, actor/target/precondition, durable effect reconciliation |

NFR1–NFR3 apply to every sequence and state; NFR4/NFR5 to every owner-bound or content surface; NFR6 to all web interactions; NFR7 to the component contracts and reproducible checks; NFR8 to resource/exhaustion feedback; NFR9 to safe status/correlation; NFR10 to boundary-consistent states. Coverage here is a design map, not proof of the downstream full-parity ledger or source-complete inventory.

## Walkthroughs and expected observations

- **V01 / P1 normal:** M01 register/verify → M02 skip or finish → M03 approved research query → M04 1706.03762v7 → M05 source-linked understanding → Save → M06 later login/reopen. Return from the paper to the retained query, filters/order and result position; return from evidence to the same paper/version/anchor. Match the requirements' §3.2.1/§3.5 rubric rather than judging visual polish as answer quality. Repeat M03 in loading/no-match/error: its query and refinement controls remain available, with edit/clear/retry actions appropriate to the state.
- **V02 / P2 and translation:** repeat using 2005.11401v4 and the approved RAG query/rubric; select a retained translation action/language pair and inspect source correspondence. Existing results reopen without regeneration.
- **V03 interrupted work:** submit once, sleep/reconnect/restart, then inspect M05/M08. Terminal state does not regress; lost acknowledgement reconciles the intended job/turn.
- **V04 draft recovery:** type in M08/M09; observe saving then acknowledged saved; restart and authenticate as the same owner; restore context and text. Repeat with save failure, expired session, account switch, explicit logout, conflicting tabs and deletion. Both status and helper identify only acknowledged drafts as recoverable after restart; show a saved time only when known, and never imply the latest failed/conflicting edit is durable. Verify M08 sends a question while M09's visible and accessible “분석 시작” action starts analysis.
- **V05 owner isolation:** B/anonymous/revoked sessions follow A's private direct links, assets, drafts, history and export preview. No prior-owner text, count, source or result leaks.
- **V06 truthful writes:** fail save, history clear, preference update and topic unsubscribe. No false saved/deleted state; retry preserves the intended effect.
- **V07 controlled export:** modify preview/destination after approval; interrupt after possible remote success. Require a new approval for changed content and reconciliation for unknown outcome.
- **V08 administration/operations:** ordinary account denied; eligible admin completes MFA; stale quota/operational preconditions rejected; unknown resource/disk outcomes never appear completed.
- **V09 accessibility/responsiveness:** keyboard-only paper and account flows, screen-reader status/draft recovery, 320px reflow and zoom, long Korean/source text, both appearances and reduced motion. See the checklist for test evidence required later.

## Assumptions & Open Questions

| Item | Decision/evidence and deadline |
| --- | --- |
| D-01 durable drafts | The user selected recovery after browser restart. Storage, encryption/key/session access, retention duration, automatic expiry, deletion/backup propagation, offline write semantics and shared-device handling require privacy/security and capacity evidence before implementation. UX invariants are specified now; no invented retention period. |
| D-02 exact parity vocabulary | Reconcile every current filter/order, summary level/language, provider unlink rule, supported file/format and operational surface under IB-01/03 before coding the affected contract. The all-capability boundary remains fixed. |
| D-03 account/data policy | Retention/reactivation, erasure, revocation and pending-work deletion/restore remain upstream decisions. The UI must explain the eventual approved policy; a placeholder is not production acceptance. |
| D-04 access/language/browser matrix | Verify current anonymous permissions and supported languages/browsers/assistive technologies. Proposed Korean reference copy and responsive layouts do not remove existing supported behavior. |
| D-05 resource and integration fit | Verify public email, provider sign-in/export, local models/search and workload limits at $0. Prototype simulations are not evidence of feasibility or integration parity. |
| D-06 validation | Numeric service-quality goals follow the baseline. Actual user usability evidence and implemented WCAG checks are still required; design review is not a conformance assessment. |

No stack, hosting, migration, schedule, paid service, production operation or external publication is chosen by these mockups. Git follows [CONVENTIONS.md](../../../../../../../CONVENTIONS.md): working branch → PR into develop → release promotion to main.
