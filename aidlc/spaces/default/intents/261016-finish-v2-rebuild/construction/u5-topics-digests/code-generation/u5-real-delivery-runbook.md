# U5 real digest delivery — operator runbook

Status on 2026-10-19 (updated after the second attempt): **one real digest was
sent and reached the inbox.** The second attempt (realm
`docsuri-u5-95df9983c1b017e4`, run `bdc65d9f-c805-4dbc-bd20-a2a5e650f91c`,
sender `no-reply@mail.rvnnt.dev`) ended `sent` with a provider receipt at
05:11:26 UTC, and the person confirmed inbox arrival. The mail app's one-click
unsubscribe worked; the browser confirmation button was refused with
`request.origin` (R-15) and is fixed in source with automated tests, not yet
re-run live (section 4 step 7, section 8). The tunnel is rolled back and the
host stopped. Facts: [evidence register](../../../maintenance/u5-real-delivery-evidence.md).

**Run order.** The sections are reference, not a sequence. Run them in this
order: 3 (fresh realm) → 4 (tunnel and endpoint gate) → 6 (credential into
the shell) → 2a (read-only domain check) → decide the section 2 gates → 5
(activation record) → 7 (check, provision, prepare, preview, approval) → 8
(send and outcome) → 9 (retention). Section 2 depends on 2a and on 4 step 7;
2a needs the credential from 6; 5 needs the realm from 3 and the gates from 2.

The history below records the first attempt. The first authorized attempt (realm `docsuri-u5-a4ed677392fc22d7`, run
`2ea6c002-f993-4cc6-9add-36a7867cb911`, attempted 2026-10-19 04:49:59 UTC,
`pathKind: real`) ended `failed` / `delivery-path-refused` with no provider
receipt, and spent that realm's single allocation. The code at the time did not
record the provider's status code, so the cause is not proven. It is most likely
the sender domain: the sender was `no-reply@docsuri.rvnnt.dev`, but a later
read-only `GET /domains` (status 200, so the key is valid) listed only
`mail.rvnnt.dev` as verified. That realm is preserved, not deleted, at
`/private/tmp/docsuri-u5-preserved-docsuri-u5-a4ed677392fc22d7-fe26b52f`.
A refusal now records the provider's HTTP status and error name (section 8a).
A new attempt needs a fresh realm (section 3) and the person's new approval.
Each step below is for the operator (the person) to run, in order, with the
stated stops.

Decisions this runbook implements (the person's, authoritative): Resend free
plan; the sender must be on a domain Resend lists as **verified** in
`GET /domains`. Today that is only `mail.rvnnt.dev`, so the sender is
`no-reply@mail.rvnnt.dev`. The public unsubscribe origin stays
`https://docsuri.rvnnt.dev`; sender domain and unsubscribe host are independent,
and the composition accepts them being different. Exactly one permitted recipient (the address the
person gave in the session; deliberately not repeated in this committed file);
public unsubscribe origin `https://docsuri.rvnnt.dev` through the existing
tunnel; exactly **one** real attempt per realm database, never replenished by
failure (account erasure or a fresh realm resets the count; see section 3);
real-send
evidence kept **30 days**; unchanged shared-device design (single-use,
run-bound cancellation that works without signing in); $0 budget, no paid
service or fallback.

## 1. What the code provides

| Piece | Where | Behaviour |
|---|---|---|
| Real composition | `backend/u5_real_delivery.py` → `assemble_u5_real` | Resend adapter (`digest_mail_binding(synthetic=False)`), policy `u5-real-demonstration` (limit 1, retention 30 days), `EmailUnsubscribe` bound to the public origin with an explicit aware expiry, and a middleware (`PublicCancellationOrigin`) that, on the cancellation path only, admits that exact `Origin` and restores the page's own `Referrer-Policy: same-origin` and CSP over the host boundary's, so a browser's confirmation POST carries the real origin rather than `null`. Refuses on any missing/invalid input; no fallback. |
| Host flag | `scripts/serve_docsuri_u5.py --real-delivery` | Without the flag the host is synthetic and never reads provider variables, even when they are set. |
| Activation record | `/tmp/docsuri-u5-run/real-delivery.json` (0600, run-bound) | Non-secret operator decisions and the two fail-closed gates. |
| Credential | process environment only | `EMAIL_PROVIDER=resend`, `RESEND_API_KEY` (must have the `re_…` key shape; a malformed value is refused locally so it cannot waste the single attempt). |
| Operator tool | `scripts/u5_real_delivery.py --action check\|provision\|prepare\|preview\|outcome` | Never constructs the adapter, issues a capability or reads the key's value. `provision`, `prepare`, `preview` require the host to be stopped. |
| Capability record | `topics.digest` | Synthetic host: `degraded` / `synthetic-only`. Real host: `degraded` / `real-bounded`, policy `u5-real-demonstration`. |
| Allocation guard | scheduler + repository | One real attempt per realm database: the count is that realm's `topics.send_log_entry` rows with `path_kind='real'`. Only the permitted recipient's due topics and queued runs are read (filtered before the page), so another account can never spend the attempt. |
| Refusal detail | migration `u5_refusal_detail.sql` + `digest_email.py` | A provider refusal (400/401/403/404/413/422/429) records the HTTP status and Resend's error `name` (validated as a short lowercase identifier, else `name-unavailable`) on `topics.delivery_outcome`, set once. Refusals decided on this host before any network call get their own reasons (`recipient-not-permitted`, `unsubscribe-url-invalid`, and the existing `recipient-unavailable`). Never stored: the key, request headers, the response body, Resend's free-text `message`. 408/409/5xx and transport errors stay `unknown`; nothing retries. |
| Retention | migration `u5_real_send_retention.sql` + scheduler sweep | Each real attempt stamps `evidence_retain_until = attempted_at + 30 days` (DB-enforced maximum). After it, a settled run's provider receipt is cleared; the row stays, so the allocation is not replenished. |

## 2. Prerequisites the operator confirms (fail-closed gates)

Set a gate to `true` only after checking it yourself; the code cannot verify
these and treats `true` as your statement.

- `freePlanVerified`: the Resend account is on the free plan and has quota for
  one message; the read-only check in section 2a printed `status 200`; and the
  sender's domain (the part after `@` in `sender`) is listed there with status
  `verified`. Note: a wrong or revoked key, or an unverified sending domain, is
  answered by Resend with a 4xx refusal, which is recorded **and spends the
  single attempt**. The first attempt was spent this way (see the status note).
- `unsubscribeEndpointVerified`: section 4 step 7 passed (inert GET page,
  header-less one-click POST, and the browser-confirmation path's automated
  tests).

## 2a. Read-only pre-send check of the key and the sending domain

Run this in the shell from section 6, after the credential is loaded. It makes
one `GET https://api.resend.com/domains`, sends no email, and prints only the
HTTP status, then each domain's name and status. It never prints the key,
request headers or the response body. Do not run it with `set -x`, and do not
replace it with `curl -v`, which prints the `Authorization` header.

```bash
backend/.venv/bin/python - <<'EOF'
import os
import httpx

response = httpx.get(
    "https://api.resend.com/domains",
    headers={"Authorization": "Bearer " + os.environ["RESEND_API_KEY"]},
    timeout=10,
)
print("status", response.status_code)
if response.status_code == 200:
    for domain in response.json().get("data", []):
        print(domain.get("name"), domain.get("status"))
EOF
```

Expected: `status 200` and the line `mail.rvnnt.dev verified`. The sender in
section 5 must use a domain printed with `verified`. If the status is 401 or
403, or the sender's domain is missing or not `verified`, stop: do not write
`freePlanVerified: true`. This check does not prove the account's plan or
quota; confirm those in the dashboard. A key limited to sending may be refused
by this read endpoint even though it can send; in that case confirm the domain
status in the dashboard instead and record that the check was done there.

## 3. Fresh demonstration realm

Use a realm of its own, not the checkpoint realm. Run the AI-DLC browser
checkpoint first (it needs the current fixtures-only realm), then:

```bash
backend/.venv/bin/python scripts/verify_docsuri_u5.py --phase archive-owned --profile synthetic-local --environment-file /tmp/docsuri-u5-run/environment.json
backend/.venv/bin/python scripts/verify_docsuri_u5.py --phase setup --profile synthetic-local --environment-file /tmp/docsuri-u5-run/environment.json
backend/.venv/bin/python scripts/verify_docsuri_u5.py --phase migrate --profile synthetic-local --environment-file /tmp/docsuri-u5-run/environment.json
backend/.venv/bin/python scripts/verify_docsuri_u5.py --phase fixtures --profile synthetic-local --environment-file /tmp/docsuri-u5-run/environment.json
```

A realm whose single allocation is spent (as `docsuri-u5-a4ed677392fc22d7`
and `docsuri-u5-95df9983c1b017e4` were) can never send again; `archive-owned`
preserves it, and the new realm starts with a fresh allocation of one.

The allocation is per realm database, not global. Two things reset it:
a fresh realm (its own empty count), and erasing the recipient's account
(`topics.erase_private_controls` deletes the topics, and the send-log rows
cascade with them). **Never do either to retry a spent attempt.** A fresh realm
is only for a new attempt that the person has separately approved, with a new
preview. `migrate` applies every appended U5
migration, including `u5_refusal_detail.sql` (65 migrations in total). The
`outcome` action needs that migration: run it against a realm migrated with the
current source, not against an older preserved one.

If `setup` right after `archive-owned` answers `owned prerequisite unavailable`,
Docker is still releasing the stopped container's port; run `setup` again.
The realm lives at most 24 hours. The cancellation link works only while the
U5 host runs and before `capabilityExpiresAt`.

The digest contains whatever eligible papers the realm holds inside the window.
In this realm that is the two **synthetic fixture papers** ("Synthetic digest
study alpha/beta", dated the fixtures day). No other content is available, and
the preview shows exactly this.

## 4. Cloudflare tunnel: proposed change (not applied)

Read-only findings: launchd agent `dev.docsuri.tunnel` runs
`/opt/homebrew/bin/cloudflared --no-autoupdate --config ~/.cloudflared/config.yml tunnel run docsuri`,
logging to `~/Library/Logs/DocSuri/tunnel.log`, with no `--loglevel` flag
(cloudflared default `info`). `config.yml` is locally managed: `docsuri.rvnnt.dev`
goes to `http://127.0.0.1:3000`, `ssh.rvnnt.dev` to SSH, then a 404 catch-all.

The owned U5 host listens on `https://127.0.0.1:18089` with a per-realm
self-signed certificate. Its `TrustedHostMiddleware` admits only Host `127.0.0.1`.

### Diff for `~/.cloudflared/config.yml`

```diff
 ingress:
+  # U5 email cancellation only: the single-use 43-character capability path.
+  # GET serves an inert confirmation page; POST is the RFC 8058 one-click.
+  # Every other docsuri.rvnnt.dev path still goes to :3000 unchanged.
+  - hostname: docsuri.rvnnt.dev
+    path: ^/api/v2/topics/email-unsubscribe/[A-Za-z0-9_-]{43}$
+    service: https://127.0.0.1:18089
+    originRequest:
+      httpHostHeader: 127.0.0.1
+      originServerName: 127.0.0.1
+      # Loopback-only origin with a per-realm self-signed certificate. Stricter
+      # alternative: caPool: /tmp/docsuri-u5-run/<realm certificate>.crt
+      # (must be updated for every new realm).
+      noTLSVerify: true
   - hostname: docsuri.rvnnt.dev
     service: http://127.0.0.1:3000
```

The new rule must stay **above** the existing `docsuri.rvnnt.dev` rule (first
match wins). cloudflared cannot filter by method; the U5 app answers only GET
and POST on this path (others get 405) and treats an unknown token as a no-op.

### URL access logging on this path

- **U5 host:** `serve_docsuri_u5.py` runs uvicorn with `access_log=False`. The
  cancellation handlers never log, echo or redirect the token, and error paths
  return fixed text.
- **The :3000 web app** never receives this path once the rule is in place.
- **cloudflared:** at the default `info` level it does not write per-request
  lines. Do not add `--loglevel debug` or `--transport-loglevel debug`.
  Error-level "request failed" lines can include the destination URL when the
  origin is down. So keep the U5 host running for the whole capability window,
  or run the tunnel with `--loglevel fatal` for that window. After the
  demonstration, check without printing matches:
  `grep -c 'email-unsubscribe' ~/Library/Logs/DocSuri/tunnel.log` (expect `0`).
  Rotated copies kept by `dev.docsuri.logrotate` need the same check.
- **Cloudflare edge (dashboard; verify, cannot be set from this repository):**
  confirm there is no Logpush job and no active Instant Logs session for the
  zone. Confirm no WAF custom, rate-limiting or managed rule logs matches for
  this hostname/path; Security Events record the URI path of matched requests.
  Zone analytics may aggregate request paths. The token is single-use and
  expires with the capability, which limits the exposure, but it is not zero.

### Apply (operator)

1. `cp ~/.cloudflared/config.yml ~/.cloudflared/config.yml.bak-u5-$(date +%Y%m%d%H%M%S)`
2. Insert the rule above.
3. `/opt/homebrew/bin/cloudflared tunnel --config ~/.cloudflared/config.yml ingress validate`
4. Check rule selection locally:
   `/opt/homebrew/bin/cloudflared tunnel --config ~/.cloudflared/config.yml ingress rule https://docsuri.rvnnt.dev/api/v2/topics/email-unsubscribe/AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA`
   (expect the `https://127.0.0.1:18089` rule), then the same command with
   `https://docsuri.rvnnt.dev/` (expect `http://127.0.0.1:3000`).
5. `launchctl kickstart -k gui/$(id -u)/dev.docsuri.tunnel`
6. Start the **synthetic** U5 host in its own terminal, before any recipient is
   provisioned (it would otherwise deliver a prepared run to the local sink):
   `backend/.venv/bin/python scripts/serve_docsuri_u5.py --environment-file /tmp/docsuri-u5-run/environment.json`
7. From another network or device, using a dummy 43-character token:
   - `GET https://docsuri.rvnnt.dev/api/v2/topics/email-unsubscribe/<43 chars>`
     must show the "이메일 구독 해지" confirmation page.
   - `curl -s -o /dev/null -w '%{http_code}' -X POST -H 'Content-Type: application/x-www-form-urlencoded' --data 'List-Unsubscribe=One-Click' https://docsuri.rvnnt.dev/api/v2/topics/email-unsubscribe/<43 chars>`
     must print `200` (an unknown token changes nothing).
   - `https://docsuri.rvnnt.dev/` must still serve the :3000 app.
   Then stop the synthetic host (Ctrl-C).
8. The browser confirmation path (pressing "구독 해지 확인" on the page) cannot
   be checked live here: the synthetic host has no `PublicCancellationOrigin`,
   so it refuses the public `Origin` and serves the boundary's
   `Referrer-Policy: no-referrer`. Both are expected on the synthetic host. Before
   the send, this path is covered only by automated tests (review finding R-15):
   ```bash
   backend/.venv/bin/python -m pytest -c backend/pytest.u5-topics-digests.ini -q tests/u5_topics_digests/component/test_real_composition.py
   ```
   It must pass, including
   `test_browser_confirm_under_the_served_policy_passes_the_boundary` and
   `test_only_the_exact_origin_on_the_exact_path_and_methods_is_admitted`; the
   database-backed counterpart in `integration/test_real_delivery.py` runs in the
   `integration` and `coverage` phases. The live browser path is first exercised
   on the real host in section 8.

   Only now may `unsubscribeEndpointVerified` be `true`. The gate covers the live
   GET, the live header-less POST and the automated browser-confirmation tests.

### Rollback

`cp <the backup> ~/.cloudflared/config.yml && launchctl kickstart -k gui/$(id -u)/dev.docsuri.tunnel`.
Then stop any U5 host and delete `/tmp/docsuri-u5-run/real-delivery.json`.

## 5. Activation record (operator writes it; never contains the key)

```bash
umask 077
RUN_ID=$(backend/.venv/bin/python -c 'import json;print(json.load(open("/tmp/docsuri-u5-run/environment.json"))["runId"])')
EXPIRES=$(date -u -v+12H +%Y-%m-%dT%H:%M:%S+00:00)   # must be before the realm's expiry
DIGEST_RECIPIENT='<the one approved address>'
cat > /tmp/docsuri-u5-run/real-delivery.json <<EOF
{"runId": "$RUN_ID", "sender": "no-reply@mail.rvnnt.dev",
 "permittedRecipient": "$DIGEST_RECIPIENT", "unsubscribeOrigin": "https://docsuri.rvnnt.dev",
 "capabilityExpiresAt": "$EXPIRES", "freePlanVerified": true, "unsubscribeEndpointVerified": true}
EOF
```

Write `true` for a gate only once section 2 is satisfied; `false` refuses.
The sender's domain must be one that section 2a printed as `verified`
(`mail.rvnnt.dev`). The unsubscribe origin stays `https://docsuri.rvnnt.dev`.

## 6. Credential into this shell only (nothing printed)

```bash
set -a; source <(grep '^RESEND_API_KEY=' backend/.env.aws-secrets); set +a
export EMAIL_PROVIDER=resend
```

`backend/.env.aws-secrets` defines `RESEND_API_KEY` (checked by name only) and
does not define `EMAIL_PROVIDER`, hence the explicit export. Do not run with
`set -x`. The verification runner strips both variables from its children, so
synthetic phases stay network-disabled.

## 7. Check, provision, prepare and preview (host stopped; no send possible)

```bash
backend/.venv/bin/python scripts/u5_real_delivery.py --environment-file /tmp/docsuri-u5-run/environment.json --action check
backend/.venv/bin/python scripts/u5_real_delivery.py --environment-file /tmp/docsuri-u5-run/environment.json --action provision --language ko --time-zone Asia/Seoul
backend/.venv/bin/python scripts/u5_real_delivery.py --environment-file /tmp/docsuri-u5-run/environment.json --action prepare
backend/.venv/bin/python scripts/u5_real_delivery.py --environment-file /tmp/docsuri-u5-run/environment.json --action preview
```

- `check` must show `activation: ok`, `provider: ok`, `allocation.remaining: 1`.
  It is `ready: true` only after provisioning. It reports whether
  `RESEND_API_KEY` is present and well-shaped, never its value.
- `provision` creates the permitted recipient's account (verified, no sign-in
  credential), its local-research consent (the person's authorization for this
  demonstration), language/time-zone settings and one daily topic. Use
  `--language en` for an English message. Re-running never rewrites settings.
- `prepare` creates today's run in the recipient's zone. It must report
  `state: prepared` and `items: 2`.
- `preview` prints the exact subject, text, HTML, recipient, sender, the
  appended `Unsubscribe:` line and link, `List-Unsubscribe`,
  `List-Unsubscribe-Post: List-Unsubscribe=One-Click`, the `Idempotency-Key`
  and the endpoint. The token appears as
  `REDACTED-single-use-token-issued-only-at-send-admission`; the real token is
  issued once, at send admission, and only its hash is stored. The output
  contains the recipient address: keep it in the terminal, out of committed files.

**STOP:** show the person the preview and get explicit approval of this exact
message and recipient before section 8. If anything changes (settings, a new
run), prepare and preview again.

## 8. The single authorized send

```bash
backend/.venv/bin/python scripts/serve_docsuri_u5.py --environment-file /tmp/docsuri-u5-run/environment.json --real-delivery
```

Run it in its own terminal, in the shell from section 6. Startup refuses
without the activation record, the variables, a valid key shape or both gates.
The first worker pass sends the prepared run once (`pathKind=real`). Then:

```bash
backend/.venv/bin/python scripts/u5_real_delivery.py --environment-file /tmp/docsuri-u5-run/environment.json --action outcome
```

It shows `state` (`sent`, `failed` or `unknown`), the provider receipt, its
SHA-256, the acknowledgement time, `evidenceRetainUntil`, for a failed run the
`refusal` detail (section 8a), and `allocation.spent: 1`. `unknown` means the result was not observed: nothing
resends it automatically, and the attempt is spent. Correlate the inbox
separately; provider acceptance is not proof of inbox placement.

### 8a. Reading a refusal

For a `failed` run, `outcome` adds a `refusal` object built only from recorded
facts. Example for a provider refusal:

```json
"failureReason": "delivery-path-refused",
"refusal": {
  "decidedBy": "provider",
  "reason": "delivery-path-refused",
  "reachedProvider": true,
  "httpStatus": 403,
  "errorName": "validation_error",
  "detailRecorded": true
}
```

- `decidedBy: "provider"` with `reachedProvider: true`: Resend received the
  request and refused it. `httpStatus` is the HTTP status (one of 400, 401,
  403, 404, 413, 422, 429). `errorName` is Resend's error `name`, or
  `name-unavailable` when the body had no valid short name. Resend's
  explanatory `message` is deliberately not kept; match the status and name
  against Resend's error documentation and the dashboard's email log. Typical
  readings: 401/403 with a key or permission name point at the key; 403
  `validation_error` usually means the sending domain is not verified; 422
  points at the message fields; 429 at rate or daily quota.
- `decidedBy: "local"` with `reachedProvider: false`: refused on this host,
  before any network call. `recipient-unavailable`: the recipient account had
  no consent or address at send time. `recipient-not-permitted`: the address
  was not the one permitted recipient. `unsubscribe-url-invalid`: the issued
  cancellation link did not match the configured origin. None of these reached
  Resend, but the attempt is still spent, because admission counts it.
- `detailRecorded: false` (`reachedProvider: null`, no status): a provider-path
  refusal recorded before refusal detail existed, like the first attempt. Who
  refused cannot be told from the record.
- `decidedBy: "unclassified"`: a reason this tool does not know (for example
  one written by a test); read `failureReason`.

`refusal` is `null` for runs that did not fail. The output never contains the
key, request headers, the response body or the recipient address.

While the real host runs, check the browser path live with a dummy
43-character token (an unknown token changes nothing and spends nothing):

```bash
URL=https://docsuri.rvnnt.dev/api/v2/topics/email-unsubscribe/AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
curl -s -D - -o /dev/null "$URL" | grep -i '^referrer-policy'
curl -s -o /dev/null -w '%{http_code}\n' -X POST -H 'Origin: https://docsuri.rvnnt.dev' -H 'Content-Type: application/x-www-form-urlencoded' --data 'List-Unsubscribe=One-Click' "$URL"
curl -s -o /dev/null -w '%{http_code}\n' -X POST -H 'Origin: null' -H 'Content-Type: application/x-www-form-urlencoded' --data 'List-Unsubscribe=One-Click' "$URL"
```

Expected: `referrer-policy: same-origin`, then `200` (what a browser sends
under that policy), then `403` (`null` stays refused). Then test the emailed
link in a browser by pressing "구독 해지 확인", or with the mail app's
unsubscribe. After that, or at `capabilityExpiresAt`, stop the host (Ctrl-C)
and roll back the tunnel (section 4). Never start a second `--real-delivery` host to "retry": the
allocation is spent, and the code refuses anyway.

## 9. Retention (30 days)

- **Inside the realm:** the provider receipt is cleared by the scheduler sweep
  once `evidenceRetainUntil` passes and the outcome is settled. The realm lives
  at most 24 hours, though, so in practice the sweep never reaches that point
  while the realm is live.
- **Preserved realms:** `archive-owned` keeps the stopped database volume and
  directory indefinitely. Those hold the receipt and the recipient's account
  address. On or before `attempted_at + 30 days`, the operator must delete that
  preserved realm (`docker volume rm <volumePreserved>` and the
  `/private/tmp/docsuri-u5-preserved-<runId>-…` directory). Nothing deletes it
  automatically. For the first attempt that deadline is **2026-11-18 04:49:59
  UTC**: volume `docsuri-u5-a4ed677392fc22d7-pgdata` and directory
  `/private/tmp/docsuri-u5-preserved-docsuri-u5-a4ed677392fc22d7-fe26b52f`. It
  holds no provider receipt (none was issued), but it does hold the
  recipient's account address. For the second attempt the deadline is
  **2026-11-18 05:11:26 UTC**: volume `docsuri-u5-95df9983c1b017e4-pgdata` and
  directory
  `/private/tmp/docsuri-u5-preserved-docsuri-u5-95df9983c1b017e4-b5081e79`,
  which hold the plaintext receipt and the recipient's address.
- **Committed evidence** (`../../../maintenance/u5-real-delivery-evidence.md`):
  record the receipt's SHA-256, acknowledgement time, state and run id. Do not
  record the plaintext receipt or the recipient address, because git history
  outlives 30 days.
- **Provider side:** Resend keeps its own logs under its plan's retention,
  outside this repository's control. Check it in the dashboard.
