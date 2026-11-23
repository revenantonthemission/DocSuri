# U8 release runbook: the first release, branch protection, install and rollback

Run at the Operation stages, with your decisions (cicd-pipeline § 3.1, § 4–§ 6). The
authoritative repository is the fork, `revenantonthemission/DocSuri` (`origin`). Nothing
in CI deploys: a release reaches this Mac only through `docsuri-release install`, in
person.

## 1. The first v2 release (`main`'s one-off push)

`main` does not exist yet, and a pull request cannot target a branch that does not
exist, so the first release creates it with one push.

1. Choose `develop`'s release commit: one whose complete verification
   (`U8 complete verification`: `U8 complete / shared-contracts`,
   `U8 complete / frontend`, `U8 complete / backend` and `U8 complete / browser`)
   and `ci.yml`'s jobs passed. Pushing it as `main` runs the lane on it a second time.
   The install reads every run of each name, and each must have passed, so wait for the
   second run before installing. A run that the lane's own concurrency cancelled counts
   as not passed: a later push to the same branch, or a manual run on it, cancels a run
   still in progress. Re-run that workflow run on GitHub, and install once step 0 shows
   no run of the four names that did not pass.
2. Push it as `main`, once:

   ```bash
   git push origin <commit>:refs/heads/main
   ```

3. That push runs `release.yml`:
   - its first step lists `origin`'s tags; with no `v2.*` tag there it passes
     `custom_tag: 2.0.0` to the tagging step, so the tag is `v2.0.0` whatever the
     computed bump and whatever tags the history holds;
   - the tag is annotated (`create_annotated_tag: true`);
   - **the guard** (`scripts/u8_release_guard.py`) fails the job when no `v2.*` tag
     existed before the run and the created tag is not `v2.0.0`, before the GitHub
     Release is published, so a wrong first version is never published;
   - a `contents: read` job builds the workspace from the tagged commit with its
     lockfile (`scripts/u8_build_workspace.py`: precompressed, first-load budget
     checked) and hands it on as an artifact;
   - a narrow `contents: write` job attaches `docsuri-workspace.tar.gz` and
     `docsuri-workspace.tar.gz.sha256` to the GitHub Release.
4. Check the Release page: tag `v2.0.0`, annotated, with both files attached. If the
   guard failed, nothing was published: delete the wrong tag on `origin`, fix the cause
   and push again.

Every later release is a pull request from `develop` into `main`; the tagger computes it
from the newest tag reachable on `main`, starting at `v2.0.0`.

## 2. Branch protection's required checks

Switch protection on for `develop` once the complete verification lane exists there,
and for `main` right after the first release has created it. It is free for a public
repository. Require exactly the checks that always report, each by the name GitHub
reports for it. That name is its job's `name:` (a job without one reports its id).
Choose GitHub Actions as each check's source, never any source (GitHub Actions'
`app_id`, 15368, when set through the API).

- `ci.yml`, each job by the name it reports, with its id in brackets:
  `REM-1 isolated rules and adapters` (`platform-integrity`),
  `shared (SSOT · drift · pytest)` (`shared`), `ingestion (U1)` (`ingestion`),
  `discovery (U2)` (`discovery`), `summarization (U7)` (`summarization`),
  `ops (U6 reliability/detection)` (`ops`), `backend app-shell (mounts U2/U3)`
  (`backend`), `accounts + library (root tests/ — U3 · U4)` (`root-suites`),
  `Security Scan (SCA + Secrets)` (`security`),
  `REM-1 full closure audit (not diff-only)` (`rem1-closure-audit`),
  `REM-1 isolated Postgres acceptance` (`rem1-isolated`) and
  `REM-1 platform suite on macOS (APFS semantics)` (`macos-filesystem`);
- `Dependency review (PR-only · npm + pip)` (`dependency-review`), on pull requests;
- the complete verification: `U8 complete / shared-contracts`,
  `U8 complete / frontend`, `U8 complete / backend` and `U8 complete / browser`.

No other workflow reports these four names. U2's, U4's and U6's lanes report bare
`frontend`, `backend` and the like, which protection does not require, so they neither
satisfy nor hold the complete verification (review finding R-13).

Do not require the per-unit lanes (U1–U7): they run only when their paths change, so a
required one could hold a pull request forever.

## 3. Install a release

In person, on this Mac:

```bash
echo '{"tag": "v2.0.0"}' | sudo -k /Library/DocSuri/release/ops/bin/docsuri-release install
```

The tag comes on standard input; the short hash of step 0 is typed on the terminal
(`/dev/tty`), where the command also shows what you confirm, so standard output carries
only its one JSON result. Run it from a terminal: without one, step 0 is refused
(`confirmation-unavailable`) and nothing changes. It refuses to run when the environment
holds `PYTHON*`, `DYLD_*` or `LD_*` variables, and while another `docsuri-release`
command runs (`release-run-active`). What it does (cicd-pipeline § 5.1):

| Step | What happens | Stops when |
|---|---|---|
| 0. Show and confirm | The tag, its commit, every check run of the commit that carries one of the four names `U8 complete / …`, each with its app, status, conclusion and id, the commits since the installed release, the migrations, and any arrangement change with the installer's plan. You type the commit's short hash on the terminal to go on. | you stop or type another hash; nothing has changed |
| 1. Preflight | GitHub's public check runs for the commit: refused `check-runs-incomplete` when GitHub lists more check runs than one page holds, `complete-verification-ambiguous` when a run of one of the four names comes from an app other than GitHub Actions, and `complete-verification-not-passed`, naming the checks, when one of the names has no run or has a run that did not pass, a cancelled one included; each such run's name and id recorded as the commit's VerificationRun; the tag annotated and on `main`; not the release that runs now (`tag-installed`: use `verify` or `rollback` for it); no production restore, switch, abort or rollback active; isolation passed within 15 minutes; disk room; and the performance phase's room (6 GiB available, fewer than 60 requests a minute over 15 minutes). | any check fails; nothing has changed |
| 2. Stage | The tag cloned into `/Library/DocSuri/releases/<tag>/`, its CPython and `uv sync --frozen --no-build`, the workspace build checked against its SHA-256, `otool -L`, the arrangement version. The folder `release-previous` points to (the kept release after a rollback) is reused as it stands when its identity names this tag and commit: no clone, no move (your decision of 2026-10-26, "Reuse the kept folder"); its build manifest, libraries and arrangement version are checked again. No folder a link points to is ever moved or deleted; a leftover folder of the tag's name that no link points to (a staging that was killed) is removed and the tag cloned afresh. | a digest or check fails, the new folder is deleted; the kept folder's identity names another tag or commit (`kept-release-differs`) or cannot be read (`kept-release-unreadable`), nothing changes |
| 3. Performance phase | The composed realm from `releases/<tag>/`: 20 users paced like people (about 4 requests a second), every target, no refusal, the host ready throughout. **v1's peak rate** comes from the consumer inventory taken from your Cloudflare export (the migration runbook, Workflow 11); the phase fails if v1's rate is higher than the test's, or if no such inventory exists. | a target is breached; production is unchanged |
| 4. Maintenance | Live mode only: the public address to the maintenance server. | the route fails; it routes back |
| 5. Stop | v2's host, workers and scheduler, through service control. | a stop fails; each role it stopped starts again and it routes back |
| 6. Backup | The backup agent's in-person backup and a ledger copy, after writes stop; integrity must pass. | the backup fails; the roles it stopped start again and it routes back |
| 7. Arrangement | Only when the release changes it: its own installer, under the in-progress marker. | an apply fails; the links never moved, so the current release starts again on the arrangement as the installer left it, and it routes back; repair the apply and install again (there is nothing to roll back) |
| 8. Migrate | Each owner's new migrations through the production environment tool, each in its own transaction. | a migration fails; the current release starts again |
| 9. Swap | `release-previous` to the current release, `release` to `releases/<tag>/`, each link replaced atomically. | — |
| 10. Start | v2 started, readiness within 10 minutes, then the signed-out probe journey. | a start fails, readiness or the probe fails, or anything else fails; it switches back (§ 5) |
| 11. Route back | Live mode only. | it tries once more; if that fails too the release stays installed and running behind the notice, and `recover` (§ 6) routes the address |
| 12. Record | The installed tag and commit as readiness evidence, and the release's ledger record; the marker removed; every folder neither link points to deleted. | — |

Before the switch the public address serves v1, so steps 4 and 11 are skipped and the
rehearsal v2 restarts; a new tag restarts the soak.

Step 6 asks for your password twice more (your decision of 2026-10-26, "Through your
login"). The release command runs as root, and the backup agent refuses root for every
word but its first configuration, so the backup after writes stop and its ledger copy
reach the agent through your login account's own in-person grant: `sudo -u <you>
/usr/bin/sudo -k -u _docsuri_r1t_backup docsuri-backup-agent backup`, then the same with
`ledger-copy`. Each `sudo -k` asks for your login's password on the terminal: one prompt
for the backup, one for the ledger copy (the ledger component's own copy, read before
it, runs from root and asks for none). The agent's caller rule is unchanged. A prompt left
unanswered, or a wrong password, fails the backup, and step 6's way out runs.

After a cutover rollback, with no dry run accepted since (the cutover runbook), an install
switches the release but leaves v2 stopped, and records it as not yet probed: its
readiness wait, probe journey and automatic switch-back run when the soak later starts
v2 (your decisions of 2026-10-25, "Keep v2 stopped" and "Probe it when the soak starts").
The cutover records the release's verification only once that probe passed: the install
itself records none and answers `release-not-probed` for the cutover. Meanwhile
`cutover check` answers `release-not-probed` and starts nothing: the soak then starts
only through `docsuri-release verify` with that tag (§ 4), once a dry run is accepted.
When that `verify`'s start fails, or v2 is not ready within its 10 minutes, it runs no
probe and switches nothing back: the roles that started keep running on the unprobed
release (v2 is running, not stopped), its record still waits for its probe, and
`cutover check` still answers `release-not-probed`. Run the same `verify` again once the
cause is fixed; to have v2 stopped meanwhile, use `service stop` in person.

While the cutover is rolled-back (an accepted dry run or not, until the soak starts),
every way out of an install leaves v2 stopped, as a release rollback does: a backup or
migration failure before the swap starts nothing again, and a failed start or probe
after it switches back and leaves v2's roles stopped. Outside that state, a way out
before the swap starts again only the roles the stop found running (the fixed program's
`wasLoaded`), so a role you stopped in person before the install stays stopped.

If that probe fails (your decision of 2026-10-26, "Leave v2 stopped"):

- `release` points back at the release `release-previous` names, and v2's three roles
  are left stopped. Each was stopped through the service control, so each stop record
  cites a receipt PlatformControl holds and the isolation check counts it as planned.
- The failed release's record ends `switched-back`, no longer waiting for a probe. If
  the links could not point back (no kept release, a relink that failed), the record
  stays `installed` and waiting for its probe, with `switch-back-failed`, so no soak can
  start on it; `recover` (§ 6) points the links back and ends it `switched-back`. When
  there is no kept release to point back to (after a switch back both links name the
  kept release until the next install, so a kept release that then fails its own probe
  has nothing to switch back to: `step: no-kept-release`), `recover` moves no link
  and answers the one way out, a new tag (§ 6).
- The cutover stays `rolled-back` and names the tag the links now point to, with no
  verification on it, so no soak starts. Should that naming fail, the cutover keeps the
  failed release's tag, still with no verification; and the soak and the switch refuse
  any tag the links do not point to (`release-not-linked`).
- What to run next: `docsuri-release verify` with the linked tag (§ 4). It starts v2 on
  that release, waits for readiness and starts the soak. Until then, renew v2's stop
  records in person with `service stop` before their 14 days pass (the cutover runbook).
  If the switch back answered `switch-back-failed`, run `recover` (§ 6) first.
- **When the kept release is closed** (your decision of 2026-10-26, "Stay put, v2
  stopped"): `release-previous` names a release whose record is `rolled-back` (the
  release you rolled back from, after `docsuri-release rollback`), `failed` or
  `switched-back`. The switch back never points `release` at it. The links stay on the
  release that failed its probe, v2's three roles are stopped (each stop through the
  service control, its record citing a held receipt), the failed release's record stays
  `installed`, still waiting for its probe, with `recover-required`, and the answer is
  `recover-required` with `step: kept-release-closed` and the kept release named. When
  a stop failed, a role still runs the failed release: the answer then says
  `v2: running` with the stop's own reason as `step` (`service.control-failed`; the
  record keeps it as `switchBackStep`), and `recover` is what stops it. No soak starts, and `cutover check`
  starts nothing. `recover` (§ 6) stops v2's three roles (a stop of a role already
  stopped is done), moves no link and answers the one way out, a new tag (your decision
  of 2026-10-27, "Drop that remedy"): fix the release, then `docsuri-release install`
  with the new tag. v2 stays stopped until that install; the install settles the waiting
  record (its probe superseded, its reason cleared) and runs v2 on the new release (while
  the cutover is rolled-back with no dry run accepted since, v2 stays stopped and the new
  release waits for its probe, § 3). There is no rollback to an earlier release:
  `rollback` is refused while the kept release is closed (`kept-release-failed`), after
  every completed install only the two linked folders remain under `releases/`, and the
  links are the release command's, never edited by hand.

Every way out ends the install's record, so the live exclusion is never left held: before
the swap (steps 4–8) each role the install stopped starts again and the address routes
back, and the record ends `failed`; after the swap (steps 10–11) § 5's switch back runs.
Ctrl-C, a closed terminal or SSH session (SIGHUP) and SIGTERM end the record too, as an
interruption (`release-interrupted`); `recover` (§ 6) then puts the links and v2 in a
known state. A run killed outright (no handler ran) is the one case that leaves its
record `installing`, holding the exclusion until `recover` ends it (§ 6), whichever state
the kept release is in. An interruption before the record began (step 0's prompt, the preflight,
staging or the performance phase) answers `release-interrupted` with `changed: false`
and offers nothing: nothing of production changed. An effect a run left in flight is
settled by the next run first, by its receipt, never by running it again; the backup
after writes stop is settled this way too, from the bound operation the journal kept
before the set was taken. That settling happens before the next command begins its
record, so while an effect is still within its lease the next command (`recover`
included) is refused (`effect-in-progress`), runs nothing beside it and changes no
record; wait for the lease to pass and run it again: it is then reconciled from its
target, and an effect that never ran runs nothing. Once an install completes, the
reasons earlier records kept for `recover` are cleared: v2 and the links are then known
to be the new release's.

## 4. Verify the installed release

`verify` runs steps 0, 1 and 3 again for the release that runs now, records the same
VerificationRun evidence and moves the cutover as step 12 does. After a cutover rollback
it is what starts v2 for the soak and runs the probe journey of a release installed while
v2 was kept stopped (the cutover runbook). The tag comes on standard input, as for
`install`, and the short hash on the terminal:

```bash
echo '{"tag": "v2.0.0"}' | sudo -k /Library/DocSuri/release/ops/bin/docsuri-release verify
```

It is refused for any tag but the one `release` points to (`verify-installed-tag-only`).

`verify` starts v2's three roles only (your decision of 2026-10-26, "Only for a pending
probe"): to probe the linked release while it is still waiting for its probe; to start
the soak on the linked release after a failed probe's switch back left v2 stopped on it
(the switch back marks that on the failed release's record, and the mark is spent once
v2 started); and, after a cutover rollback with a dry run accepted since, as the soak's
start (the cutover runbook; `cutover check` starts it there too). In any other state it
starts nothing: a v2 that runs gets the verification recorded and its soak restarted,
and a v2 you stopped in person with `service stop` stays stopped. `verify` then records
no verification, answers `v2-stopped` for the cutover and offers the operator tool's
start, once per label:

```bash
echo '{}' | /Library/DocSuri/release/.venv/bin/python -I -m docsuri_ops.u8_platform service start <label> --production
```

If `verify` is interrupted (Ctrl-C, a closed terminal, SIGTERM), for instance during its
10-minute readiness wait, it first stops again each role it had itself started from
stopped, so v2 is as the `verify` found it, and answers `release-interrupted` offering
`docsuri-release verify`. Running the same `verify` again completes it; `recover` has
nothing to do for an interrupted `verify` and answers `nothing-to-recover`.

## 5. Roll back

- **Automatically, during an install.** If a start fails, v2 is not ready within 10
  minutes of step 10, or the probe journey fails, the same command stops v2, points
  `release` back at the release `release-previous` names (the failed folder is marked
  failed and kept for diagnosis), starts v2, waits up to 10 minutes for it to be ready,
  clears the marker and routes back. Each of those steps runs whatever the one before it
  did; if any did not complete (the previous release not ready within its 10 minutes
  included, `v2-not-ready-after-switch-back`), the record still ends, the answer is
  `switch-back-failed`, and `recover` (§ 6) completes it. The public address is routed
  back only to a ready v2: otherwise the maintenance notice stays, and `recover` routes
  once v2 is ready. One switch back has nothing to complete: after a switch back both
  links name the kept release until the next install, so if that release then fails its
  own probe (at the soak's start, § 4) its switch back finds no kept release
  (`switch-back-failed` with `step: no-kept-release`), the links stay, v2's three roles
  are left stopped, and the record stays `installed` and waiting for its probe. `recover`
  then answers `recover-required` with `step: no-kept-release` and the one way out, a
  new tag (§ 6); no soak starts until that install.
- **Later, by hand.** If a problem shows up after an install finished:

  ```bash
  echo '{}' | sudo -k /Library/DocSuri/release/ops/bin/docsuri-release rollback
  ```

  It rolls back the release `release` points to, to the kept release `release-previous`
  points to, with the same link switch behind the maintenance notice. The schema and the
  arrangement stay as they are: both are additive across two releases, so the previous
  release runs on them.
  - It is refused when there is no kept release (`no-kept-release`: `release-previous`
    is missing, points to a missing folder, or to the release that runs now), when the
    release that runs now has no installed record (`no-installed-release`), when the
    kept folder's identity cannot be read (`kept-release-unreadable`), and when the
    kept release is closed: its record is `rolled-back`, `failed` or `switched-back`
    (`kept-release-failed`, naming the kept release and its state; your decision of
    2026-10-26, "Stay put, v2 stopped").
  - It is refused while anything else holds the live exclusion: a production restore, a
    switch, an abort, a cutover rollback, an install or another release rollback. While
    it runs it holds the exclusion itself (`rolling-back`). If it fails, it releases the
    exclusion and restores v2 and the route; if it is interrupted, `recover` completes it.
  - Each run acts again; it never replays an earlier rollback's stop and start.
  - While the cutover is rolled-back, it leaves v2 stopped and names the tag the links
    now point to, whether or not a dry run was accepted since: after a cutover rollback
    only the soak's start starts v2.
  - It is also refused while an install or a release rollback runs, and the cutover's
    words that switch, roll back or restart v2, and `service stop|start`, are refused
    while it runs (`release-rollback-active`); an install refuses them the same way
    (`release-install-active`). Beside the ledger's record, every `docsuri-release`
    command holds a run lock (`control/releases/release-run.lock`, a root-only file no
    other account can open, so none can hold it) from its start to its end, and writes
    a marker beside it (`control/releases/release-run.json`, root-written and readable
    by anyone: the command's pid, word and start), removed at its end. `service
    stop|start`, the soak's start and `cutover check`'s set retry read that marker
    without a password, and without locking anything, right before they act and again
    once their receipt is bound, and refuse while the command's process lives
    (`release-run-active`; your decision of 2026-10-26, "Check the release run lock").
    A marker whose process is gone was left by a command that died: they refuse it too
    (`release-run-marker-stale`) until the next `docsuri-release` command, which
    replaces it under the lock; run `recover` (§ 6) then.

## 6. Recover what an interrupted or incomplete run left

```bash
echo '{}' | sudo -k /Library/DocSuri/release/ops/bin/docsuri-release recover
```

Run it when an install or a rollback was interrupted, or answered
`switch-back-failed`, `resume-failed` or a route back that failed (an interrupted
`verify` is completed by running `verify` again, § 4). It is refused while
another `docsuri-release` command runs (`release-run-active`) and while a production
restore or a cutover's switch, abort or rollback holds the live exclusion;
`nothing-to-recover` means no record needs it. What it does:

- a record still `installing` (a run killed outright) or one that ended as interrupted
  with the links at its new release: the links point back at the kept release, as § 5's
  switch back leaves them; when the kept release is closed (below), a record still
  `installing` ends `failed` with `recover-required` instead, so the live exclusion it
  held is released and the new tag's install is not refused `release-install-active`;
- a record still `rolling-back`: it ends by where the links stand (`installed` before the
  switch, `rolled-back` after);
- a release installed while v2 was kept stopped whose probe never ran and that no longer
  runs: its record ends switched back;
- a record that ended `failed` or `switched-back` while the links still point at its
  release (a failure inside the switch back): the links point back at the kept release;
- then v2's three roles are stopped and started again (or kept stopped while the cutover
  is rolled-back), the address is routed back to v2 in live mode, the record's reason is
  cleared and the cutover names the tag the links point to.

When the links would point back at a kept release that is closed (`release-previous`
names a release whose record is `rolled-back`, `failed` or `switched-back`; your
decision of 2026-10-26, "Stay put, v2 stopped"), `recover` moves no link: it stops v2's
three roles (a role may still run the release that failed, after a stop that failed or
an install interrupted after its start; a stop of a role already stopped is done) and
answers `recover-required`, naming the kept release and its state, with the one way out:
`docsuri-release install` with a new tag (§ 3; your decision of 2026-10-27, "Drop that
remedy"). No rollback to an earlier release is offered, and no link is edited by hand:
`rollback` refuses a closed kept release, and after a completed install no earlier release
remains under `releases/`. If a stop fails, the answer says
`v2: running` with the step that failed; run `recover` again, or stop that role with the
operator tool's `service stop <label>` (the installation runbook).

The same answer when there is no kept release at all: after a switch back both links
name the kept release until the next install, so when that release fails its own probe
its switch back answers `switch-back-failed` with `step: no-kept-release` and its record
stays `installed`, waiting for its probe (§ 5). `recover` has no link to move either: it
stops v2's three roles (each already stopped is done), changes nothing, and answers
`recover-required` with `step: no-kept-release` and the one way out, `docsuri-release
install` with a new tag (§ 3). Run again, it answers the same. The record keeps
`switch-back-failed`, so `verify` answers `recover-required` and no soak starts
meanwhile; the new tag's install is not refused by it (an `installed` record holds no
exclusion), and that install settles the waiting record (its probe superseded, its
reason cleared), points `release` at the new tag and `release-previous` at the release
that failed, and starts v2 and the soak unless the cutover is rolled-back with no dry run
accepted since.
