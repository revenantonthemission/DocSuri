from __future__ import annotations

import pytest

from docsuri_ops.platform_control import authority, enums
from docsuri_ops.platform_control.errors import ControlError

pytestmark = pytest.mark.u7_component


def granted(actor="operator", scope=("t-1",), ops=("platform.file.write",), klass=enums.CLASS_ROUTINE):
    return authority.Grant(
        authority_id="a-1",
        actor_reference=actor,
        target_scope=scope,
        permitted_operation=ops,
        authority_class=klass,
    )


def test_local_actor_is_derived_from_the_os_not_the_request():
    actor = authority.local_actor()
    assert actor and len(actor) <= 128


@pytest.mark.parametrize("scope", [["*"], ["all"], [""], ["bad/../path"]])
def test_wildcard_or_implicit_scope_is_invalid(scope):
    with pytest.raises(ControlError) as excinfo:
        authority.explicit_scope(scope)
    assert excinfo.value.code == "INVALID_INPUT"


def test_explicit_scope_is_accepted():
    assert authority.explicit_scope(["t-1", "t-2"]) == ("t-1", "t-2")


def test_wrong_actor_is_forbidden_before_any_effect():
    with pytest.raises(ControlError) as excinfo:
        authority.authority_admits(
            granted(),
            actor="someone-else",
            operation="platform.file.write",
            target="t-1",
            requested_class=enums.CLASS_ROUTINE,
            execute=True,
        )
    assert excinfo.value.code == "FORBIDDEN"


def test_target_outside_grant_is_forbidden():
    with pytest.raises(ControlError) as excinfo:
        authority.authority_admits(
            granted(),
            actor="operator",
            operation="platform.file.write",
            target="t-2",
            requested_class=enums.CLASS_ROUTINE,
            execute=True,
        )
    assert excinfo.value.code == "FORBIDDEN"


def test_routine_grant_cannot_cover_a_destructive_release_operation():
    with pytest.raises(ControlError) as excinfo:
        authority.authority_admits(
            granted(ops=("platform.target.release",)),
            actor="operator",
            operation="platform.target.release",
            target="t-1",
            requested_class=enums.CLASS_DESTRUCTIVE,
            execute=True,
        )
    assert excinfo.value.code == "FORBIDDEN"


def test_evidence_reader_grant_can_read_but_never_authorize_an_effect():
    reader = granted(ops=(), klass=enums.CLASS_READER)
    authority.authority_admits(
        reader,
        actor="operator",
        operation="inspectEvidence",
        target="t-1",
        requested_class=enums.CLASS_ROUTINE,
        execute=False,
    )
    with pytest.raises(ControlError) as excinfo:
        authority.authority_admits(
            reader,
            actor="operator",
            operation="platform.file.write",
            target="t-1",
            requested_class=enums.CLASS_ROUTINE,
            execute=True,
        )
    assert excinfo.value.code == "FORBIDDEN"


def test_revoked_grant_never_admits_an_effect():
    revoked = authority.Grant(
        authority_id="a-1",
        actor_reference="operator",
        target_scope=("t-1",),
        permitted_operation=("platform.file.write",),
        authority_class=enums.CLASS_ROUTINE,
        revocation="revoked",
    )
    with pytest.raises(ControlError) as excinfo:
        authority.authority_admits(
            revoked,
            actor="operator",
            operation="platform.file.write",
            target="t-1",
            requested_class=enums.CLASS_ROUTINE,
            execute=True,
        )
    assert excinfo.value.code == "FORBIDDEN"


def test_operation_outside_permitted_set_is_forbidden():
    with pytest.raises(ControlError):
        authority.authority_admits(
            granted(ops=("platform.file.probe",)),
            actor="operator",
            operation="platform.file.write",
            target="t-1",
            requested_class=enums.CLASS_ROUTINE,
            execute=True,
        )
