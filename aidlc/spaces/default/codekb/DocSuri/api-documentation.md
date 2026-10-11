# DocSuri API Documentation

## Scope and transport

Static source inventory found **108 application HTTP method/path declarations** across health and fourteen module groups, plus **4 operations in the separate platform-integrity API**. Counts are declaration counts, not proof that all routes mount in an environment: module failures/configuration/feature gates can remove or reject surfaces. FastAPI-generated documentation endpoints and Next page routes are not included.

Graph Route nodes were insufficient (only three backend candidates), so a direct Python AST pass over application Python, excluding tests/environments, enumerated HTTP decorators and router prefixes. This is not generated live OpenAPI; dynamic route availability and every field/error branch remain to be verified. Source paths below are relative to the repository.

Browser requests usually use `/bff/<backend-path>`. `frontend/app/bff/[...path]/route.ts` forwards GET/POST/PUT/PATCH/DELETE/OPTIONS, cookies and Set-Cookie; handles selected SSE and image routes; disables job caching; retries eligible GET failures once but not mutations. Production requires an upstream unless explicitly allowing mock mode. Backend paths below omit `/bff`.

Authentication comes from gateway principal/session handling and controller dependencies. Search and session inspection have optional-auth handling; account entry/token flows and signed unsubscribe have distinct rules. Administrator routes require role/MFA. A module-local development app or a direct fake-request test is not the assembled authentication boundary.

## Route inventory

Methods sharing a path are listed together; brace names are path parameters, not literal URLs.

### Health and operations — 5 declarations

Sources: `backend/health.py:19`, `backend/modules/ops/controller.py:80,140`.

| Methods | Path | Purpose / access |
|---|---|---|
| GET | /health; /healthz | application liveness |
| GET | /readyz | configured required-module readiness, not full journey proof |
| GET | /ops/dashboard | administrator/MFA operational summary |
| GET | /ops/incidents | administrator/MFA incident listing |

### Accounts — 22 declarations

Source: `backend/modules/accounts/controller.py:482–1178`. Controller declarations inventoried; all lifecycle payload/error semantics were not deeply audited.

| Methods | Path under /auth | Contract family |
|---|---|---|
| POST | /signup; /login; /resend-verification | credential/verification inputs; session/cookie and public response mapping |
| GET | /verify-email | verification token |
| POST | /password-reset/request; /password-reset/confirm | reset request/token/new credential |
| POST | /change-password | authenticated credential change |
| POST | /email-change/request | authenticated email change request |
| GET | /email-change/confirm; /email-change/revoke | lifecycle token confirmation/revocation |
| POST | /account/delete; /account/reactivate | withdrawal/reactivation |
| GET | /social/google/start; /social/google/callback | OAuth/OIDC redirect and state/code flow |
| GET | /social/orcid/start; /social/orcid/callback | ORCID redirect and state/code flow |
| POST | /social/link | explicit account-link confirmation |
| GET | /session | current session view; optional-auth inspection |
| POST | /logout | session termination |
| POST | /mfa/enroll; /mfa/verify | MFA enrollment/verification |
| GET | /admin/whoami | administrator identity gate |

### Discovery — 2 declarations

Source: `backend/modules/discovery/src/discovery/api/router.py:66,85`.

| Method | Path | Input / output / relevant failures |
|---|---|---|
| POST | /api/search | shared SearchRequest → search result union; validation result 400, normal/degraded result 200, store outage mapped to generic 503 |
| GET | /api/papers/{paper_id} | metadata when paper service is configured; 404 absent paper, generic 503 unavailable store |

Production search ignores spoofable X-User-Id and uses the principal or server anonymous identity. Standalone `build_app` explicitly enables a development identity header; do not substitute it for mounted behavior.

### Library — 10 declarations

Source: `backend/modules/library/controller.py:111–256`. All owner authenticated. List operations accept bounded limit/cursor; saved-search list also accepts query. Domain validation → 422, quota/state conflict → 409, unavailable rerun gateway → 503, absent/foreign item → generalized 404.

| Methods | Path | Contract |
|---|---|---|
| POST, GET | /library/saved-searches | SavedSearchCreateDTO → SavedSearchDTO; list → SavedSearchPageDTO |
| DELETE | /library/saved-searches/{item_id} | 204 |
| POST | /library/saved-searches/{item_id}/rerun | SearchResultSetDTO |
| POST, GET | /library/items | LibraryItemCreateDTO → LibraryItemDTO; list → LibraryPageDTO |
| DELETE | /library/items/{item_id} | 204 |
| GET, DELETE | /library/history | HistoryPageDTO or clear 204 |
| POST | /library/history/{item_id}/rerun | SearchResultSetDTO |

Create returns 201 for new items and 200 when a service reports an existing item.

### Summary, jobs and documents — 12 declarations

Source: `backend/modules/summarization/src/summarization/api/router.py`, mounted by `backend/wiring.py:495`.

| Method | Path | Current mounted behavior |
|---|---|---|
| POST | /api/content-jobs/submit | taskType/input/idempotencyKey → 202 jobId/state receipt; auth 401, invalid task 400, unavailable service 503 |
| GET | /api/content-jobs/{job_id}/state | owner jobId/state/error?/resultRef?; currently missing browser-required seq |
| GET | /api/content-jobs/{job_id}/events | owner event stream; Last-Event-ID or lastEventId resume; current framing regression Q-04 |
| GET | /api/content-jobs/{job_id}/result | owner resultRef only; absent/unready/expired currently 404 |
| POST | /api/summarize | synchronous summary/translation request through orchestration; separate from durable submit |
| GET, POST | /api/glossary | authenticated terminology list/update |
| GET | /api/papers/{paper_id}/doc-model | version query; ok/docModel, building/retryAfterMs, source_unavailable or license_unavailable; storage fault 503 |
| GET | /api/papers/{paper_id}/assets | gated public asset manifest |
| GET | /api/papers/{paper_id}/assets/{asset_id} | gated owned/authenticated public asset byte proxy |
| GET | /api/userdoc/{doc_id}/doc-model | owner-scoped private document read |
| GET | /api/summarization/ready | summary service/store readiness check |

Submit recognizes summarize, translate, novelty, evidence and ingest_userdoc. Do not infer these are all worker-supported through the mounted callback. Public paper document routes refuse private namespace IDs before other branches. Browser result retrieval requires a versioned preparedResult envelope and distinguishes 409/410/422; current producer disagreement is owned in Q-01–Q-03 of [quality assessment](code-quality-assessment.md). The deprecated client-only translate-job helper is not an additional mounted route.

### Citation graph — 2 declarations

Source: `backend/modules/citation_graph/controller.py:374,436`. Feature flag and principal required.

| Method | Path | Contract |
|---|---|---|
| GET | /api/papers/{paper_id}/citation-tree | expandNodeId/refresh → nodes, edges, unresolved, depth/truncation/cache/provider status |
| POST | /api/papers/{paper_id}/citation-tree/save | SaveCitationNodeRequest → library add; unsaveable node 422 |

Provider timeout/rate limit can produce degraded results and cached fallback, not necessarily an HTTP error. Maximum visible nodes is capped at 50.

### Personalization and onboarding — 12 declarations

Sources: `backend/modules/personalization/controller.py:69–168`, `backend/modules/onboarding/controller.py:69–130`. Principal required; personalization routes feature gated.

| Methods | Path | Contract |
|---|---|---|
| POST | /api/personalization/events | behavior event validation/recording |
| GET | /api/personalization/decision/search; /api/personalization/decision/summary-defaults | PersonalizationDecision |
| GET, PATCH | /api/personalization/settings | settings / enabled update |
| POST | /api/personalization/delete-events; /api/personalization/reset-profile | delete recorded events / reset profile |
| GET | /mypage/recently-viewed | RecentlyViewedList |
| GET | /onboarding/status | state and allowed categories |
| POST | /onboarding/interests | InterestSelection → state/eventRecorded/reason |
| POST | /onboarding/skip | skipped state |
| GET | /onboarding/orcid-suggestions | suggestions/degraded; best-effort external lookup |

### My page, trends and plans — 16 declarations

Sources: `backend/modules/mypage/controller.py:70–153`, `trends/controller.py:91–190`, `plans/controller.py:70–129`.

| Methods | Path | Contract / access |
|---|---|---|
| GET, POST | /mypage/subscription | own SubscriptionDTO; POST 201; mock subscription behavior |
| POST | /mypage/subscription/cancel | own subscription cancellation |
| GET | /mypage/account-profile; /mypage/orcid-profile | own profile; missing profile 404 |
| GET, POST | /mypage/consents | own ConsentsDTO / ConsentsUpdate |
| GET, POST | /trends/follows | own FollowListResponse / topic create 201; duplicate/limit 409 |
| DELETE | /trends/follows/{topic_id} | own removal; absent/foreign 404 |
| GET, PUT | /trends/settings | DigestSettingsResponse / optedIn/cadence update |
| POST | /trends/unsubscribe | signed owner token, no login dependency in handler; invalid token 400 |
| GET | /plans/me | own resolved tier, quota and expiry |
| POST | /plans/grants | ADMIN plus MFA, GrantRequest → GrantResponse 201 |
| DELETE | /plans/grants/{user_id} | ADMIN plus MFA, revoke assignment; absent 404 |

No payment API is declared in these controllers.

### Evidence and research sessions — 11 declarations

Sources: `backend/modules/evidence/controller.py:168,276,325`; `evidence/sessions/controller.py:117–284`. Owner principal and configured agent/feature prerequisites; turn creation uses quota checks.

| Methods | Path | Contract |
|---|---|---|
| POST | /api/evidence/turns | topic/scope/papers/attachments → success, abstain, error or pending turn; negotiated SSE |
| POST | /api/evidence/attachments | PDF bytes with fileName/id query → attachment identity/reference |
| GET | /api/evidence/jobs/{job_id} | owner pending/completed turn job view |
| POST, GET, DELETE | /api/research/jobs | create/list/reset sessions |
| GET, DELETE | /api/research/jobs/{job_id} | detail/delete session; generalized 404 |
| GET, POST | /api/research/jobs/{job_id}/messages | list/add messages; POST supports negotiated SSE or pending JSON |
| POST | /api/research/attachments | PDF upload and build enqueue; 415 non-PDF, 422 invalid/unavailable upload |

SSE reports bounded progress and final validated results. A client must handle JSON pending responses even when it requested a stream; replay must not resubmit mutations blindly.

### Novelty and Notion — 16 declarations

Source: `backend/modules/novelty/controller.py:92–360`. Owner-scoped jobs and connections; feature/quota/configuration prerequisites apply.

| Methods | Path | Contract |
|---|---|---|
| POST, GET, DELETE | /api/novelty/jobs | create/list/reset jobs |
| GET, DELETE | /api/novelty/jobs/{job_id} | status/delete |
| POST | /api/novelty/jobs/{job_id}/manuscript | text/Markdown/PDF manuscript input |
| GET | /api/novelty/jobs/{job_id}/result | job/artifacts/export |
| GET | /api/novelty/jobs/{job_id}/events | resumable progress stream |
| GET, POST | /api/novelty/jobs/{job_id}/messages | conversation history / add message |
| POST | /api/novelty/jobs/{job_id}/cancel | cancellation state |
| POST | /api/novelty/jobs/{job_id}/notion/preview | prepare export preview |
| POST | /api/novelty/jobs/{job_id}/notion/approve | explicit approval before external export |
| GET, PUT, DELETE | /api/novelty/notion/connection | own connection status / encrypted token configuration / disconnect |

## Separate platform-integrity API — 4 declarations

Source: `platform_integrity/src/docsuri_platform_integrity/api/app.py:45–154`. Separate loopback/read-only daemon, not a backend mount. Peer identity is derived from verified client-certificate scope, never a caller identity header. Non-loopback peers get 404; metadata without verified identity gets 401; request bodies are rejected. Admission/deadline/response caps bound work.

| Method | Path | Contract |
|---|---|---|
| GET | /healthz | liveness only |
| GET | /readyz | shallow/deep/subjectEligible/reasons; 200 or 503 |
| GET | /internal/v1/evidence/{subject:path} | authorized bounded GateEvaluation; absent/denied 404 |
| GET | /internal/v1/compatibility/{release:path} | exact release compatibility verdict/reasons; absent/denied 404 |

Compatibility observes manifest/artifact/generation/role/schema/config bindings; it does not grant mutation authority.

## Non-HTTP/internal interfaces

- Ingestion CLI: ingest-one, trigger-full-rebuild, schedule-tick; queue worker consumes ingestion/build jobs.
- Ops CLI: run-detectors, run-grounding-eval, run-reliability-eval, dashboard-summary.
- Shared Protocols and JSON schema/event contracts connect retrieval, grounding, cost, history, ingestion and observability.
- Worker queue messages, direct Python repository/service interfaces and platform operational CLI protocols require separate detailed contract extraction before replacement. This inventory does not pretend to be exhaustive message-field documentation.
