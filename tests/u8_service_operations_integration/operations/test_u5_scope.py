"""U5's coverage lane measures no U8 code (U8 plan Step 22, "U8's lines out of U5's
files", item 7).

Three source scans, each parsing the source and each shown to find a planted case:

- no file in `.coveragerc.u5`'s include list imports a module listed under
  `.coveragerc.u8`'s "U8's own backend files", a module with a `u8_` segment, or
  `backend.modules.operations`;
- in `backend/`, `scripts/` and `ops/src/`, only `backend/u8_topics.py` calls
  `begin_send` with `admission` or with `**` arguments;
- in `backend/` and `ops/src/`, only U5's due path writes a digest run, and it hands in
  the due instant (U8 plan Step 159(e)). It is a syntax scan: it sees the INSERT's text
  in a string and calls named `prepare_run` or made on a `preparation`.

U5's three restored files and `.coveragerc.u5` hold exactly their built bytes: each is
compared with its SHA-256 pinned at the branch base (`built_files`), never with `HEAD`,
which in CI already holds every change.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from tests.u8_service_operations_integration.built_files import changed_from_built

ROOT = Path(__file__).resolve().parents[3]
U5_RC = ROOT / "backend/.coveragerc.u5"
U8_RC = ROOT / "backend/.coveragerc.u8"
OPERATIONS = "backend.modules.operations"
ADMISSION_CALLER = "backend/u8_topics.py"
U5_RESTORED = ("backend/u5_policy.py", "backend/modules/topics/delivery.py",
               "backend/u5_real_delivery.py")


def includes(rc: Path) -> list[str]:
    """The `[report]` include patterns, in order, comments dropped."""
    patterns, inside = [], False
    for line in rc.read_text().splitlines():
        if line.startswith("include"):
            inside = True
            continue
        if not inside:
            continue
        if line and not line[0].isspace():
            break  # the next option ends the list
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            patterns.append(stripped)
    return patterns


def u8_own_backend_patterns(rc: Path) -> list[str]:
    """The patterns listed under `.coveragerc.u8`'s "U8's own backend files" heading."""
    patterns, inside = [], False
    for line in rc.read_text().splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            inside = stripped.startswith("# U8's own backend files")
            continue
        if inside and stripped:
            patterns.append(stripped)
    return patterns


def expand(root: Path, patterns: list[str]) -> list[Path]:
    return sorted({path for pattern in patterns for path in root.glob(pattern)})


def module_of(root: Path, path: Path) -> str:
    return ".".join(path.relative_to(root).with_suffix("").parts)


def imported(root: Path, path: Path) -> set[str]:
    """Every module a file imports, relative imports resolved."""
    package = module_of(root, path).rsplit(".", 1)[0]
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_bytes(), str(path))):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                parts = package.split(".")
                base = parts[: len(parts) - node.level + 1]
                origin = ".".join(base + ([node.module] if node.module else []))
            else:
                origin = node.module or ""
            names.add(origin)
            names.update(f"{origin}.{alias.name}" for alias in node.names)
    return names


def is_u8(name: str, u8_modules: frozenset[str]) -> bool:
    return (
        any(part.startswith("u8_") for part in name.split("."))
        or name == OPERATIONS or name.startswith(OPERATIONS + ".")
        or name in u8_modules
        or any(name.startswith(module + ".") for module in u8_modules)
    )


def u8_imports_in(root: Path, files: list[Path], u8_modules: frozenset[str]) -> dict[str, list]:
    found = {}
    for path in files:
        names = sorted(name for name in imported(root, path) if is_u8(name, u8_modules))
        if names:
            found[str(path.relative_to(root))] = names
    return found


def admission_callers(root: Path, folders=("backend", "scripts", "ops/src")) -> list[str]:
    """Files that call `begin_send` with `admission` or with `**` arguments."""
    callers = []
    for folder in folders:
        for path in sorted((root / folder).rglob("*.py")):
            for node in ast.walk(ast.parse(path.read_bytes(), str(path))):
                if not isinstance(node, ast.Call):
                    continue
                name = getattr(node.func, "attr", None) or getattr(node.func, "id", None)
                if name == "begin_send" and any(
                    keyword.arg in (None, "admission") for keyword in node.keywords
                ):
                    callers.append(str(path.relative_to(root)))
                    break
    return callers


def u8_modules_at(root: Path) -> frozenset[str]:
    patterns = u8_own_backend_patterns(root / "backend/.coveragerc.u8")
    return frozenset(module_of(root, path) for path in expand(root, patterns))


def test_the_two_lists_are_read_as_written():
    u5 = includes(U5_RC)
    assert "backend/modules/topics/*.py" in u5 and "backend/u5_policy.py" in u5
    assert all(not pattern.startswith("#") for pattern in u5)
    own = u8_own_backend_patterns(U8_RC)
    assert {"backend/u8_*.py", "backend/modules/accounts/integrations/u8_digest_mail.py",
            "backend/modules/accounts/u8_verifier_key.py",
            "backend/modules/operations/*.py"} <= set(own)
    assert "backend/local_profile.py" not in own  # a shared file, not U8's own
    modules = u8_modules_at(ROOT)
    assert {"backend.u8_topics", "backend.modules.operations.ledger",
            "backend.modules.accounts.integrations.provider_gate"} <= modules


def test_no_file_u5s_lane_measures_imports_a_u8_module():
    files = expand(ROOT, includes(U5_RC))
    assert len(files) > 15  # the include list was really expanded
    assert u8_imports_in(ROOT, files, u8_modules_at(ROOT)) == {}


def test_the_import_scan_finds_a_planted_u8_import(tmp_path):
    folder = tmp_path / "backend/modules/topics"
    folder.mkdir(parents=True)
    planted = {
        "a.py": "from backend.u8_topics import GatedTopicsScheduler\n",
        "b.py": "from ..operations import ledger\n",
        "c.py": "def later():\n    from ..accounts.integrations.provider_gate import gate_active\n",
        "d.py": "import backend.modules.accounts.u8_verifier_key\n",
        "e.py": "from backend.u5_policy import TopicsPolicy\nimport json\n",
    }
    for name, source in planted.items():
        (folder / name).write_text(source)
    u8_modules = frozenset({"backend.modules.accounts.integrations.provider_gate"})
    found = u8_imports_in(tmp_path, sorted(folder.glob("*.py")), u8_modules)
    assert set(found) == {f"backend/modules/topics/{name}.py" for name in "abcd"}


def test_only_u8_topics_calls_begin_send_with_an_admission():
    assert admission_callers(ROOT) == [ADMISSION_CALLER]


def test_the_admission_scan_finds_a_planted_caller(tmp_path):
    folder = tmp_path / "backend"
    folder.mkdir()
    (folder / "keyword.py").write_text(
        "def go(repository, run):\n"
        "    return repository.begin_send(run, 'real', admission=lambda row: True)\n")
    (folder / "spread.py").write_text(
        "def go(repository, run, options):\n"
        "    return repository.begin_send(run, 'real', **options)\n")
    (folder / "plain.py").write_text(
        "def go(repository, run):\n"
        "    return repository.begin_send(run, 'real', real_send_limit=1)\n")
    assert admission_callers(tmp_path, folders=("backend",)) == [
        "backend/keyword.py", "backend/spread.py"]


# --- The digest run's one write path (U8 plan Step 159(e), L4-9) --------------------------
#
# `topics.digest` counts a pending run from `scheduled_at` and reads a pending run with
# none as late. So product code must hold one writer of a run, reached through one
# caller chain that hands in the due instant.

RUN_INSERT = re.compile(r"insert\s+into\s+topics\.digest_run\b", re.IGNORECASE)
RUN_WRITER = "backend/modules/topics/repository.py"
PREPARE_RUN_CALLER = "backend/modules/topics/preparation.py"
PREPARATION_CALLER = "backend/modules/topics/scheduler.py"
# U5's two realm tools: the only other writers of a run, never part of a composition.
REALM_TOOL_WRITERS = ["scripts/u5_browser_fixtures.py", "scripts/u5_real_delivery.py"]


def _scheduled_at(call: ast.Call) -> str | None:
    """The source of a call's `scheduled_at` argument, or None when it hands in none."""
    for keyword in call.keywords:
        if keyword.arg == "scheduled_at":
            return ast.unparse(keyword.value)
    return None


def _asks_a_preparation(call: ast.Call) -> bool:
    """`<...>preparation.prepare(...)`: a preparation asked to prepare a run."""
    func = call.func
    if not isinstance(func, ast.Attribute) or func.attr != "prepare":
        return False
    receiver = func.value
    return getattr(receiver, "attr", None) == "preparation" or (
        getattr(receiver, "id", None) == "preparation")


def digest_run_writers(root: Path, folders=("backend", "ops/src")) -> dict[str, list]:
    """The digest run's write path as the source holds it: the files whose strings hold
    the run's INSERT, and every call of `prepare_run` and of a preparation's `prepare`,
    each with its file and the source of its `scheduled_at` argument."""
    found: dict[str, list] = {"inserts": [], "prepare_run": [], "preparations": []}
    for folder in folders:
        for path in sorted((root / folder).rglob("*.py")):
            name = str(path.relative_to(root))
            for node in ast.walk(ast.parse(path.read_bytes(), str(path))):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    if RUN_INSERT.search(node.value) and name not in found["inserts"]:
                        found["inserts"].append(name)
                elif isinstance(node, ast.Call):
                    called = getattr(node.func, "attr", None) or getattr(node.func, "id", None)
                    if called == "prepare_run":
                        found["prepare_run"].append((name, _scheduled_at(node)))
                    elif _asks_a_preparation(node):
                        found["preparations"].append((name, _scheduled_at(node)))
    return found


def the_due_path_alone(found: dict[str, list]) -> bool:
    """The caller-chain rule: one writer, one caller of `prepare_run` passing its own
    `scheduled_at` on, and one preparation asked for, with the due row's instant."""
    return found == {
        "inserts": [RUN_WRITER],
        "prepare_run": [(PREPARE_RUN_CALLER, "scheduled_at")],
        "preparations": [(PREPARATION_CALLER, "topic['due_at']")],
    }


PLANTED_WRITERS = {
    "second_insert.py": (
        "def write(conn):\n"
        "    conn.execute('INSERT INTO topics.digest_run(id) ' 'VALUES(%s)', (1,))\n"),
    "second_caller.py": (
        "def write(repository, topic, day):\n"
        "    return repository.prepare_run(topic, day, day, 1, [])\n"),
    "second_preparation.py": (
        "def write(self, topic, window, now):\n"
        "    return self.preparation.prepare(topic, window, 1, scheduled_at=now)\n"),
}


def test_only_u5s_due_path_writes_a_digest_run_and_hands_in_the_due_instant(tmp_path):
    """In `backend/` and `ops/src/` a digest run is inserted in one file, `prepare_run`
    is called from U5's preparation only, and a preparation is asked for by U5's
    scheduler only, with `scheduled_at=topic["due_at"]`. Under `scripts/` U5's two realm
    tools are the only other writers. The scan is shown to find a planted second writer
    of each kind, in source strings of the test's own."""
    assert the_due_path_alone(digest_run_writers(ROOT)), digest_run_writers(ROOT)
    tools = digest_run_writers(ROOT, folders=("scripts",))
    writers = {*tools["inserts"], *(name for name, _ in tools["prepare_run"]),
               *(name for name, _ in tools["preparations"])}
    assert sorted(writers) == REALM_TOOL_WRITERS
    built = {RUN_WRITER: (ROOT / RUN_WRITER).read_text(),
             PREPARE_RUN_CALLER: (ROOT / PREPARE_RUN_CALLER).read_text(),
             PREPARATION_CALLER: (ROOT / PREPARATION_CALLER).read_text()}
    for planted in [None, *PLANTED_WRITERS]:
        tree = tmp_path / (planted or "built")
        for name, source in built.items():
            (tree / name).parent.mkdir(parents=True, exist_ok=True)
            (tree / name).write_text(source)
        if planted is not None:
            (tree / "backend" / planted).write_text(PLANTED_WRITERS[planted])
        found = digest_run_writers(tree, folders=("backend",))
        assert the_due_path_alone(found) == (planted is None), (planted, found)
    # A scheduler that hands in its pass's clock, not the due row's instant, is found too.
    clocked = tmp_path / "clocked"
    for name, source in built.items():
        (clocked / name).parent.mkdir(parents=True, exist_ok=True)
        (clocked / name).write_text(source.replace('scheduled_at=topic["due_at"]',
                                                   "scheduled_at=self._now()"))
    found = digest_run_writers(clocked, folders=("backend",))
    assert found["preparations"] == [(PREPARATION_CALLER, "self._now()")]
    assert not the_due_path_alone(found)


def test_u5s_three_restored_files_are_exactly_their_built_text():
    assert changed_from_built(U5_RESTORED) == {}
    # `.coveragerc.u5` itself is unchanged too.
    assert changed_from_built(["backend/.coveragerc.u5"]) == {}
