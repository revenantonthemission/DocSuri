# Quality gates

Date: 2026-11-23
Stage: CI Pipeline, for U5 (topics and digests), U6 (the approved Notion export) and U8 (service operations and integration).

This document says what must pass before a merge into `develop` and before a release, which workflow job checks each thing, and where the gates have gaps. It describes the 13 workflow files as they stand in `.github/workflows/`. This stage changes none of them. **Nothing has run on GitHub for this work yet.** The first run is the draft pull request of Q4 below, and it has not happened. Wherever a result would go, this document says "no run yet".

Upstream documents this one draws on:

- U5's code summary: [../u5-topics-digests/code-generation/code-summary.md](../u5-topics-digests/code-generation/code-summary.md)
- U6's code summary: [../u6-approved-export/code-generation/code-summary.md](../u6-approved-export/code-generation/code-summary.md)
- U8's code summary: [../u8-service-operations-integration/code-generation/code-summary.md](../u8-service-operations-integration/code-generation/code-summary.md)
- Build and Test's summary: [../build-and-test/build-and-test-summary.md](../build-and-test/build-and-test-summary.md)
- Build and Test's test results: [../build-and-test/test-results.md](../build-and-test/test-results.md)
- Also used: [../build-and-test/cross-unit-traceability.md](../build-and-test/cross-unit-traceability.md), U8's [release runbook](../u8-service-operations-integration/code-generation/u8-release-runbook.md), and this stage's [questions and answers](ci-pipeline-questions.md).

A "lane" below is a Unit's own workflow file and the test phases it runs. "The complete verification" is `u8-complete-verification.yml`, which checks the whole application and reports four checks named "U8 complete / ..." (`ci-pipeline-questions.md:15-16`).

## Decisions this document rests on

The maintainer answered all six questions with A and confirmed the summary with "Looks correct" (`ci-pipeline-questions.md:75, 92, 108, 131, 148, 169, 194`).

| Question | Decision in plain words | Consequence here |
|---|---|---|
| Q1 | The earlier Units' lanes stay as they are (`ci-pipeline-questions.md:69, 173`). | Each test command Build and Test recorded that no workflow runs is listed under "Known gaps" for a follow-up piece of work. The lanes of U1 and U7, and U3's backend, keep no coverage floor in CI. The check before Operation records "CI enforces every recorded test command" as not met. |
| Q2 | The fixed home-folder path in U8's design, code, tests and plan stays as designed (`ci-pipeline-questions.md:86, 174`). | Nothing reopens. This document does not repeat the path. |
| Q3 | The racy U6 test, `frontend/test/u6-export/outcome-step.test.tsx`, is fixed in a follow-up piece of work after this work merges into `develop` (`ci-pipeline-questions.md:102, 175`). | Until then a red run on it is recorded as failed. A second run that passes lets the pull request merge on GitHub. Both results are kept. See "A red run". |
| Q4 | The first run on GitHub happens now, as a draft pull request into `develop` (`ci-pipeline-questions.md:125, 176`). | `develop` is merged into the branch first. The maintainer sees the exact file list and gives the word for the commit, the push and the pull request. **None of this has happened yet.** Each check's real result is to be recorded before this stage is approved. |
| Q5 | Branch protection requires the 17 check names of U8's release runbook plus the Next app job (`ci-pipeline-questions.md:142, 177`). | The list is under "Branch protection". Only the maintainer can switch it on, after a first run shows each name reporting. |
| Q6 | The check before Operation is recorded as failed, with every open item and the stage that owns it, and brought to this stage's approval (`ci-pipeline-questions.md:163, 178`). | This departs from the stage file's instruction to stop the transition and go back to the owning stage (`.claude/aidlc-common/stages/construction/ci-pipeline.md:84-85`). It is the maintainer's decision. Operation opens with those items open, even if the first run on GitHub fails. |

Assumptions the maintainer left unchanged (`ci-pipeline-questions.md:40-48, 179-187`):

- **The interim merge rule ends when this stage is approved.** `CONVENTIONS.md:13-26` lets completed work merge into `develop` despite known, pre-existing legacy CI failures "until that work establishes the replacement checks". This stage is that work. From its approval on, a pull request into `develop` merges only when its checks pass, which is also the project rule "NEVER merge without CI passing" (`aidlc/spaces/default/memory/project.md:109`). A check that fails on this work's own first run is not a legacy failure, so it holds this pull request too (`ci-pipeline-questions.md:44`). The only exception is the racy U6 test under Q3.
- **Merge commits.** The gates are described for merge commits. No repository setting is changed (`ci-pipeline-questions.md:45`).
- **Protection settings to propose:** no required review, administrators included, branches up to date before a merge (`ci-pipeline-questions.md:46`). They are proposals.
- **Releases are installed in person.** Nothing in CI deploys (`ci-pipeline-questions.md:37`; `.github/workflows/release.yml:4-5`).
- **No workflow file that a Unit claims is changed** (`ci-pipeline-questions.md:48, 187`). The six files no Unit claims also stay as they are, because Q1 = A keeps the U1, U3 and U7 lanes and Q5 = A does not rename the branch-name job (`ci-pipeline-questions.md:75, 148`); so this stage changes no workflow file.

## Gates before a merge into develop

These are the 18 required checks: the 17 names of U8's release runbook (`u8-release-runbook.md:57-69`) and the Next app job. Each "Name it reports" was checked against the job's `name:` line in the workflow file. **All 17 runbook names match the files exactly. No name differs.**

"Blocks" means: once the maintainer switches branch protection on, GitHub refuses a merge while the check is red. It is not on yet: it waits for a first run that shows each name reporting (`ci-pipeline-questions.md:140, 177`). Until then the maintainer keeps the same rule by hand: a pull request merges only when its checks pass (`ci-pipeline-questions.md:44`).

| Name it reports | Workflow file and job | What it enforces | Blocks |
|---|---|---|---|
| REM-1 isolated rules and adapters | `ci.yml`, `platform-integrity` (`.github/workflows/ci.yml:36-37`) | Install from the lock file with no changes (a frozen install), Ruff, pytest for `platform_integrity` (`ci.yml:54-56`) | Yes, once protection is on |
| shared (SSOT · drift · pytest) | `ci.yml`, `shared` (`ci.yml:57-58`) | Schema drift guard, Python consumer inventory, Ruff, pytest (`ci.yml:71-78`) | Yes, once protection is on |
| ingestion (U1) | `ci.yml`, `ingestion` (`ci.yml:80-81`) | Ruff and pytest for `ingestion` (`ci.yml:94-97`) | Yes, once protection is on |
| discovery (U2) | `ci.yml`, `discovery` (`ci.yml:99-100`) | Ruff and pytest with the `api` extra (`ci.yml:113-116`) | Yes, once protection is on |
| summarization (U7) | `ci.yml`, `summarization` (`ci.yml:118-119`) | Ruff and pytest with all extras (`ci.yml:132-138`) | Yes, once protection is on |
| ops (U6 reliability/detection) | `ci.yml`, `ops` (`ci.yml:140-141`) | Ruff and pytest for `ops` (`ci.yml:161-164`) | Yes, once protection is on |
| backend app-shell (mounts U2/U3) | `ci.yml`, `backend` (`ci.yml:166-167`) | Ruff and pytest for the backend shell (`ci.yml:180-183`) | Yes, once protection is on |
| accounts + library (root tests/ — U3 · U4) | `ci.yml`, `root-suites` (`ci.yml:185-186`) | Ruff over accounts, library, ops modules and root `tests/`; pytest on `tests/accounts`, `tests/library`, `tests/performance` (`ci.yml:201-209`) | Yes, once protection is on |
| Dependency review (PR-only · npm + pip) | `ci.yml`, `dependency-review` (`ci.yml:214-215`) | Fails on a newly introduced dependency with a high-severity advisory (`ci.yml:225-227`). Runs on pull requests only (`ci.yml:220`) | Yes, once protection is on |
| Security Scan (SCA + Secrets) | `ci.yml`, `security` (`ci.yml:229-230`) | pip-audit on backend, ingestion and ops; blocking gitleaks scan (`ci.yml:244-265`) | Yes, once protection is on |
| REM-1 full closure audit (not diff-only) | `ci.yml`, `rem1-closure-audit` (`ci.yml:271-272`) | pip-audit over every project found by `pyproject.toml`; declared images digest-pinned (`ci.yml:288-318`) | Yes, except four named projects only warn (see "Security gates") |
| REM-1 isolated Postgres acceptance | `ci.yml`, `rem1-isolated` (`ci.yml:355-356`) | The isolated Postgres tests run for real; the job fails on any skip or on no passes (`ci.yml:403-425`) | Yes, once protection is on |
| REM-1 platform suite on macOS (APFS semantics) | `ci.yml`, `macos-filesystem` (`ci.yml:430-431`) | Platform and ops suites on macOS; U8's arrangement suite as root with the 80% macOS coverage floor (`ci.yml:445-463`) | Yes, once protection is on |
| U8 complete / shared-contracts | `u8-complete-verification.yml`, `shared-contracts` (`.github/workflows/u8-complete-verification.yml:28-29`) | Canonical schema drift, generated binding drift, shared contract suite (`u8-complete-verification.yml:41-49`) | Yes, once protection is on |
| U8 complete / frontend | `u8-complete-verification.yml`, `frontend` (`u8-complete-verification.yml:51-52`) | Types, ESLint, U8's Vitest lane with coverage, the workspace build gate (`u8-complete-verification.yml:70-85`) | Yes, once protection is on |
| U8 complete / backend | `u8-complete-verification.yml`, `backend` (`u8-complete-verification.yml:87-88`) | Image pins, seven Ruff runs, set-up and migration of a throwaway test database (a "realm"), coverage by parts with the combined report, and the `u2-regression` phase, which runs U2's tests against the assembled application (`u8-complete-verification.yml:108-185`) | Yes, once protection is on |
| U8 complete / browser | `u8-complete-verification.yml`, `browser` (`u8-complete-verification.yml:187-188`) | Fixtures, the complete verification run, the previous release's critical journeys; uploads the run's result files (VerificationRun JSON) for 90 days (`u8-complete-verification.yml:249-270`). Needs the other three jobs (`:191`) | Yes, once protection is on |
| next app (tsc · drift guards · tests · production build · audit) | `next-app.yml`, `next-app` (`.github/workflows/next-app.yml:32-33`) | Whole-program and e2e type checks, drift guards, the full frontend test suite, production build, production dependency audit at high (`next-app.yml:53-68`) | Yes, once protection is on |

All of these workflows run on pull requests into `develop` and `main` (`ci.yml:14-15`, `u8-complete-verification.yml:10-11`, `next-app.yml:17-18`). The complete verification and Next app have no path filter, so they report on every pull request (`u8-complete-verification.yml:3-6`; `next-app.yml:8`).

## Other checks that report but are not required

| Check | Where | Why it is not required |
|---|---|---|
| CodeQL: "Analyze (python)" and "Analyze (javascript-typescript)" | `.github/workflows/codeql.yml:22-23, 33` | Not in the runbook's list, and Q5 = A did not add it (option C would have, `ci-pipeline-questions.md:144`). Its findings land in the Security tab (`codeql.yml:3, 27`). |
| Branch-name check, which reports the bare name "check" | `.github/workflows/branch-name-check.yml:15` (the job has no `name:`) | Not in the runbook's list, and Q5 = A did not add it. Requiring it would first need a name of its own (`ci-pipeline-questions.md:144`). It still fails a pull request whose branch name breaks `CONVENTIONS.md` (`branch-name-check.yml:25-31`). |
| The per-Unit lanes U1 to U7 (`u1-paper-journey.yml` to `u7-controlled-platform-protocols.yml`) | Each lane's own file | They run only when their paths change, so a required lane could hold a pull request forever (`u8-release-runbook.md:75-76`). Their jobs report bare names such as `frontend` and `backend`, which protection does not require (`u8-release-runbook.md:71-73`). |
| REM-1 PBT Full (2,000 examples) | `ci.yml:322-324` | Runs only on the nightly schedule or a manual run, never on a pull request (`ci.yml:324`). |

## Coverage floors

The rule is 80% line coverage for new code (`aidlc/spaces/default/memory/project.md:151`; `ci-pipeline-questions.md:34`), and the floor is never lowered (`project.md:107`). Where it is enforced in CI:

| Lane | Where the run is | Where the floor is set |
|---|---|---|
| U2 frontend (cumulative: U1 to U6 and U8 tests over all of `src/`) | `.github/workflows/u2-account-controls.yml:51-53` | `frontend/vitest.u2-account-controls.config.ts:26`, merged by `frontend/vitest.u2-cumulative.config.ts:1-8` |
| U2 backend, on a fresh, throwaway test database, after the job that runs U2's five test phases | `u2-account-controls.yml:104-135` | `backend/.coveragerc.u2:38` |
| U3 frontend | `u3-paper-corpus-capabilities.yml:52-54` | `frontend/vitest.u3-corpus.config.ts:44-46` (80% on `src/u3-corpus`, 48% on `src/App.tsx`) |
| U4 frontend | `u4-research-novelty.yml:77-79` | `frontend/vitest.u4-research.config.ts:26` (80% on `src/u4-research`, 48% on `src/App.tsx`) |
| U4 backend | `u4-research-novelty.yml:120-122` | `backend/.coveragerc.u4:14`, read by `scripts/verify_docsuri_u4.py:1251-1260` |
| U5 frontend | `u5-topics-digests.yml:77-79` | `frontend/vitest.u5-topics.config.ts:25` |
| U5 backend | `u5-topics-digests.yml:121-123` | `backend/.coveragerc.u5:25`, read by `scripts/verify_docsuri_u5.py:1387-1396` |
| U6 frontend | `u6-approved-export.yml:86-88` | `frontend/vitest.u6-export.config.ts:25` |
| U6 backend | `u6-approved-export.yml:144-146` | `backend/.coveragerc.u6:28`, used by `scripts/verify_docsuri_u6.py:1126`; plus the separate coverage report on `scripts/u6_preservation.py`, also held at 80% (`verify_docsuri_u6.py:1175-1179`) |
| U8 frontend (complete verification) | `u8-complete-verification.yml:80-82` | `frontend/vitest.u8-complete.config.ts:45` |
| U8 backend (complete verification, combined report of all parts) | `u8-complete-verification.yml:178-181` | `backend/.coveragerc.u8:134`; `scripts/verify_docsuri_u8.py:2766` (`--fail-under=80`) |
| U8 macOS adapters | `ci.yml:455-463` (`--cov-fail-under=80`) | `backend/.coveragerc.u8-macos:12` |

The 48% floor on the shared `src/App.tsx` in the U3 and U4 configs was set by earlier pieces of work and is unchanged here. The U2 cumulative lane counts `App.tsx` inside one 80% line floor over all of `src/` taken together (`frontend/vitest.u2-account-controls.config.ts:24, 26`; `frontend/vitest.u2-cumulative.config.ts:4-5`). No CI floor holds `App.tsx` on its own at 80%. Whether the 48% meets `project.md:107` is for the maintainer to decide in a follow-up; it is listed under "The check before Operation".

Lanes that enforce no floor in CI:

- **U1.** The frontend job runs Vitest without `--coverage` (`u1-paper-journey.yml:55-56`), so the threshold in `frontend/vitest.u1-paper-journey.config.ts:19` is not applied there. The Python job only collects tests (`u1-paper-journey.yml:75-80`).
- **U7.** The lane runs the component tests without coverage (`u7-controlled-platform-protocols.yml:42-45`).
- **U3 backend.** The lane runs the five test phases (database, repository, component, integration, operations) but no coverage phase (`u3-paper-corpus-capabilities.yml:65, 92`), and `backend/.coveragerc.u3` holds no `fail_under`.
- **The eight `ci.yml` suite jobs** run pytest with no coverage floor (`ci.yml:56, 78, 97, 116, 138, 164, 183, 209`).
- **Next app.** Its test step runs `pnpm run test` (`next-app.yml:57-58`), which is `vitest run` (`frontend/package.json:23`), not `test:coverage` (`frontend/package.json:28`). The full frontend suite therefore holds no floor in CI; the per-Unit frontend lanes above measure their own source. This departs from `project.md:105` ("NEVER skip lint, typecheck, or test:coverage in CI"). It predates this work and is listed as an open item for the maintainer, not changed here.

No floor is weakened to make a run pass (`ci-pipeline-questions.md:34`; `aidlc/spaces/default/memory/project.md:107`).

## Security gates

| Gate | Where | What it does | Blocks |
|---|---|---|---|
| Dependency review | `ci.yml:214-227` | On pull requests only, fails when the change adds a dependency with a high-severity advisory. Pre-existing debt does not fail it (`ci.yml:216-219`). | Yes, once protection is on. On a push it is skipped (`ci.yml:220`). |
| pip-audit in the security job | `ci.yml:244-255` | Audits the frozen third-party closure of backend, ingestion and ops with pip-audit 2.10.1. The maintainer left pip-audit to CI on 2026-11-15 (`ci-pipeline-questions.md:35`). | Yes, once protection is on. |
| Gitleaks secret scan | `ci.yml:256-265` | Scans the current tree (`--no-git`) and fails on any finding (`--exit-code 1`). History is not scanned. | Yes, once protection is on. |
| CodeQL | `codeql.yml:21-42` | Python and JavaScript/TypeScript analysis; results go to the Security tab. | No. It is not a required check (Q5 = A). |
| Full closure audit | `ci.yml:271-318` | pip-audit over every project in the repository, not only the changed ones, plus the digest-pin check of declared images. | Yes for every project except four. A finding in `backend/modules/discovery`, `backend/modules/summarization`, `platform_integrity` or `shared/python` prints a warning instead of failing (`ci.yml:291, 303-304`), until the maintainer decides what to do about CVE-2026-82049 and CVE-2026-85091 (`ci.yml:283-285`). This document records that as a warning, not a gate. |

No production secret enters CI. The workflows use throwaway test databases and fake providers, and `GITHUB_TOKEN` writes only the tag, the GitHub Release with its archive, and CodeQL's results (`ci-pipeline-questions.md:36`; `release.yml:12-15, 27-28, 124-125`; `codeql.yml:27`).

## Gates before a release

- **A pull request from `develop` into `main`.** Every later release is such a pull request (`u8-release-runbook.md:45-46`; `CONVENTIONS.md:8, 25-26`). On it run `ci.yml`, `next-app.yml`, `codeql.yml` and the complete verification, which all take pull requests into `main` (`ci.yml:15`, `next-app.yml:18`, `codeql.yml:10`, `u8-complete-verification.yml:11`), and the branch-name check, which allows `develop` as a source (`branch-name-check.yml:24-25`). U1's and U7's lanes run there only when their paths change. U2's to U6's do not run there at all (see "Known gaps").
- **The first release is different.** `main` does not exist yet, so the first v2 release is one push of a chosen `develop` commit as `main`, not a pull request. That commit's complete verification and `ci.yml` jobs must have passed (`u8-release-runbook.md:10-26`).
- **What `release.yml` does on the push to `main`** (`release.yml:8-10`): it works out the next version from conventional commits and creates an annotated `v` tag, using `v2.0.0` when no `v2.*` tag exists (`release.yml:39-59`); a guard fails the job before the GitHub Release is published if the first v2 tag is not `v2.0.0` (`release.yml:61-66`); the tag already exists on `origin` by then, and the runbook says to delete it there (`u8-release-runbook.md:41-43`); when a tag was made, it publishes the GitHub Release (`release.yml:68-74`); a read-only job builds the workspace from the tagged commit (`release.yml:78-115`); a narrow job attaches `docsuri-workspace.tar.gz` and its SHA-256 (`release.yml:118-137`). Nothing deploys (`release.yml:139-140`).
- **The in-person install checks the complete verification for the exact commit.** Step 0 shows every check run of the tag's commit that carries one of the four "U8 complete / ..." names, and the maintainer types the commit's short hash. Step 1 refuses when one of the names has no run, has a run that did not pass (a cancelled one included), or has a run from an app other than GitHub Actions (`u8-release-runbook.md:95-96`). U8's infrastructure design settled that a release reaches production in person (`../u8-service-operations-integration/infrastructure-design/infrastructure-design-questions.md:40, 80`).

## Branch protection

Only the maintainer can switch protection on, in the repository's settings (`ci-pipeline-questions.md:140`).

- **When.** For `develop`, after the first run on GitHub shows each required name reporting. For `main`, right after the first release has created it (`u8-release-runbook.md:50-51`; `ci-pipeline-questions.md:177`). **The fork has no `main` yet** (`u8-release-runbook.md:10-11`; `git branch -r` lists `origin/develop` and no `origin/main`), so protection on `main` can only follow the first release.
- **The exact list to enter**, each as GitHub reports it:
  1. REM-1 isolated rules and adapters
  2. shared (SSOT · drift · pytest)
  3. ingestion (U1)
  4. discovery (U2)
  5. summarization (U7)
  6. ops (U6 reliability/detection)
  7. backend app-shell (mounts U2/U3)
  8. accounts + library (root tests/ — U3 · U4)
  9. Security Scan (SCA + Secrets)
  10. REM-1 full closure audit (not diff-only)
  11. REM-1 isolated Postgres acceptance
  12. REM-1 platform suite on macOS (APFS semantics)
  13. Dependency review (PR-only · npm + pip)
  14. U8 complete / shared-contracts
  15. U8 complete / frontend
  16. U8 complete / backend
  17. U8 complete / browser
  18. next app (tsc · drift guards · tests · production build · audit)
- **Proposed settings (proposals, not decisions):** no required review, because the maintainer is the only maintainer and GitHub does not let an author approve their own pull request; administrators included, so the checks bind the maintainer too; branches up to date before a merge (`ci-pipeline-questions.md:46`).
- **Warnings about names, from the runbook** (`u8-release-runbook.md:52-55, 71-73`):
  - Require each check by the name GitHub reports for it. That name is the job's `name:`; a job without one reports its id.
  - Choose GitHub Actions as each check's source, never "any source" (GitHub Actions' `app_id` is 15368 when set through the API).
  - Only the complete verification reports the four "U8 complete / ..." names. The lanes of U2, U4 and U6 report bare `frontend`, `backend` and the like, which neither satisfy nor hold those checks.
- **If the Next app workflow is removed one day,** protection must change at the same time (`ci-pipeline-questions.md:142`).

## A red run

- **A failing run is reported as failing** and never described as passing (`CONVENTIONS.md:20-21`). Its result is kept in this stage's record even when a later run passes.
- **A refused set-up.** The set-ups of the U1, U2, U3 and U7 tools still wait for PostgreSQL in a way that can start too early (`aidlc/spaces/default/memory/project.md:40`); on GitHub only U2's and U3's lanes run such a set-up (`ci-config.md`, section 8, item 4). Build and Test met this five times in its last run (`../build-and-test/build-and-test-summary.md:713`). A refused set-up counts as this start-up race only when the stopped container's log shows the init server restarting (`project.md:40`). The refused environment is then kept as a failed prerequisite, and the job is run again on a fresh environment, never relabelled. The second run's result is then the lane's result, as it was for U1's and U7's lanes in Build and Test, and both runs are recorded here. That is the lead's reading of the project rule, open to the maintainer's correction at this stage's approval. A refused set-up whose log does not show that restart is an ordinary failure and holds the pull request (`ci-pipeline-questions.md:44`).
- **The racy U6 test, until its follow-up fix.** `frontend/test/u6-export/outcome-step.test.tsx` failed 1 of 1,248 tests in one of five runs of the full suite (`../build-and-test/test-results.md:78-79, 110`). Its 15 ms poll can remove the cancel button before the test clicks it (`../build-and-test/build-and-test-summary.md:698`). On GitHub it would run in three places once the workflows run: Next app's test step, U6's frontend job and U2's cumulative frontend job (`ci-pipeline-questions.md:99`; `frontend/vitest.u2-cumulative.config.ts:16`). If a run goes red on this test, and on nothing else, the run is recorded as failed, and a second run that passes lets the pull request merge. A run red on any other check holds the pull request (`ci-pipeline-questions.md:44`). Both results stay in this record. Follow-up: fix the timing race in `frontend/test/u6-export/outcome-step.test.tsx`, as a separate piece of work after this work merges into `develop` (Q3, `ci-pipeline-questions.md:102, 175`).
- **No floor or check is weakened** to make a run pass (`ci-pipeline-questions.md:34`; `aidlc/spaces/default/memory/project.md:105, 107`).

## Known risks

The two risks the maintainer let stand without a question (`ci-pipeline-questions.md:49-51`):

1. **Memory.** Memory ran close to the 1 GiB limit on this Mac: U5's and U6's browser lanes peaked at 92.95% and 92.10%, and U8's verification run at 92.78% (95.37% in the run before) (`../build-and-test/build-and-test-summary.md:720`; `ci-pipeline-questions.md:50`). No run on GitHub shows how its runners behave.
2. **Lanes missing on the release pull request.** The lanes of U2 to U6 do not run on a pull request from `develop` into `main` (see the end of "Known gaps").

## Known gaps

Test commands that no workflow runs on GitHub, as listed in Q1 (`ci-pipeline-questions.md:57-60, 173`). Each of those is owned by a follow-up piece of work (Q1 = A). A last row adds two U8 phases that Build and Test ran and no workflow runs either; the row says what the records give for their owner.

| Unit | What no workflow runs | The workflow's own words |
|---|---|---|
| U1 | The backend tests: the lane only collects them (`u1-paper-journey.yml:75-80`). The browser journeys run in no workflow. Build and Test ran U1's component, repository and integration phases (`../build-and-test/test-results.md:72`); it did not run these browser journeys either. | The file's header says the DB, browser and operations phases are "recorded as unexecuted required evidence in CI" (`u1-paper-journey.yml:3-8`). It prints no notice in the run. |
| U7 | The database, repository, integration and operations phases, and the coverage pass. Build and Test ran all of them (`../build-and-test/test-results.md:76`). | The run prints the notice "U7 phases not run in CI" (`u7-controlled-platform-protocols.yml:52-54`), and a second notice that no type checker is installed (`:55-57`). |
| U3 | The backend coverage pass. Build and Test ran it (`../build-and-test/test-results.md:74`); the tool has the phase (`scripts/verify_docsuri_u3.py:942-951`). | None. |
| U2 | The browser journeys. Build and Test did not run them either (`../build-and-test/test-results.md:73`). | The "Evidence boundary" step says browser journeys "remain separate evidence" (`u2-account-controls.yml:93-99`). |
| U8 (not in Q1) | The `performance` and `capacity-burst` phases of `scripts/verify_docsuri_u8.py`, which Build and Test ran on realm B (`../build-and-test/test-results.md:58-59`). The complete verification runs neither (`u8-complete-verification.yml:238-260`). The records place the performance phase's evidence with each installation (`../build-and-test/cross-unit-traceability.md:13`); no owner for running these phases in CI is recorded. | None. |

Lanes that do not run on a pull request from `develop` into `main`: U2, U3, U4, U5 and U6, each of which filters its pull-request trigger on `branches: [develop]` (`u2-account-controls.yml:5`, `u3-paper-corpus-capabilities.yml:5`, `u4-research-novelty.yml:5`, `u5-topics-digests.yml:5`, `u6-approved-export.yml:5`). U1's and U7's triggers have no branch filter, so they run there when their paths change (`u1-paper-journey.yml:10-12`, `u7-controlled-platform-protocols.yml:9-11`). The required checks above all run there.

## What Build and Test left to this stage

Build and Test left 15 targets unverified for this stage and marked 3 not applicable because this stage is where CI is set up to run them (`../build-and-test/build-and-test-summary.md:691`; `../build-and-test/test-results.md:178`). The row line for each is in `../build-and-test/build-and-test-summary.md`.

| Target IDs (summary line) | What is owed | What would show it | Result |
|---|---|---|---|
| U8:D11:rotation-link-and-pipe-safety (245), U8:D11:rotation-macos (246), U8:D11:rotation-schedule-expiry (248), U8:NFR9.8 (504), U8:NFR9.8:rotation-on-macos (508) | Log rotation's cases on real root-owned folders: links, pipe, hard link, no-loss move, copy-then-truncate, owners kept | `ci.yml`, `macos-filesystem`, the "U8 arrangement suite on macOS" step (`ci.yml:455-463`) | no run yet |
| U8:D6:visudo-check (282), U8:NFR1.6 (314), U8:NFR3.8 (356) | `visudo -c -f` on the sudo rules, and the `pfctl` parse of the packet-filter anchor, as root on macOS. For NFR1.6, sudo's cleaned environment is shown only at the installation, so a run here shows only part (`../build-and-test/build-and-test-summary.md:314`) | the same step | no run yet |
| U8:NFR3.11:locked-dependencies (326), U8:NFR3.11 (324) | The install from locked dependencies with lock hashes. For NFR3.11 the real runtime downloads happen only at the installation, so a run here shows only part | the same step | no run yet |
| U8:unit-test-instructions:commands-phase-arrangement (627), U8:unit-test-instructions:coverage-targets-macos-adapters (652) | The arrangement folder as root on macOS, and the macOS adapters' report at 80% | the same step, with `--cov-fail-under=80` (`ci.yml:462-463`) | no run yet |
| U8:tech-stack-decisions:verification-lane (618) | The complete verification running as a GitHub Actions lane | `u8-complete-verification.yml`, all four jobs | no run yet |
| U8:code-generation-plan:step-44-next-app (573) | Next app's checks passing on GitHub. Build and Test's row lists four of the five steps as run on this Mac; the production build is not among them, and the test step failed once in five runs on the racy U6 test | `next-app.yml`, `next-app` (`next-app.yml:53-68`) | no run yet |
| U8:code-generation-plan:completion-evidence-boundaries (558) | That no stage claims evidence only the installation or the maintainer's own steps can produce. A GitHub run can show only part of it | every required check, with the installation's evidence left to later stages | no run yet |
| Not applicable in Build and Test: U5:code-generation-plan:testing-contract-team-ci-before-merge (92), U6:code-generation-plan:testing-contract-ci (195), U8:code-generation-plan:testing-contract-ci-before-merge (574) | CI runs and passes on the pull request before merge, with the 80% floor enforced there | the pull request's run: U5's lane (`u5-topics-digests.yml`), U6's lane (`u6-approved-export.yml`) and the complete verification, beside the other required checks | no run yet |

## The check before Operation

The stage file asks for four confirmations (`.claude/aidlc-common/stages/construction/ci-pipeline.md:70-85`). What each will show:

1. **All Units built and tested.** U5, U6 and U8 are built. Build and Test ended as failed, and the maintainer approved it with "Accept failure", leaving its 12 failed and 33 unverified checks open (`ci-pipeline-questions.md:17, 154`; `../build-and-test/build-and-test-summary.md:689-690`). Owner: Build and Test, which was approved as failed. These 45 are not among the 112 targets that later stages own (`../build-and-test/build-and-test-summary.md:689-691`); they stay open into Operation by the maintainer's Q6 decision. The three that rest on the racy U6 test go to its follow-up fix; U8's scope floor, one of the three, also waits on U1's L1-80 failures and the maintainer's word (`../build-and-test/build-and-test-summary.md:698`).
2. **No unresolved findings in the Units' code-generation tables.** Not met. The three files read: [../u5-topics-digests/code-generation/traceability.json](../u5-topics-digests/code-generation/traceability.json), [../u6-approved-export/code-generation/traceability.json](../u6-approved-export/code-generation/traceability.json) and [../u8-service-operations-integration/code-generation/traceability.json](../u8-service-operations-integration/code-generation/traceability.json). U8's holds 28 rows marked `Deferred` and one marked `persons-decision`, the vector-storage size (`u8-service-operations-integration/code-generation/traceability.json:389`). U6's holds one row marked "open until U8's reopen" (`:45`) and one marked "jsdom side only; the browser side stays open" (`:106`). U5's records its browser-only checks as staying Unverified by the maintainer's choice (`u5-topics-digests/code-generation/traceability.json:453`); its older repair entry that marks the browser lane `OPEN` (`:389`) was followed by a later browser lane that passed (`:408`). The vector-storage size is 0.74 GB, inside the corrected bound the maintainer gave but above the approved design's "about 0.5 GB", waiting for the maintainer's decision (`ci-pipeline-questions.md:155`).
3. **The cross-Unit requirement gate passed.** Not met: 190 of 209 requirement IDs are covered. The other 19 are U8's; their code is built and tested, but their evidence comes from a run on GitHub (this stage), the installation, each installation's performance phase and the soak, the dry runs and the switch from v1 to v2, v1's restart rehearsal, or the first release; FR4.2 also names Build and Test (`../build-and-test/cross-unit-traceability.md:13`; `ci-pipeline-questions.md:156`).
4. **The CI gates enforce the build and test commands Build and Test recorded.** Not met. The commands under "Known gaps" run in no workflow, and nothing has run on GitHub yet (Q1, Q4).

Open items and their owners (`../build-and-test/build-and-test-summary.md:691`): this stage, 15 targets and 3 not applicable (above); Environment Provisioning 46; Performance Validation 26; Deployment Execution 19; Observability Setup 5; Deployment Pipeline 1; the known gaps and the racy test, a follow-up piece of work; the vector-storage size, the maintainer. Also open:

- U8's three Minor review findings R-19, R-20 and R-21, accepted at U8's approval with no owner named (`../build-and-test/build-and-test-summary.md:718`);
- J06's durable drafts, owed before the release (`../build-and-test/build-and-test-summary.md:717`);
- U8-S part 2 and U1's L1-80 failures, waiting for the maintainer's word (`../build-and-test/build-and-test-summary.md:719`);
- the CVE-2026-82049 and CVE-2026-85091 decisions behind the closure audit's warning, the maintainer (`ci-pipeline-questions.md:35`);
- the merge method, the maintainer, before the second release (`ci-pipeline-questions.md:45`);
- the unwritten note on the deployment rule, the maintainer (`ci-pipeline-questions.md:47`);
- Next app's test step without coverage against `project.md:105`, and the 48% floor on `src/App.tsx` against `project.md:107`, the maintainer (see "Coverage floors").

The verdict is to be recorded in `aidlc/spaces/default/intents/261016-finish-v2-rebuild/verification/phase-check-construction.md` as **failed**, with each open item and its owner, and brought to this stage's approval (Q6 = A). That departs from the stage file's instruction to stop, and it is the maintainer's decision. This document does not write that file. The file does not exist yet (the `verification` folder holds only the ideation and inception checks); it must exist before this stage's approval, and until then step 5 is not done (`.claude/aidlc-common/stages/construction/ci-pipeline.md:81-82`).
