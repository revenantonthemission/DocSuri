# U2 NFR Design — proposal and confirmation

Date: 2026-10-13. Unit: `u2-account-personal-controls`, an embedded library with web contributions in the shared application. This proposal precedes the generated designs and their independent review.

## Sources

| ID | Source | Constraint on this design |
|---|---|---|
| NFR | [Security and cross-cutting requirements](../nfr-requirements/security-requirements.md) and [traceability](../nfr-requirements/traceability.json) | Map all 39 derived requirements across all ten inception NFRs to concrete patterns, owners and verification evidence. |
| TECH | [Technology decisions](../nfr-requirements/tech-stack-decisions.md) | Extend the existing shared application and selected PostgreSQL facility; distinguish observed bindings, candidate extensions and evidence-blocked public choices. |
| FD | [Functional specification](../functional-design/functional-spec.md), [rules](../functional-design/rules.md) and [frontend specification](../functional-design/frontend-components.md) | Preserve current authority, replay/revision ordering, protected proofs, lifecycle manifests, saved work, activity boundaries, accounting and safe owner switching. |
| CONTRACT | [Canonical contracts](../../../inception/contract-design/contract-summary.md) | Concrete typed/module/browser schemas must agree; coordinate C03/C13 reset recovery changes before affected code. |
| DOMAIN | [Component ownership](../../../inception/domain-design/components.md) and [unit catalogue](../../../inception/units-generation/unit-of-work.md) | AccountAccess, Library, Personalization and UsageEntitlements remain authoritative; WebWorkspace is presentation. No new permanent service or duplicate store by assumption. |
| REVIEW | [Functional review R-01](../functional-design/reviews/review-01.md) and [NFR review](../nfr-requirements/reviews/review-01.md) | Reset cleanup progress/restart discovery still needs concrete contract and executable closure. The requirements review found no new issues; it did not close this earlier finding. |
| HUMAN | Confirmed rebuild and U2 summaries | $0 free/local only, all current capabilities, one maintainer, public registration, baseline-first numeric targets, approved Korean visual/accessibility direction and existing decision points. |
| GIT | [CONVENTIONS.md](../../../../../../../../CONVENTIONS.md) | Completed branches merge through PRs into develop under the interim CI policy; main promotion remains separate. |

## Resolved decisions and ambiguity analysis

No earlier product decision needs to be repeated. The shared application, owner boundaries, public access model, $0 budget and retained capability scope are settled. Baseline-first numeric quality targets do not authorize unbounded admission or weaken correctness/security invariants. Do not copy generic guide examples for retries, timeouts, availability or retention as approved product values.

Requirements gates G1–G8 identify evidence that still constrains concrete bindings: credential/MFA recovery policies; provider and public email delivery; authoritative users/data, backups and retention/reactivation; vocabulary/access matrix; participant coverage; quotas/period/refund rules; finite resource fit and baseline targets; canonical coordination. Design the validation and refusal behavior for absent policy, and resolve evidence-backed details where possible. This summary does not supply missing policy values, approve public hosting or choose a migration. A concrete choice that needs human policy input returns to the human before its affected implementation.

Current contracts expose `settings.reset` with immutable acknowledgement and initial disposition, while `SettingsSnapshot` has no reset reference/progress and internal `settings.readProjection` does not expose cleanup status. Design a specific owner-authorized discovery/inspection pair or equivalent explicit settings-read extension, rather than rely on mutation replay. The design must choose one concrete shape, bind it to C03/C13 and document compatibility before affected code; this proposal does not claim that amendment already exists.

## Proposed design work

| Area | Intended concrete design | Verification obligation |
|---|---|---|
| Authority and protected proofs | Layer trusted browser entry, current owner/session/role/purpose checks, exact revision control and durable normalized-intent receipts. Specify scoped preauth/MFA/reactivation continuations, atomic proof consumption and safe credential/key handling. | Negative access/proof/replay matrix, revocation races, unknown outcomes, single MFA material delivery and separation from operator authority. |
| Public/provider boundaries | Define separate provider and delivery adapters, callback/redirect protections, bounded calls and truthful availability; distinguish synthetic conformance from public integration evidence. | Provider-specific callback/claim/subject checks, replay/mix-up/timeouts and real permitted free delivery evidence before readiness. |
| Reset recovery | Personalization owns durable reset identity, original boundary and acknowledgement; current progress derives from required per-scope evidence. Specify bounded owner discovery after authenticated restart and read-only inspection with concrete C03/C13 schemas/bindings. | Lost acknowledgement, no surviving browser receipt ID, overlapping resets, out-of-order responses, pending→blocked→complete and cross-owner denial; no read creates a new reset or advances a boundary. |
| Lifecycle and saved work | Define participant manifests, responsibility/evidence transitions, current consent/tombstone enforcement and restore restrictions. Preserve stable Library references and trusted history admission cutoffs; reset does not delete explicit Library/defaults. | Missing/stale participant, concurrent clear/reset, late events, reactivation/erasure and isolated restore with restrictions newer than the backup. |
| Accounting | Design finite current admission, owner-bound reservations, original-period settlement and durable reconciliation across separate commits. | Concurrent last allowance, retry, crash around acceptance/settlement, current-admin grant/revoke and unknown outcome; no guessed refund or distributed atomicity claim. |
| Capacity and fault isolation | Map bounded hash workers, provider calls, connection pools, reads/pages, reconciliation batches, retry/deadline policies and storage/recovery headroom to logical components. Define safe degraded/blocked behavior. | Resource-boundary and fault tests; numeric operating values require measured fit and policy evidence. No paid scaling or silent feature removal. |
| Browser and observation | Carry authority generations through private caches and delayed responses; preserve safe navigation, truthful states and accessible Korean feedback. Separate disposable diagnostics from durable authority/recovery evidence. | Shared-device restart/back navigation, keyboard/screen-reader/reflow/contrast, redaction/rotation and diagnosis/repair exercise. |

## Artifact plan

Produce `security-design.md`, `logical-components.md` and `traceability.json`. The library-kind output set has no standalone performance/reliability/scalability/observability document; those obligations remain fully covered in the two designs. Include owner boundaries, failure domains, shared-resource and blast-radius mapping, control/data flows, policy gates, recovery rules and evidence for all 39 NFR IDs. Validate cross-references and diagrams where used, then obtain independent architecture review. Canonical amendments are coordinated work before affected implementation, not a claim that a prose proposal has changed contracts.

## Assumptions & Open Questions

No new product assumption is adopted. Existing gates remain explicit: real data/continuity and backups; permitted processing/retention/reactivation; MFA recovery/session policy; public provider/email feasibility; quota/reset/refund policy; resource capacity and numeric targets; current consumer compatibility. U1's recorded assistance/semantic-search/figure limitations remain open. Durable research drafts remain assigned to U4.

## Consolidated Summary Confirmation

- Design concrete security, recovery, capacity and observation patterns for all 39 U2 requirements within the shared application and its four domain owners; retain all current capabilities and the $0 free/local constraint.
- Specify current authority, scoped sessions and protected proofs, exact revision/replay ordering, administrator MFA, safe provider/browser boundaries and secret handling. Keep application administration separate from operator authority.
- Resolve the reset-recovery design gap with durable owner-bound responsibility, immutable acceptance and separately evolving cleanup status. Choose concrete authenticated restart-discovery and read-only inspection bindings, coordinate C03/C13 before affected code, and require lost-reply/restart/overlapping-reset tests without a second reset.
- Design lifecycle participant completion, consent/clear/reset boundaries, permissible reactivation/restore and one intended accounting effect with durable reconciliation. Missing or unknown evidence stays explicit; no guessed completion, refund or resurrection.
- Define finite resource isolation, pagination, deadlines/retries and recovery headroom, plus safe diagnostics and reproducible baseline/repair checks. Numeric service targets follow measured baselines and human agreement; policy and resource limits must be concrete before operation.
- Preserve the Korean responsive workspace, inherited colors, Apple HIG web adaptations, Light/Dark/System and WCAG 2.2 AA target, including shared-device isolation and accessible failure/recovery feedback.
- Keep retention/reactivation, real-data continuity, backup obligations, MFA recovery, public provider/email delivery, quotas and public capacity evidence-dependent. Distinguish existing bindings from candidates; no paid fallback, silent feature cuts or public deployment inferred from local tests.
- Produce the security design, logical component/failure-domain map and complete traceability, validate them and obtain independent review. Continue serially with automatic ordinary completion and existing summary/plan/verification/failure decisions. Merge fulfilled branches through PRs into develop under CONVENTIONS.md; main promotion remains separate.

Does this all look correct before I generate the artifact?

- Looks correct
- Request changes

[Answer]:
