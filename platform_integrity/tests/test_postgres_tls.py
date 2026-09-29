from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from docsuri_platform_integrity.adapters.credentials import TLSMaterial
from docsuri_platform_integrity.adapters.postgres_tls import PostgresTarget, PostgresTLS


class Connection:
    def __init__(self, user="r1_reader"):
        self.pgconn = SimpleNamespace(ssl_in_use=True)
        self.user = user
        self.closed = False
        self.rolled_back = False
        self.flags = (False, False, False, False, False)

    def execute(self, query, params=()):
        assert "pg_roles" in query
        return SimpleNamespace(fetchone=lambda: (self.user, *self.flags))

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


def test_verified_tls_has_explicit_role_and_no_password_fallback(tmp_path, monkeypatch):
    import psycopg

    material = TLSMaterial(tmp_path / "cert", tmp_path / "key", tmp_path / "ca")
    lifecycle, parameters = [], []
    connection = Connection()

    class Secrets:
        @contextmanager
        def materialize(self):
            lifecycle.append("materialized")
            yield material
            lifecycle.append("removed")

    def connect(**kwargs):
        parameters.append(kwargs)
        assert lifecycle == ["materialized"]
        return connection

    monkeypatch.setattr(psycopg, "connect", connect)
    target = PostgresTarget(database="rem1_test", user="r1_reader", port=15439)
    with PostgresTLS(target, Secrets()).connect() as conn:
        assert lifecycle == ["materialized", "removed"]
        assert conn.rolled_back and not conn.closed
    assert connection.closed
    assert parameters[0]["sslmode"] == "verify-full"
    assert parameters[0]["host"] == "localhost" and parameters[0]["hostaddr"] == "127.0.0.1"
    assert parameters[0]["passfile"] == "/dev/null" and "password" not in parameters[0]


def test_inherited_libpq_environment_is_rejected_before_secrets(monkeypatch):
    monkeypatch.setenv("PGSERVICE", "unexpected")
    target = PostgresTarget(database="rem1_test", user="r1_reader", port=15439)
    with pytest.raises(PermissionError):
        with PostgresTLS(target, None).connect():
            pytest.fail("inherited database service accepted")


@pytest.mark.parametrize("changes", [{"database": "db; SQL"}, {"user": "postgres"}, {"port": 0}])
def test_unsafe_or_owner_connection_targets_are_rejected(changes):
    with pytest.raises(ValueError):
        PostgresTarget(**({"database": "rem1_test", "user": "r1_reader", "port": 15439} | changes))


@pytest.mark.parametrize("fault", [None, "tls", "role", "privilege"])
def test_raw_physical_connection_has_explicit_ownership_and_fail_closed_identity(
    tmp_path, monkeypatch, fault,
):
    import psycopg

    connection, options, lifecycle = Connection(), [], []
    if fault == "tls":
        connection.pgconn.ssl_in_use = False
    elif fault == "role":
        connection.user = "r1_other"
    elif fault == "privilege":
        connection.flags = (True, False, False, False, False)

    class Secrets:
        @contextmanager
        def materialize(self):
            lifecycle.append("materialized")
            yield TLSMaterial(tmp_path / "cert", tmp_path / "key", tmp_path / "ca")
            lifecycle.append("removed")

    def connect(**kwargs):
        options.append(kwargs)
        return connection

    monkeypatch.setattr(psycopg, "connect", connect)
    transport = PostgresTLS(PostgresTarget(database="rem1_test", user="r1_reader", port=15439),
                            Secrets())
    if fault:
        with pytest.raises(PermissionError):
            transport.open(readonly=False, autocommit=True)
        assert connection.closed
    else:
        opened = transport.open(readonly=False, autocommit=True)
        assert opened is connection and not connection.closed
        opened.close()
    assert lifecycle == ["materialized", "removed"]
    assert options[0]["autocommit"] is True
    assert "synchronous_commit=on" in options[0]["options"]
