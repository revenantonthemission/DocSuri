"""U3's coverage lane measures no U8 code in PaperAssistance (U8 plan Step 24; your
decision of 2026-10-24, "Fix it in U8").

- `backend/modules/summarization/u3_catalog.py`, `u3_dispatch.py` and `u3_http.py`, the
  PaperAssistance files `.coveragerc.u3` measures, import no module with a `u8_` segment
  and no `backend.modules.operations`; they hold only the seams whose default is U3's
  built 256-chunk, unique-anchor rule, `AssistanceDispatch`'s per-item hook `_item`,
  which does nothing until U8's `CompleteAssistanceDispatch` overrides it (U8 plan Step
  51(d), L1-6), and the assistance history read's two seams (U8 plan Step 83(b), L1-8):
  `assistance_router`'s `history_bound` and `history_in_one_read`, with
  `GuardedAssistanceRepository.history`'s `bound` and `with_metadata`, whose defaults
  keep U3's built 100 rows and one metadata read per row. The scan parses the source and
  finds a planted case.
- `.coveragerc.u3` holds exactly its built bytes: it is compared with its SHA-256 pinned
  at the branch base (`built_files`), never with `HEAD`, which in CI already holds every
  change.
"""

from __future__ import annotations

import ast
from pathlib import Path

from tests.u8_service_operations_integration.built_files import changed_from_built

ROOT = Path(__file__).resolve().parents[3]
U3_RC = ROOT / "backend/.coveragerc.u3"
OPERATIONS = "backend.modules.operations"
SUMMARIZATION = "backend/modules/summarization/"


def measured_assistance(rc: Path) -> list[str]:
    """The PaperAssistance files the U3 report includes."""
    found, inside = [], False
    for line in rc.read_text().splitlines():
        if line.startswith("include"):
            inside = True
            continue
        if inside and line and not line[0].isspace():
            break
        stripped = line.strip()
        if inside and stripped.startswith(SUMMARIZATION):
            found.append(stripped)
    return found


def violations(root: Path, relative: list[str]) -> dict[str, list[str]]:
    found = {}
    for name in relative:
        path = root / name
        package = ".".join(Path(name).with_suffix("").parts[:-1])
        names: set[str] = set()
        for node in ast.walk(ast.parse(path.read_bytes(), name)):
            if isinstance(node, ast.Import):
                names.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    parts = package.split(".")
                    origin = ".".join(parts[: len(parts) - node.level + 1]
                                      + ([node.module] if node.module else []))
                else:
                    origin = node.module or ""
                names.add(origin)
                names.update(f"{origin}.{alias.name}" for alias in node.names)
        bad = sorted(item for item in names
                     if any(part.startswith("u8_") for part in item.split("."))
                     or item == OPERATIONS or item.startswith(OPERATIONS + "."))
        if bad:
            found[name] = bad
    return found


def test_the_three_measured_assistance_files_import_no_u8_module():
    measured = measured_assistance(U3_RC)
    assert {f"{SUMMARIZATION}{name}" for name in (
        "u3_catalog.py", "u3_dispatch.py", "u3_http.py")} <= set(measured)
    assert violations(ROOT, measured) == {}


def test_the_scan_finds_a_planted_case(tmp_path):
    folder = tmp_path / "backend/modules/summarization"
    folder.mkdir(parents=True)
    (folder / "u3_catalog.py").write_text(
        "from backend.modules.summarization.u8_assistance_sources import blocks\n")
    (folder / "u3_dispatch.py").write_text(
        "def later():\n    from ..operations import ledger\n")
    (folder / "u3_http.py").write_text("from .payload import SelectionRule\n")
    found = violations(tmp_path, [f"{SUMMARIZATION}{name}" for name in (
        "u3_catalog.py", "u3_dispatch.py", "u3_http.py")])
    assert set(found) == {f"{SUMMARIZATION}u3_catalog.py", f"{SUMMARIZATION}u3_dispatch.py"}


def test_the_u3_coverage_configuration_is_unchanged():
    assert changed_from_built(["backend/.coveragerc.u3"]) == {}
