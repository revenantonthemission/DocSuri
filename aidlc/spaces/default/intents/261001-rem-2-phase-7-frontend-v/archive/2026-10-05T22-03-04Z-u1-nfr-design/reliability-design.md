# U1 Reliability and Maintenance Design

## Sources

`../nfr-requirements/reliability-requirements.md`, `../nfr-requirements/observability-requirements.md`, `../nfr-requirements/scalability-requirements.md`, `../functional-design/functional-spec.md`, `../../../inception/contract-design/contract-summary.md` and confirmed `nfr-design-questions.md` govern this design. C7 and the functional T1–T8 boundaries remain authoritative. The selected values below are testable starting defaults, not measured environment guarantees.

## RD-1 — Worker Supervisor, Lease and Visibility

Use independent supervisor renewal capacity while generation runs in an isolated child/execution task within the existing worker runtime. Generation/output encoding cannot own the only thread/process/connection that renews authority. The child receives the one initial invocation grant and authoritative input; it cannot directly publish through another fence or create a second grant. A supervisor/process crash can leave an ambiguous invocation; the protocol fails safely or recovers a committed exact snapshot, never reruns the whole pipeline.

```yaml
starting_profile:
  heartbeat_seconds: 15
  publication_lease_seconds: 90
  message_visibility_seconds: 120
  visibility_renewal_seconds: 30
  reconciliation_scan_seconds: 30
  dispatch_ambiguity_seconds: 120
  control_persistence_deadline_seconds: 5
  queue_control_deadline_seconds: 5
  scheduling_jitter_allowance_seconds: 5
  cleanup_interval_seconds: 3600
```

Startup rejects nonpositive or incompatible values. With H=15, L=90, D=5 and jitter allowance J=5, require L > 3H + 2D + J: 90 >60. With visibility V=120, renewal R=30 and queue-control budget Q=5, require V > 2R + Q + J: 120 >70. These guards provide nominal retry/scheduling margin, not proof of actual loaded-system timing. Test measured renewal scheduling/latency under maximum qualified payload/concurrency; if the allowance or deadlines are exceeded, adjust configuration explicitly and revalidate before claiming readiness.

Database current time after acquiring authoritative locks governs lease predicates, not browser/worker wall clock or a stale transaction-start timestamp. Renew compares the current fence, live lease and existing owner/job; it cannot revive expired/revoked authority. Before prepared binding or terminal publication, obtain sufficient valid authority/remaining margin for the bounded persistence operation, renewing first if needed. All writes retain atomic fence/owner/state checks. Expiry during a stalled/cancelled transaction is resolved safely: no late unguarded write or assumed commit success; reconcile uncertain commit by exact stored identity.

Budget acquisition, lock, statement and commit handling within the total 5-second operation deadline. Reserve control resources independently of generation and avoid holding the job lock across external provider calls. Actual adapter cancellation/transaction limits and database resource configuration are verified in implementation/infrastructure; defaults that cannot be enforced are not accepted as working controls.

Visibility is a separate queue delivery mechanism. Set/renew it explicitly on actively supervised receipts; don't treat visibility renewal as a database lease grant. Receive only available execution capacity. Failed visibility renewal can cause redelivery, which observes existing effect authority and does not invoke again. Queue/provider maximum visibility/runtime restrictions must be verified; long legitimate work remains governed by valid independent renewals, not an invented user completion SLA. Terminal acknowledgement is idempotent; invalid old receipt handles don't reopen work. Covers **NFR11.3**.

For T5/T6 write admission require remaining publication authority >2D+J (15 seconds under the starting profile); renew first when it is shorter, and reject when renewal cannot establish current valid authority. Recheck fresh database time/fence at the final guarded publication boundary. The implementation must demonstrate an enforceable total transaction/cancellation budget, not simply a five-second timeout on each of several statements. A lost commit response remains uncertain until exact durable identity is reconciled; no new invocation is granted. Real-store fixtures advance time while awaiting lock/write/commit so expired authority cannot be treated as a successful late unguarded publication.

## RD-2 — Dispatch, Compatibility and Reconciliation

One service-owned send permission changes a proven new-protocol binding from NOT_STARTED to SENDING before its single external send attempt. Disable SDK-level blind SendMessage retries that could make an unknown response look like definite rejection; choose bounded queue-call attempts and classify acknowledgement, definite non-dispatch and ambiguity explicitly. A later same-key request or maintenance actor may compete for the first T2 claim of an existing NOT_STARTED record, not repeat SENDING/UNKNOWN send.

Definite rejection with no accepted message/effect settles safe failure and releases the binding atomically. Positive acknowledgement or verified queue receipt settles acceptance without regressing current state. Unknown send retains identity and follows bounded reconciliation; no message/effect evidence is invented from elapsed time. A pre-effect conservative unknown-dispatch failure retains binding and makes later delivery acknowledgement-only. Pin the evidence/defer policy and regression cases; no old terminal job restarts.

On each 30-second recovery pass, page three explicit eligibility classes: proven NOT_STARTED first dispatch, pre-effect SENDING/UNKNOWN dispatch ambiguity, and expired execution authority. Skip locked/live/reconciled work and recheck authoritative predicates rather than trust a stale list. Execution reconciliation publishes from exact durable content or safe uncertain failure without generation/key release. Newly normalized legacy/keyless callers enter new authority; pre-existing ambiguous old records are drained/isolated before cutover. Replace the old blind re-enqueue path. Covers **NFR4.4, NFR11.4**, supporting **NFR11.3**.

**Pre-effect ambiguous-dispatch bound:** Use a 120-second ambiguity window from authoritative dispatchStartedAt committed by T2, never reset by polling/replay. Require it to exceed one queue-control budget +two persistence budgets +one scan interval +jitter allowance (120 >50 under the profile). Include new-protocol SENDING/UNKNOWN bindings whose job is still SUBMITTED and has no generation effect intent. These records have no execution lease and must not be omitted by a lease-only scan. Before the bound, retain binding and settle only from trusted acknowledgement or validated queue-receipt evidence; never send again to discover the previous outcome.

At or after 120 seconds, lock/recheck current job/binding/dispatch fence and database time. If confirmation/acceptance won, retain that actual state and do not fail/release it. If still SUBMITTED with SENDING/UNKNOWN, current fence, no confirmation and no effect intent, revoke/advance dispatch authority and atomically publish FAILED with safe dispatch_outcome_uncertain, retryable false, and its event **with the binding retained**. Later acknowledgement/rejection/delivery cannot reopen the job, release the key or invoke generation; terminal delivery is acknowledgement-only. Legacy missing markers/timestamps are not invented into this eligibility.

This is a conservative ambiguity bound, not a normal queue-delivery/generation SLA. Settle on the next qualifying 30-second pass, with bounded pass/jitter margin and verified backlog progress. Test crash after T2 before send, lost response, early/late receipt, stale old publisher, deletion and both competing acceptance/failure orderings. No outcome grants another send/invocation. Proven definite-rejection release remains a separate path.

## RD-3 — Scheduled Maintenance and Deadline-Safe Cleanup

Use the existing one-shot backend maintenance/recovery seam with authenticated internal job/store access and service-owned guarded operations. No public maintenance endpoint or generation callback is needed for cleanup/reconciliation. First-dispatch maintenance alone has restricted permission to use the validated NOT_STARTED send claim; UNKNOWN dispatch or effect intent never grants it.

Infrastructure Design must prove actual scheduling support for the 30-second recovery cadence. A minute-only scheduler may invoke a bounded runner that performs a pass at start and a second at the absolute 30-second point, with independent short pass budgets and no drift-producing sleep-after-work loop. Otherwise use a verified existing sub-minute scheduling capability. Do not silently replace 30 seconds with a minute or deploy an unapproved new service to hide the gap. Schedule overlap uses database guards and idempotent operations, not a fragile single-instance assumption.

Cleanup runs hourly and pages expired prepared rows using an expiry/purge-status index. Recheck server expiry and current owner/job inside each purge transaction; retain only needed job/binding/expiry metadata while the job remains. Remove the expired prepared payload and unnecessary preparation-content metadata; don't delete keys/history to force another execution. Account deletion removes dependent live records and late writes cannot recreate them. A restored expired payload remains unreadable and enters cleanup; actual backup retention/restore controls follow the verified existing policy.

Use bounded batches with persistent pagination/progress so each overdue row can be reached instead of repeatedly scanning only the first page. Impose pass/run deadlines and reschedule remaining work. Qualify measured backlog drain rate against the 24-hour deadline, including retries after failure, overlap and foreground traffic. A successful empty scan is distinct from a failed scan or a scan which omitted backlog. Hourly scheduling alone is not proof that a large backlog clears within 24 hours.

OD-4 specifies age warnings at 12 hours, urgent alerts at 18 hours and breach at 24 hours. Record run/failure/backlog health and missing invocation freshness; route actionable alerts to the accountable human. During outage, reads still enforce TTL and missing deadline is reported rather than silently waived. Covers **NFR11.5**.

**Pass/run bounds:** Start with a 20-second recovery-pass budget and at most 100 candidate rows per page, processing only the work that fits remaining budget. For a minute-triggered two-pass runner, start passes at absolute invocation offsets 0 and 30 seconds with a 58-second total runner deadline: 30-second second-pass offset +20-second pass +5-second scheduling allowance leaves three seconds of finish margin. A missed/over-budget pass is reported unhealthy and rescheduled; it is not labeled a successful 30-second cadence. Per-operation deadlines use the remaining pass budget. First dispatch is not claimed if its send/settlement cannot fit; NOT_STARTED remains eligible for a later first claim, rather than committing a send intent without safe operational budget.

Start cleanup with the same 20-second bounded pass and a 100-row page limit. If eligible backlog remains, request guarded continuation within 60 seconds through a verified existing scheduling mechanism instead of waiting another hour. Persistent progress and overlap-safe predicates prevent starvation; qualify actual drain rate against the largest tested backlog and 24-hour deadline. Infrastructure Design must provide compatible retry/continuation wiring and runtime limits; these defaults cannot claim a currently available scheduler or production-scale guarantee. Queue-call/persistence deadlines and continuation choices never grant another generation invocation.

## RD-4 — Exact Result and Query Fault Classification

T5 commits exact final schema/semantically validated owner-specific payload and immutable identity before T6. Repeated persistence must match the already bound payload; lost acknowledgement reconciles by exact identity/digest rather than regenerate. T6 rechecks committed binding, current authority and legal state, and commits terminal state/event and fixed expiry together.

Keep state queries narrow; result query checks authentication/owner/state/expiry/version/binding before content delivery. Temporary storage failure yields controlled 503, not permanent legacy-unavailable 422. Expired owned records yield 410 even after payload purge, while unknown/other-owner remains identical 404. Neither failure nor read retry invokes the existing pipeline or current glossary rendering. Verify summary/translation final outputs after settings change and all C2 positive/negative fixtures. Covers **NFR11.2**.

## RD-5 — Stream/Fallback Lifecycle

Native EventSource connects through BFF with its native reconnect header; recreated streams use the last accepted opaque history ID via the supported query mechanism. Server lookup verifies that ID in the authorized job and preserves real delimiters. State poll seq and history cursor are independent. Apply nonregressing state and deduplicated ordered history, including poll-ahead/replay fixtures; don't compare state names or timestamps as authoritative order.

SSE failure enables one nonoverlapping SWR fallback read at the configured two-second interval; keep native reconnection separate from JSON retry. Live restoration stops fallback. Terminal/owner/job/context change/unmount cancels obsolete work and invalidates old-job callbacks/cache. Network loss marks authorized observations stale; verified access loss clears them. Backend exhausted terminal stream returns 204 and authorized state read supplies terminal presentation. Preserve received-history checkpoints through render reset without claiming a poll reconstructed missing history. Covers **NFR5.1–NFR5.3**.

## RD-6 — Rendering and Async Failure Domains

Status descendant rendering is contained by the standalone boundary, notifying the stable parent for full-page fallback with authorized tracking checkpoint. Async network/event/diagnostic failures use explicit handlers and safe inline feedback. Recovery resets only query/stream/rendering for the actual job; it never submits, generates or rotates keys. Missing context disables recovery with explanation and safe return.

Preserve conditional focus and view dismissal from the approved mockups; an ordinary background update or late obsolete completion cannot seize focus. Repeated fallback remains usable and does not immediately remount a known crashing subtree on Return. Covers **NFR6.1–NFR6.3**.

## Verification Before Execution

Test authority and cancellation/deadline boundaries with real storage and controlled clocks, both race orderings, slow child work, renewal starvation/store outages, duplicate receipt, crash before/after prepare/publication and deletion. Verify the actual scheduler, runtime limits, permissions and cleanup drain capacity before their affected activation. Numeric starting values are not a blanket readiness guarantee. NFR11.1's implementation tests and the separately human-authorized real skeleton check remain required.
