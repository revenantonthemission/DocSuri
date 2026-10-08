# U1 Performance Requirements

## Sources and Evidence Status

Confirmed `nfr-requirements-questions.md` Q1 and summary; inception NFR9 and its exact profile; contracts C1–C4/C6–C8; U1 Functional Design. Upstream paths are beneath `../../../inception/`. These are acceptance targets and evidence requirements, not measured results. U2 completes the wider job UI/performance evidence and U3 owns asset decoded-readiness acceptance; U1 still tests its delivered behavior.

The current confirmed Q3 amendment consumes `../functional-design/functional-spec.md`, `../functional-design/rules.md`, `../../../inception/requirements-analysis/requirements.md`, `../../../inception/contract-design/contract-summary.md` and historical `aidlc/spaces/default/codekb/DocSuri/technology-stack.md`. Current Functional Design is independently reviewed in `../functional-design/reviews/review-03.md`; delivery and isolated-realm handoffs are `../../../inception/delivery-planning/bolt-plan.md` and `../../../verification/u1-isolated-postgres-bootstrap-plan.md`. Prior requirement/map bytes remain under `../../../archive/2026-10-05T21-28-11Z-u1-nfr-requirements/`.

## Detailed Requirements

| ID | Requirement / pass-fail condition | Method and source |
|---|---|---|
| NFR9.1 | SSE construction-to-open p95 is strictly <300 ms under the profile below. No network/gateway overhead is excluded. | Browser monotonic timing from native EventSource construction to open, 100 sequential samples; inception NFR9, AC8.2.1 |
| NFR9.2 | Status mount-request-to-first-committed-UI p95 is strictly <200 ms under that same profile. Cosmetic motion cannot delay the committed state. | Browser monotonic timestamps at requested mount and first committed named status surface, 100 samples; NFR9, AC8.2.3 |
| NFR9.3 | Evidence includes the raw sample set, build/browser/runtime versions, authentication, runner region, cache/network settings, percentile calculation and every failed operation. Failures cannot be counted as fast successful samples or dropped silently. | Record attempts and successful durations separately; use nearest-rank p95, rank 95 for 100 successful samples. Any failure is surfaced for resolution, with replacements/attempts recorded; NFR9, AC8.2.4–5 |
| NFR9.4 | Characterize relational prepared-result persistence/read latency and resource footprint for both branches, including representative larger supported translation content, without reducing exactness or adding an unapproved size cutoff. The report must identify fixture sizes, query/write measurements, configured budgets and observed bottlenecks before asserting capacity. | Measure exact final payload fidelity, bytes, latency distributions, database/worker resource use and errors against real storage. NFR Design pins fixtures/run details; Q1, FR3.5, NFR9 |

## Approved Profile

Production frontend build and the real staging BFF/gateway, authenticated unthrottled desktop Chromium, browser runner in the same deployment region, one active job, 100 sequential samples for each UI metric. Pin actual configuration and timing instrumentation before collecting evidence; synthetic/mock timings do not satisfy this profile. Record end-to-end overhead.

The uncached 100 KiB image fixture and decoded-readiness p95 <500 ms are retained for U3. They are not U1 result-payload-size bounds. Job execution duration is not substituted for SSE or mounting latency. Actual runtime/provider limits are inputs to worker timing design, not invented user completion deadlines.

## Measurement Boundaries and Failure Handling

The existing transport budgets remain 10 seconds for ordinary gateway requests, 15 seconds for SSE header acquisition and 10 seconds for asset relay, with the C8 bounded GET-only retry. Those timeouts are not the latency thresholds above; an operation finishing inside its timeout can still fail p95 acceptance. Polling remains a fixed configured two-second interval, not overlapping requests or a guarantee that every slow read finishes in two seconds.

Larger snapshot fixtures must preserve full final personalized content, including the exact shared C2 summary code/data strings, translation overlays and schema-valid bare DocModel. Do not flatten reproducibility or normalize string values to reduce measured bytes. Report resource pressure rather than trimming fields or substituting shared cache content. If approved input/result behavior cannot be supported by the selected database placement, surface the concrete design/placement decision before claiming readiness.

## Verification Handoff

NFR Design specifies collection/fixture details and the implementation instrumentation. Build and Test plus Performance Validation provide current results. No new production throughput, uptime or unlimited-capacity claim follows from these targets. Raw errors and private payloads must not be included in public telemetry; fixture content may be synthetic and isolated where appropriate.

The approved delivery recovery order requires current design/plan and narrow migration-admission/source-footprint reconciliation, admitted registered SQL and independently measured isolated-realm proof before required real-schema acceptance. Local model/shape checks and the preserved mock-default build do not establish this benchmark. Contract Design R-03 remains Accepted risk: its original schema environment misses date-time validation. Monotonic UI timing and actual application/store timestamp/expiry evidence must be collected through their own meaningful checks rather than attributed to that payload-shape pass.
