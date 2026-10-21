"""Real runtime-role constraints and triggers of schema `export`; no in-memory substitute."""

from uuid import uuid4

import psycopg
import pytest

from tests.u6_approved_export import export_rows as rows

CHECK = psycopg.errors.CheckViolation


def test_pending_reservation_is_revision_zero_held_and_without_envelope(connect):
    """R-01: pending <=> revision 0 <=> a holder; only the holder fields change while pending."""
    with connect("export") as conn:
        connection, account, _ = rows.reserve(conn)
        row = rows.connection_row(conn, connection)
        assert (row["state"], row["revision"]) == ("pending", 0)
        for values in (
            (1, "pending", uuid4()),  # pending at a public revision
            (0, "pending", None),  # pending with no holder
            (1, "connected", None),  # connected without an envelope
        ):
            with pytest.raises(CHECK), conn.transaction():
                conn.execute(
                    "INSERT INTO export.connection(id,account_id,revision,state,pending_holder,"
                    "pending_started_at) VALUES(%s,%s,%s,%s,%s,clock_timestamp())",
                    (uuid4(), uuid4(), *values),
                )
        new_holder = uuid4()
        assert (
            conn.execute(
                "UPDATE export.connection SET pending_holder=%s,pending_started_at=clock_timestamp() "
                "WHERE id=%s AND state='pending'",
                (new_holder, connection),
            ).rowcount
            == 1
        )
        with pytest.raises(CHECK), conn.transaction():
            conn.execute(
                "UPDATE export.connection SET workspace_name='changed' WHERE id=%s", (connection,)
            )
        with pytest.raises(CHECK), conn.transaction():
            conn.execute(
                "UPDATE export.connection SET state='connected',revision=1,pending_holder=NULL,"
                "pending_started_at=NULL WHERE id=%s",
                (connection,),
            )
        assert rows.connection_row(conn, connection)["pending_holder"] == new_holder


def test_envelope_exists_exactly_while_in_use_and_names_its_key_version(connect):
    """A stored envelope is `DSE1`-tagged and carries the version column as its version field."""
    with connect("export") as conn:
        connection, account, holder = rows.reserve(conn)
        version, other = rows.key_version(), rows.key_version()
        malformed = (
            (rows.envelope(other), version),  # version field differs from the column
            (b"DSX1" + rows.envelope(version)[4:], version),  # wrong tag
            (rows.envelope(version)[:60], version),  # too short to hold nonce and tag
        )
        for envelope, column in malformed:
            with pytest.raises(CHECK), conn.transaction():
                conn.execute(
                    "SELECT export.store_token_envelope(%s,%s,0,%s,%s,%s,NULL,NULL,NULL,NULL)",
                    (account, connection, holder, envelope, column),
                )
        assert rows.store(conn, account, connection, 0, holder=holder, version=version) == 1
        opened = conn.execute(
            "SELECT * FROM export.open_token_envelope(%s,%s)", (account, connection)
        ).fetchone()
        assert opened["token_key_version"] == version and opened["revision"] == 1
        assert bytes(opened["sealed_token"])[5 : 5 + len(version)] == version.encode()
        # The runtime role cannot end use without clearing the envelope it cannot write.
        with pytest.raises(CHECK), conn.transaction():
            conn.execute(
                "UPDATE export.connection SET state='disconnected',revision=revision+1 WHERE id=%s",
                (connection,),
            )
        cleared = conn.execute(
            "SELECT export.clear_token_envelope(%s,%s,1,'disconnected') AS revision",
            (account, connection),
        ).fetchone()["revision"]
        assert cleared == 2
        assert not conn.execute(
            "SELECT * FROM export.open_token_envelope(%s,%s)", (account, connection)
        ).fetchall()


def test_connection_transitions_outside_the_state_machine_are_refused(connect):
    with connect("export") as conn:
        connection, account = rows.connected(conn)
        refused = (
            "UPDATE export.connection SET account_id=%s WHERE id=%s",
            "UPDATE export.connection SET revision=0 WHERE id=%s",
            "UPDATE export.connection SET state='pending' WHERE id=%s",
            "UPDATE export.connection SET state='unavailable',revision=revision+1 WHERE id=%s",
            "UPDATE export.connection SET workspace_name='renamed' WHERE id=%s",
        )
        for statement in refused:
            parameters = (uuid4(), connection) if "account_id" in statement else (connection,)
            with pytest.raises(CHECK), conn.transaction():
                conn.execute(statement, parameters)
        # BR1.6: unavailability and recovery keep the revision.
        for state in ("unavailable", "connected"):
            conn.execute("UPDATE export.connection SET state=%s WHERE id=%s", (state, connection))
            assert rows.connection_row(conn, connection)["revision"] == 1
        assert conn.execute(
            "SELECT export.clear_token_envelope(%s,%s,1,'revoked') AS revision",
            (account, connection),
        ).fetchone()["revision"] == 2
        for statement in (
            "UPDATE export.connection SET state='disconnected',revision=revision+1 WHERE id=%s",
            "UPDATE export.connection SET state='unavailable' WHERE id=%s",
        ):
            with pytest.raises(CHECK), conn.transaction():
                conn.execute(statement, (connection,))
        # Reconnecting a revoked connection advances by exactly one.
        assert rows.store(conn, account, connection, 2) == 3


def test_outcome_facts_keep_the_revision_and_a_replace_resets_the_capability(connect):
    """Decision "Connection facts from outcomes": facts change at an unchanged revision."""
    with connect("export") as conn:
        connection, account = rows.connected(conn)
        destination = rows.destination_id()
        conn.execute(
            "UPDATE export.connection SET creation_capability='confirmed',last_destination_id=%s "
            "WHERE id=%s",
            (destination, connection),
        )
        row = rows.connection_row(conn, connection)
        assert (row["revision"], row["creation_capability"]) == (1, "confirmed")
        # A new token never inherits a confirmed capability.
        with pytest.raises(CHECK), conn.transaction():
            conn.execute(
                "UPDATE export.connection SET revision=revision+1 WHERE id=%s", (connection,)
            )
        assert rows.store(conn, account, connection, 1) == 2
        row = rows.connection_row(conn, connection)
        assert (row["creation_capability"], row["last_destination_id"]) == ("unknown", destination)
        conn.execute(
            "UPDATE export.connection SET creation_capability='refused' WHERE id=%s", (connection,)
        )
        assert rows.connection_row(conn, connection)["revision"] == 2


def test_preview_revision_is_immutable_except_one_trim(connect):
    """D12 and BR2.6: the frozen tree, hashes and marker never change; one trim clears the copy."""
    with connect("export") as conn:
        connection, account = rows.connected(conn)
        first = rows.preview(conn, connection, account)
        key = (first["preview_id"], first["revision"])
        for assignment in (
            "rendered_content_hash=repeat('0',64)",
            "rendered_text='edited'",
            "marker='docsuri-export:other'",
            "binding_hash=repeat('1',64)",
        ):
            with pytest.raises(CHECK), conn.transaction():
                conn.execute(
                    f"UPDATE export.preview_revision SET {assignment} "
                    "WHERE preview_id=%s AND revision=%s",
                    key,
                )
        with pytest.raises(CHECK), conn.transaction():  # half a trim
            conn.execute(
                "UPDATE export.preview_revision SET rendered_text=NULL,trimmed_at=clock_timestamp() "
                "WHERE preview_id=%s AND revision=%s",
                key,
            )
        trim = (
            "UPDATE export.preview_revision SET rendered_blocks=NULL,rendered_text=NULL,"
            "trimmed_at=clock_timestamp() WHERE preview_id=%s AND revision=%s"
        )
        assert conn.execute(trim, key).rowcount == 1
        with pytest.raises(CHECK), conn.transaction():
            conn.execute(trim, key)
        with pytest.raises(CHECK), conn.transaction():
            rows.approve(conn, first)  # a trimmed revision can no longer be approved
        second = rows.preview(
            conn, connection, account, artifact=first["artifact"], destination=first["destination"]
        )
        assert (second["preview_id"], second["revision"]) == (first["preview_id"], 2)
        pair = conn.execute(
            "SELECT current_revision FROM export.preview_pair WHERE preview_id=%s",
            (first["preview_id"],),
        ).fetchone()
        assert pair["current_revision"] == 2


def test_preview_revisions_are_consecutive_and_markers_unique(connect):
    with connect("export") as conn:
        connection, account = rows.connected(conn)
        facts = rows.preview(conn, connection, account)
        insert = (
            "INSERT INTO export.preview_revision(preview_id,revision,source_revision,"
            "source_content_hash,source_eligibility_revision,source_title,connection_id,"
            "connection_revision,destination,render_policy,marker,rendered_blocks,rendered_text,"
            "rendered_content_hash,binding_hash) VALUES(%s,%s,'1',repeat('a',64),'1','t',%s,1,"
            "'{}','{}',%s,'{}','t',repeat('b',64),repeat('c',64))"
        )
        with pytest.raises(CHECK), conn.transaction():
            conn.execute(insert, (facts["preview_id"], 3, connection, f"skip-{uuid4()}"))
        with pytest.raises(psycopg.errors.UniqueViolation), conn.transaction():
            conn.execute(insert, (facts["preview_id"], 2, connection, facts["marker"]))
        with pytest.raises(CHECK), conn.transaction():
            conn.execute(
                "UPDATE export.preview_pair SET artifact_id=%s WHERE preview_id=%s",
                (uuid4(), facts["preview_id"]),
            )


def test_one_approval_per_revision_never_expired_and_never_timed(connect):
    """BR3.2 and BR3.5: one approval per preview revision; `expired` and `expires_at` never occur."""
    with connect("export") as conn:
        connection, account = rows.connected(conn)
        facts = rows.preview(conn, connection, account)
        with pytest.raises(CHECK), conn.transaction():  # an approval binds its revision's hash
            rows.approve(conn, {**facts, "binding_hash": "f" * 64})
        with pytest.raises(CHECK), conn.transaction():  # an approval binds its pair's owner
            rows.approve(conn, {**facts, "account": uuid4()})
        approval = rows.approve(conn, facts)
        with pytest.raises(psycopg.errors.UniqueViolation), conn.transaction():
            rows.approve(conn, facts)
        for statement in (
            "UPDATE export.approval SET expires_at=clock_timestamp() WHERE id=%s",
            "UPDATE export.approval SET state='expired' WHERE id=%s",
            "UPDATE export.approval SET state='invalidated' WHERE id=%s",
            "UPDATE export.approval SET binding_hash=repeat('e',64) WHERE id=%s",
        ):
            with pytest.raises(CHECK), conn.transaction():
                conn.execute(statement, (approval,))
        conn.execute(
            "UPDATE export.approval SET state='invalidated',invalidation_reason='source-changed' "
            "WHERE id=%s",
            (approval,),
        )
        with pytest.raises(CHECK), conn.transaction():
            conn.execute("UPDATE export.approval SET state='cancelled',invalidation_reason=NULL "
                         "WHERE id=%s", (approval,))


def test_effect_transitions_follow_the_state_machine(connect):
    """BR4.3: unknown never executes again, terminal effects are frozen, revision +1 per update."""
    with connect("export") as conn:
        bound = rows.exported(conn)
        effect = bound["effect"]
        with pytest.raises(CHECK), conn.transaction():  # revision must advance
            conn.execute("UPDATE export.effect SET waiting_since=clock_timestamp() WHERE id=%s",
                         (effect,))
        with pytest.raises(CHECK), conn.transaction():  # accepted cannot jump to unknown
            rows.advance(conn, effect, "unknown")
        with pytest.raises(CHECK), conn.transaction():  # a remote page only when succeeded
            rows.advance(conn, effect, "accepted", remote_reference="page")
        rows.advance(conn, effect, "accepted", waiting_since=None)
        rows.claim(conn, effect)
        rows.advance(conn, effect, "unknown")
        with pytest.raises(CHECK), conn.transaction():
            rows.advance(conn, effect, "executing")
        with pytest.raises(CHECK), conn.transaction():  # a terminal state needs ended_at
            rows.advance(conn, effect, "succeeded")
        conn.execute(
            "UPDATE export.effect SET state='succeeded',revision=revision+1,"
            "ended_at=clock_timestamp(),remote_reference='page-1',settled_by='reconciliation' "
            "WHERE id=%s",
            (effect,),
        )
        with pytest.raises(CHECK), conn.transaction():
            rows.advance(conn, effect, "succeeded", remote_url="https://example.invalid/p")


def test_failed_effects_carry_a_reason_and_never_return_to_accepted(connect):
    with connect("export") as conn:
        effect = rows.exported(conn)["effect"]
        with pytest.raises(CHECK), conn.transaction():  # an accepted effect has no ended_at
            conn.execute(
                "UPDATE export.effect SET revision=revision+1,ended_at=clock_timestamp() WHERE id=%s",
                (effect,),
            )
        with pytest.raises(CHECK), conn.transaction():  # failed needs its reason
            conn.execute(
                "UPDATE export.effect SET state='failed',revision=revision+1,"
                "ended_at=clock_timestamp() WHERE id=%s",
                (effect,),
            )
        conn.execute(
            "UPDATE export.effect SET state='failed',revision=revision+1,ended_at=clock_timestamp(),"
            "outcome_reason='dependency-unavailable' WHERE id=%s",
            (effect,),
        )
        with pytest.raises(CHECK), conn.transaction():
            conn.execute(
                "UPDATE export.effect SET state='accepted',revision=revision+1,ended_at=NULL,"
                "outcome_reason=NULL WHERE id=%s",
                (effect,),
            )
        row = conn.execute("SELECT state,revision FROM export.effect WHERE id=%s", (effect,)).fetchone()
        assert (row["state"], row["revision"]) == ("failed", 2)


def test_one_effect_in_flight_per_owner_and_effects_copy_their_binding(connect):
    """BR5.1 and BR4.1: one accepted-or-executing effect per owner; the marker is the revision's."""
    with connect("export") as conn:
        first = rows.exported(conn)
        account, connection = first["account"], first["connection"]
        second = rows.preview(conn, connection, account)
        approval = rows.approve(conn, second)
        with pytest.raises(CHECK), conn.transaction():
            rows.bind(conn, {**second, "marker": first["marker"]}, approval)
        with pytest.raises(CHECK), conn.transaction():
            conn.execute(
                "INSERT INTO export.effect(id,approval_id,account_id,artifact_id,destination_id,"
                "binding_hash,marker,request_key,state) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,'executing')",
                (uuid4(), approval, account, second["artifact"], second["destination"],
                 second["binding_hash"], second["marker"], uuid4()),
            )
        with pytest.raises(psycopg.errors.UniqueViolation), conn.transaction():
            rows.bind(conn, second, approval)
        conn.execute(
            "UPDATE export.effect SET state='cancelled',revision=revision+1,"
            "ended_at=clock_timestamp(),outcome_reason='owner-cancelled' WHERE id=%s",
            (first["effect"],),
        )
        rows.bind(conn, second, approval)
        unique = conn.execute(
            "SELECT count(*) AS n FROM pg_indexes WHERE schemaname='export' AND tablename='effect' "
            "AND indexdef LIKE 'CREATE UNIQUE INDEX % (marker)'"
        ).fetchone()["n"]
        assert unique == 1


def test_a_commit_leaving_an_executing_effect_without_an_attempt_is_refused(connect):
    """NFR4.8: the deferred check refuses the commit, and a claim with its attempt commits."""
    with connect("export") as conn:
        effect = rows.exported(conn)["effect"]
        conn.commit()
        rows.advance(conn, effect, "executing")
        with pytest.raises(CHECK):
            conn.commit()
        assert conn.execute("SELECT state FROM export.effect WHERE id=%s",
                            (effect,)).fetchone()["state"] == "accepted"
        rows.claim(conn, effect)
        conn.commit()
        assert conn.execute("SELECT state FROM export.effect WHERE id=%s",
                            (effect,)).fetchone()["state"] == "executing"


def test_attempts_are_consecutive_follow_only_rate_limits_and_set_facts_once(connect):
    with connect("export") as conn:
        effect = rows.exported(conn)["effect"]
        with pytest.raises(CHECK), conn.transaction():  # the effect is not executing yet
            conn.execute(
                "INSERT INTO export.attempt(id,effect_id,attempt_number,started_at,deadline_at,"
                "writer_identity,connection_revision,path_kind) VALUES(%s,%s,1,clock_timestamp(),"
                "clock_timestamp()+interval '90 seconds','bot',1,'synthetic')",
                (uuid4(), effect),
            )
        first = rows.claim(conn, effect)
        with pytest.raises(CHECK), conn.transaction():  # the first is still outstanding
            rows.claim(conn, effect, number=2)
        rows.end_attempt(conn, first, "rate-limited", provider_request_id="request-1")
        with pytest.raises(CHECK), conn.transaction():
            rows.claim(conn, effect, number=3)
        for statement in (
            "UPDATE export.attempt SET response_class='uncertain' WHERE id=%s",
            "UPDATE export.attempt SET provider_request_id='request-2' WHERE id=%s",
            "UPDATE export.attempt SET writer_identity='other-bot' WHERE id=%s",
        ):
            with pytest.raises(CHECK), conn.transaction():
                conn.execute(statement, (first,))
        second = rows.claim(conn, effect, number=2)
        rows.end_attempt(conn, second, "uncertain")
        with pytest.raises(CHECK), conn.transaction():  # only a rate-limited attempt repeats
            rows.claim(conn, effect, number=3)


def test_reconciliation_checks_are_insert_only(connect):
    with connect("export") as conn:
        effect = rows.exported(conn)["effect"]
        insert = (
            "INSERT INTO export.reconciliation_check(id,effect_id,checked_at,window_start,result,"
            "remote_reference,evidence_hash) VALUES(%s,%s,clock_timestamp(),clock_timestamp(),"
            "%s,%s,repeat('d',64))"
        )
        with pytest.raises(CHECK), conn.transaction():  # marker-found names its page
            conn.execute(insert, (uuid4(), effect, "marker-found", None))
        check = uuid4()
        conn.execute(insert, (check, effect, "not-found", None))
        for statement in (
            "UPDATE export.reconciliation_check SET result='listing-incomplete' WHERE id=%s",
            "UPDATE export.reconciliation_check SET checked_at=clock_timestamp() WHERE id=%s",
        ):
            with pytest.raises(CHECK), conn.transaction():
                conn.execute(statement, (check,))
