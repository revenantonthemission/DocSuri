# U1 build, verification and delivery pipeline design

Date: 2026-10-11 (Asia/Seoul). Unit: `u1-integrated-paper-journey`.
Status: future pipeline design. No workflow, application, deployment or IaC is
implemented or executed here. Physical candidates and their selection conditions
are in the [infrastructure specification](infrastructure-specification.md).

This design follows the [confirmed proposal](infrastructure-design-questions.md),
all six [NFR designs](../nfr-design/logical-components.md) and
[CONVENTIONS.md](../../../../../../../../CONVENTIONS.md). It retains $0, one human
maintainer, all release capabilities, the shared application release and separately
controlled operator executable. Ordinary stage completion remains serial; the
approved summary/plan/failure stops and the exact completion-command decision
remain applicable.

## PIPE01 — Execution placement, cost and trust

| Workload | Proposed execution binding | Enablement / trust conditions |
|---|---|---|
| Trusted local build and mounted rehearsal | Isolated versioned workspace and synthetic environment on the approved local native/container binding | Recheck real capacity; use declared disposable paths and credentials. No live owner data, inherited service secrets or existing store reuse. A clean checkout alone is not process/network isolation. |
| Untrusted PR checks | Candidate standard GitHub-hosted runner for the repository verified public during this design's read-only inventory; no deployment credential or model/private-host access | Reconfirm visibility and verify account/runner eligibility, quotas, artifact/cache policy and hard no-overage behavior before enablement. Keep trusted local work available when hosted eligibility is unresolved. Never connect the maintainer's private workstation as a runner for untrusted PR code. |
| Real local model and mounted storage tests | Trusted reviewed revision in the bounded local experiment environment | Exact model/runtime/digest and permitted fixtures must be established. Do not expose the model endpoint, database, host socket, home directory or private network to PR jobs. Hosted mock checks cannot certify this lane. |
| Trusted packaging/promotion | Separate trusted execution after relevant checks, with the minimum destination-specific permission | Rebuild reviewed exact source under the trusted pipeline and verify source/artifact identity. A matching digest alone cannot make a PR-produced binary trusted. Treat PR-created artifacts/caches as untrusted input, not executable promotion instructions. |
| Separately controlled operator package | Distinct artifact, manifest and credentials even if built from the same reviewed source revision | U1 tests absence and composition boundary only where U7 behavior is not installed. No application admin/session credential grants PlatformControl authority. |

GitHub documents free use for public repositories on standard hosted runners,
while private repositories have plan-dependent allowances; larger runners are
charged. Confirm account storage/cache rules and effective spending prevention
before enabling hosted jobs. A notification-only budget is insufficient for the
$0 constraint. Do not assume this repository's eligibility from the presence of
workflow files. [GitHub Actions billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions).

The local profile uses a native application/web/executor and candidate local Ollama
model runtime. PostgreSQL 16.15 is the selected common transaction binding for U1
implementation and its next mounted experiment, using the cached official image
`postgres@sha256:a3b7f434b2dc57ce85a67e171163eb8ab1a1ebcb39d27484661f26b1dfbe30d6`.
The [storage evaluation](evidence/storage-evaluation.md) passed eight modeled
PostgreSQL primitive checks; the actual owner roles, dedicated persistent Docker
volume, protected transport, container/VM restart and coherent backup/restore
remain required assembled evidence. The tmpfs probe does not establish them.
Native/container variants must satisfy the same checks. The initial experiment permits at most
512 MiB incremental disk growth, preserves an 8 GiB host free-space floor and
allows one expensive model call at a time. Build/dependency/restore/model temporary
growth joins that same total. If a clean build or restore cannot fit, record the
blocked run and revise the evidenced allocation before execution; do not fill the
disk or omit the required check. Existing model caches are usable only after exact
identity and permitted-use checks; no cloud model alias is a fallback.

For hosted checks, default token permission is read-only; supply no ordinary user,
operator, production, provider or model credentials. Pin approved actions by full
commit, review their code, separate trust-domain caches, avoid direct interpolation
of PR text into scripts, and do not check out untrusted code in a privileged
`pull_request_target`/`workflow_run` job. A maintainer's click does not make malicious
code safe for a private host. [GitHub Actions security hardening](https://docs.github.com/en/actions/security-for-github-actions/security-guides/security-hardening-for-github-actions).

## PIPE02 — Build stages and test-automation integration

The future versioned runner manifest will hold concrete commands and tool versions.
Those commands are not invented in a design document. Each stage records attempted,
passed, failed, aborted, skipped/unexecuted and unresolved checks with exit status,
resource envelope, exact revision and evidence. No check is marked passing because
its dependency was unavailable.

| Order / stage | Inputs and work | Gate / retained evidence |
|---|---|---|
| 1. Resolve source and preflight | Clean reviewed source identity; dependency locks; assembly and contract revisions; permitted fixture/model evidence; effective finite policy; actual RAM/disk/free-resource allocation | Refuse missing mandatory policy or unsupported binding. Record tool/OS/architecture and fresh capacity; no automated paid fallback or model download to fix fit. |
| 2. Contract and document consistency | Canonical C00/C02/C03/C06/C13/C14 amendments and generated producer/browser/worker consumers; lifecycle and boundary manifest; design traceability | Missing/malformed/stale revision cases, unsupported versions, required participants and compatibility inventory. R-01/R-03 and glossary/time findings remain open until canonical and executable evidence agrees. |
| 3. Reproducible dependency install/build | Pinned runtime and locked dependencies; client/server/worker builds; safe example configuration; separately packaged operator where applicable | Clean install/build completes within budget; lock drift, missing provenance or client-bundled secrets fail. An existing cache is an optimization, not the sole reproducibility evidence. |
| 4. Fast checks | Appropriate lint/type checks, owner unit tests, schema validation, deliberate dependency faults and security input cases | Deterministic fakes may establish denied/timeout/malformed behavior only. Record which adapter was replaced. No canned assistance success counts toward real usefulness. |
| 5. Real storage/owner contracts | Selected PostgreSQL persistent-volume/owner-role binding and authority serialization, CAS/uniqueness, claims/fences, receipts, immutable artifact binding and separate accounting reconciliation | Both revocation/effect race orders; concurrent commits; crash/reply loss; container/VM restart and coherent backup/restore checks. A different test store or tmpfs primitive test does not prove the mounted binding. |
| 6. Mounted normal journey | Real browser, application, worker, model, selected storage/search and fresh authenticated return over P1/P2 and supported translation | Useful semantic review, exact source/result binding, durable paper/query saves, same-owner recovery and account-B denial. Transport success, identifier lookup and prefilled answers are insufficient. |
| 7. Fault/capacity/security/accessibility | Mounted targeted faults, finite mixed load, observation outages, unauthorized routes, secret canaries, lifecycle/restore, keyboard/assistive and responsive checks | Preserve accepted identities and actual effects; demonstrate reserved recovery capacity. Record failure-inclusive baselines and manual review findings. No real-disk filling or current-data disposal. |
| 8. Package and provenance | Shared application/execution artifacts plus independent operator artifact as installed; runtime/configuration manifest, migrations, notices, fixture hashes and check report | Hash every deliverable; prove installed bytes match the checked artifact. No secrets, user stores or raw private evidence in release archives. |
| 9. Install/upgrade/repair rehearsal | Install the immutable package into a new isolated environment; exercise applicable migrations and controlled defect repair; verify owner reads and fresh readiness | Record setup/diagnosis/repair/verification time and interventions. Meaningful regression fails before repair and passes after; a restart alone is not repair. |
| 10. Integration/promotion evaluation | Exact revision/artifact and cumulative evidence; interim base/head CI comparison; migration/rollback compatibility and unresolved risks | Apply PIPE05. Exact runnable completion command remains `UNSET` until the human approves the actual v2 invocation before checkpoint use. |

Build automation may run independent bounded fast checks together; the resource
manifest caps aggregate concurrency. Model, restore and mixed-load experiments run
serially within the same shared allocation, preserving foreground and recovery
capacity. A job-level deadline stops computation and records incomplete work; it
cannot erase accepted obligations or release uncertain reservations.

## PIPE03 — Verification lanes, fixtures and completion evidence

| Lane / fixture | Required checks and observations | Distinct evidentiary limit |
|---|---|---|
| Fast injected failures | Timeout, malformed response, denied request, full logical allocation, dropped reply and retry exhaustion using controlled adapters | Good for exact fault placement and quick regression. Does not establish actual model usefulness, public delivery, storage durability or resource fit. |
| Real P1 `1706.03762v7` | Query `self attention sequence transduction without recurrence`; useful explanation of square-root key-dimension scaling, large dot products/small softmax gradients at §3.2.1 equation (1), and positional signals/sinusoidal choice at §3.5 | Require exact eligible content hash and anchored answer review. A direct ID search or expected-answer fixture cannot replace this normal retrieval/model path. |
| Real P2 `2005.11401v4` | Query `retrieval augmented generation parametric non parametric memory`; distinguish BART parameters and retrieved Wikipedia memory, RAG-Sequence and RAG-Token using Figure 1/§2.1–§2.3 | Reject “Sequence retrieves only one candidate.” Record omissions/unsupported claims and abstentions, not only fluent output. |
| Search binding | Bounded PostgreSQL lexical retrieval plus native exact dense-vector ranking is the initial candidate; evaluate every retained mode, Korean queries, filters, stable pagination, source withdrawal and growing corpus | Real selected embedding identity/quality and memory/ranking limits must pass before capability readiness. No initial Redis/SQS/OpenSearch dependency is needed; removing a retained search outcome is not a permitted simplification. |
| Supported translation | Actual returned supported language pair and exact eligible source/output spans, terminology and fidelity review | Preserve accepted options and immutable PaperAssistance glossary snapshot/non-null revision. Do not silently truncate input or remove a supported capability to fit. |
| Durable saves and fresh return | Save submitted query/exact paper; restart application/worker where applicable; start a new authenticated browser without transient job IDs; rediscover retained result from owner history | Reads create no new jobs, claims, glossary row or debit. Equal-time ordering, cursor expiry, source withdrawal and result unavailability remain explicit. |
| A/B/session/input security | Lists/direct IDs/assets/history/SSE, credential substitution, revoked sessions, CSRF/origin, hostile source/model text, redirects/SSRF/path inputs, late A callbacks after B login | Observe actual bytes and effects plus permitted positive controls. Current owner/source authority must hold at release/commit, not only at admission. |
| Acceptance/claim/result/accounting faults | Kill after reserve/accept/publish/settle; lost reply; delayed duplicate; acquire/renew/reclaim/revoke races; stale worker success/failure; restore and original-period reconciliation | Compare independent acknowledgement ledger with owner receipts, input/fence/result binding and one accounting effect. No exactly-once transport claim. |
| Capacity/observation failures | Mixed search/read/save/model work; queue/model cap; isolated write/quota failure; collector outage; stale probes; clock uncertainty; local incident discovery | Enforce physical/shared envelope and finite policies. Simulate pressure in isolated namespaces; never fill the host volume or count separate directories as isolation. |
| Interaction/accessibility | Korean full journey, focus/keyboard/announcements, 320 CSS-pixel reflow, 200% text, rendered contrast, Light/Dark/System, phone/tablet/desktop and source/result readability | Automatic checks supplement actual rendered/manual evidence; no automated-only WCAG conformance claim. |

The run manifest records permitted fixture acquisition/provenance, content hashes,
synthetic account identities, exact model digest/license/template/tokenizer/runtime,
acceptance options, policy/configuration/contract/build revisions, actual selected
adapters, enforced finite limits, workload and cold/warm conditions. Record failures,
aborts, unavailable dependencies, incomplete runs, raw outcome counts and protected
meaning-review evidence. Source text is untrusted data, never pipeline instructions.

The completion record has `completion_command: UNSET`. Implementation supplies a
real reproducible candidate invocation after the environment and cumulative suite
exist; the human approves it before its first checkpoint use. Later units extend
the same installed-operation/verification manifest. Added dependencies, policies,
model changes and cross-owner changes rerun affected U1 checks; full U8 parity is
not implied by a successful U1 contribution.

## PIPE04 — Artifact, secret and provenance management

| Item | Packaging / storage design | Verification and retention boundary |
|---|---|---|
| Application and worker release | One versioned shared-application assembly with controlled execution roles, immutable package hash and exact source revision | Verify dependency locks, contract/schema compatibility and installed artifact digest. Native archives and container images are alternative bindings, not two assumed production releases. |
| Operator release | Independent manifest/artifact/control path under PlatformControl | No shared privileged credential or automatically mounted app secret. Absent U7 behavior stays absent, not a success placeholder. |
| Manifest / software inventory | Source/tree identity, runtime/dependency/model identities, licenses/notices, build inputs/toolchain, configuration schema, migration range, checks and fixture hashes | Trace from source to checked package to installed bytes. This local provenance record is not a claim of a certified supply-chain level. |
| Dependencies and model files | Verified checksums/origin and exact immutable identities; optional bounded trusted cache | Cache misses do not cause an unapproved provider/model substitution. Model weights stay outside ordinary CI artifacts; package records a digest/reference and permitted acquisition procedure. |
| Build/check evidence | Safe summary plus protected local detailed evidence, linked by run identity | Put only sanitized summaries in PR/hosted logs. Resolve eligible output access/expiry before capture; cap storage under the infrastructure experiment allocation. Keep previous known-good manifest and current candidate within that cap. |
| Runtime secrets | Owner-scoped protected secret references resolved at launch, distinct synthetic/test credentials per environment | No secrets in Git, lockfiles, client bundle, image/archive, logs, cache or diagnostic export. Scan synthetic canaries across success/failure paths and rotate compromised material. |
| CI permissions | Read-only source/test token for untrusted checks; separate minimum promotion permission only in trusted context when enabled | Audit actions, workflow changes, effective routes and secret access. Secret masking alone is not proof of safe handling. No service/operator secrets used by PR tests. |
| Migrations/configuration | Versioned compatible schema transitions, explicit policy precedence and effective safe-config view | Missing/ambiguous mandatory policy blocks affected enablement. Preserve original in-flight intent/period/obligation across changes. A rollback must meet PIPE06's compatibility conditions. |
| Backup references | Protected coherent backup manifest, hashes, keys referenced through separate custody and current lifecycle evidence | Backup bytes and keys are never ordinary hosted CI artifacts. An isolated restore must prove meaningful recoverability; a copied directory is not a backup test. |

Use free local dependency/security/license scanning where the chosen ecosystem
supports it. Record scanner/database version and whether advisory data was current;
offline/stale scans remain limited evidence. Review findings against actual exposure,
fix exploitable blockers before enabling affected paths, and record unresolved
findings and justified disposition. Do not assume a paid scanner or hosted registry.

## PIPE05 — Environment promotion and deployment strategy

| Boundary | Promotion rule | Evidence / behavior |
|---|---|---|
| Working branch → `develop` | Fulfilled short-lived branch through GitHub PR, per CONVENTIONS | Until v2 replacement checks exist, compare known legacy base/head failures, run appropriate changed-work checks and investigate new regressions. Known pre-existing CI failures alone do not block this interim integration; failures/unrun checks stay disclosed. Never relabel failing CI as passed. |
| Trusted candidate → isolated rehearsal | Install one verified package into a synthetic versioned namespace | Same intended store/model/runtime binding and finite policies as checked. Restrict ingress/egress and disable unrelated public/external effects. Native/container overhead and supervision are part of the evidence. |
| Candidate rehearsal → accepted U1 evidence | Required actual-adapter, mounted normal/fault/usefulness/repair checks and the human-approved exact completion invocation pass for that revision | Design validators and legacy CI are insufficient. Record failed/unexecuted cases and unresolved operating scope; ordinary workflow completion follows its own existing gates. |
| `develop` → `main` | Separate release PR; production advances only by promoting develop | Version/tag per CONVENTIONS; review cumulative capability, continuity, operating policy, actual deployment target, rollback and public-integration evidence. A develop merge is not public deployment permission or proof. |
| Release artifact → operating environment | Future explicit selected environment and deployment execution after its prerequisites are satisfied | Public registration/email, DNS/TLS, source/model permissions, real-data retention/continuity, backups, capacity and $0 eligibility need actual evidence. The workstation experiment does not select public hosting. |

For the proposed one-instance local environment, use a controlled stop-and-replace
installation: stop new admission, allow bounded eligible work to settle or preserve
durable pending obligations, quiesce the old executor, install the verified package,
apply compatible migrations, revalidate sessions/claims/authority and run fresh
readiness/affected-journey checks before reopening admission. Record downtime.
The old and new application must not both acquire work unless future proved shared
fencing/capacity explicitly permits overlap. No paid blue-green estate or automatic
replica is needed or selected.

Feature/capability enablement is explicit and versioned. Missing evidence can keep
an affected path unavailable but does not close its release capability obligation.
Promotion never silently reduces search modes, useful model behavior, translation,
accessibility, public registration or any later-unit scope to make checks green.
Future v2 workflow implementation occurs in its own code/pipeline work; this
document does not rewrite current CI or branch protections.

## PIPE06 — Rollback, recovery and one-maintainer runbook

| Trigger / phase | Authorized procedure in the selected environment | Verification / stop condition |
|---|---|---|
| Build/package failure before install | Reject the candidate and preserve failure report; leave last verified package identity available | No installed-state claim changes. Remove only declared disposable build output within its retention policy. |
| Install/start/readiness regression | Stop new affected admission and executor acquisition; inspect effective manifest, owner state and protected incident evidence | Prefer previous known-good package only when its runtime, contract, schema and policy range still accepts current state. A binary downgrade is unsafe if those ranges no longer match. |
| Compatible binary/config rollback | Quiesce/fence old execution, install the retained compatible artifact, preserve owner stores/receipts and reconcile original accepted work | Current-authority reads, claim replacement, result/accounting integrity and fresh affected journey must pass before reopening. No stale session/worker is revived. |
| Incompatible/destructive migration | Stop; choose a forward repair or verified isolated restore under an explicit data/continuity decision | Never automatically downgrade schema, reset data or restore an old snapshot over live state. Explain acknowledged work that would be lost and external effects that would remain. |
| Corrupt/missing state or artifacts | Isolated coherent restore with serving, dispatch and external effects disabled; recover keys and current revocation/withdrawal/erasure evidence | Validate all owner/artifact links and acknowledgements, supersede restored claims/sessions, reconcile original obligations, then verify domain/journey readiness. Unknown current restrictions keep the scope closed. |
| Model/provider regression | Disable new affected admission; preserve accepted immutable model/input/period binding and truthful pending/result status | A model switch is a new evaluated binding, not transparent rollback. It cannot rewrite accepted intent or silently reprocess a retained result. |
| Suspected credential exposure | Revoke/rotate the affected credential through its owner, inspect scoped effects and rebuild a clean trusted artifact when required | Verify old credential denial, allowed new route and safe logs/builds. Do not print the secret during investigation. |

Rollback cannot undo an email/provider request already delivered, a published
external effect, a committed database change, disclosure of delivered bytes or an
accounting outcome. Those need the owning component's recorded reconciliation or
explicit compensation policy; a deployment script must not invent a refund,
release or cross-owner data edit. Already accepted work remains the original
operation through rollback and retry.

The maintainer runbook names the affected owner, exact artifact/configuration,
inspection permissions, current evidence, preconditions, safe action, expected
receipt/state, stop/escalation condition and final domain check. A controlled
rehearsal measures setup, diagnosis, repair and verified recovery, including manual
steps and failures. Keep previous compatible package metadata and recoverable
backup evidence within the declared allocation; retaining bytes on the same failing
volume does not provide media-loss protection.

## Sources and unresolved enablement

Authoritative local inputs: [confirmed infrastructure questions](infrastructure-design-questions.md),
[performance](../nfr-design/performance-design.md), [security](../nfr-design/security-design.md),
[scalability](../nfr-design/scalability-design.md), [reliability](../nfr-design/reliability-design.md),
[observability](../nfr-design/observability-design.md), [logical components](../nfr-design/logical-components.md),
[technology decisions](../nfr-requirements/tech-stack-decisions.md),
[NFR traceability](../nfr-design/traceability.json) and [CONVENTIONS.md](../../../../../../../../CONVENTIONS.md).
The GitHub primary references were read on 2026-10-11 and support only the
conditional hosted-runner cost/security design; account settings and eligibility
must still be verified before use.

Implementation owns the actual commands, workflow configuration, package format,
selected adapter conformance and fresh evidence. Data owners own policy/retention
and continuity prerequisites; ServiceOperations owns capacity and runbooks; the
human approves numeric targets after baseline and the actual completion command
before its checkpoint use. No model, database, public deployment, migration or
operating readiness is certified by this design alone.
