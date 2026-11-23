"""One way between U7's PlatformControl package and U8's (U8 plan Step 44; the person's
decisions of 2026-10-25, "Move U8's code out of U7" and "Its own package's name").

The scan parses the source. U7's package and test folder hold exactly their built files;
no file of U7's package imports, or names in a string, any `docsuri_ops` module outside
it or any `backend` module, or defines a moved name; nothing anywhere else imports a
moved module or name from its old place or names an old module or path; every relative
import inside `u8_platform/` resolves to a U8 module that defines the name; only U8's
`Operator` passes the executor's `adapter_module`; the runbooks and the installer's
checklist name U8's commands through `docsuri_ops.u8_platform` only; `.coveragerc.u8`'s
headings name the new package and U7's two seam files; and U7's part of `inventory.json`
is the built one. Each rule has a planted case it must catch. This file alone is exempt
from the old-name rules, because it names the old places to find them.
"""

from __future__ import annotations

import ast
import hashlib
import io
import json
import re
import tokenize
from collections.abc import Iterator
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
U7_PACKAGE = ROOT / "ops/src/docsuri_ops/platform_control"
U7_TESTS = ROOT / "tests/u7_controlled_platform_protocols"
U8_PACKAGE = ROOT / "ops/src/docsuri_ops/u8_platform"
RECORD = ROOT / ("aidlc/spaces/default/intents/261016-finish-v2-rebuild/construction/"
                 "u8-service-operations-integration/code-generation")
SELF = Path(__file__).resolve()
SKIPPED = {".venv", "node_modules", "__pycache__", ".pytest_cache", ".ruff_cache"}
# A file no checkout holds: this Mac's folder metadata, which `.gitignore` leaves out.
SKIPPED_FILES = {".DS_Store"}

U7_BUILT_FILES = {
    "__init__.py", "__main__.py", "authority.py", "cli.py", "enums.py", "errors.py",
    "evidence.py", "executor.py", "inventory.json", "inventory.py", "native_adapter.py",
    "observations.py", "profile.py", "reconciler.py", "schema.sql", "store.py",
}
U7_TEST_FILES = {
    "conftest.py",
    *(f"component/{name}.py" for name in (
        "test_authority_logic", "test_cli_projection", "test_entrypoint", "test_executor",
        "test_inventory", "test_native_adapter", "test_state_projection")),
    *(f"database/{name}.py" for name in (
        "test_guard_authority", "test_lease_and_binding", "test_owner_privileges")),
    "integration/test_cli_boundary.py", "integration/test_cli_in_process.py",
    "operations/test_recovery.py",
    *(f"repository/{name}.py" for name in (
        "test_crash_recovery", "test_durability", "test_operation_lifecycle",
        "test_reconciliation")),
}
MOVED_MODULES = ("u8_protocols", "fixed", "in_person", "credential_release", "decisions",
                 "recovery_words", "v1_environment", "drivers", "u8_store")
A6_EFFECT_CONSTANTS = tuple(f"EFFECT_{name}" for name in (
    "DATABASE_BACKUP", "DATABASE_RESTORE", "DATABASE_RECREATE", "DATABASE_REMOVE",
    "SERVICE_CONTROL", "TUNNEL_ROUTE", "ISOLATION_CHECK", "PROFILE_CHANGE", "COPY_DISPOSE",
    "V1_LIFECYCLE_APPLY", "DECISION_RECORD"))
MOVED_NAMES = frozenset({
    "U8PlatformProfile", "ReaderBinding", "PRODUCTION_LABELS", "V1_LABELS", "REALM_LABELS",
    "TUNNEL_ORIGINS", "PRODUCTION_STORE_LOGINS", "READER_FILE", "STORE_AMENDMENT",
    "U8_REALM_RUN", "U8_REALM_DATABASE", "U8_PRODUCTION_DATABASE", "U8_PRODUCTION_PORT",
    "U8_PRODUCTION_CONTROL", "U8_PRODUCTION_PROFILE", "U8_EFFECT_KINDS", "U7_EFFECT_KINDS",
    "_driver_effect", "_login_store", *A6_EFFECT_CONSTANTS,
})
OLD_MODULE = re.compile(r"\bplatform_control[./](" + "|".join(MOVED_MODULES) + r")\b")
OLD_COMMAND = re.compile(r"(-m\s+docsuri_ops\.platform_control|platform_control\.cli`?'s)"
                         r"\W+(recovery|cutover|migration|inventory)\b")
FOREIGN_MODULE = re.compile(r"\bdocsuri_ops\.(?!platform_control\b)[a-z_]")
DOCSURI_OPS_COMMAND = re.compile(r"\bdocsuri-ops\s+(platform|cutover|recovery|migration|"
                                 r"inventory)\b")
# The canonical JSON digest of `inventory.json` without `version`, `u8ProtocolsNote` and
# `u8Protocols`, taken from the branch base `bf82ed19`, where those keys are U7's own.
U7_INVENTORY_PART = "0231dab2480a19eb84f629f9c7e2bb709d1b96dfbe0ebdad38ab878d7b87c525"


# --- helpers --------------------------------------------------------------------------------


def files_under(folder: Path) -> Iterator[Path]:
    for path in sorted(folder.rglob("*")):
        if (path.is_file() and path.name not in SKIPPED_FILES
                and not SKIPPED & set(path.relative_to(folder).parts)):
            yield path


def python_sources(*folders: Path) -> Iterator[Path]:
    for folder in folders:
        for path in files_under(folder):
            if path.suffix == ".py" or (path.parent.name == "bin" and path.name.startswith(
                    "docsuri-")):
                yield path


def strings_of(tree: ast.AST) -> Iterator[str]:
    """Every string constant, f-string constant parts included."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            yield node.value


def imported_modules(tree: ast.AST, package: str | None = None) -> Iterator[tuple[str, str | None]]:
    """(module, name) for every import, relative imports resolved against `package`."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name, None
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if node.level:
                base = (package or "").split(".")
                base = base[: len(base) - node.level + 1]
                module = ".".join([*base, module] if module else base)
            for alias in node.names:
                yield module, alias.name


def package_of(path: Path) -> str:
    """The dotted package a source file's relative imports resolve against."""
    base = ROOT / "ops/src" if (ROOT / "ops/src") in path.parents else ROOT
    parts = list(path.relative_to(base).parts[:-1])
    return ".".join(parts)


# --- rule 1-2: the built file sets -------------------------------------------------------------


def file_set_problems(folder: Path, expected: set[str], *, subfolders: bool) -> list[str]:
    found = {str(path.relative_to(folder)) for path in files_under(folder)}
    problems = [f"extra {name}" for name in sorted(found - expected)]
    problems += [f"missing {name}" for name in sorted(expected - found)]
    if not subfolders:
        problems += [f"subfolder {path.name}" for path in folder.iterdir()
                     if path.is_dir() and path.name != "__pycache__"]
    return problems


def test_u7s_package_and_test_folder_hold_exactly_their_built_files(tmp_path):
    assert file_set_problems(U7_PACKAGE, U7_BUILT_FILES, subfolders=False) == []
    assert file_set_problems(U7_TESTS, U7_TEST_FILES, subfolders=True) == []
    planted = tmp_path / "platform_control"
    (planted / "drivers").mkdir(parents=True)
    for name in U7_BUILT_FILES:
        (planted / name).write_text("")
    (planted / "fixed.py").write_text("")
    assert file_set_problems(planted, U7_BUILT_FILES, subfolders=False) == [
        "extra fixed.py", "subfolder drivers"]


# --- rule 3-5: U7's package names nothing of U8's ------------------------------------------------


def u7_file_problems(source: str, package: str = "docsuri_ops.platform_control") -> list[str]:
    tree = ast.parse(source)
    problems = []
    for module, _name in imported_modules(tree, package):
        if module == "backend" or module.startswith("backend."):
            problems.append(f"imports {module}")
        elif (module == "docsuri_ops" or module.startswith("docsuri_ops.")) and not (
                module == "docsuri_ops.platform_control"
                or module.startswith("docsuri_ops.platform_control.")):
            problems.append(f"imports {module}")
    problems += [f"names {text!r}" for text in strings_of(tree) if FOREIGN_MODULE.search(text)]
    for node in tree.body:
        targets = ([node.name] if isinstance(node, (ast.FunctionDef, ast.ClassDef))
                   else [t.id for t in node.targets if isinstance(t, ast.Name)]
                   if isinstance(node, ast.Assign) else [])
        problems += [f"defines {name}" for name in targets if name in MOVED_NAMES]
    return problems


def test_no_file_of_u7s_package_imports_names_or_defines_anything_of_u8s():
    found = {path.name: u7_file_problems(path.read_text(), package_of(path))
             for path in python_sources(U7_PACKAGE)}
    assert {name: problems for name, problems in found.items() if problems} == {}
    inventory = (U7_PACKAGE / "inventory.json").read_text()
    assert "u8_platform" not in inventory and "docsuri_ops." not in inventory


@pytest.mark.parametrize("planted", [
    "from docsuri_ops.u8_platform import adapter\n",
    "def f():\n    from docsuri_ops.cutover.tool import main\n",
    "import backend.u8_host\n",
    "from .. import release\n",
    "CHILD = 'docsuri_ops.u8_platform.adapter'\n",
    "LABELS = f'{1}docsuri_ops.migration.words'\n",
    "U8_EFFECT_KINDS = ()\n",
    "class U8PlatformProfile:\n    pass\n",
    "def _driver_effect(request):\n    return request\n",
])
def test_the_u7_rules_find_a_planted_case(planted):
    assert u7_file_problems(planted)
    assert u7_file_problems("from . import enums\nfrom .store import Store\n"
                            "NAME = 'docsuri_ops.platform_control.native_adapter'\n") == []


# --- rule 6: nothing imports or names a moved module from its old place -------------------------


def outside_problems(source: str, package: str = "docsuri_ops.platform_control") -> list[str]:
    tree = ast.parse(source)
    problems = []
    for module, name in imported_modules(tree, package):
        if OLD_MODULE.search(module) or (
                module.startswith("docsuri_ops.platform_control") and (
                    name in MOVED_NAMES or name in MOVED_MODULES)):
            problems.append(f"imports {module}:{name}")
    problems += [f"names {text!r}" for text in strings_of(tree) if OLD_MODULE.search(text)]
    problems += [f"comment {text!r}" for text in comments_of(source) if OLD_MODULE.search(text)]
    return problems


def comments_of(source: str) -> list[str]:
    return [token.string for token in tokenize.generate_tokens(io.StringIO(source).readline)
            if token.type == tokenize.COMMENT]


def text_problems(text: str) -> list[str]:
    return [line for line in text.splitlines() if OLD_MODULE.search(line)
            or OLD_COMMAND.search(line)]


def outside_sources() -> Iterator[Path]:
    for path in python_sources(ROOT / "backend", ROOT / "ops", ROOT / "scripts", ROOT / "tests"):
        if path.resolve() != SELF:
            yield path


def test_nothing_imports_or_names_a_moved_module_from_its_old_place():
    found = {}
    for path in outside_sources():
        problems = outside_problems(path.read_text(), package_of(path))
        if problems:
            found[str(path.relative_to(ROOT))] = problems
    assert found == {}
    texts = [*files_under(ROOT / ".github"), *sorted((ROOT / "backend").glob(".coveragerc*")),
             *sorted((ROOT / "backend").glob("pytest*.ini"))]
    assert {str(path.relative_to(ROOT)): text_problems(path.read_text()) for path in texts
            if text_problems(path.read_text())} == {}


@pytest.mark.parametrize("planted", [
    "from docsuri_ops.platform_control.u8_protocols import Operator\n",
    "from docsuri_ops.platform_control import fixed\n",
    "import docsuri_ops.platform_control.drivers.realm\n",
    "from docsuri_ops.platform_control.profile import U8PlatformProfile\n",
    "from docsuri_ops.platform_control.enums import U8_EFFECT_KINDS\n",
    "from .profile import REALM_LABELS\n",
    "MODULE = 'docsuri_ops.platform_control.recovery_words'\n",
    "PATH = f'ops/src/docsuri_ops/platform_control/u8_store.sql'\n",
    "x = 1  # see platform_control.decisions\n",
])
def test_the_old_place_rules_find_a_planted_case(planted):
    assert outside_problems(planted)


def test_the_old_place_rules_pass_u7_names_and_sql():
    assert outside_problems(
        "from docsuri_ops.platform_control.profile import private_bytes\n"
        "from docsuri_ops.platform_control import RUNTIME_ROLE, enums\n"
        "SQL = 'SELECT * FROM platform_control.target_lease'\n") == []
    assert text_problems("    ops/src/docsuri_ops/platform_control/drivers/*.py\n")
    assert text_problems("run: python -m docsuri_ops.platform_control cutover status\n")
    assert not text_problems("    ops/src/docsuri_ops/u8_platform/drivers/*.py\n")


def test_no_string_names_u8s_commands_through_u7s_package():
    found = {}
    for path in outside_sources():
        if U7_TESTS in path.parents or U7_PACKAGE in path.parents:
            continue
        tree = ast.parse(path.read_text())
        hits = [text for text in strings_of(tree) if OLD_COMMAND.search(text)]
        hits += [text for text in comments_of(path.read_text()) if OLD_COMMAND.search(text)]
        if hits:
            found[str(path.relative_to(ROOT))] = hits
    assert found == {}
    for planted in ("python -m docsuri_ops.platform_control recovery backup",
                    "`docsuri_ops.platform_control.cli`'s `cutover` words"):
        assert OLD_COMMAND.search(planted)
    assert not OLD_COMMAND.search("python -I -m docsuri_ops.u8_platform cutover begin")


# --- rule 7: relative imports inside U8's package -------------------------------------------------


def defined_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            names.update(t.id for t in node.targets if isinstance(t, ast.Name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            names.update((alias.asname or alias.name).split(".")[0] for alias in node.names)
    return names


def relative_import_problems(path: Path, source: str, package_root: Path) -> list[str]:
    """Each relative import must resolve inside `package_root` to a module that exists and
    defines the name (or to a submodule of that name)."""
    problems = []
    folder = path.parent
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.ImportFrom) or not node.level:
            continue
        base = folder
        for _ in range(node.level - 1):
            base = base.parent
        if base != package_root and package_root not in base.parents:
            problems.append(f"leaves the package: level {node.level}")
            continue
        target = base.joinpath(*(node.module or "").split(".")) if node.module else base
        module_file = (target / "__init__.py") if target.is_dir() else target.with_suffix(".py")
        if not module_file.is_file():
            problems.append(f"no module {node.module!r}")
            continue
        defined = defined_names(module_file)
        for alias in node.names:
            submodule = module_file.parent / f"{alias.name}.py" if module_file.name == (
                "__init__.py") else None
            if alias.name not in defined and not (submodule and submodule.is_file()) and not (
                    module_file.name == "__init__.py"
                    and (module_file.parent / alias.name / "__init__.py").is_file()):
                problems.append(f"{node.module or '.'} has no {alias.name}")
    return problems


def test_every_relative_import_inside_u8s_package_resolves_to_a_u8_module():
    found = {}
    for path in python_sources(U8_PACKAGE):
        problems = relative_import_problems(path, path.read_text(), U8_PACKAGE)
        if problems:
            found[str(path.relative_to(ROOT))] = problems
    assert found == {}
    assert sorted(p.name for p in U8_PACKAGE.glob("*.py")) == sorted([
        "__init__.py", "__main__.py", "adapter.py", "availability_words.py",
        "credential_release.py", "decisions.py",
        "effect_kinds.py", "fixed.py", "in_person.py", "operator_tool.py",
        "platform_profile.py", "recovery_words.py", "service_words.py", "u8_protocols.py",
        "v1_environment.py"])
    assert (U8_PACKAGE / "u8_store.sql").is_file()
    assert (U8_PACKAGE / "__init__.py").read_text().count("\n") < 12  # a docstring only
    assert not [node for node in ast.parse((U8_PACKAGE / "__init__.py").read_text()).body
                if not isinstance(node, ast.Expr)]


@pytest.mark.parametrize("planted", [
    "from . import RUNTIME_ROLE\n", "from . import enums\n",
    "from .cli import effect_token\n", "from .profile import private_bytes\n",
    "from .platform_profile import PlatformProfile\n", "from ... import release\n",
])
def test_the_relative_import_rule_finds_a_planted_case(planted):
    path = U8_PACKAGE / "u8_protocols.py"
    assert relative_import_problems(path, planted, U8_PACKAGE)
    assert relative_import_problems(
        path, "from .platform_profile import U8PlatformProfile\nfrom .drivers import apply\n"
              "from .drivers.realm import RealmDriver\n", U8_PACKAGE) == []


# --- rule 8: only U8's Operator names the bounded child -------------------------------------------


def adapter_module_calls(source: str) -> list[tuple[str | None, str | None, str]]:
    """(class, function, value) of every call passing `adapter_module` by keyword."""
    found: list[tuple[str | None, str | None, str]] = []

    def visit(node: ast.AST, owner: str | None, function: str | None) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ClassDef):
                visit(child, child.name, function)
                continue
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                visit(child, owner, child.name)
                continue
            if isinstance(child, ast.Call):
                found.extend(
                    (owner, function, keyword.value.id if isinstance(keyword.value, ast.Name)
                     else ast.unparse(keyword.value))
                    for keyword in child.keywords if keyword.arg == "adapter_module")
            visit(child, owner, function)

    visit(ast.parse(source), None, None)
    return found


def test_only_u8s_operator_passes_the_executors_adapter_module():
    calls = {}
    for path in python_sources(ROOT / "backend", ROOT / "ops", ROOT / "scripts"):
        found = adapter_module_calls(path.read_text())
        if found:
            calls[str(path.relative_to(ROOT))] = found
    assert calls == {"ops/src/docsuri_ops/u8_platform/u8_protocols.py": [
        ("Operator", "execute", "BOUNDED_CHILD")]}
    from docsuri_ops.u8_platform.u8_protocols import BOUNDED_CHILD

    assert BOUNDED_CHILD == "docsuri_ops.u8_platform.adapter"
    planted = "def go(run):\n    run(adapter_module='docsuri_ops.elsewhere')\n"
    assert adapter_module_calls(planted) == [(None, "go", "'docsuri_ops.elsewhere'")]


# --- rule 9: the runbooks and the installer's checklist ------------------------------------------


def runbook_problems(text: str) -> list[str]:
    problems = [line for line in text.splitlines()
                if re.search(r"-m\s+docsuri_ops\.(?!u8_platform\b)", line)]
    problems += [line for line in text.splitlines() if DOCSURI_OPS_COMMAND.search(line)]
    return problems


def test_the_runbooks_and_the_checklist_run_u8s_commands_through_u8s_package():
    migration = (RECORD / "u8-migration-runbook.md").read_text()
    cutover = (RECORD / "u8-cutover-runbook.md").read_text()
    installation = (RECORD / "u8-installation-runbook.md").read_text()
    for text in (migration, cutover):
        assert "-m docsuri_ops.u8_platform" in text
        assert runbook_problems(text) == []
    first = [line for line in installation.splitlines()
             if line.startswith("| `first-rehearsal-database`")]
    assert len(first) == 1 and "-m docsuri_ops.u8_platform cutover begin" in first[0]
    assert runbook_problems(installation) == []
    checklist = (ROOT / "ops/src/docsuri_ops/arrangement/checklist.py").read_text()
    assert not DOCSURI_OPS_COMMAND.search(checklist)
    assert "-m docsuri_ops.u8_platform cutover begin --production" in checklist
    for planted in ("python -m docsuri_ops.platform_control cutover begin",
                    "Run `docsuri-ops cutover begin`.", "(docsuri-ops platform)"):
        assert runbook_problems(planted)


# --- rule 10: the coverage headings ---------------------------------------------------------------


def coverage_headings(text: str) -> dict[str, list[str]]:
    headings: dict[str, list[str]] = {}
    current = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#") and line.startswith("    "):
            current = stripped
            headings.setdefault(current, [])
        elif current is not None and line.startswith("    ") and stripped:
            headings[current].append(stripped)
        elif not line.startswith("    "):
            current = None
    return headings


def coverage_problems(text: str) -> list[str]:
    headings = coverage_headings(text)
    ops = next((paths for heading, paths in headings.items()
                if heading.startswith("# U8's own ops files")), None)
    owner = next((paths for heading, paths in headings.items()
                  if heading.startswith("# Owner files U8 changes")), None)
    problems = []
    if ops is None or owner is None:
        return ["a heading is missing"]
    for wanted in ("ops/src/docsuri_ops/u8_platform/*.py",
                   "ops/src/docsuri_ops/u8_platform/drivers/*.py"):
        if wanted not in ops:
            problems.append(f"ops heading lacks {wanted}")
    problems += [f"ops heading names {p}" for p in ops if "platform_control" in p]
    seams = sorted(p for p in owner if "platform_control" in p)
    if seams != ["ops/src/docsuri_ops/platform_control/executor.py",
                 "ops/src/docsuri_ops/platform_control/native_adapter.py"]:
        problems.append(f"owner heading names {seams}")
    problems += [f"owner heading names {p}" for p in owner if "u8_platform" in p]
    for heading, paths in headings.items():
        if heading.startswith(("# U8's own ops files", "# Owner files U8 changes")):
            continue
        problems += [f"{heading} names {p}" for p in paths
                     if "platform_control" in p or "u8_platform" in p]
    return problems


def test_the_coverage_headings_name_the_new_package_and_the_two_seam_files():
    text = (ROOT / "backend/.coveragerc.u8").read_text()
    assert coverage_problems(text) == []
    planted = text.replace("    ops/src/docsuri_ops/platform_control/executor.py\n",
                           "    ops/src/docsuri_ops/platform_control/cli.py\n")
    assert coverage_problems(planted)
    moved_back = text.replace("    ops/src/docsuri_ops/u8_platform/drivers/*.py\n",
                              "    ops/src/docsuri_ops/platform_control/drivers/*.py\n")
    assert coverage_problems(moved_back)


# --- rule 11: U7's part of the inventory ------------------------------------------------------


def u7_part_digest(document: dict) -> str:
    part = {key: value for key, value in document.items()
            if key not in ("version", "u8ProtocolsNote", "u8Protocols")}
    return hashlib.sha256(json.dumps(part, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False).encode()).hexdigest()


def test_u7s_part_of_the_inventory_is_the_built_one():
    document = json.loads((U7_PACKAGE / "inventory.json").read_text())
    assert document["version"] == 2 and len(document["protocols"]) == 8
    assert u7_part_digest(document) == U7_INVENTORY_PART
    changed = json.loads(json.dumps(document))
    changed["protocols"][0]["notes"] = "changed"
    assert u7_part_digest(changed) != U7_INVENTORY_PART
