#!/usr/bin/env bash
# Dead-man's-switch heartbeat for the DocSuri server.
#
# Probes the serving chain and reports the verdict to a healthchecks.io check:
#   all probes pass  → GET  $DOCSURI_HEARTBEAT_PING_URL         (check stays up)
#   a probe fails    → POST $DOCSURI_HEARTBEAT_PING_URL/fail    (immediate alert; body names the probe)
#   machine is dead  → no ping at all                            (grace period expires → alert)
# The last row is the point: no on-box monitor can report its own host's death, so the
# alerting authority must be the ABSENCE of a ping, judged by an off-machine service.
#
# Runs from launchd (dev.docsuri.heartbeat, StartInterval 300, via run.sh). Exits 0 once
# probing completes: a failed probe is a finding delivered through /fail, not a fault of
# this script — a nonzero exit would only turn launchd status red on a box nobody watches.
#
# Config lives OUTSIDE the repo in ~/.config/docsuri/monitoring.env (the ping URL is a
# capability — anyone holding it can fake a healthy signal):
#   DOCSURI_HEARTBEAT_PING_URL=https://hc-ping.com/<uuid>
set -uo pipefail

CONF="${DOCSURI_MONITORING_ENV:-$HOME/.config/docsuri/monitoring.env}"
# shellcheck disable=SC1090
[ -f "$CONF" ] && . "$CONF"

PUBLIC_URL="${DOCSURI_PUBLIC_URL:-https://docsuri.rvnnt.dev}"
API_PORT="${DOCSURI_API_PORT:-8000}"
WEB_PORT="${DOCSURI_WEB_PORT:-3000}"

# Three attempts spread over ~10s per probe, so a KeepAlive respawn (ThrottleInterval
# is 10s) rides through without paging anyone; still down after that = real outage.
failed=""
probe() { # <name> <url> <per-attempt timeout seconds>
  curl -fsS -o /dev/null --max-time "$3" \
    --retry 2 --retry-all-errors --retry-delay 3 "$2" \
    || failed="$failed $1"
}

probe api    "http://127.0.0.1:$API_PORT/health" 5
probe web    "http://127.0.0.1:$WEB_PORT/"       5
# The public probe exercises the whole chain: Cloudflare edge → tunnel → web → BFF.
# If egress itself is down this fails AND the ping below can't be delivered — which
# still alerts, via the grace path. The two failure modes converge on the same signal.
probe public "$PUBLIC_URL/bff/health"            15

STAMP="$(date '+%F %T')"
if [ -z "${DOCSURI_HEARTBEAT_PING_URL:-}" ]; then
  echo "[$STAMP] probes:${failed:- all-ok} — DOCSURI_HEARTBEAT_PING_URL unset in $CONF; NO PING SENT (monitoring is blind)"
  exit 0
fi

if [ -z "$failed" ]; then
  curl -fsS -o /dev/null -m 10 --retry 3 "$DOCSURI_HEARTBEAT_PING_URL" \
    || echo "[$STAMP] probes all ok but ping delivery failed — egress problem?"
else
  echo "[$STAMP] FAILED probes:$failed"
  curl -fsS -o /dev/null -m 10 --retry 3 \
    --data-raw "failed probes:$failed" "$DOCSURI_HEARTBEAT_PING_URL/fail" || true
fi
exit 0
