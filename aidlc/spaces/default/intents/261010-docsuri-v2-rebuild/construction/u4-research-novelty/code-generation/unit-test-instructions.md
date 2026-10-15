# U4 — unit test instructions

Unit: `u4-research-novelty`. Testing Contract: test-after, standard strategy, brownfield, `feature` scope with an 80% line-coverage floor for new code.

## Framework setup and configuration

- Backend: `pytest` with the existing `backend/.venv`; shared fixtures and the owner-scoped realm helpers already used by the U1/U2/U3 suites.
- Frontend: `vitest` + React Testing Library for components; the existing Playwright harness for the mounted browser journeys.
- Coverage: the project's configured coverage tooling; the 80% floor applies to this unit's new production paths and is not lowered to make a run pass.

## Exact unit-scoped commands

Run only this unit's tests — never a bare project-wide command:

```bash
backend/.venv/bin/python -m pytest tests/u4_research_novelty -q
```

Per layer while building (test-after: implement the layer, then run its tests):

```bash
backend/.venv/bin/python -m pytest tests/u4_research_novelty/database -q
backend/.venv/bin/python -m pytest tests/u4_research_novelty/repository -q
backend/.venv/bin/python -m pytest tests/u4_research_novelty/component -q
backend/.venv/bin/python -m pytest tests/u4_research_novelty/integration -q
```

Frontend:

```bash
cd frontend && npx vitest run src/u4-research
```

Browser journeys (mounted host, real API/DB):

```bash
python3 scripts/verify_docsuri_u4.py --phase browser --profile synthetic-local --environment-file /tmp/docsuri-u4-run/environment.json
```

Verify the first command runs before any test is written; a test-first or test-after step is invalid without a runnable command.

## Expected coverage targets

- 80% line coverage for this unit's new code (feature-scope floor), measured by the project's coverage configuration.
- Five to eight tests per component (standard strategy), plus integration tests for the C07/C12/C14 boundaries.
- Existing suites remain green (473 backend + 356 frontend as recorded); a failing existing test is a regression, not a skip.

## Mocking and stubbing guidance

- Prefer the real mounted boundary and real owner-scoped stores; repository/database and integration tests use the real realm helpers.
- Test doubles are held to the same contract as the mounted path (operations, error vocabulary, state transitions) so they cannot return impossible success.
- The local model and extraction adapters are exercised through `C12` fixtures labelled synthetic; fixture-only provider success is labelled as such and never claimed as parity.
- Never mock away the authority check: owner/context denial is asserted against the real path.

## Test data management

- Synthetic fixtures only; no real user data and no private content reused across runs.
- Fixture set must include: support, contradiction and insufficient-evidence cases; an unread web reference; a corrupt/unsupported extraction; malformed model output; a draft conflict with a newer acknowledged revision; a cancellation racing completion; a tombstone racing a late write; and a non-conforming outbound retrieval target.
- Realm identity and ownership are verified before use; failed or expired environments are a failed prerequisite, never a skip.
- Evidence bundles record command, exit code, counts and skip reasons with private text redacted.
