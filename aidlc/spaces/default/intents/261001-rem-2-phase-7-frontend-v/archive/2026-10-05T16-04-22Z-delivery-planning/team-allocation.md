# Team Allocation — Phase 7

## Sources and Staffing Decision

Confirmed delivery questions Q9–Q11 select one-session Construction. A **Bolt**, one build pass ending in a runnable increment, maps to each approved Unit. The historical team-formation files describe placeholder roles and obsolete units; that stage is recorded skipped and does not prove those people exist or are available. No staffing capacity or multi-team allocation is inferred from them.

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
