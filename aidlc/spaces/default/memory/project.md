# Project-Level Rules

> Project-specific specialisation and corrections. Loaded after `org.md` and
> `team.md` as strict-additive guidance; contradictions with broader policy
> are rejected. Populated by practices-discovery and the self-learning loop.
>
> Use sparingly: most teams don't need a project layer. Reach for it
> only when this specific project needs stable, durable guidance beyond the
> team practice (for example, package-specific release checks or an additional
> regression suite for a legacy component).

## Way of Working

<!-- Project-specific specialisation. Example: -->
<!-- This monorepo requires package-scoped branch names and a package owner -->
<!-- review in addition to the team's normal merge policy. -->

## Walking Skeleton

<!-- Project-specific specialisation. Example: -->
<!-- The walking skeleton must exercise the legacy service adapter as well -->
<!-- as the new service boundary. -->

## Testing Posture

<!-- Project-specific specialisation. -->

## Guard Policy

<!-- Project-specific. Mode: strict, relaxed, or off. Strict here holds for every intent and cannot be changed from chat. A section under the retired Change Control heading, written by an earlier release, is still read. -->

## Deployment

<!-- Project-specific specialisation. -->

## Code Style

<!-- Project-specific specialisation. -->

## Tech Stack

<!-- Technology choices locked for this project. -->

## Decided

<!-- Decisions made in earlier stages that should not be re-asked. -->
<!-- Format: DECIDED: [decision] (Stage [slug], [date]) -->

## Scope Overrides

<!-- Custom scope rules for this project. -->

## Forbidden

<!-- Populated by practices-discovery affirmation gate. -->
<!-- Format: NEVER [behavior] (affirmed [date]) -->
<!-- Example: NEVER throw exceptions across service layer boundaries (affirmed 2026-05-17) -->

- NEVER route content-job API calls directly to `/api/content-jobs/*` (bypasses BFF, violates SEC-8) (affirmed 2026-10-02)

- NEVER use presigned URLs for asset delivery (violates SECURITY-08) (affirmed 2026-10-02)

- NEVER skip auth re-check at asset delivery time (violates SEC-9) (affirmed 2026-10-02)

- NEVER use `axios` for HTTP — use native `fetch` + custom Transport (affirmed 2026-10-02)

- NEVER use `@tanstack/react-query` — use SWR (lighter, already in stack) (affirmed 2026-10-02)

- NEVER use `lodash` — use native JavaScript (affirmed 2026-10-02)

- NEVER use `moment.js` — use native `Date` / `Intl` APIs (affirmed 2026-10-02)

- NEVER use `classnames` — use `clsx` (lighter, same API) (affirmed 2026-10-02)

- NEVER use `styled-components` or `@emotion/*` — use CSS Modules + Tailwind (affirmed 2026-10-02)

- NEVER use `moment` or `date-fns` — use native `Intl.DateTimeFormat` (affirmed 2026-10-02)

- NEVER hardcode API base URLs — use `/bff/api/content-jobs` constant (affirmed 2026-10-02)

- NEVER skip Error Boundary on SSE-consuming components (affirmed 2026-10-02)

- NEVER skip ARIA live region on real-time status components (affirmed 2026-10-02)

- NEVER skip polling fallback on SSE connections (affirmed 2026-10-02)

- NEVER store secrets in client-side code or localStorage (affirmed 2026-10-02)

- NEVER commit `.env` files or secrets to git (affirmed 2026-10-02)

- NEVER skip lint, typecheck, or test:coverage in CI (affirmed 2026-10-02)

- NEVER reduce coverage floor below 80% for feature scope (affirmed 2026-10-02)

- NEVER merge without CI passing (lint + typecheck + test + e2e) (affirmed 2026-10-02)

## Mandated

<!-- Populated by practices-discovery affirmation gate. -->
<!-- Format: ALWAYS [behavior] (affirmed [date]) -->
<!-- Example: ALWAYS use Result<T,E> for fallible operations in service layer (affirmed 2026-05-17) -->

- ALWAYS route all content-job API calls through `/bff/api/content-jobs/*` (SEC-8 compliance — gateway injects principal) (affirmed 2026-10-02)

- ALWAYS generate idempotency keys as SHA-256 hash of `userId:paperId:taskType:JSON.stringify(params)` for deterministic retry (affirmed 2026-10-02)

- ALWAYS store idempotency keys in `localStorage` with key format `idempotency:{paperId}:{taskType}` (survives page reload) (affirmed 2026-10-02)

- ALWAYS use native `EventSource` for SSE with `Last-Event-ID` header for resume on reconnect (affirmed 2026-10-02)

- ALWAYS implement polling fallback (SWR 2s fixed interval) when SSE fails (affirmed 2026-10-02)

- ALWAYS wrap JobStatus in React Error Boundary for graceful degradation (affirmed 2026-10-02)

- ALWAYS use same-origin asset delivery via `/bff/api/papers/{paperId}/assets/{assetId}` (no presigned URLs) (affirmed 2026-10-02)

- ALWAYS forward session cookie through BFF proxy for gateway authentication (affirmed 2026-10-02)

- ALWAYS relay Set-Cookie headers from gateway back to browser (affirmed 2026-10-02)

- ALWAYS use native `fetch` + custom Transport interface for all API calls (affirmed 2026-10-02)

- ALWAYS use SWR for server state management (stale-while-revalidate) (affirmed 2026-10-02)

- ALWAYS use `clsx` + `tailwind-merge` for conditional className composition (affirmed 2026-10-02)

- ALWAYS use CSS Modules + Tailwind CSS for styling (affirmed 2026-10-02)

- ALWAYS use native `crypto.subtle` for cryptographic operations (SHA-256 hashing) (affirmed 2026-10-02)

- ALWAYS use native `EventSource` API for SSE consumption (affirmed 2026-10-02)

- ALWAYS use strict TypeScript — no `any`, no implicit any, strict null checks (affirmed 2026-10-02)

- ALWAYS run lint, typecheck, and test:coverage before merge (CI gate) (affirmed 2026-10-02)

- ALWAYS maintain ≥80% line coverage for new code (feature scope floor) (affirmed 2026-10-02)

- ALWAYS keep existing test suites green (473 backend + 356 frontend) (affirmed 2026-10-02)

- ALWAYS run walking skeleton ceremony for this feature — first Unit is smallest working slice, run through all stages, verify with Construction Verification Command, require human checkpoint approval (affirmed 2026-10-02)

- ALWAYS follow test-last per component ordering — implement component fully, then write tests (affirmed 2026-10-02)

- ALWAYS deploy continuously to production on merge — every commit passing CI auto-deploys to production (affirmed 2026-10-02)

- ALWAYS conduct security review mid-implementation (Week 2) for AssetViewer migration (SEC-8/SEC-9) (affirmed 2026-10-02)

- ALWAYS integrate Sentry for client-side error tracking in Phase 7 (affirmed 2026-10-02)

--- (affirmed 2026-10-02)

## Corrections

<!-- Project-specific corrections from human feedback. -->
<!-- Format: NEVER/ALWAYS [behavior] (learned [date]) -->
- Separated same-key submission recovery from re-execution of a terminal failed job. The human selected same-parameter recovery only; requirements must not promise a restart that the backend idempotency contract does not provide. (learned 2026-10-03) <!-- cid:261001-rem-2-phase-7-frontend-v:requirements-analysis:79a69179587122017ed67c5c697f9d6272aa2d67a3c3b42293bb3df3efca4140 -->
- Treat historical CodeKB readiness claims as evidence to recheck against the current code and contracts before planning integration work; source spot-checks found BFF streaming and result-reference gaps that the old inventory described as ready, so the story handoff now names those prerequisites instead of claiming compatibility. (learned 2026-10-03) <!-- cid:261001-rem-2-phase-7-frontend-v:user-stories:a8b6d990cfe455319c63807a39afcb083c5f90757b4a2ace3a2056fffdc6439a -->
- Inspect existing UI request triggers before reusing a component as a read-only result view; SummaryModal currently requests work on mount and persona changes, so result-view design must explicitly separate reading a completed result from initiating work and preserve the intended initial parameter choices. (learned 2026-10-03) <!-- cid:261001-rem-2-phase-7-frontend-v:refined-mockups:cc0070bab92cff94bbec22a049f657822c7cf78cc6be0780c20eb2b4b94e1153 -->
- The human approved the proposed rebuild plan with the explicit choice "Approve". Start the plan for this piece of work; no reusable scope was requested by that choice. (learned 2026-10-10) <!-- cid:261010-docsuri-v2-rebuild:intent-capture:0f939d6637c59a9249475cee236b2d208d661c99a47328f845c26e685c1f4178 -->
- Use CONVENTIONS.md as the authoritative Git workflow for DocSuri: working branches merge into develop through a GitHub PR, and releases promote develop to main. The human explicitly selected this workflow after the conflicting direct-to-main convention was presented; this decision supersedes that conflicting convention for this project. Follow the branch naming and version-tag conventions in CONVENTIONS.md as well. (learned 2026-10-10) <!-- cid:261010-docsuri-v2-rebuild:intent-capture:3a31e57dcfd7ff133d1b6205f3117d0fa923ad3a508da079a6e10905ddafb1b7 -->
