#!/usr/bin/env bash
# Bring up the DocSuri local development stack on Colima.
#
# Local development only. See the header of colima-stack.compose.yaml for the pinned images and
# for the deliberate local-only relaxations.
#
# The Postgres `ssl=on` setting needs a server certificate, which the REM-1 derived image does not
# ship. The certificate is generated here and delivered with `docker cp` rather than bind-mounted,
# because Colima's virtiofs cannot hold the 0600 postgres ownership the server requires. That is the
# same delivery mechanism platform_integrity/tests/test_postgres_mtls.py already uses.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
compose_file="$here/colima-stack.compose.yaml"
cert_dir="$here/.certs"

if ! command -v colima >/dev/null 2>&1; then
  echo "colima is not installed; this stack targets Colima per the retargeted design" >&2
  exit 1
fi
# `colima status` reports on stderr, so its exit code is the reliable signal, not its output.
if ! colima status >/dev/null 2>&1; then
  echo "colima is not running; start it with: colima start" >&2
  exit 1
fi

echo "==> generating a self-signed Postgres server certificate (localhost, local dev only)"
mkdir -p "$cert_dir"
openssl req -x509 -newkey rsa:2048 -nodes -days 30 \
  -keyout "$cert_dir/server.key" -out "$cert_dir/server.crt" \
  -subj "/CN=localhost/O=DocSuri local dev" \
  -addext "subjectAltName=DNS:localhost,IP:127.0.0.1" \
  >/dev/null 2>&1
chmod 600 "$cert_dir/server.key"

echo "==> docker compose up -d"
docker compose -f "$compose_file" up -d

echo "==> installing the Postgres server certificate"
# A restart is required first: the image entrypoint regenerates pg_hba.conf on every start, and the
# container must exist before anything can be copied into it.
container="$(docker compose -f "$compose_file" ps -q postgres)"
docker cp "$cert_dir/server.crt" "$container:/tmp/rem3-server.crt"
docker cp "$cert_dir/server.key" "$container:/tmp/rem3-server.key"
docker exec --user root "$container" chown postgres:postgres \
  /var/lib/postgresql/data/server.crt /var/lib/postgresql/data/server.key \
  2>/dev/null || {
    # First boot has not created the data directory yet; wait for it, then retry.
    for _ in $(seq 1 60); do
      docker exec --user root "$container" test -d /var/lib/postgresql/data && break
      sleep 1
    done
    docker cp "$cert_dir/server.crt" "$container:/var/lib/postgresql/data/server.crt"
    docker cp "$cert_dir/server.key" "$container:/var/lib/postgresql/data/server.key"
    docker exec --user root "$container" chown postgres:postgres \
      /var/lib/postgresql/data/server.crt /var/lib/postgresql/data/server.key
  }
docker exec --user root "$container" chmod 600 \
  /var/lib/postgresql/data/server.crt /var/lib/postgresql/data/server.key

echo "==> restarting postgres so it loads the certificate"
docker compose -f "$compose_file" restart postgres

echo "==> waiting for health"
docker compose -f "$compose_file" up -d --wait --wait-timeout 240

echo
echo "==> stack status"
docker compose -f "$compose_file" ps --format 'table {{.Service}}\t{{.Status}}'

echo
# Report the ports actually published, not the defaults: OrbStack shadowing is invisible here and
# printing the defaults would hand out DSNs that do not reach this stack.
pg_port="$(docker compose -f "$compose_file" port postgres 5432 2>/dev/null | sed 's/.*://')"
redis_port="$(docker compose -f "$compose_file" port redis 6379 2>/dev/null | sed 's/.*://')"
os_port="$(docker compose -f "$compose_file" port opensearch 9200 2>/dev/null | sed 's/.*://')"
mq_port="$(docker compose -f "$compose_file" port elasticmq 9324 2>/dev/null | sed 's/.*://')"
s3_port="$(docker compose -f "$compose_file" port seaweedfs 9000 2>/dev/null | sed 's/.*://')"

echo "Postgres DSN (local only): postgresql://rem3_smoke:rem3_smoke_local_only@127.0.0.1:${pg_port:-?}/rem3_smoke?sslmode=require"
echo "Redis:                     redis://127.0.0.1:${redis_port:-?}/0"
echo "OpenSearch:                http://127.0.0.1:${os_port:-?}  (security plugin disabled: local only)"
echo "ElasticMQ (SQS):           http://127.0.0.1:${mq_port:-?}"
echo "S3 (SeaweedFS):            http://127.0.0.1:${s3_port:-?}  [S3 AUTH UNWIRED — see compose header]"
