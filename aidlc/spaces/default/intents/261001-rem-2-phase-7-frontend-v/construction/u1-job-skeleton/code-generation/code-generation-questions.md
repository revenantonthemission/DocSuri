# Code Generation Questions — U1 Job Skeleton

## Sources and Current Status

The current Unit consumes `../functional-design/{functional-spec,rules,entities}.md`, `../../../inception/contract-design/contract-summary.md`, `../nfr-design/{performance-design,security-design}.md`, `../infrastructure-design/infrastructure-specification.md`, `../../../inception/units-generation/unit-of-work.md` and `../../../inception/requirements-analysis/requirements.md`. The full U1 NFR, infrastructure monitoring/delivery and story-allocation records remain implementation constraints.

U1 Infrastructure Design has completed its document checks and independent review. Its recorded review is `../infrastructure-design/reviews/review-01.md`: no Critical finding, Major R-01 for the missing concrete staging network-enforcement/outbound path, and Minor R-02 for an incorrect source citation. They remain New in that completed record; planning here does not silently edit or resolve it. Functional Design Minor R-05 and NFR Requirements Minor R-01 likewise remain for the U1 human checkpoint.

The resolving provider source is `backend/modules/summarization/src/summarization/real_wiring.py`, as identified by the passed contract and source inspection. Use that exact path in the implementation plan; do not copy the infrastructure source-anchor typo.

Before the implementation plan can specify isolated staging safely, its remaining network mechanism needs a concrete choice. The confirmed hosting, same-server staging, pull-based continuous delivery and broker-persistence qualification choices are not reopened. No application source, live environment or deployment has been changed by this planning pass.

## Q1. Staging Ingress and Selective Egress Enforcement

The selected staging boundary must deny production/host/LAN access while allowing the real HTTPS staging benchmark and scrubbed diagnostics. A private internal container network alone cannot supply that selective outbound path. Which mechanism should the implementation plan specify?

- A. **Internal staging network with a controlled egress helper** — Keep staging API/worker/database/broker/cache/storage/inference and benchmark workloads on the private internal network without host networking, production mounts or a container socket. Publish only the staging BFF through the protected staging HTTPS/tunnel origin. Add a staging-only outbound proxy/gateway helper: only it has an external network attachment, it accepts allowlisted HTTPS destinations for the staging origin and required diagnostics, and it denies production/host/LAN/link-local destinations, arbitrary CONNECT hosts/ports and DNS rebinding. Apply the destination enforcement at that helper and its external guest-network boundary; direct workload egress stays denied. Configure the benchmark browser/diagnostic transports to use that path and verify paired allow/deny cases against the selected local runtime. This adds test-environment infrastructure within the existing host, not a public application API; image/policy/script details and exact runtime qualification belong to the approved implementation plan.
- B. **Use an existing verified enforcement mechanism** — Provide the non-secret existing runtime/network policy or configuration location. It must identify ingress, the selective outbound path and the enforcing control, including how the browser reaches real staging HTTPS and diagnostics leave while production/host/LAN remain inaccessible. Verify those claims before using it; namespace naming or unrestricted outbound connectivity is insufficient.
- X. Other (please specify)

Recommendation: A when no existing verified equivalent is available. Preserve all prior owner/authority/deadline/result and quality requirements. Unsupported enforcement or inadequate host resources blocks staging activation and requires a concrete follow-up rather than a weaker isolation claim.

[Answer]: A

## Implementation Planning and Approval Boundary

After resolving the mechanism, prepare the detailed story-linked implementation steps, source/test blast radius, current baseline and unit-scoped test instructions. Embed the tool-rendered Testing Contract unchanged, retaining test-after/test-last per component and the at-least-80% new-code coverage floor. Include the requested senior-engineering implementation-plan review before asking for initial Plan Approval.

Keep the completed infrastructure artifacts/review receipt intact; this plan must make the missing mechanism explicit and use the correct source anchor. Carry all recorded open findings into the U1 human checkpoint without inventing an Accepted risk or Resolved disposition.

The dedicated Plan Approval section and tool-produced approval/source fingerprints are added only once the actual plan and test instructions are final. Its answer stays blank until the human chooses Approve Plan or Request Changes. No developer implementation is authorized by the infrastructure summary confirmation or this pending question. The real integrated verification command remains separately human-authorized.

## Answer Analysis

The human answered the file-backed question directly: "Q1: A". This selects the internal staging network with a controlled egress helper. The selection supplies the architectural enforcement/outbound-path approach needed by the implementation plan and is consistent with the previously confirmed same-host staging and protected production boundary. Exact local-runtime support and deployed isolation remain qualifications to prove, not existing-operation claims.

## Q2. Recovery From the Blocked Schema Prerequisite

The first implementation attempt returned a blocking handoff in `code-summary.md`. It wrote 29 claimed application/test/configuration/lock paths: runner support, job/protocol/prepared-content models, migration 003 source and guarded schema fixtures. Model tests passed (94, model-lane coverage 89.55%) and the isolated full existing frontend suite remained 356 passed. The required schema lane returned one admission failure, 15 passing local checks and ten missing-realm errors with zero skips. U1 is not complete, and its later store/service/worker/browser/runtime implementation has not advanced.

The actual blockers are:

- **Migration admission:** The inherited `backend/migrations/__init__.py` rejects procedural BEGIN/END/DO/EXECUTE syntax in the new registered migration. Any repair must preserve current-authority, immutable registry/digest and top-level transaction/external-effect protections; no raw-SQL bypass or broad guard relaxation is authorized. This source extension needs explicit footprint/baseline reconciliation.
- **C2 result contract:** Its summary `reproducibility: string` conflicts with the actual existing DTO/shared schema's `{code, data}` object. Preserve the exact object; resolve the contract through its normal owner/approval path rather than flattening content or claiming conformance.
- **Real test realm:** Required disposable PostgreSQL authority/purge databases, scoped role, Linux isolation and trusted manifest/receipt bindings are absent. Operator readiness must supply these through the authorized launcher; no production DSN/credential or self-written isolation proof is substituted.
- **Remaining qualification:** Stricter imported TypeScript graph, residual high dependency finding and qualified images/provider/control/notification evidence remain unresolved. Local model coverage is not the final all-source coverage gate or skeleton proof.

How should we proceed?

- A. **Retry** — Reconcile the safe migration-admission source extension and C2 contract correction, retain the current implementation and source snapshot, and resume the required schema checks after the verified isolated realm is supplied. Review the concrete repairs and preserve all quality/security targets; do not bypass the failing prerequisite or move unfinished backend guarantees to U2.
- B. **Skip** — Preserve partial work and explicitly replan U1 and its dependent units. U1 is the required walking skeleton, so skipping it cannot silently unlock U2/U3 or claim the integrated result.
- C. **Abort** — Stop implementation with the current changes and blocking evidence preserved for later resumption.
- X. Other (please specify)

Recommendation: Retry for the already assigned integration gaps, with the required real-realm readiness coordinated by revenantonthemission. Public manifest/configuration locations can be discussed; credentials remain in the authorized operator channel.

[Answer]: A. Retry

## Q3. Prior-Contract Correction and Revalidation

`recovery-impact.md` identifies the exact conflict: C2 declares summary reproducibility as a string, while the actual shared schema/DTO requires `{code, data}`. Correcting the prior approved contract must use its owner/approval path. The proposed change preserves exact content and existing behavior, but reopening that boundary can invalidate downstream reviews/approvals and require unchanged designs to be revalidated before code generation resumes. The partial source and immutable baseline are preserved.

- A. **Reopen Contract Design for the narrow correction** — Use the returned workflow route to modify C2 to the authoritative shared object, validate complete summary-envelope fixtures and obtain its normal review/approval. Revalidate reusable unchanged downstream records through that route, then reconcile the migration-admission footprint/current implementation plan and required exact-plan authority. No code or requirement/Unit/deployment expansion is inferred.
- B. **Hold the contract correction** — Keep exact-summary completion blocked while the owner supplies a different authoritative resolution. Do not flatten actual content or silently override the approved spec.
- X. Other (please specify)

Recommendation: A to correct the verified specification mismatch while preserving the actual prepared payload and current implementation.

[Answer]: A. Reopen Contract Design for the narrow correction

## Q4. Verified Isolated PostgreSQL Realm

Schema verification requires the qualified Linux workload/network boundary and distinct disposable database identities. Which readiness arrangement should we use?

- A. **Use an existing verified realm** — Identify its non-secret manifest/receipt/configuration location and have revenantonthemission bind the trusted digests and scoped role access through the authorized launcher. Credential values stay in that operator channel. Verify actual markers/roles/network proof before any mutation.
- B. **Prepare an isolated-bootstrap plan** — No verified realm is available. Prepare the concrete owned local test-environment bootstrap/artifact/qualification plan and obtain its operational authorization before resource/rule application. Keep real-schema acceptance blocked until actual proof exists; no synthetic receipt or production fallback.
- X. Other (please specify)

[Answer]: B. Prepare an isolated-bootstrap plan

## Historical Plan Approval

Approve this exact Code Generation plan?

This decision covers `code-generation-plan.md`, its embedded Testing Contract and `unit-test-instructions.md` for u1-job-skeleton. The separately requested pre-implementation review is recorded in `reviews/implementation-plan-review-02.md`; it does not replace this human decision or the later completed-code review. `baseline-results.md` identifies the current source, passing checks, three existing SSE failures to repair and unverified real-runtime prerequisites.

[Approval Fingerprint]: sha256:v3:d81d7a5430b1fa7bc1c398ad99388b13cfc69f56af947c57f0b069960522bd98
[Planned Source]: 4b22034726c38f1118e01079cbc5ec7d65a432f7a61549c837a8e2dc24b28ac9

- Approve Plan — Proceed to implementation of this exact plan and test instructions through the required protected approval receipt.
- Request Changes — Revise the plan or test instructions before implementation.

[Answer]: Approve Plan

## Historical Code Generation Confirmation

- **Selected network mechanism (Q1: A):** Keep staging application, database, queue, cache, storage, inference and benchmark workloads on the private internal network. Only the controlled staging egress helper has an external attachment. Workloads cannot use host networking, production mounts/credentials or the container socket, and cannot bypass that helper for outbound access.
- **Allowed paths and enforcement:** Publish only the staging BFF through the protected staging HTTPS/tunnel origin. The helper permits only the configured staging-origin and required diagnostic HTTPS destinations, with explicit host/port rules, production/host/LAN/link-local denial and DNS-rebinding protection. Enforce the destination policy both at the helper and its external guest-network boundary; keep direct workload egress denied. Configure the actual benchmark browser and diagnostic transports for this path, including both address families or fail-closed handling of unsupported paths.
- **Required proof:** Include paired allowed/denied destination, wrong-environment, direct-egress bypass, rebinding and credential/mount isolation tests before staging activation. Record the selected local-runtime enforcement point and effective rules. Unsupported enforcement or insufficient host resources needs a concrete follow-up; an internal network or namespace alone is not proof.
- **U1 implementation scope:** Plan the real summarize submission → authenticated BFF/gateway → durable queue/worker → SSE → COMPLETED → exact authorized result journey, plus both tasks' shared backend guarantees, original-request recovery, truthful outcomes, current-fence authority, owner deletion/expiry, accessible containment/focus and scrubbed diagnostics. Preserve the already chosen runtime/maintenance/cleanup, rollout, snapshot and test requirements and later U2/U3 allocations.
- **Plan quality and boundaries:** Prepare complete story-linked ordered steps, source/test blast radius, current baseline and unit-scoped test instructions. Embed the tool-rendered Testing Contract unchanged and retain test-after/test-last per component, at least 80% new-code line coverage, existing suites and required real-store/browser evidence. Obtain the requested senior-engineering implementation-plan review before initial Plan Approval. Preserve unrelated dirty source and use the resolving provider path `backend/modules/summarization/src/summarization/real_wiring.py`.
- **Approval and prior findings:** This confirmation permits preparing the planning documents from these inputs. Application generation still waits for the separate exact-plan Approve Plan decision. The real skeleton verification invocation has its own authorization. The completed Infrastructure Design R-01/R-02 and earlier minor findings retain their recorded checkpoint dispositions; do not silently edit those reviewed outputs or relabel findings resolved.

Does this all look correct before I prepare the U1 implementation plan and test instructions?

- Looks correct
- Request changes

[Answer]: Looks correct

## Current U1 Implementation-Planning Revalidation

The preserved planning/implementation records are `code-generation-plan.md`, `unit-test-instructions.md`, `code-summary.md`, `source-manifest.json`, `traceability.json`, `baseline-results.md`, `recovery-impact.md` and their test/review evidence. The 50-step plan and instructions are starting inputs, not current-attempt execution authority. The historical approval/fingerprint and earlier questions/summary above retain their exact answers as prior decisions; no current Plan Approval or new source baseline is inferred from them.

Current approved inputs include `../../../inception/contract-design/contract-summary.md` with corrected shared required summary code/data, the amended Functional/NFR Requirements/NFR Design/Infrastructure outputs and `../../../inception/delivery-planning/bolt-plan.md`. The public real-realm planning handoff is `../../../verification/u1-isolated-postgres-bootstrap-plan.md`. Current owning reviews are `../functional-design/reviews/review-03.md`, `../nfr-requirements/reviews/review-02.md`, `../nfr-design/reviews/review-03.md` and `../infrastructure-design/reviews/review-02.md`.

The current Infrastructure review independently resolves its prior staging-enforcement R-01 and provider-source-anchor R-02, but records a new **Major Infrastructure R-03**: the direct `prepared_content JSONB` representation cannot store every contract-permitted string, because PostgreSQL rejects U+0000 even as a Unicode escape. This is distinct from **Contract Design R-03**, whose absent timestamp-checker limitation remains Accepted risk. Neither status is changed by this planning handoff; a READY design review is not an issue-free or implementation/operational verdict.

### Required Bounded Plan Updates

- **Lossless string storage:** Define an explicit lossless relational representation or reversible storage codec before capture/store implementation. Cover the complete permitted C2 string domain, canonical integrity hashing over original values, exact decoding on reads and safe unavailable behavior for corrupt/unknown encoding. Add successful capture/persist/read regression for U+0000, empty strings, escaping and a distinguishable literal backslash-u sequence, plus corruption/unknown-codec negatives. Preserve the shared contract and valid returned content; do not drop/normalize characters, classify valid content as malformed success or silently add a character restriction. The representation choice remains to be settled in the current planning/confirmation path.
- **Current C2 and timestamp obligations:** The former specification string/object contradiction in historical B-03 is corrected upstream. Actual partial model/capture/consumer/store conformance still needs current verification. Carry required exact code/data object/no extra nested fields, bare DocModel/final personalization, available RFC 3339 checker admission, malformed-date negatives and real fresh-database-time T5/T6/one-time-expiry tests. Keep owner/state/known-expiry/unavailable precedence and zero read generation/enqueue/submit/current-settings rendering; synthetic shape/format evidence does not fix the old helper or prove actual store TTL.
- **Migration admission and source footprint:** Add the narrow executor/admission-policy/test footprint through current plan authority, with supplemental original-byte capture checked against the original approved full source listing before its write. Preserve the original 395-file snapshot and actual 29 claimed writes; never recapture modified bytes, substitute HEAD or claim unrelated user changes. Review the actual registered 003/policy together and retain full-script identity/digest, same-connection current authority, canonical locking, per-step transaction/ledger, guarded commit and changed/unknown-digest/revoked-authority/top-level escape/external-effect negatives. No raw rejected SQL or broad procedural exemption is authorized.
- **Real prerequisites and ordered work:** Materialize and qualify the concrete operator-owned database-only bootstrap plan with admitted artifacts, separately authorized resource/rule/credential/reversal scope and independent protected realm/role/marker/digest/network evidence before fixture mutation. Keep authority and later adapted minimal-purge targets distinct. Required schema/owner proof must pass without skips before later ordered store/service/worker/browser implementation. Real full staging separately qualifies broker/persistence, Squid/guest/provider enforcement, source/build closure, scheduling/resources and actual diagnostics; the PostgreSQL/image/runtime and MinIO UNOBTAINABLE/control/notification gaps remain actual prerequisites.
- **Partial work and current evidence:** Preserve existing models/schema/runner/lock/build-copy support and historical executed evidence, while separating implemented local pieces from failed/unverified acceptance. Reconcile the stricter imported TypeScript graph and residual dependency finding without weaker flags, excluded authority paths or broad later-Unit refactors. Update obsolete source/script/Dockerfile/upstream-finding descriptions against the current reviewed handoffs. Keep existing three baseline SSE failures assigned until repaired; model-lane coverage and a mock-default build are not complete-source or skeleton passes.
- **Planning and approval:** Preserve test-after/test-last, the current native Testing Contract, ≥80% complete changed-source coverage, all current-suite/lint/type/real-store/browser/security/performance obligations, the selected timing/maintenance/monitoring and Mac/staging/pull/rollback choices, October 14 review and U1→U2→U3 scope/order. Archive prior planning/instruction/handoff versions before modifying them; record only actual progress and source claims. Confirm the updated answers before revising the plan, obtain the requested current pre-implementation engineering review and current-attempt exact Plan Approval before developer execution. The real integrated invocation/checkpoint and resource/rule operations remain separately authorized.

## Q5. Preserved U1 Implementation Plan and Test Instructions

How should we handle the preserved U1 implementation plan and test instructions now that the corrected designs and recovery handoffs are available and the new lossless-storage concern must be addressed?

- A. **Modify (Recommended)** — Revise the existing plan/instructions for the bounded updates above, preserving partial source, baseline and prior evidence. Settle the storage representation, confirm the summary, review the concrete plan and obtain current exact-plan authority before implementation.
- B. **Keep** — Retain the plan/instructions as-is and revalidate them against current inputs; unresolved storage, admission/footprint, realm and current-authority prerequisites still block affected execution.
- C. **Redo from scratch** — Regenerate the plan/instructions from current approved inputs, archiving their prior versions while preserving actual source and evidence.
- X. Other (please specify)

[Answer]: A. Modify (Recommended)

The human replied exactly `modify`. This selects the bounded planning amendment, preserving actual source/baseline/evidence. Lossless storage is the remaining concrete representation choice below; current summary confirmation and exact Plan Approval are still required before their respective artifact-generation and implementation steps.

## Lossless Storage Evidence and Tradeoffs

Read-only source checks found that `backend/modules/summarization/src/summarization/domain/prepared_result.py` already represents captured content as `serialized_content` and validates its decoded payload and digest on reads. `backend/modules/summarization/src/summarization/domain/job_protocol.py` supplies the current private canonical serializer/digest, shared with server input identity; the content-storage repair must not silently change browser idempotency or server input identity. Its current UTF-8-encodability restriction is source behavior to reconcile against the complete permitted C2 content domain, not authority to narrow the shared schema.

The draft `backend/modules/summarization/migrations/003_content_job_authority_prepared.sql` uses `prepared_content JSONB` with object/status/task checks and immutable payload/identity, owner, binding and expiry guards. It has not passed admission or real-schema acceptance. A changed representation needs explicit replacement of representation-specific checks while retaining relational ownership, legal states, immutable content/digest, T5/T6/deletion and purge constraints. Direct JSONB payload operations cannot be used on unrestricted original strings.

PostgreSQL 16 documentation, [JSON Types §8.14](https://www.postgresql.org/docs/16/datatype-json.html), retrieved on 2026-10-05, confirms JSONB rejects the Unicode null escape and imposes surrogate/encoding restrictions. It also permits textual JSON storage and warns that JSON processing functions can convert escapes and reproduce those errors even with the `json` type. Merely selecting `json` is therefore not a sufficient all-path resolution. These are documentation/source checks; no database, application or operational probe was executed.

| Option | Representation and benefit | Cost and required evidence |
|---|---|---|
| Escaped JSON in TEXT | Store complete, versioned canonical ASCII-escaped JSON text as the opaque payload; an actual null character is represented by the literal JSON escape sequence in storage and restored by the application parser. This fits the existing serialized-content model and avoids an additional Base64 layer | Revise the unapplied draft column and representation-specific checks; perform full C2/task/integrity validation before guarded writes and after authorized reads. Retain SQL metadata/owner/state/fence/immutability/expiry/purge guarantees. Never cast the opaque payload to JSONB or decode restricted characters inside SQL |
| Versioned JSONB capsule | Retain the JSONB column for safe capsule/version/task metadata and store complete original canonical JSON bytes in a reversible ASCII/Base64 field; decode and verify before producing C2 content | Additional versioned codec/capsule validation, encoding overhead and corruption/unknown-version paths. Revise draft checks to validate the capsule rather than claim it is raw C2 content; measure encoded volume/deadlines and never expose the capsule as public content |

Both require a declared content-specific canonicalization/storage version and digest over original decoded values, separate from submission/input hashing; deterministic escaping must preserve allowed values rather than normalize them. Validate exact whole-content/task identity and stored digest before reads, with ownership/state/trusted-known-expiry checks first. Unknown/corrupt representation is controlled unavailable without generation, enqueue, current-settings rendering or TTL extension. Keep timestamp/owner/fence metadata outside the opaque payload and retain safe expiry/purge/deletion behavior.

Add test-after coverage for complete successful summary/translation capture, storage and reads with U+0000, empty strings, ordinary/decomposed/astral Unicode, whitespace, escaping and literal backslash-u sequences; corruption, digest mismatch and unknown representation must fail safely. Required actual PostgreSQL tests prove the selected database-boundary behavior after admission/realm qualification; an in-memory round-trip alone does not resolve Infrastructure R-03. The shared C2/public preparedResult v1 and historical SQL 002 remain authoritative; this choice permits planning the concrete repair, not implementation or a retroactive finding disposition.

## Q6. Lossless Prepared-Result Storage

The new Infrastructure R-03 finding requires a storage representation that can preserve every valid C2 string, including U+0000. Which representation should the revised implementation plan specify?

- A. **Escaped JSON in TEXT (Recommended)** — Store versioned canonical ASCII-escaped JSON text, preserving values exactly on decode. It fits the existing serialized-content model with fewer codec steps; revise the unapplied payload column/checks and keep full validation/integrity plus relational authority safeguards.
- B. **Versioned JSONB capsule** — Keep JSONB as a safe metadata capsule with an ASCII/Base64 encoded canonical payload, adding explicit versioned encoding/decoding, corruption handling and encoded-size qualification.
- X. Other (please specify)

Recommendation: A because result queries retrieve the whole immutable payload and currently need no content-path index/query, while the existing model already retains serialized content. Both approaches retain the current relational placement and require real persistence/reader proof; no character filtering, contract narrowing or generative repair is selected.

[Answer]: A. Escaped JSON in TEXT (Recommended)

The human replied exactly `Escaped JSON in TEXT`. The revised plan will specify the opaque escaped-JSON TEXT payload and its validation/integrity/authority boundaries, with the database-specific representation repair and real round-trip tests included in the current approval scope. This is a planning choice; Infrastructure R-03 is not marked resolved by it.

## Q7. Supplemental Planning Checker Recovery

The current plan/instructions/handoff amendment is written, its four originals have matching archived byte identities, and required-section plus scoped whitespace checks passed. The supplemental temporary `verify_u1_code_plan_revision.py` check failed twice: first it did not recognize an integration action as an implementation step; after that correction it treated the required verbatim Testing Contract's `team.md` mention as a stage-local Markdown source reference. The latter is a citation-parser defect, not permission to change the Testing Contract or evidence of a missing project rule. No independent pre-implementation review or current exact Plan Approval has been claimed.

The checking attempt is paused after the second failure. How should we proceed?

- A. **Abandon and replace checker (Recommended)** — Abandon the faulty supplemental citation-check implementation and replace it with a prose/code-fence-aware check, keeping the native checks, exact Testing Contract, architecture decisions and quality floors. Run the corrected checks and requested independent review before presenting exact Plan Approval.
- B. **Pause here** — Preserve the amended documents and existing source/evidence for later resumption before checking/review/approval.
- X. Other (please specify)

[Answer]: A. Abandon and replace checker (Recommended)

The human replied exactly `Abandon and replace checker`. This explicitly abandons the faulty supplemental checking implementation and authorizes its prose/code-fence-aware replacement with the existing native checks and quality obligations retained. It is not Plan Approval or acceptance of unresolved implementation/operational findings.

## Historical Implementation-Planning Amendment Confirmation

- **Planning amendment and preserved work (Q5: Modify):** Modify the existing `code-generation-plan.md` and `unit-test-instructions.md` from the current approved Contract, Functional, NFR and Infrastructure inputs. Archive prior planning/instruction/handoff versions first. Retain the actual partial models/schema/runner/lock/build-copy implementation, 29 claimed source writes, historical executed results, explicit unfinished/GAP rows and original immutable 395-file dirty-source baseline. Reconcile the step sequence/progress and source/test blast radius rather than restarting completed work, ticking unverified steps or relabelling old tests/approvals as current. U1 still delivers the real summarize journey and both-task backend guarantees; U2/U3 keep their approved later allocations.
- **Lossless result storage (Q6: Escaped JSON in TEXT):** Specify the whole immutable prepared payload as opaque canonical ASCII-escaped JSON in a nullable `prepared_content TEXT` column, with SQL NULL permitted only for the existing guarded purge lifecycle. An original U+0000 is stored as literal escape characters, decoded to the original value by the application; a literal backslash-u sequence remains distinguishable. Preserve required code/data strings, ordinary/decomposed/astral Unicode, whitespace, escaping and empty strings exactly, along with bare DocModel/final personalization. Introduce the content-specific private `canonical-json-ascii-v2` policy: deterministic key ordering/compact serialization/ASCII escaping and finite JSON values, digest derived from original values through that declared canonical byte representation and explicit encoding/canonical version verification. Keep browser original-input SHA-256 and server input identity separate and unchanged; do not apply the new content serializer globally or recompute existing bindings under a different identity policy. Public preparedResult v1 remains decoded C2 content, not a storage wrapper or escaped display string.
- **Schema, validation and authority:** Revise only the unapplied draft 003 payload representation/checks and necessary current model/store/test paths. Replace raw JSONB payload operators with explicit text/encoding/lifecycle checks and full C2/task/identity/digest validation before guarded binding and after authorized reads; never cast/decode the opaque payload through SQL JSONB/JSON processing. Keep structured owner/job/task/version/digest/timestamp metadata and relational FK/state/fence/immutability/expiry/purge/deletion guarantees, short bounded operations, separate T5 preparation and T6 terminal publication, one-time fixed expiry and no resurrection. Unknown/corrupt/unsupported encoding or digest is controlled unavailable after owner/state/trusted-known-expiry precedence, not reconstruction or generative repair. Preserve historical migration 002 and supported legacy/keyless authority handling; no guessed adoption of absent legacy markers.
- **Exact-content and timestamp evidence:** Add meaningful test-after capture/serialize/persist/read regressions for both tasks, including U+0000 versus literal backslash-u, Unicode/escaping/empty strings, corruption, digest mismatch and unsupported storage version. Verify the complete declared C2 string domain and actual database binding/reader path; in-memory or escaped-text inspection alone is not real PostgreSQL acceptance. Enforce corrected required code/data object/no extra nested fields; remove the partial codec's unapproved string fallback and reject additional reproducibility fields instead of silently dropping them. Retain available timezone-aware RFC 3339/calendar/offset checking for preparedAt/expiresAt/DocModel generatedAt, explicit missing-checker failure and real fresh-database-time before/at/after-expiry, duplicate-publication, changed-settings/configuration, malformed/legacy/purge/deletion/store-failure cases. Preserve 401/generic404/409/trusted410/unavailable422/transient503/gateway504 and zero read generation/enqueue/submit/current-settings rendering. Infrastructure R-03 remains New pending the concrete repair/proof and owning review/disposition; Contract Design R-03 independently remains Accepted risk, not fixed by synthetic format checks.
- **Narrow migration admission and footprint:** Reconcile `backend/migrations/__init__.py` and any narrowly required policy/test additions through the current plan and supplemental original-byte/absent-path capture checked against the original approved full source listing before their writes. Preserve the existing snapshot; never recapture modified bytes, substitute HEAD or claim unrelated user work. Plan an explicit reviewed owner/identity/full-script-digest-bound procedural-script treatment, retaining the default conservative path and same-connection current authority, canonical locks, per-step transaction/ledger and guarded commit. Review the actual revised 003/policy together; tests include changed/unknown script identity/digest, revoked authority, top-level transaction/nontransactional/external-effect/role/system/database escape negatives. No raw rejected SQL or blanket procedural exemption is selected.
- **Qualified prerequisites and ordered implementation:** Materialize the public database-only bootstrap plan with qualified concrete artifacts/runtime/launcher, separately authorized resource/rule/credential/reversal scope and independently measured protected realm/role/marker/digest/network identity before fixture mutation. Preserve distinct full authority and later adapted minimal-purge databases, read-only preflight and required no-skip schema/owner proof before later ordered store/service/dispatcher/supervisor/maintenance/controller/BFF/browser work. Retain unresolved PostgreSQL/image/runtime/provider/control/notification findings and MinIO UNOBTAINABLE; a local-only substitute, written verified flag or missing-live-test skip cannot supply acceptance. Keep production source/venv/.next, credentials, live roles and shared broker outside development execution; operational application retains its separate concrete authorization.
- **Retained integration and operating choices:** Keep current owner/session/current-context guards, full captured-input idempotency hash, optional draft/tracking references, command-free result/tracking recovery, real LF/opaque SSE cursor/state-history separation, fixed nonoverlapping two-second fallback, cookie/error/redirect fidelity, accessible conditional focus/announcements and scrubbed diagnostics. Preserve Mac/launchd/Cloudflare, isolated same-host staging, qualified Squid/guest/provider enforcement, exact-main-commit pull delivery, all-queue safe broker transition and compatible readable rollback. Keep H/L 15/90 seconds, V/R 120/30, D/Q/J=5, scan 30, ambiguity 120, current authority/pass-admission margins, independent renewal, 20-second/100-row maintenance passes, hourly cleanup/60-second continuation, 86,400-second live-payload purge and current monitoring thresholds/accurate external watchdog boundary. Measure both exact result branches and larger translations under qualified resources; strict SSE/status p95 below 300/200 ms retains the real authenticated production-build/same-region/one-active-job/100-sample profile and at least two real-store competing actors. No new cloud/runtime, result-size cap, throughput/uptime or backup-erasure commitment is added.
- **Testing, current source evidence and approval:** Embed the freshly rendered Testing Contract unchanged: `sha256:f87c0507a83e45b42705d96d9cdb5a9124962ca7bb56c2fd06fd2061fcc42153`, test-after/test-last per component, Standard five–eight tests with happy/error coverage plus required boundary/E2E/security/performance cases, ≥80% complete source-bound new/changed executable-line coverage and required CI. Preserve current suites/lint/strict types and the three assigned baseline SSE failures until repaired; reconcile the stricter imported graph without weaker flags/exclusions or broad later-Unit refactors. Refresh obsolete script/Dockerfile/upstream-finding claims from actual current sources. After this summary is confirmed, produce the current story-linked ordered plan/exact scoped test instructions, run meaningful document/source checks and the requested fresh pre-implementation engineering review, then obtain current-attempt exact Plan Approval before developer execution. Final implemented-code review, October 14 security review with revenantonthemission/completed-asset follow-up, and the separately human-authorized real integrated invocation/skeleton checkpoint remain required. This summary confirmation authorizes the planning amendment, not application/resource execution or acceptance of unresolved findings.

Does this all look correct before I generate the artifact?

- Looks correct
- Request changes

[Answer]: Looks correct

## Plan Approval

Approve this exact Code Generation plan?

This current-attempt decision covers `code-generation-plan.md`, its unchanged complete native Testing Contract and `unit-test-instructions.md` for u1-job-skeleton. The requested current pre-implementation senior-engineering review is `reviews/implementation-plan-review-03.md`: all four prior planning concerns remain Resolved and no new grounded planning repair is required. This review is not the final implemented-code review or operational/skeleton acceptance. Actual partial source/baseline/evidence and qualified-realm/admission/coverage obligations remain binding.

The current tool-produced approval/source tags are recorded here before presentation. The historical tags/answer above remain prior provenance and are not reused as current authority.

[Approval Fingerprint]: sha256:v3:ea95305833651a01cd3fda1b7f256870ef61615a3bc3c4e5957cdebf689b6d21
[Planned Source]: 1e1bb78c35f28326e3fec0c917efc314637256cebc0c91fcb4f966c9180e8d72

- Approve Plan — Authorize developer implementation of this exact current plan and scoped test instructions through its protected receipt; required focused SQL review, qualified realm/resources and separate operational/checkpoint authorizations remain required.
- Request Changes — Revise the plan or test instructions before implementation.

[Answer]: Approve Plan

## Re-entry Context — Human-Directed Redo

The human directed a backward redo of code generation so that the missing frontend job surface lands under u1-job-skeleton before U2 proceeds (the U2 reconciliation question was answered "B. Reopen U1 for a completion pass first"). The engine executed the human-directed backward jump (`aidlc engine jump execute --target code-generation --direction redo`, 2026-10-07T06:35:34Z). Earlier answers, decisions and confirmations in this file remain preserved as prior provenance and are not reused as current-attempt authority.

Artifact re-use: **Modify** — the 50-step `code-generation-plan.md`, `unit-test-instructions.md`, `code-summary.md`, `traceability.json`, this questions file and `source-manifest.json` are retained and updated in place; nothing is redone from scratch.

Completion-pass scope: implement the plan's missing frontend job-surface steps that U1's completion boundary and U2's dependency require — the BFF-routed content-job transport (Step 19 frontend/BFF portion and Step 21), the pre-job submission surface (Steps 23-26), the error-containment surfaces (Steps 27-30), the live job status projection with replay/reconnection and the fixed two-second fallback (Steps 31-32), the query-only completed-result modal (Steps 33-34), the stable parent composition (Steps 35-36) and the scrubbed diagnostics (Steps 37-38), each with its test-after rows under the u1 unit-scoped configs; then update `code-summary.md`, `source-manifest.json` and `traceability.json` and obtain a fresh current-attempt review. Backend/SQL/staging steps that remain blocked on independent qualified SQL/realm/operator prerequisites stay as recorded obligations outside this pass (Steps 2, 5-18, 39-47 as applicable); this pass claims no real database/operational evidence.

Review cycle and restart: two adversarial review passes then ran on the completion-pass record (both reaching NOT-READY at their iteration caps; their findings R-01–R-14 were dispositioned and every actionable finding was fixed on the working bytes, including the persona-enum, owner-bound-recovery and evidence-wording repairs). Because a stage attempt allows two review passes, the human selected the engine's offered recovery — restart the stage from the top (`aidlc engine orchestrate next --stage code-generation` → `aidlc engine jump execute --target code-generation --direction redo`, 2026-10-08T02:28:15Z) with the revision instruction "Re-check the current bytes". This entry re-confirms the summary once and re-saves every output document under that confirmation; the restart itself changes no artifact content, and the fixed application/test bytes carry forward unchanged.

Fresh consolidated-summary confirmation and fresh exact Plan Approval are required under the new attempt before generation, because the earlier attempt-scoped receipts do not authorize this attempt.

## Consolidated Summary Confirmation

- **Current choices and documents:** Retain Q5 Modify and Q6 Escaped JSON in TEXT, and add the human-selected Q7 abandonment/replacement of the faulty supplemental checker. The 50-step `code-generation-plan.md`, exact `unit-test-instructions.md`, preserved partial `code-summary.md` and current `recovery-impact.md` are amended from current approved inputs. Their four original archived Git blob identities match. Preserve the source manifest at the count approved with this confirmation (40 claims — 29→38→40 lineage; `source-manifest.json` remains the live claim authority and has since grown with the completion pass's 29 claimed writes, 69 current; the two Q8-A claims being `ops/server/u1_colima_executor.py` and `ops/tests/test_u1_colima_executor.py`), original immutable395-file baseline, historical executed results and all184 partial trace rows/unfinished obligations; current planning is not current implementation or execution authority.
- **Selected exact storage:** Prepared content is canonical ASCII-escaped JSON stored as opaque TEXT, with SQL NULL only for guarded payload purge and exact application decode. Keep the private content-only canonical-json-ascii-v2/version/digest policy separate from unchanged browser/server input identity. Preserve required string code/data with no extras/fallback, complete permitted C2 strings including NUL versus literal backslash-u, and bare DocModel/final personalization. Public preparedResult v1 contains decoded values. No SQL JSON/JSONB cast/function/operator may process the opaque payload; application C2/task/identity/digest checks accompany retained typed metadata/owner/state/fence/FK/immutability/expiry/deletion safeguards.
- **Tests and failure handling:** Retain test-after exact capture/serialize/schema/store/read cases for both tasks, Unicode/escaping/empty strings, corruption/digest/unknown version, active RFC3339/calendar/offset checking and actual fresh-database-time preparation/publication/before-at-after fixed expiry. Owner/state/trusted-known-expiry precedes permanent unavailable versus transient failure; every read/retry has zero generation/enqueue/submit/current-settings rendering. Infrastructure R-03 remains New pending concrete repair/real-store proof; Contract Design R-03 remains the separate Accepted risk, not repaired by document/format checks.
- **Admission, footprint and real prerequisites:** Retain supplemental original-byte/new-path capture against the original full listing, narrowly reviewed fixed owner/identity/full-script-digest admission and the inherited conservative/default/same-connection authority/lock/transaction/ledger/guarded commit protections. Focused independent actual003/policy review follows implementation/local negatives and precedes procedural SQL execution. Complete inspect-by-default database-only bootstrap and actual qualified independently measured protected realm/role/marker/digest/network proof with separate operator authorization precede required no-skip schema/owner/TEXT-column acceptance and later ordered store/worker/browser work. Authority and later guarded minimal-purge targets remain distinct; no raw bypass, proof flags, local substitute, source recapture or unqualified artifact supplies acceptance.
- **Integration, operating choices and quality:** Retain the approved U1 summarize journey/both-task backend, U2/U3 later allocation, current-session/original-input/recovery/cursor/state-history/accessibility/diagnostic guarantees, Mac/launchd/Cloudflare/private staging/Squid/guest/provider/qualified pull/all-queue transition/readable rollback choices and all selected resource/timing/maintenance/alert/latency profiles. The exact native Testing Contract f87c0507a83e45b42705d96d9cdb5a9124962ca7bb56c2fd06fd2061fcc42153 remains byte-identical: test-after/Standard, at least80% complete source-bound coverage, current suites/lint/strict types and required real-store/browser/security/performance evidence. Pending images/runtime/provider/control/channel/MinIO and existing SSE/strict-graph defects remain actual prerequisites or assigned repairs.
- **Checker recovery and executed evidence (Q7):** Preserve the abandoned temporary checker and use its prose/code-fence-aware replacement. The replacement passed three regression checks, four exact archive identities, unchanged Testing Contract, 50 ordered steps/only historical capture complete, 11 tables, 45 resolving Markdown references, 19 scoped commands, the pre-Q8-A historical 29-claim count (the Q7 checker ran before the two Q8-A executor claims were added; the manifest count at this confirmation is 40 by the 29→38→40 lineage in the confirmed summary above — the live claim authority has since grown to 69 with the completion pass's claimed writes),184 rows with178 GAP/six Deferred and original395-file inventory. Native required sections and scoped whitespace checks passed. Results are recorded in `../../../verification/u1-code-generation-plan-checks.md`. This is document/source consistency, not application/database/operational acceptance; no native or quality obligation was removed.
- **Next review and approval:** Confirm the complete current answer set including Q7 before reassociating the existing planning outputs with this confirmation and obtaining requested fresh independent pre-implementation engineering scrutiny. Present current exact Plan Approval after the concrete plan/instructions/review are final; developer/source execution waits for that protected human decision. Final implemented-code/source/coverage review, October14 security/completed-asset follow-up, separately authorized resource/rule operations and the separately human-authorized real integrated invocation/skeleton checkpoint retain their own roles. No finding acceptance, completed Unit or later-Unit/release unlock is inferred.

Does this all look correct before I generate the artifact?

- Looks correct
- Request changes

[Answer]: Looks correct

## Q8. PostgreSQL Artifact and Operator Handoff

Q4 already selected **Prepare an isolated-bootstrap plan**. That public plan and the inspect-only bootstrap module are prepared; the selected hosting, staging boundary, TEXT storage, testing requirements and approved implementation sequence remain the starting decisions. The second focused source check in `reviews/migration-admission-review-02.md` resolves both SQL/codec findings at the source/local boundary. It does not supply actual PostgreSQL acceptance or operational authorization.

The next required schema lane still lacks admitted PostgreSQL/workload artifacts, a concrete qualified privileged executor and independently measured protected realm evidence. `ops/platform-integrity/sbom-targets.json` still lists the PostgreSQL candidate with blocking High **CVE-2026-85091** and `CANDIDATE_PENDING_OPERATOR_MAINTENANCE_WINDOW`. `ops/server/u1_db_bootstrap.py` exposes an inspect-only CLI and a protected operator-executor port, not a concrete privileged Colima implementation. No current answer or audit receipt selects an artifact remedy or supplies that operator handoff.

Which outstanding artifact/operator handoff should I pursue next?

- A. **Investigate remediation and prepare the launcher handoff (Recommended)** — Investigate a fixed, pinned PostgreSQL/base closure and prepare the concrete Colima executor/configuration, resource limits/identities, scoped network rules, protected credential-delivery channel and owned reversal for review. Report unavailable fixes or remaining qualifications explicitly. Image build/pull, provisioning, guest-rule and credential application still require their separate concrete authorization; this choice authorizes preparation, not a vulnerability exception or live application.
- B. **Provide a qualified operator handoff** — Supply non-secret admitted artifact/runtime/launcher/configuration and measured-proof locations with trusted hashes through revenantonthemission. Keep credential values in the protected operator channel. A newly available independently qualified realm can be proposed with these bindings; its actual role/marker/network/source/validity checks must pass before mutation.
- C. **Pause here** — Preserve the current implementation and source/local evidence until the qualified artifact/operator prerequisites are available.
- X. Other (please specify)

[Answer]: A. Investigate remediation and prepare the launcher handoff
