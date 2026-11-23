"""U6:NFR6.3/real-export-approval: the real policy gates one approved real export (L1-3).

Six steps over the real activation policy: the factory and its capability row, the
listing scoped to the activation destination, one approved export written exactly once,
the refusals that write nothing, the replay and skip behaviour, and the operator
outcome's digests only. The keyring lives under `tmp_path`, never the realm's folder;
each test makes the fewest requests, because the real policy paces at 500 ms.
"""

import datetime as dt
import json
from uuid import UUID, uuid4

from backend.modules.accounts.services.guarded_entry import GuardedEntryService
from backend.u6_real_export import parse_activation, real_export_factory, real_policy
from scripts.u6_real_export import outcome as real_outcome
from tests.u6_approved_export import lane_flows as lf
from tests.u6_approved_export import notion_flows as nf
from tests.u6_approved_export import service_flows as sf

RUN = "docsuri-u6-0123456789abcdef"
DESTINATION = "0123456789abcdef0123456789abcdef"
TODAY = dt.date(2026, 10, 20)


def settings(**overrides) -> dict:
    terms = {
        "plan": "free",
        "memberCount": 1,
        "checkedOn": "2026-10-19",
        "publishedLimits": ["Free plan block limit for workspaces with two or more members"],
    }
    terms.update(overrides.pop("freeTerms", {}))
    return {"runId": RUN, "activationDestinationId": DESTINATION, "freeTerms": terms, **overrides}


class Inherited:
    def run_once(self, limit=1):
        return {"limit": limit}


def activation_for(realm, page: str):
    return parse_activation(
        settings(runId=realm.run_id, activationDestinationId=page), realm, today=TODAY
    )


def real_rig(transactions, connect, authority, realm, tmp_path) -> tuple:
    """A lane rig under the real policy whose activation page is a fresh fake page."""
    page = uuid4().hex
    activation = activation_for(realm, page)
    built = lf.build(
        transactions,
        connect,
        authority,
        tmp_path,
        keys="real-keys",
        policy=real_policy(activation),
    )
    built.rig.fake.add_page(page, title="활성")
    built.rig.configure()
    return built, activation, page


def exported(transactions, connect, authority, realm, tmp_path) -> tuple:
    """One pressed export, written through the real lane, plus its other fake page."""
    built, activation, page = real_rig(transactions, connect, authority, realm, tmp_path)
    other = built.rig.fake.add_page(title="다른 곳")
    flow = built.rig.press(page, built.rig.research.ready())
    assert built.lane.run_item(lf.item(flow["effect"])) != "skipped"
    return built, activation, page, other, flow


def test_the_factory_carries_the_real_policy_and_the_real_row(transactions, realm):
    activation = activation_for(realm, DESTINATION)
    factory = real_export_factory(activation)
    assert factory.keywords["policy"] == real_policy(activation)

    fake = nf.fake_with(nf.synthetic_token(), nf.bot_id())
    built = factory(
        transactions,
        GuardedEntryService(transactions),
        None,
        Inherited(),
        research=sf.ResearchDouble(),
        transport_factory=lambda: fake,
    )

    assert built["capabilities"] == [
        {
            "id": "export",
            "state": "degraded",
            "modeIds": ["real-bounded"],
            "languageIds": ["ko"],
            "levelIds": [],
            "formatIds": ["notion"],
            "policy": real_policy(activation).reference(),
        }
    ]


def test_only_the_activation_destination_is_usable(
    transactions, connect, authority, realm, tmp_path
):
    built, activation, page = real_rig(transactions, connect, authority, realm, tmp_path)
    other = built.rig.fake.add_page(title="다른 곳")
    assert built.rig.policy == real_policy(activation)
    assert built.rig.service.vault._keys.root == tmp_path / "real-keys"

    listing = built.rig.service.list_destinations(authority, {})

    entries = {item["destinationId"]: item for item in listing["destinations"]}
    assert entries[page]["writable"] is True
    assert entries[other]["writable"] is False
    assert built.rig.connection()["destinationScopeIds"] == [page]

    asked = len(built.rig.fake.requests)
    assert sf.refuse("prepare_preview", lambda: built.rig.preview(other)) == "FORBIDDEN"
    assert len(built.rig.fake.requests) == asked

    built.rig.approve(built.rig.preview(page))
    assert built.rig.fake.writes == []
    step = lf.own_step(built, lf.LaneDouble(), [])
    assert step.run_once()["handedOver"] is None
    assert built.rig.fake.writes == []


def test_one_approved_export_writes_exactly_one_page(
    transactions, connect, authority, realm, tmp_path
):
    built, _, page, other, flow = exported(transactions, connect, authority, realm, tmp_path)
    preview, effect = flow["preview"], flow["effect"]

    created = built.rig.fake.pages_under(page)
    assert len(created) == 1 and built.rig.fake.pages_under(other) == []
    assert built.rig.fake.writes[0].content_hash == preview["renderedContentHash"]
    attempts = lf.attempts(connect, effect)
    assert attempts[-1]["response_class"] == "created"
    with connect("export") as conn:
        path_kind = conn.execute(
            "SELECT path_kind FROM export.attempt WHERE effect_id=%s",
            (UUID(effect["effectId"]),),
        ).fetchone()["path_kind"]
    assert path_kind == "real"
    assert lf.row(connect, effect)["state"] == "succeeded"


def test_the_refusals_write_nothing_and_leave_counts_untouched(
    transactions, connect, authority, realm, tmp_path
):
    built, _, page = real_rig(transactions, connect, authority, realm, tmp_path)
    source = built.rig.research.ready()
    stale = built.rig.preview(page, source)
    fresh = built.rig.preview(page, source)
    approval = built.rig.approve(fresh)

    with connect("export") as conn:
        before = {
            table: conn.execute(
                f"SELECT count(*) AS n FROM export.{table} WHERE account_id=%s",
                (authority.account_id,),
            ).fetchone()["n"]
            for table in ("approval", "effect")
        }

    assert (
        sf.refuse(
            "execute",
            lambda: built.rig.service.execute(
                authority,
                {"approvalId": str(uuid4()), "bindingHash": "f" * 64},
                operation=uuid4(),
            ),
        )
        == "NOT_FOUND"
    )
    assert (
        sf.refuse(
            "execute",
            lambda: built.rig.service.execute(
                authority,
                {"approvalId": approval["approvalId"], "bindingHash": stale["bindingHash"]},
                operation=uuid4(),
            ),
        )
        == "CONFLICT"
    )
    assert (
        sf.refuse(
            "approve",
            lambda: built.rig.service.approve(
                authority,
                {**built.rig.approval_value(stale), "explicitApproval": False},
                operation=uuid4(),
            ),
        )
        == "INVALID_ARGUMENT"
    )

    with connect("export") as conn:
        after = {
            table: conn.execute(
                f"SELECT count(*) AS n FROM export.{table} WHERE account_id=%s",
                (authority.account_id,),
            ).fetchone()["n"]
            for table in ("approval", "effect")
        }
    assert after == before
    assert built.rig.fake.writes == []


def test_a_replayed_execute_and_a_second_item_are_skipped(
    transactions, connect, authority, realm, tmp_path
):
    built, _, page = real_rig(transactions, connect, authority, realm, tmp_path)
    source = built.rig.research.ready()
    stale = built.rig.preview(page, source)
    fresh = built.rig.preview(page, source)

    assert (
        sf.refuse(
            "approve",
            lambda: built.rig.service.approve(
                authority, built.rig.approval_value(stale), operation=uuid4()
            ),
        )
        == "CONFLICT"
    )

    key = uuid4()
    approval = built.rig.approve(fresh, key=key)
    effect = built.rig.execute(approval, key=key)
    again = built.rig.execute(approval, key=key)
    assert again["effectId"] == effect["effectId"]

    assert built.lane.run_item(lf.item(effect)) != "skipped"
    assert built.lane.run_item(lf.item(effect)) == "skipped"
    assert len(built.rig.fake.writes) == 1
    assert len(lf.attempts(connect, effect)) == 1


def test_the_operator_outcome_reports_digests_only(
    transactions, connect, authority, realm, tmp_path
):
    built, activation, page, _, flow = exported(
        transactions, connect, authority, realm, tmp_path
    )

    record = real_outcome(
        transactions, realm, activation, effect_id=UUID(flow["effect"]["effectId"]), today=TODAY
    )

    assert record["pathKind"] == "real"
    assert record["outcomeClass"] == "created"
    assert record["effectState"] == "succeeded"
    assert len(record["requestIdSha256"]) == 64
    assert len(record["pageLinkSha256"]) == 64
    dump = json.dumps(record)
    created = built.rig.fake.pages_under(page)[0]
    request_id = lf.attempts(connect, flow["effect"])[0]["provider_request_id"]
    assert request_id is not None and request_id not in dump
    assert created not in dump and "https://www.notion.so" not in dump
    assert built.rig.token not in dump
