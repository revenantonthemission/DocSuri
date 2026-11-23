"""The arrangement driver: A6's effects on this Mac, through the fixed programs only
(U8 plan Step 27; D4, D6, security-design § 5.2–5.3).

Each effect is one fixed program in `/Library/DocSuri/release/ops/bin/`, run through
sudo as its account with one word from its closed set and any further input as bounded
JSON on standard input:

- in person, `sudo -k -u <account> <program> <word>`, so sudo asks for your password for
  each command and refreshes no cached authentication (D4);
- for the scheduler's standing grants, `sudo -n -u <account> <program> <word>`, which
  never prompts and fails unless the rule is `NOPASSWD`.

No generic command, path or shell is ever run. The program's one JSON result is the
effect's outcome; a refusal settles not-applied. The driver refuses every synthetic
profile (BR7.1).

The release command runs as root, and the backup agent refuses root for every word but
its first configuration. So a driver built `through` your login account (the release
command's) reaches the agent's `backup` and `ledger-copy` through your login's own
in-person grant, `sudo -u <you> /usr/bin/sudo -k -u _docsuri_r1t_backup <agent> <word>`:
the agent sees your login as its caller and asks for your password for each (your
decision of 2026-10-26, "Through your login"). The agent's caller rule is unchanged. A
driver running as root takes your login from the root-owned
`control/platform-authorities.json` (`actors.operator`), never from its own
configuration, which your login can write: a configured `operatorLogin` that differs
from it, and any service account (root, or a name beginning with `_`), is refused
before anything runs (review finding, Minor, R17).

Every program an effect runs, the production environment tool's words, the agent's
`stream-back` and v1's lifecycle apply included, runs under what is left of a bound below
its protocol's deadline (`program_bound`, counted from the effect's start, so the two
programs of a production restore share one bound): a program still running at the bound
is ended (SIGTERM, which sudo relays to it, then SIGKILL), so no program outlives its
receipt and answers late, after the receipt has settled unknown or been reconciled
(review finding, Minor, R16; Major, R21). The effect then fails `program-timed-out`, and
its receipt settles not applied.
"""

from __future__ import annotations

import json
import os
import re
import stat
import subprocess
import time
from collections.abc import Callable
from pathlib import Path

from . import DriverRefused, facts_of

BIN = Path("/Library/DocSuri/release/ops/bin")
SUDO = "/usr/bin/sudo"
PROGRAM_SECONDS = 3600
# After the bound: SIGTERM, which sudo relays to the program, then SIGKILL this long after.
PROGRAM_GRACE_SECONDS = 5
# The root-owned authority identities, the one source of your login for a root driver.
AUTHORITIES = Path("/Library/DocSuri/control/platform-authorities.json")
SERVICE, BACKUP, ROOT = "_docsuri_v2", "_docsuri_r1t_backup", "root"
# The agent's words the release command (root) reaches through your login (your
# decision of 2026-10-26, "Through your login"): the backup after writes stop and its
# ledger copy, nothing else.
THROUGH_LOGIN_WORDS = frozenset({"backup", "ledger-copy"})
LOGIN_NAME = re.compile(r"[a-z][a-z0-9_.-]{0,31}")


def _program(name: str) -> str:
    return str(BIN / name)


def program_bound(kind: str) -> float:
    """The bound a fixed program runs under for an effect of `kind`: below the deadline
    of every protocol of that effect kind (`inventory.json`), by a quarter of it up to
    five seconds, so the driver ends the program before U7's executor ends the adapter
    around it; `PROGRAM_SECONDS` for a word that is no effect's."""
    from docsuri_ops.u8_platform.u8_protocols import load_revision

    deadlines = [protocol.deadline_seconds for protocol in load_revision().u8
                 if protocol.effect_kind == kind]
    if not deadlines:
        return float(PROGRAM_SECONDS)
    deadline = min(deadlines)
    return max(1.0, deadline - min(float(PROGRAM_GRACE_SECONDS), deadline / 4))


def run_program(argv: list[str], *, input: bytes | None = None, timeout: float = PROGRAM_SECONDS,
                check: bool = False, capture_output: bool = False,
                **options) -> subprocess.CompletedProcess:
    """`subprocess.run` for a fixed program, with one difference: at `timeout` the
    program is ended, not only the `sudo` in front of it. SIGTERM goes to `sudo`, which
    relays it to the program; a program still there `PROGRAM_GRACE_SECONDS` later is
    killed. `TimeoutExpired` is raised as `subprocess.run` raises it."""
    if capture_output:
        options.update(stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    with subprocess.Popen(argv, stdin=subprocess.PIPE, **options) as process:
        try:
            stdout, stderr = process.communicate(input, timeout=timeout)
        except subprocess.TimeoutExpired:
            process.terminate()
            try:
                process.communicate(timeout=PROGRAM_GRACE_SECONDS)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate()
            raise
    completed = subprocess.CompletedProcess(argv, process.returncode, stdout, stderr)
    if check:
        completed.check_returncode()
    return completed


def read_root_authorities(path: Path = AUTHORITIES) -> dict | None:
    """`control/platform-authorities.json` as a root driver reads it: root-owned, a
    regular file writable by its owner only (`authorities-file-refused` otherwise), or
    None when it does not exist."""
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    except FileNotFoundError:
        return None
    except OSError:
        raise DriverRefused("authorities-file-refused") from None
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or (
                stat.S_IMODE(info.st_mode) & 0o022):
            raise DriverRefused("authorities-file-refused")
        with os.fdopen(descriptor, "rb") as stream:
            value = json.loads(stream.read(64 * 1024))
    except ValueError:
        raise DriverRefused("authorities-file-refused") from None
    if not isinstance(value, dict):
        raise DriverRefused("authorities-file-refused")
    return value


class ArrangementDriver:
    def __init__(self, config: dict, *, run: Callable = run_program,
                 lstat: Callable = os.lstat, release: Callable | None = None,
                 connect: Callable | None = None, through: str | None = None,
                 euid: Callable[[], int] = os.geteuid,
                 authorities: Callable[[], dict | None] = read_root_authorities):
        """`release` is the in-person credential release (D5) and `connect` the
        database connector; tests pass stand-ins for both. `through` is your login
        account's name; an operator driver running as root (the release command, and
        its effects' child) takes it from the root-owned authority identities
        (`authorities`, `control/platform-authorities.json`'s `actors.operator`), and
        refuses a configured `operatorLogin` that differs from it (review finding,
        Minor, R17)."""
        if config.get("kind") != "arrangement" or not config.get("production"):
            raise DriverRefused("arrangement-driver-refuses-synthetic")
        self._as_root = euid() == 0 and config.get("actor") == "operator"
        if self._as_root:
            if through is None:
                recorded = authorities()
                actors = recorded.get("actors") if isinstance(recorded, dict) else None
                through = actors.get("operator") if isinstance(actors, dict) else None
            configured = config.get("operatorLogin")
            if configured is not None and configured != through:
                raise DriverRefused("through-login-refused")
        if through is not None and (not isinstance(through, str) or through == ROOT
                                    or through.startswith("_")
                                    or not LOGIN_NAME.fullmatch(through)):
            raise DriverRefused("through-login-refused")
        self.config, self._run, self._lstat = config, run, lstat
        self._release, self._connect, self._through = release, connect, through
        self._bound = float(PROGRAM_SECONDS)
        # While an effect runs: the moment its bound ends, so each program it runs gets
        # what is left of the bound (review finding, Major, R21).
        self._deadline: float | None = None
        self._monotonic = time.monotonic

    def _remaining(self) -> float:
        """What is left of the effect's bound, at least one second; the whole program
        bound outside an effect (the migration's byte words, run by the operator tool's
        own steps)."""
        if self._deadline is None:
            return self._bound
        return max(1.0, self._deadline - self._monotonic())

    def _run_bounded(self, argv: list[str], **options) -> subprocess.CompletedProcess:
        """`self._run` with the effect's remaining bound as the timeout, whatever the
        caller asked for: no program an effect runs outlives its receipt."""
        return self._run(argv, **{**options, "timeout": self._remaining()})

    def command(self, account: str, program: str, word: str | None, *, via: str) -> list[str]:
        """The one invocation a sudo rule names exactly; from root, the agent's backup
        and ledger copy go through your login's own in-person grant first."""
        if via not in ("in-person", "standing"):
            raise DriverRefused("authority-refused")
        flag = "-k" if via == "in-person" else "-n"
        argv = [SUDO, flag, "-u", account, _program(program)]
        argv = argv if word is None else [*argv, word]
        if via != "in-person" or account != BACKUP or word not in THROUGH_LOGIN_WORDS:
            return argv
        if self._through is not None:
            return [SUDO, "-u", self._through, *argv]
        if self._as_root:
            # Root without your login named: the agent would refuse it anyway.
            raise DriverRefused("through-login-unconfigured")
        return argv

    def _invoke(self, account: str, program: str, word: str | None, document: dict | None, *,
                via: str) -> dict:
        """One fixed program run under the effect's bound (`program_bound`): one that is
        still running at the bound is ended and the effect refused `program-timed-out`,
        so no program answers after its receipt settled (review finding, Minor, R16)."""
        try:
            completed = self._run_bounded(
                self.command(account, program, word, via=via),
                input=json.dumps(document or {}).encode(), capture_output=True,
                check=False,
            )
        except subprocess.TimeoutExpired:
            raise DriverRefused("program-timed-out") from None
        stream = completed.stderr if program == "docsuri-backup-agent" and word in (
            "stream-back", "ledger-copy", "snapshot-stream") else completed.stdout
        try:
            result = json.loads(stream.decode().splitlines()[-1])
        except (ValueError, IndexError):
            raise ValueError("the fixed program answered no JSON result") from None
        if completed.returncode != 0 or not result.get("ok"):
            raise DriverRefused(str(result.get("reason", "program-refused")))
        return result

    # --- effects -------------------------------------------------------------------------

    def effect(self, kind: str, inputs: dict, *, context: dict) -> list[str]:
        handler = getattr(self, "_" + kind.replace("-", "_"), None)
        if handler is None:
            raise DriverRefused("unsupported-effect-kind")
        self._bound = program_bound(kind)
        self._deadline = self._monotonic() + self._bound
        try:
            return handler(inputs, context)
        finally:
            self._bound, self._deadline = float(PROGRAM_SECONDS), None

    def _database_backup(self, inputs, context):
        result = self._invoke(BACKUP, "docsuri-backup-agent", "backup",
                              {"database": inputs["database"], "recordId": inputs["recordId"]},
                              via=inputs["via"])
        return [f"backup-volume/{result['location']}", *facts_of(result)]

    def _database_restore(self, inputs, context):
        if inputs.get("mode") == "scratch":
            document = {"scratchDatabase": inputs["scratchDatabase"],
                        "setKind": inputs["setKind"]}
            if "recordId" in inputs:
                document["recordId"] = inputs["recordId"]
            result = self._invoke(BACKUP, "docsuri-backup-agent", "verify", document,
                                  via=inputs["via"])
            return [f"database/{result['scratchDatabase']}", *facts_of(result)]
        if inputs.get("mode") != "production" or inputs.get("via") != "in-person":
            raise DriverRefused("restore-mode-refused")
        # Workflow 7: the set streams back through the agent's in-person `stream-back`
        # into a private spool, its digest checked here; the production environment tool
        # checks it again and restores it with `pg_restore -j 2 --no-comments` as the
        # restore login, released in person (D5) and handed on through standard input.
        entry = {"path": inputs["setPath"], "sha256": inputs["setSha256"]}
        with self._streamed_back(entry) as spool:
            self._tool("restore-database", {
                "database": inputs["database"], "setPath": inputs["setPath"],
                "setSha256": inputs["setSha256"], "operationId": context["operationId"],
            }, login="restore", payload=spool.read_bytes())
        return [f"database/{inputs['database']}",
                *facts_of({"setPath": inputs["setPath"], "setSha256": inputs["setSha256"]})]

    def _database_recreate(self, inputs, context):
        document = {"database": inputs["database"], "operationId": context["operationId"]}
        if inputs.get("abandonment"):
            document["abandonment"] = True
        self._tool("recreate-database", document, login="operator")
        return [f"database/{inputs['database']}"]

    # --- the production environment tool and the streamed sets --------------------------

    def _tool(self, word: str, document: dict, *, login: str | None = None,
              payload: bytes | None = None) -> dict:
        """One in-person word of the production environment tool, with a login released
        in person first (D5); a refusal settles not-applied. The program runs under what
        is left of the effect's bound, not `invoke`'s own timeout (review finding,
        Major, R21): a `recreate-database`, `remove-database` or `restore-database` still
        running at the bound is ended and the effect refused `program-timed-out`, so no
        late recreate lands after its receipt settled and a later restore acted."""
        from docsuri_ops.production_tool import Refused, invoke

        try:
            return invoke(word, document, login=login, run=self._run_bounded, payload=payload,
                          release=self._release,
                          program=_program("docsuri-production-tool"))
        except Refused as refused:
            raise DriverRefused(refused.reason) from None
        except subprocess.TimeoutExpired:
            raise DriverRefused("program-timed-out") from None

    def _streamed_back(self, entry: dict):
        """The agent's in-person `stream-back` into a new private spool (0600), its digest
        checked against the record before use (BR4.3). It runs under what is left of the
        restore's bound, which the restore itself then shares (review finding, Major,
        R21); one still streaming at the bound is ended (`program-timed-out`)."""
        import contextlib
        import hashlib
        import tempfile

        @contextlib.contextmanager
        def spooled():
            folder = Path(tempfile.mkdtemp(prefix="docsuri-restore-"))
            spool = folder / "set.archive"
            try:
                argv = self.command(BACKUP, "docsuri-backup-agent", "stream-back", via="in-person")
                try:
                    completed = self._run_bounded(argv, input=json.dumps(entry).encode(),
                                                  capture_output=True, check=False)
                except subprocess.TimeoutExpired:
                    raise DriverRefused("program-timed-out") from None
                if completed.returncode != 0:
                    raise DriverRefused("stream-back-refused")
                data = completed.stdout or b""
                if hashlib.sha256(data).hexdigest() != entry["sha256"]:
                    raise DriverRefused("streamed-set-digest-mismatch")
                descriptor = os.open(spool, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                                     0o600)
                with os.fdopen(descriptor, "wb") as stream:
                    stream.write(data)
                yield spool
            finally:
                spool.unlink(missing_ok=True)
                folder.rmdir()

        return spooled()

    def _drop_as_scheduler(self, database: str) -> None:
        """The standing removal (BR9.17): through the scheduler account's own database
        login, a member of the disposable-databases role only, read from its private
        credentials file; the standing job runs as that account, so no sudo is needed."""
        from psycopg import sql

        from docsuri_ops.arrangement.paths import PRODUCTION_DATABASES

        if not PRODUCTION_DATABASES.is_disposable(database):
            raise DriverRefused("database-refused")
        path = Path(self.config.get("schedulerCredentials", ""))
        try:
            descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        except OSError:
            raise DriverRefused("scheduler-credentials-unavailable") from None
        with os.fdopen(descriptor, "rb") as stream:
            value = json.loads(stream.read(64 * 1024))
        login = value.get("database", {})
        connect = self._connect
        if connect is None:
            import psycopg

            connect = psycopg.connect
        with connect(host="127.0.0.1", port=int(self.config.get("databasePort", 15432)),
                     dbname="postgres", user=login.get("user"), password=login.get("password"),
                     require_auth="scram-sha-256", connect_timeout=5,
                     autocommit=True) as conn:
            conn.execute("SET statement_timeout = '600s'")
            conn.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(database)))

    def agent_word(self, word: str, document: dict, *, via: str) -> dict:
        """One of the agent's JSON words for the operator tool's own steps (a volume
        retirement's `prepare-volume`, `configure` and `status`, BR4.10)."""
        if word in ("stream-back", "ledger-copy", "snapshot-stream"):
            raise DriverRefused("byte-word-refused")
        return self._invoke(BACKUP, "docsuri-backup-agent", word, document, via=via)

    # --- the migration's byte words (the production migration platform) -------------------

    @staticmethod
    def _agent_result(stream: bytes, returncode: int) -> dict:
        try:
            result = json.loads((stream or b"").decode().splitlines()[-1])
        except (ValueError, IndexError):
            raise DriverRefused("agent-answered-no-result") from None
        if returncode != 0 or not result.get("ok"):
            raise DriverRefused(str(result.get("reason", "agent-refused")))
        return result

    def snapshot_stream(self, header: dict, payload: bytes) -> dict:
        """A snapshot's tar archive into the agent's in-person `snapshot-stream`: its
        header line, then the archive; the result comes on standard error."""
        argv = self.command(BACKUP, "docsuri-backup-agent", "snapshot-stream", via="in-person")
        completed = self._run(argv, input=json.dumps(header).encode() + b"\n" + payload,
                              capture_output=True, timeout=PROGRAM_SECONDS, check=False)
        return self._agent_result(completed.stderr, completed.returncode)

    def ledger_copy(self, stream: bytes, *, via: str) -> dict:
        """The ledger component's copy into the agent's `ledger-copy`: the bytes on its
        standard input, its one JSON result on standard error (BR6.10)."""
        argv = self.command(BACKUP, "docsuri-backup-agent", "ledger-copy", via=via)
        completed = self._run(argv, input=stream, capture_output=True,
                              timeout=PROGRAM_SECONDS, check=False)
        return self._agent_result(completed.stderr, completed.returncode)

    def stream_back(self, entry: dict, spool: Path) -> dict:
        """One catalogued file streamed back in person into a new private spool (0600),
        its digest checked against the record before use (BR4.3)."""
        import hashlib

        argv = self.command(BACKUP, "docsuri-backup-agent", "stream-back", via="in-person")
        spool.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        descriptor = os.open(spool, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(descriptor, "wb") as sink:
            completed = self._run(argv, input=json.dumps(entry).encode(), stdout=sink,
                                  stderr=subprocess.PIPE, timeout=PROGRAM_SECONDS, check=False)
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

    def _database_remove(self, inputs, context):
        if inputs["via"] == "standing":
            self._drop_as_scheduler(inputs["database"])
        else:
            self._tool("remove-database", {"database": inputs["database"],
                                           "operationId": context["operationId"]},
                       login="operator")
        return [f"database/{inputs['database']}"]

    def _service_control(self, inputs, context):
        program = "docsuri-service-stop" if inputs["action"] == "stop" else "docsuri-service-start"
        result = self._invoke(ROOT, program, inputs["label"],
                              {"receiptId": context["operationId"]}, via="in-person")
        loaded = result.get("wasLoaded")
        facts = facts_of({"wasLoaded": str(loaded).lower()}) if isinstance(loaded, bool) else []
        return [f"service/{inputs['label']}/{inputs['action']}", *facts]

    def _tunnel_route(self, inputs, context):
        self._invoke(ROOT, "docsuri-tunnel-route", inputs["origin"],
                     {"receiptId": context["operationId"]}, via="in-person")
        return [f"tunnel/{inputs['origin']}"]

    def _isolation_check(self, inputs, context):
        result = self._invoke(ROOT, "docsuri-isolation-check", None, None, via=inputs["via"])
        return [f"isolation/{result.get('evidence', 'recorded')}"]

    def _profile_change(self, inputs, context):
        self._invoke(SERVICE, "docsuri-profile", inputs["field"],
                     {"value": inputs["value"], "receiptId": context["operationId"]},
                     via="in-person")
        return [f"profile/{inputs['field']}"]

    def _copy_dispose(self, inputs, context):
        if inputs["place"] == "backup-volume":
            self._invoke(BACKUP, "docsuri-backup-agent", "dispose-event",
                         {"path": inputs["location"], "event": inputs["event"]}, via="in-person")
            return [f"backup-volume/{inputs['location']}"]
        if inputs["place"] == "database":
            return self._database_remove({"database": inputs["location"], "via": "in-person"},
                                         context)
        if inputs["place"] == "v1-stores":
            return self._v1_stores_gone(inputs["locations"])
        raise DriverRefused("place-refused")

    def _v1_stores_gone(self, locations: list[str]) -> list[str]:
        """v1's stores on this Mac, where the arrangement's configuration names them
        (`v1Stores`: location name to absolute path, your login account's), checked
        read-only: each must be gone. You delete them by hand; nothing here deletes
        anything (BR9.17)."""
        places = self.config.get("v1Stores") or {}
        refs = []
        for location in locations:
            path = places.get(location)
            if not isinstance(path, str) or not Path(path).is_absolute():
                raise DriverRefused("v1-store-location-refused")
            try:
                self._lstat(path)
            except FileNotFoundError:
                refs.append(f"{location}/absent")
                continue
            raise DriverRefused("v1-store-still-present")
        return refs

    def _v1_lifecycle_apply(self, inputs, context):
        """v1's own account code, with v1's runtime from v1's fixed checkout, under the
        effect's bound (review finding, Major, R21)."""
        runtime, checkout = self.config.get("v1Runtime"), self.config.get("v1Checkout")
        if not runtime or not checkout:
            raise DriverRefused("v1-runtime-unconfigured")
        try:
            completed = self._run_bounded(
                [*runtime, "-I", "-m", "backend.modules.accounts.services.v2_rollback_apply"],
                input=json.dumps({"outcomes": inputs["outcomes"],
                                  "accounts": inputs["accounts"]}).encode(),
                capture_output=True, cwd=checkout, check=False,
            )
        except subprocess.TimeoutExpired:
            raise DriverRefused("program-timed-out") from None
        if completed.returncode != 0:
            raise DriverRefused("v1-lifecycle-refused")
        return ["v1/lifecycle"]

    def _ledger_copy(self, inputs, context):
        """A lone ledger copy (L1-5, U8 plan Step 64(c)): the ledger component's `copy` as
        the service account, then the agent's `ledger-copy`, one after the other under the
        effect's bound. The component's copy is held in memory and handed to the agent on
        its standard input; it is never written to a file. Each answers its one JSON
        result on standard error."""
        via = inputs["via"]
        try:
            source = self._run_bounded(
                self.command(SERVICE, "docsuri-ledger", "copy", via=via),
                input=b"", capture_output=True, check=False)
        except subprocess.TimeoutExpired:
            raise DriverRefused("program-timed-out") from None
        ledger = self._agent_result(source.stderr, source.returncode)
        try:
            sink = self._run_bounded(
                self.command(BACKUP, "docsuri-backup-agent", "ledger-copy", via=via),
                input=source.stdout or b"", capture_output=True, check=False)
        except subprocess.TimeoutExpired:
            raise DriverRefused("program-timed-out") from None
        agent = self._agent_result(sink.stderr, sink.returncode)
        head = {"headSequence": ledger.get("count"), "headDigest": ledger.get("head")}
        return [f"backup-volume/{agent['location']}", *facts_of({**agent, **head})]

    def _decision_record(self, inputs, context):
        # The decision's effect is its receipt: it binds the operator, the step, the
        # subject reference and its digest; the effect record keeps the bound input.
        return [f"decisions/{context['operationId']}"]

    # --- reconciliation ------------------------------------------------------------------

    def observe(self, kind: str, inputs: dict) -> bool:
        """Unknown effects on this Mac are reconciled from their program's own records,
        which the effect record covers; nothing else is read or run here."""
        return False
