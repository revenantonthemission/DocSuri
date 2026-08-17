#!/usr/bin/env bash
# Create (or refresh) the Cloudflare Tunnel that fronts this machine, then install it
# as a launchd agent. Idempotent — safe to re-run.
#
# PREREQUISITE (interactive, do this once by hand):
#     cloudflared tunnel login
# That opens a browser, asks which zone to authorize, and writes
# ~/.cloudflared/cert.pem. It cannot be automated: it is an OAuth consent step.
#
#   ops/server/tunnel-setup.sh [hostname]
#
# Default hostname is docsuri.rvnnt.dev — rvnnt.dev is the only zone on Cloudflare
# nameservers (docsuri.org has no NS records at all since the AWS teardown).
set -euo pipefail

HOSTNAME_ARG="${1:-docsuri.rvnnt.dev}"
TUNNEL_NAME="${DOCSURI_TUNNEL_NAME:-docsuri}"
CF_DIR="$HOME/.cloudflared"
WEB_PORT="${DOCSURI_WEB_PORT:-3000}"
AGENT_DIR="$HOME/Library/LaunchAgents"
LOG_DIR="$HOME/Library/Logs/DocSuri"
UID_NUM="$(id -u)"
CLOUDFLARED="$(command -v cloudflared || echo /opt/homebrew/bin/cloudflared)"

if [ ! -f "$CF_DIR/cert.pem" ]; then
  echo "ERROR: $CF_DIR/cert.pem not found." >&2
  echo "Run this first (it opens a browser):  cloudflared tunnel login" >&2
  exit 1
fi

mkdir -p "$CF_DIR" "$LOG_DIR"

# --- tunnel ------------------------------------------------------------------------
# `tunnel create` fails if the name already exists, so look it up first. The tunnel's
# credentials file (<uuid>.json) is the long-lived secret that lets this host serve
# the hostname; cert.pem is only used for management API calls like create/route.
if TUNNEL_ID="$("$CLOUDFLARED" tunnel list --output json 2>/dev/null \
      | python3 -c "import sys,json;print(next((t['id'] for t in json.load(sys.stdin) if t['name']=='$TUNNEL_NAME'),''))")" \
   && [ -n "$TUNNEL_ID" ]; then
  echo "reusing existing tunnel '$TUNNEL_NAME' ($TUNNEL_ID)"
else
  echo "creating tunnel '$TUNNEL_NAME'…"
  "$CLOUDFLARED" tunnel create "$TUNNEL_NAME"
  TUNNEL_ID="$("$CLOUDFLARED" tunnel list --output json \
      | python3 -c "import sys,json;print(next(t['id'] for t in json.load(sys.stdin) if t['name']=='$TUNNEL_NAME'))")"
fi

# --- ingress -----------------------------------------------------------------------
# ONLY the Next.js BFF (port 3000) is published. The FastAPI gateway, Postgres, Redis,
# OpenSearch, MinIO and Ollama are never named here and are all bound to 127.0.0.1, so
# they remain unreachable from the internet even if this config were leaked. The BFF
# reaches the API server-side over loopback (DOCSURI_GATEWAY_URL).
#
# The catch-all http_status:404 is mandatory — cloudflared refuses to start without a
# final rule that matches everything.
cat > "$CF_DIR/config.yml" <<YAML
tunnel: $TUNNEL_ID
credentials-file: $CF_DIR/$TUNNEL_ID.json

originRequest:
  connectTimeout: 30s
  disableChunkedEncoding: false

ingress:
  - hostname: $HOSTNAME_ARG
    service: http://127.0.0.1:$WEB_PORT
  - service: http_status:404
YAML
echo "wrote $CF_DIR/config.yml  ($HOSTNAME_ARG -> 127.0.0.1:$WEB_PORT)"

# --- DNS ---------------------------------------------------------------------------
# Creates/updates a proxied CNAME <hostname> -> <uuid>.cfargotunnel.com in the zone.
"$CLOUDFLARED" tunnel route dns "$TUNNEL_NAME" "$HOSTNAME_ARG" 2>&1 | tail -2 || \
  echo "(route dns reported an existing record — continuing)"

# --- launchd agent -----------------------------------------------------------------
cat > "$AGENT_DIR/dev.docsuri.tunnel.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>dev.docsuri.tunnel</string>
  <key>ProgramArguments</key>
  <array>
    <string>$CLOUDFLARED</string>
    <string>--no-autoupdate</string>
    <string>--config</string><string>$CF_DIR/config.yml</string>
    <string>tunnel</string><string>run</string><string>$TUNNEL_NAME</string>
  </array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>ThrottleInterval</key><integer>10</integer>
  <key>ProcessType</key><string>Interactive</string>
  <key>StandardOutPath</key><string>$LOG_DIR/tunnel.log</string>
  <key>StandardErrorPath</key><string>$LOG_DIR/tunnel.log</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key><string>/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    <key>HOME</key><string>$HOME</string>
  </dict>
</dict>
</plist>
PLIST

launchctl bootout "gui/$UID_NUM/dev.docsuri.tunnel" 2>/dev/null || true
for _ in $(seq 1 50); do
  launchctl print "gui/$UID_NUM/dev.docsuri.tunnel" >/dev/null 2>&1 || break
  sleep 0.2
done
launchctl bootstrap "gui/$UID_NUM" "$AGENT_DIR/dev.docsuri.tunnel.plist"

echo
echo "tunnel agent installed. https://$HOSTNAME_ARG"
echo "logs: $LOG_DIR/tunnel.log"
