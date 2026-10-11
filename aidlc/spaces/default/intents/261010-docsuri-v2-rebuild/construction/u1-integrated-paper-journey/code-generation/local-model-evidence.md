# Bounded local-model implementation evidence

## Status

Step 7/8 model execution and reference validation are implemented, but normal
summary readiness is **not established**. Actual P1/P2 explanations still omit
required distinctions or overstate source hypotheses. Passing format tests do
not close the useful-output rubric. No paper jobs or Usage reservations were
created by these isolated model probes. No full journey, operating capacity or
release readiness is claimed.

## Implemented boundary

- `docsuri_ops.local_models` verifies pinned cached Qwen3:8b and BGE-M3 manifests
  and blobs, creates APFS clones in the owned private environment, starts only
  its listener on loopback 11439, verifies Ollama 0.40.2/cloud-disabled routing,
  and stops its own process group after the run. Shared listener/cache remain
  untouched. Native GPU execution required the approved sandbox escalation.
- Generation remains context 2048/output 224 tokens, temperature 0, two threads,
  one loaded model and one in-process execution permit, zero keep-alive, 90s
  total generation deadline; embedding deadline is 60s. Admission may wait
  at most 10s for resource recovery within the request deadline.
- Disk floor is 8 GiB; model admission requires 35% reported free memory and
  execution stops below 20%. Finite request/response, source, log and model
  memory bounds remain enforced. Cross-process permits and protected
  native/container transport remain Step 13 work, not proven by loopback.
- Assistance validates source text hashes and exact anchors. Its internal
  constrained JSON format requires text and a nonempty citation array; malformed,
  empty, truncated, missing or invented references are insufficient results.
  Unknown IDs inside comma-separated inline citation groups are also rejected.
  No citations are fabricated to repair prose. Actual semantic support remains
  independently reviewed.
- Real BGE outputs require finite, nonzero 1024-dimensional vectors. The current
  two-paper diagnostic ranks each intended source first; this is not yet the
  approved research-query search over the application corpus.

## Executed checks and retained attempts

Exact development invocations:

```text
python3 scripts/verify_docsuri_u1.py --phase component --profile synthetic-local --environment-file /tmp/docsuri-u1-run/environment.json
python3 scripts/verify_docsuri_u1.py --phase model --profile synthetic-local --environment-file /tmp/docsuri-u1-run/environment.json
```

Component phase: **56 passed, zero skips, 2.98s**. Scoped Ruff check passed on
the five model implementation/test files after a line-length correction.
Per-module cumulative coverage has not yet been measured for these files;
the completed-U1 80% floor remains required.

Protected evidence files below are under `/tmp/docsuri-u1-run/`, named
`model-output-<ID>.json`. They contain exact source/config digests, private
source excerpts, raw responses, timings, model/runtime pins and resource samples.
Complete fetched text and raw responses are intentionally not committed.

| ID | Transport/reference checks | Evidence interpretation |
|---|---|---|
| 1791723013099623000 | 5 failed, 4.03s | Restricted native GPU allocation failed; later cases refused the stopped runtime. |
| 1791723099878718000 | 3 passed / 2 failed, 24.27s | Escalated GPU execution worked; two admissions lacked recovered memory. Returned summaries incomplete. |
| 1791723222316938000 | 5 passed, 33.22s | Bounded admission recovery worked; unsupported summary qualifiers/limits remained. |
| 1791723345173587000 | 1 passed / 4 failed, 36.01s | Invented/ranged/missing citations and output truncation rejected; raw failures preserved. |
| 1791723461336045000 | 5 passed, 29.92s | Position and selected Korean translation passed parent review; scaling guarantee and missing parametric-memory definition remained. |
| 1791723633821659000 | 5 setup errors, 6.06s | No model execution. Read-only clone reuse wrongly attributed unrelated filesystem growth; accounting corrected. |
| 1791723777403737000 | 3 passed / 2 failed, 32.08s | Range/missing references rejected; semantic completeness remained inconsistent. |
| 1791724195142174000 | 5 passed, 30.31s | Constrained JSON fixed reference shape; scaling/position certainty and P2 top-K coverage regressed. |
| 1791724265527430000 | 5 passed, 29.76s | Latest generic mechanism prompt still does not establish full source rubric. |

Each started owned server exited with code 0 at cleanup; the setup-only failed
attempt started no server. No test is reported as semantic success merely from
its transport/reference result. Earlier incorrect and incomplete outputs remain
available for review; no best-output selection establishes repeatable readiness.

Latest run returned scaling, position, RAG, selected translation and diagnostic
embeddings in approximately 6.53, 5.74, 7.04, 2.62 and 1.48 seconds respectively.
These five samples are diagnostic observations, not numeric service targets.
Latest translation preserves the bounded sentence's added positional encodings,
input embeddings and encoder/decoder placement; it does not prove arbitrary
document translation. P2 still says per-output/per-token without explaining the
document distinction and does not explicitly define the learned BART parameters.
P1 position still asserts relative-position learning beyond the source's
hypothesis. P1 scaling shifts the uncertainty to necessity rather than faithfully
preserving the causal hypothesis. These remain quality failures for readiness.

## Allocation correction and open work

The false setup refusal is retained. Reuse now records unchanged owned file
allocation rather than crediting/debiting unrelated filesystem writes. Creation
passes retain the conservative 64 MiB observed growth ceiling. The latest pass
reused 10 members, created none, and recorded zero owned allocation delta with
about 14.8 GB free. APFS shared block counts are not exclusive physical bytes.
Absolute host/runtime/recovery allocations were not weakened.

Keep model quality unresolved before exposing normal summaries. Mounted jobs,
source withdrawal, actual query search, worker fencing with model completion,
cross-process execution limits, process recovery and cumulative coverage remain
later implementation evidence. No paid fallback, model download, silent scope
cut or public hosting decision was introduced.
