"""Purpose Keychain TLS material with bounded, role-private, connection-scoped plaintext."""

import os
import stat
import subprocess
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import serialization

from ..contracts.codec import decode
from .keychain import KeychainReader, KeyUnavailable


@dataclass(frozen=True)
class TLSReference:
    keychain: Path
    service: str
    account: str

    def __post_init__(self):
        if not self.keychain.is_absolute() or any(
            not isinstance(value, str) or not 0 < len(value.encode()) <= 200 or "\x00" in value
            for value in (self.service, self.account)
        ):
            raise ValueError("invalid purpose keychain reference")


@dataclass(frozen=True)
class TLSMaterial:
    certificate: Path
    private_key: Path
    ca: Path


def host_encryption_enabled():
    try:
        result = subprocess.run(
            ["/usr/bin/fdesetup", "status"], capture_output=True, text=True, timeout=1,
            stdin=subprocess.DEVNULL, env={"PATH": "/usr/bin:/bin", "LANG": "en_US.UTF-8"},
            check=False,
        )
        return result.returncode == 0 and result.stdout.strip() == "FileVault is On."
    except (OSError, subprocess.TimeoutExpired):
        return False


def validate_bundle(raw: bytes):
    try:
        bundle = decode(raw, max_bytes=65_536)
        if not isinstance(bundle, dict) or set(bundle) != {"certificate", "privateKey", "ca"}:
            raise ValueError("TLS bundle fields")
        if any(not isinstance(value, str) or not value for value in bundle.values()):
            raise ValueError("TLS bundle value")
        certificate = x509.load_pem_x509_certificate(bundle["certificate"].encode())
        authority = x509.load_pem_x509_certificate(bundle["ca"].encode())
        key = serialization.load_pem_private_key(bundle["privateKey"].encode(), password=None)
        encoding, form = serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
        if (
            certificate.public_key().public_bytes(encoding, form)
            != key.public_key().public_bytes(encoding, form)
            or not authority.extensions.get_extension_for_class(x509.BasicConstraints).value.ca
        ):
            raise ValueError("TLS key or CA mismatch")
        return bundle
    except Exception:
        raise KeyUnavailable("purpose TLS material invalid") from None


class KeychainTLS:
    def __init__(self, reference: TLSReference, runtime_root: Path, *,
                 reader_factory=KeychainReader, encryption_check=host_encryption_enabled):
        self.reference = reference
        self.runtime_root = runtime_root
        self.reader_factory = reader_factory
        self.encryption_check = encryption_check

    @contextmanager
    def materialize(self):
        folder = None
        names = ("certificate.pem", "private-key.pem", "ca.pem")
        try:
            if self.encryption_check() is not True:
                raise KeyUnavailable("host encryption unavailable")
            owner = self.runtime_root.lstat()
            if (
                not stat.S_ISDIR(owner.st_mode) or owner.st_uid != os.geteuid()
                or stat.S_IMODE(owner.st_mode) != 0o700
            ):
                raise KeyUnavailable("role runtime root unavailable")
            reader = self.reader_factory(self.reference.keychain)
            bundle = validate_bundle(reader.get(self.reference.service, self.reference.account))
            folder = Path(tempfile.mkdtemp(prefix="tls-", dir=self.runtime_root))
            for name, key in zip(names, ("certificate", "privateKey", "ca"), strict=True):
                fd = os.open(folder / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                             0o600)
                with os.fdopen(fd, "wb") as stream:
                    stream.write(bundle[key].encode())
                    stream.flush()
                    os.fsync(stream.fileno())
            del bundle
        except Exception:
            if folder is not None:
                self._cleanup(folder, names)
            raise KeyUnavailable("purpose TLS material unavailable") from None
        try:
            yield TLSMaterial(*(folder / name for name in names))
        finally:
            self._cleanup(folder, names)

    @staticmethod
    def _cleanup(folder, names):
        # Only unlink the three files created in our fresh private directory. No recursive delete.
        try:
            for name in names:
                (folder / name).unlink(missing_ok=True)
            folder.rmdir()
        except OSError:
            raise KeyUnavailable("TLS material cleanup incomplete") from None
