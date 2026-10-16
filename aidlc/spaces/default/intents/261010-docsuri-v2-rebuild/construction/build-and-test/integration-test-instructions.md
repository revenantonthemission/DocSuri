# Integration Test Instructions — u4-research-novelty

## Test Framework Setup and Configuration

Backend:
- `pytest` with the existing `backend/.venv` virtual environment.
- U4 integration tests live under `tests/u4_research_novelty/integration/`.
- Shared fixtures and owner-scoped realm helpers are used (same as U1/U2/U3 suites).
- No additional test framework installation is required.

Frontend:
- Vitest + React Testing Library for component integration tests under `frontend/test/u4-research-novelty/`.
- Playwright for mounted browser journeys under `frontend/e2e/u4-research-novelty/`.

## How to Run the Tests

Run only U4-scoped commands — never a bare project-wide command.

Backend integration phases (run from repository root with `backend/.venv/bin/python`):

```bash
backend/.venv/bin/python scripts/verify_docsuri_u4.py --phase database --profile synthetic-local --environment-file /tmp/docsuri-u4-run/environment.json
backend/.venv/bin/python scripts/verify_docsuri_u4.py --phase repository --profile synthetic-local --environment-file /tmp/docsuri-u4-run/environment.json
backend/.venv/bin/python scripts/verify_docsuri_u4.py --phase component --profile synthetic-local --environment-file /tmp/docsuri-u4-run/environment.json
backend/.venv/bin/python scripts/verify_docsuri_u4.py --phase integration --profile synthetic-local --environment-file /tmp/docsuri-u4-run/environment.json
```

Frontend integration (run from `frontend/`):

```bash
npx vitest run --config vitest.u4-research.config.ts
```

Browser journeys (mounted host, real API/DB):

```bash
backend/.venv/bin/python scripts/verify_docsuri_u4.py --phase browser --profile synthetic-local --environment-file /tmp/docsuri-u4-run/environment.json
```

## Expected Coverage Targets

- 80% line coverage for u4's new production code (feature-scope floor), measured by the project's coverage configuration.
- Each measured authored file at least 80% line coverage.
- Five to eight tests per component (standard strategy), plus integration tests for the C07/C12/C14 boundaries.
- Existing suites remain green (473 backend + 356 frontend as recorded).

## Test Data Management

- Synthetic fixtures only; no real user data and no private content reused across runs.
- Fixture set must include: support, contradiction and insufficient-evidence cases; an unread web reference; a corrupt/unsupported extraction; malformed model output; a draft conflict with a newer acknowledged revision; a cancellation racing completion; a tombstone racing a late write; and a non-conforming outbound retrieval target.
- Realm identity and ownership are verified before use; failed or expired environments are a failed prerequisite, never a skip.
- Evidence bundles record command, exit code, counts and skip reasons with private text redacted.

## Cross-Unit Interaction Coverage

- C07 boundary: mounted direct HTTP requests for manuscript mode with empty and ineligible attachment scopes (asserts 503 POLICY_UNRESOLVED and unchanged admission count).
- C12 boundary: provider adapter envelope for extraction and model calls, with synthetic fixtures labelled as such.
- C14 boundary: durable accepted-work delivery, dispatch obligation reconciliation, and completion fact validation.
- U4→U6 export source read: `readNoveltyArtifactForExport` with eligibility recheck and immutable artifact tuple.
- Cross-owner denial: A's private resources are refused to B, anonymous, and revoked sessions.
- Tombstone dominance: deleted session reads return NOT_FOUND; late draft saves are rejected.
