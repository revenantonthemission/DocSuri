# Build instructions

How to build DocSuri v2 as this piece of work leaves it: the topics and digests Unit (U5), the approved export Unit (U6) and the complete integration with service operations (U8), assembled with the earlier Units U1–U4 and U7 that a previous piece of work built. Everything here runs on the maintainer's Mac or in CI. Nothing in it touches the live v1 service that runs from this same checkout.

## Sources

- U5: `construction/u5-topics-digests/code-generation/code-generation-plan.md` (Testing Contract), `unit-test-instructions.md` and `code-summary.md` in the same folder.
- U6: `construction/u6-approved-export/code-generation/code-generation-plan.md`, `unit-test-instructions.md` and `code-summary.md`.
- U8: `construction/u8-service-operations-integration/code-generation/code-generation-plan.md`, `unit-test-instructions.md` and `code-summary.md`, with the runbooks in that folder for the installation itself.
- CI: `.github/workflows/ci.yml` and `.github/workflows/u8-complete-verification.yml` for the install commands a fresh machine uses.

## Prerequisites

- **Machine:** this Mac (Apple silicon, macOS), the repository at `~/Projects/DocSuri` on branch `feature/u8-service-operations-integration`.
- **Python:** 3.13 (CI pins 3.13.7), with the project's virtual environments already present: `backend/.venv`, `ingestion/.venv`, `shared/python/.venv`, `ops/.venv`, `platform_integrity/.venv`, `backend/modules/discovery/.venv` and `backend/modules/summarization/.venv`.
- **Node:** through `corepack pnpm@9.15.9`, with `frontend/node_modules` installed and Playwright's Chromium for the browser journeys.
- **Docker:** Colima only, 4 CPUs and 6 GiB of memory, reached with the two variables below. Never OrbStack.
- **Disk:** at least 25 GiB free before a complete run. The recovery journey (J09) refuses unless free space minus its database stays above 20 GiB.
- **Network:** none to real providers. Google, ORCID, Resend, healthchecks.io, Notion and Cloudflare are played by local stand-ins, and the model runtime by a deterministic stand-in.

## Dependency installation

On this Mac the live v1 runs from the same virtual environments and `frontend/node_modules`, so these commands are documented here and run only by the maintainer's decision. A fresh clone or a CI runner uses them as `ci.yml` does:

```bash
uv sync --project backend --frozen --python 3.13.7
uv sync --project shared/python --frozen --python 3.13.7
uv sync --project ingestion --frozen --python 3.13.7
uv sync --project ops --frozen --python 3.13.7
uv sync --project backend/modules/discovery --frozen --python 3.13.7
uv sync --project backend/modules/summarization --frozen --python 3.13.7
uv sync --project platform_integrity --frozen --all-extras --python 3.13
corepack pnpm@9.15.9 --dir frontend install --frozen-lockfile --ignore-scripts
corepack pnpm@9.15.9 --dir frontend exec playwright install --with-deps chromium
```

The lock files are the contract: a build never changes `pyproject.toml`, `uv.lock`, `package.json` or `pnpm-lock.yaml`.

## Environment setup

Every command runs from the repository root unless it names a working directory.

```bash
export DOCKER_CONFIG=$HOME/.docsuri-u8/docker-config
export DOCKER_HOST=unix://$HOME/.colima/default/docker.sock
```

Each Unit's environment tool builds a disposable realm under `/tmp/docsuri-<unit>-run` (mode 0700, 24 hours of life). Each phase takes the same three arguments, written out in full; zsh does not split an unquoted variable into words, so a shared `$ARGS` does not work there:

```bash
backend/.venv/bin/python scripts/verify_docsuri_u8.py --phase setup --profile synthetic-local --environment-file /tmp/docsuri-u8-run/environment.json
backend/.venv/bin/python scripts/verify_docsuri_u8.py --phase migrate --profile synthetic-local --environment-file /tmp/docsuri-u8-run/environment.json
```

- U8's realm uses ports 18109–18114, 15509–15510, 16389, 19209 and 19009. No realm ever binds v1's ports (3000, 8000, 5432, 6379, 9200, 9000).
- The other Units' tools follow the same shape: `scripts/verify_docsuri_u1.py` through `verify_docsuri_u7.py`, each with its own run root.
- The production profile is never used by any build or test. Every stand-in and the realm driver refuse it.

## Build commands

DocSuri's backend, operations tools and ingestion are Python and have no compile step. Building the application means checking the shared contract, type-checking and bundling the frontend, and building the composed database chain.

1. **Shared contract.** The canonical schemas, the generated Python and TypeScript bindings, and the type contract stay in step:

   ```bash
   shared/python/.venv/bin/python shared/python/tools/export_workspace_contract.py --check
   PATH="$PWD/shared/python/.venv/bin:$PATH" shared/python/.venv/bin/python shared/python/tools/generate.py --check
   corepack pnpm@9.15.9 --dir frontend run check:types
   ```

2. **Type checks,** always with `--incremental false` so no build-info file is written into `frontend/`:

   ```bash
   corepack pnpm@9.15.9 --dir frontend exec tsc --project tsconfig.u5-topics.json --noEmit --incremental false
   corepack pnpm@9.15.9 --dir frontend exec tsc --project tsconfig.u6-export.json --noEmit --incremental false
   corepack pnpm@9.15.9 --dir frontend exec tsc --project tsconfig.u8-complete.json --noEmit --incremental false
   corepack pnpm@9.15.9 --dir frontend exec tsc --noEmit --incremental false
   corepack pnpm@9.15.9 --dir frontend exec tsc -p tsconfig.e2e.json --noEmit --incremental false
   ```

3. **Frontend production bundle and its budget.** U8's build gate builds the composed single-page application and fails when the first load passes 300 KB of scripts or 50 KB of styles, compressed:

   ```bash
   backend/.venv/bin/python scripts/verify_docsuri_u8.py --phase build-gate --profile synthetic-local --environment-file /tmp/docsuri-u8-run/environment.json
   ```

4. **The composed database chain.** U8's `setup` and `migrate` phases build PostgreSQL 16.14 with pgvector 0.8.7 and apply the composed chain of `backend/u8_migrations.py` (137 migrations on 2026-11-15), then install and verify PlatformControl's store in `docsuri_u8_platform`.

5. **Lint.** Ruff on U8's CI target list, and each Unit's ESLint command as its unit-test instructions spell it (for U8, with `--parser-options '{"project":"./tsconfig.u8-complete.json"}'`).

   Since run 5 (2026-11-19), U6's Ruff runs exactly as its CI workflow writes it: the `run:` block of the step "Lint export and shared runtime changes" in `.github/workflows/u6-approved-export.yml` (lines 106-123 on 2026-11-19), taken verbatim and executed from the repository root the way GitHub runs a bash step, `bash --noprofile --norc -eo pipefail <file>`. `~/.docsuri-u8/lead-scripts/u6_step63_extra.py` does this (its `ci-lint` step). The block holds four Ruff invocations: U6's tests under `scripts/u6-lint.toml` (E,F,I,UP,B at line length 100), its scripts under `scripts/u6-lint-scripts.toml`, its backend and shared runtime files under their own configurations, and the four U2 accounts files it changes under `scripts/u6-lint-accounts.toml`. A hand-made list of U6's targets without those `--config` options lints each file under its folder's defaults, which is not U6's check: in run 5 such a list (rung 1's step 01, `u6-ruff-ci-list`) reported 3 import-order findings that U6's configuration does not raise.

   Since run 6 (2026-11-23), U8's loop-back 4 section adds two checks, run once from the repository root. The ops project's own Ruff over the five ops files the section changed:

   ```bash
   (cd ops && .venv/bin/ruff check --no-cache src/docsuri_ops/production_wiring.py src/docsuri_ops/production_tool.py src/docsuri_ops/u8_platform/platform_profile.py src/docsuri_ops/arrangement/installer.py src/docsuri_ops/arrangement/verify.py)
   ```

   and Prettier over the eight frontend files it changed:

   ```bash
   corepack pnpm@9.15.9 --dir frontend exec prettier --check e2e/u8-complete/isolation.spec.ts e2e/u8-complete/helpers.ts e2e/u8-complete/cutover.spec.ts e2e/u8-complete/accessibility-screens.spec.ts e2e/u8-complete/migration.spec.ts test/u8-complete/notices.test.tsx test/u8-complete/first-sign-in.test.tsx src/u8-entry/entry-panel.tsx
   ```

6. **Kept bytes** (since run 6). U8's loop-back 4 section keeps 45 shared paths byte for byte. `shasum -a 256` over the 45 paths, in the order `~/.docsuri-u8/lead-scripts/bt6_lanes_chain.sh` lists them (its `u8_kept_bytes`), is compared with the first readings' table in U8's code summary. U5's seven kept files are compared the same way by the `kept-bytes` lane of `lb4_u5_lanes.py` (`integration-test-instructions.md`).

The release that the installation deploys is built later, at the installation, by `docsuri-release install <tag>` from a tagged commit (`u8-release-runbook.md`). It is not part of this build.

## Build verification

The build passes when every command above exits 0 and:

- `export_workspace_contract.py --check` reports the canonical schema partition verified, and `generate.py --check` reports `_generated/` matching the schemas;
- every type check is clean;
- the build gate stays within both budgets;
- `migrate` reports `u8-migrated` with the platform store `verified`;
- since run 6, every one of the 45 shared paths and U5's seven kept files reads equal to its recorded SHA-256.

## Troubleshooting

- **A phase refuses with `coverage-after-fixtures`.** U8's coverage needs the realm's synthetic accounts, which `fixtures` uses up. Run coverage on a fresh realm straight after `migrate`.
- **A later phase refuses on its environment's allocation.** A coverage pass uses up the environment's synthetic accounts (U4: "Synthetic account allocation exhausted") or its authentication attempts (U5). So U4's `component` and `integration`, and U5's `component` and browser check, run on fresh environments of their own. The refused environment is kept as a failed prerequisite and archived; it is never reset or relabelled.
- **U1's bootstrap or U7's setup is refused within about a second.** Both tools wait with `docker exec pg_isready` over the container's Unix socket, which can pass against the image's temporary init server, and then connect at once. Keep the refused environment as a failed prerequisite and rerun the lane on a fresh environment (`integration-test-instructions.md`). Run 6 had five such refusals (U1 twice, U7 three times) against run 5's two. A wait over TCP would close the race; changing U1's or U7's tool waits for the maintainer.
- **Realm B is missing phases.** `verification-run` runs `restore-paths` and `browser-recovery`, the corpus, then the other journey phases and both restarts (`scripts/u8_phases.py:106-114`). It never runs `compatibility`, `performance` or `capacity-burst`, so chain those after it, in that order. The operations lane runs alone on a fresh realm of its own, because the disk it uses would leave the recovery journey (J09) too little.
- **A corpus paper is refused: `refused-by-database-time-limits`.** One paper's import stalled past the database's time limits during the corpus load. It happened in run 5's Q5 measurement (2026-11-19, the first `--corpus only` pass) and at U8's checkpoint verification before run 6 (2026-11-23, after 161 of 600 papers; four read-only helper agents had started 30 to 45 s earlier, and causation is not proven). Keep the realm as a failed run, never relabelled, and rerun the whole run alone on a fresh realm, with nothing else running: no helper agents, no other workflow, no other lane. Run 6's checkpoint rerun passed that way.
- **A phase waits or refuses on the runner lock.** U8's phases share `/tmp/.docsuri-u8-runner.lock`; run one at a time.
- **A part runs past its 300 s bound.** Check `uptime` and the busiest processes. When something other than the run loads the Mac, wait and rerun once on a fresh realm. Bounds are never raised.
- **J09 refuses for disk.** macOS swap files grow during long runs and take disk. Remove archived test copies (stopped realm containers and volumes), then `colima ssh -- sudo fstrim -v /mnt/lima-colima`. A restart clears swap but also empties `/tmp`, where the preserved evidence folders live. Since run 6, each chain keeps its own output and every driver's output under `$HOME` (`~/.docsuri-u8/final-evidence/` and `~/.docsuri-u8/lead-scripts/final-lanes/bt6-chain-20261123/`), and the lane folders a run leaves in `/tmp` are copied into `~/.docsuri-u8/final-evidence/` when the run ends.
- **Docker cannot find credentials.** Keep `DOCKER_CONFIG` pointing at `$HOME/.docsuri-u8/docker-config`; the default config names a keychain helper that is not installed.
- **Never in `frontend/`:** `next build`, `pnpm build`, `pnpm e2e` or Playwright's default configuration. The live v1 serves from that folder. A Vite build with `--outDir` under `/tmp` is safe.
- **Rebuilding the AI-DLC engine.** Run `bun build --compile` from `~/aidlc-fix`, not from this repository: it leaves temporary `.<hash>-00000000.bun-build` files in the folder it runs from.
