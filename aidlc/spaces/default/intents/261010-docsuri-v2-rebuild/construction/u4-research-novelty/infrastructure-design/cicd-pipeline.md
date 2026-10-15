# U4 CI/CD and operations design

Date: 2026-10-16 (Asia/Seoul). Unit: `u4-research-novelty`. This document designs
the delivery pipeline, environment flow, migration/expiry/rollback procedures and
evidence operations that realize U4's infrastructure decisions. It performs no
deployment, migration or public operation; the canonical contracts (C07, C12, C14,
C13) and the shared application baseline (host, owner transactions, worker control
loop, scoped runners) remain authoritative.

## Delivery pipeline — stages and gates

The pipeline extends the existing scoped-runner pattern. Each stage is
content-hashed, read-only where possible, and fails closed; untrusted PR jobs
receive no secrets (NFR4.5).

| Stage | What runs | Gate / failure rule |
|---|---|---|
| Source | Branch naming and PR target per CONVENTIONS.md; frozen base revision recorded | Refuse a PR that does not target `develop`; record the base SHA. |
| Lint & typecheck | Python Ruff; frontend ESLint + strict `tsc` | Fail fast on any violation; no waivers. |
| Unit/component | `pytest` scoped to U4's component tests (draft CAS, evidence, attachment refusals, cancellation races) | Zero tests collected or any skip is a failure; assert behaviour, not collection. |
| Database | Real owner-scoped PostgreSQL realm phases (context binding, tombstones, immutable revisions, monotonic job sequence) | Missing/foreign realm identity is a failed prerequisite, never a skip. |
| Repository | Real owner roles and transaction facility (revisions, tombstones, evidence, usage reconciliation) | Fail on substituted in-memory success. |
| Integration | Mounted host through the real boundary (C07 operations, C12 adapter fixtures labelled synthetic, C14 delivery); revoked, expired and anonymous session cases per private surface | Dependency-outage, unknown-outcome and error-mapping cases included; a revoked/anonymous session must receive no private read, list, event or asset; fixture-only provider success is labelled, not parity. |
| Operations | Bounded fault schedules (lost response, restart mid-turn, cancellation/completion race, tombstone vs late write, upload/extraction failure) | Capacity/preflight failure stops with evidence instead of shrinking assertions. |
| Frontend unit + browser | Scoped Vitest and Playwright for U4 surfaces (session, evidence, attachments, drafts, novelty, progress and unknown states) | Real API/DB; no route mocks replacing behaviour; accessibility checks recorded with limitations. |
| Contract conformance | C07/C12/C14/C13 boundary checks: state machines, draft CAS and exact-revision consumption, C12 outbound-target rejection, C14 owner-commits-state, immutable artifact tuple | Existing consumers re-verified before behaviour changes; incompatibility refuses explicitly (NFR10.1–10.2). |
| Privacy and policy gates | Policy-unresolved refusals stay refusals; private identity never resolves on a public route; telemetry redaction checked | A refusal converted into a green skip fails the stage (NFR5.2, NFR5.5). |
| Coverage | U4 production paths measured; additive 80% floor for new code | Never lower a configured threshold; gaps reported, not excluded. |
| Evidence bundle | Command, exit code, counts, skips, source/lock/policy/fixture hashes; redacted diagnostics | Retained with the run; failed/unknown responsibility evidence preserved before teardown. |

Every stage runs through the real mounted boundary in its phase; test doubles are
conformance-checked against the same contract and cannot return impossible success
(NFR10.3).

## Environment and release flow

- One local application release hosts the embedded U4 contribution
  (`ResearchWorkspace`) with its worker and bounded local model/extraction runtime
  on the shared host; no second service, broker or store is introduced (NFR7.1).
- Work integrates on the short-lived working branch `feature/u4-research-novelty`
  through a PR into `develop` under CONVENTIONS.md. Main promotion is separate and
  human-gated; this design performs no public deployment, no billing activation
  and no real-data migration (NFR8.1).
- Synthetic environments are owned, finite and disposable: identity/ownership
  checks precede use; failed environments remain inspectable; teardown preserves
  required evidence first.
- Private data never leaves its owner scope in any environment: fixtures are
  synthetic, and no uploaded or retrieved content is reused across runs
  (NFR5.1, NFR5.4).

## Execution payload enablement (closing the carried contract gap)

C14 states that owners other than PaperAssistance "require a compatible payload
codec before enablement", and its `readExecutionPayload` is typed
`AssistanceExecutionPayload`/`AssistanceAcceptedInput` with the semantics "U1
supports only PaperAssistance; other owner payload codecs remain INCOMPATIBLE
until coordinated by their unit". The NFR Design review left this open for U4.
**There is therefore an open cross-unit gate that U4 cannot close alone:**

1. **Precondition — contract amendment (owner: the contract authority for
   C00/C14, with U4 as requester).** Before any codec work, C00 must gain a
   ResearchWorkspace accepted-input/payload type (or a generalized owner payload
   shape) and C14's `readExecutionPayload` must accept U4's operation kinds. The
   amendment is executed through the normal revision path for
   `contract-summary.md`; this design neither performs nor pre-empts it.
2. **U4's obligation — proof, not prose.** Once the amendment exists, U4
   registers a durable codec for its own operation kinds and proves it with a
   mounted `acquireExecutionClaim` → payload-read → `recordCompletion` round trip
   in the Integration stage (NFR10.1, NFR10.3).
3. **Fail-closed until then.** While the amendment or the round trip is missing,
   U4's accepted-work path is **not enabled**: acceptance refuses with the explicit
   incompatibility outcome rather than accepting work no worker can retrieve, and
   the pipeline refuses to green-light the Operations stage for U4.
4. The gate is recorded as an open item carried to the unit checkpoint; a green
   unit run cannot stand in for an enableable job path.

## Migration, expiry and rollback procedures

| Procedure | Design |
|---|---|
| Migration | Ordered, compatible migrations for context/session/turn/novelty/draft/evidence records under the shared owner-transaction facility; stop → migrate → start verification with recorded schema identity; append-only amendments; no destructive real-data migration. |
| Artifact expiry | Owner-scoped declared expiry is applied by a bounded, idempotent sweep; expired artifacts are disclosed as expired and never regenerated or exported (BR7.3). |
| Rollback (code/config) | Revert the release artifact/configuration to the previous pinned revision; migrations stay backward-compatible; verification reruns the affected phases. |
| Rollback (data) | Immutable revisions and tombstones are never rewritten; a bad revision is superseded by a new one, and a mistaken tombstone is repaired only through the recorded recovery path, never by deleting the boundary. |
| Deletion and restore | Deletion writes the tombstone before cleanup and applies the defined dispositions to pending work, drafts, attachments and derived data; a restore replays current tombstones and re-verifies owner relationships and derived-data disposition before serving (BR5.4, NFR5.3). |
| Failure evidence | Each procedure records its command, expected/observed outcome and preserved evidence before any teardown or replacement (NFR3.1, NFR9.1). |

## Resource configuration and $0 guardrails

- Finite limits (upload bytes, queue depth, run/batch concurrency, retry counts,
  page sizes, model concurrency, artifact retention window, disk watermark) are
  configuration with recorded values and validation before operation; numbers are
  agreed after baseline measurement (NFR8.1; no numeric target is asserted here).
- The measurement procedure from the technology decisions is wired into the
  Operations stage: cold/warm workloads, contention and exhaustion schedules,
  distributions and raw safe evidence (NFR2.2).
- Refusal states (`POLICY_UNRESOLVED`, `CAPACITY_EXHAUSTED`,
  `SOURCE_INELIGIBLE`, explicit limitation) are first-class pipeline
  expectations, never converted into green skips (NFR5.2, NFR8.2).
- No paid provider, endpoint, runner or overage is configured; a capability that
  cannot fit $0 fails loudly for human decision rather than falling back
  (NFR8.2).
- Outbound retrieval targets are validated before fetch in every environment,
  including local ones, so a fixture cannot mask a missing validation (NFR4.6).

## Secrets and protected material

| Rule | Application |
|---|---|
| No secrets in repositories, images or CI logs | All checks; secret scans in the pipeline; redaction of evidence artifacts. |
| Untrusted PR jobs receive no secrets | PR jobs run read-only, secret-free stages; only trusted/local runs touch protected fixtures. |
| Private content is not evidence material | Evidence bundles carry hashes, identifiers and counts, never private text or attachment content (NFR9.1). |
| Protected fixtures | Mode-restricted local paths with documented ownership/expiry; credentials never printed; provider fixtures explicitly synthetic (NFR4.5, NFR5.3). |

## Evidence and recovery operations

- Each phase writes its evidence record (command, exit code, counts, skip reasons,
  source/lock/policy/fixture/manifest hashes, fault schedule, resource
  observations) under its owned run directory, with a redacted summary on the PR.
- A maintainer can reproduce setup, a representative research/novelty defect and
  its repair from a clean checkout using pinned dependencies, isolated synthetic
  configuration and the recorded phase commands; diagnosis/repair/recheck
  durations are recorded (NFR7.1–7.3).
- Failed or unknown responsibility evidence is preserved before teardown or
  environment replacement; recovery reports changed state only after capability
  checks succeed (NFR3.1, NFR9.2).
- The pipeline surfaces carried review findings through its traceability/section
  gates instead of masking them with green tests.

## Requirement mapping

| Requirement | Pipeline element |
|---|---|
| NFR1.1–1.5 | Unit/Integration/Operations stages; evidence and grounding fixtures; assessment scale checks |
| NFR2.1–2.3 | Ordering assertions; measurement wiring; bounded phases and exhaustion schedules |
| NFR3.1–3.5 | Database/Operations phases (restart, races, tombstones); migration/expiry/rollback procedures |
| NFR4.1–4.6 | Privacy and policy gates; secrets/protected material; outbound-target validation |
| NFR5.1–5.5 | Privacy and policy gates; deletion/restore procedure; private-content evidence rule |
| NFR6.1–6.3 | Frontend unit/browser stages; accessibility checks with recorded limitations |
| NFR7.1–7.3 | Scoped runner pattern; pinned dependencies; recovery operations |
| NFR8.1–8.2 | Resource configuration and $0 guardrails; refusal states |
| NFR9.1–9.2 | Evidence bundle; readiness distinction; redaction |
| NFR10.1–10.4 | Contract-conformance stage; execution payload enablement; usage reconciliation checks |

This design claims no execution: every gate above becomes evidence only when the
corresponding phase actually runs under its owned environment.

## Sources

- [NR] `../nfr-requirements/security-requirements.md` (NFR1.1–NFR10.4), `../nfr-requirements/tech-stack-decisions.md`.
- [ND] `../nfr-design/security-design.md`, `../nfr-design/logical-components.md` — including the bridge to this stage.
- [CT] `../../../inception/contract-design/contract-summary.md` — C07, C12, C14, C13.
- [CV] `CONVENTIONS.md` — branch flow and the interim v2 CI policy.
