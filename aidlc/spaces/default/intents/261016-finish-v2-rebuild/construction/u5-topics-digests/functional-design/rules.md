# Business Rules — U5 topics & digests

Date: 2026-10-17 (Asia/Seoul)
Unit: u5-topics-digests. Sources: confirmed [functional-design-questions.md](functional-design-questions.md) (Q1–Q6), [requirements FR1](../../../inception/requirements-analysis/requirements.md).

```yaml
rules:
  - id: BR1.1
    statement: "One active subscription per account and normalized topic."
    category: validation
    appliesTo: FollowedTopic
    trigger: "follow request"
    logic: "IF an active FollowedTopic already exists for (accountId, normalized topicKey) THEN reject the follow with a duplicate notice. ELSE IF an unsubscribed FollowedTopic exists for that pair THEN reactivate it (same identity, watermark and history; settings reset to the current defaults with a revision bump) and confirm to the account. ELSE create a new FollowedTopic active with default settings."
    violationBehaviour: "Rejected request; existing subscription unchanged; no second row."
    source: FR1.1

  - id: BR1.2
    statement: "Digest windows and delivery times are evaluated in the account's timezone."
    category: policy
    appliesTo: DigestRun, DigestSettings
    trigger: "schedule evaluation and window computation"
    logic: "IF the scheduled delivery time (in the account's timezone) is reached THEN compute the content window with an inclusive end in that same timezone and prepare the run; a run firing late still delivers its window."
    violationBehaviour: "n/a (definitional rule); timezone ambiguity resolved by one stated zone, never by mixed-zone comparison."
    source: FR1.2

  - id: BR1.3
    statement: "Settings revisions invalidate in-flight preparation."
    category: constraint
    appliesTo: DigestRun, DigestSettings
    trigger: "settings change while a run is prepared/sending"
    logic: "IF DigestSettings.revision advances while a run for that topic is prepared or sending THEN the in-flight run completes only its already-started send attempt; the NEXT run uses the new settings. A prepared-but-not-yet-sending run is discarded and re-prepared."
    violationBehaviour: "No digest is delivered with settings the account already changed; the change is never silently ignored."
    source: FR1.2

  - id: BR1.4
    statement: "Digest delivery uses the application's email delivery capability; a real send requires a configured, $0-compliant path."
    category: policy
    appliesTo: DigestRun, SendLogEntry
    trigger: "digest delivery"
    logic: "IF a prepared digest sends THEN it is delivered as an email message assembled from the digest content, sent to the account's email address through the email delivery capability the built application already owns (local sink in test profiles; the maintainer-configured SMTP or equivalent free path in real operation). A real send is recorded with pathKind `real` only when that configured path actually carried it; the topics view also renders the last digest's content for reading without any send."
    violationBehaviour: "No send claims `real` without a configured path; an unconfigured path surfaces as a plain configuration error, never as a fake success."
    source: FR1.4

  - id: BR2.1
    statement: "Digest content comes only from the eligible corpus inside the configured window."
    category: validation
    appliesTo: DigestRun
    trigger: "content selection"
    logic: "IF content is corpus-eligible AND its date falls within [windowStart, windowEnd] (inclusive) THEN it is selectable ELSE excluded."
    violationBehaviour: "Excluded content never appears in a digest; eligibility failures degrade to fewer items, never to ineligible content."
    source: FR1.3

  - id: BR2.2
    statement: "Content already included in a delivered digest is not repeated."
    category: constraint
    appliesTo: TopicDeliveryWatermark, DigestRun
    trigger: "content selection"
    logic: "IF content is in the topic's delivery watermark THEN exclude it from selection."
    violationBehaviour: "No repeated item; a fully-watermarked window yields an empty digest, not a re-send."
    source: FR1.3

  - id: BR2.3
    statement: "An empty window is a recorded empty digest, not a failure."
    category: policy
    appliesTo: DigestRun
    trigger: "selection finds no eligible content"
    logic: "IF selection returns no content THEN record the run terminal as `empty` with an empty digestContent and an outcome row whose observedState is `empty` (no delivery send is required)."
    violationBehaviour: "The window's run exists with an explicit empty outcome; it is never counted as a delivery failure."
    source: FR1.4

  - id: BR2.4
    statement: "Digest preparation is idempotent per (topic, window)."
    category: constraint
    appliesTo: DigestRun
    trigger: "scheduler re-fire, backlog catch-up, or crash-recovery re-check for a window that may already have a run"
    logic: "IF a non-discarded run already exists for (topicId, windowStart, windowEnd) THEN do not create a second run: the scheduler adopts the existing run (prepared -> sending if eligible; otherwise leaves it in its current state). Windows for a topic are prepared strictly in chronological order: a later window is not prepared while an earlier window of the same topic has a non-terminal run (prepared/sending/unknown), so selection always reads a watermark that reflects every already-sent earlier window."
    violationBehaviour: "No duplicate window run can exist; a late or repeated schedule tick cannot double-prepare or double-send a window."
    source: NFR4

  - id: BR3.1
    statement: "Only one send attempt in flight per topic."
    category: constraint
    appliesTo: DigestRun
    trigger: "run state transition to sending"
    logic: "IF another run for the same topic is in state sending THEN do not start a second send; the new run waits in prepared."
    violationBehaviour: "Concurrent sends are prevented; at-most-one in-flight per topic."
    source: FR1.4

  - id: BR3.2
    statement: "Unknown outcomes reconcile before any further effect, from this module's send log."
    category: policy
    appliesTo: DeliveryOutcome, SendLogEntry
    trigger: "a send attempt's outcome is unobserved"
    logic: "IF observedState is unknown THEN no new digest for the topic may start a send until the outcome is reconciled to sent or failed. Reconciliation is driven by the run's SendLogEntry (transport receipt and acknowledgment) plus recipient/delivery-path evidence; the actor is the scheduled reconciliation check (the same scheduler pass) and, where evidence stays unavailable, the owner's explicit resolution through the topic's resolve control (a run-scoped `resolve` action on the topics view): 'resolved as delivered' (watermark updated, assuming the send landed) or 'resolved as not delivered' (recorded failed, assuming it did not) — a human decision that names which assumption it makes. Silence alone never reconciles."
    violationBehaviour: "Delivery for the topic stays visibly paused until reconciliation; no duplicate send is emitted from uncertainty, and an unresolved outcome cannot be silently aged into a resolution."
    source: FR1.4

  - id: BR3.3
    statement: "Retries are explicit, never blind rescheduling."
    category: policy
    appliesTo: DigestRun, DeliveryOutcome
    trigger: "failed or reconciled-failed outcome"
    logic: "IF an outcome resolves to failed THEN the next scheduled window prepares a fresh run (new window, new watermark check); the failed run itself is never re-sent automatically. The failed window's content is re-delivered by a later window only while it remains inside that window's bounds (BR2.1); content that ages out of every window is not re-delivered, and the outcome history records that gap honestly."
    violationBehaviour: "A failed digest is never re-sent by a retry loop; the next window's normal schedule is the only automatic follow-up."
    source: FR1.4

  - id: BR3.4
    statement: "A restart recovers orphaned send attempts into reconciliation, never into a silent permanent block."
    category: policy
    appliesTo: DigestRun, SendLogEntry
    trigger: "process restart or recovery sweep finds a run in `sending` with no recorded outcome"
    logic: "IF a restart or recovery sweep finds a run in state sending with no recorded outcome and no live sending process holding it THEN move the run to unknown; its SendLogEntry facts are preserved and used when present, and their absence (a crash before the entry was written) is itself recorded as the run's evidence gap. BR3.2's reconciliation then applies (scheduled check first, owner's explicit resolution where evidence stays unavailable)."
    violationBehaviour: "No run is stranded in `sending`; BR3.1's single-flight block never becomes a silent permanent stop for the topic."
    source: NFR4

  - id: BR4.1
    statement: "Unsubscribe is immediate and terminal for delivery."
    category: authorization
    appliesTo: FollowedTopic
    trigger: "unsubscribe request, including during queued/prepared work"
    logic: "IF unsubscribe is recorded THEN status becomes unsubscribed immediately; prepared (not yet sending) runs are discarded (state `discarded`, no outcome row); an in-flight sending run finishes its single attempt and records its outcome normally, but the unsubscribed status prevents any further run from starting; nothing sends after the unsubscribe is recorded. A later re-follow reactivates the same row (BR1.1) with its watermark intact."
    violationBehaviour: "No post-unsubscribe send; queued work is dropped, not delivered; the in-flight attempt's outcome is recorded for history, never re-attempted."
    source: FR1.5

  - id: BR4.2
    statement: "Consent withdrawal that covers digests stops delivery like an unsubscribe."
    category: authorization
    appliesTo: FollowedTopic
    trigger: "consent change recorded by the account layer"
    logic: "IF the account's effective consent no longer permits digests THEN the topic behaves as unsubscribed for delivery (late consent changes honored) until consent is restored."
    violationBehaviour: "No digest delivery without effective consent, regardless of queued work."
    source: NFR2

  - id: BR4.3
    statement: "Account lifecycle participation reports disposition without writing account data."
    category: constraint
    appliesTo: FollowedTopic
    trigger: "lifecycle coordinator requests participant disposition"
    logic: "IF an AccountLifecycleRequest (withdrawal/erasure) is outstanding THEN the digest participant reports its own disposition for that account's topics and marks them unsubscribed where policy requires; it writes only its own tables."
    violationBehaviour: "No cross-module writes; an unreported participant is visible to the coordinator, not assumed complete."
    source: FR1.6

  - id: BR5.1
    statement: "Owner isolation on every read and write."
    category: authorization
    appliesTo: all entities
    trigger: "any request"
    logic: "IF a request is not authenticated as the owner of the topic's account THEN deny it; list/read/write paths check the caller's right to the topic on every access, including settings and status reads."
    violationBehaviour: "Denied with a plain refusal; no data crosses owners."
    source: NFR1
```

## Rules summary

| Rule | Category | One-line effect |
|---|---|---|
| BR1.1 | validation | No duplicate active subscription per account+topic |
| BR1.2 | policy | Timezone-consistent windows; late runs still deliver |
| BR1.3 | constraint | Settings revisions invalidate in-flight preparation |
| BR2.1 | validation | Window-and-eligibility bounded content only |
| BR2.2 | constraint | Delivered content never repeats (watermark) |
| BR2.3 | policy | Empty window = recorded empty digest, not failure |
| BR3.1 | constraint | At most one in-flight send per topic |
| BR3.2 | policy | Unknown outcome reconciles before further effect |
| BR3.3 | policy | No blind retries; next window is the only automatic follow-up |
| BR4.1 | authorization | Unsubscribe immediate; queued work dropped |
| BR4.2 | authorization | Consent withdrawal stops delivery like unsubscribe |
| BR4.3 | constraint | Lifecycle participation reports its own disposition, no cross-writes |
| BR5.1 | authorization | Owner isolation on every path |
