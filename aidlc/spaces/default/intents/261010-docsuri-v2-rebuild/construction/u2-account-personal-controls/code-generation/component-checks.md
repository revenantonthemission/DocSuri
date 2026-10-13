# U2 component checkpoint — Library and Personalization

## Scope and evidence

The 2026-10-14 local run used the owned `docsuri_u2` PostgreSQL database from `/tmp/docsuri-u2-run/environment.json`. It used the actual owner-role transaction facility, canonical generated models and real durable receipts. These are isolated synthetic component checks, not a public-service or release-readiness claim.

```sh
DOCSURI_U2_ENVIRONMENT_FILE=/tmp/docsuri-u2-run/environment.json backend/.venv/bin/python -m pytest -c backend/pytest.u2-account-personal-controls.ini tests/u2_account_personal_controls/component/test_library.py tests/u2_account_personal_controls/component/test_owner_lifecycle.py tests/u2_account_personal_controls/component/test_personalization.py -q --tb=short
```

Result: **46 passed in 2.63 seconds**, with no skipped cases. The three files contain 16 Library, 8 owner-lifecycle and 22 Personalization cases. Targeted Ruff checks and `git diff --check` passed after formatting.

## Behaviors established

- Explicit defaults preserve acknowledged onboarding/interests, including skip. Current manual account controls remain usable without behavioral or research consent in U2; the isolated U1 guard remains compatible.
- Receipts reconcile one intended write before stale-revision checks; shared owner locks serialize concurrent writes and absent controls.
- Personalization accepts only installed producer bindings, current owner/session/source/consent authority and the current input boundary. Duplicate events do not multiply effects; delayed, prohibited or reset-generation events do not rebuild deleted behavior.
- Recent/projection/suggestion reads create no activity or settings. Source withdrawal is visible and excludes withdrawn evidence from derived interests.
- Reset owner cleanup preserves post-boundary activity and stays pending while the separately required restore scope lacks evidence.
- Library preserves original saved paper/version/eligibility/title separately from current source disposition. Keyset pages bind owner, authority, view, limit and snapshot; viewing a saved query does not execute it.
- Discovery assigns admission sequence before search work. Library resolves producer facts itself; a pre-clear search finishing later is suppressed. Replaying a clear does not remove newer permitted history. An empty history read returns a deterministic revision without allocating a row.
- Lifecycle effects run with current authoritative action and claim generation held through the owner transaction. Stale/superseded or foreign tickets are denied. Erasure removes private controls and their receipt payloads through narrow guarded functions; ordinary runtime roles do not receive general receipt-delete permission. Withdrawal preserves retained state.

## Failures repaired and remaining checks

The first Personalization test run found that the bounded transaction wrapper has no nested `transaction()` API. Suppression now rolls back the complete transaction before returning its safe disposition; the rerun passed. The first Library run found that the Discovery definer role lacked its narrow AccountAccess guard permission and that a read of immutable admission requested an unnecessary update-level lock. An append-only grant and a plain immutable read fixed those failures; the rerun passed. Applied migration bytes were not changed.

API mounting, browser flows, provider integration, complete lifecycle coordination, current-restriction enforcement during an actual older-backup restore, process/resource supervision, cumulative verification and coverage measurement remain separate obligations. These component counts do not close them. The exact cumulative completion command remains unselected until its prescribed human decision.
