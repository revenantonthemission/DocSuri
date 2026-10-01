# REM-2 Corrective Plan — Private Content Service

**Status**: Phases 0 (F01/F02/F05 items) + 1 + 2 + 3 **complete** — F01/F02 security hotfix
(`cedb68a8`) and F05 timeout alignment (`5b9d2b2`) + frontend browser budget (`b47d1db3`) landed
2026-10-01; next is Phase 4 (F07). Phases 4–8 pending. Decisions D1–D6 answered (all A),
recorded in `rem-2-corrective-decision-questions.md`.
**Date**: 2026-10-01
**Unit**: REM-2 Private Content Service (`rem-2-private-content`) — re-opened under the same ID
**Supersedes**: the REM-2 completion claim in commit `fcbac4e` ("REM-2 & REM-3: Complete …")
**Specification**: the REM-2 design documents under `aidlc-docs/construction/rem-2-private-content/`
remain authoritative and are **retained, not rewritten**; the approved plan answers in
`rem-2-private-content-{functional-design,nfr-requirements,nfr-design,infrastructure-design,code-generation}-plan.md`
(all `[Answer]: A`) are binding.

---

## 1. Why this unit was re-opened

The round-3 prerequisite decision (`aidlc-docs/construction/rem-4-prerequisite-decision-questions.md`,
**Q1=B**) scoped this corrective unit to **G1/G2/G3 + the REM-3 corrective**, where
**G2 = F01/F02/F05/F07 = the REM-2 worker pipeline, "rewritten in this unit"**
(`aidlc-docs/audit.md:7258`). Only REM-3 (G3) and the agent-runnable G1 runbook sections were actually
executed; the plan recorded **G2 🔴 not met — "REM-2 pipeline still unbuilt"**
(`rem-3-corrective-plan.md:247`).

The reason REM-2 was believed "handled by deletion" is that the seven AIDLC-generated
`platform_integrity/.../adapters/*` duplicated existing backend code
(`aidlc-docs/audit.md:7498-7512`). That is true only for the REM-3-shaped adapters. Two independent
read-only reconstructions of the **REM-2** acceptance path (2026-10-01) show the backend
implementations the deletion pointed at **do not actually meet F01/F02/F05/F07** and that the public
job contract (RJ-AC01–RJ-AC12) is largely unimplemented.

## 2. Defects, with evidence

Two read-only gap analyses were run against the real code (deleted adapters excluded). Verdicts:

| # | Finding | Verdict | Concrete gap (evidence) |
|---|---|---|---|
| 1 | **F01** private userdoc read boundary | **NOT MET** | `GET /api/papers/{paper_id}/doc-model` verifies only session presence, never ownership (`summarization/.../api/router.py:94-138`, `:105-107`); `userdoc:` is not rejected on the corpus route; the id flows verbatim into the S3 key (`adapters/s3_docmodel.py:44-54`, `:47`); private and corpus share one bucket+prefix (`ops/cdk/stacks/compute_stack.py:356,360`; `ingestion/.../aws.py:79-80`). Net: any authenticated session can read another tenant's uploaded-PDF DocModel. `authorize_owned` exists (`library/authz.py:17-25`) but is unused here. Owner binding exists only on the mint/poll side (`evidence/controller.py:290-303`, `backend/tests/test_user_docmodel.py:114,149,219`). |
| 2 | **F02** shared translation-cache contamination | **NOT MET** | Client `abstract` is accepted unvalidated (`router.py:202-224`) and is the sole/fallback source for translate+abstract (`domain/source_selector.py:31-41`, `:43-60`); the cache key carries no source content (`domain/models.py:84-108`; `domain/cache_key.py`; `adapters/s3_redis_store.py:40-51`); the baseline key is owner-agnostic by design (`tests/test_pbt.py:45-53`). Net: one user's crafted `abstract` becomes every user's cached artifact. Compounded by F01 via `userdoc:` ids. |
| 3 | **F05** generation timeout / sync→async conversion | **NOT MET** | An async SQS path returns `202` (`api/summary.py:90-123`) but there is **no aligned budget** (browser/BFF/API/model/worker), **no threshold** that converts a normal over-budget generation to job/pending/poll, and **no bounded hang termination**. No F05 regression exists. |
| 4 | **F07** private asset serving | **NOT MET** | `GET /api/papers/{paper_id}/assets` checks only principal presence (`router.py:140-163`); manifest query has no owner/license predicate (`adapters/rds_assets.py:61-74`); the browser fetches the presigned S3/MinIO URL **directly** (`frontend/lib/api/apiClient.ts:470-488`; `components/DocModelViewer.tsx:496,546,549,603`), so no re-check occurs after issuance; `object_ref` is withheld from JSON but the **object key leaks inside the presigned URL** (`rds_assets.py:96-101`; pinned by `tests/test_assets_endpoint.py:203`); `AWS_ENDPOINT_URL_S3` (MinIO) would leak an internal host (`rds_assets.py:55-58`). CSP currently allowlists the S3 host, confirming direct-to-S3 is what ships (`frontend/middleware.ts:31-47`, `:39`). |
| 5 | **Job contract RJ-AC01–AC12** | **NOT MET** (transport only) | No durable job store/state machine, no idempotency-key store, no job event stream/SSE/subscribe/reconnect, no status-result-writes-no-recursive-job, no expiry, no authz re-check bound to current caller (job ID alone suffices), no owner-scoped job deletion, no queue-outage/crash/partial-deploy recovery guarantees. Frontend `contentJobApi.ts`/`JobStatus.tsx`/`AssetViewer.tsx` exist but **have no matching backend routes** (`content-jobs` grep returns nothing) — dead code. |
| 6 | **No failing regressions** | gap | The current suite **pins the unsafe behavior as intended** (`test_pbt.py:45-53`, `test_domain_source_cache_length.py:35-37`, `test_assets_endpoint.py:203`). F01/F02/F05/F07 have no reproductions. |

**Severity**: defects 1 and 2 are **cross-tenant data exposure** (private DocModel readable by any
session; client text published into the shared cache). Defect 4 leaks object keys and serves assets
without owner/license authorization. These are SECURITY-08 / SECURITY-13 blocking findings.

## 3. Scope

### In scope
- **F01** — private userdoc read boundary: reject `userdoc:` on the public corpus route; owner-verified
  private read; shared boundary for source selection and derived-artifact read.
- **F02** — canonical translation/asset cache identity: server-verified source only; key bound to
  canonical source identity + content version; client source cannot determine another user's result.
- **F05** — aligned generation time budgets; over-budget normal generation converts to
  job/pending/poll; bounded hang termination (no arbitrary 10s 504).
- **F07** — authenticated same-origin asset endpoint with owner/license/object re-check; no internal
  endpoint/key exposure; CSP aligned.
- **Public job contract RJ-AC01, AC02, AC03, AC04, AC05, AC06, AC07, AC08, AC12** for the REM-2
  content paths (durable acceptance, status-without-recursion, events/reconnect, expiry, caller/object
  authz, idempotency/redelivery, canonical cache reuse, authorized same-origin delivery, resiliency).
- **Frontend** wiring of the status/event/asset flows (`contentJobApi.ts`, `JobStatus.tsx`,
  `AssetViewer.tsx`) to the real backend.
- **Failing regressions first** for every defect (per `verification-remediation-2026-09-18.md` §4).

### Out of scope — BLOCKED-ON-REM-4
| Item | Reason |
|---|---|
| **F03/F11/F12** (corpus integrity, empty degradation, no-match) | REM-4 scope |
| **G4** integration/browser/compatibility | closes on REM-4's F03/F11/F12 |
| **G5** recovery/live preflight | closes on REM-4's F03 evidence |
| Full corpus rebuild | separate explicit approval gate |
| F09/F10, F04 | already implemented in the REM-3 corrective (G3) |
| RJ-AC09/AC10/AC11 ownership re-work | owned by REM-3/REM-4 paths; **verify, do not rebuild**. AC09 purge cascade is F04 (done); AC10 unsubscribe is F09 (done); AC11 deactivation/session is FR-28 (done). This unit asserts they still hold for the new job entities. |

## 4. Authoritative decisions (binding, from the approved plans)

- **FD-Q1**: new dedicated route for private read; **public corpus route rejects `userdoc:` (404)**.
- **FD-Q2 / NFR-Q8 / NFR-Q13**: cache key = `translate:{canonical_paper_id}:{version}:{source_tier}:{target_lang}:{persona_hash}`; **client source ignored**; server canonical lookup; source tier enum.
- **FD-Q3 / NFR-Q11**: char-count + model-p95 threshold; below → sync, above → job accept. Default thresholds summarize 8k / translate 12k / novelty 16k chars; reverse timeout table (model p95 → worker → API → BFF → browser).
- **FD-Q4 / ND-Q4 / ND-Q7 / ID-Q7**: dedicated asset endpoint with owner/license/object re-check before returning a short-TTL presigned GET; assetId = `asset:{sha256(content)[:32]}`; CSP `img-src 'self'`.
- **FD-Q5**: `POST /private/userdoc` → job → DocModel → `userdoc:{owner}:{docId}`; no corpus dedup; failure → abstained.
- **FD-Q6**: state machine `submitted|accepted|queued|running|completed|failed|abstained`; cache hit → completed immediately.
- **ND-Q2 / NFR-Q4**: `JobEventEmitter` + SSE endpoint `GET /jobs/{jobId}/events` with `Last-Event-ID` replay.
- **ND-Q3**: cache hit → `200 {assetId}`; miss → `202 {jobId}`.
- **ND-Q5 / NFR-Q9**: per-boundary `JobAuthzMiddleware`; cached authz ≤1 min; expiry → immediate `failed` + `permission_revoked`.
- **ND-Q6**: idempotency key = `content:{canonical_paper_id}:{task_type}:{input_hash}:{params_hash}`.
- **ND-Q8 / NFR-Q12**: effect ledger `(job_id, attempt)` unique; dedup on redelivery.
- **ID-Q1**: **separate `private/userdoc/{owner}/{docId}/` prefix** (not the corpus `doc-model/` prefix), IAM-isolated.
- **ID-Q3**: ElasticMQ (local) / SQS-compatible queue + DLQ.
- **PBT Full + Security Full**; PBT seed `20260930`; Python Hypothesis + TS fast-check.

## 5. Open decision questions — ANSWER BEFORE EXECUTION

Mirroring the REM-3 duplicate-implementation escalation, five decisions materially change the work.
They are collected in `aidlc-docs/construction/rem-2-corrective-decision-questions.md`. Execution
does not start until answered.

## 6. Execution phases

> Every finding first gets a **failing** permanent regression; then the fix; then the green.

### Phase 0 — Reproductions (no production code yet)
1. [x] F01: cross-owner `GET /api/papers/userdoc:<uuid>/doc-model` regression (fails today).
2. [x] F02: two requests differing only in client `abstract` share a cache entry (fails today).
3. [x] F05: over-budget sync generation is not converted to job / no bounded hang (fails today).
4. [ ] F07: asset manifest returns no owner/license check + key-in-URL assertion (fails today).
5. [ ] Job contract: durable-acceptance and idempotency regressions (fail today).

### Phase 1 — F01 private read boundary (highest severity)
6. [x] Reject `userdoc:` on the public corpus route with 404 (FD-Q1).
7. [x] New owner-verified private read route; non-owner → indistinguishable 404.
8. [x] Route source selection + derived-artifact read through the same boundary.
9. [x] Store private DocModels under the **separate** `private/userdoc/{owner}/{docId}/` prefix (ID-Q1);
    backfill/deny old shared-prefix reads.

### Phase 2 — F02 canonical cache identity
10. [x] Canonical source resolution from server-verified metadata/DocModel only (FD-Q2).
11. [x] Cache key binds canonical identity + content version; client `abstract` no longer keyless.
12. [x] Guard so a client body can never populate/replace a shared canonical entry (RJ-AC07).
13. [ ] Invalidate/repair contaminated baseline entries (`gver==0`) — dry-run counts first.
    *Partially self-healing:* the new `_x<sourceVer>` segment rotates every F02-era path, so no
    pre-fix artifact is addressable again. What D6 still needs: the dry-run count + back-up of
    untraceable objects, and a rebuild path for uploads whose legacy `doc-model/userdoc:...`
    object is now denied (item 9's backfill half).*

### Phase 3 — F05 timeout alignment + sync/async threshold
14. [x] Declare the reverse timeout table as config (NFR-Q11).
15. [x] Threshold converts over-budget normal generation to job accept + pending/poll (FD-Q3).
16. [x] Bounded hang termination; remove arbitrary 10s 504 behavior.
    *Landed 2026-10-01 (`5b9d2b2` backend + `b47d1db3` frontend). The table is declared once in
    `summarization.domain.timeout_profile` and mirrored in `ops/platform-integrity/timeouts.yaml`,
    with drift tests on **both** sides. The undeclared orchestrator token constant (~24k chars) is
    replaced by the declared per-task **char** threshold, so a 10k-char summary now becomes
    job-accept + pending instead of an inline generation that blew the budget. The API leg is
    actually enforced in `gateway_seam.run_summarization`: a generation still running at its budget
    is handed to the job queue and answered `pending` (or, with no queue, a bounded abstain), so no
    request outlives the layer the outer timeouts are calibrated against. The client's arbitrary
    10s fallback is replaced by the declared browser leg (15s summary/translate, 30s novelty/evidence).*

### Phase 4 — F07 same-origin asset serving
17. [ ] Same-origin `GET` asset endpoint with owner/license/object re-check before delivery.
18. [ ] Never expose internal endpoint/key in any response (incl. presigned URL path) (SECURITY-08).
19. [ ] CSP `img-src 'self'`; update `frontend/middleware.ts`; point viewer at same-origin URL.

### Phase 5 — Job contract (RJ-AC01–08, AC12)
20. [ ] Durable job store + state machine (`submitted→accepted→queued→running→completed/failed/abstained`).
21. [ ] Idempotency-key store; submit returns existing jobId (ND-Q6, RJ-AC06).
22. [ ] Job event emitter + SSE subscribe/reconnect with `Last-Event-ID`; no recursive status jobs.
23. [ ] Caller/object authz re-check at every boundary; job ID alone insufficient; non-owner indistinguishable.
24. [ ] Canonical result reuse with per-caller metadata/authz isolation; result expiry.
25. [ ] Effect ledger `(job_id, attempt)`; redelivery dedup (ND-Q8).
26. [ ] Authorized direct delivery of prepared DocModel/results; no new job.
27. [ ] Queue/DLQ wiring (ElasticMQ/SQS) + worker consumer with bounded concurrency (ID-Q3/ID-Q4).

### Phase 6 — Resiliency + readiness
28. [ ] Injected queue-loss / worker-crash / partial-deploy / subscription-break tests (NFR-Q12, RJ-AC12).
29. [ ] Accepted-work recovery or explicit terminal failure; zero duplicate effects.
30. [ ] Health/readiness answer without creating jobs.

### Phase 7 — Frontend wiring
31. [ ] Wire `contentJobApi.ts` submit/subscribe/status to real routes; `JobStatus.tsx` states.
32. [ ] Wire `AssetViewer.tsx` to the same-origin endpoint.
33. [ ] TS PBT (`job_event_order`, `asset_delivery`) + component tests.

### Phase 8 — Gates + evidence
34. [ ] Python PBT (state machine, cache idempotency, authz recheck, queue redelivery).
35. [ ] Full suites green (backend/ops/platform_integrity/frontend), ruff/ESLint/tsc clean.
36. [ ] Live smoke against Colima Postgres/Redis/OpenSearch/ElasticMQ/MinIO.
37. [ ] Record G2 by evidence in `aidlc-state.md`; leave G4/G5 `BLOCKED-ON-REM-4`.

## 7. Security invariants (must hold at completion, verified by gates)

- A `userdoc:` id is never served by a public corpus route.
- A non-owner can never distinguish "exists but not yours" from "does not exist" for private docs/assets.
- No client-supplied body can determine or contaminate another caller's or the canonical result.
- No internal object key or MinIO/S3 endpoint appears in any client-visible response.
- Job access requires current caller/object authorization, not possession of a job ID.
- Retries/redelivery create exactly one effect.
- No secret in logs or committed files; no `-A` Keychain ACLs.

## 8. Definition of done

- [ ] F01/F02/F05/F07 each have a **permanent regression** that fails before the fix and passes after.
- [ ] No cross-owner read of a private DocModel under any route.
- [ ] Client `abstract` cannot alter a shared cache entry.
- [ ] Over-budget sync generation converts to job/poll; hangs terminate bounded.
- [ ] Assets served same-origin with owner/license/object re-check; no key/endpoint leak.
- [ ] RJ-AC01–08 + AC12 acceptance demonstrated by tests (unit + integration + injected failures).
- [ ] Frontend flows wired to real backend routes (no dead code).
- [ ] All static gates green; live smoke passes on Colima.
- [ ] Gate matrix recorded: **G2** met; **G4/G5** remain `BLOCKED-ON-REM-4`.

## 9. Traceability

| Defect | Finding | Requirement | Blocking finding |
|---|---|---|---|
| 1 | F01 | FR-18/38, RJ-AC05/08 | SECURITY-08 |
| 2 | F02 | FR-5/13, QT-5, RJ-AC06/07 | SECURITY-13 |
| 3 | F05 | FR-12/13, NFR-P2/R2, RJ-AC01/03/04 | RESILIENCY-10 |
| 4 | F07 | FR-17/18, RJ-AC08 | SECURITY-08 |
| 5 | job contract | FR-52, NFR-R4, QT-12, C-13 | SECURITY-12/13 |
