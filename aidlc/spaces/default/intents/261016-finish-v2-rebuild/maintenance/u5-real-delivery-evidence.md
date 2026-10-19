# U5 real delivery evidence

Updated: 2026-10-19 (UTC times below). **Status: one real digest was sent and
reached the inbox.** The provider accepted it with a receipt, and the person
confirmed it arrived in their inbox. The mail app's one-click unsubscribe worked.
The browser's "구독 해지 확인" button on the public cancellation page did not; it
has been fixed in source and covered by automated tests, but not re-run live.

The recipient is masked as `c***@icloud.com` in every authored file. The one
exception is the engine-written AI-DLC audit shard
(`../audit/mac-mini-eab026d8eae1.md`), which records the two send-approval
questions verbatim, address included; only AI-DLC's tools may write it. The
person chose on 2026-10-19 to commit it as is, because the same address is
already public in this repository. The
plaintext provider receipt is not committed: it stays only in the preserved
realm database, and only its SHA-256 is recorded here, because git history
outlives the 30-day retention (runbook section 9).

## Attempt 1 — failed (provider path refused)

| Fact | Recorded value |
|---|---|
| Realm | `docsuri-u5-a4ed677392fc22d7`, preserved at `/private/tmp/docsuri-u5-preserved-docsuri-u5-a4ed677392fc22d7-fe26b52f`, volume `docsuri-u5-a4ed677392fc22d7-pgdata` |
| Run | `2ea6c002-f993-4cc6-9add-36a7867cb911`, window 2026-10-13 to 2026-10-19 |
| Sender | `no-reply@docsuri.rvnnt.dev` |
| Attempted at | 2026-10-19 04:49:59.301549 UTC |
| Path | `pathKind: real` (Resend adapter) |
| Outcome | `failed`, `delivery-path-refused`; no receipt, no acknowledgement |
| Allocation | 1 of 1 spent (failures never replenish it) |
| Evidence retained until | 2026-11-18 04:49:59 UTC |

Cause: most likely an unverified sending domain, not proven. The code at the
time recorded no provider status. A later read-only `GET /domains` (status 200)
listed only `mail.rvnnt.dev` as verified, and Resend's dashboard showed no log
for the attempt. In response, refusals now record the HTTP status and Resend's
error name (`u5_refusal_detail.sql`), and the sender moved to the verified domain.

## Attempt 2 — sent, inbox delivery confirmed

Read from the realm with the read-only `scripts/u5_real_delivery.py --action
outcome` before the realm was archived:

| Fact | Recorded value |
|---|---|
| Realm | `docsuri-u5-95df9983c1b017e4`, preserved with `archive-owned` at `/private/tmp/docsuri-u5-preserved-docsuri-u5-95df9983c1b017e4-b5081e79`, volume `docsuri-u5-95df9983c1b017e4-pgdata` (container stopped, nothing deleted) |
| Run | `bdc65d9f-c805-4dbc-bd20-a2a5e650f91c`, window 2026-10-13 to 2026-10-19 |
| Sender | `no-reply@mail.rvnnt.dev` (domain listed `verified` by Resend) |
| Recipient | `c***@icloud.com`, the one permitted recipient |
| Path | `pathKind: real` (Resend adapter) |
| State | `sent` (observed `sent`, not reconciled) |
| Attempted at | 2026-10-19 05:11:26.544134 UTC |
| Acknowledged at | 2026-10-19 05:11:26.918413 UTC |
| Provider receipt SHA-256 | `f17b05558fa8cc6c336532267eb17a19b13934d90513317ebe5566f62e0e9064` |
| Allocation | 1 of 1 spent, 0 remaining |
| Evidence retained until | 2026-11-18 05:11:26 UTC |

- **Provider acceptance:** the receipt above, persisted before the outcome.
- **Inbox delivery:** the person confirmed the email arrived in their inbox.
  Provider acceptance plus that confirmation is the recorded inbox delivery.
- **Mail-app one-click unsubscribe:** worked. The person used their mail app's
  built-in unsubscribe, which sends the header-less RFC 8058 POST.
- **Browser confirmation: failed.** Opening the emailed link and pressing
  "구독 해지 확인" returned
  `{"code":"FORBIDDEN","messageKey":"request.origin","requestId":"boundary","retryable":false}`.

## Browser confirmation failure (review finding R-15)

Root cause, reproduced locally against the real host boundary with no network:

1. The host boundary (`backend/local_host.py`, `local_boundary`) writes
   `Referrer-Policy: no-referrer` and its own CSP on every response, replacing the
   cancellation page's headers.
2. Under the Fetch standard's "append a request `Origin` header" step, a
   non-CORS, non-GET request (the page's own form POST) serializes its `Origin`
   as `null` when the document's policy is `no-referrer`.
3. `PublicCancellationOrigin` removed only the exact approved origin, so
   `Origin: null` reached the boundary, which refuses any origin other than the
   host's own. Earlier endpoint checks used header-less POSTs and missed this.

Fix (`backend/modules/topics/unsubscribe.py`): the cancellation page and its POST
answer declare `Referrer-Policy: same-origin`. In the real composition only,
`PublicCancellationOrigin` (outermost; exact path; GET and POST only) restores
the page's own headers over the boundary's. Under `same-origin`, a same-origin
form POST carries the document's real origin, `https://docsuri.rvnnt.dev`,
which the middleware already admits. The token URL is still never sent as a
cross-origin referrer, and the page's CSP (`default-src 'none'; form-action
'self'; frame-ancestors 'none'`) now actually reaches the browser. Nothing else
was widened: `Origin: null`, foreign origins, other paths, other methods and the
synthetic host are unchanged.

Tests (no network): `tests/u5_topics_digests/component/test_real_composition.py`
derives the browser's `Origin` from the served `Referrer-Policy` with a Fetch-rule
helper (`tests/u5_topics_digests/fetch_origin.py`). It confirms that the old
`no-referrer` header produced the refused `null`, and that the new page passes
through the real boundary. `tests/u5_topics_digests/integration/test_real_delivery.py`
repeats the browser case through the full `assemble_u5_real` app against the
realm store, with refusal of `null`, foreign origins and other paths, plus a
header-less one-click POST. Coverage run: 255 passed, 0 failures, errors or
skips, 85.01% aggregate (80% floor), fresh realm `docsuri-u5-5302ce36da2f4551`,
evidence `/tmp/docsuri-u5-run/coverage-evidence-1792387423998293000.json`.

**Not re-run live.** The fixed browser path has automated coverage only. A
live re-check needs a running real host and the tunnel rule, and the realm that
sent has no allocation left.

## Tunnel and host

After the send, the Cloudflare tunnel change (runbook section 4) was rolled
back and the U5 host was stopped. The exact rollback time was not recorded in
this session. Neither was touched while preparing this record.

## Retention obligations

The preserved realm for attempt 2 holds the plaintext receipt and the
recipient's account address. On or before **2026-11-18 05:11:26 UTC** the
operator must delete volume `docsuri-u5-95df9983c1b017e4-pgdata` and directory
`/private/tmp/docsuri-u5-preserved-docsuri-u5-95df9983c1b017e4-b5081e79`. The
attempt 1 realm (no receipt, but the recipient address) has the deadline
2026-11-18 04:49:59 UTC. Nothing deletes either automatically. Resend keeps its
own logs under its plan's retention.

## Provider facts (checked during preparation)

Resend's published Free plan lists $0, 3,000 emails per month and 100 per day.
A newsletter sent through its API requires recipient consent and an unsubscribe
mechanism, including the visible link and the two unsubscribe headers
([pricing](https://resend.com/pricing)). Its send API accepts custom headers
and an idempotency key that expires after 24 hours
([send API](https://resend.com/docs/api-reference/emails/send-email),
[idempotency keys](https://resend.com/docs/dashboard/emails/idempotency-keys)).
A successful API request proves provider acceptance only
([event types](https://resend.com/docs/webhooks/event-types)); inbox placement
here rests on the person's confirmation.

Procedure: [runbook](../construction/u5-topics-digests/code-generation/u5-real-delivery-runbook.md),
[delivery configuration](../construction/u5-topics-digests/code-generation/delivery-configuration.md).
