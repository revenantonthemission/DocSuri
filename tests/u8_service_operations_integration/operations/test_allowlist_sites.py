"""The completeness test of decision "Allowlist sites" (U8 plan Step 12).

Every Python file in `backend/` and `ops/src/`, outside U8's own new files, is scanned.
A file that names the U6 environment must also name the U8 one. Names are matched
exactly, on the file's string literals and identifiers, never as loose substrings:
`"approved-export"` must be a whole literal (so `execute-approved-export` and a plan
path are not hits), and the unit key is the whole literal `"u6"`. The addresses
`127.0.0.1:18099` and `/tmp/docsuri-u6-run` match inside a literal, as in an origin.

`backend/u3_host.py`'s contribution gates are the one exception: the complete assembly
never calls `assemble_u3`, so those gates keep refusing the U8 realm
(`test_assemblies_alone.py` proves it).
"""

from __future__ import annotations

import ast
import fnmatch
import io
import subprocess
import tokenize
from pathlib import Path

import pytest

from backend import local_profile

ROOT = Path(__file__).resolve().parents[3]
U6_LITERALS = frozenset({"approved-export", "docsuri_u6", "u6", "/tmp/docsuri-u6-run"})
U6_ADDRESSES = ("127.0.0.1:18099", "/tmp/docsuri-u6-run")
U6_NAMES = frozenset({"EXPORT_ORIGIN"})
U8_LITERALS = frozenset({"service-operations", "docsuri_u8", "u8", "/tmp/docsuri-u8-run"})
U8_ADDRESSES = ("127.0.0.1:18110", "127.0.0.1:18109", "/tmp/docsuri-u8-run")
U8_NAMES = frozenset({"COMPLETE_ORIGIN", "COMPLETE_REALMS"})
EXCEPTIONS = frozenset({"backend/u3_host.py"})
# U8's own new files: they name both environments by design and are not allowlist sites.
U8_OWN = (
    "backend/u8_*.py", "backend/production_boundary.py", "backend/request_context.py",
    "backend/log_events.py", "backend/maintenance_server.py", "backend/import_parity.py",
    "backend/modules/operations/*", "backend/modules/*/u8_*.py",
    "backend/modules/accounts/entry_limits.py", "backend/modules/accounts/repository/imports.py",
    "backend/modules/library/repository/imports.py",
    "backend/modules/personalization/import_repository.py",
    "backend/modules/research/job_list.py",
    "ops/src/docsuri_ops/u8_*", "ops/src/docsuri_ops/arrangement/*",
    "ops/src/docsuri_ops/backup_agent/*", "ops/src/docsuri_ops/standing/*",
    "ops/src/docsuri_ops/migration/*", "ops/src/docsuri_ops/cutover/*",
)
# The allowlist sites of rows 1-9 (row 10 is the frontend's Playwright configuration).
SITES = frozenset({
    "backend/local_profile.py", "backend/local_browser.py", "backend/local_host.py",
    "backend/transactions.py", "backend/artifacts.py",
    "backend/modules/accounts/local_http.py",
    "backend/modules/accounts/services/guarded_entry.py",
    "backend/modules/personalization/guarded_service.py",
    "ops/src/docsuri_ops/local_transport.py",
})


def listed() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard", "--",
         "backend", "ops/src"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    )
    return sorted(
        name for name in result.stdout.split("\0")
        if name.endswith(".py") and (ROOT / name).is_file()
    )


def own(name: str) -> bool:
    return any(fnmatch.fnmatch(name, pattern) for pattern in U8_OWN)


def tokens(source: str) -> tuple[list[str], set[str]]:
    """(string literal values, identifiers) of one file."""
    literals, identifiers = [], set()
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type == tokenize.STRING:
            try:
                value = ast.literal_eval(token.string)
            except (ValueError, SyntaxError):
                # An f-string: its constant parts are what it names.
                value = token.string
            if isinstance(value, bytes):
                value = value.decode("latin-1")
            if isinstance(value, str):
                literals.append(value)
        elif getattr(tokenize, "FSTRING_MIDDLE", None) == token.type:
            literals.append(token.string)
        elif token.type == tokenize.NAME:
            identifiers.add(token.string)
    return literals, identifiers


def names(source: str, exact, addresses, identifiers) -> bool:
    literals, found = tokens(source)
    return (
        any(value in exact or any(item in value for item in addresses) for value in literals)
        or bool(found & identifiers)
    )


def names_u6(source: str) -> bool:
    return names(source, U6_LITERALS, U6_ADDRESSES, U6_NAMES)


def names_u8(source: str) -> bool:
    return names(source, U8_LITERALS, U8_ADDRESSES, U8_NAMES)


def test_every_file_that_names_the_u6_environment_names_the_u8_one():
    hits, missing = set(), []
    for name in listed():
        if own(name):
            continue
        source = (ROOT / name).read_text()
        if not names_u6(source):
            continue
        hits.add(name)
        if name not in EXCEPTIONS and not names_u8(source):
            missing.append(name)
    assert missing == []
    # The scan finds exactly the allowlist sites and the one exception, so a new site
    # that names U6 must be added here deliberately.
    assert hits == SITES | EXCEPTIONS


def test_matching_is_exact_not_a_loose_substring():
    assert not names_u6('ROUTE = "/api/v2/c09/execute-approved-export"\n')
    assert not names_u6('"""See construction/u6-approved-export/code-generation/plan.md."""\n')
    assert not names_u6('unit = "u60"\n')
    assert names_u6('REALM = "approved-export"\n')
    assert names_u6('ORIGIN = "https://127.0.0.1:18099"\n')
    assert names_u6('UNITS = ("u5", "u6")\n')
    assert names_u6("from backend.local_browser import EXPORT_ORIGIN\n")
    assert names_u8('x = f"https://127.0.0.1:18110/{path}"\n')
    assert not names_u8('x = "u80"\n')


def test_the_u3_gates_are_the_only_exception_and_still_name_only_u6():
    source = (ROOT / "backend/u3_host.py").read_text()
    assert names_u6(source) and not names_u8(source)


@pytest.mark.parametrize("site", sorted(SITES))
def test_each_site_names_the_composed_realm(site):
    assert names_u8((ROOT / site).read_text()), site


def test_the_public_origins_hold_only_the_composed_realm():
    """Pinned: only U8 has a public stand-in; U1 to U6 resolve to their own application
    port, so a later entry cannot move another unit's origin."""
    assert local_profile.PUBLIC_ORIGINS == {"u8": "https://127.0.0.1:18110"}
    assert {unit: local_profile.public_origin(unit) for unit in ("u2", "u3", "u4", "u5", "u6")} == {
        "u2": "https://127.0.0.1:18049", "u3": "https://127.0.0.1:18059",
        "u4": "https://127.0.0.1:18079", "u5": "https://127.0.0.1:18089",
        "u6": "https://127.0.0.1:18099",
    }
    assert local_profile.PORTS["u8"] == (18109, 15509)
    assert local_profile.REALMS["u8"] == ("u8-service-operations-integration", "service-operations")
