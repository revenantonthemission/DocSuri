"""Inspect-by-default, database-ONLY U1 launcher contract and owned reversal.

Run ``python server/u1_db_bootstrap.py --config PUBLIC_JSON --sha256 HEX`` to
inspect. This CLI has NO application verb and never connects, fetches images,
starts containers, reads credentials, changes rules or issues isolation receipts.

The complete application/reversal sequence is exposed to an operator's separately
qualified executor through ``execute_plan``. That executor must implement the
typed actions below (resource creation, protected credential delivery, guest-rule
application, PostgreSQL provisioner and identity-scoped deletion). It is NOT the
production installer/run.sh or a shell assembled from an untrusted document.
Every action requires freshly rechecked protected authorization/qualification;
fixture admission additionally requires independent measured isolation/role proof.
An executor's successful return is NOT a measured receipt or schema acceptance.
"""

from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import os
import re
import stat
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

Digest = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
Name = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_-]{0,62}$")]
Image = Annotated[str, Field(pattern=r"^[a-z0-9./_-]+@sha256:[a-f0-9]{64}$")]


class BootstrapBlocked(RuntimeError):
    """Safe category only; no config/credentials or raw executor/validator text."""


class Value(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class Database(Value):
    host: Name
    address: str
    port: Literal[5432]
    database: Name
    role: Name
    connection_limit: Annotated[int, Field(ge=1, le=8)]

    @model_validator(mode="before")
    @classmethod
    def integer_port(cls, raw):
        if not isinstance(raw, dict) or type(raw.get("port")) is not int:
            raise ValueError("port_invalid")
        return raw


class BootstrapConfig(Value):
    version: Literal[1]
    unit: Literal["u1-job-skeleton"]
    environment: Literal["u1-staging"]
    realm_id: Annotated[str, Field(pattern=r"^[a-f0-9]{16}$")]
    context: Name
    guest_id: Digest
    runtime_digest: Digest
    source_digest: Digest
    launcher_digest: Digest
    rules_digest: Digest
    postgres_image: Image
    workload_image: Image
    postgres_uid: Annotated[int, Field(ge=1)]
    workload_uid: Annotated[int, Field(ge=1)]
    operator_uid: Annotated[int, Field(ge=1)]
    workload_hostname: Name
    internal_network_cidr: str
    authority_database: Database
    purge_database: Database
    memory_bytes: Annotated[int, Field(ge=134217728)]
    cpus: Annotated[int, Field(ge=1, le=64)]
    disk_reserve_bytes: Annotated[int, Field(ge=134217728)]
    max_connections: Annotated[int, Field(ge=16, le=100)]
    credential_channel_digest: Digest
    valid_until: str

    @model_validator(mode="before")
    @classmethod
    def integer_version(cls, raw):
        if not isinstance(raw, dict) or type(raw.get("version")) is not int:
            raise ValueError("version_invalid")
        return raw

    @model_validator(mode="after")
    def validate_boundaries(self):
        if type(self.version) is not int:
            raise ValueError("version_invalid")
        network = ipaddress.ip_network(self.internal_network_cidr, strict=True)
        # Dedicated IPv4 subnet; unsupported IPv6 is explicitly denied by the
        # rule contract and measured negatives, NOT inferred from this setting.
        if (network.version != 4 or not network.is_private or network.is_loopback
                or network.is_link_local or not 24 <= network.prefixlen <= 28):
            raise ValueError("network_invalid")
        authority, purge = self.authority_database, self.purge_database
        for purpose, database in (("authority", authority), ("purge", purge)):
            prefix = "docsuri_u1_" + purpose + "_" + self.realm_id
            if database.database != prefix or database.role != prefix:
                raise ValueError("database_role_identity_invalid")
            destination = ipaddress.ip_address(database.address)
            if (destination not in network or destination in (network.network_address,
                                                             network.broadcast_address)
                    or database.host in {"localhost", "host-gateway", "host.docker.internal"}):
                raise ValueError("endpoint_invalid")
        authority_endpoint = (authority.host, authority.address, authority.port)
        if authority_endpoint != (purge.host, purge.address, purge.port):
            raise ValueError("dedicated_cluster_identity_invalid")
        if self.operator_uid == self.workload_uid or self.postgres_uid == self.workload_uid:
            raise ValueError("principal_separation_required")
        if authority.connection_limit + purge.connection_limit + 2 > self.max_connections:
            raise ValueError("connection_headroom_required")
        valid_time(self.valid_until)
        return self


def valid_time(value: object) -> datetime:
    pattern = r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]+)?Z"
    if not isinstance(value, str) or not re.fullmatch(pattern, value):
        raise BootstrapBlocked("validity_invalid")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise BootstrapBlocked("validity_invalid") from exc


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _hex_digest(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[a-f0-9]{64}", value) is not None


def _decode(raw: bytes) -> dict:
    def reject_constant(_value):
        raise ValueError("document_invalid")

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise BootstrapBlocked("document_invalid")
            result[key] = value
        return result

    try:
        value = json.loads(raw, object_pairs_hook=unique, parse_constant=reject_constant)
        if not isinstance(value, dict):
            raise BootstrapBlocked("document_invalid")
        return value
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise BootstrapBlocked("document_invalid") from exc


def parse_config(raw: bytes) -> BootstrapConfig:
    try:
        return BootstrapConfig.model_validate(_decode(raw))
    except (ValueError, TypeError, ValidationError) as exc:
        raise BootstrapBlocked("configuration_invalid") from exc


@dataclass(frozen=True)
class Action:
    operation: str
    identity: str
    parameters: tuple[tuple[str, object], ...] = ()

    def to_dict(self) -> dict:
        return {"operation": self.operation, "identity": self.identity,
                "parameters": dict(self.parameters)}


@dataclass(frozen=True)
class BootstrapPlan:
    config: BootstrapConfig
    config_digest: str
    actions: tuple[Action, ...]
    reversal: tuple[Action, ...]
    raw_config: bytes = field(repr=False)

    def inspect(self) -> dict:
        return {"version": 1, "unit": self.config.unit, "environment": self.config.environment,
                "realm_id": self.config.realm_id, "config_sha256": self.config_digest,
                "mode": "inspect", "application_performed": False, "realm_admitted": False,
                "actions": [action.to_dict() for action in self.actions],
                "reversal": [action.to_dict() for action in self.reversal],
                "fixture_prerequisites": ["independent measured isolation and role/marker probes",
                                          "protected launcher manifest/receipt/trusted digests",
                                          "focused final003/policy source review",
                                          "read-only then mutation-connection identity checks"]}


def build_plan(raw: bytes) -> BootstrapPlan:
    config = parse_config(raw)
    prefix = "docsuri-u1-" + config.realm_id
    network, volume, cluster, workload = (
        prefix + suffix for suffix in ("-net", "-data", "-pg", "-test")
    )
    credentials = prefix + "-credentials"
    labels = (("unit", config.unit), ("realm_id", config.realm_id),
              ("environment", config.environment))
    actions = (
        Action("verify_original_inventory", config.guest_id),
        Action("create_internal_network", network,
               (("cidr", config.internal_network_cidr), ("internal", True), ("ipv6", False),
                ("context", config.context), ("labels", labels))),
        Action("apply_owned_guest_rules", config.rules_digest,
               (("network", network), ("deny_ipv4_external_host_lan_production", True),
                ("deny_unsupported_ipv6", True), ("preserve_original_rules", True))),
        Action("create_owned_volume", volume, (("labels", labels),)),
        Action("deliver_protected_credentials", credentials,
               (("channel_digest", config.credential_channel_digest),
                ("postgres_uid", config.postgres_uid),
                ("workload_uid", config.workload_uid), ("read_only_workload", True))),
        Action("start_private_postgres", cluster,
               (("image", config.postgres_image), ("network", network), ("volume", volume),
                ("address", config.authority_database.address), ("published_ports", ()),
                ("user", config.postgres_uid), ("read_only_root", True), ("capabilities", ()),
                ("memory_bytes", config.memory_bytes), ("cpus", config.cpus),
                ("max_connections", config.max_connections), ("labels", labels))),
        Action("provision_separated_roles_databases_markers", cluster,
               (("authority", config.authority_database.model_dump()),
                ("purge", config.purge_database.model_dump()), ("credentials", credentials),
                ("sql", provisioning_sql(config)))),
        Action("withdraw_provisioner_credentials", credentials),
        Action("start_unadmitted_probe_workload", workload,
               (("image", config.workload_image), ("hostname", config.workload_hostname),
                ("network", network), ("user", config.workload_uid), ("source_read_only", True),
                ("source_digest", config.source_digest), ("output_separate", True),
                ("external_networks", ()), ("host_home_socket_mounts", ()), ("capabilities", ()),
                ("published_ports", ()), ("labels", labels))),
    )
    reversal = (
        Action("stop_identity_verified_workload", workload, (("labels", labels),)),
        Action("revoke_run_credentials", credentials),
        Action("stop_identity_verified_cluster", cluster, (("labels", labels),)),
        Action("remove_identity_verified_volume", volume, (("labels", labels),)),
        Action("remove_identity_verified_credentials", credentials),
        Action("remove_owned_guest_rules", config.rules_digest, (("network", network),)),
        Action("remove_identity_verified_network", network, (("labels", labels),)),
        Action("reconcile_original_inventory", config.guest_id),
    )
    return BootstrapPlan(config, digest(raw), actions, reversal, raw)


def provisioning_sql(config: BootstrapConfig) -> str:
    """Fresh-cluster provisioner ONLY. Password delivery is executor/channel-owned.

    No production DSN, full authority schema or later destructive purge fixture is
    included. All names are validated SQL identifiers; values are bound literals
    from the constrained public configuration, never credential interpolation.
    """
    marker_owner = "docsuri_u1_marker_" + config.realm_id
    lines = [f"CREATE ROLE {marker_owner} NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;",
             "REVOKE CONNECT ON DATABASE postgres, template1 FROM PUBLIC;"]
    for database in (config.authority_database, config.purge_database):
        purpose = "authority" if database == config.authority_database else "purge"
        lines.extend([
            f"CREATE ROLE {database.role} LOGIN NOSUPERUSER NOCREATEDB "
            "NOCREATEROLE NOINHERIT NOBYPASSRLS "
            f"CONNECTION LIMIT {database.connection_limit};",
            f"CREATE DATABASE {database.database} TEMPLATE template0 ENCODING 'UTF8';",
            f"REVOKE ALL ON DATABASE {database.database} FROM PUBLIC;",
            f"GRANT CONNECT ON DATABASE {database.database} TO {database.role};",
            f"\\connect {database.database}",
            "REVOKE ALL ON SCHEMA public FROM PUBLIC;",
            f"GRANT USAGE, CREATE ON SCHEMA public TO {database.role};",
            "CREATE TABLE public.u1_test_realm (singleton BOOLEAN PRIMARY KEY CHECK (singleton), "
            "realm_id TEXT NOT NULL, purpose TEXT NOT NULL, source_sha256 TEXT NOT NULL, "
            "launcher_sha256 TEXT NOT NULL, rules_sha256 TEXT NOT NULL, "
            "valid_until TIMESTAMPTZ NOT NULL);",
            f"ALTER TABLE public.u1_test_realm OWNER TO {marker_owner};",
            "REVOKE ALL ON TABLE public.u1_test_realm FROM PUBLIC;",
            f"GRANT SELECT ON TABLE public.u1_test_realm TO {database.role};",
            "INSERT INTO public.u1_test_realm VALUES (TRUE, "
            f"'{config.realm_id}', '{purpose}', "
            f"'{config.source_digest}', '{config.launcher_digest}', '{config.rules_digest}', "
            f"'{config.valid_until}');",
            "\\connect postgres",
        ])
    return "\n".join(lines) + "\n"


@dataclass(frozen=True)
class DocumentReference:
    path: Path
    sha256: str


def protected_document(reference: DocumentReference) -> dict:
    """Operator-owned, immutable trust channel. The workload cannot replace a parent."""
    path = reference.path
    if not path.is_absolute() or not re.fullmatch(r"[a-f0-9]{64}", reference.sha256):
        raise BootstrapBlocked("protected_reference_invalid")
    try:
        for part in (path, *path.parents):
            info = part.lstat()
            if stat.S_ISLNK(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
                raise BootstrapBlocked("protected_ownership_invalid")
        info = path.stat()
        if not stat.S_ISREG(info.st_mode) or info.st_size > 65536 or info.st_mode & 0o222:
            raise BootstrapBlocked("protected_document_invalid")
        raw = path.read_bytes()
    except OSError as exc:
        raise BootstrapBlocked("protected_document_unavailable") from exc
    if digest(raw) != reference.sha256:
        raise BootstrapBlocked("protected_document_digest_mismatch")
    return _decode(raw)


class Admission(Protocol):
    def check_current(self, plan: BootstrapPlan, purpose: str) -> None:
        """Independent protected documents/clock, never a workload-generated flag."""


@dataclass(frozen=True)
class ProtectedAdmission:
    authorization: DocumentReference
    qualification: DocumentReference
    inventory: DocumentReference
    isolation: DocumentReference | None = None

    def check_current(self, plan: BootstrapPlan, purpose: str) -> None:
        auth = protected_document(self.authorization)
        qualification = protected_document(self.qualification)
        inventory = protected_document(self.inventory)
        config = plan.config
        now = datetime.now(UTC)
        binding = {"unit": config.unit, "environment": config.environment,
                   "realm_id": config.realm_id, "config_sha256": plan.config_digest,
                   "context": config.context, "guest_id": config.guest_id,
                   "runtime_sha256": config.runtime_digest, "source_sha256": config.source_digest,
                   "launcher_sha256": config.launcher_digest, "rules_sha256": config.rules_digest,
                   "credential_channel_sha256": config.credential_channel_digest}
        for document in (auth, qualification, inventory):
            if (document.get("binding") != binding
                    or valid_time(document.get("valid_until", "")) <= now):
                raise BootstrapBlocked("admission_identity_or_validity_mismatch")
        if valid_time(config.valid_until) <= now:
            raise BootstrapBlocked("configuration_expired")
        if (auth.get("operator") != "revenantonthemission" or auth.get("operation") != purpose
                or auth.get("original_inventory_sha256") != self.inventory.sha256
                or auth.get("qualified_artifacts_sha256") != self.qualification.sha256):
            raise BootstrapBlocked("concrete_authorization_required")
        if (qualification.get("images") != [config.postgres_image, config.workload_image]
                or qualification.get("disposition") != "QUALIFIED"
                or qualification.get("blocking_findings") != []
                or not _hex_digest(qualification.get("security_report_sha256"))):
            raise BootstrapBlocked("qualified_artifacts_required")
        fresh_resources = [action.identity for action in plan.actions if action.operation in {
            "create_internal_network", "create_owned_volume", "start_private_postgres",
            "start_unadmitted_probe_workload",
        }]
        if (type(inventory.get("disk_available_bytes")) is not int
                or type(inventory.get("memory_available_bytes")) is not int
                or inventory.get("fresh_resources_absent") != fresh_resources
                or inventory.get("nonoverlapping_cidr") != config.internal_network_cidr
                or inventory.get("disk_available_bytes", 0) < config.disk_reserve_bytes
                or inventory.get("memory_available_bytes", 0) < config.memory_bytes):
            raise BootstrapBlocked("resource_inventory_or_headroom_required")
        if digest(Path(__file__).read_bytes()) != config.launcher_digest:
            raise BootstrapBlocked("executing_launcher_changed")
        if purpose == "fixtures":
            if self.isolation is None:
                raise BootstrapBlocked("independent_isolation_required")
            proof = protected_document(self.isolation)
            required = {"exact_database_access", "direct_egress_denied",
                        "host_lan_production_denied", "unqualified_address_families_denied",
                        "no_production_mounts_or_credentials",
                        "marker_write_denied", "cross_database_denied", "bounded_roles"}
            observations = proof.get("observations")
            if (proof.get("binding") != binding or valid_time(proof.get("valid_until", "")) <= now
                    or not isinstance(observations, dict) or set(observations) != required
                    or any(not isinstance(observation, dict) or observation.get("outcome") != "PASS"
                           or not _hex_digest(observation.get("evidence_sha256"))
                        for observation in observations.values())):
                raise BootstrapBlocked("independent_measurements_required")


class OperatorExecutor(Protocol):
    def execute(self, action: Action) -> None:
        """Qualified implementation of exact action, bounded IO, identity-scoped removal.

        Must recheck measured guest/resources/image/rules/mount identities; never
        globally prune/restart, fall back to production DSNs or print secret data.
        verify/reconcile actions compare original inventory; credential actions
        use only the independently admitted protected channel.
        """


def execute_plan(plan: BootstrapPlan, admission: ProtectedAdmission, executor: OperatorExecutor, *,
                 purpose: Literal["bootstrap", "rollback"]) -> tuple[str, ...]:
    """Explicit operator integration, NOT reachable from inspect CLI; fails closed.

    A partial failure leaves completed identities for operator reconciliation. It
    never guesses cleanup, emits verified flags or auto-runs destructive reversal.
    """
    if type(admission) is not ProtectedAdmission:
        raise BootstrapBlocked("protected_admission_required")
    if purpose not in {"bootstrap", "rollback"}:
        raise BootstrapBlocked("operation_invalid")
    completed = []
    for action in plan.actions if purpose == "bootstrap" else plan.reversal:
        if plan != build_plan(plan.raw_config):
            raise BootstrapBlocked("plan_changed_after_inspection")
        admission.check_current(plan, purpose)
        try:
            executor.execute(action)
        except Exception as exc:
            raise BootstrapBlocked("operator_action_failed:" + action.operation) from exc
        completed.append(action.identity)
    return tuple(completed)


def inspect_file(path: Path, expected_digest: str, environment: Mapping[str, str]) -> dict:
    forbidden = {"DATABASE_URL", "PGHOST", "PGSERVICE", "PGPASSFILE", "PGOPTIONS", "PGHOSTADDR",
                 "DOCSURI_CONTROL_PLANE_DSN", "DOCSURI_U1_AUTHORITY_DSN", "AWS_PROFILE",
                 "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"}
    if forbidden.intersection(environment):
        raise BootstrapBlocked("credential_or_database_environment_refused")
    try:
        if (not path.is_absolute() or path.is_symlink() or not path.is_file()
                or path.stat().st_size > 65536):
            raise BootstrapBlocked("configuration_path_invalid")
        raw = path.read_bytes()
    except OSError as exc:
        raise BootstrapBlocked("configuration_unavailable") from exc
    if digest(raw) != expected_digest:
        raise BootstrapBlocked("configuration_digest_mismatch")
    return build_plan(raw).inspect()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--sha256", required=True)
    args = parser.parse_args(argv)
    try:
        report = inspect_file(args.config, args.sha256, os.environ)
    except BootstrapBlocked as exc:
        print(json.dumps({"mode": "inspect", "application_performed": False, "error": str(exc)}))
        return 1
    print(json.dumps(report, ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
