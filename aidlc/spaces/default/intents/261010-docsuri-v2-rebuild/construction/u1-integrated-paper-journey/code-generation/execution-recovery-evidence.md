# U1 owner recovery and deadline policy

## Authoritative recovery

PaperAssistance processes at most four active jobs per recovery pass. Account
and CorpusContent status functions retain the same account/consent → source
barrier locks while returning a bounded disposition instead of raising. Existing
raising execution/source guards delegate to these same owner checks. The PA
owner then locks the target job and records an explicit failed state/reason,
revision/event and settlement obligation for current revocation, exhausted
expired fences, execution expiry or recovery-window expiry. No worker with an
expired claim gains permission to fail or complete work.

An expired lease by itself leaves a valid replacement opportunity. Live eligible
work remains unchanged. A contradictory nonterminal result requires intervention
instead of release. Failed work and its history are retained. Usage remains
reserved until the existing coordinator reads the durable terminal proof and
settles it; owner recovery does not issue timeout-based Usage releases.

The finite experimental five-minute job recovery window is implemented as an
absolute lifetime from acceptedAt. Available execution time is the lesser of
original startedAt + 90 seconds and acceptedAt + 300 seconds. A job started at
290 seconds therefore has at most ten seconds remaining. A database trigger
bounds initial and renewed leases by both deadlines; canonical input reads
report the same remaining budget. Expiry records the visible reason
`job-recovery-window-expired`, not deletion or a fresh retry budget.

The new non-raising functions are owned by the existing non-login schema roles,
use fixed safe search paths/qualified objects and expose no source bytes or
credentials. PUBLIC execution is revoked; only the PaperAssistance runtime
consumer receives the additional status privileges. Applied migration bytes
remain unchanged, with append-only amendments on the two owned databases.

## Executed evidence — 2026-10-12 local time

- Database phase after guard refactor: 47 passed in 1.64 seconds. Result/JUnit
  preserved under `/tmp/docsuri-u1-run/status-guard-`.
- Database phase after deadline binding: 47 passed in 1.80 seconds.
- Repository phase: **75 passed in 228.70 seconds**, zero failures/skips.
  Eight new cases cover live-work protection, execution/attempt exhaustion,
  account and source revocation, remaining replacement opportunity, explicit
  old-queue proof before settlement, and late-start/renew deadline binding.
- Scoped Ruff formatting/check passed. No model phase was run.

Time/fence injection is confined to named diagnostic fixtures; production code
uses database time. Original acceptance is not edited to make expiry tests pass:
the old queued fixture is created with its explicit historical acceptedAt.
This verifies owner recovery behavior, not yet worker supervision or the full
mounted application. The worker must still abort its owned computation on lease
loss and pass the reported remaining budget through setup, inference and commit.
Normal model readiness remains false, and U1 Steps 7/8 are still incomplete.
