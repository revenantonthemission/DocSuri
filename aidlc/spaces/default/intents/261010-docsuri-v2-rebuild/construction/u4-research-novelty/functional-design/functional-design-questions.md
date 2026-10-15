# DocSuri v2 — U4 Functional Design proposal

Date: 2026-10-16 (Asia/Seoul).
Unit: `u4-research-novelty`.

## Context and carried-forward decisions

The workflow resumes Construction on the current working branch
`feature/docsuri-v2-u2-account-personal-controls`, which carries the integration
assembly: U1 (PR #44, commit `1c2cbd5c`), U7 (PR #45, `5fbccc1f`), and the
completed U2 contribution whose checkpoint was approved on 2026-10-15; U3
(`u3-paper-corpus-capabilities`) completed its unit checkpoint on 2026-10-16
(verified against the recorded Construction Verification Command, approved under
the record's autonomous checkpoint policy). The U2/U3 PR handoffs into `develop`
under CONVENTIONS.md remain separate human steps; this proposal is a design
record and changes no application behavior.

The approved unit catalogue assigns U4 the completion of **ResearchWorkspace**
and its WebWorkspace views: private research, evidence, durable drafts and the
distinct research/novelty workflows. U4 is the **full-scope lead** for FR2.3 and
FR13–FR15 (with every subrequirement), and a **contributor** to FR6/FR6.3,
FR8/FR8.1, FR16/FR16.1–16.2, FR17/FR17.2, FR19–FR19.3, NFR5 and IB-03/IB-07. The
shared component owners remain authoritative; U4 is an embedded library
contribution to the same application release, not another research service.

Earlier answers already establish, and this design inherits:

- A multi-user web service with public registration, Korean desktop-first and
  responsive workspace, inherited blue/neutral palette, Apple HIG web
  adaptations, Light/Dark/System and the WCAG 2.2 AA target.
- A $0 budget: free/local providers only, no paid fallback, no hidden fallback —
  unresolved evidence blocks the affected choice rather than the whole unit.
- One human maintainer with coding agents, serial construction, automatic
  ordinary completion checkpoints, and existing human stops (plans, summaries,
  verification-command selection, failures).
- U3 owns public corpus identity, eligibility and retrieval (`C04`/`C05`);
  U2 owns accounts, consent, lifecycle acknowledgements and entitlement
  accounting (`C02`/`C03`); U4 consumes those contracts and owns private inputs.
- CONVENTIONS.md governs Git: working branch through a PR into `develop`.

Two upstream decisions bind this design and are **not** re-opened here:

1. **Contract C07** already fixes U4's operation surface, invariants, checks and
   the `ResearchTurnOrDiscussion`, `NoveltyAnalysis` and `DraftRevision` state
   machines. The functional specification must make those ordered behaviours
   explicit for this unit; it may not contradict them.
2. **Domain design** already fixes the `ResearchWorkspace` entity set
   (`ResearchSession`, `ResearchTurn`, `NoveltyAnalysis`, `ResearchArtifact`,
   `EvidenceRecord`, `PrivateAttachment`, `DraftRevision`) and their references
   to `Account`, `PaperVersion` and `UsageRecord`.

One upstream obligation remains open and must be carried, not silently closed:

- **Durable-draft policy.** C07 blocks durable draft persistence, restore,
  discard and consumption with `POLICY_UNRESOLVED` until retention, erasure,
  storage and shared-device policy is resolved (NFR5; IB-02/IB-03). The design
  must specify the correct *behaviour* under that suspension, and must not
  promise recovery the policy has not authorized.
- **Export source revision identity.** The accepted Minor finding ("export
  source revision identity", U4 and U6 with U8 cumulative checks) is not closed
  until U4 and U6 agree on the immutable artifact revision/content identity and
  its executable checks. This design must state U4's side of that contract.

## Proposed design coverage

| Area | Functional design responsibility |
|---|---|
| Research context | Server-assigned private context that binds owner and context for drafts, uploads, sessions and novelty steps; not a user-visible product feature or a job (`createResearchContext`; C07). |
| Research sessions | Owner/context-bound session create, read, owner-only snapshot listing and deletion with a durable tombstone; reopen returns committed turns and authoritative pending state and never submits work (FR14.1–14.2; C07 `createResearchSession`–`deleteResearchSessions`). |
| Grounded questions and evidence | One immutable turn/input/scope snapshot per accepted question; claims and literal quotations carry `sourceIdentity`/`sourceVersion`/`location`/`coverage`/`provenance`; contradictions and insufficient evidence are distinguished, with meaningful abstention rather than invented support (FR13, FR13.1, FR13.3; `EvidenceRecord`; C07 `acceptResearchTurn`/`readResearchTurn`). |
| Private attachments and web references | Owner/context-bound upload permit, verified bytes/hash/media, truthful malformed/oversized/truncated/password-protected/unsupported dispositions, recoverable extraction, authorizable per-asset reads, and public-corpus-route isolation; an optional web reference is never presented as evidence the analysis actually read, and extracted text is untrusted data (FR2.3, FR13.2; `PrivateAttachment`; C07 `beginPrivateAttachment`–`readPrivateAsset`). |
| Failure and limitation behaviour | Malformed model output cannot become a successful result; truncation/partial coverage is disclosed; interruption and retry preserve committed inputs and prevent duplicate accepted work (FR13.3; C12 adapter envelope; C14 delivery). |
| Durable drafts | Immutable acknowledged revisions with base-revision CAS, conflict without silent overwrite, consumption of exactly the submitted revision with newer edits preserved, discard under CAS, and restore of only acknowledged unconsumed revisions after same-owner authentication — all suspended with `POLICY_UNRESOLVED` until the retention/storage/shared-device policy resolves (FR14; `DraftRevision`; C07 `saveDraft`/`restoreDraft`/`discardDraft`). |
| Novelty analysis and discussion | Distinct topic/manuscript novelty job with immutable input and scope snapshot; separate discussion job bound to the same owner's eligible immutable result that neither reruns analysis nor approves export; cancellation/completion races with exactly one authoritative terminal outcome and no resurrection; owner-scoped artifacts with declared expiry and no automatic export (FR15.1–15.2; `NoveltyAnalysis`/`ResearchArtifact`; C07 `acceptNoveltyAnalysis`–`readResearchArtifact`). |
| Export source identity | Immutable `artifactId`/`revision`/`contentHash` tuple for ready novelty results, revalidated for current eligibility at export read; changed bytes require a new revision (FR16.1–16.2; C07 `readNoveltyArtifactForExport`). |
| Shared browser surfaces | Research workspace and novelty views over the approved Korean responsive/accessibility contract; untrusted browser state, acknowledged-versus-pending-versus-failed display, account-bound rendering cleared on switch/logout, presentation reads that never create jobs (NFR2/NFR6; C13). |
| Contributor boundaries | U4's side of FR6.3 acknowledgement, FR8.1 consent recheck, FR17.2 accounting reconciliation, and FR19 capability/health signals, without claiming closure of U2/U8-owned rows (C02/C03/C12/C14). |

## Open decisions

These are the genuinely open business decisions this design must record. The
first is a carried upstream obligation; the rest are unit-local choices that the
contracts leave to this unit.

1. **Durable-draft and private-data policy (carried, blocking).** C07 requires
   `POLICY_UNRESOLVED` until retention, erasure, storage and shared-device
   policy is resolved. Proposed treatment: design the full lifecycle and specify
   that durable draft operations refuse with an explicit policy-unresolved
   outcome until the policy exists; do not claim draft recovery, shared-device
   isolation or erasure completeness before then.
2. **Private attachment envelope (proposed).** One bounded per-owner size cap
   and an explicit media allowlist (text and PDF first), extraction treated as
   untrusted, no public publication, and typed refusals for malformed,
   oversized, truncated, password-protected and unsupported input.
3. **Optional web references (proposed).** A web reference is stored as a
   reference the owner supplied; the design records it as *not read* unless a
   permitted retrieval actually happened, and never lets retrieved text authorize
   an external action.
4. **Novelty assessment scale (proposed).** Any optional assessment uses a
   recorded method scale with `minimum <= score <= maximum` and existing
   evidence IDs; a score is never presented as proof of scientific novelty.
5. **Artifact expiry (proposed).** Novelty results and their discussion retain
   owner-scoped declared expiry; expiry is disclosed and reads never regenerate
   work or trigger export.

## Consolidated Summary Confirmation

- Complete U4's private research and novelty capabilities within
  ResearchWorkspace and its WebWorkspace views, consuming U2's account/consent
  and U3's public corpus/retrieval contracts. Retain the $0 free/local
  constraint and every current capability.
- Specify research contexts, owner/context-bound sessions with durable
  tombstones, grounded questions and evidence with literal-quote verification,
  contradiction/insufficient-evidence abstention, and private attachments and
  optional web references with truthful untrusted-source handling.
- Specify durable drafts as immutable acknowledged revisions with CAS conflict
  behaviour, exact-revision consumption that preserves newer edits, and
  same-owner restore — suspended under `POLICY_UNRESOLVED` until the retention,
  erasure, storage and shared-device policy is resolved.
- Specify novelty analysis and discussion as distinct durable jobs with exactly
  one authoritative terminal outcome across cancellation/completion races, no
  resurrection, owner-scoped expiring artifacts and no automatic export, and
  state U4's side of the immutable export source-revision identity contract
  consumed by U6.
- Specify failure behaviour across extraction/model/context limits, disclosed
  truncation, interrupted and duplicate requests, and truthful limitation
  reporting; mocks alone cannot establish normal-path parity.
- Extend the approved Korean responsive workspace, appearance modes and
  accessibility target across the research and novelty flows; browser state is
  untrusted and presentation reads never create work.
- Produce entity/rule models, behavioral and frontend specifications and U4
  traceability, check consistency and obtain independent architecture review.
  Continue serially with automatic ordinary completion and the existing human
  decision points. Merge completed branches through PRs into `develop` under
  CONVENTIONS.md; main promotion remains separate.

Does this all look correct before I generate the artifact?

- Looks correct
- Request changes

[Answer]:
