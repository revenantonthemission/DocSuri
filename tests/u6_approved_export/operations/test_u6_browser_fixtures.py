"""The browser fixtures: restartable setup, the fake's scenario and the delegated clock."""

import contextlib
import datetime as dt
import json
from dataclasses import replace
from pathlib import Path
from uuid import UUID, uuid4

import httpx
import pytest
from backend.modules.export.fake_notion import FakeNotion
from backend.transactions import Authority
from scripts import u6_browser_fixtures as fixtures
from scripts import verify_docsuri_u6 as runner

NOTION = "https://api.notion.com"


def test_fixture_setup_is_idempotent_and_its_result_is_exportable(realm, transactions):
    path = realm.root / "environment.json"
    first = fixtures.setup(path)
    record = fixtures.fixture_record(realm)
    second = fixtures.setup(path)
    assert first == second == {
        "state": "fixtures-ready",
        "accounts": 2,
        "papers": 2,
        "noveltyResults": 1,
        "scenarioPages": 13,
        "synthetic": True,
    }
    again = fixtures.fixture_record(realm)
    assert again == record and again["state"] == "ready"
    assert again["novelty"] is not None
    # The result is a ready novelty result as U4's own export read sees it.
    service, _ = fixtures.research_ports(transactions)
    member = UUID(again["accounts"]["memberA"]["accountId"])
    session = transactions.run(
        "accounts", lambda conn: fixtures.seed_fixture_session(conn, member, realm.run_id)
    )
    novelty = again["novelty"]
    reference = {key: novelty[key] for key in ("artifactId", "revision", "contentHash")}
    read = service.readNoveltyArtifactForExport(Authority(member, session), reference)
    assert read["availability"] == "ready"
    assert read["prepared"]["kind"] == "novelty-result"


def test_the_record_refuses_any_identity_drift(realm):
    record = fixtures.fixture_record(realm)
    for changes in (
        {"runId": "docsuri-u6-fedcba9876543210"},
        {"fixtureVersion": "u6-browser-v0"},
        {"state": "unknown"},
        {"notionToken": "ntn_real-looking"},
        {"scenario": {}},
        {"novelty": {"jobId": "x"}},
    ):
        with pytest.raises(runner.Refused):
            fixtures._check_record(realm, {**record, **changes})
    account = dict(record["accounts"]["memberA"], email="someone@example.com")
    with pytest.raises(runner.Refused, match="account binding"):
        fixtures._check_record(
            realm, {**record, "accounts": {**record["accounts"], "memberA": account}}
        )
    with pytest.raises(runner.Refused, match="novelty binding"):
        fixtures._check_record(realm, {**record, "novelty": None})


def test_the_scenario_gives_each_spec_its_own_destinations(realm):
    token = "u6-synthetic-" + "0" * 40
    value = fixtures.scenario(realm.run_id, token)
    assert value["runId"] == realm.run_id and set(value["tokens"]) == {token}
    pages = {page["title"]: page for page in value["pages"] if page["title"]}
    assert [page for page in value["pages"] if page["title"] is None]
    same_title = fixtures.SCENARIO_NAMES["sameTitle"]
    same = [page for page in value["pages"] if page["title"] == same_title]
    assert len(same) == 2 and len({page["parentId"] for page in same}) == 2
    assert pages[fixtures.SCENARIO_NAMES["unreadablePage"]]["readable"] is False
    seen = set()
    for spec in ("journeys", "keyboard", "accessibility"):
        names = fixtures.SCENARIO_NAMES["specs"][spec]
        cancel, settle = pages[names["cancel"]], pages[names["settle"]]
        assert cancel["normalPageReads"] == 2
        assert settle["busyChildrenAfterCreate"] is True
        assert settle["createAnswers"] == [{"status": 504}]
        seen |= {cancel["id"], settle["id"]}
    assert len(seen) == 6
    assert fixtures.scenario(realm.run_id, token) == value


async def test_the_scenario_answers_statefully_at_the_fake(realm):
    token = "u6-synthetic-" + "1" * 40
    fake = FakeNotion.from_scenario(fixtures.scenario(realm.run_id, token), run_id=realm.run_id)
    names = fixtures.SCENARIO_NAMES["specs"]["journeys"]
    pages = {page.title: page.node_id for page in fake._nodes.values() if page.is_page}
    headers = {"Authorization": f"Bearer {token}", "Notion-Version": "2026-03-11"}
    async with httpx.AsyncClient(transport=fake, base_url=NOTION, headers=headers) as client:
        cancel = pages[names["cancel"]]
        statuses = [(await client.get(f"/v1/pages/{cancel}")).status_code for _ in range(3)]
        assert statuses == [200, 200, 503]
        settle = pages[names["settle"]]
        assert (await client.get(f"/v1/blocks/{settle}/children")).status_code == 200
        body = {
            "parent": {"page_id": settle},
            "properties": {"title": [{"text": {"content": "합성"}}]},
            "children": [],
        }
        assert (await client.post("/v1/pages", json=body)).status_code == 504
        assert (await client.get(f"/v1/blocks/{settle}/children")).status_code == 503
        assert (await client.get(f"/v1/pages/{settle}")).status_code == 200
        assert (await client.get("/v1/users/me")).status_code == 200


class FakeResearch:
    """A stand-in for U4's service and execution: one job that succeeds on its step."""

    def __init__(self, outcome="succeeded"):
        self.policy = type("Policy", (), {"reference": staticmethod(lambda: {"policyId": "p"})})
        self.usage = type("Usage", (), {"ensure_entitlement": staticmethod(lambda authority: None)})
        self.outcome, self.state, self.steps = outcome, "accepted", 0

    def readNoveltyArtifactForExport(self, authority, reference):  # noqa: N802 - U4's name
        raise LookupError("not ready")

    def create_context(self, authority, value):
        return {"contextId": str(uuid4())}

    def accept(self, authority, operation, value, kind):
        assert kind == "novelty-analysis" and value["inputMode"] == "topic"
        return {"jobId": str(uuid4())}

    def read_job(self, authority, reference):
        result = {"resultId": "a" * 8, "revision": "1", "contentHash": "c" * 64}
        done = self.state == "succeeded"
        return {"state": self.state, "result": result if done else None}

    def step(self):
        self.steps += 1
        self.state = self.outcome


def test_a_missing_result_is_produced_through_the_research_service(monkeypatch):
    research = FakeResearch()
    monkeypatch.setattr(fixtures, "research_ports", lambda transactions: (research, research))
    made = fixtures.ready_novelty(None, Authority(uuid4(), uuid4()), None)
    assert research.steps == 1
    assert set(made) == {"jobId", "contextId", "artifactId", "revision", "contentHash"}
    failed = FakeResearch("failed")
    monkeypatch.setattr(fixtures, "research_ports", lambda transactions: (failed, failed))
    with pytest.raises(runner.Refused, match="did not produce"):
        fixtures.ready_novelty(None, Authority(uuid4(), uuid4()), None)


def test_the_delegated_clock_only_moves_forward_within_its_bound(realm, tmp_path):
    profile = replace(realm, root=tmp_path)
    now = dt.datetime(2026, 10, 20, 12, tzinfo=dt.UTC)
    first = fixtures.next_instant(profile, now)
    assert first == now + dt.timedelta(hours=1)
    target = tmp_path / fixtures.CLOCK_FILE
    target.write_text(json.dumps({"runId": realm.run_id, "instant": first.isoformat()}))
    target.chmod(0o600)
    assert fixtures.next_instant(profile, now) == first + dt.timedelta(hours=1)
    far = now + dt.timedelta(days=2)
    target.write_text(json.dumps({"runId": realm.run_id, "instant": far.isoformat()}))
    with pytest.raises(runner.Refused, match="exhausted"):
        fixtures.next_instant(profile, now)
    target.write_text(json.dumps({"runId": "docsuri-u6-other", "instant": first.isoformat()}))
    with pytest.raises(runner.Refused, match="another run"):
        fixtures.next_instant(profile, now)


def _file_state(path):
    """The file's existence and bytes, so a check holds on a fresh and a used environment."""
    return (True, path.read_bytes()) if path.exists() else (False, None)


def test_a_clock_advance_without_the_parent_capability_refuses(realm, monkeypatch):
    monkeypatch.setenv(runner.CLOCK_CAPABILITY, "not-the-capability")
    # A browser run leaves its clock file behind, so the refusal is judged by what it
    # did to that file: neither created nor changed it.
    clock = realm.root / fixtures.CLOCK_FILE
    before = _file_state(clock)
    # No browser phase holds a delegation here, so the grant itself is absent.
    with pytest.raises((runner.Refused, OSError)):
        fixtures.main(
            [
                "--environment-file",
                str(realm.root / "environment.json"),
                "--action",
                "advance-clock",
            ]
        )
    assert _file_state(clock) == before


def test_the_setup_action_runs_under_the_runner_lock(realm, monkeypatch, capsys):
    monkeypatch.setattr(runner, "exclusive", contextlib.nullcontext)
    path = str(realm.root / "environment.json")
    assert fixtures.main(["--environment-file", path, "--action", "setup"]) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["state"] == "fixtures-ready" and "notionToken" not in json.dumps(printed)
    assert Path(realm.root / fixtures.SCENARIO_FILE).is_file()
