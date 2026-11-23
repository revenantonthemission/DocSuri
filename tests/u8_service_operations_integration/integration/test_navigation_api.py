"""Navigation and the capability list from the registry (U8 plan Step 40; A1, BR5.1–BR5.5,
BR5.9).

`host-resolve-navigation` answers BR5.2 for each entry of `u8_registry.NAVIGATION` from
its capability's derived state and the caller's access: degraded entries stay enabled
with their reason, unavailable, stale and unknown ones are disabled with theirs, an entry
that needs a session is a sign-in prompt for a caller with none, 운영 is available only to
an administrator with a current second factor, and the footer's legal entries are always
available. A caller with no session reads only the public capability projection.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from docsuri_shared.workspace import wire

from backend.modules.operations.readiness import PUBLIC_EXTRA, CapabilityState
from backend.u8_registry import NAVIGATION
from backend.u8_routes import navigation_items
from tests.u8_service_operations_integration.host_flows import (
    OTHER_MEMBER,
    administrator,
    assert_bounded_runs,
    by_owner,
    call,
    complete_host,
    counted_post,
    fresh_client,
    lapse_second_factor,
    member,
    sign_in,
)

pytestmark = pytest.mark.usefixtures("own_address")
FORCED = {"research": "degraded", "topics.digest": "unavailable", "export": "stale",
          "usage.wallet": "unknown"}


@pytest.fixture
def host(realm, own_address):
    with complete_host(realm, address=own_address) as value:
        yield value


def forced_states(host, forced: dict[str, str]):
    """The composition's readiness with chosen states over every capability: every other
    capability available, so each entry's answer follows the state forced on it. A forced
    value is a state (its reason `forced-<name>`) or a `(state, reason)` pair."""
    real = host.composition.readiness_view

    def chosen(name: str) -> tuple[str, str | None]:
        value = forced.get(name, "available")
        if isinstance(value, tuple):
            return value
        return value, None if name not in forced else f"forced-{name}"

    def view():
        readiness = real()
        states = {name: CapabilityState(name, *chosen(name))
                  for name in readiness.contribution_of}
        readiness.states = lambda: states
        return readiness

    host.composition.readiness_view = view


def resolve(client, route: str = "search") -> dict:
    answer = call(client, "/api/v2/c01/host-resolve-navigation", {"routeId": route})
    assert answer.status_code == 200, answer.text
    value = answer.json()
    wire.HostNavigationResult.model_validate(value)
    return value


def by_route(value: dict) -> dict:
    return {item["routeId"]: item for item in value["items"]}


def test_each_state_answers_its_entry_and_reason_key_with_placements(host, sign_in_account):
    forced_states(host, FORCED)
    member(host, sign_in_account)
    items = by_route(resolve(host.client))
    assert [item["routeId"] for item in resolve(host.client)["items"]] == [
        entry.route_id for entry in sorted(NAVIGATION, key=lambda e: e.order)]
    assert items["research"]["available"] is True
    assert items["research"]["reasonKey"] == "nav.capabilityDegraded"
    assert items["jobs"]["capabilityId"] == "research"  # 작업 is backed by research
    assert (items["topics"]["available"], items["topics"]["reasonKey"]) == (
        False, "nav.capabilityUnavailable")
    assert (items["export"]["available"], items["export"]["reasonKey"]) == (
        False, "nav.capabilityStale")
    assert (items["usage"]["available"], items["usage"]["reasonKey"]) == (
        False, "nav.capabilityUnknown")
    assert items["search"]["available"] is True and "reasonKey" not in items["search"]
    assert {items[name]["placement"] for name in ("privacy", "terms")} == {"footer"}
    assert items["paper"]["placement"] == "contextual"
    assert all(items[name]["available"] for name in ("privacy", "terms"))


def test_operations_is_available_only_to_an_administrator_with_a_current_factor(
    host, sign_in_account, connect,
):
    forced_states(host, {})
    member(host, sign_in_account)
    operations = by_route(resolve(host.client))["operations"]
    assert (operations["available"], operations["reasonKey"]) == (False, "nav.administratorOnly")
    host.client.cookies.clear()
    authority, _ = administrator(host, sign_in_account, connect)
    assert by_route(resolve(host.client))["operations"]["available"] is True
    lapse_second_factor(connect, authority.account_id)
    operations = by_route(resolve(host.client))["operations"]
    assert (operations["available"], operations["reasonKey"]) == (False, "nav.administratorOnly")


def test_a_caller_with_no_session_reads_only_the_public_projection(host, sign_in_account):
    forced_states(host, {"provider.google": "unavailable"})
    answer = host.client.get("/api/v2/capabilities")
    assert answer.status_code == 200, answer.text
    page = wire.HostPublicCapabilityPage.model_validate(answer.json()).model_dump(mode="json")
    visible = {entry.capability_id for entry in NAVIGATION if entry.access == "anonymous"}
    assert {item["capabilityId"] for item in page["items"]} == visible | set(PUBLIC_EXTRA)
    assert set(PUBLIC_EXTRA) == {"account.entry", "provider.google", "provider.orcid",
                                 "provider.resend"}
    google = next(item for item in page["items"] if item["capabilityId"] == "provider.google")
    assert set(google) == {"capabilityId", "state", "reasonKey"}
    assert (google["state"], google["reasonKey"]) == ("unavailable", "forced-provider.google")
    # Signed out, the session-only entries are sign-in prompts.
    items = by_route(resolve(host.client))
    assert (items["library"]["available"], items["library"]["reasonKey"]) == (
        False, "nav.authenticationRequired")
    # Signed in, the catalog: each contribution's row with its derived state.
    member(host, sign_in_account)
    catalog = wire.CapabilityCatalog.model_validate(
        host.client.get("/api/v2/capabilities").json()).model_dump(mode="json")
    rows = {row["id"]: row for row in catalog["capabilities"]}
    assert rows["account.controls"]["state"] == "available"
    assert {"research", "novelty", "topics.digest", "export", "operations.ledger",
            "corpus.maintenance"} <= set(rows)


@pytest.mark.parametrize(("internal", "public"), [
    (("degraded", "allowance-exhausted"), ("available", "available")),
    (("degraded", "first-effect-pending"), ("unavailable", "provider-unreachable")),
    (("unavailable", "unconfigured"), ("unavailable", "provider-unreachable")),
    (("unavailable", "provider-unreachable"), ("unavailable", "provider-unreachable")),
    (("unknown", "no-observation"), ("available", "available")),
    (("stale", "observation-stale"), ("available", "available")),
])
def test_signed_out_the_mail_provider_reads_serving_or_not_serving(host, internal, public):
    """The person's answer of 2026-11-13, "Working or not, no reasons": the realm's
    signed-out answer gives provider.resend as serving or not serving alone; no limit or
    hold reason reaches a caller with no session."""
    forced_states(host, {"provider.resend": internal})
    answer = host.client.get("/api/v2/capabilities")
    assert answer.status_code == 200, answer.text
    page = wire.HostPublicCapabilityPage.model_validate(answer.json()).model_dump(mode="json")
    (item,) = [value for value in page["items"] if value["capabilityId"] == "provider.resend"]
    assert item == {"capabilityId": "provider.resend", "state": public[0],
                    "reasonKey": public[1]}
    for hidden in ("allowance-exhausted", "first-effect-pending", "unconfigured",
                   "no-observation", "observation-stale"):
        assert hidden not in answer.text
    others = [value for value in page["items"] if value["capabilityId"] != "provider.resend"]
    assert all(value["state"] == "available" for value in others)


def test_maintainer_only_admission_shows_in_the_public_projection(host):
    from backend.modules.accounts.u8_control_policy import Admission

    forced_states(host, {})
    entry = host.composition.parts["account-controls"]["entry"]
    for state, expected in (("maintainer-only", ("degraded", "admission-maintainer-only")),
                            ("open", ("available", "available"))):
        entry.admission = Admission(state)
        page = host.client.get("/api/v2/capabilities").json()
        item = next(value for value in page["items"] if value["capabilityId"] == "account.entry")
        assert (item["state"], item["reasonKey"]) == expected
        others = [value for value in page["items"] if value["capabilityId"] != "account.entry"]
        assert all(value["state"] == "available" for value in others)
    entry.admission = None


def test_an_owner_change_clears_prior_owner_state(host, sign_in_account):
    forced_states(host, {})
    assert resolve(host.client)["clearPriorOwnerState"] is True
    member(host, sign_in_account)
    signed_in = resolve(host.client)
    assert signed_in["clearPriorOwnerState"] is False
    assert call(host.client, "/api/v2/c02/access-logout", {}).status_code == 200
    after = resolve(host.client)
    assert after["clearPriorOwnerState"] is True
    assert after["authorityRevision"] != signed_in["authorityRevision"]
    missing = call(host.client, "/api/v2/c01/host-resolve-navigation", {"routeId": "nowhere"})
    assert missing.status_code == 404


NAVIGATE = "/api/v2/c01/host-resolve-navigation"


def test_navigation_reads_are_bounded_owner_transactions(host, sign_in_account):
    """Step 87(b) (L1-8): signed in, a resolve is two `accounts` runs (the session, then
    the administrator check) and one `operations` run (the capability states); signed
    out, one `operations` run alone, the entry context being read in memory."""
    signed_out, runs = counted_post(host, NAVIGATE, {"routeId": "search"})
    assert signed_out.status_code == 200, signed_out.text
    assert by_owner(runs) == {"operations": 1}, runs
    member(host, sign_in_account)
    signed_in, runs = counted_post(host, NAVIGATE, {"routeId": "search"})
    assert signed_in.status_code == 200, signed_in.text
    assert by_owner(runs) == {"accounts": 2, "operations": 1}, runs
    assert_bounded_runs(host.composition, ("accounts", "operations"))


PAPER = {"paperId": "bound-check-paper", "versionId": "bound-check-paper-v1",
         "eligibilityRevision": "1"}
# Every complete-host route that takes a page limit: (method, path, built bound, the body
# or query of a page of `limit`, its answer to bound + 1). Step 87(b)'s table.
PAGED = (
    ("POST", "/api/v2/c07/list-research-jobs", 50, lambda n: {"limit": n},
     (422, "INVALID_ARGUMENT")),
    ("POST", "/api/v2/c07/list-research-sessions", 50, lambda n: {"page": {"limit": n}},
     (422, "INVALID_ARGUMENT")),
    ("POST", "/api/v2/c06/read-assistance-history", 50,
     lambda n: {"paper": PAPER, "page": {"limit": n}}, (422, "INVALID_ARGUMENT")),
    ("POST", "/api/v2/c03/usage-inspect", 50, lambda n: {"page": {"limit": n}},
     (422, "INVALID_ARGUMENT")),
    ("POST", "/api/v2/c03/usage-list-records", 50, lambda n: {"page": {"limit": n}},
     (409, "CONFLICT")),
    ("POST", "/api/v2/c09/list-export-history", 20, lambda n: {"limit": n},
     (422, "INVALID_ARGUMENT")),
    ("POST", "/api/v2/c03/library-list-saved-papers", 50, lambda n: {"page": {"limit": n}},
     (409, "CONFLICT")),
    ("POST", "/api/v2/c03/library-list-saved-searches", 50, lambda n: {"page": {"limit": n}},
     (409, "CONFLICT")),
    ("POST", "/api/v2/c03/library-list-history", 50, lambda n: {"page": {"limit": n}},
     (409, "CONFLICT")),
    ("POST", "/api/v2/c02/access-list-consents", 50, lambda n: {"page": {"limit": n}},
     (409, "CONFLICT")),
    ("POST", "/api/v2/c02/access-list-identity-links", 50, lambda n: {"page": {"limit": n}},
     (409, "CONFLICT")),
    ("POST", "/api/v2/c03/settings-list-suggestions", 50, lambda n: {"page": {"limit": n}},
     (409, "CONFLICT")),
    ("POST", "/api/v2/c03/settings-list-recent-papers", 50, lambda n: {"page": {"limit": n}},
     (409, "CONFLICT")),
    ("GET", "/api/v2/c03/settings-resets", 50, lambda n: {"view": "history", "limit": n},
     (409, "CONFLICT")),
)


def rows_of(value: dict) -> int:
    """The rows a page answered: its longest top-level list."""
    return max((len(item) for item in value.values() if isinstance(item, list)), default=0)


def page_at(client, method: str, path: str, body: dict):
    if method == "GET":
        return client.get(path, params=body)
    return call(client, path, body)


def test_every_paged_list_route_holds_at_most_50_rows(host, sign_in_account, connect,
                                                     own_address):
    """Step 87(b) (L1-8, L1-63): a page at each route's built bound answers 200 with at
    most that many rows, bound + 1 is refused as built, and no bound exceeds 50;
    `list-incidents` clamps 51 to 50 rows (`page_of`). Search's 100 is
    `test_signed_in_search.py`'s; `read-dashboard` is one composite read (Step 104(b))."""
    inventory = host.app.state.route_inventory
    # `sign-in-migrated`: `sign-in-member` holds `host_flows.make_jobs`' synthetic
    # sessions (scope `{}`), which no session read can present.
    authority, _ = member(host, sign_in_account, OTHER_MEMBER)

    def personalization(granted: bool) -> None:
        # The recent-papers read answers only an account that gave its personalization
        # consent; `sign_in_account` leaves it refused.
        with connect("accounts") as conn:
            conn.execute("UPDATE accounts.consent SET granted=%s WHERE account_id=%s AND "
                         "purpose='personalization'", (granted, authority.account_id))

    personalization(True)
    try:
        for method, path, bound, body, refusal in PAGED:
            assert (method, path) in inventory, path
            assert bound <= 50, path
            answer = page_at(host.client, method, path, body(bound))
            assert answer.status_code == 200, (path, answer.text)
            assert rows_of(answer.json()) <= bound, path
            refused = page_at(host.client, method, path, body(bound + 1))
            assert (refused.status_code, refused.json().get("code")) == refusal, (
                path, refused.text)
    finally:
        personalization(False)
    # A consent-pending session (U8's D1 route): a migrated account's first sign-in.
    with fresh_client(host, address=own_address) as pending:
        _, email = sign_in_account(OTHER_MEMBER, consents=False)
        signed = sign_in(pending, email)
        assert signed.json()["state"] == "consent_pending", signed.text
        consents = "/api/v2/c02/access-list-consents"
        answer = call(pending, consents, {"page": {"limit": 50}})
        assert answer.status_code == 200 and rows_of(answer.json()) <= 50, answer.text
        refused = call(pending, consents, {"page": {"limit": 51}})
        assert (refused.status_code, refused.json()["code"]) == (422, "INVALID_ARGUMENT")
    # The shared account back to its consents, its limited session ended.
    sign_in_account(OTHER_MEMBER)
    # `list-incidents`, read by an administrator with a current second factor.
    incidents = "/api/v2/c11/list-incidents"
    assert ("POST", incidents) in inventory
    with fresh_client(host, address=own_address) as operator:
        administrator(SimpleNamespace(client=operator, composition=host.composition),
                      sign_in_account, connect)
        for limit in (50, 51):
            answer = call(operator, incidents, {"page": {"limit": limit}})
            assert answer.status_code == 200, answer.text
            assert len(answer.json()["items"]) <= 50


def test_navigation_items_follow_the_access_rules_without_a_host():
    states = {entry.capability_id: SimpleNamespace(state="available") for entry in NAVIGATION}
    signed_out = {item["routeId"]: item for item in navigation_items(
        states, signed_in=False, administrator=False)}
    assert signed_out["search"]["available"] and signed_out["paper"]["available"]
    assert signed_out["account"]["reasonKey"] == "nav.authenticationRequired"
    administrator_view = {item["routeId"]: item for item in navigation_items(
        {}, signed_in=True, administrator=True)}
    # No observation yet: unknown, never available (BR3.2).
    assert administrator_view["operations"]["reasonKey"] == "nav.capabilityUnknown"
    assert administrator_view["privacy"]["available"] is True
