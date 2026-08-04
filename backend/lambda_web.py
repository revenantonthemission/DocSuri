"""Lambda web bootstrap for the dev-profile API Lambda (serverless-plan Phase 1-③).

Runs ONLY as the container cmd on Lambda (``cmd=["python", "-m", "backend.lambda_web"]`` in
the dev CDK profile); the ECS image CMD stays uvicorn directly, so this module never runs
there. The Lambda Web Adapter extension (``/opt/extensions/lambda-adapter``, see
backend/Dockerfile) translates Function URL invokes into plain HTTP against the uvicorn
server this module exec's on :8000 (``PORT`` env).

DB credentials: same constraint as the cron functions — Lambda env cannot reference Secrets
Manager, so the function ships ``DB_SECRET_ARN`` and this bootstrap reuses the
``backend.lambda_entry`` helpers to inject ``DB_PASSWORD`` / assemble ``DATABASE_URL`` before
handing the process over to uvicorn via ``os.execvp`` (exec, not subprocess: uvicorn must BE
pid-of-record so signals/stdout behave exactly as the image CMD).
"""

from __future__ import annotations

import os

from backend.lambda_entry import _ensure_database_url, _inject_db_credentials

# Exactly the image CMD (backend/Dockerfile) — the adapter just needs the server on :8000.
UVICORN_ARGV = [
    "python",
    "-m",
    "uvicorn",
    "backend.main:app",
    "--host",
    "0.0.0.0",
    "--port",
    "8000",
]


def main() -> None:
    _inject_db_credentials()
    _ensure_database_url()
    os.execvp(UVICORN_ARGV[0], UVICORN_ARGV)


if __name__ == "__main__":
    main()
