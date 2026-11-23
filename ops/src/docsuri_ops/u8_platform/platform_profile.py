"""U8's platform profiles (U8 plan Step 27; A6, BR7.1).

Where PlatformControl's store is in production and in the composed realm, which driver
runs A6's effects, the launch-job labels service control may act on, the tunnel's
registered origins and production's store logins. By the person's decision of
2026-10-25 ("Move U8's code out of U7") they live here, beside U7's package: U7's
`profile.py` is as built and accepts only U7's own realm. Every U7 name this module uses
(`private_bytes`, the store, `RUNTIME_ROLE`) is imported from U7 by its absolute path.
"""

from __future__ import annotations

import functools
import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from docsuri_ops.platform_control.profile import private_bytes

U8_REALM_RUN = Path("/tmp/docsuri-u8-run")
U8_REALM_DATABASE = "docsuri_u8_platform"
U8_PRODUCTION_DATABASE = "docsuri_v2_platform"
U8_PRODUCTION_PORT = 15432
U8_PRODUCTION_CONTROL = Path("/Library/DocSuri/control")
U8_PRODUCTION_PROFILE = Path("/Library/DocSuri/profile")
READER_FILE = "platform-reader.json"
# The store's amendment, a path relative to a source tree (the repository or a staged
# release). The production tool's installation script and migration, and U8's runner,
# name it only through this constant.
STORE_AMENDMENT = "ops/src/docsuri_ops/u8_platform/u8_store.sql"
STORE_INVENTORY = "ops/src/docsuri_ops/platform_control/inventory.json"
# The files whose digest is the platform store's recorded identity (the person's decision
# of 2026-10-25, "After the move, same build"): the inventory and the amendment together,
# so a change to either one alone is applied by the next migration.
STORE_FILES = (STORE_INVENTORY, STORE_AMENDMENT)
_U8_RUN_ID = re.compile(r"docsuri-u8-[0-9a-f]{16}")
_UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")

# The named launch jobs service control may act on, one label each (A6). Production:
# v2's system jobs, the shared model runtime and tunnel, and v1's launch agents under the
# operator account. The composed realm: its own processes and the synthetic v1's.
PRODUCTION_LABELS = (
    "org.docsuri.v2.host", "org.docsuri.v2.workers", "org.docsuri.v2.scheduler",
    "org.docsuri.v2.maintenance", "org.docsuri.v2.postgres", "org.docsuri.models",
    "org.docsuri.tunnel", "dev.docsuri.api", "dev.docsuri.web", "dev.docsuri.worker-purge",
    "dev.docsuri.heartbeat",
)
V1_LABELS = ("dev.docsuri.api", "dev.docsuri.web", "dev.docsuri.worker-purge",
             "dev.docsuri.heartbeat")
REALM_LABELS = tuple(
    f"dev.docsuri.u8.run.{name}"
    for name in ("host", "workers", "scheduler", "maintenance", "v1-api", "v1-web")
)
TUNNEL_ORIGINS = ("v1-web", "v2-host", "maintenance")


def owned_private_bytes(path: Path, *, owner_uid: int, maximum: int = 65536) -> bytes:
    """U7's `private_bytes` with the owner named instead of taken from the reading
    process: a bounded regular file (never a link, never a FIFO) of mode 0600 owned by
    `owner_uid`. Root reads the service account's own binding through it."""
    import os
    import stat

    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(descriptor)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != owner_uid
                or stat.S_IMODE(info.st_mode) != 0o600 or info.st_size > maximum):
            raise ValueError("private record must be a bounded regular file of its owner")
        raw = os.read(descriptor, maximum + 1)
        if len(raw) > maximum:
            raise ValueError("private record exceeds allocation")
        return raw
    finally:
        os.close(descriptor)


def store_digest(source: Path) -> str:
    """The digest the platform store records as its identity, from a source tree (the
    repository or a staged release): each of `STORE_FILES` with its SHA-256, as one
    SHA-256. The installation script's identity insert, the production tool's migration
    and U8's runner record and compare only this value."""
    digest = hashlib.sha256()
    for file in STORE_FILES:
        digest.update(file.encode() + b"\0" + hashlib.sha256((source / file).read_bytes())
                      .hexdigest().encode() + b"\n")
    return digest.hexdigest()


@dataclass(frozen=True)
class ReaderBinding:
    """The service account's bounded evidence-reader authority (NFR1.5). Production's
    file also carries the store login the reader connects with (the realm reads its own
    `platform-credentials.json`); it never appears in a representation."""

    authority_id: str
    actor: str
    password: str | None = field(default=None, repr=False)


@dataclass(frozen=True)
class U8PlatformProfile:
    """Where PlatformControl's store is and which driver runs A6's effects.

    `production`: `docsuri_v2_platform` in v2's instance, the arrangement driver, the
    root-owned `control/` folder; the operator tool's login is released in person (D5)
    and the scheduler's comes from its own folder. `realm`: `docsuri_u8_platform` in the
    composed realm's instance, the realm driver and the run root's `platform/` folder.
    The realm driver refuses the production profile and the arrangement driver every
    synthetic one (BR7.1)."""

    kind: str
    database: str
    port: int
    environment: str
    state_root: Path
    effects_root: Path
    labels: tuple[str, ...]
    run_root: Path | None = None
    run_id: str | None = None
    container: str | None = None

    def __post_init__(self) -> None:
        if self.kind not in ("production", "realm"):
            raise ValueError("platform profile kind outside its vocabulary")
        if (self.kind == "realm") != (self.run_root is not None):
            raise ValueError("only the composed realm has a run root")

    @property
    def is_production(self) -> bool:
        return self.kind == "production"

    @classmethod
    def realm(cls, run_root: Path = U8_REALM_RUN) -> U8PlatformProfile:
        value = json.loads(private_bytes(run_root / "environment.json"))
        if value.get("realm") != "service-operations" or not _U8_RUN_ID.fullmatch(
            value.get("runId", "")
        ) or value.get("platformDatabase") != U8_REALM_DATABASE:
            raise ValueError("not the composed realm's environment")
        state = run_root / "platform"
        return cls(
            kind="realm", database=U8_REALM_DATABASE, port=int(value["databasePort"]),
            environment=f"u8-realm:{value['runId']}", state_root=state,
            effects_root=state / "effects", labels=REALM_LABELS, run_root=run_root,
            run_id=value["runId"], container=value.get("container"),
        )

    @classmethod
    def production(cls, actor: str = "operator", *,
                   control: Path = U8_PRODUCTION_CONTROL) -> U8PlatformProfile:
        """Production's store and the arrangement driver; each actor (`operator`, in
        person, or the standing `scheduler`) has its own effects folder under
        `control/effects/`, owned by its account, holding its `driver.json` and its
        effects' bound inputs (U8 plan Step 37)."""
        if actor not in ("operator", "scheduler"):
            raise ValueError("a production actor is the operator or the scheduler")
        return cls(
            kind="production", database=U8_PRODUCTION_DATABASE, port=U8_PRODUCTION_PORT,
            environment="docsuri-v2:production", state_root=control,
            effects_root=control / "effects" / actor, labels=PRODUCTION_LABELS,
        )

    # --- credentials -----------------------------------------------------------------

    def realm_password(self, role: str) -> str:
        """The realm's own store logins (`runtime`, `provisioner`)."""
        if self.run_root is None:
            raise ValueError("production logins are released in person (D5)")
        value = json.loads(private_bytes(self.run_root / "platform-credentials.json"))
        if value.get("runId") != self.run_id or role not in value.get("roles", {}):
            raise ValueError("platform credential identity mismatch")
        return value["roles"][role]

    def reader(self, root: Path | None = None, *,
               owner_uid: int | None = None) -> ReaderBinding | None:
        """The service account's reader authority, written by the realm's tool or the
        production environment tool; None while none is provisioned.

        `owner_uid` names the account that must own the binding when the reader is not
        that account: the isolation check runs as root and reads the service account's
        binding (0600, the service account's own), so it names the service account's UID
        instead of its own (`owned_private_bytes`). Without it the binding must be the
        reading account's own (U7's `private_bytes`)."""
        folder = root or (self.run_root if self.run_root is not None else U8_PRODUCTION_PROFILE)
        path = folder / READER_FILE
        if not path.exists():
            return None
        raw = private_bytes(path) if owner_uid is None else owned_private_bytes(
            path, owner_uid=owner_uid)
        value = json.loads(raw)
        if not _UUID.fullmatch(str(value.get("authorityId", ""))) or not isinstance(
            value.get("actor"), str
        ):
            raise ValueError("platform reader binding outside its form")
        password = value.get("password")
        if password is not None and (not isinstance(password, str) or not password):
            raise ValueError("platform reader binding outside its form")
        return ReaderBinding(value["authorityId"], value["actor"], password)

    def store(self, role: str, password: str):
        """The store for `role`, every connection of which demands SCRAM (NFR3.3): a
        bound login's own store, or U7's roles through the same class."""
        from docsuri_ops.platform_control.store import DatabaseTarget

        target = DatabaseTarget("127.0.0.1", self.port, self.database)
        logins = PRODUCTION_STORE_LOGINS if self.kind == "production" else REALM_STORE_LOGINS
        if role in logins:
            return _login_store(target, role, password)
        return scram_store(target, role, password)


# Production's store logins (decision "PlatformControl's store in production"): the
# operator tool's, the scheduler's and the service account's reader, each a login role of
# its own (installer phase 3). By your decision of 2026-10-26 ("Bind each login to its
# actor") each is bound to its actor in the store (`u8_login_actor`): the operator's and
# the scheduler's are members of U7's runtime role, which in U8's store reaches U7's
# functions only through U8's guarded ones; the reader's is a member of the reader role,
# which holds only the read functions.
PRODUCTION_STORE_LOGINS = ("docsuri_platform_operator", "docsuri_platform_scheduler",
                           "docsuri_platform_reader")
# The composed realm's three logins, bound the same way (the realm's tool).
REALM_STORE_LOGINS = ("docsuri_u8_platform_operator", "docsuri_u8_platform_scheduler",
                      "docsuri_u8_platform_reader")
STORE_LOGIN_KINDS = ("operator", "scheduler", "reader")
READER_ROLE = "platform_control_u8_reader"
# U7's functions each login reaches through U8's guarded one (`u8_store.sql`, 3).
GUARDED_FUNCTIONS = {name: f"u8_{name}" for name in (
    "record_evidence", "begin_operation", "mark_executing", "settle_operation",
    "reconcile_receipt", "promote_in_flight", "read_receipt", "read_receipt_named",
    "latest_evidence", "list_unresolved", "status_counts",
)}


def store_logins(kind: str) -> dict[str, str]:
    """The store login of each kind (`operator`, `scheduler`, `reader`)."""
    logins = PRODUCTION_STORE_LOGINS if kind == "production" else REALM_STORE_LOGINS
    return dict(zip(STORE_LOGIN_KINDS, logins, strict=True))


@functools.cache
def _scram_store_class() -> type:
    """U7's `Store` whose every connection demands SCRAM (NFR3.3, L4-12): U7's own
    `connection()` names no `require_auth`, so a listener in the instance's place that
    asks for a cleartext password would be sent it. The connection's other options and
    U7's error mapping are U7's, kept as they are; U7's file is not edited."""
    import contextlib

    import psycopg

    from docsuri_ops.platform_control.errors import DEPENDENCY_UNAVAILABLE, ControlError
    from docsuri_ops.platform_control.store import Store

    class ScramStore(Store):
        @contextlib.contextmanager
        def connection(self, *, autocommit: bool = False):
            try:
                conn = psycopg.connect(
                    host=self.target.host, port=self.target.port,
                    dbname=self.target.dbname, user=self.role, password=self._password,
                    connect_timeout=self._connect_timeout, options=self._options,
                    autocommit=autocommit, require_auth="scram-sha-256",
                )
            except psycopg.Error as exc:  # refused, unauthenticated or no database
                raise ControlError(
                    DEPENDENCY_UNAVAILABLE, "guarded store is unavailable",
                    retryable=True, details={"messageKey": "store-unavailable"},
                ) from exc
            try:
                yield conn
            finally:
                conn.close()

    return ScramStore


def scram_store(target, role: str, password: str):
    """U7's store for one of U7's own roles (the runtime's or the provisioner's), every
    connection of which demands SCRAM. The installer builds its provisioner's store
    through it, and `U8PlatformProfile.store` every store that is not a bound login's."""
    return _scram_store_class()(target, role=role, password=password)


def _login_store(target, role: str, password: str):
    """U7's store over one bound login: U8's guarded functions in place of U7's, reached
    through a login of its own, so each actor keeps its own password and the store refuses
    any actor but the login's own. Its connections demand SCRAM (`_scram_store_class`)."""
    from docsuri_ops.platform_control import RUNTIME_ROLE

    Store = _scram_store_class()  # noqa: N806 - the class the login's store extends

    class LoginStore(Store):
        def __init__(self) -> None:
            super().__init__(target, role=RUNTIME_ROLE, password=password)
            self.role = role

        def call_committed(self, function: str, params: tuple) -> object:
            return super().call_committed(GUARDED_FUNCTIONS.get(function, function), params)

    return LoginStore()
