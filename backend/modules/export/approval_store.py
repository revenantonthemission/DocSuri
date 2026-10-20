"""Approval and effect owner units of the export store (BR3.1–BR3.7, BR5.1, BR5.2).

Approve and execute keep their idempotency key on the approval and effect rows; a
replay (by key, or by the preview revision or approval it already produced) returns
the original before any other check (BR3.2). The bind is one guarded statement that
also consumes the approval, and every bind refusal leaves the approval approved. Cancel
and settle are compare-and-sets; settle keeps its own replay record (security design
§3).
"""

import datetime as dt
from uuid import UUID, uuid4

import psycopg
from psycopg.types.json import Jsonb

from .errors import ExportError
from .preview_store import owned_revision
from .store_support import (
    APPROVAL_COLUMNS,
    EFFECT_COLUMNS,
    INVALIDATION_REASONS,
    Replay,
    apply_connection_facts,
    effect_connection,
    invalid,
    is_hex64,
    newer_success,
    not_found,
    record_replay,
    replay_response,
    require_now,
    require_revision,
    require_text,
    require_uuid,
    seconds_until,
    settlement_offered,
)

SETTLE_DISPOSITIONS = {
    "delivered": ("succeeded", "owner-settled-delivered"),
    "not-delivered": ("failed", "owner-settled-not-delivered"),
}


def _effect_of(conn, account_id: UUID, approval_id: UUID):
    return conn.execute(
        f"SELECT {EFFECT_COLUMNS} FROM export.effect WHERE approval_id=%s AND account_id=%s",
        (approval_id, account_id),
    ).fetchone()


def _approval(conn, account_id: UUID, approval_id: UUID, *, lock: bool = False):
    row = conn.execute(
        f"SELECT {APPROVAL_COLUMNS} FROM export.approval WHERE id=%s AND account_id=%s"
        + (" FOR UPDATE" if lock else ""),
        (approval_id, account_id),
    ).fetchone()
    if row is None:
        not_found()
    return row


def _owned_effect(conn, account_id: UUID, effect_id: UUID, *, lock: bool = False):
    row = conn.execute(
        f"SELECT {EFFECT_COLUMNS} FROM export.effect WHERE id=%s AND account_id=%s"
        + (" FOR UPDATE" if lock else ""),
        (effect_id, account_id),
    ).fetchone()
    if row is None:
        not_found()
    return row


def _approval_replay(conn, account_id, request_key, preview_id, preview_revision, binding_hash):
    """By key first (another payload is IDEMPOTENCY_CONFLICT), then by preview revision."""
    row = conn.execute(
        f"SELECT {APPROVAL_COLUMNS} FROM export.approval WHERE account_id=%s AND request_key=%s",
        (account_id, request_key),
    ).fetchone()
    if row is not None and (
        row["preview_id"],
        row["preview_revision"],
        row["binding_hash"],
    ) != (preview_id, preview_revision, binding_hash):
        raise ExportError("IDEMPOTENCY_CONFLICT")
    if row is None:
        row = conn.execute(
            f"SELECT {APPROVAL_COLUMNS} FROM export.approval WHERE account_id=%s "
            "AND preview_id=%s AND preview_revision=%s",
            (account_id, preview_id, preview_revision),
        ).fetchone()
    if row is None:
        return None
    return {"approval": row, "effect": _effect_of(conn, account_id, row["id"]), "replayed": True}


def _execute_replay(conn, account_id, request_key, approval_id):
    """By key first (the same key on another approval is CONFLICT), then by approval."""
    effect = conn.execute(
        f"SELECT {EFFECT_COLUMNS} FROM export.effect WHERE account_id=%s AND request_key=%s",
        (account_id, request_key),
    ).fetchone()
    if effect is not None and effect["approval_id"] != approval_id:
        raise ExportError("CONFLICT")
    effect = effect or _effect_of(conn, account_id, approval_id)
    if effect is None:
        return None
    approval = _approval(conn, account_id, effect["approval_id"])
    return {"approval": approval, "effect": effect, "replayed": True}


def _check_validity(approval_args):
    request_key, preview_id, preview_revision, binding_hash = approval_args
    require_uuid(request_key, "requestKey")
    require_uuid(preview_id, "previewId")
    require_revision(preview_revision, "previewRevision")
    if not is_hex64(binding_hash):
        invalid("bindingHash")


class ApprovalUnits:
    # -- approve -----------------------------------------------------------------

    def approval_replay(self, authority, request_key, preview_id, preview_revision, binding_hash):
        """The approval this key or preview revision already produced, or None."""
        _check_validity((request_key, preview_id, preview_revision, binding_hash))
        return self.run(
            authority,
            lambda conn: _approval_replay(
                conn, authority.account_id, request_key, preview_id, preview_revision, binding_hash
            ),
        )

    def record_approval(
        self,
        authority,
        request_key: UUID,
        preview_id: UUID,
        preview_revision: int,
        binding_hash: str,
        policy: dict,
        *,
        now: dt.datetime,
    ) -> dict:
        """Record the approval of the pair's current, untrimmed revision (BR3.1, BR3.2).

        CONFLICT for any other revision, a different binding hash, or an export of the
        pair that succeeded after the revision was prepared; a refusal records nothing.
        """
        _check_validity((request_key, preview_id, preview_revision, binding_hash))
        if not isinstance(policy, dict) or not policy:
            invalid("policy")
        require_now(now)

        def approve(conn):
            args = (authority.account_id, request_key, preview_id, preview_revision, binding_hash)
            replayed = _approval_replay(conn, *args)
            if replayed is not None:
                return replayed
            revision = owned_revision(conn, authority.account_id, preview_id, preview_revision)
            conn.execute(
                "SELECT 1 FROM export.preview_pair WHERE preview_id=%s FOR UPDATE", (preview_id,)
            )
            if (
                revision["current_revision"] != preview_revision
                or revision["binding_hash"] != binding_hash
                or revision["trimmed_at"] is not None
            ):
                raise ExportError("CONFLICT", current={"revision": revision["current_revision"]})
            if newer_success(
                conn,
                authority.account_id,
                revision["artifact_id"],
                revision["destination_id"],
                revision["prepared_at"],
            ):
                raise ExportError("CONFLICT", current={"field": "newerExport"})
            try:
                with conn.transaction():
                    approval = conn.execute(
                        "INSERT INTO export.approval(id,account_id,preview_id,preview_revision,"
                        "binding_hash,policy,approved_at,approving_session,request_key) "
                        f"VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING {APPROVAL_COLUMNS}",
                        (
                            uuid4(),
                            authority.account_id,
                            preview_id,
                            preview_revision,
                            binding_hash,
                            Jsonb(policy),
                            now,
                            authority.session_id,
                            request_key,
                        ),
                    ).fetchone()
            except psycopg.errors.UniqueViolation:
                replayed = _approval_replay(conn, *args)
                if replayed is None:
                    raise ExportError("CONFLICT") from None
                return replayed
            return {"approval": approval, "effect": None, "replayed": False}

        return self.run(authority, approve)

    def read_approval(self, authority, approval_id: UUID) -> dict:
        """The approval with its preview revision facts and its effect, if bound."""
        require_uuid(approval_id, "approvalId")

        def read(conn):
            approval = _approval(conn, authority.account_id, approval_id)
            revision = owned_revision(
                conn, authority.account_id, approval["preview_id"], approval["preview_revision"]
            )
            effect = _effect_of(conn, authority.account_id, approval_id)
            return {"approval": approval, "revision": revision, "effect": effect}

        return self.run(authority, read)

    def invalidate_approval(
        self, authority, approval_id: UUID, reason: str, *, now: dt.datetime
    ) -> dict:
        """A continue found a stale session or a changed binding (BR3.7): an approved,
        unconsumed approval becomes invalidated with the reason. Returns the approval as
        it now stands, so a moved-on approval comes back unchanged."""
        require_uuid(approval_id, "approvalId")
        if reason not in INVALIDATION_REASONS:
            invalid("invalidationReason")
        require_now(now)

        def invalidate(conn):
            _approval(conn, authority.account_id, approval_id, lock=True)
            conn.execute(
                "UPDATE export.approval SET state='invalidated',invalidation_reason=%s "
                "WHERE id=%s AND account_id=%s AND state='approved'",
                (reason, approval_id, authority.account_id),
            )
            return _approval(conn, authority.account_id, approval_id)

        return self.run(authority, invalidate)

    # -- execute -----------------------------------------------------------------

    def execute_replay(self, authority, request_key: UUID, approval_id: UUID):
        """The effect this key or approval already produced, or None."""
        require_uuid(request_key, "requestKey")
        require_uuid(approval_id, "approvalId")
        return self.run(
            authority,
            lambda conn: _execute_replay(conn, authority.account_id, request_key, approval_id),
        )

    def bind_effect(
        self, authority, approval_id: UUID, request_key: UUID, *, now: dt.datetime
    ) -> dict:
        """Bind the approval's one effect in `accepted`, consuming the approval in the same
        statement (BR3.2). Refusals leave the approval approved:

        - CAPACITY_EXHAUSTED while another export is in flight (BR5.1);
        - OUTCOME_UNKNOWN while an unknown export of the pair exists (BR5.1);
        - CAPACITY_EXHAUSTED with `retry_after` past the rolling-hour limit (BR5.2);
        - CONFLICT when an export of the pair succeeded after the revision was prepared.
        """
        require_uuid(approval_id, "approvalId")
        require_uuid(request_key, "requestKey")
        require_now(now)

        def bind(conn):
            replayed = _execute_replay(conn, authority.account_id, request_key, approval_id)
            if replayed is not None:
                return replayed
            approval = _approval(conn, authority.account_id, approval_id, lock=True)
            if approval["state"] != "approved":
                raise ExportError("APPROVAL_REQUIRED")
            revision = owned_revision(
                conn, authority.account_id, approval["preview_id"], approval["preview_revision"]
            )
            self._refuse_bind(conn, authority.account_id, revision, now)
            effect = self._insert_effect(conn, authority.account_id, approval_id, request_key, now)
            if effect is None:
                raise ExportError("APPROVAL_REQUIRED")
            approval = _approval(conn, authority.account_id, approval_id)
            return {"approval": approval, "effect": effect, "replayed": False}

        return self.run(authority, bind)

    def _refuse_bind(self, conn, account_id: UUID, revision, now: dt.datetime) -> None:
        busy = conn.execute(
            "SELECT 1 FROM export.effect WHERE account_id=%s AND state IN ('accepted','executing')",
            (account_id,),
        ).fetchone()
        if busy is not None:
            raise ExportError("CAPACITY_EXHAUSTED")
        pair = (account_id, revision["artifact_id"], revision["destination_id"])
        unknown = conn.execute(
            "SELECT 1 FROM export.effect WHERE account_id=%s AND artifact_id=%s "
            "AND destination_id=%s AND state='unknown' LIMIT 1",
            pair,
        ).fetchone()
        if unknown is not None:
            raise ExportError("OUTCOME_UNKNOWN")
        if newer_success(conn, *pair, revision["prepared_at"]):
            raise ExportError("CONFLICT", current={"field": "newerExport"})
        window = dt.timedelta(seconds=self.policy.binds_window_seconds)
        recent = conn.execute(
            "SELECT count(*) AS n,min(accepted_at) AS oldest FROM export.effect "
            "WHERE account_id=%s AND accepted_at>%s",
            (account_id, now - window),
        ).fetchone()
        if recent["n"] >= self.policy.binds_per_window:
            raise ExportError(
                "CAPACITY_EXHAUSTED", retry_after=seconds_until(recent["oldest"] + window, now)
            )

    @staticmethod
    def _insert_effect(conn, account_id, approval_id, request_key, now):
        try:
            with conn.transaction():
                return conn.execute(
                    "WITH consumed AS (UPDATE export.approval SET state='consumed' "
                    "WHERE id=%s AND account_id=%s AND state='approved' "
                    "RETURNING id,account_id,preview_id,preview_revision,binding_hash) "
                    "INSERT INTO export.effect(id,approval_id,account_id,artifact_id,"
                    "destination_id,binding_hash,marker,request_key,accepted_at) "
                    "SELECT %s,c.id,c.account_id,p.artifact_id,p.destination_id,c.binding_hash,"
                    "r.marker,%s,%s FROM consumed c "
                    "JOIN export.preview_revision r "
                    "ON r.preview_id=c.preview_id AND r.revision=c.preview_revision "
                    "JOIN export.preview_pair p ON p.preview_id=c.preview_id "
                    f"RETURNING {EFFECT_COLUMNS}",
                    (approval_id, account_id, uuid4(), request_key, now),
                ).fetchone()
        except psycopg.errors.UniqueViolation as exc:
            in_flight = exc.diag.constraint_name == "effect_in_flight"
        raise ExportError("CAPACITY_EXHAUSTED" if in_flight else "CONFLICT") from None

    # -- cancel and settle ----------------------------------------------------------

    def cancel(
        self, authority, approval_id: UUID, expected_revision: int, *, now: dt.datetime
    ) -> dict:
        """BR3.6, A10: an unconsumed approval is cancelled by its preview revision; an
        accepted effect by its effect revision, and its approval stays consumed. An
        executing effect is CONFLICT and an unknown one OUTCOME_UNKNOWN. Repeating a
        completed cancel returns it."""
        require_uuid(approval_id, "approvalId")
        require_revision(expected_revision, "expectedRevision")
        require_now(now)

        def cancel(conn):
            approval = _approval(conn, authority.account_id, approval_id, lock=True)
            if approval["state"] in ("approved", "cancelled"):
                return self._cancel_approval(conn, approval, expected_revision)
            effect = _effect_of(conn, authority.account_id, approval_id)
            if approval["state"] != "consumed" or effect is None:
                raise ExportError("CONFLICT")
            return self._cancel_effect(conn, approval, effect, expected_revision, now)

        return self.run(authority, cancel)

    @staticmethod
    def _cancel_approval(conn, approval, expected_revision: int) -> dict:
        if approval["preview_revision"] != expected_revision:
            raise ExportError("CONFLICT", current={"revision": approval["preview_revision"]})
        if approval["state"] == "approved":
            conn.execute(
                "UPDATE export.approval SET state='cancelled' WHERE id=%s AND state='approved'",
                (approval["id"],),
            )
        current = _approval(conn, approval["account_id"], approval["id"])
        return {"approval": current, "effect": None}

    @staticmethod
    def _cancel_effect(conn, approval, effect, expected_revision: int, now) -> dict:
        state = effect["state"]
        if state == "executing":
            raise ExportError("CONFLICT", current={"state": state})
        if state == "unknown":
            raise ExportError("OUTCOME_UNKNOWN")
        if state not in ("accepted", "cancelled"):
            raise ExportError("CONFLICT", current={"state": state})
        if state == "accepted":
            if effect["revision"] != expected_revision:
                raise ExportError("CONFLICT", current={"revision": effect["revision"]})
            effect = conn.execute(
                "UPDATE export.effect SET state='cancelled',revision=revision+1,"
                "outcome_reason='owner-cancelled',ended_at=%s,updated_at=clock_timestamp() "
                f"WHERE id=%s AND revision=%s AND state='accepted' RETURNING {EFFECT_COLUMNS}",
                (now, effect["id"], expected_revision),
            ).fetchone()
        return {"approval": approval, "effect": effect}

    def settle(
        self,
        authority,
        effect_id: UUID,
        expected_revision: int,
        disposition: str,
        replay: Replay,
        *,
        assumption: str,
        remote_url: str | None = None,
        now: dt.datetime,
    ) -> dict:
        """BR4.5: the owner settles an unknown export by compare-and-set on its revision,
        only while settlement is offered, with its replay record. Delivered also names
        the bound destination as the connection's last destination."""
        require_uuid(effect_id, "effectId")
        require_revision(expected_revision, "expectedRevision")
        if disposition not in SETTLE_DISPOSITIONS:
            invalid("disposition")
        if not isinstance(replay, Replay):
            invalid("operationKey")
        require_text(assumption, "assumption")
        if remote_url is not None and (
            disposition != "delivered" or not 1 <= len(remote_url) <= 2048
        ):
            invalid("remoteUrl")
        require_now(now)

        def settle(conn):
            recorded = replay_response(conn, authority.account_id, "settle", replay)
            if recorded is not None:
                effect = _owned_effect(conn, authority.account_id, effect_id)
                return {"effect": effect, "replayed": True, "response": recorded}
            effect = _owned_effect(conn, authority.account_id, effect_id, lock=True)
            if effect["state"] != "unknown" or effect["revision"] != expected_revision:
                raise ExportError(
                    "CONFLICT", current={"revision": effect["revision"], "state": effect["state"]}
                )
            if not settlement_offered(conn, effect, now, self.policy):
                raise ExportError("CONFLICT", current={"field": "settlementOffered"})
            state, reason = SETTLE_DISPOSITIONS[disposition]
            settled = conn.execute(
                "UPDATE export.effect SET state=%s,revision=revision+1,outcome_reason=%s,"
                "settled_by='owner',owner_assumption=%s,remote_url=%s,ended_at=%s,"
                "updated_at=clock_timestamp() WHERE id=%s AND revision=%s AND state='unknown' "
                f"RETURNING {EFFECT_COLUMNS}",
                (state, reason, assumption, remote_url, now, effect_id, expected_revision),
            ).fetchone()
            if disposition == "delivered":
                bound = effect_connection(conn, effect_id)
                apply_connection_facts(
                    conn,
                    bound["connection_id"],
                    bound["destination_id"],
                    attempt_revision=None,
                    capability=None,
                )
            response = {
                "effectId": str(effect_id),
                "state": settled["state"],
                "revision": settled["revision"],
            }
            record_replay(conn, authority.account_id, "settle", replay, response)
            return {"effect": settled, "replayed": False, "response": response}

        return self.run(authority, settle)
