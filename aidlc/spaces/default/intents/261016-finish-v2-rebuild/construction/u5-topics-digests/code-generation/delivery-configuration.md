# U5 digest delivery configuration and bounded demonstration

Resend is the selected adapter. The human confirms there is currently no sender
address or test recipient. No external send is authorized. Local checks use
`local-sink` and cannot establish real acceptance or inbox delivery.

## Required binding

The existing account-owned `digest_mail_binding` accepts `synthetic=False`,
`provider=resend` and server-held configuration: `apiKey`, `sender`,
`permittedRecipient`, `unsubscribeUrl` (HTTPS origin only), `freePlanVerified`
and `unsubscribeEndpointVerified`. The two booleans are fail-closed composition
gates, not independent evidence that the external assertions are true. Verify the
actual account plan, quota, sender/domain, public routing and DKIM before setting
them. Credentials stay in inherited server custody, outside documents/logs/browser
state. Local/test profiles reject real configuration regardless of ambient keys.

Inject this adapter and a Topics-owned `EmailUnsubscribe` capability into U5's
existing application, with the same verified HTTPS origin and an explicit aware
expiry. Select retention and shared-device/privacy treatment before activation.
The policy must allow a finite real-send budget (one for this demonstration).
The durable send log counts attempts; failures do not replenish this budget.
Keep URL access logs disabled at the app and proxy, including error paths. Verify
the external route actually supports inert GET and cookie-free RFC8058 POST.
An environment URL alone is insufficient evidence.

## Preview without sending

The persisted immutable presentation belongs to `topics.digest_run.presentation`
and its matching `preference_snapshot` and `request_key`. The authenticated
read-only `GET /api/v2/topics/{topicId}/settings` returns each owner's
`runs[].presentation` through `TopicView`; it never initiates a send. Match the
selected immutable `runId`. Inspect it in the Topics workspace
using the intended owner session. There is no real prepared message to preview
yet, because a recipient/sender and permitted real run have not been established.
Do not use a synthetic fixture as permission to contact a person.

Before authorization, preserve the exact subject/text/HTML, run/request identity,
source revisions, recipient and sender privately. Show the human the exact message
and recipient. Transport appends `Unsubscribe: <run-bound URL>` to text and
`Unsubscribe / 구독 해지` to HTML, plus `List-Unsubscribe` and
`List-Unsubscribe-Post: List-Unsubscribe=One-Click`. Include these additions in
the preview; redact the bearer token from public evidence. The capability itself
is issued only for the admitted sending run, once, and cannot authorize other
actions. Its plaintext is never stored in the database.

## Separate authorized demonstration

After the prerequisites and explicit recipient/message approval exist, use one
permitted prepared run and the one-attempt budget. Record `pathKind=real`, the
stable request identity, actual provider acknowledgement and acknowledgement
time. Correlate recipient-side evidence separately: provider acceptance alone
does not prove inbox placement or reading. A lost/ambiguous response remains
unknown. Reconciliation reads existing evidence and never issues another POST;
the provider idempotency window cannot justify retrying an expired key.

No public hosting, deployment, account creation, paid fallback or production
migration is authorized by this procedure. Missing prerequisites keep real delivery and
unit completion open. The parent-maintained evidence register is
`../../../maintenance/u5-real-delivery-evidence.md`.
