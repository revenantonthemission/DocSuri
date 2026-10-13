"""Bounded transactional data access for U7 through the guarded functions.

Nothing here issues direct DML against a protected table: every write and read
goes through a ``SECURITY DEFINER`` guard function so a role cannot widen its
own authority. The effect never runs inside a transaction this module holds
open; ``begin_operation`` and ``settle_operation`` are separate commits.
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

import psycopg

from . import PROVISIONER_ROLE, RUNTIME_ROLE, SCHEMA
from .errors import DEPENDENCY_UNAVAILABLE, ControlError, code_for_sqlstate
from .profile import PlatformProfile


@dataclass(frozen=True)
class DatabaseTarget:
    host: str
    port: int
    dbname: str


class Store:
    """One role-scoped connection factory over the ``PlatformControl`` schema."""

    def __init__(
        self,
        target: DatabaseTarget,
        *,
        role: str,
        password: str,
        connect_timeout: int = 3,
        statement_timeout_ms: int = 5000,
    ) -> None:
        if role not in (RUNTIME_ROLE, PROVISIONER_ROLE):
            raise ValueError("unexpected U7 execution role")
        self.target = target
        self.role = role
        self._password = password
        self._connect_timeout = connect_timeout
        self._options = (
            f"-c statement_timeout={statement_timeout_ms} -c search_path=pg_catalog"
        )

    @classmethod
    def runtime(cls, profile: PlatformProfile) -> Store:
        credentials = profile.runtime_credentials()
        return cls(
            DatabaseTarget("127.0.0.1", profile.database_port, profile.database_name),
            role=RUNTIME_ROLE,
            password=credentials["password"],
        )

    @classmethod
    def provisioner(cls, profile: PlatformProfile) -> Store:
        credentials = profile.provisioner_credentials()
        return cls(
            DatabaseTarget("127.0.0.1", profile.database_port, profile.database_name),
            role=PROVISIONER_ROLE,
            password=credentials["password"],
        )

    @contextlib.contextmanager
    def connection(self, *, autocommit: bool = False) -> Iterator[psycopg.Connection]:
        try:
            conn = psycopg.connect(
                host=self.target.host,
                port=self.target.port,
                dbname=self.target.dbname,
                user=self.role,
                password=self._password,
                connect_timeout=self._connect_timeout,
                options=self._options,
                autocommit=autocommit,
            )
        except psycopg.Error as exc:  # connection refused / auth / no DB
            raise ControlError(
                DEPENDENCY_UNAVAILABLE,
                "guarded store is unavailable",
                retryable=True,
                details={"messageKey": "store-unavailable"},
            ) from exc
        try:
            yield conn
        finally:
            conn.close()

    @staticmethod
    def call(conn: psycopg.Connection, function: str, params: tuple[Any, ...]) -> Any:
        """Invoke one guarded function and map a database refusal to ControlError."""
        placeholders = ", ".join(["%s"] * len(params))
        sql = f"SELECT {SCHEMA}.{function}({placeholders})"
        try:
            row = conn.execute(sql, params).fetchone()
        except psycopg.Error as exc:
            raise ControlError(
                code_for_sqlstate(getattr(exc, "sqlstate", None)),
                f"guarded call {function} refused",
                details={"messageKey": function},
            ) from exc
        return row[0] if row else None

    def call_committed(self, function: str, params: tuple[Any, ...]) -> Any:
        with self.connection() as conn:
            value = self.call(conn, function, params)
            conn.commit()
            return value

    # --- provisioner surface -------------------------------------------------

    def provision_authority(
        self,
        *,
        authority_id: str,
        actor: str,
        scope: list[str],
        operations: list[str],
        authority_class: str,
        binding: dict[str, Any],
    ) -> dict[str, Any]:
        return self.call_committed(
            "provision_authority",
            (
                authority_id,
                actor,
                psycopg.types.json.Jsonb(scope),
                psycopg.types.json.Jsonb(operations),
                authority_class,
                psycopg.types.json.Jsonb(binding),
            ),
        )

    def revoke_authority(self, authority_id: str) -> dict[str, Any]:
        return self.call_committed("revoke_authority", (authority_id,))

    def provision_target(self, target_id: str) -> dict[str, Any]:
        return self.call_committed("provision_target", (target_id,))

    def read_authority(self, authority_id: str) -> dict[str, Any]:
        return self.call_committed("read_authority", (authority_id,))

    # --- runtime surface -----------------------------------------------------

    def record_evidence(
        self,
        *,
        target: str,
        input_hash: str,
        environment: str,
        observations: dict[str, Any],
        max_age_seconds: int,
    ) -> dict[str, Any]:
        return self.call_committed(
            "record_evidence",
            (
                target,
                input_hash,
                environment,
                psycopg.types.json.Jsonb(observations),
                max_age_seconds,
            ),
        )

    def latest_evidence(self, actor: str, authority_id: str, target: str) -> dict[str, Any] | None:
        """Target-scope bounded in the store layer: the guard runs inside the function."""
        return self.call_committed("latest_evidence", (actor, authority_id, target))

    def begin_operation(
        self,
        *,
        actor: str,
        authority_id: str,
        operation: str,
        target: str,
        input_hash: str,
        environment: str,
        evidence_id: str,
        generation: int,
        idempotency_key: str,
        effect_reference: str,
    ) -> dict[str, Any]:
        return self.call_committed(
            "begin_operation",
            (
                actor,
                authority_id,
                operation,
                target,
                input_hash,
                environment,
                evidence_id,
                generation,
                idempotency_key,
                effect_reference,
            ),
        )

    def mark_executing(self, operation_id: str) -> dict[str, Any]:
        return self.call_committed("mark_executing", (operation_id,))

    def settle_operation(
        self,
        *,
        operation_id: str,
        outcome: str,
        disposition: str,
        effect_refs: list[str],
    ) -> dict[str, Any]:
        return self.call_committed(
            "settle_operation",
            (
                operation_id,
                outcome,
                disposition,
                psycopg.types.json.Jsonb(effect_refs),
            ),
        )

    def promote_in_flight(self) -> int:
        return self.call_committed("promote_in_flight", ())

    def reconcile_receipt(
        self,
        *,
        operation_id: str,
        applied: bool,
        evidence: list[str],
    ) -> dict[str, Any]:
        return self.call_committed(
            "reconcile_receipt",
            (operation_id, applied, psycopg.types.json.Jsonb(evidence)),
        )

    def read_receipt(
        self, actor: str, authority_id: str, operation_id: str
    ) -> dict[str, Any]:
        return self.call_committed("read_receipt", (actor, authority_id, operation_id))

    def list_unresolved(self, actor: str, authority_id: str) -> list[dict[str, Any]]:
        return self.call_committed("list_unresolved", (actor, authority_id)) or []

    def status_counts(self, actor: str, authority_id: str) -> dict[str, Any]:
        return self.call_committed("status_counts", (actor, authority_id)) or {}

    def supervisor_summary(self) -> dict[str, Any]:
        """Privileged local supervision summary (provisioner role only)."""
        return self.call_committed("supervisor_summary", ()) or {}
