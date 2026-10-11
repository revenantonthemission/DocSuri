# Search ranking and cursor component

Implemented a finite page builder using the generated canonical query/result
bindings, with lexical/semantic modes, relevance/newest order, bounded author
and year filters, source metadata, exact paper/version eligibility references
and Korean match labels. Lexical scores come from a parameterized PostgreSQL
`ts_rank_cd` query over weighted title and projection text. Semantic ranking
requires compatible stored vectors plus a query embedding; missing/incompatible
input raises unavailable instead of producing an empty successful response.
No OpenSearch, BM25 or multilingual lexical-equivalence claim is made.

Cursors are signed with an injected private key and bind owner, complete query,
publication revision, page size and contract revision. Their lifetime is five
minutes, decoded size and offsets are bounded, and any changed context requires
a fresh search. Ranking deduplicates versions before pagination with stable
ties. Caller authorization and publication verification remain repository
responsibilities; the page builder creates neither jobs nor history facts.

After implementation, seven component cases were added. Exact component phase
returned **63 passed, zero skips, 2.93s**. Exact repository phase subsequently
returned **22 passed, zero skips, 39.88s**, including actual PostgreSQL lexical
scoring, canonical page output, source withdrawal and persistent container
replacement. Both used:

```text
python3 scripts/verify_docsuri_u1.py --phase component --profile synthetic-local --environment-file /tmp/docsuri-u1-run/environment.json
python3 scripts/verify_docsuri_u1.py --phase repository --profile synthetic-local --environment-file /tmp/docsuri-u1-run/environment.json
```

Scoped Ruff check passes. These are component and diagnostic-boundary results,
not the P1/P2 research-query acceptance checks. Real eligible corpus publication,
actual stored BGE vectors, approved research-query relevance, history/receipt
coordination, preference vocabulary integration, mounted UI and cumulative
coverage remain pending. The fixture vectors/scores used for pure policy
isolation do not establish normal search quality.

## Model review clarification

The parent reviewed the latest model evidence after its checkpoint. Do not
introduce an additional failure solely for omitting the word "hypothesize" when
a position explanation states the source's mathematical expressibility rather
than promising measured outcomes. The substantive unresolved summary findings
remain the complete P1 causal explanation and P2 memory/document distinctions.
No further model experiment ran during this source change. Section-wise
generation is being considered within the original finite whole-work envelope;
it is not implemented or verified here.
