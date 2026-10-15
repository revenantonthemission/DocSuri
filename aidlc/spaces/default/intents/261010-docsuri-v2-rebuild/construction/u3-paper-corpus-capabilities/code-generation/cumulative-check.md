# U3 cumulative completion check — invocation and recorded runs

Prepared 2026-10-15. This record carries the U3-inclusive cumulative check for U1, U2, U3 and U7 and their installed composition. The runnable invocation lives in `scripts/verify_docsuri_cumulative.py` (the shared check; U3's layer runs after U2 so the composition covers the corpus/discovery/assistance owners). It runs only at its recorded human decision point, presented before checkpoint verification.

## Exact invocation

```sh
backend/.venv/bin/python scripts/verify_docsuri_cumulative.py --confirm-recorded-decision
```

It runs each layer's own phases against that layer's environment (U1: database, repository, component, integration, operations; U2 and U3: database, repository, component, integration, operations; U7: component, database, repository, integration, operations) and then the cumulative frontend configuration. It never provisions, reseeds or disposes a realm; a missing or expired environment fails the check instead of becoming a skip.

## Prerequisite state at the decision point

U1, U2 and U7 manifests had expired (~2 h, ~22 h and ~1 h past their renewals) and were re-provisioned fresh for these runs (U1 and U2 via their own setup plus bootstrap/migrate; U7 via teardown, retirement of the expired run root and fresh setup). U3's realm was valid from this unit's build.

## Recorded runs (2026-10-15)

- Run 1: U1 database failed (its re-provisioned realm was missing the owner/migration credential files; its setup only renews an existing realm and cannot restore them); U2 database failed (the fresh realm had no accumulated `operations.observation` rows until the host had run once); U3 and U7 passed all phases.
- Run 2 (after re-provisioning U1 fresh with bootstrap and warming U2 with one host run): U1 repository failed (the shared discovery read code now requires the `snapshot_revision` column that only U3's migration adds); U2 component failed for the same missing column; U3 and U7 passed.
- Run 3 (after applying U3's `backend/modules/discovery/u3_schema.sql` to the U1 and U2 realms and preparing U1's fixture inputs): **U2, U3 and U7 pass every phase.** U1 passes database (47) and stops at repository (1 failed, 72 passed, 11 errors).

## Open blocker

The remaining U1 blocker is model-runtime evidence drift, not a U3 defect: U1's repository phase needs `corpus-publication.json`, whose regeneration embeds the fixture papers through the pinned local runtime. The machine now carries ollama 0.40.4 while the pinned evidence requires 0.40.2, so publication refuses with `ModelUnavailable`, and the original realm's publication cannot be transplanted (realm-identity bound). Restoring the pinned build or re-evidencing that path is U1's own remediation. The check is **not passed**; this blocker is carried as an open item alongside the earlier realm-composition and fixture-preparation findings, and no parity or readiness claim is made from these runs.

## Resolution (2026-10-16)

The human authorized changing the machine's ollama version. Homebrew had auto-upgraded ollama to 0.40.4 on 2026-10-15, replacing the pinned 0.40.2 binary while a 0.40.2 server process from 2026-10-10 kept running on 127.0.0.1:11434.

- Staged the v0.40.2 macOS release (`ollama-darwin.tgz`, checksum verified against the release `sha256sum.txt`) as a Homebrew-mirroring keg at `/opt/homebrew/Cellar/ollama/0.40.2/` (`libexec/` holds the extracted binary, `llama-server`, the `*.dylib`/`*.so` set and the `mlx_metal_v*` directories; `bin/ollama` is the keg-relative symlink).
- Repointed `/opt/homebrew/bin/ollama` to `../Cellar/ollama/0.40.2/bin/ollama`. The prior target (`../Cellar/ollama/0.40.4/bin/ollama`) and the 0.40.4 keg are untouched; the running 0.40.2 service on port 11434 was left alone. Revert: `ln -sfn ../Cellar/ollama/0.40.4/bin/ollama /opt/homebrew/bin/ollama`.
- A scratch server started from the new path reported `{"version":"0.40.2"}`. The first publication attempt then failed with `ModelUnavailable` because the keg copy omitted `llama-server` (the pinned runtime looks for `<libexec>/llama-server`); copying the complete extracted set fixed it.
- `backend/.venv/bin/python scripts/publish_docsuri_u1_papers.py` → `{"database": "docsuri_u1_journey", "papers": 2, "ready": true}` (attempt 3, `published`).
- The recorded Construction Verification Command (`python3 scripts/verify_docsuri_u1.py --phase browser --profile synthetic-local --environment-file /tmp/docsuri-u1-run/environment.json`) passed 6/6 journeys (`expected: 6, skipped: 0, unexpected: 0`).

U3's unit construction checkpoint was then **verified** (`exit_code 0`, `evidence_unchanged: true`, tool-owned `CHECKPOINT_VERIFICATION_RECORDED` receipt) and approved under the record's autonomous checkpoint policy; the walk advanced to the next unit's functional-design. The cumulative check's earlier realm-composition and fixture-preparation findings remain separate open items.
