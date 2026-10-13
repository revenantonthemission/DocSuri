# U2 Infrastructure Design — proposal and confirmation

Date: 2026-10-13. Unit: `u2-account-personal-controls`, an embedded library with browser contributions. This proposal precedes the delivery/integration design and its independent review.

## Sources

| ID | Source | Constraint on this stage |
|---|---|---|
| NFR-D | [Security design](../nfr-design/security-design.md), [logical components](../nfr-design/logical-components.md), [traceability](../nfr-design/traceability.json) | Bind all 39 quality contributions to the shared assembly, finite policies, verification and recovery. Preserve domain authority and reset discovery. |
| REVIEW | [NFR architecture review R-01](../nfr-design/reviews/review-01.md) | Define an atomic accepting-owner accept-versus-close transition. Release requires durable closure evidence fencing delayed acceptance; test both winning orders and crash recovery before accounting code. |
| NFR-R | [Quality requirements](../nfr-requirements/security-requirements.md) and [technology decisions](../nfr-requirements/tech-stack-decisions.md) | G1–G8 constrain credential/MFA policy, providers/email, data/retention/backups, vocabularies, participants, quotas, resources and canonical bindings. |
| FD | [Functional specification](../functional-design/functional-spec.md) | Preserve current authority, protected proofs, real saved work, consent and reset boundaries, lifecycle completion and truthful accounting. |
| CONTRACT | [Canonical contracts](../../../inception/contract-design/contract-summary.md) and [component ownership](../../../inception/domain-design/components.md) | Coordinate exact C02/C03/C13 amendments and actual consumers before affected code. No duplicate domain store or operator authority through app administration. |
| UNIT | [Unit catalogue](../../../inception/units-generation/unit-of-work.md) | One shared application; U2 is an embedded library. U7 remains separately controlled. |
| LOCAL | [U1 infrastructure specification](../../u1-integrated-paper-journey/infrastructure-design/infrastructure-specification.md) | Existing local Python/API/static-web/PostgreSQL assembly and isolated synthetic environment; INFRA04 already requires closed admission intent before release. Local bindings do not select public hosting. |
| HUMAN | Confirmed rebuild/U2 summaries and [CONVENTIONS.md](../../../../../../../../CONVENTIONS.md) | All current capabilities, $0 free/local only, one maintainer, baseline-first targets; completed branches through PRs into develop under interim CI guidance, main promotion separate. |

## Resolved decisions and ambiguity analysis

Retain the shared application and four U2 domain owners. The library-kind stage produces `cicd-pipeline.md` and `traceability.json`; integration resource/configuration bindings belong in that delivery document, without inventing a separate U2 service or independent production infrastructure. The existing pipeline has not been replaced: designing its U2 verification path does not claim that new CI checks already run or supersede the user's interim policy.

No previous product choice needs repeating. No public host, paid service, migration/retention interval, MFA recovery bypass or unmeasured numeric service target is chosen. Where a binding depends on unresolved policy, specify the required evidence, safe refusal and responsible owner. Bring concrete policy choices to the human before affected implementation. Synthetic-only configurations must remain visibly distinct from public operation.

The new accounting finding requires a design correction before implementation: an authoritative negative read alone cannot permit release. The accepting owner must atomically select acceptance or terminal closure for an admission identity/generation; only closure evidence that rejects every delayed acceptance can authorize release. The pipeline must exercise both race orders and crashes. This proposal does not claim a coordinated canonical amendment or executable closure already exists.

## Dated local observations

At the start of this pass, `df -k /Users/revenantonthemission/Projects/DocSuri` reported 42,800,000 KiB available (about 40.8 GiB) on the working filesystem. Read-only `sysctl -n hw.memsize hw.ncpu` reported 25,769,803,776 bytes RAM (24 GiB) and 14 logical CPUs. These are shared-machine totals/observations, not resource allocations, free-memory measurements, public capacity or authority to remove unrelated data. Recheck before every bounded experiment and reserve recovery/restore headroom.

The NFR Design branch merged through PR #48 at develop `62ffd535`; its local document checks passed. Head CI run 38417131695 has ten completed failing job/step pairs matching base run 38397759390; macOS remains queued at this observation. Ingestion, discovery, PR dependency review, branch naming and CodeQL passed, and scheduled PBT is skipped. No failing or pending check is described as passing. This baseline is evidence to compare, not a substitute for runnable U2 verification.

## Proposed work

| Area | Proposed design and evidence |
|---|---|
| Reproducible assembly | Map U2 build/package/runtime dependencies, migrations, canonical generated bindings and browser contributions into the existing local application; pin identities and validate explicit configuration. Compare additional components only where necessary, within $0. |
| Security/configuration | Bind local credential/key custody, cookie/CSRF/callback configuration, participant identities, finite pools/queues/attempts and safe readiness. Investigate official provider protocols/free-use evidence before real provider selection; do not expose secrets in CI or artifacts. |
| Contract closure | Carry exact reset discovery/inspection and immutable acceptance semantics into the C03/C13 coordination gate; bind C02 authority guards and accept-versus-close accounting evidence before affected implementation. |
| Verification pipeline | Define scoped static/build/schema checks, real-store mounted integration, proof/owner/race/restart/fault tests, Korean browser/accessibility evidence and cumulative application checks. Keep fixture-only and public-delivery evidence separate. |
| Resource fit | Select only evidence-backed finite synthetic experiment bounds; measure hashes, database/concurrency, reconciliation and storage within reserved recovery headroom. Operating policies and service targets remain subject to their evidence/human decisions. |
| Promotion and recovery | Define reproducible artifact identity, environment promotion, safe stop/drain, migration compatibility, isolated backup/restore and rollback/reconciliation. Rollback cannot restore revoked authority or allow delayed acceptance after release. No production deployment is authorized here. |
| Observation | Package bounded safe logs/metrics/readiness and redacted reproduction evidence; mandatory receipts/tombstones/outstanding work survive optional telemetry rotation. |

## Assumptions & Open Questions

No new product assumption is adopted. G1–G8 remain explicit prerequisites for affected operation. U1 assistance/search/figure limitations and later-unit full parity remain open. Durable research drafts remain U4 work. The accepted U1 verification invocation does not prove U2; the exact expanded runnable cumulative command still uses the existing human selection point. Existing automatic ordinary completion does not waive enabled summary, plan, verification-command or failure stops.

## Consolidated Summary Confirmation

- Design U2's reproducible build, package, verification and integration into the existing free/local shared application. Keep the four domain owners and separately controlled U7 tool; retain every current capability.
- Bind security/configuration, finite resource policies, participant registration, safe observation and recovery to that assembly. Use isolated synthetic accounts and eligible fixtures until real-data/provider prerequisites are resolved; remeasure capacity and reserve recovery space.
- Resolve the accounting review finding with an atomic accept-versus-close decision at the accepting owner. Release capacity only from durable closure evidence that fences delayed acceptance, and require both race orderings and crash tests before accounting code.
- Coordinate current-authority and revision bindings, reset restart-discovery/status and accepting-owner accounting contracts before affected implementation. A design proposal or mock is not canonical or executable closure.
- Define build/schema/static checks, real-store API/browser integration, interruption/fault/owner-isolation checks and cumulative verification. Preserve the Korean responsive interface, inherited colors, Apple HIG adaptations, appearance modes and accessibility target. The exact runnable completion command remains a separate human decision when available.
- Define artifact identity, promotion, migration compatibility, safe rollback/reconciliation, secret custody and isolated backup/restore. Retention/reactivation, MFA recovery, providers/email, public capacity, continuity and quotas remain evidence-dependent. No paid fallback, feature cuts or public deployment is inferred.
- Produce the pipeline/integration design and infrastructure traceability, validate them and obtain independent review. Follow CONVENTIONS.md: completed branches merge through PRs into develop under the interim CI policy; pipeline replacement and main promotion require their own completed work. Continue serially with automatic ordinary completion and existing human decision points.

Does this all look correct before I generate the artifact?

- Looks correct
- Request changes

[Answer]: Looks correct
