# Local model and paper-source eligibility evidence

Date checked: 2026-10-11. Scope: U1 Infrastructure Design research for bounded
local P1/P2 retrieval, understanding and translation experiments. This is a
source assessment, not an executed model test, production stack selection or
public-content permission grant. No models were downloaded, installed or run by
this research pass.

The governing requirements are [performance P02](../../nfr-design/performance-design.md),
[security SEC03/SEC07](../../nfr-design/security-design.md),
[technology T05/E02/E04](../../nfr-requirements/tech-stack-decisions.md) and
[functional WF2–WF5](../../functional-design/functional-spec.md). Exact source,
purpose, model identity and result coverage must remain visible. Source text is
evidence, never instructions granting tools or authority.

## Findings and disposition

| Item | Supported finding | Remaining boundary |
|---|---|---|
| Original Qwen3-8B | The publisher's model card and model-repository LICENSE identify Apache-2.0. Local inference is documented. | A similarly named cached quantization is not identified by the upstream card. Preserve the actual cache digest, provenance, license/notice, tokenizer/template and runtime metadata. |
| Original BGE-M3 | BAAI's own model card identifies MIT and documents multilingual embeddings. | The card does not establish the provenance or completeness of the notices shipped with a cached conversion. Dense embedding output alone does not establish every upstream retrieval mode. |
| Ollama | Its own source is MIT; official docs describe local inference, explicit cloud disable and bounded runtime parameters. | Localhost can also proxy a cloud-model request. Listener address alone does not prove local execution or offline operation. |
| Exact P1/P2 versions | Both version-specific arXiv pages link to the arXiv non-exclusive distribution license. arXiv's API terms separately allow personal/research use of content. | This supports the narrow local research assessment below; it does not establish public full-text, figure, translation or model-input redistribution rights. |
| U1 usefulness | Official sections below support a source-grounded evaluation rubric. | No search quality, supported language pair, useful output, full-paper coverage or mounted journey has passed through this source review. |

## Model license and runtime sources

### Qwen3-8B

The official [Qwen/Qwen3-8B card](https://huggingface.co/Qwen/Qwen3-8B)
identifies Apache-2.0 and demonstrates local execution. Its
[LICENSE](https://huggingface.co/Qwen/Qwen3-8B/blob/main/LICENSE) contains the
Apache-2.0 terms: redistribution includes supplying the license, identifying
modified files, retaining applicable notices and carrying applicable NOTICE
attribution when present. This is evidence about the original release, not an
assertion that a cached derivative satisfies those conditions.

The card describes a native 32,768-token context and tested extension to 131,072
with YaRN. Extension requires compatible runtime/configuration and is not an
observed local capacity. For non-thinking mode the publisher suggests
temperature 0.7, top_p 0.8, top_k 20 and min_p 0; its template can explicitly
disable thinking. A short-output local probe is a separate bounded experiment,
not reproduction of the publisher's long-output benchmark settings. These
documented capabilities do not prove Korean translation quality on P1/P2.

### BGE-M3

The official [BAAI/bge-m3 card](https://huggingface.co/BAAI/bge-m3) labels the model
MIT, with 1,024-dimensional representations and an 8,192-token sequence limit.
It describes dense, sparse and multi-vector retrieval and more than 100 languages.
Its dense-embedding guidance does not require adding query instructions. These
are upstream features; inspect the selected runtime's output before claiming a
particular mode or input limit is supported.

The linked publisher implementation, [FlagEmbedding LICENSE](https://github.com/FlagOpen/FlagEmbedding/blob/master/LICENSE),
is MIT and requires preserving its copyright and permission notices in copies
or substantial portions. That implementation license is additional evidence,
not a replacement provenance record for model weights. The attempted standalone
`BAAI/bge-m3/blob/main/LICENSE` web read did not yield usable content in this pass;
the model's MIT designation is established by its publisher-controlled card.
A placeholder copyright notice in a cached wrapper cannot be repaired by
inventing an author/year or silently copying the implementation notice onto
weights. Record that gap and reconcile the conversion's source before selecting
it for distribution.

### Ollama local-only candidate

The official [Ollama LICENSE](https://github.com/ollama/ollama/blob/main/LICENSE)
is MIT. The [FAQ](https://docs.ollama.com/faq) documents a default loopback listener
at `127.0.0.1:11434`. It documents cloud disable through either
`OLLAMA_NO_CLOUD=1` in the serving process or `disable_ollama_cloud: true` in
server configuration, followed by restart and confirmation of the cloud-disabled
log message. This disables its cloud models and web search; it does not itself
prove that all updater/download/network activity is disabled.

The [authentication documentation](https://docs.ollama.com/api/authentication)
states that the local API needs no authentication and demonstrates cloud-model
use through that same API. Therefore the candidate service boundary is a
protected loopback/internal executor with an explicit local-model allowlist,
verified cached identity and no remote-model or paid fallback. A public browser
must use the application's authenticated owner boundary; a raw Ollama port is
not that boundary. Do not infer cloud disable from an absent API key or a local
URL. Record effective configuration separately from this documented profile.

| Probe control | Official evidence and interpretation |
|---|---|
| Context and output | The [Modelfile reference](https://docs.ollama.com/modelfile) defines `num_ctx` and `num_predict`; use finite explicit values, including space for instructions, source and output. A `num_predict` limit is not an elapsed-time limit. |
| Defaults are not a reliable manifest | The FAQ currently says 4,096 context; the [context-length page](https://docs.ollama.com/context-length) describes VRAM-dependent defaults, and the Modelfile table says 2,048. Record the configured and actually allocated context rather than choosing among inconsistent defaults. Larger context increases memory demand. |
| Thinking, release and measurement | [Chat API](https://docs.ollama.com/api/chat) documents `think`, `keep_alive`, token counts, duration fields and completion reason. Select supported thinking behavior explicitly; `keep_alive: 0` requests unload after the call. A timeout or token-limit stop is an incomplete attempt, not useful-result success. |
| Embedding truncation | [Embedding API](https://docs.ollama.com/api/embed) defaults `truncate` to true. Use `truncate: false` so an oversized input reports an error instead of silently losing text. Preserve input hash, chunk boundaries, returned dimensions and prompt token count. |

An initial `num_ctx: 2048` / roughly 192 output tokens, one active call and a
finite request deadline can establish a small diagnostic envelope. Those are
experiment choices, not vendor-recommended universal values or a U1 capacity
target. Record client timeout and actual server termination/unload separately:
disconnecting a client is not proof computation stopped. A network-denied run
with all required cached artifacts can supply offline evidence; no such run is
claimed here. An existing cloud alias is not an approved fallback.

## Exact paper licenses and purpose separation

| Fixture | Exact-version evidence | License observed |
|---|---|---|
| P1 | [Attention Is All You Need, 1706.03762v7](https://arxiv.org/abs/1706.03762v7), version date 2023-08-02; [versioned HTML](https://arxiv.org/html/1706.03762v7) | arXiv perpetual, non-exclusive distribution license |
| P2 | [Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks, 2005.11401v4](https://arxiv.org/abs/2005.11401v4), version date 2021-04-12; [versioned HTML](https://arxiv.org/html/2005.11401v4) | arXiv perpetual, non-exclusive distribution license |

Both license links resolve to the [arXiv non-exclusive license](https://arxiv.org/licenses/nonexclusive-distrib/1.0/license.html).
Its grant is to arXiv. The [reuse guidance](https://info.arxiv.org/help/license/reuse.html)
explains that this license does not directly grant additional reuse permissions
and directs downstream reuse requests to the author/rightsholder. Neither exact
version was identified here as CC-BY or CC0 full text.

The [arXiv API Terms of Use](https://info.arxiv.org/help/api/tou.html) explicitly
list personal/research retrieval, storage and use of e-print content as allowed.
They separately identify descriptive metadata, including abstracts, as CC0;
that metadata rule does not relicense full text. They prohibit serving e-print
content from one's servers without the relevant license/rightsholder permission
and encourage links to arXiv for content access. Legacy API clients must also
respect one connection and at least three seconds between requests. No bulk
harvest is needed for this two-paper assessment.

This provides a documented basis for an isolated personal/research assessment:
read the exact publicly provided versions, select the necessary passages,
evaluate locally and retain minimal private research evidence. Applying that
basis to a small local translation/understanding probe is a purpose-limited
interpretation of the research-use terms, not a grant to publish derivative
content or a jurisdiction-specific legal conclusion. The [bulk-access guidance](https://info.arxiv.org/help/bulk_data.html)
also distinguishes computation/indexing from redistribution and requires
arXiv download links for indexes or tools.

The P1 HTML additionally carries a narrow Google permission for attributed
table/figure reproduction in journalistic or scholarly works. It does not
establish a general full-text/translation license or automatically authorize a
public product's figure-serving use. P2's Figure 1 may guide private evaluation;
this record does not reproduce its image or claim public image rights.

For these local probes, bind paper ID/version, fetched representation/hash,
retrieval time, section/span, permitted purpose, recipient, retention and output
coverage in the fixture manifest. Keep extracted passage bundles and unreviewed
model outputs out of public repository artifacts. Retain only the minimum
assessment evidence under the experiment's declared access/retention policy.
Before public display, translation delivery, corpus reuse or model transfer to
another recipient, establish that particular use's permission and recheck it.
Unresolved public rights remain a CorpusContent eligibility block; this does
not remove the eventual U1 journey requirement.

## Bounded official excerpts and evaluation targets

The quotations below are intentionally small: P1 has 20 whitespace-delimited
words and P2 has 13. The surrounding evaluation rubric is a paraphrase, not a
licensed copy of full sections. These quotations alone cannot supply every
required understanding fact. Build a purpose-bound private evaluation input
from the indicated exact sections when testing those facts; do not substitute
this expected-answer rubric as model source input.

### P1 — source anchors and a translation diagnostic

Read §3.2.1 equation (1), its surrounding scaling explanation, and §3.5 of the
[exact P1 HTML](https://arxiv.org/html/1706.03762v7). The source-grounded explanation
must connect growing key dimension to large dot products and small softmax
gradients, and explain division by the square root of key dimension before
softmax. For position, identify addition to embeddings at both stacks, matching
dimensions and the use of sine/cosine signals. The paper motivates sinusoidal
signals through relative positions and possible longer-sequence extrapolation;
do not turn that motivation into a guarantee.

Small translation input from §3.5:

> To this end, we add "positional encodings" to the input embeddings at the bottoms of the encoder and decoder stacks.

A reviewer checks preservation of addition, the positional-encoding term, input
embeddings and both encoder/decoder locations. Record English→Korean only if
that pair is explicitly offered by the selected operation. A fluent short
translation does not prove full-paper support or all technical-term fidelity.

### P2 — source anchors and a translation diagnostic

Read Figure 1's caption, §2.1–§2.3 and the relevant introduction context in the
[exact P2 HTML](https://arxiv.org/html/2005.11401v4). The explanation must distinguish
BART generator parameters from the retrieved Wikipedia/document-index memory.
Both variants retrieve top-K candidates. Sequence marginalizes document choices
at sequence level, using one document within each sequence-probability term;
Token marginalizes at each output position and can use different document
evidence across tokens. An answer saying Sequence retrieves only one candidate
fails. Reading the caption here does not claim visual inspection of the figure.

Small translation input from §2.1:

> The RAG-Sequence model uses the same retrieved document to generate the complete sequence.

Review the same-document and whole-sequence meanings together with the broader
top-K context. Do not score a translation of this sentence as proof that the
model understands marginalization. Keep retrieval query text, indexed source
representation and scored returned paper/version separate from the reference
answer. A two-item similarity ordering is diagnostic, not corpus-level recall.

## Evidence required to use or extend these results

For each actual probe record the exact cached digest, origin/notice gaps,
runtime/version, effective local/cloud routing, template and options, input and
output hashes, accepted coverage, source spans, finite resource/deadline policy,
raw outcome and competent review. Preserve failures, truncation and abstention.
An upstream model context limit or disk footprint does not establish local
working memory, concurrent-service headroom or sustainable throughput.

If the narrow research-purpose boundary cannot be maintained, use newly authored
synthetic text for infrastructure-only diagnostics. Example original input:
“The test library contains two documents. A delayed reply preserves the original
request identifier. A second read does not create another processing job.”
Give it a synthetic fixture ID and its own hash; never label it P1/P2. It can test
transport, encoding, bounded output, identity binding and a simple translation
comparison. It cannot close source-bound P1/P2 understanding, real search
usefulness, supported-paper translation or the complete mounted journey.

No legal exception was assumed, no rights were inferred from a paper being free
to read, and no model license was used as permission for input papers. The source
review supports a bounded research candidate; operating selection still needs
the parent experiment's identity, resource, quality and recovery evidence.

## Verification boundary

All external links above are primary publisher/project/arXiv sources read on
2026-10-11. Moving `main`/`master` documentation establishes the observed upstream
statements, not the installed runtime's behavior. Exact cached model metadata,
execution and resource measurements belong to the separate parent probe record.

Repository context was read directly as non-code documentation. Tier 2 graph
coverage was checked for all four governing files in project
`Users-revenantonthemission-Projects-DocSuri`, generation
`2026-10-11T08:48:14Z`, coverage recording `2026-10-11T09:29:41Z`: all returned
`no_recorded_issue` and `metadata_match`. That is a best-effort freshness signal,
not a completeness proof or executable conformance result.
The new evidence file returned `not_tracked` on its own coverage check and was
read directly; local links, UTF-8 decoding and quotation word counts were checked.
