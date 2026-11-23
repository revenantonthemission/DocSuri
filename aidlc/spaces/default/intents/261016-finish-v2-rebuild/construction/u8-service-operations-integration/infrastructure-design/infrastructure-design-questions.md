# Infrastructure Design Questions — U8 complete service operations and integration

Date: 2026-10-22 (Asia/Seoul)
Unit: u8-service-operations-integration (service). Inputs:

- this Unit's NFR design: [security](../nfr-design/security-design.md), [performance](../nfr-design/performance-design.md), [scalability](../nfr-design/scalability-design.md), [reliability](../nfr-design/reliability-design.md), [observability](../nfr-design/observability-design.md) and [logical components](../nfr-design/logical-components.md);
- the [functional spec](../functional-design/functional-spec.md) (Workflow 20, the installation) and [rules](../functional-design/rules.md) (BR6.5 and BR10.1–BR10.7);
- the active project rules (project.md § Mandated, team.md § Deployment) and CONVENTIONS.md;
- the repository today: `.github/workflows/` (`ci.yml`, the per-unit lanes U1–U7, `release.yml`), the remote branches and tags, and `ops/server/`.

This stage turns the design into the infrastructure to build: what runs where, how it is monitored, and how a change travels from a commit to production. Most of it is already fixed by your earlier answers; the two questions below are the ones that are not. Each question offers the design I recommend as A. Answer with a letter, or in your own words under X.

## Settled from the records (no question)

These follow from decisions on record or from the repository as it is. If one should change, say so under X of the closest question.

- **Environments.**
  - Each unit's synthetic realm on this Mac, for development.
  - The CI lanes on GitHub's runners.
  - The composed realm: the whole application on synthetic data. It runs in CI, and on this Mac for the performance phase.
  - The production profile in rehearsal mode (the soak), then in live mode.

  The composed realm and rehearsal mode play the part of staging, so no separate staging machine is added.
- **Infrastructure as code.** Every file of the arrangement is a template in the repository, rendered and installed by one installer you run in person as root: the launch job definitions, the sudo rules, the packet filter anchor, the tunnel configurations, PostgreSQL's configuration and `pg_hba.conf`, and the rotation list.
  - Run twice, the installer changes nothing the second time.
  - Its plan mode shows every change before it applies one.
  - Drift is caught by the isolation check's digests every 5 minutes.
- **The complete verification lane.** It runs on GitHub's Linux runners for every push and pull request to `develop` and `main`, beside the per-unit lanes, which stay as they are (BR10.4).
  - PostgreSQL 16 with pgvector runs in a pinned container.
  - A deterministic stand-in embedder gives the production-size corpus its vectors, because the real models run only on this Mac.
  - The tests that need macOS and root (the packet filter rules, the sudo rules, launchd, `tmutil` and the rotation job) run on GitHub's macOS runner, which allows sudo.
- **No production secret enters CI.** CI uses the synthetic realm and its stand-ins. `GITHUB_TOKEN` only creates the tag and the GitHub Release.
- **Branch protection.** `develop` and `main` require the CI jobs and the complete verification lane to pass before a merge. That is free for a public repository.
  - The fork has no `main` yet; its newest tag is v1.19.0. The first v2 release creates `main` from `develop`'s release commit and is tagged v2.0.0, a major release for the breaking v2 contracts (CONVENTIONS.md).
  - Later releases keep `release.yml`'s version from conventional commits.
- **The performance phase** runs on this Mac against the composed realm, before a release reaches production, because the targets are measured on this Mac's hardware and pinned versions (NFR8.11). It takes about 20 minutes, while production keeps serving.
- **Settings by hand.** Cloudflare's settings for the hostname and healthchecks.io's three checks are set by hand, and recorded in the installation log without any secret. No Cloudflare or healthchecks.io API token is kept on this Mac. The public-address byte comparison catches a changed edge (security-design.md § 4).
- **Monitoring stays local.** Observations live in the database, and logs, evidence, latency summaries and the availability record live in files. 운영 is the dashboard, and healthchecks.io the only outside service. No metrics server is added.

## Q1. How does a release reach production?

The records point two ways:

- **The project rule.** project.md § Mandated says "ALWAYS deploy continuously to production on merge — every commit passing CI auto-deploys to production". team.md says the same. That was affirmed on 2026-10-02, for the earlier Phase 7 frontend.
- **U8's approved design.** Production runs from a root-owned release folder that only the release path changes, with administrator rights (BR6.5). An upgrade is an in-person step (NFR3.11). Your answers to Q18 and Q19 of NFR Requirements kept every unattended path away from the code v2 runs.
- **The repository today.** Merging `develop` into `main` already cuts the version tag and the GitHub Release automatically (`release.yml`). Its deploy job was removed along with AWS, and v1 is deployed by hand.

A. In person. A merge into `main` keeps cutting the tag and the GitHub Release by itself. You then install that tag on this Mac with one in-person command, which:
   - checks that the complete verification passed for that exact commit (BR10.5);
   - runs the performance phase on this Mac, about 20 minutes;
   - takes a pre-release backup;
   - routes the public address to the maintenance notice, applies the owners' migrations, puts the new release in place, starts v2, and routes back once v2 is ready.

   The continuous-deployment rule would then be read as not covering this Mac's production. That reading is recorded through the learnings step at U8's checkpoint, which you approve there.
B. Automatic. A root job on this Mac installs each new `main` tag by itself, with the same steps, accepting only tags signed with a key you hold. The rule then holds as written. But it adds an unattended path that changes the code v2 runs: a compromised GitHub account or signing key could ship code here while nobody is present.

X. Other (please specify)

[Answer]: A

## Q2. How is a failed release undone?

A release can fail after it is in place, for example when v2 does not become ready, or a check fails right after the start.

A. Keep the previous release beside the current one.
   - The installed release stays in `/Library/DocSuri/release/`, and the one before it in `release-previous/`.
   - Every owner migration is written expand-then-contract across two releases, so the previous release still runs on the new schema.
   - If v2 is not ready within 10 minutes of the start, the same in-person command switches back on its own: it puts the previous release in place, restarts v2 and routes back, all in a few minutes.
   - The pre-release backup stays as the last resort.

   The cost is about 1 GB more on the internal disk for the kept release, and owners' migrations must stay backward compatible for one release.
B. Keep no previous release. A failed release is undone by a production restore from the pre-release backup: up to 2 hours, and any writes made after that backup are lost.

X. Other (please specify)

[Answer]: A

## Consolidated Summary Confirmation

- **Q1 — a release reaches production in person.**
  - A merge into `main` keeps cutting the tag and the GitHub Release by itself.
  - You install the tag on this Mac with one in-person command. It checks that the complete verification passed for that exact commit, runs the performance phase on this Mac (about 20 minutes), takes a pre-release backup, routes to the maintenance notice, applies the owners' migrations, puts the new release in place, starts v2 and routes back once v2 is ready.
  - The continuous-deployment rule is read as not covering this Mac's production. That reading is recorded through the learnings step at U8's checkpoint, for you to approve there.
- **Q2 — a failed release is undone by the kept previous release.**
  - The previous release stays in `release-previous/`, and every owner migration is expand-then-contract across two releases.
  - If v2 is not ready within 10 minutes of the start, the same command switches back by itself in a few minutes. The pre-release backup stays as the last resort.
  - This costs about 1 GB more on the internal disk.
- **Settled from the records:**
  - the environments: unit realms, the CI lanes, the composed realm, and the production profile in rehearsal, then live mode;
  - one idempotent installer, with a plan mode, for every file of the arrangement, and drift caught by the isolation check;
  - the complete verification lane in CI, with pgvector in a pinned container, a stand-in embedder, and the root-needing tests on GitHub's macOS runner;
  - no production secret in CI;
  - branch protection on `develop` and `main`, with the first v2 release creating `main` and tagged v2.0.0;
  - the performance phase on this Mac before each release;
  - Cloudflare's and healthchecks.io's settings by hand, with no API token kept;
  - monitoring kept local, with 운영 as the dashboard.

Does this all look correct before I generate the artifact?

- Looks correct
- Request changes

[Answer]: Looks correct
