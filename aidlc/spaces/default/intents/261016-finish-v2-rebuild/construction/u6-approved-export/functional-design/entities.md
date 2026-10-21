# Entities — U6 approved export

Date: 2026-10-19 (Asia/Seoul)
Unit: u6-approved-export. Sources: confirmed [functional-design-questions.md](functional-design-questions.md) (Q1–Q8 and the settled items), [requirements FR2](../../../inception/requirements-analysis/requirements.md), [unit definition](../../../inception/units-generation/unit-of-work.md), [story map](../../../inception/units-generation/unit-of-work-story-map.md). Component ownership follows the approved ApprovedExport component (`../../../../261010-docsuri-v2-rebuild/inception/domain-design/components.md`) and the frozen export contract C09 (`../../../../261010-docsuri-v2-rebuild/inception/contract-design/contract-summary.md`). Field names follow the frozen wire records where one exists; additions to them are listed as amendments in [functional-spec.md](functional-spec.md).

```yaml
entities:
  - name: "ExportConnection"
    description: "The owner's single Notion connection. Holds the protected integration token while it exists; the token itself is never readable outside the export path."
    attributes:
      - name: "connectionId"
        logicalType: "uuid"
        required: true
        unique: true
      - name: "accountId"
        logicalType: "uuid"
        required: true
        unique: true
        references: "Account.accountId (by stable ID; never written by this module)"
      - name: "revision"
        logicalType: "integer"
        required: true
        unique: false
        min: 1
        constraints: "advances on every configure, replace, disconnect and provider-reported revocation (BR1.4); never on unavailability (BR1.6)"
      - name: "provider"
        logicalType: "enum"
        required: true
        unique: false
        allowedValues: ["notion"]
      - name: "state"
        logicalType: "enum"
        required: true
        unique: false
        allowedValues: ["connected", "disconnected", "revoked", "unavailable"]
      - name: "protectedCredential"
        logicalType: "opaque-protected-value"
        required: false
        unique: false
        constraints: "present only while state is connected or unavailable; write-only from the owner's side; never returned, displayed, logged or copied into another record (BR1.1); protection mechanism decided in NFR design"
      - name: "validatedAt"
        logicalType: "timestamp"
        required: false
        unique: false
        constraints: "when Notion last accepted the token"
      - name: "workspaceName"
        logicalType: "string"
        required: false
        unique: false
        constraints: "the Notion workspace name Notion reports for the token; shown instead of the token (BR1.2); removed with the connection"
      - name: "connectionUserId"
        logicalType: "string"
        required: false
        unique: false
        constraints: "the identity Notion assigns to the integration behind the current token; copied onto each attempt as its writer identity (ExportAttempt.writerIdentity)"
      - name: "creationCapability"
        logicalType: "enum"
        required: true
        unique: false
        allowedValues: ["unknown", "confirmed", "refused"]
        default: "unknown"
        constraints: "Notion's connection-wide permission to create content, as far as shown: unknown until the first write, confirmed after a successful write, refused after a permission refusal; reset to unknown when the token is replaced (BR1.5, BR4.2)"
      - name: "lastDestinationId"
        logicalType: "string"
        required: false
        unique: false
        constraints: "the destination of the owner's most recent succeeded export; preselected only when currently listed and readable (BR1.5)"
      - name: "limitations"
        logicalType: "list<string>"
        required: true
        unique: false
        default: "[]"
        constraints: "plain-language notes (for example 'synthetic provider only'); never credential material"
    entityConstraints:
      - "At most one ExportConnection per account; configuring again replaces the token in place under the expected revision (BR1.3)."
      - "protectedCredential is absent whenever state is disconnected or revoked (BR1.4)."
    relationships:
      - target: "ExportPreview"
        cardinality: "1:N"
        direction: "ExportConnection -> ExportPreview"

  - name: "ExportPreview"
    description: "One immutable revision of the owner's read-only rendering of one exact research result for one destination. Only a preview revision can be approved."
    attributes:
      - name: "previewId"
        logicalType: "uuid"
        required: true
        unique: false
        constraints: "one previewId per export pair (account, source artifactId, destinationId); unique together with revision (BR2.3)"
      - name: "revision"
        logicalType: "integer"
        required: true
        unique: false
        min: 1
        constraints: "each preparation for the same owner, source and destination adds the next revision; an existing revision never changes"
      - name: "accountId"
        logicalType: "uuid"
        required: true
        unique: false
        references: "Account.accountId (by stable ID)"
      - name: "source"
        logicalType: "research-artifact-reference"
        required: true
        unique: false
        references: "ResearchArtifact (owned by ResearchWorkspace): artifactId, revision and contentHash exactly as U4's export read returned them (BR2.1)"
      - name: "sourceEligibilityRevision"
        logicalType: "string"
        required: true
        unique: false
        constraints: "U4's eligibility revision for the source at preview time"
      - name: "sourceTitle"
        logicalType: "string"
        required: true
        unique: false
        constraints: "the page title the render policy derives from the result (the summary's first sentence, prefixed, with a fallback; BR2.3); kept for the history and the earlier-export notice after the rendered content is removed (BR2.6)"
      - name: "connectionId"
        logicalType: "uuid"
        required: true
        unique: false
        references: "ExportConnection.connectionId"
      - name: "connectionRevision"
        logicalType: "integer"
        required: true
        unique: false
      - name: "destination"
        logicalType: "destination-snapshot"
        required: true
        unique: false
        constraints: "value object: destinationId (the parent page's id), workspaceId, parentPageId, title (a placeholder when untitled), location context and formatRevision, as read when the preview was prepared"
      - name: "renderPolicy"
        logicalType: "policy-reference"
        required: true
        unique: false
        constraints: "the versioned rendering policy (policyId, revision)"
      - name: "marker"
        logicalType: "string"
        required: true
        unique: true
        constraints: "the DocSuri export marker, derived from previewId and revision; the text of the last top-level block; carries no personal data (BR4.1)"
      - name: "renderedBlocks"
        logicalType: "block-tree"
        required: false
        unique: false
        constraints: "the canonical block tree the render policy produced: exactly the blocks the page will be created with, marker last (BR2.3, BR2.4); removed once no longer needed (BR2.6)"
      - name: "renderedText"
        logicalType: "string"
        required: false
        unique: false
        constraints: "the plain-text projection of renderedBlocks shown read-only to the owner, including the marker line (BR2.3); removed with it (BR2.6)"
      - name: "renderedContentHash"
        logicalType: "hash"
        required: true
        unique: false
        constraints: "hash of the canonical renderedBlocks, so the written blocks are exactly the hashed ones (BR2.3)"
      - name: "bindingHash"
        logicalType: "hash"
        required: true
        unique: false
        constraints: "canonical hash over owner, source tuple, source eligibility revision, destinationId, connection revision, render policy and renderedContentHash (BR2.3); the same value the provider message calls previewHash"
      - name: "earlierExports"
        logicalType: "list<earlier-export-notice>"
        required: true
        unique: false
        default: "[]"
        constraints: "earlier effects for the same source and destination: succeeded ones with date and link, and ones that may exist in Notion (not-found-after-checks, owner-settled-not-delivered) (BR2.5)"
      - name: "preparedAt"
        logicalType: "timestamp"
        required: true
        unique: false
    entityConstraints:
      - "(previewId, revision) is unique; a revision is immutable apart from removing its rendered content (BR2.6)."
      - "Preparing, reading or discarding a preview never writes to Notion and never creates an approval (BR2.2)."
    relationships:
      - target: "ExportApproval"
        cardinality: "1:0..1"
        direction: "ExportPreview revision -> ExportApproval (at most one approval per preview revision, BR3.2)"

  - name: "ExportApproval"
    description: "The owner's explicit approval of one exact preview revision. It authorizes exactly one export effect and nothing else."
    attributes:
      - name: "approvalId"
        logicalType: "uuid"
        required: true
        unique: true
      - name: "accountId"
        logicalType: "uuid"
        required: true
        unique: false
        references: "Account.accountId (by stable ID)"
      - name: "previewId"
        logicalType: "uuid"
        required: true
        unique: false
        references: "ExportPreview.previewId"
      - name: "previewRevision"
        logicalType: "integer"
        required: true
        unique: false
        constraints: "(previewId, previewRevision) is unique: one approval per preview revision (BR3.2)"
      - name: "bindingHash"
        logicalType: "hash"
        required: true
        unique: false
        constraints: "equals the approved preview revision's bindingHash (BR3.1)"
      - name: "policy"
        logicalType: "policy-reference"
        required: true
        unique: false
        constraints: "the approval-validity policy: valid while the binding holds, no time-based expiry (BR3.5)"
      - name: "approvedAt"
        logicalType: "timestamp"
        required: true
        unique: false
      - name: "expiresAt"
        logicalType: "timestamp"
        required: false
        unique: false
        constraints: "always empty in U6: validity is defined by the binding, not a clock (BR3.5)"
      - name: "state"
        logicalType: "enum"
        required: true
        unique: false
        allowedValues: ["approved", "consumed", "cancelled", "invalidated", "expired"]
        default: "approved"
        constraints: "expired is part of the frozen contract but never entered in U6 (BR3.5); consumed, cancelled and invalidated are terminal"
      - name: "invalidationReason"
        logicalType: "enum"
        required: false
        unique: false
        allowedValues: ["source-changed", "destination-changed", "connection-changed", "authority-revoked", "account-withdrawn"]
        constraints: "set only when an unconsumed approval is invalidated (BR3.4)"
      - name: "approvingSession"
        logicalType: "session-reference"
        required: true
        unique: false
        constraints: "internal reference to the owner session that pressed the button; checked when continuing (BR3.7) and before every write (BR3.3); never exposed"
      - name: "requestKey"
        logicalType: "uuid"
        required: true
        unique: true
        constraints: "the press's idempotency key as recorded by the approve call (keys are scoped per owner and operation); a replay returns this approval and its effect (BR3.2)"
    entityConstraints:
      - "approved -> consumed happens exactly when the approval's one ExportEffect is bound; a consumed approval is never changed again (BR3.2, BR3.4)."
      - "An approval interrupted before binding stays approved until it is continued, cancelled or invalidated (BR3.6, BR3.7)."
    relationships:
      - target: "ExportEffect"
        cardinality: "1:0..1"
        direction: "ExportApproval -> ExportEffect"

  - name: "ExportEffect"
    description: "The one intended Notion page creation bound to an approval; the unit of execution, outcome and reconciliation."
    attributes:
      - name: "effectId"
        logicalType: "uuid"
        required: true
        unique: true
      - name: "approvalId"
        logicalType: "uuid"
        required: true
        unique: true
        references: "ExportApproval.approvalId"
      - name: "accountId"
        logicalType: "uuid"
        required: true
        unique: false
        references: "Account.accountId (by stable ID)"
      - name: "revision"
        logicalType: "integer"
        required: true
        unique: false
        constraints: "advances on every state change; the compare-and-set value for cancel (BR3.6)"
      - name: "bindingHash"
        logicalType: "hash"
        required: true
        unique: false
      - name: "state"
        logicalType: "enum"
        required: true
        unique: false
        allowedValues: ["accepted", "executing", "succeeded", "failed", "unknown", "cancelled", "invalidated"]
        default: "accepted"
      - name: "marker"
        logicalType: "string"
        required: true
        unique: true
        constraints: "copied unchanged from the bound preview revision (BR4.1)"
      - name: "requestKey"
        logicalType: "uuid"
        required: true
        unique: true
        constraints: "the idempotency key of the execute call that bound the effect (scoped per owner and operation); a replay of that call returns this effect (BR3.2)"
      - name: "waitingSince"
        logicalType: "timestamp"
        required: false
        unique: false
        constraints: "set when a pre-write check could not complete; starts the wait bound (BR3.3); cleared when a check completes"
      - name: "nextAttemptAt"
        logicalType: "timestamp"
        required: false
        unique: false
        constraints: "set while executing in a rate-limit wait (BR4.2); a worker resumes the effect after it (BR4.6)"
      - name: "nextCheckAt"
        logicalType: "timestamp"
        required: false
        unique: false
        constraints: "for an unknown effect: when the next reconciliation scan runs, shown to the owner (BR4.4, BR4.5)"
      - name: "scanningStoppedAt"
        logicalType: "timestamp"
        required: false
        unique: false
        constraints: "when the scan budget was spent with the effect still unknown; from then on settlement is offered (BR4.4, BR4.5)"
      - name: "remoteReference"
        logicalType: "string"
        required: false
        unique: false
        constraints: "the created Notion page id, the page's identity; set only when succeeded (BR4.7)"
      - name: "remoteUrl"
        logicalType: "url"
        required: false
        unique: false
        constraints: "the page's link for display only, never parsed or used as identity (BR4.7)"
      - name: "reconciliationEvidenceHash"
        logicalType: "hash"
        required: false
        unique: false
        constraints: "hash of the evidence that settled an unknown outcome"
      - name: "outcomeReason"
        logicalType: "enum"
        required: false
        unique: false
        allowedValues: ["token-invalid", "no-access", "destination-missing", "content-rejected", "workspace-block-limit", "provider-blocked", "rate-limit-budget-spent", "not-found-after-checks", "owner-settled-delivered", "owner-settled-not-delivered", "dependency-unavailable", "policy-unresolved", "source-changed", "destination-changed", "connection-changed", "authority-revoked", "account-withdrawn", "owner-cancelled"]
        constraints: "why the effect ended failed, invalidated or cancelled, or that the owner settled it; a fixed category, never provider response text (BR7.2)"
      - name: "settledBy"
        logicalType: "enum"
        required: false
        unique: false
        allowedValues: ["provider", "reconciliation", "owner"]
      - name: "ownerAssumption"
        logicalType: "string"
        required: false
        unique: false
        constraints: "the named assumption the owner accepted when settling (BR4.5)"
      - name: "limitations"
        logicalType: "list<string>"
        required: true
        unique: false
        default: "[]"
    entityConstraints:
      - "Exactly one ExportEffect per consumed approval, durably recorded before any provider write (BR3.2)."
      - "An owner has at most one effect in accepted or executing at a time, and no new effect for a source and destination whose earlier effect is unknown (BR5.1)."
      - "accepted -> executing is one atomic step with the recording of its first ExportAttempt, a compare-and-set (BR3.3); an executing effect therefore always has an attempt. succeeded, failed, cancelled and invalidated are terminal; an effect never re-enters executing from unknown or failed (BR4.3)."
    relationships:
      - target: "ExportAttempt"
        cardinality: "1:N"
        direction: "ExportEffect -> ExportAttempt"
      - target: "ReconciliationCheck"
        cardinality: "1:N"
        direction: "ExportEffect -> ReconciliationCheck"

  - name: "ExportAttempt"
    description: "This module's durable record of one provider write attempt: the transport facts that decide or later reconcile the outcome."
    attributes:
      - name: "attemptId"
        logicalType: "uuid"
        required: true
        unique: true
      - name: "effectId"
        logicalType: "uuid"
        required: true
        unique: false
        references: "ExportEffect.effectId"
      - name: "attemptNumber"
        logicalType: "integer"
        required: true
        unique: false
        min: 1
      - name: "startedAt"
        logicalType: "timestamp"
        required: true
        unique: false
        constraints: "recorded before the request leaves (BR4.6)"
      - name: "writerIdentity"
        logicalType: "string"
        required: true
        unique: false
        constraints: "the integration identity that sent this attempt; reconciliation and read-back match pages against it, not the connection's current identity (BR4.2, BR4.4)"
      - name: "connectionRevision"
        logicalType: "integer"
        required: true
        unique: false
      - name: "endedAt"
        logicalType: "timestamp"
        required: false
        unique: false
      - name: "responseClass"
        logicalType: "enum"
        required: false
        unique: false
        allowedValues: ["created", "refused", "rate-limited", "uncertain"]
        constraints: "absent while the request is outstanding (BR4.2, BR4.6)"
      - name: "providerRequestId"
        logicalType: "string"
        required: false
        unique: false
        constraints: "the provider's request identifier when it supplies one"
      - name: "pathKind"
        logicalType: "enum"
        required: true
        unique: false
        allowedValues: ["synthetic", "real"]
        constraints: "real only when the request actually went to Notion (BR8.1, BR8.2)"
    entityConstraints:
      - "Attempt numbers are consecutive per effect; only a rate-limited attempt may be followed by another (BR4.2)."

  - name: "ReconciliationCheck"
    description: "One scan of the destination to settle an unknown effect."
    attributes:
      - name: "checkId"
        logicalType: "uuid"
        required: true
        unique: true
      - name: "effectId"
        logicalType: "uuid"
        required: true
        unique: false
        references: "ExportEffect.effectId"
      - name: "checkedAt"
        logicalType: "timestamp"
        required: true
        unique: false
      - name: "windowStart"
        logicalType: "timestamp"
        required: true
        unique: false
        constraints: "the first attempt's start minute less the clock margin (BR4.4)"
      - name: "result"
        logicalType: "enum"
        required: true
        unique: false
        allowedValues: ["marker-found", "not-found", "listing-unavailable", "listing-incomplete"]
        constraints: "not-found means one complete scan found no page carrying the marker (BR4.4)"
      - name: "remoteReference"
        logicalType: "string"
        required: false
        unique: false
        constraints: "the earliest page carrying the marker, when found"
      - name: "otherMarkedPages"
        logicalType: "list<string>"
        required: true
        unique: false
        default: "[]"
        constraints: "further pages carrying the same marker: possible duplicates, shown to the owner (BR4.4)"
      - name: "evidenceHash"
        logicalType: "hash"
        required: true
        unique: false
    entityConstraints:
      - "Checks for one effect stop at the first marker-found result, or at the second not-found result taken at least one settling interval after the first (BR4.4)."

  - name: "ExportLifecycleEvidence"
    description: "What this participant records once per account-lifecycle request and scope."
    attributes:
      - name: "requestId"
        logicalType: "uuid"
        required: true
        unique: false
        references: "lifecycle request (owned by AccountAccess; by stable ID)"
      - name: "scope"
        logicalType: "enum"
        required: true
        unique: false
        allowedValues: ["live_records", "pending_work", "external_copies"]
      - name: "action"
        logicalType: "enum"
        required: true
        unique: false
        allowedValues: ["withdraw", "reactivate", "erase"]
      - name: "reasonKey"
        logicalType: "enum"
        required: true
        unique: false
        allowedValues: ["owner-scope-complete", "external-copies-retained-by-owner"]
        constraints: "the platform's completed-scope reason; external-copies-retained-by-owner is reported by AccountAccess as retained by policy (BR6.4, amendment A8)"
      - name: "counts"
        logicalType: "map<string, integer>"
        required: true
        unique: false
        constraints: "numbers only: approvals invalidated, effects invalidated, exports in flight, exports unknown, pages exported; no titles, links or content (BR6.1, BR7.2)"
      - name: "recordedAt"
        logicalType: "timestamp"
        required: true
        unique: false
    entityConstraints:
      - "Unique per (requestId, scope); written exactly once, without deferral (BR6.5)."
```

## Summary

Seven entities, all owned by ApprovedExport:

- **ExportConnection** is the owner's single Notion connection. It holds the protected token, the reported workspace name and integration identity, and a revision that every real change advances. Unavailability does not advance it.
- **ExportPreview** is an immutable revision (previewId plus revision) of one exact novelty result rendered for one destination. It carries the export marker and the binding hash, and keeps its rendered text only while needed.
- **ExportApproval** is the explicit approval of one preview revision. Its validity is defined by its binding, and it is consumed by exactly one effect.
- **ExportEffect** is the single intended page creation. It carries its state, marker, wait and check times, outcome reason and link.
- **ExportAttempt** holds the transport facts of each write attempt, including which integration wrote it.
- **ReconciliationCheck** records each destination scan, including any possible duplicates it found.
- **ExportLifecycleEvidence** records this participant's counts and platform reason key per lifecycle request and scope.

Accounts and research results are referenced by stable ID only. This module never writes account or research data, and each owned record has exactly one writer: this module.
