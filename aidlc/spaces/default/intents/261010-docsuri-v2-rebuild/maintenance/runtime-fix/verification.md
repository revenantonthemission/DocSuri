# Runtime repair verification

Date: 2026-10-11 (Asia/Seoul)

## Result and remaining step

The correction is implemented and verified in an isolated checkout of the exact
AI-DLC 2.11.0 source commit used by the installed release. It is **not installed
in DocSuri**, and the live rebuild has **not advanced** from Intent Capture.

The active workflow's PreToolUse protection hook rejected copying the corrected
orchestrator into `.codex/tools/aidlc-orchestrate.ts`. Its stated restriction is
that installed enforcement-file maintenance must use the official updater or an
external terminal outside the running agent workflow. No bypass, direct state
edit, session override, or alternative live invocation was attempted afterward.

The newest published official preview checked,
`v2.11.1-preview.20261009.1`, still injects the unmarked session override in
`engineChildEnv` (lines 728–737), so installing that release would not contain
this correction. Source: the upstream GitHub Contents API for
`core/tools/aidlc-orchestrate.ts` at that exact tag.

The external application command is in `README.md`. It applies the reviewable
`project.patch` with original and corrected SHA-256 checks. After application,
use the source runtime to continue through normal lifecycle commands, preserving
the user's existing approval. No new product or Git-flow approval is needed.

## Change

`engineChildEnv` preserves native Codex identity provenance only when the parent
has no valid inherited override, is running the Codex project setup, and the
native thread ID matches the resolved session. Existing payload handling and
the bare-override rejection policy remain intact. This avoids promoting an
unverified override merely because a parent ancestry lookup was unavailable.

## Executed validation

| Check | Result |
| --- | --- |
| Regression suite before source correction | 11 passed, 2 failed; both new native Codex child cases reproduced the reported ownership conflict |
| t312 + t318 after correction | 40 passed, 3 Windows-only skips, 0 failed; 189 assertions |
| `bun run typecheck` after correction | Passed all three TypeScript configurations |
| Focused Biome and `git diff --check` | Passed |
| `bun scripts/package.ts --check` | Deterministic across two independent builds for all seven distributions |
| Native build | Passed all 56 checks, no failures; VERIFIED, full-runtime, darwin-arm64 |
| Compiled parent-to-state-child parity | Native identity reached the intended record; conflicting bare override still rejected; unrelated state and audit bytes unchanged |

The real process-ancestry tests require process-inspection permission. The first
restricted run could not inspect processes; its results were not treated as
verification. The reported results come from runs with that permission.

The compiled parity case uses temporary workflow records and actual child
processes. It proves the compiled handoff, not a successful live DocSuri approval
transition. `build-results-native.json` records the native build evidence.

## Identity and hashes

- Upstream tag: `v2.11.0`
- Upstream commit: `6a378b53c0a4fe0641ed7d8de8dfff94264d5b6a`
- Bun: `1.4.2`
- Original DocSuri orchestrator SHA-256: `c8d7bd195274ce2bfd96d02b00b199c779d4fd6dd2e31534b289a6b37774356f`
- Corrected generated orchestrator SHA-256: `0faff50155adebcac735d594a6d00dbf3c07f4dc7fe2aaa895d4fcb0009e306f`
- Verified local native binary SHA-256: `1908a4527b9ad5ce5bb73d32699a037170e2988becf55ed8a611ed9e45745df6`

The native binary is a local build, not an official release. No release manifest
or attestation was forged or replaced.

## Existing approval and artifact preservation

The audit records the user's exact `Approve` answer for `intent-capture` at
2026-10-10T13:58:16Z. The source repair does not change those documents. Their
SHA-256 values before any live continuation are:

| Document | SHA-256 |
| --- | --- |
| intent-statement.md | `277496dea0a26c35e32f6924fa55067adce3b393d6d92f25f558121a76f415a1` |
| stakeholder-map.md | `d25083c3ea8d4e456188af56aaec14bdc38a8e938feaf4fd48f9f14067ee2e6b` |
| intent-capture-questions.md | `2dd3aae403c27725e1d485c2bfe685db959290fb02fa8d70b39b372a50316f12` |

Git workflow follows `CONVENTIONS.md`: the repair package is prepared on
`fix/aidlc-session-propagation`, created from `develop`; integration uses a PR
into `develop`, with production promotion from `develop` to `main`.
