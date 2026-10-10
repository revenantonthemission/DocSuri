# AI-DLC conversation identity repair

This is a local correction to AI-DLC 2.11.0, based on upstream commit
`6a378b53c0a4fe0641ed7d8de8dfff94264d5b6a` (tag `v2.11.0`).

The orchestrator must preserve the provenance of a native Codex conversation
identity when it starts a child command. A manually exported session override
must still be checked against process ancestry. The change does not alter
approval requirements, lifecycle routing, or the identity resolver's policy.

`upstream.patch` contains the authored source correction and regression tests.
`project.patch` applies only the corresponding generated orchestrator change to
`.codex/tools/aidlc-orchestrate.ts`. **The fix has not been installed:** the
active workflow's protection hook refused replacing installed enforcement files.
It explicitly permits intentional maintenance from an external terminal.
See `verification.md` for the executed checks and remaining step.

## Reproduce

Use an isolated checkout, not an existing AI-DLC development checkout:

```sh
git clone --depth 1 --branch v2.11.0 https://github.com/awslabs/aidlc-workflows.git /tmp/docsuri-aidlc-fix
cd /tmp/docsuri-aidlc-fix
git rev-parse HEAD
# Expected: 6a378b53c0a4fe0641ed7d8de8dfff94264d5b6a
git apply --unidiff-zero /path/to/this/directory/upstream.patch
bun install --frozen-lockfile
bun scripts/package.ts
bun test tests/unit/t312-orchestrate-session-binding.test.ts
bun test tests/unit/t318-session-binding-helpers.test.ts
bun run typecheck
bun scripts/build-binaries.ts --target native
bun /path/to/this/directory/native-parity.ts /tmp/docsuri-aidlc-fix
```

The process-ancestry tests need permission to inspect processes (`ps` on macOS).
Run them outside a sandbox that blocks process inspection. Test fixtures use
temporary projects and never mutate the real DocSuri workflow.

## Apply from an external terminal

From the DocSuri root, run:

```sh
bash aidlc/spaces/default/intents/261010-docsuri-v2-rebuild/maintenance/runtime-fix/apply-local-fix.sh
```

The script checks the exact original source hash, checks the patch, applies it,
and verifies the resulting hash. It changes only the tracked orchestrator source.
It does not change guards, workflow records, approval evidence, or the machine's
official runtime. The patch is reversible with `git apply -R project.patch`
from the repository root using the full path to the patch.

## Command after applying the fix

After applying the patch, and until an upstream release includes this correction,
run workflow commands from the repository root using the corrected source runtime:

```sh
bun .codex/tools/aidlc.ts engine orchestrate next --resume
```

Use the same prefix for subsequent commands returned by the workflow, preserving
all arguments. This is AI-DLC's source execution mode and requires Bun. The
machine's official native release remains separately installed. Do not replace
its signed release metadata with locally generated metadata. When updating
AI-DLC, verify this regression against the new release before removing the
local correction and returning workflow commands to the machine launcher.
