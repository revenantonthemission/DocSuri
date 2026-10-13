# U1 admission and accounting reconciliation

## Implemented boundary

PaperAssistance prepares one immutable intent; Usage reserves against that owner,
operation and intent; PaperAssistance accepts the same work. Unknown replies do
not release reservations. Durable terminal/result proof binds original input,
source, reservation and output before accounting settlement. A lost settlement
reply leaves the PA obligation pending and exact replay completes it once.
Already accepted accounting obligations can settle after account revocation.

Quota exhaustion is a typed definite refusal and closes the open preparation.
An owner-only sweep processes at most four unreconciled rejections or open
preparations at least five minutes old, using PostgreSQL owner time. Age selects
candidates; a locked still-open admission with no accepted job establishes the
durable rejection. Accepted work is never cancelled by this mechanism. Rejected
admissions remain pending until Usage acknowledges the exact proof.

Usage serializes reservation and rejection under its entitlement row lock. A
permanent operation tombstone prevents delayed reservation after rejection,
whether a reservation existed yet or not. The tombstone and any release commit
together. Explicit rejected reconciliation and background recovery share this
protocol. Runtime grants permit only SELECT/INSERT on tombstones, preserving
their identity; the trusted coordinator supplies owner-produced evidence, not a
browser-provided proof. Service scheduling and mounted transport remain later
implementation obligations.

Global admission count is serialized with an owner transaction advisory lock;
the existing own-two/global-four bounds remain in force. No timeout-based
release, quota reset, new user cancellation action or paid fallback was added.

## Executed checks (2026-10-11)

- Component wrapper: 107 passed in 3.03 seconds; zero failed/skipped.
- First repository attempt: 18 failed / 36 passed in 98.58 seconds. The new
  table lacked explicit runtime grants. Applied migration bytes were preserved;
  a separate SELECT/INSERT grant amendment corrected both owned databases.
- Corrected repository wrapper: 58 passed in 113.82 seconds; zero failed/skipped.
- Follow-up repository wrapper: 59 passed in 132.81 seconds; zero failed/skipped.
  Strengthened concurrency evidence requires two distinct PostgreSQL backend
  IDs and observes the second blocked by the first using `pg_blocking_pids`
  before releasing the lock. Added real commit-then-lost-reservation reply.
- Scoped Ruff formatting/check passed for the changed Python implementation
  and new tests.

Commands were the approved component and repository invocations of
`python3 scripts/verify_docsuri_u1.py`, each with `--profile synthetic-local
--environment-file /tmp/docsuri-u1-run/environment.json`. Runs were serial and
bound to actual source inventories. Bootstrap amendments ran only against the
owned diagnostic and journey databases, without clearing accepted state.

Real-role checks cover both concurrent entitlement-lock orders (a deliberate
pause after real lock acquisition and observed actual blocking), lost reservation/acceptance/settlement
replies, permanent rejection replay, revoked open work, fresh-open and accepted
positive controls, no reservation creation after rejection, and denied tombstone
UPDATE/DELETE and foreign-owner mutation. Normal result bytes in these tests are
explicit diagnostic fixtures; they do not establish model output quality.

The original failed result and source inventory are preserved at
`/tmp/docsuri-u1-run/usage-grant-failure-repository-result.json`, fingerprint
`a9e7636489962a6ae9ba32e619c2cc9316b49e9f8c446c18d777f321cdf5ce83`.
Its original JUnit was removed by the next runner invocation before archival;
it is unavailable, not reconstructed. Detailed failure output remains in the
tool transcript. The corrected result/JUnit use the runner's current repository
paths. The initial 58-pass result/JUnit were preserved under the
`/tmp/docsuri-u1-run/usage-first-pass-` prefix before the follow-up run.
Step 13 must introduce bounded attempt-specific evidence retention so
reruns cannot erase earlier diagnostic records.

This is an intermediate component checkpoint. New-module cumulative coverage,
mounted API/worker behavior, scheduled recovery, useful model output, browser
journeys and complete U1 verification are still required. Steps 7/8 remain open;
no completion command or normal assistance readiness is approved here.
