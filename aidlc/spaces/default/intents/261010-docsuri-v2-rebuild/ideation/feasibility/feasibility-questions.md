# DocSuri v2 — Feasibility questions

## Carried-forward decisions

- Retain all current product capabilities; defer new feature expansion.
- Prioritize stable, smooth use and comprehensible, repairable code.
- Anchor verification in finding, understanding, saving, and revisiting a paper.
- Measure the baseline before agreeing numeric success targets.
- The user decides scope and priorities; there are no other named approvers.
- Inspect existing users and saved data before choosing continuity or migration.
- Follow `CONVENTIONS.md`: working branches → PR into `develop` → release to `main`.

These decisions are already approved and are not being reopened here.

## Questions

### Q1. What hard deadline and budget limits should constrain the rebuild?

Include any launch date and limits for development, hosting, or model/API usage.

A. No fixed deadline or budget yet; estimate them after discovery.
B. There are hard limits; provide the date and/or amounts.
C. There is a target date or budget, but it is flexible; provide the targets.
X. Other (please specify)

[Answer]: No fixed deadline or budget yet; estimate after discovery.

### Q2. Who will build and maintain v2, and what capacity is available?

A. Me with coding agents; plan for one human maintainer.
B. A small human team with coding agents; describe roles and availability.
C. Not decided; identify the effort and skills needed first.
X. Other (please specify)

[Answer]: Me with coding agents; plan for one human maintainer.

### Q3. Are the current technologies or providers mandatory for v2?

This asks about constraints, not a technology selection. Capability retention
remains mandatory regardless of the answer.

A. No fixed technology choice; evaluate replacements against stability and repairability.
B. Some technologies or providers must remain; name them.
C. Inventory the current dependencies before deciding what can change.
X. Other (please specify)

[Answer]: No fixed technology choice; evaluate replacements against stability and repairability.

### Q4. Are there external integration commitments that may not be visible in the repository?

Examples include an institution's sign-in system, a partner API, a required
export format, or an existing third-party consumer of DocSuri APIs.

A. No known commitments beyond current product capabilities.
B. Yes; describe the integration and what must remain compatible.
C. Unknown; investigate current usage before deciding.
X. Other (please specify)

[Answer]: No known commitments beyond current product capabilities.

### Q5. Are there known privacy, content-licensing, institutional, or data-location requirements?

A. No additional requirements are known; identify applicable obligations during discovery.
B. Specific requirements apply; name the policy, agreement, or constraint.
C. Uncertain; investigate before choosing hosting and data-handling rules.
X. Other (please specify)

[Answer]: Uncertain; investigate before choosing hosting and data-handling rules.

## Evidence to collect

- Inventory the current stack, external dependencies, AWS usage and environments
  from repository configuration and available read-only infrastructure evidence.
- Distinguish declared infrastructure from resources verified live.
- Determine which users and saved-data categories exist without copying private
  content into planning artifacts.
- Identify operating costs, current service obligations, and any organizational
  change restrictions not answered above. Ask targeted follow-ups only where
  available evidence cannot settle them.

## Sources

- Approved `../intent-capture/intent-statement.md` and its question record.
- `CONVENTIONS.md` and the user's explicit Git-flow correction.

## Consolidated Summary Confirmation

- Retain all current capabilities for researchers and engineers, anchored in
  finding, understanding, saving and revisiting a paper. Prioritize stable,
  smooth use and comprehensible, repairable code.
- There is no fixed deadline or budget yet. Estimate effort and operating costs
  after discovery; do not assume unlimited resources.
- Plan for one human maintainer supported by coding agents.
- No current technology or provider is mandatory. Evaluate replacements against
  stability and repairability while preserving the product capabilities.
- No external integration commitments are known beyond current capabilities.
  Verify existing dependencies and usage during discovery.
- Privacy, content-licensing, institutional and data-location requirements are
  uncertain. Investigate them before choosing hosting and data-handling rules.
- Repository hosting descriptions and local runtime observations still need
  reconciliation: the DocSuri frontend root responds, the documented local
  backend health endpoint was unavailable, and the observed stopped containers
  belong to the development stack. These are observations, not a complete
  production inventory or a measured user-journey baseline.
- Existing users, authoritative saved data and backup restorability remain to
  be established before deciding continuity or migration.
- Measure complete-task success, responsiveness, interruption recovery and
  defect reproduction/repair before setting numeric targets.
- The feasibility documents will distinguish confirmed constraints from open
  risks, assumptions and dependencies. No stack, hosting, migration policy,
  schedule or spending amount is selected by this confirmation.
- The user retains scope and priority decisions. Git follows `CONVENTIONS.md`:
  working branch → PR into `develop` → release promotion to `main`.

Does this all look correct before I generate the artifact?

Looks correct / Request changes

[Answer]: Looks correct
