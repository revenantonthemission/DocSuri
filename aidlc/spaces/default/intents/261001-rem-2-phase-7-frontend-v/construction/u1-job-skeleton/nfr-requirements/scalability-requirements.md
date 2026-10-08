# U1 Capacity Qualification Requirements

## Selected Profile

Confirmed Q1 selects qualification of the existing single-active-job profile and measured capacity, not invented production concurrency/throughput/uptime commitments. Detailed verification sub-IDs inherit NFR11's test/evidence obligation and cite Q1 explicitly. Current runtimes, relational snapshot placement and the approved Unit allocation remain the design boundary.

The current confirmed Q3 amendment consumes `../functional-design/functional-spec.md`, `../functional-design/rules.md`, `../../../inception/requirements-analysis/requirements.md`, `../../../inception/contract-design/contract-summary.md` and historical `aidlc/spaces/default/codekb/DocSuri/technology-stack.md`. The current design retains both-task backend ownership and the exact C2 code/data object; `../../../inception/delivery-planning/bolt-plan.md` and `../../../verification/u1-isolated-postgres-bootstrap-plan.md` define recovery/admission handoffs, not measured capacity.

## Detailed Requirements

| ID | Requirement / pass-fail condition | Evidence |
|---|---|---|
| NFR11.6 | Every critical competing-authority scenario uses at least two claimants against real authoritative storage. All tested outcomes preserve single first-dispatch/first-invocation permission, consistent lifecycle/history, exact immutable binding and owner isolation. | Pin barriers/interleavings and run details for acceptance/dispatch, execution claim, renewal versus reconciliation, result publication and deletion. A passing isolated in-memory test alone is insufficient; NFR11, Q1 |
| NFR11.7 | Capacity/resource reporting identifies actual runtime/store configuration, tested concurrency, result-byte distributions, latency/resource measurements, errors and bottlenecks, including summary and larger supported translation fixtures and expired-payload cleanup effects. No unsupported production capacity or growth guarantee is asserted. | Record current measurements and known limits; qualify the unchanged NFR9 profile independently. Escalate inability to support approved data rather than trim results or silently cap size; NFR11, Q1, FR3.5 |

## Required Qualification Dimensions

Measure database connections/transaction wait, snapshot write/read volume, worker memory and queue/read resource behavior where available. Include at least the two result branches and documented representative larger translation content. NFR Design supplies actual fixture selection and repeatable run configuration; the reported largest fixture must come from supported input bounds/evidence, not the unrelated 100 KiB asset benchmark.

Capacity fixtures retain the complete final code/data object and prepared personalization, including allowed Unicode, whitespace and escaping. Neither synthetic shape checks nor an isolated in-memory actor proves durable contention, admitted PostgreSQL or deployment capacity. Required real-store runs are admitted through the qualified disposable authority realm; the separate minimal-schema purge database is used only after its guard/bridge adaptation. Record source/artifact/realm identity and failures alongside measurements under the existing NFR11.6/NFR11.7 evidence obligations.

Single-job UI timing and two-claimant correctness do not prove a production jobs-per-minute rate or general service availability. The capacity report must say which traffic/input ranges were tested and which remain unmeasured. Additional product scale targets require an explicit grounded decision; they are not inferred from historical persona usage counts or a worker's nominal concurrency setting.

## Scaling and Scope Handoff

Prefer evidence-led diagnosis of the existing deployment before proposing new services, databases or autoscaling. No new architecture is selected by this requirements document. Keep U1 backend guarantees for both tasks; U2 adds frontend translation/resilience, and U3 owns assets. Resource-pressure remediation that changes persistence placement or accepted behavior must be surfaced before implementation/release readiness claims.
