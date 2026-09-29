# REM-1 Platform Integrity — Code Generation Plan

**Stage**: CONSTRUCTION / Code Generation, Part 1 — Planning  
**Unit**: REM-1 (`rem-1-platform-integrity`)  
**Date**: 2026-09-24  
**Status**: R1CGR1=A approved (2026-09-24); Part 2 in progress.  
**Workspace root**: repository root, brownfield; application code remains outside `aidlc-docs/`.

## 1. Approved scope and authority

Inputs: remediation Requirements `verification-remediation-2026-09-18.md` (F06/F08/F13), FR-52/RJ-AC12; User Stories `US-R4`, `US-R5`; Units Generation UGR1=A; Functional Design R1FDR1=A (E-R1-01~24, FL-R1-01~08, BR-R1-01~22, PROP-R1-01~16); NFR Requirements R1NFRR1=A (NFR-R1-01~24, TD-R1-01~17, EV-R1-01~09); NFR Design R1NDR1=A (PAT-R1-01~12, LC-R1-01~17, VAL-R1-01~18); Infrastructure Design R1IFR1=A (R1IF1=B Colima, R1IF2=A owned removable drive, R1IF3~10=A). Follow `aidlc-docs/construction/shared-infrastructure.md` for shared-resource ownership.

REM-1 is an **independent versioned deployable**: R1C read-only evidence/health daemon, R1R explicit runner/CLI and scoped helpers, OBS contract. Domain owners keep authority over their schemas and mutations. REM-2/3/4 supply their own local OBS/health/queue/recovery evidence later; G1 does not mark US-R4/5 or RJ-AC12 globally complete. No public user-job API is created in REM-1.

The approved single-Mac/zero-paid-infrastructure constraints apply. Code generation produces install, backup, cutover and restore artifacts; executing privileged host changes, FileVault enablement, container-runtime switchover, destructive data repair or a full corpus rebuild remains behind the separately recorded preflight/approval and Build-and-Test evidence gates. Drive alias, capacity and daily availability are required operator inputs; the implementation must not assume values.

## 2. Existing source and new code locations

| Boundary | Existing source to modify / new location | Contract |
|---|---|---|
| Independent Python unit **(new)** | `platform_integrity/pyproject.toml`, `platform_integrity/uv.lock`, `platform_integrity/src/docsuri_platform_integrity/contracts/{models.py,codec.py,ports.py}`, `domain/{registry.py,run.py,gate.py,bindings.py,supply_chain.py}`, `application/{evidence.py,verification.py,supervisor.py}`, `adapters/{postgres.py,filesystem.py,authority.py,keychain.py,clock.py,scanner.py,telemetry.py}`, `api/{app.py,router.py}`, `cli/__main__.py`, `platform_integrity/tests/` (module-relative paths under the package `src/` prefix) | Python 3.13, immutable wheel and separate R1C/R1R/tool closures (TD-R1-01, C0→C3) |
| Migration ownership **(existing)** | `backend/migrations/{__init__.py,__main__.py}` plus new `backend/migrations/registry.py`, `backend/app.py`, `backend/tests/` | One explicit ordered registry; existing SQL stays with its domain; read-only check never creates a ledger (F08) |
| Shared contract **(existing)** | `shared/{dtos,events,vector-spec}/`, `shared/python/tools/generate.py`, `shared/python/src/docsuri_shared/_generated/`, `shared/python/tests/` | Local schema catalog, versioned consumer/visibility manifest and complete generated Python wire; no network resolution |
| Frontend contract **(existing)** | `frontend/scripts/gen-types.mjs`, `frontend/types/generated/`, `frontend/types/.schema-raw/`, `frontend/test/` | Build-consumed TypeScript wires and explicit view adapters, offline `$ref` closure, non-zero on any target failure (F13) |
| Frozen inventory/CI **(existing)** | `backend/`, `ingestion/`, `ops/`, `shared/python/`, `backend/modules/{discovery,summarization}/` lock/manifest files; `frontend/{package.json,pnpm-lock.yaml}`; `.github/workflows/ci.yml`; `backend/docker-compose.yml` | Patched resolved occurrences, pinned images/tools, actual inventory/SBOM and fail-closed audit (F06) |
| Host assembly **(existing/new)** | `ops/server/{run.sh,install.sh,README.md}`, `ops/local/backup-db.sh`, new `ops/platform-integrity/` scripts/config/test fixtures | Scoped launchd roles/Keychain/CA/clock, isolated rehearsal, Colima transition and removable-drive recovery. Approved C-5/NFR-A1/RES-10 intent was back-synced to `aidlc-docs/inception/requirements/requirements.md` in Part 1 |
| Code summary **(documentation only)** | `aidlc-docs/construction/rem-1-platform-integrity/code/code-summary.md` | Implemented paths, limitations, EV/VAL/PROP evidence and remaining G2~G5 responsibilities |

Do not copy the old migration basename ledger or curated TS types into a competing SSOT. Generated outputs only activate after complete validation; an existing unmanaged generated tree is not silently treated as verified.

### Current hazards guiding sequencing

- `backend/migrations/__init__.py` identifies scripts by **basename**; `001` names collide across modules. `pending_migrations()` creates the tracking table during a purported check. Startup and CLI use different path lists; fresh DB evidence/glossary are missed. Legacy rows need explicit owner/target/definition reconciliation, not invented historical checksums.
- `frontend/scripts/gen-types.mjs` skips a failed remote library `$ref` yet exits successfully, while `types/generated/` is the actual build-consumed curated tree. Python generator uses remove/copy publication rather than an atomic head.
- `.github/workflows/ci.yml` covers PR dependency diffs rather than every frozen installed occurrence; Compose contains mutable tags and example credentials. Existing launchd wrappers source a broad `.env` and mutable repository venvs.
- R1IF1=B requires a verified **OrbStack→Colima** data-plane export/restore/cutover with no assumption of double VM space. R1IF2=A requires drive fact collection; FileVault was Off at last observation. The host must not be reconfigured merely to run tests.

## 3. Part 1 planning progress

- [x] Read the current remediation requirements, story/unit map, approved FD/NFR/Infrastructure artifacts and extension configuration.
- [x] Inspect the existing migration, generator, frontend, CI, Compose, launcher and backup seams; identify files to modify versus new paths.
- [x] Define the ordered C0→C3 unit plan, security/rollback boundaries, tests, and G1 versus G4/G5 completion criteria below.
- [x] Review decision and story traceability (US-R4/5, F06/F08/F13, RJ-AC12, LC 01~17 and PROP 01~16), content format (Prettier Markdown parser/debug-check), step count (17) and readiness for plan approval; `git diff --check` passed.
- [x] Record explicit Part 1 plan approval (`R1CGR1`) before implementing Part 2. User: "R1CGR1: A", 2026-09-24T10:41:57Z.

## 4. Part 2 — numbered implementation steps

Each step is completed and checked **in the same interaction** that performs it; record the relevant targeted verification before advancing. Steps are sequential unless a step explicitly says its work can be staged together. Existing files are edited in place, not duplicated.

- [x] **Step 1 — Freeze baseline and reproduce F06/F08/F13.** Baseline HEAD `32a424d1` in isolated worktree `rem1-20260924`, frozen backend/frontend installs; no production credentials loaded. F08 readonly inspection regression failed on emitted CREATE, registry/apply-authorization tests failed on missing new interfaces; F13 generator returned 0 for missing catalog (test failed). Backend frozen audit found anyio 4.14.0 and cryptography 49.0.0 advisories. Scanner incomplete-report regression was introduced with the new pure API (initial import failure, then behavioral pass); additional collision/consumer/scanner tests remain in downstream steps. Trace BR-R1-01/03/13~18; F06/F08/F13; EV-R1-03~05.
- [x] **Step 2 — Scaffold the independent frozen package and contracts.** Created `platform_integrity/pyproject.toml`, frozen `uv.lock`, C0 models/codec/ports and test harness. Strict immutable control values, RFC8785 canonical JSON, duplicate/depth/size checks, lossless integer instants and purpose-bound Ed25519 envelopes. Contract tests: 10 passed; built wheel and imported it in isolated non-editable uv environment with `python -I` and no repository PYTHONPATH. Application/API/adapters/CLI directories populate in their implementation steps. Trace TD-R1-01/07/17; BR-R1-01/02/21.
- [ ] **Step 3 — Implement pure business rules and model tests.** Implement C1 registry/order/dedup/legacy-assurance/reconciliation, RunIntent/attempt/checkpoint, generation/consumer invariants, inventory/advisory normalization, exact exception/current evidence selection and SafeObservation. Domain-specific Hypothesis strategies and independent symbolic models cover PROP-R1-01~16 (round-trip, ordering/invariant, idempotence, oracle, stateful sequences, empty/boundary/invalid commands); keep minimum shrunk counterexamples as examples. Trace FL-R1-01~08, BR-R1-01~22; PBT-01~07/10.
  - [x] Frozen ordered effect plans and stable intent identity, exact target/attempt/fence-bound checkpoint values, conservative commit/abort reconciliation, and an independent interrupted-effect state model implemented. Initial focused tests: 26 passed; final REM-1 suite 80 passed and release run/property subset 25 passed (seed 20260924; 2,000 examples / 200×100 stateful). Conflicting commit-after-abort and canonical/nonwrapping sequence regressions included. Native execution/authority is not inferred from these pure values.
  - [x] Current-evidence reservation/selection, fresh record/key/exception trust, exact mutable-target state binding, safe replayable evaluation cuts and a verification-history state model implemented (PROP-R1-01/14/15). Isolated REM-1 suite 127 passed, release property subset 48 passed, seed 20260924. Signature verification uses real Ed25519 with synthetic owner ports; physical trust providers remain a separate obligation.
  - [x] Offline catalog/ref/export-visibility invariants are shared by the Python generator and REM-1 tool role through the bootstrap-independent `docsuri_schema` namespace. A Node interpreter uses the same 20 conformance vectors. Nested IDs/anchors, cycles, escaped pointers, literal data, missing/duplicate/unsupported targets and visibility violations are covered. Shared suite 112 passed; release catalog/generation subset 39 passed; frontend contract suite 29 passed.
  - [x] Add registry-assurance/capability assessment, exact runtime compatibility, safe observation and lossless inventory evaluation. The 2026-09-25 release-profile subset passes 23 tests (seed 20260925, 2,000 examples). Regressions retain conflicting/undeclared-scope findings, reject unknown exception authority and duplicate scopes, and preserve report-order/duplicate invariance.
  - [ ] Complete the remaining generation-publication/owner-consumer models and full PROP-R1-01~16 trace obligations, including production composition of the new pure assessments.
- [x] **Step 4 — Establish the read-only migration registry.** Explicit owner-qualified registry covers backend and ingestion, including evidence/glossary/mypage. Startup/CLI consume the same registry; check uses readonly Postgres transactions and never creates a ledger. Unregistered/missing/symlinked files fail coverage. Old startup mutation is disabled; legacy RUN_MIGRATIONS_ON_STARTUP no longer authorizes DDL. Registry/domain ordering and namespace checks are tested; actual target/current authority binding remains Step 6. Verification: focused backend migration/DSN suite 13 passed, including six disposable-Postgres tests and actual evidence/glossary HTTP. Trace F08, BR-R1-01~04/09; EV-R1-03.
- [x] **Step 5 — Reconcile legacy history without retroactive proof.** Readonly inspection blocks unresolved basename history and changed definitions. Explicit adoption requires an injected current-authority provider, domain postcondition verifier and receipt; it records ADOPTED_BASELINE and preserves original rows. Disposable PG tests verify refusal, positive domain-checked adoption, legacy preservation and idempotent fresh application. Production authority provisioning remains Step 6/10, not supplied by the test-only authority. Trace BR-R1-04/05/09; PROP-R1-02/03/04.
- [ ] **Step 6 — Implement control/audit schemas and target transaction adapter.** Add owner-reviewed migrations for `r1_control`/`r1_audit`, append-only critical events/outbox and scoped DB command roles. The target adapter keeps a dedicated physical psycopg connection/session lock, canonical fence, durable intent/UNKNOWN before dispatch and step-effect+ledger in one target transaction; commit reply loss remains UNKNOWN until read-only reconciliation. Native source authority/revoke/commit-guard semantics must be demonstrated in an isolated PG+U3/operation adapter; if current source cannot serialize revocation with commit, privileged apply remains unavailable. Add actual two-writer/revoke/rollback fault tests. Trace PAT-R1-02/03/09, VAL-R1-01~03/09/13, EV-R1-03/06.
  - [x] Connect stable RunIntent/attempt/checkpoint transitions to atomic control/audit/outbox transactions and verify lost acknowledgement, CAS competition, and audit failure using disposable Postgres. Expanded to 15 real control-DB tests, included in the final 80-pass REM-1 suite. Also verified partial resume, history-gap refusal and no grant/time renewal on attempt replay. Target/source authority observations are synthetic; native mutation permission, scoped command roles and physical durability remain separate obligations.
  - [x] Add `003_verification_protocol.sql` and explicit evidence reservation/publication transactions. New PENDING heads replace earlier eligibility, late results remain immutable history, retries preserve the original revision, and SQL enforces monotonic heads plus an atomic reservation/head floor. Eleven new actual Postgres cases cover publication races, audit failure, lost acknowledgement, legacy non-promotion and signed read-service composition; the existing evidence transaction regression also passes.
  - [x] Add migration 004 and `PostgresOperatorAuthority` on the target connection, with current grant/target checks and SHARE-lock finalization before migration COMMIT. Nine disposable-PG tests demonstrate revoke/finalize ordering, stale epoch/clock refusal and exact apply-versus-adopt purpose separation. Read/mutation guards reject malformed clock windows and unknown revocation. Twelve backend migration regressions pass. The test clock/DB-owner role is synthetic; durable UNKNOWN-to-dispatch integration and native least-privilege roles remain open.
  - [x] Bind target ledger receipts to the complete target/plan/effect, enforce clock-independent authority and epoch at database finalization, and use canonical target exclusion for both dispatch and bounded read-only reconciliation. Migration 008 preserves legacy rows without inventing v2 provenance. Absence alone cannot prove abort; unproven historical authorization does not become verified success. Real PG regressions reproduce and close the former unsafe cases.
  - [x] Connect acknowledged UNKNOWN/audit/outbox preparation to a one-shot dispatcher and explicit read-only target reconciliation. Verify no target call after failed/lost control acknowledgement, no blind retry, and conservative handling of lost target/control results using actual PostgreSQL fault tests. Focused control/target/dispatch/role and generated failure-cut suite: 81 passed, Hypothesis seed 20260927. Physical source clock/login provisioning remains separate acceptance work.
  - [x] Record PAT-R1-02/03/09 and VAL-R1-01~03/09/13 evidence, regression/property results and remaining native-provider limitations. Thirteen changed source/test/documentation files are byte-identical in the preserved worktree, which reproduces 456 platform passes and Ruff success. Main ops: 98 passed. Step 6 acceptance remains open.
  - [x] Add owner-provisioned approval-revision/login-name/OID bindings, audited bind/revoke commands, and scoped current-source read/finalization without process-role UPDATE rights. Migration 009 enforces the same mapping on direct target commands and at commit; explicit binding rejects privileged/write-capable logins and never reassigns an existing revision.
  - [x] Wire current run/reconcile source authorization and protected-clock/mTLS target-helper composition. Actual non-superuser logins prove guard/apply/observe, principal/purpose denial, both revoke orderings, atomic source audit and role recreation. Focused source/target/dispatch/property/transport suite: 137 passed, seed 20260927. Clock frames and control-store write credentials are test-realm inputs; physical NTS/Keychain and scoped control-store commands remain acceptance work.
  - [x] Run focused/full/property checks and record native proof versus remaining control-store/physical acceptance boundaries. All 17 changed files are byte-identical in the preserved worktree; it reproduces 496 platform passes and Ruff success. Main ops: 98 passed. Focused Markdown parsing and git diff --check pass; the previously recorded historical state-document formatter limitation is not a new failure.
  - [x] Replace owner-backed control-store writes with scoped native command roles and bind target dispatch to acknowledged checkpoint provenance at the helper boundary. Prove the complete co-located PostgreSQL coordination path without owner credentials; physical acceptance is tracked separately below.
    - [x] Add native register/attempt/prepare/reconcile/read commands with current source checks, exact plan/state transitions and atomic audit/outbox; deny process-role raw table writes. Migration 010 and ScopedPostgresRunStore implement this boundary.
    - [x] Require a committed exact preparation and one-use response secret at the native target boundary; preserve lost-ack UNKNOWN and derive completion from native/helper-owned evidence rather than coordinator claims. Migration 011 removes the old signature, requires same-transaction helper finalization, and adds audited source-owner fence advancement. Full main suite: 522 passed; ops: 98 passed.
    - [x] Wire the full scoped helper, exercise actual non-superuser coordination/fault/recovery paths and property parity, and record/synchronize verified results and remaining physical gates. All 19 changed files have byte parity in the preserved worktree, which reproduces 522 platform passes and Ruff success; main ops has 98 passes. Release property and focused Markdown checks pass.
  - [ ] Complete owner-reviewed installation and physical purpose-Keychain/live-NTS/mTLS/guard receipt acceptance for the frozen release. The isolated profile uses synthetic clock frames and does not satisfy this gate.
- [ ] **Step 7 — Build the filesystem generation/journal boundary.** Implement helper-owned immutable generations, full-file manifest verification, same-APFS expected-head atomic replacement and durability receipt, read-only generation pin, GC protection, framed append-only bootstrap journal and metadata-only verified import. Test interrupted seal/head/receipt, torn tail, stale head, late writable descriptors, reader/backup pins and recovery against an isolated APFS root. No rmtree/copy partial activation. Trace PAT-R1-04/05/10, VAL-R1-05~08/14~16, EV-R1-04/07.
- [ ] **Step 8 — Close the offline schema closure.** Inventory *all* declared `shared/` schema resources, local absolute `$id`/`$defs`/fragment references, supported recursion, public/server/internal exports and actual Python/TS consumer imports. Implement a local resolver/consumer manifest in `platform_integrity/`; update `shared/python/tools/generate.py` and `frontend/scripts/gen-types.mjs` to stage complete outputs and fail non-zero for every unresolved/unsupported target. Wire `frontend/types/generated/` to schema-backed wire types and check explicit curated view adapters with positive/negative fixtures. Test disabled network, failed *one* target, unexpected new schema/consumer and crash during activation; existing known-good generation remains intact. Trace F13, BR-R1-13~16, PROP-R1-09~12, EV-R1-04.
  - [x] Add the explicit 13-file schema inventory and Python/internal versus TypeScript/public generation roots. Both generators validate the catalog before staging, preserve schema-shaped literal values, resolve local nested IDs/anchors/JSON pointers, and reject unresolved references and export-name collisions. The emitter's raw-JSON dereferencer is restricted to schema positions with external/file/HTTP resolution disabled. Single-target failure preserves published output; Python drift and TypeScript build-consumption checks pass.
  - [x] Add actual TypeScript/Python AST inventories and source fingerprints; register all 17 discovered view adapters and reject unregistered/missing adapters, ungenerated production body casts, shadowed Python generated imports and snapshot drift. Current inventory: TS 185 imports/64 casts/17 adapters; Python 217 imports/97 local model candidates. Promote 57 existing frontend declarations to the 14th schema resource and regenerate both targets. Shared 115, frontend UI 340 and generator/inventory 32 tests pass; type/drift checks pass.
  - [ ] Complete backend-owner parity/negative fixtures for the promoted wire definitions and local model candidates, plus privileged generation activation/reader/backup proof. AST discovery and generated lineage are not full wire-parity or physical publication proof.
- [ ] **Step 9 — Patch and freeze the real dependency closure.** Update the pinned direct/transitive versions and lock files in *all actual deploy/tool packages* plus frontend, checking API/build compatibility. Pin Compose images by immutable digest and remove committed example production credentials via protected runtime provisioning. Build actual SBOM (CycloneDX; Syft/Grype where applicable), reconcile lock vs installed occurrence per platform/role/extra, validate scan provenance/coverage and block on unknown, unsupported or unapproved critical/high. An unreachable-source exception must match exact artifact/closure/assumptions, approver, expiry and current trust; findings remain visible. Run failure-injected scanner and package audits. Trace F06, BR-R1-17~20, PROP-R1-13/14, EV-R1-05.
  - [x] Capture pinned Syft 1.52.0/Grype 0.119.0 reports for validation/reader/runner environments and the pinned PostgreSQL image. Add bounded capture, explicit failure/unknown/suppression classification and ten parser regressions. Retained PostgreSQL report: 323 findings, 96 High + 2 Critical; blocking fix states 24 fixed/12 not-fixed/62 wont-fix. Findings remain visible and acceptance is BLOCKED.
  - [ ] Remediate or obtain exact currently valid exceptions for image findings; verify remaining images/native/interpreter/tool scopes and rescan the final frozen first-party artifacts after source changes.
- [ ] **Step 10 — Implement current authority, Keychain and clock adapters.** Add a non-renewing, scope-bound U3/approved-operator read/commit guard port without changing normal sliding session behavior. Use purpose-specific keychains/CA with role-scoped unlock, validated TLS/mTLS on `127.0.0.1:8101`, protected Unix socket peer verification via **macOS-supported** primitive (not Linux-only `SO_PEERCRED`), and a pinned native chrony NTS observer health adapter. Missing key, stale revocation, clock age ≥30s, uncertainty >±1s, sleep/resume and unsupported OS primitive all fail closed; no `.env`/plaintext fallback. Trace PAT-R1-02/08/12, VAL-R1-10/12/13/16, EV-R1-06.
  - [x] Prepare and verify a pinned Darwin arm64 chrony/Python clock bundle with frozen load dependencies, non-adjusting configuration and protected publication paths. Built unprivileged from the pinned chrony `4.9` (`4924c6f5…`) and CPython `3.13.15+20260924` (`064afb7c…`) sources: 2248 files, 97,622,694 bytes, current manifest `509b5074da51eebe58cadb8b4527d3ab6c2c961f4bf15e6e2f3f971e75da1752`. The earlier rehearsal verified 400 chronyd executable mappings within the frozen closure or system libraries. Static Mach-O/Python closure checks and system Python 3.9 plan-only execution pass.
  - [x] Remediate `CVE-2026-82049` (High) in the frozen runtime. The pinned 3.13.15 archive predates the PSF backport, so the builder applies upstream `b8f23e307097552eaea2604383a12ab280520d0d` byte-for-byte against the pinned preimage and purges stale `tarfile` bytecode. Bootstrap extraction now also refuses to materialize any hard-link member, closing the vulnerable pre-3.14 `tarfile` path before the patch exists. The upstream hard-link-to-symlink regression passes under both the `data` and `tar` filters. Grype still reports the CPE match, so the finding stays visible as unapproved in `sbom-targets.json` for operator acceptance rather than being suppressed.
  - [x] Add an operator-run test-realm clock installer/probe using the existing UID 608 and launch policy; test refusal paths. `provision_clock.py` exposes `fetch/build/refresh/seal/backport/rehearse/install/probe/uninstall`, requires a protected root-owned operator copy for privileged actions, rejects manifest widening, extra sources, disabled NTS and tampered artifacts, and plans two fixed clock jobs. The exact handoff and patch-verification follow-up is tracked below.
  - [x] Verify vendor-patch metadata and the exact postimage at the install boundary; make backport verification read-only and bind its evidence to the manifest. Reproduced and fixed unchecked patch claims and a CA staging-swap race. Main ops: 137 passed, including 39 clock tests and two 2,000-example property tests (seed 20260928); Ruff passes. The actual sealed-runtime vendor regression and system Python plan-only install pass. Retain raw scanner findings (SECURITY-05/10/13/15; PBT-02~08/10).
  - [x] Reseal and verify the final candidate, correct evidence/counts, and provide runnable digest-bound protected-copy/install/probe/uninstall commands with no missing arguments. All 8 changed files have preserved-worktree byte parity; both ops suites pass 137 tests. Artifact/scan/proof pins, Bash/Zsh syntax, Markdown/JSON parsing and git diff --check pass. Operator authentication and actual installation remain the next gate (RESILIENCY-03/04/13).
  - [ ] Complete clock acceptance for the frozen release. Live collection, authenticated publication and isolated reader validation/write denials are now proven by the operator's NATIVE_CLOCK_PROBED result. Signed receipt/trust provisioning and remaining expiry/reboot acceptance remain pending.
    - [x] Record the operator's successful installation of manifest `509b5074…` and failed clock probe. Readonly launchctl/stat/frame observations and the installed interpreter reproduce an unreadable root-owned 0400 deployment manifest under non-root launch roles.
    - [x] Correct the published manifest read mode to root-owned 0444 and ensure an unreadable same-digest installation is repaired. Four regressions fail before the fix and pass afterward, with distinct root-owner/service-reader permissions and repeat-repair idempotence. Full platform: 528 passed / 90.33% coverage; ops: 137 passed; Ruff and wheel build pass.
    - [x] Verify the correction and provide digest-checked recovery for the existing installation, retaining original bundle/provisioner pins. Handoff §13 commands pass Bash/Zsh syntax and pin validation; all 8 changed files have WT byte parity, and its 39 launcher tests/Ruff pass. Main full platform/ops, wheel build, Markdown/JSON and git diff --check pass. Actual repaired native probe remains operator-executed.
    - [x] Record the operator's mode repair and repeated probe failure. Verify deployed mode 0444, observer run 2/exit 2, sampler exit 2, UNAVAILABLE frame, and successful inspector-side deployment/identity/all-artifact validation. The remaining native launch-context failure is not yet identified.
    - [x] Prepare and verify a bounded one-shot launch-context diagnostic that records actual credentials and the launcher exception, intercepts target exec, and is digest-bound for operator staging. `diagnose_clock_launch.sh` has SHA256 `410016041adc71e2a503848446ee3ac1a222d73571976e0bf2202ef41869ecbe`; four diagnostic regressions and the full 141-pass ops suite/Ruff pass. A real UID-501 dry run exposes its expected role-boundary refusal, not the unknown UID-608 cause.
    - [x] Collect the diagnostic from the actual observer launchd job before changing another runtime permission or privilege policy. Operator report: UID/EUID/GID/EGID 608, native groups [608,12,61,100], PermissionError at launch_guard, targetExecuted=false.
      - [x] Identify and correct the diagnostic command-ordering error: terminal-attached launchctl debug remains foreground, preventing the chained kickstart. Handoff §14 now uses Terminal A for capture and Terminal B for kickstart; the existing pending capture can be triggered directly.
    - [x] Route launchd through the existing verified root bootstrap with Python -I -B, then setgroups([]), setgid and setuid before target exec. Preserve exact post-drop checks. New root-path regressions cover ordered drop, every syscall failure, residual groups and invalid artifacts; platform 534 passed / 90.42%, Ruff success.
    - [x] Prepare a default-plan-only repair bound to the original bundle/provisioner/deployment and the two exact plist preimages; test rejection, stop-before-publish and failure/interrupt/unacknowledged-start cleanup. Real System-Python preflight passes; repair and renderer postimages agree. Ops 156 passed, platform 534 passed / 90.42%, Ruff/wheel/shell/Markdown/JSON checks pass. All 10 changed files have WT byte parity; WT launcher 45 and repair 15 targeted tests pass. Handoff §15 is ready for operator apply/probe.
    - [x] Record operator repair completion and observe exact repaired plists, live chronyd PID 87325 at UID/GID 608, successful periodic publication and authenticated frames. Installed ProtectedClock passes five inspector-side reads across 20 seconds within policy after the initial UID-600 reader failure.
    - [x] Rerun only the original protected probe against the stabilized source. Operator result: NATIVE_CLOCK_PROBED, collector OBSERVED, reader CLOCK_READ_VERIFIED, clockWriteDenied=true, commandSocketDenied=true, window width 235726 us. capabilityReceiptIssued=false.
    - [x] Prepare `ops/platform-integrity/clock-receipt.test.json` with the deployed frame/UID/config digest. Live issuer --probe-only reports nts_clock proven=true/verified; four omitted provider sections are not_configured and overall exit is 2. No key is read or receipt issued. The production signing path still needs role-scoped Keychain access, trusted-time validity and independent release-trust anchoring.
    - [x] Wire protected receipt issuance/preflight to the authenticated clock window and independently provisioned release trust; the current bootstrap CLI uses local wall time and evidence-named trust files.
      - [x] Add fixed-root immutable receipt policy loading, host/release/role/clock/artifact bindings, public-key validity/revocation and current-policy rechecks; test forged evidence trust and policy drift.
      - [x] Add the purpose-Keychain Ed25519 signer with explicit role/file permissions, public-key pinning and no private-key file/CLI fallback; use complete trusted time windows for issuance and verification.
      - [x] Integrate protected issuer/preflight CLIs, scoped capabilities, bounded atomic publication and failures; replace insecure acceptance tests with meaningful protected-path and property regressions.
      - [x] Prepare a separate frozen signer bundle and operator-only Keychain create/unlock/issue workflow; exercise native disposable-Keychain behavior, validate handoff and synchronize verified results.
    - [ ] Provision the approved role-scoped release signer and trusted public-key entry, issue the host/release-bound nts_clock receipt from a fresh probe, and verify it through preflight. The provisioner is implemented, Ruff-clean and unit-covered (11 tests), and the Keychain→sign→publish→verify path is proven end-to-end against a real native Keychain, but every root action still needs an operator: FileVault must be enabled first, then `provision_receipts.py` runs under sudo, then the issuer with `--keychain-password-stdin`, then preflight. No `nts_clock` receipt exists yet, so `capabilityReceiptIssued` stays false.
- [ ] **Step 11 — Assemble R1C read-only API.** Expose authenticated bounded evidence/compatibility and distinct shallow/deep/subject readiness on native FastAPI behind loopback mTLS. Enforce 256 KiB request, 1 MiB/100 items response, total 3s deadline, 8 metadata + 2 health admissions, 512 MiB RSS including 64 MiB immutable-only LRU, generation-aware 3-failure/10s breaker. `read/check/health` never creates run/ledger, invokes a scanner, starts a job or refreshes a grant. Verify 401/404/no-leak and dependency failure responses with test client and isolated real store. Trace US-R4/5, BR-R1-01/20~22, PAT-R1-01/07/12, EV-R1-02/06/09.
  - [x] Current trust and head/record coherence are checked across the read; mid-read head/key changes return INCOMPLETE. Real worker admission remains held until synchronous I/O ends, even when the HTTP waiter times out. Missing current providers cannot promote checksum-only PASS; caller grants are rechecked after I/O. Actual native-role/dependency/load/RSS acceptance is still open.
  - [x] Close the read-surface gaps found on 2026-09-29. Authentication is now an explicit `401` rather than an accidental `404`: `/internal/**` requires the 64-hex-lowercase fingerprint the TLS transport injects, and three header names plus a query parameter cannot forge it. Non-loopback peers get a fixed `not_found`, so the daemon never confirms its existence off-host. `/readyz` now reports shallow/deep/`subjectEligible` separately, with `subjectEligible` a real boolean instead of a hardcoded `null`. `/internal/v1/compatibility/{release}` exposes the existing `domain/compatibility.py`, which had no API at all, and fails closed (503) when its owner port is unprovisioned. The 100-item response cap is now enforced across every item-bearing field, not just bytes. Subjects/releases use `{param:path}` because a `Ref` admits `/`, so `repo/one` previously matched no route. 24 new tests; platform 406 passed/185 skipped, ops 179 passed, Ruff clean. Physical mTLS, load/RSS and role acceptance remain open.
- [ ] **Step 12 — Assemble R1R and scoped helper interfaces.** Provide explicit `check/plan/verify/apply/reconcile/backup` CLI actions with machine-readable non-success, no default apply. One-shot supervisor claims one host-heavy lane, accounts for child RSS ≤2 GiB, disk `free >= 10 GiB + 2×additional peak`, bounded output/deadlines, child cleanup/orphan witness and no auto-resume. Separate generator/scanner/publisher/signer/audit/backup roles and deny arbitrary shell/path/SQL/sign requests. Test SIGTERM, stale holder, duplicate attempt, lost receipt and resource saturation. Trace BR-R1-06~12/21, PAT-R1-06, VAL-R1-04/13/18, EV-R1-02/03.
- [ ] **Step 13 — Package local host provisioning and rollback artifacts.** Add `ops/platform-integrity/` guarded installer/plists/role-permission and isolated `rem-1-test` rehearsal configuration, without running it on the serving checkout. Script P0 operator drive fact/verified encrypted backup + restore preflight, FileVault console-unlock check; P1 OrbStack→Colima export (PG dump, OpenSearch snapshot, host MinIO mount, queue drain) and reversible cutover with the original VM retained; P2 UID/Keychain/PG `hostssl`/client `verify-full`/8101 wiring; P3 frozen release, one-shot helper and 60s audit relay. Require each physical capability and current disk peak to be proven before activation. Trace R1IF1~10, NFR-R1-12~16, EV-R1-06/07.
  - [x] Prepare a default PLAN_ONLY, operator-root-only test-realm UID/directory script. The operator executed the original verified artifact on 2026-09-26; readonly OS inspection confirms UID/GID 600~608, root 0711, role directories 0700 and preparation receipt 0600. Keychain/NTS/DB roles/plists/rollback and complete physical setup remain open.
  - [x] Record `DocSuri_Backup` at `/Volumes/DocSuri_Backup`, encrypted/unlocked USB APFS UUID `BB384D60-46AF-4A06-B6F7-95710B3B7A3C`, 1,537,204,109,312 bytes shared container free. Operator enabled ownership and readonly reinspection confirms it. R1OP3=A specifies daily 03:00 Asia/Seoul (UTC+9) backup start with continuous connection. Scheduler installation/activation and actual backup/restore acceptance remain open.
  - [x] Correct the native IsHidden namespace parser and add readonly `--check` plus protected operator-only `--probe`. Initial sixteen focused regressions pass, including real libSystem kernel-group query, conflicting namespace, ambient privilege, missing-file, FIFO, cross-role-access and privileged mutable-source refusal cases. Actual metadata check passes for nine accounts; the first operator `--probe` failed with nine timeouts and does not establish native role acceptance.
  - [x] Capture the nine-timeout failure, observe the actual interpreter image rather than the launcher chain, and add stage/cleanup diagnostics plus a one-role retry. Twenty-two focused tests pass, including real EOF/timeout/process-group/pipe-descendant checks. Operator's UID-600 retry completed in 0.052s with groups=[600], own read/write and 8 read + 8 write + 3 ambient-group denials. This is reader-only synthetic-file acceptance; the original timeout's exact internal cause remains unconfirmed.
  - [x] Complete the same r2 probe for all nine roles. Operator report `role-probe-236g0xrp` is ROLE_FILE_ISOLATION_VERIFIED/completeRoleCoverage=true: UID/GID 600~608, only each primary kernel GID, own read/write, 72 cross-read + 72 cross-write + 27 ambient-group-read denials, all complete/exit 0/no timeout/reaped in 0.044~0.051s per worker. Source/interpreter digests match the current files. This completes synthetic-file isolation only; installed launcher/Keychain/NTS/DB privileges and broader G1 remain open.
- [ ] **Step 14 — Add local observability, retention and backup evidence.** Provide redacted structured JSON with request/run/effect correlation, outbox relay cursor, safe heartbeat/alert hook, 14-day ordinary/90-day critical retention and approval-bound GC. Include exact snapshot cut, encrypted removable-drive archive coverage and isolated restore with new target incarnation; missing drive, no verified remote copy, clock/key lock or unresolved writer yields incomplete/unready rather than success. Integrate through `ops/server/` and `ops/local/` owner seams without deleting pre-existing logs/backups. Trace US-R4/5, NFR-R1-14~16/19/20, EV-R1-06/07/09.
- [ ] **Step 15 — Harden CI and reproducibility.** Update `.github/workflows/ci.yml` and dedicated local runner instructions for frozen Python/Node images, *full* production/tool closure audits (not PR-diff-only), SBOM/image digest validation, schema output/read-only drift, smoke and PBT Full. Pin or log Hypothesis and fast-check seeds, preserve shrinking/replay data, run PR profile (200 examples; 50 stateful sequences ×50 commands) and release/nightly (2,000; 200×100), and include isolated macOS/PG/filesystem/clock/key/restore checks with explicit non-success when unavailable. Keep existing unit CI lanes. Trace F06/F08/F13, PBT-02~10, EV-R1-01~08.
- [ ] **Step 16 — Run G1 isolated end-to-end acceptance.** On non-production ports/UID/DB/schema/CA/filesystem: fresh and legacy DB tests, actual evidence/glossary requests, collision/changed SQL/two-writer/COMMIT-lost proof, offline full schema/consumer generation, patched frozen dependency/image inventory, owner/key/TLS denial, R1C liveness/deep health and runner failure/rollback. Record artifact revision, coverage, seed, throughput p95 (5 req/s ×10 min normal plus separate overload), RSS/disk and effect provenance. Do not count mock-only unit tests as EV-R1-03/04/06/07. Trace VAL-R1-01~18, EV-R1-01~09 and NFR-R1-07.
  - [x] Exercise actual pg_dump/pg_restore of control/audit schemas in the isolated test container and verify evidence preservation plus old-PASS invalidation under a new incarnation. Add eight load-harness regressions: exact isolated origin, no redirects with client credentials, and failure/incomplete responses excluded from success. Native 600-second load/RSS/overload and encrypted/off-host/RTO/RPO acceptance remain unexecuted.
- [ ] **Step 17 — Document code, constraints and next-unit handoff.** Create `aidlc-docs/construction/rem-1-platform-integrity/code/code-summary.md` (Markdown only) listing changed/new files, actual commands/results, any unsupported physical capability, no-live-activation facts, G1 result versus US-R4/5/RJ-AC12 G4/G5 dependency, shared-owner review and remaining REM-2/3/4 contract. Mark all plan steps and stage state in the same interaction as each completed step; run `git diff --check` and review no unrelated user work was overwritten.

## 5. Trace and stop gates

### Implementation checkpoint (2026-09-26 — launchd installer/manifest)

- `platform_integrity/src/docsuri_platform_integrity/deployment/launchd.py` gained `install` and
  `uninstall`. Before this there was `render` (GENERATED_NOT_INSTALLED) and `exec` only — no path
  that put a plist into launchd at all. The operator flow is now render → review → install.
- `install` verifies root, darwin, launchctl integrity, realm integrity, account/uid/gid, role
  working-directory ownership and **every frozen artifact digest** before writing anything. Any
  failure means zero plists written; a partial install would leave a state that looks installed.
- "Installed" is confirmed three ways — manifest digest, plist bytes equal to the re-derived
  bytes, and `launchctl print` actually holding the job. My first version trusted only the
  presence of `deployment.json`, which misreported a half-removed install as installed; drifted
  state is now repaired bootout-first so a broken job never keeps running during the repair.
- `--replace` is required to move to a different manifest, and replacement still boots the old
  deployment out first, so the cutover stays reversible.
- `uninstall` refuses to delete when launchd still holds a job: removing the plist of a running
  job would strand a process with no way to stop it. A `Label` mismatch is treated as foreign and
  left alone. No recursive or glob deletion.
- `write_root_file` refuses symlinks and files root does not own, and writes via temp → fsync →
  `os.replace` → parent directory fsync at 0644 (plist) / 0400 (manifest).
- Four self-corrections: the `ALREADY_INSTALLED` misreport, a refuse-silent-replacement guard
  dropped during refactoring, the missing uninstall orphan check, and a `require_root` that made
  the suite structurally untestable by checking launchctl root-ownership instead of writability.
- `test_launch_policy.py` 24 → 34. Full suite 350 passed / 0 skipped / 89% statements / Ruff clean.
  Verified on this host only that non-root install/uninstall return BLOCKED with exit 2, that
  render emits a valid plist, and that `/Library/LaunchDaemons` is unchanged. **No root install
  was performed and this host was not modified**; the test launchctl is a recorder.
- Still open for Steps 10/13: create the nine `_docsuri_r1t_*` accounts, stage toolchains and
  artifacts, rehearse against the isolated test profile, and install production inside the
  maintenance window. G1 remains blocked.


### Implementation checkpoint (2026-09-26 — readonly probes and receipt issuer)

Preflight readiness is now end-to-end code: probe, issue, verify. No step is checked because the
five physical capability proofs and the Step 6 operator authority are still open.

- `platform_integrity/src/docsuri_platform_integrity/deployment/capability.py` (new): readonly probes for all five capabilities, reusing the existing adapters. Never raises — an unavailable capability is `proven=False` with a reason, so a crashed probe cannot read as a passed one. `ProbeSet.run()` probes once per run; `receipt_from()` refuses anything unproven or any window over seven days.
- `ops/platform-integrity/issue_receipt.py` (new): the issuer. The configuration document carries references only; credentials are never read from it. `--probe-only` reads no key and writes nothing. **One unproven capability refuses the whole run and writes no file**, because a partial set must never look like acceptance. Signing keys are checked for symlink, owner, `0o077` mode, link count and size before any read; receipts are written 0600 via temp + `os.replace`.
- ~~`native_commit_guard` is deliberately not issuable here.~~ **Superseded 2026-09-26:** Step 6 is now implemented, and this capability *is* issued from a live `PostgresOperatorAuthority` on an idle autocommit target connection. `notIssuableHere` no longer exists; see the Step 6 checkpoint below.
- Two of my own defects were corrected: `probe_restore_receipt` rejected a restore that had just completed (the observation window is a single instant, so the rule is "not in the future and within 30 days"), and `build_probe_set` crashed with `TypeError` on a wrong-typed section (now explicit `ValueError`, so the CLI fails closed).
- Verified through the real CLI: `--probe-only` → `ISSUED` → `preflight.py --evidence` reports `provenCapabilities: ["restore_receipt"]` with no capability reasons left. Throwaway keys, deleted immediately; not acceptance evidence.
- `platform_integrity` 340 passed / 0 skipped / 89% statements / Ruff clean; `ops` 86 passed / Ruff clean. Six new files plus the previously main-only `images/postgres-alpine-nosu.Dockerfile` and `sbom-targets.json` synced byte-identical to the worktree; full tree parity reconfirmed.
- Still open for Steps 10/13: launchd installer/manifest, real purpose Keychains, live NTS clock, real DB mTLS role, backup/archive command and scheduler, and the Step 6 operator authority needed to issue the commit-guard receipt. G1 remains blocked.


### Implementation checkpoint (2026-09-24)

### Implementation checkpoint (2026-09-26 — signed capability receipt verifier)

Preflight readiness code gap closed; no step is checked because the issuing installer and the five physical capability proofs are still open.

- `platform_integrity/src/docsuri_platform_integrity/deployment/receipt.py` (new): Ed25519 capability receipts bound to `IOPlatformUUID` + release + 7-day-capped validity + artifact/evidence digests. Manifest-trusted keys carry `revoked` and their own validity. Every unproven capability returns a specific reason; unproven is never treated as proven.
- `ops/platform-integrity/preflight.py`: replaced the unconditional `<capability>_requires_receipt_verification` with real verification, so `ready=true` is reachable. Trust is a separate argument from evidence, and trust keys must resolve inside the evidence file's own directory.
- `ops`: added `docsuri-platform-integrity` dependency and raised `requires-python` to `>=3.13` (the new dependency requires 3.13; leaving `>=3.11` would be unsatisfiable).
- Corrected three defects found while implementing: strict-mode `model_validate` rejects enum strings from JSON (use `model_validate_json(canonical(...))`); a `bytes` public-key field cannot be serialised to JSON (canonical base64url text instead); `ValidityWindow.contains` requires `upper < valid_until`.
- Verified: `platform_integrity` 308 passed / 0 skipped / 89% statements / Ruff clean with the real loopback mTLS test executing against the derived image (`REM1_TEST_PG_DSN` **and** `REM1_TEST_CONTAINER` are both required or the test silently skips); `ops` 68 passed / Ruff clean. Six files synced byte-identical to the preserved worktree and full tree parity reconfirmed.
- Still open for Step 13: no receipt issuer, launchd installer/manifest, purpose Keychain, live NTS clock, backup/archive command and scheduler, native commit guard, and the `CVE-2026-85091` zlib finding. G1 remains blocked.

### Implementation checkpoint (2026-09-29 — Steps 7, 12, 14, 15 code complete)

No step box is checked: every one of these retains a physical or operator-gated acceptance obligation. The code obligations below are complete and verified; what remains is named rather than implied.

**Step 7 — generation/journal boundary.** Added `domain/generation.py` and extended `adapters/filesystem.py` with `GenerationBoundary`, `PinRegistry`, durability receipts, verified metadata-only import, pin-protected collection and `_erase_tree`. `RetentionPolicy`-independent generation tests cover interrupted receipt/seal, torn tail, stale head, late writable descriptor, reader/backup pins, GC, import verification, symlink escape and recovery. Open: the isolated **APFS** root and the native durability proofs still need an operator host.

**Step 12 — R1R and scoped helper interfaces.** Added `domain/actions.py` (closed action vocabulary, role matrix, forbidden request kinds, machine-readable failure states) and rewrote `cli/__main__.py` to expose explicit actions with no default apply. `application/supervisor.py` already satisfied the one-shot obligations (single lane claim, child RSS ≤2 GiB, `free >= 10 GiB + 2×additional peak`, bounded output/deadline, process-group cleanup, holder witness, no auto-resume) and was left unchanged. Open: native role binding, the real lost-receipt/duplicate-attempt rehearsal, and the physical mTLS handshake.

**Step 14 — observability, retention and backup evidence.** Added `domain/retention.py` (request/run/effect correlation, monotonic relay cursor, 14-day ordinary / 90-day critical retention, approval-bound GC that never touches records outside the managed set) and `domain/backup.py` (`BackupEvidence`, `evaluate_backup`, `cut_is_exact`). Every backup signal defaults to the **unproven** value, so an absent archive, unverified remote copy, locked clock/key, unresolved writer or missing restore yields `INCOMPLETE` rather than a partial success. Open: `ops/server/` and `ops/local/` seam wiring, the encrypted removable-drive archive, and the isolated restore to a new target incarnation.

**Step 15 — CI and reproducibility.** In `.github/workflows/ci.yml`: added a nightly + `workflow_dispatch` trigger; `rem1-closure-audit` (full, **non-diff-only** closure audit over every discovered `pyproject.toml`, with un-dispositioned projects reported rather than silently dropped, plus a digest-pinning check driven by the new tested `ops/platform-integrity/validate_supply_chain.py`); `pbt-full` (release profile, 2,000 examples / 200×100); `rem1-isolated` (provisions the container the harness contract names so the 185 skipped Postgres tests actually run, with an anti-vacuous-pass guard); and `macos-filesystem` (APFS hardlink/symlink/rename semantics the Linux lanes cannot observe). Defects caught and fixed while writing these: the committed `sbom-targets.json` uses a **dict** shape, so the first inline check would have crashed; a declared image with **no** digest slipped through as a false negative; `-q` in `addopts` plus an explicit `-q` became `-qq` and suppressed the summary line; and the skipif on the isolated tests is evaluated at **runtime**, so a collection-count guard would have proved nothing — the guard now requires zero skips after a real run. Open: the closure audit could not be executed locally (`uvx pip-audit` aborts in this sandbox with an `ensurepip` SIGABRT), so the newly covered projects are reported as warnings pending CVE disposition rather than promoted to blocking.

Work is isolated in `/var/folders/59/1zr18zjd30n_w8nnxdq2r_qm0000gn/T/opencode/rem1-20260924`. Steps with remaining obligations stay unchecked. Independent offline parts of later steps were prepared while native capability proof remained unavailable:

- Steps 3/6/7: pure contracts/rules, stateful/round-trip/boundary tests, control/audit SQL+CAS, journal and immutable generation/head adapters implemented. Full PROP/VAL coverage, native finalization/revocation and role-separated durability proof remain open.
- Follow-up Steps 3/6: stable semantic run identity, immutable attempt records, exact-bound conservative reconciliation and transactional UNKNOWN/audit/outbox store implemented. `002_run_protocol.sql` is additive and packaged with `001_control.sql` in the wheel. 80 REM-1 tests (86% statements), 77 shared tests/drift, release run/property subset 25, Ruff and non-editable wheel/migration import checks passed. The task-owned PG container was stopped; worktree/source patch retained.
- Current-evidence follow-up: fresh trust/exception evaluation and mutable-target state binding, coherent bounded reads and atomic verification publication/late history implemented with migration 003. Latest REM-1 suite 127 passed (87% statements); release property subset 48 passed; Ruff and fresh non-editable wheel/resource checks passed. The fresh smoke used `uv run --no-cache` after observing reuse of an obsolete same-path wheel environment. Provider/role/physical G1 obligations remain open.
- Schema follow-up: explicit 13-resource catalog, shared Python tooling namespace and Node interpreter, public/internal closure checks, 20 cross-language vectors and generator integration verified. Shared 112 passed/release subset 39, frontend generator 29/UI 338 plus tsc/build/drift, REM-1 127 passed and fresh wheel imports passed. Actual hand-authored consumer/view inventory and native publication proofs remain open; only the completed substeps are checked.
- Step 8: all seven shared DTO schemas now generate one build-consumed TS wire module offline; schema aliases/view refinements compile. Python resolves all 13 schemas locally and pins an immutable generated tree. Invalid remote ref, missing catalog and source-field regressions pass. Broader wire-consumer inventory/visibility proof remains open.
- Step 9: updated Python locks and Next 15.5.26; audited installed backend/ingestion/REM-1 and frontend production tree report no known vulnerabilities. Compose image digests resolved; image/OS SBOM and Grype verification remain open.
- Steps 10~12: native macOS peer identity, noninteractive Keychain read adapter, non-renewing U3 session observation, clock-window arithmetic, bounded R1C API, circuit breaker and one-shot supervisor implemented. Production native clock/current-authority/role configuration is unavailable; privileged apply is deliberately BLOCKED, not a success stub.
- Steps 13~16: readonly preflight and isolated rehearsal commands/CI guards added. No privileged installer, live migration/cutover, key provisioning or release activation was executed. Current Docker context is already `colima` (observed, not switched by this task); installation proof still needs operator verification. Release preflight with 1 GiB estimated additional peak returned disk_reserve plus drive/FileVault/current-authority/clock/key/TLS/restore missing evidence.


| Acceptance | Owning steps | Required observed evidence |
|---|---|---|
| F08 migration truth/atomicity | 1, 3~6, 16 | Fresh/legacy PG, stable owner-qualified IDs, no read-side DDL, effect+ledger atomically; actual evidence/glossary HTTP |
| F13 offline complete bindings | 1~3, 7~8, 15~16 | All declared local refs/exports/consumers; generated Python+TS build; old-or-complete-new after crash |
| F06 supply-chain | 1, 3, 9, 15~16 | Patched resolved/installed closures, pinned tool/image digests, SBOM, scanner/feed completeness, no unapproved critical/high |
| US-R4/5, RJ-AC12 | 3, 6~7, 10~16 | REM-1-local safe OBS/health/checkpoints; final cross-REM queue/consumer/reconnect evidence belongs to G4/G5 |
| Props and failure scenarios | 1~16 | PROP-R1-01~16, VAL-R1-01~18 with seeded/replayable examples and real adapter fault probes |

**Hard stop**: if OS/keychain/clock/native revoke guard or filesystem durability cannot be proved, do not declare mutation/reader eligible; return a documented blocked capability. If drive capacity/free disk does not satisfy the selected backup and `10 GiB + 2×peak` condition, defer host changes without deleting unrelated data. A full corpus rebuild/reindex and production data mutation have their separately approved execution gates. Unverified R1IF2 operator facts are installation inputs, not invented defaults.

## 6. Enabled extension compliance — planning level

| Rules | Planning evaluation / implementation owner |
|---|---|
| SECURITY-01/03/05~15 | Compliant at plan level: Steps 2~16 require FileVault/drive encryption, mTLS/current authority, structured redacted logging, strict input/role isolation, patched artifacts, auditable transitions, denial and cleanup tests. Actual compliance is demonstrated by EV/VAL tests rather than this document. |
| SECURITY-02 | N/A for REM-1 itself (no new public-facing intermediary); existing Cloudflare/BFF access-log responsibility remains with EDGE/REM-3 and G4. |
| SECURITY-04 | N/A for REM-1 (no new HTML endpoint); existing BFF/CSP remains under REM-2 and G4. |
| RESILIENCY-01~07/10~15 | Compliant at plan level: steps assign workload importance, RPO/RTO/restart evidence, gated rollback, OBS/deep health, disk/backpressure/timeouts, encrypted backups, real restore/fault drills and IR integration. |
| RESILIENCY-08 | N/A by the user-approved single-Mac fault-domain exception. |
| RESILIENCY-09 | Compliant replacement: bounded local admissions, host-heavy singleton, RSS/disk/queue backpressure rather than horizontal autoscale. |
| PBT-01~10 | Full mode retained: FD identified PROP-R1-01~16; Steps 2~3/8~9/15~16 map round-trip, invariants, idempotence, oracle, stateful, domain generators, shrinking and seeds with Hypothesis/fast-check plus concrete regressions. PBT-09 framework/dependencies selected in TD-R1-14/15. |

No enabled extension is disabled. Only rules not applicable to this unit/stage are marked N/A; no stage-completion claim can bypass an applicable failing rule.

## 7. Plan approval gate

## Question R1CGR1

After reviewing the 17 ordered implementation steps, F06/F08/F13 scope, package paths, security/resource stop gates and isolation of live host changes, should REM-1 Code Generation Part 2 proceed? Approval applies to the entire plan; it does not authorize production deployment or corpus rebuild.

A) Approve the entire plan and proceed with Part 2.

B) Request changes to the plan before implementation.

X) Other (describe your decision after the `[Answer]:` tag).

[Answer]: A

### Native runtime and database mTLS checkpoint (2026-09-26)

- Step 10: `deployment/launchd.py`, `host.py`, `adapters/{credentials,postgres_tls,nts,read_authority}.py` and `migrations/005_reader_access.sql` implemented and integrated into `main`. Immutable manifest allowlist, role-scoped plist with `InitGroups=false`/`Umask=0o077`/`env -i`, frozen artifact digest verification, ordered `setgroups([])`→gid→uid drop with pre-exec uid/gid/group re-verification, handle-only (never credential-byte) configuration, and the production/test port boundary. Real loopback mTLS against the disposable database now passes: certificate-mapped `session_user`, read-only transaction enforcement and wrong-CA denial.
- Step 10: the code substep is done and Step 10 remains **unchecked**: clock bundle preparation, the operator installer/probe and the `CVE-2026-82049` vendor backport are all verified locally, but the real purpose Keychain ACL, the serving 8101 loopback mTLS path, the live installed chrony NTS daemon and the U3 current-authority guard are operator-side or still open.
- New-module statement coverage raised to launchd 92%, host 99%, nts 93%, read_authority 100% while covering real execution paths. Whole-package result **280 passed / 89%** statements in `main` (2026-09-25 baseline was 190 / 88%), Ruff clean.
- Root cause of the long-standing mTLS fixture failure was three independent defects, not a code defect: `docker restart` inside an open connection, a 256M `HostConfig.Tmpfs` PGDATA that discarded `ALTER SYSTEM` on every restart, and a `hostssl` rule ordered after the image-wide `scram-sha-256` rule. The disposable container now uses the named volume `rem1-pgdata-20260926`; the entrypoint rewrites `pg_hba.conf` on start, so the fixture installs HBA after restart and reloads.

### Step 6 live OperatorAuthority commit-guard issuance checkpoint (2026-09-26)

- Step 6 is now **implemented and live-tested**; it stays **unchecked** as acceptance evidence because every
  proof below is a disposable-realm proof, not one of the nine physical operator capabilities.
- Added `deployment/operator_plan.py`: a frozen, digest-pinned, root/current-owner, non-group/world-writable,
  single-link, non-symlink, size-capped operator plan reader. A plan that is edited after approval cannot be
  re-read, because the caller must supply the pinned `planDigest` that the approval already names.
- `capability.py::probe_native_commit_guard` now proves the guard in both directions against the real adapter:
  an identity that provably is not in the plan must be refused with exactly
  `effect is outside the frozen operator plan`, and the planned identity must be admitted into the guarded
  region with **no effect performed**. It deliberately stops at the yield because the adapter refuses
  finalization after the body, so only a flag set inside the body can distinguish a refusal from an admission.
- Two probe verdicts were corrected during live testing. `MutationUnavailable` subclasses `PermissionError`, so
  a revoked or out-of-scope approval was being reported as an internal crash; it is a legitimate refusal. And
  the `entered` flag must be read **before** the exception message, because a guard that admits and only then
  raises the post-yield refusal raises the same exception as one that refused up front.
- Added `tests/test_guard_receipt.py`: 10 tests against the isolated database that replay migrations
  `001~004`, insert a real `r1_control.authority` row and `r1_control.target_identity`, and prove
  refusal on a revoked approval, a wrong operator role, a database row naming a different plan, a fence for
  another incarnation and an expired decision deadline; plus admission of the planned effect, an ordinary
  signed receipt that the normal `verify_capability` accepts, and a check that the audit and outbox tables
  are still empty and the connection left `IDLE` afterwards. The receipt is a normal capability receipt: same
  signer, same verifier, same trust and validity rules as every other capability.
- `issue_receipt.py` composes the live authority from `nativeCommitGuard` (`plan`, `planDigest`,
  `operatorDatabase`, `operatorTls`, `approval`, `fence`, `deadlineSeconds`, optional `identity`): the
  `actor_role` is derived from `operatorDatabase.user`, the authenticated `ProtectedClock` is mandatory, the
  connection is `PostgresTLS` readonly/autocommit, the approval's `plan` must equal the pinned `planDigest`,
  and the authority and fence targets must match. All five capabilities are now requested by default, so
  `notIssuableHere` no longer exists; a declared-but-broken guard section reports an unproven capability
  instead of falling back to "not issuable here", and any unproven requested capability blocks issuance.
- Package result in `main`: **382 passed / 89%** statements, Ruff clean. `ops`: **98 passed**, Ruff clean.
  (Ran from `ops/`, not `ops/platform-integrity/`; the latter is the CLI package and holds no tests.)
- Still open and unchanged: purpose-specific Keychain material, live chrony NTS, the production-equivalent
  database role, the encrypted backup and restore drill, the 03:00 Asia/Seoul scheduler, the 127.0.0.1:18101
  5 rps x 600 s native acceptance run, the launchd test/production rehearsal, registry publication, and
  `CVE-2026-85091`. G1 stays blocked and Step 6 stays unchecked.

### Step 6 target effect adapter and fault-injection checkpoint (2026-09-26)

- Step 6's central deliverable was genuinely absent and is now implemented: nothing previously applied an
  effect. The control plane recorded `UNKNOWN` durably and `PostgresOperatorAuthority` admitted, but there
  was no defined way to perform the effect and record it in the **same target transaction**.
- Added `migrations/006_target_effects.sql`: a separate `r1_target` plane (deliberately not `r1_control`)
  with a `state` row carrying the exact native digest a compare-and-set moves between, and an append-only
  `effect_ledger` row bound to run/step/attempt/fence epoch. A unique index enforces one effect per
  `(run_id, step, fence_epoch)`, so the database refuses a repeat even behind the session lock.
- Added `adapters/target_effect.py::PostgresTargetExecutor`. Per effect it takes a dedicated physical
  autocommit connection, holds a session-level `pg_advisory_lock` for the whole effect, and then drives
  the guard's own protocol: `guard()` -> one target transaction -> compare-and-set on
  `expected_before` -> state write -> ledger row -> `before_commit()`. The finalizer's `FOR SHARE` re-read
  happens *inside* the transaction holding the effect, which is what serializes a revoke against the
  commit. The lock is session level, so a crash releases it; an explicit unlock failure is swallowed
  because `close()` releases it anyway and must not mask the real outcome.
- Failure classification is the point of the adapter, so it is explicit: a rejected statement, a
  `MutationUnavailable` refusal, or a stale precondition is a **provable** non-application and propagates;
  only a lost connection (`OperationalError`) becomes `TargetOutcomeUnknown`, because there the effect may
  be durable and the caller must not be told either success or failure. `observe()` is the only resolver
  and is read-only (`SET TRANSACTION READ ONLY`): a ledger row proves a commit, an unchanged target proves
  a quiet abort, and any other digest stays `UNKNOWN` because an unexpected observation proves nothing.
- Added `tests/test_target_effects.py` (16 tests) covering all four Step 6 fault cases: two concurrent
  target writers (exactly one applies; the loser is refused with a classified reason, never a crash or a
  second ledger row), a fresh fence epoch not re-arming a moved precondition, the index refusing a forged
  repeat, revoke committed before the effect, **a revoke landing mid-transaction**, rollback after the
  effect write taking both state and ledger back, no session-lock leak after rollback, a lost commit reply
  that leaves the effect durable while the caller is told UNKNOWN, a blind retry then being impossible, and
  the three observation outcomes including a drifted target staying UNKNOWN.
- The mid-transaction revoke test was verified to be load-bearing by mutation: deleting the finalizer's
  re-check makes the effect **commit under an already-revoked authority** and the test fails. This is the
  privileged-apply hazard the step forbids, and it is now pinned by a regression test rather than asserted.
- Two of my own test bugs were corrected against the real behaviour: `check_binding` raises `PermissionError`,
  which is the *parent* of `MutationUnavailable`, so the assertions had to expect the base class; and a
  fence epoch the target has not adopted is refused as out-of-scope, so a genuine "new fence" test must
  advance `r1_control.target_identity.epoch` before the compare-and-set becomes the deciding check.
- Result: `main` **398 passed / 89%** statements (`target_effect.py` 96%), Ruff clean. `ops` 98 passed.
- Step 6 remains **unchecked** for acceptance. The target executor is proven only against a disposable
  realm; the physical operator capabilities, purpose Keychain, live chrony NTS, production-equivalent
  database role, backup/restore drill, scheduler, native 5 rps x 600 s acceptance, launchd rehearsal,
  registry publication and `CVE-2026-85091` are unchanged. G1 stays blocked.

### Step 6 append-only enforcement and scoped DB command roles checkpoint (2026-09-26)

- Step 6 explicitly asks for "append-only critical events/outbox and scoped DB command roles". Both were
  **claims, not mechanisms**: `001`/`006` said "append-only" in a comment while the session role could
  freely `UPDATE`/`DELETE`, and nothing stopped the process from writing the tables directly.
- Added `migrations/007_command_roles.sql`:
  - NOLOGIN group roles `r1_target_owner` / `r1_target_operator` / `r1_target_auditor`.
    `r1_target_operator` has no INSERT/UPDATE/DELETE/TRUNCATE on any table and no rights in
    `r1_control`; its only write capability is `EXECUTE` on one `SECURITY DEFINER` function.
  - `r1_target.effect_ledger` and `r1_control.outbox` now reject `UPDATE`, `DELETE` **and `TRUNCATE`**.
    A row-level trigger never fires for `TRUNCATE`, so each table also needs a statement-level guard;
    without it the append-only property is silently false, which mutation testing confirmed.
  - `r1_target.apply_effect(...)` takes only scalars, fixes the compare-and-set target, takes the row lock
    itself, and re-verifies the approval. The Python guard is **defence in depth, not the enforcement
    boundary** — a first version of this migration let the scoped role apply an effect under a **revoked**
    authority by calling the function without a guard. The database now refuses a revoked, non-`apply`,
    retargeted or out-of-epoch grant itself (`R1T02`), and a lost compare-and-set (`R1T01`).
  - Refusals carry explicit SQLSTATEs and the adapter classifies by code, never by matching message text.
- Two checks are deliberately **left to the guard** and this is now documented in the migration and the
  operator handoff rather than left to look like an oversight:
  - *expiry*, because judging the window in SQL would mean trusting `clock_timestamp()` instead of the
    protected chrony/NTS clock the plan requires;
  - *which database role may use which approval*, because that needs the role mapping Step 10 still owes.
    A cross-target escape is fully closed; a session-to-approval identity binding is not yet.
- `adapters/target_effect.py` no longer computes the ledger digest or `applied_at` in Python; the database
  records both. A dead `except TargetStateChanged` clause was removed once the CAS moved into SQL and that
  exception could no longer be raised inside the guarded block.
- `tests/test_target_effects.py` grew to **28 tests** and `adapters/target_effect.py` reached **100%**
  statement coverage. It now also pins: ledger/outbox `UPDATE`/`DELETE`/`TRUNCATE` rejection, the operator
  role having no write right anywhere, auditor read-only, a cross-target/cross-incarnation escape being
  refused, a non-`apply` grant refused, a stale epoch refused, a revoke landing *after* the guard read
  being caught by the command, scoped read-only reconciliation, and the failed-unlock path not masking a
  real outcome.
- Every new enforcement was **mutation-verified**. Removing the `revoked`, `target`, `namespace`,
  `incarnation`, `purpose` or `epoch` predicate each fails a named test, as does removing the scoped grant
  or the TRUNCATE guard. This found two genuine holes that prose review had missed: a cross-target escape
  no test covered, and an untested `purpose` predicate.
- Test-hygiene defect fixed rather than worked around: `tests/test_reader_roles_postgres.py` applies every
  migration but only cleared `r1_control`/`r1_audit`, so it collided with objects left in `r1_target`.
- Result: `main` **413 passed / 90%** statements (`target_effect.py` 100%), Ruff clean. `ops` **98 passed**,
  Ruff clean. `git diff --check` clean.
- Step 6 remains **unchecked** for acceptance. The physical operator capabilities, purpose Keychain, live
  chrony NTS, production-equivalent database role and the Step 10 role mapping, backup/restore drill,
  scheduler, native 5 rps x 600 s acceptance, launchd rehearsal, registry publication and
  `CVE-2026-85091` are unchanged. G1 stays blocked.

### Step 6 durable dispatch/reconciliation checkpoint (2026-09-27)

- Added migration 008: fully bound v2 receipts, legacy provenance preservation, canonical target
  exclusion, monotonic epochs, deferred native grant/epoch/revision/plan checks and durability checks.
- Fixed unsafe observation of in-flight writers, receipt rebinding and authorization inferred from
  ledger existence. Nine regressions reproduced those defects before the fixes.
- Added `RunDispatcher` and typed control/target ports. Acknowledged UNKNOWN/audit/outbox precedes the
  single target dispatch; any interrupted boundary requires explicit reconciliation. Historical commit
  without authorization proof remains COMMITTED/PAUSED rather than becoming SUCCEEDED.
- Actual PostgreSQL tests cover both revocation orderings, direct command bypass attempts, legacy
  upgrade, scoped observation, bounded lock waits, audit/acknowledgement failures, competing dispatchers
  and fresh-attempt resume after fencing. Generated failure cuts cover varying frozen plans and retries.
- Main verification: **456 passed**, **90%** statements, target adapter and dispatcher **100%**; ops
  **98 passed**. Ruff and `git diff --check` passed. Seed **20260927**; the new property also passes the
  release profile (2,000-example limit).
- Remaining acceptance: native current authority/clock and least-privilege end-to-end login mapping,
  protected helper composition and physical operator evidence. Step 6 and G1 remain open; the concrete
  source/role gap is not waived by documenting it. See the latest code summary and operator handoff.

### Step 6 current-source and login binding checkpoint (2026-09-27)

- Migration 009 adds immutable approval-revision/actor/login-name/OID mappings and audited, command-only
  bind/revoke operations. Binding rejects privileged or table-write-capable logins; the same revision
  cannot be reassigned, and a recreated login cannot inherit the old mapping.
- `PostgresOperatorAuthority` now uses a scoped read/finalization function whose inaccessible owner
  holds the SHARE-lock privileges. Target process roles receive no authority-table UPDATE privilege.
  Direct target commands check mappings before ledger insertion and at deferred finalization.
- Added `PostgresCommandAuthority` with separate current `run` and `reconcile` approvals, and
  `build_operator_dispatcher` with a frozen step, protected clock, original deadline, explicit TLS
  connection sources and role identities derived from those sources. Physical connections are closed
  by their owning adapter; credentials are removed after the TLS handshake.
- Two initial actual-login regressions failed on the old implementation (legitimate guard denied;
  unrelated login could use the approval directly). Native role, revoke/audit, clock failure, scoped
  read, revision/OID and no-renewal regressions now pass. Main: **496 passed / 90%** statements; ops:
  **98 passed**; Ruff and `git diff --check` pass. Authority property seed **20260927**, release profile
  with 2,000-example limit passes.
- The target helper, source reader and source administration commands are tested with actual
  non-superuser logins. Tests still use owner-backed control checkpoint storage, disposable credentials
  and synthetic NTS frames. Scoped control-store commands and physical provider acceptance remain
  explicit Step 6/G1 obligations; no complete native acceptance is claimed.

### Step 6 scoped coordination/prepared execution checkpoint (2026-09-27)

- Migrations 010/011 add command-only coordination, one-use preparation response secrets, native
  committed checkpoint/audit/outbox checks, helper-owned finalization witnesses and audited epoch CAS.
  Legacy unprepared apply is disabled; caller observations cannot manufacture native completion.
- `ScopedPostgresRunStore` and `build_scoped_operator_dispatcher` implement the co-located PostgreSQL
  profile. Registration/attempt/prepare/apply/reconcile/fencing run under actual non-superuser logins.
  Protected adapters release secrets only after synchronous commit ACK; the database verifies committed
  provenance, not network acknowledgement delivery.
- Main **522 passed / 90%**, ops **98 passed**, Ruff and `git diff --check` pass. Native SQL/JCS oracle
  and dispatcher failure-cut properties pass release profiles, seed **20260927**. Fault tests include
  lost ACKs, audit/clock rollback, two coordinators, replay, forged results, fencing and multi-step order.
- Global WAL insertion/flush comparison is not a per-commit proof inside a write transaction: own/hint
  WAL can make it wait on the wrong records. Durability uses the synchronous control/target protocol and
  protected helper provenance. Exact trust bounds are recorded in the code summary.
- Readonly preflight without release/evidence and with peak=0 reports unready/zero capabilities and five
  malformed receipt reasons; FileVault/drive/minimum reserve passed. This is a diagnostic floor, not
  provider absence or activation evidence. Physical Step 6/G1 acceptance remains open.
