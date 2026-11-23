"""U6:security-design:log-content: failures log fixed names and classes only.

The pass logs a failed step's name and exception class; the write path surfaces nothing
under `docsuri.export*` (the dedicated SDK logger alone keeps the SDK's own warning
records, off the root); no surfaced line or stored row carries the token, the provider's
message text, the API host or a created page id. Every stored provider fact is a
validated id.
"""

import json
import logging

import psycopg
import pytest

from backend.modules.export import classification
from backend.modules.export import notion_adapter as adapter_module
from backend.modules.export.fake_notion import SAVED_BUSY, Answer
from backend.modules.export.repository import WriteOutcome
from backend.modules.export.worker import ExportPass, ExportPassIncomplete
from tests.u6_approved_export import lane_flows as lane
from tests.u6_approved_export import notion_flows as nf

# One representative answer per failure class a write can meet; each is queued on the
# create and on the read-backs, like the token-exposure matrix does.
FAILURES = [
    Answer.error(401),
    Answer.error(403),
    Answer.block_limit(),
    Answer.error(404),
    Answer.rate_limited(wait=0),
    Answer.error(500),
    Answer.error(503),
    Answer.of(SAVED_BUSY),
]


class Faulty(lane.OwnDue):
    """The real store, with the orphan sweep failing the way a database fault would."""

    def sweep_orphans(self, now):
        raise psycopg.OperationalError("store down: synthetic-secret-detail")


def test_a_failing_pass_step_logs_only_its_name_and_class(
    transactions, connect, authority, tmp_path, caplog
):
    rig = lane.build(transactions, connect, authority, tmp_path)
    caplog.set_level(logging.DEBUG, logger="docsuri.export.worker")
    step = ExportPass(
        Faulty(rig.repo, []),
        rig.rig.research,
        lane.LaneDouble(),
        policy=rig.rig.policy,
        clock=rig.clock,
    )

    with pytest.raises(ExportPassIncomplete) as caught:
        step.run_once()

    assert caught.value.steps == ("orphans",)
    records = [record for record in caplog.records if record.name == "docsuri.export.worker"]
    assert [record.getMessage() for record in records] == [
        "export pass step orphans failed (OperationalError)"
    ]
    record = records[0]
    assert record.exc_info is None
    assert all(isinstance(argument, str) for argument in record.args)
    assert "synthetic-secret-detail" not in caplog.text


@pytest.fixture
def write_rig(transactions, connect, authority, tmp_path, caplog):
    policy = nf.policy(
        write_deadline_seconds=1,
        read_timeout_seconds=1,
        page_read_budget_seconds=1,
        read_back_budget_seconds=1,
    )
    repo = nf.repository(transactions, policy)
    opener = nf.vault(tmp_path)
    token, bot = nf.synthetic_token(), nf.bot_id()
    fake = nf.fake_with(token, bot)
    target, connection = nf.stored_connection(repo, connect, authority, opener, token, user=bot)
    destination = fake.add_page(title="대상")
    return {
        "policy": policy,
        "repo": repo,
        "vault": opener,
        "token": token,
        "bot": bot,
        "fake": fake,
        "target": target,
        "connection": connection,
        "destination": destination,
        "adapter": nf.adapter(repo, opener, fake, policy),
        "caplog": caplog,
    }


async def attempt(rig, authority, answer):
    """One bound effect, written through the adapter with `answer` queued, recorded as
    the lane would record it so the effect leaves the owner's in-flight slot. A
    token-invalid answer revokes the connection, so the same token is re-connected at
    its current revision before the next bound effect."""
    connection = rig["repo"].read_connection(authority)
    if connection["state"] != "connected":
        connection = nf.replace_token(
            rig["repo"], authority, rig["vault"], rig["token"], user=rig["bot"]
        )
    bound = nf.bound_effect(rig["repo"], authority, connection, rig["destination"])
    claimed = rig["repo"].claim(
        bound["effect"]["id"], bound["effect"]["revision"], now=nf.now()
    )
    rig["fake"].queue("pages.create", answer)
    for _ in range(4):
        rig["fake"].queue("pages.retrieve", answer)
    result = await rig["adapter"].create_page(
        rig["target"],
        nf.write_request(bound, connection, rig["bot"]),
        deadline_seconds=1,
    )
    recorded = rig["repo"].record_write_outcome(
        bound["effect"]["id"],
        claimed.attempt["id"],
        claimed.effect["revision"],
        result.outcome or WriteOutcome("uncertain"),
        now=nf.now(),
    )
    if recorded is not None and recorded["state"] == "executing":
        rig["repo"].end_unwritten(
            bound["effect"]["id"],
            recorded["revision"],
            "rate-limit-budget-spent",
            now=nf.now(),
        )
    return result


async def test_no_export_record_appears_for_any_write_failure(write_rig, authority):
    rig = write_rig
    surfaced = []

    class Capture(logging.Handler):
        def emit(self, record):
            surfaced.append(record)

    capture = Capture()
    logging.getLogger().addHandler(capture)
    pinned = {
        name: logging.getLogger(name).level
        for name in ("", "httpx", "httpcore", "notion_client")
    }
    try:
        for name in ("httpx", "httpcore"):
            logging.getLogger(name).setLevel(logging.WARNING)
        for name in ("", "notion_client"):
            rig["caplog"].set_level(logging.DEBUG, logger=name)
        for answer in FAILURES:
            result = await attempt(rig, authority, answer)
            assert result is not None
    finally:
        logging.getLogger().removeHandler(capture)
        for name, level in pinned.items():
            logging.getLogger(name).setLevel(level)

    # Over the whole failure matrix nothing surfaced to the application log: no export
    # module, transport or SDK record reaches the root, and the dedicated SDK logger
    # stays off it entirely (it alone keeps the SDK's own warning records).
    assert not any(
        record.name.startswith(("docsuri.export", "notion_client", "httpx", "httpcore"))
        for record in surfaced
    )
    text = "\n".join(record.getMessage() for record in surfaced) + json.dumps(
        [str(vars(record)) for record in surfaced]
    )
    assert rig["token"] not in text
    assert "synthetic answer" not in text
    assert "api.notion.com" not in text
    for page_id in [rig["destination"], *rig["fake"].pages_under(rig["destination"])]:
        assert page_id not in text


async def test_stored_rows_hold_no_provider_text_and_only_patterned_ids(
    write_rig, authority, connect
):
    rig = write_rig
    await attempt(rig, authority, Answer.error(403))
    await attempt(rig, authority, Answer.of(SAVED_BUSY))

    with connect("export") as conn:
        effects = conn.execute(
            "SELECT coalesce(string_agg(to_jsonb(e)::text,' '),'') AS text FROM export.effect e "
            "WHERE e.account_id=%s",
            (authority.account_id,),
        ).fetchone()["text"]
        attempts = conn.execute(
            "SELECT coalesce(string_agg(to_jsonb(a)::text,' '),'') AS text FROM export.attempt a "
            "JOIN export.effect e ON e.id=a.effect_id WHERE e.account_id=%s",
            (authority.account_id,),
        ).fetchone()["text"]
        lane_status = conn.execute(
            "SELECT coalesce(string_agg(to_jsonb(s)::text,' '),'') AS text "
            "FROM export.lane_status s"
        ).fetchone()["text"]
        rows = conn.execute(
            "SELECT a.provider_request_id,e.remote_url FROM export.attempt a "
            "JOIN export.effect e ON e.id=a.effect_id WHERE e.account_id=%s",
            (authority.account_id,),
        ).fetchall()

    created = rig["fake"].pages_under(rig["destination"])
    for text in (effects, attempts, lane_status):
        assert rig["token"] not in text
        assert "synthetic answer" not in text
        assert "api.notion.com" not in text
        assert all(page_id not in text for page_id in created)
    for row in rows:
        if row["provider_request_id"] is not None:
            assert classification._REQUEST_ID.fullmatch(row["provider_request_id"])
        if row["remote_url"] is not None:
            assert adapter_module._NOTION_URL.fullmatch(row["remote_url"])
