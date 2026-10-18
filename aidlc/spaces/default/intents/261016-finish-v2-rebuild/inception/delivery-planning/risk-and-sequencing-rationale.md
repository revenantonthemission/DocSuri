# Risk and Sequencing Rationale — Finish the DocSuri v2 rebuild

Date: 2026-10-17 (Asia/Seoul)
Workflow: 261016-finish-v2-rebuild. Heuristic: **risk-first** (Boehm's spiral argument) — sequence the highest-uncertainty work early so decisions are calibrated before dependent work commits. No formal WSJF scoring was used (three units, fixed dependency shape, no deadline; the person declined scoring). [Q2]

## Why this order

**B06 (U5) first.** Topics & digests carries the most new behavior: persisted subscriptions, timezone-bound scheduling, consent interplay, delivery with uncertain outcomes, and lifecycle participation. It exercises the embedded-library pattern against the built application for the first time in this workflow, and its real delivery evidence (beyond a local sink) is the riskiest external dependency. Shipping it first surfaces integration and licensing surprises while two units of budget remain. [Q1] [Q6]

**B07 (U6) second.** Approved export is smaller and its hardest prerequisite (U4's immutable artifact revisions) is already merged. Its risk is concentrated in external effects: Notion terms, token protection, exactly-once with reconciliation. Building it after U5 means the assembled-application risk (U8) is tackled with both new modules in hand.

**B08 (U8) last, deliberately.** Assembly risk is real but of a different kind: it spans every service and can only be verified cumulatively. Sequencing it last maximizes what it verifies at once and keeps the honest tail redo (build/CI + seven operation stages over the real operating mode) anchored to a complete application. Verifying units first is the mitigation for assembly surprises, not a replacement for U8's cumulative check. [Q6]

## Deviations from topological order

None: U5 → U6 → U8 respects the DAG (U5 and U6 are mutually independent; the order between them is the economic choice, and U5's larger behavioral surface earns the earlier slot). U5 and U6 could run concurrently in principle; the recorded execution setting is serial with one reviewer, and this plan keeps that honestly. [Q3] [Q4]

## What would trigger replanning

- Notion terms prove unsustainable → U6's export destination approach needs a human scope decision before B07 proceeds.
- Content licensing tightens against digest selection → B06's content window/eligibility rules need a human decision.
- Local capacity limits verification runs → the verification command and fixtures need human re-approval.
- A unit checkpoint fails repeatedly → halt and ask rather than papering over (the failure mode that produced the jumped tail in the closed workflow).

## Confidence chain

Each Bolt's confidence hypothesis (in [bolt-plan.md](bolt-plan.md)) is falsifiable by its expected demo; failure stops at the checkpoint with evidence and options, never silently worked around.
