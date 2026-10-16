# U4 technology decisions and evidence boundaries

Unit: `u4-research-novelty`. This unit adds an **embedded library contribution**
to the existing application release; it selects no new deployed service and no
new runtime. Every choice below is either inherited-and-to-be-verified or
open-with-an-evidence-gate; nothing here is asserted as already verified.

## Integration baseline (existing, to verify)

- Backend service and persistence: the existing Python/FastAPI assembly with the
  owner-scoped local Postgres realm used by U1/U2/U3; U4 adds records, not a
  second store.
- Browser: the shared `WebWorkspace` shell (Next.js), same-origin transport and
  the existing session boundary; U4 contributes views, not a new app.
- Durable accepted-work delivery: the `C14` dispatch/completion protocol already
  used by U3 (`deliverAccepted`, `recordCompletion`, `acquireExecutionClaim`).
- Provider boundary: the `C12` typed adapter envelope; credentials stay as
  server-side references and never reach the browser.
- Local model runtime: a free/local, cloud-disabled model runtime is required and
  no paid path is permitted, but the specific runtime version and model set are
  **not** confirmed by the upstream artifacts passed to this stage (the
  code-knowledge base's technology-stack record names no such local model). U4
  adds no model of its own; the pin is an open evidence gate (see the candidate
  decisions below).

## Candidate decisions and evidence gates

| Decision | Candidate | Gate before adoption |
|---|---|---|
| PDF/text extraction | Free/local, deterministic extractor over an allowlisted media set | Reproduces on synthetic fixtures: malformed, oversized, truncated, password-protected, unsupported; no partial public publication |
| Grounded generation | Free/local, cloud-disabled model through `C12` `model.generate` | Cite the owning selection that pins the runtime version and model set (and proves cloud is disabled), then verify: abstains or discloses limits on insufficient evidence, unavailable model and context truncation |
| Private artifact storage | Owner-scoped protected storage (provider unselected) | Retention/erasure policy resolved (NFR5.2); no presigned URLs; no public route |
| Optional web reference | On-demand, permission-checked retrieval | Distinguishes read from not-read; unread references never count as evidence |
| Novelty assessment scale | Recorded method scale (`min <= score <= max`) with evidence ids | Never presented as proof of scientific novelty |

## Measurement requirements (before numeric targets)

- Save acknowledgement, reopen and queued-job completion timings, with
  distributions, sample sizes and cold/warm conditions.
- Upload and extraction refusal latency and the effective size/media bounds.
- Restart/reconnect recovery time and duplication rate for accepted turns.
- Artifact read latency at representative and boundary sizes.
- Workload envelope (bytes, queue depth, concurrent jobs) fitting the local
  machine or verified free terms, with the exhaustion behaviour recorded.

Numeric thresholds are agreed with the human after this evidence; none is
asserted here.

## Contract coordination and compatibility

`C07` fixes the operation surface, invariants, checks and the
`ResearchTurnOrDiscussion`, `NoveltyAnalysis` and `DraftRevision` state machines;
`C12` fixes the adapter envelope and error vocabulary; `C14` fixes delivery,
dedup and completion-fact rules. The export source identity
(`artifactId`/`revision`/`contentHash` plus an eligibility revision) is a joint
U4/U6 obligation and must be closed by executable checks, not prose — the
accepted Minor finding remains open until U6 and U8's cumulative check agree.

## Repairability

Setup uses the existing reproducible local realms and synthetic fixtures. A
maintainer must be able to reproduce a research/novelty defect, identify its
boundary, fix it and demonstrate a regression plus affected integration checks,
including the policy-suspended draft path and the tombstone rules.

## Explicitly not selected

- Any paid provider, paid fallback or automatic purchase.
- Presigned URLs or any public route to private content.
- A retention period, erasure boundary or shared-device policy (NFR5.2 keeps the
  durable-draft path refused until these are resolved).
- A second application service, worker topology or model.
