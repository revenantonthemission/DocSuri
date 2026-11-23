"""The migration tool's wiring on the composed realm (U8 plan Step 31; BR8.11, BR10.2).

The realm stands in for the arrangement: its own PostgreSQL instance holds the run's
rehearsal and import databases, the realm driver runs the same backup agent against a
folder standing in for the volume, and PlatformControl's realm store binds every
disposal. What production does through the production environment tool (Step 37),
the realm does here through its own administrator login, which never touches v1:

- `create_rehearsal`: a new rehearsal database, owned by the disposable-databases role,
  with the composed realm's schema and the rows its chain seeds, copied whole from the
  realm's private composed template (`docsuri_u8_template`, which `migrate` keeps on the
  chain), its owners' connection grants and the realm's identity row, so the owners'
  imports and v2's workers run on it exactly as on a database the chain made;
- `create_import` and `restore_import`: a fresh import database owned by the same role,
  into which the snapshot's dump is restored as that role (`--no-owner`);
- `import_reader`: the scheduler's stand-in login reads the import database, which it
  holds through the disposable-databases role;
- `owners_for`: the four owners' import operations on the rehearsal database, with
  CorpusContent's production limits and the realm's deterministic stand-in embedder.

v1's search index and object store are read through the readers the caller passes
(`index`, `objects`): the synthetic v1's stand-ins in the realm's tests, v1's own stores
in production.
"""

from __future__ import annotations

import dataclasses
import json
import re
import subprocess
from collections.abc import Callable
from contextlib import contextmanager
from pathlib import Path

from docsuri_ops.platform_control.profile import private_bytes

NAME = re.compile(r"docsuri_[a-z0-9]{2,8}_(rehearsal|import)_[0-9a-f]{12}")
PRODUCTION = re.compile(r"docsuri_[a-z0-9]{2,8}")
SOURCE = "docsuri_u8"
TEMPLATE = "docsuri_u8_template"
DISPOSABLE = "docsuri_disposable"
SECONDS = 600


def _admin_password(run_root: Path) -> str:
    return json.loads(private_bytes(run_root / "migration-credentials.json"))[
        "databaseAdminPassword"]


def _connect(port: int, user: str, password: str, database: str, **options):
    import psycopg

    return psycopg.connect(host="127.0.0.1", port=port, dbname=database, user=user,
                           password=password, require_auth="scram-sha-256",
                           connect_timeout=5, **options)


def docker_environment() -> dict[str, str]:
    """The environment of the realm's `docker` calls: PATH, HOME and DOCKER_CONFIG, and
    DOCKER_HOST when this process holds it, so the calls reach the Docker the caller
    chose (U8 plan L1-76). Nothing else of this process's environment passes."""
    import os

    return {key: os.environ[key] for key in ("PATH", "HOME", "DOCKER_CONFIG", "DOCKER_HOST")
            if key in os.environ}


def _docker(*args: str, stdin=None, seconds: int = SECONDS) -> subprocess.CompletedProcess:
    return subprocess.run(["docker", *args], stdin=stdin, capture_output=True,
                          env=docker_environment(), timeout=seconds, check=False)


@dataclasses.dataclass
class RealmDatabases:
    run_root: Path
    port: int
    container: str
    run_id: str

    @classmethod
    def for_realm(cls, run_root: Path) -> RealmDatabases:
        value = json.loads(private_bytes(run_root / "environment.json"))
        return cls(run_root, int(value["databasePort"]), value["container"], value["runId"])

    def admin(self, database: str = "postgres"):
        return _connect(self.port, "postgres", _admin_password(self.run_root), database,
                        autocommit=True)

    def _require(self, name: str, kind: str) -> None:
        match = NAME.fullmatch(name)
        if match is None or match.group(1) != kind:
            raise ValueError("database name outside its disposable pattern")

    def create_rehearsal(self, name: str) -> None:
        """A new rehearsal database, created again in full when an earlier create of the
        same name did not confirm (its answer lost, or its grants or schema copy cut
        short). The callers record the name before they ask and ask again only while the
        creation is unconfirmed, so nothing uses that database yet; here the schema copy
        is not one step, so a database of this name owned by the disposable-databases
        role is dropped and made again. One owned by any other role is refused."""
        from psycopg import sql

        self._require(name, "rehearsal")
        ident = sql.Identifier(name)
        with self.admin() as conn:
            owner = conn.execute("SELECT pg_get_userbyid(datdba) FROM pg_database "
                                 "WHERE datname=%s", (name,)).fetchone()
            if owner is not None:
                if owner[0] != DISPOSABLE:
                    raise ValueError("rehearsal database not the disposable role's")
                conn.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(ident))
            conn.execute(sql.SQL("CREATE DATABASE {} OWNER {} TEMPLATE template1").format(
                ident, sql.Identifier(DISPOSABLE)))
            conn.execute(sql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC").format(ident))
            for (role,) in conn.execute(
                "SELECT r.rolname FROM pg_database d, aclexplode(d.datacl) a JOIN pg_roles r "
                "ON r.oid=a.grantee WHERE d.datname=%s AND a.privilege_type='CONNECT'",
                (SOURCE,)).fetchall():
                conn.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                    ident, sql.Identifier(role)))
        self._copy_schema(name)

    def _copy_schema(self, name: str) -> None:
        """The composed realm's schema and the rows the composed chain seeds (singleton
        cursors and sequences), with its identity row: a whole copy of the realm's private
        composed template (`docsuri_u8_template`, which the realm's `migrate` keeps on the
        chain and no test writes), never of `docsuri_u8`, whose rows tests change. Refused
        if the template is not on `docsuri_u8`'s chain."""
        with self.admin(SOURCE) as source:
            expected = source.execute(
                "SELECT run_id,schema_hashes FROM public.docsuri_local_identity").fetchone()
        with self.admin(TEMPLATE) as template:
            found = template.execute(
                "SELECT run_id,schema_hashes FROM public.docsuri_local_identity").fetchone()
        if found != expected:
            raise RuntimeError("composed-template-not-current")
        piped = _docker("exec", self.container, "sh", "-c",
                        f"pg_dump -U postgres {TEMPLATE} | "
                        f"psql -U postgres -v ON_ERROR_STOP=1 -q -d {name}")
        if piped.returncode != 0:
            raise RuntimeError("schema-copy-failed")

    def copy_composed_schema(self, database: str) -> None:
        """The realm's composed template, copied whole into a database the caller created
        (your decision of 2026-10-24): only the production stand-in's own rehearsal copy
        qualifies, so the name must follow production's rehearsal pattern
        (`docsuri_v2_rehearsal_<12 hex>`). Only the tests' production stand-in calls it."""
        from docsuri_ops.arrangement.paths import PRODUCTION_DATABASES

        if PRODUCTION_DATABASES.kind_of(database) != "rehearsal":
            raise ValueError("only a production rehearsal database takes the composed schema")
        self._copy_schema(database)

    def prepare_production(self, name: str) -> None:
        """A final run's target: the production stand-in just recreated empty, given the
        composed schema. Only a journey's own production stand-in qualifies (a database
        of its own, under the production or the rehearsal naming), never `docsuri_u8`
        itself; its empty schemas and identity row from the recreate's base are replaced
        by the copy."""
        from psycopg import sql

        own = PRODUCTION.fullmatch(name) is not None or (
            NAME.fullmatch(name) is not None and NAME.fullmatch(name).group(1) == "rehearsal")
        if not own or name == SOURCE:
            raise ValueError("only a journey's production stand-in is prepared here")
        with self.admin(name) as conn:
            if conn.execute("SELECT count(*) FROM pg_class c JOIN pg_namespace n ON "
                            "n.oid=c.relnamespace WHERE c.relkind='r' AND n.nspname NOT IN "
                            "('pg_catalog','information_schema','public')").fetchone()[0]:
                raise ValueError("the production stand-in is not empty")
            for (schema,) in conn.execute(
                "SELECT nspname FROM pg_namespace WHERE nspname NOT LIKE 'pg\\_%' AND "
                "nspname NOT IN ('public','information_schema')").fetchall():
                conn.execute(sql.SQL("DROP SCHEMA {}").format(sql.Identifier(schema)))
            conn.execute("DROP TABLE IF EXISTS public.docsuri_local_identity")
        self._copy_schema(name)

    def create_import(self, name: str) -> None:
        """A fresh import database: one a resumed import restored before is replaced."""
        from psycopg import sql

        self._require(name, "import")
        ident = sql.Identifier(name)
        with self.admin() as conn:
            conn.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(ident))
            conn.execute(sql.SQL("CREATE DATABASE {} OWNER {} TEMPLATE template1").format(
                ident, sql.Identifier(DISPOSABLE)))

    def restore_import(self, name: str, spool: Path) -> None:
        self._require(name, "import")
        with open(spool, "rb") as source:
            restored = _docker("exec", "-i", self.container, "pg_restore", "-U", "postgres",
                               "--no-owner", "--no-privileges", "--no-comments", "--role",
                               DISPOSABLE, "--exit-on-error", "-d", name, stdin=source)
        if restored.returncode != 0:
            raise RuntimeError("import-restore-failed")

    def database_bytes(self, name: str) -> int:
        with self.admin() as conn:
            row = conn.execute("SELECT pg_database_size(datname) FROM pg_database "
                               "WHERE datname=%s", (name,)).fetchone()
        return 0 if row is None else int(row[0])

    @contextmanager
    def import_reader(self, name: str):
        from psycopg.rows import dict_row

        self._require(name, "import")
        password = json.loads(private_bytes(self.run_root / "standin-credentials.json"))[
            "roles"]["scheduler"]
        with _connect(self.port, "docsuri_scheduler", password, name, autocommit=True,
                      row_factory=dict_row) as conn:
            yield conn


def owners_for(local_profile) -> Callable:
    """The four owners' import operations on one rehearsal database of the realm."""

    def build(database: str):
        from backend.artifacts import PrivateArtifacts
        from backend.modules.corpus.limits import PRODUCTION_LIMITS
        from backend.modules.discovery.u8_search import VECTOR_POLICY, StandinEmbeddings
        from backend.modules.operations.migration.phases import Owners
        from backend.transactions import OwnerTransactions

        target = dataclasses.replace(local_profile, database_name=database)
        # § 3.1's migration tool row (Step 51(c), L1-13).
        transactions = OwnerTransactions(target, process="migration")
        files = PrivateArtifacts.for_profile(local_profile, "corpus-files",
                                             maximum_bytes=PRODUCTION_LIMITS.max_source_bytes)
        owners = Owners.for_target(transactions, files=files, limits=PRODUCTION_LIMITS,
                                   embedder=StandinEmbeddings(), vector_policy=VECTOR_POLICY)
        return owners, transactions.close

    return build
