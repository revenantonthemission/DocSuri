# U2 mounted API checkpoint

## Verified scope

On 2026-10-14, the combined mounted API suite used the owned synthetic `docsuri_u2` PostgreSQL database, its actual owner-role transactions and the U2 application composition. Account/Usage contributed 17 cases and Library/Personalization contributed 18.

```sh
DOCSURI_U2_ENVIRONMENT_FILE=/tmp/docsuri-u2-run/environment.json backend/.venv/bin/python -m pytest -c backend/pytest.u2-account-personal-controls.ini tests/u2_account_personal_controls/integration -q --tb=short
```

Result: **35 passed in 15.56 seconds**, no skipped cases. One existing Starlette TestClient/httpx deprecation warning remains. These are mounted ASGI/real-store tests; they do not establish real-browser, public-provider, full release, resource-capacity or older-backup recovery readiness.

## Owner controls and corrections

The checks exercise current owner authentication, policy/revision validation, protected credential/MFA flows, lifecycle confirmation, account/usage boundaries, settings/onboarding preservation, signed library pagination, history clearing without deleting explicit saves, reset confirmation/replay/expiry and read-only reset rediscovery. A switched account cannot inspect the earlier owner's reset or reuse their cursor. Withdrawn source material retains its original saved reference/title/revision.

The first mount attempt caught a missing installed Personalization producer parameter. A subsequent fixture used a reserved `.invalid` email that the canonical email validator correctly refused; the isolated login fixture now uses `fixture.example.com`. Both were repaired before the combined passing run. The bound Library save now contributes consent-permitted recent activity through the same installed Personalization owner. Activity captures authority, consent and input boundary before the source action and rechecks them on delivery; it is optional derived data, not a browser-acknowledged durable command.

C02/C03 required concrete confirmation issuance routes. Canonical contracts now define reauthenticated `access.prepareLifecycle` and `settings.prepareReset`. Reset confirmation consumption occurs in the same transaction as its boundary and acceptance receipt; replay binds the original confirmation as part of the normalized intent. A confirmation replay does not extend expiry. No current-browser principal, arbitrary policy or invented confirmation reference substitutes for the authoritative owner record.

## Remaining evidence

Current-owner lifecycle adapters, complete restore/backup obligations, browser verification, resource supervision, packaging, cumulative checks and coverage remain separate work. A reset's two required scopes remain pending until their current evidence exists; status reads do not claim leases, allocate a reset or perform cleanup. Real provider activation and authoritative-user/data decisions remain subject to the recorded evidence gates. The exact cumulative completion command has not been selected or approved by this checkpoint.
