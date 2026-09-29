"""Role-scoped Ed25519 signing from a purpose Keychain; no private-key file fallback."""

import os
import stat
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from ..deployment.launchd import REALMS, kernel_groups
from ..deployment.receipt import issue
from .credentials import host_encryption_enabled
from .keychain import KeychainReader, KeyUnavailable


def require_signer_role(policy):
    identity = policy.signer
    if ((os.getuid(), os.geteuid(), os.getgid(), os.getegid()) != (
        identity.uid, identity.uid, identity.gid, identity.gid,
    ) or set(kernel_groups()) - {identity.gid}):
        raise PermissionError("receipt signer role boundary not established")


def verify_keychain_path(policy):
    path = Path(policy.signer.keychain)
    role_root = REALMS[policy.profile] / "sign"
    path.relative_to(role_root)
    for parent in path.parents:
        info = parent.lstat()
        if (not stat.S_ISDIR(info.st_mode) or info.st_uid not in {0, policy.signer.uid}
            or info.st_mode & 0o022):
            raise KeyUnavailable("signing keychain ancestor is unprotected")
    info = path.lstat()
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != policy.signer.uid
        or stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1):
        raise KeyUnavailable("signing keychain is unprotected")


class KeychainReceiptSigner:
    def __init__(self, policy, *, reader_factory=KeychainReader,
                 encryption_check=host_encryption_enabled):
        self.policy = policy
        self.reader_factory = reader_factory
        self.encryption_check = encryption_check

    def sign(self, receipt, *, lower, upper):
        require_signer_role(self.policy)
        verify_keychain_path(self.policy)
        if self.encryption_check() is not True:
            raise KeyUnavailable("host encryption unavailable")
        reference = self.policy.signer
        trust = self.policy.trust()[reference.key_id]
        if (type(lower) is not int or type(upper) is not int
            or not 0 <= lower <= upper < 2**64 or upper - lower > 2_000_000
            or trust.revoked or not trust.validity.contains(lower, upper)
            or receipt.host != self.policy.host or receipt.release != self.policy.release
            or self.policy.artifacts().get(receipt.capability) != receipt.artifact
            or not receipt.validity.contains(lower, upper)
            or int(receipt.validity.valid_until) - int(receipt.validity.valid_from)
            > self.policy.max_receipt_seconds * 1_000_000
            or int(receipt.validity.valid_from) < int(trust.validity.valid_from)
            or int(receipt.validity.valid_until) > int(trust.validity.valid_until)):
            raise PermissionError("receipt signing authority is unavailable")
        try:
            raw = self.reader_factory(Path(reference.keychain)).get(
                reference.service, reference.account)
            key = Ed25519PrivateKey.from_private_bytes(raw)
            if key.public_key().public_bytes_raw() != trust.key().public_bytes_raw():
                raise ValueError("public key mismatch")
            envelope = issue(receipt, key_id=reference.key_id, key=key)
        except Exception as error:
            # A bare reason is indistinguishable between a locked keychain, an ACL that
            # refuses the interpreter, and a key that does not match the policy's trust key.
            # Those need different operator actions, so the underlying failure is named and
            # chained rather than discarded.
            raise KeyUnavailable(
                f"purpose signing key unavailable: {type(error).__name__}: {error}"
            ) from error
        finally:
            raw = key = None
        return envelope
