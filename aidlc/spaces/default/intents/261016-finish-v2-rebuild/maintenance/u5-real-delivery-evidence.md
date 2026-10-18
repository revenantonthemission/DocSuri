# U5 real delivery evidence preparation

Prepared: 2026-10-19 (Asia/Seoul). Status: not sent. The maintainer selected
Resend and confirmed that no sender address or test recipient exists yet. The
existing account and credential configuration remain unverified. This record prepares the existing U5
real-delivery acceptance check; it does not authorize an external message or
establish completion.

## Provider facts checked

Resend is the maintainer-selected provider, not yet a verified account. Its published
Free plan lists $0, 3,000 emails per month and 100 per day. The account's actual
plan and remaining allowance must be checked separately. A newsletter sent
through its email API requires recipient consent and an unsubscribe mechanism,
including the visible link and the two documented unsubscribe headers.
[Pricing and newsletter guidance](https://resend.com/pricing).

Its send API accepts custom email headers and an initial request idempotency
key. Keys expire after 24 hours; this does not override DocSuri's requirement to
pause uncertain outcomes instead of automatically resending.
[Send API](https://resend.com/docs/api-reference/emails/send-email),
[idempotency keys](https://resend.com/docs/dashboard/emails/idempotency-keys).

A successful API request proves provider acceptance. The provider's delivered
event describes delivery to the recipient's mail server. Neither establishes
inbox placement or reading; those need separately correlated recipient-side
evidence. [Event definitions](https://resend.com/docs/webhooks/event-types).

## Inputs and prepared payload

| Input | Current evidence |
|---|---|
| Existing free provider/account and allowance | Resend selected by maintainer; account, actual plan and allowance not inspected |
| Verified sender and test recipient | Maintainer confirmed neither exists yet; no send can be prepared for a concrete recipient |
| Secure credential configuration reference | Requested; values must remain in server configuration |
| Working owner-bound unsubscribe endpoint | Local assembled cancellation checks passed in the current integration run; public HTTPS reachability, DKIM coverage and deployed logging treatment remain unverified |
| Permitted paper content and owner preferences | To be bound to the repaired application's prepared snapshot |
| Exact subject, text/HTML, links and recipient | To be rendered and shown after local verification, before send approval |
| Explicit approval for one external send | Not requested or granted; sender and recipient must exist first |

The prepared message must come from the repaired application path. A separate
handwritten email or a direct provider smoke test cannot substitute for that
integration. Record its immutable run/request identity, source revision and
payload digest without copying credentials or private recipient data into Git.
The [delivery configuration and preview procedure](../construction/u5-topics-digests/code-generation/delivery-configuration.md)
names the server binding and read-only presentation retrieval. No real message
has been prepared or sent.

Before enabling the provider's one-click unsubscribe headers, verify the actual
endpoint accepts the required request and affects only the intended subscription.
The existing authenticated browser DELETE route is not itself that POST endpoint.
Do not present a configuration flag as integration evidence or weaken owner
checks to make the demonstration pass. Public hosting remains a separate decision.

## Evidence to retain

After explicit approval, attempt at most the authorized message through the
configured application delivery path. Retain the actual transport identity,
provider receipt and acknowledgement time, durable outcome, and correlated
recipient confirmation. A timeout or ambiguous response remains unknown; use
read-only evidence or the approved explicit resolution path, never an automatic
repeat send. A refusal, missing prerequisite or incomplete receipt remains an
open result. Local-sink and mocked-provider tests are recorded separately.

This check remains subject to the approved U5 plan, the $0 limit and the user's
existing review-before-merge instruction. No provider account, domain, public
deployment or paid resource has been created by this preparation.
