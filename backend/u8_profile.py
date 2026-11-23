"""The production profile (amendment A9, U8 plan Step 9) and the complete realms' listener.

`LocalProfile.load` (U2's `backend/local_profile.py`) reads one owned synthetic realm
under `/tmp`. Production has its own loader here, `ProductionProfile.load`, which applies
the same owner, mode and link rule on a durable root that must lie outside `/tmp`, has
no expiry, and changes only through PlatformControl's profile operation (BR6.1, BR9.15).
A production profile exists only through this module (the person's decision of
2026-10-24, "Move, scope tools, test U2").

`listen_port(profile)` and `public_authority(profile)` give any profile's loopback
listener and its public authority: the composed realm's origin is its public stand-in,
so its listener differs from its origin.
"""

from __future__ import annotations

import json
import math
import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from backend.local_profile import KEY_FOLDERS, PORTS, LocalProfile, private_bytes, public_origin

PRODUCTION_ORIGIN = "https://docsuri.rvnnt.dev"
PRODUCTION_DATABASE = "docsuri_v2"
PRODUCTION_REALM = "production"
# tech-stack-decisions "Addresses": the host, the maintenance server and v2's instance.
PRODUCTION_LISTEN_PORT = 18200
PRODUCTION_MAINTENANCE_PORT = 18201
PRODUCTION_DATABASE_PORT = 15432
PRODUCTION_MANIFEST = "environment.json"
PRODUCTION_ACCOUNT_ROLES = ("service", "scheduler", "backup", "database", "models", "tunnel")
_MANIFEST_REQUIRED = frozenset({
    "profile", "runId", "mode", "admission", "database", "databasePort", "publicOrigin",
    "listenPort", "maintenancePort", "backupVolume", "maintainerAccount", "accounts",
    "keyFolders", "createdAt",
})
_MANIFEST_OPTIONAL = frozenset({"rehearsalDatabase", "receiptId"})
_TMP_ROOTS = (Path("/tmp"), Path("/private/tmp"))


def listen_port(profile) -> int:
    """The loopback port a profile's host listens on: production's own, else the realm's
    application port (the composed realm's origin is its public stand-in, so its
    listener differs from its origin)."""
    if getattr(profile, "is_production", False):
        return profile.production_listen_port
    for unit, (application, database) in PORTS.items():
        if database == profile.database_port and public_origin(unit) == profile.origin:
            return application
    return int(profile.origin.rsplit(":", 1)[1])


def public_authority(profile) -> str:
    """The `host[:port]` of a profile's public origin."""
    return profile.origin.split("://", 1)[1]


def custody_failure(info: os.stat_result, *, uid: int, exact_mode: int | None = None) -> str | None:
    """The owner, mode and link check of the production loader, the synthetic loader's
    rule with a named failure.

    Returns `link`, `owner` or `mode` for the first failure, or None. A mode fails when
    it grants group or other access, or, with `exact_mode`, when it differs from it.
    """
    if stat.S_ISLNK(info.st_mode):
        return "link"
    if info.st_uid != uid:
        return "owner"
    mode = stat.S_IMODE(info.st_mode)
    if mode & 0o077 or (exact_mode is not None and mode != exact_mode):
        return "mode"
    return None


class ProfileRefused(ValueError):
    """A production profile check failed; `check` names it (Workflow 1 step 2)."""

    def __init__(self, check: str, message: str):
        super().__init__(f"{check}: {message}")
        self.check = check


def _under_tmp(path: Path) -> bool:
    candidates = {path, path.resolve()}
    roots = {*_TMP_ROOTS, *(root.resolve() for root in _TMP_ROOTS)}
    return any(item == root or root in item.parents for item in candidates for root in roots)


def _require_root(root: Path, uid: int) -> Path:
    """BR6.1: absolute, outside /tmp, not a link, owned by the service account, 0700."""
    if not root.is_absolute():
        raise ProfileRefused("root-relative", "the profile root must be an absolute path")
    if _under_tmp(root):
        raise ProfileRefused("root-under-tmp", "the profile root must lie outside /tmp")
    try:
        info = root.lstat()
    except FileNotFoundError:
        raise ProfileRefused("root-missing", "the profile root does not exist") from None
    if stat.S_ISLNK(info.st_mode):
        raise ProfileRefused("root-link", "the profile root must not be a link")
    if not stat.S_ISDIR(info.st_mode):
        raise ProfileRefused("root-missing", "the profile root is not a folder")
    failure = custody_failure(info, uid=uid, exact_mode=0o700)
    if failure is not None:
        raise ProfileRefused(f"root-{failure}", "the profile root must be the service's, 0700")
    return root


def _require_tree(root: Path, uid: int) -> None:
    """Every folder in the root is 0700 and every file 0600, owned by the service account,
    and nothing in it is a link."""
    for folder, names, files in os.walk(root, followlinks=False):
        for name in (*names, *files):
            path = Path(folder) / name
            info = path.lstat()
            failure = custody_failure(
                info, uid=uid, exact_mode=0o700 if stat.S_ISDIR(info.st_mode) else 0o600
            )
            if failure is not None:
                kind = "folder" if stat.S_ISDIR(info.st_mode) else "file"
                raise ProfileRefused(f"{kind}-{failure}", "profile content custody differs")
            if not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)):
                raise ProfileRefused("file-kind", "the profile holds only folders and files")


def _manifest_text(value, field: str, pattern: str) -> str:
    if not isinstance(value, str) or re.fullmatch(pattern, value) is None:
        raise ProfileRefused("manifest", f"{field} is outside its form")
    return value


@dataclass(frozen=True)
class ProductionProfile(LocalProfile):
    """The durable production profile (entities.md ProductionProfile). No expiry: its
    `expires_at` is infinite, so the owner transactions' retention check never ends it."""

    mode: str = "rehearsal"
    admission: str = "maintainer-only"
    rehearsal_database: str | None = None
    production_listen_port: int = PRODUCTION_LISTEN_PORT
    maintenance_port: int = PRODUCTION_MAINTENANCE_PORT
    backup_mount: str = ""
    backup_identity: str = ""
    maintainer_account: UUID | None = None
    accounts: tuple[tuple[str, str], ...] = ()
    receipt_id: str | None = None
    created_at: float = 0.0

    is_production = True

    @classmethod
    def load(cls, manifest: Path, *, service_uid: int) -> ProductionProfile:  # type: ignore[override]
        """Read `<root>/environment.json` and refuse, naming the check, a root that is
        relative, under /tmp, a link, not the service account's or not 0700, and any
        file in it that is not 0600."""
        root = _require_root(Path(manifest).parent, service_uid)
        if Path(manifest).name != PRODUCTION_MANIFEST:
            raise ProfileRefused("manifest", "the production manifest is environment.json")
        _require_tree(root, service_uid)
        try:
            value = json.loads(private_bytes(root / PRODUCTION_MANIFEST, uid=service_uid))
        except FileNotFoundError:
            raise ProfileRefused("manifest", "the environment manifest is missing") from None
        except ValueError:
            raise ProfileRefused("manifest", "the environment manifest is unreadable") from None
        return cls._from_manifest(root, value)

    @classmethod
    def _from_manifest(cls, root: Path, value) -> ProductionProfile:
        from docsuri_ops.arrangement.paths import PRODUCTION_DATABASES

        if not isinstance(value, dict) or not (
            _MANIFEST_REQUIRED <= set(value) <= _MANIFEST_REQUIRED | _MANIFEST_OPTIONAL
        ):
            raise ProfileRefused("manifest", "the manifest's fields differ from the profile's")
        if value["profile"] != PRODUCTION_REALM or value["publicOrigin"] != PRODUCTION_ORIGIN:
            raise ProfileRefused("manifest", "not the production profile")
        if (value["listenPort"], value["maintenancePort"], value["databasePort"]) != (
            PRODUCTION_LISTEN_PORT, PRODUCTION_MAINTENANCE_PORT, PRODUCTION_DATABASE_PORT,
        ):
            raise ProfileRefused("manifest", "unexpected production listener")
        if value["keyFolders"] != list(KEY_FOLDERS):
            raise ProfileRefused("manifest", "the key folders differ from the profile's")
        mode, admission = value["mode"], value["admission"]
        if mode not in ("rehearsal", "live") or admission not in ("maintainer-only", "open"):
            raise ProfileRefused("manifest", "unknown mode or admission")
        if mode == "rehearsal" and admission != "maintainer-only":
            raise ProfileRefused("manifest", "rehearsal mode admits only the maintainer")
        database = value["database"]
        rehearsal = value.get("rehearsalDatabase")
        if rehearsal is not None and PRODUCTION_DATABASES.kind_of(rehearsal) != "rehearsal":
            raise ProfileRefused("manifest", "the rehearsal database is outside its pattern")
        if mode == "live" and database != PRODUCTION_DATABASE:
            raise ProfileRefused("manifest", "live mode runs on the production database")
        if mode == "rehearsal" and (rehearsal is None or database != rehearsal):
            raise ProfileRefused("manifest", "rehearsal mode runs on its rehearsal database")
        accounts = value["accounts"]
        if not isinstance(accounts, dict) or set(accounts) != set(PRODUCTION_ACCOUNT_ROLES):
            raise ProfileRefused("manifest", "the account names differ from the profile's")
        volume = value["backupVolume"]
        if not isinstance(volume, dict) or set(volume) != {"mountPoint", "identity"}:
            raise ProfileRefused("manifest", "the backup volume's identity is incomplete")
        created = value["createdAt"]
        if type(created) not in (int, float) or not math.isfinite(created) or created <= 0:
            raise ProfileRefused("manifest", "createdAt must be a finite time")
        account = _manifest_text(value["maintainerAccount"], "maintainerAccount", r"[0-9a-f-]{36}")
        try:
            maintainer = UUID(account)
        except ValueError as error:
            raise ProfileRefused("manifest", "maintainerAccount is not an identity") from error
        receipt = value.get("receiptId")
        if receipt is not None:
            _manifest_text(receipt, "receiptId", r"[0-9a-f-]{36}")
        return cls(
            root,
            _manifest_text(value["runId"], "runId", r"docsuri-v2-[0-9a-f]{16}"),
            PRODUCTION_ORIGIN,
            PRODUCTION_DATABASE_PORT,
            math.inf,
            database,
            PRODUCTION_REALM,
            mode=mode,
            admission=admission,
            rehearsal_database=rehearsal,
            backup_mount=_manifest_text(
                volume["mountPoint"], "mountPoint", r"/Volumes/[A-Za-z0-9_.-]{1,64}"
            ),
            backup_identity=_manifest_text(volume["identity"], "identity", r"[0-9A-Fa-f-]{36}"),
            maintainer_account=maintainer,
            accounts=tuple(
                (role, _manifest_text(accounts[role], role, r"_docsuri_[a-z0-9_]{1,32}"))
                for role in PRODUCTION_ACCOUNT_ROLES
            ),
            receipt_id=receipt,
            created_at=float(created),
        )
