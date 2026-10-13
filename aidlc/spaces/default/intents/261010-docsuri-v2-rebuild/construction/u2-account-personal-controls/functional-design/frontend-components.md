# U2 account and personal controls — frontend specification

This logical component design implements [workflows W1–W14](functional-spec.md) in the existing WebWorkspace. It introduces no component framework or independent application. It preserves the approved Korean interface, inherited blue/neutral colors, Apple HIG hierarchy/grouping/progressive disclosure, Light/Dark/System and WCAG 2.2 AA target. Mockups and this specification are design evidence; browser and assistive-technology verification are still required.

## Component hierarchy and ownership

```text
WebWorkspace
  SessionBoundary
    SafeReturnContext
    AuthenticationPanel
      RegistrationAndVerification
      SignInAndMfaContinuation
      PasswordRecovery
      ReactivationRequestAndStatus
    OwnerWorkspace
      AccountSettings
        ProfileEditor
        PasswordAndEmailControls
        LinkedIdentities
        MfaEnrollmentAndRecovery
        ConsentControls
        LifecycleActionAndProgress
      PersonalSettings
        DefaultsAndAppearance
        InterestOnboarding
        BehaviorAndProfileReset
      LibraryWorkspace
        SavedPaperList
        SavedSearchList
        HistoryListAndClear
        RecentPapers
      UsageAndPlan
      AdminBoundary
        EntitlementAssignment
  SharedStatus / ConflictResolution / BoundedPagination
```

SessionBoundary derives current identity and authority generation from the authenticated boundary, never component props supplied by a caller. Other components receive authorized projections plus typed operation callbacks. They do not import another owner's persistence. AdminBoundary improves presentation but server authority remains mandatory. SafeReturnContext contains allowlisted route/query context only; it never stores private paper text, credentials, MFA material or a mutation to replay.

## Props, state, commands and revision sources

All private projections are tagged with the current owner/authority generation. Every component discards responses from earlier generations before rendering, including background list refresh and browser-back restoration. Loading/error/unknown states are explicit tagged view states, not empty arrays or numeric zero defaults.

| Component | Logical props and local state | Canonical integration |
|---|---|---|
| RegistrationAndVerification | Public credential/field policy readiness, safe return route; local fields, bounded resend status, validation and delivery outcome | C02 access.register/requestVerification/verifyEmail; no caller-created authenticated account. |
| SignInAndMfaContinuation | Safe current session or limited continuation; local credentials/factor and expired-flow feedback | C02 access.login/inspectSession/verifyMfa/logout; cookies handled by the trusted transport; clear secrets on exit. |
| PasswordAndEmailControls / PasswordRecovery | Authorized current identity, safe policy consequences; local proof/new values, pending/unknown outcome | C02 access.requestPasswordReset/completePasswordReset/changePassword/requestEmailChange/completeEmailChange; no email update through ProfileEditor. |
| LinkedIdentities | Safe links with revisions, provider readiness, permitted profile coverage; link/unlink pending state | C02 access.beginIdentityFlow/completeIdentityFlow/listIdentityLinks/unlinkIdentity/readOrcidProfile; unlink revision from selected link. |
| MfaEnrollmentAndRecovery | Safe enrollment reference and policy readiness; transient protected material, confirmation/expired/recovery state | C02 access.beginMfaEnrollment/retrieveMfaEnrollmentMaterial/confirmMfaEnrollment/recoverMfa. One-time material never enters generic response storage or analytics. |
| ProfileEditor | Account profile, mutable field definitions, profile/vocabulary revisions; local edits and conflict comparison | C02 access.readProfile/updateProfile; expectedRevision from readProfile. No credential/email/role fields accepted. |
| ConsentControls | Current purpose/policy decisions and separate cleanup evidence; local pending toggle | C02 access.listConsents/updateConsent. Canonical operation has no invented client revision field; server serializes acknowledged decisions and UI refetches current state. |
| LifecycleActionAndProgress | Approved consequences, readiness and safe request projection; explicit action confirmation, blocked-scope status | C02 lifecycle.request/inspect; ordinary withdrawn sessions cannot poll. Only a specifically authorized current reader or narrow recovery flow may inspect. |
| ReactivationRequestAndStatus | Neutral public initiation, then bound proof/limited request continuation | C02 access.requestReactivation and lifecycle.reactivate/inspect; `sign_in_required` only after complete. |
| DefaultsAndAppearance | SettingsSnapshot, vocabularies and capability readiness; local defaults/appearance, dirty/conflict state | C03 settings.read/update; one shared settings revision. Unsupported preferences are disclosed, never silently replaced. |
| InterestOnboarding | SettingsSnapshot onboarding/interests, attributable suggestions; local selection and progress | C03 settings.updateOnboarding/listSuggestions; same shared revision. Explicit save/complete/skip; ORCID optional. |
| BehaviorAndProfileReset | Current settings/consent/projection, approved scope text; explicit confirmation and cleanup progress | C03 settings.reset with settings.read revision; C02 consent changes remain separate. Show boundary acknowledgement separately from complete cleanup. |
| SavedPaperList | Bounded page, saved identity/current disposition and per-record revision; selection and remove outcome | C03 library.listSavedPapers/readSavedPaper/savePaper/removeSavedPaper. A restricted source remains a labelled saved reference. |
| SavedSearchList | Bounded saved contexts/labels/revisions; open, explicit rerun, remove outcome | C03 library.listSavedSearches/readSavedSearch/saveSearch/removeSavedSearch; Discovery receives a separate explicit rerun. |
| HistoryListAndClear | Stable history page and separate clearBoundary; selected context and confirmed clear | C03 library.listHistory/readHistory/clearHistory. Never send page snapshot revision or a browser cutoff as expectedRevision. |
| RecentPapers | Permitted recent projection, source dispositions and pagination | C03 settings.listRecentPapers; cold start/disabled/unavailable remain distinct from saved library content. |
| UsageAndPlan | Known/unknown quota, server period, labelled mock plan and bounded records | C03 usage.inspect/readPlan/listRecords; no purchase controls or guessed zero balance. |
| EntitlementAssignment | Current administrator assurance, independently resolved target assignment and allowed policy tiers; reason/edit/conflict | C03 usage.readAssignment/grantEntitlement/revokeEntitlement. Revision is assignment-specific, including initial absent assignment; self-plan is not the admin revision source. |

## Shared interaction states

| State | Display and permitted next action |
|---|---|
| Loading | Keep the view title, navigation and relevant query/form controls. Announce progress without obscuring the entire workspace or presenting an empty account. |
| Empty | Explain the particular empty list and its existing next action; distinguish cold start, no saves and cleared history. |
| Editing | Mark unsaved values. Never promise restart recovery for account forms or credentials. Preserve local nonsecret edits during a recoverable validation/conflict flow while the same authorized owner remains. |
| Submitting | Show saving/requesting and retain one command identity; disable accidental duplicate submission for clarity while server idempotency remains required. |
| Saved/accepted | Use acknowledged revision or request reference. Accepted lifecycle/reset work shows pending scope progress; it is not labelled cleanup complete. |
| Definite failure | State the failed action, field/error and retry eligibility; keep valid same-owner nonsecret inputs. Do not change the prior committed projection. |
| Unknown outcome | Show “처리 결과 확인 중” with safe original operation reference and a reconciliation action. Do not create a second command as retry or claim saved/failed. |
| Conflict | Preserve local input and show the newly authorized snapshot after explicit read; user chooses reload or deliberate reapply with a new intended command and correct revision. No automatic overwrite. |
| Expired/unauthorized | Clear private render state and transient secrets, retain safe navigation context, then show sign-in. No automatic replay after return. |
| Policy/provider unavailable | Name the affected capability and safe alternative, such as manual interests or retry later. Keep the retained feature visible as unavailable; do not claim parity. |
| Complete cleanup | Show only after every required scope is evidenced. Pending/blocked evidence remains inspectable only through its authorized flow. |

Account switching destroys old-owner component state and cache entries before any new-owner screen renders. Responses from pending old-owner calls cannot repopulate them. Explicitly submitted work may finish durably under its recorded policy, but the new owner cannot inspect its result. Browser restart triggers fresh authentication and authorized reads of acknowledged records; an old route is not authority.

## Form validation and sensitive interactions

1. Server policies provide finite limits and retained vocabularies before enabling submission. Client checks mirror them for usability; authoritative checks always run at the owner boundary. Preserve valid Korean/Unicode input, reject malformed/oversized values and distinguish optional null from an empty value that violates a field's policy.
2. Show inline errors linked to fields and a focusable error summary when multiple fields fail. Profile forms use typed retained definitions; reject duplicate/unknown field IDs and stale vocabulary revisions. Settings require at least one actual named change and retained action/language/level/filter values.
3. Credential and proof fields use appropriate labels and autocomplete semantics, allow password managers and paste, and avoid cognitive authentication obstacles. Do not persist these values as drafts. Clear them after completion, expiry, navigation, logout and owner switch.
4. Sensitive actions show the exact scope before confirmation: remove one save; clear history; delete behavior; reset derived profile; withdraw; erase; revoke an entitlement. Confirmation does not replace current proof, authority, server policy or revision checks.
5. MFA material appears only in its protected transient panel. Render QR locally; never send the seed to an image/analytics service. Leaving the panel clears it. If retrieval was lost or expired, guide a new enrollment rather than offering “show again.” Recovery remains unavailable until its controlled policy is approved.
6. Consent text separates a prospective processing decision from deletion/reset of existing retained data. An unsaved toggle does not show processing as already revoked. Acknowledged revocation can show cleanup pending while future processing is already blocked.

## Navigation, appearance and accessibility

- Preserve the reading workspace and safe search context when opening account/settings/library panels. Group related controls with clear headings and stable placement; reveal advanced destructive actions deliberately. Do not nest entire authentication or admin applications inside the reader.
- Desktop layouts favor readable grouped forms and list/detail context. On phones/tablets, reflow the same capabilities into one readable column with reachable primary actions, wrapping labels and no content overlap at text zoom. Wide quota/admin records use an accessible labelled layout rather than clipped columns.
- Use inherited blue accents `#2f6df6` (light) and `#5b8bff` (dark), existing neutral surfaces and verified accessible variants from the approved design mapping. Use status text/icon as well as color. Light/Dark/System follows acknowledged settings; temporary preview is labelled unsaved if persistence fails.
- Maintain logical headings, landmarks, labels and focus order. Dialogs keep focus within their interaction and restore focus to their trigger; route changes focus an appropriate heading. Status messages use nonintrusive live announcements; urgent field failures are associated with the control.
- Provide visible focus, sufficient target size, keyboard equivalents, reduced-motion behavior and announced pagination/result changes. Maintain query and filter controls throughout loading/error/empty search recovery. A provider popup/callback failure returns focus and a usable fallback without a redirect loop.

## Review and later verification boundary

Review screens for registration/recovery/MFA, settings/consent, lifecycle progress/reactivation, library/history, personalization reset, plan and admin allocation in loading, empty, saved, failure, unknown, conflict and expired states. Execute keyboard, focus, Korean long-text, narrow screen, zoom and appearance checks against the implemented UI. Include cross-account back navigation, late responses, lost-write acknowledgements, clear/reset races and secret-display expiry. All 20 product capability groups remain release obligations; these U2 components alone do not prove the complete product or accessibility conformance.
