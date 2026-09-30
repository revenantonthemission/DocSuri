# REM-4 Prerequisite Decision — G4/G5 Cannot Close Without REM-4

I recorded both answers. **Q2=A is accepted and executable.** Q1=D is blocked by a circular
dependency that no scoping choice can remove, so it needs an explicit decision from you.

## What I confirmed

Q1=D's rationale is factually right: REM-4 does need G2/G4/G5. But the gate definitions show that
G4 and G5 cannot close until REM-4's own deliverables exist.

From `aidlc-docs/inception/plans/verification-remediation-2026-09-18-workflow-plan.md`:

| Gate | Findings it must close |
|---|---|
| G2 service/store/worker | F01/F02/F05/F07, RJ-AC01~08/12 |
| G3 lifecycle/edge | F04/F09/F10, RJ-AC05/09/10/11 |
| G4 통합/browser/compatibility | **F03/F07/F11/F12**, RJ-AC01~12, US-RJ1~3 |
| G5 복구/live preflight | safe repair approval scope, RES-2/4/10/12, **F03**/F04 |

REM-4's scope is exactly **F03/F11/F12** (`unit-of-work-plan.md:270`).

G4 explicitly requires "corpus report와 no-match/저하" behaviour, and its findings column contains the
complete REM-4 finding set. G5 requires F03, which is the corpus-audit finding that R4A
`CorpusEvidenceService` is meant to produce. So **G4/G5 are downstream of REM-4's evidence work**,
not parallel to it.

This conflicts with your first-round **Q2=C** ("Defer REM-4 entirely until REM-3 is genuinely
verified... plan nothing new yet"). Absorbing G4/G5 into this unit requires starting REM-4 now.

## Deliverable split under Q1=D

| Gate | Absorbable now? | Why |
|---|---|---|
| G1 | Partly | Rescans, pip-audit disposition, Docker bridge mTLS yes; CVE-2026-85091 sign-off, postgres CANDIDATE→APPROVED, CVE-2026-82049 stay operator-owned |
| G2 | Yes | F01/F02/F05/F07 are REM-2's scope; this unit already rewrites that worker pipeline |
| G3 | Yes | REM-3's own gate, already in scope |
| G4 | **No** | Needs F03/F11/F12 corpus report and no-match/degradation behaviour from REM-4 |
| G5 | **No** | Needs F03 evidence from REM-4's R4A `CorpusEvidenceService` |

## What is settled regardless of your answer

- Q1=B: re-open REM-3 under the same ID, append corrective plan and superseding annotation.
- Q2=A: delete the seven defective adapters and the REM-3 frontend components, regenerate from the
  approved design which stays the specification.
- Q3=A: bring the container stack up on Colima, retarget the infrastructure design and
  `ops/server/install.sh` from OrbStack to Colima.
- Q4=A: code rewrite and all static gates first, then one consolidated operator runbook.
- Image pulls: all four pinned digests from `sbom-targets.json`.

## Question 1
G4 and G5 are structurally blocked on REM-4's F03/F11/F12 deliverables. How do you want to proceed?

A) Start the minimal read-only REM-4 evidence slice now, inside this unit — R4A `CorpusEvidenceService` audit/report emission only, with no mutation port and no R4R `CorpusRepairRunner`. This unblocks the F03 evidence G5 needs and the corpus-report part of G4, while keeping REM-4's destructive capability explicitly deferred.

B) Scope this unit to G1/G2/G3 plus the REM-3 corrective work, mark G4/G5 as blocked-on-REM-4, and start REM-4 properly as its own unit afterwards with its own planning cycle.

C) Absorb full REM-4 into this unit including R4R `CorpusRepairRunner` and repair approval tooling, so G1 through G5 all close together and REM-4 is fully done as a side effect.

X) Other (please describe after [Answer]: tag below)

[Answer]: B) Scope this unit to G1/G2/G3 plus the REM-3 corrective work, mark G4/G5 as blocked-on-REM-4, and start REM-4 properly as its own unit afterwards with its own planning cycle.

## Question 2
Whichever scope you choose above, how should the deferred G4/G5 portion be recorded so it is not
silently treated as satisfied?

A) Add explicit "BLOCKED-ON-REM-4" markers to the gate status in `aidlc-state.md` and `audit.md`, so no downstream reader can infer G4/G5 passed

B) Record the deferral only in this decision file and the corrective plan, leaving gate status files untouched until the work actually lands

C) Add the markers, and also add a blocking verification gate in the Build and Test phase that fails while G4/G5 remain unsatisfied

X) Other (please describe after [Answer]: tag below)

[Answer]: A) Add explicit "BLOCKED-ON-REM-4" markers to the gate status in `aidlc-state.md` and `audit.md`, so no downstream reader can infer G4/G5 passed
