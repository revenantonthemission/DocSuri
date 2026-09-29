"""Role-scoped launchd/exec allowlist. Only protected, digest-bound manifests may execute."""

import argparse
import ctypes
import grp
import json
import os
import plistlib
import pwd
import stat
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Annotated, Literal

from pydantic import Field

from ..contracts.codec import canonical, decode, digest
from ..contracts.models import Digest, Value

ROLES = ("reader", "runner", "tool", "bundle", "sign", "audit", "journal", "backup", "clock")
REALMS = {"test": Path("/Library/Application Support/DocSuri/rem-1-test"),
          "production": Path("/Library/Application Support/DocSuri/rem-1")}
MINIMAL_ENV = {"PATH": "/usr/bin:/bin", "LANG": "en_US.UTF-8", "HOME": "/var/empty"}
Tag = Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9-]{0,99}$")]
Argument = Annotated[str, Field(min_length=1, max_length=1024)]
LAUNCH_DAEMONS = Path("/Library/LaunchDaemons")
LAUNCHCTL = Path("/bin/launchctl")
LABEL_PREFIX = "org.docsuri.rem1."
# One artifact per frozen entry; the plist name is the label so the test and production
# realms can never collide in a single system domain.
PLIST_MODE = 0o644
# The manifest contains public artifact paths/digests and role metadata, never credentials.
# launchd starts exec under the service UID, which must read this root-owned, non-writable file.
MANIFEST_MODE = 0o444
MANIFEST_MAX_BYTES = 4 * 1024**2


def entry_label(profile: str, entry) -> str:
    return LABEL_PREFIX + profile + "." + entry.name


def plist_path(profile: str, entry) -> Path:
    return LAUNCH_DAEMONS / (entry_label(profile, entry) + ".plist")


def role_account(profile: str, role: str) -> str:
    return ("_docsuri_r1t_" if profile == "test" else "_docsuri_r1_") + role


class LaunchEntry(Value):
    name: Tag
    role: Literal[
        "reader", "runner", "tool", "bundle", "sign", "audit", "journal", "backup", "clock"
    ]
    uid: Annotated[int, Field(ge=1, le=2**31 - 1)]
    gid: Annotated[int, Field(ge=1, le=2**31 - 1)]
    mode: Literal["daemon", "oneshot", "periodic", "observer"]
    interval: Annotated[int, Field(ge=5, le=86400)] | None = None
    argv: Annotated[tuple[Argument, ...], Field(min_length=1, max_length=32)]


class LaunchManifest(Value):
    profile: Literal["test", "production"]
    release: Tag
    python: str
    entries: Annotated[tuple[LaunchEntry, ...], Field(min_length=1, max_length=32)]
    artifacts: Annotated[tuple[tuple[str, Digest], ...], Field(min_length=1, max_length=10_000)]


def artifact_path(manifest, name):
    path = PurePosixPath(name)
    root = REALMS[manifest.profile]
    if (
        not path.is_absolute() or str(path) != name or ".." in path.parts
        or any(character in name for character in "\x00\r\n")
    ):
        raise ValueError("noncanonical artifact path")
    relative = Path(name).relative_to(root)
    if len(relative.parts) < 3 or relative.parts[0] not in {"releases", "toolchains"}:
        raise ValueError("artifact outside frozen roots")
    if relative.parts[0] == "releases" and relative.parts[1] != manifest.release:
        raise ValueError("artifact from another release")
    return Path(name)


def validate_manifest(manifest: LaunchManifest):
    if len({entry.name for entry in manifest.entries}) != len(manifest.entries):
        raise ValueError("duplicate launch entry")
    artifacts = dict(manifest.artifacts)
    if len(artifacts) != len(manifest.artifacts):
        raise ValueError("duplicate artifact path")
    if manifest.python not in artifacts:
        raise ValueError("launcher interpreter digest missing")
    for name, _ in manifest.artifacts:
        artifact_path(manifest, name)
    identities = {}
    for entry in manifest.entries:
        pair = entry.uid, entry.gid
        if entry.role in identities and identities[entry.role] != pair:
            raise ValueError("role identity changed within manifest")
        if entry.role not in identities and any(
            uid == entry.uid or gid == entry.gid for uid, gid in identities.values()
        ):
            raise ValueError("roles share an identity")
        identities[entry.role] = pair
        if entry.mode == "daemon" and entry.role != "reader":
            raise ValueError("only reader has daemon keepalive")
        if (entry.mode == "periodic") != (entry.interval is not None):
            raise ValueError("periodic entry requires explicit interval")
        if any(any(char in arg for char in "\x00\r\n") for arg in entry.argv):
            raise ValueError("invalid argument")
        if entry.argv[0] not in artifacts:
            raise ValueError("executable digest missing")
        artifact_path(manifest, entry.argv[0])
        if entry.mode == "observer":
            if (
                entry.role != "clock" or len(entry.argv) != 6
                or entry.argv[1:5] != ("-x", "-U", "-d", "-f")
                or entry.argv[5] not in artifacts
            ):
                raise ValueError("clock observer must be fixed non-adjusting chronyd")
        elif (
            entry.argv[0] != manifest.python or len(entry.argv) < 5
            # -B is required, not tolerated. Bytecode written into the frozen closure is
            # rewritten in place by the next interpreter run that lacks it, which invalidates
            # the pinned artifact digests and leaves execute() unable to start ever again.
            or entry.argv[1:4] != ("-I", "-B", "-m")
            or entry.argv[4] not in {"docsuri_platform_integrity.host",
                                     "docsuri_platform_integrity.cli"}
        ):
            raise ValueError("unsupported executable entry")
        for arg in entry.argv:
            if arg.startswith("/"):
                artifact_path(manifest, arg)
                if arg not in artifacts:
                    raise ValueError("argument artifact digest missing")
    return manifest


def protected_bytes(path: Path, *, owner=0, limit=262_144):
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, "rb") as source:
        value = os.fstat(source.fileno())
        if (
            not stat.S_ISREG(value.st_mode) or value.st_uid != owner
            or value.st_mode & 0o022 or value.st_nlink != 1 or value.st_size > limit
        ):
            raise PermissionError("unprotected runtime artifact")
        content = source.read(limit + 1)
        if len(content) > limit:
            raise ValueError("runtime artifact too large")
        return content


def protected_chain(path: Path):
    for parent in path.parents:
        value = parent.lstat()
        if not stat.S_ISDIR(value.st_mode) or value.st_uid != 0 or value.st_mode & 0o022:
            raise PermissionError("runtime ancestor is mutable")


def kernel_groups():
    if sys.platform != "darwin":
        raise PermissionError("native macOS required")
    library = ctypes.CDLL("/usr/lib/libSystem.B.dylib", use_errno=True)
    function = library.getgroups
    function.argtypes = [ctypes.c_int, ctypes.POINTER(ctypes.c_uint32)]
    function.restype = ctypes.c_int
    count = function(0, None)
    if not 0 <= count <= 256:
        raise PermissionError("kernel group observation unavailable")
    groups = (ctypes.c_uint32 * max(count, 1))()
    if function(count, groups) != count:
        raise PermissionError("kernel group observation changed")
    return tuple(groups[:count])


def manifest_digest(manifest):
    return digest(canonical(manifest.model_dump(mode="json")))


def launchd_plist(manifest: LaunchManifest, entry: LaunchEntry) -> bytes:
    validate_manifest(manifest)
    if entry not in manifest.entries:
        raise ValueError("entry not in frozen manifest")
    label = entry_label(manifest.profile, entry)
    # env is a fixed system executable: launchd's inherited environment is removed before Python.
    arguments = ["/usr/bin/env", "-i", *[f"{k}={v}" for k, v in MINIMAL_ENV.items()],
                 manifest.python, "-I", "-B", "-m", "docsuri_platform_integrity.deployment.launchd",
                 "exec", "--profile", manifest.profile, "--entry", entry.name,
                 "--manifest-digest", manifest_digest(manifest)]
    # Darwin may supply directory groups even with InitGroups=false. The verified bootstrap
    # needs root only to clear groups, then setgid/setuid and check native credentials before exec.
    # -B prevents this short root phase from creating unmanifested bytecode in the frozen closure.
    result = {"Label": label, "UserName": "root", "GroupName": "wheel",
              "InitGroups": False, "ProgramArguments": arguments, "Umask": 0o077,
              "WorkingDirectory": str(REALMS[manifest.profile] / entry.role),
              "KeepAlive": entry.mode == "daemon",
              "RunAtLoad": entry.mode in {"daemon", "observer"},
              "ExitTimeOut": 5, "ThrottleInterval": 5, "ProcessType": "Background",
              "SoftResourceLimits": {"NumberOfFiles": 256, "Core": 0},
              "HardResourceLimits": {"NumberOfFiles": 256, "Core": 0}}
    if entry.mode == "periodic":
        result["StartInterval"] = entry.interval
    return plistlib.dumps(result, sort_keys=True)


def execute(profile: str, name: str, expected_digest: str):
    root = REALMS[profile]
    path = root / "deployment.json"
    protected_chain(path)
    manifest = validate_manifest(LaunchManifest.model_validate_json(
        canonical(decode(protected_bytes(path, limit=MANIFEST_MAX_BYTES)))
    ))
    if manifest.profile != profile or manifest_digest(manifest) != expected_digest:
        raise PermissionError("deployment manifest changed")
    entry = next((item for item in manifest.entries if item.name == name), None)
    if entry is None:
        raise PermissionError("unknown launch entry")
    prefix = "_docsuri_r1t_" if profile == "test" else "_docsuri_r1_"
    principal = pwd.getpwnam(prefix + entry.role)
    group = grp.getgrnam(prefix + entry.role)
    if (principal.pw_uid, principal.pw_gid, group.gr_gid) != (entry.uid, entry.gid, entry.gid):
        raise PermissionError("installed identity differs from deployment")
    total = 0
    for name, expected in manifest.artifacts:
        artifact = artifact_path(manifest, name)
        protected_chain(artifact)
        data = protected_bytes(artifact, limit=64 * 1024**2)
        total += len(data)
        if total > 512 * 1024**2 or digest(data) != expected:
            raise PermissionError("frozen artifact verification failed")
    if os.getuid() == 0 and os.geteuid() == 0:
        os.setgroups([])
        os.setgid(entry.gid)
        os.setuid(entry.uid)
    if (
        (os.getuid(), os.geteuid(), os.getgid(), os.getegid())
        != (entry.uid, entry.uid, entry.gid, entry.gid)
        or set(kernel_groups()) - {entry.gid}
    ):
        raise PermissionError("runtime role boundary not established")
    os.umask(0o077)
    os.chdir(root / entry.role)
    os.execve(entry.argv[0], list(entry.argv), MINIMAL_ENV.copy())


def require_root():
    if sys.platform != "darwin":
        raise PermissionError("native macOS required")
    if os.getuid() != 0 or os.geteuid() != 0:
        raise PermissionError("installer requires root")
    if LAUNCHCTL.is_symlink() or not LAUNCHCTL.is_file():
        raise PermissionError("launchctl unavailable")
    if os.stat(LAUNCHCTL).st_mode & 0o022:
        raise PermissionError("launchctl is writable")


def launchctl(*arguments):
    """Fixed-argument launchctl call. No shell, no inherited environment, no stdin."""
    result = subprocess.run(
        [str(LAUNCHCTL), *arguments], stdin=subprocess.DEVNULL, capture_output=True,
        text=True, timeout=60, env=dict(MINIMAL_ENV), check=False)
    if result.returncode != 0:
        raise RuntimeError("launchctl " + arguments[0] + " failed: " + result.stderr.strip()[:200])
    return result.stdout


def is_loaded(label: str) -> bool:
    """True only when launchd currently holds the job. A non-zero exit means it does not."""
    result = subprocess.run(
        [str(LAUNCHCTL), "print", "system/" + label], stdin=subprocess.DEVNULL,
        capture_output=True, text=True, timeout=60, env=dict(MINIMAL_ENV), check=False)
    return result.returncode == 0


def read_manifest(path: Path) -> LaunchManifest:
    protected_chain(path)
    return validate_manifest(LaunchManifest.model_validate_json(
        canonical(decode(protected_bytes(path, limit=MANIFEST_MAX_BYTES)))
    ))


def read_published(path: Path):
    """Canonical JSON of the manifest currently published in a realm, without schema validation.

    A deployment written by an earlier release need not satisfy today's validator -- a stricter
    one adds rules over time. Parsing it strictly would make an explicit replace unable to
    migrate exactly the deployments that need migrating, so only the byte-level protections
    apply here. Nothing is executed from this document; it is compared and read for labels.
    """
    protected_chain(path)
    return json.loads(canonical(decode(protected_bytes(path, limit=MANIFEST_MAX_BYTES))))


def published_labels(profile: str, path: Path) -> list[str]:
    """Labels named by the published manifest, so an older release can still be retired."""
    document = read_published(path)
    if not isinstance(document, dict) or not isinstance(document.get("entries"), list):
        raise PermissionError("published manifest is unreadable")
    labels = []
    for entry in document["entries"]:
        name = entry.get("name") if isinstance(entry, dict) else None
        if not isinstance(name, str) or not name:
            raise PermissionError("published manifest entry is unreadable")
        labels.append(LABEL_PREFIX + profile + "." + name)
    return labels


def verify_realm(profile: str):
    """The realm root and every role work directory must already be root-built and immutable."""
    root = REALMS[profile]
    protected_chain(root)
    value = os.lstat(root)
    if not stat.S_ISDIR(value.st_mode):
        raise PermissionError("realm is not a directory")
    if not LAUNCH_DAEMONS.is_dir():
        raise PermissionError("launchd system directory missing")
    return root


def verify_identities(manifest: LaunchManifest):
    """Every declared uid/gid must be a real, already-created launchd account."""
    for entry in manifest.entries:
        account = role_account(manifest.profile, entry.role)
        try:
            principal, group = pwd.getpwnam(account), grp.getgrnam(account)
        except KeyError as error:
            raise PermissionError("role account not provisioned") from error
        if (principal.pw_uid, principal.pw_gid, group.gr_gid) != (entry.uid, entry.gid, entry.gid):
            raise PermissionError("installed identity differs from deployment")
        working = REALMS[manifest.profile] / entry.role
        directory = os.lstat(working)
        if not stat.S_ISDIR(directory.st_mode) or directory.st_uid != entry.uid:
            raise PermissionError("role working directory is not owned by its role")


def verify_artifacts(manifest: LaunchManifest):
    """Refuse to publish anything until every frozen byte is proven on disk."""
    total = 0
    for name, expected in manifest.artifacts:
        artifact = artifact_path(manifest, name)
        protected_chain(artifact)
        data = protected_bytes(artifact, limit=64 * 1024**2)
        total += len(data)
        if total > 512 * 1024**2 or digest(data) != expected:
            raise PermissionError("frozen artifact verification failed")
    return total


def write_root_file(path: Path, data: bytes, mode: int):
    """Create a root-owned immutable file atomically; never follow an existing symlink."""
    if path.is_symlink():
        raise PermissionError("refusing to write through a symlink")
    if path.exists():
        existing = os.lstat(path)
        if not stat.S_ISREG(existing.st_mode) or existing.st_uid != 0 or existing.st_nlink != 1:
            raise PermissionError("refusing to replace a foreign launchd file")
        path.unlink()
    temporary = path.with_name("." + path.name + ".installing")
    if temporary.exists():
        temporary.unlink()
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
    try:
        with os.fdopen(descriptor, "wb") as sink:
            sink.write(data)
            sink.flush()
            os.fsync(sink.fileno())
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    os.chmod(temporary, mode)
    os.replace(temporary, path)
    os.chown(path, 0, 0)
    directory = os.open(path.parent, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)
    if path.read_bytes() != data:
        raise PermissionError("installed file verification failed")


def bootout(profile: str, labels: list[str]):
    """Stop the named jobs. Idempotent: a label launchd does not hold is not an error.

    Load state is observed directly instead of inferred from launchd's wording, which varies by
    release ("not found" versus "Could not find service"); re-checking after a failed call also
    covers a job that unloads concurrently.
    """
    for label in labels:
        if not is_loaded(label):
            continue
        result = subprocess.run(
            [str(LAUNCHCTL), "bootout", "system/" + label], stdin=subprocess.DEVNULL,
            capture_output=True, text=True, timeout=60, env=dict(MINIMAL_ENV), check=False)
        if result.returncode != 0 and is_loaded(label):
            raise RuntimeError("launchctl bootout failed: " + result.stderr.strip()[:200])


def installed_digest(profile: str):
    """Digest of the deployment currently published in the realm, or None if nothing is."""
    path = REALMS[profile] / "deployment.json"
    if not path.is_file() or path.is_symlink():
        return None
    return digest(canonical(read_published(path)))


def is_published(profile: str, manifest: LaunchManifest) -> bool:
    """A deployment counts as installed only if the manifest, every plist byte and every
    live label all agree. A half-removed or drifted install must be repaired, not trusted."""
    if installed_digest(profile) != manifest_digest(manifest):
        return False
    if stat.S_IMODE((REALMS[profile] / "deployment.json").stat().st_mode) != MANIFEST_MODE:
        return False
    for entry in manifest.entries:
        path = plist_path(profile, entry)
        if path.is_symlink() or not path.is_file():
            return False
        if path.read_bytes() != launchd_plist(manifest, entry):
            return False
        if not is_loaded(entry_label(profile, entry)):
            return False
    return True


def install(profile: str, manifest_path: Path, *, replace: bool = False):
    """Verify everything, then publish plists and bootstrap them into the system domain."""
    require_root()
    root = verify_realm(profile)
    manifest = read_manifest(manifest_path)
    if manifest.profile != profile:
        raise PermissionError("manifest belongs to another realm")
    verify_identities(manifest)
    verify_artifacts(manifest)
    expected = manifest_digest(manifest)
    current = installed_digest(profile)
    if current is not None and current != expected and not replace:
        raise PermissionError("a different deployment is already installed; use --replace")
    if current == expected and is_published(profile, manifest) and not replace:
        return {"state": "ALREADY_INSTALLED", "manifestDigest": expected, "labels": []}
    if current is not None:
        bootout(profile, published_labels(profile, root / "deployment.json"))
    outputs = {plist_path(profile, item): launchd_plist(manifest, item)
               for item in manifest.entries}
    for path, data in outputs.items():
        write_root_file(path, data, PLIST_MODE)
    write_root_file(root / "deployment.json",
                    canonical(manifest.model_dump(mode="json")), MANIFEST_MODE)
    labels = []
    for entry in manifest.entries:
        launchctl("bootstrap", "system", str(plist_path(profile, entry)))
        labels.append(entry_label(profile, entry))
    if not is_published(profile, manifest):
        raise RuntimeError("installed state did not verify")
    return {"state": "INSTALLED", "manifestDigest": expected, "labels": labels,
            "artifacts": len(manifest.artifacts)}


def uninstall(profile: str):
    """Boot out and remove only this realm's own files. No recursive or glob deletion."""
    require_root()
    root = verify_realm(profile)
    manifest = read_manifest(root / "deployment.json")
    if manifest.profile != profile:
        raise PermissionError("installed manifest belongs to another realm")
    bootout(profile, [entry_label(profile, item) for item in manifest.entries])
    still = [entry_label(profile, item) for item in manifest.entries
             if is_loaded(entry_label(profile, item))]
    if still:
        # Deleting the plist of a job launchd still holds would orphan a running process
        # with no way to stop it, so refuse and leave everything in place.
        raise RuntimeError("launchd still holds jobs: " + ",".join(sorted(still)))
    removed = []
    for entry in manifest.entries:
        path = plist_path(profile, entry)
        if not path.is_file() or path.is_symlink():
            continue
        if plistlib.loads(path.read_bytes())["Label"] != entry_label(profile, entry):
            raise PermissionError("refusing to remove a foreign launchd file")
        path.unlink()
        removed.append(entry_label(profile, entry))
    (root / "deployment.json").unlink()
    return {"state": "UNINSTALLED", "labels": removed}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    render = commands.add_parser("render")
    render.add_argument("manifest", type=Path)
    render.add_argument("destination", type=Path)
    launch = commands.add_parser("exec")
    launch.add_argument("--profile", choices=tuple(REALMS), required=True)
    launch.add_argument("--entry", required=True)
    launch.add_argument("--manifest-digest", required=True)
    setup = commands.add_parser("install")
    setup.add_argument("--profile", choices=tuple(REALMS), required=True)
    setup.add_argument("manifest", type=Path)
    setup.add_argument("--replace", action="store_true")
    teardown = commands.add_parser("uninstall")
    teardown.add_argument("--profile", choices=tuple(REALMS), required=True)
    args = parser.parse_args()
    try:
        if args.command == "exec":
            execute(args.profile, args.entry, args.manifest_digest)
        elif args.command == "install":
            print(json.dumps(install(args.profile, args.manifest, replace=args.replace)))
        elif args.command == "uninstall":
            print(json.dumps(uninstall(args.profile)))
        else:
            manifest = validate_manifest(LaunchManifest.model_validate_json(
                canonical(decode(args.manifest.read_bytes()))
            ))
            outputs = {item.name + ".plist": launchd_plist(manifest, item)
                       for item in manifest.entries}
            outputs["deployment.json"] = canonical(manifest.model_dump(mode="json"))
            args.destination.mkdir(mode=0o700, exist_ok=False)
            for name, data in outputs.items():
                (args.destination / name).write_bytes(data)
            print(json.dumps({"state": "GENERATED_NOT_INSTALLED",
                              "manifestDigest": manifest_digest(manifest),
                              "entries": len(manifest.entries)}))
        return 0
    except Exception as error:
        # The reason alone has repeatedly hidden the failing call; carry the type and message
        # so an operator can act without rebuilding a bundle to surface the traceback.
        print(json.dumps({"state": "BLOCKED", "reason": "native_launch_unavailable",
                          "errorType": type(error).__name__, "detail": str(error)[:200]}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
