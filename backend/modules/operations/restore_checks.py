"""The checks a restored database must pass (U8 plan Step 29; BR4.5, BR4.6, Workflow 6,
Workflow 7).

They run on one connection the caller opens: the scheduler's login on a scratch copy,
which the disposable-databases role owns (Workflow 6), or the restore login on the
restored production database, which holds every owner's role (Workflow 7, D14). Neither
is ServiceOperations writing an owner's tables: a scratch copy belongs to no owner, and
the production replay is the operator's in-person restore acting through each owner's
role (the production environment tool's `restore-evaluate`, Step 37).

- `integrity` reads every table of every owner schema, so every table is present with
  its rows readable, and every expected owner schema holds a table.
- `replay` applies each tombstoned erasure to the copy, as AccountAccess's erase leaves
  it: the account erased and inactive, its sessions ended, and every row of the owner's
  personal data removed from every owner schema, together with the rows that reach the
  owner only through one of those rows (an enrolment's recovery codes, a challenge's
  delivery; `dependents`). AccountAccess's and the owners' own
  records of the erasure (`ERASURE_EVIDENCE`, and every owner's receipts) stay, as they
  do in the live service.
- `surviving` counts the tombstoned owners the copy would revive: an account not erased,
  or any personal-data row left. A verification passes only at zero (BR4.5).
"""

from __future__ import annotations

from collections.abc import Iterable
from uuid import UUID

import psycopg
from psycopg import sql

OWNER_COLUMNS = ("account_id", "owner_id")
# What erasure keeps in the live service: AccountAccess's restriction, lifecycle and
# receipt records and the owners' own erasure boundaries (U2's erase); every owner's
# `receipt` table holds digests and outcomes only.
ERASURE_EVIDENCE = frozenset({
    "accounts.account", "accounts.current_restriction", "accounts.lifecycle",
    "accounts.lifecycle_request", "accounts.control_receipt", "accounts.consent_obligation",
    "assistance.erased_admission", "library.restriction", "library.history_boundary",
    "personalization.reset_responsibility", "discovery.owner_admission",
})
MAX_PASSES = 8
SYSTEM = ("pg_catalog", "information_schema", "public")


def _tables(conn) -> list[tuple[str, str]]:
    return [tuple(row) for row in conn.execute(
        "SELECT n.nspname,c.relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
        "WHERE c.relkind IN ('r','p') AND n.nspname <> ALL(%s) AND n.nspname NOT LIKE 'pg\\_%%' "
        "ORDER BY 1,2", (list(SYSTEM),),
    ).fetchall()]


def integrity(conn, expected_schemas: Iterable[str] = ()) -> dict:
    """Every table present with its rows readable; every expected schema holds one."""
    tables = _tables(conn)
    rows = 0
    for schema, table in tables:
        rows += conn.execute(sql.SQL("SELECT count(*) FROM {}.{}").format(
            sql.Identifier(schema), sql.Identifier(table))).fetchone()[0]
    present = {schema for schema, _ in tables}
    missing = sorted(set(expected_schemas) - present)
    return {"integrity": "passed" if tables and not missing else "failed",
            "tables": len(tables), "rows": rows, "missingSchemas": missing}


def personal_columns(conn) -> list[tuple[str, str, str]]:
    """Every owner-identity column of the personal-data tables."""
    found = conn.execute(
        "SELECT c.table_schema,c.table_name,c.column_name FROM information_schema.columns c "
        "JOIN information_schema.tables t ON t.table_schema=c.table_schema AND "
        "t.table_name=c.table_name AND t.table_type='BASE TABLE' "
        "WHERE c.column_name = ANY(%s) AND c.data_type='uuid' AND c.table_schema <> ALL(%s) "
        "ORDER BY 1,2,3", (list(OWNER_COLUMNS), list(SYSTEM)),
    ).fetchall()
    return [
        (schema, table, column) for schema, table, column in found
        if f"{schema}.{table}" not in ERASURE_EVIDENCE and table != "receipt"
    ]


def dependents(conn) -> dict[tuple[str, str], list[tuple[str, str, str, str]]]:
    """For each table, the single-column foreign keys into it from tables that carry no
    owner column (an MFA enrolment's recovery codes, a challenge's delivery): rows whose
    owner is only reachable through the row they reference. Each entry is
    `(schema, table, column, referenced column)` of the referencing table."""
    owned = {(schema, table) for schema, table, _ in personal_columns(conn)}
    found: dict[tuple[str, str], list[tuple[str, str, str, str]]] = {}
    for parent_schema, parent, schema, table, column, referenced in conn.execute(
        "SELECT pn.nspname,pc.relname,dn.nspname,dc.relname,da.attname,pa.attname "
        "FROM pg_constraint co JOIN pg_class dc ON dc.oid=co.conrelid "
        "JOIN pg_namespace dn ON dn.oid=dc.relnamespace "
        "JOIN pg_class pc ON pc.oid=co.confrelid JOIN pg_namespace pn ON pn.oid=pc.relnamespace "
        "JOIN pg_attribute da ON da.attrelid=co.conrelid AND da.attnum=co.conkey[1] "
        "JOIN pg_attribute pa ON pa.attrelid=co.confrelid AND pa.attnum=co.confkey[1] "
        "WHERE co.contype='f' AND cardinality(co.conkey)=1 ORDER BY 1,2,3,4,5"
    ).fetchall():
        dependent = f"{schema}.{table}"
        if (schema, table) in owned or dependent in ERASURE_EVIDENCE or table == "receipt":
            continue
        found.setdefault((parent_schema, parent), []).append(
            (schema, table, column, referenced))
    return found


def _remove_dependents(conn, graph, schema: str, table: str, where: sql.Composable,
                       owners: list[UUID], depth: int = 0) -> int:
    """Remove the rows that reach the owner only through `schema.table`'s rows selected
    by `where` (one `%s`, the owners), deepest first."""
    removed = 0
    for child_schema, child, child_column, referenced in graph.get((schema, table), []):
        if depth >= MAX_PASSES:
            raise RuntimeError("tombstone replay found a dependency chain beyond its bound")
        selected = sql.SQL("{} IN (SELECT {} FROM {}.{} WHERE {})").format(
            sql.Identifier(child_column), sql.Identifier(referenced),
            sql.Identifier(schema), sql.Identifier(table), where)
        removed += _remove_dependents(conn, graph, child_schema, child, selected, owners,
                                      depth + 1)
        removed += conn.execute(sql.SQL("DELETE FROM {}.{} WHERE {}").format(
            sql.Identifier(child_schema), sql.Identifier(child), selected), (owners,)).rowcount
    return removed


def _accounts(values: Iterable) -> list[UUID]:
    return sorted({UUID(str(value)) for value in values})


def _has_accounts(conn) -> bool:
    return conn.execute("SELECT to_regclass('accounts.account')").fetchone()[0] is not None


def replay(conn, accounts: Iterable) -> dict:
    """Apply each tombstoned erasure to the copy; a row a foreign key still holds is
    removed in a later pass, once the rows that reference it are gone."""
    owners = _accounts(accounts)
    if not owners:
        return {"replayed": 0, "removedRows": 0}
    removed, pending, graph = 0, personal_columns(conn), dependents(conn)
    for _ in range(MAX_PASSES):
        blocked = []
        for schema, table, column in pending:
            try:
                with conn.transaction():
                    removed += _remove_dependents(
                        conn, graph, schema, table,
                        sql.SQL("{} = ANY(%s)").format(sql.Identifier(column)), owners)
                    removed += conn.execute(sql.SQL("DELETE FROM {}.{} WHERE {} = ANY(%s)").format(
                        sql.Identifier(schema), sql.Identifier(table), sql.Identifier(column)),
                        (owners,)).rowcount
            except psycopg.errors.ForeignKeyViolation:
                blocked.append((schema, table, column))
        if not blocked:
            break
        pending = blocked
    else:
        raise RuntimeError("tombstone replay could not remove every personal row")
    if _has_accounts(conn):
        conn.execute("UPDATE accounts.account SET active=false,lifecycle_state='erased' "
                     "WHERE id = ANY(%s) AND (active OR lifecycle_state<>'erased')", (owners,))
    return {"replayed": len(owners), "removedRows": removed}


def surviving(conn, accounts: Iterable) -> int:
    """The tombstoned owners the copy would revive."""
    owners = _accounts(accounts)
    if not owners:
        return 0
    alive: set[UUID] = set()
    if _has_accounts(conn):
        alive |= {row[0] for row in conn.execute(
            "SELECT id FROM accounts.account WHERE id = ANY(%s) AND "
            "(active OR lifecycle_state<>'erased')", (owners,)).fetchall()}
    for schema, table, column in personal_columns(conn):
        alive |= {row[0] for row in conn.execute(sql.SQL(
            "SELECT DISTINCT {col} FROM {}.{} WHERE {col} = ANY(%s)").format(
            sql.Identifier(schema), sql.Identifier(table), col=sql.Identifier(column)),
            (owners,)).fetchall()}
    return len(alive)
