"""Shared stand-ins for the installer's tests (U8 plan Step 38): fake macOS tools, a fake
v2 instance and PlatformControl provisioner, published runtimes and pinned models, all
under a temporary prefix. Nothing here runs a macOS tool, sudo or a network call.

`FakeTools` keeps the state the real tools would change (accounts, owners, jobs, the
keychain, Time Machine's exclusions) in memory, applies modes to the real files under the
prefix, and records every call, so a test can tell whether a run changed anything.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import hashlib
import io
import json
import os
import shutil
import tarfile
import zipfile
from pathlib import Path

from docsuri_ops.arrangement import runtimes
from docsuri_ops.arrangement.checklist import Checklist, InstallationLog
from docsuri_ops.arrangement.keychain import generate
from docsuri_ops.arrangement.paths import Accounts, ArrangementPaths
from docsuri_ops.arrangement.phases import InstallContext
from docsuri_ops.arrangement.tunnel import ROOT_CERTIFICATE_FOLDER

NOW = dt.datetime(2026, 10, 23, 1, 0, tzinfo=dt.UTC)
OPERATOR, OPERATOR_UID = "revenantonthemission", 501
TUNNEL = "docsuri-v2-fixture01"
RUN_ID = "docsuri-v2-" + "a" * 16
RULES = "pass in quick on lo0 proto tcp to 127.0.0.1 port 18200 user _docsuri_v2\n"
VOLUME_ID = "0A1B2C3D-0000-4000-8000-000000000001"
MUTATING = ("create_account", "chown", "fchown", "chmod", "clone", "bootstrap", "bootout",
            "restart", "exclude", "keychain_add", "run")


def identity(info: os.stat_result) -> tuple:
    """A file's identity for the fake tools' recorded owners: its device and inode, with
    its birth time where the system keeps one, so a later file that reuses a freed inode
    is never taken for the one that was given."""
    born = getattr(info, "st_birthtime_ns", None) or getattr(info, "st_birthtime", None)
    return info.st_dev, info.st_ino, born


def reads_recorded(monkeypatch) -> list[int]:
    """The inode of every file read while the test runs, by either route: `os.read` on a
    descriptor (the no-link walk's route) and `io.open` / `open` by name (the route of
    `Path.read_bytes`, `Path.read_text` and `open()`, which the walk replaced), so a
    return to a by-path read is caught too. A name that does not resolve is not
    recorded (its open fails as it would have)."""
    import builtins

    original_read, original_open, inodes = os.read, io.open, []

    def read(descriptor, size):
        inodes.append(os.fstat(descriptor).st_ino)
        return original_read(descriptor, size)

    def opened(file, *args, **kwargs):
        if isinstance(file, int):
            inodes.append(os.fstat(file).st_ino)
        else:
            try:
                inodes.append(os.stat(file).st_ino)
            except (OSError, TypeError, ValueError):
                pass
        return original_open(file, *args, **kwargs)

    monkeypatch.setattr(os, "read", read)
    monkeypatch.setattr(io, "open", opened)
    monkeypatch.setattr(builtins, "open", opened)
    return inodes


def tar_of(members: dict[str, bytes], *, mode: str = "w:gz") -> bytes:
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode=mode) as archive:
        for name, content in members.items():
            info = tarfile.TarInfo(name)
            info.size, info.mode = len(content), 0o755
            archive.addfile(info, io.BytesIO(content))
    return stream.getvalue()


def zip_of(members: dict[str, bytes]) -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        for name, content in members.items():
            archive.writestr(name, content)
    return stream.getvalue()


@dataclasses.dataclass
class Published:
    """Fake runtime archives and their publishers' checksum answers, by URL."""

    files: dict = dataclasses.field(default_factory=dict)
    pins: dict = dataclasses.field(default_factory=dict)


def published_runtimes(*, wrong: str | None = None) -> Published:
    """A runtime archive per pin, each with its publisher's checksum (`wrong` names a pin
    whose answer does not match its archive)."""
    found = Published()
    postgres = tar_of({"postgresql-16.14/configure": b"#!/bin/sh\n"}, mode="w:bz2")
    url = "https://fake.invalid/postgresql-16.14.tar.bz2"
    found.files[url] = postgres
    digest = hashlib.sha256(postgres).hexdigest()
    found.files[url + ".sha256"] = (
        f"{'0' * 64 if wrong == 'postgresql' else digest}  postgresql-16.14.tar.bz2\n").encode()
    found.pins["POSTGRESQL"] = dataclasses.replace(
        runtimes.POSTGRESQL, url=url, checksum_url=url + ".sha256")
    vector = zip_of({"vector-0.8.7/Makefile": b"all:\n"})
    vector_url = "https://fake.invalid/vector-0.8.7.zip"
    found.files[vector_url] = vector
    found.pins["PGVECTOR_RUNTIME"] = dataclasses.replace(
        runtimes.PGVECTOR_RUNTIME, url=vector_url, sha256=hashlib.sha256(vector).hexdigest())
    for key, pin in (("OLLAMA", runtimes.OLLAMA), ("CLOUDFLARED", runtimes.CLOUDFLARED),
                     ("UV", runtimes.UV)):
        archive = tar_of({f"bundle/{Path(program).name}": b"\xcf\xfa\xed\xfe binary"
                          for program in pin.programs})
        archive_url = f"https://fake.invalid/{pin.archive}"
        digest = "f" * 64 if wrong == pin.name else hashlib.sha256(archive).hexdigest()
        found.files[archive_url] = archive
        answer_url = f"https://fake.invalid/api/{pin.name}"
        found.files[answer_url] = json.dumps({"tag_name": f"v{pin.version}", "assets": [
            {"name": pin.archive, "digest": f"sha256:{digest}"}]}).encode()
        found.pins[key] = dataclasses.replace(pin, url=archive_url, checksum_url=answer_url)
    return found


def install_pins(monkeypatch, published: Published) -> None:
    for name, pin in published.pins.items():
        monkeypatch.setattr(runtimes, name, pin)
    monkeypatch.setattr(runtimes, "RUNTIMES", tuple(published.pins[name] for name in (
        "POSTGRESQL", "PGVECTOR_RUNTIME", "OLLAMA", "CLOUDFLARED", "UV")))


def pinned_models(home: Path, monkeypatch) -> dict[str, str]:
    """Your home folder's model copy, with pins that its manifests hash to."""
    from docsuri_ops.arrangement import models

    pins = {}
    root = home / ".ollama" / "models"
    for model in ("bge-m3:latest", "qwen3:8b"):
        name, tag = model.split(":")
        blob = f"{model}-weights".encode()
        blob_digest = hashlib.sha256(blob).hexdigest()
        (root / "blobs").mkdir(parents=True, exist_ok=True)
        (root / "blobs" / f"sha256-{blob_digest}").write_bytes(blob)
        manifest = json.dumps({"config": {"digest": f"sha256:{blob_digest}"},
                               "layers": []}).encode()
        path = root / models.REGISTRY / name / tag
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(manifest)
        pins[model] = hashlib.sha256(manifest).hexdigest()
    monkeypatch.setattr(models, "MODEL_PINS", pins)
    return pins


class FakeTools:
    """macOS's tools as the installer drives them, in memory."""

    def __init__(self, paths: ArrangementPaths, published: Published):
        self.paths, self.published = paths, published
        self.accounts: dict[str, dict] = {"_docsuri_r1t_backup": {
            "uid": 607, "shell": "/usr/bin/false", "gid": 607}}
        self.owners: dict[str, int] = {}
        # Owners given through a descriptor, by the file's identity (`identity`).
        self.given: dict[tuple, int] = {}
        self.jobs: set[str] = set()
        self.keychain: dict[str, bytes] = {}
        self.exclusions: set[str] = set()
        self.calls: list[tuple] = []
        self.fail_lint = False
        # A program's own `otool -L` answer, by its path; with no entry, `libraries`
        # answers as built.
        self.links: dict[str, list[str]] = {}

    def _record(self, *call) -> None:
        self.calls.append(call)

    def mutations(self) -> list[tuple]:
        return [call for call in self.calls if call[0] in MUTATING]

    # accounts
    def account(self, name):
        return self.accounts.get(name)

    def create_account(self, name, uid):
        self._record("create_account", name)
        self.accounts[name] = {"uid": uid, "shell": "/usr/bin/false", "gid": uid}

    # files
    def owner(self, path):
        if not Path(path).exists() and not Path(path).is_symlink():
            return None
        info = Path(path).lstat()
        given = self.given.get(identity(info))
        if given is not None:
            return given
        return self.owners.get(str(path), info.st_uid)

    def moved(self, source, target):
        if str(source) in self.owners:
            self.owners[str(target)] = self.owners.pop(str(source))

    def chown(self, path, uid, gid):
        self._record("chown", str(path), uid, gid)
        self.owners[str(path)] = uid
        if Path(path).exists() or Path(path).is_symlink():
            self.given.pop(identity(Path(path).lstat()), None)

    def fchown(self, descriptor, uid, gid):
        """An owner given through a file's or folder's own descriptor (your answer of
        2026-11-10, "Fix both and sweep the rest"), kept by the file's identity, so it
        follows the file through a rename as a real owner does."""
        info = os.fstat(descriptor)
        self._record("fchown", info.st_ino, uid, gid)
        self.given[identity(info)] = uid

    def descriptor_owner(self, descriptor):
        info = os.fstat(descriptor)
        return self.given.get(identity(info), info.st_uid)

    def chmod(self, path, mode):
        self._record("chmod", str(path), mode)
        Path(path).chmod(mode)

    def clone(self, source, target):
        self._record("clone", str(target))
        shutil.copyfile(source, target)

    # jobs
    def job_state(self, label):
        return "running" if label in self.jobs else None

    def bootstrap(self, definition):
        self._record("bootstrap", Path(definition).stem)
        self.jobs.add(Path(definition).stem)

    def bootout(self, domain_label):
        self._record("bootout", domain_label)
        self.jobs.discard(domain_label.rsplit("/", 1)[-1])

    def restart(self, domain_label):
        self._record("restart", domain_label)

    # rules
    def plist_lint(self, path):
        return not self.fail_lint and Path(path).is_file()

    def sudoers_check(self, path):
        return Path(path).is_file() and b"Cmnd_Alias" in Path(path).read_bytes()

    def anchor_check(self, path):
        return Path(path).is_file()

    def anchor_rules(self):
        return RULES if "org.docsuri.v2.pf" in self.jobs else None

    # Time Machine and the keychain
    def exclude(self, path):
        self._record("exclude", path)
        self.exclusions.add(path)

    def excluded(self, path):
        return path in self.exclusions

    def keychain_add(self, service, account, secret, **options):
        # The secret stays only in `self.keychain`, never in a call record (Step 75(a)).
        self._record("keychain_add", service, account, dict(options))
        self.keychain[service] = secret

    def keychain_has(self, service, **_):
        return service in self.keychain

    def keychain_read(self, service, **_):
        """A copy of the stored item, as a buffer the caller clears (a missing item raises
        as `security` does)."""
        if service not in self.keychain:
            from docsuri_ops.arrangement.macos import ToolFailed

            raise ToolFailed("tool-failed:security")
        return bytearray(self.keychain[service])

    def volume(self, name):
        return {"identifier": VOLUME_ID, "locked": False, "encrypted": True}

    def libraries(self, program):
        return list(self.links.get(str(program), [])) if Path(program).exists() else None

    def memory_available(self):
        return 16 * 1024**3

    def fetch(self, url):
        self._record("fetch", url)
        return self.published.files[url]

    def run(self, argv, *, input=None, cwd=None, **options):
        """The build and setup tools: each leaves what the real one would leave."""
        self._record("run", Path(argv[0]).name, *argv[1:3])
        name = Path(argv[0]).name
        if name == "make" and "install" in argv and not any("PG_CONFIG" in a for a in argv):
            for program in runtimes.POSTGRESQL.programs:
                path = self.paths.postgres_runtime / program
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"\xcf\xfa\xed\xfe postgres")
        elif name == "make" and "install" in argv and any(
            a.startswith("PG_CONFIG=") for a in argv
        ):
            self._install_pgvector()
        elif name == "initdb":
            (self.paths.postgres_data / "PG_VERSION").write_text("16\n")
        elif name == "cloudflared" and "create" in argv:
            credentials = Path(argv[argv.index("--credentials-file") + 1])
            credentials.write_text('{"TunnelID": "fixture"}')
        return b""

    def _install_pgvector(self) -> None:
        """What PGXS's `make install` leaves under the PostgreSQL prefix, at literal paths
        never read from `runtimes`, so a pin that departs from this layout fails phase 2.
        The library's bytes are its own: the isolation check keeps one `otool -L` answer
        per digest, and PostgreSQL's fake programs share one digest."""
        root = self.paths.postgres_runtime
        for relative, content in (
            ("lib/vector.dylib", b"\xcf\xfa\xed\xfe vector"),
            ("share/extension/vector.control",
             b"default_version = '0.8.7'\nmodule_pathname = '$libdir/vector'\n"
             b"relocatable = true\n"),
            ("share/extension/vector--0.8.7.sql", b"-- vector 0.8.7 install script fixture\n"),
        ):
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)


class FakeStore:
    def __init__(self):
        self.targets, self.authorities = [], {}
        # Each store login's actor (`u8_bind_login`), never rebound to another, and the
        # logins the installation script made members of the runtime role.
        self.logins: dict[str, tuple[str, str]] = {}
        self.runtime_members: set[str] = set()

    def call_committed(self, function, params):
        if function == "u8_login_bindings":
            (logins,) = params
            return {login: {"bound": login in self.logins,
                            "actor": self.logins.get(login, (None, None))[0],
                            "kind": self.logins.get(login, (None, None))[1],
                            "runtimeMember": login in self.runtime_members}
                    for login in logins}
        if function != "u8_bind_login":
            raise AssertionError(f"the installer called {function}")
        login, actor, kind = params
        if self.logins.setdefault(login, (actor, kind)) != (actor, kind):
            from docsuri_ops.platform_control.errors import ControlError

            raise ControlError("CONFLICT", "login already bound to another actor")
        return {"login": login, "actor": actor, "kind": kind}

    def provision_target(self, target):
        self.targets.append(target)

    def provision_authority(self, *, authority_id, actor, scope, operations, authority_class,
                            binding):
        self.authorities[authority_id] = {"actor": actor, "scope": scope,
                                          "operations": operations, "class": authority_class}

    def read_authority(self, authority_id):
        """U7's `read_authority` shape, for the installer's grant check."""
        from docsuri_ops.platform_control.errors import ControlError

        held = self.authorities.get(str(authority_id))
        if held is None:
            raise ControlError("NOT_FOUND", "unknown authority")
        return {"authorityId": authority_id, "actorReference": held["actor"],
                "targetScope": list(held["scope"]),
                "permittedOperation": list(held["operations"]),
                "authorityClass": held["class"], "revokedAt": held.get("revokedAt")}


class FakeDatabase:
    """v2's instance as the installer reaches it, in memory: the script is kept so a
    test can check what it holds."""

    def __init__(self, paths: ArrangementPaths):
        self.paths, self.scripts, self.store_ = paths, [], FakeStore()
        self.installed = False

    def initialised(self):
        return (self.paths.postgres_data / "PG_VERSION").exists()

    def initdb(self):
        (self.paths.postgres_data / "PG_VERSION").write_text("16\n")

    def ready(self):
        return self.initialised()

    def run_script(self, script):
        self.scripts.append(script)
        self.installed = True
        # The runtime role's members, as the script's grants and revokes leave them.
        for line in script.splitlines():
            words = line.rstrip(";").split()
            if words[:3] == ["GRANT", "platform_control_runtime", "TO"]:
                self.store_.runtime_members.add(words[3])
            if words[:3] == ["REVOKE", "platform_control_runtime", "FROM"]:
                self.store_.runtime_members.discard(words[3])

    def identities(self):
        return {"production": self.installed, "platform": self.installed}

    def login_check(self, role, password):
        """Raise-only: the fake instance answers no statement, so a path that reaches a
        login check fails loudly."""
        raise AssertionError("the fake database takes no login")

    def store(self, password):
        self.store_.password = password
        return self.store_


@dataclasses.dataclass
class Stage:
    ctx: InstallContext
    tools: FakeTools
    database: FakeDatabase
    secrets: list[bytes]
    answers: list[str]
    asked: list[str]


def install_stage(tmp_path: Path, monkeypatch, *, wrong: str | None = None,
                  decline: str | None = None) -> Stage:
    paths = ArrangementPaths.under(tmp_path / "Library" / "DocSuri")
    published = published_runtimes(wrong=wrong)
    install_pins(monkeypatch, published)
    home = tmp_path / "home"
    pins = pinned_models(home, monkeypatch)
    (home / "Library" / "LaunchAgents").mkdir(parents=True)
    (home / "Library" / "LaunchAgents" / "homebrew.mxcl.ollama.plist").write_text("<plist/>")
    tools = FakeTools(paths, published)
    secrets: list[bytes] = []
    answers = [f"https://hc-ping.com/{index:08d}-fixture" for index in range(3)]
    asked: list[str] = []

    def secret() -> bytes:
        value = generate()
        secrets.append(value)
        return value

    def ask(item: str, instruction: str) -> bool:
        asked.append(item)
        if item == "new-certificate-issued":
            folder = paths.control / ROOT_CERTIFICATE_FOLDER
            folder.mkdir(parents=True, exist_ok=True)
            (folder / "cert.pem").write_text("certificate fixture")
        return item != decline

    remaining = list(answers)
    log = InstallationLog(paths.installation_log, clock=lambda: NOW, base=paths.prefix)
    database = FakeDatabase(paths)
    ctx = InstallContext(
        paths=paths, accounts=Accounts.standard(), tools=tools, clock=lambda: NOW, log=log,
        checklist=Checklist(log, ask, lambda item, text: remaining.pop(0)),
        operator=OPERATOR, operator_uid=OPERATOR_UID, operator_home=home, tunnel_name=TUNNEL,
        maintainer_account="00000000-0000-4000-8000-0000000000aa", run_id=RUN_ID,
        generate=secret, database=database,
        model_tags=lambda: {"models": [{"name": model, "digest": digest}
                                       for model, digest in pins.items()]},
        verification=lambda ctx: [{"check": "isolation-check", "passed": True}],
        v1_checkout=tmp_path / "v1", v1_stores={"v1-stores/database": str(tmp_path / "v1db")},
        load_profile=manifest_loads,
    )
    return Stage(ctx, tools, database, secrets, answers, asked)


def manifest_loads(manifest: Path):
    """Phase 7's profile load under a temporary prefix: the production loader's manifest
    checks, without its custody checks (the fake tools never chown, and CI's temporary
    folders lie under /tmp, which the production loader refuses)."""
    from backend.u8_profile import ProductionProfile

    return ProductionProfile._from_manifest(manifest.parent, json.loads(manifest.read_bytes()))


def tree(root: Path) -> dict[str, tuple]:
    """Every path under `root` with its mode and, for files, its bytes."""
    found = {}
    if not root.exists():
        return found
    for path in sorted(root.rglob("*")):
        info = path.lstat()
        found[str(path)] = (info.st_mode, path.read_bytes() if path.is_file() else None)
    return found
