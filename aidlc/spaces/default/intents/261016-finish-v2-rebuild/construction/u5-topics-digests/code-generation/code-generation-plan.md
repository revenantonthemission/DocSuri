# U5 — Topics and digests · Code generation plan

Unit: `u5-topics-digests`. Branch: `feature/u5-topics-digests`. Scope: `docsuri-v2-finish` (express base), test-after, standard strategy; existing suites stay green.

## Summary

- Builds: repairs for all six U5 review findings and browser fixture isolation, completing inherited preferences, owner-timezone scheduling, and truthful real/local email delivery without dropping existing digest capabilities.
- Touches: Topics, Personalization, the existing account email seam, shared contracts and targeted migrations, U5 assembly/configuration, Korean settings UI, unit tests, browser fixtures, verification scripts, and operational instructions.
- Tests: retain the existing 81 backend checks; add five to eight checks per changed component, real-store/API tests, and at least four mounted browser journeys; preserve existing coverage floors and verify inherited behavior.

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
  "input_sha256": "sha256:feb040c7898e5b924695da36d1e6633e1d2cad660b370bc4d3d863451b5e0cf9",
  "contract_sha256": "sha256:0b3bdbd990d6def665d447995282ba760f054c761c3ccf40dbbb9fc1b114553b"
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

- [ ] **Step 12 — Frontend behavior — test after implementation.**
  Extend scoped Vitest/RTL tests, then run at least four mounted journeys:
  follow/settings/unsubscribe, scheduler/local-sink delivery, explicit unknown
  resolution, and the promised empty-digest state. Include owner preference
  propagation and truthful no-send empty outcomes. Keep the existing timeout and
  send limits. Trace: FR1.1–FR1.5; NFR5.1; R-02 and browser failure.

- [ ] **Step 13 — Environment/build configuration and integration evidence.**
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

- [ ] **Step 14 — Documentation, fresh review and completion evidence.**
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
