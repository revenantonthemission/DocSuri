# U4 — Research and novelty implementation

Status: independent review iteration 1 repairs passed local verification and the
U4 CI workflow at `83f6aa262e568eee2591f24418eda1ffe275518e`; ready for independent
review iteration 2. See `review-repairs.md`. This record does not certify
release parity, public operating feasibility, or completion of the construction checkpoint.

## What changed

ResearchWorkspace is an embedded owner in the existing application. It contributes
the C07 routes, research/novelty navigation, and one responsibility in the existing
supervised worker. `assemble_u4` supplies an explicit contribution to the inherited
U3 assembly; the normal U3 path retains its original realm requirement. Only the
exact owned U4 database/realm/origin may assemble the research contribution.
The C01 navigation contribution is capability-gated and permits the explicitly
degraded synthetic research surfaces only after authentication. Readiness adds
the research owner's context/job/artifact/admission store probe for U4; previous
assemblies retain eight required owners. A live worker alone cannot substitute
for that owner-store observation.

The research owner stores contexts, sessions and tombstones, accepted immutable
inputs, dispatch obligations, fenced execution claims, versioned drafts, private
attachment records, immutable expiring artifacts, evidence and assessments.
Every private repository operation rechecks current account/session authority.
Context/session ownership, revision conflicts, exact draft consumption, source
eligibility and terminal state guards are enforced independently of the browser.

An admission is durably prepared before the separate usage reservation. Acceptance
and dispatch commit atomically. Durable closure prevents delayed acceptance;
only that closure or a terminal execution result can release capacity. Unknown
commits retain their original identity for reconciliation. Result publication
binds the exact owner, context, job, input hash, claim/fence and artifact tuple.

The canonical C14 amendments add research payload and completion variants.
Research artifacts are not encoded as assistance results. The owner codec checks
the discriminator and all binding relationships because generated Pydantic models
alone do not enforce every JSON Schema conditional. Public routes expose C07;
worker claim, payload and completion operations remain internal.

The Korean interface distinguishes pending, acknowledged, failed and unknown
outcomes, retains exact retry identity, clears private state on account changes,
and confirms the scope of destructive actions. Session lists use owner-bound
snapshot cursors; mutations invalidate stale snapshots. Presentation reads never
submit new research work. Input limits are expressed as UTF-8 bytes.

## Deliberate policy and evidence boundaries

- Execution currently uses an explicitly synthetic extractive provider. It can
  demonstrate source-bound evidence, verified quotations and abstention, but it
  does not establish useful research-model output or substantive novelty scoring.
  Those capabilities remain owed for release; no paid provider is introduced.
- Durable draft and private-upload operations remain policy-suspended at C07.
  Internal versioned persistence/extraction primitives are tested, but unresolved
  retention, allocation/discovery and protected upload-byte bindings are not
  replaced with invented public endpoints. Restart draft recovery is not claimed.
- PDF extraction has a typed unsupported outcome in the bounded synthetic adapter.
  UTF-8 text extraction records malformed and truncated outcomes. Full supported
  private-document processing remains an explicit parity obligation.
- Web references are not fetched or treated as read evidence. The outbound target
  validator rejects unsafe schemes, hosts, addresses and redirects; a real network
  adapter still needs approved policy and address-pinning verification.
- Session deletion installs tombstones and invalidates result visibility. Its
  response remains `limited`: physical purge, retained backups and lifecycle
  participant completion are not claimed while their policies remain unresolved.
- Artifact expiry is enforced on reads and by an idempotent sweep. This is not a
  complete backup/restore or legal erasure policy.
- Browser and unit tests establish only their exercised cases, not WCAG conformance,
  user validation or numeric service targets. Baseline targets remain open.

All current capabilities remain in the first-v2-release scope. These gaps are
evidence and policy conditions to close, not silent scope reductions.

## Runtime and repairability

The owned synthetic environment uses PostgreSQL on loopback 15479 and HTTPS 18079,
with private manifest, credentials, TLS material and evidence below
`/tmp/docsuri-u4-run`. It is distinct from the pre-existing unowned U4 container.
The runner verifies identity, expiry, resource bounds, immutable migration hashes
and source/lock snapshots. Refusal and missing prerequisites are failures, never skips.

The source design mentioned Next.js, but the inherited executable workspace is the
Vite/React shell. U4 extends that existing release and records the mismatch; it does
not introduce a second frontend or claim a framework migration.

`traceability.json` maps 162 requirement/rule IDs to bounded implementation paths,
outside-unit responsibility, or explicit gaps. Its OK rows identify contributions,
not complete cross-unit requirements. Sixteen GAP rows preserve unfinished
model/document parity, draft and account lifecycle policy, complete accessibility
auditing and clean-checkout reproduction evidence.

Before review iteration 1, local verification passed 181 backend tests with zero skips and 87.66%
line coverage (every measured authored file at least 82%), 73 frontend tests,
and all six real browser journeys. The frontend's new source has 99.69% line
coverage; retained U1/U2/U3 frontend suites passed 18/92/31, and affected U1/U2
backend runtime suites passed 13/39. Shared contract checks passed 161 tests.
Those browser and backend runs used the same frozen source digest, now superseded by repairs:
`c171d721ffd83b8636511925e5c747f2fafd14fed47d0b778d5ec8611423e26a`.

After the review repairs, final local verification passed **191 backend tests**
with zero skips/failures/errors and **88.22%** coverage (each measured authored
file at least 82%), **74 frontend tests** with 99.70% new-source line coverage,
and **six real browser journeys** including two-view deletion and refresh.
Root and unit-specific frontend TypeScript checks passed without changing their
configuration. The repaired browser and backend runs share source digest
`263138dac917df184b469b9886e694fe0ce28f6d0970f0185c50aa4665cae8fa`
and owned realm `docsuri-u4-6242203c924051fe`, browser then backend coverage.
Remote CI run 38842485487 subsequently exposed a browser RSS-limit failure.
The browser-only V8 allocation repair at `83f6aa26` passed 78 operations tests
and a new six-case local browser run at peak RSS 928,759,808 bytes, preserving
the exact 1 GiB RSS guard and all journeys. That new browser evidence has source
digest `f7e5fe9c8fbda21938deb339944d9aba9abcf51bfe1a9f46b1e6089fde5cf442`.
The earlier local 191-test coverage remains tied to its original source; the
final-source remote cumulative run passed 193 tests with zero failures/errors/skips
and the unchanged 80% coverage gate. Its exact percentage is not available in the
public summary; 88.22% belongs only to the earlier local 191-test run.
The final remote browser run passed all six journeys with zero failures/errors/skips,
49 migrations and clean process stops, at peak RSS 1,012,883,456 bytes.
Shared-contract and frontend jobs also passed in
[U4 CI run 38843024805](https://github.com/revenantonthemission/DocSuri/actions/runs/38843024805).

See `testing-evidence.md` for failures, repairs and exact evidence records, and
`source-manifest.json` for application paths. The earlier pre-review local cutoff
preceded remote CI; the final successful run above supplies actual execution evidence.
Git remains working branch → PR
into develop; release promotion to main and deployment are separate.

The workflow's saved Construction Verification Command still invokes the U1
browser verifier and U1 realm. It does not verify U4. The later completion
checkpoint must obtain the preserved human approval for an actual U4/cumulative
command before using it. This code-generation work does not alter that workflow
setting or imply that command selection was approved.
