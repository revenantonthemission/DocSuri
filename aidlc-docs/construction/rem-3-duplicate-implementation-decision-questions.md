# REM-3 Adapter Duplication — Decision Required

Phase 3 was instructed to "delete and regenerate the seven defective adapters inside
`platform_integrity/src/docsuri_platform_integrity/adapters/`". Before regenerating them I
searched the monorepo for existing equivalents, and **five of the seven duplicate code that
already exists, is wired into a running request path, and is already tested.**

Regenerating them as written in the plan would create a **second parallel implementation** of
account purge, email unsubscribe, client identity, rate limiting, and S3 presigning — and the new
copies would be dead code, because their only importer is already broken.

## Evidence: existing, wired, tested implementations

| Adapter | Existing implementation | State |
|---|---|---|
| `purge.py` | `account_deletions` table (`backend/modules/accounts/migrations/003`, `011_add_purge_attempts.sql`), `AccountDeletionService.purge_job()`, `backend/modules/accounts/purge_worker.py` (60 lines, real CLI), `SqlOwnerDataPurger` (101 lines, 16 owner-scoped tables, identifier whitelisting) | **complete**, wired, tested |
| `unsubscribe.py` | `backend/modules/trends/service.py` `UnsubscribeTokenSigner` (HMAC-SHA256, `hmac.compare_digest`), `issue_unsubscribe_token()`, `unsubscribe()`, `POST /trends/unsubscribe` (no-login, token-only, never 5xx), `digest.py` CLI, frontend page | **complete**, wired, 629 lines of tests |
| `ratelimit.py` | `backend/middleware/rate_limit.py` (151 lines) — `InMemoryRateLimiter` sliding window, `RedisRateLimiter` (`INCR`+`EXPIRE`, TLS, fails open), consumed by gateway blanket limit, accounts per-email/per-IP, `agent_quota.py` per-user daily | **complete**, wired, tested |
| `identity.py` | `backend/middleware/gateway.py` `_forwarded_client()` / `_rate_limit_key()` — right-most-N-hop XFF resolution, rejects spoofable leftmost, validates hop is an IP; `TRUST_PROXY_HEADERS`/`TRUSTED_PROXY_COUNT` deployed as CloudFront+ALB | **partial** (no Cloudflare header), wired, tested |
| `assets.py` | `summarization/adapters/rds_assets.py` `RdsS3AssetReader.presign()` (boto3, `generate_presigned_url`, honours `AWS_ENDPOINT_URL_S3` for local MinIO, never leaks `object_ref`), `ingestion/adapters/assets.py` `S3RdsAssetStore` (SSE-KMS, delete-by-version, orphan-tolerant GC) | **complete**, wired, tested |

`revocation.py` and `authz.py` are the exception — **no equivalent exists**. Revocation prior art
is only `session:{handle}` key deletion in `accounts/repository/session.py`; there is no `jti`
tracking or denylist anywhere. `authz.py`'s `_check_revocation()` is a stub returning `False`
("구현 간소화"), and `api/content_jobs.py` returns a hardcoded `mock-jwt-token` and a mock
presigned URL.

## The regeneration target is orphaned

All seven files are dead code. The only importer is
`platform_integrity/src/docsuri_platform_integrity/api/content_jobs.py`, and that module is broken
in three independent ways: it imports from `ops.platform_integrity` (a hyphenated, `__init__.py`-less
directory), `AuthorizationServiceImpl` is defined nowhere, and the router is never mounted in any
FastAPI app. `_job_service` / `_asset_service` / `_authz_service` are never assigned, so every route
would 503 regardless. No test imports any of the seven.

## The approved plan already assigns these elsewhere

`aidlc-docs/inception/plans/verification-remediation-2026-09-18-workflow-plan.md` maps G3 findings to
modules, and the homes are **not** `platform_integrity`:

| Line | Scope | Findings |
|---|---|---|
| 54 | `accounts` + `evidence`/`onboarding`/`trends`/`plans` — 파기/메일 | F04, F09 |
| 55 | BFF + `gateway` + accounts controller — trusted client identity | F10 |
| 589 | G3 requires: full owner store/job/event/result purge + late-write blocking; immediate session/account protection; send-blocked-after-token-revocation; spoof-resistant same-client bucket | F04/F09/F10 |

So the plan's own scope table puts purge in `accounts`, email in `trends`, and edge identity in the
gateway. The `platform_integrity` adapters were never the integration point.

## What BR-PURGE still genuinely needs (the real remaining work)

The existing accounts purge covers DB cascade, grace period, idempotency, and poison-record
quarantine. It does **not** cover these BR-PURGE clauses, and this is where real work remains:

- `pg_advisory_xact_lock` per owner (BR-PURGE-03/06) — no advisory lock anywhere.
- **Object** purge order: DB cascade → S3 objects → backup GC → `PURGED` (BR-PURGE-03).
  `SqlOwnerDataPurger` does not touch S3 at all.
- Optimistic `version` column (BR-PURGE-07) — `account_deletions` has `state` + `purge_attempts`, no `version`.
- Late-write blocking after purge request (F04) — a `DEACTIVATED` account can still be written to.
- `List-Unsubscribe` / `List-Unsubscribe-Post` headers (F09) — absent repo-wide.
- `Retry-After` on 429 (F10) — absent repo-wide; only the orphan adapter set it.
- Cloudflare identity headers — absent repo-wide.

## Question 1

Given that five of seven are duplicates of working code and the plan's own scope table assigns them
to `backend/` modules, how should Phase 3 proceed?

A) **Delete the seven orphaned adapters and implement F04/F09/F10 in their assigned homes** —
   extend `accounts` purge with advisory locks + S3 object purge + late-write blocking, add
   `List-Unsubscribe` headers to the `trends` digest path, and extend the gateway with Cloudflare
   identity + `Retry-After`. Build the genuinely-missing revocation/AuthZ there. This closes G3
   against the code that is actually wired, and avoids two implementations of the same rules.

B) **Regenerate the seven adapters as planned** inside `platform_integrity`, treating them as the
   REM-3 deliverable, and separately fix the orphaned `content_jobs.py` so they are reachable.

C) **Hybrid** — delete only the four confirmed duplicates (`purge`, `unsubscribe`, `ratelimit`,
   `assets`) and regenerate the three that have no equivalent (`identity`, `revocation`, `authz`)
   in `platform_integrity`.

X) Other (please describe after [Answer]: tag below)

[Answer]: A) Delete the seven orphaned adapters and implement F04/F09/F10 in their assigned homes — extend `accounts` purge with advisory locks + S3 object purge + late-write blocking, add `List-Unsubscribe` headers to the `trends` digest path, and extend the gateway with Cloudflare identity + `Retry-After`. Build the genuinely-missing revocation/AuthZ there. This closes G3 against the code that is actually wired, and avoids two implementations of the same rules.

## Question 2

Whichever option is chosen, should the `minio` Python SDK stay a declared dependency?

The only consumer would be a regenerated `assets.py`. The existing, wired asset paths use **boto3**
and honour `AWS_ENDPOINT_URL_S3`. Since the MinIO image is already substituted locally by SeaweedFS,
the `minio` SDK adds a second, unused S3 client to the tree.

A) **Drop the `minio` SDK**; keep `psycopg` / `redis` / `PyJWT` declared, and use boto3 like the
   existing asset paths
B) **Keep the `minio` SDK** declared for the REM-3 asset adapter as originally decided

X) Other (please describe after [Answer]: tag below)

[Answer]: A) Drop the `minio` SDK; keep `psycopg` / `redis` / `PyJWT` declared, and use boto3 like the existing asset paths

## Resolution

Approved: **Q1=A, Q2=A.**

- The seven orphaned `platform_integrity` adapters are **deleted, not regenerated**.
- F04 purge extends `backend/modules/accounts` (advisory locks, S3 object purge, late-write
  blocking, optimistic `version`).
- F09 email extends `backend/modules/trends` (`List-Unsubscribe` headers) and the send path
  (block after token revocation).
- F10 edge trust extends `backend/middleware/gateway.py` (Cloudflare identity, `Retry-After`).
- Revocation denylist and AuthZ recheck are **new work**, built in the backend session/auth homes.
- Asset presigning reuses the existing boto3 paths; the `minio` SDK is dropped.

This supersedes plan step 10 ("delete and regenerate seven adapters") and step 11's requirement for
a new `platform_integrity/workers/purge_worker.py`: the existing
`backend/modules/accounts/purge_worker.py` is the purge worker and is extended instead.

## Note on work already done this phase

The `rem3` optional-dependency group was added to `platform_integrity/pyproject.toml` (resolving
`minio`, `psycopg`, `pyjwt`, `redis`), which fixes defect 3's unimportability, and an import check
confirmed all seven modules import. **Per Q2=A, `minio` was subsequently removed from that group**,
leaving `psycopg` / `redis` / `pyjwt`. No adapter has been regenerated and no design document has
been modified.
