## Review

**Verdict:** NOT-READY
**Reviewer:** aidlc-architecture-reviewer-agent
**Date:** 2026-10-06T02:17:22Z
**Iteration:** 1

### Scope and Decision Boundary

This is the initial U1 Steps2–6 focused independent **source/security** review, before procedural SQL execution. It is not the final whole-Unit Code Generation review, a protected approval receipt, operational authorization, realm admission, PostgreSQL acceptance or a skeleton checkpoint. The current Plan Approval identity supplied in the dispatch is `sha256:v3:48887bcf8d0ca4f9d8a9371dffa0fbb3c437d6a758379946c235d04eefb25e37`; the current questions file records that same identity and the selected opaque TEXT representation. I did not invoke approval/fingerprint/lifecycle tools to reconstruct its authority.

The reviewed boundary includes the actual complete 003 SQL, literal admission policy, registry and inherited executor; the specified source/admission and realm/schema tests; the adjacent content codec/model; inspect-only bootstrap and its mocked operator port; supplied contracts/designs/questions; and public source/test evidence plus immutable baseline/supplement. No sibling Unit Construction content or builder planning/diaries was accessed. Mandatory framework shared/reviewer knowledge was loaded; both corresponding space-specific knowledge directories are absent.

Only the named review file is authored. No database connection, SQL execution, live fixture, retained purge, Docker/network/package-fetch/resource/credential/privileged operation was performed. Step7+ and real SQL remain stopped. The absence of a qualified live realm or concrete privileged executor is a disclosed dependency, **not by itself a source finding**.

### Findings

| ID | Severity | Location | Finding | Required action | Status |
|---|---|---|---|---|---|
| R-01 | Critical | backend/modules/summarization/migrations/003_content_job_authority_prepared.sql > `content_job_binding_guard`, `trg_content_job_binding_guard` (lines 218–261), and `trg_content_job_validate_binding` (lines 449–451) | Dispatch identity/fence immutability protects UPDATE only. Neither binding trigger handles DELETE, and there is no parent-to-binding FK. A binding can therefore be deleted while its v1 job remains; no deletion-triggered validation requires its retention. More seriously, deleting a SUBMITTED job's SENDING/UNKNOWN binding and inserting a new NOT_STARTED binding with the same owner/input/key bypasses the old-row identity, start-time and monotonic-fence checks. The final deferred validator accepts that replacement, reopening first-send eligibility after an ambiguous send. This contradicts C1/C7 retained dispatch evidence and BR1.7. This is a source-traced schema bypass, not a claim that a presently implemented HTTP route exploits it. | Add deletion protection for submission bindings while their owning job exists, preserving legitimate job/account cascades after parent deletion. Cover direct deletion and delete/reinsert reset attempts after SENDING/UNKNOWN, plus permitted parent cascades. Refresh the entire SQL's literal digest/policy and source evidence after the repair; include those actual bytes and negatives in the second focused pass. Author the PostgreSQL regressions now, but execute them only after the separate source and qualified-realm prerequisites. | New |
| R-02 | Major | backend/modules/summarization/src/summarization/domain/result_storage_codec.py > `canonical_content` (lines 23–29), `decode_canonical_content` (lines 49–60); backend/modules/summarization/tests/test_u1_result_storage_codec.py > `STRINGS` and full-content/property round trips (lines 42, 98–128) | The codec does not preserve every string currently admitted from Python/DTO payloads. Independently executed pure-source probes show the two-code-point string `U+D800 U+DC00` is decoded as the single scalar `U+10000`. These distinct original Python values produce identical canonical text and digests, and both summarize and translate capture return content unequal to their original payload. Existing explicit fixtures cover a lone high surrogate and an astral scalar, but not adjacent high/low surrogate code points; the 120-example property test does not establish that missing case. This conflicts with the specified no-normalization/exact-value capture obligation for the currently admitted string domain. It is a canonicalization ambiguity, not a cryptographic SHA-256 collision. | Make the content-only lossless representation preserve the currently admitted source string values and their integrity identities, including adjacent surrogate code points versus the corresponding scalar. Add codec and both-task capture/read regressions, including string keys where applicable. Do not silently normalize the original DTO values or reject them as malformed C2 content to hide the loss; if the selected canonical-JSON representation cannot meet that obligation, surface the concrete representation/semantic decision through its owning contract/plan boundary. Keep browser/server input hashing unchanged. | New |

### Evidence for the Findings

**R-01 — complete static transaction trace, without executing SQL:**

1. Start with a valid v1 job in SUBMITTED, seq 0, no effect/prepared result, and its retained SENDING or UNKNOWN binding. Its recorded dispatch fence is positive and its start time is populated.
2. Deleting that child binding fires neither `trg_content_job_binding_guard` nor `trg_content_job_validate_binding`: both declarations name INSERT/UPDATE only. The job is not changed, so no new job validation is queued by that deletion. Existing child-to-job FKs do not prevent deleting the child.
3. Insert a replacement with the same job/owner/input identity/idempotency key, another dispatch identity, outcome NOT_STARTED, fence 0, no start/release time. The insert guard checks that the existing job has authority version 1; it does not compare the removed binding. The uniqueness and NOT_STARTED checks can all hold after the old row is gone.
4. At deferred validation, owner/input and retained-key equality hold. SUBMITTED is explicitly exempt from requiring CONFIRMED. With seq 0, no effect and no prepared binding, the remaining validator predicates do not preserve the removed dispatch evidence. Even retaining the same binding ID would not recover OLD-row protection.
5. The database now presents fresh first-dispatch eligibility where WF2/BR1.7 require SENDING/UNKNOWN never to grant another send. The existing effect/event deletion guards demonstrate the intended parent-cascade exception pattern, but no analogous binding guard exists.

Relevant passed obligations are `aidlc/spaces/default/intents/261001-rem-2-phase-7-frontend-v/inception/contract-design/contract-summary.md > C1 Submission and State Semantics / C7`, and `aidlc/spaces/default/intents/261001-rem-2-phase-7-frontend-v/construction/u1-job-skeleton/functional-design/rules.md > BR1.7`. Current static token-presence tests and fake executor tests do not test this deletion boundary. Later store CAS/permission work remains necessary, but does not make this candidate's claimed immutable binding retention a database fact.

**R-02 — independently reproduced, pure Python only:**

```text
original code points: [0xd800, 0xdc00]
decoded code points:  [0x10000]
exact original Python string preserved: False
different original values share canonical bytes: True
different original values share content digest: True
summarize capture retains exact original payload: False
translate capture retains exact original payload: False
```

The probe called the actual `canonical_content`, `decode_canonical_content`, `prepared_content_digest` and existing synthetic `capture` helpers. For summarize it supplied the surrogate-pair string as reproducibility.code and the scalar as reproducibility.data; for translate it supplied the pair as DocModel.fullText. Neither capture rejected the source value, and neither returned the original Python payload exactly. JSON/wire handling of UTF-16 pairs must not be confused with the stronger internal exact-value guarantee currently asserted by the capture tests. The obligations are explicit in the passed Functional WF3, Reliability RD-4 and current questions' content-only lossless/no-normalization choice.

### Independently Verified Identities

SHA-256 values below were computed from actual bytes, not accepted solely from the developer's prose. Sizes are byte counts where stated. The reviewed SQL remains unapplied.

| Item | Verified identity |
|---|---|
| Actual registered 003; 25,701 bytes | `918ed4ab3c54535c1802a157bb6efb9c9b3b4021ef98603431d5e3e49f923f95` |
| Fixed literal policy `backend/migrations/u1_atomic_admission.py`; 1,571 bytes | `e3cb44552ce9ccc7ca48904ffa2ebd6159f2ac01ec8c1300f16db185bc78219e` |
| Current executor `backend/migrations/__init__.py`; 10,836 bytes | `ef6995cdad27b58355ae4a349ecc2cc21667324259b1e50d29d2aaa3426ce6a2` |
| Original executor supplement preimage; 10,146 bytes, source mode 100644 | `6a4f59b0402d6cd756a0677cb86918f8abf11447a0e1e473541b3d1d35d4c74f` |
| Historical 002; current bytes equal original capture, 5,753 bytes | `8f47c5582aadff04afe2f4cac0f39ad1e9e8985f411dd809528d9a8571a07f7f` |
| Original baseline manifest | `a57fbe1e60374dd48a0e83dae0648d537dbea6d039a1f26116bb3a5bca8d5c92` |
| Original full listing, exact-byte hash | `9b6bcacda2f5e05ec3a573d5aae19fe959e2e2bf86b6ebfd29ac6f75d8a21080` |
| Supplement manifest, also its content-addressed directory identity | `2148418e4b2b574cdafcede2b247e727864de99ba56c18a9b1575f3113516aa2` |
| Public `tranche-source-evidence-02.json` | `26cc65eaed4c481bfb5b2f0c1ace5e43a532b35fc60fc4350baef34084c7132e` |
| Current 38-claim `source-manifest.json` | `105fad6d25dd7e6c87e36bc0ee7a824a8b79a6fec2f02b0223edcff2ca58751d` |
| Current partial `traceability.json` | `3f2f93741143128413a65612e1bd26bff86bec782b59069f669a25dfa10abf23` |
| Reviewed content codec | `61cad1d737d5f07d04c898a00f1f4dec30ceebe2a0599ba23db814eca7e605b8` |

The original source-binding ID remains `4b22034726c38f1118e01079cbc5ec7d65a432f7a61549c837a8e2dc24b28ac9`; it is not the exact-byte listing hash. The baseline/supplement/listing paths are the exact `.aidlc-engine/u1-source-baseline/`, `u1-source-supplements/` and `source-review/code-generation/workspace-4b22034726c3.tsv` paths supplied in the dispatch under this intent record.

### Preserved Guarded Paths and Security Assessment

**Narrow procedural admission:** The literal policy verifies exact `MigrationDefinition` type, owner `summarization`, local ID `003_content_job_authority_prepared.sql`, canonical repository path, nonsymlink file, fixed definition digest and supplied payload digest. It then resolves the actual registry entry, requires one matching definition and rereads its actual bytes. Registry discovery does not update the literal pin. The reserved local ID cannot fall back to ordinary SQL after a byte change, even when replaced with benign nonprocedural SQL. Actual positive/lookalike/copy/mutation/context-free negatives passed. This is the one new procedural exception, not a blanket procedural waiver.

**Executor differential:** The immutable original-to-current diff is limited to the definition-aware `_atomic_sql` extension, additional deny-only role/user/database/session-authorization cases, and changing the guarded call to `_atomic_sql(payload, spec)`. AST comparison independently confirmed unchanged `_inspect`, `inspect_migrations`, `pending_migrations`, `adopt_baseline`, `_normalize_dsn`, authority interface and inspection types; the complete textual diff shows no other executor changes. The canonical advisory lock `(1380798032, 1)`, byte-drift check, same-connection authority guard surrounding the transaction, SQL-before-ledger ordering, `before_commit`, rollback propagation and final unlock are preserved. Fresh fake-connection negatives cover revoked authority at entry and commit, changed bytes, lock contention, legacy reconciliation and existing-schema refusal. The protected realm marker is **not** ignored by production apply to simulate an empty target. Adoption still requires its explicit domain checker/authority and records ADOPTED_BASELINE rather than claiming verified execution.

**SQL capability scope:** The complete pinned script contains transaction-contained table/column/constraint/index/view definitions and static PL/pgSQL trigger functions. I found no dynamic SQL, SECURITY DEFINER, external-program/file/network capability, top-level transaction control, concurrent index operation or role/system/database administration in the pinned candidate. Function-local BEGIN/END and trigger `EXECUTE FUNCTION` are not top-level transaction escape. The conservative noncandidate lane still rejects the tested transaction/procedural/external operations, with the added denials not creating permissions for other identities. The above source checks do not constitute PostgreSQL parsing/execution proof. R-01 is a durable-evidence guard defect even though the script's admitted capabilities are transaction-contained.

**TEXT and lifecycle:** `prepared_content` is opaque TEXT, not a raw unrestricted C2 JSONB value. The SQL does not cast/process that column with JSON/JSONB functions/operators. Fixed `json-ascii`/canonical version 2, nonempty text/byte-length checks, typed task/version/digest metadata and owner/job/task composite FKs remain. Prepared identity/content/version/digest/prepared-at metadata are immutable on update; established expiry cannot be renewed. The insert guard rejects an initially purged/missing payload or initialized expiry. Payload-changing cleanup permits SQL NULL only through the checked expired COMPLETED-job path, clears preparation identity and retains matching expiry; subsequent resurrection/purge-marker changes are refused. The purge-only return before the ACTIVE-owner check permits removal for an inactive owner without granting generation. Job/effect legacy adoption refusal, legal state/seq updates, exact completion binding/expiry, effect-intent deletion protection and account/job child cascades remain present.

These are **partial data-layer constraints**, not a claim of complete T1–T8 execution authority. Full decoded C2 shape/task/digest validation remains an application obligation. Actual store owner/fence/lease/time/CAS checks, command/permission boundaries, one-time invocation consumption, bounded transactions, owner-purger integration and read precedence are later work explicitly marked unimplemented. Neither a value constructor nor a missing legacy marker/effect supplies invocation permission. The domain codec supports the selected NUL-versus-literal-escape mechanism, but R-02 refutes its broader currently claimed exact-source-string guarantee.

**Schema and realm pre-admission:** `admitted_schema_statements()` obtains actual accounts001 plus summarization001/002/003 definitions, rechecks every payload digest and materializes all admissions before the first fixture DDL. A mocked final-script refusal produces zero DDL calls. The real fixture retains forced rollback and rejects public tables other than the protected marker; it does not call production ledger/adoption to bypass the marker.

`realm.py` requires absolute bounded regular nonsymlink read-only trust documents with root-owned non-writable ancestors and exact trusted hashes. It checks Linux/workload identity, manifest/receipt realm/unit/environment, validity, matching configuration/guest/runtime/source/launcher/rules/credential-channel bindings and the required measured-observation identities. Authority/purge database-role identities are distinct on the same dedicated private endpoint; DSN indirection/inherited PG configuration is refused at initial admission. A constructed realm must reread the protected proof rather than authorize itself.

The first connection must be read-only and pass actual database/user/address/port/marker/source/launcher/rule/validity/purpose checks and bounded-role privileges. SUPERUSER, CREATEDB, CREATEROLE, BYPASSRLS, replication, role membership, marker writes/ownership, database ownership and postgres/template1/purge cross-database CONNECT are inadmissible. The second connection repeats identity/privilege validation and the protected-document current check before return; mismatches close it before fixture mutation. Fresh tests exercise these reader/connection negatives through mocks. Root ownership and written PASS/evidence hashes are a trust-channel contract, not an independent measurement made by this review. Concrete launcher/source/rule/mount/credential enforcement and actual measured isolation still have to be supplied and qualified externally.

**Inspect-only bootstrap:** The CLI only inspects. The source separates private resource creation, rule application, protected credentials, role/marker provisioning, provisioner withdrawal and an initially unadmitted probe workload; it defines identity-scoped reversal without global prune/production reuse. The operator port checks an exact `ProtectedAdmission`, rebuilds the plan from its raw configuration and rechecks protected authorization/qualification/inventory before each action. It does not supply a concrete executor, launch a workload or mint an independent isolation receipt. The actual privileged integration remains absent and explicitly disclosed; the source/mock passes must not be called a completed operational launcher.

### Source Supplement and Evidence Assessment

Read-only computational checks independently verified all **395 original captured files / 2,983,766 bytes**, their hashes/sizes, nonwritable nonsymlink captures and original-listing source-mode/hash entries. The unchanged captured 002 is not replaced with HEAD. All three supplemental preimages match their original listing entries; the eight supplemental absent paths are absent from that listing and original capture. Both inherited migration tests remain byte-identical to their supplemental preimages and are unclaimed. No changed executor was recaptured as its baseline.

All **38 current claim paths** are unique, match the public evidence's exact current bytes/sizes/modes and are nonsymlinks. The nine supplement-backed added claims are executor, policy, admission tests, codec, codec tests, timestamp tests, TEXT schema tests, bootstrap and bootstrap tests; the remaining 29 claims retain the reported initial-tranche allocation. All 12 byte changes relative to the original 395-file capture are claimed. This verifies attribution within the supplied original/supplemental boundary, not a whole-workspace or future collector certification. No unrelated user/framework paths or untouched inherited tests were added to these claims.

The partial trace remains **184 rows: 178 GAP, six Deferred, no OK**. Its bytes match the supplied public evidence hash. No source/test observation is promoted to trace completion.

The public backend/Ops XML/coverage bytes and their recorded source hashes were checked. The latest public backend report contains 250 passing cases and 944/1119 covered statements (84.36%); Ops contains 35 passing cases and 234/259 covered statements (90.35%). These are developer-run historical local reports independently checked for consistency, not fresh whole-suite coverage from this review. Their intentionally uninvoked SQL/live paths and partial inherited-executor/realm/fixture coverage remain visible. The before/after compatibility reports both retain the same three recorded failures among 93 cases. The initial bootstrap Boolean-version failure is retained separately; its corrected final report is not relabeled as TDD evidence.

### Validation Tool Results

| Tool/check | Actual result | Interpretation |
|---|---|---|
| Dispatch-recommended focused pytest selection, frozen/no-sync/offline sanitized backend environment, no pytest cache or new XML/coverage output | PASS, exit 0; 70 passing cases, zero failures/errors/skips | 29 admission + six registry + 30 realm + three migration source + two TEXT source cases. All connection executors are mocks/call logs; no live fixture or SQL interpreter ran. |
| Own Ops bootstrap pytest, same sanitized prefix with existing Ops environment | PASS, exit 0; 35 passing cases, zero failures/errors/skips | Inspect/configuration/protected-admission and mocked action/reversal behavior only. |
| Pure actual-code codec and both-task capture adversarial probe | Reproduced R-02: exact equality false in codec and both tasks; pair/scalar canonical bytes and digests equal | New independent counterexample despite the passing supplied tests; no database or evidence file write. |
| Complete SQL reading plus binding-trigger/constraint trace | R-01 confirmed at source level | No DELETE-triggered retention check, and delete/reinsert avoids OLD-row guards. PostgreSQL execution was deliberately not attempted. |
| Baseline/supplement/current-claim hash, size, mode and differential script | PASS, exit 0 | Verifies supplied immutable identities, three preimages/eight absent paths, 38 actual claims, 12 original-capture changes and preserved guarded executor paths. |
| Public report/source-hash consistency script | PASS after correcting the reviewer's XML class-prefix assumption | The first checker stopped on a mistaken `tests.u1_integration` class-name assumption; actual XML uses `modules.summarization.tests.u1_integration`. The corrected suffix-based selection verifies all 70 focused nodes, seven report identities/counts/totals and recorded coverage-source hashes. This was a checker error, not an application-test failure. |
| Scoped backend/module Ruff command from tranche verification, 13 changed Python paths, owning config, `--no-cache` | PASS, exit 0 | No lint suppression/configuration weakening or autofix. |
| Own Ops Ruff, bootstrap source/tests, owning config, `--no-cache` | PASS, exit 0 | No source modification. |
| `git diff --check -- "backend/migrations/__init__.py"` | PASS, exit 0 | Scoped whitespace check only; no git mutation. |

**Exact fresh focused command**, working directory `backend/modules/summarization`:

```bash
env -i PATH="/Users/revenantonthemission/.local/bin:/opt/homebrew/bin:/usr/bin:/bin" HOME="/var/folders/59/1zr18zjd30n_w8nnxdq2r_qm0000gn/T/opencode/u1-tranche-home" ENV=test AWS_EC2_METADATA_DISABLED=true PYTHONDONTWRITEBYTECODE=1 UV_OFFLINE=true UV_CACHE_DIR="/var/folders/59/1zr18zjd30n_w8nnxdq2r_qm0000gn/T/opencode/uv-cache" UV_PROJECT_ENVIRONMENT="/var/folders/59/1zr18zjd30n_w8nnxdq2r_qm0000gn/T/opencode/u1-backend-venv" uv run --project ../.. --frozen --no-sync python -m pytest ../../tests/test_u1_atomic_admission.py ../../tests/test_migration_registry.py tests/u1_integration/test_realm_preflight.py tests/u1_integration/test_migrations.py::test_registered_additive_authority_script_follows_unchanged_002 tests/u1_integration/test_migrations.py::test_historical_002_retains_the_coordinators_prewrite_bytes_not_head tests/u1_integration/test_migrations.py::test_registered_authority_script_is_admitted_by_the_actual_migration_runner tests/u1_integration/test_text_result_schema.py::test_local_registered_payload_column_is_opaque_text_with_no_json_payload_operations tests/u1_integration/test_text_result_schema.py::test_local_full_schema_preadmission_retains_owner_immutable_and_lifecycle_guards -q -rs -p no:cacheprovider
```

All other fresh Python checks used that identical sanitized environment. Ops substituted only `UV_PROJECT_ENVIRONMENT=/var/folders/59/1zr18zjd30n_w8nnxdq2r_qm0000gn/T/opencode/u1-ops-venv`, working directory `ops`, running `uv run --frozen --no-sync python -m pytest tests/test_u1_db_bootstrap.py -q -rs -p no:cacheprovider` and the documented own-project Ruff command. Hash/differential/report checks were inline read-only Python computations; their outputs stayed in the tool transcript. The codec probe's inputs and decisive outputs are recorded above. No frontend/domain-wide regression suite, dependency installation or new coverage artifact was generated.

### Summary

The fixed identity/policy and inherited guarded executor integration withstand the focused admission checks, and the original/supplemental source evidence matches the supplied immutable identities. Nevertheless, binding deletion can erase/reset dispatch authority, and the actual codec loses an admitted source-string distinction; repair these grounded source defects before the second focused pass, without treating passing local tests as permission for procedural SQL or as qualified realm/store/Unit acceptance.
