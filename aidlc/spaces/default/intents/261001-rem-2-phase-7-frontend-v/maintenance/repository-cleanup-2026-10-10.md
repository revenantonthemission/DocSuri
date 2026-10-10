# Repository cleanup before v2 — 2026-10-10

Status: completed for the verified cleanup set. Initially archived on the current
disk; transferred to SSD01 at the user's subsequent request on 2026-10-10.
This is repository maintenance requested after the completed frontend workflow.

## Retained baseline

The retained baseline is the current `develop` checkout at
`50c3a665bb6d4b5cb252b812c63563ee7b764a2f`, including existing local changes.
No branch, commit, deployment, database, or workflow state was changed.

Retained `backend/`, `frontend/`, `ingestion/`, `ops/`, `platform_integrity/`,
`shared/`, `tests/`, manifests, lockfiles, migrations, environment files, and
installed dependencies, current development tooling, and `aidlc/` records.
The custom unit-review skill still consumes `.aidlc-rule-details/`.

The running Next process uses `frontend/.next/standalone` as its working directory.
Preserved all of `.next`; building or running the default E2E command would
overwrite the deployed output. Backend/runtime retirement was not established
by this bounded audit. CDK sources remain; only generated `ops/cdk/cdk.out/` was
removed after checking manifests, ignore rules, service launches, and backups.

## Completed changes

- Removed 135 untracked disposable cache/output paths, totaling 39,550,692 bytes
  (37.7 MiB):
  Python bytecode, pytest/ruff caches, frontend coverage, coverage data,
  TypeScript incremental state, Finder metadata outside dependency trees, and CDK output.
- Removed the now-empty `backup/` directory tree.
- Added ignore patterns for heap snapshots and local coverage output, preserving
  the existing local `.gitignore` edits.
- Corrected frontend README references to the committed wire DTO generator and
  removed an obsolete test count and missing design-document link.
- Compared SHA-256 hashes of 2,153 previously tracked files against the pre-cleanup
  snapshot. Expected changes include the documented CI, ignore, README, and
  runbook-reference edits, the exact archived tracked files, and a concurrent
  per-clone audit append. Retained service source files are unchanged.

Detailed execution receipts were copied from `/tmp/docsuri-cleanup-20261010/`
into the archive's `recovery/` directory.

## Archived files

Archive: `/Volumes/SSD01/DocSuri-archive/2026-10-10-pre-v2/`.
Original repository-relative paths are preserved under `legacy/`.

| Path | Files | Bytes | Reason |
| --- | ---: | ---: | --- |
| `aidlc.archive/` | 426 | 9,169,282 | Historical lifecycle/design/operations record |
| `aidlc.archive3/` | 36 | 50,596 | Abandoned intent-capture snapshot |
| `aidlc.archive4/` | 30 | 47,783 | Abandoned intent-capture snapshot |
| `reports/` | 5 | 65,293 | Historical July reports and AWS drain record |
| `tools/` | 148 | 1,282,932 | Legacy standalone code/design/traceability reviewers |
| `server.heapsnapshot` | 1 | 131,069,810 | Diagnostic capture |
| `tui.heapsnapshot` | 1 | 176,304,055 | Diagnostic capture |
| `.github/workflows/sync-stories.yml` | 1 | 951 | Invokes a missing legacy script and stories path |
| **Total** | **648** | **317,990,702** | **303.3 MiB** |

All 648 files passed SHA-256 and mode verification before source removal.
Originals were rechecked for concurrent changes, then removed; archived files
were verified again afterward. The archive includes previously untracked records.
The subsequent SSD01 transfer verified all 671 files (339,819,999 bytes), including
recovery data and receipts, against the local archive, then removed the redundant
local copy. All 648 legacy manifest entries and the complete Git recovery bundle
also passed independent verification. One filename differed only by Unicode
normalization. The external verification/removal receipt is
`/Volumes/SSD01/DocSuri-archive/2026-10-10-local-copy-removal.json`.

## Completed transfer and reference repairs

1. Created the dated archive beside the repository, recording HEAD, existing
   working-tree changes, paths, sizes, and SHA-256 hashes.
2. Copied and verified the full archive set and unchanged originals before
   removing source paths. Verified all archived copies again after removal.
3. Retained the dated runbook at
   `ops/platform-integrity/runbooks/g1-operator-runbook-2026-10-01.md` with its
   original dated body unchanged. Its status is historical; current status remains in
   `ops/platform-integrity/sbom-targets.json` and `cve-disposition.md`.
4. Repaired three references in `ops/platform-integrity/cve-disposition.md` and
   `construction/u1-job-skeleton/code-generation/postgres-remediation-and-launcher-handoff.md`
   within this intent, preserving historical claims and dates.
5. Recorded the historical `aidlc-docs/` mapping to the archive's
   `legacy/aidlc.archive/spaces/default/intents/261001-default/`. The detailed
   operator handoff and historical plans remain recoverable there.
6. Removed only the three archived root tool projects from CI's pending closure
   list. Dependency discovery and checks remain, as does `shared/python/tools/`.
7. Preserved the live frontend's build, dependencies, and service source. Changes
   remain uncommitted for review; no remote workflows or GitHub issues were changed.

## Verification

The frontend checks below ran before archive transfer. Their source inputs were
unchanged by the transfer.

Final verification passed: 648 archived file hashes and modes matched; all 154
archived tracked files matched the saved baseline; 1,993 retained tracked files
were byte-identical. The six expected changed tracked files were CI, gitignore,
frontend README, two runbook-reference documents, and the concurrent audit append.
The Git bundle digest matched, HEAD was unchanged, and the live standalone build
remained present. CI YAML parsed successfully with all 15 jobs; its only edit
removed the three archived tool names. All five historical mapping targets and
three retained-runbook pointers resolved. Changed-file whitespace checks passed.

- `pnpm typecheck`: passed.
- `pnpm check:types`: passed.
- `pnpm test:contracts`: passed, 32 tests in 2 files.
- `pnpm check:consumers`: failed with `consumer inventory incomplete`.
  Diagnosis: the underlying error is `actual TypeScript consumer inventory drift`.
  All 17 adapters and 64 wire boundaries match, and schema/fixture files exist.
  `shared/typescript-consumers.json` records 44 source digests versus 46 current
  consumers; four imports were removed and four added. The checked source inputs
  are byte-identical to the pre-cleanup snapshot. This pre-existing snapshot
  inconsistency was left unchanged.

No production build, restart, deployment, issue synchronization, or package
installation was performed.

## Evidence limits

Graph-assisted frontend and legacy dependency audits used Tier 2 verification,
exact-path coverage checks, and direct reads for excluded/partially parsed files.
The most recent checked graph generation was `2026-10-10T07:57:41Z`.
Ignored development tooling was inspected for references as well. This does not
establish that every retained source file is necessary or that every backend
module is deployed; no source deletion is justified merely by a missing graph edge.

## Recovery and later transfer

The archive contains `manifest.json`, `verification.json`, `completion.json`,
and a `README.md` with recovery instructions. `recovery/repository.bundle`
preserves all available Git refs and passed `git bundle verify`.
`recovery/working-tree.patch`, `index.patch`, and status receipts preserve tracked
local differences and staged state before archival. This is not a database or
whole-machine backup.

Git bundle SHA-256:
`4b9573ccd78a17cc608a4817ad1a097ef293db3e29f557736349f880dfae301b`.

Move the entire dated directory together when transferring it to SSD01. Update
this record and the retained G1 runbook's archive location afterward. The archive
is outside the Git checkout and will not be included in a repository commit.
