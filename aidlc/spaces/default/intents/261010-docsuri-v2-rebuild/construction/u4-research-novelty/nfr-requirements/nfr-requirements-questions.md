# DocSuri v2 — U4 NFR Requirements proposal

Date: 2026-10-16 (Asia/Seoul).
Unit: `u4-research-novelty`.

## Context and carried-forward decisions

This stage follows U4's completed Functional Design (review verdict READY,
with two Major and four Minor consistency findings carried in
`../functional-design/reviews/review-01.md`) on the working branch
`feature/u4-research-novelty` created from `develop` (`72aeba5d`, which already
contains U1, U2, U3 and U7).

The unit is a **library** contribution to the existing application release, so
the service-scoped NFR categories do not produce separate artifacts here; this
stage produces `security-requirements.md`, `tech-stack-decisions.md` and
`traceability.json` over the inception NFR set.

Inherited and not re-opened: $0 free/local only, Korean responsive workspace with
the WCAG 2.2 AA target, serial construction with autonomous ordinary completion,
and the numeric targets left to baseline measurement. Contract `C07` fixes the
operation surface and state machines; `C12` fixes the provider adapter envelope;
`C14` fixes durable accepted-work delivery.

Upstream obligations this stage must keep honest:

- **Durable-draft policy suspension (NFR5).** Durable draft persistence, restore,
  discard and consumption stay refused with a policy-unresolved outcome until
  retention, erasure, storage and shared-device policy is resolved.
- **Export source-revision identity (FR16).** The immutable
  `artifactId`/`revision`/`contentHash` tuple and its eligibility recheck are
  U4's side of the contract U6 consumes.

## Proposed derived requirements

Every corrected requirement inherits its inception NFR id with a sub-number
(`NFRx.y`). The proposal covers all ten inception NFRs as applicable to this
unit; each row is written out in `security-requirements.md`.

| Inception NFR | Derived focus for U4 |
|---|---|
| NFR1 | Grounding/abstention on controlled fixtures; exact-revision consumption; cross-owner denial |
| NFR2 | Save/reopen feedback; ordered progress never ahead of commit; no duplicate submission |
| NFR3 | Restart/reconnect recovery; immutable input; newer-edit survival; tombstone dominance; one race outcome |
| NFR4 | Owner+context enforcement; private identity never public; untrusted content gains nothing; revoked sessions refused |
| NFR5 | Classification and obligations; draft-policy suspension; deletion covering caches/derived/queued work |
| NFR6 | Keyboard/AT operation with announced status; confirmed destructive actions |
| NFR7 | Reproducible fixtures and diagnosis for research/novelty paths |
| NFR8 | Bounded uploads/queues/retries/concurrency; no paid fallback |
| NFR9 | Privacy-safe failure linkage; observed/unknown/stale distinction |
| NFR10 | C07/C12/C14 parity; agreed export identity; test doubles held to the same contract |

## Open decisions

1. **Extraction and PDF handling (proposed).** Free/local, deterministic,
   allowlisted to text and PDF first; verified bytes before extraction; typed
   refusals for malformed, oversized, truncated, password-protected or
   unsupported input. The specific library remains unselected pending evidence.
2. **Grounded-output model use (proposed).** Reuse the pinned local runtime
   already used by U3 (qwen3:8b + bge-m3, cloud disabled); no new model and no
   paid fallback. The unit must abstain or disclose limits when the model is
   unavailable.
3. **Private artifact storage (proposed).** Keep the unselected object-store
   boundary; owner-scoped, no presigned URLs, no public publication. Retention
   and erasure remain tied to the NFR5 policy suspension.
4. **Numeric targets (proposed).** Left to baseline measurement. No latency,
   throughput or recovery-time number is asserted by this design.

## Consolidated Summary Confirmation

- Record the derived NFRx.y requirements for all ten inception NFRs against U4's
  private research and novelty behaviour, without weakening any required outcome
  (owner isolation, truthful status, intentional abstention, zero planned spending).
- Keep the durable-draft policy suspension explicit: no durability, shared-device
  isolation or erasure-completeness claim before the policy is resolved.
- Keep the pinned free/local model and extraction choices, with no paid fallback
  and honest limitation behaviour when they are unavailable.
- Leave numeric performance, capacity and recovery targets to baseline
  measurement; name what must be measured before they can be agreed.
- Produce security, tech-stack and traceability artifacts, then obtain
  independent architecture review before the approval gate.

Does this all look correct before I generate the artifact?

- Looks correct
- Request changes

[Answer]: Looks correct (guide mode — recommended; change it and say so if you disagree before the approval gate)

## Sources

- [FD] `../functional-design/` — `functional-spec.md`, `rules.md`, `entities.md`, `traceability.json`.
- [RQ] `../../../inception/requirements-analysis/requirements.md` — NFR1–NFR10 and the public-paper acceptance tasks.
- [CT] `../../../inception/contract-design/contract-summary.md` — C07, C12, C14 and the C13 browser binding.
- [KB] `aidlc/spaces/default/codekb/DocSuri/technology-stack.md` — the current stack evidence.
- [Git] CONVENTIONS.md and the branch state after PR #50 merged U2/U3 into `develop`.
