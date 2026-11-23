"""U6's export lane, service and binding import no U8 code (U8 plan Step 52(h); L1-6).

`backend/modules/export/lane.py` gained one per-item hook, `ExportLane.item_hook`, which
U8's composition sets to `u8_job_lines.ExportItemLines`; the lane itself, with
`service.py` and `binding.py`, imports no module with a `u8_` segment and nothing from
`backend.modules.operations`. The scan parses the source, lazy imports included, and is
shown to find a planted case.
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OPERATIONS = "backend.modules.operations"
EXPORT = "backend/modules/export/"
SCANNED = tuple(f"{EXPORT}{name}" for name in ("lane.py", "service.py", "binding.py"))


def violations(root: Path, relative: tuple[str, ...]) -> dict[str, list[str]]:
    """Each file's imported names that are U8 modules or ServiceOperations."""
    found = {}
    for name in relative:
        package = ".".join(Path(name).with_suffix("").parts[:-1])
        names: set[str] = set()
        for node in ast.walk(ast.parse((root / name).read_bytes(), name)):
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


def test_u6s_lane_service_and_binding_import_no_u8_module():
    assert all((ROOT / name).is_file() for name in SCANNED)
    assert violations(ROOT, SCANNED) == {}


def test_the_scan_finds_a_planted_case(tmp_path):
    folder = tmp_path / "backend/modules/export"
    folder.mkdir(parents=True)
    (folder / "lane.py").write_text("def later():\n    from backend.u8_job_lines import x\n")
    (folder / "service.py").write_text("from ..operations import ledger\n")
    (folder / "binding.py").write_text("from .lane_store import ClaimRefused\n")
    found = violations(tmp_path, SCANNED)
    assert set(found) == {f"{EXPORT}lane.py", f"{EXPORT}service.py"}
    assert found[f"{EXPORT}lane.py"] == ["backend.u8_job_lines", "backend.u8_job_lines.x"]
    assert found[f"{EXPORT}service.py"] == ["backend.modules.operations",
                                            "backend.modules.operations.ledger"]
