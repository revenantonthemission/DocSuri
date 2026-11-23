"""Step 21: U5's mounted surface is pinned to its listed routes, process and folders.

U5 joins the one assembled release (backend/u5_host.py): it deploys no separate
service, worker fleet or store and adds no infrastructure or deployment surface
(logical-components, one failure domain). Here the release U5's runner serves
(scripts/serve_docsuri_u5.py) is compared with the same realm's release assembled with
an empty topics contribution, which passes the same realm and owner gates:

- routes: U5 adds exactly the eleven listed routes, each answered by U5's own handlers
  ahead of the static fallback, and takes no inherited route away;
- service: U5 adds no middleware and no lifespan of its own, only its two state entries
  and its one capability row;
- process: U5's components run on the host's own owner transactions, as the host
  process's role under the topics login, and its digest pass is one more step of the
  shared worker pass; assembling it starts no thread or process the inherited release
  does not start;
- port: the served host listens on the realm's one application port only;
- store: the realm keeps one application database, with U5's one schema in it;
- folders: driving U5's routes, a digest delivery and its email unsubscribe leaves the
  realm's folders and files exactly as they were, and U5's own modules name no realm
  file other than the two listed and open no file, socket, thread or process.
"""

import ast
import datetime as dt
import json
import os
import re
import secrets
import subprocess
import sys
import threading
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlsplit
from uuid import UUID, uuid4

import pytest
import scripts.serve_docsuri_u5 as serve
from backend.local_profile import private_bytes
from backend.u3_host import U3ControlWorker
from backend.u4_host import ResearchWorker, assemble_u4
from backend.u5_host import TopicsWorker
from docsuri_ops.local_transport import inspect_transport
from fastapi import APIRouter
from fastapi.testclient import TestClient
from starlette.routing import Match

from tests.u5_topics_digests.realm_catalog import admin_connection

ROOT = Path(__file__).resolve().parents[3]

# The routes U5 mounts in its realm: the topics router, the email unsubscribe router
# (the synthetic realm always issues the cancellation capability) and the C03 settings
# router the earlier assemblies do not mount.
U5_ROUTES = frozenset(
    {
        ("GET", "/api/v2/topics"),
        ("POST", "/api/v2/topics"),
        ("DELETE", "/api/v2/topics/{topic_id}"),
        ("GET", "/api/v2/topics/{topic_id}/settings"),
        ("PUT", "/api/v2/topics/{topic_id}/settings"),
        ("POST", "/api/v2/topics/{topic_id}/runs/{run_id}/resolve"),
        ("GET", "/api/v2/topics/email-unsubscribe/{token}"),
        ("POST", "/api/v2/topics/email-unsubscribe/{token}"),
        ("POST", "/api/v2/c03/settings-read"),
        ("POST", "/api/v2/c03/settings-update"),
        ("POST", "/api/v2/c03/settings-update-onboarding"),
    }
)
U5_HANDLERS = frozenset(
    {
        "backend.modules.topics.http",
        "backend.modules.topics.unsubscribe",
        "backend.modules.personalization.local_http",
    }
)
STATIC_FALLBACK = ("GET", "/{path:path}")
APPLICATION_PORT, DATABASE_PORT = 18089, 15489
# The owners' schemas in the realm's one application database; U5's is `topics`.
SCHEMAS = frozenset(
    {
        "accounts",
        "assistance",
        "corpus",
        "discovery",
        "library",
        "operations",
        "personalization",
        "public",
        "research",
        "topics",
        "usage",
    }
)
# U5's own production modules (the shared files it changed belong to their owners).
OWN_MODULES = (
    *sorted((ROOT / "backend/modules/topics").glob("*.py")),
    ROOT / "backend/modules/accounts/integrations/digest_email.py",
    ROOT / "backend/u5_host.py",
    ROOT / "backend/u5_policy.py",
    ROOT / "backend/u5_real_delivery.py",
)
# Modules that would bring a listener, a process, a thread, a background loop or a
# store of U5's own. httpx stays allowed: it is the built email path's client.
SURFACE_MODULES = frozenset(
    {
        "concurrent",
        "dbm",
        "gunicorn",
        "http",
        "multiprocessing",
        "pickle",
        "sched",
        "selectors",
        "shelve",
        "shutil",
        "signal",
        "socket",
        "socketserver",
        "sqlite3",
        "ssl",
        "subprocess",
        "tempfile",
        "threading",
        "uvicorn",
        "xmlrpc",
    }
)
FILE_CALLS = frozenset(
    {
        "chmod",
        "glob",
        "iterdir",
        "makedirs",
        "mkdir",
        "open",
        "private_bytes",
        "private_json",
        "read_bytes",
        "read_text",
        "remove",
        "rename",
        "replace",
        "rmdir",
        "rmtree",
        "touch",
        "unlink",
        "write_bytes",
        "write_text",
    }
)


def empty_topics(transactions, entry, corpus, inherited_worker):
    """The same release with nothing contributed: an empty router, no capability row,
    the inherited worker unchanged. The realm and owner gates still apply in full."""
    return {
        "service": None,
        "scheduler": None,
        "capabilities": [],
        "router": APIRouter(),
        "worker": inherited_worker,
    }


def child_processes() -> set[int]:
    """This process's children, without the `ps` that lists them."""
    listing = subprocess.run(
        ["ps", "-Ao", "pid=,ppid=,comm="], capture_output=True, text=True, check=True, timeout=5
    ).stdout
    me = os.getpid()
    children = set()
    for line in listing.splitlines():
        fields = line.split(None, 2)
        if len(fields) == 3 and int(fields[1]) == me and Path(fields[2]).name != "ps":
            children.add(int(fields[0]))
    return children


def thread_families(threads) -> Counter:
    """Thread names with their counters removed: `pool-7-worker-2` is `pool-#-worker-#`."""
    return Counter(re.sub(r"\d+", "#", thread.name) for thread in threads)


def assembled(assemble):
    """One assembly, with the threads and child processes it started."""
    threads, children = set(threading.enumerate()), child_processes()
    app = assemble()
    started = {thread for thread in threading.enumerate() if thread not in threads}
    return app, started, child_processes() - children


@pytest.fixture(scope="module")
def releases(realm):
    baseline, baseline_threads, baseline_children = assembled(
        lambda: assemble_u4(realm, topics_factory=empty_topics)
    )
    try:
        served, served_threads, served_children = assembled(
            lambda: serve.assemble(realm.root / "environment.json")[0]
        )
    except BaseException:
        baseline.state.transactions.close()
        raise
    yield SimpleNamespace(
        baseline=baseline,
        served=served,
        threads=(baseline_threads, served_threads),
        children=(baseline_children, served_children),
    )
    served.state.transactions.close()
    baseline.state.transactions.close()


def flat_routes(routes) -> list:
    """The concrete routes in matching order. FastAPI keeps an included router as one
    entry (`original_router`), opened here in place; every U5 and inherited router names
    its full paths, so a prefixed include is refused rather than guessed at."""
    found = []
    for route in routes:
        inner = getattr(route, "original_router", None)
        if inner is None:
            found.append(route)
            continue
        assert getattr(route.include_context, "prefix", "") in ("", None)
        found += flat_routes(inner.routes)
    return found


def surface(app) -> list[tuple[str, str]]:
    """Every (method, path) the application routes, in matching order."""
    found = []
    for route in flat_routes(app.routes):
        methods = getattr(route, "methods", None) or {type(route).__name__}
        found.extend((method, route.path) for method in sorted(methods) if method != "HEAD")
    return found


def answering_route(app, method: str, path: str):
    """The route the router dispatches a request to: the first full match."""
    scope = {
        "type": "http",
        "method": method,
        "path": path,
        "root_path": "",
        "query_string": b"",
        "headers": [],
    }
    for route in flat_routes(app.routes):
        match, _ = route.matches(scope)
        if match is Match.FULL:
            return route
    return None


def concrete(path: str) -> str:
    return (
        path.replace("{topic_id}", str(uuid4()))
        .replace("{run_id}", str(uuid4()))
        .replace("{token}", "x" * 43)
    )


def test_u5_adds_exactly_its_listed_routes_answered_by_its_own_handlers(releases):
    baseline, served = surface(releases.baseline), surface(releases.served)
    # U5 adds the listed routes, each once, and takes no inherited route away.
    assert Counter(served) - Counter(baseline) == Counter(U5_ROUTES)
    assert Counter(baseline) - Counter(served) == Counter()
    # The static fallback stays the last route of both releases.
    assert baseline[-1] == served[-1] == STATIC_FALLBACK
    for method, path in sorted(U5_ROUTES):
        request = concrete(path)
        route = answering_route(releases.served, method, request)
        # U5's own handler for that route answers, ahead of the fallback...
        assert route is not None and route.path == path, (method, path)
        assert route.endpoint.__module__ in U5_HANDLERS, (method, path)
        # ...and without U5 nothing but the fallback (or no route) would.
        inherited = answering_route(releases.baseline, method, request)
        assert inherited is None or (method, inherited.path) == STATIC_FALLBACK, (method, path)


def test_u5_adds_no_middleware_or_lifespan_and_only_its_two_state_entries(releases):
    baseline, served = releases.baseline, releases.served

    def stack(app):
        return [
            (
                item.cls.__qualname__,
                getattr(item.kwargs.get("dispatch"), "__qualname__", None),
                tuple(sorted(item.kwargs)),
            )
            for item in app.user_middleware
        ]

    assert stack(served) == stack(baseline) and stack(served)
    lifespans = {app.router.lifespan_context.__qualname__ for app in (served, baseline)}
    assert len(lifespans) == 1
    # The same state entries; only U5's two are filled, by its service and scheduler.
    assert set(served.state._state) == set(baseline.state._state)
    assert baseline.state.topics is None and baseline.state.topics_scheduler is None
    assert type(served.state.topics).__name__ == "TopicsService"
    assert type(served.state.topics_scheduler).__name__ == "TopicsScheduler"
    # One capability row more, and it is U5's.
    rows = Counter(row["id"] for row in served.state.capability_catalog)
    rows.subtract(Counter(row["id"] for row in baseline.state.capability_catalog))
    assert +rows == Counter({"topics.digest": 1})


def test_u5_runs_on_the_host_transactions_inside_the_shared_worker_pass(releases):
    served = releases.served
    host = served.state.transactions
    scheduler = served.state.topics_scheduler
    delivery = scheduler.delivery
    # Every U5 component works through the host's one set of owner transactions.
    for repository in (
        served.state.topics.repository,
        scheduler.repository,
        scheduler.preparation.repository,
        delivery.repository,
    ):
        assert repository.transactions is host
    assert delivery.unsubscribe.transactions is host
    # Its database session is the host process's role under the topics login.
    session = scheduler.repository.system(
        lambda conn: conn.execute(
            "SELECT current_user AS login, current_setting('application_name') AS process"
        ).fetchone()
    )
    assert session == {"login": "docsuri_topics", "process": "docsuri-topics-digests-api-topics"}

    # The digest pass is one more step of the one worker pass, not a worker of its own.
    def chain(worker):
        kinds = []
        while worker is not None:
            kinds.append(type(worker))
            worker = getattr(worker, "inherited", None)
        return kinds

    assert chain(releases.baseline.state.control_worker) == [ResearchWorker, U3ControlWorker]
    assert chain(served.state.control_worker) == [TopicsWorker, ResearchWorker, U3ControlWorker]
    assert served.state.control_worker.scheduler is scheduler


def test_assembling_u5_starts_no_thread_or_process_the_inherited_release_does_not(releases):
    baseline_threads, served_threads = releases.threads
    # The owner transactions' pool threads, the same for both releases; nothing else.
    assert thread_families(served_threads) == thread_families(baseline_threads)
    assert thread_families(served_threads) and set(thread_families(served_threads)) == {
        "pool-#-scheduler",
        "pool-#-worker-#",
    }
    assert releases.children == (set(), set())


def test_the_served_host_listens_on_the_realm_application_port_only(realm, monkeypatch):
    calls = []

    def run(app, **options):
        calls.append(options)
        app.state.transactions.close()

    monkeypatch.setattr(serve, "uvicorn", SimpleNamespace(run=run))
    monkeypatch.setattr(
        sys,
        "argv",
        ["serve_docsuri_u5.py", "--environment-file", str(realm.root / "environment.json")],
    )
    serve.main()
    assert len(calls) == 1
    options = calls[0]
    origin = urlsplit(realm.origin)
    # One TCP listener on the realm's loopback application port, one worker process.
    listener = (options["host"], options["port"], options["workers"])
    assert listener == (origin.hostname, origin.port, 1)
    assert listener == ("127.0.0.1", APPLICATION_PORT, 1)
    assert "uds" not in options and "fd" not in options
    transport = inspect_transport(realm)
    assert (options["ssl_certfile"], options["ssl_keyfile"]) == (
        str(transport.certificate),
        str(transport.key),
    )
    # The realm's manifest names exactly the application port and the database port.
    manifest = json.loads(private_bytes(realm.root / "environment.json"))
    ports = {key: value for key, value in manifest.items() if key.lower().endswith("port")}
    assert ports == {"applicationPort": APPLICATION_PORT, "databasePort": DATABASE_PORT}
    assert realm.database_port == DATABASE_PORT


def test_the_realm_keeps_one_application_database_with_one_u5_schema(realm):
    with admin_connection(realm) as conn:
        databases = {
            row["datname"]
            for row in conn.execute(
                "SELECT datname FROM pg_database WHERE NOT datistemplate"
            ).fetchall()
        }
        owners = {
            row["nspname"]: row["owner"]
            for row in conn.execute(
                "SELECT n.nspname, r.rolname AS owner FROM pg_namespace n "
                "JOIN pg_roles r ON r.oid=n.nspowner "
                "WHERE n.nspname !~ '^pg_' AND n.nspname <> 'information_schema'"
            ).fetchall()
        }
    # A scratch database (realm_catalog.scratch_database) is a test's own, always dropped.
    applications = {name for name in databases if not name.startswith("docsuri_u5_scratch_")}
    assert applications == {"postgres", realm.database_name}
    # The owners' schemas and no other; U5's `topics` is owned by its own owner role.
    assert set(owners) == SCHEMAS
    assert {name: role for name, role in owners.items() if name != "public"} == {
        name: f"docsuri_{name}_owner" for name in SCHEMAS - {"public"}
    }


def tree(root: Path) -> set[tuple[str, str]]:
    """Each entry under the realm root as (relative path, kind); no content is read."""
    entries = set()
    for path in root.rglob("*"):
        kind = "link" if path.is_symlink() else "folder" if path.is_dir() else "file"
        entries.add((path.relative_to(root).as_posix(), kind))
    return entries


def authorize(app, authority):
    """Bind a fresh browser credential to the fixture's existing session."""
    token = secrets.token_hex(32)
    csrf = app.state.entry.verifier("session-csrf", token)
    app.state.transactions.run(
        "accounts",
        lambda conn: conn.execute(
            "UPDATE accounts.session SET token_hash=%s,csrf_hash=%s WHERE id=%s AND account_id=%s",
            (
                app.state.entry.verifier("session", token),
                app.state.entry.verifier("csrf", csrf),
                authority.session_id,
                authority.account_id,
            ),
        ),
    )
    return token, csrf


def keyed(client, method, path, body=None):
    return client.request(method, path, json=body, headers={"Idempotency-Key": str(uuid4())})


def test_driving_u5_leaves_the_realm_folders_and_files_unchanged(realm, releases, authority):
    app = releases.served
    token, csrf = authorize(app, authority)
    # Admission opens only on a genuine capacity observation; take one.
    app.state.control_capacity.refresh()
    before = tree(realm.root)
    client = TestClient(app, base_url=realm.origin)
    client.cookies.set("session_id", token)
    client.headers.update({"Origin": realm.origin, "X-CSRF-Token": csrf})
    try:
        followed = keyed(
            client,
            "POST",
            "/api/v2/topics",
            {"topicKey": f"surface-{uuid4().hex[:10]}", "displayName": "표면 확인"},
        )
        assert followed.status_code == 200, followed.text
        topic_id = followed.json()["topicId"]
        assert client.get("/api/v2/topics").status_code == 200
        view = client.get(f"/api/v2/topics/{topic_id}/settings")
        assert view.status_code == 200, view.text
        saved = keyed(
            client,
            "PUT",
            f"/api/v2/topics/{topic_id}/settings",
            {
                "revision": view.json()["settings"]["revision"],
                "cadence": "daily",
                "deliveryTimeLocal": "00:00",
                "deliveryDay": None,
                "contentWindowDays": 7,
            },
        )
        assert saved.status_code == 200, saved.text
        assert keyed(client, "POST", "/api/v2/c03/settings-read", {}).status_code == 200

        # One digest of the eligible fixture papers, prepared and sent through the
        # realm's local sink by the release's own preparation and delivery.
        scheduler = app.state.topics_scheduler
        today = dt.datetime.now(dt.UTC).date()  # the fixture owner's zone is UTC
        run, adopted = scheduler.preparation.prepare(
            UUID(topic_id),
            (today - dt.timedelta(days=6), today),
            saved.json()["settings"]["revision"],
        )
        assert not adopted and run["state"] == "prepared"
        sending = scheduler.repository.begin_send(run["id"], scheduler.delivery.path_kind())
        assert sending is not None and scheduler.delivery.path_kind() == "local-sink"
        # The cancellation capability an email carries is bound while its run is sending.
        cancel = urlsplit(scheduler.delivery.unsubscribe.issue(run["id"])).path
        outcome = scheduler.delivery.attempt(sending, {"account_id": authority.account_id})
        assert outcome["state"] == "sent"
        resolve = keyed(
            client,
            "POST",
            f"/api/v2/topics/{topic_id}/runs/{run['id']}/resolve",
            {"decision": "delivered", "assumption": "보낸 메일이 도착했다고 가정합니다"},
        )
        assert 400 <= resolve.status_code < 500  # a sent run has nothing to resolve

        # The email's one-click unsubscribe, through the cookie-free routes.
        assert client.get(cancel).status_code == 200
        cancelled = client.post(cancel, data={"List-Unsubscribe": "One-Click"})
        assert cancelled.status_code == 200, cancelled.text
        removed = keyed(client, "DELETE", f"/api/v2/topics/{topic_id}")
        assert removed.status_code == 200, removed.text
        assert removed.json()["status"] == "unsubscribed"
    finally:
        client.close()
    assert tree(realm.root) == before


def own_source_uses(path: Path) -> dict:
    """The imports, file calls and realm-root file names one module's source names."""
    module = ast.parse(path.read_text(), str(path))
    uses = {"imports": set(), "calls": set(), "realm": set(), "os": set(), "asyncio": set()}
    for node in ast.walk(module):
        if isinstance(node, ast.Import):
            uses["imports"] |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            uses["imports"].add(node.module.split(".")[0])
        elif isinstance(node, ast.Call):
            function = node.func
            name = getattr(function, "id", None) or getattr(function, "attr", None)
            if name in FILE_CALLS:
                uses["calls"].add(name)
        elif isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            if node.value.id in ("os", "asyncio"):
                uses[node.value.id].add(node.attr)
        elif (
            isinstance(node, ast.BinOp)
            and isinstance(node.op, ast.Div)
            and isinstance(node.left, ast.Attribute)
            and node.left.attr == "root"
        ):
            right = node.right
            named = right.value if isinstance(right, ast.Constant) else ast.unparse(right)
            uses["realm"].add(named)
    return uses


def test_u5_modules_name_only_the_listed_realm_files_and_open_no_surface():
    names = {path.relative_to(ROOT).as_posix() for path in OWN_MODULES}
    assert {
        "backend/modules/topics/scheduler.py",
        "backend/modules/topics/delivery.py",
        "backend/u5_host.py",
        "backend/u5_real_delivery.py",
    } <= names
    found = {path.relative_to(ROOT).as_posix(): own_source_uses(path) for path in OWN_MODULES}
    surfaces = {name: sorted(uses["imports"] & SURFACE_MODULES) for name, uses in found.items()}
    assert {name: listed for name, listed in surfaces.items() if listed} == {}
    # The only file access: reading the two listed realm files through private_bytes.
    calls = {name: sorted(uses["calls"]) for name, uses in found.items() if uses["calls"]}
    assert calls == {
        "backend/u5_host.py": ["private_bytes"],
        "backend/u5_real_delivery.py": ["private_bytes"],
    }
    realm_files = {name: sorted(uses["realm"]) for name, uses in found.items() if uses["realm"]}
    assert realm_files == {
        "backend/u5_host.py": ["digest-fixture-clock.json"],
        "backend/u5_real_delivery.py": ["ACTIVATION_FILE"],
    }
    from backend.u5_real_delivery import ACTIVATION_FILE

    assert ACTIVATION_FILE == "real-delivery.json"
    # The process environment is read (the provider key); no process is forked or run.
    assert set().union(*(uses["os"] for uses in found.values())) <= {"environ"}
    # A send waits on the calling thread; no task, thread or listener is started.
    assert set().union(*(uses["asyncio"] for uses in found.values())) <= {"run", "wait_for"}
