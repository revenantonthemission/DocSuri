# U5 digest delivery configuration and bounded demonstration

## Current status — 2026-10-19

**One real digest was sent and reached the inbox.** The second authorized
attempt (realm `docsuri-u5-95df9983c1b017e4`, run
`bdc65d9f-c805-4dbc-bd20-a2a5e650f91c`, sender `no-reply@mail.rvnnt.dev`) ended
`sent` with `pathKind: real`. It was attempted at 05:11:26.544 UTC and
acknowledged at 05:11:26.918 UTC with a provider receipt (SHA-256
`f17b05558fa8cc6c336532267eb17a19b13934d90513317ebe5566f62e0e9064`). The person
confirmed it arrived in their inbox, and that their mail app's one-click
unsubscribe worked. The realm's allocation is spent (1 of 1).

The browser confirmation button on the public cancellation page failed with the
boundary's `request.origin` refusal (review finding R-15). It is fixed in source
and covered by automated tests, but not re-run live. The tunnel change is rolled
back and the U5 host is stopped. Full facts, the first failed attempt and the
retention deadlines are in the evidence register
[`../../../maintenance/u5-real-delivery-evidence.md`](../../../maintenance/u5-real-delivery-evidence.md).

## Decided configuration (the person's decisions)

| Decision | Value |
|---|---|
| Provider | Resend, free plan; no SES, paid or mock-success fallback |
| Sender | `no-reply@mail.rvnnt.dev` (a domain Resend lists as `verified`); the first attempt's `no-reply@docsuri.rvnnt.dev` was not verified |
| Recipient scope | exactly one permitted recipient, the address the person gave (masked `c***@icloud.com` in committed files); the scheduler reads only that account's due topics and queued runs |
| Public unsubscribe origin | `https://docsuri.rvnnt.dev`, reached through the existing Cloudflare tunnel with one path-scoped rule (runbook section 4), applied only for the demonstration and rolled back afterwards |
| Budget | one real attempt **per realm database**; failures and receipt expiry never replenish it. Account erasure (cascade) and a fresh realm each reset the count, so an operator must not do either to retry |
| Retention | real-send evidence kept 30 days (`evidence_retain_until = attempted_at + 30 days`, DB-enforced maximum); preserved realms are deleted by the operator before that deadline |
| Shared-device treatment | unchanged: a single-use, run-bound cancellation capability that works without signing in; only its hash is stored |
| Cost | $0 |

## Real-delivery wiring

| Piece | Where | Behaviour |
|---|---|---|
| Real composition | `backend/u5_real_delivery.py` → `assemble_u5_real` | Builds the owned U5 host with the Resend adapter (`digest_mail_binding(synthetic=False)`), policy `REAL_DEMONSTRATION_TOPICS` (`u5-real-demonstration`, limit 1, 30-day retention) and an `EmailUnsubscribe` bound to the public origin with an explicit aware expiry. Any missing or invalid input refuses; there is no fallback. The synthetic `assemble_u5` is unchanged. |
| Host flag | `scripts/serve_docsuri_u5.py --real-delivery` | Without the flag the host is synthetic and never reads provider variables, even when they are set. |
| Activation file | `<realm>/real-delivery.json` (owner-only, run-bound) | Non-secret decisions: `runId`, `sender`, `permittedRecipient`, `unsubscribeOrigin`, `capabilityExpiresAt`, and the operator gates `freePlanVerified` and `unsubscribeEndpointVerified`. Exactly these fields; anything but `true` refuses. |
| Credential | process environment only | `EMAIL_PROVIDER=resend`, `RESEND_API_KEY` (must have the `re_…` shape). Never written, echoed, logged or placed in an error. The verification runner strips both from its children. |
| Scheduler recipient filter | `backend/modules/topics/scheduler.py`, `repository.py` | In the real composition, only the permitted recipient's due topics and queued runs are read, filtered before the bounded page, so another account can never spend the attempt. |
| Retention migration and sweep | `backend/modules/topics/u5_real_send_retention.sql`, scheduler sweep | Each real attempt stamps `evidence_retain_until`. After it, a settled run's receipt is cleared; the row stays, so the allocation is not replenished. |
| Refusal detail | `backend/modules/topics/u5_refusal_detail.sql`, `digest_email.py` | A provider refusal records the HTTP status and Resend's error `name` (or `name-unavailable`), set once. Local pre-network refusals have their own reasons. The key, headers, body and free-text `message` are never stored. |
| Origin middleware | `backend/modules/topics/unsubscribe.py` → `PublicCancellationOrigin` | Real composition only, installed outermost. On the exact 43-character cancellation path, for GET and POST only, it drops an `Origin` equal to the approved origin, and restores the page's own headers (`Referrer-Policy: same-origin`, its CSP) over the boundary's. Any other origin, including `null`, is still refused. |
| Operator tool | `scripts/u5_real_delivery.py --action check\|provision\|prepare\|preview\|outcome` | Never constructs the adapter, issues a capability or reads the key's value. |

## Verification results

| Result | Evidence |
|---|---|
| Real wiring first verified: 207 passed, 0 failures/errors/skips, 84.52% aggregate | realm `docsuri-u5-482869d6a89fa6c3`, `/private/tmp/docsuri-u5-preserved-docsuri-u5-482869d6a89fa6c3-9efdf694/coverage-evidence-1792384373649846000.json` |
| Refusal detail: 250 passed, 84.93% aggregate | realm `docsuri-u5-287134e8035e6532` (see code-summary.md) |
| R-15 browser confirmation fix: 255 passed, 0 failures/errors/skips, 85.01% aggregate | fresh realm `docsuri-u5-5302ce36da2f4551`, `/tmp/docsuri-u5-run/coverage-evidence-1792387423998293000.json` |

All of these use a fake transport and fake credentials; none is evidence of
delivery. The real delivery evidence is the attempt-2 record above.

## Preview without sending

The persisted immutable presentation is `topics.digest_run.presentation`, with
its matching `preference_snapshot` and `request_key`. The authoritative preview
of an actual run is `scripts/u5_real_delivery.py --action preview` (runbook
section 7). It prints the exact subject, text, HTML, sender, recipient, the
appended `Unsubscribe:` line and link, `List-Unsubscribe`,
`List-Unsubscribe-Post: List-Unsubscribe=One-Click`, the `Idempotency-Key` and
the endpoint, with the bearer token redacted. The capability is issued only at
send admission, once; its plaintext is never stored. Keep the recipient address
out of committed files. A synthetic fixture is never permission to contact a
person.

## Rules for any further demonstration

Use one permitted prepared run and the realm's one-attempt budget, after the
person approves the exact preview and recipient. Record `pathKind=real`, the
request identity, the provider receipt and acknowledgement time, and correlate
recipient-side evidence separately: provider acceptance alone does not prove
inbox placement or reading. A lost or ambiguous response stays `unknown`;
reconciliation reads existing evidence and never issues another POST. No public
hosting, deployment, account creation, paid fallback or production migration is
authorized by this procedure.

## Historical: first authorized attempt — 2026-10-19

Kept as recorded at the time; the current status above supersedes it.

| Fact | Recorded value |
|---|---|
| Realm | `docsuri-u5-a4ed677392fc22d7` (preserved, not deleted: `/private/tmp/docsuri-u5-preserved-docsuri-u5-a4ed677392fc22d7-fe26b52f`, volume `docsuri-u5-a4ed677392fc22d7-pgdata`) |
| Run | `2ea6c002-f993-4cc6-9add-36a7867cb911`, window 2026-10-13 to 2026-10-19 |
| Attempted at | 2026-10-19 04:49:59 UTC (`attempted_at` 04:49:59.301549+00:00) |
| Path | `pathKind: real` (Resend adapter) |
| Outcome | `failed`, failure reason `delivery-path-refused`, not reconciled |
| Provider receipt / acknowledgement | none / none |
| Budget | that realm's single real-send allocation is spent (`spent 1`, `remaining 0`) |
| Evidence retained until | 2026-11-18 04:49:59 UTC |

The `failed` outcome meant the transport classed the result as a definite
refusal. It recorded no status code then, and the same reason also covered
local pre-network refusals, so whether Resend was reached, and why, cannot be
proven. Resend's dashboard showed no log. Most likely cause (not proven): the
unverified sending domain `docsuri.rvnnt.dev`; a later read-only
`GET /domains` (status 200) listed only `mail.rvnnt.dev` as verified. In
response: refusal detail was added (`u5_refusal_detail.sql`), the sender moved
to `no-reply@mail.rvnnt.dev`, and the runbook gained the read-only
`GET /domains` pre-send check.

## Historical: status before the first attempt

Before the first attempt there was no sender address or test recipient, and no
external send was authorized. Local checks used `local-sink` and could not
establish real acceptance or inbox delivery. The binding was described then as
the account-owned `digest_mail_binding` with `synthetic=False`,
`provider=resend` and server-held `apiKey`, `sender`, `permittedRecipient`,
`unsubscribeUrl`, `freePlanVerified` and `unsubscribeEndpointVerified`, with the
two booleans as fail-closed composition gates rather than evidence. That is the
binding `assemble_u5_real` now composes, from the activation file and the
environment as described above.
