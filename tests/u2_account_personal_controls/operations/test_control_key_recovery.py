"""Independent, private recovery snapshots with explicit current-version fencing."""

import hashlib
import hmac
import os

import pytest

from backend.modules.accounts.control_key_recovery import _recover, capture
from backend.modules.accounts.control_keys import ControlKeyring
from backend.modules.accounts.control_policy import PolicyUnavailable

pytestmark = pytest.mark.u2_operations


@pytest.fixture(scope="session", autouse=True)
def exclusive_environment():
    yield  # Isolated temp custody only; no shared realm or PostgreSQL.


@pytest.fixture
def ring(tmp_path):
    verifier = os.urandom(32)
    path = tmp_path / "account-verifier.key"
    path.write_bytes(verifier)
    path.chmod(0o600)
    instance = ControlKeyring.__new__(ControlKeyring)
    instance.root, instance.run_id = tmp_path, "test-run"
    instance.legacy_key = hmac.new(verifier, b"encryption\0u2-controls-v1", hashlib.sha256).digest()
    instance.rotate()
    return instance


def test_snapshot_recovery_restores_missing_members_without_changing_identity(ring):
    bound = capture(ring)
    original = ring.read()
    for name in ("account-verifier.key", ring.filename, "account-control-keyring.initialized"):
        (ring.root / name).unlink()
    result = _recover(ring.root, ring.run_id, bound["digest"], bound["generation"])
    assert result["recovered"] and ring.read() == original
    assert capture(ring) == bound
    assert (ring.root / "account-key-recovery").stat().st_mode & 0o777 == 0o700


def test_old_snapshot_cannot_replace_newer_custody(ring):
    old = capture(ring)
    ring.rotate()
    current = ring.read()
    with pytest.raises(PolicyUnavailable, match="divergent"):
        _recover(ring.root, ring.run_id, old["digest"], old["generation"])
    assert ring.read() == current
    fresh = capture(ring)
    assert fresh["generation"] == 3 and fresh["digest"] != old["digest"]


@pytest.mark.parametrize(
    "fault", ["missing", "digest", "run", "generation", "permissions", "directory", "verifier"]
)
def test_incomplete_wrong_or_unprotected_recovery_refuses(ring, fault):
    bound = capture(ring)
    path = ring.root / "account-key-recovery" / (bound["digest"] + ".json")
    run, generation = ring.run_id, bound["generation"]
    if fault == "missing":
        path.unlink()
    elif fault == "digest":
        path.write_bytes(path.read_bytes() + b" ")
    elif fault == "run":
        run = "other-run"
    elif fault == "generation":
        generation = 1
    elif fault == "permissions":
        path.chmod(0o644)
    elif fault == "directory":
        path.parent.chmod(0o755)
    else:
        (ring.root / "account-verifier.key").write_bytes(b"x" * 32)
    with pytest.raises((PolicyUnavailable, FileNotFoundError)):
        _recover(ring.root, run, bound["digest"], generation)


def test_capture_rejects_verifier_keyring_disagreement(ring):
    (ring.root / "account-verifier.key").write_bytes(b"x" * 32)
    with pytest.raises(PolicyUnavailable, match="disagree"):
        capture(ring)
