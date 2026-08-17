#!/usr/bin/env bash
# DocSuri local-serving Postgres backup — dump inside the compose container → verify → iCloud.
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

STAMP="$(date +%Y%m%d-%H%M%S)"
WORKDIR="$(mktemp -d)"
trap 'rm -rf "$WORKDIR"' EXIT
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
DEST_DIR="${DOCSURI_BACKUP_DIR:-$HOME/Library/Mobile Documents/com~apple~CloudDocs/DocSuriBackups/postgres}"
mkdir -p "$DEST_DIR"
cp "$DUMP" "$DEST_DIR/docsuri-$STAMP.dump"
# Mirror the old S3 lifecycle: keep 30 days of dailies, prune older.
find "$DEST_DIR" -name 'docsuri-*.dump' -mtime +30 -delete
echo "[$(date '+%F %T')] backup ok: $DEST_DIR/docsuri-$STAMP.dump ($(du -h "$DUMP" | cut -f1))"
