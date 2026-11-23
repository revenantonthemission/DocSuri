"""Every file the macOS report measures is imported by an arrangement test (U8 plan Step
98(f)).

`backend/.coveragerc.u8-macos` includes exactly the three macOS adapters, with
`fail_under = 80`; an AST scan of `tests/u8_service_operations_integration/arrangement`
finds an import of each; and `backend/.coveragerc.u8` omits exactly those three and
`scripts/verify_docsuri_u8.py`, so each file sits in one of the two U8 reports. The
arrangement folder runs as root in CI's `macos-filesystem` job (Step 103(c)); this check
reads its sources only.
"""

from __future__ import annotations

import ast
import configparser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ARRANGEMENT = "tests/u8_service_operations_integration/arrangement"
MACOS_RC = "backend/.coveragerc.u8-macos"
U8_RC = "backend/.coveragerc.u8"
SOURCE_ROOT = "ops/src/"
ADAPTERS = (
    "ops/src/docsuri_ops/arrangement/macos.py",
    "ops/src/docsuri_ops/standing/macos.py",
    "ops/src/docsuri_ops/isolation_macos.py",
)


def listed(text: str, section: str, option: str) -> list[str]:
    parser = configparser.ConfigParser()
    parser.read_string(text)
    return [line.strip() for line in parser.get(section, option).splitlines() if line.strip()]


def module_of(path: str) -> str:
    """`ops/src/docsuri_ops/standing/macos.py` → `docsuri_ops.standing.macos`."""
    return path.removeprefix(SOURCE_ROOT).removesuffix(".py").replace("/", ".")


def imported_modules(source: str) -> set[str]:
    """Every module an import statement may name: `import a.b`, and for `from a import b`
    both `a` and `a.b`."""
    found: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            found |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            found.add(node.module)
            found |= {f"{node.module}.{alias.name}" for alias in node.names}
    return found


def scope_problems(includes: list[str], sources: dict[str, str]) -> list[str]:
    """Each included file no arrangement test imports."""
    imported = set().union(*(imported_modules(text) for text in sources.values()))
    return [f"{path}: no arrangement test imports {module_of(path)}"
            for path in includes if module_of(path) not in imported]


def arrangement_sources(root: Path = ROOT) -> dict[str, str]:
    return {path.name: path.read_text(encoding="utf-8")
            for path in sorted((root / ARRANGEMENT).glob("test_*.py"))}


def test_every_file_the_macos_report_measures_is_imported_by_an_arrangement_test():
    macos = (ROOT / MACOS_RC).read_text(encoding="utf-8")
    includes = listed(macos, "report", "include")
    assert includes == list(ADAPTERS)
    parser = configparser.ConfigParser()
    parser.read_string(macos)
    assert parser.getint("report", "fail_under") == 80
    sources = arrangement_sources()
    assert scope_problems(includes, sources) == []
    # Each file is in exactly one of the two reports.
    omitted = listed((ROOT / U8_RC).read_text(encoding="utf-8"), "report", "omit")
    assert sorted(omitted) == sorted([*ADAPTERS, "scripts/verify_docsuri_u8.py"])
    # A planted include with no importing test, checked in memory, fails.
    planted = [*includes, "ops/src/docsuri_ops/planted_macos.py"]
    assert scope_problems(planted, sources) == [
        "ops/src/docsuri_ops/planted_macos.py: no arrangement test imports "
        "docsuri_ops.planted_macos"]
    # So does a test folder that loses its only import of one adapter.
    without = {name: text.replace("from docsuri_ops import isolation_macos\n", "")
               .replace("from docsuri_ops.isolation_macos import MacTools\n", "")
               for name, text in sources.items()}
    assert scope_problems(includes, without) == [
        "ops/src/docsuri_ops/isolation_macos.py: no arrangement test imports "
        "docsuri_ops.isolation_macos"]
