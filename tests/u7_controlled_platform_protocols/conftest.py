"""Owned U7 fixtures: the synthetic-local DB, its grants and synthetic targets."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest

from docsuri_ops.platform_control import enums
from docsuri_ops.platform_control.authority import local_actor
from docsuri_ops.platform_control.profile import PlatformProfile
from docsuri_ops.platform_control.store import Store


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


@dataclass
class Harness:
    profile: PlatformProfile
    runtime: Store
    provisioner: Store
    actor: str

    @property
    def environment(self) -> str:
        return f"synthetic-local:{self.profile.run_id}"

    def target(self, name: str | None = None) -> str:
        target = name or f"t-{uuid4().hex[:12]}"
        self.provisioner.provision_target(target)
        return target

    def grant(
        self,
        *,
        target: str,
        operations: list[str] | None = None,
        authority_class: str = enums.CLASS_ROUTINE,
        actor: str | None = None,
    ) -> str:
        authority_id = str(uuid4())
        self.provisioner.provision_authority(
            authority_id=authority_id,
            actor=actor or self.actor,
            scope=[target],
            operations=["platform.file.write"] if operations is None else operations,
            authority_class=authority_class,
            binding={"provisionedBy": self.actor},
        )
        return authority_id

    def evidence(
        self,
        *,
        target: str,
        input_hash: str,
        max_age_seconds: int = 300,
        environment: str | None = None,
        observations: dict | None = None,
    ) -> dict:
        return self.runtime.record_evidence(
            target=target,
            input_hash=input_hash,
            environment=environment or self.environment,
            observations=observations or {"status": "observed"},
            max_age_seconds=max_age_seconds,
        )

    # --- scope-bounded reads (actor + authority are enforced in the store) ---

    def receipt(self, operation_id: str, authority: str) -> dict:
        return self.runtime.read_receipt(self.actor, authority, operation_id)

    def latest(self, target: str, authority: str) -> dict | None:
        return self.runtime.latest_evidence(self.actor, authority, target)

    def unresolved(self, authority: str) -> list[dict]:
        return self.runtime.list_unresolved(self.actor, authority)

    def counts(self, authority: str) -> dict:
        return self.runtime.status_counts(self.actor, authority)


@pytest.fixture(scope="session")
def profile() -> PlatformProfile:
    manifest = os.environ.get("DOCSURI_U7_ENVIRONMENT_FILE")
    if not manifest:
        pytest.skip("no U7 synthetic environment")
    return PlatformProfile.load(Path(manifest))


@pytest.fixture
def harness(profile: PlatformProfile) -> Harness:
    return Harness(
        profile=profile,
        runtime=Store.runtime(profile),
        provisioner=Store.provisioner(profile),
        actor=local_actor(),
    )


@pytest.fixture
def migrate(profile: PlatformProfile):
    """A one-shot migration-authority connection for fixture-only state changes.

    Deliberately not available to the runtime/provisioner roles: only the owned
    disposable fixture's migration credential can backdate a lease or read raw
    rows, so production grants stay strict.
    """
    credentials = json.loads((profile.root / "migration-credentials.json").read_text())
    conn = psycopg.connect(
        host="127.0.0.1",
        port=profile.database_port,
        dbname=profile.database_name,
        user="postgres",
        password=credentials["databaseAdminPassword"],
        connect_timeout=3,
    )
    try:
        yield conn
    finally:
        conn.close()
