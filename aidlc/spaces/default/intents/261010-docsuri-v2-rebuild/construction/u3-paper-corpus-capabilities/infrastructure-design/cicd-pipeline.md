# U3 CI/CD and operations design

Date: 2026-10-15 (Asia/Seoul). Unit: `u3-paper-corpus-capabilities`. This document designs the delivery pipeline, environment flow, migration/publication/rollback procedures and evidence operations that realize U3's confirmed infrastructure decisions. It performs no deployment, migration or public operation; the canonical contracts (C04–C06, C13, C14) and the shared application baseline (host, PostgreSQL owner transactions, worker control loop, scoped runners) remain authoritative.

## Delivery pipeline — stages and gates

The pipeline extends the existing scoped-runner pattern. Each stage is content-hashed, read-only where possible, and fails closed; untrusted PR jobs receive no secrets (NFR4.4).

| Stage | What runs | Gate / failure rule |
|---|---|---|
| Source | Branch naming and PR target per CONVENTIONS.md; frozen base revision recorded | Refuse a PR that does not target `develop` under the interim CI policy; record the base SHA. |
| Lint & typecheck | Python Ruff; frontend ESLint + strict `tsc` | Fail fast on any violation; no waivers. |
| Unit/component | `pytest` scoped to `tests/u3_paper_corpus_capabilities/component` | Zero tests collected or any skip is a failure; assert behaviour, not collection. |
| Database | Real PostgreSQL synthetic realm phases (uniqueness, eligibility revisions, publication receipts, races) | Missing/foreign realm identity is a failed prerequisite, never a skip. |
| Repository | Real owner roles and transaction facility (paging, receipts, change facts, read-only recovery) | Fail on substituted in-memory success. |
| Integration | Mounted host through the real boundary (C04–C06 operations, provider fixtures labelled synthetic) | Dependency-outage and error-mapping cases included; fixture-only provider success is labelled, not parity. |
| Operations | Bounded fault schedules (partial writes, crash boundaries, saturation, provider limits, restore rehearsal) | Capacity/preflight failure stops with evidence instead of shrinking assertions. |
| Frontend unit + browser | Scoped Vitest and Playwright for U3 surfaces (discovery/reading/assistance, states, reflow) | Real API/DB; no route mocks replacing behaviour; accessibility automated checks recorded with limitations. |
| Contract conformance | C04–C06/C13/C14 boundary checks (one state/event contract, framing/reconnect, prepared-result shapes, error mapping; Q-01–Q-04 closure) | Existing U1/U2 consumers re-verified before behaviour changes; incompatibility refuses explicitly (NFR10.1–10.2). |
| Coverage | U3 production paths measured; additive 80% floor for new code | Never lower a configured threshold; gaps reported, not excluded. |
| Evidence bundle | Command, exit code, counts, skips, source/lock/policy/fixture hashes; redacted diagnostics | Retained with the run; failed/unknown responsibility evidence is preserved before teardown. |

Every stage above is exercised through the real mounted boundary in its phase; test doubles are conformance-checked against the same contract and cannot return impossible success (NFR10.2).

## Environment and release flow

- One local application release hosts the embedded U3 contribution (CorpusContent, Discovery, PaperAssistance) with its worker and optional model runtime on the shared host; no second service, broker or store is introduced (NFR7.1).
- Work integrates on a short-lived working branch through a PR into `develop` under CONVENTIONS.md and its interim CI policy. Main promotion is separate and human-gated; this design performs no public deployment, no billing activation and no real-data migration (NFR8.1).
- Environments: local synthetic development (this pipeline) and, behind their evidence gates, any eventual public operation — whose hosting, capacity and provider decisions remain unselected and out of scope here.
- Synthetic environments are owned, finite and disposable: identity/ownership checks precede any use; failed environments remain inspectable; teardown preserves required evidence first.

## Migration, publication and rollback procedures

| Procedure | Design |
|---|---|
| Migration | Ordered, compatible migrations for corpus/search/assistance tables under the shared owner-transaction facility; stop → migrate → start verification with recorded schema identity; append-only amendments; no destructive real-data migration. |
| Publication | Projection publication follows the CAS/quarantine discipline: a new generation is distinct from the published one and only publishes when manifest, receipts, eligibility and compatibility all verify (BR2.3). |
| Rollback (code/config) | Revert the release artifact/configuration to the previous pinned revision; migrations are backward-compatible so the previous release remains operational; verification reruns the affected phases. |
| Rollback (projection) | Re-point publication to the previous complete generation (CAS); never serve a partial generation; eligibility revisions remain authoritative regardless of publication state. |
| Restore | Restore runs into the quarantine target, replays current withdrawal boundaries and verifies receipts/owner relationships before any serving; previous-era authority cannot resurrect prohibited content (BR3.1, NFR3.4). |
| Failure evidence | Each procedure records its command, expected/observed outcome and preserved evidence before any teardown or replacement (NFR3.3, NFR9.1). |

## Resource configuration and $0 guardrails

- Finite limits (pool sizes, run/batch concurrency, queue depth, retry counts, page sizes, citation traversal bounds, model concurrency, disk watermark) are configuration with recorded values and validation before operation; numbers are agreed after baseline measurement (NFR2.2, NFR8.2).
- The measurement procedure from the technology decisions is wired into the operations phase: cold/warm workloads, contention and exhaustion schedules, distributions and raw safe evidence (NFR2.2).
- Refusal states (`POLICY_UNRESOLVED`, `CAPACITY_EXHAUSTED`, explicit degradation) are first-class pipeline expectations, never converted into green skips (NFR5.1, NFR8.1).
- No paid provider, endpoint, runner or overage is configured; a required capability that cannot fit $0 fails loudly for human decision rather than silently falling back (NFR8.1).

## Secrets and protected material

| Rule | Application |
|---|---|
| No secrets in repositories, images or CI logs | All checks; secret scans in the pipeline; redaction of evidence artifacts. |
| Untrusted PR jobs receive no secrets | Only trusted/local runs may touch protected fixtures; CI on PRs runs read-only, secret-free stages. |
| Protected fixtures | Mode-restricted local paths with documented ownership/expiry; credentials never printed; provider fixtures explicitly synthetic (NFR4.4, NFR5.3). |
| Credential handling | Only environment-owned secrets at runtime; no client-side or logged material (NFR4.4). |

## Evidence and recovery operations

- Each phase writes its evidence record (command, exit code, counts, skip reasons, source/lock/policy/fixture/manifest hashes, fault schedule, resource observations) under its owned run directory and a redacted summary accompanies the PR.
- A maintainer can reproduce setup, a representative corpus/search/assistance defect and its repair from a clean checkout using pinned dependencies, isolated synthetic configuration and the recorded phase commands; diagnosis/repair/recheck durations are recorded (NFR7.2).
- Failed or unknown responsibility evidence is preserved before teardown or environment replacement; recovery changes reported state only after capability checks succeed (NFR3.3, NFR9.2).
- The pipeline surfaces the carried review findings through its traceability/section/upstream gates instead of masking them with green tests.

## Requirement mapping

| Requirement | Pipeline element |
|---|---|
| NFR1.3, NFR3.3–3.4 | Database/operations phases; migration/publication/rollback and restore procedures |
| NFR2.2–2.3 | Measurement wiring; bounded phases; exhaustion schedules |
| NFR4.3–4.4, NFR5.1, NFR5.3 | Secrets/protected-material rules; permission fixtures; redaction |
| NFR6.1–6.2 | Frontend unit/browser stages; state confirmations in evidence |
| NFR7.1–7.3 | Scoped runner pattern; pinned dependencies; compatibility/license evidence gates |
| NFR8.1–8.2 | Resource configuration and $0 guardrails; refusal states |
| NFR9.1–9.2 | Evidence bundle; readiness distinction; recovery operations |
| NFR10.1–10.2 | Contract-conformance stage; double-conformance and incompatibility refusal |

This design claims no execution: every gate above becomes evidence only when the corresponding phase actually runs under its owned environment.
