"""The supply-chain check must reject a mutable deployment input, not just agree with the file.

A validator that only ever confirms the committed targets are clean is indistinguishable from no
validator, so each mutation below asserts a specific failure.
"""

import copy
import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "platform-integrity" / "validate_supply_chain.py"
TARGETS = Path(__file__).resolve().parents[1] / "platform-integrity" / "sbom-targets.json"

_spec = importlib.util.spec_from_file_location("validate_supply_chain", SCRIPT)
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)
unpinned_images = _module.unpinned_images
image_references = _module.image_references

PINNED = "sha256:" + "a" * 64


@pytest.fixture
def targets() -> dict:
    return json.loads(TARGETS.read_bytes())


def test_committed_targets_are_fully_digest_pinned(targets):
    assert unpinned_images(targets) == []


def test_every_declared_reference_is_covered(targets):
    resolved = image_references(targets)
    assert {"images.postgres", "derivedImages.postgres"} <= set(resolved)
    # A derived image's base is a cross-reference, not a literal reference.
    assert resolved["derivedImages.postgres.base"] == "postgresUpstreamBase"


def test_a_mutable_tag_is_rejected(targets):
    targets["images"]["redis"] = "redis:7-alpine"
    assert unpinned_images(targets) == ["images.redis: redis:7-alpine"]


def test_a_declared_image_with_no_digest_is_rejected(targets):
    """Absence of a pin is the failure case, not a pass."""
    targets["images"]["opensearch"] = {"findings": 0}
    assert unpinned_images(targets) == ["images.opensearch: <no digest declared>"]


def test_a_derived_image_may_not_fall_back_to_a_tag(targets):
    targets["derivedImages"]["postgres"] = {"base": "postgresUpstreamBase", "digest": "x:latest"}
    assert unpinned_images(targets) == ["derivedImages.postgres: x:latest"]


def test_a_base_pointing_at_an_undeclared_entry_is_rejected(targets):
    """A dangling base silently drops the inherited pinning guarantee."""
    targets["derivedImages"]["postgres"] = {"base": "ghostBase", "digest": f"x@{PINNED}"}
    assert unpinned_images(targets) == ["derivedImages.postgres.base: ghostBase"]


def test_findings_do_not_become_ci_failures(targets):
    """CVE disposition stays an explicit operator concern, not an implicit gate here."""
    targets["nativeRuntimes"]["clockObserver"] = {"blockingFindings": 3}
    targets["images"]["clockObserver"] = {"digest": f"clock@{PINNED}", "findings": 5}
    assert unpinned_images(targets) == []


def test_a_malformed_section_is_rejected(targets):
    targets["images"] = ["postgres@sha256:abc"]
    with pytest.raises(TypeError):
        image_references(targets)


def test_missing_sections_yield_nothing_to_check():
    assert unpinned_images({}) == []


def test_main_exits_zero_on_the_committed_file(capsys):
    assert _module.main(["validate_supply_chain.py", str(TARGETS)]) == 0
    assert "digest-pinned" in capsys.readouterr().out


def test_main_exits_nonzero_on_a_mutable_target(tmp_path, capsys):
    target = tmp_path / "targets.json"
    target.write_text(json.dumps({"images": {"redis": "redis:7-alpine"}}))
    assert _module.main(["validate_supply_chain.py", str(target)]) == 1
    assert "not digest-pinned" in capsys.readouterr().err


def test_main_requires_exactly_one_argument():
    assert _module.main(["validate_supply_chain.py"]) == 2


def test_targets_are_not_mutated_by_validation(targets):
    snapshot = copy.deepcopy(targets)
    unpinned_images(targets)
    assert targets == snapshot
