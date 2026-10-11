# Completed runtime-fix branch integration

Date: 2026-10-11 (Asia/Seoul).

## Outcome

[PR #35](https://github.com/revenantonthemission/DocSuri/pull/35) merged
`fix/aidlc-session-propagation` into `develop` at
`9e6dbe49297459e84ebd754c3b738b473bedec7b` on 2026-10-11T03:31:16Z.
The PR head was `c29bcd071e9a3e030282e3314d12035133b7ad05`; its base was
`a94047d5`. The merge preserves the verified runtime repair and the approved
planning history through Refined Mockups, with Domain Design started.

The completed local and origin fix branches were deleted after the merge was
confirmed. Domain Design continues on `docs/docsuri-v2-domain-design`, created
from the updated `develop`. No main-branch promotion or release was performed.

## Authorization and interim policy

The user instructed: "When the fix is finished, merge to develop and continue
your work. every branch should be merged back to develop when their purpose is
fulfilled."

After the existing CI failures were identified, the user clarified:
"We haven't rewrite the CI/CD pipeline yet, so follow the git flow for now."

[CONVENTIONS.md](../../../../../../CONVENTIONS.md) records completed-branch
integration and the interim treatment of verified pre-existing CI failures.
The clarification permits this develop integration; it is not evidence that CI
passed or that the service is ready for release.

## Validation and limits

The current orchestrator SHA-256 matches the tested correction recorded in
[runtime-fix/verification.md](runtime-fix/verification.md):
`0faff50155adebcac735d594a6d00dbf3c07f4dc7fe2aaa895d4fcb0009e306f`.
The existing focused regression, type-check, packaging and compiled parity
evidence remains applicable to that unchanged correction. Current whitespace
validation passed.

[PR CI](https://github.com/revenantonthemission/DocSuri/actions/runs/38108334236)
had 11 failed jobs whose failure signatures matched the
[exact develop-base CI](https://github.com/revenantonthemission/DocSuri/actions/runs/38045880764).
No files changed in the application or CI directories between these two commits:
`.github`, `backend`, `frontend`, `ops`, `platform_integrity`, `shared`,
`ingestion`, and `summarization`.

| Existing repair area | Matching failure |
| --- | --- |
| Consumer inventories | Shared Python inventory drift and incomplete frontend consumer inventory; frontend TypeScript and generated-schema checks passed |
| Lint | Summarization: 62 Ruff errors; accounts/library: UP047 in library validation |
| Test environments/imports | Ops imports of psycopg/server; backend import of tests.u1_integration, with 1 failed, 501 passed and 7 skipped on both commits |
| Platform fixtures | Ubuntu native-platform failures; two macOS Keychain failures with status -25293; Postgres container lookup failure before tests |
| Audit inputs | Relative editable paths and hash-checking incompatibility in security/closure audits |

Ingestion, discovery, dependency review, branch naming and both CodeQL analyses
passed. Frontend tests/E2E/build and secret scanning were not reached after
earlier failures. No full-suite pass or vulnerability clearance is claimed.
These repair areas remain evidence for the subsequent CI/CD work.

## Approved Domain Design branch integration

On 2026-10-11, the user approved Domain Design with both Minor architecture
findings accepted. [PR #36](https://github.com/revenantonthemission/DocSuri/pull/36)
merged `docs/docsuri-v2-domain-design` into `develop` at
`b819700ec4526231a6832195bc11e147dbd49da0` on 2026-10-11T04:27:58Z.
The reviewed head was `e3b80ad722774b5fbbd822dea534a09ac96ae769`; its exact
base was `9e6dbe49297459e84ebd754c3b738b473bedec7b`.

The domain document verifier passed 13 components, 42 entity owners, 44 acyclic
dependencies, all 70 functional requirement mappings, seven ADRs and Mermaid
syntax. The independent review was READY with the two accepted clarifications:
search-projection write ownership and the artifact revision bound by export
approval. Document checks do not establish runtime parity or deployment readiness.

[PR #36 CI](https://github.com/revenantonthemission/DocSuri/actions/runs/38111431799)
finished with 11 failed jobs, three passed jobs and one skipped job. Every failed
job matched the error signatures in the
[exact-base CI](https://github.com/revenantonthemission/DocSuri/actions/runs/38108651681).
The failures belong to the same repair areas listed above; no new CI regression
was identified. Ingestion, discovery and dependency review passed, as did both
[CodeQL analyses](https://github.com/revenantonthemission/DocSuri/actions/runs/38111431921)
and the [branch-name check](https://github.com/revenantonthemission/DocSuri/actions/runs/38111431888).
Frontend tests/E2E/build and secret scanning were not reached after earlier
failures. Application source, dependencies and CI workflows were unchanged.

Integration followed the user's documented interim policy. The completed local
and remote Domain Design branches were removed, local develop was fast-forwarded
to origin/develop, and Units Generation continues on
`docs/docsuri-v2-units-generation`. Main was not promoted.

## Approved Units Generation branch integration

On 2026-10-11, the user approved the eight-unit decomposition with no new
architecture findings. [PR #37](https://github.com/revenantonthemission/DocSuri/pull/37)
merged `docs/docsuri-v2-units-generation` into `develop` at
`1033307515e3ebcf52bca2134a734885ae04a13a` on 2026-10-11T05:21:11Z.
The verified head was `03e3e71d8048bc4b3849f740a74e7e01ffbca063`; its exact
base was `b819700ec4526231a6832195bc11e147dbd49da0`.

The unit document verifier passed eight units, 19 acyclic dependencies, all
70 functional requirement mappings, ten NFR rows and Mermaid syntax. The
independent architecture review returned READY with no new findings. This
establishes document consistency, not runtime parity or free/local feasibility.

[PR #37 CI](https://github.com/revenantonthemission/DocSuri/actions/runs/38114290424)
finished with 11 failed jobs, three passed and one skipped. All 11 failure
signatures matched the
[exact-base CI](https://github.com/revenantonthemission/DocSuri/actions/runs/38111666857).
They cover the existing consumer inventory, lint, import/dependency, native
platform, Postgres fixture and audit-input defects listed above. No new CI
regression was identified. Ingestion, discovery and dependency review passed;
both [CodeQL analyses](https://github.com/revenantonthemission/DocSuri/actions/runs/38114290428)
and the [branch-name check](https://github.com/revenantonthemission/DocSuri/actions/runs/38114290429)
passed. Frontend dependency audit/lint/tests/E2E/build, ingestion/ops security
audits and secret scanning were not reached. Scheduled full PBT was skipped.
Application source, dependencies and CI workflows were unchanged.

Integration followed CONVENTIONS.md and the user's interim policy. Local
`develop` was synchronized to the merge, the completed local and remote branch
was deleted, and Contract Design continues on
`docs/docsuri-v2-contract-design` from that merge. Main was not promoted.

## Approved Contract Design branch integration

On 2026-10-11, the user approved Contract Design with three Major architecture
findings accepted. [PR #38](https://github.com/revenantonthemission/DocSuri/pull/38)
merged `docs/docsuri-v2-contract-design` into `develop` at
`d1bf16e1ae46e769cffc5b824705135e938687fb` on 2026-10-11T06:18:13Z.
The verified head was `f638b8698b905ae08a896f4c375909d8ef0ef01d`; its exact
base was `1033307515e3ebcf52bca2134a734885ae04a13a`.

The local contract verifier passed 14 contract families, 415 schema definitions,
1,421 references, 141 typed operations, 115 HTTP operations in two OpenAPI
documents, 19 dependency edges, all 70 functional IDs, six positive and nine
negative cases. The independent architecture review remains NOT-READY with
three accepted findings: browser revision preconditions, acknowledged-draft
rediscovery after restart, and worker execution claims/payload retrieval.
Acceptance permits the planning handoff; it does not resolve these findings or
establish implementation readiness. Delivery Planning carries their closure
obligations into the affected work.

[PR #38 CI](https://github.com/revenantonthemission/DocSuri/actions/runs/38117352817)
finished with 11 failed jobs, three passed and one skipped. All 11 diagnostic
signatures matched the
[exact-base CI](https://github.com/revenantonthemission/DocSuri/actions/runs/38114507506).
The failures concern existing consumer inventories, lint, imports/dependencies,
native platform fixtures, Postgres setup and audit inputs. No new CI regression
was identified. Ingestion, discovery and dependency review passed, as did both
[CodeQL analyses](https://github.com/revenantonthemission/DocSuri/actions/runs/38117352833)
and the [branch-name check](https://github.com/revenantonthemission/DocSuri/actions/runs/38117352822).

Shared lint/tests, accounts/library and summarization tests, frontend dependency
audit/lint/tests/E2E/build, remaining security audits and secret scanning,
declared-image digest verification, isolated Postgres verification and Ops tests
on APFS were not reached. Full PBT was skipped. Matching failure signatures do
not establish full-suite success, security clearance or runtime readiness.
Application source, dependencies and CI workflows were unchanged.

Integration followed CONVENTIONS.md and the user's interim policy. Local
`develop` and `origin/develop` were synchronized to the merge; the completed
local and remote contract branches were deleted. Delivery Planning continues
on `docs/docsuri-v2-delivery-planning`, created from that merge. Main was not
promoted.

## Approved Delivery Planning branch integration

On 2026-10-11, the user approved Delivery Planning and completed Inception.
[PR #39](https://github.com/revenantonthemission/DocSuri/pull/39) merged
`docs/docsuri-v2-delivery-planning` into `develop` at
`93b43f86639c51df1c82bcf919809f9a8d9c5002` on 2026-10-11T07:15:36Z.
The verified head was `50d625ccde5c895e9483760a665a2a2af33786da`; its exact
base was `d1bf16e1ae46e769cffc5b824705135e938687fb`.

The delivery verifier passed eight serial build passes, all 19 dependencies,
70 functional requirement IDs across both traceability records, ten NFR rows,
15 external dependencies, local links and Mermaid syntax. Domain and unit
consistency checks also passed. The three accepted contract findings remain
open with early closure tasks. Operating feasibility remains conditional, and
the construction verification command remains unset pending separate approval
of a runnable v2 check. These results establish planning consistency only.

[PR #39 CI](https://github.com/revenantonthemission/DocSuri/actions/runs/38120547668)
finished with 11 failed jobs, three passed and one skipped. All 11 failure
diagnostics matched the
[exact-base CI](https://github.com/revenantonthemission/DocSuri/actions/runs/38117621096):
230 normalized diagnostic lines matched, with additional complete failed-step
comparisons for shared and frontend. This bounded comparison identified no new
regression. Failures concern existing consumer inventories, lint,
imports/dependencies, native platform fixtures, Postgres setup and audit inputs.
Ingestion, discovery and dependency review passed, as did both
[CodeQL analyses](https://github.com/revenantonthemission/DocSuri/actions/runs/38120547665)
and the [branch-name check](https://github.com/revenantonthemission/DocSuri/actions/runs/38120547664).

Shared lint/tests, accounts/library and summarization tests, frontend dependency
audit/lint/tests/E2E/build, ingestion/ops security audits and secret scanning,
declared-image digest verification, isolated Postgres tests and non-vacuity
verification, and Ops tests on APFS were not reached. Full PBT was skipped.
CI remains failed; this comparison does not establish full-suite success,
security clearance or application readiness. Application source, dependencies
and CI workflows were unchanged.

Integration followed CONVENTIONS.md and the user's interim policy. Local
`develop` and `origin/develop` were synchronized to the merge, and the completed
local and remote Delivery Planning branches were deleted. Functional Design
continues on `docs/docsuri-v2-u1-functional-design`, created from that merge.
Construction retains serial, unit-major execution and no separate walking-
skeleton ceremony as approved in Delivery Planning. The ordinary completion
checkpoint approval choice remains pending. Main was not promoted.

## U1 Functional Design integration

The human subsequently selected Continue automatically for ordinary Construction
completion. U1 Functional Design completed with its confirmed summary, document
checks and independent architecture review. [PR #40](https://github.com/revenantonthemission/DocSuri/pull/40)
merged into develop at `ee2957bac885549d4b5865e8bb939967f0dfbfb3` on
2026-10-11T07:57:22Z. Its verified head was
`ae88e6bff698c969291254dd65ffe08ea6f9facd`, exact base
`93b43f86639c51df1c82bcf919809f9a8d9c5002`.

Validation passed for 21 logical entities, 39 rules, nine workflows, 14 local
checks, 29 U1 FR contributions and all 70 release FR rows, ten NFRs and nine IB
obligations. Mermaid syntax passed. The review found no Critical/Major concerns
and two Minor details: initial empty-glossary revision and immutable acceptance
timestamp. These carry into coordinated contracts before affected code. No
running application, operating feasibility or executable finding closure is
claimed from this design.

[Head CI 38122906293](https://github.com/revenantonthemission/DocSuri/actions/runs/38122906293)
finished with 11 failed, three passed and one skipped job. All 230 normalized
diagnostic lines across its 11 failures matched
[exact-base CI 38120766277](https://github.com/revenantonthemission/DocSuri/actions/runs/38120766277)
(11 failed, two passed, two skipped); shared/frontend complete failed steps also
matched after normalization. No new regression was identified by this bounded
comparison. Ingestion, discovery and PR-only dependency review passed, as did
[CodeQL](https://github.com/revenantonthemission/DocSuri/actions/runs/38122906295)
and [branch naming](https://github.com/revenantonthemission/DocSuri/actions/runs/38122906331).

Shared lint/tests, accounts/library and summarization tests, frontend dependency
audit/lint/tests/E2E/build, ingestion/ops security audits and Gitleaks, image
digest verification, isolated Postgres/non-vacuity checks and Ops APFS tests
were not reached. Full PBT was skipped. CI remains failed; this establishes
neither security clearance nor complete-service readiness. Application source,
dependencies and CI configuration were unchanged.

Integration followed CONVENTIONS.md and the interim policy. Local develop and
origin/develop were synchronized; completed local/remote Functional Design
branches were removed. U1 NFR Requirements continues on the fresh
`docs/docsuri-v2-u1-nfr-requirements` branch from the merge. Enabled summary/plan
confirmations, exact verification-command approval and failure decisions remain
human stops. Main was not promoted.
