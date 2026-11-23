"""AccountAccess, TopicsDigests and TopicsDigests' live work never import ServiceOperations
(U8 plan Steps 14 and 22; security-design § 13 and § 15 "Email allowance (D12)" item 6)."""

from __future__ import annotations

import ast
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from backend import u8_registry
from backend.u8_host import compose
from backend.u8_registry import (
    PORT_OWNERS,
    ManifestRefused,
    import_boundary_violations,
    verify_import_boundaries,
)

ROOT = Path(__file__).resolve().parents[3]


def owner_files(root: Path) -> list[Path]:
    files = []
    for entry in PORT_OWNERS:
        place = root / entry
        files.extend([place] if entry.endswith(".py") else place.rglob("*.py"))
    return files


def tree_with(tmp_path: Path, relative: str, source: str, *, append: bool = False) -> Path:
    """A copy of the port owners' modules with one more file, or one file extended."""
    root = tmp_path / "release"
    for entry in PORT_OWNERS:
        target = root / entry
        if entry.endswith(".py"):
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / entry, target)
        else:
            shutil.copytree(ROOT / entry, target, ignore=shutil.ignore_patterns("__pycache__"))
    path = root / relative
    if append:
        with path.open("a") as stream:
            stream.write(source)
        return root
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        stream.write(source)
    return root


def test_no_module_of_accounts_or_topics_imports_service_operations():
    assert import_boundary_violations(ROOT) == []
    files = owner_files(ROOT)
    assert len(files) > 20  # every owner tree was really scanned
    assert ROOT / "backend/u8_topics.py" in files
    verify_import_boundaries(ROOT)


@pytest.mark.parametrize("source", [
    "from backend.modules.operations.allowance import LedgerAllowance\n",
    "import backend.modules.operations.ledger\n",
    "from backend.modules import operations\n",
    "from ...operations import allowance\n",
    "import importlib\nimportlib.import_module('backend.modules.operations.ledger')\n",
])
def test_each_form_of_import_is_found(tmp_path, source):
    relative = "backend/modules/accounts/integrations/leaky.py"
    root = tree_with(tmp_path, relative, source)
    assert import_boundary_violations(root) == [relative]


def test_a_topics_module_importing_it_fails_the_complete_assemblys_check(tmp_path):
    relative = "backend/modules/topics/leaky.py"
    root = tree_with(tmp_path, relative, "from ..operations.ledger import Ledger\n")
    with pytest.raises(ManifestRefused) as raised:
        verify_import_boundaries(root)
    assert relative in str(raised.value)
    # compose runs the check before it looks at the profile at all.
    with pytest.raises(ManifestRefused):
        compose(object(), release_root=root)


def test_a_service_operations_import_planted_in_u8_topics_is_found(tmp_path):
    relative = "backend/u8_topics.py"
    root = tree_with(tmp_path, relative,
                     "\nfrom backend.modules.operations.allowance import LedgerAllowance\n",
                     append=True)
    assert import_boundary_violations(root) == [relative]
    with pytest.raises(ManifestRefused, match="u8_topics"):
        verify_import_boundaries(root)


def test_the_check_names_its_six_entries():
    assert PORT_OWNERS == (
        "backend/modules/accounts", "backend/modules/topics", "backend/u8_topics.py",
        "backend/u8_research.py", "backend/u8_research_model.py", "backend/u8_model_lane.py",
    )
    assert u8_registry.OPERATIONS_MODULE == "backend.modules.operations"


@pytest.mark.parametrize("relative", [
    "backend/u8_research.py", "backend/u8_research_model.py", "backend/u8_model_lane.py",
])
def test_a_service_operations_import_planted_in_a_research_module_is_found(tmp_path, relative):
    root = tree_with(tmp_path, relative,
                     "\nfrom backend.modules.operations.incidents import Incidents\n",
                     append=True)
    assert import_boundary_violations(root) == [relative]
    with pytest.raises(ManifestRefused, match=relative.split("/")[-1].removesuffix(".py")):
        verify_import_boundaries(root)


# --- the ledger's standard-library rule (L1-32, Step 97(h)) ------------------------------------

LEDGER_FILES = ("ledger", "ledger_records", "errors", "tombstones")


def imported_modules(path: Path) -> list[tuple[int, str]]:
    """Every import in a file, at module level and inside functions: (level, module) for
    each name an `import` or `from ... import` names."""
    found = []
    for node in ast.walk(ast.parse(path.read_text(), filename=str(path))):
        if isinstance(node, ast.Import):
            found.extend((0, alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            found.append((node.level, node.module or ""))
    return found


def test_the_ledger_imports_only_the_standard_library():
    folder = ROOT / "backend/modules/operations"
    for name in LEDGER_FILES:
        imports = imported_modules(folder / f"{name}.py")
        assert imports, name
        for level, module in imports:
            if level:
                # A relative import names one of the four files.
                assert level == 1 and module in LEDGER_FILES, (name, module)
            else:
                top = module.split(".")[0]
                assert top in sys.stdlib_module_names or top == "rfc8785", (name, module)
    # The ledger CLI on import adds only standard-library modules, `backend.*` and
    # `rfc8785` to a bare interpreter's start; its function-level imports (the
    # production command's wiring, reaching `backend.u8_profile` and
    # `docsuri_ops.u8_platform`) do not run on import.
    probe = ("import json, sys\n"
             f"sys.path.insert(0, {str(ROOT)!r})\n"
             "before = set(sys.modules)\n"
             "import backend.modules.operations.ledger_cli\n"
             "print(json.dumps(sorted(set(sys.modules) - before)))\n")
    completed = subprocess.run([sys.executable, "-I", "-c", probe], capture_output=True,
                               text=True, timeout=60, check=True, cwd=ROOT)
    added = json.loads(completed.stdout)
    assert "backend.modules.operations.ledger_cli" in added
    for module in added:
        top = module.split(".")[0]
        assert top in sys.stdlib_module_names or top in {"backend", "rfc8785"}, module
    assert not any(module.startswith(("backend.u8_profile", "docsuri_ops"))
                   for module in added)


def test_the_canonical_json_dependency_is_locked_and_hash_checked():
    import tomllib

    pyproject = tomllib.loads((ROOT / "backend/pyproject.toml").read_text())
    assert "rfc8785==0.1.4" in pyproject["project"]["dependencies"]
    lock = tomllib.loads((ROOT / "backend/uv.lock").read_text())
    (entry,) = [item for item in lock["package"] if item["name"] == "rfc8785"]
    assert entry["version"] == "0.1.4"
    assert entry["sdist"]["hash"] == (
        "sha256:e545841329fe0eee4f6a3b44e7034343100c12b4ec566dc06ca9735681deb4da")
    assert [wheel["hash"] for wheel in entry["wheels"]] == [
        "sha256:520d690b448ecf0703691c76e1a34a24ddcd4fc5bc41d589cb7c58ec651bcd48"]
