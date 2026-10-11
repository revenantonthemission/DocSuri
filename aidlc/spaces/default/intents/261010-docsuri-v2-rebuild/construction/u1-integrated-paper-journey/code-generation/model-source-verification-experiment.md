# Bounded two-pass source verification experiment

## Predeclared candidate

Profile `qwen-source-verification-4096-2048x2-v1` tests whether a separate generic
source-checking pass corrects the measured comparison/qualifier errors left by
single-pass thinking. This is an experiment, not normal readiness. Prior failed
outputs and their semantic findings remain evidence; truncation was not their
only cause.

Use the same pinned Qwen3:8b, original P1/P2/selected Korean span, fixed seeds
42 and 43, and compact text/citations schema. Each work item combines its
selected source sections. First generate a candidate, then check its claims
against the original excerpts and return corrected text. No paper-specific
answer facts, replacement templates, seed search, third call or automatic retry
is included. A failed first or second stage rejects the complete result.

Exactly two calls for a successful item, at most 2,048 generated tokens per call
and 4,096 total (including thinking), under one 90-second whole-work deadline.
Each call retains 4,096 context with at most 2,048 actual prompt tokens, the
existing actual allocation/truncation checks, one loaded model, two threads,
8-GiB loaded-model cap and existing memory/disk floors. Sampling remains the
thinking profile's 0.6/0.95/20/0. The second call retains the exact original
sources and binds the candidate bytes and original request by SHA-256. A
candidate beyond 4,096 UTF-8 bytes is refused before that second call.

Both raw stage outputs remain private, with separate prompt/output token counts
and final totals. Hidden thinking is not printed. Actual final claims still
require independent comparison against the original rubric: model self-review,
valid JSON and citations do not establish factual correctness. Selected-section
coverage does not claim a whole-paper summary.

## Execution

Executed 2026-10-12 (local time): component phase 111 passed in 4.57 seconds;
scoped Ruff passed. Model phase 10 structural/transport checks passed in 316.63
seconds. **Both complete seed attempts fail semantic acceptance; normal summary
readiness remains false.** No rerun or profile promotion follows this result.

Protected outputs:

- Seed 42: `/tmp/docsuri-u1-run/model-output-1791730791574653000.json`.
- Seed 43: `/tmp/docsuri-u1-run/model-output-1791730944863865000.json`.

Both owned model servers exited 0. Resource samples numbered 304 and 323.
Observed context was 4,096 and loaded-model size 5,919,872,122 bytes. Minimum
free-memory percentages were 23% and 24%; minimum free-disk readings were
17,408,741,376 and 17,071,562,752 bytes, above the preserved operational floors.
All eight source work items completed within 90 seconds; longest was 53.17
seconds. Per-call observed prompts ranged 213–1,629 tokens and generation
303–1,100 tokens, within both reserves. Complete per-stage counts and original
candidate outputs remain in these records; no combination of successes from
different seeds is represented as one successful attempt.

| Case | Seed 42 seconds / stage generation tokens | Seed 43 seconds / stage generation tokens |
|---|---|---|
| P1 scaling | 32.39 / 573 + 490 | 42.58 / 544 + 939 |
| P1 position | 36.95 / 619 + 607 | 37.97 / 549 + 706 |
| P2 memories | 50.33 / 732 + 935 | 53.17 / 1,100 + 675 |
| Selected EN→KO span | 25.99 / 414 + 386 | 21.82 / 413 + 303 |

Independent source review found seed 42's scaling, positional mechanism and
selected Korean span meet their bounded rubric. Its P2 explanation now states
the parametric/non-parametric memory definitions and variant distinction, but
adds an unsupported source-attributed uncertainty claim about MIPS and document
relevance. Seed 43 still reverses the small-dimension attention comparison and
changes extrapolation beyond training lengths into longer sequences during
training. The second pass did not reliably repair substantive source errors.
Seed 43's P2 and selected Korean span pass. Across both complete attempts the
bounded semantic review totals five passing and three failing source cases,
despite all eight structured source responses and both embedding checks passing.

This run's exact result/source inventory and JUnit are preserved under
`/tmp/docsuri-u1-run/two-pass-verification-`. Parent's independent SHA-bound
review is `/tmp/docsuri-u1-parent-model-review.json`.

The previous thinking phase's default result/JUnit were archived under
`/tmp/docsuri-u1-run/thinking-first-pass-` before this run. Model readiness is an
unresolved U1 prerequisite; diagnostic worker fixtures cannot replace normal
useful-output evidence. Remaining integration work may continue independently.
