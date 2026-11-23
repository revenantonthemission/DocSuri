# CI Pipeline Questions

Date: 2026-11-23
Stage: CI Pipeline, for the whole piece of work: U5 (topics and digests), U6 (the approved Notion export) and U8 (service operations and integration). Inputs:

- Build and Test's records: the [summary](../build-and-test/build-and-test-summary.md), the [test results](../build-and-test/test-results.md) and the [cross-unit traceability](../build-and-test/cross-unit-traceability.md);
- each Unit's code summary: [U5](../u5-topics-digests/code-generation/code-summary.md), [U6](../u6-approved-export/code-generation/code-summary.md) and [U8](../u8-service-operations-integration/code-generation/code-summary.md);
- U8's [infrastructure design questions](../u8-service-operations-integration/infrastructure-design/infrastructure-design-questions.md) and [release runbook](../u8-service-operations-integration/code-generation/u8-release-runbook.md);
- the repository today: the 13 files in `.github/workflows/`, `CONVENTIONS.md` and the project rules.

CI for this work already exists, so this stage does not design a pipeline from nothing. It records what the workflows enforce, sets the gates, and closes the gaps you choose to close. The stage's usual questions (which CI tool, which branch strategy, which artifact store) are already answered in the records. They are listed first, with no question, followed by the assumptions I will work on unless you correct them. The six questions after that are the decisions that are still yours. Where I have a recommendation it is option A; Q6 states its own. Answer with a letter, or in your own words under X.

Five terms are used throughout:

- **Lane.** A Unit's own workflow file and the test phases it runs, such as database, component, coverage and browser.
- **The complete verification.** `u8-complete-verification.yml`, U8's workflow that checks the whole application: its shared contracts, frontend, backend and browser journeys. It reports four checks named "U8 complete / ...".
- **Accept failure.** Your choice at Build and Test's approval: the stage was approved as failed, with its 12 failed and 33 unverified checks left open and no Unit reopened.
- **Reopening a Unit.** This work runs under the strict guard policy you set, with the review-freeze check switched off by you. I expect an edit to a Unit's approved files to send that Unit back for review, verification and approval. Build and Test has run six times so far: after each of the four times it sent work back to a Unit (a loop-back), it was run again. I expect the same here, and I will confirm the exact effect before I touch any approved file. Every option below that reopens a Unit therefore amounts to a fifth loop-back. Build and Test's rules bound loop-backs at three; the fourth went past that bound on your word, and a fifth would go past it again. If several of your answers reopen Units, I expect to reopen them in one round, one Unit at a time, as one loop-back, with Build and Test run once after all of them, not once per answer.
- **Operation.** The phase after this one, which deploys and runs the service.

## Settled from the records (no question)

If one of these should change, say so under X of the closest question.

- **CI tool.** GitHub Actions on GitHub's own runners: Linux for the suites, and the macOS runner for the tests that need macOS and root. You confirmed this in U8's infrastructure design.
- **Branches.** `CONVENTIONS.md`: a working branch merges into `develop` through a pull request, and `develop` is promoted to `main` for a release. `branch-name-check.yml` checks the branch names. The fork has no `main` yet: the first v2 release creates it from `develop`'s release commit, and protection on `main` can only follow that.
- **What exists.** 13 workflow files. Once this branch is pushed, these run on every pull request into `develop`:
  - `ci.yml`: eight suite jobs, the dependency review, the security scan (pip-audit and gitleaks), the full closure audit (pip-audit over every project in the repository, not only the changed ones), the isolated Postgres job and the macOS job;
  - `codeql.yml`, `next-app.yml`, the complete verification and `branch-name-check.yml`.

  The per-Unit lanes (U1 to U7) run only when their paths change. `release.yml` runs only on a push to `main`.
- **None of it has run on GitHub for this work.** The branch `feature/u8-service-operations-integration` has no commit of its own. It stands at pull request #54's merge, four commits behind GitHub's `develop`. 1,588 changed or new paths are uncommitted, 209 of them AI-DLC framework files under `.aidlc/`. They include the complete verification's new workflow file and changes to `ci.yml`, `release.yml`, `u2-account-controls.yml` and `u6-approved-export.yml`.
- **Required before a merge.** You confirmed that `develop` and `main` require the CI jobs and the complete verification to pass. Which check names that means exactly is Q5.
- **Floors.** 80% line coverage for new code, enforced wherever a lane measures it: the frontend lanes of U2 to U6 and U8, the backend coverage phases of U2, U4, U5, U6 and U8, and the macOS job's report on U8. The lanes of U1 and U7, and U3's backend, enforce no floor in CI (Q1). No floor or check is weakened to make a run pass.
- **Security scans.** The dependency review on every pull request, pip-audit in CI's security job (your decision of 2026-11-15 to leave it to CI), a blocking gitleaks scan, and CodeQL. One check only warns today: a finding in four named projects makes the full closure audit print a warning instead of failing, until you decide what to do about two known vulnerabilities (CVE-2026-82049 and CVE-2026-85091). The gates document will record it as a warning, not as a gate.
- **No production secret enters CI.** CI runs on throwaway test databases with made-up data and fake providers. `GITHUB_TOKEN` writes only the tag, the GitHub Release with its attached archive, and CodeQL's results.
- **Artifacts and releases.** No container or package registry. A merge into `main` cuts an annotated `v` tag and a GitHub Release that holds `docsuri-workspace.tar.gz` and its SHA-256. You install a release on this Mac in person, as you answered in U8's infrastructure design (its Q1, option A). Nothing deploys by itself.
- **Which files reopen a Unit when changed.** U5 claims its own lane's workflow file and U6 its own. U8 claims `ci.yml`, `release.yml`, `u2-account-controls.yml`, `next-app.yml` and the complete verification's file, and also the set-up tools of the earlier Units' lanes (`scripts/verify_docsuri_u1.py` to `u7`). The other six workflow files belong to no Unit of this work.

## My assumptions (correct them under X)

These are my readings, not decisions on record.

- **When the interim merge rule ends.** `CONVENTIONS.md` lets completed work merge into `develop` despite known, pre-existing legacy CI failures, "until that work establishes the replacement checks". This stage is that work. I read the rule as ending when this stage is approved: from then on a pull request into `develop` merges only when its checks pass, which is also the project rule ("never merge without CI passing"). A check that fails on this work's own first run is not a legacy failure, so it holds this pull request too.
- **Merge method.** `CONVENTIONS.md` names none. The team rules say branches are squash-merged, but that text was written for the direct-to-`main` flow that `CONVENTIONS.md` replaced, and pull requests #53 to #56 were merged with merge commits. I will describe the gates for merge commits and change no repository setting. The method decides what `release.yml` reads when it works out a version, so it should be settled before the second release; the first is fixed at v2.0.0.
- **Other protection settings.** When you switch protection on, I will propose: no required review (you are the only maintainer, and GitHub does not let an author approve their own pull request), administrators included (so the checks bind you too), and branches up to date before a merge.
- **The deployment rule.** The project rules still say every commit that passes CI deploys to production by itself. Your in-person answer reads that rule as not covering this Mac's production. The note that was to record that reading in the rules was never written. I follow your answer; say under X if you want the note written now.
- **Workflow files.** I plan to change no workflow file that a Unit claims, unless one of your answers calls for it.
- **Two risks I will record in the gates document, without a question.**
  - Memory ran close to the 1 GiB limit on this Mac: U5's and U6's browser lanes peaked at 92.95% and 92.10% in Build and Test's last run, and U8's verification at 92.78% (95.37% in the run before).
  - The lanes of U2 to U6 do not run on a pull request from `develop` into `main`. U1's and U7's have no branch filter and run there when their paths change.

## Q1. [Release engineer] The earlier Units' test commands that no workflow runs

U8's infrastructure design settled that the per-Unit lanes "stay as they are". This stage's last check asks something that decision did not cover: whether CI enforces every test command Build and Test recorded. For some commands of the earlier Units it does not.

- U1 (the paper journey): its lane only collects the backend tests and does not run them, and its browser journeys run in no workflow.
- U7 (platform protocols): its lane runs the component tests only, and prints a notice that the database, repository, integration and operations phases did not run.
- U3 (the paper corpus): its lane does not run the backend coverage pass.
- U2 (account controls): its browser journeys run in no workflow.

What a change would touch:

- The workflow files of U1, U3 and U7 belong to no Unit of this work, so changing them reopens nothing.
- U2's workflow file and the lanes' set-up tools are claimed by U8, so changing those reopens U8.
- The set-up tools wait for PostgreSQL in the way that started too early five times in Build and Test's last run. Running more database phases in CI brings that race there.
- U1's repository and integration phases also need its pinned model runtime and two papers fetched from arxiv.org. Without them those phases ran in Build and Test and ended in the failures you accepted earlier. The run with the papers and the runtime never happened, and whether to allow it is a decision you left open.

A. Keep the lanes as decided. The gates document lists each recorded command that no workflow runs, with its lane's own notice, as a known gap for a follow-up piece of work. These lanes keep running with no coverage floor in CI. The check before Operation (Q6) then records "CI enforces every recorded test command" as not met.
B. Add the missing phases to the workflow files of U3 and U7 only. Nothing reopens, and CI fetches nothing beyond the pinned PostgreSQL image that other lanes already pull. U7's coverage pass refuses a changed module below 80%; U3's reports coverage but holds no floor. Pull-request runs get longer, and the start-up race can refuse a set-up; the job is then kept as failed and run again. U1's and U2's gaps stay listed.
C. Add everything: B, plus U1's phases, U2's browser job, and set-ups that wait until PostgreSQL accepts a network connection. CI then downloads U1's model runtime and two papers from arxiv.org on each run, and those phases have never passed in this work. U8 is reopened, and Build and Test is likely run again.

X. Other (please specify)

[Answer]: A

## Q2. [Maintainer] The fixed home-folder path in U8's design, code and plan

Earlier you chose "Summary now, plan later" for this Mac's home path in U8's records. The code summary's lines were rewritten with `~`, and the plan's were to follow after U8's approval and before any commit. What is left in U8's plan is of a different kind, so I am asking before I touch it.

- Four plan lines hold the real home path. Three quote the fixed Time Machine exclusion path for OrbStack's data folder, and one passes the bare home folder to a test that must refuse it.
- That path is not a leftover. U8's approved security requirement and security design set it as a fixed absolute path. U8's isolation check, which is written but not yet committed, holds it as a literal, and three test files assert it. Rewriting only the plan's lines with `~` would make the plan disagree with the code it describes.
- Nothing new would become public. The account name in the path is the same as the repository owner's public GitHub name. 22 files already committed on `develop` hold the same home path: 21 from earlier pieces of work and one in this work's own event log. Removing those would mean rewriting public history, which this stage does not touch.
- Options B and C edit U8's approved files, so they reopen U8.

A. Leave all of it as designed. It is the installation's fixed path on this Mac, and nothing reopens. "Plan later" is closed as not needed for these lines.
B. Rewrite only the plan's four lines with `~`, as first decided. The plan then no longer quotes the code's literal. U8 is reviewed, verified and approved again before any push, and Build and Test is likely run again.
C. Remove the literal everywhere. The installer takes the operator's home folder at installation, and the security requirement, the security design, the isolation check, the three test files and the plan change with it. U8 reopens from its design on, and Build and Test is run again before any push.

X. Other (please specify)

[Answer]: A

## Q3. [Maintainer] The racy test in the approved-export Unit

One frontend test of U6, in `frontend/test/u6-export/outcome-step.test.tsx`, has a timing race: its 15 ms poll can remove the cancel button before the test clicks it. "Accept failure" left this fix open. I ask about it again only because of what the race does on GitHub.

- In Build and Test the full frontend suite failed 1 of 1,248 tests in one of its five runs because of it, and three of Build and Test's checks are recorded as failed on it.
- On GitHub the test runs in three places: the Next app workflow's full test step, U6's own frontend job, and U2's cumulative frontend job. Any of them can go red now and then through no fault of the change under test.
- The test is already on `develop`, unchanged: U6 was merged with pull request #54.

A. Fix it in a follow-up piece of work, after this work has merged into `develop`. Until then a run that goes red on this test is recorded as failed. On GitHub a second run that passes lets the pull request merge, but the gates document keeps both results and names the follow-up.
B. Fix it before the first push. U6 is reopened for this one test, the test is made deterministic, and U6 is reviewed, verified and approved again. Build and Test is then likely run again. The three failed checks can then pass.
C. Fix it now on its own `fix/` branch from `develop`, apart from this work. This branch would later take the changed file from `develop`, and I do not yet know what that does to U6's approval in this piece of work. I would check that first and come back to you before doing it.

X. Other (please specify)

[Answer]: A

## Q4. [Maintainer] When the first run on GitHub happens

None of the workflows has run on GitHub for this work, because nothing is committed or pushed. Build and Test left 15 checks unverified for this stage.

- Eleven are the macOS job's root tests: log rotation on root-owned folders, the check of the sudo rules, the packet-filter rules, the install from locked dependencies and the macOS coverage report.
- Two are the complete verification running on GitHub and the Next app checks.
- The last two of the 15 are the pinned runtimes, whose real downloads happen at the installation, and the rule that Build and Test claims no evidence that only the installation or your own steps can produce. A run on GitHub can show only part of each.

Three more checks, "CI passes on the pull request before merge" for U5, U6 and U8, were marked not applicable in Build and Test because this stage is where CI is set up to run them. Only a pull request's run can show them.

- A commit, a push and a pull request are yours to ask for. I will not make them on my own.
- Before any commit I will show you the exact list of files. The working tree also holds the 209 framework paths and five dependency files that were staged earlier and already equal `develop`'s. U8's records name three files that must not be committed; none of them is in the working tree today.
- GitHub's `develop` would first be merged into this branch. U8's records leave that merge to your word. Its four commits are the dependency upgrades of pull requests #55 and #56. The working tree already carries those versions, and Build and Test ran on them, so the merge changes no file's content.
- What goes into the commit depends on Q1, Q2 and Q3. If one of your answers there reopens a Unit, "now" below means after that Unit is approved again.

A. Now, as a draft pull request into `develop`: merge `develop` into the branch, commit, push, and open the pull request as a draft. Every pull-request workflow runs, nothing can be merged by accident, and this stage records each check's real result before you approve it.
B. After this stage is approved. The stage is approved on its documents alone. The 15 checks stay unverified, the check before Operation (Q6) records the CI gates as written but never run, and branch protection (Q5) waits for the run. The first run's results are recorded in the next stage, Deployment Pipeline. That is Operation's first stage, so this option needs option A of Q6.
C. You push yourself, when you choose. I prepare the file list and the pull request text only. This stage is approved with no run recorded, as in B, and the run's results are recorded in Deployment Pipeline, so this option also needs option A of Q6.

X. Other (please specify)

[Answer]: A

## Q5. [Maintainer] Which checks branch protection requires

You confirmed that `develop` and `main` require "the CI jobs and the complete verification" before a merge. U8's release runbook turns that into 17 check names: 12 jobs of `ci.yml`, the dependency review on pull requests, and the four "U8 complete" checks.

- Three more workflows report on every pull request and are not in that list: Next app (types, the full frontend test suite of 1,248 tests, the production build and the dependency audit), CodeQL (code scanning) and the branch-name check.
- The full frontend suite runs only in Next app. The complete verification runs U8's own frontend tests, not that suite.
- The project rules say nothing merges without lint, type checks, tests and browser tests passing. Options A and C put that rule into GitHub for the frontend suite; option B leaves it to your own check before a merge.
- Only you can switch protection on, in the repository's settings, and only after a first run shows each name reporting.

A. The runbook's 17 names plus the Next app job, which reports as "next app (tsc · drift guards · tests · production build · audit)". The full frontend suite and the production build then hold a merge. The racy test of Q3 can hold a merge until a run of it passes. If the Next app workflow is removed one day, protection must change at the same time.
B. Exactly the runbook's 17 names. The full frontend suite still runs on every pull request, but a red run of it does not hold a merge in GitHub.
C. Everything that reports on every pull request: A, plus CodeQL's analyses and the branch-name check. The branch-name job first needs a name of its own, because it reports the bare name "check" today. Its workflow file belongs to no Unit, so that change reopens nothing.

X. Other (please specify)

[Answer]: A

## Q6. [Maintainer] How the check before Operation is recorded

This stage ends with a check before Operation begins. The stage's instructions say to confirm four things, and to stop and go back to the owning stage "if any traceability file is missing or any unresolved finding remains". No file is missing. Here is what the four will show:

- **All Units built and tested.** U5, U6 and U8 are built. Build and Test ended as failed, and you approved it with "Accept failure".
- **No open rows in the Units' own requirement tables.** U6's and U8's tables hold rows marked open or deferred. One of them is the vector-storage size: 0.74 GB, inside the corrected bound you gave earlier (774,404,601 bytes) but above the approved design's "about 0.5 GB". It waits for your decision: write your correction into the design, shrink the index, or accept the miss.
- **The requirement check across Units passed.** It did not: 190 of 209 requirement IDs are covered. The other 19 are U8's. Their code is built and tested, but U8 marks them deferred because their evidence comes from a run on GitHub (which this stage can produce), the installation, each installation's performance phase and the soak, the dry runs and the switch from v1 to v2, v1's restart rehearsal, or the first release.
- **CI enforces the recorded test commands.** Not for the commands of Q1, and nothing has run on GitHub yet (Q4).

So the check cannot fully pass in this stage: some items belong to later stages. You approved Build and Test with the 19 IDs and the failed checks open.

My recommendation here depends on Q4: B if the first run happens in this stage (Q4 A), and A if it does not.

A. Record the check as failed, listing every open item with the stage that owns it, and bring it to this stage's approval. This departs from the stage's instruction to stop, and the record says so as your decision. Your approval then opens Operation with those items open, and each later stage must close its own. If you chose A in Q4, Operation opens even when that run on GitHub fails; the failures are listed with the rest.
B. The same record, but Operation opens only once the macOS job and the complete verification have passed on a pull request on GitHub. A red run holds Operation until it is fixed, and a fix in a workflow file that U8 claims reopens U8. This needs option A of Q4.
C. Stop, as the stage instructs. Operation does not open, and the work goes back to U6, U8 and Build and Test for the items a rebuild can close. This reopens U6 and U8 as described at the top. The items that later stages own cannot close this way, and with option B or C of Q4 the first run on GitHub would have no stage that records it.

X. Other (please specify)

[Answer]: A

## Consolidated Summary Confirmation

- **Q1 — the earlier Units' lanes stay as they are.** The gates document lists each recorded test command that no workflow runs as a known gap for a follow-up piece of work: U1's backend tests and browser journeys, U7's database, repository, integration and operations phases, U3's backend coverage pass, and U2's browser journeys. Those lanes keep no coverage floor in CI, and the check before Operation records "CI enforces every recorded test command" as not met.
- **Q2 — the fixed home-folder path stays as designed** in U8's security requirement, security design, isolation check, tests and plan. Nothing reopens, and "plan later" is closed for these lines.
- **Q3 — the racy U6 test is fixed in a follow-up piece of work,** after this work has merged into `develop`. Until then a red run on it is recorded as failed. A second run that passes lets the pull request merge on GitHub, and the gates document keeps both results and names the follow-up.
- **Q4 — the first run on GitHub happens now, as a draft pull request into `develop`.** `develop` is merged into the branch first. I show you the exact file list and wait for your word before the commit, the push and the pull request. This stage records each check's real result before you approve it.
- **Q5 — branch protection requires the runbook's 17 check names plus the Next app job.** You switch it on, after the first run shows each name reporting.
- **Q6 — the check before Operation is recorded as failed and brought to this stage's approval,** listing every open item with the stage that owns it. This departs from the stage's instruction to stop, and the record says so as your decision. Your approval opens Operation with those items open, even if the first run on GitHub fails; its failures are listed with the rest.
- **Settled from the records and my assumptions, unchanged:**
  - GitHub Actions on GitHub's runners; working branches into `develop` by pull request, and `develop` promoted to `main` for a release;
  - 80% line coverage for new code where a lane measures it, with no floor or check weakened;
  - the dependency review, pip-audit in CI, gitleaks and CodeQL, with the full closure audit recorded as a warning for four projects;
  - no production secret in CI, no registry, a tag and a GitHub Release on a merge into `main`, and releases installed in person;
  - the interim merge rule ends when this stage is approved;
  - the gates are described for merge commits, and no repository setting is changed;
  - the protection settings I will propose: no required review, administrators included, branches up to date;
  - no workflow file that a Unit claims is changed.

Does this all look correct before I generate the artifact?

- Looks correct
- Request changes

[Answer]: Looks correct
