# Functional Design Questions — U5 topics & digests

Date: 2026-10-17 (Asia/Seoul)
Unit: u5-topics-digests (embedded library; TopicsDigests owns digest state). Inputs: [unit definition](../../inception/units-generation/unit-of-work.md), [requirements FR1](../../inception/requirements-analysis/requirements.md), approved [wireframes](../../ideation/rough-mockups/wireframes.md), the built application's trends/digest surface.

## Q1. Scheduling model for digest preparation and delivery?

A. Per-topic settings drive a scheduled preparation run (cadence + delivery time evaluated in the owner's timezone); a run that fires late (machine asleep, backlog) delivers the digest for its window at execution time rather than skipping it; day boundaries computed in one stated timezone
B. A different model (say under Other)
C. Not applicable

X. Other (please specify)

[Answer]: A

## Q2. Content selection and repeat-avoidance?

A. Each digest selects eligible corpus content published/updated within the topic's configured window; content already included in a delivered digest for that topic is not repeated (per-topic watermark); a window with no eligible content produces an explicitly recorded empty digest, not a failure
B. A different rule (say under Other)
C. Not applicable

X. Other (please specify)

[Answer]: A

## Q3. Delivery outcome states and reconciliation?

A. A digest run moves through prepared → sending → sent, failed, or unknown (send initiated but outcome unobserved, e.g. lost response); unknown outcomes reconcile before any further digest effect for that topic; a failed/unknown run is retried only via explicit reconciliation, never by blind rescheduling
B. A different set (say under Other)
C. Not applicable

X. Other (please specify)

[Answer]: A

## Q4. Unsubscribe, consent and lifecycle behavior?

A. Unsubscribe takes effect immediately for the topic: queued/prepared-but-unsent work is dropped, and nothing sends after the unsubscribe is recorded; a consent withdrawal that covers digests stops delivery the same way (late consent changes honored); account withdrawal participation records the digest participant's disposition when the lifecycle coordinator asks
B. A different rule (say under Other)
C. Not applicable

X. Other (please specify)

[Answer]: A

## Q5. Entity ownership and references?

A. TopicsDigests owns: followed topics, per-topic digest settings, digest runs, delivery outcomes and the per-topic sent-content watermark; accounts and papers are referenced by stable ID only (no account or corpus data written by this module); one writer per owned table
B. A different split (say under Other)
C. Not applicable

X. Other (please specify)

[Answer]: A

## Q6. UI behavior for the new screens?

A. Per the approved wireframes: a topics list (follow/unfollow, per-row settings entry, last-digest indicator) and a per-topic settings form (cadence, time, window, inherited language/level); all five screen states (empty/loading/populated/error/partial); Korean labels; keyboard-operable with visible focus; digest status changes announced via a polite live region
B. A different behavior (say under Other)
C. Not applicable

X. Other (please specify)

[Answer]: A

## Consolidated Summary Confirmation

- Q1: Per-topic cadence + delivery time evaluated in the owner's timezone; late runs deliver their window's digest rather than skipping; day boundaries in one stated timezone.
- Q2: Window-based selection from eligible corpus; per-topic sent-content watermark prevents repeats; an empty window is an explicitly recorded empty digest, not a failure.
- Q3: prepared → sending → sent | failed | unknown; unknown reconciles before any further effect; retries only via explicit reconciliation, never blind rescheduling.
- Q4: Unsubscribe is immediate (queued work dropped, nothing sends after); consent withdrawal stops delivery; lifecycle participation reports disposition.
- Q5: TopicsDigests owns followed topics, settings, digest runs, outcomes and watermarks; accounts/papers referenced by stable ID only; one writer per owned table.
- Q6: Wireframe-faithful topics list + settings form; five screen states; Korean; keyboard-operable; polite live region for status.

- Looks correct
- Request changes

[Answer]: Looks correct
