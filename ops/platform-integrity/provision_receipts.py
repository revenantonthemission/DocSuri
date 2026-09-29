"""Root-provisioned receipt signing: purpose Keychain, trusted public key, fixed policy.

One privileged step, and nothing here trusts the caller:

* The NTS capability artifact is read from the installed, root-owned clock deployment
  manifest, never from an argument, so a policy cannot claim a clock that is not deployed.
* The Ed25519 private key is generated in memory, placed in a purpose Keychain owned by the
  signing role with an ACL bound to the named issuer interpreter, and never written to a
  file, argv or log.
* The trust key is the public half of exactly that Keychain item, so a substituted key
  yields receipts that fail verification rather than receipts that pass.
* The policy is written to its fixed root-owned 0444 path; the caller chooses only the
  profile, release, key id, issuer interpreter and receipt duration.
"""

import argparse
import getpass
import grp
import json
import os
import pwd
import stat
import sys
from pathlib import Path, PurePosixPath

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from docsuri_platform_integrity.adapters.keychain_provisioning import NativeKeychain
from docsuri_platform_integrity.contracts.codec import canonical, decode, digest
from docsuri_platform_integrity.contracts.models import ValidityWindow
from docsuri_platform_integrity.deployment.launchd import (
    REALMS,
    LaunchManifest,
    artifact_path,
    role_account,
    validate_manifest,
)
from docsuri_platform_integrity.deployment.receipt import Capability, host_identity, trust_key
from docsuri_platform_integrity.deployment.receipt_policy import (
    ClockReference,
    ReceiptPolicy,
    ReceiptScope,
    ReceiptSignerReference,
    keychain_path,
    output_directory,
    policy_path,
)

MANIFEST_BYTES = 4 * 1024**2
CHRONY_CONFIG = "chrony.conf"


def read_regular(path: Path, limit: int) -> bytes:
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, "rb") as source:
        info = os.fstat(source.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > limit
                or info.st_mode & 0o022):
            raise ValueError("unsafe artifact file")
        data = source.read(limit + 1)
        if len(data) > limit:
            raise ValueError("artifact size limit")
        return data


def clock_config_argument(manifest) -> str:
    """The chrony configuration `chronyd` is actually launched with, taken from the manifest.

    This deliberately does not construct the path from the realm root. A provisioner that
    *assumes* a layout (`releases/<release>/config/chrony.conf`) pins a file that need not be the
    one the clock runs: a deployment that stores it elsewhere would either be rejected while
    healthy, or -- worse, be accepted against a config that chronyd never reads. Reading the `-f`
    argument out of the frozen manifest instead binds the policy to the config that is genuinely
    in force, so a substituted config cannot pass as the deployed one.

    The property this preserves is "uniquely pinned": exactly one chronyd entry, exactly one `-f`
    within it, the argument must be the chrony config by name, and `artifact_path` already rejects
    non-canonical paths, `..`, symlinked traversal, and anything outside this release's roots.
    """
    candidates = []
    for entry in manifest.entries:
        argv = list(entry.argv)
        if not any(argument.endswith("/chronyd") for argument in argv[:1]):
            continue
        flags = argv.count("-f")
        if flags == 0:
            # chronyd would read a configuration this manifest never mentions, so there is
            # nothing to pin and nothing to sign for.
            continue
        if flags > 1 or argv.index("-f") + 1 >= len(argv):
            # More than one `-f`, or a trailing flag with no value: the configuration actually
            # in force is ambiguous.
            raise ValueError("chronyd configuration argument is ambiguous")
        candidates.append(argv[argv.index("-f") + 1])
    if len(candidates) != 1:
        raise ValueError("installed clock configuration is not uniquely pinned")
    config = candidates[0]
    if PurePosixPath(config).name != CHRONY_CONFIG:
        raise ValueError("chronyd is not launched with the expected configuration")
    return config


def installed_clock(profile: str, release: str, *, owner: int = 0):
    """Bind the policy to the deployed clock, taking every value from installed state.

    `owner` is the uid the realm and its manifest must belong to. It is a parameter only so
    the unprivileged suite can exercise this function against a fixture; production callers
    keep the default root requirement.
    """
    root = REALMS[profile]
    if root.lstat().st_uid != owner:
        raise PermissionError("realm is not root-owned")
    manifest = LaunchManifest.model_validate_json(
        canonical(decode(read_regular(root / "deployment.json", MANIFEST_BYTES),
                         max_bytes=MANIFEST_BYTES)))
    validate_manifest(manifest)
    if (manifest.profile, manifest.release) != (profile, release):
        raise ValueError("installed clock is a different profile or release")
    configuration = dict(manifest.artifacts)
    expected = clock_config_argument(manifest)
    if expected not in configuration:
        raise ValueError("installed clock configuration is not uniquely pinned")
    config_digest = configuration[expected]
    # The installed bytes must still hash to what the frozen manifest recorded.
    if digest(read_regular(artifact_path(manifest, expected), 4 * 1024**2)) != config_digest:
        raise ValueError("installed clock configuration does not match its manifest")
    return ClockReference(frame=str(root / "clock-public/current.json"),
                          writer_uid=manifest.entries[0].uid, config_digest=config_digest)


def ensure_directory(path: Path, *, uid: int, gid: int, mode: int) -> None:
    if path.exists():
        info = path.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != uid:
            raise PermissionError("existing directory has another owner")
    else:
        os.mkdir(path, mode)
    os.chown(path, uid, gid)
    os.chmod(path, mode)


def sign_identity(profile: str):
    account = role_account(profile, "sign")
    principal = pwd.getpwnam(account)
    group = grp.getgrnam(account)
    return principal.pw_uid, group.gr_gid


def provision(profile: str, release: str, key_id: str, issuer: Path, seconds: int,
              password: str, capabilities):
    if os.geteuid() != 0 or sys.platform != "darwin":
        raise PermissionError("root on macOS is required")
    uid, gid = sign_identity(profile)
    clock = installed_clock(profile, release)
    if clock.writer_uid == uid:
        raise ValueError("clock and signer identities must differ")
    root = REALMS[profile]
    ensure_directory(root / "sign", uid=uid, gid=gid, mode=0o700)
    ensure_directory(root / "receipt-policy", uid=0, gid=0, mode=0o755)
    ensure_directory(root / "receipt-public", uid=0, gid=0, mode=0o755)
    # The public directory is signer-owned so the signer can stage and replace receipts,
    # while every ancestor above it stays root-owned and unwritable by anyone else.
    ensure_directory(output_directory(profile, release), uid=uid, gid=gid, mode=0o755)

    service = "org.docsuri.rem1." + profile + ".receipt-signing"
    account = release + "/" + key_id
    path = keychain_path(profile, release, key_id)
    if path.exists() or path.is_symlink():
        raise FileExistsError("signing keychain already exists; rotate explicitly")
    private = Ed25519PrivateKey.generate()
    # The public half is the only part that leaves this process; the private half goes
    # straight into the Keychain and is dropped before anything else can observe it.
    public = private.public_key()
    try:
        NativeKeychain().create(path, password, service, account,
                                private.private_bytes_raw(), issuer, owner=uid)
    finally:
        private = None
    os.chown(path, uid, gid)
    os.chmod(path, 0o600)

    # The trust window is anchored to the deployed clock, never to this host's wall time.
    lower, upper = clock.clock()()
    moment = lower
    trust_days = 365
    trust = trust_key(key_id, public, validity=ValidityWindow(
        valid_from=str(moment - 86_400_000_000),
        valid_until=str(moment + trust_days * 86_400_000_000)))
    policy = ReceiptPolicy(
        profile=profile, release=release, host=host_identity(),
        clock=clock,
        signer=ReceiptSignerReference(uid=uid, gid=gid, key_id=key_id, keychain=str(path),
                                      service=service, account=account),
        trust_keys=(trust,),
        scopes=tuple(ReceiptScope(capability=capability, artifact=clock.config_digest)
                     for capability in capabilities),
        max_receipt_seconds=seconds,
    ).validate_bindings()
    target = policy_path(profile, release)
    if target.exists() or target.is_symlink():
        raise FileExistsError("receipt policy already exists; rotate explicitly")
    staged = target.with_name("." + target.name + ".new")
    descriptor = os.open(staged, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o444)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(canonical(policy.model_dump(mode="json")))
        stream.flush()
        os.fsync(stream.fileno())
    os.rename(staged, target)
    os.chown(target, 0, 0)
    os.chmod(target, 0o444)
    return {
        "state": "PROVISIONED", "profile": profile, "release": release, "keyId": key_id,
        "policy": str(target), "policySha256": digest(canonical(policy.model_dump(mode="json"))),
        "keychain": str(path), "output": str(output_directory(profile, release)),
        "signerUid": uid, "clockWriterUid": clock.writer_uid,
        "publicKeySha256": _public_digest(public),
        "capabilities": [capability.value for capability in capabilities],
        "clockConfigDigest": clock.config_digest, "host": policy.host,
        "trustedWindow": [str(lower), str(upper)],
        "trustValidFrom": trust.validity.valid_from,
        "trustValidUntil": trust.validity.valid_until,
    }


def _public_digest(public) -> str:
    return digest(public.public_bytes_raw())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=("test", "production"), required=True)
    parser.add_argument("--release", required=True)
    parser.add_argument("--key-id", required=True, help="stable identifier for this signing key")
    parser.add_argument("--issuer", type=Path, required=True,
                        help="interpreter that may read the keychain item (ACL bound)")
    parser.add_argument("--capability", action="append", default=None,
                        choices=[capability.value for capability in Capability],
                        help="receipt capability to authorize; default is nts_clock")
    parser.add_argument("--days", type=int, default=1, help="maximum receipt validity (<=7)")
    args = parser.parse_args()
    stage = "arguments"
    try:
        if not 1 <= args.days <= 7:
            raise ValueError("receipt duration must be 1..7 days")
        if not args.issuer.is_file():
            raise ValueError("issuer interpreter must be an existing file")
        capabilities = tuple(Capability(name) for name in (
            args.capability or [Capability.NTS_CLOCK.value]))
        if len(set(capabilities)) != len(capabilities):
            raise ValueError("duplicate capability")
        for capability in capabilities:
            if capability is not Capability.NTS_CLOCK:
                # No other capability's artifact is bound to installed state yet.
                raise ValueError("capability is not bindable to installed state")
        # The password never appears in argv, the environment or a file.
        password = getpass.getpass("signing keychain password: ")
        if password != getpass.getpass("signing keychain password (confirm): "):
            raise ValueError("keychain passwords differ")
        stage = "provision"
        result = provision(args.profile, args.release, args.key_id, args.issuer,
                           args.days * 86400, password, capabilities)
    except Exception as error:
        print(json.dumps({"state": "BLOCKED", "stage": stage, "reason": type(error).__name__,
                          "detail": str(error)[:200]}))
        return 2
    finally:
        password = None
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
