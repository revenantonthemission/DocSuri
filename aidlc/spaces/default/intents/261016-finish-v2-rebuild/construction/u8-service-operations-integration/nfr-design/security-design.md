# Security Design — U8 complete service operations and integration

Date: 2026-10-22 (Asia/Seoul)
Unit: u8-service-operations-integration (service). Sources:

- confirmed [nfr-design-questions.md](nfr-design-questions.md) (Q1–Q6 and the points settled from the records);
- [security-requirements.md](../nfr-requirements/security-requirements.md) (NFR1.1–NFR6.2) and [tech-stack-decisions.md](../nfr-requirements/tech-stack-decisions.md), with the [reliability](../nfr-requirements/reliability-requirements.md), [performance](../nfr-requirements/performance-requirements.md), [scalability](../nfr-requirements/scalability-requirements.md) and [observability](../nfr-requirements/observability-requirements.md) requirements where a control serves them too;
- the open points R-20 and R-21 of the [NFR requirements review](../nfr-requirements/reviews/review-04.md);
- the [functional spec](../functional-design/functional-spec.md), [rules](../functional-design/rules.md) and [entities](../functional-design/entities.md);
- the built code, read on 2026-10-22:
  - the browser boundary and its cookies, `backend/local_browser.py` (`private_cookie`, `boundary_route`, `require_post_headers`);
  - the host boundary, `backend/local_host.py` (`assemble`);
  - the sign-in services, `backend/modules/accounts/services/guarded_entry.py` (`_admit`, `_credential_work`, `verifier`), `control_entry.py`, `control_mfa.py` and `control_identity.py`, with the identity callback route in `backend/modules/accounts/control_http.py`;
  - the account-controls policy, `backend/modules/accounts/control_policy.py`;
  - the owner transactions, `backend/transactions.py`;
  - U5's Resend adapter, `backend/u5_real_delivery.py`;
  - the operator tool's authority, `ops/src/docsuri_ops/platform_control/authority.py`;
- this Mac on 2026-10-22: sudo 1.9.17p2 with its manuals, `sudo(8)` and `sudoers(5)`. There is no `/etc/pam.d/sudo_local`, so sudo authenticates with the password only;
- Cloudflare's [HTTP headers reference](https://developers.cloudflare.com/fundamentals/reference/http-headers/) (`CF-Connecting-IP`), read on 2026-10-22.

U8 hosts every unit, so this file designs the security, consent, integrity, accessibility and $0 requirements of the whole application (NFR1–NFR6, the retention and erasure requirements NFR3.12–NFR3.14 included). U5's and U6's security designs apply inside it unchanged. The other U8 design files cover speed ([performance-design.md](performance-design.md)), capacity ([scalability-design.md](scalability-design.md)), availability and recovery ([reliability-design.md](reliability-design.md)), monitoring ([observability-design.md](observability-design.md)) and the map of parts ([logical-components.md](logical-components.md)).

## 1. Decisions at a glance

| ID | Decision | Source | Serves |
|---|---|---|---|
| D1 | AccountAccess gets a production policy of its own. A member's session lasts 12 hours, an administrator's 1 hour, a purpose-limited session 15 minutes, and none is extended while it is used. The test policy's other values carry over, and the account cap is 500 | Q1 A | NFR1.1–NFR1.3 |
| D2 | Three sign-in limits, checked and counted together in one transaction: 20 attempts a minute per client address (the one Cloudflare stamps), a 15-minute wait after 5 failures in 15 minutes per email address, and 120 attempts a minute for everyone together. A refused attempt changes none of the counts | Q2 A | NFR1.3; the denial-of-service row of § 14 |
| D3 | A provider's redirect back and a link in an email both land on a workspace page, which continues with same-site requests. Every cookie stays `SameSite=Strict` | settled here | NFR1.1, NFR4.5 |
| D4 | Each in-person command asks for your password every time. The operator tool runs it with `sudo -k`, and sudo's rules set `timestamp_timeout=0` for DocSuri's in-person commands only | Q4 A | NFR1.5, NFR1.6, NFR3.2 |
| D5 | The operator tool's database logins are released by a root fixed command onto a pipe, after D4's authentication | settled | NFR3.2 |
| D6 | One closed set of fixed commands, each checking its own argument, under one root-owned rules file | NFR1.6 | NFR1.5, NFR1.6, NFR4.2 |
| D7 | The production browser boundary: two host names; the scheme set to https from the public host name, with no forwarded header ever trusted; origin and CSRF checks bound to the public origin; the built headers plus `form-action` and HSTS; and long caching only for content-hashed files | settled | NFR1.1, NFR1.7 |
| D8 | Each secret lives with the one account that uses it, never in a launch job's definition | NFR3.2 | NFR3.1, NFR3.2 |
| D9 | v2's PostgreSQL instance accepts SCRAM logins over loopback only, and its superuser only over its private socket | NFR3.3 | NFR3.3 |
| D10 | The packet filter ties each local address to its listening account, and the runtime isolation check confirms the arrangement every 5 minutes | NFR3.8 | NFR3.4, NFR3.7, NFR3.8 |
| D11 | Log lines carry only registered fields. The rotation job reaches files without following links or blocking, moves v2's own logs aside, and copies-then-truncates only the rest | settled; R-20, R-21 | NFR3.9 |
| D12 | One shared email count in the operations ledger. Each Resend adapter reserves its send first through an email-allowance port it owns, which the ledger component implements, so no owner calls ServiceOperations | settled | NFR6.2, NFR4.6 |
| D13 | Every request gets a fresh identifier, which is never taken from the request | settled | NFR3.9 |
| D14 | pgvector, built from its pinned source release into PostgreSQL's root-owned folder, is the instance's only extension. It is installed in `template1` too, so every database created later already has it | Q5 A | NFR3.3, NFR3.11 |

## 2. Trust boundaries

| Boundary | What crosses it | Checked by | Trusted for | Never trusted for |
|---|---|---|---|---|
| Internet → Cloudflare's edge | every browser request | TLS at the edge for `docsuri.rvnnt.dev` | — | anything in the request |
| Cloudflare's edge → the tunnel | the proxied requests | the tunnel's own credentials, on the connection `_docsuri_tunnel` opens outward | the stamped client address on requests for the public origin (D2) | every other header, and the body |
| The tunnel → the v2 host (`127.0.0.1:18200`) or the maintenance server (`:18201`) | HTTP on loopback | the packet filter, so that only the listening account's socket receives (D10) | that the listener is v2's | the caller's identity |
| A browser → v2's routes | the session cookie and the CSRF header | AccountAccess's session guard on every protected route (§ 3.6) | the Authority the server establishes | owner fields, roles or lists the browser sends |
| v2 → its PostgreSQL instance (`127.0.0.1:15432`) | the owners' logins | SCRAM, with every client demanding it (D9) | that the server holds each login's verifier | — |
| v2 → the model runtime (`127.0.0.1:11434`) | prompts and texts | the packet filter (only `_docsuri_models` can listen) and the pinned digests (ModelEvidence) | the pinned model's identity | its output as anything but data |
| v2 → Google, ORCID, Resend and Notion | outbound HTTPS | each provider's TLS, behind its owner's adapter | the fields the adapter parses | anything else in an answer |
| Your login account → another account | fixed commands through sudo | your password, every time (D4) | the in-person steps | — |
| The scheduler account → another account | the unattended fixed commands | sudo's rules for that account alone (D6) | the standing authority | any in-person command |
| The backup agent → the backup volume | archive writes, reads back and deletions | the volume's ownership and encryption, and the agent's catalogue | its own catalogue | a ledger record that contradicts the catalogue |

## 3. Accounts, sessions and sign-in (NFR1.1–NFR1.3)

### 3.1 The production account policy (D1, Q1)

The built `ControlPolicy` accepts only the synthetic policy (`u2-synthetic-v1`, realm `account-controls`) and refuses to run anywhere else. AccountAccess gains a second policy, `docsuri-production-v1`, bound to the production profile's realm. The production profile accepts only that policy, and the synthetic realms keep only theirs, so neither can run in the other's place. This is the "policy for real operation" BR6.8 refers to.

| Value | Synthetic policy (built) | Production policy |
|---|---|---|
| Member session | 15 minutes | 12 hours |
| Administrator session | 15 minutes | 1 hour |
| Purpose-limited session (lifecycle status, consent-pending) | 15 minutes | 15 minutes |
| Second factor after the password | within 5 minutes | within 5 minutes |
| Account cap | 20 | 500 (NFR1.3) |
| Every other field: the request, password and value size bounds, the page size, the scope count, outstanding confirmations, the cursor lifetime (5 minutes), the lifecycle worker's lease, attempt timing and attempt count, and the period and quota fields | as built | unchanged |

- **Session length by role.** Today one value, `session_seconds`, sets every full session, including the one `control_mfa.py` issues after the second factor. The production policy separates three lengths. A full session takes its length from the account's role when it is issued: 12 hours for a member, including a member who uses a second factor, and 1 hour for an administrator. The lifecycle-status and consent-pending sessions keep 15 minutes.
- **Never extended.** A session ends at its fixed time, whatever the activity. The browser then asks the person to sign in again. Signing in on another device opens a session of its own. Changing or resetting a password ends every session of the account, as built.
- **Effect on U6.** U6 ends an approved export that has not started when its approving session ends (U6 NFR Design Q4). So that bound becomes 12 hours for a member's approval instead of 1. U6's rule and code are unchanged. Previews that were never approved keep their 7-day limit.
- **Cookies.** The session cookie keeps the built attributes: `Secure`, `HttpOnly`, `SameSite=Strict`, `Path=/`, no `Domain`, and a `Max-Age` equal to the session's length.

### 3.2 Sign-in limits (D2, Q2)

The built `_admit` keeps one counter per minute for everyone together, at most 20, in front of sign-in, registration, verification requests, email verification, password reset and reactivation. It raises that counter for every attempt it lets through, and it checks one password at a time per process (`_credential_work`). Behind the public address, one sender could fill that counter. The production policy puts three limits in front of the same operations, in this order:

| Order | Limit | Key | Window | Over the limit |
|---|---|---|---|---|
| 1 | Per client address | the stamped address's keyed digest | 20 attempts a minute | the built busy answer with `Retry-After` |
| 2 | Per email address, sign-in only | the submitted email's keyed digest | after 5 failed sign-ins within 15 minutes, a 15-minute wait | the same busy answer, whether or not an account exists |
| 3 | Everyone together | none | 120 attempts a minute | the same busy answer |

- **One transaction.** All three are checked and counted in one transaction, before any password is checked. A limit that refuses raises inside it, so the transaction rolls back. A refused attempt therefore changes none of the three counts.
- **What one address can take.** A flood from one address takes at most its own 20 of the shared 120 each minute. Everyone else can still sign in, which is what the shared bound alone could not ensure. A flood spread over six or more addresses can still fill the shared bound, and that bound then protects the machine (§ 17).
- **After the checks,** the password is checked, still one at a time. A failed sign-in adds one to its email's count in its own short transaction.
- **Mail requests.** Requests for verification and reset mail stay bounded per account by the built outstanding-confirmation limit.

**The client address.**
- It is read from `CF-Connecting-IP`, and only on requests whose host is the public origin, `docsuri.rvnnt.dev`. The host never reads `X-Forwarded-For` or `True-Client-IP`. On a request for the loopback origin, the address is the socket's peer.
- The value must be exactly one header holding one address that Python's `ipaddress` parses. An IPv6 address counts by its /64 prefix, so one household or device cannot make new buckets by moving within its own range.
- A public-origin request whose header is missing or malformed counts in one shared "unknown" bucket under the same limit of 20. That fails closed: it is never unlimited.
- Cloudflare's documentation says it adds this header to traffic from its edge to the origin. It does not say outright that a value the caller sent is replaced. A test through the public address therefore checks that a forged value is counted under the real address. If that ever changed, a caller could dodge the per-address limit, and the shared bound would still hold.
- A program on this Mac could connect to v2's local address and send its own value. That only lets it dodge its own per-address limit.

**What is kept.** Addresses and email addresses are kept only as keyed digests, made with the built `verifier` (HMAC-SHA256 under the entry key) with the purposes `entry-address` and `entry-email`. Per-address rows are deleted when their minute ends, as the built row is. Per-email rows are deleted 15 minutes after the last failure or when the wait ends. Neither ever appears in a log line, an observation or a report.

### 3.3 Arriving from another site (D3)

The built cookies are all `SameSite=Strict`. A browser does not send them on a top-level navigation that comes from another site. Two arrivals are exactly that:

- **The provider's redirect back.** Today the registered callback is the API route `GET /api/v2/identity/callback/{provider}` itself. It reads the entry cookie (`docsuri_entry`) and answers JSON. A real redirect back from Google or ORCID arrives without the cookie, so the flow would be refused, and the person would see raw JSON.
- **A link in an email**, for verification or a password reset.

Design:

- The redirect URI registered with each provider is a workspace page, `https://docsuri.rvnnt.dev/sign-in/callback/{provider}`. The host serves it as the static shell, which needs no cookie.
- Before anything else renders, the page's script reads `flow`, `state` and `code` from its own address and removes them with `history.replaceState`.
- It then calls the existing API route with a same-site request. On that request the browser does send the `Strict` entry cookie, and the built checks run unchanged: the flow binding, the state, the sealed verifier, and the callback identity the adapter registered.
- The session cookie it sets stays `Strict`. Email links work the same way: they open a workspace page, which continues with same-site requests.
- **A cancelled or refused sign-in.** A provider returns `error` and `state` without a `code` when the person cancels or refuses at Google or ORCID. The page then calls no API route. It shows a plain Korean message ("로그인이 취소되었습니다") with a way back to sign-in, and the flow's entry context simply expires after its 15 minutes. Any other query the page does not recognise is handled the same way.
- No cookie is relaxed to `Lax`. The code stays out of every log (access logs are off), of the `Referer` header (`no-referrer`) and of the address bar.

The adapter's registered callback becomes the page's address. The token exchange still sends exactly that value, as the built flow compares it (`callback_id`).

### 3.4 Administrators (NFR1.2)

- 운영, incidents and recovery requests answer only an administrator whose current session completed the second factor. Everyone else gets the same safe denial as any protected resource, with no counts or identifiers (BR3.8).
- An administrator's session lasts 1 hour (D1).
- ServiceOperations checks the administrator's session again when the operator starts the request (BR4.2), so a request made in a session that has since ended cannot start.

### 3.5 Admission (NFR1.3)

- **Maintainer-only.** While the profile's admission is maintainer-only, AccountAccess refuses sign-in to every account that is not an administrator. Admission is a policy input the host passes from the profile, never a browser input. The shell shows the maintenance notice on every page except `/privacy` and `/terms` (BR6.4).
- **Open.** After admission opens, only migrated accounts sign in. Registration stays closed until AccountAccess's public-activation evidence is recorded and your decision opens it. After that the policy's account cap of 500 applies, refused with AccountAccess's existing answer (BR6.8).

### 3.6 Owner isolation (NFR1.1)

- Every router of the complete assembly is mounted behind the host's boundary and its owner's guard. The complete verification lists every route of the assembly. Each must be either on the public list (the health routes, `/privacy`, `/terms`, the sign-in entry routes and the static shell) or guarded, and a route that is neither fails the run.
- Navigation is resolved on the server, and the browser's own owner-bound list is removed (amendment A1).
- Another owner's identifier answers exactly like a missing one. A signed-out caller reads only the public capability projection (BR5.9).
- On sign-out, an owner change or a session's end, the workspace drops every cached private response and resolves navigation again (BR5.5).

## 4. The browser and edge boundary (NFR1.7, D7)

- **Listeners.** The host listens only on `127.0.0.1:18200` and the maintenance server only on `127.0.0.1:18201`. The packet filter lets only their own account's socket receive there (§ 6.8).
- **Host names.** The built `TrustedHostMiddleware` allows only `127.0.0.1`. Production allows `docsuri.rvnnt.dev` and `127.0.0.1`, and refuses every other host name.
- **The scheme.** TLS ends at Cloudflare's edge, and the tunnel reaches the host over loopback HTTP. The built route class (`boundary_route`) refuses every request whose scheme is not `https`, or whose `Host` is not its origin's authority, so production fixes the scheme from the deployment and never from a header:
  - The production origin, `https://docsuri.rvnnt.dev`, joins the route class's owned origins, with the authority `docsuri.rvnnt.dev`.
  - The host's outermost middleware sets the request's scheme to `https` for every request whose `Host` is exactly `docsuri.rvnnt.dev`. That is a fact of the deployment: the listener is reachable only on loopback, and only the tunnel serves that name.
  - Requests for `127.0.0.1` keep `http`, so they reach the health routes and no browser route.
  - Uvicorn runs with `proxy_headers=False` and no `forwarded_allow_ips`. Its defaults trust forwarded headers from 127.0.0.1, which would let any program on this Mac set them. So `X-Forwarded-Proto`, `X-Forwarded-For`, `X-Forwarded-Host` and `Forwarded` never set the scheme, the host name or the client address. The only client address is the stamped one of § 3.2.
  - The tunnel's registered configurations for v2's host and for the maintenance server set `httpHostHeader: docsuri.rvnnt.dev`, so the host name the host checks never depends on what the tunnel forwards by default.
- **Origins and CSRF.** The profile's origin is `https://docsuri.rvnnt.dev`. The built boundary refuses any `Origin` header but that one. Every state-changing request needs it, together with the CSRF header bound to the session (`require_post_headers`). So the loopback origin can serve the scheduler's read-only probes but no browser session (§ 16).
- **Headers.** The built set stays: `Content-Security-Policy: default-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'`, with `X-Content-Type-Options: nosniff` and `Referrer-Policy: no-referrer`. Production adds:
  - `form-action 'self' https://accounts.google.com https://orcid.org` to the policy;
  - `Strict-Transport-Security: max-age=31536000` on public-origin answers;
  - `Permissions-Policy: camera=(), microphone=(), geolocation=()`;
  - `Cross-Origin-Opener-Policy: same-origin`.

  The workspace build has no inline script, so the policy needs no `'unsafe-inline'`. A page that breaks the policy fails the complete verification.
- **Caching.** Only files the build lists in its manifest under a content hash are sent with `Cache-Control: public, max-age=31536000, immutable`. The shell, every API and event-stream answer and every paper asset keep the built `no-store`, so neither a browser nor Cloudflare stores anything private (performance-design.md § 4).
- **Paper assets.** They are delivered from the same origin, and authority is checked again on every delivery. No presigned address exists (project.md § Mandated and § Forbidden).
- **Cloudflare's settings for the hostname.** "Always Use HTTPS" is on, the minimum TLS version is 1.2, and every feature that injects scripts or rewrites pages (Rocket Loader, Email Address Obfuscation, automatic Web Analytics, Zaraz) is off. The installation records these settings. The complete verification's public-address check fetches the shell through the public address and compares it byte for byte with the release's build, so any change made at the edge fails the check.
- **The maintenance server.** It answers `GET` and `HEAD` only, sets no cookie, sends the same headers with `Cache-Control: no-store`, and serves only the notice and the static legal pages (BR9.10).

## 5. Operating-system authority (NFR1.4–NFR1.6)

### 5.1 Accounts

| Account | Runs | Owns | May run through sudo |
|---|---|---|---|
| `_docsuri_v2` (610) | the host, workers, scheduler and maintenance server | the profile root, with its secrets, keys and logs | nothing |
| `_docsuri_v2_sched` (611) | the standing job | `scheduler/` (its database login, ping addresses and logs) and `availability/` | the unattended set only (§ 5.2) |
| `_docsuri_v2_db` (612) | v2's PostgreSQL instance | `postgres/data/` and `postgres/socket/` | nothing |
| `_docsuri_models` (613) | the model runtime | `models/` and `models-state/` | nothing |
| `_docsuri_tunnel` (614) | the tunnel | `tunnel/credentials/` and `tunnel/logs/` | nothing |
| `_docsuri_r1t_backup` (607) | the backup agent, whenever one of its commands runs | the backup volume and `backup-agent/` | nothing |
| your login account | the operator tool, and v1 until it retires | v1's stores and your login keychain | every fixed command, each only after your password (D4) |
| root | the packet filter's loader, the backup volume's unlock, the log rotation and the fixed commands | the rule files, the runtimes and the release | — |

The service account holds only PlatformControl's bounded evidence reader (NFR1.5). The database, models and tunnel accounts each run their one launch job and nothing else.

### 5.2 Fixed commands (D6, NFR1.6)

- Each fixed command is a root-owned program in the release folder, which no other account can write.
- It takes at most one argument: a name from its closed set (a launch job's label, a registered origin's name, a command word, or a database name matching its fixed pattern). It checks that name again itself, and refuses anything else with a fixed reason key.
- It runs under sudo's defaults on this Mac, `env_reset` and `secure_path`. No rule carries the `SETENV` tag or adds to `env_keep`, so no variable, path or library from the caller reaches it.
- All the rules live in `/etc/sudoers.d/docsuri-v2` (root, mode 0440). The installation checks that file with `visudo -c -f`, and the isolation check compares its digest with the installed one.

Grants:

| Who | Runs as | Which commands | Password |
|---|---|---|---|
| your login account | root, `_docsuri_v2` or `_docsuri_r1t_backup`, per command | every in-person command: service control per label, tunnel routing, the database operations, the backup agent's in-person commands, the profile operations, copy disposal, v1 lifecycle, decision recording, the ledger component, the production environment tool, the migration tool's import phases, the credential release | asked every time (D4) |
| `_docsuri_v2_sched` | `_docsuri_r1t_backup` | the backup agent's `status`, `backup`, `ledger-copy`, `verify` and `dispose-due` | none (`NOPASSWD`) |
| `_docsuri_v2_sched` | `_docsuri_v2` | the ledger component's unattended words | none |
| `_docsuri_v2_sched` | root | the runtime isolation check, which takes no argument | none |
| `_docsuri_v2` and every other account | — | nothing | — |

Where a command's set is small, such as service control's labels, the rule lists each allowed invocation exactly. The program checks again in every case. An illustration of the shape (Infrastructure Design fixes the paths):

```text
Cmnd_Alias DOCSURI_INPERSON_ROOT = /Library/DocSuri/release/bin/docsuri-service-control, \
                                   /Library/DocSuri/release/bin/docsuri-tunnel-route
Cmnd_Alias DOCSURI_AGENT_UNATTENDED = /Library/DocSuri/release/bin/docsuri-backup-agent status, \
                                      /Library/DocSuri/release/bin/docsuri-backup-agent dispose-due
Defaults!DOCSURI_INPERSON_ROOT timestamp_timeout=0, umask=077
revenantonthemission ALL = (root) DOCSURI_INPERSON_ROOT
_docsuri_v2_sched    ALL = (_docsuri_r1t_backup) NOPASSWD: DOCSURI_AGENT_UNATTENDED
```

### 5.3 In person (D4, Q4)

- Every in-person command is in an in-person alias whose rule sets `timestamp_timeout=0`. So sudo asks for your password for each one, even when a cached sudo authentication from other use exists.
- The operator tool runs each one with `sudo -k`. sudo then asks and does not refresh your cached credentials (`sudo(8)`, option `-k`). So a DocSuri step never opens sudo's 5-minute window for anything else.
- A production restore asks at each of its steps, about 15 times. It works the same in Terminal on this Mac and over SSH, because sudo asks for the password on this Mac either way.
- The scheduler's unattended grants cover only the commands in § 5.2. No in-person command is in any alias the scheduler account can use.
- The actor of an in-person step is the account sudo authenticated, which the command reads from `SUDO_UID`. sudo sets that itself, so a caller cannot choose it. The built operator tool's `getpass.getuser()` stays only for display.
- Your other sudo use keeps sudo's usual 5 minutes per terminal (§ 17).

### 5.4 The operator tool's database logins (D5)

- The operator tool's logins in v2's instance are generic-password items in the System keychain. Root creates them at installation (Workflow 20, step 3). They are never in your login keychain, in an environment file or in any file your login account can read (NFR3.2).
- The release command is in person (D4). It reads the item as root, writes the password to its standard output, a pipe the operator tool opened, and exits. The tool passes it to its one connection as a libpq parameter and never sets `PGPASSWORD` or writes a password file.
- The tool holds a released password in memory only for the one bound operation that needed it, then drops it.
- Without your password, a program running as your login account cannot read the item, cannot run the release command, and so cannot log in to v2's instance as the operator.

### 5.5 Decisions (NFR1.4)

- Only PlatformControl's decision operation (`platform.decision.record`), run in person, records a decision, as a MaintainerApproval in the operations ledger through the ledger component's fixed command.
- The tool shows you the subject exactly, computes the digest of the bytes it showed, and binds the decision to you (from `SUDO_UID`), the step, the subject reference and that digest. Each later effect checks the digest of what it is about to do against the decision.
- The web application reads decisions from the ledger and has no route that writes one (amendment A5).

## 6. Secrets, keys and data at rest (NFR3.1–NFR3.8)

### 6.1 Where each secret lives (D8, NFR3.2)

| Secret | Held by | Where | Read by |
|---|---|---|---|
| The owners' database passwords | `_docsuri_v2` | `profile/owner-credentials.json`, mode 0600 | the built owner transactions, with their private-file checks (not a link, the owner's own, mode 0600) |
| The Resend key and the Google and ORCID client secrets | `_docsuri_v2` | the profile's private environment file, mode 0600 | the complete assembly's entrypoint, with the same checks |
| The scheduler's database login and the healthchecks.io ping addresses | `_docsuri_v2_sched` | `scheduler/`, mode 0700, files 0600 | the standing job |
| The backup agent's logins (one in v2's instance, one read-only in v1's data plane) | `_docsuri_r1t_backup` | `backup-agent/`, mode 0700, files 0600 | the backup agent |
| The operator tool's logins | root | the System keychain | the release command (D5) |
| The backup volume's passphrase | root | the System keychain, and your password manager | the unlock job (NFR3.5) |
| The passphrase of v1's new volume | you | your login keychain and your password manager | you (NFR3.6) |
| The tunnel's credentials | `_docsuri_tunnel` | `tunnel/credentials/`, mode 0700, file 0600 | the tunnel (NFR3.4) |

- **Never in a launch job's definition.** The files in `/Library/LaunchDaemons/` are readable by every account, so no secret goes into one, nor into its `EnvironmentVariables`. A job finds its secrets only in its own account's folder.
- **Missing secrets.** A missing service secret refuses the start, naming it. A missing provider secret leaves only that provider unconfigured and unavailable (BR6.7, BR7.2).
- **Generation.** Every production password and secret is generated at installation for production, from 32 random bytes, by root. It is written straight into its holder's file with the holder's ownership, never echoed, and never copied from the development keys in your login account (BR6.11 (7)). The installation log records only that the step ran (NFR3.9).
- **Changing one.** A password changes only through an in-person step that sets the role's new SCRAM verifier and rewrites the holder's file together.

### 6.2 Keys (NFR3.1)

- The export token keyring, the account control keyring with its recovery snapshots, the account verifier key and the search cursor key each live in their own owner-only folder under the profile root. U6's keyring keeps the folder U6 designed, `export-keys/`. The others leave `/tmp` for the profile root.
- The profile root is under `/Library/DocSuri/`, which Time Machine excludes (§ 6.7). The backup agent dumps databases only, so no backup set holds a key (BR4.8).
- At start, the key check refuses the start while accounts exist and a key folder is missing (Workflow 1). A key is never regenerated silently. It is replaced only through its owner's operator command, run in person through the production environment tool (BR6.9), with that owner's stated consequence.
- U6's first-start and loss rule, which uses the database as a second witness, its sealing and its one client per use apply unchanged.

### 6.3 v2's PostgreSQL instance (D9, NFR3.3)

- `listen_addresses = '127.0.0.1'`, `port = 15432` and `password_encryption = scram-sha-256`. The socket folder `/Library/DocSuri/postgres/socket/` is mode 0700, owned by the database account.
- `pg_hba.conf` holds three lines, in this order:
  - `local all <superuser> peer`;
  - `host all <superuser> 127.0.0.1/32 reject`;
  - `host all all 127.0.0.1/32 scram-sha-256`.

  The superuser role has no password. So it can be used only over the socket, and only by the database account.
- Every client connects with `require_auth=scram-sha-256`: v2, the backup agent, the scheduler's login and the operator tool. The backend's driver bundles libpq 18, which supports it. A program listening in place of the instance cannot complete a login. SCRAM also proves the server, and every other method is refused by the client. So v2's start check fails unless its own connection authenticated through SCRAM.
- Each owner keeps its own schema with its owner and login roles (BR1.4). Scratch, import and rehearsal databases belong to the disposable-databases role, the only role the scheduler's login is a member of, so that login cannot drop the production database (BR9.17).
- **The one extension (D14).** pgvector (Q5) is installed at installation by the database account, through the superuser socket, in `template1` and in each existing database.
  - Every database created later, scratch and rehearsal included, therefore already has it, so a dump's `CREATE EXTENSION IF NOT EXISTS` is a no-op for the login that restores it.
  - Every restore runs `pg_restore --no-comments`, because the dump also carries the extension's comment, which only the extension's owner, the superuser, may set.
  - A scratch restore (restore verification) also runs with `--no-owner` and `--role` set to the disposable-databases role. The scratch copy then belongs to that role, so the scheduler's login, a member of it, can check it, replay the tombstones into it and drop it.
  - A production restore keeps each owner's ownership. It runs, in person, under the operator tool's restore login, which holds exactly the owner-role memberships a restore needs; Infrastructure Design lists them.
  - So no restore needs the superuser.

### 6.4 The tunnel (NFR3.4)

- The credentials file sits in `tunnel/credentials/`, which only the tunnel account can read. The three registered configurations and the active choice are root-owned files in `tunnel/config/`. Each keeps the `ssh.rvnnt.dev` route and sets `no-autoupdate: true` and `loglevel: warn`.
- Routing changes only through the root fixed command that takes a registered origin's name (§ 5.2).
- After the installation, no Cloudflare account certificate is valid, and the old tunnel is deleted (Workflow 20, step 6). A later tunnel change issues a certificate in person and revokes it the same way.

### 6.5 The backup volume (NFR3.5)

- `DocSuri_Backup` is encrypted APFS with ownership enforced, owned by `_docsuri_r1t_backup`. Only the backup agent writes, reads back or deletes in U8's folder, `docsuri-v2`, and only on its catalogue's terms (Workflow 19).
- The root unlock job, `org.docsuri.v2.backup-unlock`, reads the passphrase from the System keychain at boot and every 60 seconds while the volume is present but locked. The passphrase is also in your password manager, so the drive can be read on another Mac. It is no longer in your login keychain.
- The agent's status check fails closed when the earlier tool's cleanup marker sits in U8's folder or any folder above it (BR6.6).

### 6.6 v1's stores (NFR3.6)

- Before the first dry run, v1's object store, its database dumps and the 2026-10-10 archive move from `/Volumes/SSD01` into the new encrypted volume (for example `DocSuri_v1`). That volume enforces ownership, and its folders are owner-only for your login account.
- v1's object store is served from there.
- These locations, the iCloud copies of v1's backups and the Time Machine backups that hold v1's data are recorded as v1's stores, each with its disposal dates (§ 9).

### 6.7 Time Machine (NFR3.7)

- At installation, root runs `tmutil addexclusion -p` for two fixed absolute paths: `/Library/DocSuri/` and `/Users/revenantonthemission/Library/Group Containers/HUAQ24HBR6.dev.orbstack/`. A fixed-path exclusion holds whatever the folder contains later.
- The installation log records both. The isolation check runs `tmutil isexcluded` on both every 5 minutes, as its `isolation-backups` item.
- Every date that erasure evidence shows for a copy on the internal disk (a rehearsal, import or scratch database) is its removal or backstop date plus 24 hours, for the local snapshots (§ 9).

### 6.8 Runtime isolation (D10, NFR3.8)

- **Programs and files.** Every program the non-login accounts or a fixed command run, and every file they read to decide what to do, comes from a root-owned folder under `/Library/DocSuri/` or `/etc` that no other account can write. Nothing comes from a home folder or from Homebrew's prefix.
- **The packet filter.** `org.docsuri.v2.pf` loads `/etc/pf.anchors/org.docsuri.v2` at boot and enables the filter. The anchor is loaded under the system's own `com.apple/*` anchor point, so `/etc/pf.conf`, which macOS updates may replace, is never edited. For each local address, connections pass only while that address's own account owns the listening socket, and are refused otherwise, including while the service is stopped:

```text
pass  in quick on lo0 proto tcp to 127.0.0.1 port 18200 user _docsuri_v2
pass  in quick on lo0 proto tcp to 127.0.0.1 port 18201 user _docsuri_v2
pass  in quick on lo0 proto tcp to 127.0.0.1 port 11434 user _docsuri_models
pass  in quick on lo0 proto tcp to 127.0.0.1 port 15432 user _docsuri_v2_db
block return in quick on lo0 proto tcp to 127.0.0.1 port { 18200 18201 11434 15432 }
```

- **The isolation check.** One root command, run every 5 minutes by the scheduler account, which completes within 60 seconds (NFR8.10). Its items:
  - programs: root-owned, writable by no other account, loading only their own folder's and system libraries;
  - rule and configuration files: owners, modes and digests;
  - accounts: present, non-login, with their UIDs;
  - the database: listening on loopback only, and the `pg_hba.conf` digest;
  - the filter: enabled, with the anchor's digest loaded;
  - the backup volume: unlocked whenever it is present;
  - backups (`isolation-backups`): both Time Machine exclusions;
  - boot items: every job set to start at boot, and running unless a valid stop record covers it;
  - stop records: root-owned, well-formed, citing a service-control receipt, and within their 14 days (NFR7.19).

  Its results are kept 14 days in `/Library/DocSuri/evidence/isolation/`. A failed item makes platform.isolation unavailable, with the item as its limitation (observability-design.md § 3).

## 7. Logs and error reporting (NFR3.9, NFR3.10)

### 7.1 What a log line may carry (D11, D13)

- Each line is one JSON object, written with Python's standard library, with only registered fields:
  - `ts`: UTC, ISO 8601, with milliseconds;
  - `level` and `component`;
  - `event`: a fixed key;
  - identifiers: `requestId`, `jobId`, `operationId`, and account, owner and object identifiers;
  - `state`, `reason` (a fixed key) and `durationMs`.

  The logging helper accepts only these names, with typed values: identifiers, registered keys and numbers. A call with any other field, or with free text, is refused when the code is tested.
- **Exceptions.** An exception is logged as its type and code location, never with its message or local values, because a message can quote input.
- **Other libraries.** Records from third-party loggers keep only the logger's name, the level and the message template without its arguments. The root logger stays at WARNING. Uvicorn's access log is off, and `httpx`, `httpcore`, `urllib3` and `psycopg` stay at WARNING. The Notion SDK keeps U6's null logger.
- **Request identifiers.** The host makes a fresh identifier for every request. It never takes one from a header, so a caller cannot plant text in the logs that way. The identifier goes into the error answer's `requestId`, every log line and observations, and into a job's record when the request starts one, so the workers' lines can be traced back to it (NFR9.11).
- **Never logged:** a credential, token, password or hash, an email address, a client address, private text, a request body or a private query (NFR3.9).

### 7.2 Each runtime's own log (NFR3.9)

- **PostgreSQL:**
  - `log_min_messages = log`;
  - `log_error_verbosity = terse`;
  - `log_min_error_statement = panic`;
  - `log_statement = 'none'`;
  - `log_min_duration_statement = -1`;
  - `log_parameter_max_length = 0` and `log_parameter_max_length_on_error = 0`.

  These keep its own operational messages and drop every error a client causes. v2 logs its own database errors with fixed reason keys.
- **The model runtime** keeps its default level, which records request lines and never prompt text.
- **The tunnel** logs at `warn`. v2's addresses never carry private input (BR5.5).
- **The installation log** records each step's name and outcome, never a secret or certificate content.
- **Where.** Every log lives under `/Library/DocSuri/`, which Time Machine excludes.

### 7.3 Rotation (D11; R-20, R-21)

The root job `org.docsuri.v2.logrotate` runs at 03:00 over its fixed, root-owned list of log folders (observability-design.md § 7).

- **Reaching a folder.** It opens each log folder from `/Library/DocSuri/` one component at a time, with `O_DIRECTORY | O_NOFOLLOW`. At each step it checks the owner: root above the account's folder, and the account at and below it. A folder, or any folder above it, that is a link or has the wrong owner is skipped and recorded with a fixed reason key in `control/logs/` (R-20).
- **Opening a file.** Files are opened only relative to the folder's descriptor (`openat`), with `O_NOFOLLOW | O_NONBLOCK`, so a pipe planted under a log's name cannot make the open wait. The job then checks, through the descriptor (`fstat`), that the file is a regular file with one link, owned by the folder's account. Anything else is skipped and recorded (R-21).
- **v2's own logs** (host, workers, scheduler, maintenance server and standing job). These processes write through Python's `WatchedFileHandler`, which notices when its file is moved and reopens a new one, created 0600 under the process's own account. So the job only moves the file aside (`renameat` within the folder, to `<name>.log.<YYYYMMDD>`), and nothing written is lost.
- **Files launchd holds open** (each job's standard-output and error files, the model runtime's and the tunnel's output). The job:
  - copies the file through its descriptor to the end;
  - writes the copy with `O_CREAT | O_EXCL | O_NOFOLLOW`, then sets its owner and mode 0600 on the open descriptor;
  - checks the size once more, and records the bytes written while it copied, which that check shows (R-21);
  - truncates through the same descriptor after confirming it is still the same file (device and inode).

  The single call between that last size check and the truncation is the one accepted loss, which nothing can count.
- **PostgreSQL's dated files** are never copied or truncated, only deleted after 14 days.
- **Expiry.** Moved files and copies older than 14 days are deleted under the same rules: never through a link, and only regular files the folder's account owns.
- A planted link therefore cannot make root read, copy, truncate or delete anything outside the logs.

### 7.4 No external error reporter (NFR3.10)

- No external error reporter runs in this release. One added later must follow U6's rules: no local variables, no default personal data, no request bodies, the export adapter's frames scrubbed and browser input masked (BR3.10).
- Of everything about the service's errors, only the check names and pass or fail reach healthchecks.io (NFR9.6).

## 8. Software supply chain (NFR3.11)

- Each runtime is pinned and taken from its publisher:
  - PostgreSQL 16.14 built from the PostgreSQL project's source release, without ICU or TLS;
  - pgvector built from its pinned source release against that build, into the same root-owned folder (D14, Q5). Its library is checked like PostgreSQL's own;
  - Ollama 0.40.7 and cloudflared 2026.10.3 from their official GitHub release archives;
  - CPython 3.13.7 installed by uv into the release folder.
- Each download is checked against its publisher's published SHA-256 before installation. Every Python dependency is installed from the lockfile (`uv sync --frozen`) and checked against its lock hash.
- `otool -L` confirms that each program loads only its own folder's and system libraries, and the isolation check repeats that every 5 minutes.
- An upgrade is an in-person administrator step. A model change, or a new digest for a pinned model, is a new release (BR6.11 (2)). The system model runtime holds only the pinned models' clones, so models from elsewhere, cloud models included, are never present to be used.

## 9. Retention and erasure (NFR3.12–NFR3.14)

- **Recording.** Every copy of personal data outside the live service is recorded as a RetainedCopy, BackupSet or LedgerCopy before anything is written to it, with its disposal point and backstop date (Workflow 19, step 2). The values are NFR3.12's table. The backup agent's catalogue records each file's earliest disposal time when the file is written, and decides deletion.
- **Internal-disk copies.** For a copy on the internal disk, the date erasure evidence discloses is its removal or backstop date plus 24 hours (§ 6.7).
- **The 14-day minimum (NFR3.13).** The backup agent refuses a decided disposal date earlier than 14 days after the copy was written, for the v1 final snapshot and for a rolled-back database's copy. It accepts a date only with its decision's receipt and subject digest, which PlatformControl checks before the in-person command runs. A caller can only extend a disposal time. The retention floor always keeps the newest passed set of each database that still exists and the newest verified ledger copy.
- **Erasure (NFR3.14):**
  - An erasure reports complete only when every scope has evidence (BR2.2), including a live restore verification whose register head covers the owner's tombstone.
  - That verification starts at the next 05:00 run, within 24 hours of the tombstone, and completes within 60 minutes of its start (reliability-design.md § 7).
  - The backups evidence names every undisposed set and copy that may hold the owner's data, with the latest date by which each is gone.
- **Archive-only data** can be retrieved for a returning user only until v1's stores are disposed of.

## 10. Integrity, idempotency and reconciliation (NFR4.1–NFR4.6)

- **Recovery requests (NFR4.1).**
  - Each deliberate submission carries its own `submissionId`, and only its retries recover it.
  - The ledger holds each environment's exclusion: one production-affecting request is active at a time, and a waiting request holds nothing and expires after 24 hours.
  - An unknown outcome is reconciled from PlatformControl's receipt and evidence before any other production-affecting operation, and is never re-run blindly.
- **Bound operations (NFR4.2).** Every switch, abort, rollback, restore, disposal and decision effect is a PlatformControl operation that binds the actor, target and input before the effect and leaves a receipt. Only the fixed commands of § 5.2 exist, and no generic command, path or shell is admitted.
- **The ledger and the tombstone register (NFR4.3).**
  - Both are append-only and chained with SHA-256. Each entry is synced to disk before the head is replaced atomically.
  - Writers in the host and the workers take the ledger's file lock.
  - On open, entries a crash left beyond the head are adopted or discarded as the rules state. Any other break stops dependent writes and opens an incident.
  - A ledger copy reaches the backup volume with every set, and at least daily.
- **Migration (NFR4.4).**
  - Target identities are deterministic, so a second pass over the same snapshot imports and updates nothing.
  - Each run's parity report holds counts and checksums per kind, and no password, hash, token, email address or content.
  - v1's vectors are never reused: every paper is embedded again with the pinned model.
- **Outward providers (NFR4.5).**
  - Each provider's first live effect waits for your decision on the digest of its recorded preview.
  - You verify real Google and ORCID sign-in yourself before admission opens, through D3's pages.
  - An abort or a rollback clears these approvals.
- **U5 and U6 (NFR4.6).** Digest and export effects keep U5's and U6's idempotency and reconciliation unchanged. Each email also reserves its place in the shared count first (§ 13).

## 11. Consent (NFR2.1–NFR2.3)

- **First sign-in (NFR2.1).** A migrated account's first sign-in opens a consent-pending session, which every guard denies for anything but giving consents (amendment A3). The account gets a full session only after its v2 consents are recorded. Consent is never carried over from v1 or inferred.
- **Rehearsal (NFR2.2).** The Resend adapter, for account mail and digests alike, and the Notion adapter each read the profile's mode before every effect. In rehearsal mode, which covers every dry run and the soak, a recipient other than your verified address, or a connection other than your own, is held as not permitted and recorded. Each provider has this one check, at its adapter, so no caller can go around it.
- **Live mode (NFR2.3).**
  - U5's single-test bound lifts only after Resend is active in live mode, and digests then go only to subscribers who consented under U5's rules.
  - Withdrawal and consent revocation stop digests and exports, including work already in flight, as U5 and U6 designed.
  - The complete verification proves the race (BR10.3).

## 12. Accessibility (NFR5.1, NFR5.2)

- **Every screen U8 adds or changes** uses Korean labels and meets WCAG 2.2 AA: navigation in every state, 작업, 운영, the legal pages, the sign-in, callback and moved-version notices, and the maintenance notice. Among the design choices:
  - one polite live region in the shell announces capability, job and incident changes;
  - focus moves to the main heading on every route change;
  - targets are at least 24 by 24 CSS px;
  - layouts reflow at 320 CSS px;
  - colours come from tokens that meet 4.5:1 for text and 3:1 for large text.
- **Evidence.** The complete verification records automated checks, keyboard runs, the live region's announcements and 320 CSS px captures for every screen of the complete application. A failed check fails the run (BR10.6).
- **Without scripts (NFR5.2).** The maintenance notice and the static `/privacy` and `/terms` copies are plain HTML and CSS, readable without scripts.

## 13. $0 operation and the email allowance (NFR6.1, NFR6.2, D12)

- **$0 (NFR6.1).** Production uses only free or local components:
  - the local PostgreSQL, Ollama and cloudflared builds;
  - Cloudflare's free tunnel;
  - Resend's free plan;
  - healthchecks.io's free plan, 3 of its 20 checks;
  - Notion's free plan, through each owner's own token;
  - GitHub Actions for CI.

  Nothing falls back to a paid service.
- **The count (NFR6.2).** The email allowance is one count for Resend, kept with its ProviderActivation in the operations ledger, so a production restore cannot roll it back.
  - **Who writes it.** Account mail and digests each send through their Resend adapter. Before it calls Resend, the adapter reserves the send through an email-allowance port that the adapters own (reserve, release, settle). The ledger component implements the port: it appends the reservation to the operations ledger under the ledger's lock. The host's composition wires the port to the ledger component.
  - **No new dependency.** Neither AccountAccess nor TopicsDigests calls ServiceOperations, and no domain logic is involved. So the component graph stays as `components.md` has it: ServiceOperations depends on the owners and on the ledger, never the reverse. ServiceOperations only reads the count, for ProviderActivation's `allowanceRemaining` and for provider.resend's observation.
  - Days are UTC days, so they reset at 09:00 in Seoul; months are UTC months.
  - A digest is reserved only while the day's count of all mail is below 60. Account mail is reserved while that count is below 90. Nothing is reserved once the month's count reaches 2,700.
  - Each message carries its own Resend idempotency key, as U5's adapter already does (`Idempotency-Key`). A retry reuses its message's key and its reservation.
  - A send Resend definitely refused appends a release. A send whose outcome is unknown keeps its reservation.
  - At either limit, provider.resend is degraded with allowance-exhausted, digests wait for the reset, and account mail fails with a plain message.

## 14. Threats and controls

| Threat | Example | Controls |
|---|---|---|
| Spoofing | a program listening on v2's database or host address | D9, D10 |
| Spoofing | a forged client address | D2 |
| Spoofing | a forged decision or ledger record | § 5.5, § 10, the backup agent's catalogue |
| Spoofing | a sign-in redirected somewhere else | registered redirect URIs and the built flow binding (§ 3.3) |
| Tampering | a swapped program, library, model or rule file | § 8, § 6.8 |
| Tampering | a log folder replaced by a link to steer root | D11 |
| Tampering | a changed backup file | the volume's ownership and the catalogue's digests |
| Repudiation | disputing who approved a restore, a disposal or the switch | § 5.5, § 10 |
| Information disclosure | keys or data in Time Machine | § 6.7 |
| Information disclosure | secrets in a world-readable launch job definition | D8 |
| Information disclosure | private data in logs | D11 |
| Information disclosure | private answers cached by a browser or Cloudflare | D7 |
| Information disclosure | client addresses kept or logged | D2 |
| Information disclosure | v1's data on an unencrypted drive | § 6.6 |
| Denial of service | a sign-in flood | D2 |
| Denial of service | a full internal disk | scalability-design.md § 3 |
| Denial of service | the email allowance used up | D12 |
| Denial of service | the model runtime saturated | performance-design.md § 3 |
| Denial of service | a stopped job nobody renews | § 6.8, reliability-design.md § 13 |
| Elevation of privilege | the running application using operator authority | § 5.1, § 5.2 |
| Elevation of privilege | a cached sudo authentication reused by another program | D4, § 17 |
| Elevation of privilege | a planted link or pipe steering the root rotation job | D11 |

## 15. Required verification

Code Generation and the complete verification (BR10.3) prove the behaviours below. They come on top of those listed in security-requirements.md § Required verification, which all still apply.

- **Policy (D1):**
  - a member's session ends 12 hours after sign-in, an administrator's after 1 hour and a purpose-limited session after 15 minutes, and no activity extends one;
  - a member with a second factor gets 12 hours;
  - the synthetic policy refuses the production realm, and the production policy refuses a synthetic one;
  - the 501st account is refused with AccountAccess's existing answer.
- **Sign-in limits (D2):**
  - the 21st attempt from one address within a minute is refused before any password is checked;
  - after 5 failed sign-ins within 15 minutes, an email address is refused for 15 minutes, with the same answer for an email that has no account;
  - the 121st attempt within a minute is refused for everyone;
  - one address sending 200 attempts a minute leaves a second address able to sign in, and the refused attempts change none of the counts;
  - a forged `CF-Connecting-IP` sent through the public address is counted under the real address;
  - a missing or malformed header lands in the unknown bucket;
  - two IPv6 addresses in one /64 share a bucket;
  - no client or email address appears outside its keyed digest.
- **Arrivals from another site (D3):**
  - a stand-in provider served from another site, so the browser treats its redirect as cross-site, completes a sign-in while every cookie stays `Strict`;
  - the code has left the address bar before the page's API call;
  - a provider's `error` return shows the Korean message with the way back, and calls no API route;
  - an email link opened in a fresh browser reaches its page and continues.
- **In person (D4):**
  - two in-person commands in a row each ask for the password;
  - a sudo authentication cached by an unrelated command does not run one;
  - after an in-person command, `sudo -n true` in the same terminal fails, because no cache was refreshed;
  - the scheduler account can run no in-person command;
  - the same holds over SSH.
- **Credential release (D5):**
  - without your password, your login account cannot read the operator tool's items;
  - a released password appears in no process's arguments or environment, and in no file.
- **Fixed commands (D6):** an argument outside a command's closed set is refused by the rule or by the program, and a variable set by the caller does not reach the program.
- **Browser boundary (D7):**
  - a request sent through the tunnel reaches its browser route, which sees `https` and the public host name;
  - a forged `X-Forwarded-Proto`, `X-Forwarded-For`, `X-Forwarded-Host` or `Forwarded` header sent from loopback changes neither the scheme nor the client address;
  - a request for `127.0.0.1` reaches the health routes and no browser route;
  - every answer carries the headers of § 4;
  - only content-hashed files are cacheable;
  - the shell fetched through the public address equals the release's build byte for byte;
  - a host name other than the two is refused.
- **Logs (D11):**
  - a log folder replaced by a link, and a folder above it replaced by a link, pointing at a root-only folder, are skipped and recorded, and nothing in the target is read, copied, truncated or deleted (R-20);
  - a pipe planted under a log's name is skipped at once, without stalling the run (R-21);
  - a hard link is skipped;
  - a moved v2 log loses no line written during the move;
  - a copy-then-truncate run records the bytes written while it copied;
  - after the run, no copy or moved file older than 14 days remains, and each keeps its log's owner and mode 0600;
  - a logging call with an unregistered field or free text fails its test.
- **The extension (D14):**
  - a database created after the installation already has pgvector;
  - the backup agent's login, which is not a superuser, restores a set into a scratch database without error, with the copy owned by the disposable-databases role;
  - a production restore by the operator tool's restore login keeps every owner's ownership, without the superuser;
  - no second extension can be created by any login but the superuser's.
- **Email allowance (D12):**
  - the 61st digest of a UTC day waits while account mail continues up to 90;
  - at 2,700 in a month, all mail stops;
  - a refused send releases its reservation, and an unknown outcome keeps it;
  - a production restore leaves the count as it was;
  - a retry reuses its message's idempotency key;
  - neither AccountAccess's nor TopicsDigests's module imports ServiceOperations; the import check of the complete assembly fails if one does.

## 16. Requirement wording settled here

- **BR6.8's "policy for real operation"** is `docsuri-production-v1` with D1's values and D2's limits.
- **NFR6.2's counts.** There is one daily count of all mail: digests stop when it reaches 60, and account mail when it reaches 90. The monthly count is 2,700. Separate daily caps of 90 and 60 would add up past Resend's free 100 a day, so this is the reading that keeps the free tier.
- **NFR9.8's "copies each log and then truncates it, so writers holding the file open lose nothing".** v2's own logs are moved aside instead, and lose nothing. Copy-then-truncate stays for the files launchd holds open. The bytes written while a copy ran are counted, and the single call between the last size check and the truncation is the one accepted, uncounted loss (§ 7.3; R-21).
- **NFR3.2's "authenticate at this Mac with your password".** That is sudo's password prompt on this Mac, in Terminal or over SSH, asked for every in-person command (D4).
- **NFR1.7's "loopback origin".** The scheduler's read-only probes use it. Its requests keep the `http` scheme, which no browser route accepts, and cookies and CSRF checks are bound to the public origin, so no browser session works through it (§ 4).

## 17. Residual risks

These are accepted in the design and stay visible at the U8 checkpoint:

- **Root through your general sudo use.** Any sudo password you type for something else opens sudo's usual 5 minutes in that terminal. A program started from that terminal within those minutes can become root, and root can do whatever an in-person command does. DocSuri's own commands never open that window (`sudo -k`), but your other sudo use does. Doing operator work in a terminal window of its own limits this. Setting `timestamp_timeout=0` for your account removes it, at the cost of sudo always asking. That is your decision, outside this design.
- **Cloudflare's header.** That Cloudflare replaces a caller's own `CF-Connecting-IP` is confirmed by test, not by its documentation (§ 3.2). If it changed, the per-address limit could be dodged, and the shared bound would still hold.
- **A targeted lockout.** Anyone who knows an account's email address, the administrator's included, can keep its web sign-in waiting with 5 wrong passwords every 15 minutes. The per-email limit stays as you confirmed it (Q2), because it is what stops one account's password being guessed from many addresses. Your in-person operations do not depend on web sign-in.
- **A spread-out flood.** A flood from six or more addresses can still fill the shared 120 a minute and hold everyone's sign-in while it lasts. The shared bound is then what protects the machine.
- **Programs on this Mac** can connect to v2's local address with a client address value of their own, which affects only their own per-address limit.
- The residual risks of security-requirements.md stay as listed there: v1 and its data plane under your login account, the Time Machine disk "무제", the test-realm backup account 607, and macOS updates that stop at the unlock screen.
