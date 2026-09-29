"""F08: read-only inspection and explicitly authorized, transaction-bound migration steps.

Startup/check never creates a ledger. Historical filename-only rows need reconciliation:
matching a name does NOT prove which owner or SQL bytes executed. Production apply requires
a current-authority guard supplied by the REM-1 composition; the CLI does not mint one.
"""

from __future__ import annotations

import hashlib
import re
from contextlib import AbstractContextManager
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .registry import MigrationDefinition, for_paths


class MigrationBlocked(RuntimeError):
    pass


def _atomic_sql(payload: bytes) -> str:
    sql = payload.decode("utf-8")
    # Conservative admission of developer-owned registry scripts: these operations can escape
    # the step transaction or create external effects. Ignore full-line comments for admission;
    # execute the original bytes unchanged. Ambiguous/complex scripts require explicit review.
    executable = "\n".join(line for line in sql.splitlines() if not line.lstrip().startswith("--"))
    if re.search(
        r"\b(BEGIN|START\s+TRANSACTION|COMMIT|ROLLBACK|END|VACUUM|CONCURRENTLY|"
        r"COPY|CALL|DO|EXECUTE|SET\s+ROLE|CREATE\s+DATABASE|ALTER\s+SYSTEM)\b",
        executable,
        re.I,
    ):
        raise MigrationBlocked("script is not admitted as ATOMIC_STEP")
    return sql


class MigrationAuthority(Protocol):
    def guard(self, connection, identity: str, definition_digest: str) -> AbstractContextManager:
        """Must serialize current authority/revocation with this connection's COMMIT."""
        ...


@dataclass(frozen=True)
class Inspection:
    state: str
    pending: tuple[str, ...]
    changed: tuple[str, ...] = ()
    legacy: tuple[str, ...] = ()


_LEDGER = """
CREATE TABLE IF NOT EXISTS public._migrations_v2 (
    identity TEXT PRIMARY KEY,
    definition_digest TEXT NOT NULL,
    assurance TEXT NOT NULL CHECK (assurance IN ('VERIFIED_EXECUTION', 'ADOPTED_BASELINE')),
    receipt TEXT NOT NULL,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""


def _normalize_dsn(dsn: str) -> str:
    scheme, sep, rest = dsn.partition("://")
    return scheme.split("+", 1)[0] + sep + rest if sep and "+" in scheme else dsn


def _inspect(conn, specs: tuple[MigrationDefinition, ...]) -> Inspection:
    exists = conn.execute("SELECT to_regclass('public._migrations_v2')").fetchone()[0]
    records = {}
    if exists:
        records = dict(
            conn.execute("SELECT identity, definition_digest FROM public._migrations_v2").fetchall()
        )
    legacy_exists = conn.execute("SELECT to_regclass('public._migrations')").fetchone()[0]
    legacy = ()
    if legacy_exists:
        # Preserve all unresolved legacy rows, even if the same name appears in one source today.
        legacy = tuple(
            row[0]
            for row in conn.execute("SELECT name FROM public._migrations ORDER BY name").fetchall()
            if not (
                (matches := [s for s in specs if s.local_id == row[0]])
                and all(records.get(s.identity) == s.digest for s in matches)
            )
        )
    pending = tuple(s.identity for s in specs if s.identity not in records)
    changed = tuple(
        s.identity for s in specs if s.identity in records and records[s.identity] != s.digest
    )
    state = (
        "CHANGED_DEFINITION"
        if changed
        else "NEEDS_RECONCILIATION"
        if legacy
        else ("PENDING" if pending and exists else "UNINITIALIZED" if pending else "READY")
    )
    return Inspection(state, pending, changed, legacy)


def inspect_migrations(dsn: str, paths: list[str | Path] | None = None) -> Inspection:
    import psycopg

    specs = for_paths(paths)
    with psycopg.connect(
        _normalize_dsn(dsn),
        connect_timeout=1,
        options="-c statement_timeout=2000 -c default_transaction_read_only=on",
    ) as conn:
        return _inspect(conn, specs)


def pending_migrations(dsn: str, paths: list[str | Path] | None = None) -> list[str]:
    result = inspect_migrations(dsn, paths)
    if result.changed or result.legacy:
        raise MigrationBlocked(result.state)
    return list(result.pending)


def apply_migrations(
    dsn: str, paths: list[str | Path] | None = None, *, authority: MigrationAuthority | None = None
) -> list[str]:
    if authority is None:
        raise MigrationBlocked("explicit current-authority guard required")
    import psycopg

    specs = for_paths(paths)
    applied = []
    with psycopg.connect(
        _normalize_dsn(dsn),
        connect_timeout=1,
        autocommit=True,
        options="-c statement_timeout=300000 -c lock_timeout=5000",
    ) as conn:
        # Canonical database/schema lock, not a caller-controlled alias or per-module lock.
        locked = conn.execute("SELECT pg_try_advisory_lock(1380798032, 1)").fetchone()[0]
        if not locked:
            raise MigrationBlocked("another migration writer is active")
        try:
            status = _inspect(conn, specs)
            if status.changed or status.legacy:
                raise MigrationBlocked(status.state)
            if status.state == "UNINITIALIZED":
                existing = conn.execute("""SELECT tablename FROM pg_tables
                    WHERE schemaname='public' AND tablename NOT LIKE '\\_migrations%' ESCAPE '\\'
                    """).fetchall()
                if existing:
                    raise MigrationBlocked("existing schema needs explicit baseline reconciliation")
            bootstrap_digest = "sha256:" + hashlib.sha256(_LEDGER.encode()).hexdigest()
            with authority.guard(conn, "registry:bootstrap", bootstrap_digest) as finalization:
                with conn.transaction():
                    conn.execute(_LEDGER)
                    if finalization is not None:
                        finalization.before_commit()
            for spec in specs:
                row = conn.execute(
                    "SELECT definition_digest FROM public._migrations_v2 WHERE identity=%s",
                    (spec.identity,),
                ).fetchone()
                if row:
                    if row[0] != spec.digest:
                        raise MigrationBlocked("definition changed")
                    continue
                payload = spec.path.read_bytes()
                if "sha256:" + hashlib.sha256(payload).hexdigest() != spec.digest:
                    raise MigrationBlocked("script changed after planning")
                # Registry SQL is developer-owned immutable input; never taken from HTTP/CLI text.
                with authority.guard(conn, spec.identity, spec.digest) as finalization:
                    with conn.transaction():
                        conn.execute(_atomic_sql(payload))
                        conn.execute(
                            """INSERT INTO public._migrations_v2
                            (identity, definition_digest, assurance, receipt)
                            VALUES (%s,%s,'VERIFIED_EXECUTION',%s)""",
                            (spec.identity, spec.digest, f"migration:{spec.identity}"),
                        )
                        if finalization is not None:
                            finalization.before_commit()
                applied.append(spec.identity)
        finally:
            conn.execute("SELECT pg_advisory_unlock(1380798032, 1)")
    return applied


def adopt_baseline(
    dsn: str,
    *,
    identities: tuple[str, ...],
    receipt: str,
    verify_postconditions,
    authority: MigrationAuthority,
) -> tuple[str, ...]:
    """Explicit domain-verified adoption; never rewrites filename history as verified execution.

    Called only by protected composition with a reviewed postcondition checker and current
    authority. The checker observes the live target in this same transaction; it may not infer
    execution from an existing table name. No generic CLI flag issues an adoption authorization.
    """
    import psycopg

    selected = {s.identity: s for s in for_paths(None)}
    if not identities or len(set(identities)) != len(identities) or not receipt:
        raise MigrationBlocked("explicit adoption manifest and receipt required")
    if not set(identities) <= selected.keys():
        raise MigrationBlocked("unknown adoption identity")
    with psycopg.connect(
        _normalize_dsn(dsn),
        connect_timeout=1,
        autocommit=True,
        options="-c statement_timeout=300000 -c lock_timeout=5000",
    ) as conn:
        if not conn.execute("SELECT pg_try_advisory_lock(1380798032, 1)").fetchone()[0]:
            raise MigrationBlocked("another migration writer is active")
        try:
            with authority.guard(conn, "registry:adopt", receipt) as finalization:
                with conn.transaction():
                    conn.execute(_LEDGER)
                    for identity in identities:
                        spec = selected[identity]
                        if not verify_postconditions(conn, spec):
                            raise MigrationBlocked("domain postconditions not verified")
                        row = conn.execute(
                            "SELECT definition_digest FROM public._migrations_v2 WHERE identity=%s",
                            (identity,),
                        ).fetchone()
                        if row and row[0] != spec.digest:
                            raise MigrationBlocked("conflicting adopted definition")
                        if not row:
                            conn.execute(
                                """INSERT INTO public._migrations_v2
                                (identity, definition_digest, assurance, receipt)
                                VALUES (%s,%s,'ADOPTED_BASELINE',%s)""",
                                (identity, spec.digest, receipt),
                            )
                    if finalization is not None:
                        finalization.before_commit()
        finally:
            conn.execute("SELECT pg_advisory_unlock(1380798032, 1)")
    return identities
