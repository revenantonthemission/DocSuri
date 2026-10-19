# U5 real digest — expected message preview (generated offline, nothing sent)

Generated on 2026-10-19 with the production rendering and payload functions
(`render_presentation` and `digest_message`). No database, network call or
credential was involved. This is the **expected** shape. The authoritative
preview for the actual run is the output of
`scripts/u5_real_delivery.py --action preview` (runbook section 7), printed
from the persisted, immutable run. Show that output to the person before
authorizing the send.

**Sender updated (review finding R-16).** This file first listed the sender
`no-reply@docsuri.rvnnt.dev`, the unverified domain of the failed first attempt.
It now shows `no-reply@mail.rvnnt.dev`, the verified sender of the second
attempt, which was sent on 2026-10-19 after the person approved its actual
`preview` output (see the
[evidence register](../../../maintenance/u5-real-delivery-evidence.md)).
Everything else below is unchanged expected shape.

Assumptions behind this expected preview, which `prepare`/`preview` confirm:
- The topic name is the tool default `DocSuri real delivery check`, the level is
  `standard`, and the time zone is `Asia/Seoul`.
- The demonstration realm holds the two **synthetic fixture papers**, published
  on the day the realm's fixtures are seeded (shown here as `2026-10-19`).
- The language is the `provision` choice. Korean is shown first, then English.

The recipient is the one address the person approved. It is masked here
(`c***@icloud.com`) to keep it out of git history; the `preview` action prints
it in full in the terminal. The run-bound bearer token is redacted. The real
token is issued once, at send admission, and only its SHA-256 is stored.

## Provider request (both languages)

- `POST https://api.resend.com/emails`
- `Authorization: Bearer` + the value of `RESEND_API_KEY` from the process environment (never shown)
- `Idempotency-Key: <the run's request key>` (the `preview` action prints the actual value)
- From: `no-reply@mail.rvnnt.dev`
- To: `c***@icloud.com` (masked; exactly one recipient)
- Headers on the message:
  - `List-Unsubscribe: <https://docsuri.rvnnt.dev/api/v2/topics/email-unsubscribe/REDACTED-single-use-token-issued-only-at-send-admission>`
  - `List-Unsubscribe-Post: List-Unsubscribe=One-Click`

## Korean (`--language ko`)

Subject:

```text
[DocSuri] 'DocSuri real delivery check' 주제 다이제스트 (2)
```

Text part:

```text
'DocSuri real delivery check' 주제 다이제스트
최신 논문 2편입니다.
표준 · 원문 제목 및 발행일
- Synthetic digest study alpha (2026-10-19)
- Synthetic digest study beta (2026-10-19)

Unsubscribe: https://docsuri.rvnnt.dev/api/v2/topics/email-unsubscribe/REDACTED-single-use-token-issued-only-at-send-admission
```

HTML part:

```html
<html><body><h3>&#x27;DocSuri real delivery check&#x27; 주제 다이제스트</h3><p>최신 논문 2편입니다.</p><p>표준 · 원문 제목 및 발행일</p><ul><li>Synthetic digest study alpha (2026-10-19)</li><li>Synthetic digest study beta (2026-10-19)</li></ul><p><a href="https://docsuri.rvnnt.dev/api/v2/topics/email-unsubscribe/REDACTED-single-use-token-issued-only-at-send-admission">Unsubscribe / 구독 해지</a></p></body></html>
```

## English (`--language en`)

Subject:

```text
[DocSuri] 'DocSuri real delivery check' topic digest (2)
```

Text part:

```text
'DocSuri real delivery check' topic digest
2 recent papers.
Standard · original titles and publication dates
- Synthetic digest study alpha (2026-10-19)
- Synthetic digest study beta (2026-10-19)

Unsubscribe: https://docsuri.rvnnt.dev/api/v2/topics/email-unsubscribe/REDACTED-single-use-token-issued-only-at-send-admission
```

HTML part:

```html
<html><body><h3>&#x27;DocSuri real delivery check&#x27; topic digest</h3><p>2 recent papers.</p><p>Standard · original titles and publication dates</p><ul><li>Synthetic digest study alpha (2026-10-19)</li><li>Synthetic digest study beta (2026-10-19)</li></ul><p><a href="https://docsuri.rvnnt.dev/api/v2/topics/email-unsubscribe/REDACTED-single-use-token-issued-only-at-send-admission">Unsubscribe / 구독 해지</a></p></body></html>
```

## What the person sees when they cancel

Opening the link shows a Korean confirmation page ("이메일 구독 해지", button
"구독 해지 확인"). Confirming unsubscribes this one topic; no sign-in is needed.
(In the second attempt this button was refused with `request.origin`; the
cause is fixed in source and tested, not yet re-run live. The mail app's
one-click unsubscribe worked.)
A mail client's one-click unsubscribe does the same through
`List-Unsubscribe-Post`. Either way the link is single-use and works only while
the U5 host runs and before the capability expiry.

## Things worth a decision before the send

- The content is two synthetic fixture titles. This proves delivery, not
  editorial content.
- The `Unsubscribe:` line in the text part and the link label are English or
  bilingual even in the Korean message. That is the adapter's fixed wording.
