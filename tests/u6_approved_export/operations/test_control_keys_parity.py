"""U2's keyring, run through the shared helper, behaves exactly as the built one (D1)."""

import base64
import json
import os
import secrets

import pytest
from backend import key_custody
from backend.modules.accounts.control_keys import ControlKeyring
from backend.modules.accounts.control_policy import PolicyUnavailable

MARKER = "account-control-keyring.initialized"
LOCK = "account-control-keyring.lock"


@pytest.fixture
def ring(tmp_path):
    # The constructor pins the live U2 folder; tests build the ring as the recovery
    # module does, through __new__ and the three instance attributes.
    instance = ControlKeyring.__new__(ControlKeyring)
    instance.root, instance.run_id, instance.legacy_key = tmp_path, "u2-parity", b"k" * 32
    return instance


def test_configuration_is_class_level_and_instances_hold_only_three_attributes(ring):
    settings = ControlKeyring.custody
    assert (ControlKeyring.filename, settings.filename) == ("account-control-keyring.json",) * 2
    assert (settings.lock_name, settings.marker_name) == (LOCK, MARKER)
    assert (settings.generation_min, settings.generation_max, settings.max_versions) == (1, 3, 3)
    assert settings.error is PolicyUnavailable and settings.max_bytes == 4096
    ring.rotate()
    ring.read()
    assert set(vars(ring)) == {"root", "run_id", "legacy_key"}


def test_legacy_record_is_in_memory_and_the_read_path_creates_nothing(ring):
    assert ring.read() == {
        "runId": "u2-parity",
        "active": "u2-v1",
        "generation": 1,
        "keys": {"u2-v1": base64.b64encode(b"k" * 32).decode()},
    }
    assert ring.active_version == "u2-v1" and ring.key("u2-v1") == b"k" * 32
    assert list(ring.root.iterdir()) == []


def test_marker_without_a_key_file_refuses_with_u2s_message(ring):
    (ring.root / MARKER).write_text("u2-parity")
    with pytest.raises(PolicyUnavailable, match="^account-control encryption custody unavailable$"):
        ring.read()


def test_rotation_adds_up_to_three_keys_then_refuses_and_keeps_the_record(ring):
    first = ring.rotate()
    second = ring.rotate()
    assert (first["generation"], second["generation"]) == (2, 3)
    assert second["retainedVersions"] == sorted(["u2-v1", first["activeVersion"], second["activeVersion"]])
    before = ring.read()
    with pytest.raises(
        PolicyUnavailable, match="^keyring retention capacity requires an explicit decision$"
    ):
        ring.rotate()
    assert ring.read() == before and ring.active_version == second["activeVersion"]
    assert all(len(ring.key(version)) == 32 for version in before["keys"])


def test_rotation_writes_the_marker_before_one_call_to_write(ring, monkeypatch):
    seen = []
    real_write = ring._write

    def observe(value):
        seen.append((ring.root / MARKER).exists())
        real_write(value)

    monkeypatch.setattr(ring, "_write", observe)
    ring.rotate()
    assert seen == [True]
    assert (ring.root / MARKER).read_text() == "u2-parity"


def test_staged_write_uses_u2s_staging_name(ring, monkeypatch):
    names = []
    real_replace = os.replace

    def observe(source, target):
        names.append(os.path.basename(source))
        real_replace(source, target)

    monkeypatch.setattr(key_custody.os, "replace", observe)
    ring.rotate()
    assert len(names) == 1 and names[0].startswith(".control-key-") and len(names[0]) == 45
    assert sorted(p.name for p in ring.root.iterdir()) == sorted(
        [ControlKeyring.filename, MARKER, LOCK]
    )


def rewrite(ring, **changes):
    value = ring.read()
    value.update(changes)
    path = ring.root / ring.filename
    path.write_text(json.dumps(value))
    path.chmod(0o600)


@pytest.mark.parametrize("generation", [0, 4, True])
def test_generation_outside_one_to_three_refuses(ring, generation):
    ring.rotate()
    rewrite(ring, generation=generation)
    with pytest.raises(PolicyUnavailable, match="^account-control encryption custody unavailable$"):
        ring.read()


def test_version_pattern_accepts_legacy_and_hex_versions_only(ring):
    ring.rotate()
    value = ring.read()
    assert list(value["keys"])[0] == "u2-v1"
    rewrite(ring, keys={**value["keys"], "u6-" + "a" * 32: base64.b64encode(b"x" * 32).decode()})
    with pytest.raises(PolicyUnavailable):
        ring.read()


def test_u2_exception_types_and_messages_are_unchanged(ring):
    ring.rotate()
    with pytest.raises(PolicyUnavailable, match="^required retained encryption key unavailable$"):
        ring.key("u2-" + secrets.token_hex(16))
    (ring.root / LOCK).chmod(0o644)
    with pytest.raises(PolicyUnavailable, match="^account-control lock custody unavailable$"):
        ring.rotate()
    (ring.root / LOCK).chmod(0o600)
    (ring.root / ring.filename).chmod(0o644)
    with pytest.raises(PolicyUnavailable) as raised:
        ring.read()
    # As before the extraction, a custody fault keeps its cause.
    assert raised.value.__cause__ is not None


def test_a_held_lock_still_raises_the_operating_system_refusal(ring):
    with ring._lock():
        with pytest.raises(BlockingIOError):
            ring.rotate()


def test_constructor_still_pins_the_u2_folder(tmp_path):
    with pytest.raises(ValueError):
        ControlKeyring(tmp_path, "run", os.urandom(32))
    with pytest.raises(ValueError):
        ControlKeyring(tmp_path, "run", b"short")
