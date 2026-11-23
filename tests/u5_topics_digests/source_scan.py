"""U5's production modules and two parsed-source scans over them.

The modules are the backend files U5's coverage report measures
(`backend/.coveragerc.u5`): U5's own and the shared ones it changed. The report's
scripts are left out: they are the operator and verification tools, whose standard
output is their interface. Both scans parse the source, so a name that merely contains
`print` (`preference_fingerprint`) or a docstring that mentions a variable is not a hit.
"""

from __future__ import annotations

import ast
import configparser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COVERAGE_RC = ROOT / "backend/.coveragerc.u5"
LOGGERS = frozenset({"logging", "loguru", "structlog"})
PROVIDER_VARIABLES = frozenset({"EMAIL_PROVIDER", "RESEND_API_KEY"})


def production_modules(rc: Path = COVERAGE_RC) -> list[Path]:
    parser = configparser.ConfigParser()
    parser.read(rc)
    patterns = [line.strip() for line in parser["report"]["include"].splitlines() if line.strip()]
    return sorted(
        {path for pattern in patterns if pattern.startswith("backend/") for path in ROOT.glob(pattern)}
    )


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def logging_uses(source: str, name: str = "<source>") -> list[str]:
    """Each logging import, logger factory, `print` call or standard-stream use."""
    found = []
    for node in ast.walk(ast.parse(source, name)):
        if isinstance(node, ast.Import):
            found += [f"import {alias.name}" for alias in node.names
                      if alias.name.split(".")[0] in LOGGERS]
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module and node.module.split(".")[0] in LOGGERS:
                found.append(f"from {node.module} import")
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id == "print":
                found.append("print()")
        elif isinstance(node, ast.Attribute):
            if node.attr == "getLogger":
                found.append("getLogger")
            elif (
                node.attr in ("stdout", "stderr")
                and isinstance(node.value, ast.Name)
                and node.value.id == "sys"
            ):
                found.append(f"sys.{node.attr}")
    return found


class _EnvironmentReads(ast.NodeVisitor):
    def __init__(self):
        self.scope, self.found = ["<module>"], []

    def visit_FunctionDef(self, node):
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ImportFrom(self, node):
        if node.module == "os":
            self.found += [(self.scope[-1], f"from os import {alias.name}")
                           for alias in node.names if alias.name in ("environ", "getenv")]
        self.generic_visit(node)

    def visit_Attribute(self, node):
        if (
            isinstance(node.value, ast.Name)
            and node.value.id == "os"
            and node.attr in ("environ", "environb", "getenv")
        ):
            self.found.append((self.scope[-1], f"os.{node.attr}"))
        self.generic_visit(node)

    def visit_Constant(self, node):
        if node.value in PROVIDER_VARIABLES:
            self.found.append((self.scope[-1], node.value))


def environment_reads(source: str, name: str = "<source>") -> list[tuple[str, str]]:
    """(enclosing function, read) for each process-environment access or provider
    variable name used as a whole string."""
    visitor = _EnvironmentReads()
    visitor.visit(ast.parse(source, name))
    return visitor.found
