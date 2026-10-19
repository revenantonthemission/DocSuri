# U5 code summary — topics & digests

## Steps 12–13 verification — 2026-10-19 (supersedes the mounted-browser status below)

**Browser supervision repair.** Browser verification observed two process trees
(Playwright and the companion host) by taking a separate `ps -A` snapshot per
root in every 50 ms tick. That doubled the process-table scans and measured the
trees at different instants; prior attempts stopped on `TimeoutExpired` from that
observation. `scripts/verify_docsuri_u5.py` now takes ONE bounded snapshot per tick
(`process_tree_rss(roots, deadline)`) and sums the union of both trees, so a shared
descendant cannot be counted twice. The 1-second per-observation limit
(`OBSERVATION_SECONDS`), the 1 GiB aggregate RSS budget, the 300-second phase bound,
log limits and the fresh-realm refusal are unchanged. Supervision records now add
`observations` and `slowestObservationSeconds` for diagnosis. The passing run below
shows the repaired path works; it does not prove the earlier timeouts had no
host-load component.

**Mounted browser checkpoint (exact authorized command, fresh realm
`docsuri-u5-bbedf7e857ba1c5d`, 63 migrations, fixtures only):** 4 tests, 0
failures/errors/skips, exit 0. Playwright 7.8s; supervision 8.17s, 121 observations,
slowest 0.0229s, peak RSS 909,737,984 bytes (within, but close to, the 1 GiB
budget), process stopped. Journeys: follow/preferences/settings/unsubscribe 1.32s;
scheduler → local-sink delivery with Korean/Asia/Seoul propagation 4.99s; recorded
empty digest with no send 0.50s; explicit unknown resolution 0.46s. Source
SHA-256 `2097abb709a6be4bbb2645474755e309f1540bae6b5f1d5e73a014541a5f38f5`.
Realm preserved at `/private/tmp/docsuri-u5-preserved-docsuri-u5-bbedf7e857ba1c5d-a52f4219`.
This direct run is not the AI-DLC checkpoint receipt; that must still be produced
through the checkpoint verifier on a fresh realm.

**Frontend (Step 12):** new `frontend/test/u5-topics/settings-dialog.test.tsx`
(13 cases: unconfigured zone, Korean non-default readout, unreadable preferences,
preference-save refresh, weekly day gate with day/window body, stale weekday
dropped, unchanged save, initial read failure, reload failure, Escape and Tab
trap, in-dialog unsubscribe confirm/cancel, local-sink vs real path labels).
Scoped Vitest: **35 passed**, U5 lines **97.93%** (floor 80%); typecheck, CI lint
command, Prettier and Vite build pass. `topics.test.tsx` was Prettier-formatted
only.

**Backend (fresh realm `docsuri-u5-272f4bac81e78719`):** coverage phase **158
passed, zero failures/errors/skips, 82.94% aggregate** (80% floor), 13.2s, peak
RSS 243,924,992 bytes. Three new runner regressions: one snapshot per tick for both
roots, union without double counting under the unchanged limit, refusal after the
deadline. Per-file gaps remain below 80%: `personalization/local_http.py` 35%,
`scripts/u5_browser_fixtures.py` 73%, `scripts/serve_docsuri_u5.py` 70%,
`accounts/services/guarded_entry.py` 79%.

**Static and inherited checks:** ruff (CI file list plus `digest_email.py`)
passes; canonical schema and generated-binding drift checks pass; shared contract
suite 161 passed; U1 transport/records regression 13 passed; U2 transport/runtime
regression 39 passed.

**Still open:** real email delivery (no sender, recipient, or authorized message;
nothing sent); the AI-DLC browser checkpoint receipt; a fresh independent review.

## Repair status — 2026-10-19

This section supersedes the earlier implementation account below. Local repairs
are implemented; completion and merge remain pending.
Resend is selected, but the human confirms no sender address or test recipient
exists. No external email was sent and no provider account or domain was created.
See [external evidence prerequisites](../../../maintenance/u5-real-delivery-evidence.md).

The repair adds authoritative C03 language/standard-level/IANA-zone settings,
owner-authorized background reads, actual English/Korean presentation, immutable
preference snapshots and send-admission fencing. The schedule filters due owners
before pagination, retains intended weekly dates after late execution, uses one
aware instant, and handles DST gaps/folds with finite searches. Appearance-only
changes preserve prepared work; effective preference changes discard only unsent
work. Account bootstrap and logout retain account-control authority after research
consent withdrawal; research delivery still requires consent.

The account-owned digest adapter returns accepted/refused/unknown with actual
receipt and acknowledgement time. Local profiles cannot access the network;
real composition requires explicit free Resend configuration and a finite durable
send budget. Initial requests use immutable idempotency keys; reconciliation
never sends again. A hash-only, run-bound cancellation capability supports an
inert confirmation GET and bounded cookie-free RFC8058 POST; existing browser
authorization remains unchanged. The assembled middleware/store test uses actual
lifespan and a real capacity refresh; it proves the route boundary, not startup
readiness. Public HTTPS, DKIM, proxy logging and real delivery remain unverified.

### Repair verification

Latest stable-source backend verification: **155 passed, zero failures/errors/
skips, 82.94% aggregate coverage**, retaining the 80% floor. Runtime was 93.61s,
peak RSS 215,433,216 bytes, and the process stopped. Immutable evidence:
`/private/tmp/docsuri-u5-preserved-docsuri-u5-68f00b6ee0bcf67a-aa7edb82/coverage-evidence-1792342925464628000.json`.
This supersedes the earlier 148/146-check backend results below.

The browser fixture helper now derives absolute interpreter/script/root paths
from its source URL. Both repository-root and frontend working-directory path
checks, scoped and explicit helper TypeScript checks, and formatting pass.
A mounted attempt reached one passing journey before exposing a nested runner
lock in synthetic clock advancement. The repair retains the parent's exclusive
phase lock and delegates only clock advancement through a private run-bound,
short-lived capability. Only the Playwright process receives its plaintext
token; persistent metadata holds its hash. The child validates run, expiry,
live lock owner and active lock. Setup/unrelated phases still require exclusive
ownership. Capability metadata is removed on success/failure; broad child
environment construction is unchanged. Seven focused checks pass, including an
actual spawned child, refusal cases and cleanup; they also pass in the 155-test suite.

Mounted acceptance remains **unverified**. The final attempt stopped on recurring
process-observation TimeoutExpired before a test report: exit 1, supervision-error,
37.712s, 625,885,184-byte peak RSS and stopped process. No causal claim about
host load is established, and monitoring/time/resource bounds remain unchanged.
No more retries were made. The complete four-journey mounted proof and real
provider demonstration remain prerequisites for unit completion and merge.
Final browser evidence is preserved at
`/private/tmp/docsuri-u5-preserved-docsuri-u5-87dd16122f1ae63d-a65cdc86/browser-evidence-1792343092561092000.json`.
The current Vite build passed in 7.921s, peak RSS 571,785,216 bytes. Browser
execution began (34 log bytes), then supervision failed; this attempt is not
described as a startup failure. Source SHA-256:
`4f6e3d10f17129f4352175e262775b63770b184ea2dbd6f4170befab6914cd6d`.
The database is stopped and its volume retained.

Subsequent scheduling repair filters consent-stopped owners and topics with
prepared/sending/unknown work before the bounded due page. Queued sending,
reconciliation and consent cleanup remain separate phases; admission still
rechecks authority. Two new real-store cases seed 51 blocked topics ahead of
two eligible topics, exercise three finite passes and assert no additional
attempts for blocked topics. The first supervised component attempt stopped on
process-observation TimeoutExpired after five progress markers, before a report:
`/tmp/docsuri-u5-run/component-evidence-1792341362321630000.json`.
The failed process was stopped and its realm preserved at
`/private/tmp/docsuri-u5-preserved-docsuri-u5-eddddd3bf264167a-ff27e224`.
After a separate bounded host startup diagnostic passed, one fresh coverage
retry completed: **148 passed, zero failures/errors/skips, 83.08% aggregate**,
88.60 seconds, 232,833,024-byte peak RSS, stopped process. Both 51-blocked-topic
cases passed, including repeated finite passes and no new blocked-owner sends.
Evidence: `/tmp/docsuri-u5-run/coverage-evidence-1792341719463695000.json`, realm
`docsuri-u5-dd539733ed2faf50`. This verifies the subsequent scheduling change;
the 146-check result below remains historical. Mounted browser verification is
coordinated separately after preserving this backend realm.

The prior stable-source coverage command in unit-test-instructions.md completed with
**146 passed, zero failures/errors/skips, 83.33% aggregate coverage**. The runner
recorded 83.20 seconds, 219,004,928-byte peak RSS and a stopped process. Evidence:
`/tmp/docsuri-u5-run/coverage-evidence-1792339838010455000.json`, realm
`docsuri-u5-dbef52eaa00ced76`. Exact scoped collection also found 146 tests.
This includes both final runner regressions; no coverage threshold was lowered.
Individual gaps remain (for example fixture helper74%); aggregate passage does
not establish untested real transport or mounted browser behavior.

- Scoped initial collection: 81 baseline tests. Repaired backend coverage:
  **144 passed, zero failed/errors/skips, 83.33% aggregate**, with changed inherited
  account/personalization files included. Evidence is preserved under
  `/private/tmp/docsuri-u5-preserved-docsuri-u5-d11d5b70b57c1935-9f68eda7/coverage-evidence-1792338687405729000.json`.
  This historical repair pass predates the final runner regressions; the final
  146-check result above supersedes it.
- Earlier repair aggregate: 137 passed but 75.68% coverage, correctly failed.
  Seven meaningful inherited session/settings checks added; they exposed and
  verified the consent-independent logout fix. Component pass: 41 checks.
- Frontend: approved scoped typecheck passes; Vitest 22 passed, 92.27% lines.
  Shared canonical export check and Python binding check pass.
- Browser: four journeys prepared, including empty/no-send. First clean-realm
  attempt stopped on host process-observation timeout before any product assertion;
  logs/volume preserved at
  `/private/tmp/docsuri-u5-preserved-docsuri-u5-5a9c245c5a5e48a2-06f63a09`.
  The one-second observation limit remains unchanged. Runner now records
  subprocess supervision failures and stops children; focused regression passes.
  One accidental direct full operations-file invocation had 11 passes and five
  missing-manifest setup errors; it is not counted as a suite pass.
- A subsequent browser attempt produced one failure and three not-run journeys:
  the host served old static assets without the new preference controls. That
  failed realm is preserved at
  `/private/tmp/docsuri-u5-preserved-docsuri-u5-5cc14ee5470b8ed8-2dd9b197`.
  The runner now rebuilds the current Vite entry before serving, records build
  command/log/supervision, and refuses failed builds within the original total
  300-second bound. The focused failed-build regression passes. Final mounted
  verification remains blocked: the corrected run built successfully in 5.75s
  (581,877,760-byte peak RSS), then host startup observation raised TimeoutExpired
  before tests began. The failure has no test report and no fabricated process
  metrics. Preserve its full evidence at
  `/private/tmp/docsuri-u5-preserved-docsuri-u5-5aeb407c0268ad99-1e66dc21/browser-evidence-1792339535341341000.json`.
  No further browser retry was made before rechecking process observation. The empty-state mounted proof and
  Step12 remain open pending a complete mounted run under the original bounds.

All stateful phases use the exact commands in unit-test-instructions.md. Earlier
layer passes were database16, repository19, component34, integration22 and
operations46 before the seven inherited regressions. The backend/browser realms
are independent; a consumed or failed realm is archived, never cleared or extended.

### Migration and remaining evidence

Fresh corrected **63-migration** installations and the additive **62→63** path
were exercised. These do not prove adoption of the original failed 59-migration
realm: its selection-comment bytes differ, so immutable ledger checks refuse drift.
Preserve that original realm and create the fresh synthetic replacement; never
rewrite its receipts. No existing-user migration is authorized or claimed.

The scoped runner, selection comment, preference inheritance and owner-zone
scheduling repairs are implemented and locally tested. Typed real delivery and
cancellation are implemented, but actual external acceptance and correlated
recipient evidence remain unavailable. The four mounted browser journeys still
need a completed pass under the original process/resource bounds.

The source manifest enumerates existing U5 contributions and all repair source,
tests and generated bindings. Existing account/corpus/research boundaries are
exercised through the real assembled store; no whole-release parity claim is made.
Historical results below remain historical evidence, not the repaired-source proof.

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
