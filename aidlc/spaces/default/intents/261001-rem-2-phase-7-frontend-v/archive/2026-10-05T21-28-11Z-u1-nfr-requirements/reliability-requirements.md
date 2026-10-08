# U1 Reliability and Data-Lifecycle Requirements

## Sources and Objectives

Approved NFR4/NFR5/NFR6/NFR11, FR2.5/FR3.5, C1–C4/C6–C8 and the U1 functional transaction/workflow model govern correctness. Confirmed NFR Q2 adds the expired live-payload cleanup deadline. Verification-oriented NFR11 sub-IDs below explicitly specialize its existing backend regression obligation; the 24-hour operational refinement originates in this stage's human answer, not a claim that it already existed in inception.

No production uptime SLA, disaster-recovery duration or general backup-retention policy was supplied. Preserve actual existing objectives where evidenced and report unverified settings; scenario-based durability proof is not a global availability promise.

## Detailed Requirements

| ID | Requirement / pass-fail condition | Required evidence |
|---|---|---|
| NFR4.4 | Retained bindings recover the actual original job/state. Only definite non-dispatch may release a key and permit explicit unchanged-request replacement. Ambiguous send/effect retains identity, old terminal jobs do not restart, and recovery feedback cannot invent a cause. | Paired retained replay, rejection/release, unknown send, executed-terminal and replacement fixtures; C1/C4/C7, FR4 |
| NFR5.1 | Native stream failure activates SWR state fallback at the fixed configured two-second interval without overlapping pending reads. Live restoration stops fallback; channel state is distinct from backend job state. | Actual reconnect/fallback/restoration scenarios with controlled clocks/requests; NFR5, C3/C8 |
| NFR5.2 | Opaque cursor lookup, per-job seq/state watermark and independent history reconciliation preserve order without duplicate history, state regression or a poll watermark invented as a cursor. | Multiple jobs where eventId differs from seq, header/query precedence, duplicate/missing/older events and terminal 204; NFR5, C3 |
| NFR5.3 | Terminal/context/navigation/owner loss releases obsolete streams/readers/timers; late old-job responses cannot publish. Network-only loss preserves clearly stale authorized observations; known access loss removes protected content. | Cleanup, replacement and stale response fixtures, including same owner/paper but different selected job; NFR5, FR2.4 |
| NFR6.1 | Rendering failure reaches the standalone status containment and stable-parent full-page fallback with safe recoverable context. The parent history/cursor checkpoint does not become another mutable state owner. | Throwing-descendant and repeated-render-failure fixtures, with usable return/recovery focus; NFR6, BR5.3 |
| NFR6.2 | Network/stream callback and diagnostic failures use explicit integration-boundary handling and do not rely on render containment. They cannot fabricate terminal success or silently fail. | Malformed event, transport/store and diagnostic-delivery failure fixtures; NFR6, FR7.2 |
| NFR6.3 | Tracking reset and result-read retry retain actual job identity and cause zero submission/generation/enqueue. Missing recovery context has an explanation and safe return; removal of the focused action follows the conditional focus rule. | Command counters, context/missing-original/focus scenarios; NFR6, C4, refined mockups |
| NFR11.2 | Backend result evidence for both tasks proves exact committed final personalization across changed settings, owner/TTL enforcement, consistent state/events and no generation/enqueue during any read. Successful translation validates bare DocModel, not unavailable wrappers. | Positive and negative complete-envelope, changed-glossary/model/source, expiry and ownership fixtures; NFR11, FR2.5/FR3.5 |
| NFR11.3 | At all declared interruption/concurrency windows, legal state/event/binding consistency holds and duplicate whole-pipeline invocation grants equal zero. A renewed current worker cannot be failed by stale expiry observation; revoked authority cannot publish. Ambiguous intent without exact content fails safely and retains binding. | Real-store race/crash tests with at least two claimants where competing authority is possible, plus effect/binding/publication/ack windows; NFR11, Q1, C7 |
| NFR11.4 | T1-before-T2 loss has guarded first-dispatch recovery or truthful no-send terminal settlement. Supported new legacy/keyless calls normalize into new authority without synthetic merging; active unverifiable old jobs cannot acquire fresh generation grants. Old sender/worker drain or isolation is verified before affected cutover. | Restart, competing-first-claim, deletion, old/new message/caller and ambiguous legacy fixtures; NFR11, C1/C6/C8 |
| NFR11.5 | Result reads are denied immediately at fixed expiry. Expired prepared live-database payloads are purged no later than 86,400 seconds after that expiry. Minimal owner/job/expiry metadata remains only while the job remains, preserving owner 410 versus other-owner/unknown 404. Owner deletion removes dependent live records and no late worker recreates them. | Server-time expiry boundaries, cleanup deadline, cleanup failure/recovery and deletion races. Verify actual backup/deletion policy separately; no read/redelivery TTL extension or invented backup-erasure deadline; NFR11, FR3.3/FR3.5, confirmed Q2 |

## Operational Timing Must Be Pinned Before Execution

NFR Design must pin numerical heartbeat, publication lease, queue visibility, first-dispatch scan/defer and ambiguous-execution reconciliation timing against actual runtime/communication/persistence budgets. Configurations must reject invalid/nonpositive values and incompatible budgets; test boundary timing with server-authoritative clocks, renewal latency and prolonged healthy work. A queue visibility expiry is not publication authority and must not grant another invocation.

The required evidence is bounded and testable: current authority survives legitimate renewals, stale authority cannot bind/publish, expired authority settles from a durable snapshot or safe failure within the configured recovery policy, and NOT_STARTED work has an eventual guarded continuation. Numerical recovery tuning remains a next-stage deliverable, not a fabricated product SLA. U1 worker execution approval requires both that configuration and its tests.

## Cleanup and Failure Handling

The 24-hour deadline concerns the expired payload in the live relational prepared-result record. It does not delete the whole job/key/history to force another execution, shorten the readable TTL, or authorize deletion of project knowledge documents. Fixed expiry metadata is initialized once at completion; it is not recomputed from today's configuration on read.

Define a cleanup schedule/retry and monitoring margin capable of meeting the deadline. If a store outage or cleanup failure threatens it, alert before breach and report a breach honestly; access remains denied at TTL regardless. Do not equate physical cleanup success with backup erasure: retain/verify the existing backup/deletion policy and restore controls before recovery actions. Restored expired results must still be denied and scheduled for appropriate cleanup.

Physical durability and recovery rely on actual storage configuration. In-memory fixtures can prove shape but cannot substitute for transaction/concurrency tests or the real integrated skeleton. Existing backup/restore objectives cannot be declared satisfied by code review alone.
