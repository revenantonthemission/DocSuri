# Thinking-mode candidate: bounded feasibility

Date: 2026-10-11. Named experimental profile; normal readiness remains false.

The structured-definition experiment reached its output limit and also produced
an unsupported quote. Rejected partial scaling text additionally reversed the
gradient explanation. Increasing JSON length alone therefore does not establish
semantic quality. A distinct thinking-mode candidate tests a different inference
mode while keeping the same model, sources and original acceptance rubric.

## Proposed named experimental profile

`qwen-thinking-4096-2048-v1`: same pinned Qwen3 8B, two fixed seeds 42/43,
temperature 0.6, top-p 0.95, top-k 20, min-p 0, thinking enabled. One combined
selected-source request per existing work item, using compact text/citations
JSON. Preserve complete P1 scaling, P1 position, P2 memories and selected Korean
translation cases; do not combine successful cases across attempts. No source-
specific answers, automatic retries, downloads or normal-profile promotion.

[Qwen's official quickstart](https://qwen.readthedocs.io/en/stable/getting_started/quickstart.html)
recommends these sampling values for thinking and warns against greedy decoding.
It also recommends a thinking budget above 1024 for meaningful gains. Its sample
two-generation budget mechanism is not part of this candidate. The proposed
2048 output cap covers the complete generation rather than guaranteeing a
separate 1024-token thinking allocation.

[Ollama's thinking documentation](https://docs.ollama.com/capabilities/thinking)
describes the thinking control and separate thought/answer fields. Support in
the pinned local model/runtime must still be verified rather than inferred from
documentation or a model name.

## Finite resource and correctness conditions

Context would be 4096 and total generated tokens at most 2048, including thinking.
The earlier combined P2 prompt used 1142 tokens, so a 2048-token input reserve
appears plausible. This is an estimate: changed instructions/schema/tokenization
must be measured and inputs exceeding that reserve refused, without truncation.

Keep the single 90-second whole-work deadline including admission, two threads,
one loaded model, 8 GiB loaded-model allocation, existing physical-memory floors,
8 GiB disk floor, bounded response/log files and cloud-disabled owned listener.
Longer generation may time out, and larger context may exceed memory limits.
Either is a failed finite experiment, not permission to increase those bounds.

Before any candidate inference, the implementation must verify the actual
`/api/show` thinking capability and model context metadata. During the run,
observe the effective loaded context and size through `/api/ps`; require the
declared context rather than silently falling back. Request validation must
admit only this named exact profile in addition to the unchanged existing
profile. Response validation must use the selected profile and reject length
termination, empty final answers, excess combined token count, malformed JSON,
unknown citations and control characters. Preserve both thought and final-answer
raw evidence privately for diagnosis; only validated final content is a result.

The existing runtime requires changes in four explicit areas: request options
and named-profile selection; startup metadata/capability checks; effective context
and memory observation; and profile-bound response token validation. The adapter
must use one combined request and retain the 90-second stop mechanism. Fault
tests precede a single complete two-seed run after implementation. All prior
failed attempts remain retained; semantic review remains independent.

## Scope limits

This candidate still evaluates the selected evidence spans, not complete-paper
summary coverage. C06 requests select an option rather than arbitrary sections;
the eventual U1 option must expose its finite source-selection policy and truthful
partial coverage/limitations. That integration must not turn bounded fixture
results into an unsupported whole-paper or public-capacity claim. No profile,
hosting or paid fallback is selected by this feasibility assessment.

## Implementation and planned execution record

The separately named candidate was authorized after Library checkpoint
27fd33bf. Request/server context and response validation now carry the exact
profile. Startup requires actual thinking/completion capabilities and advertised
context support; each candidate inference must observe effective 4096 context
while loaded. A missing observation or a possible truncation message in the
scoped server log rejects the result. Thought text remains private and is not
printed. The compact summary instruction allows at most 180 words, translation
90 words; the hard combined generation cap remains 2048 tokens.

After implementation, **100 component tests passed in 3.04 seconds**; scoped
Ruff passed. New fault cases exercise named-profile separation, exact option
bounds, missing capability/context, excess input/output tokens, absent thought
or final answer, length termination, and one-call source/anchor preservation.
The next step is one full fixed-seed model phase, with all prior failures retained.

## Observed experiment and remaining blocker

The single model phase returned **8 failed / 2 passed in 159.85 seconds**. Its
first log detector incorrectly treated the explicit `truncated = 0` status as
a truncation warning. Every generation was rejected; only the two embedding
diagnostics passed. Original outcomes and raw responses remain unchanged.

Actual startup metadata verified Qwen3 completion/thinking support and advertised
context 40960. Live observations verified effective context 4096 for every
generation, with maximum loaded-model size 5,919,872,122 bytes. Seed 42 retained
151 samples, minimum free memory 24%, and minimum free disk 13,495,771,136 bytes;
seed 43 retained 166 samples, 22% and 13,702,692,864 bytes. Both owned servers
exited zero. No work item exceeded 31.20 seconds; all raw generations reported
stop termination and remained below the declared combined output bound.

| Case | Seed 42 prompt/output tokens; seconds | Seed 43 prompt/output tokens; seconds |
|---|---|---|
| P1 scaling | 371 / 573; 17.91 | 371 / 544; 17.28 |
| P1 position | 546 / 619; 17.03 | 546 / 549; 15.51 |
| P2 memories | 1118 / 732; 22.21 | 1118 / 1100; 31.20 |
| Selected Korean span | 213 / 414; 11.64 | 213 / 413; 11.61 |

Protected evidence: `/tmp/docsuri-u1-run/model-output-1791729026792377000.json`
(42) and `/tmp/docsuri-u1-run/model-output-1791729103325010000.json` (43).
Thought text was not printed or used as the user-visible result; independent
review compared final-answer text against the exact recorded source inputs.

That review found substantive failures independent of the instrumentation bug.
Both scaling answers claim additive attention performs better for small key
dimension, reversing the supplied comparison. Seed 43 position changes potential
extrapolation beyond training lengths into longer sequences during training.
Seed 42 position and both bounded Korean spans satisfy the original semantic
checks; both P2 outputs state the memory and sequence/token distinctions, but
seed 42 adds unsupported uncertainty commentary. These partial successes do not
make either complete attempt ready.

After retaining these results, the detector was corrected to recognize explicit
zero/false truncation status while still rejecting positive or unknown truncation
messages. **101 component tests passed in 4.63 seconds** after the fix, with
scoped Ruff and whitespace checks passing. No identical model rerun is
performed because this correction cannot repair the demonstrated content errors.
Summary usefulness/grounding remains an unresolved U1 prerequisite; independent
Usage/PA integration may continue without asserting normal summary readiness.
