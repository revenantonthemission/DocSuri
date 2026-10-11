# DocSuri v2 — Units of work

Date: 2026-10-11 (Asia/Seoul). Basis: the approved eight-unit plan and confirmed
[generation summary](units-generation-questions.md#consolidated-summary-confirmation).
These documents await the Units Generation artifact review and approval.

## Purpose and scope

Define construction boundaries for the complete v2 rebuild. All 20 retained
capability groups, 50 functional subrequirements and ten NFRs remain required.
The first complete product demonstration is finding → understanding → saving →
revisiting a paper; it is not the release boundary. Unit completion requires
the unit's implemented behavior and evidence, not only its design files.

The [domain catalogue](../domain-design/components.md) continues to own all
13 logical components and 42 entities. Units are increments of implementation
and verification within those owners, not eight new business authorities.
The [architecture decisions](../domain-design/decisions.md),
[requirements](../requirements-analysis/requirements.md), approved
[interaction specification](../refined-mockups/interaction-spec.md) and
[design mapping](../refined-mockups/design-system-mapping.md) constrain each unit.

## Unit catalogue

Directory values are stable construction-record directory names, not a selected
application source layout. `service` denotes an executable deliverable;
`library` denotes embedded code with no independently operated runtime. A unit
kind sets the normal design-artifact scope; it never removes applicable product,
UI, data, security, recovery, accessibility or operational requirements.

| Unit ID | Directory | Kind | Deployment model | Relative complexity | Delivered boundary |
|---|---|---|---|---|---|
| U1 | u1-integrated-paper-journey | service | shared | XL | Runnable application foundation and complete paper-journey demonstration |
| U2 | u2-account-personal-controls | library | embedded | L | Complete account, personal-library, consent, personalization and entitlement controls |
| U3 | u3-paper-corpus-capabilities | library | embedded | XL | Complete public corpus, discovery/citations, reading and paper-assistance capabilities |
| U4 | u4-research-novelty | library | embedded | XL | Private research, evidence, durable drafts and distinct research/novelty workflows |
| U5 | u5-topics-digests | library | embedded | M | Topic subscriptions and recoverable digest delivery |
| U6 | u6-approved-export | library | embedded | M | Owner-authorized Notion connection, preview and reconciled export |
| U7 | u7-controlled-platform-protocols | service | standalone | L | Controlled operator executable, platform evidence and durable protocol receipts |
| U8 | u8-service-operations-integration | service | shared | XL | Complete application assembly, operations and cumulative recovery/repair verification |

Complexity compares uncertainty and integration surface, not duration, staffing,
spending or a delivery promise. U1 includes a real model/understanding path and
durability, so a thin user journey is not assumed to be small implementation
work. U3 has broad source/index/model recovery obligations; U4 has private-input
and concurrent lifecycle risk; U8 must exercise the whole service. Evidence may
change these estimates during Delivery Planning without changing capability scope.

## Shared release and composition responsibilities

U1 and U8 produce successive assemblies of **one application release**. U1 is
the runnable initial assembly; U8 is the complete assembly. They do not require
two permanent application services. U2–U6 contribute embedded domain code,
adapters and relevant views. U7 retains a separate controlled operator boundary.
Languages, frameworks, stores, host placement and worker processes remain open
until the applicable evidence and later design decisions support them. A
resource-intensive execution process may be separated within the application
release without turning every module into an independently deployed service.

Construction dependencies describe which contract or implementation a change
requires. They are not a second runtime call graph. An implementation introduced
by U1 may be extended by U2 or U3 while its authoritative component remains the
same. Do not create parallel account stores, paper registries, usage ledgers or
job authorities merely to keep unit source trees disjoint.

| Source/composition responsibility | Accountable unit and constraint |
|---|---|
| Initial host, public extension interfaces and baseline application assembly | U1 defines server/browser composition, safe error/status presentation, current-owner context and module registration interfaces. The initial application runs without importing U2–U7 implementations. |
| Embedded contribution and its real integration assembly | Each of U2–U6 owns its domain changes, adapter wiring, view contributions and mounted integration checks against U1's host. A contribution is not complete from isolated library tests. |
| Complete application entrypoint and registration manifest | U8 composes the completed contributions and platform evidence adapter. This is the final version of the application's composition, not a new business owner or second production application. |
| Independent operator entrypoint | U7 owns its actor/target authority, executable interface, controlled effects and evidence/receipt interface. Application login does not implicitly authorize operator effects. |
| Shared source changes | The implementing unit identifies the affected component, current files, consumers and tests before editing. Contract changes require compatibility/impact checks and updates to consumers; no duplicate replacement contract may silently diverge. |
| Construction source layout and manifests | Functional/Contract Design and Code Generation resolve concrete language-appropriate paths and declare ownership for each change. Unit record directories are not instructions to duplicate application modules under eight repositories. |

The minimum extension contract includes contribution identity/version,
dependencies, capability/readiness reporting, route/view registration, current
principal/consent access, lifecycle participant registration and safe observation
hooks. Contract Design chooses exact signatures and compatibility behavior.
The host rejects missing/incompatible required registrations explicitly. It must
not invent healthy capabilities from absent modules. Registration mechanisms
are trusted application composition, not an externally installable plugin feature.

U2–U6 each run their contribution in a real assembly with the necessary earlier
contracts, even before U8 exists. U8 then verifies the full combination and
cross-capability effects. This makes integration evidence available throughout
construction without creating a core-to-future-module dependency. Reusable
mechanics preserve operation-specific lifecycle and authorization authorities.

## Component responsibility across increments

The first column names the existing authoritative owner. The other columns
assign work, not additional ownership. U8's cumulative checks do not transfer
entities out of their component.

| Component | Initial responsibility | Completion/extensions | Composition and verification |
|---|---|---|---|
| AccountAccess | U1: verified synthetic registration/login/logout, current owner/session checks and minimum safe lifecycle interface | U2: full retained credentials, external identities, MFA, consent and lifecycle outcomes; consumers implement their own participant duties | U8: complete participant and cross-capability revocation/restore checks |
| CorpusContent | U1: permitted fixture paper/version/content loading and current eligibility | U3: all retained ingestion, refresh, canonicalization, withdrawal, rebuild and recovery behavior | U8: corpus/search/content/library consistency and restore checks |
| Personalization | U1: safe default/manual entry needed by the anchor journey | U2: settings, recent activity, consent-governed projections, reset and onboarding | U3 consumes complete permitted projection/default behavior; U8 checks integration |
| Discovery | U1: real research-query lookup over identified eligible fixtures | U3: complete lexical/semantic/refinement/citation and degraded-state behavior | U4/U5 consume the eligible-source contracts; U8 checks full integration |
| Library | U1: confirmed owner-bound paper/query saves and revisit | U2: full saved search, history, remove/clear and concurrency controls; U3 supplies corpus identity/withdrawal dispositions | U8 verifies cross-source and owner lifecycle cases |
| UsageEntitlements | U1: bounded workload and stable accounting references for accepted anchor work | U2: complete inspection, grants/revocation, reset/accounting policy and current authorization contract; each operation owner reconciles its own effects | U8 verifies cross-operation races and resource exhaustion |
| PaperAssistance | U1: actual supported understanding path, recoverable job/progress and prepared-result read | U3: all supported summary/translation choices, glossary, eligibility and terminal/recovery behavior | U8 checks mounted browser/service/executor/result consistency |
| ResearchWorkspace | U4: authoritative private attachments, drafts, research sessions/turns, novelty and evidence | U4 completes its distinct internal workflows; U6 consumes an authorized immutable artifact revision contract | U8 checks full private-work isolation, deletion and recovery |
| TopicsDigests | U5: subscription and delivery lifecycle | U5: current-consent/unsubscribe checks and uncertain-send reconciliation | U8 checks full-service behavior and operational evidence |
| ApprovedExport | U6: connection, explicit approval and remote-effect authority | U6: exact preview/revision/destination binding and uncertain-outcome reconciliation | U8 checks combined analysis/export/deletion and recovery cases |
| PlatformControl | U7: independent operator authority and controlled executable | U7: complete retained protocol membership, evidence and receipts | U8 consumes bounded evidence/recovery contracts without acquiring platform authority |
| ServiceOperations | U1: essential capability signals and diagnosable anchor failures; every contribution supplies observations | U8: complete incident/resource/grounding/reliability views, authorized recovery and readiness | U8 verifies outcomes through owning domains; observations alone are not service readiness |
| WebWorkspace | U1: shared shell and complete anchor interaction | U2–U6: coherent views for their retained capabilities using the same design and host contracts | U8: full composition, navigation/focus/context consistency and accessibility verification |

## Unit definitions and acceptance boundaries

### U1 — Integrated paper journey

Deliver a runnable executable with real server, browser, persistence and accepted
work execution through whichever free/local technology is later approved. Use
authorized fixtures for the documented P1/P2 tasks; record eligibility,
configuration and actual execution. A static screen, mocked answer or no-op
dispatcher cannot pass the journey. A local email sink demonstrates a local
registration test only; intended public integration needs separate real evidence.

Include the necessary slices of account access, safe entry/onboarding defaults,
corpus identity/content, discovery, paper assistance, usage control, library,
shared presentation and operations. Demonstrate a research query, useful
source-associated understanding, acknowledged save, fresh authenticated revisit
and prepared-result retrieval without silently starting another job. Exercise
second-account denial, lost save acknowledgement, interrupted stream and
service/executor restart. Record baseline observations without inventing targets.

This establishes host and domain contracts consumed later; the remaining modes,
providers, lifecycle policies and fine-grained capability set stay explicitly
assigned to later units. The initial participant list covers actual persisted
owners; absent future features are not falsely reported as complete. Every new
owner expands that list before its data can be persisted. Existing data is not
reset or migrated simply to make the demonstration run.

### U2 — Account and personal controls

Complete AccountAccess, Personalization, Library and UsageEntitlements duties,
including public authentication abuse controls, credential/email changes,
Google/ORCID linking, administrator MFA, profile/consent, deletion/reactivation,
onboarding, personal defaults, recent activity, history and quota administration.
Preserve existing mock subscription presentation without introducing billing.
U1's initial entities evolve under the same owners rather than being copied into
a second account or library system.

Supply complete lifecycle request/participant acknowledgement, current consent
and entitlement contracts to later contributions. U2 verifies these with the
owners already present; later units add and test their own participants, and U8
checks manifest completeness across all owners. U2 must not claim complete
erasure for future features or edit those future owners' data itself. Retention,
reactivation, backup and draft policy must be settled before affected behavior.

Exercise successful and denied provider callbacks, revoked sessions, replayed
identity challenges, cross-owner access, concurrent saved-work updates, delayed
history/profile facts, and accounting uncertainty. U3's canonicalization and
withdrawal contracts support final saved-reference integration; U2 can verify its
side against the common contract without importing U3 implementation.

### U3 — Complete paper and corpus capabilities

Complete CorpusContent, Discovery and PaperAssistance, with their WebWorkspace
views and the reference's retained public-paper actions, filters, modes,
languages/presentation levels, glossary, citations, assets and source-only or
unavailable-content states. Reconcile the fine-grained parity ledger instead of
assuming a parent FR covers every currently supported behavior.

Implement refresh, rebuild, deduplication, version/canonical identity, withdrawal,
retry and reprocessing with coherent object/control/index outcomes. Contract
Design must resolve the accepted projection-writer finding: identify the writer,
compatibility contract and publication/rebuild completion evidence, including
withdrawal propagation. The catalogue's ownership remains unchanged; this
document assigns the clarification, not a particular index or transport.

Prove mounted progress framing/recovery, actual dispatch, prepared-result shape
and read semantics against the four known job defects. Exercise source changes,
partial writes, index/model incompatibility, quota races and provider limits.
Publish the complete eligible-source/retrieval contracts consumed by U4/U5;
saved references continue to belong to Library in U2.

### U4 — Research and novelty

Implement ResearchWorkspace and its UI contributions: grounded questions,
comparison/quotation evidence, supported private attachments and web references,
committed sessions/turns, distinct novelty modes/jobs/results/discussion, and
durable owner-bound drafts. Do not imply that an optional web reference was read
or treat source text as authorization. Keep public corpus identity and private
attachment identity separate.

Resolve draft retention/deletion, storage and shared-device isolation before
implementing persistence. Recover only acknowledged revisions after restart and
authentication; never silently resubmit. Test newer edits against consumption of
an older submitted draft, conflict resolution, account changes, late writes,
session deletion and cancellation/completion races. Committed work and accepted
jobs retain their own authorities.

Provide the eligible novelty artifact and immutable revision/content identity
contract consumed by U6. The accepted export-source finding is not closed until
the source and consumer agree on that identity and its executable checks.
Full grounded-answer/novelty acceptance includes useful source-associated output,
contradictory/insufficient evidence and actual extraction/model failures; mocks
alone cannot establish normal-path parity.

### U5 — Topics and digests

Implement TopicsDigests with persisted topic follow/unfollow, digest settings,
content-window selection, delivery outcomes and unsubscribe. Consume eligible
source/retrieval and current consent/lifecycle contracts, with truthful empty or
unavailable inputs. Supply its account-lifecycle participant and operational
observations through the common interfaces.

Test scheduling/time-zone boundaries, retries, crashes around remote send,
uncertain outcomes, unsubscribe after queueing and late consent changes.
Verify a sustainable free/local real delivery path for public operation. A test
sink remains useful fault-injection evidence but cannot stand in for that path.

### U6 — Approved export

Implement ApprovedExport and its UI contribution for per-owner Notion connection,
current preview, destination selection, explicit approval and reconciled external
effect. Consume U4's authorized source revision and U2's current authority.
Analysis completion, preview display, cancel or result reopening must not cause
an export. Changed source content/destination or revoked authority must prevent
execution under an obsolete approval.

Resolve the upstream artifact-revision finding jointly with U4 in Contract
Design; use the same identity in preview, approval and execution evidence. Test
other-owner access, secret handling, timeout after remote success, duplicate
execution, disconnected provider and unknown outcome. Preserve external-copy
versus-local-deletion distinctions in the approved policy. Verify retained
integration under sustainable free terms; this unit does not authorize sending
real user exports during planning or bypass explicit effect approval in tests.

### U7 — Controlled platform protocols

Deliver the retained operator executable with independent actor/target authority,
platform evidence/compatibility, precondition validation and durable outcome
receipts. Reconcile actual protocol membership and native-platform requirements
from the reference before declaring parity. Do not replace native filesystem or
credential semantics with mocks and claim equivalence.

Exercise safe fixtures for wrong actor/target, stale evidence, changed input,
interrupted execution, duplicate effects, disk exhaustion and permission failure.
Destructive or release effects still require their applicable explicit operator
authority. This unit is independently executable; its graph has no application
prerequisite merely to force a build sequence. U8 consumes its bounded evidence
interface, not a blanket privilege to invoke every operation.

### U8 — Complete service operations and integration

Deliver the complete application assembly, registration/participant manifests,
ServiceOperations capabilities, authorized operational views and recovery
procedures. Integrate all WebWorkspace contributions as one coherent experience:
shared navigation/search context, focus, owner transitions, status, draft and
result feedback, approved colors, Korean text, responsive layouts and appearance
modes. Finish actual keyboard/assistive-technology, reflow and contrast evidence;
mockups alone do not establish WCAG 2.2 AA conformance.

Verify all requirement rows cumulatively, including mounted feature combinations,
private/public boundaries, current-account checks, lifecycle acknowledgements,
late effects, reference withdrawal and controlled restore. Demonstrate diagnosis
and repair of a representative defect from a clean checkout, with regression and
affected integration checks. Readiness reports failed, missing, stale and unknown
capabilities honestly; liveness and platform receipts are insufficient alone.

Close or explicitly escalate the evidence conditions before affected release:
full parity, agreed quality targets, sustainable $0 capacity, user-approved
continuity/migration, backups/restore and maintainer procedures. A cumulative
test pass cannot waive an unresolved required condition. Dedicated later CI/CD
and deployment stages retain their responsibilities; U8 supplies a reproducible
application and verification entrypoints, not an authorization to release.

## Evidence prerequisites and downstream work

These conditions constrain affected work, including U1. They are not placed
only in U8 after irreversible choices have already been made. The
[scope backlog](../../ideation/scope-definition/intent-backlog.md) carries
the discovery and closure evidence; this decomposition allocates consumers.

| Evidence or decision | Affected units and required handling |
|---|---|
| IB-01 capability and external-consumer reconciliation | All units refine their retained behaviors and contract expectations; U8 rejects unexplained omissions in full parity. |
| IB-02 authoritative users/data and recoverable backups | Every unit that persists or changes data; establish inventory/restore and obtain continuity decision before migration. Isolated synthetic development does not decide existing-user treatment. |
| IB-03 integration, privacy, source and location obligations | U1–U6/U8 before affected copying, model use, email, export, storage or hosting; U7 for retained operational data/authority. Record unresolved facts without making legal claims. |
| IB-04 baseline and numeric quality agreement | U1 provides the anchor's executable measurements; all units supply relevant cases; U8 verifies agreed targets. No numeric defaults are invented here. |
| IB-05 sustainable free/local capacity | All required paths, including real registration/email, model work, search, export, storage and operations; complete enough evidence before choosing affected technology or public operating limits. |
| Draft retention/deletion and shared-device treatment | U2's lifecycle contract and U4's persistence, with U6/U8 effects and restore implications; acknowledged recovery alone does not select a policy. |
| Accepted projection-writer and export-revision findings | U3 and U4/U6 respectively carry explicit Contract Design closure tasks; see the [Domain Design review](../domain-design/reviews/review-01.md). No resolution is claimed at unit assignment. |
| IB-06–IB-09 comprehensibility, anchor, parity and release proof | These span actual construction, integrated validation and later delivery/release stages. Completing these documents closes none by itself. |

## Alternatives and consequences

The approved eight-unit approach balances reviewable increments with one shared
application release. Its main cost is precise composition and shared-source
responsibility. The four-unit alternative reduces coordination but concentrates
remaining researcher work into a very large review and repair surface. A
component-per-service alternative adds inter-service failure modes and operation
cost without measured $0 capacity justification. None changes the retained
capability boundary; the chosen plan favors the current one-maintainer model.

Dependency independence is documented in [the DAG](unit-of-work-dependency.md),
not converted here into a recommended economic build order or critical path.
The active plan adds no walking-skeleton ceremony at this stage. Delivery
Planning consumes the DAG and risk-first evidence obligations, confirms demos
and verification, and proposes work batches under the recorded serial execution.

Follow [CONVENTIONS.md](../../../../../../../CONVENTIONS.md): working branches
merge through PRs into develop when complete, with the documented interim
legacy-CI policy; promotion to main remains separate. A planning approval does
not authorize spending, migration, destructive platform actions or publication.

## Coverage and verification limits

[The requirement map](unit-of-work-story-map.md) names a primary completion
responsibility and participating units for every upstream FR. Parent IDs group
their children's responsibilities; they are not extra implemented features.
[traceability.json](traceability.json) mirrors those assignments. `OK` means a
valid assignment, not accepted runtime behavior. No user-story artifact was
produced, so stable FR IDs are the enumeration source.

Validate unit identities/kinds, component coverage, DAG/diagram parity,
traceability and source links before independent review. These checks prove
document consistency only. Unit construction, complete-task performance,
recovery, accessibility and full-service acceptance remain to be demonstrated.
