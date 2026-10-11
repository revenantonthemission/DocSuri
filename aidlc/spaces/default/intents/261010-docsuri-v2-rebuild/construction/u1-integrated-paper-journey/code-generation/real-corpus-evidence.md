# Real paper publication and research-query evidence

Date: 2026-10-11. Code Generation Steps 7/8 remain in progress.

## Implemented boundary

The isolated journey database now contains the eligible P1 Transformer and P2
RAG fixtures: 77 and 63 parsed chunks respectively. The publication command
uses the real pinned local BGE model for all 140 chunk vectors and four English
and Korean research-query vectors. It does not generate assistance summaries.
Diagnostic test data remains in the separate diagnostic database; neither
database is reset or adopted from an unrelated service.

The checked metadata fixture records titles, author lists and first-submission
dates from the [P1 abstract](https://arxiv.org/abs/1706.03762) and
[P2 abstract](https://arxiv.org/abs/2005.11401), checked on 2026-10-11. Dates are
2017-06-12 and 2020-05-22, not invented publication dates for the selected HTML
versions. Raw and parsed source custody and local-use limitations remain those
in the parser/source evidence; this does not establish redistribution rights.

Corpus publication binds immutable metadata, source URL/version, content and
projection hashes. A bounded confirmation transaction holds the publication
barrier and current source guards together before recording readiness. Starting
a new attempt clears the current ready marker; a failed attempt cannot leave
an old ready marker masquerading as a new successful publication.

Each protected attempt is a separate bounded evidence file, referenced by digest
from the small current manifest. The manifest admits at most 16 attempts. This
avoids embedding the approximately 129 KiB source inventory in a manifest whose
own read bound is 64 KiB. Existing validated vectors and query vectors replay
without starting a model server or changing the immutable publication.

## Executed commands and outcomes

Commands ran from the repository root against the explicitly owned synthetic
environment. The publisher used the authorized native GPU execution boundary.

```text
backend/.venv/bin/python scripts/publish_docsuri_u1_papers.py
python3 scripts/verify_docsuri_u1.py --phase component --profile synthetic-local --environment-file /tmp/docsuri-u1-run/environment.json
python3 scripts/verify_docsuri_u1.py --phase repository --profile synthetic-local --environment-file /tmp/docsuri-u1-run/environment.json
```

| Attempt | Executed result | Interpretation |
|---|---|---|
| Metadata policy and publication guards | 78 component tests passed in 3.65 s; 25 repository tests passed in 50.91 s | Pure fixture checks plus real PostgreSQL publication behavior |
| Atomic readiness confirmation | 25 repository tests passed in 51.06 s | Current source/hash checks share the publication transaction |
| First real publication | Two papers published in 27.6508696 s; 62 resource samples | Real BGE execution; no Qwen output claim |
| First full research-query suite | 34 passed, 1 failed in 55.29 s | P1 English lexical research query returned no paper; retained failure |
| Corrected ranking component scope | 79 passed in 4.55 s | Includes rejecting a cursor from the previous ranking policy |
| Corrected complete repository scope | 36 passed in 56.45 s; no skips, errors or failures | Real query, filter, paging, no-cross-paper-match and replay checks |

The first lexical failure exposed an implementation defect: all query terms
were required to occur in one chunk, although the relevant paper expressed them
across several chunks. A direct PostgreSQL diagnostic confirmed that the full
P1 version matched the unchanged query and P2 did not. Ranking now evaluates the
complete conjunction over one eligible immutable paper version, with weighted
title text and parameter-bound query input. It does not relax the query into OR
or combine terms across papers. The negative `sinusoidal parametric` case
checks that distinct papers cannot jointly manufacture a match. Cursor and
snapshot compatibility is now `local-search-2-paper-lexical` so paging cannot
silently span the ranking change.

All four actual English/Korean semantic queries rank the intended paper first.
The tests also cover the two English lexical research queries, exact paper and
version lookup, title lookup, real author/year filters, an unknown-author empty
result, and newest-first pagination. The final 15 recorded query observations
had maximum database/query-adapter time 0.052929584 s. These checks use cached
vectors from real BGE execution; this is not a measurement of end-to-end latency
for a newly embedded query, mounted browser interaction, or a broad retrieval
benchmark.

## Protected evidence and limitations

Protected records under `/tmp/docsuri-u1-run/` contain the source inventory,
commands, exact identities and public fixture text; they are not committed.

| Record | Purpose |
|---|---|
| `corpus-publication.json` | Current bounded manifest; first publication was 2,089 bytes |
| `corpus-publication-attempt-1791727211605570000.json` | First real publication, 145,856 bytes; SHA-256 `b8f9ab2fb59717790f60e264da98df993a246b64012c23900587db33b6d42feb` |
| `research-query-evidence-1791727419108077000.json` | Original failed lexical attempt, including 14 query observations |
| `research-query-evidence-1791727663113701000.json` | Corrected 15 query observations |
| `corpus-publication-attempt-1791727663828758000.json` | Third attempt, validated no-model replay; SHA-256 `0c2dee8b35fc34b28c6abb4bc70d8df78ff03b8b98585cc107de77f4f90e9896` |
| `repository-result.json` | Final 36/36 result, source unchanged during execution; source inventory digest `b825a0011de7272584803f25ff5956484691681c4ae28f17f590c2c8ee275149` |

The original publisher closed its owned runtime, but did not persist the exact
server exit status. That status is **unrecorded**, not retrospectively asserted
to be zero. The publisher now records `serverExit` for future executions;
no-model replays correctly retain null with no runtime samples. At this
checkpoint, corpus artifacts total 4,612,596 bytes, including preserved earlier
parser attempts. Model logs, database and other allocations are separate and
remain subject to the existing aggregate operational limits.

This checkpoint proves the bounded real corpus/query boundary. It does not close
assistance output quality, mounted API/browser journeys, cumulative per-module
coverage, public capacity or the later operations fault/recovery obligations.
The assistance readiness marker remains false. No completion checkpoint or
construction verification-command approval is claimed.
