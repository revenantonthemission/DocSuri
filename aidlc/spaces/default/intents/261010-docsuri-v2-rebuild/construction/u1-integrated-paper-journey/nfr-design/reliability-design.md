# DocSuri v2 — U1 reliability design

Date: 2026-10-11 (Asia/Seoul). Unit: `u1-integrated-paper-journey`. Status: logical mechanisms and required
verification; implementation, measured durability, restore success and executable contract closure remain
unproven.

## Scope and source of authority

Preserve acknowledged state and accepted work through the bounded paper journey on the evidenced $0 free/local
configuration, operated by one human maintainer. This design chooses owner protocols and adapter guarantees,
not a database, broker, replication arrangement, deployment topology or paid fallback.

Sources: [confirmed design questions](nfr-design-questions.md), [reliability
requirements](../nfr-requirements/reliability-requirements.md), [technology
candidates](../nfr-requirements/tech-stack-decisions.md), [functional
workflows](../functional-design/functional-spec.md), [rules](../functional-design/rules.md),
[entities](../functional-design/entities.md), [contract
amendments](../functional-design/contract-revision-plan.md), [component
ownership](../../../inception/domain-design/components.md) and [canonical
C00/C02/C03/C06/C11/C13/C14](../../../inception/contract-design/contract-summary.md). The canonical amendments
and affected consumers must be coordinated before code. This document describes intended protocols; it does
not publish alternate APIs.

## Requirement mapping

| Requirement | Solution | Concrete mechanism and verification |
|---|---|---|
| NFR3.1 | REL01 | Owner transaction joins mutation, revision and receipt; exact replay precedes new-write CAS; lost-response and concurrent-write faults. |
| NFR3.2 | REL02 | Atomic accepted record/outbox, fenced owner claims, protected immutable input and finite recovery; kill/redelivery/replacement races. |
| NFR3.3 | REL03 | Durable admission reconciliation, staged-result binding and terminal/settlement obligation; idempotent UsageEntitlements settlement across faults. |
| NFR3.4 | REL04 | Explicit durability envelope, protected recovery manifest and isolated authority-safe restore; measured loss and restoration. |
| NFR3.5 | REL05 | Stable bounded owner history plus snapshot/result recovery; fresh browser rediscovers retained exact-paper work without new effects. |

### REL01 — Atomic owner writes with durable replay receipts

AccountAccess, Library and Personalization each own their mutation transaction. Its durable unit contains the
domain change, advanced revision, normalized intent digest and immutable operation receipt. Required
recovery/audit obligations join that same unit; an ordinary telemetry emission does not. A rejected or
rolled-back transaction preserves the previous committed state and cannot emit a saved ack.

The trusted boundary authenticates and checks current permission before receipt lookup. The key is scoped to
verified owner, operation kind and semantic intent, including its original revision precondition. An exact
committed replay returns the safe original receipt even when the current entity revision has advanced; it
never performs the old write again. Key reuse with different intent conflicts. Only a previously unseen
command reaches atomic compare-and-swap (CAS): compare the observed revision, change state, advance revision
and insert the unique receipt together. Declared create-if-absent uses its explicit null convention; missing
revision is never an unconditional overwrite.

On response loss, WebWorkspace preserves an uncertain disposition and reconciles the original identity under
current authorization. An unavailable lookup remains unknown. A genuine conflict uses an authorized fresh read
before a deliberate new command; reauthentication or reopening a view does not resubmit mutations. Receipt
retention must cover the resolved reconciliation/replay horizon and all outstanding obligations; expiry cannot
make an old key silently become new work.

Library deduplicates Discovery history facts by original completion identity. Clear commits its owner
boundary/revision and receipt against the server-captured Discovery admission cutoff; delayed facts at or
before that cutoff stay hidden. The empty-history control token remains owner-defined. Personalization reset
compares its control revision and advances the separate input boundary atomically; late behavior cannot undo
reset. Neither token substitutes for current consent.

**Verification and tradeoff:** LC01/LC07–LC09 inject rejection, disk-full, commit-before-reply termination,
replay after a later edit, same-revision writers, history duplicate/reordering and clear/reset races. Compare
owner reads/receipts against the independent expected-state ledger, including revoked/account-B reads.
Transactional receipts consume retained storage but avoid ambiguity created by client-only deduplication.
Adapter selection must prove atomicity, uniqueness and its actual durable-ack guarantee; process restart alone
does not prove power-loss safety.

### REL02 — Recoverable acceptance and fenced execution

PaperAssistance first verifies the REL03 reservation and immutable input binding. Its acceptance transaction
records the original job, receipt, reservation, protected payload descriptor, immutable original acceptance
time and durable dispatch obligation together. The descriptor must already reference verified durable
immutable bytes or bytes in the same proven durable unit. Incomplete staging cannot produce acceptance. Outbox
scanning uses bounded batches and durable checkpoints; delivery acknowledgement cannot erase unfinished owner
work. Transport may redeliver; it is never a second business job authority.

| Boundary | Owner commit and race behavior |
|---|---|
| Acquire | Atomically compare eligible nonterminal job/current claim and allocate one worker-bound lease, owner-time expiry, fence and lease revision. Competing deliveries cannot both acquire current authority. |
| Renew | Compare worker, lease, fence, expiry and expected lease revision; advance only lease revision. An expired/replaced claim cannot revive itself. |
| Reclaim | Under owner serialization, verify expired/revoked prior claim, retain operation/input/reservation and issue a strictly larger fence. Attempt timing changes; original acceptance time does not. |
| Read payload | Authenticate executor, match current claim and exact descriptor/hash, then recheck current account/consent/source-purpose permission. A locator, message or account ID grants no access. |
| New progress/failure/success fact | Match trusted executor, active unexpired claim, fence, immutable input and expected business revision; owner allocates committed revision/sequence. Terminal state cannot regress. |
| Committed-fact replay | Authenticate first, compare fact identity and content digest, then return the permitted recorded disposition. An expired claim may recover an existing receipt; it cannot create another effect. |

Revocation, reclaim, renewal and new effect commits share the owner's serialized authority boundary. Following
LOG03, the current AccountAccess/CorpusContent policy barrier and protected owner commit use the proved shared
serialization capability. The guard checks current authority and remains effective through the protected
commit; expensive inference runs outside it. An asynchronous authority cache or earlier check followed by an
unguarded write is insufficient. If the adapter cannot prove this serialization, deny the new effect and
retain the obligation for authorized reconciliation. A replaced worker cannot fail a newer attempt, publish
progress/result, renew, obtain fresh payload or alter accounting. Owner recovery may record an
exhausted/forbidden-work disposition using its own authorized recovery operation; it never impersonates the
expired worker.

**Finite retry and circuit policy:** each dependency adapter has separate concurrency and wait limits, request
deadline and breaker state. Closed permits bounded attempts; configured failure evidence opens the breaker;
open fails new calls promptly and preserves accepted obligations; after finite cooldown, half-open admits a
bounded probe set and either closes on current evidence or reopens. Probes obey source permissions and cannot
duplicate a business effect. Model failure cannot consume reserved snapshot/receipt/reconciliation capacity.

| Error class | Decision under versioned policy |
|---|---|
| Invalid request, unsupported option, revoked permission, unresolved policy | No blind retry. Return safe definitive failure or maintain a blocked reconciliation incident where outcome is unknown. |
| Storage/dependency transient or throttling with safe retry semantics | Retry the same identity with capped exponential backoff/jitter, advertised delay, finite attempt cap and elapsed deadline. |
| Timeout/connection loss after possible effect | Reconcile the original owner receipt first; do not infer rejection or allocate a new key. |
| CAS conflict or stale/replaced claim | Reread authorized owner state; only a still-current actor may propose a new fact. Stale workers stop. |
| Corruption, result-binding mismatch or invariant breach | Quarantine the affected material, block publication and expose an incident; no automatic success or destructive cleanup. |

Deadline expiry stops automatic execution/retry under the resolved disposition policy; it does not delete
receipts, release uncertain reservations or discard accepted responsibility. Exhaustion becomes a discoverable
failed outcome or explicit pending reconciliation with a safe maintainer procedure. Browser close and stream
disconnect add no cancellation action. Clock regression/uncertain owner time blocks lease-sensitive new
effects until safe reconciliation; worker wall clocks cannot extend claims. Finite lease, renewal,
claim/retry/deadline, breaker, recovery-scan and isolation values are mandatory before enablement.

**Verification and tradeoff:** LC05/LC06/LC09 kill immediately after acceptance, before dispatch, during claim
and after owner commit; duplicate and reorder delivery, race renew/reclaim/revoke and late old-worker
success/failure. Check one job and monotone state with unchanged acceptance time. Durable scanning and fencing
add contention/retained metadata; a volatile queue or delivery counter cannot meet the same fault guarantee.
Test clock faults and stalled half-open probes.

### REL03 — Admission and result settlement across two owners

UsageEntitlements records one reservation under owner/operation identity, input binding, original accounting
period and policy revision before work acceptance. PaperAssistance retains a durable admission disposition
keyed by the same intent; pending is distinct from accepted or definitively rejected. A crash between these
commits is recoverable by owner lookup, not by assuming either outcome.

An orphan-reservation scan reconciles PaperAssistance's admission disposition. If acceptance is absent, its
owner must serialize and seal definitive rejection against concurrent/late acceptance before UsageEntitlements
releases under policy. If outcome or owner is unavailable, keep reservation pending with bounded retries and
an incident. Browser timeout and elapsed reservation age alone cannot release it. The rejection record remains
sufficient to bar late acceptance throughout the resolved obligation/replay lifetime. Reserve/release/reset
concurrency stays inside UsageEntitlements; original period binding survives a reset-window change.

| Phase | Durable authority and recovery |
|---|---|
| Prepare output | Worker writes private immutable staging; PaperAssistance verifies durable existence, integrity, schema, accepted source/options/glossary binding and output validity. Staged bytes are inaccessible to user reads. |
| Publish outcome | One PaperAssistance transaction validates REL02 claim/current authority and commits result binding, terminal job revision/sequence, fact receipt and durable desired settlement obligation. Never publish success pointing to partial/missing bytes. |
| Settle | UsageEntitlements authenticates the owner request, compares its accounting revision, and commits the unique original operation/reservation disposition plus receipt. Exact replay returns that receipt; contradictory settlement conflicts. |
| Confirm/recover | PaperAssistance records the settlement receipt against its pending obligation. A crash or lost reply repeats lookup/settlement for the same identity, never counts deliveries as debits. |

This is recoverable coordination between owner transactions, not a cross-owner database transaction or
exactly-once transport claim. Successful result visibility requires durable verified result and terminal
binding plus a recoverable settlement obligation; settlement itself may remain explicitly pending in
authorized usage/ operations views. Failure/release/refund also needs a durable owner disposition and
policy-bound obligation. Revocation winning before publication suppresses it; revocation after success governs
present read access without rewriting history. Unbound staging is reclaimed only by a bounded owner cleanup
that checks all live bindings/obligations and approved retention; unknown ownership is quarantined.

**Verification and tradeoff:** LC05/LC10 crash before/after reserve, acceptance, staging, publish, settlement
and confirmation; race rejection with late accept, duplicate/conflicting settlement, reset, revoke and result
cleanup. Reconcile all operations, reservations, visible results and logical debits/refunds, including
unresolved cases. Temporary pending capacity and staged orphans are deliberate costs of safe recovery.
Accounting/refund/retention values remain prerequisites.

### REL04 — Fault-scoped backup and isolated restoration

Each owner declares authoritative records, receipts/fences, immutable artifacts, settlement/admission
obligations and lifecycle suppression evidence in a recovery manifest. Derived search/cache/telemetry state is
identified separately with its rebuild source. Backups need a verified consistency point across metadata and
artifact references, key/configuration access, checksums, capture time and source acknowledgement ledger.
Independently copied live files are not assumed coherent.

ServiceOperations coordinates a restore into an isolated namespace with public serving, model execution,
dispatch and external effects disabled. Verify backup integrity and key recovery; restore owners and
relationships; reconcile current revocation, consent, withdrawal, erasure and pending lifecycle restrictions
from an authoritative source newer than the backup where needed. If that source or key is missing, keep
affected data unavailable and report the limitation. Restored sessions/claims cannot resume as valid live
authority; revalidate or supersede them under the owner protocol before enabling work. Reconcile accepted jobs
and settlement by original identity, rebuild permitted derivatives, then run current authorized domain reads
and the mounted journey before allowing exposure.

Process/worker/browser restart with intact evidenced durable storage is the ordinary-fault envelope. Power
loss, corruption and media/environment loss require their own non-production drills and actual persistence
guarantees. Stop new admission on storage exhaustion; reserve recovery headroom and preserve protected
obligations. Graceful degradation keeps permitted reading/search usable where possible and labels unavailable
saves/model/history separately. An alternate instance or restored copy may serve only after owner
authority/fencing validation; no active-active failover, replica or automatic host takeover is selected.

**Verification and tradeoff:** LC12–LC14 compare restored owner/artifact links and all known acknowledgements,
not row counts alone. Record disruption, detection, manual setup/key access, recovery start, useful readiness
and final reconciliation on a monotonic drill clock. Report lost acknowledgements, last protected source
point, actual loss interval/count and unresolved/censored attempts. Baseline RTO, RPO and availability precede
human target agreement; no zero-loss media promise. Backup location/cadence/retention, existing-user inventory
and recoverable continuity remain decisions before affected operation or migration. Isolation costs temporary
capacity, so the drill must fit a finite evidenced envelope without touching live data.

### REL05 — Read-only return through stable retained history

PaperAssistance supplies the planned exact-paper/version history read; Library supplies saved references. A
new authenticated browser starts from the saved list with no retained job/result IDs, then queries bounded
assistance history. Rows bind the original operation, source/content hash, action/options and glossary
snapshot. PaperAssistance owns the initial empty glossary and non-null revision. LOG04 defines a
side-effect-free owner-scoped virtual empty snapshot/revision tied to normalization policy when no row exists.
U1 acceptance persists its exact terms and revision in immutable input; first U3 editing CASes absent plus
that initial revision. A glossary read allocates no record. Personalization supplies assistance defaults. The
older contrary ownership row is corrected here and must be coordinated canonically before code.

History sorts descending immutable original acceptance time (`createdAt`) with job ID as deterministic
tie-break. The opaque cursor binds owner, exact paper/ version, query/schema and stable membership snapshot,
with finite page/expiry policy. Every page and follow-up job/result read rechecks current authority; stable
membership never freezes permission or expiry. Invalid/expired cursor requests a fresh read. Distinguish
empty, dependency-failed, pending, failed, ready, expired, withdrawn and restricted outcomes under current
disclosure policy. No history/result read creates records, acquires claims, extends retention or debits.

Progress uses full owner snapshots ordered by committed sequence. Ignore duplicate/ older events; reconnect
gaps obtain reset/current snapshot, with bounded polling fallback. A closed stream never establishes success.
Account switch clears private presentation epochs/subscriptions so late responses cannot render another owner.
Research drafts remain U4; U1 introduces neither a composer nor job cancellation.

**Verification and tradeoff:** LC06/LC07/LC09 discard browser IDs and recover the same result; compare
execution/accounting counts before/after. Exercise ties, page changes/expiry, withdrawal, foreign-owner
cursors, unavailable result store, source-version mismatch and revoked access. Stable snapshots require
bounded retention/storage; their expiry yields explicit refresh rather than inconsistent pages.

## Completion evidence and unresolved bindings

All scenarios require actual selected adapters and fault points, recorded policy/ build/contract revisions,
permitted P1/P2 fixtures, synthetic A/B accounts and an independent acknowledgement ledger. Preserve failed,
aborted and unexecutable attempts. [Observability design](observability-design.md) owns safe correlation,
measurement denominators and operational procedures; security/capacity designs own authority enforcement and
the shared finite-resource envelope.

Open bindings: canonical browser/claim/history amendments; authoritative time and durable storage guarantees;
finite recovery/accounting policies; source/model rights and retention; recoverable keys/backups and human
continuity choice; measured service targets and the separately approved runnable completion command. Logical
document validation closes none of these executable or operating obligations.
