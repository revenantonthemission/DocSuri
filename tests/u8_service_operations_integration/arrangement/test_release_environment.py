"""The release environment on a clean clone at a temporary path (U8 plan Step 38; decision
"The release environment", cicd-pipeline § 3 and § 5.1 step 2, C10).

Run only in `ci.yml`'s `macos-filesystem` job, or through the tool's `arrangement` phase,
as root under sudo (`DOCSURI_U8_ARRANGEMENT=1`). It runs the release command's own step 2
on clones of this checkout: `uv sync --project backend --frozen --no-build` with every
local package left out, then `docsuri-release.pth`; every entry module imports and every
fixed program's `--self-check` passes from the environment's own interpreter; a
dependency without a wheel fails; and after a swap and a switch back, code and libraries
load from the real path `release` points to.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from docsuri_ops import release
from docsuri_ops.arrangement.paths import ArrangementPaths
from docsuri_ops.arrangement.render import FIXED_PROGRAMS
from docsuri_ops.arrangement.runtimes import PYTHON_VERSION

REPOSITORY = Path(__file__).resolve().parents[3]
SECONDS = 1800


@pytest.fixture(scope="module", autouse=True)
def as_root_on_macos():
    if sys.platform != "darwin" or os.geteuid() != 0:
        pytest.fail("the arrangement tests run as root on macOS (the macos-filesystem job)")


def uv() -> Path:
    found = shutil.which("uv")
    if found is None:
        pytest.fail("uv is not installed in the macOS job")
    return Path(found)


def staged(folder: Path) -> Path:
    """The release command's step 2 on a clean clone of this checkout."""
    subprocess.run(["git", "clone", "--quiet", "--no-hardlinks", str(REPOSITORY), str(folder)],
                   check=True, timeout=SECONDS)
    environment = release.sync_environment(folder, uv=uv())
    subprocess.run([str(uv()), "python", "install", PYTHON_VERSION], env=environment,
                   check=True, timeout=SECONDS, capture_output=True)
    completed = subprocess.run(release.sync_command(uv(), folder), env=environment, cwd=folder,
                               capture_output=True, timeout=SECONDS, check=False)
    assert completed.returncode == 0, completed.stderr.decode()[-2000:]
    release.write_pth(folder)
    return folder


@pytest.fixture(scope="module")
def releases(tmp_path_factory):
    root = tmp_path_factory.mktemp("releases-root")
    paths = ArrangementPaths.under(root / "Library" / "DocSuri")
    paths.releases.mkdir(parents=True)
    first = staged(paths.releases / "v2.0.0")
    second = staged(paths.releases / "v2.0.1")
    return paths, first, second


def interpreter(folder: Path) -> str:
    return str(folder / ".venv" / "bin" / "python")


def test_the_sync_installs_wheels_only_and_leaves_the_local_packages_out(releases):
    _, first, _ = releases
    site = release.site_packages(first)
    names = {path.name.split("-")[0].lower().replace("_", "-") for path in site.iterdir()}
    for package in release.LOCAL_PACKAGES:
        assert package not in names, package
    pth = (site / release.PTH).read_text().splitlines()
    assert pth == [str(first.resolve()), *[str(first / root) for root in
                                           release.SOURCE_ROOTS[1:]]]
    assert "fastapi" in names and "psycopg" in names


def test_every_entry_module_imports_and_each_program_checks_itself(releases):
    _, first, _ = releases
    for module in release.ENTRY_MODULES:
        completed = subprocess.run([interpreter(first), "-I", "-c", f"import {module}"],
                                   capture_output=True, timeout=120, check=False)
        assert completed.returncode == 0, (module, completed.stderr.decode()[-1500:])
    for name in FIXED_PROGRAMS:
        completed = subprocess.run([interpreter(first), "-I", str(first / "ops/bin" / name),
                                    "--self-check"], capture_output=True, timeout=120,
                                   check=False)
        assert completed.returncode == 0, (name, completed.stderr.decode()[-1500:])
        result = json.loads(completed.stdout)
        assert result["ok"] is True and Path(result["file"]).is_relative_to(first.resolve())


def test_a_dependency_without_a_wheel_fails(tmp_path):
    project = tmp_path / "project"
    package = tmp_path / "source-only"
    (package / "source_only").mkdir(parents=True)
    (package / "source_only" / "__init__.py").write_text("")
    (package / "pyproject.toml").write_text(
        '[project]\nname = "source-only"\nversion = "0.1.0"\n'
        '[build-system]\nrequires = ["hatchling"]\nbuild-backend = "hatchling.build"\n')
    project.mkdir()
    (project / "pyproject.toml").write_text(
        f'[project]\nname = "probe"\nversion = "0.1.0"\nrequires-python = ">=3.13"\n'
        f'dependencies = ["source-only"]\n[tool.uv]\npackage = false\n'
        f'[tool.uv.sources]\nsource-only = {{ path = "{package}" }}\n')
    environment = {**release.sync_environment(project, uv=uv()), "UV_OFFLINE": "1"}
    locked = subprocess.run([str(uv()), "lock", "--project", str(project)], env=environment,
                            capture_output=True, timeout=SECONDS, check=False)
    assert locked.returncode == 0, locked.stderr.decode()[-1500:]
    synced = subprocess.run([str(uv()), "sync", "--project", str(project), "--frozen",
                             "--no-build"], env=environment, capture_output=True,
                            timeout=SECONDS, check=False)
    assert synced.returncode != 0
    assert b"build" in synced.stderr.lower()


def test_after_a_swap_and_a_switch_back_code_loads_from_the_linked_release(releases):
    paths, first, second = releases

    def loaded_from() -> set[Path]:
        probe = ("import json, backend, docsuri_ops, fastapi; print(json.dumps("
                 "[backend.__file__, docsuri_ops.__file__, fastapi.__file__]))")
        completed = subprocess.run([str(paths.release / ".venv" / "bin" / "python"), "-I", "-c",
                                    probe], capture_output=True, timeout=120, check=True)
        return {Path(item).resolve() for item in json.loads(completed.stdout)}

    def link(target: Path) -> None:
        pending = paths.release.with_name("release.pending")
        if pending.is_symlink():
            pending.unlink()
        os.symlink(target, pending)
        os.replace(pending, paths.release)

    link(first)
    assert all(path.is_relative_to(first.resolve()) for path in loaded_from())
    install = release.ReleaseInstall.__new__(release.ReleaseInstall)
    install.paths = paths
    install.swap(second)
    assert all(path.is_relative_to(second.resolve()) for path in loaded_from())
    assert Path(os.readlink(paths.release_previous)) == first
    link(Path(os.readlink(paths.release_previous)))  # the switch back of § 6
    assert all(path.is_relative_to(first.resolve()) for path in loaded_from())
