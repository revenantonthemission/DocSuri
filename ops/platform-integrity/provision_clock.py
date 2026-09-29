#!/usr/bin/env python3
"""Pinned unprivileged clock preparation and operator-only test-realm installation.

The observer never adjusts the system clock. Build artifacts and a rehearsal are not a
host capability receipt; installed role/clock acceptance is checked separately.
"""

import argparse
import hashlib
import io
import json
import os
import platform
import posixpath
import pwd
import re
import shutil
import signal
import stat
import subprocess
import tarfile
import tempfile
import time
import urllib.request
from pathlib import Path, PurePosixPath

CHRONY_VERSION = "4.9"
CHRONY_URL = "https://chrony-project.org/releases/chrony-4.9.tar.gz"
CHRONY_SHA = "4924c6f530105bcd5b9e9e33c48a2ae1bfd889222c8480bc41601110efc864d0"
PYTHON_VERSION = "3.13.15"
PYTHON_URL = ("https://github.com/astral-sh/python-build-standalone/releases/download/20260924/"
              "cpython-3.13.15%2B20260924-aarch64-apple-darwin-install_only_stripped.tar.gz")
PYTHON_SHA = "064afb7c2fc0bbf511d886288adf98696af5105e36c138cdf2c199c0146fcf68"
TARFILE_CVE = "CVE-2026-82049"
TARFILE_COMMIT = "b8f23e307097552eaea2604383a12ab280520d0d"
TARFILE_PATH = "runtime/lib/python3.13/tarfile.py"
TARFILE_BEFORE_SHA = "9fedddf7e814c226cb7e1ac0aa603092eda40047367ec00ad740a81484a17d01"
TARFILE_AFTER_SHA = "7ad04a66bb92373bd6d2552a2f01fce8a4ca95463ebf661612fd574465977929"
ROOT = Path("/Library/Application Support/DocSuri/rem-1-test")
SOCKET_ROOT = Path("/var/db/docsuri/rem1-test/clock")
SYSTEM_CA = Path("/etc/ssl/cert.pem")
MAX_BYTES = 512 * 1024**2
MAX_FILES = 10_000
ENV = {"PATH": "/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin", "LANG": "en_US.UTF-8",
       "HOME": "/var/empty", "PYTHONDONTWRITEBYTECODE": "1"}
MACHO = {b"\xcf\xfa\xed\xfe", b"\xfe\xed\xfa\xcf", b"\xca\xfe\xba\xbe", b"\xbe\xba\xfe\xca"}


def fingerprint(data):
    return hashlib.sha256(data).hexdigest()


def json_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def relative_name(name):
    if not isinstance(name, str):
        raise ValueError("unsafe bundle path")
    path = PurePosixPath(name)
    if (not isinstance(name, str) or not name or path.is_absolute() or ".." in path.parts
        or str(path) != name or any(c in name for c in "\x00\r\n\\")):
        raise ValueError("unsafe bundle path")
    return path


def download(url, expected, destination):
    if destination.exists() or destination.is_symlink():
        info = destination.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_size > 64 * 1024**2:
            raise ValueError("unsafe archive cache")
        content = destination.read_bytes()
    else:
        with urllib.request.urlopen(url, timeout=60) as response:
            content = response.read(64 * 1024**2 + 1)
    if len(content) > 64 * 1024**2 or fingerprint(content) != expected:
        raise ValueError("archive digest mismatch")
    if not destination.exists():
        with destination.open("xb") as output:
            output.write(content)
    return content


def extract_archive(content, destination, prefix):
    """Validate the entire pinned archive before extracting; only internal file aliases allowed."""
    with tarfile.open(fileobj=io.BytesIO(content), mode="r:gz") as archive:
        entries = archive.getmembers()
        if len(entries) > MAX_FILES or sum(item.size for item in entries) > MAX_BYTES:
            raise ValueError("archive size limit")
        names = set()
        for item in entries:
            name = item.name.rstrip("/")
            relative_name(name)
            if name.split("/")[0] != prefix or name in names:
                raise ValueError("archive namespace or duplicate path")
            names.add(name)
            # Never let the bootstrap interpreter materialize hard links to symlinks. This
            # avoids the vulnerable pre-3.14 tarfile path even before the runtime is patched.
            if not (item.isfile() or item.isdir() or item.issym()):
                raise ValueError("unsupported archive member")
            if item.issym():
                if PurePosixPath(item.linkname).is_absolute():
                    raise ValueError("external archive link")
                target = posixpath.normpath(posixpath.join(posixpath.dirname(name), item.linkname))
                if target.split("/")[0] != prefix:
                    raise ValueError("external archive link")
        destination.mkdir(mode=0o700)
        archive.extractall(destination, filter="data")
    return destination / prefix


def freeze_tree(source, destination):
    """Snapshot a verified source tree, dereferencing bounded internal aliases only."""
    root = source.resolve()
    count, total = 0, 0

    def copy(current, target, ancestors):
        nonlocal count, total
        resolved = current.resolve(strict=True)
        resolved.relative_to(root)
        info = resolved.stat()
        if stat.S_ISDIR(info.st_mode):
            if resolved in ancestors:
                raise ValueError("source alias cycle")
            target.mkdir(mode=0o755)
            for child in sorted(resolved.iterdir()):
                if child.name == "__pycache__" or child.suffix == ".pyc":
                    continue
                copy(child, target / child.name, ancestors | {resolved})
        elif stat.S_ISREG(info.st_mode):
            count, total = count + 1, total + info.st_size
            if count > MAX_FILES or total > MAX_BYTES:
                raise ValueError("source closure limit")
            data = resolved.read_bytes()
            with target.open("xb") as output:
                output.write(data)
            target.chmod(0o755 if info.st_mode & 0o111 else 0o644)
        else:
            raise ValueError("unsupported source object")

    copy(source, destination, set())


def run(argv, *, cwd=None, timeout=300, env=None):
    return subprocess.run([str(value) for value in argv], cwd=cwd, env=env or ENV,
                          stdin=subprocess.DEVNULL, capture_output=True, text=True,
                          timeout=timeout, check=True).stdout


def fetch_sources(work):
    if os.geteuid() == 0 or platform.system() != "Darwin" or platform.machine() != "arm64":
        raise PermissionError("unprivileged Darwin arm64 build required")
    if shutil.disk_usage(work.parent).free < 10 * 1024**3 + 2 * MAX_BYTES:
        raise ValueError("clock preparation disk reserve")
    work.mkdir(mode=0o700, exist_ok=False)
    chrony = download(CHRONY_URL, CHRONY_SHA, work / "chrony.tar.gz")
    python = download(PYTHON_URL, PYTHON_SHA, work / "python.tar.gz")
    extract_archive(chrony, work / "chrony-source", "chrony-" + CHRONY_VERSION)
    extract_archive(python, work / "python-source", "python")
    return {"state": "SOURCES_VERIFIED", "chrony": CHRONY_VERSION, "python": PYTHON_VERSION,
            "chronySha256": CHRONY_SHA, "pythonSha256": PYTHON_SHA, "work": str(work)}


def is_macho(path):
    with path.open("rb") as source:
        return source.read(4) in MACHO


def load_commands(path):
    dependencies = []
    for line in run(["/usr/bin/otool", "-L", path]).splitlines()[1:]:
        if " (compatibility version " in line:
            dependencies.append(line.strip().split(" (compatibility version ", 1)[0])
    ids = run(["/usr/bin/otool", "-D", path]).splitlines()[1:]
    own_id = ids[0].strip() if ids else None
    rpaths, in_rpath = [], False
    for line in run(["/usr/bin/otool", "-l", path]).splitlines():
        value = line.strip()
        if value.startswith("cmd "):
            in_rpath = value == "cmd LC_RPATH"
        if in_rpath and value.startswith("path "):
            rpaths.append(value[5:].rsplit(" (offset ", 1)[0])
    return [name for name in dependencies if name != own_id], rpaths, own_id


def system_library(name):
    return name.startswith(("/usr/lib/", "/System/Library/"))


def relocate_macho(bundle, origins):
    """Close every non-system load edge, copy Homebrew dependencies, and remove ambient rpaths."""
    library = bundle / "native" / "lib"
    library.mkdir(mode=0o755)
    original_to_copy = {Path(origin).resolve(): target for target, origin in origins.items()}
    queue = [path for path in sorted(bundle.rglob("*")) if path.is_file() and is_macho(path)]
    provenance, seen = [], set()
    executable = bundle / "runtime/bin"
    _, inherited, _ = load_commands(executable / "python3.13")

    def expanded(value, origin):
        return Path(value.replace("@loader_path", str(origin.parent))
                    .replace("@executable_path", str(executable)))

    while queue:
        target = queue.pop(0)
        if target in seen:
            continue
        seen.add(target)
        origin = Path(origins.get(target, target)).resolve()
        deps, rpaths, own_id = load_commands(target)
        for dependency in deps:
            if system_library(dependency):
                continue
            if dependency.startswith("@rpath/"):
                roots = [expanded(value, origin) for value in rpaths]
                # Python extension modules inherit the executable's declared runtime search path.
                roots.extend(expanded(value, executable / "python3.13") for value in inherited)
                candidates = [base / dependency[len("@rpath/"):] for base in roots]
                matches = {path.resolve() for path in candidates if path.is_file()}
                if len(matches) != 1:
                    raise ValueError("unresolved or ambiguous Mach-O rpath: " + dependency)
                source = matches.pop()
            else:
                source = expanded(dependency, origin).resolve(strict=True)
            if source.is_relative_to(bundle):
                copied = source
            else:
                if not source.is_relative_to(Path("/opt/homebrew/Cellar")) or not source.is_file():
                    raise ValueError("unexpected native dependency: " + str(source))
                copied = original_to_copy.get(source)
                if copied is None:
                    copied = library / (fingerprint(str(source).encode())[:12] + "-" + source.name)
                    shutil.copyfile(source, copied)
                    copied.chmod(0o755)
                    original_to_copy[source] = copied
                    origins[copied] = source
                    provenance.append({"source": str(source),
                                       "sourceSha256": fingerprint(source.read_bytes()),
                                       "file": str(copied.relative_to(bundle))})
                    queue.append(copied)
            replacement = "@loader_path/" + os.path.relpath(copied, target.parent)
            run(["/usr/bin/install_name_tool", "-change", dependency, replacement, target])
        for entry in rpaths:
            run(["/usr/bin/install_name_tool", "-delete_rpath", entry, target])
        if own_id:
            run(["/usr/bin/install_name_tool", "-id", "@loader_path/" + target.name, target])
        run(["/usr/bin/codesign", "--force", "--sign", "-", target])
    verify_load_closure(bundle)
    return provenance


def verify_load_closure(bundle):
    for file in sorted(bundle.rglob("*")):
        if not file.is_file() or not is_macho(file):
            continue
        deps, rpaths, _ = load_commands(file)
        if rpaths:
            raise ValueError("ambient Mach-O rpath remains")
        for dependency in deps:
            if system_library(dependency):
                continue
            if not dependency.startswith("@loader_path/"):
                raise ValueError("unfrozen load edge")
            resolved = (file.parent / dependency[len("@loader_path/"):]).resolve(strict=True)
            resolved.relative_to(bundle)
            if resolved.is_symlink() or not resolved.is_file():
                raise ValueError("invalid frozen load edge")


def verify_python_closure(bundle):
    runtime = bundle / "runtime"
    for path in runtime.rglob("*"):
        if (path.suffix in {".pth", "._pth"}
            or path.name in {"sitecustomize.py", "usercustomize.py"}):
            raise ValueError("ambient Python import hook")
    paths = json.loads(run([runtime / "bin/python3.13","-I","-B","-c",
                            "import json,sys; print(json.dumps(sys.path))"]))
    for value in paths:
        Path(value).resolve().relative_to(runtime)


def clock_ca_path(digest):
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ValueError("invalid CA digest")
    return SOCKET_ROOT.parent / ("ca-" + digest + ".pem")


def observer_config(socket_root, user="_docsuri_r1t_clock", trust=SYSTEM_CA):
    # chrony tokenizes whitespace rather than shell quoting. Keep runtime paths short/space-free.
    if (any(char.isspace() for char in str(socket_root) + str(trust))
        or len(str(socket_root / "chronyc.9999999" / ("f" * 16) / "sock")) >= 104):
        raise ValueError("unsupported native socket path")
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]{0,63}", user):
        raise ValueError("invalid observer identity")
    return (f"user {user}\nserver time.cloudflare.com iburst nts minpoll 4 maxpoll 4\n"
            "authselectmode require\nport 0\ncmdport 0\n"
            f"nosystemcert\nntstrustedcerts {trust}\n"
            f"bindcmdaddress {socket_root}/chronyd.sock\n"
            f"pidfile {socket_root}/chronyd.pid\n"
            f"driftfile {socket_root}/chrony.drift\n"
            f"ntsdumpdir {socket_root}/nts\n").encode()


def pinned_artifact(path):
    """Bytecode is a derived cache, never a deployment invariant.

    freeze_tree already keeps .pyc out of the frozen tree, but inventory() walks the built
    bundle, so a run that lacked -B before inventory can leave bytecode behind and get it
    pinned. Once pinned, the next such run rewrites it in place and execute() refuses to start,
    which no longer recovers without a rebuild. Keeping it unpinned is the liveness half of the
    same rule freeze_tree applies to the tree itself.
    """
    return ("__pycache__" not in Path(path).parts
            and Path(path).suffix not in {".pyc", ".pyo"})


def inventory(bundle):
    files, total = [], 0
    for path in sorted(bundle.rglob("*")):
        info = path.lstat()
        if stat.S_ISDIR(info.st_mode):
            continue
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ValueError("non-regular bundle artifact")
        name = str(path.relative_to(bundle))
        relative_name(name)
        data = path.read_bytes()
        total += len(data)
        if len(data) > 64 * 1024**2 or total > MAX_BYTES or len(files) >= MAX_FILES:
            raise ValueError("bundle closure limit")
        files.append({"path": name, "sha256": fingerprint(data), "size": len(data),
                      "executable": bool(info.st_mode & 0o111)})
    return files


def destination(release, name):
    path = relative_name(name)
    if path.parts[0] in {"runtime", "native"}:
        return ROOT / "toolchains" / release / name
    if path.parts[0] == "config" and len(path.parts) == 2:
        return ROOT / "releases" / release / path.name
    raise ValueError("unrecognized bundle destination")


def seal_bundle(work, release):
    from docsuri_platform_integrity.contracts.codec import canonical, digest
    from docsuri_platform_integrity.deployment.launchd import (
        LaunchEntry,
        LaunchManifest,
        validate_manifest,
    )
    from docsuri_platform_integrity.host import HostConfiguration, validate_configuration

    bundle = work / "bundle"
    patch = apply_tarfile_backport(work)
    if not re.fullmatch(r"r1t-clock-[a-z0-9-]{1,60}", release):
        raise ValueError("test clock release name required")
    principal = pwd.getpwnam("_docsuri_r1t_clock")
    uid, gid = principal.pw_uid, principal.pw_gid
    if uid < 600 or uid != gid:
        raise ValueError("prepared clock identity required")
    config = bundle / "config"
    config.mkdir(mode=0o755, exist_ok=True)
    ca = read_regular(SYSTEM_CA.resolve(strict=True))
    (config / "nts-ca.pem").write_bytes(ca)
    chrony = observer_config(SOCKET_ROOT, trust=clock_ca_path(fingerprint(ca)))
    (config / "chrony.conf").write_bytes(chrony)
    configuration = HostConfiguration(
        profile="test", role="clock", uid=uid, gid=gid, clock_uid=uid,
        clock_frame=str(ROOT / "clock-public/current.json"), clock_config_digest=digest(chrony),
        chronyc=str(destination(release, "native/chronyc")),
        chronyc_digest=digest((bundle / "native/chronyc").read_bytes()),
        chrony_socket=str(SOCKET_ROOT / "chronyd.sock"),
    )
    validate_configuration(configuration)
    (config / "clock.json").write_bytes(canonical(configuration.model_dump(mode="json")))
    # The launch manifest cannot include its own hash.
    files = [item for item in inventory(bundle) if item["path"] != "config/deployment.json"]
    python = str(destination(release, "runtime/bin/python3.13"))
    entries = (
        LaunchEntry(name="nts-observer",role="clock",uid=uid,gid=gid,mode="observer",argv=(
            str(destination(release,"native/chronyd")),"-x","-U","-d","-f",
            str(destination(release,"config/chrony.conf")))),
        LaunchEntry(name="clock-sample",role="clock",uid=uid,gid=gid,mode="periodic",interval=5,
                    argv=(python,"-I","-B","-m","docsuri_platform_integrity.host","clock","--config",
                          str(destination(release,"config/clock.json")))),
    )
    launch = LaunchManifest(profile="test",release=release,python=python,entries=entries,
                            artifacts=tuple((str(destination(release,item["path"])),
                                             "sha256:"+item["sha256"]) for item in files))
    validate_manifest(launch)
    (config / "deployment.json").write_bytes(canonical(launch.model_dump(mode="json")))
    manifest = {"kind": "docsuri.clock-bundle.v1", "release": release, "uid": uid, "gid": gid,
                "chrony": CHRONY_VERSION, "chronySourceSha256": CHRONY_SHA,
                "python": PYTHON_VERSION, "pythonSourceSha256": PYTHON_SHA,
                "installerSha256": fingerprint(Path(__file__).read_bytes()),
                "systemCaSha256": fingerprint(ca),
                "runtimePatch": patch,
                "files": inventory(bundle)}
    encoded = json_bytes(manifest)
    (work / "bundle.json").write_bytes(encoded)
    return {"state": "PREPARED_NOT_INSTALLED", "manifest": str(work / "bundle.json"),
            "manifestSha256": fingerprint(encoded), "files": len(manifest["files"]),
            "bytes": sum(item["size"] for item in manifest["files"])}


def build(work, release):
    if os.geteuid() == 0 or platform.system() != "Darwin" or platform.machine() != "arm64":
        raise PermissionError("unprivileged Darwin arm64 build required")
    project = Path(__file__).resolve().parents[2] / "platform_integrity"
    uv = shutil.which("uv")
    if uv is None:
        raise ValueError("uv unavailable")
    uv_command = [uv, "--cache-dir", work / "uv-cache"]
    # Revalidate fetched inputs, including extraction if the work directory was retained.
    chrony = download(CHRONY_URL, CHRONY_SHA, work / "chrony.tar.gz")
    python = download(PYTHON_URL, PYTHON_SHA, work / "python.tar.gz")
    source = extract_archive(chrony, work / "build-source", "chrony-" + CHRONY_VERSION)
    runtime_source = extract_archive(python, work / "runtime-source", "python")
    bundle = work / "bundle"
    bundle.mkdir(mode=0o700)
    freeze_tree(runtime_source, bundle / "runtime")
    native = bundle / "native"
    native.mkdir(mode=0o755)
    build_env = dict(ENV, CC="/usr/bin/clang", CFLAGS="-O2 -mmacosx-version-min=14.0",
                     LDFLAGS="-Wl,-headerpad_max_install_names")
    run([source / "configure", "--prefix=/usr/local", "--disable-readline", "--disable-refclock",
         "--disable-rtc"], cwd=source, env=build_env)
    run(["/usr/bin/make", "-j2"], cwd=source, env=build_env)
    for name in ("chronyd", "chronyc"):
        shutil.copyfile(source / name, native / name)
        (native / name).chmod(0o755)
    run([*uv_command, "build", "--wheel", "--out-dir", work / "wheels", project], cwd=project)
    requirements = run([*uv_command,"export","--frozen","--no-dev",
                        "--no-emit-project","--no-editable",
                        "--no-header"], cwd=project)
    (work / "requirements.txt").write_text(requirements)
    interpreter = bundle / "runtime/bin/python3.13"
    run([*uv_command,"pip","install","--python",interpreter,"--link-mode","copy",
         "--require-hashes","--only-binary",":all:",
         "-r",work / "requirements.txt"], cwd=work)
    wheels = tuple((work / "wheels").glob("docsuri_platform_integrity-*.whl"))
    if len(wheels) != 1:
        raise ValueError("ambiguous first-party wheel")
    run([*uv_command,"pip","install","--python",interpreter,"--link-mode","copy",
         "--no-deps",wheels[0]], cwd=work)
    # Only the real interpreter is an entry point; remove source-prefix helper scripts/aliases.
    for path in (bundle / "runtime/bin").iterdir():
        if path.name != "python3.13":
            if not path.is_file() or path.is_symlink():
                raise ValueError("unexpected runtime bin member")
            path.unlink()
    provenance = relocate_macho(
        bundle, {native / name: source / name for name in ("chronyd","chronyc")},
    )
    (work / "native-dependencies.json").write_bytes(json_bytes(provenance))
    verify_python_closure(bundle)
    run([interpreter,"-I","-B","-c",
         "from docsuri_platform_integrity.host import HostConfiguration; "
         "from docsuri_platform_integrity.adapters.nts import native_time; "
         "print(native_time().boot_id)"], cwd=work)
    version = run([native / "chronyd", "--version"])
    if "version 4.9" not in version or "+NTS" not in version:
        raise ValueError("required chrony/NTS build unavailable")
    return seal_bundle(work, release)


def refresh_package(work, release):
    if os.geteuid() == 0:
        raise PermissionError("unprivileged package build required")
    project = Path(__file__).resolve().parents[2] / "platform_integrity"
    uv = shutil.which("uv")
    if uv is None:
        raise ValueError("uv unavailable")
    command = [uv,"--cache-dir",work / "uv-cache"]
    run([*command,"build","--wheel","--out-dir",work / "wheels",project], cwd=project)
    wheel, = (work / "wheels").glob("docsuri_platform_integrity-*.whl")
    python = work / "bundle/runtime/bin/python3.13"
    run([*command,"pip","install","--python",python,"--no-deps","--reinstall",
         "--link-mode","copy",wheel], cwd=work)
    entry = work / "bundle/runtime/bin/docsuri-integrity"
    if entry.is_file() and not entry.is_symlink():
        entry.unlink()
    verify_load_closure(work / "bundle")
    verify_python_closure(work / "bundle")
    return seal_bundle(work, release)


def apply_tarfile_backport(work):
    """Exact PSF 3.13 backport, against bytes from the pinned standalone archive."""
    if os.geteuid() == 0:
        raise PermissionError("runtime patching must be unprivileged")
    raw = download(PYTHON_URL, PYTHON_SHA, work / "python.tar.gz")
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as archive:
        entries = [item for item in archive.getmembers()
                   if item.name == "python/lib/python3.13/tarfile.py"]
        if len(entries) != 1 or not entries[0].isfile():
            raise ValueError("pinned tarfile module missing")
        with archive.extractfile(entries[0]) as stream:
            original = stream.read(512 * 1024 + 1)
    old = b"                    os.link(tarinfo._link_target, targetpath)"
    new = (b"                    # Resolve the target so the hard link points to the file\n"
           b"                    # itself. Otherwise os.link() may duplicate a symlink to a\n"
           b"                    # shallower location, where it's relative target escapes the\n"
           b"                    # destination directory. (CVE-2026-82049)\n"
           b"                    os.link(os.path.realpath(tarinfo._link_target), targetpath)")
    if (len(original) > 512 * 1024 or original.count(old) != 1
        or fingerprint(original) != TARFILE_BEFORE_SHA):
        raise ValueError("vendor patch preimage differs")
    patched = original.replace(old, new)
    if fingerprint(patched) != TARFILE_AFTER_SHA:
        raise ValueError("vendor patch postimage differs")
    path = work / "bundle" / TARFILE_PATH
    if read_regular(path) not in (original, patched):
        raise ValueError("unrecognized staged tarfile module")
    path.write_bytes(patched)
    for bytecode in (path.parent / "__pycache__").glob("tarfile.*.pyc"):
        if not bytecode.is_file() or bytecode.is_symlink():
            raise ValueError("unsafe stale tarfile bytecode")
        bytecode.unlink()
    proof = runtime_patch()
    verify_runtime_patch(work / "bundle", proof)
    return proof


def runtime_patch():
    """Reviewed PSF backport identity; independent of the candidate's own assertions."""
    return {"cve": TARFILE_CVE, "upstreamCommit": TARFILE_COMMIT, "file": TARFILE_PATH,
            "beforeSha256": TARFILE_BEFORE_SHA, "afterSha256": TARFILE_AFTER_SHA}


def verify_runtime_patch(bundle, proof):
    if proof != runtime_patch():
        raise ValueError("unapproved runtime patch metadata")
    path = bundle / TARFILE_PATH
    if fingerprint(read_regular(path, 512 * 1024)) != TARFILE_AFTER_SHA:
        raise ValueError("runtime patch postimage differs")
    shadows = [path.with_suffix(".pyc"), path.with_suffix(".pyo")]
    shadows.extend((path.parent / "__pycache__").glob("tarfile.*.pyc"))
    if any(candidate.exists() or candidate.is_symlink() for candidate in shadows):
        raise ValueError("runtime patch has unverified bytecode")


TARFILE_REGRESSION = """import io,json,stat,sys,tarfile,tempfile
from pathlib import Path
with tempfile.TemporaryDirectory(dir=sys.argv[1]) as directory:
 root=Path(directory)
 outside=root/'escape'
 outside.write_text('private-sentinel')
 outside.chmod(0o600)
 before=outside.stat(); data=io.BytesIO()
 with tarfile.open(fileobj=data,mode='w') as archive:
  entry=tarfile.TarInfo('a/escape')
  entry.size=5
  archive.addfile(entry,io.BytesIO(b'decoy'))
  entry=tarfile.TarInfo('a/b/s')
  entry.type=tarfile.SYMTYPE
  entry.linkname='../escape'
  archive.addfile(entry)
  entry=tarfile.TarInfo('s')
  entry.type=tarfile.LNKTYPE
  entry.linkname='a/b/s'
  archive.addfile(entry)
 for filter in ('data','tar'):
  data.seek(0)
  dest=root/filter
  dest.mkdir()
  with tarfile.open(fileobj=data) as archive:
   archive.extractall(dest,filter=filter)
  assert not (dest/'s').is_symlink()
  assert (dest/'s').read_bytes()==b'decoy'
  assert outside.read_text()=='private-sentinel'
  assert stat.S_IMODE(outside.stat().st_mode)==0o600
  assert outside.stat().st_mtime_ns==before.st_mtime_ns
print(json.dumps({'state':'VENDOR_BACKPORT_VERIFIED',
                  'cve':'CVE-2026-82049',
                  'filters':['data','tar']}))
"""


def verify_tarfile_backport(work, expected):
    """Test the sealed candidate without repairing it or changing any bundle bytes."""
    manifest = verify_bundle(work, expected)
    result = json.loads(run([work / "bundle/runtime/bin/python3.13","-I","-B","-c",
                             TARFILE_REGRESSION,work], timeout=30))
    if result != {"state": "VENDOR_BACKPORT_VERIFIED", "cve": TARFILE_CVE,
                  "filters": ["data", "tar"]}:
        raise ValueError("vendor regression result differs")
    verify_bundle(work, expected)
    result.update(patch=manifest["runtimePatch"], manifestSha256=expected,
                  release=manifest["release"], accepted=False)
    (work / "tarfile-remediation.json").write_bytes(json_bytes(result))
    return result


def read_regular(path, limit=64 * 1024**2):
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


def no_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate manifest key")
        result[key] = value
    return result


def verify_bundle(work, expected):
    raw = read_regular(work / "bundle.json", 4 * 1024**2)
    if not re.fullmatch(r"[0-9a-f]{64}", expected or "") or fingerprint(raw) != expected:
        raise ValueError("reviewed manifest digest required")
    manifest = json.loads(raw, object_pairs_hook=no_duplicate_keys)
    required = {"kind","release","uid","gid","chrony","chronySourceSha256","python",
                "pythonSourceSha256","installerSha256","systemCaSha256","runtimePatch","files"}
    if (not isinstance(manifest, dict) or set(manifest) != required
        or manifest["kind"] != "docsuri.clock-bundle.v1"
        or not re.fullmatch(r"r1t-clock-[a-z0-9-]{1,60}", manifest["release"])
        or manifest["chrony"] != CHRONY_VERSION or manifest["chronySourceSha256"] != CHRONY_SHA
        or manifest["python"] != PYTHON_VERSION or manifest["pythonSourceSha256"] != PYTHON_SHA
        or type(manifest["uid"]) is not int or not 600 <= manifest["uid"] < 4000
        or type(manifest["gid"]) is not int or manifest["gid"] != manifest["uid"]
        or manifest["installerSha256"] != fingerprint(Path(__file__).read_bytes())
        or not isinstance(manifest["files"], list) or not 1 <= len(manifest["files"]) <= MAX_FILES):
        raise ValueError("invalid reviewed clock bundle")
    names, total = set(), 0
    for item in manifest["files"]:
        if (not isinstance(item, dict) or set(item) != {"path","sha256","size","executable"}
            or type(item["size"]) is not int or not 0 <= item["size"] <= 64 * 1024**2
            or type(item["executable"]) is not bool
            or not re.fullmatch(r"[0-9a-f]{64}", item["sha256"])):
            raise ValueError("invalid artifact entry")
        destination(manifest["release"], item["path"])
        if item["path"] in names:
            raise ValueError("duplicate artifact")
        names.add(item["path"])
        data = read_regular(work / "bundle" / item["path"])
        total += len(data)
        if len(data) != item["size"] or fingerprint(data) != item["sha256"] or total > MAX_BYTES:
            raise ValueError("artifact digest mismatch")
    actual = {item["path"] for item in inventory(work / "bundle")}
    if actual != names:
        raise ValueError("unregistered or missing bundle artifact")
    verify_runtime_patch(work / "bundle", manifest["runtimePatch"])
    verify_clock_plan(work / "bundle", manifest)
    return manifest


def verify_clock_plan(bundle, manifest):
    """The privileged install surface is exactly two clock jobs, not arbitrary reviewed JSON."""
    release, uid, gid = manifest["release"], manifest["uid"], manifest["gid"]
    python = str(destination(release, "runtime/bin/python3.13"))
    ca = read_regular(bundle / "config/nts-ca.pem")
    if fingerprint(ca) != manifest["systemCaSha256"]:
        raise ValueError("CA artifact differs from reviewed snapshot")
    chrony = observer_config(SOCKET_ROOT, trust=clock_ca_path(manifest["systemCaSha256"]))
    if read_regular(bundle / "config/chrony.conf") != chrony:
        raise ValueError("observer configuration differs from fixed policy")
    config = json.loads(read_regular(bundle / "config/clock.json"),
                        object_pairs_hook=no_duplicate_keys)
    expected_config = {
        "profile":"test","role":"clock","uid":uid,"gid":gid,"clock_uid":uid,
        "clock_config_digest":"sha256:"+fingerprint(chrony),
        "clock_frame":str(ROOT / "clock-public/current.json"),
        "database":None,"database_tls":None,"server_tls":None,
        "chronyc":str(destination(release,"native/chronyc")),
        "chronyc_digest":"sha256:"+fingerprint(read_regular(bundle / "native/chronyc")),
        "chrony_socket":str(SOCKET_ROOT / "chronyd.sock"),"policies":[],
    }
    if config != expected_config:
        raise ValueError("publisher configuration differs from fixed policy")
    launch = json.loads(read_regular(bundle / "config/deployment.json",4*1024**2),
                        object_pairs_hook=no_duplicate_keys)
    # freeze_tree excludes bytecode from the frozen tree, but inventory() walks the *built*
    # bundle, so any interpreter run that lacked -B before inventory can leave .pyc behind and
    # get it pinned. Pinned bytecode is a liveness hazard rather than a safety one: it is
    # rewritten in place by the next such run, after which execute() refuses to start and the
    # deployment cannot recover without a rebuild. Bytecode is a derived cache, so unpinned.
    artifacts = [[str(destination(release,item["path"])),"sha256:"+item["sha256"]]
                 for item in manifest["files"]
                 if item["path"] != "config/deployment.json" and pinned_artifact(item["path"])]
    expected_launch = {
        "profile":"test","release":release,"python":python,"artifacts":artifacts,
        "entries":[
            {"name":"nts-observer","role":"clock","uid":uid,"gid":gid,"mode":"observer",
             "interval":None,"argv":[str(destination(release,"native/chronyd")),"-x","-U","-d","-f",
                                      str(destination(release,"config/chrony.conf"))]},
            {"name":"clock-sample","role":"clock","uid":uid,"gid":gid,"mode":"periodic",
             "interval":5,"argv":[python,"-I","-B","-m","docsuri_platform_integrity.host","clock",
                                  "--config",str(destination(release,"config/clock.json"))]},
        ],
    }
    if launch != expected_launch:
        raise ValueError("launch plan differs from the two fixed clock jobs")


def require_protected_operator():
    if (platform.system() != "Darwin" or platform.machine() != "arm64"
        or os.getuid() != 0 or os.geteuid() != 0):
        raise PermissionError("operator must authenticate locally as root")
    script = Path(__file__).absolute()
    for path in (script, *script.parents):
        info = path.lstat()
        if info.st_uid != 0 or info.st_mode & 0o022 or stat.S_ISLNK(info.st_mode):
            raise PermissionError("run a reviewed root-owned protected script copy")


def verify_installed_file(path, expected):
    for parent in path.parents:
        info = parent.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
            raise PermissionError("installed artifact ancestor changed")
    if path.lstat().st_uid != 0 or fingerprint(read_regular(path)) != expected:
        raise PermissionError("installed artifact changed")


def ensure_directory(path, *, uid=0, gid=None, mode=0o755):
    if path.exists() or path.is_symlink():
        info = path.lstat()
        if (not stat.S_ISDIR(info.st_mode) or info.st_uid != uid
            or (gid is not None and info.st_gid != gid)
            or stat.S_IMODE(info.st_mode) != mode):
            raise PermissionError("existing directory differs from the clock plan: " + str(path))
    else:
        path.mkdir(mode=mode)
        os.chown(path, uid, 0 if gid is None else gid)
        path.chmod(mode)


def install_file(path, data, *, executable=False):
    mode = 0o555 if executable else 0o444
    if path.exists() or path.is_symlink():
        info = path.lstat()
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_nlink != 1
            or stat.S_IMODE(info.st_mode) != mode or read_regular(path) != data):
            raise PermissionError("existing immutable artifact differs: " + str(path))
        return
    descriptor, temporary = tempfile.mkstemp(prefix=".clock-install-", dir=path.parent)
    temporary = Path(temporary)
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
            os.fchmod(output.fileno(), mode)
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        temporary.unlink(missing_ok=True)


def install(work, expected, *, apply=False, replace=False):
    manifest = verify_bundle(work, expected)
    result = {"state": "PLAN_ONLY", "profile": "test", "release": manifest["release"],
              "manifestSha256": expected, "installerSha256": manifest["installerSha256"],
              "files": len(manifest["files"]),
              "bytes": sum(item["size"] for item in manifest["files"]),
              "runtimePatch": manifest["runtimePatch"], "ready": False}
    if not apply:
        return result
    require_protected_operator()
    principal = pwd.getpwnam("_docsuri_r1t_clock")
    if (principal.pw_uid, principal.pw_gid) != (manifest["uid"], manifest["gid"]):
        raise PermissionError("prepared clock identity changed")
    ca = SYSTEM_CA.resolve(strict=True)
    ca_data = read_regular(ca)
    if ca.stat().st_uid != 0 or fingerprint(ca_data) != manifest["systemCaSha256"]:
        raise PermissionError("system CA trust snapshot changed")
    required = 10 * 1024**3 + 2 * sum(item["size"] for item in manifest["files"])
    if shutil.disk_usage(ROOT).free < required:
        raise PermissionError("installation disk reserve")
    ensure_directory(ROOT.parent)
    ensure_directory(ROOT, mode=0o711)
    ensure_directory(ROOT / "clock", uid=manifest["uid"], gid=manifest["gid"], mode=0o700)
    deployed = ROOT / "deployment.json"
    planned = read_regular(work / "bundle/config/deployment.json", 4 * 1024**2)
    # Overwriting a differing deployment is refused unless the operator asks for it by name. The
    # launchd publisher is given the same flag so it retires the old jobs through its own bootout
    # path; deleting deployment.json by hand instead would make it see nothing installed, skip
    # that bootout, and then fail to bootstrap the labels that are still loaded.
    if (deployed.exists() and read_regular(deployed, 4 * 1024**2) != planned
            and not replace):
        raise PermissionError("another test deployment is installed; pass --replace to replace it")
    # Persistent short private state survives reboot. /var is the fixed operating-system alias.
    for path in (Path("/private/var/db/docsuri"), Path("/private/var/db/docsuri/rem1-test")):
        ensure_directory(path)
    ensure_directory(Path("/private/var/db/docsuri/rem1-test/clock"),
                     uid=manifest["uid"], gid=manifest["gid"], mode=0o700)
    install_file(Path("/private") / clock_ca_path(manifest["systemCaSha256"]).relative_to("/"),
                 ca_data)
    ensure_directory(ROOT / "clock-public", uid=manifest["uid"], gid=manifest["gid"])
    for item in manifest["files"]:
        target = destination(manifest["release"], item["path"])
        for parent in reversed(target.parents):
            if parent != ROOT and ROOT in parent.parents:
                ensure_directory(parent)
        # Re-read and verify while copying; the unprivileged staging directory may change.
        data = read_regular(work / "bundle" / item["path"])
        if fingerprint(data) != item["sha256"]:
            raise ValueError("staging changed during installation")
        install_file(target, data, executable=item["executable"])
    python = destination(manifest["release"], "runtime/bin/python3.13")
    config = destination(manifest["release"], "config/deployment.json")
    output = run([python,"-I","-B","-m","docsuri_platform_integrity.deployment.launchd",
                  "install","--profile","test",config]
                 + (["--replace"] if replace else []), timeout=120)
    result.update(state="INSTALLED_NOT_ACCEPTED", launch=json.loads(output))
    return result


def rehearse(work, *, timeout=120):
    """A bounded real-network compatibility test under the developer UID; not role acceptance."""
    if os.geteuid() == 0:
        raise PermissionError("unprivileged rehearsal required")
    # chronyc appends its PID and a random directory to the server directory. Even the macOS
    # temporary root is too long; a fresh private workspace child fits both Unix socket paths.
    parent = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory(prefix=".n", dir=parent) as directory:
        return _rehearse(work, Path(directory), timeout)


def verify_live_images(text, bundle):
    paths = []
    system = ("/usr/lib/", "/System/Library/",
              "/System/Volumes/Preboot/Cryptexes/OS/System/Library/")
    for line in text.splitlines():
        match = re.search(r"\b[rw-]{2}x/[rwx-]{3}\s+.*?(/[^\n]+)$", line)
        if match:
            path = match[1].strip()
            paths.append(path if path.startswith(system) else str(Path(path).resolve(strict=True)))
    if not paths or not any(path.startswith(str(bundle) + "/") for path in paths):
        raise ValueError("executable image observation unavailable")
    for path in paths:
        if not path.startswith((str(bundle) + "/", *system)):
            raise ValueError("unfrozen executable image: " + path)
    return len(paths)


def _rehearse(work, state, timeout):
    from docsuri_platform_integrity.adapters.nts import make_frame, native_time, selected_source

    config = state / "chrony.conf"
    config.write_bytes(observer_config(state, user=pwd.getpwuid(os.getuid()).pw_name))
    native = work / "bundle/native"
    socket = state / "chronyd.sock"
    log_path = work / ("rehearsal" + state.name + ".log")
    status = {"state": "UNPROVEN", "scope": "unprivileged-network-rehearsal", "accepted": False,
              "log": str(log_path)}
    with log_path.open("xb") as log:
        process = subprocess.Popen([str(native / "chronyd"),"-x","-U","-d","-f",str(config)],
                                   stdin=subprocess.DEVNULL,stdout=log,stderr=log,env=ENV,
                                   start_new_session=True)
        try:
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline and process.poll() is None:
                if os.fstat(log.fileno()).st_size > 262_144:
                    raise ValueError("observer log limit")
                if socket.exists():
                    try:
                        def query(command, *args):
                            return run([native / "chronyc","-n","-h",socket,command,*args],
                                       timeout=1)

                        before = native_time()
                        reports = {"tracking_before": query("tracking"),
                                   "sources": query("sources")}
                        address = selected_source(reports["sources"])
                        reports.update(authdata=query("authdata"),ntpdata=query("ntpdata",address),
                                       sourcename=query("sourcename",address),tracking=query("tracking"))
                        frame = make_frame(reports,before,native_time(),
                                           config_digest="sha256:"+fingerprint(config.read_bytes()))
                        loaded = run(["/usr/bin/vmmap","-w",str(process.pid)])
                        (work / "rehearsal-images.txt").write_text(loaded)
                        status["executableImages"] = verify_live_images(loaded, work / "bundle")
                        status.update(state="NTS_OBSERVED_NOT_ACCEPTED",frame=frame.model_dump(mode="json"))
                        status["loadClosureVerified"] = True
                        status.pop("lastError", None)
                        break
                    except Exception as error:
                        status["lastError"] = type(error).__name__ + ": " + str(error)[:500]
                time.sleep(1)
        finally:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait(timeout=5)
    (work / "rehearsal.json").write_bytes(json_bytes(status))
    return status


CLOCK_READ_PROBE = """import json,os,socket,sys
from pathlib import Path
from docsuri_platform_integrity.adapters.nts import ProtectedClock
from docsuri_platform_integrity.deployment.launchd import kernel_groups
frame,writer,config,sock,reader=sys.argv[1:]
assert os.getuid()==os.geteuid()==int(reader) and not(set(kernel_groups())-{int(reader)})
lower,upper=ProtectedClock(Path(frame),writer_uid=int(writer),config_digest=config)()
try:
 fd=os.open(frame,os.O_WRONLY|os.O_NOFOLLOW)
except PermissionError: pass
else:
 os.close(fd); raise RuntimeError('reader_can_write_clock')
client=socket.socket(socket.AF_UNIX,socket.SOCK_DGRAM)
try: client.connect(sock)
except PermissionError: pass
else: raise RuntimeError('reader_can_control_chrony')
finally: client.close()
print(json.dumps({'state':'CLOCK_READ_VERIFIED','lower':str(lower),'upper':str(upper),
                  'clockWriteDenied':True,'commandSocketDenied':True}))
"""


def probe(work, expected):
    require_protected_operator()
    manifest = verify_bundle(work, expected)
    for item in manifest["files"]:
        installed = destination(manifest["release"], item["path"])
        verify_installed_file(installed, item["sha256"])
    installed_ca = Path("/private") / clock_ca_path(manifest["systemCaSha256"]).relative_to("/")
    verify_installed_file(installed_ca, manifest["systemCaSha256"])
    config = json.loads(read_regular(destination(manifest["release"],"config/clock.json")))
    python = destination(manifest["release"],"runtime/bin/python3.13")
    common = {"env": ENV,"stdin": subprocess.DEVNULL,"capture_output": True,"text": True,
              "timeout": 15,"check": True,"extra_groups": [],"umask": 0o077}
    deadline = time.monotonic() + 90
    while True:
        try:
            sample = subprocess.run(
                [str(python),"-I","-B","-m","docsuri_platform_integrity.host","clock",
                 "--config",str(destination(manifest["release"],"config/clock.json"))],
                user=manifest["uid"],group=manifest["gid"],cwd=ROOT / "clock",**common,
            )
            break
        except subprocess.CalledProcessError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(5)
    reader = pwd.getpwnam("_docsuri_r1t_reader")
    observed = subprocess.run([str(python),"-I","-B","-c",CLOCK_READ_PROBE,config["clock_frame"],
                               str(manifest["uid"]),config["clock_config_digest"],config["chrony_socket"],
                               str(reader.pw_uid)],user=reader.pw_uid,group=reader.pw_gid,
                              cwd=ROOT / "reader",**common)
    return {"state": "NATIVE_CLOCK_PROBED", "profile": "test", "capabilityReceiptIssued": False,
            "collector": json.loads(sample.stdout), "reader": json.loads(observed.stdout)}


def uninstall(work, expected):
    require_protected_operator()
    manifest = verify_bundle(work, expected)
    desired = read_regular(work / "bundle/config/deployment.json", 4 * 1024**2)
    if read_regular(ROOT / "deployment.json", 4 * 1024**2) != desired:
        raise PermissionError("another test deployment is installed")
    for item in manifest["files"]:
        path = destination(manifest["release"], item["path"])
        verify_installed_file(path, item["sha256"])
    python = destination(manifest["release"], "runtime/bin/python3.13")
    result = json.loads(run([python,"-I","-B","-m","docsuri_platform_integrity.deployment.launchd",
                             "uninstall","--profile","test"], timeout=120))
    # Invalidate the old sample immediately; preserve binaries and private state for inspection.
    (ROOT / "clock-public/current.json").unlink(missing_ok=True)
    return {"state": "CLOCK_STOPPED", "launch": result}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("fetch", "build", "refresh", "seal", "backport",
                                           "rehearse", "install", "probe", "uninstall"))
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--release", default="r1t-clock-20260927")
    parser.add_argument("--manifest-sha256")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--replace", action="store_true",
                        help="deliberately replace a differing installed test deployment")
    args = parser.parse_args()
    try:
        unprivileged = {"fetch", "build", "refresh", "seal", "backport", "rehearse"}
        if args.command in unprivileged and os.geteuid() == 0:
            raise PermissionError("build/rehearsal must not execute as root")
        action = {"fetch": lambda: fetch_sources(args.work),
                  "build": lambda: build(args.work.resolve(), args.release),
                  "refresh": lambda: refresh_package(args.work.resolve(), args.release),
                  "seal": lambda: seal_bundle(args.work.resolve(), args.release),
                  "backport": lambda: verify_tarfile_backport(args.work.resolve(),
                                                               args.manifest_sha256),
                  "rehearse": lambda: rehearse(args.work.resolve()),
                  "install": lambda: install(args.work.resolve(),args.manifest_sha256,
                                             apply=args.apply, replace=args.replace),
                  "probe": lambda: probe(args.work.resolve(),args.manifest_sha256),
                  "uninstall": lambda: uninstall(args.work.resolve(),args.manifest_sha256),
                  }[args.command]
        result = action()
        print(json.dumps(result))
        return 2 if result["state"] in {"UNPROVEN","BLOCKED"} else 0
    except Exception as error:
        detail = ((error.stderr or error.stdout)[-2000:]
                  if isinstance(error, subprocess.CalledProcessError) else str(error))
        print(json.dumps({"state": "BLOCKED", "reason": type(error).__name__, "detail": detail}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
