# DocSuri v2 — Requirements Analysis questions

Date: 2026-10-11 (Asia/Seoul).

## Context and carried-forward decisions

The user approved Reverse Engineering. Its inventory supplies 20 capability
groups for detailed requirements; source presence does not prove live operation
or complete capability parity. The four paper-job integration defects must be
resolved through intended-behavior acceptance criteria, not preserved as desired
behavior. [RE] [CQ]

Previously answered questions were checked before preparing this file. These
decisions remain settled and are not reopened:

- Retain all current product capabilities in the first v2 release, including
  account, research, export and maintainer/operational capabilities. Defer new
  feature expansion. The paper journey alone is not release completeness. [IC] [SC]
- Serve researchers and engineers who need to find and understand papers;
  anchor the experience in find → understand → save → revisit. [IC]
- Prioritize stable, smooth use and comprehensible, repairable files and code.
  Measure task success, responsiveness, interruption recovery and defect
  reproduction/repair before agreeing numeric targets. [IC] [SC]
- Keep the budget at $0 with free or local stacks, one human maintainer with
  coding agents, no fixed deadline and no mandatory technology/provider. [FQ]
- Follow risk-first sequencing. Determine authoritative users, saved data and
  recoverable backups before choosing continuity or migration. Investigate
  obligations before hosting/data-handling choices. [SC] [IB]
- No external integration commitments are known beyond current capabilities;
  actual dependencies and consumers still require investigation. [FQ]
- The user decides scope and priorities. Git follows CONVENTIONS.md: working
  branch → PR into develop → release promotion to main. [SC]

The declared Standard depth is retained. Two questions address new user-facing
choices; prior answers cover the other business and constraint topics. Technical
corner cases will be carried into testable requirements or explicit assumptions,
without asking the user to guess implementation behavior or measurements.

## Q1. What access model should the first v2 release support?

The current capability inventory includes registration, personal accounts,
owner-scoped saved work and administrator functions. This question concerns who
may enter the service, not a hosting provider, deployment permission or removal
of any capability. All choices retain account and data-isolation capabilities;
resource feasibility still needs evidence.

A. A multi-user web service with public registration.
B. A multi-user web service initially limited to invited users; retain the full capability set.
C. Keep multi-user capabilities required, but decide public versus invited access after free/local capacity and operating evidence are available.
X. Other (please specify)

[Answer]: A multi-user web service with public registration.

## Q2. What research example should guide the first end-to-end acceptance checks?

The agreed journey is finding a relevant paper, understanding it, saving it and
returning later. A reference task makes those checks concrete. If supplying an
example, include a topic or query, an optional paper, and what the reader should
learn. Public or synthetic fixtures can avoid exposing private material. This
does not replace verification of the remaining capabilities or claim user
research has been conducted.

A. Choose and document representative public-paper tasks; I have no particular example to supply now.
B. I will provide a research topic, query or paper and the outcome I want the reader to understand.
X. Other (please specify)

[Answer]: Choose and document representative public-paper tasks; I have no particular example to supply now.

## Evidence and decision dependencies

The approved backlog assigns environment authority, aggregate users/data,
backup restoration, resource capacity, free-service terms, obligations and
baseline measurements to evidence work. These are not answered by the two
preferences above. No migration, destructive data action, paid fallback,
numeric quality target, platform choice or delivery-feasibility conclusion is
inferred from this questionnaire. [IB]

Requirements will trace all CAP-01–CAP-20 groups to preserved outcomes, with
happy-path and failure/recovery acceptance criteria. Existing mock subscription
presentation and plan administration must not be expanded into a real payment
system. Unsupported readiness claims, missing queue dispatch, incompatible
state/results and malformed progress events inform explicit verification work.
[RE] [CQ]

## Sources

- [desc] Initial description: "Now that we cleaned up our codebase, let's start making a new version of DocSuri service from the beginning. Our highest priority is to make a stable, smooth user experience. Also, the codebase should be structured cleanly not only from the file perspective, but also from the code perspective so that the codebase is comprehensible and repairable."
- [IC] [Approved intent](../../ideation/intent-capture/intent-statement.md) and its [answers](../../ideation/intent-capture/intent-capture-questions.md).
- [FQ] [Feasibility answers](../../ideation/feasibility/feasibility-questions.md), including the later $0 instruction.
- [SC] [Approved scope](../../ideation/scope-definition/scope-document.md).
- [IB] [Approved backlog](../../ideation/scope-definition/intent-backlog.md), IB-01–IB-09.
- [RE] [Business overview](../../../../codekb/DocSuri/business-overview.md), CAP-01–CAP-20; [architecture](../../../../codekb/DocSuri/architecture.md); [code structure](../../../../codekb/DocSuri/code-structure.md).
- [CQ] [Code-quality assessment](../../../../codekb/DocSuri/code-quality-assessment.md), Q-01–Q-08, with source-versus-executed evidence distinguished.
- [Git conventions](../../../../../../../CONVENTIONS.md).

## Answer analysis

Q1 selects a multi-user web service with public registration. It establishes the
intended access model; public hosting, sustainable capacity and deployment
readiness still require their own evidence. Q2 delegates selection of documented
public-paper tasks to the agents. It does not leave a user-supplied example
pending. Neither answer contradicts the approved scope or requires a follow-up.

The requirements will separate preserved outcomes, source-observed defects,
proposed acceptance criteria and unresolved evidence. Conditions that affect
public registration, ownership, sessions, asynchronous work, storage, external
dependencies and generated research output will receive explicit pass/fail
behavior. Exact quantitative limits remain dependent on the approved baseline
and target-setting sequence.

## Consolidated Summary Confirmation

- Build a multi-user web service with public registration for researchers and
  engineers. Preserve personal accounts, administrator boundaries and isolation
  of each user's saved work and private material.
- Retain all current capabilities in the first v2 release. Map the 20 discovered
  capability groups into traceable requirements covering discovery, reading and
  AI assistance, library/history, accounts/preferences, citations, research and
  novelty, approved exports, quotas and operations. Defer new feature expansion;
  existing mock subscription behavior is not a real billing requirement.
- Prove find → understand → save → revisit first. Agents will choose and document
  public-paper tasks with queries, source references, expected useful outcomes
  and repeatable checks. These supplement the full capability-parity checks and
  do not claim validation by actual users.
- Define observable happy-path, error and recovery criteria, including truthful
  job progress/results, retry and duplicate handling, interrupted sessions,
  unavailable dependencies, failed writes, ownership checks and accessible
  interaction. Carry the four confirmed paper-job integration defects into
  acceptance work without prescribing the old implementation as v2's design.
- Prioritize stable, smooth use and comprehensible, repairable code. Measure
  complete-task success, responsiveness, interruption recovery and defect
  reproduction/repair before agreeing numeric quality targets. Source presence
  and isolated tests do not establish complete readiness.
- Keep the budget at $0 with only free or local stacks, one human maintainer
  supported by coding agents and no fixed deadline. Verify public-service
  capacity and behavior at resource limits; retain the risk-first order and
  bring evidenced conflicts back to the user without silent scope cuts or paid
  fallback.
- Establish authoritative users, data and recoverable backups before selecting
  continuity/migration. Investigate obligations and current integrations before
  affected hosting or data-handling choices. Stack, hosting, migration, numeric
  targets and schedule remain open until their required evidence is available.
- The user remains the sole scope and priority approver. Keep concise updates
  and clear review summaries. Follow CONVENTIONS.md: working branch → PR into
  develop → release promotion to main.

Does this all look correct before I generate the requirements artifact?

- Looks correct
- Request changes

[Answer]:
