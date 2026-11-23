"""Earlier assemblies keep booting on their own (U8 plan Step 12; BR1.7).

Test 2 builds each earlier assembly from a profile of its own realm in a fresh
interpreter and checks that no U8 module was loaded at any point. This environment holds
none of those realms (and U6's checkpoint realm must not be touched), so each build runs
up to its first owner connection, which the profile's empty root refuses: every import
and every realm gate of the build path has run by then. Their own runners build them in
full in their own realms.
"""

from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from backend.u3_host import assemble_u3
from backend.u4_host import assemble_u4
from backend.u5_host import assemble_u5
from backend.u6_host import assemble_u6

ROOT = Path(__file__).resolve().parents[3]
EARLIER_HOSTS = (
    "backend/local_host.py", "backend/u3_host.py", "backend/u4_host.py", "backend/u5_host.py",
    "backend/u6_host.py",
)
# The modules only the complete assembly may load: any module with a `u8_` segment (U8's
# own modules, wherever they sit), ServiceOperations, and U8's three host modules.
U8_PREFIXES = ("backend.modules.operations",)
U8_MODULES = ("backend.production_boundary", "backend.request_context", "backend.log_events")


def imported_modules(path: Path, package: str | None = None) -> set[str]:
    """Every module a file imports, at any depth, with relative imports resolved."""
    tree = ast.parse(path.read_text(), filename=str(path))
    if package is None:
        package = ".".join(path.relative_to(ROOT).with_suffix("").parts[:-1])
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = package.split(".")
                base = base[: len(base) - node.level + 1]
                module = ".".join([*base, node.module] if node.module else base)
            else:
                module = node.module or ""
            names.add(module)
            names.update(f"{module}.{alias.name}" for alias in node.names)
    return names


def is_u8(name: str) -> bool:
    return (
        any(part.startswith("u8_") for part in name.split("."))
        or name.startswith(U8_PREFIXES)
        or name in U8_MODULES
    )


@pytest.mark.parametrize("path", EARLIER_HOSTS)
def test_an_earlier_host_imports_no_u8_module(path):
    names = imported_modules(ROOT / path)
    assert names, path
    assert not sorted(name for name in names if is_u8(name))


def test_the_import_graph_check_finds_a_u8_import(tmp_path):
    """The check itself is not vacuous: a planted import is found."""
    planted = tmp_path / "probe.py"
    planted.write_text(
        "import json\nfrom .u8_host import compose\nfrom .modules.operations import ledger\n"
        "def later():\n    from backend.log_events import log_event\n"
        "from .modules.accounts.integrations.u8_digest_mail import HeldDigestMail\n"
    )
    found = {name for name in imported_modules(planted, "backend") if is_u8(name)}
    assert {"backend.u8_host", "backend.modules.operations", "backend.log_events",
            "backend.modules.accounts.integrations.u8_digest_mail"} <= found
    assert "json" not in found


BUILD = r"""
import dataclasses, json, sys, tempfile
from pathlib import Path
from backend.local_profile import LocalProfile

root = Path(tempfile.mkdtemp())
realms = {
    "u1": ("https://127.0.0.1:18039", 15439, "docsuri_u1_journey", "journey"),
    "u2": ("https://127.0.0.1:18049", 15449, "docsuri_u2", "account-controls"),
    "u3": ("https://127.0.0.1:18059", 15459, "docsuri_u3", "corpus-maintenance"),
    "u4": ("https://127.0.0.1:18079", 15479, "docsuri_u4", "research-workspace"),
    "u5": ("https://127.0.0.1:18089", 15489, "docsuri_u5", "topics-digests"),
    "u6": ("https://127.0.0.1:18099", 15499, "docsuri_u6", "approved-export"),
}
unit = sys.argv[1]
origin, port, database, realm = realms[unit]
profile = LocalProfile(root, "docsuri-%s-0000000000000000" % unit, origin, port, 4102444800.0,
                       database, realm)
if unit in ("u1", "u2"):
    from backend.local_host import assemble_journey as build
else:
    module = __import__("backend.%s_host" % unit, fromlist=["x"])
    build = getattr(module, "assemble_%s" % unit)
try:
    build(profile)
    outcome = "built"
except FileNotFoundError:
    outcome = "stopped-at-owner-connection"
loaded = sorted(name for name in sys.modules
                if any(part.startswith("u8_") for part in name.split("."))
                or name.startswith("backend.modules.operations")
                or name in ("backend.production_boundary", "backend.request_context",
                            "backend.log_events"))
print(json.dumps({"outcome": outcome, "u8": loaded}))
"""


@pytest.mark.parametrize("unit", ["u1", "u2", "u3", "u4", "u5", "u6"])
def test_each_earlier_assembly_is_built_with_no_u8_module_loaded(unit):
    result = subprocess.run(
        [sys.executable, "-c", BUILD, unit], cwd=ROOT, capture_output=True, text=True,
        timeout=120,
        env={**os.environ, "PYTHONPATH": os.pathsep.join(
            [str(ROOT), str(ROOT / "ops/src"), str(ROOT / "ingestion/src")]
        )},
    )
    assert result.returncode == 0, result.stderr[-2000:]
    value = json.loads(result.stdout.splitlines()[-1])
    assert value == {"outcome": "stopped-at-owner-connection", "u8": []}


@pytest.mark.parametrize("build", [assemble_u3, assemble_u4, assemble_u5, assemble_u6])
def test_assemble_u3s_gates_still_refuse_the_u8_realm(realm, build, monkeypatch):
    from backend import transactions

    def never(*args, **kwargs):
        raise AssertionError("a gate let the U8 realm reach its owners")

    monkeypatch.setattr(transactions, "OwnerTransactions", never)
    with pytest.raises(ValueError, match="realm"):
        build(realm)
