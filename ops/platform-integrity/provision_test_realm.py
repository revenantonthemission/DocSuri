#!/usr/bin/env python3
"""Operator-run native UID/filesystem preparation, exclusively for the isolated test realm.

No serving daemon is started. This is preparation, not a native/G1 acceptance receipt.
"""

import argparse
import ctypes
import hashlib
import json
import os
import platform
import plistlib
import secrets
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path("/Library/Application Support/DocSuri/rem-1-test")
ROLES = ("reader", "runner", "tool", "bundle", "sign", "audit", "journal", "backup", "clock")
DIRECTORY_GROUPS = {"everyone": 12, "localaccounts": 61, "_lpoperator": 100}
WORKER_STAGES = frozenset({
    "worker_entered", "imports_ready", "input_wait", "input_ready", "identity_check",
    "kernel_groups", "groups_verified", "own_open", "own_read", "own_write", "own_fsync",
    "own_verified", "cross_role_checks", "directory_group_checks", "complete",
})

# This fixed program executes only after Popen has dropped UID/GID/supplementary groups.
# The data and paths are synthetic fixtures constructed by the root-owned parent.
PROBE_PROGRAM = r'''
import sys

def stage(code):
    sys.stderr.write("R1PROBE:" + code + "\n")
    sys.stderr.flush()

if __name__ == "__main__":
    stage("worker_entered")
import ctypes
import json
import os
import stat
if __name__ == "__main__":
    stage("imports_ready")

def process_groups():
    # macOS CPython os.getgroups() queries directory membership, even after setgroups().
    # Read the bounded kernel credential list directly; file probes also verify enforcement.
    if sys.platform != "darwin":
        return os.getgroups()
    stage("kernel_groups")
    library = ctypes.CDLL("/usr/lib/libSystem.B.dylib", use_errno=True)
    function = library.getgroups
    function.argtypes = [ctypes.c_int, ctypes.POINTER(ctypes.c_uint32)]
    function.restype = ctypes.c_int
    count = function(0, None)
    if not 0 <= count <= 256:
        raise OSError("kernel_group_query")
    buffer = (ctypes.c_uint32 * max(count, 1))()
    observed = function(count, buffer)
    if observed != count:
        raise OSError("kernel_group_query_changed")
    return list(buffer[:observed])

def probe_access(payload):
    stage("identity_check")
    uid, gid = payload["uid"], payload["gid"]
    if (os.getuid(), os.geteuid(), os.getgid(), os.getegid()) != (uid, uid, gid, gid):
        raise PermissionError("process_identity")
    groups = process_groups()
    if set(groups) - {gid}:
        raise PermissionError("effective_groups")
    stage("groups_verified")
    stage("own_open")
    descriptor = os.open(payload["own"], os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, "r+b", buffering=0) as own:
        value = os.fstat(own.fileno())
        if not stat.S_ISREG(value.st_mode) or value.st_nlink != 1:
            raise ValueError("fixture_not_regular")
        stage("own_read")
        if own.read(4097) != payload["token"].encode():
            raise ValueError("fixture_mismatch")
        stage("own_write")
        own.write(b":verified")
        own.flush()
        stage("own_fsync")
        os.fsync(own.fileno())
    stage("own_verified")
    read_denied = write_denied = group_denied = 0
    stage("cross_role_checks")
    for path in payload["others"]:
        for flags in (os.O_RDONLY, os.O_WRONLY):
            try:
                descriptor = os.open(path, flags | os.O_NOFOLLOW | os.O_NONBLOCK)
            except PermissionError:
                if flags == os.O_RDONLY:
                    read_denied += 1
                else:
                    write_denied += 1
            else:
                os.close(descriptor)
                raise PermissionError("cross_role_access")
    stage("directory_group_checks")
    for path in payload["groupFiles"]:
        try:
            descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        except PermissionError:
            group_denied += 1
        else:
            os.close(descriptor)
            raise PermissionError("ambient_group_access")
    stage("complete")
    return {"uid": uid, "gid": gid, "groups": groups, "ownReadWrite": True,
            "crossReadDenied": read_denied, "crossWriteDenied": write_denied,
            "directoryGroupReadDenied": group_denied}

if __name__ == "__main__":
    try:
        stage("input_wait")
        data = sys.stdin.buffer.read(65537)
        stage("input_ready")
        if len(data) > 65536:
            raise ValueError("probe_input_limit")
        print(json.dumps(probe_access(json.loads(data))))
    except Exception as error:
        codes = {"process_identity", "effective_groups", "fixture_mismatch", "cross_role_access",
                 "ambient_group_access", "fixture_not_regular", "probe_input_limit",
                 "kernel_group_query", "kernel_group_query_changed"}
        reason = str(error) if str(error) in codes else type(error).__name__
        print(json.dumps({"state": "BLOCKED", "reason": reason}))
        sys.exit(2)
'''


def command(*arguments):
    result = subprocess.run(arguments, capture_output=True, text=True, timeout=10, check=True)
    return result.stdout.strip()


def secure_directory(path, uid=0):
    if path.exists() or path.is_symlink():
        value = path.lstat()
        if not stat.S_ISDIR(value.st_mode) or value.st_uid not in {0, uid}:
            raise RuntimeError("existing test-realm path has unexpected ownership/type")
    else:
        path.mkdir(mode=0o700)
    os.chown(path, uid, -1)
    path.chmod(0o700)


def validate_identity_attributes(name, uid, users, groups):
    if (
        not 600 <= uid < 4000 or groups.get(name) != str(uid)
        or list(users.values()).count(str(uid)) != 1
        or list(groups.values()).count(str(uid)) != 1
    ):
        raise RuntimeError("existing test identity has an unsafe or aliased UID/GID")
    expected = {"UniqueID": str(uid), "PrimaryGroupID": str(uid),
                "UserShell": "/usr/bin/false", "NFSHomeDirectory": "/var/empty", "IsHidden": "1"}
    attributes = plistlib.loads(command(
        "/usr/bin/dscl", "-plist", ".", "-read", "/Users/" + name, *expected,
    ).encode())
    for attribute, value in expected.items():
        aliases = (attribute, "dsAttrTypeStandard:" + attribute, "dsAttrTypeNative:" + attribute)
        observed = [attributes[key] for key in aliases if key in attributes]
        if not observed or any(item != [value] for item in observed):
            raise RuntimeError("pre-existing test identity attributes differ from the plan")


def validate_existing_identity(name, uid, users, groups):
    validate_identity_attributes(name, uid, users, groups)
    if set(command("/usr/bin/id", "-G", name).split()) != {str(uid)}:
        raise RuntimeError("pre-existing test identity has supplementary privileges")


def directory_ids():
    users = dict(line.rsplit(None, 1) for line in command(
        "/usr/bin/dscl", ".", "-list", "/Users", "UniqueID",
    ).splitlines())
    groups = dict(line.rsplit(None, 1) for line in command(
        "/usr/bin/dscl", ".", "-list", "/Groups", "PrimaryGroupID",
    ).splitlines())
    return users, groups


def checked_directory(path, uid, mode, gid=None):
    value = path.lstat()
    if (
        not stat.S_ISDIR(value.st_mode) or value.st_uid != uid
        or stat.S_IMODE(value.st_mode) != mode
        or (gid is not None and value.st_gid != gid)
    ):
        raise RuntimeError("test directory ownership or mode mismatch")


def check_preparation():
    """Readonly account/directory metadata, not process execution or native acceptance."""
    if platform.system() != "Darwin":
        raise RuntimeError("native macOS required")
    checked_directory(ROOT.parent, 0, 0o755)
    checked_directory(ROOT, 0, 0o711)
    users, groups = directory_ids()
    identities = {}
    ambient = {gid for name, gid in DIRECTORY_GROUPS.items()
               if groups.get(name) == str(gid) and list(groups.values()).count(str(gid)) == 1}
    for role in ROLES:
        name = "_docsuri_r1t_" + role
        uid = int(users[name])
        validate_identity_attributes(name, uid, users, groups)
        memberships = {int(value) for value in command("/usr/bin/id", "-G", name).split()}
        if uid not in memberships or memberships - {uid} - ambient:
            raise RuntimeError("unrecognized directory group privileges")
        checked_directory(ROOT / role, uid, 0o700, uid)
        identities[role] = {"name": name, "uid": uid, "gid": uid,
                            "directoryGroups": sorted(memberships)}
    receipt = (ROOT / "preparation.json").lstat()
    if (
        not stat.S_ISREG(receipt.st_mode) or receipt.st_uid != 0
        or stat.S_IMODE(receipt.st_mode) != 0o600 or receipt.st_nlink != 1
    ):
        raise RuntimeError("preparation receipt metadata mismatch")
    return {"state": "METADATA_VERIFIED", "ready": False, "scope": "account-directory-metadata",
            "identities": identities, "processGroupIsolationRequired": True,
            "observedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "timeQuality": "host-unverified"}


def new_fixture(path, data, uid, gid, mode=0o600):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
    with os.fdopen(descriptor, "wb") as output:
        os.fchown(output.fileno(), uid, gid)
        os.fchmod(output.fileno(), mode)
        output.write(data)
        output.flush()
        os.fsync(output.fileno())


def current_interpreter():
    """Use the actual running image, not Apple's developer-tool/Python.app launch wrappers."""
    if sys.platform != "darwin":
        return Path(sys.executable).resolve(strict=True)
    library = ctypes.CDLL("/usr/lib/libproc.dylib", use_errno=True)
    function = library.proc_pidpath
    function.argtypes = [ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32]
    function.restype = ctypes.c_int
    buffer = ctypes.create_string_buffer(4096)
    size = function(os.getpid(), buffer, len(buffer))
    if not 0 < size < len(buffer):
        raise RuntimeError("native interpreter image unavailable")
    path = Path(buffer.value.decode("utf-8", errors="strict"))
    if not path.is_absolute():
        raise RuntimeError("invalid interpreter image path")
    return path.resolve(strict=True)


def worker_stages(stderr):
    if isinstance(stderr, bytes):
        stderr = stderr.decode("utf-8", errors="replace")
    return [line.removeprefix("R1PROBE:") for line in (stderr or "").splitlines()
            if line.startswith("R1PROBE:") and line.removeprefix("R1PROBE:") in WORKER_STAGES]


def run_probe_worker(interpreter, payload, *, timeout=5):
    """One owned process group; preserve allowlisted progress even when communication times out."""
    data = json.dumps(payload)
    if len(data.encode()) > 65536:
        raise ValueError("probe input too large")
    process = subprocess.Popen(
        [str(interpreter), "-I", "-c", PROBE_PROGRAM],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        cwd="/var/empty", env={"PATH": "/usr/bin:/bin", "LANG": "en_US.UTF-8"},
        user=payload["uid"], group=payload["gid"], extra_groups=(), start_new_session=True,
    )
    started = time.monotonic()
    timed_out, cleanup = False, "not_needed"
    stdout = stderr = ""
    try:
        try:
            stdout, stderr = process.communicate(input=data, timeout=timeout)
        except subprocess.TimeoutExpired as error:
            timed_out = True
            stdout, stderr = error.output or "", error.stderr or ""
            # No poll/wait has reaped this child before signalling: its PID cannot be reused.
            if process.returncode is None:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                    cleanup = "process_group_killed"
                except ProcessLookupError:
                    cleanup = "process_group_already_gone"
            else:
                cleanup = "parent_exited_group_unverified"
            try:
                stdout, stderr = process.communicate(timeout=1)
            except subprocess.TimeoutExpired as remaining:
                stdout, stderr = remaining.output or stdout, remaining.stderr or stderr
                cleanup = "pipe_quiescence_unverified"
                try:
                    process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    cleanup = "parent_quiescence_unverified"
        stages = worker_stages(stderr)
        return {"returncode": process.returncode, "stdout": stdout, "stderr": stderr,
                "timedOut": timed_out,
                "parentReaped": process.returncode is not None, "cleanup": cleanup,
                "stages": stages, "lastStage": stages[-1] if stages else "before_worker_code",
                "elapsedSeconds": round(time.monotonic() - started, 3), "pid": process.pid}
    finally:
        if process.returncode is None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            try:
                process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                pass  # The returned report retains parent_quiescence_unverified, never success.
        for stream in (process.stdin, process.stdout, process.stderr):
            stream.close()


def probe_roles(only_role=None):
    """Explicit operator-only, synthetic file isolation test. Retains all probe artifacts."""
    if platform.system() != "Darwin" or os.geteuid() != 0:
        raise PermissionError("operator root execution required")
    if only_role is not None and only_role not in ROLES:
        raise ValueError("unknown probe role")
    # Do not execute privileged probes from a mutable checkout or writable staging directory.
    script = Path(__file__).absolute()
    for path in (script, *script.parents):
        value = path.lstat()
        if stat.S_ISLNK(value.st_mode) or value.st_uid != 0 or value.st_mode & 0o022:
            raise PermissionError("root-owned protected script staging required")
    observed = check_preparation()
    interpreter = current_interpreter()
    runtime = interpreter.stat()
    if not stat.S_ISREG(runtime.st_mode) or runtime.st_uid != 0 or runtime.st_mode & 0o022:
        raise PermissionError("protected interpreter image required")
    interpreter_digest = hashlib.sha256(interpreter.read_bytes()).hexdigest()
    if shutil.disk_usage(ROOT).free < 10 * 1024**3 + 2 * 1024**2:
        raise RuntimeError("probe disk reserve insufficient")
    probe_root = Path(tempfile.mkdtemp(prefix="role-probe-", dir=ROOT))
    probe_root.chmod(0o711)
    token = secrets.token_hex(16)
    owned = {}
    for role, identity in observed["identities"].items():
        folder = probe_root / role
        folder.mkdir(mode=0o700)
        os.chown(folder, identity["uid"], identity["gid"])
        owned[role] = folder / "sentinel"
        new_fixture(owned[role], token.encode(), identity["uid"], identity["gid"])
    group_files = []
    for name, gid in DIRECTORY_GROUPS.items():
        path = probe_root / (name + ".sentinel")
        new_fixture(path, b"synthetic-group-probe", 0, gid, 0o640)
        group_files.append(str(path))
    results, interrupted = {}, False
    requested = (only_role,) if only_role else ROLES
    for role in requested:
        if interrupted:
            results[role] = {"state": "NOT_RUN", "reason": "previous_worker_timeout"}
            continue
        identity = observed["identities"][role]
        uid, gid = identity["uid"], identity["gid"]
        payload = {"uid": uid, "gid": gid, "token": token, "own": str(owned[role]),
                   "others": [str(path) for other, path in owned.items() if other != role],
                   "groupFiles": group_files}
        diagnostics = {"lastStage": "before_worker_code"}
        try:
            launch = run_probe_worker(interpreter, payload)
            diagnostics = {key: value for key, value in launch.items()
                           if key not in {"stdout", "stderr"}}
            errors = launch["stderr"]
            if isinstance(errors, str):
                errors = errors.encode("utf-8", errors="replace")
            error_file = role + ".stderr.log"
            new_fixture(probe_root / error_file, errors[:65536], 0, 0)
            diagnostics.update({"stderrFile": error_file, "stderrBytes": len(errors),
                                "stderrTruncated": len(errors) > 65536})
            if launch["timedOut"] or not launch["parentReaped"]:
                results[role] = {"state": "BLOCKED", "reason": "TimeoutExpired",
                                 "worker": diagnostics}
                interrupted = True
                continue
            result = json.loads(launch["stdout"])
            if not isinstance(result, dict):
                raise RuntimeError("invalid probe result")
            if launch["returncode"]:
                known = {"process_identity", "effective_groups", "fixture_mismatch",
                         "cross_role_access", "ambient_group_access", "fixture_not_regular",
                         "probe_input_limit", "kernel_group_query", "kernel_group_query_changed",
                         "PermissionError", "OSError", "ValueError", "FileNotFoundError"}
                reason = result.get("reason")
                results[role] = {"state": "BLOCKED", "worker": diagnostics,
                                 "reason": reason if isinstance(reason, str) and reason in known
                                 else "probe_worker_failed"}
                continue
            if (
                result.get("uid") != uid or result.get("gid") != gid
                or set(result.get("groups", [0])) - {gid}
                or result.get("ownReadWrite") is not True
                or result.get("crossReadDenied") != len(ROLES) - 1
                or result.get("crossWriteDenied") != len(ROLES) - 1
                or result.get("directoryGroupReadDenied") != len(group_files)
            ):
                raise RuntimeError("probe result incomplete")
            descriptor = os.open(owned[role], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            with os.fdopen(descriptor, "rb") as source:
                value = os.fstat(source.fileno())
                if (
                    not stat.S_ISREG(value.st_mode) or value.st_nlink != 1
                    or value.st_uid != uid or value.st_gid != gid
                    or source.read(4097) != (token + ":verified").encode()
                ):
                    raise RuntimeError("probe write witness mismatch")
            results[role] = {"state": "VERIFIED", "worker": diagnostics, **result}
        except (OSError, ValueError, TypeError, RuntimeError, subprocess.SubprocessError) as error:
            results[role] = {"state": "BLOCKED", "reason": type(error).__name__,
                             "worker": diagnostics}
    passed = all(result["state"] == "VERIFIED" for result in results.values())
    success = (
        "ROLE_FILE_ISOLATION_VERIFIED" if not only_role
        else "PARTIAL_ROLE_FILE_ISOLATION_VERIFIED"
    )
    report = {"state": success if passed else "BLOCKED", "ready": False,
              "scope": "synthetic-file-access-only", "probeRoot": str(probe_root),
              "roles": results, "requestedRoles": requested,
              "completeRoleCoverage": passed and len(results) == len(ROLES),
              "processLaunch": {"supplementaryGroups": [], "timeoutSeconds": 5,
                                "interpreter": str(interpreter),
                                "interpreterSha256": interpreter_digest,
                                "selection": "current-native-process-image"},
              "remaining": ["installed_launcher_group_policy", "keychain_acl", "nts_clock",
                            "database_mtls_roles", "native_commit_guard", "filevault",
                            "encrypted_backup_restore", "load_acceptance"]}
    new_fixture(probe_root / "probe.json", json.dumps(report, indent=2).encode(), 0, 0)
    return report


def prepare():
    if platform.system() != "Darwin" or os.geteuid() != 0:
        raise PermissionError("operator must run reviewed preparation locally with sudo")
    parent = ROOT.parent
    if parent.is_symlink():
        raise RuntimeError("DocSuri root must not be a symlink")
    if not parent.exists():
        parent.mkdir(mode=0o755)
    if parent.stat().st_uid != 0 or parent.stat().st_mode & 0o022:
        raise RuntimeError("DocSuri parent must be root-owned and non-writable by other roles")
    secure_directory(ROOT)
    ROOT.chmod(0o711)  # Traverse to an owned role directory; other roles cannot list the realm.
    users, groups = directory_ids()
    used = {int(value) for value in (*users.values(), *groups.values())}
    identities = {}
    for role in ROLES:
        name = "_docsuri_r1t_" + role
        if name in users:
            if name not in groups or users[name] != groups[name]:
                raise RuntimeError("pre-existing test identity has inconsistent group")
            uid = int(users[name])
            validate_existing_identity(name, uid, users, groups)
        elif name in groups:
            raise RuntimeError("pre-existing test group has no matching user")
        else:
            uid = next(number for number in range(600, 4000) if number not in used)
            used.add(uid)
            command("/usr/bin/dscl", ".", "-create", "/Groups/" + name)
            command("/usr/bin/dscl", ".", "-create", "/Groups/" + name, "PrimaryGroupID", str(uid))
            command("/usr/bin/dscl", ".", "-create", "/Users/" + name)
            for attribute, value in {
                "UniqueID": str(uid), "PrimaryGroupID": str(uid), "UserShell": "/usr/bin/false",
                "NFSHomeDirectory": "/var/empty", "IsHidden": "1",
                "RealName": "DocSuri isolated REM-1 " + role,
            }.items():
                command("/usr/bin/dscl", ".", "-create", "/Users/" + name, attribute, value)
        secure_directory(ROOT / role, uid)
        os.chown(ROOT / role, uid, uid)
        identities[role] = {"name": name, "uid": uid, "gid": uid}
    manifest = {"profile": "rem-1-test", "root": str(ROOT), "identities": identities,
                "state": "PREPARED_NOT_ACCEPTED",
                "remaining": ["keychain_acl", "nts_clock", "database_mtls_roles",
                              "native_commit_guard",
                              "filevault", "encrypted_backup_restore", "load_acceptance"]}
    target = ROOT / "preparation.json"
    if target.is_symlink():
        raise RuntimeError("invalid preparation receipt path")
    descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "w") as output:
        json.dump(manifest, output, indent=2)
        output.flush()
        os.fsync(output.fileno())
    return manifest


def main():
    parser = argparse.ArgumentParser()
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--apply", action="store_true")
    actions.add_argument("--check", action="store_true", help="readonly metadata inspection")
    actions.add_argument("--probe", action="store_true", help="operator-only synthetic access test")
    parser.add_argument("--role", choices=ROLES, help="probe one role for bounded diagnosis")
    args = parser.parse_args()
    if args.role and not args.probe:
        parser.error("--role requires --probe")
    try:
        if args.check:
            result = check_preparation()
        elif args.probe:
            result = probe_roles(only_role=args.role)
        elif args.apply:
            result = prepare()
        else:
            result = {"state": "PLAN_ONLY", "root": str(ROOT), "roles": ROLES,
                      "operatorAuthenticationRequired": True}
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.SubprocessError) as error:
        result = {"state": "BLOCKED", "reason": type(error).__name__}
    print(json.dumps(result, indent=2))
    return 2 if result["state"] == "BLOCKED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
