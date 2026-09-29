"""The frozen operator plan is digest-pinned and read through a protected path."""

import os
import stat

import pytest

from docsuri_platform_integrity.contracts.codec import canonical, digest
from docsuri_platform_integrity.deployment.operator_plan import (
    MAX_PLAN_BYTES,
    FrozenPlan,
    read_frozen_plan,
)

RELEASE = "r1-2026.09"
D = digest(b"step-definition")
OTHER = digest(b"other")


def write_plan(path, *, release=RELEASE, identities=None, mode=0o400):
    payload = {"release": release,
               "identities": identities or {"registry:apply": D, "registry:adopt": OTHER}}
    data = canonical(payload)
    if path.exists():
        os.chmod(path, 0o600)
    path.write_bytes(data)
    os.chmod(path, mode)
    return data


def test_plan_is_read_when_pinned_digest_owner_and_mode_hold(tmp_path):
    plan_path = tmp_path / "operator-plan.json"
    data = write_plan(plan_path)
    plan = read_frozen_plan(plan_path, digest(data), release=RELEASE)
    assert plan.identities["registry:apply"] == D
    assert plan.definition("registry:adopt") == OTHER
    assert plan.definition("registry:absent") is None


def test_plan_for_another_release_is_refused(tmp_path):
    plan_path = tmp_path / "operator-plan.json"
    data = write_plan(plan_path)
    with pytest.raises(PermissionError, match="another release"):
        read_frozen_plan(plan_path, digest(data), release="r1-other")


def test_substituted_plan_is_refused_before_it_is_interpreted(tmp_path):
    plan_path = tmp_path / "operator-plan.json"
    data = write_plan(plan_path)
    with pytest.raises(PermissionError, match="digest does not match"):
        read_frozen_plan(plan_path, OTHER, release=RELEASE)
    # The pinned value is the only thing that admits a plan; rewriting the file is not enough.
    write_plan(plan_path, identities={"registry:apply": OTHER})
    with pytest.raises(PermissionError, match="digest does not match"):
        read_frozen_plan(plan_path, digest(data), release=RELEASE)


@pytest.mark.parametrize("mode", [0o666, 0o664, 0o646, 0o620, 0o602])
def test_group_or_world_writable_plan_is_refused(tmp_path, mode):
    plan_path = tmp_path / "operator-plan.json"
    data = write_plan(plan_path, mode=mode)
    with pytest.raises(PermissionError, match="not protected"):
        read_frozen_plan(plan_path, digest(data), release=RELEASE)


@pytest.mark.parametrize("mode", [0o400, 0o444, 0o644, 0o640])
def test_readable_but_non_writable_plan_is_accepted(tmp_path, mode):
    # A plan holds identity-to-digest pairs, not secrets, so group or world *read* is fine.
    # Only a write bit would let anyone substitute a plan, so only that is rejected.
    plan_path = tmp_path / "operator-plan.json"
    data = write_plan(plan_path, mode=mode)
    assert read_frozen_plan(plan_path, digest(data), release=RELEASE).identities


def test_symlinked_plan_is_refused(tmp_path):
    plan_path = tmp_path / "operator-plan.json"
    data = write_plan(plan_path)
    link = tmp_path / "link.json"
    link.symlink_to(plan_path)
    with pytest.raises(PermissionError, match="symlink"):
        read_frozen_plan(link, digest(data), release=RELEASE)


def test_oversized_plan_is_refused(tmp_path):
    data = write_plan(tmp_path / "reference.json")
    assert MAX_PLAN_BYTES >= len(data)
    plan_path = tmp_path / "operator-plan.json"
    plan_path.write_bytes(b"{" + b" " * MAX_PLAN_BYTES + b"}")
    os.chmod(plan_path, 0o400)
    with pytest.raises(PermissionError, match="not protected"):
        read_frozen_plan(plan_path, digest(b"{}"), release=RELEASE)


def test_empty_plan_authorizes_nothing():
    # A plan with no identities would authorize nothing, so it is not a valid plan at all.
    with pytest.raises(ValueError):
        FrozenPlan.model_validate({"release": RELEASE, "identities": {}})


def test_hardlinked_plan_is_refused(tmp_path):
    plan_path = tmp_path / "operator-plan.json"
    data = write_plan(plan_path)
    other = tmp_path / "other.json"
    os.link(plan_path, other)
    assert plan_path.stat().st_nlink == 2
    with pytest.raises(PermissionError, match="not protected"):
        read_frozen_plan(plan_path, digest(data), release=RELEASE)
    assert stat.S_IMODE(plan_path.stat().st_mode) == 0o400
