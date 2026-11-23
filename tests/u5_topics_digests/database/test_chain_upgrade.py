"""Step 17 (d): the seven repair migrations upgrade a populated pre-repair chain in place.

A scratch database this module owns receives the runner's own base install and
amendments and U5's chain through `u5_run_guard.sql`: the 59 migrations the first U5
build applied. Pre-repair rows then go in under each owner's own role: topics with runs
in every state, their settings, send logs, outcomes, a watermark, lifecycle evidence and
a Personalization settings row from before time zones existed. The seven repairs follow.
The module reads back every row and receipt, exercises the constraints and guards on the
old rows, and compares the upgraded catalog with the realm's fresh install of the same
66 migrations.

The chain's current bytes are applied throughout. A realm that recorded the first bytes
of `u5_digest_read.sql` is refused rather than upgraded; test_migration_digests.py pins
that.
"""

import datetime as dt
import hashlib
from contextlib import contextmanager
from types import SimpleNamespace
from uuid import uuid4
from zoneinfo import ZoneInfo

import psycopg
import pytest
from psycopg import sql
from psycopg.rows import dict_row, tuple_row
from psycopg.types.json import Jsonb

from scripts import verify_docsuri_u5 as runner
from tests.u5_topics_digests.realm_catalog import SYSTEM_SCHEMAS, admin_connection, scratch_database

LAST_BEFORE_REPAIRS = "backend/modules/topics/u5_run_guard.sql"
REPAIRS = (
    "backend/modules/personalization/u5_digest_preferences.sql",
    "backend/modules/topics/u5_preference_snapshot.sql",
    "backend/modules/topics/u5_schedule.sql",
    "backend/modules/topics/u5_unsubscribe_capability.sql",
    "backend/modules/topics/u5_real_send_retention.sql",
    "backend/modules/topics/u5_refusal_detail.sql",
    "backend/modules/topics/u5_scheduled_instant.sql",
)
PRE_REPAIR_MIGRATIONS = 59  # the first U5 build's realm (code summary)
# Every table holding a pre-repair row, keyed by its primary key.
PRE_REPAIR_ROWS = {
    "topics.followed_topic": "id",
    "topics.digest_settings": "id",
    "topics.digest_run": "id",
    "topics.delivery_outcome": "id",
    "topics.send_log_entry": "id",
    "topics.topic_delivery_watermark": "id",
    "topics.lifecycle_evidence": "request_id",
    "personalization.settings": "account_id",
}
ITEM = {"versionId": "v-legacy-1", "paperId": "p-legacy-1", "title": "Legacy", "publishedOn": "2026-01-03"}
LATEST_PRE_REPAIR_WINDOW = dt.date(2026, 1, 28)
# The catalog of a whole database, outside the system schemas.
OUTSIDE_SYSTEM = "n.nspname <> ALL(%(system)s) AND n.nspname !~ '^pg_'"
CATALOG = {
    "schemas": "SELECT n.nspname, pg_get_userbyid(n.nspowner), coalesce(n.nspacl::text,'') "
    f"FROM pg_namespace n WHERE {OUTSIDE_SYSTEM}",
    "relations": "SELECT n.nspname, c.relname, c.relkind, pg_get_userbyid(c.relowner), "
    "coalesce(c.relacl::text,''), c.relpersistence FROM pg_class c "
    "JOIN pg_namespace n ON n.oid=c.relnamespace "
    f"WHERE c.relkind IN ('r','p','v','m','f','S','i') AND {OUTSIDE_SYSTEM}",
    "columns": "SELECT n.nspname, c.relname, a.attnum, a.attname, format_type(a.atttypid,a.atttypmod), "
    "a.attnotnull, coalesce(pg_get_expr(d.adbin,d.adrelid),''), a.attidentity, a.attgenerated, "
    "coalesce(a.attacl::text,'') FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid "
    "JOIN pg_namespace n ON n.oid=c.relnamespace "
    "LEFT JOIN pg_attrdef d ON d.adrelid=a.attrelid AND d.adnum=a.attnum "
    f"WHERE c.relkind IN ('r','p','v','m','f') AND a.attnum>0 AND NOT a.attisdropped AND {OUTSIDE_SYSTEM}",
    "constraints": "SELECT n.nspname, c.relname, k.conname, k.contype, k.convalidated, "
    "pg_get_constraintdef(k.oid) FROM pg_constraint k JOIN pg_class c ON c.oid=k.conrelid "
    f"JOIN pg_namespace n ON n.oid=c.relnamespace WHERE {OUTSIDE_SYSTEM}",
    "indexes": "SELECT n.nspname, c.relname, pg_get_indexdef(i.indexrelid) FROM pg_index i "
    f"JOIN pg_class c ON c.oid=i.indrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE {OUTSIDE_SYSTEM}",
    "triggers": "SELECT n.nspname, c.relname, t.tgname, t.tgenabled, pg_get_triggerdef(t.oid) "
    "FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid JOIN pg_namespace n ON n.oid=c.relnamespace "
    f"WHERE NOT t.tgisinternal AND {OUTSIDE_SYSTEM}",
    "functions": "SELECT n.nspname, p.oid::regprocedure::text, p.prorettype::regtype::text, "
    "pg_get_userbyid(p.proowner), p.prokind, p.prosecdef, p.provolatile, coalesce(p.proacl::text,''), "
    "coalesce(array_to_string(p.proconfig,','),''), md5(p.prosrc) FROM pg_proc p "
    f"JOIN pg_namespace n ON n.oid=p.pronamespace WHERE {OUTSIDE_SYSTEM}",
    "default privileges": "SELECT pg_get_userbyid(d.defaclrole), coalesce(n.nspname,''), "
    "d.defaclobjtype, d.defaclacl::text FROM pg_default_acl d "
    "LEFT JOIN pg_namespace n ON n.oid=d.defaclnamespace",
}


class ExistingRoles:
    """The runner's base install, minus role creation: the scratch database shares the
    realm's cluster, where every owner role and login already exists."""

    def __init__(self, conn):
        self.conn = conn
        self.skipped = []

    def execute(self, statement, params=None, **kwargs):
        text = statement if isinstance(statement, str) else statement.as_string(self.conn)
        if text.startswith("CREATE ROLE "):
            self.skipped.append(text.split()[2].strip('"'))
            return None
        return self.conn.execute(statement, params, **kwargs)


def apply_chain(conn, files, recorded: dict, database: str) -> None:
    """The loop of the runner's `migrate` (scripts/verify_docsuri_u5.py), on `database`."""
    for owner, relative in files:
        assert relative not in recorded, relative
        if relative == "ops/src/docsuri_ops/u3_capacity.sql":
            conn.execute(
                sql.SQL("GRANT CONNECT ON DATABASE {} TO docsuri_operations_owner").format(
                    sql.Identifier(database)
                )
            )
            conn.execute("GRANT EXECUTE ON FUNCTION pg_catalog.pg_ls_waldir() TO docsuri_operations_owner")
        conn.execute(sql.SQL("SET LOCAL ROLE {}").format(sql.Identifier(f"docsuri_{owner}_owner")))
        conn.execute((runner.ROOT / relative).read_text(), prepare=False)
        conn.execute("RESET ROLE")
        recorded[relative] = runner.digest(runner.ROOT / relative)
    conn.execute(
        "UPDATE public.docsuri_local_identity SET schema_hashes=%s WHERE singleton", (Jsonb(recorded),)
    )


def as_role(conn, role: str) -> None:
    conn.execute(sql.SQL("SET LOCAL ROLE {}").format(sql.Identifier(role)))


def follow(conn, topic, owner, key, *, cadence="daily", day=None, window=7):
    conn.execute(
        "INSERT INTO topics.followed_topic(id,account_id,topic_key,display_name) "
        "VALUES(%s,%s,%s,'Legacy Topic')",
        (topic, owner, key),
    )
    conn.execute(
        "INSERT INTO topics.digest_settings(id,topic_id,cadence,delivery_time_local,delivery_day,"
        "content_window_days) VALUES(%s,%s,%s,'09:00',%s,%s)",
        (uuid4(), topic, cadence, day, window),
    )


def prepare(conn, run, topic, start, end, *, content=(ITEM,), revision=1):
    conn.execute(
        "INSERT INTO topics.digest_run(id,topic_id,window_start,window_end,digest_content,"
        "settings_revision) VALUES(%s,%s,%s,%s,%s,%s)",
        (run, topic, start, end, Jsonb(list(content)), revision),
    )


def move(conn, run, state):
    conn.execute(
        "UPDATE topics.digest_run SET state=%s,updated_at=clock_timestamp() WHERE id=%s", (state, run)
    )


def attempt(conn, run, *, receipt=None):
    """A send as the first build recorded it: always on the local sink."""
    move(conn, run, "sending")
    conn.execute(
        "INSERT INTO topics.send_log_entry(id,run_id,path_kind) VALUES(%s,%s,'local-sink')", (uuid4(), run)
    )
    if receipt is not None:
        conn.execute(
            "UPDATE topics.send_log_entry SET transport_receipt=%s,acknowledged_at=clock_timestamp() "
            "WHERE run_id=%s",
            (receipt, run),
        )


def observe(conn, run, state, reason=None):
    move(conn, run, state)
    conn.execute(
        "INSERT INTO topics.delivery_outcome(id,run_id,observed_state,failure_reason) VALUES(%s,%s,%s,%s)",
        (uuid4(), run, state, reason),
    )


def seed_pre_repair(conn) -> SimpleNamespace:
    ids = SimpleNamespace(
        owner_a=uuid4(),
        owner_b=uuid4(),
        request=uuid4(),
        **{f"t{n}": uuid4() for n in range(1, 5)},
        **{f"r{n}": uuid4() for n in range(1, 9)},
    )
    as_role(conn, "docsuri_personalization")
    conn.execute(
        "INSERT INTO personalization.settings(account_id,appearance,defaults) VALUES(%s,'dark',%s)",
        (ids.owner_a, Jsonb({"assistanceDefaults": {"languageId": "ko", "presentationLevelId": "standard"}})),
    )
    as_role(conn, "docsuri_topics")
    # Owner A, daily: sent with a watermark, failed, an attempt cut mid-send, and a later
    # window queued before them (the run guard only stops a window behind open work).
    follow(conn, ids.t1, ids.owner_a, "legacy-daily")
    prepare(conn, ids.r4, ids.t1, "2026-01-22", "2026-01-28")
    prepare(conn, ids.r1, ids.t1, "2026-01-01", "2026-01-07")
    attempt(conn, ids.r1, receipt="sink-legacy-1")
    observe(conn, ids.r1, "sent")
    conn.execute(
        "INSERT INTO topics.topic_delivery_watermark(id,topic_id,content_id,included_in_run_id) "
        "VALUES(%s,%s,'v-legacy-1',%s)",
        (uuid4(), ids.t1, ids.r1),
    )
    prepare(conn, ids.r2, ids.t1, "2026-01-08", "2026-01-14")
    attempt(conn, ids.r2)
    observe(conn, ids.r2, "failed", "transport-error")
    prepare(conn, ids.r3, ids.t1, "2026-01-15", "2026-01-21")
    attempt(conn, ids.r3)
    # Owner A, weekly: an empty digest, then unsubscribed.
    follow(conn, ids.t2, ids.owner_a, "legacy-weekly", cadence="weekly", day="mon", window=30)
    prepare(conn, ids.r5, ids.t2, "2026-01-01", "2026-01-30", content=())
    observe(conn, ids.r5, "empty")
    conn.execute(
        "UPDATE topics.followed_topic SET status='unsubscribed',updated_at=clock_timestamp() WHERE id=%s",
        (ids.t2,),
    )
    # Owner B, weekly: a settings change discarded queued work and re-prepared the window.
    follow(conn, ids.t3, ids.owner_b, "legacy-revised", cadence="weekly", day="fri")
    prepare(conn, ids.r6, ids.t3, "2026-01-01", "2026-01-07")
    conn.execute(
        "UPDATE topics.digest_settings SET content_window_days=30,revision=2 WHERE topic_id=%s", (ids.t3,)
    )
    move(conn, ids.r6, "discarded")
    prepare(conn, ids.r7, ids.t3, "2026-01-01", "2026-01-07", revision=2)
    # Owner B, daily: an attempt whose outcome was never observed.
    follow(conn, ids.t4, ids.owner_b, "legacy-unknown")
    prepare(conn, ids.r8, ids.t4, "2026-01-01", "2026-01-07")
    attempt(conn, ids.r8)
    observe(conn, ids.r8, "unknown")
    conn.execute(
        "INSERT INTO topics.lifecycle_evidence(request_id,scope,generation,policy_ref,"
        "manifest_revision,evidence_ref) VALUES(%s,'live_records',1,%s,'legacy-manifest',%s)",
        (ids.request, Jsonb({"policyId": "legacy"}), uuid4()),
    )
    conn.execute("RESET ROLE")
    return ids


def read_rows(conn) -> dict:
    with conn.cursor(row_factory=dict_row) as cursor:
        return {
            table: {
                str(row["value"][key]): row["value"]
                for row in cursor.execute(
                    sql.SQL("SELECT to_jsonb(t) AS value FROM {} t").format(
                        sql.Identifier(*table.split("."))
                    )
                ).fetchall()
            }
            for table, key in PRE_REPAIR_ROWS.items()
        }


def catalog(conn) -> dict:
    with conn.cursor(row_factory=tuple_row) as cursor:
        return {
            name: sorted(
                tuple(map(str, row))
                for row in cursor.execute(
                    query, {"system": list(SYSTEM_SCHEMAS)} if "%(system)s" in query else None
                ).fetchall()
            )
            for name, query in CATALOG.items()
        }


def receipts(conn) -> dict:
    with conn.cursor(row_factory=tuple_row) as cursor:
        return cursor.execute("SELECT schema_hashes FROM public.docsuri_local_identity").fetchone()[0]


@pytest.fixture(scope="module")
def upgraded(realm):
    files = [relative for _, relative in runner.MIGRATIONS]
    cut = files.index(LAST_BEFORE_REPAIRS) + 1
    before, repairs = runner.MIGRATIONS[:cut], runner.MIGRATIONS[cut:]
    assert tuple(relative for _, relative in repairs) == REPAIRS
    with scratch_database(realm, "upgrade") as name:
        # The runner's own functions read tuple rows.
        with admin_connection(realm, dbname=name, rows=None) as conn:
            hashes = {owner: runner.digest(runner.ROOT / path) for owner, path in runner.SCHEMAS.items()}
            identity = {"runId": f"{realm.run_id}-scratch-upgrade"}
            install = ExistingRoles(conn)
            with pytest.MonkeyPatch.context() as patch:
                patch.setattr(runner, "DATABASE", name)
                runner.install_base(install, identity, {"roles": dict.fromkeys(runner.OWNERS, "")}, hashes)
            recorded = runner.amend(conn, identity, hashes)
            apply_chain(conn, before, recorded, name)
            conn.commit()
            pre_repair = dict(recorded)
            ids = seed_pre_repair(conn)
            conn.commit()
            rows_before = read_rows(conn)
            conn.commit()
            apply_chain(conn, repairs, recorded, name)
            conn.commit()
        yield SimpleNamespace(
            name=name, ids=ids, pre_repair=pre_repair, rows_before=rows_before, skipped=install.skipped
        )


@contextmanager
def scratch_session(realm, upgraded):
    """One transaction on the upgraded scratch database, always rolled back."""
    conn = admin_connection(realm, dbname=upgraded.name)
    try:
        yield conn
    finally:
        conn.rollback()
        conn.close()


def test_the_upgrade_keeps_every_pre_repair_row_and_receipt(realm, upgraded):
    with scratch_session(realm, upgraded) as conn:
        after = read_rows(conn)
        recorded = receipts(conn)
        runs = conn.execute(
            "SELECT preference_snapshot,presentation,request_key,scheduled_at FROM topics.digest_run"
        ).fetchall()
        outcomes = conn.execute("SELECT provider_status,provider_error FROM topics.delivery_outcome").fetchall()
        logs = conn.execute(
            "SELECT path_kind,evidence_retain_until,evidence_expired_at FROM topics.send_log_entry"
        ).fetchall()
        unsubscribes = conn.execute("SELECT count(*) AS n FROM topics.email_unsubscribe").fetchone()["n"]
    with admin_connection(realm) as conn:
        fresh = receipts(conn)
    assert set(upgraded.skipped) == {
        role for owner in runner.OWNERS for role in (f"docsuri_{owner}_owner", f"docsuri_{owner}")
    }
    # Receipts: the 59 pre-repair ones unchanged, seven added, the same as a fresh install's.
    assert len(upgraded.pre_repair) == PRE_REPAIR_MIGRATIONS
    assert {path: recorded[path] for path in upgraded.pre_repair} == upgraded.pre_repair
    assert set(recorded) - set(upgraded.pre_repair) == set(REPAIRS)
    assert recorded == fresh
    # Rows: every pre-repair row reads back with every pre-repair value.
    assert {table: len(rows) for table, rows in upgraded.rows_before.items()} == {
        "topics.followed_topic": 4,
        "topics.digest_settings": 4,
        "topics.digest_run": 8,
        "topics.delivery_outcome": 4,
        "topics.send_log_entry": 4,
        "topics.topic_delivery_watermark": 1,
        "topics.lifecycle_evidence": 1,
        "personalization.settings": 1,
    }
    for table, rows in upgraded.rows_before.items():
        assert set(after[table]) == set(rows), table
        for key, row in rows.items():
            assert {column: after[table][key][column] for column in row} == row, (table, key)
    # New columns on old rows hold no invented history.
    assert [(run["preference_snapshot"], run["presentation"]) for run in runs] == [(None, None)] * 8
    assert len({run["request_key"] for run in runs} - {None}) == 8
    # No old run is given a scheduled instant it never had (loop-back 4, L4-2).
    assert [run["scheduled_at"] for run in runs] == [None] * 8
    assert outcomes == [{"provider_status": None, "provider_error": None}] * 4
    assert logs == [{"path_kind": "local-sink", "evidence_retain_until": None, "evidence_expired_at": None}] * 4
    assert unsubscribes == 0


def test_the_upgraded_catalog_matches_a_fresh_install(realm, upgraded):
    with scratch_session(realm, upgraded) as conn:
        upgraded_catalog = catalog(conn)
    with admin_connection(realm) as conn:
        fresh_catalog = catalog(conn)
    # Default privileges may be empty: a per-schema REVOKE cannot lift PostgreSQL's
    # global PUBLIC default, so every function revokes PUBLIC itself.
    assert all(upgraded_catalog[name] for name in CATALOG if name != "default privileges")
    for name in CATALOG:
        assert upgraded_catalog[name] == fresh_catalog[name], name


def test_old_rows_keep_their_constraints_and_guards(realm, upgraded):
    ids = upgraded.ids
    refused = [
        (psycopg.errors.CheckViolation, "UPDATE topics.digest_run SET preference_snapshot='{}' WHERE id=%s", (ids.r1,)),
        (psycopg.errors.CheckViolation, "UPDATE topics.digest_run SET request_key=gen_random_uuid() WHERE id=%s", (ids.r1,)),
        # An old run holds no scheduled instant, and none is filled in later.
        (psycopg.errors.CheckViolation, "UPDATE topics.digest_run SET scheduled_at=created_at WHERE id=%s", (ids.r1,)),
        (psycopg.errors.CheckViolation, "UPDATE topics.digest_run SET state='prepared' WHERE id=%s", (ids.r1,)),
        (
            psycopg.errors.CheckViolation,
            "UPDATE topics.delivery_outcome SET provider_status=400,provider_error='validation_error' WHERE run_id=%s",
            (ids.r2,),
        ),
        (
            psycopg.errors.CheckViolation,
            "UPDATE topics.send_log_entry SET evidence_expired_at=clock_timestamp() WHERE run_id=%s",
            (ids.r1,),
        ),
        # Open work behind the window: the attempt cut mid-send and the queued window.
        (
            psycopg.errors.CheckViolation,
            "INSERT INTO topics.digest_run(id,topic_id,window_start,window_end,digest_content,settings_revision) "
            "VALUES(gen_random_uuid(),%s,'2026-01-29','2026-02-04','[]',1)",
            (ids.t1,),
        ),
        # The re-prepared window is taken; the discarded run does not count.
        (
            psycopg.errors.UniqueViolation,
            "INSERT INTO topics.digest_run(id,topic_id,window_start,window_end,digest_content,settings_revision) "
            "VALUES(gen_random_uuid(),%s,'2026-01-01','2026-01-07','[]',2)",
            (ids.t3,),
        ),
        # One attempt in flight per topic.
        (psycopg.errors.UniqueViolation, "UPDATE topics.digest_run SET state='sending' WHERE id=%s", (ids.r4,)),
        (
            psycopg.errors.CheckViolation,
            "INSERT INTO topics.topic_delivery_watermark(id,topic_id,content_id,included_in_run_id) "
            "VALUES(gen_random_uuid(),%s,'v-legacy-1',%s)",
            (ids.t4, ids.r1),
        ),
    ]
    token = hashlib.sha256(ids.request.bytes).hexdigest()
    with scratch_session(realm, upgraded) as conn:
        as_role(conn, "docsuri_topics")
        for error, statement, params in refused:
            with pytest.raises(error), conn.transaction():
                conn.execute(statement, params)
        # The legal moves still apply to old rows: reconciling the unobserved attempt,
        # retiring the one cut mid-send, and cancelling by email until reactivation.
        move(conn, ids.r8, "sent")
        conn.execute(
            "UPDATE topics.delivery_outcome SET reconciled_state='sent',reconciled_at=clock_timestamp() "
            "WHERE run_id=%s",
            (ids.r8,),
        )
        move(conn, ids.r3, "unknown")
        conn.execute(
            "INSERT INTO topics.email_unsubscribe(token_hash,account_id,topic_id,run_id,expires_at) "
            "VALUES(%s,%s,%s,%s,clock_timestamp()+interval '1 day')",
            (token, ids.owner_a, ids.t2, ids.r5),
        )
        conn.execute("UPDATE topics.followed_topic SET status='active' WHERE id=%s", (ids.t2,))
        states = dict(
            (row["id"], row["state"])
            for row in conn.execute(
                "SELECT id,state FROM topics.digest_run WHERE id = ANY(%s)", ([ids.r3, ids.r8],)
            ).fetchall()
        )
        reconciled = conn.execute(
            "SELECT reconciled_state FROM topics.delivery_outcome WHERE run_id=%s", (ids.r8,)
        ).fetchone()["reconciled_state"]
        revoked = conn.execute(
            "SELECT revoked_at FROM topics.email_unsubscribe WHERE token_hash=%s", (token,)
        ).fetchone()["revoked_at"]
    assert states == {ids.r3: "unknown", ids.r8: "sent"} and reconciled == "sent"
    assert revoked is not None


def test_old_settings_get_no_invented_zone_until_the_owner_confirms_one(realm, upgraded):
    ids = upgraded.ids
    with scratch_session(realm, upgraded) as conn:
        as_role(conn, "docsuri_topics")
        legacy = conn.execute("SELECT personalization.digest_preferences(%s) AS p", (ids.owner_a,)).fetchone()["p"]
        unset = conn.execute("SELECT personalization.digest_preferences(%s) AS p", (ids.owner_b,)).fetchone()["p"]
        horizon = conn.execute("SELECT clock_timestamp()+interval '3 days' AS t").fetchone()["t"]
        unconfirmed = conn.execute("SELECT * FROM topics.next_occurrence(%s,%s)", (ids.t1, horizon)).fetchall()
        as_role(conn, "docsuri_personalization")
        with pytest.raises(psycopg.errors.CheckViolation), conn.transaction():
            conn.execute(
                "UPDATE personalization.settings SET defaults=defaults||%s WHERE account_id=%s",
                (Jsonb({"timeZone": "Mars/Olympus"}), ids.owner_a),
            )
        confirmed = conn.execute(
            "UPDATE personalization.settings SET defaults=defaults||%s WHERE account_id=%s RETURNING defaults",
            (Jsonb({"timeZone": "Asia/Seoul"}), ids.owner_a),
        ).fetchone()["defaults"]
        as_role(conn, "docsuri_topics")
        occurrences = conn.execute("SELECT * FROM topics.next_occurrence(%s,%s)", (ids.t1, horizon)).fetchall()
    assert {key: legacy[key] for key in legacy if key != "sourceRevision"} == {
        "languageId": "ko",
        "presentationLevelId": "standard",
        "timeZone": None,
        "effectiveAt": None,
        "usesDefaults": False,
    }
    assert legacy["sourceRevision"]
    assert unset == {
        "languageId": "en",
        "presentationLevelId": "standard",
        "timeZone": None,
        "effectiveAt": None,
        "sourceRevision": None,
        "usesDefaults": True,
    }
    assert unconfirmed == []
    effective = dt.datetime.fromisoformat(confirmed["timeZoneEffectiveAt"])
    assert confirmed["timeZone"] == "Asia/Seoul"
    # The first due occurrence follows the confirmation: no legacy window is re-run.
    assert len(occurrences) == 1
    occurrence = occurrences[0]
    assert occurrence["window_day"] > LATEST_PRE_REPAIR_WINDOW
    assert effective <= occurrence["due_at"] <= horizon
    assert occurrence["due_at"].astimezone(ZoneInfo("Asia/Seoul")).time() == dt.time(9, 0)
    assert (occurrence["preferences"]["timeZone"], occurrence["preferences"]["languageId"]) == ("Asia/Seoul", "ko")


def test_erasing_an_owner_reaches_every_topics_table_and_no_other_owner(realm, upgraded):
    ids = upgraded.ids
    counted = {
        "followed_topic": "id = ANY(%(topics)s)",
        "digest_settings": "topic_id = ANY(%(topics)s)",
        "digest_run": "topic_id = ANY(%(topics)s)",
        "delivery_outcome": "run_id IN (SELECT id FROM topics.digest_run WHERE topic_id = ANY(%(topics)s))",
        "send_log_entry": "run_id IN (SELECT id FROM topics.digest_run WHERE topic_id = ANY(%(topics)s))",
        "topic_delivery_watermark": "topic_id = ANY(%(topics)s)",
        "email_unsubscribe": "topic_id = ANY(%(topics)s)",
    }

    def counts(conn, topics):
        return {
            table: conn.execute(
                sql.SQL("SELECT count(*) AS n FROM {} WHERE ").format(sql.Identifier("topics", table))
                + sql.SQL(where),
                {"topics": topics},
            ).fetchone()["n"]
            for table, where in counted.items()
        }

    with scratch_session(realm, upgraded) as conn:
        as_role(conn, "docsuri_topics")
        conn.execute(
            "INSERT INTO topics.email_unsubscribe(token_hash,account_id,topic_id,run_id,expires_at) "
            "VALUES(%s,%s,%s,%s,clock_timestamp()+interval '1 day')",
            (hashlib.sha256(ids.owner_b.bytes).hexdigest(), ids.owner_b, ids.t4, ids.r8),
        )
        conn.execute("RESET ROLE")
        erased_before = counts(conn, [ids.t3, ids.t4])
        kept_before = counts(conn, [ids.t1, ids.t2])
        # The role topics.erase_private_controls runs as; its foreign keys do the rest.
        as_role(conn, "docsuri_topics_owner")
        conn.execute("DELETE FROM topics.followed_topic WHERE account_id=%s", (ids.owner_b,))
        conn.execute("RESET ROLE")
        erased_after = counts(conn, [ids.t3, ids.t4])
        kept_after = counts(conn, [ids.t1, ids.t2])
    assert erased_before == {
        "followed_topic": 2,
        "digest_settings": 2,
        "digest_run": 3,
        "delivery_outcome": 1,
        "send_log_entry": 1,
        "topic_delivery_watermark": 0,
        "email_unsubscribe": 1,
    }
    assert erased_after == dict.fromkeys(counted, 0)
    assert kept_after == kept_before
