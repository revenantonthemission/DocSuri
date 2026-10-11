# DocSuri v2 — Requirements

Date: 2026-10-11 (Asia/Seoul). Basis: the user's confirmed requirements answers and consolidated summary, together with the approved intent, scope and reverse-engineering reference. [RQ] [IC] [SC] [BO]

## Intent analysis

Rebuild DocSuri so researchers and engineers can reliably find a paper, understand it, save it and return to it later. Stable, smooth use and code that one human maintainer can understand and repair are the priorities. The first v2 release retains **all current product capabilities**, including operational capabilities; new feature expansion is deferred. The paper journey is the first complete demonstration, followed by evidence for the rest of the capability set. It is not a reduced release boundary. [IC] [SC]

This is a system-wide brownfield rebuild with substantial discovery dependencies. Requirements Analysis uses the approved Standard depth. The current reference identifies 20 capability groups across the browser, service, jobs, ingestion and operations. It is repository-wide in breadth, with deeper inspection of selected paths; it does not prove every sub-behavior or deployed capability. Continue reconciling shallow, disabled, broken and disputed paths before declaring full parity. The requirements below specify observable outcomes rather than preserving the current implementation or defects. [BO] [AR] [CS] [CQ]

The service must support public registration and multiple users, personal accounts, private saved work and administrator boundaries. No count of actual users, observed demand, market validation, authoritative deployment or recoverable production backup is established here. Public registration is a product requirement, not permission to deploy or spend. The user remains the sole scope and priority approver. [RQ] [CR]

### Actors and acceptance conventions

| Actor / context | Required boundary |
| --- | --- |
| Visitor / prospective researcher | Can reach registration and relevant entry information; anonymous access to other surfaces must be explicitly defined during design |
| Registered researcher or engineer | Can use the retained capabilities with the correct account, saved work, preferences and private material |
| Another registered user | Cannot enumerate, read, change or export the first user's private resources, including through guessed identifiers or indirect links |
| Administrator / operator | Can perform authorized administration and operational procedures; ordinary account status does not grant these powers |
| Human maintainer supported by agents | Can reproduce setup, trace behavior, diagnose a fault, repair it and verify recovery within the approved free/local operating model |

All FR and NFR items are **Must** for first-release acceptance under the current scope. Their IDs are permanent traceability keys; preserve them when splitting work, adding tests or revising wording. Subrequirements have their own stable IDs. Each numbered criterion describes a check, not a claim that it has passed. Later design may decompose it further without dropping the outcome. External-provider failures require truthful recovery behavior, but a mocked adapter or permanently unavailable feature does not establish normal-path parity. [SC] [BL]

Use isolated synthetic accounts A and B, an administrator account, controlled fixtures and non-production fault injection. Record the build, configuration, fixture identities, expected/observed outcome and retained evidence. Exercise actual mounted boundaries through the browser where applicable; separately cover API and operational interfaces. A mock-only pass cannot substitute for the integration evidence needed by that capability. Do not access real user data or send real exports/emails merely to prepare this specification.

## Functional requirements

### FR1 — Find and refine papers

Source: CAP-01; IB-01, IB-07, IB-08. [BO] [BL]

- **FR1.1:** Accept a research query, return relevant paper metadata and stable paper identities, and support the current filters, refinement, ordering and rerun behavior. Acceptance: a documented fixture query locates its expected paper; changing each retained filter changes only the intended result scope; reopening a result resolves the same identified paper/version.
- **FR1.2:** Preserve the current lexical and semantic discovery outcomes and explicit degradation behavior without selecting a search engine or embedding provider here. Acceptance: reference relevance cases exercise both supported modes; unavailable semantic resources produce a disclosed supported fallback or actionable unavailability, never a fabricated normal semantic result.
- **FR1.3:** Distinguish loading, no match, invalid input, partial/degraded results and retrieval failure. Acceptance: empty, whitespace, Unicode, punctuation and oversized queries have defined server-validated outcomes; timeout/index failure does not appear as a successful empty search; retry preserves the query and filters. Pagination and stable ordering do not silently duplicate or omit fixture results while the underlying snapshot is unchanged; changing data is identified rather than presented as a stable snapshot.

### FR2 — Read paper content and sources

Source: CAP-02; IB-07, IB-08. [BO] [AR]

- **FR2.1:** Present available structured full text, figures, anchors and source links associated with the selected paper and version. Acceptance: fixture section and figure links resolve to the intended content; navigating away and back does not substitute another paper or version; a source-only paper remains distinguishable from one with readable full text.
- **FR2.2:** Represent absent, building, unsupported, failed, withdrawn and access-restricted content truthfully, retaining useful authorized metadata/source links when available. Acceptance: missing assets or malformed document models produce bounded errors and usable navigation; unsupported content does not trigger endless loading or invented text. Content availability and source permissions are checked before display or processing under NFR5.
- **FR2.3:** Keep private uploaded documents and their assets bound to the owner and permitted research context. Acceptance: A's private document, figure and download links fail safely for B, an unauthenticated session and a revoked session; private identifiers cannot be resolved via public corpus routes; malformed paths, traversal and unsafe rendered content cannot escape the permitted document scope.

### FR3 — Understand papers with summary and translation jobs

Source: CAP-03; Q-01–Q-04; IB-07, IB-08. [BO] [CQ]

- **FR3.1:** Preserve summary, translation and supported presentation-level choices for eligible paper content. Acceptance: each current action and level has a reference case showing usable output tied to paper/version, requested operation and language; missing content, unsupported requests or unavailable models produce an explicit reason and safe retry or alternative. No successful answer is fabricated when no result exists.
- **FR3.2:** Accept asynchronous work only with recoverable responsibility for dispatch and execution. Acceptance: duplicate submission or retry after a lost response resolves the same intended job/effect; queue outage, crash between durable acceptance and dispatch, and worker restart either recover that work or expose a terminal actionable failure. An accepted job must not silently remain abandoned. Completion and quota effects are not duplicated by redelivery.
- **FR3.3:** Expose coherent ordered progress and terminal states through the supported browser/service transport. Acceptance: the actual mounted service and browser agree on state/event identity and ordering; reconnect after a known event recovers missed progress without regressing terminal state; stale, repeated or out-of-order events do not corrupt the view. A sleeping tab, interrupted stream and status polling recover the same authoritative job state. Do not prescribe an old sequence field or wire format as the only possible design.
- **FR3.4:** Return a usable prepared result with correct owner, operation and paper/version binding. Acceptance: result reads distinguish pending, completed, expired, failed and unauthorized cases; completed result retrieval does not regenerate work; refresh/revisit returns the same result while retained; expiry explains how to request again without claiming it is still available. Actual browser-to-service-to-worker-to-result checks cover the four known integration defects listed below.

### FR4 — Maintain terminology preferences

Source: CAP-04. [BO]

- **FR4.1:** Preserve supported glossary inspection and updates, associated with the authenticated owner and used by the relevant understanding actions. Acceptance: a saved term/preference survives reopening and affects a controlled eligible output; B cannot read or modify A's glossary.
- **FR4.2:** Validate empty, duplicate, Unicode, conflicting and oversized terms according to documented normalization and update rules. Acceptance: a failed write leaves the previous committed glossary usable and reports failure; repeated submission has the documented single intended effect; concurrent edits are resolved visibly rather than silently erasing committed preferences.

### FR5 — Save papers and searches; revisit history

Source: CAP-05; IB-07, IB-08. [BO] [AR]

- **FR5.1:** Preserve current add/list/remove behavior for saved papers and saved searches, with stable owner and paper/query identity. Acceptance: saving a fixture paper and a refined query survives reload and a new login; repeated saves do not create unintended duplicate entries; a failed persistence operation is not shown as a confirmed saved state.
- **FR5.2:** Preserve history inspection, clear operations and rerun behavior. Acceptance: a qualifying authenticated search can be found and rerun with its recorded query/refinements; empty and paginated histories behave consistently; clearing A's history affects only A and does not unintentionally delete saved papers or searches. Failed clear operations report the actual remaining state.
- **FR5.3:** Revisit stored work even when source availability changes. Acceptance: withdrawn/unavailable papers and renamed or canonicalized identifiers have an explicit disposition; saved references are not silently redirected to unrelated content or lost. Read, write, list and delete paths reject cross-owner access; simultaneous tabs converge to the committed state after refresh.

### FR6 — Register and manage the account lifecycle

Source: CAP-06; public-registration answer. [BO] [RQ]

- **FR6.1:** Support public registration, email verification, login and logout. Acceptance: a new eligible synthetic account completes the journey; duplicate or malformed registration and unverified access follow documented rules; failed email delivery exposes a recoverable state; expired/used verification links fail safely. Responses must not disclose another person's private account information.
- **FR6.2:** Preserve password reset/change and email-change flows with required identity verification. Acceptance: valid changes succeed, expired/replayed tokens do not; interrupted changes leave a recoverable authoritative identity; old and new credentials/sessions behave according to the documented revocation policy. Reauthentication must not lose already committed saved work.
- **FR6.3:** Preserve account deletion/withdrawal and reactivation outcomes within a defined retention and recovery policy. Acceptance: the user can understand and confirm the operation; access is revoked when required; related saved/private data is handled consistently; reactivation restores only data that the approved policy lawfully and technically retains. Permanent erasure must not be represented as reversible. The retention periods and existing-data treatment remain open under O-03/O-04; do not invent them here.
- **FR6.4:** Apply server-side validation, abuse controls and protected session handling to public authentication flows. Acceptance: repeated invalid/automated requests reach the configured bounded response, forged identity/session requests fail, and a logged-out or revoked session cannot regain protected access by replaying a browser request. Numeric rate limits are chosen from evidence, not an assumed traffic count.

### FR7 — Link external identities and protect administration

Source: CAP-07. [BO]

- **FR7.1:** Preserve Google and ORCID account-linking/sign-in behavior and ORCID profile access where supported in the current reference. Acceptance: valid provider responses bind to the intended local account; identity collisions, denied consent, invalid callback state and replay are rejected; unavailable/revoked providers produce a recoverable outcome without silently creating a different account. Retain existing unlink behavior where present and verify its effects during parity reconciliation.
- **FR7.2:** Preserve administrator MFA and authorization boundaries. Acceptance: ordinary users and an administrator missing required MFA cannot exercise protected administration; expired/replayed second factors fail; legitimate authorized access works. Loss/recovery of administrative access has a documented controlled procedure before release, rather than a production bypass.

### FR8 — Manage account profile, consent and subscription presentation

Source: CAP-08. [BO]

- **FR8.1:** Preserve profile and consent inspection/update behavior with durable owner isolation. Acceptance: a changed value survives a new session; invalid input and storage failure are explicit; withdrawal of a consent changes the affected future processing according to the documented policy without changing another user's state.
- **FR8.2:** Preserve existing subscription/plan presentation without implying real payment processing. Acceptance: displayed status matches the configured mock or administrative assignment; mock data is recognizable in the appropriate environment; no screen claims a charge, paid entitlement or successful purchase that did not occur. Real billing is outside this release's retained capability reference.

### FR9 — Explore citations and save references

Source: CAP-09. [BO]

- **FR9.1:** Preserve citation relationship exploration and saving of eligible referenced papers into the owner's library. Acceptance: a bounded fixture graph shows the correct cited/citing identities and prevents cycles or duplicate nodes from creating unbounded traversal; eligible saves resolve the intended paper; ineligible nodes explain the limitation.
- **FR9.2:** Handle provider limits, incomplete metadata, unknown references and stale/unavailable graph data explicitly. Acceptance: partial data is labeled, repeat requests use the documented freshness behavior, and a provider failure permits recovery without erasing an already saved reference or fabricating relationships. Node/depth limits remain configurable and tested at their chosen boundaries.

### FR10 — Personalize with user control

Source: CAP-10. [BO]

- **FR10.1:** Preserve search/summary defaults and recent-paper views. Acceptance: supported settings persist and affect the appropriate subsequent action; recent paper identity and ordering match controlled activity; missing enrichment or cold-start profiles have a usable default and disclosed degradation where needed.
- **FR10.2:** Preserve opt-out, deletion of behavior events and profile reset. Acceptance: opt-out prevents the future behavior processing it governs; reset and delete affect the intended owner data/projections and do not unexpectedly delete the library; retry and delayed events do not silently recreate erased or prohibited personalization. The data-handling policy must define the deletion boundary before implementation acceptance.

### FR11 — Complete or skip onboarding

Source: CAP-11. [BO]

- **FR11.1:** Preserve interest selection, skip and stored onboarding state. Acceptance: a new user can complete or skip onboarding, return after interruption and reach the normal service without a redirect loop; revisiting does not overwrite established preferences unexpectedly.
- **FR11.2:** Preserve optional ORCID-derived suggestions. Acceptance: linked eligible data yields attributable suggestions; missing profile, denied authorization or provider failure permits manual selection/skip and does not prevent account or core paper use.

### FR12 — Follow topics and receive controlled digests

Source: CAP-12. [BO] [AR]

- **FR12.1:** Preserve topic follow/unfollow and digest configuration. Acceptance: repeated follow requests do not create unintended duplicates; changes persist for the owner; empty, Unicode and invalid topic inputs have defined outcomes; another user cannot change the subscription.
- **FR12.2:** Preserve digest preparation, delivery and unsubscribe behavior. Acceptance: controlled scheduling/time-zone/clock cases select the intended content window, including no-new-content cases; retries and crash recovery reconcile send state to avoid unintended repeated deliveries; delivery failure is visible to operations. An unsubscribe or applicable consent revocation prevents later eligible sends, including already queued work checked before dispatch. Public delivery feasibility remains dependent on a sustainable free/local email path; a local sink alone proves only the test path.

### FR13 — Ask grounded research questions

Source: CAP-13. [BO] [AR]

- **FR13.1:** Preserve research questions, claim comparison and quotation evidence across the supported document scopes. Acceptance: answers link claims to the intended accessible source/section; a literal quote can be verified against that source; disagreement and uncertainty are distinguished from established claims. With insufficient evidence, no corpus or unavailable model, return a meaningful abstention or partial result rather than invented support.
- **FR13.2:** Preserve attachments and supported web references with source distinctions. Acceptance: eligible text/PDF attachments can participate in the authorized research context; malformed, oversized, truncated, password-protected or unsupported files fail with a usable explanation and no partial public publication. Retrieved text and document instructions are untrusted evidence and cannot override owner permissions, secret handling or external-action approval. Optional web references must not be misrepresented as evidence the analysis actually read.
- **FR13.3:** Preserve useful structured output through extraction/model failure and context limits. Acceptance: malformed model output cannot become a false successful result; truncation/partial coverage is disclosed; interruption and retries preserve committed inputs and prevent duplicate accepted work according to FR14. Validate observable grounding on controlled positive, contradictory and insufficient-evidence fixtures.

### FR14 — Persist research sessions and pending work

Source: CAP-14. [BO] [AR]

- **FR14.1:** Preserve creating, saving, reopening and inspecting research sessions/messages and their progress/pending state. Acceptance: an interrupted session can be reopened with committed messages and authoritative pending/terminal status; a repeated request does not duplicate the intended turn; late worker completion is associated with the correct session and input.
- **FR14.2:** Preserve deletion of one or all owned sessions. Acceptance: A's deletion does not affect B, and deleted work cannot be reopened via a stale direct link. Pending jobs and late events follow the defined cancellation/tombstone/retention policy instead of recreating a deleted session. Failure to commit deletion is reported, with remaining state recoverable.

### FR15 — Analyze novelty and manage its jobs

Source: CAP-15. [BO]

- **FR15.1:** Preserve topic- and manuscript-based novelty analysis, result artifacts and discussion of results. Acceptance: both input modes produce inspectable, source-associated outcomes for eligible fixtures; missing or conflicting evidence and unsupported manuscript formats produce truthful limitations. Scores or generated claims must not be presented as proof of scientific novelty beyond their recorded evidence and method.
- **FR15.2:** Preserve job status, progress and cancellation. Acceptance: duplicate submission, worker restart and stream interruption recover authoritative status; cancellation and completion racing have one recorded outcome; after cancellation is acknowledged, late events do not resurrect the job or start an unapproved export. Artifacts and chat remain owner-scoped and follow declared retention/expiry behavior.

### FR16 — Preview and approve Notion export

Source: CAP-16. [BO] [AR]

- **FR16.1:** Preserve per-owner Notion connection and a preview of the intended novelty export. Acceptance: preview identifies destination and content; invalid/revoked credentials or disconnected state have a recoverable outcome; credentials never appear in client-visible content or normal logs and cannot be used by another owner.
- **FR16.2:** Execute an export only after the owner's explicit approval of the current preview/destination. Acceptance: changed preview content or destination invalidates the prior approval; retry, timeout after remote success and duplicate execution reconcile the export outcome without silently publishing multiple copies. Unknown remote outcome is reported as unknown until reconciled; preview/cancel/expired approval does not itself publish. Verify the retained integration within free terms before claiming parity; no paid fallback is authorized.

### FR17 — Inspect and administer quotas

Source: CAP-17. [BO]

- **FR17.1:** Preserve current plan/quota inspection and authorized tier grant/revoke operations. Acceptance: a user sees their applicable allocation/usage and an administrator can change it with an auditable outcome; unauthorized changes fail. Public users cannot choose an administrative entitlement by modifying request data.
- **FR17.2:** Enforce resource limits consistently across protected actions. Acceptance: boundary, exhausted, concurrent, retry and daily-reset/time-zone cases have documented accounting; unknown usage does not appear as zero; no double charge/debit occurs for the same intended effect; failures/retries apply the chosen refund/accounting rules visibly. Entitlement changes cannot activate paid resources under C-13. Values and reset semantics must be specified and checked before implementation acceptance.

### FR18 — Maintain the paper corpus and recover processing

Source: CAP-18. [BO] [AR]

- **FR18.1:** Preserve source ingestion, incremental refresh and rebuild, with metadata/full-text eligibility checks, canonical identity, version handling and deduplication. Acceptance: duplicate/reordered source records and reruns yield the intended current paper representation without unintended duplicate searchable chunks; malformed or incomplete source records are classified; a failed stage does not incorrectly advance completion or a source watermark.
- **FR18.2:** Preserve withdrawal/removal handling and coherent search/content state. Acceptance: a withdrawal fixture stops exposing affected content according to the approved policy, while existing saved references receive the explicit disposition in FR5.3; stale caches and indexes cannot silently defeat that decision. License/access changes trigger the required eligibility decision before further use.
- **FR18.3:** Preserve retry, dead-letter/reprocessing and recovery operations. Acceptance: interruption between object/control/index writes, partial batch failure, rate limits and index/model incompatibility leave inspectable state and a repeatable recovery path; rerun does not corrupt already committed records. Rebuild uses identified authoritative inputs and verified recovery procedures, not an assumption that the search index is the only data that matters.

### FR19 — Observe and operate the service

Source: CAP-19; Q-05–Q-07. [BO] [CQ]

- **FR19.1:** Preserve health, incident, cost/resource, grounding and reliability signals and their authorized operational views/actions. Acceptance: controlled dependency outage and job failure can be detected and traced to the affected capability without exposing private content; unknown or stale measurements are labeled rather than reported as healthy or zero-cost.
- **FR19.2:** Make readiness and degradation reflect actual retained capabilities. Acceptance: an optional module that fails to mount, a missing required store or an unavailable execution path is visible to maintainers and affected users; a green process check alone cannot claim complete service readiness. Recovery changes the reported state only after appropriate capability checks succeed.
- **FR19.3:** Preserve documented incident diagnosis and recovery operations with recorded outcomes. Acceptance: an operator can reproduce a controlled incident, identify affected work, recover it and verify service/user state; temporary telemetry failures do not silently erase required operational evidence or trigger unbounded resource use.

### FR20 — Preserve platform evidence and controlled operations

Source: CAP-20. [BO] [AR]

- **FR20.1:** Preserve platform evidence/compatibility assessment and authorized access to its results. Acceptance: a controlled fixture distinguishes current, stale, mismatched and missing evidence; restricted reads remain bounded and authenticated; evidence about platform state is not substituted for application journey readiness.
- **FR20.2:** Preserve controlled operational protocols, authority checks and durable outcome/receipt reconciliation. Acceptance: wrong actor/target, stale precondition or changed input is rejected before an unsafe effect; interrupted or duplicate execution has a recoverable recorded outcome; filesystem permission failure, disk exhaustion or lost connectivity cannot be reported as completed. Destructive/release effects require the applicable explicit operator authority. Actual protocol membership and compatibility are reconciled from the reference before claiming full parity; these requirements do not authorize running such operations now.

## Non-functional requirements

| ID | Requirement and observable acceptance | Measurement / closure |
| --- | --- | --- |
| NFR1 | **Complete-task correctness.** The anchor journey and all retained capabilities must pass traceable success, negative and recovery checks. Persisted state, ownership, output usefulness and cross-boundary transitions are verified together; isolated screens, source presence and mocked happy paths are insufficient. | Record attempted and successful complete runs with failure reasons and environment. Reconcile every CAP and sub-behavior to implementation and evidence under IB-01/08/09. Numeric success targets follow the baseline; unresolved required failures prevent a readiness claim. |
| NFR2 | **Responsiveness and smooth interaction.** Loading, progress, success, stale/degraded state and errors must be timely, distinct and understandable; users retain their committed work and can retry safely. No infinite loading, render feedback loop or repeated unintended submission. | Baseline time to usable search/content, input feedback, save acknowledgement, reopen and queued-job completion, with distributions, sample sizes and cold/warm conditions. Agree thresholds after measurement, then verify in the selected environment at representative and boundary load. |
| NFR3 | **Durability and interruption recovery.** Acknowledged persistent writes and accepted jobs have a defined recovery responsibility; interrupted multi-step writes cannot be presented as fully successful. Retries are bounded and idempotent for the intended effect. | Inject lost responses, offline/reconnect, sleep, restart, dependency outage, simultaneous edits and disk/store failure in non-production. Record retained/lost work, recovery steps/time and duplicate effects. Agree recovery objectives after authoritative inventory/baseline; restore drills must verify owner relationships and artifacts as well as row counts. |
| NFR4 | **Multi-user security.** Server-enforced authentication, owner isolation, administrator/MFA separation and revocation apply consistently to lists, search, direct reads, mutation, events, assets, downloads and exports. Inputs and rendered content are treated as untrusted; secrets stay in protected configuration/storage. | Cross-user/anonymous/revoked-session tests cover each applicable boundary; injection, unsafe URL/path, callback/session replay and untrusted-file cases cannot gain privilege or reveal private resources. Record authorization matrix and abuse-limit checks before public release. |
| NFR5 | **Privacy and content handling.** Classify public corpus, private uploads, accounts, behavior, operational evidence and credentials. Apply investigated source permissions, consent, retention/erasure and location requirements before selecting affected storage/hosting/processing. | Maintain the data/obligation register, provenance and ownership map; verify deletion, revocation and controlled restore, including caches, derived artifacts and queued work. Publicly accessible papers are not assumed to permit every storage, translation, model or redistribution use. Unresolved obligations block the affected choice, not unrelated analysis. |
| NFR6 | **Usability and accessibility.** Core and retained interactions support keyboard operation, meaningful labels/status/error announcements, visible focus, readable contrast, zoom/reflow and understandable errors. Destructive actions have clear scope/consequences and a deliberate confirmation. | Exercise the anchor journey and representative account, form, long-result, modal and job states with keyboard and assistive technology; preserve focus and committed context on errors/reauthentication. State a test matrix and measurable criteria during design; this document does not claim a certification or select a numeric conformance target without investigation. |
| NFR7 | **Repairability and reproducibility.** Keep module responsibilities, configuration authority, data ownership and contracts understandable. Provide reproducible setup and dependency/runtime versions, safe synthetic fixtures, diagnosis and recovery instructions, and an effective way to verify a repair. | From a clean checkout, one maintainer reproduces a representative defect, identifies its boundary, fixes it and demonstrates a regression check plus affected integration checks. Record setup/diagnosis/repair/verification time, manual steps and obstacles; agree targets after baseline. Existing contradictory runbooks and test counts must be rechecked. |
| NFR8 | **Sustainable $0 capacity.** Normal and failure operation must fit available local resources or verified sustainable free-service terms. Bound queues, uploads, retries, caches, model work and concurrency so public registration cannot silently activate billable overages or cause unbounded work. | Record hardware/storage/network needs, tested workload envelope, free quotas/terms and configuration preventing paid fallback. Exercise exhaustion/backpressure and recovery without false success, lost committed data or automatic purchases. Verify public registration, email, model, search, export and operator paths; local-only mocks do not prove public-service fit. |
| NFR9 | **Actionable, privacy-aware observability.** Link a user-visible failure to relevant service/job/dependency evidence using safe identifiers; distinguish observed values, estimates, unknowns and stale evidence. | An injected paper-job failure and operational incident can be traced end to end with timestamps and outcome classification. Logs/metrics omit credentials and unnecessary private text, have documented retention/access limits, and remain useful across retries and restarts. No particular telemetry vendor is selected. |
| NFR10 | **Contract and integration consistency.** Browser, service, workers, stored data and external adapters must agree on identity, states, errors and compatibility. Document supported contracts, bounded inputs, schema/version policy and failure semantics before implementing the boundary. | Execute real mounted contract/integration checks, including stream framing/reconnect, prepared results, dispatch and error mapping. Verify existing consumers before changing externally relied-on behavior; schema evolution and rollback/recovery follow the chosen continuity plan. Test doubles must be checked against the same contract. |

Numeric latency, throughput, concurrency, availability, recovery, retention and repair-time targets are **not selected** by this document. Baseline work must identify an authoritative environment (or explicitly label a reconstruction), hardware/configuration, dataset, workload, sample size, timing boundaries, failure categories and raw evidence. Report an unexecutable or failed baseline as such; do not replace it with assumed historical passing counts. The user agrees quantitative targets after that evidence. Required outcomes such as owner isolation, truthful status, full parity and zero planned spending already apply. [CR: C-04/C-05/C-13; BL: IB-02/04/05]

## Representative public-paper acceptance tasks

The user delegated selection of these examples. Primary references were checked on 2026-10-11. These are repeatable engineering tasks, not observed user research or executed service tests. They supplement the full parity ledger and do not select DocSuri's model architecture. [RQ]

### P1 — Understand the Transformer

- **Paper:** Vaswani et al., *Attention Is All You Need*, arXiv **1706.03762v7**. Pin this version in fixture metadata and preserve the distinction between paper identity and version. [Version record](https://arxiv.org/abs/1706.03762v7).
- **Find:** use the research query `self attention sequence transduction without recurrence`; also record a title/identifier lookup as a diagnostic. In the declared fixture corpus, the researcher must be able to identify and open the intended paper. A title-only success does not replace the research-query check.
- **Understand:** explain why attention scores are divided by the square root of the key dimension, and how token order is represented without recurrence. The first answer must connect large dot products to very small softmax gradients; the second must identify positional signals added to embeddings and the paper's sinusoidal choice. Validate against §3.2.1, equation (1), and §3.5 of the [fixed paper](https://arxiv.org/pdf/1706.03762v7). An unrelated citation or unsupported explanation fails the understanding check.

### P2 — Understand retrieval-augmented generation

- **Paper:** Lewis et al., *Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks*, arXiv **2005.11401v4**. [Version record](https://arxiv.org/abs/2005.11401v4).
- **Find:** use `retrieval augmented generation parametric non parametric memory`; retain a title/identifier diagnostic as for P1.
- **Understand:** distinguish the generator's learned parameters from the retrieved Wikipedia index, and explain RAG-Sequence versus RAG-Token. The answer must identify BART and retrieval as separate roles; the sequence formulation uses a document across an output sequence, while the token formulation permits a different document for each token. It must not claim that the sequence formulation retrieves only one candidate. Validate against Figure 1 and §2.1–§2.3 of the [fixed paper](https://arxiv.org/pdf/2005.11401v4).

### Shared repeatable procedure and evidence

1. **Prepare:** record fixture identities/versions, source URLs, allowed processing uses, content checksums where files are held, corpus composition and actual environment. Establish permitted fixture loading under NFR5; do not assume that public access grants unrestricted ingestion, translation or redistribution. Record a blocked fixture honestly and resolve eligibility before using it; no permissions investigation is claimed complete here.
2. **Enter:** create and verify synthetic public-registration accounts A and B in the test environment. Complete or skip onboarding. Record any email/provider setup dependency and whether the run proves only a local test path or the intended public-service integration. Use A for the journey.
3. **Find:** execute the task's research query, identify/open the fixed paper and check metadata/version. Record the query, configuration, results, relevance judgment and time to usable result. A corpus missing the fixture is a fixture/environment failure, not evidence of a successful no-match experience.
4. **Understand:** use the retained reading and summary/research assistance to answer the stated questions, follow the evidence to the specified source sections and check meaning against the reference. Record inputs, selected presentation/language options, output, citations and latency. Exercise a supported translation action as an additional FR3 check: compare meaning and terminology against the same source with a competent reviewer, documenting the chosen supported language pair. The full action/level/language parity set remains in FR3's downstream ledger.
5. **Save:** save the paper and query through FR5. Where research assistance was used, preserve its messages through the existing FR14 session capability; this task does not introduce a separate note-taking feature. Verify acknowledgement against committed state and repeat the save after a simulated lost response to check the intended single effect.
6. **Revisit:** close/reopen the browser and log in again as A. Find the saved paper/query, rerun the query, open the same paper/version and reopen committed research messages where applicable. Return to the evidence references and prepared result while retained; if a declared result expiry has occurred, verify the explicit expired state without silent regeneration. Confirm B cannot see A's library, history, private research session or private attachments through either UI or direct requests.
7. **Recover:** repeat with an interrupted job stream/tab sleep, lost save response, expired login, dependency outage, duplicate request and controlled service/worker restart. Verify authoritative progress/result recovery and committed data, not merely a displayed success toast. Use separate missing-content/insufficient-evidence fixtures to require explicit abstention. Record time, manual recovery actions and whether any work was lost or duplicated.

For each task, the normal run passes only when the intended paper is found, the answer satisfies the source-grounded rubric, saves are durable and owner-isolated, and revisit reaches the same intended work. Negative/recovery cases pass only when the specified failure is truthful and recovery preserves the defined state without an unauthorized or duplicate effect. A wrong source/version, fabricated support, false save, missing committed work or cross-owner exposure is a failure. Report normal and recovery outcomes separately, alongside the baseline timing observations; later user-agreed numeric targets are additional acceptance conditions. These tasks have **not been executed**, and no success rate, latency or user endorsement is asserted.

## Known defects carried into acceptance

These are reverse-engineering findings, not additional features or an instruction to retain the old wire design. [CQ]

| Finding | Observed reference problem | Required acceptance disposition |
| --- | --- | --- |
| Q-01 | Mounted job state omits the ordering field required by the browser | FR3.3 / NFR10: one executable state/event contract through the actual browser and service; monotonic recovery behavior |
| Q-02 | Result endpoint and browser disagree about usable result shape and pending/expired/failure semantics | FR3.4 / NFR10: ready result is usable, pending/expired/failed states are distinct, owner checks hold and reads do not regenerate work |
| Q-03 | Mounted job acceptance invokes a no-op enqueue callback | FR3.2 / NFR3: accepted work reaches execution or explicit recoverable failure, including acceptance/dispatch crash windows |
| Q-04 | Stream frames contain literal escaped newlines; an isolated existing test failed | FR3.3 / NFR10: valid frames are received and consumed through the real transport, including reconnect and missed progress |
| Q-05–Q-08 | Readiness masking, uncertain operational authority, test/environment drift and responsibility/contract concentration | FR19 / FR20 / NFR7–NFR10 and evidence work IB-01–IB-06; resolve each with current evidence rather than treating source size or historical counts as proof |

The recorded isolated failure is evidence for Q-04 only; it is not a full service baseline or proof that Q-01–Q-03 have been executed. This stage has not fixed or retested the service. [CQ]

## Traceability and release accounting

| Reference capability | Requirement owner | Principal verification contexts |
| --- | --- | --- |
| CAP-01 discovery | FR1 | Query/refinement/relevance, empty/error/degraded retrieval, pagination |
| CAP-02 reader | FR2 | Structured content/assets/anchors, source-only, withdrawal and private access |
| CAP-03 summary/translation/jobs | FR3 | Each retained action/level, dispatch/progress/results, interruption |
| CAP-04 glossary | FR4 | Persistence, normalization, output use, cross-owner denial |
| CAP-05 library/history | FR5 | Save/remove/rerun/clear, stable identity and later session |
| CAP-06 account lifecycle | FR6 | Public registration through verification, credential changes, deletion/reactivation |
| CAP-07 identity/MFA | FR7 | Google/ORCID valid and failed callbacks; authorized administrative access |
| CAP-08 profile/consent/subscription | FR8 | Durable profile/consent effects and truthful mock presentation |
| CAP-09 citations | FR9 | Bounded relationships, provider failure and eligible reference save |
| CAP-10 personalization | FR10 | Defaults/recent items, opt-out, event deletion/profile reset |
| CAP-11 onboarding | FR11 | Select/skip/resume; optional suggestion failure |
| CAP-12 topics/digests | FR12 | Follow/configure, send recovery, unsubscribe and time boundaries |
| CAP-13 research/evidence | FR13 | Grounded claims/quotes/comparison, attachments, abstention and web provenance |
| CAP-14 research persistence | FR14 | Messages, pending/reopen, deletion and late completion |
| CAP-15 novelty | FR15 | Topic/manuscript, artifacts/chat, cancellation race |
| CAP-16 Notion export | FR16 | Connection, current preview, explicit approval and remote-outcome reconciliation |
| CAP-17 plans/quotas | FR17 | Inspection, grant/revoke, concurrent enforcement and reset |
| CAP-18 ingestion | FR18 | Refresh/rebuild/dedup/version/withdrawal/reprocessing |
| CAP-19 service operations | FR19 | Capability health, safe telemetry, incidents and verified recovery |
| CAP-20 platform operations | FR20 | Evidence/compatibility, authority/precondition checks and durable outcomes |

The table maps all 20 discovered groups, not every unexamined line of code. IB-01 must reconcile finer behavior and integration dependencies into these stable IDs, adding IDs where necessary and recording disputed cases for the user. For each retained behavior the downstream parity ledger must name reference evidence, requirement, implementation responsibility, normal/negative/recovery checks, execution environment and outcome. An unexplained omission, unavailable required integration, failing acceptance result or unverified required branch prevents full-parity acceptance; it is not closed by a placeholder row. All NFRs apply wherever their context occurs. [SC] [BL]

| Approved backlog outcome | Requirements / evidence obligation |
| --- | --- |
| IB-01 current product reference | CAP-to-FR map plus continued sub-behavior/dependency reconciliation; no silent removal of broken or gated capabilities |
| IB-02 users, data and recovery authority | FR5–FR8, FR10–FR18, FR20; NFR3–NFR5; O-03/O-05 resolution before continuity selection |
| IB-03 integrations and obligations | FR7, FR12, FR13, FR16, FR18; NFR5/NFR10; O-02/O-04 resolution before affected changes |
| IB-04 baseline and agreed targets | NFR1–NFR3/NFR7–NFR9; repeatable public-paper tasks and quality measurement protocol |
| IB-05 sustainable free/local fit | NFR8; FR6/FR7/FR12/FR16 dependencies and model/search/worker capacity; workload/effort evidence |
| IB-06 understandable foundations | NFR7/NFR9/NFR10; boundary, configuration, setup and defect-repair proof |
| IB-07 anchor journey | FR1–FR5 with account/authorization, job and recovery dependencies; complete-task checks |
| IB-08 remaining parity | Every CAP/FR and applicable NFR, including operational capabilities; all reference behavior accounted for |
| IB-09 release and continuity proof | Complete parity, agreed quality results, selected transition/restore proof, $0 capacity and maintainership evidence; CONVENTIONS.md Git flow |

### Corner-case coverage

| Applicable condition family | Required disposition |
| --- | --- |
| Empty/one/many results; duplicate or changed identity; stale data and pagination | FR1, FR2, FR5, FR9, FR10, FR18; document stable snapshot and canonical/version semantics |
| Unicode, punctuation, very long or malformed input; unsafe markup/URLs; unsupported or truncated files | FR1, FR2, FR4, FR6, FR12, FR13, FR15, FR18; NFR4/NFR10; validate server-side and define bounded errors |
| Numeric/time boundaries, unknown versus zero, clock skew, expiration, daily windows | FR3, FR6, FR12, FR17, FR19, FR20; NFR8/NFR9; specify trusted clock/time-zone/limit semantics in design |
| Network/provider/rate-limit failure, missing credentials, cold start and incompatible schema/model | FR1–FR3, FR7, FR9, FR11–FR13, FR16, FR18–FR20; NFR8/NFR10; explicit degradation and capped recovery |
| Failed/partial writes, disk full/permissions, parallel tabs/workers, retries, crashes and late events | FR3–FR6, FR10, FR12, FR14–FR20; NFR3; preserve authoritative committed state and reconcile ambiguous outcomes |
| Unknown files, path traversal/symlinks and source changed after validation | FR2, FR13, FR16, FR18, FR20; NFR4/NFR7/NFR10; constrain reads/writes to intended resources, bind effects to validated inputs, never silently remove unrelated files |
| Public access, private ownership, revoked consent/session, retention, deletion and restore | FR2, FR5–FR8, FR10, FR12–FR17; NFR4/NFR5; authorization and data policy apply to derived data as well as primary records |
| Loading/error/empty states, focus, reauthentication, double-submit, destructive actions and rendering loops | FR1–FR17; NFR2/NFR6; preserve committed context and expose recovery/action consequences |
| Grounding failure, hostile source instructions, model/context limits and external-action side effects | FR3, FR13, FR15, FR16; NFR4/NFR5/NFR8; abstain/disclose partial evidence and require current export approval |
| Clean setup, missing tools, configuration precedence, version drift and defective telemetry | FR19/FR20; NFR7/NFR9/NFR10; reproducible supported environment and verified repair path |

## Constraints

The upstream C-01–C-13 remain authoritative. [CR]

| IDs | Constraint applied here |
| --- | --- |
| C-01/C-02 | All current capabilities in first v2; new feature expansion deferred. All FR/NFR items are Must under that boundary. |
| C-03/C-04 | Researchers/engineers; paper journey first; stable, smooth use and repairable files/code. |
| C-05 | Baseline precedes numeric quality targets; no historical test count or invented threshold establishes readiness. |
| C-06 | Authoritative users/data and recovery evidence precede the user's continuity decision; cleanup is not permission to reset accounts or discard saved work. |
| C-07 | One human maintainer with coding agents; operational burden and skill/availability evidence matter. No fixed deadline. |
| C-08/C-09 | Evaluate technologies freely within budget; investigate obligations before affected hosting/data choices. Current provider names in retained integrations do not select the internal stack. |
| C-10/C-11 | User decides scope/priorities; concise updates and clear review summaries. End users/future maintainers are considered without claiming their independent endorsement. |
| C-12 | Working branch → PR into develop → release promotion to main, per CONVENTIONS.md. No direct integration into main. |
| C-13 | $0; only free/local stacks. No planned paid APIs, subscriptions, new hardware, automatic overages or hidden paid fallback. Free trials alone do not demonstrate sustainable operation. |

Risk-first sequencing keeps capability/reference work, data/recovery authority, obligations, baseline and free/local fit ahead of dependent implementation and release commitments. It respects the approved lifecycle rather than replacing stage order. If evidence shows a conflict between parity, quality and available resources, present the specific conflict and alternatives to the user; do not silently reduce the feature set, weaken the targets or spend. [SC] [BL]

## Assumptions & Open Questions

### Assumptions and their limits

- **A-REQ1:** The approved 20 capability groups are the current working reference. This is justified by the completed repository rescan, but it is not an exhaustive deployed behavior inventory. Shallow areas, optional surfaces and external consumers remain to be reconciled under IB-01/03. All upstream feasibility assumptions remain unproven unless their evidence explicitly closes them.
- **A-REQ2:** Synthetic accounts and deliberately selected public-paper fixtures are suitable for repeatable engineering acceptance. They do not establish demand, user endorsement, universal relevance or production corpus coverage. Fixture processing permissions must be checked for each intended use.
- **A-REQ3:** Public registration can only be accepted when the full journey and protective controls fit sustainable $0 resources. That fit is a hypothesis to test, not an assurance that a free provider or local machine is sufficient.
- **A-REQ4:** Later design will define concrete wire/schema/UI choices, supported limits and operational policies while preserving these outcomes. Pending policy values are explicit dependent decisions, not discretion to omit a capability or claim acceptance prematurely.

### Open questions and closure dependencies

| Item / upstream link | Evidence or decision needed | Responsible investigation / decision; due before |
| --- | --- | --- |
| O-05, O-03; IB-02 | Authoritative service/resource inventory; actual accounts, owner-linked saved/private data, secrets/key continuity and restore-tested backups | Agents investigate, user decides continuity; before representative baseline, transition choice and operational change |
| O-03/O-04; FR6.3, FR10.2, FR14.2 | Retention/erasure/reactivation policy, deletion propagation, pending-work disposition and backup treatment | Agents investigate obligations and technical effects, user selects applicable product policy; before affected data design and acceptance |
| O-02; IB-01/03 | Actual integrations/consumers, current sub-behaviors, disabled paths, current language/level/export formats and compatibility obligations | Agents reconcile evidence, user resolves scope disputes; before contract changes and full-parity claim |
| O-04; IB-03 | Source/content permissions, user-data processing, institutional/jurisdiction/location facts and provider terms | Agents investigate with primary evidence and seek qualified clarification if required; before affected hosting, processing or redistribution decisions |
| O-01/O-05; IB-04/05 | Free/local public-service envelope, model/search/storage/email/provider fit, exhaustion behavior and operating effort | Agents measure and propose options, user decides evidenced tradeoffs; before selecting resources and committing delivery feasibility |
| C-05; IB-04 | Baseline method/results and numeric task-success, responsiveness, recovery and repair targets | Agents measure, user agrees targets; before claiming quality acceptance or release readiness |
| O-06/O-07 | Maintainer availability, skills, operating burden and change windows | User supplies availability/constraints when evidence permits planning; before schedule or release commitment |
| RQ access decision; NFR4/NFR6 | Detailed anonymous/authenticated/admin access matrix, supported browser/assistive-technology and language matrix, bounded input/abuse limits | Agents derive from current capabilities and tests; confirm genuinely new policy choices with user before dependent implementation; no extra public anonymous capability is assumed |

These are evidence and design dependencies carried forward, not unanswered user requirements that are being guessed. Preserve upstream O-01–O-07 and RAID identifiers when evidence arrives; this document closes none solely by restating them. Continuing definition is appropriate while affected commitments remain conditional. [CR] [SC]

## Out of scope

- New product capabilities beyond the retained reference, speculative expansion and a reduced-feature first-release substitution.
- Real payment/billing functionality inferred from mock subscription screens or administrative quotas.
- Paid resources, paid fallback and hardware purchases under the current $0 constraint.
- An assumed empty-user fresh start, selected migration/retention policy, chosen stack/hosting, fixed delivery date or numeric quality targets without their required evidence and decision.
- Claiming market validation, production load, real-user acceptance, measured improvements, compliance certification or implementation/test completion from this requirements document.

## Sources

- [RQ] [Requirements answers and confirmed summary](requirements-analysis-questions.md): public registration, delegated public-paper examples and all carried constraints.
- [IC] [Approved intent statement](../../ideation/intent-capture/intent-statement.md): goals, audience, quality and full capability retention.
- [SC] [Approved scope document](../../ideation/scope-definition/scope-document.md): release boundary, risk-first order and closure evidence.
- [CR] [Constraint register](../../ideation/feasibility/constraint-register.md): C-01–C-13 and O-01–O-07.
- [BL] [Approved intent backlog](../../ideation/scope-definition/intent-backlog.md): IB-01–IB-09 and unresolved evidence dependencies.
- [BO] [Business overview](../../../../codekb/DocSuri/business-overview.md): CAP-01–CAP-20 and source-visible business rules.
- [AR] [Architecture](../../../../codekb/DocSuri/architecture.md): system/data boundaries and continuity candidates.
- [CS] [Code structure](../../../../codekb/DocSuri/code-structure.md): reference surfaces and package boundaries, not a chosen v2 structure.
- [CQ] [Code-quality assessment](../../../../codekb/DocSuri/code-quality-assessment.md): Q-01–Q-08 and bounded verification evidence.
- [Git] [CONVENTIONS.md](../../../../../../../CONVENTIONS.md): working branches, PR integration into develop and release promotion to main.
