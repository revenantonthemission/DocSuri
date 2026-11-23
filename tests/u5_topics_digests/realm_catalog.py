"""Catalog reads and scratch databases over the realm's own superuser login.

U5's runner applies every migration as this login (`migration-credentials.json`).
Tests use it only to read what no owner login may read - the catalog's grants and
whole-table snapshots - and to create a scratch database they own and always drop.
They never use it to seed rows on an owner's behalf or to bypass an owner's grants.
"""

from __future__ import annotations

import json
import secrets
from contextlib import contextmanager

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

from backend.local_profile import private_bytes

SYSTEM_SCHEMAS = ("pg_catalog", "information_schema", "pg_toast")
# One row per relation with the privileges `role` holds on it. has_any_column_privilege
# also sees a grant on a single column, which has_table_privilege does not, so the
# column-capable privileges use it. Sequences report `SEQUENCE <privilege>`.
RELATION_PRIVILEGES = """
SELECT n.nspname || '.' || c.relname AS relation, array_remove(CASE WHEN c.relkind = 'S' THEN ARRAY[
    CASE WHEN has_sequence_privilege(%(role)s, c.oid, 'USAGE') THEN 'SEQUENCE USAGE' END,
    CASE WHEN has_sequence_privilege(%(role)s, c.oid, 'SELECT') THEN 'SEQUENCE SELECT' END,
    CASE WHEN has_sequence_privilege(%(role)s, c.oid, 'UPDATE') THEN 'SEQUENCE UPDATE' END]
  ELSE ARRAY[
    CASE WHEN has_any_column_privilege(%(role)s, c.oid, 'SELECT') THEN 'SELECT' END,
    CASE WHEN has_any_column_privilege(%(role)s, c.oid, 'INSERT') THEN 'INSERT' END,
    CASE WHEN has_any_column_privilege(%(role)s, c.oid, 'UPDATE') THEN 'UPDATE' END,
    CASE WHEN has_table_privilege(%(role)s, c.oid, 'DELETE') THEN 'DELETE' END,
    CASE WHEN has_table_privilege(%(role)s, c.oid, 'TRUNCATE') THEN 'TRUNCATE' END,
    CASE WHEN has_any_column_privilege(%(role)s, c.oid, 'REFERENCES') THEN 'REFERENCES' END,
    CASE WHEN has_table_privilege(%(role)s, c.oid, 'TRIGGER') THEN 'TRIGGER' END] END, NULL) AS held
FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE c.relkind IN ('r','p','v','m','f','S') AND n.nspname <> ALL(%(system)s)
  AND n.nspname !~ '^pg_'
"""


def admin_connection(realm, *, dbname=None, autocommit=False, rows=dict_row):
    """The realm's superuser. On the realm database the run identity is checked first."""
    secret = json.loads(private_bytes(realm.root / "migration-credentials.json"))
    options = {} if rows is None else {"row_factory": rows}
    conn = psycopg.connect(
        host="127.0.0.1",
        port=realm.database_port,
        dbname=dbname or realm.database_name,
        user="postgres",
        password=secret["databaseAdminPassword"],
        connect_timeout=3,
        autocommit=autocommit,
        **options,
    )
    if dbname is None:
        identity = conn.execute("SELECT run_id FROM public.docsuri_local_identity").fetchone()
        run_id = identity["run_id"] if rows is dict_row else identity[0]
        if run_id != realm.run_id:
            conn.close()
            raise AssertionError("the realm database belongs to another run")
        if not autocommit:
            conn.commit()
    return conn


@contextmanager
def scratch_database(realm, label: str):
    """A database in the realm's cluster that only this test uses; always dropped."""
    name = f"docsuri_u5_scratch_{label}_{secrets.token_hex(4)}"
    with admin_connection(realm, autocommit=True) as conn:
        conn.execute(sql.SQL("CREATE DATABASE {} TEMPLATE template1").format(sql.Identifier(name)))
    try:
        yield name
    finally:
        with admin_connection(realm, autocommit=True) as conn:
            conn.execute(
                sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(name))
            )


def relations(conn, *, exclude=()) -> list[dict]:
    """Every table, view and sequence outside the system schemas, with its first column
    that a plain `SET c=c` may name (neither generated nor an always-identity column)."""
    return conn.execute(
        "SELECT n.nspname AS schema, c.relname AS name, c.relkind AS kind, "
        "(SELECT a.attname FROM pg_attribute a WHERE a.attrelid=c.oid AND a.attnum>0 "
        " AND NOT a.attisdropped AND a.attgenerated='' AND a.attidentity<>'a' "
        " ORDER BY a.attnum LIMIT 1) AS first_column "
        "FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
        "WHERE c.relkind IN ('r','p','v','m','f','S') AND n.nspname <> ALL(%s) "
        "AND n.nspname !~ '^pg_' ORDER BY 1,2",
        (list(SYSTEM_SCHEMAS) + list(exclude),),
    ).fetchall()


def relation_privileges(conn, role: str) -> dict[str, frozenset[str]]:
    """`schema.name` -> the privileges `role` holds, for every relation it holds any on."""
    rows = conn.execute(
        RELATION_PRIVILEGES, {"role": role, "system": list(SYSTEM_SCHEMAS)}
    ).fetchall()
    return {row["relation"]: frozenset(row["held"]) for row in rows if row["held"]}


def schema_privileges(conn, role: str) -> dict[str, frozenset[str]]:
    """Every schema outside the system ones -> the USAGE and CREATE `role` holds there."""
    rows = conn.execute(
        "SELECT nspname AS schema, has_schema_privilege(%s, oid, 'USAGE') AS can_use, "
        "has_schema_privilege(%s, oid, 'CREATE') AS can_create FROM pg_namespace "
        "WHERE nspname <> ALL(%s) AND nspname !~ '^pg_' ORDER BY 1",
        (role, role, list(SYSTEM_SCHEMAS)),
    ).fetchall()
    return {
        row["schema"]: frozenset(
            label for label, column in (("USAGE", "can_use"), ("CREATE", "can_create")) if row[column]
        )
        for row in rows
    }


def callable_functions(conn, role: str) -> dict[str, dict]:
    """Every function `role` can call: EXECUTE on it and USAGE on its schema."""
    rows = conn.execute(
        "SELECT p.oid::regprocedure::text AS signature, n.nspname AS schema, "
        "p.prosecdef AS definer, pg_get_userbyid(p.proowner) AS owner, "
        "p.prorettype = 'trigger'::regtype AS trigger "
        "FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
        "WHERE n.nspname <> ALL(%s) AND n.nspname !~ '^pg_' "
        "AND has_function_privilege(%s, p.oid, 'EXECUTE') "
        "AND has_schema_privilege(%s, n.oid, 'USAGE') ORDER BY 1",
        (list(SYSTEM_SCHEMAS), role, role),
    ).fetchall()
    return {row["signature"]: row for row in rows}
