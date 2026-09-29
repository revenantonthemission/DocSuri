# Verification Remediation Requirements Questions - 2026-09-18

## Context

The prior audit recorded 13 findings in `aidlc-docs/construction/build-and-test/project-verification-2026-09-18.md`. Four were reproduced as focused counterexamples; the remainder include code, dependency, live corpus, runtime configuration, and requirements-baseline issues. These choices establish the exact remediation boundary before code changes begin.

Enter one letter after every `[Answer]:` tag. Choose `X` when none of the listed choices matches and describe the preferred boundary.

## Question 1 - Remediation Scope

Which findings should this remediation cycle address?

A) All F01-F13 findings, including code fixes, dependency upgrades, corpus remediation tooling, and requirement/runtime alignment

B) P1 findings F01-F06 only, addressing private data access, shared-cache integrity, corpus integrity, owner-data purge, generation timeout, and vulnerable dependencies

C) Only the four reproduced counterexamples: F01, F02, F05, and F10

D) All directly code-fixable findings, while deferring live corpus rebuild/purge, dependency upgrades, and requirement-baseline changes

X) Other (please describe after the `[Answer]:` tag below)

[Answer]: A

## Question 2 - Live Runtime and Data Changes

May this cycle modify the currently running local service or its persisted corpus/data?

A) Code and isolated tests only; do not mutate the live runtime or persisted data

B) Code plus read-only live verification; provide separately reviewed repair commands for later execution

C) Include safe live configuration and data repair after tests pass, with backup and rollback steps; do not perform a full corpus rebuild without another explicit approval

D) Include complete live remediation, including fixture removal and corpus rebuild, after backup and rollback validation

X) Other (please describe after the `[Answer]:` tag below)

[Answer]: C

## Question 3 - Requirements Baseline

How should conflicts between the approved AWS/multi-zone requirements and the current single-Mac local runtime be handled?

A) Preserve the approved requirements and fix implementation only; report runtime topology gaps as unresolved

B) Re-baseline infrastructure, availability, recovery, cost, and model/index requirements to the current local runtime before implementation

C) Preserve functional, privacy, security, and data-integrity requirements while re-baselining only obsolete hosting-specific requirements to the current runtime

X) Other (please describe after the `[Answer]:` tag below)

[Answer]: B

## Question 4 - Security Extension

Should security extension rules continue to be enforced for this remediation cycle?

A) Yes - enforce all SECURITY rules as blocking constraints

B) No - disable SECURITY rules for this cycle

X) Other (please describe after the `[Answer]:` tag below)

[Answer]: A

## Question 5 - Resiliency Extension

Should the resiliency baseline continue to apply to this remediation cycle?

A) Yes - apply the resiliency baseline as blocking directional and design-time constraints

B) No - disable the resiliency baseline for this cycle

X) Other (please describe after the `[Answer]:` tag below)

[Answer]: A

## Question 6 - Property-Based Testing Extension

Which property-based testing enforcement mode should apply to this remediation cycle?

A) Full - enforce all PBT rules as blocking constraints

B) Partial - enforce PBT-02, PBT-03, PBT-07, PBT-08, and PBT-09, matching the current project configuration

C) None - disable PBT rules for this cycle

X) Other (please describe after the `[Answer]:` tag below)

[Answer]: A
