# U2 cumulative completion check — prepared invocation

Prepared 2026-10-14. This record defines the runnable cumulative check for U1, U2 and U7 and their installed composition. It runs only at its recorded human decision point, presented by the conductor before checkpoint verification; each run and its result are recorded in the audit trail.

## Exact invocation

```sh
backend/.venv/bin/python scripts/verify_docsuri_cumulative.py --confirm-recorded-decision
```

The `--confirm-recorded-decision` flag exists so the check cannot run accidentally: without it the script refuses with `refused: the cumulative check runs only at its recorded human decision point`. The script runs, in order:

1. U1 (`scripts/verify_docsuri_u1.py`) phases `database, repository, component, integration, operations` against `/tmp/docsuri-u1-run/environment.json`. Two of the runner's phases are excluded because U1 never claimed them: `contracts` (its test directory was never authored; U1's code-summary records its contracts tests as not authored in that unit) and `model` (U1's code-summary records model quality as blocked by the unresolved P1/P2 grounding evidence; the phase refuses with `ModelUnavailable: runtime version or cloud-disable evidence mismatch`).
2. U2 (`scripts/verify_docsuri_u2.py`) phases `database, repository, component, integration, operations` against `/tmp/docsuri-u2-run/environment.json`.
3. U7 (`scripts/verify_docsuri_u7.py`) phases `component, database, repository, integration, operations` against `/tmp/docsuri-u7-run/environment.json`.
4. The cumulative frontend configuration `frontend/vitest.u2-cumulative.config.ts` (retained U1 + U2 frontend tests against the same complete workspace source inventory).

Each phase runs under its own runner, which enforces its own realm identity, frozen dependency hashes and phase evidence. The script never provisions, reseeds, disposes or bypasses a realm, and any missing, invalid or expired environment fails the check instead of becoming a skip.

## Current prerequisite state (honest)

| Realm | Run identity | Validity observed 2026-10-14 |
|---|---|---|
| U1 | `docsuri-u1-ce00031530778523` | **expired** (~20 h past its recorded retention) |
| U2 | `docsuri-u2-c274e71798431965` | valid at observation |
| U7 | `docsuri-u7-93583d0d3febe0c5` | **expired** (~5.6 h past its recorded retention) |

Both U1 and U7 realms are expired synthetic environments. The cumulative check therefore cannot run until those layers are re-provisioned by their own recorded setup phases (a decision for their owners, not something this unit performs silently). The current realms were not revived, replaced or extended by this preparation; an expired environment is refused by its own runner.

## What the check does and does not claim

- It demonstrates the installed composition: each layer runs the shared application/owner stores against its own realm, and the frontend cumulative configuration runs U1 and U2 browser-independent UI behavior against the same frozen source.
- It does not claim fixture-only provider parity, public-provider activation, public capacity, real-data migration or production readiness. Real provider/delivery/retention/quota/capacity decisions remain G1–G8.
- U1's recorded normal-assistance, semantic-search and figure limitations remain explicit in U1's own evidence and are not relabelled by a cumulative pass.
- U7 separation is demonstrated by running U7's own realms/phases; the U2 application-admin role never gains U7 operator rights (verified independently in U2's owner suites).

## Presentation point

The conductor presents the invocation above, the prerequisite table and the unexecuted status to the person at the cumulative verification decision point. Only after the recorded approval may the command run; its stdout (per-layer phase exit codes and the frontend tail) is the transferable evidence, while each runner retains its own private phase evidence under its owned run directory.
