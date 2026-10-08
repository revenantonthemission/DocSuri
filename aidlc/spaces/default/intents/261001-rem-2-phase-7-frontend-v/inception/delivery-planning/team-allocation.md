# Team Allocation — Phase 7

## Sources and Staffing Decision

Confirmed delivery questions Q9–Q11 select one-session Construction. A **Bolt**, one build pass ending in a runnable increment, maps to each approved Unit. The historical team-formation files describe placeholder roles and obsolete units; that stage is recorded skipped and does not prove those people exist or are available. No staffing capacity or multi-team allocation is inferred from them.

Q12 and the current confirmed summary select bounded modifications against the approved C2 correction in `../contract-design/contract-summary.md`. `bolt-plan.md`, `risk-and-sequencing-rationale.md` and `external-dependency-map.md` assign the recovery work without changing Units or staffing. `../../construction/u1-job-skeleton/code-generation/{code-summary,recovery-impact}.md` records preserved partial U1 source; `../../verification/u1-isolated-postgres-bootstrap-plan.md` is a planning handoff, not available environment access.

| Bolt / Unit | Implementation responsibility | Specialist assistance | Accountable human |
|---|---|---|---|
| U1 job skeleton | One-session AI-led backend/frontend integration; developer role during code generation | Architect for persistence/fencing/compatibility; QA for crash, auth and integrated evidence; security expertise for trust boundaries | revenantonthemission |
| U2 job resilience | Same session, serial frontend increment | Designer/QA for focus/accessibility; developer/architect for replay and immutable recovery | revenantonthemission |
| U3 secure assets | Same session, serial asset integration | Security reviewer for SEC-8/SEC-9; QA/designer for viewer behavior and equivalents | revenantonthemission |

Specialist assistance follows applicable stage procedures and permissions; this allocation does not dispatch work or create parallel teams. Preserve unit-major serial execution and solo/one-session ownership. It grants no automatic approvals, commits, deployments or environment access.

## Named Reviews and Checkpoints

- **Security review:** revenantonthemission, 2026-10-14. AI security assistance may support it. Assess actual available work and record evidence, findings, actions and disposition. If asset code is not ready, complete an implementation follow-up before asset release rather than treating design review as security completion.
- **Skeleton checkpoint:** revenantonthemission reviews U1's actual integrated evidence after the separately authorized verification command succeeds. A design approval cannot substitute for it.
- **Plan and design decisions:** revenantonthemission receives the required approvals and concrete unresolved choices. Construction autonomy remains whatever is explicitly chosen at the applicable checkpoint; one-session staffing is not autonomy.
- **Dependency readiness contact:** revenantonthemission coordinates confirmation of staging, backend/worker/queue/persistence, Sentry and asset-data availability. This is accountability for checking, not a claim of access or booked external staff.

## Working Agreement

Keep shared BFF/parent component edits serial. Use the approved `main` base/target and short-lived branches with squash merge when merging is authorized. U1's XL size requires internal demonstrable milestones and refreshed estimates; it is not an excuse to claim unverified component-only work as a finished skeleton. Separate testable internal changes where practical without adding unapproved units or exposing incomplete functionality.

At a blocker, record the affected acceptance/contract, evidence, owner and earliest next check; return the concrete decision to revenantonthemission. Do not invent a delivery date, reduce coverage or bypass ownership/expiry protections. Missing availability may permit isolated design/test work but prevents the blocked integrated verification or release.

## U1 Recovery Responsibility

| Work | Implementation/verification responsibility | Human decision or prerequisite |
|---|---|---|
| Current C2 and dependent-design revalidation | Architect/developer checks exact code/data preservation, both task branches, compatibility and existing authority/timing/ownership constraints | revenantonthemission approves required design/plan decisions; preserved earlier receipts are not new-attempt authority |
| Narrow migration-admission repair | Developer reconciles supplemental pre-write source capture, registered full-script identity and guarded transaction path; QA verifies changed-digest/unknown-script/authority negatives and real PostgreSQL constraints | Required current implementation approval; no direct rejected-SQL bypass or general guard relaxation |
| Disposable PostgreSQL realm | Platform/QA work prepares the concrete launcher, exact source/artifact/resource identities, effective isolation probes, trust bindings and identity-scoped teardown | revenantonthemission qualifies/authorizes actual resource/rule application and controls credentials; no secret values in chat or artifacts |
| Real schema and later purge evidence | Developer/QA runs implemented schema checks only after real realm admission; later adapts the retained purge fixture and verifies its distinct database before destructive setup | Missing/wrong/expired proof blocks mutation. The authority role has no purge-target or provisioner privileges |
| Stricter typing and complete quality evidence | Developer/QA resolves the imported graph within approved scope, completes source-bound coverage/CI collectors and preserves current-suite health | Unresolved scope/dependency/image/control/notification qualification goes to revenantonthemission; no quality-floor waiver |
| Accepted timestamp-validation limitation | QA distinguishes the upstream shape-validation results from timestamp/runtime-expiry proof | Preserve Contract Design R-03's accepted disposition; required application/store expiry evidence is still mandatory |

Partial implementation and the original dirty-source baseline remain intact through recovery. No staffing choice authorizes branch changes, commits, provisioning, deployment or the exact skeleton invocation. Keep the recorded October 14 security appointment and implementation follow-up requirement while recovery milestones are assessed.
