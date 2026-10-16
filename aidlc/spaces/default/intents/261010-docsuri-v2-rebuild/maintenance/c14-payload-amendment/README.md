# C00/C14 accepted-work payload amendment — raised work item

Raised 2026-10-16 out of U4 (`u4-research-novelty`) Construction, on the human's
instruction that it be its own piece of work **before** U4's code generation.

Status: **open — blocking U4's accepted-work enablement.**

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

## How to pick it up

Repository issues are disabled, so this record is the work item. When the human
chooses, it can be minted as its own AI-DLC intent (`/aidlc` with this scope:
amend C00/C14 for ResearchWorkspace accepted-work payloads, then prove the
mounted round trip) — that intent would own the amendment and the U4 codec
enablement, and U4's plan Step 15 stays unchecked until it lands.
