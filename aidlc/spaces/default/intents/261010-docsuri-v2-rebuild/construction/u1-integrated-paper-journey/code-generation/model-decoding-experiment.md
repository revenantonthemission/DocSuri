# Fixed decoding-configuration experiment

## Predeclared profile

The prior exact-section neutral prompt produced useful P1 and translation
outputs but lost an explicit P2 definition. Definition-priority wording then
regressed P1 mathematical meaning. The next bounded experiment restores the
neutral section explanation and changes decoding configuration, rather than
adding paper-specific facts or increasing the resource envelope.

[Qwen's official quickstart](https://qwen.readthedocs.io/en/stable/getting_started/quickstart.html),
checked on 2026-10-11, recommends non-thinking temperature 0.7, top_p 0.8,
top_k 20 and min_p 0. Two seeds, 42 and 43, are declared before execution.
Each runs all four unchanged P1/P2/translation cases and the two-paper embedding
diagnostic. No seed search, mixture of successful sections from different runs,
or factual completion by authored answers is permitted.

The pinned cached model, source/parser bytes, exact natural-section grouping,
structured output validation, 2048-token context, 224 output tokens per call,
two CPU threads, at most eight source groups and shared 90-second whole-work
deadline remain unchanged. Thinking stays disabled. The timer must stop owned
computation at the deadline. There is no download, shared model-service change
or new spending. Failed/incomplete outputs remain protected evidence.

The adapter retains the original greedy diagnostic profile as an explicit
bounded option; only the two predeclared sampling seeds are additionally
admitted. Every request hash includes the actual options. The experiment
does not select a ready normal-output profile. Independent semantic review
must evaluate the complete same-profile output; format checks are insufficient.

## Results

Component regressions: 73 passed in 3.10 seconds. The single model phase ran
both predeclared seeds: ten execution/binding/retrieval checks passed in 87.59
seconds. Both owned model servers exited zero. Commands were the approved
component and model phase invocations from `unit-test-instructions.md`; model
execution used the authorized native GPU permission scope.

| Seed | Protected output manifest | P1 scaling / position / selected Korean span | P2 | Overall useful-output assessment |
|---|---|---|---|---|
| 42 | `/tmp/docsuri-u1-run/model-output-1791726500430990000.json` | Bounded rubric pass | Generator parameters as parametric memory omitted | Fail |
| 43 | `/tmp/docsuri-u1-run/model-output-1791726543678883000.json` | Bounded rubric pass | Generator parameters as parametric memory omitted | Fail |

The parent independently reviewed both complete outputs against the original
rubric. P2 explains the document index and sequence/token distinction, but still
omits the required generator-parameter definition. No additional top-K wording
or equation criterion was imposed. The two-paper embedding diagnostic ranked
the intended source first for each query; real corpus publication and research
query/filter checks remain separate unfinished work.

P1 scaling/position/P2/translation wall times were 6.67/5.88/19.97/2.86 seconds
for seed 42 and 6.83/5.85/20.75/2.93 seconds for seed 43. Full raw responses,
source bindings, actual decoding options, execution samples and source/config
digests remain in the protected manifests. There was no successful aggregate
quality result and no normal generation profile selected. Readiness remains
false; further seed or prompt search is stopped while unaffected discovery
implementation continues.
