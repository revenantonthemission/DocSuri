"""Accepting work in the complete host (U8 plan Step 87(d); P8, L1-6, L1-7).

Each test composes its own `complete_host(realm)` and starts that composition's export
lane once, stopping it at teardown (`ExportLane.start` refuses a second start). The
export contribution is the composition's own, over the test's own `FakeNotion` from
`u8_fixtures.notion_scenario` with a token generated per run: `backend.u6_host.
synthetic_notion` is pointed at it for the compose, and `build_approved_export` imports
it at call time.

- an export accept records the effect and answers at once: `execute-approved-export`
  sends nothing to Notion, its effect row is written in the statement that consumes the
  approval, and only the lane writes the page (P8);
- a continued export is accepted as the decision says (L1-7): a continue from a second
  session of the account checks only local facts, the lane's pre-write check ends it
  unwritten when the destination changed, and a continue after the approving session
  ended is refused with the approval invalidated as `authority-revoked`;
- each started job records its own accepting request's identifier, never the
  Idempotency-Key, a planted `x-request-id` or an earlier request's, and the worker
  lines of the assistance job and the export effect name it (L1-6).

The accounts are the realm's deterministic ones: the member `sign-in-member`, which no
other file binds exports from. The file binds three effects a run, well inside U6's 20
binds per account in a rolling hour; every effect ends before the next bind, and the
file runs its own assistance jobs until they are terminal and settled. A worker pass
takes the oldest due item realm-wide, so each wait runs at most four bounded passes and
reads only its own ids.
"""

from __future__ import annotations

import json
import logging
import secrets
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from backend.log_events import EVENTS_LOGGER
from backend.transactions import Authority
from backend.u6_policy import SYNTHETIC_EXPORT
from tests.u8_service_operations_integration.host_flows import (
    MEMBER,
    call,
    complete_host,
    csrf,
    fresh_client,
    import_paper,
    member,
    session_of,
    sign_in,
)

pytestmark = pytest.mark.usefixtures("own_address")
C09 = "/api/v2/c09/"
PASSES = 4
IDLE_SECONDS = 30.0
# The run's own Notion token, accepted only by this file's fakes.
TOKEN = "u8-synthetic-" + secrets.token_hex(20)
# The member's ready novelty result, made once per module run and reused.
KNOWN: dict = {}
CHUNKS = [
    {"anchor": "intro", "section": "Introduction",
     "text": "Attention lets a model weigh every input token against every other token."},
    {"anchor": "method", "section": "Method",
     "text": "We train the encoder on paired sentences and report the loss on held out data."},
]


def fixtures_module():
    from scripts import verify_docsuri_u8

    folder = str(Path(verify_docsuri_u8.ROOT) / "scripts")
    if folder not in sys.path:
        sys.path.insert(0, folder)
    import u8_fixtures

    return u8_fixtures


@pytest.fixture
def host(realm, own_address, monkeypatch):
    """The complete host over this test's own fake Notion, its export lane started."""
    from backend import u6_host
    from backend.modules.export.fake_notion import FakeNotion

    scenario = fixtures_module().notion_scenario(realm.run_id, TOKEN)
    fake = FakeNotion.from_scenario(scenario, run_id=realm.run_id)
    monkeypatch.setattr(u6_host, "synthetic_notion", lambda profile, clock: fake)
    with complete_host(realm, address=own_address) as value:
        lane = value.composition.parts["approved-export"]["lane"]
        lane.start()
        try:
            yield SimpleNamespace(composition=value.composition, app=value.app,
                                  client=value.client, fake=fake, lane=lane,
                                  practice=page_of(scenario, "practice"))
        finally:
            lane.stop()


def page_of(scenario: dict, purpose: str) -> str:
    title = {"practice": fixtures_module().NOTION_PRACTICE}[purpose]
    return next(page["id"] for page in scenario["pages"] if page["title"] == title)


def signed_in(host, sign_in_account, connect) -> tuple[Authority, str]:
    """The member signed in (session 1), granted its usage, its authority current."""
    from backend.modules.accounts.u8_control_policy import U8_SYNTHETIC_POLICY
    from backend.modules.plans.u8_usage import ImportedUsage

    authority, email = member(host, sign_in_account, MEMBER)
    ImportedUsage(host.composition.transactions, U8_SYNTHETIC_POLICY).grant_imported(
        authority.account_id, source="realm_fixture")
    free_quota(host, authority.account_id)
    return Authority(authority.account_id, session_of(connect, authority.account_id)), email


def free_quota(host, account_id) -> None:
    """The account's reservations of the current period moved one period back, so the
    realm's quota of 3 per 15 minutes is free for this test's accepts; the rows stay
    (as `host_flows.free_quota` does on a stand-in)."""
    from backend.modules.accounts.u8_control_policy import U8_SYNTHETIC_POLICY
    from backend.modules.plans.u8_usage import ResearchUsageService
    from tests.u8_service_operations_integration import recovery_flows as rf

    realm = host.composition.profile
    current = ResearchUsageService(host.composition.transactions,
                                   U8_SYNTHETIC_POLICY).current_period()
    prefix, number = current.split(":")
    with rf.admin(realm, realm.database_name) as conn, conn.transaction():
        conn.execute("UPDATE usage.reservation SET period_id=%s WHERE account_id=%s AND "
                     "period_id=%s", (f"{prefix}:{int(number) - 1}", account_id, current))


def novelty(host, authority) -> dict:
    """The member's ready novelty result (`u8_fixtures.ready_novelty`), made once per
    module run; later tests reuse its known reference."""
    value = fixtures_module().ready_novelty(host.composition.transactions, authority,
                                            KNOWN.get("novelty"))
    KNOWN["novelty"] = value
    return {key: value[key] for key in ("artifactId", "revision", "contentHash")}


def ok(client, operation: str, body: dict, *, key=None) -> dict:
    answer = client.post(C09 + operation, json=body, headers={
        "origin": "https://127.0.0.1:18110", "x-csrf-token": csrf(client),
        "idempotency-key": str(key or uuid4())})
    assert answer.status_code == 200, (operation, answer.text)
    return answer.json()


def post_c09(client, operation: str, body: dict, *, key=None):
    return client.post(C09 + operation, json=body, headers={
        "origin": "https://127.0.0.1:18110", "x-csrf-token": csrf(client),
        "idempotency-key": str(key or uuid4())})


def connected(client) -> dict:
    """The member's connection to the fake under this run's token: configured afresh,
    replacing a connection an earlier run left, then read."""
    current = post_c09(client, "read-notion-connection", {})
    expected = current.json().get("revision") if current.status_code == 200 else None
    return ok(client, "configure-notion-connection", {
        "token": TOKEN, "expectedRevision": expected,
        "credentialPolicy": SYNTHETIC_EXPORT.reference()})


def destination(client, connection: dict, page: str) -> dict:
    listed = ok(client, "list-export-destinations", {"connectionId": connection["connectionId"]})
    entry = next(item for item in listed["destinations"]
                 if item["destinationId"].replace("-", "") == page)
    return {key: entry[key] for key in ("connectionId", "workspaceId", "parentPageId",
                                        "formatRevision", "destinationId")}


def approved(client, source: dict, target: dict, *, key=None) -> dict:
    preview = ok(client, "prepare-export-preview", {
        "source": source, "destination": target, "renderPolicy": SYNTHETIC_EXPORT.reference()})
    approval = ok(client, "approve-export-preview", {
        "previewId": preview["previewId"], "previewRevision": preview["revision"],
        "bindingHash": preview["bindingHash"], "explicitApproval": True}, key=key)
    return approval


def execute_body(approval: dict) -> dict:
    return {"approvalId": approval["approvalId"], "bindingHash": approval["bindingHash"]}


def effect_row(connect, effect_id) -> dict:
    with connect("export") as conn:
        return conn.execute("SELECT state,outcome_reason,xmin::text AS x FROM export.effect "
                            "WHERE id=%s", (effect_id,)).fetchone()


def approval_row(connect, approval_id) -> dict:
    with connect("export") as conn:
        return conn.execute("SELECT state,invalidation_reason,xmin::text AS x FROM "
                            "export.approval WHERE id=%s", (approval_id,)).fetchone()


def wait_idle(lane) -> None:
    deadline = time.monotonic() + IDLE_SECONDS
    while not lane.idle and time.monotonic() < deadline:
        time.sleep(0.05)
    assert lane.idle, "the export lane never went idle"


def passes_until(host, done) -> None:
    """Bounded worker passes (at most four), each followed by the lane's idle, until
    `done()` holds; fails if it never does."""
    for _ in range(PASSES):
        if done():
            return
        host.composition.worker.run_once(limit=1)
        wait_idle(host.lane)
    assert done(), "the item never reached its outcome within four passes"


def ended(connect, effect_id) -> bool:
    return effect_row(connect, effect_id)["state"] not in ("accepted", "executing")


# --- P8 -------------------------------------------------------------------------------


def test_an_export_accept_records_the_effect_and_answers_at_once(host, sign_in_account,
                                                                 connect):
    authority, _ = signed_in(host, sign_in_account, connect)
    source = novelty(host, authority)
    connection = connected(host.client)
    target = destination(host.client, connection, host.practice)
    key = uuid4()
    approval = approved(host.client, source, target, key=key)
    # The approve's destination read (U6's BR3.1 check) is counted apart.
    requests = len(host.fake.requests)
    effect = ok(host.client, "execute-approved-export", execute_body(approval), key=key)
    assert effect["state"] == "accepted"
    assert len(host.fake.requests) == requests  # nothing reached Notion
    row = effect_row(connect, effect["effectId"])
    assert row["state"] == "accepted"
    consumed = approval_row(connect, approval["approvalId"])
    assert consumed["state"] == "consumed"
    assert row["x"] == consumed["x"]  # `bind_effect`: one statement
    again = ok(host.client, "execute-approved-export", execute_body(approval), key=key)
    assert again["effectId"] == effect["effectId"]
    writes = len(host.fake.writes)
    passes_until(host, lambda: ended(connect, effect["effectId"]))
    assert len(host.fake.writes) == writes + 1
    assert effect_row(connect, effect["effectId"])["state"] == "succeeded"


# --- L1-7 ------------------------------------------------------------------------------


def history_entry(client, approval_id: str) -> dict:
    page = ok(client, "list-export-history", {"limit": 20})
    return next(entry for entry in page["entries"] if entry["approvalId"] == approval_id)


def test_a_continued_export_is_accepted_as_the_decision_says(host, sign_in_account, connect,
                                                             own_address):
    authority, email = signed_in(host, sign_in_account, connect)
    source = novelty(host, authority)
    connection = connected(host.client)
    target = destination(host.client, connection, host.practice)
    approval = approved(host.client, source, target)
    with fresh_client(host, address=own_address) as second:
        assert sign_in(second, email).status_code == 200
        requests = len(host.fake.requests)
        effect = ok(second, "execute-approved-export", execute_body(approval))
        assert effect["state"] == "accepted"
        assert len(host.fake.requests) == requests
        # The destination changes before the lane's pre-write check.
        page = host.fake.page(host.practice)
        writes = len(host.fake.writes)
        page.readable = False
        try:
            passes_until(host, lambda: ended(connect, effect["effectId"]))
        finally:
            page.readable = True
        row = effect_row(connect, effect["effectId"])
        assert (row["state"], row["outcome_reason"]) == ("invalidated", "destination-changed")
        assert approval_row(connect, approval["approvalId"])["state"] == "consumed"
        assert len(host.fake.writes) == writes
        entry = history_entry(second, approval["approvalId"])
        assert entry["effect"]["effectId"] == effect["effectId"]
        assert "destination-changed" in (entry["effect"].get("outcomeReason"),
                                         entry.get("invalidationReason"))
        # A new approval in session 1, which then signs out: a continue is refused.
        later = approved(host.client, source, target)
        assert call(host.client, "/api/v2/c02/access-logout", {}).status_code == 200
        requests = len(host.fake.requests)
        refused = post_c09(second, "execute-approved-export", execute_body(later))
        assert (refused.status_code, refused.json()["code"]) == (409, "APPROVAL_REQUIRED")
        assert len(host.fake.requests) == requests
        row = approval_row(connect, later["approvalId"])
        assert (row["state"], row["invalidation_reason"]) == ("invalidated", "authority-revoked")


# --- L1-6 ------------------------------------------------------------------------------


def job_lines(caplog, job_id) -> dict:
    found = {}
    for record in caplog.records:
        if record.name != EVENTS_LOGGER:
            continue
        line = json.loads(record.getMessage())
        if line.get("jobId") == str(job_id) and line["event"] in ("job.started", "job.ended"):
            found[line["event"]] = line
    return found


def assistance_request(host, paper: dict) -> dict:
    """An assistance request on `paper` as the workspace builds it, from the options
    route and the catalog's content revision."""
    from backend.modules.summarization.u3_catalog import catalog_for

    options = ok_c06(host.client, "read-assistance-options", {"paper": paper})
    corpus = host.composition.parts["paper-corpus"]
    source = corpus["corpus_repository"].read(paper["versionId"])
    catalog = catalog_for(source, provider_ready=True, rule=corpus.get("assistance_rule"))
    glossary = ok_c06(host.client, "read-glossary", {})
    option = options["options"][0]
    return {"paper": paper, "contentRevision": catalog.content_revision,
            "contentHash": source["source_hash"], "operation": option["operation"],
            "optionId": option["optionId"], "optionsRevision": options["revision"],
            "glossaryRevision": str(glossary["revision"]), "processingPolicy": options["policy"]}


def ok_c06(client, operation: str, body: dict) -> dict:
    answer = call(client, "/api/v2/c06/" + operation, body)
    assert answer.status_code == 200, (operation, answer.text)
    return answer.json()


def origin_of(connect, owner: str, table: str, row_id) -> UUID | None:
    with connect(owner) as conn:
        return conn.execute(f"SELECT origin_request_id FROM {owner}.{table} WHERE id=%s",
                            (row_id,)).fetchone()["origin_request_id"]


def settled(connect, job_id) -> bool:
    with connect("assistance") as conn:
        row = conn.execute("SELECT state,settlement_pending FROM assistance.job WHERE id=%s",
                           (job_id,)).fetchone()
    return row["state"] in ("succeeded", "failed") and not row["settlement_pending"]


def test_each_started_job_records_its_requests_identifier(host, sign_in_account, connect,
                                                          monkeypatch, caplog):
    import backend.request_context as request_context
    from backend.modules.summarization.requests import AssistanceRequests
    from backend.modules.summarization.u3_catalog import catalog_for

    caplog.set_level(logging.DEBUG, logger=EVENTS_LOGGER)
    authority, _ = signed_in(host, sign_in_account, connect)
    source = novelty(host, authority)
    issued: list[UUID] = []

    def literal():
        value = uuid4()
        issued.append(value)
        return value

    monkeypatch.setattr(request_context, "uuid4", literal)
    planted = str(uuid4())
    host.client.headers["x-request-id"] = planted

    def accepted(path: str, body: dict, *, key=None) -> tuple[dict, UUID]:
        answer = host.client.post(path, json=body, headers={
            "origin": "https://127.0.0.1:18110", "x-csrf-token": csrf(host.client),
            "idempotency-key": str(key or uuid4())})
        assert answer.status_code == 200, (path, answer.text)
        return answer.json(), issued[-1]

    try:
        # A research turn: its context and session first, then the accept.
        research = host.composition.parts["research-workspace"]["service"]
        policy = research.policy.reference()
        context, _ = accepted("/api/v2/c07/create-research-context",
                              {"purpose": "research", "policy": policy})
        scope = {"contextId": context["contextId"], "publicPapers": [], "attachmentIds": [],
                 "webReferences": [], "scopePolicy": policy}
        session, earlier = accepted("/api/v2/c07/create-research-session",
                                    {"title": "합성 연구", "scope": scope})
        turn_key = uuid4()
        turn, turn_request = accepted("/api/v2/c07/accept-research-turn", {
            "sessionId": session["sessionId"], "scope": scope, "mode": "question",
            "text": "어텐션은 무엇을 하나요?", "policy": policy}, key=turn_key)
        stored = origin_of(connect, "research", "job", turn["jobId"])
        assert stored == turn_request
        assert stored not in (turn_key, UUID(planted), earlier)
        # An assistance job on a paper version imported through CorpusImports.
        paper = import_paper(SimpleNamespace(transactions=host.composition.transactions),
                             CHUNKS)
        body = assistance_request(host, paper)
        assist_key = uuid4()
        job, assist_request = accepted("/api/v2/c06/accept-assistance", body, key=assist_key)
        stored = origin_of(connect, "assistance", "job", job["jobId"])
        assert stored == assist_request
        assert stored not in (assist_key, UUID(planted), turn_request)
        # An export effect on its own preview and approval.
        connection = connected(host.client)
        target = destination(host.client, connection, host.practice)
        key = uuid4()
        approval = approved(host.client, source, target, key=key)
        effect, effect_request = accepted(C09 + "execute-approved-export",
                                          execute_body(approval), key=key)
        stored = origin_of(connect, "export", "effect", effect["effectId"])
        assert stored == effect_request
        assert stored not in (key, UUID(planted), assist_request)
    finally:
        del host.client.headers["x-request-id"]
        monkeypatch.undo()
    # An assistance job accepted outside a request stores NULL.
    corpus = host.composition.parts["paper-corpus"]
    requests = AssistanceRequests(
        corpus["dispatch"].admission, corpus["corpus_repository"],
        lambda value: catalog_for(value, provider_ready=True, rule=corpus.get("assistance_rule")))
    free_quota(host, authority.account_id)
    outside = requests.submit(authority, uuid4(), assistance_request(host, paper))
    assert origin_of(connect, "assistance", "job", outside["id"]) is None
    # The passes run the assistance jobs and the lane runs the effect.
    passes_until(host, lambda: settled(connect, job["jobId"]))
    passes_until(host, lambda: settled(connect, outside["id"]))
    passes_until(host, lambda: ended(connect, effect["effectId"]))
    for job_id, origin in ((job["jobId"], assist_request),
                           (effect["effectId"], effect_request)):
        lines = job_lines(caplog, job_id)
        assert set(lines) == {"job.started", "job.ended"}, (job_id, lines)
        assert {line["requestId"] for line in lines.values()} == {str(origin)}
    assert all("requestId" not in line for line in job_lines(caplog, outside["id"]).values())
