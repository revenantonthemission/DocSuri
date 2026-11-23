"""Every connection site that names a database demands SCRAM (U8 plan Step 164(i);
NFR3.3, L4-12).

A syntax scan of U8's product code that opens PostgreSQL connections:
`backend/transactions.py`, `backend/u8_*.py`, `backend/modules/operations` and
`ops/src/docsuri_ops`. It sees three shapes: a call with a `dbname` keyword, a dictionary
with a `dbname` key, and a string that holds `dbname=`. Each must carry `require_auth`
with `scram-sha-256`, or be one of the sites of `EXEMPT`, a closed list of the sites the
requirement's words do not cover, each with its reason.

What it cannot see: a connection whose options are assembled elsewhere (a positional
database name, options spread from a mapping built in another function). `UNSEEN` names
the one such site of this kind that the plan lists, with the fact that makes it safe,
which the test checks. It leaves `scripts/` and v1's modules out: the realm's tools and
the earlier Units' runners connect to their own realms, and v1's code to v1's database,
none of which is v2's instance.

This module also holds the raise-only spy Step 164's other tests set in place of the
driver's `connect`: it refuses before any connection and carries the options it was
called with in its exception, so a test reads them from the refusal.
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRAM = "scram-sha-256"
SCANNED = ("backend/transactions.py", "backend/u8_*.py", "backend/modules/operations/**/*.py",
           "ops/src/docsuri_ops/**/*.py")

# (file, enclosing function): why the requirement's words do not cover the site.
EXEMPT = {
    ("ops/src/docsuri_ops/platform_control/store.py", "connection"): (
        "U7's own Store, in U7's realm; U8's stores override it "
        "(`u8_platform/platform_profile.py`), and U7's file is not edited"),
    ("ops/src/docsuri_ops/u2_restore.py", "_connect"): (
        "U2's quarantined restore rehearsal: U2's own realm on port 15449, as that realm's "
        "superuser; not v2's instance"),
    ("ops/src/docsuri_ops/load_probe.py", "__init__"): (
        "the REM-1 load probe, a command-line tool that takes its host, port and database "
        "as arguments; not a client of v2's instance"),
    ("ops/src/docsuri_ops/production_wiring.py", "open_v1"): (
        "v1's database at the `v1Sources` address, read-only; not v2's instance"),
}
# Sites the scan cannot see, with the fact the test checks instead.
UNSEEN = {
    ("ops/src/docsuri_ops/production_tool.py", "_connect"): (
        "it spreads the options it is handed; it is the tool context's default `connect`, "
        "and the context's `connect` is called in `_open` only, which names the option"),
}


class Reached(BaseException):  # noqa: N818 - a signal, not an error
    """Raised in place of a connection; `options` is what the driver was asked for. Not an
    `Exception`, so a word that goes on after a failed connection (`recreate-database`
    falls back on its kept base) does not take it for one."""

    @property
    def options(self) -> dict:
        return self.args[0]


def refusing_connect(*_positional, **options):
    """A raise-only spy for the driver's `connect`: no connection is ever opened."""
    raise Reached(options)


def demanded(options: dict) -> tuple:
    """What a recorded connection names: host, port, user, database, `require_auth`."""
    return (options.get("host"), options.get("port"), options.get("user"),
            options.get("dbname"), options.get("require_auth"))


# --- the scan --------------------------------------------------------------------------


def _constants(tree: ast.Module) -> dict[str, str]:
    """The module's own string constants, so `require_auth=REQUIRE_AUTH` resolves."""
    found = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant) and (
                isinstance(node.value.value, str)):
            found.update({target.id: node.value.value for target in node.targets
                          if isinstance(target, ast.Name)})
    return found


def _is_scram(node: ast.AST | None, constants: dict[str, str]) -> bool:
    if isinstance(node, ast.Constant):
        return node.value == SCRAM
    return isinstance(node, ast.Name) and constants.get(node.id) == SCRAM


def _text(node: ast.AST) -> str | None:
    """A string's literal text: a constant's value, or an f-string's constant parts."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return "".join(part.value for part in node.values
                       if isinstance(part, ast.Constant) and isinstance(part.value, str))
    return None


def _site(node: ast.AST, constants: dict[str, str]) -> bool | None:
    """None when `node` names no database; else whether it demands SCRAM."""
    if isinstance(node, ast.Call) and any(k.arg == "dbname" for k in node.keywords):
        return any(k.arg == "require_auth" and _is_scram(k.value, constants)
                   for k in node.keywords)
    if isinstance(node, ast.Dict):
        keys = [key.value if isinstance(key, ast.Constant) else None for key in node.keys]
        if "dbname" not in keys:
            return None
        return "require_auth" in keys and _is_scram(
            node.values[keys.index("require_auth")], constants)
    text = _text(node)
    if text is None or "dbname=" not in text:
        return None
    return f"require_auth={SCRAM}" in text


def _walk(node: ast.AST, function: str, skip: set[int], out: list, constants) -> None:
    for child in ast.iter_child_nodes(node):
        inside = child.name if isinstance(
            child, ast.FunctionDef | ast.AsyncFunctionDef) else function
        if isinstance(child, ast.Expr) and isinstance(child.value, ast.Constant):
            continue  # a docstring or a bare string: no connection is made from it
        if id(child) not in skip:
            demands = _site(child, constants)
            if demands is not None:
                out.append((child.lineno, inside, demands))
        if isinstance(child, ast.JoinedStr):
            continue  # its parts were read as one string
        _walk(child, inside, skip, out, constants)


def connection_sites(source: str) -> list[tuple[int, str, bool]]:
    """Every site of `source` that names a database: (line, enclosing function, whether
    it demands SCRAM)."""
    tree = ast.parse(source)
    out: list = []
    _walk(tree, "<module>", set(), out, _constants(tree))
    return out


def scanned_files(root: Path = ROOT) -> dict[str, str]:
    files = sorted({path for pattern in SCANNED for path in root.glob(pattern)})
    return {str(path.relative_to(root)): path.read_text() for path in files
            if "__pycache__" not in path.parts}


def problems(files: dict[str, str], exempt=EXEMPT) -> list[str]:
    """Each site without the option that no exemption names, and each exemption that
    names no site (the list is closed: a stale entry fails too)."""
    found, used = [], set()
    for file, source in files.items():
        for line, function, demands in connection_sites(source):
            if (file, function) in exempt:
                used.add((file, function))
            elif not demands:
                found.append(f"{file}:{line} ({function}) names a database without "
                             f"require_auth={SCRAM}")
    found.extend(f"{file} ({function}): exempt, and no site there names a database"
                 for file, function in sorted(set(exempt) - used))
    return found


def _context_connect_callers(source: str) -> set[str]:
    """The functions of the production tool that call `context.connect(...)`."""
    callers = set()
    for function in ast.walk(ast.parse(source)):
        if not isinstance(function, ast.FunctionDef):
            continue
        for node in ast.walk(function):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and (
                    node.func.attr == "connect") and isinstance(node.func.value, ast.Name) and (
                    node.func.value.id == "context"):
                callers.add(function.name)
    return callers


U7_PACKAGE = "ops/src/docsuri_ops/platform_control/"


def bare_store_builders(files: dict[str, str]) -> list[str]:
    """Each place outside U7's own package that builds U7's `Store` itself (`Store(...)`,
    `Store.runtime(...)`, `Store.provisioner(...)`): such a store names no `require_auth`.
    A class that extends `Store` is not a build; U8's own does, and overrides it."""
    found = []
    for file, source in files.items():
        if file.startswith(U7_PACKAGE):
            continue
        for node in ast.walk(ast.parse(source)):
            callee = node.func if isinstance(node, ast.Call) else None
            if isinstance(callee, ast.Attribute) and callee.attr in ("runtime", "provisioner"):
                callee = callee.value
            name = callee.id if isinstance(callee, ast.Name) else (
                callee.attr if isinstance(callee, ast.Attribute) else None)
            if name == "Store":
                found.append(f"{file}:{node.lineno} builds U7's Store itself")
    return found


PLANTED = {
    "a call": "import psycopg\ndef reach(name):\n    return psycopg.connect(dbname=name)\n",
    "a call with a weaker demand": (
        "import psycopg\ndef reach(name):\n"
        "    return psycopg.connect(dbname=name, require_auth='md5')\n"),
    "a dictionary": (
        "def options(name):\n    user = 'x'\n"
        "    return {'dbname': name, 'user': user}\n"),
    "a string": (
        "def target(name):\n    user = 'x'\n"
        "    return f'host=127.0.0.1 dbname={name} user={user}'\n"),
}
DEMANDING = (
    "import psycopg\nREQUIRE_AUTH = 'scram-sha-256'\n"
    "def reach(name):\n"
    "    '''dbname= in a docstring is no site.'''\n"
    "    psycopg.connect(dbname=name, require_auth='scram-sha-256')\n"
    "    psycopg.connect(dbname=name, require_auth=REQUIRE_AUTH)\n"
    "    kwargs = {'dbname': name, 'require_auth': REQUIRE_AUTH}\n"
    "    return (f'host=127.0.0.1 dbname={name} '\n"
    "            f'require_auth=scram-sha-256', kwargs)\n"
)


def test_every_connection_site_that_names_a_database_in_u8s_product_code_demands_scram():
    """A syntax scan, and no more: a site whose options are assembled elsewhere is not
    seen (the module's docstring)."""
    files = scanned_files()
    assert {"backend/transactions.py", "backend/u8_host.py",
            "backend/modules/operations/producers.py",
            "ops/src/docsuri_ops/u8_platform/platform_profile.py",
            "ops/src/docsuri_ops/platform_control/store.py"} <= set(files)
    assert not [file for file in files if file.startswith(("scripts/", "tests/"))]
    assert problems(files) == []
    # The scan sees sites at all: at least the ones the plan's table names.
    seen = {(file, function) for file, source in files.items()
            for _, function, _ in connection_sites(source)}
    ops = "ops/src/docsuri_ops/"
    assert {("backend/transactions.py", "__init__"),
            (ops + "production_wiring.py", "connect"),
            (ops + "production_wiring.py", "production_import"),
            (ops + "production_tool.py", "_open"),
            (ops + "production_tool.py", "restore_database"),
            (ops + "production_tool.py", "restore_import"),
            (ops + "backup_agent/dumps.py", "conninfo"),
            (ops + "u8_platform/platform_profile.py", "connection"),
            (ops + "u8_platform/credential_release.py", "one_connection"),
            (ops + "u8_platform/recovery_words.py", "connect"),
            (ops + "u8_platform/drivers/arrangement.py", "_drop_as_scheduler"),
            (ops + "u8_platform/drivers/realm.py", "_connect"),
            (ops + "u8_platform/drivers/realm.py", "_pg_restore"),
            (ops + "migration/realm.py", "_connect"),
            (ops + "arrangement/installer.py", "login_check")} <= seen
    # Each planted site without the option is reported, by file, line and function.
    for label, source in PLANTED.items():
        [problem] = problems({"planted.py": source}, exempt={})
        assert problem.startswith("planted.py:3 (") and SCRAM in problem, label
    assert problems({"planted.py": DEMANDING}, exempt={}) == []
    assert len(connection_sites(DEMANDING)) == 4
    # U7's own Store is reported by name once it is off the list, and a stale entry too.
    without = {key: reason for key, reason in EXEMPT.items() if "platform_control" not in key[0]}
    assert [problem for problem in problems(files, exempt=without)
            if "platform_control/store.py" in problem]
    stale = {**EXEMPT, ("backend/u8_host.py", "nowhere"): "planted"}
    assert problems(files, exempt=stale) == [
        "backend/u8_host.py (nowhere): exempt, and no site there names a database"]
    assert all(reason for reason in (*EXEMPT.values(), *UNSEEN.values()))
    # U7's `Store` is exempt as U7's own: nothing outside U7's package builds one itself.
    assert bare_store_builders(files) == []
    assert bare_store_builders({"planted.py": (
        "from docsuri_ops.platform_control.store import Store\n"
        "def reach(target, profile):\n"
        "    return Store(target, role='r', password='p'), Store.runtime(profile)\n")}) == [
        "planted.py:3 builds U7's Store itself", "planted.py:3 builds U7's Store itself"]
    # The site the scan cannot see: the tool's `_connect` spreads its options, and the
    # context's `connect` is called in `_open` alone.
    tool = files["ops/src/docsuri_ops/production_tool.py"]
    assert ("ops/src/docsuri_ops/production_tool.py", "_connect") not in seen
    assert _context_connect_callers(tool) == {"_open"}
    assert "    connect: Callable = _connect\n" in tool
