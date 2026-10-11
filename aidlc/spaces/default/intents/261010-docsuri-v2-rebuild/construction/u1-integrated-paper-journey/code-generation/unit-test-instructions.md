# U1 unit test instructions

## Status and test ordering

These instructions accompany the proposed [implementation plan](code-generation-plan.md).
The new U1 suite, configurations and wrapper below are **planned, not yet
implemented or reported passing**. Plan Step 2 creates and verifies them before
the first behavior-test run. The exact commands below form their required CLI
interface; preserve this interface as the implementation is developed.

Use the plan's unchanged Testing Contract: implement each applicable layer or
component, then write and run its tests. Verify runner readiness first. Database,
repository, business, API and frontend tests follow their respective
implementation steps. Build and Test later verifies and extends this evidence.

Every command here targets only u1-integrated-paper-journey. Existing frontend
scripts named test:u1 and e2e:u1 belong to earlier work and are not substitutes
for the new suite. The separate Construction Verification Command remains
unset until the human approves its exact runnable invocation; none of these
development commands records that approval or completes a unit checkpoint.

## Runner setup and configuration

Run from the DocSuri repository root. Step 2 checks the actual installed Python,
Node, pnpm, uv, browser, PostgreSQL and Ollama versions against the chosen
locks/digests. Existing backend pytest/pytest-cov and frontend Vitest, Testing
Library, Playwright and axe dependencies are starting points. Do not infer
compatibility from package declarations; verify collection and a mounted slice.

The planned standard-library wrapper scripts/verify_docsuri_u1.py orchestrates
only the following bounded paths and records the actual child commands and
exit codes. It must reject unknown phases, escaping paths, missing dependencies,
unavailable required services and an empty behavior-test collection. Its phase
selector must never fall back to a repository-wide test run.

| Purpose | Planned configuration and exact scope |
|---|---|
| Python component tests | tests/u1_integrated_paper_journey/component/; backend/pytest.u1-paper-journey.ini with repo-root imports and strict markers |
| PostgreSQL behavior | tests/u1_integrated_paper_journey/database/; real PostgreSQL 16.15, persistent disposable volume, separate runtime principals |
| Repository behavior | tests/u1_integrated_paper_journey/repository/; actual selected storage, private filesystem and transactional adapters |
| Mounted API/worker integration | tests/u1_integrated_paper_journey/integration/; real assembly, claims, HTTP and progress stream |
| Local model quality | tests/u1_integrated_paper_journey/model/; real cached model manifests, source/translation rubrics and bounded retrieval |
| Operations/recovery | tests/u1_integrated_paper_journey/operations/; actual supervisor, restart/restore and resource-fault cases |
| Frontend component behavior | frontend/test/u1-integrated-paper-journey/; frontend/vitest.u1-paper-journey.config.ts |
| Mounted browser journeys | frontend/e2e/u1-integrated-paper-journey/; frontend/playwright.u1-paper-journey.config.ts |
| Shared producer/consumer bindings | tests/u1_integrated_paper_journey/contracts/; exact U1 roots/consumer closure through existing generators |
| Coverage | The listed U1 tests and an explicit inventory of new/changed U1 executable modules; retain existing stricter thresholds |

The wrapper must resolve the repository root itself, use argument arrays rather
than shell command interpolation, propagate every child failure, and record
collection totals separately from executed tests. Frontend config include/testDir
must name the U1 paths above. Python calls must pass those exact directories,
the dedicated config and strict marker selection, using the backend's locked
environment. Expose the expanded commands in each run's manifest for independent
reproduction. Missing collection is a configuration error, never a green test.

## Isolated fixture setup

The setup phase creates a uniquely named U1 synthetic environment and writes
its private manifest to /tmp/docsuri-u1-run/environment.json. It refuses an
existing directory unless its ownership marker and exact manifest match.
The manifest names only new fixture accounts, database/roles, private files,
container/volume and loopback ports. The runtime never inherits a production
database URL or provider credentials from the user's service environment.

Recheck finite CPU, memory, disk, queue, model context/output and deadline
allocations against the infrastructure design before provisioning. Keep at
least 8 GiB host disk free and measured recovery reserve. Define a finite
install/build allocation from measured dependency sizes; the 512 MiB experiment
budget does not authorize an unbounded build. If headroom cannot support the
chosen profile, stop the affected run with evidence and resolve the conflict.

The setup provisions the selected persistent-volume PostgreSQL profile and
owner-scoped roles, synthetic verification-mail sink, private fixture files and
explicit local-only model endpoint. No migrations target pre-existing user
data. No model download, paid fallback or live email is implicit. Cached model
hashes and cloud-disabled routing must pass validation before real-model tests.

```bash
python3 scripts/verify_docsuri_u1.py --phase setup --profile synthetic-local --environment-file /tmp/docsuri-u1-run/environment.json
python3 scripts/verify_docsuri_u1.py --phase runner-readiness --profile synthetic-local --environment-file /tmp/docsuri-u1-run/environment.json
```

Runner readiness validates imports, config, versions and exact collection roots.
It may report that test files are not yet authored, but must not claim behavior
passed. Before each first layer test, that layer's collection must be nonempty.
Setup and readiness are prerequisite results, not behavioral acceptance evidence.

## Exact U1 development commands

Run these phases in implementation-plan order, after the corresponding code
and test files exist. A phase runs only its row in the scope table; all require
the explicit synthetic environment manifest.

```bash
python3 scripts/verify_docsuri_u1.py --phase database --profile synthetic-local --environment-file /tmp/docsuri-u1-run/environment.json
python3 scripts/verify_docsuri_u1.py --phase repository --profile synthetic-local --environment-file /tmp/docsuri-u1-run/environment.json
python3 scripts/verify_docsuri_u1.py --phase component --profile synthetic-local --environment-file /tmp/docsuri-u1-run/environment.json
python3 scripts/verify_docsuri_u1.py --phase contracts --profile synthetic-local --environment-file /tmp/docsuri-u1-run/environment.json
python3 scripts/verify_docsuri_u1.py --phase model --profile synthetic-local --environment-file /tmp/docsuri-u1-run/environment.json
python3 scripts/verify_docsuri_u1.py --phase integration --profile synthetic-local --environment-file /tmp/docsuri-u1-run/environment.json
python3 scripts/verify_docsuri_u1.py --phase frontend --profile synthetic-local --environment-file /tmp/docsuri-u1-run/environment.json
python3 scripts/verify_docsuri_u1.py --phase browser --profile synthetic-local --environment-file /tmp/docsuri-u1-run/environment.json
python3 scripts/verify_docsuri_u1.py --phase operations --profile synthetic-local --environment-file /tmp/docsuri-u1-run/environment.json
python3 scripts/verify_docsuri_u1.py --phase coverage --profile synthetic-local --environment-file /tmp/docsuri-u1-run/environment.json
```

The coverage phase aggregates relevant scoped test evidence and, where necessary,
reruns only U1 tests with instrumentation. It must state which runs it combines
and use the same source revision. A service unavailable to CI is recorded as
unexecuted required evidence, not silently skipped into a successful unit result.
Local model/recovery evidence must accompany the exact tested source/configuration
when CI cannot reproduce it. Appropriate legacy regression checks and exact
base/head CI comparison are additional integration obligations documented in
the delivery record; they are not unscoped commands to repeat in every unit.

## Required behavior and volume

Use five to eight focused tests for each of the nine component families in the
plan, at least 45 component tests overall, plus at least sixteen real-boundary
cases and six mounted journeys. Counts do not replace semantic coverage.

| Boundary | Required checks and positive controls |
|---|---|
| Real runtime database grants | Owner-only DML; denied foreign UPDATE/DELETE and function abuse; legitimate same-transaction guarded target write; rollback and both revoke/effect orderings with two connections |
| Revisions and receipts | Missing/malformed/stale revision; absent-resource CAS; exact replay after later mutation; current-authority check before replay; same key with changed intent denied |
| Accepted work and usage | Durable acceptance after lost reply; fenced claim acquire/renew/replacement; bound payload; one result and one accounting effect; uncertain settlement remains reconcilable |
| Permission and result reads | Account B cannot list/read/stream/fetch A's work/assets; source withdrawal takes effect; fresh authenticated A can rediscover an allowed result without retained transient IDs; reads create no work or debit |
| File and process failure | Missing/corrupt/partial publication; crash before/after commit and settlement; persistent-volume container replacement and actual supported VM restart; coherent backup restore with current restrictions |
| Browser/state | Stale search response; unknown save; reconnect/sleep/restart; account switch; appearance storage failure; visible query controls; source anchors; keyboard/focus/status/reflow |
| Real output quality | P1 scaling/positional reasoning, P2 retrieval and sequence/token distinction, accurate source anchors, mathematical meaning and supported English-to-Korean translation; record every failed/incomplete output |
| Operations | Bounded queues/storage/model deadlines; no optional-telemetry data dependency; protected required incidents; reproducible injected defect and verified repair |

Six mounted scenarios cover P1, P2, supported translation, saving and fresh
authenticated return, interrupted accepted-work recovery, and cross-account
denial with authorized positive controls. Use the actual mounted backend and
frontend, real persistence and the local model for normal useful-output claims.

## Coverage, accessibility and measurement

Measure at least 80% line coverage for every new/changed U1 implementation
module. Report per-file and aggregate denominators; do not hide low-coverage
code, reduce thresholds or replace measurements with planned counts. Generated
bindings still require drift/round-trip tests; document any non-executable
generated-file classification explicitly. Preserve stricter existing targets.

Run axe on rendered journey states, then verify keyboard order, focus return,
announcements, contrast, 320px reflow, 200% text and light/dark/system with actual
browser views. Automated checks alone do not establish WCAG conformance.

Record complete-task success, output usefulness, latency distributions, recovery
time, peak memory/disk and defect reproduction/repair effort with sample sizes,
hardware/configuration and failed/unexecuted denominators. Numeric service
targets still require measured baseline and human agreement. Finite operational
limits already required by design must be enforced during these measurements.

## Mocks, fixture custody and cleanup

Use fakes only for narrow unit isolation and explicitly injected failure modes
such as lost responses, failed writes, unavailable dependencies or clock control.
They cannot establish normal source-bound assistance, actual role enforcement,
durable recovery, mounted browser integration or resource feasibility. Pair each
security denial with an authorized positive control. Keep test clock/seed inputs
explicit and avoid timing-only concurrency assertions where barriers suffice.

Use synthetic identities and eligible P1/P2 material under the recorded rights
boundary. Keep complete fetched text, private prompts, passwords, session
credentials, tokens and database connection secrets out of committed evidence.
Commit fixture provenance, hashes, minimized paraphrases/rubrics and sanitized
results. Public redistribution rights remain separate from local research use.

Each run manifest records source SHA, lock/model/image hashes, commands, test
IDs, timestamps, results, omissions and owned resource identifiers. A teardown
phase may remove only resources proven to belong to that exact manifest, after
sanitized evidence is saved; it must refuse unknown directories, shared model
caches, other containers, service data and any resource whose ownership is
uncertain. Do not prune the system or delete unrelated data to free capacity.

```bash
python3 scripts/verify_docsuri_u1.py --phase teardown --profile synthetic-local --environment-file /tmp/docsuri-u1-run/environment.json
```

Before completion, code-summary.md records the actual implemented runner,
expanded invocations, results and remaining limitations. An independent review
checks finished code, source-manifest.json and requirement traceability.
