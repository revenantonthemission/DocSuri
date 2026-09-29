#!/usr/bin/env python3
"""Digest-bound repair of two installed r1t-clock-20260927 plists; plan-only by default."""

import argparse
import copy
import hashlib
import json
import os
import platform
import plistlib
import stat
import subprocess
import tempfile
from pathlib import Path
from types import ModuleType

BUNDLE_SHA = "509b5074da51eebe58cadb8b4527d3ab6c2c961f4bf15e6e2f3f971e75da1752"
PROVISIONER_SHA = "efb6145be5dff0f3ab0d087fe27c0c3e9b12746574342cba6a59d3f1cef3eb67"
DEPLOYMENT_SHA = "ac0c16bb5bf6baa5a502464a4a1f0807b0395eabe6a768abd3d06df0c47bdd26"
ROOT = Path("/Library/Application Support/DocSuri/rem-1-test")
DAEMONS = Path("/Library/LaunchDaemons")
PREIMAGES = {
    "nts-observer": "ab40d8a3fa832064e91555228b34a36e100e74111b96a3d250b1d31f40fd7160",
    "clock-sample": "3f059ce1178218ed4f815d42a069e81cf66b77bd5d7adea92cde649558519c44",
}
ENV = {"PATH": "/usr/bin:/bin:/usr/sbin:/sbin", "HOME": "/var/empty", "LANG": "en_US.UTF-8"}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def protected_path(path):
    for parent in path.parents:
        info = parent.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
            raise PermissionError("protected root-owned ancestor required")
    info = path.lstat()
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_nlink != 1
        or info.st_mode & 0o022):
        raise PermissionError("protected root-owned file required")


def read_regular(path, limit=256 * 1024):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > limit:
            raise ValueError("invalid repair input")
        data = stream.read(limit + 1)
        if len(data) > limit:
            raise ValueError("repair input too large")
        return data


def require_operator():
    if (platform.system() != "Darwin" or platform.machine() != "arm64"
        or os.getuid() != 0 or os.geteuid() != 0):
        raise PermissionError("operator root execution required")
    protected_path(Path(__file__).absolute())


def provisioner(path):
    if os.geteuid() == 0:
        require_operator()
        protected_path(path)
    source = read_regular(path)
    if sha(source) != PROVISIONER_SHA:
        raise ValueError("original provisioner digest differs")
    module = ModuleType("reviewed_clock_provisioner")
    module.__file__ = str(path)
    exec(compile(source, str(path), "exec"), module.__dict__)
    return module


def repaired_plist(name, raw):
    """Only exact original or already-repaired bytes may enter this three-field transform."""
    before = plistlib.loads(raw)
    before["UserName"] = before["GroupName"] = "_docsuri_r1t_clock"
    arguments = before["ProgramArguments"]
    if arguments[7] == "-B":
        del arguments[7]
    original = plistlib.dumps(before, sort_keys=True)
    if sha(original) != PREIMAGES[name]:
        raise ValueError("unrecognized clock plist")
    after = copy.deepcopy(before)
    after["UserName"], after["GroupName"] = "root", "wheel"
    after["ProgramArguments"].insert(7, "-B")
    repaired = plistlib.dumps(after, sort_keys=True)
    if raw not in (original, repaired):
        raise ValueError("partially modified or foreign clock plist")
    return repaired


def prepare(work, provisioner_path):
    tool = provisioner(provisioner_path)
    manifest = tool.verify_bundle(work, BUNDLE_SHA)
    if (manifest["release"] != "r1t-clock-20260927"
        or (manifest["uid"], manifest["gid"]) != (608, 608)):
        raise ValueError("unexpected installed clock identity")
    identity = tool.pwd.getpwnam("_docsuri_r1t_clock")
    if (identity.pw_uid, identity.pw_gid) != (608, 608):
        raise PermissionError("clock account changed")
    for item in manifest["files"]:
        tool.verify_installed_file(tool.destination(manifest["release"], item["path"]),
                                   item["sha256"])
    tool.verify_installed_file(ROOT / "deployment.json", DEPLOYMENT_SHA)
    ca = Path("/private") / tool.clock_ca_path(manifest["systemCaSha256"]).relative_to("/")
    tool.verify_installed_file(ca, manifest["systemCaSha256"])
    entries = []
    for name in PREIMAGES:
        label = "org.docsuri.rem1.test." + name
        path = DAEMONS / (label + ".plist")
        protected_path(path)
        raw = read_regular(path)
        entries.append((label, path, raw, repaired_plist(name, raw)))
    return entries


def launchctl(*args, absent_ok=False):
    result = subprocess.run(["/bin/launchctl", *args], env=ENV, stdin=subprocess.DEVNULL,
                            capture_output=True, text=True, timeout=30, check=False)
    if result.returncode and not (absent_ok and result.returncode in (2, 3)):
        raise RuntimeError("launchctl " + args[0] + ": " + result.stderr.strip()[:500])
    return result.stdout


def replace_plist(path, before, after):
    protected_path(path)
    if read_regular(path) != before:
        raise PermissionError("plist changed after preflight")
    fd, temporary = tempfile.mkstemp(prefix=".docsuri-clock-groups-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as output:
            output.write(after)
            output.flush()
            os.fchmod(output.fileno(), 0o644)
            os.fsync(output.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
        if read_regular(path) != after:
            raise ValueError("repaired plist differs")
    finally:
        Path(temporary).unlink(missing_ok=True)


def repair(work, provisioner_path, *, apply=False):
    if apply:
        require_operator()
    entries = prepare(work, provisioner_path)
    result = {"state": "PLAN_ONLY", "accepted": False, "bundleSha256": BUNDLE_SHA,
              "bootstrapUid": 0, "targetUid": 608, "targetGid": 608,
              "plists": [{"label": label, "beforeSha256": sha(before), "afterSha256": sha(after)}
                         for label, _, before, after in entries]}
    if not apply:
        return result
    stopped = []
    for label, _, _, _ in entries:
        launchctl("bootout", "system/" + label, absent_ok=True)
        stopped.append(label)
    # No old sample should survive a launcher/identity repair.
    (ROOT / "clock-public/current.json").unlink(missing_ok=True)
    for _, path, before, after in entries:
        replace_plist(path, before, after)
    started = []
    try:
        for label, path, _, _ in entries:
            launchctl("bootstrap", "system", str(path))
            started.append(label)
        for label, _, _, _ in entries:
            launchctl("print", "system/" + label)
    except BaseException as failure:
        cleanup_failed = []
        # A failed/lost bootstrap reply does not prove the job was never registered.
        for label, _, _, _ in entries:
            try:
                launchctl("bootout", "system/" + label, absent_ok=True)
            except Exception:
                cleanup_failed.append(label)
        if cleanup_failed:
            raise RuntimeError("repair failed; stop unconfirmed: " + ",".join(cleanup_failed)) \
                from failure
        raise
    return {**result, "state": "REPAIRED_NOT_ACCEPTED", "stopped": stopped, "started": started}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", required=True, type=Path)
    parser.add_argument("--provisioner", required=True, type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        result = repair(args.work.resolve(), args.provisioner.absolute(), apply=args.apply)
        print(json.dumps(result))
        return 0
    except Exception as error:
        print(json.dumps({"state": "BLOCKED", "accepted": False,
                          "reason": type(error).__name__, "detail": str(error)[:500]}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
