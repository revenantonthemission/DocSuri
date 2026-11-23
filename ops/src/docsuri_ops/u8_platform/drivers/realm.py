"""The realm driver: A6's effects on the composed realm (U8 plan Step 27; BR10.2, BR10.3).

It stands in for the arrangement, so the journeys exercise the same receipts,
preconditions and ledger records as production:

- **service control** records the named realm process's wanted state in
  `platform/services/<label>.json`, which the realm's process supervisor acts on, and on
  a stop leaves a stop record citing its receipt in `platform/stops/`, bounded at 14 days
  like production's;
- **tunnel routing** writes the public stand-in's active configuration
  (`tunnel-active.json` in the run root, which `scripts/u8_tunnel_standin.py` reads);
- **the backup agent** is the same agent (`docsuri_ops.backup_agent`), run against the
  realm's stand-in volume folder `backup-volume/` with the realm's caller identities:
  the scheduler's for the standing words, the operator's in person;
- **database removal** drops a disposable database through the scheduler's stand-in
  login, and a **recreate** recreates the realm's production stand-in through the
  realm's administrator login. The recreate keeps the database's base, which no
  owner's dump carries and the restore login may not restore: the database's own
  grants, the owners' empty schemas each owned by its owner, the public schema's and
  `pg_ls_waldir`'s grants, and (except for an abandonment's empty recreate) the realm's
  identity row. It reads them from the database before dropping it, keeping a copy in
  `platform/recreate/` so a retry after a failure between the drop and the create
  still has them (U8 plan Step 29);
- **a production restore** (Workflow 7) streams the chosen set back through the agent's
  in-person `stream-back` into a private spool file, checks its digest against the
  record before use, and restores it with `pg_restore -j 2 --no-comments` as the restore
  login, with `maintenance_work_mem = 1GB` and two parallel maintenance workers, so
  every object keeps its owner without the superuser (D14). Only the owners' entries
  are restored: the base is the recreate's;
- **profile changes** update the realm's platform profile, `platform/profile.json`;
- **the isolation check** records a stand-in result (no arrangement exists in a realm);
- **decisions** record what the receipt binds in `platform/decisions/`;
- **v1 lifecycle apply** runs `v2_rollback_apply` with the synthetic v1's runtime the
  driver configuration names.

Every effect refuses the production profile (BR7.1).
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

from . import DriverRefused, canonical, facts_of

STOP_BOUND = dt.timedelta(days=14)
RESTORE_SECONDS = 2700  # performance-design § 7.2: 45 minutes for recreate and restore
# The session settings of a production restore's index rebuild (performance-design § 7.2).
RESTORE_OPTIONS = "-c maintenance_work_mem=1GB -c max_parallel_maintenance_workers=2"
OWNER_ROLE = re.compile(r"docsuri_[a-z]+_owner")
# Entries a production restore never takes from the set: the base the recreate keeps.
BASE_ENTRIES = ("SCHEMA", "EXTENSION", "COMMENT")
CONTAINER = re.compile(r"docsuri-u8-[0-9a-f]{16}")
ORIGINS = ("v1-web", "v2-host", "maintenance")
LABEL = re.compile(r"dev\.docsuri\.u8\.run\.[a-z0-9-]{1,32}")
PROFILE_FIELDS = ("mode", "admission", "rehearsalDatabase", "backupVolume")
V1_STORE = re.compile(r"v1-stores/[a-z0-9-]{1,32}")
V1_SECONDS = 300
AGENT_SECONDS = 1800
# A supervised start waits for the process to answer its health address (the
# supervisor's own start bound is 90 s); a stop for its exit. Both end inside the
# protocol's 120 s deadline (inventory.json, `platform.service.control`).
SERVICE_ACK_SECONDS = 100
SERVICE_POLL_SECONDS = 0.25
# The agent's realm entry (`backup_agent.cli.main_realm`) and the two words whose JSON
# result goes to standard error; the driver itself imports nothing of the agent's.
AGENT_ENTRY = ("import sys; from docsuri_ops.backup_agent.cli import main_realm; "
               "raise SystemExit(main_realm(sys.argv[1:]))")
AGENT_BYTE_WORDS = ("stream-back", "ledger-copy", "snapshot-stream")
# The ledger component's copy for a lone ledger copy (L1-5, U8 plan Step 64(c)): the
# ledger folder's chain up to its head on standard output, the head on standard error,
# from the repository, as the realm's ledger component would answer it.
LEDGER_ENTRY = (
    "import datetime, json, sys; from pathlib import Path; "
    "from backend.modules.operations.ledger import LedgerStore; "
    "store = LedgerStore.open(Path(sys.argv[1]), "
    "clock=lambda: datetime.datetime.now(datetime.UTC)); "
    "head = store.copy(sys.stdout.buffer); sys.stdout.buffer.flush(); store.close(); "
    "sys.stderr.write(json.dumps({'ok': True, **head}) + '\\n')"
)


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def _write(path: Path, value: dict) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    pending = path.with_name(path.name + ".pending")
    descriptor = os.open(pending, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(canonical(value))
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(pending, path)


def _read(path: Path) -> dict | None:
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    except FileNotFoundError:
        return None
    with os.fdopen(descriptor, "rb") as stream:
        return json.loads(stream.read(65536))


CALLERS = ("operator", "scheduler")


class RealmDriver:
    def __init__(self, config: dict, *, caller: str = "operator"):
        """`caller` is who runs the request: the operator in person, or the standing
        scheduler, whose requests run under the scheduler's identity and are refused
        every in-person agent word, as production's `sudo -k` fails unattended (your
        decision of 2026-10-26, "Only in person"). An effect's child takes it from
        the caller its operator recorded beside the input."""
        if config.get("kind") != "realm" or config.get("production"):
            raise DriverRefused("realm-driver-refuses-production")
        if caller not in CALLERS:
            raise DriverRefused("caller-refused")
        self.config, self.caller = config, caller
        self.run_root = Path(config["runRoot"])
        self.state = Path(config["stateRoot"])
        # Where the tunnel stand-in reads its active choice: the run root, unless a
        # journey keeps its own (the operations tests do, so the realm's routing holds).
        self.tunnel_root = Path(config.get("tunnelRoot", config["runRoot"]))
        self.run_id = config["runId"]

    # --- the backup agent --------------------------------------------------------------

    def _agent_command(self, word: str, via: str) -> tuple[list[str], dict, str]:
        repository = self.config.get("repository")
        if not repository:
            raise DriverRefused("realm-repository-unconfigured")
        if via not in ("standing", "in-person"):
            raise DriverRefused("authority-refused")
        if self.caller == "scheduler" and via == "in-person":
            # A standing request never reaches an in-person word (production's `sudo -k`
            # fails unattended), so a standing path that needs you fails here too.
            raise DriverRefused("in-person-refused")
        caller = self.config["schedulerUid"] if via == "standing" else self.config["operatorUid"]
        return [sys.executable, "-c", AGENT_ENTRY, self.config["agentFolder"], word], (
            self.agent_environment(caller)), repository

    @staticmethod
    def agent_environment(caller) -> dict:
        """The backup agent's environment: PATH and SUDO_UID, and DOCKER_HOST when this
        process holds it, so the agent's `docker exec` reaches the realm's Docker (U8 plan
        L1-76)."""
        environment = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "SUDO_UID": str(caller)}
        if "DOCKER_HOST" in os.environ:
            environment["DOCKER_HOST"] = os.environ["DOCKER_HOST"]
        return environment

    @staticmethod
    def _agent_result(stream: bytes, returncode: int) -> dict:
        try:
            result = json.loads(stream.decode().splitlines()[-1])
        except (ValueError, IndexError):
            raise DriverRefused("agent-answered-no-result") from None
        if returncode != 0 or not result.get("ok"):
            raise DriverRefused(result.get("reason", "agent-refused"))
        return result

    def _agent(self, word: str, document: dict, *, via: str) -> dict:
        """The same agent, in a process of its own from the repository (production's
        fixed program reaches the release's source roots through its `.pth`; the
        bounded child has none), as the scheduler or the operator by `SUDO_UID`."""
        argv, environment, repository = self._agent_command(word, via)
        completed = subprocess.run(
            argv, input=json.dumps(document).encode(), capture_output=True, cwd=repository,
            env=environment, timeout=AGENT_SECONDS, check=False,
        )
        stream = completed.stderr if word in AGENT_BYTE_WORDS else completed.stdout
        return self._agent_result(stream, completed.returncode)

    def agent_word(self, word: str, document: dict, *, via: str) -> dict:
        """One of the agent's JSON words for the operator tool's own steps (a volume
        retirement's `prepare-volume`, `configure` and `status`, BR4.10)."""
        if word in AGENT_BYTE_WORDS:
            raise DriverRefused("byte-word-refused")
        return self._agent(word, document, via=via)

    def ledger_copy(self, stream: bytes) -> dict:
        """The ledger component's stream into the agent's unattended `ledger-copy`, as
        the standing job pipes it in production (Step 35); the copy reaches the agent
        only as a stream."""
        argv, environment, repository = self._agent_command("ledger-copy", "standing")
        completed = subprocess.run(argv, input=stream, capture_output=True, cwd=repository,
                                   env=environment, timeout=AGENT_SECONDS, check=False)
        return self._agent_result(completed.stderr, completed.returncode)

    def snapshot_stream(self, header: dict, payload: bytes) -> dict:
        """A snapshot's tar archive into the agent's in-person `snapshot-stream`: its
        header line, then the archive (Workflow 19 step 3, U8 plan Step 31)."""
        argv, environment, repository = self._agent_command("snapshot-stream", "in-person")
        stream = json.dumps(header).encode() + b"\n" + payload
        completed = subprocess.run(argv, input=stream, capture_output=True, cwd=repository,
                                   env=environment, timeout=AGENT_SECONDS, check=False)
        return self._agent_result(completed.stderr, completed.returncode)

    def stream_back(self, entry: dict, spool: Path) -> dict:
        """One catalogued file streamed back in person into a new private spool, its
        digest checked against the record before use (an import, Workflow 9)."""
        return self._stream_back(entry, spool)

    def _stream_back(self, entry: dict, spool: Path) -> dict:
        """The agent's in-person `stream-back` into a new private spool file; the
        caller checks the digest against the record before use (BR4.3)."""
        argv, environment, repository = self._agent_command("stream-back", "in-person")
        spool.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        descriptor = os.open(spool, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(descriptor, "wb") as sink:
            completed = subprocess.run(
                argv, input=json.dumps(entry).encode(), stdout=sink, stderr=subprocess.PIPE,
                cwd=repository, env=environment, timeout=AGENT_SECONDS, check=False,
            )
            sink.flush()
            os.fsync(sink.fileno())
        result = self._agent_result(completed.stderr, completed.returncode)
        digest = hashlib.sha256()
        with open(spool, "rb") as source:
            while block := source.read(1 << 20):
                digest.update(block)
        if digest.hexdigest() != entry["sha256"] or result.get("sha256") != entry["sha256"]:
            raise DriverRefused("streamed-set-digest-mismatch")
        return result

    # --- databases -----------------------------------------------------------------------

    def _password(self, file: str, role: str) -> str:
        from docsuri_ops.platform_control.profile import private_bytes

        value = json.loads(private_bytes(self.run_root / file))
        if value.get("runId") not in (self.run_id, None):
            raise DriverRefused("realm-credential-mismatch")
        roles = value.get("roles", {})
        return roles[role] if role in roles else value[role]

    def _connect(self, user: str, password: str, dbname: str = "postgres"):
        import psycopg

        return psycopg.connect(host="127.0.0.1", port=int(self.config["databasePort"]),
                               dbname=dbname, user=user, password=password,
                               require_auth="scram-sha-256", connect_timeout=5,
                               autocommit=True)

    def _drop_disposable(self, database: str) -> None:
        from psycopg import sql

        with self._connect("docsuri_scheduler",
                           self._password("standin-credentials.json", "scheduler")) as conn:
            conn.execute(sql.SQL("SET statement_timeout = '600s'"))
            conn.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(database)))

    def _admin(self, dbname: str = "postgres"):
        return self._connect("postgres", self._password("migration-credentials.json",
                                                        "databaseAdminPassword"), dbname)

    def _base_path(self, database: str) -> Path:
        return self.state / "recreate" / f"{database}.json"

    def _capture_base(self, database: str) -> dict:
        """The database's base, read before it is dropped (or the copy kept by an
        earlier attempt, when a failure left it dropped)."""
        with self._admin() as conn:
            exists = conn.execute("SELECT 1 FROM pg_database WHERE datname=%s",
                                  (database,)).fetchone()
            if exists is None:
                kept = _read(self._base_path(database))
                if kept is None:
                    raise DriverRefused("recreate-base-unknown")
                return kept
            grants = conn.execute(
                "SELECT coalesce(r.rolname,'PUBLIC') AS role,a.privilege_type AS privilege "
                "FROM pg_database d, aclexplode(d.datacl) a LEFT JOIN pg_roles r "
                "ON r.oid=a.grantee WHERE d.datname=%s ORDER BY 1,2", (database,),
            ).fetchall()
            # A database whose grants were never changed keeps PostgreSQL's defaults.
            defaults = conn.execute("SELECT datacl IS NULL FROM pg_database WHERE datname=%s",
                                    (database,)).fetchone()[0]
        with self._admin(database) as conn:
            base = {
                "databaseDefaults": bool(defaults),
                "publicDefaults": bool(conn.execute(
                    "SELECT nspacl IS NULL FROM pg_namespace WHERE nspname='public'"
                ).fetchone()[0]),
                "database": [list(row) for row in grants],
                "schemas": [list(row) for row in conn.execute(
                    "SELECT nspname,pg_get_userbyid(nspowner) FROM pg_namespace WHERE nspname "
                    "NOT LIKE 'pg\\_%' AND nspname NOT IN ('public','information_schema') "
                    "ORDER BY 1").fetchall()],
                "public": [list(row) for row in conn.execute(
                    "SELECT coalesce(r.rolname,'PUBLIC'),a.privilege_type FROM pg_namespace n, "
                    "aclexplode(n.nspacl) a LEFT JOIN pg_roles r ON r.oid=a.grantee "
                    "WHERE n.nspname='public' ORDER BY 1,2").fetchall()],
                "waldir": [row[0] for row in conn.execute(
                    "SELECT coalesce(r.rolname,'PUBLIC') FROM pg_proc p, aclexplode(p.proacl) a "
                    "LEFT JOIN pg_roles r ON r.oid=a.grantee WHERE p.oid="
                    "'pg_catalog.pg_ls_waldir'::regproc AND a.privilege_type='EXECUTE' "
                    "AND r.rolname IS DISTINCT FROM 'postgres' ORDER BY 1").fetchall()],
                "identity": None,
            }
            if conn.execute("SELECT to_regclass('public.docsuri_local_identity')").fetchone()[0]:
                row = conn.execute("SELECT run_id,schema_hashes FROM "
                                   "public.docsuri_local_identity").fetchone()
                readers = [item[0] for item in conn.execute(
                    "SELECT r.rolname FROM pg_class c, aclexplode(c.relacl) a JOIN pg_roles r "
                    "ON r.oid=a.grantee WHERE c.oid='public.docsuri_local_identity'::regclass "
                    "AND a.privilege_type='SELECT' AND r.rolname<>'postgres' ORDER BY 1"
                ).fetchall()]
                base["identity"] = {"runId": row[0], "schemaHashes": row[1], "readers": readers}
        _write(self._base_path(database), base)
        return base

    @staticmethod
    def _grantee(role: str):
        from psycopg import sql

        return sql.SQL("PUBLIC") if role == "PUBLIC" else sql.Identifier(role)

    def _replay_base(self, database: str, base: dict, *, identity: bool) -> None:
        from psycopg import sql
        from psycopg.types.json import Jsonb

        name = sql.Identifier(database)
        with self._admin() as conn:
            if not base.get("databaseDefaults"):
                conn.execute(sql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC").format(name))
                for role, privilege in base["database"]:
                    if privilege in ("CONNECT", "CREATE", "TEMPORARY"):
                        conn.execute(sql.SQL("GRANT {} ON DATABASE {} TO {}").format(
                            sql.SQL(privilege), name, self._grantee(role)))
        with self._admin(database) as conn:
            if not base.get("publicDefaults"):
                conn.execute("REVOKE ALL ON SCHEMA public FROM PUBLIC")
                for role, privilege in base["public"]:
                    if privilege in ("USAGE", "CREATE") and role != "pg_database_owner":
                        conn.execute(sql.SQL("GRANT {} ON SCHEMA public TO {}").format(
                            sql.SQL(privilege), self._grantee(role)))
            for role in base["waldir"]:
                conn.execute(sql.SQL("GRANT EXECUTE ON FUNCTION pg_catalog.pg_ls_waldir() TO {}")
                             .format(self._grantee(role)))
            for schema, owner in base["schemas"]:
                conn.execute(sql.SQL("CREATE SCHEMA {} AUTHORIZATION {}").format(
                    sql.Identifier(schema), sql.Identifier(owner)))
            recorded = base.get("identity")
            if identity and recorded is not None:
                conn.execute(
                    "CREATE TABLE public.docsuri_local_identity (singleton boolean PRIMARY KEY "
                    "CHECK(singleton),run_id text NOT NULL,schema_hashes jsonb NOT NULL)")
                conn.execute("INSERT INTO public.docsuri_local_identity VALUES(true,%s,%s)",
                             (recorded["runId"], Jsonb(recorded["schemaHashes"])))
                for role in recorded["readers"]:
                    conn.execute(sql.SQL("GRANT SELECT ON public.docsuri_local_identity TO {}")
                                 .format(sql.Identifier(role)))

    def _recreate(self, database: str, *, abandonment: bool = False) -> None:
        """Drop and create the database from `template1` (pgvector in it, D14), then
        replay its base; an abandonment's recreate keeps no identity row, so v2's start
        check refuses the empty database until its owners' migrations run again."""
        from psycopg import sql

        base = self._capture_base(database)
        with self._admin() as conn:
            conn.execute("SET statement_timeout = '600s'")
            name = sql.Identifier(database)
            conn.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(name))
            conn.execute(sql.SQL("CREATE DATABASE {} TEMPLATE template1").format(name))
        self._replay_base(database, base, identity=not abandonment)

    # --- a production restore (Workflow 7) -----------------------------------------------

    def _container(self) -> str:
        from docsuri_ops.platform_control.profile import private_bytes

        value = json.loads(private_bytes(self.run_root / "environment.json"))
        container = str(value.get("container", ""))
        if value.get("runId") != self.run_id or not CONTAINER.fullmatch(container):
            raise DriverRefused("realm-container-mismatch")
        return container

    @staticmethod
    def owners_entries(listing: str) -> str:
        """The set's table of contents without the base: only the owners' entries, and
        none that creates a schema, an extension or a comment."""
        kept = []
        for line in listing.splitlines():
            if not line.strip() or line.startswith(";"):
                continue
            fields = line.split()
            if len(fields) < 5 or fields[3] in BASE_ENTRIES:
                continue
            if not OWNER_ROLE.fullmatch(fields[-1]):
                continue
            kept.append(line)
        return "\n".join(kept) + "\n"

    @staticmethod
    def docker_environment() -> dict:
        """The environment of the driver's `docker` calls: PATH, DOCKER_CONFIG and HOME
        as built, and DOCKER_HOST when this process holds it (U8 plan L1-76)."""
        env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin")}
        if os.environ.get("DOCKER_CONFIG"):
            env["DOCKER_CONFIG"] = os.environ["DOCKER_CONFIG"]
        if os.environ.get("HOME"):
            env["HOME"] = os.environ["HOME"]
        if "DOCKER_HOST" in os.environ:
            env["DOCKER_HOST"] = os.environ["DOCKER_HOST"]
        return env

    def _docker(self, *args: str, payload: bytes | None = None, source=None, seconds: int = 600,
                environment: dict | None = None) -> subprocess.CompletedProcess:
        env = self.docker_environment()
        env.update(environment or {})
        if source is not None:
            return subprocess.run(["docker", *args], stdin=source, capture_output=True,
                                  env=env, timeout=seconds, check=False)
        return subprocess.run(["docker", *args], input=payload, capture_output=True,
                              env=env, timeout=seconds, check=False)

    def _pg_restore(self, database: str, spool: Path, token: str) -> None:
        """`pg_restore -j 2 --no-comments` as the restore login, inside the realm's
        database container, from the verified spool copied into the container's private
        `/tmp` (a 16 MB tmpfs: the container's own root is read-only): `-j` needs a
        regular file."""
        container = self._container()
        archive = f"/tmp/docsuri-restore-{token}.archive"
        listing = f"/tmp/docsuri-restore-{token}.list"
        password = self._password("standin-credentials.json", "restore")
        try:
            with open(spool, "rb") as source:
                copied = self._docker("exec", "-i", container, "dd", f"of={archive}",
                                      "status=none", source=source)
            if copied.returncode != 0:
                raise DriverRefused("restore-spool-unavailable")
            listed = self._docker("exec", container, "pg_restore", "-l", archive)
            if listed.returncode != 0:
                raise DriverRefused("restore-set-unreadable")
            entries = self.owners_entries(listed.stdout.decode("utf-8", "replace")).encode()
            if self._docker("exec", "-i", container, "dd", f"of={listing}", "status=none",
                            payload=entries).returncode:
                raise DriverRefused("restore-list-unavailable")
            target = (f"host=127.0.0.1 port=5432 dbname={database} user=docsuri_restore "
                      "require_auth=scram-sha-256 connect_timeout=5")
            restored = self._docker(
                "exec", "-e", "PGPASSWORD", "-e", "PGOPTIONS", container, "pg_restore", "-j", "2",
                "--no-comments", "--exit-on-error", "--no-password", "-L", listing, "-d", target,
                archive, seconds=RESTORE_SECONDS,
                environment={"PGPASSWORD": password, "PGOPTIONS": RESTORE_OPTIONS},
            )
            if restored.returncode != 0:
                raise DriverRefused("restore-failed")
        finally:
            self._docker("exec", container, "rm", "-f", archive, listing)

    # --- effects -------------------------------------------------------------------------

    def effect(self, kind: str, inputs: dict, *, context: dict) -> list[str]:
        handler = getattr(self, "_" + kind.replace("-", "_"), None)
        if handler is None:
            raise DriverRefused("unsupported-effect-kind")
        caller = context.get("caller") or self.caller
        if caller not in CALLERS:
            raise DriverRefused("caller-refused")
        self.caller = caller
        return handler(inputs, context)

    def _database_backup(self, inputs, context):
        result = self._agent("backup", {"database": inputs["database"],
                                        "recordId": inputs["recordId"]}, via=inputs["via"])
        return [f"backup-volume/{result['location']}", *facts_of(result)]

    def _database_restore(self, inputs, context):
        if inputs.get("mode") == "scratch":
            document = {"scratchDatabase": inputs["scratchDatabase"],
                        "setKind": inputs["setKind"]}
            if "recordId" in inputs:
                document["recordId"] = inputs["recordId"]
            result = self._agent("verify", document, via=inputs["via"])
            return [f"database/{result['scratchDatabase']}", *facts_of(result)]
        if inputs.get("mode") != "production" or inputs.get("via") != "in-person":
            raise DriverRefused("restore-mode-refused")
        entry = {"path": inputs["setPath"], "sha256": inputs["setSha256"]}
        spool = self.state / "restore" / f"{context['token']}.archive"
        try:
            self._stream_back(entry, spool)
            self._pg_restore(inputs["database"], spool, context["token"])
        finally:
            spool.unlink(missing_ok=True)
        return [f"database/{inputs['database']}",
                *facts_of({"setPath": entry["path"], "setSha256": entry["sha256"]})]

    def _database_recreate(self, inputs, context):
        self._recreate(inputs["database"], abandonment=bool(inputs.get("abandonment")))
        return [f"database/{inputs['database']}"]

    def _database_remove(self, inputs, context):
        self._drop_disposable(inputs["database"])
        return [f"database/{inputs['database']}"]

    @property
    def services(self) -> Path:
        """Where service control writes each label's wanted state: the driver's own state
        folder, unless the configuration names the folder a supervisor watches."""
        return Path(self.config.get("servicesRoot", self.state / "services"))

    def services_for(self, label: str) -> Path:
        """v1's two labels may be watched elsewhere (`v1ServicesRoot`: the synthetic v1's
        supervisor watches the realm's folder), so a journey's own v2 stays its own."""
        if label.rsplit(".", 1)[-1].startswith("v1-") and self.config.get("v1ServicesRoot"):
            return Path(self.config["v1ServicesRoot"])
        return self.services

    def _supervised(self, label: str) -> bool:
        """A live supervisor has registered for this label in the services folder."""
        value = _read(self.services_for(label) / "supervisors" / f"{label}.json")
        if not value or value.get("runId") != self.run_id:
            return False
        try:
            os.kill(int(value["pid"]), 0)
        except (ProcessLookupError, ValueError, KeyError, TypeError):
            return False
        except PermissionError:
            return True
        return True

    def _await_ack(self, label: str, operation: str, wanted: str) -> None:
        """Wait, within its bound, for the supervisor to report the label in the wanted
        state for this operation; anything else fails the effect (BR10.2)."""
        deadline = time.monotonic() + SERVICE_ACK_SECONDS
        while time.monotonic() < deadline:
            ack = _read(self.services_for(label) / f"{label}.ack.json") or {}
            if ack.get("operationId") == operation:
                if ack.get("result") != "succeeded" or ack.get("observed") != wanted:
                    raise DriverRefused("service-control-failed")
                return
            if not self._supervised(label):
                raise DriverRefused("service-supervisor-gone")
            time.sleep(SERVICE_POLL_SECONDS)
        raise DriverRefused("service-control-unacknowledged")

    def _service_control(self, inputs, context):
        label, action = inputs["label"], inputs["action"]
        if not LABEL.fullmatch(label) or action not in ("start", "stop"):
            raise DriverRefused("label-refused")
        now = _now()
        wanted = "stopped" if action == "stop" else "running"
        supervised = self._supervised(label)
        # The job's state before this effect, as the fixed program reports it
        # (`wasLoaded`): a label never set is taken as running, for a stop and for a
        # start alike (the realm's v2 may run without a wanted-state file, as
        # production's job runs at boot before any wanted state is written; review
        # finding, Minor, R18), so only a label set `stopped` counts as unloaded.
        before = (_read(self.services_for(label) / f"{label}.json") or {}).get("state")
        was_loaded = before != "stopped"
        _write(self.services_for(label) / f"{label}.json",
               {"label": label, "state": wanted,
                "operationId": context["operationId"], "at": now.isoformat()})
        if supervised:
            self._await_ack(label, context["operationId"], wanted)
        stop = self.state / "stops" / f"{label}.json"
        if action == "stop":
            _write(stop, {"label": label, "operationId": context["operationId"],
                          "stoppedAt": now.isoformat(),
                          "expiresAt": (now + STOP_BOUND).isoformat()})
        elif stop.exists():
            os.unlink(stop)
        return [f"service/{label}/{action}",
                *facts_of({"wasLoaded": "true" if was_loaded else "false"})]

    def _tunnel_route(self, inputs, context):
        if inputs["origin"] not in ORIGINS:
            raise DriverRefused("origin-refused")
        _write(self.tunnel_root / "tunnel-active.json", {"runId": self.run_id,
                                                         "origin": inputs["origin"]})
        return [f"tunnel/{inputs['origin']}"]

    def _isolation_check(self, inputs, context):
        now = _now()
        _write(self.state / "isolation" / f"{now:%Y%m%dT%H%M%S%f}.json",
               {"result": "passed", "standin": True, "checkedAt": now.isoformat(),
                "operationId": context["operationId"]})
        return ["isolation/standin"]

    def _profile_change(self, inputs, context):
        field = inputs["field"]
        if field not in PROFILE_FIELDS:
            raise DriverRefused("profile-field-refused")
        path = self.state / "profile.json"
        current = _read(path) or {}
        _write(path, {**current, field: inputs["value"],
                      "receiptOperationId": context["operationId"]})
        return [f"profile/{field}"]

    def _copy_dispose(self, inputs, context):
        if inputs["place"] == "backup-volume":
            self._agent("dispose-event", {"path": inputs["location"], "event": inputs["event"]},
                        via="in-person")
            return [f"backup-volume/{inputs['location']}"]
        if inputs["place"] == "database":
            self._drop_disposable(inputs["location"])
            return [f"database/{inputs['location']}"]
        if inputs["place"] == "v1-stores":
            return self._v1_stores_gone(inputs["locations"])
        raise DriverRefused("place-refused")

    def _v1_stores_gone(self, locations: list[str]) -> list[str]:
        """The realm's stand-ins for v1's stores (`v1-stores/*` in the run root), checked
        read-only: each must be gone. Nothing is deleted here (BR9.17). A journey may keep
        its own stand-ins (`v1StoresRoot`), so the realm's are never touched by a test."""
        root = Path(self.config.get("v1StoresRoot", self.config["runRoot"]))
        refs = []
        for location in locations:
            if not V1_STORE.fullmatch(str(location)):
                raise DriverRefused("v1-store-location-refused")
            try:
                os.lstat(root / location)
            except FileNotFoundError:
                refs.append(f"{location}/absent")
                continue
            raise DriverRefused("v1-store-still-present")
        return refs

    def v1_environment(self) -> dict:
        """v1's whole process environment, from the file `u8_synthetic_v1.wire_driver`
        wrote and only after its addresses are checked: v1's code otherwise defaults to v1's
        real stores (its session store to the live site's Redis on 6379). Fails closed."""
        from docsuri_ops.u8_platform.v1_environment import (
            V1EnvironmentRefused,
            load,
            runtime_environment,
        )

        checkout = self.config.get("v1Checkout")
        if not checkout:
            raise DriverRefused("v1-checkout-unconfigured")
        # A journey keeps its own file under its own root; the checks are the same.
        root = Path(self.config.get("v1EnvironmentRoot", self.run_root))
        try:
            checked = load(self.config.get("v1EnvironmentFile"), run_root=root)
            return runtime_environment(checked, Path(checkout))
        except V1EnvironmentRefused as refused:
            raise DriverRefused(str(refused)) from None

    def _v1_lifecycle_apply(self, inputs, context):
        runtime = self.config.get("v1Runtime")
        if not runtime:
            raise DriverRefused("v1-runtime-unconfigured")
        environment = self.v1_environment()
        completed = subprocess.run(
            [*runtime, "-m", "backend.modules.accounts.services.v2_rollback_apply"],
            input=canonical({"outcomes": inputs["outcomes"], "accounts": inputs["accounts"]}),
            capture_output=True, cwd=self.config["v1Checkout"], env=environment,
            timeout=V1_SECONDS, check=False,
        )
        if completed.returncode != 0:
            raise DriverRefused("v1-lifecycle-refused")
        return ["v1/lifecycle"]

    def _decision_record(self, inputs, context):
        _write(self.state / "decisions" / f"{context['operationId']}.json", dict(inputs))
        return [f"decisions/{context['operationId']}"]

    def _ledger_copy(self, inputs, context):
        """A lone ledger copy (L1-5, U8 plan Step 64(c)): the ledger folder the
        configuration names (`ledgerFolder`, default `<runRoot>/ledger`) copied into
        memory, then piped into the realm agent's `ledger-copy` as the recorded caller.
        The bounded child receives only the bound input, so the driver produces the
        ledger's stream itself."""
        repository = self.config.get("repository")
        if not repository:
            raise DriverRefused("realm-repository-unconfigured")
        folder = str(self.config.get("ledgerFolder") or self.run_root / "ledger")
        argv, environment, _ = self._agent_command("ledger-copy", inputs["via"])
        try:
            source = subprocess.run(
                [sys.executable, "-c", LEDGER_ENTRY, folder], input=b"", capture_output=True,
                cwd=repository, env={"PATH": environment["PATH"]}, timeout=AGENT_SECONDS,
                check=False)
        except subprocess.TimeoutExpired:
            raise DriverRefused("program-timed-out") from None
        ledger = self._agent_result(source.stderr, source.returncode)
        completed = subprocess.run(argv, input=source.stdout, capture_output=True,
                                   cwd=repository, env=environment, timeout=AGENT_SECONDS,
                                   check=False)
        agent = self._agent_result(completed.stderr, completed.returncode)
        head = {"headSequence": ledger.get("count"), "headDigest": ledger.get("head")}
        return [f"backup-volume/{agent['location']}", *facts_of({**agent, **head})]

    # --- reconciliation ------------------------------------------------------------------

    def observe(self, kind: str, inputs: dict) -> bool:
        """Whether the effect is in place now, read from its target alone."""
        if kind == "tunnel-route":
            return (_read(self.tunnel_root / "tunnel-active.json") or {}).get(
                "origin") == inputs["origin"]
        if kind == "service-control":
            state = _read(self.services_for(inputs["label"]) / f"{inputs['label']}.json") or {}
            return state.get("state") == ("stopped" if inputs["action"] == "stop" else "running")
        if kind == "profile-change":
            return (_read(self.state / "profile.json") or {}).get(inputs["field"]) == inputs[
                "value"]
        return False
