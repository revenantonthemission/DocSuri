"""A signed-in search in the composed realm (U8 plan Step 24, the person's decision of
2026-10-23, "Fix it, widen the check"; Allowlist sites row 11).

`GuardedDiscoveryRepository.admit` and the finish's admission check accepted only U2's and
U3's realms, so every signed-in search in the complete assembly answered 409 CONFLICT
(`admission binding required`, a `ValueError` through the boundary). Row 11 adds the
composed realm and production to both sites, one value per site:

1. a signed-in search through the HTTP route answers 200, records its admission, and its
   finish checks that admission (the execution's captured generation is its sequence);
2. a finish whose admission is missing, or bound to another owner or query, is refused;
3. a signed-out search still answers, with no admission and no owner fact;
4. a realm outside the accepted ones is still refused.
"""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from backend.modules.discovery.guarded_repository import GuardedDiscoveryRepository
from backend.modules.discovery.u3_search import _query_digest
from backend.transactions import Authority
from backend.u3_policy import QUERY_VOCABULARY, SEARCH_POLICY
from tests.u8_service_operations_integration.host_flows import (
    OTHER_MEMBER,
    assert_bounded_runs,
    by_owner,
    call,
    complete_host,
    counted_post,
    fresh_client,
    member,
    session_of,
)

pytestmark = pytest.mark.usefixtures("own_address")


def query(text: str = "synthetic") -> dict:
    return {"query": text, "modeId": "lexical", "orderId": "relevance", "filters": [],
            "vocabularyRevision": QUERY_VOCABULARY, "policyRef": SEARCH_POLICY}


@pytest.fixture
def host(realm, own_address):
    with complete_host(realm, address=own_address) as value:
        yield value


def search(client, text: str = "synthetic"):
    return call(client, "/api/v2/c05/search", {"query": query(text), "page": {"limit": 5}})


def admissions(connect, account_id) -> list[dict]:
    with connect("discovery") as conn:
        return conn.execute(
            "SELECT a.execution_id,a.sequence,a.query_hash,e.captured_generation "
            "FROM discovery.admission a LEFT JOIN discovery.execution e "
            "ON e.id=a.execution_id WHERE a.account_id=%s ORDER BY a.sequence",
            (account_id,)).fetchall()


def test_a_signed_in_search_answers_and_its_finish_checks_its_admission(
        host, sign_in_account, connect):
    authority, _ = member(host, sign_in_account)
    before = len(admissions(connect, authority.account_id))
    answer = search(host.client)
    assert answer.status_code == 200, answer.text
    assert answer.json()["outcome"] in ("complete", "partial")
    rows = admissions(connect, authority.account_id)
    assert len(rows) == before + 1
    newest = rows[-1]
    assert newest["query_hash"] == _query_digest(query())
    # The finish ran after its admission check: its fact carries the admission's sequence.
    assert newest["captured_generation"] == newest["sequence"]


def test_the_search_page_holds_at_most_100_and_its_reads_are_bounded(host, sign_in_account):
    """Step 87(b) (L1-8): a signed-in search is four `discovery` runs (the admission, the
    candidates in one `SearchCandidates.read`, the record and the acknowledgement) and
    one `accounts` run (the session); the history relay's Library runs are Library's
    own. Its page holds at most 100 hits, and 101 answers 409 as built."""
    member(host, sign_in_account)
    answer, runs = counted_post(host, "/api/v2/c05/search",
                                {"query": query(), "page": {"limit": 100}})
    assert answer.status_code == 200, answer.text
    assert len(answer.json()["hits"]) <= 100
    owners = by_owner(runs)
    assert (owners.get("discovery"), owners.get("accounts")) == (4, 1), runs
    assert set(owners) <= {"discovery", "accounts", "library"}, runs
    assert_bounded_runs(host.composition, ("discovery", "accounts"))
    refused = call(host.client, "/api/v2/c05/search",
                   {"query": query(), "page": {"limit": 101}})
    assert (refused.status_code, refused.json()["code"]) == (409, "CONFLICT"), refused.text


def test_a_finish_without_its_own_admission_is_refused(host, sign_in_account, connect):
    # Each owner's live session from its sign-in through the host (`sign_in_account`
    # ends the fixture's own sessions first).
    signed, _ = member(host, sign_in_account)
    owner = Authority(signed.account_id, session_of(connect, signed.account_id))
    with fresh_client(host) as client:
        other_signed, _ = member(SimpleNamespace(client=client), sign_in_account,
                                 OTHER_MEMBER)
    other = Authority(other_signed.account_id, session_of(connect, other_signed.account_id))
    repository = GuardedDiscoveryRepository(host.composition.transactions)
    digest = _query_digest(query())
    # No admission at all.
    with pytest.raises(PermissionError, match="search admission"):
        repository.record(owner, uuid4(), query(), digest, [], 1)
    # An admission bound to another query.
    execution = uuid4()
    sequence = repository.admit(owner, execution, digest)
    with pytest.raises(PermissionError, match="search admission"):
        repository.record(owner, execution, query("other"), _query_digest(query("other")),
                          [], sequence)
    # An admission bound to another owner.
    with pytest.raises(PermissionError, match="search admission"):
        repository.record(other, execution, query(), digest, [], sequence)
    # Its own admission, its own query: accepted.
    fact = repository.record(owner, execution, query(), digest, [], sequence)
    assert fact["captured_generation"] == sequence


def test_a_signed_out_search_needs_no_admission(host, connect):
    with fresh_client(host) as guest:
        with connect("discovery") as conn:
            before = conn.execute("SELECT count(*) AS n FROM discovery.admission").fetchone()["n"]
        answer = search(guest)
        assert answer.status_code == 200, answer.text
        with connect("discovery") as conn:
            after = conn.execute("SELECT count(*) AS n FROM discovery.admission").fetchone()["n"]
    assert after == before


@pytest.mark.parametrize("realm_name", ["research-workspace", "topics-digests",
                                        "approved-export", "journey", "elsewhere"])
def test_a_realm_outside_the_accepted_ones_is_still_refused(realm_name):
    def run(owner, work):  # never reached: the realm check refuses first
        raise AssertionError("an unaccepted realm reached the database")

    transactions = SimpleNamespace(profile=SimpleNamespace(realm=realm_name), run=run)
    authority = SimpleNamespace(account_id=uuid4(), session_id=uuid4())
    with pytest.raises(ValueError, match="admission binding required"):
        GuardedDiscoveryRepository(transactions).admit(authority, uuid4(), "0" * 64)


class Reached(Exception):
    """The sentinel an accepted realm's admit meets at its owner transaction."""


class AcceptedRealm:
    """A raise-only spy for an accepted realm's transactions (your answer of 2026-11-11,
    "Rewrite, keep two"): `run` records the owner it is asked for in the sentinel it
    raises, so no statement runs and no answer stands in for the database's."""

    def __init__(self, realm):
        self.profile = SimpleNamespace(realm=realm)

    def run(self, owner, work):
        raise Reached(owner)


def test_the_accepted_realms_are_u2_u3_the_composed_realm_and_production():
    authority = SimpleNamespace(account_id=uuid4(), session_id=uuid4())
    for name in ("account-controls", "corpus-maintenance", "service-operations", "production"):
        with pytest.raises(Reached) as reached:
            GuardedDiscoveryRepository(AcceptedRealm(name)).admit(authority, uuid4(), "0" * 64)
        assert reached.value.args == ("discovery",), name
