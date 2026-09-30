# REM-3 Corrective Unit — G1 Scope Clarification

I recorded all five answers in `aidlc-docs/audit.md`. **Q1, Q2, Q3, and Q4 are mutually consistent
and I will execute them as given.** Only Q5 needs your decision, because its stated rationale rests
on a factual error.

## The problem with Q5=C

You chose C: "Fold the whole of G1 into the corrective unit so that REM-4 becomes unblockable as soon
as this unit completes."

Per the approved gate map in `aidlc-docs/inception/plans/unit-of-work-plan.md`:

| Unit | Line | Completion gates |
|---|---|---|
| REM-1 Platform Integrity | 267 | **G1** |
| REM-2 Private Content | 268 | G2, G4 |
| REM-3 Lifecycle and Edge Trust | 269 | G3, G4/G5 |
| REM-4 Corpus Integrity | 270 | **G2/G4/G5** |

**G1 is REM-1's gate. REM-4's gates are G2/G4/G5 — none of them is G1.** So folding G1 into this
unit does not make REM-4 unblockable, which is the outcome you picked C to get. This also conflicts
with your Q2 answer in the previous round, which correctly listed "G1/G2/G4/G5" as the REM-4
preconditions.

There are three further complications with absorbing G1 wholesale:

1. **G1 is already blocked**, per `ops/platform-integrity/cve-disposition.md:71`, on items that are
   operator-owned: the CVE-2026-85091 exception sign-off or an alpine base refresh, promotion of the
   derived postgres image from CANDIDATE to APPROVED, acceptance of the clock observer
   CVE-2026-82049 finding, rescans of redis/opensearch/minio/elasticmq, a pip-audit SIGABRT
   disposition, and Docker bridge mTLS validation. I cannot discharge a sign-off on your behalf, so
   "the whole of G1" cannot be completed autonomously under any option below.
2. **The four unscanned images are not pulled locally.** Only postgres images exist locally
   (`docsuri/postgres-alpine-16.15-nosu` in `:local`/`:repro`/`:rep2`/`:rep3`, plus `postgres:16`).
   The redis, opensearch, minio, and elasticmq digests pinned in
   `ops/platform-integrity/sbom-targets.json` must be pulled before any rescan. Note this overlaps
   with your Q3=A decision to bring the stack up on Colima, so the pulls are needed either way.
3. **G1 was REM-1's gate and REM-1 is already marked complete.** Absorbing G1 means reopening a
   closed unit's acceptance criteria.

For context, there is no compose file for the service stack in the repo — only
`backend/docker-compose.yml` — so the Q3=A bring-up will need a new stack definition regardless.

## Question 1
Given that G1 is not a REM-4 gate, how should G1 be handled in this corrective unit?

A) Absorb the parts of G1 this unit can actually execute — the redis/opensearch/minio/elasticmq rescans, the pip-audit SIGABRT disposition, and Docker bridge mTLS validation — and leave the CVE-2026-85091 sign-off, postgres image promotion, and CVE-2026-82049 acceptance on a separate operator track. Accept that REM-4 will still wait on G2/G4/G5, not G1.

B) Absorb all of G1 as originally chosen, including writing the operator sign-off steps into the runbook, accepting that the unit cannot fully close G1 and that REM-4 remains gated on G2/G4/G5 regardless

C) Do not absorb G1 at all. Keep this corrective unit strictly on REM-3 (Q1-Q4 as answered), and treat G1 closure as a prerequisite task on the separate REM-1/G1 track that must finish before REM-4 planning resumes

D) Absorb G1 and additionally pull G2/G4/G5 closure into this unit, since REM-4 actually needs those — making this a full remediation-closure unit rather than a REM-3 corrective

X) Other (please describe after [Answer]: tag below)

[Answer]: D) Absorb G1 and additionally pull G2/G4/G5 closure into this unit, since REM-4 actually needs those — making this a full remediation-closure unit rather than a REM-3 corrective

## Question 2
For the image pulls that both Q3=A and any G1 rescan require, how should this be handled?

A) Pull the four pinned digests from `sbom-targets.json` as part of this unit, since Q3=A needs the stack up on Colima anyway and the digests are already pinned and approved-for-scan

B) Pull only what Q3=A needs to run the live smoke test (postgres, redis, opensearch), and defer minio and elasticmq pulls to whichever unit needs them

C) Leave all pulls to you as an operator step, and have this unit work only against what is already local

X) Other (please describe after [Answer]: tag below)

[Answer]: A) Pull the four pinned digests from `sbom-targets.json` as part of this unit, since Q3=A needs the stack up on Colima anyway and the digests are already pinned and approved-for-scan
