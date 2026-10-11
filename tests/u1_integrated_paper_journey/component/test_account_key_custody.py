"""Real key-file custody faults with credential hashing isolated."""

import hashlib
import os
import stat
from types import SimpleNamespace

import pytest

from backend.modules.accounts.services import guarded_entry

pytestmark = pytest.mark.u1_component


def configuration(tmp_path, monkeypatch):
    monkeypatch.setattr(guarded_entry, "PrivateArtifacts", lambda root: None)
    monkeypatch.setattr(
        guarded_entry, "get_password_hasher", lambda: SimpleNamespace(hash=lambda _: "dummy")
    )
    return SimpleNamespace(profile=SimpleNamespace(root=tmp_path))


def test_failed_directory_sync_never_acknowledges_key_and_retry_keeps_bytes(tmp_path, monkeypatch):
    configuration_value = configuration(tmp_path, monkeypatch)
    original = os.fsync

    def fail_directory(descriptor):
        if stat.S_ISDIR(os.fstat(descriptor).st_mode):
            raise OSError("injected key directory sync")
        original(descriptor)

    with monkeypatch.context() as patch:
        patch.setattr(os, "fsync", fail_directory)
        with pytest.raises(OSError, match="directory sync"):
            guarded_entry.GuardedEntryService(configuration_value)
    before = hashlib.sha256((tmp_path / "account-verifier.key").read_bytes()).hexdigest()
    guarded_entry.GuardedEntryService(configuration_value)
    assert hashlib.sha256((tmp_path / "account-verifier.key").read_bytes()).hexdigest() == before


def test_aliased_key_is_rejected_without_rotation(tmp_path, monkeypatch):
    configuration_value = configuration(tmp_path, monkeypatch)
    guarded_entry.GuardedEntryService(configuration_value)
    key = tmp_path / "account-verifier.key"
    os.link(key, tmp_path / "alias")
    with pytest.raises(ValueError, match="custody"):
        guarded_entry.GuardedEntryService(configuration_value)
    assert key.stat().st_nlink == 2
