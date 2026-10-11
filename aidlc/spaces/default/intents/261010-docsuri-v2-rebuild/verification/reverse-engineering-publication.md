# Reverse Engineering Publication Evidence

Date: 2026-10-11. Repository: DocSuri. Branch: `fix/aidlc-session-propagation`.

## Scope and source checks

The human selected **Full rescan** and confirmed the persisted Reverse Engineering summary. The developer produced all nine analysis documents and the durable [scan handoff](../inception/reverse-engineering/developer-scan.md). Application source was not edited.

The original pre-scan snapshot over `./` recorded:

- Source: `tree:124698c6a40fb40a7d02c22629b15fd4dec2a0d64a206d6a72e063887e9589ae`
- Prior shared store: `sha256:282ece22311d81519369fd94abd66f8d188c29072cdf9b588c1358eb1c934ab8`

Canonical validation accepted the new timestamp as partial coverage: 57 deep paths, 13 analyzed component boundaries and 7 shallow paths. All component names and deep path lists agree across the timestamp, component inventory and handoff. The old store had no machine-readable scope block: the comparison returned `UNKNOWN_SCOPE (absent)`, so no claim about preservation of earlier verified coverage can be established from it.

The scope fingerprint mint returned literal `unknown`, including simple-path probes. Its cause remains undetermined. No handwritten hash or guard override was used; guarded publication accepted the candidate against the exact original source and store snapshot.

## Transactional publication

Both publications used `bun .codex/tools/aidlc.ts engine workspace codekb-publish --repo DocSuri`, staged directory `<record>/.aidlc-engine/codekb-stage-DocSuri/`, and `--paths ./`. The source expectation remained the original source hash above.

| Publication | Expected store | Published generation | Result |
|---|---|---|---|
| Full rescan | `sha256:282ece22311d81519369fd94abd66f8d188c29072cdf9b588c1358eb1c934ab8` | `sha256:93c49d7cf938198672b0a2c453f8f24e9c8eb7e16ed64187740770e66f7feec1` | Exit 0; all nine files published; staged directory removed by tool |
| EOF normalization | `sha256:93c49d7cf938198672b0a2c453f8f24e9c8eb7e16ed64187740770e66f7feec1` | `sha256:dbbf631d82b7301c50a32365e066f0a8212398f0244e9042b3e0d5f68a3a33fd` | Exit 0; all nine files published; staged directory removed by tool |

The first publication exposed one extra blank EOF line in each document through `git diff --check`. A fresh snapshot confirmed the same source hash. The developer copied the published set into staging and removed exactly one trailing newline byte per file, with all other bytes unchanged. The second scope comparison returned `COVERS`; this compares the formatting repair with the newly published scan, not with the historical untracked scope. The tool consumed both temporary scope drafts.

Final location: `aidlc/spaces/default/codekb/DocSuri/`. Exactly nine expected, nonempty Markdown artifacts were verified. No direct writes bypassed publication.

## Validation and limits

- Published CodeKB `git diff --check`: passed. The later staged check includes one harmless blank-EOF warning in the developer handoff. An attempted formatting-only change was rolled back byte-for-byte because its pipeline receipt had already frozen that file; the original receipt remains authoritative. No application or document-content defect is suppressed by this exception.
- Required developer handoff headings: present.
- Document checks: links, paths, table counts, coverage agreement, balanced fences and three manually checked Mermaid diagrams with text fallbacks.
- API inventory: 108 application HTTP declarations and 4 separate platform-integrity declarations; declaration inventory does not establish live availability.
- One existing isolated SSE regression was executed and failed; the preceding module-local attempt failed collection. Exact commands, environment and output are in [test evidence](reverse-engineering-test-evidence.md).
- No full application suite, browser journey, build, live service or deployment validation. The scan retains explicit shallow/excluded coverage, user/data/backup uncertainty and free/local capacity questions.

Git integration continues to follow `CONVENTIONS.md`: working branch → PR into `develop` → release promotion to `main`.
