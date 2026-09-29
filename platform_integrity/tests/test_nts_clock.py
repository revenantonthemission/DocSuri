import os
from dataclasses import replace
from pathlib import Path

import pytest

from docsuri_platform_integrity.adapters.clock import ClockUnavailable
from docsuri_platform_integrity.adapters.nts import (
    NativeTime,
    ProtectedClock,
    make_frame,
    publish_frame,
)
from docsuri_platform_integrity.contracts.codec import digest

D = digest(b"protected chrony config")
BEFORE = NativeTime(1_000_000_000, 1_000_000_000, "boot-1", "wake-1")
AFTER = replace(BEFORE, continuous_ns=1_010_000_000, wall_us=1_000_010_000)
TRACKING = """Reference ID : C0000201 (192.0.2.1)
Stratum : 2
Ref time (UTC) : Sat Sep 26 00:00:00 2026
System time : 0.250000 seconds slow of NTP time
Frequency : 1.0 ppm slow
Residual freq : 0.1 ppm
Skew : 0.2 ppm
Root delay : 0.010000 seconds
Root dispersion : 0.001000 seconds
Leap status : Normal
"""
REPORTS = {
    "tracking_before": TRACKING, "tracking": TRACKING,
    "sources": "^* 192.0.2.1 1 4 377 2 +0ns[+0ns] +/- 1ms\n",
    "authdata": "192.0.2.1 NTS 1 15 256 10 0 0 8 100\n",
    "ntpdata": "Remote address : 192.0.2.1 (C0000201)\nAuthenticated : Yes\n"
               "Leap status : Normal\nNTP tests : 111 111 1111\nTotal good RX : 10\n",
    "sourcename": "time.cloudflare.com\n",
}


def test_authenticated_observer_corrects_offset_with_conservative_bounds():
    frame = make_frame(REPORTS, BEFORE, AFTER, config_digest=D)
    assert frame.utc_us == "1000260000"
    assert frame.uncertainty_us >= 16_000
    assert frame.authenticated is True


@pytest.mark.parametrize("report,replacement", [
    ("authdata", REPORTS["authdata"].replace("NTS", "SK")),
    ("ntpdata", REPORTS["ntpdata"].replace("Authenticated : Yes", "Authenticated : No")),
    ("sources", REPORTS["sources"].replace("377 2", "377 30")),
    ("sourcename", "unapproved.example"),
    ("tracking", TRACKING.replace("Normal", "Not synchronised")),
    ("tracking", TRACKING.replace("0.001000", "NaN")),
    ("tracking", TRACKING.replace("C0000201", "C0000202")),
])
def test_unverified_or_stale_observations_never_create_trusted_frame(report, replacement):
    with pytest.raises(ClockUnavailable):
        make_frame(REPORTS | {report: replacement}, BEFORE, AFTER, config_digest=D)


def test_clock_jump_or_wake_during_observation_is_rejected():
    for end in (replace(AFTER, wall_us=AFTER.wall_us + 10_000_000),
                replace(AFTER, resume_id="wake-2")):
        with pytest.raises(ClockUnavailable):
            make_frame(REPORTS, BEFORE, end, config_digest=D)


def test_protected_snapshot_expires_and_invalidates_on_wake(tmp_path):
    frame = make_frame(REPORTS, BEFORE, AFTER, config_digest=D)
    path = tmp_path / "clock.json"
    publish_frame(path, frame)
    current = AFTER
    reader = ProtectedClock(path, writer_uid=os.getuid(), config_digest=D,
                            context=lambda: current, trusted_root=tmp_path)
    lower, upper = reader()
    assert lower < int(frame.utc_us) < upper
    current = replace(AFTER, continuous_ns=AFTER.continuous_ns + 30_000_000_000)
    with pytest.raises(ClockUnavailable):
        reader()
    current = replace(AFTER, resume_id="wake-2")
    with pytest.raises(ClockUnavailable):
        reader()


def test_failed_new_observation_replaces_old_eligibility(tmp_path):
    path = tmp_path / "clock.json"
    publish_frame(path, make_frame(REPORTS, BEFORE, AFTER, config_digest=D))
    publish_frame(path, None)
    reader = ProtectedClock(path, writer_uid=os.getuid(), config_digest=D,
                            context=lambda: AFTER, trusted_root=tmp_path)
    with pytest.raises(ClockUnavailable):
        reader()


def fake_chronyc(tmp_path, reports):
    """A protected stand-in for chronyc that replays canned report text per subcommand."""
    script = tmp_path / "chronyc"
    script.write_text(
        "#!/bin/sh\n"
        'case "$*" in\n'
        '  *tracking*) cat <<\'TRACK\'\n' + REPORTS["tracking"] + 'TRACK\n;;\n'
        '  *sources*) printf \'%s\' "' + REPORTS["sources"].strip() + '"\n;;\n'
        '  *authdata*) printf \'%s\' "' + REPORTS["authdata"].strip() + '"\n;;\n'
        '  *ntpdata*) cat <<\'NTPD\'\n' + REPORTS["ntpdata"] + 'NTPD\n;;\n'
        '  *sourcename*) printf \'%s\' "' + REPORTS["sourcename"].strip() + '"\n;;\n'
        "  *) exit 64;;\n"
        "esac\n")
    script.chmod(0o555)
    return script


@pytest.fixture
def chrony_socket():
    """A real AF_UNIX endpoint; macOS caps sun_path far below pytest's tmp_path length."""
    import shutil
    import socket as unix
    import tempfile

    directory = tempfile.mkdtemp(prefix="r1nts")
    path = Path(directory) / "c.sock"
    server = unix.socket(unix.AF_UNIX)
    server.bind(str(path))
    server.listen(1)
    yield path
    server.close()
    shutil.rmtree(directory, ignore_errors=True)


@pytest.fixture
def collector(tmp_path, chrony_socket, monkeypatch):
    from docsuri_platform_integrity.adapters import nts

    script = fake_chronyc(tmp_path, REPORTS)
    monkeypatch.setattr(nts, "protected_chain", lambda path: None)
    monkeypatch.setattr(nts.protected_bytes, "__kwdefaults__", {"owner": os.getuid(),
                                                                "limit": 262_144})
    return nts.ChronyCollector(script, digest(script.read_bytes()), chrony_socket, D)


def test_native_clock_context_is_observable_and_epoch_stable():
    from docsuri_platform_integrity.adapters.nts import native_time

    first, second = native_time(), native_time()
    assert first.boot_id and first.resume_id
    assert first.boot_id == second.boot_id and first.resume_id == second.resume_id
    assert second.continuous_ns >= first.continuous_ns
    assert second.wall_us >= first.wall_us


def test_protected_observer_produces_a_frame_from_the_live_socket(collector):
    frame = collector.collect()
    assert frame.authenticated is True
    assert frame.uncertainty_us >= 16_000
    assert frame.config_digest == D


def test_observer_refuses_tampered_binary_foreign_socket_and_budget_exhaustion(
        collector, tmp_path, monkeypatch):
    from docsuri_platform_integrity.adapters import nts

    with pytest.raises(ClockUnavailable):
        nts.ChronyCollector(collector.executable, digest(b"other"), collector.socket, D).collect()

    foreign = tmp_path / "foreign.sock"
    foreign.write_bytes(b"")
    with pytest.raises(ClockUnavailable):
        nts.ChronyCollector(collector.executable, collector.executable_digest, foreign, D).collect()

    ticks = iter((0.0, 5.0, 5.0))
    monkeypatch.setattr(nts.time, "monotonic", lambda: next(ticks))
    with pytest.raises(ClockUnavailable):
        collector.collect()


def test_observer_fails_closed_when_chronyc_reports_nothing_usable(collector, monkeypatch,
                                                                  tmp_path):
    from docsuri_platform_integrity.adapters import nts

    silent = tmp_path / "silent-chronyc"
    silent.write_text("#!/bin/sh\nexit 1\n")
    silent.chmod(0o555)
    collector.executable = silent
    collector.executable_digest = digest(silent.read_bytes())
    with pytest.raises(ClockUnavailable):
        collector.collect()
    assert nts.ChronyCollector is not None
