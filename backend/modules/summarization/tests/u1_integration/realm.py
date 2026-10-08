"""Read-only, identity-bound preflight for the dedicated U1 authority database.

This validates *operator-supplied* isolation/realm receipts; it does not issue them,
configure a firewall, mint credentials, or assert that a synthetic receipt is live
proof. No DSN, password, raw driver error or receipt capability is printed.
"""

from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import re
import socket
import stat
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from summarization.domain.job_protocol import JobProtocolError, rfc3339_instant


class RealmBlocked(RuntimeError):
    pass


class Connection(Protocol):
    def execute(self, query: str, parameters: tuple = ()) -> object: ...
    def close(self) -> None: ...


@dataclass(frozen=True, slots=True)
class AuthorityRealm:
    realm_id: str
    host: str
    address: str
    port: int
    database: str
    role: str
    manifest_digest: str
    dsn: str = field(repr=False)
    purge_database: str
    source_digest: str
    launcher_digest: str
    rules_digest: str
    valid_until: str
    connection_limit: int
    environment: tuple[tuple[str, str], ...] = field(repr=False)

    def check_current(self) -> None:
        if require_authority_realm(dict(self.environment)) != self:
            raise RealmBlocked("U1 protected realm changed; no mutation permitted")


def _document(path: str | None, expected_digest: str | None) -> dict:
    if not path or not expected_digest:
        raise RealmBlocked("U1 realm manifest/receipt and its trusted SHA-256 are required")
    source = Path(path)
    if (not source.is_absolute() or source.is_symlink()
            or not re.fullmatch(r"[a-f0-9]{64}", expected_digest)):
        raise RealmBlocked("U1 realm document path refused")
    info = source.stat()
    for parent in (source, *source.parents):
        parent_info = parent.lstat()
        if (stat.S_ISLNK(parent_info.st_mode) or parent_info.st_uid != 0
                or parent_info.st_mode & 0o022):
            raise RealmBlocked("U1 realm documents require protected operator ownership")
    if not source.is_file() or info.st_size > 65536 or info.st_mode & 0o222:
        raise RealmBlocked("U1 realm document must be bounded and read-only")
    payload = source.read_bytes()
    if hashlib.sha256(payload).hexdigest() != expected_digest:
        raise RealmBlocked("U1 realm document identity mismatch")
    try:
        document = json.loads(payload)
    except (ValueError, UnicodeError) as exc:
        raise RealmBlocked("U1 realm document invalid") from exc
    if not isinstance(document, dict):
        raise RealmBlocked("U1 realm document invalid")
    return document


def require_authority_realm(environment: Mapping[str, str] | None = None) -> AuthorityRealm:
    env = os.environ if environment is None else environment
    if any(key.startswith("PG") or key in {"DATABASE_URL", "DOCSURI_CONTROL_PLANE_DSN"}
           for key in env):
        raise RealmBlocked("U1 inherited database environment refused")
    manifest = _document(env.get("DOCSURI_U1_TEST_REALM_MANIFEST"),
                         env.get("DOCSURI_U1_TEST_REALM_SHA256"))
    if (type(manifest.get("version")) is not int or manifest.get("version") != 1
            or manifest.get("unit") != "u1-job-skeleton"
            or manifest.get("environment") != "u1-staging"
            or not isinstance(manifest.get("realm_id"), str)
            or not re.fullmatch(r"[a-f0-9]{16}", manifest["realm_id"])):
        raise RealmBlocked("U1 authority realm identity invalid")
    # Destructive fixtures are admitted only in the selected guest/workload
    # boundary, never in the documented native production source environment.
    if os.uname().sysname != "Linux" or socket.gethostname() != manifest.get("workload_hostname"):
        raise RealmBlocked("U1 fixtures require the qualified isolated Linux workload")
    receipt_digest = env.get("DOCSURI_U1_ISOLATION_RECEIPT_SHA256")
    receipt = _document(env.get("DOCSURI_U1_ISOLATION_RECEIPT"), receipt_digest)
    try:
        valid_until = rfc3339_instant(receipt["valid_until"])
    except (KeyError, TypeError, ValueError, JobProtocolError) as exc:
        raise RealmBlocked("U1 isolation receipt validity missing") from exc
    if (valid_until.tzinfo is None or valid_until <= datetime.now(UTC)
            or manifest.get("isolation_receipt_sha256") != receipt_digest
            or receipt.get("realm_id") != manifest["realm_id"]
            or receipt.get("unit") != "u1-job-skeleton"
            or receipt.get("environment") != "u1-staging"
            or receipt.get("verified") != {
                "direct_egress_denied": True, "host_lan_production_denied": True,
                "unqualified_address_families_denied": True,
            }):
        raise RealmBlocked("U1 isolation proof missing, expired or mismatched")
    binding = manifest.get("binding")
    required_digests = {"config_sha256", "guest_id", "runtime_sha256", "source_sha256",
                        "launcher_sha256", "rules_sha256", "credential_channel_sha256"}
    if (not isinstance(binding, dict) or receipt.get("binding") != binding
            or set(binding) != required_digests | {"unit", "environment", "realm_id", "context"}
            or any(not isinstance(binding.get(key), str)
                   or not re.fullmatch(r"[a-f0-9]{64}", binding[key])
                   for key in required_digests)
            or any(binding.get(key) != manifest[key] for key in ("unit", "environment", "realm_id"))
            or not isinstance(binding.get("context"), str) or not binding["context"]):
        raise RealmBlocked("U1 launcher/source/image/rule binding invalid")
    observations = receipt.get("observations")
    required_probes = {"exact_database_access", "direct_egress_denied",
                       "host_lan_production_denied", "unqualified_address_families_denied",
                       "no_production_mounts_or_credentials",
                       "marker_write_denied", "cross_database_denied", "bounded_roles"}
    if (not isinstance(observations, dict) or set(observations) != required_probes
            or any(not isinstance(item, dict) or item.get("outcome") != "PASS"
                   or not isinstance(item.get("evidence_sha256"), str)
                   or not re.fullmatch(r"[a-f0-9]{64}", item["evidence_sha256"])
                   for item in observations.values())):
        raise RealmBlocked("U1 independent measured observations required")
    authority = manifest.get("authority_database", {})
    purge = manifest.get("purge_database", {})
    if not isinstance(authority, dict) or not isinstance(purge, dict):
        raise RealmBlocked("U1 database identities missing")
    database, role = authority.get("database"), authority.get("role")
    if (database != "docsuri_u1_authority_" + manifest["realm_id"] or role != database
            or purge.get("database") != "docsuri_u1_purge_" + manifest["realm_id"]
            or purge.get("role") != purge.get("database")):
        raise RealmBlocked("U1 authority and minimal-schema purge databases must be distinct")
    for item in (authority, purge):
        if type(item.get("connection_limit")) is not int or not 1 <= item["connection_limit"] <= 8:
            raise RealmBlocked("U1 bounded database roles required")
    host, address, port = authority.get("host"), authority.get("address"), authority.get("port")
    if not isinstance(host, str) or host in {"localhost", "host.docker.internal", "host-gateway"}:
        raise RealmBlocked("U1 database host invalid")
    if any(authority.get(key) != purge.get(key) for key in ("host", "address", "port")):
        raise RealmBlocked("U1 databases require the same dedicated cluster")
    try:
        network = ipaddress.ip_network(manifest["internal_network_cidr"], strict=True)
        destination = ipaddress.ip_address(address)
    except (KeyError, ValueError, TypeError) as exc:
        raise RealmBlocked("U1 database address binding missing") from exc
    if (not network.is_private or destination not in network or destination.is_loopback
            or destination.is_link_local or type(port) is not int or not 1 <= port <= 65535):
        raise RealmBlocked("U1 database destination invalid")
    dsn = env.get("DOCSURI_U1_AUTHORITY_DSN")
    if not dsn:
        raise RealmBlocked("DOCSURI_U1_AUTHORITY_DSN is required; no default DSN is used")
    try:
        from psycopg.conninfo import conninfo_to_dict
        parameters = conninfo_to_dict(dsn)
    except ImportError as exc:
        raise RealmBlocked("U1 real PostgreSQL driver is required") from exc
    except Exception as exc:
        raise RealmBlocked("U1 database connection identity invalid") from exc
    if (parameters.get("host") != host or parameters.get("dbname") != database
            or parameters.get("user") != role or parameters.get("port", "5432") != str(port)
            or not set(parameters) <= {"host", "dbname", "user", "port", "password", "sslmode"}):
        raise RealmBlocked("U1 DSN does not match the trusted authority realm")
    selected = tuple(sorted((key, value) for key, value in env.items()
                            if key.startswith("DOCSURI_U1_")))
    return AuthorityRealm(manifest["realm_id"], host, str(destination), port, database, role,
                          env["DOCSURI_U1_TEST_REALM_SHA256"], dsn, purge["database"],
                          binding["source_sha256"], binding["launcher_sha256"],
                          binding["rules_sha256"],
                          receipt["valid_until"], authority["connection_limit"], selected)


_IDENTITY_QUERY = """
SELECT current_database(), current_user, inet_server_addr()::text, inet_server_port(),
       (SELECT realm_id FROM public.u1_test_realm WHERE singleton = TRUE),
       r.rolsuper, r.rolcreatedb, r.rolcreaterole,
       (SELECT source_sha256 FROM public.u1_test_realm WHERE singleton = TRUE),
       (SELECT launcher_sha256 FROM public.u1_test_realm WHERE singleton = TRUE),
       (SELECT rules_sha256 FROM public.u1_test_realm WHERE singleton = TRUE),
       (SELECT valid_until FROM public.u1_test_realm WHERE singleton = TRUE),
       (SELECT purpose FROM public.u1_test_realm WHERE singleton = TRUE)
FROM pg_roles r WHERE r.rolname = current_user
"""

_PRIVILEGE_QUERY = """
SELECT r.rolbypassrls, r.rolreplication,
       EXISTS (SELECT 1 FROM pg_auth_members WHERE member = r.oid),
       has_table_privilege(current_user, 'public.u1_test_realm', 'SELECT'),
       has_table_privilege(current_user, 'public.u1_test_realm',
                          'INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER'),
       has_database_privilege(current_user, 'postgres', 'CONNECT'),
       has_database_privilege(current_user, 'template1', 'CONNECT'),
       has_database_privilege(current_user, %s, 'CONNECT'),
       (SELECT datdba = r.oid FROM pg_database WHERE datname = current_database()),
       (SELECT tableowner = current_user FROM pg_tables
        WHERE schemaname = 'public' AND tablename = 'u1_test_realm'), r.rolconnlimit
FROM pg_roles r WHERE r.rolname = current_user
"""


def _check_identity(connection, realm: AuthorityRealm) -> None:
    row = connection.execute(_IDENTITY_QUERY).fetchone()
    expected = (realm.database, realm.role, realm.address, realm.port, realm.realm_id,
                 False, False, False, realm.source_digest, realm.launcher_digest,
                 realm.rules_digest,
                 rfc3339_instant(realm.valid_until), "authority")
    if row != expected:
        raise RealmBlocked(
            "U1 database marker/server/role identity mismatch; no mutation permitted"
        )
    privileges = connection.execute(_PRIVILEGE_QUERY, (realm.purge_database,)).fetchone()
    if privileges != (False, False, False, True, False, False, False, False, False, False,
                      realm.connection_limit):
        raise RealmBlocked("U1 database/marker/role privileges invalid; no mutation permitted")


def open_authority_connection(realm: AuthorityRealm):
    """No DDL/delete connection until a separate read-only connection passes."""
    realm.check_current()
    try:
        import psycopg
    except ImportError as exc:
        raise RealmBlocked("U1 real PostgreSQL driver is required") from exc
    readonly = None
    writable = None
    try:
        readonly = psycopg.connect(
            realm.dsn, autocommit=True, connect_timeout=3,
            options="-c default_transaction_read_only=on -c statement_timeout=3000",
        )
        if readonly.execute("SHOW transaction_read_only").fetchone() != ("on",):
            raise RealmBlocked("U1 initial identity connection must be read-only")
        _check_identity(readonly, realm)
        readonly.close()
        readonly = None
        writable = psycopg.connect(
            realm.dsn, autocommit=True, connect_timeout=3,
            options="-c statement_timeout=5000 -c lock_timeout=3000",
        )
        # Rebinding/connection routing cannot change identity between the probe
        # and the later mutation capability. This is still read-only SQL.
        _check_identity(writable, realm)
        realm.check_current()
        return writable
    except RealmBlocked:
        if writable is not None:
            writable.close()
        raise
    except Exception as exc:
        if writable is not None:
            writable.close()
        raise RealmBlocked(
            "U1 authority connection/preflight failed; no mutation permitted"
        ) from exc
    finally:
        if readonly is not None:
            readonly.close()
