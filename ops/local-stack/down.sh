#!/usr/bin/env bash
# Tear down the DocSuri local development stack.
#
#   ./down.sh          stop containers, keep volumes
#   ./down.sh --volumes  also remove the named volumes (destroys local stack data)
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
compose_file="$here/colima-stack.compose.yaml"

if [ "${1:-}" = "--volumes" ]; then
  docker compose -f "$compose_file" down --volumes
else
  docker compose -f "$compose_file" down
fi
