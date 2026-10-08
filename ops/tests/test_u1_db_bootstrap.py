"""Local inspect/application-port negatives, not artifact/isolation/operator receipts."""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import Mock

import pytest

from server import u1_db_bootstrap as bootstrap


def config() -> dict:
    token = "0123456789abcdef"
    endpoint = {"host": "postgres-u1", "address": "172.31.200.2", "port": 5432}
    return {
        "version": 1, "unit": "u1-job-skeleton", "environment": "u1-staging", "realm_id": token,
        "context": "colima", "guest_id": "a" * 64, "runtime_digest": "b" * 64,
        "source_digest": "c" * 64,
        "launcher_digest": bootstrap.digest(Path(bootstrap.__file__).read_bytes()),
        "rules_digest": "d" * 64, "postgres_image": "docsuri/postgres@sha256:" + "1" * 64,
        "workload_image": "docsuri/u1-tests@sha256:" + "2" * 64,
        "postgres_uid": 70, "workload_uid": 1000, "operator_uid": 501,
        "workload_hostname": "u1-test", "internal_network_cidr": "172.31.200.0/24",
        "authority_database": {**endpoint, "database": "docsuri_u1_authority_" + token,
                               "role": "docsuri_u1_authority_" + token, "connection_limit": 4},
        "purge_database": {**endpoint, "database": "docsuri_u1_purge_" + token,
                           "role": "docsuri_u1_purge_" + token, "connection_limit": 2},
        "memory_bytes": 268435456, "cpus": 1, "disk_reserve_bytes": 268435456,
        "max_connections": 20,
        "credential_channel_digest": "e" * 64,
        "valid_until": (datetime.now(UTC) + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def plan():
    return bootstrap.build_plan(json.dumps(config()).encode())


def documents(target):
    """Synthetic local objects ONLY; no root-owned file or measured probe produced."""
    c = target.config
    binding = {"unit": c.unit, "environment": c.environment, "realm_id": c.realm_id,
               "config_sha256": target.config_digest, "context": c.context, "guest_id": c.guest_id,
               "runtime_sha256": c.runtime_digest, "source_sha256": c.source_digest,
               "launcher_sha256": c.launcher_digest, "rules_sha256": c.rules_digest,
               "credential_channel_sha256": c.credential_channel_digest}
    common = {"binding": binding, "valid_until": c.valid_until}
    fresh_resources = [a.identity for a in target.actions if a.operation in {
        "create_internal_network", "create_owned_volume", "start_private_postgres",
        "start_unadmitted_probe_workload",
    }]
    return {
        "auth": {**common, "operator": "revenantonthemission", "operation": "bootstrap",
                 "original_inventory_sha256": "1" * 64, "qualified_artifacts_sha256": "2" * 64},
        "qualification": {**common, "images": [c.postgres_image, c.workload_image],
                          "disposition": "QUALIFIED", "blocking_findings": [],
                          "security_report_sha256": "3" * 64},
        "inventory": {**common, "nonoverlapping_cidr": c.internal_network_cidr,
                      "fresh_resources_absent": fresh_resources,
                      "disk_available_bytes": c.disk_reserve_bytes,
                      "memory_available_bytes": c.memory_bytes},
    }


def admission(monkeypatch, docs):
    references = {name: bootstrap.DocumentReference(Path("/operator/" + name), digest)
                  for name, digest in (("auth", "0" * 64), ("inventory", "1" * 64),
                                       ("qualification", "2" * 64))}
    monkeypatch.setattr(bootstrap, "protected_document", lambda ref: docs[ref.path.name])
    return bootstrap.ProtectedAdmission(references["auth"], references["qualification"],
                                        references["inventory"])


def test_inspection_never_applies(tmp_path, monkeypatch, capsys) -> None:
    raw = json.dumps(config()).encode()
    path = tmp_path / "public.json"
    path.write_bytes(raw)
    monkeypatch.setattr(bootstrap.os, "environ", {})
    assert bootstrap.main(["--config", str(path), "--sha256", bootstrap.digest(raw)]) == 0
    report = json.loads(capsys.readouterr().out)
    assert not report["application_performed"] and not report["realm_admitted"]
    assert len(report["actions"]) == 9 and len(report["reversal"]) == 8
    operations = [a["operation"] for a in report["actions"]]
    assert operations.index("apply_owned_guest_rules") < operations.index("start_private_postgres")
    assert (operations.index("withdraw_provisioner_credentials")
            < operations.index("start_unadmitted_probe_workload"))
    postgres = report["actions"][5]["parameters"]
    assert postgres["published_ports"] == [] and postgres["capabilities"] == []
    assert postgres["read_only_root"]
    sql = report["actions"][6]["parameters"]["sql"]
    assert "NOBYPASSRLS" in sql and "NOINHERIT" in sql and "TEMPLATE template0" in sql
    assert "CONNECTION LIMIT 4" in sql and "CONNECTION LIMIT 2" in sql
    assert "GRANT SELECT ON TABLE public.u1_test_realm" in sql
    assert "PASSWORD" not in sql and "content_jobs" not in sql and "DROP SCHEMA" not in sql
    assert not any(word in json.dumps(report)
                   for word in ("docker.sock", "run.sh", "MinIO", "SENDING"))


@pytest.mark.parametrize("change", [
    {"environment": "production"}, {"postgres_image": "postgres:16"}, {"max_connections": 0},
    {"workload_uid": 501}, {"cpus": True}, {"version": True},
    {"internal_network_cidr": "127.0.0.0/24"},
    {"internal_network_cidr": "2001:db8::/64"}, {"valid_until": "2026-02-30T00:00:00Z"},
    {"password": "must-not-be-config"},
])
def test_wrong_environment_artifacts_resources_and_secrets_fail_inspection(change) -> None:
    with pytest.raises(bootstrap.BootstrapBlocked):
        bootstrap.build_plan(json.dumps({**config(), **change}).encode())


@pytest.mark.parametrize("change", [
    {"database": "production"}, {"role": "admin"}, {"host": "localhost"},
    {"address": "172.30.1.25"}, {"address": "172.31.200.0"}, {"port": 13000},
])
def test_wrong_role_endpoint_or_cross_database_cannot_reuse_authority_scope(change) -> None:
    raw = config()
    raw["authority_database"].update(change)
    with pytest.raises(bootstrap.BootstrapBlocked):
        bootstrap.build_plan(json.dumps(raw).encode())


@pytest.mark.parametrize("variable", [
    "DATABASE_URL", "PGSERVICE", "PGPASSFILE", "PGHOSTADDR", "AWS_PROFILE",
])
def test_credentials_wrong_hash_and_missing_configuration_do_not_apply(tmp_path, variable) -> None:
    raw = json.dumps(config()).encode()
    path = tmp_path / "public.json"
    path.write_bytes(raw)
    with pytest.raises(bootstrap.BootstrapBlocked, match="environment_refused"):
        bootstrap.inspect_file(path, bootstrap.digest(raw), {variable: "secret-never-output"})
    with pytest.raises(bootstrap.BootstrapBlocked, match="digest_mismatch"):
        bootstrap.inspect_file(path, "f" * 64, {})
    with pytest.raises(bootstrap.BootstrapBlocked):
        bootstrap.inspect_file(tmp_path / "missing", "f" * 64, {})
    with pytest.raises(bootstrap.BootstrapBlocked, match="document_invalid"):
        bootstrap.build_plan(b'{"version":1,"version":1}')


def test_user_owned_or_writable_proof_is_not_operator_authority(tmp_path) -> None:
    path = tmp_path / "proof.json"
    path.write_text("{}")
    with pytest.raises(bootstrap.BootstrapBlocked, match="protected"):
        bootstrap.protected_document(bootstrap.DocumentReference(path, bootstrap.digest(b"{}")))


@pytest.mark.parametrize("section,change", [
    ("auth", {"operator": "agent"}), ("auth", {"operation": "rollback"}),
    ("auth", {"original_inventory_sha256": "0" * 64}),
    ("qualification", {"disposition": "CANDIDATE_PENDING_OPERATOR_MAINTENANCE_WINDOW"}),
    ("qualification", {"blocking_findings": ["High CVE-2026-85091"]}),
    ("qualification", {"security_report_sha256": None}),
    ("inventory", {"disk_available_bytes": 0}), ("inventory", {"memory_available_bytes": True}),
    ("inventory", {"fresh_resources_absent": []}),
    ("inventory", {"valid_until": "2000-01-01T00:00:00Z"}),
])
def test_invalid_authority_blocks_executor(monkeypatch, section, change) -> None:
    target = plan()
    docs = documents(target)
    docs[section].update(change)
    executor = Mock()
    with pytest.raises(bootstrap.BootstrapBlocked):
        bootstrap.execute_plan(target, admission(monkeypatch, docs), executor, purpose="bootstrap")
    executor.execute.assert_not_called()


def test_local_sequence_rechecks_each_action_revocation_and_owned_reversal(monkeypatch) -> None:
    target = plan()
    docs = documents(target)
    gate = admission(monkeypatch, docs)
    executor = Mock()
    assert len(bootstrap.execute_plan(target, gate, executor, purpose="bootstrap")) == 9
    assert [call.args[0] for call in executor.execute.call_args_list] == list(target.actions)
    # Revocation after one action prevents every subsequent mutation.
    executor.reset_mock()

    def revoke(_action):
        docs["auth"]["operation"] = "revoked"

    executor.execute.side_effect = revoke
    with pytest.raises(bootstrap.BootstrapBlocked, match="authorization"):
        bootstrap.execute_plan(target, gate, executor, purpose="bootstrap")
    assert executor.execute.call_count == 1
    docs["auth"]["operation"] = "rollback"
    executor.execute.side_effect = None
    executor.reset_mock()
    assert len(bootstrap.execute_plan(target, gate, executor, purpose="rollback")) == 8
    assert [call.args[0] for call in executor.execute.call_args_list] == list(target.reversal)
    assert all("prune" not in a.operation and "production" not in a.identity
               for a in target.reversal)


def test_mutation_and_missing_proof_do_not_admit_or_cleanup(monkeypatch) -> None:
    target = plan()
    docs = documents(target)
    gate = admission(monkeypatch, docs)
    with pytest.raises(bootstrap.BootstrapBlocked, match="authorization"):
        gate.check_current(target, "fixtures")
    docs["auth"]["operation"] = "fixtures"
    with pytest.raises(bootstrap.BootstrapBlocked, match="isolation_required"):
        gate.check_current(target, "fixtures")
    docs["auth"]["operation"] = "bootstrap"
    executor = Mock()
    with pytest.raises(bootstrap.BootstrapBlocked, match="protected_admission_required"):
        bootstrap.execute_plan(target, Mock(), executor, purpose="bootstrap")
    executor.execute.assert_not_called()
    # Synthetic objects test the independent-observation admission branch only;
    # they are never written as receipts and grant no actual fixture access.
    docs["auth"]["operation"] = "fixtures"
    required = {"exact_database_access", "direct_egress_denied", "host_lan_production_denied",
                "unqualified_address_families_denied", "no_production_mounts_or_credentials",
                "marker_write_denied", "cross_database_denied", "bounded_roles"}
    docs["isolation"] = {
        "binding": docs["auth"]["binding"], "valid_until": target.config.valid_until,
        "observations": {key: {"outcome": "PASS", "evidence_sha256": "4" * 64}
                         for key in required},
    }
    full_gate = bootstrap.ProtectedAdmission(
        gate.authorization, gate.qualification, gate.inventory,
        bootstrap.DocumentReference(Path("/operator/isolation"), "5" * 64),
    )
    assert full_gate.check_current(target, "fixtures") is None
    for observations in (None, {}, {key: {"outcome": "FAIL"} for key in required}):
        docs["isolation"]["observations"] = observations
        with pytest.raises(bootstrap.BootstrapBlocked, match="measurements_required"):
            full_gate.check_current(target, "fixtures")
    assert target.inspect()["realm_admitted"] is False
    docs["auth"]["operation"] = "bootstrap"
    executor.execute.side_effect = RuntimeError("private credential detail")
    with pytest.raises(bootstrap.BootstrapBlocked, match="operator_action_failed") as error:
        bootstrap.execute_plan(target, gate, executor, purpose="bootstrap")
    assert "private" not in str(error.value) and executor.execute.call_count == 1
    mutated = deepcopy(target)
    dict(mutated.actions[6].parameters)["authority"]["database"] = "production"
    executor.reset_mock()
    with pytest.raises(bootstrap.BootstrapBlocked, match="plan_changed"):
        bootstrap.execute_plan(mutated, gate, executor, purpose="bootstrap")
    executor.execute.assert_not_called()
