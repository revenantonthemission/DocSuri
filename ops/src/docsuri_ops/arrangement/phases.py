"""The installer's seven phases (U8 plan Step 37; infrastructure-specification § 4,
Workflow 20, BR6.11, D8, D9, D14).

Each phase answers two questions:

- `changes(ctx)`: what differs now from the arrangement it installs, each difference a
  `Change` with a target, an action and a difference that names no secret, and the one
  function that applies it. An arrangement already in place yields no change, so a
  second run changes nothing; plan mode lists the changes and applies none.
- `verify(ctx)`: whether its own result holds, checked before the next phase starts; a
  failure raises `PhaseFailed` with a fixed key and the installer stops there.

The phases: 1. accounts; 2. runtimes (PostgreSQL 16.14 and pgvector from source, Ollama,
cloudflared, uv and the release, each against its publisher's checksum and with `otool
-L`); 3. folders and the database (owners and modes, the Time Machine exclusions,
`initdb`, the roles, `template1`'s extension, `docsuri_v2` with its base and
`docsuri_v2_platform` with U7's schema, each password generated into its holder);
4. rule files; 5. models and tunnel; 6. filter, volume and jobs; 7. restart and check.
"""

from __future__ import annotations

import contextlib
import datetime as dt
import json
import os
import shutil
import stat
import tarfile
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from . import keychain, render, runtimes, safe_fs
from .checklist import Checklist, InstallationLog
from .paths import Accounts, ArrangementPaths

PHASE_NAMES = ("accounts", "runtimes", "folders-and-database", "rule-files",
               "models-and-tunnel", "filter-volume-and-jobs", "restart-and-check")
RUNTIME_MARKER = ".docsuri-runtime.json"
# (path under the prefix, owner, mode): every folder of tech-stack-decisions' tables.
FOLDERS = (
    ("", "root", 0o755), ("releases", "root", 0o755), ("runtimes", "root", 0o755),
    ("tunnel", "root", 0o755), ("tunnel/config", "root", 0o755), ("control", "root", 0o755),
    ("control/stops", "root", 0o755), ("control/logs", "root", 0o755),
    ("control/effects", "root", 0o755), ("control/effects/operator", "operator", 0o700),
    ("control/effects/scheduler", "scheduler", 0o700),
    ("evidence", "root", 0o755), ("evidence/isolation", "root", 0o755),
    ("profile", "service", 0o700), ("profile/logs", "service", 0o700),
    ("profile/evidence", "service", 0o700), ("profile/ledger", "service", 0o700),
    ("profile/export-keys", "service", 0o700), ("profile/control-keys", "service", 0o700),
    ("profile/verifier-key", "service", 0o700), ("profile/cursor-key", "service", 0o700),
    # PostgreSQL's rule files, root's, outside the database account's `postgres/` (your
    # answer of 2026-11-11, "Map the login, root rules").
    ("postgres-rules", "root", 0o755),
    ("postgres", "database", 0o755), ("postgres/data", "database", 0o700),
    ("postgres/socket", "database", 0o700), ("postgres/logs", "database", 0o700),
    ("models", "models", 0o700), ("models-state", "models", 0o700),
    ("models-state/logs", "models", 0o700),
    ("tunnel/credentials", "tunnel", 0o700), ("tunnel/logs", "tunnel", 0o700),
    ("scheduler", "scheduler", 0o700), ("scheduler/logs", "scheduler", 0o700),
    ("backup-agent", "backup", 0o700), ("backup-agent/logs", "backup", 0o700),
    ("availability", "scheduler", 0o755),
)


class PhaseFailed(RuntimeError):
    """A phase's own check failed; the message is a fixed key."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


@dataclass
class Change:
    phase: str
    action: str
    target: str
    difference: str
    apply: Callable[[], None] = field(repr=False, compare=False)

    def describe(self) -> dict:
        return {"phase": self.phase, "action": self.action, "target": self.target,
                "difference": self.difference}


@dataclass
class InstallContext:
    """What the phases work with: the arrangement's paths and accounts (a temporary prefix
    with fake tools in tests), the adapter, the clock, the installation log and the
    checklist, and the installation's own choices."""

    paths: ArrangementPaths
    accounts: Accounts
    tools: object
    clock: Callable[[], dt.datetime]
    log: InstallationLog
    checklist: Checklist
    operator: str
    operator_uid: int
    operator_home: Path
    tunnel_name: str
    maintainer_account: str
    run_id: str
    release_tag: str | None = None
    stage_release: Callable[[str], Path] | None = None
    root_uid: int = 0
    generate: Callable[[], bytes] = keychain.generate
    database: object = None
    model_tags: Callable[[], dict] = field(default=lambda: {})
    verification: Callable[[InstallContext], list[dict]] | None = None
    source: Path = field(default_factory=lambda: Path(__file__).resolve().parents[4])
    # v1's fixed checkout (its runtime for a rollback's lifecycle apply) and v1's stores'
    # locations on this Mac, for the arrangement driver (no secret).
    v1_checkout: Path | None = None
    v1_stores: dict = field(default_factory=dict)
    # v1's database, search index and object store addresses for the operator's
    # environment file (`v1Sources`, the production migration platform).
    v1_sources: dict = field(default_factory=dict)
    # Phase 3's end (your decision of 2026-10-24): the linked release's
    # `docsuri-production-tool migrate` as the service account, with the operator login
    # from the System keychain; None leaves the chain to the release command.
    migrate: Callable[[InstallContext], dict] | None = None
    # Phase 7's check that the profile still loads (the production loader by default).
    load_profile: Callable[[Path], object] | None = None
    # Phase 7's keyring start (your decisions of 2026-10-24 and 2026-10-25): v2's three
    # roles stopped, the linked release's `docsuri-production-tool control-key-start` as
    # the service account, the roles started again. None leaves the keyring unstarted.
    control_key_start: Callable[[InstallContext], dict] | None = None

    def uid(self, owner: str) -> int:
        if owner == "root":
            return self.root_uid
        if owner == "operator":
            return self.operator_uid
        return getattr(self.accounts, owner).uid

    def gid(self, owner: str) -> int:
        return 0 if owner == "root" else (
            20 if owner == "operator" else getattr(self.accounts, owner).uid)


# --- shared helpers -------------------------------------------------------------------------


def _describe_mode(mode: int) -> str:
    return f"{mode:04o}"


def folder_change(ctx: InstallContext, phase: str, path: Path, owner: str,
                  mode: int) -> Change | None:
    """A folder with its owner and mode, never through a link."""
    try:
        info = path.lstat()
    except FileNotFoundError:
        info = None
    if info is not None and stat.S_ISLNK(info.st_mode):
        raise PhaseFailed("folder-is-a-link")
    current_owner = None if info is None else ctx.tools.owner(path)
    if info is not None and stat.S_ISDIR(info.st_mode) and stat.S_IMODE(
        info.st_mode
    ) == mode and current_owner == ctx.uid(owner):
        return None
    before = "absent" if info is None else (
        f"{_describe_mode(stat.S_IMODE(info.st_mode))} uid {current_owner}")

    def apply() -> None:
        set_folder(ctx, path, owner, mode)

    return Change(phase, "folder", str(path), f"{before} -> {_describe_mode(mode)} {owner}",
                  apply)


def set_folder(ctx: InstallContext, path: Path, owner: str, mode: int) -> None:
    """The folder made when missing and given its mode and owner through its own
    descriptor (your answer of 2026-11-10, "Fix both and sweep the rest"): its parent is
    reached by the no-link walk from the root-owned base, the folder itself is opened
    relative to the parent with `O_NOFOLLOW`, and `os.fchmod` and the tools' `fchown` act
    on that descriptor, so a link an account put in place of the folder or of a folder on
    the way is refused (`folder-is-a-link`) and nothing it points to changes."""
    base = safe_fs.walk_base(ctx.paths.prefix, path.parent)
    try:
        with safe_fs.folder_at(base, path.parent, create=True) as parent:
            with contextlib.suppress(FileExistsError):
                os.mkdir(path.name, mode, dir_fd=parent)
            descriptor = safe_fs.open_child_folder(parent, path.name)
    except safe_fs.PathRefused:
        raise PhaseFailed("folder-is-a-link") from None
    try:
        os.fchmod(descriptor, mode)
        ctx.tools.fchown(descriptor, ctx.uid(owner), ctx.gid(owner))
    finally:
        os.close(descriptor)


def _read_target(ctx: InstallContext, target: Path) -> bytes:
    """A rendered file's current bytes, read through the no-link walk (a file another
    account could swap is never read through a link or a second name)."""
    try:
        content = safe_fs.read_regular(safe_fs.walk_base(ctx.paths.prefix, target.parent),
                                       target)
    except safe_fs.PathRefused:
        raise PhaseFailed("rule-file-not-a-regular-file") from None
    if content is None:
        raise PhaseFailed("rule-file-not-a-regular-file")
    return content


def file_change(ctx: InstallContext, phase: str, item: render.Rendered) -> Change | None:
    """One rendered file: its bytes, mode and owner; written through a new file beside
    it and renamed over, never through a link."""
    target = item.target
    try:
        info = target.lstat()
    except FileNotFoundError:
        info = None
    if info is not None and not stat.S_ISREG(info.st_mode):
        raise PhaseFailed("rule-file-not-a-regular-file")
    current = None if info is None else _read_target(ctx, target)
    same = info is not None and current == item.content and stat.S_IMODE(
        info.st_mode) == item.mode and ctx.tools.owner(target) == ctx.uid(item.owner)
    if same:
        return None
    if info is None:
        before = "absent"
    elif current != item.content:
        before = "content differs"
    else:
        before = f"{_describe_mode(stat.S_IMODE(info.st_mode))} uid {ctx.tools.owner(target)}"

    def apply() -> None:
        write_file(ctx, target, item.content, item.mode, item.owner)

    return Change(phase, "file", str(target),
                  f"{before} -> {_describe_mode(item.mode)} {item.owner}", apply)


def write_file(ctx: InstallContext, target: Path, content: bytes, mode: int, owner: str) -> None:
    """The target's bytes replaced through a pending file beside it (your answer of
    2026-11-10, "Fix both and sweep the rest"): the folder is reached by the no-link walk
    from the root-owned base, the pending file is created new relative to the folder's
    descriptor, given its mode and owner on its own descriptor before it is closed, and
    renamed over the target relative to the same descriptor; nothing is set or renamed
    by path, so the folder's account cannot swap a name in between."""
    pending = target.with_name(target.name + ".docsuri-pending")
    uid, gid = ctx.uid(owner), ctx.gid(owner)
    safe_fs.write_replacing(safe_fs.walk_base(ctx.paths.prefix, target.parent), target,
                            content, mode=mode,
                            give=lambda descriptor: ctx.tools.fchown(descriptor, uid, gid))
    ctx.tools.moved(pending, target)


def _regular_file(path: Path) -> bool:
    """Whether a regular file is at the name itself, read with `lstat`: a link, a folder
    or anything else at the name does not count, nor does a missing path. `otool -L`
    follows a link, so a link to a library outside a runtime's folder would otherwise be
    judged on its target's closure."""
    try:
        return stat.S_ISREG(path.lstat().st_mode)
    except FileNotFoundError:
        return False


def _prefixed(ctx: InstallContext, relative: str) -> Path:
    return ctx.paths.prefix / relative if relative else ctx.paths.prefix


# --- phase 1: accounts ----------------------------------------------------------------------


class AccountsPhase:
    name = "accounts"
    NEW = ("service", "scheduler", "database", "models", "tunnel")

    def changes(self, ctx: InstallContext) -> list[Change]:
        found = []
        for key in self.NEW:
            account = getattr(ctx.accounts, key)
            if ctx.tools.account(account.name) is None:
                found.append(Change(self.name, "account", account.name,
                                    f"absent -> uid {account.uid}, no login",
                                    lambda account=account: ctx.tools.create_account(
                                        account.name, account.uid)))
        return found

    def verify(self, ctx: InstallContext) -> None:
        for key in (*self.NEW, "backup"):
            account = getattr(ctx.accounts, key)
            found = ctx.tools.account(account.name)
            if found is None:
                raise PhaseFailed(f"account-missing:{key}")
            if found["uid"] != account.uid:
                raise PhaseFailed(f"account-uid-differs:{key}")
            if found["shell"] != "/usr/bin/false":
                raise PhaseFailed(f"account-can-log-in:{key}")


# --- phase 2: runtimes and the release ------------------------------------------------------


def runtime_record(ctx: InstallContext, pin: runtimes.RuntimePin) -> dict | None:
    path = ctx.paths.runtimes / pin.folder / RUNTIME_MARKER
    try:
        value = json.loads(path.read_bytes())
    except (OSError, ValueError):
        return None
    marker = f"{pin.name}-{pin.version}"
    return value.get(marker) if isinstance(value, dict) else None


def _record_runtime(ctx: InstallContext, pin: runtimes.RuntimePin, archive: str,
                    publisher: str) -> None:
    path = ctx.paths.runtimes / pin.folder / RUNTIME_MARKER
    try:
        value = json.loads(path.read_bytes())
    except (OSError, ValueError):
        value = {}
    value[f"{pin.name}-{pin.version}"] = {"archiveSha256": archive, "publisherSha256": publisher}
    write_file(ctx, path, json.dumps(value, sort_keys=True).encode(), 0o644, "root")


def fetch_verified(ctx: InstallContext, pin: runtimes.RuntimePin) -> tuple[bytes, str]:
    """The archive, refused unless its digest equals its publisher's checksum."""
    from .macos import sha256_bytes

    data = ctx.tools.fetch(pin.url)
    answer = b"" if pin.checksum_url is None else ctx.tools.fetch(pin.checksum_url)
    try:
        publisher = runtimes.publisher_checksum(pin, answer)
    except ValueError:
        raise PhaseFailed(f"publisher-checksum-unreadable:{pin.name}") from None
    digest = sha256_bytes(data)
    ctx.log.write("runtimes", f"checksum:{pin.name}", "passed" if digest == publisher
                  else "failed", sha256=digest)
    if digest != publisher:
        raise PhaseFailed(f"runtime-checksum-differs:{pin.name}")
    return data, publisher


def _extract(data: bytes, into: Path) -> Path:
    """A tar archive's members into a new folder under tarfile's `data` filter, which
    refuses absolute paths, `..`, links leaving the folder and special files."""
    import io

    try:
        with tarfile.open(fileobj=io.BytesIO(data)) as archive:
            archive.extractall(into, filter="data")
    except (tarfile.TarError, OSError):
        raise PhaseFailed("archive-refused") from None
    return into


class RuntimesPhase:
    name = "runtimes"

    def _install_simple(self, ctx: InstallContext, pin: runtimes.RuntimePin) -> None:
        data, publisher = fetch_verified(ctx, pin)
        folder = ctx.paths.runtimes / pin.folder
        staging = Path(tempfile.mkdtemp(prefix=f".{pin.name}-", dir=ctx.paths.runtimes))
        try:
            _extract(data, staging)
            folder.mkdir(mode=0o755, parents=True, exist_ok=True)
            for program in pin.programs:
                found = next(iter(sorted(staging.rglob(Path(program).name))), None)
                if found is None:
                    raise PhaseFailed(f"runtime-program-missing:{pin.name}")
                destination = folder / program
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(found, destination)
                ctx.tools.chmod(destination, 0o755)
                ctx.tools.chown(destination, ctx.root_uid, 0)
        finally:
            shutil.rmtree(staging, ignore_errors=True)
        from .macos import sha256_bytes

        _record_runtime(ctx, pin, sha256_bytes(data), publisher)

    def _install_postgres(self, ctx: InstallContext) -> None:
        """PostgreSQL 16.14 from its source release, without ICU or TLS, then pgvector
        built against it (D14); both checked against their published checksums."""
        from .macos import BUILD_SECONDS, sha256_bytes

        folder = ctx.paths.postgres_runtime
        for pin in (runtimes.POSTGRESQL, runtimes.PGVECTOR_RUNTIME):
            if runtime_record(ctx, pin) is not None:
                continue
            data, publisher = fetch_verified(ctx, pin)
            staging = Path(tempfile.mkdtemp(prefix=f".{pin.name}-", dir=ctx.paths.runtimes))
            try:
                if pin is runtimes.POSTGRESQL:
                    _extract(data, staging)
                    source = staging / f"postgresql-{pin.version}"
                    ctx.tools.run(["./configure", f"--prefix={folder}",
                                   *runtimes.POSTGRESQL_CONFIGURE], cwd=source,
                                  seconds=BUILD_SECONDS)
                    ctx.tools.run(["/usr/bin/make", "-j", "4"], cwd=source, seconds=BUILD_SECONDS)
                    ctx.tools.run(["/usr/bin/make", "install"], cwd=source, seconds=BUILD_SECONDS)
                else:
                    import io
                    import zipfile

                    with zipfile.ZipFile(io.BytesIO(data)) as archive:
                        archive.extractall(staging)
                    source = staging / f"vector-{pin.version}"
                    config = f"PG_CONFIG={folder / 'bin' / 'pg_config'}"
                    ctx.tools.run(["/usr/bin/make", config], cwd=source, seconds=BUILD_SECONDS)
                    ctx.tools.run(["/usr/bin/make", config, "install"], cwd=source,
                                  seconds=BUILD_SECONDS)
            finally:
                shutil.rmtree(staging, ignore_errors=True)
            _record_runtime(ctx, pin, sha256_bytes(data), publisher)

    def _release_change(self, ctx: InstallContext) -> Change | None:
        if ctx.release_tag is None or ctx.paths.release.is_symlink():
            return None
        tag = ctx.release_tag

        def apply() -> None:
            if ctx.stage_release is None:
                raise PhaseFailed("release-staging-unwired")
            folder = ctx.stage_release(tag)
            link = ctx.paths.release.with_name("release.docsuri-pending")
            if link.is_symlink():
                link.unlink()
            os.symlink(folder, link)
            os.replace(link, ctx.paths.release)

        return Change(self.name, "release", f"releases/{tag}", "absent -> staged and linked",
                      apply)

    def changes(self, ctx: InstallContext) -> list[Change]:
        # The root-owned folders the runtimes and the release go into come first; phase 3
        # sets every other folder.
        found = [change for change in (
            folder_change(ctx, self.name, ctx.paths.prefix, "root", 0o755),
            folder_change(ctx, self.name, ctx.paths.runtimes, "root", 0o755),
            folder_change(ctx, self.name, ctx.paths.releases, "root", 0o755),
        ) if change is not None]
        if any(runtime_record(ctx, pin) is None
               for pin in (runtimes.POSTGRESQL, runtimes.PGVECTOR_RUNTIME)):
            found.append(Change(self.name, "runtime", str(ctx.paths.postgres_runtime),
                                f"absent -> PostgreSQL {runtimes.POSTGRESQL_VERSION} with "
                                f"pgvector {runtimes.PGVECTOR.version} built from source",
                                lambda: self._install_postgres(ctx)))
        for pin in (runtimes.OLLAMA, runtimes.CLOUDFLARED, runtimes.UV):
            if runtime_record(ctx, pin) is None:
                found.append(Change(self.name, "runtime",
                                    str(ctx.paths.runtimes / pin.folder),
                                    f"absent -> {pin.name} {pin.version}",
                                    lambda pin=pin: self._install_simple(ctx, pin)))
        release = self._release_change(ctx)
        if release is not None:
            found.append(release)
        return found

    def verify(self, ctx: InstallContext) -> None:
        from .macos import loads_only_from

        for pin in runtimes.RUNTIMES:
            if runtime_record(ctx, pin) is None:
                raise PhaseFailed(f"runtime-missing:{pin.name}")
            folder = ctx.paths.runtimes / pin.folder
            for program in pin.programs:
                # A pinned program or module must be a regular file before `otool -L`
                # runs on it (BR6.11 (0)); a link at the name does not count.
                if not _regular_file(folder / program):
                    raise PhaseFailed(f"runtime-program-missing:{pin.name}")
                libraries = ctx.tools.libraries(folder / program)
                if libraries is None or not loads_only_from(libraries, folder):
                    raise PhaseFailed(f"runtime-loads-outside:{pin.name}")
            for config_file in pin.config_files:
                if not _regular_file(folder / config_file):
                    raise PhaseFailed(f"runtime-file-missing:{pin.name}")
        if ctx.release_tag is not None:
            verify_release_programs(ctx, ctx.paths.release_bin)


def verify_release_programs(ctx: InstallContext, folder: Path) -> None:
    """Every fixed program present, a regular file, root-owned, mode 0755."""
    for name in render.FIXED_PROGRAMS:
        path = folder / name
        try:
            info = path.lstat()
        except FileNotFoundError:
            raise PhaseFailed(f"program-missing:{name}") from None
        if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != render.PROGRAM_MODE:
            raise PhaseFailed(f"program-mode:{name}")
        if ctx.tools.owner(path) != ctx.root_uid:
            raise PhaseFailed(f"program-owner:{name}")


def set_program_modes(ctx: InstallContext, folder: Path) -> list[str]:
    """Mode 0755 and root ownership on the release's seventeen fixed programs, by the
    installer's own code (never a shell command)."""
    done = []
    for name in render.FIXED_PROGRAMS:
        path = folder / name
        if path.is_symlink() or not path.is_file():
            raise PhaseFailed(f"program-missing:{name}")
        ctx.tools.chmod(path, render.PROGRAM_MODE)
        ctx.tools.chown(path, ctx.root_uid, 0)
        done.append(name)
    return done


# --- phase 4: rule files ---------------------------------------------------------------------


class RuleFilesPhase:
    name = "rule-files"

    def rendered(self, ctx: InstallContext) -> list[render.Rendered]:
        # PostgreSQL's files are phase 3's: the server starts there and reads them.
        postgres = (ctx.paths.postgres_data, ctx.paths.postgres_rules)
        return [item for item in render.render(ctx.paths, ctx.accounts, operator=ctx.operator,
                                               tunnel_name=ctx.tunnel_name)
                if item.target.parent not in postgres]

    def changes(self, ctx: InstallContext) -> list[Change]:
        found = []
        for item in self.rendered(ctx):
            change = file_change(ctx, self.name, item)
            if change is None:
                continue
            if item.target == ctx.paths.sudoers_rules:
                change = Change(change.phase, change.action, change.target, change.difference,
                                lambda item=item, inner=change.apply: self._sudoers(ctx, item,
                                                                                    inner))
            found.append(change)
        return found

    def _sudoers(self, ctx: InstallContext, item: render.Rendered, write: Callable) -> None:
        """`visudo -c -f` on the rules before they are put in place: a rule that does not
        parse never reaches `/etc/sudoers.d`."""
        with tempfile.NamedTemporaryFile(prefix="docsuri-v2-sudoers-", delete=True) as copy:
            copy.write(item.content)
            copy.flush()
            if not ctx.tools.sudoers_check(Path(copy.name)):
                raise PhaseFailed("sudo-rules-do-not-parse")
        write()

    def verify(self, ctx: InstallContext) -> None:
        if not ctx.tools.sudoers_check(ctx.paths.sudoers_rules):
            raise PhaseFailed("sudo-rules-do-not-parse")
        for item in self.rendered(ctx):
            if not item.target.exists() or item.target.read_bytes() != item.content:
                raise PhaseFailed(f"rule-file-differs:{item.target.name}")
            if item.target.suffix == ".plist" and not ctx.tools.plist_lint(item.target):
                raise PhaseFailed(f"launch-job-does-not-lint:{item.target.name}")
        if not ctx.tools.anchor_check(ctx.paths.pf_anchor):
            raise PhaseFailed("filter-anchor-does-not-parse")


# --- phase 5: models and tunnel ---------------------------------------------------------------

LOGIN_OLLAMA = "homebrew.mxcl.ollama"


def remove_login_definition(base: Path, definition: Path) -> bool:
    """Your login account's job definition removed, only when it is a regular file (your
    answer of 2026-11-10, "Fix both and sweep the rest"): your home folder is yours, so
    its folders are reached by the no-link walk from `base` (the root-owned folder that
    holds the home folders) and the name is removed relative to its folder's descriptor.
    A link at the name or at a folder on the way, or another thing than a file, is left as
    it is, as a linked definition was before; answers whether it removed one."""
    try:
        with safe_fs.folder_at(base, definition.parent) as folder:
            info = os.stat(definition.name, dir_fd=folder, follow_symlinks=False)
            if not stat.S_ISREG(info.st_mode):
                return False
            os.unlink(definition.name, dir_fd=folder)
    except (FileNotFoundError, safe_fs.PathRefused):
        return False
    return True


class ModelsTunnelPhase:
    """Workflow 20 steps 5 and 6: the pinned models cloned, verified and served by the
    system job before your login account's runtime goes; the tunnel moved without a gap."""

    name = "models-and-tunnel"

    def _models_in_place(self, ctx: InstallContext) -> bool:
        from .models import ModelsRefused, verify_models

        uid = ctx.accounts.models.uid
        try:
            verify_models(ctx.paths.models, base=ctx.paths.prefix,
                          owned_by=lambda descriptor: ctx.tools.descriptor_owner(descriptor) == uid)
        except (ModelsRefused, OSError, ValueError, KeyError):
            return False
        return True

    def _move_models(self, ctx: InstallContext) -> None:
        from .models import ModelsRefused, clone_models, runtime_reports_pins

        models = ctx.accounts.models
        try:
            clone_models(ctx.tools, ctx.operator_home / ".ollama" / "models", ctx.paths.models,
                         uid=models.uid, gid=models.uid, base=ctx.paths.prefix)
        except ModelsRefused as refused:
            raise PhaseFailed(str(refused)) from None
        agent = f"gui/{ctx.operator_uid}/{LOGIN_OLLAMA}"
        ctx.tools.bootout(agent)
        ctx.tools.bootstrap(ctx.paths.launch_daemons / "org.docsuri.models.plist")
        if not runtime_reports_pins(ctx.model_tags):
            # Back to your login account's runtime, kept for exactly this (error path).
            ctx.tools.bootout("system/org.docsuri.models")
            definition = ctx.operator_home / "Library" / "LaunchAgents" / f"{LOGIN_OLLAMA}.plist"
            ctx.tools.run(["/bin/launchctl", "bootstrap", f"gui/{ctx.operator_uid}",
                           str(definition)])
            raise PhaseFailed("model-runtime-does-not-report-the-pins")
        ctx.checklist.wait(self.name, "v1-model-calls-answer")
        definition = ctx.operator_home / "Library" / "LaunchAgents" / f"{LOGIN_OLLAMA}.plist"
        remove_login_definition(ctx.operator_home.parent, definition)

    def _move_tunnel(self, ctx: InstallContext) -> None:
        from .tunnel import TunnelMove, TunnelRefused

        move = TunnelMove(
            paths=ctx.paths, tools=ctx.tools, tunnel_name=ctx.tunnel_name,
            tunnel_uid=ctx.accounts.tunnel.uid, operator_uid=ctx.operator_uid,
            cloudflared=ctx.paths.cloudflared_runtime / "cloudflared",
            wait=lambda item: ctx.checklist.wait(self.name, item),
            log=lambda step, outcome: ctx.log.write(self.name, f"tunnel:{step}", outcome),
            place=lambda target, content: write_file(ctx, target, content, 0o644, "root"))
        try:
            move.run()
        except TunnelRefused as refused:
            raise PhaseFailed(str(refused)) from None

    def changes(self, ctx: InstallContext) -> list[Change]:
        found = []
        if not self._models_in_place(ctx):
            found.append(Change(self.name, "models", str(ctx.paths.models),
                                "your home folder's copy -> verified clones, system job",
                                lambda: self._move_models(ctx)))
        credentials = ctx.paths.tunnel_credentials / render.TUNNEL_CREDENTIALS
        if not credentials.exists() or not (ctx.paths.tunnel_config / "active.yml").exists():
            found.append(Change(self.name, "tunnel", ctx.tunnel_name,
                                "your login account's tunnel -> the tunnel account's",
                                lambda: self._move_tunnel(ctx)))
        return found

    def verify(self, ctx: InstallContext) -> None:
        from .models import runtime_reports_pins

        if not self._models_in_place(ctx):
            raise PhaseFailed("models-not-verified")
        if not runtime_reports_pins(ctx.model_tags):
            raise PhaseFailed("model-runtime-does-not-report-the-pins")
        credentials = ctx.paths.tunnel_credentials / render.TUNNEL_CREDENTIALS
        try:
            info = credentials.lstat()
        except FileNotFoundError:
            raise PhaseFailed("tunnel-credentials-missing") from None
        if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o600 or (
            ctx.tools.owner(credentials) != ctx.accounts.tunnel.uid
        ):
            raise PhaseFailed("tunnel-credentials-custody")
        if not (ctx.paths.tunnel_config / "active.yml").is_file():
            raise PhaseFailed("tunnel-active-configuration-missing")
