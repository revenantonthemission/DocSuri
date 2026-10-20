"""Lane and pass units of the export store, run as the service through `system`.

No unit here calls Notion (D8): the lane records, calls outside any transaction, then
records again. Each unit is a compare-and-set on the effect revision and returns None
when the record moved on. Entering `executing` and inserting its attempt are one
transaction (NFR4.8); the schema's deferred trigger refuses any commit that breaks it.
Every due-time decision compares against the caller's `now`; only the pace reservation
uses the database clock (D6, security design §9.2).
"""

import datetime as dt
from dataclasses import dataclass, field
from uuid import UUID, uuid4

import psycopg
from psycopg.types.json import Jsonb

from backend.transactions import Busy

from .store_support import (
    ATTEMPT_COLUMNS,
    CHECK_RESULTS,
    EFFECT_COLUMNS,
    INVALIDATION_REASONS,
    OUTCOME_REASONS,
    REVISION_COLUMNS,
    apply_connection_facts,
    effect_connection,
    invalid,
    is_hex64,
    latest_attempt,
    latest_check,
    next_check_time,
    require_now,
    require_optional_text,
    require_revision,
    require_text,
    require_uuid,
    session_current,
)

RESPONSE_CLASSES = ("created", "refused", "rate-limited", "uncertain")
ORPHAN_LIMITATION = "orphaned-attempt"
# The evidence gap of an orphaned attempt, recorded once within the 16-entry bound.
_ORPHAN_GAP = (
    ",limitations=CASE WHEN limitations @> '[\"orphaned-attempt\"]'::jsonb "
    "OR jsonb_array_length(limitations)>=16 THEN limitations "
    "ELSE limitations || '[\"orphaned-attempt\"]'::jsonb END"
)
# Reasons that end an unwritten effect as failed rather than invalidated.
UNWRITTEN_FAILURES = ("dependency-unavailable", "policy-unresolved", "rate-limit-budget-spent")


@dataclass(frozen=True)
class Claimed:
    effect: dict
    attempt: dict


@dataclass(frozen=True)
class ClaimRefused:
    """A definite change (`connection-changed`, `authority-revoked`) or, for an
    unavailable connection, `connection-unavailable` (could not check, BR1.6)."""

    reason: str


@dataclass(frozen=True)
class WriteOutcome:
    """One classified write answer (security design §7), with no provider text."""

    response_class: str
    provider_request_id: str | None = None
    creator_confirmed: bool | None = None
    remote_reference: str | None = None
    remote_url: str | None = None
    reason: str | None = None
    retry_at: dt.datetime | None = None

    def __post_init__(self):
        if self.response_class not in RESPONSE_CLASSES:
            invalid("responseClass")
        require_optional_text(self.provider_request_id, "providerRequestId", limit=128)
        if self.creator_confirmed not in (None, True, False):
            invalid("creatorConfirmed")
        created = self.response_class == "created"
        if created != (self.remote_reference is not None):
            invalid("remoteReference")
        require_optional_text(self.remote_reference, "remoteReference", limit=128)
        require_optional_text(self.remote_url, "remoteUrl", limit=2048)
        if (self.response_class == "refused") != (self.reason in OUTCOME_REASONS):
            invalid("reason")
        if (self.response_class == "rate-limited") != (self.retry_at is not None):
            invalid("retryAt")
        if self.retry_at is not None:
            require_now(self.retry_at, "retryAt")


@dataclass(frozen=True)
class CheckResult:
    """One reconciliation scan's result and its evidence (BR4.4)."""

    result: str
    window_start: dt.datetime
    evidence_hash: str
    remote_reference: str | None = None
    remote_url: str | None = None
    other_marked_pages: list = field(default_factory=list)

    def __post_init__(self):
        if self.result not in CHECK_RESULTS:
            invalid("result")
        require_now(self.window_start, "windowStart")
        if not is_hex64(self.evidence_hash):
            invalid("evidenceHash")
        if (self.result == "marker-found") != (self.remote_reference is not None):
            invalid("remoteReference")
        require_optional_text(self.remote_url, "remoteUrl", limit=2048)
        if not isinstance(self.other_marked_pages, list) or len(self.other_marked_pages) > 10:
            invalid("otherMarkedPages")


@dataclass(frozen=True)
class PaceSlot:
    """A reserved pace slot on the database clock (D6)."""

    slot_at: dt.datetime
    database_now: dt.datetime
    within_budget: bool

    @property
    def wait_seconds(self) -> float:
        return max(0.0, (self.slot_at - self.database_now).total_seconds())


def _locked_effect(conn, effect_id: UUID, expected_revision: int, state: str | tuple):
    states = (state,) if isinstance(state, str) else state
    effect = conn.execute(
        f"SELECT {EFFECT_COLUMNS} FROM export.effect WHERE id=%s FOR UPDATE", (effect_id,)
    ).fetchone()
    if effect is None or effect["revision"] != expected_revision or effect["state"] not in states:
        return None
    return effect


def _update_effect(conn, effect_id: UUID, assignments: str, params: tuple):
    return conn.execute(
        f"UPDATE export.effect SET revision=revision+1,updated_at=clock_timestamp(),{assignments} "
        f"WHERE id=%s RETURNING {EFFECT_COLUMNS}",
        (*params, effect_id),
    ).fetchone()


def _schedule_unknown(conn, effect_id: UUID, attempt, now, policy, *, evidence=None, extra=""):
    """Make or keep an effect unknown, waiting for its next scheduled check counted from
    the attempt's `deadlineAt`, or stop scanning once the check period is spent (BR4.4).
    `extra` adds assignments of the same single update."""
    upcoming = next_check_time(attempt["deadline_at"], now, policy)
    return _update_effect(
        conn,
        effect_id,
        "state='unknown',next_check_at=%s,scanning_stopped_at=CASE WHEN %s::timestamptz IS NULL "
        "THEN coalesce(scanning_stopped_at,%s) END,"
        "reconciliation_evidence_hash=coalesce(%s,reconciliation_evidence_hash)" + extra,
        (upcoming, upcoming, now, evidence),
    )


class LaneUnits:
    # -- hand-over ---------------------------------------------------------------

    def due_items(self, now: dt.datetime, limit: int | None = None) -> list[dict]:
        """Due work in security design §8.1's order: an executing effect whose
        rate-limit wait has passed; the oldest accepted effect of an owner with nothing
        executing; an unknown effect whose next check is due."""
        require_now(now)
        limit = self.policy.pass_batch if limit is None else limit
        if type(limit) is not int or not 1 <= limit <= 100:
            invalid("limit")
        return self.system(
            lambda conn: conn.execute(
                "SELECT kind,id,account_id,revision,state,due_at FROM ("
                "SELECT 1 AS priority,'resume' AS kind,e.id,e.account_id,e.revision,e.state,"
                "e.next_attempt_at AS due_at FROM export.effect e WHERE e.state='executing' "
                "AND e.next_attempt_at<=%(now)s AND NOT EXISTS (SELECT 1 FROM export.attempt t "
                "WHERE t.effect_id=e.id AND t.ended_at IS NULL) "
                "UNION ALL SELECT 2,'execute',e.id,e.account_id,e.revision,e.state,e.accepted_at "
                "FROM export.effect e WHERE e.state='accepted' AND NOT EXISTS (SELECT 1 FROM "
                "export.effect x WHERE x.account_id=e.account_id AND x.state='executing') "
                "UNION ALL SELECT 3,'scan',e.id,e.account_id,e.revision,e.state,e.next_check_at "
                "FROM export.effect e WHERE e.state='unknown' AND e.next_check_at<=%(now)s "
                "AND e.scanning_stopped_at IS NULL) due "
                "ORDER BY priority,due_at,id LIMIT %(limit)s",
                {"now": now, "limit": limit},
            ).fetchall()
        )

    def push_next_check(self, effect_id: UUID, expected_revision: int, *, now: dt.datetime):
        """At hand-over of a scan, move `next_check_at` past the scan budget plus one
        minute so no second worker starts the same scan. Returns the new revision."""
        require_uuid(effect_id, "effectId")
        require_revision(expected_revision, "expectedRevision")
        require_now(now)
        later = now + dt.timedelta(seconds=self.policy.scan_budget_seconds + 60)

        def push(conn):
            if _locked_effect(conn, effect_id, expected_revision, "unknown") is None:
                return None
            return _update_effect(conn, effect_id, "next_check_at=%s", (later,))["revision"]

        return self.system(push)

    def effect_binding(self, effect_id: UUID) -> dict | None:
        """Everything the lane needs for one effect: the effect, its approval's owner and
        session, the bound preview revision with its frozen tree (the content port), the
        current connection, the attempts' writer identities and the latest check."""
        require_uuid(effect_id, "effectId")

        def read(conn):
            effect = conn.execute(
                f"SELECT {EFFECT_COLUMNS} FROM export.effect WHERE id=%s", (effect_id,)
            ).fetchone()
            if effect is None:
                return None
            approval = conn.execute(
                "SELECT id,account_id,approving_session,preview_id,preview_revision "
                "FROM export.approval WHERE id=%s",
                (effect["approval_id"],),
            ).fetchone()
            revision = conn.execute(
                f"SELECT {REVISION_COLUMNS},rendered_blocks FROM export.preview_revision "
                "WHERE preview_id=%s AND revision=%s",
                (approval["preview_id"], approval["preview_revision"]),
            ).fetchone()
            connection = conn.execute(
                "SELECT id,revision,state,connection_user_id,creation_capability "
                "FROM export.connection WHERE id=%s",
                (revision["connection_id"],),
            ).fetchone()
            attempts = conn.execute(
                f"SELECT {ATTEMPT_COLUMNS} FROM export.attempt WHERE effect_id=%s "
                "ORDER BY attempt_number",
                (effect_id,),
            ).fetchall()
            return {
                "effect": effect,
                "approval": approval,
                "revision": revision,
                "connection": connection,
                "attempts": attempts,
                "writerIdentities": sorted({a["writer_identity"] for a in attempts}),
                "firstAttemptAt": attempts[0]["started_at"] if attempts else None,
                "latestCheck": latest_check(conn, effect_id),
            }

        return self.system(read)

    # -- claim and write outcomes ---------------------------------------------------

    def claim(
        self,
        effect_id: UUID,
        expected_revision: int,
        *,
        now: dt.datetime,
        path_kind: str = "synthetic",
    ):
        """Compare-and-set into `executing` with the attempt in the same transaction
        (NFR4.8): from accepted, or resuming a passed rate-limit wait. The guard checks
        the bound connection revision and the approving session (security design §8.2).
        Returns Claimed, ClaimRefused, or None when the effect moved on. A second owner
        export cannot be executing: the schema's in-flight index allows one per owner.
        """
        require_uuid(effect_id, "effectId")
        require_revision(expected_revision, "expectedRevision")
        require_now(now)
        if path_kind not in ("synthetic", "real"):
            invalid("pathKind")
        deadline = dt.timedelta(seconds=self.policy.write_deadline_seconds)

        def claim(conn):
            effect = _locked_effect(conn, effect_id, expected_revision, ("accepted", "executing"))
            if effect is None:
                return None
            previous = latest_attempt(conn, effect_id)
            if effect["state"] == "executing" and not (
                previous is not None
                and previous["response_class"] == "rate-limited"
                and effect["next_attempt_at"] is not None
                and effect["next_attempt_at"] <= now
            ):
                return None
            refusal, connection = self._claim_guard(conn, effect)
            if refusal is not None:
                return ClaimRefused(refusal)
            claimed = _update_effect(
                conn, effect_id, "state='executing',waiting_since=NULL,next_attempt_at=NULL", ()
            )
            attempt = conn.execute(
                "INSERT INTO export.attempt(id,effect_id,attempt_number,started_at,deadline_at,"
                "writer_identity,connection_revision,path_kind) VALUES(%s,%s,%s,%s,%s,%s,%s,%s) "
                f"RETURNING {ATTEMPT_COLUMNS}",
                (
                    uuid4(),
                    effect_id,
                    (previous["attempt_number"] + 1) if previous else 1,
                    now,
                    now + deadline,
                    connection["connection_user_id"],
                    connection["revision"],
                    path_kind,
                ),
            ).fetchone()
            return Claimed(claimed, attempt)

        return self.system(claim)

    @staticmethod
    def _claim_guard(conn, effect):
        bound = effect_connection(conn, effect["id"])
        connection = conn.execute(
            "SELECT revision,state,connection_user_id FROM export.connection WHERE id=%s",
            (bound["connection_id"],),
        ).fetchone()
        if connection is None or connection["revision"] != bound["connection_revision"]:
            return "connection-changed", None
        if connection["state"] != "connected" or connection["connection_user_id"] is None:
            return "connection-unavailable", None
        approval = conn.execute(
            "SELECT account_id,approving_session FROM export.approval WHERE id=%s",
            (effect["approval_id"],),
        ).fetchone()
        if not session_current(conn, approval["account_id"], approval["approving_session"]):
            return "authority-revoked", None
        return None, connection

    def record_write_outcome(
        self,
        effect_id: UUID,
        attempt_id: UUID,
        expected_revision: int,
        outcome: WriteOutcome,
        *,
        now: dt.datetime,
    ):
        """Record one classified answer on its outstanding attempt and move the effect:
        created → succeeded, refused → failed, rate-limited → still executing with its
        next attempt time, uncertain → unknown. Applies the connection facts of decision
        "Connection facts from outcomes". None when the effect or attempt moved on."""
        require_uuid(effect_id, "effectId")
        require_uuid(attempt_id, "attemptId")
        require_revision(expected_revision, "expectedRevision")
        if not isinstance(outcome, WriteOutcome):
            invalid("outcome")
        require_now(now)

        def record(conn):
            effect = _locked_effect(conn, effect_id, expected_revision, "executing")
            attempt = latest_attempt(conn, effect_id) if effect else None
            if attempt is None or attempt["id"] != attempt_id or attempt["ended_at"] is not None:
                return None
            conn.execute(
                "UPDATE export.attempt SET ended_at=%s,response_class=%s,provider_request_id=%s,"
                "creator_confirmed=%s WHERE id=%s",
                (
                    now,
                    outcome.response_class,
                    outcome.provider_request_id,
                    outcome.creator_confirmed,
                    attempt_id,
                ),
            )
            return self._apply_outcome(conn, effect, attempt, outcome, now)

        return self.system(record)

    def _apply_outcome(self, conn, effect, attempt, outcome: WriteOutcome, now):
        kind = outcome.response_class
        if kind == "created":
            moved = _update_effect(
                conn,
                effect["id"],
                "state='succeeded',remote_reference=%s,remote_url=%s,settled_by='provider',"
                "ended_at=%s",
                (outcome.remote_reference, outcome.remote_url, now),
            )
        elif kind == "refused":
            moved = _update_effect(
                conn,
                effect["id"],
                "state='failed',outcome_reason=%s,settled_by='provider',ended_at=%s",
                (outcome.reason, now),
            )
        elif kind == "rate-limited":
            return _update_effect(
                conn,
                effect["id"],
                "next_attempt_at=%s,rate_limit_started_at=coalesce(rate_limit_started_at,%s)",
                (outcome.retry_at, now),
            )
        else:
            return _schedule_unknown(conn, effect["id"], attempt, now, self.policy)
        bound = effect_connection(conn, effect["id"])
        capability = {"created": "confirmed"}.get(kind)
        if kind == "refused" and outcome.reason == "no-access":
            capability = "refused"
        apply_connection_facts(
            conn,
            bound["connection_id"],
            bound["destination_id"] if kind == "created" else None,
            attempt_revision=attempt["connection_revision"],
            capability=capability,
        )
        return moved

    def mark_waiting(self, effect_id: UUID, expected_revision: int, *, now: dt.datetime):
        """BR3.3: a pre-write check could not complete; the effect waits from the first
        such pass (`waiting_since`). Returns the effect, unchanged when already waiting."""
        require_uuid(effect_id, "effectId")
        require_revision(expected_revision, "expectedRevision")
        require_now(now)

        def wait(conn):
            effect = _locked_effect(conn, effect_id, expected_revision, ("accepted", "executing"))
            if effect is None or effect["waiting_since"] is not None:
                return effect
            return _update_effect(conn, effect_id, "waiting_since=%s", (now,))

        return self.system(wait)

    def end_unwritten(
        self, effect_id: UUID, expected_revision: int, reason: str, *, now: dt.datetime
    ):
        """End an effect nothing was written for: an accepted effect with a definite
        change becomes invalidated; a resumed one, a spent rate-limit budget or a passed
        could-not-check bound becomes failed. Never while an attempt is outstanding."""
        require_uuid(effect_id, "effectId")
        require_revision(expected_revision, "expectedRevision")
        if reason not in INVALIDATION_REASONS and reason not in UNWRITTEN_FAILURES:
            invalid("reason")
        require_now(now)

        def end(conn):
            effect = _locked_effect(conn, effect_id, expected_revision, ("accepted", "executing"))
            if effect is None:
                return None
            attempt = latest_attempt(conn, effect_id)
            if attempt is not None and attempt["ended_at"] is None:
                return None
            invalidated = effect["state"] == "accepted" and reason in INVALIDATION_REASONS
            state = "invalidated" if invalidated else "failed"
            return _update_effect(
                conn, effect_id, "state=%s,outcome_reason=%s,ended_at=%s", (state, reason, now)
            )

        return self.system(end)

    # -- reconciliation and orphans -------------------------------------------------

    def record_check(
        self, effect_id: UUID, expected_revision: int, check: CheckResult, *, now: dt.datetime
    ):
        """Record one scan (insert-only) and move the unknown effect: a marker found makes
        it succeeded; a second complete clean scan at least one settling interval after
        an earlier one fails it (not-found-after-checks); otherwise it waits for its next
        scheduled check, or stops scanning when the check period is spent (BR4.4)."""
        require_uuid(effect_id, "effectId")
        require_revision(expected_revision, "expectedRevision")
        if not isinstance(check, CheckResult):
            invalid("check")
        require_now(now)
        settling = dt.timedelta(seconds=self.policy.settling_wait_seconds)

        def record(conn):
            effect = _locked_effect(conn, effect_id, expected_revision, "unknown")
            if effect is None:
                return None
            earlier_clean = conn.execute(
                "SELECT 1 FROM export.reconciliation_check WHERE effect_id=%s "
                "AND result='not-found' AND checked_at<=%s LIMIT 1",
                (effect_id, now - settling),
            ).fetchone()
            conn.execute(
                "INSERT INTO export.reconciliation_check(id,effect_id,checked_at,window_start,"
                "result,remote_reference,other_marked_pages,evidence_hash) "
                "VALUES(%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    uuid4(),
                    effect_id,
                    now,
                    check.window_start,
                    check.result,
                    check.remote_reference,
                    Jsonb(check.other_marked_pages),
                    check.evidence_hash,
                ),
            )
            attempt = latest_attempt(conn, effect_id)
            if check.result == "marker-found":
                return self._marker_found(conn, effect, attempt, check, now)
            if check.result == "not-found" and earlier_clean is not None:
                return _update_effect(
                    conn,
                    effect_id,
                    "state='failed',outcome_reason='not-found-after-checks',"
                    "settled_by='reconciliation',reconciliation_evidence_hash=%s,ended_at=%s,"
                    "next_check_at=NULL",
                    (check.evidence_hash, now),
                )
            return _schedule_unknown(
                conn, effect_id, attempt, now, self.policy, evidence=check.evidence_hash
            )

        return self.system(record)

    @staticmethod
    def _marker_found(conn, effect, attempt, check: CheckResult, now):
        moved = _update_effect(
            conn,
            effect["id"],
            "state='succeeded',remote_reference=%s,remote_url=%s,settled_by='reconciliation',"
            "reconciliation_evidence_hash=%s,ended_at=%s,next_check_at=NULL",
            (check.remote_reference, check.remote_url, check.evidence_hash, now),
        )
        bound = effect_connection(conn, effect["id"])
        apply_connection_facts(
            conn,
            bound["connection_id"],
            bound["destination_id"],
            attempt_revision=attempt["connection_revision"] if attempt else None,
            capability="confirmed",
        )
        return moved

    def sweep_orphans(self, now: dt.datetime) -> list[UUID]:
        """BR4.6: an attempt still outstanding past the orphan threshold has no live
        holder. Its effect becomes unknown, the attempt is closed as uncertain and the
        evidence gap is recorded as a limitation. Returns the effects moved."""
        require_now(now)
        threshold = now - dt.timedelta(seconds=self.policy.orphan_after_seconds)

        def sweep(conn):
            orphans = conn.execute(
                "SELECT e.id AS effect_id,t.id AS attempt_id FROM export.effect e "
                "JOIN export.attempt t ON t.effect_id=e.id AND t.ended_at IS NULL "
                "WHERE e.state='executing' AND t.started_at<=%s "
                "ORDER BY t.started_at,e.id LIMIT %s FOR UPDATE OF e SKIP LOCKED",
                (threshold, self.policy.housekeeping_batch),
            ).fetchall()
            moved = []
            for orphan in orphans:
                attempt = conn.execute(
                    "UPDATE export.attempt SET ended_at=%s,response_class='uncertain' "
                    f"WHERE id=%s RETURNING {ATTEMPT_COLUMNS}",
                    (now, orphan["attempt_id"]),
                ).fetchone()
                _schedule_unknown(
                    conn, orphan["effect_id"], attempt, now, self.policy, extra=_ORPHAN_GAP
                )
                moved.append(orphan["effect_id"])
            return moved

        return self.system(sweep)

    # -- pace, status and lane record -------------------------------------------------

    def reserve_pace_slot(self, connection_id: UUID, *, remaining_seconds: float):
        """Reserve the connection's next pace slot in one statement on the database
        clock (§9.2). The slot is left used even when it lies past the remaining budget
        (`within_budget` False). None when the pace record is missing or the reservation
        is busy: both are could-not-check, and neither is retried in a loop."""
        require_uuid(connection_id, "connectionId")
        if not isinstance(remaining_seconds, (int, float)) or remaining_seconds < 0:
            invalid("remainingSeconds")
        interval = self.policy.pace_interval_ms / 1000

        def reserve(conn):
            return conn.execute(
                "UPDATE export.connection_pace SET next_slot_at="
                "greatest(next_slot_at,clock_timestamp())+make_interval(secs=>%s) "
                "WHERE connection_id=%s RETURNING next_slot_at-make_interval(secs=>%s) AS slot_at,"
                "clock_timestamp() AS database_now",
                (interval, connection_id, interval),
            ).fetchone()

        try:
            row = self.system(reserve)
        except (Busy, psycopg.OperationalError):
            return None
        if row is None:
            return None
        wait = (row["slot_at"] - row["database_now"]).total_seconds()
        return PaceSlot(row["slot_at"], row["database_now"], wait <= remaining_seconds)

    def status_counts(self, now: dt.datetime) -> dict:
        """Counts and ages only (logical-components §8)."""
        require_now(now)
        return self.system(
            lambda conn: conn.execute(
                "SELECT export.status_counts(%s) AS status", (now,)
            ).fetchone()["status"]
        )

    def record_lane_status(self, outcome: str) -> None:
        """The lane's last outcome category and its time; a category, never text."""
        require_text(outcome, "outcome", limit=64)
        self.system(
            lambda conn: conn.execute(
                "INSERT INTO export.lane_status(outcome) VALUES(%s) ON CONFLICT(singleton) "
                "DO UPDATE SET outcome=excluded.outcome,observed_at=clock_timestamp()",
                (outcome,),
            )
        )
