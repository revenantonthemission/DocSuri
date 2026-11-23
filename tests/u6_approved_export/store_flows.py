"""Repository-level flows for the store tests: the real `ExportRepository` over the realm.

The realm persists across phases and owns at most twenty synthetic accounts, so every
owner test first erases the conftest owner's export rows through a real erase ticket
(the same path `export.erase_account_records` serves for AccountAccess). Envelopes are
synthetic `DSE1` bytes; no token or Notion call exists anywhere here. The clock is
injected: every unit receives the test's `now`.
"""

import datetime as dt
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from uuid import UUID, uuid4

import psycopg

from backend.modules.export.repository import (
    ExportRepository,
    PreviewFacts,
    RenderedRevision,
    Replay,
    SealedToken,
    WriteOutcome,
)
from backend.modules.export.store_support import canonical_digest, replay_input_hash
from backend.transactions import Authority
from backend.u6_policy import ExportPolicy
from tests.u6_approved_export import export_rows as rows

RENDER_POLICY = {"policyId": "u6-synthetic-export", "revision": "1"}
APPROVAL_POLICY = {"policyId": "u6-approval-validity", "revision": "1"}


def at(seconds: float = 0, *, base: dt.datetime | None = None) -> dt.datetime:
    """A point on the injected clock, `seconds` after the base (now by default)."""
    return (base or dt.datetime.now(dt.UTC)) + dt.timedelta(seconds=seconds)


def repository(transactions, **policy) -> ExportRepository:
    return ExportRepository(transactions, ExportPolicy(**policy))


def fresh(connect, account: UUID) -> None:
    """Erase the account's export rows left by earlier runs, through a real erase ticket."""
    ticket = rows.lifecycle_ticket(connect, account, "erase")
    with connect("export") as conn:
        conn.execute("SELECT export.erase_account_records(%s,%s,%s,%s,%s)", ticket)
        conn.commit()


def second_session(connect, authority: Authority) -> Authority:
    """Another current session of the same owner, so a test can end it on its own."""
    session = uuid4()
    with connect("accounts") as conn:
        revision = conn.execute(
            "SELECT authority_revision FROM accounts.account WHERE id=%s", (authority.account_id,)
        ).fetchone()["authority_revision"]
        conn.execute(
            "INSERT INTO accounts.session(id,account_id,token_hash,csrf_hash,authority_revision,"
            "expires_at) VALUES(%s,%s,%s,%s,%s,clock_timestamp()+interval '30 minutes')",
            (session, authority.account_id, str(uuid4()), str(uuid4()), revision),
        )
    return Authority(authority.account_id, session)


def end_session(connect, authority: Authority) -> None:
    with connect("accounts") as conn:
        conn.execute(
            "UPDATE accounts.session SET revoked=true WHERE id=%s", (authority.session_id,)
        )


@contextmanager
def held_session(connect, authority: Authority) -> Iterator[None]:
    """Hold the session row `FOR UPDATE` from a second connection while the block runs.

    The real guard `accounts.guard_session` locks the same row `FOR SHARE`, so its own
    statement waits until the realm's lock bound (`lock_timeout=1000`, 1 s) ends it with
    55P03 (`LockNotAvailable`), which is not the guard's 42501 answer: the could-not-check
    path is reached through a real failure, never a replaced unit. The holder rolls back
    before it closes, so the row is free before the test's next check.
    """
    holder = connect("accounts")
    try:
        held = holder.execute(
            "SELECT id FROM accounts.session WHERE id=%s AND account_id=%s FOR UPDATE",
            (authority.session_id, authority.account_id),
        ).fetchone()
        assert held is not None, "the held session must exist"
        yield
        holder.execute("SELECT 1")  # the holder was alive for the whole block
    finally:
        with suppress(psycopg.Error):
            holder.rollback()
        holder.close()


PACE_ROW = "SELECT next_slot_at FROM export.connection_pace WHERE connection_id=%s FOR UPDATE"
EFFECT_ROW = "SELECT id FROM export.effect WHERE id=%s FOR UPDATE"
LANE_STATUS_ROW = "SELECT outcome FROM export.lane_status WHERE singleton FOR UPDATE"


@contextmanager
def held_rows(connect_raw, *locks: tuple[str, tuple]) -> Iterator[None]:
    """Hold the named rows `FOR UPDATE` from one administrative session while the block runs.

    A locking or updating statement of the code under test then waits until the realm's
    lock bound (`lock_timeout=1000`, 1 s) ends it with 55P03 (`LockNotAvailable`), a real
    fault, never a replaced unit. Plain reads are not blocked. Each hold must stay under
    the realm's 5 s idle-in-transaction bound (`idle_in_transaction_session_timeout=5000`).
    """
    holder = connect_raw()
    try:
        for sql, params in locks:
            assert sql.lstrip().startswith("SELECT") and sql.rstrip().endswith("FOR UPDATE")
            assert holder.execute(sql, params).fetchone() is not None, "the held row must exist"
        yield
        holder.execute("SELECT 1")  # the holder was alive for the whole block
    finally:
        with suppress(psycopg.Error):
            holder.rollback()
        holder.close()


def expire_session(connect, authority: Authority) -> None:
    """Reach the expiry branch of the session guard on its own."""
    with connect("accounts") as conn:
        conn.execute(
            "UPDATE accounts.session SET expires_at=clock_timestamp()-interval '1 minute' "
            "WHERE id=%s",
            (authority.session_id,),
        )


def set_consent(connect, account: UUID, purpose: str, granted: bool) -> None:
    """Upsert one consent grant, so a test can reach the guard's consent branch."""
    with connect("accounts") as conn:
        conn.execute(
            "INSERT INTO accounts.consent(account_id,purpose,granted) VALUES(%s,%s,%s) "
            "ON CONFLICT(account_id,purpose) DO UPDATE SET granted=excluded.granted",
            (account, purpose, granted),
        )


def sealed(*, validated_at: dt.datetime | None = None, user: str = "synthetic-bot") -> SealedToken:
    version = rows.key_version()
    return SealedToken(
        envelope=rows.envelope(version),
        key_version=version,
        workspace_name="Synthetic Workspace",
        workspace_id="synthetic-workspace",
        connection_user_id=user,
        validated_at=validated_at or at(),
    )


def configure_request(expected_revision, token="synthetic-token") -> dict:
    return {
        "expectedRevision": expected_revision,
        "credentialPolicy": RENDER_POLICY,
        "token": token,
    }


def replay_for(request: dict, key: UUID | None = None) -> Replay:
    return Replay(key or uuid4(), replay_input_hash(request))


def configure(repo, authority, now, *, expected=None, user="synthetic-bot") -> dict:
    """Reserve (or verify), then store a sealed token; returns the store result."""
    slot = repo.reserve_connection(authority, expected, now=now)
    request = configure_request(expected)
    return repo.store_configured(
        authority, slot, sealed(validated_at=now, user=user), replay_for(request), now=now
    )


def connected(repo, connect, authority, now) -> dict:
    """A fresh owner with a connected connection; returns the connection read."""
    fresh(connect, authority.account_id)
    configure(repo, authority, now)
    return repo.read_connection(authority)


def facts(connection: dict, *, artifact: UUID | None = None, destination: str | None = None):
    destination = destination or rows.destination_id()
    artifact = artifact or uuid4()
    return PreviewFacts(
        artifact_id=artifact,
        destination_id=destination,
        source_revision="1",
        source_content_hash=canonical_digest({"source": str(artifact)}),
        source_eligibility_revision="1",
        source_title="Synthetic result",
        connection_id=connection["id"],
        connection_revision=connection["revision"],
        destination={
            "destinationId": destination,
            "connectionId": str(connection["id"]),
            "title": "Synthetic page",
        },
        render_policy=RENDER_POLICY,
    )


def render(preview_id: UUID, revision: int) -> RenderedRevision:
    """A stand-in for the render policy: marker last, hashes over the tree."""
    marker = f"docsuri-export:v1:{preview_id.hex}:{revision}"
    tree = {
        "properties": {"title": "Synthetic"},
        "children": [{"text": "body"}, {"marker": marker}],
    }
    content = canonical_digest(tree)
    return RenderedRevision(
        marker=marker,
        rendered_blocks=tree,
        rendered_text="Synthetic\nbody\n" + marker,
        rendered_content_hash=content,
        binding_hash=canonical_digest({"preview": str(preview_id), "revision": revision}),
    )


def prepare(repo, authority, connection, now, **pair) -> dict:
    return repo.add_preview_revision(authority, facts(connection, **pair), render, now=now)


def approve(repo, authority, preview, now, *, key: UUID | None = None) -> dict:
    return repo.record_approval(
        authority,
        key or uuid4(),
        preview["preview_id"],
        preview["revision"],
        preview["binding_hash"],
        APPROVAL_POLICY,
        now=now,
    )["approval"]


def bound(repo, authority, connection, now, **pair) -> dict:
    """A preview revision, its approval and its accepted effect."""
    preview = prepare(repo, authority, connection, now, **pair)
    approval = approve(repo, authority, preview, now)
    effect = repo.bind_effect(authority, approval["id"], uuid4(), now=now)["effect"]
    return {"preview": preview, "approval": approval, "effect": effect}


def succeed(repo, effect: dict, now) -> dict:
    """Claim the accepted effect and record a created page; returns the succeeded effect."""
    claimed = repo.claim(effect["id"], effect["revision"], now=now)
    reference = uuid4().hex
    return repo.record_write_outcome(
        effect["id"],
        claimed.attempt["id"],
        claimed.effect["revision"],
        WriteOutcome(
            "created",
            provider_request_id="synthetic-request",
            creator_confirmed=True,
            remote_reference=reference,
            remote_url=f"https://www.notion.so/{reference}",
        ),
        now=now,
    )


def uncertain(repo, effect: dict, now) -> dict:
    """Claim the accepted effect and record an uncertain answer; returns it unknown."""
    claimed = repo.claim(effect["id"], effect["revision"], now=now)
    return repo.record_write_outcome(
        effect["id"],
        claimed.attempt["id"],
        claimed.effect["revision"],
        WriteOutcome("uncertain"),
        now=now,
    )


def effect_row(connect, effect_id: UUID) -> dict:
    with connect("export") as conn:
        return conn.execute(
            "SELECT id,state,revision,outcome_reason,ended_at,settled_by,next_check_at,"
            "scanning_stopped_at,waiting_since,remote_url FROM export.effect WHERE id=%s",
            (effect_id,),
        ).fetchone()


def approval_row(connect, approval_id: UUID) -> dict:
    with connect("export") as conn:
        return conn.execute(
            "SELECT id,state,invalidation_reason FROM export.approval WHERE id=%s", (approval_id,)
        ).fetchone()


def revision_row(connect, preview_id: UUID, revision: int) -> dict:
    with connect("export") as conn:
        return conn.execute(
            "SELECT preview_id,revision,rendered_blocks,rendered_text,trimmed_at,earlier_exports "
            "FROM export.preview_revision WHERE preview_id=%s AND revision=%s",
            (preview_id, revision),
        ).fetchone()


def connection_row(connect, connection_id: UUID) -> dict:
    with connect("export") as conn:
        return conn.execute(
            "SELECT id,account_id,revision,state,pending_holder,pending_started_at,"
            "creation_capability,last_destination_id FROM export.connection WHERE id=%s",
            (connection_id,),
        ).fetchone()


def pace_count(connect, connection_id: UUID) -> int:
    with connect("export") as conn:
        return conn.execute(
            "SELECT count(*) AS n FROM export.connection_pace WHERE connection_id=%s",
            (connection_id,),
        ).fetchone()["n"]
