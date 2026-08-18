# DocSuri server runbook

This Mac **is** the production server (AWS decommissioned 2026-08-17). Everything runs
here: data plane in OrbStack containers, app processes under launchd, inference on
Ollama, public ingress through a Cloudflare Tunnel.

```
                 Internet
                    │  TLS terminated at Cloudflare edge
              Cloudflare edge
                    │  outbound-only tunnel — no inbound port is open on this Mac
              cloudflared  (launchd: dev.docsuri.tunnel)
                    │  http://127.0.0.1:3000
   ┌────────────────▼──────────────────┐
   │  Next.js standalone — the BFF     │  dev.docsuri.web
   │  app/bff/[...path]/route.ts       │
   └────────────────┬──────────────────┘
                    │  DOCSURI_GATEWAY_URL, server-side only
   ┌────────────────▼──────────────────┐
   │  FastAPI modular monolith         │  dev.docsuri.api   (127.0.0.1:8000)
   └────────────────┬──────────────────┘
                    │
   Postgres · Redis · OpenSearch · MinIO · ElasticMQ   (compose, all 127.0.0.1)
   Ollama bge-m3 + qwen3:8b                            (brew service, 127.0.0.1:11434)
```

**The single most important property:** only port 3000 is published through the tunnel.
The API, every datastore, and Ollama bind `127.0.0.1` exclusively, so they are
unreachable from the internet even if the tunnel config leaked. The BFF is the one
ingress choke point, and the browser never learns the backend's address.

## Daily use

```bash
ops/server/docsurictl status          # agents + containers + endpoints + tunnel + disk
ops/server/docsurictl logs api -f
ops/server/docsurictl restart all
ops/server/docsurictl rebuild         # frontend rebuild + reload web agent
```

Logs live in `~/Library/Logs/DocSuri/`, rotated daily at 50 MB, 3 generations kept.

## Processes

| Agent | Kind | Notes |
|---|---|---|
| `dev.docsuri.api` | keepalive | uvicorn, **one worker only** (see below) |
| `dev.docsuri.web` | keepalive | Next.js standalone `server.js` |
| `dev.docsuri.worker-{ingestion,summarization,evidence,novelty}` | keepalive | ElasticMQ poll loops, graceful SIGTERM |
| `dev.docsuri.worker-purge` | daily | GDPR grace-period sweep — one shot, not a daemon |
| `dev.docsuri.logrotate` | daily | truncates in place, preserving launchd's descriptor |
| `dev.docsuri.tunnel` | keepalive | cloudflared |
| `dev.docsuri.backup` | daily | pre-existing pg_dump → iCloud |

### Why one uvicorn worker
`backend/app.py` builds the U6 rate limiter and the ObservabilityHub store **in
process** (`app.state.*`). Each extra worker would carry its own independent counter,
so the public rate limit would silently become N × `gateway_rate_limit_max_requests`.
FastAPI is async; one process serves concurrent requests fine. Raise the limit in
config rather than adding workers.

### Why LaunchAgents, not LaunchDaemons
OrbStack's Docker daemon and the Ollama brew service live in the user's GUI session.
A LaunchDaemon starts before login and would find no Docker socket and no Ollama.
Agents start at login — which is why **automatic login must stay enabled** for the
server to return unattended after a reboot or power cut.

## First-time / rebuild-from-scratch

```bash
docker compose -f backend/docker-compose.yml up -d
cd frontend && NODE_ENV=production NEXT_PUBLIC_DOCSURI_REAL_API=1 \
  NEXT_PUBLIC_DOCSURI_RESEARCH_AGENT_ENABLED=true \
  NEXT_PUBLIC_ORCID_LOGIN_ENABLED=false pnpm build && cd ..
ops/server/install.sh
cloudflared tunnel login          # interactive, once — writes ~/.cloudflared/cert.pem
ops/server/tunnel-setup.sh docsuri.rvnnt.dev
```

`NEXT_PUBLIC_*` are **inlined at build time**. Changing them requires a rebuild, not a
restart — `docsurictl rebuild` does both.

## SSH access

**On the LAN:** `ssh <user>@172.30.1.25`. That is `en0` (Ethernet), which is *manually*
configured and has never moved. `en1` (Wi-Fi) is DHCP **and uses a randomised MAC**
(macOS Private Wi-Fi Address), so its lease changes and a DHCP reservation cannot bind
to it — don't use the Wi-Fi address for anything durable.

**From outside:** through the same Cloudflare tunnel, gated by Cloudflare Access.

```bash
DOCSURI_SSH_HOSTNAME=ssh.rvnnt.dev ops/server/tunnel-setup.sh docsuri.rvnnt.dev
```

Client side, one-time:

```
Host ssh.rvnnt.dev
  ProxyCommand /opt/homebrew/bin/cloudflared access ssh --hostname %h
  User <user>
```

Or use Access → Browser rendering → SSH for a terminal in the browser with nothing
installed locally.

**Two preconditions, both able to fail silently:**

1. **The Access application must exist before the DNS record.** DNS is what makes the
   hostname reachable; publish it first and sshd is briefly open to anyone who runs
   `cloudflared access ssh`. Cloudflare gives no warning — a gated and an ungated tunnel
   look identical from here. Verify:
   `curl -sI https://ssh.rvnnt.dev/ | grep -i '^location'` must redirect to
   `<team>.cloudflareaccess.com`. A `200` or a hang means it is **ungated**.
2. **sshd must be key-only.** macOS ships `PasswordAuthentication yes` + `UsePAM yes`.
   The hardening lives in `/etc/ssh/sshd_config.d/200-docsuri-hardening.conf`:
   ```
   PasswordAuthentication no
   KbdInteractiveAuthentication no
   PermitRootLogin no
   ```
   Two traps: sshd is **first-match-wins**, so the `200-` prefix matters only because
   nothing earlier (`100-macos.conf`) sets those keywords — check before renaming. And
   under PAM, disabling `PasswordAuthentication` alone is *not* enough; keyboard-interactive
   still accepts passwords, which is why the second line is there. No restart is needed —
   macOS sshd is socket-activated and re-reads config per connection.

Debugging a timeout: `log show --last 30m --predicate 'process == "sshd"'`. **No entries
means the packets never arrived** (routing/firewall/wrong address), so stop looking at keys
and sshd config. Note a private address like `172.30.1.25` is unroutable from outside the
LAN — from a remote network it can only ever time out.

## Server-mode configuration that is easy to get wrong

Set in `backend/.env` (gitignored):

- `ENV=production` — `backend/app.py:209` passes `production=(not is_local)` into the
  U6 gateway; that flag is what stops internal error detail reaching the internet.
  Flipping it also makes several modules fail-fast on config they previously defaulted.
- `TRUST_PROXY_HEADERS=1`, `TRUSTED_PROXY_COUNT=1` — the rate-limit key is the
  `X-Forwarded-For` hop counted **from the right**, so a client-supplied leftmost hop
  cannot spoof another user into the limiter.
- `DOCSURI_AWS_REGION` / `DOCSURI_CONTROL_PLANE_DSN` — ingestion's `require_production()`
  demands these. Note the `DOCSURI_` prefix (distinct from the bare `AWS_REGION` boto3
  uses for MinIO), and that the control-plane DSN is a **libpq** URL, not the
  SQLAlchemy `postgresql+psycopg://` form.
- `ACCOUNT_EVENTS_BUS=none` — explicit declaration that no async subscriber exists.
  Leaving it unset still fail-fasts, which is the guard's real purpose.

## Known gaps

- **Registration is effectively closed.** `RESEND_API_KEY` is empty, so verification
  emails silently fail and new signups stay `PENDING` forever. Re-issue a Resend key
  and restart to reopen it.
- **Social login is off.** Google/ORCID client secrets are empty; the frontend is
  built with `NEXT_PUBLIC_ORCID_LOGIN_ENABLED=false` so no broken button renders.
- **Search rerank (US-P4) is off.** It was Bedrock Cohere-Rerank with no local
  equivalent; search falls back to baseline RRF ordering.
- **Single point of failure.** One machine, one disk, no redundancy. The daily
  `pg_dump` to iCloud is the only recovery path — MinIO's 24 GB of parse/embed
  artifacts under `~/DocSuriData` are **not** backed up offsite.
- **Disk is the binding constraint** (~93% full). OpenSearch watermarks are raised to
  96/97/98% in `backend/docker-compose.yml` precisely because the defaults would flip
  indices read-only here. Watch `docsurictl status`.

## Troubleshooting

**An agent won't start.** `launchctl print gui/$(id -u)/dev.docsuri.<role>` gives the
real reason; the log file usually has the traceback. Remember launchd has no shell
profile — anything resolved via PATH must be absolute (node comes from nvm, which is
why `run.sh` pins the interpreter path).

**`Bootstrap failed: 5: Input/output error`** — `bootout` is asynchronous and the old
job is still tearing down. `install.sh` polls `launchctl print` until the label
disappears before bootstrapping; re-run it.

**OpenSearch yellow/red.** On a single node every replica is permanently unassigned
(a replica cannot share a node with its primary). Indices are created with
`number_of_replicas: 0`; if a new index appears yellow, set it to 0.

**Nothing came back after reboot.** Check automatic login is still enabled, then that
OrbStack is still in Login Items — the containers depend on it, and the agents depend
on the containers.
