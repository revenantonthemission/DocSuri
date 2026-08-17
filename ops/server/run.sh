#!/usr/bin/env bash
# Role dispatcher for the launchd-supervised DocSuri server processes.
#
# launchd does NOT read shell profiles, .env files, or nvm — it starts jobs with a
# near-empty environment and PATH=/usr/bin:/bin:/usr/sbin:/sbin. Every plist therefore
# invokes THIS script, which is the one place that:
#   1. resolves the repo root,
#   2. loads backend/.env (+ .env.aws-secrets) into the environment,
#   3. execs the role's real command with an ABSOLUTE interpreter path.
#
# `exec` matters: it replaces this shell with the target process so launchd's PID
# tracking, KeepAlive restarts, and SIGTERM-on-unload reach the actual worker rather
# than a wrapper that would swallow them.
#
#   ops/server/run.sh <role>
#
set -euo pipefail

ROLE="${1:?usage: run.sh <api|web|worker-ingestion|worker-summarization|worker-evidence|worker-novelty|worker-purge>}"
REPO="${DOCSURI_REPO:-$HOME/Projects/DocSuri}"
cd "$REPO"

# --- environment -----------------------------------------------------------------
# `set -a` exports every variable defined until `set +a`, which is what turns a flat
# KEY=value .env file into real process environment without listing each key.
set -a
# shellcheck disable=SC1091
[ -f backend/.env ] && . backend/.env
# Optional: re-issued third-party credentials (Resend/Notion/OIDC secrets). Absent by
# default — the app degrades gracefully rather than failing to boot.
# shellcheck disable=SC1091
[ -f backend/.env.aws-secrets ] && . backend/.env.aws-secrets
set +a

# The API and workers import in-tree packages (backend.*, docsuri_shared, discovery,
# summarization) by path rather than via an installed distribution.
export PYTHONPATH="$REPO:$REPO/shared/python:$REPO/backend/modules/discovery/src:$REPO/backend/modules/summarization/src:${PYTHONPATH:-}"
export PYTHONUNBUFFERED=1

BACKEND_PY="$REPO/backend/.venv/bin/python"
INGEST_PY="$REPO/ingestion/.venv/bin/python"
NODE_BIN="${DOCSURI_NODE_BIN:-$HOME/.nvm/versions/node/v24.14.0/bin/node}"

case "$ROLE" in
  api)
    # ONE worker on purpose. backend/app.py builds the U6 rate limiter and the
    # ObservabilityHub store in-process (app.state.*), so each additional uvicorn
    # worker would carry its own independent counter and the public rate limit
    # would silently become N x gateway_rate_limit_max_requests. FastAPI is async;
    # a single process serves concurrent requests fine.
    #
    # Bound to 127.0.0.1: the Next.js BFF reaches the API server-side over loopback,
    # and the browser never sees this address. Nothing about the API is exposed to
    # the tunnel.
    exec "$REPO/backend/.venv/bin/uvicorn" backend.main:app \
      --host 127.0.0.1 --port "${DOCSURI_API_PORT:-8000}" \
      --workers 1 --proxy-headers --forwarded-allow-ips='127.0.0.1' \
      --log-level info
    ;;

  web)
    # Next.js `output: 'standalone'` emits a self-contained server.js that does NOT
    # need `next` on PATH or node_modules resolution from the repo. Static assets are
    # not copied into it by design, so install.sh links them in after each build.
    cd "$REPO/frontend/.next/standalone"
    export PORT="${DOCSURI_WEB_PORT:-3000}"
    export HOSTNAME=127.0.0.1
    exec "$NODE_BIN" server.js
    ;;

  worker-ingestion)
    exec "$INGEST_PY" -m docsuri_ingestion.worker
    ;;
  worker-summarization)
    exec "$BACKEND_PY" -m summarization.worker
    ;;
  worker-evidence)
    exec "$BACKEND_PY" -m backend.modules.evidence.worker
    ;;
  worker-novelty)
    exec "$BACKEND_PY" -m backend.modules.novelty.worker
    ;;
  worker-purge)
    exec "$BACKEND_PY" -m backend.modules.accounts.purge_worker
    ;;

  logrotate)
    # Housekeeping, not an app process. launchd appends to StandardOutPath forever;
    # without this a chatty worker would fill the disk that OpenSearch shares.
    exec /bin/bash "$REPO/ops/server/docsurictl" rotate-logs
    ;;

  *)
    echo "unknown role: $ROLE" >&2
    exit 64
    ;;
esac
