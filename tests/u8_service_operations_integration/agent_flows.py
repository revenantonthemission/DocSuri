"""The backup agent under a temporary folder (U8 plan Step 26).

`build` lays out a stand-in backup volume and the agent's own folder under `tmp_path`,
both private, prepares U8's folder on the volume and writes the agent's configuration
for the composed realm's names. `invoke` runs one command word the way its fixed
program does: through `cli.run`, with the caller the account sudo authenticated
(`SUDO_UID`). `FakeTools` stands in for the PostgreSQL client programs in the
component-level files and records every call, so a refusal "before any connection" is
seen as no call at all; the realm's own database is used in
`integration/test_backup_agent_restore.py`.

A watched restore (U8 plan Step 122(a)) is recorded in `FakeTools.watches`, never in
`calls`, whose exact tuples the agent tests compare, and `end_sessions` in `ended`.
`build` gives the agent an internal-disk reading of its own (`internal_free`, 100 GiB
unless a test says otherwise), so no agent test built here reads this Mac's free space;
a test that needs a changing reading sets `rig.context.internal_free` itself.
"""

from __future__ import annotations

import datetime as dt
import io
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4

from docsuri_ops.backup_agent import cli
from docsuri_ops.backup_agent.config import AgentConfig, Login, write
from docsuri_ops.backup_agent.disposal import prepare_volume
from docsuri_ops.backup_agent.status import StandinVolume

SCHEDULER, OPERATOR, SERVICE = 611, 501, 610
IDENTITY = "standin-volume-0001"
GIB = 1024**3
TABLES = {"accounts.account", "library.saved_paper"}


@dataclass
class FakeTools:
    """The client programs, recorded: `dump` writes a fixed body; the table of contents
    and the tables seen are configurable, so the integrity check can be made to fail."""

    seen: set[str] = field(default_factory=lambda: set(TABLES))
    listed: set[str] = field(default_factory=lambda: set(TABLES))
    living: set[str] = field(default_factory=set)
    calls: list[tuple] = field(default_factory=list)
    body: bytes = b"PGDMP-synthetic-dump\n"
    # The table of contents `pg_restore -l` prints (U8 plan Step 63(h)); None lists one
    # TABLE line for each table in `listed`.
    toc: list[str] | None = None
    # Each watched restore's (database, watch seconds, maintenance database), and each
    # `end_sessions` call's arguments (U8 plan Step 122(a)).
    watches: list[tuple] = field(default_factory=list)
    ended: list[tuple] = field(default_factory=list)

    def tables(self, database):
        self.calls.append(("tables", database))
        return set(self.seen)

    def incarnation(self, database):
        self.calls.append(("incarnation", database))
        return f"{database}:4242"

    def incarnations(self, database):
        self.calls.append(("incarnations", database))
        return set(self.living)

    def dump(self, database, sink):
        self.calls.append(("dump", database))
        sink.write(self.body + database.encode())

    def toc_tables(self, archive):
        self.calls.append(("toc", archive.name))
        return set(self.listed)

    def toc_entries(self, archive):
        self.calls.append(("toc-entries", archive.name))
        if self.toc is not None:
            return list(self.toc)
        return [f"{number}; 1259 {16000 + number} TABLE {name.replace('.', ' ')} docsuri_owner"
                for number, name in enumerate(sorted(self.listed), start=200)]

    def create_scratch(self, maintenance, name, role):
        self.calls.append(("create", name, role))

    def restore(self, source, database, role, *, listing=None, beside=None, watch=None):
        """Each restore is recorded with the `pg_restore -L` list it was given (None for
        a whole-archive restore); its watch, when one comes, in `watches`."""
        self.calls.append(("restore", database, role, len(source.read()), listing))
        if watch is not None:
            self.watches.append((database, watch.seconds, watch.maintenance))

    def end_sessions(self, maintenance, database):
        self.ended.append((maintenance, database))
        return 0


def ledger_copy_bytes(tmp_path: Path, clock) -> bytes:
    """A consistent copy of a ledger's chain, as `docsuri-ledger copy` streams it. Its
    folder is made with a plain `mkdir`, so build it once per test."""
    from backend.modules.operations.ledger import LedgerStore

    folder = tmp_path / "service-ledger"
    folder.mkdir(mode=0o700)
    store = LedgerStore.open(folder, clock=clock)
    try:
        store.append("note", {"n": 1})
        store.append("note", {"n": 2})
        sink = io.BytesIO()
        store.copy(sink)
        return sink.getvalue()
    finally:
        store.close()


@dataclass
class Rig:
    context: cli.AgentContext
    config: AgentConfig
    tools: FakeTools
    volume: Path
    clock: object

    @property
    def u8(self) -> Path:
        return self.config.u8_folder


def build(tmp_path: Path, clock, *, tools: FakeTools | None = None, free: int = 100 * GIB,
          backup_uid: int | None = None, container: str = "docsuri-u8-0000000000000000",
          login: Login | None = None, prefix: str = "docsuri_u8", real: bool = False,
          internal_free: int = 100 * GIB) -> Rig:
    """`real` keeps the agent's own client programs (the realm's database container)."""
    volume = tmp_path / "volume"
    volume.mkdir(mode=0o700)
    prepare_volume(volume, clock=clock)
    folder = tmp_path / "backup-agent"
    folder.mkdir(mode=0o700)
    config = AgentConfig(
        kind="realm", mount=volume, volume_identity=IDENTITY, database_prefix=prefix,
        v2_login=login or Login("127.0.0.1", 15509, "docsuri_backup_agent", "v2-login"),
        scheduler_uid=SCHEDULER, operator_uid=OPERATOR, service_uid=SERVICE,
        container=container,
    )
    write(folder, config)
    tools = tools or FakeTools()
    context = cli.AgentContext(
        folder, clock=clock, tools_factory=None if real else (lambda c, v1: tools),
        volume=StandinVolume(IDENTITY), free=lambda path: free,
        backup_uid=os.getuid() if backup_uid is None else backup_uid,
        internal_free=lambda: internal_free,
    )
    return Rig(context, config, tools, volume, clock)


def invoke(rig: Rig, word: str, document: dict | bytes | None = None, *,
           caller: int = OPERATOR, environ: dict | None = None) -> tuple[int, dict, bytes]:
    """One command word through the fixed program's shape; returns the exit status, the
    one JSON result and any bytes the word wrote to standard output."""
    if isinstance(document, bytes):
        raw = document
    else:
        raw = json.dumps(document or {}).encode()
    stdin, stdout, stderr = io.BytesIO(raw), io.BytesIO(), io.BytesIO()
    env = {"SUDO_UID": str(caller), **(environ or {})}
    status = cli.run([word], rig.context, environ=env, stdin=stdin, stdout=stdout,
                     stderr=stderr)
    result_stream = stderr if word in cli.BYTE_OUTPUT + cli.BYTE_INPUT else stdout
    lines = result_stream.getvalue().splitlines()
    payload = stdout.getvalue() if word in cli.BYTE_OUTPUT else b""
    return status, json.loads(lines[-1]), payload


def backed_up(rig: Rig, database: str = "docsuri_u8", record_id: str | None = None) -> dict:
    status, result, _ = invoke(rig, "backup", {"database": database,
                                                "recordId": record_id or str(uuid4())},
                               caller=SCHEDULER)
    assert status == 0, result
    return result


def advance(clock, seconds: float) -> dt.datetime:
    return clock.advance(seconds)
