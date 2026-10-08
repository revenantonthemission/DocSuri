"""Local negatives for the prepared Colima executor.

No root-owned file, no live docker/colima invocation, no measured guest proof and
no operator receipt is produced here: fake channels stand in for the host and the
privileged guest so the exact argv, ordering and refusal behaviour can be checked
before any concrete operator authorises a real run.
"""

from __future__ import annotations

import json
import os
import stat
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from server import u1_colima_executor as executor_module
from server import u1_db_bootstrap as bootstrap
from server.u1_colima_executor import (
    ColimaExecutor,
    CredentialChannel,
    ExecutorRefused,
    RefusingGuest,
    digest,
    main,
    rule_spec_digest,
    tree_digest,
)

SUPERUSER = "SuperuserSecret123"
AUTHORITY = "AuthoritySecret1234"
PURGE = "PurgeRoleSecret12345"
EMPTY_SNAPSHOT = {"containers": "", "networks": "", "volumes": "",
                  "rules_v4": "", "rules_v6": ""}
LABELS = {"unit": "u1-job-skeleton", "realm_id": "0123456789abcdef",
          "environment": "u1-staging"}


class FakeRunner:
    """Fixed-argv docker channel: records every command, never touches a socket."""

    def __init__(self, context: str = "colima") -> None:
        self.context = context
        self.commands: list[list[str]] = []
        self.stdin: list[bytes] = []
        self.present: dict[str, str] = {}

    def run(self, argv, *, stdin: bytes | None = None) -> str:
        argv = list(argv)
        self.commands.append(argv)
        if stdin is not None:
            self.stdin.append(stdin)
        head, second = argv[0], argv[1] if len(argv) > 1 else ""
        if head == "ps" and second == "-a":
            return "\n".join(name for name, kind in self.present.items()
                             if kind == "container")
        if head == "network" and second == "ls":
            return "\n".join(name for name, kind in self.present.items()
                             if kind == "network")
        if head == "volume" and second == "ls":
            return "\n".join(name for name, kind in self.present.items()
                             if kind == "volume")
        if second == "inspect":
            kind, name = head, argv[-1]
            if self.present.get(name) != kind:
                raise ExecutorRefused("command_failed:inspect")
            if "--format" in argv:
                return json.dumps(LABELS)
            return "{}"
        if head == "network" and second == "create":
            if "--internal" not in argv or "--subnet" not in argv:
                raise ExecutorRefused("command_failed:create")
            self.present[argv[-1]] = "network"
            return ""
        if head == "volume" and second == "create":
            self.present[argv[-1]] = "volume"
            return ""
        if head == "network" and second == "rm":
            self.present.pop(argv[-1], None)
            return ""
        if head == "volume" and second == "rm":
            self.present.pop(argv[-1], None)
            return ""
        if head == "rm" and second == "--force":
            self.present.pop(argv[-1], None)
            return ""
        if head == "run":
            if "--detach" in argv:
                self.present[argv[argv.index("--name") + 1]] = "container"
            return ""
        if head == "exec":
            return ""
        raise ExecutorRefused("command_failed:" + head)


class FakeGuest:
    """Privileged channel stand-in with mutable, comment-scoped rule state."""

    def __init__(self) -> None:
        self.commands: list[list[str]] = []
        self.v4: list[str] = []
        self.v6: list[str] = []

    def run(self, argv, *, stdin: bytes | None = None) -> str:
        argv = list(argv)
        self.commands.append(argv)
        rendered = "-A " + " ".join(argv[3:])
        if argv[0] == "iptables" and argv[1:2] == ["-S"]:
            if len(argv) == 3:
                return "-N " + argv[2]
            return "\n".join(self.v4)
        if argv[0] == "ip6tables" and argv[1:2] == ["-S"]:
            return "-N " + argv[2]
        if argv[0] == "iptables" and argv[1:2] == ["-w"]:
            self._mutate(self.v4, argv[2], rendered)
            return ""
        if argv[0] == "ip6tables" and argv[1:2] == ["-w"]:
            self._mutate(self.v6, argv[2], rendered)
            return ""
        if argv[0] in {"iptables-save", "ip6tables-save"}:
            return "\n".join(self.v4 if argv[0] == "iptables-save" else self.v6)
        raise ExecutorRefused("guest_command_failed:" + argv[0])

    @staticmethod
    def _mutate(rules: list[str], verb: str, rendered: str) -> None:
        if verb == "-A":
            rules.append(rendered)
            return
        if rendered not in rules:
            raise ExecutorRefused("guest_command_failed:delete")
        rules.remove(rendered)


@pytest.fixture(autouse=True)
def trusted_operator_files(monkeypatch) -> None:
    """Local files stand in for the operator's root-owned channel (see the owner test)."""
    monkeypatch.setattr(executor_module, "_trusted_owner", lambda info: True)


def workspace(tmp_path: Path) -> SimpleNamespace:
    """Fully derived public configuration: every digest is computed, none guessed."""
    uid = os.getuid()
    source_root = tmp_path / "source"
    source_root.mkdir(mode=0o755)
    (source_root / "probe.sh").write_text("#!/bin/sh\nexit 0\n")
    (source_root / "probe.sh").chmod(0o644)
    operator_dir = tmp_path / "operator"
    operator_dir.mkdir(mode=0o700)
    channel_path = operator_dir / "channel.json"
    channel_raw = json.dumps({
        "version": 1, "realm_id": "0123456789abcdef",
        "valid_until": (datetime.now(UTC) + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "postgres_superuser_password": SUPERUSER, "authority_password": AUTHORITY,
        "purge_password": PURGE,
    }, sort_keys=True, separators=(",", ":")).encode()
    channel_path.write_bytes(channel_raw)
    channel_path.chmod(0o444)
    secrets_dir = tmp_path / "secrets"
    secrets_dir.mkdir(mode=0o700)
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir(mode=0o700)
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text('{"realm": "synthetic"}')
    manifest_path.chmod(0o444)
    receipt_path = tmp_path / "receipt.json"
    receipt_path.write_text('{"observations": {}}')
    receipt_path.chmod(0o444)
    endpoint = {"host": "postgres-u1", "address": "172.31.200.2", "port": 5432}
    raw_config = {
        "version": 1, "unit": "u1-job-skeleton", "environment": "u1-staging",
        "realm_id": "0123456789abcdef", "context": "colima",
        "guest_id": digest(json.dumps(EMPTY_SNAPSHOT, sort_keys=True,
                                      separators=(",", ":")).encode()),
        "runtime_digest": "b" * 64, "source_digest": tree_digest(source_root),
        "launcher_digest": digest(Path(bootstrap.__file__).read_bytes()),
        "rules_digest": "d" * 64,
        "postgres_image": "docsuri/postgres@sha256:" + "1" * 64,
        "workload_image": "docsuri/u1-tests@sha256:" + "2" * 64,
        "postgres_uid": 70, "workload_uid": uid, "operator_uid": uid + 1000,
        "workload_hostname": "u1-test", "internal_network_cidr": "172.31.200.0/24",
        "authority_database": {**endpoint, "database": "docsuri_u1_authority_0123456789abcdef",
                               "role": "docsuri_u1_authority_0123456789abcdef",
                               "connection_limit": 4},
        "purge_database": {**endpoint, "database": "docsuri_u1_purge_0123456789abcdef",
                           "role": "docsuri_u1_purge_0123456789abcdef",
                           "connection_limit": 2},
        "memory_bytes": 268435456, "cpus": 1, "disk_reserve_bytes": 268435456,
        "max_connections": 20, "credential_channel_digest": digest(channel_raw),
        "valid_until": (datetime.now(UTC) + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    first = bootstrap.parse_config(json.dumps(raw_config).encode())
    raw_config["rules_digest"] = rule_spec_digest(first)
    raw = json.dumps(raw_config).encode()
    plan = bootstrap.build_plan(raw)
    return SimpleNamespace(
        raw=raw, plan=plan, config=plan.config, source_root=source_root,
        channel=CredentialChannel(channel_path, digest(channel_raw)),
        secrets_dir=secrets_dir, evidence_dir=evidence_dir,
        manifest_path=manifest_path, receipt_path=receipt_path,
        operator_dir=operator_dir,
    )


def build(ws: SimpleNamespace, *, runner: FakeRunner | None = None,
          guest: FakeGuest | None = None) -> ColimaExecutor:
    return ColimaExecutor(
        ws.config, runner=runner if runner is not None else FakeRunner(),
        channel=ws.channel, executor_sha256=ColimaExecutor.self_digest(),
        source_root=ws.source_root, manifest_path=ws.manifest_path,
        receipt_path=ws.receipt_path, evidence_dir=ws.evidence_dir,
        secrets_dir=ws.secrets_dir,
        guest=guest if guest is not None else FakeGuest(),
    )


def admission(monkeypatch, plan: bootstrap.BootstrapPlan,
              operation: str = "bootstrap") -> bootstrap.ProtectedAdmission:
    config = plan.config
    binding = {"unit": config.unit, "environment": config.environment,
               "realm_id": config.realm_id, "config_sha256": plan.config_digest,
               "context": config.context, "guest_id": config.guest_id,
               "runtime_sha256": config.runtime_digest, "source_sha256": config.source_digest,
               "launcher_sha256": config.launcher_digest, "rules_sha256": config.rules_digest,
               "credential_channel_sha256": config.credential_channel_digest}
    common = {"binding": binding, "valid_until": config.valid_until}
    fresh = [a.identity for a in plan.actions if a.operation in {
        "create_internal_network", "create_owned_volume", "start_private_postgres",
        "start_unadmitted_probe_workload"}]
    docs = {
        "auth": {**common, "operator": "revenantonthemission", "operation": operation,
                 "original_inventory_sha256": "1" * 64, "qualified_artifacts_sha256": "2" * 64},
        "qualification": {**common, "images": [config.postgres_image, config.workload_image],
                          "disposition": "QUALIFIED", "blocking_findings": [],
                          "security_report_sha256": "3" * 64},
        "inventory": {**common, "nonoverlapping_cidr": config.internal_network_cidr,
                      "fresh_resources_absent": fresh,
                      "disk_available_bytes": config.disk_reserve_bytes,
                      "memory_available_bytes": config.memory_bytes},
    }
    monkeypatch.setattr(bootstrap, "protected_document",
                        lambda reference: docs[reference.path.name])
    references = {name: bootstrap.DocumentReference(Path("/operator/" + name), value)
                  for name, value in (("auth", "0" * 64), ("inventory", "1" * 64),
                                      ("qualification", "2" * 64))}
    return bootstrap.ProtectedAdmission(references["auth"], references["qualification"],
                                        references["inventory"])


def test_prepared_executor_refuses_context_executable_and_rule_digests(tmp_path) -> None:
    ws = workspace(tmp_path)
    with pytest.raises(ExecutorRefused, match="executor_digest_mismatch"):
        ColimaExecutor(ws.config, runner=FakeRunner(), channel=ws.channel,
                       executor_sha256="f" * 64, source_root=ws.source_root,
                       manifest_path=ws.manifest_path, receipt_path=ws.receipt_path,
                       evidence_dir=ws.evidence_dir, secrets_dir=ws.secrets_dir)
    with pytest.raises(ExecutorRefused, match="context_mismatch"):
        ColimaExecutor(ws.config, runner=FakeRunner("other"), channel=ws.channel,
                       executor_sha256=ColimaExecutor.self_digest(), source_root=ws.source_root,
                       manifest_path=ws.manifest_path, receipt_path=ws.receipt_path,
                       evidence_dir=ws.evidence_dir, secrets_dir=ws.secrets_dir)
    weak = bootstrap.parse_config(
        json.dumps({**json.loads(ws.raw), "rules_digest": "d" * 64}).encode())
    with pytest.raises(ExecutorRefused, match="rules_digest_mismatch"):
        ColimaExecutor(weak, runner=FakeRunner(), channel=ws.channel,
                       executor_sha256=ColimaExecutor.self_digest(), source_root=ws.source_root,
                       manifest_path=ws.manifest_path, receipt_path=ws.receipt_path,
                       evidence_dir=ws.evidence_dir, secrets_dir=ws.secrets_dir)
    shared = tmp_path / "shared"
    shared.mkdir(mode=0o755)
    with pytest.raises(ExecutorRefused, match="secrets_dir_invalid"):
        ColimaExecutor(ws.config, runner=FakeRunner(), channel=ws.channel,
                       executor_sha256=ColimaExecutor.self_digest(), source_root=ws.source_root,
                       manifest_path=ws.manifest_path, receipt_path=ws.receipt_path,
                       evidence_dir=ws.evidence_dir, secrets_dir=shared)


def test_unknown_operation_identity_and_weakened_flags_refuse(tmp_path) -> None:
    ws = workspace(tmp_path)
    executor = build(ws)
    with pytest.raises(ExecutorRefused, match="operation_unsupported"):
        executor.execute(bootstrap.Action("format_disks", executor.cluster))
    with pytest.raises(ExecutorRefused, match="identity_mismatch"):
        executor.execute(bootstrap.Action("create_owned_volume", executor.network))
    with pytest.raises(ExecutorRefused, match="plan_flag_unsupported"):
        executor.execute(bootstrap.Action(
            "deliver_protected_credentials", executor.credentials,
            (("channel_digest", ws.config.credential_channel_digest),
             ("postgres_uid", ws.config.postgres_uid),
             ("workload_uid", ws.config.workload_uid), ("read_only_workload", False))))
    with pytest.raises(ExecutorRefused, match="identity_mismatch"):
        executor.execute(bootstrap.Action(
            "create_owned_volume", executor.volume,
            (("labels", (("unit", "u1-job-skeleton"), ("realm_id", "0" * 16),
                         ("environment", "u1-staging"))),)))
    with pytest.raises(ExecutorRefused, match="credential_channel_digest_mismatch"):
        executor.execute(bootstrap.Action(
            "deliver_protected_credentials", executor.credentials,
            (("channel_digest", "f" * 64), ("postgres_uid", ws.config.postgres_uid),
             ("workload_uid", ws.config.workload_uid), ("read_only_workload", True))))


def test_ownership_and_digest_checks_refuse_tampering(monkeypatch, tmp_path) -> None:
    ws = workspace(tmp_path)
    reference = ws.channel.path
    raw = reference.read_bytes()
    genuine = lambda info: info.st_uid == 0  # noqa: E731 - explicit real owner rule
    monkeypatch.setattr(executor_module, "_trusted_owner", genuine)
    # The real check refuses an operator-user owned channel even with a good digest.
    with pytest.raises(ExecutorRefused, match="protected_ownership_invalid"):
        executor_module._protected_bytes(reference, digest(raw))
    with pytest.raises(ExecutorRefused, match="protected_ownership_invalid"):
        executor_module._protected_file_sha(ws.manifest_path)
    assert executor_module._trusted_owner(reference.stat()) is False
    monkeypatch.setattr(executor_module, "_trusted_owner", lambda info: True)
    assert executor_module._protected_bytes(reference, digest(raw)) == raw
    with pytest.raises(ExecutorRefused, match="digest_mismatch"):
        executor_module._protected_bytes(reference, "f" * 64)
    reference.chmod(0o644)
    with pytest.raises(ExecutorRefused, match="protected_document_invalid"):
        executor_module._protected_bytes(reference, digest(raw))
    reference.chmod(0o444)
    with pytest.raises(ExecutorRefused, match="protected_reference_invalid"):
        executor_module._protected_bytes(Path("relative.json"), digest(raw))
    with pytest.raises(ExecutorRefused, match="protected_reference_invalid"):
        executor_module._protected_file_sha(Path("relative.json"))


def test_privileged_guest_is_refused_by_default(tmp_path) -> None:
    ws = workspace(tmp_path)
    executor = ColimaExecutor(
        ws.config, runner=FakeRunner(), channel=ws.channel,
        executor_sha256=ColimaExecutor.self_digest(), source_root=ws.source_root,
        manifest_path=ws.manifest_path, receipt_path=ws.receipt_path,
        evidence_dir=ws.evidence_dir, secrets_dir=ws.secrets_dir)
    assert isinstance(executor.guest, RefusingGuest)
    with pytest.raises(ExecutorRefused, match="guest_authorization_required"):
        executor.execute(bootstrap.Action("apply_owned_guest_rules", ws.config.rules_digest,
                                          (("network", executor.network),)))
    with pytest.raises(ExecutorRefused, match="guest_authorization_required"):
        executor.execute(bootstrap.Action("remove_owned_guest_rules", ws.config.rules_digest,
                                          (("network", executor.network),)))
    # Inventory verification with a refusing guest compares against the protected
    # measurement and only passes when that measurement matches what is readable.
    executor.execute(bootstrap.Action("verify_original_inventory", ws.config.guest_id))
    assert executor._inventory_snapshot() == ws.config.guest_id  # noqa: SLF001


def test_rule_application_is_comment_scoped_and_removal_requires_presence(tmp_path) -> None:
    ws = workspace(tmp_path)
    guest = FakeGuest()
    executor = build(ws, guest=guest)
    action = bootstrap.Action("apply_owned_guest_rules", ws.config.rules_digest,
                              (("network", executor.network),
                               ("deny_ipv4_external_host_lan_production", True),
                               ("deny_unsupported_ipv6", True),
                               ("preserve_original_rules", True)))
    executor.execute(action)
    assert len(guest.v4) == 7 and len(guest.v6) == 1
    assert all("docsuri-u1-0123456789abcdef" in rule for rule in guest.v4)
    assert guest.v4[0].startswith("-A DOCKER-USER -s 172.31.200.0/24 -d 172.31.200.0/24")
    assert guest.v4[-1].endswith("-j DROP") and "0.0.0.0/0" in guest.v4[-1]
    with pytest.raises(ExecutorRefused, match="owned_rules_already_present"):
        executor.execute(action)
    removal = bootstrap.Action("remove_owned_guest_rules", ws.config.rules_digest,
                               (("network", executor.network),))
    executor.execute(removal)
    assert guest.v4 == [] and guest.v6 == []
    with pytest.raises(ExecutorRefused, match="owned_rules_missing"):
        executor.execute(removal)


def test_identity_scoped_deletion_requires_owned_labels(tmp_path) -> None:
    ws = workspace(tmp_path)
    runner = FakeRunner()
    executor = build(ws, runner=runner)
    executor.execute(bootstrap.Action("create_internal_network", executor.network,
                                      (("cidr", ws.config.internal_network_cidr),
                                       ("internal", True), ("ipv6", False),
                                       ("context", ws.config.context),
                                       ("labels", tuple(LABELS.items())))))
    assert executor.network in runner.present
    runner.commands.clear()
    # Relabelling the network by hand (simulated) invalidates identity-scoped removal.
    original = runner.run

    def relabel(argv, *, stdin=None):
        if argv[:2] == ["network", "inspect"] and "--format" in argv:
            return json.dumps({**LABELS, "unit": "someone-else"})
        return original(argv, stdin=stdin)

    runner.run = relabel  # type: ignore[method-assign]
    with pytest.raises(ExecutorRefused, match="owned_resource_label_mismatch"):
        executor.execute(bootstrap.Action("remove_identity_verified_network", executor.network,
                                          (("labels", tuple(LABELS.items())),)))


def test_credential_lifecycle_withdraws_revokes_and_removes(tmp_path) -> None:
    ws = workspace(tmp_path)
    executor = build(ws)
    deliver = bootstrap.Action("deliver_protected_credentials", executor.credentials,
                               (("channel_digest", ws.config.credential_channel_digest),
                                ("postgres_uid", ws.config.postgres_uid),
                                ("workload_uid", ws.config.workload_uid),
                                ("read_only_workload", True)))
    executor.execute(deliver)
    superuser_file = ws.secrets_dir / "u1_superuser_password"
    assert superuser_file.read_text() == SUPERUSER
    assert stat.S_IMODE(superuser_file.stat().st_mode) == 0o600
    executor.execute(bootstrap.Action("withdraw_provisioner_credentials", executor.credentials))
    assert not superuser_file.exists()
    with pytest.raises(ExecutorRefused, match="provisioner_credential_missing"):
        executor.execute(bootstrap.Action("withdraw_provisioner_credentials",
                                          executor.credentials))
    executor.execute(bootstrap.Action("revoke_run_credentials", executor.credentials))
    assert not ws.channel.path.exists()
    assert not any(ws.secrets_dir.iterdir())
    with pytest.raises(ExecutorRefused, match="run_credentials_absent"):
        executor.execute(bootstrap.Action("revoke_run_credentials", executor.credentials))
    executor.execute(bootstrap.Action("remove_identity_verified_credentials",
                                      executor.credentials))
    assert not ws.secrets_dir.exists()
    # Delivery without a live channel refuses instead of writing to a missing directory.
    with pytest.raises(ExecutorRefused, match="protected_document_unavailable"):
        executor.execute(bootstrap.Action("deliver_protected_credentials", executor.credentials,
                                          (("channel_digest", ws.config.credential_channel_digest),
                                           ("postgres_uid", ws.config.postgres_uid),
                                           ("workload_uid", ws.config.workload_uid),
                                           ("read_only_workload", True))))


def test_credential_channel_scope_and_validity_are_checked(tmp_path) -> None:
    ws = workspace(tmp_path)
    # A foreign file never reaches parsing: the plan's registered digest comes first.
    foreign = json.loads(ws.channel.path.read_text())
    foreign["realm_id"] = "fedcba9876543210"
    foreign_path = ws.operator_dir / "wrong.json"
    foreign_path.write_text(json.dumps(foreign, sort_keys=True, separators=(",", ":")))
    foreign_path.chmod(0o444)
    pinned = build(ws)
    pinned.channel = CredentialChannel(foreign_path, digest(foreign_path.read_bytes()))
    with pytest.raises(ExecutorRefused, match="credential_channel_digest_mismatch"):
        pinned._channel()  # noqa: SLF001 - direct unit check of the refusal

    def rewrite(path: Path, document: dict) -> None:
        if path.exists():
            path.chmod(0o644)
        path.write_text(json.dumps(document, sort_keys=True, separators=(",", ":")))
        path.chmod(0o444)

    def registered(update: dict) -> ColimaExecutor:
        """A channel registered under the plan digest, carrying the given change."""
        document = {**json.loads(ws.channel.path.read_text()), **update}
        path = ws.operator_dir / "check.json"
        rewrite(path, document)
        channel = CredentialChannel(path, digest(path.read_bytes()))
        executor = build(ws)
        executor.channel = channel
        executor.config = ws.config.model_copy(
            update={"credential_channel_digest": channel.sha256})
        return executor

    with pytest.raises(ExecutorRefused, match="scope_mismatch"):
        registered({"realm_id": "fedcba9876543210"})._channel()  # noqa: SLF001
    with pytest.raises(ExecutorRefused, match="scope_mismatch"):
        registered({"valid_until": "2020-01-01T00:00:00Z"})._channel()  # noqa: SLF001
    incomplete = registered({})
    path = incomplete.channel.path
    document = json.loads(path.read_text())
    del document["purge_password"]
    rewrite(path, document)
    incomplete.channel = CredentialChannel(path, digest(path.read_bytes()))
    incomplete.config = ws.config.model_copy(
        update={"credential_channel_digest": incomplete.channel.sha256})
    with pytest.raises(ExecutorRefused, match="credential_channel_incomplete"):
        incomplete._channel()  # noqa: SLF001


def test_full_bootstrap_and_owned_reversal_sequence(monkeypatch, tmp_path) -> None:
    ws = workspace(tmp_path)
    runner = FakeRunner()
    guest = FakeGuest()
    executor = build(ws, runner=runner, guest=guest)
    gate = admission(monkeypatch, ws.plan)
    completed = bootstrap.execute_plan(ws.plan, gate, executor, purpose="bootstrap")
    assert completed == tuple(action.identity for action in ws.plan.actions)
    flat = json.dumps(runner.commands)
    for secret in (SUPERUSER, AUTHORITY, PURGE):
        assert secret not in flat
    assert f"DOCSURI_U1_AUTHORITY_DSN={AUTHORITY}" not in flat
    assert "--env-file" in flat and "publish" not in flat
    assert "--cap-drop" in flat and "no-new-privileges" in flat
    assert any("--user" in command and str(ws.config.postgres_uid) in command
               for command in runner.commands)
    # The provisioner password reaches psql on stdin only, never in argv.
    assert AUTHORITY.encode() in b"".join(runner.stdin)
    assert not (ws.secrets_dir / "u1_superuser_password").exists()
    assert (ws.secrets_dir / "u1_authority_password").exists()
    assert (ws.secrets_dir / "u1_authority_dsn.env").exists()
    assert len(guest.v4) == 7
    runner.commands.clear()
    gate = admission(monkeypatch, ws.plan, "rollback")
    undone = bootstrap.execute_plan(ws.plan, gate, executor, purpose="rollback")
    assert undone == tuple(action.identity for action in ws.plan.reversal)
    assert runner.present == {} and guest.v4 == [] and guest.v6 == []
    assert not ws.secrets_dir.exists() and not ws.channel.path.exists()
    flat = json.dumps(runner.commands)
    assert all(secret not in flat for secret in (SUPERUSER, AUTHORITY, PURGE))


def test_postgres_and_workload_commands_pin_identity_and_limits(tmp_path) -> None:
    ws = workspace(tmp_path)
    runner = FakeRunner()
    executor = build(ws, runner=runner)
    executor.execute(bootstrap.Action("create_internal_network", executor.network,
                                      (("cidr", ws.config.internal_network_cidr),
                                       ("internal", True), ("ipv6", False),
                                       ("context", ws.config.context),
                                       ("labels", tuple(LABELS.items())))))
    executor.execute(bootstrap.Action("create_owned_volume", executor.volume,
                                      (("labels", tuple(LABELS.items())),)))
    executor.execute(bootstrap.Action("deliver_protected_credentials", executor.credentials,
                                      (("channel_digest", ws.config.credential_channel_digest),
                                       ("postgres_uid", ws.config.postgres_uid),
                                       ("workload_uid", ws.config.workload_uid),
                                       ("read_only_workload", True))))
    executor.execute(bootstrap.Action("start_private_postgres", executor.cluster,
                                      (("image", ws.config.postgres_image),
                                       ("network", executor.network), ("volume", executor.volume),
                                       ("address", ws.config.authority_database.address),
                                       ("published_ports", ()),
                                       ("user", ws.config.postgres_uid), ("read_only_root", True),
                                       ("capabilities", ()),
                                       ("memory_bytes", ws.config.memory_bytes),
                                       ("cpus", ws.config.cpus),
                                       ("max_connections", ws.config.max_connections),
                                       ("labels", tuple(LABELS.items())))))
    start = next(command for command in runner.commands
                 if command[0] == "run" and "--detach" in command)
    assert "--ip" in start and ws.config.authority_database.address in start
    assert "--read-only" in start and "--pids-limit" in start
    assert "--restart" in " ".join(start) and "no-new-privileges" in start
    assert not any(flag in start for flag in ("--privileged", "--network host"))
    with pytest.raises(ExecutorRefused, match="owned_resource_already_present"):
        executor.execute(bootstrap.Action("start_private_postgres", executor.cluster,
                                          (("image", ws.config.postgres_image),
                                           ("network", executor.network),
                                           ("volume", executor.volume),
                                           ("address", ws.config.authority_database.address),
                                           ("user", ws.config.postgres_uid),
                                           ("memory_bytes", ws.config.memory_bytes),
                                           ("cpus", ws.config.cpus),
                                           ("max_connections", ws.config.max_connections),
                                           ("labels", tuple(LABELS.items())))))
    with pytest.raises(ExecutorRefused, match="image_identity_mismatch"):
        executor.execute(bootstrap.Action("start_private_postgres", executor.cluster,
                                          (("image", "postgres:16"),
                                           ("network", executor.network),
                                           ("volume", executor.volume),
                                           ("address", ws.config.authority_database.address),
                                           ("user", ws.config.postgres_uid),
                                           ("memory_bytes", ws.config.memory_bytes),
                                           ("cpus", ws.config.cpus),
                                           ("max_connections", ws.config.max_connections),
                                           ("labels", tuple(LABELS.items())))))


def test_source_digest_and_protected_bindings_gate_the_workload(tmp_path) -> None:
    ws = workspace(tmp_path)
    runner = FakeRunner()
    executor = build(ws, runner=runner)
    base = (("image", ws.config.workload_image), ("hostname", ws.config.workload_hostname),
            ("network", executor.network), ("user", ws.config.workload_uid),
            ("source_read_only", True), ("source_digest", ws.config.source_digest),
            ("output_separate", True), ("external_networks", ()),
            ("host_home_socket_mounts", ()), ("capabilities", ()), ("published_ports", ()),
            ("labels", tuple(LABELS.items())))
    wrong = tuple(("source_digest", "c" * 64) if key == "source_digest"
                  else (key, item) for key, item in base)
    with pytest.raises(ExecutorRefused, match="source_identity_mismatch"):
        executor.execute(bootstrap.Action("start_unadmitted_probe_workload",
                                          executor.workload, wrong))
    (ws.source_root / "probe.sh").write_text("#!/bin/sh\nexit 1\n")
    with pytest.raises(ExecutorRefused, match="source_identity_mismatch"):
        executor.execute(bootstrap.Action("start_unadmitted_probe_workload",
                                          executor.workload, base))
    (ws.source_root / "probe.sh").write_text("#!/bin/sh\nexit 0\n")
    (ws.source_root / "probe.sh").chmod(0o644)
    executor.execute(bootstrap.Action("start_unadmitted_probe_workload", executor.workload,
                                      base))
    start = runner.commands[-1]
    assert "--env-file" in start and "--read-only" in start
    assert str(ws.manifest_path) in " ".join(start)
    assert ws.config.workload_image in start
    assert (ws.secrets_dir / "u1_authority_dsn.env").is_file()


def test_cli_digest_helpers_never_apply_anything(tmp_path, capsys) -> None:
    ws = workspace(tmp_path)
    assert main(["self-digest"]) == 0
    assert json.loads(capsys.readouterr().out)["executor_sha256"] == \
        ColimaExecutor.self_digest()
    assert main(["tree-digest", str(ws.source_root)]) == 0
    first = json.loads(capsys.readouterr().out)
    assert first["applied"] is False and first["tree_sha256"] == ws.config.source_digest
    (ws.source_root / "probe.sh").write_text("#!/bin/sh\nexit 0\n")
    (ws.source_root / "probe.sh").chmod(0o644)
    assert main(["tree-digest", str(ws.source_root)]) == 0
    assert json.loads(capsys.readouterr().out)["tree_sha256"] == ws.config.source_digest
    link = ws.source_root / "escape"
    link.symlink_to("/etc/passwd")
    assert main(["tree-digest", str(ws.source_root)]) == 1
    assert json.loads(capsys.readouterr().out)["error"] == "source_root_invalid"
    link.unlink()
    config_path = tmp_path / "public.json"
    config_path.write_bytes(ws.raw)
    assert main(["rule-spec", "--config", str(config_path),
                 "--sha256", digest(ws.raw)]) == 0
    assert json.loads(capsys.readouterr().out)["rules_sha256"] == ws.config.rules_digest
    assert main(["rule-spec", "--config", str(config_path), "--sha256", "f" * 64]) == 1
    assert json.loads(capsys.readouterr().out)["error"] == "configuration_digest_mismatch"
