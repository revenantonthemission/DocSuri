#!/usr/bin/env bash
# Install (or refresh) the launchd agents that make this Mac the DocSuri server.
# Idempotent: re-run after any code change, rebuild, or plist tweak.
#
#   ops/server/install.sh
#
# Why LaunchAgents (gui/<uid>) and not LaunchDaemons (system/):
# OrbStack's Docker daemon and the Ollama brew service both live in the user's GUI
# session. A LaunchDaemon starts before login and would find no Docker socket and no
# Ollama, so every dependency would be missing at start. Agents start at login, which
# is why auto-login is the companion setting — see README.md.
set -euo pipefail

REPO="${DOCSURI_REPO:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
AGENT_DIR="$HOME/Library/LaunchAgents"
LOG_DIR="$HOME/Library/Logs/DocSuri"
UID_NUM="$(id -u)"

# role:ProcessType:schedule
#   api/web are latency-sensitive → Interactive keeps launchd from throttling them.
#   Queue consumers are long-running poll loops → keepalive, Adaptive priority.
#   worker-purge is NOT a daemon: purge_worker.main() runs one sweep and returns
#   (its docstring specifies a cron/EventBridge schedule). Under KeepAlive launchd
#   would relaunch it every ThrottleInterval forever, hammering Postgres. It gets
#   StartInterval instead — one sweep per day, which matches the purge_after grace
#   period semantics.
PERIODIC_INTERVAL_SECONDS=86400
ROLES=(
  "api:Interactive:keepalive"
  "web:Interactive:keepalive"
  "worker-ingestion:Adaptive:keepalive"
  "worker-summarization:Adaptive:keepalive"
  "worker-evidence:Adaptive:keepalive"
  "worker-novelty:Adaptive:keepalive"
  "worker-purge:Background:periodic"
  "logrotate:Background:periodic"
)

mkdir -p "$AGENT_DIR" "$LOG_DIR"
chmod +x "$REPO/ops/server/run.sh"

# --- Next.js standalone asset wiring ----------------------------------------------
# `output: 'standalone'` deliberately omits .next/static and public/ from the bundle
# (they are meant to go on a CDN). Served from this box there is no CDN, so they must
# sit where server.js expects them. Symlinks — not copies — so a `pnpm build` refresh
# is picked up without re-running this installer.
if [ -d "$REPO/frontend/.next/standalone" ]; then
  mkdir -p "$REPO/frontend/.next/standalone/.next"
  ln -sfn "$REPO/frontend/.next/static" "$REPO/frontend/.next/standalone/.next/static"
  ln -sfn "$REPO/frontend/public"       "$REPO/frontend/.next/standalone/public"
  echo "linked standalone assets"
else
  echo "WARNING: frontend/.next/standalone missing — run 'pnpm build' in frontend/ first" >&2
fi

write_plist() {
  local role="$1" ptype="$2" sched="$3" label="dev.docsuri.$role" plist="$AGENT_DIR/dev.docsuri.$role.plist"
  local lifecycle
  if [ "$sched" = "periodic" ]; then
    # RunAtLoad fires one sweep at login, then StartInterval repeats it. No KeepAlive:
    # a clean exit is the expected outcome, not a fault.
    lifecycle="  <key>RunAtLoad</key><true/>
  <key>StartInterval</key><integer>$PERIODIC_INTERVAL_SECONDS</integer>"
  else
    # Restart on ANY exit, including a clean one: for a server, exiting is always a
    # fault. ThrottleInterval keeps a misconfigured role from spin-looping; launchd
    # waits this many seconds between respawns.
    lifecycle="  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>ThrottleInterval</key><integer>10</integer>"
  fi
  cat > "$plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$label</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>$REPO/ops/server/run.sh</string>
    <string>$role</string>
  </array>
  <key>WorkingDirectory</key><string>$REPO</string>
$lifecycle
  <key>ProcessType</key><string>$ptype</string>
  <key>StandardOutPath</key><string>$LOG_DIR/$role.log</string>
  <key>StandardErrorPath</key><string>$LOG_DIR/$role.log</string>
  <key>EnvironmentVariables</key>
  <dict>
    <!-- launchd hands jobs a bare PATH. Homebrew (/opt/homebrew/bin) is needed for
         docker/cloudflared; the nvm node path is resolved inside run.sh instead, so
         a node upgrade only requires editing one line there. -->
    <key>PATH</key><string>/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    <key>DOCSURI_REPO</key><string>$REPO</string>
    <key>HOME</key><string>$HOME</string>
  </dict>
  <key>SoftResourceLimits</key>
  <dict>
    <!-- Default 256 descriptors is far too low for an async server holding DB, Redis,
         OpenSearch and upstream HTTP connections concurrently. -->
    <key>NumberOfFiles</key><integer>8192</integer>
  </dict>
</dict>
</plist>
PLIST
  echo "wrote $plist"
}

for entry in "${ROLES[@]}"; do
  IFS=':' read -r role ptype sched <<< "$entry"
  write_plist "$role" "$ptype" "$sched"
  # A changed plist is only re-read after a bootout. bootout is ASYNCHRONOUS: it
  # returns before the job is gone, and bootstrapping into a label that is still
  # tearing down fails with "Bootstrap failed: 5: Input/output error". So bootout,
  # then poll `launchctl print` until the label really disappears, then bootstrap.
  launchctl bootout "gui/$UID_NUM/dev.docsuri.$role" 2>/dev/null || true
  for _ in $(seq 1 50); do
    launchctl print "gui/$UID_NUM/dev.docsuri.$role" >/dev/null 2>&1 || break
    sleep 0.2
  done
  if launchctl bootstrap "gui/$UID_NUM" "$AGENT_DIR/dev.docsuri.$role.plist" 2>/dev/null; then
    echo "  bootstrapped dev.docsuri.$role"
  else
    # Never abort the whole install for one role — the others are independent.
    echo "  WARNING: bootstrap failed for dev.docsuri.$role (see: launchctl print gui/$UID_NUM/dev.docsuri.$role)" >&2
  fi
done

echo
echo "installed ${#ROLES[@]} agents. logs: $LOG_DIR"
echo "status: ops/server/docsurictl status"
