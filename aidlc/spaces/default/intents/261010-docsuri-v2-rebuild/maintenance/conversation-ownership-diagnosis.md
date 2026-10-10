# Conversation ownership diagnosis

Date: 2026-10-10 (Asia/Seoul)

## Status

Update, 2026-10-11: the verified correction was applied to the tracked project
runtime from an external terminal, after the protection hook refused agent-side
installation. The corrected source command successfully completed Intent Capture
using the user's existing `Approve` answer. The audit records `GATE_APPROVED`,
`STAGE_COMPLETED` for `intent-capture`, and `STAGE_STARTED` for `feasibility` at
2026-10-10T22:24:00Z (2026-10-11 07:24 Asia/Seoul). The current state is
`feasibility`, `Running`. See [runtime verification](runtime-fix/verification.md).

All three approved document SHA-256 values still match the pre-continuation
snapshot. No additional product or Git-flow approval was requested for this
checkpoint.

`CONVENTIONS.md` is authoritative for Git workflow: working branches merge into `develop` through a GitHub PR; releases promote `develop` to `main`. That decision is persisted in the project rules.

At the original diagnosis checkpoint, the supported intent-switch command
completed, but the subsequent transition still failed. No session-identity
environment override, lifecycle-state edit, guard change, or runtime patch was
applied during that diagnosis. The later external source correction and normal
engine transition are documented separately in the verification report.

## Confirmed source behavior before the repair

The original code was inspected in `.codex/tools/aidlc-orchestrate.ts` and
`.codex/tools/aidlc-lib.ts`. Line numbers below refer to the pre-repair source:

1. The orchestrator resolves its workflow selection and stores the resolved session ID in `engineSessionId` (`aidlc-orchestrate.ts:15574`).
2. `engineChildEnv` copies the process environment and injects `AIDLC_SESSION_OVERRIDE=engineSessionId`, without adding provenance (`aidlc-orchestrate.ts:657`).
3. `spawnState` passes that environment to the state command (`aidlc-orchestrate.ts:12552`).
4. `resolveInvokingSessionId` uses native `CODEX_THREAD_ID` authority only when a valid override is absent. The injected override prevents that branch. Without recognized provenance, a different ancestry identity causes rejection (`aidlc-lib.ts:6518-6552`).
5. `resolveWorkflowSelection` resolves session identity before reading the workflow binding (`aidlc-lib.ts:6604`). Changing the selected intent therefore does not repair this child-environment behavior.

The invoking environment was inspected only for the four relevant variables: `AIDLC_SESSION_OVERRIDE` and `AIDLC_SESSION_OVERRIDE_SOURCE` were absent, `CODEX_THREAD_ID` identified this chat, and `AIDLC_HARNESS_DIR` was absent. The unmarked override is introduced by the child-environment construction in the inspected source.

The installed command reports `aidlc 2.11.0 (runtime 2.11.0)`. The source behavior explains the observed parent-success/child-failure pattern. This diagnosis does not prove byte identity between repository source and the installed compiled runtime.

## Implemented correction

`engineChildEnv` now uses the existing `hookChildEnv` helper only when no valid
inherited override exists, the runtime is Codex, and the native thread ID matches
the resolved session. Existing hook provenance and conflicting bare-override
rejection remain intact. The installed project source hash matches the verified
generated correction.

Focused regression cases for a runtime correction:

- A parent that legitimately resolves native Codex identity passes that identity to a state child even when ancestry identifies another session.
- A parent with validated hook identity preserves that identity in the child.
- A conflicting bare override remains rejected.
- The real `orchestrate report` child path is exercised; testing only the resolver would miss the propagation defect.
- Existing approval evidence and declared artifact fingerprints remain intact across the successful stage transition.

At the original diagnosis checkpoint these were proposed verification cases.
The subsequent implementation and executed checks are in the linked verification report.

## Completed product-document verification

- Claim-source checks passed for `intent-statement.md` and `stakeholder-map.md`, with no findings.
- Required-section checks passed for both documents and `intent-capture-questions.md`.
- Upstream-coverage validation reported no upstream inputs for this stage.
- The independent product review completed with no findings.
- `git diff --check` passed at the document-verification checkpoint.

## Evidence limits

Tier 2 graph verification covered the two source files. Graph generation was `2026-10-10T13:38:00Z`; metadata matched the checked files. The recorded partial-parse range at `aidlc-lib.ts:22782` was read directly and concerns an unrelated directory traversal declaration. Coverage is best effort, not proof of completeness. A separate read-only inspection corroborated the source-level diagnosis.
