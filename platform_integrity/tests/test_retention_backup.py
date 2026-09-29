"""Retention, relay cursor, correlation and backup evidence rules."""

import pytest

from docsuri_platform_integrity.domain.backup import (
    BackupEvidence,
    cut_is_exact,
    evaluate_backup,
)
from docsuri_platform_integrity.domain.retention import (
    CRITICAL_DAYS,
    DAY_US,
    ORDINARY_DAYS,
    Correlation,
    RetentionPolicy,
    advance_relay_cursor,
    correlation_is_nested,
    gc_decision,
    retention_deadline_us,
)

POLICY = RetentionPolicy()
NOW = 1_000 * DAY_US


def evidence(**overrides):
    values = dict(
        cut_us=str(NOW - DAY_US),
        generation="sha256:" + "a" * 64,
        archive="sha256:" + "b" * 64,
        archive_encrypted=True,
        remote_copy_verified=True,
        restored_incarnation="incarnation-two",
        writer_resolved=True,
        clock_trusted=True,
        key_unlocked=True,
    )
    values.update(overrides)
    return BackupEvidence(**values)


# -- retention ------------------------------------------------------------


def test_default_windows_are_fourteen_and_ninety_days():
    assert POLICY.ordinary_days == ORDINARY_DAYS == 14
    assert POLICY.critical_days == CRITICAL_DAYS == 90
    assert POLICY.window_us("ordinary") == 14 * DAY_US
    assert POLICY.window_us("critical") == 90 * DAY_US
    with pytest.raises(ValueError):
        POLICY.window_us("secret")


def test_retention_policy_rejects_absurd_windows():
    with pytest.raises(ValueError):
        RetentionPolicy(ordinary_days=0)
    with pytest.raises(ValueError):
        RetentionPolicy(critical_days=100_000)


def test_deadline_is_event_plus_window():
    assert retention_deadline_us("ordinary", 1000, POLICY) == 1000 + 14 * DAY_US
    assert retention_deadline_us("critical", 1000, POLICY) == 1000 + 90 * DAY_US


def test_ordinary_record_is_collected_only_after_its_window():
    assert not gc_decision("ordinary", NOW - 13 * DAY_US, NOW, POLICY, managed=True)
    assert gc_decision("ordinary", NOW - 15 * DAY_US, NOW, POLICY, managed=True)


def test_critical_record_is_never_collected_without_approval():
    old = NOW - 365 * DAY_US
    assert not gc_decision("critical", old, NOW, POLICY, managed=True)
    assert not gc_decision("critical", old, NOW, POLICY, managed=True, approved=False)
    assert gc_decision("critical", old, NOW, POLICY, managed=True, approved=True)


def test_gc_never_touches_records_outside_the_managed_set():
    """Pre-existing operator logs and backups are not this system's to delete."""
    old = NOW - 365 * DAY_US
    assert not gc_decision("ordinary", old, NOW, POLICY, managed=False)
    assert not gc_decision("ordinary", old, NOW, POLICY, managed=False, approved=True)
    assert not gc_decision("critical", old, NOW, POLICY, managed=False, approved=True)


def test_gc_refuses_while_a_writer_is_unresolved():
    old = NOW - 365 * DAY_US
    assert not gc_decision(
        "ordinary", old, NOW, POLICY, managed=True, writer_resolved=False
    )
    assert gc_decision("ordinary", old, NOW, POLICY, managed=True, writer_resolved=True)


# -- relay cursor ---------------------------------------------------------


def test_relay_cursor_advances_and_never_rewinds():
    assert advance_relay_cursor(None, 5) == 5
    assert advance_relay_cursor(5, 6) == 6
    with pytest.raises(ValueError):
        advance_relay_cursor(5, 5)
    with pytest.raises(ValueError):
        advance_relay_cursor(5, 4)


def test_relay_cursor_rejects_nonsense():
    with pytest.raises(ValueError):
        advance_relay_cursor(None, -1)
    with pytest.raises(ValueError):
        advance_relay_cursor("5", 6)


# -- correlation ----------------------------------------------------------


def test_an_effect_must_name_its_run():
    assert correlation_is_nested(Correlation(request="req-1"))
    assert correlation_is_nested(Correlation(request="req-1", run="run-1"))
    assert correlation_is_nested(Correlation(request="req-1", run="run-1", effect="eff-1"))
    assert not correlation_is_nested(Correlation(request="req-1", effect="eff-1"))


# -- backup evidence ------------------------------------------------------


def test_a_complete_backup_verifies():
    assert evaluate_backup(evidence(), now_us=NOW) == ("VERIFIED", ())


@pytest.mark.parametrize(
    "overrides,reason",
    [
        ({"archive": None}, "archive_missing"),
        ({"archive_encrypted": False}, "archive_not_encrypted"),
        ({"remote_copy_verified": False}, "no_verified_remote_copy"),
        ({"writer_resolved": False}, "writer_unresolved"),
        ({"clock_trusted": False}, "clock_untrusted"),
        ({"key_unlocked": False}, "key_locked"),
        ({"restored_incarnation": None}, "restore_not_performed"),
    ],
)
def test_each_missing_condition_is_reported_not_absorbed(overrides, reason):
    verdict, reasons = evaluate_backup(evidence(**overrides), now_us=NOW)
    assert verdict == "INCOMPLETE"
    assert reason in reasons


def test_absent_evidence_fields_cannot_be_omitted_to_reach_success():
    """Every signal defaults to the unproven value, not the proven one."""
    minimal = BackupEvidence(
        cut_us=str(NOW - DAY_US), generation="sha256:" + "a" * 64
    )
    verdict, reasons = evaluate_backup(minimal, now_us=NOW)
    assert verdict == "INCOMPLETE"
    assert reasons == (
        "archive_missing",
        "clock_untrusted",
        "key_locked",
        "no_verified_remote_copy",
        "restore_not_performed",
        "writer_unresolved",
    )


def test_a_backup_on_only_the_failing_disk_is_never_a_backup():
    verdict, reasons = evaluate_backup(
        evidence(remote_copy_verified=False), now_us=NOW
    )
    assert verdict == "INCOMPLETE"
    assert "no_verified_remote_copy" in reasons


def test_a_cut_in_the_future_is_refused():
    verdict, reasons = evaluate_backup(evidence(cut_us=str(NOW + DAY_US)), now_us=NOW)
    assert verdict == "INCOMPLETE"
    assert "cut_in_future" in reasons


def test_rpo_and_rto_outside_their_windows_are_incomplete():
    verdict, reasons = evaluate_backup(
        evidence(rpo_us=str(365 * DAY_US)), now_us=NOW
    )
    assert "rpo_outside_window" in reasons
    verdict, reasons = evaluate_backup(
        evidence(rto_us=str(30 * DAY_US)), now_us=NOW
    )
    assert "rto_outside_window" in reasons


def test_cut_must_belong_to_one_writer_epoch():
    assert cut_is_exact(1000, writer_epoch="e1", observed_epoch="e1")
    assert not cut_is_exact(1000, writer_epoch="e1", observed_epoch="e2")


def test_a_rotated_writer_across_the_cut_is_not_an_exact_cut():
    """The rotation is detected by the epoch differing, not by any wall-clock reading."""
    value = evaluate_backup(evidence(), now_us=NOW)
    assert value[0] == "VERIFIED"
    assert not cut_is_exact(NOW, writer_epoch="e1", observed_epoch="e2")
