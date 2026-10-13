# U2 build, integration and local infrastructure pipeline

Date: 2026-10-14 (Asia/Seoul). Unit: `u2-account-personal-controls`, embedded library. Status: infrastructure design; implementation and operating evidence remain separate. The $0 budget, all-capability scope and one-maintainer model apply.

## PIPE2-01 — Inputs, placement and current evidence

The [confirmed proposal](infrastructure-design-questions.md) authorizes this artifact. The [security design](../nfr-design/security-design.md) supplies SD2-01–09; [logical components](../nfr-design/logical-components.md) supplies LC2-01–08; the [functional specification](../functional-design/functional-spec.md) defines behavior; the [component catalogue](../../../inception/domain-design/components.md) defines ownership; and [canonical contracts](../../../inception/contract-design/contract-summary.md) define inter-unit boundaries. [Traceability](traceability.json) maps all 39 derived NFRs to concrete bindings here. “OK” in that map means design coverage, not a passing implementation.

U2 extends the existing Python/FastAPI host, static React/TypeScript workspace and local PostgreSQL transaction facility from the [U1 infrastructure specification](../../u1-integrated-paper-journey/infrastructure-design/infrastructure-specification.md) and [delivery design](../../u1-integrated-paper-journey/infrastructure-design/cicd-pipeline.md). It does not deploy a second account service. U7 remains a separately controlled operator executable, with no authority inherited from an application administrator.

| Facet | Selected local binding | Boundary / remaining evidence |
|---|---|---|
| Compute | Existing native Python API/static web assembly; U2 modules registered through C00/C01 | No new broker, Redis, Kubernetes, paid service or host is required. One host remains a shared failure domain. |
| Storage | Same pinned local PostgreSQL 16 assembly as U1, separate synthetic U2 database realm and owner roles | Common physical transaction facility does not permit cross-owner writers. No existing-service database is selected or migrated. |
| Network | Loopback HTTPS API/static origin and loopback database; exact run-owned ports in a validated manifest | Reuse U1 port pair only after exclusive ownership/preflight. No public listener, remote tunnel or production callback is provisioned. |
| Async work | Owner-persisted responsibilities, bounded claim runners and fenced commits in PostgreSQL | No in-memory queue can acknowledge durable acceptance; no network call inside a long transaction. |
| Identity/delivery | Typed Google/ORCID/email ports; isolated deterministic synthetic adapters and local email sink for tests | Real credentials, provider eligibility and delivery remain G2-blocked. Synthetic success is not provider integration success. |
| Environments | Disposable synthetic test realm plus isolated restore realm; artifact quarantine for review | Dev/test labels cannot authorize real data. Public staging/production and migration remain unselected. |
| Shared ownership | U1 owns host/profile mechanism; U2 owners own their schemas, registrations, policies and UI; U8 completes composition | Coordinate host changes in U2; do not replace U1 behavior or let core import future modules. |

Current source inspected at application base `62ffd535` (documentation branch `a5d7f763`):

| Evidence | Observation | Delivery implication |
|---|---|---|
| `.github/workflows/u1-paper-journey.yml` | Frontend lint/types/Vitest/Vite build; Python scoped lint and pytest **collection only** | Collection is not execution. Add actual U2 component execution and trusted real-store/browser checks before claiming cumulative verification. |
| `scripts/verify_docsuri_u1.py`, main/headroom | Only `synthetic-local`, fixed `/tmp/docsuri-u1-run/environment.json`; build directories bounded at 2 GiB, free-space check of 12 GiB minus their existing occupancy | U2 needs an explicit coordinated profile/runner extension. Historical U1 512 MiB probe figures are not the current runner cap. |
| `backend/local_profile.py` | Fixed U1 path/realm/ports; owned bounded private files; expiry/run identity validation | Do not point current code at an arbitrary U2 path or a real DB. New U2 binding must retain these checks. |
| `backend/pyproject.toml`, `frontend/package.json` | Existing Python and pnpm workspace; React static Vite assembly coexists with legacy Next scripts | Use the explicit v2 Vite target. Old scripts named `test:u2` are not evidence for this rebuilt U2. |
| Local observation, 2026-10-13 UTC | 24 GiB RAM, 14 logical CPUs; later free-disk reading 41,600,000 KiB (about 39.7 GiB) | Snapshot only; remeasure before each experiment. No capacity reservation or public readiness follows. |
| Installed Python environment | Python 3.13.7; argon2-cffi 25.1.0, cryptography 50.0.1, pyotp 2.10.0, psycopg 3.3.6, FastAPI 0.141.1 | Installed versions do not establish frozen-lock equality, vulnerability clearance or provider compatibility. |
| Bounded in-memory Argon2id experiment | 10 sequential hash-plus-verify pairs, memory=65,536 KiB, time cost=3, parallelism=1; 15-second overall alarm. Durations ms: 179.253, 182.581, 176.085, 176.859, 176.929, 173.234, 179.936, 170.626, 175.874, 177.285. Peak process RSS 88,719,360 bytes. All verifications succeeded. | Synthetic probe only: no secrets or hashes logged, no account/store/network used. Select this as an initial test-profile candidate; concurrency, contention, security policy and public fit remain unproven. |

Graph-assisted Tier 2 inspection used exact main/headroom snippets and main outbound calls; narrowed symbol search exhausted three results. Relevant source/config paths had metadata matches and no recorded coverage gap at the 2026-10-13T14:59:17Z generation; this is best-effort evidence, not an exhaustive repository audit.

## PIPE2-02 — Reproducible build and artifact identity

| Sequence | Work / owner | Required evidence and failure action |
|---|---|---|
| 1. Contracts and policy | U2 developer coordinates C02/C03/C13 with their owners, then validates actual consumers | Apply PIPE2-05 and PIPE2-06 deltas before affected code. Record schema revision/digest and compatibility inventory. Stop on unresolved ambiguous protocol; doubles cannot invent a separate contract. |
| 2. Resolve | Build from a clean commit with frozen Python/pnpm locks and declared toolchain | Record repository/commit, Python/Node/pnpm/uv versions, OS/architecture, lock hashes, package licenses and vulnerability results. An unavailable advisory feed is incomplete evidence. No upgrade during a verification run. |
| 3. Compile and inspect | Scoped Python lint/type checks, frontend lint/type checks, static v2 build, generated-binding drift checks | Compile actual mounted U2 contributions and affected shared consumers. Dependency/style failures must have explicit provenance; collection-only tests cannot pass this gate. |
| 4. Component and contracts | Execute focused tests for owners, state transitions, browser clients, schema validation and adapters | Inventory expected test IDs/count and fail on zero tests, unexpected skips or fixture-only doubles replacing required store checks. |
| 5. Real integration | Trusted isolated run, PIPE2-03–08 and V1–V9 | Separate per-layer results; failed/unknown outcomes remain in the evidence. No real user data or credential loading. |
| 6. Package | Bundle compatible backend/module artifacts, static web assets, ordered migrations and validated configuration schema | Manifest includes source/lock/schema/policy/participant/migration/test-tool digests and content hashes. Exclude environment files, credentials, DB dumps and private browser traces. |
| 7. Promotion review | Same artifact bytes across verification and local promotion | Verify hashes and supported schema/config ranges. Rebuilding creates a new candidate requiring its affected checks. Nothing auto-deploys on main. |

Use existing free/local tools and caches only when their artifact hashes and origins are checked. Pin future workflow actions to reviewed immutable revisions; current tag-based actions are not claimed fixed here. Untrusted PR checks have read-only repository permission, bounded time/resources, no provider/deployment secrets and no access to the maintainer's private local runner. A maintainer-reviewed exact commit may run the isolated local integration job. Do not execute untrusted pull-request code on a general self-hosted machine with private credentials. Hosted jobs are optional only within verified free allowance with no overage; local checks remain the $0 execution path.

Artifact identity includes the complete installed participant manifest with owner, scope, protocol version and migration compatibility. An absent required U2 participant blocks the dependent acceptance at startup and execution; it never becomes a no-op success. Later units expand the manifest through their own verified contributions.

## PIPE2-03 — Local profile, storage and secrets binding

Implement a named U2 extension of the current profile/runner before using it. Proposed root `/tmp/docsuri-u2-run`, manifest `environment.json`, unique unpredictable run ID, synthetic U2 realm and distinct restore realm are **planned bindings**, not options supported by today's U1 runner. Preserve U1's unchanged supported invocation and add regression checks for both profiles.

| Resource / configuration | Required binding | Verification |
|---|---|---|
| Run root and manifest | Owned directory 0700, files 0600, no symlinks, bounded reads, finite expiry, repository/commit/run identity and declared synthetic profile | Refuse wrong owner/path/mode/expiry, reused foreign run and occupied ports. Cleanup only named resources whose ownership matches; retain failed-run evidence under its bounded policy. |
| API/static origin | One loopback HTTPS origin; host-only Secure/HttpOnly scoped cookies; explicit SameSite=Lax for tested top-level returns | Test success/error/redirect headers, origin + flow-bound CSRF, CORS denial, no-store and CSP. No global TLS bypass or public configuration inheritance. |
| Database | U1's pinned PostgreSQL image identity, checked locally before reuse; run-specific DB roles/credentials | Migration credential never enters API manifest; owner runtime roles cannot write another owner's schema. Back up/restore only the named synthetic realm. |
| Owner authority/effects | C02 guard on the common transaction facility; authority → owner control → operation → sorted child locks | Hold authority serialization until local owner commit. Test revocation/cutoff races and bounded deadlock retry. Cross-owner commits each reauthorize. |
| Keys | OS cryptographic randomness and maintained authenticated encryption; separate versioned seed/cursor/proof purposes | MFA ciphertext binds account/enrollment/key version as authenticated data. Digest nonrecoverable tokens. Never reuse password hashes as keys or log key bytes. |
| Local key custody | Run-owned 0600 key bundle outside DB and package, loaded through bounded no-follow reads; a separate 0700 recovery directory with its own 0600 copy | This is a synthetic host-level test arrangement, not protection against host loss. Missing/wrong/old key blocks dependent flows; no plaintext fallback. |
| Rotation | Active encrypt key plus explicitly permitted decrypt-only older versions; rewrap each owned record with compare-and-set evidence | Retire old keys only after live, pending, retained backup and restore manifests prove they are unnecessary. A failed rewrap remains visible and retryable. Test restart between versions. |
| Email and provider fixtures | Run-owned sink restricted to synthetic recipient allowlist and loopback callback fixtures | No real emails or accounts. Sink payload has short test lifetime and is excluded from normal logs; browser/trace evidence redacts codes/tokens. |
| Actual Google/ORCID/email | Adapter config and secrets separate from artifact; endpoints/scopes/callbacks explicitly validated | Disabled without G2 evidence. Do not reuse legacy secrets or create a provider account implicitly. |

Public and host-failure custody remains a prerequisite: identify a free permitted independent recovery location, key custodian and current restriction ledger recovery before real deployment. A second directory on the same disk cannot meet host-loss recovery. When that evidence is unavailable, affected service recovery stays quarantined; do not pretend a stale snapshot is authoritative.

## PIPE2-04 — Finite experimental policy and measurement

The following versioned `u2-synthetic-v1` policy is an initial, bounded **test profile** for at most 20 synthetic accounts and 100 records per list owner. It is not the production credential, retention, quota, SLO or public-abuse policy. The runner validates every value and cross-field sum before setup. Defaults cannot fill unknown real policy.

| Family | Initial test bound | Behavior / evidence |
|---|---|---|
| Request data | Body 64 KiB; password 1,024 UTF-8 bytes; scalar profile/query value 4 KiB; page 25 rows, maximum 50; response 256 KiB; manifest 32 required scopes | Reject oversize before hashing or transaction. Never truncate meaningful input or required scope evidence. Enumerated vocabularies remain G4-controlled. |
| Hash pool | Argon2id probe parameters above; 1 worker, 2 waiting slots, 2-second queue wait, 5-second execution deadline | Reject before accepting expensive work when full. Execution timeout fences the result and keeps the worker slot charged until termination is confirmed; no unbounded replacement workers. Measure memory/CPU and neutral outcome timing under contention. |
| API and DB | 8 normal in-flight requests plus 2 recovery slots; 8 app DB connections divided 5 normal/2 recovery/1 runner; 1 migration connection only while app stopped | Global limits include dedicated pools. Wait at most 1 second; DB transaction/statement/lock budgets 5/3/1 seconds. Long calls do not occupy DB transactions. |
| Provider transport | 2 simultaneous calls total, 1 per provider; connect/read/total deadlines 2/5/8 seconds | No automatic retry for unknown single-use exchange/send. Read-only probes at most 2 attempts with 1/2-second delays. Transport failure circuit opens after 3 failures in 30 seconds, probes once after 30 seconds. Neutral auth denial is not a transport fault. |
| Credential/proof fixtures | Synthetic session 15 minutes, limited continuation/proof 5 minutes, MFA display capability 60 seconds; attempt bucket 5 per flow per minute plus 20 per synthetic identity and 40 per network bucket per minute | Values exercise expiry/rate behavior only. Recovery checks show scopes cannot upgrade and one shared bucket cannot silently lock everyone permanently. Real settings require G1. |
| Background work | At most 100 outstanding responsibilities per owner, batch 5, global concurrency 2; lease 15 seconds, one attempt deadline 10 seconds, at most 3 automatic attempts with bounded 1/2/4-second backoff | Claim generation fences late effects. Exhaustion becomes durable blocked status. Outstanding-count cap includes blocked work; new admission stops, inspection remains available. |
| Polling/cursors | Cursor expiry 5 minutes; foreground refresh 2/4/8 seconds then 8-second cap, 20 attempts; stop hidden/offline | Manual read-only refresh remains. Stale cursor requests a fresh page, never changes acceptance or boundary. |
| Process/experiment | API+workers RSS safety budget 1 GiB; DB 1 GiB; one browser 1 GiB; never run build and load/restore phases concurrently; 5-minute measured workload phase | Supervisor samples resource use, stops new admission before budget breach and preserves owned recovery. OS-level container limits where supported plus process supervision; sampled RSS is not a hard allocation guarantee. Refuse to start if enforcement/preflight unavailable. |
| Build/disk | Preserve current U1 2 GiB build-tree cap and 12 GiB-minus-occupied free check; additionally reserve 4 GiB for U2 disposable data/recovery after that check | Require free ≥ max(12 GiB minus existing build occupancy, 4 GiB) at start; separately track U2 use so U1 headroom is not double-counted as spent allocation. Limits below sum to 4 GiB; no build/restore overlap. |
| U2 disk allocation | Live DB including indexes/WAL 512 MiB; restore DB 512 MiB; backup 256 MiB; test/browser evidence 256 MiB; diagnostics 64 MiB; recovery/maintenance reserve 2,496 MiB | Sum 4,096 MiB. Measure real footprint before advancing load. Disable new admission at 80% of live allowance; retain space for admitted commits, WAL and closure. Never delete mandatory receipts/restrictions to stay under quota. |
| Mandatory records | No age-based eviction of outstanding obligations, admission closures, suppression/tombstones or required proof of revocation during a run | Approaching record or byte bounds stops acceptance. Dispose the whole synthetic realm only after test evidence is exported safely and no external effect exists. This is not a production retention policy. |
| Optional telemetry | 1,000 queued events or 1 MiB buffer, whichever first; log files total 16 MiB, metrics/evidence share remaining diagnostics cap | Rotate/drop optional data with counters. Business evidence stays in owner store. No raw secrets/private payload in diagnostics. |
| Quota fixture | Two explicit test assignments with 3 one-unit operations in a test period; controlled boundary transition; no real billing | These are seeded scenario values, not new user allocation policy. Unassigned inspection is read-only and cannot fabricate an allocation. G6 governs real periods/refunds. |

Disk and memory bounds are proposed safety ceilings, not already measured guarantees. Before the first mutating load test, measure maximum allowed in-flight commits, WAL/maintenance growth and a full backup/restore of this fixture set. Prove their combined worst observed requirement plus a recorded margin fits the reserved 2,496 MiB and process budget; otherwise stop and reduce only the declared experiment dataset or propose a revised test profile. Do not consume the reserve with logs or declare the retained product scope reduced.

Record cold/warm task success with denominators, feedback and queue/local/provider timing separately, min/median/p95/max and sample counts, RSS/CPU/disk peaks, saturation rejection, unknown outcomes and recovery time. Ascend contention only within the above finite envelope. The small sequential hashing probe is not the account journey baseline. Numeric service targets require measured results and the user's subsequent agreement.

## PIPE2-05 — Atomic admission closure and quota reconciliation

This section supplies the missing mechanism from [NFR Design review R-01](../nfr-design/reviews/review-01.md). A negative acceptance lookup is never sufficient to release capacity. It refines SD2-07 consistently with U1 INFRA04; canonical coordination and executable closure still remain before accounting code.

| Record / transition | Authoritative owner and invariant |
|---|---|
| Admission intent | The accepting owner durably creates a unique intent before requesting a reservation: operation ID, generation, normalized intent digest, owner binding, policy, original period/quantity and state `open`. It cannot be recreated under the same identity after terminal closure. |
| Reservation | Usage atomically deduplicates on accepting owner + operation + generation, checks allowance and persists reservation plus backreference to the intent. A response lost after commit is inspected/replayed by that identity. |
| Acceptance | Accepting owner atomically compares `open` to `accepted`, under its admission-row lock and current authority guard, with effect/responsibility + immutable receipt and exact reservation reference in the same transaction. It validates the reservation matches intent/owner/period/quantity; no effect can precede this commit. |
| Closure | Accepting owner atomically compares the same `open` state to terminal `closed`, recording immutable intent/generation/digest, closure revision, reason and time. Competes with acceptance on the same row. It returns authoritative terminal closure evidence; a stale open read cannot authorize release. |
| Release | Usage verifies the accepting-owner contract's terminal closed evidence matches the exact reserved intent/generation/digest, then atomically releases once. A missing row, timeout, expired worker lease or unavailable owner preserves unresolved reservation responsibility. |
| Settlement | `accepted` cannot transition to closed-for-nonacceptance. Settle once by original reservation and accepted effect. Conflicting evidence blocks reconciliation; any permitted post-acceptance refund uses a distinct explicitly authorized policy transition. |
| Retry/new work | Same request always addresses the original intent. A retry after closure returns original closure, never reopens it. A genuinely new attempt uses a new explicit operation identity and any separately authorized generation; old packets cannot target it. |
| Retention | Keep terminal admission and Usage suppression evidence as long as delayed acceptance/replay or backup restoration can occur. Restore restrictions enforce it. Unknown safe compaction policy stops affected growth instead of erasing fences. |

No distributed transaction is claimed. Each owner commits its own state, with durable reconciliation over the stable identity. A trusted typed owner API returns evidence; client-supplied “closed” JSON or telemetry is not evidence. Worker leases control who may execute, but only the admission state controls whether an operation can still become accepted.

Required C03/accepting-owner contract delta before implementation: allocate/inspect/accept/close intent operations; closed-state evidence shape and identity binding; state conflict/error mapping; reservation reference checks and read-only reconciliation; permission scope and supported version. Name the accepting owner for each chargeable operation in the consumer inventory. Shared physical PG can bind close/accept through owner functions and row locks without granting Usage write access to that schema.

V6 must force both orders: pause acceptance before commit, close and release, resume the old acceptance and prove zero effect; accept first, attempt close and prove it cannot release. Kill each process before/after reservation, close, acceptance, settlement and release commit; recover repeatedly and inspect one intended effect/accounting outcome. Also test stale generation, forged closure, conflicting digest, period change, absent owner and restore with an older open intent. This design addresses the review's race; only canonical+runtime results can close the implementation finding.

## PIPE2-06 — Canonical coordination and mounted verification

| Integration | Binding before affected implementation | Required closure |
|---|---|---|
| C02 current authority | Same local transaction guard and exact scoped-session/proof/lifecycle permission matrix from SD2-01–03 | Mounted owner read/effect tests serialize revocation and deny foreign/expired/limited contexts; no unrestricted AccountAccess writer is exposed. |
| C03/C13 revisions | Explicit required expectedRevision for each affected mutation; original receipt before new-mutation revision check; safe error and rediscovery bindings | Inventory browser and real external consumers; regenerate versioned schemas/clients and run compatibility checks. No silent latest-revision retry. |
| C03/C13 reset recovery | Adopt exact SD2-05 proposal: required resetId in SettingsResetResult, listResets and inspectReset; outstanding/history routes, bound cursor, per-ID statusRevision and complete scope list | Coordinate required-result shape as potentially breaking. Test fresh authenticated restart with no browser state, two resets, lost acknowledgement, older status response and read-only inspection. |
| C03 accounting / accepting owners | PIPE2-05 admission state and terminal closure evidence | Version and validate all consumers before reservation/reconciliation code; V6 closes the race. |
| Participant registration | Immutable policy/manifest at acceptance; unique owner/scope/version and generation-fenced evidence for required live, derived, pending, external and restore work | Missing/incompatible registration blocks dependent command. No placeholders certify future U3–U6 scope; U8 verifies full parity. |
| Browser host | Korean account/settings/library/admin screens in existing static workspace; inherited blue/neutral tokens, Apple HIG web hierarchy, Light/Dark/System | Preserve visible controls during errors, authority-generation isolation, accessible status, manual onboarding/skip and safe sign-in return without action replay. |

Use explicit test layers and retain their different proof strength:

| Scenario | Automation / fixture and assertion | Evidence beyond isolated tests |
|---|---|---|
| V1 Account/proof journeys | Real owner DB through mounted HTTP for registration, verification, login, password/email recovery, Google/ORCID adapter fixtures; expiry/replay/lost response | Synthetic sink and protocol fixture results are labelled. Real provider/delivery remains separately gated, never counted as passed. |
| V2 Owner/admin/MFA | Two owners and distinct administrator; revoked role/session between validation and commit; scoped continuation misuse, foreign page/cursor/receipt, CSRF/origin checks | Single material delivery, TOTP/recovery-code replay, no secrets in logs/browser storage; application role cannot run U7. |
| V3 Library/history | Save/read/restart, lost reply duplicate, original clear checkpoint and delayed events around it | Inspect stored reference/receipt/boundary; newer permitted work survives old clear replay; reads do not add history. |
| V4 Reset recovery | Real API + browser storage cleared + fresh owner login; discover outstanding/history, two resets, cursor expiry/outage and reordered results | Count writes/claims/boundary changes during list/inspect: zero. Incomplete required scope never displays complete. |
| V5 Lifecycle/restore | Withdraw/erase/reactivate fixture policies, missing/replaced participant, generation races; isolated backup restore against current restrictions | Authority revoked before cleanup; pending/blocked truth, no restored erased data, no stale permission revival. Host-loss evidence gate remains open. |
| V6 Usage | Concurrent last allowance, revision conflict, missing assignment read, duplicate/unknown commits and PIPE2-05 schedules | Directly inspect reservation/intent/effect/ledger invariants, original period and replay; no negative-read release. |
| V7 Bounds | Saturate hash/provider/DB/work pools, pages/bytes, admission counts and declared disk experiment; bounded faults | Recovery slots work; no acknowledged responsibility lost, no worker multiplication on timeout, safety stop and measured reserve retained. |
| V8 UI/accessibility | Real browser desktop/tablet/phone, light/dark/system, expiry/account-switch/back-forward, no local secret persistence, Korean errors/status | Automated focus/contrast/reflow checks plus documented keyboard and screen-reader tasks. A screenshot/test count is not WCAG conformance. |
| V9 Repair/integration | Fresh setup from pinned artifact, seeded lost acknowledgement/reconciliation defect, repair through owner operations, cumulative U1/U2 and U7 separation | Reproduction/diagnosis/repair/recheck timings and exact commands; no direct manual row editing in recovery procedure. Keep known U1 assistance/search/figure gaps explicit. |

The U1 runner's fixture-reset behavior must be separated from U2 continuation tests: teardown/reseed cannot erase the responsibility being tested between interruption and authenticated return. Use isolated test cases and stable per-case run IDs. Do not label a reseeded browser session “recovery.”

## PIPE2-07 — Monitoring and failure response

| Metric / evidence | Source and bound | Action / routing |
|---|---|---|
| Accepted/rejected/failed/unknown and latency components | Allowlisted owner events, bounded operation/reason labels; no owner/query IDs in metric labels | Record baseline with sample counts. No invented latency SLO alarm. |
| Outstanding/blocked age and stale generation rejection | Authoritative per-owner status read, finite aggregate query | Missing or unknown source displays unavailable, not zero. Maintainer inspects owner evidence and resumes through its contract. |
| Authority/durability/key/participant readiness | Current capability observations with build/policy/manifest and observedAt | Stop affected admission immediately when required authority, store, key or participant fails. Keep read-only inspection where authorized and available. |
| Pool/disk/RSS and diagnostics drops | Profile-enforcing supervisor and finite telemetry counters | At admission safety threshold stop growth; budget breach stops the experiment safely, retaining durable state and a failed result. |
| Accounting invariant or restored restriction mismatch | V6 assertions and restore reconciliation | Block affected work, preserve evidence and investigate; no fabricated settlement or cleanup completion. |
| Provider readiness | Separate synthetic adapter, actual credential/terms/transport and public readiness fields | A local sink's green result cannot enable real public flows. Circuit/open/unknown status has safe user explanation. |

All diagnostic payloads follow SD2-08's allowlist: correlation/operation/reference, policy/revision/generation, timing, disposition and reason only. No password, seed, code, token, email/query/manuscript text, raw provider body or full callback URL. Error and retry paths undergo the same redaction checks. A protected defect packet contains source/tool/policy hashes, fixture seed, fault schedule, safe state transitions and executable reproduction command. User-facing status is owner-authorized; maintainer diagnostics do not grant arbitrary private-content access.

Optional logs are rotated within PIPE2-04. Durable receipts, admission closures, current restrictions and unresolved responsibility are database business state with separate backup/reconciliation obligations. Their loss is a failed durability result regardless of healthy logging.

## PIPE2-08 — Promotion, rollback and isolated restore

The selected local strategy is **stop, migrate, start, verify** for the synthetic shared application; overlapping blue-green/canary instances would add unproven resource and schema compatibility. Public deployment strategy remains unselected. There is no availability promise during local maintenance.

1. Verify exact candidate hashes, current profile limits, free capacity, key availability, permitted dataset and complete installed manifest. Stop new admissions and drain only within the finite budget; accepted work that remains is durable and visible.
2. Record current restriction high-water identity independently from the data snapshot: authority/revocation, consent, lifecycle/tombstones, clear/reset boundaries, admission closures and required evidence. Snapshot matching owner DB state plus manifests/integrity hashes; store encryption keys separately.
3. Restore to the isolated run-owned restore realm. Retain the untouched newer restriction journal from the original test environment; compare/reconcile restored rows through owning restore hooks before enabling reads/effects. An unavailable or insufficient journal quarantines affected data.
4. Run schema compatibility, key decrypt/version, manifest completeness and V5/V6 suppression tests. Verify restore never reopens a terminal admission or resurrects an erased/private record. Record elapsed time and peak space; no numeric RTO/RPO has been agreed.
5. Apply ordered compatible migrations with their own checks, start the same candidate, verify current capability readiness and a cumulative synthetic journey. Do not accept a new run simply because the process is live.
6. Roll back code/static/config only to an artifact compatible with current schema and policy. Forward repair incompatible migrations; do not run a destructive down migration by default. Restoring an older DB still requires current restrictions and reconciliation and cannot undo external effects.
7. Retain the last safe candidate and failure evidence within test bounds. Teardown requires verified run ownership and no unknown external work; remove only synthetic resources created for that run.

Real backup/restore and retention require G3: authoritative service/data and recoverable backups, independently durable current restriction evidence and key custody, approved lifetimes/reactivation policy and tested restore-set completeness. The current same-disk local exercise proves only the chosen fault schedule. It cannot establish host-loss recovery or authorize destruction/migration of existing users' data.

## PIPE2-09 — Gates, Git flow and handoff

| Gate | Implementation/design allowed now | Before real affected activation / completion claim |
|---|---|---|
| G1 | Synthetic credential/MFA policies and bounded measured hashing candidate | Maintainer decision on session/proof/recovery/abuse settings; concurrent fit and secure recovery proof; no admin bypass. |
| G2 | Provider adapters and synthetic protocol/sink tests | Actual Google/ORCID/email account eligibility, terms/scopes/free limits/no-overage, callback and real delivery evidence. No paid fallback. |
| G3 | Isolated synthetic lifecycle/key/restore exercises | Authoritative users/data/backups, obligations, retention/reactivation and independent current-restriction/key recovery evidence. No legacy 30-day default. |
| G4/G5 | Validated vocabularies and actual U2 registrations | Verified access matrix/consumer inventory and complete installed manifest for each accepted operation; later full integration covers every retained capability. |
| G6 | Explicit seeded quota scenarios and PIPE2-05 protocol | Approved real allocation/period/refund/accepted-work policy; unknown balance/policy neither unlimited nor guessed zero. |
| G7 | Finite test bounds with measured reserve and baseline | Public resource fit and numeric targets after evidence and human agreement; surface conflicts without feature cuts/spending. |
| G8 | Formal coordinated deltas before code | Canonical schemas/consumers plus executable proof for revision/reset/admission mechanisms. Design coverage alone does not close runtime findings. |

Follow [CONVENTIONS.md](../../../../../../../../CONVENTIONS.md): working branch → PR into develop; merge each fulfilled branch, then start the next branch from updated develop. Main release promotion is separate. Apply the user's interim CI policy while the pipeline replacement is pending: compare failing legacy jobs to the exact develop base, investigate new failures, record pending/unknown checks honestly, and do not change required checks merely to obtain a merge.

This pipeline design does not implement or run replacement CI. Code Generation must supply exact build/test configuration, U2 runner/profile extension, migration/policy manifests, local package and reproducible verification commands. The existing U1 invocation cannot certify U2. Present the exact runnable cumulative completion command for the separate recorded human approval before its completion checkpoint invokes it. Ordinary unit-stage completion remains automatic; enabled plans/summaries, verification selection and failure decisions remain human points.

Delivery evidence must identify which capabilities are implemented, verified locally, externally blocked or still open. U2 cannot declare all-release parity, public readiness, approved retention or complete accessibility from this document. The all-capability rebuild, Korean integrated interface and $0 constraint continue through subsequent units.

## Primary guidance

Sources accessed 2026-10-13 UTC. These inform controls; none establishes DocSuri's actual provider eligibility or production policy.

- [OWASP Password Storage Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html) recommends Argon2id and published minimum parameters; the larger local probe candidate above requires its own measured fit.
- [Google OpenID Connect](https://developers.google.com/identity/openid-connect/openid-connect) identifies provider subject as the stable identity key, rather than mutable email; validate actual issuer, audience, state/nonce and supported flow binding.
- [ORCID read-data API tutorial](https://info.orcid.org/documentation/api-tutorials/api-tutorial-read-data-on-a-record/) describes Public API credentials, registered HTTPS callbacks, authentication/read-public scope and Public API use restrictions. Establish DocSuri's actual permitted use and limits before choosing live credentials.

