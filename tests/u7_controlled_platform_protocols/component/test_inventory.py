from __future__ import annotations

import pytest

from docsuri_ops.platform_control import enums, inventory

pytestmark = pytest.mark.u7_component


def test_every_protocol_carries_an_explicit_disposition():
    loaded = inventory.load_inventory()
    assert len(loaded.protocols) >= 4
    assert all(p.disposition in enums.PROTOCOL_DISPOSITIONS for p in loaded.protocols)
    summary = inventory.dispositions_summary(loaded)
    assert sum(summary.values()) == len(loaded.protocols)
    assert summary[enums.DISPOSITION_RETAINED] >= 1


def test_admitted_vocabulary_is_the_retained_set_only():
    loaded = inventory.load_inventory()
    admitted = set(loaded.admitted_names())
    for protocol in loaded.protocols:
        if protocol.name in admitted:
            assert protocol.disposition == enums.DISPOSITION_RETAINED
            assert protocol.native_verified is True
        else:
            assert not protocol.is_executable


def test_cloud_dependent_protocols_are_recorded_not_executable():
    loaded = inventory.load_inventory()
    recorded = [
        p for p in loaded.protocols if p.disposition != enums.DISPOSITION_RETAINED
    ]
    assert recorded
    assert all(p.consumer_impact for p in recorded)
    assert all(not p.is_executable for p in recorded)


@pytest.mark.parametrize("protocol", [p for p in inventory.load_inventory().protocols])
def test_every_protocol_declares_a_finite_window_and_deadline(protocol):
    assert protocol.max_age_seconds > 0
    assert protocol.deadline_seconds > 0
    assert protocol.effect_kind in enums.EFFECT_KINDS


def test_unknown_operation_is_not_in_the_vocabulary():
    loaded = inventory.load_inventory()
    assert loaded.by_name("rm -rf /") is None
    assert loaded.by_name("platform.unknown.op") is None


def test_consumer_matrix_records_compatibility_truthfully():
    loaded = inventory.load_inventory()
    assert loaded.consumers
    allowed = {"recorded-only", "compatibility-dependent"}
    assert all(c.compatibility in allowed for c in loaded.consumers)
    assert any(c.compatibility == "compatibility-dependent" for c in loaded.consumers)


def test_inventory_rejects_a_missing_validity_window(tmp_path):
    import json

    forged = {
        "version": 1,
        "protocols": [
            {
                "name": "x",
                "disposition": "retained-local",
                "authorityClass": "routine",
                "maxAgeSeconds": 0,
                "deadlineSeconds": 10,
                "effectKind": "file-write",
                "nativeVerified": True,
            }
        ],
    }
    path = tmp_path / "inventory.json"
    path.write_text(json.dumps(forged))
    with pytest.raises(ValueError):
        inventory.load_inventory(path)
