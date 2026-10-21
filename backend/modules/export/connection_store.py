"""Connection units of the export store: the owner's single connection (BR1.3).

A first configure reserves an internal `pending` row (revision 0) and its pace row, so
the token check is paced like any other call (R-13). Every later change to that row is
a compare-and-set on its holder (R-02); every change to a real connection is a
compare-and-set on its revision (BR1.3). Replace, disconnect and revocation end older
pending work in the same transaction (BR1.4); unavailability keeps the revision
(BR1.6). Reads never show the pending reservation: it reads as not connected.
"""

import datetime as dt
from dataclasses import dataclass
from uuid import UUID, uuid4

import psycopg

from .errors import ExportError
from .store_support import (
    CONNECTION_COLUMNS,
    Replay,
    invalid,
    invalidate_older_work,
    not_found,
    record_replay,
    replay_response,
    require_now,
    require_optional_text,
    require_optional_uuid,
    require_revision,
    require_text,
    require_uuid,
)

_ENVELOPE_LIMIT = 4096


@dataclass(frozen=True)
class ConnectionSlot:
    """The row a configure check acts on: a held reservation, or a real connection at
    the revision the owner expected."""

    connection_id: UUID
    expected_revision: int
    holder: UUID | None

    @property
    def pending(self) -> bool:
        return self.holder is not None

    @property
    def next_revision(self) -> int:
        """The revision the store will create; the vault binds the envelope to it."""
        return self.expected_revision + 1


@dataclass(frozen=True)
class SealedToken:
    """What a successful check stores: the envelope and the workspace facts."""

    envelope: bytes
    key_version: str
    workspace_name: str | None
    workspace_id: str | None
    connection_user_id: str | None
    validated_at: dt.datetime

    def __post_init__(self):
        if not isinstance(self.envelope, bytes) or not 1 <= len(self.envelope) <= _ENVELOPE_LIMIT:
            invalid("envelope")
        require_text(self.key_version, "keyVersion", limit=64)
        require_optional_text(self.workspace_name, "workspaceName", limit=8000)
        require_optional_text(self.workspace_id, "workspaceId", limit=128)
        require_optional_text(self.connection_user_id, "connectionUserId", limit=128)
        require_now(self.validated_at, "validatedAt")


def _owner_row(conn, account_id: UUID, *, lock: bool = False):
    return conn.execute(
        f"SELECT {CONNECTION_COLUMNS},pending_holder,pending_started_at "
        "FROM export.connection WHERE account_id=%s" + (" FOR UPDATE" if lock else ""),
        (account_id,),
    ).fetchone()


def _visible(row, connection_id: UUID | None):
    """A real connection, optionally only the one named; pending and absent read alike."""
    if row is None or row["state"] == "pending":
        return None
    if connection_id is not None and row["id"] != connection_id:
        return None
    return {key: value for key, value in row.items() if not key.startswith("pending_")}


class ConnectionUnits:
    """Owner units for the connection and the lane's revocation and availability units."""

    # -- owner reads ------------------------------------------------------------

    def read_connection(self, authority, connection_id: UUID | None = None) -> dict:
        """The owner's connection; absent, pending and foreign all raise LookupError."""
        require_optional_uuid(connection_id, "connectionId")

        def read(conn):
            row = _visible(_owner_row(conn, authority.account_id), connection_id)
            if row is None:
                not_found()
            return row

        return self.run(authority, read)

    def configure_replay(self, authority, replay: Replay) -> dict | None:
        """The configure record for this key, or None; another input is a conflict."""
        return self.run(
            authority, lambda conn: replay_response(conn, authority.account_id, "configure", replay)
        )

    def record_configure_refusal(self, authority, replay: Replay, code: str) -> None:
        """A replace whose token Notion refused keeps its replay record (the code only),
        so the same key answers the same refusal (security design §3)."""
        if not isinstance(replay, Replay):
            invalid("operationKey")
        require_text(code, "code", limit=64)
        self.run(
            authority,
            lambda conn: record_replay(
                conn, authority.account_id, "configure", replay, {"code": code}
            ),
        )

    def connection_state(self, account_id: UUID, connection_id: UUID) -> dict | None:
        """The revision and state of one owner's real connection, for the binding check
        (BR3.3); None when it is absent, pending or another owner's."""
        require_uuid(account_id, "accountId")
        require_uuid(connection_id, "connectionId")
        return self.system(
            lambda conn: conn.execute(
                "SELECT id,revision,state,workspace_id FROM export.connection "
                "WHERE id=%s AND account_id=%s AND state<>'pending'",
                (connection_id, account_id),
            ).fetchone()
        )

    # -- configure ---------------------------------------------------------------

    def reserve_connection(
        self, authority, expected_revision: int | None, *, now: dt.datetime
    ) -> ConnectionSlot:
        """Reserve a first configure, take over a stale reservation, or verify the
        expected revision of a real connection (BR1.3, R-01, R-02, R-03).

        CONFLICT while a fresh reservation exists, from `unavailable` (decision
        "Configure from unavailable"), or when the revision is not the expected one.
        """
        if expected_revision is not None:
            require_revision(expected_revision, "expectedRevision", minimum=0)
        require_now(now)
        takeover = dt.timedelta(seconds=self.policy.pending_takeover_seconds)

        def reserve(conn):
            row = _owner_row(conn, authority.account_id, lock=True)
            if row is None:
                if expected_revision:
                    raise ExportError("CONFLICT", current={"revision": None})
                return self._insert_reservation(conn, authority.account_id, now)
            if row["state"] == "pending":
                if expected_revision or row["pending_started_at"] > now - takeover:
                    raise ExportError("CONFLICT", current={"revision": None})
                return self._take_over(conn, row, now, takeover)
            if row["state"] == "unavailable" or row["revision"] != expected_revision:
                raise ExportError("CONFLICT", current={"revision": row["revision"]})
            return ConnectionSlot(row["id"], row["revision"], None)

        return self.run(authority, reserve)

    @staticmethod
    def _insert_reservation(conn, account_id: UUID, now: dt.datetime) -> ConnectionSlot:
        connection_id, holder = uuid4(), uuid4()
        try:
            with conn.transaction():
                conn.execute(
                    "INSERT INTO export.connection(id,account_id,revision,state,"
                    "pending_holder,pending_started_at) VALUES(%s,%s,0,'pending',%s,%s)",
                    (connection_id, account_id, holder, now),
                )
                conn.execute(
                    "INSERT INTO export.connection_pace(connection_id) VALUES(%s)",
                    (connection_id,),
                )
        except psycopg.errors.UniqueViolation:
            raise ExportError("CONFLICT", current={"revision": None}) from None
        return ConnectionSlot(connection_id, 0, holder)

    @staticmethod
    def _take_over(conn, row, now: dt.datetime, takeover: dt.timedelta) -> ConnectionSlot:
        holder = uuid4()
        taken = conn.execute(
            "UPDATE export.connection SET pending_holder=%s,pending_started_at=%s,"
            "updated_at=clock_timestamp() WHERE account_id=%s AND state='pending' "
            "AND pending_holder=%s AND pending_started_at<=%s RETURNING id",
            (holder, now, row["account_id"], row["pending_holder"], now - takeover),
        ).fetchone()
        if taken is None:
            raise ExportError("CONFLICT", current={"revision": None})
        return ConnectionSlot(taken["id"], 0, holder)

    def store_configured(
        self,
        authority,
        slot: ConnectionSlot,
        sealed: SealedToken,
        replay: Replay,
        *,
        now: dt.datetime,
    ) -> dict:
        """Store the checked token by compare-and-set; in the same transaction end older
        pending work and write the configure replay record.

        CONFLICT, with nothing written, when the reservation was taken over or removed,
        or the revision moved on (R-02). A replay of the same key returns its record.
        """
        if not isinstance(slot, ConnectionSlot) or not isinstance(sealed, SealedToken):
            invalid("connection")
        if not isinstance(replay, Replay):
            invalid("operationKey")
        require_now(now)

        def store(conn):
            recorded = replay_response(conn, authority.account_id, "configure", replay)
            if recorded is not None:
                return {"replayed": True, "response": recorded}
            revision = conn.execute(
                "SELECT export.store_token_envelope(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) AS revision",
                (
                    authority.account_id,
                    slot.connection_id,
                    slot.expected_revision,
                    slot.holder,
                    sealed.envelope,
                    sealed.key_version,
                    sealed.workspace_name,
                    sealed.workspace_id,
                    sealed.connection_user_id,
                    sealed.validated_at,
                ),
            ).fetchone()["revision"]
            if revision is None:
                raise ExportError("CONFLICT")
            ended = invalidate_older_work(
                conn, authority.account_id, slot.connection_id, revision, now
            )
            response = {
                "connectionId": str(slot.connection_id),
                "state": "connected",
                "revision": revision,
            }
            record_replay(conn, authority.account_id, "configure", replay, response)
            return {"replayed": False, "response": response, **ended}

        return self.run(authority, store)

    def release_pending(
        self, authority, holder: UUID, *, refusal: tuple[Replay, str] | None = None
    ) -> bool:
        """A check that ended any other way removes only the row it still holds; the pace
        row goes with it. False when the row moved on. A definite refusal can keep its
        replay record (the code only) in the same transaction."""
        require_uuid(holder, "holder")

        def release(conn):
            released = conn.execute(
                "SELECT export.release_pending(%s,%s) AS released",
                (authority.account_id, holder),
            ).fetchone()["released"]
            if refusal is not None:
                replay, code = refusal
                record_replay(conn, authority.account_id, "configure", replay, {"code": code})
            return released

        return self.run(authority, release)

    # -- disconnect --------------------------------------------------------------

    def disconnect(self, authority, connection_id: UUID | None = None, *, now: dt.datetime) -> dict:
        """Clear the envelope, advance the revision and end older pending work (BR1.4).
        A repeat returns the disconnected connection unchanged."""
        require_optional_uuid(connection_id, "connectionId")
        require_now(now)

        def disconnect(conn):
            row = _visible(_owner_row(conn, authority.account_id, lock=True), connection_id)
            if row is None:
                not_found()
            if row["state"] in ("disconnected", "revoked"):
                return {"connection": row, "approvalsInvalidated": [], "effectsInvalidated": []}
            revision = conn.execute(
                "SELECT export.clear_token_envelope(%s,%s,%s,'disconnected') AS revision",
                (authority.account_id, row["id"], row["revision"]),
            ).fetchone()["revision"]
            if revision is None:
                raise ExportError("CONFLICT", current={"revision": row["revision"]})
            ended = invalidate_older_work(conn, authority.account_id, row["id"], revision, now)
            current = _visible(_owner_row(conn, authority.account_id), None)
            return {"connection": current, **ended}

        return self.run(authority, disconnect)

    # -- lane units: revocation and availability ----------------------------------

    def revoke_connection(
        self, account_id: UUID, connection_id: UUID, opened_revision: int, *, now: dt.datetime
    ) -> dict | None:
        """D16: Notion refused a stored token. Revoke by compare-and-set on the revision
        the operation opened; only then end older pending work (BR1.4). None when the
        revision moved on: the revocation is discarded and nothing changes."""
        require_uuid(account_id, "accountId")
        require_uuid(connection_id, "connectionId")
        require_revision(opened_revision, "connectionRevision")
        require_now(now)

        def revoke(conn):
            revision = conn.execute(
                "SELECT export.clear_token_envelope(%s,%s,%s,'revoked') AS revision",
                (account_id, connection_id, opened_revision),
            ).fetchone()["revision"]
            if revision is None:
                return None
            return {
                "revision": revision,
                **invalidate_older_work(conn, account_id, connection_id, revision, now),
            }

        return self.system(revoke)

    def set_availability(
        self, account_id: UUID, connection_id: UUID, opened_revision: int, *, available: bool
    ) -> bool:
        """BR1.6: a token that cannot be opened makes the connection unavailable, and one
        that opens again makes it connected; the revision stays and nothing is
        invalidated. False when the connection moved on."""
        require_uuid(account_id, "accountId")
        require_uuid(connection_id, "connectionId")
        require_revision(opened_revision, "connectionRevision")
        before, after = ("unavailable", "connected") if available else ("connected", "unavailable")
        return self.system(
            lambda conn: (
                conn.execute(
                    "UPDATE export.connection SET state=%s,updated_at=clock_timestamp() "
                    "WHERE id=%s AND account_id=%s AND revision=%s AND state=%s",
                    (after, connection_id, account_id, opened_revision, before),
                ).rowcount
                == 1
            )
        )

    def open_token_envelope(self, account_id: UUID, connection_id: UUID):
        """The envelope, revision, key version and state of a connected or unavailable
        connection, through the owner-rights function only (D13); None otherwise."""
        require_uuid(account_id, "accountId")
        require_uuid(connection_id, "connectionId")

        def read(conn):
            row = conn.execute(
                "SELECT sealed_token,revision,token_key_version,state "
                "FROM export.open_token_envelope(%s,%s)",
                (account_id, connection_id),
            ).fetchone()
            if row is None:
                return None
            return {**row, "sealed_token": bytes(row["sealed_token"])}

        return self.system(read)

    def token_key_counts(self) -> list[dict]:
        """Sealed tokens per key version, with no identifiers (the D3 witness)."""
        return self.system(
            lambda conn: conn.execute(
                "SELECT token_key_version,sealed_tokens FROM export.token_key_counts()"
            ).fetchall()
        )
