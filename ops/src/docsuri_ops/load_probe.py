"""Concrete DependencyProbe for PostgreSQL read-side state snapshots.

Usage:
    python -m docsuri_ops.load_probe \
        --host 127.0.0.1 --port 5432 --database rem1 --user r1_reader \
        --tables runs,ledger,checkpoint,audit \
        --output snapshot.json

The output is a JSON object with table names as keys and row counts as values,
suitable for --dependency-state and --dependency-state-before in load_acceptance.py.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import psycopg

from .load_observation import DependencyProbe


class PostgresDependencyProbe(DependencyProbe):
    """Queries PostgreSQL and returns row counts for the configured tables."""

    def __init__(
        self,
        *,
        host: str,
        port: int,
        database: str,
        user: str,
        tables: tuple[str, ...],
        password: str | None = None,
        sslmode: str = "verify-full",
        sslrootcert: str | None = None,
    ) -> None:
        self._dsn = f"host={host} port={port} dbname={database} user={user} sslmode={sslmode}"
        if password:
            self._dsn += f" password={password}"
        if sslrootcert:
            self._dsn += f" sslrootcert={sslrootcert}"
        self._tables = tables

    def counts(self) -> dict[str, int]:
        result: dict[str, int] = {}
        with psycopg.connect(self._dsn, autocommit=True) as conn:
            for table in self._tables:
                # Use parameterized query to avoid injection; table name is from trusted config
                row = conn.execute(
                    f'SELECT count(*) FROM "{table}"'
                ).fetchone()
                result[table] = int(row[0]) if row else 0
        return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5432)
    parser.add_argument("--database", required=True)
    parser.add_argument("--user", required=True)
    parser.add_argument("--password", help="if omitted, reads from stdin (one line)")
    parser.add_argument("--tables", required=True,
                        help="comma-separated list of table names to count")
    parser.add_argument("--sslmode", default="verify-full",
                        choices=(
                            "disable", "allow", "prefer", "require",
                            "verify-ca", "verify-full",
                        ))
    parser.add_argument("--sslrootcert", help="path to CA cert for verify-ca/verify-full")
    parser.add_argument("--output", type=Path, required=True,
                        help="write snapshot JSON here")
    args = parser.parse_args(argv)

    password = args.password
    if password is None:
        line = sys.stdin.readline()
        if not line:
            print("error: no password on stdin", file=sys.stderr)
            return 2
        password = line.rstrip("\n")

    probe = PostgresDependencyProbe(
        host=args.host,
        port=args.port,
        database=args.database,
        user=args.user,
        tables=tuple(t.strip() for t in args.tables.split(",") if t.strip()),
        password=password,
        sslmode=args.sslmode,
        sslrootcert=args.sslrootcert,
    )

    snapshot = probe.counts()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with os.fdopen(os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as f:
        json.dump(snapshot, f, indent=2, sort_keys=True)
        f.write("\n")
    print(json.dumps(snapshot, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
