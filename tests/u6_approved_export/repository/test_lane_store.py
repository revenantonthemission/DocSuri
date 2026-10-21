"""Lane and pass units: due order, the atomic claim, outcomes, scans, orphans and facts."""

import datetime as dt
from uuid import uuid4

import pytest
from backend.modules.export.errors import ExportError
from backend.modules.export.repository import CheckResult, Claimed, ClaimRefused, WriteOutcome

from tests.u6_approved_export import store_flows as flows

# Due-order runs on an early injected clock, so its items sort ahead of the realm's
# accumulated real-time rows within each priority, and later rows are not yet due.
EPOCH = dt.datetime(2001, 1, 1, tzinfo=dt.UTC)
EVIDENCE = "f" * 64


def rate_limited(repo, effect, now, retry_after_seconds=50):
    claimed = repo.claim(effect["id"], effect["revision"], now=now)
    return repo.record_write_outcome(
        effect["id"],
        claimed.attempt["id"],
        claimed.effect["revision"],
        WriteOutcome("rate-limited", retry_at=flows.at(retry_after_seconds, base=now)),
        now=now,
    )


def test_due_items_follow_the_hand_over_order(transactions, connect, authority, authority_b):
    """Security design §8.1: resumable executing, then oldest accepted, then due scans."""
    repo = flows.repository(transactions)
    connection = flows.connected(repo, connect, authority, EPOCH)
    unknown = flows.uncertain(
        repo, flows.bound(repo, authority, connection, EPOCH)["effect"], EPOCH
    )
    resumable = rate_limited(
        repo,
        flows.bound(repo, authority, connection, flows.at(1, base=EPOCH))["effect"],
        flows.at(1, base=EPOCH),
    )
    other = flows.connected(repo, connect, authority_b, EPOCH)
    accepted = flows.bound(repo, authority_b, other, flows.at(2, base=EPOCH))["effect"]

    early = repo.due_items(flows.at(40, base=EPOCH), limit=100)
    assert accepted["id"] in [item["id"] for item in early]
    assert not {resumable["id"], unknown["id"]} & {item["id"] for item in early}
    due = repo.due_items(flows.at(300, base=EPOCH), limit=100)
    ours = [item for item in due if item["id"] in {resumable["id"], accepted["id"], unknown["id"]}]
    assert [(item["kind"], item["id"]) for item in ours] == [
        ("resume", resumable["id"]),
        ("execute", accepted["id"]),
        ("scan", unknown["id"]),
    ]
    priorities = [("resume", "execute", "scan").index(item["kind"]) for item in due]
    assert priorities == sorted(priorities)
    with pytest.raises(ExportError):
        repo.due_items(EPOCH, limit=0)


def test_the_claim_and_its_attempt_land_in_one_transaction(transactions, connect, authority):
    """NFR4.8: entering executing and recording the attempt are one compare-and-set."""
    repo, now = flows.repository(transactions), flows.at()
    connection = flows.connected(repo, connect, authority, now)
    effect = flows.bound(repo, authority, connection, now)["effect"]
    claimed = repo.claim(effect["id"], effect["revision"], now=now)
    assert isinstance(claimed, Claimed)
    assert (claimed.effect["state"], claimed.effect["revision"]) == ("executing", 2)
    attempt = claimed.attempt
    assert (attempt["attempt_number"], attempt["started_at"]) == (1, now)
    assert attempt["deadline_at"] == flows.at(90, base=now)
    assert (attempt["writer_identity"], attempt["connection_revision"]) == ("synthetic-bot", 1)
    assert attempt["ended_at"] is None and attempt["path_kind"] == "synthetic"
    binding = repo.effect_binding(effect["id"])
    assert [a["id"] for a in binding["attempts"]] == [attempt["id"]]
    assert binding["effect"]["state"] == "executing" and binding["firstAttemptAt"] == now
    assert binding["revision"]["rendered_blocks"]["children"][-1]["marker"] == effect["marker"]
    assert binding["writerIdentities"] == ["synthetic-bot"]
    assert repo.claim(effect["id"], effect["revision"], now=now) is None  # moved on
    assert repo.claim(effect["id"], 2, now=now) is None  # executing, not rate-limited
    assert repo.effect_binding(uuid4()) is None


def test_the_claim_is_refused_after_a_definite_change_or_while_unavailable(
    transactions, connect, authority
):
    repo, now = flows.repository(transactions), flows.at()
    connection = flows.connected(repo, connect, authority, now)
    effect = flows.bound(repo, authority, connection, now)["effect"]
    repo.set_availability(authority.account_id, connection["id"], 1, available=False)
    assert repo.claim(effect["id"], 1, now=now) == ClaimRefused("connection-unavailable")
    repo.set_availability(authority.account_id, connection["id"], 1, available=True)
    flows.configure(repo, authority, now, expected=1)  # the replace invalidates `effect`
    assert flows.effect_row(connect, effect["id"])["state"] == "invalidated"

    replaced = repo.read_connection(authority)
    other_session = flows.second_session(connect, authority)
    preview = flows.prepare(repo, authority, replaced, now)
    approval = flows.approve(repo, other_session, preview, now)
    waiting = repo.bind_effect(authority, approval["id"], uuid4(), now=now)["effect"]
    flows.end_session(connect, other_session)
    assert repo.claim(waiting["id"], 1, now=now) == ClaimRefused("authority-revoked")
    assert flows.effect_row(connect, waiting["id"])["state"] == "accepted"

    repo.end_unwritten(waiting["id"], 1, "authority-revoked", now=now)
    current = flows.bound(repo, authority, replaced, now)["effect"]
    with connect("export") as conn:  # the revision moves on between check and claim
        conn.execute(
            "SELECT export.clear_token_envelope(%s,%s,2,'disconnected')",
            (authority.account_id, replaced["id"]),
        )
    assert repo.claim(current["id"], current["revision"], now=now) == ClaimRefused(
        "connection-changed"
    )


def test_an_executing_export_holds_the_owner_until_it_ends(transactions, connect, authority):
    """BR5.1: while one export executes, no other can be bound or claimed for the owner."""
    repo, now = flows.repository(transactions), flows.at()
    connection = flows.connected(repo, connect, authority, now)
    effect = flows.bound(repo, authority, connection, now)["effect"]
    claimed = repo.claim(effect["id"], 1, now=now)
    approval = flows.approve(repo, authority, flows.prepare(repo, authority, connection, now), now)
    with pytest.raises(ExportError) as caught:
        repo.bind_effect(authority, approval["id"], uuid4(), now=now)
    assert caught.value.code == "CAPACITY_EXHAUSTED"
    assert repo.claim(effect["id"], claimed.effect["revision"], now=now) is None
    assert repo.end_unwritten(effect["id"], 2, "dependency-unavailable", now=now) is None


def test_outcomes_move_the_effect_and_terminal_ones_set_ended_at(transactions, connect, authority):
    repo, now = flows.repository(transactions), flows.at()
    connection = flows.connected(repo, connect, authority, now)
    refused = flows.bound(repo, authority, connection, now)["effect"]
    claimed = repo.claim(refused["id"], 1, now=now)
    outcome = WriteOutcome("refused", provider_request_id="req-1", reason="content-rejected")
    assert repo.record_write_outcome(refused["id"], uuid4(), 2, outcome, now=now) is None
    failed = repo.record_write_outcome(refused["id"], claimed.attempt["id"], 2, outcome, now=now)
    assert (failed["state"], failed["outcome_reason"], failed["settled_by"]) == (
        "failed",
        "content-rejected",
        "provider",
    )
    assert failed["ended_at"] == now

    waiting = rate_limited(repo, flows.bound(repo, authority, connection, now)["effect"], now)
    assert waiting["state"] == "executing" and waiting["ended_at"] is None
    assert waiting["next_attempt_at"] == flows.at(50, base=now)
    assert waiting["rate_limit_started_at"] == now
    assert repo.claim(waiting["id"], waiting["revision"], now=flows.at(49, base=now)) is None
    resumed = repo.claim(waiting["id"], waiting["revision"], now=flows.at(51, base=now))
    assert resumed.attempt["attempt_number"] == 2 and resumed.effect["next_attempt_at"] is None
    spent = repo.record_write_outcome(
        waiting["id"],
        resumed.attempt["id"],
        resumed.effect["revision"],
        WriteOutcome("rate-limited", retry_at=flows.at(500, base=now)),
        now=flows.at(52, base=now),
    )
    assert spent["rate_limit_started_at"] == now  # the window starts at the first answer
    ended = repo.end_unwritten(
        waiting["id"], spent["revision"], "rate-limit-budget-spent", now=flows.at(60, base=now)
    )
    assert (ended["state"], ended["outcome_reason"]) == ("failed", "rate-limit-budget-spent")

    accepted = flows.bound(repo, authority, connection, now)["effect"]
    marked = repo.mark_waiting(accepted["id"], 1, now=now)
    assert marked["waiting_since"] == now and marked["revision"] == 2
    assert repo.mark_waiting(accepted["id"], 2, now=flows.at(5, base=now))["waiting_since"] == now
    invalidated = repo.end_unwritten(accepted["id"], 2, "source-changed", now=now)
    assert (invalidated["state"], invalidated["ended_at"]) == ("invalidated", now)


def test_scans_settle_unknown_exports_and_stop_when_the_period_is_spent(
    transactions, connect, authority
):
    """BR4.4: marker found, two clean scans a settling interval apart, schedule and stop."""
    repo, now = flows.repository(transactions), flows.at()
    connection = flows.connected(repo, connect, authority, now)
    unknown = flows.uncertain(repo, flows.bound(repo, authority, connection, now)["effect"], now)
    assert unknown["next_check_at"] == flows.at(90 + 180, base=now)
    pushed = repo.push_next_check(unknown["id"], unknown["revision"], now=flows.at(270, base=now))
    assert pushed == unknown["revision"] + 1
    assert flows.effect_row(connect, unknown["id"])["next_check_at"] == flows.at(
        270 + 360, base=now
    )
    assert repo.push_next_check(unknown["id"], unknown["revision"], now=now) is None
    reference = uuid4().hex
    found = repo.record_check(
        unknown["id"],
        pushed,
        CheckResult(
            "marker-found",
            now,
            EVIDENCE,
            remote_reference=reference,
            other_marked_pages=[{"remoteReference": uuid4().hex}],
        ),
        now=flows.at(300, base=now),
    )
    assert (found["state"], found["settled_by"], found["remote_reference"]) == (
        "succeeded",
        "reconciliation",
        reference,
    )
    facts = repo.read_connection(authority)
    assert facts["last_destination_id"] == unknown["destination_id"]
    assert facts["creation_capability"] == "confirmed"

    stopped = flows.uncertain(repo, flows.bound(repo, authority, connection, now)["effect"], now)
    late = flows.at(90 + 86401, base=now)
    result = repo.record_check(
        stopped["id"],
        stopped["revision"],
        CheckResult("listing-incomplete", now, EVIDENCE),
        now=late,
    )
    assert result["state"] == "unknown" and result["next_check_at"] is None
    assert result["scanning_stopped_at"] == late
    assert result["reconciliation_evidence_hash"] == EVIDENCE
    view = repo.read_effect(authority, stopped["id"], now=late)
    assert view["settlementOffered"] is True and view["possibleDuplicates"] == []


def test_orphaned_attempts_turn_their_effect_unknown(transactions, connect, authority):
    """BR4.6: an attempt outstanding past the threshold has no live holder."""
    repo, now = flows.repository(transactions, housekeeping_batch=1000), flows.at()
    connection = flows.connected(repo, connect, authority, now)
    effect = flows.bound(repo, authority, connection, now)["effect"]
    repo.claim(effect["id"], 1, now=now)
    assert effect["id"] not in repo.sweep_orphans(flows.at(899, base=now))
    assert effect["id"] in repo.sweep_orphans(flows.at(901, base=now))
    binding = repo.effect_binding(effect["id"])
    assert binding["effect"]["state"] == "unknown"
    assert binding["effect"]["limitations"] == ["orphaned-attempt"]
    assert binding["attempts"][0]["response_class"] == "uncertain"
    assert binding["effect"]["next_check_at"] == flows.at(90 + 1800, base=now)


def test_outcomes_set_connection_facts_without_moving_the_revision(
    transactions, connect, authority
):
    """Decision "Connection facts from outcomes": an older token's outcome never marks a
    replaced connection, and neither fact moves the connection revision."""
    repo, now = flows.repository(transactions), flows.at()
    connection = flows.connected(repo, connect, authority, now)
    created = flows.succeed(repo, flows.bound(repo, authority, connection, now)["effect"], now)
    facts = repo.read_connection(authority)
    assert (facts["revision"], facts["creation_capability"]) == (1, "confirmed")
    assert facts["last_destination_id"] == created["destination_id"]

    denied = flows.bound(repo, authority, connection, now)["effect"]
    claimed = repo.claim(denied["id"], 1, now=now)
    repo.record_write_outcome(
        denied["id"], claimed.attempt["id"], 2, WriteOutcome("refused", reason="no-access"), now=now
    )
    facts = repo.read_connection(authority)
    assert (facts["revision"], facts["creation_capability"]) == (1, "refused")
    assert facts["last_destination_id"] == created["destination_id"]  # a refusal names none

    old = flows.bound(repo, authority, connection, now)["effect"]
    old_claim = repo.claim(old["id"], 1, now=now)
    flows.configure(repo, authority, now, expected=1)
    replaced = repo.read_connection(authority)
    assert (replaced["revision"], replaced["creation_capability"]) == (2, "unknown")
    repo.record_write_outcome(
        old["id"],
        old_claim.attempt["id"],
        2,
        WriteOutcome("created", remote_reference=uuid4().hex),
        now=now,
    )
    facts = repo.read_connection(authority)
    assert (facts["revision"], facts["creation_capability"]) == (2, "unknown")
    assert facts["last_destination_id"] == old["destination_id"]
