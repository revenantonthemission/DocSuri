"""Lambda cron entrypoint for the dev-profile maintenance jobs (serverless-plan Phase 1-②).

The dev CDK profile runs the two EventBridge-scheduled maintenance jobs as container-image
Lambdas built from the SAME ``docsuri-api`` image the ECS tasks used (image entrypoint
overridden to ``python -m awslambdaric``, cmd → this handler). The EventBridge rule input
carries ``{"job": <name>}`` and each job dispatches to the SAME module entrypoint the ECS
``python -m`` command ran, so behavior stays identical to prod.

DB credentials: ECS injected ``DB_PASSWORD`` via container ``secrets=``; Lambda environment
variables cannot reference Secrets Manager, so the function receives ``DB_SECRET_ARN`` (+
``secretsmanager:GetSecretValue``) instead and this module fetches the password once per
execution environment (cold start — the ``DB_PASSWORD`` guard makes warm invokes a no-op)
and injects it into ``os.environ`` before dispatch. ``DATABASE_URL`` is then assembled from
the ECS-shaped ``DB_*`` split for entrypoints that read the full DSN (purge_worker).

Exceptions propagate (and non-zero exit statuses are raised) so Lambda marks the invocation
failed and the failure is visible to EventBridge/CloudWatch.
"""

from __future__ import annotations

import json
import os
from typing import Any


def _inject_db_credentials() -> None:
    """Fetch the DB password from Secrets Manager (DB_SECRET_ARN) into DB_PASSWORD."""
    secret_arn = os.getenv("DB_SECRET_ARN")
    if not secret_arn or os.getenv("DB_PASSWORD"):
        return
    import boto3  # deferred: not needed for local/test dispatch

    client = boto3.client("secretsmanager")
    payload = json.loads(client.get_secret_value(SecretId=secret_arn)["SecretString"])
    os.environ["DB_PASSWORD"] = payload["password"]


def _ensure_database_url() -> None:
    """Assemble DATABASE_URL from the DB_* split (the ECS env shape) if not explicitly set.

    purge_worker reads the full DSN; the CDK env ships DB_HOST/PORT/NAME/USER + the secret
    password, so build the same DSN ``Settings.from_env`` resolves for the API path. Gated on
    DB_HOST so a bare local/test run never gets a surprise sqlite DATABASE_URL injected.
    """
    if os.getenv("DATABASE_URL") or not os.getenv("DB_HOST"):
        return
    from backend.config import Settings

    os.environ["DATABASE_URL"] = Settings.from_env().database_url


def _run_personalization_maintenance() -> int:
    from backend.modules.personalization.maintenance import run

    return run()


def _run_account_purge() -> int:
    from backend.modules.accounts.purge_worker import main

    return main()


_JOBS = {
    "personalization_maintenance": _run_personalization_maintenance,
    "account_purge": _run_account_purge,
}


def handler(event: dict[str, Any] | None, context: object) -> dict[str, str]:
    job = (event or {}).get("job")
    runner = _JOBS.get(job)
    if runner is None:
        raise ValueError(f"unknown job: {job!r} (expected one of {sorted(_JOBS)})")
    _inject_db_credentials()
    _ensure_database_url()
    status = runner()
    if status != 0:
        raise RuntimeError(f"job {job!r} exited with status {status}")
    return {"job": job, "status": "ok"}
