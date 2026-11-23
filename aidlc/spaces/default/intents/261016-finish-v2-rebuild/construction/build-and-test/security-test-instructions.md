# Security test instructions

U8 hosts every Unit, so its security requirements carry those of the whole application: owner isolation and authorization (NFR1), consent (NFR2), credentials, keys and data at rest (NFR3), integrity and idempotency (NFR4), accessibility (NFR5) and $0 operation (NFR6). U5's and U6's own requirements still apply inside the composed application unchanged. This file says how each required security check runs here, and which ones need the real arrangement at the installation.

## Sources

- U8 `nfr-requirements/security-requirements.md` (§ Required verification), `nfr-design/security-design.md` (§ 15, D1–D14), `infrastructure-design/cicd-pipeline.md` (§ 11), and `code-generation/code-generation-plan.md` ("Completion and evidence boundaries") with its `unit-test-instructions.md` and `code-summary.md`.
- U5 `nfr-requirements/security-requirements.md`; U6 `nfr-requirements/security-requirements.md` (§ Required verification).
- CI: `.github/workflows/ci.yml` (the security and closure-audit jobs) and `.github/workflows/codeql.yml`.

## Framework setup and configuration

- **Behaviour tests:** pytest in each Unit's layer folders and Playwright in the browser journeys, on the realms `build-instructions.md` describes. Owner roles, owner filters and the session guard are real; providers are stand-ins that refuse the production profile.
- **U8's security journeys:** `SEC` (`frontend/e2e/u8-complete/security.spec.ts`: a cross-site provider arrival through the identity stand-in on `https://localhost:18114`, a provider's error return, and a reset link opened in a browser that did not ask for it) in the `security` phase, with the phase's backend half (`SECURITY_TESTS` in `scripts/u8_phases.py`: the route inventory, the production headers and forged forwarded headers, the sign-in limits and the cross-site arrival); J03, J12 and J13 in `browser-isolation`; both inside `verification-run`.
- **Exposure tests:** every logger captured at DEBUG level, and the realm database's server log read after forced failures (a unique violation on an email, an invalid input carrying a test value, a failed statement).
- **Dependency audit (SCA):** pip-audit 2.10.1 under Python 3.13.7 over each project's frozen export, and `pnpm audit --prod --audit-level high` for the frontend.
- **Secret scan:** gitleaks v8.21.2 (`ghcr.io/gitleaks/gitleaks:v8.21.2`, already in Colima) over the files the branch delivers, with findings redacted and the repository's `.gitleaks.toml` allowlist.
- **Static analysis (SAST):** CodeQL runs in GitHub (`codeql.yml`) on the pull request. It has no local equivalent here, and it belongs to the CI Pipeline stage.
- **Dynamic checks:** no scanner. The browser-boundary tests (D7) send forged forwarding headers and other host names through the public stand-in. The same probes run through `docsuri.rvnnt.dev` in the maintainer-only window.

## How to run

### Behaviour tests

They run inside the phases the other instruction files list: U8's `component`, `integration`, `operations` and `coverage`, U8's `verification-run` (`security`, `browser-isolation`, `accessibility`), and U5's and U6's `coverage` and `browser` phases. No separate command exists, so no security check can be skipped by leaving a command out.

### Dependency audit

Exports go to a private folder outside the checkout, so the audit writes nothing into the repository:

```bash
AUDIT_DIR=$(mktemp -d)
for project in backend ingestion ops; do
  extras=""; [ "$project" = ingestion ] && extras="--all-extras"
  uv export --project "$project" --frozen $extras --no-dev --no-emit-local -o "$AUDIT_DIR/$project.txt"
  uvx --python 3.13.7 pip-audit==2.10.1 -r "$AUDIT_DIR/$project.txt"
done
corepack pnpm@9.15.9 --dir frontend audit --prod --audit-level high
```

- backend, ingestion and ops are blocking, as in CI's security job.
- CI's closure audit also exports every other project. Four of them (`backend/modules/discovery`, `backend/modules/summarization`, `platform_integrity`, `shared/python`) are reported but not blocking, because their CVE disposition (CVE-2026-82049, CVE-2026-85091) is an open operator item.
- `uv export --frozen` reads the lock files only. It changes no virtual environment and no lock.
- On 2026-11-15 the maintainer left pip-audit to CI's security job for this stage, because it calls PyPI's vulnerability service. `pnpm audit` runs here; its call to npm's registry was approved earlier.

### Secret scan

CI scans its clean checkout. Locally, the files git would deliver are copied into a private folder under `$HOME` (Colima mounts only `$HOME`), so gitignored local files such as environment files and virtual environments are never read:

```bash
SCAN_DIR=$(mktemp -d "$HOME/.docsuri-u8/scan.XXXXXX")
git ls-files -z --cached --others --exclude-standard \
  | python3 -I -c "import os,sys; d=sys.stdin.buffer.read().split(b'\0'); sys.stdout.buffer.write(b''.join(p+b'\0' for p in d if p and os.path.lexists(p)))" \
  | rsync -a --from0 --files-from=- ./ "$SCAN_DIR/"
find "$SCAN_DIR" -type f | wc -l
DOCKER_HOST=unix://$HOME/.colima/default/docker.sock DOCKER_CONFIG=$HOME/.docsuri-u8/docker-config \
  docker run --rm -v "$SCAN_DIR:/repo" ghcr.io/gitleaks/gitleaks:v8.21.2 detect --source /repo --no-git --redact -v --exit-code 1
rm -rf "$SCAN_DIR"
```

The `python3` filter drops paths the git index still lists but that no longer exist. It was added in run 4 (2026-11-17): unfiltered, rsync stopped with exit 23 on a deleted file still in the index, and macOS's rsync has no `--ignore-missing-args`. Run 5 (2026-11-19) ran this command, its output to `~/.docsuri-u8/final-evidence/bt-gitleaks-20261119.log`, which records "no leaks found"; the 4,801 files and exit 0 went to the chain output, lost in the Mac's restart of 2026-11-21, and are kept in the coordinator's notes (`~/.docsuri-u8/lead-scripts/l2-records/l2-build-notes.md`).

Run 6 (2026-11-23) ran the same command inside the lanes chain (`~/.docsuri-u8/lead-scripts/bt6_lanes_chain.sh`, its `gitleaks_scan`), its output to `~/.docsuri-u8/final-evidence/bt-gitleaks-20261123.log`: 4,815 files, exit 0, "no leaks found" (scan completed in 6.01 s). The file count and exit code are also in the chain's own output, kept as `~/.docsuri-u8/final-evidence/bt6-lanes-chain-output-20261123.txt`.

## Required checks and where each runs

| Requirement | Proven here | Proven at the installation, and the stage that owns it |
|---|---|---|
| NFR1.1 server-side authority; another owner's identifier answers like a missing one; signed-out callers read only the public projection | U8 integration tests; J03, J12, J13; U5's and U6's owner-isolation tests. Not all of it in run 6: Step 43's browser isolation is still Not Met, because memberA holds no ORCID link, MFA enrollment or lifecycle request, so three reads by identifier are asked with a made-up identifier on both sides, and eight probed rows are marked not claimed; BR10.3's journeys row, Not Met in run 5, is Met in run 6. The clearing of private state at an owner change or a session's end ran in full only in jsdom (NFR1.1, Unverified); see `test-results.md` | — |
| NFR1.2 and NFR1.3 the operator surface only for administrators with current MFA; maintainer-only and migrated-only admission | U8 component and integration tests; J12. Since run 6, loop-back 4's Chromium checks of `/search` and of the password-reset and reactivate proof forms under maintainer-only pass. NFR1.3 itself is Not Met in run 6: the email cancellation page, `GET /api/v2/topics/email-unsubscribe/{token}`, served by U8's host, shows no maintenance notice. The required case for NFR1.3 is Not Met too: the realm's own maintainer-only window with nothing staged (Step 170(b)) is not built. See `test-results.md` § Not Met | the maintainer-only window, and since run 6 NFR1.3's admission row: Deployment Execution |
| NFR1.4 and NFR4.2 decisions and effects only through bound PlatformControl operations with receipts | U8 operations tests; U7's lane | — |
| D1 session lengths, the 501st account refused, profiles refusing each other's realm | U8 component tests | — |
| D2 sign-in limits per address, per email and overall; IPv6 /64 buckets; keyed digests only | U8 component and integration tests | a forged `CF-Connecting-IP` through Cloudflare: Deployment Execution |
| D3 cross-site arrivals with `Strict` cookies, the code out of the address bar, a provider's `error` return | `SEC` through the identity stand-in on another site. Not all of it in runs 5 and 6: SEC shows the ORCID error return and an address with no provider answer in Chromium, but the repeated and missing state, code and flow cases and an error beside a complete answer ran only in jsdom, so D3's provider-error return is Unverified; see `test-results.md` | real Google and ORCID sign-in: Deployment Execution |
| D7 the browser boundary: forged forwarding headers from loopback, `127.0.0.1` reaching only health routes, the § 4 headers, cacheable content-hashed files only, other host names refused | `integration/test_boundary.py`, through the public stand-in and on loopback | the shell byte-for-byte through the public address: Deployment Execution |
| D11 log rotation skips links, pipes and hard links; 14-day retention; owner and mode 0600 | the `arrangement` folder (macOS with sudo) | `ci.yml`'s `macos-filesystem` job: CI Pipeline |
| D12 the email allowance: 61st digest waits, 2,700 a month stops all mail, reservations, idempotency keys | U8 component tests; U5's tests | — |
| D14 pgvector in every new database; restores without the superuser | U8 database and operations tests | — |
| NFR3.1 keys only in the profile's key folders, never regenerated silently | U6's and U2's key tests; U8's restore paths | — |
| NFR3.9 no secret, token, password, hash, email address or private text in any log, observation, incident, parity report or installation log; nothing quoted in PostgreSQL's server log | the exposure tests; U6's token tests | — |
| NFR3.13 no disposal date earlier than 14 days; a forged ledger record deletes nothing early | U8 backup agent tests | — |
| NFR4.4 the second migration pass imports and updates nothing | J10 | the dry runs on real data: the Operation stages |
| NFR2.1–NFR2.3 consent at first sign-in; rehearsal recipients only; withdrawal racing in-flight work | J05, J08, J10; U5's consent tests | live mode after the first approval |
| U6: tokens never cross operations, never leave in logs or errors, only `https://api.notion.com`, content hash bound, no new key after a loss | U6's integration tests against the HTTP-level fake Notion | the first export on your decision: Deployment Execution |
| D4, D5, NFR1.5: in-person commands always ask for the password; your login account cannot read the operator's items; real sudo refuses the service and scheduler accounts | the logic with fakes, in U8's operations tests | the installer's verification in person (Workflow 20): Environment Provisioning |
| NFR1.6 fixed commands refuse arguments outside their closed set and run with a cleaned environment | U8 operations tests with fakes | real sudo at the installation: Environment Provisioning |
| NFR3.3 SCRAM only; no login through a stand-in listener on 15432; no TCP login as the superuser | the logic with fakes. Since run 6, loop-back 4's tests assert `require_auth=scram-sha-256` at the operator tool's connections, credential release's value and the production tool's two `pg_restore` strings, and NFR3.3 and its libpq row belong to Environment Provisioning. The required case for NFR3.3 is Not Met: `verify.py:70-71` compares libpq install names as strings, so a path with `..` or a symlink under the runtime that points outside it passes; see `test-results.md` § Not Met | the real instance: Environment Provisioning |
| NFR3.7 and NFR3.8 the Time Machine exclusions and the packet filter, checked by the isolation check | the isolation check's tests with recorded tool output | the installation's step 11 and every 5 minutes after it: Environment Provisioning |
| cicd-pipeline § 11: required checks report; the install's refusals; the first release's tag | the release tool's tests with a fake GitHub API. The lane's four jobs report names of their own, and the install's gate reads only those names, every run of each, from GitHub Actions alone (U8's CP-5) | the release runbook, with branch protection set from its § 2: CI Pipeline, Deployment Pipeline |
| Known-vulnerable dependencies and committed secrets | the dependency audit and the secret scan above | CI's security, closure-audit and CodeQL jobs: CI Pipeline |

## Expected results

- Every behaviour test passes in its phase; any skip or zero-test phase fails.
- pip-audit reports no known vulnerability for backend, ingestion and ops; `pnpm audit` reports nothing at high or critical.
- gitleaks reports no finding in the delivered files.

## Test data and environment

- Every secret is generated per run. No real provider key, token, account, email address or v1 data appears in any test, fixture or scan copy.
- The exposure tests plant known test values and assert their absence; they never print a secret.
- The scan copy holds only the files the branch delivers and is removed after the scan.
