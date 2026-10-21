"""Shared mechanics of the export store: column lists, argument checks, refusal mapping,
the one-clock check schedule, and the multi-row steps several units repeat.

Nothing here opens a transaction or calls Notion. Every helper takes the bounded
connection of the unit that calls it, so each unit stays one re-runnable closure.
Column lists are explicit: the runtime role cannot read `sealed_token` or
`token_key_version` on `export.connection` (D13), so no query here selects `*` from it.
"""

import datetime as dt
import hashlib
import json
import math
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from uuid import UUID

import psycopg
from psycopg.types.json import Jsonb

from backend.u6_policy import ExportPolicy

from .errors import ExportError

CONNECTION_COLUMNS = (
    "id,account_id,revision,provider,state,validated_at,workspace_name,workspace_id,"
    "connection_user_id,creation_capability,last_destination_id,limitations,created_at,"
    "updated_at"
)
APPROVAL_COLUMNS = (
    "id,account_id,preview_id,preview_revision,binding_hash,policy,approved_at,expires_at,"
    "state,invalidation_reason,approving_session,request_key"
)
EFFECT_COLUMNS = (
    "id,approval_id,account_id,artifact_id,destination_id,revision,binding_hash,state,marker,"
    "request_key,accepted_at,updated_at,waiting_since,next_attempt_at,rate_limit_started_at,"
    "next_check_at,scanning_stopped_at,ended_at,remote_reference,remote_url,"
    "reconciliation_evidence_hash,outcome_reason,settled_by,owner_assumption,limitations"
)
# A preview revision without its rendered tree; the tree travels only to the lane.
REVISION_COLUMNS = (
    "preview_id,revision,source_revision,source_content_hash,source_eligibility_revision,"
    "source_title,connection_id,connection_revision,destination,render_policy,marker,"
    "rendered_text,rendered_content_hash,binding_hash,earlier_exports,prepared_at,trimmed_at"
)
ATTEMPT_COLUMNS = (
    "id,effect_id,attempt_number,started_at,deadline_at,writer_identity,connection_revision,"
    "ended_at,response_class,provider_request_id,path_kind,creator_confirmed"
)
CHECK_COLUMNS = (
    "id,effect_id,checked_at,window_start,result,remote_reference,other_marked_pages,evidence_hash"
)

TERMINAL_EFFECT_STATES = ("succeeded", "failed", "cancelled", "invalidated")
CHECK_RESULTS = ("marker-found", "not-found", "listing-unavailable", "listing-incomplete")
INVALIDATION_REASONS = (
    "source-changed",
    "destination-changed",
    "connection-changed",
    "authority-revoked",
    "account-withdrawn",
)
# The reasons a provider refusal or an unwritten end can carry (entities.md, 18 values).
OUTCOME_REASONS = (
    "token-invalid",
    "no-access",
    "destination-missing",
    "content-rejected",
    "workspace-block-limit",
    "provider-blocked",
    "rate-limit-budget-spent",
    "not-found-after-checks",
    "owner-settled-delivered",
    "owner-settled-not-delivered",
    "dependency-unavailable",
    "policy-unresolved",
    *INVALIDATION_REASONS,
    "owner-cancelled",
)
_HEX64 = frozenset("0123456789abcdef")
NOT_FOUND = "export record not found"


@dataclass(frozen=True)
class Replay:
    """One idempotency record's identity: the owner's key and the request's input hash."""

    operation_key: UUID
    input_hash: str

    def __post_init__(self):
        require_uuid(self.operation_key, "operationKey")
        if not is_hex64(self.input_hash):
            invalid("inputHash")


def invalid(field: str):
    raise ExportError("INVALID_ARGUMENT", current={"field": field})


def not_found():
    """A foreign record and an absent one answer the same way (BR7.1)."""
    raise LookupError(NOT_FOUND)


def is_hex64(value) -> bool:
    return isinstance(value, str) and len(value) == 64 and set(value) <= _HEX64


def require_uuid(value, field: str) -> UUID:
    if not isinstance(value, UUID):
        invalid(field)
    return value


def require_optional_uuid(value, field: str) -> UUID | None:
    return None if value is None else require_uuid(value, field)


def require_now(value, field: str = "now") -> dt.datetime:
    if not isinstance(value, dt.datetime) or value.tzinfo is None:
        invalid(field)
    return value


def require_revision(value, field: str, *, minimum: int = 1) -> int:
    if type(value) is not int or value < minimum:
        invalid(field)
    return value


def require_text(value, field: str, *, limit: int = 2000) -> str:
    if not isinstance(value, str) or not 1 <= len(value.encode()) <= limit:
        invalid(field)
    return value


def require_optional_text(value, field: str, *, limit: int = 2000) -> str | None:
    return None if value is None else require_text(value, field, limit=limit)


def canonical_digest(value) -> str:
    """SHA-256 of the canonical JSON, in U4's `digest` form (sorted, compact, UTF-8)."""
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


def replay_input_hash(request: dict, *, secret_fields: tuple[str, ...] = ("token",)) -> str:
    """The replay record's input hash: the request without its secret fields (§3)."""
    if not isinstance(request, dict):
        invalid("request")
    return canonical_digest({k: v for k, v in request.items() if k not in secret_fields})


def seconds_until(later: dt.datetime, now: dt.datetime) -> int:
    """Whole seconds from `now` to `later`, at least one (a refusal's stated wait)."""
    return max(1, math.ceil((later - now).total_seconds()))


def next_check_time(
    base: dt.datetime, now: dt.datetime, policy: ExportPolicy
) -> dt.datetime | None:
    """The first scheduled check after `now`, counted from the attempt's `deadlineAt`.

    The schedule is the policy's offsets (3, 10 and 30 min), then hourly until the
    hourly phase ends, then every 3 h, within the total check period (24 h). None
    means the check period is spent and scanning stops (BR4.4).
    """
    offsets = list(policy.check_offsets_seconds)
    point = offsets[-1] + policy.check_hourly_seconds
    while point <= policy.check_hourly_until_seconds:
        offsets.append(point)
        point += policy.check_hourly_seconds
    point = offsets[-1] + policy.check_late_interval_seconds
    while point <= policy.check_total_seconds:
        offsets.append(point)
        point += policy.check_late_interval_seconds
    for offset in offsets:
        candidate = base + dt.timedelta(seconds=offset)
        if candidate > now:
            return candidate
    return None


@contextmanager
def translated(conn, *, current: dict | None = None) -> Iterator[None]:
    """A savepoint whose unique and check refusals become one CONFLICT answer.

    The schema's guards raise 23514 for every state-machine refusal, and a unique
    violation is a concurrent writer that got there first; neither leaks its text.
    """
    try:
        with conn.transaction():
            yield
    except (psycopg.errors.UniqueViolation, psycopg.errors.CheckViolation):
        conflict = ExportError("CONFLICT", current=current)
    else:
        return
    raise conflict from None


def session_current(conn, account_id: UUID, session_id: UUID) -> bool:
    """Whether a session is still current, by AccountAccess's own guard in a savepoint.

    A 42501 is the definite "no longer current" answer; any other fault propagates so
    the caller treats it as could-not-check, never as a revoked authority.
    """
    try:
        with conn.transaction():
            conn.execute(
                "SELECT accounts.guard_session(%s,%s,'local-research')",
                (account_id, session_id),
            )
    except psycopg.errors.InsufficientPrivilege:
        return False
    return True


def replay_response(conn, account_id: UUID, operation: str, replay: Replay):
    """The stored response for this key, or None; another input is IDEMPOTENCY_CONFLICT."""
    row = conn.execute(
        "SELECT input_hash,response FROM export.replay_record "
        "WHERE account_id=%s AND operation=%s AND operation_key=%s",
        (account_id, operation, replay.operation_key),
    ).fetchone()
    if row is None:
        return None
    if row["input_hash"] != replay.input_hash:
        raise ExportError("IDEMPOTENCY_CONFLICT")
    return row["response"]


def record_replay(conn, account_id: UUID, operation: str, replay: Replay, response: dict):
    """The response holds only identifiers, state, revision or a refusal code (§3)."""
    try:
        with conn.transaction():
            conn.execute(
                "INSERT INTO export.replay_record(account_id,operation,operation_key,"
                "input_hash,response) VALUES(%s,%s,%s,%s,%s)",
                (account_id, operation, replay.operation_key, replay.input_hash, Jsonb(response)),
            )
    except psycopg.errors.UniqueViolation:
        conflict = ExportError("IDEMPOTENCY_CONFLICT")
    else:
        return
    raise conflict from None


def invalidate_older_work(
    conn, account_id: UUID, connection_id: UUID, revision: int, now: dt.datetime
) -> dict:
    """BR1.4: approved approvals and accepted effects bound to an earlier connection
    revision (or to a connection that no longer exists) become invalidated, with reason
    connection-changed. Executing effects finish and unknown ones stay unknown."""
    effects = conn.execute(
        "UPDATE export.effect e SET state='invalidated',revision=e.revision+1,"
        "outcome_reason='connection-changed',ended_at=%s,updated_at=clock_timestamp() "
        "FROM export.approval a JOIN export.preview_revision r "
        "ON r.preview_id=a.preview_id AND r.revision=a.preview_revision "
        "WHERE a.id=e.approval_id AND e.account_id=%s AND e.state='accepted' "
        "AND (r.connection_id<>%s OR r.connection_revision<%s) RETURNING e.id",
        (now, account_id, connection_id, revision),
    ).fetchall()
    approvals = conn.execute(
        "UPDATE export.approval a SET state='invalidated',"
        "invalidation_reason='connection-changed' FROM export.preview_revision r "
        "WHERE r.preview_id=a.preview_id AND r.revision=a.preview_revision "
        "AND a.account_id=%s AND a.state='approved' "
        "AND (r.connection_id<>%s OR r.connection_revision<%s) RETURNING a.id",
        (account_id, connection_id, revision),
    ).fetchall()
    return {
        "approvalsInvalidated": [row["id"] for row in approvals],
        "effectsInvalidated": [row["id"] for row in effects],
    }


def trim_revision(conn, preview_id: UUID, revision: int, now: dt.datetime) -> bool:
    """The one trim of a preview revision: the tree and text go, the summary stays."""
    return (
        conn.execute(
            "UPDATE export.preview_revision SET rendered_blocks=NULL,rendered_text=NULL,"
            "trimmed_at=%s WHERE preview_id=%s AND revision=%s AND trimmed_at IS NULL",
            (now, preview_id, revision),
        ).rowcount
        == 1
    )


def apply_connection_facts(
    conn,
    connection_id: UUID,
    destination_id: str,
    *,
    attempt_revision: int | None,
    capability: str | None,
) -> None:
    """Connection facts from an outcome: every success names its destination; the
    creation capability changes only while the connection is still at the attempt's
    revision, so an older token's outcome never marks a replaced connection. Neither
    change moves the connection revision."""
    if capability not in (None, "confirmed", "refused"):
        raise ValueError("unknown creation capability")
    if destination_id is not None:
        conn.execute(
            "UPDATE export.connection SET last_destination_id=%s,updated_at=clock_timestamp() "
            "WHERE id=%s AND state<>'pending' AND last_destination_id IS DISTINCT FROM %s",
            (destination_id, connection_id, destination_id),
        )
    if capability is not None and attempt_revision is not None:
        conn.execute(
            "UPDATE export.connection SET creation_capability=%s,updated_at=clock_timestamp() "
            "WHERE id=%s AND revision=%s AND state IN ('connected','unavailable') "
            "AND creation_capability<>%s",
            (capability, connection_id, attempt_revision, capability),
        )


def effect_connection(conn, effect_id: UUID):
    """The bound connection of an effect, with the destination it names."""
    return conn.execute(
        "SELECT r.connection_id,r.connection_revision,e.destination_id FROM export.effect e "
        "JOIN export.approval a ON a.id=e.approval_id "
        "JOIN export.preview_revision r "
        "ON r.preview_id=a.preview_id AND r.revision=a.preview_revision WHERE e.id=%s",
        (effect_id,),
    ).fetchone()


def latest_attempt(conn, effect_id: UUID):
    return conn.execute(
        f"SELECT {ATTEMPT_COLUMNS} FROM export.attempt WHERE effect_id=%s "
        "ORDER BY attempt_number DESC LIMIT 1",
        (effect_id,),
    ).fetchone()


def latest_check(conn, effect_id: UUID):
    return conn.execute(
        f"SELECT {CHECK_COLUMNS} FROM export.reconciliation_check WHERE effect_id=%s "
        "ORDER BY checked_at DESC,id DESC LIMIT 1",
        (effect_id,),
    ).fetchone()


def settlement_offered(conn, effect, now: dt.datetime, policy: ExportPolicy) -> bool:
    """BR4.5: only an unknown effect past its settling wait, and only once checks cannot
    decide, the connection cannot read the destination, or scanning has stopped."""
    if effect["state"] != "unknown":
        return False
    attempt = latest_attempt(conn, effect["id"])
    if attempt is None:
        return False
    if attempt["deadline_at"] + dt.timedelta(seconds=policy.settling_wait_seconds) > now:
        return False
    if effect["scanning_stopped_at"] is not None:
        return True
    check = latest_check(conn, effect["id"])
    if check is not None and check["result"] in ("listing-unavailable", "listing-incomplete"):
        return True
    bound = effect_connection(conn, effect["id"])
    state = conn.execute(
        "SELECT state FROM export.connection WHERE id=%s", (bound["connection_id"],)
    ).fetchone()
    return state is None or state["state"] != "connected"


def newer_success(conn, account_id: UUID, artifact_id: UUID, destination_id: str, since):
    """Whether an export of the pair succeeded after `since` (decision "Newer succeeded
    export"): approve and bind refuse with CONFLICT so a fresh preview shows it."""
    return (
        conn.execute(
            "SELECT 1 FROM export.effect WHERE account_id=%s AND artifact_id=%s "
            "AND destination_id=%s AND state='succeeded' AND ended_at>%s LIMIT 1",
            (account_id, artifact_id, destination_id, since),
        ).fetchone()
        is not None
    )
