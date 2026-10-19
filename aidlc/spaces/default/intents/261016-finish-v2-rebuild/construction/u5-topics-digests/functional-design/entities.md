# Entities — U5 topics & digests

Date: 2026-10-17 (Asia/Seoul)
Unit: u5-topics-digests. Sources: confirmed [functional-design-questions.md](functional-design-questions.md) (Q1–Q6), [requirements FR1](../../../inception/requirements-analysis/requirements.md), [unit definition](../../../inception/units-generation/unit-of-work.md).

```yaml
entities:
  - name: "FollowedTopic"
    description: "A topic an account follows; the root of the digest configuration tree."
    attributes:
      - name: "topicId"
        logicalType: "uuid"
        required: true
        unique: true
      - name: "accountId"
        logicalType: "uuid"
        required: true
        unique: false
        references: "Account.accountId (by stable ID; never written by this module)"
      - name: "topicKey"
        logicalType: "string"
        required: true
        unique: false
        constraints: "normalized per the built topic taxonomy; one spelling per topic (case/Unicode-normalized)"
      - name: "followedAt"
        logicalType: "timestamp"
        required: true
        unique: false
      - name: "status"
        logicalType: "enum"
        required: true
        unique: false
        allowedValues: ["active", "unsubscribed"]
        default: "active"
    entityConstraints:
      - "One active FollowedTopic per (accountId, normalized topicKey); duplicates rejected, not merged silently."
      - "Unsubscribe stops delivery immediately; the row keeps its identity, history and watermark. Re-following an unsubscribed topic reactivates the SAME row (identity, watermark and history preserved; no duplicate delivery), rather than creating a second row."
    relationships:
      - target: "DigestSettings"
        cardinality: "1:1"
        direction: "FollowedTopic -> DigestSettings"
      - target: "DigestRun"
        cardinality: "1:N"
        direction: "FollowedTopic -> DigestRun"

  - name: "DigestSettings"
    description: "Per-topic delivery configuration owned by the account; initial values derived at follow time (daily, 08:00 local, 7-day window) and explicitly changeable. Language/level are NOT stored here: they are read from the account's preferences at preparation time."
    attributes:
      - name: "settingsId"
        logicalType: "uuid"
        required: true
        unique: true
      - name: "topicId"
        logicalType: "uuid"
        required: true
        unique: true
        references: "FollowedTopic.topicId"
      - name: "cadence"
        logicalType: "enum"
        required: true
        unique: false
        allowedValues: ["daily", "weekly"]
        default: "daily"
      - name: "deliveryTimeLocal"
        logicalType: "time"
        required: true
        unique: false
        constraints: "evaluated in the account's timezone"
        default: "08:00 local (initial settings derived at follow time; explicitly changeable)"
      - name: "deliveryDayLocal"
        logicalType: "enum"
        required: false
        unique: false
        allowedValues: ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
        constraints: "weekly cadence only: the anchor day the digest fires on; default derived from the follow date's weekday; ignored for daily cadence"
      - name: "contentWindowDays"
        logicalType: "integer"
        required: true
        unique: false
        allowedValues: [7, 30]
        default: 7
      - name: "revision"
        logicalType: "integer"
        required: true
        unique: false
        constraints: "incremented on every change; late revisions invalidate in-flight preparation per BR1.3"
    relationships:
      - target: "FollowedTopic"
        cardinality: "1:1"
        direction: "DigestSettings -> FollowedTopic"

  - name: "DigestRun"
    description: "One preparation-and-delivery attempt for a topic window; the unit of idempotency and reconciliation."
    attributes:
      - name: "runId"
        logicalType: "uuid"
        required: true
        unique: true
      - name: "topicId"
        logicalType: "uuid"
        required: true
        unique: false
        references: "FollowedTopic.topicId"
      - name: "windowStart"
        logicalType: "date"
        required: true
        unique: false
      - name: "windowEnd"
        logicalType: "date"
        required: true
        unique: false
        constraints: "inclusive end, computed in the account's timezone (BR1.2)"
      - name: "state"
        logicalType: "enum"
        required: true
        unique: false
        allowedValues: ["prepared", "sending", "sent", "failed", "unknown", "empty", "discarded"]
        default: "prepared"
      - name: "digestContent"
        logicalType: "json"
        required: true
        unique: false
        constraints: "required, possibly an empty list; an empty list is a valid recorded empty digest (BR2.3)"
      - name: "settingsRevision"
        logicalType: "integer"
        required: true
        unique: false
        constraints: "the DigestSettings.revision this run was prepared against"
    entityConstraints:
      - "At most one non-discarded run per (topicId, windowStart, windowEnd): a scheduler re-fire or crash-recovery re-check for a window that already has a prepared/sending/sent/failed/unknown/empty run finds that run instead of creating a duplicate (idempotent preparation, NFR4)."
      - "A topic has at most one run in `sending` state at a time (BR3.1)."
      - "State transitions follow the functional-spec state machine; no state is skipped. `empty`, `sent`, `failed` and `discarded` are terminal for the run."
    relationships:
      - target: "FollowedTopic"
        cardinality: "N:1"
        direction: "DigestRun -> FollowedTopic"
      - target: "DeliveryOutcome"
        cardinality: "0:1"
        direction: "DigestRun -> DeliveryOutcome (exactly one for every terminal run except discarded; none while prepared/sending; none for discarded runs)"
      - target: "TopicDeliveryWatermark"
        cardinality: "1:N"
        direction: "DigestRun -> TopicDeliveryWatermark (rows whose includedInRunId is this run)"

  - name: "DeliveryOutcome"
    description: "The recorded result of a run's send attempt, including unknown outcomes awaiting reconciliation."
    attributes:
      - name: "outcomeId"
        logicalType: "uuid"
        required: true
        unique: true
      - name: "runId"
        logicalType: "uuid"
        required: true
        unique: true
        references: "DigestRun.runId"
      - name: "observedState"
        logicalType: "enum"
        required: true
        unique: false
        allowedValues: ["sent", "failed", "unknown", "empty"]
      - name: "observedAt"
        logicalType: "timestamp"
        required: true
        unique: false
      - name: "reconciledState"
        logicalType: "enum"
        required: false
        unique: false
        allowedValues: ["sent", "failed"]
      - name: "reconciledAt"
        logicalType: "timestamp"
        required: false
        unique: false
      - name: "failureReason"
        logicalType: "string"
        required: false
        unique: false
        constraints: "plain-language category; no secrets or full recipient addresses"
    relationships:
      - target: "DigestRun"
        cardinality: "1:1"
        direction: "DeliveryOutcome -> DigestRun"

  - name: "SendLogEntry"
    description: "This module's durable record of one send attempt's transport facts; the evidence source for outcome reconciliation."
    attributes:
      - name: "logId"
        logicalType: "uuid"
        required: true
        unique: true
      - name: "runId"
        logicalType: "uuid"
        required: true
        unique: false
        references: "DigestRun.runId"
      - name: "attemptedAt"
        logicalType: "timestamp"
        required: true
        unique: false
      - name: "transportReceipt"
        logicalType: "string"
        required: false
        unique: false
        constraints: "provider/delivery-path acknowledgment id or handle; may be absent when the attempt died before a receipt"
      - name: "acknowledgedAt"
        logicalType: "timestamp"
        required: false
        unique: false
      - name: "pathKind"
        logicalType: "enum"
        required: true
        unique: false
        allowedValues: ["real", "local-sink"]
    entityConstraints:
      - "Exactly one per run that enters `sending`: created when the send starts (before the outcome is known), then updated with the transport receipt and acknowledgment facts. It is the reconciliation evidence for BR3.2 and the restart-recovery evidence for BR3.4."
    relationships:
      - target: "DigestRun"
        cardinality: "1:1"
        direction: "SendLogEntry -> DigestRun"

  - name: "TopicDeliveryWatermark"
    description: "Per-topic record of content already included in a delivered digest; prevents repeats."
    attributes:
      - name: "watermarkId"
        logicalType: "uuid"
        required: true
        unique: true
      - name: "topicId"
        logicalType: "uuid"
        required: true
        unique: false
        references: "FollowedTopic.topicId"
      - name: "contentId"
        logicalType: "string"
        required: true
        unique: false
        references: "corpus content stable ID (read-only reference)"
      - name: "includedInRunId"
        logicalType: "uuid"
        required: true
        unique: false
        references: "DigestRun.runId"
    entityConstraints:
      - "Unique per (topicId, contentId); the selection query excludes watermarked content (BR2.2)."
```

## Summary

Six entities, all owned by TopicsDigests: **FollowedTopic** (subscription root with terminal unsubscribe), **DigestSettings** (per-topic cadence/time/window with a revision counter), **DigestRun** (one idempotent preparation-and-delivery attempt per window, carrying the settings revision it was prepared against), **DeliveryOutcome** (sent/failed/unknown with explicit reconciliation fields), **SendLogEntry** (per-run transport facts; the reconciliation and restart-recovery evidence), and **TopicDeliveryWatermark** (per-topic sent-content record driving repeat-avoidance). Accounts and corpus content are referenced by stable IDs only — this module never writes account, library or corpus data, and each owned table has exactly one writer (this module's repository). [Q5]
