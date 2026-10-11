# DocSuri v2 — Architecture Decision Records

Date: 2026-10-11 (Asia/Seoul). **Status: Proposed — pending the human Domain Design gate.** The confirmed [design summary](domain-design-questions.md#consolidated-summary-confirmation) authorizes preparation of these proposals; it does not pre-approve the resulting decomposition. The [component catalogue](components.md) defines the component and entity identifiers used by these records.

The decisions retain all current capabilities within the $0 free/local constraint and one-maintainer model. They define logical code boundaries and responsibility, leaving deployment grouping, technology, detailed schemas and mechanisms to later stages. “Alternatives Rejected” below records alternatives not recommended in this proposal; the user chooses at the design gate.

## ADR-001: Organize by business responsibility and compose one web workspace

**Status:** Proposed.

**Context.** The first release must retain all 20 capability groups while making finding → understanding → saving → revisiting feel coherent. The same account, paper and job appears across screens. Organizing solely by screens risks several implementations of the same ownership and recovery rule; preserving every historical module risks retaining accidental boundaries. [Requirements FR1–FR20, NFR1/7/10](../requirements-analysis/requirements.md); [interaction invariants and C01–C11](../refined-mockups/interaction-spec.md).

| Option | Benefits | Costs and security/privacy implications | Reversibility |
| --- | --- | --- | --- |
| A — Business components with shared web composition | One home for each business operation; common navigation and feedback connect the journey; changes can be traced to a responsible owner | Cross-component journeys need explicit contracts; a shared composition layer must not become an alternative authorization or persistence authority | Components can be regrouped into implementation units later if ownership and contracts remain stable |
| B — Journey or screen components owning their own vertical slices | Local screen changes are easy to locate; a journey can be developed with fewer initial cross-module calls | Accounts, paper identity, quotas, drafts and jobs span journeys, creating duplicated rules or an expanding shared core; privacy and recovery fixes may need several edits | Consolidating duplicated business data and rules later is harder than moving presentation code |

**Decision.** Recommend A: `AccountAccess`, `CorpusContent`, `Discovery`, `Library`, `PaperAssistance`, `ResearchWorkspace`, `Personalization`, `TopicsDigests`, `ApprovedExport`, `UsageEntitlements`, `ServiceOperations` and `PlatformControl`, composed by `WebWorkspace` for retained web interactions. These are 13 logical components, not 13 deployed services.

`WebWorkspace` owns presentation composition, safe transient navigation context and consistent interaction feedback. It preserves the approved Korean interface, inherited blue/neutral colors, HIG web adaptations, responsive behavior, appearance modes and accessibility target. Business owners still enforce authorization, durable acceptance and truthful outcomes on every applicable server boundary. No durable job, draft, library item or permission becomes owned by the browser merely because it is displayed there.

`Discovery` owns search and citation exploration; `Library` owns the user's saved papers, saved queries and history. `Library` consumes authorized completed search outcomes from `Discovery` for qualifying history. Rerunning or saving a result is composed through explicit operations in `WebWorkspace`; `Discovery` does not call back into `Library`. `Personalization` owns defaults, recent activity, controlled behavior processing and onboarding, while `TopicsDigests` owns following and delivery lifecycles. Discovery consumes permitted personalization; it does not transfer ownership of the profile. The catalogue makes these dependency directions explicit and proposes no deliberate cycle.

**Consequences.** Shared presentation can remain smooth while the maintainer finds each rule in one business boundary. The cost is explicit composition and contract verification, including multi-component partial failure. Domain boundaries alone prove neither runtime isolation nor usability; real mounted journey checks remain necessary. Internal utilities may be shared without acquiring business ownership.

**Alternatives Rejected.** B is viable for a smaller application with little shared state, but is not recommended for DocSuri's cross-screen owner, content and recovery obligations. A one-for-one copy of the existing module tree is also not selected: the current code is parity evidence, while these boundaries follow the approved outcomes. Unit grouping remains open.

## ADR-002: Separate canonical corpus, saved references and private research material

**Status:** Proposed.

**Context.** Reading and saving must preserve paper/version identity through canonicalization, withdrawal and unavailable content. Private uploads must never become resolvable through public corpus routes. A user's saved reference is not the paper itself, and deleting that reference must not delete shared corpus content. [Requirements FR2/5/9/18, NFR4/5](../requirements-analysis/requirements.md); [paper identity and reading surface](../refined-mockups/interaction-spec.md#c03--paper-identity-and-reading-surface).

| Option | Benefits | Costs and security/privacy implications | Reversibility |
| --- | --- | --- | --- |
| A — Separate owners linked by explicit identity references | Canonical/version decisions have one authority; personal saves and private attachments have distinct deletion and access responsibilities | Each reader/save/analysis must resolve current eligibility and preserve identity across boundaries | Storage can later change while identity and ownership contracts remain; moving ownership itself requires an explicit migration |
| B — One document component for corpus content, private uploads and saved copies | Common parsing and document access can be colocated; fewer apparent content interfaces | Mixed public/private and per-user/shared lifecycles make authorization and erasure rules harder to inspect; “delete document” becomes ambiguous | Splitting mixed records later requires classification and repair of references, assets and derived content |

**Decision.** Recommend A. `CorpusContent` owns public corpus identity, versions, content/assets, provenance, eligibility and ingestion/reprocessing outcomes. “Public corpus” describes the content category, not a grant of anonymous access or unrestricted reuse. `Library` owns personal saved references and query/history records. `ResearchWorkspace` owns private attachments, their derived private material and their authorized research context. Common extraction mechanics may be reused without combining those authorities.

`Discovery` resolves corpus identities for search and citations, including incomplete or unavailable references. Saving follows `Library`'s authorized operation. Corpus withdrawal, alias changes and source restrictions remain explicit dispositions for saved references and derived views; stale indexes or cached content cannot overrule current eligibility. Saved records must not silently resolve to unrelated papers. Private identifiers and assets are checked through `ResearchWorkspace` rather than passed into a public lookup as interchangeable paper IDs.

**Consequences.** Ownership makes save removal, corpus withdrawal and private erasure independently understandable. Consumers must handle unavailable content and eligibility changes instead of assuming a referenced object is usable forever. No duplicate canonical authority is introduced by a search projection or saved display snapshot. Existing-user continuity, source permissions and recovery evidence still constrain any eventual migration.

**Alternatives Rejected.** B can work with strong internal subdomains, but offers little simplification once the same distinct access and deletion rules are retained. Separate owners make these distinctions visible before implementation; they do not prohibit sharing parsers or infrastructure.

## ADR-003: Coordinate account lifecycle through owner acknowledgements

**Status:** Proposed.

**Context.** Withdrawal, reactivation, consent changes and session revocation affect saved work, drafts, private assets, derived profiles and queued effects. A request may span failures or restarts. One component directly editing everybody's data obscures responsibility; untracked broadcasts cannot justify a claim that deletion completed. Retention, erasure, pending-work and backup policy remain unresolved. [Requirements FR6.3/6.4/8.1/10.2/12.2/14.2, NFR3–5](../requirements-analysis/requirements.md); [durable draft lifecycle and effect transitions](../refined-mockups/interaction-spec.md).

| Option | Benefits | Costs and security/privacy implications | Reversibility |
| --- | --- | --- | --- |
| A — Account-owned request/progress with domain-owned execution | Current account authority is centralized; each participant can prove what happened to its own data; partial completion is visible | A complete participant manifest, acknowledgement contract and recovery process are required; progress does not by itself prove erasure | Delivery/coordination mechanisms can change without transferring domain data ownership |
| B — Central account deletion handler directly changes all domain stores | A single procedure can initially appear simpler and provide one execution path | Requires broad write privileges and knowledge of every schema, cache and derived artifact; failures and new stores can silently leave gaps | Later separation must untangle cross-domain writes and recovery semantics |

**Decision.** Recommend A. `AccountAccess` owns current identity/session/consent facts and the `AccountLifecycleRequest`, including the required participant manifest and progress. Domains depend on its lifecycle contract, consume applicable work, act on their own entities and acknowledge their disposition back through that contract. `AccountAccess` does not import participant implementations or edit their data. Notification delivery alone is not a participant acknowledgement.

Trusted application composition supplies the required participant set; adding an owner requires updating that set and its completeness check. The account boundary revokes applicable access according to the eventual policy; each business owner rechecks current authority for reads, mutations, queued effects and late results. Participants must prevent erased or prohibited work from being revived by retries, old events, caches or restoration. Required participant outcomes include the scope and evidence needed for owned data, derived material and recovery/backup handling. A request stays incomplete or explicitly limited until every required participant and restore/derived-data disposition is known. No blanket “all data deleted” statement follows merely from changing the account status.

**Consequences.** Accountability and partial recovery remain inspectable without a cycle of module imports. This introduces coordination work and makes missing participants a correctness failure. Functional/Contract Design must define acknowledgements, policy versions, stale-work handling and recovery. The request's bookkeeping is not a retention policy, legal determination, physical deletion mechanism or proof of erasure. Reactivation can restore only lawfully and technically retained data under the later approved policy.

**Alternatives Rejected.** B is viable for very small, tightly controlled data models but would concentrate cross-domain knowledge and privilege here. Pure untracked event fan-out is not an acceptable completion authority: it cannot establish that all required owners acted. Event, asynchronous or synchronous delivery mechanisms remain open provided the chosen contract preserves A's responsibilities.

## ADR-004: Keep durable work authoritative in the business operation that accepts it

**Status:** Proposed.

**Context.** Summary/translation, research, novelty, ingestion, digests and exports have different input, cancellation, permission and result rules, but all need truthful acceptance and recovery. The approved interaction contract distinguishes a connection from work state and a result read from new execution. Quota retries must reconcile the same effect. [Requirements FR3/12–19, NFR3/8/10](../requirements-analysis/requirements.md); [activity card and effect transitions](../refined-mockups/interaction-spec.md).

| Option | Benefits | Costs and security/privacy implications | Reversibility |
| --- | --- | --- | --- |
| A — Operation-owned records with reusable execution mechanics | Acceptance, permitted transitions, result ownership and recovery stay together; policies can differ without hidden overrides | Common mechanics need a small shared contract; drift must be caught through contract and integration checks | Shared mechanisms can be extracted or replaced without moving authoritative business records |
| B — Generic job component owns every lifecycle and result | One place for scheduling, progress and retry mechanics; potentially uniform operational tooling | A generic owner must learn domain-specific deletion, cancellation and authorization rules, or become a competing status authority | Moving rules/results back into domains later risks job identity and in-flight recovery changes |

**Decision.** Recommend A. `PaperAssistance`, `ResearchWorkspace`, `CorpusContent`, `TopicsDigests` and `ApprovedExport` own accepted work and resulting effects for their respective operations. Shared scheduling, persistence, transport or retry code may implement mechanisms, but does not decide a business outcome or become a generic job authority. No particular queue, worker placement or durability pattern is selected here.

The accepting owner binds input, owner/context, operation and relevant content version; assumes recoverable dispatch/execution responsibility before acknowledging acceptance; and reconciles duplicates and uncertain responses. It decides permitted terminal outcomes and exposes ordered authoritative progress and prepared results. Opening a prepared result or reconnecting only reads that work. Deletion/cancellation and late completion must resolve under the operation's policy without reviving deleted work or triggering a second effect.

`UsageEntitlements` separately owns allocations and accounting facts. Protected operations use its current decisions and stable effect references rather than keeping independent balances. Retry, settlement/refund, reset and race rules need explicit later contracts; this decomposition does not claim an atomic transaction across owners. An unknown accounting or acceptance outcome remains unknown until reconciled. Quota administration never authorizes paid resources.

**Consequences.** Repair can trace a stuck or incorrect job to its accepting domain. Shared mechanisms reduce duplication only when their contracts preserve domain rules. The cost is explicit reconciliation across acceptance, execution, accounting and effects, exercised under loss/retry/restart cases. A uniform UI activity card can read these contracts without overwriting domain status.

**Alternatives Rejected.** B remains viable if a later system has stable shared job semantics, but these retained operations differ materially. Selecting it now would hide unresolved policy in a framework. Independent duplicated execution implementations with no common contract are also rejected because the required browser/service/worker consistency would be harder to maintain.

## ADR-005: Keep research and novelty workflows distinct inside ResearchWorkspace

**Status:** Proposed.

**Context.** Grounded questions and novelty analysis both use owner-bound source scopes, private documents, manuscript/question drafts, evidence and prepared results. Their submission, discussion, cancellation and result semantics differ. A single maintainer benefits from shared private-input handling, while those distinct semantics must stay comprehensible. [Requirements FR2.3/13–15, NFR3–5/7](../requirements-analysis/requirements.md); [durable draft lifecycle, C05 and C09](../refined-mockups/interaction-spec.md).

| Option | Benefits | Costs and security/privacy implications | Reversibility |
| --- | --- | --- | --- |
| A — One research boundary with distinct internal workflows | Private attachments, scope checks and draft revisions have one owner; common evidence handling is reusable | The boundary is substantial; research turns and novelty jobs must remain separate, named concepts rather than an undifferentiated workflow | Explicit internal workflows can later separate with a deliberate ownership and migration decision |
| B — Separate research-session and novelty components | Each lifecycle can evolve independently; implementation responsibilities are narrower | Shared attachments/drafts need another explicit owner or more inter-component contracts; transfers risk broadening private scope | Recombining code is feasible, but shared records and authority must first be reconciled |

**Decision.** Recommend A. `ResearchWorkspace` owns research sessions and committed messages, novelty analysis work/results/discussion, durable unsent drafts, and private attachments/derived material. The catalogue names `ResearchSession`, `ResearchTurn`, `NoveltyAnalysis`, `ResearchArtifact`, `EvidenceRecord`, `PrivateAttachment` and `DraftRevision` under that owner. Keep research-turn and novelty-job identities, lifecycle rules and evidence semantics explicit. Reuse suitable extraction, grounding and draft mechanisms without making a novelty result equivalent to a research answer or treating an unexamined web reference as read evidence.

Drafts are distinct from committed messages and accepted work. Only an acknowledged draft revision is promised recoverable after browser restart and same-owner authentication. Submission binds the intended revision; consumption applies only to that accepted revision, preserving later edits. Conflicts retain authorized alternatives until an explicit resolution is acknowledged. Restore never auto-submits. Expiry/account switch clears private presentation and transient state, while durable recovery and deletion follow the eventual approved policy; a browser owner tag alone is not secure storage.

**Consequences.** One owner can enforce private context and coordinate draft-to-accepted-work transitions without cross-owned writes. The tradeoff is a broader component that needs clear internal modules and focused tests. Access must remain context-specific within it; common ownership does not grant all sessions access to every attachment. Privacy, storage, retention and recovery policy remain prerequisites to implementation of durable drafts.

**Alternatives Rejected.** B is viable but is not recommended initially because it adds coordination around the same private research material without an established independent operating need. Reversibility is retained by keeping the two workflows explicit: they may later be separated behind contracts with an intentional data migration and ownership decision. A generic “conversation” record for every draft, message, job and result is rejected because it erases the required lifecycle distinctions.

## ADR-006: Give approved export its own effect authority

**Status:** Proposed.

**Context.** A completed novelty analysis is useful without publishing it. Notion export requires an owner connection, review of current content/destination, explicit approval and reconciliation when remote success is uncertain. A retry must not silently publish duplicates. [Requirements FR16, NFR3–5/8](../requirements-analysis/requirements.md); [export preview and approval](../refined-mockups/interaction-spec.md#c11--export-preview-and-approval).

| Option | Benefits | Costs and security/privacy implications | Reversibility |
| --- | --- | --- | --- |
| A — Separate ApprovedExport owner | Connection credentials, preview/approval binding and remote-effect receipts have one narrow authority; analysis can finish without any publishing authority | Export needs an authorized result-read contract and must handle changed/revoked sources and credentials | Implementation grouping can change behind the contract; moving credentials/effect records requires migration |
| B — Export as a final branch of novelty execution | Fewer boundaries and direct access to analysis output; simple initial happy path | Analysis retries and completion become coupled to an external effect; credentials and publishing checks enter a broader execution path | Extractable if approvals/effects remain explicit; harder if retries share analysis identity |

**Decision.** Recommend A. `ApprovedExport` owns per-owner Notion connection state, preview, explicit approval and export execution/reconciliation. It reads eligible novelty output through `ResearchWorkspace` and current authority through `AccountAccess`. The dependency is export → research, not analysis → export. Preview, analysis completion, draft restore and cancellation never imply publishing approval.

Approval binds the owner, reviewed content revision and destination. A relevant change or loss of authority invalidates that approval before an effect. Unknown remote outcome remains unknown while reconciled against the original effect; a new request must not manufacture certainty or a duplicate publication. Credentials are never exposed in the browser, normal logs or another owner's context. Final API, credential-storage and reconciliation mechanisms are deferred, and the retained integration must be feasible under verified free terms.

**Consequences.** The external side effect has an auditable, narrow owner. More explicit contracts are required for source eligibility, changed previews and account/connection lifecycle. Domain separation does not itself prove remote idempotency or erase an already published copy; revocation and external-data disposition must be investigated and represented truthfully.

**Alternatives Rejected.** B is viable with an explicit separate approval subflow, but that restores much of A's logical boundary inside a more privileged analysis component. Reversibility remains possible through the export contract, while moving existing credentials and effect records would require deliberate migration. Automatic publication on successful analysis is incompatible with the approved requirements.

## ADR-007: Separate service recovery from controlled platform authority

**Status:** Proposed.

**Context.** Capability health and incident recovery differ from platform compatibility evidence, operator authorization and controlled destructive/release effects. A green process signal does not prove the paper journey, and an application administrator is not automatically authorized to change platform targets. Both retained operational capabilities must remain available to one maintainer. [Requirements FR19/20, NFR4/7–9](../requirements-analysis/requirements.md); [operation-record interaction](../refined-mockups/interaction-spec.md#c10--usage-administrative-action-and-operation-record).

| Option | Benefits | Costs and security/privacy implications | Reversibility |
| --- | --- | --- | --- |
| A — ServiceOperations and PlatformControl as distinct owners | User-capability recovery and privileged target protocols have explicit authority boundaries; restricted platform evidence need not be broadly exposed | Operator workflows need links and safe correlation across both owners; some evidence is consumed across a boundary | Can share an implementation unit or tool surface while retaining separate authority |
| B — One operations component for all observations and effects | One operational entry point and fewer initial interfaces | Readiness, support privileges and destructive/release authority can blur; unrelated evidence stores and access rules accumulate | Splitting later requires classifying evidence and separating accumulated privileges |

**Decision.** Recommend A. `ServiceOperations` owns capability observations, incidents and service recovery records. It reads domain status through contracts and reads relevant platform evidence through `PlatformControl`. It requests retained recovery actions from the appropriate owner, which enforces its own authority and preconditions. It does not directly rewrite library, research, ingestion or accounting records to make a dashboard appear healthy.

`PlatformControl` independently owns operator authorities, target evidence, controlled-operation records and durable receipts. Business-account grants are not platform-operation grants. Restricted reads, actor/target/precondition checks and changed-input rejection apply under its own authority. Effect execution and reconciliation retain applicable explicit operator authority; this design authorizes no real destructive or release operation.

Business components emit safe observations through infrastructure adapters; they do not import `ServiceOperations` as a prerequisite for executing business rules. The observer's dependency on domain contracts therefore does not introduce reverse module dependencies. Telemetry failure cannot create false success, discard required evidence or cause unbounded resource use. Service capability readiness and platform-evidence currency remain separate claims.

**Consequences.** Failures can be traced without letting a dashboard become a universal privileged writer. Maintaining two evidence/authority vocabularies adds documentation and integration work, including redaction and correlation rules. Existing operational interfaces remain in scope without inventing a mobile UI for command-line protocols. Neither component chooses a vendor or permits expenditure.

**Alternatives Rejected.** B is viable with strong internal privilege separation, but the current requirements benefit from making that separation visible in the catalogue. Reversibility exists at the logical contract boundary: both can later share an implementation unit or tool surface without combining their authority or evidence claims.

## Deferred evidence and downstream decisions

The approved [requirements open questions](../requirements-analysis/requirements.md) and [interaction implementation dependencies](../refined-mockups/interaction-spec.md#verification-and-unresolved-implementation-decisions) remain open. Before affected implementation choices, establish authoritative existing users/data and recoverable backups; investigate content/privacy obligations; resolve anonymous-access detail, retention/erasure/reactivation and restore behavior; verify sustainable free/local capacity and integrations; and measure the baseline before choosing numeric quality targets. Those investigations may refine policy or motivate a revised boundary proposal. They do not silently reduce capability scope or make this design a completed implementation.

Units Generation can group these code boundaries after the human design gate. Contract and Functional Design must turn their responsibilities into executable interfaces, detailed entities, transition/race rules and acceptance checks. Later NFR/infrastructure work selects patterns and technology from evidence within the $0 constraint. Git integration follows the current [CONVENTIONS.md](../../../../../../../CONVENTIONS.md), including completed working branches returning through PRs to `develop` and the recorded interim CI guidance.
