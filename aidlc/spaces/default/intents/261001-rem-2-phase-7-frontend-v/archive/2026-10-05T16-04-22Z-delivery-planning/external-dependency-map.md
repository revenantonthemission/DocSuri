# External Dependency Map — Phase 7

## Basis

Each **Bolt**, a build pass producing a runnable increment, consumes the prerequisites below. The human confirmed **revenantonthemission** as the readiness coordination contact and security reviewer. Assignment is not evidence that an environment, credential, reviewer slot beyond the confirmed date, or dataset is available. No secrets belong in these records.

| Dependency | Blocks | Accountable contact | Status / lead time | Checkpoint and fallback if unavailable |
|---|---|---|---|---|
| Authenticated real staging frontend/BFF/gateway and test accounts | U1 integrated skeleton; U2/U3 end-to-end evidence | revenantonthemission | Unverified; lead time unknown | Check October 5 and before integrated run; escalate access, continue isolated tests where valid, do not substitute mock evidence |
| Existing backend API, worker, queue and persistence environment | U1 actual dispatch/result/crash verification | revenantonthemission | Unverified; configuration and capability must be inspected | Confirm compatible runtimes, queues and controlled test data; block real verification until ready |
| Exact prepared-result persistence and lease/fencing mechanism | U1 implementation approval | AI architecture/development work; revenantonthemission for unresolved decisions | Internal design prerequisite, not delivered | Functional/NFR Design pins C7 operations and timing; escalate infeasible guarantees before coding |
| Compatible API/worker/frontend rollout and rollback capability | U1 merge/exposure affecting live behavior | revenantonthemission | Unverified; existing production-on-merge practice is not proof of readiness | Pipeline/deployment work must provide compatible exposure and rollback before affected merge/release |
| Sentry project/configuration and safe telemetry path | Delivered error reporting and U1/U2 acceptance | revenantonthemission | Unverified; lead time unknown | Confirm configuration without exposing secrets; test scrubbed delivery/failure handling; do not downgrade to console-only reporting |
| Authorized paper/result fixtures for both tasks | U1 backend tests and integrated result demo | revenantonthemission with AI QA | Unverified real fixture availability | Synthetic fixtures support isolated tests; real authorized fixture required for actual skeleton evidence |
| Asset license/manifest/version and meaningful text/table equivalents | U3 secure delivery and accessibility | revenantonthemission with design/QA | Unverified; no content-service assumptions | Inspect actual data and allowed access, escalate missing equivalents rather than invent content |
| Human security review and disposition | Asset release; shared trust-boundary remediation | revenantonthemission | Scheduled 2026-10-14 | Review available code/design on that date; follow up on completed implementation before asset release if needed |
| Runnable real integrated verification command | First and later Construction checkpoints | AI developer authors; revenantonthemission authorizes exact invocation | Explicitly deferred; unset | U1 supplies the command and prerequisites, then a separate human authorization precedes execution at checkpoint |
| Current CI/test/coverage tooling | Every merge and unit acceptance | AI developer/QA; revenantonthemission resolves access/config blockers | Script inventory differs from historical assumptions | Reconcile actual commands and coverage tooling without weakening ≥80% new-code floor; keep current suites green |
| Same-region authenticated unthrottled desktop Chromium benchmark environment | U2/U3 performance and release evidence | revenantonthemission with AI QA | Unverified; lead time unknown | Confirm environment, collect 100 sequential samples per metric including overhead; do not replace staging profile with mocked timings |

## Dependency Handling

At the October 5 readiness check, record actual available services, who can grant missing access, realistic lead times and the next check date. Until then, unknown lead time is not zero. Recheck before each consuming verification or release activity. If access is missing, retain the blocked status and route it to revenantonthemission; isolated implementation/testing may continue only when it does not rely on invented capabilities.

No external team handoff or fixed product deadline was supplied. Do not infer either from historical placeholder roles. The required security appointment has a real date and accountable reviewer; any additional follow-up date must be scheduled based on actual asset implementation readiness, with disposition required before release.

## Operation Handoff

Delivery Planning defines accountability and compatibility constraints. Infrastructure/pipeline/deployment stages supply actual environment-specific provisioning, rollout, smoke-test and rollback procedures under separate authorization. Feature exposure must preserve accepted contracts during non-atomic upgrades and rollback; no old incompatible worker may consume new-format jobs. Existing runtime/persistence configuration must be verified rather than replaced by an assumed new platform.
