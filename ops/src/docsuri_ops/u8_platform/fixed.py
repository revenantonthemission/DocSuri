"""PlatformControl's fixed programs (U8 plan Step 27; D6, NFR1.6, security-design § 5.2).

Each program in `ops/bin/` is a short root-owned Python program. It takes exactly one
argument, a name from its own closed set, which it checks again itself, and refuses
anything else with a fixed reason key. Any further input is bounded JSON on standard
input, validated before use. It refuses to run when the environment holds `PYTHON*`,
`DYLD_*` or `LD_*` variables, and writes one JSON result to standard output
(`docsuri-credential-release` writes the password there instead, to the pipe the
operator tool opened, and its JSON result to standard error).

- `docsuri-service-start` / `docsuri-service-stop` <label>: one named launch job. A stop
  disables and unloads the job and writes a root-owned stop record in `control/stops/`
  citing its receipt, bounded at 14 days; a start enables and loads it and removes the
  record. v1's launch agents are reached in the operator's own domain (`SUDO_UID`).
- `docsuri-tunnel-route` <origin>: makes one root-owned registered configuration the
  active one and restarts the tunnel's job.
- `docsuri-credential-release` <login>: reads one System keychain item as root, only for
  the account sudo authenticated (`SUDO_UID`) when that account is the installed operator
  named in `control/platform-authorities.json` (`installed_operator`, read root-owned,
  unwritable by others and through no link); every other caller, root without sudo
  included, is refused before the keychain is read, and the result names that account
  (U8 plan Step 119; D4, security-design § 5.3).
- `docsuri-profile` <field>: applies one profile change atomically, with its receipt
  identifier in the manifest, under the profile's own checks.
- `docsuri-logs` filter: the per-account log lines carrying one request identifier,
  read-only.

Every macOS tool is run through `context.run`, so tests drive the programs with recorded
output under a temporary prefix.
"""

from __future__ import annotations

import contextlib
import datetime as dt
import json
import os
import pwd
import re
import stat
import subprocess
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import BinaryIO, NamedTuple

from docsuri_ops.arrangement import safe_fs
from docsuri_ops.arrangement.paths import ArrangementPaths
from docsuri_ops.platform_control.errors import ControlError

from .credential_release import LOGINS
from .in_person import actor_from_sudo
from .platform_profile import PRODUCTION_LABELS, TUNNEL_ORIGINS, V1_LABELS

REFUSED_ENVIRONMENT = ("PYTHON", "DYLD_", "LD_")
MAX_INPUT = 16 * 1024
STOP_BOUND = dt.timedelta(days=14)
LAUNCHCTL = "/bin/launchctl"
# launchctl's answers for a job already in the wanted state (as `MacTools` treats them):
# bootstrap of a job already loaded, and bootout of a job not loaded.
BOOTSTRAP_LOADED = (5, 37)
BOOTOUT_NOT_LOADED = (3, 113)
SECURITY = "/usr/bin/security"
SYSTEM_KEYCHAIN = "/Library/Keychains/System.keychain"
TUNNEL_LABEL = "org.docsuri.tunnel"
PROFILE_WORDS = {"mode": "mode", "admission": "admission",
                 "rehearsal-database": "rehearsalDatabase", "backup-volume": "backupVolume"}
LOG_LINES = 500
AUTHORITIES_NAME = "platform-authorities.json"
MAX_AUTHORITIES = 64 * 1024
_RECEIPT = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")


class Refused(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


@dataclass
class FixedContext:
    """Where a fixed program works: the arrangement's paths (a test prefix in tests),
    the tool runner, the clock, the account files must belong to (root) and the user
    database the in-person actor is looked up in (`lookup`, as `actor_from_sudo` takes)."""

    paths: ArrangementPaths = field(default_factory=ArrangementPaths)
    run: Callable = subprocess.run
    clock: Callable[[], dt.datetime] = _now
    owner_uid: int = 0
    environ: Mapping[str, str] = field(default_factory=dict)
    lookup: Callable[[int], object] = pwd.getpwuid


def _tool(context: FixedContext, argv: list[str], *, capture: bool = False,
          ok_codes: tuple[int, ...] = (0,)):
    completed = context.run(argv, capture_output=True, timeout=60, check=False)
    if completed.returncode not in ok_codes:
        raise Refused("tool-failed")
    return completed.stdout if capture else completed.returncode


def _write_root_file(context: FixedContext, path: Path, payload: bytes, mode: int) -> None:
    """Atomically, owned by the program's account (root), never through a link."""
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_name(path.name + ".pending")
    descriptor = os.open(pending, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, mode)
    try:
        os.fchmod(descriptor, mode)
        if os.getuid() == 0:
            os.fchown(descriptor, context.owner_uid, 0)
        os.write(descriptor, payload)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    os.replace(pending, path)


def _receipt(document: dict) -> str:
    value = document.get("receiptId")
    if set(document) != {"receiptId"} or not isinstance(value, str) or not _RECEIPT.fullmatch(
        value
    ):
        raise Refused("receipt-required")
    return value


# --- service control -----------------------------------------------------------------------


def _domain(label: str, context: FixedContext) -> tuple[str, str]:
    """(launchctl domain, the job's definition) for one label."""
    if label in V1_LABELS:
        uid = context.environ.get("SUDO_UID", "")
        if not uid.isdigit():
            raise Refused("operator-unknown")
        import pwd

        home = Path(pwd.getpwuid(int(uid)).pw_dir)
        return f"gui/{uid}", str(home / "Library" / "LaunchAgents" / f"{label}.plist")
    return "system", f"/Library/LaunchDaemons/{label}.plist"


def stop_record_path(paths: ArrangementPaths, label: str) -> Path:
    return paths.control_stops / f"{label}.json"


def service_stop(label: str, document: dict, context: FixedContext) -> dict:
    """A stop disables and unloads the job and writes its stop record, deciding from
    launchd's state, not from whether a record exists (your decision of 2026-10-26,
    "Start and stop are safe to repeat"). The bootout always runs: a loaded job is
    unloaded even when a record is already there, and bootout's not-loaded answers
    (`BOOTOUT_NOT_LOADED`, as `MacTools.bootout` treats them) mean the job was already
    unloaded, which is done, not a failure. A stop of a job already unloaded whose
    record is there renews the record under the new receipt, with a new 14 days
    (NFR7.19)."""
    receipt = _receipt(document)
    domain, _ = _domain(label, context)
    path = stop_record_path(context.paths, label)
    had_record = path.exists() or path.is_symlink()
    _tool(context, [LAUNCHCTL, "disable", f"{domain}/{label}"])
    answer = _tool(context, [LAUNCHCTL, "bootout", f"{domain}/{label}"],
                   ok_codes=(0, *BOOTOUT_NOT_LOADED))
    was_loaded = answer == 0
    renewal = had_record and not was_loaded
    now = context.clock()
    record = {"label": label, "receiptId": receipt, "stoppedAt": now.isoformat(),
              "expiresAt": (now + STOP_BOUND).isoformat()}
    _write_root_file(context, path, json.dumps(record, sort_keys=True).encode(), 0o644)
    return {"label": label, "state": "stopped", "stopRecord": record, "renewed": renewal,
            "wasLoaded": was_loaded}


def service_start(label: str, document: dict, context: FixedContext) -> dict:
    """A start enables and loads the job and removes its stop record. A start on a job
    already loaded is done, so a start is safe to repeat. Bootstrap's answers 5 and 37
    (`BOOTSTRAP_LOADED`) are not proof on their own: 5 is launchctl's generic
    input/output error, which a plist with the wrong owner or mode also answers, so
    after either the job must show as loaded (`launchctl print <domain>/<label>` exits 0)
    before the stop record goes; otherwise the start fails (`tool-failed`) and the record
    stays (review finding, Minor, R13)."""
    _receipt(document)
    domain, definition = _domain(label, context)
    _tool(context, [LAUNCHCTL, "enable", f"{domain}/{label}"])
    answer = _tool(context, [LAUNCHCTL, "bootstrap", domain, definition],
                   ok_codes=(0, *BOOTSTRAP_LOADED))
    if answer != 0:
        _tool(context, [LAUNCHCTL, "print", f"{domain}/{label}"], capture=True)
    record = stop_record_path(context.paths, label)
    if record.exists() or record.is_symlink():
        os.unlink(record)
    return {"label": label, "state": "running", "wasLoaded": answer != 0}


def read_stop_record(path: Path, *, owner_uid: int, now: dt.datetime) -> dict | None:
    """A stop record that covers its job: root-owned, in its fixed format, within its
    bound and citing a receipt; anything else is None (a lapse for the isolation check)."""
    try:
        info = path.lstat()
    except FileNotFoundError:
        return None
    if not stat.S_ISREG(info.st_mode) or info.st_uid != owner_uid or info.st_mode & 0o022:
        return None
    try:
        value = json.loads(path.read_bytes())
    except ValueError:
        return None
    if not isinstance(value, dict) or set(value) != {"label", "receiptId", "stoppedAt",
                                                     "expiresAt"}:
        return None
    try:
        expires = dt.datetime.fromisoformat(value["expiresAt"])
        stopped = dt.datetime.fromisoformat(value["stoppedAt"])
    except (TypeError, ValueError):
        return None
    if not _RECEIPT.fullmatch(str(value["receiptId"])) or expires - stopped > STOP_BOUND or (
        now > expires
    ):
        return None
    return value


# --- tunnel routing ------------------------------------------------------------------------


def tunnel_route(origin: str, document: dict, context: FixedContext) -> dict:
    receipt = _receipt(document)
    folder = context.paths.tunnel_config
    registered = folder / f"{origin}.yml"
    info = registered.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != context.owner_uid or info.st_mode & 0o022:
        raise Refused("registered-configuration-refused")
    _write_root_file(context, folder / "active.yml", registered.read_bytes(), 0o644)
    _write_root_file(context, folder / "active.json",
                     json.dumps({"origin": origin, "receiptId": receipt}).encode(), 0o644)
    _tool(context, [LAUNCHCTL, "kickstart", "-k", f"system/{TUNNEL_LABEL}"])
    return {"origin": origin, "active": True}


# --- credential release --------------------------------------------------------------------


class Released(NamedTuple):
    """A released login's password and the account sudo authenticated for it."""

    secret: bytes
    actor: str


def installed_operator(paths: ArrangementPaths, *, owner_uid: int) -> str:
    """`control/platform-authorities.json`'s `actors.operator`, the one reading of that
    file for an in-person check: the folder reached by the no-link walk from the prefix,
    the file opened relative to it as a regular file with one name owned by `owner_uid`
    (root in production) and writable by its owner only, at most 64 KiB read. Anything
    else, an absent file included, is `authorities-file-refused`."""
    try:
        with safe_fs.folder_at(paths.prefix, paths.control) as folder:
            descriptor = safe_fs.open_existing(folder, AUTHORITIES_NAME, owners=(owner_uid,))
            try:
                if stat.S_IMODE(os.fstat(descriptor).st_mode) & 0o022:
                    raise Refused("authorities-file-refused")
                raw = safe_fs.read_all(descriptor, MAX_AUTHORITIES)
            finally:
                os.close(descriptor)
    except OSError:
        raise Refused("authorities-file-refused") from None
    try:
        value = json.loads(raw) if len(raw) <= MAX_AUTHORITIES else None
    except ValueError:
        value = None
    actors = value.get("actors") if isinstance(value, dict) else None
    operator = actors.get("operator") if isinstance(actors, dict) else None
    if not isinstance(operator, str) or not operator:
        raise Refused("authorities-file-refused")
    return operator


def credential_release(login: str, document: dict, context: FixedContext) -> Released:
    """One login's password, released only to the installed operator as sudo
    authenticated it (D4, D5): a refused caller never reaches the keychain."""
    if document:
        raise Refused("input-field-refused")
    try:
        actor = actor_from_sudo(context.environ, lookup=context.lookup)
    except ControlError:
        raise Refused("in-person-actor-refused") from None
    if actor != installed_operator(context.paths, owner_uid=context.owner_uid):
        raise Refused("not-the-installed-operator")
    secret = _tool(context, [SECURITY, "find-generic-password", "-s", f"docsuri-v2-{login}",
                             "-w", SYSTEM_KEYCHAIN], capture=True)
    if not secret or len(secret) > 257:
        raise Refused("credential-unavailable")
    return Released(secret, actor)


# --- profile -------------------------------------------------------------------------------


def _database_follows_mode(value: dict) -> None:
    """The profile's database follows its mode (your decision of 2026-10-24): the
    rehearsal database in rehearsal mode, `docsuri_v2` in live mode. The switch keeps
    `rehearsalDatabase`, so an abort's return to rehearsal loads; a rehearsal mode with
    no rehearsal database is refused before anything is written. A rollback finds it
    cleared, because opening removed every rehearsal database, so the rollback sets a
    new, empty one (still live: the database stays `docsuri_v2`) before it sets mode
    rehearsal (your decision of 2026-10-24, "Create a fresh rehearsal database")."""
    from backend.u8_profile import PRODUCTION_DATABASE

    if value.get("mode") == "live":
        value["database"] = PRODUCTION_DATABASE
        return
    rehearsal = value.get("rehearsalDatabase")
    if not isinstance(rehearsal, str) or not rehearsal:
        raise Refused("rehearsal-database-unset")
    value["database"] = rehearsal


def profile_change(word: str, document: dict, context: FixedContext) -> dict:
    """One field of `profile/environment.json`, under the production profile's own
    checks, with its receipt identifier; written atomically, 0600, the service
    account's. The `mode` and `rehearsal-database` words also set `database`
    (`_database_follows_mode`)."""
    from backend.u8_profile import ProductionProfile, ProfileRefused

    if set(document) != {"value", "receiptId"}:
        raise Refused("input-field-refused")
    receipt = _receipt({"receiptId": document["receiptId"]})
    root = context.paths.profile
    manifest = root / "environment.json"
    info = manifest.lstat()
    if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o600:
        raise Refused("profile-custody")
    value = json.loads(manifest.read_bytes())
    key = PROFILE_WORDS[word]
    if key == "backupVolume":
        if not isinstance(document["value"], dict):
            raise Refused("value-refused")
        value["backupVolume"] = document["value"]
    elif document["value"] is None and key == "rehearsalDatabase":
        value.pop("rehearsalDatabase", None)
    else:
        value[key] = document["value"]
    if key in ("mode", "rehearsalDatabase"):
        _database_follows_mode(value)
    value["receiptId"] = receipt
    try:
        ProductionProfile._from_manifest(root, value)
    except ProfileRefused as refused:
        raise Refused(f"profile-{refused.check}") from None
    pending = manifest.with_name("environment.json.pending")
    descriptor = os.open(pending, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        json.dump(value, stream, sort_keys=True)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(pending, manifest)
    return {"field": key, "receiptId": receipt}


# --- logs ----------------------------------------------------------------------------------


def log_folders(paths: ArrangementPaths) -> tuple[Path, ...]:
    return (paths.profile / "logs", paths.scheduler / "logs", paths.backup_agent / "logs",
            paths.tunnel_logs, paths.control_logs)


def logs_filter(word: str, document: dict, context: FixedContext) -> dict:
    request = document.get("requestId")
    if set(document) != {"requestId"} or not isinstance(request, str) or not _RECEIPT.fullmatch(
        request
    ):
        raise Refused("request-id-refused")
    needle = f'"requestId":"{request}"'
    found = []
    for folder in log_folders(context.paths):
        with contextlib.closing(_log_streams(context, folder)) as streams:
            for name, stream in streams:
                with stream:
                    for line in stream:
                        if needle not in line.replace(" ", ""):
                            continue
                        found.append({"file": f"{folder.name}/{name}", "line": line.strip()})
                        if len(found) >= LOG_LINES:
                            return {"requestId": request, "lines": found, "truncated": True}
    return {"requestId": request, "lines": found, "truncated": False}


def _log_streams(context: FixedContext, folder: Path):
    """Each log file of one folder, opened only through descriptors (your answer of
    2026-11-10, "Fix both and sweep the rest"): the folder belongs to an account that
    could change it, so it is reached by the no-link walk from the root-owned prefix, its
    names are listed through its descriptor, and each file is opened relative to it with
    `O_NOFOLLOW | O_NONBLOCK` and read only when it is a regular file with one name owned
    by the folder's own account or by root. A link at the folder or at a file, a second
    name of another file, a FIFO, a socket and another account's file are skipped,
    never read. A missing folder holds no lines."""
    try:
        descriptor = safe_fs.open_folder(context.paths.prefix, folder)
    except (FileNotFoundError, safe_fs.PathRefused):
        return
    try:
        owners = (os.fstat(descriptor).st_uid, context.owner_uid)
        for name in sorted(os.listdir(descriptor)):
            try:
                opened = safe_fs.open_existing(descriptor, name, owners=owners)
            except (FileNotFoundError, safe_fs.PathRefused):
                continue
            yield name, os.fdopen(opened, "r", encoding="utf-8", errors="replace")
    finally:
        os.close(descriptor)


# --- the shared shape ----------------------------------------------------------------------

PROGRAMS: dict[str, tuple[tuple[str, ...], Callable]] = {
    "docsuri-service-start": (PRODUCTION_LABELS, service_start),
    "docsuri-service-stop": (PRODUCTION_LABELS, service_stop),
    "docsuri-tunnel-route": (TUNNEL_ORIGINS, tunnel_route),
    "docsuri-credential-release": (LOGINS, credential_release),
    "docsuri-profile": (tuple(PROFILE_WORDS), profile_change),
    "docsuri-logs": (("filter",), logs_filter),
}


def _emit(stream: BinaryIO, value: dict, status: int) -> int:
    stream.write(json.dumps(value, sort_keys=True, separators=(",", ":")).encode() + b"\n")
    stream.flush()
    return status


def run(program: str, argv: list[str], context: FixedContext, *, environ: Mapping[str, str],
        stdin: BinaryIO, stdout: BinaryIO, stderr: BinaryIO) -> int:
    words, handler = PROGRAMS[program]
    secret_out = program == "docsuri-credential-release"
    results = stderr if secret_out else stdout
    if any(name.startswith(REFUSED_ENVIRONMENT) for name in environ):
        return _emit(results, {"ok": False, "reason": "environment-refused"}, 2)
    if len(argv) != 1 or argv[0] not in words:
        return _emit(results, {"ok": False, "reason": "word-refused"}, 2)
    raw = stdin.read(MAX_INPUT + 1)
    try:
        if len(raw) > MAX_INPUT:
            raise Refused("input-too-large")
        try:
            document = json.loads(raw or b"{}")
        except ValueError:
            raise Refused("input-not-json") from None
        if not isinstance(document, dict):
            raise Refused("input-not-an-object")
        context.environ = environ
        result = handler(argv[0], document, context)
    except Refused as refused:
        return _emit(results, {"ok": False, "reason": refused.reason}, 1)
    except (OSError, KeyError, ValueError, subprocess.SubprocessError):
        # A missing file, an unknown account or a tool that hung: still one JSON result,
        # with no path, value or traceback in it.
        return _emit(results, {"ok": False, "reason": "program-failed"}, 1)
    if secret_out:
        stdout.write(result.secret)
        stdout.flush()
        return _emit(stderr, {"ok": True, "login": argv[0], "actor": result.actor}, 0)
    return _emit(stdout, {"ok": True, **result}, 0)


def main_fixed(program: str) -> int:
    """The installed program's entry: its own name, one word, the arrangement's paths."""
    return run(program, sys.argv[1:], FixedContext(), environ=os.environ,
               stdin=sys.stdin.buffer, stdout=sys.stdout.buffer, stderr=sys.stderr.buffer)
