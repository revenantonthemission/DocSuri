# U1 API, installation and test guide

Canonical browser/worker surface, the actual unit test commands and the
recovery pointers for the explicit synthetic-local composition. Nothing here is
the Construction Verification Command; that remains unset until the human
approves it separately.

## API surface (same-origin, `/api/v2`)

All POSTs carry `Origin`, `X-CSRF-Token` (session or bound anonymous flow) and
an `Idempotency-Key`. Errors use the typed envelope
`{code, requestId, retryable, messageKey, retryAfterSeconds?}`.

| Area | Routes | Principal |
|---|---|---|
| Host | `GET /health/live`, `GET /health/ready`, `GET /api/v2/capabilities`, `POST /api/v2/c01/host-resolve-navigation` | session or bound anonymous |
| Accounts | `GET /api/v2/session`, `POST /api/v2/c02/access-register`, `access-request-verification`, `access-verify-email`, `access-login`, `access-logout`, `access-inspect-session` | session or bound anonymous |
| Corpus | `POST /api/v2/c04/resolve-paper`, `c04/read-content`, `GET /api/v2/papers/{paperId}/versions/{versionId}/assets/{assetId}` | authenticated (assets: authenticated, bounded unavailability) |
| Discovery | `POST /api/v2/c05/search` (lexical; semantic requires the pinned embedder) | session or bound anonymous |
| Library | `POST /api/v2/c03/library-save-paper`, `library-list-saved-papers`, `library-read-saved-paper`, `library-remove-saved-paper`, `library-save-search`, `library-list-saved-searches`, `library-remove-saved-search`, `library-list-history`, `library-read-history`, `library-clear-history` | authenticated |
| Personalization | `POST /api/v2/c03/settings-read`, `settings-update`, `settings-update-onboarding` | authenticated |
| Usage | `POST /api/v2/c03/usage-inspect` | authenticated |
| Assistance | `POST /api/v2/c06/read-assistance-options`, `accept-assistance`, `read-assistance-job`, `read-prepared-assistance`, `read-assistance-history`, `read-glossary`, `GET /api/v2/jobs/{jobId}`, `GET /api/v2/jobs/{jobId}/result`, `GET /api/v2/jobs/{jobId}/events` | authenticated, owner-bound |

`accept-assistance` truthfully refuses `503 NOT_READY` while the reviewed
model-readiness marker is absent.

## Installation (owned disposable environment)

1. Run the setup phase; it provisions the container/volume, both owned
   databases, owner roles, the synthetic mail sink, the private fixture files
   and the retention-bound HTTPS material, and records the manifest:

   ```bash
   python3 scripts/verify_docsuri_u1.py --phase setup --profile synthetic-local \
     --environment-file /tmp/docsuri-u1-run/environment.json
   python3 scripts/verify_docsuri_u1.py --phase runner-readiness --profile synthetic-local \
     --environment-file /tmp/docsuri-u1-run/environment.json
   ```

2. Serve the journey realm (HTTPS loopback, static workspace from
   `frontend/dist`) with the supervisor:

   ```bash
   backend/.venv/bin/python scripts/supervise_docsuri_u1.py start-api \
     --environment-file /tmp/docsuri-u1-run/environment.json
   backend/.venv/bin/python scripts/supervise_docsuri_u1.py status \
     --environment-file /tmp/docsuri-u1-run/environment.json
   ```

3. No migration is applied to pre-existing data; every credential stays under
   the private run root (`owner-credentials.json`, 0600) and is never printed.

## Actual unit test commands

```bash
# backend phases (each scope only; serial; the wrapper supplies the manifest)
python3 scripts/verify_docsuri_u1.py --phase database     --profile synthetic-local --environment-file /tmp/docsuri-u1-run/environment.json
python3 scripts/verify_docsuri_u1.py --phase component    --profile synthetic-local --environment-file /tmp/docsuri-u1-run/environment.json
python3 scripts/verify_docsuri_u1.py --phase repository   --profile synthetic-local --environment-file /tmp/docsuri-u1-run/environment.json
python3 scripts/verify_docsuri_u1.py --phase integration  --profile synthetic-local --environment-file /tmp/docsuri-u1-run/environment.json
python3 scripts/verify_docsuri_u1.py --phase operations   --profile synthetic-local --environment-file /tmp/docsuri-u1-run/environment.json
python3 scripts/verify_docsuri_u1.py --phase frontend     --profile synthetic-local --environment-file /tmp/docsuri-u1-run/environment.json
python3 scripts/verify_docsuri_u1.py --phase browser      --profile synthetic-local --environment-file /tmp/docsuri-u1-run/environment.json
```

Instrumented coverage (measured numbers, explicit inventory):

```bash
# backend: append every scope into one data file, then report JSON
export COVERAGE_FILE=/tmp/docsuri-u1-run/.coverage-final
backend/.venv/bin/python -m pytest -c backend/pytest.u1-paper-journey.ini \
  tests/u1_integrated_paper_journey/<scope> -m u1_<scope> -q -p no:cacheprovider \
  --cov=backend.local_browser --cov=backend.local_host --cov=backend.local_observation \
  --cov=backend.transactions --cov=backend.artifacts \
  --cov=backend.modules.accounts.local_http --cov=backend.modules.corpus \
  --cov=backend.modules.discovery --cov=backend.modules.library \
  --cov=backend.modules.personalization --cov=backend.modules.plans \
  --cov=backend.modules.summarization --cov=scripts --cov-append --cov-report=
backend/.venv/bin/python -m coverage json -o /tmp/docsuri-u1-run/python-coverage.json

# frontend: the runner supplies the explicit changed-module inventory
DOCSURI_U1_COVERAGE_INCLUDE='["src/api.ts","src/ui.tsx","src/paper.tsx","src/App.tsx"]' \
  corepack pnpm@9.15.9 exec vitest run --config vitest.u1-paper-journey.config.ts --coverage
```

## Recovery

- `ops/local-stack/u1-operations.md` owns stop/replace, backup/restore/rollback,
  readiness/observation expiry and the bounded limits.
- A failed browse/test session heals through the wrapper's fixture transitions
  (owned account ledger and browser accounts are reset/deleted, the demo account
  is restored) and the supervisor's `status` names exactly which component is
  not ready.
- A lost settlement or stuck acceptance is reconciled by the owner recovery
  path proven in `tests/u1_integrated_paper_journey/operations/`; a source
  withdrawal or authority revocation is refused at the next guarded read.
