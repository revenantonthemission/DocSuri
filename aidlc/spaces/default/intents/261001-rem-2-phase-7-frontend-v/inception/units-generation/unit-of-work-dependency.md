# Unit Dependencies — Phase 7

## Sources

Confirmed `units-generation-questions.md`, `unit-of-work.md`, and the approved Domain Design catalogue/ADRs.

## Dependency DAG

Each edge means the listed unit depends on its prerequisite. Names equal construction directory names.

```yaml
units:
  - name: u1-job-skeleton
    kind: service
    depends_on: []
  - name: u2-job-resilience
    kind: ui
    depends_on: [u1-job-skeleton]
  - name: u3-secure-assets
    kind: service
    depends_on: [u1-job-skeleton]
```

Text fallback: U2 depends on U1; U3 depends on U1. U1 has no unit prerequisite. There is no U2/U3 edge and no cycle.

U1 is the first resolved DAG unit and the integrated walking skeleton. It owns all code needed for summarize → BFF → SSE → COMPLETED → exact authorized result, including backend controller/service/worker and required adapter remediation plus protection/containment. Existing gateway/queue infrastructure remains a dependency; the remediated job/result backend is U1's deliverable, not an externally completed assumption. No code from a later unit is required. Contract Design is an earlier lifecycle prerequisite, not another unit.

## Integration Points

| Consumer | Prerequisite | Interface/behavior consumed | Boundary protection |
|---|---|---|---|
| U2 | U1 | Submission/captured recovery identity, known-job tracking, native stream and state/result transports, read-only result surface | Keep request identity immutable; preserve owner isolation, terminal state and no-submit reads |
| U2 | U1 | Form completion callback into stable PaperDetailIsland context | Pre-job recovery returns actual backend identity before tracking mounts; suppress obsolete responses |
| U2 | U1 | Backend summary/translation outcome and exact prepared-result contract, validated by US2.6/US3.4 fixtures | No generation on reads; owner/TTL enforcement and prepared personalization cannot depend on U2 UI work |
| U2 | U1 | Preserved failed-dispatch key-release exception | Actual replacement identity does not restart the old terminal job; reject late old-job updates |
| U3 | U1 | Configured BFF gateway routing, cookie relay/error conventions and paper/owner context | Limit proxy edits to asset handling; retain job-stream regression checks |
| U3 | U1 | PaperDetailIsland document composition seam | Preserve existing job surfaces, focus and context invalidation |

Integration details are logical contracts here. Contract Design defines actual wire/typed interfaces and authoritative error/cursor/reference behavior. No new subscription helper or custom-header native EventSource constructor is assumed.

## Topological Independence and Shared Files

After U1, U2 and U3 have no capability dependency on each other. Both topological orderings are valid; this document does not recommend one or identify an economic critical path. Serial Construction remains selected. Topological independence is not proof of merge independence: shared parent/proxy changes require explicit coordination and regression checks. Delivery Planning decides later scheduling and any approved concurrency strategy.

Frontend/BFF changes remain in Next.js; U1 additionally modifies the existing backend API and worker runtimes. They are not assumed to roll out atomically. Contract Design pins cross-version compatibility; Delivery Planning and deployment stages own exposure, rollout, verification and rollback under the production-on-merge practice. This is coordination within existing deployments, not a new architecture. Rollout readiness distinguishes a verified skeleton from full release completion.
