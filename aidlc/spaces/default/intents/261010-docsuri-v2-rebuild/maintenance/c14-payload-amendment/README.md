# C00/C14 accepted-work payload amendment — raised work item

Raised 2026-10-16 out of U4 (`u4-research-novelty`) Construction, on the human's
instruction that it be its own piece of work **before** U4's code generation.

Status: **amendment landed 2026-10-16 — remaining acceptance criteria belong to U4's build.**

## Issue

C14's `readExecutionPayload` is typed `AssistanceExecutionPayload` /
`AssistanceAcceptedInput`, and its semantics state: "U1 supports only
PaperAssistance; other owner payload codecs remain INCOMPATIBLE until coordinated
by their unit." No C00/C14 type or operation can carry a ResearchWorkspace
accepted input.

Consequence for U4: an accepted research turn, novelty analysis or novelty
discussion has no contracted way to hand its frozen input to a worker. U4's
accepted-work path therefore cannot be enabled, and the design keeps it
fail-closed rather than accepting work no worker can retrieve.

## Required change

An amendment through the normal revision path for
`inception/contract-design/contract-summary.md`:

1. C00 gains a ResearchWorkspace accepted-input/payload type (or a generalized
   owner payload shape) covering `research-turn`, `novelty-analysis` and
   `novelty-discussion` inputs.
2. C14's `readExecutionPayload` accepts those operation kinds under the same
   claim, fence and input-hash rules that PaperAssistance already uses.

Owner: the contract authority for C00/C14; U4 is the requester. U4 performs
neither the amendment nor a workaround, and PaperAssistance consumers are not
disturbed.

## Acceptance criteria

- [ ] C00/C14 amended and re-versioned; existing PaperAssistance consumers unaffected.
- [ ] U4 registers a durable payload codec for its operation kinds.
- [ ] A mounted `acquireExecutionClaim` → payload-read → `recordCompletion` round trip passes for U4.
- [ ] U4's fail-closed refusal is replaced by the enabled path (plan Step 15 stays unchecked until then).

## Evidence and references

- `aidlc/spaces/default/intents/261010-docsuri-v2-rebuild/construction/u4-research-novelty/infrastructure-design/cicd-pipeline.md` — section "Execution payload enablement" (the fail-closed design and this gate).
- `.../u4-research-novelty/nfr-design/reviews/review-01.md` — Major finding that raised it.
- `.../u4-research-novelty/infrastructure-design/reviews/review-02.md` — R-01 closed by design against this gate.
- `.../u4-research-novelty/code-generation/code-generation-plan.md` — Step 15 (gated, unchecked).

## Resolution (2026-10-16)

The contract half of this item is done.

- **C00** gained `ResearchAcceptedInput` (owner-scoped frozen input: `kind` ∈ {`research-turn`, `novelty-analysis`, `novelty-discussion`}, context/session binding, immutable `inputSnapshot` + `inputHash`, `sourceScope`, `attachmentReferences`, optional `draftRevision`, `processingPolicy`) and `ResearchExecutionPayload` (`binding`, `acceptedAt`, `input`, policy-bound `evidenceScope`, `usageRecordId`).
- **C14** `readExecutionPayload` now releases an owner-scoped payload type — `AssistanceExecutionPayload` for PaperAssistance, `ResearchExecutionPayload` for ResearchWorkspace — keeps every other codec `INCOMPATIBLE` until its own unit coordinates it, and gained a matching invariant (no generic-envelope fallback). The added semantic note that released input/evidence is untrusted data and never authorizes an external action is preserved.
- **Version:** C14 `2.0.0` → `2.1.0`.
- **Validation:** `shared/python/tools/export_workspace_contract.py` regenerated `shared/dtos/workspace.schema.json` and `shared/events/execution.schema.json`; the change is additive only (two new `$defs` plus the union reference — existing PaperAssistance consumers unaffected), and the `--check` drift gate passes.

**Remaining acceptance criteria (U4's build, not this item):** register the durable codec for U4's kinds; prove the mounted `acquireExecutionClaim` → payload-read → `recordCompletion` round trip; replace the fail-closed refusal with the enabled path (plan Step 15 stays unchecked until then).

## How to pick it up

Repository issues are disabled, so this record is the work item; its contract half
is now resolved and merged into the record. The remaining criteria run inside U4's
code generation, so the natural pickup is to resume U4 rather than mint a separate
intent.
