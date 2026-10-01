# G1 / REM-3 Operator Runbook

**As of**: 2026-10-01
**Scope**: the operator-owned residual of the REM-3 corrective unit and the G1 platform-integrity
gate. Everything here needs at least one of: `sudo` / a maintenance window / a risk-acceptance
decision. Nothing here is executable by the agent.

**Sources of truth**
- Gate map and G1 definition: `aidlc-docs/inception/plans/verification-remediation-2026-09-18-workflow-plan.md` (§5, line ~587)
- Supply chain pins and status fields: `ops/platform-integrity/sbom-targets.json`
- Disposition narrative and G1 checklist: `ops/platform-integrity/cve-disposition.md`
- Native/clock/keychain/launchd detail: `aidlc-docs/construction/rem-1-platform-integrity/code/operator-handoff.md`
- This unit's plan: `aidlc-docs/construction/plans/rem-3-corrective-plan.md` (Phase 5, step 18)

**Two hard rules**
1. **No secrets in chat, argv, env, files, or logs.** Where a password is required the tools read it
   from `getpass` or stdin; keep it that way.
2. **Never use `security ... -A`.** `-A` grants *every* application access to the item and defeats the
   purpose-specific ACL. See §5.

Current G1 blockers (from `cve-disposition.md` §"G1 blockers"):

| # | Blocker | Owner action | Operator-actionable |
|---|---|---|---|
| 1 | CVE-2026-85091 — alpine zlib, no upstream fix | exception **or** base refresh | yes |
| 2 | Derived postgres image CANDIDATE → APPROVED | maintenance window | yes |
| 3 | CVE-2026-82049 — python `tarfile`, mitigated in build | accept as mitigated | yes |
| 4 | MinIO image unobtainable | upstream / provider decision | **no** |

Plus: rescans (redis/opensearch/elasticmq), pip-audit SIGABRT disposition, Docker bridge mTLS,
purpose-Keychain ACLs, secret rotation, worker entry-point/launchd verification, live smoke test.

---

## 0. Preconditions

```sh
# root-capable shell for the privileged steps; a normal shell for the rest
sudo -v
id -u                 # expect 501; root steps use sudo
/usr/bin/fdesetup status   # signing/clock provisioning require "FileVault is On"
```

- FileVault: **On** is required by `KeychainReceiptSigner` (`host_encryption_required` otherwise).
  Host was observed **Off** on 2026-09-26 — enable it before §5/§6.
- Colima running for §8: `colima status`.
- Do §1–§4 (supply chain) before evaluating G1.

---

## 1. The three sign-offs (+ MinIO)

These are decisions, not code changes. Each ends by editing a status field in
`ops/platform-integrity/sbom-targets.json` and updating the checklist in `cve-disposition.md`.

### 1.1 CVE-2026-85091 — alpine zlib in the derived postgres image

- **Finding**: High, no upstream fix in alpine 3.21 as of 2026-09-30 (`derivedImages.postgres.remaining`).
- **Option A — time-boxed exception** (compensating controls already true: non-root uid, no gosu,
  network isolation, read-only FS posture). Record in `cve-disposition.md`:
  - the CVE id, the accepted scope (this image only), the expiry/review date, and the compensating controls.
  - set `derivedImages.postgres.status` → `APPROVED` (combines with §1.2) **only after** the exception is written and signed here.
- **Option B — base refresh**: rebuild `ops/platform-integrity/images/postgres-alpine-nosu.Dockerfile`
  on an alpine base carrying zlib 1.3.3+, then **re-scan (§2)** and record the new digest. A new digest
  invalidates the old approval; the R1OP/derived-image verification must be repeated.
- **Evidence to record**: exception text (or new digest + rescan summary), decision date, decider.

### 1.2 Derived postgres CANDIDATE → APPROVED

- Current: `derivedImages.postgres.status = "CANDIDATE_PENDING_OPERATOR_MAINTENANCE_WINDOW"`.
- Prerequisite: §1.1 resolved and §4 bridge mTLS executed.
- Action: in the maintenance window, set `derivedImages.postgres.status` → `APPROVED`.
- **Evidence to record**: status field change + the §4 bridge result.

### 1.3 CVE-2026-82049 — clock observer `tarfile`

- Current: `nativeRuntimes.clockObserver.status = "NATIVE_CLOCK_PROBED_RECEIPT_PENDING"`,
  `scan.state = "BLOCKED"`; the PSF backport `b8f23e307097552eaea2604383a12ab280520d0d` is
  installer-enforced (preimage/postimage) and the sealed-runtime regression passes for `data`/`tar`.
- Grype keys on `nvd:cpe` and therefore keeps showing the finding after the in-build fix.
- Action: **accept as "mitigated in build"** explicitly. Record in `cve-disposition.md` that the raw
  Grype finding is accepted-not-fixed and why (CPE-based match vs. backported bytes), and the
  sealed-runtime regression evidence digest.
- **Evidence to record**: acceptance text + regression digest + decider + date.

### 1.4 MinIO — record as UNOBTAINABLE (no sign-off possible)

- `images.minio.status = "UNOBTAINABLE"`, `scan = "NOT_RUN_NO_ARTIFACT"`. The pin is deliberately
  **not** repointed (provenance). Do **not** substitute a mirror for release evidence.
- Operator decision only if production S3 provider changes. Otherwise: leave recorded, mark the
  sub-item N/A in the G1 checklist with the reason.
- **Guard**: `localDevImages.substituteAssetStore` (SeaweedFS) is `productionInput: false` and must
  never appear in scan evidence.

---

## 2. Image rescans (redis, opensearch, elasticmq)

MinIO is excluded (no artifact). The four pinned digests are in `sbom-targets.json`.

```sh
TOOLS=/private/var/root/docsuri-tools          # unprivileged alternatives are fine; keep the dir private
OUT=/private/var/root/docsuri-scan-20261001

# 1) fetch the pinned scanner archives (Syft 1.52.0 / Grype 0.119.0, digest-checked)
uv run --directory ops python platform-integrity/fetch_tools.py --destination "$TOOLS"

# 2) pull the digest-pinned images first (they are not local yet)
docker pull redis@sha256:c6eabf748fc7a61dbb5a705c78bcf3d6377b1127a97d0ce965c11c44ba46896f
docker pull opensearchproject/opensearch@sha256:4ee82ecb35d837a6186c81aaa64c8a5bce71aa956edbd87f1f684ab56af52c44
docker pull softwaremill/elasticmq-native@sha256:e4580ab9ad1bd5cd37b4ba04911bc5ccc8cd2d9ab4de56ece65acee71c24e05c

# 3) scan each (one output dir per subject; --source uses the same pinned digest)
uv run --directory ops python platform-integrity/scan_sbom.py \
  --tools "$TOOLS" --output "$OUT/redis" --subject redis \
  --source docker:redis@sha256:c6eabf748fc7a61dbb5a705c78bcf3d6377b1127a97d0ce965c11c44ba46896f \
  --profile production
# repeat for opensearch and elasticmq with their digests
```

- Exit `0` = `SCANNED`; exit `2` = INCOMPLETE (`summary.json` carries `reasons`). An incomplete capture
  is **not** a pass.
- Review each `summary.json` + `grype.json`:
  `uv run --directory ops python platform-integrity/summarize_findings.py "$OUT/<subject>/grype.json" --details`
- Record per-image components/findings/blocking in `sbom-targets.json` and the `cve-disposition.md`
  inventory table. New blocking High/Critical findings must get a disposition before G1 can be evaluated.

---

## 3. pip-audit SIGABRT disposition

- `uvx pip-audit==2.10.1` aborts with `SIGABRT`; root cause undetermined. It does **not** block the
  image scan path (Syft/Grype) but blocks Python dependency scanning.
- Action (either):
  - **Fix**: reproduce under a clean `uvx` and capture the abort; try a newer `pip-audit`, or run under
    a plain venv; if it is a resolver/OSV-cache crash, document the workaround.
  - **Document as non-blocking**: record the exact command, the SIGABRT, why it is independent of the
    image gate, and what compensates (frozen locks + Syft/Grype on images). Put it in
    `cve-disposition.md` §"pip-audit".
- **Evidence to record**: command, output, decision.

---

## 4. Docker bridge mTLS validation (derived postgres)

The loopback mTLS harness is `platform_integrity/tests/test_postgres_mtls.py` (gated on
`REM1_TEST_PG_DSN` + `REM1_TEST_CONTAINER`). **The fixture hard-codes `CONTAINER ==
"rem1-test-pg-20260924"`, host `127.0.0.1`, port `15439`, database `rem1_test`** — use exactly those
names, not an arbitrary container name. It currently proves **loopback**; G1 asks for the endpoint
validated **over the host bridge** (the published port traverses the bridge).

```sh
# 1) user-defined bridge (not the default bridge), so DNS/network behaviour matches production-ish use
docker network create docsuri-g1-bridge

# 2) run the derived image on that network with the pinned digest + exact DSN the fixture asserts
docker run -d --name rem1-test-pg-20260924 --network docsuri-g1-bridge \
  -e POSTGRES_DB=rem1_test -e POSTGRES_USER=rem1_test -e POSTGRES_PASSWORD=rem1_test_local \
  -p 127.0.0.1:15439:5432 \
  docsuri/postgres-alpine-16.15-nosu@sha256:ccbe2a110992a5b602afdd4a28a45f184de67308d4e80284c0b2329a10cb0e2e

# 3) run the harness against that container (it installs its own CA/server cert and HBA, via docker cp)
#    note: the platform_integrity suite runs from its own project dir
REM1_TEST_PG_DSN='postgresql://rem1_test:rem1_test_local@127.0.0.1:15439/rem1_test' \
REM1_TEST_CONTAINER=rem1-test-pg-20260924 \
  uv run --directory platform_integrity --extra api --extra postgres python -m pytest \
  tests/test_postgres_mtls.py -v

# 4) teardown
docker rm -f rem1-test-pg-20260924 && docker network rm docsuri-g1-bridge
```

**Run 2026-10-01 (agent):** network `docsuri-g1-bridge` (driver `bridge`,
id `ac30303185f6b44a1ef69bc461077ed652d4db7062f5843324c29987ca7a3062`); container
`rem1-test-pg-20260924` attached at `172.19.0.2` on the pinned image digest
`docsuri/postgres-alpine-16.15-nosu@sha256:ccbe2a110992…0e2e`. Harness result:
`tests/test_postgres_mtls.py` → **1 passed** (full client-certificate login succeeds; wrong-CA is
denied). Exited container `rem1-test-pg-20260924` was renamed `…-bak` to free the pinned name.

- Success = real TLS handshake, `cert clientname` → `session_user`, read-only transaction enforced,
  wrong-CA rejected, over the bridge network with the published port.
- **Evidence to record**: pass/fail, image digest, date. Then complete §1.2.

---

## 5. Purpose-Keychain ACLs **without `-A`**

Provisioning is done by `provision_receipts.py` (root) + `issue_receipt.py` (signer). The provisioner
creates the item through `SecKeychainItemCreateFromContent` with an ACL bound to the signer, so **the
operator must not add `-A`** at any point.

### Do (root, maintenance window)

```sh
# stage 0: FileVault must be On
sudo /usr/bin/fdesetup status | grep -q "FileVault is On" || echo "BLOCKED: enable FileVault first"

# stage 1: root-side provisioner (prompts twice via getpass; nothing lands in argv/env/files)
sudo uv run --directory ops python platform-integrity/provision_receipts.py \
  --profile test --release r1-clock-20260927 \
  --key-id receipt-key-1 \
  --issuer "$(uv run --directory ops python -c 'import sys; print(sys.executable)')" \
  --capability nts_clock --days 1

# stage 2: issue (unprivileged; unlock via stdin, re-locks in a finally)
printf '%s\n' "$KEYCHAIN_PASSWORD" | uv run --directory ops python platform-integrity/issue_receipt.py \
  --profile test --release r1-clock-20260927 --capability nts_clock --days 1 \
  --keychain-password-stdin

# stage 3: verify
uv run --directory ops python platform-integrity/preflight.py \
  --root <repo root> --estimated-peak-bytes 0 \
  --profile test --release r1-clock-20260927 --evidence <evidence.json>
```

- The provisioner refuses a silent replace (`FileExistsError`) and refuses to bind capabilities other
  than `nts_clock` to installed state — that is intended.
- Ownership/modes it produces (test profile): sign/ `_docsuri_r1t_sign` 0700; `sign/<release>--<key_id>.keychain-db`
  0600; `receipt-policy/*.json` root 0444; `receipt-public/<release>/` sign 0755. Production uses
  `--profile production` (`rem-1`, `_docsuri_r1_*`).

### Don't

- **Never** `security add-generic-password -A` or `security import ... -A`. If you must touch the
  keychain by hand (you normally should not), grant a single binary with `-T /absolute/path/to/binary`
  and no `-A`.
- Never place trust keys inside the evidence bundle (rejected: `evidence_invalid_or_contains_trust`).
  Trust comes only from the root-owned 0444 policy.
- Never put the signing key or password in a file, argv, or env.

**Evidence to record**: provisioner JSON (`state=PROVISIONED`, `policySha256`, `keychain`,
`publicKeySha256`, `trustedWindow`), issuer file paths (`*.receipt.json`, 0444), preflight
`provenCapabilities`.

---

## 6. Secret rotation

Two rotatable secrets: the **signing key** (purpose Keychain) and the **keychain password**. Rotation
is explicit removal + re-provision — there is no in-place swap.

```sh
# 1) stop anything using the signer
sudo python -m docsuri_platform_integrity.deployment.launchd uninstall --profile test   # or production

# 2) remove the old artifact set (exact paths ONLY; never glob/recursive deletes)
#    sign/<release>--<old_key_id>.keychain-db
#    receipt-policy/<release>.json
#    receipt-public/<release>/ (the published receipts for the retired key-id)

# 3) re-run §5 stages 1–3 with a NEW --key-id (e.g. receipt-key-2)
# 4) re-issue receipts, re-run preflight, confirm the old key-id no longer verifies
```

- Rotation of the **DB TLS / operator identity** material follows the same "remove then re-provision"
  shape via the Keychain/mTLS provisioning in `operator-handoff.md` §9/§6.
- **Evidence to record**: old key-id retired, new key-id + `policySha256`, preflight re-verified,
  date. Do not keep private keys or passwords in the evidence.

---

## 7. Worker entry-point + launchd verification (as root)

Two surfaces: the REM-1/native launchd jobs, and the REM-3 backend purge worker.

### 7.1 launchd (root, maintenance window)

Run these from the `platform_integrity/` project (the `docsuri_platform_integrity` package lives
there); use its `uv run`/venv so the module resolves.

```sh
# render for review (unprivileged), then install (root)
uv run --directory platform_integrity python -m docsuri_platform_integrity.deployment.launchd \
  render <manifest.json> /tmp/rem1-review
sudo uv run --directory platform_integrity python -m docsuri_platform_integrity.deployment.launchd \
  install --profile test /tmp/rem1-review/deployment.json
# replacing an existing deployment REQUIRES --replace (it bootouts the old one first)
sudo uv run --directory platform_integrity python -m docsuri_platform_integrity.deployment.launchd \
  install --profile test <new.json> --replace

# verify each job is actually held by launchd under the expected uid (clock jobs run as 608)
sudo launchctl print system/org.docsuri.rem1.test.nts-observer
sudo launchctl print system/org.docsuri.rem1.test.clock-sample
# expect UserName/GroupName resolution to _docsuri_r1t_clock (608/608)
```

- `install` refuses unless root, realm, accounts and artifact digests all match; it re-verifies itself
  after writing and fails if launchd is not holding the job.
- Uninstall refuses if launchd still holds a job (won't orphan a running process).
- **Evidence to record**: `launchctl print` output showing label + uid, install JSON state.

### 7.2 backend purge worker entry point

```sh
# dry-run against the local stack (Logging publisher fallback when ACCOUNT_EVENTS_BUS is unset)
DATABASE_URL='postgresql+psycopg://rem3_smoke:rem3_smoke_local_only@127.0.0.1:<pg_port>/rem3_smoke' \
ACCOUNT_EVENTS_BUS=docsuri-events \
  backend/.venv/bin/python -m backend.modules.accounts.purge_worker
```

- Confirm it acquires the advisory lock only once per sweep and purges DB rows before object keys.
- **Evidence to record**: worker run output + one purge of a seeded DEACTIVATED account.

---

## 8. Live smoke test on Colima

```sh
ops/local-stack/up.sh          # generates a local PG server cert, brings the stack up, prints real ports
```

- **Port shadowing**: if OrbStack is running it silently intercepts 5432/6379/9200/9324/9000 while the
  containers still report healthy. Either quit OrbStack, or `cp ops/local-stack/env.orbstack-conflict
  ops/local-stack/.env` first (the file is git-ignored). Always use the ports `up.sh` prints.
- Backend live legs:

```sh
DOCSURI_TEST_PG_DSN='postgresql://rem3_smoke:rem3_smoke_local_only@127.0.0.1:<pg_port>/rem3_smoke' \
  backend/.venv/bin/python -m pytest tests/accounts/test_purge_real_postgres.py -v
```

- Known local gap: SeaweedFS S3 auth is **unwired** (`InvalidAccessKeyId`), so the local object-store
  leg of F04 object purge is not functionally exercisable locally; it is exercised by
  `S3ObjectPurger` against a real bucket in production. Do not record the local stack as proving
  off-host object purge.
- **Evidence to record**: `up.sh` port block, the pytest result, and an explicit note that object-store
  purge is production-only.

**Run 2026-10-01 (agent):** `up.sh` brought the Colima stack up, all five services healthy. Ports:
PG `15432`, Redis `16379`, OpenSearch `19200`, ElasticMQ `19324`, SeaweedFS S3 `19000`
(ports shifted for OrbStack shadowing). F04 live leg
`tests/accounts/test_purge_real_postgres.py` → **2 passed** against
`postgresql://rem3_smoke:…@127.0.0.1:15432/rem3_smoke`. **Object-store purge remains production-only**
(SeaweedFS S3 auth unwired locally); this run does **not** prove off-host object purge.

---

## 9. Close-out: record evidence and re-validate

1. Edit `ops/platform-integrity/sbom-targets.json` status fields per §1.
2. Update the `cve-disposition.md` G1 checklist and inventory tables.
3. Re-run the pin check (must pass):

```sh
uv run --directory ops python platform-integrity/validate_supply_chain.py \
  ops/platform-integrity/sbom-targets.json
```

4. Update `aidlc-docs/aidlc-state.md` G1 row and append the evidence to `aidlc-docs/audit.md`.
5. Do **not** mark G4/G5 — they remain `BLOCKED-ON-REM-4` regardless of G1.

### Clean-environment install test

Provisions **only the declared dependencies** in a fresh interpreter, then imports the package and
every adapter — the gate that catches undeclared dependencies (audit defect 3).

```sh
tmp=$(mktemp -d)
uv venv --python 3.13 "$tmp/venv"
uv pip install --python "$tmp/venv/bin/python" "platform_integrity[rem3]"
"$tmp/venv/bin/python" - <<'PY'
import importlib, pkgutil
import docsuri_platform_integrity.adapters as adapters
names = ["docsuri_platform_integrity", "docsuri_platform_integrity.adapters"]
names += [f"docsuri_platform_integrity.adapters.{m.name}" for m in pkgutil.iter_modules(adapters.__path__)]
for n in sorted(set(names)):
    importlib.import_module(n)
print("imported", len(set(names)), "modules, 0 failures")
PY
```

**Run 2026-10-01 (agent):** **20/20 modules imported, 0 failures** after deleting 3 orphaned REM-2
adapter modules (`registry.py`, `cache.py`, `private_userdoc.py`) that failed to import (mutual
circular import; a reference to the removed `contracts.models.DocModel`; and a call to a
non-existent `adapters.ingestion.parse_document`). None were imported by any test or module.

### G1 completion checklist (copy from `cve-disposition.md`)

- [ ] CVE-2026-85091 exception signed, or alpine base refresh + rescan recorded
- [ ] Derived postgres image promoted `CANDIDATE` → `APPROVED`
- [ ] CVE-2026-82049 accepted as mitigated-in-build
- [ ] Redis, OpenSearch, ElasticMQ scanned this cycle (✅ 2026-09-30); new blocking findings dispositioned (❌ 338 pending)
- [x] MinIO recorded as UNOBTAINABLE / N/A (no artifact)
- [x] pip-audit SIGABRT fixed or documented non-blocking (not reproducible; venv drift reconciled → clean)
- [x] Docker bridge mTLS validation executed and recorded (2026-10-01: 1 passed)
- [ ] Purpose-Keychain ACLs provisioned without `-A`; receipts issued and preflight verified
- [ ] Secrets rotated via remove-then-reprovision; old key-id retired
- [ ] launchd jobs verified as root; purge worker entry point verified
- [x] Colima live smoke executed (object-store purge noted as production-only)
- [x] `validate_supply_chain.py` passes on the updated targets
