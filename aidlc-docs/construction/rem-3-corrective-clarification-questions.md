# REM-3 Corrective Unit — Scope Clarification Questions

I accepted all four answers and recorded them in `aidlc-docs/audit.md`. No contradictions were
found among them. However, validating them against this machine surfaced four constraints that
change how the corrective unit must be scoped and sequenced, so I need these resolved before I
write the plan.

## Context you should know first

- **G1 is already blocked independent of REM-3.** `ops/platform-integrity/cve-disposition.md:71`
  shows G1 waiting on your CVE-2026-85091 exception sign-off (or alpine base refresh), promotion
  of the derived postgres image from CANDIDATE to APPROVED, and rescans of
  redis/opensearch/minio/elasticmq. Per Q2=C, REM-4 therefore stays deferred until those are
  closed on their own track.
- **No containers are running.** `docker ps` is empty, so Q3=C's live smoke test currently has
  no target services.
- **The container runtime is Colima, not OrbStack.** `orbstack` is absent; `colima` is running
  (Docker 29.5.2, virtiofs, socket at `~/.colima/default/docker.sock`). The REM-3 infrastructure
  design assumes OrbStack in 6 places across `deployment-architecture.md` and
  `infrastructure-design.md`, and `ops/server/install.sh` also references OrbStack.
- **Q4=A work requires root.** Keychain ACL rewriting without `-A`, secret rotation, `launchctl`
  bootstrap/verify as root, and Docker bridge mTLS validation all need your sudo. I will write
  them as operator runbook steps rather than executing them myself.

## Question 1
What should the corrective unit be called, and how should it relate to the existing REM-3 unit?

A) New unit ID `REM-3R` (corrective), created alongside the retained REM-3 artifacts, with the original REM-3 record preserved and marked superseded-by-REM-3R

B) Re-open the existing REM-3 unit under the same ID, appending a corrective plan and superseding annotation to the existing REM-3 documentation

C) New unit ID `REM-5` treated as a normal forward unit, with no supersession semantics — simplest bookkeeping, but loses the audit trail that REM-3 was corrected rather than completed

X) Other (please describe after [Answer]: tag below)

[Answer]: B) Re-open the existing REM-3 unit under the same ID, appending a corrective plan and superseding annotation to the existing REM-3 documentation

## Question 2
Given Q1=B says "rewrite rather than patch", what happens to the existing REM-3 source files?

A) Delete the seven defective adapters and the REM-3 frontend components and regenerate them from the approved design, keeping the design documents as the specification

B) Keep the files in place but treat them as unused draft, regenerate under corrected names/paths, and remove the originals only after the new code passes all gates

C) Rewrite in place, preserving the existing module and file paths so downstream imports and provision scripts keep working, changing only the bodies

X) Other (please describe after [Answer]: tag below)

[Answer]: A) Delete the seven defective adapters and the REM-3 frontend components and regenerate them from the approved design, keeping the design documents as the specification

## Question 3
Q3=C requires a live smoke test against real Postgres/Redis/OpenSearch, but no containers are running and the runtime is Colima rather than the assumed OrbStack. How should this be handled?

A) Bring up the container stack on Colima as part of this corrective unit, and update the infrastructure design and `ops/server/install.sh` to target Colima instead of OrbStack

B) Bring up the containers on Colima for testing purposes only, and leave the OrbStack-vs-Colima re-baselining as a separate infrastructure decision to be made before REM-4

C) Do not bring up containers in this unit; implement and statically verify everything, and record the live smoke test as an operator-executed gate that blocks unit completion until run

D) Use whatever the existing ops tooling already assumes, and report back if it fails, without pre-deciding the runtime question

X) Other (please describe after [Answer]: tag below)

[Answer]: A) Bring up the container stack on Colima as part of this corrective unit, and update the infrastructure design and `ops/server/install.sh` to target Colima instead of OrbStack

## Question 4
The corrective unit has to satisfy Q4=A's operator work (real keychain ACLs, secret rotation, root re-verification) as well as the Q3=C code gates. How should sequencing be handled?

A) Sequence strictly: code rewrite plus all static gates first, then a single consolidated operator runbook covering keychains, launchd, secret rotation, and the live smoke test

B) Split into two deliverables: an agent-executable code/static-gate phase, then a separate operator-only remediation phase with its own approval gate before proceeding

C) Do the operator runbook first, since the currently installed workers and `-A` keychains are live exposure that should be closed before more code work

X) Other (please describe after [Answer]: tag below)

[Answer]: A) Sequence strictly: code rewrite plus all static gates first, then a single consolidated operator runbook covering keychains, launchd, secret rotation, and the live smoke test

## Question 5
Should the corrective unit also absorb the still-open G1 items, or leave them on a separate track?

A) Leave G1 items entirely separate and operator-owned; the corrective unit only guarantees that it does not add new G1 violations, and REM-4 stays deferred until G1 closes on its own

B) Have the corrective unit close the G1 items it can technically close (image rescans, pip-audit disposition, Docker bridge mTLS validation) and leave only the CVE-2026-85091 sign-off and postgres image promotion to you

C) Fold the whole of G1 into the corrective unit so that REM-4 becomes unblockable as soon as this unit completes

X) Other (please describe after [Answer]: tag below)

[Answer]: C) Fold the whole of G1 into the corrective unit so that REM-4 becomes unblockable as soon as this unit completes
