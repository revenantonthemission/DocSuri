# DocSuri v2 — Intent questions

## Sources

- [desc] Initial description: "Now that we cleaned up our codebase, let's start making a new version of DocSuri service from the beginning. Our highest priority is to make a stable, smooth user experience. Also, the codebase should be structured cleanly not only from the file perspective, but also from the code perspective so that the codebase is comprehensible and repairable."
- [scope] Workflow-selected scope: `classic`.

## Already established

- Rebuild DocSuri from the beginning following the codebase cleanup. [desc]
- Make a stable, smooth user experience the highest priority. [desc]
- Make both the file organization and the code understandable and repairable. [desc]
- The workflow-selected scope is `classic`. Workflow scope does not establish the product's feature boundaries. [scope]

## Q1. Who should DocSuri v2 serve first, and what recurring task is hardest for them today?

This determines whose experience we optimize. The groups below are possible choices, not confirmed users.

A. Researchers or engineers who need to find and understand papers; describe their main difficulty.
B. Students or readers learning unfamiliar research; describe their main difficulty.
C. Me as the initial user of a personal research tool; describe the task I need most.
D. Not yet defined.
X. Other (please specify)

[Answer]: A. Researchers or engineers who need to find and understand papers.

## Q2. Which complete user journey should anchor the v2 experience?

This identifies the outcome to prove from beginning to end; it does not automatically exclude other capabilities.

A. Find a relevant paper, understand it, save it, and return to it later.
B. Bring a paper I already have, read or understand it, and retain the useful result.
C. Preserve the existing core journeys after checking which ones actually work and matter.
D. Not yet defined.
X. Other (please specify)

[Answer]: A. Find a relevant paper, understand it, save it, and return to it later.

## Q3. How should we judge whether v2 meets the stability, smoothness, and repairability goals?

Your priorities are already established. This asks how we should turn them into measurable acceptance criteria; no performance or reliability numbers have been agreed yet.

A. Measure complete-task success, responsiveness, recovery from interruptions, and the ability to reproduce and fix a defect; establish numeric targets after measuring the baseline.
B. Use specific acceptance targets I provide here.
C. Not yet defined.
X. Other (please specify)

[Answer]: A. Measure complete-task success, responsiveness, recovery from interruptions, and the ability to reproduce and fix a defect; establish numeric targets after measuring the baseline.

## Q4. Who decides scope and priorities, and who else needs to influence or review the result?

This identifies decision authority and stakeholder interests without assuming there is a larger team.

A. I decide scope and priorities; consider end users and future maintainers, with no other named approvers.
B. I decide, with additional stakeholders I will name together with their interests.
C. Another person or team decides; I will name them and their interests.
D. Not identified.
X. Other (please specify)

[Answer]: A. I decide scope and priorities; consider end users and future maintainers, with no other named approvers.

## Q5. What communication or reporting cadence do you want during the rebuild?

The approved plan already includes review points. This asks what additional communication helps you follow the work.

A. Concise progress updates and a clear summary at each review point.
B. Milestone summaries and material issues, plus the plan's required review questions.
C. A particular reporting cadence or format I will specify.
D. None beyond the plan's review points.
X. Other (please specify)

[Answer]: A. Concise progress updates and a clear summary at each review point.

## Q6. What should the first v2 release leave out?

The workflow-selected scope is already `classic`. This question concerns the product boundary, not the development plan.

A. No exclusions yet; assess existing capabilities before deciding what the first v2 release includes.
B. Prioritize the chosen complete journey and explicitly defer other capabilities during scope definition.
C. Retain all current product capabilities in v2; leave new feature expansion for later.
D. Not yet defined.
X. Other (please specify)

[Answer]: C. Retain all current product capabilities in v2; leave new feature expansion for later.

## Q7. What continuity should v2 provide for existing users and their saved data?

Starting the implementation again does not establish whether users should start again. This decision affects the eventual transition to v2.

A. Existing users should keep access to their accounts and saved content through a planned transition.
B. Start v2 with fresh user data while retaining the historical data separately.
C. Not yet defined; determine what users and data exist before choosing.
X. Other (please specify)

[Answer]: C. Not yet defined; determine what users and data exist before choosing.

## Consolidated Summary Confirmation

- Rebuild DocSuri following the cleanup, with a stable, smooth user experience as the highest priority and understandable, repairable files and code. [desc]
- Serve researchers and engineers who need to find and understand papers. [Q1]
- Anchor the experience in finding a relevant paper, understanding it, saving it, and returning to it later. [Q2]
- Retain all current product capabilities in v2; defer new feature expansion. The anchor journey does not narrow the feature-parity requirement. [Q2] [Q6]
- Measure complete-task success, responsiveness, recovery from interruptions, and the ability to reproduce and fix a defect. Set numeric targets after measuring the baseline; no numeric targets are agreed yet. [Q3]
- The user decides scope and priorities; consider end users and future maintainers, with no other named approvers. [Q4]
- Provide concise progress updates and a clear summary at each review point. [Q5]
- User and data continuity is undecided. Determine what users and data exist before choosing the transition policy. [Q7]

Does this all look correct before I generate the artifact?

- Looks correct
- Request changes

[Answer]: Looks correct
