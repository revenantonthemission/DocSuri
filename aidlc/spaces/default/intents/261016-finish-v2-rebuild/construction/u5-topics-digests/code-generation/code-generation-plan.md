# U5 — Topics and digests · Code generation plan

Unit: `u5-topics-digests`. Branch: `feature/u5-topics-digests`. Scope: `docsuri-v2-finish` (express base), test-after, standard strategy; existing suites stay green.

## Summary

- Builds: Build and Test loop-back 4 for U5 (Steps 40–48), beyond the bound by your "Retry with fix": each digest run's scheduled instant, in a new column `topics.digest_run.scheduled_at` (L4-1 and L4-7 are your choices). U5 sets it once, from the due read's `due_at`, when its scheduler prepares the run, and the database refuses every later change (decisions L4-1 to L4-6). This is U5's half of U8-A2: U8's digest producer reads the column when U8 is rebuilt, and U8's two NFR9.2 targets change only then. L4-1 is the column or a key in the preference snapshot; L4-7 leaves U5's browser-only checks out of this loop-back.
- Touches: one entry, with its comment, in U8's composed chain, `backend/u8_migrations.py`, the only file of another Unit (L4-3); a new U5 migration, `backend/modules/topics/u5_scheduled_instant.sql`; `backend/modules/topics/repository.py`, `preparation.py` and `scheduler.py`; U5's chain in `scripts/verify_docsuri_u5.py`; U5's tests: `database/test_preference_schema.py`, `database/test_chain_upgrade.py`, `database/test_migration_digests.py`, `operations/test_runner_bindings.py`, a new `repository/test_scheduled_instant.py`, `component/test_topics_scheduler.py`, and a new helper module `calendar_flow.py` moved out of `component/test_schedule_preferences.py`; U5's code summary, traceability and source manifest. No frontend file, no route and no change to `http.py`.
- Tests: 12 new backend tests (18 collected items): 1 database, 8 repository and 3 scheduler; U5's three chain-pinning test files extended under their own test names; the collect-only total goes from 331 to 349 if every test is built as listed; every changed U5 component holds five to eight tests; each new or extended test is run once with its behaviour withheld; existing suites and floors stay as they are.

## Testing Contract

```json
{
  "version": 1,
  "methodology": "test-after",
  "source": "team",
  "ordering": "** Test-last per component — Implement component fully, then write its tests.",
  "scope": "express",
  "test_strategy": "standard",
  "project_type": "brownfield",
  "applicable_notes": [
    {
      "layer": "org",
      "text": "We treat tests as a first-class deliverable in every Bolt. The specific\nmethodology (TDD, BDD, ATDD, or classic test-after) is affirmed at\npractices-discovery and recorded in `team.md` under this heading with explicit\n`Methodology` and `Ordering` fields; Code Generation resolves those fields\nindependently from coverage, tooling, and scope notes.\n\nWhen no posture has been affirmed, our default per scope is:\n- **Methodology**: test-after\n- **Ordering**: implement each applicable testable layer, then write and run\n  that layer's tests.\n- `mvp`, `enterprise`, `feature`, `infra`, `classic` add an 80% line-coverage\n  floor and CI execution before merge.\n- `bugfix`, `security-patch` add a targeted regression for the specific\n  bug/vulnerability and require the existing suite to remain green.\n- `express` uses the Minimal strategy: requirement-driven unit tests (one per\n  requirement, with a happy-path floor per component); existing tests remain\n  green.\n- `poc`, `refactor`, `workshop` add no extra new-test floor and require the\n  existing suite to remain green.\n\nThe active `Test Strategy` still applies in every scope and determines test\nvolume/types. Scope floors are additive; they never reduce or replace the\nselected strategy.\n\nBuild and Test verifies defined coverage floors and affirmed quality targets;\nthey may not be weakened to make a step pass.\n\nAffirm a stricter posture in `team.md` if the team commits to one."
    },
    {
      "layer": "team",
      "text": "**Methodology:** test-after\n**Ordering:** Test-last per component — Implement component fully, then write its tests.\n\n**Scope floors (feature scope):**\n- 80% line-coverage floor for new code\n- CI execution before merge\n- Existing test suites must remain green (473 backend + 356 frontend)\n\n**Evidence from reverse-engineering:**\n- Current coverage: ~65% overall, but Phase 7 target components at 0% (JobStatus, contentJobApi BFF routing)\n- 356 frontend tests passing (Vitest + React Testing Library)\n- 473 backend tests passing\n- Playwright E2E configured (~25 tests, ~30% coverage)\n- CI runs lint, typecheck, test:coverage, test:e2e\n- **Gap:** Phase 7 components (JobStatus, AssetViewer migration, contentJobApi BFF routing) completely untested\n- **Gap:** No Error Boundary tests, no SSE polling fallback tests, no idempotency key tests\n\n**Affirmed posture for Phase 7:**\n- Maintain test-after methodology (team default)\n- Ordering: Test-last per component (implement fully, then test)\n- 80% coverage floor for new code enforced in CI\n- All existing tests must remain green\n\n---"
    },
    {
      "layer": "project",
      "text": "- U5's component lane needs its own fresh realm: a coverage pass exhausts the realm's authentication-attempt allocation, so the runner refuses a later lane on that realm. Preserve the refused realm as a failed prerequisite and re-run on a fresh one; never relabel it. Ruff format drift in files no step touched is recorded, not fixed, when CI runs ruff check only and a file must keep pinned bytes. (learned 2026-10-28) \n\n- Tick a Code Generation plan box only after the run its own text asks for has passed, including when restoring ticks after a new Plan Approval clears them. A box whose run is owed to ci.yml's macos-filesystem job, an installation or a browser lane stays open, with the owed run named in the code summary, because editing the plan's text voids its approval. Before a checkpoint, check every verified and not-yet-verified line in the code summary against the runs' start times and source digest. (learned 2026-11-14) \n\n- Before U8's realm runs, keep free disk less the realm database above J09's 20 GiB guard and never lower the guard: with the person's approval remove only stopped docsuri-u8-<id> containers and volumes and run Colima's fstrim twice (the second pass releases what the first misses), and if swap still leaves too little, copy the preserved folders out of /tmp and ask the person to restart the Mac. Run realm B (setup, migrate, fixtures --corpus skip, verification-run) without the operations lane, which runs alone on a fresh realm, record that move as a deviation while the approved instructions still put the lane on realm B, and wait about 90 s after each archive before the next setup. (learned 2026-11-14) \n\n- For local runs on this Mac, give every DocSuri test-tool command DOCKER_HOST=unix://$HOME/.colima/default/docker.sock and DOCKER_CONFIG=$HOME/.docsuri-u8/docker-config, and confirm the run's containers through Colima's socket before recording any run or measurement as evidence, because OrbStack holds the default Docker socket after restarts. A test tool or child process that builds its own environment keeps DOCKER_HOST whenever its caller set it, and changing another Unit's tool for that waits for the person's answer. (learned 2026-11-14) \n\n- Before a record says a new or changed test catches its defect, run it once against the old code or with the awaited event withheld (edit, run, restore exactly), outside any recorded verification run, confirm the restore by digest or diff, and record the failure it gave. A test checked only by reading the code is recorded as not run and is not claimed to catch the defect. (learned 2026-11-14) \n\n- In every timing or capacity measurement on synthetic papers, give each run and each paper texts of their own, drawn from a seed derived from the measurement's token, the size and the run number, because repeated text adds no new vector to the HNSW index and makes later runs look fast. Count every run, the first included, and treat a slow first run as a finding to explain, never as a cold start to set aside. (learned 2026-11-14) \n\n- Make a DocSuri test tool's setup wait for PostgreSQL over TCP, the way its bootstrap and migrate connect, not on docker exec pg_isready over the container's Unix socket, which can pass against the image's socket-only init server. Until the U1, U2, U3 and U7 setups wait that way, check a refusal at their bootstrap or base-only migrate against the stopped container's log for the init-server restart, keep it as a failed prerequisite and rerun on a fresh environment, never relabelled. (learned 2026-11-14)"
    }
  ],
  "obligations": {
    "strategy": "standard",
    "strategy_volume": [
      "Five to eight tests per component.",
      "Unit tests plus integration tests for key boundaries.",
      "Add E2E, performance, or security tests when requirements demand them."
    ],
    "scope_floor": [
      "Keep the existing test suite green.",
      "This scope adds no extra new-test floor beyond the selected test strategy."
    ],
    "combination_rule": "Apply every selected-strategy obligation and every scope-floor obligation; neither replaces the other, and a targeted scope regression may add the narrowest necessary test type beyond the strategy default."
  },
  "plan_profile": {
    "methodology": "test-after",
    "runner_step": "Verify the existing test runner/configuration and record the exact unit-scoped command.",
    "runner_ready_before_first_test": true,
    "testable_layers": [
      "Data model / database behavior",
      "Repository / data access",
      "Business logic",
      "API / endpoint",
      "Frontend behavior"
    ],
    "steps": [
      "Project structure and production configuration skeleton.",
      "Verify the existing test runner/configuration and record the exact unit-scoped command.",
      "Data model / database behavior - implement.",
      "Data model / database behavior - write and run its tests after implementation.",
      "Repository / data access - implement.",
      "Repository / data access - write and run its tests after implementation.",
      "Business logic - implement.",
      "Business logic - write and run its tests after implementation.",
      "API / endpoint - implement.",
      "API / endpoint - write and run its tests after implementation.",
      "Frontend behavior - implement.",
      "Frontend behavior - write and run its tests after implementation.",
      "Environment/build configuration.",
      "Documentation and traceability."
    ]
  },
  "input_sha256": "sha256:3990a78e27a36dd2a57fdaaf230108e8f4333f968cfea16c978632bf38e20457",
  "contract_sha256": "sha256:0aa10a7c0f0951b1d7a42d30f48c9f9dc63f93eef1125959651d5c864e8e6eca"
}
```

## Revision basis and boundary

The human selected **Repair and re-review U5** on the six findings in
[review-02.md](reviews/review-02.md) and the failed browser checkpoint. This plan
modifies the existing implementation; it does not restart it or accept missing
capabilities. The previous plan and implementation are recoverable from
`1e35045b`. All repair checkboxes below start unchecked.

Inputs remain the approved [functional specification](../functional-design/functional-spec.md),
[business rules](../functional-design/rules.md), [entity model](../functional-design/entities.md),
[security requirements](../nfr-requirements/security-requirements.md),
[technology decisions](../nfr-requirements/tech-stack-decisions.md),
[security design](../nfr-design/security-design.md),
[logical components](../nfr-design/logical-components.md),
[pipeline contribution](../infrastructure-design/cicd-pipeline.md),
[unit catalogue](../../../inception/units-generation/unit-of-work.md),
[requirements](../../../inception/requirements-analysis/requirements.md), and
[delivery plan](../../../inception/delivery-planning/bolt-plan.md).
The [repair assessment](../../../maintenance/u5-repair-assessment.md) supplies
source evidence and migration cautions, not a scope waiver.

Keep existing follow/reactivate/unsubscribe, owner checks, revision handling,
chronological windows, watermark, lifecycle disposition, consent and orphan
recovery behavior. Preserve the original finite realm expiry, evidence and
resource bounds, including the corrected expired-realm preservation path.
Do not copy account or preference ownership into Topics.

## Repair decisions and integration rules

- Language and level use Personalization/C03's authoritative settings and
  revision, not C02 profile JSON or the unused SQL language column. Mount the
  necessary settings routes in U5 with account-control authority; manual settings
  must remain usable independently of research consent. Add a narrow,
  owner-authorized background read rather than pretending a worker has a browser
  session. Preserve supported vocabulary; reject unsupported values instead of
  silently mapping them to Korean or inventing another difficulty.
- Keep the existing missing-settings defaults `en`/`standard`, explicitly labelled
  as defaults. The chosen language changes actual digest subject, explanatory
  text, labels and empty-state presentation; `standard` selects the supported
  standard presentation. Original paper titles retain their source wording.
- Resolve the owner's explicit IANA timezone through the settings owner's
  contract and expose the effective zone. Synthetic fixtures set their zones
  explicitly. An unconfigured real owner must receive a clear configuration
  state rather than an assumed location. Validate against the installed timezone
  database; coordinate schemas, Python/TypeScript bindings, writer and readers.
  Topic rows hold an execution snapshot, not a second authoritative preference.
- Use one aware instant and the owner's zone for due-time selection, weekday and
  inclusive calendar-date windows. Filter due owners before bounded pagination.
  A DST gap becomes due at the first valid instant after the requested wall time;
  a repeated wall time creates at most one run for the local window. Preserve
  chronological ordering and watermark exclusion across timezone changes.
- Weekly scheduling must satisfy both the selected weekday and wall time. Late
  execution, including the following day, retains the intended occurrence and
  local window date. Persist or deterministically recover the next occurrence
  for bounded chronological catch-up within existing limits. Initial timezone
  confirmation and later timezone changes set an explicit effective boundary;
  do not invent historical zones or retroactive sends. Clarify canonical C08's
  older 'nonoverlapping windows' wording: schedule occurrences are unique, while
  the approved rolling 7/30-day content lookbacks may overlap and watermarks
  suppress repeated delivered items.
- Snapshot preferences, timezone, source revision and effective presentation
  with the prepared run. A change to the effective language/level/timezone
  fingerprint invalidates unsent preparation before sending; unrelated
  appearance/onboarding edits do not. Keep the C03 revision for provenance/CAS.
  An already-started attempt finishes once.
  Sent, failed and unknown evidence is never rewritten by a later preference
  update. Re-prepare discarded work as a new row, preserving BR2.4.
- Extend the existing email seam with a digest-specific result:
  `accepted`, `refused`, or `unknown`, actual receipt and acknowledgement time.
  Existing account email callers keep their established interface. Resolve
  `pathKind` from the actual bound adapter; content provenance remains separate.
  Real acceptance requires a valid provider acknowledgement identifier.
  Timeouts, lost responses and malformed successful responses cannot imply
  definite refusal. Persist receipt evidence before recording terminal outcomes.
- Bind a stable provider idempotency key to the immutable run/request where the
  configured adapter supports it. It protects the initial send; it does not add
  automatic resend or POST-based reconciliation. Reconciliation reads evidence;
  missing evidence keeps the outcome unknown until explicit owner resolution.
  BR3.2, BR3.3 and post-unsubscribe protections remain unchanged.
- Real operation uses an explicitly configured existing free email adapter,
  without an implicit SES or paid fallback. Synthetic/local/test profiles remain
  network-disabled even with ambient credentials. Fail closed on unknown
  provider names, missing configuration, mismatched policy/adapter, unsupported
  vocabulary, or exhausted limits. Keep actual account-plan/quota verification
  and one bounded authorized external demonstration as evidence prerequisites.
- Email-service credentials remain with the inherited delivery capability and
  server configuration. Topics neither stores nor logs them. Inception NFR3 is
  specifically the U6 Notion-token requirement and remains N/A for U5; that does
  not waive inherited secret-custody obligations. Qualify old statements about
  'no configuration' as no new service/secret store: the existing adapter still
  needs explicit composition and documented configuration.
- Preserve applied migration bytes/receipts. Use targeted additions rather than
  importing all U2 account SQL into U5's overlapping U3/U4 chain. Correct R-03's
  mechanism description without rewriting an applied ledger; the corrected
  unreleased SQL comment needs a fresh verification baseline and a documented
  path for preserved older synthetic realms.

## Plan steps (test-after: implement each layer, then write and run its tests)

- [x] **Step 1 — Preserve baseline and bind configuration responsibilities.**
  Keep the current working branch and failed evidence. Pin source boundaries,
  component owners, supported preference vocabulary and real/local transport
  configuration in the existing U5 assembly. No new service, framework, provider
  account or secret store. Inspect prerequisites without displaying secrets.
  Trace: FR1; NFR6.1; R-04–R-06; pipeline contribution.

- [x] **Step 2 — Repair and verify the unit-scoped runner instructions.**
  Correct R-01 in this plan and test instructions to
  `backend/.venv/bin/python -m pytest -c backend/pytest.u5-topics-digests.ini --collect-only -q tests/u5_topics_digests`.
  Run from the repository root after approval. The current baseline collects
  81 tests; record the actual final count rather than prescribing it.
  Preserve runner supervision and coverage floors. Trace: R-01; Testing Contract.

- [x] **Step 3 — Data model / database behavior — implement.**
  Add targeted owner-setting/timezone and immutable preparation-snapshot
  migrations in their owning modules. Bind source revision, presentation,
  delivery request identity and transport evidence to each run without new
  duplicated business ownership. Restrict cross-component grants. Preserve
  terminal evidence, window uniqueness, lifecycle deletion and rollback
  compatibility. Correct R-03's selection comment to describe direct
  eligibility/purpose/withdrawal predicates. Trace: FR1.2–FR1.4; NFR1, NFR4;
  R-03–R-06.

- [x] **Step 4 — Data model / database behavior — test after implementation.**
  Extend `tests/u5_topics_digests/database/` with fresh-install and upgrade
  coverage, immutable evidence/revision constraints, timezone validation,
  restricted grants and rejected migration drift. Keep prior 59-migration
  realm evidence separate from new baseline evidence. Trace: Step 3; NFR1/NFR4.

- [x] **Step 5 — Repository / data access — implement.**
  Expose owner-owned background settings reads, resolve timezone before bounded
  due filtering, snapshot preferences atomically, and fence prepared runs
  against stale preference/settings revisions at send admission. Preserve
  receipt-first reconciliation and owner isolation. Keep topic writers inside
  Topics and preference writers inside Personalization. Trace: FR1.2–FR1.4;
  BR1.2/1.3/2.4/3.2; R-04–R-06.

- [x] **Step 6 — Repository / data access — test after implementation.**
  Extend `tests/u5_topics_digests/repository/` for two-owner settings,
  forbidden cross-owner reads/writes, due-filter pagination, simultaneous
  preference/send admission, discarded re-preparation, immutable unknown/sent
  evidence, receipt persistence and watermark correctness. Trace: Step 5;
  NFR1.1/NFR4.1–NFR4.3.

- [x] **Step 7 — Business logic — implement.**
  Complete preparation-time language/level consumption and rendering, owner-zone
  scheduling and weekly/date/DST semantics. Add typed digest transport outcomes
  through `backend/modules/accounts/integrations/email.py` or an adjacent
  account-owned adapter, injected by U5 composition. Protect local/test
  isolation, finite real-send budget and actual provider receipts. Reconciliation
  never sends again; unresolved ambiguity remains visibly paused. Preserve
  consent/unsubscribe and all existing lifecycle/recovery guards. Trace:
  FR1.1–FR1.6; BR1.2–BR4.3; R-04–R-06.

- [x] **Step 8 — Business logic — test after implementation.**
  Extend `tests/u5_topics_digests/component/` and focused delivery tests for
  differing owner languages/zones, level behavior, midnight/weekly boundaries,
  DST gap/fold, late firing, zone changes, stale preparation, accepted/refused/
  unknown responses, receipt-loss and post-receipt crashes, duplicate/concurrent
  attempts and expired provider keys. Assert zero network calls in synthetic
  profiles even with fake ambient credentials; no SES/paid/mock-success fallback.
  Trace: Step 7; NFR2/NFR4/NFR6; R-04–R-06.

- [x] **Step 9 — API / endpoint — implement.**
  Mount the owner settings routes in U5, coordinate C03/shared DTO/schema bindings
  and digest effective-preference readouts, and retain operation/revision
  receipts and current authority checks. Provide explicit unconfigured-zone,
  unsupported-preference and real-transport configuration states. Do not expand
  anonymous access or add an effect-triggering read. Trace: FR1.2/FR1.4;
  NFR1/NFR2; R-04–R-06.

- [x] **Step 10 — API / endpoint — test after implementation.**
  Extend `tests/u5_topics_digests/integration/` with mounted settings, revision
  conflict/lost-ack replay, account switch, foreign references, invalid timezone,
  consent-independent manual settings, and consent-dependent delivery. Verify
  inherited account/personalization and research/corpus boundaries through
  explicit focused regression commands, without claiming whole-release parity.
  Trace: Step 9; FR1.2/FR1.5/FR1.6; NFR1/NFR2.

- [x] **Step 11 — Frontend behavior — implement.**
  Show actual inherited language/level/timezone and acknowledged saves in the
  Korean responsive workspace; link or mount the existing settings UI needed
  to configure them. Keep wrong-owner/account-switch cleanup, keyboard/focus,
  appearance modes and truthful delivery/unknown/empty feedback. Correct stale
  helper text only after its claimed behavior exists. Trace: FR1.2/FR1.4;
  NFR5.1; R-02/R-04/R-05.

- [x] **Step 12 — Frontend behavior — test after implementation.**
  Extend scoped Vitest/RTL tests, then run at least four mounted journeys:
  follow/settings/unsubscribe, scheduler/local-sink delivery, explicit unknown
  resolution, and the promised empty-digest state. Include owner preference
  propagation and truthful no-send empty outcomes. Keep the existing timeout and
  send limits. Trace: FR1.1–FR1.5; NFR5.1; R-02 and browser failure.

- [x] **Step 13 — Environment/build configuration and integration evidence.**
  Repair local suite isolation in `scripts/verify_docsuri_u5.py`, fixture
  helpers and test configuration as necessary: a browser realm must be fresh
  and independent of coverage fixtures; preserve consumed/failed realms before
  preparing replacements. Retain CI's separate backend/browser jobs. Verify
  formatter/lint/typecheck/schema generation, targeted inherited regressions,
  U5 backend coverage and mounted browser checks. Document real adapter
  configuration and finite quota/cost enforcement. Prepare a bounded real-send
  check; execute it only after verified free capacity, sender, permitted content
  and an explicitly authorized recipient/send are available. Trace: NFR6.1;
  R-01/R-06; pipeline contribution; delivery-plan B06.

- [x] **Step 14 — Documentation, fresh review and completion evidence.**
  Update `code-summary.md`, `traceability.json`, `source-manifest.json` and
  instructions with actual changed paths, commands/results, remaining gaps and
  all six finding dispositions. Coordinate affected formal contract definitions
  and consumer bindings without silently altering approved capability scope.
  Obtain a fresh independent architecture review over final source and artifacts;
  preserve old review/evidence. Run the existing authorized browser checkpoint
  through AI-DLC after source is settled. Real email evidence and all mandatory
  conditions must be met before claiming U5 complete; if an external prerequisite
  remains unavailable, report it rather than substituting a local pass.
  Only completed work merges by PR into `develop` under `CONVENTIONS.md`.
  Trace: all FR1 and applicable NFRs; R-01–R-06; stage Step 5/6.
- [x] **Step 15 — Confirm the finished build for the reopened attempt.**
  Code Generation was reopened only so Step 14 could be marked complete after its
  final review froze the plan. Change no application source. Verify every path in
  `source-manifest.json` exists, record in `code-summary.md` that Step 14 is
  complete (real delivery accepted and inbox-confirmed; mail-client one-click
  unsubscribe worked; browser confirm fixed and covered by automated tests but not
  re-run live), obtain a fresh independent architecture review for this attempt,
  then run the authorized browser checkpoint through AI-DLC.
  Trace: stage Step 5/6; R-15.

## Build and Test loop-back 1 (2026-10-28)

Build and Test's target check (`construction/build-and-test/test-results.md`, Target Verification Matrix and Loop-Back Log) found 4 of U5's targets Not Met and 20 that no test in a passed lane checks in full. Every U5 suite passed. You chose "Retry with fix" on 2026-10-27, and on 2026-10-28 you decided the three design questions this repair needs. Steps 1–15 stay as built; Steps 16–25 are new and start unchecked.

**Decisions:**

- **L1-1, refusal detail kept (your decision).** A definite provider refusal keeps the provider's HTTP status and its validated error name beside the plain-language category, as `u5_refusal_detail.sql` built them: a status from a fixed set and a name matching `^[a-z][a-z0-9_]{0,63}$`, or `name-unavailable`, never free text, a secret, a payload or an address. This amends the wording "a plain-language category only" of U5's security requirements (Data Protection). It is recorded here and in the code summary rather than in the approved requirements file, so the stages built on that file are not flagged for a re-check.
- **L1-2, the shared shell files are counted by U2's cumulative lane (your decision).** `frontend/src/App.tsx` and `frontend/src/api.ts` are measured by `vitest.u2-cumulative.config.ts` under its 80% floor over all of `src/`. U5's lane keeps measuring `src/u5-topics/**`. U5's test instructions say so.
- **L1-3, the two unmeasured backend files join U5's report (your decision).** `backend/local_observation.py`, and `backend/modules/accounts/integrations/email.py` if it remains a U5 change after Step 19, join `backend/.coveragerc.u5`'s include list under its 80% floor. The other twelve changed backend files stay with the reports that already measure them: U8's for the shared runtime files and `local_transport.py`, U2's for `accounts/local_http.py`, U3's and U4's for their hosts. U5's runner, `scripts/verify_docsuri_u5.py`, stays unmeasured, as U8's runner does; its behaviour is tested.
- **L1-4, the unused seam is removed.** `send_digest_email` on the account email client has no caller anywhere. Digests go through `digest_email.py`. Removing it is the clean fix; the alternative, a caller invented for it, would be dead weight.

**Steps (test-after):**

- [x] **Step 16 — Record the decisions.** Write L1-1 to L1-4 into `code-summary.md` (deviations) and `traceability.json`. The refusal-detail target cites L1-1. No source changes. Trace: Build and Test loop-back 1.

- [x] **Step 17 — Data model / database — tests.** Add to `tests/u5_topics_digests/database/`:
  - (a) The `docsuri_topics` login is refused INSERT, UPDATE and DELETE on every other owner's tables, and SELECT on accounts tables. Its intended reads are listed and asserted as the only ones: the corpus eligibility reads and the narrow preference read.
  - (b) Every other owner login is refused INSERT, UPDATE and DELETE on every topics table.
  - (c) The topics schema's table list is pinned to its eight tables. The design's "six owned entities" predates the two repair tables, and the code summary says so.
  - (d) An upgrade test: apply U5's chain through the last migration before the repairs, insert representative topics, runs, outcomes and settings, apply the rest, and assert the rows, constraints and guards hold.
  - (e) A digest list of every applied U5 migration file, so an edit to an applied file fails the test.

  Trace: NFR1.2, NFR2.2; logical-components (repositories, one writer); required repair verification (migration and ownership).

- [x] **Step 18 — Repository — tests.** In `tests/u5_topics_digests/repository/`, the lifecycle participant's withdraw and erase change only topics rows: the accounts and other owners' rows they could reach read back unchanged, and the participant's login holds no write grant outside topics. Trace: NFR2.2.

- [x] **Step 19 — Business logic — implement.** Remove `send_digest_email` from the account email client interface in `backend/modules/accounts/integrations/email.py`, and the docstring mention in `backend/modules/topics/delivery.py`. If `email.py` then matches its content before U5, drop it from `source-manifest.json` and from L1-3's include list; otherwise L1-3 measures it. Trace: Testing Contract (key boundaries); L1-4.

- [x] **Step 20 — Business logic — tests.** Add to `tests/u5_topics_digests/component/` and `operations/`:
  - (a) The message a send would make equals the run's stored presentation exactly: subject, text, html, recipient and the two List-Unsubscribe headers, with no other field (no cc, bcc or reply-to).
  - (b) The email subject follows each owner's language (`en`, `ko`).
  - (c) An owner with a missing or invalid zone leaves other owners' topics due, and a weekly topic falls due exactly at its due instant.
  - (d) A failing digest step leaves the scheduler's other steps and the search, library, accounts and research answers unaffected.
  - (e) U5's configuration, activation record and stored rows hold no key material or secret field, and the provider key is read only from the process environment at assembly.
  - (f) A source check: U5's production modules import no logger and call no `print`.
  - (g) U5's tool fails a phase on zero tests, any skip, an error, and a missing or invalid JUnit report.
  - (h) Evidence records the exact command, the source digests and the counts, and redacts recipients and private content.
  - (i) `backend/local_observation.py`'s U5 lines are exercised.

  Trace: data protection (delivery content, no credentials); required repair verification (preference inheritance, timezone); logical-components (blast radius); security-design (no new logging); expected coverage (no false success); test data (evidence redaction).

- [x] **Step 21 — API / endpoint — tests.** In `tests/u5_topics_digests/integration/`, U5's mounted surface is pinned: the routes it serves and the processes and folders it uses are exactly the listed ones, so U5 adds no service, port, store or deployment surface. Trace: logical-components (one failure domain).

- [x] **Step 22 — Frontend — tests.** In `frontend/e2e/u5-topics-digests/` and `frontend/test/u5-topics/`:
  - (a) The settings form and the resolve control pass axe with `wcag2a`, `wcag2aa`, `wcag21aa` and `wcag22aa`, and the 320 CSS px reflow check, in the light, dark and system themes, with focus visible on each control.
  - (b) No credential appears in browser storage or in the served bundle.
  - (c) U5's views import only React, SWR, the shared `ui` and `api` modules and `topics.css`, so no new UI stack enters.

  Trace: NFR5.1; real-delivery evidence (credentials kept out); tech-stack decision (no new stack).

- [x] **Step 23 — Configuration and measurement.** Apply L1-3 to `backend/.coveragerc.u5` and L1-2 to U5's `unit-test-instructions.md`, and list there which report measures each of U5's other changed files. Run U5's coverage on a fresh realm; Step 20's tests keep it at or above 80%. No floor changes. Trace: expected coverage (backend); framework setup (frontend coverage).

- [x] **Step 24 — Process evidence.** Record in `code-summary.md`:
  - each component's test count from the collect-only run, file by file, against the standard strategy's five to eight;
  - the 81 baseline checks mapped to today's test ids, with their status;
  - the collect-only total;
  - the layer order, as the plan's ticked steps show it.

  Trace: Testing Contract (strategy volume, runner step, scope floor, methodology).

**Found while building Steps 16–24 (2026-10-28).** The new checks found two defects the steps above do not cover. Steps 25 and 26 fix them, so Step 22 can pass in full:

- **Dark-theme contrast in U5's settings form (WCAG 1.4.3).** In the dark and system-dark themes, all 11 form controls fail axe's colour-contrast rule: #111111 text on #131519 (1.03:1), and the unsubscribe button #b3261e on #131519 (2.79:1). The topics list's muted text (#555 on the dark panel, about 2.4:1) shares the cause. `frontend/src/u5-topics/topics.css` uses `--surface`, `--text`, `--muted` and `--border`, which no stylesheet defines, so the light fallbacks always apply. U4's and U6's views use the workspace tokens `--color-surface`, `--color-text`, `--color-text-muted`, `--color-border` and `--color-danger`, which carry dark values.
- **A date-pinned existing test.** `tests/u5_topics_digests/component/test_schedule_preferences.py` pins calendar instants, starting 2026-11-01 05:30 UTC, while `topics.next_occurrence` returns only occurrences at or after the follow, settings and zone times, which come from the run clock. From that date the tests that expect an occurrence get none.

Recorded, not fixed here: `topics.revoke_email_unsubscribe()` keeps PostgreSQL's default PUBLIC EXECUTE. It is a trigger function, and only the topics login and owner reach its schema, so nothing can call it today. Fixing it needs an appended migration, which also changes U8's composed chain. U8's built-file pins for `backend/modules/topics/delivery.py` and `backend/.coveragerc.u5` change with Steps 19 and 23, and U8's loop-back updates them.

The reopen reset the boxes of Steps 1–15. Their work stands, and this attempt's runs exercise it again: Steps 17–24's lanes and Step 27's. So they are ticked again, and Step 27's review and checkpoint stand in for Steps 14 and 15 in this attempt.

- [x] **Step 25 — Frontend — implement.** In `frontend/src/u5-topics/topics.css`, replace `--surface`, `--text`, `--muted` and `--border` with the workspace tokens `--color-surface`, `--color-text`, `--color-text-muted` and `--color-border`, and use `--color-danger` for the unsubscribe button. Drop the hard-coded light fallbacks, so every theme takes its own values, as U4's and U6's stylesheets do. No layout change. Step 22's settings-form check then covers it. Trace: NFR5.1 (contrast).

- [x] **Step 26 — Business logic — tests.** Make `tests/u5_topics_digests/component/test_schedule_preferences.py` take its instants from the injected clock: follow, settings and zone times come from the same fixed `now`, and each test's expected occurrences are derived from that `now`. Keep every case's meaning: fold, gap, weekly wall time, next-day recovery, due filter before the page limit, and owner time zones. The tests then pass on any date. No production change. Trace: Testing Contract (scope floor: existing suites stay green).

- [x] **Step 27 — Run, record and review.** Run U5's lanes on fresh realms:
  - `coverage`, then `component` in a later minute;
  - `browser` on its own fresh realm, with every spec passing;
  - the frontend Vitest lane with coverage, `tsc` and ESLint;
  - Ruff on U5's targets.

  Then update `code-summary.md`, `traceability.json` and `source-manifest.json`, get a fresh architecture review of this attempt, and run U5's checkpoint. Trace: stage Steps 5 and 6.

## Build and Test loop-back 2 (2026-11-15)

Build and Test's re-run of 2026-11-15 (`construction/build-and-test/test-results.md`, Target Verification Matrix and Loop-Back Log) passed every U5 lane but found one of U5's targets Not Met, the Testing Contract's test volume, and three that no test or run checks in full. You chose "Retry with fix" on 2026-11-15. NFR5.1's two unchecked clauses get checks here. The other two, the order of work in the methodology layers and in the runner step, only Code Generation's records can show, and no step here changes them. Steps 1–27 stay as built; Steps 28–33 are new and start unchecked. No production code changes.

**Decision (proposed with this plan):**

- **L2-1, the runner's tests are grouped by the runner's parts.** `tests/u5_topics_digests/operations/test_runner.py` holds 28 test functions, one per safety boundary of `scripts/verify_docsuri_u5.py`, where the Testing Contract asks for five to eight per component. The runner has five distinct parts, so the file is split into one test file per part, each holding five to eight of the existing tests, moved unchanged: no test is merged, weakened or dropped. The alternatives were to merge the 28 into at most eight parametrized functions, which would bundle unrelated boundaries into one test, or to keep the file and leave the target Not Met. If you prefer either, choose Request Changes and say which.

**Steps (test-after; every step adds or moves tests only):**

- [x] **Step 28 — Record the decision and the scope.** Write L2-1 into `code-summary.md` (deviations) and `traceability.json`, and record why the two order-of-work targets and the later-stage one stay as they are. No source changes. Trace: Build and Test loop-back 2.

- [x] **Step 29 — Repository — tests: the lifecycle participant.** Add `tests/u5_topics_digests/repository/test_lifecycle_participant.py`, on the realm's own stores:
  - (a) A reactivation changes no topics row and still records its disposition.
  - (b) A withdrawal unsubscribes the account's active topics and discards only its `prepared` runs; a `sending` run is left to finish its single attempt.
  - (c) The `pending_work` scope of an erasure discards the account's prepared runs and leaves its topics' status unchanged.

  With the three tests that reach it today, the participant has six. Trace: FR1.6; BR4.1, BR4.3; Testing Contract (strategy volume).

- [x] **Step 30 — Business logic — tests: the topics probe.** Add to `tests/u5_topics_digests/component/test_owner_observation.py`:
  - (a) A topics store the probe cannot read, through a real denied grant, is recorded as `observation.storeDenied`, and the evidence holds that reason key only, never the error's text.
  - (b) A recorded topics observation holds exactly its four counts (`topics`, `runs`, `sends`, `guard_functions`) and no name, identifier or address.

  With its four tests today, the probe has six. Trace: U5 security design (no new logging; evidence of ids and counts only); Testing Contract (strategy volume).

- [x] **Step 31 — Tests: the runner's tests by part (L2-1).** Split `tests/u5_topics_digests/operations/test_runner.py` into five files, moving each test unchanged with the imports and helpers it uses:
  - `test_runner_supervision.py` (8): measured memory, the observation timeout, the browser snapshot per tick, the process-tree snapshot (union and deadline), proportional bytes, PSS on Linux, and the proportional budget;
  - `test_runner_clock.py` (5): the clock advance, the browser clock child, the delegation's refusals and its revocation, and the refused parallel runner;
  - `test_runner_configuration.py` (5): the database command's configuration, private evidence, content digests, the policy reference and the phase catalog;
  - `test_runner_bindings.py` (5): the child environment's manifest, the migration chain, owner and realm bindings, the transport binding and the local profile's manifest;
  - `test_runner_serving.py` (5): browser assets, the fixture record and its setup, serving the owned release, and the refused real delivery.

  The collect-only total is unchanged by this step. Trace: Testing Contract (strategy volume).

- [x] **Step 32 — Frontend — tests: NFR5.1's announcements and names.** In `frontend/test/u5-topics/` (Vitest with Testing Library):
  - (a) Following a topic, unsubscribing, saving settings and resolving an unknown outcome each announce their message in the polite status line (`role="status"`), and a failed request announces in `role="alert"`; each assertion reads the live region, not only the text.
  - (b) The controls of the topic list and of the resolve control carry their Korean accessible names: 새 주제, 주제 팔로우, 발송 설정, 구독 해지, 배달됨으로 해결 and 미전달로 해결.

  Trace: NFR5.1.

- [x] **Step 33 — Run, record and review.** For each new test, run it once with the behaviour it awaits withheld (edit, run, restore exactly, confirm the restore by digest), outside the recorded runs, and record the failure it gave. Then run U5's lanes on fresh realms:
  - `coverage`, then `component` on its own fresh realm;
  - `browser` and `database`, each on its own fresh realm;
  - the frontend Vitest lane with coverage, `tsc` and ESLint;
  - Ruff on U5's CI list, and the collect-only command.

  Then update `code-summary.md` (each component's test count, file by file, and L2-1), `traceability.json` and `source-manifest.json`, get a fresh architecture review of this attempt, and run U5's checkpoint. Trace: stage Steps 5 and 6.

When this attempt's approval clears the boxes of Steps 1–27, their work stands: each is ticked again only after Step 33's runs, which exercise it again, have passed, as the project's rule asks.

## Build and Test loop-back 3 (2026-11-17)

Build and Test's fourth run (`construction/build-and-test/test-results.md`: Target Verification Matrix, Outcome and Loop-Back Log entry 3) passed every U5 lane but left U5's test volume Not Met, and NFR5.1 and the preference inheritance Unverified for clauses no test checks; U5's frontend states are browser-only, said at Build and Test's gate. You chose "Retry with fix" on 2026-11-17. Steps 1–33 stay as built; Steps 34–39 are new and start unchecked. No production code changes, unless Step 37 finds a settings-form control without its Korean accessible name: that fix, in `frontend/src/u5-topics/digest-settings.tsx`, is recorded and gets its own review.

**Decision (proposed with this plan):**

- **L3-1, every changed component holds five to eight tests.** L2-1 split the runner's tests by part and merged nothing. These changed components are still outside five to eight (Build and Test's row `U5:code-generation-plan:testing-contract-strategy-volume`, and Step 24's table in `code-summary.md`): `database/test_schema.py` 10, `repository/test_repository.py` 9, `repository/test_preferences.py` 10, `component/test_topics_logic.py` 13, `component/test_real_composition.py` 18 functions (43 items), `integration/test_http.py` 11 (topics routes 5 and settings routes 6), `operations/test_phase_verdicts.py` 4, and in `frontend/test/u5-topics/`, `announcements.test.tsx` 10, `topics.test.tsx` 14 and `settings-dialog.test.tsx` 13. The fix, in this order: (1) a file that checks several components is split, its tests moved unchanged, one file per component, as L2-1 did; (2) a component that still holds more than eight tests merges its same-rule cases into one test each, keeping every assertion and case (`pytest.mark.parametrize` in Python, where the count is per function; in Vitest one test per rule that asserts every case, since each `it.each` row counts as a test); (3) a component below five gains tests. No assertion or case is dropped or weakened. Merged tests fail less specifically, the trade-off L2-1 turned down for the runner. The alternative, amending U5's instructions to U8's rule (a component above eight carries its reason and is kept), would relax a defined target, which the stage file says is never an acceptable fix; if you want it anyway, choose Request Changes and say so.

**Steps (test-after; every step adds, moves or merges tests, unless Step 37 finds a missing name):**

- [x] **Step 34 — Record the decision and the scope.** Write L3-1 into `code-summary.md` (deviations) and `traceability.json`, and record why the two order-of-work targets and the later-stage one stay as they are, and that the frontend states' remaining gap is browser-only. No source changes. Trace: Build and Test loop-back 3.

- [x] **Step 35 — Tests: one file per component (L3-1 (1)).** Move tests unchanged, with the imports and helpers they use:
  - `integration/test_http.py` into a topics-routes file (5) and a settings-routes file (6);
  - `component/test_real_composition.py` and `component/test_topics_logic.py`, each into one file per component it checks;
  - `frontend/test/u5-topics/topics.test.tsx` and `settings-dialog.test.tsx`, by their describe blocks, into one file for `topics-view.tsx` and one for `digest-settings.tsx`.

  The collect-only and Vitest totals are unchanged by this step. Trace: Testing Contract (strategy volume).

- [x] **Step 36 — API — tests: the inherited defaults through the settings route.** In the settings-routes file of Step 35:
  - (a) An owner with no saved preferences reads the topic settings route and gets `usesDefaults` true, with `en` and `standard`.
  - (b) An owner who has chosen gets `usesDefaults` false, with their choice.

  The settings routes then hold eight tests. Trace: unit-test instructions, required repair (preference inheritance).

- [x] **Step 37 — Frontend — tests: NFR5.1's settings form and populated list.**
  - (a) Vitest with Testing Library, in the `digest-settings.tsx` file of Step 35: the settings form's controls are found by role and Korean accessible name, not by test id.
  - (b) Playwright, in `frontend/e2e/u5-topics-digests/`: with `a11y.ts`'s `axeFindings`, `reflowFindings` and `focusFindings`, a populated topic list has no findings in each of the four theme settings, and the settings form's controls are found by role and Korean accessible name.

  If a control has no Korean accessible name, add it in `digest-settings.tsx` and record the product change for the review. Afterwards NFR5.1's remaining gap is browser-only: the list's and resolve control's live region and names in Chromium, which this plan does not add. Trace: NFR5.1.

- [x] **Step 38 — Tests: merge and add to reach five to eight (L3-1 (2) and (3)).** For each component still above eight after Steps 35–37 (among them `test_schema.py`, `test_repository.py`, `test_preferences.py` and `announcements.test.tsx`, and any file Step 35 split that is still above eight), merge same-rule cases into one test each, keeping every assertion and case. Give `operations/test_phase_verdicts.py` a fifth test, for a verdict case its four do not check, named in the code summary. Trace: Testing Contract (strategy volume).

- [x] **Step 39 — Run, record and review.** For each new test, run it once with the behaviour it awaits withheld (edit, run, restore exactly, confirm the restore by digest), outside the recorded runs, and record the failure it gave; for each merged test, withhold the behaviour of one of its cases the same way and record that it fails. Then run U5's lanes on fresh realms:
  - `coverage`, then `component` on its own fresh realm;
  - `browser` and `database`, each on its own fresh realm;
  - the frontend Vitest lane with coverage, `tsc` and ESLint;
  - Ruff on U5's CI list, and the collect-only command.

  Then update `code-summary.md` (each component's test count before and after, file by file, and L3-1), `traceability.json` and `source-manifest.json`, get a fresh architecture review of this attempt, and run U5's checkpoint. Trace: stage Steps 5 and 6.

When this attempt's approval clears the boxes of Steps 1–33, their work stands: each is ticked again only after Step 39's runs, which exercise it again, have passed, as the project's rule asks.

## Build and Test loop-back 4 (2026-11-22)

Build and Test's fifth run (`construction/build-and-test/test-results.md`: Target Verification Matrix, Outcome and Loop-Back Log entry 4) passed every U5 lane and ruled none of U5's targets Not Met. It left two of U8's targets Not Met for a reason only U5's stored data can remove: `U8:NFR9.2` and `U8:NFR9.2:export-digest-degraded`. A `sending` or `unknown` run whose topic's settings changed after it was prepared cannot be counted from its scheduled time, because U5 records no run's scheduled instant (group U8-A2 in `~/.docsuri-u8/lead-scripts/l2-records/bt5-rung2.json`). You chose "Retry with fix" on 2026-11-22, beyond the bound of three loop-backs: the question stated "Loop-backs used: 3/3" and offered that choice only as an override of the bound. The fix is option 2 of L3-3 in U8's plan (`construction/u8-service-operations-integration/code-generation/code-generation-plan.md:10050-10055`), which reverses the option 1 you chose there: U5 records each run's scheduled instant when it prepares the run, and U8's digest producer counts a re-set run from it. Code Generation is reopened for U5 first and for U8 after it, so this section builds U5's half only: the record, and the contract U8 reads. No U8 target changes its verdict until U8 is rebuilt. Rung 2 put U5's half at about half a day of build, then a re-check review, a fresh checkpoint verification (about 30 minutes plus disk) and your re-approval; $0, local only. Steps 1–39 stay as built; Steps 40–48 are new and start unchecked. Unlike loop-backs 2 and 3, this one changes production code: a new U5 migration, `backend/modules/topics/repository.py`, `preparation.py` and `scheduler.py`, U5's runner chain, and one entry in U8's composed chain (L4-3).

**Decisions (L4-1 and L4-7 are your choices; L4-2 to L4-6 are proposed with this plan, and you can turn any of them down with Request Changes):**

- **L4-1, your choice: where the scheduled instant is recorded.** In both options the value comes the same way: the due read already returns it (`repository.py:385-390`, `d.due_at` beside `d.window_day`), the scheduler holds it and drops it today (`scheduler.py:136-141`), and no U5 table keeps it (`u5_schema.sql:29-43`; `u5_preference_snapshot.sql:2-4`).
  1. **(Recommended) A new column, `topics.digest_run.scheduled_at`, added by a new U5 migration.** The file is `backend/modules/topics/u5_scheduled_instant.sql`, three statements:
     - `ALTER TABLE topics.digest_run ADD COLUMN scheduled_at timestamptz` (nullable, no default, no backfill, no CHECK);
     - `CREATE OR REPLACE FUNCTION topics.guard_preparation_snapshot()`, with the header of `u5_preference_snapshot.sql:6-7` word for word (`RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog`), the same message and ERRCODE '23514' (`:11`), and `scheduled_at` added to both sides of the compared tuple (`:9-10`). A replaced function keeps its owner and its grants and takes every other property from the new statement, so a header written without the search path would lose it and no existing lane would show it; Step 42(a) reads it back;
     - `REVOKE ALL ON FUNCTION topics.guard_preparation_snapshot() FROM PUBLIC`, as `u5_refusal_detail.sql:45` does.

     It adds no table, function, sequence, index or grant. This is the plain reading of "U5 records each run's scheduled instant": a named, typed value, set once, which the database itself refuses to change. What it costs: one file that only U8's manifest claims changes with U5's build (L4-3); U5's chain and its three pinning tests move (Steps 41–42); every environment is set up fresh (U8's tool refuses an older one; U5's and U6's tools would apply the file in place, so for those two the instructions make it a rule); and U6's `coverage` and `browser` phases run again on two fresh U6 environments (L4-5).
  2. **A `scheduledAt` key inside the run's `preference_snapshot`, with no migration.** It changes `repository.py`, `preparation.py`, `scheduler.py` and tests only: no SQL, no chain, no chain pin and no file of another Unit, and U8's verification-run meets the same database as today with U8's files byte for byte. The snapshot is already immutable (`u5_preference_snapshot.sql:9-12`) and its fingerprint reads three keys only (`presentation.py:6-7`), so no fence moves. Against it: the snapshot is defined as the owner's preferences (`backend/modules/personalization/u5_digest_preferences.sql:31-37`), and the instant depends on the topic's settings, not on a preference; the value is JSON text with no type, which U8 would cast inside a required capability's statement, where one malformed value fails the whole read; a run with no snapshot (every row from before the repairs, and the browser fixtures' seeded run) has nowhere to hold it; the operator's preview would show it under "preferenceSnapshot" (`backend/u5_real_delivery.py:251`), in a file whose bytes U8 pins; and only pydantic's default for unknown keys keeps it from the browser, in `backend/modules/topics/http.py`, which cannot be edited to say so without changing `shared/python-consumers.json`, a file U6's manifest claims. It saves little in U6's lanes: U6's host imports U5's (`backend/u6_host.py:22`; `backend/u5_host.py:63-64`), so its coverage and browser phases are still reached. Effort, as an estimate: about the same half day of build, less Steps 41 and 42 and U8's `database` phase; the re-check review, the checkpoint and your re-approval are the same.
  - Turned down for both: a side table or a settings-history table (a new table moves U8's realm privilege pin and U5's own eight-table pin, `tests/u5_topics_digests/database/test_owner_grants.py:230-244`, for nothing a column does not give); a new SQL function U8 calls (it moves the same pin and still needs storage); the database computing the instant at insert, or `prepare_run` computing it (a third copy of the wall-minute rule, after `u5_schedule.sql:25-38` and `backend/modules/operations/producers.py:196-206`, and an instant invented for windows no schedule produced); storing the delivery time instead of the instant (every reader repeats the daylight-saving arithmetic); and the `presentation` or `digest_content` fields (`presentation` is the rendered message, compared whole with a fresh render and submitted as the content of U8's first effect, `backend/u8_topics.py:99-101`; `digest_content` must be the item array, `u5_schema.sql:41-42`).
  - Steps 41–46 are written for option 1. Option 2 is a Request Changes: Steps 41 and 42 and L4-3 go, the instructions' section changes, and the plan is approved again before any build step.
- **L4-2, what is stored, and a run with no value (proposed with this plan).**
  - **The value** is the `due_at` that `topics.next_occurrence` returned for the occurrence whose `window_day` is the run's `window_end` (`scheduler.py:93-95`): the first valid instant at which the owner's confirmed zone reads that day at the topic's delivery time, across a missing or a repeated wall minute (`u5_schedule.sql:25-38`). The scheduler hands it to `DigestPreparation.prepare`, which hands it to `TopicsRepository.prepare_run`, as a new keyword argument `scheduled_at` that defaults to none. Nothing copies the rule.
  - **Why it is the right instant.** The due row is one snapshot (`backend/transactions.py:328`, SERIALIZABLE), and two existing fences hold between that read and the insert: the insert guard refuses a run whose settings revision is no longer the current one (`u5_run_guard.sql:11-14`), so the delivery time cannot have changed, and `expected_preferences` refuses a changed zone or zone confirmation (`repository.py:497-501`). So `prepare_run` accepts an instant only together with `expected_preferences`, and refuses one that has no zone or is not a date-time, with `INVALID_ARGUMENT` on `scheduledAt`. The scheduler always passes both (`scheduler.py:140`).
  - **Set once.** A run that is adopted keeps its own row and its first instant (`repository.py:505-511`, `:530-536`); a run prepared again after a discard is a new row with its own. With the replaced guard, any `UPDATE` that changes the column raises 23514, a change from none to a value included. Without that guard the topics login could change it (`u5_schema.sql:232`), so the guard is what makes "never changed" a fact of the database. No U5 statement updates it.
  - **A run with no value holds SQL NULL, and nothing fills it in later.** That is every run no due occurrence prepared: the operator's on-demand prepare (`scripts/u5_real_delivery.py:267`), the browser fixtures' seeded unknown run and its direct call (`scripts/u5_browser_fixtures.py:274-278`, `:355-357`), a direct `prepare_run` call or a direct insert in a test, U8's among them (calls at `tests/u8_service_operations_integration/integration/test_first_effects.py:177`, `:468` and `component/test_u5_seam_defaults.py:84`; inserts at `component/test_producers.py:232-250`, `:1717-1722`), and every row stored before the file. It follows the file beside it: "NULL marks preserved pre-repair evidence, never an invented historical setting" (`u5_preference_snapshot.sql:1`). Production starts empty and prepares only through the scheduler (`backend/u8_outward.py:371-388`; `backend/u8_topics.py:198-219` overrides the three send hooks only), so production holds no such run. None of those callers changes.
  - **No CHECK on the column.** Not against `created_at`: the scheduler's clock may run ahead of the database's, in U5's realm (`backend/u5_host.py:86-89`) and in U8's after J12's one-day advance, so the instant may be later than the row's creation. Not against `window_end`: a gap can skip a whole calendar date (`u5_schedule.sql:35-36`).
  - **Not shown to the owner.** `RUN_COLUMNS` gains the column (`repository.py:39-42`), so every run row, new or adopted, has the same keys. The owner's two reads keep their explicit column lists (`repository.py:233-242`, `:258-268`) and `http.py` does not change, so no route and no screen shows it. `scripts/u5_real_delivery.py:282` selects it through `RUN_COLUMNS` with its bytes unchanged, and the preview picks its fields by name (`backend/u5_real_delivery.py:238-262`), so the preview does not show it either.
  - **The name** is `scheduled_at`: "scheduled" is BR1.2's word and the word of U8's observability-design § 3.2 line 61.
  - The alternative, an instant worked out for such runs from their window and the topic's current delivery time, invents one, and for a re-set run it is wrong in exactly the case this loop-back fixes. If you want it anyway, choose Request Changes and say so.
- **L4-3, the one file of another Unit: `backend/u8_migrations.py` gains one entry (proposed with this plan; it follows from L4-1's option 1).**
  - **The entry.** `("topics", "backend/modules/topics/u5_scheduled_instant.sql")` in `LATER_UNITS`, after `u5_refusal_detail.sql` (`backend/u8_migrations.py:160`) and before `u6_lifecycle_guard.sql` (`:161`), with a short comment above it: which loop-back added it, and that it was inserted in U6's applied order, not appended, so a realm migrated before it is set up fresh. Nothing else in that file changes. That place is U6's applied order, which the list follows (`:129-130`): U6 builds every environment from U5's `MIGRATIONS` and then its own four files (`scripts/verify_docsuri_u6.py:44`, `:69-75`). The chain's end is U8's own files and is pinned (`tests/u8_service_operations_integration/database/test_u8_schema.py:507`). If the checkpoint or U8's `database` phase fails for a reason that needs any other change in a file of another Unit, the build stops and the finding goes to you; no further file of another Unit changes in U5's build.
  - **Why it is in U5's build.** U5's checkpoint is the Construction Verification Command, U8's `verification-run`, on U8's composed chain. That chain is a written list (`backend/u8_migrations.py:131-165`), and U8's tool compares only U1's part with its source (`scripts/verify_docsuri_u8.py:1686-1694`). Without the entry the realm migrates cleanly and has no such column; J02's first preparation then fails, because the insert names a missing column and neither `prepare_run` nor the scheduler catches that (`repository.py:530-543`; `scheduler.py:142-147`). So U5's checkpoint cannot pass with U8's files as they are today.
  - **What it costs.**
    - U8's approved review goes stale. It already does through `repository.py`, `scheduler.py` and `scripts/verify_docsuri_u5.py`, which U8's manifest also claims, and U8 is reopened next.
    - U5's manifest claims the path too, as U8's claims U5's `repository.py`, so that U5's reviewer reads the entry. Any later U8 edit of that file then stales U5's review, a comment included. Q5's option (b), a new U8 migration, is such an edit. By U8's plan (`:9968`, `:10053`) a stale approved review owes a re-check review, a fresh checkpoint verification (about 30 minutes plus disk) and your re-approval. Line 10053 adds "with U5's lanes run again", written for a change to U5's own code; by the reach rule (L4-5) a U8 edit of this file reaches none of U5's lanes, because none reads `backend/u8_migrations.py`. U5's code would not be rebuilt. Step 41(c) writes the entry's comment in U5's build, so that U8's build has no reason of its own to edit the file. How the engine treats a path two manifests claim was read from the manifests' existing practice, not checked against the engine. Weigh that when you choose Q5 at U8's Plan Approval.
    - It is inserted in the middle of the list, not appended as U8's Build and Test loop-back files were (`backend/u8_migrations.py:167-169`). A U8 realm migrated before this build refuses `migrate` (`scripts/verify_docsuri_u8.py:1725-1727`); every run here sets up a fresh one. Production's tool applies whatever is pending, in chain order, with no such rule (`ops/src/docsuri_ops/production_tool.py:246-263`).
    - U8's realm privilege pin is read as unmoved: a column with no grant of its own gives no row (`scripts/verify_docsuri_u8.py:1907-1911`), the pin holds 51 column rows and none in `topics`, and a replaced function keeps its two rows (`scripts/u8_realm_privileges.txt:481-482`). The tool's comment lists a new column as row-moving (`scripts/verify_docsuri_u8.py:1858-1859`); the query shows that only a column grant is. This is a reading, not a run, so Step 48 runs U8's `database` phase once. If the pin does move, that is recorded and owed to U8's plan (the pin file and its digest are U8's); it does not block U5's checkpoint, which does not read the pin.
  - **U6:** no file U6's manifest claims changes, so U6's approved review stays. `http.py` (pinned by `shared/python-consumers.json`) and `backend/u5_host.py` do not change.
  - **Kept bytes.** `backend/u5_policy.py`, `backend/modules/topics/delivery.py`, `backend/u5_real_delivery.py`, `backend/.coveragerc.u5` and `frontend/vitest.u5-topics.config.ts` do not change: U8's tests pin their bytes (`tests/u8_service_operations_integration/built_files.py:26-41`, `:184`). Step 40 takes their SHA-256, and `http.py`'s and `u5_host.py`'s, before the first edit, and Step 48(e) after the last.
  - Turned down:
    - U5 code that looks for the column and writes without it when it is missing (it hides a composition error behind a branch no lane would run);
    - U8's chain reading U5's list (U5's list holds `u5_lifecycle_tables.sql`, which the composed chain leaves out, `backend/u8_migrations.py:236-245`);
    - appending the entry after U8's own files. It would keep earlier U8 realms' applied files a prefix of the chain (`backend/u8_migrations.py:167-169`). But it puts a U5 file after U6's and U8's, against the list's rule of U6's applied order (`:129-130`), and it needs a new tuple and a changed `CHAIN` line, because the end of `U8_FILES` is pinned (`test_u8_schema.py:507`). Production starts empty and every realm is set up fresh, so the prefix protects nothing today;
    - reopening U8 before U5 (your order keeps U8's checkpoint last, over every Unit's final code).
- **L4-4, the tests: five to eight per changed component (proposed with this plan).** Counted as L3-1 counts them, by test functions per file:
  - the additive preparation evidence, `database/test_preference_schema.py`: 6, then 7;
  - a run's scheduled instant in `TopicsRepository`, a new file `repository/test_scheduled_instant.py`: 8. `repository/test_repository.py` and `repository/test_preferences.py` already hold eight each and gain nothing;
  - the due path, `component/test_topics_scheduler.py`: 5, then 8. `DigestPreparation.prepare` only passes the instant on, so it is counted with the scheduler, whose three new tests reach the store through it; Step 48 shows them fail when the preparation drops the instant;
  - the chain upgrade, the applied migration bytes and the runner's bindings (`database/test_chain_upgrade.py`, `database/test_migration_digests.py`, `operations/test_runner_bindings.py`): 5 each, extended under their own names, none added;
  - the composed chain's one entry, `backend/u8_migrations.py`: no U5 test. Step 41's read, which needs no realm, fails when the entry is missing or misplaced. U8's `database/test_composed_chain.py` (15 functions), run once in Step 48(d) on a migrated U8 realm, shows that the composed chain applies with the file. None of its tests fails if the entry is missing, because it compares the realm's receipts with the same list that built the realm (`:69-75`); the checkpoint's J02 does fail then. The file is counted in U8's volume, and a test comparing U8's list with U5's `MIGRATIONS` is owed to U8's plan (L4-6).

  That is 12 new test functions, 18 collected items, and the collect-only total goes from 331 to 349 if every test is built as listed. No test reads the column on the browser fixtures' seeded run or on the operator's on-demand run: both reach the store by paths the database test and repository test 2 check, and the instructions' required-cases row claims neither. If you would rather give the preparation a test file of its own, choose Request Changes and say so. As an estimate it is about an hour more; it would need five tests for a method that only passes one argument on, so the count would rest on near-duplicate cases.
- **L4-5, the lanes follow the reach rule (U8's L2-18): a lane runs again only when a changed file reaches it (proposed with this plan).**
  - Runs in Step 48: all of U5's lanes, each test phase on its own fresh realm. U5's frontend lanes run too, although no frontend file changes, so that the boxes of the earlier frontend steps are ticked again only after their own runs.
  - U6, with U6's own tool and no U6 file changed: `coverage` on one fresh U6 environment and `browser` on a second, the two environments U6's own instructions and workflow use (U6's `unit-test-instructions.md:250-251`; `.github/workflows/u6-approved-export.yml:141-147`). Every U6 environment is built from U5's `MIGRATIONS`, and U6's host imports the changed preparation and scheduler.
    - Together the two phases run every U6 test that needs a migrated environment. `coverage` runs the database, repository, component, integration and operations folders in one pass (`scripts/verify_docsuri_u6.py:1120`), the operations folder holding the test that reads every `.py` under `backend/` (U8's L3-12). So those phases are not run a second time as lanes of their own.
    - This is narrower than the words of U8's plan (`:10054`, "every U6 phase run on a migrated environment runs again") and than Build and Test's run 5, which ran `component` and `integration` as lanes of their own before `coverage` on one environment (591 and 48 tests, `~/.docsuri-u8/lead-scripts/final-lanes/run-20261119-103747-52341/`, steps 43–45). U6's workflow says a repeat spends the fixture quotas again (`:141-143`). Build and Test runs them again. If you want them here as well, say so at Plan Approval.
  - U8: its `database` phase once, on a fresh U8 realm, for the composed chain and the privilege pin (L4-3); then the checkpoint's `verification-run` on another. Every other U8 lane is reached too, through the chain and through `backend/.coveragerc.u8:111-112`, which measures `scheduler.py` and `repository.py`. Those run in U8's reopened build, on U8's final source, and are not run twice.
  - These stand, with the reason written down: U1's to U4's and U7's lanes (no file they reach changes), U6's `frontend` phase, type check and ESLint (no frontend file changes), the shared contract checks (no pinned file changes) and next-app's audit (no lockfile changes).
  - Disk. This loop-back sets up about fifteen environments, one at a time for each Unit's tool. In run 5 the realm set up after realm B started with 23.56 GiB free (`test-results.md`, "Disk and swap"), against J09's 20 GiB guard and the 22 GiB working floor before a U8 `setup`. The free disk is read before U8's `database` realm is set up and again before the checkpoint's (unit-test instructions), and the checkpoint may need your approval to free disk first.
  - Turned down: running every U8 lane here as well (U8's files change next, so those runs would be repeated), and leaving U8's `database` phase to U8's build (the privilege-pin reading would then reach U8's plan as a reading).
- **L4-6, the contract U8 consumes, and what is owed to U8's plan (proposed with this plan).**
  - **The contract.** `topics.digest_run.scheduled_at`, a `timestamptz`: the due instant of the occurrence the run was prepared for, set once at insert and never changed. It is not NULL for every run U5's scheduler prepared, whatever happens to the topic's settings or the owner's zone afterwards, and whatever state the run is in. It is NULL for a run no due occurrence prepared and for a row older than the file; production cannot hold one. It may be later than the run's `created_at`. U8 reads it in its own statement under the topics login, as it reads `state` and `updated_at` today (`backend/modules/operations/producers.py:188-212`, `:251`), and writes nothing. For a NULL row U8 states its own fallback; today's arms of `DIGEST_RUNS` are that fallback.
  - **Owed to U8's plan, recorded by Step 47, with the privilege pin's result added by Step 48:** the producer's statement and its comments; the M and P cases of U8's Step 146 and a NULL case for the fallback; the withdrawal of U8's correction 184 and record 113; U8's coverage of the new lines in the two files its report measures; U8's records of a chain entry inserted mid-list; that both manifests now claim `backend/u8_migrations.py`, so any further U8 edit of it stales U5's review (L4-3); that nothing compares U8's copy of U5's files with U5's `MIGRATIONS`, so a missing entry fails only in a journey; that every U8 environment set up before U5's build is archived and set up again, none migrated in place; and that U6's `component` and `integration` phases were not run as lanes of their own in U5's build (L4-5).
  - Turned down: a U5 repository read for pending runs that U8 calls. It would move U8's fallback rule and its two 24-hour counts into U5, split one statement's snapshot into two reads, and make U5's build larger for the same answer.
- **L4-7, your choice: U5's browser-only checks (U5-C2) are not built here. (Recommended: leave them out here.)** Build and Test's log leaves the 26 browser-only targets to the gate unless you add their checks at Plan Approval. U5's three are `U5:NFR5.1` (the list's and the resolve control's live-region messages and the Korean names of their buttons), the frontend states and the defaults label of the preference inheritance: their remaining clauses ran only in jsdom (`test-results.md:184`). Loop-back 3 already checked the populated list and the settings form's Korean names in Chromium and the defaults marker through the settings route. Left out, the three targets stay Unverified and are said at Build and Test's gate again. Adding them is about half a day in `frontend/e2e/u5-topics-digests/`, at low to moderate risk: a button without its Korean name would be a product fix with its own review. Rung 2 expects all three Met afterwards. If you want them in this loop-back, choose Request Changes and say so; the plan then gains their steps before any build step.

**Steps (test-after: each layer is implemented, then its tests are written and run; the API and frontend layers do not change, and Step 48's lanes run their tests again):**

- [x] **Step 40 — Record the decisions and the scope.** Write L4-1 to L4-7 into `code-summary.md`, in a new first section for this loop-back, with your choice of "Retry with fix" beyond the bound and the reversal of L3-3's option 1, and into `traceability.json`. Record the design correction: `functional-design/entities.md`'s DigestRun gains `scheduledAt` (a timestamp, optional: the due instant of the occurrence the run was prepared for; set once; absent for a run no schedule prepared), and the approved file is not edited. Record what this build does not show:
  - no U8 target changes until U8 is rebuilt;
  - the bounded real send that Steps 13 and 14 name is not repeated, because this plan authorizes no external message. Its evidence is of the source before this change.

  Take the first SHA-256 reading of the seven kept files of L4-3 (unit-test instructions, loop-back 4) before any edit, and record it. Run the collect-only command before any new test is written and record its count and time (unit-test instructions, loop-back 4); note the time each of Steps 41–46 is finished, for Step 47. Files: `code-summary.md`, `traceability.json`. No source changes. Verification: L4-1 to L4-7, the design correction and what this build does not show are in `code-summary.md` and `traceability.json`, and the first reading of the seven kept files and the first collect-only count are in the code summary, taken before any edit. Trace: Build and Test loop-back 4.

- [x] **Step 41 — Data model / database — implement.**
  - (a) Add `backend/modules/topics/u5_scheduled_instant.sql`, the three statements of L4-1's option 1, with a first-line comment that NULL marks a run no schedule prepared and never an invented instant. The replaced function keeps the header `RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog`, the message 'preparation snapshot is immutable' and ERRCODE '23514', and compares `scheduled_at` on both sides of the tuple. No applied file changes.
  - (b) Append `("topics", "backend/modules/topics/u5_scheduled_instant.sql")` to `MIGRATIONS` in `scripts/verify_docsuri_u5.py`, after `u5_refusal_detail.sql` (`:76`).
  - (c) **The one file of another Unit (L4-3):** add the same entry to `LATER_UNITS` in `backend/u8_migrations.py`, after `:160`, with its short comment above it. Nothing else in that file changes.

  Files: `backend/modules/topics/u5_scheduled_instant.sql` (new), `scripts/verify_docsuri_u5.py`, `backend/u8_migrations.py`. Verification: the file applies in order on a fresh U5 realm (`setup`, `migrate`); Step 42's tests pass; and for (c) the read that needs no realm (unit-test instructions, loop-back 4) finds the entry once, between `u5_refusal_detail.sql` and `u6_lifecycle_guard.sql`, under the `topics` owner. That the composed chain applies with it is shown by Step 48(d) and the checkpoint, not here. Trace: FR1.2; BR1.2, BR2.4; L4-1, L4-3.

- [x] **Step 42 — Data model / database — tests.**
  - (a) New, in `tests/u5_topics_digests/database/test_preference_schema.py`: `test_a_runs_scheduled_instant_is_set_once_and_never_changes`. Through the topics login, on two topics: a run inserted with an instant refuses a change to another instant and to none; a run inserted without one holds none and refuses a later instant; a state move leaves both as they were. Then, read from `pg_proc`: the replaced function still has `search_path=pg_catalog`, is not a definer function, and is executable by the topics login and its owner only.
  - (b) `database/test_migration_digests.py`: `U5_CHAIN` gains the new file with the SHA-256 of its built bytes, after `:91-95`, and the `newest-repair` case (`:133`) names the new file.
  - (c) `database/test_chain_upgrade.py`: `REPAIRS` gains the file (`:34-41`); the prose says seven repairs and 66 migrations (`:1`, `:7`, `:10`, `:328`); `test_the_upgrade_keeps_every_pre_repair_row_and_receipt` also reads the new column on the eight old runs and finds none set (`:317`, `:349`); `test_old_rows_keep_their_constraints_and_guards` also tries to set an old run's instant and is refused (`:371`).
  - (d) `operations/test_runner_bindings.py`: the list after `u5_run_guard.sql` gains the file (`:49-56`). It is the runner's chain test, extended here because the same edit moves it.

  Files: those four test files. Verification: `--phase database` on a fresh U5 realm passes, 34 tests expected (33 after loop-back 3 and this one; the actual count is recorded), and the three realm-free chain tests run directly (unit-test instructions, loop-back 4). Trace: Step 41; BR1.2; required repair verification (migration and ownership).

- [x] **Step 43 — Repository — implement.** In `backend/modules/topics/repository.py`: `RUN_COLUMNS` gains `scheduled_at` (`:39-42`); `prepare_run` takes the keyword argument `scheduled_at=None` (`:465-474`), refuses with `INVALID_ARGUMENT` on `scheduledAt` an instant that has no zone, is not a date-time or comes without `expected_preferences`, beside its other argument checks (`:481-486`), and writes the value in its insert (`:515-528`). Nothing else in the file changes: the adoption paths, the owner's two reads and every state move stay as they are. Files: `backend/modules/topics/repository.py`. Verification: Step 44's tests. Trace: BR1.2, BR2.4; L4-2.

- [x] **Step 44 — Repository — tests.** New file `tests/u5_topics_digests/repository/test_scheduled_instant.py`, eight tests on the real realm, each handing in an instant that differs from the window's day at the topic's current delivery time, so that a reading worked out from the current settings cannot pass by coincidence:
  1. `test_a_prepared_run_keeps_the_scheduled_instant_it_is_handed`: the returned row and a fresh read hold it, and an instant given at another offset reads back as the same instant.
  2. `test_a_run_prepared_without_an_instant_holds_none`: not its creation time, and not its window's day at the delivery time.
  3. `test_an_instant_that_is_naive_mistyped_or_unfenced_is_refused`, three cases: no zone; a string; given without `expected_preferences`. Each is `INVALID_ARGUMENT` on `scheduledAt`, and no run is created.
  4. `test_an_instant_from_a_due_read_made_before_a_zone_change_is_refused`: the owner's zone changes after the preferences were read; the preparation is refused `CONFLICT` and no run holds the instant.
  5. `test_a_refire_adopts_the_run_and_keeps_its_first_instant`: a second preparation of the window with another instant adopts the run and changes nothing.
  6. `test_a_later_change_leaves_a_started_runs_instant`, three cases: the owner saves a new delivery time; changes the cadence to weekly; changes the zone. Each change is made after the send started, through the owner's real save with its revision, and the instant is read again while the run is `sending` and after it turns `unknown`. This is the run U8-A2 is about.
  7. `test_no_state_move_changes_the_instant`: prepared, sending, unknown and the owner's resolution, and a prepared run that is discarded, each read through the topics login with the states U8's statement names.
  8. `test_a_run_prepared_again_after_a_discard_holds_its_own_instant`: the discarded row keeps the first instant and the new row holds the second.

  Files: `tests/u5_topics_digests/repository/test_scheduled_instant.py` (new). Verification: `--phase repository` on a prepared U5 realm. Trace: Step 43; BR1.2, BR1.3, BR2.4; U8's NFR9.2 (observability-design § 3.2 line 61), for the contract.

- [x] **Step 45 — Business logic — implement.** `DigestPreparation.prepare` takes `scheduled_at=None` and passes it to `prepare_run` (`backend/modules/topics/preparation.py:31-42`). `TopicsScheduler._evaluate_due` passes `topic["due_at"]`, from the same due row that gave the window and the preferences (`backend/modules/topics/scheduler.py:136-141`). No other caller changes. Files: `backend/modules/topics/preparation.py`, `backend/modules/topics/scheduler.py`. Verification: Step 46's tests. Trace: BR1.2; L4-2.

- [x] **Step 46 — Business logic — tests.**
  - (a) Move the calendar helpers of `component/test_schedule_preferences.py` (`run_clock`, `utc_date_after`, `next_transition`, `wall_exists`, `first_valid_instant`, `schedule` and `occurrence`, with `NEW_YORK` and `FAR_AHEAD`), unchanged, into a new helper module `tests/u5_topics_digests/calendar_flow.py`, beside `topics_flow.py`. That file imports them, and its seven tests do not change.
  - (b) Three tests, last in `tests/u5_topics_digests/component/test_topics_scheduler.py`, each through `TopicsScheduler.run_once` on the real realm, each comparing the stored instant with one worked out from the zone database, not from the code under test:
    1. `test_a_daily_run_records_its_occurrence_not_the_pass_clock`: the pass runs some minutes after the due minute.
    2. `test_a_late_pass_records_the_occurrence_it_catches_up`, two cases: a daily topic whose pass runs three days late, and a weekly topic whose pass runs on the next local day. The run's window ends on the delivery day and its instant is that day's.
    3. `test_a_run_due_in_a_clock_change_records_the_first_valid_minute`, two cases in America/New_York: the day with no 02:30, where 03:00 is recorded, and the day with two 01:30s, where the first is recorded. In each case the pass runs later than the recorded instant: ten minutes after 03:00 on the spring day, and after the second 01:30 on the autumn day, so that a pass's clock handed in as the instant cannot equal it.

    The new tests change an owner's zone through `calendar_flow.schedule`, as the calendar tests do, and none puts it back. Every later test that takes an owner fixture starts from the fixtures' reset to UTC (`tests/u5_topics_digests/conftest.py:83-87`), which stamps a new zone boundary; a test that takes none meets the zones as `test_schedule_preferences.py` already leaves them today.

  Files: `tests/u5_topics_digests/calendar_flow.py` (new), `component/test_schedule_preferences.py`, `component/test_topics_scheduler.py`. Verification: `--phase component` on a prepared U5 realm passes, 141 tests expected (136 after loop-back 3 and these five items; the actual count is recorded). Trace: Step 45; BR1.2; required repair verification (timezone).

- [x] **Step 47 — Records.** In `code-summary.md`:
  - each changed component's test count before and after, file by file;
  - the order of work for Steps 41–46: each layer's implementation finished before its tests were written, with times, and the collect-only run made before the first new test;
  - the contract of L4-6, word for word;
  - the list owed to U8's plan;
  - that Step 41(c) changed a file only U8's manifest claimed.

  In `traceability.json`: a `loopback_4_evidence` block, and BR1.2 traced to the new migration. In `source-manifest.json`: the four new claims, `backend/modules/topics/u5_scheduled_instant.sql`, `tests/u5_topics_digests/repository/test_scheduled_instant.py`, `tests/u5_topics_digests/calendar_flow.py` and `backend/u8_migrations.py`. Files: those three records. Verification: every path this section changed is claimed, and the counts equal those of a collect-only run made on the source as Step 46 left it. Trace: Testing Contract (strategy volume, methodology); stage Step 5.

- [x] **Step 48 — Run and record.**
  - (a) **Withheld checks, outside the recorded runs.** Each new test and each extended test runs once with the behaviour it awaits withheld (edit, run, restore exactly, confirm the restore by SHA-256), and the failure it gave is recorded: the migration with old rows filled in and its guard not comparing the instant; the replaced guard written without its fixed search path; the old chain; one changed byte in the new file; `prepare_run` not storing the instant; `prepare_run` stamping the present time and refusing nothing; `prepare_run` without its preference fence; the scheduler handing in the pass's clock; and the preparation dropping the instant (unit-test instructions, loop-back 4, W1a, W1b and W2 to W8). A test whose withheld run has not happened is recorded as not run.
  - (b) **U5's lanes, on the final source, each test phase on its own fresh realm:** `database`, `repository`, `component`, `coverage` under the unchanged 80% floor, and `browser`; then the frontend Vitest lane with coverage, `tsc` and ESLint; Ruff on U5's CI list and on `backend/u8_migrations.py`; `test_archive_expiry.py`; and the collect-only command.
  - (c) **U6's lanes (L4-5):** `coverage` on a fresh U6 environment and `browser` on a second, with U6's own tool.
  - (d) **U8's `database` phase (L4-3, L4-5)** on a fresh U8 realm, archived before the checkpoint's realm is set up. The free disk is read before its `setup` (unit-test instructions). It shows that the composed chain applies with the new file, and it reads the privilege pin's test; it does not show that the entry is present, which Step 41's read and J02 do. Its result is recorded either way. A failure there is recorded with the test and what it showed, and goes to you before the checkpoint: a moved privilege pin is owed to U8's plan, and anything else may mean the chain entry is wrong.
  - (e) Compare the SHA-256 of the seven kept files of L4-3 with the readings Step 40 took before the first edit.

  Then add the runs to `code-summary.md` and `traceability.json`. Files: `code-summary.md`, `traceability.json`. Verification: every U5 and U6 lane above exits 0 with no skip, the kept files' digests are equal, and U8's `database` phase has its recorded result, with `database/test_composed_chain.py` passing in it. Trace: stage Step 5.

  This box is ticked with that record, before the review and the checkpoint, as Step 33's and Step 39's were (`code-summary.md`, "The plan's boxes in this attempt"): the engine routes a Unit to completion only once every box is ticked, and an edit to the plan after the review would void its receipt. The fresh architecture review of this attempt and U5's checkpoint follow as the stage's own handoff (stage Step 6). The checkpoint is the Construction Verification Command, U8's `verification-run`, run by AI-DLC's checkpoint verifier on a fresh U8 realm after `setup`, `migrate` and `fixtures --corpus skip`. If either fails, the Unit returns to Code Generation and this box with it.

When this attempt's approval clears the boxes of Steps 1–39, their work stands: each is ticked again only after Step 48's runs, which exercise it again, have passed, as the project's rule asks. Steps 14, 15, 27, 33 and 39 ask for a review and a checkpoint of their own attempts; those passed, and this attempt's review and checkpoint stand in for them. The bounded real send of Steps 13 and 14 is not repeated, because this plan authorizes no external message: its evidence is of the source before this change, and `integration/test_real_delivery.py::test_operator_tool_prepares_and_previews_without_sending` runs the operator's prepare and preview on the final source in the `coverage` lane, as contract evidence only.

## Requirement and finding traceability

| Requirement or finding | Repair steps |
|---|---|
| FR1.1 | 1, 7, 8, 12, 14; retain existing follow/reactivation behavior |
| FR1.2 | 3–12, 14 |
| FR1.3 | 3–8, 12, 14; retain eligibility/watermark filtering |
| FR1.4 | 3–14 |
| FR1.5 / FR1.6 | 5–10, 12–14 |
| NFR1 / NFR2 | 3–10, 12–14 |
| NFR3 | N/A for U5: specifically Notion credentials in U6; inherited email secrets still protected |
| NFR4 | 3–10, 12–14 |
| NFR5 | 9–14 |
| NFR6 | 1, 7, 8, 13, 14 |
| R-01 | 2, 13, 14 |
| R-02 | 11, 12, 14 |
| R-03 | 3, 4, 14 |
| R-04 | 3–12, 14 |
| R-05 | 3–12, 14 |
| R-06 | 1, 3–10, 13, 14 |
| Browser fixture backlog | 12, 13, 14 |
| Build and Test loop-back 1: the 4 Not Met and 20 not fully checked U5 targets; decisions L1-1 to L1-4; the dark-theme contrast and date-pinned test it found | 16–27 |
| Build and Test loop-back 2: U5's test volume (Not Met) and NFR5.1's two unchecked clauses; decision L2-1 | 28–33 |
| Build and Test loop-back 3: U5's test volume (Not Met), NFR5.1's settings-form names and populated list, and the inherited-defaults marker through the settings route; decision L3-1 | 34–39 |
| Build and Test loop-back 4, beyond the bound by your choice: U8-A2, U5's half (U8:NFR9.2 and U8:NFR9.2:export-digest-degraded, Not Met in run 5): each run's scheduled instant recorded when it is prepared (FR1.2; BR1.2, BR2.4); decisions L4-1 to L4-7 | 40–48 |

## Completion and evidence boundaries

No current test result is relabelled as a repaired-source result. Preserve 81-test
coverage and the failed browser proof as baseline evidence, then collect fresh
results after implementation. The 80% aggregate coverage floor and any existing
stricter targets remain intact; report per-file gaps honestly. Previously quoted
473/356 counts are historical references, not assertions about current suites.

The plan authorizes local code/configuration repair and verification. It does
not authorize paid resources, provider-account creation, unsolicited external
messages, data migration, production deployment, or promotion to `main`.
Prepare the exact external demonstration for separate explicit send authorization.
A real adapter tested with a fake client is contract evidence, not real delivery.
