"""The CutoverRecord machine, row by row (U8 plan Step 34; functional-spec.md § State
machine — CutoverRecord; BR9.1–BR9.17).

Every row of the table is driven through `Cutover` on a private ledger, and each guard is
shown refusing when it does not hold, with the record unchanged. Your decisions are
MaintainerApprovals with their binding facts, as the operator tool appends them.
"""

from __future__ import annotations

import datetime as dt
from uuid import uuid4

import pytest

from backend.modules.operations.errors import OperationsError
from backend.modules.operations.incidents import Incidents
from tests.u8_service_operations_integration import cutover_flows as cf
from tests.u8_service_operations_integration import recovery_flows as rf

DAY = 86400


@pytest.fixture
def ledger(tmp_path, clock):
    value = rf.open_ledger(tmp_path, clock)
    yield value
    value.close()


def refused(action, reason: str | None = None, code: str = "CONFLICT"):
    with pytest.raises(OperationsError) as caught:
        action()
    assert caught.value.code == code
    if reason is not None:
        assert caught.value.current["reasonKey"] == reason
    return caught.value


def clean_soak(ledger, cutover, clock) -> dict:
    """A soak whose full period ran clean on ledger evidence, evaluated."""
    record = cutover.current()
    start = dt.datetime.fromisoformat(record["soakStartedAt"].replace("Z", "+00:00"))
    sets = cf.scheduled_sets(ledger, start, 7)
    cf.verified_restore(ledger, sets[0], now=start + dt.timedelta(days=1))
    clock.advance(7 * DAY + 60)
    evaluated, reasons = cutover.evaluate_soak()
    assert evaluated["soakClean"] and not reasons, reasons
    return evaluated


def ready(ledger, clock):
    cutover, _ = cf.rehearsing(ledger, clock)
    clean_soak(ledger, cutover, clock)
    return cutover, cutover.check_ready([])


def switching(ledger, clock):
    cutover, record = ready(ledger, clock)
    approval = cf.decision(ledger, "switch-start", record["cutoverId"], now=clock())
    return cutover, cutover.approve_start(approval, [])


def test_none_to_preparing_once_and_only_once(ledger, clock):
    cutover = cf.machine(ledger, clock)
    record = cutover.begin(cf.TAG)
    assert record["state"] == "preparing" and record["releaseTag"] == cf.TAG
    assert record["switchTimeBoundSeconds"] == 4 * 3600
    assert record["rollbackWindowSeconds"] == 14 * DAY and record["soakPeriodSeconds"] == 7 * DAY
    refused(lambda: cutover.begin("v2.0.1"), "cutover-record-exists")
    assert len(ledger.records("cutover-record")) == 1


def test_preparing_records_an_accepted_dry_run_and_needs_both_to_rehearse(ledger, clock):
    cutover = cf.machine(ledger, clock)
    cutover.begin(cf.TAG)
    refused(cutover.start_soak, "dry-run-not-accepted")
    pending = cf._run(ledger, "dry", ("copying",), now=clock())
    refused(lambda: cutover.dry_run_accepted(pending["runId"]), "dry-run-not-accepted")
    run = cf.accepted_dry_run(ledger, now=clock())
    assert cutover.dry_run_accepted(run["runId"])["state"] == "preparing"
    refused(cutover.start_soak, "verification-not-passed")
    refused(lambda: cutover.verification_passed(uuid4(), "v2.0.9"),
            "verification-not-for-this-release")
    cutover.verification_passed(uuid4(), cf.TAG)
    rehearsing = cutover.start_soak()
    assert rehearsing["state"] == "rehearsing" and "soakStartedAt" in rehearsing


def test_rehearsing_moves_to_a_newer_dry_run_and_resets_on_a_new_tag(ledger, clock):
    cutover, record = cf.rehearsing(ledger, clock)
    newer = cf.accepted_dry_run(ledger, now=clock())
    moved = cutover.dry_run_accepted(newer["runId"])
    assert moved["state"] == "rehearsing" and moved["acceptedDryRunId"] == newer["runId"]
    assert moved["soakStartedAt"] == record["soakStartedAt"]  # the soak continues
    reset = cutover.new_release("v2.0.1")
    assert reset["releaseTag"] == "v2.0.1" and "soakStartedAt" not in reset
    assert not reset["soakClean"] and "verificationRunId" not in reset
    refused(cutover.restart_soak, "verification-not-passed")
    cutover.verification_passed(uuid4(), "v2.0.1")
    assert "soakStartedAt" in cutover.restart_soak()


def test_ready_to_switch_needs_every_precondition_and_lapses_back(ledger, clock):
    cutover, record = cf.rehearsing(ledger, clock)
    refused(lambda: cutover.check_ready([]), "soak-not-clean")
    clean_soak(ledger, cutover, clock)
    assert cutover.check_ready(["incident-unresolved"])["state"] == "rehearsing"
    assert cutover.check_ready([])["state"] == "ready-to-switch"
    # A precondition lapses: back to rehearsing; a newer dry run lapses it too.
    assert cutover.check_ready(["restart-rehearsal-void"])["state"] == "rehearsing"
    cutover.check_ready([])
    newer = cf.accepted_dry_run(ledger, now=clock())
    assert cutover.dry_run_accepted(newer["runId"])["state"] == "rehearsing"


def test_a_rehearsal_backstop_returns_to_preparing_with_an_incident(ledger, clock):
    cutover, _ = ready(ledger, clock)
    back = cutover.rehearsal_backstop()
    assert back["state"] == "preparing" and "acceptedDryRunId" not in back
    incident = Incidents(ledger, environment="rehearsal").open_for("storage.capacity")
    assert incident is not None and incident["openedBy"] == "tolerance-exceeded"
    refused(cutover.rehearsal_backstop, "cutover-not-at-this-step")


def test_the_switch_starts_only_on_your_decision_with_every_precondition(ledger, clock):
    cutover, record = ready(ledger, clock)
    refused(lambda: cutover.approve_start(None, []), "decision-required", "FORBIDDEN")
    declined = cf.decision(ledger, "switch-start", record["cutoverId"], now=clock(),
                           decision="declined")
    refused(lambda: cutover.approve_start(declined, []), "decision-declined")
    other = cf.decision(ledger, "switch-start", str(uuid4()), now=clock())
    refused(lambda: cutover.approve_start(other, []), "decision-required", "FORBIDDEN")
    approval = cf.decision(ledger, "switch-start", record["cutoverId"], now=clock())
    error = refused(lambda: cutover.approve_start(approval, ["soak-not-clean"]),
                    "precondition-missing")
    assert error.current["missing"] == ["soak-not-clean"]
    assert cutover.current()["state"] == "ready-to-switch"
    started = cutover.approve_start(approval, [])
    assert started["state"] == "switching" and approval in started["approvals"]
    assert cutover.holds_live_exclusion()


def test_the_bound_runs_from_v1s_stop_and_passes_after_four_hours(ledger, clock):
    cutover, record = switching(ledger, clock)
    assert not cutover.bound_passed()  # not started until v1 stops
    facts = rf.receipt("platform.service.control", "dev.docsuri.u8.run.v1-api", now=clock())
    stopped = cutover.v1_stopped([facts])
    assert facts["receiptId"] in stopped["effectReceipts"]
    clock.advance(4 * 3600 - 1)
    assert not cutover.bound_passed()
    clock.advance(2)
    assert cutover.bound_passed()
    assert cutover.v1_stopped([])["switchStartedAt"] == stopped["switchStartedAt"]


def first_live(ledger, clock) -> dict:
    facts = rf.receipt(now=clock())
    backup = str(uuid4())
    record = {
        "backupId": backup, "environment": "live", "revision": 99, "trigger": "first-live",
        "takenAt": rf.utc_text(clock()), "checksum": "c" * 64, "sizeBytes": 1,
        "sourceDatabaseBytes": 1, "location": f"archives/live-set-x-{backup}.archive",
        "databaseIncarnation": "docsuri_u8:1", "stagingLocation": "staging/x",
        "retainUntil": rf.utc_text(clock() + dt.timedelta(days=14)), "integrity": "passed",
        "operatorReceiptRef": facts["receiptId"]}
    ledger.append("backup-set", record, expect_revision=0, receipts=(facts,))
    return record


def at_opening(ledger, clock):
    cutover, record = switching(ledger, clock)
    cutover.v1_stopped([])
    run = cf.final_run(ledger, now=clock())
    cutover.final_run(run["runId"])
    clock.advance(60)
    first_live(ledger, clock)
    return cutover, record


def test_opening_needs_each_gate_and_your_decision_on_the_shown_subject(ledger, clock):
    cutover, record = switching(ledger, clock)
    cutover.v1_stopped([])
    subject = {"cutoverId": record["cutoverId"], "providersAcceptedUnavailable": ["orcid"],
               "v1StoresDisposeAfter": "2027-01-30T00:00:00Z"}
    approval = cf.decision(ledger, "admission-opening", record["cutoverId"], now=clock(),
                           subject=subject)
    error = refused(lambda: cutover.open(approval, subject, capabilities_missing=["research"]),
                    "opening-gate-missing")
    assert set(error.current["missing"]) >= {"final-report-not-approved",
                                             "first-live-backup-not-passed",
                                             "capability-research-not-available"}
    reported = cf.final_run(ledger, now=clock(), state="reported")
    cutover.final_run(reported["runId"])
    clock.advance(60)
    first_live(ledger, clock)
    ledger.append("provider-activation", {"provider": "orcid", "outward": False,
                                          "state": "held", "limitations": []},
                  expect_revision=0)
    ledger.append("provider-activation", {"provider": "google", "outward": False,
                                          "state": "held", "limitations": []},
                  expect_revision=0)
    error = refused(lambda: cutover.open(approval, subject, capabilities_missing=[]),
                    "opening-gate-missing")
    assert error.current["missing"] == ["final-report-not-approved",
                                        "provider-google-not-verified"]
    accepted = cf.final_run(ledger, now=clock())
    cutover.final_run(accepted["runId"])
    refused(lambda: cutover.open(approval, {**subject, "providersAcceptedUnavailable": [
        "orcid", "google"]}, capabilities_missing=[]), "decision-subject-differs")
    google = ledger.get("provider-activation", "google")
    ledger.append("provider-activation", {**google, "state": "active"}, expect_revision=1)
    Incidents(ledger, environment="live").signal("research", "operator")
    refused(lambda: cutover.open(approval, subject, capabilities_missing=[]),
            "opening-gate-missing")
    incident = Incidents(ledger, environment="live").open_for("research")
    ledger.append("service-incident", {**incident, "revision": 2, "state": "resolved",
                                       "resolutionKind": "capability-available",
                                       "resolvedAt": rf.utc_text(clock())}, expect_revision=1)
    opened = cutover.open(approval, subject, capabilities_missing=[])
    assert opened["state"] == "switched" and "admissionOpenedAt" in opened
    assert not cutover.holds_live_exclusion()


def test_the_abort_takes_over_the_live_cutover_incident_and_returns_on_v1(ledger, clock):
    cutover, record = switching(ledger, clock)
    incidents = Incidents(ledger, environment="live")
    earlier = incidents.signal("operations.cutover", "tolerance-exceeded")
    clock.now = clock.now.replace(microsecond=clock.now.microsecond // 1000 * 1000)
    from backend.modules.operations.ledger import utc_text

    abort_at = utc_text(clock())
    aborting = cutover.abort(reason="switch-bound-passed")
    assert aborting["state"] == "aborting"
    assert aborting["abortIncidentId"] == earlier["incidentId"]  # taken over, not a second
    assert aborting["abortStartedAt"] == abort_at  # the abort's clock (L1-3)
    assert incidents.role(earlier["incidentId"]) == "abort"
    cutover.v1_restart_failed()
    assert cutover.current()["state"] == "aborting"
    assert any("v1-restart-failed" in ref for ref in incidents.get(
        earlier["incidentId"])["correlationIds"])
    back = cutover.aborted()
    assert back["state"] == "rehearsing" and "switchStartedAt" not in back
    assert back["abortStartedAt"] == abort_at
    refused(cutover.aborted, "cutover-not-at-this-step")
    # A later check keeps it; the start drops it and records its check instant.
    assert cutover.check_ready([])["abortStartedAt"] == abort_at
    clock.advance(60)
    restart = cf.decision(ledger, "switch-start", record["cutoverId"], now=clock())
    again = cutover.approve_start(restart, [])
    assert "abortStartedAt" not in again and again["switchCheckedAt"] == utc_text(clock())
    cutover.abort(reason="operator-abort")
    cutover.aborted()
    # Another switch needs the abort's incident resolved with your review.
    review = cf.decision(ledger, "abort-review", record["cutoverId"], now=clock())
    resolved = incidents.resolve(earlier["incidentId"], "abort-reviewed", [f"approval:{review}"])
    assert resolved["resolutionKind"] == "abort-reviewed"


def test_an_abort_opens_its_own_incident_when_none_is_open(ledger, clock):
    cutover, _ = switching(ledger, clock)
    aborting = cutover.abort(reason="final-run-rejected")
    incident = Incidents(ledger, environment="live").get(aborting["abortIncidentId"])
    assert incident["openedBy"] == "switch-aborted"
    assert incident["capabilities"] == ["operations.cutover"]


def rolled_out(ledger, clock):
    cutover, record = at_opening(ledger, clock)
    subject = {"cutoverId": record["cutoverId"], "providersAcceptedUnavailable": []}
    approval = cf.decision(ledger, "admission-opening", record["cutoverId"], now=clock(),
                           subject=subject)
    cutover.open(approval, subject, capabilities_missing=[])
    return cutover, cutover.current()


def test_a_rollback_within_the_window_waits_for_v1_and_its_copy(ledger, clock):
    cutover, record = rolled_out(ledger, clock)
    approval = cf.decision(ledger, "rollback", record["cutoverId"], now=clock())
    rolling = cutover.rollback(approval)
    assert rolling["state"] == "rolling-back" and cutover.holds_live_exclusion()
    refused(lambda: cutover.rolled_back(), "v1-not-serving")
    refused(lambda: cutover.rollback_v1_serving(applied={"outcomesApplied": True}),
            "v1-lifecycle-not-applied")
    serving = cutover.rollback_v1_serving(applied={"outcomesApplied": True,
                                                   "sessionsEnded": True})
    assert "rollbackV1ServingAt" in serving
    cancel = cf.decision(ledger, "rollback-cancel", record["cutoverId"], now=clock())
    refused(lambda: cutover.cancel_rollback(cancel), "v1-already-serving")
    done = cutover.rolled_back()
    assert done["state"] == "rolled-back"


def test_a_rollback_after_the_window_is_refused(ledger, clock):
    cutover, record = rolled_out(ledger, clock)
    clock.advance(14 * DAY + 1)
    approval = cf.decision(ledger, "rollback", record["cutoverId"], now=clock())
    refused(lambda: cutover.rollback(approval), "rollback-window-closed")
    assert cutover.current()["state"] == "switched"


def test_a_rollback_is_allowed_at_the_windows_last_instant_after_the_opening(ledger, clock):
    """NFR7.16, BR9.7 (L3-8): the 14-day window counts from the record's own opening,
    inclusive of its last instant; neither v1's stop nor the 7-day soak bounds it. The
    instant is read from the record, because the ledger keeps milliseconds."""
    cutover, record = rolled_out(ledger, clock)
    opened = record["admissionOpenedAt"]
    assert dt.datetime.fromisoformat(record["switchStartedAt"].replace("Z", "+00:00")) < (
        dt.datetime.fromisoformat(opened.replace("Z", "+00:00")))
    clock.now = dt.datetime.fromisoformat(opened.replace("Z", "+00:00")) + dt.timedelta(
        seconds=14 * DAY)
    approval = cf.decision(ledger, "rollback", record["cutoverId"], now=clock())
    rolling = cutover.rollback(approval)
    assert rolling["state"] == "rolling-back"
    assert rolling["admissionOpenedAt"] == opened


def test_a_pending_copy_waits_on_its_incident_and_each_exit(ledger, clock):
    cutover, record = rolled_out(ledger, clock)
    cutover.rollback(cf.decision(ledger, "rollback", record["cutoverId"], now=clock()))
    refused(cutover.rollback_copy_pending, "v1-not-serving")
    cutover.rollback_v1_serving(applied={"outcomesApplied": True, "sessionsEnded": True})
    waiver = cf.decision(ledger, "rollback-copy-waiver", record["cutoverId"], now=clock())
    refused(lambda: cutover.rolled_back(waiver=waiver), "rollback-copy-not-pending")
    refused(lambda: cutover.replacement_volume(uuid4()), "rollback-copy-not-pending")
    pending = cutover.rollback_copy_pending()
    assert "rollbackCopyPendingSince" in pending
    incidents = Incidents(ledger, environment="live")
    assert incidents.role(pending["rollbackCopyIncidentId"]) == "rollback-copy"
    # A retirement decision lets the copy go to a replacement volume; the wait goes on.
    refused(lambda: cutover.replacement_volume(uuid4()), "decision-required", "FORBIDDEN")
    retire = cf.decision(ledger, "backup-volume-retirement", "standin-volume", now=clock())
    assert cutover.replacement_volume(retire)["state"] == "rolling-back"
    # A dry run cannot be accepted onto the cutover while the copy is pending.
    run = cf.accepted_dry_run(ledger, now=clock())
    refused(lambda: cutover.dry_run_accepted(run["runId"]), "cutover-not-at-this-step")
    done = cutover.rolled_back(waiver=waiver)
    assert done["state"] == "rolled-back" and "rollbackCopyPendingSince" not in done
    assert waiver in done["approvals"]


def test_a_rollback_is_cancelled_only_before_v1_serves(ledger, clock):
    cutover, record = rolled_out(ledger, clock)
    cutover.rollback(cf.decision(ledger, "rollback", record["cutoverId"], now=clock()))
    declined = cf.decision(ledger, "rollback-cancel", record["cutoverId"], now=clock(),
                           decision="declined")
    refused(lambda: cutover.cancel_rollback(declined), "decision-declined")
    cancel = cf.decision(ledger, "rollback-cancel", record["cutoverId"], now=clock())
    back = cutover.cancel_rollback(cancel)
    assert back["state"] == "switched"
    assert back["admissionOpenedAt"] == record["admissionOpenedAt"]  # the window counts on


def test_rolled_back_accepts_a_dry_run_and_rehearses_again(ledger, clock):
    cutover, record = rolled_out(ledger, clock)
    cutover.rollback(cf.decision(ledger, "rollback", record["cutoverId"], now=clock()))
    cutover.rollback_v1_serving(applied={"outcomesApplied": True, "sessionsEnded": True})
    cutover.rolled_back()
    run = cf.accepted_dry_run(ledger, now=clock())
    assert cutover.dry_run_accepted(run["runId"])["state"] == "rolled-back"
    again = cutover.start_soak()
    assert again["state"] == "rehearsing" and again["acceptedDryRunId"] == run["runId"]


def test_settlement_after_the_window_under_the_inventorys_dispositions(ledger, clock):
    cutover, record = rolled_out(ledger, clock)
    approval = cf.decision(ledger, "settlement", record["cutoverId"], now=clock())
    refused(lambda: cutover.settle(approval), "rollback-window-open")
    clock.advance(14 * DAY + 1)
    refused(lambda: cutover.settle(approval), "inventory-not-ready")
    # Both inventories are taken at the switch's check (L1-21): taken at the
    # settlement's clock, 14 days after it, they would read `inventory-not-recent`.
    checked = dt.datetime.fromisoformat(record["switchCheckedAt"].replace("Z", "+00:00"))
    incomplete = cf.complete_inventory(ledger, now=checked, approved=False)
    cutover.inventory_taken(incomplete["inventoryId"])
    refused(lambda: cutover.settle(approval), "inventory-not-ready")
    inventory = cf.complete_inventory(ledger, now=checked)
    cutover.inventory_taken(inventory["inventoryId"])
    settled = cutover.settle(approval)
    assert settled["state"] == "settled" and "settledAt" in settled
    refused(lambda: cutover.rollback(approval), "cutover-not-at-this-step")


def test_the_routing_reader_gives_the_producer_the_route_and_unknown_effects(tmp_path, clock):
    import json
    from types import SimpleNamespace

    from backend.modules.operations.cutover import EXPECTED_ROUTE, routing_reader
    from backend.modules.operations.producers import CutoverProducer

    profile = SimpleNamespace(is_production=False, root=tmp_path, run_id="docsuri-u8-run1")
    status = {"unresolved": 0}
    read = routing_reader(profile, lambda: status)
    assert read() == {"route": None, "unknownEffects": 0}  # nothing routed yet
    (tmp_path / "tunnel-active.json").write_text(json.dumps(
        {"runId": "docsuri-u8-run1", "origin": "v1-web"}))
    assert read() == {"route": "v1-web", "unknownEffects": 0}
    (tmp_path / "tunnel-active.json").write_text(json.dumps(
        {"runId": "another-run", "origin": "v2-host"}))
    assert read()["route"] is None  # another run's routing is never this realm's
    ledger_ = rf.open_ledger(tmp_path, clock)
    try:
        cf.machine(ledger_, clock).begin(cf.TAG)
        (tmp_path / "tunnel-active.json").write_text(json.dumps(
            {"runId": "docsuri-u8-run1", "origin": EXPECTED_ROUTE["preparing"]}))
        producer = CutoverProducer(ledger_, read)
        assert producer.observe(clock()).outcome == "available"
        status["unresolved"] = 1
        assert producer.observe(clock()).reason == "cutover-effect-unknown"
    finally:
        ledger_.close()


def test_the_first_sign_in_notice_shows_only_once_the_profile_opened_admission():
    from types import SimpleNamespace

    from backend.modules.operations.cutover import moved_notice

    assert not moved_notice(SimpleNamespace(is_production=False, mode="live", admission="open"))
    assert not moved_notice(SimpleNamespace(is_production=True, mode="live",
                                            admission="maintainer-only"))
    assert moved_notice(SimpleNamespace(is_production=True, mode="live", admission="open"))


def test_accountaccess_lists_the_latest_outcome_per_account_since_the_switch(transactions):
    from backend.modules.accounts.services.rollback_outcomes import RollbackOutcomes

    reader = RollbackOutcomes(transactions)
    future = dt.datetime.now(dt.UTC) + dt.timedelta(days=1)
    assert reader.latest_outcomes(future) == []
    assert reader.changes_since(future) == {"accounts-created": 0, "lifecycle-requests": 0}
    since = dt.datetime(2026, 1, 1, tzinfo=dt.UTC)
    outcomes = reader.latest_outcomes(since)
    assert len({item["accountId"] for item in outcomes}) == len(outcomes)  # one per account
    assert {item["outcome"] for item in outcomes} <= {"withdraw", "erase", "reactivate"}
    assert set(reader.changes_since(since)) == {"accounts-created", "lifecycle-requests"}
    with pytest.raises(ValueError):
        reader.latest_outcomes(dt.datetime(2026, 1, 1))


def test_a_restart_rehearsal_is_recorded_on_your_decision(ledger, clock):
    cutover, record = cf.rehearsing(ledger, clock)
    refused(lambda: cutover.record_restart_rehearsal(uuid4(), commit="b" * 40, receipts=()),
            "decision-required", "FORBIDDEN")
    approval = cf.decision(ledger, "v1-restart-rehearsal", record["cutoverId"], now=clock())
    facts = rf.receipt("platform.tunnel.route", "tunnel", now=clock())
    rehearsed = cutover.record_restart_rehearsal(approval, commit="b" * 40, receipts=[facts])
    assert rehearsed["v1CheckoutCommit"] == "b" * 40 and "v1RestartRehearsedAt" in rehearsed
    assert facts["receiptId"] in rehearsed["effectReceipts"]
