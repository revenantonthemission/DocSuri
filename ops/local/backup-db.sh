#!/usr/bin/env bash
# DocSuri local-serving Postgres backup — dump inside the compose container → verify →
# local tier + iCloud.
#
# The Mac mini serves DocSuri from backend/docker-compose.yml with no Multi-AZ safety net,
# so this script IS the durability story: dump, prove the archive is readable
# (pg_restore --list), then ship it off-machine via iCloud Drive (AWS decommissioned
# 2026-08-17 — no S3 anymore).
#
# Cron (daily 03:30):
#   30 3 * * * $HOME/Projects/DocSuri/ops/local/backup-db.sh >> $HOME/Library/Logs/docsuri-backup.log 2>&1
#
# Requires: the compose stack's postgres service running, and iCloud Drive signed in.
# No host pg_dump needed — dump and verify both run inside the postgres:16 container,
# so client/server versions can never drift.
set -euo pipefail

DOCSURI_REPO="${DOCSURI_REPO:-$(cd "$(dirname "$0")/../.." && pwd)}"
COMPOSE_FILE="$DOCSURI_REPO/backend/docker-compose.yml"
DB_USER="${DOCSURI_DB_USER:-docsuri}"
DB_NAME="${DOCSURI_DB_NAME:-docsuri}"

# Monitoring: report the outcome to a healthchecks.io check so a silent failure can't
# recur (this job failed 6 straight nights in Aug 2026 and nobody knew — the schedule
# means only an off-machine service can notice a missing run). URL unset → pings are
# skipped and the script behaves exactly as before.
MONITORING_ENV="${DOCSURI_MONITORING_ENV:-$HOME/.config/docsuri/monitoring.env}"
# shellcheck disable=SC1090
[ -f "$MONITORING_ENV" ] && . "$MONITORING_ENV"
ping_backup() { # <suffix: "" | "/start" | "/fail"> [body]
  [ -n "${DOCSURI_BACKUP_PING_URL:-}" ] || return 0
  curl -fsS -o /dev/null -m 10 --retry 3 ${2:+--data-raw "$2"} \
    "$DOCSURI_BACKUP_PING_URL$1" || true
}

STAMP="$(date +%Y%m%d-%H%M%S)"
WORKDIR="$(mktemp -d)"
finish() {
  local status=$?
  rm -rf "$WORKDIR"
  if [ "$status" -eq 0 ]; then
    ping_backup ""
  else
    ping_backup "/fail" "backup exited $status — see ~/Library/Logs/docsuri-backup.log"
  fi
}
trap finish EXIT
# /start lets healthchecks.io measure run duration and catch a hung dump via the
# check's grace period, not just a missing one.
ping_backup "/start"
DUMP="$WORKDIR/docsuri-$STAMP.dump"

echo "[$(date '+%F %T')] dumping $DB_NAME …"
# Dump to a container-side temp file and verify there before copying out: pg_restore --list
# on a real file (not a pipe) is unambiguous for custom-format archives, and a dump that
# pg_restore can't even list is not a backup — fail before uploading garbage.
docker compose -f "$COMPOSE_FILE" exec -T postgres bash -c "
  set -euo pipefail
  pg_dump -U '$DB_USER' --format=custom --no-owner -f /tmp/docsuri-backup.dump '$DB_NAME'
  pg_restore --list /tmp/docsuri-backup.dump > /dev/null
"
docker compose -f "$COMPOSE_FILE" cp postgres:/tmp/docsuri-backup.dump "$DUMP"
docker compose -f "$COMPOSE_FILE" exec -T postgres rm -f /tmp/docsuri-backup.dump

# Off-machine copy = iCloud Drive (AWS decommissioned 2026-08-17; the old docsuri-backups
# S3 bucket is gone). iCloud syncs the file off this Mac, which is the durability point —
# the local Docker volume and this dump must not share a single failure domain.
#
# TCC trap (found 2026-08-18): under launchd, ~/Library/Mobile Documents allows creating
# and unlinking files by exact path but DENIES directory enumeration — find/glob die with
# "Operation not permitted" on the directory itself (the 03:30 cp succeeded every night
# while `find -mtime +30 -delete` failed right after). So iCloud is write-only from here:
# never listed, only written and deleted at constructed paths. LOCAL_DIR is the
# enumerable retention manifest, and a second restore tier that does not depend on
# iCloud sync having actually happened.
DEST_DIR="${DOCSURI_BACKUP_DIR:-$HOME/Library/Mobile Documents/com~apple~CloudDocs/DocSuriBackups/postgres}"
LOCAL_DIR="${DOCSURI_BACKUP_LOCAL_DIR:-$HOME/Backups/docsuri/postgres}"
mkdir -p "$DEST_DIR" "$LOCAL_DIR"
cp "$DUMP" "$LOCAL_DIR/docsuri-$STAMP.dump"
cp "$DUMP" "$DEST_DIR/docsuri-$STAMP.dump"

# Mirror the old S3 lifecycle: keep 30 days of dailies. Retention keys off the date IN
# THE FILENAME, not mtime: mirrored/seeded copies carry their copy time as mtime, and
# stat on an evicted (dataless) iCloud file is another TCC trap.
CUTOFF="$(date -v-30d +%Y%m%d)"
for f in "$LOCAL_DIR"/docsuri-*.dump; do
  [ -e "$f" ] || continue
  name="$(basename "$f")"
  fdate="${name#docsuri-}"; fdate="${fdate%%-*}"
  if [ "$fdate" -lt "$CUTOFF" ] 2>/dev/null; then
    # iCloud first; keep the local entry if that fails so the next run retries
    # instead of orphaning the iCloud copy forever.
    if rm -f "$DEST_DIR/$name" 2>/dev/null; then
      rm -f "$f"
      echo "[$(date '+%F %T')] pruned $name (older than 30 days)"
    else
      echo "[$(date '+%F %T')] WARNING: could not delete $name from iCloud; keeping local entry to retry"
    fi
  fi
done
echo "[$(date '+%F %T')] backup ok: $DEST_DIR/docsuri-$STAMP.dump + $LOCAL_DIR ($(du -h "$DUMP" | cut -f1))"
