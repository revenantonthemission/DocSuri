# Entities — U8 complete service operations and integration

Date: 2026-10-21 (Asia/Seoul)
Unit: u8-service-operations-integration. Sources: confirmed [functional-design-questions.md](functional-design-questions.md) (Q1–Q16 and the settled items), the [NFR Requirements answers](../nfr-requirements/nfr-requirements-questions.md) Q14–Q19 that reopened this design (backup volume, accounts and runtime arrangement), [requirements FR3, FR4 and NFR1–NFR6](../../../inception/requirements-analysis/requirements.md) (`requirements.md`), [unit definition](../../../inception/units-generation/unit-of-work.md) (`unit-of-work.md`), [story map](../../../inception/units-generation/unit-of-work-story-map.md) (`unit-of-work-story-map.md`), the approved ServiceOperations, WebWorkspace and PlatformControl components (`../../../../261010-docsuri-v2-rebuild/inception/domain-design/components.md`), the frozen contracts C01, C02, C10, C11 and C13 (`../../../../261010-docsuri-v2-rebuild/inception/contract-design/contract-summary.md`), the U5 and U6 handoffs, and the current code as recorded in [functional-spec.md](functional-spec.md) § "What this design relies on".

Ownership. The approved catalogue gives ServiceOperations capability readiness, incidents and verified recovery records, and gives WebWorkspace the host composition (C01). U8 completes both. The backup agent's catalogue (CatalogueEntry) belongs to the backup-volume operations U8 adds to PlatformControl (amendment A6). Every other entity named here (Account, Paper, SavedPaper, lifecycle requests, research records and so on) stays with its owner and is referenced by stable ID only. Field names follow the frozen wire records where one exists (HostContribution, HostNavigationItem, OpsObservation, OpsIncident, OpsRecoveryRequest); additions are listed as amendments in [functional-spec.md](functional-spec.md). Where each entity is stored is fixed in § "Storage placement" below (BR6.10).

## Entity model

```yaml
entities:
  - name: "ContributionRegistration"
    description: "One contribution in the complete application's registration manifest (C01 HostContribution). The manifest is a finite, versioned build input; nothing at runtime adds, removes or edits an entry."
    attributes:
      - name: "contributionId"
        logicalType: "string"
        required: true
        unique: true
        allowedValues: ["paper-journey", "account-controls", "paper-corpus", "research-workspace", "topics-digests", "approved-export", "service-operations", "platform-control"]
      - name: "unit"
        logicalType: "enum"
        required: true
        unique: false
        allowedValues: ["U1", "U2", "U3", "U4", "U5", "U6", "U7", "U8"]
      - name: "revision"
        logicalType: "string"
        required: true
        unique: false
        constraints: "the contribution's published revision; compared at start (BR1.2)"
      - name: "schemaDigest"
        logicalType: "hash"
        required: true
        unique: false
        constraints: "digest of the contract schemas the contribution was built against; an unknown or different digest makes the contribution incompatible (BR1.2)"
      - name: "components"
        logicalType: "list<string>"
        required: true
        unique: false
        constraints: "the owning components this contribution implements, by catalogue name"
      - name: "requires"
        logicalType: "list<string>"
        required: true
        unique: false
        default: "[]"
        constraints: "contributionIds that must be active first"
      - name: "provides"
        logicalType: "list<string>"
        required: true
        unique: false
        references: "CapabilityRegistration.capabilityId"
      - name: "routes"
        logicalType: "list<string>"
        required: true
        unique: false
        default: "[]"
        constraints: "the browser routes it mounts; platform-control mounts none (BR1.1)"
      - name: "lifecycleParticipantIds"
        logicalType: "list<string>"
        required: true
        unique: false
        default: "[]"
        references: "LifecycleParticipantEntry.participantId"
      - name: "required"
        logicalType: "boolean"
        required: true
        unique: false
        constraints: "every contribution of the complete application is required in the production profile"
      - name: "activation"
        logicalType: "enum"
        required: true
        unique: false
        allowedValues: ["active", "unavailable"]
        constraints: "derived at start from BR1.2; never set by hand"
      - name: "unavailableReason"
        logicalType: "enum"
        required: false
        unique: false
        allowedValues: ["missing", "incompatible", "dependency-unavailable", "policy-unresolved"]
        constraints: "present exactly when activation is unavailable"
    entityConstraints:
      - "One manifest revision lists each contributionId once; the manifest revision is a digest of all entries (BR1.1)."
      - "platform-control is listed as the separately authorized operator surface and provides no browser route (BR1.1, BR4.2)."
    relationships:
      - target: "CapabilityRegistration"
        cardinality: "1:N"
        direction: "ContributionRegistration -> CapabilityRegistration"
      - target: "LifecycleParticipantEntry"
        cardinality: "1:N"
        direction: "ContributionRegistration -> LifecycleParticipantEntry"

  - name: "CapabilityRegistration"
    description: "One capability the application reports on: who provides it, who observes it, whether readiness requires it, how fresh its evidence must be and when a lasting problem becomes an incident. The complete set is the capability registry in functional-spec.md (BR3.11)."
    attributes:
      - name: "capabilityId"
        logicalType: "string"
        required: true
        unique: true
        constraints: "one of the registry's identifiers (BR3.11), for example account.entry, discovery.search, export, provider.resend, public.static"
      - name: "contributionId"
        logicalType: "string"
        required: true
        unique: false
        references: "ContributionRegistration.contributionId"
      - name: "owningComponent"
        logicalType: "string"
        required: true
        unique: false
      - name: "producerId"
        logicalType: "string"
        required: true
        unique: false
        constraints: "the one registered producer whose observations are admitted for this capability (BR3.4); public.static is produced by the host itself"
      - name: "required"
        logicalType: "boolean"
        required: true
        unique: false
        constraints: "as the registry states; a required capability that is unavailable, unknown or stale keeps readiness false (BR3.1); providers are never required (BR3.11)"
      - name: "renewalIntervalSeconds"
        logicalType: "integer"
        required: true
        unique: false
        min: 1
        constraints: "policy, set at NFR Requirements (BR3.3)"
      - name: "freshnessBoundSeconds"
        logicalType: "integer"
        required: true
        unique: false
        min: 1
        constraints: "policy; must exceed renewalIntervalSeconds; an older observation is stale (BR3.2)"
      - name: "incidentToleranceSeconds"
        logicalType: "integer"
        required: true
        unique: false
        min: 0
        constraints: "policy; how long a required capability may stay degraded, unknown or stale before an incident opens, and how long operations.cutover or platform.isolation may stay unavailable (BR3.7)"
    entityConstraints:
      - "Each capability belongs to exactly one contribution and has exactly one producer."
    relationships:
      - target: "CapabilityObservation"
        cardinality: "1:N"
        direction: "CapabilityRegistration -> CapabilityObservation"
      - target: "NavigationEntry"
        cardinality: "1:N"
        direction: "CapabilityRegistration -> NavigationEntry"

  - name: "NavigationEntry"
    description: "One route of the complete application's single navigation set, with its access rule and placement. The server resolves it per request (C01 host.resolveNavigation); the browser keeps no copy of the rules."
    attributes:
      - name: "routeId"
        logicalType: "string"
        required: true
        unique: true
        allowedValues: ["search", "library", "research", "novelty", "jobs", "topics", "export", "settings", "usage", "account", "operations", "paper", "privacy", "terms"]
      - name: "titleKey"
        logicalType: "string"
        required: true
        unique: false
        constraints: "Korean label key: 검색, 내 서재, 연구, 참신성 분석, 작업, 주제 구독, 내보내기, 설정, 사용량, 계정, 운영, 논문, 개인정보 처리방침, 이용약관"
      - name: "path"
        logicalType: "string"
        required: true
        unique: true
        constraints: "registered relative path; privacy and terms keep their current public addresses /privacy and /terms (BR5.6)"
      - name: "capabilityId"
        logicalType: "string"
        required: true
        unique: false
        references: "CapabilityRegistration.capabilityId"
        constraints: "privacy and terms use public.static, which is available whenever the host serves (BR5.6)"
      - name: "access"
        logicalType: "enum"
        required: true
        unique: false
        allowedValues: ["public", "signed-in", "owner", "administrator"]
        constraints: "account is owner; operations is administrator; privacy and terms are public (BR5.1, BR5.3)"
      - name: "placement"
        logicalType: "enum"
        required: true
        unique: false
        allowedValues: ["primary", "contextual", "footer"]
        constraints: "paper is contextual (opened from results), privacy and terms are footer, the rest primary (BR5.3)"
      - name: "order"
        logicalType: "integer"
        required: true
        unique: false
        min: 0
    entityConstraints:
      - "Within one manifest revision each path and each routeId occurs once."
    relationships: []

  - name: "LifecycleParticipantEntry"
    description: "One owner in the account-lifecycle manifest (C02), with the scopes it must answer for every withdraw, reactivate and erase request."
    attributes:
      - name: "participantId"
        logicalType: "enum"
        required: true
        unique: true
        allowedValues: ["AccountAccess", "Library", "Personalization", "UsageEntitlements", "PaperAssistance", "DiscoveryCitations", "ResearchWorkspace", "TopicsDigests", "ApprovedExport", "ServiceOperations"]
      - name: "scopes"
        logicalType: "list<enum>"
        required: true
        unique: false
        allowedValues: ["live_records", "derived_artifacts", "pending_work", "caches", "backups", "restore_enforcement", "external_copies"]
        constraints: "exactly the scopes in BR2.1 for each participant"
      - name: "required"
        logicalType: "boolean"
        required: true
        unique: false
        default: "true"
      - name: "adapter"
        logicalType: "enum"
        required: true
        unique: false
        allowedValues: ["registered", "absent"]
        constraints: "absent keeps every scope of the entry blocked (BR2.2)"
      - name: "manifestRevision"
        logicalType: "string"
        required: true
        unique: false
        constraints: "the lifecycle manifest revision this entry belongs to (BR2.7)"
    entityConstraints:
      - "At most 32 (participant, scope) pairs per manifest revision (current AccountAccess bound); the BR2.1 manifest has 21."
    relationships: []

  - name: "ModelEvidence"
    description: "The digest the release pins for one model v2 uses (BR6.11). It is part of the release, which is root-owned and readable by every account, so neither the models account nor your login account can change it, and the runtime isolation check's programs item covers it (BR6.12). v2's provider.models check compares it with the digest the runtime reports, at every renewal and before each model job starts."
    attributes:
      - name: "model"
        logicalType: "string"
        required: true
        unique: true
        constraints: "the model's registry name and tag, from a closed set: bge-m3:latest and qwen3:8b"
      - name: "purpose"
        logicalType: "enum"
        required: true
        unique: false
        allowedValues: ["embedding", "assistance"]
        constraints: "bge-m3:latest produces the embeddings stored under bge-m3-1024-pinned-1; qwen3:8b serves paper assistance (BR7.7)"
      - name: "digest"
        logicalType: "hash"
        required: true
        unique: false
        constraints: "the SHA-256 of the model's manifest: the hash of the manifest the model registry serves for the tag, which the runtime reports for the stored model"
    entityConstraints:
      - "Changed only by a reviewed release, installed in person (BR6.5): a model change, or a new digest for the same tag, is a new release, and installing it puts the model in place first, the way Workflow 20 step 5 does. While the runtime reports a digest other than the running release's pin, provider.models is unavailable with model-evidence-mismatch, and model work waits (BR7.2)."
      - "A model the release does not pin is never used (BR6.11)."
      - "Holds no secret."
    relationships: []

  - name: "CapabilityObservation"
    description: "One admitted observation of one capability (C11 OpsObservation). The capability's displayed state is derived from the latest one (BR3.2). Observations are re-derived continuously and are never evidence by themselves."
    attributes:
      - name: "observationId"
        logicalType: "uuid"
        required: true
        unique: true
      - name: "capability"
        logicalType: "string"
        required: true
        unique: false
        references: "CapabilityRegistration.capabilityId"
      - name: "component"
        logicalType: "string"
        required: true
        unique: false
      - name: "producerId"
        logicalType: "string"
        required: true
        unique: false
        constraints: "must equal the capability's registered producer (BR3.4)"
      - name: "observedAt"
        logicalType: "timestamp"
        required: true
        unique: false
      - name: "revision"
        logicalType: "integer"
        required: true
        unique: false
        min: 1
        constraints: "advances per capability; a duplicate observation identity is reconciled, not re-applied"
      - name: "status"
        logicalType: "enum"
        required: true
        unique: false
        allowedValues: ["available", "degraded", "unavailable", "unknown"]
      - name: "reasonKey"
        logicalType: "string"
        required: false
        unique: false
        constraints: "registered outcome code only (for example provider-unreachable, allowance-exhausted, first-effect-pending, capacity-exhausted, module-absent, runtime-isolation-lapsed, model-evidence-mismatch, capacity-approaching, internal-disk-low, internal-disk-critical); required unless status is available"
      - name: "evidenceRef"
        logicalType: "string"
        required: true
        unique: false
        constraints: "opaque reference; never private text, credentials, tokens, email addresses, titles or content (BR3.4)"
      - name: "limitations"
        logicalType: "list<string>"
        required: true
        unique: false
        default: "[]"
        constraints: "registered limitation keys, for example pre-switch-recipient-bound, semantic-search-unavailable, isolation-filter"
    entityConstraints:
      - "Stale is never stored: it is derived at read time from observedAt and the capability's freshness bound (BR3.2)."
    relationships: []

  - name: "ServiceIncident"
    description: "One incident correlating a capability problem with its diagnosis, any recovery and the evidence that closed it (C11 OpsIncident). Kept in the operations ledger so it survives restores and the move from rehearsal to live."
    attributes:
      - name: "incidentId"
        logicalType: "uuid"
        required: true
        unique: true
      - name: "environment"
        logicalType: "enum"
        required: true
        unique: false
        allowedValues: ["rehearsal", "live"]
      - name: "revision"
        logicalType: "integer"
        required: true
        unique: false
        min: 1
      - name: "capabilities"
        logicalType: "list<string>"
        required: true
        unique: false
        references: "CapabilityRegistration.capabilityId"
        min: 1
        constraints: "the abort's incident names exactly operations.cutover (BR3.7, BR9.5)"
      - name: "correlationIds"
        logicalType: "list<string>"
        required: true
        unique: false
        default: "[]"
        constraints: "opaque job, effect, observation or receipt references only"
      - name: "state"
        logicalType: "enum"
        required: true
        unique: false
        allowedValues: ["open", "investigating", "recovering", "resolved"]
      - name: "openedAt"
        logicalType: "timestamp"
        required: true
        unique: false
      - name: "openedBy"
        logicalType: "enum"
        required: true
        unique: false
        allowedValues: ["tolerance-exceeded", "job-failure-correlated", "switch-aborted", "rollback-copy-pending", "operator"]
        constraints: "rollback-copy-pending: a rollback whose database copy cannot be completed opened it; when it took over an already-open live operations.cutover incident instead, that incident keeps its own openedBy and the rollback's signal attaches (BR9.7)"
      - name: "diagnosisKey"
        logicalType: "string"
        required: false
        unique: false
        constraints: "fixed diagnosis vocabulary, for example v1-restart-failed for an abort whose v1 would not start (BR9.5); no free text with private data"
      - name: "recoveryRequestIds"
        logicalType: "list<uuid>"
        required: true
        unique: false
        default: "[]"
        references: "RecoveryRequest.recoveryRequestId"
      - name: "evidenceRefs"
        logicalType: "list<string>"
        required: true
        unique: false
        default: "[]"
        constraints: "verification evidence; at least one is required to resolve (BR3.7)"
      - name: "resolutionKind"
        logicalType: "enum"
        required: false
        unique: false
        allowedValues: ["capability-available", "abort-reviewed", "rollback-copy-settled", "environment-stopped"]
        constraints: "present exactly when resolved: capability-available needs the capability available again and any recovery verified; abort-reviewed is the only kind for the abort's incident (the one CutoverRecord.abortIncidentId names) and needs the abort settled and your review recorded; rollback-copy-settled is the only kind for a rollback's copy-pending incident (the one CutoverRecord.rollbackCopyIncidentId names) and needs the copy recorded or waived and the production database recreated, on those receipts, with no observation; environment-stopped is for any other live incident whose environment an abort or a rollback stopped (BR3.7, BR9.7)"
      - name: "resolvedAt"
        logicalType: "timestamp"
        required: false
        unique: false
    entityConstraints:
      - "At most one incident in a non-resolved state per (environment, capability); later signals attach to it (BR3.7)."
      - "The abort's incident, opened by the abort or taken over by it from an open live operations.cutover incident, is in the live environment, names operations.cutover and resolves only as abort-reviewed (BR3.7, BR9.5)."
      - "A rollback's copy-pending incident, opened by the rollback or taken over by it from an open live operations.cutover incident in the same way, is in the live environment, names operations.cutover and resolves only as rollback-copy-settled (BR3.7, BR9.7)."
    relationships:
      - target: "RecoveryRequest"
        cardinality: "1:N"
        direction: "ServiceIncident -> RecoveryRequest"

  - name: "RecoveryRequest"
    description: "A request for one of the offered recovery procedures (C11 requestRecovery), made by an administrator or by the schedule. The platform effect itself runs only under operator authority (BR4.2)."
    attributes:
      - name: "recoveryRequestId"
        logicalType: "uuid"
        required: true
        unique: true
      - name: "environment"
        logicalType: "enum"
        required: true
        unique: false
        allowedValues: ["rehearsal", "live"]
      - name: "origin"
        logicalType: "enum"
        required: true
        unique: false
        allowedValues: ["administrator", "schedule"]
        constraints: "schedule may request only backup.create and restore.verify (BR4.2)"
      - name: "incidentId"
        logicalType: "uuid"
        required: false
        unique: false
        references: "ServiceIncident.incidentId"
      - name: "operation"
        logicalType: "enum"
        required: true
        unique: false
        allowedValues: ["backup.create", "restore.verify", "restore.production"]
      - name: "targetId"
        logicalType: "string"
        required: true
        unique: false
        constraints: "the environment's database for backup.create; a BackupSet.backupId for both restore operations"
      - name: "expectedRevision"
        logicalType: "integer"
        required: true
        unique: false
        min: 0
        constraints: "backup.create: the environment's backup revision (number of recorded BackupSets for it); restore operations: the chosen set's revision; a mismatch is a conflict (BR4.9)"
      - name: "requestedBy"
        logicalType: "uuid"
        required: false
        unique: false
        references: "Account.accountId (owned by AccountAccess; by stable ID)"
        constraints: "required when origin is administrator"
      - name: "mfaVerifiedAt"
        logicalType: "timestamp"
        required: false
        unique: false
        constraints: "required when origin is administrator; must be current at request and at operator start (BR4.2)"
      - name: "submissionId"
        logicalType: "uuid"
        required: true
        unique: true
        constraints: "new for every deliberate submission, reused only by retries of that submission (BR4.9)"
      - name: "idempotencyKey"
        logicalType: "hash"
        required: true
        unique: true
        constraints: "digest of origin, requester, operation, target, expectedRevision and submissionId (BR4.9)"
      - name: "approvalId"
        logicalType: "uuid"
        required: false
        unique: false
        references: "MaintainerApproval.approvalId"
        constraints: "restore.production only, required before admission: your decision approving the exact backup and target (BR4.7, BR9.14)"
      - name: "preRestoreBackupId"
        logicalType: "uuid"
        required: false
        unique: false
        references: "BackupSet.backupId"
        constraints: "restore.production without a predecessor only: the set this request's own run took after writes stopped; nothing is recreated or restored until its integrity passes. A successor takes none; its predecessor's set is its fallback (BR4.7)"
      - name: "postRestoreBackupId"
        logicalType: "uuid"
        required: false
        unique: false
        references: "BackupSet.backupId"
        constraints: "restore.production only: the set of the restored database this request's own run took; v2 starts only once it has passed (BR4.7)"
      - name: "successorRequestId"
        logicalType: "uuid"
        required: false
        unique: false
        references: "RecoveryRequest.recoveryRequestId"
        constraints: "restore.production only: set when a held request ends because the successor your decision admitted in its place started running and took over its exclusion without a gap; until then the held request keeps the exclusion, and a successor that ends before running leaves it held (BR4.4, BR4.7)"
      - name: "predecessorRequestId"
        logicalType: "uuid"
        required: false
        unique: false
        references: "RecoveryRequest.recoveryRequestId"
        constraints: "restore.production only, for a successor: the held request it replaces, which its decision names as well as the backup and target. A successor takes no pre-restore backup and keeps its predecessor's pre-restore set as its fallback. On any failure before its restore, tombstone replay and integrity check have passed it is held in turn; a failed post-restore backup moves it to post-restore-pending like any restore (BR4.7)"
      - name: "abandonmentApprovalId"
        logicalType: "uuid"
        required: false
        unique: false
        references: "MaintainerApproval.approvalId"
        constraints: "restore.production only: your restore-abandonment decision for this held request. It is refused while a successor waits. While it is set and abandonedAt is not, an abandonment is in flight; a retry after a failed recreate uses the same decision (BR4.7, BR9.14)"
      - name: "abandonmentRecreateReceiptRef"
        logicalType: "string"
        required: false
        unique: false
        constraints: "the receipt of the abandonment's recreate, bound to abandonmentApprovalId; once recorded, the request ends failed (BR4.7, BR9.10)"
      - name: "abandonedAt"
        logicalType: "timestamp"
        required: false
        unique: false
        constraints: "set when the request ends failed after its abandonment's recreate receipt; the disposal pass is no longer held off by this request (BR9.17)"
      - name: "lossReportRef"
        logicalType: "string"
        required: false
        unique: false
        constraints: "the per-kind report, in the evidence folder, of what the abandonment lost; identifiers and counts only (BR4.7)"
      - name: "startAuthorizedAt"
        logicalType: "timestamp"
        required: false
        unique: false
        constraints: "restore.production only: recorded by the request's own last steps once its post-restore set has passed; while a production restore of the live environment is active without it, v2's start check refuses every start, whether by service control or by a launch job at boot (BR4.7, BR6.1)"
      - name: "state"
        logicalType: "enum"
        required: true
        unique: false
        allowedValues: ["requested", "awaiting-operator", "running", "verifying", "post-restore-pending", "held", "succeeded", "failed", "unknown", "cancelled", "refused", "expired"]
        constraints: "active means awaiting-operator, running, verifying, unknown, post-restore-pending or held; requested holds nothing (BR4.4). post-restore-pending and held occur only for restore.production after its database was recreated, and keep the maintenance notice up (BR4.7)"
      - name: "operatorReceiptRef"
        logicalType: "string"
        required: false
        unique: false
        constraints: "the PlatformControl receipt binding actor, operation, target and input hash (C10)"
      - name: "evidenceRefs"
        logicalType: "list<string>"
        required: true
        unique: false
        default: "[]"
      - name: "createdAt"
        logicalType: "timestamp"
        required: true
        unique: false
      - name: "updatedAt"
        logicalType: "timestamp"
        required: true
        unique: false
    entityConstraints:
      - "Per environment, at most one production-affecting request (backup.create of the environment's database, restore.production) and at most one restore.verify is active, whatever the origin; none is admitted while a switch, an abort or a rollback holds the live environment's exclusion (BR4.4)."
      - "A request in requested holds nothing and expires if it is not admitted within the recovery start bound (BR4.4)."
      - "restore.production cannot leave requested without approvalId; its pre-restore backup (except for a successor, which takes none) and its post-restore backup are steps of its own run, not separate requests. So are its recreate (at most once, at its step, bound to its receipt), an abandonment's recreate (bound to your abandonment decision as well), and starting v2 again (BR4.7, BR9.10)."
    relationships:
      - target: "BackupSet"
        cardinality: "N:1"
        direction: "RecoveryRequest -> BackupSet"
      - target: "MaintainerApproval"
        cardinality: "N:1"
        direction: "RecoveryRequest -> MaintainerApproval"

  - name: "BackupSet"
    description: "One backup of one environment's database, with its integrity result and retention. Key material is never part of a set (BR4.8)."
    attributes:
      - name: "backupId"
        logicalType: "uuid"
        required: true
        unique: true
      - name: "environment"
        logicalType: "enum"
        required: true
        unique: false
        allowedValues: ["rehearsal", "live"]
        constraints: "rehearsal sets back up the rehearsal database during the soak; live sets back up the production database"
      - name: "revision"
        logicalType: "integer"
        required: true
        unique: false
        min: 1
        constraints: "the environment's backup revision this set created (BR4.9)"
      - name: "trigger"
        logicalType: "enum"
        required: true
        unique: false
        allowedValues: ["scheduled", "requested", "pre-restore", "post-restore", "first-live"]
        constraints: "pre-restore and post-restore sets are taken inside a production restore's own run, before the restore and of the restored database (BR4.7); first-live by the switch (BR9.4)"
      - name: "recoveryRequestId"
        logicalType: "uuid"
        required: false
        unique: false
        references: "RecoveryRequest.recoveryRequestId"
        constraints: "the request whose run produced the set (scheduled, requested, pre-restore and post-restore sets); absent for the first-live set, whose receipt is on the CutoverRecord"
      - name: "sourceCopyId"
        logicalType: "uuid"
        required: false
        unique: false
        references: "RetainedCopy.copyId"
        constraints: "rehearsal sets only: the rehearsal-database retained copy the set backs up; the set is disposed with it (BR9.12)"
      - name: "takenAt"
        logicalType: "timestamp"
        required: true
        unique: false
      - name: "checksum"
        logicalType: "hash"
        required: true
        unique: false
      - name: "sizeBytes"
        logicalType: "integer"
        required: true
        unique: false
        min: 0
      - name: "sourceDatabaseBytes"
        logicalType: "integer"
        required: true
        unique: false
        min: 0
        constraints: "the source database's size, indexes included, when the agent dumped it; the internal-disk guard reads it before a restore verification (BR6.6)"
      - name: "location"
        logicalType: "string"
        required: true
        unique: false
        constraints: "the set's one archive file (a PostgreSQL custom-format dump the backup agent made itself) in the archives folder of U8's folder on the backup volume the production profile names; written, read back and deleted only by the backup agent (BR4.3, BR9.17)"
      - name: "databaseIncarnation"
        logicalType: "string"
        required: true
        unique: false
        constraints: "the database the agent dumped: its cluster's identifier, its name and its object id; the retention floor protects the newest passed set of each incarnation that still exists (BR9.17)"
      - name: "stagingLocation"
        logicalType: "string"
        required: true
        unique: false
        constraints: "where the agent first wrote the dump, in the staging folder on the backup volume; recorded before anything is written (BR4.3)"
      - name: "stagingRemovedAt"
        logicalType: "timestamp"
        required: false
        unique: false
        constraints: "set when the agent removes the staging file after the written copy's digest is verified, or by its staging sweep after a failed write (BR4.3, BR9.17)"
      - name: "retainUntil"
        logicalType: "timestamp"
        required: true
        unique: false
        constraints: "fixed when the set is written, from the backup agent's own retention policy (policy), and repeated from its catalogue; a caller can only extend it (BR4.3, BR9.17)"
      - name: "integrity"
        logicalType: "enum"
        required: true
        unique: false
        allowedValues: ["unchecked", "passed", "failed"]
        constraints: "the backup agent's own check of its dump (BR4.3); a backup counts only when passed"
      - name: "operatorReceiptRef"
        logicalType: "string"
        required: true
        unique: false
      - name: "heldByFloorSince"
        logicalType: "timestamp"
        required: false
        unique: false
        constraints: "set while the retention floor keeps the set past its retainUntil as the newest passed set of its database incarnation; cleared when it is disposed (BR9.17)"
      - name: "disposalPendingSince"
        logicalType: "timestamp"
        required: false
        unique: false
        constraints: "set when the set's disposal point is reached but its disposal could not complete; cleared by disposedAt (BR9.17)"
      - name: "disposedAt"
        logicalType: "timestamp"
        required: false
        unique: false
        constraints: "set from the backup agent's receipt at the disposal pass after retainUntil or, for a rehearsal set, with its rehearsal database (BR9.17)"
      - name: "retiredWithVolumeAt"
        logicalType: "timestamp"
        required: false
        unique: false
        constraints: "set, in place of disposedAt, when the volume holding the set is retired as lost for good (BR4.10)"
    entityConstraints:
      - "A set is never edited after integrity is passed; a failed set is kept as evidence and never restored."
      - "Until disposedAt or retiredWithVolumeAt, every set that may hold an owner's data, and its staging file until stagingRemovedAt, is counted in that owner's backups evidence (BR2.5)."
    relationships:
      - target: "RestoreVerification"
        cardinality: "1:N"
        direction: "BackupSet -> RestoreVerification"
      - target: "LedgerCopy"
        cardinality: "1:1"
        direction: "BackupSet -> LedgerCopy"
      - target: "CatalogueEntry"
        cardinality: "1:1"
        direction: "BackupSet -> CatalogueEntry"

  - name: "LedgerCopy"
    description: "One read-only copy of the operations ledger on the backup volume, streamed by the ledger component to the backup agent with every backup set and on its own on any day no set was taken, so the ledger always has a copy off the internal disk (BR6.10)."
    attributes:
      - name: "ledgerCopyId"
        logicalType: "uuid"
        required: true
        unique: true
      - name: "backupId"
        logicalType: "uuid"
        required: false
        unique: true
        references: "BackupSet.backupId"
        constraints: "the set this copy accompanies; absent for a copy taken on its own"
      - name: "takenAt"
        logicalType: "timestamp"
        required: true
        unique: false
      - name: "location"
        logicalType: "string"
        required: true
        unique: false
        constraints: "the copy's archive file in the archives folder of U8's folder on the backup volume; written, read back and deleted only by the backup agent (BR4.3, BR9.17)"
      - name: "stagingLocation"
        logicalType: "string"
        required: true
        unique: false
        constraints: "where the agent first wrote the stream, in the staging folder on the backup volume; recorded before anything is written (BR4.3)"
      - name: "stagingRemovedAt"
        logicalType: "timestamp"
        required: false
        unique: false
        constraints: "set when the agent removes the staging file, or by its staging sweep after a failed write (BR4.3, BR9.17)"
      - name: "digest"
        logicalType: "hash"
        required: true
        unique: false
      - name: "headSequence"
        logicalType: "integer"
        required: true
        unique: false
        min: 0
        constraints: "the ledger head the copy reaches"
      - name: "headDigest"
        logicalType: "hash"
        required: true
        unique: false
      - name: "verifiedAt"
        logicalType: "timestamp"
        required: false
        unique: false
        constraints: "set by the backup agent when the written copy's digest matched the sender's and its chain verified up to headSequence; only a verified copy can be used to repair the ledger, and the retention floor counts only verified copies (BR6.10, BR9.17)"
      - name: "retainUntil"
        logicalType: "timestamp"
        required: true
        unique: false
        constraints: "fixed when the copy is written, from the backup agent's own retention policy: the same as its set's, or a daily set's for a copy taken on its own; a caller can only extend it (BR9.17)"
      - name: "heldByFloorSince"
        logicalType: "timestamp"
        required: false
        unique: false
        constraints: "set while the retention floor keeps the copy past its retainUntil as the newest verified ledger copy (BR9.17)"
      - name: "disposalPendingSince"
        logicalType: "timestamp"
        required: false
        unique: false
      - name: "disposedAt"
        logicalType: "timestamp"
        required: false
        unique: false
      - name: "retiredWithVolumeAt"
        logicalType: "timestamp"
        required: false
        unique: false
        constraints: "set, in place of disposedAt, when the volume holding the copy is retired as lost for good (BR4.10)"
      - name: "operatorReceiptRef"
        logicalType: "string"
        required: true
        unique: false
    entityConstraints:
      - "Holds the same identifiers as the ledger and nothing more; no content, email address or name."
      - "Repair uses the newest copy with verifiedAt present whose chain still verifies up to its headSequence, read back through the backup agent (BR6.10)."
    relationships:
      - target: "CatalogueEntry"
        cardinality: "1:1"
        direction: "LedgerCopy -> CatalogueEntry"

  - name: "RestoreVerification"
    description: "One restore of a backup set into a scratch target, proving integrity and that every owner tombstoned up to a stated register position stays erased."
    attributes:
      - name: "verificationId"
        logicalType: "uuid"
        required: true
        unique: true
      - name: "environment"
        logicalType: "enum"
        required: true
        unique: false
        allowedValues: ["rehearsal", "live"]
      - name: "backupId"
        logicalType: "uuid"
        required: true
        unique: false
        references: "BackupSet.backupId"
      - name: "startedAt"
        logicalType: "timestamp"
        required: true
        unique: false
      - name: "finishedAt"
        logicalType: "timestamp"
        required: false
        unique: false
      - name: "registerHeadSequence"
        logicalType: "integer"
        required: true
        unique: false
        min: 0
        constraints: "the highest tombstone sequence replayed and checked, read from the register head when the verification started (BR4.5)"
      - name: "registerHeadDigest"
        logicalType: "hash"
        required: true
        unique: false
      - name: "integrity"
        logicalType: "enum"
        required: true
        unique: false
        allowedValues: ["passed", "failed"]
      - name: "erasedOwnersSurviving"
        logicalType: "integer"
        required: true
        unique: false
        min: 0
        constraints: "must be 0 for a verified result (BR4.5)"
      - name: "result"
        logicalType: "enum"
        required: true
        unique: false
        allowedValues: ["verified", "failed"]
      - name: "evidenceRef"
        logicalType: "string"
        required: true
        unique: false
      - name: "scratchRemovedAt"
        logicalType: "timestamp"
        required: false
        unique: false
        constraints: "present once the same operation has removed the scratch target; a verification whose scratch target could not be removed is failed, and the target becomes a retained copy until the operator removes it (BR4.5, BR9.12)"
    entityConstraints:
      - "result is verified only when integrity passed, erasedOwnersSurviving is 0 and scratchRemovedAt is present."
    relationships: []

  - name: "RestoreTombstone"
    description: "One entry of the restore-enforcement register: the stable identity of an owner whose erasure was accepted. Kept in the operations ledger, outside every database backup, and never rolled back by a restore (BR4.6)."
    attributes:
      - name: "sequence"
        logicalType: "integer"
        required: true
        unique: true
        min: 1
        constraints: "append-only, gap-free"
      - name: "accountId"
        logicalType: "uuid"
        required: true
        unique: true
        references: "Account.accountId (owned by AccountAccess; by stable ID)"
      - name: "lifecycleRequestId"
        logicalType: "uuid"
        required: true
        unique: true
        references: "lifecycle request (owned by AccountAccess; by stable ID)"
      - name: "appendedAt"
        logicalType: "timestamp"
        required: true
        unique: false
      - name: "digest"
        logicalType: "hash"
        required: true
        unique: false
        constraints: "chains the previous entry's digest"
    entityConstraints:
      - "Holds identifiers and times only; no email, name or content."
      - "The register head (count and head digest) is replaced atomically after each synced append and recorded in every erase evidence and restore verification, so a truncated tail is detected (BR4.6)."
      - "Valid entries a crash left beyond the head are adopted and the head advanced; only the last entry beyond the head may be a torn append, which is discarded with a record (BR4.6)."
    relationships: []

  - name: "RetainedCopy"
    description: "One copy that may hold personal data outside the live service, recorded before anything is written to it: a dry run's copy of v1, a rehearsal database, the import database a run reads its snapshot through, a scratch restore its verification could not remove, the v1 final snapshot, v1's stopped stores, or a production database kept after a rollback (BR9.12). Rehearsal backup sets are BackupSets linked to their rehearsal database's copy."
    attributes:
      - name: "copyId"
        logicalType: "uuid"
        required: true
        unique: true
      - name: "kind"
        logicalType: "enum"
        required: true
        unique: false
        allowedValues: ["dry-run-snapshot", "rehearsal-database", "import-database", "scratch-restore", "v1-final-snapshot", "v1-stores", "rolled-back-v2-database"]
      - name: "sourceRef"
        logicalType: "string"
        required: true
        unique: false
        constraints: "the record that made or kept it: a MigrationRun.runId, a RestoreVerification.verificationId or the CutoverRecord.cutoverId"
      - name: "createdAt"
        logicalType: "timestamp"
        required: true
        unique: false
      - name: "checksum"
        logicalType: "hash"
        required: false
        unique: false
        constraints: "for snapshot and archive kinds, filled in when the copy completes; absent while a copy runs, for a copy cut short, and for a rehearsal database, which changes while the soak runs"
      - name: "completedAt"
        logicalType: "timestamp"
        required: false
        unique: false
        constraints: "snapshot kinds: when copying finished and the checksums were recorded; an import reads only a completed snapshot, and an incomplete one is disposed through this record (BR8.15, BR9.12)"
      - name: "sourceDatabaseBytes"
        logicalType: "integer"
        required: false
        unique: false
        min: 0
        constraints: "for a dry-run snapshot or the v1 final snapshot: v1's database size, indexes included, when the agent dumped it; the internal-disk guard reads it before the import restore (BR6.6)"
      - name: "locations"
        logicalType: "list<string>"
        required: true
        unique: false
        min: 1
        constraints: "every place the copy occupies (databases, index, object prefixes, files); a file copy is one archive file per source (a PostgreSQL custom-format dump the backup agent made itself, or a tar archive with a manifest of its members' checksums) in the archives folder of U8's folder on the backup volume, written and deleted only by the backup agent, and databases are in PostgreSQL (BR4.3, BR9.17); disposal deletes exactly these, each by its place's one deletion path (BR9.17), and no application route or code reads them"
      - name: "stagingLocation"
        logicalType: "string"
        required: false
        unique: false
        constraints: "file copies only: where the backup agent first wrote each file, in the staging folder on the backup volume; recorded before anything is written there (BR4.3)"
      - name: "stagingRemovedAt"
        logicalType: "timestamp"
        required: false
        unique: false
        constraints: "set when the agent removes the staging files after the written copies' digests are verified, or by its staging sweep after a failed write, within the one-day staging backstop (BR4.3, BR9.17)"
      - name: "disposeAfter"
        logicalType: "timestamp"
        required: true
        unique: false
        constraints: "for v1-final-snapshot, v1-stores and rolled-back-v2-database: the disposal date your decision approved (policy), no earlier than the end of the rollback window for v1-stores; for the other kinds: the backstop date (policy) by which the copy is disposed even if its disposal event never comes (BR9.12). For a file copy the date is fixed in the backup agent's catalogue when the file is written, after PlatformControl has checked it against the cited decision's receipt and subject digest and the agent against its minimum for the kind; only the operator in person can bring it forward (BR4.3, BR9.17)"
      - name: "disposalApprovalId"
        logicalType: "uuid"
        required: false
        unique: false
        references: "MaintainerApproval.approvalId"
        constraints: "required for the kinds whose disposal date you approve: the decision of the step that created the copy (switch start, admission opening or rollback), or a later disposal-date decision that changed it (BR9.12)"
      - name: "disposalPendingSince"
        logicalType: "timestamp"
        required: false
        unique: false
        constraints: "set when the disposal point is reached but the disposal could not complete (volume missing or locked, or only part deleted); the record stays counted in erasure evidence until disposedAt (BR9.17)"
      - name: "disposedAt"
        logicalType: "timestamp"
        required: false
        unique: false
      - name: "disposalReceiptRef"
        logicalType: "string"
        required: false
        unique: false
        constraints: "the receipt of PlatformControl's disposal operation, carrying the backup agent's receipt for files on the backup volume; present with disposedAt"
      - name: "retiredWithVolumeAt"
        logicalType: "timestamp"
        required: false
        unique: false
        constraints: "set, in place of disposedAt, when the volume holding the copy's files is retired as lost for good; its receipt is your retirement decision's (BR4.10)"
      - name: "returnedToServiceAt"
        logicalType: "timestamp"
        required: false
        unique: false
        constraints: "v1-stores only: set when a rollback returns v1 to service; the record then stops counting as a retained copy (BR9.7)"
    entityConstraints:
      - "Recorded, with every location the copy will occupy, before anything is written to it; disposal deletes exactly the listed locations, each by its place's one deletion path, and keeps the record with disposedAt (BR9.12, BR9.17)."
      - "Until it is disposed, retired with its volume or returned to service, a copy that may hold an owner's data is counted in that owner's backups evidence (BR2.5)."
    relationships:
      - target: "BackupSet"
        cardinality: "1:N"
        direction: "RetainedCopy -> BackupSet"
      - target: "CatalogueEntry"
        cardinality: "1:N"
        direction: "RetainedCopy -> CatalogueEntry"

  - name: "CatalogueEntry"
    description: "One file in U8's folder on the backup volume as the backup agent's own catalogue records it. The catalogue, not the operations ledger, decides what may be deleted there and when (BR4.3, BR9.17)."
    attributes:
      - name: "path"
        logicalType: "string"
        required: true
        unique: true
        constraints: "relative to U8's folder: a file in the archives folder, or one in the staging folder while it is written; never outside U8's folder"
      - name: "recordId"
        logicalType: "uuid"
        required: true
        unique: false
        constraints: "the BackupSet, LedgerCopy or RetainedCopy the file belongs to"
      - name: "recordKind"
        logicalType: "enum"
        required: true
        unique: false
        allowedValues: ["live-backup-set", "rehearsal-backup-set", "ledger-copy", "dry-run-snapshot", "v1-final-snapshot", "rolled-back-v2-database"]
        constraints: "fixed by the command and the source database through the agent's own mapping, never by what a caller says: the unattended backup command gives a live set from the production database and a rehearsal set from a database matching the rehearsal pattern; the unattended ledger-copy command gives a ledger copy; the in-person snapshot command gives a dry-run or final snapshot of v1's database; the in-person rollback copy command gives a rolled-back database's copy of the production database (BR4.3)"
      - name: "role"
        logicalType: "enum"
        required: true
        unique: false
        allowedValues: ["archive", "staging"]
      - name: "sizeBytes"
        logicalType: "integer"
        required: false
        unique: false
        min: 0
      - name: "digest"
        logicalType: "hash"
        required: false
        unique: false
        constraints: "set when the file is written; a deletion goes ahead only while the file still has this digest (BR9.17)"
      - name: "databaseIncarnation"
        logicalType: "string"
        required: false
        unique: false
        constraints: "dumps only: the cluster identifier, database name and object id the agent dumped"
      - name: "integrity"
        logicalType: "enum"
        required: true
        unique: false
        allowedValues: ["unchecked", "passed", "failed"]
        constraints: "the agent's own check: a dump's table of contents, a ledger copy's chain up to its head (BR4.3, BR6.10)"
      - name: "earliestDisposalAt"
        logicalType: "timestamp"
        required: true
        unique: false
        constraints: "fixed when the entry is made: retainUntil from the agent's own retention policy for a set or ledger copy; for a v1 final snapshot or a rolled-back database's copy, the date your decision approved, checked by PlatformControl against that decision's receipt and subject digest and refused by the agent when it is earlier than the agent's own minimum for the kind (policy); and the backstop date for the rest. A caller can only extend it, and only the in-person command brings it forward (BR4.3, BR9.17)"
      - name: "decisionReceiptRef"
        logicalType: "string"
        required: false
        unique: false
        constraints: "for a v1 final snapshot or a rolled-back database's copy: the receipt of the decision whose date earliestDisposalAt carries, and of any later disposal-date decision that changed it (BR9.14)"
      - name: "state"
        logicalType: "enum"
        required: true
        unique: false
        allowedValues: ["writing", "written", "held-by-floor", "disposed"]
        constraints: "a catalogue lost with its volume is not updated; its records are closed in the ledger instead (BR4.10)"
      - name: "enteredAt"
        logicalType: "timestamp"
        required: true
        unique: false
      - name: "disposedAt"
        logicalType: "timestamp"
        required: false
        unique: false
      - name: "previousDigest"
        logicalType: "hash"
        required: true
        unique: false
        constraints: "the digest of the catalogue entry before this one; the chain must verify before any write or deletion (BR6.6, BR9.17)"
    entityConstraints:
      - "Written only by the backup agent, append-only: a change is a new version of the entry, and an earlier disposal time never replaces a later one except through the in-person command."
      - "Holds no content of the file, and no name or email address."
    relationships: []

  - name: "IsolationCheckResult"
    description: "One result of the runtime isolation check (BR6.12). The root check writes it into the root-owned isolation evidence folder, which every account can read and no other account can write. ServiceOperations reads the latest one as platform.isolation, and the migration tool always reads it directly from that folder (BR8.11)."
    attributes:
      - name: "resultId"
        logicalType: "uuid"
        required: true
        unique: true
      - name: "checkedAt"
        logicalType: "timestamp"
        required: true
        unique: false
        constraints: "when the check ran; a result older than platform.isolation's freshness bound (policy) is stale for the capability (BR3.2) and for the dry-run gate (BR8.11)"
      - name: "items"
        logicalType: "list<object>"
        required: true
        unique: false
        constraints: "one entry per item (programs, files, accounts, database, filter, volume, backups, boot), each with passed and, when it failed, a fixed reason key; no secrets and no paths outside the arrangement's folders"
      - name: "stopRecords"
        logicalType: "list<object>"
        required: true
        unique: false
        default: "[]"
        constraints: "each valid stop record found: label, stoppedAt, the service-control receipt it cites and expiresAt (BR6.12)"
      - name: "passed"
        logicalType: "boolean"
        required: true
        unique: false
        constraints: "true only when every item passed"
      - name: "digest"
        logicalType: "hash"
        required: true
        unique: false
        constraints: "SHA-256 of the result's canonical JSON"
    entityConstraints:
      - "Written only by the root check, kept for its bounded period (policy) and then deleted by the check itself; never written to the ledger, which keeps only the incidents about it (BR3.7)."
    relationships: []

  - name: "MaintainerApproval"
    description: "One decision of yours on a step this design reserves for you, recorded only through PlatformControl's decision operation by the operator and appended to the operations ledger. The web application reads decisions but never creates one (BR9.14)."
    attributes:
      - name: "approvalId"
        logicalType: "uuid"
        required: true
        unique: true
      - name: "step"
        logicalType: "enum"
        required: true
        unique: false
        allowedValues: ["dry-run-go-ahead", "dry-run-report", "misfit-decision", "consumer-disposition", "v1-restart-rehearsal", "switch-start", "final-report", "provider-sign-in", "provider-first-effect", "admission-opening", "abort-review", "rollback", "rollback-cancel", "rollback-copy-waiver", "settlement", "production-restore", "restore-abandonment", "disposal-date", "backup-volume-retirement"]
      - name: "subjectRef"
        logicalType: "string"
        required: true
        unique: false
        constraints: "the record decided on: a runId, a (kind, reason), a consumer, the cutoverId, a provider, a recoveryRequestId, a copyId or the backup volume's identity"
      - name: "subjectDigest"
        logicalType: "hash"
        required: true
        unique: false
        constraints: "digest of exactly what you were shown: the report, the decision and its mapping rule, the disposition, the first effect's recorded preview, the backup and target (and, for a successor restore, the held request it replaces), the disposal date (with any digest mismatch the backup agent found), the per-kind counts a rollback copy waiver gives up, the per-kind state a restore abandonment gives up, every passed set that remains and the fact that v2 then starts on an empty database, the records on a volume to retire and its replacement, or the facts for the step, such as which providers an opening accepts unavailable"
      - name: "decision"
        logicalType: "enum"
        required: true
        unique: false
        allowedValues: ["approved", "declined"]
      - name: "recordedAt"
        logicalType: "timestamp"
        required: true
        unique: false
      - name: "operatorReceiptRef"
        logicalType: "string"
        required: true
        unique: false
        constraints: "the PlatformControl receipt binding you as the operator, the step, the subject reference and the subject digest (C10)"
    entityConstraints:
      - "A decision applies only to the subject digest it names; a changed subject needs a new decision."
      - "The latest decision for a (step, subjectRef) is the current one; an earlier one is never edited."
      - "An administrator session is not operator authority, and no web route records a decision (BR4.2, BR9.14)."
    relationships: []

  - name: "ConsumerInventory"
    description: "The inventory of every client of v1's routes, with the disposition you approved for each, required before the switch (BR9.11)."
    attributes:
      - name: "inventoryId"
        logicalType: "uuid"
        required: true
        unique: true
      - name: "observedFrom"
        logicalType: "timestamp"
        required: true
        unique: false
      - name: "observedUntil"
        logicalType: "timestamp"
        required: true
        unique: false
        constraints: "the observation window is a policy value"
      - name: "consumers"
        logicalType: "list<object>"
        required: true
        unique: false
        constraints: "each {clientRef, routesUsed, source: observed|known, disposition: moves-with-v2|retired-with-v1|informed|accepted-to-break, approvalId}; approvalId references the MaintainerApproval recording your decision on that disposition (BR9.14); clientRef is an opaque client description, never a person's identity"
      - name: "complete"
        logicalType: "boolean"
        required: true
        unique: false
        constraints: "true only when every consumer has an approved disposition"
    entityConstraints:
      - "Exactly one inventory is current; a new observation window creates a new one."
    relationships: []

  - name: "ProductionProfile"
    description: "The durable environment manifest of the production profile (Q5): where its state lives, which database it uses, how it is reached, who it admits and which release it runs."
    attributes:
      - name: "profileId"
        logicalType: "enum"
        required: true
        unique: true
        allowedValues: ["production"]
      - name: "mode"
        logicalType: "enum"
        required: true
        unique: false
        allowedValues: ["rehearsal", "live"]
        constraints: "rehearsal before the switch (rehearsal database, BR7.5 bound); live from the switch's live start (BR9.4); changed only through PlatformControl's profile operation (BR9.15)"
      - name: "admission"
        logicalType: "enum"
        required: true
        unique: false
        allowedValues: ["maintainer-only", "open"]
        constraints: "always maintainer-only in rehearsal mode and during the switch's verification window; open only after your opening decision; changed only through PlatformControl's profile operation (BR9.15)"
      - name: "root"
        logicalType: "path"
        required: true
        unique: true
        constraints: "absolute, outside /tmp, owner-only, not a link (BR6.1)"
      - name: "backupVolume"
        logicalType: "string"
        required: true
        unique: false
        constraints: "the encrypted backup volume's mount point and volume identity (today DocSuri_Backup on the external drive); checked at every start as far as the service account can see; ServiceOperations compares it with the volume identity the backup agent's status check reports for the agent's own configuration, and the agent never reads the profile (BR6.1, BR6.6); changed only by PlatformControl's profile operation on your decision retiring a volume lost for good (BR4.10, BR9.15)"
      - name: "backupFolder"
        logicalType: "string"
        required: true
        unique: false
        constraints: "U8's folder on the backup volume, docsuri-v2 at its top level, holding the archives folder, the staging folder and the backup agent's catalogue; owned by the backup account; neither it nor any folder above it carries the earlier tool's cleanup marker (BR6.6)"
      - name: "backupAccount"
        logicalType: "string"
        required: true
        unique: false
        constraints: "the dedicated OS account the backup agent runs as, which alone owns the backup volume and writes, reads back and deletes anything in U8's folder; never the service account (BR4.3)"
      - name: "serviceAccount"
        logicalType: "string"
        required: true
        unique: false
        constraints: "the dedicated, non-login OS account v2's host, workers, scheduler and maintenance server run as, as system launch jobs with fixed labels; it owns root, holds only PlatformControl's bounded evidence reader, and is granted no command as any other account (BR3.5, BR6.1)"
      - name: "schedulerAccount"
        logicalType: "string"
        required: true
        unique: false
        constraints: "the dedicated, non-login OS account the standing authority's system launch job runs as; it alone holds the unattended grants (the backup agent's unattended commands, the ledger component's fixed command, PlatformControl's standing operations, the read-only runtime isolation check, and a database login in v2's PostgreSQL instance that reads scratch databases and can drop only databases owned by the disposable-databases role) and holds nothing in person (BR4.2, BR6.11)"
      - name: "databaseAccount"
        logicalType: "string"
        required: true
        unique: false
        constraints: "the dedicated, non-login OS account whose system launch job runs v2's own PostgreSQL instance; it owns the instance's data folder (owner-only, in a system folder) and runs nothing else (BR6.11)"
      - name: "databaseInstance"
        logicalType: "string"
        required: true
        unique: false
        constraints: "the loopback address of v2's own PostgreSQL instance, which holds the production, rehearsal, scratch and import databases and authenticates every login with SCRAM; never v1's data plane (BR6.3, BR6.11)"
      - name: "modelsAccount"
        logicalType: "string"
        required: true
        unique: false
        constraints: "the dedicated, non-login OS account whose system launch job runs the model runtime v1 and v2 share; it owns the models folder (BR6.11)"
      - name: "tunnelAccount"
        logicalType: "string"
        required: true
        unique: false
        constraints: "the dedicated, non-login OS account whose system launch job runs the tunnel; it alone can read the tunnel's credentials, while the configurations it runs from are root-owned and the active one changes only through PlatformControl's tunnel routing, in person (BR6.11, BR9.10)"
      - name: "tunnelOrigins"
        logicalType: "list<string>"
        required: true
        unique: false
        allowedValues: ["v1-web", "v2-host", "maintenance"]
        constraints: "the three registered origins the tunnel can route the public address to, each a root-owned configuration in the arrangement's configuration folder; the routing command accepts only these names and makes one of them active (BR6.11, BR9.10)"
      - name: "configurationFolder"
        logicalType: "path"
        required: true
        unique: true
        constraints: "the root-owned folder holding the tunnel's registered configurations and active choice, the packet filter's rules and service control's stop records; no other account can write to it (BR6.11, BR6.12)"
      - name: "releaseCheckout"
        logicalType: "path"
        required: true
        unique: true
        constraints: "the production clone's system folder, outside every home folder, holding the Python runtime and every dependency the release runs with; readable by the service account and changed only by the release path with administrator rights (BR6.5, BR6.11)"
      - name: "databaseName"
        logicalType: "string"
        required: true
        unique: true
        constraints: "the one production database, in v2's own PostgreSQL instance (databaseInstance); distinct from v1's database and from every synthetic realm (BR6.3)"
      - name: "rehearsalDatabaseName"
        logicalType: "string"
        required: false
        unique: false
        constraints: "the rehearsal database of the accepted dry run the soak runs on, following the rehearsal databases' fixed name pattern; set by PlatformControl's profile operation when your decision accepts a dry run, cleared right after admission opens and when it reaches its backstop date, and left set by an abort; a rehearsal database is removed only once this field no longer names it (BR8.11, BR9.15, BR9.17)"
      - name: "bindAddress"
        logicalType: "string"
        required: true
        unique: false
        allowedValues: ["127.0.0.1"]
      - name: "localPort"
        logicalType: "integer"
        required: true
        unique: true
        constraints: "distinct from v1's ports, the maintenance server's port and every synthetic port"
      - name: "publicOrigin"
        logicalType: "string"
        required: true
        unique: false
        allowedValues: ["https://docsuri.rvnnt.dev"]
      - name: "releaseTag"
        logicalType: "string"
        required: true
        unique: false
        constraints: "a release tag on main (BR6.5)"
      - name: "releaseCommit"
        logicalType: "string"
        required: true
        unique: false
      - name: "createdAt"
        logicalType: "timestamp"
        required: true
        unique: false
    entityConstraints:
      - "No expiry field: the profile is durable, unlike the synthetic 24-hour profiles."
      - "Holds no secret: secrets live in the profile's private environment and key folders (BR6.2, BR6.7)."
    relationships:
      - target: "ProviderActivation"
        cardinality: "1:N"
        direction: "ProductionProfile -> ProviderActivation"

  - name: "ProviderActivation"
    description: "The production state of one real provider, including whether its first outward effect and, for sign-in providers, its first real sign-in have been verified (Q9)."
    attributes:
      - name: "provider"
        logicalType: "enum"
        required: true
        unique: true
        allowedValues: ["google", "orcid", "resend", "models", "notion"]
      - name: "outward"
        logicalType: "boolean"
        required: true
        unique: false
        constraints: "true for resend and notion, whose effects reach people or places outside DocSuri (BR7.3)"
      - name: "state"
        logicalType: "enum"
        required: true
        unique: false
        allowedValues: ["unconfigured", "held", "active", "degraded", "unavailable"]
        constraints: "held shows as degraded with reason first-effect-pending (outward) or sign-in-unverified (google, orcid) (BR7.3, BR7.8)"
      - name: "approvalContentHash"
        logicalType: "hash"
        required: false
        unique: false
        constraints: "outward providers: the digest of the held first effect's recorded preview that your decision approved (BR7.3)"
      - name: "approvalId"
        logicalType: "uuid"
        required: false
        unique: false
        references: "MaintainerApproval.approvalId"
        constraints: "the decision that approved the first effect (outward) or recorded your real sign-in (google, orcid) in the current switch (BR9.14); cleared with approvedAt when an abort or a rollback returns the profile to rehearsal"
      - name: "approvedAt"
        logicalType: "timestamp"
        required: false
        unique: false
        constraints: "outward providers: your approval; sign-in providers: your verified real sign-in; holds only for the switch it was given in and is cleared by an abort or a rollback (BR7.3, BR7.8)"
      - name: "allowanceRemaining"
        logicalType: "map<string, integer>"
        required: false
        unique: false
        constraints: "resend only: remaining daily and monthly sends under the free tier (BR7.4)"
      - name: "limitations"
        logicalType: "list<string>"
        required: true
        unique: false
        default: "[]"
    entityConstraints:
      - "In live mode an outward or sign-in provider leaves held only through your recorded decision; a later decision declining it returns the provider to held (BR7.3, BR7.8, BR9.14)."
      - "An abort or a rollback that returns the profile to rehearsal clears approvedAt and approvalId on every outward and sign-in provider, so the next switch verifies each again in its own maintainer-only window (BR9.5, BR9.7)."
      - "models is unavailable with model-evidence-mismatch while a model's digest differs from the release's pin (ModelEvidence), or the release does not pin it, and model work waits; the digest is checked at every renewal and before each model job starts (BR6.11, BR7.7)."
    relationships: []

  - name: "MigrationRun"
    description: "One run of the U8 migration tool, dry or final, from one snapshot of v1 into one empty target."
    attributes:
      - name: "runId"
        logicalType: "uuid"
        required: true
        unique: true
      - name: "kind"
        logicalType: "enum"
        required: true
        unique: false
        allowedValues: ["dry", "final"]
      - name: "snapshotCopyId"
        logicalType: "uuid"
        required: false
        unique: false
        references: "RetainedCopy.copyId"
        constraints: "the retained copy of v1 this run reads: a dry-run-snapshot for a dry run, the v1-final-snapshot for the final run; present from the start of copying and replaced when a resumed copy starts again under a new record"
      - name: "target"
        logicalType: "enum"
        required: true
        unique: false
        allowedValues: ["rehearsal", "production"]
        constraints: "dry runs target their own rehearsal database; the final run targets the production database (BR8.11, BR8.12)"
      - name: "targetCopyId"
        logicalType: "uuid"
        required: false
        unique: false
        references: "RetainedCopy.copyId"
        constraints: "dry runs only: the rehearsal-database retained copy created for this run in preparing"
      - name: "toolCommit"
        logicalType: "string"
        required: true
        unique: false
      - name: "decisionsDigest"
        logicalType: "hash"
        required: true
        unique: false
        constraints: "digest of every MisfitDecision current when the run started; the switch needs the latest accepted dry run's digest to equal the current one (BR8.9, BR9.2)"
      - name: "state"
        logicalType: "enum"
        required: true
        unique: false
        allowedValues: ["preparing", "copying", "importing", "verifying", "reported", "accepted", "rejected", "failed", "interrupted"]
      - name: "interruptedPhase"
        logicalType: "enum"
        required: false
        unique: false
        allowedValues: ["preparing", "copying", "importing", "verifying"]
        constraints: "present exactly while state is interrupted; the run resumes only to this phase (BR8.15)"
      - name: "startedAt"
        logicalType: "timestamp"
        required: true
        unique: false
      - name: "finishedAt"
        logicalType: "timestamp"
        required: false
        unique: false
      - name: "acceptedAt"
        logicalType: "timestamp"
        required: false
        unique: false
        constraints: "set only by your decision accepting the run's parity report"
      - name: "reportApprovalId"
        logicalType: "uuid"
        required: false
        unique: false
        references: "MaintainerApproval.approvalId"
        constraints: "your decision on the run's report, accepting or rejecting it (BR9.14)"
    entityConstraints:
      - "At most one run in preparing, copying, importing, verifying or interrupted at a time; an interrupted dry run can be abandoned, which fails it (BR8.15)."
    relationships:
      - target: "ParityEntry"
        cardinality: "1:N"
        direction: "MigrationRun -> ParityEntry"
      - target: "MisfitRecord"
        cardinality: "1:N"
        direction: "MigrationRun -> MisfitRecord"

  - name: "ParityEntry"
    description: "One line of a run's parity report: the counts and checksums for one kind of record."
    attributes:
      - name: "runId"
        logicalType: "uuid"
        required: true
        unique: false
        references: "MigrationRun.runId"
      - name: "kind"
        logicalType: "enum"
        required: true
        unique: false
        allowedValues: ["account", "identity-link", "preferences", "paper", "paper-content", "paper-embedding", "paper-figure", "saved-paper", "followed-topic", "digest-settings", "glossary", "saved-search", "search-history", "behavior-event", "plan-record", "private-upload", "research-history", "novelty-history", "summary"]
      - name: "inScope"
        logicalType: "boolean"
        required: true
        unique: false
        constraints: "true for the Q13 groups (account to saved-paper); false for every other v1 personal-data kind, which is counted but not imported unless a decision maps it (BR8.1)"
      - name: "sourceCount"
        logicalType: "integer"
        required: true
        unique: false
        min: 0
      - name: "imported"
        logicalType: "integer"
        required: true
        unique: false
        min: 0
      - name: "unchanged"
        logicalType: "integer"
        required: true
        unique: false
        min: 0
      - name: "updated"
        logicalType: "integer"
        required: true
        unique: false
        min: 0
      - name: "skippedByReason"
        logicalType: "map<string, integer>"
        required: true
        unique: false
        default: "{}"
      - name: "excludedByDecision"
        logicalType: "map<string, integer>"
        required: true
        unique: false
        default: "{}"
      - name: "sourceChecksum"
        logicalType: "hash"
        required: true
        unique: false
      - name: "targetChecksum"
        logicalType: "hash"
        required: true
        unique: false
      - name: "reconciles"
        logicalType: "boolean"
        required: true
        unique: false
        constraints: "true only when sourceCount = imported + unchanged + updated + skipped + excluded and the checksums over the compared fields match (BR8.10)"
    entityConstraints:
      - "Unique per (runId, kind)."
    relationships: []

  - name: "MisfitRecord"
    description: "One v1 record that could not be imported as it is, named by kind and source identifier only."
    attributes:
      - name: "runId"
        logicalType: "uuid"
        required: true
        unique: false
        references: "MigrationRun.runId"
      - name: "kind"
        logicalType: "string"
        required: true
        unique: false
        constraints: "a ParityEntry kind"
      - name: "sourceId"
        logicalType: "string"
        required: true
        unique: false
        constraints: "the v1 identifier; never an email address, name or content"
      - name: "reasonKey"
        logicalType: "enum"
        required: true
        unique: false
        allowedValues: ["not-in-scope", "no-v2-home", "required-field-without-source", "closed-in-v1", "unverified-in-v1", "locked-in-v1", "no-email", "email-case-conflict", "unconfirmed-link", "duplicate-provider-link", "dependency-not-migrated", "ineligible-in-v2", "exceeds-v2-limit", "content-shape-unconvertible", "embedding-provenance-unproven", "duplicate-by-version"]
      - name: "newInFinal"
        logicalType: "boolean"
        required: true
        unique: false
        default: "false"
        constraints: "true when its (kind, reason) was met neither by the accepted dry run nor by an earlier final run whose freeze has ended; such records take the archive-only default and need your explicit approval in the final report (BR8.9)"
    entityConstraints:
      - "Unique per (runId, kind, sourceId, reasonKey)."
    relationships: []

  - name: "MisfitDecision"
    description: "Your decision for one kind and reason of misfit, applied to every matching record before the final run (Q16)."
    attributes:
      - name: "kind"
        logicalType: "string"
        required: true
        unique: false
      - name: "reasonKey"
        logicalType: "string"
        required: true
        unique: false
      - name: "decision"
        logicalType: "enum"
        required: true
        unique: false
        allowedValues: ["map", "archive-only", "drop"]
        default: "proposed to you: archive-only for reason not-in-scope; none otherwise (records first seen in a final run take archive-only through newInFinal, BR8.9)"
      - name: "mappingRule"
        logicalType: "string"
        required: false
        unique: false
        constraints: "required when decision is map: the stated rule the owners' imports apply (for example display name from the ORCID name, else the address part before @)"
      - name: "decidedAt"
        logicalType: "timestamp"
        required: true
        unique: false
      - name: "approvalId"
        logicalType: "uuid"
        required: true
        unique: false
        references: "MaintainerApproval.approvalId"
        constraints: "your decision recording this choice (BR9.14); a proposed default becomes a decision only when you record it, and newInFinal records are covered by your final-report decision instead (BR8.9)"
      - name: "frozen"
        logicalType: "boolean"
        required: true
        unique: false
        default: "false"
        constraints: "true from the start of the final run that started with this decision; cleared when that run is rejected or fails, or when the cutover aborts or rolls back after it started, even once its report was accepted, so the decision can change before the next final run; while true the decision never changes (BR8.9)"
    entityConstraints:
      - "Unique per (kind, reasonKey)."
    relationships:
      - target: "MisfitRecord"
        cardinality: "1:N"
        direction: "MisfitDecision -> MisfitRecord"

  - name: "CutoverRecord"
    description: "The single record of the move from v1 to v2 (Q1): its state, the evidence each step needs, the receipts of each effect, and your approvals."
    attributes:
      - name: "cutoverId"
        logicalType: "uuid"
        required: true
        unique: true
      - name: "releaseTag"
        logicalType: "string"
        required: true
        unique: false
        constraints: "the release being rehearsed or switched to; a new release restarts the soak (BR9.3)"
      - name: "state"
        logicalType: "enum"
        required: true
        unique: false
        allowedValues: ["preparing", "rehearsing", "ready-to-switch", "switching", "aborting", "switched", "rolling-back", "rolled-back", "settled"]
        constraints: "aborting lasts until v1 serves at the public address again (BR9.5); rolling-back lasts until v1 serves and the stopped production database's copy is recorded or waived, or until your decision cancels it before v1 serves (BR9.7)"
      - name: "soakStartedAt"
        logicalType: "timestamp"
        required: false
        unique: false
      - name: "soakPeriodSeconds"
        logicalType: "integer"
        required: true
        unique: false
        min: 1
        constraints: "policy, set at NFR Requirements"
      - name: "soakClean"
        logicalType: "boolean"
        required: true
        unique: false
        default: "false"
      - name: "verificationRunId"
        logicalType: "uuid"
        required: false
        unique: false
        references: "VerificationRun.runId"
      - name: "acceptedDryRunId"
        logicalType: "uuid"
        required: false
        unique: false
        references: "MigrationRun.runId"
      - name: "consumerInventoryId"
        logicalType: "uuid"
        required: false
        unique: false
        references: "ConsumerInventory.inventoryId"
      - name: "v1CheckoutCommit"
        logicalType: "string"
        required: false
        unique: false
        constraints: "the commit of the fixed checkout v1 runs from (BR9.16)"
      - name: "v1RestartRehearsedAt"
        logicalType: "timestamp"
        required: false
        unique: false
        constraints: "when the latest v1 restart rehearsal passed; void after any change to v1's checkout, commit or services (BR9.16)"
      - name: "finalSnapshotCopyId"
        logicalType: "uuid"
        required: false
        unique: false
        references: "RetainedCopy.copyId"
        constraints: "a final snapshot whose copy completed; one that never completed is disposed through its record when its run ends, and this field then names nothing (BR9.5, BR9.12)"
      - name: "v1StoresCopyId"
        logicalType: "uuid"
        required: false
        unique: false
        references: "RetainedCopy.copyId"
        constraints: "recorded right after admission opens (BR9.4)"
      - name: "rollbackV1ServingAt"
        logicalType: "timestamp"
        required: false
        unique: false
        constraints: "set when v1 answers at the public address during a rollback; the v1-stores copy's return to service, the profile's return to rehearsal, the clearing of provider approvals and the unfreezing of decisions all happen at that step, and the rollback can be cancelled only before it (BR9.7)"
      - name: "rollbackCopyPendingSince"
        logicalType: "timestamp"
        required: false
        unique: false
        constraints: "set while a rollback, with v1 already serving, waits for the stopped production database's copy; the database is not recreated and no dry run, rehearsal or switch starts until the copy is recorded, written to a replacement volume (BR4.10), or waived by your decision (BR9.7)"
      - name: "rollbackCopyIncidentId"
        logicalType: "uuid"
        required: false
        unique: false
        references: "ServiceIncident.incidentId"
        constraints: "the incident a rollback's copy-pending wait opened on operations.cutover in the live environment, or the already-open live operations.cutover incident it took over; it resolves only as rollback-copy-settled, before the other live incidents resolve as environment-stopped (BR3.7, BR9.7)"
      - name: "abortIncidentId"
        logicalType: "uuid"
        required: false
        unique: false
        references: "ServiceIncident.incidentId"
        constraints: "the abort's incident of the latest abort, whether the abort opened it or took it over from an open live operations.cutover incident; BR9.2 needs it resolved before another switch"
      - name: "finalRunId"
        logicalType: "uuid"
        required: false
        unique: false
        references: "MigrationRun.runId"
      - name: "switchStartedAt"
        logicalType: "timestamp"
        required: false
        unique: false
      - name: "switchTimeBoundSeconds"
        logicalType: "integer"
        required: true
        unique: false
        min: 1
        constraints: "policy; a switch not opened within it aborts (BR9.5)"
      - name: "admissionOpenedAt"
        logicalType: "timestamp"
        required: false
        unique: false
      - name: "rollbackWindowSeconds"
        logicalType: "integer"
        required: true
        unique: false
        min: 1
        constraints: "policy, set at NFR Requirements; counted from admissionOpenedAt"
      - name: "effectReceipts"
        logicalType: "list<string>"
        required: true
        unique: false
        default: "[]"
        constraints: "the PlatformControl receipts of every switch, abort, rollback, restart rehearsal, profile, v1 lifecycle and disposal effect, in order (BR9.10)"
      - name: "approvals"
        logicalType: "list<uuid>"
        required: true
        unique: false
        default: "[]"
        references: "MaintainerApproval.approvalId"
        constraints: "your decisions on this record's steps: v1 restart rehearsal, switch start, final report with its new-in-final items, provider verifications and first effects, admission opening, abort review, rollback, its cancellation and any waiver of its database copy, settlement (BR9.14)"
    entityConstraints:
      - "Exactly one CutoverRecord exists; it is never deleted, even after settlement."
    relationships:
      - target: "MigrationRun"
        cardinality: "1:N"
        direction: "CutoverRecord -> MigrationRun"
      - target: "RetainedCopy"
        cardinality: "1:N"
        direction: "CutoverRecord -> RetainedCopy"
      - target: "MaintainerApproval"
        cardinality: "1:N"
        direction: "CutoverRecord -> MaintainerApproval"

  - name: "VerificationRun"
    description: "One run of the whole-application verification (Q10) over the one composed synthetic realm, recorded as evidence for an exact commit."
    attributes:
      - name: "runId"
        logicalType: "uuid"
        required: true
        unique: true
      - name: "commit"
        logicalType: "string"
        required: true
        unique: false
      - name: "journeys"
        logicalType: "list<object>"
        required: true
        unique: false
        constraints: "each {journeyId, result: passed|failed|not-run, evidenceRef}; journeyIds are those of BR10.3"
      - name: "result"
        logicalType: "enum"
        required: true
        unique: false
        allowedValues: ["passed", "failed", "incomplete"]
        constraints: "passed only when every BR10.3 journey passed"
      - name: "startedAt"
        logicalType: "timestamp"
        required: true
        unique: false
      - name: "finishedAt"
        logicalType: "timestamp"
        required: false
        unique: false
    entityConstraints:
      - "Evidence for one commit only; a different commit needs its own run (BR10.5)."
    relationships: []
```

## Storage placement

Each entity has exactly one home (BR6.10). The **operations ledger** is ServiceOperations' append-only record in the production profile root. It is never emptied by an abort, never overwritten by a production restore, and the same ledger serves rehearsal and live. A read-only copy of it (a LedgerCopy) is written onto the backup volume with every backup set and on its own on any day without one. The **backup volume** is the encrypted external volume the profile names; only the backup agent, running as the backup account, writes, reads back or deletes in U8's folder there (BR4.3, BR9.17). A BackupSet, LedgerCopy or RetainedCopy record lives in the ledger; the set or copy it describes lives at its location, on the backup volume for every file copy, where the agent's catalogue records each file and decides when it may be deleted.

| Entity | Stored in | Survives an aborted switch | Survives a rollback | Survives a production restore |
|---|---|---|---|---|
| ContributionRegistration, CapabilityRegistration, NavigationEntry, LifecycleParticipantEntry, ModelEvidence | the release (build input) | yes | yes | yes |
| CapabilityObservation | the running environment's database (operations schema), re-derived | no; re-observed | kept in the stopped database's retained copy | rolls back; re-observed |
| ServiceIncident, RecoveryRequest, BackupSet, RestoreVerification, RestoreTombstone | operations ledger (a BackupSet's data on the backup volume) | yes | yes | yes |
| ProviderActivation, ConsumerInventory, RetainedCopy, CutoverRecord, MaintainerApproval | operations ledger | yes | yes | yes |
| LedgerCopy | operations ledger (the copy's file on the backup volume) | yes | yes | yes |
| CatalogueEntry | the backup agent's catalogue in U8's folder on the backup volume | yes | yes | yes |
| IsolationCheckResult | the root-owned isolation evidence folder, readable by every account, kept for its bounded period | yes | yes | yes |
| MigrationRun, ParityEntry, MisfitRecord, MisfitDecision | operations ledger, with the full report file in the evidence folder | yes | yes | yes |
| VerificationRun | evidence folder, referenced from the ledger | yes | yes | yes |
| ProductionProfile | the profile's environment manifest, changed only by PlatformControl's profile operation | yes, returned to rehearsal mode | yes, returned to rehearsal mode | yes |

## Summary

Twenty-five entities in four groups.

**Composition (WebWorkspace host, completed by U8).** These are build inputs, not runtime records.
- **ContributionRegistration** is one contribution of the complete application: its revision and schema digest, what it requires and provides, its routes and its lifecycle participants.
- **CapabilityRegistration** says who provides and who observes a capability and whether readiness requires it. The full registry is in functional-spec.md.
- **NavigationEntry** is one route of the single navigation set, with its access rule and placement.
- **LifecycleParticipantEntry** is one owner in the account-lifecycle manifest, with its scopes.
- **ModelEvidence** is the digest the release pins for one model v2 uses. v2 uses a model only while the runtime reports that digest, and a new digest needs a new release.

**Operations (ServiceOperations).**
- **CapabilityObservation** is one admitted observation. It is re-derived continuously and is never evidence by itself.
- **ServiceIncident** correlates a lasting problem with its diagnosis, recovery and closing evidence, and records how it was resolved.
- **RecoveryRequest** is an administrator's or the schedule's request for backup or restore. Its platform effect runs only under operator authority. A production restore takes its own backup after writes stop.
- **BackupSet** is one backup of one environment's database. It never contains key material.
- **RestoreVerification** proves that a backup restores and that every owner tombstoned up to a stated register position stays erased, and records that its scratch copy was removed.
- **RestoreTombstone** is the append-only register of accepted erasures. Its head is anchored in the evidence that relies on it.
- **LedgerCopy** is a verified copy of the operations ledger on the backup volume, taken at least daily, from which a damaged ledger is repaired.
- **RetainedCopy** is any copy that may hold personal data outside the live service, from dry-run copies of v1 to the archives, with its disposal point.
- **CatalogueEntry** is one file on the backup volume as the backup agent's own catalogue records it; the catalogue, not the ledger, decides when it may be deleted. It belongs to the backup-volume operations U8 adds to PlatformControl (amendment A6), not to ServiceOperations.
- **IsolationCheckResult** is one result of the root isolation check: a pass or a fail per item, the stop records it found, and when it ran. Like CatalogueEntry, it belongs to the PlatformControl operations U8 adds (amendment A6).
- **MaintainerApproval** is one decision of yours, recorded only through the operator tool.
- **ProductionProfile** is the durable environment manifest, including its mode and admission.
- **ProviderActivation** tracks each real provider and its verified first effect or first sign-in.

**Continuity (ServiceOperations, used by the U8 migration tool).**
- **MigrationRun** is one dry or final run. An interrupted run remembers its phase.
- **ParityEntry** gives one kind's counts and checksums.
- **MisfitRecord** names each record that could not be imported as it is, including any first seen in the final run.
- **MisfitDecision** is your decision per kind and reason.
- **ConsumerInventory** lists every client of v1's routes and the disposition you approved for it.
- **CutoverRecord** follows the move from v1 to v2, including aborts and rollbacks, with its receipts and your decisions.

**Evidence.**
- **VerificationRun** records the whole-application verification for one exact commit.

U8 writes none of the owners' records. Imports, lifecycle effects and recoveries are each performed by the owning component's own operation. U8 stores only the records above, in the places named in § Storage placement.
