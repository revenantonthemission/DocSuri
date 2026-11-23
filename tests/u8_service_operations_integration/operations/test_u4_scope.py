"""U4's coverage lane measures no U8 code, and U4's own research files are as built (U8
plan Step 22; your decision of 2026-10-24, "Build the research executor").

- No file in `.coveragerc.u4`'s include list imports a U8 module: a module listed under
  `.coveragerc.u8`'s "U8's own backend files", any module with a `u8_` segment, or
  `backend.modules.operations`. The scan parses the source and finds a planted case.
- `backend/u4_policy.py`, `backend/u4_host.py`, `backend/.coveragerc.u4` and
  `backend/modules/research/evidence.py`, `execution.py`, `jobs.py` and `service.py`
  hold exactly their built bytes: each is compared with its SHA-256 pinned at the branch
  base (`built_files`), never with `HEAD`, which in CI already holds every change.
  By your decision of 2026-10-24 ("Move, scope tools, test U2"), `execution.py` is back
  to its built text: the complete realms' usage authority is set by U8's builders
  (`backend/modules/plans/u8_usage.use_complete_usage`).
- U4's phases pass with its coverage phase at or above 80% (U4's own tool, whose
  coverage phase judges `.coveragerc.u4`'s floor; Step 22's runs).
"""

from __future__ import annotations

import ast
from pathlib import Path

from tests.u8_service_operations_integration.built_files import changed_from_built

ROOT = Path(__file__).resolve().parents[3]
U4_RC = ROOT / "backend/.coveragerc.u4"
U8_RC = ROOT / "backend/.coveragerc.u8"
OPERATIONS = "backend.modules.operations"
U4_UNCHANGED = (
    "backend/u4_policy.py", "backend/u4_host.py", "backend/modules/research/evidence.py",
    "backend/modules/research/execution.py", "backend/modules/research/jobs.py",
    "backend/modules/research/service.py",
)


def includes(rc: Path) -> list[str]:
    patterns, inside = [], False
    for line in rc.read_text().splitlines():
        if line.startswith("include"):
            inside = True
            continue
        if not inside:
            continue
        if line and not line[0].isspace():
            break
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            patterns.append(stripped)
    return patterns


def u8_own(rc: Path) -> list[str]:
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


def is_u8(name: str, modules: frozenset[str]) -> bool:
    return (any(part.startswith("u8_") for part in name.split("."))
            or name == OPERATIONS or name.startswith(OPERATIONS + ".")
            or name in modules or any(name.startswith(m + ".") for m in modules))


def u8_imports(root: Path, files: list[Path], modules: frozenset[str]) -> dict[str, list]:
    found = {}
    for path in files:
        names = sorted(name for name in imported(root, path) if is_u8(name, modules))
        if names:
            found[str(path.relative_to(root))] = names
    return found


def u8_modules() -> frozenset[str]:
    return frozenset(module_of(ROOT, path) for path in expand(ROOT, u8_own(U8_RC)))


def test_no_file_u4s_lane_measures_imports_a_u8_module():
    files = expand(ROOT, includes(U4_RC))
    assert ROOT / "backend/modules/research/execution.py" in files
    assert ROOT / "backend/modules/research/job_list.py" in files
    assert len(files) > 15  # the include list was really expanded
    # ResearchWorkspace's own new files (`job_list.py`, `control_lifecycle.py`) are U4's,
    # measured in U4's lane, so they are not U8 modules here.
    modules = u8_modules() - {module_of(ROOT, path) for path in files}
    assert {"backend.u8_research", "backend.u8_research_model", "backend.u8_model_lane",
            "backend.modules.summarization.u8_assistance_sources"} <= modules
    assert "backend.modules.research.job_list" not in modules
    assert u8_imports(ROOT, files, modules) == {}


def test_the_scan_finds_a_planted_u8_import(tmp_path):
    folder = tmp_path / "backend/modules/research"
    folder.mkdir(parents=True)
    planted = {
        "a.py": "from backend.u8_research import PRODUCTION_RESEARCH\n",
        "b.py": "def later():\n    from ..operations.incidents import Incidents\n",
        "c.py": "import backend.u8_model_lane\n",
        "d.py": "from backend.modules.summarization import model_runtime\n",
        "e.py": "from backend.u4_policy import SYNTHETIC_RESEARCH\nfrom .jobs import x\n",
    }
    for name, source in planted.items():
        (folder / name).write_text(source)
    modules = frozenset({"backend.modules.summarization.model_runtime"})
    found = u8_imports(tmp_path, sorted(folder.glob("*.py")), modules)
    assert set(found) == {f"backend/modules/research/{name}.py" for name in "abcd"}


def test_u4s_policy_host_and_four_research_files_are_their_built_text():
    assert changed_from_built(U4_UNCHANGED) == {}
    assert changed_from_built(["backend/.coveragerc.u4"]) == {}
