# CI/CD Pipeline — U8 complete service operations and integration

Date: 2026-10-22 (Asia/Seoul)
Unit: u8-service-operations-integration (service). Sources:

- confirmed [infrastructure-design-questions.md](infrastructure-design-questions.md) (Q1, Q2 and the points settled from the records);
- this Unit's NFR design: [security](../nfr-design/security-design.md) (D4, D6, § 4, § 6.3), [performance](../nfr-design/performance-design.md) (§ 2.2, § 3.3, § 6, § 7, § 10, § 11), [reliability](../nfr-design/reliability-design.md) (§ 8, § 15), [observability](../nfr-design/observability-design.md) and [logical components](../nfr-design/logical-components.md) (§ 6);
- the [functional spec](../functional-design/functional-spec.md) (Workflows 7, 12, 13 and 20) and [rules](../functional-design/rules.md) (BR1.5, BR4.4, BR6.5, BR10.1–BR10.7);
- CONVENTIONS.md (branches, pull requests, annotated SemVer tags), and org.md, team.md and project.md, each under § Deployment, with project.md also under § Mandated;
- the repository on 2026-10-22:
  - `.github/workflows/ci.yml`, whose jobs run on every push and pull request to `develop` and `main`;
  - the per-unit lanes U1–U7, which run only on pull requests and only when their paths change (U2–U6 only for pull requests into `develop`);
  - `release.yml`, whose permissions still include `id-token: write` and `actions: read` from the removed AWS deploy;
  - the fork `revenantonthemission/DocSuri` (`origin`), with no `main` and no tags. Its v1 tags exist only in the local clone and upstream. v1.19.0, the newest, is lightweight and its commit is not in `develop`'s history: the newest tag reachable from `develop` is v1.18.0;
- the tagging action's documentation (`mathieudutour/github-tag-action`, read on 2026-10-22):
  - `create_annotated_tag` defaults to `false`;
  - `custom_tag` overrides the computed bump, and `tag_prefix` still applies to it;
  - `initial_version` sets the baseline before the first tag;
- how uv builds a Python environment: it records absolute paths (the interpreter, script launchers, and editable installs of workspace members), so an environment does not survive being moved.

This is how a change travels from a commit to production: what CI checks, how a release is cut, how it is installed on this Mac, and how a failed release is undone. Where things run is in [infrastructure-specification.md](infrastructure-specification.md), and what is watched is in [monitoring-design.md](monitoring-design.md).

## 1. Decisions at a glance

| ID | Decision | Source |
|---|---|---|
| C1 | A release reaches production in person: a merge into `main` cuts the tag and the GitHub Release by itself, and one in-person command installs it on this Mac | Q1 A |
| C2 | A failed release is undone by switching back to the kept previous release. Every owner migration and every arrangement change is additive across two releases, and CI proves the previous release still runs on the new schema | Q2 A |
| C3 | The complete verification lane runs on every push and pull request to `develop` and `main`, with no path filter, beside the per-unit lanes | BR10.4 |
| C4 | Branch protection on `develop` and `main` requires the checks that always report: `ci.yml`'s every-push jobs and the complete verification lane. The path-filtered per-unit lanes keep running but are not required | settled; § 3.1 |
| C5 | The fork, `revenantonthemission/DocSuri`, is the authoritative repository. The first v2 release creates `main` with a one-off push and is tagged v2.0.0 through the action's `custom_tag`, whatever tags the history holds. Tags are annotated | settled; CONVENTIONS.md; § 4 |
| C10 | Each release lives in its own folder, `releases/<tag>/`, with its Python environment built at that final path. `release` and `release-previous` are root-owned links to two of them, so no environment is ever moved | settled; Q2 A; § 5.3 |
| C6 | The performance phase runs on this Mac before a release reaches production, only when this Mac has room for it, with stand-in vectors for its corpus and the real model for its queries | NFR8.11; § 5.2 |
| C7 | No production secret enters CI. The workspace build runs in a read-only job, and third-party actions are pinned by commit | settled; § 4 |
| C8 | An arrangement change is applied by the install that carries it, inside its maintenance window. The isolation check compares against the installed arrangement's manifest | settled; § 9 |
| C9 | The install shows what it will change and asks you to type the commit's short hash before it touches production | Q1 A; § 5.1 |

## 2. From a commit to production

1. A working branch opens a pull request into `develop` (CONVENTIONS.md). CI runs; branch protection requires the always-reporting checks (§ 3.1).
2. A release pull request promotes `develop` into `main`, with the same required checks. The first release is the exception: it creates `main` itself (§ 4).
3. The push to `main` runs `release.yml`. It computes the next version from the conventional commits, creates the annotated tag, and publishes the GitHub Release with the workspace build and its SHA-256 attached (§ 4).
4. On this Mac, you run `docsuri-release install <tag>` in person. It shows what it will change, asks you to confirm, then checks, measures, backs up and installs (§ 5).
5. If the release does not become ready, the same command switches back to the previous release (§ 6).

Before the switch, the install targets the rehearsal environment, and a new release tag restarts the soak. After the switch, it targets live production (§ 7).

## 3. Continuous integration (C3, C4)

| Stage | Where | What runs | Required check |
|---|---|---|---|
| Lint, types and suites | `ci.yml`, Linux and macOS, on every push and pull request to `develop` and `main` | `platform-integrity`, `shared`, `ingestion`, `discovery`, `summarization`, `ops`, `backend`, `root-suites`, `security`, `rem1-closure-audit`, `rem1-isolated` and `macos-filesystem`, plus `dependency-review` on pull requests | yes, each by its job name |
| Per-unit lanes | the U1–U7 workflows, on pull requests whose paths they watch | as built (BR10.4) | no: a check that never reports would hold a pull request forever. The complete verification covers the whole application on every change |
| The complete verification | new `u8-complete-verification.yml`, Linux, on every push and pull request to `develop` and `main`, with no `paths:` filter | the composed realm (below) | yes |
| Arrangement tests | `ci.yml`'s `macos-filesystem` job, extended, on the macOS runner, which allows sudo | the rotation job's link, pipe and hard-link tests; `visudo -c -f` on the sudo rules, `plutil -lint` on the launch job definitions and `pfctl -n -f` on the packet filter anchor; `uv sync --frozen --no-build` on macOS, so a dependency without a wheel fails here and not at an install | yes, as part of `macos-filesystem` |

### 3.1 Required checks (C4)

- **The set.** Branch protection on `develop` and `main` requires exactly the checks marked yes above. Each of them reports on every push and pull request to either branch, so none can hold a pull request forever.
- **The per-unit lanes** still run whenever their paths change, and their failures are visible on the pull request, but they are not required.
- **When it is switched on.** Protection for `develop` starts once the complete verification lane exists on `develop`, and for `main` right after the first release has created it (§ 4). It is free for a public repository.

### 3.2 The complete verification lane (BR10.1–BR10.6)

**Preparation**

- the same root-owned private temp root the existing Linux jobs use, `/r1-private/tmp` with `TMPDIR` set to it, because the keychain ancestor check refuses a world-writable `/tmp`;
- PostgreSQL 16 with pgvector, from pgvector's official image for PostgreSQL 16 pinned by digest. A first step asserts `server_version` 16.14 and pgvector's pinned `extversion`, so the image matches production's source build or the lane fails.

**The realm**

- One composed realm with every contribution and participant, the composition production uses, on the synthetic profile at `127.0.0.1:18109` and `:15509`.
- The real workers and control loop, and only the outward providers as stand-ins (BR10.2).

**A synthetic v1**

- v1's own code at the same commit, with stand-ins for its data plane as service containers (PostgreSQL 16, its search index and its object store), seeded with synthetic v1 data.
- The migration journeys of BR10.3 run against it.

**A real browser**

Playwright with Chromium, for the journeys and the accessibility evidence.

**The corpus**

- A synthetic corpus at the size the first dry run measures: the paper count, the spread of chunks per paper and the largest values. Until that run exists, 600 papers of 100 chunks.
- Its vectors come from a deterministic stand-in embedder.

**Phases**

- the journeys of BR10.3;
- security: the route inventory, owner isolation, the production headers, forged forwarded headers, the sign-in limits, and the cross-site arrival with a stand-in provider served from another site;
- accessibility evidence for every screen (BR10.6);
- both restore paths as logins that are not superusers (security-design.md § 6.3);
- the workspace build's gate: precompressed files, and the first load under 300 KB of scripts and 50 KB of styles, compressed (performance-design.md § 2.2).

**The schema compatibility check (C2)**

- The lane migrates a database to the candidate's schema.
- It checks out the previous v2 release tag, and that tag's own test suite runs its critical journeys against the migrated database.
- A migration that drops, renames or narrows what the previous release still uses fails the lane.
- Until a v2 tag exists, there is no previous v2 release: the check is skipped, and says so in its output.

**Its output**

A VerificationRun record for the commit: each journey with its result and evidence reference (entities.md). It is kept as the run's artifact for 90 days.

## 4. Cutting a release (C5, C7)

- **The authoritative repository** is the fork, `revenantonthemission/DocSuri` (`origin`). It carries `main`, the tags, the GitHub Releases and the check runs the install reads.
- **The trigger.** `release.yml` runs on every push to `main`, as today, and computes the next SemVer from conventional commits. The tagging step gains `create_annotated_tag: true`: the action's default is `false`, which makes lightweight tags, while CONVENTIONS.md requires annotated ones.
- **The first v2 release.** It runs once, in this order:
  1. `main` is created by a one-off push of `develop`'s chosen release commit. A pull request cannot target a branch that does not exist yet.
  2. That push runs `release.yml`. Its first step lists the tags on `origin`. With no `v2.*` tag there, it passes `custom_tag: 2.0.0` to the tagging step, which overrides the computed bump, so the tag is `v2.0.0` whatever tags the history holds. No v1 baseline is needed: `origin` has none, and v1.19.0's commit is not in `develop`'s history anyway.
  3. A guard step fails the job if no `v2.*` tag existed before the run and the created tag is not `v2.0.0`, so a wrong first version is never published.
  4. Protection for `main` is then switched on (§ 3.1). Every later release is a pull request from `develop` into `main`, and the tagger computes it from the newest tag reachable on `main`, starting at `v2.0.0`.
- **The workspace build.**
  - A job with `contents: read` builds the v2 workspace from the tagged commit, with its lockfile. It precompresses the files, checks the first-load budget, and hands the result on as a workflow artifact.
  - A second, narrow job with `contents: write` attaches the build and its SHA-256 to the GitHub Release.
  - The build's package install never runs where a write token exists, and no Node.js is needed on this Mac.
- **Permissions.** `release.yml` drops `id-token: write` and `actions: read`, which are left over from the removed AWS deploy. Only its release and upload jobs have `contents: write`. Every third-party action stays pinned by commit.

## 5. Installing a release (C1, C6, C9)

`docsuri-release install <tag>` is an in-person fixed command. The operator tool runs it with `sudo -k`, so it asks for your password (security-design.md § 5.3).

### 5.1 The steps

| Step | What happens | Stops the install when |
|---|---|---|
| 0. Show and confirm | It shows the tag, its commit, the complete verification's run and result, the commits since the installed release, the migrations it will apply and any arrangement change with the installer's plan. You type the commit's short hash to go on | you stop, or type another hash. Nothing has changed |
| 1. Preflight | It reads, without a token, GitHub's public check runs for the tag's commit on `origin`, and records the conclusion of the complete verification and the run's identity as that commit's VerificationRun in the profile's evidence folder (BR10.5). It also checks: the tag is annotated and on `main`; no production restore, switch, abort or rollback is active; the latest isolation result passed within 15 minutes; the internal disk can hold the staged release and a backup; and the room the performance phase needs (§ 5.2) | any check fails. Nothing has changed |
| 2. Stage | It clones the tag into `/Library/DocSuri/releases/<tag>/`, the folder the release will run from (§ 5.3), as root. There it installs its CPython and its Python dependencies from the lockfile, wheels only, with their hashes (`uv sync --frozen --no-build`), so no package's build script ever runs as root and every path the environment records is its final one. It downloads the workspace build, checks its SHA-256 against the release, runs the library check (`otool -L`) and reads the release's arrangement version (§ 9) | a digest or a check fails. The folder is deleted |
| 3. Performance phase | It runs the composed realm from `releases/<tag>/`, the same path production will run, on this Mac. It records NFR8.1–NFR8.6 with the release's VerificationRun (NFR8.11), bounded as § 5.2 says | a target is breached. Production's code, data and routing are unchanged |
| 4. Maintenance (live mode only) | It routes the public address to the maintenance server through tunnel routing | the route fails. Nothing has changed |
| 5. Stop | It stops v2's host, workers and scheduler through service control | a stop fails. It routes back |
| 6. Backup | It takes the backup agent's in-person backup of the current database and a ledger copy, after writes have stopped, and requires integrity to pass | the backup fails. It starts the current release again and routes back |
| 7. Arrangement (only when the release changes it) | It runs the release's own installer from `releases/<tag>/`, applying the plan you saw at step 0. A root-owned in-progress marker, bound to this install's receipt and valid for 60 minutes, tells the isolation check to report the changed items as a change in progress rather than as lapses (§ 5.4) | an apply fails. The installer's result names what was applied, and that state is written to the manifest (§ 5.4). The install stops with v2 stopped and the maintenance notice up, for you to repair or roll back (§ 6) |
| 8. Migrate | It applies each owner's new migrations from `releases/<tag>/`, in owner order, through the production environment tool (BR1.5). Each runs in its own transaction | a migration fails. That one rolls back; the migrations already applied stay, and the current release, which accepts them (§ 6), starts again. The marker is cleared (§ 5.4) |
| 9. Swap | It points `release-previous` at the release `release` points to, then points `release` at `releases/<tag>/`. Each link is replaced atomically: a new link is renamed over the old one (§ 5.3) | — |
| 10. Start | It starts v2 through service control, waits up to 10 minutes for readiness, then runs the signed-out probe journey (BR10.7) | readiness or the probe fails. It switches back (§ 6) |
| 11. Route back (live mode only) | It routes the public address back to v2 | the route fails. It retries, and the maintenance notice stays meanwhile |
| 12. Record | It records the installed tag and commit as readiness evidence (BR6.5), and the release's ledger record: the tag, the previous tag, the VerificationRun, the backup set, the arrangement version and each step's time. It removes the in-progress marker, so the next isolation check compares against the new arrangement manifest. It then deletes every folder under `releases/` that neither link points to | — |

- **Downtime.** The maintenance window runs from step 4 to step 11: the backup, any arrangement change, the migrations and the start. At today's sizes that is a few minutes, and it counts against the month's availability.
- **Before the switch.** The public address serves v1, so steps 4 and 11 are skipped and the rehearsal v2 restarts. A new tag restarts the soak (Workflow 12).
- **One at a time.** An install holds the live environment's exclusion in the ledger, like a production restore, so no backup, verification or disposal starts during it (BR4.4).

### 5.2 Sharing the Mac during the performance phase

The phase runs a second, composed v2 beside production, so it is bounded:

- **Room.**
  - The phase's realm runs as your login account, with its own throwaway PostgreSQL from the root-owned 16.14 build (infrastructure-specification.md § 4).
  - It is budgeted at up to 5 GiB: its host and workers under 4 GiB, plus its database with production's settings.
  - Preflight requires at least 6 GiB of memory available (free plus inactive, from `vm_stat`). It also requires production to have served fewer than 60 requests a minute over the last 15 minutes, from the latency summaries.
  - Otherwise it refuses and says to try again at a quieter time.
- **Vectors.** The phase's corpus gets its vectors from the same deterministic stand-in embedder as CI, so no hour of embedding is needed. Its queries are embedded by the real, pinned search model, so NFR8.4 includes the real query embedding.
- **The shared model runtime.**
  - The phase's query embeddings queue with production's, one at a time (`OLLAMA_NUM_PARALLEL=1`).
  - Production's searches keep their 2-second embedding bound and answer by words only if they must (performance-design.md § 3.3), so production degrades gracefully and never waits without limit.
  - The phase sends no research or novelty work, so the research model is not loaded for it.
- **What it records.** Production's request rate during the phase is recorded beside the measurements, so a breach caused by load can be told apart from a slow release.

### 5.3 Release folders and links (C10)

- **One folder per release.** Each release lives in `/Library/DocSuri/releases/<tag>/`: its clone, its uv-installed CPython, its `.venv` and the workspace build. uv records absolute paths, so each environment is built where it will run and is never moved.
- **Two links.** `/Library/DocSuri/release` and `/Library/DocSuri/release-previous` are root-owned symbolic links, each to one of those folders.
  - Every launch job and fixed command uses the path `/Library/DocSuri/release/…`, as BR6.5 names it. Jobs restart after the link changes, so a running process never sees it change under it.
  - A switch replaces a link atomically: a new link is created beside it and renamed over it.
- **What the isolation check confirms.** Both links are owned by root, point into `releases/`, and point at root-owned folders no other account can write. The libraries each program loads resolve inside its own release folder.
- **Disk.** At most three release folders exist at once: the installed one, the previous one and, during an install, the candidate. After step 12 only the two the links point to remain, about 1 GB more than one release alone (Q2 A).

### 5.4 The in-progress marker and the arrangement manifest

- **What the marker is.** At step 7 the install writes a root-owned marker, bound to its receipt and valid for 60 minutes. While it is valid, the isolation check reports the arrangement items the plan changes as a change in progress, never as lapses.
- **Every way out clears it.** The marker is removed, and the manifest records the arrangement as it actually stands, whichever way the install ends:
  - at step 12, after success;
  - after a failed migration at step 8;
  - after a switch back (§ 6);
  - after a failed apply at step 7. The manifest then records what the installer did apply, and the isolation check reports any item left inconsistent as a failure, so the lapse is seen.
- **A marker past its 60 minutes,** for example because the install was killed, stops covering anything. The isolation check then reports the items against the manifest, so an unfinished change cannot stay hidden.

## 6. Undoing a failed release (C2)

- **Automatic switch back.** If v2 is not ready within 10 minutes of step 10, or the probe journey fails, the same command, still in person:
  1. stops v2;
  2. points `release` back at the release `release-previous` points to. The failed release's folder is marked failed and kept for diagnosis until the next install deletes it;
  3. starts v2 and waits for readiness;
  4. clears the in-progress marker and records the arrangement state (§ 5.4);
  5. routes back.

  The previous release still runs from its own folder and environment, so nothing has to be rebuilt. It takes a few minutes.
- **The schema and the arrangement stay as they are.** Both are additive across two releases (below), so the previous release runs on them as they are.
- **A later rollback.** If a problem shows up after the install has finished, `docsuri-release rollback` does the same link switch behind the maintenance notice, in person, while `release-previous` still points to a kept release.
- **Additive across two releases.**
  - A migration may add tables, columns, indexes and functions, add nullable columns or columns with defaults, and backfill.
  - An arrangement change may add a job, a rule, a setting or a folder.
  - Either may drop, rename or narrow only in a later release, once no installed or kept release uses the old shape.
  - Each owner's migrations must also be compatible on their own, because a failed install can leave some owners migrated and others not (step 8).
  - CI's schema compatibility check enforces the migrations (§ 3.2). The installer's plan marks an arrangement change that is not additive.
- **An arrangement change that is not additive.** Step 0 then says the automatic switch back is unavailable for this release. A failure after step 7 then rolls back by running the previous release's installer and the swap, or by the production restore of step 6's backup, on your decision.
- **The first v2 release** has no earlier v2 release to switch back to. It installs in rehearsal mode, before the switch, while v1 still serves the public address. A failed first install leaves the rehearsal v2 stopped, and the install is repeated once fixed.
- **The last resort.** A production restore from step 6's pre-release backup (Workflow 7), on your decision. It loses any writes made after that backup.

## 7. Environments and promotion

| Environment | Runs | Promoted by |
|---|---|---|
| A unit's synthetic realm | this Mac, during development | a pull request into `develop` |
| CI and the composed realm | GitHub's runners, on every push and pull request | merging into `develop`, then the release into `main` |
| The composed realm on this Mac | the performance phase of each install | step 3 of the install |
| Rehearsal (the soak) | the production profile, before the switch | the switch (Workflow 13), on your decisions |
| Live | the production profile, after the switch | each install |

team.md's "deploy on merge to staging" is met by the composed realm, which every merge into `develop` runs.

## 8. Secrets in CI/CD (C7)

- **CI holds no production secret.** The synthetic realm makes its own throwaway keys and passwords for each run, and outward providers are stand-ins, so no provider key is needed.
- **Release asset.** The workspace build is public, carries its SHA-256 in the release, and is checked at install.
- **On this Mac.** The install reads no secret except what the restarted jobs read from their own folders. The migrations run under the owners' logins, through the production environment tool as the service account. Nothing secret leaves the machine.
- **Logs.** No workflow prints a secret. The CI jobs mask every value the synthetic realm generates.

## 9. Arrangement changes and releases (C8)

- **The manifest.** The installer writes `control/arrangement-manifest.json` (root, 0644): the arrangement version it installed, and the digest of every file it put in place. The isolation check compares the installed files against that manifest, not against the running release. So which release is active never changes what the check expects.
- **The version.** Each release's templates carry an arrangement version.
  - A release with the installed version installs with no arrangement step.
  - A release with a higher version brings its own installer, which runs at step 7.
  - A release with a lower version, or with an unrecognised one, is refused at step 2.
- **Outside a release.** A runtime upgrade or an arrangement repair can still run the installer on its own, in person, with its plan mode first (infrastructure-specification.md § 4). A runtime upgrade repeats the performance phase before it reaches production (NFR8.11).

## 10. Requirement wording settled here

- **project.md § Mandated, "ALWAYS deploy continuously to production on merge".** It is read as not covering this Mac's production (Q1 A). A merge into `main` still produces the tag and the GitHub Release by itself, and installing is in person, because the release folder changes only with administrator rights (BR6.5). org.md's § Deployment already gates production on a manual approval by default, so the reading does not conflict with org-level policy.
  - The reading is recorded through the learnings step at U8's checkpoint, for you to approve there.
  - C1 rests on your Q1 answer, not on that record. If the reading is not recorded, the rule and C1 remain in conflict, and the conflict is shown at the checkpoint for your decision.
- **team.md § Deployment, "deploy on merge to staging".** The composed realm in CI is the staging environment every merge into `develop` reaches.

## 11. Required verification

- **CI and the release workflow:**
  - Each required check reports on a pull request that touches no per-unit path, and on the release pull request into `main`.
  - A failed journey in the complete verification lane blocks the merge.
  - The first release on a fork with no v2 tag is tagged `v2.0.0` through `custom_tag`, whatever tags the history holds, and the guard fails a job that creates anything else. A later release computes from the newest tag on `main`.
  - The lane fails when the database image's PostgreSQL or pgvector version differs from the pins.
  - The workspace build's job holds no write token, and the build's first load stays within its budget.
- **Refusals before production changes:**
  - The install refuses a tag whose commit has no successful complete-verification check, a lightweight tag, a tag not on `main`, and a wrong short hash at step 0.
  - A workspace build whose SHA-256 differs from the release's is refused.
  - A dependency without a wheel is refused at step 2, and no build script runs as root.
  - The performance phase is refused below its memory or load threshold, and production's request rate is recorded with its measurements.
  - An install during a production restore, a switch, an abort or a rollback is refused.
- **Failures during an install:**
  - A migration that fails in one owner leaves the earlier owners' migrations applied, and the current release keeps running on that partly expanded schema.
  - v2 not ready within 10 minutes of the start switches back by itself, and the time it took is recorded.
- **Compatibility and the arrangement:**
  - The previous release's critical journeys pass on the candidate's schema.
  - A release with a higher arrangement version applies its installer at step 7. During that window the isolation check reports a change in progress, not a lapse. After step 12, the check passes against the new manifest.
  - After a switch back from a release that changed the arrangement additively, the isolation check still passes.
  - The in-progress marker is gone, and the manifest matches the arrangement as it stands, after a failed migration at step 8, after a failed apply at step 7, and after a switch back. A marker past its 60 minutes covers nothing.
- **Release folders:**
  - After the swap, and again after a switch back, the running host and workers import their code and their libraries from the real path `release` points to, and from no other release folder.
  - The performance phase ran from the same folder production then runs.
  - After step 12, only the two folders the links point to remain under `releases/`.
- **After an install:** readiness evidence shows the new tag and commit, and the ledger shows the release record.
