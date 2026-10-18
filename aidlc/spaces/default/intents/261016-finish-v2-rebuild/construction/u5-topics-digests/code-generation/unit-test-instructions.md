# U5 — unit test instructions

Unit: `u5-topics-digests`. Revised for the human's **Repair and re-review U5**
decision. Testing Contract: test-after, standard strategy, brownfield,
express base. Implement each layer, then write and run its checks. Preserve
existing targets and behavior; no requirement is waived by a synthetic test.

## Framework setup and configuration

- Backend: `pytest` in `backend/.venv`, unit configuration
  `backend/pytest.u5-topics-digests.ini`, and existing owner-scoped realm helpers.
- Frontend: scoped Vitest/React Testing Library and Playwright configurations.
- Coverage: retain `backend/.coveragerc.u5` and
  `frontend/vitest.u5-topics.config.ts` floors. Include the changed production
  paths in measurement; do not omit new preference or delivery code to improve
  the percentage.
- Run Python commands from the repository root. Use the unit runner for
  stateful checks so identity, finite capacity, supervision and evidence remain
  enforced. An expired/missing/consumed realm is a failed prerequisite, not a skip.
- Preserve the failed or consumed realm using `archive-owned` before a fresh
  `setup`, `migrate`, `fixtures` sequence. Never extend its expiry, reset quota,
  rewrite migration receipts, delete failed-run evidence, or broaden DB grants.

## Exact unit-scoped commands

Collect only, before the first repair-layer test execution. This command neither
executes the test suite nor falls through to repository-wide collection:

```bash
backend/.venv/bin/python -m pytest -c backend/pytest.u5-topics-digests.ini --collect-only -q tests/u5_topics_digests
```

The unchanged baseline collected 81 tests. Record the actual repaired count.
The prior unscoped command is superseded; do not run it.

Preserve an existing owned idle realm, then initialize its replacement:

```bash
backend/.venv/bin/python scripts/verify_docsuri_u5.py --phase archive-owned --profile synthetic-local --environment-file /tmp/docsuri-u5-run/environment.json
backend/.venv/bin/python scripts/verify_docsuri_u5.py --phase setup --profile synthetic-local --environment-file /tmp/docsuri-u5-run/environment.json
backend/.venv/bin/python scripts/verify_docsuri_u5.py --phase migrate --profile synthetic-local --environment-file /tmp/docsuri-u5-run/environment.json
backend/.venv/bin/python scripts/verify_docsuri_u5.py --phase fixtures --profile synthetic-local --environment-file /tmp/docsuri-u5-run/environment.json
```

Use `archive-owned` only when an existing owned realm is present and its
custody/resource checks pass. Preserve the returned archive path and original
manifest bytes. Active clients must be resolved before preservation. Inspect
available capacity before allocating a replacement; no limit is waived.

Per layer after its implementation:

```bash
backend/.venv/bin/python scripts/verify_docsuri_u5.py --phase database --profile synthetic-local --environment-file /tmp/docsuri-u5-run/environment.json
backend/.venv/bin/python scripts/verify_docsuri_u5.py --phase repository --profile synthetic-local --environment-file /tmp/docsuri-u5-run/environment.json
backend/.venv/bin/python scripts/verify_docsuri_u5.py --phase component --profile synthetic-local --environment-file /tmp/docsuri-u5-run/environment.json
backend/.venv/bin/python scripts/verify_docsuri_u5.py --phase integration --profile synthetic-local --environment-file /tmp/docsuri-u5-run/environment.json
```

These are individual finite passes, not an instruction to reuse one exhausted
realm indefinitely. Preserve/recreate when required. The focused preservation
regression is independently runnable:

```bash
backend/.venv/bin/python -m pytest -c backend/pytest.u5-topics-digests.ini -q tests/u5_topics_digests/operations/test_archive_expiry.py
```

Full backend coverage in its own fresh realm:

```bash
backend/.venv/bin/python scripts/verify_docsuri_u5.py --phase coverage --profile synthetic-local --environment-file /tmp/docsuri-u5-run/environment.json
```

Frontend commands run with `frontend` as the working directory:

```bash
corepack pnpm@9.15.9 exec tsc --project tsconfig.u5-topics.json --noEmit
corepack pnpm@9.15.9 exec vitest run --config vitest.u5-topics.config.ts --coverage
```

Mounted browser check, using another freshly initialized realm with no prior
coverage-test topic backlog:

```bash
backend/.venv/bin/python scripts/verify_docsuri_u5.py --phase browser --profile synthetic-local --environment-file /tmp/docsuri-u5-run/environment.json
```

The browser invocation above remains the exact human-authorized construction
verification command. At the actual unit completion checkpoint, invoke it
through AI-DLC's checkpoint verifier so the proof binds to the current source.
A direct exploratory browser run does not create that checkpoint receipt.

## Browser and backend isolation

Coverage fixtures may enqueue scheduled work. They must never precede browser
acceptance in the same realm. Preserve the backend realm and create a new
browser realm at the same manifest path, or use separately owned realms under a
documented runner binding that leaves the authorized command intact.
CI already uses distinct backend and browser jobs; preserve that separation.

Keep the existing 20-second browser expectation and delivery/resource limits.
Test scheduler backlog separately with explicit bounded expectations. Do not
clear state, skip queued work, enlarge timeouts, or mark a failure as a pass.
Preserve every failed attempt, command, log, report and source digest.

## Required repair verification

| Area | Required cases and observable evidence |
|---|---|
| Migration and ownership | Fresh install and upgrade from the current U5 chain; targeted additions avoid duplicate U2 columns/tables; cross-owner grants refused; original migration hashes/receipts remain immutable. |
| Preference inheritance | Two owners select `en` and `ko`; inspect actual persisted presentation and email subject/body, not just stamps. Consume supported `standard`; reject unsupported vocabulary. Label missing-settings defaults honestly. |
| Timezone | Explicit confirmed zones; missing/invalid zone affects only its owner. Same UTC instant across local midnight; daily and weekly before/at/after due time; next-day late weekly execution; DST gap/fold; first confirmation and later zone changes; bounded catch-up. |
| Queued changes | Preference changes racing preparation/admission discard unsent work; sending finishes once; unknown and terminal evidence remain unchanged. Appearance-only edits do not discard an otherwise valid digest. |
| Settings authority | C03 routes mounted; current owner, revision CAS and receipt replay enforced. Manual settings remain editable after research/behavior consent revocation; delivery still stops. |
| Transport contract | Accepted response retains actual receipt/time; definite refusal fails; timeout, connection loss, ambiguous server error or malformed success remains unknown. Sanitized categories never expose secret/recipient/provider payload. |
| Recovery | Crash after receipt persistence reconciles without another send; absent evidence remains unknown. Stable initial request identity, duplicate/concurrent calls, changed payload and expired provider keys never justify automatic resend. |
| Configuration | Local/test profiles make zero real network calls with fake ambient credentials. Missing/unsupported real configuration refuses; no implicit SES, paid, or mock-success fallback. Actual adapter identity determines `pathKind`. |
| Existing behavior | Owner isolation, source eligibility, watermark, unknown pause, unsubscribe/consent changes, single-flight, orphan recovery and lifecycle disposition stay effective. |
| Frontend | Loading/empty/error/ready/partial states; acknowledged save, stale revision, honest inherited settings, account switch, keyboard/focus, Korean responsive light/dark/system UI. |
| Browser journeys | At least four: follow/settings/unsubscribe; scheduled local-sink delivery; explicit unknown resolution; recorded empty digest with no send. Add owner-preference propagation assertions through the actual mounted API/store. |

Use five to eight focused tests per changed component and integration checks for
every changed boundary; add cases where distinct races require them. After
shared preference/email code changes, run the relevant existing account,
Personalization, profile-binding and U3/U4 integration regressions with exact
file scopes and their own valid realm prerequisites. Record the selected
commands/results in the code summary. Do not run a bare project-wide pytest or
reuse U5 credentials in another unit's realm.

## Expected coverage targets

- Preserve the configured 80% aggregate backend coverage floor and any existing
  stricter targets. Report individual file coverage honestly.
- Baseline evidence is 81 backend checks and 87.87% aggregate coverage, followed
  by a failed browser checkpoint. These results are not repaired-source results.
- Existing suites must remain green. Historical 473 backend/356 frontend counts
  are references to prior work, not verified present suite sizes.
- Zero tests, skipped mandatory checks, missing evidence or missing required
  external prerequisites cannot be described as success.

## Mocking and stubbing guidance

Prefer the real mounted boundary and owner-scoped PostgreSQL. Never mock away
an authority, consent, revision or ownership check. Inject one UTC instant
through both SQL selection and Python window calculations; do not combine it
with independent database time.

Adapter contract tests use fake HTTP responses and fake credentials. A
real-adapter fixture may assert its trusted identity with a fake transport,
but that is explicitly simulated contract evidence. Synthetic assembled
application runs always remain network-disabled and record `local-sink`.
Do not label a local acknowledgement as external delivery.

## Real-delivery evidence

Prepare one bounded demonstration with the configured existing free adapter,
run identity, permitted paper content, verified sender, confirmed $0 plan and
available quota. Keep credentials in inherited server configuration; never put
them in this document, client state, error text or evidence.

Obtain explicit authorization for the recipient and exact test message before
any external send. Record the actual `pathKind=real`, provider acknowledgement,
and correlated recipient-side evidence. Provider acceptance alone proves
acceptance, not inbox placement or reading. An unconfigured or unauthorized
path remains an open prerequisite. No synthetic or mock pass closes R-06's
real-delivery condition.

## Test data management

Use synthetic accounts and eligible public-paper fixtures for automated tests.
Include different confirmed owner zones, an unresolved zone, supported
language/level values, eligible/fully-watermarked/empty windows, stale prepared
runs, sending/unknown states with and without receipts, consent/unsubscribe
races, and timezone-change boundaries.

Real delivery is a separately authorized demonstration and cannot reuse
synthetic fixtures as authority to contact someone. Evidence must record exact
commands, identities, source digests, counts and outcomes while redacting
private content and recipient addresses.
