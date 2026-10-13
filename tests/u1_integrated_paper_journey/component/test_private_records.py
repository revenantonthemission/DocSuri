"""Private runtime records fail closed on file-type and allocation substitution."""

import json
import os
import threading

import pytest

from backend.local_profile import LocalProfile, private_bytes

pytestmark = pytest.mark.u1_component


def test_private_regular_record_and_size_limit(tmp_path):
    path = tmp_path / "record"
    path.write_bytes(b"bounded")
    path.chmod(0o600)
    assert private_bytes(path) == b"bounded"
    with pytest.raises(ValueError, match="bounded"):
        private_bytes(path, maximum=3)


def test_fifo_is_rejected_without_waiting_for_a_writer(tmp_path):
    path = tmp_path / "fifo"
    os.mkfifo(path, 0o600)
    finished = threading.Event()
    errors = []

    def read():
        try:
            private_bytes(path)
        except ValueError as exc:
            errors.append(str(exc))
        finally:
            finished.set()

    thread = threading.Thread(target=read, daemon=True)
    thread.start()
    assert finished.wait(timeout=1), "private record read blocked on FIFO"
    thread.join(timeout=1)
    assert errors and "regular file" in errors[0]


def test_symlink_and_directory_are_not_private_records(tmp_path):
    target = tmp_path / "target"
    target.write_bytes(b"record")
    target.chmod(0o600)
    link = tmp_path / "link"
    link.symlink_to(target)
    with pytest.raises(OSError):
        private_bytes(link)
    with pytest.raises(ValueError):
        private_bytes(tmp_path)


def test_publicly_readable_record_is_rejected(tmp_path):
    path = tmp_path / "record"
    path.write_bytes(b"record")
    path.chmod(0o644)
    with pytest.raises(ValueError):
        private_bytes(path)


def test_journey_profile_requires_exact_ready_marker(tmp_path):
    profile = LocalProfile(tmp_path, "owned-run", "http://127.0.0.1:18039", 15439, 9999999999)
    marker = {
        "runId": "owned-run",
        "database": "docsuri_u1_journey",
        "realm": "journey",
        "state": "ready",
    }
    path = tmp_path / "journey-database.json"
    for changes in ({"state": "prepared"}, {"runId": "foreign"}, {"database": "postgres"}, {}):
        path.write_text(json.dumps({**marker, **changes}))
        path.chmod(0o600)
        if changes:
            with pytest.raises(ValueError, match="established"):
                profile.journey()
        else:
            assert profile.journey().database_name == "docsuri_u1_journey"
