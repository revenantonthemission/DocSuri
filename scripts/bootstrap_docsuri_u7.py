"""Install the U7 PlatformControl schema and roles in the owned disposable DB.

Only inside the positively identified disposable U7 database: creates the
non-login schema owner and the bounded runtime/provisioner login roles, installs
the guard functions, seeds the retained-inventory vocabulary and the synthetic
fixture targets, and records the inventory identity.
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import stat
import sys
from pathlib import Path

import psycopg
from psycopg import sql
from verify_docsuri_u7 import (
    FIXTURE_TARGETS,
    ROOT,
    RUN,
    Refused,
    load_manifest,
    private_json,
    resource_matches,
)

sys.path.insert(0, str(ROOT))
from docsuri_ops.platform_control import OWNER_ROLE, PROVISIONER_ROLE, RUNTIME_ROLE
from docsuri_ops.platform_control.inventory import load_inventory

DATABASE = "docsuri_u7"


def read_private(path: Path) -> dict:
    info = path.lstat()
    if (
        path.parent != RUN
        or path.is_symlink()
        or info.st_uid != os.getuid()
        or stat.S_IMODE(info.st_mode) != 0o600
    ):
        raise Refused("private credential identity mismatch")
    return json.loads(path.read_bytes())


def inventory_hash() -> str:
    path = ROOT / "ops/src/docsuri_ops/platform_control/inventory.json"
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _credentials(path: Path, run_id: str, role: str) -> dict:
    if path.exists():
        value = read_private(path)
        if value.get("runId") != run_id or value.get("role") != role:
            raise Refused("existing credential record belongs to another environment")
        return value
    value = {"runId": run_id, "role": role, "password": secrets.token_urlsafe(32)}
    private_json(path, value)
    return value


def migrate_schema(conn) -> None:
    """Idempotent, additive-only migrations for an already-installed schema.

    Signature changes are applied by dropping the superseded overloads before the
    idempotent ``schema.sql`` is re-applied, so no stale unscoped function can
    survive a migration.
    """
    for signature in (
        "platform_control.read_receipt(uuid)",
        "platform_control.latest_evidence(text)",
        "platform_control.list_unresolved()",
        "platform_control.status_counts()",
    ):
        conn.execute(f"DROP FUNCTION IF EXISTS {signature}")
    conn.execute(
        "ALTER TABLE platform_control.protocol DROP CONSTRAINT IF EXISTS protocol_effect_kind_check"
    )
    conn.execute(
        "ALTER TABLE platform_control.protocol ADD CONSTRAINT protocol_effect_kind_check "
        "CHECK (effect_kind IN ('file-write','file-probe','credential-presence'))"
    )


def seed_protocols(conn) -> None:
    inventory = load_inventory()
    for protocol in inventory.protocols:
        row = protocol.as_row()
        conn.execute(
            """
            INSERT INTO platform_control.protocol
                (name, disposition, authority_class, max_age_seconds, deadline_seconds,
                 effect_kind, native_verified, consumer_impact)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (name) DO UPDATE
              SET disposition=excluded.disposition, authority_class=excluded.authority_class,
                  max_age_seconds=excluded.max_age_seconds, deadline_seconds=excluded.deadline_seconds,
                  effect_kind=excluded.effect_kind, native_verified=excluded.native_verified,
                  consumer_impact=excluded.consumer_impact
            """,
            (
                row["name"],
                row["disposition"],
                row["authority_class"],
                row["max_age_seconds"],
                row["deadline_seconds"],
                row["effect_kind"],
                row["native_verified"],
                row["consumer_impact"],
            ),
        )


def seed_targets(conn) -> None:
    for target in FIXTURE_TARGETS:
        conn.execute(
            "INSERT INTO platform_control.target(target_id) VALUES (%s) ON CONFLICT DO NOTHING",
            (target,),
        )


def bootstrap() -> dict:
    manifest = load_manifest(RUN / "environment.json")
    for kind, key in (("container", "container"), ("volume", "volume")):
        if not resource_matches(kind, manifest[key], manifest["runId"]):
            raise Refused("owned container or volume identity missing")
    admin = read_private(RUN / "migration-credentials.json")
    runtime = _credentials(RUN / "runtime-credentials.json", manifest["runId"], "runtime")
    provisioner = _credentials(
        RUN / "provisioner-credentials.json", manifest["runId"], "provisioner"
    )
    with psycopg.connect(
        host="127.0.0.1",
        port=manifest["databasePort"],
        dbname=DATABASE,
        user="postgres",
        password=admin["databaseAdminPassword"],
        connect_timeout=3,
    ) as conn:
        if conn.execute("SHOW server_version").fetchone()[0].split(".")[0] != "16":
            raise Refused("selected PostgreSQL version not present")
        existing = conn.execute(
            "SELECT to_regclass('public.docsuri_u7_identity')"
        ).fetchone()[0]
        if existing:
            row = conn.execute(
                "SELECT run_id, inventory_hash FROM public.docsuri_u7_identity"
            ).fetchone()
            if row is None or row[0] != manifest["runId"]:
                raise Refused("database identity mismatch; adoption refused")
            # Idempotent U7-owned migration: re-seed the retained-inventory
            # vocabulary and synthetic targets (additive/upsert only) and advance
            # the recorded inventory marker. No destructive DDL is ever applied,
            # so a rollback never destroys receipts.
            current = inventory_hash()
            conn.execute("SET LOCAL ROLE " + OWNER_ROLE)
            migrate_schema(conn)
            conn.execute(
                (ROOT / "ops/src/docsuri_ops/platform_control/schema.sql").read_text(),
                prepare=False,
            )
            seed_protocols(conn)
            seed_targets(conn)
            conn.execute("RESET ROLE")
            conn.execute(
                "UPDATE public.docsuri_u7_identity SET inventory_hash = %s WHERE singleton",
                (current,),
            )
            conn.commit()
            state = "verified" if row[1] == current else "migrated"
            return {"schemaState": state, "inventoryHash": current, "previousInventoryHash": row[1]}

        conn.execute(
            sql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC").format(sql.Identifier(DATABASE))
        )
        conn.execute("REVOKE ALL ON SCHEMA public FROM PUBLIC")
        conn.execute(
            "CREATE TABLE public.docsuri_u7_identity (singleton boolean PRIMARY KEY CHECK(singleton), run_id text NOT NULL, inventory_hash text NOT NULL)"
        )
        for role, login, password in (
            (OWNER_ROLE, False, None),
            (RUNTIME_ROLE, True, runtime["password"]),
            (PROVISIONER_ROLE, True, provisioner["password"]),
        ):
            statement = sql.SQL(
                "CREATE ROLE {} {} NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS"
            ).format(sql.Identifier(role), sql.SQL("LOGIN" if login else "NOLOGIN"))
            if password is not None:
                statement = statement + sql.SQL(" CONNECTION LIMIT 4 PASSWORD {}").format(
                    sql.Literal(password)
                )
            conn.execute(statement)
            conn.execute(
                sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                    sql.Identifier(DATABASE), sql.Identifier(role)
                )
            )
        conn.execute(
            sql.SQL("CREATE SCHEMA platform_control AUTHORIZATION {}").format(
                sql.Identifier(OWNER_ROLE)
            )
        )
        conn.execute(sql.SQL("SET LOCAL ROLE {}").format(sql.Identifier(OWNER_ROLE)))
        conn.execute(
            (ROOT / "ops/src/docsuri_ops/platform_control/schema.sql").read_text(),
            prepare=False,
        )
        seed_protocols(conn)
        seed_targets(conn)
        conn.execute("RESET ROLE")
        conn.execute(
            "INSERT INTO public.docsuri_u7_identity(singleton, run_id, inventory_hash) VALUES (true, %s, %s)",
            (manifest["runId"], inventory_hash()),
        )
        conn.commit()
    return {"schemaState": "installed", "inventoryHash": inventory_hash()}


def main() -> int:
    try:
        print(json.dumps(bootstrap(), sort_keys=True))
        return 0
    except (Refused, OSError, ValueError, psycopg.Error) as exc:
        print(
            f"Bootstrap refused: {type(exc).__name__}; sqlstate={getattr(exc, 'sqlstate', None)}",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
