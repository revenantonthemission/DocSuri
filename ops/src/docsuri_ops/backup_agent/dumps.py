"""The databases the backup agent dumps and restores (U8 plan Step 25; BR4.3, BR4.5, D14,
Workflow 5, Workflow 6, Workflow 19 steps 3 and 5).

- `backup` dumps, with `pg_dump -Fc`, only a database its configuration names in v2's
  instance: the production database, as a live set, or a rehearsal-pattern database,
  as a rehearsal set. Scratch and import databases are never dumped.
- `snapshot` (in person) dumps v1's database through its read-only login, as a dry-run
  or final snapshot; `rollback-copy` (in person) dumps the stopped production database
  as a rolled-back database's copy.
- The integrity check is the agent's own: the dump's table of contents lists every
  table the agent saw in that database when it dumped.
- `verify` restores the newest passed set of the kind it is asked for (the live set, or
  the rehearsal set during the soak) into a new scratch database, with
  `pg_restore --no-comments --no-owner --no-privileges --role <disposable role>`, so the
  copy belongs to the disposable-databases role and no file leaves the agent. The name is checked
  against the scratch pattern before any connection is made: PostgreSQL cannot limit
  the names a login creates while acting as a role it may create as, so this check and
  the one role the agent ever switches to are the limit (the person's decision of
  2026-10-22). Its own statements carry their own timeout, because `CREATE DATABASE`
  can outlast the instance's statement limit.
- `verify` stops below the internal disk's critical floor (NFR7.18, NFR8.14; U8 plan
  Step 121, L2-8): the floor is read before any client program runs and between the two
  passes, and every `WATCH_SECONDS` while `pg_restore` runs. Below it the agent ends its
  own sessions on the scratch database (`pg_terminate_backend` with a 5 s wait), then
  stops its client (SIGTERM, then SIGKILL `END_GRACE_SECONDS` later, once
  `STOP_GRACE_SECONDS` have passed) and refuses `internal-disk-critical` with
  `sessionsEnded`. The scheduler's login drops the scratch database afterwards
  (Workflow 6's own drop); the agent drops nothing.

`PgTools` runs the PostgreSQL client programs: `RuntimeTools` from the release's pinned
runtime on this Mac, `ContainerTools` inside the composed realm's database container.
Both connect with `require_auth=scram-sha-256` (D9), and the login's password reaches
the client program only through its own environment, never its arguments.
"""

from __future__ import annotations

import datetime as dt
import math
import os
import re
import secrets
import shutil
import subprocess
import time
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

import psycopg
from psycopg import sql

from .config import AgentConfig, Login
from .writing import CHUNK, AgentRefused, ArchiveWriter, Decided

# `CREATE DATABASE` and a restore may run past the instance's statement limit.
STATEMENT_SECONDS = 600
DUMP_SECONDS = 1800
# The critical floor's stop (NFR7.18, NFR8.14; U8 plan Step 121(b)).
CRITICAL = "internal-disk-critical"
WATCH_SECONDS = 5
STOP_GRACE_SECONDS = 30
END_GRACE_SECONDS = 5
# The session-ending statement's own bound; `pg_terminate_backend` waits up to 5 s.
END_STATEMENT_SECONDS = 10
_END_SESSIONS = (
    "SELECT count(*) FILTER (WHERE pg_terminate_backend(pid, 5000)) FROM pg_stat_activity "
    "WHERE datname = %s AND usename = current_user AND pid <> pg_backend_pid()"
)
TOC_TABLE = re.compile(r"^\d+; \d+ \d+ TABLE (\S+) (\S+) ")
# The search projection's HNSW index (backend/modules/corpus/u8_search.sql), restored in
# a pass of its own so its rebuild is timed alone (NFR9.4, U8 plan Step 62(d)).
HNSW_ENTRY = re.compile(r"^\d+; \d+ \d+ INDEX corpus projection_embedding_hnsw( |$)")
_TABLES = (
    "SELECT n.nspname || '.' || c.relname AS name FROM pg_class c "
    "JOIN pg_namespace n ON n.oid = c.relnamespace "
    "WHERE c.relkind IN ('r','p') AND n.nspname NOT IN ('pg_catalog','information_schema') "
    "AND n.nspname NOT LIKE 'pg\\_toast%'"
)


def _never() -> str | None:
    return None


@dataclass(frozen=True)
class RestoreWatch:
    """How a running restore is watched: `reason()` answers None or why to stop; `end()`
    ends the restore's sessions and answers how many; `seconds` between readings;
    `grace` for the sessions to go before the client is signalled; `maintenance` names
    the database `end` connects to (kept here so a test can see it)."""

    reason: Callable[[], str | None]
    end: Callable[[], int]
    seconds: float
    grace: float
    maintenance: str


def conninfo(login: Login, database: str, *, port: int | None = None) -> str:
    return psycopg.conninfo.make_conninfo(
        host=login.host, port=port or login.port, dbname=database, user=login.user,
        require_auth="scram-sha-256", connect_timeout=5,
    )


class PgTools:
    """The PostgreSQL client programs for one login; subclasses say where they run."""

    def __init__(self, login: Login, password: str):
        self.login, self._password = login, password

    # -- the programs ------------------------------------------------------------------

    def command(self, program: str, args: list[str]) -> list[str]:
        raise NotImplementedError

    def program_port(self) -> int:
        return self.login.port

    def environment(self) -> dict[str, str]:
        """The client programs' environment: PATH, PGPASSWORD and LANG."""
        return {"PATH": os.environ.get("PATH", "/usr/bin:/bin"),
                "PGPASSWORD": self._password, "LANG": "C"}

    def _run(self, program: str, args: list[str], *, stdin=None, stdout=None,
             seconds: int, payload: bytes | None = None) -> subprocess.CompletedProcess:
        if payload is not None:
            return subprocess.run(
                self.command(program, args), input=payload, stdout=stdout or subprocess.PIPE,
                stderr=subprocess.PIPE, env=self.environment(), timeout=seconds, check=False,
            )
        return subprocess.run(
            self.command(program, args), stdin=stdin, stdout=stdout or subprocess.PIPE,
            stderr=subprocess.PIPE, env=self.environment(), timeout=seconds, check=False,
        )

    def dump(self, database: str, sink: BinaryIO) -> None:
        target = conninfo(self.login, database, port=self.program_port())
        completed = self._run("pg_dump", ["-Fc", "--no-password", "-d", target],
                              stdout=sink, seconds=DUMP_SECONDS)
        if completed.returncode != 0:
            raise AgentRefused("dump-failed")

    def toc_entries(self, archive: Path) -> list[str]:
        """The archive's table of contents as `pg_restore -l` prints it, line by line."""
        with open_archive(archive) as source:
            completed = self._run("pg_restore", ["-l"], stdin=source, seconds=STATEMENT_SECONDS)
        if completed.returncode != 0:
            raise AgentRefused("toc-unreadable")
        return completed.stdout.decode("utf-8", "replace").splitlines()

    def toc_tables(self, archive: Path) -> set[str]:
        found = set()
        for line in self.toc_entries(archive):
            match = TOC_TABLE.match(line)
            if match:
                found.add(f"{match.group(1)}.{match.group(2)}")
        return found

    @contextmanager
    def list_file(self, listing: str, beside: Path):
        """A restore's list file where the client program reads it: a private folder
        beside the staging files (0700, the file 0600), removed afterwards."""
        folder = beside / f".restore-list-{secrets.token_hex(8)}"
        os.mkdir(folder, 0o700)
        try:
            path = folder / "restore.list"
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                                 0o600)
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(listing.encode())
            yield str(path)
        finally:
            shutil.rmtree(folder, ignore_errors=True)

    def restore(self, source: BinaryIO, database: str, role: str, *,
                listing: str | None = None, beside: Path | None = None,
                watch: RestoreWatch | None = None) -> None:
        """A scratch restore: every object owned by `role`, and no grant restored. A
        scratch copy needs only that ownership, so the scheduler's login, a member of the
        role, can check it, replay into it and drop it; and the dump carries a grant on
        a system function (A10's `pg_ls_waldir`) that only the superuser may give, so
        restoring the grants would fail for every login but the superuser's (D14).
        `listing`, when given, is the `pg_restore -L` list that limits this pass (U8 plan
        Step 62(d)); its file goes where `list_file` puts it. `watch`, when given, is
        read while the client runs and can stop it (`_watched`, U8 plan Step 121(b))."""
        target = conninfo(self.login, database, port=self.program_port())
        args = ["--no-comments", "--no-owner", "--no-privileges", "--role", role,
                "--exit-on-error", "--no-password"]
        if listing is None:
            status = self._restore_client([*args, "-d", target], source, watch)
        else:
            if beside is None:
                raise AgentRefused("restore-list-unavailable")
            with self.list_file(listing, beside) as path:
                status = self._restore_client([*args, "-L", path, "-d", target], source,
                                              watch)
        if status != 0:
            raise AgentRefused("restore-failed")

    def _restore_client(self, args: list[str], source: BinaryIO,
                        watch: RestoreWatch | None) -> int:
        """`pg_restore` run to its exit status: as built without a watch, else watched."""
        if watch is None:
            return self._run("pg_restore", args, stdin=source, stdout=subprocess.DEVNULL,
                             seconds=STATEMENT_SECONDS).returncode
        return self._watched(self.command("pg_restore", args), source, watch)

    def _watched(self, command: list[str], source: BinaryIO, watch: RestoreWatch) -> int:
        """The client under `Popen`, waited for `watch.seconds` at a time with the watch's
        reason read after each wait; a reason stops it (`_stop`). The statement bound
        behaves as `subprocess.run`'s timeout does: the client killed, `TimeoutExpired`
        raised. The client never outlives this call."""
        bound = STATEMENT_SECONDS
        child = subprocess.Popen(command, stdin=source, stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL, env=self.environment())
        try:
            deadline = time.monotonic() + bound
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    _kill(child)
                    raise subprocess.TimeoutExpired(command, bound)
                try:
                    return child.wait(timeout=min(watch.seconds, remaining))
                except subprocess.TimeoutExpired:
                    pass
                reason = watch.reason()
                if reason is not None:
                    _stop(child, watch, reason)
        finally:
            if child.poll() is None:
                _kill(child)

    def end_sessions(self, maintenance: str, database: str) -> int:
        """End this login's own sessions on `database`, from one connection to
        `maintenance`, and answer how many ended. With its 5 s timeout
        `pg_terminate_backend` waits until each backend has exited (PostgreSQL 14 and
        later), so the scheduler's `DROP DATABASE` that follows is not raced; without
        `pg_signal_backend` a login can end only its own sessions."""
        with self.connect(maintenance) as conn:
            conn.execute(sql.SQL("SET statement_timeout = {}").format(
                sql.Literal(f"{END_STATEMENT_SECONDS}s")))
            row = conn.execute(_END_SESSIONS, (database,)).fetchone()
        return 0 if row is None else int(row[0])

    # -- the agent's own statements -------------------------------------------------------

    def connect(self, database: str):
        return psycopg.connect(conninfo(self.login, database), password=self._password,
                               autocommit=True)

    def tables(self, database: str) -> set[str]:
        with self.connect(database) as conn:
            return {row[0] for row in conn.execute(_TABLES).fetchall()}

    def incarnation(self, database: str) -> str | None:
        """The database's incarnation: its name and its oid, so a recreated database
        is a new incarnation."""
        with self.connect(database) as conn:
            row = conn.execute("SELECT oid FROM pg_database WHERE datname = %s",
                               (database,)).fetchone()
        return None if row is None else f"{database}:{row[0]}"

    def database_bytes(self, database: str) -> int:
        """The database's size, indexes included, when it is dumped: a verification's
        internal-disk guard reads it before restoring the set (BR6.6)."""
        with self.connect(database) as conn:
            return int(conn.execute("SELECT pg_database_size(current_database())").fetchone()[0])

    def incarnations(self, database: str) -> set[str]:
        """Every incarnation that still exists in the instance."""
        with self.connect(database) as conn:
            rows = conn.execute("SELECT datname, oid FROM pg_database").fetchall()
        return {f"{name}:{oid}" for name, oid in rows}

    def create_scratch(self, maintenance: str, name: str, role: str) -> None:
        """`CREATE DATABASE` as the disposable-databases role, which then owns it."""
        with self.connect(maintenance) as conn:
            conn.execute(sql.SQL("SET statement_timeout = {}").format(
                sql.Literal(f"{STATEMENT_SECONDS}s")))
            conn.execute(sql.SQL("SET ROLE {}").format(sql.Identifier(role)))
            conn.execute(sql.SQL("CREATE DATABASE {} TEMPLATE template1").format(
                sql.Identifier(name)))


def _kill(child: subprocess.Popen) -> None:
    child.kill()
    child.wait()


def _ended(watch: RestoreWatch) -> int:
    """One `watch.end()`; a connection that fails ends nothing this tick, and the stop
    goes on to the client's signals, so the refusal still names its reason."""
    try:
        return watch.end()
    except (psycopg.Error, OSError):
        return 0


def _stop(child: subprocess.Popen, watch: RestoreWatch, reason: str) -> None:
    """Stop a watched restore: its sessions first, because the work is theirs (the server
    goes on building an index after its client dies, and in the composed realm the
    client runs inside the database container, which a signal to `docker exec` does not
    reach), at each tick until the client exits or `watch.grace` passes; then SIGTERM,
    `END_GRACE_SECONDS`, SIGKILL, and the sessions ended once more."""
    ended = 0
    grace_ends = time.monotonic() + watch.grace
    while child.poll() is None:
        left = grace_ends - time.monotonic()
        if left <= 0:
            break
        ended += _ended(watch)
        try:
            child.wait(timeout=min(watch.seconds, max(left, 0.001)))
        except subprocess.TimeoutExpired:
            pass
    if child.poll() is None:
        child.terminate()
        try:
            child.wait(timeout=END_GRACE_SECONDS)
        except subprocess.TimeoutExpired:
            _kill(child)
    ended += _ended(watch)
    raise AgentRefused(reason, sessionsEnded=ended)


class RuntimeTools(PgTools):
    """The release's pinned PostgreSQL client programs on this Mac."""

    def __init__(self, login: Login, password: str, *, bin_dir: Path):
        super().__init__(login, password)
        self.bin_dir = bin_dir

    def command(self, program: str, args: list[str]) -> list[str]:
        return [str(self.bin_dir / program), *args]


class ContainerTools(PgTools):
    """The composed realm: the client programs inside its database container, which
    reach the server on the container's own port; the password passes through the
    environment of `docker exec`."""

    PORT = 5432

    def __init__(self, login: Login, password: str, *, container: str):
        super().__init__(login, password)
        # The realm's database container, or the synthetic v1's (`<run>-v1-postgres`).
        if not re.fullmatch(r"docsuri-u8-[0-9a-f]{16}(-v1-postgres)?", container):
            raise ValueError("the realm's database container is named by its run")
        self.container = container

    def program_port(self) -> int:
        return self.PORT

    def environment(self) -> dict[str, str]:
        """As every client's, and DOCKER_HOST when this process holds it, so `docker exec`
        reaches the realm's Docker (U8 plan L1-76)."""
        environment = super().environment()
        if "DOCKER_HOST" in os.environ:
            environment["DOCKER_HOST"] = os.environ["DOCKER_HOST"]
        return environment

    def command(self, program: str, args: list[str]) -> list[str]:
        return ["docker", "exec", "-i", "-e", "PGPASSWORD", self.container, program, *args]

    @contextmanager
    def list_file(self, listing: str, beside: Path):
        """The list file inside the container's private `/tmp`, written with `dd` as the
        realm driver's production restore writes its listing; removed afterwards."""
        path = f"/tmp/docsuri-agent-restore-{secrets.token_hex(8)}.list"
        written = self._run("dd", [f"of={path}", "status=none"], payload=listing.encode(),
                            seconds=STATEMENT_SECONDS)
        if written.returncode != 0:
            raise AgentRefused("restore-list-unavailable")
        try:
            yield path
        finally:
            self._run("rm", ["-f", path], seconds=STATEMENT_SECONDS)


def v1_source(config: AgentConfig) -> dict | None:
    """v1's database as the agent's read-only login reaches it: its address and name."""
    if config.v1_login is None or config.v1_database is None:
        return None
    return {"host": config.v1_login.host, "port": config.v1_login.port,
            "database": config.v1_database}


def open_archive(path: Path):
    """An archive in the agent's folder, reached without following a link."""
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    return os.fdopen(descriptor, "rb")


class Databases:
    """The dump and restore commands over one configuration, its tools and its writer."""

    def __init__(self, config: AgentConfig, tools: PgTools, writer: ArchiveWriter, *,
                 v1_tools: PgTools | None = None, clock: Callable[[], dt.datetime],
                 monotonic: Callable[[], float] = time.monotonic,
                 floor: Callable[[], str | None] = _never,
                 watch_seconds: float = WATCH_SECONDS):
        self.config, self.tools, self.writer = config, tools, writer
        self.v1_tools, self.clock, self.monotonic = v1_tools, clock, monotonic
        # The critical floor: None, or the refusal key that stops a verification.
        self.floor, self.watch_seconds = floor, watch_seconds

    def _check_floor(self) -> None:
        reason = self.floor()
        if reason is not None:
            raise AgentRefused(reason)

    def _watch(self, scratch: str) -> RestoreWatch:
        """The watch over one scratch restore: the floor, and the agent's own sessions on
        `scratch` (already checked against its pattern) ended from the database
        `create_scratch` connects to."""
        maintenance = self.config.names.production
        return RestoreWatch(self.floor, lambda: self.tools.end_sessions(maintenance, scratch),
                            self.watch_seconds, STOP_GRACE_SECONDS, maintenance)

    def _dump_into(self, tools: PgTools, database: str, kind: str, record_id: str,
                   decided: Decided | None = None) -> dict:
        seen = tools.tables(database)
        incarnation = tools.incarnation(database)
        size = tools.database_bytes(database) if hasattr(tools, "database_bytes") else None
        receipt = self.writer.write(
            kind, record_id=record_id, fill=lambda sink: tools.dump(database, sink),
            integrity=lambda archive: seen <= tools.toc_tables(archive),
            incarnation=incarnation, decided=decided,
        )
        if size is not None:
            receipt["databaseBytes"] = size
        return receipt

    def backup(self, database: str, record_id: str) -> dict:
        """A live set from the production database, a rehearsal set from a rehearsal
        database; any other name is refused before any connection."""
        kind = self.config.names.kind_of(database)
        if kind == "production":
            return self._dump_into(self.tools, database, "live-set", record_id)
        if kind == "rehearsal":
            return self._dump_into(self.tools, database, "rehearsal-set", record_id)
        raise AgentRefused("database-refused")

    def rollback_copy(self, record_id: str, decided: Decided) -> dict:
        return self._dump_into(self.tools, self.config.names.production, "rolled-back-copy",
                               record_id, decided)

    def snapshot(self, kind: str, record_id: str, decided: Decided | None) -> dict:
        if kind not in ("dry-run-snapshot", "final-snapshot"):
            raise AgentRefused("kind-refused")
        if self.v1_tools is None or self.config.v1_database is None:
            raise AgentRefused("v1-not-configured")
        receipt = self._dump_into(self.v1_tools, self.config.v1_database, kind, record_id,
                                  decided)
        # Where the dump read v1 from, for the caller to check against the address it
        # names (the production migration platform).
        receipt["source"] = v1_source(self.config)
        return receipt

    def verify(self, scratch: str, set_kind: str, catalogue, record_id: str | None = None) -> dict:
        """Restore a passed set of `set_kind` into the new scratch database `scratch`,
        checked against the scratch pattern before any connection: the set whose record
        is `record_id` (a request names the set it verifies, Step 29), or else the
        newest passed one."""
        if not isinstance(scratch, str) or self.config.names.kind_of(scratch) != "scratch":
            raise AgentRefused("scratch-name-refused")
        if set_kind not in ("live-set", "rehearsal-set"):
            raise AgentRefused("kind-refused")
        self._check_floor()  # before any client program (U8 plan Step 121(b))
        chosen = newest_passed(catalogue, set_kind, record_id)
        if chosen is None:
            raise AgentRefused("no-passed-set")
        archive = self.config.u8_folder / chosen.path
        from .writing import file_digest

        if file_digest(archive) != chosen.sha256:
            raise AgentRefused("digest-mismatch")
        entries = self.tools.toc_entries(archive)
        self.tools.create_scratch(self.config.names.production, scratch,
                                  self.config.disposable_role)
        hnsw = [index for index, line in enumerate(entries) if HNSW_ENTRY.match(line)]
        result = {"scratchDatabase": scratch, "setPath": chosen.path,
                  "setSha256": chosen.sha256, "setRecordId": chosen.record_id}
        if not hnsw:
            with open_archive(archive) as source:
                self.tools.restore(source, scratch, self.config.disposable_role,
                                   watch=self._watch(scratch))
        else:
            result["hnswRebuildSeconds"] = self._restore_in_two_passes(
                archive, scratch, entries, set(hnsw))
        result["restoredAt"] = self.clock().astimezone(dt.UTC).isoformat()
        return result

    def _restore_in_two_passes(self, archive: Path, scratch: str, entries: list[str],
                               hnsw: set[int]) -> int:
        """Every entry but the HNSW index, in the archive's order, then the index alone,
        timed on the injected monotonic clock and rounded up to whole seconds (NFR9.4).
        Each pass is watched, and the floor is read again between them; a refusal there
        carries no `sessionsEnded`."""
        role = self.config.disposable_role
        first = "\n".join(f";{line}" if index in hnsw else line
                          for index, line in enumerate(entries)) + "\n"
        second = "\n".join(entries[index] for index in sorted(hnsw)) + "\n"
        with open_archive(archive) as source:
            self.tools.restore(source, scratch, role, listing=first,
                               beside=self.config.staging, watch=self._watch(scratch))
        self._check_floor()
        with open_archive(archive) as source:
            started = self.monotonic()
            self.tools.restore(source, scratch, role, listing=second,
                               beside=self.config.staging, watch=self._watch(scratch))
            elapsed = self.monotonic() - started
        return max(0, math.ceil(elapsed))


def newest_passed(catalogue, set_kind: str, record_id: str | None = None):
    """The newest written set of a kind whose integrity passed (of one record, when
    `record_id` names it)."""
    candidates = [
        entry for entry in catalogue.files().values()
        if entry.state in ("written", "held") and entry.integrity == "passed"
        and entry.path.startswith(f"archives/{set_kind}-")
        and (record_id is None or entry.record_id == record_id)
    ]
    return max(candidates, key=lambda entry: entry.path, default=None)


def stream(path: Path, sink: BinaryIO) -> None:
    with open_archive(path) as source:
        while block := source.read(CHUNK):
            sink.write(block)
