# DocSuri v2 — U4 Infrastructure Design proposal

Date: 2026-10-16 (Asia/Seoul).
Unit: `u4-research-novelty`.

## Context

This stage realises U4's confirmed NFR decisions as a delivery pipeline and
environment flow. U4 is a library contribution inside the existing release, so
the infrastructure artifact set for this unit is the CI/CD and operations design
plus traceability; hosting, capacity and provider selection remain unselected.

Inherited and not re-opened: $0 free/local only, the interim `develop`
integration policy in CONVENTIONS.md, and numeric targets left to baseline
measurement.

One carried finding shapes this design: the NFR Design review found that C14's
`readExecutionPayload` returns `INCOMPATIBLE` for owners other than
PaperAssistance, so U4's accepted-work path has no contracted payload source. This
stage closes it by design — U4 registers its own durable payload codec and proves
a mounted claim → payload-read → completion round trip before the path is enabled;
until then acceptance refuses with the explicit incompatibility outcome.

## Proposed design

| Area | Design |
|---|---|
| Pipeline stages | Source, lint/typecheck, unit, database, repository, integration, operations, frontend, contract conformance, privacy/policy gates, coverage, evidence bundle — each fails closed, refusals never become skips |
| Environment flow | One release hosting the embedded contribution and bounded local runtime; short-lived branch → PR → `develop`; synthetic, disposable environments; no private content reuse |
| Payload enablement | Per-kind durable codec proven by a mounted round trip; the path stays disabled (explicit refusal) until proven |
| Migration/expiry/rollback | Compatible ordered migrations; bounded idempotent expiry sweep; immutable revisions and tombstones never rewritten; restore replays current tombstones |
| $0 guardrails | Finite bounded limits with recorded values; no paid provider; loud failure rather than overage; outbound-target validation exercised everywhere |
| Secrets/protected material | Secret-free PR jobs; no private text or credentials in evidence; synthetic fixtures only |
| Evidence and recovery | Per-phase evidence bundle with hashes and counts; reproducible setup/repair path; evidence preserved before teardown |

## Open decisions

1. **Draft-path enablement (proposed).** Stay policy-gated: the pipeline expects a
   policy-unresolved refusal and must not convert it into a green skip.
2. **Expiry sweep cadence and retention window (proposed).** Configuration with a
   recorded value, agreed after baseline measurement.
3. **Execution topology (proposed).** Not selected here; the pipeline verifies the
   contract surface and leaves worker topology to Code Generation.

## Consolidated Summary Confirmation

- Design the pipeline, environment flow, payload enablement, migration/expiry/
  rollback, $0 guardrails, secret handling and evidence operations listed above.
- Keep the execution payload gap closed by proof, not by prose: no enablement
  before the mounted round trip passes.
- Keep provider/topology selection and numeric targets open for the appropriate
  later decision, with no paid path anywhere.
- Produce the pipeline design and traceability, then obtain independent
  architecture review before the approval gate.

Does this all look correct before I generate the artifact?

- Looks correct
- Request changes

[Answer]: Looks correct (guide mode — recommended; change it and say so if you disagree before the approval gate)

## Sources

- [ND] `../nfr-design/security-design.md`, `logical-components.md` — including the bridge to this stage.
- [NR] `../nfr-requirements/security-requirements.md`, `tech-stack-decisions.md`.
- [CT] `../../../inception/contract-design/contract-summary.md` — C07, C12, C14, C13.
- [CV] CONVENTIONS.md — branch flow and the interim v2 CI policy.
