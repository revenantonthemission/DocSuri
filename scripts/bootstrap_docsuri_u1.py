"""Install owner schemas only inside the positively identified disposable U1 DB."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import stat
import sys
from pathlib import Path

import psycopg
from psycopg import sql
from verify_docsuri_u1 import (
    ROOT,
    RUN,
    Refused,
    load_manifest,
    private_json,
    resource_matches,
)

SCHEMAS = {
    "accounts": "backend/modules/accounts/local_schema.sql",
    "corpus": "backend/modules/corpus/local_schema.sql",
    "library": "backend/modules/library/local_schema.sql",
    "personalization": "backend/modules/personalization/local_schema.sql",
    "discovery": "backend/modules/discovery/local_schema.sql",
    "usage": "backend/modules/plans/local_schema.sql",
    "assistance": "backend/modules/summarization/local_schema.sql",
    "operations": "ops/src/docsuri_ops/local_schema.sql",
}
AMENDMENTS = (
    ("corpus", "backend/modules/corpus/local_binding_guards.sql"),
    ("assistance", "backend/modules/summarization/local_binding_guards.sql"),
    ("library", "backend/modules/library/local_operations.sql"),
    ("assistance", "backend/modules/summarization/local_glossary.sql"),
    ("corpus", "backend/modules/corpus/local_reference_guard.sql"),
    ("library", "backend/modules/library/local_reference_guard.sql"),
    ("accounts", "backend/modules/accounts/local_execution_guard.sql"),
    ("assistance", "backend/modules/summarization/local_claim_guards.sql"),
    ("accounts", "backend/modules/accounts/local_entry.sql"),
)


def amend(conn, manifest: dict, source_hashes: dict) -> dict:
    """Apply only explicit append-only schema amendments, within the same DB identity."""
    row = conn.execute(
        "SELECT run_id,schema_hashes FROM public.docsuri_local_identity FOR UPDATE"
    ).fetchone()
    if row is None or row[0] != manifest["runId"]:
        raise Refused("migration identity mismatch")
    known = row[1]
    if any(known.get(name) != value for name, value in source_hashes.items()):
        raise Refused("existing base schema bytes differ; new migration required")
    for owner, path in AMENDMENTS:
        value = hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
        if path in known:
            if known[path] != value:
                raise Refused("previously applied amendment changed")
            continue
        conn.execute(
            sql.SQL("SET LOCAL ROLE {}").format(
                sql.Identifier(f"docsuri_{owner}_owner")
            )
        )
        conn.execute((ROOT / path).read_text(), prepare=False)
        conn.execute("RESET ROLE")
        known[path] = value
    conn.execute(
        "UPDATE public.docsuri_local_identity SET schema_hashes=%s WHERE singleton",
        (psycopg.types.json.Jsonb(known),),
    )
    return known


def read_private(path: Path) -> dict:
    info = path.lstat()
    if (
        path.parent != RUN
        or path.is_symlink()
        or info.st_uid != os.getuid()
        or stat.S_IMODE(info.st_mode) != 0o600
    ):
        raise Refused("private credential identity mismatch")
    return json.loads(path.read_text())


def bootstrap() -> dict:
    manifest = load_manifest(RUN / "environment.json")
    if not resource_matches("container", manifest["container"], manifest["runId"]):
        raise Refused("owned container identity missing")
    if not resource_matches("volume", manifest["volume"], manifest["runId"]):
        raise Refused("owned persistent volume identity missing")
    source_hashes = {
        name: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
        for name, path in SCHEMAS.items()
    }
    admin = read_private(RUN / "migration-credentials.json")
    credentials_path = RUN / "owner-credentials.json"
    if credentials_path.exists():
        credentials = read_private(credentials_path)
        if credentials.get("runId") != manifest["runId"]:
            raise Refused("owner credentials belong to another environment")
    else:
        credentials = {
            "runId": manifest["runId"],
            "roles": {name: secrets.token_urlsafe(32) for name in SCHEMAS},
        }
        private_json(credentials_path, credentials)
    with psycopg.connect(
        host="127.0.0.1",
        port=manifest["databasePort"],
        dbname="docsuri_u1",
        user="postgres",
        password=admin["databaseAdminPassword"],
        connect_timeout=3,
    ) as conn:
        if conn.execute("SHOW server_version").fetchone()[0].split()[0] != "16.15":
            raise Refused("selected PostgreSQL version not present")
        if conn.execute("SELECT current_database()").fetchone()[0] != "docsuri_u1":
            raise Refused("database identity mismatch")
        existing = conn.execute(
            "SELECT to_regclass('public.docsuri_local_identity')"
        ).fetchone()[0]
        if existing:
            hashes = amend(conn, manifest, source_hashes)
            return {
                "schemaState": "verified-with-explicit-amendments",
                "schemaHashes": hashes,
            }
        found = conn.execute(
            "SELECT nspname FROM pg_namespace WHERE nspname NOT LIKE 'pg_%' AND nspname NOT IN ('public','information_schema')"
        ).fetchall()
        if found:
            raise Refused(
                "database contains unrecognized schemas; no migration attempted"
            )
        conn.execute("REVOKE ALL ON DATABASE docsuri_u1 FROM PUBLIC")
        conn.execute("REVOKE ALL ON SCHEMA public FROM PUBLIC")
        conn.execute(
            "CREATE TABLE public.docsuri_local_identity (singleton boolean PRIMARY KEY CHECK(singleton), run_id text NOT NULL, schema_hashes jsonb NOT NULL)"
        )
        conn.execute(
            "INSERT INTO public.docsuri_local_identity VALUES (true,%s,%s)",
            (manifest["runId"], psycopg.types.json.Jsonb(source_hashes)),
        )
        for name, path in SCHEMAS.items():
            owner = sql.Identifier(f"docsuri_{name}_owner")
            runtime = sql.Identifier(f"docsuri_{name}")
            schema = sql.Identifier(name)
            conn.execute(
                sql.SQL(
                    "CREATE ROLE {} NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS"
                ).format(owner)
            )
            conn.execute(
                sql.SQL(
                    "CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS CONNECTION LIMIT 2 PASSWORD {}"
                ).format(runtime, sql.Literal(credentials["roles"][name]))
            )
            conn.execute(
                sql.SQL("GRANT CONNECT ON DATABASE docsuri_u1 TO {}").format(runtime)
            )
            conn.execute(
                sql.SQL("CREATE SCHEMA {} AUTHORIZATION {}").format(schema, owner)
            )
            conn.execute(sql.SQL("SET LOCAL ROLE {}").format(owner))
            conn.execute(
                sql.SQL(
                    "ALTER DEFAULT PRIVILEGES IN SCHEMA {} REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC"
                ).format(schema)
            )
            conn.execute((ROOT / path).read_text(), prepare=False)
            conn.execute(
                sql.SQL(
                    "CREATE TABLE {}.receipt (account_id uuid NOT NULL, kind text NOT NULL, key uuid NOT NULL, intent_hash text NOT NULL CHECK(intent_hash ~ {}), outcome jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT clock_timestamp(), PRIMARY KEY(account_id,kind,key))"
                ).format(schema, sql.Literal("^[0-9a-f]{64}$"))
            )
            conn.execute(
                sql.SQL("GRANT USAGE ON SCHEMA {} TO {}").format(schema, runtime)
            )
            conn.execute(
                sql.SQL(
                    "GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA {} TO {}"
                ).format(schema, runtime)
            )
            conn.execute(
                sql.SQL("REVOKE UPDATE,DELETE ON {}.receipt FROM {}").format(
                    schema, runtime
                )
            )
            conn.execute(
                sql.SQL(
                    "GRANT USAGE,SELECT ON ALL SEQUENCES IN SCHEMA {} TO {}"
                ).format(schema, runtime)
            )
            conn.execute(
                sql.SQL("GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA {} TO {}").format(
                    schema, runtime
                )
            )
            conn.execute("RESET ROLE")
            conn.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(runtime))
            conn.execute(
                sql.SQL("GRANT SELECT ON public.docsuri_local_identity TO {}").format(
                    runtime
                )
            )
        for name in ("library", "personalization", "discovery", "usage", "assistance"):
            runtime = sql.Identifier(f"docsuri_{name}")
            conn.execute(
                sql.SQL("GRANT USAGE ON SCHEMA accounts TO {}").format(runtime)
            )
            conn.execute(
                sql.SQL(
                    "GRANT EXECUTE ON FUNCTION accounts.guard_session(uuid,uuid,text) TO {}"
                ).format(runtime)
            )
        for name in ("library", "discovery", "assistance"):
            runtime = sql.Identifier(f"docsuri_{name}")
            conn.execute(sql.SQL("GRANT USAGE ON SCHEMA corpus TO {}").format(runtime))
            conn.execute(
                sql.SQL(
                    "GRANT EXECUTE ON FUNCTION corpus.guard_version(text,text) TO {}"
                ).format(runtime)
            )
        conn.execute(
            "GRANT EXECUTE ON FUNCTION accounts.guard_execution(uuid,uuid) TO docsuri_assistance"
        )
        conn.execute(
            "GRANT SELECT ON corpus.paper,corpus.version,corpus.projection TO docsuri_discovery"
        )
        hashes = amend(conn, manifest, source_hashes)
    return {"schemaState": "installed", "schemaHashes": hashes}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rotate-runtime-credentials", action="store_true")
    args = parser.parse_args()
    try:
        result = bootstrap()
        if args.rotate_runtime_credentials:
            manifest = load_manifest(RUN / "environment.json")
            administrator = read_private(RUN / "migration-credentials.json")
            replacement = {
                "runId": manifest["runId"],
                "roles": {name: secrets.token_urlsafe(32) for name in SCHEMAS},
            }
            with psycopg.connect(
                host="127.0.0.1",
                port=manifest["databasePort"],
                dbname="docsuri_u1",
                user="postgres",
                password=administrator["databaseAdminPassword"],
                connect_timeout=3,
            ) as conn:
                identity = conn.execute(
                    "SELECT run_id FROM public.docsuri_local_identity"
                ).fetchone()[0]
                if identity != manifest["runId"]:
                    raise Refused("rotation database identity mismatch")
                for name, password in replacement["roles"].items():
                    conn.execute(
                        sql.SQL("ALTER ROLE {} PASSWORD {}").format(
                            sql.Identifier("docsuri_" + name), sql.Literal(password)
                        )
                    )
            private_json(RUN / "owner-credentials.json", replacement)
            result = {"runtimeCredentials": "rotated", "roles": len(SCHEMAS)}
        print(json.dumps(result, sort_keys=True))
        return 0
    except (Refused, OSError, ValueError, psycopg.Error) as exc:
        # SQL errors may contain data/parameters: emit only class and SQLSTATE.
        print(
            f"Bootstrap refused: {type(exc).__name__}; sqlstate={getattr(exc, 'sqlstate', None)}",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
