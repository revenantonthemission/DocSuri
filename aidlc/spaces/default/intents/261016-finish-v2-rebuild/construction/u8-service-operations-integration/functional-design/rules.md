# Business Rules — U8 complete service operations and integration

Date: 2026-10-21 (Asia/Seoul)
Unit: u8-service-operations-integration. Sources: confirmed [functional-design-questions.md](functional-design-questions.md) (Q1–Q16 and the settled items), the [NFR Requirements answers](../nfr-requirements/nfr-requirements-questions.md) Q14–Q19 that reopened this design (backup volume, accounts and runtime arrangement), [requirements FR3, FR4 and NFR1–NFR6](../../../inception/requirements-analysis/requirements.md) (`requirements.md`), the requirements corrections RC1 and RC2 recorded in [functional-spec.md](functional-spec.md), the [unit definition](../../../inception/units-generation/unit-of-work.md), the approved components (`components.md`) and the frozen contracts C01, C02, C10, C11 and C13 with their common authority rules (`contract-summary.md`, both under `../../../../261010-docsuri-v2-rebuild/inception/`), and the U5 and U6 handoffs. Values marked "policy" (intervals, bounds, periods, budgets, allowances, tolerances, dates) are fixed at NFR Requirements; this file fixes only their meaning.

Definitions used throughout:
- **Production profile**: the durable profile the real service runs on (BR6.1). It is in **rehearsal** mode before the switch and **live** mode after it. In live mode its **admission** is maintainer-only during the switch's verification window and open after it. Mode and admission change only through PlatformControl's profile operation (BR9.15).
- **Composed realm**: one application with every contribution, running against one database (BR1.4). Production and the whole-application verification use the same composition with different profiles.
- **Operations ledger**: ServiceOperations' append-only record in the profile root, holding every record that must outlive emptying, restores and the move from rehearsal to live (BR6.10).
- **Required capability**: a capability the capability registry in functional-spec.md marks required (BR3.11).
- **Outward provider**: a provider whose effect reaches a person or place outside DocSuri: email (Resend) and Notion.
- **Retained copy**: any copy that may hold personal data outside the live service, such as a dry-run copy of v1, a rehearsal database or an archive, recorded with its disposal point (BR9.12).
- **Active request**: a recovery request in awaiting-operator, running, verifying, unknown, post-restore-pending or held. A request in requested is waiting and holds nothing (BR4.4).
- **You**: the maintainer. Every step this file reserves for you is recorded as your decision through the operator tool, never through the web application (BR9.14).
- **The operator**: whoever holds PlatformControl's operator authority on this machine. In practice that is you, acting through the operator tool and not as an application administrator (BR4.2).
- **The operator tool**: PlatformControl's operator commands together with U8's migration and cutover commands, run by the operator on this machine under the operator account. It writes the operations ledger through ServiceOperations' ledger component, run as the service account through that component's fixed command, so the ledger stays writable while v2 is stopped (BR6.10).
- **Service account**: the dedicated, non-login macOS account that v2's host, workers, scheduler and maintenance server run as, started by system launch jobs an administrator installs (as the earlier platform work starts its role accounts). It owns the production profile root (BR6.1) and is granted nothing beyond PlatformControl's bounded evidence reader, which reads recorded status and evidence and can cause no effect (BR3.5). It can run no command as any other account (operator, scheduler, backup, database, models or tunnel), so the running application can neither use operator authority nor reach the backup volume.
- **Operator account**: your own login account on this Mac, which the operator tool runs as. v1's launch agents and v1's data plane (OrbStack, holding v1's database, search index and object store) also run under it until v1 retires, and the other programs you run use it every day, so nothing it holds works unattended: every grant it has into another account needs interactive authentication at this Mac. That covers the fixed commands to run the ledger component and the production environment tool as the service account, the backup agent's in-person commands, service control and the tunnel's routing command. The credentials the operator tool uses, including its logins in v2's PostgreSQL instance, are released only the same way. It holds no part of v2's runtime arrangement: v2's databases, the model runtime and the tunnel run as their own accounts (BR6.11).
- **Scheduler account**: a dedicated, non-login macOS account that the standing authority's system launch job runs as, a job with a fixed label that an administrator installs (BR4.2). It holds the only unattended grants: the backup agent's unattended commands, the ledger component's fixed command run as the service account, PlatformControl's standing operations, the read-only runtime isolation check (BR6.12), and a database login in v2's PostgreSQL instance that can read scratch databases and drop only scratch, import and rehearsal databases, never the production database; it has no login in v1's data plane. The limit is ownership: those databases, and only those, are created owned by a dedicated role for disposable databases. The scheduler's login is a member of that role and of no other, and PostgreSQL lets only an owner drop a database. The refusal of the current rehearsal database is PlatformControl's database remove's own check, which reads the profile's current rehearsal database from the latest profile receipt in the ledger, never from the profile itself. It holds nothing in person and no service control.
- **Service control**: v2's host, workers and scheduler and the maintenance server run under the service account as system launch jobs with fixed labels, installed by an administrator; v2's PostgreSQL instance, the model runtime and the tunnel are system launch jobs of their own accounts, installed the same way (BR6.11). Starting or stopping one is PlatformControl's service-control operation. It runs one fixed command per label, which an administrator grants the operator account to run with administrator rights, in person, and which starts or stops exactly that job. A stop is persistent: the job stays disabled across restarts, a power cut included, until service control starts it again (BR6.12). v1's launch agents and its data plane in OrbStack run under the operator account itself, which controls them directly. The service account and the scheduler account hold no service control (BR9.10).
- **Database account**, **models account** and **tunnel account**: three dedicated, non-login macOS accounts. Each runs one system launch job with a fixed label that an administrator installs, and nothing else, so each starts at boot without anyone logging in (BR6.11). The database account runs v2's own PostgreSQL instance, which holds every v2 database (production, rehearsal, scratch and import), and owns its data folder. The models account runs the local model runtime that v1 and v2 share, and owns the models folder. The tunnel account runs the tunnel and alone can read its credentials; the configurations it runs from are root-owned. None of them can run a command as another account, and the operator account reaches them only through service control and the tunnel's routing command, in person.
- **Runtime isolation**: what BR6.11 requires of the production arrangement: every program the non-login accounts run, and every file their jobs and fixed commands read to decide what they do, comes from root-owned folders; v2's PostgreSQL instance, the model runtime and the tunnel run as their own accounts; and the packet filter lets a connection reach the local address of v2's host, the maintenance server, the model runtime or v2's instance only while the listening socket belongs to that address's account. BR6.12's read-only check confirms it every renewal interval, observed as the platform.isolation capability.
- **Backup volume**: the encrypted volume on this Mac's external drive that the production profile names (today `DocSuri_Backup`, set up for the earlier platform-integrity work), owned by the dedicated backup account the profile names. U8's files live only in U8's folder, `docsuri-v2` at the volume's top level, which holds the archives folder, the staging folder and the backup agent's catalogue. Neither that folder nor any folder above it may carry the earlier tool's cleanup marker, so that tool's age-based cleanup never treats U8's files as its own (BR6.6). The folder holds every backup set, the ledger copies and every file copy of personal data the migration and the cutover make (BR4.3, BR6.10).
- **Backup agent**: the one program that runs as the backup account, and the only thing that writes, reads back or deletes anything in U8's folder (BR4.3, BR9.17). It is started only through fixed commands that an administrator of this Mac grants, with no shell and no caller-chosen program or path, and never to the service account. Its unattended commands, granted without a password to the scheduler account alone, only report status, back up an environment's database, take a ledger copy, restore a passed set into a new scratch database for a restore verification, and run the disposal pass. The operator account may run any of its commands, but only in person, after interactive authentication at this Mac; the commands only it may run are its in-person commands: taking a snapshot of v1, copying a rolled-back database, streaming a file back, deleting a copy on its event, bringing a disposal time forward, deleting a file the catalogue can no longer vouch for, rebuilding the catalogue, preparing a replacement volume and changing the agent's own configuration. It trusts no caller: a copy's kind follows from the command and the source database, never from what a caller says, and a deletion happens only on the terms its own catalogue recorded when the file was written.
- **Catalogue**: the backup agent's own append-only, digest-chained record in U8's folder, written only by the agent. For each file it holds the path, size and digest, the record the file belongs to and that record's kind, the database incarnation for a dump, the integrity result, the earliest disposal time and the state (writing, written, held by the retention floor, or disposed) (BR4.3, BR9.17).
- **Staging folder**: the folder inside U8's folder where the backup agent first writes each file before writing it into the archives folder; owned by the backup account, folders 0700 and files 0600. Nothing is staged on the internal disk (BR4.3).

## Rules

```yaml
rules:
  - id: BR1.1
    statement: "The complete application is assembled from one finite, versioned registration manifest."
    category: constraint
    appliesTo: ContributionRegistration, CapabilityRegistration, NavigationEntry, LifecycleParticipantEntry
    trigger: "building and starting the complete application"
    logic: "IF the complete application is built THEN its manifest lists every contribution exactly once (paper-journey U1, account-controls U2, paper-corpus U3, research-workspace U4, topics-digests U5, approved-export U6, platform-control U7, service-operations U8) with its revision, schema digest, components, required contributions, provided capabilities, routes and lifecycle participants, and the manifest revision is a digest of all entries. platform-control is listed as the separately authorized operator surface and mounts no browser route. Nothing at runtime adds, removes or edits an entry."
    violationBehaviour: "A build whose manifest lacks a contribution, repeats one or differs from its digest is refused; no partial application is produced."
    source: FR3.1

  - id: BR1.2
    statement: "Each contribution is verified against the manifest before it is activated."
    category: validation
    appliesTo: ContributionRegistration, CapabilityRegistration
    trigger: "application start"
    logic: "IF a contribution is missing, its revision or schema digest differs from the manifest, a contribution it requires is unavailable, or a policy it depends on is unresolved THEN it stays unavailable with reason missing, incompatible, dependency-unavailable or policy-unresolved, every capability it provides is unavailable, and the application does not report ready. Registration writes no domain data."
    violationBehaviour: "No capability of an unverified contribution is ever reported available, and no default state stands in for a missing module."
    source: FR3.1

  - id: BR1.3
    statement: "Capability states come from current evidence, never from constants."
    category: calculation
    appliesTo: CapabilityRegistration, CapabilityObservation
    trigger: "navigation resolution, the capability catalog read, readiness"
    logic: "IF any surface needs a capability's state THEN it reads the state derived by BR3.2 from that capability's observations; a capability whose contribution is unavailable is unavailable whatever its observations say. The only exception is public.static, which is available whenever the host serves (BR5.6)."
    violationBehaviour: "A capability with no current evidence shows unknown or stale, never available."
    source: FR3.1

  - id: BR1.4
    statement: "All contributions run in one application against one database, each owner in its own schema and roles."
    category: constraint
    appliesTo: ContributionRegistration
    trigger: "application start and every transaction"
    logic: "IF the complete application runs THEN every contribution is mounted in one process group against one database; each owner keeps its own schema and owner and login roles; every transaction runs as its owner's role and checks the database identity, as today's owner transactions do."
    violationBehaviour: "A contribution that needs a second database or realm is not part of the complete application."
    source: FR3.1

  - id: BR1.5
    statement: "Conflicting schema definitions are resolved by new reconciling migrations from their owners, applied only by an explicit migrate step."
    category: constraint
    appliesTo: ContributionRegistration
    trigger: "migrate step of the composed realm"
    logic: "IF two units define the same schema object differently (the session purpose column and the session guard, the lifecycle request and scope tables and the account lifecycle revision, the capacity footprint function, the entry receipt kinds) THEN the defining owner adds a new migration that produces one definition serving every caller: AccountAccess for session, lifecycle and receipt objects, ServiceOperations for the capacity function. An applied migration file is never edited; the start applies no migration; the reconciled realm keeps U2's controls (coordinator, control worker, entry, control and usage routes) and U3's session authority together, and U2's tests run against it and must pass."
    violationBehaviour: "A migrate step that would apply a conflicting definition stops before any change; the start refuses a schema that is not at the expected migration set."
    source: FR3.1

  - id: BR1.6
    statement: "U8 owns no business entity and never writes another owner's records."
    category: authorization
    appliesTo: ContributionRegistration, MigrationRun, RecoveryRequest
    trigger: "any change U8 needs in an owner's data: lifecycle effects, migration imports, recovery"
    logic: "IF U8 needs a domain change THEN it calls the owning component's operation under trusted composition authority and records only its own records in the places BR6.10 names; reads of owners' data use the owners' read or count operations. v1 is outside the composed application and is changed only at a rollback, through v1's own account code (BR9.13)."
    violationBehaviour: "A direct write into another owner's schema is refused by that owner's roles; no U8 code path issues one."
    source: FR3.1

  - id: BR1.7
    statement: "Earlier assemblies keep booting on their own; the complete assembly is a separate entrypoint."
    category: constraint
    appliesTo: ContributionRegistration
    trigger: "building or verifying any assembly"
    logic: "IF the U1 assembly or any unit's own assembly is started THEN it starts without importing later contributions; the complete assembly is its own entrypoint and is the only one used by the production profile."
    violationBehaviour: "A change that makes an earlier assembly depend on a later contribution fails that assembly's own runner."
    source: FR3.1

  - id: BR2.1
    statement: "The lifecycle manifest names every owner of account-bound data with the scopes it answers."
    category: constraint
    appliesTo: LifecycleParticipantEntry
    trigger: "building the manifest; every lifecycle request"
    logic: "IF the complete application runs THEN its lifecycle manifest is: AccountAccess (live_records, derived_artifacts), Library (live_records), Personalization (live_records, derived_artifacts, pending_work), UsageEntitlements (live_records), PaperAssistance (live_records, derived_artifacts, pending_work), DiscoveryCitations (live_records), ResearchWorkspace (live_records, derived_artifacts, pending_work), TopicsDigests (live_records, pending_work), ApprovedExport (live_records, pending_work, external_copies) and ServiceOperations (backups, restore_enforcement): 21 pairs, within AccountAccess's 32-pair bound."
    violationBehaviour: "A manifest missing a participant or scope is refused by AccountAccess's manifest configuration; no request starts under it."
    source: FR3.1

  - id: BR2.2
    statement: "A lifecycle request completes only when every scope of its manifest revision has policy-valid evidence."
    category: constraint
    appliesTo: LifecycleParticipantEntry
    trigger: "every participant acknowledgement"
    logic: "IF any scope of the request's recorded manifest revision lacks policy-valid evidence (no adapter, no evidence, attempts spent) THEN the request stays pending or blocked; a lost, duplicate or stale acknowledgement never counts as evidence."
    violationBehaviour: "Completion is never inferred from account status or message delivery; the owner sees honest per-scope progress."
    source: FR3.1

  - id: BR2.3
    statement: "ResearchWorkspace answers its scopes through its own participant, built in U4's module."
    category: policy
    appliesTo: LifecycleParticipantEntry
    trigger: "withdraw, reactivate or erase request for an owner"
    logic: "IF the request is withdraw THEN accepted research and novelty work stops (pending_work) and the owner's research records stop being served while kept (live_records, derived_artifacts); IF reactivate THEN only what withdrawal kept is served again; IF erase THEN contexts, sessions, turns, jobs, artifacts, evidence, attachments and drafts are deleted. The participant writes only research records, once per request and scope, and records counts only as evidence."
    violationBehaviour: "Research data never blocks completion silently and is never kept past an erasure."
    source: FR3.1

  - id: BR2.4
    statement: "TopicsDigests and ApprovedExport join the manifest with their built adapters."
    category: constraint
    appliesTo: LifecycleParticipantEntry
    trigger: "building the manifest"
    logic: "IF the manifest is built THEN TopicsDigests and ApprovedExport are registered with the adapters and scopes U5 and U6 built, AccountAccess's lifecycle guard maps both participants (and ResearchWorkspace), and AccountAccess reports ApprovedExport's external-copies reason key as retained by policy (U6 amendment A8)."
    violationBehaviour: "Withdrawal always stops digests and exports; an owner's Notion pages are never misreported as erased."
    source: FR3.1

  - id: BR2.5
    statement: "ServiceOperations' backups evidence names every retained copy that may hold the owner's data and the date by which the last one is gone."
    category: policy
    appliesTo: LifecycleParticipantEntry, BackupSet, RetainedCopy
    trigger: "a lifecycle request's backups scope"
    logic: "IF a live backup schedule with a retention policy is active and at least one live BackupSet has integrity passed THEN the evidence is the number of undisposed backup sets and undisposed retained copies (BR9.12) that may hold the owner's data, and the latest date by which each will be gone: a set's retainUntil, a copy's approved disposal date, or the backstop date of a copy that is disposed on an event. The copies that may hold the owner's data are every live set taken while the account existed, any staging file a write left behind on the backup volume, any file there the ledger has no record of (BR9.17), and, for an owner migrated from v1, every rehearsal set and every v1, rehearsal or import copy. A set the retention floor holds past its retainUntil has no date: the evidence names it as held as the last good backup, and the erasure cannot report complete until a date can be named (BR9.17). A copy retired with a lost backup volume is listed as retired with that encrypted volume on that date (BR4.10). AccountAccess shows the owner that date as retained by policy until then; ELSE the scope stays blocked."
    violationBehaviour: "No erasure reports complete while a retained copy is undisclosed."
    source: FR4.1

  - id: BR2.6
    statement: "ServiceOperations gives restore-enforcement evidence for an erasure only from a verification that covered the owner's tombstone."
    category: policy
    appliesTo: LifecycleParticipantEntry, RestoreTombstone, RestoreVerification
    trigger: "a lifecycle request's restore_enforcement scope"
    logic: "IF the request is erase THEN the owner's tombstone is appended to the register when the scope is first claimed (BR4.6), and a live restore verification becomes due within the erasure verification bound (policy); the scope gets evidence only IF a live RestoreVerification with result verified has registerHeadSequence at or above the owner's tombstone sequence, and the evidence records the register head it relied on. For withdraw and reactivate the evidence is that no tombstone is needed."
    violationBehaviour: "An erasure never reports complete on a verification that did not check that owner."
    source: FR4.1

  - id: BR2.7
    statement: "A request keeps the manifest revision it started under."
    category: constraint
    appliesTo: LifecycleParticipantEntry
    trigger: "a manifest revision change while requests are in flight"
    logic: "IF the manifest revision changes THEN in-flight requests keep their recorded revision until AccountAccess reconciles them; new requests use the new revision."
    violationBehaviour: "No in-flight request silently gains or loses a scope."
    source: FR3.1

  - id: BR3.1
    statement: "Liveness, capability readiness and journey readiness are kept apart."
    category: constraint
    appliesTo: CapabilityObservation, CapabilityRegistration, VerificationRun
    trigger: "any health or readiness read"
    logic: "IF the process answers THEN it is live; it is ready only IF no required capability is unavailable, unknown or stale (a degraded required capability is named in the answer but does not by itself make the service unready), background work runs and storage admission is open; journey readiness comes only from the whole-application verification (BR10). A live process, a platform receipt or a ready state never implies journey readiness."
    violationBehaviour: "The public health route reports liveness and capability readiness only, and never claims more."
    source: FR4.1

  - id: BR3.2
    statement: "A capability's state is derived from its latest admitted observation, with stale derived from age."
    category: calculation
    appliesTo: CapabilityObservation, CapabilityRegistration
    trigger: "every state read"
    logic: "IF the contribution is unavailable THEN unavailable; ELSE IF there is no observation THEN unknown; ELSE IF the latest observation is older than freshnessBoundSeconds THEN stale; ELSE the latest status (available, degraded, unavailable or unknown) with its reason and limitations."
    violationBehaviour: "Unknown and stale are never shown or counted as available."
    source: FR4.1

  - id: BR3.3
    statement: "Every registered capability is observed periodically by its producer."
    category: policy
    appliesTo: CapabilityRegistration, CapabilityObservation
    trigger: "the control loop"
    logic: "IF renewalIntervalSeconds have passed since a capability's last observation THEN its producer observes it again; a producer that cannot observe records unknown with its reason."
    violationBehaviour: "Readiness never rests on a single observation taken at start."
    source: FR4.1

  - id: BR3.4
    statement: "Only registered producers' safe observations are admitted, and observing never changes a domain outcome."
    category: validation
    appliesTo: CapabilityObservation
    trigger: "recording an observation"
    logic: "IF the producer is not the capability's registered producer, the outcome code or limitation key is not registered, or a field would carry private text, credentials, tokens, email addresses, titles or content THEN the observation is refused. A failure to record never changes a job, effect or request; buffering is bounded and dropped observations are counted and shown as missing evidence."
    violationBehaviour: "The operator surface shows what is missing instead of a fabricated state."
    source: FR4.2

  - id: BR3.5
    statement: "Platform status is pulled from PlatformControl read-only and never stands in for application readiness."
    category: policy
    appliesTo: CapabilityObservation
    trigger: "the platform.status and platform.isolation renewal intervals"
    logic: "IF the interval is due THEN ServiceOperations reads PlatformControl's status and evidence through its read-only operation (C10 inspectEvidence) and records it as the platform.status capability's observation, and the runtime isolation check's latest result as the platform.isolation capability's (BR6.12); it never executes a platform operation for this."
    violationBehaviour: "Platform evidence appears on the dashboard as its own capabilities only."
    source: FR4.2

  - id: BR3.6
    statement: "The measurements U5 and U6 handed over become capability health and error rates."
    category: calculation
    appliesTo: CapabilityObservation
    trigger: "the export, digest and storage renewal intervals"
    logic: "IF the export interval is due THEN ServiceOperations reads U6's status counts and records the export module as degraded when the oldest unknown or accepted effect is older than its bound (policy), recording the error rate as failed over terminal effects in the last 24 hours; IF the digest interval is due THEN it reads U5's delivery outcome counts the same way; the provider each module depends on reports on its own capability (BR3.11). IF the storage interval is due THEN it records the capacity footprint (BR6.6) as storage.capacity."
    violationBehaviour: "Counts carry no identifiers, titles or content."
    source: FR4.2

  - id: BR3.7
    statement: "Lasting problems open incidents in the ledger, and an incident resolves only with verification evidence."
    category: policy
    appliesTo: ServiceIncident, CapabilityRegistration
    trigger: "state changes, correlated job failures, switch aborts, the operator"
    logic: "IF a required capability is unavailable, or degraded, unknown or stale for longer than incidentToleranceSeconds, or operations.cutover or platform.isolation is unavailable for longer than its tolerance, or platform.isolation is unknown or stale for longer than its tolerance, or a domain job failure is correlated to a required capability, THEN an incident opens in the operations ledger for the current environment unless one is already open for that capability, in which case the signal attaches to it. A switch abort opens its own incident on operations.cutover in the live environment or, when a live operations.cutover incident is already open, takes that one over as the abort's incident (BR9.5). A rollback whose database copy cannot be completed does the same for its copy-pending incident (BR9.7). An incident moves open -> investigating -> recovering -> resolved and resolves only with evidence, recorded as its resolution kind: capability-available when the capability is available again and, where a recovery ran, its verification passed; abort-reviewed for an abort's incident, when every abort effect's receipt is settled, v1 answers at the public address, the production database was recreated and your review of the abort is recorded; rollback-copy-settled for a rollback's copy-pending incident (the one CutoverRecord.rollbackCopyIncidentId names), when the copy of the stopped production database is recorded or your decision waived it and the database was recreated, with those receipts as evidence and no observation needed, since v2 is stopped (BR9.7); environment-stopped for any other unresolved live incident when an abort or a rollback stops v2, with the stop's receipt as evidence and the incident listed for your review in the abort's incident or on the rollback."
    violationBehaviour: "An incident never closes because signals stopped arriving, and a restore never erases the incident that caused it."
    source: FR4.1

  - id: BR3.8
    statement: "The operator surface is for administrators with current MFA only."
    category: authorization
    appliesTo: CapabilityObservation, ServiceIncident, RecoveryRequest
    trigger: "dashboard, incident list and recovery reads and requests"
    logic: "IF the caller is not an administrator with completed, current MFA THEN the answer is the same safe denial as any protected resource, with no counts or identifiers."
    violationBehaviour: "Ordinary users learn nothing about operations from the denial."
    source: NFR1

  - id: BR3.9
    statement: "Production logs carry identifiers, states and fixed reasons only."
    category: policy
    appliesTo: CapabilityObservation, ServiceIncident, MigrationRun
    trigger: "any log line"
    logic: "IF the application logs THEN it records identifiers, states, timestamps and fixed reason keys at informational level by default; transport libraries stay at warning or above and the Notion SDK logger keeps U6's setting; HTTP access logs stay off; no credential, token, password or hash, email address, private text, request body or private query is ever logged."
    violationBehaviour: "Diagnostics stay useful without becoming a leak."
    source: NFR3

  - id: BR3.10
    statement: "No external error reporter is active in this release; one added later must follow U6's rules."
    category: policy
    appliesTo: CapabilityObservation
    trigger: "adding or configuring error reporting"
    logic: "IF an external error reporter is added THEN it sends no local variables, no default personal data and no request bodies, scrubs the export adapter's frames, and masks every browser input; until then errors stay in local logs, observations and incidents. This reading of the project's error-reporter rule is proposed for your confirmation with this design's approval."
    violationBehaviour: "No error data leaves the machine in this release."
    source: NFR3

  - id: BR3.11
    statement: "The capability registry decides which capabilities readiness requires; providers are never required."
    category: constraint
    appliesTo: CapabilityRegistration
    trigger: "building the manifest; every readiness, soak and switch evaluation"
    logic: "IF a capability is registered THEN its required flag is the one in the capability registry: the account, library, personalization, usage, corpus, search, research, novelty, topics, export, operations ledger, storage and background-work capabilities are required; paper assistance, platform status and every provider (google, orcid, resend, models, notion) are not required, because their absence degrades features honestly (BR7.2); the cutover check (operations.cutover) is not required because it concerns the move between versions, not the running service, and the runtime isolation check (platform.isolation) is not required because it guards the arrangement rather than a function, so both open incidents past their tolerance instead (BR3.7); public.static is always available while the host serves. A held provider shows degraded with first-effect-pending or sign-in-unverified."
    violationBehaviour: "No provider outage makes the whole service report unready, and no required module is silently optional."
    source: FR4.1

  - id: BR4.1
    statement: "Backup and restore are the only recovery procedures offered in this release."
    category: validation
    appliesTo: RecoveryRequest
    trigger: "a recovery request"
    logic: "IF the operation is not backup.create, restore.verify or restore.production THEN the request is refused as not offered."
    violationBehaviour: "No other recovery path exists through ServiceOperations."
    source: FR4.1

  - id: BR4.2
    statement: "Administrators and the schedule request recovery; only operator authority performs platform effects."
    category: authorization
    appliesTo: RecoveryRequest, BackupSet, RestoreVerification
    trigger: "a recovery request and its execution"
    logic: "IF an administrator with current MFA and the recovery grant, or the schedule, requests a procedure THEN ServiceOperations records it in the ledger as requested and admits it to awaiting-operator under BR4.4; the backup or restore runs only as a PlatformControl controlled operation, bound to actor, operation, target, input hash and evidence before any effect. The schedule acts under a standing operator authority provisioned only for backup.create of an environment's database, its ledger copy (BR6.10), restore.verify into a scratch target, the disposal pass BR9.17 defines, and the read-only runtime isolation check (BR6.12); it runs as the scheduler account through a system launch job, holds nothing in person, and the service account holds no operator authority and can run none of the operator tool's commands (BR6.1). restore.production always needs the operator in person and is never scheduled. An administrator's MFA is rechecked at operator start. The application administrator never holds operator authority and never records your decisions (BR9.14)."
    violationBehaviour: "A request alone never writes a backup or restores a database, and no standing authority can restore production."
    source: FR4.1

  - id: BR4.3
    statement: "A backup is one database's set, counted only after its integrity check."
    category: policy
    appliesTo: BackupSet
    trigger: "the daily schedule (policy), a request, before a production restore, the first live backup of the switch"
    logic: "IF a backup is taken THEN it captures one environment's database only (the rehearsal database during the soak, the production database in live mode), records time, checksum, size, the database incarnation it was dumped from, its backup revision and retainUntil in the ledger, and counts only IF its integrity check passes. Every file copy U8 puts on the backup volume (a backup set, a ledger copy, a dry-run copy of v1, the v1 final snapshot, a rolled-back database's copy) is one archive file written by the backup agent: the copy's record in the ledger names its staging and final locations, and the agent enters the file in its catalogue, before anything is written. A database the agent dumps itself, in PostgreSQL's custom format, and only a database its own configuration names (the production database and the rehearsal databases by their fixed name pattern, in v2's instance, and v1's database, in v1's data plane; scratch and import databases have patterns of their own and are never dumped), so no caller supplies a dump's content. Its own database logins are one in v2's instance, which can read the production and rehearsal databases and can create and restore into only databases under the scratch name pattern, and a read-only one in v1's data plane that only the in-person snapshot command uses; the integrity check is the agent's own: the dump's table of contents lists every table the agent saw in that database when it dumped. The copy's kind follows from the command and the source database through a fixed mapping in the agent's configuration: the unattended backup command makes a live set from the production database and a rehearsal set from a rehearsal database; v1's database is dumped only by the in-person snapshot command, as a dry-run or final snapshot; and the production database becomes a rolled-back database's copy only through the in-person rollback copy command. Anything else reaches the agent as a stream from the operation that can read the source, with that operation's digest of what it sent: a ledger copy from the ledger component (unattended), and a directory tree (a search index's exported documents, or the selected objects with their manifest) as a tar archive carrying a manifest of its members' checksums (in person, with its snapshot). The agent writes the file into its staging folder, then into the archives folder with the earlier tool's archive write, which never replaces an existing file and checks that the volume is encrypted (asked of the volume's mount point); the written file's digest must equal the staged file's and, for a stream, the sender's. It then removes the staging file and completes the catalogue entry, and its receipt gives the location, digest, size and earliest disposal time, which the ledger record repeats. The earliest disposal time is fixed when the file is written: retainUntil from the agent's own retention policy (policy) for a backup set or a ledger copy, the backstop date for a copy disposed on an event, and, for the v1 final snapshot or a rolled-back database's copy, the date your decision approved. For those two, PlatformControl checks the date against the cited decision's receipt and subject digest before the in-person command runs, and the agent refuses a date earlier than its own minimum for that kind (policy) and records the decision's receipt with the entry. Reading back for a restore verification is the agent restoring a passed set into a new scratch database itself, so its unattended commands never hand a file to a caller; every other reading back (a production restore, an import, a ledger repair) is the agent streaming the file through its in-person command to the operation that asked, which checks its digest, and a tar archive's member checksums against its manifest, before use. Nothing on the volume is changed after it is written, and nothing is deleted there except as BR9.17 states."
    violationBehaviour: "A failed set is kept as evidence and never restored; the backups scope stays blocked until a live set passes (BR2.5); while the backup agent's volume check fails (BR6.6), no backup, verification or copy runs: each request fails with that reason, anything the agent staged for it is removed, at the latest by the first disposal pass once the volume is back (BR9.17), and an incident opens on storage.capacity."
    source: FR4.1

  - id: BR4.4
    statement: "Production-affecting operations never overlap, a waiting request holds nothing, and an unknown outcome is reconciled first."
    category: constraint
    appliesTo: RecoveryRequest, CutoverRecord
    trigger: "admitting or starting any recovery request, whatever its origin; a switch, an abort or a rollback"
    logic: "IF a request is to be admitted from requested to awaiting-operator THEN, under the ledger's exclusive lock, no request of a conflicting kind may be active in its environment: backup.create of the environment's database and restore.production conflict with each other and with themselves, and restore.verify conflicts only with restore.verify. The one exception is a production restore admitted on your decision in place of a held production restore of the same environment, which that decision names (BR4.7). Only one such successor waits at a time. The held request keeps the exclusion while the successor waits; when the successor starts running, it takes the exclusion over without a gap and the held request ends. If the successor ends before running, the held request keeps it. While a rehearsal database is being removed with its backup sets (BR9.17), no backup.create or restore.verify of the rehearsal environment is admitted, and the removal waits until none is active. While a switch, an abort or a rollback runs, it holds the live environment's production-affecting exclusion, and its own backup and recreate steps run inside it. A request in requested holds nothing and expires if it is not admitted within the recovery start bound (policy). IF an outcome is unknown THEN the request stays unknown, and so still active, until PlatformControl's receipt and evidence settle it; it is never re-run blindly."
    violationBehaviour: "No duplicate restore, overlapping backup or backup during a restore runs, and no waiting request blocks a step it is waiting for."
    source: FR4.1

  - id: BR4.5
    statement: "A restore verification restores into a scratch target and proves erased owners stay erased up to a stated register position."
    category: validation
    appliesTo: RestoreVerification, BackupSet, RestoreTombstone
    trigger: "restore.verify"
    logic: "IF a passed BackupSet is verified THEN the register head (sequence and digest) is read and recorded first, the set is restored into a scratch target (never production), integrity is checked, every tombstone up to that head is replayed, and every tombstoned owner is checked absent; the result is verified only IF integrity passed and erasedOwnersSurviving is 0. The same operation then removes the scratch target, the verification records scratchRemovedAt, and the request succeeds only once that removal is confirmed. IF the scratch target cannot be removed THEN the verification fails and the target is recorded as a retained copy until the operator removes it (BR9.12)."
    violationBehaviour: "A failed verification gives no restore_enforcement evidence (BR2.6) and opens an incident, and no scratch copy outlives its verification unrecorded."
    source: FR4.1

  - id: BR4.6
    statement: "Accepted erasures are recorded in a restore-enforcement register that no restore rolls back and whose truncation is detected."
    category: constraint
    appliesTo: RestoreTombstone
    trigger: "an erase request's restore_enforcement scope being claimed; every restore"
    logic: "IF an erase request's restore_enforcement scope is first claimed THEN its owner's stable identity, request and time are appended to the register in the ledger under its exclusive lock, chained by digest and synced to disk, and only then is the register head (count and head digest) replaced atomically; each erase evidence and each verification records the head it used, and a retried claim finds its tombstone by request and appends nothing. On every open, the entries up to the recorded head must verify and reach it. Valid entries beyond the head that chain from it, left by a crash after a synced append and before the head was replaced, are adopted: the head is advanced to the last of them atomically and the adoption is recorded. Only the last entry beyond the head may fail to verify; it is a torn append and is discarded with a record of the discard. IF any restore runs THEN every tombstone newer than the restored backup is replayed through AccountAccess's restore evaluation before the service reopens."
    violationBehaviour: "A shortfall, a break up to the head, or any other entry beyond the head that does not verify and chain is damage: restores are blocked and an incident opens."
    source: FR4.1

  - id: BR4.7
    statement: "A production restore needs your decision, the operator in person, a fresh backup taken after writes stop, and AccountAccess's restore evaluation."
    category: authorization
    appliesTo: RecoveryRequest, BackupSet
    trigger: "restore.production"
    logic: "IF a production restore is requested THEN it is admitted only after your decision approving the exact backup and target is recorded (BR9.14), and it runs only with the operator in person: the public address routes to the maintenance server (BR9.10) and v2 stops; a pre-restore backup of the current database is taken as a step of this same request (trigger pre-restore, linked to it) and must pass its integrity check before anything is restored (a successor takes none, below); then the database is recreated, once per request and only at this step: while running, after the maintenance route, the v2 stop and, without a predecessor, the passed pre-restore set (BR9.10). It is then restored from the chosen set, every tombstone newer than that set is replayed through AccountAccess's restore evaluation, integrity is checked, a backup of the restored database is taken as a step of this same request (trigger post-restore) and must pass its integrity check; then the request records its start authorization (startAuthorizedAt), and v2 starts and the public address routes back to v2, as the request's own last steps. The request stays active, and so holds the live environment's exclusion, from admission until it ends (BR4.4). The disposal pass therefore cannot run while the old incarnation has ended and the restored one has no passed set yet (BR9.17). v2's own start check enforces the order: while a production restore of the live environment is active, every start of v2 refuses unless that request has recorded startAuthorizedAt. That covers a start through service control and a start by a launch job at boot alike, so v2 stays stopped through post-restore-pending and held (BR6.1). IF a step fails before the recreate begins (the route to the maintenance server, stopping v2, or the pre-restore backup) THEN nothing is restored. The request ends failed first; then the operator starts v2 again on the untouched database and routes the public address back through plain service control, which v2's start check allows because no restore is active any more. The maintenance notice stays until the route back succeeds. IF the post-restore backup fails THEN the request moves to post-restore-pending and stays active with the maintenance notice up. The operator retries the backup under this same request and its receipt, needing no new decision, once the volume check passes; or retires a volume lost for good and takes the backup on the replacement (BR4.10). IF v2's start, its readiness or the route back fails after startAuthorizedAt THEN the request stays verifying, still active with the maintenance notice up, and the operator retries those last steps under it. IF a step fails once the recreate has begun (the recreate itself, the restore, the tombstone replay or the integrity check) THEN the request moves to held and stays active with the maintenance notice up. The way back is a successor: a new production restore, of the held request's pre-restore set or another passed set, whose decision names the held request as well as the backup and target. Your decision admits it in the held request's place, but the held request keeps its hold, and the exclusion, until the successor starts running. Only then does the held request end failed, naming its successor, with the exclusion passing to the successor without a gap. A successor that is cancelled, refused or expires before it runs leaves the held request held, with the same exits, and only one successor waits for a held request at a time. The successor's database was already recreated by its predecessor, so it takes no pre-restore backup; the predecessor's pre-restore set stays its fallback. Any failure of a successor before its restore, tombstone replay and integrity check have passed leaves it held in turn, and it never starts v2; a failed post-restore backup moves it to post-restore-pending like any restore. IF a held request is to be given up, typically because no restorable passed set survives (for example after its backup volume was lost and retired), THEN your decision can abandon it (restore-abandonment, BR9.14). Its subject lists every passed set of the environment that remains, the per-kind state of what will be lost, and the fact that v2 will then start on an empty database. Abandoning while a restorable set remains is therefore a deliberate, recorded choice, and those sets then follow the normal floor and disposal rules (BR9.17). It is refused while a successor waits, which must be cancelled first, and it is recorded on the request (abandonmentApprovalId). The production database is then recreated empty (BR6.3) under the still-held request, as its step bound to that decision's receipt (BR9.10), so nothing erased can come back. Only once the recreate's receipt is recorded (abandonmentRecreateReceiptRef) does the request end failed (abandonedAt), with the loss report in the evidence folder (lossReportRef). The same decision authorizes the start that follows: the operator starts v2 on the empty database and routes the public address back through service control, which v2's start check allows because no restore is active any more, and the maintenance notice comes down when the route back succeeds. A recreate that fails leaves the request held and may be retried under the same decision, needing no new one. One whose outcome is unknown leaves it unknown. Either way v2 stays stopped and the same exits remain. Erased data is never revived and current authority is never bypassed."
    violationBehaviour: "Without your decision the request waits or expires and production is untouched, no restore replaces a state that has no passed backup, and v2 never serves a restored database before its post-restore set has passed."
    source: FR4.1

  - id: BR4.8
    statement: "Key material is never part of a backup, and a restore leaves the key folders untouched."
    category: constraint
    appliesTo: BackupSet, ProductionProfile
    trigger: "taking or restoring a backup"
    logic: "IF a backup is taken THEN it contains no key material, as U6's security design requires for its keys; IF a database is restored THEN the key folders stay as they are and each owner's own rule handles any mismatch: export connections whose key version is missing become unavailable until their owners reconnect (U6), the account control keyring follows U2's key recovery, and a lost account verifier key is replaced only through AccountAccess's operator command, which ends every session and outstanding proof (BR6.2)."
    violationBehaviour: "No backup ever pairs sealed tokens with the key that opens them."
    source: FR4.1

  - id: BR4.9
    statement: "Every deliberate recovery submission has its own identity; only its retries recover it."
    category: validation
    appliesTo: RecoveryRequest
    trigger: "submitting or retrying a recovery request"
    logic: "IF a request is submitted THEN its expectedRevision is the environment's current backup revision for backup.create, or the chosen set's revision for a restore, and its idempotency key is the digest of origin, requester, operation, target, expectedRevision and a submissionId created once per deliberate submission; a retry of the same submission recovers the original request, and a new deliberate submission creates a new request."
    violationBehaviour: "A retry never creates a second request, and a new submission never recovers an earlier one."
    source: FR4.1

  - id: BR4.10
    statement: "A backup volume lost for good is retired and replaced only on your decision."
    category: policy
    appliesTo: ProductionProfile, BackupSet, LedgerCopy, RetainedCopy, CatalogueEntry, CutoverRecord
    trigger: "the backup volume failed, wiped or missing with no prospect of return"
    logic: "IF the backup volume is lost for good THEN your decision (backup-volume-retirement, BR9.14), whose subject lists every undisposed record with files on that volume, retires it, and the operator in person names its replacement, an encrypted volume owned by the backup account, in one in-person step with a fixed order. First, the backup agent's in-person prepare-volume command creates U8's folder with its archives and staging folders and a new, empty catalogue, owned by the backup account. Second, its in-person configure command records the new volume's mount point and identity in the agent's own configuration. Third, the agent's own status check must pass on that volume. Fourth, PlatformControl's profile operation (BR9.15) names the same volume in the profile, and is refused unless the third step passed for exactly that volume identity. Last, ServiceOperations' comparison of the two passes (BR6.6). Until the fourth step, storage.capacity shows backup-volume-mismatch and nothing is written to either volume. Retirement is refused while a switch or an abort holds the live environment's exclusion. During a rollback it is allowed only while the rollback's copy waits (BR9.7). During a production restore it is allowed only while the restore waits on the backup volume or is held (post-restore-pending or held, BR4.7), so a held restore can reach a passed set on a replacement volume. Every undisposed record with files on the retired volume is closed with retiredWithVolumeAt and that decision's receipt in place of disposedAt, and erasure evidence lists those copies as retired with an encrypted volume on that date (BR2.5). Backups, ledger copies, any pending rollback copy (BR9.7) and any pending post-restore backup (BR4.7) then go to the replacement, where a backup of the current environment's database and a ledger copy are taken at once, except while a production restore of that environment is active: then only the ledger copy is taken, because the database may be half restored, and the restore's own backups follow its own steps (BR4.4, BR4.7)."
    violationBehaviour: "The profile never names a volume that has not passed the volume check, and no record on a lost volume stays pending without end."
    source: FR4.1

  - id: BR5.1
    statement: "The server resolves the single navigation set; the browser keeps no access rules of its own."
    category: authorization
    appliesTo: NavigationEntry
    trigger: "every navigation resolution"
    logic: "IF navigation is resolved THEN the server applies each entry's access rule and capability state and returns, per entry, available and a reason key; the browser renders exactly that and keeps no separate owner-bound or hidden list."
    violationBehaviour: "A route being visible is never the authorization check; every route still enforces current authority."
    source: FR3.1

  - id: BR5.2
    statement: "Each navigation entry shows its real state with a reason."
    category: policy
    appliesTo: NavigationEntry
    trigger: "rendering navigation"
    logic: "IF available THEN enabled; IF degraded THEN enabled with its limitation shown; IF the entry needs a session and there is none THEN shown with a sign-in prompt (nav.authenticationRequired); IF unavailable, unknown or stale THEN disabled with its reason shown in Korean; IF administrator-only and the caller is not an administrator THEN absent."
    violationBehaviour: "No entry is silently disabled without a visible reason."
    source: FR3.1

  - id: BR5.3
    statement: "Primary navigation lists the application's destinations; the paper view opens from results."
    category: constraint
    appliesTo: NavigationEntry
    trigger: "building the navigation manifest"
    logic: "IF the manifest is built THEN the primary entries are 검색, 내 서재, 연구, 참신성 분석, 작업, 주제 구독, 내보내기, 설정, 사용량 and 계정, plus 운영 for administrators; 논문 is contextual and opens from search, library, digest and job results with their return context; 개인정보 처리방침 and 이용약관 are footer entries."
    violationBehaviour: "No primary entry exists without a mounted capability behind it."
    source: FR3.1

  - id: BR5.4
    statement: "작업 is the owner's read-only job list across research and novelty work."
    category: policy
    appliesTo: NavigationEntry
    trigger: "opening or refreshing 작업"
    logic: "IF the owner opens 작업 THEN they see their research and novelty jobs newest first through ResearchWorkspace's owner job list read, each linking to its job view or result, with live state from the job event stream and a polling fallback; reading the list never starts, repeats or cancels work."
    violationBehaviour: "Another owner's jobs are never listed; a failed stream falls back to polling without losing the list."
    source: FR3.1

  - id: BR5.5
    statement: "Owner transitions clear private state, and navigation never submits work."
    category: constraint
    appliesTo: NavigationEntry
    trigger: "sign-out, account switch, session expiry, any navigation"
    logic: "IF the owner changes or the session ends THEN private rendering state, caches and accessibility content are cleared; navigation never submits work; private input never appears in addresses, route templates or telemetry."
    violationBehaviour: "One account's data never shows under another."
    source: NFR1

  - id: BR5.6
    statement: "Privacy and terms are public pages of the v2 application at their current addresses, independent of any capability state."
    category: constraint
    appliesTo: NavigationEntry
    trigger: "building the v2 workspace; any request for /privacy or /terms"
    logic: "IF the v2 application serves the public address THEN /privacy and /terms are served signed out, readable without running the application's scripts, backed by public.static (available whenever the host serves), and linked from the entry and sign-in screens; their text is carried over unchanged from the current pages, and the privacy address stays the one Google's consent screen points to."
    violationBehaviour: "The legal pages are never disabled by a capability state and never become unreachable after the switch."
    source: FR3.1

  - id: BR5.7
    statement: "After the switch the v2 workspace is the only browser application."
    category: constraint
    appliesTo: NavigationEntry, CutoverRecord
    trigger: "the switch and settlement"
    logic: "IF the switch completes THEN the public address serves only the v2 workspace from the v2 host; the Next.js application stops with v1 and is retired at settlement (BR9.8), as requirements correction RC2 records."
    violationBehaviour: "Two browser applications never serve the public address at once."
    source: FR3.1

  - id: BR5.8
    statement: "New and changed screens are Korean and meet WCAG 2.2 AA."
    category: validation
    appliesTo: NavigationEntry
    trigger: "building any new or changed screen"
    logic: "IF a screen is new or changed in U8 (navigation, 작업, 운영, legal pages, sign-in notices, maintenance notice) THEN it uses Korean labels and meets WCAG 2.2 AA: keyboard access, visible focus, announced status, reflow and contrast."
    violationBehaviour: "A screen failing the check is not released."
    source: NFR5

  - id: BR5.9
    statement: "Signed-out callers see only a minimal public projection of capability states."
    category: authorization
    appliesTo: CapabilityRegistration, CapabilityObservation
    trigger: "a capability read without a session"
    logic: "IF the caller has no session THEN the capability read returns only the capabilities that back entries the caller may see, account.entry and the sign-in providers, each with its state and reason key alone; no age, limitation, evidence reference, count or producer identity is returned."
    violationBehaviour: "Nothing operational leaks to anonymous callers."
    source: NFR1

  - id: BR6.1
    statement: "v2 production state lives under one durable, owner-only root outside /tmp, and its copies of personal data on the backup volume it names."
    category: validation
    appliesTo: ProductionProfile
    trigger: "every start of the production profile"
    logic: "IF the production profile starts THEN its root must exist, be absolute, lie outside /tmp, not be a link, be owned by the service account with no group or other access (folders 0700, files 0600), and hold the environment manifest, key folders, the operations ledger, logs and evidence; it has no expiry. The operator side reaches the root only through fixed commands an administrator grants to run as the service account: the ledger component's and the production environment tool's for the operator account, in person, and the ledger component's alone for the scheduler account, unattended. The service account is granted nothing beyond PlatformControl's bounded evidence reader (BR3.5). Backup sets, ledger copies and the other file copies of personal data live on the backup volume the manifest names, in U8's folder, written only by the backup agent (BR4.3); the start checks the volume is mounted and encrypted, as far as the service account can see (BR6.6); a missing or unfit backup volume does not stop the start, but storage.capacity shows degraded with backup-volume-unavailable until it is back. The start also refuses, whoever starts it, while a production restore of the live environment is active and has not recorded its start authorization (BR4.7)."
    violationBehaviour: "The start refuses with the failed root check named; no state is written outside the root and the backup volume."
    source: FR4.1

  - id: BR6.2
    statement: "Key material lives in the production profile's key folders, never in backups, and a lost key is replaced only through its owner's operator command."
    category: constraint
    appliesTo: ProductionProfile
    trigger: "start, backup, restore, key loss"
    logic: "IF the production profile runs THEN the export token keyring, the account control keyring with its recovery snapshots, the account verifier key and the search cursor key live in its key folders, never in the repository, /tmp or a backup set (BR4.8); IF accounts exist and a key is missing THEN the start refuses, and the key is replaced only through its owner's operator command with that owner's stated consequence (U6 create-key-after-loss, U2 key recovery, AccountAccess verifier replacement ending every session and outstanding proof)."
    violationBehaviour: "A key is never regenerated silently."
    source: FR4.1

  - id: BR6.3
    statement: "One dedicated production database, separate from v1 and every synthetic realm; emptying means recreating."
    category: constraint
    appliesTo: ProductionProfile
    trigger: "provisioning, emptying and every transaction"
    logic: "IF the production profile runs THEN it uses its one production database in v2's own PostgreSQL instance (BR6.11), separate from v1's data plane, with each owner's roles; emptying the production or rehearsal database means recreating it from the expected migration set, so it holds only the schema and the migrations' seeded reference rows; rehearsal, scratch and import databases live in the same instance, and rehearsal databases are retained copies, one per dry run, disposed as BR9.12 states (BR8.11); no synthetic profile points at the production database and the production profile never points at a synthetic realm."
    violationBehaviour: "A database identity mismatch stops the transaction; a database is never emptied by deleting rows table by table."
    source: FR4.1

  - id: BR6.4
    statement: "The v2 host is local-only and public only through the tunnel, and it honours the profile's admission."
    category: authorization
    appliesTo: ProductionProfile
    trigger: "every request"
    logic: "IF a request arrives THEN the host, bound to a loopback address that only it can serve (BR6.11), accepts it only for its public origin (through the tunnel, run as the tunnel account) or its loopback origin (local checks), and binds origin and CSRF checks to the public origin; before the switch the tunnel does not route to it, so it is reachable only on its local port; while admission is maintainer-only, every page except /privacy and /terms shows the maintenance notice with an administrator sign-in, and only administrator accounts can sign in. The legal pages stay readable because Google's consent screen points to /privacy during your sign-in verification (BR5.6, BR7.8)."
    violationBehaviour: "Requests for any other host are refused, and nobody but you uses v2 before admission opens."
    source: FR4.1

  - id: BR6.5
    statement: "Production runs from its own checkout, pinned to a release tag on main."
    category: constraint
    appliesTo: ProductionProfile
    trigger: "every production start and every release"
    logic: "IF production starts THEN it runs, as the service account, from its own clone at a release tag on main (CONVENTIONS.md), kept in a system folder outside every home folder that the service account can read and only the release path, with administrator rights, can change; the Python runtime and every dependency the release runs with are installed inside that folder, so nothing v2, the backup agent, the ledger component, the production environment tool or the scheduler's jobs load comes from a home folder or Homebrew's prefix (BR6.11); the development working tree never runs production, and readiness evidence records the running tag and commit."
    violationBehaviour: "A branch switch in the development tree changes nothing in production."
    source: FR4.1

  - id: BR6.6
    statement: "Storage admission uses the production budget and measures the production database plus the write-ahead log."
    category: calculation
    appliesTo: ProductionProfile, CapabilityObservation
    trigger: "every capacity refresh"
    logic: "IF capacity is measured THEN the footprint is the current database's size plus the write-ahead log of v2's PostgreSQL instance, whatever the database is named. The instance keeps that log near a configured maximum whatever any database writes (no archiving, no replication slots and a maximum size, policy); PostgreSQL can pass it briefly under heavy writes, so the budget leaves room for it. The rehearsal, scratch and import databases have no budget of their own; the internal disk bounds them. storage.capacity shows degraded with capacity-approaching once the footprint passes its warning share of the budget (policy), and with internal-disk-low once the internal disk's free space falls below its threshold (policy). A restore verification starts only if the internal disk's free space, less the size the source database had when it was dumped (recorded with the set, indexes included), stays above that threshold. A dry run's import restore and each of its import phases start only if the free space, less what the run still has to write, stays above it: its import database (v1's dumped size, recorded with the snapshot, indexes included) plus the rehearsal database it builds (the current rehearsal database's size, measured at check time through the operator tool's login, or v1's dumped size while no dry run is accepted), less what those two databases already hold. The threshold is set above the write-ahead log's configured maximum, so the log needs no term of its own. The standing authority checks it before the backup agent's verify command, and the migration tool before its import restore and each import phase, each reading the threshold from its own configuration, since the agent never reads the profile. A refusal is recorded with internal-disk-low: the verification request is refused, and the dry run is interrupted (BR4.4, BR8.15). Below a critical floor (policy), storage.capacity is unavailable with internal-disk-critical: storage admission closes with capacity-exhausted, scheduled restore verifications and imports stop, and an incident opens at once, so the shared instance never runs out of room for its write-ahead log; admission stays open only while the footprint is under the production budget (policy), which replaces the synthetic 512 MiB budget. The backup volume is checked from two sides. The service's capacity producer reads what the service account can see: whether the volume is mounted and encrypted, and its free space. The backup agent's own status check runs, from the scheduler account, every renewal interval, and from PlatformControl before every operation on the volume. For the volume its own configuration names, it confirms: the backup account owns the volume, the mounted volume enforces ownership, and the backup account can write U8's folder; the catalogue verifies; and neither U8's folder nor any folder above it, up to the filesystem root, carries the earlier tool's cleanup marker (the agent never creates one). It reports that volume's identity, and the agent never reads the profile. PlatformControl records each result as evidence. ServiceOperations reads it through its evidence reader, as BR3.5 pulls platform status, and compares the reported volume identity with the one the profile names, which it reads itself; a difference is backup-volume-mismatch. The check fails closed. While either side fails, or free space is below the backup floor (policy), no write runs on the volume, and no deletion runs either unless low free space is the only failure, because deleting is what frees it. The in-person prepare-volume and configure commands are the only exception: they act on a replacement volume that is not yet the configured one, so the check of the old volume does not gate them, and the new volume must pass before anything else uses it (BR4.10). storage.capacity shows degraded with backup-volume-unavailable, backup-volume-low, backup-volume-shared-cleanup (the marker found), backup-catalogue-damaged or backup-volume-mismatch, which never closes admission."
    violationBehaviour: "Admission closes with the existing capacity-exhausted answer before the budget is crossed, and recovery routes stay open."
    source: FR4.1

  - id: BR6.7
    statement: "Secrets come from the profile's private environment, and a missing provider secret degrades only that provider."
    category: validation
    appliesTo: ProductionProfile, ProviderActivation
    trigger: "start"
    logic: "IF a secret the service itself needs is missing THEN the start refuses naming it; IF a provider's secret is missing THEN that provider is unconfigured and its capability unavailable (BR7.2); no secret is read from the repository."
    violationBehaviour: "The service never crash-loops on a missing provider secret."
    source: FR4.1

  - id: BR6.8
    statement: "Production admission follows AccountAccess's real-operation policy; public registration waits for its evidence."
    category: policy
    appliesTo: ProductionProfile
    trigger: "sign-up, sign-in"
    logic: "IF the production profile runs with admission open THEN account admission and limits follow AccountAccess's policy for real operation (policy), replacing the synthetic account limits; public registration opens only IF AccountAccess's public-activation evidence is recorded, ELSE only existing (migrated) accounts sign in."
    violationBehaviour: "Registration never opens on unrecorded evidence."
    source: FR4.1

  - id: BR6.9
    statement: "Unit operator commands run against the production profile through the production environment tool."
    category: authorization
    appliesTo: ProductionProfile
    trigger: "an operator key or recovery command"
    logic: "IF the operator runs a unit's operator command (U6 create-key-after-loss, rotate-key, retire-key, key-counts; U2 key recovery; AccountAccess verifier replacement) THEN it runs against the production profile through the production environment tool's administrative path, which the operator account runs as the service account through its fixed command, in person, never through the web application."
    violationBehaviour: "No key operation is reachable over HTTP."
    source: FR4.1

  - id: BR6.10
    statement: "U8's lasting records live in an append-only operations ledger that no emptying, restore or mode change touches."
    category: constraint
    appliesTo: ServiceIncident, RecoveryRequest, BackupSet, RestoreVerification, RestoreTombstone, RetainedCopy, ConsumerInventory, ProviderActivation, MigrationRun, ParityEntry, MisfitRecord, MisfitDecision, CutoverRecord, MaintainerApproval, LedgerCopy
    trigger: "writing any of these records"
    logic: "IF one of these records is written THEN it is appended, as a new version of the record, to the operations ledger in the profile root, owner-only, under an exclusive lock, digest-chained and synced before the ledger head is replaced atomically. Every write goes through ServiceOperations' ledger component under that same lock: the running application uses it as the service account, and the operator tool (operator account, in person) and the standing authority (scheduler account) run it as the service account through its fixed command, so records are written while v2 is stopped during a switch, an abort, a rollback or a production restore. On every open, entries left beyond the head by a crash are adopted or discarded exactly as BR4.6 states for the register. The ledger is never emptied by an abort, never overwritten by a production restore, and shared by rehearsal and live with each record naming its environment; capability observations stay in the running environment's database and are never evidence by themselves. A read-only copy of the ledger (a LedgerCopy) is streamed by the ledger component, run through that fixed command, into the backup agent's unattended ledger-copy command (BR4.3) with every backup set, rehearsal or live, and on its own at the backup time on any day no set was taken, so the ledger has a copy off the internal disk from its first day; each copy records the head sequence and head digest it reaches, is verified by the agent as chained up to that head when written, holds the same identifiers as the ledger and nothing more, and is kept and disposed like a daily set (BR9.17)."
    violationBehaviour: "A ledger that falls short of its head, breaks up to it, or holds any other entry beyond it that does not verify and chain stops every write that depends on it and opens an incident; the operator repairs it from the newest ledger copy whose chain verifies up to its recorded head, read back through the backup agent, and records which entries after that head were re-derived from their receipts or lost; nothing is rewritten in place."
    source: FR4.1

  - id: BR6.11
    statement: "v2's databases, the model runtime and the tunnel run as their own non-login accounts, at local addresses only those accounts can serve, and they start at boot without a login."
    category: constraint
    appliesTo: ProductionProfile, ProviderActivation, CapabilityObservation
    trigger: "installing the runtime arrangement before the first dry run; every boot; every renewal interval; every model job"
    logic: "IF the production profile runs THEN: (0) every program that the service, scheduler, backup, database, models or tunnel account runs, and every program a fixed command runs, comes from a root-owned folder outside every home folder and outside Homebrew's prefix, together with its interpreter and every library it loads: v2's own code, its Python runtime and its dependencies from the production checkout (BR6.5), and each runtime below from a root-owned copy that an administrator installs and upgrades in person. The same holds for every file those jobs and commands read to decide what they do: the tunnel's registered configurations and its active choice, the packet filter's rules, the system launch jobs' definitions and the fixed-command rules. No other account can change any of them without an administrator's password. Each fixed command accepts only a name from its closed set (a label, an origin or a command word), checks it again itself, and runs with sudo's cleaned environment, so no caller-supplied variable, path or library reaches it. (1) v2's databases (production, rehearsal, scratch and import) live in v2's own PostgreSQL instance, separate from v1's data plane. A system launch job with a fixed label runs it as the database account, which owns its data folder (owner-only, in a system folder on the internal disk) and runs nothing else. The instance listens only on the loopback address and accepts only SCRAM logins over TCP; its superuser is reachable only by the database account, through the instance's own local socket. Every client of the instance (v2, the backup agent, the scheduler's login and the operator tool) demands SCRAM (libpq's require_auth=scram-sha-256, with libpq 16 or later, including the libpq that psycopg's binary package bundles), so a stand-in that skips the exchange is refused, and v2's start check fails unless its own connection authenticated through SCRAM. (2) The model runtime is one system launch job run as the models account, which owns the models folder in a system folder; the job sets the runtime's home to a state folder that account owns, since the account has none. It serves v1 and v2 at its existing local address. v2 uses a model only while the digest the runtime reports for it matches the digest the release pins for it (ModelEvidence): the hash of the model's manifest, which is also the hash of the manifest the model registry serves for its tag. A model the release does not pin is never used. The digest is checked at every renewal of provider.models and before each model job starts; a mismatch makes provider.models unavailable with model-evidence-mismatch, and model work waits (BR7.2). A model change, or a new digest for the same tag, is a new release, installed in person (BR6.5); installing it puts the model in place first, the way Workflow 20 step 5 does, and until the runtime reports the new pin that model is unavailable. (3) The tunnel is one system launch job run as the tunnel account, which alone can read the tunnel's credentials. Its three registered configurations (v1 web, v2 host and maintenance server) are root-owned files, and each keeps today's route for `ssh.rvnnt.dev` to this Mac's SSH service unchanged. A routing change is PlatformControl's tunnel routing, run by the operator in person through a fixed command that takes only the origin's name, makes that configuration the active one and restarts the tunnel's job (BR9.10). No Cloudflare account certificate, which can create tunnels and move DNS routes, stays valid after the installation: the one your login account held is revoked, and the one the installation issues is revoked once the tunnel exists; a later tunnel change issues a fresh one the same way, in person. (4) The packet filter is enabled at boot by a system launch job, which loads DocSuri's rules beside the system's own. It lets a connection reach the local address of v2's host, the maintenance server, the model runtime or v2's instance only while the listening socket belongs to that address's account (the service account for the first two), so no other account can take an address over, even while its service is stopped or restarting. (5) The backup volume's passphrase is kept in a root-only store on the internal disk (the System keychain), not in your login keychain. A system launch job unlocks the volume with it at boot, and again whenever a volume appears or a minute passes while the backup volume is present but locked, so a drive that attaches late is unlocked too; it hands the passphrase over on standard input, never on a command line. The copy you keep off this Mac stays. (6) These jobs, v2's own jobs and the scheduler account's jobs start at boot without anyone logging in, so a restart that skips the disk unlock (an authorized restart) brings the production arrangement, the backup volume included, back unattended; a v2 start that finds its instance not yet answering keeps the host live and not ready and retries (BR3.1). (7) Installing the arrangement replaces every credential your login account could already have copied. The Cloudflare account certificate your login account holds is revoked in Cloudflare's dashboard, by deleting the API token it carries, so every copy of it stops working. As root, a new certificate is issued into a folder only root can read, a new tunnel is created with its credentials written straight into the tunnel account's folder, the hostnames' routes move to it, and the old tunnel is deleted, so its credentials stop working too; the new certificate is then revoked the same way and deleted. Each revocation is confirmed before its file is deleted: a read-only tunnel listing made with the revoked certificate is refused, and one made with the new certificate before its own revocation shows the old tunnel gone. The old certificate and tunnel files are deleted from your login account's tunnel folder, leaving another project's files there untouched; that project's running tunnel is unaffected, but changing its tunnels needs a new certificate, issued in person. The backup volume's passphrase is changed, the new one is stored only in the System keychain and in your password manager, and the login keychain's item is deleted. v2's own credentials (its database passwords, the Resend key and the Google and ORCID client secrets) are issued for production and kept only by the accounts that use them, never copies of the development keys your login account holds. (8) Time Machine, which this Mac runs, excludes `/Library/DocSuri/` as a whole and OrbStack's data folder, which holds v1's data plane. The first holds every account's private folder (the profile root, the PostgreSQL folder with its logs, the models' state, the tunnel's credentials, and the scheduler's and the backup agent's credentials and logs), beside programs and configuration the installation reproduces. Root sets both exclusions at installation, so no Time Machine backup holds v2's key material, credentials, database, ledger or logs, or v1's data (BR4.8, BR9.12). Time Machine's local snapshots can keep a deleted file on the internal disk for up to 24 hours, so every date erasure evidence shows for a copy on the internal disk is its removal or backstop date plus 24 hours (BR2.5). The arrangement counts as installed only when all of this is done and the runtime isolation check passes (BR6.12). An administrator installs it in person by Workflow 20, before the first dry run; a dry run starts only while it is installed and its latest runtime isolation evidence passed within its freshness bound, so every dry run, the soak and v1's restart rehearsal run on it (BR8.11, BR9.3, BR9.16). v1's own services and its data plane in OrbStack stay under the operator account until v1 retires, so what the migration reads from v1 is as trustworthy as that account; v1 uses the shared model runtime and tunnel at the same addresses, and the installation retires its own login-account jobs for them."
    violationBehaviour: "No program running as your login account can change a program another account runs or a file it runs from, read or change v2's databases, serve the address of v2's host, the maintenance server, the model runtime or v2's instance, use the tunnel's credentials, including any it copied before the installation, or have a swapped model used; a lapse shows on 운영 and opens an incident (BR3.7)."
    source: FR4.1

  - id: BR6.12
    statement: "One read-only root check confirms the runtime arrangement every renewal interval, tells planned stops from lapses, and names what failed."
    category: validation
    appliesTo: CapabilityObservation, ProductionProfile
    trigger: "every platform.isolation renewal interval; the end of the installation (Workflow 20)"
    logic: "IF the platform.isolation interval is due, or the installation ends, THEN the scheduler account runs the runtime isolation check: one fixed command run as root, because the packet filter's state and other accounts' processes can be read only as root, granted to the scheduler account without a password, taking no argument and changing nothing. It checks, for BR6.11: (programs) for every system launch job of the arrangement, of v2 and of the scheduler account, and for every fixed command, that the program, its interpreter, every library it links and the release's code and dependency folders (the code holds the pinned model digests, ModelEvidence), and every folder above each up to the root of the disk, belong to root and no other account can write to them, that none lies in a home folder or Homebrew's prefix, and that every running process of those jobs runs that program; (files) that the files those jobs and commands read to decide what they do (the tunnel's registered configurations and its active choice, the packet filter's rules, the job definitions and the fixed-command rules) belong to root and no other account can write to them; (accounts) that each job is defined to run as its own account and each of its running processes does, and that each data folder belongs to its account with no access for any other; (database) that v2's instance accepts only SCRAM logins over TCP; (filter) that the packet filter is enabled and DocSuri's rules are loaded exactly as the root-owned rules file states; (volume) that the backup volume's passphrase is in the System keychain and that, while the volume is present, it is unlocked and enforces ownership; (backups) that Time Machine excludes `/Library/DocSuri/` and OrbStack's data folder (BR6.11); (boot) that every job of the arrangement is defined to start at boot and is enabled, unless a valid stop record covers it. Service control's stop is persistent: its fixed command, run as root, disables and unloads the job and writes a stop record (the label, the time and the reference of the operation's receipt) into the root-owned configuration folder, and its start enables and loads the job and removes the record. PlatformControl binds that receipt before any effect and keeps it (C10), so it exists before the record is written. Every stop goes through PlatformControl's service-control operation, the installation's included (Workflow 20 step 9), so every stop record cites a receipt. A disabled job with a valid stop record counts as stopped, not as a lapse. A stop record is valid only in its fixed format, owned by root, and for its bound (policy), after which the job counts as a lapse until service control stops it again or starts it. The check's result lists each stop record's expiry, and the operator renews a stop in person, by stopping the job again, before its bound passes; v2's own jobs, stopped from the installation until the soak, are renewed this way. Any other disabled or missing job is a lapse. The check reads only these root-written records, never the ledger or a receipt: it validates each record's owner, format and bound, and treats anything malformed as a lapse. Whether each cited receipt exists and succeeded is checked by the operator tool, through PlatformControl's receipt read (C10), whenever it lists or renews stops; a stop record whose receipt is missing or did not succeed is shown to you as a lapse until service control stops or starts that job again. The result (IsolationCheckResult) holds a pass or a fail for each item, a fixed reason key for each failure, the stop records it found with their expiry, and the time it was checked. The check writes it, as root, into the root-owned isolation evidence folder, which every account can read and no other account can write; PlatformControl's read-only status includes the latest one, and ServiceOperations reads it as platform.isolation: available when every item passes, and otherwise unavailable with runtime-isolation-lapsed, its limitations naming the failed items (isolation-programs, isolation-files, isolation-accounts, isolation-database, isolation-filter, isolation-volume, isolation-backups, isolation-boot). The check keeps its results for a bounded period (policy) and deletes older ones itself; the ledger keeps only the incidents about them (BR3.7). The migration tool, running as the operator account, always reads the latest result directly from that folder, whether or not a v2 host runs (BR8.11)."
    violationBehaviour: "The arrangement is never reported in force on an unchecked item, and a planned stop is never taken for a lapse, nor a lapse for a planned stop."
    source: FR4.1

  - id: BR7.1
    statement: "Production uses real providers, and each mode keeps to its own adapters."
    category: policy
    appliesTo: ProviderActivation
    trigger: "start of any profile"
    logic: "IF the production profile runs THEN Google and ORCID sign-in go through AccountAccess's identity flow (linking only to verified accounts, as v2's identity rules require), account mail (verification, password reset, email change) and digests go through Resend, paper assistance and search embeddings use the local model runtime with the pinned models, and Notion uses each owner's own token; IF a synthetic profile runs THEN only the local fakes run."
    violationBehaviour: "A stand-in never runs in production, and a real provider never runs in a test."
    source: FR4.1

  - id: BR7.2
    statement: "A provider that cannot serve degrades honestly, with no fallback."
    category: policy
    appliesTo: ProviderActivation, CapabilityObservation
    trigger: "any provider use"
    logic: "IF a provider is unconfigured, held, unreachable, refusing or over its limit THEN its capability is degraded or unavailable with its reason, dependent features show that state and never claim the effect happened, and work waits or fails with a plain Korean message; nothing switches to another or paid provider."
    violationBehaviour: "No feature claims success through a provider that did not serve."
    source: NFR6

  - id: BR7.3
    statement: "Each outward provider's first live effect is approved by you during the maintainer-only window, before anyone else is admitted."
    category: authorization
    appliesTo: ProviderActivation
    trigger: "the switch's maintainer-only window"
    logic: "IF the profile is live with admission maintainer-only THEN each outward provider is held (degraded, first-effect-pending). You trigger its first effect addressed to yourself; the owning module holds it and records its exact content as a preview in the profile's evidence folder; you approve that content's digest as your decision through the operator tool (BR9.14); the module sends it only once that decision is in the ledger (approvalContentHash and approvedAt recorded), and the provider becomes active. Admission opens only when every configured outward provider is active or your opening decision accepts it unavailable. While held, nothing is sent and held work waits. An approval holds only for the switch it was made in: an abort or a rollback clears it (BR9.5, BR9.7)."
    violationBehaviour: "No user-facing mail or export is needed before its provider is approved, and no outward effect reaches anyone before the approved first effect."
    source: FR4.1

  - id: BR7.4
    statement: "Email stays within the free tier's allowance."
    category: calculation
    appliesTo: ProviderActivation
    trigger: "before each email"
    logic: "IF the daily or monthly allowance (policy) is exhausted THEN digests wait for the reset, account mail fails with a plain message, and the email capability is degraded with allowance-exhausted until the allowance resets."
    violationBehaviour: "Nothing is sent beyond the free tier."
    source: NFR6

  - id: BR7.5
    statement: "Before the switch, outward effects reach only you."
    category: authorization
    appliesTo: ProviderActivation, ProductionProfile
    trigger: "any outward effect while the production profile is in rehearsal mode, and in every dry run"
    logic: "IF the profile is in rehearsal mode THEN email goes only to your verified address and Notion only through your own connection; any other recipient is held as not permitted and recorded."
    violationBehaviour: "No migrated person receives anything from v2 before the switch."
    source: FR4.1

  - id: BR7.6
    statement: "The unit bounds on real export and real delivery lift only in live production, after the first approval."
    category: policy
    appliesTo: ProviderActivation
    trigger: "the provider becoming active in live mode"
    logic: "IF Notion becomes active in live mode THEN U6's single test-destination bound lifts and owners export to shared pages their own connection can read, under U6's rules and the Notion free-terms policy; IF Resend becomes active in live mode THEN U5's single-test bound lifts and digests go to subscribers who consented, under U5's rules."
    violationBehaviour: "In rehearsal mode and in tests the unit bounds stay in force."
    source: FR4.1

  - id: BR7.7
    statement: "Paper assistance runs on the local runtime only after its readiness evidence is recorded, and only with the model the release pins."
    category: policy
    appliesTo: ProviderActivation
    trigger: "an assistance request in production"
    logic: "IF PaperAssistance's readiness evidence (the reviewed real-model evidence its readiness marker in the profile records) is not recorded THEN assistance shows pending, not available; once recorded, requests run on the local runtime with the pinned model, only while the runtime reports the digest the release pins for it (ModelEvidence, BR6.11)."
    violationBehaviour: "No assistance result is produced before its readiness evidence is recorded, or by a model whose digest differs from the release's pin."
    source: FR4.1

  - id: BR7.8
    statement: "Real Google and ORCID sign-in are verified by you in the maintainer-only window, through the public address."
    category: validation
    appliesTo: ProviderActivation
    trigger: "the switch's maintainer-only window"
    logic: "IF the profile is live with admission maintainer-only and the tunnel routes to v2 THEN each configured sign-in provider is held (degraded, sign-in-unverified) until you complete a real sign-in with your own linked identity through the public address and record that verification as your decision (BR9.14), which sets approvedAt and makes it active; a provider that fails verification stays unavailable at opening unless you abort the switch. A verification holds only for the switch it was made in: an abort or a rollback clears it (BR9.5, BR9.7)."
    violationBehaviour: "No user meets a sign-in provider that was never exercised for real."
    source: FR4.1

  - id: BR8.1
    statement: "The migration moves the Q13 groups that exist in v1 and counts every other v1 personal-data kind as not migrated."
    category: policy
    appliesTo: MigrationRun, ParityEntry, MisfitDecision
    trigger: "every migration run"
    logic: "IF a run imports THEN it imports accounts (email, verified state, role as user to member and admin to administrator, display name by the mapping decision its missing v1 source requires, linked Google and ORCID identities), preferences (settings and onboarding), saved papers, and papers with their content and embeddings; it never imports sessions, pending verification, reset or email-change tokens, jobs, Notion connections, MFA secrets or consents. Collections, notes and API keys do not exist in v1. Followed topics and digest settings, glossary, saved searches, search history, behavior events, plan records, private uploads, research, novelty and evidence history and summaries are counted per kind with reason not-in-scope and default to archive-only, and paper figures have no v2 home (BR8.9)."
    violationBehaviour: "No v1 kind disappears from the report; nothing outside the decided scope is imported."
    source: FR4.1

  - id: BR8.2
    statement: "Every imported record is written by its owner's import operation."
    category: authorization
    appliesTo: MigrationRun
    trigger: "importing a record"
    logic: "IF a record is imported THEN the owner's import operation (AccountAccess, Personalization, CorpusContent, Library) writes it under trusted composition authority and validates it by the owner's own rules (for example a lowercase unique email, or a saved paper that references an eligible corpus version); the tool never writes an owner's tables."
    violationBehaviour: "A record the owner refuses is a misfit with the owner's reason, never forced in."
    source: FR4.1

  - id: BR8.3
    statement: "Target identities are deterministic, so a repeated import changes nothing."
    category: calculation
    appliesTo: MigrationRun, ParityEntry
    trigger: "importing a record"
    logic: "IF a source record is imported THEN its target identity is derived from (v1, kind, source id); importing it again changes nothing when the source is unchanged and updates the target when the source changed; a second pass over the same snapshot and target reports zero imported and zero updated. The same derivation finds the v2 account of any v1 account in a retained snapshot."
    violationBehaviour: "An interrupted run resumes by running again, with no duplicates."
    source: FR4.1

  - id: BR8.4
    statement: "Records are imported in dependency order, and a record whose dependency was not migrated is skipped."
    category: constraint
    appliesTo: MigrationRun, MisfitRecord
    trigger: "importing"
    logic: "IF a run imports THEN the order is accounts, identity links, preferences, papers with content and embeddings, then saved papers; IF a record's dependency (its account or its paper version) was not imported THEN it is a misfit with reason dependency-not-migrated."
    violationBehaviour: "No orphan record is created."
    source: FR4.1

  - id: BR8.5
    statement: "Password credentials carry over unchanged where v2 verifies them; nothing weakens them."
    category: policy
    appliesTo: MigrationRun
    trigger: "importing an account"
    logic: "IF the v1 password hash is in a format v2's verifier accepts (v1 and v2 use the same Argon2id hasher) THEN it is carried unchanged; IF the account has no usable password (provider-only) THEN it carries none and signs in only through its linked provider; ELSE it is marked reset-required. No plaintext, pepper or re-hash is introduced."
    violationBehaviour: "No credential is weakened, exposed or invented."
    source: FR4.1

  - id: BR8.6
    statement: "A migrated account's first sign-in collects consent, resets an unusable password, and makes an administrator enrol MFA."
    category: policy
    appliesTo: MigrationRun
    trigger: "a migrated account's first sign-in"
    logic: "IF a migrated account signs in for the first time THEN it gives v2's consents before any personal feature runs (consent is never carried or inferred); IF it is reset-required THEN a reset email is requested instead and the screen says whether it was accepted for sending or why it could not be sent; IF it is an administrator THEN it enrols MFA before any administrator action."
    violationBehaviour: "No personal feature runs for a migrated account without its own consent, and no screen claims an email was sent when it was not."
    source: FR4.1

  - id: BR8.7
    statement: "Papers are matched to the corpus's canonical identity and converted by its owner."
    category: validation
    appliesTo: MigrationRun, MisfitRecord
    trigger: "importing a paper"
    logic: "IF a v1 paper is imported THEN CorpusContent matches it by its canonical identity (arXiv id without version, DOI, or the canonical key) so an existing paper is linked, not duplicated; converts its parsed content into the owner's content shape; and applies its eligibility and size limits. A paper that fails them is a misfit (ineligible-in-v2, exceeds-v2-limit or content-shape-unconvertible)."
    violationBehaviour: "No paper bypasses the corpus's eligibility rules."
    source: FR4.1

  - id: BR8.8
    statement: "A v1 embedding is reused only when its provenance is proven to match v2's pinned policy."
    category: validation
    appliesTo: MigrationRun, MisfitRecord
    trigger: "importing a paper's embeddings"
    logic: "IF a batch's v1 vectors are offered for reuse THEN a sample of its chunks (policy) is re-embedded with v2's pinned model and policy, and the vectors are reused only IF every sampled pair matches within the tolerance (policy); ELSE the batch's embeddings are misfits with reason embedding-provenance-unproven, whose map decision means re-embedding locally with the pinned model."
    violationBehaviour: "Search never mixes vectors from a different model."
    source: FR4.1

  - id: BR8.9
    statement: "Misfits are reported, never dropped silently; each kind and reason gets your decision, and anything new in the final run gets the archive-only default and your explicit approval."
    category: policy
    appliesTo: MisfitRecord, MisfitDecision, MigrationRun
    trigger: "every run; the final run's start and report"
    logic: "IF a record cannot be imported as it is THEN it is recorded with kind, source id and reason; each (kind, reason) gets your decision (BR9.14): map (with a stated mapping rule the owners' imports apply), archive-only (kept only in the retained v1 copies) or drop (not imported, recorded); not-in-scope kinds default to archive-only. A final run refuses to start while any (kind, reason) met by the accepted dry run, or by an earlier final run whose freeze has ended, is undecided, and it freezes the decisions current at its start. IF the final run meets a (kind, reason) none of those runs met THEN its records take archive-only, are marked newInFinal, and the final report lists them apart and needs your explicit approval of them. IF a final run is rejected or fails, or the cutover aborts or rolls back after it started, even once its report was accepted, THEN its freeze ends: you can change any decision before the next final run, which freezes the decisions current at its own start. Every run records the digest of the decisions current at its start; IF a decision changes after the latest accepted dry run started THEN that dry run no longer satisfies the switch (BR9.2) until a new dry run under the current decisions is accepted, so no decision reaches the production import without first running in a dry run."
    violationBehaviour: "No record is lost without a decision you made or approved, and no decision stays frozen after the run that froze it has ended."
    source: FR4.1

  - id: BR8.10
    statement: "Each run produces a parity report that reconciles counts and checksums per kind."
    category: calculation
    appliesTo: ParityEntry, MigrationRun
    trigger: "the end of every run"
    logic: "IF a run finishes importing THEN for each kind it records source count, imported, unchanged, updated, skipped by reason and excluded by decision, and an order-independent checksum over the compared normalized fields on the source side and, through each owner's parity read, on the target side; a kind reconciles only IF the counts add up and the checksums match. Every skipped or excluded record is named by kind and source id, with newInFinal ones listed apart; the report holds no password, hash, token, email address or content and is stored owner-only in the profile's evidence folder."
    violationBehaviour: "A run whose report does not reconcile cannot be accepted."
    source: FR4.1

  - id: BR8.11
    statement: "Dry runs read a copy of v1 and write only to a disposable rehearsal database."
    category: constraint
    appliesTo: MigrationRun, ProductionProfile
    trigger: "a dry run"
    logic: "IF a dry run starts THEN, after your go-ahead because it reads production data, the migration tool run by the operator takes a read-only copy of v1's database, search index and object store onto the backup volume through the backup agent's in-person snapshot command (BR4.3), which dumps v1's database itself while the tool streams the search index's documents and the selected objects to it, and imports it into a new rehearsal database created for this run; the import reads the snapshot's database through an import database restored from its dump. The snapshot, the rehearsal database and the import database are recorded as retained copies (dry-run-snapshot, rehearsal-database and import-database) before anything is written to them, the snapshot's checksums are recorded when its copy completes, and an import reads only a completed snapshot; the run never writes to v1 or to the production database. Their disposal follows BR9.12, so at most two rehearsal databases exist at once: the accepted dry run's, which the soak uses (BR9.3), and the one a newer run is building. A dry run starts only while no switch, abort or rollback is running, and only while the runtime arrangement is installed (Workflow 20) and the latest runtime isolation evidence, which the migration tool always reads directly from the isolation evidence folder, passed within its freshness bound (BR6.11, BR6.12). The tool reads it again at every phase boundary and at least once per freshness bound during a phase; a failed item, or evidence older than that bound, interrupts the run, which resumes only once the check passes again (BR8.15)."
    violationBehaviour: "v1 and the production database are untouched by every dry run."
    source: FR4.1

  - id: BR8.12
    statement: "The final run happens only inside the switch, into the recreated production database, and its snapshot is kept as a retained copy."
    category: constraint
    appliesTo: MigrationRun, CutoverRecord, RetainedCopy
    trigger: "the switch"
    logic: "IF the final run starts THEN, with v1 writes already stopped, the production database is recreated empty (BR6.3); the final snapshot of v1's database, search index and object store is then taken onto the backup volume through the backup agent as a dry run's is (BR4.3, BR8.11), recorded as a retained copy (v1-final-snapshot) before anything is copied and given its checksums when the copy completes; the run imports under the frozen decisions, reading the snapshot's database through its own import database, and its parity report must reconcile with the final snapshot; the switch continues only after your decision approving that report (BR9.14)."
    violationBehaviour: "A final run outside the switch is refused; a report you do not approve aborts the switch (BR9.5)."
    source: FR4.1

  - id: BR8.13
    statement: "Closed v1 accounts are never imported as active, and erased data is never recreated."
    category: policy
    appliesTo: MigrationRun, MisfitRecord
    trigger: "importing an account"
    logic: "IF a v1 account is deactivated or has a pending deletion THEN it is a misfit with reason closed-in-v1, defaulting to archive-only; IF it is pending verification or locked THEN it is a misfit with reason unverified-in-v1 or locked-in-v1 for your decision; data deleted in v1 is never recreated."
    violationBehaviour: "No closed account reopens through migration."
    source: FR4.1

  - id: BR8.14
    statement: "Identity conflicts are misfits by kind."
    category: validation
    appliesTo: MigrationRun, MisfitRecord
    trigger: "importing accounts and identity links"
    logic: "IF accounts' emails differ only in letter case THEN email-case-conflict; IF an account has no email (ORCID-only sign-up) THEN no-email; IF an identity link is unconfirmed or breaks v2's one-link-per-provider rule THEN unconfirmed-link or duplicate-provider-link; IF saved papers differ only by version suffix THEN they collapse into one saved paper and the others are reported as duplicate-by-version."
    violationBehaviour: "No account is merged or guessed silently."
    source: FR4.1

  - id: BR8.15
    statement: "An interrupted run resumes only to the phase it stopped in, against a re-verified snapshot."
    category: constraint
    appliesTo: MigrationRun
    trigger: "a run that stops before reporting"
    logic: "IF a run stops in preparing, copying, importing or verifying THEN it records interruptedPhase; running it again resumes only that phase: preparing creates or recreates the target again; an incomplete copy is disposed through its retained copy record and copied again under a new record; and before importing resumes the snapshot's checksums are verified against those recorded. You may abandon an interrupted dry run, which fails it and disposes of its copies (BR9.12). IF an interrupted final run is not resumed and reported within the switch time bound (policy) THEN it fails and the switch aborts (BR9.5)."
    violationBehaviour: "Parity never reconciles against a partial copy, an interrupted run never blocks every later run, and v1 writes never stay stopped indefinitely."
    source: FR4.1

  - id: BR9.1
    statement: "Until the switch, v1 serves production with its code and data unchanged, and v2 runs beside it."
    category: constraint
    appliesTo: CutoverRecord, ProductionProfile
    trigger: "the side-by-side period"
    logic: "IF the cutover is preparing or rehearsing THEN the tunnel routes the public address to v1 as today, and the v2 production composition runs on its own local port and its own data in rehearsal mode. The one change v1 sees is that, before the first dry run, its model runtime and its tunnel move to their own accounts at the same addresses (BR6.11), which v1's restart rehearsal then covers (BR9.16). The same move retires v1's own login-account jobs for the tunnel and the model runtime, and v1's control script no longer manages the tunnel."
    violationBehaviour: "Nothing in the rehearsal changes what the public address serves. The installation moves the tunnel without interrupting v1 at the public address, because the old tunnel serves until the hostname's route moves. v1's model calls pause only while the model runtime switches accounts, and during the installation's authorized restart the public address shows the maintenance notice until you log in and v1 answers again (Workflow 20)."
    source: FR4.1

  - id: BR9.2
    statement: "The switch starts only when every precondition holds."
    category: validation
    appliesTo: CutoverRecord
    trigger: "starting the switch"
    logic: "IF the switch is requested THEN it starts only when (1) the whole-application verification passed on the exact release tag (BR10.5), (2) the soak ran clean for its full period on that tag (BR9.3), (3) the latest dry run's report is accepted, that run used the decisions current now (BR8.9), and every misfit kind and reason BR8.9 requires is decided, (4) a rehearsal restore verification with result verified exists (BR4.5), (5) the consumer inventory is complete with every disposition approved (BR9.11), (6) no incident is unresolved in either environment, including the incident of an earlier abort (BR3.7, BR9.5), (7) v1 runs from a fixed checkout and its restart rehearsal passed within its window (BR9.16), (8) the backup volume check passes from both sides with free space of at least the backup floor plus the sizes the accepted dry run measured for its snapshot and for a backup of its rehearsal database, which stand for the final snapshot and the first live backup (BR6.6), (9) the latest runtime isolation evidence passed within its freshness bound (BR6.11, BR6.12), and (10) your decision approves the start (BR9.14)."
    violationBehaviour: "A missing precondition keeps the cutover in rehearsing or ready-to-switch, with the missing item named."
    source: FR4.1

  - id: BR9.3
    statement: "The soak runs the release in rehearsal mode for its full period and is clean only on ledger evidence."
    category: policy
    appliesTo: CutoverRecord, ServiceIncident, BackupSet, RestoreVerification
    trigger: "the soak period"
    logic: "IF the soak runs THEN the release runs on the production profile in rehearsal mode and on the runtime arrangement BR6.11 requires, with real providers under the recipient bound (BR7.5), on the rehearsal database of the latest accepted dry run, for soakPeriodSeconds (policy); it is clean only IF the ledger shows, for the rehearsal environment and the soak period, no incident on a required capability or on platform.isolation that was not resolved with verification, the scheduled backups recorded with integrity passed, at least one restore verification verified, and no incident open at its end. A new release tag restarts the soak. A newer accepted dry run moves the soak onto its rehearsal database without restarting it, because the clean period is evidence about the release; the restore verification BR9.2 (4) needs must then be of the new rehearsal database."
    violationBehaviour: "A soak that is not clean leaves the cutover rehearsing."
    source: FR4.1

  - id: BR9.4
    statement: "The switch follows one recorded sequence, with a maintainer-only window before admission opens."
    category: constraint
    appliesTo: CutoverRecord, MigrationRun, ProductionProfile, ProviderActivation
    trigger: "your approval of the switch start"
    logic: "IF the switch starts THEN, while it holds the live environment's exclusion (BR4.4) and with each effect run as a bound operation whose receipt is added to the CutoverRecord (BR9.10): route the public address to the maintenance server, stop v1's services and scheduled jobs, and stop the rehearsal v2; run the final migration (BR8.12) and get your decision on its report; change the profile to live with admission maintainer-only (BR9.15) and start v2 on the production database; take the first live backup and require its integrity to pass; route the public address to v2; in the window, sign in yourself, verify Google and ORCID sign-in (BR7.8) and approve each outward provider's first effect (BR7.3); require every required capability available and no incident open; then, on your decision, open admission (BR9.15). Right after admission opens, v1's stopped stores are recorded as a retained copy (v1-stores) and the rehearsal databases and rehearsal backup sets are disposed (BR9.12). v1 stays stopped but installed."
    violationBehaviour: "A step that fails, is declined or exceeds the switch time bound triggers the abort (BR9.5)."
    source: FR4.1

  - id: BR9.5
    statement: "Until admission opens, the switch aborts back to v1, and v1 is serving again before anything of v2's is removed."
    category: policy
    appliesTo: CutoverRecord, ServiceIncident, MisfitDecision
    trigger: "a failed step, your decline, an interrupted final run past its bound, or the switch time bound passing before admission opens"
    logic: "IF the switch aborts THEN the cutover moves to aborting and the abort's incident opens on operations.cutover in the live environment, opened by switch-aborted, or, when a live operations.cutover incident is already open, that incident becomes the abort's incident (BR3.7); the public address routes to the maintenance server and v2 stops; v1's services and scheduled jobs start, and once v1's health answers locally the public address routes back to v1; only then does the profile return to rehearsal mode with admission maintainer-only (BR9.15) and the production database get recreated empty; every outward and sign-in provider's approval is cleared, so the next switch verifies each again in its own window (BR7.3, BR7.8); the other unresolved live incidents resolve as environment-stopped and are listed in the abort's incident (BR3.7); a final run that was not yet accepted ends failed, and the decisions unfreeze whether or not it was accepted (BR8.9); the cutover returns to rehearsing and the rehearsal v2 starts again on the accepted dry run's database. A completed final snapshot stays as its retained copy, while one whose copy never completed is disposed through its record (BR9.12); the accepted dry run and its rehearsal database stay, and the soak's clean result stays valid for the same release tag, so the cutover can return to ready-to-switch once BR9.2 holds again, which needs the abort's incident resolved with your review. IF v1 does not start THEN the cutover stays aborting with the maintenance notice up, the abort's incident records v1-restart-failed, and the operator repairs v1 from its fixed checkout (BR9.16); nothing routes to v1 until its health answers locally, and v1's data is untouched because the switch only read it."
    violationBehaviour: "Users see v1 again after the maintenance notice, with nothing lost, and v2's database is never emptied while v1 is not serving."
    source: FR4.1

  - id: BR9.6
    statement: "Every session ends at the switch, and returning users are told why they sign in again."
    category: policy
    appliesTo: CutoverRecord
    trigger: "the first visits after admission opens"
    logic: "IF someone arrives after admission opens THEN they have no session (v1 sessions are not migrated), and the entry screen tells returning users that DocSuri moved to the new version and asks them to sign in once (BR8.6)."
    violationBehaviour: "No v1 session or token works on v2."
    source: FR4.1

  - id: BR9.7
    statement: "Within the rollback window you can return to v1; v2's lifecycle outcomes reach v1 before it serves, and nothing of v2's is removed until v1 serves."
    category: policy
    appliesTo: CutoverRecord, RetainedCopy
    trigger: "your rollback decision within rollbackWindowSeconds (policy) of admission opening"
    logic: "IF you roll back THEN the cutover moves to rolling-back and holds the live environment's exclusion (BR4.4) until the rollback ends: the public address routes to the maintenance server and v2 stops; v1's services and scheduled jobs start with the public address still on the maintenance server; v2's lifecycle outcomes are applied to v1 and every v1 session ends (BR9.13); the public address routes to v1 and v1's health answers through it, which records rollbackV1ServingAt. At that same step the v1-stores retained copy is marked returned to service, the profile returns to rehearsal mode with admission maintainer-only (BR9.15), every outward and sign-in provider's approval is cleared (BR7.3, BR7.8) and the decisions unfreeze (BR8.9). Only after that step is the stopped production database copied onto the backup volume as a retained copy (rolled-back-v2-database, BR4.3), and it is recreated empty only once that copy's checksum is recorded; unresolved live incidents then resolve as environment-stopped and are listed on the rollback (BR3.7); accounts created and writes made in v2 since the switch are reported per kind and never merged into v1; the cutover is rolled-back. IF the copy cannot be completed for any reason (the backup volume missing, locked or full, a digest that differs, an integrity check that fails, or a stream that breaks) THEN the cutover stays rolling-back with v1 serving and records rollbackCopyPendingSince: what the serving step did stays done, so the profile is in rehearsal mode, provider approvals stay cleared and decisions can be changed, but no dry run, rehearsal or switch starts, and the production database stays stopped and untouched; an incident opens on operations.cutover in the live environment, or, when a live operations.cutover incident is already open, the rollback takes that one over as its copy-pending incident with the new signal attached, as an abort does (BR3.7); CutoverRecord.rollbackCopyIncidentId names it. The wait ends in one of three ways: the operator retries the copy, once the volume check passes when the volume was the cause; your decision retires a volume lost for good and names its replacement (BR4.10), and the copy is written there; or your decision waives the copy (rollback-copy-waiver, BR9.14), whose subject is the per-kind count of accounts and writes made in v2 since the switch that will be lost, and the database is recreated without a copy. That incident resolves as rollback-copy-settled, on the receipts of the copy or the waiver and of the recreate, before the other live incidents resolve as environment-stopped; it is never one of them (BR3.7). IF v1 does not start, or a step fails before rollbackV1ServingAt is recorded, THEN your decision can cancel the rollback: v1 stops, v2 starts again on its untouched database with the profile unchanged, the public address routes back to v2, and the cutover returns to switched with its rollback window still counted from admission opening."
    violationBehaviour: "No owner who withdrew or erased in v2 is served by v1 as before, nothing personal is left without a disposal point, and v2's database is never emptied while v1 is not serving, nor before its copy is recorded unless your decision waived it."
    source: FR4.1

  - id: BR9.8
    statement: "Settlement retires v1 through the release path; v1's data stays only as a dated retained copy."
    category: policy
    appliesTo: CutoverRecord, RetainedCopy
    trigger: "the rollback window closing without rollback, and your decision confirming settlement"
    logic: "IF your decision confirms settlement THEN v1's routes and the Next.js application are retired through the release path under the dispositions of the consumer inventory (BR9.11); v1's database, search index, object store and its own backup files stay stopped as the v1-stores retained copy recorded when admission opened, until its disposal date (BR9.12); the cutover is settled."
    violationBehaviour: "v1 code is never removed while an approved disposition depends on it."
    source: FR4.1

  - id: BR9.9
    statement: "U8 builds and rehearses the cutover; the real switch runs in Deployment Execution with your approval."
    category: authorization
    appliesTo: CutoverRecord
    trigger: "any real switch, rollback or settlement"
    logic: "IF a real switch, rollback or settlement is due THEN it runs in the Deployment Execution stage with your approval; U8 supplies the procedures, tools and rehearsal evidence and authorizes no release."
    violationBehaviour: "No U8 build step changes what production serves."
    source: FR4.1

  - id: BR9.10
    statement: "Every switch, abort, rollback, restore, disposal and decision effect is a bound PlatformControl operation with a receipt."
    category: authorization
    appliesTo: CutoverRecord, RecoveryRequest, RetainedCopy, MaintainerApproval, ProductionProfile
    trigger: "any service, routing, database-lifecycle, profile, disposal, v1 or decision effect"
    logic: "IF the switch, an abort, a rollback, a production restore, a disposal or a decision of yours needs an effect THEN it runs under operator authority as one of these bound operations: service control (start or stop one named service: v1 API, v1 web, v1 workers and scheduled jobs, which are launch agents of the operator account; v2 host, v2 workers, v2 scheduler and the maintenance server, which are system launch jobs of the service account, and v2's PostgreSQL instance, the model runtime and the tunnel, which are system launch jobs of their own accounts (BR6.11), each reached only through its own fixed command with administrator rights, in person; a stop disables and unloads the job, so it stays stopped across restarts until service control starts it, and a start enables and loads it, BR6.12); tunnel routing (route the public address to one of three registered origins: v1 web, v2 host, maintenance server, through a fixed command that takes only the origin's name, makes that root-owned configuration the active one and restarts the tunnel's job); database recreate (the production database or a rehearsal database, refused while the profile is live with admission open, with two exceptions, each bound to the request's receipt (BR4.7). The first is the recreate step of a production restore. It is allowed only while the request is running, its route to the maintenance server and its v2 stop have receipts, and the request has no recreate receipt yet. A request without a predecessor also needs its pre-restore set to have passed; a successor needs the request it replaced to have ended naming it. The second is the recreate of a held restore's abandonment, with no successor waiting, bound also to your abandonment decision's receipt. It may follow any earlier recreate of the same request, and repeats only as a retry after a failed abandonment recreate. Any other recreate is refused while live and open, including one bound to a restore that is awaiting-operator, verifying or post-restore-pending); database remove (a rehearsal database, a scratch target or an import database only, BR9.17); database backup and the backup agent's other volume operations (BR4.3); database restore; profile mode, admission and backup volume (BR9.15); retained-copy disposal (BR9.17); v1 lifecycle application (BR9.13); and decision recording (BR9.14). Each binds actor, target and input before the effect, leaves its receipt on the record it serves, and an unknown outcome is reconciled before the next effect. A planned stop outside a switch, abort, rollback or production restore (at installation, for maintenance or to renew a stop) serves no other record: PlatformControl keeps its receipt, and the job's stop record cites it (BR6.12). The maintenance server is a static server in the release with no application or database dependency, serving only the maintenance notice and static copies of /privacy and /terms."
    violationBehaviour: "No generic command, path or shell execution is admitted."
    source: FR4.1

  - id: BR9.11
    statement: "The consumer inventory and its approved dispositions come before the switch."
    category: validation
    appliesTo: ConsumerInventory, CutoverRecord
    trigger: "preparing the switch"
    logic: "IF the switch is to be prepared THEN the inventory lists every client seen calling v1's routes over the observation window (policy) and every known integration, and records for each the disposition your decision approves (BR9.14): moves with v2, retired with v1, informed, or accepted to break; it is complete only when every consumer has one."
    violationBehaviour: "The switch never breaks an unrecorded consumer."
    source: FR4.1

  - id: BR9.12
    statement: "Every retained copy of personal data is recorded before use, with a disposal point, a backstop date, operator-only reading and a disposal record."
    category: policy
    appliesTo: RetainedCopy, BackupSet, LedgerCopy
    trigger: "making or keeping any copy that may hold personal data outside the live service; its disposal point or backstop date arriving"
    logic: "IF a copy that may hold personal data is made or kept outside the live service THEN it is recorded as a RetainedCopy, listing every location it will occupy, before anything is written to it, so a copy cut short by a stop or a failure is still recorded; it is disposed at its point: an incomplete snapshot when a resumed copy replaces it or its run ends; a dry-run snapshot when its run is accepted, rejected, failed or abandoned; an import database when its run reaches any end; a rehearsal database, together with its rehearsal backup sets, when a newer dry run is accepted, when its own run is rejected, failed or abandoned, or right after admission opens; a scratch restore that its verification could not remove, as soon as the operator removes it; the v1 final snapshot, v1's stores (its database, search index, object store and its own backup files, together with any Time Machine backup that holds them, recorded right after admission opens) and a rolled-back v2 database at the disposal date your decision approves (policy), which for v1's stores is no earlier than the end of the rollback window. That date is part of the subject of the decision of the step that creates the copy: the switch start for the final snapshot, the admission opening for v1's stores, the rollback for a rolled-back database; a later decision can change it, and an earlier date takes effect only as BR9.17 states. Every copy also has a backstop date (policy) by which it is disposed whatever happens; a backstop that passes while a switch, an abort or a rollback runs takes effect when it ends, and a rehearsal database reaching it while the soak still uses it returns the cutover to preparing. File copies (dry-run snapshots, the v1 final snapshot, a rolled-back database's copy) live on the backup volume (BR4.3); databases (rehearsal databases, scratch restores, import databases) live in PostgreSQL; v1's stores stay where v1 keeps them. No application route or application code reads a copy: copies on the backup volume are read back only by PlatformControl's restore, verification and import operations, through the backup agent (BR4.3). Deletion follows BR9.17. v1's stores stop being a retained copy when a rollback returns them to service."
    violationBehaviour: "No copy of personal data is kept without a recorded end, and erasure evidence discloses every undisposed copy (BR2.5)."
    source: FR4.1

  - id: BR9.13
    statement: "At a rollback, v2's lifecycle outcomes reach v1 through v1's own account code before v1 serves."
    category: constraint
    appliesTo: CutoverRecord
    trigger: "a rollback, after v2 stops and v1's services start with the public address still on the maintenance server"
    logic: "IF a rollback applies v2's lifecycle outcomes THEN, after v2 has stopped so that nothing changes any more, the operator tool lists through AccountAccess's read operation, run under trusted composition authority against the stopped production database, every v2 account whose lifecycle state changed since the switch with its latest outcome (withdrawn or erasure accepted; an account reactivated after its withdrawal needs nothing); it finds each matching v1 account by BR8.3's derivation over v1's database, which is unchanged since the switch; PlatformControl's v1 lifecycle operation, bound to that list's hash, applies them through v1's own account code: an erasure becomes a v1 deletion due now and is purged at once by v1's purge code with the owner's v1 data; a withdrawal becomes a v1 deletion with v1's own grace period, which ends in v1's purge unless the owner reactivates in v1. The same operation then ends every v1 session, so nobody returns with a session from before the switch, and reads back each account's v1 state; the public address routes to v1 only when every account matches. The per-account results, identifiers and states only, are recorded on the CutoverRecord."
    violationBehaviour: "An erased owner's v1 data is purged before v1 serves; a mismatch keeps the maintenance notice up until it is resolved or your decision cancels the rollback (BR9.7)."
    source: FR4.1

  - id: BR9.14
    statement: "Your decisions are recorded only through the operator tool, never through the web application."
    category: authorization
    appliesTo: MaintainerApproval, CutoverRecord, MigrationRun, MisfitDecision, ConsumerInventory, ProviderActivation, RecoveryRequest, RetainedCopy
    trigger: "any step this design reserves for you"
    logic: "IF a step this design reserves for you is decided (the go-ahead to copy v1 for a dry run, accepting or rejecting a dry run's report, a misfit decision, a consumer disposition, the v1 restart rehearsal, the switch start, the final report with its new-in-final items, a provider's real sign-in or first effect, opening admission with any provider accepted unavailable, reviewing an abort, a rollback or its cancellation, waiving a rollback's database copy, settlement, a production restore, abandoning a held production restore, a disposal date, retiring a backup volume lost for good) THEN you record it as the operator through PlatformControl's decision operation, which shows you the exact subject and binds you, the step, the subject reference and the digest of that subject in its receipt; the operator tool appends it to the ledger as a MaintainerApproval through ServiceOperations' ledger component, which admits it only with a valid receipt (BR6.10). A decision covers only the digest it names, and the latest decision for a step and subject is the current one. The web application and the application administrator can read decisions and never create one."
    violationBehaviour: "No step that needs your decision proceeds on a decision recorded any other way, or on one whose subject changed after you decided."
    source: FR4.1

  - id: BR9.15
    statement: "The profile's mode, admission, rehearsal database and backup volume change only through PlatformControl's profile operation, at the steps that call for it."
    category: authorization
    appliesTo: ProductionProfile, CutoverRecord, MigrationRun
    trigger: "the switch, opening admission, an abort or a rollback; accepting a dry run; a rehearsal database's backstop date; retiring a backup volume lost for good"
    logic: "IF the mode or admission is to change THEN it runs as PlatformControl's profile operation under operator authority, with its receipt on the CutoverRecord: rehearsal to live only while the cutover is switching, after your decision approving the final report and with the v2 host stopped; maintainer-only to open only with your decision approving the opening; live back to rehearsal, with admission back to maintainer-only, only in an abort or a rollback and only after v1 serves again. A mode change takes effect at the next v2 start; an admission change takes effect from the next request. In rehearsal mode admission is always maintainer-only. The profile's rehearsal database changes only through the same operation, run by the operator in person: it is set to a dry run's rehearsal database when your decision accepts that run. If the soak is already running, the rehearsal v2 stops before the change and starts again on the new database right after it; otherwise the rehearsal v2 first starts when the soak starts, once the complete verification has also passed on the release (BR9.3, BR10.5). It is cleared right after admission opens, and when it reaches its backstop date once the rehearsal v2 has stopped; an abort leaves it set, because the rehearsal v2 starts again on it. A rehearsal database is removed only once the profile no longer names it (BR9.17). The backup volume the profile names changes only through the same operation, run by the operator in person on your decision retiring a volume lost for good, and only to a volume that passes the volume check (BR4.10, BR6.6)."
    violationBehaviour: "A mode, admission, rehearsal database or backup volume change outside its step is refused before any effect."
    source: FR4.1

  - id: BR9.16
    statement: "Before the switch, v1 runs from a fixed checkout and its stop and restart have been rehearsed."
    category: validation
    appliesTo: CutoverRecord
    trigger: "preparing the switch; any change to v1's checkout or services"
    logic: "IF the switch is to start THEN v1's services run from a checkout at a recorded commit that development work does not change, and within the restart rehearsal window (policy) before the switch, on your decision, the operator routed the public address to the maintenance server, stopped and started every v1 named service from that checkout through service control, and confirmed that v1's health and a signed-out page answered through the public address, with the model runtime and the tunnel already running as their own accounts (BR6.11), each step with its receipt on the CutoverRecord. A later change to v1's checkout, commit or services, including the model runtime or the tunnel, voids the rehearsal. This same checkout is what an abort or a rollback starts and what the operator repairs from."
    violationBehaviour: "A switch never stops a v1 that has not been shown to start again."
    source: FR4.1

  - id: BR9.17
    statement: "Each place a copy lives has one deletion path, bounded to what that place may lose, and the last good backup is never deleted."
    category: constraint
    appliesTo: RetainedCopy, BackupSet, LedgerCopy, CatalogueEntry
    trigger: "a disposal point or backstop date reached; a failed write; the disposal pass"
    logic: "IF anything on the backup volume is to be deleted THEN only the backup agent deletes it, on its catalogue's terms and never on the ledger's word alone: it deletes only a regular file inside U8's folder that its catalogue lists for the record named, reached without following any link, never a directory, and only while the file's digest still matches the catalogue's; and only once the catalogue's own earliest disposal time has passed, or, for a copy disposed on its event (a dry-run snapshot when its run ends, a rehearsal backup set once its rehearsal database has been removed), when the operator in person asks through the in-person command; incomplete files and staging files the agent removes itself. The service account can ask the agent nothing (BR6.1). A caller can only ever extend a disposal time; bringing one forward, or deleting a file whose digest no longer matches, needs your disposal-date decision, carried out by the operator in person through the agent's in-person command. The retention floor holds whatever is asked: the agent never deletes the newest backup set with integrity passed of a database incarnation that still exists, or the newest ledger copy it verified. A set or ledger copy the floor keeps past its retainUntil records heldByFloorSince, has no date in erasure evidence (BR2.5), makes storage.capacity show degraded with last-good-backup-held and opens an incident on it, and goes at the first disposal pass after a newer one passes or its database incarnation ends; a rehearsal database is therefore removed before its backup sets, and across a production restore the old incarnation's sets stay safe because the disposal pass cannot run while the restore request is active, which it stays until a post-restore set has passed, a successor restore has taken over, nothing was recreated, or an abandonment's recreate receipt is recorded (BR4.7). After an abandonment the old incarnation's sets follow the normal floor and disposal rules: the incarnation has ended, so they go at their retainUntil, unless they were retired with a lost volume. The disposal pass runs under the standing authority after each scheduled backup and whenever the volume check passes again after failing, but never while a switch, an abort, a rollback or a production restore holds the live environment's exclusion: it asks the agent which files are due by its catalogue, has each deleted, and sets disposedAt on the record from the agent's receipt; a due file the ledger has no record of is deleted all the same and opens an incident on storage.capacity, and so does a ledger record whose disposal point the catalogue does not show, which is refused. At each pass the agent also removes any staging file that no write is using once the staging backstop (policy, one day) has passed. A catalogue that does not verify stops every write and deletion on the volume until the operator in person rebuilds it through the in-person command from the files present and their ledger records, keeping for each file the later of the two disposal times. IF a database is to be deleted THEN PlatformControl's database remove deletes only a rehearsal database, a scratch restore or an import database, recognised by its fixed name pattern, never the production database and never the rehearsal database the profile names as current. It runs at the database's event, in person, or at its backstop date under the standing authority, through the scheduler account's database login, which can drop only databases owned by the disposable-databases role; the operation itself refuses the current rehearsal database, read from the latest profile receipt in the ledger. For a rehearsal database the order is fixed: the profile is repointed or cleared first (BR9.15); the removal then waits until no backup.create or restore.verify of the rehearsal environment is active, and none is admitted meanwhile (BR4.4); then the database is removed; and only then are its backup sets disposed, because the floor stops holding them once their incarnation has ended. A rehearsal database the soak still uses at its backstop date returns the cutover to preparing (BR9.12) and opens an incident on storage.capacity until the operator in person stops the rehearsal v2, clears the profile's rehearsal database and removes it. v1's stores are deleted only by the operator in person, at the date your decision approved; once their backstop date passes with them still in place, an incident opens on storage.capacity until they are deleted. IF a disposal cannot complete (the volume missing or locked, or only part deleted) THEN the record stays undisposed with disposalPendingSince and what remains, still counted in erasure evidence (BR2.5); the next disposal pass retries it, and an incident opens on storage.capacity once a backstop date has passed. A volume lost for good is retired as BR4.10 states."
    violationBehaviour: "A forged, stale or damaged ledger record can make nothing be deleted early, outside U8's folder, through a link or past the floor; the application's account can make the agent do nothing at all; the last good backup and the last verified ledger copy are never deleted; erasure evidence discloses every undisposed copy (BR2.5)."
    source: FR4.1

  - id: BR10.1
    statement: "The whole application is verified in one composed synthetic realm."
    category: constraint
    appliesTo: VerificationRun
    trigger: "every verification run"
    logic: "IF the complete verification runs THEN it provisions one realm with every contribution and participant, the same composition production uses, with the synthetic profile and local provider fakes."
    violationBehaviour: "A run over separate per-unit realms does not count."
    source: FR3.2

  - id: BR10.2
    statement: "Verification goes through real boundaries."
    category: constraint
    appliesTo: VerificationRun
    trigger: "every verification run"
    logic: "IF a journey is verified THEN it goes through real HTTP, a real browser, the real database with owner roles, and the real workers and control loop; only outward providers are faked."
    violationBehaviour: "A journey checked through internal calls only is reported not-run."
    source: FR3.2

  - id: BR10.3
    statement: "Verification covers the cross-unit journeys, the unit's acceptance boundaries and the operating procedures."
    category: validation
    appliesTo: VerificationRun
    trigger: "every verification run"
    logic: "IF the complete verification runs THEN it covers: sign-in to library to search to paper to research to novelty to export; topics to digest; public and private isolation, with signed-out access to every private route, event stream and asset refused like a missing resource; current authority, with a session revoked during a stream and during a job; late effects, with withdrawal and consent revocation racing an in-flight digest, export and job and no effect after the revocation; durable drafts, with save, restore after reload, a two-window conflict and an account switch; the job lifecycle, with accept, progress, cancel, unknown-outcome reconciliation and the owner job list; withdrawal, reactivation and erasure across every participant reaching complete; backup and restore verification with an erased owner not revived; migration of a synthetic v1 fixture covering every misfit reason, with an idempotent second pass and a reconciling report; the cutover procedures against a synthetic v1 run from v1's own code with a local stand-in for the tunnel: a switch, an abort that has v1 serving before v2's database is emptied, a rollback that applies v2's lifecycle outcomes to v1 and ends its sessions, and a cancelled rollback; every navigation state (signed out, degraded, unavailable, administrator); owner isolation between two synthetic owners on every list, read, event and asset; and one representative defect diagnosed and repaired from a clean checkout with its regression and affected checks."
    violationBehaviour: "A missing journey makes the run incomplete, never passed."
    source: FR3.2

  - id: BR10.4
    statement: "The complete verification has its own CI lane; per-unit runners stay."
    category: policy
    appliesTo: VerificationRun
    trigger: "every change to develop"
    logic: "IF a change reaches develop THEN the complete verification lane runs; every per-unit runner and lane stays as it is."
    violationBehaviour: "A failed complete lane blocks the merge."
    source: FR3.2

  - id: BR10.5
    statement: "Readiness and release claims need passing complete evidence for the exact commit."
    category: validation
    appliesTo: VerificationRun, CutoverRecord
    trigger: "any readiness or release claim"
    logic: "IF a claim is made for a commit THEN it needs a VerificationRun with result passed for that commit; missing or failed evidence blocks the claim, and a passing run never waives an unresolved required condition (undecided misfits, missing restore evidence, unrecorded provider evidence)."
    violationBehaviour: "The claim is refused with the missing evidence named."
    source: FR4.2

  - id: BR10.6
    statement: "Accessibility evidence covers the complete application."
    category: validation
    appliesTo: VerificationRun
    trigger: "every verification run"
    logic: "IF the complete verification runs THEN it records keyboard, focus, screen-reader announcement, 320-pixel reflow and contrast evidence for every screen of the complete application."
    violationBehaviour: "A failed check makes the run failed."
    source: NFR5

  - id: BR10.7
    statement: "U8 supplies read-only production probes for the Operation stages."
    category: policy
    appliesTo: VerificationRun, ProductionProfile
    trigger: "Operation stages and the soak"
    logic: "IF production is probed THEN the probes read liveness, capability readiness and a signed-out journey only; they never create work, sign in as a person or send anything."
    violationBehaviour: "A probe that would cause an effect is refused."
    source: FR4.2
```

## Rules summary

| Group | Rules | Gist |
|---|---|---|
| Composition | BR1.1–BR1.7 | One versioned registration manifest, verified before activation. States come from evidence, never constants. One application against one database with owner roles. Conflicting schema is reconciled by its owners through new migrations, never at start. U8 owns no business entity. Earlier assemblies still boot alone. |
| Lifecycle manifest | BR2.1–BR2.7 | Ten participants, 21 scope pairs. A request completes only on evidence for every scope. ResearchWorkspace gets its own participant. TopicsDigests and ApprovedExport join with their built adapters. Backups evidence discloses every retained copy and backup set with the date the last one is gone. Restore enforcement needs a verification that covered the owner's tombstone. Requests keep their manifest revision. |
| Readiness and incidents | BR3.1–BR3.11 | Liveness, capability readiness and journey readiness stay apart. State is derived from the latest admitted observation, with stale derived from age, and renewed periodically. Observations are safe and never change outcomes. Platform status is pulled read-only. Handed-over counts become health and error rates. Incidents live in the ledger and resolve only on evidence of a stated kind: the capability back, an abort reviewed by you, a rollback's copy settled, or the environment stopped. The operator surface is administrator-and-MFA only. Logs are safe, and no external error reporter runs. The registry decides which capabilities are required; providers, the cutover check and the runtime isolation check never are, and the two checks open incidents past their tolerance, the isolation check also when it stops reporting. |
| Backup and restore | BR4.1–BR4.10 | Only backup and restore are offered. Administrators and the schedule request, and operator authority performs; production restore is never scheduled. A backup is one database's set, counted after integrity passes. Every file copy is one archive that the backup agent, running as the backup account, writes onto the encrypted backup volume: it dumps databases itself and receives everything else as a verified stream, stages only on that volume, records each file in its own catalogue, and takes a copy's kind from its command and source database and a decided date only with that decision's receipt. Only the scheduler account (its unattended commands) and the operator account (in person) may start it; the service account v2 runs as may not. Active requests of conflicting kinds never overlap, a waiting request holds nothing, and unknown outcomes are reconciled first. Verification proves erased owners stay erased up to a recorded register head and removes its scratch copy. The tombstone register survives restores, detects truncation and adopts entries a crash left past its head. A production restore needs your decision, takes its own backup after writes stop, backs up the restored database before v2 reopens, and stays active, holding the environment, until then or until a successor restore, which your decision binds to it, takes over; v2's own start check refuses while it has not authorised the start. Keys are never backed up. Each deliberate submission has its own identity. A backup volume lost for good is retired and replaced only on your decision. |
| Navigation and web | BR5.1–BR5.9 | The server resolves one navigation set. Every entry shows its real state and reason. 논문 opens from results; 작업 is a read-only job list. Owner changes clear private state. Legal pages stay public at their addresses, independent of capability states. After the switch there is one browser application. Korean, WCAG 2.2 AA. Anonymous callers see a minimal capability projection. |
| Production profile | BR6.1–BR6.12 | v2 runs as its own non-login service account, which owns one durable owner-only root outside /tmp and is granted nothing but a read-only evidence reader; the operator account (in person) and the scheduler account (unattended, ledger only) reach that root only through fixed commands, and the backup volume the profile names holds every copy of personal data; a missing backup volume degrades storage but never stops the start. Keys live in its key folders, never in backups, and are replaced only through their owners' commands. One production database, emptied only by recreating it. Local-only host, public through the tunnel, with maintainer-only admission during the switch window, except for the legal pages. Its own checkout, in a system folder, pinned to a release tag on main. A production storage budget with correct WAL measurement. Secrets from the profile environment. Production admission policy. Operator commands through the environment tool. An append-only operations ledger holds every lasting record, adopts entries a crash left past its head, and has a verified copy on the backup volume at least daily. v2's databases live in its own PostgreSQL instance, and that instance, the model runtime and the tunnel run as their own non-login accounts at local addresses no other account can serve, so all of it comes back after an authorized restart without a login. A read-only root check confirms the arrangement every renewal interval and names what failed, and installing it replaces every credential your login account held. |
| Real providers | BR7.1–BR7.8 | Real adapters in production, fakes in tests. Honest degradation, no fallback. Each outward provider's first live effect is approved by your decision in the maintainer-only window, from a recorded preview. Email within the free tier. Before the switch, outward effects reach only you. The U5 and U6 bounds lift only in live production. Assistance waits for its readiness evidence and runs only on the model the release pins. Real Google and ORCID sign-in are verified by you before admission opens. |
| Migration | BR8.1–BR8.15 | The Q13 groups that exist move; every other kind is counted and defaults to archive-only. Owners write their own records. Deterministic identities make reruns idempotent. Dependency order. Credentials carried unchanged, never weakened. First sign-in collects consent. Papers matched and converted by their owner. Embeddings reused only on proven provenance. Misfits decided by you, with anything new in the final run defaulted and approved explicitly, decisions unfrozen after an abort, and a changed decision rehearsed in a new dry run before it reaches production. Reconciling parity reports. Each dry run reads a recorded copy into its own rehearsal database; the final run only inside the switch, its snapshot kept as a retained copy. Closed accounts stay closed. Identity conflicts are misfits. Interrupted runs resume only to their phase, and an interrupted dry run can be abandoned. |
| Cutover | BR9.1–BR9.17 | v1 serves until the switch. Ten preconditions, including the consumer inventory, no unresolved incident, a rehearsed v1 restart, a fit backup volume and runtime isolation in force. A clean soak on ledger evidence. One recorded switch sequence with a maintainer-only window, aborting back to v1 until admission opens, with v1 serving before anything of v2's is removed. Everyone signs in once. A rollback window that first applies v2's withdrawals and erasures to v1 through v1's own code, and can be cancelled until v1 serves; v2's database is copied before it is emptied, unless your decision waives the copy. Settlement retires v1 and keeps its data as a dated retained copy. The real switch runs at Deployment Execution with your decisions. Every effect is a bound operation with a receipt. Every retained copy has an end. Each place a copy lives has one bounded deletion path: on the backup volume only the backup agent deletes, on its own catalogue's terms, never early on the ledger's word and never the last good backup. Your decisions are recorded only through the operator tool, and the profile's mode, admission, rehearsal database and backup volume change only at their steps. |
| Verification | BR10.1–BR10.7 | One composed synthetic realm through real boundaries, covering the cross-unit journeys, the unit's acceptance boundaries and the operating procedures, in its own CI lane. Claims need passing evidence for the exact commit. Complete accessibility evidence. Read-only production probes. |
