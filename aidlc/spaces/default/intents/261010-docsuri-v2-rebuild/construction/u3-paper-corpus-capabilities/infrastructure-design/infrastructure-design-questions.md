# U3 Infrastructure Design — proposal and confirmation

Date: 2026-10-15 (Asia/Seoul). Unit: `u3-paper-corpus-capabilities`, an embedded library with browser contributions inside the shared application. This is a proposal for the infrastructure/pipeline design pass, not the generated design or a deployment approval.

## Sources

| ID | Source | Consequence for this pass |
|---|---|---|
| ND | [Security design](../nfr-design/security-design.md) and [logical components](../nfr-design/logical-components.md) | The component inventory, failure domains and shared resources (PostgreSQL transactions, worker capacity, model runtime, telemetry adapter) define what the pipeline and operations must build, verify and recover. |
| NR | [Security requirements](../nfr-requirements/security-requirements.md) and [technology decisions](../nfr-requirements/tech-stack-decisions.md) | Evidence gates, measurement procedure, finite limits and $0 constraints constrain pipeline stages, resource configuration and secrets handling. |
| REVIEWS | Carried review findings | Functional design (participation row, traceability completeness, section floors, references, restore path, vocabulary), NFR requirements (glossary coverage, technology-inventory reference), NFR design (upstream citations, dangling target, count) remain closure tasks for their stages; the pipeline must verify rather than mask them. |
| FD | [Functional specification](../functional-design/functional-spec.md) | Workflows and state machines define the operations the pipeline phases must exercise (runs/publication, search, assistance, glossary). |
| CONTRACT | [Canonical contracts](../../../inception/contract-design/contract-summary.md) | C04–C06/C13/C14 pin the boundaries whose real mounted checks the pipeline must run; migration/publication rollback follows their CAS/quarantine discipline. |
| UNIT | [Unit catalogue](../../../inception/units-generation/unit-of-work.md) and [requirement assignment map](../../../inception/units-generation/unit-of-work-story-map.md) | U3 is an embedded contribution in one application release; U8 owns the complete assembly and cumulative verification. |
| BASE | Existing U1/U2 assembly and runners | The shared host, PostgreSQL owner transactions, worker control loop and the scoped bridge/test runners are the integration baseline to extend (no new service, broker or store by assumption). |
| HUMAN | Confirmed constraints | $0 free/local only; one human maintainer with agents; no public deployment or paid fallback; releases follow CONVENTIONS.md (working branch → PR into develop; main promotion separate). |
| GIT | [CONVENTIONS.md](../../../../../../../../CONVENTIONS.md) | Branch/PR/merge conventions and the interim CI policy for this rebuild. |

## Resolved decisions and ambiguity analysis

- No new human question is needed: the deployment model (one local application release, embedded contributions, no public hosting), the $0 budget, the serial construction flow and the existing runner pattern already settle the infrastructure questions. This summary is the remaining human decision before generation.
- No cloud service, hosted pipeline, paid runner or public environment is selected or required by this design; where an eventual public operation would need one, that decision remains behind its evidence gates and out of scope here.
- Numeric resource values (pool sizes, queue depths, retention) remain measurement-first; the pipeline design defines where they are configured, validated and evidenced, not their values.
- The pipeline must surface the carried review findings through its gates (traceability/section/upstream checks) rather than letting green tests mask them.

## Proposed design coverage

| Area | Design decisions to record |
|---|---|
| Delivery pipeline for U3's work | Scoped stages extending the existing runner pattern: lint/typecheck; U3 component tests; database, repository, integration and operations phases through the real shared host/stores; frontend unit and browser checks for the U3 surfaces; coverage; schema/contract conformance checks (C04–C06/C13/C14). Frozen inputs, content hashes, read-only permissions, no secrets on untrusted PRs. |
| Environment and release flow | One local application release with the worker and optional model runtime; per CONVENTIONS.md a working branch integrates through a PR into develop under the interim CI policy, and main promotion stays separate and human-gated. No public deployment is performed by this design. |
| Migration, publication and rollback | Ordered, compatible migrations with stop-migrate-start verification; projection publication uses the existing CAS/quarantine discipline so rollback never serves a partial generation; withdrawal boundaries are replayed by any restore before serving. Rollback and restore steps are documented with their evidence expectations. |
| Resource configuration and $0 guardrails | Where finite pool/queue/retry/page/traversal/model-concurrency limits and disk watermarks are configured and validated; measurement procedure wiring so numeric targets follow baseline evidence; clear refusal when capacity or permission evidence is missing. |
| Secrets and protected material | No credentials or provider secrets in repositories, images, CI logs or client code; untrusted PR jobs receive none; protected fixture material lives in mode-restricted local paths and is redacted from evidence artifacts. |
| Evidence and recovery operations | How phase evidence (commands, exit codes, counts, hashes, fault schedules) is captured and retained per the measurement procedure; how a maintainer reproduces and repairs a representative failure through the runner; how failed/unknown responsibility evidence is preserved before any teardown. |

`infrastructure-specification.md` and `monitoring-design.md` are not produced for this library kind (no separately deployed service); their obligations are carried inside the logical-components view, the security design and this pipeline design.

## Artifact plan

1. `cicd-pipeline.md`: the staged pipeline (stage → gate mapping), environment/release flow, migration/publication/rollback procedures, resource-configuration and secrets handling, and evidence/recovery operations — each mapping to the NFR design decisions it realizes.
2. `traceability.json`: every infrastructure-relevant `NFRx.y` design decision mapped to its concrete pipeline/configuration or procedure, with no unexplained gaps.

Validate references and unresolved prerequisites, then obtain the required independent architecture review. No deployment, migration or public operation follows merely from this document generation.

## Assumptions & Open Questions

No new product assumption is adopted. Open evidence gates remain: source permissions, model readiness, citation-provider terms, finite capacity policy and quantitative targets after baseline. Their absence appears as designed refusal/degradation, never as pipeline success. The carried review findings stay with their owning stages.

## Consolidated Summary Confirmation

- Define U3's delivery pipeline as scoped stages extending the existing runner pattern: lint/typecheck, U3 component tests, database/repository/integration/operations phases through the real shared host, frontend unit and browser checks, coverage, and C04–C06/C13/C14 contract conformance — with frozen inputs, content hashes, read-only permissions and no secrets on untrusted PRs.
- Record the environment and release flow: one local application release with worker and optional model runtime; working branch → PR into develop under CONVENTIONS.md; main promotion separate and human-gated; no public deployment performed by this design.
- Define migration/publication/rollback procedures: ordered compatible migrations with stop-migrate-start verification; CAS/quarantine publication discipline so rollback never serves partial generations; restore replays current withdrawal boundaries before serving.
- Define resource-configuration and $0 guardrails: where finite limits and disk watermarks are configured and validated; measurement wiring for baseline-first targets; explicit refusal when capacity or permission evidence is missing.
- Define secrets and protected-material handling: nothing in repositories, images, CI logs or client code; untrusted PR jobs receive no secrets; protected fixtures are mode-restricted and redacted from evidence.
- Define evidence and recovery operations: how phase evidence and fault schedules are captured; how a maintainer reproduces and repairs a representative failure; how failed/unknown responsibility evidence is preserved before teardown.
- Surface the carried review findings through the pipeline's own gates rather than letting green tests mask them, and keep every evidence gate explicit.
- Produce the pipeline design and traceability; validate them and obtain independent review. Continue serially with automatic ordinary completion and the existing human decision points.

Does this all look correct before I generate the artifact?

- Looks correct
- Request changes

[Answer]: Looks correct
