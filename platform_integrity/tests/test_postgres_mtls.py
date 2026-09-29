"""Actual loopback TLS/certificate login in the disposable container; never a production DSN."""

import ipaddress
import os
import subprocess
import time
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit

import psycopg
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID
from test_tls_server import certificate

from docsuri_platform_integrity.adapters.credentials import TLSMaterial
from docsuri_platform_integrity.adapters.postgres_tls import PostgresTarget, PostgresTLS

DSN = os.environ.get("REM1_TEST_PG_DSN")
CONTAINER = os.environ.get("REM1_TEST_CONTAINER")
pytestmark = pytest.mark.skipif(not DSN or not CONTAINER, reason="isolated PG container required")

DATA = "/var/lib/postgresql/data"
HBA = f"{DATA}/pg_hba.conf"
SETTINGS = (("ssl", "on"), ("ssl_cert_file", "/tmp/rem1-server.pem"),
            ("ssl_key_file", "/tmp/rem1-server.key"), ("ssl_ca_file", "/tmp/rem1-ca.pem"))


def docker(*args):
    return subprocess.run(["docker", *args], check=True, capture_output=True, timeout=30)


def wait_ready(timeout=30.0):
    """The entrypoint rewrites HBA on start, so readiness is polled instead of assumed."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        probe = subprocess.run(
            ["docker", "exec", CONTAINER, "pg_isready", "-U", "rem1_test", "-d", "rem1_test"],
            capture_output=True, timeout=10)
        if probe.returncode == 0:
            return
        time.sleep(0.2)
    raise AssertionError("disposable PostgreSQL did not become ready")


def install_hba(source, address):
    """Restart first: the image entrypoint regenerates pg_hba.conf on every start."""
    docker("restart", CONTAINER)
    wait_ready()
    docker("cp", str(source), f"{CONTAINER}:{HBA}")
    docker("exec", "--user", "root", CONTAINER, "chown", "postgres:postgres", HBA)
    docker("exec", "--user", "root", CONTAINER, "chmod", "600", HBA)


def apply_settings(conn, values):
    for name, value in values:
        conn.execute(psycopg.sql.SQL("ALTER SYSTEM SET {} = {}").format(
            psycopg.sql.Identifier(name), psycopg.sql.Literal(value)))


@pytest.fixture
def tls_database(tmp_path):
    parsed = urlsplit(DSN)
    assert parsed.hostname == "127.0.0.1" and parsed.port == 15439 and parsed.path == "/rem1_test"
    assert CONTAINER == "rem1-test-pg-20260924"
    wait_ready()
    ca_key, ca_cert, ca, _ = certificate(tmp_path, "pg-ca")
    key = ec.generate_private_key(ec.SECP256R1())
    now = datetime.now(UTC)
    leaf = (x509.CertificateBuilder()
            .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")]))
            .issuer_name(ca_cert.subject).public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(minutes=1)).not_valid_after(now + timedelta(days=1))
            .add_extension(x509.SubjectAlternativeName([x509.DNSName("localhost")]), False)
            .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), False)
            .sign(ca_key, hashes.SHA256()))
    server, server_key = tmp_path / "pg-server.pem", tmp_path / "pg-server.key"
    server.write_bytes(leaf.public_bytes(serialization.Encoding.PEM))
    server_key.write_bytes(key.private_bytes(serialization.Encoding.PEM,
                           serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    _, _, client, client_key = certificate(tmp_path, "r1_tls_probe", ca_key=ca_key,
                                          ca_cert=ca_cert, client=True)
    for source, target in ((ca, "ca.pem"), (server, "server.pem"), (server_key, "server.key")):
        docker("cp", str(source), f"{CONTAINER}:/tmp/rem1-{target}")
    server_key_path = "/tmp/rem1-server.key"
    docker("exec", "--user", "root", CONTAINER, "chown", "postgres:postgres", server_key_path)
    docker("exec", "--user", "root", CONTAINER, "chmod", "600", server_key_path)

    hba = tmp_path / "pg_hba.conf"
    with psycopg.connect(DSN, autocommit=True) as conn:
        if conn.execute("SELECT 1 FROM pg_roles WHERE rolname='r1_tls_probe'").fetchone() is None:
            conn.execute("CREATE ROLE r1_tls_probe LOGIN")
        original = conn.execute("SELECT pg_read_file('pg_hba.conf')").fetchone()[0]
        address = ipaddress.ip_address(conn.execute("SELECT inet_client_addr()").fetchone()[0])
        mask = 32 if address.version == 4 else 128
        # HBA rules match in order; the image-wide scram rule cannot precede ours.
        marker = "host all all all scram-sha-256"
        lines = [line for line in original.splitlines() if "r1_tls_probe" not in line]
        if marker not in lines:
            pytest.fail("expected disposable image HBA marker")
        lines.insert(lines.index(marker),
                     f"hostssl rem1_test r1_tls_probe {address}/{mask} cert clientname=CN")
        hba.write_text("\n".join(lines) + "\n")
        apply_settings(conn, SETTINGS)

    install_hba(hba, address)
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute("SELECT pg_reload_conf()")
        assert "hostssl rem1_test r1_tls_probe" in conn.execute(
            "SELECT pg_read_file('pg_hba.conf')").fetchone()[0]
        assert conn.execute("SHOW ssl").fetchone()[0] == "on"

    class Secrets:
        @contextmanager
        def materialize(self):
            yield TLSMaterial(client, client_key, ca)

    try:
        yield PostgresTLS(PostgresTarget(database="rem1_test", user="r1_tls_probe", port=15439),
                          Secrets()), ca
    finally:
        hba.write_text(original)
        with psycopg.connect(DSN, autocommit=True) as conn:
            for name, _ in SETTINGS:
                conn.execute(psycopg.sql.SQL("ALTER SYSTEM RESET {}").format(
                    psycopg.sql.Identifier(name)))
        install_hba(hba, address)


def test_verify_full_client_certificate_login_and_wrong_ca_denial(tls_database, tmp_path):
    transport, ca = tls_database
    with transport.connect() as connection:
        assert connection.pgconn.ssl_in_use
        assert connection.execute("SELECT session_user").fetchone()[0] == "r1_tls_probe"
        with pytest.raises(psycopg.errors.ReadOnlySqlTransaction):
            connection.execute("CREATE TEMP TABLE forbidden_write(id int)")
    _, _, wrong_ca, _ = certificate(tmp_path, "wrong-ca")
    ca.write_bytes(wrong_ca.read_bytes())
    with pytest.raises(psycopg.OperationalError) as denied:
        with transport.connect():
            pytest.fail("untrusted database certificate accepted")
    assert "certificate" in str(denied.value).lower()
