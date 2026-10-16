"""Private fixture identity and restart semantics; real setup is separately exercised."""

import hashlib
import json
import os
import stat
import sys
import time
from types import SimpleNamespace
from uuid import UUID

import pytest

from backend.artifacts import Artifact
from backend.local_profile import LocalProfile
from scripts import u4_browser_fixtures as fixtures
from scripts import verify_docsuri_u4 as runner


@pytest.fixture
def profile(tmp_path, monkeypatch):
    root = tmp_path / "run"
    root.mkdir(mode=0o700)
    monkeypatch.setattr(runner, "RUN", root)
    return LocalProfile(
        root,
        "docsuri-u4-0123456789abcdef",
        "https://127.0.0.1:18079",
        15479,
        time.time() + 300,
        "docsuri_u4",
        "research-workspace",
    )


def test_prepared_credentials_survive_restart_without_replacement(profile):
    first = fixtures.fixture_record(profile)
    raw = (profile.root / "browser-fixtures.json").read_bytes()
    second = fixtures.fixture_record(profile)
    assert second == first and (profile.root / "browser-fixtures.json").read_bytes() == raw
    assert first["accounts"]["memberA"]["password"] != first["accounts"]["memberB"]["password"]
    assert len(first["accounts"]) == 2 and first["state"] == "prepared"
    assert stat.S_IMODE((profile.root / "browser-fixtures.json").stat().st_mode) == 0o600


@pytest.mark.parametrize("damage", ["run", "account", "artifacts", "papers"])
def test_changed_fixture_identity_refuses_without_repair(profile, damage):
    value = fixtures.fixture_record(profile)
    if damage == "run":
        value["runId"] = "foreign"
    elif damage == "account":
        value["accounts"]["memberA"]["accountId"] = value["accounts"]["memberB"]["accountId"]
    elif damage == "artifacts":
        value["artifacts"] = {"foreign": {}}
    else:
        value["papers"] = []
    runner.private_json(profile.root / "browser-fixtures.json", value)
    before = (profile.root / "browser-fixtures.json").read_bytes()
    with pytest.raises(runner.Refused):
        fixtures.fixture_record(profile)
    assert (profile.root / "browser-fixtures.json").read_bytes() == before


class FixtureArtifacts:
    """Filesystem-backed test port; production PrivateArtifacts has its own tests."""

    def __init__(self, root):
        root.mkdir(mode=0o700, exist_ok=True)
        self.root = root

    def publish(self, content):
        name = hashlib.sha256(content).hexdigest()[:32] + ".blob"
        descriptor = os.open(self.root / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
        return Artifact(name, hashlib.sha256(content).hexdigest(), len(content))

    def read(self, artifact):
        return (self.root / artifact.name).read_bytes()


def test_artifact_acknowledgement_retries_do_not_republish(profile, monkeypatch):
    monkeypatch.setattr(fixtures, "PrivateArtifacts", FixtureArtifacts)
    value = fixtures.fixture_record(profile)
    fixtures.prepare_artifacts(profile, value)
    before = {p.name: p.read_bytes() for p in (profile.root / "corpus-files").iterdir()}
    fixtures.prepare_artifacts(profile, value)
    assert before == {p.name: p.read_bytes() for p in (profile.root / "corpus-files").iterdir()}
    assert len(before) == 2
    target = profile.root / "corpus-files" / value["artifacts"]["u4-paper-alpha"]["name"]
    target.write_bytes(b"changed")
    with pytest.raises(runner.Refused, match="no automatic replacement"):
        fixtures.prepare_artifacts(profile, value)
    assert target.read_bytes() == b"changed"


def test_interrupted_artifacts_remain_within_finite_allocation(profile, monkeypatch):
    monkeypatch.setattr(fixtures, "PrivateArtifacts", FixtureArtifacts)
    files = FixtureArtifacts(profile.root / "corpus-files")
    for index in range(8):
        files.publish(str(index).encode())
    with pytest.raises(runner.Refused, match="allocation exhausted"):
        fixtures.prepare_artifacts(profile, fixtures.fixture_record(profile))
    assert len(list(files.root.iterdir())) == 8


def test_acknowledged_artifact_loss_never_republishes_implicitly(profile):
    value = fixtures.fixture_record(profile)
    value["state"] = "ready"
    runner.private_json(profile.root / "browser-fixtures.json", value)
    with pytest.raises(runner.Refused, match="acknowledged"):
        fixtures.fixture_record(profile)


class SeedConnection:
    def __init__(self, fixture_value, *, count=0, created=True, existing=()):
        self.fixtures, self.count, self.created, self.existing = (
            fixture_value,
            count,
            created,
            existing,
        )
        self.calls = []
        self.last = ""
        self.params = None

    def execute(self, sql, params=None):
        self.calls.append((sql, params))
        self.last, self.params = sql, params
        return self

    def fetchall(self):
        assert self.last.startswith("SELECT id,email")
        return self.existing

    def fetchone(self):
        if "count(*) AS count FROM accounts" in self.last:
            return {"count": self.count}
        if self.last.startswith("INSERT INTO corpus.version"):
            return {"id": self.params[0]} if self.created else None
        if self.last.startswith("SELECT source_hash,private_path"):
            paper = next(p for p in fixtures.PAPERS if p["versionId"] == self.params[0])
            artifact = self.fixtures["artifacts"][paper["paperId"]]
            return {"source_hash": artifact["sha256"], "private_path": artifact["name"]}
        if "AS digest FROM" in self.last:
            return {"digest": "a" * 64}
        raise AssertionError("unexpected fixture read")


def test_account_and_usage_retry_cannot_restore_restrictions_or_spent_quota(profile):
    value = fixtures.fixture_record(profile)
    existing = [
        {"id": UUID(v["accountId"]), "email": v["email"]} for v in value["accounts"].values()
    ]
    conn = SeedConnection(value, count=20, existing=existing)
    fixtures.seed_accounts(
        conn, value, {"memberA": "synthetic-hash-a", "memberB": "synthetic-hash-b"}, profile.run_id
    )
    fixtures.seed_usage(conn, value)
    mutations = [sql for sql, params in conn.calls if sql.startswith("INSERT")]
    assert len(mutations) == 6
    assert all("DO NOTHING" in sql for sql in mutations)
    assert not any(
        "UPDATE" in sql or "DELETE" in sql or "replication_role" in sql
        for sql, params in conn.calls
    )


def test_account_capacity_and_foreign_identity_refuse_before_insertion(profile):
    value = fixtures.fixture_record(profile)
    conn = SeedConnection(value, count=19)
    with pytest.raises(runner.Refused, match="allocation exhausted"):
        fixtures.seed_accounts(conn, value, {}, profile.run_id)
    assert not any(sql.startswith("INSERT") for sql, _ in conn.calls)
    conn = SeedConnection(
        value,
        count=1,
        existing=[
            {
                "id": UUID(value["accounts"]["memberA"]["accountId"]),
                "email": "other@fixture.invalid",
            }
        ],
    )
    with pytest.raises(runner.Refused, match="identity"):
        fixtures.seed_accounts(conn, value, {}, profile.run_id)


@pytest.mark.parametrize("created", [True, False])
def test_corpus_retry_preserves_withdrawal_and_publication_identity(profile, monkeypatch, created):
    monkeypatch.setattr(fixtures, "PrivateArtifacts", FixtureArtifacts)
    value = fixtures.fixture_record(profile)
    fixtures.prepare_artifacts(profile, value)
    conn = SeedConnection(value, created=created)
    fixtures.seed_corpus(conn, value, profile.run_id)
    statements = [sql for sql, _ in conn.calls]
    assert not any(
        "UPDATE corpus.version" in sql or "UPDATE corpus.paper" in sql for sql in statements
    )
    assert any("UPDATE corpus.publication" in sql for sql in statements) is created
    assert sum("INSERT INTO corpus.projection" in sql for sql in statements) == (
        2 if created else 0
    )


def test_setup_reconciles_each_owner_then_acknowledges_without_reset(profile, monkeypatch):
    monkeypatch.setattr(fixtures, "PrivateArtifacts", FixtureArtifacts)
    monkeypatch.setattr(runner, "manifest", lambda path: (profile, {"runId": profile.run_id}))
    monkeypatch.setattr(runner, "require_resources", lambda value: None)
    monkeypatch.setattr(runner, "require_stopped", lambda: None)
    calls = []

    class Transactions:
        def __init__(self, profile, **kwargs):
            assert kwargs == {"process": "maintenance"}

        def run(self, owner, action):
            calls.append(owner)
            value = json.loads((profile.root / "browser-fixtures.json").read_bytes())
            return action(SeedConnection(value))

        def close(self):
            calls.append("closed")

    monkeypatch.setattr(fixtures, "OwnerTransactions", Transactions)
    monkeypatch.setattr(
        fixtures,
        "GuardedEntryService",
        lambda tx: SimpleNamespace(_hash_password=lambda text: "synthetic-hash"),
    )
    assert fixtures.setup(profile.root / "environment.json")["state"] == "fixtures-ready"
    assert calls == ["accounts", "usage", "corpus", "closed"]
    value = fixtures.fixture_record(profile)
    assert value["state"] == "ready"
    before = (profile.root / "browser-fixtures.json").read_bytes()
    fixtures.setup(profile.root / "environment.json")
    assert (profile.root / "browser-fixtures.json").read_bytes() == before


def test_cli_prints_only_safe_fixture_counts(profile, monkeypatch, capsys):
    monkeypatch.setattr(fixtures, "setup", lambda path: {"state": "fixtures-ready", "accounts": 2})
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "fixtures",
            "--environment-file",
            str(profile.root / "environment.json"),
            "--action",
            "setup",
        ],
    )
    assert fixtures.main() == 0
    assert json.loads(capsys.readouterr().out) == {"state": "fixtures-ready", "accounts": 2}
