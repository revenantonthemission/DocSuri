"""Ruff holds U6's files to E, F, I, UP and B at 100 (U6 plan Step 61, L3-9 to L3-12).

The four invocations of the workflow step "Lint export and shared runtime changes" run here
with the pinned Ruff 0.16.8 from `backend/.venv` and `--no-cache`, each exiting 0: U6's tests
under `scripts/u6-lint.toml`; U6's five scripts under `scripts/u6-lint-scripts.toml` (Ruff's
default selection, extended); U6's backend files and the shared runtime files under their
own `pyproject.toml`; and the four U2 files U6 changes, from their folder, under
`scripts/u6-lint-accounts.toml` (cicd-pipeline §2.3). The configurations are read with
`tomllib`, the resolved rules and settings paths with `--show-settings`, and the workflow
step must hold exactly these invocations. Planted files in `tmp_path` show that the
configurations refuse what they should. Nothing is mocked and nothing is written into the
repository. No realm is needed.
"""

from __future__ import annotations

import hashlib
import json
import re
import shlex
import subprocess
import tomllib
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
RUFF = ROOT / "backend/.venv/bin/ruff"
RUFF_VERSION = "ruff 0.16.8"
WORKFLOW = ROOT / ".github/workflows/u6-approved-export.yml"
STEP = "Lint export and shared runtime changes"
SELECTED = ["E", "F", "I", "UP", "B"]
TESTS_CONFIG = "scripts/u6-lint.toml"
SCRIPTS_CONFIG = "scripts/u6-lint-scripts.toml"
ACCOUNTS_TOML = "scripts/u6-lint-accounts.toml"
ACCOUNTS_FOLDER = "backend/modules/accounts"
ACCOUNTS_CONFIG = "../../../scripts/u6-lint-accounts.toml"
FORBIDDEN_KEYS = (
    "ignore",
    "extend-ignore",
    "per-file-ignores",
    "extend-per-file-ignores",
    "fix",
    "unsafe-fixes",
)
SCRIPTS = ("scripts/verify_docsuri_u6.py", "scripts/serve_docsuri_u6.py", "scripts/u6_*.py")
SCRIPT_GLOB_FILES = [
    "scripts/u6_browser_fixtures.py",
    "scripts/u6_preservation.py",
    "scripts/u6_real_export.py",
]
# (3): U6's backend files and the shared runtime files, under their own configurations.
BACKEND = (
    "backend/modules/export",
    "backend/u6_*.py",
    "backend/key_custody.py",
    "backend/local_profile.py",
    "backend/transactions.py",
    "backend/local_browser.py",
    "backend/artifacts.py",
    "backend/local_host.py",
    "backend/u3_host.py",
    "backend/modules/personalization/guarded_service.py",
    "ops/src/docsuri_ops/local_transport.py",
)
OWN_SETTINGS = {"backend/pyproject.toml", "ops/pyproject.toml"}
# (4): the U2 files U6 changes, run from their folder.
ACCOUNTS = (
    "control_keys.py",
    "services/control_lifecycle.py",
    "local_http.py",
    "services/guarded_entry.py",
)
# What the workflow's four invocations hold: (folder, arguments after `check --no-cache`).
WORKFLOW_INVOCATIONS = [
    (".", ["--config", TESTS_CONFIG, "tests/u6_approved_export"]),
    (".", ["--config", SCRIPTS_CONFIG, *SCRIPTS]),
    (".", list(BACKEND)),
    (ACCOUNTS_FOLDER, ["--config", ACCOUNTS_CONFIG, *ACCOUNTS]),
]
CACHE_FOLDERS = (".", "scripts", "tests", "backend", "ops", ACCOUNTS_FOLDER)


def ruff(folder: str | Path, *arguments: str) -> subprocess.CompletedProcess:
    """One `ruff check --no-cache` from `folder`, read-only."""
    return subprocess.run(
        [str(RUFF), "check", "--no-cache", *arguments],
        cwd=ROOT / folder,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


def expanded(paths: list[str] | tuple[str, ...]) -> list[str]:
    """The paths with their globs expanded from the repository root, as bash does."""
    found = []
    for path in paths:
        if any(mark in path for mark in "*?["):
            matches = sorted(str(item.relative_to(ROOT)) for item in ROOT.glob(path))
            assert matches, path
            found.extend(matches)
        else:
            found.append(path)
    return found


def invocations() -> list[tuple[str, list[str]]]:
    """The four invocations, globs expanded from the folders they run in."""
    return [
        (folder, expanded(arguments) if folder == "." else arguments)
        for folder, arguments in WORKFLOW_INVOCATIONS
    ]


def enabled_rules(output: str) -> set[str]:
    """The rule codes of `linter.rules.enabled` in a `--show-settings` answer."""
    block = output.split("linter.rules.enabled = [", 1)[1].split("\n]", 1)[0]
    return set(re.findall(r"\(([A-Z]+[0-9]+)\)", block))


def show_settings(folder: str, *arguments: str) -> str:
    completed = ruff(folder, "--show-settings", *arguments)
    assert completed.returncode == 0, completed.stderr
    return completed.stdout


def settings_path(output: str) -> str:
    found = re.search(r'^Settings path: "(.+)"$', output, re.MULTILINE)
    assert found, output[:400]
    return str(Path(found.group(1)).relative_to(ROOT))


def plant(tmp_path: Path, name: str, text: str) -> Path:
    path = tmp_path / name
    path.write_text(text)
    return path


def codes(completed: subprocess.CompletedProcess) -> set[str]:
    return {finding["code"] for finding in json.loads(completed.stdout)}


def linted_files() -> dict[str, str]:
    """The SHA-256 of every file the four invocations name or hold (configurations too)."""
    found = {}
    names = [(".", [TESTS_CONFIG, SCRIPTS_CONFIG, ACCOUNTS_TOML])] + invocations()
    for folder, arguments in names:
        for word in arguments:
            if word.startswith("-") or word.startswith("../"):
                continue
            path = (ROOT / folder / word).resolve()
            items = sorted(path.rglob("*.py")) if path.is_dir() else [path]
            for item in items:
                if item.is_file():
                    found[str(item)] = hashlib.sha256(item.read_bytes()).hexdigest()
    return found


def caches() -> dict[str, tuple[int, int]]:
    """Every file of an existing `.ruff_cache` in the six folders (size, modification time)."""
    found = {}
    for folder in CACHE_FOLDERS:
        cache = ROOT / folder / ".ruff_cache"
        if cache.is_dir() and not cache.is_symlink():
            for item in sorted(cache.rglob("*")):
                facts = item.lstat()
                found[str(item.relative_to(ROOT))] = (facts.st_size, facts.st_mtime_ns)
    return found


def workflow_invocations() -> tuple[dict, str, list[tuple[str, list[str]]]]:
    """The workflow, the ruff binary the step names and each `"$ruff" check` it runs."""
    document = yaml.safe_load(WORKFLOW.read_text())
    steps = [
        step
        for job in document["jobs"].values()
        for step in job.get("steps", [])
        if step.get("name") == STEP
    ]
    assert len(steps) == 1
    lines = [line.strip() for line in steps[0]["run"].replace("\\\n", " ").splitlines()]
    commands = [line for line in lines if line and not line.startswith("#")]
    binary = [line for line in commands if line.startswith("ruff=")]
    found = []
    for line in commands:
        if '"$ruff"' not in line:
            continue
        folder = "."
        if line.startswith("(cd "):
            folder, line = line[len("(cd ") :].split(" && ", 1)
            assert line.endswith(")")
            line = line[:-1]
        words = shlex.split(line)
        assert words[:3] == ["$ruff", "check", "--no-cache"], line
        found.append((folder, words[3:]))
    assert len(binary) == 1
    return document, binary[0], found


def test_u6s_lint_configurations_hold_e_f_i_up_b_at_100_and_ignore_nothing(tmp_path):
    # The three configurations, read with tomllib.
    configurations = {
        name: tomllib.loads((ROOT / name).read_text())
        for name in (TESTS_CONFIG, SCRIPTS_CONFIG, ACCOUNTS_TOML)
    }
    for name, value in configurations.items():
        assert value["line-length"] == 100 and value["target-version"] == "py313", name
        for key in FORBIDDEN_KEYS:
            assert key not in value, (name, key)
            if key == "ignore" and name == ACCOUNTS_TOML:
                assert value["lint"][key] == [], name
            else:
                assert key not in value["lint"], (name, key)
    assert configurations[TESTS_CONFIG]["lint"]["select"] == SELECTED
    scripts = configurations[SCRIPTS_CONFIG]["lint"]
    assert scripts["extend-select"] == SELECTED and "select" not in scripts
    accounts = configurations[ACCOUNTS_TOML]
    assert accounts["extend"] == "../backend/modules/accounts/ruff.toml"
    assert accounts["lint"]["select"] == SELECTED
    for name in OWN_SETTINGS:
        ruff_table = tomllib.loads((ROOT / name).read_text())["tool"]["ruff"]
        assert ruff_table["line-length"] == 100 and ruff_table["lint"]["select"] == SELECTED
        for key in FORBIDDEN_KEYS:
            assert key not in ruff_table and key not in ruff_table["lint"], (name, key)

    # Through --show-settings: the resolved rules and the settings each path takes.
    test_file = "tests/u6_approved_export/conftest.py"
    tests_rules = enabled_rules(show_settings(".", "--config", TESTS_CONFIG, test_file))
    exact = enabled_rules(show_settings(".", "--isolated", "--select", "E,F,I,UP,B", test_file))
    assert tests_rules == exact
    script = "scripts/u6_real_export.py"
    script_rules = enabled_rules(show_settings(".", "--config", SCRIPTS_CONFIG, script))
    assert enabled_rules(show_settings(".", "--isolated", script)) <= script_rules
    assert exact <= script_rules and {"S110", "BLE001"} <= script_rules
    for path in expanded(BACKEND):
        files = sorted((ROOT / path).rglob("*.py")) if (ROOT / path).is_dir() else [ROOT / path]
        for item in files:
            output = show_settings(".", str(item.relative_to(ROOT)))
            assert settings_path(output) in OWN_SETTINGS, item

    # Planted files fail with exactly the named codes; each uses every name it imports.
    long_line = "VALUE = " + " + ".join(["1"] * 24)
    long_and_unsorted = plant(
        tmp_path,
        "planted_tests.py",
        f"import sys\nimport os\n\n{long_line}\nprint(os.sep, sys.argv, VALUE)\n",
    )
    assert len(long_and_unsorted.read_text().splitlines()[3]) == 101
    completed = ruff(
        ".", "--config", TESTS_CONFIG, "--output-format", "json", str(long_and_unsorted)
    )
    assert completed.returncode == 1 and codes(completed) == {"E501", "I001"}
    # docsuri_ops is first-party only through the file's `src` (ops/src).
    first_party = plant(
        tmp_path,
        "planted_first_party.py",
        "import pytest\nfrom docsuri_ops.local_transport import inspect_transport\n\n"
        "PAIR = (pytest, inspect_transport)\n",
    )
    completed = ruff(".", "--config", TESTS_CONFIG, "--output-format", "json", str(first_party))
    assert completed.returncode == 1 and codes(completed) == {"I001"}
    swallowed = plant(
        tmp_path,
        "planted_script.py",
        "def f():\n    try:\n        return 1\n    except Exception:\n        pass\n",
    )
    completed = ruff(".", "--config", SCRIPTS_CONFIG, "--output-format", "json", str(swallowed))
    assert completed.returncode == 1 and codes(completed) == {"S110", "BLE001"}


def test_ruff_passes_on_u6s_files_and_writes_nothing():
    version = subprocess.run(
        [str(RUFF), "--version"], capture_output=True, text=True, timeout=30, check=True
    )
    assert version.stdout.strip() == RUFF_VERSION
    assert expanded(["scripts/u6_*.py"]) == SCRIPT_GLOB_FILES
    before = {"files": linted_files(), "caches": caches()}

    for folder, arguments in invocations():
        completed = ruff(folder, *arguments)
        assert completed.returncode == 0, (
            folder,
            arguments[:3],
            completed.stdout[-4000:],
            completed.stderr[-2000:],
        )

    after = {"files": linted_files(), "caches": caches()}
    assert after["files"] == before["files"]
    assert after["caches"] == before["caches"]


def test_the_workflow_step_runs_exactly_u6s_lint_invocations():
    document, binary, found = workflow_invocations()
    assert binary == 'ruff="$PWD/backend/.venv/bin/ruff"'
    assert found == WORKFLOW_INVOCATIONS
    # PyYAML reads the bare `on` key as True.
    paths = document[True]["pull_request"]["paths"]
    assert "scripts/u6-lint*.toml" in paths
