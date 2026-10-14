"""Real private-file rotation and authenticated encryption without a live realm."""

import os

import pytest
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from backend.modules.accounts.control_keys import ControlKeyring
from backend.modules.accounts.control_policy import PolicyUnavailable
from backend.modules.accounts.services.control_entry import ControlEntryService

pytestmark = pytest.mark.u2_operations


@pytest.fixture(scope="session", autouse=True)
def exclusive_environment():
    """These isolated private-file tests never connect to the shared realm."""
    yield


@pytest.fixture
def custody(tmp_path):
    # Isolate filesystem mechanics; the production constructor separately rejects
    # arbitrary roots. No live keys or fixture accounts are touched by these tests.
    ring = ControlKeyring.__new__(ControlKeyring)
    ring.root, ring.run_id, ring.legacy_key = tmp_path, "docsuri-u2-test", b"k" * 32
    entry = ControlEntryService.__new__(ControlEntryService)
    entry.keyring = ring
    return ring, entry


def test_rotation_retains_old_proofs_and_legacy_ciphertext(custody):
    ring, entry = custody
    original = entry.protect("mfa:one", {"seed": "private"})
    nonce = b"n" * 12
    legacy = nonce + AESGCM(ring.legacy_key).encrypt(nonce, b'{"seed":"old"}', b"mfa:old")
    changed = ring.rotate()
    current = entry.protect("mfa:two", {"seed": "new"})
    assert entry.protection_version(current) == changed["activeVersion"]
    assert entry.reveal("mfa:one", original) == {"seed": "private"}
    assert entry.reveal("mfa:old", legacy) == {"seed": "old"}
    assert entry.reveal("mfa:two", current) == {"seed": "new"}
    with pytest.raises(InvalidTag):
        entry.reveal("mfa:one", current)


def test_restart_reads_retained_key_custody(custody):
    ring, entry = custody
    ring.rotate()
    sealed = entry.protect("proof:one", {"delivery": "private-reference"})
    restarted = ControlKeyring.__new__(ControlKeyring)
    restarted.root, restarted.run_id, restarted.legacy_key = ring.root, ring.run_id, ring.legacy_key
    entry.keyring = restarted
    assert entry.reveal("proof:one", sealed)["delivery"] == "private-reference"


def test_missing_keyring_after_rotation_fails_closed(custody):
    ring, _ = custody
    ring.rotate()
    (ring.root / ring.filename).unlink()
    with pytest.raises(PolicyUnavailable):
        ring.read()


def test_missing_retained_key_never_falls_back(custody):
    ring, entry = custody
    old = entry.protect("proof:old", {"value": 1})
    ring.rotate()
    value = ring.read()
    del value["keys"]["u2-v1"]
    ring._write(value)
    with pytest.raises(PolicyUnavailable):
        entry.reveal("proof:old", old)


def test_crash_before_ring_write_preserves_fail_closed_marker(custody, monkeypatch):
    ring, _ = custody

    def fail(_):
        raise OSError("simulated durable-write failure")

    monkeypatch.setattr(ring, "_write", fail)
    with pytest.raises(OSError):
        ring.rotate()
    with pytest.raises(PolicyUnavailable):
        ring.read()


def test_rotation_bound_retains_all_existing_keys(custody):
    ring, _ = custody
    ring.rotate()
    ring.rotate()
    before = ring.read()
    with pytest.raises(PolicyUnavailable):
        ring.rotate()
    assert ring.read() == before


@pytest.mark.parametrize("fault", ["permissions", "other-run", "duplicate", "symlink"])
def test_invalid_custody_denied(custody, fault):
    ring, _ = custody
    ring.rotate()
    path = ring.root / ring.filename
    if fault == "permissions":
        path.chmod(0o644)
    elif fault == "other-run":
        value = ring.read()
        value["runId"] = "other-run"
        ring._write(value)
    elif fault == "duplicate":
        value = path.read_text()
        path.write_text(value[:-1] + ',"active":"u2-v1"}')
    else:
        path.unlink()
        path.symlink_to(ring.root / "absent")
    with pytest.raises(PolicyUnavailable):
        ring.read()


def test_constructor_denies_arbitrary_root(tmp_path):
    with pytest.raises(ValueError):
        ControlKeyring(tmp_path, "run", os.urandom(32))


def test_readonly_compatibility_does_not_initialize_files(custody):
    ring, entry = custody
    assert ring.active_version == "u2-v1"
    assert entry.reveal("proof:test", entry.protect("proof:test", {"ok": True})) == {"ok": True}
    assert list(ring.root.iterdir()) == []
