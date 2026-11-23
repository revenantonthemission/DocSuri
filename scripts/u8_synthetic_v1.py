"""The composed realm's synthetic v1 (U8 plan Step 43: `v1-up` and `v1-down`).

v1 runs from its own code at the repository's commit, against its own data plane, with
synthetic data only, at the realm's own addresses (decision "The composed realm's
addresses"), never v1's real ones:

| Part | Realm address | v1's own |
|---|---|---|
| v1's API (`backend.main:app`, one Uvicorn worker) | 18112 | 8000 |
| v1's Next.js standalone web | 18113 | 3000 |
| PostgreSQL, Redis, OpenSearch, objects | 15510, 16389, 19209, 19009 | 5432, 6379, 9200, 9000 |

Every address is on 127.0.0.1. PostgreSQL, Redis and OpenSearch are exactly
`backend/docker-compose.yml`'s pinned images. **Deviation (the person's decision of
2026-10-23):** the object store is SeaweedFS (`chrislusf/seaweedfs`, pinned by digest, its
S3 gateway), not compose's pinned MinIO, because MinIO's pinned image can no longer be
pulled from any registry. v1's own code reaches it through its normal S3 settings
(`AWS_ENDPOINT_URL_S3` and the run's keys).

- **The web** is built once per commit in a git worktree outside the repository folder
  (`~/.docsuri-u8/v1-web-<commit>`), from the repository's own lockfile with pnpm 9.15.9,
  never in the live `frontend/` (whose `.next/` the live site serves). The build's public
  flags are the live install's (`ops/server/docsurictl`). Only that worktree is ever removed
  (`remove-web`).
- **The data plane**: the four images above, each pinned by digest and bounded in memory
  so the realm's database, the U6 environment and this fit in Colima's VM together,
  labelled with the run, published on loopback only. ElasticMQ, which only v1's
  asynchronous workers use, is not started: the decision names four data-plane ports.
- **v1's own migrations** (every file of v1's registry, in its order, recorded in v1's own
  ledger; `migrate_v1`), then **the synthetic v1 data** (`scripts/u8_fixtures.py`) is
  loaded into v1's tables, index and bucket.
- **The supervisor** (`supervise`, started detached by `v1-up`) is the realm's process
  supervisor for v1's two named services. It acts on the wanted state the realm driver's
  service control writes (`platform/services/<label>.json`), starts or stops the process,
  and acknowledges each operation once the process answers its health address or has
  exited (`<label>.ack.json`), so a service-control receipt means the service really
  started or stopped.

Every v1 process gets the realm's addresses explicitly, and only after
`docsuri_ops.u8_platform.v1_environment` has checked them. v1's session store
otherwise defaults to `localhost:6379`, the live site's Redis, so nothing here starts
without that check passing.
No v1 process is given a model, mail or provider endpoint: v1 serves its mock search and
its console mail, and calls nothing outward. Everything refuses the production profile.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import secrets
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for entry in (ROOT, ROOT / "ops/src", ROOT / "scripts"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

RUN = Path("/tmp/docsuri-u8-run").resolve()
STATE = RUN / "v1"
SERVICES = RUN / "platform" / "services"
WEB_ROOT = Path.home() / ".docsuri-u8"
PYTHON = ROOT / "backend/.venv/bin/python"
PNPM = ("corepack", "pnpm@9.15.9")
LABEL = "dev.docsuri.u8.run"
V1_LABEL = "dev.docsuri.u8.v1"
API_LABEL, WEB_LABEL = "dev.docsuri.u8.run.v1-api", "dev.docsuri.u8.run.v1-web"
API_PORT, WEB_PORT = 18112, 18113
API_HEALTH = f"http://127.0.0.1:{API_PORT}/health"
WEB_HEALTH = f"http://127.0.0.1:{WEB_PORT}/"
PUBLIC_ORIGIN = "https://127.0.0.1:18110"
# The data plane: `backend/docker-compose.yml`'s pinned images, sized for the realm.
IMAGES = {
    "postgres": "postgres:16@sha256:"
                "a3b7f434b2dc57ce85a67e171163eb8ab1a1ebcb39d27484661f26b1dfbe30d6",
    "redis": "redis:7.4.11@sha256:c6eabf748fc7a61dbb5a705c78bcf3d6377b1127a97d0ce965c11c44ba46896f",
    "opensearch": "opensearchproject/opensearch:2.19.5@sha256:"
                  "4ee82ecb35d837a6186c81aaa64c8a5bce71aa956edbd87f1f684ab56af52c44",
    # The person's decision of 2026-10-23: SeaweedFS's S3 gateway, not compose's MinIO.
    "objects": "chrislusf/seaweedfs@sha256:"
               "4e61d15fd35994cb1e43e1e553dff106794841fd9a99ade2fc8c8bfce4d7872d",
}
PORTS = {"postgres": (15510, 5432), "redis": (16389, 6379), "opensearch": (19209, 9200),
         "objects": (19009, 8333)}
MEMORY = {"postgres": 512 * 1024**2, "redis": 128 * 1024**2, "opensearch": 1024**3,
          "objects": 384 * 1024**2}
OPENSEARCH_HEAP = "-Xms384m -Xmx384m"
RECOVERY_RESERVE = 512 * 1024**2
DISK_FLOOR = 6 * 1024**3
DATABASE, DATABASE_USER = "docsuri", "docsuri"
UP_SECONDS = 300
START_SECONDS = 90  # inside the driver's 100 s wait and the 120 s service deadline
STOP_SECONDS = 15
POLL_SECONDS = 0.25
MAX_LOG = 16 * 1024**2
# The live install's build flags (ops/server/docsurictl), with ORCID's button off as there.
WEB_BUILD_FLAGS = {"NEXT_PUBLIC_DOCSURI_REAL_API": "1",
                   "NEXT_PUBLIC_DOCSURI_RESEARCH_AGENT_ENABLED": "true",
                   "NEXT_PUBLIC_ORCID_LOGIN_ENABLED": "false"}


class V1Refused(RuntimeError):
    """A fixed reason; never a secret or private content."""


# --- the run ------------------------------------------------------------------------------


def run_identity(environment: Path, *, allow_expired: bool = False) -> dict:
    """The realm's manifest, refusing anything but the composed realm's own run.

    An expired realm is refused for execution; `allow_expired` admits it only for
    the v1 stop, where expiry must not keep v1 alive while the realm is set aside.
    Every custody check stays.
    """
    from backend.local_profile import LocalProfile, private_bytes

    try:
        profile = LocalProfile.load(environment)
    except ValueError as expired:
        if not allow_expired:
            raise
        value = LocalProfile.preservation_identity(environment)
        if (
            environment.resolve() != RUN / "environment.json"
            or (value.get("realm"), value.get("database"))
            != ("service-operations", "docsuri_u8")
        ):
            raise V1Refused("the synthetic v1 serves the composed realm only") from expired
        return json.loads(private_bytes(environment))
    if getattr(profile, "is_production", False) or (
        profile.realm, profile.database_name, profile.root) != ("service-operations",
                                                                "docsuri_u8", RUN):
        raise V1Refused("the synthetic v1 serves the composed realm only")
    return json.loads(private_bytes(environment))


def private_folder(path: Path) -> Path:
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = path.lstat()
    if not path.is_dir() or path.is_symlink() or info.st_uid != os.getuid() or (
        info.st_mode & 0o777) != 0o700:
        raise V1Refused(f"{path.name} must be a private folder")
    return path


def write_private(path: Path, value: object) -> None:
    from u8_fixtures import write_private as write

    private_folder(path.parent)
    write(path, value)


def read_private(path: Path) -> dict | None:
    from backend.local_profile import private_bytes

    try:
        return json.loads(private_bytes(path))
    except FileNotFoundError:
        return None


def commit() -> str:
    head = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True,
                          text=True, timeout=30, check=True).stdout.strip()
    if len(head) != 40:
        raise V1Refused("repository commit unreadable")
    return head


def credentials(run_id: str) -> dict:
    path = STATE / "credentials.json"
    value = read_private(path)
    if value is not None:
        if value.get("runId") != run_id:
            raise V1Refused("synthetic v1 credentials belong to another run")
        return value
    value = {"runId": run_id, "postgres": secrets.token_urlsafe(24),
             "objectsUser": "u8v1" + secrets.token_hex(6),
             "objectsPassword": secrets.token_urlsafe(24), "reader": secrets.token_urlsafe(24)}
    write_private(path, value)
    return value


def v1_environment(secret: dict) -> dict:
    """Everything a v1 process is given: the realm's addresses only, no outward endpoint."""
    return {
        "ENV": "production",
        "DATABASE_URL": (f"postgresql+psycopg://{DATABASE_USER}:{secret['postgres']}@127.0.0.1:"
                         f"{PORTS['postgres'][0]}/{DATABASE}"),
        "REDIS_HOST": "127.0.0.1",
        "REDIS_PORT": str(PORTS["redis"][0]),
        "DOCSURI_OPENSEARCH_ENDPOINT": f"http://127.0.0.1:{PORTS['opensearch'][0]}",
        "DOCSURI_OPENSEARCH_USE_SSL": "0",
        "DOCSURI_OPENSEARCH_VERIFY_CERTS": "0",
        "AWS_ENDPOINT_URL_S3": f"http://127.0.0.1:{PORTS['objects'][0]}",
        "AWS_ACCESS_KEY_ID": secret["objectsUser"],
        "AWS_SECRET_ACCESS_KEY": secret["objectsPassword"],
        "AWS_REGION": "ap-northeast-2",
        "DOCSURI_AWS_REGION": "ap-northeast-2",
        "SES_MOCK": "true",
        "ACCOUNT_EVENTS_BUS": "none",
        "CORS_ORIGINS": PUBLIC_ORIGIN,
        "TRUST_PROXY_HEADERS": "0",
        "CLOUDFLARE_TRUSTED": "0",
        "RECAPTCHA_SECRET_KEY": "",
        "PYTHONUNBUFFERED": "1",
    }


def require_realm_addresses(environment: dict) -> None:
    """Refuse any v1 environment that could reach v1's real stores (the shared check the
    realm driver applies too)."""
    from docsuri_ops.u8_platform.v1_environment import (
        V1EnvironmentRefused,
        require_realm_environment,
    )

    try:
        require_realm_environment(environment)
    except V1EnvironmentRefused as refused:
        raise V1Refused(str(refused)) from None


def process_environment(extra: dict) -> dict:
    base = {key: os.environ[key] for key in ("PATH", "HOME", "LANG", "TMPDIR")
            if key in os.environ}
    base["PYTHONPATH"] = os.pathsep.join(str(ROOT / part) for part in (
        "", "shared/python/src", "backend/modules/discovery/src",
        "backend/modules/summarization/src", "ops/src"))
    return {**base, **extra}


# --- the web build (a worktree outside the repository) ------------------------------------


def worktree_for(head: str) -> Path:
    return WEB_ROOT / f"v1-web-{head[:12]}"


def build_marker(tree: Path) -> Path:
    """The build's record, beside the worktree in the private folder (the worktree root
    keeps git's own modes)."""
    return WEB_ROOT / f"{tree.name}.build.json"


def web_ready(tree: Path, head: str) -> bool:
    marker = read_private(build_marker(tree)) if tree.exists() else None
    return bool(marker and marker.get("commit") == head and (
        tree / "frontend/.next/standalone/server.js").is_file())


def private_log(path: Path):
    """A log in the run root: appended, never through a link, and always mode 0600, so
    the run's preservation check accepts it."""
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW, 0o600)
    os.fchmod(descriptor, 0o600)
    return os.fdopen(descriptor, "ab")


def _step(args: list[str], *, cwd: Path, seconds: float, environment: dict | None = None,
          log: Path) -> None:
    with private_log(log) as stream:
        completed = subprocess.run(args, cwd=cwd, stdout=stream, stderr=subprocess.STDOUT,
                                   env=environment, timeout=seconds, check=False)
    if completed.returncode != 0:
        raise V1Refused(f"web build step failed: {args[0]} {args[1] if len(args) > 1 else ''}")


def build_web(head: str, *, seconds: float) -> dict:
    """The worktree at the commit, the lockfile's install, and `next build` there."""
    deadline = time.monotonic() + seconds
    private_folder(WEB_ROOT)
    tree = worktree_for(head)
    log = private_folder(STATE) / "web-build.log"
    private_log(log).close()
    if web_ready(tree, head):
        return {"state": "present", "worktree": str(tree)}
    started = time.monotonic()
    if not tree.exists():
        _step(["git", "-C", str(ROOT), "worktree", "add", "--detach", str(tree), head],
              cwd=ROOT, seconds=120, log=log)
    if (tree / "frontend/.next").exists() and not web_ready(tree, head):
        raise V1Refused("the worktree holds an unfinished build; remove-web, then v1-up")
    environment = process_environment({"CI": "true", "NEXT_TELEMETRY_DISABLED": "1",
                                       "COREPACK_ENABLE_DOWNLOAD_PROMPT": "0",
                                       **WEB_BUILD_FLAGS})
    _step([*PNPM, "--dir", "frontend", "install", "--frozen-lockfile", "--prefer-offline"],
          cwd=tree, seconds=max(1, deadline - time.monotonic()), environment=environment,
          log=log)
    _step([*PNPM, "--dir", "frontend", "exec", "next", "build"], cwd=tree,
          seconds=max(1, deadline - time.monotonic()), environment=environment, log=log)
    standalone = tree / "frontend/.next/standalone"
    (standalone / ".next").mkdir(exist_ok=True)
    for link, target in ((standalone / ".next/static", tree / "frontend/.next/static"),
                         (standalone / "public", tree / "frontend/public")):
        if not link.is_symlink() and not link.exists():
            link.symlink_to(target)
    write_private(build_marker(tree), {"commit": head})
    return {"state": "built", "worktree": str(tree),
            "seconds": round(time.monotonic() - started, 1)}


def remove_web(head: str) -> dict:
    """Remove only the worktree this tool added (`git worktree remove`)."""
    tree = worktree_for(head)
    if not tree.exists():
        return {"state": "absent", "worktree": str(tree)}
    subprocess.run(["git", "-C", str(ROOT), "worktree", "remove", "--force", str(tree)],
                   check=True, timeout=120, capture_output=True)
    build_marker(tree).unlink(missing_ok=True)
    return {"state": "removed", "worktree": str(tree)}


# --- the data plane -------------------------------------------------------------------------


def docker(*args: str, seconds: float = 120, check: bool = True,
           environment: dict | None = None) -> subprocess.CompletedProcess:
    env = {key: os.environ[key] for key in ("PATH", "HOME", "DOCKER_CONFIG", "DOCKER_HOST")
           if key in os.environ}
    env.update(environment or {})
    completed = subprocess.run(["docker", *args], capture_output=True, text=True, env=env,
                               timeout=seconds, check=False)
    if check and completed.returncode != 0:
        raise V1Refused(f"docker {args[0]} failed")
    return completed


def container_name(run_id: str, part: str) -> str:
    return f"{run_id}-v1-{part}"


def inspect(name: str) -> dict | None:
    completed = docker("container", "inspect", name, check=False)
    if completed.returncode:
        return None
    records = json.loads(completed.stdout)
    return records[0] if len(records) == 1 else None


def require_owned(record: dict, run_id: str) -> None:
    labels = record["Config"].get("Labels") or {}
    if labels.get(LABEL) != run_id or labels.get(V1_LABEL) != run_id:
        raise V1Refused("a synthetic v1 container is not this run's; preserved")


def available_memory() -> int:
    """The Docker kernel's available memory, read with the realm's bounded probe."""
    sys.path.insert(0, str(ROOT / "scripts"))
    from verify_docsuri_u8 import docker_available_memory

    return docker_available_memory(IMAGES["redis"])


def preflight(run_id: str) -> dict:
    import shutil

    free = shutil.disk_usage(ROOT).free
    if free < DISK_FLOOR:
        raise V1Refused("free disk would fall below 6 GiB; nothing started")
    missing = [part for part in IMAGES if inspect(container_name(run_id, part)) is None]
    needed = sum(MEMORY[part] for part in IMAGES if part in missing or not running(
        inspect(container_name(run_id, part))))
    available = available_memory()
    if needed and available < needed + RECOVERY_RESERVE:
        raise V1Refused(f"Docker available bytes {available} below the synthetic v1's "
                        f"{needed} and the recovery reserve {RECOVERY_RESERVE}")
    return {"hostFreeBytes": free, "dockerAvailableBytes": available, "neededBytes": needed}


def running(record: dict | None) -> bool:
    return bool(record and record["State"]["Running"])


def run_command(run_id: str, part: str, secret: dict) -> tuple[list[str], dict]:
    host, inner = PORTS[part]
    name = container_name(run_id, part)
    args = ["run", "-d", "--name", name, "--label", f"{LABEL}={run_id}",
            "--label", f"{V1_LABEL}={run_id}", "--memory", str(MEMORY[part]),
            "--memory-swap", str(MEMORY[part]), "--pids-limit", "256",
            "-p", f"127.0.0.1:{host}:{inner}"]
    environment: dict = {}
    if part == "postgres":
        args += ["--mount", f"type=volume,src={name}-data,dst=/var/lib/postgresql/data",
                 "-e", f"POSTGRES_USER={DATABASE_USER}", "-e", f"POSTGRES_DB={DATABASE}",
                 "-e", "POSTGRES_PASSWORD",
                 # Loopback inside the container is SCRAM too, as in the realm's own
                 # container, so the agent's dump (require_auth=scram-sha-256) can log in.
                 "-e", "POSTGRES_INITDB_ARGS=--auth-host=scram-sha-256 --auth-local=trust",
                 IMAGES[part],
                 "-c", "shared_buffers=64MB", "-c", "max_connections=40"]
        environment["POSTGRES_PASSWORD"] = secret["postgres"]
    elif part == "redis":
        args += ["--tmpfs", "/data:rw,size=32m", IMAGES[part], "redis-server", "--save", "",
                 "--appendonly", "no", "--maxmemory", "64mb"]
    elif part == "opensearch":
        args += ["--mount", f"type=volume,src={name}-data,dst=/usr/share/opensearch/data",
                 "-e", "discovery.type=single-node", "-e", "DISABLE_SECURITY_PLUGIN=true",
                 "-e", "DISABLE_INSTALL_DEMO_CONFIG=true",
                 "-e", f"OPENSEARCH_JAVA_OPTS={OPENSEARCH_HEAP}",
                 "-e", "cluster.routing.allocation.disk.watermark.low=96%",
                 "-e", "cluster.routing.allocation.disk.watermark.high=97%",
                 "-e", "cluster.routing.allocation.disk.watermark.flood_stage=98%",
                 IMAGES[part]]
    else:
        # SeaweedFS's single-process mode with its S3 gateway on 8333; its admin identity
        # is the run's own keys, so an unsigned or wrongly signed request is refused.
        args += ["--mount", f"type=volume,src={name}-data,dst=/data",
                 "-e", "AWS_ACCESS_KEY_ID", "-e", "AWS_SECRET_ACCESS_KEY", IMAGES[part],
                 "mini", "-dir=/data"]
        environment.update(AWS_ACCESS_KEY_ID=secret["objectsUser"],
                           AWS_SECRET_ACCESS_KEY=secret["objectsPassword"])
    return args, environment


def start_data_plane(run_id: str, secret: dict) -> dict:
    states = {}
    for part in IMAGES:
        name = container_name(run_id, part)
        record = inspect(name)
        if record is None:
            args, environment = run_command(run_id, part, secret)
            docker(*args, environment=environment, seconds=300)
            states[part] = "created"
            continue
        require_owned(record, run_id)
        if not running(record):
            docker("start", name)
            states[part] = "started"
        else:
            states[part] = "running"
    return states


def _probe(url: str, seconds: float = 3) -> int | None:
    try:
        with urllib.request.urlopen(url, timeout=seconds) as answer:
            return answer.status
    except urllib.error.HTTPError as error:
        return error.code
    except (OSError, ValueError):
        return None


def wait_until(check, seconds: float, reason: str) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        with contextlib.suppress(Exception):
            if check():
                return
        time.sleep(1)
    raise V1Refused(reason)


def postgres_connect(secret: dict, *, autocommit: bool = True):
    import psycopg

    return psycopg.connect(host="127.0.0.1", port=PORTS["postgres"][0], dbname=DATABASE,
                           user=DATABASE_USER, password=secret["postgres"], connect_timeout=3,
                           autocommit=autocommit)


def redis_ping() -> bool:
    with socket.create_connection(("127.0.0.1", PORTS["redis"][0]), timeout=2) as stream:
        stream.sendall(b"PING\r\n")
        return stream.recv(16).startswith(b"+PONG")


def wait_data_plane(secret: dict, seconds: float) -> None:
    def postgres() -> bool:
        with postgres_connect(secret) as conn:
            return conn.execute("SELECT 1").fetchone() == (1,)

    wait_until(postgres, seconds, "v1's PostgreSQL did not answer")
    wait_until(redis_ping, seconds, "v1's Redis did not answer")
    wait_until(lambda: _probe(f"http://127.0.0.1:{PORTS['opensearch'][0]}/_cluster/health")
               == 200, seconds, "v1's OpenSearch did not answer")
    wait_until(lambda: _probe(f"http://127.0.0.1:{PORTS['objects'][0]}/healthz")
               == 200, seconds, "v1's object store did not answer")


def stop_data_plane(run_id: str) -> dict:
    states = {}
    for part in IMAGES:
        name = container_name(run_id, part)
        record = inspect(name)
        if record is None:
            states[part] = "absent"
            continue
        require_owned(record, run_id)
        if running(record):
            docker("stop", "--time", "10", name, seconds=30)
        states[part] = "stopped"
    return states


# --- v1's migrations and the synthetic data ------------------------------------------------


def migrate_v1(secret: dict) -> list[str]:
    """v1's own migrations: every file of v1's registry (`backend/migrations/registry.py`),
    in its order, each in its own transaction, recorded in v1's own ledger
    (`public._migrations_v2`) with its registry identity and digest, as v1's runner records
    them. v1's generic lane (`apply_migrations`) admits only scripts it can prove
    non-procedural and leaves `accounts:013_block_late_writes_during_purge.sql` to its
    protected runner; this synthetic database's only writer is the realm's tool, which
    applies the registry's bytes unchanged. A recorded file whose digest differs refuses."""
    import hashlib

    import psycopg

    from backend.migrations import _LEDGER
    from backend.migrations.registry import for_paths

    applied = []
    with psycopg.connect(host="127.0.0.1", port=PORTS["postgres"][0], dbname=DATABASE,
                         user=DATABASE_USER, password=secret["postgres"], connect_timeout=3,
                         autocommit=True,
                         options="-c statement_timeout=300000 -c lock_timeout=5000") as conn:
        conn.execute(_LEDGER)
        recorded = dict(conn.execute(
            "SELECT identity, definition_digest FROM public._migrations_v2").fetchall())
        for spec in for_paths(None):
            if spec.identity in recorded:
                if recorded[spec.identity] != spec.digest:
                    raise V1Refused("an applied v1 migration changed")
                continue
            payload = spec.path.read_bytes()
            if "sha256:" + hashlib.sha256(payload).hexdigest() != spec.digest:
                raise V1Refused("a v1 migration changed after planning")
            with conn.transaction():
                conn.execute(payload.decode("utf-8"), prepare=False)
                conn.execute(
                    "INSERT INTO public._migrations_v2(identity,definition_digest,assurance,"
                    "receipt) VALUES (%s,%s,'VERIFIED_EXECUTION',%s)",
                    (spec.identity, spec.digest, f"u8-realm:{spec.identity}"))
            applied.append(spec.identity)
    return applied


def s3_client(secret: dict):
    import boto3
    from botocore.config import Config

    return boto3.client("s3", endpoint_url=f"http://127.0.0.1:{PORTS['objects'][0]}",
                        aws_access_key_id=secret["objectsUser"],
                        aws_secret_access_key=secret["objectsPassword"],
                        region_name="ap-northeast-2",
                        config=Config(signature_version="s3v4", retries={"max_attempts": 2},
                                      connect_timeout=5, read_timeout=30))


def dataset_for(run_root: Path):
    """The realm's synthetic v1 dataset, with the realm's own password (`v1-password.json`,
    U8 plan Step 96(d)): the same value the fixtures phase records."""
    import u8_fixtures

    return u8_fixtures.v1_dataset(run_root)


def load_data(secret: dict, run_id: str, run_root: Path = RUN) -> dict:
    """The synthetic v1 data into v1's database, its search index and its bucket."""
    import httpx

    import u8_fixtures

    dataset = dataset_for(run_root)
    with postgres_connect(secret, autocommit=False) as conn:
        database = u8_fixtures.load_v1_database(conn, dataset)
        conn.commit()
    base = f"http://127.0.0.1:{PORTS['opensearch'][0]}"
    with httpx.Client(base_url=base, timeout=30, trust_env=False) as client:
        if client.head(f"/{u8_fixtures.INDEX}").status_code == 404:
            created = client.put(f"/{u8_fixtures.INDEX}", json={
                "settings": {"number_of_shards": 1, "number_of_replicas": 0}})
            if created.status_code not in (200, 201):
                raise V1Refused("v1's search index could not be created")
        for item in dataset.index_documents():
            answer = client.put(f"/{u8_fixtures.INDEX}/_doc/{item['chunkId']}", json=item)
            if answer.status_code not in (200, 201):
                raise V1Refused("v1's search index refused a document")
        client.post(f"/{u8_fixtures.INDEX}/_refresh")
    s3 = s3_client(secret)
    buckets = {item["Name"] for item in s3.list_buckets().get("Buckets", [])}
    if u8_fixtures.BUCKET not in buckets:
        s3.create_bucket(Bucket=u8_fixtures.BUCKET)
    # The document models and the bucket's extra objects (U8 plan Step 68(e)).
    objects = {**dataset.objects(), **dataset.bucket_extras()}
    for key, body in objects.items():
        s3.put_object(Bucket=u8_fixtures.BUCKET, Key=key, Body=body)
    record = u8_fixtures.dataset_record(dataset, run_id)
    write_private(STATE / "dataset.json", record)
    return {"database": database, "indexDocuments": len(dataset.index_documents()),
            "objects": len(objects), "digest": record["digest"]}


# --- the supervisor --------------------------------------------------------------------------


def wanted(label: str) -> dict | None:
    return read_private(SERVICES / f"{label}.json")


def set_wanted(label: str, state: str, operation: str) -> None:
    import datetime as dt

    write_private(SERVICES / f"{label}.json", {
        "label": label, "state": state, "operationId": operation,
        "at": dt.datetime.now(dt.UTC).isoformat()})


def acknowledged(label: str, operation: str) -> dict | None:
    value = read_private(SERVICES / f"{label}.ack.json")
    return value if value and value.get("operationId") == operation else None


def child_command(label: str, head: str) -> tuple[list[str], Path, dict]:
    from docsuri_ops.u8_platform.v1_environment import V1EnvironmentRefused, load

    try:
        # Only the file `wire_driver` wrote, checked again here; missing means no start.
        environment = load(STATE / "environment.json", run_root=RUN)
    except V1EnvironmentRefused as refused:
        raise V1Refused(str(refused)) from None
    if label == API_LABEL:
        from docsuri_ops.u8_platform.v1_environment import runtime_environment

        return ([str(PYTHON), "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1",
                 "--port", str(API_PORT), "--workers", "1", "--no-access-log"], ROOT,
                runtime_environment(environment, ROOT))
    standalone = worktree_for(head) / "frontend/.next/standalone"
    node = os.environ.get("DOCSURI_NODE_BIN") or str(
        Path.home() / ".nvm/versions/node/v24.14.0/bin/node")
    return ([node, "server.js"], standalone, process_environment({
        "PORT": str(WEB_PORT), "HOSTNAME": "127.0.0.1", "NODE_ENV": "production",
        "DOCSURI_GATEWAY_URL": f"http://127.0.0.1:{API_PORT}", "NEXT_TELEMETRY_DISABLED": "1"}))


class Supervisor:
    """v1's two named services, kept in the wanted state the realm driver writes."""

    def __init__(self, head: str, run_id: str):
        self.head, self.run_id = head, run_id
        self.children: dict[str, subprocess.Popen] = {}
        self.stopping = False

    def _log(self, label: str):
        path = STATE / f"{label.rsplit('.', 1)[-1]}.log"
        if path.exists() and path.stat().st_size > MAX_LOG:
            path.unlink()
        return private_log(path)

    def alive(self, label: str) -> bool:
        child = self.children.get(label)
        return child is not None and child.poll() is None

    def start(self, label: str) -> bool:
        argv, cwd, environment = child_command(label, self.head)
        with self._log(label) as log:
            self.children[label] = subprocess.Popen(argv, cwd=cwd, env=environment,
                                                    stdout=log, stderr=subprocess.STDOUT,
                                                    stdin=subprocess.DEVNULL,
                                                    start_new_session=True)
        health = API_HEALTH if label == API_LABEL else WEB_HEALTH
        deadline = time.monotonic() + START_SECONDS
        while time.monotonic() < deadline and self.alive(label):
            if _probe(health) == 200:
                return True
            time.sleep(0.5)
        return False

    def stop(self, label: str) -> bool:
        child = self.children.pop(label, None)
        if child is None or child.poll() is not None:
            return True
        with contextlib.suppress(ProcessLookupError):
            os.killpg(child.pid, signal.SIGTERM)
        try:
            child.wait(STOP_SECONDS)
        except subprocess.TimeoutExpired:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(child.pid, signal.SIGKILL)
            child.wait(5)
        return True

    def ack(self, label: str, value: dict, result: bool) -> None:
        import datetime as dt

        observed = "running" if self.alive(label) else "stopped"
        write_private(SERVICES / f"{label}.ack.json", {
            "label": label, "operationId": value.get("operationId"), "wanted": value["state"],
            "observed": observed, "result": "succeeded" if result and observed == value[
                "state"] else "failed", "at": dt.datetime.now(dt.UTC).isoformat()})

    def turn(self) -> None:
        for label in (API_LABEL, WEB_LABEL):
            value = wanted(label)
            if value is None:
                continue
            done = read_private(SERVICES / f"{label}.ack.json") or {}
            current = done.get("operationId") == value.get("operationId")
            if value["state"] == "running" and not self.alive(label):
                self.ack(label, value, self.start(label))
            elif value["state"] == "stopped" and self.alive(label):
                self.ack(label, value, self.stop(label))
            elif not current:
                self.ack(label, value, True)

    def run(self) -> None:
        def stopping(signum, frame):
            self.stopping = True

        signal.signal(signal.SIGTERM, stopping)
        signal.signal(signal.SIGINT, stopping)
        while not self.stopping and RUN.exists():
            self.turn()
            time.sleep(POLL_SECONDS)
        for label in list(self.children):
            self.stop(label)


def supervisor_pid() -> int | None:
    value = read_private(STATE / "supervisor.json")
    if not value:
        return None
    pid = int(value["pid"])
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return None
    return pid


def register_supervisor(run_id: str) -> None:
    """The realm driver waits for an acknowledgement only from a live, registered
    supervisor of a label's services folder."""
    for label in (API_LABEL, WEB_LABEL):
        write_private(SERVICES / "supervisors" / f"{label}.json",
                      {"pid": os.getpid(), "runId": run_id})
    write_private(STATE / "supervisor.json", {"pid": os.getpid(), "runId": run_id})


def start_supervisor(environment: Path) -> int:
    pid = supervisor_pid()
    if pid is not None:
        return pid
    with private_log(STATE / "supervisor.log") as log:
        process = subprocess.Popen(
            [str(PYTHON), str(Path(__file__).resolve()), "supervise", "--environment-file",
             str(environment)], cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL, start_new_session=True, env=process_environment({}))
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if supervisor_pid() == process.pid:
            return process.pid
        if process.poll() is not None:
            break
        time.sleep(0.2)
    raise V1Refused("the synthetic v1's supervisor did not start")


def wait_services(state: str, operation: str, seconds: float) -> dict:
    deadline = time.monotonic() + seconds
    results = {}
    for label in (API_LABEL, WEB_LABEL):
        while time.monotonic() < deadline:
            done = acknowledged(label, operation)
            if done is not None:
                results[label] = done["result"]
                break
            time.sleep(0.25)
        else:
            raise V1Refused(f"{label.rsplit('.', 1)[-1]} did not reach {state}")
    if any(result != "succeeded" for result in results.values()):
        raise V1Refused(f"a v1 service did not reach {state}")
    return results


# --- the realm driver's v1 wiring ------------------------------------------------------------


READER = "docsuri_v1_reader"
AGENT_V1_LOGIN = "v1-login"


def create_reader(secret: dict) -> None:
    """v1's read-only login for the backup agent's snapshot (`pg_read_all_data`), so the
    migration reads v1 without v1's own owner login (BR8.11)."""
    from psycopg import sql

    with postgres_connect(secret) as conn:
        exists = conn.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (READER,)).fetchone()
        verb = "ALTER" if exists else "CREATE"
        conn.execute(sql.SQL(verb + " ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE "
                             "CONNECTION LIMIT 3 PASSWORD {}").format(
            sql.Identifier(READER), sql.Literal(secret["reader"])))
        conn.execute(sql.SQL("GRANT pg_read_all_data TO {}").format(sql.Identifier(READER)))
        conn.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
            sql.Identifier(DATABASE), sql.Identifier(READER)))


def wire_agent(run_id: str, secret: dict) -> dict:
    """The realm's backup agent gains v1's database: its reader login (password file 0600
    in the agent's folder) and v1's own container, where the snapshot's dump runs."""
    import dataclasses

    from docsuri_ops.backup_agent.config import Login
    from docsuri_ops.backup_agent.config import load as load_agent
    from docsuri_ops.backup_agent.config import write as write_agent

    folder = RUN / "backup-agent"
    password = folder / AGENT_V1_LOGIN
    descriptor = os.open(password, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        stream.write(secret["reader"])
    config = load_agent(folder)
    write_agent(folder, dataclasses.replace(
        config, v1_database=DATABASE,
        v1_login=Login("127.0.0.1", PORTS["postgres"][0], READER, AGENT_V1_LOGIN),
        v1_container=container_name(run_id, "postgres")))
    return {"v1Database": DATABASE, "v1Container": container_name(run_id, "postgres")}


def wire_driver(secret: dict) -> None:
    """v1's fixed checkout, runtime and environment in the realm driver's configuration,
    for `platform.v1.lifecycle.apply` (BR9.13)."""
    driver = RUN / "platform" / "effects" / "driver.json"
    value = read_private(driver)
    if value is None:
        raise V1Refused("the realm driver is not configured; run migrate")
    environment = v1_environment(secret)
    require_realm_addresses(environment)
    write_private(STATE / "environment.json", environment)
    value.update(v1Checkout=str(ROOT), v1Runtime=[str(PYTHON)],
                 v1EnvironmentFile=str(STATE / "environment.json"))
    write_private(driver, value)


# --- the words ----------------------------------------------------------------------------------


def v1_up(environment: Path) -> dict:
    deadline = time.monotonic() + UP_SECONDS
    value = run_identity(environment)
    run_id = value["runId"]
    private_folder(STATE)
    head = commit()
    resources = preflight(run_id)
    web = build_web(head, seconds=max(1.0, deadline - time.monotonic()))
    secret = credentials(run_id)
    containers = start_data_plane(run_id, secret)
    wait_data_plane(secret, max(1.0, deadline - time.monotonic()))
    applied = migrate_v1(secret)
    data = load_data(secret, run_id)
    create_reader(secret)
    agent = wire_agent(run_id, secret)
    wire_driver(secret)
    pid = start_supervisor(environment)
    operation = f"v1-up:{time.time_ns()}"
    for label in (API_LABEL, WEB_LABEL):
        set_wanted(label, "running", operation)
    services = wait_services("running", operation, max(1.0, deadline - time.monotonic()))
    write_private(STATE / "state.json", {"runId": run_id, "commit": head,
                                         "worktree": web["worktree"], "supervisor": pid})
    return {"state": "v1-up", "commit": head, "web": web, "resources": resources,
            "containers": containers, "migrationsApplied": len(applied), "data": data,
            "agent": agent,
            "services": services, "seconds": round(UP_SECONDS - (deadline - time.monotonic()))}


def v1_down(environment: Path) -> dict:
    value = run_identity(environment, allow_expired=True)
    run_id = value["runId"]
    services = {}
    pid = supervisor_pid()
    if pid is not None:
        operation = f"v1-down:{time.time_ns()}"
        for label in (API_LABEL, WEB_LABEL):
            set_wanted(label, "stopped", operation)
        services = wait_services("stopped", operation, START_SECONDS)
        os.kill(pid, signal.SIGTERM)
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline and supervisor_pid() is not None:
            time.sleep(0.2)
        if supervisor_pid() is not None:
            raise V1Refused("the synthetic v1's supervisor did not stop")
    for label in (API_LABEL, WEB_LABEL):
        (SERVICES / "supervisors" / f"{label}.json").unlink(missing_ok=True)
    (STATE / "supervisor.json").unlink(missing_ok=True)
    for port in (API_PORT, WEB_PORT):
        with socket.socket() as probe:
            if probe.connect_ex(("127.0.0.1", port)) == 0:
                raise V1Refused("a v1 listener still answers after its stop")
    containers = stop_data_plane(run_id)
    return {"state": "v1-down", "services": services, "containers": containers}


def supervise(environment: Path) -> int:
    value = run_identity(environment)
    state = read_private(STATE / "state.json") or {}
    head = state.get("commit") or commit()
    register_supervisor(value["runId"])
    Supervisor(head, value["runId"]).run()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="u8_synthetic_v1.py")
    parser.add_argument("word", choices=("v1-up", "v1-down", "supervise", "build-web",
                                         "remove-web"))
    parser.add_argument("--environment-file", required=True, type=Path)
    args = parser.parse_args(argv)
    environment = args.environment_file.resolve()
    try:
        if args.word == "v1-up":
            result = v1_up(environment)
        elif args.word == "v1-down":
            result = v1_down(environment)
        elif args.word == "supervise":
            return supervise(environment)
        elif args.word == "build-web":
            run_identity(environment)
            private_folder(STATE)
            result = build_web(commit(), seconds=UP_SECONDS)
        else:
            run_identity(environment)
            result = remove_web(commit())
    except (V1Refused, ValueError, OSError, subprocess.SubprocessError) as error:
        reason = str(error) if isinstance(error, V1Refused) else type(error).__name__
        print(json.dumps({"state": "refused", "reason": reason}))
        return 1
    print(json.dumps(result, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
