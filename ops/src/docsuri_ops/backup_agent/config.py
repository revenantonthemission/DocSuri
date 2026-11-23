"""The backup agent's own configuration (U8 plan Step 25; BR4.3, BR4.10, BR6.6, NFR3.12,
NFR3.13; Workflow 19).

One private file, `config.json`, in the agent's folder (`backup-agent/`, the backup
account's, 0700; the file 0600). Only the in-person `configure` command changes it.
It holds:

- the backup volume's mount point and identity, and U8's folder on it (`docsuri-v2`,
  with `archives/` and `staging/` and the agent's catalogue);
- the instance's database names, from the one module that holds them
  (`arrangement/paths.py`): the agent dumps only the production database and the
  rehearsal-pattern databases there, and creates only scratch-pattern databases;
- v1's database, which only the in-person snapshot reads, and its read-only login;
- the agent's logins, each a file of its own at 0600 in the agent's folder;
- the callers it accepts: the scheduler account (unattended words) and the operator
  account (every word, in person); the service account is refused everything;
- the retention policy (14 daily sets and 8 weeks of Sunday sets), the minimum time
  before a decided disposal date and the backstops, from U8's production policy rows;
- the kind of arrangement it runs in: `production`, or `realm` for the composed realm,
  whose volume is a folder standing in for the backup volume.

Nothing here is a secret: the logins' passwords stay in their own files.
"""

from __future__ import annotations

import json
import os
import re
import stat
from dataclasses import asdict, dataclass, field
from pathlib import Path

from docsuri_ops.arrangement.paths import DATABASE_ROLES, DatabaseNames

CONFIG = "config.json"
U8_FOLDER = "docsuri-v2"
ARCHIVES = "archives"
STAGING = "staging"
KINDS = ("production", "realm")
MAX_CONFIG = 16 * 1024
# The free-space floor below which nothing new is written (NFR3.12). Production's volume
# always holds 64 GiB back; only the composed realm, whose stand-in folder shares this
# Mac's own disk and holds a few hundred megabytes, may name its own.
BACKUP_FLOOR_BYTES = 64 * 1024**3
_IDENTITY = re.compile(r"[0-9A-Za-z][0-9A-Za-z._-]{0,63}")
DAY = 86400


class ConfigRefused(ValueError):
    """The configuration is missing, malformed or not the agent's own private file."""


@dataclass(frozen=True)
class Login:
    """One database login: where it connects and the private file with its password."""

    host: str
    port: int
    user: str
    password_file: str

    def __post_init__(self) -> None:
        if self.host != "127.0.0.1" or not 1 <= self.port <= 65535:
            raise ConfigRefused("a login connects only to the loopback address")
        if not re.fullmatch(r"[a-z][a-z0-9_]{1,62}", self.user):
            raise ConfigRefused("login user outside its form")
        if "/" in self.password_file or not _IDENTITY.fullmatch(self.password_file):
            raise ConfigRefused("a login's password file is a name in the agent's folder")


@dataclass(frozen=True)
class Retention:
    """RD § 6 and NFR3.12–NFR3.13, in seconds."""

    daily_set_seconds: int = 14 * DAY
    sunday_set_seconds: int = 8 * 7 * DAY
    ledger_copy_seconds: int = 14 * DAY
    decided_minimum_seconds: int = 14 * DAY
    staging_backstop_seconds: int = 1 * DAY
    dry_run_backstop_seconds: int = 14 * DAY
    final_snapshot_backstop_seconds: int = 120 * DAY
    rolled_back_backstop_seconds: int = 90 * DAY

    def __post_init__(self) -> None:
        for name, value in asdict(self).items():
            if type(value) is not int or value <= 0:
                raise ConfigRefused(f"{name} must be a finite positive number of seconds")

    @classmethod
    def from_policy(cls, policy) -> Retention:
        return cls(
            daily_set_seconds=policy.daily_set_retention_seconds,
            sunday_set_seconds=policy.sunday_set_retention_seconds,
            ledger_copy_seconds=policy.daily_set_retention_seconds,
            decided_minimum_seconds=policy.decided_date_minimum_seconds,
            staging_backstop_seconds=policy.staging_file_backstop_seconds,
            dry_run_backstop_seconds=policy.dry_run_copy_backstop_seconds,
            final_snapshot_backstop_seconds=policy.final_snapshot_backstop_seconds,
            rolled_back_backstop_seconds=policy.rolled_back_backstop_seconds,
        )


@dataclass(frozen=True)
class AgentConfig:
    kind: str
    mount: Path
    volume_identity: str
    database_prefix: str
    v2_login: Login
    scheduler_uid: int
    operator_uid: int
    service_uid: int
    v1_database: str | None = None
    v1_login: Login | None = None
    disposable_role: str = DATABASE_ROLES.disposable
    retention: Retention = field(default_factory=Retention)
    # The composed realm only: its database container, where the client programs run.
    container: str | None = None
    space_floor_bytes: int = BACKUP_FLOOR_BYTES
    # The composed realm only: the synthetic v1's own database container
    # (`<run>-v1-postgres`, scripts/u8_synthetic_v1.py), where v1's dumps run. Without it a
    # realm's v1 database is a database of the realm's own instance.
    v1_container: str | None = None
    # The composed realm on the native database (the release's performance phase, U8 plan
    # Step 43): no container; the client programs come from the pinned runtime.
    native: bool = False

    def __post_init__(self) -> None:
        if self.kind not in KINDS:
            raise ConfigRefused("arrangement kind outside its vocabulary")
        if type(self.space_floor_bytes) is not int or self.space_floor_bytes < 1 or (
            self.kind != "realm" and self.space_floor_bytes != BACKUP_FLOOR_BYTES
        ):
            raise ConfigRefused("only the composed realm names its own space floor")
        if self.native is not False and (self.kind != "realm" or self.native is not True):
            raise ConfigRefused("only the composed realm runs on the native database")
        if (self.kind == "realm") != (self.container is not None or self.native):
            raise ConfigRefused("only the composed realm names a database container")
        if self.native and self.container is not None:
            raise ConfigRefused("the native realm names no database container")
        if self.container is not None and not re.fullmatch(r"docsuri-u8-[0-9a-f]{16}",
                                                           self.container):
            raise ConfigRefused("the realm's container is named by its run")
        if self.v1_container is not None and (
            self.kind != "realm" or self.v1_login is None
            or self.v1_container != f"{self.container}-v1-postgres"
        ):
            raise ConfigRefused("only the realm names v1's container, by its run")
        if not self.mount.is_absolute():
            raise ConfigRefused("the volume's mount point must be absolute")
        if not _IDENTITY.fullmatch(self.volume_identity or ""):
            raise ConfigRefused("volume identity outside its form")
        try:
            DatabaseNames(self.database_prefix)
        except ValueError:
            raise ConfigRefused("database prefix outside the fixed naming") from None
        uids = (self.scheduler_uid, self.operator_uid, self.service_uid)
        if any(type(uid) is not int or uid < 0 for uid in uids) or len(set(uids)) != 3:
            raise ConfigRefused("the three callers must be distinct accounts")
        if (self.v1_database is None) != (self.v1_login is None):
            raise ConfigRefused("v1's database and its read-only login come together")
        if self.v1_database is not None and not re.fullmatch(r"[a-z][a-z0-9_]{1,62}",
                                                             self.v1_database):
            raise ConfigRefused("v1's database name outside its form")

    # --- the places it uses ---------------------------------------------------------

    @property
    def names(self) -> DatabaseNames:
        return DatabaseNames(self.database_prefix)

    @property
    def u8_folder(self) -> Path:
        return self.mount / U8_FOLDER

    @property
    def archives(self) -> Path:
        return self.u8_folder / ARCHIVES

    @property
    def staging(self) -> Path:
        return self.u8_folder / STAGING

    # --- the file ------------------------------------------------------------------------

    def as_document(self) -> dict:
        value = {
            "kind": self.kind, "mount": str(self.mount), "volumeIdentity": self.volume_identity,
            "databasePrefix": self.database_prefix, "v2Login": asdict(self.v2_login),
            "schedulerUid": self.scheduler_uid, "operatorUid": self.operator_uid,
            "serviceUid": self.service_uid, "disposableRole": self.disposable_role,
            "retention": asdict(self.retention),
        }
        if self.v1_database is not None:
            value["v1Database"] = self.v1_database
            value["v1Login"] = asdict(self.v1_login)
        if self.container is not None:
            value["container"] = self.container
        if self.v1_container is not None:
            value["v1Container"] = self.v1_container
        if self.space_floor_bytes != BACKUP_FLOOR_BYTES:
            value["spaceFloorBytes"] = self.space_floor_bytes
        if self.native:
            value["native"] = True
        return value

    @classmethod
    def from_document(cls, value: dict) -> AgentConfig:
        required = {"kind", "mount", "volumeIdentity", "databasePrefix", "v2Login",
                    "schedulerUid", "operatorUid", "serviceUid", "disposableRole", "retention"}
        if not isinstance(value, dict) or not required <= set(value) <= required | {
            "v1Database", "v1Login", "container", "spaceFloorBytes", "v1Container", "native",
        }:
            raise ConfigRefused("the configuration's fields differ from the agent's")
        try:
            return cls(
                kind=value["kind"], mount=Path(value["mount"]),
                volume_identity=value["volumeIdentity"],
                database_prefix=value["databasePrefix"], v2_login=Login(**value["v2Login"]),
                scheduler_uid=value["schedulerUid"], operator_uid=value["operatorUid"],
                service_uid=value["serviceUid"], v1_database=value.get("v1Database"),
                v1_login=Login(**value["v1Login"]) if "v1Login" in value else None,
                disposable_role=value["disposableRole"],
                retention=Retention(**value["retention"]),
                container=value.get("container"),
                space_floor_bytes=value.get("spaceFloorBytes", BACKUP_FLOOR_BYTES),
                v1_container=value.get("v1Container"),
                native=value.get("native", False),
            )
        except TypeError as error:
            raise ConfigRefused("the configuration's fields differ from the agent's") from error


def _require_private(path: Path, *, folder: bool) -> os.stat_result:
    info = path.lstat()
    mode = 0o700 if folder else 0o600
    kind = stat.S_ISDIR if folder else stat.S_ISREG
    if (
        stat.S_ISLNK(info.st_mode) or not kind(info.st_mode)
        or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != mode
    ):
        raise ConfigRefused("the agent's folder and files are its own and private")
    return info


def load(folder: Path) -> AgentConfig:
    """Read `config.json` from the agent's own private folder."""
    try:
        _require_private(folder, folder=True)
        _require_private(folder / CONFIG, folder=False)
        descriptor = os.open(folder / CONFIG, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(descriptor, "rb") as stream:
            raw = stream.read(MAX_CONFIG + 1)
    except FileNotFoundError:
        raise ConfigRefused("the agent is not configured") from None
    if len(raw) > MAX_CONFIG:
        raise ConfigRefused("the configuration exceeds its bound")
    try:
        return AgentConfig.from_document(json.loads(raw))
    except ValueError as error:
        if isinstance(error, ConfigRefused):
            raise
        raise ConfigRefused("the configuration is not JSON") from None


def write(folder: Path, config: AgentConfig) -> None:
    """Replace `config.json` atomically (temporary file, sync, rename, folder sync)."""
    _require_private(folder, folder=True)
    payload = json.dumps(config.as_document(), sort_keys=True, indent=1).encode()
    temporary = folder / (CONFIG + ".pending")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        os.write(descriptor, payload)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    os.replace(temporary, folder / CONFIG)
    handle = os.open(folder, os.O_RDONLY)
    try:
        os.fsync(handle)
    finally:
        os.close(handle)


def read_password(folder: Path, login: Login) -> str:
    """A login's password from its own 0600 file in the agent's folder."""
    path = folder / login.password_file
    _require_private(path, folder=False)
    value = path.read_text(encoding="utf-8").strip()
    if not value or "\n" in value or len(value) > 256:
        raise ConfigRefused("a login's password file holds one bounded line")
    return value
