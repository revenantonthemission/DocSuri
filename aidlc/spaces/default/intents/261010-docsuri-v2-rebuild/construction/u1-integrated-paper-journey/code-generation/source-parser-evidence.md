# Bounded source parsing and private research fixtures

Date: 2026-10-11. Step 7/8 component work; real-model and mounted acceptance
remain pending.

The CorpusContent adapter reuses the retained ingestion DocModel parser. It
preserves literal inline/display LaTeX, nested section/block identity and figure
captions while removing active HTML elements. It rejects oversized bytes,
excessive structure, empty content and projection overflow instead of silently
truncating evidence. Figure references do not claim that pixels were fetched.

The private loader fetches only the two approved versioned research fixtures,
with a 2 MiB source bound, no redirects, proxy inheritance or public publication.
The protected manifest is `/tmp/docsuri-u1-run/paper-fixtures.json`; it binds the
run, exact paper/version/title/source URL and raw/parsed artifact hashes. Reuse
verifies these artifacts. Parser/dependency changes reparse the original checked
raw bytes and preserve the previous manifest and immutable artifacts. Current
parser identity is `4cdf041f793ba4f54bd26c2e8bbc4e4e4ab6716fdece6eaaa02d954ab1246549`.

| Fixture | Version | Parsed chunks | Raw source SHA-256 |
|---|---:|---:|---|
| Attention Is All You Need | 7 | 77 | fe1288e9c6f8322156429ab44bf5ced203155f8ecc7ea9fe6cfd125872c72a3b |
| Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks | 4 | 63 | 7f643ebcf14fa024288da5e7d79c834246101f8ff8d1258994b690fc79aeb892 |

Both hashes match the earlier infrastructure observations. This proves the
current source parse, not normal assistance quality or public redistribution
rights. Current parser headings omit the source's separate numeric heading
tags; stable block IDs and full title paths must be used faithfully, without
inventing printed section numbers from parser-generated IDs.

Independent source comparison found that the initial 74/61-chunk parse omitted
caption-bearing SVG-object figures, including P2 Figure 1. The retained parser
required an `img` before accepting a figure; sanitizing the active object exposed
that assumption. The existing parser owner now retains caption-bearing figures
with blank source hints, preserving ordinal alignment for the existing asset
resolver's fallback or an unavailable image. P2 Introduction/s1.fig1 now retains
the retriever/generator, top-K and marginalization caption. All earlier private
manifests/artifacts remain intact. No model run used the incomplete parse.

The shared parser version advances from @7 to @8 because figure ordinals and
full text change. The existing builder cache contract compares this version;
U1 also binds the shared constant's bytes in its parser fingerprint. No existing
service cache was migrated or rebuilt by these checks.

Before the parser change, its existing suite passed 24 tests in 0.12 seconds.
The new caption regression fails against the exact `git show HEAD` pre-change
parser saved in `/tmp/docsuri-u1-parser-before-figure-fix.py` (only the later
image remains, with ordinal zero), and passes against corrected source. An
initial isolated import attempt hit a package circular import; importing the
package before substituting the old parser resolved that harness-only issue.
The authored new assertion initially failed to unwrap the generated block DTO;
it was corrected before using the regression as evidence. The unchanged asset
extraction and builder suites passed 36 tests against old parser bytes, then
all three affected suites passed **61 tests**, no skips, in 0.25 seconds after
the parser fix/version bump. This includes real PDF/asset resolution machinery
and existing stale-parser-cache rebuild checks.

The shared bump also reaches existing PaperAssistance cache keys and source
freshness. Its affected `test_domain_source_cache_length.py`,
`test_orchestrator.py`, `test_docmodel_endpoint.py` and
`test_docmodel_build_trigger.py` suites passed with the backend locked Python
environment and no failure/skip indicators. Existing consumers import the shared
constant; no separate literal @7 consumer remained in the checked backend,
frontend, ingestion or shared source trees.

The backend adds only beautifulsoup4 4.15.0, lxml 6.1.3, defusedxml 0.7.1 and
transitive soupsieve 3.0.1; no existing locked package version changes/removals.
Installed metadata reports MIT, BSD-3-Clause, PSFL and MIT respectively. An
initial uninstalled full ingestion dependency proposal changed unrelated
OpenSearch versions and was replaced by this bounded parser binding. The U1
pytest and fixture command use an explicit ingestion source path; future host
and worker packaging must carry that same binding.

The backend environment grew from 202,396 to 222,848 KiB. Repeat setup measures
existing backend environment, frontend dependencies and built assets against
the original 2 GiB build allocation. It reserves only the remaining allocation,
preserving the 8 GiB host floor and 1 GiB each for runtime and recovery. Missing
build paths provide zero credit; `du` is never invoked without explicit paths.
Symlinks and measured build usage over 2 GiB are refused. Fresh setup still
requires all 12 GiB of free headroom.

The final serial component phase passed **45 tests**, zero skips/errors/failures, in
2.91 seconds. New checks cover literal equations, section stability, active
element removal, figure metadata, parsing/projection limits, manifest scope and
source substitution, parser/dependency binding, and repeat setup boundaries.
An earlier run had 38 passes and one fixture error: the authored figure lacked
the retained parser's required `ltx_caption` class. Correcting that diagnostic
fixture produced a passing run; parser behavior was not weakened. Scoped Ruff
checks passed after import ordering. Per-module final coverage is still pending.

```bash
uv --no-cache sync --project backend --locked --group dev
python3 scripts/verify_docsuri_u1.py --phase setup --profile synthetic-local --environment-file /tmp/docsuri-u1-run/environment.json
backend/.venv/bin/python scripts/load_docsuri_u1_papers.py
python3 scripts/verify_docsuri_u1.py --phase component --profile synthetic-local --environment-file /tmp/docsuri-u1-run/environment.json
```

Tier 2 graph coverage at generation 2026-10-11T12:37:43Z reported current metadata
and no recorded issue for the changed Python sources. The pytest configuration
was read directly, including its reported partial lines 7–13. Lock metadata is
untracked by the graph; direct structured lock comparison established the four
additions and absence of changed/removed existing versions. These are bounded
evidence, not a claim of exhaustive graph coverage.
