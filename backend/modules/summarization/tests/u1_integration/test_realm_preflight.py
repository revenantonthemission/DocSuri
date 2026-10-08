"""Local guard tests, never a substitute for operator isolation/database proof."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import Mock

import pytest

from tests.u1_integration.realm import (
    AuthorityRealm,
    RealmBlocked,
    open_authority_connection,
    require_authority_realm,
)


def realm() -> AuthorityRealm:
    return AuthorityRealm("synthetic", "postgres-u1", "172.31.200.2", 5432,
                          "docsuri_u1_authority_synthetic", "docsuri_u1_authority_synthetic",
                          "a" * 64, "postgresql://synthetic", "docsuri_u1_purge_synthetic",
                          "b" * 64, "c" * 64, "d" * 64, "2099-01-01T00:00:00Z", 4, ())


def permit_synthetic_guard_unit_test(monkeypatch) -> None:
    # Explicit local test seam only; real fixtures ALWAYS re-read protected proof.
    monkeypatch.setattr(AuthorityRealm, "check_current", lambda _self: None)


def identity() -> tuple:
    target = realm()
    return (target.database, target.role, target.address, target.port, target.realm_id,
            False, False, False, target.source_digest, target.launcher_digest, target.rules_digest,
            datetime(2099, 1, 1, tzinfo=UTC), "authority")


def connection(row: tuple, *, readonly: bool = False):
    result = Mock()
    privileges = (False, False, False, True, False, False, False, False, False, False, 4)
    def execute(sql, *_args):
        if sql.startswith("SHOW") and readonly:
            value = ("on",)
        elif "rolbypassrls" in sql:
            value = privileges
        else:
            value = row
        return Mock(fetchone=Mock(return_value=value))

    result.execute.side_effect = execute
    return result


def test_missing_manifest_fails_before_any_connection_attempt(monkeypatch) -> None:
    connect = Mock()
    monkeypatch.setattr("psycopg.connect", connect)
    with pytest.raises(RealmBlocked, match="required"):
        require_authority_realm({})
    connect.assert_not_called()


def test_two_connections_are_separated_by_readonly_identity_success(monkeypatch) -> None:
    permit_synthetic_guard_unit_test(monkeypatch)
    first = connection(identity(), readonly=True)
    second = connection(identity())
    connect = Mock(side_effect=[first, second])
    monkeypatch.setattr("psycopg.connect", connect)
    assert open_authority_connection(realm()) is second
    assert connect.call_count == 2
    assert "default_transaction_read_only=on" in connect.call_args_list[0].kwargs["options"]
    first.close.assert_called_once()
    assert all(call.args[0].lstrip().startswith(("SHOW", "SELECT"))
               for actor in (first, second) for call in actor.execute.call_args_list)


@pytest.mark.parametrize("position,value", [
    (0, "production"), (1, "production-role"), (2, "192.168.1.2"),
    (3, 5433), (4, "wrong-marker"), (5, True), (6, True), (7, True),
])
def test_wrong_identity_never_opens_the_mutation_connection(monkeypatch, position, value) -> None:
    permit_synthetic_guard_unit_test(monkeypatch)
    row = list(identity())
    row[position] = value
    first = connection(tuple(row), readonly=True)
    connect = Mock(return_value=first)
    monkeypatch.setattr("psycopg.connect", connect)
    with pytest.raises(RealmBlocked, match="identity mismatch"):
        open_authority_connection(realm())
    assert connect.call_count == 1
    first.close.assert_called_once()


def test_initial_probe_cannot_silently_be_a_writable_session(monkeypatch) -> None:
    permit_synthetic_guard_unit_test(monkeypatch)
    first = connection(identity())
    connect = Mock(return_value=first)
    monkeypatch.setattr("psycopg.connect", connect)
    with pytest.raises(RealmBlocked, match="read-only"):
        open_authority_connection(realm())
    assert connect.call_count == 1
    first.close.assert_called_once()


def test_rebinding_between_probe_and_second_connection_is_rechecked_before_ddl(monkeypatch) -> None:
    permit_synthetic_guard_unit_test(monkeypatch)
    first = connection(identity(), readonly=True)
    second = connection(("wrong-database", *identity()[1:]))
    monkeypatch.setattr("psycopg.connect", Mock(side_effect=[first, second]))
    with pytest.raises(RealmBlocked, match="identity mismatch"):
        open_authority_connection(realm())
    second.close.assert_called_once()
    assert len(second.execute.call_args_list) == 1
    assert second.execute.call_args.args[0].lstrip().startswith("SELECT")


def test_driver_error_does_not_open_second_connection_or_print_raw_error(monkeypatch) -> None:
    permit_synthetic_guard_unit_test(monkeypatch)
    connect = Mock(side_effect=RuntimeError("private driver credential"))
    monkeypatch.setattr("psycopg.connect", connect)
    with pytest.raises(RealmBlocked, match="preflight failed") as error:
        open_authority_connection(realm())
    assert "private" not in str(error.value)
    assert connect.call_count == 1


def test_constructed_realm_or_user_document_is_not_proof(monkeypatch, tmp_path) -> None:
    import hashlib

    from tests.u1_integration.realm import _document

    connect = Mock()
    monkeypatch.setattr("psycopg.connect", connect)
    with pytest.raises(RealmBlocked, match="required"):
        open_authority_connection(realm())
    path = tmp_path / "self-authored.json"
    path.write_text("{}")
    with pytest.raises(RealmBlocked, match="operator ownership"):
        _document(str(path), hashlib.sha256(b"{}").hexdigest())
    connect.assert_not_called()


@pytest.mark.parametrize("position", [0, 1, 2, 4, 5, 6, 7, 8, 9, 10])
def test_marker_write_and_admin_privileges_block_mutation(monkeypatch, position) -> None:
    permit_synthetic_guard_unit_test(monkeypatch)
    first = connection(identity(), readonly=True)
    old = first.execute.side_effect
    privileges = [False, False, False, True, False, False, False, False, False, False, 4]
    privileges[position] = True
    def execute(sql, *args):
        if "rolbypassrls" in sql:
            return Mock(fetchone=Mock(return_value=tuple(privileges)))
        return old(sql, *args)

    first.execute.side_effect = execute
    connect = Mock(return_value=first)
    monkeypatch.setattr("psycopg.connect", connect)
    with pytest.raises(RealmBlocked, match="privileges invalid"):
        open_authority_connection(realm())
    assert connect.call_count == 1


def test_expired_proof_at_second_preflight_closes_mutation_connection(monkeypatch) -> None:
    checks = Mock(side_effect=[None, RealmBlocked("proof expired")])
    monkeypatch.setattr(AuthorityRealm, "check_current", lambda _self: checks())
    first, second = connection(identity(), readonly=True), connection(identity())
    monkeypatch.setattr("psycopg.connect", Mock(side_effect=[first, second]))
    with pytest.raises(RealmBlocked, match="expired"):
        open_authority_connection(realm())
    second.close.assert_called_once()
    assert all(call.args[0].lstrip().startswith("SELECT") for call in second.execute.call_args_list)


@pytest.mark.parametrize("failure", [
    "expired", "wrong-source", "role", "missing-probe", "indirection",
])
def test_protected_document_semantic_negatives_fail_before_connect(monkeypatch, failure) -> None:
    from tests.u1_integration import realm as module

    # Pure reader/schema fixtures, not files or independent isolation receipts.
    token = "0123456789abcdef"
    endpoint = {"host": "postgres-u1", "address": "172.31.200.2", "port": 5432}
    binding = {"unit": "u1-job-skeleton", "environment": "u1-staging", "realm_id": token,
               "context": "colima", **{key: "a" * 64 for key in (
                   "config_sha256", "guest_id", "runtime_sha256", "source_sha256",
                   "launcher_sha256", "rules_sha256", "credential_channel_sha256")}}
    manifest = {
        "version": 1, "unit": "u1-job-skeleton", "environment": "u1-staging", "realm_id": token,
        "workload_hostname": "u1-test", "isolation_receipt_sha256": "b" * 64,
        "internal_network_cidr": "172.31.200.0/24", "binding": binding,
        "authority_database": {**endpoint, "database": "docsuri_u1_authority_" + token,
                               "role": "docsuri_u1_authority_" + token, "connection_limit": 4},
        "purge_database": {**endpoint, "database": "docsuri_u1_purge_" + token,
                           "role": "docsuri_u1_purge_" + token, "connection_limit": 2},
    }
    receipt = {
        "unit": manifest["unit"], "environment": manifest["environment"], "realm_id": token,
        "valid_until": "2099-01-01T00:00:00Z", "binding": dict(binding),
        "verified": {"direct_egress_denied": True, "host_lan_production_denied": True,
                     "unqualified_address_families_denied": True},
        "observations": {key: {"outcome": "PASS", "evidence_sha256": "c" * 64} for key in (
            "exact_database_access", "direct_egress_denied", "host_lan_production_denied",
            "unqualified_address_families_denied", "no_production_mounts_or_credentials",
            "marker_write_denied", "cross_database_denied", "bounded_roles")},
    }
    env = {"DOCSURI_U1_TEST_REALM_MANIFEST": "/operator/manifest",
           "DOCSURI_U1_TEST_REALM_SHA256": "a" * 64,
           "DOCSURI_U1_ISOLATION_RECEIPT": "/operator/receipt",
           "DOCSURI_U1_ISOLATION_RECEIPT_SHA256": "b" * 64,
           "DOCSURI_U1_AUTHORITY_DSN": ("host=postgres-u1 port=5432 "
                                       f"dbname=docsuri_u1_authority_{token} "
                                       f"user=docsuri_u1_authority_{token}")}
    monkeypatch.setattr(module, "_document", lambda path, _digest:
                        manifest if path.endswith("manifest") else receipt)
    monkeypatch.setattr(module.os, "uname", lambda: Mock(sysname="Linux"))
    monkeypatch.setattr(module.socket, "gethostname", lambda: "u1-test")
    connect = Mock()
    monkeypatch.setattr("psycopg.connect", connect)
    # Valid synthetic reader binding parses, but no connection/proof is produced.
    assert module.require_authority_realm(env).source_digest == "a" * 64
    if failure == "expired":
        receipt["valid_until"] = "2000-01-01T00:00:00Z"
    elif failure == "wrong-source":
        receipt["binding"]["source_sha256"] = "0" * 64
    elif failure == "role":
        manifest["authority_database"]["role"] = "admin"
    elif failure == "missing-probe":
        receipt["observations"].pop("marker_write_denied")
    else:
        env["DOCSURI_U1_AUTHORITY_DSN"] += " options='-c role=admin'"
    with pytest.raises(RealmBlocked):
        module.require_authority_realm(env)
    connect.assert_not_called()
