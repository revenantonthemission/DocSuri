# U5 — unit test instructions

Unit: `u5-topics-digests`. Testing Contract: test-after, standard strategy, brownfield, `docsuri-v2-finish` scope (express base) — existing suites stay green; no extra new-test floor beyond the selected strategy.

## Framework setup and configuration

- Backend: `pytest` with the existing `backend/.venv`; the owner-scoped realm helpers already used by the U3/U4 suites.
- Frontend: `vitest` + React Testing Library for components; the existing Playwright harness for the mounted browser journeys.
- Coverage: the project's configured coverage tooling (`backend/.coveragerc.u5` and `vitest.u5-topics.config.ts`); floors are never lowered to make a run pass.
- Stateful tests require an established, unexpired owned synthetic realm at `/tmp/docsuri-u5-run/environment.json`, with the current migrations and fixtures. Use the unit runner's `setup`, `migrate`, and `fixtures` phases in order; preserve an old consumed realm with `archive-owned` before preparing a fresh one. Never reset quota or extend an old realm's expiry.
- Run the Python commands below from the repository root with `backend/.venv/bin/python`; a system `python3` may lack the installed database dependencies. The runner supplies the U5 environment, pytest configuration, resource supervision and evidence capture.

## Exact unit-scoped commands

Collect-only before anything is written (runner step; must run before the first test exists):

```bash
backend/.venv/bin/python -m pytest -c backend/pytest.u5-topics-digests.ini -q
```

Full per-unit coverage pass (run alone; never a bare project-wide command):

```bash
backend/.venv/bin/python scripts/verify_docsuri_u5.py --phase coverage --profile synthetic-local --environment-file /tmp/docsuri-u5-run/environment.json
```

Per layer while building (test-after: implement the layer, then run its tests). Each stateful pass consumes finite fixture capacity; check remaining capacity before reuse:

```bash
backend/.venv/bin/python scripts/verify_docsuri_u5.py --phase database --profile synthetic-local --environment-file /tmp/docsuri-u5-run/environment.json
backend/.venv/bin/python scripts/verify_docsuri_u5.py --phase repository --profile synthetic-local --environment-file /tmp/docsuri-u5-run/environment.json
backend/.venv/bin/python scripts/verify_docsuri_u5.py --phase component --profile synthetic-local --environment-file /tmp/docsuri-u5-run/environment.json
backend/.venv/bin/python scripts/verify_docsuri_u5.py --phase integration --profile synthetic-local --environment-file /tmp/docsuri-u5-run/environment.json
```

Frontend (run from `frontend`):

```bash
npx vitest run --config vitest.u5-topics.config.ts
```

Browser journeys (mounted host, real API/DB, real local sink for the email path):

```bash
backend/.venv/bin/python scripts/verify_docsuri_u5.py --phase browser --profile synthetic-local --environment-file /tmp/docsuri-u5-run/environment.json
```

## Expected coverage targets

- This unit's new production paths are measured by the project's coverage configuration; the standard strategy volume applies (five to eight tests per component) plus integration tests at the API/preparation/delivery boundaries.
- Existing suites remain green (473 backend + 356 frontend as recorded); a failing existing test is a regression, not a skip.

## Mocking and stubbing guidance

- Prefer the real mounted boundary and real owner-scoped stores; database and integration tests use the real realm helpers.
- The email delivery capability is exercised through the real local sink in test profiles; test doubles are held to the same contract (outcome vocabulary, `pathKind`) so they cannot return impossible success. A test-profile send never claims `pathKind: real`.
- Time is injectable for scheduler evaluation (timezone boundaries, late firing); injected time must flow through the same evaluation path as production ticks.
- Never mock away the owner check: denial is asserted against the real path.

## Test data management

- Synthetic fixtures only; no real user data and no private content reused across runs.
- Fixture set must include: an account with two active topics and one unsubscribed topic; a topic with a settings revision change mid-preparation; a window with eligible content, a fully-watermarked window, and an empty window; a send attempt left `sending` by a simulated crash; an unknown outcome with and without a SendLogEntry; an unsubscribe racing a prepared run; a consent withdrawal mid-window; and a per-owner boundary account.
- Realm identity and ownership are verified before use; failed or expired environments are a failed prerequisite, never a skip.
- Evidence bundles record command, exit code, counts and skip reasons with private text redacted.
