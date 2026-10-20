"""Synthetic export rows written as the runtime role, for the store-level tests.

Every row goes through `docsuri_export`'s own grants and the schema's triggers, never an
owner bypass. Envelopes are synthetic bytes in the `DSE1` layout: the store checks their
shape and version field, never their cryptography. No real token exists anywhere here.
"""

import hashlib
import secrets
from uuid import uuid4

from psycopg.types.json import Jsonb

ENVELOPE_TAG = b"DSE1"
NONCE_BYTES = 12
SYNTHETIC_CIPHERTEXT_BYTES = 48
RENDER_POLICY = {"policyId": "u6-synthetic-export", "revision": "1"}
APPROVAL_POLICY = {"policyId": "u6-approval-validity", "revision": "1"}


def key_version() -> str:
    return "u6-" + secrets.token_hex(16)


def envelope(version: str) -> bytes:
    """`DSE1` | len(version) | version | nonce | ciphertext-with-tag (synthetic bytes)."""
    encoded = version.encode("ascii")
    return (
        ENVELOPE_TAG
        + bytes([len(encoded)])
        + encoded
        + secrets.token_bytes(NONCE_BYTES)
        + secrets.token_bytes(SYNTHETIC_CIPHERTEXT_BYTES)
    )


def hex_digest(*parts: object) -> str:
    return hashlib.sha256(":".join(str(part) for part in parts).encode()).hexdigest()


def destination_id() -> str:
    return secrets.token_hex(16)


def reserve(conn, account=None, *, holder=None, started_at="clock_timestamp()"):
    """A first-configure reservation and its pace row; returns (connection, account, holder)."""
    connection, account, holder = uuid4(), account or uuid4(), holder or uuid4()
    conn.execute(
        "INSERT INTO export.connection(id,account_id,revision,state,pending_holder,"
        f"pending_started_at) VALUES(%s,%s,0,'pending',%s,{started_at})",
        (connection, account, holder),
    )
    conn.execute("INSERT INTO export.connection_pace(connection_id) VALUES(%s)", (connection,))
    return connection, account, holder


def store(conn, account, connection, expected, *, holder=None, version=None):
    """Calls the store function; returns the new revision or None."""
    version = version or key_version()
    return conn.execute(
        "SELECT export.store_token_envelope(%s,%s,%s,%s,%s,%s,'Synthetic Workspace',"
        "'synthetic-workspace','synthetic-bot',clock_timestamp()) AS revision",
        (account, connection, expected, holder, envelope(version), version),
    ).fetchone()["revision"]


def connected(conn, account=None):
    """A connected connection at revision 1; returns (connection, account)."""
    connection, account, holder = reserve(conn, account)
    assert store(conn, account, connection, 0, holder=holder) == 1
    return connection, account


def connection_row(conn, connection):
    return conn.execute(
        "SELECT id,account_id,revision,state,pending_holder,creation_capability,"
        "last_destination_id FROM export.connection WHERE id=%s",
        (connection,),
    ).fetchone()


def preview(conn, connection, account, *, artifact=None, destination=None, prepared_at=None):
    """The next preview revision of an export pair; returns its binding facts."""
    artifact, destination = artifact or uuid4(), destination or destination_id()
    pair = conn.execute(
        "SELECT preview_id FROM export.preview_pair WHERE account_id=%s AND artifact_id=%s "
        "AND destination_id=%s",
        (account, artifact, destination),
    ).fetchone()
    preview_id = pair["preview_id"] if pair else uuid4()
    if not pair:
        conn.execute(
            "INSERT INTO export.preview_pair(preview_id,account_id,artifact_id,destination_id) "
            "VALUES(%s,%s,%s,%s)",
            (preview_id, account, artifact, destination),
        )
    revision = (
        conn.execute(
            "SELECT current_revision FROM export.preview_pair WHERE preview_id=%s", (preview_id,)
        ).fetchone()["current_revision"]
        + 1
    )
    marker = f"docsuri-export:{preview_id}:{revision}"
    binding = hex_digest("binding", preview_id, revision)
    tree = {"properties": {"title": "Synthetic"}, "children": [{"marker": marker}]}
    conn.execute(
        "INSERT INTO export.preview_revision(preview_id,revision,source_revision,"
        "source_content_hash,source_eligibility_revision,source_title,connection_id,"
        "connection_revision,destination,render_policy,marker,rendered_blocks,rendered_text,"
        "rendered_content_hash,binding_hash,prepared_at) VALUES(%s,%s,'1',%s,'1',"
        "'Synthetic result',%s,1,%s,%s,%s,%s,%s,%s,%s,coalesce(%s,clock_timestamp()))",
        (
            preview_id,
            revision,
            hex_digest("source", artifact),
            connection,
            Jsonb({"destinationId": destination, "connectionId": str(connection)}),
            Jsonb(RENDER_POLICY),
            marker,
            Jsonb(tree),
            "Synthetic\n" + marker,
            hex_digest("content", preview_id, revision),
            binding,
            prepared_at,
        ),
    )
    return {
        "preview_id": preview_id,
        "revision": revision,
        "marker": marker,
        "binding_hash": binding,
        "artifact": artifact,
        "destination": destination,
        "account": account,
    }


def approve(conn, facts, *, session=None, request_key=None):
    approval = uuid4()
    conn.execute(
        "INSERT INTO export.approval(id,account_id,preview_id,preview_revision,binding_hash,"
        "policy,approving_session,request_key) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)",
        (
            approval,
            facts["account"],
            facts["preview_id"],
            facts["revision"],
            facts["binding_hash"],
            Jsonb(APPROVAL_POLICY),
            session or uuid4(),
            request_key or uuid4(),
        ),
    )
    return approval


def bind(conn, facts, approval, *, request_key=None):
    """Consumes the approval and binds its one accepted effect; returns the effect id."""
    effect = uuid4()
    conn.execute(
        "INSERT INTO export.effect(id,approval_id,account_id,artifact_id,destination_id,"
        "binding_hash,marker,request_key) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)",
        (
            effect,
            approval,
            facts["account"],
            facts["artifact"],
            facts["destination"],
            facts["binding_hash"],
            facts["marker"],
            request_key or uuid4(),
        ),
    )
    conn.execute("UPDATE export.approval SET state='consumed' WHERE id=%s", (approval,))
    return effect


def exported(conn, account=None):
    """A connection, one approved preview revision and its accepted effect."""
    connection, account = connected(conn, account)
    facts = preview(conn, connection, account)
    approval = approve(conn, facts)
    return {**facts, "connection": connection, "approval": approval, "effect": bind(conn, facts, approval)}


def advance(conn, effect, state, **facts):
    """One effect update: the given state and facts, with the revision advanced by one."""
    columns = "".join(f",{name}=%s" for name in facts)
    return conn.execute(
        f"UPDATE export.effect SET state=%s,revision=revision+1{columns} WHERE id=%s",
        (state, *facts.values(), effect),
    ).rowcount


def claim(conn, effect, *, number=1):
    """accepted (or a rate-limited executing effect) -> executing with its attempt."""
    if number == 1:
        advance(conn, effect, "executing")
    attempt = uuid4()
    conn.execute(
        "INSERT INTO export.attempt(id,effect_id,attempt_number,started_at,deadline_at,"
        "writer_identity,connection_revision,path_kind) VALUES(%s,%s,%s,clock_timestamp(),"
        "clock_timestamp()+interval '90 seconds','synthetic-bot',1,'synthetic')",
        (attempt, effect, number),
    )
    return attempt


def lifecycle_ticket(connect, account, action, scopes=("live_records",)):
    """A live AccountAccess ticket for ApprovedExport, seeded as U5's tests seed theirs."""
    request, lifecycle_revision = uuid4(), uuid4()
    with connect("accounts") as conn:
        conn.execute(
            "UPDATE accounts.account SET lifecycle_revision=%s WHERE id=%s",
            (lifecycle_revision, account),
        )
        conn.execute(
            "INSERT INTO accounts.lifecycle_request(id,account_id,revision,action,policy_ref,"
            "manifest_revision,manifest,disposition,reason_key) "
            "VALUES(%s,%s,%s,%s,%s,'u6-store-test',%s,'pending','pending')",
            (
                request,
                account,
                lifecycle_revision,
                action,
                Jsonb(APPROVAL_POLICY),
                Jsonb([["ApprovedExport", scope] for scope in scopes]),
            ),
        )
        for scope in scopes:
            conn.execute(
                "INSERT INTO accounts.lifecycle_scope(request_id,participant,scope,generation,"
                "lease_until,attempts) VALUES(%s,'ApprovedExport',%s,1,"
                "clock_timestamp()+interval '1 minute',1)",
                (request, scope),
            )
    return (request, account, 1, Jsonb(APPROVAL_POLICY), "u6-store-test")


def end_attempt(conn, attempt, response_class, **facts):
    columns = "".join(f",{name}=%s" for name in facts)
    return conn.execute(
        f"UPDATE export.attempt SET ended_at=clock_timestamp(),response_class=%s{columns} "
        "WHERE id=%s",
        (response_class, *facts.values(), attempt),
    ).rowcount
