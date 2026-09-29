"""F08 live SQL tests. Only an explicitly configured disposable test database is accepted."""

import os
from contextlib import contextmanager
from urllib.parse import urlsplit

import psycopg
import pytest

from backend.migrations import (
    MigrationBlocked,
    adopt_baseline,
    apply_migrations,
    inspect_migrations,
)
from backend.migrations.registry import registry

DSN = os.environ.get("REM1_TEST_PG_DSN")
pytestmark = pytest.mark.skipif(not DSN, reason="REM1_TEST_PG_DSN disposable database required")


@pytest.fixture
def database():
    parts = urlsplit(DSN)
    assert parts.hostname in {"127.0.0.1", "localhost"}
    assert parts.port != 5432 and parts.path == "/rem1_test"
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute("DROP SCHEMA public CASCADE")
        conn.execute("CREATE SCHEMA public")
    return DSN


class TestOnlyAuthority:
    """Test-owned bootstrap credential. Never shipped as a production authority adapter."""

    @contextmanager
    def guard(self, connection, identity, definition_digest):
        yield


def test_fresh_database_check_is_readonly_and_complete_apply_is_idempotent(database):
    assert inspect_migrations(database).state == "UNINITIALIZED"
    with psycopg.connect(database) as conn:
        assert conn.execute("SELECT to_regclass('public._migrations_v2')").fetchone()[0] is None
    applied = apply_migrations(database, authority=TestOnlyAuthority())
    assert len(applied) == len(registry())
    assert inspect_migrations(database).state == "READY"
    assert apply_migrations(database, authority=TestOnlyAuthority()) == []
    with psycopg.connect(database) as conn:
        for table in (
            "evidence_sessions",
            "evidence_turns",
            "user_glossary",
            "mypage_subscriptions",
        ):
            assert conn.execute("SELECT to_regclass(%s)", (f"public.{table}",)).fetchone()[0]


def test_legacy_history_cannot_be_promoted_by_filename(database):
    spec = registry()[0]
    with psycopg.connect(database) as conn:
        conn.execute("CREATE TABLE _migrations(name text PRIMARY KEY)")
        conn.execute("INSERT INTO _migrations VALUES (%s)", (spec.local_id,))
    assert inspect_migrations(database).state == "NEEDS_RECONCILIATION"
    with pytest.raises(MigrationBlocked, match="RECONCILIATION"):
        apply_migrations(database, authority=TestOnlyAuthority())
    with pytest.raises(MigrationBlocked, match="postconditions"):
        adopt_baseline(
            database,
            identities=(spec.identity,),
            receipt="test-only-review",
            verify_postconditions=lambda conn, spec: False,
            authority=TestOnlyAuthority(),
        )
    with psycopg.connect(database) as conn:
        assert conn.execute("SELECT name FROM _migrations").fetchall() == [(spec.local_id,)]


def test_domain_verified_adoption_stays_adopted_and_preserves_history(database):
    spec = registry()[0]
    with psycopg.connect(database) as conn:
        conn.execute(spec.path.read_text())
        conn.execute("CREATE TABLE _migrations(name text PRIMARY KEY)")
        conn.execute("INSERT INTO _migrations VALUES (%s)", (spec.local_id,))

    def domain_check(conn, definition):
        columns = {
            r[0]
            for r in conn.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema='public' AND table_name='accounts'"
            )
        }
        return (
            definition.identity == spec.identity
            and {"id", "email", "password_hash", "status"} <= columns
        )

    adopt_baseline(
        database,
        identities=(spec.identity,),
        receipt="domain-review-1",
        verify_postconditions=domain_check,
        authority=TestOnlyAuthority(),
    )
    with psycopg.connect(database) as conn:
        assert conn.execute("SELECT assurance FROM _migrations_v2").fetchall() == [
            ("ADOPTED_BASELINE",)
        ]
        assert conn.execute("SELECT name FROM _migrations").fetchall() == [(spec.local_id,)]
    assert inspect_migrations(database).state == "PENDING"


def test_second_writer_is_rejected_by_database_scoped_lock(database):
    with psycopg.connect(database, autocommit=True) as holder:
        holder.execute("SELECT pg_advisory_lock(1380798032, 1)")
        with pytest.raises(MigrationBlocked, match="another"):
            apply_migrations(database, authority=TestOnlyAuthority())
        assert holder.execute("SELECT to_regclass('public._migrations_v2')").fetchone()[0] is None


def test_failed_step_rolls_back_effect_and_ledger(database):
    class FailBeforeThirdStep(TestOnlyAuthority):
        @contextmanager
        def guard(self, connection, identity, definition_digest):
            if identity.startswith("accounts:003"):
                raise PermissionError("revoked")
            yield

    with pytest.raises(PermissionError):
        apply_migrations(database, authority=FailBeforeThirdStep())
    with psycopg.connect(database) as conn:
        assert conn.execute("SELECT count(*) FROM _migrations_v2").fetchone()[0] == 2
        assert (
            conn.execute("SELECT to_regclass('public.password_reset_tokens')").fetchone()[0] is None
        )


def test_fresh_schema_serves_evidence_and_glossary_http(database, monkeypatch):
    from uuid import uuid4

    from docsuri_shared._generated.dtos.evidence_schema import EvidenceAbstainResult
    from docsuri_shared.authz import Principal, UserRole
    from fastapi.testclient import TestClient
    from summarization.adapters.rds_glossary import RdsGlossaryRepository
    from summarization.api.router import build_router

    from backend.app import create_app
    from backend.config import Settings
    from backend.modules.evidence import controller
    from backend.modules.evidence.models import TurnAbstainResult

    apply_migrations(database, authority=TestOnlyAuthority())
    monkeypatch.setenv("EVIDENCE_AGENT_ENABLED", "true")
    principal = Principal(user_id=str(uuid4()), role=UserRole.USER)
    app = create_app(
        Settings(
            env="test", database_url=database.replace("postgresql://", "postgresql+psycopg://")
        )
    )
    app.dependency_overrides[controller.get_principal] = lambda: principal

    class EvidencePort:
        def run(self, ctx, request):
            return TurnAbstainResult(
                outcome=EvidenceAbstainResult(state="abstain", abstainReason="out_of_corpus")
            )

    app.dependency_overrides[controller.get_orchestrator] = lambda: EvidencePort()

    class GlossaryPort:
        def list_glossary_terms(self, owner):
            with psycopg.connect(database) as conn:
                return list(RdsGlossaryRepository(connection=conn).get_user_glossary(owner))

    app.include_router(build_router(GlossaryPort()))

    @app.middleware("http")
    async def test_identity(request, call_next):
        request.state.principal = principal
        return await call_next(request)

    with TestClient(app) as client:
        assert (
            client.post("/api/evidence/turns", json={"topic": "test-only question"}).status_code
            == 200
        )
        response = client.get("/api/glossary")
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "terms": []}
