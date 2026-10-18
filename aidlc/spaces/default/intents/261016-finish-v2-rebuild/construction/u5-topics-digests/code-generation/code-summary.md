# U5 code summary — topics & digests

Date: 2026-10-18 (Asia/Seoul)
Unit: u5-topics-digests. Branch: `feature/u5-topics-digests`. Contract: AIDLC-TESTING-CONTRACT `sha256:0b3bdbd990d6def665d447995282ba760f054c761c3ccf40dbbb9fc1b114553b` (methodology test-after, 80% line floor, existing suites stay green).

## What was built

TopicsDigests joins the one assembled release as an embedded module: topic
follow/unsubscribe/reactivate, per-topic digest settings with revision-checked
saves, a bounded scheduler (due evaluation, idempotent preparation, single send
attempt per pass, orphan sweep, evidence-based reconciliation), digest email
through the built accounts seam, and lifecycle participation under the shared
coordinator contract.

- **Schema (Step 3)** — `topics` owner schema: `followed_topic` (identity
  immutable, one row per (account, normalized key), reactivation reuses the
  row), `digest_settings` (weekly⇔delivery-day CHECK, monotonic revision),
  `digest_run` (state machine `prepared→sending→sent|failed|unknown` plus
  `empty|discarded`; window uniqueness excluding discarded; single-flight
  partial index; unknown-pause and sending-age indexes; deterministic empty
  content), `delivery_outcome`, `send_log_entry`, `topic_delivery_watermark`,
  `lifecycle_evidence`, nine guard functions with triggers, grants mirroring
  the research owner (no DELETE, no cross-schema writes).
- **Repository (Step 5)** — `TopicsRepository`: every owner path rechecks live
  authority (`guard`), worker units run in bounded system transactions,
  multi-step flows are atomic (settings save discards prepared runs BR1.3;
  send start enforces active/consent/pause in the checked transition
  BR3.1/3.2/4.2; terminal sends append the watermark from the run's own
  content BR2.2; reconcile applies the watermark exactly like a direct send).
- **Business logic (Step 7)** — `TopicsService` (normalized keys, shaped
  payloads, resolve that names its assumption), `DigestPreparation`
  (eligible-corpus selection in the inclusive window, watermark excluded,
  bounded by policy), `DigestDelivery` (single send per attempt through the
  additive `send_digest_email` seam; transport facts land before the outcome,
  so a crash leaves an unknown that evidence can still reconcile; unobserved
  transports pause as unknown; failures record a plain reason and are never
  re-sent), `TopicsScheduler` (sweep → reconcile → consent-stop drop → due
  evaluation → send, each bounded), `TopicsDigestsLifecycleParticipant`
  (withdraw unsubscribes + drops queued work; erase removes every digest fact;
  evidence written by the shared `apply_owner_effect` writer).
- **HTTP (Step 9)** — literal REST `/api/v2/topics…` on the owned HTTPS origin
  with the shared error vocabulary (`DUPLICATE→CONFLICT`, revision
  `CONFLICT→STALE_REVISION`), owner checks on every access, foreign and
  nonexistent identifiers indistinguishable (404).
- **Frontend (Step 11)** — `src/u5-topics/**`: TopicsView (h1, SWR with a 4s
  pipeline refresh), FollowedTopicsSection/TopicList/TopicRow
  (TopicSummary with icon+text last-digest indicator, DigestSettingsLink,
  ResolveUnknownControl, UnsubscribeButton), FollowTopicAction,
  DigestSettingsForm (cadence/time/day/window, inherited-level note,
  acknowledged save states, stale-revision reload offer — never a blind
  retry), ConfirmationDialog (focus trap, Escape, focus return), Korean
  labels throughout. Transport gained `put`/`del` (DELETE carries CSRF without
  a body) and a topics route pattern in `safeApiPath`.
- **Environment (Step 13)** — `scripts/verify_docsuri_u5.py` (phases
  setup/migrate/fixtures/archive-owned/{database,repository,component,
  integration,operations,coverage}/frontend/browser/serve/teardown),
  `scripts/serve_docsuri_u5.py`, `scripts/u5_browser_fixtures.py` (two
  synthetic accounts, two dated papers, and a guaranteed unresolved-unknown
  fixture case for the resolve journey), `backend/.coveragerc.u5`,
  `frontend/{vitest.u5-topics.config.ts,tsconfig.u5-topics.json,
  playwright.u5-topics.config.ts}`, scoped CI lane
  `.github/workflows/u5-topics-digests.yml`.

## Recorded verification evidence before environment recovery

The following results predate the expiry-preservation repair described below.
The old realm is expired and these results do not verify the changed source or
the current completion checkpoint.

Realm `docsuri-u5-3617b2afe7ed52de` (`/tmp/docsuri-u5-run/environment.json`,
LABEL `dev.docsuri.u5.run`, ports 15489/18089, policy `u5-synthetic-v1`):

- `--phase setup` → base-installed; `--phase migrate` →
  `{"state": "u5-migrated", "migrationCount": 59}` (8 base schemas + 22
  amendments + 29 migrations including the appended correction below).
- `--phase database` → 10 passed; `--phase repository` → 9 passed (re-run
  twice against accumulated state); `--phase component` → 11 passed (twice);
  `--phase integration` → 5 passed (twice, mounted TestClient over the real
  realm); `--phase operations` → 15 passed; `--phase coverage` → 50 passed,
  **87.86%** line coverage against the 80% floor.
- `--phase frontend` → 14 Vitest/RTL tests passed; `--phase browser` → 3
  mounted Playwright journeys passed (twice): follow → settings → unsubscribe;
  follow → scheduler pass → local-sink delivery with the indicator updating;
  the resolve control closing a real unresolved unknown.
- Local-sink delivery evidence: the scheduler journey's digest send is recorded in
  `topics.send_log_entry` with `path_kind='local-sink'` and acknowledged
  transport facts (`acknowledged_at`), and the delivery outcome row records
  `sent`. No send anywhere claims `pathKind='real'`: the synthetic policy is
  synthetic-only, so the capability stays truthfully degraded
  (`u5-synthetic-topics`, `synthetic-only: true`).

## Expired-environment recovery checks

Normal execution correctly refuses the original expired realm. Archival formerly
used that execution loader too, preventing preservation after expiry.
`LocalProfile.preservation_identity` now validates custody, identity and finite
original timestamps without granting an executable profile. `archive-owned`
retains the exact resource, private-file, idle-process and active-database-client
checks before stopping and preserving the owned resources. It does not extend
expiry, reset quotas or delete the database volume.

The new archival regression suite contributes 31 checks. Together with the
existing U4 profile-binding suite, the focused run passed **48 tests** with one
warning. Ruff on the three changed files and `git diff --check` passed.

Actual archival preserved the old files and database volume without changing
expiry. Fresh Colima realm `docsuri-u5-bbf3b6a7f306e989` then applied 59 migrations
and loaded two synthetic accounts and two papers. The coverage phase passed
**81 tests, zero failures/errors/skips, 87.87% aggregate coverage** against the
unchanged 80% aggregate gate. The first attempt was blocked before tests by the
sandbox's denial of `ps` memory supervision; the identical command passed with
scoped escalation. Both attempts' evidence was retained. The current browser
completion checkpoint is still required; the original realm's browser counts
above remain historical evidence.

## Decisions and deviations

1. **Appended corrective migration.** The database probes caught the
   chronology gate firing on same-window duplicates (`<=` instead of `<`),
   masking the unique index's `UniqueViolation` with a `CheckViolation`. The
   runner refuses changed applied migrations ("append a new migration"), so
   `backend/modules/topics/u5_run_guard.sql` (CREATE OR REPLACE with the
   strictly-earlier gate) was appended to MIGRATIONS — the realm stays
   append-only and fresh realms apply both files.
2. **Lifecycle chain composition.** `u2_controls.sql` was NOT imported: it
   collides with `u3_session_authority.sql` (both `ALTER accounts.session ADD
   COLUMN purpose` with different CHECK sets) and would flip the inherited
   `guard_session` semantics. Instead `u5_lifecycle_tables.sql` carries the
   lifecycle DDL verbatim, the canonical `u2_lifecycle_effect.sql` /
   `u2_lifecycle_action.sql` are imported, and `u5_lifecycle_guard.sql`
   mirrors the owner-grants for `topics`. `accounts.entry_receipt` comes from
   the U1 amendment `local_entry.sql`, already in the base.
3. **SCHEMAS vs OWNERS (plan Step 13 wording).** The plan said "SCHEMAS
   extended with topics"; the shipped runner keeps `SCHEMAS` as the frozen U1
   receipt-bearing base and adds `topics` through `OWNERS` + MIGRATIONS — the
   same effect with no topics receipt table. Recorded as the deliberate
   resolution of the plan conflict.
4. **Coverage denominator.** `backend/.coveragerc.u5` measures the production
   surface (topics modules, policy, host, serve, fixtures) at 87.86%; the
   verification runner itself is excluded. U4 measured its runner because its
   operations suite (≈1,200 lines) exercised it; U5's runner is the
   measurement harness — self-measuring it needs nested coverage data files —
   and its safety boundaries are locked by the 15 operations tests. Recorded
   as the deliberate U5 deviation from the U4 include shape.
5. **Scheduler paging.** The first paging draft (oldest-first page over active
   topics) starved new topics once the persistent realm accumulated actives.
   Due-ness moved into the SQL read (`due_topics(zone, limit)`) with a
   separate `consent_stopped_runs` sweep, so every returned row is work the
   pass can attempt.
6. **Rolling windows.** Windows are the settings' rolling bound
   (`[today-(days-1), today]` in the one stated zone `Asia/Seoul`); the
   watermark, not window tiling, prevents repeats. This makes BR3.3's clause
   ("a failed window's content is re-delivered by a later window while inside
   its bounds") reachable and keeps BR2.4's watermark rationale intact.
7. **Shared error vocabulary.** The wire enum has no DUPLICATE code: a
   duplicate follow surfaces as `409 CONFLICT`; a revision-checked save
   refused on a stale revision surfaces as `STALE_REVISION` so the client can
   reload; a second resolution attempt on a closed run is `409 CONFLICT`.
8. **One writer per table.** Lifecycle evidence is written by the shared
   `apply_owner_effect` contract like every other participant; the
   repository's planned lifecycle methods were removed rather than duplicating
   that writer.
9. **Digest item shape** (resolved at Step 5): `{versionId, paperId, title,
   publishedOn}` — opaque jsonb to the repository, rendered by the email
   assembler and available to the API reads.
10. **Wiring additions beyond the plan's named files** (all in-service chain
    edits the unit required): `backend/artifacts.py` (u5 run root whitelist),
    `ops/src/docsuri_ops/local_transport.py` (U5 realm binding),
    `backend/local_profile.py`/`backend/transactions.py` (u5 realm pair plus
    the `DeadlineConnection.transaction()` savepoint seam),
    `backend/local_browser.py` (TOPICS_ORIGIN),
    `backend/local_observation.py` (topics observation probe),
    `backend/u3_host.py`/`backend/u4_host.py` (factory plumbing),
    `backend/modules/accounts/local_http.py` (the entry surface accepts the
    topics origin), `backend/modules/accounts/integrations/email.py`
    (additive `send_digest_email` seam), `backend/lifecycle_effects.py` +
    `backend/control_worker.py` (participant registration — the shared
    manifest was deliberately not extended, so coordinator realms without the
    topics schema never dispatch TopicsDigests tickets).
11. **`archive-legacy` dropped** from the runner: no superseded U5 prototype
    exists to preserve (the idle U4 prototype was stopped by the orchestrator,
    not by this unit).
12. **Local-only note:** the `frontend` phase's first invocation failed on a
    cold corepack cache (a pnpm download attempt while
    `COREPACK_ENABLE_NETWORK=0`); the warm cache cleared it. The CI lane
    installs pnpm explicitly, so the lane is unaffected.
13. **Realm-persistent test design:** every suite re-runs against accumulated
    realm state (unique follow keys, membership-based corpus assertions,
    stable uuid5 accounts, the fixtures' forward-window resolve case). The
    repository/coverage passes were each verified twice.

## Known limits

- The synthetic profile's email path is the local sink; a real configured
  path (`pathKind='real'`) stays unimplemented by policy until a maintainer
  configures a free provider — the capability row stays `degraded`.
- The current digest preparation does not read account language/level
  preferences. The email content is Korean and the UI's inheritance note
  overstates the implemented behavior. The synthetic policy also uses one
  `Asia/Seoul` delivery zone. FR1.2's preference inheritance and owner-timezone
  behavior remain incomplete; preserving these requirements is not evidence
  that they have been implemented.
- The delivery plan requires real delivery evidence. Local-sink acknowledgement
  is useful integration evidence but does not meet that completion condition.
- The list read carries each topic's latest non-discarded run and last
  outcome; the settings read carries the per-run history (bounded 10).
- The resolve control keys off the latest non-discarded run, which real
  chronology (BR2.4) guarantees is the open unknown; the fixture seeding
  respects that invariant.
