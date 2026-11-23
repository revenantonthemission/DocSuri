"""One way: U8 builds on U2, never the reverse (U8 plan Step 44; the person's decision of
2026-10-24, "Move, scope tools, test U2").

Each scan parses the source and is shown to find a planted case:

1. no file `.coveragerc.u2` measures imports a U8 module (a module under either of
   `.coveragerc.u8`'s "U8's own" headings, any module with a `u8_` segment, or
   `backend.modules.operations`), except three pinned lazy imports: `for_realm`'s
   complete policies, and `backend/transactions.py`'s `complete_gates` and
   `complete_realm`;
2. no such file defines or uses a name that moved to a U8 module, except
   `COMPLETE_POLICIES` inside `for_realm`;
3. no file in `backend/`, `scripts/` or `ops/src/` imports a moved name from its old
   module, lazy imports included;
4. U8's own files build U2's control classes only through U8's: no direct call of
   `ControlEntryService`, `ControlMfaService`, `ControlIdentityService`,
   `ControlLifecycleService`, `ControlCapacity` or `ControlWorker`, except
   `ControlCapacity` in `complete_capacity`;
5. `AssistanceDispatch(`, `CompleteAssistanceDispatch(` (U8's dispatch with the job
   lines, U8 plan Step 51(d)) and `ResearchExecution(` appear in U8's own files only in
   `u8_host.build_paper_corpus`, `u8_outward.production_corpus` and
   `scripts/u8_fixtures.ready_novelty`, and each of these calls `use_complete_usage`;
6. no such file names a column or function only a U8 migration adds
   (`client_address_digest`, by the person's decision of 2026-10-25, "Cap per address,
   raise site cap", and `expire_identity_flows`, by "Count every start, free places at
   once"): U2's `begin` and `complete` reach the provider start limits only through their
   hooks (`_admit_start`, `_finish_refused`), which U8's `ArrivalIdentityService` fills,
   and the site-wide cap only through `flow_capacity`.
"""

from __future__ import annotations

import ast
import configparser
import fnmatch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
U2_RC = ROOT / "backend/.coveragerc.u2"
U8_RC = ROOT / "backend/.coveragerc.u8"
OPERATIONS = "backend.modules.operations"
OPS_PACKAGE = ROOT / "ops/src"
# (file, function, module): the three lazy imports at allowlist sites.
PINNED = frozenset({
    ("backend/modules/accounts/control_policy.py", "for_realm",
     "backend.modules.accounts.u8_control_policy"),
    ("backend/transactions.py", "complete_gates", "backend.u8_policy"),
    ("backend/transactions.py", "complete_realm", "docsuri_ops.arrangement.paths"),
})
# Each name that moved to a U8 module, by the U2 module it left (Step 44's box).
MOVED = {
    "backend.control_runtime": {"CapacityBudget", "capacity_budget", "CapacityRefresher",
                                "BudgetedCapacity", "complete_capacity"},
    "backend.control_worker": {"CompleteLifecycleWorker", "retention_date",
                               "INVALID_RETENTION_DATE"},
    "backend.local_profile": {
        "ProductionProfile", "ProfileRefused", "custody_failure", "listen_port",
        "public_authority", "PRODUCTION_DATABASE", "PRODUCTION_REALM",
        "PRODUCTION_LISTEN_PORT", "PRODUCTION_MAINTENANCE_PORT", "PRODUCTION_DATABASE_PORT",
        "PRODUCTION_MANIFEST", "PRODUCTION_ACCOUNT_ROLES"},
    "backend.modules.accounts.control_policy": {
        "Admission", "ADMISSIONS", "remaining_seconds", "BOUND_REALMS", "SYNTHETIC_CEILINGS",
        "PRODUCTION_CEILINGS", "CEILINGS", "CompletePolicy", "U8_SYNTHETIC_POLICY",
        "PRODUCTION_POLICY", "COMPLETE_POLICIES"},
    "backend.modules.accounts.services.control_entry": {"CompleteControlEntryService"},
    "backend.modules.accounts.services.control_mfa": {"CompleteMfaService",
                                                       "SetupEnrolment"},
    "backend.modules.accounts.services.control_identity": {
        "ArrivalIdentityService", "ARRIVAL_PATH", "arrival_callback",
        "ArrivalFixtureProvider", "arrival_providers"},
    "backend.modules.accounts.services.control_lifecycle": {"CompleteLifecycleService"},
    "backend.modules.accounts.control_http": {"D1ControlRoutes", "d1_control_router"},
    "backend.modules.accounts.local_http": {"D1AccountRoutes", "d1_account_router"},
    "backend.modules.plans.control_service": {
        "ResearchUsageService", "ImportedUsage", "CompleteUsage", "usage_for",
        "use_complete_usage", "IMPORT_ACTOR"},
}
ALL_MOVED = frozenset().union(*MOVED.values())
# Allowed: the complete realms' policies `for_realm` reads lazily from U8's module.
ALLOWED_USES = frozenset({("backend/modules/accounts/control_policy.py", "for_realm",
                           "COMPLETE_POLICIES")})
U2_CLASSES = frozenset({"ControlEntryService", "ControlMfaService", "ControlIdentityService",
                        "ControlLifecycleService", "ControlCapacity", "ControlWorker"})
ALLOWED_BUILDS = frozenset({("backend/u8_capacity.py", "complete_capacity", "ControlCapacity")})
USAGE_PARTS = frozenset({"AssistanceDispatch", "CompleteAssistanceDispatch",
                         "ResearchExecution"})
USAGE_SITES = frozenset({
    ("backend/u8_host.py", "build_paper_corpus"),
    ("backend/u8_outward.py", "production_corpus"),
    ("scripts/u8_fixtures.py", "ready_novelty"),
    # The fixtures' ready assistance job (plan Step 167, L4-13): PaperAssistance's dispatch
    # built under `use_complete_usage`, as `ready_novelty` builds the research execution.
    ("scripts/u8_fixture_assistance.py", "assistance_job"),
})
U8_OWN_PATTERNS = (
    "backend/u8_*.py", "backend/modules/*/u8_*.py", "backend/modules/*/*/u8_*.py",
    "backend/modules/operations/**/*.py", "scripts/u8_*.py",
)


# --- Reading the source -------------------------------------------------------------------


def u2_files() -> list[str]:
    parser = configparser.ConfigParser()
    parser.read(U2_RC)
    return [line.strip() for line in parser["report"]["include"].splitlines() if line.strip()]


def u8_own_patterns() -> list[str]:
    """Both of `.coveragerc.u8`'s "U8's own" headings: its backend and its ops files."""
    patterns, inside = [], False
    for line in U8_RC.read_text().splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            inside = stripped.startswith(("# U8's own backend files", "# U8's own ops files"))
            continue
        if stripped.startswith(("omit", "fail_under", "[")):
            inside = False
        if inside and stripped:
            patterns.append(stripped)
    return patterns


def module_of(root: Path, path: Path) -> str:
    relative = path.relative_to(root)
    if relative.parts[:2] == ("ops", "src"):
        relative = Path(*relative.parts[2:])
    return ".".join(relative.with_suffix("").parts)


def u8_modules(root: Path = ROOT) -> frozenset[str]:
    paths = {path for pattern in u8_own_patterns() for path in root.glob(pattern)}
    return frozenset(module_of(root, path) for path in paths)


def scopes(tree) -> dict[int, str]:
    """Each node's enclosing top-level or method function name, by node id."""
    owner: dict[int, str] = {}

    def visit(node, name: str) -> None:
        for child in ast.iter_child_nodes(node):
            inner = child.name if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                else name
            owner[id(child)] = inner
            visit(child, inner)

    visit(tree, "<module>")
    return owner


def imports(root: Path, path: Path) -> list[tuple[str, str, str]]:
    """(module, imported name or '', enclosing function) of every import in a file,
    relative imports resolved."""
    tree = ast.parse(path.read_bytes(), str(path))
    owner = scopes(tree)
    package = module_of(root, path).rsplit(".", 1)[0]
    found = []
    for node in ast.walk(tree):
        where = owner.get(id(node), "<module>")
        if isinstance(node, ast.Import):
            found += [(alias.name, "", where) for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                parts = package.split(".")
                base = parts[: len(parts) - node.level + 1]
                origin = ".".join(base + ([node.module] if node.module else []))
            else:
                origin = node.module or ""
            for alias in node.names:
                found.append((origin, alias.name, where))
    return found


def is_u8(name: str, modules: frozenset[str]) -> bool:
    return (any(part.startswith("u8_") for part in name.split("."))
            or name == OPERATIONS or name.startswith(OPERATIONS + ".")
            or name in modules or any(name.startswith(m + ".") for m in modules))


# --- 1. No U2-measured file imports a U8 module, but the three pinned ---------------------


def u8_imports(root: Path, files: list[str], modules: frozenset[str]) -> list[tuple]:
    found = []
    for name in files:
        for module, imported, where in imports(root, root / name):
            full = f"{module}.{imported}" if imported else module
            if (is_u8(module, modules) or is_u8(full, modules)) and (
                    name, where, module) not in PINNED:
                found.append((name, where, module))
    return found


def test_no_file_u2s_lane_measures_imports_a_u8_module_but_the_three_pinned():
    files = u2_files()
    assert len(files) == 44
    modules = u8_modules()
    assert {"backend.modules.accounts.u8_control_policy", "backend.modules.plans.u8_usage",
            "backend.u8_capacity", "docsuri_ops.arrangement.paths"} <= modules
    assert u8_imports(ROOT, files, modules) == []
    # The three pinned imports are still where they are pinned.
    present = {(name, where, module) for name in files
               for module, _, where in imports(ROOT, ROOT / name)}
    assert PINNED <= present


def test_the_import_scan_finds_a_planted_case(tmp_path):
    folder = tmp_path / "backend/modules/accounts"
    folder.mkdir(parents=True)
    planted = {
        "a.py": "from backend.modules.accounts.u8_entry import CompleteControlEntryService\n",
        "b.py": "def later():\n    from .u8_identity import ArrivalIdentityService\n",
        "c.py": "import backend.modules.operations.ledger\n",
        "d.py": "def for_realm(realm):\n    from .u8_control_policy import COMPLETE_POLICIES\n",
        "e.py": "from backend.local_profile import KEY_FOLDERS\n",
    }
    for name, source in planted.items():
        (folder / name).write_text(source)
    files = [f"backend/modules/accounts/{name}" for name in planted]
    found = {name for name, _, _ in u8_imports(tmp_path, files, frozenset())}
    assert found == {f"backend/modules/accounts/{name}.py" for name in "abcd"}


# --- 2. No U2-measured file defines or uses a moved name ------------------------------------


def moved_uses(root: Path, files: list[str]) -> list[tuple[str, str, str]]:
    found = []
    for name in files:
        tree = ast.parse((root / name).read_bytes(), name)
        owner = scopes(tree)
        for node in ast.walk(tree):
            where = owner.get(id(node), "<module>")
            used = None
            if isinstance(node, ast.Name) and node.id in ALL_MOVED:
                used = node.id
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and (
                    node.name in ALL_MOVED and owner.get(id(node)) == "<module>"):
                used = node.name
            elif isinstance(node, ast.alias) and node.name in ALL_MOVED:
                used = node.name
            if used is not None and (name, where, used) not in ALLOWED_USES:
                found.append((name, where, used))
    return found


def test_no_file_u2s_lane_measures_defines_or_uses_a_moved_name():
    assert moved_uses(ROOT, u2_files()) == []


def test_the_moved_name_scan_finds_a_planted_case(tmp_path):
    (tmp_path / "backend").mkdir()
    planted = {
        "a.py": "class CompletePolicy:\n    pass\n",
        "b.py": "def judge(x):\n    return CapacityBudget(x)\n",
        "c.py": "from backend.u8_profile import ProfileRefused\n",
        "d.py": "def for_realm(realm):\n    return COMPLETE_POLICIES[realm]\n",
        "e.py": "def capacity():\n    return 1\n",
    }
    for name, source in planted.items():
        (tmp_path / "backend" / name).write_text(source)
    found = {name for name, _, _ in moved_uses(
        tmp_path, [f"backend/{name}" for name in planted])}
    assert found == {"backend/a.py", "backend/b.py", "backend/c.py", "backend/d.py"}


# --- 3. No file imports a moved name from its old module -------------------------------------


def source_files(root: Path) -> list[Path]:
    """Every tracked or new Python file in `backend/`, `scripts/` and `ops/src/`."""
    import subprocess

    result = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard", "--",
         "backend", "scripts", "ops/src"],
        cwd=root, capture_output=True, text=True, check=True, timeout=60)
    return sorted(root / name for name in result.stdout.split("\0")
                  if name.endswith(".py") and (root / name).is_file())


def stale_imports(root: Path, paths: list[Path]) -> list[tuple[str, str, str]]:
    found = []
    for path in paths:
        try:
            listed = imports(root, path)
        except SyntaxError:
            continue
        for module, imported, _ in listed:
            if imported in MOVED.get(module, ()):
                found.append((str(path.relative_to(root)), module, imported))
    return found


def test_no_file_imports_a_moved_name_from_its_old_module():
    assert stale_imports(ROOT, source_files(ROOT)) == []


def test_the_stale_import_scan_finds_a_planted_case(tmp_path):
    folder = tmp_path / "backend"
    folder.mkdir()
    planted = {
        "a.py": "from backend.local_profile import ProductionProfile\n",
        "b.py": "def later():\n    from .control_runtime import CapacityRefresher\n",
        "c.py": "from backend.modules.plans.control_service import usage_for\n",
        "d.py": "from backend.u8_profile import ProductionProfile\n",
    }
    for name, source in planted.items():
        (folder / name).write_text(source)
    found = {path for path, _, _ in stale_imports(tmp_path, sorted(folder.glob("*.py")))}
    assert found == {"backend/a.py", "backend/b.py", "backend/c.py"}


# --- 4 and 5. What U8's own files build ------------------------------------------------------


def own_files(root: Path) -> list[str]:
    names = set()
    for pattern in U8_OWN_PATTERNS:
        names |= {str(path.relative_to(root)) for path in root.glob(pattern)}
    ops = {str(path.relative_to(root)) for pattern in u8_own_patterns()
           if pattern.startswith("ops/") for path in root.glob(pattern)}
    return sorted(names | ops)


def calls(root: Path, files: list[str], names: frozenset[str]) -> list[tuple[str, str, str]]:
    found = []
    for name in files:
        tree = ast.parse((root / name).read_bytes(), name)
        owner = scopes(tree)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                target = node.func
                called = target.id if isinstance(target, ast.Name) else (
                    target.attr if isinstance(target, ast.Attribute) else None)
                if called in names:
                    found.append((name, owner.get(id(node), "<module>"), called))
    return found


def test_u8s_own_files_build_u2s_control_classes_only_through_u8s():
    files = own_files(ROOT)
    assert "backend/u8_host.py" in files and "backend/modules/accounts/u8_entry.py" in files
    built = [item for item in calls(ROOT, files, U2_CLASSES) if item not in ALLOWED_BUILDS]
    assert built == []
    assert ALLOWED_BUILDS <= set(calls(ROOT, files, U2_CLASSES))


def test_each_usage_part_is_built_only_where_it_takes_u8s_usage():
    files = own_files(ROOT)
    sites = {(name, where) for name, where, _ in calls(ROOT, files, USAGE_PARTS)}
    assert sites == USAGE_SITES
    users = {(name, where) for name, where, _ in calls(
        ROOT, files, frozenset({"use_complete_usage"}))}
    assert USAGE_SITES <= users


# --- 6. No U2-measured file names a U8-only column -------------------------------------------

# Column or function -> the U8 migration that adds it.
U8_COLUMNS = {
    "client_address_digest": "backend/modules/accounts/u8_identity_flow_address.sql",
    "expire_identity_flows": "backend/modules/accounts/u8_identity_flow_starts.sql",
}


def u8_column_uses(root: Path, files: list[str]) -> list[tuple[str, str]]:
    """(file, column) for every string or name in a file that mentions a U8-only column."""
    found = []
    for name in files:
        for node in ast.walk(ast.parse((root / name).read_bytes(), name)):
            text = node.value if isinstance(node, ast.Constant) and isinstance(
                node.value, str) else (node.id if isinstance(node, ast.Name) else (
                    node.attr if isinstance(node, ast.Attribute) else None))
            if text is None:
                continue
            found += [(name, column) for column in U8_COLUMNS if column in text]
    return sorted(set(found))


def test_no_file_u2s_lane_measures_names_a_column_only_u8_adds():
    for column, migration in U8_COLUMNS.items():
        assert column in (ROOT / migration).read_text(), column
    assert u8_column_uses(ROOT, u2_files()) == []
    # Both are U8's: its own identity service writes and counts the column and calls the
    # deletion function.
    assert {("backend/modules/accounts/u8_identity.py", "client_address_digest"),
            ("backend/modules/accounts/u8_identity.py", "expire_identity_flows")} <= set(
        u8_column_uses(ROOT, ["backend/modules/accounts/u8_identity.py"]))


def test_the_column_scan_finds_a_planted_case(tmp_path):
    (tmp_path / "backend").mkdir()
    planted = {
        "a.py": "Q = 'SELECT client_address_digest FROM accounts.identity_flow'\n",
        "b.py": "def f(row):\n    return row.client_address_digest\n",
        "c.py": "Q = 'SELECT state_hash FROM accounts.identity_flow'\n",
    }
    for name, source in planted.items():
        (tmp_path / "backend" / name).write_text(source)
    found = {name for name, _ in u8_column_uses(
        tmp_path, [f"backend/{name}" for name in planted])}
    assert found == {"backend/a.py", "backend/b.py"}


def test_the_build_scans_find_a_planted_case(tmp_path):
    (tmp_path / "backend").mkdir()
    (tmp_path / "backend/u8_planted.py").write_text(
        "def compose(t):\n    return ControlEntryService(t, None)\n"
        "def corpus(t):\n    return AssistanceDispatch(t, None, None)\n")
    found = calls(tmp_path, ["backend/u8_planted.py"], U2_CLASSES | USAGE_PARTS)
    assert ("backend/u8_planted.py", "compose", "ControlEntryService") in found
    assert ("backend/u8_planted.py", "corpus", "AssistanceDispatch") in found
    assert fnmatch.fnmatch("backend/u8_planted.py", U8_OWN_PATTERNS[0])
