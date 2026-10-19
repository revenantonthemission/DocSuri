# U5 verification environment recovery

Date: 2026-10-18. Branch: `feature/u5-topics-digests`.

## Observed checkpoint and current prerequisites

The recorded unit checkpoint `36365aba-82f7-44f7-aa37-80720a51b218` ran the
human-approved U5 browser command on 2026-10-18 at 08:23:49 UTC and exited 1:
`insufficient free space for host floor and remaining allocated headroom`.
It did not verify the unit. The command remains authorized:

```bash
backend/.venv/bin/python scripts/verify_docsuri_u5.py --phase browser --profile synthetic-local --environment-file /tmp/docsuri-u5-run/environment.json
```

At resumption, the host had about 26 GiB available and the current Docker
context was `colima`. The exact owned database
`docsuri-u5-3617b2afe7ed52de` was running, but its original manifest expired at
Unix timestamp `1792326964.674409`. Neither additional disk space nor a running
container renews that authorization.

## Preservation defect reproduced

The documented `archive-owned` phase exited 1 before changing files or Docker
resources. `archive_owned` called `manifest`, which called `LocalProfile.load`;
the normal execution loader rejected the expired environment before archival
could check its custody and preserve it.

The repair separates preservation identity validation from executable profile
loading. Preservation must retain the original finite timestamps, verify file
custody and identity, check exact owned Docker/database resources, and refuse
other database clients before stopping and moving anything. Normal service,
test, migration and fixture operations must continue to reject expired profiles.
No quota reset, expiry extension, resource-limit relaxation or deletion is an
acceptable recovery procedure.

## Verification status

The repair is implemented in `backend/local_profile.py` and
`scripts/verify_docsuri_u5.py`. Preservation returns validated metadata, never
an executable `LocalProfile`. The new
`tests/u5_topics_digests/operations/test_archive_expiry.py` adds 31 regression
cases for expired preservation, normal execution refusal across U1–U5, finite
timestamps, custody, exact resource identity and active-client refusals.

```bash
backend/.venv/bin/python -m pytest -q tests/u4_research_novelty/runtime/test_profile_binding.py tests/u5_topics_digests/operations/test_archive_expiry.py
```

Result: **48 passed, 1 warning** (31 new checks plus 17 existing U4 profile
binding checks). Ruff on all three changed files and `git diff --check` passed.
These isolated checks do not replace actual Colima verification.

The actual `archive-owned` phase now succeeds. It preserved the old run at
`/private/tmp/docsuri-u5-preserved-docsuri-u5-3617b2afe7ed52de-bd74976f`, stopped
its exact owned container and retained its volume and original expiry.

Fresh Colima realm `docsuri-u5-bbf3b6a7f306e989` was created at
`1792334161.375471`, expires at `1792420561.375471`, applied 59 migrations and
loaded two synthetic accounts and two papers. No real email was sent.

```bash
backend/.venv/bin/python scripts/verify_docsuri_u5.py --phase coverage --profile synthetic-local --environment-file /tmp/docsuri-u5-run/environment.json
```

The initial invocation failed before tests began because the sandbox denied
`ps`, which the runner uses for aggregate memory supervision. Its evidence was
retained. A scoped escalated retry of the same command passed **81 tests, zero
failures/errors/skips**, with **87.87% aggregate coverage** against the unchanged
80% aggregate gate. Elapsed time was 5.204 seconds and peak RSS 206,716,928 bytes.
Individual file coverage is not claimed to meet an 80% per-file target.

Evidence: `/tmp/docsuri-u5-run/coverage-evidence-1792334249726881000.json`, SHA-256
`83222bc4ff5238d2b2dea06b0052b2ed45339d14bed968ce1ecc9d25eee569f6`.

The fresh independent source review is recorded at
`construction/u5-topics-digests/code-generation/reviews/review-02.md` with
NOT-READY: four Major and two Minor findings. The preservation repair passed
the independent check; the recorded standalone test command, preference
inheritance, owner timezone, real delivery, missing empty-state journey and
selection-mechanism comment remain unresolved. No completion or merge is
claimed.

The exact human-approved browser command then ran through the unit checkpoint
on 2026-10-18 at 14:44:22 UTC. Proof ID
`2db25edd-52e1-4836-ac0b-ab787e9ce6bb` records exit 1, with unchanged source:
one journey passed, the scheduler/local-sink delivery journey failed, and one
journey did not run because the configured first-failure stop fired. The failed
assertion at `frontend/e2e/u5-topics-digests/journey.spec.ts:64` waited 20 seconds
for `마지막 발송 완료` but observed `… 발송 준비 중`. This is a failed integrated
check, not a passing local delivery demonstration.

Failure evidence is preserved at
`/tmp/docsuri-u5-run/browser-evidence-1792334687012149000.json` and
`/tmp/docsuri-u5-run/u5-phase-browser-1792334663794089000.log`.
Read-only database diagnosis found the target run still prepared, without a
send log or delivery outcome. Its owner remained active and verified, with
consent, no unknown-outcome pause and no send in flight. It was prepared at
14:44:46.287 UTC, near browser shutdown. During this browser interval, 11 older
coverage-created topics received local-sink acknowledgements at roughly
2.25-second intervals; one older eligible prepared topic still preceded the
browser topic. This supports a fixture/backlog isolation problem: the browser's
20-second expectation depends on prior suite state. It does not establish a
transport failure or justify relaxing the delivery safeguards.

No data reset, timeout extension or blind rerun has been performed. Synthetic
delivery evidence also cannot satisfy the delivery plan's real email
demonstration or the full v2 operating requirements.

The final staged `git diff --cached --check` reported six existing documentation
whitespace issues: one empty audit target with a trailing space and final blank
lines in five upstream traceability files. The earlier unstaged diff check did
not cover these previously untracked documents. Their reviewed bytes were
preserved; the final full staged whitespace check is not claimed as passing.
