# U1 Implementation-Planning Checks

## Scope and Recovery Decision

The human selected `Abandon and replace checker` in `../construction/u1-job-skeleton/code-generation/code-generation-questions.md` Q7. The faulty supplemental checker is preserved as `verify_u1_code_plan_revision.abandoned.py` in the approved temporary work directory; its replacement at `verify_u1_code_plan_revision.py` separates Markdown prose citations from fenced literal examples. The mandatory Testing Contract is validated independently byte-for-byte, not interpreted as stage-local Markdown links.

Checked documents are `../construction/u1-job-skeleton/code-generation/code-generation-plan.md`, `../construction/u1-job-skeleton/code-generation/unit-test-instructions.md`, `../construction/u1-job-skeleton/code-generation/code-summary.md` and `../construction/u1-job-skeleton/code-generation/recovery-impact.md`, with their source manifest/partial trace and original baseline metadata. Original planning/handoff versions remain in `../archive/2026-10-06T00-01-08Z-u1-code-generation/`.

## Executed Replacement Results

The corrected check was run from the workspace root with `PYTHONDONTWRITEBYTECODE=1`, `UV_OFFLINE=1` and the approved temporary UV cache, through `uv run --no-project` on the replacement script. It writes no application, source, database or lifecycle state.

| Check | Actual result | Meaning |
|---|---|---|
| Prose/code-fence regressions | Three passed | Actual prose links remain checked; copied JSON and tilde-fenced examples are excluded; a missing actual prose reference is still rejected |
| Original archive identities | Four exact Git blob identities match | Preserved original bytes, verified before amendment and checked again |
| Testing Contract | Byte-identical to archived native block; declared hash f87c0507a83e45b42705d96d9cdb5a9124962ca7bb56c2fd06fd2061fcc42153 | Test-after/Standard obligations retained; this is not exact Plan Approval |
| Step sequence/progress | 50 sequential steps; only historical capture Step1 marked complete | No unfinished component/test/realm activity is falsely ticked complete |
| Tables and citations | 11 tables; 45 resolving Markdown references | Current document/reference consistency, including preserved partial-target anchors |
| Commands | 19 exact scoped commands | Current/proposed U1 command inventory has explicit filters/files; proposed absent sources still require implementation/readiness |
| Actual source claims | 29 preserved | Planning does not claim new application writes |
| Partial trace | 184 rows:178 GAP/six Deferred | 124 AC,35 detailed NFR,25 BR; no completed implementation inferred |
| Original capture | 395 files;2,983,766 bytes; unchanged historical002 identity | Immutable source baseline retained, not replaced with HEAD/current changed bytes |
| TEXT/version/admission handoffs | Present | Selected content-only ASCII-v2/TEXT, input-identity separation, reviewed narrow admission, source supplement and qualified-real-realm boundaries |

The prior required-section checks passed for all four documents, with 10/6/7/5 H2 sections respectively. Scoped archive/current whitespace checks passed. The replacement changes only the temporary checker; those document checks are not recast as application tests or real acceptance.

## Evidence Limits and Next Handoff

No application tests/build/install, SQL/database/network/role/broker mutation, source generation or operational acceptance occurred in this check. Infrastructure R-03's concrete lossless storage/real round-trip proof remains pending, and Contract Design R-03 retains its accepted original timestamp-checker limitation. Native quality floors, source/realm/current-authority protections and actual pending artifact/control/notification requirements remain binding.

The Q7 recovery decision is a new recorded answer after the earlier planning-summary confirmation. Refresh the confirmation covering the complete current answers before independent pre-implementation review and current exact Plan Approval; never infer either from a successful supplemental document check.
