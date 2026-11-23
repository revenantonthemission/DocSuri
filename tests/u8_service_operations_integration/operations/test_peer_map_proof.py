"""The peer map and the root-owned rule files, proved against a real PostgreSQL 16 (package
G3, your answer of 2026-11-11, "Scratch container"; package G1's item 7).

The realm's own database container is read-only, so the proof runs in a short-lived
container of the realm's own verified image (the manifest's `databaseImage`, PostgreSQL
16.14 with pgvector 0.8.7): small limits, no published port, `--network none`, and the
label key `dev.docsuri.u8.peer-proof` valued with the realm's run ID. It never names the
realm's own container or volume. Inside it, as root:

- the database account (`Accounts.database`, `_docsuri_v2_db`) and one unmapped account
  are made;
- `render.render_postgres` renders `pg_hba.conf` and `pg_ident.conf` into the root-owned
  `postgres-rules` folder, each with its rendered owner and mode;
- the installer's own `ProductionDatabase.initdb` runs `initdb` as the database account,
  with the installer's own arguments;
- the server starts as the database account with the launch job's own arguments
  (`render.launch_jobs`), adapting only the paths: the prefix is a folder of the container,
  and the runtime's programs are the image's.

Then four claims: (1) the database account signs in as `render.SUPERUSER` over the socket
with no password; (2) `SHOW hba_file` and `SHOW ident_file` answer the pinned paths;
(3) the unmapped account is refused; (4) neither rule file is writable by the database
account. Claims (1) and (2) go through the installer's and the isolation check's own
tools, run inside the container. Peer sign-in needs no password, so this module holds none.

The container is removed in the fixture's `finally`, which starts before anything can fail;
a run killed at its part's bound skips it, so the runner removes the container by its
label key after each child of the part and in `archive-owned`.
"""

from __future__ import annotations

import json
import secrets
import subprocess
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from docsuri_ops import isolation_macos
from docsuri_ops.arrangement import macos as arrangement_macos
from docsuri_ops.arrangement import render
from docsuri_ops.arrangement.installer import ProductionDatabase
from docsuri_ops.arrangement.macos import ToolFailed
from docsuri_ops.arrangement.paths import Accounts, ArrangementPaths

PEER_PROOF_LABEL = "dev.docsuri.u8.peer-proof"
# The container's own prefix; the arrangement's layout under it (`ArrangementPaths.under`).
PROOF_PREFIX = Path("/srv/docsuri-peer-proof/DocSuri")
# The image's PostgreSQL 16 programs, in place of the arrangement's runtime folder.
IMAGE_BIN = "/usr/lib/postgresql/16/bin"
UNMAPPED = ("docsuri_unmapped", 640)
PROOF_MEMORY = 256 * 1024**2
PROOF_RESERVE = 512 * 1024**2
PROOF_PIDS = 64
# The container ends itself after this many seconds even if every removal were skipped; the
# runner still removes the stopped container by its label.
PROOF_LIFETIME = 180
READY_SECONDS = 30
PROOF_SECONDS = 60
POSTGRES_JOB = "org.docsuri.v2.postgres"
IMAGE_DATA_TMPFS = "/var/lib/postgresql/data:rw,noexec,nosuid,size=1m"


class Scratch:
    """The proof's container: every program runs through `docker exec`, under the Docker
    endpoint the runner passes on; a program in the arrangement's runtime folder runs as
    the image's own program of that name."""

    def __init__(self, runner, container: str, paths: ArrangementPaths):
        self.runner = runner
        self.container = container
        self.paths = paths
        self.failures: list[str] = []

    def program(self, argv: list[str]) -> list[str]:
        runtime = str(self.paths.postgres_runtime / "bin") + "/"
        first = argv[0]
        if first.startswith(runtime):
            first = f"{IMAGE_BIN}/{first.removeprefix(runtime)}"
        return [first, *argv[1:]]

    def docker(self, argv: list[str], *, user: str | None = None, data: bytes | None = None,
               detach: bool = False, workdir: str | None = None,
               seconds: float = 30) -> subprocess.CompletedProcess:
        words = ["docker", "exec"]
        if data is not None:
            words.append("-i")
        if detach:
            words.append("-d")
        if user is not None:
            words += ["-u", user]
        if workdir is not None:
            words += ["-w", workdir]
        words += [self.container, *self.program(argv)]
        completed = subprocess.run(words, input=data, capture_output=True, timeout=seconds,
                                   check=False, env=self.runner.child_environment(None))
        if completed.returncode != 0:
            self.failures.append(f"{Path(argv[0]).name}: "
                                 + completed.stderr[-300:].decode("utf-8", "replace"))
        return completed

    def root(self, *argv: str, data: bytes | None = None) -> None:
        completed = self.docker(list(argv), user="0:0", data=data)
        if completed.returncode != 0:
            pytest.fail(f"{argv[0]} failed in the proof's container: {self.failures[-1]}")

    def run(self, argv: list[str], *, capture_output: bool, timeout: float, check: bool,
            user: int | None = None, group: int | None = None,
            extra_groups: list[int] | None = None, input: bytes | None = None,
            cwd: str | None = None) -> subprocess.CompletedProcess:
        """`subprocess.run`'s shape, for the installer's and the isolation check's own
        tools: a run as `user` is `docker exec -u user:group`, which sets no supplementary
        group the container's account tables do not list (`extra_groups=[]`)."""
        if not capture_output or check or extra_groups not in (None, []):
            raise AssertionError("the proof's tools capture output and check codes themselves")
        who = None if user is None else f"{user}:{user if group is None else group}"
        return self.docker(argv, user=who, data=input, workdir=cwd, seconds=timeout)


def seconds_since(started: float) -> float:
    return round(time.monotonic() - started, 2)


@pytest.fixture(scope="module")
def proof(realm):
    """The prepared container with its server running (module docstring); removed in
    `finally` whatever happened."""
    from scripts import verify_docsuri_u8 as runner

    started = time.monotonic()
    container = f"docsuri-u8-peer-proof-{secrets.token_hex(6)}"
    try:
        manifest = json.loads((Path(realm.root) / "environment.json").read_bytes())
        image, realm_run = manifest["databaseImage"], manifest["runId"]
        available = runner.docker_available_memory(image)
        if available < PROOF_MEMORY + PROOF_RESERVE:
            pytest.fail(f"Docker available bytes {available} below the proof's 256 MiB and "
                        "the 512 MiB recovery reserve")
        # Realms run one at a time: a container under the key is a killed run's leftover.
        runner.remove_peer_proofs()
        created = runner.command([
            "docker", "run", "-d", "--name", container,
            "--label", f"{PEER_PROOF_LABEL}={realm_run}",
            "--network", "none", "--memory", "256m", "--memory-swap", "256m",
            "--pids-limit", str(PROOF_PIDS), "--cpus", "1",
            # The image declares this folder a volume; a small tmpfs in its place keeps
            # Docker from making an anonymous volume for a folder the proof never uses.
            "--tmpfs", IMAGE_DATA_TMPFS,
            "--entrypoint", "sleep", image, str(PROOF_LIFETIME),
        ], timeout=60)
        if created.returncode != 0:
            pytest.fail("the proof's container did not start: " + created.stderr[-500:])
        record = json.loads(runner.command(["docker", "container", "inspect", container],
                                           timeout=30).stdout)[0]
        host = record["HostConfig"]
        assert record["Config"]["Labels"][PEER_PROOF_LABEL] == realm_run
        assert record["Image"] == image and host["NetworkMode"] == "none"
        # No published port, no volume or bind mount: nothing of the realm's is reachable.
        assert not host["PortBindings"] and record["Mounts"] == []
        assert host["Tmpfs"] == dict([IMAGE_DATA_TMPFS.split(":", 1)])
        assert host["Memory"] == host["MemorySwap"] == PROOF_MEMORY
        assert host["PidsLimit"] == PROOF_PIDS
        assert manifest["container"] != container and manifest["volume"] not in json.dumps(
            record["Mounts"])

        paths = ArrangementPaths.under(PROOF_PREFIX)
        accounts = Accounts.standard()
        scratch = Scratch(runner, container, paths)
        prepare_accounts(scratch, accounts)
        install_rules(scratch, paths, accounts)
        database = ProductionDatabase(SimpleNamespace(
            paths=paths, accounts=accounts,
            tools=arrangement_macos.MacTools(run=scratch.run)))
        try:
            database.initdb()
        except ToolFailed:
            pytest.fail("the installer's initdb failed: " + scratch.failures[-1])
        job = start_server(scratch, paths, accounts)
        deadline = time.monotonic() + READY_SECONDS
        while not database.ready():
            if time.monotonic() > deadline:
                pytest.fail("the proof's server never became ready: "
                            + "; ".join(scratch.failures[-3:]))
            time.sleep(0.25)
        yield SimpleNamespace(scratch=scratch, paths=paths, accounts=accounts,
                              database=database, job=job, started=started)
    finally:
        removed = runner.command(["docker", "rm", "-f", "-v", container], timeout=60)
        # Removed now, or never made (Docker then answers "No such container").
        assert removed.returncode == 0 or "No such container" in removed.stderr


def prepare_accounts(scratch: Scratch, accounts: Accounts) -> None:
    """The database account and one unmapped account, each with its own group."""
    for name, uid in ((accounts.database.name, accounts.database.uid), UNMAPPED):
        scratch.root("groupadd", "--gid", str(uid), name)
        scratch.root("useradd", "--uid", str(uid), "--gid", str(uid), "--no-create-home",
                     "--home-dir", "/nonexistent", "--shell", "/usr/sbin/nologin", name)


def install_rules(scratch: Scratch, paths: ArrangementPaths, accounts: Accounts) -> None:
    """The prefix root's; `postgres-rules` root's, 0755, holding the two rendered rule files
    with their rendered owner and mode; `postgres/` and its socket folder the database
    account's, 0700. `postgresql.conf` is not installed: its 512 MB of shared buffers do
    not fit the proof's limits, and the launch job's arguments pin every setting the claims
    read."""
    uid = str(accounts.database.uid)
    scratch.root("install", "-d", "-m", "0755", "-o", "root", "-g", "root", str(paths.prefix))
    scratch.root("install", "-d", "-m", "0755", "-o", "root", "-g", "root",
                 str(paths.postgres_rules))
    for folder in (paths.postgres_data.parent, paths.postgres_socket):
        scratch.root("install", "-d", "-m", "0700", "-o", uid, "-g", uid, str(folder))
    rules = [item for item in render.render_postgres(paths, accounts) if item.kind == "rule"]
    assert sorted(item.target.name for item in rules) == ["pg_hba.conf", "pg_ident.conf"]
    for item in rules:
        assert item.target.parent == paths.postgres_rules and item.owner == "root"
        target = str(item.target)
        scratch.root("sh", "-c", 'umask 077; cat > "$1"', "sh", target, data=item.content)
        scratch.root("chown", "root:root", target)
        scratch.root("chmod", format(item.mode, "o"), target)


def start_server(scratch: Scratch, paths: ArrangementPaths, accounts: Accounts) -> dict:
    """The launch job's own arguments as the database account, from its working folder."""
    job = next(item for item in render.launch_jobs(paths) if item["label"] == POSTGRES_JOB)
    assert job["account"] == "database"
    who = f"{accounts.database.uid}:{accounts.database.uid}"
    started = scratch.docker(list(job["arguments"]), user=who, detach=True,
                             workdir=job["workingDirectory"])
    if started.returncode != 0:
        pytest.fail("the server did not start: " + scratch.failures[-1])
    return job


def pinned(job: dict, setting: str) -> str:
    """The value the launch job pins with `-c <setting>=`."""
    arguments = job["arguments"]
    values = [arguments[index + 1].removeprefix(f"{setting}=")
              for index, word in enumerate(arguments[:-1])
              if word == "-c" and arguments[index + 1].startswith(f"{setting}=")]
    assert len(values) == 1, setting
    return values[0]


def as_unmapped(proof, *argv: str) -> subprocess.CompletedProcess:
    return proof.scratch.docker(list(argv), user=f"{UNMAPPED[1]}:{UNMAPPED[1]}")


def psql_as_superuser(proof) -> list[str]:
    paths = proof.paths
    return [str(paths.postgres_runtime / "bin" / "psql"), "-X", "-w", "-At", "-h",
            str(paths.postgres_socket), "-p", "15432", "-U", render.SUPERUSER, "-d",
            "postgres", "-c", "SELECT 1"]


def test_claim_1_the_database_account_signs_in_as_the_superuser_with_no_password(proof):
    """Through the installer's own `psql` as the database account: peer, over the socket,
    `-w` so no password prompt is ever answered. `system_user` (PostgreSQL 16) names the
    method and the operating-system account the map admitted. The data folder's own
    `pg_hba.conf` (initdb's, with no map) would refuse this sign-in, so it also shows the
    pinned rule files are in force."""
    database = proof.database
    answer = database._as_database(database._psql(
        "-w", "-At", "-c", "SELECT current_user, session_user, system_user")).decode()
    assert answer.strip() == (f"{render.SUPERUSER}|{render.SUPERUSER}|"
                              f"peer:{proof.accounts.database.name}")
    assert render.SUPERUSER == "postgres"


def test_claim_2_show_hba_file_and_ident_file_answer_the_pinned_paths(proof):
    """The isolation check's own `MacTools.hba_file` and `ident_file`, asked as the database
    account inside the container: each answers the launch job's pin, the file in the
    root-owned rules folder."""
    tools = isolation_macos.MacTools(run=proof.scratch.run)
    paths, uid = proof.paths, proof.accounts.database.uid
    psql = str(paths.postgres_runtime / "bin" / "psql")
    socket = str(paths.postgres_socket)
    hba, ident = paths.postgres_rules / "pg_hba.conf", paths.postgres_rules / "pg_ident.conf"
    assert pinned(proof.job, "hba_file") == str(hba)
    assert pinned(proof.job, "ident_file") == str(ident)
    assert tools.hba_file(psql, socket, uid) == str(hba)
    assert tools.ident_file(psql, socket, uid) == str(ident)
    assert str(paths.postgres_data) not in (str(hba), str(ident))


def test_claim_4_neither_rule_file_is_writable_by_the_database_account(proof):
    """Each rule file is root's, 0644: the database account can read it but neither write,
    append to nor replace it, and cannot add a file beside it. The same checks succeed in
    the database account's own data folder, so a refusal here is the files' custody."""
    paths, account = proof.paths, proof.accounts.database
    who = f"{account.uid}:{account.uid}"
    scratch = proof.scratch

    def code(*argv: str) -> int:
        return scratch.docker(list(argv), user=who).returncode

    for name in ("pg_hba.conf", "pg_ident.conf"):
        target = str(paths.postgres_rules / name)
        stat = scratch.docker(["stat", "-c", "%U %G %a %F", target], user="0:0")
        assert stat.stdout.decode().strip() == "root root 644 regular file", name
        assert code("test", "-r", target) == 0, name
        assert code("test", "-w", target) != 0, name
        assert code("sh", "-c", 'echo "local all all trust" >> "$1"', "sh", target) != 0, name
        assert code("ln", "-sf", "/dev/null", target) != 0, name
    rules = scratch.docker(["stat", "-c", "%U %a", str(paths.postgres_rules)], user="0:0")
    assert rules.stdout.decode().strip() == "root 755"
    assert code("touch", str(paths.postgres_rules / "pg_hba.conf.new")) != 0
    # The control: the database account writes in its own folder.
    own = str(paths.postgres_data / "peer-proof-control")
    assert code("touch", own) == 0 and code("test", "-w", own) == 0
    assert code("rm", own) == 0
    # Nothing the refused writes tried changed either file.
    for item in render.render_postgres(paths, proof.accounts):
        if item.kind == "rule":
            held = scratch.docker(["cat", str(item.target)], user="0:0").stdout
            assert held == item.content, item.target.name


def test_claim_3_the_unmapped_account_is_refused(proof):
    """The unmapped account cannot reach the socket under the launch job's 0700
    permissions. To show the map itself refuses it, root then opens the socket's path to
    it, and its peer sign-in as the superuser is refused for the map, while the database
    account's is still admitted. Run last: it widens the socket for the rest of the module."""
    scratch, paths = proof.scratch, proof.paths
    command = psql_as_superuser(proof)
    blocked = as_unmapped(proof, *command)
    assert blocked.returncode != 0
    assert b"Permission denied" in blocked.stderr
    assert pinned(proof.job, "unix_socket_permissions") == "0700"
    socket_file = str(paths.postgres_socket / ".s.PGSQL.15432")
    scratch.root("chmod", "0711", str(paths.postgres_data.parent), str(paths.postgres_socket))
    scratch.root("chmod", "0777", socket_file)
    refused = as_unmapped(proof, *command)
    assert refused.returncode != 0
    assert (b'Peer authentication failed for user "' + render.SUPERUSER.encode() + b'"'
            in refused.stderr)
    # The same opened socket still admits the mapped account.
    database = proof.database
    answer = database._as_database(database._psql("-w", "-At", "-c", "SELECT system_user"))
    assert answer.decode().strip() == f"peer:{proof.accounts.database.name}"
    elapsed = seconds_since(proof.started)
    assert elapsed < PROOF_SECONDS, f"the proof took {elapsed} s"
