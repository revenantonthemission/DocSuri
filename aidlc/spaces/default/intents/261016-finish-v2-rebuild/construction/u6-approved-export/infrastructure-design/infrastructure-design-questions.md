# Infrastructure Design Questions — U6 approved export

Date: 2026-10-20 (Asia/Seoul)
Unit: u6-approved-export (embedded library). Inputs:

- the [security design](../nfr-design/security-design.md) and [logical components](../nfr-design/logical-components.md);
- the [functional spec](../functional-design/functional-spec.md);
- the open points of the [NFR design review](../nfr-design/reviews/review-02.md);
- the built pipeline: U5's workflow (`.github/workflows/u5-topics-digests.yml`), the root CI (`.github/workflows/ci.yml`), the release workflow (`.github/workflows/release.yml`) and U5's environment tool (`scripts/verify_docsuri_u5.py`).

For a library unit, this stage produces the delivery pipeline design and its traceability. There are no deployment, services or monitoring documents, because U6 adds no servers or cloud resources of its own.

Each question offers the design I recommend as A. Answer with a letter, or in your own words under X.

## Settled from the records (no question)

These follow from decisions already on record or from the built pipeline. If one should change, say so under X of the closest question.

- **No deployment step.** Merging `develop` into `main` tags a release and publishes its notes. The deploy job was removed on 2026-08-18, when the AWS account was decommissioned, and the $0 budget keeps it that way. Rollback is reverting the change.
- **Dependency checks already cover the new SDK.** The root CI's dependency review runs on every pull request, and its `pip-audit` scans the backend's locked requirements. Both include `notion-client` once it is added, and `backend/uv.lock` pins it by hash.
- **Adding the SDK changes `backend/uv.lock`.** Every local environment tool checks that lock. Existing local environments of U2 to U5 must therefore be re-created after the change, as happened during U5's re-check. CI always builds fresh environments, so it is unaffected.
- **No Notion secret anywhere in CI.** Every CI run uses the fake Notion. The real token is only ever entered by you through the connect form, and is stored sealed in the local environment.
- **Local environment for U6.** Its folder is `/tmp/docsuri-u6-run`, with application port 18099 and database port 15499, both unused today. Its database is `docsuri_u6`. It follows U5's environment tool: setup, migrate, fixtures, browser, serve, archive and teardown. Archiving is the destructive version, which deletes the key file only after every check has passed.
- **Three of the four open review points are fixed in code generation:**
  - a candidate token can be passed into a single Notion operation without being stored;
  - a failed key-count call means protection is unavailable, never "no tokens";
  - a stale "D1–D14" source line is corrected.

  The fourth, first-time connect, is Q3 below.

## Q1. How does U6 enter CI?

Each built unit has its own path-filtered workflow. U5's has four jobs: shared contracts, frontend, backend on an isolated local environment, and browser journeys.

A. A U6 workflow (`u6-approved-export.yml`) that mirrors U5's four jobs, on pull requests into `develop`:
   - **Shared contracts:** schema and generated-binding drift checks, plus the contract tests, which cover the C09 amendments.
   - **Frontend:** U6 types, lint, Vitest with coverage, and the shared workspace build.
   - **Backend:**
     - lint;
     - the earlier units' regressions, now including U2's three keyring test files after the keyring extraction;
     - then a fresh U6 environment: setup, migrate, and one complete test and coverage pass against the fake Notion.
   - **Browser:** Playwright journeys on the U6 environment (connect, export, cancel, settle an unclear export), with the axe accessibility checks.
B. Add U6's checks to U5's workflow instead. There is one workflow fewer, but U6's checks then depend on U5's path filters and job layout.

X. Other (please specify)

[Answer]: A

## Q2. What happens after the one real export to your Notion workspace?

The real export runs only from an operator-started real composition of the local environment, never in CI, and only after you approve its exact content. Afterwards, your Notion token is still stored, sealed, in that environment until the environment ends, which is at most 24 hours.

A. Close it down straight after the evidence is recorded:
   - DocSuri disconnects, which deletes the stored token;
   - the environment is then archived (which deletes its key) or torn down;
   - the evidence note suggests you remove the integration's access in Notion if you no longer need it.
B. Keep the connection until the environment ends on its own (at most 24 hours). Teardown or archiving then deletes the key.

X. Other (please specify)

[Answer]: A

## Q3. How is a first-time connect paced and capped?

The design keys the request pace (2 requests per second) and the one-at-a-time cap to a connection. A first-time owner has no connection yet when their token is checked, so as written their first connect could never be paced and would fail. The NFR design review raised this as a significant point.

A. Key both the pace record and the one-at-a-time cap to the owner, not the connection. Each owner has at most one connection, so the effect is the same. The pace record is created on first use, so a first connect is paced and capped like any other call.
B. Keep them keyed to the connection, and create the connection record first in a "pending" state before the token is checked. This adds a state the frozen contract does not have.

X. Other (please specify)

[Answer]: B

## Q4. Follow-up to Q3: who can see the "pending" connection, and how is a stale one cleared?

You chose to create the connection record in a "pending" state before a first-time token check (Q3 B). A pending record appears only on an owner's very first connect: a replace or a reconnect already has a connection record. Two things are still open:

- whether the pending state leaves the server;
- what happens to a pending record when its check fails or the process stops mid-check.

A. The pending state stays on the server:
   - **Hidden from reads.** No read returns it. While it exists, the connection reads as "not connected", and the connect form shows its own "확인 중" during the call. The frozen contract stays unchanged.
   - **Failed check.** A failed check deletes the pending record at once.
   - **Left behind.** A pending record left by a stopped process is taken over by your next connect once it is older than 2 minutes, and housekeeping removes any that remain.
   - **Two tabs.** A second connect while a fresh pending record exists answers that a check is already running.
   - **Account changes.** Withdrawal and erasure delete it.
B. Show it in the contract. Add `pending` to the connection states as a new additive amendment (A11), so another open tab can show "연결 확인 중". Cleanup is the same as A.

X. Other (please specify)

[Answer]: A

## Consolidated Summary Confirmation

- **Q1:** U6 gets its own workflow, `u6-approved-export.yml`, which mirrors U5's four jobs on pull requests into `develop`:
  - shared contracts: drift checks and contract tests, which cover the C09 amendments;
  - frontend: types, lint, Vitest with coverage, and the workspace build;
  - backend: lint and the earlier units' regressions, including U2's keyring tests, then a fresh U6 environment with setup, migrate, and one test and coverage pass against the fake Notion;
  - browser: Playwright journeys with the axe checks.
- **Q2:** After the one real export and its evidence:
  - DocSuri disconnects, which deletes the token;
  - the environment is archived, which deletes its key, or torn down;
  - the evidence note suggests removing the integration's access in Notion.
- **Q3:** The pace record and the one-at-a-time cap stay keyed to the connection. A first-time connect creates the connection record in a pending state before the token is checked.
- **Q4:** The pending state never leaves the server:
  - reads show "not connected", and the connect form shows "확인 중";
  - a failed check deletes it at once;
  - a stale one, older than 2 minutes, is taken over by the next connect, and housekeeping removes leftovers;
  - a second connect during a fresh check is told a check is running;
  - withdrawal and erasure delete it;
  - the frozen contract is unchanged.
- **Settled from the records:**
  - There is no deploy step: merging into `main` tags a release, and rollback is a revert.
  - The dependency review and `pip-audit` already cover `notion-client`.
  - The lock change means re-creating the local U2–U5 environments.
  - No Notion secret is in CI.
  - U6's local environment is `/tmp/docsuri-u6-run` (ports 18099 and 15499, database `docsuri_u6`), with U5's tool phases and a destructive archive.
  - Three open review points are fixed in code generation.

- Looks correct
- Request changes

[Answer]: Looks correct
