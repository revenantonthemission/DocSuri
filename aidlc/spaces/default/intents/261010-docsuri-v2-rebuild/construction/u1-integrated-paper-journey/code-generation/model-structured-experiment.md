# Bounded source-definition experiment

Predeclared on 2026-10-11, after corpus checkpoint 23f63ebd.

## Hypothesis and complete profile

The earlier aggregate prose format repeatedly omitted explicit source-defined
terms while retaining contextual details. This experiment separates short
explanation from model-generated definitions, each carrying its exact source
anchor and a verbatim supporting substring. It adds no paper-specific terms or
answers. Existing C06 sections, coverage and method revision remain the eventual
result boundary; this is an internal adapter experiment, not a new public API.

Use the unchanged complete P1 scaling, P1 position, P2 memories and selected
English-to-Korean span, plus the existing two-paper embedding diagnostic. Run
both predeclared seeds 42 and 43 using the same cached Qwen3 8B/BGE models,
source chunks and natural-section grouping. No seed search or automatic retry.
Keep context 2048, maximum 224 output tokens per call, at most eight calls per
work item and one enforced 90-second whole-item deadline including admission.
Temperature 0.7, top-p 0.8, top-k 20 and min-p 0 remain the previous experiment's
non-thinking profile. Summary readiness remains false pending complete review.

Summary JSON has exactly `text`, `citations` and `definitions`. Explanation asks
for at most 45 words. Definitions is an array of zero to two objects, each with
exactly `term` (1–64 characters), `meaning` (1–160), `anchor` from the supplied
vocabulary, and `quote` (1–180). The instruction prioritizes explicit source
definitions over benchmark/history/model-size details and asks for meanings of
at most 15 words. An empty array is allowed for sections without explicit terms;
the adapter cannot infer semantic completeness from an empty array. Translation
retains its translation-only text/citations shape and 90-word instruction.

The adapter checks exact quote membership in the named bound source block,
nonempty bounded fields, exact shape, known citations, and control characters.
It renders validated model-generated definitions beside the explanation without
inventing connective claims. Quote membership proves provenance only; independent
review must still establish that a definition follows from its quote. Neither
citations nor definitions are synthesized to repair a failed model response.

Any truncation, malformed output, unsupported quote, control character or failed
section rejects the complete result. Partial diagnostic outputs remain protected.
The current 224-token allocation may be insufficient for the extra structure;
such an outcome is a failed experiment, not grounds for silently raising limits.

## Prior formatting defect

The retained seed-42 output `model-output-1791726500430990000.json` contains an
actual U+0009 tab inside the intended inline model-dimension notation in the P1
position result. Its earlier bounded semantic assessment is distinct from this
formatting defect. Seed 43 lacks that tab; both attempts already failed overall
for omitted P2 terminology. Their original bytes remain unchanged. The new
validator rejects decoded C0/DEL characters while preserving correctly escaped
literal mathematical backslashes.

## Execution

Implementation preceded component fault tests: 90 component tests passed in
3.08 seconds, and scoped Ruff formatting/lint passed. One complete two-seed model
phase then ran and returned **6 failures and 4 passes in 73.01 seconds**. The
wrapper propagated failure. No automatic retry or parameter increase occurred.

Commands used the approved synthetic environment:

```text
python3 scripts/verify_docsuri_u1.py --phase component --profile synthetic-local --environment-file /tmp/docsuri-u1-run/environment.json
python3 scripts/verify_docsuri_u1.py --phase model --profile synthetic-local --environment-file /tmp/docsuri-u1-run/environment.json
```

| Seed/case | Prompt/output tokens | Outcome |
|---|---|---|
| 42 scaling | 469 / 224 | Truncated; whole result rejected |
| 42 position | 644 / 224 | Truncated; whole result rejected |
| 42 memories | 636 / 224 on first section | Truncated; remaining sections not executed |
| 42 Korean span | 219 / 55 | Returned bound translation, 2.87 s |
| 43 scaling | 469 / 217 | Completed JSON but quote was not an exact source substring; rejected |
| 43 position | 644 / 224 | Truncated; whole result rejected |
| 43 memories | 636 / 224 on first section | Truncated; remaining sections not executed |
| 43 Korean span | 219 / 55 | Returned bound translation, 3.16 s |

Both two-paper embedding diagnostics passed. They do not compensate for any
failed summary. Seed 42 retained 74 resource samples and seed 43 retained 76;
both owned servers exited with status zero. The final samples recorded about
13.8 billion free disk bytes and 51%/50% memory-free readings respectively; these
are sample observations, not new capacity guarantees. Each failed summary took
7.57–9.85 seconds. The whole-item timer and original allocations stayed intact.

Protected complete raw/source/runtime records are
`/tmp/docsuri-u1-run/model-output-1791728140163991000.json` (seed 42) and
`/tmp/docsuri-u1-run/model-output-1791728176657472000.json` (seed 43). Failed and
truncated raw responses are retained. The experiment demonstrates that this
structure does not fit the current output allocation reliably, and even the
one completed summary failed source-quote validation. Independent semantic
review cannot turn rejected outputs into accepted results. No normal profile
is selected; summary readiness remains false and further model work is held
for coordination. Cumulative finished-unit coverage remains pending.
