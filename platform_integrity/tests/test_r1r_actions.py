"""R1R action surface: the closed vocabulary, role separation, and machine-readable refusal."""

import json

import pytest

from docsuri_platform_integrity.cli.__main__ import main
from docsuri_platform_integrity.domain.actions import (
    ACTIONS,
    FORBIDDEN_REQUEST_KINDS,
    READONLY_ACTIONS,
    REQUEST_KINDS,
    ROLE_ACTIONS,
    ROLES,
    authorize,
    is_readonly,
    non_success,
    resolve_request,
)


def test_the_vocabulary_is_closed():
    assert set(ACTIONS) == {"check", "plan", "verify", "apply", "reconcile", "backup"}
    assert set(ROLES) == {
        "generator", "scanner", "publisher", "signer", "auditor", "backup", "reader"
    }
    for role, allowed in ROLE_ACTIONS.items():
        assert role in ROLES
        assert allowed <= set(ACTIONS), f"{role} names an action outside the vocabulary"
        assert allowed, f"{role} must hold at least one action"
    assert set(REQUEST_KINDS) <= set(ACTIONS) | {"schema", "audit", "capabilities",
                                                 "generation", "target", "receipt"}


def test_only_publisher_may_apply():
    holders = {role for role, allowed in ROLE_ACTIONS.items() if "apply" in allowed}
    assert holders == {"publisher"}
    assert not any(
        "apply" in ROLE_ACTIONS[role] for role in ("reader", "signer", "backup", "auditor")
    )


def test_separate_roles_do_not_accumulate_privilege():
    """No role holds the union of every action; duties stay separate."""
    everyone = frozenset().union(*ROLE_ACTIONS.values())
    assert everyone == frozenset(ACTIONS)
    for role in ROLES:
        assert ROLE_ACTIONS[role] != everyone
    assert ROLE_ACTIONS["signer"] & ROLE_ACTIONS["publisher"] == frozenset(
        ROLE_ACTIONS["signer"] & ROLE_ACTIONS["publisher"]
    ) & frozenset({"check"}), "signer and publisher may only overlap on readonly check"
    assert "apply" not in ROLE_ACTIONS["signer"]
    assert "backup" not in ROLE_ACTIONS["publisher"]


def test_backup_and_audit_roles_are_distinct():
    assert "backup" in ROLE_ACTIONS["backup"]
    assert "backup" not in ROLE_ACTIONS["auditor"]
    assert "reconcile" in ROLE_ACTIONS["auditor"]
    assert "reconcile" not in ROLE_ACTIONS["backup"]


@pytest.mark.parametrize("role", list(ROLES))
def test_a_role_may_perform_exactly_its_own_actions(role):
    for action in ACTIONS:
        if action in ROLE_ACTIONS[role]:
            assert authorize(role, action) == action
        else:
            with pytest.raises(PermissionError):
                authorize(role, action)


def test_unknown_role_or_action_is_refused():
    with pytest.raises(PermissionError):
        authorize("root", "apply")
    with pytest.raises(ValueError):
        authorize("publisher", "rm")


@pytest.mark.parametrize("kind", list(FORBIDDEN_REQUEST_KINDS))
def test_shell_path_sql_and_sign_requests_are_unrepresentable(kind):
    for role in ROLES:
        with pytest.raises(PermissionError):
            resolve_request(role, kind, "anything")


def test_requests_are_names_from_a_closed_set():
    assert resolve_request("generator", "schema", "closure") == ("schema", "closure")
    with pytest.raises(ValueError):
        resolve_request("generator", "schema", "rm -rf /")
    with pytest.raises(ValueError):
        resolve_request("generator", "unknown", "closure")


def test_readonly_classification():
    assert READONLY_ACTIONS == set(ACTIONS) - {"apply"}
    assert not is_readonly("apply")
    assert all(is_readonly(a) for a in ACTIONS if a != "apply")
    with pytest.raises(ValueError):
        is_readonly("destroy")


def test_non_success_has_no_partial_pass():
    with pytest.raises(ValueError):
        non_success("PASS", "because")
    assert non_success("BLOCKED", "native_authority_required")["state"] == "BLOCKED"
    assert non_success("REFUSED", "action_not_permitted_for_role")["state"] == "REFUSED"


# -- CLI surface ----------------------------------------------------------


def test_apply_stays_blocked_and_is_never_a_default(capsys):
    assert main(["apply"]) == 2
    assert json.loads(capsys.readouterr().out)["mutationReady"] is False


def test_every_action_reports_machine_readable_non_success(capsys):
    for argv, expected in (
        (["plan"], 2),
        (["reconcile"], 2),
        (["backup", "--generation", "current"], 2),
        (["apply"], 2),
    ):
        assert main(argv) == expected
        payload = json.loads(capsys.readouterr().out)
        assert payload["state"] in {"BLOCKED", "INCOMPLETE", "REFUSED"}
        assert payload["mutationReady"] is False


def test_role_is_enforced_when_supplied(capsys):
    assert main(["apply", "--role", "publisher"]) == 2
    capsys.readouterr()
    assert main(["apply", "--role", "reader"]) == 3
    assert json.loads(capsys.readouterr().out) == {
        "state": "REFUSED", "reason": "action_not_permitted_for_role"
    }
    assert main(["backup", "--generation", "current", "--role", "reader"]) == 3
    assert main(["plan", "--role", "signer"]) == 3
    assert main(["reconcile", "--role", "auditor"]) == 2
    capsys.readouterr()


def test_refusal_never_echoes_the_requested_action(capsys):
    main(["apply", "--role", "reader"])
    out = capsys.readouterr().out
    assert "apply" not in out and "reader" not in out


def test_backup_and_reconcile_named_requests_are_validated(capsys):
    assert main(["reconcile", "--role", "auditor"]) == 2
    assert json.loads(capsys.readouterr().out)["action"] == "reconcile"
    assert main(["backup", "--generation", "current", "--role", "backup"]) == 2
    assert json.loads(capsys.readouterr().out)["readonly"] is True


def test_missing_arguments_do_not_reach_a_tool(capsys):
    with pytest.raises(SystemExit):
        main(["backup"])
    with pytest.raises(SystemExit):
        main(["reconcile", "--role", "not-a-role"])
    with pytest.raises(SystemExit):
        main([])
    assert capsys.readouterr().out == ""
