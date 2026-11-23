"""Real filesystem checks for the synthetic U5 runner's unit and realm bindings.

Grouped by the runner's parts (decision L2-1): the child environment's manifest,
the append-only migration chain, owner and realm bindings, the realm's transport
binding and the local profile's owned manifest.
"""

import sys
from pathlib import Path

import pytest

from backend.local_profile import LocalProfile
from scripts import verify_docsuri_u5 as runner

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "ops/src"))
from docsuri_ops.local_transport import inspect_transport, prepare_transport  # noqa: E402


@pytest.fixture
def owned_root(tmp_path, monkeypatch):
    root = tmp_path / "run"
    root.mkdir(mode=0o700)
    monkeypatch.setattr(runner, "RUN", root)
    return root


def test_child_environment_binds_the_unit_manifest(owned_root):
    environment = runner.child_environment()
    assert environment["DOCSURI_U5_ENVIRONMENT_FILE"] == str(runner.RUN / "environment.json")
    assert environment["CI"] == "true"
    assert environment["COREPACK_ENABLE_NETWORK"] == "0"
    assert "DOCSURI_U5_CLOCK_CAPABILITY" not in environment


def test_migration_chain_is_append_only_and_present():
    schema_index = None
    guard_index = None
    for index, (owner, relative) in enumerate(runner.MIGRATIONS):
        assert (runner.ROOT / relative).is_file(), relative
        assert owner in runner.OWNERS, relative
        if relative.endswith("u5_schema.sql"):
            schema_index = index
        if relative.endswith("u5_run_guard.sql"):
            guard_index = index
    # The chronology-gate correction is an appended migration, never an edit of
    # the applied file: the runner refuses changed applied bytes.
    assert schema_index is not None and guard_index is not None
    assert [path for _, path in runner.MIGRATIONS[guard_index + 1 :]] == [
        "backend/modules/personalization/u5_digest_preferences.sql",
        "backend/modules/topics/u5_preference_snapshot.sql",
        "backend/modules/topics/u5_schedule.sql",
        "backend/modules/topics/u5_unsubscribe_capability.sql",
        "backend/modules/topics/u5_real_send_retention.sql",
        "backend/modules/topics/u5_refusal_detail.sql",
        "backend/modules/topics/u5_scheduled_instant.sql",
    ]
    assert guard_index > schema_index


def test_owner_and_realm_bindings_cover_topics():
    assert "topics" in runner.OWNERS
    assert runner.UNIT == "u5-topics-digests"
    assert runner.REALM == "topics-digests"
    assert runner.DATABASE == "docsuri_u5"
    assert runner.DATABASE_PORT == 15489 and runner.APPLICATION_PORT == 18089
    assert runner.POLICY == "u5-synthetic-v1"


def test_realm_transport_binding_is_owned(realm):
    transport = inspect_transport(realm)
    prepared = prepare_transport(realm)
    assert str(transport.certificate) == str(prepared.certificate)
    assert prepared.certificate.is_file() and prepared.key.is_file()


def test_local_profile_load_requires_the_owned_manifest(realm):
    with pytest.raises(ValueError):
        LocalProfile.load(realm.root / "missing.json")
    profile = LocalProfile.load(realm.root / "environment.json")
    assert profile.realm == "topics-digests" and profile.database_name == "docsuri_u5"
    assert profile.origin == "https://127.0.0.1:18089"
