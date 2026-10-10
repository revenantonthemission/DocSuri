#!/usr/bin/env bash
# Run manually in an external terminal from the DocSuri repository root.
set -euo pipefail

repo_root=$(git rev-parse --show-toplevel)
cd "$repo_root"
patch_file="aidlc/spaces/default/intents/261010-docsuri-v2-rebuild/maintenance/runtime-fix/project.patch"
target_file=".codex/tools/aidlc-orchestrate.ts"
original_hash="c8d7bd195274ce2bfd96d02b00b199c779d4fd6dd2e31534b289a6b37774356f"
corrected_hash="0faff50155adebcac735d594a6d00dbf3c07f4dc7fe2aaa895d4fcb0009e306f"
current_hash=$(shasum -a 256 "$target_file" | cut -d ' ' -f 1)

if [[ "$current_hash" == "$corrected_hash" ]]; then
  printf '%s\n' 'The verified AI-DLC correction is already applied.'
  exit 0
fi
if [[ "$current_hash" != "$original_hash" ]]; then
  printf '%s\n' 'The runtime source differs from the verified baseline; no files changed.' >&2
  exit 1
fi

git apply --check "$patch_file"
git apply "$patch_file"
actual_hash=$(shasum -a 256 "$target_file" | cut -d ' ' -f 1)
if [[ "$actual_hash" != "$corrected_hash" ]]; then
  printf '%s\n' 'The applied source hash differs from the verified correction; inspect the diff before continuing.' >&2
  exit 1
fi
printf '%s\n' 'Applied and hash-verified the AI-DLC conversation identity correction.'
printf '%s\n' 'Use: bun .codex/tools/aidlc.ts engine ...'
printf '%s\n' 'Your recorded approval and workflow state have not been changed.'
