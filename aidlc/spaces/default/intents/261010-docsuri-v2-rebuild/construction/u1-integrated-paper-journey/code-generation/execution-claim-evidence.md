# U1 canonical execution claims — intermediate boundary

`backend/modules/summarization/execution.py` uses the generated C14
ExecutionBinding, ExecutionClaim and ExecutionClaimResult models. It adapts to
the existing single PaperAssistance transaction owner and claim transition;
no parallel queue or job authority was introduced.

An accepted operation allocates immutable inputRevision and payloadRef from its
operation UUID. inputHash is the original accepted payload hash. These values
do not follow mutable progress/lease revisions. All five binding fields are
compared after current account/source guards and before claim, renewal, input
release or fact preparation. The payload reader is an internal accepted-data
seam; the complete CorpusSection/AssistanceExecutionPayload codec remains to be
assembled with CorpusContent.

Duplicate delivery by the same worker returns the exact still-current claim
without extending its lease/deadline or changing job revision/sequence. Another
worker conflicts. Expired work requires explicit previousFence matching the
current owner record; replacement preserves original acceptance and startedAt.
Remaining work budget is measured from original startedAt using owner database
time, including replacement attempts. Renewal changes the lease revision only.

Existing unbound claim helpers remain diagnostic compatibility seams, not C14
routes. At the transport boundary workerId must be derived from authenticated
executor identity; a supplied claim is not authentication. Existing complete/fail
commit guards remain authoritative after fact preparation. Receipt replay after
terminal state, source withdrawal, worker execution supervision, full payload
codec and mounted API behavior require subsequent integration checks.

## Verification — 2026-10-12 local time

- Scoped Ruff formatting/check passed.
- Approved repository wrapper: **67 passed in 165.73 seconds**, no failures or
  skips. Eight added real-role cases cover same-worker replay and authorized
  input read, competing worker denial, four binding substitutions across
  acquire/input/renew/fact preparation, renewal invariants, stale/exact reclaim
  fences and account revocation before same-worker replay.
- Current result/JUnit/source inventory are in `/tmp/docsuri-u1-run/`; the prior
  59-case result/JUnit were preserved under the `usage-final-` prefix.

No model inference was used in these diagnostic claim tests. Summary readiness
remains false after the documented two-pass semantic failures. U1 Steps 7/8
remain open, and cumulative module coverage is still pending the complete unit
verification inventory.
