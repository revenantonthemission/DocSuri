# Bounded local model evaluation

Date: 2026-10-11. This is an executed infrastructure feasibility probe using
purpose-bound public-paper passages and synthetic retrieval text. It is not the
mounted U1 acceptance test, a public hosting decision or full-paper quality proof.
The [source and model eligibility assessment](model-source-eligibility.md) supplies
the exact primary references and narrow research-purpose boundary. Raw extracted
passages and generated outputs stay in the private temporary experiment record,
not in this public repository document.

## Runtime identity and isolation

| Item | Observed value and limitation |
|---|---|
| Runtime | Ollama 0.40.2, native arm64 Mac; dedicated listener `127.0.0.1:11439`; existing listener 11434 was not restarted or reconfigured |
| Generation model | `qwen3:8b`, manifest digest `500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41`; Q4_K_M 8.2B; cached model weight blob `a3de86cd1c132c822487ededd47a324c50491393e6565cd14bafa40d0b8e686f` |
| Embedding model | `bge-m3:latest`, manifest digest `7907646426070047a77226ac3e684fbbe8410524f7b4a74d02837e43f2146bab`; F16 566.70M; cached weight blob `daec91ffb5dd0c27411bd71f29932917c49cf529a641d0168496c3a501e3062c` |
| Effective server controls | Startup log confirmed `Ollama cloud disabled: true`; MAX_LOADED_MODELS=1, NUM_PARALLEL=1, MAX_QUEUE=1, CONTEXT_LENGTH=2048, KEEP_ALIVE=0, LOAD_TIMEOUT=60s, NOPRUNE=true |
| Cache | Isolated APFS copy-on-write copies of only the two model manifests and referenced blobs under `/tmp/docsuri-u1-infra-model/models`; no pulls/downloads, cloud alias or existing cache mutation in successful runs |
| Request controls | `think:false`, `stream:false`, `keep_alive:0`, context 2048, output cap 224 tokens, temperature 0, two CPU threads; generation timeout 90 seconds; embedding timeout 60 seconds with `truncate:false` |
| Headroom policy | Begin a call only at ≥35% `memory_pressure -Q` free reading and ≥8 GiB free disk; sampled generation monitor terminates owned process group below 20% or disk floor. Between calls wait at most 10 seconds for unload and admission headroom. This is not an OS hard memory reservation. |
| Input scope | P1 `1706.03762v7`, P2 `2005.11401v4` HTML retrieved once per exact version; bounded paragraph extraction, hashes and query/prompt identities preserved; no private user source or credentials |
| Cleanup | Each owned server terminated and waited after its run; final `/api/ps` returned no loaded models. Temporary source/output/cache cleanup follows the 24-hour-or-earlier experiment policy. Cloud disable is observed; a network-denied run and strict local-user port isolation were not tested. |

Both isolated manifest files and both complete weight blobs were independently
SHA-256 hashed after execution and matched the identities in the table. No
conversion-origin claim follows from a matching content hash.
The installed model manifests were checked before inference for exact identity
and absence of a remote host. Cached Qwen license metadata identifies Apache-2.0;
BGE's wrapper has placeholder notice fields. Original publisher evidence does
not establish a complete conversion provenance/redistribution record. Preserve
that gap before packaging or distributing the model derivative. Local source
eligibility cannot be reused as public full-text/translation permission.

## Failed attempts and corrections

| Attempt | Observed result | Disposition |
|---|---|---|
| Restricted-process startup | Server started with cloud disabled, but both model loaders returned HTTP 500 after Metal command-queue/context allocation failures. Compatibility metadata writes in the original cache were also denied. | No inference success claimed. Owned server exited; original failure logs retained. This does not establish that 24 GiB is insufficient. |
| Isolated GPU-enabled run | First P1 answer returned. The next-call ≥35% headroom test then stopped the run even though inference had finished. Lowest sampled free reading was 22%. | Preserved the successful response and stopped server. Did not reduce the floor or count skipped cases as passed. |
| Retry after headroom recovered | Added bounded wait for model unload/headroom; remaining three initial cases returned. Embedding was skipped when its between-stage headroom condition was not met. | Recorded absence explicitly; later dedicated opportunity completed it. No competing workloads were stopped or user files removed. |
| Grounding refinement | Initial positional response overstated extrapolation; initial RAG response incorrectly said only one candidate is retrieved. Expanded RAG input from 907 to 3,439 characters using actual introduction/§2.1–§2.3 passages; instructions distinguish implementation/evidence/hypothesis and probability terms/candidate sets. | Two revised responses returned. Both initial failures remain in the evaluation; this is a small prompt/extraction experiment, not a robust answer-quality guarantee. |

The first source extraction strips HTML tags and preserves resulting text,
including some duplicate Unicode/TeX math tokens. It is a diagnostic extractor,
not a production document model. Math/source-span fidelity and prompt-injection
handling require real parser and mounted checks before readiness.

## Executed generation outcomes

All six returned responses ended with `done:true` and `done_reason:stop`, below
the 224-token cap. Timings include loading and a single cold response; there is
no percentile, sustained-throughput, full-context or concurrent-service claim.
The review below is the parent agent's source comparison, not an independent
researcher's user validation.

| Case | Input/output tokens | Wall / load seconds | Source comparison and remaining issue |
|---|---|---|---|
| P1 scale | 304 / 103 | 7.229 / 3.888 | Correct square-root key-dimension scaling and large-dot-product/small-gradient explanation. Requested explicit section anchor was omitted; not complete acceptance. |
| P1 position, initial | 343 / 99 | 6.062 / 2.797 | Correct addition and both stacks, but overstated extrapolation as an established capability. Fails the evidence/qualification criterion. |
| P2 memory, initial | 267 / 123 | 5.422 / 2.053 | Wrong candidate-count claim and vague parametric-memory description. Fails usefulness; transport success does not repair it. |
| English → Korean, one sentence | 97 / 39 | 3.505 / 2.359 | Preserved addition to input embeddings, positional encoding and both stacks. Korean wording is understandable though literal. A supported-pair API and longer technical translation were not implemented/tested. |
| P1 position, revised | 348 / 126 | 6.893 / 3.303 | Separates implemented positional addition, learned/sinusoidal comparison and extrapolation hypothesis. Still does not enumerate every required P1 anchor/detail. Partial diagnostic improvement, not full P1 pass. |
| P2 memory, revised | 937 / 160 | 8.273 / 2.315 | Identifies BART and dense Wikipedia index, sequence/token distinction and top-K marginalization. Probability-term explanation remains imprecise and explicit section references are absent. Partial improvement, not full P2 pass. |

Sampled loaded generation size ranged from 5,265,728,470 to 5,615,785,082 bytes;
the runtime reported the same GPU size and 2,048 context. Lowest per-case free
readings were 22%, 25%, 31%, 29%, 34% and 30% respectively. Sampling can miss
peaks; these are model-reported resident observations, not total process/host
memory. Native API/browser/worker plus persistent database were not loaded
together. Do not use these timings as a public service target or combined budget.

## Embedding diagnostic

One five-input request returned five vectors of dimension 1,024 in 1.447 seconds
(reported load 1.292 seconds, 91 input tokens). Three newly authored short
paraphrase/synthetic records represented positional encoding, RAG memory and an
unrelated library receipt. Two original questions were ranked against all three
using exact cosine similarity:

| Query | Position record | RAG record | Unrelated receipt | Diagnostic result |
|---|---|---|---|---|
| Transformer word order | 0.413124 | 0.349292 | 0.370799 | Expected record ranked first, with a small margin |
| Two memories in RAG | 0.450824 | 0.657605 | 0.432805 | Expected record ranked first |

This is a real embedding call over authored text, not real paper search. It does
not establish corpus recall, Korean relevance, lexical/semantic mode parity,
filtering, pagination, source withdrawal, ranking scalability or end-to-end
retrieval. The embedding request did not have the generation monitor thread;
it had its finite deadline and preflight, and returned quickly. It is not an
observed peak-memory test. Shared execution and resource enforcement must cover
both operation types in the real adapter.

## Evidence identity and disposition

| Evidence | SHA-256 |
|---|---|
| Retrieved P1 HTML, 188,707 bytes | `fe1288e9c6f8322156429ab44bf5ced203155f8ecc7ea9fe6cfd125872c72a3b` |
| Retrieved P2 HTML, 244,097 bytes | `7f643ebcf14fa024288da5e7d79c834246101f8ff8d1258994b690fc79aeb892` |
| P1 scaling source bundle | `55771da733a09104fdf3886209765fca62cab16885e104a03715e7c64ae8adfb` |
| P1 position source bundle | `a4f497d0bc64cb8c736b0e60585620848ee71cde34820441321d91813229f994` |
| Revised P2 source bundle | `eacdb9f270432b19100e43d7dc87ac84c0c22a8509d2e8c72c0caca5ba5cfb6e` |
| Final private results.json, 44,018 bytes | `f119248548f000902b2684016972772a0878278ad7c5d89197d85df801abcbd9` |
| Final server.log, 60,955 bytes | `ff56e09a4727ef82a61a51309cda35b32eecedb167da997f71eb672bcd33975c` |
| Final temporary experiment helper | `466a9bdd634f4de040906f3656246922dc11295470243af3f2918083cdcc8680` |
| Synthetic embedding inputs | `06d0c991ecf81b7284254364c25d87be05f7f4e72931abc99476c3c80208cd23` |

The results record preserves each prompt hash, response hash, output, token count,
time and resource sample; earlier failed runs have separate timestamped copies.
The helper lives at `/tmp/docsuri-u1-model-probe.py`. It is experiment-only code,
not the service or the human-approved completion command. A reproducible normal
adapter with versioned prompts and eligible fixtures belongs to Code Generation.

Disposition: **local candidates remain viable for implementation experiments;
usefulness and combined capacity are not closed**. Do not activate normal U1
readiness with the initial prompts or these partial results. Improve extraction,
grounding and exact section binding; verify eligible P1/P2 and supported
translation through the installed browser/API/worker/store path, including
meaningful failure/abstention and resource limits. If the required output quality
cannot be achieved within $0 resources, bring that evidence to the human; do not
replace useful assistance with canned answers or silently remove the capability.
