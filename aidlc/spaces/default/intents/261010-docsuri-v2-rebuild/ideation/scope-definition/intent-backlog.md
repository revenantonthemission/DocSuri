# DocSuri v2 — Prioritized intent backlog

Date: 2026-10-11 (Asia/Seoul)

Basis: [scope answers and confirmed summary](scope-definition-questions.md).
Prepared for Scope Definition review alongside the [scope document](scope-document.md).

## Prioritization method and boundary

Use MoSCoW to distinguish the fixed release boundary from deferred expansion.
All current capabilities and the work necessary to meet the confirmed quality,
continuity and $0 constraints are **Must** for this rebuild. New feature
expansion is **Won't for this release**. No discretionary Should/Could feature
is introduced here. Mandatory scope is not demoted merely to populate every
category. [IC] [CR]

Within Must work, follow the user's **risk-first** preference. The order below
is provisional dependency-aware planning, not a measured RICE/WSJF score, a
delivery estimate or permission to reorder the approved lifecycle. Actual
technical dependencies will be verified during discovery. No current capability
may be postponed beyond the first v2 release without a new user scope decision.

These are provisional work packages (proto-Units). They will inform detailed
requirements and implementation units; they do not establish component, service,
repository or team boundaries. One human maintainer supported by coding agents
owns the delivery context. The user decides scope, priorities and unresolved
tradeoffs; agents gather evidence and perform the work.

## Ordered backlog

Dependencies below concern evidence required to complete a package or make its
consequential decisions. They need not prevent independent investigation from
starting. Quality, security, recovery and repairability apply throughout the
implementation, including the first integrated journey.

| ID / order | Package and intended value | MoSCoW | Principal dependencies | Completion evidence |
| --- | --- | --- | --- | --- |
| IB-01 | Establish the full capability and dependency reference so nothing is lost | Must | Approved intent and feasibility evidence | Evidence-linked inventory and initial dependency mapping, including working, failing, disabled and disputed paths |
| IB-02 | Establish environment/data authority and recovery so continuity decisions are informed | Must | IB-01 informs relevant flows/stores; reconcile independently available environment evidence | Aggregate authoritative inventory, ownership, recovery verification and user-visible continuity options |
| IB-03 | Resolve integration and content/data obligations before incompatible choices | Must | IB-01 capability/dependency findings and IB-02 data/environment facts | Current integration/consumer expectations and evidence-backed obligations or explicitly unresolved decisions |
| IB-04 | Measure experience and repairability, then agree numeric targets | Must | IB-01 reference; IB-02 representative environment and safe data access | Reproducible baseline covering all four agreed dimensions, followed by user-agreed acceptance targets |
| IB-05 | Demonstrate a sustainable free/local resource approach and estimate effort | Must | IB-01 workload, IB-02 data/resources, IB-03 eligibility, IB-04 quality evidence | Full-scope resource-fit evidence, verified free terms/limits where used, operating burden and effort estimate with assumptions |
| IB-06 | Establish implementation boundaries and reproducible delivery that one maintainer can repair | Must | IB-01–IB-05 evidence and subsequent approved design/contracts | Understandable ownership, setup and verification paths demonstrated in the implemented service; no stack prescribed here |
| IB-07 | Prove find → understand → save → revisit as an integrated experience | Must | IB-01 relevant requirements, IB-04 targets, IB-05 resource approach and required IB-06 foundations | Whole-journey happy-path and representative failure/interruption evidence, with saved-state continuity through the journey |
| IB-08 | Complete and verify every remaining retained capability | Must | IB-01 full inventory and verified dependencies; IB-04–IB-06; anchor journey proven under the selected order | Every capability assigned, implemented and verified, including less visible, cross-cutting and operational behavior in the reference |
| IB-09 | Verify full release, selected transition, recovery and maintainability | Must | IB-01–IB-08; user-selected continuity policy from IB-02; resolved deployment obligations | Full parity and quality evidence, verified transition/recovery, $0 operation and maintainer instructions; Git release path followed |

## Package completion detail

### IB-01 — Capability and dependency reference

Reconcile user-visible behavior, source, tests and documentation. Each capability
entry needs a stable identifier, user/operator outcome, evidence references,
observed status, relevant data/integrations and dependencies. Distinguish intended
behavior from defects. Do not infer that a broken or disabled path is outside
scope. Record conflicts and obtain the user's disposition where evidence cannot
settle the boundary. This inventory becomes the source for detailed parity
requirements; until it exists, this backlog is not exhaustive at feature level.

Closes only with the evidence required by D-01; addresses R-01 and R-10 and tests
A-01. Discovery itself does not demonstrate implementation parity. [RAID]

### IB-02 — Environment, continuity and recovery

Identify authoritative service endpoints and data ownership rather than treating
development containers or a responding frontend as production proof. Establish
aggregate users, saved-data categories, ownership relationships and relevant
backups without placing private contents in planning artifacts. Verify recovery
in an appropriate isolated environment before claiming restorability. Present
continuity alternatives and their consequences for the user's decision. No
destructive migration or fresh-data choice follows automatically from this item.

Evidence addresses D-02, I-01–I-03, R-02–R-03 and A-02. A failed restore or missing
authority evidence remains open with its consequence recorded. [FA] [RAID]

### IB-03 — Integrations and obligations

Map actual integration dependencies, existing consumers and compatibility
expectations. Investigate content provenance/permissions, data handled and the
privacy, licensing, institutional and location facts relevant to hosting and
data handling. Keep verified requirements separate from hypotheses. Record
unresolved issues and the choices they prevent; absence of a known agreement
does not prove absence of obligations. Do not assert a legal conclusion merely
from repository configuration.

Evidence addresses D-03, O-02, O-04 and R-04/R-09. Material issues must be resolved
before affected integration, hosting or data-handling decisions. [CR] [RAID]

### IB-04 — Baseline and acceptance targets

Record environment, method, representative inputs, failure conditions and results
for complete-task success, responsiveness, interruption recovery and defect
reproduction/repair. Include the anchor journey's transitions and retain a path
to measuring other capabilities. Record unavailable measurements as unavailable,
not zero or passing. A development-only measurement must be labeled with its
limits until its representativeness is established. Agree numeric targets with
the user after measurement; no target values are invented in this backlog.

Evidence addresses D-04, I-04 and R-03/R-07/R-08. Documented numeric targets alone
do not demonstrate that the rebuilt service meets them. [IC] [FA] [RAID]

### IB-05 — Free/local feasibility and sustainable workload

Measure available local capacity and the demand of all retained capabilities
against the agreed quality targets. For any free service considered, verify
current terms, relevant quotas, expiry and billing behavior. Include storage,
backup, model/data/API needs and maintenance/recovery effort where applicable.
No paid fallback, new subscription, hardware purchase or automatic overage is
part of the plan. Existing resource assumptions remain explicit.

Compare eligible approaches against stability, repairability and one-maintainer
burden. Produce an effort estimate after discovery, with uncertainty and human
availability identified. If no measured option fits full parity and quality,
present the conflict for the user's decision; do not declare feasibility by
cutting features or lowering targets. This item informs later stack and resource
selection rather than selecting them now.

Evidence addresses D-05, O-01/O-06/O-07, I-04, R-05/R-06 and A-03/A-04. Free/local
labels alone are insufficient evidence of fit. [FA] [CR] [RAID]

### IB-06 — Comprehensible, repairable implementation

Implement the boundaries, responsibilities and contracts established in later
approved design work. A maintainer must be able to find the behavior relevant to
a defect, reproduce it, understand dependencies and verify a repair. Provide
reproducible setup, configuration guidance and appropriate automated checks.
Record why each retained boundary exists; tidy directories alone do not satisfy
repairability. Build foundations in increments needed by the retained outcomes,
with quality and recovery behavior present from the first integrated slice.

Validate this package through IB-07–IB-09 rather than declaring it done from a
directory tree or architecture diagram. It addresses C-04/C-07 and R-08. [CR]

### IB-07 — Integrated anchor journey

Using the established reference and approved requirements, prove that a
researcher or engineer can find a relevant paper, understand it through the
retained product capabilities, save it and return to it later. Verify transitions
and relevant persisted state, including representative interruptions and failure
recovery. Apply the agreed responsiveness and task-success criteria. Scope the
specific cases from inventory; do not add an unconfirmed new research feature.

This is the first complete product demonstration. Its success does not close
IB-08 or authorize release without IB-09. It addresses C-03–C-05 and R-07. [IC]

### IB-08 — Remaining capability parity

Map every IB-01 capability to a detailed requirement, implementation unit and
verification outcome as those artifacts are created. Capabilities already proven
in IB-07 remain in the same map with their evidence; they are not counted twice.
Implement and verify the remaining outcomes, compatibility and required
cross-cutting behavior in dependency order. Known failures in the reference must
have an explicit intended-behavior disposition instead of being reproduced or
silently removed. Any unresolved mapping or missing result prevents a claim of
complete parity.

This package will split into concrete units after discovery and design. No
placeholder “remaining work” row may substitute for the complete mapping at
release. It addresses C-01/C-02 and R-01/R-09/R-10. [FA] [CR]

### IB-09 — Release, continuity and operational proof

Verify the chosen continuity/transition policy against the authoritative data
inventory and recovery evidence. Verify every retained capability and agreed
quality criterion in the intended environment, including behavior under the
relevant local/free resource limits. Demonstrate setup, diagnosis, a representative
defect repair and recovery using the instructions intended for the maintainer.
Carry unresolved failures to the user with their consequences; a green build or
frontend-only check does not prove service acceptance.

Use working branches and PRs into develop, then promote develop to main for a
verified release under CONVENTIONS.md. A scope approval does not perform that
promotion. Completion requires the full outcome above and the approved lifecycle's
remaining verification and release steps. [FA] [CR]

## Evidence coverage and release accounting

| Upstream evidence item | Primary package(s) carrying it forward |
| --- | --- |
| D-01 / R-01 / A-01: capability completeness | IB-01, IB-08, IB-09 |
| D-02 / I-01–I-03 / A-02 / R-02–R-03: environment, continuity, recovery | IB-02, IB-04, IB-09 |
| D-03 / O-02 / O-04 / R-04 / R-09: integrations and obligations | IB-03, IB-08, IB-09 |
| D-04 / R-07–R-08: baseline and repairability | IB-04, IB-06, IB-07, IB-09 |
| D-05 / O-01 / O-06–O-07 / A-03–A-04 / R-05–R-06: resources and workload | IB-05, IB-06, IB-09 |
| O-03 / O-05: users/data and authoritative environment | IB-02 |
| I-04: missing measurements, estimates and resource-fit proof | IB-04, IB-05 |
| R-10: historical notes mistaken for current facts | IB-01–IB-03, IB-08 |

The [scope document's constraint table](scope-document.md#constraint-coverage-and-ownership)
maps C-01–C-13 to this backlog. These are work assignments, not closure claims.
Keep the upstream identifiers when evidence arrives and close an item only when
its specified evidence exists. No adoption, data count, throughput, cost saving,
work duration or deadline is assumed.

## Assumptions & Open Questions

The capability inventory, detailed dependency graph, final implementation-unit
decomposition, baseline and targets, continuity policy, resource fit, relevant
obligations and delivery schedule remain open. Their investigation is part of
this backlog, not permission to choose default answers. All work packages are
uncompleted; this document provides no implementation or service-test results.

## Sources

- [IC] [Approved intent statement](../intent-capture/intent-statement.md).
- [FA] [Approved feasibility assessment](../feasibility/feasibility-assessment.md).
- [CR] [Constraint register](../feasibility/constraint-register.md).
- [RAID] [Feasibility RAID log](../feasibility/raid-log.md).
- [SQ] [Scope questions and confirmation](scope-definition-questions.md).
- [Git conventions](../../../../../../../CONVENTIONS.md).
