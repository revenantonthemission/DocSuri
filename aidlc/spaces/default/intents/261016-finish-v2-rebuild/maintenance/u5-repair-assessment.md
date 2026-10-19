# U5 repair assessment

Date: 2026-10-18. Examined revision: `8ba35b90`, branch
`feature/u5-topics-digests`.

This is a candidate repair assessment, not an approved replacement code plan,
implementation, new independent review, or completion receipt. It was prepared
while the recorded choice between repairing/re-reviewing U5 and retrying the
browser check on a fresh realm remained unanswered. The reviewed source and
stage artifacts were not changed during this assessment. No external email,
provider-account inspection, credential inspection, or runtime mutation was
performed.

## Current evidence

The [independent review](../construction/u5-topics-digests/code-generation/reviews/review-02.md)
is **NOT-READY**, with four Major and two Minor findings. Fresh backend coverage
passed 81 tests with 87.87% aggregate coverage; the subsequent browser checkpoint
failed with one passing journey, one failure, and one journey not run. The
[recovery record](u5-verification-recovery.md) preserves commands, run identities,
proof IDs, and evidence locations. Neither backend coverage nor a local-sink
acknowledgement establishes completed U5 parity or real email delivery.

The recommendation remains to repair all six findings, isolate browser fixtures,
and obtain a fresh independent review before any PR merge into `develop`.

## Proposed changes and closure evidence

| Review finding | Candidate change | Required evidence |
|---|---|---|
| R-01, Major: unsafe standalone collection command | Correct both recorded commands to include `--collect-only` and the explicit `tests/u5_topics_digests` path. | Collection from the repository root succeeds and is restricted to U5. The existing correct invocation collects 81 tests; the final count may increase with repairs. |
| R-02, Minor: missing empty-digest browser journey | Add the promised mounted empty-state journey while retaining the existing delivery journey. | Browser observes a genuinely empty eligible content window, truthful state, and no fabricated send success; normal navigation remains usable. |
| R-03, Minor: inaccurate corpus-selection comment | Describe the actual direct eligibility/purpose/withdrawal filters under the transaction. Preserve applied migration integrity. | Comment agrees with inspected selection code; no applied hash ledger is rewritten. A corrected migration file requires a fresh realm or an explicitly supported upgrade path. |
| R-04, Major: missing preference inheritance | Read language/level from the existing Personalization authority, expose its required application bindings, and render from a preparation-time snapshot. | Different owners' settings affect only their own prepared presentation; stale updates, replay, consent boundaries, and restart/adoption remain correct. Disclosure alone cannot close FR1.2. |
| R-05, Major: global scheduling timezone | Resolve owner timezone through an explicit owner-owned contract before due filtering and use the same zone/instant for window construction. | Different owner zones at the same UTC instant, local midnight, weekly weekday boundaries, DST transitions, and timezone changes behave according to the documented policy. |
| R-06, Major: no real delivery binding/evidence | Add explicit transport/policy configuration and typed acceptance/refusal/unknown outcomes with provider receipts. Keep synthetic profiles network-disabled. | Contract/fault tests, truthful `pathKind`, duplicate/recovery checks, and separately authorized bounded real delivery evidence under a verified $0 account. |

The corrected collection command is:

```bash
backend/.venv/bin/python -m pytest -c backend/pytest.u5-topics-digests.ini --collect-only -q tests/u5_topics_digests
```

## Preference and timezone integration

`backend/modules/personalization/guarded_service.py` owns the current language
and level settings through
`personalization.settings.defaults.assistanceDefaults`. It supports `en`/`ko`
and currently `standard`. Its fallback language is `en`. The separate SQL
`language` column defaults to `ko` but is not the field used by this API; using
it would misread the current user setting.

`backend/modules/accounts/control_http.py` and `control_repository.py` expose
profile updates for display name, affiliation, and biography. They are not an
existing language/level/timezone API. No complete timezone API/store was found
in the bounded C02/C03 contracts examined. Shared digest contracts already name
`timeZone`, so the repair must coordinate that requirement with the authoritative
owner instead of creating per-topic preference ownership.

The U5 assembly inherits U4/U3, but `backend/u3_host.py` does not mount the C03
settings router. Merely adding that router is insufficient:
`GuardedSettingsService` currently chooses `account-control` only for the
account-controls realm and would choose consent-gated `local-research` in U5.
Manual settings must remain usable after research/behavior consent withdrawal,
while digest work and sending must still honor their current consent checks.

The worker also needs a narrow owner-authorized preference-read boundary; the
existing browser-session service is not a background-worker contract. The
account-owned `accounts.digest_recipient` function demonstrates a restricted
cross-component boundary, but does not itself supply preferences. Preparation
should freeze language, level, timezone, source revision, and resulting
presentation as run evidence. That snapshot must not become another mutable
preference store or silently rewrite sent/unknown work.

Policy details still to resolve during repair are timezone ownership and its
default/migration treatment, timezone changes for queued windows, and the
required content behavior for supported levels. Adding capability labels or
preference stamps without consuming the values would not implement the feature.

## Migration constraints

The U5 chain already includes `personalization.settings` and its receipt table
through `scripts/bootstrap_docsuri_u1.py`. It selectively includes U3/U4 and U2
lifecycle fragments, rather than all U2 account controls. Importing
`accounts/u2_controls.sql` wholesale would collide with U3's `session.purpose`
and U5's lifecycle revision/tables.

Use targeted additions and verify both fresh installation and upgrade from the
current U5 chain. Preserve the runner's refusal of changed applied migration
bytes. Update the existing test assumption that `u5_run_guard.sql` must be the
last migration if new migrations follow it. Test restricted cross-owner access
and inherited U3/U4 behavior as well as the new tables or functions.

## Real transport and uncertain outcomes

`DigestDelivery` already accepts an injected mail client, and the existing
accounts email interface exposes `send_digest_email`. The U5 host supplies no
client, so the assembled path uses `env="local"`; `path_kind()` always returns
`local-sink`, including if a caller injects a real client. Configuration alone
cannot repair these claims.

Both current real adapters return `False` after transport exceptions. U5 maps
that to failure, although a lost response may follow an accepted send. Resend's
adapter discards the response body, and the SES adapter only logs its message
ID. A real binding therefore requires preserving a typed outcome and receipt,
not just selecting an existing client. The existing U5 repository already has
receipt/acknowledgement evidence and unknown-outcome reconciliation operations.

The proposed digest transport result distinguishes accepted, refused, and
unknown. Persist real receipts and acknowledgement time; a timeout, lost
response, or malformed success response must not become a definite refusal.
Unknown outcomes remain paused unless evidence resolves them. Derive transport
identity from the actual adapter, independently of whether content is synthetic.
Reject invalid provider names, incomplete configuration, and policy/adapter
mismatches. Local/test profiles must refuse real network delivery even when
ambient credentials are present; no implicit SES, paid, or mock-success fallback.

Resend is a candidate, not a selected provider. Its official Free plan currently
lists 3,000 emails per month and 100 per day. Verify the actual account plan and
remaining quota before relying on those limits. SES is metered and cannot be
assumed to provide a $0 fallback. [Resend pricing](https://resend.com/pricing),
[AWS pricing announcement](https://aws.amazon.com/blogs/messaging-and-targeting/introducing-amazon-simple-email-service-ses-pricing-plans/).

Resend documents 24-hour idempotency keys and retrieval by email ID. If selected,
bind a stable key to the immutable run/request; expiry and missing evidence do
not authorize blind replay. `email.sent` represents successful API submission,
and `email.delivered` represents acceptance by the recipient mail server, not
inbox placement or reading. Preserve those distinctions in the UI and evidence.
[Idempotency](https://resend.com/docs/dashboard/emails/idempotency-keys),
[email retrieval](https://resend.com/docs/api-reference/emails/retrieve-email),
[event definitions](https://resend.com/docs/webhooks/event-types).

Tests should cover accepted/refused/unknown responses, receipt persistence,
crash reconciliation, concurrent attempts, changed payloads, and expired
idempotency windows. Existing consent, recipient, unsubscribe, single-flight,
and watermark guards must remain effective. A real-adapter fixture can test
`pathKind=real` with a fake transport; it is not real delivery evidence.

Before one external demonstration, establish a permitted $0 provider account,
verified sender, securely configured credential reference, and one expressly
authorized recipient/message/send. No credential value needs to appear in chat.
Provider evidence and recipient-side confirmation must be correlatable. These
inputs were not inspected; their absence is not established.

## Browser isolation and verification order

The local browser failure followed coverage in the same realm. Read-only
diagnosis found older coverage topics ahead of the browser topic, which was
prepared near shutdown without a send outcome. This supports a fixture-backlog
problem but does not prove eventual delivery or a transport failure.

`.github/workflows/u5-topics-digests.yml` already separates backend coverage and
browser verification into distinct jobs, each with fresh setup/migration. That
configuration supports isolated suites; no actual CI result is claimed here.

Preserve the failed local realm and evidence, then use a fresh realm for browser
verification. Do not extend the 20-second assertion or relax send/resource
limits to hide the backlog. Test scheduling under backlog separately with
bounded, explicit expectations. Run cumulative backend checks in a separate
realm so their fixtures cannot alter browser acceptance conditions.

A suspected component collection issue was checked without executing tests:

```bash
backend/.venv/bin/python -m pytest -c backend/pytest.u5-topics-digests.ini --collect-only -q tests/u5_topics_digests/component tests/u5_topics_digests/runtime
```

It exited 0 and collected 11 tests. The suspected directory/collection defect
was not substantiated and is not an additional review finding.

After approved repairs, update evidence and manifests, run the required checks,
and obtain a fresh independent review. The exact previously approved browser
checkpoint command remains in the recovery record. Do not substitute document
checks or legacy CI for the working-application check, or treat review readiness
as verified unit completion. Follow `CONVENTIONS.md` for any eventual completed
branch merge through a PR into `develop`.

## Assessment method and limits

Two independent read-only explorers examined the account/preference and email
boundaries using Tier 2 graph evidence from generation
`2026-10-18T14:47:58Z`, exact source, relevant traces, and coverage checks for all
cited paths. Material partial SQL ranges were read directly. Negative claims
are bounded to the inspected account/personalization interfaces and stores;
coverage metadata is a best-effort signal, not proof of completeness. The parent
checked the current Git state, review, recovery record, CI configuration, and
safe collection result. No source repair, fresh runtime test, fresh review,
provider selection, push, PR, or merge was performed during this assessment.

This document's local links, code fences, character decoding, and whitespace
checks passed. The staged diff check reported one trailing space in a
hook-generated subagent message in the audit shard. That tool-owned record was
preserved; a clean check for the full staged diff is not claimed.
