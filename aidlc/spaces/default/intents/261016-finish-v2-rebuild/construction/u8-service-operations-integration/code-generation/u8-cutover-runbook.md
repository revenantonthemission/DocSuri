# U8 cutover runbook: the soak, the restart rehearsal, the switch, abort, rollback and settlement

Run at the Operation stages (Deployment Execution), with your decisions (Workflows
12–14, BR9.1–BR9.17). Every command is the operator tool's `cutover` word, in person,
with one JSON document on standard input and one JSON result on standard output:

```bash
echo '<input>' | /Library/DocSuri/release/.venv/bin/python -I -m docsuri_ops.u8_platform cutover <word> --production
```

Each word runs its bound PlatformControl operations in order, adds each receipt to the
CutoverRecord in the ledger, and shows each step against the time left: the switch's
4-hour bound from v1's stop while switching, the rollback window while rolling back. A
step is never cut off.

**Your decisions.** `start`, `open`, `rollback`, `cancel-rollback`, `waive-copy`,
`settle`, `date-final-snapshot`, `rehearse-restart` and `provider-decision` each take the
`approvalId` of your recorded decision on its step (`switch-start`, `admission-opening`,
`rollback`, `rollback-cancel`, `rollback-copy-waiver`, `settlement`, `disposal-date`,
`v1-restart-rehearsal`, and for `provider-decision` `provider-sign-in` or
`provider-first-effect`), and where the word takes one, the `subject` you were shown; a
subject that differs from the recorded digest is refused. Each decision is recorded
through `platform.decision.record` (Workflow 18).

**No date is typed** (your decision of 2026-11-01, "Event plus offset"). Each decided
disposal date is its event plus the policy's offset, and the command fixes it when its
event happens. The subject names the offset (in seconds) its command applies, and a
command whose subject names another offset is refused, before any effect, with
`decided-rule-differs`.

**Recording a decision: `cutover decide <kind>`**, in two calls, as the migration
decisions are. The first shows the subject, rendered from the current records, and
its digest, and records nothing:

```bash
echo '{}' | ... cutover decide switch-start --production
```

Read the subject. To decide, run the same command again with `confirm` set to the
digest you were shown (and `"decision": "declined"` to decline):

```bash
echo '{"confirm": "<digest>"}' | ... cutover decide switch-start --production
```

The subject is rendered again; if anything in it changed since you were shown it (the
cutover's state or revision, the final report), nothing is recorded and the new subject
is shown. Otherwise the answer carries the `approvalId`, the command that takes it, and,
for `start`, `open`, `rollback`, `waive-copy`, `settle`, `date-final-snapshot` and
`provider-decision`, the `subject` to pass to that command exactly as returned. Each approval is taken by its one
command and refused by every other. A date-like field typed into `decide`
(`finalSnapshotDisposeAfter`, `v1StoresDisposeAfter`, `rolledBackDisposeAfter`) is
refused with `word-or-input-refused`.

| `decide` kind | input | the subject names | taken by |
|---|---|---|---|
| `v1-restart-rehearsal` | — | — | `rehearse-restart` |
| `switch-start` | — | `finalSnapshotBackstopSeconds` 10368000 (120 days after the start's check), the accepted dry run and the soak (§ 3) | `start` |
| `final-report` | — | the report | `start`, run again |
| `admission-opening` | `providersAcceptedUnavailable` | `v1StoresDisposalSeconds` 7776000 (90 days after admission opens) | `open` |
| `rollback` | — | `rolledBackDisposalSeconds` 2592000 (30 days after v1 serves again) | `rollback` |
| `rollback-cancel` | — | — | `cancel-rollback` |
| `rollback-copy-waiver` | — | what v2 made since opening | `waive-copy` |
| `settlement` | — | `finalSnapshotDisposalSeconds` 2592000 (30 days after the settlement) and `finalSnapshotCopyId` | `settle` |
| `disposal-date` | — | `finalSnapshotCopyId` and `finalSnapshotDisposeAfter`, 30 days after the abort (§ 4) | `date-final-snapshot` |
| `provider-sign-in` | `provider` (`google` or `orcid`) | the provider; taken only while switching (§ 3, step 3) | `provider-decision` |
| `provider-first-effect` | `provider` (`resend` or `notion`) and `previewDigest` | the provider and the preview's digest, a preview held since the switch's check (§ 3, step 3) | `provider-decision` |

A command run without its approval, or with another step's, is refused before any
effect. Decisions outside the cutover (the abort's review, a production restore, a
volume retirement) are not recorded by this word.

At any point, `status` shows the record, the time left, the soak's verdict and what
BR9.2 still misses:

```bash
echo '{}' | ... cutover status --production
```

## 1. The soak (Workflow 12)

0. **Begin.** The installation's phase 7 runs `cutover begin` once (the installation
   runbook): it records the CutoverRecord for the installed release's tag, creates the
   first rehearsal database, sets it in the profile and restarts v2 on it. Run again on
   a record still `preparing`, it finishes only the steps a failure left. `cutover
   check` moves the record between `rehearsing` and `ready-to-switch`, naming what is
   missing, and completes a dry run's move a failure left unfinished.
1. **Start it.** The rehearsal v2 starts on the production profile in rehearsal mode,
   on the accepted dry run's rehearsal database (the migration runbook), once a dry run
   is accepted and the complete verification has passed on the release: the
   CutoverRecord moves from `preparing` to `rehearsing`.
2. **During the soak**, real providers serve under the pre-switch recipient bound: only
   you receive anything. The scheduled backups and at least one restore verification
   of the rehearsal database run and are recorded in the ledger. Incidents are recorded
   as in production; an isolation lapse, or an isolation check that stays unknown or
   stale past its tolerance, opens one, and the soak's clean rule counts it.
3. **At the end of the soak period** the ledger evidence decides whether it was clean.
   A new release tag restarts it; a clean result stays valid for its tag after an abort.
4. **A newer dry run.** `migration accept` sets the profile to the new run's rehearsal
   database and restarts v2 on it. Only then is the rehearsal database it replaces
   removed, with its rehearsal backup sets disposed after it. A removal that cannot
   complete waits for the disposal pass. At most two rehearsal databases exist at once:
   a dry run's start, `cutover begin` and a rollback are each refused with
   `rehearsal-database-limit`, before anything is written, while two are open.

## 2. The restart rehearsal (Workflow 12, step 5)

Within the restart rehearsal window before the switch, on your decision
(`v1-restart-rehearsal`):

```bash
echo '{"approvalId": "<approval>"}' | ... cutover rehearse-restart --production
```

v1 must already run from a fixed checkout at a recorded commit. The public address
routes to the maintenance server; every v1 named service stops and starts again from
that checkout; v1's health is then waited for locally, every 5 s for up to 10 minutes
(a v1 not answering by then is `v1-restart-failed`); v1's health and a signed-out page
must answer through the public address; the receipts and v1's commit are recorded on
the CutoverRecord. Any later change to v1's checkout or services voids the rehearsal.

**v1's restart seconds (NFR8.6).** The rehearsal times v1's own restart, from its
first start to its first local health answer, to a tenth of a second. The answer
carries `v1RestartSeconds`, and `restart-rehearsal-<cutoverId>.json` in the operator's
evidence folder keeps it with `v1RestartStartedAt` and the decision's `approvalId`;
Deployment Execution reads it against NFR8.6's 3 minutes. The rehearsal restarts no v2
job, so v2's restart is shown by the installation's authorized restart. The word run
again with the same decision restarts nothing (each start replays its receipt) and keeps
the figure already recorded for that decision, or records none
(`"v1RestartMeasured": false`) when none was; a new decision restarts v1 and measures
again.

When every BR9.2 precondition holds (a clean soak, no open incident, a valid restart
rehearsal, a complete consumer inventory, the backup volume and the runtime isolation
checks passing, an accepted dry run under the current misfit decisions), the record
moves to `ready-to-switch`. The consumer inventory has two rules of its own (your
decision of 2026-11-01, "Within 24 h of the switch"):

- **Its window.** The Cloudflare export's first and last non-empty intervals must span
  at least 14 days, so take an export longer than 14 days: empty intervals at either end
  are dropped. A shorter one is named `inventory-window-short`.
- **Its recency.** Start the switch after the export's last interval ends and within 24
  hours of it. Otherwise it is named `inventory-not-recent`. The start checks both at
  its one check instant (`switchCheckedAt`), and settlement measures the same rules from
  that instant.

## 3. The switch (Workflow 13)

1. **Start**, on your decision (`switch-start`), whose subject names the final
   snapshot's offset (`finalSnapshotBackstopSeconds`, 10368000): the start dates the
   final snapshot 120 days after its check instant (`switchCheckedAt`). The subject also
   shows two blocks for your decision (NFR8.8, performance-design § 10):
   - `acceptedDryRun`: the accepted dry run's `runId`, `durationSeconds` (from its
     snapshot's start to its parity report), `phaseSeconds` and `interruptions`;
   - `soak`: its `from` and `until`, and, over the host's 5-minute latency windows inside
     that period, `windows` (how many were counted), `p95Ms` (each route class's largest
     window 95th percentile) and `requests`. The lines are kept 14 days, so a decision
     taken more than 7 days after the soak's end counts fewer windows.

   Reading the soak's lines runs the production tool's read-only `latency-summaries` in
   person, so each of the decide word's two calls asks for your password once more.

   ```bash
   echo '{"approvalId": "<approval>", "subject": {...}}' | ... cutover start --production
   ```

   The public address routes to the maintenance server; v1's services and scheduled
   jobs stop (the 4-hour bound starts); the rehearsal v2 stops; the production database
   is recreated empty; the final snapshot is taken onto the backup volume; the final
   run imports under the frozen decisions and stops at its report.
2. **Your decision on the final report** (`cutover decide final-report`), including any
   item it met for the first time, which its subject lists. Run `start` again with that
   decision (`{"approvalId": "<approval>"}`): a declined report aborts; an accepted one
   goes on. The profile goes live
   with admission maintainer-only, v2 starts on the production database, the first live
   backup must pass its integrity check, and the public address routes to v2.
3. **The maintainer-only window.** Only you can sign in:
   - first, before signing in, look at the maintenance notice (NFR1.3, BR6.4): open the
     public address in a private window, signed out. The notice, with its 관리자 로그인,
     is on `/` and on `/search`. Start a Google sign-in and an ORCID sign-in from that
     window and return from each: the notice is on the arrival page each time. It is
     not on `/privacy` and not on `/terms`. Record what you saw on each of the six
     pages, with the time, in your cutover notes before going on; a page that differs
     is a reason to abort (§ 4), not to open;
   - sign in;
   - approve each outward provider's first effect from its recorded preview: an email
     to yourself and an export to your own Notion page. List a held outward provider's
     previews held since the switch's check, then show one's exact content:

     ```bash
     echo '{"provider": "resend"}' | ... cutover provider-previews --production
     echo '{"provider": "resend", "digest": "<digest>"}' | ... cutover provider-previews --production
     ```

     Record your decision on it, in two calls (shown, then confirmed with the shown
     digest), then apply the answer with the `approvalId` and the `subject` returned:

     ```bash
     echo '{"provider": "resend", "previewDigest": "<digest>"}' | ... cutover decide provider-first-effect --production
     echo '{"provider": "resend", "previewDigest": "<digest>", "confirm": "<shown digest>"}' | ... cutover decide provider-first-effect --production
     echo '{"approvalId": "<approval>", "subject": {...}}' | ... cutover provider-decision --production
     ```

   - verify Google and ORCID sign-in: sign in through each with your own linked
     identity, then record the verification with `cutover decide provider-sign-in`
     (`{"provider": "google"}`, shown, then confirmed) and apply it with `cutover
     provider-decision`, before you open. When a provider's real sign-in fails, record
     that instead:

     ```bash
     echo '{"provider": "orcid"}' | ... cutover provider-failed --production
     ```

     A failed sign-in provider stays unavailable. To try it again in the same window,
     record a declined `provider-sign-in` decision on it and apply it: the provider
     returns to held, you sign in through it again for real, and record a new approved
     decision.

   Each of these words runs a production tool word in person and asks for your
   password (a first effect's `decide` asks on each of its two calls, for the listing).
   A decision you record takes effect only when `provider-decision` applies it; a later
   decision supersedes an earlier one, and an approval recorded in an earlier switch, or
   naming an earlier switch's preview, is refused.
4. **Open**, on your decision (`admission-opening`), whose subject names any provider it
   accepts unavailable and v1 stores' offset (`v1StoresDisposalSeconds`, 7776000): v1's
   stores are dated 90 days after admission opens. Every required capability must be
   available, every configured provider active (or accepted unavailable), and no
   incident open. A provider accepted unavailable stays so: a sign-in provider until the
   next switch's window, refused at the start for everyone once admission opens, while
   an outward one can still be approved after opening, from a preview held since the
   switch's check, with the same `provider-previews`, `decide provider-first-effect` and
   `provider-decision`:

   ```bash
   echo '{"approvalId": "<approval>", "subject": {...}}' | ... cutover open --production
   ```

   Admission opens: the cutover is `switched` and the rollback window starts. Right
   after, v1's stopped stores are recorded as a retained copy, the profile's rehearsal
   database is cleared, the rehearsal databases are removed, and only then are their
   backup sets disposed, each set once the removal of its own database has applied. A
   removal that fails, or whose outcome is unknown, leaves its database pending
   (`rehearsalDatabasesPending`, with the reason) and its sets waiting with that same
   reason (`rehearsalSetsWaiting`); nothing of those sets is disposed. v1 stays stopped
   but installed. If that disposal stops partway, `open` answers with the reason and
   `"offered": ["open"]`; run it again and it completes only the disposal, under the
   same keys, in the same order: the database, then its sets.

## 4. Abort, before admission opens

Any failed or declined step, an interrupted final run past its bound, or the 4-hour
bound passing aborts the switch by itself. To abort yourself:

```bash
echo '{"reason": "operator-abort"}' | ... cutover abort --production
```

v1 serves again before anything of v2's is removed: the public address goes to the
maintenance server, v2 stops, v1's services and scheduled jobs start, and once v1's
health answers locally the address routes back to v1. v1's health is waited for every
5 s for up to 10 minutes; the wait never starts v1 again. Only then does the profile
return to rehearsal mode, the production database is recreated empty, and every
provider approval is cleared. A final run not yet accepted ends failed and the decisions
unfreeze. The cutover returns to `rehearsing`, the rehearsal v2 starts again, and the
abort's incident stays open until you record your review of it (`abort-review`). If a
v1 start fails, or v1 has not answered by the end of the wait, the cutover stays
`aborting` behind the maintenance notice with `v1-restart-failed`: repair v1 from its
fixed checkout and run `abort` again, which starts v1 once more and waits again; nothing
routes to v1 until its health answers locally.

**The aborted attempt's final snapshot** (your decisions of 2026-11-01, "Event plus
offset" and "Start waits"). A final snapshot the aborted switch completed stays at its
120-day date until your decision moves it to 30 days after the abort
(`abortStartedAt`). Until then, `status` and `check` name it
(`"finalSnapshotAwaitingDate": "<copyId>"`), `check` keeps the record `rehearsing` with
`final-snapshot-awaiting-date` among what is missing, and `cutover start` is refused
with `precondition-missing`. Before the next start:

1. decide the date: `echo '{}' | ... cutover decide disposal-date --production`, then
   again with `confirm`; the subject shows the copy and its date;
2. run the word with the decision and its subject:
   `echo '{"approvalId": "<approval>", "subject": {...}}' | ... cutover date-final-snapshot --production`.
   It sends the backup agent `set-date` for each of the snapshot's three parts with the
   decision's receipt and digest, then records the new date on the copy. A refusal
   answers why with `"offered": ["date-final-snapshot"]`; running it again resumes;
3. run `check` again.

## 5. Rollback, within the window after opening

On your decision (`rollback`):

```bash
echo '{"approvalId": "<approval>", "subject": {...}}' | ... cutover rollback --production
```

The public address goes to the maintenance server, v2 stops, v1's services start
unrouted and v1's local health is waited for, every 5 s for up to 10 minutes (the wait
never starts v1 again; a v1 that has not answered by then leaves the rollback
`rolling-back` with `cancel-rollback` offered); v2's lifecycle outcomes are applied to
v1 and every v1 session ends; the address routes to v1.

With v1 serving, v2 is returned to rehearsal (your decision of 2026-10-24, "Create a
fresh rehearsal database"). Opening removed every rehearsal database, so the rollback:
0. removes any rehearsal database opening left pending (only those opening addressed),
   so the two-database limit never blocks a rollback (your decision of 2026-10-25,
   "Never block a rollback"); their backup sets are disposed once the cutover is
   `rolled-back`;
1. names a new rehearsal database and records it as a retained copy;
2. creates it empty;
3. sets it in the profile;
4. only then sets admission maintainer-only and mode rehearsal, clears every provider
   approval, ends the decisions' freeze and clears the accepted dry run, whose database
   is gone.

v2 stays stopped. If any of these steps fails, v1 keeps serving and the copy does not
start; run `rollback` again and it completes the missing steps with the same database
name, replaying each receipt.

Then the stopped production database is copied onto the backup volume as a retained
copy dated 30 days after v1 served again (`rollbackV1ServingAt` plus the subject's
`rolledBackDisposalSeconds`), and recreated empty only once that copy's
checksum is recorded. The cutover is `rolled-back`; accounts and writes made in v2 are
reported per kind.

**After a rollback** (your decision of 2026-10-25, "Follow the design"), a new dry run
is needed. `migration accept` sets its rehearsal database in the profile but leaves v2
stopped; v2's three roles start, with the readiness wait, when the soak starts, once the
accepted dry run and the release's complete verification both hold. The rollback's
empty database is then the one the accepted run replaces.

- A v2 that never becomes ready starts no soak (your decision of 2026-10-25, "Confirm:
  no soak until ready"): the record stays `rolled-back`, the answer is `v2-not-ready`,
  and `cutover check` or `docsuri-release verify` (the release runbook, § 4) tries again.
  If you stopped v2 in person with `service stop` after such a start, the next `cutover
  check` starts each stopped role again under a new key rather than replaying the start
  your stop superseded.
- A release installed while v2 is kept stopped is probed when the soak starts (your
  decision of 2026-10-25, "Probe it when the soak starts"). The probe and a switch back
  need the release command's hold on the links, so `cutover check` answers
  `release-not-probed` and leaves v2 stopped;
  `echo '{"tag": "<tag>"}' | sudo -k /Library/DocSuri/release/ops/bin/docsuri-release verify`
  starts v2, waits for readiness, runs the probe journey, and only once it passed
  records the verification on the cutover and starts the soak.
- **When that `verify`'s start fails, or v2 is not ready within its 10 minutes**, no
  probe runs and nothing is switched back: the roles that did start keep running on the
  unprobed release (v2 is running, not stopped), the release's record still waits for
  its probe, and the cutover stays `rolled-back` with no verification. `cutover check`
  still answers `release-not-probed` and neither starts nor stops anything. The way out
  is to run the same `verify` again once the cause is fixed: it starts what is not
  running, waits again and runs the probe. To have v2 stopped meanwhile, stop its three
  roles in person with `service stop`. An interrupted `verify` (Ctrl-C, a closed
  terminal) stops again the roles it had started itself and answers
  `release-interrupted` with `docsuri-release verify` offered; `recover` has nothing to
  do for it.
- **After a failed probe at the soak's start** (your decision of 2026-10-26, "Leave v2
  stopped"), v2's state is:
  - `release` points back at the previous release;
  - v2's three roles are stopped, each through the service control, so each stop record
    cites a receipt PlatformControl holds;
  - the failed release's record is `switched-back` (or, when the links could not point
    back, still `installed` and waiting for its probe, so no soak can start on it until
    `docsuri-release recover` points them back);
  - the cutover is still `rolled-back`, named for the tag the links point to, with no
    verification on it, so `cutover check` starts no soak. The soak and the switch also
    refuse a cutover whose tag is not the release the links point to
    (`release-not-linked`): `docsuri-release verify` with the linked tag names it.

  What to run next: `echo '{"tag": "<linked tag>"}' | sudo -k
  /Library/DocSuri/release/ops/bin/docsuri-release verify` (the release runbook, § 4)
  starts v2 on the linked release, waits for readiness and starts the soak. If the switch
  back answered `switch-back-failed`, run `docsuri-release recover` (the release runbook,
  § 6) first; it keeps v2 stopped while the cutover is rolled-back. One case has no link
  for `recover` to move: after a switch back both links name the kept release until the
  next install, so when that release fails its own probe at the soak's start, its switch
  back answers `switch-back-failed` with `step: no-kept-release`, v2's three roles stay
  stopped and its record keeps waiting for its probe, which blocks the soak. `recover`
  then changes nothing and answers `recover-required` with `step: no-kept-release` and
  the one way out: fix the release, then `docsuri-release install` with a new tag (the
  release runbook, § 3 and § 6). Renew v2's stop records with `service stop` meanwhile.
- **When the kept release is closed** (your decision of 2026-10-26, "Stay put, v2
  stopped"): `release-previous` names a release whose record is `rolled-back` (the one
  you rolled back from with `docsuri-release rollback`), `failed` or `switched-back`. The
  failed probe's switch back then points nothing back: the links stay on the release
  that failed its probe, v2's three roles are stopped (when a stop failed, the answer
  says `v2: running` with the stop's reason as `step`, and a role still runs the
  failed release until `recover` stops it), the record still waits for its probe with
  `recover-required`, the cutover keeps its state and the tag the links point to, and
  `cutover check` starts no soak (`release-not-probed` while rolled-back; nothing starts
  in rehearsing either). `docsuri-release recover` stops v2's three roles, moves no link
  and answers the one way out: a new tag (your decision of 2026-10-27, "Drop that
  remedy"): fix the release, then `docsuri-release install` with it; v2 stays stopped
  until that install. No rollback to an earlier release is offered and no link is edited
  by hand (`rollback` refuses a closed kept release, and after a completed install only
  the two linked folders remain under `releases/`). Renew v2's stop records with
  `service stop` meanwhile, as below.
- **`verify` starts v2 only for a pending probe** (your decision of 2026-10-26): outside
  the soak's start from `rolled-back`, `docsuri-release verify` starts v2's roles only to
  probe the linked release still waiting for its probe, or to start the soak on the
  linked release after a failed probe's switch back (marked on the failed release's
  record). A v2 you stopped in person stays stopped: `verify` answers `v2-stopped` and
  offers the operator tool's `service start` (the release runbook, § 4).
- **While a `docsuri-release` command runs** (its run marker,
  `control/releases/release-run.json`, root-written and readable without a password;
  the lock itself, `release-run.lock`, is a root-only file nobody else can hold),
  `service stop|start`, the soak's start in `cutover check` and its retry of waiting
  sets refuse with `release-run-active`, read right before they act and again under
  their receipt's binding (your decision of 2026-10-26, "Check the release run lock");
  run them again once the command ended. A marker left by a command that died refuses
  them too (`release-run-marker-stale`): run `docsuri-release recover` (the release
  runbook, § 6), which replaces it under the lock.
- While v2 is kept stopped, its stop records lapse after 14 days and the isolation check
  then fails. Renew them in person before that, once per label, with the operator
  tool's `service stop` (the installation runbook). `cutover status` shows when they
  expire (`expiresAt`, `lapsed`) and whether the isolation check counts each as planned
  (`planned`, computed as the check computes it: the fixed program's own record, in its
  form and bound, citing a stop of that label that PlatformControl holds).
- A rehearsal set whose database was removed but whose disposal failed
  (`rehearsalSetsWaiting`: a rollback's left set, opening's, or the set of a database a
  newer accepted dry run replaced) is disposed of only in person (your decision of
  2026-10-26, "Only in person"). Which command disposes of it depends on the cutover's
  state:
  - while the cutover is `switched`: run `cutover open` again (`echo '{}' | ... cutover
    open --production`). It re-runs opening's disposal under its own keys and disposes of
    every waiting set. `cutover check` there disposes of none and answers
    `"offered": ["open"]`.
  - in any other state the cutover can be checked in (`rolled-back`, `preparing`,
    `rehearsing`, `ready-to-switch`, and `settled`, where an opening's set may still be
    waiting): run `cutover check`. Each run disposes again of every set still waiting,
    after its database was removed. Every run of a set's disposal, opening's, a dry run's
    move's, a rollback's or a check's, runs under a key of that run's own (counted in
    `set-disposals-<cutoverId>.json`, pinned to the cutover's identity, so no later
    decision changes it), after the earlier runs' keys are settled: a disposal that keeps
    failing never runs out of keys, one an earlier run left in flight makes the set wait
    (`effect-in-progress`), and one the agent applied before its record was written is
    recorded as disposed rather than run again.

  The standing disposal pass disposes of none: its disposal by event is the backup
  agent's in-person word, which no standing grant reaches. It only reports each set still
  waiting (`waitingSets`) with the command that disposes of it (`waitingRemedy`:
  `cutover-open` or `cutover-check`). A set waiting a day opens an incident on
  storage.capacity whose correlation names that command
  (`backup-set:<id>:waiting:cutover-open` or `...:waiting:cutover-check`), your reminder to
  run it.
- No switch, cutover rollback, `cutover begin`, dry run's move or soak start of v2 runs
  while an install or a release rollback runs (`release-install-active`,
  `release-rollback-active`); run it again once the release command has ended.
- A dry run cannot start while the cutover is `switched`, and `migration accept`
  refuses a run whose rehearsal database was removed.

If the copy cannot be completed (the volume missing, locked or full, a digest that
differs, an integrity check that fails, a broken stream), the cutover stays
`rolling-back` with v1 serving, an incident opens, and the wait ends one of three ways:

```bash
echo '{}' | ... cutover retry-copy --production                                   # once the volume check passes
echo '{"replacementApprovalId": "<approval>"}' | ... cutover retry-copy --production  # onto a replacement volume
echo '{"approvalId": "<approval>", "subject": {...}}' | ... cutover waive-copy --production  # after you are shown what is lost
```

Each `retry-copy` first completes the serving step's missing parts, then the copy. A
retry onto a replacement volume records your retirement decision on the cutover, so
later runs key the serving step's profile changes under that decision; each settles the
earlier runs' receipts first: a change already applied is replayed and recorded as done,
never run a second time, and a new effect runs only for a change no earlier run applied.

If v1 does not start, or a step fails before v1 serves again, your decision
(`rollback-cancel`) cancels: v1 stops, v2 starts again on its untouched database, and
the address routes back to v2.

```bash
echo '{"approvalId": "<approval>"}' | ... cutover cancel-rollback --production
```

## 6. Settlement, after the window

On your decision (`settlement`), once the window has closed without a rollback and the
inventory's dispositions are ready, under the inventory's window and recency rules
measured from the switch's check (§ 2). The decision can be taken before the window
ends; `settle` takes its subject:

```bash
echo '{"approvalId": "<approval>", "subject": {...}}' | ... cutover settle --production
```

The record moves to `settled` and records the move's instant (`settledAt`). The final
snapshot the subject names is then re-dated to 30 days after `settledAt`, through the
backup agent's `set-date` for each of its three parts and a re-date on its record
(`finalSnapshotRedated: true`). A snapshot that already holds an earlier date keeps it
(a settlement more than 90 days after the start keeps the 120-day date), and a closed one
is left alone (`final-snapshot-closed`). A re-date cut short answers why with
`"offered": ["settle"]`; run `settle` again on the settled record and it resumes.

v1's routes and the Next.js application are retired through the release path, under the
inventory's dispositions. v1's stores stay as their retained copy until its disposal
date. After you delete v1's stores by hand at that date, record it (refused before the
date, while any location remains, and unless in person):

```bash
echo '{}' | ... cutover v1-stores-deleted --production
```
