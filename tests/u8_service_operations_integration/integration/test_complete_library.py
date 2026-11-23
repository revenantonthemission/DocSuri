"""The library's write routes in the complete app (U8 plan Step 24; the person's decision of
2026-10-23, "U2's controls in the complete app").

In the composed realm the mounted library routes take U2's control path under the realm's
own policy, through the complete host:

1. a saved paper is read back with its title, listed, refused removal at a stale
   revision and removed at its own, after which it is gone;
2. a saved search is refused removal at a stale revision and removed at its own;
3. clearing the history is durable and replays under its key, and an unknown history
   record is refused like a missing one;
4. a save under another policy is refused before it reaches the library.
"""

from __future__ import annotations

import secrets
from uuid import uuid4

import pytest

from backend.modules.accounts.u8_control_policy import U8_SYNTHETIC_POLICY
from tests.u8_service_operations_integration.conftest import post
from tests.u8_service_operations_integration.host_flows import (
    MEMBER,
    call,
    complete_host,
    csrf,
    member,
)

pytestmark = pytest.mark.usefixtures("own_address")
POLICY = U8_SYNTHETIC_POLICY.reference
QUERY = {
    "query": "Transformer",
    "modeId": "lexical",
    "orderId": "relevance",
    "filters": [],
    "vocabularyRevision": "synthetic-paper-options-1",
    "policyRef": {"policyId": "synthetic-local-search", "revision": "1"},
}


@pytest.fixture
def host(realm, own_address):
    with complete_host(realm, address=own_address) as value:
        yield value


@pytest.fixture
def signed_in(host, sign_in_account, connect):
    """The member signed in with an empty library (the library owner's own login)."""
    owner, _ = member(host, sign_in_account, MEMBER)
    with connect("library") as conn:
        for table in ("saved_query", "saved_paper", "history"):
            conn.execute(f"DELETE FROM library.{table} WHERE account_id=%s", (owner.account_id,))
    return owner


@pytest.fixture
def paper(connect):
    """An eligible synthetic paper version written through the corpus owner's login."""
    token = secrets.token_hex(4)
    paper_id, version_id, revision = f"u8cl-{token}", f"u8cl-{token}-v1", uuid4()
    with connect("corpus") as conn:
        conn.execute("INSERT INTO corpus.paper(id,title,authors,metadata) "
                     "VALUES(%s,'Synthetic library paper','[]','{}')", (paper_id,))
        conn.execute(
            "INSERT INTO corpus.version(id,paper_id,source_url,source_hash,version_label,"
            "private_path,eligible,purpose,eligibility_revision,provenance,content) VALUES"
            "(%s,%s,'https://fixture.example.com/paper',%s,'v1','fixture',true,"
            "'local-research',%s,'{}','{}')",
            (version_id, paper_id, secrets.token_hex(32), revision))
    return {"paperId": paper_id, "versionId": version_id, "eligibilityRevision": str(revision)}


def c03(client, name: str, body: dict, *, key=None):
    return post(client, f"/api/v2/c03/{name}", body, csrf(client), operation=key)


def test_a_saved_paper_is_read_listed_and_removed_at_its_own_revision(
        host, signed_in, paper):
    saved = c03(host.client, "library-save-paper", {"paper": paper, "policyRef": POLICY})
    assert saved.status_code == 200, saved.text
    identifier = saved.json()["savedPaperId"]
    read = c03(host.client, "library-read-saved-paper", {"savedPaperId": identifier})
    assert read.status_code == 200, read.text
    assert read.json()["savedTitle"] == "Synthetic library paper"
    assert read.json()["savedPaper"]["versionId"] == paper["versionId"]
    listed = c03(host.client, "library-list-saved-papers", {"page": {"limit": 5}})
    assert identifier in [item["savedPaperId"] for item in listed.json()["items"]]
    stale = {"savedPaperId": identifier, "expectedRevision": str(uuid4())}
    assert c03(host.client, "library-remove-saved-paper", stale).status_code == 409
    removed = c03(host.client, "library-remove-saved-paper",
                  {"savedPaperId": identifier, "expectedRevision": read.json()["revision"]})
    assert removed.status_code == 200, removed.text
    assert removed.json()["resourceId"] == identifier
    gone = c03(host.client, "library-read-saved-paper", {"savedPaperId": identifier})
    assert gone.status_code == 404
    invalid = c03(host.client, "library-remove-saved-paper",
                  {"savedPaperId": identifier, "expectedRevision": "not-a-revision"})
    assert invalid.status_code == 422


def test_a_saved_search_is_removed_only_at_its_own_revision(host, signed_in):
    saved = c03(host.client, "library-save-search", {"queryContext": QUERY, "label": "합성"})
    assert saved.status_code == 200, saved.text
    assert saved.json()["label"] == "합성"
    body = {"savedSearchId": saved.json()["savedSearchId"], "expectedRevision": str(uuid4())}
    assert c03(host.client, "library-remove-saved-search", body).status_code == 409
    body["expectedRevision"] = saved.json()["revision"]
    removed = c03(host.client, "library-remove-saved-search", body)
    assert removed.status_code == 200, removed.text
    page = c03(host.client, "library-list-saved-searches", {"page": {"limit": 5}})
    assert saved.json()["savedSearchId"] not in [
        item["savedSearchId"] for item in page.json()["items"]]
    invalid = dict(body, savedSearchId="not-an-identifier")
    assert c03(host.client, "library-remove-saved-search", invalid).status_code == 422


def test_clearing_the_history_is_durable_and_replays_under_its_key(host, signed_in):
    before = c03(host.client, "library-list-history", {"page": {"limit": 2}})
    assert before.status_code == 200, before.text
    key = uuid4()
    body = {"expectedRevision": before.json()["clearBoundary"], "policyRef": POLICY}
    cleared = c03(host.client, "library-clear-history", body, key=key)
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["ack"]["resourceId"] == str(signed_in.account_id)
    assert c03(host.client, "library-clear-history", body, key=key).json() == cleared.json()
    after = c03(host.client, "library-list-history", {"page": {"limit": 2}}).json()
    assert after["clearBoundary"] == cleared.json()["clearBoundary"]
    unknown = c03(host.client, "library-read-history", {"historyId": str(uuid4())})
    assert unknown.status_code == 404
    invalid = c03(host.client, "library-clear-history",
                  dict(body, expectedRevision="not-a-revision"))
    assert invalid.status_code == 422


def test_a_save_under_another_policy_is_refused(host, signed_in, paper):
    other = {"policyId": "synthetic-local-library", "revision": "1"}
    refused = call(host.client, "/api/v2/c03/library-save-paper",
                   {"paper": paper, "policyRef": other})
    assert refused.status_code >= 400
    listed = c03(host.client, "library-list-saved-papers", {"page": {"limit": 5}})
    assert listed.json()["items"] == []
