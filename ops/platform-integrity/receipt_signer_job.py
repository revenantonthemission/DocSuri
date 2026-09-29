"""Install and run the sign-role launchd job that issues a protected receipt.

Why this exists
---------------
`require_signer_role` refuses to sign unless the process's kernel group set is exactly the sign
role's gid. Every macOS account carries implicit memberships (`everyone`, `localaccounts`, and
whatever nests into `admin`), and `sudo -u` calls `initgroups(3)`, which pushes all of them into
the kernel credential. A receipt therefore cannot be issued from an operator shell: the guard is
right and the invocation is impossible. Adding the role to `admin` cannot fix it, because
directory groups still arrive.

The remedy is to stop hand-assembling the group list and let `launchd` establish it. This job uses
the bootstrap the clock agents already use -- `setgroups([])`, `setgid`, `setuid`, then verify the
native credential -- so the job holds exactly one kernel group by construction rather than by
configuration, and proves it before any signing code runs.

Trust boundaries this preserves
-------------------------------
* The interpreter is the same binary the keychain ACL names. `SecTrustedApplicationCreateFromPath`
  is path-based, so the purpose key stays usable and is never exported to a file or to argv.
* That interpreter ships a *stale* copy of this library, so the job runs it with `PYTHONPATH`
  pointing at a root-owned, digest-pinned tree. The deployment manifest pins no site-packages
  entry, so the bundled copy is unverified; recording its digest is what makes the shadowing
  auditable rather than silent.
* `argv` is fixed at install time. No shell, no caller-supplied command, and no user-writable
  path anywhere in the chain, so an operator cannot redirect what gets signed.
"""

from __future__ import annotations

import argparse
import grp
import json
import os
import platform
import plistlib
import pwd
import shutil
import stat
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple

from docsuri_platform_integrity.contracts.codec import digest
from docsuri_platform_integrity.deployment.launchd import (
    REALMS,
    kernel_groups,
    protected_chain,
    role_account,
)
from docsuri_platform_integrity.deployment.receipt_policy import load_policy

SIGN_ROLE = "sign"
LABEL_PREFIX = "org.docsuri"
# Same minimal environment the clock agents use. launchd's own environment is discarded by
# `env -i` and rebuilt from scratch so nothing ambient can influence the signing process.
MINIMAL_ENV = {"PATH": "/usr/bin:/bin", "LANG": "en_US.UTF-8", "HOME": "/var/empty"}


class SignerUnavailable(PermissionError):
    pass


def role_identity(profile: str, role: str = SIGN_ROLE) -> tuple[int, int]:
    """The sign role's uid and gid, resolved through the deployment's own naming helper."""
    name = role_account(profile, role)
    return pwd.getpwnam(name).pw_uid, grp.getgrnam(name).gr_gid


class Credential(NamedTuple):
    """A native credential. The kernel supplies every field; none is ever caller-asserted."""

    uid: int
    euid: int
    gid: int
    egid: int
    groups: tuple[int, ...]


def current_credential() -> Credential:
    return Credential(os.getuid(), os.geteuid(), os.getgid(), os.getegid(), kernel_groups())


def check_role_boundary(expected_uid: int, expected_gid: int, credential: Credential) -> None:
    """Refuse unless the process holds exactly the sign role's identity and no other group.

    Split from the syscalls, and parameterised by the *expected* role, so the rule itself is
    directly testable: the entire purpose of the job is that the credential it establishes is
    checkable before any signing code executes. Comparing against an expected gid rather than
    against itself is what catches a job that landed in the wrong role entirely.
    """
    if (credential.uid, credential.euid, credential.gid, credential.egid) != (
        expected_uid, expected_uid, expected_gid, expected_gid
    ):
        raise SignerUnavailable("role identity not established")
    extra = sorted(set(credential.groups) - {expected_gid})
    if extra:
        raise SignerUnavailable(f"role boundary not established: extra kernel groups {extra}")


def drop_to_role(uid: int, gid: int) -> None:
    """Clear supplementary groups, then assume the sign role. Irreversible by design."""
    if os.getuid() == 0 and os.geteuid() == 0:
        os.setgroups([])
        os.setgid(gid)
        os.setuid(uid)
    check_role_boundary(uid, gid, current_credential())


def job_argv(*, interpreter: Path, bootstrap: Path, library: Path, state: Path,
             arguments: list[str], unattended: bool = False) -> list[str]:
    """Build the fixed command line.

    `/usr/bin/env -i` rebuilds the environment, so `PYTHONPATH` must be passed through explicitly.
    `-I` is unusable here: it implies `-E` and would silently discard that path, leaving the
    interpreter to import its own stale bundled copy. The environment is controlled instead.

    `unattended` adds `--keychain-password-stdin`, which is the flag that makes the issuer consume
    the one line `StandardInPath` feeds it. It is added here, at install time, rather than trusted
    from the caller's pass-through, so a job installed for unattended issuance cannot be
    downgraded to an interactive read by a later caller.
    """
    if unattended:
        arguments = [*arguments, "--keychain-password-stdin"]
    return [
        "/usr/bin/env", "-i", *[f"{key}={value}" for key, value in MINIMAL_ENV.items()],
        f"PYTHONPATH={library}", str(interpreter), "-B", str(bootstrap), "run",
        "--state", str(state), "--", *arguments,
    ]


def signer_job_plist(*, label: str, argv: list[str], working_directory: Path,
                     stdout: Path, stderr: Path, stdin: Path | None = None) -> bytes:
    """A one-shot job that runs as root only to clear groups before dropping to the role.

    `InitGroups: False` plus a root bootstrap is the pattern the clock deployment already uses:
    launchd alone cannot be relied on to hand a job a single group on Darwin, so the job clears the
    list itself and then proves the result with `kernel_groups()`.

    `StandardInPath` exists only to hand the issuer its one line of password. It is the sole
    supported way for an unattended job to unlock a Keychain whose `lock-on-sleep` interval will
    otherwise elapse between runs; the file is read by launchd as the job's stdin, so the secret
    appears in no `argv` entry, no environment variable, and no process listing.
    """
    result = {
        "Label": label, "UserName": "root", "GroupName": "wheel", "InitGroups": False,
        "ProgramArguments": argv, "Umask": 0o077, "WorkingDirectory": str(working_directory),
        "RunAtLoad": False, "ExitTimeOut": 30, "ThrottleInterval": 5, "ProcessType": "Background",
        "StandardOutPath": str(stdout), "StandardErrorPath": str(stderr),
        "SoftResourceLimits": {"NumberOfFiles": 256, "Core": 0},
        "HardResourceLimits": {"NumberOfFiles": 256, "Core": 0},
    }
    if stdin is not None:
        result["StandardInPath"] = str(stdin)
    return plistlib.dumps(result, sort_keys=True)


def verify_password_source(path: Path, expected_owner: int = 0) -> str:
    """Prove the unattended password file is safe to wire into the job, and return its digest.

    A persisted password is a real weakening of the trust boundary this module otherwise keeps, so
    the file is held to a stricter standard than the other root-owned inputs: it must be a regular
    file owned by the expected owner, reachable only by that owner, and must not be writable by
    any other account. The parent directory is checked too, because a `0400` file inside a
    world-writable directory can be replaced by a symlink of the attacker's choosing. Only the
    length and digest are recorded; the contents never leave this function.
    """
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode):
        raise SignerUnavailable("keychain password source is not a regular file")
    if info.st_uid != expected_owner:
        raise SignerUnavailable("keychain password source is not owned by the expected account")
    mode = stat.S_IMODE(info.st_mode)
    if mode & 0o077:
        raise SignerUnavailable(
            f"keychain password source must not be group- or world-accessible (mode {mode:04o})")
    parent = path.parent.lstat()
    if parent.st_uid != expected_owner:
        raise SignerUnavailable(
            "keychain password source directory is not owned by the expected account")
    if stat.S_IMODE(parent.st_mode) & 0o022:
        raise SignerUnavailable("keychain password source directory is group- or world-writable")
    if not 13 <= info.st_size <= 1025:
        # One trailing newline plus the 12..1024 byte range `read_password` accepts.
        raise SignerUnavailable("keychain password source is not a single 12..1024 byte line")
    data = path.read_bytes()
    if not data.endswith(b"\n"):
        raise SignerUnavailable("keychain password source must end with a newline")
    return digest(data)


def install_library(source: Path, destination: Path, owner: int = 0) -> dict[str, str]:
    """Copy the current library to a root-owned, immutable, digest-pinned tree.

    The signing interpreter is root-owned and digest-pinned, but the `docsuri_platform_integrity`
    it carries is neither. Shadowing it with a root-owned copy is what makes the code that signs
    reviewable rather than incidental. `owner` is parameterised only so tests can exercise the
    logic without root.
    """
    if destination.exists():
        raise FileExistsError("signer library already installed; remove it explicitly")
    # Stale bytecode is excluded for the same reason the clock toolchain excludes it: a `.pyc` in a
    # tree whose purpose is "the code that signs is reviewable" is code that nobody reviewed.
    shutil.copytree(source, destination,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"))
    os.chmod(destination, 0o555)
    recorded: dict[str, str] = {}
    for path in sorted(destination.rglob("*"), reverse=True):
        if owner == 0:
            os.chown(path, 0, 0)
        path.chmod(0o555)
        if not path.is_dir():
            recorded[str(path.relative_to(destination))] = digest(path.read_bytes())
    return recorded


def verify_installed_library(library: Path, recorded: dict[str, str],
                            *, expected_owner: int = 0) -> None:
    """Refuse to sign if the installed tree drifted from what install recorded."""
    info = library.lstat()
    # `expected_owner` is a parameter only so tests can exercise the rule without root; the job
    # always passes 0, and the caller's own euid is never an acceptable owner here.
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != expected_owner
            or stat.S_IMODE(info.st_mode) & 0o022):
        raise SignerUnavailable("signer library is not a root-owned immutable directory")
    observed = {
        str(path.relative_to(library)): digest(path.read_bytes())
        for path in sorted(library.rglob("*")) if path.is_file()
    }
    if observed != recorded:
        raise SignerUnavailable("signer library contents changed since install")


def bundled_library_digest(interpreter: Path) -> str:
    """Digest the modules the interpreter would import on its own.

    Recorded rather than trusted: the manifest pins no site-packages entry, so the copy that would
    otherwise satisfy the import is unverified. Shadowing it and recording what was shadowed is
    what makes that substitution reviewable afterwards.
    """
    completed = subprocess.run(
        [str(interpreter), "-I", "-B", "-c",
         "import docsuri_platform_integrity as m; print(m.__file__)"],
        capture_output=True, check=False, timeout=60,
    )
    if completed.returncode != 0:
        raise SignerUnavailable("bound interpreter cannot import the library")
    package = Path(completed.stdout.decode().strip()).parent
    if not package.is_dir() or package.is_symlink():
        raise SignerUnavailable("unexpected bundled library location")
    modules = sorted(item for item in package.rglob("*.py") if item.is_file())
    if not modules:
        raise SignerUnavailable("bundled library contains no modules")
    return f"{digest(b''.join(item.read_bytes() for item in modules))}:{len(modules)}"


def verify_shadowing(interpreter: Path, library: Path) -> None:
    """Refuse to install a tree the interpreter would not actually import.

    `PYTHONPATH` quietly loses to the interpreter's bundled `site-packages` whenever the tree is
    laid out one level too deep, and nothing else notices: the pinned digests match, the recorded
    bundled digest still matches, and the job signs with unverified code. The failure is silent by
    construction, so it is asked directly -- the bound interpreter is told where the package
    resolved from, and anything outside `library` is refused here rather than discovered later.
    """
    completed = subprocess.run(
        [str(interpreter), "-B", "-c",
         "import docsuri_platform_integrity as m; print(m.__file__)"],
        capture_output=True, check=False, timeout=60,
        env={**MINIMAL_ENV, "PYTHONPATH": str(library)})
    if completed.returncode != 0:
        raise SignerUnavailable("bound interpreter cannot import the shadowed library")
    resolved = Path(completed.stdout.decode().strip())
    if library.resolve() not in resolved.resolve().parents:
        raise SignerUnavailable(
            f"shadowed library is not what the interpreter imports; it resolved to {resolved}")


def install(args) -> int:
    if platform.system() != "Darwin" or os.geteuid() != 0:
        raise SignerUnavailable("installer must run as root on macOS")
    # load_policy verifies the host, the trust anchors and the account binding itself; the
    # explicit check below restates the signer binding so a mismatch is named as such.
    snapshot = load_policy(args.profile, args.release)
    policy = snapshot.policy
    uid, gid = role_identity(args.profile)
    if (policy.signer.uid, policy.signer.gid) != (uid, gid):
        raise SignerUnavailable("receipt policy signer does not match the sign role")

    root = REALMS[args.profile]
    deployment = root / "deployment.json"
    protected_chain(deployment)
    manifest = json.loads(deployment.read_text())
    if (manifest["profile"], manifest["release"]) != (args.profile, args.release):
        raise SignerUnavailable("installed deployment is a different profile or release")
    interpreter = Path(manifest["python"])
    if not interpreter.is_file() or interpreter.lstat().st_uid != 0:
        raise SignerUnavailable("bound interpreter is missing or not root-owned")

    home = Path(args.realm) if args.realm else root
    label = f"{LABEL_PREFIX}.{args.profile}.receipt-sign"
    signer = home / "signer"
    if args.replace:
        # Reinstalling means re-pinning the tree the job trusts, so it is an explicit act: boot the
        # old job out, then drop the previous tree. A plain rerun refuses rather than silently
        # re-pinning code that a running job may already be executing.
        subprocess.run(["launchctl", "bootout", f"system/{label}"],
                       capture_output=True, check=False)
        existing = Path("/Library/LaunchDaemons") / f"{label}.plist"
        if existing.exists():
            existing.unlink()
        if signer.exists():
            for path in sorted(signer.rglob("*"), reverse=True):
                path.chmod(0o700 if path.is_dir() else 0o600)
            signer.chmod(0o700)
            shutil.rmtree(signer)
    results = signer / "results"
    for directory in (signer, results):
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chown(directory, uid, gid)
    library = signer / "lib"
    # Two distinct root-owned scripts, and conflating them is the bug that made the job re-exec
    # itself with the issuer's flags: `bootstrap` establishes the role, `issuer` does the signing.
    # The source is named per destination, because this file is its own bootstrap source and must
    # not be looked up under the destination's name.
    bootstrap, issuer = signer / "bootstrap.py", signer / "issue_receipt.py"
    scripts = {bootstrap: Path(__file__).resolve(),
               issuer: Path(__file__).with_name("issue_receipt.py")}
    for destination, source in scripts.items():
        if not source.is_file():
            raise FileNotFoundError(f"signer script source missing: {source}")
        if destination.exists():
            raise FileExistsError(f"{destination} already installed; remove it explicitly")
        shutil.copy2(source, destination)
        os.chown(destination, 0, 0)
        destination.chmod(0o555)
    recorded = install_library(Path(args.library_source), library)
    verify_shadowing(interpreter, library)

    password_file = args.keychain_password_file
    password_digest = None
    if password_file is not None:
        if not password_file.is_absolute():
            raise SignerUnavailable("keychain password source must be an absolute path")
        password_digest = verify_password_source(password_file, expected_owner=0)
        # The caller's pass-through must not also claim stdin, or a future rerun could read a
        # different source than the one whose digest is recorded in the job state.
        if "--keychain-password-stdin" in passthrough(args.issue_arguments):
            raise SignerUnavailable(
                "--keychain-password-stdin is set by --keychain-password-file; do not pass it")

    state = {
        "profile": args.profile, "release": args.release, "keychain": policy.signer.keychain,
        "policyPath": str(snapshot.path), "policyDigest": snapshot.digest,
        "interpreter": str(interpreter), "interpreterDigest": digest(interpreter.read_bytes()),
        "bundledLibrary": bundled_library_digest(interpreter),
        "library": str(library), "libraryFiles": recorded,
        "bootstrap": str(bootstrap), "issuer": str(issuer),
        "issuerDigest": digest(issuer.read_bytes()),
        "results": str(results), "uid": uid, "gid": gid,
        "passwordSource": str(password_file) if password_file else None,
        "passwordDigest": password_digest,
    }
    state_path = signer / "job.json"
    state_path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")
    os.chown(state_path, 0, 0)
    state_path.chmod(0o444)

    argv = job_argv(interpreter=interpreter, bootstrap=bootstrap, library=library,
                    state=state_path, arguments=passthrough(args.issue_arguments),
                    unattended=password_file is not None)
    destination = Path("/Library/LaunchDaemons") / f"{label}.plist"
    destination.write_bytes(signer_job_plist(
        label=label, argv=argv, working_directory=results,
        stdout=results / "job.out", stderr=results / "job.err",
        stdin=password_file,
    ))
    os.chown(destination, 0, 0)
    destination.chmod(0o644)
    completed = subprocess.run(["launchctl", "bootstrap", "system", str(destination)],
                               capture_output=True, check=False)
    if completed.returncode != 0:
        raise SignerUnavailable(
            f"launchctl bootstrap failed: {completed.stderr.decode(errors='replace').strip()}")
    print(json.dumps({"state": "INSTALLED", "label": label, "plist": str(destination),
                      "jobState": str(state_path), "results": str(results)}, indent=2))
    return 0


def passthrough(arguments) -> list[str]:
    """Drop argparse's leading separator. REMAINDER preserves it, and it must not reach argv."""
    return [item for item in arguments if item != "--"]


def run_bootstrap(args) -> int:
    """Execute as the sign role: verify the pinned tree, then exec the bound interpreter."""
    uid, gid = role_identity(args.profile)
    drop_to_role(uid, gid)
    state_path = Path(args.state)
    info = state_path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or stat.S_IMODE(info.st_mode) & 0o022:
        raise SignerUnavailable("signer job state is not a root-owned regular file")
    state = json.loads(state_path.read_text())
    if (state["uid"], state["gid"]) != (uid, gid):
        raise SignerUnavailable("signer job state does not describe this role")
    # The job is bound to the policy revision it was installed against, so a policy edited in
    # between cannot silently widen the scope of what gets signed.
    current = load_policy(args.profile, state["release"])
    if (str(current.path), current.digest) != (state["policyPath"], state["policyDigest"]):
        raise SignerUnavailable("receipt policy changed since the signer job was installed")
    verify_installed_library(Path(state["library"]), state["libraryFiles"])
    interpreter = Path(state["interpreter"])
    if digest(interpreter.read_bytes()) != state["interpreterDigest"]:
        raise SignerUnavailable("bound interpreter changed since install")
    issuer = Path(state["issuer"])
    if digest(issuer.read_bytes()) != state["issuerDigest"]:
        raise SignerUnavailable("receipt issuer changed since install")
    os.umask(0o077)
    # Re-prove the password source immediately before the exec. Install-time validation alone is
    # not enough: the file is operator-editable by design (so the password can be rotated without
    # reinstalling), which means it can also have been replaced, relaxed to 0644, or deleted.
    password_source = state.get("passwordSource")
    if password_source is not None:
        recorded = state.get("passwordDigest")
        if verify_password_source(Path(password_source), expected_owner=0) != recorded:
            raise SignerUnavailable("keychain password source changed since the job was installed")
    # The job states its own policy binding and the pass-through may only *narrow* it. Letting
    # the trailing arguments name a different profile or release would let a caller sign against
    # a policy the job was never installed for, so those flags are rejected outright.
    arguments = passthrough(args.issue_arguments)
    for flag in ("--profile", "--release"):
        if flag in arguments:
            raise SignerUnavailable(
                f"the signer job fixes the policy binding; {flag} is not settable")
    # stdout is the process's real stdout, and stdin is whatever launchd attached. Unlocking then
    # re-locks around the issuance, so the secret is dropped as soon as the signing call returns.
    os.execve(str(interpreter),
              [str(interpreter), "-B", str(issuer), "--profile", state["profile"],
               "--release", state["release"], *arguments],
              {**MINIMAL_ENV, "PYTHONPATH": state["library"]})


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--profile", choices=("test", "production"), default="test")
    sub = parser.add_subparsers(dest="command", required=True)
    installer = sub.add_parser("install", help="install the sign-role launchd job")
    installer.add_argument("--release", required=True)
    installer.add_argument("--library-source", required=True,
                           help="directory containing the docsuri_platform_integrity package")
    installer.add_argument("--realm", help="override the realm root")
    installer.add_argument("--replace", action="store_true",
                           help="boot out and re-pin an existing signer job and its library tree")
    installer.add_argument("--keychain-password-file", type=Path,
                           help="root-owned single-line password file wired to the job's stdin; "
                                "required for unattended issuance, since a LaunchDaemon cannot "
                                "prompt and the purpose Keychain locks on sleep")
    installer.add_argument("issue_arguments", nargs=argparse.REMAINDER)
    runner = sub.add_parser("run", help="bootstrap the sign role and issue (launchd invokes this)")
    runner.add_argument("--state", required=True)
    runner.add_argument("issue_arguments", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    return install(args) if args.command == "install" else run_bootstrap(args)


if __name__ == "__main__":
    raise SystemExit(main())
