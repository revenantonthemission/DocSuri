"""The operator's real-export steps: every settings gap named, digests-only evidence.

Settings files are written only into `tmp_path`, never into an environment folder; the
outcome is read from an export recorded by the synthetic rig over the fake Notion.
"""

import datetime as dt
import json
from dataclasses import replace
from uuid import UUID

import pytest
from backend.u6_real_export import parse_activation
from scripts import u6_real_export as operator

from tests.u6_approved_export import service_flows as sf

TODAY = dt.date(2026, 10, 20)


def settings(run_id: str, **changes) -> dict:
    value = {
        "runId": run_id,
        "activationDestinationId": "0123456789abcdef0123456789abcdef",
        "freeTerms": {
            "plan": "free",
            "memberCount": 1,
            "checkedOn": "2026-10-19",
            "publishedLimits": ["free workspace block limit as published"],
        },
    }
    value.update(changes)
    return value


@pytest.fixture
def operator_root(realm, tmp_path):
    """A profile whose folder is `tmp_path`: the settings never reach the environment."""
    profile = replace(realm, root=tmp_path)

    def write(value, *, raw: bytes | None = None, mode: int = 0o600):
        target = tmp_path / "real-export.json"
        target.write_bytes(raw if raw is not None else json.dumps(value).encode())
        target.chmod(mode)
        return target

    return profile, write


def test_complete_settings_are_ready(operator_root, realm):
    profile, write = operator_root
    write(settings(realm.run_id))
    assert operator.check(profile, today=TODAY) == {"action": "check", "state": "ready", "gaps": []}


def test_every_settings_gap_is_named(operator_root, realm):
    profile, write = operator_root
    write(
        {
            "runId": "docsuri-u6-fedcba9876543210",
            "activationDestinationId": "not-a-page",
            "freeTerms": {
                "plan": "plus",
                "memberCount": 2,
                "checkedOn": "2026-12-31",
                "publishedLimits": [],
                "extra": True,
            },
            "token": "never-allowed",
        }
    )
    assert operator.settings_gaps(profile, today=TODAY) == [
        "settings",
        "runId",
        "activationDestinationId",
        "freeTerms",
        "freeTerms.plan",
        "freeTerms.memberCount",
        "freeTerms.checkedOn",
        "freeTerms.publishedLimits",
    ]
    assert operator.check(profile, today=TODAY)["state"] == "gaps"


@pytest.mark.parametrize(
    ("case", "expected"),
    [
        ("absent", ["settings-absent"]),
        ("custody", ["settings-custody"]),
        ("json", ["settings"]),
        ("not-object", ["settings"]),
        ("terms-not-object", ["freeTerms"]),
        ("bad-date", ["freeTerms.checkedOn"]),
        ("evidence", ["environment"]),
    ],
)
def test_each_settings_gap_alone(operator_root, realm, case, expected):
    profile, write = operator_root
    if case == "custody":
        write(settings(realm.run_id), mode=0o644)
    elif case == "json":
        write(None, raw=b"{not json")
    elif case == "not-object":
        write(["settings"])
    elif case == "terms-not-object":
        write(settings(realm.run_id, freeTerms="free"))
    elif case == "bad-date":
        write(settings(realm.run_id, freeTerms={**settings("x")["freeTerms"], "checkedOn": "2026-02-30"}))
    elif case == "evidence":
        write(settings(realm.run_id))
        (profile.root / "browser-evidence-1.json").write_text("{}")
    assert operator.settings_gaps(profile, today=TODAY) == expected


def test_the_outcome_holds_digests_only(realm, transactions, connect, authority, tmp_path):
    rig = sf.build(transactions, connect, authority, tmp_path)
    rig.configure()
    pressed = rig.press(rig.page())
    rig.succeed(pressed["effect"])
    activation = parse_activation(settings(realm.run_id), realm, today=TODAY)
    effect_id = UUID(pressed["effect"]["effectId"])
    record = operator.outcome(
        transactions, realm, activation, effect_id=effect_id, source_commit="0" * 40, today=TODAY
    )
    assert set(record) == {
        "action",
        "date",
        "runId",
        "sourceCommit",
        "freeTermsReference",
        "effectState",
        "outcomeReason",
        "settledBy",
        "outcomeClass",
        "pathKind",
        "creatorConfirmed",
        "requestIdSha256",
        "pageLinkSha256",
        "retentionDeadline",
    }
    assert record["effectState"] == "succeeded" and record["outcomeClass"] == "created"
    assert record["retentionDeadline"] == "2026-10-27"
    for field in ("requestIdSha256", "pageLinkSha256"):
        assert len(record[field]) == 64
    text = json.dumps(record)
    stored = transactions.run(
        "export",
        lambda conn: conn.execute(
            "SELECT e.remote_url,a.provider_request_id FROM export.effect e "
            "JOIN export.attempt a ON a.effect_id=e.id WHERE e.id=%s",
            (effect_id,),
        ).fetchone(),
    )
    for plaintext in (rig.token, stored["remote_url"], stored["provider_request_id"]):
        assert plaintext not in text
    assert "DocSuri" not in text


class Rows:
    """Answers the outcome query with fixed rows, so the count rule is tested exactly."""

    def __init__(self, rows):
        self.rows = rows

    def run(self, owner, action):
        assert owner == "export"
        return self.rows


def test_the_outcome_names_exactly_one_export(realm):
    activation = parse_activation(settings(realm.run_id), realm, today=TODAY)
    row = {
        "state": "failed",
        "outcome_reason": "no-access",
        "settled_by": "provider",
        "remote_url": None,
        "response_class": "refused",
        "provider_request_id": None,
        "creator_confirmed": None,
        "path_kind": "real",
    }
    for rows in ([], [row, row]):
        with pytest.raises(operator.OutcomeRefused, match="exactly-one"):
            operator.outcome(Rows(rows), realm, activation, today=TODAY)
    record = operator.outcome(Rows([row]), realm, activation, today=TODAY)
    assert (record["requestIdSha256"], record["pageLinkSha256"]) == (None, None)
    assert record["pathKind"] == "real" and record["outcomeReason"] == "no-access"
    other = replace(activation, run_id="docsuri-u6-fedcba9876543210")
    with pytest.raises(operator.OutcomeRefused, match="run-differs"):
        operator.outcome(Rows([row]), realm, other)


def test_the_actions_refuse_the_wrong_realm_and_missing_settings(realm, capsys):
    with pytest.raises(ValueError, match="approved-export"):
        operator.run_action("check", replace(realm, realm="topics-digests"), None)
    path = str(realm.root / "environment.json")
    # The environment holds no settings: check names it, outcome refuses it.
    assert operator.main(["--environment-file", path, "--action", "check"]) == 1
    checked = json.loads(capsys.readouterr().out)
    assert checked["state"] == "gaps" and "settings-absent" in checked["gaps"]
    assert operator.main(["--environment-file", path, "--action", "outcome"]) == 1
    refused = json.loads(capsys.readouterr().out)
    assert refused == {"state": "refused", "category": "POLICY_UNRESOLVED", "field": "settings-absent"}
    assert not (realm.root / "real-export.json").exists()
    assert operator.source_commit() is None or len(operator.source_commit()) == 40
