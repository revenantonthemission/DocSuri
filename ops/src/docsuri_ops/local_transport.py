"""Owned short-lived HTTPS binding; no machine/browser trust-store mutation."""

from __future__ import annotations

import base64
import fcntl
import hashlib
import ipaddress
import json
import os
import stat
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from backend.local_profile import LocalProfile, private_bytes
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID


@dataclass(frozen=True)
class LocalTransport:
    certificate: Path
    key: Path
    certificate_sha256: str
    spki_sha256: str


def _public_bytes(key) -> bytes:
    return key.public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
    )


def _transport_prefix(profile: LocalProfile) -> str:
    """Map only explicitly provisioned local HTTPS realms."""
    bindings = {
        ("journey", "https://127.0.0.1:18039", "docsuri_u1_journey"): "journey-tls",
        ("account-controls", "https://127.0.0.1:18049", "docsuri_u2"): "account-controls-tls",
        ("corpus-maintenance", "https://127.0.0.1:18059", "docsuri_u3"): "corpus-maintenance-tls",
        ("research-workspace", "https://127.0.0.1:18079", "docsuri_u4"): "research-workspace-tls",
        ("topics-digests", "https://127.0.0.1:18089", "docsuri_u5"): "topics-digests-tls",
    }
    prefix = bindings.get((profile.realm, profile.origin, profile.database_name))
    if prefix is None:
        raise ValueError("HTTPS transport requires an explicit owned realm binding")
    return prefix


def inspect_transport(profile: LocalProfile) -> LocalTransport:
    prefix = _transport_prefix(profile)
    certificate_path = profile.root / f"{prefix}.crt"
    key_path = profile.root / f"{prefix}.key"
    for path in (certificate_path, key_path, profile.root / f"{prefix}.json"):
        if path.lstat().st_nlink != 1:
            raise ValueError("transport material has aliased custody")
    certificate_raw = private_bytes(certificate_path, maximum=8192)
    key_raw = private_bytes(key_path, maximum=8192)
    record = json.loads(private_bytes(profile.root / f"{prefix}.json", maximum=4096))
    certificate = x509.load_pem_x509_certificate(certificate_raw)
    key = serialization.load_pem_private_key(key_raw, password=None)
    public = _public_bytes(certificate.public_key())
    now = datetime.now(UTC)
    expected = {
        "runId": profile.run_id,
        "database": profile.database_name,
        "origin": profile.origin,
        "certificateSha256": certificate.fingerprint(hashes.SHA256()).hex(),
        "spkiSha256": base64.b64encode(hashlib.sha256(public).digest()).decode(),
        "expiresAt": int(profile.expires_at),
    }
    if record != expected or _public_bytes(key.public_key()) != public:
        raise ValueError("transport manifest or key binding differs")
    if (
        not isinstance(key, ec.EllipticCurvePrivateKey)
        or not isinstance(key.curve, ec.SECP256R1)
        or certificate.subject
        != x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, profile.run_id)])
        or certificate.issuer != certificate.subject
        or not certificate.not_valid_before_utc <= now < certificate.not_valid_after_utc
        or int(certificate.not_valid_after_utc.timestamp()) != int(profile.expires_at)
        or certificate.not_valid_after_utc - certificate.not_valid_before_utc
        > timedelta(hours=24, minutes=1)
        or certificate.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
        != x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address("127.0.0.1"))])
        or certificate.extensions.get_extension_for_class(x509.BasicConstraints).value.ca
        or ExtendedKeyUsageOID.SERVER_AUTH
        not in certificate.extensions.get_extension_for_class(x509.ExtendedKeyUsage).value
    ):
        raise ValueError("transport certificate policy invalid or expired")
    certificate.verify_directly_issued_by(certificate)
    return LocalTransport(
        certificate_path, key_path, expected["certificateSha256"], expected["spkiSha256"]
    )


def _create_private(path: Path, content: bytes):
    if len(content) > 8192:
        raise ValueError("transport material exceeds allocation")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())


def _acknowledge_transport(profile: LocalProfile) -> LocalTransport:
    transport = inspect_transport(profile)
    # A complete retry may follow a crash after file fsync but before directory
    # fsync. Revalidate and persist directory entries before acknowledging it.
    directory = os.open(profile.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)
    return transport


def prepare_transport(profile: LocalProfile) -> LocalTransport:
    prefix = _transport_prefix(profile)
    descriptor = os.open(
        profile.root / f"{prefix}.lock",
        os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK,
        0o600,
    )
    try:
        info = os.fstat(descriptor)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) != 0o600
            or info.st_nlink != 1
        ):
            raise ValueError("transport lock custody differs")
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        paths = [
            profile.root / f"{prefix}.{suffix}" for suffix in ("key", "crt", "json")
        ]
        present = [path.exists() or path.is_symlink() for path in paths]
        if any(present):
            if not all(present):
                raise ValueError("partial transport provisioning requires explicit recovery")
            return _acknowledge_transport(profile)
        now = datetime.now(UTC)
        expiry = datetime.fromtimestamp(profile.expires_at, UTC)
        if not now < expiry <= now + timedelta(hours=24):
            raise ValueError("synthetic transport retention invalid")
        key = ec.generate_private_key(ec.SECP256R1())
        subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, profile.run_id)])
        certificate = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(subject)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(minutes=1))
            .not_valid_after(expiry)
            .add_extension(
                x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]),
                critical=False,
            )
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
            .sign(key, hashes.SHA256())
        )
        public = _public_bytes(key.public_key())
        record = {
            "runId": profile.run_id,
            "database": profile.database_name,
            "origin": profile.origin,
            "certificateSha256": certificate.fingerprint(hashes.SHA256()).hex(),
            "spkiSha256": base64.b64encode(hashlib.sha256(public).digest()).decode(),
            "expiresAt": int(profile.expires_at),
        }
        _create_private(
            paths[0],
            key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            ),
        )
        _create_private(paths[1], certificate.public_bytes(serialization.Encoding.PEM))
        _create_private(paths[2], json.dumps(record, sort_keys=True).encode())
        return _acknowledge_transport(profile)
    finally:
        os.close(descriptor)
