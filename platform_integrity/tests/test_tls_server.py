"""Real loopback TLS test with synthetic certificates; no system Keychain/CA changes."""

import hashlib
import ipaddress
import os
import socket
import ssl
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID


def certificate(tmp_path, name, *, ca_key=None, ca_cert=None, client=False):
    key = ec.generate_private_key(ec.SECP256R1())
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, name)])
    now = datetime.now(UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(ca_cert.subject if ca_cert else subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(days=1))
    )
    cert = cert.add_extension(
        x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False
    )
    cert = cert.add_extension(
        x509.AuthorityKeyIdentifier.from_issuer_public_key((ca_key or key).public_key()),
        critical=False,
    )
    cert = cert.add_extension(
        x509.KeyUsage(
            digital_signature=True,
            content_commitment=False,
            key_encipherment=False,
            data_encipherment=False,
            key_agreement=False,
            key_cert_sign=ca_cert is None,
            crl_sign=ca_cert is None,
            encipher_only=False,
            decipher_only=False,
        ),
        critical=True,
    )
    if ca_cert is None:
        cert = cert.add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
    else:
        cert = cert.add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        cert = cert.add_extension(
            x509.ExtendedKeyUsage(
                [ExtendedKeyUsageOID.CLIENT_AUTH if client else ExtendedKeyUsageOID.SERVER_AUTH]
            ),
            critical=False,
        )
        if not client:
            cert = cert.add_extension(
                x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]),
                critical=False,
            )
    cert = cert.sign(ca_key or key, hashes.SHA256())
    pem, private = tmp_path / f"{name}.pem", tmp_path / f"{name}.key"
    pem.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    private.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    private.chmod(0o600)
    return key, cert, pem, private


def test_mtls_identity_is_from_transport_not_header(tmp_path):
    ca_key, ca_cert, ca, _ = certificate(tmp_path, "test-ca")
    _, _, server, server_key = certificate(tmp_path, "server", ca_key=ca_key, ca_cert=ca_cert)
    _, cert, client, client_key = certificate(
        tmp_path, "client", ca_key=ca_key, ca_cert=ca_cert, client=True
    )
    _, _, other, other_key = certificate(
        tmp_path, "other", ca_key=ca_key, ca_cert=ca_cert, client=True
    )
    fingerprint = hashlib.sha256(cert.public_bytes(serialization.Encoding.DER)).hexdigest()
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    code = """
import sys
from pathlib import Path
from docsuri_platform_integrity.api.server import serve
from docsuri_platform_integrity.api.app import create_app
from docsuri_platform_integrity.application.evidence import EvidenceService
from docsuri_platform_integrity.adapters.authority import CurrentReadAuthority, ReadGrant
from docsuri_platform_integrity.contracts.models import SubjectSnapshot
from docsuri_platform_integrity.contracts.codec import digest
class Reader:
    def healthy(self): return True
    def snapshot(self, subject): return (), ()
clock = lambda: (100, 100)
grant = ReadGrant(sys.argv[5], frozenset({'one'}), 200)
authority = CurrentReadAuthority(
    lambda cert: grant if cert == grant.certificate_fingerprint else None, clock)
d = digest(b'frozen')
subject = SubjectSnapshot(subject='one', artifact=d, incarnation='i1', policy=d)
app = create_app(EvidenceService(Reader(), authority, clock, {'one': (subject, ('schema',))}))
serve(app, certificate=Path(sys.argv[1]), private_key=Path(sys.argv[2]),
      ca=Path(sys.argv[3]), port=int(sys.argv[4]))
"""
    proc = subprocess.Popen(
        [sys.executable, "-c", code, str(server), str(server_key), str(ca), str(port), fingerprint],
        cwd=tmp_path,
        env={"PATH": os.environ.get("PATH", ""), "LANG": "en_US.UTF-8"},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        context = ssl.create_default_context(cafile=str(ca))
        context.load_cert_chain(client, client_key)
        deadline = time.monotonic() + 10
        with httpx.Client(verify=context, timeout=1, trust_env=False) as session:
            while True:
                try:
                    response = session.get(f"https://127.0.0.1:{port}/healthz")
                    break
                except httpx.TransportError:
                    if time.monotonic() > deadline or proc.poll() is not None:
                        raise
                    time.sleep(0.05)
            assert response.status_code == 200
            response = session.get(f"https://127.0.0.1:{port}/internal/v1/evidence/one")
            assert response.status_code == 200
            assert response.json()["verdict"] == "INCOMPLETE"
        unknown = ssl.create_default_context(cafile=str(ca))
        unknown.load_cert_chain(other, other_key)
        with httpx.Client(verify=unknown, timeout=1, trust_env=False) as session:
            response = session.get(
                f"https://127.0.0.1:{port}/internal/v1/evidence/one",
                headers={"X-Client-Cert": fingerprint},
            )
            assert response.status_code == 404
        with httpx.Client(
            verify=ssl.create_default_context(cafile=str(ca)), timeout=1, trust_env=False
        ) as session:
            with pytest.raises(httpx.TransportError):
                session.get(f"https://127.0.0.1:{port}/healthz")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
