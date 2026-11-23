"""`docsuri-backup-agent`: the backup agent's fixed command (U8 plan Step 25; BR4.3, BR6.6,
BR9.17, D6; Workflow 19's table).

It runs as the backup account through sudo. Its one argument is a command word, which
it checks again itself; any further input is bounded JSON on standard input (a
catalogue entry for `stream-back`, a decided date with its receipt and subject digest
for `set-date`, a mount point for `prepare-volume` and `configure`). `ledger-copy`
reads the ledger component's stream instead, and `stream-back` writes the file's bytes,
so those two write their one JSON result to standard error. It refuses to run when the
environment holds `PYTHON*`, `DYLD_*` or `LD_*` variables.

Who may run what (BR4.3; security-design § 5.2): the sudo rules are the first gate and
this is the second. The caller is the account sudo authenticated (`SUDO_UID`):

- the service account is refused every command;
- the scheduler account may run only the unattended words (`status`, `backup`,
  `ledger-copy`, `verify`, `dispose-due`);
- the operator account may run every word, in person;
- any other caller is refused; root may only write the first configuration.

Status, writing and deletion stop while the volume check fails, except that deletion
still runs when low free space is the only failure.

`verify` stops below the internal disk's critical floor (NFR7.18, NFR8.14; U8 plan Step
121, L2-8): the agent reads the free space of its own folder on the internal disk before
any client program, between its two passes and every few seconds while `pg_restore`
runs, and below `internal_disk_critical_bytes` (10 GiB, its own constant, never an
input) it ends its own sessions, stops its client and refuses `internal-disk-critical`.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import secrets
import shutil
import sys
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import BinaryIO
from uuid import UUID, uuid4

from . import agent_log
from .catalogue import Catalogue, CatalogueDamaged
from .config import AgentConfig, ConfigRefused, load, read_password, write
from .dumps import CRITICAL, WATCH_SECONDS
from .writing import AgentRefused, ArchiveWriter, Decided

UNATTENDED = ("status", "backup", "ledger-copy", "verify", "dispose-due")
IN_PERSON = ("snapshot", "snapshot-stream", "rollback-copy", "stream-back", "dispose-event",
             "set-date", "dispose-mismatch", "rebuild-catalogue", "prepare-volume",
             "configure")
WORDS = UNATTENDED + IN_PERSON
BYTE_OUTPUT = ("stream-back",)
BYTE_INPUT = ("ledger-copy", "snapshot-stream")
SNAPSHOT_PARTS = ("index", "objects")
SNAPSHOT_KINDS = ("dry-run-snapshot", "final-snapshot")
REFUSED_ENVIRONMENT = ("PYTHON", "DYLD_", "LD_")
MAX_INPUT = 64 * 1024
MAX_STREAM = 512 * 1024 * 1024
PRODUCTION_FOLDER = Path("/Library/DocSuri/backup-agent")
# The pinned runtime's client programs (`ArrangementPaths.postgres_runtime`); the earlier
# `runtimes/postgresql/` named a folder the installer never makes.
RUNTIME_BIN = Path("/Library/DocSuri/runtimes/postgresql-16.14/bin")


def _utc_now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def refused_environment(environ: Mapping[str, str]) -> bool:
    return any(name.startswith(REFUSED_ENVIRONMENT) for name in environ)


def caller_of(environ: Mapping[str, str]) -> int | None:
    value = environ.get("SUDO_UID", "")
    return int(value) if value.isdigit() else None


def _emit(stream: BinaryIO, value: dict, status: int) -> int:
    stream.write(json.dumps(value, sort_keys=True, separators=(",", ":")).encode() + b"\n")
    stream.flush()
    return status


def _bounded_json(stream: BinaryIO) -> dict:
    raw = stream.read(MAX_INPUT + 1)
    if len(raw) > MAX_INPUT:
        raise AgentRefused("input-too-large")
    try:
        value = json.loads(raw or b"{}")
    except ValueError:
        raise AgentRefused("input-not-json") from None
    if not isinstance(value, dict):
        raise AgentRefused("input-not-an-object")
    return value


def _record_id(document: dict) -> str:
    try:
        return str(UUID(str(document.get("recordId"))))
    except ValueError:
        raise AgentRefused("record-id-refused") from None


def _fields(document: dict, allowed: set[str]) -> None:
    if not set(document) <= allowed:
        raise AgentRefused("input-field-refused")


def admits(config: AgentConfig | None, word: str, caller: int | None) -> str | None:
    """The refusal reason for this caller and word, or None."""
    if caller is None:
        return "caller-unknown"
    if config is None:
        return None if (word == "configure" and caller == 0) else "agent-not-configured"
    if caller == config.service_uid:
        return "caller-refused"
    if caller == config.scheduler_uid:
        return None if word in UNATTENDED else "in-person-refused"
    if caller == config.operator_uid:
        return None
    return "caller-refused"


@dataclass
class AgentContext:
    """What one run of the agent works with; tests build it under a temporary folder."""

    folder: Path
    clock: Callable[[], dt.datetime] = _utc_now
    tools_factory: Callable | None = None
    volume: object | None = None
    free: Callable[[Path], int] | None = None
    backup_uid: int | None = None
    # The clock the scratch restore's HNSW pass is timed on (NFR9.4, U8 plan Step 62(d)).
    monotonic: Callable[[], float] = time.monotonic
    # The internal disk's free bytes, the critical floor's reading (U8 plan Step 121(c));
    # unset, `status.free_bytes` of the agent's own folder. Apart from `free`, the volume
    # check's reading.
    internal_free: Callable[[], int] | None = None
    disk_watch_seconds: float = WATCH_SECONDS

    def internal_free_bytes(self) -> int:
        if self.internal_free is not None:
            return self.internal_free()
        from .status import free_bytes

        return free_bytes(self.folder)

    def config(self) -> AgentConfig | None:
        try:
            return load(self.folder)
        except ConfigRefused as error:
            if str(error) == "the agent is not configured":
                return None
            raise

    def tools(self, config: AgentConfig, *, v1: bool = False):
        if self.tools_factory is not None:
            return self.tools_factory(config, v1)
        from .dumps import ContainerTools, RuntimeTools

        login = config.v1_login if v1 else config.v2_login
        password = read_password(self.folder, login)
        if config.kind == "realm":
            container = config.v1_container if v1 and config.v1_container else config.container
            if container is not None:
                return ContainerTools(login, password, container=container)
            # The native realm (the release's performance phase): the pinned runtime's
            # client programs, as production's are.
        return RuntimeTools(login, password, bin_dir=RUNTIME_BIN)


class Agent:
    def __init__(self, context: AgentContext, config: AgentConfig | None):
        self.context, self.config = context, config

    # --- shared pieces ---------------------------------------------------------------

    def _volume(self):
        from .status import volume_for

        return self.context.volume or volume_for(self.config)

    def status(self) -> dict:
        from .status import check, free_bytes

        return check(self.config, clock=self.context.clock, volume=self._volume(),
                     free=self.context.free or free_bytes, backup_uid=self.context.backup_uid)

    def _require(self, *, deleting: bool = False) -> None:
        status = self.status()
        if status["available"] or (deleting and status["deletionAllowed"]):
            return
        raise AgentRefused("volume-check-failed", findings=status["findings"])

    def _catalogue(self) -> Catalogue:
        try:
            return Catalogue.open(self.config.u8_folder, clock=self.context.clock)
        except (CatalogueDamaged, OSError):
            raise AgentRefused("backup-catalogue-damaged") from None

    def _writer(self, catalogue: Catalogue) -> ArchiveWriter:
        return ArchiveWriter(self.config, catalogue, clock=self.context.clock,
                             volume=self._volume())

    def _databases(self, catalogue: Catalogue):
        from .dumps import Databases

        v1 = self.context.tools(self.config, v1=True) if self.config.v1_login else None
        return Databases(self.config, self.context.tools(self.config),
                         self._writer(catalogue), v1_tools=v1, clock=self.context.clock,
                         monotonic=self.context.monotonic, floor=self._floor,
                         watch_seconds=self.context.disk_watch_seconds)

    def _floor(self) -> str | None:
        """`internal-disk-critical` while the internal disk's free space is below the
        critical floor, the agent's own constant (NFR7.18, NFR8.14)."""
        from backend.u8_policy import PRODUCTION_OPERATIONS

        if self.context.internal_free_bytes() < PRODUCTION_OPERATIONS.internal_disk_critical_bytes:
            return CRITICAL
        return None

    def _disposal(self, catalogue: Catalogue):
        from .disposal import Disposal

        tools = self.context.tools(self.config)
        return Disposal(self.config, catalogue, clock=self.context.clock,
                        incarnations=lambda: tools.incarnations(self.config.names.production))

    # --- the words ---------------------------------------------------------------------

    def run(self, word: str, stdin: BinaryIO, stdout: BinaryIO) -> dict:
        if word == "status":
            _fields(_bounded_json(stdin), set())
            return self.status()
        if word == "configure":
            return self.configure(_bounded_json(stdin))
        if word == "prepare-volume":
            from .disposal import prepare_volume

            document = _bounded_json(stdin)
            _fields(document, {"mount"})
            return prepare_volume(Path(str(document.get("mount", ""))), clock=self.context.clock)
        if word == "ledger-copy":
            return self.ledger_copy(stdin)
        if word == "snapshot-stream":
            return self.snapshot_stream(stdin)
        document = _bounded_json(stdin)
        if word in ("dispose-due", "dispose-event", "set-date", "dispose-mismatch",
                    "rebuild-catalogue"):
            return self._deletion(word, document)
        self._require()
        catalogue = self._catalogue()
        try:
            return self._write_or_read(word, document, catalogue, stdout)
        finally:
            catalogue.close()

    def _write_or_read(self, word: str, document: dict, catalogue: Catalogue,
                       stdout: BinaryIO) -> dict:
        if word == "backup":
            _fields(document, {"database", "recordId"})
            database = document.get("database")
            if not isinstance(database, str) or self.config.names.kind_of(database) not in (
                "production", "rehearsal"
            ):
                raise AgentRefused("database-refused")  # before any connection
            return self._databases(catalogue).backup(database, _record_id(document))
        if word == "verify":
            _fields(document, {"scratchDatabase", "setKind", "recordId"})
            scratch = document.get("scratchDatabase")
            if not isinstance(scratch, str) or self.config.names.kind_of(scratch) != "scratch":
                raise AgentRefused("scratch-name-refused")  # before any connection
            record = _record_id(document) if "recordId" in document else None
            return self._databases(catalogue).verify(scratch, document.get("setKind"),
                                                     catalogue, record)
        if word == "snapshot":
            _fields(document, {"kind", "recordId", "decided", "v1Source"})
            decided = Decided.parse(document["decided"]) if "decided" in document else None
            if "v1Source" in document:
                # The production migration platform names v1's database from the
                # environment file: any other address is refused before any connection
                # (the person's decision of 2026-10-24, "Build it, test on test v1").
                from .dumps import v1_source

                if document["v1Source"] != v1_source(self.config):
                    raise AgentRefused("v1-source-not-named")
            return self._databases(catalogue).snapshot(str(document.get("kind")),
                                                       _record_id(document), decided)
        if word == "rollback-copy":
            _fields(document, {"recordId", "decided"})
            return self._databases(catalogue).rollback_copy(
                _record_id(document), Decided.parse(document.get("decided")))
        from .reading import stream_back

        return stream_back(self.config, catalogue, document, stdout)

    def _deletion(self, word: str, document: dict) -> dict:
        if word == "rebuild-catalogue":
            from .disposal import rebuild_catalogue

            return rebuild_catalogue(self.config, document, clock=self.context.clock)
        self._require(deleting=True)
        catalogue = self._catalogue()
        try:
            disposal = self._disposal(catalogue)
            if word == "dispose-due":
                return disposal.dispose_due(document)
            if word == "dispose-event":
                _fields(document, {"path", "event"})
                return disposal.dispose_event(str(document.get("path")),
                                              str(document.get("event")))
            if word == "set-date":
                _fields(document, {"path", "decided"})
                return disposal.set_date(str(document.get("path")),
                                         Decided.parse(document.get("decided")))
            _fields(document, {"path"})
            return disposal.dispose_mismatch(str(document.get("path")))
        finally:
            catalogue.close()

    def ledger_copy(self, stdin: BinaryIO) -> dict:
        """Receive the ledger component's stream as a ledger copy; its integrity is its
        chain, which must verify up to its last entry (BR6.10)."""
        self._require()
        catalogue = self._catalogue()
        try:
            remaining = [MAX_STREAM]

            def fill(sink: BinaryIO) -> None:
                while block := stdin.read(1 << 20):
                    remaining[0] -= len(block)
                    if remaining[0] < 0:
                        raise AgentRefused("input-too-large")
                    sink.write(block)

            return self._writer(catalogue).write(
                "ledger-copy", record_id=str(uuid4()), fill=fill,
                integrity=lambda archive: ledger_chain_verifies(archive, self.config.staging,
                                                                self.context.clock),
            )
        finally:
            catalogue.close()

    def snapshot_stream(self, stdin: BinaryIO) -> dict:
        """A snapshot's directory tree (the search index's documents, or the selected
        objects with their manifest), in person: one JSON header line, then the tar
        archive. The kind comes from the header's snapshot kind and part alone, the
        written digest must equal the sender's, and the integrity is the archive's own
        member checksums (Workflow 19 step 3, U8 plan Step 31)."""
        from .archives import verify

        header_line = stdin.readline(MAX_INPUT + 1)
        if len(header_line) > MAX_INPUT or not header_line.endswith(b"\n"):
            raise AgentRefused("input-too-large")
        try:
            header = json.loads(header_line)
        except ValueError:
            raise AgentRefused("input-not-json") from None
        if not isinstance(header, dict):
            raise AgentRefused("input-not-an-object")
        _fields(header, {"kind", "recordId", "part", "sha256", "decided"})
        kind, part, sender = header.get("kind"), header.get("part"), header.get("sha256")
        if kind not in SNAPSHOT_KINDS or part not in SNAPSHOT_PARTS:
            raise AgentRefused("kind-refused")
        if not isinstance(sender, str) or len(sender) != 64:
            raise AgentRefused("sender-digest-required")
        decided = Decided.parse(header["decided"]) if "decided" in header else None
        self._require()
        catalogue = self._catalogue()
        try:
            remaining = [MAX_STREAM]

            def fill(sink: BinaryIO) -> None:
                while block := stdin.read(1 << 20):
                    remaining[0] -= len(block)
                    if remaining[0] < 0:
                        raise AgentRefused("input-too-large")
                    sink.write(block)

            return self._writer(catalogue).write(
                kind, record_id=_record_id(header), fill=fill, integrity=verify,
                sender_digest=sender, decided=decided, part=part,
            )
        finally:
            catalogue.close()

    def configure(self, document: dict) -> dict:
        """Write the agent's configuration (in person): the whole document the first
        time, then only the volume's mount point and identity (BR4.10)."""
        if self.config is None:
            config = AgentConfig.from_document(document)
        else:
            _fields(document, {"mount", "volumeIdentity"})
            config = replace(self.config, mount=Path(str(document.get("mount", ""))),
                             volume_identity=str(document.get("volumeIdentity", "")))
            AgentConfig.from_document(config.as_document())  # every check again
        write(self.context.folder, config)
        return {"configured": True, "mount": str(config.mount),
                "volumeIdentity": config.volume_identity}


def ledger_chain_verifies(archive: Path, staging: Path, clock) -> bool:
    """Whether a ledger copy's chain verifies: the copy is laid out as a ledger with the
    head its last entry records, in a private folder beside the staging files, and
    opened with the ledger's own verification."""
    from backend.modules.operations.errors import LedgerDamaged
    from backend.modules.operations.ledger import LedgerStore, canonical, entry_digest

    payload = archive.read_bytes()
    lines = payload[:-1].split(b"\n") if payload.endswith(b"\n") else []
    if not lines or not lines[-1]:
        return False
    folder = staging / f".verify-{secrets.token_hex(8)}"
    os.mkdir(folder, 0o700)
    try:
        for name, content in ((LedgerStore.LOG, payload),
                              (LedgerStore.HEAD, canonical({"count": len(lines),
                                                            "head": entry_digest(lines[-1])}))):
            descriptor = os.open(folder / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(content)
        try:
            LedgerStore.open(folder, clock=clock).close()
        except (LedgerDamaged, ValueError):
            return False
        return True
    finally:
        shutil.rmtree(folder, ignore_errors=True)


def run(argv: list[str], context: AgentContext, *, environ: Mapping[str, str],
        stdin: BinaryIO, stdout: BinaryIO, stderr: BinaryIO) -> int:
    """The fixed shape: an untouched environment, exactly one word, an admitted caller.
    Every run, refusals included, appends one line to the agent's own log (NFR9.8)."""
    started = time.monotonic()
    word = argv[0] if len(argv) == 1 and argv[0] in WORDS else None
    stream, value, status = _answer(argv, context, environ=environ, stdin=stdin,
                                    stdout=stdout, stderr=stderr)
    _emit(stream, value, status)
    agent_log.append(
        context.folder, word=word, reason=None if value.get("ok") else value.get("reason"),
        duration_ms=max(0, round((time.monotonic() - started) * 1000)),
    )
    return status


def _answer(argv: list[str], context: AgentContext, *, environ: Mapping[str, str],
            stdin: BinaryIO, stdout: BinaryIO,
            stderr: BinaryIO) -> tuple[BinaryIO, dict, int]:
    """The run's one result: where it goes, what it says and the exit status."""
    if refused_environment(environ):
        return stdout, {"ok": False, "reason": "environment-refused"}, 2
    if len(argv) != 1 or argv[0] not in WORDS:
        return stdout, {"ok": False, "reason": "word-refused"}, 2
    word = argv[0]
    result_stream = stderr if word in BYTE_OUTPUT + BYTE_INPUT else stdout
    try:
        config = context.config()
    except ConfigRefused:
        return result_stream, {"ok": False, "reason": "agent-config-refused"}, 1
    refusal = admits(config, word, caller_of(environ))
    if refusal is not None:
        return result_stream, {"ok": False, "reason": refusal}, 2
    previous = os.umask(0o077)
    try:
        result = Agent(context, config).run(word, stdin, stdout)
    except AgentRefused as refusal:
        return result_stream, {"ok": False, "reason": refusal.reason, **refusal.facts}, 1
    except ConfigRefused:
        return result_stream, {"ok": False, "reason": "agent-config-refused"}, 1
    finally:
        os.umask(previous)
    return result_stream, {"ok": True, **result}, 0


def main_fixed(argv: list[str] | None = None) -> int:
    """`ops/bin/docsuri-backup-agent`'s entry: one word, the agent's own folder."""
    return run(
        sys.argv[1:] if argv is None else argv, AgentContext(PRODUCTION_FOLDER),
        environ=os.environ, stdin=sys.stdin.buffer, stdout=sys.stdout.buffer,
        stderr=sys.stderr.buffer,
    )


def main_realm(argv: list[str]) -> int:
    """The composed realm's entry (the realm driver's, Step 27): the realm agent's own
    folder, then one word, in a process of its own as production's fixed program runs.
    It serves only a realm configuration; every other check is `run`'s."""
    if len(argv) != 2:
        return _emit(sys.stdout.buffer, {"ok": False, "reason": "word-refused"}, 2)
    context = AgentContext(Path(argv[0]))
    try:
        config = context.config()
    except ConfigRefused:
        config = None
    if config is None or config.kind != "realm":
        return _emit(sys.stdout.buffer, {"ok": False, "reason": "realm-entry-refused"}, 2)
    return run(argv[1:], context, environ=os.environ, stdin=sys.stdin.buffer,
               stdout=sys.stdout.buffer, stderr=sys.stderr.buffer)


if __name__ == "__main__":  # pragma: no cover - the fixed program is ops/bin/docsuri-backup-agent
    raise SystemExit(main_fixed())
