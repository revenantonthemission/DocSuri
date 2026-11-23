"""The arrangement's one source of paths, accounts, database names and database roles.

- `DatabaseNames` holds the fixed database names and patterns of the plan's decision
  "The production databases". The backup agent's configuration, database removal and
  the migration tool all read them from here. Only rehearsal, import and scratch
  databases match a disposable pattern; no pattern names the PlatformControl store,
  so the agent never dumps it and removal refuses it.
- `DatabaseRoles` names the instance's roles beyond each owner's own pair
  (security-design § 6.3, infrastructure-specification § 2 "The database's roles").
- `ArrangementPaths` is every folder under `/Library/DocSuri` (tech-stack-decisions,
  "Root-owned folders" and "Account-owned folders"); tests build it under a prefix.
- `Accounts` is security-design § 5.1's table, with its names and UIDs.

See the approved plan:
`aidlc/spaces/default/intents/261016-finish-v2-rebuild/construction/u8-service-operations-integration/code-generation/code-generation-plan.md`.
"""

from __future__ import annotations

import re
import secrets
from dataclasses import dataclass
from pathlib import Path

_SUFFIX = r"[0-9a-f]{12}"
DISPOSABLE_KINDS = ("rehearsal", "import", "scratch")


@dataclass(frozen=True)
class DatabaseNames:
    """The databases of one instance, by its fixed prefix (`docsuri_v2` in production,
    `docsuri_u8` in the composed realm)."""

    prefix: str

    def __post_init__(self) -> None:
        if re.fullmatch(r"docsuri_[a-z0-9]{2,8}", self.prefix) is None:
            raise ValueError("database prefix outside the fixed naming")

    @property
    def production(self) -> str:
        return self.prefix

    @property
    def platform(self) -> str:
        """PlatformControl's receipt store: outlives every recreate and restore."""
        return self.prefix + "_platform"

    @property
    def template(self) -> str:
        """The composed schema with no owner data, kept on the chain beside the
        production database (production's analogue of the realm's private template):
        each rehearsal database, and the production database a final run imports into,
        is copied from it whole (the person's decision of 2026-10-24, "Build it, test on
        test v1")."""
        return self.prefix + "_template"

    def pattern(self, kind: str) -> re.Pattern[str]:
        if kind not in DISPOSABLE_KINDS:
            raise ValueError("unknown disposable database kind")
        return re.compile(rf"{re.escape(self.prefix)}_{kind}_{_SUFFIX}")

    def new(self, kind: str) -> str:
        """A fresh name of a disposable kind, with 12 random hex characters."""
        name = f"{self.prefix}_{kind}_{secrets.token_hex(6)}"
        if self.pattern(kind).fullmatch(name) is None:
            raise ValueError("generated database name outside its pattern")
        return name

    def kind_of(self, name: str) -> str | None:
        """`production`, `platform`, a disposable kind, or None for any other name."""
        if name == self.production:
            return "production"
        if name == self.platform:
            return "platform"
        if name == self.template:
            return "template"
        for kind in DISPOSABLE_KINDS:
            if self.pattern(kind).fullmatch(name):
                return kind
        return None

    def is_disposable(self, name: str) -> bool:
        return self.kind_of(name) in DISPOSABLE_KINDS


PRODUCTION_DATABASES = DatabaseNames("docsuri_v2")
REALM_DATABASES = DatabaseNames("docsuri_u8")


@dataclass(frozen=True)
class DatabaseRoles:
    """Instance roles beyond each owner's `docsuri_<owner>_owner` and `docsuri_<owner>`.

    - `disposable`: NOLOGIN, the only stand-in role with `CREATEDB`; owns every
      rehearsal, import and scratch database.
    - `scheduler`: the scheduler's login, a member of `disposable` only (INHERIT, no
      SET), so it can check, replay into and drop a scratch copy but never drop the
      production database, and creates no database.
    - `backup_agent`: the backup agent's login, which is also its dump login: no
      `CREATEDB` of its own, `pg_read_all_data`, and `disposable` held with SET but
      without INHERIT. It reads the production database and the rehearsal-pattern
      databases, which it backs up, and writes or drops none of them; it has no CONNECT
      on the PlatformControl store; it creates a database only as `disposable`, which
      then owns it (the person's decision of 2026-10-22). PostgreSQL cannot limit the
      names a login creates, so its fixed command refuses any name outside the scratch
      pattern. It restores a scratch copy with `--no-owner --role <disposable>`.
    - `operator`: the operator tool's login for in-person operations.
    - `restore`: the operator tool's restore login, holding exactly the owner-role
      memberships a production restore needs, so no restore needs the superuser.
    - `operations`: ServiceOperations' operations login, a member of `pg_monitor` for
      A10's `pg_ls_waldir()` (scalability-design § 3.1).
    """

    disposable: str = "docsuri_disposable"
    scheduler: str = "docsuri_scheduler"
    backup_agent: str = "docsuri_backup_agent"
    operator: str = "docsuri_operator"
    restore: str = "docsuri_restore"
    operations: str = "docsuri_operations"


DATABASE_ROLES = DatabaseRoles()

PREFIX = Path("/Library/DocSuri")


SYSTEM_ROOT = Path("/")


@dataclass(frozen=True)
class ArrangementPaths:
    """Every arrangement path, from one prefix (`/Library/DocSuri` in production) and
    the system folders the arrangement writes outside it (`/Library/LaunchDaemons`,
    `/etc/sudoers.d`, `/etc/pf.anchors`), from one system root (`/`)."""

    prefix: Path = PREFIX
    system: Path = SYSTEM_ROOT

    @classmethod
    def under(cls, prefix: Path) -> ArrangementPaths:
        """The same layout under a temporary prefix, for tests; the system folders sit
        beside it, in `<prefix's parent>/system-root`."""
        if not prefix.is_absolute():
            raise ValueError("arrangement prefix must be absolute")
        return cls(prefix, prefix.parent / "system-root")

    @property
    def is_production(self) -> bool:
        return self.prefix == PREFIX and self.system == SYSTEM_ROOT

    # The system folders (root-owned, outside the prefix).
    @property
    def launch_daemons(self) -> Path:
        return self.system / "Library" / "LaunchDaemons"

    @property
    def sudoers_rules(self) -> Path:
        return self.system / "etc" / "sudoers.d" / "docsuri-v2"

    @property
    def pf_anchor(self) -> Path:
        return self.system / "etc" / "pf.anchors" / "org.docsuri.v2"

    # The release's fixed programs, through the `release` link.
    @property
    def release_bin(self) -> Path:
        return self.release / "ops" / "bin"

    @property
    def arrangement_marker(self) -> Path:
        return self.control / "arrangement-in-progress.json"

    @property
    def otool_cache(self) -> Path:
        return self.control / "isolation-otool.json"

    @property
    def effects(self) -> Path:
        """PlatformControl's effects folder and the arrangement driver's `driver.json`."""
        return self.control / "effects"

    @property
    def logrotate_folders(self) -> Path:
        return self.control / "logrotate-folders.json"

    @property
    def installation_log(self) -> Path:
        """The installation log, in the profile's evidence folder (Workflow 20)."""
        return self.profile / "evidence" / "installation-log.jsonl"

    @property
    def scheduler_credentials(self) -> Path:
        """The scheduler's database and PlatformControl logins (0600)."""
        return self.scheduler / "credentials.json"

    @property
    def healthchecks(self) -> Path:
        return self.scheduler / "healthchecks.json"

    @property
    def postgres_runtime(self) -> Path:
        return self.runtimes / "postgresql-16.14"

    @property
    def ollama_runtime(self) -> Path:
        return self.runtimes / "ollama-0.40.7"

    @property
    def cloudflared_runtime(self) -> Path:
        return self.runtimes / "cloudflared-2026.10.3"

    # Root-owned folders.
    @property
    def release(self) -> Path:
        return self.prefix / "release"

    @property
    def release_previous(self) -> Path:
        return self.prefix / "release-previous"

    @property
    def releases(self) -> Path:
        return self.prefix / "releases"

    @property
    def runtimes(self) -> Path:
        return self.prefix / "runtimes"

    @property
    def tunnel_config(self) -> Path:
        return self.prefix / "tunnel" / "config"

    @property
    def control(self) -> Path:
        return self.prefix / "control"

    @property
    def control_stops(self) -> Path:
        return self.control / "stops"

    @property
    def control_logs(self) -> Path:
        return self.control / "logs"

    @property
    def arrangement_manifest(self) -> Path:
        return self.control / "arrangement-manifest.json"

    @property
    def postgres_rules(self) -> Path:
        """PostgreSQL's `pg_hba.conf` and `pg_ident.conf` (root, 0755; the files 0644),
        outside `postgres/`, which the database account owns: that account can read the
        rules but neither write nor replace them (your answer of 2026-11-11, "Map the
        login, root rules")."""
        return self.prefix / "postgres-rules"

    @property
    def evidence(self) -> Path:
        return self.prefix / "evidence"

    @property
    def isolation_evidence(self) -> Path:
        return self.evidence / "isolation"

    # Account-owned folders (0700 unless noted).
    @property
    def profile(self) -> Path:
        return self.prefix / "profile"

    @property
    def postgres_data(self) -> Path:
        return self.prefix / "postgres" / "data"

    @property
    def postgres_socket(self) -> Path:
        return self.prefix / "postgres" / "socket"

    @property
    def models(self) -> Path:
        return self.prefix / "models"

    @property
    def models_state(self) -> Path:
        return self.prefix / "models-state"

    @property
    def tunnel_credentials(self) -> Path:
        return self.prefix / "tunnel" / "credentials"

    @property
    def tunnel_logs(self) -> Path:
        return self.prefix / "tunnel" / "logs"

    @property
    def scheduler(self) -> Path:
        return self.prefix / "scheduler"

    @property
    def backup_agent(self) -> Path:
        return self.prefix / "backup-agent"

    @property
    def availability(self) -> Path:
        """The scheduler account's, mode 0755, files 0644 (observability-design § 12)."""
        return self.prefix / "availability"


@dataclass(frozen=True)
class Account:
    name: str
    uid: int


@dataclass(frozen=True)
class Accounts:
    """security-design § 5.1's accounts, with their names and UIDs."""

    service: Account = Account("_docsuri_v2", 610)
    scheduler: Account = Account("_docsuri_v2_sched", 611)
    database: Account = Account("_docsuri_v2_db", 612)
    models: Account = Account("_docsuri_models", 613)
    tunnel: Account = Account("_docsuri_tunnel", 614)
    backup: Account = Account("_docsuri_r1t_backup", 607)

    @classmethod
    def standard(cls) -> Accounts:
        return cls()

    @classmethod
    def for_tests(cls) -> Accounts:
        """The same table; tests patch the user identifiers they compare against."""
        return cls()

    def by_uid(self, uid: int) -> Account | None:
        for account in (
            self.service, self.scheduler, self.database, self.models, self.tunnel, self.backup,
        ):
            if account.uid == uid:
                return account
        return None
