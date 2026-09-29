"""Independent, root-provisioned host/release policy for capability receipts."""

import grp
import pwd
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field

from ..adapters.nts import ProtectedClock
from ..contracts.codec import canonical, decode, digest
from ..contracts.models import Digest, Ref, Value
from .launchd import REALMS, protected_bytes, protected_chain, role_account
from .receipt import Capability, TrustKey, host_identity

MAX_POLICY_BYTES = 262_144


def tag(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,99}", value):
        raise ValueError("invalid receipt policy identifier")
    return value


def policy_path(profile: str, release: str) -> Path:
    return REALMS[profile] / "receipt-policy" / (tag(release) + ".json")


def keychain_path(profile: str, release: str, key_id: str) -> Path:
    return REALMS[profile] / "sign" / (tag(release) + "--" + tag(key_id) + ".keychain-db")


def output_directory(profile: str, release: str) -> Path:
    return REALMS[profile] / "receipt-public" / tag(release)


class ClockReference(Value):
    frame: str
    writer_uid: Annotated[int, Field(ge=1, le=2**31 - 1)]
    config_digest: Digest

    def clock(self):
        return ProtectedClock(Path(self.frame), writer_uid=self.writer_uid,
                              config_digest=self.config_digest)


class ReceiptSignerReference(Value):
    uid: Annotated[int, Field(ge=1, le=2**31 - 1)]
    gid: Annotated[int, Field(ge=1, le=2**31 - 1)]
    key_id: Ref
    keychain: str
    service: Ref
    account: Ref


class ReceiptScope(Value):
    capability: Capability
    artifact: Digest


class ReceiptPolicy(Value):
    version: Literal[1] = 1
    profile: Literal["test", "production"]
    release: Ref
    host: Ref
    clock: ClockReference
    signer: ReceiptSignerReference
    trust_keys: Annotated[tuple[TrustKey, ...], Field(min_length=1, max_length=16)]
    scopes: Annotated[tuple[ReceiptScope, ...], Field(min_length=1, max_length=5)]
    max_receipt_seconds: Annotated[int, Field(ge=1, le=7 * 86400)] = 86400
    probes: dict = Field(default_factory=dict)

    def validate_bindings(self):
        tag(self.release)
        tag(self.signer.key_id)
        root = REALMS[self.profile]
        if self.clock.frame != str(root / "clock-public/current.json"):
            raise ValueError("clock reference crosses profile")
        expected_path = keychain_path(self.profile, self.release, self.signer.key_id)
        if self.signer.keychain != str(expected_path):
            raise ValueError("signing keychain reference crosses purpose")
        if (self.signer.service != "org.docsuri.rem1." + self.profile + ".receipt-signing"
            or self.signer.account != self.release + "/" + self.signer.key_id):
            raise ValueError("signing item purpose differs")
        if self.signer.uid == self.clock.writer_uid:
            raise ValueError("clock and signer share an identity")
        ids = [key.key_id for key in self.trust_keys]
        caps = [scope.capability for scope in self.scopes]
        if (len(set(ids)) != len(ids) or self.signer.key_id not in ids
            or len(set(caps)) != len(caps)):
            raise ValueError("ambiguous receipt authority")
        for scope in self.scopes:
            if (scope.capability == Capability.NTS_CLOCK
                and scope.artifact != self.clock.config_digest):
                raise ValueError("clock artifact does not match policy")
        allowed = {"keychainRoles", "database", "databaseTls", "nativeCommitGuard",
                   "restoreReceipt"}
        if not set(self.probes) <= allowed:
            raise ValueError("unsupported protected probe reference")
        return self

    def probe_config(self):
        return {**self.probes, "clock": {"frame": self.clock.frame,
                                       "writerUid": self.clock.writer_uid,
                                       "configDigest": self.clock.config_digest}}

    def trust(self):
        return {key.key_id: key for key in self.trust_keys}

    def artifacts(self):
        return {scope.capability: scope.artifact for scope in self.scopes}


def verify_accounts(policy):
    signer = pwd.getpwnam(role_account(policy.profile, "sign"))
    group = grp.getgrnam(role_account(policy.profile, "sign"))
    clock = pwd.getpwnam(role_account(policy.profile, "clock"))
    if (signer.pw_uid, signer.pw_gid, group.gr_gid, clock.pw_uid) != (
        policy.signer.uid, policy.signer.gid, policy.signer.gid, policy.clock.writer_uid,
    ):
        raise PermissionError("receipt policy account binding changed")


@dataclass(frozen=True)
class PolicySnapshot:
    policy: ReceiptPolicy
    digest: str
    path: Path

    def check_current(self):
        protected_chain(self.path)
        if digest(protected_bytes(self.path, limit=MAX_POLICY_BYTES)) != self.digest:
            raise PermissionError("receipt policy changed during operation")
        verify_accounts(self.policy)


def load_policy(profile: str, release: str) -> PolicySnapshot:
    """The caller names a profile/release, never an arbitrary trust or policy file."""
    path = policy_path(profile, release)
    protected_chain(path)
    raw = protected_bytes(path, limit=MAX_POLICY_BYTES)
    policy = ReceiptPolicy.model_validate_json(canonical(decode(raw, max_bytes=MAX_POLICY_BYTES)))
    policy.validate_bindings()
    if (policy.profile, policy.release, policy.host) != (profile, release, host_identity()):
        raise PermissionError("receipt policy host or release mismatch")
    verify_accounts(policy)
    return PolicySnapshot(policy, digest(raw), path)


def trusted_window(clock) -> tuple[int, int]:
    lower, upper = clock()
    if (type(lower) is not int or type(upper) is not int
        or not 0 <= lower <= upper < 2**64 or upper - lower > 2_000_000):
        raise ValueError("invalid authenticated clock window")
    return lower, upper


class ReceiptOperation:
    """An operation cannot cross a policy revision, boot/resume epoch or 30s elapsed cap."""

    def __init__(self, snapshot, clock=None):
        self.snapshot = snapshot
        self.clock = clock if clock is not None else snapshot.policy.clock.clock()
        self.started = self.clock.context()
        self.initial = self.check()

    def check(self):
        self.snapshot.check_current()
        current = self.clock.context()
        if ((current.boot_id, current.resume_id) != (self.started.boot_id, self.started.resume_id)
            or not 0 <= current.continuous_ns - self.started.continuous_ns < 30_000_000_000):
            raise PermissionError("receipt operation clock epoch or deadline changed")
        return trusted_window(self.clock)
