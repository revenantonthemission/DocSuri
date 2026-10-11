# DocSuri v2 — Domain Design questions

Date: 2026-10-11 (Asia/Seoul).

## Existing answers and design basis

The approved requirements, revised mockups and all seven earlier question files
were checked. Their answers resolve the product choices needed to propose
logical component boundaries. No new interview question is needed before the
consolidated design summary. A supporting boundary analysis reached the same
conclusion; it was not the formal architecture review.

| Design topic | Basis carried forward | Source |
| --- | --- | --- |
| Capability boundary | Retain all 20 capability groups and 50 functional subrequirements in the first release; defer expansion | [Requirements](../requirements-analysis/requirements.md); [scope answers](../../ideation/scope-definition/scope-definition-questions.md) |
| User journey and presentation | Integrated find → understand → save → revisit experience; public registration, account isolation, administrator boundaries; desktop first with complete responsive web capabilities | [Requirements answers](../requirements-analysis/requirements-analysis-questions.md); [approved mockup answers](../refined-mockups/refined-mockups-questions.md) |
| Visual and interaction consistency | Current blue/neutral colors, Apple HIG adapted to the web, Korean-facing UI, light/dark/system appearance and the WCAG 2.2 AA design target | [Design mapping](../refined-mockups/design-system-mapping.md); [interaction specification](../refined-mockups/interaction-spec.md) |
| Work ownership and recovery | Every persistent business concept has one owner; private content stays owner/context-bound; durable drafts preserve acknowledged revisions separately from committed messages, accepted jobs and saved library work | Requirements FR2/3/5/6/13–16 and NFR3–5/10; interaction specification |
| Integration with the current system | Current modules and dependencies are evidence for retained behavior; they are not a selected v2 implementation, migration policy or deployment topology | [Reference architecture](../../../../codekb/DocSuri/architecture.md), [component inventory](../../../../codekb/DocSuri/component-inventory.md), [dependencies](../../../../codekb/DocSuri/dependencies.md) |
| Operating constraints | $0, free/local only, one human maintainer with agents, risk-first sequence, no fixed deadline; choose quantitative targets after measurement | [Feasibility answers](../../ideation/feasibility/feasibility-questions.md); scope answers |
| Git flow | Working branch → GitHub PR into develop → release promotion to main. The latest instruction says to merge each working branch back into develop when its purpose is fulfilled | [CONVENTIONS.md](../../../../../../../CONVENTIONS.md); user instruction on 2026-10-11 |

The runtime-fix branch was merged through PR #35 before continuing on the new
Domain Design branch. The user clarified that the current pipeline has not been
rewritten and to follow Git flow for now; the interim treatment of confirmed
pre-existing failures is recorded in CONVENTIONS.md and the
[integration record](../../maintenance/develop-integration.md).

## Proposed design approach

Propose responsibility groups for account/access, public corpus/content,
discovery/citations, personal library/history, paper assistance, research work,
personalization/onboarding, topics/digests, approved exports, entitlements/usage,
service operations and controlled platform operations. Describe a shared web
workspace/application composition boundary so these capabilities form the
approved integrated experience. These are logical code boundaries; this stage
does not choose the number of deployed services.

Keep distinct research-question and novelty-analysis lifecycles within the
research-work boundary. Give private attachments and draft revisions an explicit
owner there, while keeping public corpus identity/content separate. Compare this
with separate research and novelty components in the decision records, including
coordination costs and reversibility. The recommendation remains subject to the
Domain Design review and approval.

Reuse common execution and presentation mechanics while retaining one business
owner for each operation's acceptance, status, result and recovery. Model export
preview/approval/effect ownership separately from analysis completion. Make
account revocation/deletion, consent, quota and late-result interactions explicit
without creating mutual module dependencies or competing authoritative records.

## Ambiguity analysis and open evidence

- No conflict was found among the applicable product answers. The later color
  instruction supersedes the earlier fresh-palette preference. The durable draft
  choice elaborates the earlier requirements-review concern; it protects only
  acknowledged saves and does not weaken committed-work protection.
- Anonymous access beyond registration/entry information remains an access-policy
  seam. First derive retained behavior from the reference, as the requirements
  direct; ask only where a genuinely new product policy is needed. Public
  registration alone does not grant anonymous access to every capability.
- Account reactivation, erasure, pending work, draft retention/deletion and backup
  treatment require the existing data/obligation investigations. Identify their
  responsible owners now, but do not invent retention periods or make unresolved
  storage/privacy choices through the component catalogue.
- The reference has bounded deep coverage and unresolved runtime evidence. Four
  paper-job integration defects inform recovery and contract responsibilities;
  they are not behavior to reproduce in v2.
- Stack, hosting, deployment grouping, migration, physical schemas, numeric limits
  and delivery schedule remain dependent on later evidence and decisions. Entity
  entries here will state ownership, identifiers, attribute names and references
  only. Detailed types, validation and relationship cardinality come later.

## Consolidated Summary Confirmation

- Design logical code boundaries for all retained capabilities, centered on the
  integrated paper journey. Propose account/access, corpus/content,
  discovery/citations, library/history, paper assistance, research work,
  personalization/onboarding, topics/digests, approved export, entitlements/usage,
  service operations and controlled platform operations, with a shared web
  workspace that composes their interactions.
- Give each entity and business operation one authoritative owner. Separate
  public paper identity/content from private research attachments and saved
  library references. Keep draft revisions, committed messages, accepted jobs and
  prepared results distinct, with truthful recovery and account isolation.
- Compare the proposed grouping with viable alternatives. Keep research and
  novelty lifecycles explicit; reuse mechanics without creating competing job
  status authorities. Preserve explicit export approval and reconciliation.
- Define component interactions, external integration responsibilities and
  account/consent/deletion effects. Check dependency consistency and cycles.
  Use current code as parity evidence without committing to its implementation.
- Preserve the approved blue/neutral, Apple HIG-informed responsive Korean web
  experience, appearance modes and accessibility target. Keep navigation,
  search context, acknowledged drafts and job feedback coherent across screens.
- Produce the component/entity catalogue and diagram, architecture decision
  records and requirement-to-component traceability, then obtain an independent
  architecture review. No deployable-unit grouping, stack or physical schema is
  selected in this stage.
- Keep the $0 free/local constraint and one-maintainer model. Existing users/data,
  backups, obligations, capacity, anonymous-access detail, retention/deletion,
  migration and quantitative quality decisions remain explicit evidence work.
  Follow CONVENTIONS.md and merge completed working branches into develop through
  PRs; release promotion to main remains separate.

Does this all look correct before I generate the artifact?

- Looks correct
- Request changes

[Answer]: Looks correct
