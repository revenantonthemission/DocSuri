# U1 security, privacy and accessible authentication design

Date: 2026-10-11. Unit: `u1-integrated-paper-journey`. Status: logical design from the [confirmed proposal](nfr-design-questions.md);
canonical amendments, implementation and executable evidence remain pending.

## Scope, authority and traceability

This design specifies how to meet the [security requirements](../nfr-requirements/security-requirements.md) within the approved shared application and
separately controlled operator tool. Existing anonymous search remains available under its declared source/admission rules; U1 adds no wider
guest reading, assistance or private access. One maintainer, $0 free/local operation and full eventual parity remain constraints. Framework,
store, host, recipient location and numeric operating policies remain unselected. An unresolved protection disables the affected operation,
without closing parity.

| Requirement | Solution | Primary mechanism and verification |
|---|---|---|
| NFR4.1 | SEC01 | Opaque current sessions and atomic proof consumption; SEC-01 |
| NFR4.2 | SEC02 | Owner-specific boundary manifest and ordered permission guard; SEC-02 |
| NFR4.3 | SEC03 | Typed acceptance, constrained rendering and fetch adapters; SEC-03 |
| NFR4.4 | SEC04 | Trusted execution claims and authority-ordered publication; SEC-04 |
| NFR4.5 | SEC05 | Separate secret stores, credential types and privileged scopes; SEC-05 |
| NFR4.6 | SEC06 | Origin/CSRF binding and finite admission before costly work; SEC-06 |
| NFR5.1 | SEC07 | Purpose-specific evidence register and source withdrawal; SEC-07 |
| NFR5.2 | SEC08 | Owner lifecycle acknowledgements and restricted restore; SEC-08 |
| NFR5.3 | SEC09 | Private presentation epochs and policy-gated recovery storage; SEC-09 |
| NFR6.3 | SEC10 | Accessible Korean authentication and explicit safe return; SEC-10 |

SEC-01–SEC-10 are the upstream local verification cases; SEC01–SEC10 name solutions here. None is a passed test. Related performance,
reliability, capacity and observation mechanisms retain their primary mappings in their own documents.

## Authentication and authorization architecture

### SEC01 — Opaque sessions and atomic identity proofs

AccountAccess stores an ordinary account, credential verifier, challenge and session as distinct records. Registration rejects
caller-selected role, owner, verification, tier or expiry. Login checks the credential verifier and current verification/lifecycle before
creating a random opaque session; its server record binds account, authority revision, authentication strength and finite expiry. Every
protected request resolves that current record. A signed stale identity snapshot cannot substitute for this lookup. Rotation invalidates the
old session and anonymous bootstrap binding; failed logout hides local content but retains an explicit unknown server-revocation outcome
until reconciled.

The browser receives only a protected host-bound cookie: Secure, HttpOnly, Path=/, no Domain, with an explicit SameSite policy tested
against retained identity callbacks. The `__Host-` naming constraint is a candidate binding for the eventual canonical cookie name. Only the
trusted response adapter issues or clears it; no session token enters JSON, URLs, browser-readable storage or SSE cursors. Cookie settings
complement SEC06, and do not replace it. [OWASP session
guidance](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html).

Challenges bind exact account/address, purpose, authority revision, expiry and verifier. A single owner transaction compares
unused/current/unexpired proof, records consumption and the intended identity transition, and persists its safe receipt. Concurrent use has
one winner; a proof never becomes a login session by itself. Delivery acknowledgement cannot verify an account. Resend/reset entry uses
equivalent public response shape and a bounded delivery obligation, without disclosing existence; timing and abuse behavior are checked as
well as text. Tradeoff: durable lookup/receipt work buys revocation and replay correctness. **Verify:** SEC-01 concurrent consumption, wrong
bindings, stale session and lost acknowledgement, with permitted A/B controls. Finite proof/session policy and real free public delivery
evidence precede public enablement.

### SEC02 — One boundary manifest and current owner guards

The trusted C13 adapter validates schemas, strips/rejects authority assertions, and creates internal context from AccountAccess. Every owner
then validates its own resource and operation; adapter authentication alone never authorizes it. Startup compares the mounted operation
manifest against access declarations and rejects unclassified mounts. Internal C14 methods have no generic browser route.

| Boundary and owner | Required enforcement before release or commit |
|---|---|
| Entry/session — AccountAccess | Declared public or current account flow; purpose-bound proof is separate |
| Search — Discovery with CorpusContent | Declared anonymous/current-owner context, current source eligibility; no private history in anonymous results |
| Content/assets — CorpusContent | Exact paper/version/asset registry and read purpose; check before bytes leave protected delivery |
| Saves/history — Library; defaults — Personalization; own usage — UsageEntitlements | Owner predicates on lists and direct IDs; current account, revision and idempotent intent on writes/replays |
| Options/jobs/history/result/SSE — PaperAssistance | Current owner and source purpose at list/read, every emitted snapshot and result delivery; generic wrappers call the same owner |
| Worker payload/facts — PaperAssistance | SEC04 authenticated claim plus current authority, including failure/progress paths |
| Observation/recovery — ServiceOperations and effect owner | Separate observation permission from the owner's recovery command; no direct repair writes |

List queries apply owner predicates before pagination and projection. Cursor validation binds owner, query/filter, snapshot and contract
version; tampering, expiry or swapping cannot select another scope. Foreign and absent private IDs share the safe external not-found
disposition, including replay/asset errors. Private responses are no-store, and private caches are never shared authority. Current
revocation/withdrawal and effect commitment use SEC04's shared ordering capability. Live delivery revalidates each bounded release; cache
invalidation is only cleanup. Already delivered bytes cannot be recalled. Tradeoff: repeated checks increase dependency cost; unavailable
authority fails the protected path closed. **Verify:** SEC-02 expands every mounted route/alias/module operation across
A/B/anonymous/unverified/revoked/admin and positive permitted controls.

## Input validation, safe rendering and security headers

### SEC03 — Constrained data, renderer and destination adapters

HTTP and domain adapters validate bounded structure, enums and unknown fields before allocation or expensive parsing; owners validate
referenced identity, version and purpose after parsing. Database parameters and opaque object handles carry data, never query fragments or
filesystem paths. Finite body/depth/string/ asset/decompression policies must be configured before accepting each format. CorpusContent
resolves asset handles only through its exact content catalogue; normalization, traversal/symlink checks and protected root binding precede
I/O.

WebWorkspace renders paper/model output through a constrained document tree with escaped text and allowlisted formatting, safe math fallback
and no raw active HTML. Validated source citations bind exact read versions. Model output has no tools, credentials, owner selection or
permission channel; output claiming a new URL/action does not invoke it. Links use an allowed scheme/destination policy, safe
external-window isolation and an explicit source label. Return navigation accepts registered local destinations, never an arbitrary redirect
string.

Only a source/provider adapter performs server fetches. It constructs destinations from an approved provider profile; resolves and validates
network destinations, rejects private/loopback/link-local/metadata targets, rechecks every redirect and connection address, bounds
bytes/time, and sends credentials only to their bound recipient. User/model URLs cannot bypass this path. The response adapter uses an
explicit CSP for scripts/styles/connect/images, prevents framing, disables MIME sniffing and suppresses sensitive referrers. Final
directives depend on actual mounted resources and are tested before enabling them. Tradeoff: unsupported markup/destinations produce a
truthful partial/source-only view. **Verify:** SEC-03 observes DOM, network and effects for hostile content, DNS/redirect/path abuse and
version swaps alongside safe Korean/text/math cases.

## Trusted execution and encryption design

### SEC04 — Fenced execution with ordered permission barriers

PaperAssistance authenticates executor credentials independently from browser sessions and binds every claim to worker, operation/kind,
immutable input digest, payload descriptor, lease, owner-time expiry and increasing fence. Claim grant, renewal/replacement and new
progress/failure/success facts use owner atomic comparison; lease revision is separate from business revision/sequence. Workers propose
facts, while PaperAssistance allocates authoritative state and receipts. Exact committed fact replay requires current receipt-read
permission and yields no new effect. C06 direct and C14 transported facts share this validator.

AccountAccess and CorpusContent exclusively mutate their authority/consent and purpose-eligibility revisions. Their typed guard participants
and the protected effect owner must share an enforceable serialization capability: acquire guards in deterministic scope order, read current
authority, validate the active claim, then commit the owner effect and receipt before releasing guards. Revocation and withdrawal take the
same guards exclusively and advance their own barriers. The adapter must prove one ordered transaction/critical section covering guard
validation and effect commit, including crash behavior. A process-local mutex alone across independent workers, asynchronous epoch
propagation or a checked boolean followed by a separate write cannot satisfy this condition. No physical cross-store transaction is assumed;
an adapter without an equivalent proved protocol is ineligible for that protected path.

Payload release and processing dispatch require an ordered grant under current permission. Expensive inference runs outside the short guard;
publication reacquires it and rechecks claim, account/consent/source and immutable output binding. If revocation wins, no subsequent
protected publication occurs. Already permitted handoff may be unrecallable: provider enablement requires an explicit in-flight policy for
bounded interruption, suppression, disposal and recipient retention; the design promises neither instantaneous compute cancellation nor
recalled bytes. Staged results remain inaccessible until the committed binding exists. The winning completion stores result/outcome plus a
durable settlement obligation; UsageEntitlements consumes its unique reservation under the resolved winning-order policy. Recovery of that
recorded obligation cannot manufacture new debit authority. Tradeoff: short serialization reduces races but adds contention/availability
dependency. **Verify:** SEC-04 pauses before dispatch/commit, exercises both race orders, replacement, crashes and stale
success/failure/progress, and observes one valid result/accounting effect. Canonical guard/claim/settlement coordination precedes code;
unknown ordering fails closed and leaves the finding open.

### SEC05 — Separate secrets and privileged authority

AccountAccess uses a maintained password-verifier adapter with unique salts, versioned algorithm/work parameters and constant-time
verification. Passwords are never recoverably encrypted or logged; artifact SHA-256 is not a password verifier. Argon2id is an evaluation
candidate, with library identity and bounded concurrent cost measured before selecting a profile against current guidance. Opaque
session/proof secrets use cryptographic randomness and protected keyed verifiers; raw reusable secrets are absent from routine records and
telemetry. [OWASP password storage](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html).

Recoverable adapter keys live behind an owner-scoped secret provider, outside repositories/client builds. Storage encrypts secret material
and protected backup copies with separately controlled key references, versioned authenticated encryption profiles and an explicit
recovery/rotation procedure. Algorithm, library, key custody, storage location and backup access must be selected and tested before
handling; this does not select a hosted key service. Trusted transport protects browser/public and networked internal hops with
authenticated endpoints; plaintext local IPC requires a proved access boundary, not an assumed trusted network. TLS/certificate/proxy
configuration remains deployment evidence.

Credential types are non-interchangeable: ordinary account, authorized service administrator with required MFA, trusted executor, and
independent PlatformControl operator. ServiceOperations observation grants none of their write permissions. Tradeoff: rotation/recovery adds
procedures for one maintainer but avoids shared omnipotent tokens. **Verify:** SEC-05 synthetic secret canaries across responses,
logs/builds/exports/backups, credential substitution and revoked-key attempts; missing privileged U2/U7 operations stay unavailable until
fully protected.

### SEC06 — Request integrity and admission before expensive work

Session bootstrap supplies a CSRF token bound to the current session or anonymous pre-authentication context. Every browser POST, including
login/registration and POST queries, requires that token plus exact configured Origin. Missing/null/ foreign Origin fails this canonical
browser path; trusted proxy configuration cannot be inferred from caller headers. Session rotation changes the binding. No credentialed
wildcard CORS exception or GET mutation is introduced. [OWASP CSRF
guidance](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html).

AccountAccess bounds authentication/delivery attempts before expensive verifier work; Discovery bounds anonymous query cost; PaperAssistance
and UsageEntitlements coordinate bounded admission through the owner-local atomic holds and reservations in SC02 before acceptance or inference. Trusted network context and owner identity form
policy keys; client rate headers/tier do not. Bound body parsing, concurrent KDF/model tasks, queue age/length, result size, retry budget
and storage reservation; retain recovery capacity. Policy absence returns unavailable, exhaustion returns the canonical safe admission
disposition with retry information only when known. Tradeoff: strict limits can reduce availability; baseline and human-agreed targets tune
them without paid fallback. **Verify:** SEC-06 cross-context CSRF replay and concurrent limit boundaries; read/reconnect/history paths never
create jobs, claims or usage debits.

## Privacy, lifecycle and compliance controls

### SEC07 — Purpose evidence follows every derived copy

Each owner registers classification, provenance/source version, owner/scope, permitted uses, recipient/location, policy revision and
derived-copy references before storage/display/translation/model transfer. CorpusContent owns source eligibility and projection withdrawal;
PaperAssistance owns payload/result and initial empty glossary plus its non-null immutable snapshot revision; Personalization owns
assistance defaults only. Library owns saved references. Unknown rights or orphan owner mappings stay quarantined from serving/processing.
Policy changes advance SEC04 barriers; cache/index/result reads consult current eligibility even while cleanup is pending. Tradeoff:
retaining only permitted reference metadata preserves history without re-serving restricted content. **Verify:** SEC-07 traces source →
projection → payload → result → telemetry/ backup, including wrong-purpose/missing permission and withdrawn-source controls.
Recipient/location, actual permission and applicable obligations remain evidence items; public accessibility and this design are no
legal/compliance conclusion.

### SEC08 — Lifecycle receipts and restoration under current restrictions

Before first sensitive persistence, composition registers every installed owner in AccountAccess's applicable lifecycle manifest with
per-class retention, derived-copy/cache/queue/telemetry/backup treatment and policy revision. Revocation first closes current access/effect
barriers; each owner then durably acknowledges its own logical removal, erasure or retained restriction. Missing/failed owners keep
completion pending. History clear advances Library's generation atomically with its receipt, so late pre-clear facts cannot recreate history
or erase saves.

Restore runs isolated with dispatch/network effects disabled. Recover authoritative current revocation/deletion/policy barriers separately
from the older snapshot, reconcile every restored primary/derived artifact and queued obligation, validate owner/source relationships, and
rebuild only eligible projections before serving. If current restrictions cannot be established, the restored system stays closed. Tradeoff:
backup existence is insufficient; closure requires a reconciliation manifest and owner evidence. **Verify:** SEC-08 old facts, withheld
results, missing participants and restore races; demonstrate retained versus erased dispositions without claiming revoked access equals
physical erasure. Retention periods, key recovery and real-user continuity require evidence and human policy; this design authorizes no
reset, live restore or migration.

### SEC09 — Presentation epochs and policy-gated private recovery

WebWorkspace changes its presentation epoch on expiry/logout/account switch, removes private DOM/accessibility/view/cache state, clears
pending private form data and closes subscriptions. All asynchronous results/events bind owner/session epoch and exact resource; stale
callbacks cannot render or write into a new epoch. Cross-tab notification helps clear views, but fresh server session validation controls
entry and Back/page restoration before private display. A transport that misses the notification still fails current owner checks. Private
service-worker or browser persistence is disabled absent its own resolved policy.

U1 recovery persists no private payload, credential or pending private intent in browser storage until owner binding, retention/discard,
shared-device residuals and authenticated access have approved evidence. This is an evidence block, not a permissive localStorage fallback.
Volatile uncertain operations reconcile their original identity; a fresh authorized return uses server Library and canonically amended
retained-assistance history reads. Those reads never resubmit work. Tradeoff: unsent local input may be lost, and is never labeled saved.
Durable research drafts remain U4. **Verify:** SEC-09 delayed A data after B login, Back/restoration, multi-tab, failed logout and
fresh-browser own-result rediscovery.

### SEC10 — Accessible authentication with safe navigation return

AccountEntry uses Korean labels, native email/password autocomplete, paste and password-manager support. Linked field errors and one focused
summary follow failed submission; status/delivery/rate-limit announcements remain bounded. Sign-in expiry removes private previews and
focuses the neutral entry heading. Successful login revalidates an allowed local paper/query destination and reads current data; it cannot
replay a save/job. Unknown logout/delivery stays explicit.

Preserve inherited blue/neutral tokens (`#2f6df6` light, `#5b8bff` dark), Korean system typography and Apple HIG web hierarchy.
Light/Dark/System remain selectable and follow OS changes without resetting forms/focus. SEC-10 checks keyboard and assistive-technology
success/error/recovery paths, visible unobscured focus, 320 CSS-pixel reflow, 200% text resizing, 4.5:1 normal/3:1 large-text contrast and
3:1 required control/state boundaries. The approved 44px control preference and WCAG 2.2's applicable 24px target/spacing exceptions receive
separate checks. Provide an accessible alternative/assistance for any cognitive authentication challenge; do not disable credential aids.
These criteria derive from [WCAG 2.2](https://www.w3.org/TR/WCAG22/) and the approved frontend design. Tradeoff: neutral security messaging
still needs actionable Korean recovery. Rendered/manual evidence and actual identity adapters are required; design or automated scans alone
do not establish conformance.

## Assumptions, open choices and implementation handoff

C00/C02/C03/C06/C13/C14 must coordinate browser revision, claim/payload/history and the new internal ordered-guard capability before
affected code. Specify participant ownership, lock/transaction order, timeout/failure dispositions, worker credentials, settlement
eligibility and later consumers in the canonical revision; this document creates no callable public API or parallel wire version. Adapter
selection must demonstrate current authority under concurrent revocation, including list/asset/SSE release and work dispatch/publication.
Canonical changes and executable closure of Contract R-01/R-03 and LC07 remain open.

AccountAccess owns identity/secret policy; source/model owners establish permitted uses and in-flight handling; each data owner supplies
lifecycle/retention evidence; ServiceOperations establishes free/local transport/storage capacity and isolated restore fitness. Actual
finite values precede experiments/enablement; numeric service-quality targets follow measured baseline and human agreement. No installed
library, cached model or workstation is thereby selected hosting. An evidenced $0/quality/full-parity conflict returns to the human without
a paid fallback.

Verification records must name versions, policy revisions, permitted synthetic fixtures, race order, positive/negative controls, observed
bytes/effects and redacted evidence. Document checks do not prove runtime isolation, encryption, restore or accessibility. Parent-stage
review and the separately approved exact runnable completion command remain the later completion evidence.

## Sources

- [Security requirements](../nfr-requirements/security-requirements.md) and
  [technology decisions](../nfr-requirements/tech-stack-decisions.md).
- [Functional specification](../functional-design/functional-spec.md),
  [rules](../functional-design/rules.md), [entities](../functional-design/entities.md),
  [frontend specification](../functional-design/frontend-components.md) and
  [contract coordination](../functional-design/contract-revision-plan.md).
- [Component ownership](../../../inception/domain-design/components.md) and
  [canonical contracts](../../../inception/contract-design/contract-summary.md),
  particularly C00/C02/C03/C06/C13/C14. Their ownership corrects the prior
  technology record's glossary attribution without editing that historical input.
- Primary OWASP and W3C references linked at the relevant decisions were consulted
  2026-10-11. They guide bounded design/verification, not compliance certification
  or evidence that an unselected implementation satisfies these controls.
