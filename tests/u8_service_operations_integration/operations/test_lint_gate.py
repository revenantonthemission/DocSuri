"""Ruff holds U8's files to E, F, I, UP and B at 100 (U8 plan Step 97(g); Step 95(l), L1-34).

The six U8 invocations of the workflow step "Lint U8's targets" run here with the pinned
Ruff 0.16.8 from `backend/.venv` and `--no-cache`, each exiting 0 without a
`shared/python` environment: U8's tests under `scripts/u8-lint.toml`; U8's scripts under
`scripts/u8-lint-scripts.toml` (Ruff's default selection, extended); U8's own backend
and ops files under their folders' own configurations; U8's own files in the accounts
and library folders under the two strict files, run from those folders; and
`shared/python` under its own `pyproject.toml`. The configurations are read with
`tomllib`, the resolved rule sets with `--show-settings`, and the workflow step must hold
exactly these invocations plus the earlier units' (7), which is not run here. Planted
files in `tmp_path` show that the configurations refuse what they should. Nothing is
written into the repository.
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
WORKFLOW = ROOT / ".github/workflows/u8-complete-verification.yml"
STEP = "Lint U8's targets"
SELECTED = ["E", "F", "I", "UP", "B"]
TESTS_CONFIG = "scripts/u8-lint.toml"
SCRIPTS_CONFIG = "scripts/u8-lint-scripts.toml"
TARGETS = "scripts/u8-lint-targets.txt"
ACCOUNTS_FOLDER = "backend/modules/accounts"
LIBRARY_FOLDER = "backend/modules/library"
SHARED_FOLDER = "shared/python"
ACCOUNTS_CONFIG = "../../../scripts/u8-lint-accounts.toml"
LIBRARY_CONFIG = "../../../scripts/u8-lint-library.toml"
TARGETS_WORDS = f"$(cat {TARGETS})"
# (3): U8's own backend and ops files, and U8's own files in other owners' folders.
U8_BACKEND = (
    "backend/u8_*.py", "backend/production_boundary.py", "backend/log_events.py",
    "backend/request_context.py", "backend/maintenance_server.py", "backend/import_parity.py",
    "backend/modules/operations", "ops/src/docsuri_ops", "backend/modules/plans/u8_usage.py",
    "backend/modules/research/control_lifecycle.py", "backend/modules/research/job_list.py",
    "backend/modules/discovery/u8_search.py", "backend/modules/corpus/limits.py",
    "backend/modules/corpus/paper_import.py",
    "backend/modules/personalization/import_repository.py",
    "backend/modules/summarization/model_runtime.py",
    "backend/modules/summarization/u8_assistance_sources.py",
)
# (4): the 20 U8 files in the accounts folder (`.coveragerc.u8`, "U8's own backend files").
ACCOUNTS = (
    "entry_limits.py", "integrations/email_allowance.py", "integrations/identity_providers.py",
    "integrations/account_mail.py", "integrations/provider_gate.py",
    "integrations/u8_digest_mail.py", "u8_verifier_key.py", "u8_control_policy.py",
    "u8_entry.py", "u8_mail_outbox.py", "u8_mfa.py", "u8_identity.py", "u8_lifecycle.py",
    "u8_control_http.py", "u8_local_http.py", "services/v2_rollback_apply.py",
    "services/rollback_outcomes.py", "repository/imports.py", "services/first_sign_in.py",
    "services/v1_import.py",
)
LIBRARY = ("repository/imports.py",)
# (7): the earlier units' paths, under their own configurations; recorded, not run here.
EARLIER = (
    "backend/local_profile.py", "backend/transactions.py", "backend/local_browser.py",
    "backend/local_host.py", "backend/artifacts.py", "backend/control_worker.py",
    "backend/control_runtime.py", "backend/lifecycle_effects.py", "backend/modules/accounts",
    "backend/modules/research", "backend/modules/discovery", "backend/modules/corpus",
    "backend/modules/export", "backend/modules/topics", "backend/modules/personalization",
    "backend/u5_real_delivery.py", "backend/u6_real_export.py", "backend/u5_policy.py",
    "backend/u6_policy.py",
)
# What the workflow's seven invocations hold: (folder, arguments after `check --no-cache`).
WORKFLOW_INVOCATIONS = [
    (".", ["--config", TESTS_CONFIG, "tests/u8_service_operations_integration"]),
    (".", ["--config", SCRIPTS_CONFIG, TARGETS_WORDS]),
    (".", list(U8_BACKEND)),
    (ACCOUNTS_FOLDER, ["--config", ACCOUNTS_CONFIG, *ACCOUNTS]),
    (LIBRARY_FOLDER, ["--config", LIBRARY_CONFIG, *LIBRARY]),
    (SHARED_FOLDER, ["."]),
    (".", list(EARLIER)),
]
FOLDERS = (".", ACCOUNTS_FOLDER, LIBRARY_FOLDER, SHARED_FOLDER)


def ruff(folder: str | Path, *arguments: str) -> subprocess.CompletedProcess:
    """One `ruff check --no-cache` from `folder`, read-only."""
    return subprocess.run([str(RUFF), "check", "--no-cache", *arguments], cwd=ROOT / folder,
                          capture_output=True, text=True, timeout=120, check=False)


def expanded(paths: list[str] | tuple[str, ...]) -> list[str]:
    """The paths with their globs expanded from the repository root, as the shell does."""
    found = []
    for path in paths:
        if any(mark in path for mark in "*?["):
            matches = sorted(str(item.relative_to(ROOT)) for item in ROOT.glob(path))
            assert matches, path
            found.extend(matches)
        else:
            found.append(path)
    return found


def script_targets() -> list[str]:
    lines = (ROOT / TARGETS).read_text().splitlines()
    assert lines == ["scripts/u8_*.py", "scripts/serve_docsuri_u8.py",
                     "scripts/verify_docsuri_u8.py"]
    return expanded(lines)


def u8_invocations() -> list[tuple[str, list[str]]]:
    """The six U8 invocations (1) to (6), globs expanded."""
    run = []
    for folder, arguments in WORKFLOW_INVOCATIONS[:6]:
        if TARGETS_WORDS in arguments:
            arguments = [word for word in arguments if word != TARGETS_WORDS] + script_targets()
        run.append((folder, expanded(arguments) if folder == "." else arguments))
    return run


def enabled_rules(output: str) -> set[str]:
    """The rule codes of `linter.rules.enabled` in a `--show-settings` answer."""
    block = output.split("linter.rules.enabled = [", 1)[1].split("\n]", 1)[0]
    return set(re.findall(r"\(([A-Z]+[0-9]+)\)", block))


def settings(folder: str, *arguments: str) -> set[str]:
    completed = ruff(folder, "--show-settings", *arguments)
    assert completed.returncode == 0, completed.stderr
    return enabled_rules(completed.stdout)


def workflow_invocations() -> tuple[str, list[tuple[str, list[str]]]]:
    """The ruff binary the step names and each `"$ruff" check` it runs."""
    document = yaml.safe_load(WORKFLOW.read_text())
    steps = [step for job in document["jobs"].values() for step in job.get("steps", [])
             if step.get("name") == STEP]
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
            folder, line = line[len("(cd "):].split(" && ", 1)
            assert line.endswith(")")
            line = line[:-1]
        line = line.replace(TARGETS_WORDS, "TARGETS_WORDS")
        words = shlex.split(line)
        assert words[:3] == ["$ruff", "check", "--no-cache"], line
        found.append((folder, [TARGETS_WORDS if word == "TARGETS_WORDS" else word
                               for word in words[3:]]))
    assert len(binary) == 1
    return binary[0], found


def plant(tmp_path: Path, name: str, text: str) -> Path:
    path = tmp_path / name
    path.write_text(text)
    return path


def codes(completed: subprocess.CompletedProcess) -> set[str]:
    return {finding["code"] for finding in json.loads(completed.stdout)}


def linted_files() -> dict[str, str]:
    """The SHA-256 of every file the six U8 invocations name or hold (configurations too)."""
    found = {}
    for folder, arguments in u8_invocations():
        for word in arguments:
            if word.startswith("-"):
                continue
            path = (ROOT / folder / word).resolve()
            items = sorted(path.rglob("*.py")) if path.is_dir() else [path]
            for item in items:
                if item.is_file():
                    found[str(item)] = hashlib.sha256(item.read_bytes()).hexdigest()
    return found


def repository_snapshot() -> dict:
    """What a Ruff write would change: the ignored-and-untracked listing, every file of
    an existing `.ruff_cache` in the four folders (size and modification time), and the
    digests of the linted files."""
    status = subprocess.run(["git", "status", "--porcelain", "--ignored", "-z"], cwd=ROOT,
                            capture_output=True, timeout=120, check=True).stdout
    caches = {}
    for folder in FOLDERS:
        cache = ROOT / folder / ".ruff_cache"
        if cache.is_dir() and not cache.is_symlink():
            for item in sorted(cache.rglob("*")):
                facts = item.lstat()
                caches[str(item.relative_to(ROOT))] = (facts.st_size, facts.st_mtime_ns)
    return {"status": status, "caches": caches, "files": linted_files()}


def test_ruff_passes_on_u8s_files_and_the_shared_contract_with_e_f_i_up_b_at_100(tmp_path):
    before = repository_snapshot()
    version = subprocess.run([str(RUFF), "--version"], capture_output=True, text=True,
                             timeout=30, check=True)
    assert version.stdout.strip() == RUFF_VERSION

    # The six U8 invocations, each with --no-cache, exit 0.
    for folder, arguments in u8_invocations():
        completed = ruff(folder, *arguments)
        assert completed.returncode == 0, (folder, arguments[:3], completed.stdout[-4000:],
                                           completed.stderr[-2000:])

    # The four configurations, read with tomllib.
    configurations = {name: tomllib.loads((ROOT / name).read_text()) for name in (
        TESTS_CONFIG, SCRIPTS_CONFIG, "scripts/u8-lint-accounts.toml",
        "scripts/u8-lint-library.toml")}
    for name, value in configurations.items():
        assert value["line-length"] == 100 and value["target-version"] == "py313", name
        assert not value["lint"].get("ignore"), name
        assert "extend-ignore" not in value["lint"], name
        # Ignore nothing, fix nothing: no top-level ignores, no per-file ignores, no fixer.
        # (`lint.ignore = []` is how the strict files clear their folders' ignores.)
        for key in ("ignore", "extend-ignore", "per-file-ignores", "extend-per-file-ignores",
                    "fix", "unsafe-fixes"):
            assert key not in value, (name, key)
            assert key == "ignore" or key not in value["lint"], (name, key)
    # Nor do the folder configurations the strict files extend.
    for folder in (ACCOUNTS_FOLDER, LIBRARY_FOLDER):
        extended = tomllib.loads((ROOT / folder / "ruff.toml").read_text())
        for key in ("per-file-ignores", "extend-per-file-ignores", "fix", "unsafe-fixes"):
            assert key not in extended and key not in extended.get("lint", {}), (folder, key)
    for name in (TESTS_CONFIG, "scripts/u8-lint-accounts.toml", "scripts/u8-lint-library.toml"):
        assert configurations[name]["lint"]["select"] == SELECTED, name
    scripts = configurations[SCRIPTS_CONFIG]["lint"]
    assert scripts["extend-select"] == SELECTED and "select" not in scripts
    assert configurations["scripts/u8-lint-accounts.toml"]["extend"] == (
        "../backend/modules/accounts/ruff.toml")
    assert configurations["scripts/u8-lint-library.toml"]["extend"] == (
        "../backend/modules/library/ruff.toml")
    shared = tomllib.loads((ROOT / SHARED_FOLDER / "pyproject.toml").read_text())["tool"]["ruff"]
    assert shared["line-length"] == 100 and shared["lint"]["select"] == SELECTED

    # The scripts' resolved rules hold Ruff's default selection and E,F,I,UP,B.
    script = "scripts/u8_native.py"
    resolved = settings(".", "--config", SCRIPTS_CONFIG, script)
    assert settings(".", "--isolated", script) <= resolved
    assert settings(".", "--isolated", "--select", ",".join(SELECTED), script) <= resolved
    assert {"BLE001", "S110", "S102"} <= resolved
    # The strict files ignore nothing their folders ignore.
    accounts = settings(ACCOUNTS_FOLDER, "--config", ACCOUNTS_CONFIG, "u8_entry.py")
    library = settings(LIBRARY_FOLDER, "--config", LIBRARY_CONFIG, "repository/imports.py")
    assert {"B008", "E501", "UP042"} <= accounts and {"B008", "E501", "UP042"} <= library

    # The workflow step holds exactly these invocations, plus the earlier units' (7).
    binary, found = workflow_invocations()
    assert binary == 'ruff="$PWD/backend/.venv/bin/ruff"'
    assert found == WORKFLOW_INVOCATIONS

    # Planted files fail as they should.
    long_line = "VALUE = " + " + ".join(["1"] * 24)
    long_and_unsorted = plant(tmp_path, "planted_tests.py",
                              f"import sys\nimport os\n\n{long_line}\n"
                              "print(os.sep, sys.argv, VALUE)\n")
    assert len(long_and_unsorted.read_text().splitlines()[3]) == 101
    completed = ruff(".", "--config", TESTS_CONFIG, "--output-format", "json",
                     str(long_and_unsorted))
    assert completed.returncode == 1 and {"E501", "I001"} <= codes(completed)
    swallowed = plant(tmp_path, "planted_script.py",
                      "def f():\n    try:\n        return 1\n    except Exception:\n        pass\n")
    completed = ruff(".", "--config", SCRIPTS_CONFIG, "--output-format", "json", str(swallowed))
    assert completed.returncode == 1 and {"S110", "BLE001"} <= codes(completed)

    # Nothing was written into the repository: no new or changed path in the listing, no
    # cache file added or touched, no linted file rewritten.
    after = repository_snapshot()
    assert after["files"] == before["files"]
    assert after["caches"] == before["caches"]
    assert after["status"] == before["status"]
