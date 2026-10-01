# REM-2 Corrective — Decision Questions

**Status**: open — answers required before Phase 1 execution
**Date**: 2026-10-01
**Context**: `aidlc-docs/construction/plans/rem-2-corrective-plan.md`
**Why this file exists**: the REM-2 corrective touches three security-critical boundaries (private
DocModel reads, shared translation cache, asset delivery) plus where the durable job pipeline is
built. Each answer materially changes the implementation, so none is guessed. These mirror the
REM-3 duplicate-implementation escalation (`rem-3-duplicate-implementation-decision-questions.md`).

Answer each with the letter and any note. To take every recommendation, record `A` for D1–D5.

---

## D1 — Where is the durable job pipeline built?

The original REM-2 code-generation plan placed it in `ops/platform-integrity/`
(`content_job_service.py`, `job_queue.py`, `workers/*`) as a separate deployable. The REM-3 corrective
instead moved REM-3 work into `backend/` homes. The backend already has `summarization` (orchestrator,
SQS adapters, worker) and a FastAPI app.

A) **Build it in `backend/` (recommended)** — job store + state machine + events live in the FastAPI
   app/service layer; workers consume ElasticMQ/SQS; reuse `summarization`, `user_docmodel`, `library`
   and existing wiring. Consistent with the REM-3 corrective decision and with single-deployable
   `backend/`.
B) Build it in `ops/platform-integrity/` as the original REM-2 plan specified — a separate
   `docsuri-content-job` deployable.
C) Hybrid — service in `backend/`, workers in `ops/`.

[Answer]: A — build the durable job pipeline in `backend/` (service layer in the FastAPI app; workers consume ElasticMQ/SQS; reuse `summarization`/`user_docmodel`/`library`/wiring).

---

## D2 — F01 private-storage boundary

Today private and corpus DocModels share one bucket and the `doc-model/{paperId}` prefix
(`ingestion/.../aws.py:79-80`; `ops/cdk/stacks/compute_stack.py:356,360`). ID-Q1 specified a separate
prefix.

A) **Migrate private DocModels to `private/userdoc/{owner}/{docId}/` and enforce owner checks on read;
   deny legacy shared-prefix `userdoc:` reads (recommended)** — strongest isolation, matches ID-Q1.
B) Keep one prefix; gate reads on an owner-owned metadata row (no storage move).
C) Separate bucket for private content.

[Answer]: A — move private DocModels to the `private/userdoc/{owner}/{docId}/` prefix, enforce owner checks on read, and deny legacy shared-prefix `userdoc:` reads.

---

## D3 — F02 client-supplied `abstract`

The public summarization request accepts an unvalidated client `abstract` that is the sole/fallback
source and is absent from the cache key (`domain/source_selector.py:31-60`; `router.py:202-224`).

A) **Deprecate the client `abstract` field; server always resolves a canonical source (recommended)** —
   removes the contamination vector entirely; frontend stops sending it.
B) Keep it, but bind the cache key to a hash of the client source so results are isolated per input
   (still lets a client control only its own result).
C) Validate the client `abstract` against server metadata and reject mismatches.

[Answer]: A — deprecate the client `abstract` field; the server always resolves a canonical source; frontend stops sending it.

---

## D4 — F07 asset delivery mechanism

A same-origin endpoint is required (FD-Q4). The original plan proposed a same-origin endpoint that
`307`-redirects to a short-TTL presigned MinIO/S3 URL — but that browser-visible URL embeds the object
key and may embed an internal endpoint (`adapters/rds_assets.py:55-58,96-101`).

A) **Same-origin backend proxy** — the app streams the bytes; clients only ever see `'self'`; no key
   or internal endpoint is browser-visible (recommended; strongest SECURITY-08).
B) Same-origin endpoint that `307`-redirects to a short-TTL **internal-host-free** presigned URL
   (matches FD-Q4/ID-Q7; requires guaranteeing the presigned host is public/CSP-allowed).
C) Other.

[Answer]: A — same-origin backend proxy; the app streams bytes; clients only ever see `'self'`; no key or internal endpoint is browser-visible.

---

## D5 — Remediation sequencing

F01 and F02 are live cross-tenant exposures; F05/F07 and the job contract are correctness/least-privilege
gaps with no confirmed external exploit yet.

A) **Security-first (recommended)** — land F01 + F02 as a focused hotfix (own regressions, own commit)
   before the F05/F07/job-contract rebuild; everything still tracked under this one plan.
B) One pass — implement F01/F02/F05/F07 + the job contract together and gate once.
C) Minimal — only F01/F02 now; defer F05/F07/job contract to a follow-up unit (leaves G2 not met).

[Answer]: A — security-first: land F01 + F02 as a focused hotfix (own regressions/commits) before the F05/F07/job-contract rebuild; all under this plan.

---

## D6 — Contaminated shared-cache cleanup

The baseline cache key (`gver==0`) is shared across users (`tests/test_pbt.py:45-53`). Existing
entries may already contain results derived from a client-supplied source.

A) **Dry-run count first, back up, then purge only entries not traceable to a server-verified source
   (recommended)** — matches `verification-remediation-2026-09-18.md` §5.
B) Flush the whole shared baseline cache (simplest; warm-up cost).
C) Leave existing entries; enforce correctness only for new writes.

[Answer]: A — dry-run count first, back up, then purge only entries not traceable to a server-verified source.
