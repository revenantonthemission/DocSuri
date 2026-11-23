"""`docsuri-release install | rollback | verify | recover` (U8 plan Step 37; cicd-pipeline
§ 5–6, C1, C2, C6, C8, C9, C10, BR4.4, BR6.5, BR10.5, BR10.7).

An in-person fixed command (`sudo -k`, D4). `install` takes the tag as bounded JSON on
standard input (`{"tag": "v2.0.0"}`, D6's one word and bounded input) and runs cicd-pipeline
§ 5.1's steps 0–12:

0. show the tag, its commit, the complete verification's result, the commits and
   migrations, and any arrangement change; you type the commit's short hash to go on,
   on the terminal (`/dev/tty`), never on standard input, which holds the tag;
1. preflight: GitHub's public check runs for the commit, every run of the four check names
   `U8 complete / shared-contracts`, `U8 complete / frontend`, `U8 complete / backend` and
   `U8 complete / browser`, each from the app `github-actions` (a run's `app` key) and each
   passed (recorded, run by run, as its VerificationRun), an annotated tag on `main`, no
   production restore, switch, abort or rollback, isolation passed within 15 minutes, disk
   room, and the performance phase's room (6 GiB available from `vm_stat`, fewer than 60
   requests a minute over 15 minutes); a tag whose folder `release` points to is refused
   (`tag-installed`: `verify` or `rollback` it instead);
2. stage `releases/<tag>/` (decision "The release environment"): the tag's clone, its
   CPython and `uv sync --project backend --frozen --no-build` with `--no-install-package`
   for each local package, then one root-owned `docsuri-release.pth`; the workspace build
   checked against its SHA-256 and its build manifest; `otool -L`; the arrangement version,
   a lower or unknown one refused. An install of the tag `release-previous` names (the
   kept release, after a rollback) reuses that folder when its identity names the tag
   and its commit, without cloning again or moving it, and is refused when they differ
   (`kept-release-differs`) or cannot be read (`kept-release-unreadable`); no folder a
   link points to is ever moved or deleted (your decision of 2026-10-26, "Reuse the
   kept folder"), and only a leftover folder no link points to is removed before a clone;
3. the performance phase from `releases/<tag>/`;
4–6. maintenance (live mode only), stop, and the backup after writes stop;
7. the release's own installer, only for a higher arrangement version, under the marker;
8. each owner's new migrations through the production environment tool;
9. the links swapped atomically (a new link renamed over the old one);
10–12. start and the probe journey, routing back, then the record; the marker goes and
   every folder neither link points to is deleted.

By your decisions of 2026-10-24: step 2 writes the release identity (`.docsuri-release.json`,
`{tag, commit}`, root-owned 0644), which the start's `release` check reads; the release
command's evidence goes to root-owned `control/releases/` (0644), never `profile/`; step 3
runs the release's realm tool as your login account (`release-performance`, the native
database, Playwright from your checkout at the same commit); step 12 completes the
VerificationRun preflight began (`verification-run-<id>.json`, `passed` only when the
complete verification and the performance phase passed) and moves the cutover
(`new_release`, `verification_passed`, the soak). `echo '{"tag": "v2.0.0"}' | docsuri-release
verify` runs steps 0, 1 and 3 again for the installed tag only and records the same
evidence.

By your decisions of 2026-10-25: while the CutoverRecord is rolled-back with no dry run
accepted since the rollback, an install stages, migrates and switches the release but
leaves v2's three roles stopped; they start with the soak ("Keep v2 stopped"), and the
release's probe journey runs then: the cutover's verification is recorded only once it
passed, so such an install records none (`release-not-probed`), and only `verify`, once
a dry run is accepted, records it after the probe passes. Each command is its own run,
and every release effect's key belongs to that run, the backup after writes stop
included, so a second `rollback` (or a reinstall) of the same tag acts again, and takes a
new set, instead of replaying the first one's receipts. Every effect is kept in
`control/releases/effect-journal.json` until it settled, the backup with the bound
operation it runs, and each run first settles what an earlier run left unsettled by its
receipt (`u8_protocols.settle_earlier`, the backup through the procedures' own operator),
never by running it again: an effect still within its lease refuses the run
(`effect-in-progress`), so nothing runs beside it; one past its lease, or with an
unknown outcome, is reconciled from its target; one whose effect never ran runs nothing.

The ways out (§ 5.4, § 6; the review's findings of 2026-10-26):

- Before the swap, any failure (a stop that stopped only some roles, the backup, the
  apply, a migration, anything unexpected) starts again each role this run stopped and
  the fixed program reported loaded before the stop (`wasLoaded`), routes the address
  back, and ends the record `failed`; while the CutoverRecord is rolled-back nothing
  starts again, since only the soak's start starts v2 then.
- After the swap, any failure (a start, readiness not within 10 minutes, the probe
  journey, anything unexpected) is § 6's switch back to `release-previous`; a switch back
  that does not complete (the previous release not ready within its own 10 minutes
  included) still ends the record and answers `switch-back-failed`, and the public
  address stays on the maintenance notice until v2 is ready.
- A switch back never points `release` at a kept release whose record is rolled-back,
  failed or switched-back (your decision of 2026-10-26, "Stay put, v2 stopped"): the
  links stay on the release that failed, v2 stays stopped, the record carries
  `recover-required`, and `recover` keeps v2 stopped and answers the one way out: a new
  tag (fix the release, then `docsuri-release install` with it; your decision of
  2026-10-27, "Drop that remedy": no earlier release remains under `releases/` after a
  completed install, and no link is ever edited by hand). A stop that failed in that switch
  back is kept as the record's and the answer's `step`, the answer says `v2: running`,
  and `recover` stops v2's three roles before it answers (review finding, Major, R20).
  The same way out when a switch back finds no kept release at all (after a switch back
  both links name the kept release, which then fails its own probe): the record stays
  `installed` and waiting with `switch-back-failed` (step `no-kept-release`), and
  `recover` keeps v2 stopped and answers `recover-required` with the new tag.
- A kept release relinked, by a switch back as by a rollback, whose probe a later
  install superseded waits for its probe again at once, so `verify` probes it before
  any soak (review finding, Major, R21).
- `verify` starts v2's roles only to probe a linked release still waiting for its probe,
  or to start the soak on the linked release after a failed probe's switch back, which
  that switch back marks on its record (`v2Stopped`), and, from rolled-back with an
  accepted dry run, as the soak's start (your decisions of 2026-10-25, "Follow the
  design", and of 2026-10-26, "Only for a pending probe"). Otherwise a v2 you stopped in
  person stays stopped: `verify` answers `v2-stopped` and offers the operator tool's
  `service start`. An interrupted `verify` undoes its own starts, `recover` has nothing
  to do for it, and `verify` run again completes it.
- A route back that fails after a ready, probed start is tried once more; if it still
  fails the release stays installed (it runs) and `recover` routes the address.
- Ctrl-C, a closed terminal (SIGHUP) or SIGTERM end the record as an interruption.
- Each command holds `control/releases/release-run.lock` while it runs: a root-only
  file (0600) no other account can open, so no other account can hold the lock. Beside
  it the command writes `control/releases/release-run.json` (0644: its pid, word and
  start) right after taking the lock and removes it at its end, so the operator tool's
  `service stop|start`, the soak's start and `cutover check`'s set retry read that
  marker without a password and without locking anything (`release_run_active`: the
  marker's process alive is `release-run-active`; one whose process is gone is refused
  `release-run-marker-stale` until the next release command removes it under the real
  lock) and refuse while a release command runs (your decision of 2026-10-26, "Check
  the release run lock"). `recover`, refused while another release command runs, puts what
  an interrupted or incomplete run left in a known state: a record still `installing` is
  switched back (or ended `failed` before the swap), one still `rolling-back` ends by
  where the links stand, v2's roles are restarted (or kept stopped after a rollback) and
  the address routed back.

An install holds the live exclusion in the ledger (a ReleaseRecord in `installing`), so no
backup, verification or disposal starts during it. `rollback` is refused while anything
holds that exclusion (a production restore, a cutover's switch, abort or rollback, an
install), holds it itself while it runs (`rolling-back`), and switches the links back
behind the maintenance notice: from the release `release` points to (its identity file)
to the kept one `release-previous` points to, refused when that one is the same folder,
missing, a release whose record is closed (rolled-back, failed or switched-back), or a
folder whose identity cannot be read. While the CutoverRecord is rolled-back with no dry
run accepted since, it switches the links and leaves v2 stopped; the cutover record then
names the tag the links point to.
"""

from __future__ import annotations

import contextlib
import datetime as dt
import fcntl
import hashlib
import io
import json
import os
import re
import shutil
import signal
import sys
import tarfile
import time
import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import BinaryIO

# The reason keys a record carries when its run left something for `recover` (the
# cutover's soak start reads them too).
from backend.modules.operations.release_records import RECOVERABLE

from docsuri_ops.arrangement import manifest as arrangement_manifest
from docsuri_ops.arrangement.paths import ArrangementPaths

WORDS = ("install", "rollback", "verify", "recover")
RELEASE_IDENTITY = ".docsuri-release.json"  # read by the start's `release` check
VERIFICATION_RUN = "verification-run-{}.json"
TAG = re.compile(r"v\d{1,4}\.\d{1,4}\.\d{1,4}")
REPOSITORY = "revenantonthemission/DocSuri"
# The complete verification lane's check names: its jobs' `name:` lines in
# `.github/workflows/u8-complete-verification.yml`, which no other workflow reports (the
# infrastructure re-check's R-13; cicd-pipeline § 3.2).
COMPLETE_VERIFICATION = ("U8 complete / shared-contracts", "U8 complete / frontend",
                         "U8 complete / backend", "U8 complete / browser")
# The app all four check runs come from (a check run's `app.slug`).
CHECK_APP = "github-actions"
WORKSPACE_ASSET = "docsuri-workspace.tar.gz"
WORKSPACE_DIGEST_ASSET = "docsuri-workspace.tar.gz.sha256"
BUILD_MANIFEST = ".docsuri-build.json"
MEMORY_FLOOR = 6 * 1024**3
REQUEST_RATE_CEILING = 60.0
ISOLATION_FRESHNESS = dt.timedelta(minutes=15)
READY_BOUND = dt.timedelta(minutes=10)
READY_POLL_SECONDS = 5
DISK_FLOOR = 20 * 1024**3
# Each command holds this lock while it runs (`recover` refuses while one does), and every
# effect is kept in the journal until it settled. The lock file is root-only (0600); the
# marker beside it (0644: pid, word, startedAt) is what other accounts read, never lock
# (review findings, Major, R19–R21).
RUN_LOCK = "release-run.lock"
RUN_MARKER = "release-run.json"
RUN_ACTIVE = "release-run-active"
RUN_STALE = "release-run-marker-stale"
RUN_UNREADABLE = "release-run-lock-unreadable"
# What `verify` offers when v2 is stopped and nothing waits for a probe (your decision of
# 2026-10-26, "Only for a pending probe"): the operator tool's in-person start, per label.
SERVICE_START = ("echo '{}' | /Library/DocSuri/release/.venv/bin/python -I -m "
                 "docsuri_ops.u8_platform service start <label> --production")
EFFECT_JOURNAL = "effect-journal.json"
JOURNAL_LIMIT = 64
UNSETTLED = ("effect-outcome-unknown", "effect-in-progress")
ROUTE_BACK_ATTEMPTS = 2
# The local packages uv may not install (decision "The release environment"): each is put
# on the path through `docsuri-release.pth` instead, from the release's own source tree.
LOCAL_PACKAGES = ("docsuri-shared", "docsuri-discovery", "docsuri-summarization",
                  "docsuri-ops", "docsuri-platform-integrity")
SOURCE_ROOTS = (".", "shared/python/src", "ops/src", "platform_integrity/src",
                "ingestion/src", "backend/modules/discovery/src",
                "backend/modules/summarization/src")
PTH = "docsuri-release.pth"
ENTRY_MODULES = ("backend.u8_main", "backend.maintenance_server",
                 "docsuri_ops.standing.main", "docsuri_ops.production_tool",
                 "docsuri_ops.release", "docsuri_ops.arrangement.installer",
                 "backend.modules.operations.ledger_cli",
                 "docsuri_ops.backup_agent.cli", "docsuri_ops.isolation_check",
                 "docsuri_ops.u8_platform.operator_tool", "docsuri_ops.u8_platform.adapter",
                 "docsuri_ops.u8_platform.recovery_words", "docsuri_ops.u8_platform.decisions",
                 "docsuri_ops.u8_platform.in_person", "docsuri_ops.u8_platform.service_words",
                 "docsuri_ops.cutover.tool",
                 "docsuri_ops.migration.words")


class Refused(Exception):
    """The install stopped; the message is a fixed key. `changed` is False when nothing
    of production changed yet."""

    def __init__(self, reason: str, *, changed: bool = False, **facts):
        super().__init__(reason)
        self.reason, self.changed, self.facts = reason, changed, facts


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


# --- the complete verification's check runs (step 1) ------------------------------------------


def verification_runs(runs: list[dict]) -> list[dict]:
    """Every run whose name is one of `COMPLETE_VERIFICATION`, from any app, sorted by
    name and then by id as an integer, a run without an id after the other runs of its
    name."""
    return sorted((run for run in runs if run.get("name") in COMPLETE_VERIFICATION),
                  key=lambda run: (run["name"], run.get("id") is None, run.get("id") or 0))


def passed_verification(runs: list[dict]) -> list[dict]:
    """`verification_runs(runs)` when the lane passed for the commit, or refused with the
    checks concerned named (BR10.5). A run of one of the names from an app other than
    `CHECK_APP`, or naming no app, is `complete-verification-ambiguous`: a name alone
    cannot tell it from the lane's own. Then a name with no run, or with any run not
    completed with success (a run the lane's own concurrency cancelled included), is
    `complete-verification-not-passed`. Several runs of one name are read together, none
    is picked, and each must have passed (reading CP-5(a))."""
    found = verification_runs(runs)
    foreign = {run["name"] for run in found if run.get("app") != CHECK_APP}
    if foreign:
        raise Refused("complete-verification-ambiguous",
                      checks=[name for name in COMPLETE_VERIFICATION if name in foreign])
    failed = [name for name in COMPLETE_VERIFICATION
              if not any(run["name"] == name for run in found) or any(
                  run["name"] == name and (run.get("status") != "completed"
                                           or run.get("conclusion") != "success")
                  for run in found)]
    if failed:
        raise Refused("complete-verification-not-passed", checks=failed)
    return found


# --- the release environment (step 2) --------------------------------------------------------


def sync_command(uv: Path, folder: Path) -> list[str]:
    """`uv sync --project backend --frozen --no-build`, the local packages left out."""
    argv = [str(uv), "sync", "--project", str(folder / "backend"), "--frozen", "--no-build",
            "--no-dev"]
    for package in LOCAL_PACKAGES:
        argv += ["--no-install-package", package]
    return argv


def sync_environment(folder: Path, *, uv: Path) -> dict:
    """The variables uv runs with: the environment and CPython inside the release
    folder, at their final paths, and nothing from a home folder (BR6.5)."""
    return {"PATH": "/usr/bin:/bin", "UV_PROJECT_ENVIRONMENT": str(folder / ".venv"),
            "UV_PYTHON_INSTALL_DIR": str(folder / ".python"), "UV_PYTHON_PREFERENCE":
            "only-managed", "UV_CACHE_DIR": str(folder / ".uv-cache"), "HOME": str(folder),
            "UV_NO_CONFIG": "1"}


def pth_lines(folder: Path) -> str:
    return "".join(f"{(folder / root).resolve() if root == '.' else folder / root}\n"
                   for root in SOURCE_ROOTS)


def site_packages(folder: Path) -> Path:
    found = sorted((folder / ".venv" / "lib").glob("python3.*/site-packages"))
    if len(found) != 1:
        raise Refused("release-environment-site-packages")
    return found[0]


def _write_public(path: Path, payload: bytes, *, owner_uid: int = 0) -> None:
    """A file anyone may read and only its owner (root, as the release command runs)
    writes: 0644, written whole through a pending name renamed over, never a link."""
    pending = path.with_name(path.name + ".pending")
    if pending.is_symlink() or pending.exists():
        pending.unlink()
    descriptor = os.open(pending, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
    try:
        os.fchmod(descriptor, 0o644)
        if os.geteuid() == 0:
            os.fchown(descriptor, owner_uid, 0)
        os.write(descriptor, payload)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    os.replace(pending, path)


def write_identity(folder: Path, tag: str, commit: str, *, owner_uid: int = 0) -> Path:
    """The release identity (your decision of 2026-10-24): a root-owned
    `.docsuri-release.json` (`{tag, commit}`, 0644) the start's `release` check reads."""
    target = folder / RELEASE_IDENTITY
    _write_public(target, json.dumps({"tag": tag, "commit": commit}, sort_keys=True).encode(),
                  owner_uid=owner_uid)
    return target


def folder_identity(folder: Path) -> dict | None:
    """A release folder's identity file, or None: a regular file (never a link, never a
    FIFO) of at most 4 KiB holding `{tag, commit}`."""
    import stat as stat_module

    try:
        descriptor = os.open(folder / RELEASE_IDENTITY,
                             os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError:
        return None
    try:
        info = os.fstat(descriptor)
        if not stat_module.S_ISREG(info.st_mode) or info.st_size > 4096:
            return None
        value = json.loads(os.read(descriptor, 4096))
    except (OSError, ValueError):
        return None
    finally:
        os.close(descriptor)
    if not isinstance(value, dict) or set(value) != {"tag", "commit"} or not (
            isinstance(value["tag"], str) and TAG.fullmatch(value["tag"])):
        return None
    return value


def linked_identity(paths: ArrangementPaths) -> dict | None:
    """The identity file of the release `release` points to, or None."""
    return folder_identity(paths.release)


def linked_tag(paths: ArrangementPaths) -> str | None:
    """The tag of the release `release` points to: its identity, else its folder's name
    (a folder the installer staged before identities existed); None without the link.
    The cutover's soak and switch read it too (review finding, Major, R13): nothing
    starts for a tag the links do not point to."""
    link = paths.release
    if not link.is_symlink():
        return None
    return (linked_identity(paths) or {}).get("tag") or Path(os.readlink(link)).name


def _points_to(link: Path, folder: Path) -> bool:
    """Whether `link` is a link that resolves to `folder`."""
    try:
        return link.is_symlink() and link.resolve() == folder.resolve()
    except OSError:
        return False


def write_pth(folder: Path, *, owner_uid: int = 0) -> Path:
    """One root-owned `docsuri-release.pth` listing the release's own source roots."""
    target = site_packages(folder) / PTH
    descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o644)
    try:
        os.fchmod(descriptor, 0o644)
        if os.geteuid() == 0:
            os.fchown(descriptor, owner_uid, 0)
        os.write(descriptor, pth_lines(folder).encode())
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    return target


# --- the workspace build ----------------------------------------------------------------------


def check_build_manifest(dist: Path) -> dict:
    """`dist/.docsuri-build.json`: `{"version": 1, "files": [{path, sha256, size,
    contentHashed}]}`, every listed file present at its digest and size."""
    try:
        value = json.loads((dist / BUILD_MANIFEST).read_bytes())
    except (OSError, ValueError):
        raise Refused("build-manifest-unreadable") from None
    if not isinstance(value, dict) or value.get("version") != 1 or not isinstance(
        value.get("files"), list
    ):
        raise Refused("build-manifest-form")
    for item in value["files"]:
        if not isinstance(item, dict) or set(item) != {"path", "sha256", "size", "contentHashed"}:
            raise Refused("build-manifest-form")
        path = dist / str(item["path"])
        if ".." in Path(str(item["path"])).parts or not path.is_file() or path.is_symlink():
            raise Refused("build-file-missing")
        data = path.read_bytes()
        if len(data) != item["size"] or hashlib.sha256(data).hexdigest() != item["sha256"]:
            raise Refused("build-file-differs")
    for name in ("maintenance.html", "privacy.html", "terms.html"):
        if not (dist / name).is_file():
            raise Refused("build-page-missing")
    return value


def unpack_workspace(archive: bytes, expected: str, into: Path) -> dict:
    """The release asset, refused unless its SHA-256 equals the release's; unpacked into
    `frontend/dist` under tarfile's `data` filter, then its build manifest checked."""
    if hashlib.sha256(archive).hexdigest() != expected:
        raise Refused("workspace-build-digest-differs")
    dist = into / "frontend" / "dist"
    if dist.exists():
        shutil.rmtree(dist)
    dist.mkdir(parents=True)
    try:
        with tarfile.open(fileobj=io.BytesIO(archive)) as unpacked:
            unpacked.extractall(dist, filter="data")
    except (tarfile.TarError, OSError):
        raise Refused("workspace-build-unreadable") from None
    return check_build_manifest(dist)


# --- the performance phase as your login account (step 3; cicd-pipeline § 5.2) -----------------

SUDO = "/usr/bin/sudo"
GIT = "/usr/bin/git"
PERFORMANCE_PHASE = "release-performance"
LOCKFILE = "frontend/pnpm-lock.yaml"
REALM_MANIFEST = "/tmp/docsuri-u8-run/environment.json"


def performance_command(folder: Path, *, operator: str, checkout: Path,
                        variables: dict[str, str] | None = None) -> list[str]:
    """Step 3 (your decision of 2026-10-24): the release's own realm tool, with the
    release's `.venv`, as your login account (`sudo -n -u <operator>`), on the native
    database under `runtimes/postgresql-16.14`; Playwright comes from your checkout,
    which measures the release's code. `variables` (no secret: v1's counted rate) reach
    the phase through `env`, since sudo resets the environment."""
    assignments = [f"{name}={value}" for name, value in sorted((variables or {}).items())]
    return [SUDO, "-n", "-u", operator, "/usr/bin/env", *assignments,
            str(folder / ".venv" / "bin" / "python"), "-I",
            str(folder / "scripts" / "verify_docsuri_u8.py"), "--phase", PERFORMANCE_PHASE,
            "--database", "native", "--profile", "synthetic-local", "--environment-file",
            REALM_MANIFEST, "--playwright", str(checkout)]


def checkout_checks(checkout: Path, *, commit: str, folder: Path,
                    git: Callable[[list[str]], tuple[int, str]]) -> None:
    """Your checkout, whose Playwright measures the release: at the release's commit, a
    clean tree, and a `frontend/pnpm-lock.yaml` equal to the release's. `git(args)` runs
    git in the checkout as your login account and returns (status, output)."""
    if not checkout.is_absolute() or not (checkout / ".git").exists():
        raise Refused("playwright-checkout-missing")
    status, head = git(["rev-parse", "HEAD"])
    if status != 0 or head.strip() != commit:
        raise Refused("playwright-checkout-commit-differs")
    status, changes = git(["status", "--porcelain"])
    if status != 0 or changes.strip():
        raise Refused("playwright-checkout-not-clean")
    try:
        same = digest_file(checkout / LOCKFILE) == digest_file(folder / LOCKFILE)
    except OSError:
        same = False
    if not same:
        raise Refused("playwright-lockfile-differs")


def digest_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# --- staging (step 2), shared with the installer's phase 2 --------------------------------------


@dataclass
class Stager:
    """Step 2 alone (cicd-pipeline § 5.1; your decision of 2026-10-24, "Staging in the
    installer"): GitHub's checks of the tag (annotated, on `main`, the complete
    verification passed), then the clone, the sync, the `.pth`, the workspace build, the
    library check and the arrangement version, and the release identity file. It needs
    no operator and no ledger, so the installer stages through it before either exists."""

    paths: ArrangementPaths
    github: object
    clone: Callable[[str, Path], None]
    sync: Callable[[Path], None]
    libraries_outside: Callable[[Path], list[str]] = field(default=lambda folder: [])
    owner_uid: int = 0

    def checked(self, tag: str) -> tuple[dict, list[dict]]:
        """The tag's commit and its complete-verification check runs, or refused; `runs`
        holds every run of each name."""
        if not TAG.fullmatch(tag):
            raise Refused("tag-outside-its-form")
        found = self.github.tag(tag)
        if found is None:
            raise Refused("tag-unknown")
        if not found.get("annotated"):
            raise Refused("tag-not-annotated")
        if not self.github.on_main(found["sha"]):
            raise Refused("tag-not-on-main")
        runs = passed_verification(self.github.check_runs(found["sha"]))
        return found, runs

    def stage(self, tag: str, commit: str) -> dict:
        """The tag staged at `releases/<tag>/`, its final path (uv's environment and the
        `.pth` name it). The folder `release` points to is never staged over
        (`tag-installed`). The folder `release-previous` points to (the kept release,
        after a rollback) is reused as it stands when its identity names this tag and
        commit, with no clone and no move, and refused otherwise (your decision of
        2026-10-26, "Reuse the kept folder"): no folder a link points to is ever moved or
        deleted, so a run killed during staging leaves the kept release whole. A folder of
        the tag's name that no link points to is a leftover (a staging that was killed):
        it is removed and the tag cloned afresh."""
        folder = self.paths.releases / tag
        if _points_to(self.paths.release, folder):
            raise Refused("tag-installed", offered=["verify", "rollback"])
        if _points_to(self.paths.release_previous, folder):
            return self._reuse_kept(tag, commit, folder)
        if folder.is_symlink():
            folder.unlink()
        elif folder.exists():
            shutil.rmtree(folder)
        try:
            self.clone(tag, folder)
            self.sync(folder)
            write_pth(folder, owner_uid=self.owner_uid)
            digest = self.github.asset(tag, WORKSPACE_DIGEST_ASSET).decode().split()[0]
            build = unpack_workspace(self.github.asset(tag, WORKSPACE_ASSET), digest, folder)
            version, installed = self._checked_folder(folder)
            write_identity(folder, tag, commit, owner_uid=self.owner_uid)
        except BaseException:
            shutil.rmtree(folder, ignore_errors=True)
            raise
        return {"folder": folder, "arrangementVersion": version, "files": len(build["files"]),
                "arrangementChange": installed is not None and version > installed,
                "reused": False}

    def _checked_folder(self, folder: Path) -> tuple[int, int | None]:
        """The library check and the arrangement version of a staged folder: the version,
        and the installed one (None before any arrangement)."""
        if self.libraries_outside(folder):
            raise Refused("release-loads-outside")
        version = _arrangement_version(folder)
        recorded = arrangement_manifest.read_manifest(self.paths)
        installed = None if recorded is None else recorded.version
        if version is None or (installed is not None and version < installed):
            raise Refused("arrangement-version-refused")
        return version, installed

    def _reuse_kept(self, tag: str, commit: str, folder: Path) -> dict:
        """The kept release's folder reused for the tag it already holds: its identity
        must name this tag and commit (`kept-release-differs` otherwise,
        `kept-release-unreadable` without one), its build manifest, libraries and
        arrangement version are checked again, and nothing in it is written or moved."""
        kept = folder_identity(folder)
        if kept is None:
            raise Refused("kept-release-unreadable")
        if kept != {"tag": tag, "commit": commit}:
            raise Refused("kept-release-differs", keptTag=kept["tag"])
        build = check_build_manifest(folder / "frontend" / "dist")
        version, installed = self._checked_folder(folder)
        return {"folder": folder, "arrangementVersion": version, "files": len(build["files"]),
                "arrangementChange": installed is not None and version > installed,
                "reused": True}

    def stage_checked(self, tag: str) -> Path:
        """The installer's phase 2: the checks, then the staged folder."""
        found, _ = self.checked(tag)
        return self.stage(tag, found["sha"])["folder"]


# --- what the install needs from the platform -------------------------------------------------


@dataclass
class ReleasePlatform:
    """Every outside part of an install, so tests run it under a temporary prefix with a
    fake GitHub API and the realm driver."""

    # check_runs(sha) -> [{name, status, conclusion, id, app}] (the four `U8 complete / …`
    # names from the app `github-actions`), tag(tag) -> {sha, annotated}, on_main(sha),
    # asset(tag, name)
    github: object
    clone: Callable[[str, Path], None]
    sync: Callable[[Path], None]
    confirm: Callable[[dict], str]
    ledger: object
    operator: object
    run_installer: Callable[[Path], dict]
    migrate: Callable[[Path], dict]
    performance: Callable[[Path], dict]
    memory_available: Callable[[], int | None]
    request_rate: Callable[[], float]
    isolation: Callable[[], dict | None]
    disk_free: Callable[[], int]
    ready: Callable[[], bool]
    probe: Callable[[], bool]
    # The backup after writes stop: `backup(tag, key)`, the key this run's own (it names
    # the set), answering the set's record, or raising when the set failed.
    backup: Callable[[str, str], dict]
    mode: Callable[[], str]
    # The backup's bound operation, kept in the journal before the set is taken
    # (`backup_plan(tag, key)` -> {operation, target, inputs, key, environment}), and an
    # earlier run's pending backup settled by its receipt under that operation, by the
    # backup's own operator, its set recorded when it applied (`backup_settle(effect)`,
    # raising `EffectUnsettled` while it cannot settle): a pending backup is never taken
    # again (review finding, Major, R14).
    backup_plan: Callable[[str, str], dict] | None = None
    backup_settle: Callable[[dict], dict | None] | None = None
    libraries_outside: Callable[[Path], list[str]] = field(default=lambda folder: [])
    v2_labels: tuple[str, ...] = ("org.docsuri.v2.host", "org.docsuri.v2.workers",
                                  "org.docsuri.v2.scheduler")
    commits_since: Callable[[str, str], list[str]] = field(default=lambda old, new: [])
    sleep: Callable[[float], None] = time.sleep
    # The CutoverRecord's policy (the verification and soak moves, BR10.5).
    policy: object = None


@dataclass
class Step:
    name: str
    started: float
    seconds: float = 0.0


class ReleaseInstall:
    def __init__(self, paths: ArrangementPaths, platform: ReleasePlatform, *,
                 clock: Callable[[], dt.datetime] = _now, owner_uid: int = 0,
                 monotonic: Callable[[], float] = time.monotonic):
        from backend.modules.operations.release_records import ReleaseRecords

        self.paths, self.platform, self.clock = paths, platform, clock
        self.owner_uid, self.monotonic = owner_uid, monotonic
        self.records = ReleaseRecords(platform.ledger, clock=clock)
        self.steps: list[Step] = []
        self.marker_written = False
        self.run_id = uuid.uuid4().hex[:16]
        self._stopped: list[str] = []
        self._started: list[str] = []
        self._routed_maintenance = False
        # Whether this run changed anything of production yet (a record begun, an effect
        # run): an interruption before then answers `changed: false` (review finding,
        # Minor, R14). `way_out` is what an interruption offers.
        self.touched = False
        self.way_out = ["docsuri-release recover"]

    def _new_run(self) -> None:
        """Each command (`install`, `verify`, `rollback`, `recover`) is its own run, and
        each release effect's key belongs to it: a later run of the same tag (a second
        rollback, a reinstall) acts again instead of replaying an earlier run's receipts."""
        self.run_id = uuid.uuid4().hex[:16]
        self._stopped, self._started, self._routed_maintenance = [], [], False
        self.touched = False

    @contextlib.contextmanager
    def _locked(self, word: str) -> Iterator[None]:
        """The run lock (`control/releases/release-run.lock`), held exclusively while one
        command runs; a second command is refused (`release-run-active`). The system
        releases it when the process ends, however it ends, so `recover` can tell a live
        run from one that stopped. The lock file is root-only (0600), so no other account
        can hold it; the marker written beside it (`run_lock`) is what
        `release_run_active` reads without a password (your decision of 2026-10-26,
        "Check the release run lock"; review findings, Major, R19–R21)."""
        with run_lock(self.paths, word, clock=self.clock):
            yield

    # --- helpers -------------------------------------------------------------------------

    def _step(self, name: str, work: Callable[[], object]) -> object:
        step = Step(name, self.monotonic())
        try:
            return work()
        finally:
            step.seconds = self.monotonic() - step.started
            self.steps.append(step)

    # --- the effect journal (review finding, Major, R12) ----------------------------------

    def _journal(self) -> list[dict]:
        path = self.paths.control / "releases" / EFFECT_JOURNAL
        try:
            value = json.loads(path.read_bytes())
        except FileNotFoundError:
            return []
        except (OSError, ValueError):
            raise Refused("effect-journal-unreadable") from None
        entries = value.get("entries") if isinstance(value, dict) else None
        if not isinstance(entries, list):
            raise Refused("effect-journal-unreadable")
        return [entry for entry in entries if isinstance(entry, dict) and "key" in entry]

    def _journal_put(self, entry: dict) -> None:
        """One entry written (or replaced by its key); every pending entry is kept, and
        the latest settled ones up to the journal's bound."""
        entries = [item for item in self._journal() if item["key"] != entry["key"]] + [entry]
        pending = [item for item in entries if item.get("state") == "pending"]
        settled = [item for item in entries if item.get("state") != "pending"]
        room = JOURNAL_LIMIT - len(pending)
        self._evidence(EFFECT_JOURNAL, {"entries": pending + (settled[-room:] if room > 0
                                                              else [])})

    def _settle_earlier(self) -> None:
        """Before this run's first effect: every effect an earlier run left unsettled
        (interrupted, or its outcome unknown), settled by its own key. One still within
        its lease refuses this run (`effect-in-progress`), so nothing runs beside it; an
        unknown one is reconciled from its target, and PlatformControl's status no longer
        holds it as unresolved."""
        from docsuri_ops.platform_control.errors import ControlError
        from docsuri_ops.u8_platform.u8_protocols import (
            EffectUnsettled,
            PreconditionRefused,
            settle_earlier,
        )

        for entry in self._journal():
            if entry.get("state") != "pending":
                continue
            if entry.get("kind") == "backup":
                self._settle_backup(entry)
                continue
            try:
                settle_earlier(self.platform.operator, str(entry["operation"]),
                               str(entry["target"]), dict(entry["inputs"]), key=entry["key"])
            except EffectUnsettled as unsettled:
                raise Refused(unsettled.reason or "effect-outcome-unknown") from None
            except PreconditionRefused as refused:
                raise Refused(refused.reason) from None
            except ControlError:
                raise Refused("earlier-effect-unreadable") from None
            self._journal_put({**entry, "state": "settled"})

    def _settle_backup(self, entry: dict) -> None:
        """An earlier run's backup after writes stop that never settled (interrupted, its
        outcome unknown, or a failure the run could not tell from one after binding),
        settled by its receipt under the bound operation the journal kept, never by
        taking the set again (review finding, Major, R14), as `settle_earlier` settles
        every other effect:

        - its effect never ran (its bound input is absent, the run stopped before the
          set was bound): nothing runs, and once its lease passed an operation bound
          but stopped before its input was written is reconciled not applied;
        - its operation is still within its lease: this run is refused
          (`effect-in-progress`), so nothing runs beside it;
        - after its lease, or with an unknown outcome, it is reconciled from its target,
          so PlatformControl's status no longer holds it as unresolved; one that cannot
          be proven refuses the run (`effect-outcome-unknown`);
        - it applied: its set is recorded from the receipt.

        This is the backup's own operator's work (`backup_settle`). Until it settles,
        the entry stays pending and the run is refused. An entry with no bound operation
        kept (a platform that names none) has nothing to settle it by: nothing runs for
        it."""
        from docsuri_ops.platform_control.errors import ControlError
        from docsuri_ops.u8_platform.u8_protocols import EffectUnsettled, PreconditionRefused

        effect = entry.get("effect")
        settled = {**entry, "state": "settled"}
        if isinstance(effect, dict):
            if self.platform.backup_settle is None:
                raise Refused("earlier-backup-unsettled")
            try:
                result = self.platform.backup_settle(effect)
            except EffectUnsettled as unsettled:
                raise Refused(unsettled.reason or "effect-outcome-unknown") from None
            except ControlError:
                # PlatformControl could not read the earlier receipt: settling it now could
                # forget a set that applied, so it waits for the store.
                raise Refused("earlier-effect-unreadable") from None
            except PreconditionRefused as refused:
                result = {"integrity": "failed", "reason": refused.reason}
            except Exception as error:  # noqa: BLE001 - settled, its failure recorded
                result = {"integrity": "failed",
                          "reason": _reason_of(error, "earlier-backup-unsettled")}
            # Only an unsettled outcome, or an unreadable receipt, keeps the entry pending
            # (review finding, Critical, R15): a deterministic failure is recorded on the
            # settled entry, so it never refuses every later command.
            if isinstance(result, dict) and result.get("integrity") == "failed":
                settled["failure"] = _key(str(result.get("reason") or "backup-failed"))
        self._journal_put(settled)

    def _effect(self, operation: str, target: str, inputs: dict, *, key: str) -> dict:
        """One bound operation run to a settled outcome (`execute_settled`): a receipt an
        earlier run left with nothing applied under this key runs again under its next
        retry key instead of failing every later run. The journal keeps it pending until
        it settled, so a run that stops inside it leaves it for the next run to settle.
        A precondition refusal settles it (nothing was bound); a PlatformControl error
        keeps it pending, since it may have come after the receipt was bound (settling
        or reconciling it), and the next run settles it by its receipt."""
        from docsuri_ops.platform_control.errors import ControlError
        from docsuri_ops.u8_platform.u8_protocols import (
            EffectUnsettled,
            PreconditionRefused,
            execute_settled,
        )

        entry = {"key": key, "kind": "effect", "operation": operation, "target": target,
                 "inputs": inputs, "state": "pending"}
        self._journal_put(entry)
        self.touched = True
        try:
            receipt = execute_settled(self.platform.operator, operation, target, inputs, key=key)
        except PreconditionRefused as refused:
            self._journal_put({**entry, "state": "settled"})
            raise Refused(refused.reason, changed=True) from None
        except ControlError as refused:
            raise Refused(getattr(refused, "reason", "effect-refused"), changed=True) from None
        except EffectUnsettled as unsettled:
            if unsettled.kind == "failed":
                self._journal_put({**entry, "state": "settled"})
            raise Refused(unsettled.reason or f"{operation.removeprefix('platform.')}-failed",
                          changed=True) from None
        self._journal_put({**entry, "state": "settled"})
        return receipt

    def _run_key(self, tag: str, *parts: str) -> str:
        """A release effect's key: this run's own (`run_id`), the tag, and the step within
        the run, so no other run ever replays its receipt (Step 38 item 7)."""
        return ":".join(("release", self.run_id, tag, *parts, str(len(self.steps))))

    def _services(self, tag: str, action: str, labels: list[str] | None = None) -> None:
        """v2's three roles (or `labels`) started or stopped, each under this run's own
        key. The roles this run stopped are kept, so a way out starts exactly those, and
        only the ones the fixed program reports as loaded before the stop (`wasLoaded`,
        carried in the receipt's facts; review finding, Minor, R13): a role that was down
        before the run began stays down. The roles this run started from unloaded are kept
        too, so an interrupted `verify` stops exactly those."""
        for label in labels if labels is not None else self.platform.v2_labels:
            receipt = self._effect("platform.service.control", label,
                                   {"label": label, "action": action},
                                   key=self._run_key(tag, action, label))
            was_loaded = _was_loaded(receipt)
            if action == "stop":
                if was_loaded and label not in self._stopped:
                    self._stopped.append(label)
                if label in self._started:
                    self._started.remove(label)
            else:
                if label in self._stopped:
                    self._stopped.remove(label)
                if not was_loaded and label not in self._started:
                    self._started.append(label)

    def _route(self, tag: str, origin: str) -> None:
        if origin == "maintenance":
            self._routed_maintenance = True  # a way out routes back even if this failed
        self._effect("platform.tunnel.route", "tunnel", {"origin": origin},
                     key=self._run_key(tag, "route", origin))
        if origin == "v2-host":
            self._routed_maintenance = False

    def _current(self) -> Path | None:
        link = self.paths.release
        return Path(os.readlink(link)) if link.is_symlink() else None

    def _linked_tag(self) -> str | None:
        """The tag of the release `release` points to (`linked_tag`)."""
        return linked_tag(self.paths)

    def _installed_version(self) -> int | None:
        recorded = arrangement_manifest.read_manifest(self.paths)
        return None if recorded is None else recorded.version

    # --- step 0 and 1 ----------------------------------------------------------------------

    def show(self, tag: str) -> dict:
        github = self.platform.github
        found = github.tag(tag)
        if found is None:
            raise Refused("tag-unknown")
        runs = github.check_runs(found["sha"])
        previous = self.records.installed()
        return {
            "tag": tag, "commit": found["sha"], "shortHash": found["sha"][:12],
            "verification": [{"name": run["name"], "app": run.get("app"),
                              "status": run.get("status"), "conclusion": run.get("conclusion"),
                              "id": run.get("id")} for run in verification_runs(runs)],
            "commits": self.platform.commits_since(
                previous["releaseCommit"] if previous else "", found["sha"]),
        }

    def confirm(self, shown: dict) -> None:
        """Step 0's typed short hash. A confirmation that cannot be read (no terminal, an
        end of input) is refused before anything changes, never a traceback."""
        try:
            typed = self.platform.confirm(shown)
        except Exception:  # noqa: BLE001 - any unreadable answer is no confirmation
            raise Refused("confirmation-unavailable") from None
        if not isinstance(typed, str) or typed.strip() != shown["shortHash"]:
            raise Refused("short-hash-differs")

    def _stager(self) -> Stager:
        platform = self.platform
        return Stager(self.paths, platform.github, platform.clone, platform.sync,
                      libraries_outside=platform.libraries_outside, owner_uid=self.owner_uid)

    def preflight(self, tag: str, shown: dict, *, running: bool = False) -> dict:
        """Step 1. `running` is `verify`'s: the tag is the running release; an install's
        tag never is."""
        found, runs = self._stager().checked(tag)
        if not running and _points_to(self.paths.release, self.paths.releases / tag):
            # The running release is verified or rolled back, never staged over.
            raise Refused("tag-installed", offered=["verify", "rollback"])
        exclusion = self.records.exclusion_blocker()
        if exclusion is not None:
            raise Refused(exclusion)
        isolation = self.platform.isolation()
        if isolation is None or not isolation.get("passed") or (
            self.clock() - dt.datetime.fromisoformat(str(isolation["checkedAt"]))
            > ISOLATION_FRESHNESS
        ):
            raise Refused("isolation-not-fresh")
        if self.platform.disk_free() < DISK_FLOOR:
            raise Refused("internal-disk-low")
        memory = self.platform.memory_available()
        rate = self.platform.request_rate()
        if memory is None or memory < MEMORY_FLOOR:
            raise Refused("performance-phase-memory", requestRate=rate)
        if rate >= REQUEST_RATE_CEILING:
            raise Refused("performance-phase-load", requestRate=rate)
        verification = {"verificationRunId": str(uuid.uuid4()), "releaseTag": tag,
                        "commit": found["sha"],
                        "checkRuns": [[run["name"], run.get("id")] for run in runs],
                        "conclusion": "success", "passed": False,
                        "recordedAt": self.clock().isoformat()}
        # The VerificationRun begins here from GitHub's check runs; step 12 completes it.
        self._evidence(VERIFICATION_RUN.format(verification["verificationRunId"]), verification)
        return {"commit": found["sha"], "requestRate": rate, "verification": verification}

    def _evidence(self, name: str, value: dict) -> Path:
        """The release command's evidence (your decision of 2026-10-24): root-owned
        `control/releases/`, each file 0644 so `production_wiring.verification_reader` can
        read it; nothing it writes lands in `profile/`."""
        folder = self.paths.control / "releases"
        folder.mkdir(mode=0o755, parents=True, exist_ok=True)
        path = folder / name
        _write_public(path, json.dumps(value, sort_keys=True).encode(),
                      owner_uid=self.owner_uid)
        return path

    def _complete_verification(self, verification: dict, performance: dict, *,
                               v2_started: bool = True) -> dict:
        """Step 12 (cicd-pipeline § 5.1): the VerificationRun completed, `passed` only when
        the complete verification (preflight's check runs) and step 3's performance phase
        both passed, then the cutover moved (BR10.5). `v2_started` says whether this
        command started v2's roles itself (an install's step "start"; `verify` does not)."""
        completed = {**verification, "passed": verification.get("conclusion") == "success"
                     and bool(performance.get("passed")),
                     "performance": {"passed": bool(performance.get("passed"))},
                     "completedAt": self.clock().isoformat()}
        self._evidence(VERIFICATION_RUN.format(completed["verificationRunId"]), completed)
        return {"verificationRunId": completed["verificationRunId"],
                "passed": completed["passed"],
                "cutover": self._move_cutover(completed, v2_started=v2_started)}

    def _move_cutover(self, verification: dict, *, v2_started: bool = True) -> dict | None:
        """While a CutoverRecord exists before the switch: `new_release`, then
        `verification_passed` on a passed run, and the soak started or restarted.

        From rolled-back, v2 stayed stopped after the rollback, so its three roles start,
        with the readiness wait, before the soak starts (your decision of 2026-10-25,
        "Follow the design"), unless this command already started them; a start that
        fails, or a v2 not ready within the wait, starts no soak, and `cutover check`
        starts it later. A release installed while v2 was kept stopped has not run its
        probe journey: its verification is recorded on the CutoverRecord only once the
        probe passed (review findings, Major, R10 and R13), so an install made while v2
        is kept stopped records none (`release-not-probed`) and the only way to a
        verification is `verify`, once a dry run is accepted, which starts v2 and runs
        the probe. A release that fails it is switched back and the record names the tag
        the links point to, whatever the switch back did. As defence in depth, nothing is
        recorded for a tag the links do not point to (`release-not-linked`)."""
        from backend.modules.operations.cutover import Cutover
        from backend.modules.operations.errors import OperationsError

        machine = Cutover(self.platform.ledger, self.platform.policy, clock=self.clock)
        record = machine.current()
        if record is None or record["state"] not in (
                "preparing", "rehearsing", "ready-to-switch", "rolled-back"):
            return None
        tag = verification["releaseTag"]
        moved: dict = {"state": record["state"]}
        try:
            machine.new_release(tag)
            if verification["passed"]:
                self._verified(machine, verification, v2_started, moved)
        except OperationsError as error:
            moved["reason"] = (error.current or {}).get("reasonKey") or error.code
        except Refused as refused:
            # v2's start failed: no soak; the verification stays as it was.
            moved["reason"] = refused.reason
        moved["state"] = machine.require()["state"]
        return moved

    def _verified(self, machine, verification: dict, v2_started: bool, moved: dict) -> None:
        """A passed run recorded on the CutoverRecord once nothing holds it back, then the
        soak started or restarted (`_move_cutover`)."""
        from backend.modules.operations.release_records import recover_blocker

        tag = verification["releaseTag"]
        if self._linked_tag() != tag:
            moved["reason"] = "release-not-linked"
            return
        recover = recover_blocker(self.platform.ledger)
        if recover is not None:
            # A release record waits for `recover` (a switch back whose stops failed
            # leaves the failed release's processes running): no v2 start, no
            # verification and no soak until it ran (review finding, Major, R15).
            moved["reason"] = recover
            return
        blocked = self._soak_gate(machine.require(), tag, v2_started, moved)
        if blocked is not None:
            moved["reason"] = blocked
            return
        machine.verification_passed(verification["verificationRunId"], tag)
        record = machine.require()
        if record["state"] in ("preparing", "rolled-back") and "acceptedDryRunId" in record:
            if moved.get("ready") is False:
                # No soak on a v2 that did not become ready; `cutover check` starts it
                # once v2 is ready.
                moved["reason"] = "v2-not-ready"
            else:
                self._soak_owns_starts()
                machine.start_soak()
                moved["soak"] = "started"
        elif record["state"] == "rehearsing" and "soakStartedAt" not in record:
            self._soak_owns_starts()
            machine.restart_soak()
            moved["soak"] = "restarted"

    def _soak_owns_starts(self) -> None:
        """Right before the soak starts or restarts on the roles this `verify` started:
        from here they are the soak's, so an interruption that lands once the soak's
        start committed (or just before it) never stops them again (`_undo_starts`;
        review finding, Minor, R18). An interruption in between leaves v2 running with
        no soak, and `verify` run again starts the soak on it."""
        self._started = []

    def _soak_gate(self, record: dict, tag: str, v2_started: bool, moved: dict) -> str | None:
        """Before the verification is recorded: v2 started (unless this command started
        it) and waited for, only where `verify` may start it, and a linked release still
        waiting for its probe journey runs it (your decision of 2026-10-26, "Probe it
        whenever it's linked").

        `verify` starts v2's three roles only (your decision of 2026-10-26, "Only for a
        pending probe"): to probe the linked release when it is waiting for its probe; to
        start the soak on the linked release after a failed probe's switch back left v2
        stopped on it, which that switch back marked on its record (`v2Stopped`,
        `ReleaseRecords.stopped_on`); and from rolled-back with an accepted dry run, as the
        soak's start, which starts v2 after a cutover rollback (your decision of
        2026-10-25, "Follow the design"; `cutover check` starts it there too). In any
        other state nothing is started: a v2 that runs gets its soak restarted below, and
        a v2 you stopped in person stays stopped, answered `v2-stopped` with the operator
        tool's `service start` offered. A start of a role that runs is done. Only while
        the record is rolled-back with no dry run accepted does v2 stay stopped whatever
        waits, and an unprobed release then waits. Answers why the verification may not
        be recorded yet (`release-not-probed` for an unprobed release that cannot be
        probed now; `v2-stopped`; `v2-not-ready`; `release-probe-failed`), or None."""
        pending = self._probe_pending(tag)
        rolled = record["state"] == "rolled-back"
        if v2_started or (rolled and "acceptedDryRunId" not in record):
            return "release-not-probed" if pending else None
        if not rolled and not pending and "soakStartedAt" in record:
            return None  # the soak runs on the linked release: nothing to start or probe
        marked = self.records.stopped_on(tag)
        if not rolled and not pending and marked is None:
            # Nothing waits for a probe and no switch back left v2 stopped on this
            # release: `verify` starts nothing here.
            if self.platform.ready():
                return None
            moved["offered"] = [SERVICE_START]
            return "v2-stopped"
        self._settle_earlier()
        # Under this run's own keys: a start after a later rollback of the same tag is its
        # own, and a failed one is run again by the next `verify` (or by `cutover check`).
        self._step("start-rehearsal-v2", lambda: self._services(tag, "start"))
        waited = self._wait_ready()
        moved["ready"] = waited is not None
        if waited is None:
            return "v2-not-ready" if pending or not rolled else None
        if pending:
            moved.update(self._probe_at_soak(tag, waited))
            if moved["probe"] == "failed":
                return "release-probe-failed"
        if marked is not None:
            # v2 runs on the kept release again: the switch back's mark is spent.
            self.records.finish(marked["releaseTag"], "switched-back", v2_stopped=False)
        return None

    def _probe_pending(self, tag: str) -> bool:
        record = self.records.get(tag) or {}
        return record.get("state") == "installed" and record.get("probePending") is True

    def _probe_at_soak(self, tag: str, waited: float) -> dict:
        """The probe journey of a release installed while v2 was kept stopped, when the
        soak starts v2 from rolled-back (your decision of 2026-10-25, "Probe it when the
        soak starts"). Passed: recorded on its install record. Failed: § 6's switch back
        to `release-previous` (`_switch_back`), which leaves v2's three roles stopped
        (your decision of 2026-10-26, "Leave v2 stopped"): each stopped through the
        service control, so its stop record cites a held receipt, and not started on the
        previous release; the install record ends `switched-back` with `probePending`
        cleared once the links point back (until then it stays `installed` and waiting,
        which blocks every soak, for `recover`). Whether or not the switch back
        completes, the CutoverRecord stays rolled-back and names the tag the links point
        to; it never held a verification for the failed release (none is recorded before
        its probe passed), so no soak starts on it even when that naming fails, and
        `docsuri-release verify <tag>` on the linked tag then starts the soak."""
        if self._step("probe", self.platform.probe):
            self.records.finish(tag, "installed", probe_pending=False)
            return {"probe": "passed"}
        moved: dict = {"probe": "failed", "v2": "stopped"}
        try:
            moved["switchedBack"] = self._switch_back(tag, self.paths.releases / tag, False,
                                                      waited, keep_stopped=True)
        except Refused as refused:
            moved["switchedBack"] = {"state": "failed", "reason": refused.reason,
                                     **refused.facts}
            # A switch back whose stops failed left a role running the failed release:
            # the answer says so, never `stopped` (review finding, Major, R20).
            moved["v2"] = refused.facts.get("v2", "stopped")
        finally:
            try:
                moved["cutoverRelease"] = self._name_cutover_release()
            except Exception as error:  # noqa: BLE001 - the record holds no verification
                moved["cutoverRelease"] = {"reason": _reason_of(error,
                                                                "cutover-release-unnamed")}
        return moved

    # --- step 2 and 3 ------------------------------------------------------------------------

    def stage(self, tag: str, commit: str) -> dict:
        return self._stager().stage(tag, commit)

    # --- steps 4 to 12 ------------------------------------------------------------------------

    def install(self, tag: str) -> dict:
        if not TAG.fullmatch(tag):
            raise Refused("tag-outside-its-form")
        with self._locked("install"):
            return self._install(tag)

    def _install(self, tag: str) -> dict:
        from backend.modules.operations.errors import OperationsError
        from backend.modules.operations.ledger_records import RecordRefused

        self._new_run()
        shown = self._step("show", lambda: self.show(tag))
        self.confirm(shown)
        # What an earlier run left unsettled is settled before this run's record begins
        # (review finding, Minor, R14): an `effect-in-progress` refusal changes nothing.
        self._settle_earlier()
        checked = self._step("preflight", lambda: self.preflight(tag, shown))
        staged = self._step("stage", lambda: self.stage(tag, checked["commit"]))
        folder = staged["folder"]
        checked["performance"] = self._step(
            "performance", lambda: self._performance(folder, checked))
        previous_record = self.records.installed()
        # A begin that may have committed counts as touched (review finding, Minor, R18):
        # an interruption inside it (in production, inside the `docsuri-ledger append`
        # subprocess) leaves the record `installing`, which `recover` ends; one that
        # found nothing answers `nothing-to-recover`.
        self.touched = True
        try:
            self.records.begin(tag, checked["commit"],
                               previous_tag=previous_record["releaseTag"]
                               if previous_record else None)
        except OperationsError as error:
            raise Refused((error.current or {}).get("reasonKey") or error.code) from None
        except RecordRefused:
            raise Refused("release-record-refused") from None
        try:
            return self._production_steps(tag, folder, staged, checked)
        except BaseException as error:
            # Whatever stopped the run (an unexpected failure, Ctrl-C, a closed terminal),
            # the record never stays `installing`: the live exclusion is released.
            self._end_installing(tag, "release-interrupted" if not isinstance(
                error, Exception) else "release-step-failed")
            if isinstance(error, Refused) or not isinstance(error, Exception):
                raise
            raise Refused("release-step-failed", changed=True,
                          cause=_reason_of(error, type(error).__name__)) from error
        finally:
            self._clear_marker()

    def _end_installing(self, tag: str, reason: str) -> None:
        """The record ended `failed` if it is still `installing`, best effort: the
        `recover` word ends it when even this cannot."""
        try:
            current = self.records.get(tag)
            if current is not None and current["state"] == "installing":
                self.records.finish(tag, "failed", reason=reason)
        except Exception:  # noqa: BLE001 - the run's own failure is the one reported
            pass

    def _performance(self, folder: Path, checked: dict) -> dict:
        """Step 3: the performance phase from the staged release, as your login account
        (`ReleasePlatform.performance`, cicd-pipeline § 5.2)."""
        result = self.platform.performance(folder, checked["commit"])
        if not result.get("passed"):
            raise Refused("performance-target-breached", requestRate=checked["requestRate"])
        return result

    def _v2_stays_stopped(self, *, through_soak: bool = False) -> bool:
        """After a rollback (your decision of 2026-10-25, "Keep v2 stopped"): while the
        CutoverRecord is rolled-back with no dry run accepted since the rollback (the
        rollback's serving step cleared the earlier one), v2's three roles stay stopped
        through an install; they start with the soak.

        `through_soak` is a release rollback's reading (the review's fix of 2026-10-26):
        v2 stays stopped while the record is rolled-back, an accepted dry run or not,
        since only the soak's start starts v2 after a cutover rollback, and the soak's
        start moves the record to rehearsing (a `soakStartedAt` still on a rolled-back
        record is the soak before the switch)."""
        from backend.modules.operations.cutover import Cutover

        record = Cutover(self.platform.ledger, self.platform.policy, clock=self.clock).current()
        if record is None or record["state"] != "rolled-back":
            return False
        return through_soak or "acceptedDryRunId" not in record

    def _backup(self, tag: str) -> dict:
        """Step 6, the backup after writes stop, keyed by this run (its set is this run's
        own). However it fails (a failed set, an integrity not passed, an incomplete
        receipt, a refusal, an outcome still unknown), it answers a set that did not pass,
        with the failure's fixed reason key, so the install's way out runs.

        Its bound operation (`backup_plan`) is kept in the journal before the set is
        taken, and the entry stays pending after any failure, since a refusal can come
        after the receipt was bound: the next run settles it by that receipt
        (`_settle_backup`), and an interrupted run leaves it pending too. Without a bound
        operation (a platform that names none) only an unsettled outcome stays pending."""
        key = self._run_key(tag, "backup")
        entry = {"key": key, "kind": "backup", "tag": tag, "state": "pending"}
        if self.platform.backup_plan is not None:
            entry["effect"] = self.platform.backup_plan(tag, key)
        self._journal_put(entry)
        try:
            result = self.platform.backup(tag, key)
        except Exception as error:  # noqa: BLE001 - every failure is the backup's failure
            reason = _reason_of(error, "backup-failed")
            if "effect" not in entry and reason not in UNSETTLED:
                self._journal_put({**entry, "state": "settled"})
            return {"integrity": "failed", "reason": reason}
        self._journal_put({**entry, "state": "settled"})
        return result

    def _resume(self, tag: str, live: bool, kept_stopped: bool) -> str | None:
        """A way out before the swap: each role this run stopped started again (unless v2
        is kept stopped after a rollback), and the address routed back if this run routed
        it to maintenance. Answers the first failure's reason key, or None."""
        failure = None
        if not kept_stopped and self._stopped:
            try:
                self._services(tag, "start", list(self._stopped))
            except Refused as refused:
                failure = refused.reason
        if live and self._routed_maintenance:
            try:
                self._route(tag, "v2-host")
            except Refused as refused:
                failure = failure or refused.reason
        return failure

    def _before_swap(self, tag: str, folder: Path, staged: dict, live: bool) -> dict:
        if live:
            self._step("maintenance", lambda: self._route(tag, "maintenance"))
        self._step("stop", lambda: self._services(tag, "stop"))
        backup = self._step("backup", lambda: self._backup(tag))
        if backup.get("integrity") != "passed":
            raise Refused("pre-release-backup-failed", changed=True,
                          cause=backup.get("reason") or "integrity-not-passed")
        if staged["arrangementChange"]:
            self._step("arrangement", lambda: self._arrangement(folder))
        migrated = self._step("migrate", lambda: self.platform.migrate(folder))
        if migrated.get("failed"):
            raise Refused("migration-failed", changed=True, failed=migrated["failed"])
        self._step("swap", lambda: self.swap(folder))
        return backup

    def _production_steps(self, tag: str, folder: Path, staged: dict, checked: dict) -> dict:
        live = self.platform.mode() == "live"
        stopped = self._v2_stays_stopped()
        # The ways out read it as a release rollback does (review finding, Minor, R13):
        # while the CutoverRecord is rolled-back, an accepted dry run or not, only the
        # soak's start starts v2, so a failure before or after the swap leaves it stopped.
        kept = self._v2_stays_stopped(through_soak=True)
        try:
            backup = self._before_swap(tag, folder, staged, live)
        except Exception as error:
            # Before the swap: v2 back as it was, then the record ends `failed`; one whose
            # resume did not complete is left for `recover` (`resume-failed`).
            try:
                resumed = self._resume(tag, live, kept)
            except Exception:  # noqa: BLE001 - the record still ends, for `recover`
                resumed = "resume-failed"
            refused = error if isinstance(error, Refused) else None
            self._end_installing(tag, "resume-failed" if resumed else (
                _key(refused.reason) if refused else "release-step-failed"))
            extra = {"resumeFailed": resumed} if resumed else {}
            if refused is not None:
                raise Refused(refused.reason, changed=refused.changed, **refused.facts,
                              **extra) from None
            raise Refused("release-step-failed", changed=True,
                          cause=_reason_of(error, type(error).__name__), **extra) from error
        if stopped:
            # Installed while v2 is kept stopped, the release has not run its probe
            # journey: it is probed when the soak starts (your decision of 2026-10-25).
            return self._installed(tag, backup, staged, checked, stopped=True)
        try:
            self._step("start", lambda: self._services(tag, "start"))
            waited = self._wait_ready()
            probed = waited is not None and bool(self._step("probe", self.platform.probe))
        except Exception as error:
            # After the swap every failure is § 6's switch back.
            switched = self._switch_back(tag, folder, live, None,
                                         cause=_reason_of(error, "release-start-failed"),
                                         keep_stopped=kept)
            return {**switched, "cause": _reason_of(error, "release-start-failed")}
        if not probed:
            return self._switch_back(tag, folder, live, waited, keep_stopped=kept)
        route_failed = self._route_back(tag) if live else None
        return self._installed(tag, backup, staged, checked, stopped=False,
                               route_failed=route_failed)

    def _route_back(self, tag: str) -> str | None:
        """Row 11: the address back to v2, tried again once under a key of its own. A
        route that still fails keeps the release installed (v2 runs on it, ready and
        probed) and answers its reason: `recover` routes the address."""
        reason = None
        for _ in range(ROUTE_BACK_ATTEMPTS):
            try:
                self._step("route-back", lambda: self._route(tag, "v2-host"))
                return None
            except Refused as refused:
                reason = refused.reason
        return reason

    def _installed(self, tag: str, backup: dict, staged: dict, checked: dict, *,
                   stopped: bool, route_failed: str | None = None) -> dict:
        self.records.finish(tag, "installed", backup_id=backup.get("backupId"),
                            arrangement_version=staged["arrangementVersion"],
                            steps=self._step_times(), verification=checked["verification"],
                            probe_pending=True if stopped else None,
                            reason="route-back-failed" if route_failed else None)
        # What earlier runs left is in a known state now: their recoverable reasons are
        # cleared and an earlier unprobed release, no longer linked, is superseded
        # (review findings, Minor, R13 and R14).
        self.records.settle_others(tag)
        removed = self._prune()
        verification = self._complete_verification(checked["verification"],
                                                   checked["performance"],
                                                   v2_started=not stopped)
        result = {"state": "installed", "tag": tag, "removed": removed,
                  "steps": self._step_times(), "verification": verification}
        if route_failed:
            result.update(routeBack="failed", reason=route_failed,
                          offered=["docsuri-release recover"])
        return {**result, "v2": "stopped"} if stopped else result

    def verify(self, tag: str) -> dict:
        """`docsuri-release verify` with `{"tag"}` on standard input, for the installed tag
        only: steps 0, 1 and 3 on the installed release (the one the installer staged),
        recording the same evidence and moving the cutover as step 12 does."""
        if not TAG.fullmatch(tag):
            raise Refused("tag-outside-its-form")
        with self._locked("verify"):
            return self._verify(tag)

    def _verify(self, tag: str) -> dict:
        installed = self.records.installed()
        # The release the installer staged has no install record yet: its identity file,
        # in the folder `release` points to, names it.
        current = installed["releaseTag"] if installed else (
            linked_identity(self.paths) or {}).get("tag")
        if current != tag:
            raise Refused("verify-installed-tag-only")
        self._new_run()
        self.way_out = ["docsuri-release verify"]
        folder = self.paths.releases / tag
        if not _points_to(self.paths.release, folder):
            raise Refused("verify-installed-tag-only")
        shown = self._step("show", lambda: self.show(tag))
        self.confirm(shown)
        checked = self._step("preflight", lambda: self.preflight(tag, shown, running=True))
        performance = self._step("performance", lambda: self._performance(folder, checked))
        try:
            verification = self._complete_verification(checked["verification"], performance,
                                                       v2_started=False)
        except BaseException as error:
            if not isinstance(error, Exception):
                self._undo_starts(tag)
            raise
        return {"state": "verified", "tag": tag, "verification": verification,
                "steps": self._step_times()}

    def _undo_starts(self, tag: str) -> None:
        """An interrupted `verify` (Ctrl-C, a closed terminal, SIGTERM; review finding,
        Minor, R14) during the soak gate's readiness wait or its probe: the roles it
        started from unloaded are stopped again, best effort, so v2 is as the verify found
        it and the record still waits for its probe. A start the soak has taken over is
        never undone (`_soak_owns_starts`). Running `verify` again completes it;
        `recover` has nothing to do for it."""
        if not self._started:
            return
        try:
            self._services(tag, "stop", list(self._started))
        except Exception:  # noqa: BLE001 - the interruption is what the command answers
            pass

    def _arrangement(self, folder: Path) -> dict:
        arrangement_manifest.begin_change(self.paths, "release-install", clock=self.clock,
                                          owner_uid=self.owner_uid)
        self.marker_written = True
        result = self.platform.run_installer(folder)
        if result.get("failed"):
            raise Refused("arrangement-apply-failed", changed=True, phase=result["failed"])
        return result

    def _clear_marker(self) -> None:
        """Every way out: the marker goes, and the manifest records the arrangement as
        it stands (the installer's runner wrote it after its last change)."""
        if self.marker_written:
            arrangement_manifest.end_change(self.paths)
            self.marker_written = False

    def _wait_ready(self) -> float | None:
        started = self.clock()
        while True:
            if self.platform.ready():
                return (self.clock() - started).total_seconds()
            if self.clock() - started >= READY_BOUND:
                return None
            self.platform.sleep(READY_POLL_SECONDS)

    def _switch_back(self, tag: str, folder: Path, live: bool, waited: float | None, *,
                     cause: str | None = None, keep_stopped: bool = False) -> dict:
        """§ 6: stop v2, point `release` back at `release-previous`, start and wait, then
        route back; the failed folder is kept for diagnosis until the next install. Each
        step runs whatever the one before it did, and the record always ends:
        `switched-back` once the links point back (`failed` when they could not, from
        `installing`), with `switch-back-failed` and `Refused("switch-back-failed")` when
        any step did not complete, which `recover` completes.

        `keep_stopped` is a failed probe at the soak's start (your decision of
        2026-10-26, "Leave v2 stopped"): v2's three roles stay stopped after the relink
        (no start, no readiness wait), the record's `probePending` is cleared once the
        links point back, and the record is marked as having left v2 stopped on the kept
        release (`v2Stopped`, `keptTag`), so `verify` on that tag starts v2 for the soak
        (your decision of 2026-10-26, "Only for a pending probe"). A relink that did not
        happen leaves that record `installed` and waiting (its links still at the failed
        release), so no soak can start on it, and `recover` completes the switch back
        (review finding, Major, R13).

        The links never point back at a kept release whose record is closed
        (rolled-back, failed or switched-back; your decision of 2026-10-26, "Stay put,
        v2 stopped"): then nothing is relinked and nothing is started, v2 stays stopped
        on the failed release, the record ends with `recover-required` (`failed` from
        `installing`; `installed` and waiting from a verify), and `recover` answers what
        remains. What the stops did is kept (review finding, Major, R20): a stop that
        failed is the record's (`switchBackStep`) and the answer's `step`, by the
        stop's own reason (`service.control-failed`), and the answer says `v2: running`,
        since a role still runs the failed release; `recover` then stops v2's three
        roles before it answers `recover-required`.

        A kept release relinked whose probe a later install superseded waits for its
        probe again at once (`_pending_again`, as a rollback's relink does; review
        finding, Major, R21), so the next `verify` probes it before any soak.

        The switch back's own readiness wait counts (review finding, Major, R13): the
        previous release not ready within 10 minutes is a failure
        (`v2-not-ready-after-switch-back`), its wait is recorded
        (`switchBackWaitSeconds`), and in live mode the public address is routed to v2
        only once the links point back and v2 is ready; otherwise the maintenance notice
        stays and `recover` is offered."""
        started = self.clock()
        failures: list[str] = []
        # Every step catches any failure, not only a refusal (review finding, Minor, R13):
        # a ledger, store or readiness error inside the switch back still ends the record
        # with `switch-back-failed`, which `recover` completes.
        try:
            self._services(tag, "stop")
            stopped = True
        except Exception as error:  # noqa: BLE001 - the switch back goes on, for `recover`
            failures.append(_reason_of(error, "switch-back-stop-failed"))
            # A role still runs the failed release (the first failing stop ends the
            # loop): nothing is started, since a start of a role already running does
            # nothing and readiness would be the failed release's, and the address stays
            # on the maintenance notice (review finding, Major, R15). `recover` stops
            # every role again and completes the switch back.
            stopped = False
        relinked, kept = self._relink_back(folder, failures)
        closed = "kept-release-closed" in failures
        switch_wait, ready = None, False
        if not keep_stopped and stopped and not closed:
            try:
                self._services(tag, "start")
                if relinked:
                    waited_back = self._wait_ready()
                    ready = waited_back is not None
                    switch_wait = int(READY_BOUND.total_seconds() if waited_back is None
                                      else waited_back)
                    if not ready:
                        failures.append("v2-not-ready-after-switch-back")
            except Exception as error:  # noqa: BLE001 - recorded, for `recover`
                failures.append(_reason_of(error, "switch-back-start-failed"))
        # The public address goes back to v2 only once every step completed: the stops,
        # the relink, the start and readiness.
        if live and ready and stopped and relinked and not failures:
            try:
                self._route(tag, "v2-host")
            except Exception as error:  # noqa: BLE001 - recorded, for `recover`
                failures.append(_reason_of(error, "switch-back-route-failed"))
        seconds = (self.clock() - started).total_seconds()
        current = self.records.get(tag) or {}
        if relinked:
            state = "switched-back"
        else:
            state = "failed" if current.get("state") == "installing" else current.get(
                "state", "failed")
        if closed:
            reason = "recover-required"
        else:
            reason = "switch-back-failed" if failures else (_key(cause) if cause else None)
        left_stopped = keep_stopped and relinked and stopped
        self.records.finish(tag, state, reason=reason, ready_wait_seconds=int(
            READY_BOUND.total_seconds() if waited is None else waited),
            # `probePending` stays until the stops succeeded too: until then the failed
            # release may still run, and the record blocks every soak (review finding,
            # Major, R15).
            clear_probe=left_stopped,
            switch_back_wait_seconds=switch_wait,
            v2_stopped=True if left_stopped else None,
            kept_tag=_folder_tag(kept) if left_stopped and kept is not None else None,
            # The first step that did not complete, kept on the record beside the reason
            # (review finding, Major, R20): a stop that failed comes before the closed
            # kept release.
            step=_key(failures[0]) if failures else None)
        if closed:
            # v2 is stopped only when every stop completed; otherwise a role still runs
            # the failed release, and `recover` stops it (review finding, Major, R20).
            raise Refused("recover-required", changed=True, step=_key(failures[0]),
                          keptRelease=_folder_tag(kept),
                          v2="stopped" if stopped else "running",
                          offered=RECOVER_REMAINING if stopped else RECOVER_STOPS)
        if failures:
            raise Refused("switch-back-failed", changed=True, step=_key(failures[0]),
                          offered=["docsuri-release recover"],
                          **({} if stopped else {"v2": "running"}))
        result = {"state": "switched-back", "tag": tag, "switchBackSeconds": seconds}
        return {**result, "v2": "stopped"} if keep_stopped else result

    def _kept_state(self, target: Path) -> str | None:
        """The state of the kept folder's release record, by the tag its identity names;
        None without an identity or a record."""
        kept = (folder_identity(target) or {}).get("tag")
        record = self.records.get(kept) if kept else None
        return None if record is None else record["state"]

    def _relink_back(self, folder: Path, failures: list[str]) -> tuple[bool, Path | None]:
        """`release` pointed back at the folder `release-previous` points to, answering
        whether it was and that folder; a missing or same kept folder, a kept release
        whose record is closed (`kept-release-closed`: rolled-back, failed or
        switched-back, never pointed at; your decision of 2026-10-26, "Stay put, v2
        stopped"), or a relink that fails, is named in `failures`.

        Linked, a kept release whose probe a later install superseded waits for its probe
        again at once (`_pending_again`, as a rollback's relink does; review finding,
        Major, R21): the following `verify` then probes it before it spends a switch
        back's mark or starts any soak. A mark that could not be written is a failure of
        the switch back (`probe-pending-failed`), which `recover` completes
        (`_pending_again_linked`)."""
        from backend.modules.operations.release_records import CLOSED

        previous = self.paths.release_previous
        try:
            target = Path(os.readlink(previous)) if previous.is_symlink() else None
            if target is None or not target.is_dir() or target.resolve() == folder.resolve():
                failures.append("no-kept-release")
                return False, None
            if self._kept_state(target) in CLOSED:
                failures.append("kept-release-closed")
                return False, target
            _relink(self.paths.release, target)
        except OSError:
            failures.append("relink-failed")
            return False, None
        try:
            self._pending_again(target)
        except Exception as error:  # noqa: BLE001 - recorded, for `recover`
            failures.append(_reason_of(error, "probe-pending-failed"))
        return True, target

    def swap(self, folder: Path) -> None:
        """`release-previous` at what `release` points to, then `release` at the new
        folder; each a new link renamed over the old one. Never both at one folder."""
        current = self._current()
        if current is not None and current.resolve() == folder.resolve():
            raise Refused("release-already-linked", changed=True)
        if current is not None:
            _relink(self.paths.release_previous, current)
        _relink(self.paths.release, folder)

    def _prune(self) -> list[str]:
        """After step 12, only the two folders the links point to remain."""
        kept = {path.resolve() for path in (self.paths.release, self.paths.release_previous)
                if path.is_symlink()}
        removed = []
        for entry in sorted(self.paths.releases.iterdir()):
            if entry.is_dir() and not entry.is_symlink() and entry.resolve() not in kept:
                shutil.rmtree(entry)
                removed.append(entry.name)
        return removed

    def _step_times(self) -> dict[str, int]:
        return {step.name: int(step.seconds * 1000) for step in self.steps}

    # --- rollback (§ 6) ------------------------------------------------------------------------

    def rollback(self) -> dict:
        """§ 6: the links switched back to the kept release behind the maintenance notice.

        Refused while anything holds the live exclusion (a production restore, a
        cutover's switch, abort or rollback, an install or another release rollback), as
        an install is; it holds the exclusion itself while it runs (the ReleaseRecord
        `rolling-back`). It rolls back the release `release` points to (its identity),
        to the kept one `release-previous` points to: refused when that one is missing,
        the same folder, or a release that failed or was switched back. While the
        CutoverRecord is rolled-back with no dry run accepted since (your decision of
        2026-10-25, "Keep v2 stopped"), the links switch and v2's three roles stay
        stopped. The CutoverRecord then names the tag the links point to (`new_release`),
        while it is before the switch."""
        with self._locked("rollback"):
            return self._rollback()

    def _rollback_target(self) -> tuple[str, Path, Path]:
        """The linked release's tag, the kept folder and the current one, or refused: no
        kept release (`no-kept-release`), no installed record for the linked release
        (`no-installed-release`), a kept folder whose identity cannot be read
        (`kept-release-unreadable`), or a kept release whose record is closed
        (`kept-release-failed`: rolled-back, failed or switched-back; your decision of
        2026-10-26, "Stay put, v2 stopped")."""
        from backend.modules.operations.release_records import CLOSED

        previous = self.paths.release_previous
        current = self._current()
        if not previous.is_symlink() or current is None:
            raise Refused("no-kept-release")
        target = Path(os.readlink(previous))
        if not target.is_dir() or target.resolve() == current.resolve():
            raise Refused("no-kept-release")
        tag = self._linked_tag()
        installed = self.records.get(tag) if tag else None
        if installed is None or installed["state"] != "installed":
            raise Refused("no-installed-release")
        kept = (folder_identity(target) or {}).get("tag")
        if kept is None:
            raise Refused("kept-release-unreadable")
        kept_record = self.records.get(kept)
        if kept_record is not None and kept_record["state"] in CLOSED:
            raise Refused("kept-release-failed", keptRelease=kept,
                          keptState=kept_record["state"])
        return tag, target, current

    def _rollback(self) -> dict:
        from backend.modules.operations.errors import OperationsError

        exclusion = self.records.exclusion_blocker()
        if exclusion is not None:
            raise Refused(exclusion)
        tag, target, current = self._rollback_target()
        self._new_run()
        # Settled before the record begins (review finding, Minor, R14): an
        # `effect-in-progress` refusal leaves the installed record as it was.
        self._settle_earlier()
        # A begin that may have committed counts as touched (review finding, Minor, R18).
        self.touched = True
        try:
            self.records.begin_rollback(tag)
        except OperationsError as error:
            raise Refused((error.current or {}).get("reasonKey") or error.code) from None
        switched, stopped, live = False, True, False
        try:
            stopped = self._v2_stays_stopped(through_soak=True)
            live = self.platform.mode() == "live"
            if live:
                self._route(tag, "maintenance")
            self._services(tag, "stop")
            _relink(self.paths.release, target)
            switched = True
            # Linked now: a kept release whose probe a later install superseded waits for
            # its probe again at once, whatever stops the rollback after this (review
            # finding, Minor, R18), so `verify` probes it before any soak.
            self._pending_again(target)
            _relink(self.paths.release_previous, current)
            ready = None
            if not stopped:
                self._services(tag, "start")
                ready = self._wait_ready()
            if live:
                self._route(tag, "v2-host")
        except BaseException as error:
            # The exclusion is released whatever stopped the rollback: the record is
            # rolled-back once the links switched, and installed again before that, with
            # the release as it was (the roles it stopped started, the address routed
            # back). An interruption ends it the same way, for `recover` to complete.
            interrupted = not isinstance(error, Exception)
            if not switched and not interrupted:
                self._resume(tag, live, stopped)
            try:
                self.records.finish(tag, "rolled-back" if switched else "installed",
                                    reason="release-interrupted" if interrupted
                                    else "release-rollback-failed")
            except Exception:  # noqa: BLE001 - `recover` ends it when even this cannot
                pass
            if interrupted:
                raise
            if isinstance(error, Refused):
                raise Refused(error.reason, changed=True, **error.facts) from None
            raise Refused("release-rollback-failed", changed=True,
                          cause=_reason_of(error, type(error).__name__)) from error
        self.records.finish(tag, "rolled-back")
        result = {"state": "rolled-back", "tag": tag, "release": target.name,
                  "cutover": self._name_cutover_release()}
        return {**result, "v2": "stopped"} if stopped else {**result, "ready": ready is not None}

    def _pending_again(self, folder: Path) -> None:
        """A rollback to a kept release whose probe a later install superseded
        (`probeSuperseded`) makes it wait for its probe again: it is linked now, so the
        soak waits for `verify`, which probes it (your decision of 2026-10-26, "Probe it
        whenever it's linked"). It runs as soon as `release` points at the folder, and
        again where `recover` leaves the links (`_pending_again_linked`), so a rollback
        that failed or was interrupted after its relink never leaves a linked release
        treated as probed (review finding, Minor, R18)."""
        kept = (folder_identity(folder) or {}).get("tag")
        record = self.records.get(kept) if kept else None
        if record is not None and record["state"] == "installed" and record.get(
                "probeSuperseded"):
            self.records.finish(kept, "installed", probe_pending=True)

    def _pending_again_linked(self) -> None:
        """`_pending_again` for the folder `release` points to now, if any."""
        current = self._current()
        if current is not None:
            self._pending_again(current)

    def _name_cutover_release(self) -> dict | None:
        """After a rollback the CutoverRecord names the tag the links now point to
        (`new_release`), while it is before the switch; otherwise nothing moves."""
        from backend.modules.operations.cutover import Cutover
        from backend.modules.operations.errors import OperationsError

        tag = self._linked_tag()
        machine = Cutover(self.platform.ledger, self.platform.policy, clock=self.clock)
        record = machine.current()
        if record is None or not tag or not TAG.fullmatch(tag) or record["state"] not in (
                "preparing", "rehearsing", "ready-to-switch", "rolled-back"):
            return None
        try:
            moved = machine.new_release(tag)
        except OperationsError as error:
            return {"reason": (error.current or {}).get("reasonKey") or error.code}
        return {"state": moved["state"], "releaseTag": moved["releaseTag"]}

    # --- recover (the review's findings of 2026-10-26) ------------------------------------------

    def recover(self) -> dict:
        """`docsuri-release recover`, in person: what an interrupted or incomplete release
        run left, put in a known state. Refused while another release command runs (the
        run lock) and while a production restore or a cutover's switch, abort or rollback
        holds the live exclusion; `nothing-to-recover` when no record needs it."""
        with self._locked("recover"):
            return self._recover()

    def _recoverable(self) -> dict | None:
        from backend.modules.operations.release_records import HOLDING, KIND

        records = self.platform.ledger.records(KIND)
        holding = [record for record in records if record["state"] in HOLDING]
        if holding:
            return holding[0]  # the run lock is ours: whatever ran it has stopped
        linked = self._linked_tag()
        # A run that ended `failed` or `switched-back` with the links still at its release
        # (a failure that escaped the switch back's steps, review finding, Minor, R13)
        # needs `recover` whatever its reason.
        found = [record for record in records if record.get("reasonKey") in RECOVERABLE or (
            record["state"] == "installed" and record.get("probePending") is True
            and record["releaseTag"] != linked) or (
            record["state"] in ("failed", "switched-back") and _points_to(
                self.paths.release, self.paths.releases / record["releaseTag"]))]
        return max(found, key=lambda record: record["updatedAt"], default=None)

    def _recover(self) -> dict:
        from backend.modules.operations.release_records import release_blocker

        self._new_run()
        record = self._recoverable()
        if record is None:
            raise Refused("nothing-to-recover")
        exclusion = self.records.exclusion_blocker()
        if exclusion is not None and exclusion != release_blocker(self.platform.ledger):
            raise Refused(exclusion)
        tag, state = record["releaseTag"], record["state"]
        folder = self.paths.releases / tag
        linked_here = _points_to(self.paths.release, folder)
        relinks = state in ("installing", "failed", "switched-back") or (
            state == "installed" and record.get("probePending") is True)
        if linked_here and relinks:
            # Before the links change: a kept release that is closed is never pointed
            # at (your decision of 2026-10-26, "Stay put, v2 stopped"). The links stay,
            # v2's three roles are stopped (a role may still run the release that
            # failed; review finding, Major, R20), and the answer is what remains.
            self._stay_put(folder, tag)
        self._settle_earlier()
        self.touched = True
        # As a release rollback reads it: while the CutoverRecord is rolled-back, only the
        # soak's start starts v2 (a failed probe at the soak's start leaves it stopped).
        stopped = self._v2_stays_stopped(through_soak=True)
        live = self.platform.mode() == "live"
        ending = state
        if state in ("installing", "failed"):
            # A run that ended (or was killed) with the links at its new release: they
            # point back at the kept release, as § 6's switch back leaves them.
            ending = "failed"
            if linked_here:
                self._relink_previous(folder)
                ending = "switched-back" if state == "installing" else "failed"
        elif state == "switched-back" and linked_here:
            # A switch back that ended before its relink (a failure that escaped its
            # steps): the links point back now.
            self._relink_previous(folder)
        elif state == "rolling-back":
            ending = "installed" if linked_here else "rolled-back"
        elif state == "installed" and record.get("probePending") is True:
            # A release that failed its probe at the soak's start and whose switch back
            # did not relink (review finding, Major, R13): the links point back now.
            # With no kept release to point back to, `_stay_put` answered above.
            if linked_here:
                self._relink_previous(folder)
            ending = "switched-back"
        # v2 in a known state: running on the linked release (stopped and started again),
        # or stopped while it is kept stopped after a rollback; the address back to v2,
        # only once v2 is ready (otherwise the notice stays, and `recover` runs again).
        self._step("stop", lambda: self._services(tag, "stop"))
        ready = None
        if not stopped:
            self._step("start", lambda: self._services(tag, "start"))
            ready = self._wait_ready()
        held = live and ready is None
        if live and not held:
            self._step("route-back", lambda: self._route(tag, "v2-host"))
        switched = ending == "switched-back"
        self.records.finish(tag, ending, reason="route-back-failed" if held else None,
                            clear_probe=switched,
                            # Left stopped on the kept release after a cutover rollback:
                            # `verify` on the linked tag starts v2 for the soak.
                            v2_stopped=(True if stopped else False) if switched else None,
                            kept_tag=self._linked_tag() if switched and stopped else None)
        # Wherever the links ended, a linked release whose probe was superseded waits for
        # its probe again (review finding, Minor, R18).
        self._pending_again_linked()
        result = {"state": "recovered", "tag": tag, "record": ending,
                  "release": self._linked_tag(), "cutover": self._name_cutover_release()}
        if held:
            result.update(routeBack="held", reason="v2-not-ready",
                          offered=["docsuri-release recover"])
        return {**result, "v2": "stopped"} if stopped else {**result, "ready": ready is not None}

    def _stay_put(self, folder: Path, tag: str) -> None:
        """Refused (`recover-required`) when the kept release `release-previous` points to
        is closed (your decision of 2026-10-26, "Stay put, v2 stopped"): `recover` then
        moves no link and keeps v2 stopped on `tag`, and answers the one way out, a new
        tag's install (your decision of 2026-10-27, "Drop that remedy"; `RECOVER_REMAINING`).
        Keeping v2 stopped is its work (review finding, Major, R20): a switch back whose
        stops failed, or an install interrupted after its start, left a role running the
        release that failed, so v2's three roles are stopped here, each through the
        service control under this run's keys, before the answer; a stop of a role
        already stopped is done. A stop that fails is answered with `v2: running` and
        its step, and `recover` run again stops it. `changed` is whether a role was
        running. A missing kept release is answered where it is found
        (`no-kept-release`).

        The record is left as it is, except one still `installing` (an install killed
        outright after its swap and start; review finding, Major, R24): that record
        holds the live exclusion, which would refuse the one way out itself
        (`release-install-active` at the new tag's preflight and `begin`), so it ends
        `failed` with `recover-required` here, as `_switch_back` ends it from
        `installing`, keeping the first step that did not complete (a stop that failed,
        else the closed kept release) as its `switchBackStep`.

        The same answer when there is no kept release at all (the re-review's Minor of
        2026-10-27): after a switch back both links name the kept release until the next
        install, so when that release then fails its own probe its switch back finds
        nothing to point back to (`switch-back-failed`, step `no-kept-release`) and
        the record stays `installed`, waiting for its probe. `recover` then has no link
        to move either: it stops v2's three roles as above and answers `recover-required`
        with `step: no-kept-release` and the one way out, instead of a bare
        `no-kept-release` that changed nothing and led nowhere. The record keeps
        `switch-back-failed`, so no soak starts until the new tag's install settles it."""
        from backend.modules.operations.release_records import CLOSED

        previous = self.paths.release_previous
        target = Path(os.readlink(previous)) if previous.is_symlink() else None
        if target is None or not target.is_dir() or target.resolve() == folder.resolve():
            current = self.records.get(tag) or {}
            if current.get("state") == "installed" and current.get("probePending") is True:
                self._answer_what_remains(tag, step="no-kept-release",
                                          facts={"step": "no-kept-release"})
            return
        state = self._kept_state(target)
        if state not in CLOSED:
            return
        self._answer_what_remains(tag, step="kept-release-closed",
                                  facts={"keptRelease": _folder_tag(target),
                                         "keptState": state})

    def _answer_what_remains(self, tag: str, *, step: str, facts: dict) -> None:
        """`_stay_put`'s stop and answer: v2's three roles stopped under this run's keys,
        a record still `installing` ended `failed` with `recover-required` (its
        `switchBackStep` the first step that did not complete: a stop that failed, the
        step it already holds, else `step`), then `Refused("recover-required")` with
        `facts`, `v2` and what is offered; a stop that failed replaces any `step` in
        `facts` with its own reason."""
        self._settle_earlier()
        failure = None
        try:
            self._step("stop", lambda: self._services(tag, "stop"))
        except Exception as error:  # noqa: BLE001 - answered, for `recover` again
            failure = _reason_of(error, "switch-back-stop-failed")
        self.touched = bool(self._stopped) or failure is not None
        current = self.records.get(tag) or {}
        if current.get("state") == "installing":
            self.records.finish(tag, "failed", reason="recover-required",
                                step=_key(failure) if failure else (
                                    current.get("switchBackStep") or step))
            self.touched = True
        answered = {**facts, "step": _key(failure)} if failure else dict(facts)
        raise Refused("recover-required", changed=self.touched, release=tag,
                      v2="stopped" if failure is None else "running",
                      offered=RECOVER_REMAINING if failure is None else RECOVER_STOPS,
                      **answered)

    def _relink_previous(self, folder: Path) -> None:
        previous = self.paths.release_previous
        target = Path(os.readlink(previous)) if previous.is_symlink() else None
        if target is None or not target.is_dir() or target.resolve() == folder.resolve():
            raise Refused("no-kept-release")
        _relink(self.paths.release, target)


def unprobed_tag(ledger, paths: ArrangementPaths, *, clock=None) -> str | None:
    """The tag of the installed release whose install record waits for its probe journey
    (installed while v2 was kept stopped), else None: the cutover's soak start then waits
    for `docsuri-release verify`, which probes it (your decision of 2026-10-25). It fails
    closed (review finding, Major, R10): a record still waiting blocks the soak whatever
    the links point to, since only the release command's probe, or `recover`, ends it, and
    whichever installed record is the latest (review finding, Minor, R13): a `recover`
    that finished an older record never hides a pending one. A later install supersedes
    it (`ReleaseRecords.settle_others`)."""
    from backend.modules.operations.release_records import ReleaseRecords

    del paths  # the links never clear a probe that has not run
    pending = ReleaseRecords(ledger, clock=clock or _now).unprobed()
    return None if pending is None else pending["releaseTag"]


# What `recover` answers when the kept release is closed (your decision of 2026-10-26,
# "Stay put, v2 stopped"): the one way out, v2 kept stopped meanwhile. A rollback to an
# earlier release is not offered (your decision of 2026-10-27, "Drop that remedy"): after
# a completed install only the two linked folders remain under `releases/`, `rollback`
# refuses a closed kept release, and the links are this command's, never edited by hand.
RECOVER_REMAINING = ("docsuri-release install with a new tag",)
# The same, when a role still runs the release that failed (a stop failed; review
# finding, Major, R20): `recover` stops v2's three roles first, and the operator tool's
# in-person stop is the other way to stop one.
SERVICE_STOP = ("echo '{}' | /Library/DocSuri/release/.venv/bin/python -I -m "
                "docsuri_ops.u8_platform service stop <label> --production")
RECOVER_STOPS = ("docsuri-release recover", SERVICE_STOP, *RECOVER_REMAINING)


def _folder_tag(folder: Path) -> str:
    """A release folder's tag: its identity, else its name."""
    return (folder_identity(folder) or {}).get("tag") or folder.name


def run_lock_path(paths: ArrangementPaths) -> Path:
    """The release command's run lock, `control/releases/release-run.lock`: root-only
    (0600), so no other account can open it, let alone hold it."""
    return paths.control / "releases" / RUN_LOCK


def run_marker_path(paths: ArrangementPaths) -> Path:
    """The release command's run marker, `control/releases/release-run.json`: root-written,
    readable by anyone (0644), present exactly while a command runs (or left by one that
    died, until the next command removes it under the lock)."""
    return paths.control / "releases" / RUN_MARKER


@contextlib.contextmanager
def run_lock(paths: ArrangementPaths, word: str, *,
             clock: Callable[[], dt.datetime] = _now) -> Iterator[Path]:
    """The release command's run lock held for the block, with its marker written beside
    it (review findings, Major, R19–R21; your decision of 2026-10-26, "Check the release
    run lock").

    The lock is an exclusive `flock` on a root-only file (0600): `flock` needs no write
    access, so a file other accounts could open read-only is one they could hold, which
    would let any local account refuse every release command, `recover` and the cutover
    rollback included; a file they cannot open, they cannot hold. Presence is published
    through a separate marker (`run_marker_path`, 0644: `pid`, `word`, `startedAt`),
    written under the lock right after it is taken and removed in the block's `finally`,
    which readers read and never lock, so a reader can neither hold the lock nor make a
    command answer `release-run-active` for the reader's instant. Under the lock, any
    marker already there was left by a command that died (`release_run_active` refuses
    it as stale meanwhile): it is replaced. A second command is refused
    (`release-run-active`)."""
    folder = paths.control / "releases"
    folder.mkdir(mode=0o755, parents=True, exist_ok=True)
    descriptor = os.open(folder / RUN_LOCK, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        os.fchmod(descriptor, 0o600)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise Refused(RUN_ACTIVE) from None
        marker = folder / RUN_MARKER
        if marker.is_symlink() or marker.exists():
            marker.unlink()  # left by a command that died: ours replaces it
        _write_public(marker, json.dumps({"pid": os.getpid(), "word": word,
                                          "startedAt": clock().isoformat()},
                                         sort_keys=True).encode())
        try:
            yield marker
        finally:
            with contextlib.suppress(OSError):
                marker.unlink()
    finally:
        os.close(descriptor)


def _process_alive(pid: int) -> bool:
    """Whether a process with `pid` exists: `os.kill(pid, 0)`, where a refusal (EPERM)
    means a live process of another account, root's included."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def release_run_active(paths: ArrangementPaths, *,
                       alive: Callable[[int], bool] = _process_alive) -> str | None:
    """`release-run-active` while a release command runs, else None (your decision of
    2026-10-26, "Check the release run lock"). Read without a password and without
    locking anything: the command's marker (`run_marker_path`, root-written, readable by
    anyone) names its pid, and that process alive (`os.kill(pid, 0)`: it exists, or
    EPERM, a live process of another account) is the command running. No marker means
    no release command runs. A marker whose process is gone was left by a command that
    died: refused fail closed (`release-run-marker-stale`) until the next release
    command replaces it under the real lock, since what that command left is unknown. A
    marker that cannot be opened or read (a link in its place, no JSON, no pid) refuses
    (`release-run-lock-unreadable`), never admits. The bounded residual is a pid reused
    by another process before the next release command runs: then the marker reads as
    active, fail closed, until that command."""
    try:
        descriptor = os.open(run_marker_path(paths), os.O_RDONLY | os.O_NOFOLLOW)
    except FileNotFoundError:
        return None
    except OSError:
        return RUN_UNREADABLE
    try:
        with os.fdopen(descriptor, "rb") as stream:
            value = json.loads(stream.read(4096))
    except (OSError, ValueError):
        return RUN_UNREADABLE
    pid = value.get("pid") if isinstance(value, dict) else None
    if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
        return RUN_UNREADABLE
    return RUN_ACTIVE if alive(pid) else RUN_STALE


def _relink(link: Path, target: Path) -> None:
    pending = link.with_name(link.name + ".docsuri-pending")
    if pending.is_symlink() or pending.exists():
        pending.unlink()
    os.symlink(target, pending)
    os.replace(pending, link)


def _arrangement_version(folder: Path) -> int | None:
    path = folder / "ops/src/docsuri_ops/arrangement/templates/VERSION"
    try:
        value = int(path.read_text().strip())
    except (OSError, ValueError):
        return None
    return value if value >= 1 else None


def _was_loaded(receipt: dict) -> bool:
    """Whether a service control's job was loaded before it ran, from its receipt's
    `wasLoaded` fact (the fixed program's own answer). A receipt without the fact (an
    earlier driver's) counts as loaded: a stop is then started again by a way out, and a
    start is never undone by an interrupted `verify`."""
    from docsuri_ops.u8_platform.drivers import parse_facts

    try:
        facts = parse_facts(list(receipt.get("effectRefs") or []))
    except ValueError:
        return True
    return facts.get("wasLoaded") != "false"


def _key(reason: str) -> str:
    return "".join(c if c.isalnum() or c in ".-" else "-" for c in reason.lower())[:64]


_FIXED_REASON = re.compile(r"[a-z][a-z0-9.-]{0,63}")


def _reason_of(error: BaseException, default: str) -> str:
    """A failure's fixed reason key (`reason`, as `ProcedureFailed` and `Refused` carry
    it; `effect-outcome-unknown` for an outcome still unknown), or `default`: never free
    text, which may carry anything."""
    if type(error).__name__ == "OutcomeUnknown":
        return "effect-outcome-unknown"
    value = getattr(error, "reason", None)
    return value if isinstance(value, str) and _FIXED_REASON.fullmatch(value) else default


# --- each fixed program's `--self-check` (decision "The release environment") ---------------------

PROGRAM_ENTRIES = {
    "docsuri-backup-agent": "docsuri_ops.backup_agent.cli",
    "docsuri-backup-unlock": "docsuri_ops.backup_unlock",
    "docsuri-credential-release": "docsuri_ops.u8_platform.fixed",
    "docsuri-installer": "docsuri_ops.arrangement.installer",
    "docsuri-isolation-check": "docsuri_ops.isolation_check",
    "docsuri-ledger": "backend.modules.operations.ledger_cli",
    "docsuri-logrotate": "docsuri_ops.logrotate",
    "docsuri-logs": "docsuri_ops.u8_platform.fixed",
    "docsuri-migration-import": "backend.modules.operations.migration.phases",
    "docsuri-pf-load": "docsuri_ops.pf_loader",
    "docsuri-production-tool": "docsuri_ops.production_tool",
    "docsuri-profile": "docsuri_ops.u8_platform.fixed",
    "docsuri-release": "docsuri_ops.release",
    "docsuri-service-start": "docsuri_ops.u8_platform.fixed",
    "docsuri-service-stop": "docsuri_ops.u8_platform.fixed",
    "docsuri-standing": "docsuri_ops.standing.main",
    "docsuri-tunnel-route": "docsuri_ops.u8_platform.fixed",
}


def self_check(program: str, *, stdout: BinaryIO | None = None) -> int:
    """`<program> --self-check`: the program's entry module imports from the release's
    own source roots (through `docsuri-release.pth`), so a module that needs build-time
    data fails in CI, not at an install. It changes nothing."""
    import importlib

    name = Path(program).name
    stream = stdout or sys.stdout.buffer
    module = PROGRAM_ENTRIES.get(name)
    if module is None:
        stream.write(json.dumps({"ok": False, "reason": "program-unknown"}).encode() + b"\n")
        return 2
    loaded = importlib.import_module(module)
    stream.write(json.dumps({"ok": True, "program": name, "module": module,
                             "file": str(Path(loaded.__file__).resolve())}).encode() + b"\n")
    stream.flush()
    return 0


# --- the program (D6) --------------------------------------------------------------------------


@contextlib.contextmanager
def interrupts() -> Iterator[None]:
    """SIGHUP (a closed terminal or SSH session) and SIGTERM end the run as Ctrl-C does
    (`KeyboardInterrupt`), so every way out that ends the release record runs for them
    too; the earlier handlers come back afterwards."""

    def interrupt(signum, frame):
        raise KeyboardInterrupt(f"signal {signum}")

    previous = {number: signal.signal(number, interrupt)
                for number in (signal.SIGHUP, signal.SIGTERM)}
    try:
        yield
    finally:
        for number, handler in previous.items():
            signal.signal(number, handler)


def run(argv: list[str], *, stdin: BinaryIO, stdout: BinaryIO, environ,
        factory: Callable[[], ReleaseInstall]) -> int:
    """One word and its bounded JSON on standard input; exactly one JSON result on
    standard output, whatever stopped the command (D6): a refusal, an interruption or an
    unexpected failure each answer a fixed reason key, never a traceback."""

    def emit(value: dict, status: int) -> int:
        stdout.write(json.dumps(value, sort_keys=True, default=str).encode() + b"\n")
        stdout.flush()
        return status

    if any(name.startswith(("PYTHON", "DYLD_", "LD_")) for name in environ):
        return emit({"ok": False, "reason": "environment-refused"}, 2)
    if len(argv) != 1 or argv[0] not in WORDS:
        return emit({"ok": False, "reason": "word-refused"}, 2)
    raw = stdin.read(4097)
    try:
        document = json.loads(raw or b"{}")
    except ValueError:
        return emit({"ok": False, "reason": "input-not-json"}, 2)
    if len(raw) > 4096 or not isinstance(document, dict):
        return emit({"ok": False, "reason": "input-refused"}, 2)
    chosen = None
    try:
        if argv[0] in ("install", "verify"):
            if set(document) != {"tag"} or not isinstance(document["tag"], str):
                return emit({"ok": False, "reason": "input-refused"}, 2)
            chosen = factory()
            result = (chosen.install if argv[0] == "install" else chosen.verify)(document["tag"])
        else:
            if document:
                return emit({"ok": False, "reason": "input-refused"}, 2)
            chosen = factory()
            result = (chosen.rollback if argv[0] == "rollback" else chosen.recover)()
    except Refused as refused:
        return emit({"ok": False, "reason": refused.reason, "changed": refused.changed,
                     **refused.facts}, 1)
    except KeyboardInterrupt:
        # Before the run changed anything of production (no record begun, no effect run:
        # step 0's prompt, the preflight, staging), nothing needs `recover` (review
        # finding, Minor, R14).
        if chosen is None or not getattr(chosen, "touched", True):
            return emit({"ok": False, "reason": "release-interrupted", "changed": False}, 130)
        return emit({"ok": False, "reason": "release-interrupted", "changed": True,
                     "offered": list(getattr(chosen, "way_out", None)
                                     or ["docsuri-release recover"])}, 130)
    except Exception as error:  # noqa: BLE001 - one JSON result, never a traceback
        return emit({"ok": False, "reason": "release-command-failed", "changed": True,
                     "cause": _reason_of(error, type(error).__name__)}, 1)
    return emit({"ok": True, **result}, 0)


def main_fixed(argv: list[str] | None = None) -> int:
    """The installed program: production's wiring (`production_wiring.release_install`),
    with SIGHUP and SIGTERM taken as interrupts."""
    from docsuri_ops.production_wiring import release_install

    with interrupts():
        return run(sys.argv[1:] if argv is None else argv, stdin=sys.stdin.buffer,
                   stdout=sys.stdout.buffer, environ=os.environ, factory=release_install)
