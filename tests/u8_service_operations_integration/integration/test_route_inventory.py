"""The complete assembly's route inventory (U8 plan Step 40; security-design § 3.6, NFR1.1).

`host_app` mounts every owner's routes in one application. Each route must be on the
public list, a token route, or behind its owner's guard, and has a route class; a route
that is neither, or has no class, fails the assembly check. A signed-out caller reaches
no private route, event stream or asset, and another owner's identifiers behave exactly
as missing ones.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import APIRouter

from backend.u8_routes import (
    PUBLIC_ROUTES,
    TOKEN_ROUTES,
    access_of,
    check_routes,
    flat_routes,
    route_class,
)
from tests.u8_service_operations_integration.host_flows import (
    OTHER_MEMBER,
    call,
    complete_host,
    fresh_client,
    make_jobs,
    member,
    session_of,
)

SCRIPTS = str(Path(__file__).resolve().parents[3] / "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)
pytestmark = pytest.mark.usefixtures("own_address")
# Owner-guarded routes whose owner admits a caller with no session: navigation, the
# capability projection, search and public reading (the owners' own access rules).
ANONYMOUS_PERMITTED = {
    "/api/v2/c01/host-resolve-navigation", "/api/v2/capabilities", "/api/v2/c05/search",
    "/api/v2/c05/read-citations", "/api/v2/c04/resolve-paper", "/api/v2/c04/read-content",
    "/api/v2/c04/read-asset",
}
REFUSAL_KEYS = {"code", "requestId", "retryable", "messageKey"}


@pytest.fixture
def host(realm, own_address):
    with complete_host(realm, address=own_address) as value:
        yield value


def test_every_route_is_public_token_or_guarded_and_classed(host):
    inventory = host.app.state.route_inventory
    assert len(inventory) > 100
    for (method, path), (klass, access) in inventory.items():
        assert klass == route_class(method, path)
        if access == "public":
            assert (method, path) in PUBLIC_ROUTES
        elif access == "token":
            assert (method, path) in TOKEN_ROUTES
        else:
            assert access == "guarded" and path.startswith("/api/v2/"), (method, path)
    # Every owner's surface is mounted, and each route once.
    for path in ("/api/v2/c02/access-login", "/api/v2/c02/access-read-profile",
                 "/api/v2/c03/library-list-saved-papers", "/api/v2/c03/settings-read",
                 "/api/v2/c03/usage-inspect", "/api/v2/c04/read-content", "/api/v2/c05/search",
                 "/api/v2/c06/accept-assistance", "/api/v2/c07/list-research-jobs",
                 "/api/v2/c09/list-export-history", "/api/v2/c11/read-dashboard",
                 "/api/v2/c01/host-resolve-navigation"):
        assert ("POST", path) in inventory, path
    for path in ("/privacy", "/terms", "/sign-in/callback/{provider}", "/api/v2/topics",
                 "/api/v2/jobs/{job_id}/events", "/api/v2/identity/callback/{provider}"):
        assert ("GET", path) in inventory, path
    paths = [(m, r.path) for r in flat_routes(host.app.router.routes)
             for m in (getattr(r, "methods", None) or ()) if m != "HEAD"]
    assert len(paths) == len(set(paths))


def test_production_without_account_controls_serves_no_session_or_owner_route(realm):
    """Your decision of 2026-10-24: with AccountAccess's controls missing, production
    mounts only the static pages and the public capability projection, and readiness
    names `account.controls`."""
    import asyncio

    import httpx

    from backend.u8_host import BUILDERS, host_app
    from tests.u8_service_operations_integration.host_flows import production_composition

    async def ask(app, method, path):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                     base_url="https://docsuri.rvnnt.dev") as http:
            return await http.request(method, path, json={} if method == "POST" else None)

    builders = {key: value for key, value in BUILDERS.items() if key != "account-controls"}
    with production_composition(realm, builders=builders) as env:
        app = host_app(env.composition)
        inventory = app.state.route_inventory
        assert not any(path.startswith(("/api/v2/c0", "/api/v2/c1", "/api/v2/session"))
                       for _, path in inventory)
        # No route serves them: the host answers an unmounted API path as not ready.
        for method, path in (("GET", "/api/v2/session"), ("POST", "/api/v2/c02/access-login")):
            answer = asyncio.run(ask(app, method, path))
            assert answer.status_code == 503 and answer.json()["code"] == "NOT_READY", path
        assert asyncio.run(ask(app, "GET", "/api/v2/capabilities")).status_code == 200
        assert "account.controls" in env.composition.readiness()["missing"]


def test_a_route_that_is_neither_public_nor_guarded_fails_the_assembly_check(host):
    from backend.request_context import RouteClasses

    stray = APIRouter()

    @stray.post("/api/v2/c99/stray")
    async def unguarded():
        return {}

    classes = RouteClasses()
    classes.register("/api/v2/c99/stray", "read", methods=("POST",))
    [route] = stray.routes
    assert access_of(route, "POST") is None
    with pytest.raises(ValueError, match="neither public nor guarded"):
        check_routes(stray.routes, classes)
    with pytest.raises(ValueError, match="without a route class"):
        check_routes(stray.routes, RouteClasses())
    # A guarded-looking path outside the shared boundary is not guarded either.
    plain = APIRouter()

    @plain.post("/api/v2/c03/library-list-saved-papers")
    async def lookalike():
        return {}

    classes.register("/api/v2/c03/library-list-saved-papers", "read", methods=("POST",))
    with pytest.raises(ValueError, match="neither public nor guarded"):
        check_routes(plain.routes, classes)


def test_the_realms_server_serves_its_own_realm_and_wires_the_identity_standin(host):
    import dataclasses

    import serve_docsuri_u8 as serve
    from backend.modules.accounts.integrations.identity_providers import (
        GoogleIdentityProvider,
        OrcidIdentityProvider,
    )
    from u8_identity_standin import IdentityStandin, RecordedAnswers

    realm = host.composition.profile
    serve.require_realm(realm)
    for other in (dataclasses.replace(realm, realm="approved-export"),
                  SimpleNamespace(is_production=True, realm=realm.realm,
                                  database_name=realm.database_name)):
        with pytest.raises(ValueError):
            serve.require_realm(other)
    answers = RecordedAnswers(IdentityStandin(realm))
    controls = host.composition.parts["account-controls"]
    serve.prepare_with(answers)(host.composition)
    providers = controls["entry"].identity_providers
    assert isinstance(providers["google"], GoogleIdentityProvider)
    assert isinstance(providers["orcid"], OrcidIdentityProvider)
    serve.prepare_with(answers)(SimpleNamespace(parts={}, profile=realm))  # no controls
    roles = [argv[2:4] for argv in serve.children(realm.root / "environment.json")[:2]]
    assert roles == [["backend.u8_main", "workers"], ["backend.u8_main", "scheduler"]]
    assert any("u8_tunnel_standin.py" in " ".join(argv)
               for argv in serve.children(realm.root / "environment.json"))


def test_the_served_realm_names_the_standin_clients_only_while_it_is_served(host):
    import json

    import serve_docsuri_u8 as serve
    from backend.u8_host import PROVIDER_ENVIRONMENT, provider_secrets

    realm = host.composition.profile
    path = realm.root / PROVIDER_ENVIRONMENT
    # One an earlier serve left behind when it was stopped before its end is its own:
    # the next serve's end removes it.
    with serve.standin_clients(realm):
        pass
    assert not path.exists()
    with serve.standin_clients(realm):
        assert path.stat().st_mode & 0o777 == 0o600
        assert set(json.loads(path.read_text())) == {"googleClientSecret", "orcidClientSecret"}
        # Google and ORCID count configured; Resend stays unconfigured, so no mail leaves.
        assert provider_secrets(realm) == {"provider.google": "configured",
                                           "provider.orcid": "configured",
                                           "provider.resend": "unconfigured"}
    assert not path.exists()
    # A file already present is the operator's own, left as it is.
    path.write_text("{}")
    path.chmod(0o600)
    try:
        with serve.standin_clients(realm):
            assert path.read_text() == "{}"
        assert path.read_text() == "{}"
    finally:
        path.unlink()


def test_a_signed_out_caller_reaches_no_private_route_stream_or_asset(host):
    inventory = host.app.state.route_inventory
    client = host.client
    refused = 0
    for (method, path), (_, access) in sorted(inventory.items()):
        if access != "guarded" or path in ANONYMOUS_PERMITTED:
            continue
        concrete = path.replace("{job_id}", str(uuid4())).replace(
            "{topic_id}", str(uuid4())).replace("{run_id}", str(uuid4())).replace(
            "{provider}", "orcid")
        if method == "GET":
            answer = client.get(concrete)
        elif method == "POST":
            answer = call(client, concrete, {})
        else:
            answer = client.request(method, concrete, json={})
        assert answer.status_code in (400, 401, 403, 404, 422), (method, path, answer.text)
        assert set(answer.json()) <= REFUSAL_KEYS, (method, path)
        refused += 1
    assert refused > 60


def test_another_owners_identifiers_behave_as_missing(host, sign_in_account, connect):
    owner, _ = member(host, sign_in_account)
    jobs = make_jobs(connect, owner.account_id, session_of(connect, owner.account_id),
                     ("research-turn", "novelty-analysis"))
    own = call(host.client, "/api/v2/c07/list-research-jobs", {"limit": 50})
    assert own.status_code == 200, own.text
    assert {str(job) for job in jobs} <= {item["jobId"] for item in own.json()["items"]}
    with fresh_client(host, address="198.18.250.7") as other_client:
        member(SimpleNamespace(client=other_client), sign_in_account, OTHER_MEMBER)
        listed = call(other_client, "/api/v2/c07/list-research-jobs", {"limit": 50})
        assert listed.status_code == 200
        assert not {str(job) for job in jobs} & {item["jobId"] for item in listed.json()["items"]}
        for target in (str(jobs[0]), str(uuid4())):
            answers = [
                other_client.get(f"/api/v2/jobs/{target}"),
                other_client.get(f"/api/v2/jobs/{target}/events"),
                other_client.get(f"/api/v2/jobs/{target}/result"),
                call(other_client, "/api/v2/c07/read-research-job",
                     {"jobId": target, "contextId": str(uuid4()), "kind": "research-turn"}),
            ]
            shape = [(answer.status_code, answer.json().get("code")) for answer in answers]
            if target == str(jobs[0]):
                foreign = shape
            else:
                assert shape == foreign
        assert all(status in (403, 404, 422) for status, _ in foreign)


# --- record 102: every request recorded under its own route's class (Step 130; L2-2) ------


def test_each_routes_own_request_is_recorded_under_its_class(host):
    from backend.u8_routes import sample_path

    classes = host.app.boundary.context.classes
    inventory = host.app.state.route_inventory
    recorded = {key: classes.classify(key[0], sample_path(key[1])) for key in inventory}
    assert recorded == {key: klass for key, (klass, _) in inventory.items()}
    expected = {
        ("GET", "/api/v2/session"): "read",
        ("GET", "/api/v2/jobs/{job_id}"): "read",
        ("GET", "/api/v2/topics"): "read",
        ("GET", "/api/v2/identity/callback/{provider}"): "read",
        ("GET", "/api/v2/jobs/{job_id}/events"): "stream",
        ("GET", "/api/v2/papers/{paper_id}/versions/{version_id}/assets/{asset_id}"): "asset",
        ("GET", "/health/live"): "health",
        ("GET", "/api/v2/capabilities"): "navigation",
        ("GET", "/{path:path}"): "static",
    }
    assert {key: recorded[key] for key in expected} == expected
    assert classes.classify("GET", "/research") == "static"
    assert classes.classify("GET", "/api/v2/no-such-route") == "static"
    # The recorder writes None as `static`.
    assert classes.classify("POST", "/api/v2/no-such-route") is None


def test_a_template_matching_another_routes_request_first_fails_the_assembly_check(host):
    import re

    from starlette.routing import compile_path

    from backend.request_context import RouteClasses
    from backend.u8_host import route_classes
    from backend.u8_routes import register_classes, sample_path

    routes = host.app.router.routes
    early = RouteClasses()
    early.register("/{path:path}", "static", methods=("GET",))
    register_classes(early, routes)
    with pytest.raises(ValueError, match=re.escape("route recorded under another class: GET /")):
        check_routes(routes, early)

    own = route_classes()
    assert not any(path == "/{path:path}" for _, path, _, _ in own._entries)
    register_classes(own, routes)
    assert check_routes(routes, own) == host.app.state.route_inventory

    template = "/x/{n:int}/{f:float}/{u:uuid}/{rest:path}"
    assert sample_path(template) == "/x/1/1.5/00000000-0000-0000-0000-000000000001/sample"
    for each in (template, "/api/v2/jobs/{job_id}/events"):
        regex, _, _ = compile_path(each)
        assert regex.match(sample_path(each)), each


def test_real_requests_are_recorded_under_their_routes_class(
    host, sign_in_account, connect, monkeypatch,
):
    import backend.u8_routes as routes
    from backend.u8_policy import ROUTE_CLASSES
    from tests.u8_service_operations_integration.conftest import post
    from tests.u8_service_operations_integration.host_flows import csrf

    owner, _ = member(host, sign_in_account)
    [job] = make_jobs(connect, owner.account_id, session_of(connect, owner.account_id),
                      ("research-turn",))
    token = csrf(host.client)
    # A real 0.3 s wait: the stream's own lifetime, as test_jobs_api sets it.
    monkeypatch.setattr(routes, "JOB_STREAM_SECONDS", 0.3)
    monkeypatch.setattr(routes, "JOB_POLL_SECONDS", 0.05)
    latency, client = host.app.state.latency, host.client
    before = {name: latency.summary(name) for name in ROUTE_CLASSES}

    assert client.get("/health/live").status_code == 200
    assert client.get("/api/v2/capabilities").status_code == 200
    assert client.get("/api/v2/session").status_code == 200
    assert client.get(f"/api/v2/jobs/{job}").status_code == 200
    events = client.get(f"/api/v2/jobs/{job}/events")
    assert events.status_code == 200, events.text
    assert events.headers["content-type"].startswith("text/event-stream")
    assert client.get("/research").status_code in (200, 503)
    assert client.get("/api/v2/no-such-route").status_code == 503
    asset = client.get(f"/api/v2/papers/{uuid4()}/versions/{uuid4()}/assets/{uuid4()}")
    assert (asset.status_code, asset.json()["code"]) == (404, "FORBIDDEN"), asset.text
    post(client, "/api/v2/c04/read-asset", {}, token)
    post(client, "/api/v2/c11/read-dashboard", {"page": {"limit": 10}}, token)

    after = {name: latency.summary(name) for name in ROUTE_CLASSES}
    counts = {name: after[name]["count"] - before[name]["count"] for name in ROUTE_CLASSES}
    assert counts == {"health": 1, "navigation": 1, "read": 2, "stream": 1, "static": 2,
                      "asset": 2, "administration": 1, "search": 0, "accept": 0}
    errors = {name: after[name]["errors5xx"] - before[name]["errors5xx"]
              for name in ROUTE_CLASSES}
    assert errors["static"] >= 1
    assert {name: value for name, value in errors.items() if name != "static"} == dict.fromkeys(
        (name for name in ROUTE_CLASSES if name != "static"), 0)


# --- The isolation table (U8 plan Step 168(b); L4-13) --------------------------------------

ISOLATION_TABLE = Path(__file__).resolve().parents[1] / "isolation_routes.json"
PROBED_KINDS = {"owner-list", "owner-read", "owner-read-by-id", "owner-event", "asset",
                "suspended"}
OTHER_KINDS = {"not-owner-scoped", "administrator", "write", "write-by-id", "public", "token"}
WRITE_KINDS = {"write", "write-by-id"}
# The route classes whose guarded routes are never a write.
READING_CLASSES = {"read", "stream", "asset", "administration", "navigation", "search"}


def isolation_table() -> dict:
    import json

    return json.loads(ISOLATION_TABLE.read_text(encoding="utf-8"))


def table_gaps(inventory: dict, rows: list[dict]) -> dict[str, list[tuple[str, str]]]:
    """The routes the inventory holds and the table does not (`missing`), the rows that
    name no route of the inventory (`stray`) and the rows written twice (`repeated`)."""
    keys = [(row["method"], row["path"]) for row in rows]
    return {"missing": sorted(set(inventory) - set(keys)),
            "stray": sorted(set(keys) - set(inventory)),
            "repeated": sorted({key for key in keys if keys.count(key) > 1})}


def test_every_route_of_the_assembly_has_an_isolation_row(host):
    gaps = table_gaps(host.app.state.route_inventory, isolation_table()["routes"])
    assert gaps == {"missing": [], "stray": [], "repeated": []}, gaps


def test_a_new_guarded_route_without_an_isolation_row_fails(host):
    from backend.local_browser import boundary_route
    from backend.u8_host import route_classes
    from backend.u8_routes import register_classes

    origin = host.composition.transactions.profile.origin
    stray = APIRouter(route_class=boundary_route(origin))

    @stray.post("/api/v2/c03/library-read-stray")
    async def unlisted():
        return {}

    routes = [*host.app.router.routes, *stray.routes]
    classes = route_classes()
    register_classes(classes, routes)
    inventory = check_routes(routes, classes)
    assert inventory[("POST", "/api/v2/c03/library-read-stray")] == ("read", "guarded")
    gaps = table_gaps(inventory, isolation_table()["routes"])
    assert gaps == {"missing": [("POST", "/api/v2/c03/library-read-stray")], "stray": [],
                    "repeated": []}


def test_a_guarded_read_stream_or_asset_route_is_never_classed_as_a_write(host):
    inventory = host.app.state.route_inventory
    kinds = {(row["method"], row["path"]): row["kind"] for row in isolation_table()["routes"]}
    checked = 0
    for key, (klass, access) in inventory.items():
        if access != "guarded" or klass not in READING_CLASSES:
            continue
        checked += 1
        assert kinds[key] not in WRITE_KINDS, (key, klass, kinds[key])
    # The reading classes hold most of the guarded surface; an empty pass proves nothing.
    assert checked >= 50, checked
    assert {klass for klass, _ in inventory.values()} >= READING_CLASSES


def test_every_owner_row_names_a_probe_every_other_row_says_why_and_the_destinations_are_the_registrys(  # noqa: E501
) -> None:
    from backend.u8_registry import NAVIGATION

    table = isolation_table()
    probes = []
    for row in table["routes"]:
        key = (row["method"], row["path"])
        assert row["kind"] in PROBED_KINDS | OTHER_KINDS, key
        if row["kind"] in PROBED_KINDS:
            assert isinstance(row.get("probe"), str) and row["probe"], key
            assert "reason" not in row, key
            probes.append(row["probe"])
        else:
            assert isinstance(row.get("reason"), str) and len(row["reason"]) >= 20, key
            assert "probe" not in row and "notClaimed" not in row, key
        if "notClaimed" in row:
            assert isinstance(row["notClaimed"], str) and len(row["notClaimed"]) >= 20, key
        assert row.get("anonymous", True) is True, key
        # A row the signed-out pass skips is one a signed-out caller may reach: on the
        # public list, or among the owners' own anonymous routes, which this file's
        # signed-out test asks of the host.
        if row.get("anonymous"):
            assert key in PUBLIC_ROUTES or row["path"] in ANONYMOUS_PERMITTED, key
    assert len(probes) == len(set(probes)), sorted(p for p in probes if probes.count(p) > 1)
    assert all(row["kind"] in ("suspended", "owner-read-by-id", "owner-list")
               for row in table["routes"] if "notClaimed" in row)
    flagged = {(row["method"], row["path"]) for row in table["routes"] if row.get("anonymous")}
    assert {key for key in flagged if key in PUBLIC_ROUTES} == {
        ("GET", "/api/v2/session"), ("POST", "/api/v2/c02/access-inspect-session")}
    assert table["destinations"] == [entry.path for entry in NAVIGATION]
