"""The production environment tool (U8 plan Step 37; BR6.9, cicd-pipeline § 5.1 step 8,
D5, D6, D14).

`ops/bin/docsuri-production-tool <word>`, run as the service account through sudo, in
person, against the production profile only, with one word per owner operator command
and any further input as bounded JSON on standard input. Each word states its owner's
consequence in its result.

- `migrate`: each owner's new migrations of the composed chain (`backend.u8_migrations`),
  U1's amendments first, in owner order, each file in its own transaction under its
  owner's role (`SET LOCAL ROLE`), on the profile's current database; a failure rolls
  that file back and keeps the earlier ones. Then PlatformControl's store migration:
  when the store's recorded digest (the inventory and `u8_store.sql` together) differs,
  `u8_store.sql` and each missing protocol row of inventory version 2.
- `restore-evaluate`: the tombstones newer than a restored set replayed through
  AccountAccess's restore evaluation (`restore_checks.replay`, with each dependent row),
  and the tombstoned owners counted absent, as the restore login (Workflow 7 step 6).
- `restore-database`, `recreate-database`, `remove-database`: the arrangement driver's
  in-person database effects (Workflow 7, BR9.17). `restore-database` reads a JSON header
  line and then the set's archive (streamed back by the backup agent's in-person
  `stream-back`), checks its digest into a private spool, and runs `pg_restore -j 2
  --no-comments` as the restore login with `maintenance_work_mem = 1GB` and two parallel
  maintenance workers, only the owners' entries (the recreate keeps the base).
- U6's `create-export-key-after-loss`, `rotate-export-key`, `retire-export-key` and
  `export-key-counts`, on `profile/export-keys/`, through `SET ROLE
  docsuri_export_owner`.
- AccountAccess's `replace-verifier-key`: every session and outstanding proof ends, then
  a new key replaces the old one in `profile/verifier-key/` (BR6.2).
- `control-key-start` (your decisions of 2026-10-24, "Add a key snapshot step", and of
  2026-10-25, "Start it at install, U8 snapshot"): AccountAccess's
  `u8_verifier_key.start_keyring` on the profile's `control-keys/`. It starts the control
  keyring once, with U2's own `ControlKeyring.rotate`, then writes U8's keyring snapshot
  (the keyring's record and its start marker's run, no verifier). Run again it takes only
  a missing snapshot. It is refused, writing nothing, while v2 runs: each of v2's three
  roles needs a current root-owned stop record (`docsuri-service-stop`'s, in
  `control/stops/`). Phase 7 of the installer runs it once v2's first start has created
  the verifier key, before any account exists.
- U2's `control-key-recovery`: `u8_verifier_key.recover_production` on the profile's
  `control-keys/` folder, from U8's keyring snapshot whose exact digest and generation the
  operator retained (the start's result names them). Only the keyring's missing files,
  its record and its start marker, are recreated; a present file that differs refuses, so
  a newer keyring is never replaced, and the verifier key is never written. U2's own
  `control_key_recovery.py` keeps U2's test folder and snapshot format.
- `readiness-evidence`: PaperAssistance's reviewed real-model evidence marker
  (`profile/evidence/model-readiness.json`, BR7.7).
- `latency-summaries` `{from, until}`: the host's latency lines in that window, read
  only, for the switch-start decision (U8 plan Step 70(d), L1-59).
- `replace-cursor-key` (U8 plan Step 72(a), L1-4): a new search cursor key in the
  profile's `cursor-key/`, refused while v2 runs, as `control-key-start` is. Open search
  and job-list pages then restart at their first page.
- `provider-previews` `{provider, digest?}` (U8 plan Step 106(e), CP-3): a held outward
  provider's previews held since the switch's check, by digest and size, or one's exact
  content; read only, on a live profile.
- `provider-decision` `{provider, approvalId, subject}`: your `provider-sign-in` or
  `provider-first-effect` decision applied with the subject `cutover decide` showed
  (`ProviderActivation.approve`, every binding check of the switch and the latest
  decision on this side), on the profile's ledger.
- `provider-failed` `{provider}`: a sign-in provider whose real sign-in failed in the
  window recorded unavailable, only while the cutover is switching.

**Released logins (D5).** A word that needs the operator tool's login or the restore
login takes the password in its input as `login.password`: the operator tool released it
in person (`docsuri-credential-release`, onto a pipe) and handed it on through this
program's standard input. The password is passed to one connection as a libpq
parameter and dropped after the word; it is never an argument, an environment variable
or a file. `pg_restore` has no such parameter, so it reads the password at its own
prompt from a pseudo-terminal this program opens (`pg_restore --password`): the
password crosses only that terminal (the choice recorded for D5).

`control-key-recovery` runs while v2 is stopped, as U2's operator recovery does; the
keyring's own lock serialises it and `control-key-start` with any other custody writer.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import sys
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import BinaryIO

from docsuri_ops.arrangement.paths import (
    DATABASE_ROLES,
    PRODUCTION_DATABASES,
    Accounts,
    ArrangementPaths,
)

WORDS = (
    "migrate", "restore-evaluate", "restore-database", "recreate-database", "remove-database",
    "create-export-key-after-loss", "rotate-export-key", "retire-export-key",
    "export-key-counts", "replace-verifier-key", "control-key-recovery", "readiness-evidence",
    "create-disposable", "restore-import", "prepare-production",
    # Your decision of 2026-10-24 ("The production tool's new words").
    "export-settings", "provider-environment", "research-review",
    # Your decisions of 2026-10-24 ("Add a key snapshot step") and of 2026-10-25 ("Start
    # it at install, U8 snapshot").
    "control-key-start",
    # The soak's latency lines for your switch-start decision (U8 plan Step 70(d), L1-59).
    "latency-summaries",
    # The search cursor key's replacement while v2 is stopped (U8 plan Step 72(a), L1-4).
    "replace-cursor-key",
    # The providers' window words (U8 plan Step 106(e); your request of 2026-11-14, "Add
    # the defect fixes").
    "provider-previews", "provider-decision", "provider-failed",
)
# v2's three roles, which `control-key-start` and `replace-cursor-key` need stopped
# (u8_platform.platform_profile's first three production labels).
V2_ROLES = ("org.docsuri.v2.host", "org.docsuri.v2.workers", "org.docsuri.v2.scheduler")
REFUSED_ENVIRONMENT = ("PYTHON", "DYLD_", "LD_")
MAX_INPUT = 64 * 1024
MAX_ARCHIVE = 64 * 1024**3
RESTORE_OPTIONS = "-c maintenance_work_mem=1GB -c max_parallel_maintenance_workers=2"
RESTORE_SECONDS = 2700
OWNER_ROLE = re.compile(r"docsuri_[a-z]+_owner")
BASE_ENTRIES = ("SCHEMA", "EXTENSION", "COMMENT")
PLATFORM_IDENTITY = "public.docsuri_platform_identity"
_UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
CONSEQUENCES = {
    "migrate": "owners-migrated-in-order",
    "restore-evaluate": "tombstoned-owners-not-revived",
    "restore-database": "database-restored-from-set",
    "recreate-database": "database-recreated-empty-of-owner-data",
    "remove-database": "disposable-database-removed",
    "create-export-key-after-loss": "tokens-under-lost-key-need-reconnect",
    "rotate-export-key": "tokens-resealed-under-new-key",
    "retire-export-key": "retired-key-opens-nothing",
    "export-key-counts": "none",
    "replace-verifier-key": "every-session-and-proof-ended",
    "control-key-recovery": "missing-control-key-custody-recreated",
    "control-key-start": "new-sign-in-secrets-use-the-started-key",
    "readiness-evidence": "real-model-executor-may-run",
    "create-disposable": "disposable-database-created",
    "restore-import": "v1-snapshot-restored-into-import-database",
    "prepare-production": "production-database-copied-from-template",
    "export-settings": "export-settings-take-effect-at-the-next-start",
    "provider-environment": "providers-configured-at-the-next-start",
    "research-review": "review-written-for-your-decision",
    "latency-summaries": "none",
    "replace-cursor-key": "open-cursors-restart",
    "provider-previews": "none",
    "provider-decision": "provider-follows-your-decision",
    "provider-failed": "sign-in-provider-unavailable",
}


class Refused(Exception):
    def __init__(self, reason: str, **facts):
        super().__init__(reason)
        self.reason, self.facts = reason, facts


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def _connect(**options):
    import psycopg

    return psycopg.connect(**options)


@dataclass
class ToolContext:
    """Where the tool works: the arrangement's paths (a test prefix in tests), the
    service account it must run as, the clock, the database connector and the
    `pg_restore` runner."""

    paths: ArrangementPaths = field(default_factory=ArrangementPaths)
    service_uid: int = field(default_factory=lambda: Accounts.standard().service.uid)
    clock: Callable[[], dt.datetime] = _now
    connect: Callable = _connect
    restore: Callable | None = None
    port: int = 15432
    release: Path | None = None
    # `research-review`'s parts (the production runtime and CorpusContent's reads by
    # default; a mock runtime and corpus in tests), its monotonic clock and probe pace.
    runtime: Callable[[], object] | None = None
    corpus: Callable | None = None
    monotonic: Callable[[], float] = time.monotonic
    probe_interval: float = 1.0
    # The account that owns the stop records (root; the test's own user in tests).
    root_uid: int = 0

    def v2_stopped(self) -> bool:
        """Each of v2's three roles has a current stop record: root-owned, in its fixed
        format, for its own label, within its 14-day bound (`docsuri-service-stop`'s)."""
        from docsuri_ops.u8_platform.fixed import read_stop_record

        now = self.clock()
        for label in V2_ROLES:
            record = read_stop_record(self.paths.control_stops / f"{label}.json",
                                      owner_uid=self.root_uid, now=now)
            if record is None or record["label"] != label:
                return False
        return True

    def profile(self):
        from backend.u8_profile import ProductionProfile

        return ProductionProfile.load(self.paths.profile / "environment.json",
                                      service_uid=self.service_uid)

    def source(self) -> Path:
        """The release's own source tree (where the migrations and schemas live)."""
        return self.release or Path(__file__).resolve().parents[3]


def _login(document: Mapping, user: str) -> str:
    """The released password of `user` (the operator tool's login or the restore login),
    handed on through standard input; refused when absent or outside its form."""
    login = document.get("login")
    if user not in (DATABASE_ROLES.operator, DATABASE_ROLES.restore) or not isinstance(
        login, dict
    ) or set(login) != {"password"} or not isinstance(login["password"], str) or not (
        16 <= len(login["password"]) <= 256
    ):
        raise Refused("released-login-required")
    return login["password"]


def _open(context: ToolContext, user: str, password: str, database: str, **options):
    return context.connect(host="127.0.0.1", port=context.port, dbname=database, user=user,
                           password=password, require_auth="scram-sha-256",
                           connect_timeout=5, **options)


def _only(document: Mapping, allowed: set[str]) -> None:
    if not set(document) <= allowed:
        raise Refused("input-field-refused")


# --- migrate (cicd-pipeline § 5.1 step 8) ---------------------------------------------------


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pending_migrations(known: Mapping[str, str], source: Path) -> list[tuple[str, str]]:
    """U1's amendments then the composed chain, each file not yet applied; an applied
    file whose bytes changed refuses (append-only by digest)."""
    from backend.u8_migrations import REPLACED, U1_AMENDMENTS, migrations

    files = [*U1_AMENDMENTS, *migrations()]
    if set(file for _, file in files) & set(REPLACED):
        raise Refused("chain-lists-a-left-out-file")
    if set(REPLACED) & set(known):
        raise Refused("database-holds-a-left-out-file")
    pending = []
    for owner, file in files:
        if file in known:
            if known[file] != _digest(source / file):
                raise Refused("applied-migration-changed")
            continue
        pending.append((owner, file))
    return pending


def migrate(context: ToolContext, document: Mapping) -> dict:
    _only(document, {"login"})
    password = _login(document, DATABASE_ROLES.operator)
    profile = context.profile()
    source = context.source()
    # A current database that does not exist yet (the first rehearsal database before
    # `cutover begin` creates it) is reported `absent` (your decision of 2026-10-24).
    state, applied, failed = "absent", [], None
    if _exists(context, password, profile.database_name):
        state = "migrated"
        applied, failed = _migrate_database(context, password, profile.database_name,
                                            profile.run_id, source)
    # The template the rehearsal databases are copied from stays on the same chain
    # (the person's decision of 2026-10-24, "Build it, test on test v1").
    template = None
    if not failed:
        template_applied, failed = _migrate_database(
            context, password, PRODUCTION_DATABASES.template, profile.run_id, source)
        template = {"database": PRODUCTION_DATABASES.template, "applied": template_applied}
    platform = None if failed else migrate_platform(context, password)
    result = {"database": profile.database_name, "state": state, "applied": applied,
              "failed": failed, "template": template, "platform": platform}
    if failed:
        raise Refused("migration-failed", **result)
    return result


def _exists(context: ToolContext, password: str, database: str) -> bool:
    with _open(context, DATABASE_ROLES.operator, password, "postgres", autocommit=True) as conn:
        return conn.execute("SELECT 1 FROM pg_database WHERE datname=%s",
                            (database,)).fetchone() is not None


def _migrate_database(context: ToolContext, password: str, database: str, run_id: str,
                      source: Path) -> tuple[list[str], dict | None]:
    """The composed chain's pending files on one database of the run, each as its
    owner role in its own transaction; the first that fails stops the rest."""
    from psycopg import sql
    from psycopg.types.json import Jsonb

    applied, failed = [], None
    with _open(context, DATABASE_ROLES.operator, password, database) as conn:
        row = conn.execute("SELECT run_id,schema_hashes FROM public.docsuri_local_identity"
                           ).fetchone()
        if row is None or row[0] != run_id:
            raise Refused("database-identity-differs")
        conn.commit()
        known = dict(row[1])
        if not conn.execute("SELECT has_function_privilege('docsuri_operations_owner',"
                            "'pg_catalog.pg_ls_waldir()','EXECUTE')").fetchone()[0]:
            raise Refused("capacity-observation-not-granted")
        conn.commit()
        for owner, file in pending_migrations(known, source):
            try:
                with conn.transaction():
                    conn.execute(sql.SQL("SET LOCAL ROLE {}").format(
                        sql.Identifier(f"docsuri_{owner}_owner")))
                    conn.execute((source / file).read_text(), prepare=False)
                    conn.execute("RESET ROLE")
                    known[file] = _digest(source / file)
                    conn.execute("UPDATE public.docsuri_local_identity SET schema_hashes=%s "
                                 "WHERE singleton", (Jsonb(known),))
            except Exception as error:  # noqa: BLE001 - this file rolls back; earlier stay
                failed = {"database": database, "file": file, "owner": owner,
                          "error": type(error).__name__}
                break
            applied.append(file)
    return applied, failed


def protocol_rows(source: Path) -> list[tuple]:
    """Every protocol row of inventory version 2, in the protocol table's column order:
    U7's eight, unchanged, then A6's (as the realm's tool seeds them)."""
    from docsuri_ops.platform_control.inventory import load_inventory
    from docsuri_ops.u8_platform.u8_protocols import load_revision

    path = source / "ops/src/docsuri_ops/platform_control/inventory.json"
    rows = []
    for protocol in load_inventory(path).protocols:
        row = protocol.as_row()
        rows.append((row["name"], row["disposition"], row["authority_class"],
                     row["max_age_seconds"], row["deadline_seconds"], row["effect_kind"],
                     row["native_verified"], row["consumer_impact"]))
    impacts = {item["name"]: item["consumerImpact"]
               for item in json.loads(path.read_text())["u8Protocols"]}
    for protocol in load_revision(path).u8:
        rows.append((protocol.name, "retained-local", protocol.authority_class,
                     protocol.max_age_seconds, protocol.deadline_seconds, protocol.effect_kind,
                     True, impacts[protocol.name]))
    return rows


PROTOCOL_COLUMNS = ("name", "disposition", "authority_class", "max_age_seconds",
                    "deadline_seconds", "effect_kind", "native_verified", "consumer_impact")


def migrate_platform(context: ToolContext, password: str) -> dict:
    """PlatformControl's store in production (`docsuri_v2_platform`): when the store's
    digest changed (`platform_profile.store_digest`, the inventory and the amendment
    together), U8's additive `u8_store.sql` again, then each missing protocol row; an
    existing row that differs refuses, so U7's rows and every receipt stay as they are. A
    store whose digest matches is verified and left as it is."""
    from psycopg import sql

    from docsuri_ops.platform_control import OWNER_ROLE
    from docsuri_ops.u8_platform.platform_profile import STORE_AMENDMENT, store_digest

    source = context.source()
    digest = store_digest(source)
    amendment = (source / STORE_AMENDMENT).read_text()
    with _open(context, DATABASE_ROLES.operator, password,
               PRODUCTION_DATABASES.platform) as conn:
        identity = conn.execute(f"SELECT inventory_hash FROM {PLATFORM_IDENTITY}").fetchone()
        if identity is None:
            raise Refused("platform-store-identity-missing")
        if identity[0] == digest:
            return {"state": "verified", "storeDigest": digest}
        added = []
        with conn.transaction():
            conn.execute(sql.SQL("SET LOCAL ROLE {}").format(sql.Identifier(OWNER_ROLE)))
            conn.execute(amendment, prepare=False)
            columns = ", ".join(PROTOCOL_COLUMNS)
            for row in protocol_rows(source):
                existing = conn.execute(
                    f"SELECT {columns} FROM platform_control.protocol WHERE name=%s",
                    (row[0],)).fetchone()
                if existing is None:
                    conn.execute(f"INSERT INTO platform_control.protocol ({columns}) VALUES "
                                 "(%s,%s,%s,%s,%s,%s,%s,%s)", row)
                    added.append(row[0])
                elif tuple(existing) != row:
                    raise Refused("platform-protocol-differs")
            conn.execute("RESET ROLE")
            conn.execute(f"UPDATE {PLATFORM_IDENTITY} SET inventory_hash=%s WHERE singleton",
                         (digest,))
        return {"state": "migrated", "storeDigest": digest, "added": added}


# --- restore-evaluate, restore-database, recreate and remove (Workflow 7, BR9.17) ----------


def _database(document: Mapping, *, kinds: tuple[str, ...]) -> str:
    name = document.get("database")
    if not isinstance(name, str) or PRODUCTION_DATABASES.kind_of(name) not in kinds:
        raise Refused("database-refused")
    return name


def restore_evaluate(context: ToolContext, document: Mapping) -> dict:
    from backend.modules.operations import restore_checks

    _only(document, {"login", "database", "accounts"})
    password = _login(document, DATABASE_ROLES.restore)
    context.profile()
    database = _database(document, kinds=("production", "rehearsal"))
    accounts = document.get("accounts")
    if not isinstance(accounts, list) or len(accounts) > 10_000 or not all(
        isinstance(item, str) and _UUID.fullmatch(item) for item in accounts
    ):
        raise Refused("accounts-refused")
    with _open(context, DATABASE_ROLES.restore, password, database, autocommit=True) as conn:
        replayed = restore_checks.replay(conn, accounts)
        surviving = restore_checks.surviving(conn, accounts)
    return {**replayed, "surviving": surviving}


def owners_entries(listing: str) -> str:
    """The set's table of contents without the base: only the owners' entries."""
    kept = []
    for line in listing.splitlines():
        if not line.strip() or line.startswith(";"):
            continue
        fields = line.split()
        if len(fields) < 5 or fields[3] in BASE_ENTRIES or not OWNER_ROLE.fullmatch(fields[-1]):
            continue
        kept.append(line)
    return "\n".join(kept) + "\n"


def run_with_password(argv: list[str], password: str, *, environment: dict,
                      seconds: float = RESTORE_SECONDS) -> int:
    """Run a client that asks for its password at its own prompt, on a pseudo-terminal
    this process opened: the password crosses only that terminal (D5)."""
    import pty
    import select
    import time

    pid, descriptor = pty.fork()
    if pid == 0:  # the child: the terminal is its controlling one
        os.execve(argv[0], argv, environment)
    deadline = time.monotonic() + seconds
    sent, output = False, b""
    try:
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                os.kill(pid, 9)
                break
            ready, _, _ = select.select([descriptor], [], [], min(remaining, 1.0))
            if ready:
                try:
                    chunk = os.read(descriptor, 4096)
                except OSError:
                    break
                if not chunk:
                    break
                output = (output + chunk)[-256:]
                if not sent and b"assword" in output:
                    os.write(descriptor, password.encode() + b"\n")
                    sent = True
            finished, status = os.waitpid(pid, os.WNOHANG)
            if finished:
                return os.waitstatus_to_exitcode(status)
    finally:
        os.close(descriptor)
    _, status = os.waitpid(pid, 0)
    return os.waitstatus_to_exitcode(status)


def _bin(context: ToolContext, name: str) -> str:
    return str(context.paths.postgres_runtime / "bin" / name)


def restore_database(context: ToolContext, stdin: BinaryIO) -> dict:
    """The header line, then the archive: spooled privately, its digest checked, then
    restored with `pg_restore -j 2 --no-comments` as the restore login."""
    import subprocess

    header_line = stdin.readline(MAX_INPUT + 1)
    try:
        header = json.loads(header_line)
    except ValueError:
        raise Refused("input-not-json") from None
    if not isinstance(header, dict):
        raise Refused("input-not-an-object")
    _only(header, {"login", "database", "setPath", "setSha256", "operationId"})
    password = _login(header, DATABASE_ROLES.restore)
    context.profile()
    database = _database(header, kinds=("production",))
    expected = str(header.get("setSha256", ""))
    operation = str(header.get("operationId", ""))
    if not re.fullmatch(r"[0-9a-f]{64}", expected) or not _UUID.fullmatch(operation):
        raise Refused("set-identity-refused")
    spool_folder = context.paths.profile / "restore-spool"
    spool_folder.mkdir(mode=0o700, exist_ok=True)
    spool = spool_folder / f"{operation}.archive"
    listing_path = spool_folder / f"{operation}.list"
    digest = hashlib.sha256()
    descriptor = os.open(spool, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        written = 0
        while block := stdin.read(1 << 20):
            written += len(block)
            if written > MAX_ARCHIVE:
                raise Refused("archive-too-large")
            digest.update(block)
            os.write(descriptor, block)
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = -1
        if digest.hexdigest() != expected:
            raise Refused("streamed-set-digest-mismatch")
        listed = subprocess.run([_bin(context, "pg_restore"), "-l", str(spool)],
                                capture_output=True, timeout=600, check=False)
        if listed.returncode != 0:
            raise Refused("restore-set-unreadable")
        listing = os.open(listing_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                          0o600)
        with os.fdopen(listing, "w") as stream:
            stream.write(owners_entries(listed.stdout.decode("utf-8", "replace")))
        target = (f"host=127.0.0.1 port={context.port} dbname={database} "
                  f"user={DATABASE_ROLES.restore} require_auth=scram-sha-256 connect_timeout=5")
        argv = [_bin(context, "pg_restore"), "-j", "2", "--no-comments", "--exit-on-error",
                "--password", "-L", str(listing_path), "-d", target, str(spool)]
        runner = context.restore or run_with_password
        code = runner(argv, password, environment={"PATH": "/usr/bin:/bin",
                                                   "PGOPTIONS": RESTORE_OPTIONS})
        if code != 0:
            raise Refused("restore-failed")
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        spool.unlink(missing_ok=True)
        listing_path.unlink(missing_ok=True)
    return {"database": database, "setSha256": expected}


def capture_base(conn, database: str) -> dict:
    """What a recreate must keep: the database's grants, the owners' empty schemas with
    their owners, the public schema's grants and the identity row with its readers."""
    grants = conn.execute(
        "SELECT coalesce(r.rolname,'PUBLIC'),a.privilege_type FROM pg_database d, "
        "aclexplode(d.datacl) a LEFT JOIN pg_roles r ON r.oid=a.grantee WHERE d.datname="
        "current_database() ORDER BY 1,2").fetchall()
    base = {
        "database": [list(row) for row in grants],
        "schemas": [list(row) for row in conn.execute(
            "SELECT nspname,pg_get_userbyid(nspowner) FROM pg_namespace WHERE nspname "
            "NOT LIKE 'pg\\_%' AND nspname NOT IN ('public','information_schema') "
            "ORDER BY 1").fetchall()],
        "public": [list(row) for row in conn.execute(
            "SELECT coalesce(r.rolname,'PUBLIC'),a.privilege_type FROM pg_namespace n, "
            "aclexplode(n.nspacl) a LEFT JOIN pg_roles r ON r.oid=a.grantee "
            "WHERE n.nspname='public' ORDER BY 1,2").fetchall()],
        "identity": None,
    }
    if conn.execute("SELECT to_regclass('public.docsuri_local_identity')").fetchone()[0]:
        row = conn.execute("SELECT run_id,schema_hashes FROM public.docsuri_local_identity"
                           ).fetchone()
        readers = [item[0] for item in conn.execute(
            "SELECT r.rolname FROM pg_class c, aclexplode(c.relacl) a JOIN pg_roles r "
            "ON r.oid=a.grantee WHERE c.oid='public.docsuri_local_identity'::regclass "
            "AND a.privilege_type='SELECT' ORDER BY 1").fetchall()]
        base["identity"] = {"runId": row[0], "schemaHashes": row[1], "readers": readers}
    return base


def replay_base(conn, database: str, base: dict, *, identity: bool) -> None:
    from psycopg import sql
    from psycopg.types.json import Jsonb

    name = sql.Identifier(database)

    def grantee(role: str):
        return sql.SQL("PUBLIC") if role == "PUBLIC" else sql.Identifier(role)

    conn.execute(sql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC").format(name))
    for role, privilege in base["database"]:
        if privilege in ("CONNECT", "CREATE", "TEMPORARY"):
            conn.execute(sql.SQL("GRANT {} ON DATABASE {} TO {}").format(
                sql.SQL(privilege), name, grantee(role)))
    conn.execute("REVOKE ALL ON SCHEMA public FROM PUBLIC")
    for role, privilege in base["public"]:
        if privilege in ("USAGE", "CREATE") and role != "pg_database_owner":
            conn.execute(sql.SQL("GRANT {} ON SCHEMA public TO {}").format(
                sql.SQL(privilege), grantee(role)))
    for schema, owner in base["schemas"]:
        conn.execute(sql.SQL("CREATE SCHEMA {} AUTHORIZATION {}").format(
            sql.Identifier(schema), sql.Identifier(owner)))
    recorded = base.get("identity")
    if identity and recorded is not None:
        conn.execute("CREATE TABLE public.docsuri_local_identity (singleton boolean PRIMARY KEY "
                     "CHECK(singleton),run_id text NOT NULL,schema_hashes jsonb NOT NULL)")
        conn.execute("INSERT INTO public.docsuri_local_identity VALUES(true,%s,%s)",
                     (recorded["runId"], Jsonb(recorded["schemaHashes"])))
        for role in recorded["readers"]:
            conn.execute(sql.SQL("GRANT SELECT ON public.docsuri_local_identity TO {}").format(
                sql.Identifier(role)))


def recreate_database(context: ToolContext, document: Mapping) -> dict:
    """Drop and create the production database from `template1` (pgvector in it, D14)
    as the operator tool's login, keeping its base; an abandonment's recreate keeps no
    identity row, so v2's start refuses until its owners' migrations run again."""
    from psycopg import sql

    _only(document, {"login", "database", "operationId", "abandonment"})
    password = _login(document, DATABASE_ROLES.operator)
    context.profile()
    database = _database(document, kinds=("production",))
    abandonment = document.get("abandonment", False) is True
    kept = context.paths.profile / "recreate" / f"{database}.json"
    try:
        with _open(context, DATABASE_ROLES.operator, password, database) as conn:
            base = capture_base(conn, database)
            conn.commit()
        kept.parent.mkdir(mode=0o700, exist_ok=True)
        kept.write_text(json.dumps(base))
        os.chmod(kept, 0o600)
    except Refused:
        raise
    except Exception:  # noqa: BLE001 - dropped by an earlier attempt: its kept base
        if not kept.exists():
            raise Refused("recreate-base-unknown") from None
        base = json.loads(kept.read_text())
    with _open(context, DATABASE_ROLES.operator, password, "postgres", autocommit=True) as conn:
        conn.execute("SET statement_timeout = '600s'")
        conn.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(
            sql.Identifier(database)))
        conn.execute(sql.SQL("CREATE DATABASE {} TEMPLATE template1 ENCODING 'UTF8' "
                             "LOCALE 'C'").format(sql.Identifier(database)))
    with _open(context, DATABASE_ROLES.operator, password, database, autocommit=True) as conn:
        replay_base(conn, database, base, identity=not abandonment)
    return {"database": database, "abandonment": abandonment}


def remove_database(context: ToolContext, document: Mapping) -> dict:
    """A rehearsal, import or scratch database only, by its fixed pattern, through the
    operator tool's login, which inherits the disposable-databases role's ownership; the
    production database and PlatformControl's store match no pattern (BR9.17)."""
    from psycopg import sql

    _only(document, {"login", "database", "operationId"})
    password = _login(document, DATABASE_ROLES.operator)
    context.profile()
    database = _database(document, kinds=("rehearsal", "import", "scratch"))
    with _open(context, DATABASE_ROLES.operator, password, "postgres", autocommit=True) as conn:
        conn.execute("SET statement_timeout = '600s'")
        conn.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(database)))
    return {"database": database}


# --- the migration's databases (the person's decision of 2026-10-24, "Build it, test on
# --- test v1") ---------------------------------------------------------------------------


def _connect_grants(conn, database: str) -> list[str]:
    """The roles holding CONNECT on one database (the production database's readers)."""
    return [row[0] for row in conn.execute(
        "SELECT r.rolname FROM pg_database d, aclexplode(d.datacl) a JOIN pg_roles r "
        "ON r.oid=a.grantee WHERE d.datname=%s AND a.privilege_type='CONNECT' ORDER BY 1",
        (database,)).fetchall()]


def _template_current(conn, run_id: str, source: Path) -> None:
    """The template holds this run's identity and every file of the chain."""
    row = conn.execute("SELECT run_id,schema_hashes FROM public.docsuri_local_identity"
                       ).fetchone()
    if row is None or row[0] != run_id:
        raise Refused("template-identity-differs")
    if pending_migrations(dict(row[1]), source):
        raise Refused("template-not-current")


def create_disposable(context: ToolContext, document: Mapping) -> dict:
    """A rehearsal or import database, created as the disposable-databases role, which
    then owns it, so the standing removal can drop it (BR9.17):

    - a rehearsal database is the template copied whole (the composed schema, the rows
      the chain seeds and the run's identity row), with the production database's
      CONNECT grants, so v2's owners and workers run on it as on production;
    - an import database is empty (`template1`); one a resumed import made before is
      replaced, since the snapshot's dump is restored into it again.

    A rehearsal database's creation is idempotent for its own name: a caller records the
    name before it asks (the CutoverRecord's begin, a rollback, a dry run), so when a
    create succeeded on the server but its answer was lost, the retry finds that
    database. One that exists, is owned by the disposable-databases role and carries the
    template's identity and chain counts as created, and its PUBLIC revoke and CONNECT
    grants are applied again (they may not have run). Any other existing database under
    the name is refused and never touched (`rehearsal-database-not-disposable`,
    `template-identity-differs`)."""
    from psycopg import sql

    _only(document, {"login", "database", "operationId"})
    password = _login(document, DATABASE_ROLES.operator)
    profile = context.profile()
    database = _database(document, kinds=("rehearsal", "import"))
    kind = PRODUCTION_DATABASES.kind_of(database)
    ident = sql.Identifier(database)
    if kind == "rehearsal":
        with _open(context, DATABASE_ROLES.operator, password,
                   PRODUCTION_DATABASES.template) as conn:
            _template_current(conn, profile.run_id, context.source())
            conn.commit()
    existing = False
    if kind == "rehearsal":
        existing = _existing_rehearsal(context, password, database, profile.run_id)
    with _open(context, DATABASE_ROLES.operator, password, "postgres", autocommit=True) as conn:
        conn.execute("SET statement_timeout = '600s'")
        conn.execute(sql.SQL("SET ROLE {}").format(sql.Identifier(DATABASE_ROLES.disposable)))
        if kind == "import":
            conn.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(ident))
            conn.execute(sql.SQL("CREATE DATABASE {} TEMPLATE template1").format(ident))
            return {"database": database, "kind": kind}
        if not existing:
            conn.execute(sql.SQL("CREATE DATABASE {} TEMPLATE {}").format(
                ident, sql.Identifier(PRODUCTION_DATABASES.template)))
        conn.execute(sql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC").format(ident))
        granted = _connect_grants(conn, PRODUCTION_DATABASES.production)
        for role in granted:
            conn.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                ident, sql.Identifier(role)))
    result = {"database": database, "kind": kind, "connectGrants": granted}
    return {**result, "existing": True} if existing else result


def _existing_rehearsal(context: ToolContext, password: str, database: str,
                        run_id: str) -> bool:
    """Whether the named rehearsal database already exists as an earlier create of this
    word left it: owned by the disposable-databases role, with the template's identity
    and chain (a whole-template copy, which `CREATE DATABASE ... TEMPLATE` makes in one
    step). False when it does not exist; refused when it exists in any other shape."""
    with _open(context, DATABASE_ROLES.operator, password, "postgres", autocommit=True) as conn:
        row = conn.execute("SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname=%s",
                           (database,)).fetchone()
    if row is None:
        return False
    if row[0] != DATABASE_ROLES.disposable:
        raise Refused("rehearsal-database-not-disposable")
    with _open(context, DATABASE_ROLES.operator, password, database) as conn:
        _template_current(conn, run_id, context.source())
        conn.commit()
    return True


def restore_import(context: ToolContext, stdin: BinaryIO) -> dict:
    """The header line, then the snapshot's dump of v1: spooled privately, its digest
    checked, then restored into the run's import database as the disposable-databases
    role (`--no-owner --no-privileges --role`), so nothing of v1's ownership or grants
    comes along and the import database stays the disposable role's."""
    header_line = stdin.readline(MAX_INPUT + 1)
    try:
        header = json.loads(header_line)
    except ValueError:
        raise Refused("input-not-json") from None
    if not isinstance(header, dict):
        raise Refused("input-not-an-object")
    _only(header, {"login", "database", "sha256", "operationId"})
    password = _login(header, DATABASE_ROLES.operator)
    context.profile()
    database = _database(header, kinds=("import",))
    expected, operation = str(header.get("sha256", "")), str(header.get("operationId", ""))
    if not re.fullmatch(r"[0-9a-f]{64}", expected) or not _UUID.fullmatch(operation):
        raise Refused("dump-identity-refused")
    spool_folder = context.paths.profile / "import-spool"
    spool_folder.mkdir(mode=0o700, exist_ok=True)
    spool = spool_folder / f"{operation}.dump"
    digest = hashlib.sha256()
    descriptor = os.open(spool, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        written = 0
        while block := stdin.read(1 << 20):
            written += len(block)
            if written > MAX_ARCHIVE:
                raise Refused("archive-too-large")
            digest.update(block)
            os.write(descriptor, block)
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = -1
        if digest.hexdigest() != expected:
            raise Refused("streamed-dump-digest-mismatch")
        target = (f"host=127.0.0.1 port={context.port} dbname={database} "
                  f"user={DATABASE_ROLES.operator} require_auth=scram-sha-256 connect_timeout=5")
        argv = [_bin(context, "pg_restore"), "--no-owner", "--no-privileges", "--no-comments",
                "--role", DATABASE_ROLES.disposable, "--exit-on-error", "--password", "-d",
                target, str(spool)]
        runner = context.restore or run_with_password
        if runner(argv, password, environment={"PATH": "/usr/bin:/bin"}) != 0:
            raise Refused("import-restore-failed")
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        spool.unlink(missing_ok=True)
    return {"database": database, "sha256": expected}


def prepare_production(context: ToolContext, document: Mapping) -> dict:
    """A final run's target (BR6.3): the production database, just recreated empty by
    `platform.database.recreate`, is replaced by the template copied whole, so it holds
    the composed schema, the chain's seeded rows and the run's identity and nothing
    else; its CONNECT grants are kept. Refused while it holds any owner table."""
    from psycopg import sql

    _only(document, {"login", "database", "operationId"})
    password = _login(document, DATABASE_ROLES.operator)
    profile = context.profile()
    database = _database(document, kinds=("production",))
    with _open(context, DATABASE_ROLES.operator, password, database) as conn:
        if conn.execute("SELECT count(*) FROM pg_class c JOIN pg_namespace n ON "
                        "n.oid=c.relnamespace WHERE c.relkind='r' AND n.nspname NOT IN "
                        "('pg_catalog','information_schema','public')").fetchone()[0]:
            raise Refused("production-database-not-empty")
        conn.commit()
    with _open(context, DATABASE_ROLES.operator, password,
               PRODUCTION_DATABASES.template) as conn:
        _template_current(conn, profile.run_id, context.source())
        conn.commit()
    ident = sql.Identifier(database)
    with _open(context, DATABASE_ROLES.operator, password, "postgres", autocommit=True) as conn:
        conn.execute("SET statement_timeout = '600s'")
        granted = _connect_grants(conn, database)
        conn.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(ident))
        conn.execute(sql.SQL("CREATE DATABASE {} TEMPLATE {}").format(
            ident, sql.Identifier(PRODUCTION_DATABASES.template)))
        conn.execute(sql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC").format(ident))
        for role in granted:
            conn.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                ident, sql.Identifier(role)))
    return {"database": database, "connectGrants": granted}


# --- U6's key commands, AccountAccess's verifier key, the model evidence --------------------


def export_key(context: ToolContext, word: str, document: Mapping) -> dict:
    from backend.modules.export import key_commands
    from backend.u6_real_export import load_activation
    from backend.u8_outward import export_policy

    _only(document, {"login", "version"} if word == "retire-export-key" else {"login"})
    password = _login(document, DATABASE_ROLES.operator)
    profile = context.profile()
    folder = profile.root / "export-keys"
    policy = export_policy(profile, load_activation(profile))
    with _open(context, DATABASE_ROLES.operator, password, profile.database_name) as conn:
        if word == "export-key-counts":
            return key_commands.key_counts(folder, profile.run_id, conn, policy=policy)
        if word == "create-export-key-after-loss":
            return key_commands.create_key_after_loss(folder, profile.run_id, conn, policy=policy)
        if word == "rotate-export-key":
            return key_commands.rotate_key(folder, profile.run_id, conn, policy=policy)
        return key_commands.retire_key(folder, profile.run_id, conn,
                                       str(document.get("version", "")), policy=policy)


def replace_verifier_key(context: ToolContext, document: Mapping) -> dict:
    from backend.modules.accounts.u8_verifier_key import (
        REPLACEMENT_REASONS,
        replace_verifier_key,
    )
    from backend.transactions import OwnerTransactions

    _only(document, {"expectedKeyRevision", "reasonKey"})
    if document.get("reasonKey") not in REPLACEMENT_REASONS:
        raise Refused("reason-refused")
    expected = document.get("expectedKeyRevision")
    if not isinstance(expected, str) or not re.fullmatch(r"absent|[0-9a-f]{32}", expected):
        raise Refused("key-revision-refused")
    from backend.modules.accounts.control_policy import PolicyUnavailable

    profile = context.profile()
    # § 3.1's production environment tool row (Step 51(c), L1-13).
    transactions = OwnerTransactions(profile, process="maintenance")
    try:
        return replace_verifier_key(transactions, expected_key_revision=expected,
                                    reason_key=document["reasonKey"], now=context.clock())
    except PolicyUnavailable:
        raise Refused("legacy-protected-factors-need-re-protection") from None
    except ValueError:
        raise Refused("stale-verifier-key-revision") from None
    finally:
        transactions.close()


def control_key_recovery(context: ToolContext, document: Mapping) -> dict:
    """U2's key recovery in production (BR6.2; your decisions of 2026-10-22, 2026-10-24 and
    2026-10-25): the profile's `control-keys/` folder, from U8's keyring snapshot named by
    its exact digest and generation. Only the keyring's missing files are recreated, and
    the verifier key is never written."""
    from backend.modules.accounts.control_policy import PolicyUnavailable
    from backend.modules.accounts.u8_verifier_key import KeyringRefused, recover_production

    _only(document, {"expectedDigest", "expectedGeneration"})
    digest = document.get("expectedDigest")
    generation = document.get("expectedGeneration")
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise Refused("recovery-digest-refused")
    if type(generation) is not int or not 1 <= generation <= 3:
        raise Refused("recovery-generation-refused")
    profile = context.profile()
    try:
        return recover_production(profile.root / "control-keys", profile_root=profile.root,
                                  run_id=profile.run_id, expected_digest=digest,
                                  expected_generation=generation)
    except KeyringRefused as refused:
        raise Refused("control-key-recovery-refused", detail=refused.reason) from None
    except PolicyUnavailable:
        raise Refused("control-key-recovery-refused", detail="keyring-custody") from None


def control_key_start(context: ToolContext, document: Mapping) -> dict:
    """The control keyring's start and U8's keyring snapshot (your decisions of 2026-10-24
    and 2026-10-25), in person while v2 is stopped: refused, writing nothing, while any of
    v2's roles runs or when the profile's folders fail their owner and mode checks."""
    from backend.modules.accounts.u8_verifier_key import KeyringRefused, start_keyring
    from backend.u8_profile import ProfileRefused

    _only(document, set())
    if not context.v2_stopped():
        raise Refused("control-key-start-refused", detail="v2-running")
    try:
        profile = context.profile()
    except ProfileRefused as refused:
        raise Refused("control-key-start-refused", detail=f"profile-{refused.check}") from None
    try:
        return start_keyring(profile.root, profile.run_id)
    except KeyringRefused as refused:
        raise Refused("control-key-start-refused", detail=refused.reason) from None


def replace_cursor_key(context: ToolContext, document: Mapping) -> dict:
    """The search cursor key's replacement (L1-4, U8 plan Step 72(a)), in person while v2
    is stopped: refused, writing nothing, while any of v2's three roles runs (a running
    process keeps the key it read at its start). It writes 32 random bytes to a staging
    file in `cursor-key/` (0600, created exclusively, never through a link), syncs it,
    replaces the key with it and syncs the folder; a missing key is created the same way.
    Cursors signed under the old key then no longer decode, so open search and job-list
    pages start again at their first page."""
    import secrets
    import stat

    from backend.u8_host import cursor_key_path
    from backend.u8_profile import ProfileRefused

    _only(document, set())
    if not context.v2_stopped():
        raise Refused("cursor-key-replace-refused", detail="v2-running")
    try:
        profile = context.profile()
    except ProfileRefused as refused:
        raise Refused("cursor-key-replace-refused", detail=f"profile-{refused.check}") from None
    path = cursor_key_path(profile)
    try:
        folder_info = path.parent.lstat()
    except FileNotFoundError:
        raise Refused("cursor-key-replace-refused", detail="folder-missing") from None
    if not stat.S_ISDIR(folder_info.st_mode):
        raise Refused("cursor-key-replace-refused", detail="folder-custody")
    existed = path.exists() or path.is_symlink()
    staging = path.parent / (f".{path.name}-" + secrets.token_hex(8))
    descriptor = os.open(staging, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(secrets.token_bytes(32))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(staging, path)
    except BaseException:
        staging.unlink(missing_ok=True)
        raise
    folder = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(folder)
    finally:
        os.close(folder)
    return {"keyReplaced": existed, "keyCreated": not existed}


def _instant(value) -> dt.datetime | None:
    if not isinstance(value, str):
        return None
    try:
        moment = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return moment if moment.tzinfo is not None else None


def latency_summaries(context: ToolContext, document: Mapping) -> dict:
    """The host's latency lines over `{from, until}`, read-only (U8 plan Step 70(d),
    L1-59): `request_context.window_summaries` of the profile's `evidence/latency` with
    production's 5-minute windows, for your switch-start decision. Two instants with an
    offset, `from` before `until`, at most the lines' 14-day retention apart; anything
    else is `window-outside-its-form`. It writes nothing."""
    from backend.request_context import window_summaries
    from backend.u8_policy import PRODUCTION_OPERATIONS

    _only(document, {"from", "until"})
    start, end = _instant(document.get("from")), _instant(document.get("until"))
    if start is None or end is None or end <= start or (
        (end - start).total_seconds() > PRODUCTION_OPERATIONS.latency_retention_seconds
    ):
        raise Refused("window-outside-its-form")
    context.profile()  # the production profile only, as every word
    return window_summaries(context.paths.profile / "evidence" / "latency", start=start,
                            end=end, window_seconds=PRODUCTION_OPERATIONS.latency_window_seconds)


def readiness_evidence(context: ToolContext, document: Mapping) -> dict:
    """The reviewed real-model evidence (BR7.7): the pinned digests reviewed and
    `purposes`, one evidence digest per purpose (`assistance` and/or `research`, each its
    own review; your decision of 2026-10-24), owner-only, in the profile. `research` is
    refused unless its digest names a `research-review` file in the profile. The marker
    keeps one digest per purpose (`u8_outward.model_readiness` reads it): a purpose is
    recorded once, the same digest again changes nothing, and a different digest for it
    is refused."""
    from backend.local_profile import private_bytes
    from backend.u8_outward import MARKER_PURPOSES, READINESS_MARKER

    from docsuri_ops.local_models import MODEL_PINS

    _only(document, {"models", "purposes"})
    if document.get("models") != MODEL_PINS:
        raise Refused("models-differ-from-the-pins")
    given = document.get("purposes")
    if not isinstance(given, dict) or not given or not set(given) <= MARKER_PURPOSES:
        raise Refused("purpose-refused")
    for evidence in given.values():
        if not isinstance(evidence, str) or not re.fullmatch(r"[0-9a-f]{64}", evidence):
            raise Refused("evidence-digest-refused")
    profile = context.profile()
    if "research" in given:
        from docsuri_ops.research_review import review_named

        if not review_named(profile.root, given["research"]):
            raise Refused("research-review-missing")
    path = profile.root.joinpath(*READINESS_MARKER)
    path.parent.mkdir(mode=0o700, exist_ok=True)
    purposes: dict = {}
    if path.exists():
        try:
            earlier = json.loads(private_bytes(path))
            purposes = dict(earlier["purposes"]) if earlier.get("models") == MODEL_PINS else {}
        except (OSError, ValueError, KeyError, TypeError):
            raise Refused("readiness-marker-unreadable") from None
    for purpose, evidence in given.items():
        if purposes.get(purpose) not in (None, evidence):
            raise Refused("purpose-already-recorded")
    purposes.update(given)
    value = {"models": dict(MODEL_PINS), "purposes": purposes,
             "recordedAt": context.clock().astimezone(dt.UTC).isoformat()}
    _write_private_json(path, value)
    return {"recorded": READINESS_MARKER[-1], "purposes": sorted(given)}


def _write_private_json(path: Path, value: dict) -> None:
    """Written whole and renamed into place, 0600, the service account's."""
    pending = path.with_name(path.name + ".pending")
    descriptor = os.open(pending, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        json.dump(value, stream, sort_keys=True)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(pending, path)


# --- the settings words and the research review (your decision of 2026-10-24) ---------------

PROVIDER_FIELDS = ("googleClientId", "googleClientSecret", "orcidClientId", "orcidClientSecret",
                   "resendApiKey", "accountMailSender", "digestSender")
PROVIDER_SECRETS = ("googleClientSecret", "orcidClientSecret", "resendApiKey")
MAX_SETTING = 512
SECRET_MINIMUM = 16
_SETTING = re.compile(r"[^\x00-\x1f\x7f]{1,512}")


def export_settings(context: ToolContext, document: Mapping) -> dict:
    """`real-export.json` (`runId`, `activationDestinationId`, `freeTerms`), checked by
    U6's own settings rule for this profile's run, then written 0600."""
    from backend.modules.export.errors import ExportError
    from backend.u6_host import ACTIVATION_FILE
    from backend.u6_real_export import parse_activation

    _only(document, {"runId", "activationDestinationId", "freeTerms"})
    profile = context.profile()
    try:
        parse_activation(dict(document), profile)
    except ExportError as error:
        field_name = (getattr(error, "current", None) or {}).get("field") or "settings"
        raise Refused(f"export-settings-refused:{field_name}"[:80]) from None
    _write_private_json(profile.root / ACTIVATION_FILE, dict(document))
    return {"written": ACTIVATION_FILE, "fields": sorted(document)}


def provider_environment(context: ToolContext, document: Mapping) -> dict:
    """`private-environment.json`: any of the providers' clients, secrets and senders,
    merged over what it holds; each secret at least 16 characters, each value a bounded
    line. Nothing it takes is ever reported back."""
    from backend.local_profile import private_bytes
    from backend.u8_host import PROVIDER_ENVIRONMENT

    _only(document, set(PROVIDER_FIELDS))
    if not document:
        raise Refused("input-field-refused")
    for name, value in document.items():
        if not isinstance(value, str) or not _SETTING.fullmatch(value):
            raise Refused("setting-outside-its-form")
        if name in PROVIDER_SECRETS and len(value) < SECRET_MINIMUM:
            raise Refused("secret-too-short")
    profile = context.profile()
    path = profile.root / PROVIDER_ENVIRONMENT
    current: dict = {}
    if path.exists() or path.is_symlink():
        try:
            current = json.loads(private_bytes(path))
        except (OSError, ValueError):
            raise Refused("private-environment-unreadable") from None
        if not isinstance(current, dict) or not set(current) <= set(PROVIDER_FIELDS):
            raise Refused("private-environment-unreadable")
    _write_private_json(path, {**current, **document})
    return {"written": PROVIDER_ENVIRONMENT, "fields": sorted(document)}


def research_review(context: ToolContext, document: Mapping) -> dict:
    """The fixed review set through `LocalResearchModel` on the production runtime, on
    three ready versions, creating no job (`research_review`); in person. While
    provider.models is observed unavailable it is refused at its start, before any
    runtime call (`_models_serving`)."""
    from backend.u8_outward import EMBEDDING_BATCH, EMBEDDING_KEEP_ALIVE, QUERY_SECONDS
    from backend.u8_research_model import CorpusRanker, LocalResearchModel

    from docsuri_ops.research_review import ReviewRefused, run_review, write_review

    _only(document, {"versions"})
    profile = context.profile()
    runtime = context.runtime() if context.runtime is not None else _production_runtime()
    release = _models_serving(context, profile, runtime)
    try:
        corpus, close = (context.corpus(profile) if context.corpus is not None
                         else _production_corpus(profile))
    except BaseException:
        release()
        raise
    try:
        from backend.modules.discovery.local_embedding import LocalEmbeddings

        embedder = LocalEmbeddings(runtime, keep_alive=EMBEDDING_KEEP_ALIVE,
                                   query_seconds=QUERY_SECONDS, batch=EMBEDDING_BATCH)
        provider = LocalResearchModel(runtime, ready=lambda: True,
                                      ranker=CorpusRanker(corpus, embedder),
                                      clock=context.monotonic)
        try:
            review = run_review(provider, runtime, embedder, corpus,
                                document.get("versions"), clock=context.monotonic,
                                probe_interval=context.probe_interval)
        except ReviewRefused as refused:
            raise Refused(str(refused)) from None
    finally:
        close()
        release()
    path, digest = write_review(profile.root, review, now=context.clock())
    return {"review": path.name, "evidenceSha256": digest, "items": len(review["items"]),
            "invalidAnswers": review["invalidAnswers"]}


REVIEW_HELD = "provider-held"


def _models_serving(context: ToolContext, profile, runtime) -> Callable[[], None]:
    """The review's circuit breaker (reliability-design § 10; L4-11): provider.models'
    stored state, read from the profile's own database (the newest observation,
    `unknown` with none or an unreadable store, `stale` past 900 s). While it reads
    `unavailable` the word is refused `provider-held` here, before any runtime call;
    otherwise the runtime is given the same reader, so a state that turns during the
    review stops its next request. Returns what closes the reader."""
    from backend.modules.operations.readiness import stored_state_reader
    from backend.u8_policy import PRODUCTION_OPERATIONS

    observed, release = stored_state_reader(profile, "provider.models", context.clock,
                                            PRODUCTION_OPERATIONS, process="maintenance")
    if callable(getattr(runtime, "held", None)):
        runtime.observed = observed
    if observed() == "unavailable":
        release()
        raise Refused(REVIEW_HELD)
    return release


def _production_runtime():
    from backend.modules.summarization.model_runtime import SharedModelRuntime

    return SharedModelRuntime()


def _production_corpus(profile):
    from backend.modules.corpus.repository import CorpusRepository
    from backend.transactions import OwnerTransactions

    # § 3.1's production environment tool row (Step 51(c), L1-13).
    transactions = OwnerTransactions(profile, process="maintenance")
    return CorpusRepository(transactions, files=None), transactions.close


# --- the providers' window words (U8 plan Step 106(e), CP-3) --------------------------------

PROVIDER_WORD_FIELDS = {"provider-previews": frozenset({"provider", "digest"}),
                        "provider-decision": frozenset({"provider", "approvalId", "subject"}),
                        "provider-failed": frozenset({"provider"})}


def provider_activation_word(context: ToolContext, word: str, document: dict) -> dict:
    """`provider-previews`, `provider-decision` and `provider-failed`: the service side
    of the cutover's provider words (`provider_activation.provider_word`) over the
    profile's ledger, with the settings v2's processes build from the profile (the
    maintainer, the configured providers and the previews folder, the service account's
    own). Only a live profile; the ledger is opened under its own lock and closed."""
    from backend import u8_host
    from backend.modules.operations.errors import OperationsError
    from backend.modules.operations.provider_activation import (
        ActivationSettings,
        ProviderActivation,
        provider_word,
    )

    profile = context.profile()
    if not set(document) <= PROVIDER_WORD_FIELDS[word]:
        raise Refused("input-field-refused")
    try:
        settings = ActivationSettings.from_profile(profile, u8_host.provider_secrets(profile))
        if settings.mode != "live":
            raise Refused("profile-not-live")
        ledger = u8_host.open_ledger(profile, context.clock)
    except u8_host.StartRefused as refused:
        raise Refused("start-check-failed", check=refused.check) from None
    try:
        activation = ProviderActivation(ledger, settings, clock=context.clock)
        return provider_word(activation, word, document)
    except OperationsError as error:
        reason = (error.current or {}).get("reasonKey") or error.code.lower()
        raise Refused(str(reason)) from None
    except (ValueError, TypeError):
        raise Refused("input-field-refused") from None
    finally:
        ledger.close()


# --- the installation's database (Workflow 20 step 3; phases.FoldersDatabasePhase) ---------

OWNERS = ("accounts", "assistance", "corpus", "discovery", "export", "library", "operations",
          "personalization", "research", "topics", "usage")
SESSION_GUARD_LOGINS = ("library", "personalization", "discovery", "usage", "assistance",
                        "research", "topics", "export")
CORPUS_GUARD_LOGINS = ("library", "discovery", "assistance", "research", "topics")
PLATFORM_LOGINS = {"operator": "docsuri_platform_operator",
                   "scheduler": "docsuri_platform_scheduler",
                   "reader": "docsuri_platform_reader"}  # u8_protocols.PRODUCTION_* hold the same
PLATFORM_PROVISIONER = "platform_control_provisioner"
OWNER_CONNECTION_LIMIT = 4  # performance-design § 3.1: the composed realm and production
_HEX = re.compile(r"[0-9a-f]{32,128}")


def _literal(password: str) -> str:
    """A generated password as an SQL literal: hexadecimal, so it needs no escaping."""
    if not _HEX.fullmatch(password):
        raise Refused("generated-password-outside-its-form")
    return f"'{password}'"


def _role(name: str, clause: str, password: str | None = None) -> str:
    created = f"CREATE ROLE {name} {clause}" + (
        "" if password is None else f" PASSWORD {_literal(password)}")
    return (f"DO $$BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='{name}') THEN "
            f"{created}; ELSE ALTER ROLE {name} {clause}; END IF; END$$;")


def _create_database(name: str, owner: str | None = None) -> str:
    owned = f" OWNER {owner}" if owner else ""
    return (f"SELECT 'CREATE DATABASE {name}{owned} ENCODING ''UTF8'' LOCALE ''C'' TEMPLATE "
            f"template1' WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname='{name}')"
            " \\gexec")


def installation_script(source: Path, *, run_id: str, passwords: Mapping) -> str:
    """The psql script the installer runs as the database account over its socket, as
    the superuser (no password; only that account, only the socket): every role with
    its limits and memberships, `template1`'s extension, `docsuri_v2` with its base
    (each owner's schema, as the composed realm's base install makes it), the template
    `docsuri_v2_template` with the same base, and `docsuri_v2_platform` with U7's
    schema, U8's amendment and the protocol rows. It is idempotent: an existing role
    keeps its password, an existing database its content. It holds the generated
    passwords, so it goes only to psql's standard input."""
    if not re.fullmatch(r"docsuri-v2-[0-9a-f]{16}", run_id):
        raise Refused("run-id-outside-its-form")
    roles = DATABASE_ROLES
    database, platform = PRODUCTION_DATABASES.production, PRODUCTION_DATABASES.platform
    owners = passwords["owners"]
    lines = ["\\set ON_ERROR_STOP on", "\\connect postgres",
             _role(roles.disposable, "NOLOGIN NOSUPERUSER CREATEDB NOCREATEROLE NOINHERIT "
                   "NOBYPASSRLS")]
    for owner in OWNERS:
        lines.append(_role(f"docsuri_{owner}_owner",
                           "NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS"))
        lines.append(_role(f"docsuri_{owner}", "LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE "
                           f"NOINHERIT NOBYPASSRLS CONNECTION LIMIT {OWNER_CONNECTION_LIMIT}",
                           owners[owner]))
    lines += [
        _role(roles.scheduler, "LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE INHERIT NOBYPASSRLS "
              "CONNECTION LIMIT 3", passwords["scheduler"]),
        _role(roles.backup_agent, "LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE INHERIT "
              "NOBYPASSRLS CONNECTION LIMIT 3", passwords["backupAgent"]),
        _role(roles.operator, "LOGIN NOSUPERUSER CREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS "
              "CONNECTION LIMIT 2", passwords["operator"]),
        _role(roles.restore, "LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE INHERIT NOBYPASSRLS "
              "CONNECTION LIMIT 3", passwords["restore"]),
        f"GRANT {roles.disposable} TO {roles.scheduler} WITH INHERIT TRUE, SET FALSE;",
        f"GRANT {roles.disposable} TO {roles.backup_agent} WITH INHERIT FALSE, SET TRUE;",
        # SET as well, so the production environment tool creates the migration's
        # rehearsal and import databases as the disposable role, which then owns them
        # (the person's decision of 2026-10-24); the login already holds CREATEDB and
        # inherits the role's privileges, so this adds no power to create or drop.
        f"GRANT {roles.disposable} TO {roles.operator} WITH INHERIT TRUE, SET TRUE;",
        f"GRANT pg_read_all_data TO {roles.backup_agent} WITH INHERIT TRUE, SET FALSE;",
        f"GRANT pg_monitor TO {roles.operations};",
        "GRANT EXECUTE ON FUNCTION pg_catalog.pg_ls_waldir() TO docsuri_operations_owner;",
    ]
    for owner in OWNERS:
        lines.append(f"GRANT docsuri_{owner}_owner TO {roles.restore};")
        lines.append(f"GRANT docsuri_{owner}_owner TO {roles.operator} WITH INHERIT FALSE, "
                     "SET TRUE;")
    lines += ["\\connect template1", "CREATE EXTENSION IF NOT EXISTS vector;"]
    lines += _base_lines(source, database, run_id=run_id, fresh="fresh")
    # The template the migration copies (the person's decision of 2026-10-24): the same
    # base, kept on the same chain by `migrate`, and marked a template so the disposable
    # role may copy it without owning it.
    template = PRODUCTION_DATABASES.template
    lines += _base_lines(source, template, run_id=run_id, fresh="fresh_template")
    lines += ["\\connect postgres", f"ALTER DATABASE {template} WITH IS_TEMPLATE true;"]
    lines += _platform_lines(source, run_id=run_id, passwords=passwords["platform"],
                             platform=platform)
    return "\n".join(lines) + "\n"


def _base_lines(source: Path, database: str, *, run_id: str, fresh: str) -> list[str]:
    """One database of the run with its base: each owner's schema as the composed
    realm's base install makes it, the identity row, the owners' and the operator
    tool's grants. Idempotent: a database with an identity row is left as it is."""
    from backend.u8_migrations import BASE

    roles = DATABASE_ROLES
    lines = ["\\connect postgres", _create_database(database, roles.operator),
             f"\\connect {database}", "CREATE EXTENSION IF NOT EXISTS vector;",
             f"SELECT to_regclass('public.docsuri_local_identity') IS NULL AS {fresh} \\gset",
             f"\\if :{fresh}"]
    hashes = {owner: _digest(source / file) for owner, file in BASE}
    lines += [f"REVOKE ALL ON DATABASE {database} FROM PUBLIC;",
              "REVOKE ALL ON SCHEMA public FROM PUBLIC;",
              "CREATE TABLE public.docsuri_local_identity (singleton boolean PRIMARY KEY "
              "CHECK(singleton),run_id text NOT NULL,schema_hashes jsonb NOT NULL);",
              "INSERT INTO public.docsuri_local_identity VALUES(true,'"
              f"{run_id}','{json.dumps(hashes, sort_keys=True)}');"]
    schemas = dict(BASE)
    for owner in OWNERS:
        lines += [f"GRANT CONNECT ON DATABASE {database} TO docsuri_{owner};",
                  f"GRANT USAGE ON SCHEMA public TO docsuri_{owner}_owner;",
                  f"CREATE SCHEMA {owner} AUTHORIZATION docsuri_{owner}_owner;",
                  f"SET ROLE docsuri_{owner}_owner;",
                  f"ALTER DEFAULT PRIVILEGES IN SCHEMA {owner} REVOKE EXECUTE ON FUNCTIONS "
                  "FROM PUBLIC;"]
        if owner in schemas:
            lines += [f"\\i {source / schemas[owner]}",
                      f"CREATE TABLE {owner}.receipt (account_id uuid NOT NULL,kind text NOT "
                      "NULL,key uuid NOT NULL,intent_hash text NOT NULL CHECK(intent_hash ~ "
                      "'^[0-9a-f]{64}$'),outcome jsonb NOT NULL,created_at timestamptz NOT NULL "
                      "DEFAULT clock_timestamp(),PRIMARY KEY(account_id,kind,key));",
                      f"GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA {owner} TO "
                      f"docsuri_{owner};",
                      f"REVOKE UPDATE,DELETE ON {owner}.receipt FROM docsuri_{owner};",
                      f"GRANT USAGE,SELECT ON ALL SEQUENCES IN SCHEMA {owner} TO docsuri_{owner};",
                      f"GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA {owner} TO docsuri_{owner};"]
        lines += [f"GRANT USAGE ON SCHEMA {owner} TO docsuri_{owner};", "RESET ROLE;",
                  f"GRANT USAGE ON SCHEMA public TO docsuri_{owner};",
                  f"GRANT SELECT ON public.docsuri_local_identity TO docsuri_{owner};"]
    for owner in SESSION_GUARD_LOGINS:
        lines += [f"GRANT USAGE ON SCHEMA accounts TO docsuri_{owner};",
                  "GRANT EXECUTE ON FUNCTION accounts.guard_session(uuid,uuid,text) TO "
                  f"docsuri_{owner};"]
    for owner in CORPUS_GUARD_LOGINS:
        lines += [f"GRANT USAGE ON SCHEMA corpus TO docsuri_{owner};",
                  f"GRANT EXECUTE ON FUNCTION corpus.guard_version(text,text) TO docsuri_{owner};"]
    lines += ["GRANT EXECUTE ON FUNCTION accounts.guard_execution(uuid,uuid) TO "
              "docsuri_assistance;",
              "GRANT SELECT ON corpus.paper,corpus.version,corpus.projection TO docsuri_discovery;",
              "\\endif"]
    for role in (roles.restore, roles.operator, roles.backup_agent, "docsuri_operations_owner"):
        lines.append(f"GRANT CONNECT ON DATABASE {database} TO {role};")
    lines.append(f"GRANT SELECT,UPDATE ON public.docsuri_local_identity TO {roles.operator};")
    # A function's grants live in each database's own catalog: the capacity observation
    # (`pg_ls_waldir`, which `migrate` checks on each database of the run) is granted
    # here too, not only in `postgres` (U8 plan Step 98(d)'s instance found it missing).
    lines.append("GRANT EXECUTE ON FUNCTION pg_catalog.pg_ls_waldir() TO "
                 "docsuri_operations_owner;")
    return lines


def reader_role_lines() -> list[str]:
    """The reader login's memberships: out of the runtime role, into the reader role
    (your decision of 2026-10-26, "Bind each login to its actor"). Part of the
    installation script, and run again by the installer on an existing install whose
    reader still holds the runtime role (review findings, Minor, R16 and R17)."""
    from docsuri_ops.platform_control import RUNTIME_ROLE
    from docsuri_ops.u8_platform.platform_profile import READER_ROLE

    login = PLATFORM_LOGINS["reader"]
    return [f"REVOKE {RUNTIME_ROLE} FROM {login};",
            f"GRANT {READER_ROLE} TO {login} WITH INHERIT TRUE, SET FALSE;"]


def reader_role_script() -> str:
    """`reader_role_lines` as a psql script of its own, run over the socket as the
    database account (the installer's `run_script`)."""
    return "\n".join(["\\set ON_ERROR_STOP on", "\\connect postgres", *reader_role_lines()]) + "\n"


def _platform_lines(source: Path, *, run_id: str, passwords: Mapping, platform: str) -> list[str]:
    from docsuri_ops.platform_control import OWNER_ROLE, RUNTIME_ROLE
    from docsuri_ops.u8_platform.platform_profile import (
        READER_ROLE,
        STORE_AMENDMENT,
        store_digest,
    )

    lines = ["\\connect postgres", _create_database(platform),
             _role(OWNER_ROLE, "NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT "
                   "NOBYPASSRLS"),
             _role(RUNTIME_ROLE, "NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT "
                   "NOBYPASSRLS"),
             # The reader role holds only the read functions (your decision of 2026-10-26,
             # "Bind each login to its actor"); the amendment grants them to it.
             _role(READER_ROLE, "NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT "
                   "NOBYPASSRLS"),
             _role(PLATFORM_PROVISIONER, "LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT "
                   "NOBYPASSRLS CONNECTION LIMIT 2", passwords["provisioner"])]
    for key, login in PLATFORM_LOGINS.items():
        lines.append(_role(login, "LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE INHERIT "
                           "NOBYPASSRLS CONNECTION LIMIT 2", passwords[key]))
        if key == "reader":
            # The reader login is no member of the runtime role: the read functions only.
            lines += reader_role_lines()
        else:
            lines.append(f"GRANT {RUNTIME_ROLE} TO {login} WITH INHERIT TRUE, SET FALSE;")
    lines += [f"GRANT {OWNER_ROLE} TO {DATABASE_ROLES.operator} WITH INHERIT FALSE, SET TRUE;",
              f"\\connect {platform}",
              f"SELECT to_regclass('{PLATFORM_IDENTITY}') IS NULL AS fresh_platform \\gset",
              "\\if :fresh_platform",
              f"REVOKE ALL ON DATABASE {platform} FROM PUBLIC;",
              "REVOKE ALL ON SCHEMA public FROM PUBLIC;",
              f"CREATE TABLE {PLATFORM_IDENTITY} (singleton boolean PRIMARY KEY CHECK(singleton), "
              "run_id text NOT NULL, inventory_hash text NOT NULL);",
              f"CREATE SCHEMA platform_control AUTHORIZATION {OWNER_ROLE};",
              f"SET ROLE {OWNER_ROLE};",
              f"\\i {source / 'ops/src/docsuri_ops/platform_control/schema.sql'}",
              f"\\i {source / STORE_AMENDMENT}"]
    for row in protocol_rows(source):
        values = ",".join("true" if item is True else "false" if item is False
                          else str(item) if isinstance(item, int)
                          else "'" + str(item).replace("'", "''") + "'" for item in row)
        lines.append(f"INSERT INTO platform_control.protocol ({', '.join(PROTOCOL_COLUMNS)}) "
                     f"VALUES ({values});")
    lines += ["RESET ROLE;",
              # The store's digest (the inventory and the amendment), so the next
              # `migrate` verifies a store just installed.
              f"INSERT INTO {PLATFORM_IDENTITY} VALUES (true,'{run_id}','{store_digest(source)}');",
              "\\endif"]
    for role in (OWNER_ROLE, RUNTIME_ROLE, READER_ROLE, PLATFORM_PROVISIONER,
                 *PLATFORM_LOGINS.values(), DATABASE_ROLES.operator):
        lines.append(f"GRANT CONNECT ON DATABASE {platform} TO {role};")
    # The identity row sits in `public`, whose PUBLIC grants the fresh store revoked: the
    # operator tool's `migrate` reads and updates it (U8 plan Step 98(d)'s instance found
    # the schema closed to it).
    lines.append(f"GRANT USAGE ON SCHEMA public TO {DATABASE_ROLES.operator};")
    lines.append(f"GRANT SELECT,UPDATE ON {PLATFORM_IDENTITY} TO {DATABASE_ROLES.operator};")
    return lines


# --- the program's shape (D6) --------------------------------------------------------------


def _emit(stream: BinaryIO, value: dict, status: int) -> int:
    stream.write(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
                 + b"\n")
    stream.flush()
    return status


def _bounded(stdin: BinaryIO) -> dict:
    raw = stdin.read(MAX_INPUT + 1)
    if len(raw) > MAX_INPUT:
        raise Refused("input-too-large")
    try:
        value = json.loads(raw or b"{}")
    except ValueError:
        raise Refused("input-not-json") from None
    if not isinstance(value, dict):
        raise Refused("input-not-an-object")
    return value


def dispatch(word: str, stdin: BinaryIO, context: ToolContext) -> dict:
    if word == "restore-database":
        return restore_database(context, stdin)
    if word == "restore-import":
        return restore_import(context, stdin)
    document = _bounded(stdin)
    if word == "create-disposable":
        return create_disposable(context, document)
    if word == "prepare-production":
        return prepare_production(context, document)
    if word == "migrate":
        return migrate(context, document)
    if word == "restore-evaluate":
        return restore_evaluate(context, document)
    if word == "recreate-database":
        return recreate_database(context, document)
    if word == "remove-database":
        return remove_database(context, document)
    if word == "replace-verifier-key":
        return replace_verifier_key(context, document)
    if word == "readiness-evidence":
        return readiness_evidence(context, document)
    if word == "control-key-recovery":
        return control_key_recovery(context, document)
    if word == "control-key-start":
        return control_key_start(context, document)
    if word == "replace-cursor-key":
        return replace_cursor_key(context, document)
    if word == "export-settings":
        return export_settings(context, document)
    if word == "provider-environment":
        return provider_environment(context, document)
    if word == "research-review":
        return research_review(context, document)
    if word == "latency-summaries":
        return latency_summaries(context, document)
    if word in ("provider-previews", "provider-decision", "provider-failed"):
        return provider_activation_word(context, word, document)
    return export_key(context, word, document)


def run(argv: list[str], context: ToolContext, *, environ: Mapping[str, str],
        stdin: BinaryIO, stdout: BinaryIO, uid: int | None = None) -> int:
    from backend.u8_profile import ProfileRefused

    if any(name.startswith(REFUSED_ENVIRONMENT) for name in environ):
        return _emit(stdout, {"ok": False, "reason": "environment-refused"}, 2)
    if len(argv) != 1 or argv[0] not in WORDS:
        return _emit(stdout, {"ok": False, "reason": "word-refused"}, 2)
    if (os.getuid() if uid is None else uid) != context.service_uid:
        return _emit(stdout, {"ok": False, "reason": "service-account-only"}, 2)
    word = argv[0]
    try:
        result = dispatch(word, stdin, context)
    except Refused as refused:
        _log_word(context, word, "refused")
        return _emit(stdout, {"ok": False, "reason": refused.reason, **refused.facts}, 1)
    except ProfileRefused as refused:
        _log_word(context, word, "refused")
        return _emit(stdout, {"ok": False, "reason": f"profile-{refused.check}"}, 1)
    except Exception as error:  # noqa: BLE001 - one JSON result, no detail or traceback
        _log_word(context, word, "failed")
        return _emit(stdout, {"ok": False, "reason": "word-failed",
                              "error": type(error).__name__}, 1)
    _log_word(context, word, "done")
    return _emit(stdout, {"ok": True, "word": word, "consequence": CONSEQUENCES[word],
                          "result": result}, 0)


def _log_word(context: ToolContext, word: str, outcome: str) -> None:
    """The installation log names each word and its outcome, never a value (your
    decision of 2026-10-24); a log that cannot be written never changes the result."""
    from docsuri_ops.arrangement.checklist import InstallationLog

    if not context.paths.installation_log.parent.is_dir():
        return  # the profile's evidence folder is the installer's to make
    try:
        InstallationLog(context.paths.installation_log, clock=context.clock,
                        base=context.paths.prefix).write(
            "production-tool", word, outcome)
    except (OSError, ValueError):
        pass


def main_fixed(argv: list[str] | None = None) -> int:
    return run(sys.argv[1:] if argv is None else argv, ToolContext(), environ=os.environ,
               stdin=sys.stdin.buffer, stdout=sys.stdout.buffer)


# --- the operator tool's side ---------------------------------------------------------------

PROGRAM = "/Library/DocSuri/release/ops/bin/docsuri-production-tool"


def invoke(word: str, document: dict, *, login: str | None = None, run=None, release=None,
           payload: bytes | None = None, program: str = PROGRAM) -> dict:
    """Run one word in person: `sudo -k -u _docsuri_v2 docsuri-production-tool <word>`,
    with the login released in person first (D5) and handed on through standard input
    only. `payload` follows the JSON header line (`restore-database`'s archive)."""
    import subprocess

    from docsuri_ops.u8_platform.credential_release import release as release_login

    if word not in WORDS:
        raise Refused("word-refused")
    document = dict(document)
    secret = None
    if login is not None:
        secret = (release or release_login)(login)
        document["login"] = {"password": secret.decode()}
    try:
        header = json.dumps(document).encode()
        body = header + (b"\n" + payload if payload is not None else b"")
        argv = ["/usr/bin/sudo", "-k", "-u", Accounts.standard().service.name, program, word]
        completed = (run or subprocess.run)(argv, input=body, capture_output=True,
                                            timeout=RESTORE_SECONDS + 600, check=False)
    finally:
        document.pop("login", None)
        if secret is not None:
            secret[:] = b"\0" * len(secret)
    try:
        result = json.loads(completed.stdout.decode().splitlines()[-1])
    except (ValueError, IndexError):
        raise Refused("tool-answered-no-result") from None
    if completed.returncode != 0 or not result.get("ok"):
        raise Refused(str(result.get("reason", "word-failed")))
    return result


__all__ = ["WORDS", "ToolContext", "Refused", "run", "main_fixed", "invoke", "protocol_rows",
           "pending_migrations"]
