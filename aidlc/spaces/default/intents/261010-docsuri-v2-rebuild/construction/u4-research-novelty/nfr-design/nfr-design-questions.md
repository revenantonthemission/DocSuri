# DocSuri v2 — U4 NFR Design proposal

Date: 2026-10-16 (Asia/Seoul).
Unit: `u4-research-novelty`.

## Context

This stage designs the patterns behind U4's derived requirements
(`../nfr-requirements/security-requirements.md`, NFR1.1–NFR10.4, review READY
with 0 open findings) inside the C07/C12/C14 contract surface. U4 is a library
contribution: performance, scalability, reliability and observability designs
are owned by the service units that host the same release, so this stage produces
`security-design.md`, `logical-components.md` and `traceability.json`.

Inherited and not re-opened: $0 free/local only, no paid fallback, the Korean
responsive WCAG 2.2 AA workspace, serial construction with autonomous ordinary
completion, and numeric targets left to baseline measurement.

## Proposed design

| Area | Pattern |
|---|---|
| Authority | One server-side owner/context/lifecycle evaluation per operation; private identity never public; non-revealing refusals |
| Accepted work | Immutable input + recoverable dispatch committed atomically; normalized-intent identity for retry/dedup; owner-written ordered sequence; fenced completion facts |
| Drafts | CAS on base revision, immutable acknowledged revisions, exact-revision consumption, restore of unconsumed revisions only, policy-gated durability |
| Attachments | Bounded permit after policy/capacity; byte/hash/media verification before extraction; typed dispositions; no public publication |
| Outbound retrieval | Scheme/host allowlist, private/loopback/link-local and redirect rejection before fetch; unread references excluded from evidence |
| Grounding | Evidence carries source/version/location/coverage/provenance; abstention over invention; score only with method scale and evidence IDs |
| Degradation | Typed limitations for model, capacity and policy triggers; no unbounded work and no paid fallback |
| Observability | Safe correlation identifiers; observed/unknown/stale readiness; private text and credentials excluded |

## Open decisions

1. **Freshness of eligibility checks (proposed).** Recheck eligibility at
   acceptance, at completion and at export read; no cached eligibility is treated
   as current.
2. **Draft policy gate (proposed).** The durable draft path stays closed with a
   policy-unresolved refusal until retention, erasure, storage and shared-device
   policy is resolved; the rest of the unit remains available.
3. **Execution topology (proposed).** A single claim per accepted operation with
   bounded queue and concurrency behind C14; topology selection is deferred to
   Infrastructure Design.
4. **Observation sink (proposed).** Emit privacy-safe signals through the shared
   infrastructure adapters; no new telemetry vendor.

## Consolidated Summary Confirmation

- Design the authority, accepted-work, draft, attachment, retrieval, grounding,
  degradation and observability patterns listed above, without weakening any
  required outcome and without a paid path.
- Keep the durable-draft policy gate explicit and keep private identity off every
  public route.
- Keep the execution topology, object-store boundary and measurement targets open
  for Infrastructure Design and baseline measurement.
- Produce security-design, logical-components and traceability artifacts, then
  obtain independent architecture review before the approval gate.

Does this all look correct before I generate the artifact?

- Looks correct
- Request changes

[Answer]: Looks correct (guide mode — recommended; change it and say so if you disagree before the approval gate)

## Sources

- [NR] `../nfr-requirements/security-requirements.md`, `tech-stack-decisions.md`, `traceability.json`.
- [FD] `../functional-design/functional-spec.md`, `rules.md`, `entities.md`.
- [CT] `../../../inception/contract-design/contract-summary.md` — C07, C12, C14, C13.
- [DC] `../../../inception/domain-design/components.md` — the `ResearchWorkspace` component and its consumers.
