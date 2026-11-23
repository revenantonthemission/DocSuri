"""Production's wiring of the operator tool, the standing job and the release command
(U8 plan Step 37; BR4.2, BR6.10, BR9.17, D4, D5, security-design § 5.2–5.4).

Everything above it is shared with the composed realm; this module only puts the parts
together on this Mac:

- **The ledger through `docsuri-ledger`** (`LedgerClient`). Neither your login account nor
  the scheduler account can open the ledger, which belongs to the service account; each
  reads and writes it through the ledger component's fixed command, in person (`sudo -k`)
  or unattended (`sudo -n`). Reads come from a consistent copy (`docsuri-ledger copy`),
  folded locally; a write is `docsuri-ledger append` with its expected revision, so the
  component's own lock and receipt confirmation decide it. `atomic(step)` runs the step on
  a fresh copy, then sends all its appends as one batch tied to the head it read, which
  the component checks as one and writes with signals held back; a stale or refused
  batch wrote nothing, and the step runs again from a fresh copy.
- **The profile's state from the ledger** (`ledger_profile_state`). The mode, admission
  and current rehearsal database are read from the latest profile receipt in the ledger,
  never from the profile itself (BR9.17): the receipt's bound input hash decides which of
  the known values it set.
- **The operators.** In person, the operator tool's PlatformControl login is released
  (`docsuri-credential-release platform`, D5) and the actor is the account that release
  authenticated through sudo (`SUDO_UID`), which must be the installed operator; the
  release command reads its own `SUDO_UID` (`in_person_actor`). The standing authority
  uses the scheduler account's own credentials file.
- **The standing job** (`production_parts`), **the recovery words**
  (`production_procedures`), **the cutover commands** (`production_cutover_platform`) and
  **the release command** (`release_install`).
"""

from __future__ import annotations

import datetime as dt
import http.client
import json
import os
import pwd
import shutil
import subprocess
import tempfile
import threading
import urllib.request
from collections.abc import Callable
from pathlib import Path

from docsuri_ops.arrangement.paths import (
    DATABASE_ROLES,
    PRODUCTION_DATABASES,
    Accounts,
    ArrangementPaths,
)

SUDO = "/usr/bin/sudo"
PROGRAM_SECONDS = 1800
READY_URL = "http://127.0.0.1:18200/health/ready"
PUBLIC_ORIGIN = "https://docsuri.rvnnt.dev"
V1_API_HEALTH = "http://127.0.0.1:8000/health"
MAX_RESULT = 64 * 1024
ATTEMPTS = 3


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


class WiringRefused(RuntimeError):
    """A production part is not in place; the message is a fixed key."""


# --- the ledger through its fixed command ------------------------------------------------------


class _Capturing:
    """The local copy's locked view, with each append also captured for the remote one."""

    def __init__(self, view, captured: list):
        self._view, self._captured = view, captured

    def get(self, kind, key):
        return self._view.get(kind, key)

    def revision(self, kind, key):
        return self._view.revision(kind, key)

    def records(self, kind):
        return self._view.records(kind)

    def append(self, kind, record, *, expect_revision, receipts=()):
        appended = self._view.append(kind, record, expect_revision=expect_revision,
                                     receipts=receipts)
        self._captured.append((kind, record, expect_revision, list(receipts)))
        return appended


class LedgerClient:
    """The operations ledger, read and written through `docsuri-ledger` as the service
    account (`via` `in-person` or `standing`). The standing job's lanes share one client
    from their own threads (the agent status reads the ledger's identities beside the
    backup, U8 plan Step 66(f)), so one lock holds each read, append and fresh copy whole:
    no lane closes the local copy another is reading."""

    def __init__(self, *, via: str, clock: Callable[[], dt.datetime] = _now,
                 run: Callable = subprocess.run, paths: ArrangementPaths | None = None):
        if via not in ("in-person", "standing"):
            raise ValueError("the ledger is reached in person or by the standing authority")
        self.via, self.clock, self._run = via, clock, run
        self.paths = paths or ArrangementPaths()
        self._folder: Path | None = None
        self._local = None
        self._lock = threading.RLock()

    def _argv(self, word: str) -> list[str]:
        return [SUDO, "-k" if self.via == "in-person" else "-n", "-u",
                Accounts.standard().service.name, str(self.paths.release_bin / "docsuri-ledger"),
                word]

    def _call(self, word: str, document: dict) -> dict:
        completed = self._run(self._argv(word), input=json.dumps(document).encode(),
                              capture_output=True, timeout=PROGRAM_SECONDS, check=False)
        try:
            result = json.loads(completed.stdout[-MAX_RESULT:].decode().splitlines()[-1])
        except (ValueError, IndexError):
            raise WiringRefused("ledger-answered-no-result") from None
        return result

    def copy(self, sink) -> dict:
        completed = self._run(self._argv("copy"), input=b"", capture_output=True,
                              timeout=PROGRAM_SECONDS, check=False)
        try:
            result = json.loads(completed.stderr[-MAX_RESULT:].decode().splitlines()[-1])
        except (ValueError, IndexError):
            raise WiringRefused("ledger-copy-answered-no-result") from None
        if completed.returncode != 0 or not result.get("ok"):
            raise WiringRefused(str(result.get("reason", "ledger-copy-refused")))
        (sink.write if hasattr(sink, "write") else sink)(completed.stdout)
        return result

    def refresh(self):
        """A fresh copy, folded into a private local ledger."""
        with self._lock:
            return self._refresh()

    def _refresh(self):
        import io

        from backend.modules.operations.ledger import Ledger, LedgerStore, canonical
        from backend.modules.operations.ledger_cli import _copy_head

        self.close()
        stream = io.BytesIO()
        self.copy(stream)
        payload = stream.getvalue()
        folder = Path(tempfile.mkdtemp(prefix="docsuri-ledger-copy-"))
        count, head = _copy_head(payload) if payload else (0, "0" * 64)
        for name, content in ((LedgerStore.LOG, payload),
                              (LedgerStore.HEAD, canonical({"count": count, "head": head}))):
            descriptor = os.open(folder / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "wb") as target:
                target.write(content)
        self._folder = folder
        self._local = Ledger.open(folder, clock=self.clock)
        return self._local

    def _view(self):
        return self._local if self._local is not None else self.refresh()

    def get(self, kind, key):
        with self._lock:
            return self._view().get(kind, key)

    def revision(self, kind, key) -> int:
        with self._lock:
            return self._view().revision(kind, key)

    def records(self, kind) -> list[dict]:
        with self._lock:
            return self._view().records(kind)

    def events(self, kind) -> list[dict]:
        with self._lock:
            return self._view().events(kind)

    def _send(self, document: dict) -> dict:
        from backend.modules.operations.errors import OperationsError

        result = self._call("append", document)
        if result.get("ok"):
            return result
        if result.get("reason") in ("stale-revision", "stale-head"):
            raise OperationsError("STALE_REVISION", current=result.get("current"))
        raise OperationsError("CONFLICT", current={"reasonKey": result.get("reason")})

    def append(self, kind, record, *, expect_revision: int, receipts=()):
        with self._lock:
            result = self._send({"kind": kind, "record": record,
                                 "expectRevision": expect_revision, "receipts": list(receipts)})
            self.invalidate()
            return result

    def atomic(self, step):
        """`step` against a fresh copy, then all its appends sent as one batch, tied to
        the head the step's reads saw (`expectHead`): the ledger component checks them
        as one under its lock and writes them with signals held back (review findings,
        Major, R14; Minor, R18). So a guard spanning records (`release_blocker`, the
        recovery admission's live exclusion, a migration run already active, a
        successor's held predecessor) holds for every process, and no refusal or signal
        leaves a step half applied: anything appended since the copy refuses the whole
        batch `stale-head`, nothing of the step is written, and the step runs again on a
        fresh copy, at most `ATTEMPTS` times (review finding, Major, R12). Only a disk
        error between the component's writes can leave a prefix of the step committed,
        which the ledger's next open adopts."""
        with self._lock:
            return self._atomic(step)

    def _atomic(self, step):
        from backend.modules.operations.errors import OperationsError
        from backend.modules.operations.ledger_cli import MAX_BATCH

        for _attempt in range(ATTEMPTS):
            local = self.refresh()
            seen = local.head
            captured: list = []
            outcome = local.atomic(
                lambda view, captured=captured: step(_Capturing(view, captured)))
            if len(captured) > MAX_BATCH:
                # The component would refuse it: a step writes at most one batch, and a
                # caller with more records splits them into steps (review finding, Major,
                # R15). Nothing is sent.
                self.invalidate()
                raise OperationsError("CONFLICT",
                                      current={"reasonKey": "ledger-batch-too-large"})
            try:
                if captured:
                    self._send({"expectHead": {"count": seen.count, "head": seen.head},
                                "appends": [{"kind": kind, "record": record,
                                             "expectRevision": expected, "receipts": receipts}
                                            for kind, record, expected, receipts in captured]})
            except OperationsError as error:
                if error.code == "STALE_REVISION":
                    continue  # the batch wrote nothing: the step runs again
                raise
            finally:
                self.invalidate()
            return outcome
        raise OperationsError("CONFLICT", current={"reasonKey": "ledger-contended"})

    def invalidate(self) -> None:
        """Drop the local copy, closed with its folder, so the next read takes a fresh
        one (review fixes, batch 4): a copy dropped without `close()` kept its lock file
        descriptor open for the life of the standing job, one per write, and a copy kept
        across the job's own writes hid what other processes recorded."""
        self.close()

    def close(self) -> None:
        with self._lock:
            if self._local is not None:
                self._local.close()
                self._local = None
            if self._folder is not None:
                shutil.rmtree(self._folder, ignore_errors=True)
                self._folder = None


# --- the profile's state from the latest profile receipts --------------------------------------

PROFILE_OPERATIONS = {"mode": "platform.profile.mode", "admission": "platform.profile.admission",
                      "rehearsalDatabase": "platform.profile.rehearsal-database"}
DEFAULTS = {"mode": "rehearsal", "admission": "maintainer-only", "rehearsalDatabase": None}


def _candidates(ledger, field_name: str) -> list[dict]:
    if field_name == "mode":
        return [{"field": "mode", "value": value} for value in ("live", "rehearsal")]
    if field_name == "admission":
        found = [{"field": "admission", "value": "maintainer-only"}]
        found += [{"field": "admission", "value": "open", "approvalId": item["approvalId"]}
                  for item in ledger.records("maintainer-approval")
                  if item["step"] == "admission-opening"]
        return found
    names = {location.removeprefix("database/")
             for record in ledger.records("retained-copy")
             if record["kind"] == "rehearsal-database"
             for location in record["locations"] if location.startswith("database/")}
    return [{"field": "rehearsalDatabase", "value": value} for value in [None, *sorted(names)]]


def ledger_profile_state(ledger) -> dict:
    """Each field from the latest succeeded profile receipt the ledger holds: its bound
    input hash names the value it set. A receipt whose value cannot be named leaves the
    field unknown, which every precondition reads as refusing."""
    from docsuri_ops.u8_platform.drivers import input_hash

    facts = list(ledger.records("receipt-facts"))
    state = dict(DEFAULTS)
    for field_name, operation in PROFILE_OPERATIONS.items():
        latest = next((item for item in reversed(facts) if item["operation"] == operation
                       and item["outcome"] == "succeeded"), None)
        if latest is None:
            continue
        match = next((candidate for candidate in _candidates(ledger, field_name)
                      if input_hash(candidate) == latest["inputHash"]), None)
        state[field_name] = match["value"] if match is not None else "unknown"
    return state


def production_facts(ledger, *, clock: Callable[[], dt.datetime],
                     databases: Callable[[], set[str]] | None = None):
    """The facts production's operators read before each effect: the profile from the
    latest profile receipts, and the instance's disposable databases as the ledger
    records them (`recorded_databases`), so A6's "profile, database, sets" guard and
    NFR8.15's scratch limit refuse in production as they do in the realm."""
    from docsuri_ops.u8_platform.platform_profile import PRODUCTION_LABELS
    from docsuri_ops.u8_platform.u8_protocols import Facts, recorded_databases

    listed = databases or recorded_databases(ledger)

    def read() -> Facts:
        state = ledger_profile_state(ledger)
        return Facts(PRODUCTION_DATABASES, state["mode"], state["admission"],
                     state["rehearsalDatabase"], ledger, clock(), listed, PRODUCTION_LABELS)

    return read


# --- the operators ------------------------------------------------------------------------------


def _authorities(paths: ArrangementPaths) -> dict:
    try:
        return json.loads((paths.control / "platform-authorities.json").read_bytes())
    except (OSError, ValueError):
        raise WiringRefused("platform-authorities-not-installed") from None


def production_operator(ledger, *, clock: Callable[[], dt.datetime] = _now,
                        paths: ArrangementPaths | None = None, release: Callable | None = None,
                        actor: str | None = None,
                        released_as: Callable[[str], tuple[bytearray, str]] | None = None,
                        **options):
    """The operator tool in person: its PlatformControl login released in person (D5),
    the operator's routine and destructive grants. Its actor is the release command's
    `actor` when one is given, checked before the release; otherwise the account the
    release authenticated through sudo (D4), which must be the installed operator. The
    authority file is read first in both branches, so a Mac without the arrangement
    refuses before anything is released. A release that refuses (`ReleaseRefused`) is
    the wiring refusal `credential-not-released` in both branches, so every word answers
    it as its other wiring refusals; nothing was released, so nothing is wiped."""
    from docsuri_ops.platform_control import enums
    from docsuri_ops.u8_platform.credential_release import ReleaseRefused, release_with_actor
    from docsuri_ops.u8_platform.credential_release import release as release_login
    from docsuri_ops.u8_platform.platform_profile import U8PlatformProfile
    from docsuri_ops.u8_platform.u8_protocols import PRODUCTION_OPERATOR, Operator

    paths = paths or ArrangementPaths()
    recorded = _authorities(paths)
    if actor is not None:
        name = actor
        if name != recorded["actors"]["operator"]:
            raise WiringRefused("not-the-installed-operator")
        try:
            secret = (release or release_login)("platform")
        except ReleaseRefused:
            raise WiringRefused("credential-not-released") from None
    else:
        try:
            secret, name = (released_as or release_with_actor)("platform")
        except ReleaseRefused:
            raise WiringRefused("credential-not-released") from None
        if name != recorded["actors"]["operator"]:
            secret[:] = b"\0" * len(secret)
            raise WiringRefused("not-the-installed-operator")
    profile = U8PlatformProfile.production("operator", control=paths.control)
    try:
        store = profile.store(PRODUCTION_OPERATOR, secret.decode())
    finally:
        secret[:] = b"\0" * len(secret)
    grants = recorded["authorities"]
    return Operator(profile, store, actor=name,
                    authorities={enums.CLASS_ROUTINE: grants["operatorRoutine"],
                                 enums.CLASS_DESTRUCTIVE: grants["operatorDestructive"]},
                    facts=options.pop("facts", None) or production_facts(ledger, clock=clock),
                    **options)


def in_person_actor(paths: ArrangementPaths, environ, *,
                    lookup: Callable[[int], object] = pwd.getpwuid, owner_uid: int = 0) -> str:
    """The account sudo authenticated for an in-person command run as root (D4), which
    must be the installed operator, read through `fixed.installed_operator`: root-owned
    (`owner_uid`), unwritable by others and through no link. Root without sudo has no
    `SUDO_UID` and is refused."""
    from docsuri_ops.platform_control.errors import ControlError
    from docsuri_ops.u8_platform.fixed import Refused, installed_operator
    from docsuri_ops.u8_platform.in_person import actor_from_sudo

    try:
        name = actor_from_sudo(environ, lookup=lookup)
    except ControlError:
        raise WiringRefused("in-person-actor-refused") from None
    try:
        operator = installed_operator(paths, owner_uid=owner_uid)
    except Refused:
        raise WiringRefused("authorities-file-refused") from None
    if name != operator:
        raise WiringRefused("not-the-installed-operator")
    return name


def scheduler_credentials(paths: ArrangementPaths) -> dict:
    from docsuri_ops.platform_control.profile import private_bytes

    try:
        return json.loads(private_bytes(paths.scheduler_credentials))
    except (OSError, ValueError):
        raise WiringRefused("scheduler-credentials-unavailable") from None


def standing_operator(ledger, *, clock: Callable[[], dt.datetime] = _now,
                      paths: ArrangementPaths | None = None, **options):
    """The standing authority: the scheduler account's own PlatformControl login and its
    three grants (`SCHEDULER_GRANTS`), from its private credentials file."""
    from docsuri_ops.u8_platform.platform_profile import U8PlatformProfile
    from docsuri_ops.u8_platform.u8_protocols import (
        PRODUCTION_SCHEDULER,
        Operator,
        scheduler_authorities,
    )

    paths = paths or ArrangementPaths()
    value = scheduler_credentials(paths)
    profile = U8PlatformProfile.production("scheduler", control=paths.control)
    store = profile.store(PRODUCTION_SCHEDULER, value["platform"]["password"])
    return Operator(profile, store, actor=value["actor"],
                    **scheduler_authorities(value["authorities"]),
                    facts=options.pop("facts", None) or production_facts(ledger, clock=clock),
                    standing=True, **options)


def arrangement_driver(paths: ArrangementPaths, actor: str, **options):
    from docsuri_ops.u8_platform.drivers import load_config
    from docsuri_ops.u8_platform.drivers.arrangement import ArrangementDriver

    return ArrangementDriver(load_config(paths.effects / actor), **options)


# --- database logins for one bound operation ----------------------------------------------------


def _connector(user: str, password_of: Callable[[], str]):
    def connect(database: str):
        import psycopg

        return psycopg.connect(host="127.0.0.1", port=15432, dbname=database, user=user,
                               password=password_of(), require_auth="scram-sha-256",
                               connect_timeout=5, autocommit=True)

    return connect


def _released(login: str, release: Callable | None) -> Callable[[], str]:
    from docsuri_ops.u8_platform.credential_release import release as release_login

    def password() -> str:
        secret = (release or release_login)(login)
        try:
            return secret.decode()
        finally:
            secret[:] = b"\0" * len(secret)

    return password


def ready_probe(url: str = READY_URL, seconds: float = 10) -> Callable[[], bool]:
    def ready() -> bool:
        try:
            with urllib.request.urlopen(url, timeout=seconds) as answer:  # noqa: S310
                return answer.status == 200
        except OSError:
            return False

    return ready


# --- the recovery words and the standing job's procedures ---------------------------------------


def production_procedures(ledger, operator, *, role: str, clock: Callable[[], dt.datetime] = _now,
                          paths: ArrangementPaths | None = None, release: Callable | None = None,
                          policy=None, steps: Callable | None = None, driver=None):
    """Workflow 5–7's procedures on this Mac: the scratch checks and drops through the
    scheduler's login (standing) or the operator tool's (in person, released), the
    restore evaluation through the production environment tool, the agent's words and
    the ledger copy through the fixed programs."""
    from backend.modules.operations import restore_checks
    from backend.modules.operations.incidents import Incidents
    from backend.modules.operations.recovery import RecoveryRequests
    from backend.modules.operations.recovery_procedures import Platform, RecoveryProcedures
    from backend.modules.operations.tombstones import Tombstones
    from backend.u8_policy import PRODUCTION_OPERATIONS

    from docsuri_ops.production_tool import invoke
    from docsuri_ops.standing import macos as standing_macos
    from docsuri_ops.u8_platform.recovery_words import Wiring

    paths = paths or ArrangementPaths()
    policy = policy or PRODUCTION_OPERATIONS
    actor = "scheduler" if role == "scheduler" else "operator"
    driver = driver or arrangement_driver(paths, actor, release=release)
    if role == "scheduler":
        login = scheduler_credentials(paths)["database"]
        disposable = _connector(login["user"], lambda: login["password"])
    else:
        disposable = _connector(DATABASE_ROLES.operator, _released("operator", release))
    restorer = _connector(DATABASE_ROLES.restore, _released("restore", release))
    facts = operator.facts

    def scratch_checks(database: str, accounts: list[str]) -> dict:
        with disposable(database) as conn:
            checked = restore_checks.integrity(conn)
            replayed = restore_checks.replay(conn, accounts)
            return {**checked, **replayed, "surviving": restore_checks.surviving(conn, accounts)}

    def restore_evaluate(database: str, accounts: list[str]) -> dict:
        return invoke("restore-evaluate", {"database": database, "accounts": accounts},
                      login="restore", release=release)["result"]

    def production_integrity(database: str) -> dict:
        with restorer(database) as conn:
            return restore_checks.integrity(conn)

    def drop_scratch(database: str) -> None:
        from psycopg import sql

        if PRODUCTION_DATABASES.kind_of(database) != "scratch":
            raise ValueError("only a scratch database is dropped here")
        with disposable("postgres") as conn:
            conn.execute("SET statement_timeout = '600s'")
            conn.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(database)))

    def ledger_copy() -> dict:
        """The ledger copy beside a set (BR6.10). The standing job pipes the ledger
        component's copy into the agent's unattended `ledger-copy`. In person, the two
        run one after the other, each with `sudo -k`, so each asks for your password
        on its own (D4): the component's copy through the ledger client, then its bytes
        into the agent's `ledger-copy` (review finding, Critical, R15)."""
        if role == "scheduler":
            return standing_macos.ledger_copy(folder=paths.release_bin)
        import io

        stream = io.BytesIO()
        head = ledger.copy(stream)
        return {"agent": driver.ledger_copy(stream.getvalue(), via="in-person"), "head": head}

    platform = Platform(
        operator=operator, production=PRODUCTION_DATABASES.production,
        labels=("org.docsuri.v2.host", "org.docsuri.v2.workers", "org.docsuri.v2.scheduler"),
        scratch_name=lambda: PRODUCTION_DATABASES.new("scratch"),
        free_bytes=lambda: free_space(paths),
        scratch_checks=scratch_checks, restore_evaluate=restore_evaluate,
        production_integrity=production_integrity, drop_scratch=drop_scratch,
        ready=ready_probe(), rehearsal=lambda: facts().current_rehearsal,
        ledger_copy=ledger_copy, agent=driver.agent_word, **({"steps": steps} if steps else {}),
        # Live when the platform's mode is live, else rehearsal (U8 plan Step 64(h)).
        current_environment=lambda: "live" if facts().mode == "live" else "rehearsal",
    )
    requests = RecoveryRequests(ledger, policy, clock=clock)
    procedures = RecoveryProcedures(requests, platform, incidents=Incidents(ledger,
                                                                            environment="live"),
                                    tombstones=Tombstones(ledger), policy=policy, clock=clock)
    return Wiring(procedures, close=ledger.close)


def production_parts(ledger, *, clock: Callable[[], dt.datetime] = _now,
                     paths: ArrangementPaths | None = None, send=None):
    """The standing job on this Mac: the scheduler's grants, the arrangement driver's
    unattended agent words, the ledger through `docsuri-ledger` (`sudo -n`), the
    healthchecks.io addresses of `scheduler/healthchecks.json` and the probes of
    `docsuri.rvnnt.dev` and 127.0.0.1:18200."""
    from backend.u8_policy import PRODUCTION_OPERATIONS as policy

    from docsuri_ops.cutover.disposal import DisposalPass, DisposalPlatform
    from docsuri_ops.standing import heartbeat as heartbeats
    from docsuri_ops.standing.availability import AvailabilityRecord
    from docsuri_ops.standing.healthchecks import Healthchecks, load_addresses
    from docsuri_ops.standing.heartbeat import PRODUCTION_LOCAL, PRODUCTION_PUBLIC, Heartbeat
    from docsuri_ops.standing.housekeeping import Housekeeping, starts_pruner
    from docsuri_ops.standing.main import (
        AgentStatus,
        ScheduledRecovery,
        StandingParts,
        evidence_recorder,
        isolation_lane,
        ledger_identities,
    )

    paths = paths or ArrangementPaths()
    operator = standing_operator(ledger, clock=clock, paths=paths)
    driver = arrangement_driver(paths, "scheduler")
    procedures = production_procedures(ledger, operator, role="scheduler", clock=clock,
                                       paths=paths, policy=policy, driver=driver).procedures
    options = {} if send is None else {"send": send}
    checks = Healthchecks(load_addresses(paths.scheduler, production=True), **options)
    record = AvailabilityRecord(paths.availability, slot_seconds=policy.availability_slot_seconds)
    limit = policy.probe_limit_seconds
    heartbeat = Heartbeat(record, checks,
                          public=lambda: heartbeats.probe(PRODUCTION_PUBLIC, seconds=limit),
                          local=lambda: heartbeats.probe(PRODUCTION_LOCAL, seconds=limit))
    facts = operator.facts

    def serving() -> str:
        """The environment the standing job serves now (L1-65): the disposal pass's
        incidents and the standing job's requests read this one function."""
        return "live" if facts().mode == "live" else "rehearsal"

    disposal = DisposalPass(ledger, policy, DisposalPlatform(
        operator=operator, names=PRODUCTION_DATABASES, environment=serving,
        current_rehearsal=lambda: facts().current_rehearsal,
        dispose_due=lambda document: driver.agent_word("dispose-due", document, via="standing")),
        clock=clock).run
    agent = AgentStatus(lambda: driver.agent_word("status", {}, via="standing"),
                        evidence_recorder(operator.store, environment=operator.profile.environment,
                                          max_age_seconds=policy.provider_stale_seconds),
                        disposal, identities=ledger_identities(ledger))
    recovery = ScheduledRecovery(procedures.requests, procedures, checks,
                                 environment=serving, disposal=disposal, policy=policy)
    # The start record (NFR8.6, U8 plan Step 66(e)): /Library/DocSuri/scheduler/evidence/
    # starts/, 0700, pruned after 14 days by housekeeping.
    starts = paths.scheduler / "evidence" / "starts"
    housekeeping = Housekeeping(expire_requests=procedures.requests.expire_due,
                                delete_observations=lambda now: 0,
                                prune_availability=record.prune,
                                prune_starts=starts_pruner(starts))
    watch = heartbeats.StartWatch(
        starts, lambda: heartbeats.probe(PRODUCTION_LOCAL, seconds=limit), clock)
    return StandingParts(heartbeat, checks, agent, isolation_lane(operator), recovery,
                         housekeeping, policy, slot_seconds=policy.availability_slot_seconds,
                         start_watch=watch)


# --- the cutover commands -------------------------------------------------------------------------

VERIFICATION_RUN = "verification-run-{}.json"
FIRST_REHEARSAL = "first-rehearsal-database.json"
MAX_EVIDENCE = 64 * 1024


def release_evidence_folder(paths: ArrangementPaths) -> Path:
    """The release command's root-owned evidence (your decision of 2026-10-24): its
    VerificationRuns, written 0644, outside the profile."""
    return paths.control / "releases"


def _read_public_json(path: Path) -> dict | None:
    """A small root-written JSON file, never through a link or from a FIFO."""
    import stat as stat_module

    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError:
        return None
    try:
        info = os.fstat(descriptor)
        if not stat_module.S_ISREG(info.st_mode) or info.st_size > MAX_EVIDENCE:
            return None
        value = json.loads(os.read(descriptor, MAX_EVIDENCE))
    except (OSError, ValueError):
        return None
    finally:
        os.close(descriptor)
    return value if isinstance(value, dict) else None


def verification_reader(paths: ArrangementPaths) -> Callable[[str], dict | None]:
    """BR9.2's precondition 1: the VerificationRun the release command recorded,
    `control/releases/verification-run-<id>.json` (`verificationRunId`, `releaseTag`,
    `commit`, `passed`); one whose identifier differs from its name counts as none."""
    from uuid import UUID

    def read(run_id: str) -> dict | None:
        try:
            identity = str(UUID(str(run_id)))
        except ValueError:
            return None
        value = _read_public_json(release_evidence_folder(paths)
                                  / VERIFICATION_RUN.format(identity))
        if value is None or value.get("verificationRunId") != identity:
            return None
        return value

    return read


def named_rehearsal_reader(paths: ArrangementPaths) -> Callable[[], str | None]:
    """The first rehearsal database the installer's manifest names (phase 3 records its
    name, no secret, in `control/first-rehearsal-database.json`)."""

    def read() -> str | None:
        value = _read_public_json(paths.control / FIRST_REHEARSAL)
        name = None if value is None else value.get("database")
        return name if isinstance(name, str) and PRODUCTION_DATABASES.kind_of(
            name) == "rehearsal" else None

    return read


class OperatorTransactions:
    """Production's owner transactions as the operator tool reaches them in person: its
    released login on `docsuri_v2`, acting as the owner's role (`SET ROLE`, which the
    installer grants it for every owner), each read in its own read-only transaction.
    `RollbackOutcomes` reads AccountAccess's lifecycle facts through it."""

    def __init__(self, connect: Callable[[str], object],
                 database: str = PRODUCTION_DATABASES.production):
        self._connect, self.database = connect, database

    def run(self, owner: str, work: Callable):
        from psycopg import sql
        from psycopg.rows import dict_row

        with self._connect(self.database) as conn:
            conn.autocommit = False
            conn.row_factory = dict_row
            with conn.transaction():
                conn.execute("SET TRANSACTION READ ONLY")
                conn.execute(sql.SQL("SET LOCAL ROLE {}").format(
                    sql.Identifier(f"docsuri_{owner}_owner")))
                return work(conn)


def v1_account_reader(config: dict, *, connect: Callable | None = None):
    """v1's accounts read-only at the `v1Sources` database address (and no other), with
    your login's private credentials for v1's database named in the operator's
    environment file (`v1Accounts.credentials`, `{"user", "password"}`, 0600, yours):
    every account's identity, and the state of named ones, in read-only transactions."""
    from docsuri_ops.migration.production import V1Sources

    sources = V1Sources.from_config(config)
    named = (config.get("v1Accounts") or {}).get("credentials")
    if not isinstance(named, str) or not Path(named).is_absolute():
        raise WiringRefused("v1-accounts-credentials-unconfigured")

    def open_v1():
        import psycopg

        secret = _v1_login(Path(named))
        opener = connect or psycopg.connect
        return opener(host=sources.database["host"], port=sources.database["port"],
                      dbname=sources.database["database"], user=secret["user"],
                      password=secret["password"], connect_timeout=5,
                      options="-c default_transaction_read_only=on")

    def accounts() -> list[str]:
        with open_v1() as conn:
            return [str(row[0]) for row in conn.execute(
                "SELECT id::text FROM accounts ORDER BY id").fetchall()]

    def states(ids: list[str]) -> dict[str, str | None]:
        with open_v1() as conn:
            found = dict(conn.execute("SELECT id::text,status FROM accounts WHERE "
                                      "id::text = ANY(%s)", (list(ids),)).fetchall())
        return {item: found.get(item) for item in ids}

    return accounts, states


def _v1_login(path: Path) -> dict:
    """Your v1 database login file, with the object store credentials' custody checks
    (a regular file of yours, 0600 or tighter, never a link), `{"user", "password"}`."""
    import stat as stat_module

    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError:
        raise WiringRefused("v1-accounts-credentials-unreadable") from None
    try:
        info = os.fstat(descriptor)
        if not stat_module.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or (
                info.st_mode & 0o077) or info.st_size > 4096:
            raise WiringRefused("v1-accounts-credentials-refused")
        value = json.loads(os.read(descriptor, 4096))
    except ValueError:
        raise WiringRefused("v1-accounts-credentials-refused") from None
    finally:
        os.close(descriptor)
    if not isinstance(value, dict) or set(value) != {"user", "password"} or not all(
            isinstance(item, str) and item for item in value.values()):
        raise WiringRefused("v1-accounts-credentials-refused")
    return value


def operator_activation(ledger, *, clock: Callable[[], dt.datetime] = _now):
    """ProviderActivation over the ledger, for the operator tool (BR9.5, BR9.7): which
    providers are configured is read from their own records there (the operator cannot
    read the profile's private environment), and the maintainer is not needed to clear
    approvals for rehearsal."""
    from backend.modules.operations.provider_activation import (
        PROVIDERS,
        ActivationSettings,
        ProviderActivation,
    )

    configured = frozenset(
        provider for provider in PROVIDERS
        if (ledger.get("provider-activation", provider) or {}).get("state")
        not in (None, "unconfigured"))
    return ProviderActivation(ledger, ActivationSettings("rehearsal", None, configured),
                              clock=clock)


class OperatorActivation:
    """`operator_activation`, built from the ledger when an abort or a rollback clears
    the approvals (so building the platform reads nothing)."""

    def __init__(self, ledger, *, clock: Callable[[], dt.datetime] = _now):
        self.ledger, self.clock = ledger, clock

    def clear_approvals(self, *, mode: str = "rehearsal") -> dict[str, str]:
        return operator_activation(self.ledger, clock=self.clock).clear_approvals(mode=mode)


def v1_store_present(config: dict) -> Callable[[str], bool]:
    places = dict(config.get("v1Stores") or {})

    def present(location: str) -> bool:
        path = places.get(location)
        if not isinstance(path, str) or not Path(path).is_absolute():
            raise WiringRefused("v1-store-location-unconfigured")
        try:
            os.lstat(path)
        except FileNotFoundError:
            return False
        return True

    return present


def production_cutover_platform(ledger, operator, *, clock: Callable[[], dt.datetime] = _now,
                                paths: ArrangementPaths | None = None, policy=None,
                                steps: Callable | None = None, release: Callable | None = None,
                                stop_owner_uid: int = 0):
    """The cutover's platform on this Mac: the operator in person, the arrangement
    driver's agent words, the production probes, the isolation evidence folder and the
    operator's own evidence folder. `stop_owner_uid` is the account that owns the fixed
    programs' stop records (root; a test prefix's own account in tests)."""
    from backend.u8_policy import PRODUCTION_OPERATIONS

    from docsuri_ops.cutover.preconditions import SwitchEvidence
    from docsuri_ops.cutover.tool import (
        CutoverPlatform,
        V1Checkout,
        http_probe,
        ready_report,
        snapshot_parts_reader,
    )
    from docsuri_ops.cutover.tool import rehearsal_fingerprint_reader as fingerprints
    from docsuri_ops.isolation_check import receipt_held_by
    from docsuri_ops.migration.isolation_gate import IsolationGate
    from docsuri_ops.u8_platform.drivers import load_config
    from docsuri_ops.u8_platform.platform_profile import PRODUCTION_LABELS, V1_LABELS
    from docsuri_ops.u8_platform.service_words import (
        OperatorReceipts,
        planned_by_check,
        stop_expiries,
        stopped_v2_labels,
    )

    paths = paths or ArrangementPaths()
    policy = policy or PRODUCTION_OPERATIONS
    config = load_config(paths.effects / "operator")
    driver = arrangement_driver(paths, "operator", release=release)
    folder = paths.effects / "operator" / "evidence"
    facts = operator.facts
    procedures = production_procedures(ledger, operator, role="operator", clock=clock,
                                       paths=paths, release=release, policy=policy,
                                       driver=driver).procedures

    def first_backup(key: str) -> dict:
        from backend.modules.operations.recovery_procedures import OutcomeUnknown, ProcedureFailed

        from docsuri_ops.cutover.tool import StepFailed

        try:
            return procedures.take("live", "first-live", request=None, via="in-person",
                                   step="first-live", owner_key=key)
        except ProcedureFailed as failure:
            raise StepFailed(failure.reason) from None
        except OutcomeUnknown:
            raise StepFailed("effect-outcome-unknown") from None

    def missing_capabilities() -> list[str]:
        report = ready_report(READY_URL)
        if report is None:
            return ["readiness-unreadable"]
        return sorted({*report.get("missing", []), *report.get("degraded", [])})

    from docsuri_ops.cutover.tool import PUBLIC_PATHS as paths_of

    def migration():
        """The production migration platform's tool (the person's decision of
        2026-10-24), built when the switch reaches its final run."""
        from docsuri_ops.cutover.tool import StepFailed
        from docsuri_ops.migration.production import SourcesRefused, production_migration_tool
        from docsuri_ops.u8_platform.drivers import DriverRefused

        try:
            return production_migration_tool(ledger, operator, clock=clock, paths=paths,
                                             release=release)
        except (SourcesRefused, DriverRefused) as refused:
            raise StepFailed(refused.reason) from None
        except (WiringRefused, OSError):
            raise StepFailed("migration-platform-unavailable") from None

    def final_run(approval: str, dispose_after: dt.datetime) -> dict:
        from docsuri_ops.migration.production import final_run_for

        return final_run_for(migration())(approval, dispose_after)

    def final_decide(run_id: str, approval: str) -> dict:
        from docsuri_ops.migration.production import final_decide_for

        return final_decide_for(migration())(run_id, approval)

    def fail_final(run_id: str, reason: str) -> dict:
        """The migration tool's `fail`: a final run not yet accepted ends failed."""
        return migration().fail(run_id, reason)

    # The rollback's lifecycle facts, from AccountAccess's own tables through the
    # operator tool's released login acting as its owner role (read only).
    owners = OperatorTransactions(_connector(DATABASE_ROLES.operator,
                                            _released("operator", release)))

    def lifecycle_outcomes(since: dt.datetime) -> list[dict]:
        from backend.modules.accounts.services.rollback_outcomes import RollbackOutcomes

        return RollbackOutcomes(owners).latest_outcomes(since)

    def v2_writes(since: dt.datetime) -> dict[str, int]:
        from backend.modules.accounts.services.rollback_outcomes import RollbackOutcomes

        return RollbackOutcomes(owners).changes_since(since)

    def v1_reads():
        try:
            return v1_account_reader(config)
        except Exception as refused:  # noqa: BLE001 - a part not in place, as its key
            from docsuri_ops.cutover.tool import StepFailed

            raise StepFailed(getattr(refused, "reason", None) or str(refused)
                             or "v1-accounts-unwired") from None

    def create_rehearsal(name: str) -> dict:
        from uuid import uuid4

        from docsuri_ops.production_tool import invoke

        return invoke("create-disposable", {"database": name, "operationId": str(uuid4())},
                      login="operator", release=release)["result"]

    def soak_latency(start: dt.datetime, end: dt.datetime) -> dict:
        """The host's latency lines, which `profile/evidence/` keeps from the operator
        (0700, the service account's): the production tool's read-only
        `latency-summaries`, in person (U8 plan Step 70(d), L1-59)."""
        from backend.modules.operations.ledger import utc_text

        from docsuri_ops.production_tool import invoke

        return invoke("latency-summaries", {"from": utc_text(start), "until": utc_text(end)},
                      release=release)["result"]

    def provider_word(word: str, document: dict) -> dict:
        """The cutover's three provider words (U8 plan Step 106(f), CP-3): the production
        tool's in-person words of the same names, as the service account, since the
        previews and the profile's live settings are that account's. No login: the
        words open no database. A refusal reaches the caller by its reason."""
        from backend.modules.operations.errors import OperationsError

        from docsuri_ops.production_tool import Refused, invoke

        try:
            return invoke(word, document, release=release)["result"]
        except Refused as refused:
            raise OperationsError("CONFLICT", current={"reasonKey": refused.reason}) from None

    def release_tag() -> str | None:
        """The installed release's tag: its install record, or for the release the
        installer staged (no install record yet) the identity file `release` points to."""
        from backend.modules.operations.release_records import ReleaseRecords

        from docsuri_ops.release import linked_identity

        installed = ReleaseRecords(ledger, clock=clock).installed()
        if installed is not None:
            return installed.get("releaseTag")
        return (linked_identity(paths) or {}).get("tag")

    checkout = config.get("v1Checkout")
    evidence = SwitchEvidence(
        verification=verification_reader(paths),
        v1_checkout=V1Checkout(Path(checkout), ()) if checkout else (lambda: None),
        rehearsal_fingerprint=fingerprints(folder),
        agent_status=lambda: driver.agent_word("status", {}, via="in-person"),
        service_volume=lambda: "mounted" if Path("/Volumes/DocSuri_Backup").is_dir()
        else "unavailable",
        isolation=IsolationGate(paths.isolation_evidence,
                                freshness_seconds=policy.isolation_freshness_seconds,
                                clock=clock),
        rehearsal_database=lambda: facts().current_rehearsal,
        # The release the links point to: no soak or switch for another tag (review
        # finding, Major, R13).
        linked_release=lambda: linked_release(paths),
    )
    return CutoverPlatform(
        operator=operator, production=PRODUCTION_DATABASES.production,
        v1_labels=tuple(label for label in PRODUCTION_LABELS if label in V1_LABELS),
        v2_labels=("org.docsuri.v2.host", "org.docsuri.v2.workers", "org.docsuri.v2.scheduler"),
        v2_ready=ready_probe(), v1_ready=lambda: http_probe(V1_API_HEALTH) == 200,
        public=lambda kind: http_probe(PUBLIC_ORIGIN + paths_of[kind]) == 200,
        evidence=evidence, evidence_folder=folder, capabilities_missing=missing_capabilities,
        agent=driver.agent_word, first_backup=first_backup,
        rehearsal_copy=lambda: facts().current_rehearsal,
        v1_store_present=v1_store_present(config), final_run=final_run,
        final_decide=final_decide, fail_final=fail_final,
        lifecycle_outcomes=lifecycle_outcomes, v2_writes=v2_writes,
        v1_accounts=lambda: v1_reads()[0](), v1_states=lambda ids: v1_reads()[1](ids),
        activation=OperatorActivation(ledger, clock=clock),
        release_tag=release_tag, named_rehearsal=named_rehearsal_reader(paths),
        create_rehearsal=create_rehearsal, **({"steps": steps} if steps else {}),
        soak_latency=soak_latency, provider_word=provider_word,
        snapshot_parts=snapshot_parts_reader(folder / "migration", ledger, policy, clock),
        # Each stop record's `planned`, computed as the isolation check computes it, its
        # receipt read through the operator's own grants (the review's fix of 2026-10-26).
        stop_records=lambda: stop_expiries(
            paths.control_stops, PRODUCTION_LABELS, now=clock(),
            planned=planned_by_check(owner_uid=stop_owner_uid,
                                     held=receipt_held_by(OperatorReceipts(operator)),
                                     now=clock)),
        stopped_labels=lambda: stopped_v2_labels(paths.control_stops, PRODUCTION_LABELS),
        release_unprobed=lambda: unprobed_release(ledger, paths, clock=clock),
        # The release command's run marker, read without a password and without locking
        # anything, right where a word acts (your decision of 2026-10-26, "Check the
        # release run lock").
        release_run=lambda: release_run_held(paths),
    )


def release_run_held(paths: ArrangementPaths) -> str | None:
    """`release-run-active` while a `docsuri-release` command runs, read from its run
    marker (`release.release_run_active`), else None; a marker left by a command that
    died refuses too (`release-run-marker-stale`)."""
    from docsuri_ops.release import release_run_active

    return release_run_active(paths)


def linked_release(paths: ArrangementPaths) -> str | None:
    """The tag of the release `release` points to (`release.linked_tag`), or None."""
    from docsuri_ops.release import linked_tag

    return linked_tag(paths)


def unprobed_release(ledger, paths: ArrangementPaths, *,
                     clock: Callable[[], dt.datetime] = _now) -> str | None:
    """The linked release's tag while its install record waits for its probe (installed
    while v2 was kept stopped, the person's decision of 2026-10-25), else None."""
    from docsuri_ops.release import unprobed_tag

    return unprobed_tag(ledger, paths, clock=clock)


# --- the migration's import phases (`docsuri-migration-import`) ---------------------------------

IMPORT_HEADER = frozenset({"login", "runId", "importDatabase", "targetDatabase", "decisions",
                           "final", "required", "archives", "toWrite", "skipPapers"})


def free_space(paths: ArrangementPaths) -> int:
    """Production's one free-space reader (U8 plan Step 68(b)): the bytes an unprivileged
    process may still write under the prefix, `f_bavail × f_frsize`."""
    return shutil.disk_usage(paths.prefix).free


def _archives(header: dict, payload: bytes) -> dict:
    """The snapshot's two tar archives after the header, each checked against its
    manifest's member checksums before use (BR4.3)."""
    from backend.modules.operations.migration.v1_source import split_objects

    from docsuri_ops.backup_agent.archives import ArchiveRefused, unpack_bytes

    sizes = header.get("archives")
    if not isinstance(sizes, dict) or set(sizes) != {"index", "objects"} or any(
        type(value) is not int or value < 0 for value in sizes.values()
    ) or sizes["index"] + sizes["objects"] != len(payload):
        raise ValueError("archives-refused")
    index, objects = payload[: sizes["index"]], payload[sizes["index"]:]
    try:
        documents = unpack_bytes(index) if index else {}
        stored = unpack_bytes(objects) if objects else {}
    except ArchiveRefused:
        raise ValueError("archive-member-checksum-differs") from None
    # The bucket's listing, the objects part's reserved member (Step 68(c)).
    members, listing = split_objects(stored)
    return {"index_documents": [json.loads(line) for line in documents.get(
        "documents.jsonl", b"").splitlines() if line.strip()], "objects": members,
        "listing": listing}


def _skip_papers(header: dict) -> list[str]:
    value = header.get("skipPapers") or []
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError("header-refused")
    return value


def production_import(word: str, header: dict, payload: bytes, *, profile=None,
                      connect: Callable | None = None, embedder=None,
                      clock: Callable[[], dt.datetime] = _now,
                      free_bytes: Callable[[], int] | None = None) -> dict:
    """One import phase as the service account on this Mac (BR8.2, BR8.4): the four
    owners' import operations on the run's target database under trusted composition
    authority, reading v1's records from the run's import database through the operator
    tool's login (released in person and handed on in the header), with the pinned
    embedder in batches of 16. `idempotency` reports what a second pass would change,
    without asking again for the papers `skipPapers` names (Step 68(h)). `import` stops
    at the disk guard's next boundary (S3, Step 68(b)) and answers `{"interrupted":
    <reason>}`; `free_bytes` defaults to `free_space`."""
    import dataclasses

    from backend.artifacts import PrivateArtifacts
    from backend.modules.corpus.limits import PRODUCTION_LIMITS
    from backend.modules.discovery.u8_search import VECTOR_POLICY
    from backend.modules.operations.migration import parity
    from backend.modules.operations.migration.misfits import Decisions
    from backend.modules.operations.migration.phases import ImportRun, Owners
    from backend.modules.operations.migration.v1_source import V1Source
    from backend.transactions import OwnerTransactions
    from backend.u8_policy import PRODUCTION_OPERATIONS
    from backend.u8_profile import ProductionProfile
    from psycopg.rows import dict_row

    from docsuri_ops.migration.disk_guard import DiskGuard, DiskStopped

    if not set(header) <= IMPORT_HEADER or not {"login", "runId", "importDatabase",
                                                 "targetDatabase", "archives"} <= set(header):
        raise ValueError("header-refused")
    to_write = header.get("toWrite")
    if word == "import" and (type(to_write) is not int or to_write < 0):
        raise ValueError("header-refused")
    skip = _skip_papers(header) if word == "idempotency" else []
    login = header["login"]
    if not isinstance(login, dict) or not isinstance(login.get("password"), str):
        raise ValueError("released-login-required")
    names = PRODUCTION_DATABASES
    if names.kind_of(str(header["importDatabase"])) != "import" or names.kind_of(
        str(header["targetDatabase"])
    ) not in ("rehearsal", "production"):
        raise ValueError("database-refused")
    source = _archives(header, payload)
    profile = profile or ProductionProfile.load(ArrangementPaths().profile / "environment.json",
                                                service_uid=Accounts.standard().service.uid)
    if not getattr(profile, "is_production", False):
        raise ValueError("production-profile-only")
    decisions = Decisions.from_records(header.get("decisions") or [])
    if header.get("final"):
        decisions = decisions.for_final_run()
    release_observed: Callable[[], None] | None = None
    if embedder is None:
        embedder, release_observed = _pinned_embedder(profile, clock)
    target = dataclasses.replace(profile, database_name=str(header["targetDatabase"]))
    # § 3.1's migration tool row (Step 51(c), L1-13): the import runs under its own gate.
    transactions = OwnerTransactions(target, process="migration")
    try:
        files = PrivateArtifacts.for_profile(profile, "corpus-files",
                                             maximum_bytes=PRODUCTION_LIMITS.max_source_bytes)
        owners = Owners.for_target(transactions, files=files, limits=PRODUCTION_LIMITS,
                                   embedder=embedder, vector_policy=VECTOR_POLICY)
        opener = connect or __import__("psycopg").connect
        # The import database lives in the target profile's own instance (Step 51(e)):
        # 15432 in production, the realm's port on the production stand-in.
        with opener(host="127.0.0.1", port=target.database_port,
                    dbname=str(header["importDatabase"]),
                    user=DATABASE_ROLES.operator, password=login["password"],
                    require_auth="scram-sha-256", connect_timeout=5, autocommit=True,
                    row_factory=dict_row) as conn:
            boundary = None
            if word == "import":
                def held() -> int:
                    # Each login measures only its own database.
                    def size(cursor) -> int:
                        row = cursor.execute(
                            "SELECT pg_database_size(current_database()) AS bytes").fetchone()
                        return int(row["bytes"])

                    return size(conn) + transactions.run("corpus", size)

                guard = DiskGuard(free_bytes or (lambda: free_space(ArrangementPaths())),
                                  PRODUCTION_OPERATIONS.internal_disk_threshold_bytes,
                                  PRODUCTION_OPERATIONS.internal_disk_critical_bytes)
                boundary = guard.boundary(to_write=to_write, held=held)
            try:
                tallies = ImportRun(V1Source(conn, **source), owners, decisions, clock=clock,
                                    boundary=boundary, skip_papers=skip).run()
            except DiskStopped as stopped:
                return {"interrupted": stopped.reason}
        changed = sum(tally.imported + tally.updated for tally in tallies.values())
        if word == "idempotency":
            return {"changed": changed}
        misfits = [list(item) for tally in tallies.values() for item in tally.misfits]
        required = {tuple(pair) for pair in header.get("required") or []}
        fresh = ({(kind, reason) for kind, _, reason in misfits} - required
                 if header.get("final") else set())
        report = parity.build(str(header["runId"]), tallies, owners, now=clock(),
                              new_in_final=fresh)
        return {"misfits": misfits, "newInFinal": sorted([list(pair) for pair in fresh]),
                "report": report, "changed": changed}
    finally:
        transactions.close()
        if release_observed is not None:
            release_observed()


def _pinned_embedder(profile, clock: Callable[[], dt.datetime]):
    """The import's pinned embedder on the shared model runtime, and what closes its
    state reader. The runtime reads provider.models' stored state from the profile's own
    database before every request (reliability-design § 10; L4-11): the newest
    observation, `unknown` with none or an unreadable store, `stale` past 900 s. While
    it reads `unavailable` the runtime sends nothing and raises `ProviderHeld`, which
    ends the run through the import program's handler as `{"ok": false, "reason":
    "provider-held"}`, as an unreachable runtime ends it."""
    from backend.modules.discovery.local_embedding import LocalEmbeddings
    from backend.modules.operations.readiness import stored_state_reader
    from backend.modules.summarization.model_runtime import SharedModelRuntime
    from backend.u8_outward import EMBEDDING_BATCH, EMBEDDING_KEEP_ALIVE, QUERY_SECONDS
    from backend.u8_policy import PRODUCTION_OPERATIONS

    observed, release = stored_state_reader(profile, "provider.models", clock,
                                            PRODUCTION_OPERATIONS, process="migration")
    embedder = LocalEmbeddings(SharedModelRuntime(observed=observed),
                               keep_alive=EMBEDDING_KEEP_ALIVE,
                               query_seconds=QUERY_SECONDS, batch=EMBEDDING_BATCH)
    return embedder, release


# --- the release command -------------------------------------------------------------------


class GitHubReader:
    """GitHub's public API, read without a token (cicd-pipeline § 5.1 step 1)."""

    def __init__(self, fetch: Callable[[str], bytes], repository: str):
        self.fetch, self.api = fetch, f"https://api.github.com/repos/{repository}"

    def _json(self, path: str):
        return json.loads(self.fetch(self.api + path))

    def tag(self, tag: str) -> dict | None:
        try:
            reference = self._json(f"/git/ref/tags/{tag}")["object"]
        except (OSError, ValueError, KeyError):
            return None
        if reference.get("type") == "tag":
            annotated = self._json(f"/git/tags/{reference['sha']}")
            return {"sha": annotated["object"]["sha"], "annotated": True}
        return {"sha": reference["sha"], "annotated": False}

    def on_main(self, sha: str) -> bool:
        return self._json(f"/compare/{sha}...main").get("status") in ("ahead", "identical")

    def check_runs(self, sha: str) -> list[dict]:
        """Every check run of the commit, each as `{name, status, conclusion, id, app}`,
        `app` being the run's `app.slug` or None (the infrastructure re-check's R-13).
        It asks for `filter=latest` explicitly, GitHub's default, so a change of default
        cannot change what the install reads; whether that also folds separate runs of one
        name on one commit is not relied on, since the gate reads every run it is given.
        One page of up to 100 runs is read, and an answer whose `total_count` is missing
        or differs from the runs on the page is refused (`check-runs-incomplete`), so no
        run can sit beyond the page."""
        from docsuri_ops.release import Refused

        answer = self._json(f"/commits/{sha}/check-runs?filter=latest&per_page=100")
        runs = answer.get("check_runs", [])
        total = answer.get("total_count")
        if not isinstance(total, int) or isinstance(total, bool) or total != len(runs):
            raise Refused("check-runs-incomplete")
        return [{"name": run.get("name"), "status": run.get("status"),
                 "conclusion": run.get("conclusion"), "id": run.get("id"),
                 "app": run["app"].get("slug") if isinstance(run.get("app"), dict) else None}
                for run in runs]

    def asset(self, tag: str, name: str) -> bytes:
        release = self._json(f"/releases/tags/{tag}")
        for asset in release.get("assets", []):
            if asset.get("name") == name:
                return self.fetch(asset["browser_download_url"])
        raise WiringRefused("release-asset-missing")


LATENCY_DAY_BYTES = 32 * 1024 * 1024
# The largest count one summary line may carry: far above any window this host can serve,
# and small enough that a day file's sum divides into a float (the batch-7 review: a
# count of 10**400 raised OverflowError out of `request_rate`).
LATENCY_COUNT_MAX = 10**9


def _latency_day(base: Path, path: Path, owners) -> bytes:
    """One day file's bytes, read as root only through the no-link walk from `base` (the
    root-owned prefix): `profile/evidence/latency` is the service account's, so the file
    is read only when it is a regular file with one name owned by one of `owners` (the
    service account), opened with `O_NOFOLLOW | O_NONBLOCK`, and at most
    `LATENCY_DAY_BYTES` (your answer of 2026-11-10, "Fix both and sweep the rest").
    A refused file (a link at it or at a folder on the way, a second name, a FIFO, a
    socket, another owner, an oversized file) and an absent one count as no lines, as an
    unreadable one always did: the service account already controls these files' bytes
    and could write an empty file, so a refusal tells preflight nothing a missing day file
    would not, and nothing the account chose elsewhere is ever read."""
    from docsuri_ops.arrangement import safe_fs

    try:
        with safe_fs.folder_at(base, path.parent) as folder:
            descriptor = safe_fs.open_existing(folder, path.name, owners=owners)
    except OSError:
        return b""
    try:
        raw = safe_fs.read_all(descriptor, LATENCY_DAY_BYTES)
    except OSError:
        return b""
    finally:
        os.close(descriptor)
    return b"" if len(raw) > LATENCY_DAY_BYTES else raw


def request_rate(folder: Path, *, now: dt.datetime, base: Path, owners=None,
                 minutes: int = 15) -> float:
    """Production's requests a minute over the last `minutes`, from the host's latency
    summaries (`evidence/latency/YYYY-MM-DD.jsonl`, P10), each day file read through the
    no-link walk from `base` (`_latency_day`)."""
    since = now - dt.timedelta(minutes=minutes)
    total = 0
    for day in {since.date(), now.date()}:
        raw = _latency_day(base, folder / f"{day:%Y-%m-%d}.jsonl", owners)
        for line in raw.decode(errors="replace").splitlines():
            total += _latency_count(line, since)
    return total / minutes


def _latency_count(line: str, since: dt.datetime) -> int:
    """One summary line's request count when its window starts at or after `since`, else
    0. A line the service account wrote outside its form counts 0 instead of ending the
    release's preflight: one that does not decode or nests too deeply, a window that is
    not text or has no UTC offset (as `request_context._window_start` reads it), and a
    count that is not a whole number from 0 to `LATENCY_COUNT_MAX` (`Infinity`, `1e999`
    and `10**400` included)."""
    try:
        value = json.loads(line)
    except (ValueError, RecursionError):
        return 0
    if not isinstance(value, dict) or not isinstance(value.get("window"), str):
        return 0
    try:
        window = dt.datetime.fromisoformat(value["window"].replace("Z", "+00:00"))
    except ValueError:
        return 0
    count = value.get("count", 0)
    if window.tzinfo is None or type(count) is not int or not 0 <= count <= LATENCY_COUNT_MAX:
        return 0
    return count if window >= since else 0


V1_INVENTORY_ENV = "DOCSURI_U8_V1_INVENTORY"


def v1_inventory(ledger) -> dict | None:
    """The newest consumer inventory taken from your Cloudflare export (Workflow 11, made
    by the operator before the switch; the person's decision of 2026-10-24): its
    identifier, window, request count and busiest interval, the source of v1's peak rate
    at the install's performance phase. None when there is none."""
    counted = [item for item in ledger.records("consumer-inventory")
               if item.get("source") == "cloudflare-export"]
    if not counted:
        return None
    newest = max(counted, key=lambda item: item["observedUntil"])
    return {name: newest[name] for name in (
        "inventoryId", "observedFrom", "observedUntil", "requests", "peakRequests", "peakAt",
        "intervalSeconds")}


def latest_isolation(folder: Path) -> dict | None:
    names = sorted(path for path in folder.glob("*.json") if path.is_file())
    if not names:
        return None
    try:
        return json.loads(names[-1].read_bytes())
    except (OSError, ValueError):
        return None


def keychain_release(login: str) -> bytearray:
    """As root (the release command), one operator login straight from the System
    keychain, as `docsuri-credential-release` reads it (D5)."""
    from docsuri_ops.u8_platform.fixed import SECURITY, SYSTEM_KEYCHAIN

    completed = subprocess.run([SECURITY, "find-generic-password", "-s", f"docsuri-v2-{login}",
                                "-w", SYSTEM_KEYCHAIN], capture_output=True, timeout=60,
                               check=False)
    if completed.returncode != 0:
        raise WiringRefused("credential-unavailable")
    return bytearray(completed.stdout.rstrip(b"\n"))


PUBLIC_AUTHORITY = "docsuri.rvnnt.dev"
# The first anonymous navigation entry (`backend/u8_registry.py`'s NAVIGATION).
PROBE_ROUTE = "search"
PROBE_READ_BYTES = 1 << 20
PROBE_SECONDS = 10
ENTRY_COOKIE_PREFIX = "docsuri_entry="
_HEX_DIGITS = frozenset("0123456789abcdef")


def _probe_request(base: str, path: str, authority: str, *, body: bytes | None = None,
                   headers: dict[str, str] | None = None) -> tuple[int, bytes, list[str]]:
    """One probe request at the public authority: its status, at most `PROBE_READ_BYTES`
    of its body and its `Set-Cookie` headers. A refusal (urllib's `HTTPError`, an
    `OSError`) propagates to the probe, which answers False."""
    request = urllib.request.Request(base + path, data=body,
                                     headers={"Host": authority, **(headers or {})},
                                     method="GET" if body is None else "POST")
    with urllib.request.urlopen(request, timeout=PROBE_SECONDS) as answer:  # noqa: S310
        return (answer.status, answer.read(PROBE_READ_BYTES),
                list(answer.headers.get_all("Set-Cookie") or []))


def _probe_object(content: bytes) -> dict:
    """A probe answer's JSON body, which must be an object."""
    value = json.loads(content)
    if not isinstance(value, dict):
        raise TypeError("probe answer is not a JSON object")
    return value


def _probe_journey(base: str, authority: str) -> bool:
    """The six reads in order; False at the first that fails, nothing sent after it."""
    from uuid import uuid4

    status, content, _ = _probe_request(base, "/health/live", authority)
    if status != 200 or _probe_object(content)["process"] != "alive":
        return False
    status, _, _ = _probe_request(base, "/", authority)
    if status != 200:
        return False
    status, content, cookies = _probe_request(base, "/api/v2/session", authority)
    if status != 200:
        return False
    token = _probe_object(content)["csrfToken"]
    entries = [cookie for cookie in cookies if cookie.startswith(ENTRY_COOKIE_PREFIX)]
    if (not isinstance(token, str) or len(token) != 64 or not set(token) <= _HEX_DIGITS
            or len(entries) != 1):
        return False
    entry = entries[0].split(";", 1)[0]
    status, content, _ = _probe_request(
        base, "/api/v2/c01/host-resolve-navigation", authority,
        body=json.dumps({"routeId": PROBE_ROUTE}).encode(),
        headers={"Origin": f"https://{authority}", "Content-Type": "application/json",
                 "X-CSRF-Token": token, "Idempotency-Key": str(uuid4()), "Cookie": entry})
    if status != 200:
        return False
    resolved = _probe_object(content)
    if resolved["resolvedRouteId"] != PROBE_ROUTE or resolved["clearPriorOwnerState"] is not True:
        return False
    for path in ("/privacy", "/health/ready"):
        status, _, _ = _probe_request(base, path, authority)
        if status != 200:
            return False
    return True


def signed_out_probe(base: str = "http://127.0.0.1:18200", *,
                     authority: str = PUBLIC_AUTHORITY) -> bool:
    """BR10.7's probe journey (NFR9.12; observability-design § 11, lines 178-186), signed
    out, through the host's boundary at its public authority, in order: liveness, the
    shell, the session read (an anonymous entry context, which stores nothing), the
    anonymous navigation to `search`, `/privacy`, then readiness. It stops at the first
    read that fails and answers False; any other status, a refused request, a malformed
    body or a body that is not a JSON object also answers False, so nothing escapes the
    release's verify. It never sends a session cookie, names no `/api/v2/c02/` route and
    posts nothing but the navigation read."""
    try:
        return _probe_journey(base, authority)
    except (OSError, ValueError, KeyError, TypeError, http.client.HTTPException):
        # `http.client.HTTPException` is no `OSError`: urllib re-raises a malformed status
        # line, an overlong line or a cut chunked body unwrapped.
        return False


def staging_parts(paths: ArrangementPaths, tools):
    """Step 2's outside parts on this Mac: the tag's clone (its fixed programs root-owned
    0755), the release environment's sync, and the library check."""
    from docsuri_ops.arrangement.render import FIXED_PROGRAMS
    from docsuri_ops.arrangement.runtimes import PYTHON_VERSION
    from docsuri_ops.release import REPOSITORY, sync_command, sync_environment

    uv = paths.runtimes / "uv-0.9.0" / "uv"

    def clone(tag: str, folder: Path) -> None:
        tools.run(["/usr/bin/git", "clone", "--quiet", "--depth", "1", "--branch", tag,
                   f"https://github.com/{REPOSITORY}.git", str(folder)], seconds=600)
        for name in FIXED_PROGRAMS:
            program = folder / "ops" / "bin" / name
            os.chmod(program, 0o755)
            os.chown(program, 0, 0)

    def sync(folder: Path) -> None:
        environment = sync_environment(folder, uv=uv)
        tools.run([str(uv), "python", "install", PYTHON_VERSION], env=environment, seconds=900)
        tools.run(sync_command(uv, folder), env=environment, cwd=folder, seconds=1800)

    return clone, sync


def staging_platform(*, paths: ArrangementPaths | None = None, tools=None):
    """The installer's phase 2 (your decision of 2026-10-24, "Staging in the installer"):
    GitHub's public API with the tag, `main` and complete-verification checks, then the
    clone, the sync, the library check and the identity file (`release.Stager`). It
    builds no operator and no ledger client, which do not exist before phase 3."""
    from docsuri_ops.release import REPOSITORY, Stager

    paths = paths or ArrangementPaths()
    if tools is None:
        from docsuri_ops.arrangement.macos import MacTools

        tools = MacTools()
    clone, sync = staging_parts(paths, tools)
    return Stager(paths, GitHubReader(lambda url: tools.fetch(url), REPOSITORY), clone, sync)


def release_platform(*, paths: ArrangementPaths | None = None):
    """The release command's platform on this Mac, run as root in person."""
    from docsuri_ops.arrangement.macos import MacTools
    from docsuri_ops.production_tool import invoke
    from docsuri_ops.release import REPOSITORY, ReleasePlatform

    paths = paths or ArrangementPaths()
    actor = in_person_actor(paths, os.environ)
    tools = MacTools()
    ledger = LedgerClient(via="in-person", paths=paths)
    operator = production_operator(ledger, paths=paths, release=keychain_release,
                                   actor=actor)
    clone, sync = staging_parts(paths, tools)

    def program(folder: Path, name: str) -> list[str]:
        return [str(folder / ".venv" / "bin" / "python"), "-I", str(folder / "ops/bin" / name)]

    def migrate(folder: Path) -> dict:
        """The new release's own production environment tool, before the swap."""
        def run(argv, **options):
            account = argv[3]
            return subprocess.run([SUDO, "-u", account, *program(folder,
                                                                "docsuri-production-tool"),
                                   argv[-1]], **options)

        try:
            return invoke("migrate", {}, login="operator", release=keychain_release,
                          run=run)["result"]
        except Exception as error:  # noqa: BLE001 - reported as the failed owner's migration
            return {"failed": {"reason": str(error)}}

    def run_installer(folder: Path) -> dict:
        completed = subprocess.run([*program(folder, "docsuri-installer"), "apply"],
                                   capture_output=True, timeout=7200, check=False)
        try:
            return json.loads(completed.stdout.decode().splitlines()[-1])
        except (ValueError, IndexError):
            return {"failed": "installer-answered-no-result"}

    operator_name = actor

    def performance(folder: Path, commit: str) -> dict:
        return release_performance(folder, commit, operator=operator_name,
                                   checkout=operator_checkout(paths),
                                   inventory=v1_inventory(ledger))

    # The release command runs as root, which the backup agent refuses: its backup after
    # writes stop and its ledger copy go through your login's own in-person grant (your
    # decision of 2026-10-26, "Through your login"), one password prompt each.
    driver = arrangement_driver(paths, "operator", release=keychain_release,
                                through=operator_name)
    procedures = production_procedures(ledger, operator, role="operator", paths=paths,
                                       release=keychain_release, driver=driver).procedures
    backup = release_backup(procedures, lambda: ledger_profile_state(ledger)["mode"])

    return ReleasePlatform(
        github=GitHubReader(lambda url: tools.fetch(url), REPOSITORY), clone=clone, sync=sync,
        confirm=tty_confirm,
        ledger=ledger, operator=operator, run_installer=run_installer, migrate=migrate,
        performance=performance, memory_available=tools.memory_available,
        request_rate=lambda: request_rate(paths.profile / "evidence" / "latency", now=_now(),
                                          base=paths.prefix,
                                          owners=(Accounts.standard().service.uid,)),
        isolation=lambda: latest_isolation(paths.isolation_evidence),
        disk_free=lambda: free_space(paths), ready=ready_probe(),
        probe=signed_out_probe, backup=backup, backup_plan=backup.plan,
        backup_settle=backup.settle,
        mode=lambda: ledger_profile_state(ledger)["mode"], policy=_production_policy(),
    )


CONFIRM_BYTES = 64


def tty_confirm(shown: dict, *, open_tty: Callable[[], object] | None = None) -> str:
    """Step 0's confirmation on the terminal (`/dev/tty`), never on standard input,
    which holds the tag's JSON (`echo '{"tag": …}' | docsuri-release install`) and is read
    whole first, and never on standard output, which carries the one JSON result (D6):
    what is shown and the prompt go to the terminal, and one bounded line is read back.
    No terminal (or an end of input) raises, which the release command refuses as
    `confirmation-unavailable` before anything changes (review finding, Major, R12)."""
    opener = open_tty or (lambda: open("/dev/tty", "r+b", buffering=0))
    prompt = (f"{json.dumps(shown, indent=1, sort_keys=True)}\n"
              "Type the commit's short hash to go on: ").encode()
    with opener() as terminal:
        terminal.write(prompt)
        line = terminal.readline(CONFIRM_BYTES)
    if not line:
        raise EOFError("no confirmation")
    return line.decode("utf-8", "replace").strip()


class ReleaseBackup:
    """The release command's backup after writes stop (cicd-pipeline § 5.1 step 6): one
    set of the database v2 runs on now (production's in live mode, the profile's
    rehearsal database otherwise), through the recovery procedures' Workflow 5, keyed by
    the release run's own key (`ReleaseInstall._run_key`), so each install takes its own
    set, a failed one is retried by the next install, and a reinstall in another mode
    backs up that mode's database. A failed set raises (`ProcedureFailed`,
    `OutcomeUnknown`); the release command turns that into its way out.

    `plan(tag, key)` is the bound operation the set runs (`backup_effect`), which the
    release command keeps in its journal before the set is taken, and the set taken
    under that key runs exactly it. `settle(effect)` settles an earlier run's pending
    backup by its receipt, through the procedures' own operator (`settle_earlier`), and
    records its set when it applied (review finding, Major, R14), so a pending backup is
    never taken again: None when nothing applied (it never ran, it failed, or it was
    reconciled not applied), `{"integrity": "failed", "reason"}` when it applied but its
    set did not pass or could not be recorded (its ledger copy included), `EffectUnsettled`
    while it is still within its lease or its outcome cannot be proven."""

    def __init__(self, procedures, mode: Callable[[], str]):
        self.procedures, self.mode = procedures, mode
        self._planned: dict[str, dict] = {}

    def plan(self, tag: str, key: str) -> dict:
        environment = "live" if self.mode() == "live" else "rehearsal"
        effect = self.procedures.backup_effect(environment, request=None, via="in-person",
                                               step="pre-release", owner_key=key)
        self._planned[key] = effect
        return effect

    def __call__(self, tag: str, key: str) -> dict:
        effect = self._planned.pop(key, None) or self.plan(tag, key)
        return self.procedures.take(effect["environment"], "pre-release", request=None,
                                    via="in-person", step="pre-release", owner_key=key,
                                    effect=effect)

    def settle(self, effect: dict) -> dict | None:
        from backend.modules.operations.recovery_procedures import ProcedureFailed

        from docsuri_ops.u8_platform.u8_protocols import settle_earlier

        receipt = settle_earlier(self.procedures.platform.operator, str(effect["operation"]),
                                 str(effect["target"]), dict(effect["inputs"]),
                                 key=str(effect["key"]))
        if receipt is None:
            return None
        # The receipt applied: whatever recording it does now settles the entry, a failure
        # with its reason (`{"integrity": "failed", "reason"}`), so a recording that keeps
        # failing never keeps every later release command refused (review finding,
        # Critical, R15). Only `settle_earlier`'s unsettled outcome above refuses the run.
        try:
            return self.procedures.record_applied(effect, "pre-release", None, receipt)
        except ProcedureFailed as failure:
            return {"integrity": "failed", "reason": failure.reason}
        except Exception:  # noqa: BLE001 - the recording failed after the set applied
            return {"integrity": "failed", "reason": "backup-record-failed"}


def release_backup(procedures, mode: Callable[[], str]) -> ReleaseBackup:
    return ReleaseBackup(procedures, mode)


def _production_policy():
    from backend.u8_policy import PRODUCTION_OPERATIONS

    return PRODUCTION_OPERATIONS


def operator_checkout(paths: ArrangementPaths) -> Path:
    """Your checkout whose Playwright the release's performance phase uses, as the
    installation's settings name it (`control/installation.json`, `operatorCheckout`)."""
    value = _read_public_json(paths.control / "installation.json") or {}
    checkout = value.get("operatorCheckout")
    if not isinstance(checkout, str) or not Path(checkout).is_absolute():
        raise WiringRefused("operator-checkout-unconfigured")
    return Path(checkout)


def release_performance(folder: Path, commit: str, *, operator: str, checkout: Path,
                        inventory: dict | None, run: Callable = subprocess.run) -> dict:
    """Step 3 as your login account (cicd-pipeline § 5.2; your decision of 2026-10-24):
    your checkout checked (the release's commit, a clean tree, the same lockfile), then
    the release's `release-performance` phase on the native database, with v1's rate from
    the newest consumer inventory beside it (the person's decision of 2026-10-24)."""
    from docsuri_ops.release import checkout_checks, performance_command

    def git(arguments: list[str]) -> tuple[int, str]:
        completed = run([SUDO, "-n", "-u", operator, "/usr/bin/git", "-C", str(checkout),
                         *arguments], capture_output=True, timeout=60, check=False)
        return completed.returncode, completed.stdout.decode("utf-8", "replace")

    checkout_checks(checkout, commit=commit, folder=folder, git=git)
    variables = {} if inventory is None else {
        V1_INVENTORY_ENV: json.dumps(inventory, sort_keys=True, separators=(",", ":"))}
    completed = run(performance_command(folder, operator=operator, checkout=checkout,
                                        variables=variables),
                    capture_output=True, timeout=7200, check=False, cwd=folder,
                    env={"PATH": "/usr/bin:/bin"})
    return {"passed": completed.returncode == 0, "v1Inventory": inventory}


def release_install():
    """`docsuri-release`'s production wiring: the installed arrangement's paths, GitHub's
    public API without a token, the operator (as root, its logins from the System
    keychain) and the ledger through its fixed command."""
    from docsuri_ops.release import ReleaseInstall

    return ReleaseInstall(ArrangementPaths(), release_platform(), clock=_now)


__all__ = ["LedgerClient", "ledger_profile_state", "production_facts", "production_operator",
           "standing_operator", "production_procedures", "production_parts",
           "production_cutover_platform", "release_install", "WiringRefused"]
