"""C11 browser routes (U8 plan Step 39; A5, BR3.8, BR4.1, BR4.9).

`POST /api/v2/c11/read-dashboard`, `/list-incidents`, `/request-recovery` and
`/read-recovery-status`, behind the shared browser boundary and AccountAccess's
administration guard:

- each answers only an administrator whose current session completed its second factor
  within the guard's bound (`accounts.guard_session` with purpose `administration`);
- an administrator whose second factor is not current gets FORBIDDEN, so the workspace
  shows its MFA prompt, and everyone else gets the ordinary not-found answer: neither
  carries a count or an identifier (BR3.8);
- `request-recovery` records a RecoveryRequest in the operations ledger as `requested`
  (or recovers the one this submission made), and answers a stale expected revision with
  CONFLICT (BR4.9). A request naming an incident is written in one ledger step with the
  incident's versions (L1-19, L1-64): an open incident's `investigating` version
  (`recovery-requested`), the request, then its `recovering` version. Any refusal writes
  nothing and leaves the incident open; an incident resolved meanwhile is CONFLICT
  before any request exists, and a replay appends nothing. Platform effects still need
  the operator in person (C11 semantics);
- no route records a decision: your decisions are recorded only through PlatformControl's
  `platform.decision.record` and read from the ledger (A5).
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable
from uuid import UUID

import psycopg
from docsuri_shared.workspace import wire
from fastapi import APIRouter, Request
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool

from backend.local_browser import (
    BrowserDenied,
    boundary_route,
    post_context,
    read_payload,
    request_identifier,
)
from backend.transactions import Authority, guard

from .errors import LedgerDamaged, OperationsError
from .incidents import Incidents
from .ledger import utc_text
from .recovery import RecoveryRequests

PREFIX = "/api/v2/c11/"
# The guard's own bound for a current second factor (`u8_session_authority.sql`).
MFA_SECONDS = 300
STATUS = {"INVALID_INPUT": 422, "FORBIDDEN": 403, "NOT_FOUND": 404, "CONFLICT": 409,
          "POLICY_UNRESOLVED": 503, "DEPENDENCY_UNAVAILABLE": 503, "UNKNOWN_OUTCOME": 409}
CODES = {"INVALID_INPUT": "INVALID_ARGUMENT"}
# A RecoveryRequest's state as C13's JobReceipt names a job's.
RECEIPT_STATE = {
    "requested": "accepted", "awaiting-operator": "accepted", "running": "running",
    "verifying": "running", "post-restore-pending": "running", "held": "running",
    "unknown": "running", "succeeded": "succeeded", "failed": "failed", "refused": "failed",
    "expired": "failed", "cancelled": "cancelled",
}


def policy_reference(policy) -> dict:
    """The policy reference a recovery request names: the operations policy in force."""
    return {"policyId": f"u8-operations-{policy.name}", "revision": "1"}


def administrator_check(transactions, authority: Authority) -> dt.datetime:
    """The session's second-factor time when the caller is an administrator with a current
    second factor; FORBIDDEN for an administrator without one, NOT_FOUND for anyone else."""

    def check(conn):
        account = conn.execute("SELECT role FROM accounts.account WHERE id=%s",
                               (authority.account_id,)).fetchone()
        if account is None or account["role"] != "administrator":
            return "not-found"
        try:
            with conn.transaction():
                guard(conn, authority, purpose="administration")
        except psycopg.Error:
            return "mfa"
        return conn.execute(
            "SELECT mfa_at FROM accounts.session WHERE id=%s AND account_id=%s",
            (authority.session_id, authority.account_id),
        ).fetchone()["mfa_at"]

    outcome = transactions.run("accounts", check)
    if outcome == "not-found":
        raise BrowserDenied(404, "NOT_FOUND")
    if outcome == "mfa" or outcome is None:
        raise BrowserDenied(403, "FORBIDDEN")
    return outcome


def operations_router(transactions, *, entry, dashboard, ledger, policy, environment: str,
                      clock: Callable[[], dt.datetime]) -> APIRouter:
    origin = transactions.profile.origin
    router = APIRouter(route_class=boundary_route(origin, missing=(404, "NOT_FOUND")))
    reference = policy_reference(policy)

    def mfa_current(requested_by: str, verified_at: str) -> bool:
        # The factor's time is the database's (`control_mfa.verify` writes `mfa_at` from
        # `clock_timestamp()`, and the administration guard reads it so), so its age is
        # measured on that clock too: the composed realm's delegated clock may stand
        # ahead of it, which refused every administrator request once a journey had
        # moved that clock (the recovery journey found it).
        moment = dt.datetime.fromisoformat(verified_at.replace("Z", "+00:00"))
        database_now = transactions.run(
            "accounts",
            lambda conn: conn.execute("SELECT clock_timestamp() AS now").fetchone()["now"])
        return database_now - moment < dt.timedelta(seconds=MFA_SECONDS)

    requests = RecoveryRequests(ledger, policy, clock=clock, mfa_current=mfa_current)
    incidents = Incidents(ledger, environment=environment)

    def answer(work, output):
        try:
            result = work()
        except OperationsError as error:
            code = error.code
            raise BrowserDenied(STATUS.get(code, 500), CODES.get(code, code)) from None
        except LedgerDamaged:
            raise BrowserDenied(503, "DEPENDENCY_UNAVAILABLE") from None
        try:
            return output.model_validate(result).model_dump(mode="json")
        except ValidationError:
            raise BrowserDenied(500, "INTERNAL_ERROR") from None

    async def administrator(request: Request, schema):
        _, _, authority = await post_context(request, origin=origin, entry=entry,
                                             anonymous=None)
        verified = await run_in_threadpool(administrator_check, transactions, authority)
        value = await read_payload(request, schema)
        return authority, verified, value

    @router.post(PREFIX + "read-dashboard")
    async def read_dashboard(request: Request):
        _, _, value = await administrator(request, wire.OpsQueryHttp)
        return await run_in_threadpool(answer, lambda: dashboard.read(value),
                                       wire.OpsDashboardPage)

    @router.post(PREFIX + "list-incidents")
    async def list_incidents(request: Request):
        _, _, value = await administrator(request, wire.OpsQueryHttp)
        return await run_in_threadpool(answer, lambda: dashboard.incidents(value),
                                       wire.OpsIncidentReadPage)

    def submit(authority: Authority, verified: dt.datetime, value: dict) -> dict:
        if value["policy"] != reference:
            raise OperationsError("POLICY_UNRESOLVED")
        try:
            expected = int(value["expectedRevision"])
        except ValueError:
            raise OperationsError("INVALID_INPUT") from None
        # The request and its incident's versions are one ledger step (L1-19, L1-64).
        record = requests.request(
            origin=value["origin"], operation=value["operation"], environment=environment,
            target_id=value["targetId"], expected_revision=expected,
            submission_id=value["submissionId"], requested_by=authority.account_id,
            mfa_verified_at=utc_text(verified), incident_id=value.get("incidentId"),
            incidents=incidents,
        )
        return {
            "jobId": record["recoveryRequestId"], "revision": str(record["revision"]),
            "seq": int(record["revision"]), "state": RECEIPT_STATE[record["state"]],
            "requestId": request_identifier(), "acceptedAt": record["createdAt"],
        }

    @router.post(PREFIX + "request-recovery")
    async def request_recovery(request: Request):
        authority, verified, value = await administrator(request, wire.OpsRecoverySubmissionHttp)
        return await run_in_threadpool(answer, lambda: submit(authority, verified, value),
                                       wire.JobReceipt)

    @router.post(PREFIX + "read-recovery-status")
    async def read_recovery_status(request: Request):
        _, _, value = await administrator(request, wire.OpsRecoveryStatusReadHttp)
        try:
            identity = str(UUID(value["recoveryRequestId"]))
        except ValueError:
            raise BrowserDenied(404, "NOT_FOUND") from None

        def read():
            status = requests.status(identity)
            if status["environment"] != environment:
                raise OperationsError("NOT_FOUND")
            return status

        return await run_in_threadpool(answer, read, wire.OpsRecoveryStatus)

    return router
