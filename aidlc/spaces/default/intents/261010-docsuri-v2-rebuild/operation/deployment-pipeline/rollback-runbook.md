# Rollback Runbook — u4-research-novelty

## Rollback Triggers

| Trigger | Detection | Response |
|---|---|---|
| CI gate failure on `main` | `ci.yml` fails (lint, typecheck, test:coverage, test:e2e, security) | Block promotion; do not deploy to production |
| Production smoke test/health check failure | Readiness probe on mounted host fails | Rollback to previous pinned revision |
| Post-deployment incident (P1/P2) | Observability/alerting threshold breached | Rollback per this runbook; post-incident review required |

## Rollback Procedure — Code/Config

1. Identify the last known-good pinned revision on `main`.
2. Revert the release artifact/configuration to that revision (`git revert` or `git checkout <sha>`).
3. Confirm migrations stay backward-compatible (no destructive real-data migration).
4. Re-run the affected CI pipeline phases (lint, typecheck, test:coverage, test:e2e).
5. Deploy the reverted revision to production.
6. Run production smoke test/health check to verify success.

## Rollback Procedure — Data

1. Immutable revisions and tombstones are **never rewritten**.
2. A bad revision is superseded by a new revision, not deleted.
3. A mistaken tombstone is repaired only through the recorded recovery path, never by deleting the deletion boundary.
4. Replay current tombstones and re-verify owner relationships and derived-data disposition before serving (BR5.4, NFR5.3).

## Post-Incident Requirements (P1/P2)

- Runbook includes escalation paths and contact information.
- Post-incident review required: document timeline, root cause, and prevention.
- Recovery changes the reported state only after capability checks succeed (NFR9.2).

## $0 Budget Compliance

- No paid infrastructure; rollback uses only existing local/disposable synthetic environments.
- No automatic rollback to a paid fallback — NFR8.2 prohibits billable activation.
- Refusal states (`POLICY_UNRESOLVED`, `CAPACITY_EXHAUSTED`, etc.) are first-class expectations, never converted into green skips.

## Evidence Preservation

- Each rollback records command, expected/observed outcome, and preserved evidence before any teardown or replacement (NFR3.1, NFR9.1).
- Failed or unknown responsibility evidence is preserved before environment replacement.
