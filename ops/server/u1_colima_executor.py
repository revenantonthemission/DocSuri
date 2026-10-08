"""Concrete, prepared-not-applied Colima/Docker executor for the U1 database-only realm.

This module supplies the ``OperatorExecutor`` implementation that
``u1_db_bootstrap.execute_plan`` requires.  Every typed action of the approved
bootstrap/reversal plan is implemented here so the accountable operator can
review the exact commands before any of them run, and each action fails closed
when an identity, ownership, resource or measurement check does not match the
approved configuration.

Nothing runs on import and there is no application verb: the only ways in are
the inspect CLI of ``u1_db_bootstrap`` and ``execute_plan``, which rechecks the
protected admission documents before *every* action.  Image build/pull,
provisioning, guest-rule application and credential delivery still require the
separate concrete operator authorisation described in
``postgres-remediation-and-launcher-handoff.md``.

The digest helpers (``tree-digest``, ``rule-spec``, ``self-digest``) exist so a
public bootstrap configuration can be filled with reproducible values instead of
guessed ones.  They read and hash; they never start, pull, create or delete.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from urllib.parse import quote

try:  # package import (``python -m pytest`` from ``ops/``) first, script mode second
    from server import u1_db_bootstrap as bootstrap
except ImportError:  # pragma: no cover - exercised only by direct script execution
    import u1_db_bootstrap as bootstrap  # type: ignore[no-redef]

PASSWORD_PATTERN = re.compile(r"^[A-Za-z0-9._~+=/-]{16,128}$")
HEX64 = re.compile(r"^[a-f0-9]{64}$")
REALM = re.compile(r"^[a-f0-9]{16}$")


class ExecutorRefused(RuntimeError):
    """Safe category only; never carries configuration, secret or command output."""


class Runner(Protocol):
    """Host-side command channel.  argv is a list; no shell ever interprets it."""

    context: str

    def run(self, argv: Sequence[str], *, stdin: bytes | None = None) -> str:
        """Return stdout, or raise ``ExecutorRefused`` on a non-zero exit."""


class Guest(Protocol):
    """Privileged guest-side channel (separately qualified; refused when absent)."""

    def run(self, argv: Sequence[str], *, stdin: bytes | None = None) -> str:
        """Return stdout, or raise ``ExecutorRefused`` on a non-zero exit."""


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _check_argv(argv: Sequence[str]) -> None:
    if not argv or any(not isinstance(part, str) or "\n" in part for part in argv):
        raise ExecutorRefused("command_shape_invalid")


class CommandRunner:
    """Fixed-argv subprocess runner bound to one docker context."""

    def __init__(self, context: str, executable: str = "docker") -> None:
        self.context = context
        self.executable = executable

    def run(self, argv: Sequence[str], *, stdin: bytes | None = None) -> str:
        _check_argv(argv)
        complete = [self.executable, "--context", self.context, *argv]
        try:
            result = subprocess.run(  # noqa: S603 - fixed argv, no shell
                complete, input=stdin, capture_output=True, check=False, timeout=300
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise ExecutorRefused("command_unavailable") from exc
        if result.returncode != 0:
            raise ExecutorRefused("command_failed:" + str(argv[0]))
        return result.stdout.decode("utf-8", "replace")


class ColimaGuest:
    """Privileged guest channel: ``colima ssh -- sudo -n <argv>``."""

    def __init__(self, executable: str = "colima") -> None:
        self.executable = executable

    def run(self, argv: Sequence[str], *, stdin: bytes | None = None) -> str:
        _check_argv(argv)
        complete = [self.executable, "ssh", "--", "sudo", "-n", *argv]
        try:
            result = subprocess.run(  # noqa: S603 - fixed argv, no shell
                complete, input=stdin, capture_output=True, check=False, timeout=300
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise ExecutorRefused("guest_unavailable") from exc
        if result.returncode != 0:
            raise ExecutorRefused("guest_command_failed:" + str(argv[0]))
        return result.stdout.decode("utf-8", "replace")


class RefusingGuest:
    """Default guest: prepared review only, every privileged call refused."""

    def run(self, argv: Sequence[str], *, stdin: bytes | None = None) -> str:
        raise ExecutorRefused("guest_authorization_required")


@dataclass(frozen=True)
class CredentialChannel:
    """Operator-owned run-scoped secret channel; values never appear in output."""

    path: Path
    sha256: str

    def __repr__(self) -> str:  # keep secrets and path out of logs and tracebacks
        return f"CredentialChannel(sha256={self.sha256!r}, path=<protected>)"

    def document(self) -> dict:
        raw = _protected_bytes(self.path, self.sha256)
        try:
            document = bootstrap._decode(raw)  # noqa: SLF001 - shared decoder contract
        except (ValueError, TypeError, bootstrap.BootstrapBlocked) as exc:
            raise ExecutorRefused("credential_channel_invalid") from exc
        if document.get("version") != 1:
            raise ExecutorRefused("credential_channel_invalid")
        required = {
            "version", "realm_id", "valid_until", "postgres_superuser_password",
            "authority_password", "purge_password",
        }
        if not required <= document.keys():
            raise ExecutorRefused("credential_channel_incomplete")
        for key in ("postgres_superuser_password", "authority_password", "purge_password"):
            value = document[key]
            if not isinstance(value, str) or PASSWORD_PATTERN.fullmatch(value) is None:
                raise ExecutorRefused("credential_channel_invalid")
        if not isinstance(document["realm_id"], str) or REALM.fullmatch(
            document["realm_id"]
        ) is None:
            raise ExecutorRefused("credential_channel_invalid")
        return document


def _trusted_owner(info: os.stat_result) -> bool:
    """Protected documents are operator-root owned; nothing else counts as trusted."""
    return info.st_uid == 0


def _protected_bytes(path: Path, expected: str) -> bytes:
    """Root-owned, immutable, size-bounded, digest-checked file.  Mirrors the plan."""
    if not path.is_absolute() or HEX64.fullmatch(expected) is None:
        raise ExecutorRefused("protected_reference_invalid")
    try:
        for part in (path, *path.parents):
            info = part.lstat()
            if stat.S_ISLNK(info.st_mode) or not _trusted_owner(info) or info.st_mode & 0o022:
                raise ExecutorRefused("protected_ownership_invalid")
        info = path.stat()
        if not stat.S_ISREG(info.st_mode) or info.st_size > 65536 or info.st_mode & 0o222:
            raise ExecutorRefused("protected_document_invalid")
        raw = path.read_bytes()
    except OSError as exc:
        raise ExecutorRefused("protected_document_unavailable") from exc
    if digest(raw) != expected:
        raise ExecutorRefused("protected_document_digest_mismatch")
    return raw


def _protected_file_sha(path: Path) -> str:
    """Hash a protected file after the ownership checks, without a stored hash."""
    if not path.is_absolute():
        raise ExecutorRefused("protected_reference_invalid")
    try:
        for part in (path, *path.parents):
            info = part.lstat()
            if stat.S_ISLNK(info.st_mode) or not _trusted_owner(info) or info.st_mode & 0o022:
                raise ExecutorRefused("protected_ownership_invalid")
        info = path.stat()
        if not stat.S_ISREG(info.st_mode) or info.st_size > 65536 or info.st_mode & 0o222:
            raise ExecutorRefused("protected_document_invalid")
        raw = path.read_bytes()
    except OSError as exc:
        raise ExecutorRefused("protected_document_unavailable") from exc
    return digest(raw)


@dataclass(frozen=True)
class RuntimeBindings:
    """Protected manifest/receipt paths, their trusted hashes and the workload DSN."""

    manifest_path: Path
    manifest_sha256: str
    receipt_path: Path
    receipt_sha256: str
    evidence_dir: Path
    authority_dsn: str

    @classmethod
    def from_channel(
        cls,
        channel: CredentialChannel,
        config: bootstrap.BootstrapConfig,
        *,
        manifest_path: Path,
        receipt_path: Path,
        evidence_dir: Path,
    ) -> RuntimeBindings:
        document = channel.document()
        if document.get("realm_id") != config.realm_id:
            raise ExecutorRefused("credential_channel_scope_mismatch")
        if document.get("valid_until") != config.valid_until:
            raise ExecutorRefused("credential_channel_scope_mismatch")
        authority = config.authority_database
        password = quote(document["authority_password"], safe="")
        return cls(
            manifest_path=manifest_path,
            manifest_sha256=_protected_file_sha(manifest_path),
            receipt_path=receipt_path,
            receipt_sha256=_protected_file_sha(receipt_path),
            evidence_dir=evidence_dir,
            authority_dsn=(
                f"postgresql://{authority.role}:{password}@{authority.host}:"
                f"{authority.port}/{authority.database}"
            ),
        )


def tree_digest(root: Path) -> str:
    """Reproducible digest of a read-only source copy: relative path, mode, bytes.

    Entries are visited in sorted relative-path order so two copies of the same
    tree agree.  Symlinks and non-regular files are refused: the admitted source
    copy must be a plain directory tree that is not group/other writable.
    """
    if not root.is_dir() or root.is_symlink():
        raise ExecutorRefused("source_root_invalid")
    try:
        info = root.stat()
    except OSError as exc:
        raise ExecutorRefused("source_root_invalid") from exc
    if info.st_mode & 0o022:
        raise ExecutorRefused("source_root_invalid")
    hasher = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix().encode()
        entry = path.lstat()
        if stat.S_ISLNK(entry.st_mode) or not (
            stat.S_ISREG(entry.st_mode) or stat.S_ISDIR(entry.st_mode)
        ):
            raise ExecutorRefused("source_root_invalid")
        mode = stat.S_IMODE(entry.st_mode)
        hasher.update(b"D" + relative + f":{mode:o}\n".encode())
        if stat.S_ISREG(entry.st_mode):
            hasher.update(b"F" + relative + f":{mode:o}:".encode())
            hasher.update(path.read_bytes())
            hasher.update(b"\n")
    return hasher.hexdigest()


def rule_spec(config: bootstrap.BootstrapConfig) -> dict:
    """Canonical owned rule specification bound by ``config.rules_digest``.

    The hook chain is measured read-only at P2/P4; the executor refuses to apply
    when that chain is absent.  Every rule is scoped by the fresh, non-overlapping
    realm CIDR and tagged with the realm comment, so no pre-existing rule can
    match it and only these exact arguments can be removed again.
    """
    cidr = config.internal_network_cidr
    tag = "docsuri-u1-" + config.realm_id
    return {
        "version": 1,
        "realm_id": config.realm_id,
        "hook_chain": "DOCKER-USER",
        "comment": tag,
        "source_cidr": cidr,
        "allow": [{"target": "RETURN", "destination": cidr}],
        "deny": [
            {"target": "DROP", "destination": "127.0.0.0/8"},
            {"target": "DROP", "destination": "169.254.0.0/16"},
            {"target": "DROP", "destination": "10.0.0.0/8"},
            {"target": "DROP", "destination": "172.16.0.0/12"},
            {"target": "DROP", "destination": "192.168.0.0/16"},
            {"target": "DROP", "destination": "0.0.0.0/0"},
        ],
        "deny_unsupported_ipv6": True,
        "preserve_original_rules": True,
    }


def rule_spec_digest(config: bootstrap.BootstrapConfig) -> str:
    encoded = json.dumps(rule_spec(config), sort_keys=True, separators=(",", ":")).encode()
    return digest(encoded)


def rule_argv(spec: dict, entry: dict, verb: str) -> list[str]:
    """Exact iptables arguments for one owned rule; identical for add and delete."""
    return [
        verb, spec["hook_chain"], "-s", spec["source_cidr"], "-d", entry["destination"],
        "-m", "comment", "--comment", spec["comment"], "-j", entry["target"],
    ]


def _normalize_iptables(text: str) -> str:
    """Drop per-rule counters so two read-only snapshots of equal rules compare equal."""
    lines = []
    for line in text.splitlines():
        parts = line.split()
        if parts and parts[0] == "-A" and "-c" in parts:
            index = parts.index("-c")
            del parts[index : index + 2]
        lines.append(" ".join(parts))
    return "\n".join(lines)


class ColimaExecutor:
    """Identity-scoped executor for the approved U1 bootstrap/reversal actions."""

    def __init__(
        self,
        config: bootstrap.BootstrapConfig,
        *,
        runner: Runner,
        channel: CredentialChannel,
        executor_sha256: str,
        source_root: Path,
        manifest_path: Path,
        receipt_path: Path,
        evidence_dir: Path,
        secrets_dir: Path,
        guest: Guest | None = None,
    ) -> None:
        if runner.context != config.context:
            raise ExecutorRefused("context_mismatch")
        if executor_sha256 != self.self_digest():
            raise ExecutorRefused("executor_digest_mismatch")
        if rule_spec_digest(config) != config.rules_digest:
            raise ExecutorRefused("rules_digest_mismatch")
        _private_dir(secrets_dir)
        if not _owned_evidence_dir(evidence_dir, config.workload_uid):
            raise ExecutorRefused("evidence_dir_invalid")
        self.config = config
        self.runner = runner
        self.guest = guest if guest is not None else RefusingGuest()
        self.channel = channel
        self.executor_sha256 = executor_sha256
        self.source_root = source_root
        self.manifest_path = manifest_path
        self.receipt_path = receipt_path
        self.evidence_dir = evidence_dir
        self.secrets_dir = secrets_dir
        self._credentials: dict | None = None
        prefix = "docsuri-u1-" + config.realm_id
        self.network = prefix + "-net"
        self.volume = prefix + "-data"
        self.cluster = prefix + "-pg"
        self.workload = prefix + "-test"
        self.credentials = prefix + "-credentials"
        self.secret_files = {
            "superuser": secrets_dir / "u1_superuser_password",
            "authority": secrets_dir / "u1_authority_password",
            "purge": secrets_dir / "u1_purge_password",
            # The workload DSN is a channel secret: it reaches the container as an
            # env-file line, never as a value on the host command line.
            "dsn": secrets_dir / "u1_authority_dsn.env",
        }

    @staticmethod
    def self_digest() -> str:
        return digest(Path(__file__).read_bytes())

    def labels(self) -> tuple[str, ...]:
        config = self.config
        return (
            "unit=" + config.unit,
            "realm_id=" + config.realm_id,
            "environment=" + config.environment,
        )

    def execute(self, action: bootstrap.Action) -> None:
        """Dispatch one approved action.  Unknown or mis-identity actions refuse."""
        handlers: dict[str, Callable[[bootstrap.Action], None]] = {
            "verify_original_inventory": self._verify_inventory,
            "create_internal_network": self._create_network,
            "apply_owned_guest_rules": self._apply_rules,
            "create_owned_volume": self._create_volume,
            "deliver_protected_credentials": self._deliver_credentials,
            "start_private_postgres": self._start_postgres,
            "provision_separated_roles_databases_markers": self._provision,
            "withdraw_provisioner_credentials": self._withdraw_credentials,
            "start_unadmitted_probe_workload": self._start_workload,
            "stop_identity_verified_workload": self._stop_container,
            "revoke_run_credentials": self._revoke_credentials,
            "stop_identity_verified_cluster": self._stop_container,
            "remove_identity_verified_volume": self._remove_volume,
            "remove_identity_verified_credentials": self._remove_credentials,
            "remove_owned_guest_rules": self._remove_rules,
            "remove_identity_verified_network": self._remove_network,
            "reconcile_original_inventory": self._reconcile_inventory,
        }
        handler = handlers.get(action.operation)
        if handler is None:
            raise ExecutorRefused("operation_unsupported")
        if action.identity != self._expected_identity(action.operation):
            raise ExecutorRefused("identity_mismatch")
        self._parameters(action)  # boundary flags checked before any command runs
        handler(action)

    def _expected_identity(self, operation: str) -> str:
        mapping = {
            "verify_original_inventory": self.config.guest_id,
            "reconcile_original_inventory": self.config.guest_id,
            "create_internal_network": self.network,
            "remove_identity_verified_network": self.network,
            "apply_owned_guest_rules": self.config.rules_digest,
            "remove_owned_guest_rules": self.config.rules_digest,
            "create_owned_volume": self.volume,
            "remove_identity_verified_volume": self.volume,
            "deliver_protected_credentials": self.credentials,
            "withdraw_provisioner_credentials": self.credentials,
            "revoke_run_credentials": self.credentials,
            "remove_identity_verified_credentials": self.credentials,
            "start_private_postgres": self.cluster,
            "provision_separated_roles_databases_markers": self.cluster,
            "stop_identity_verified_cluster": self.cluster,
            "start_unadmitted_probe_workload": self.workload,
            "stop_identity_verified_workload": self.workload,
        }
        return mapping[operation]

    def _parameters(self, action: bootstrap.Action) -> dict:
        """Reject any plan flag that would weaken the reviewed boundary."""
        parameters = dict(action.parameters)
        for flag in ("internal", "preserve_original_rules", "read_only_workload",
                     "read_only_root", "source_read_only", "output_separate",
                     "deny_ipv4_external_host_lan_production", "deny_unsupported_ipv6"):
            if parameters.get(flag) is False:
                raise ExecutorRefused("plan_flag_unsupported")
        if "ipv6" in parameters and parameters["ipv6"] is not False:
            raise ExecutorRefused("plan_flag_unsupported")  # the owned network stays v4-only
        for flag in ("published_ports", "capabilities", "external_networks",
                     "host_home_socket_mounts"):
            if parameters.get(flag) not in (None, ()):
                raise ExecutorRefused("plan_flag_unsupported")
        if "labels" in parameters and dict(parameters["labels"]) != self._label_map():
            raise ExecutorRefused("identity_mismatch")
        return parameters

    def _label_map(self) -> dict[str, str]:
        config = self.config
        return {"unit": config.unit, "realm_id": config.realm_id,
                "environment": config.environment}

    # -- inventory ---------------------------------------------------------

    def _inventory_snapshot(self) -> str:
        payload = {
            "containers": self.runner.run(
                ["ps", "-a", "--format", "{{.ID}}|{{.Names}}|{{.Image}}|{{.Labels}}"]
            ),
            "networks": self.runner.run(
                ["network", "ls", "--format", "{{.ID}}|{{.Name}}|{{.Labels}}"]
            ),
            "volumes": self.runner.run(["volume", "ls", "--format", "{{.Name}}|{{.Labels}}"]),
            "rules_v4": _normalize_iptables(self._guest_read("iptables-save")),
            "rules_v6": _normalize_iptables(self._guest_read("ip6tables-save")),
        }
        return digest(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode())

    def _guest_read(self, command: str) -> str:
        if isinstance(self.guest, RefusingGuest):
            return ""  # review-only construction: no guest measurement claimed
        try:
            return self.guest.run([command])
        except ExecutorRefused:
            return ""

    def _verify_inventory(self, action: bootstrap.Action) -> None:
        if self._inventory_snapshot() != self.config.guest_id:
            raise ExecutorRefused("original_inventory_mismatch")

    def _reconcile_inventory(self, action: bootstrap.Action) -> None:
        for identity in (self.network, self.volume, self.cluster, self.workload):
            if self._resource_exists(identity):
                raise ExecutorRefused("owned_resource_still_present")
        if self._inventory_snapshot() != self.config.guest_id:
            raise ExecutorRefused("original_inventory_not_restored")

    def _resource_exists(self, identity: str) -> bool:
        for probe in (
            ["container", "inspect", identity],
            ["network", "inspect", identity],
            ["volume", "inspect", identity],
        ):
            try:
                self.runner.run(probe)
            except ExecutorRefused:
                continue
            return True
        return False

    def _labels_of(self, kind: str, identity: str) -> dict:
        try:
            if kind == "volume":
                raw = self.runner.run(
                    ["volume", "inspect", "--format", "{{json .Labels}}", identity]
                )
            else:
                raw = self.runner.run([kind, "inspect", "--format", "{{json .Config.Labels}}",
                                       identity])
        except ExecutorRefused as exc:
            raise ExecutorRefused("owned_resource_missing") from exc
        try:
            labels = json.loads(raw.strip() or "null")
        except ValueError as exc:
            raise ExecutorRefused("owned_resource_unreadable") from exc
        return labels if isinstance(labels, dict) else {}

    def _require_labels(self, kind: str, identity: str) -> None:
        labels = self._labels_of(kind, identity)
        if any(labels.get(key) != value for key, value in self._label_map().items()):
            raise ExecutorRefused("owned_resource_label_mismatch")

    # -- resources ---------------------------------------------------------

    def _create_network(self, action: bootstrap.Action) -> None:
        parameters = dict(action.parameters)
        if parameters.get("context") != self.config.context:
            raise ExecutorRefused("context_mismatch")
        if parameters.get("internal") is not True or parameters.get("ipv6") is not False:
            raise ExecutorRefused("plan_flag_unsupported")
        if parameters.get("cidr") != self.config.internal_network_cidr:
            raise ExecutorRefused("endpoint_identity_mismatch")
        if self._resource_exists(self.network):
            raise ExecutorRefused("owned_resource_already_present")
        self.runner.run([
            "network", "create", "--driver", "bridge", "--internal",
            "--subnet", self.config.internal_network_cidr, "--ipv6=false",
            "--label", *self.labels(), self.network,
        ])

    def _remove_network(self, action: bootstrap.Action) -> None:
        self._require_labels("network", self.network)
        self.runner.run(["network", "rm", self.network])

    def _create_volume(self, action: bootstrap.Action) -> None:
        if self._resource_exists(self.volume):
            raise ExecutorRefused("owned_resource_already_present")
        self.runner.run([
            "volume", "create", "--driver", "local", "--label", *self.labels(), self.volume,
        ])

    def _remove_volume(self, action: bootstrap.Action) -> None:
        self._require_labels("volume", self.volume)
        self.runner.run(["volume", "rm", self.volume])

    # -- guest rules -------------------------------------------------------

    def _apply_rules(self, action: bootstrap.Action) -> None:
        parameters = dict(action.parameters)
        if parameters.get("network") != self.network:
            raise ExecutorRefused("identity_mismatch")
        if parameters.get("rules_digest") not in (None, self.config.rules_digest):
            raise ExecutorRefused("identity_mismatch")
        spec = rule_spec(self.config)
        try:
            self.guest.run(["iptables", "-S", spec["hook_chain"]])
        except ExecutorRefused as exc:
            raise ExecutorRefused(_hook_category(exc)) from exc
        if spec["comment"] in self.guest.run(["iptables", "-S"]):
            raise ExecutorRefused("owned_rules_already_present")
        for entry in spec["allow"] + spec["deny"]:
            self.guest.run(["iptables", "-w", *rule_argv(spec, entry, "-A")])
        if not self.guest.run(["ip6tables", "-S", spec["hook_chain"]]).strip():
            raise ExecutorRefused("ipv6_hook_unavailable")
        self.guest.run([
            "ip6tables", "-w", "-A", spec["hook_chain"], "-s", spec["source_cidr"],
            "-m", "comment", "--comment", spec["comment"], "-j", "DROP",
        ])

    def _remove_rules(self, action: bootstrap.Action) -> None:
        spec = rule_spec(self.config)
        try:
            listing = self.guest.run(["iptables", "-S"])
        except ExecutorRefused as exc:
            raise ExecutorRefused(_hook_category(exc)) from exc
        if spec["comment"] not in listing:
            raise ExecutorRefused("owned_rules_missing")
        for entry in reversed(spec["allow"] + spec["deny"]):
            self.guest.run(["iptables", "-w", *rule_argv(spec, entry, "-D")])
        try:
            self.guest.run([
                "ip6tables", "-w", "-D", spec["hook_chain"], "-s", spec["source_cidr"],
                "-m", "comment", "--comment", spec["comment"], "-j", "DROP",
            ])
        except ExecutorRefused as exc:
            raise ExecutorRefused("owned_rules_missing") from exc
        if spec["comment"] in self.guest.run(["iptables", "-S"]):
            raise ExecutorRefused("owned_rules_not_removed")

    # -- credentials -------------------------------------------------------

    def _channel(self) -> dict:
        if self._credentials is None:
            if self.channel.sha256 != self.config.credential_channel_digest:
                raise ExecutorRefused("credential_channel_digest_mismatch")
            document = self.channel.document()
            if document.get("realm_id") != self.config.realm_id:
                raise ExecutorRefused("credential_channel_scope_mismatch")
            if document.get("valid_until") != self.config.valid_until:
                raise ExecutorRefused("credential_channel_scope_mismatch")
            self._credentials = document
        return self._credentials

    def _deliver_credentials(self, action: bootstrap.Action) -> None:
        parameters = dict(action.parameters)
        if parameters.get("channel_digest") != self.config.credential_channel_digest:
            raise ExecutorRefused("credential_channel_digest_mismatch")
        if parameters.get("postgres_uid") != self.config.postgres_uid:
            raise ExecutorRefused("identity_mismatch")
        if parameters.get("workload_uid") != self.config.workload_uid:
            raise ExecutorRefused("identity_mismatch")
        document = self._channel()
        for key, path in (
            ("postgres_superuser_password", self.secret_files["superuser"]),
            ("authority_password", self.secret_files["authority"]),
            ("purge_password", self.secret_files["purge"]),
        ):
            _write_secret(path, document[key].encode())

    def _withdraw_credentials(self, action: bootstrap.Action) -> None:
        path = self.secret_files["superuser"]
        document = self._channel()
        expected = document["postgres_superuser_password"].encode()
        if not path.is_file() or path.read_bytes() != expected:
            raise ExecutorRefused("provisioner_credential_missing")
        os.unlink(path)

    def _revoke_credentials(self, action: bootstrap.Action) -> None:
        present = [path for path in (*self.secret_files.values(), self.channel.path)
                   if path.is_file()]
        if not present:
            raise ExecutorRefused("run_credentials_absent")
        if self.channel.path.is_file():
            self._channel()  # identity and digest checked before anything is removed
        for path in present:
            os.unlink(path)
        self._credentials = None  # the channel is gone: no cached secret survives

    def _remove_credentials(self, action: bootstrap.Action) -> None:
        for path in (*self.secret_files.values(), self.channel.path):
            if path.exists():
                raise ExecutorRefused("run_credentials_still_present")
        for directory in (self.secrets_dir, self.channel.path.parent):
            try:
                if directory.is_dir() and not any(directory.iterdir()):
                    os.rmdir(directory)
            except OSError as exc:
                raise ExecutorRefused("credential_cleanup_failed") from exc

    # -- postgres ----------------------------------------------------------

    @staticmethod
    def _sql_literal(value: str) -> str:
        if PASSWORD_PATTERN.fullmatch(value) is None:
            raise ExecutorRefused("credential_channel_invalid")
        return "'" + value.replace("'", "''") + "'"

    def _start_postgres(self, action: bootstrap.Action) -> None:
        parameters = dict(action.parameters)
        if parameters.get("image") != self.config.postgres_image:
            raise ExecutorRefused("image_identity_mismatch")
        if parameters.get("address") != self.config.authority_database.address:
            raise ExecutorRefused("endpoint_identity_mismatch")
        if parameters.get("user") != self.config.postgres_uid:
            raise ExecutorRefused("identity_mismatch")
        if parameters.get("network") != self.network or parameters.get("volume") != self.volume:
            raise ExecutorRefused("identity_mismatch")
        if parameters.get("max_connections") != self.config.max_connections:
            raise ExecutorRefused("identity_mismatch")
        if parameters.get("memory_bytes") != self.config.memory_bytes:
            raise ExecutorRefused("identity_mismatch")
        if parameters.get("cpus") != self.config.cpus:
            raise ExecutorRefused("identity_mismatch")
        if self._resource_exists(self.cluster):
            raise ExecutorRefused("owned_resource_already_present")
        password_file = self.secret_files["superuser"]
        if not password_file.is_file():
            raise ExecutorRefused("provisioner_credential_missing")
        uid = str(self.config.postgres_uid)
        # The unprivileged image cannot chown its own PGDATA: a bounded, root,
        # ephemeral owner-preparation step runs before the unprivileged server.
        self.runner.run([
            "run", "--rm", "--user", "0", "--label", *self.labels(),
            "--volume", f"{self.volume}:/var/lib/postgresql/data",
            "--entrypoint", "sh", self.config.postgres_image, "-c",
            f"chown -R {uid}:{uid} /var/lib/postgresql/data "
            f"&& chmod 700 /var/lib/postgresql/data",
        ])
        self.runner.run([
            "run", "--detach", "--name", self.cluster, "--label", *self.labels(),
            "--network", self.network, "--ip", self.config.authority_database.address,
            "--network-alias", self.config.authority_database.host,
            "--user", uid, "--read-only",
            "--tmpfs", f"/tmp:rw,size=64m,uid={uid},gid={uid},mode=1777",
            "--tmpfs", f"/var/run/postgresql:rw,size=8m,uid={uid},gid={uid},mode=0755",
            "--security-opt", "no-new-privileges", "--cap-drop", "ALL",
            "--pids-limit", "256", "--memory", str(self.config.memory_bytes),
            "--cpus", str(self.config.cpus), "--restart", "no",
            "--volume", f"{self.volume}:/var/lib/postgresql/data",
            "--mount",
            f"type=bind,src={password_file},dst=/run/secrets/u1_superuser_password,readonly",
            "--env", "POSTGRES_PASSWORD_FILE=/run/secrets/u1_superuser_password",
            "--env", "POSTGRES_INITDB_ARGS=--auth-host=scram-sha-256",
            self.config.postgres_image, "-c",
            f"max_connections={self.config.max_connections}",
        ])

    def _provision(self, action: bootstrap.Action) -> None:
        parameters = dict(action.parameters)
        if parameters.get("authority") != self.config.authority_database.model_dump():
            raise ExecutorRefused("endpoint_identity_mismatch")
        if parameters.get("purge") != self.config.purge_database.model_dump():
            raise ExecutorRefused("endpoint_identity_mismatch")
        if parameters.get("credentials") != self.credentials:
            raise ExecutorRefused("identity_mismatch")
        document = self._channel()
        self._exec_psql(bootstrap.provisioning_sql(self.config))
        for role, key, path in (
            (self.config.authority_database.role, "authority_password",
             self.secret_files["authority"]),
            (self.config.purge_database.role, "purge_password", self.secret_files["purge"]),
        ):
            # Secret travels on stdin only: never argv, never logged, never echoed.
            self._exec_psql(f"ALTER ROLE {role} PASSWORD {self._sql_literal(document[key])};")
            _write_secret(path, document[key].encode())

    def _exec_psql(self, payload: str) -> None:
        self.runner.run(
            ["exec", "--interactive", "--user", str(self.config.postgres_uid), self.cluster,
             "psql", "--username", "postgres", "--no-psqlrc", "--set", "ON_ERROR_STOP=1",
             "--file", "-"],
            stdin=payload.encode(),
        )

    # -- workload ----------------------------------------------------------

    def _start_workload(self, action: bootstrap.Action) -> None:
        parameters = dict(action.parameters)
        if parameters.get("image") != self.config.workload_image:
            raise ExecutorRefused("image_identity_mismatch")
        if parameters.get("hostname") != self.config.workload_hostname:
            raise ExecutorRefused("identity_mismatch")
        if parameters.get("user") != self.config.workload_uid:
            raise ExecutorRefused("identity_mismatch")
        if parameters.get("network") != self.network:
            raise ExecutorRefused("identity_mismatch")
        if parameters.get("source_digest") != self.config.source_digest:
            raise ExecutorRefused("source_identity_mismatch")
        if self._resource_exists(self.workload):
            raise ExecutorRefused("owned_resource_already_present")
        if tree_digest(self.source_root) != self.config.source_digest:
            raise ExecutorRefused("source_identity_mismatch")
        bindings = RuntimeBindings.from_channel(
            self.channel,
            self.config,
            manifest_path=self.manifest_path,
            receipt_path=self.receipt_path,
            evidence_dir=self.evidence_dir,
        )
        uid = str(self.config.workload_uid)
        dsn_file = self.secret_files["dsn"]
        _write_secret(dsn_file, f"DOCSURI_U1_AUTHORITY_DSN={bindings.authority_dsn}\n".encode())
        self.runner.run([
            "run", "--detach", "--name", self.workload, "--label", *self.labels(),
            "--hostname", self.config.workload_hostname, "--network", self.network,
            "--user", uid, "--read-only",
            "--tmpfs", f"/tmp:rw,size=64m,uid={uid},gid={uid},mode=1777",
            "--security-opt", "no-new-privileges", "--cap-drop", "ALL",
            "--pids-limit", "256", "--memory", str(self.config.memory_bytes),
            "--cpus", str(self.config.cpus), "--restart", "no",
            "--mount", f"type=bind,src={self.source_root},dst=/workspace/src,readonly",
            "--mount",
            f"type=bind,src={bindings.manifest_path},dst=/run/u1/manifest.json,readonly",
            "--mount", f"type=bind,src={bindings.receipt_path},dst=/run/u1/receipt.json,readonly",
            "--mount", f"type=bind,src={bindings.evidence_dir},dst=/workspace/evidence",
            "--env-file", str(dsn_file),
            "--env", "DOCSURI_U1_TEST_REALM_MANIFEST=/run/u1/manifest.json",
            "--env", f"DOCSURI_U1_TEST_REALM_SHA256={bindings.manifest_sha256}",
            "--env", "DOCSURI_U1_ISOLATION_RECEIPT=/run/u1/receipt.json",
            "--env", f"DOCSURI_U1_ISOLATION_RECEIPT_SHA256={bindings.receipt_sha256}",
            "--env", "DOCSURI_U1_EVIDENCE_DIR=/workspace/evidence",
            self.config.workload_image,
        ])

    def _stop_container(self, action: bootstrap.Action) -> None:
        identity = action.identity
        if identity not in (self.cluster, self.workload):
            raise ExecutorRefused("identity_mismatch")
        self._require_labels("container", identity)
        self.runner.run(["rm", "--force", identity])


def _hook_category(exc: ExecutorRefused) -> str:
    """Preserve the refusal of an absent privileged channel instead of relabelling."""
    if str(exc) == "guest_authorization_required":
        return "guest_authorization_required"
    return "guest_hook_unavailable"


def _write_secret(path: Path, payload: bytes) -> None:
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    except OSError as exc:
        raise ExecutorRefused("credential_write_failed") from exc
    try:
        os.write(fd, payload)
    except OSError as exc:
        raise ExecutorRefused("credential_write_failed") from exc
    finally:
        os.close(fd)


def _private_dir(path: Path) -> None:
    try:
        info = path.lstat()
    except OSError as exc:
        raise ExecutorRefused("secrets_dir_invalid") from exc
    if (
        stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode) or not path.is_absolute()
        or info.st_mode & 0o077
    ):
        raise ExecutorRefused("secrets_dir_invalid")


def _owned_evidence_dir(path: Path, workload_uid: int) -> bool:
    try:
        link = path.lstat()
        info = path.stat()
    except OSError:
        return False
    if stat.S_ISLNK(link.st_mode) or not stat.S_ISDIR(link.st_mode):
        return False
    if not path.is_absolute() or info.st_uid != workload_uid:
        return False
    return not info.st_mode & 0o022


def main(argv: list[str] | None = None) -> int:
    """Digest helpers only.  This CLI never applies, starts, pulls or deletes."""
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    tree = subparsers.add_parser("tree-digest", help="digest a read-only source copy")
    tree.add_argument("root", type=Path)
    subparsers.add_parser("self-digest", help="digest this executor")
    spec = subparsers.add_parser("rule-spec", help="print the owned rule specification digest")
    spec.add_argument("--config", type=Path, required=True)
    spec.add_argument("--sha256", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "tree-digest":
            print(json.dumps({"mode": "digest", "applied": False,
                              "tree_sha256": tree_digest(args.root)}))
        elif args.command == "self-digest":
            print(json.dumps({"mode": "digest", "applied": False,
                              "executor_sha256": ColimaExecutor.self_digest()}))
        else:
            raw = Path(args.config).read_bytes()
            if digest(raw) != args.sha256:
                raise ExecutorRefused("configuration_digest_mismatch")
            config = bootstrap.parse_config(raw)
            print(json.dumps({"mode": "digest", "applied": False,
                              "rules_sha256": rule_spec_digest(config)}))
    except (ExecutorRefused, OSError, bootstrap.BootstrapBlocked) as exc:
        print(json.dumps({"mode": "digest", "applied": False, "error": str(exc)}))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
