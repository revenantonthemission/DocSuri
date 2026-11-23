"""The complete assembly's host for the route tests (U8 plan Step 40).

`complete_host` composes the realm, builds `host_app` with every owner's routes behind D7's
boundary, refreshes the host's capacity admission once (as its refresher does), and
yields an in-process client at the public stand-in's authority. Sign-ins go through the
mounted routes: a member with the password, an administrator with the password and a
second factor (U2's enrolment, completed through the accounts owner's login).
"""

from __future__ import annotations

import asyncio
import contextlib
import datetime as dt
import json
import os
import secrets
import shutil
import threading
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient

from backend.local_browser import SESSION_COOKIE
from backend.modules.accounts.local_http import ENTRY_POLICY
from backend.modules.accounts.services.control_mfa import totp
from backend.u8_host import compose, host_app
from tests.u8_service_operations_integration.conftest import (
    SIGN_IN_PASSWORD,
    activate_factor,
    database_step,
    post,
)

ORIGIN = "https://127.0.0.1:18110"


@contextlib.contextmanager
def complete_host(realm, *, address: str | None = None, prepare=None):
    composition = compose(realm)
    try:
        if prepare is not None:
            prepare(composition)
        app = host_app(composition)
        app.state.control_capacity.refresh()
        headers = {"cf-connecting-ip": address} if address else {}
        with TestClient(app, base_url=ORIGIN, headers=headers, follow_redirects=False) as client:
            yield SimpleNamespace(composition=composition, app=app, client=client)
    finally:
        composition.close()


def fresh_client(host, address: str | None = None) -> TestClient:
    """Another browser on the same host: its own cookies."""
    headers = {"cf-connecting-ip": address} if address else {}
    return TestClient(host.app, base_url=ORIGIN, headers=headers, follow_redirects=False)


def csrf(client) -> str:
    return client.get("/api/v2/session").json()["csrfToken"]


def call(client, path: str, body: dict):
    return post(client, path, body, csrf(client))


def sign_in(client, email: str):
    return call(client, "/api/v2/c02/access-login",
                {"email": email, "password": SIGN_IN_PASSWORD, "policyRef": ENTRY_POLICY})


# The realm holds at most 20 synthetic accounts, so these tests reuse the suffixes the
# other route tests use; `sign_in_account` resets an account at each call.
MEMBER, OTHER_MEMBER, ADMINISTRATOR = "sign-in-member", "sign-in-migrated", "sign-in-admin"


def member(host, sign_in_account, suffix: str = MEMBER):
    """A signed-in member of the complete host; returns its authority and email."""
    authority, email = sign_in_account(suffix)
    answer = sign_in(host.client, email)
    assert answer.status_code == 200 and answer.json()["state"] == "authenticated", answer.text
    return authority, email


def administrator(host, sign_in_account, connect, suffix: str = ADMINISTRATOR):
    """A signed-in administrator whose second factor is current."""
    entry = host.composition.parts["account-controls"]["entry"]
    authority, email = sign_in_account(suffix, role="administrator")
    seed = activate_factor(connect, entry, authority.account_id)
    challenged = sign_in(host.client, email)
    assert challenged.json()["state"] == "mfa_required", challenged.text
    challenge = challenged.json().get("mfaChallenge", challenged.json())
    verified = call(host.client, "/api/v2/c02/access-verify-mfa", {
        "factorKind": "totp",
        "verification": {"challengeId": challenge["challengeId"],
                         "flowBinding": challenge["flowBinding"],
                         "proof": totp(seed, database_step(connect))},
    })
    assert verified.status_code == 200, verified.text
    assert host.client.cookies.get(SESSION_COOKIE)
    return authority, email


def lapse_second_factor(connect, authority_id) -> None:
    """The administrator's second factor older than the guard's bound."""
    with connect("accounts") as conn:
        conn.execute(
            "UPDATE accounts.session SET mfa_at=clock_timestamp()-interval '10 minutes' "
            "WHERE account_id=%s AND NOT revoked AND mfa_at IS NOT NULL", (authority_id,))


def make_jobs(connect, account_id, session_id, kinds, *, title="합성 연구 세션"):
    """Jobs written as ResearchWorkspace's own login, newest last; their accepted times
    are later than anything an earlier run left. Returns them newest first."""
    from backend.u4_policy import SYNTHETIC_RESEARCH

    base = dt.datetime.now(dt.UTC) + dt.timedelta(seconds=5)
    context, session = uuid4(), uuid4()
    # The session's scope in the shape U4 stores (ResearchScope), so the account's later
    # session reads can present it (the batch-7 review: '{}' made list-research-sessions
    # answer 500 for the shared account).
    scope = {"contextId": str(context), "publicPapers": [], "attachmentIds": [],
             "webReferences": [], "scopePolicy": SYNTHETIC_RESEARCH.reference()}
    jobs = []
    with connect("research") as conn:
        conn.execute("INSERT INTO research.context(id,owner_id,purpose) VALUES(%s,%s,'research')",
                     (context, account_id))
        conn.execute(
            "INSERT INTO research.session(id,owner_id,context_id,title,scope) "
            "VALUES(%s,%s,%s,%s,%s::jsonb)",
            (session, account_id, context, title, json.dumps(scope)),
        )
        for index, kind in enumerate(kinds):
            job, accepted = uuid4(), base + dt.timedelta(milliseconds=10 * index)
            conn.execute(
                "INSERT INTO research.job(id,owner_id,context_id,session_id,authority_session,"
                "kind,operation_key,input_hash,input,scope,policy,accepted_at,updated_at,"
                "usage_id) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,'{}','{}','{}',%s,%s,%s)",
                (job, account_id, context, session if kind == "research-turn" else None,
                 session_id, kind, str(uuid4()), secrets.token_hex(32), accepted, accepted,
                 uuid4()),
            )
            jobs.append(job)
    return list(reversed(jobs))


def owner_runs(composition) -> dict:
    """Every owner pool's connection requests so far, `{(lane, owner): n}`, read from
    psycopg_pool's own statistics on the composition's `CompleteTransactions` (Step
    87(b), L1-8): a run takes one pool request, so a difference is a run count. Never a
    wrapper (L1-35)."""
    transactions = composition.transactions
    counts = {}
    for lane, pools in (("normal", transactions._pools),
                        ("recovery", transactions._recovery_pools)):
        for owner, pool in dict.items(pools):
            counts[(lane, owner)] = pool.get_stats().get("requests_num", 0)
    return counts


def counted_post(host, path: str, body: dict):
    """The POST's answer and its owner runs, `{(lane, owner): n}` with only the owners
    it ran. The CSRF token is read first: `GET /api/v2/session` is itself an accounts
    run."""
    assert host.app.state.transactions is host.composition.transactions
    token = csrf(host.client)
    before = owner_runs(host.composition)
    answer = post(host.client, path, body, token)
    after = owner_runs(host.composition)
    return answer, {key: after[key] - before[key] for key in after
                    if after[key] != before[key]}


def by_owner(runs: dict) -> dict:
    """Runs per owner, both lanes together."""
    totals: dict = {}
    for (_, owner), count in runs.items():
        totals[owner] = totals.get(owner, 0) + count
    return totals


def assert_bounded_runs(composition, owners, *, recovery: bool = False) -> None:
    """One action through `composition.transactions.run` for each owner, in the normal
    lane or, with `recovery`, with `RECOVERY_REQUEST` set as a recovery route sets it:
    inside it the transaction is serializable, the connection is a `DeadlineConnection`
    with a 3 s statement bound, and 0 < remaining <= 5 s (Step 52(a)'s bounds)."""
    from backend.control_runtime import RECOVERY_REQUEST
    from backend.transactions import DeadlineConnection

    def probe(conn):
        isolation = conn.execute("SHOW transaction_isolation").fetchone()
        return (isolation["transaction_isolation"], isinstance(conn, DeadlineConnection),
                getattr(conn, "statement_ms", None), conn.remaining())

    lane = "recovery" if recovery else "normal"
    token = RECOVERY_REQUEST.set(recovery)
    try:
        for owner in owners:
            before = owner_runs(composition)
            isolation, deadline, statement_ms, remaining = composition.transactions.run(
                owner, probe)
            after = owner_runs(composition)
            assert isolation == "serializable", owner
            assert deadline and statement_ms == 3000, owner
            assert 0 < remaining <= 5.0, (owner, remaining)
            assert after[(lane, owner)] - before[(lane, owner)] == 1, owner
    finally:
        RECOVERY_REQUEST.reset(token)


def session_of(connect, account_id):
    with connect("accounts") as conn:
        return conn.execute(
            "SELECT id FROM accounts.session WHERE account_id=%s AND NOT revoked "
            "AND purpose='full_session' ORDER BY expires_at DESC LIMIT 1", (account_id,),
        ).fetchone()["id"]


# --- The production stand-in (U8 plan Step 12; your decision of 2026-10-24) ---------------
#
# Steps 22, 24 and 40 run production's own code on a production profile: its own
# rehearsal copy of the composed schema in the realm's instance, a profile under the
# tests' marked folder in `~/.cache/docsuri-u8-tests/` (the loader refuses `/tmp`), and the
# real builders. The folder holds only the test's own logins and keys and is removed
# afterwards; nothing else in the login account is touched.

TEST_ROOTS = Path.home() / ".cache" / "docsuri-u8-tests"
ROOT_MARK = ".docsuri-u8-test-root"
MARK_TEXT = b"docsuri-u8 test root: test logins and keys only; removed after each run\n"
_SWEPT: list[bool] = []
ACCOUNT_NAMES = {"service": "_docsuri_v2", "scheduler": "_docsuri_v2_sched",
                 "backup": "_docsuri_r1t_backup", "database": "_docsuri_v2_db",
                 "models": "_docsuri_models", "tunnel": "_docsuri_tunnel"}


def _marked(folder: Path) -> bool:
    mark = folder / ROOT_MARK
    return (folder.is_dir() and not folder.is_symlink() and mark.is_file()
            and not mark.is_symlink() and mark.read_bytes() == MARK_TEXT)


def remove_leftover_roots() -> list[str]:
    """The marked folders an interrupted run left, removed; anything unmarked is kept."""
    removed = []
    if TEST_ROOTS.is_dir() and not TEST_ROOTS.is_symlink():
        for child in sorted(TEST_ROOTS.iterdir()):
            if _marked(child):
                shutil.rmtree(child)
                removed.append(child.name)
    return removed


@contextlib.contextmanager
def production_root():
    """One marked folder of the tests' own, removed afterwards in any case; the first use
    in a session removes the marked folders an interrupted run left."""
    TEST_ROOTS.mkdir(mode=0o700, parents=True, exist_ok=True)
    if not _SWEPT:
        remove_leftover_roots()
        _SWEPT.append(True)
    folder = TEST_ROOTS / str(uuid4())
    folder.mkdir(mode=0o700)
    (folder / ROOT_MARK).write_bytes(MARK_TEXT)
    try:
        yield folder
    finally:
        if _marked(folder):
            shutil.rmtree(folder, ignore_errors=True)


def write_private(path: Path, payload: bytes) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(payload)


def write_readiness(profile, purposes: dict[str, str] | None, *,
                    recorded: dt.datetime | None = None) -> None:
    """The readiness marker, as the production tool's `readiness-evidence` word writes it;
    None removes it."""
    from docsuri_ops.local_models import MODEL_PINS

    folder = profile.root / "evidence"
    folder.mkdir(mode=0o700, exist_ok=True)
    marker = folder / "model-readiness.json"
    marker.unlink(missing_ok=True)
    if purposes is not None:
        write_private(marker, json.dumps({
            "models": dict(MODEL_PINS), "purposes": purposes,
            "recordedAt": (recorded or dt.datetime.now(dt.UTC)).isoformat(),
        }).encode())


@dataclass
class ProductionStandIn:
    realm: object
    database: str
    run_id: str
    profile: object
    transactions: object
    roles: dict
    # With `release=True` (Step 12's release, your decision of 2026-10-24): the
    # arrangement under the marked folder's prefix and the release folder `release`
    # points to, holding a copy of the source tree and its identity file.
    arrangement: object = None
    release_root: Path | None = None
    # With `maintainer=True`: the imported maintainer's account, verified, with an address.
    maintainer: object = None

    def connect(self, owner: str, *, autocommit: bool = False):
        """A raw login as `docsuri_<owner>` on the stand-in's own database."""
        import psycopg
        from psycopg.rows import dict_row

        return psycopg.connect(host="127.0.0.1", port=self.realm.database_port,
                               dbname=self.database, user=f"docsuri_{owner}",
                               password=self.roles[owner], connect_timeout=3,
                               row_factory=dict_row, autocommit=autocommit)

    def admin(self):
        from docsuri_ops.migration.realm import RealmDatabases

        return RealmDatabases.for_realm(self.realm.root).admin(self.database)

    def context(self, *, parts: dict | None = None, clock=None):
        """A production `BuildContext` over the stand-in, for the real builders."""
        from backend.u8_host import BuildContext

        return BuildContext(self.profile, self.transactions,
                            clock or (lambda: dt.datetime.now(dt.UTC)), dict(parts or {}))


def installer_manifest(run_id: str, maintainer) -> dict:
    """The installer's own first manifest (`arrangement.installer.profile_manifest`), made
    with fake tools."""
    from docsuri_ops.arrangement.installer import profile_manifest

    ctx = SimpleNamespace(
        tools=SimpleNamespace(volume=lambda name: {"identifier": str(uuid4()).upper()}),
        run_id=run_id, maintainer_account=str(maintainer),
        accounts=SimpleNamespace(**{role: SimpleNamespace(name=name)
                                    for role, name in ACCOUNT_NAMES.items()}),
        clock=lambda: dt.datetime.now(dt.UTC),
    )
    return profile_manifest(ctx)


def _profile_manifest(run_id: str, database: str, maintainer, *, mode: str = "rehearsal"
                      ) -> dict:
    """The installer's own manifest, then naming the stand-in's rehearsal copy, as the
    profile words do; in live mode the database is `docsuri_v2`, which the stand-in then
    points at its own copy."""
    value = installer_manifest(run_id, maintainer)
    value.update(database=database, rehearsalDatabase=database)
    if mode == "live":
        value.update(mode="live", database="docsuri_v2")
    return value


RELEASE_TAG = "v2.0.0"
SOURCE = Path(__file__).resolve().parents[2]


def source_files() -> list[str]:
    """The source tree a release holds: every file of `backend/`, `ops/` and `shared/`
    that git tracks or would track (the working tree is the release here)."""
    import subprocess

    listed = subprocess.run(
        ["git", "-C", str(SOURCE), "ls-files", "--cached", "--others", "--exclude-standard",
         "-z", "backend", "ops", "shared"], capture_output=True, check=True, timeout=60)
    return [name for name in listed.stdout.decode().split("\0") if name]


def production_release(folder: Path):
    """The arrangement under `folder/prefix` (`ArrangementPaths.under`) and its release:
    `releases/v2.0.0` holding a copy of the source tree and the release identity file,
    reached through the `release` link; each folder this user's and written by nobody
    else, as `check_release` requires of a test arrangement."""
    import subprocess

    from docsuri_ops.arrangement.paths import ArrangementPaths
    from docsuri_ops.release import write_identity

    arrangement = ArrangementPaths.under(folder / "prefix")
    release = arrangement.releases / RELEASE_TAG
    release.mkdir(parents=True)
    for path in (arrangement.prefix, arrangement.releases, release):
        os.chmod(path, 0o755)
    for name in source_files():
        source = SOURCE / name
        if source.is_symlink() or not source.is_file():
            continue
        target = release / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    commit = subprocess.run(["git", "-C", str(SOURCE), "rev-parse", "HEAD"],
                            capture_output=True, check=True, timeout=30).stdout.decode().strip()
    write_identity(release, RELEASE_TAG, commit, owner_uid=os.getuid())
    os.symlink(release, arrangement.release)
    return arrangement, release


def _insert_maintainer(realm, database: str, roles: dict):
    """The imported maintainer's account on the stand-in's own copy: verified and active,
    with an address, as the migration carries it."""
    import psycopg

    account = uuid4()
    with psycopg.connect(host="127.0.0.1", port=realm.database_port, dbname=database,
                         user="docsuri_accounts", password=roles["accounts"],
                         connect_timeout=3) as conn:
        conn.execute(
            "INSERT INTO accounts.account(id,email,password_hash,verified,active,"
            "authority_revision,display_name) VALUES(%s,%s,'not-login-material',true,true,%s,"
            "'maintainer')", (account, f"maintainer-{account}@fixture.example.com", uuid4()))
    return account


@contextlib.contextmanager
def production_stand_in(realm, *, maintainer=None, mode: str = "rehearsal",
                        release: bool = False, environment: dict | None = None):
    """Production's profile and its own rehearsal database in the realm's instance:
    `docsuri_v2_rehearsal_<12 hex>` with the realm's connection grants, the composed
    template copied into it (`RealmDatabases.copy_composed_schema`), its identity row
    rebound to a `docsuri-v2-…` run ID; dropped afterwards.

    `maintainer=True` imports a maintainer account (with an address) and names it in the
    profile; `mode="live"` writes a live manifest (`docsuri_v2`) and points the loaded
    profile at the stand-in's copy; `release=True` builds the release folder under the
    marked folder's arrangement prefix; `environment` is written as the profile's
    `private-environment.json`. With accounts present the verifier key is made first, as
    a running production has it."""
    import dataclasses

    from psycopg import sql

    from backend.local_profile import KEY_FOLDERS, private_bytes
    from backend.u8_counts import ProcessCounts
    from backend.u8_host import PROCESS_GATES
    from backend.u8_policy import PRODUCTION_OPERATIONS
    from backend.u8_profile import ProductionProfile
    from backend.u8_transactions import CompleteTransactions
    from docsuri_ops.migration.realm import DISPOSABLE, SOURCE, RealmDatabases

    databases = RealmDatabases.for_realm(realm.root)
    database = "docsuri_v2_rehearsal_" + secrets.token_hex(6)
    run_id = "docsuri-v2-" + secrets.token_hex(8)
    ident = sql.Identifier(database)
    with databases.admin() as conn:
        conn.execute(sql.SQL("CREATE DATABASE {} OWNER {} TEMPLATE template1").format(
            ident, sql.Identifier(DISPOSABLE)))
        conn.execute(sql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC").format(ident))
        for (role,) in conn.execute(
            "SELECT r.rolname FROM pg_database d, aclexplode(d.datacl) a JOIN pg_roles r "
            "ON r.oid=a.grantee WHERE d.datname=%s AND a.privilege_type='CONNECT'",
            (SOURCE,)).fetchall():
            conn.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                ident, sql.Identifier(role)))
    transactions = None
    try:
        databases.copy_composed_schema(database)
        with databases.admin(database) as conn:
            conn.execute("UPDATE public.docsuri_local_identity SET run_id=%s", (run_id,))
        roles = json.loads(private_bytes(realm.root / "owner-credentials.json"))["roles"]
        account = None
        if maintainer is True:
            account = _insert_maintainer(realm, database, roles)
            maintainer = account
        with production_root() as folder:
            root = folder / "profile"
            root.mkdir(mode=0o700)
            for name in (*KEY_FOLDERS, "ledger", "evidence"):
                (root / name).mkdir(mode=0o700)
            write_private(root / "environment.json", json.dumps(
                _profile_manifest(run_id, database, maintainer or uuid4(), mode=mode)
            ).encode())
            write_private(root / "owner-credentials.json",
                          json.dumps({"runId": run_id, "roles": roles}).encode())
            if environment is not None:
                write_private(root / "private-environment.json", json.dumps(environment).encode())
            profile = ProductionProfile.load(root / "environment.json", service_uid=os.getuid())
            profile = dataclasses.replace(profile, database_port=realm.database_port,
                                          database_name=database)
            if account is not None:
                # Both start keys, as a started production with an account holds them
                # (L1-4, Step 72(a)); a stand-in without an account holds neither, and
                # its compose creates both through `start_keys(occupied=False)`.
                from backend.modules.accounts.u8_verifier_key import (
                    ensure_key_file,
                    ensure_verifier_key,
                )
                from backend.u8_host import cursor_key_path

                ensure_verifier_key(profile)
                ensure_key_file(cursor_key_path(profile))
            arrangement = release_root = None
            if release:
                arrangement, release_root = production_release(folder)
            # U8's `CompleteTransactions`, as production's `connect_database` builds it
            # (Step 87(f), L1-6): each request's identifier reaches the owners' column
            # defaults, and its runs count into this stand-in's own `evidence/` folder.
            transactions = CompleteTransactions(
                profile, process=PROCESS_GATES["host"],
                counts=ProcessCounts(root / "evidence", "host", policy=PRODUCTION_OPERATIONS,
                                     clock=lambda: dt.datetime.now(dt.UTC)),
            )
            yield ProductionStandIn(realm, database, run_id, profile, transactions, roles,
                                    arrangement=arrangement, release_root=release_root,
                                    maintainer=account)
    finally:
        if transactions is not None:
            transactions.close()
        with databases.admin() as conn:
            conn.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(ident))


# --- The production-shaped instance (U8 plan Step 98(d), L1-56) ----------------------------
#
# The production environment tool's words act as `docsuri_operator` or `docsuri_restore`
# and need production's grants and databases, which no database of the realm's instance
# holds; the realm's grants are never widened (L1-50). So its tests run on a PostgreSQL
# instance of their own: one container of the realm's own pinned image, under the label key
# below valued with the realm's run ID, on a free port of 127.0.0.1 only, limited to
# 512 MiB with no swap, its data on a tmpfs, and production's own installation script run
# through the container's socket as its superuser, as the installer runs it.

PRODUCTION_INSTANCE_LABEL = "dev.docsuri.u8.production-instance"
PRODUCTION_INSTANCE_MEMORY = 512 * 1024**2
PRODUCTION_INSTANCE_RESERVE = 512 * 1024**2
PRODUCTION_INSTANCE_READY_SECONDS = 60


@dataclass
class ProductionInstance:
    container: str
    port: int
    run_id: str
    passwords: dict
    superuser_password: str
    seconds: dict

    def superuser(self, database: str = "postgres", *, autocommit: bool = True):
        """The instance's superuser over TCP, for a test's own setup and reads."""
        import psycopg

        return psycopg.connect(host="127.0.0.1", port=self.port, dbname=database,
                               user="postgres", password=self.superuser_password,
                               connect_timeout=5, autocommit=autocommit)

    def profile(self, root: Path, *, database: str, maintainer=None):
        """A production profile over the instance, built as `production_stand_in` builds
        its profile: the installer's manifest naming `database`, the owners' logins in
        `owner-credentials.json`, and the instance's port."""
        import dataclasses

        from backend.local_profile import KEY_FOLDERS
        from backend.u8_profile import ProductionProfile

        root.mkdir(mode=0o700, parents=True, exist_ok=True)
        for name in (*KEY_FOLDERS, "ledger", "evidence"):
            (root / name).mkdir(mode=0o700, exist_ok=True)
        if not (root / "environment.json").exists():
            write_private(root / "environment.json", json.dumps(
                _profile_manifest(self.run_id, database, maintainer or uuid4())).encode())
        if not (root / "owner-credentials.json").exists():
            write_private(root / "owner-credentials.json", json.dumps(
                {"runId": self.run_id, "roles": dict(self.passwords["owners"])}).encode())
        profile = ProductionProfile.load(root / "environment.json", service_uid=os.getuid())
        return dataclasses.replace(profile, database_port=self.port, database_name=database)

    def run_script(self, script: str) -> None:
        """`script` on psql's standard input as the instance's superuser, exactly as
        `production_instance` runs the installation script; a non-zero exit raises (its
        output is not repeated, since a script may hold verifiers)."""
        completed = subprocess_input(
            ["docker", "exec", "-i", "-u", "postgres", self.container, "psql", "-X", "-q",
             "-v", "ON_ERROR_STOP=1", "-d", "postgres"], script)
        if completed.returncode != 0:
            raise RuntimeError("the script failed on the production instance")


def _free_port() -> int:
    import socket

    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def _instance_passwords() -> dict:
    """Every installation password, sixty-four hex digits each, generated per run (L1-36),
    as the installer generates them."""
    from docsuri_ops import production_tool

    return {"owners": {owner: secrets.token_hex(32) for owner in production_tool.OWNERS},
            "scheduler": secrets.token_hex(32), "backupAgent": secrets.token_hex(32),
            "operator": secrets.token_hex(32), "restore": secrets.token_hex(32),
            "platform": {name: secrets.token_hex(32) for name in (
                "provisioner", "operator", "scheduler", "reader")}}


@contextlib.contextmanager
def production_instance(realm):
    """The production-shaped instance (module comment above): yields its container, port,
    run ID, the installation's passwords and its start and install seconds; the container
    is removed in `finally`. It fails, never skips, when Docker on Colima has less than the
    instance's 512 MiB plus the 512 MiB recovery reserve available. A run killed at its
    part's bound skips `finally`; the runner then removes the container by its label."""
    import time

    import pytest

    from docsuri_ops import production_tool
    from scripts import verify_docsuri_u8 as runner

    manifest = json.loads((Path(realm.root) / "environment.json").read_bytes())
    image, realm_run = manifest["databaseImage"], manifest["runId"]
    available = runner.docker_available_memory(image)
    required = PRODUCTION_INSTANCE_MEMORY + PRODUCTION_INSTANCE_RESERVE
    if available < required:
        pytest.fail(f"Docker available bytes {available} below the production instance's "
                    f"512 MiB and the 512 MiB recovery reserve ({required})")
    # Realms run one at a time: a container under the key is a killed run's leftover.
    runner.remove_production_instances()
    superuser_password = secrets.token_hex(32)
    run_id = "docsuri-v2-" + secrets.token_hex(8)
    passwords = _instance_passwords()
    container = f"docsuri-u8-production-instance-{secrets.token_hex(6)}"
    started = time.monotonic()
    # A free port of this Mac may still be held inside Colima's VM by an earlier
    # forwarder: another free port is tried, at most three times.
    for _attempt in range(3):
        port = _free_port()
        created = _start_instance(runner, container, realm_run, port, image,
                                  superuser_password)
        if created.returncode == 0 or "address already in use" not in created.stderr:
            break
        runner.command(["docker", "rm", "-f", "-v", container], timeout=60)
    try:
        if created.returncode != 0:
            pytest.fail("the production instance did not start: " + created.stderr[-500:])
        deadline = time.monotonic() + PRODUCTION_INSTANCE_READY_SECONDS
        while runner.command(["docker", "exec", container, "pg_isready", "-q", "-h",
                              "127.0.0.1", "-p", "5432", "-U", "postgres"],
                             timeout=10).returncode != 0:
            if time.monotonic() > deadline:
                pytest.fail("the production instance never became ready")
            time.sleep(0.5)
        start_seconds = time.monotonic() - started
        script = production_tool.installation_script(SOURCE, run_id=run_id, passwords=passwords)
        installing = time.monotonic()
        installed = subprocess_input(
            ["docker", "exec", "-i", "-u", "postgres", container, "psql", "-X", "-q",
             "-v", "ON_ERROR_STOP=1", "-d", "postgres"], script)
        if installed.returncode != 0:
            pytest.fail("the installation script failed: " + installed.stderr[-2000:].decode(
                "utf-8", "replace"))
        seconds = {"start": round(start_seconds, 2),
                   "install": round(time.monotonic() - installing, 2)}
        yield ProductionInstance(container, port, run_id, passwords, superuser_password,
                                 seconds)
    finally:
        runner.command(["docker", "rm", "-f", "-v", container], timeout=60)


def _start_instance(runner, container: str, realm_run: str, port: int, image: str,
                    superuser_password: str):
    return runner.command([
        "docker", "run", "-d", "--name", container,
        "--label", f"{PRODUCTION_INSTANCE_LABEL}={realm_run}",
        "--memory", "512m", "--memory-swap", "512m", "--pids-limit", "128",
        "--read-only",
        "--tmpfs", "/tmp:rw,noexec,nosuid,size=16m",
        "--tmpfs", "/var/run/postgresql:rw,noexec,nosuid,size=16m",
        "--tmpfs", "/var/lib/postgresql/data:rw,size=320m",
        "-p", f"127.0.0.1:{port}:5432",
        "--mount", f"type=bind,src={SOURCE},dst={SOURCE},readonly",
        "-e", "POSTGRES_PASSWORD",
        # The realm container's initdb arguments: UTF8 with the C locale everywhere.
        "-e", ("POSTGRES_INITDB_ARGS=--data-checksums --auth-host=scram-sha-256 "
               "--encoding=UTF8 --locale=C"),
        image,
        # The WAL lives on the tmpfs inside the 512 MiB limit.
        "-c", "max_wal_size=128MB", "-c", "min_wal_size=32MB",
    ], timeout=60, extra={"POSTGRES_PASSWORD": superuser_password})


def subprocess_input(argv: list[str], text: str):
    """`argv` with `text` on its standard input only (the installation script holds the
    generated passwords), under the Docker endpoint the runner passes on."""
    import subprocess

    from scripts import verify_docsuri_u8 as runner

    environment = runner.child_environment(None)
    return subprocess.run(argv, input=text.encode(), capture_output=True, timeout=240,
                          check=False, env=environment)


class ModelStandIn:
    """The shared model runtime, never called: `/api/tags` answers the chosen digests,
    `/api/embed` deterministic vectors, `/api/chat` whatever `chat` returns; every request
    is kept. `factory` is the transport the client builds."""

    def __init__(self, *, digests: dict | None = None, chat=None):
        from docsuri_ops.local_models import MODEL_PINS

        self.digests = dict(MODEL_PINS if digests is None else digests)
        self.chat = chat
        self.requests: list = []
        # `fail` is raised for every model request, `down` for `/api/tags` too (the
        # runtime not answering at all).
        self.fail: Exception | None = None
        self.down: Exception | None = None

    def handle(self, request):
        import httpx

        self.requests.append(request)
        path = request.url.path
        if self.down is not None:
            raise self.down
        if path == "/api/tags":
            return httpx.Response(200, json={"models": [
                {"name": name, "digest": digest} for name, digest in self.digests.items()]})
        if self.fail is not None:
            raise self.fail
        body = json.loads(request.content)
        if path == "/api/embed":
            vectors = [[1.0] + [0.0] * 1023 for _ in body["input"]]
            return httpx.Response(200, json={"model": body["model"], "embeddings": vectors})
        if path == "/api/chat" and self.chat is not None:
            return self.chat(body)
        return httpx.Response(404)

    def factory(self):
        import httpx

        return httpx.MockTransport(self.handle)

    def calls(self, path: str) -> list[dict]:
        return [json.loads(r.content) for r in self.requests if r.url.path == path]


def standin_account(standin: ProductionStandIn, suffix: str, *, grant: bool = True):
    """A synthetic account with a live session on the stand-in, granted its usage under
    production's policy (`grantImportedUsage`, as the migration grants it)."""
    from psycopg.types.json import Jsonb

    from backend.modules.accounts.u8_control_policy import PRODUCTION_POLICY
    from backend.modules.plans.u8_usage import ImportedUsage
    from backend.transactions import Authority

    owner, session = uuid4(), uuid4()
    revision = uuid4()
    with standin.connect("accounts") as conn:
        conn.execute(
            "INSERT INTO accounts.account(id,email,password_hash,verified,active,"
            "authority_revision,display_name) VALUES(%s,%s,'not-login-material',true,true,%s,"
            "'synthetic')", (owner, f"{suffix}-{owner}@fixture.invalid", revision))
        conn.execute("INSERT INTO accounts.consent(account_id,purpose,granted) "
                     "VALUES(%s,'local-research',true)", (owner,))
        conn.execute(
            "INSERT INTO accounts.session(id,account_id,token_hash,csrf_hash,authority_revision,"
            "expires_at) VALUES(%s,%s,%s,%s,%s,clock_timestamp()+interval '30 minutes')",
            (session, owner, str(uuid4()), str(uuid4()), revision))
    with standin.connect("personalization") as conn:
        conn.execute("INSERT INTO personalization.settings(account_id,revision,defaults) "
                     "VALUES(%s,%s,%s)", (owner, uuid4(), Jsonb({"timeZone": "UTC"})))
    if grant:
        usage = ImportedUsage(standin.transactions, PRODUCTION_POLICY)
        assert usage.grant_imported(owner, source="realm_fixture")["disposition"] == "imported"
    return Authority(owner, session)


def free_quota(standin: ProductionStandIn, account_id) -> None:
    """The account's reservations moved one policy period back, so the period's quota is
    free again; the rows themselves stay."""
    from backend.modules.accounts.u8_control_policy import PRODUCTION_POLICY
    from backend.modules.plans.u8_usage import ResearchUsageService

    current = ResearchUsageService(standin.transactions, PRODUCTION_POLICY).current_period()
    prefix, number = current.split(":")
    with standin.admin() as conn:
        conn.execute("UPDATE usage.reservation SET period_id=%s WHERE account_id=%s",
                     (f"{prefix}:{int(number) - 1}", account_id))


def import_paper(standin: ProductionStandIn, chunks: list[dict], *, paper: str | None = None,
                 version: str | None = None, embed=None,
                 published: dt.date | None = None) -> dict:
    """One paper version in the stand-in's corpus through CorpusContent's own import:
    `chunks` as the document's chunks ({anchor, section, text[, piece]}), each with its
    vector from `embed` when given. `published` is the paper's publication date; U5
    selects only papers published inside a digest's window. Returns the scope's paper
    reference."""
    import hashlib

    from backend.modules.corpus.repository import CorpusImports
    from backend.modules.discovery.u8_search import VECTOR_POLICY

    paper = paper or f"standin-{uuid4().hex[:12]}"
    version = version or f"{paper}-v1"
    content_chunks = [{**chunk, "kind": "paragraph",
                       "textHash": hashlib.sha256(chunk["text"].encode()).hexdigest()}
                      for chunk in chunks]
    content = {"document": {"title": paper}, "chunks": content_chunks}
    raw = json.dumps(content, sort_keys=True).encode()
    outcome = CorpusImports(standin.transactions).import_paper(
        paper={"id": paper, "title": f"Paper {paper}", "authors": ["A. Author"],
               "publishedOn": published},
        version={"id": version, "label": "v1", "sourceUrl": f"https://arxiv.org/abs/{paper}",
                 "sourceHash": hashlib.sha256(raw).hexdigest(), "eligible": True,
                 "content": content},
        chunks=[{"anchor": chunk["anchor"], "section": chunk["section"], "text": chunk["text"],
                 "embedding": None if embed is None else embed(chunk["text"]),
                 "vectorPolicy": None if embed is None else VECTOR_POLICY}
                for chunk in chunks],
        private_path="standin.blob", provenance={"source": "test"},
    )
    assert outcome["disposition"] == "imported", outcome
    identity = standin.transactions.run("corpus", lambda conn: conn.execute(
        "SELECT corpus.guard_version(%s,'local-research') AS revision", (version,)
    ).fetchone())
    return {"paperId": paper, "versionId": version,
            "eligibilityRevision": str(identity["revision"])}


# --- U5's own digest path (U8 plan Step 159(a); L4-9) --------------------------------------
#
# The digest path tests drive U5's built parts on a production stand-in: the owner's
# real follow and saves, U5's due read, preparation and scheduler, and U5's own run
# transitions. Nothing stands between the scheduler and the store; the one double is the
# delivery, which records an attempt and answers nothing. `topics.next_occurrence` reads
# a boundary stamped by the database's real clock, so every `day` is a future day.

DIGEST_PATH_CHUNKS = [{"anchor": "a1", "section": "Abstract",
                       "text": "A synthetic abstract for the digest path."}]


class RecordingDelivery:
    """The local-sink path: `attempt` records the run and answers nothing, so the run
    stays `sending`, as when a transport's answer never comes back."""

    def __init__(self) -> None:
        self.attempts: list = []

    def recipient_scope(self) -> None:
        return None

    def path_kind(self) -> str:
        return "local-sink"

    def attempt(self, sending: dict, run: dict) -> None:
        self.attempts.append(sending["id"])

    def reconcile_decision(self, run: dict) -> None:
        return None


def save_zone(standin: ProductionStandIn, owner, zone: str) -> None:
    """The owner's zone through the personalization save, as the settings route makes it."""
    from backend.modules.personalization.guarded_service import GuardedSettingsService

    settings = GuardedSettingsService(standin.transactions)
    settings.update(owner, uuid4(), settings.read(owner)["revision"], {"timeZone": zone})


def digest_due_topic(standin: ProductionStandIn, suffix: str, day: dt.date, *,
                     time: str = "09:00", cadence: str = "daily", weekday: str | None = None,
                     zone: str | None = None, previous: dt.date | None = None):
    """An owner whose topic's next delivery falls on `day`: the topic followed and its
    settings saved through U5's own service, a terminal (empty) run prepared for
    `previous` (the day before by default), and a paper published inside `day`'s window,
    so the window is not empty."""
    from backend.modules.topics.repository import TopicsRepository
    from backend.modules.topics.service import TopicsService

    owner = standin_account(standin, suffix, grant=False)
    if zone is not None:
        save_zone(standin, owner, zone)
    service = TopicsService(standin.transactions)
    topic = service.follow(owner, f"path-{uuid4().hex[:12]}", "Digest path")["topicId"]
    service.save_settings(owner, topic, {
        "revision": 1, "cadence": cadence, "deliveryTimeLocal": time,
        "deliveryDay": weekday, "contentWindowDays": 7})
    revision = service.read_topic(owner, topic)["settings"]["revision"]
    repository = TopicsRepository(standin.transactions)
    before = previous or day - dt.timedelta(days=1)
    ended, adopted = repository.prepare_run(topic, before, before, revision, [])
    assert (ended["state"], adopted) == ("empty", False)
    import_paper(standin, DIGEST_PATH_CHUNKS, published=day - dt.timedelta(days=1))
    return SimpleNamespace(standin=standin, owner=owner, topic=topic, service=service,
                           repository=repository, day=day)


def digest_path(standin: ProductionStandIn, suffix: str, day: dt.date, **settings):
    """`digest_due_topic` with U5's built `TopicsScheduler` over the stand-in's store and
    a recording delivery."""
    from backend.modules.topics.preparation import DigestPreparation
    from backend.modules.topics.scheduler import TopicsScheduler
    from backend.u5_policy import SYNTHETIC_TOPICS

    path = digest_due_topic(standin, suffix, day, **settings)
    path.delivery = RecordingDelivery()
    path.scheduler = TopicsScheduler(
        standin.transactions,
        DigestPreparation(standin.transactions, None, policy=SYNTHETIC_TOPICS),
        path.delivery, policy=SYNTHETIC_TOPICS)
    return path


def digest_pass(path, at: dt.datetime) -> dict:
    """One pass of the path's scheduler, its clock pinned at `at` on the instance."""
    path.scheduler._now = lambda: at
    return path.scheduler.run_once()


def digest_run_of(path) -> dict | None:
    """The topic's newest run as stored."""
    return path.repository.system(lambda conn: conn.execute(
        "SELECT id,state,scheduled_at,created_at,window_end FROM topics.digest_run "
        "WHERE topic_id=%s ORDER BY created_at DESC,id LIMIT 1", (path.topic,)).fetchone())


def end_digest_path(path) -> None:
    """The path's pending run ended and its topic unsubscribed, each by U5's own move:
    a `sending` run finishes sent, an `unknown` run is resolved by its owner, and the
    unsubscribe discards a run still prepared. The topic then has no due delivery."""
    run = digest_run_of(path)
    if run["state"] == "sending":
        path.repository.finish_send(run["id"], "sent")
    elif run["state"] == "unknown":
        path.repository.resolve_run(path.owner, path.topic, run["id"], "failed")
    path.service.unsubscribe(path.owner, path.topic)


# --- The production composition (U8 plan Step 40; your decision of 2026-10-24) ------------
#
# `production_composition` composes production through `compose()` itself, with the real
# `BUILDERS`, on the stand-in with its release folder and its arrangement under the marked
# folder's prefix. Every provider is configured unless a case leaves one out; the shared
# model runtime answers through `ModelStandIn`, never 127.0.0.1:11434.

# Its secrets are generated at import, once per process (L1-36), in their shapes.
PROVIDER_ENVIRONMENT = {
    "googleClientId": "docsuri-production-test.apps.example",
    "googleClientSecret": "google-client-secret-" + secrets.token_hex(5),
    "orcidClientId": "APP-PRODUCTIONTEST01",
    "orcidClientSecret": "orcid-client-secret-" + secrets.token_hex(5),
    "resendApiKey": "re_resend-test-key-" + secrets.token_hex(5),
    "accountMailSender": "DocSuri <account@mail.fixture.example.com>",
    "digestSender": "DocSuri <digest@mail.fixture.example.com>",
}
EXPORT_DESTINATION = "0123456789abcdef0123456789abcdef"
MARKER_EVIDENCE = "f" * 64


def export_settings(profile) -> dict:
    """U6's run-bound real-export settings for the profile (`real-export.json`)."""
    today = dt.datetime.now(dt.UTC).date() - dt.timedelta(days=1)
    return {"runId": profile.run_id, "activationDestinationId": EXPORT_DESTINATION,
            "freeTerms": {"plan": "free", "memberCount": 1, "checkedOn": today.isoformat(),
                          "publishedLimits": ["Free plan block limit for workspaces with two "
                                              "or more members"]}}


@contextlib.contextmanager
def production_composition(realm, *, mode: str = "rehearsal", environment=None,
                           export: bool = True, marker=("assistance", "research"),
                           maintainer: bool = True, builders=None, process: str = "host"):
    """Production composed by `compose()` with the real builders (module comment).
    `marker` names the readiness marker's purposes (`{}` writes an empty marker, None
    writes none); `builders` may leave a contribution out, never stub one."""
    import pytest

    from backend.modules.export import notion_session
    from backend.modules.summarization import model_runtime

    model = ModelStandIn()
    patch = pytest.MonkeyPatch()
    patch.setattr(model_runtime, "network_transport", model.factory)
    # compose() installs its provider gate in U6's module-level Notion gate and leaves it
    # there after close; a fresh dict here means `patch.undo()` restores the module's own
    # gate, so no later test meets this composition's gate over its closed ledger.
    patch.setattr(notion_session, "_INSTALLED_GATE", {})
    try:
        with production_stand_in(realm, maintainer=maintainer, mode=mode, release=True,
                                 environment=PROVIDER_ENVIRONMENT if environment is None
                                 else environment) as standin:
            root = standin.profile.root
            if export:
                write_private(root / "real-export.json",
                              json.dumps(export_settings(standin.profile)).encode())
            if marker == {}:
                (root / "evidence").mkdir(mode=0o700, exist_ok=True)
                write_private(root / "evidence" / "model-readiness.json", b"{}")
            elif marker is not None:
                write_readiness(standin.profile, dict.fromkeys(marker, MARKER_EVIDENCE))
            composition = compose(standin.profile, process=process,
                                  release_root=standin.release_root,
                                  arrangement=standin.arrangement, builders=builders)
            try:
                yield SimpleNamespace(standin=standin, composition=composition, model=model)
            finally:
                composition.close()
    finally:
        patch.undo()


async def set_flag(flag: threading.Event) -> None:
    """Ends once `flag` is set, re-read every 0.01 s; `signal_or_failure` bounds it."""
    while not flag.is_set():
        await asyncio.sleep(0.01)


async def signal_or_failure(signal, task: asyncio.Task, seconds: float, message: str) -> None:
    """Wait at most `seconds` for `signal` (an awaitable) or `task`, whichever ends first.
    A task that ends first raises its own exception at once; one that returns, or a
    signal that never comes, fails with `message`."""
    waiter = asyncio.ensure_future(signal)
    try:
        done, _ = await asyncio.wait({waiter, task}, timeout=seconds,
                                     return_when=asyncio.FIRST_COMPLETED)
    finally:
        if not waiter.done():
            waiter.cancel()
    if waiter in done:
        return
    if task in done:
        task.result()  # re-raises the task's own exception
        raise AssertionError(f"{message}: the task ended first")
    raise AssertionError(message)
