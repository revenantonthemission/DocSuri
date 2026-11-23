"""Nothing the instructions never mock is replaced (U8 plan Step 98(d), L1-35, L1-56).

An AST scan of every module under `tests/u8_service_operations_integration`,
`scripts/u8_*.py` and `scripts/serve_docsuri_u8.py` resolves each `monkeypatch.setattr`,
`setattr`, `mock.patch` and `patch.object` target; each test-defined class or function,
`SimpleNamespace` or lambda passed to a callee for a parameter named `connect`, `conn`,
`connection`, `transactions`, `ledger` or `repository` (the parameter names read by AST
from the callee's definition in the repository); each assignment of such a double to a
`repository`, `transactions`, `ledger`, `connect` or `_connect` attribute; and each
wrapper set in place of a repository's `system` or `run`.

Everywhere it finds nothing replacing `psycopg.connect` or a psycopg connection, the
conftest `connect` fixture, `connect_database`, `connect_admin`, `OwnerTransactions` (its
bounded connection and `guard` included), `accounts.guard_session`, an owner's repository
(with its `system` and `run`), a driver's, a wiring's or a tool's `connect` or `_connect`,
the shared browser boundary or D7's boundary, or the backup agent's catalogue and archive
writers. In `integration/`, `cutover_stage.py` and `scripts/serve_docsuri_u8.py` (the
journeys' servers) it also finds no replacement of the operations `Ledger` or
`open_ledger`, and no test-defined class with the ledger's `records`, `revision` and `get`.

Every remaining hit is one of the allowed kinds, listed by file and line in `ALLOWED`: a
raise-only spy, a raise-only crash or statement-failure injection, a stub that refuses
before any connection or receives no statement, and a call-through spy whose body returns
the replaced callable's value (an observer, which replaces nothing). No double answers a
statement in place of the database. A listed double whose lines change fails the scan
until its entry is updated in the same change.

After the review of build batch 9b: a callee reached through a fixture or a parameter has
every repository definition of its name read, and then only a double with the part's own
surface counts (`SURFACES`); a test-defined class with a connection's `execute` handed to a
callee nothing is known of counts as a connection; an assignment to a `connection` or
`conn` attribute replaces a connection; a double imported from another of U8's test
modules resolves to its own file and lines; a value restores only the saved original of
the same target; the conftest `connect`, `transactions` and `realm` fixtures may not be
defined again; the archive writer (`ArchiveWriter`, `backup_agent.writing`) is never
replaced. A call-through or injection must return a call of the replaced callable itself
(its name, its module default, or a name its original was saved under) or of the wrapped
object's same method, and L1-75's sleep spy and deadline injection are kinds of their own.

After the re-review of build batch 9b: a double that another unit's test helpers define
(every test tree in `DEFINITION_ROOTS`, such as `tests/u6_approved_export`) resolves to its
own file and lines; a lambda counts as the real connector only when it is handed as an
argument and calls the runner's own `connect_admin` or `connect_database`, or
`psycopg.connect`; a value restores only when it is the saved original of the same owner
and attribute; an unresolved value set in place of `psycopg.connect`, a psycopg connection
or a bounded connection is a hit; a call-through's callee is a saved original or a real
(non-test) module's own callable of that name, never a test helper's; a method may return
nothing only as `__init__` or when it calls the wrapped object's same method; and every
path of a returning double ends in such a return.

By your answer of 2026-11-11 ("Rewrite, keep two"): a stub refuses or raises, or never
returns a value in place of the work's answer (each callable it offers returns nothing,
None, or the answer of a work it was handed); a raise-only double may be a class whose
`__init__` only stores attributes and whose other methods only raise; and a new, narrow
kind, a fixed-answer stub for a refusal that real data cannot reach, answers only the
fixed value its refusal needs (constants and module constants, after asserts on its
input, with no state) and is made once, passed straight to the one call whose refusal
the test asserts (inside `pytest.raises`, or bound to a name the function asserts `not`).
By your answer "Own database", U6's `OwnDue` is no longer passed and has no entry.

After the review of build batch 10a: a fixed-answer entry names the refusal its test
asserts (`assert not <bound>.<refused>` after the one binding, never rebound, or the
call as the only statement of `pytest.raises(<refused>, match=<match>)`) and, where its
answer is more than one scalar, that answer; a scalar is constants and upper-case names
bound at module level to such a scalar. A callable a test-defined class offers as a class
attribute or assigns in `__init__` (a lambda, a `partial`, a name of its own function) is
checked as each kind checks a method, and counts as its surface.

After the re-review of build batch 10a: every class attribute, every `self.<name>` set in
`__init__` (a tuple's items one by one) and every namespace member that is not plain data
is an offered callable: a lambda, a `staticmethod` or `classmethod` of a lambda, or a name
the scanned module defines as a function is checked; a `partial`, any other `staticmethod`
or `classmethod` and a bound method of an object made here are refused; and a value the
scan cannot read (a parameter, an import, a call) is refused under a name a part is called
through (`CALLED_NAMES`) or one of the double's own methods, and otherwise is a value it
holds (a wrapped object, a profile). The stub, raise-only and call-through rules, the
surface, the unknown-callee rule and the journey ledger rule all read these.
"""

from __future__ import annotations

import ast
import functools
from dataclasses import dataclass, field
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
TESTS = "tests/u8_service_operations_integration"
SENSITIVE_PARAMETERS = frozenset({"connect", "conn", "connection", "transactions", "ledger",
                                  "repository"})
DOUBLE_ATTRIBUTES = frozenset({"repository", "transactions", "ledger", "connect", "_connect",
                               "connection", "conn"})
CONNECTION_PART = "a psycopg connection or OwnerTransactions' bounded connection"
# The conftest fixtures no test module may define again under the same name.
CONFTEST = f"{TESTS}/conftest.py"
CONFTEST_FIXTURES = frozenset({"connect", "transactions", "realm"})
# A lambda handed as an argument that only calls the runner's own connector (or
# `psycopg.connect`) is that connector, not a double.
RUNNER_CONNECTORS = frozenset({"connect_admin", "connect_database"})
RUNNER_MODULES = ("verify_docsuri_u8", "scripts.verify_docsuri_u8")
# The parts an unresolved value may still not be set in place of.
DRIVER_PARTS = frozenset({"psycopg.connect", "a psycopg connection",
                          "a psycopg connection or OwnerTransactions' bounded connection",
                          "OwnerTransactions' bounded connection"})
# Where the ledger may not be replaced: the integration tests and the journeys' servers.
JOURNEY_PATHS = (f"{TESTS}/integration/", f"{TESTS}/cutover_stage.py",
                 "scripts/serve_docsuri_u8.py")
# Where the callees' parameter names are read from.
DEFINITION_ROOTS = ("backend", "ops/src", "scripts", "tests/u8_service_operations_integration",
                    "tests/u6_approved_export")
# L1-75's two new kinds (unit-test-instructions.md:738) stand beside L1-35's four; an entry
# whose one double holds several paths names each kind, joined by "+".
KINDS = frozenset({"raise-only", "raise-injection", "stub", "call-through", "sleep-spy",
                   "deadline-injection", "fixed-answer"})


@dataclass(frozen=True)
class Hit:
    """One replacement of a part the instructions never mock: the double's own lines."""

    file: str
    start: int
    end: int
    part: str
    how: str
    node: ast.AST | None = field(default=None, compare=False, hash=False, repr=False)
    # The replaced callable's name, and the names its original was saved under.
    name: str = field(default="", compare=False, hash=False, repr=False)
    saved: frozenset = field(default=frozenset(), compare=False, hash=False, repr=False)
    # The names the module binds to real (non-test) modules.
    real: frozenset = field(default=frozenset(), compare=False, hash=False, repr=False)
    # A `SimpleNamespace` double's members: each keyword and the double it resolves to
    # (or its own value); and the scanned module, which a fixed-answer stub's uses are
    # read from.
    members: tuple = field(default=(), compare=False, hash=False, repr=False)
    module: ast.Module | None = field(default=None, compare=False, hash=False, repr=False)


@dataclass(frozen=True)
class Listed:
    """An allowed double, by file and line, with its kind and reason. A fixed-answer stub's
    entry also names the refusal the test asserts (`refused`: the attribute of `assert not
    <bound>.<refused>`, or the exception `pytest.raises` names, with its `match`) and,
    where its answer is more than one scalar, that answer (`answer`, as source)."""

    file: str
    start: int
    end: int
    kind: str
    reason: str
    refused: str = ""
    match: str = ""
    answer: str = ""


def scanned_files(root: Path = ROOT) -> dict[str, str]:
    files = sorted((root / TESTS).rglob("*.py"))
    files += sorted((root / "scripts").glob("u8_*.py"))
    files.append(root / "scripts" / "serve_docsuri_u8.py")
    return {str(path.relative_to(root)): path.read_text() for path in files
            if "__pycache__" not in path.parts}


# --- the callees' parameter names -------------------------------------------------------------


def _parameters(node: ast.FunctionDef | ast.AsyncFunctionDef, *, method: bool) -> list[str]:
    names = [item.arg for item in (*node.args.posonlyargs, *node.args.args)]
    static = any(isinstance(item, ast.Name) and item.id == "staticmethod"
                 for item in node.decorator_list)
    if method and not static and names and names[0] in ("self", "cls"):
        names = names[1:]
    return names


def definitions_of(trees: dict[str, ast.Module]) -> dict[str, list[tuple[list[str], bool]]]:
    """Each callable's name: its positional parameters and whether it is a method, for each
    definition of that name (a class by its `__init__`, as a callable, not a method)."""
    index: dict[str, list[tuple[list[str], bool]]] = {}

    def add(name: str, node, *, method: bool, called_as_method: bool) -> None:
        index.setdefault(name, []).append((_parameters(node, method=method),
                                           called_as_method))

    def walk(node, *, in_class: bool) -> None:
        for item in ast.iter_child_nodes(node):
            if isinstance(item, ast.ClassDef):
                for member in item.body:
                    if (isinstance(member, ast.FunctionDef | ast.AsyncFunctionDef)
                            and member.name == "__init__"):
                        add(item.name, member, method=True, called_as_method=False)
                walk(item, in_class=True)
            elif isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef):
                add(item.name, item, method=in_class, called_as_method=in_class)
                walk(item, in_class=False)
            else:
                walk(item, in_class=in_class)

    for tree in trees.values():
        walk(tree, in_class=False)
    return index


def module_name(path: str) -> str:
    """`scripts/u8_phases.py` -> `u8_phases` and `scripts.u8_phases`; others dotted."""
    return path.removesuffix(".py").replace("/", ".").removesuffix(".__init__")


def repository_trees():
    """Each repository module's path and parsed tree, one at a time: a tree is dropped once
    its definitions are read, so the whole repository is never held parsed at once."""
    for folder in DEFINITION_ROOTS:
        for path in sorted((ROOT / folder).rglob("*.py")):
            if ".venv" in path.parts or "node_modules" in path.parts:
                continue
            try:
                yield str(path.relative_to(ROOT)), ast.parse(path.read_text())
            except (SyntaxError, UnicodeDecodeError):
                continue


@functools.cache
def repository_index() -> tuple[dict, dict, dict]:
    """The callees' parameters, each module's own definitions (small lists of names), and
    the top-level definitions of every other unit's test tree in `DEFINITION_ROOTS` (so a
    double those helpers define resolves), read in one pass over the repository."""
    definitions: dict[str, list] = {}
    modules: dict[str, dict] = {}
    helpers: dict[str, tuple[str, dict]] = {}
    for path, tree in repository_trees():
        for name, entries in definitions_of({path: tree}).items():
            definitions.setdefault(name, []).extend(entries)
        modules.update(modules_of({path: tree}))
        if path.startswith("tests/") and not path.startswith(TESTS + "/"):
            helpers.update(scanned_nodes_of({path: tree}))
    return definitions, modules, helpers


def repository_definitions() -> dict[str, list[tuple[list[str], set[str]]]]:
    return repository_index()[0]


def modules_of(trees: dict[str, ast.Module]) -> dict[str, dict]:
    """Each module's own definitions, by every name an import may give it (`ops/src/x/y.py`
    as `x.y`, `scripts/z.py` as `z` and `scripts.z`)."""
    found: dict[str, dict] = {}
    for path, tree in trees.items():
        names = {module_name(path)}
        if path.startswith("ops/src/"):
            names.add(module_name(path.removeprefix("ops/src/")))
        if path.startswith("scripts/"):
            names.add(module_name(path.removeprefix("scripts/")))
        own = definitions_of({path: ast.Module(body=[item for item in tree.body], type_ignores=[])})
        top = {item.name for item in tree.body
               if isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef)}
        value = {name: [entry for entry in entries if not entry[1]]
                 for name, entries in own.items() if name in top}
        for name in names:
            found[name] = value
    return found


def repository_modules() -> dict[str, dict]:
    return repository_index()[1]


def helper_nodes() -> dict[str, tuple[str, dict]]:
    return repository_index()[2]


def scanned_nodes_of(trees: dict[str, ast.Module]) -> dict[str, tuple[str, dict]]:
    """Each test module's file and top-level definitions, by its dotted name, so a double
    imported from another test module (`host_flows`, `v1_flows`, `conftest`, or another
    unit's helpers such as `tests/u6_approved_export/lane_flows.py`) resolves."""
    found: dict[str, tuple[str, dict]] = {}
    for path, tree in trees.items():
        if not path.startswith("tests/"):
            continue
        top = {item.name: item for item in tree.body
               if isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef)}
        found[module_name(path)] = (path, top)
    return found


def release_caches() -> None:
    """Free the repository's index when a module that reads it ends."""
    repository_index.cache_clear()


# --- what a replacement replaces --------------------------------------------------------------


def text(node: ast.AST | None) -> str:
    return "" if node is None else ast.unparse(node)


def forbidden_part(target: str, name: str, file: str) -> str | None:
    """The never-mocked part `target.name` is, or None."""
    dotted = f"{target}.{name}" if target else name
    last = target.split(".")[-1]
    low = target.lower()
    if name == "connect" and last == "psycopg":
        return "psycopg.connect"
    if last == "Connection" and "psycopg" in target:
        return "a psycopg connection"
    if name in ("connect_database", "connect_admin"):
        return name
    if "OwnerTransactions" in dotted:
        return "backend.transactions.OwnerTransactions"
    if "DeadlineConnection" in dotted:
        return "OwnerTransactions' bounded connection"
    if name == "guard" and "transactions" in low:
        return "OwnerTransactions.guard"
    # The conftest `transactions` fixture (an OwnerTransactions) and a connection object.
    if last == "transactions" and name in ("run", "connection", "close"):
        return "backend.transactions.OwnerTransactions"
    if last in ("conn", "connection", "bounded") and name in (
            "execute", "cursor", "transaction", "commit", "connection"):
        return CONNECTION_PART
    if name == "guard_session":
        return "accounts.guard_session"
    if "repository" in low or last.endswith("Repository") or name.endswith("Repository"):
        return "an owner's repository"
    if name in ("connect", "_connect"):
        return "a driver's, a wiring's or a tool's connect"
    if "local_browser" in dotted or "production_boundary" in dotted:
        return "the browser boundary"
    if ("catalogue" in low or "catalogue" in name or ("archives" in low and "backup" in low)
            or "ArchiveWriter" in dotted or "backup_agent.writing" in dotted
            or (last == "writing" and name in ("ArchiveWriter", "write"))):
        return "the backup agent's catalogue and archive writers"
    if any(file.startswith(path) for path in JOURNEY_PATHS) and (
            name in ("Ledger", "open_ledger") or last == "Ledger"):
        return "the operations ledger in an integration test or a journey"
    return None


class Scope:
    def __init__(self, parent: Scope | None):
        self.parent, self.names = parent, {}

    def bind(self, name: str, value) -> None:
        self.names[name] = value

    def lookup(self, name: str):
        scope = self
        while scope is not None:
            if name in scope.names:
                return scope.names[name]
            scope = scope.parent
        return None


PARAMETER = object()  # a name bound as a parameter: nothing known about its value
RECEIVING = frozenset({"conn", "connection", "cursor", "transactions", "repository"})


def receives_the_part(double) -> bool:
    """A function or lambda that is handed a connection, transactions or a repository (a
    unit of work run on the real part), rather than one standing in for it."""
    if not isinstance(double, ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda):
        return False
    arguments = double.args
    names = {item.arg for item in (*arguments.posonlyargs, *arguments.args,
                                   *arguments.kwonlyargs)}
    return bool(names & RECEIVING)


# The surface a stand-in for each sensitive parameter would have.
SURFACES = {"connect": {"execute", "cursor"}, "conn": {"execute", "cursor"},
            "connection": {"execute", "cursor"}, "transactions": {"run"},
            "repository": {"system", "run"}, "ledger": {"records", "revision", "get"}}
# The names a part is called through: a value no scan can read, offered under one of them,
# may answer in place of the part.
CALLED_NAMES = frozenset().union(*SURFACES.values())


def offered_names(node: ast.ClassDef, module: ast.Module | None = None) -> set[str]:
    """Every name a test-defined class offers a callable under: its `def` methods, and its
    class attributes and `__init__` assignments that are callables (`_attribute_callables`)."""
    return ({item.name for item in _methods(node)}
            | {offer.name for offer in _attribute_callables(node, module)})


def surface_of(double, parameter: str, module: ast.Module | None = None) -> bool:
    """A test-defined class, or a `SimpleNamespace`, with the part's own surface."""
    if isinstance(double, ast.ClassDef):
        # A callable offered as a class attribute or assigned in `__init__` is surface too.
        names = offered_names(double, module)
        if parameter == "repository" and double.name.endswith("Repository"):
            return True
    elif isinstance(double, ast.Call):
        names = {item.arg for item in double.keywords if item.arg}
    else:
        return False
    return bool(names & SURFACES[parameter])


class Scanner(ast.NodeVisitor):
    """One module's hits."""

    def __init__(self, file: str, definitions: dict, modules: dict | None = None,
                 test_nodes: dict | None = None):
        self.file, self.definitions, self.modules = file, definitions, modules or {}
        self.test_nodes = test_nodes or {}
        self.scope = Scope(None)
        self.hits: list[Hit] = []
        self.journey = any(file.startswith(path) for path in JOURNEY_PATHS)
        self.origin: dict[int, str] = {}  # a double imported from another test module
        self.saved: dict[str, set[str]] = {}  # attribute name -> names its original is under
        self.saved_full: dict[str, set[str]] = {}  # `owner.attribute` -> the same
        self.real: set[str] = set()  # names bound to real (non-test) modules
        self.test_aliases: set[str] = set()  # names bound to test modules or their names
        self.tree: ast.Module | None = None  # the scanned module

    def _imports(self, node: ast.Module) -> None:
        """Every import in the module: which names are real modules, which test ones."""
        for item in ast.walk(node):
            if isinstance(item, ast.Import):
                for alias in item.names:
                    bound = alias.asname or alias.name.split(".")[0]
                    (self.test_aliases if alias.name.startswith("tests.")
                     else self.real).add(bound)
            elif isinstance(item, ast.ImportFrom):
                module = item.module or ""
                for alias in item.names:
                    bound = alias.asname or alias.name
                    if module.startswith("tests"):
                        self.test_aliases.add(bound)
                    elif f"{module}.{alias.name}" in self.modules:
                        self.real.add(bound)

    # Scopes: definitions and simple assignments bind names; parameters shadow them.

    def _prebind(self, body: list[ast.stmt]) -> None:
        for statement in body:
            if isinstance(statement, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
                self.scope.bind(statement.name, statement)

    def visit_Module(self, node: ast.Module) -> None:
        # Where an original is saved: `original = DeadlineConnection.execute`,
        # `real = getattr(repository, "begin_send")`, or a tuple of such. A test module's
        # callable (`fake = helpers.connect`) is no original.
        self.tree = node
        self._imports(node)
        for item in ast.walk(node):
            if not isinstance(item, ast.Assign):
                continue
            pairs = []
            for target in item.targets:
                if isinstance(target, ast.Tuple) and isinstance(item.value, ast.Tuple):
                    pairs += list(zip(target.elts, item.value.elts, strict=False))
                else:
                    pairs.append((target, item.value))
            for target, value in pairs:
                attribute = owner = None
                if isinstance(value, ast.Attribute):
                    attribute, owner = value.attr, value.value
                elif (isinstance(value, ast.Call) and text(value.func) == "getattr"
                      and len(value.args) >= 2 and isinstance(value.args[1], ast.Constant)):
                    attribute, owner = str(value.args[1].value), value.args[0]
                if attribute is None or not isinstance(target, ast.Name):
                    continue
                root = owner
                while isinstance(root, ast.Attribute | ast.Call | ast.Subscript):
                    root = root.func if isinstance(root, ast.Call) else root.value
                if isinstance(root, ast.Name) and root.id in self.test_aliases:
                    continue
                self.saved.setdefault(attribute, set()).add(target.id)
                self.saved_full.setdefault(f"{text(owner)}.{attribute}", set()).add(target.id)
        self._prebind(node.body)
        self.generic_visit(node)

    def _function(self, node) -> None:
        for decorator in getattr(node, "decorator_list", ()):
            self.visit(decorator)
        for default in (*node.args.defaults, *node.args.kw_defaults):
            if default is not None:
                self.visit(default)
        outer = self.scope
        self.scope = Scope(outer)
        arguments = node.args
        for item in (*arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs,
                     *([arguments.vararg] if arguments.vararg else []),
                     *([arguments.kwarg] if arguments.kwarg else [])):
            self.scope.bind(item.arg, PARAMETER)
        if isinstance(node, ast.Lambda):
            self.visit(node.body)
        else:
            self._prebind(node.body)
            for statement in node.body:
                self.visit(statement)
        self.scope = outer

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            if alias.asname:
                self.scope.bind(alias.asname, ("module", alias.name))
            else:
                self.scope.bind(alias.name.split(".")[0], ("module", alias.name.split(".")[0]))

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        for alias in node.names:
            module = node.module or ""
            dotted = f"{module}.{alias.name}"
            # `from a import b` is a module when `a.b` is one, else a name of `a`.
            value = ("module", dotted) if dotted in self.modules else ("from", module, alias.name)
            self.scope.bind(alias.asname or alias.name, value)

    def candidates(self, callee: ast.AST) -> list:
        """The definitions a call reaches: through the module's own scope and imports when
        it can tell, else every definition of the name in the repository. A callee bound
        to a parameter (a fixture's module or object, a callback) is unknown, so every
        repository definition of its name is read, functions and methods alike; none for
        a name bound to some other value."""
        def functions(name: str) -> list:
            return [entry for entry in self.definitions.get(name, []) if not entry[1]]

        if isinstance(callee, ast.Name):
            value = self.scope.lookup(callee.id)
            if isinstance(value, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
                own = definitions_of({"": ast.Module(body=[value], type_ignores=[])})
                return [entry for entry in own.get(callee.id, []) if not entry[1]]
            if isinstance(value, tuple) and value[0] == "from":
                module = self.modules.get(value[1])
                if module is not None:
                    return module.get(value[2], [])
                return functions(callee.id)
            if value is None:
                return functions(callee.id)
            if value is PARAMETER:
                return list(self.definitions.get(callee.id, []))
            return []
        if isinstance(callee, ast.Attribute):
            if isinstance(callee.value, ast.Name):
                value = self.scope.lookup(callee.value.id)
                if isinstance(value, tuple) and value[0] == "module":
                    module = self.modules.get(value[1])
                    if module is not None:
                        return module.get(callee.attr, [])
                    return functions(callee.attr)
                if value is PARAMETER:
                    # A fixture's module or object (`runner.apply_migrations(...)`): every
                    # repository definition of the name, module functions and methods.
                    return list(self.definitions.get(callee.attr, []))
            # A method call on an object: the methods of that name.
            return [entry for entry in self.definitions.get(callee.attr, []) if entry[1]]
        return []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.scope.bind(node.name, node)  # a definition inside a block binds too
        if (node.name in CONFTEST_FIXTURES and self.file != CONFTEST
                and any("fixture" in text(item) for item in node.decorator_list)):
            self._hit(node, "the conftest connect fixture",
                      f"fixture {node.name} defined again outside conftest.py")
        self._function(node)

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Lambda(self, node: ast.Lambda) -> None:
        self._function(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        if self.journey:
            # Its `def` methods and the callables it offers as attributes alike.
            if {"records", "revision", "get"} <= offered_names(node, self.tree):
                self._hit(node, "the operations ledger in an integration test or a journey",
                          f"class {node.name} has the ledger's records, revision and get")
        self.scope.bind(node.name, node)
        outer = self.scope
        self.scope = Scope(outer)
        self._prebind(node.body)
        for statement in node.body:
            self.visit(statement)
        self.scope = outer

    def visit_Assign(self, node: ast.Assign) -> None:
        self.visit(node.value)
        for target in node.targets:
            if isinstance(target, ast.Name):
                self.scope.bind(target.id, node.value)
            elif isinstance(target, ast.Attribute):
                self._assigned(target, node.value)
            self.visit(target)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if node.value is not None:
            self.visit(node.value)
            if isinstance(node.target, ast.Name):
                self.scope.bind(node.target.id, node.value)
            elif isinstance(node.target, ast.Attribute):
                self._assigned(node.target, node.value)

    # Doubles.

    def resolve(self, node: ast.AST, depth: int = 0):
        """The double `node` is (a test-defined function or class, a lambda or a
        `SimpleNamespace`, or a test-defined class's instance), else None."""
        if depth > 5:
            return None
        if isinstance(node, ast.Lambda):
            return node
        if isinstance(node, ast.Name):
            value = self.scope.lookup(node.id)
            if value is None or value is PARAMETER:
                return None
            if isinstance(value, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
                return value
            if isinstance(value, tuple):
                return self.imported(value)
            return self.resolve(value, depth + 1)
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            value = self.scope.lookup(node.value.id)
            if isinstance(value, tuple) and value[0] == "module":
                return self.imported(("from", value[1], node.attr))
        if isinstance(node, ast.Call):
            callee = node.func
            if text(callee).split(".")[-1] == "SimpleNamespace":
                return node
            # A class's instance: the class named directly, or imported (calling a name
            # bound to an instance is not making one).
            found = None
            if isinstance(callee, ast.Name):
                value = self.scope.lookup(callee.id)
                found = self.imported(value) if isinstance(value, tuple) else value
            elif isinstance(callee, ast.Attribute):
                found = self.resolve(callee, depth + 1)
            if isinstance(found, ast.ClassDef):
                return found
        return None

    def imported(self, value: tuple):
        """A class or function another test module defines, imported here."""
        if value[0] != "from":
            return None
        module = self.test_nodes.get(value[1])
        if module is None:
            return None
        path, top = module
        found = top.get(value[2])
        if found is not None:
            self.origin[id(found)] = path
        return found

    def doubles(self, node: ast.AST) -> list:
        if isinstance(node, ast.IfExp):
            return [*self.doubles(node.body), *self.doubles(node.orelse)]
        found = self.resolve(node)
        return [] if found is None else [found]

    def restoring(self, node: ast.AST, target: str, name: str) -> bool:
        """A value that puts back the saved original of the same target: the same owner's
        attribute of that name, or a name assigned from exactly that target."""
        full = f"{target}.{name}" if target else name
        if isinstance(node, ast.Attribute):
            return text(node) == full
        if isinstance(node, ast.Name):
            value = self.scope.lookup(node.id)
            return isinstance(value, ast.Attribute) and text(value) == full or (
                node.id in self.saved_full.get(full, set()))
        return False

    def real_connector(self, node: ast.AST) -> bool:
        """A lambda that only calls the runner's own `connect_admin` or `connect_database`
        (the `runner` the phases are handed, or the runner module), or `psycopg.connect`."""
        if not isinstance(node, ast.Lambda) or not isinstance(node.body, ast.Call):
            return False
        callee = node.body.func
        if isinstance(callee, ast.Attribute) and isinstance(callee.value, ast.Name):
            value = self.scope.lookup(callee.value.id)
            if callee.attr == "connect" and value == ("module", "psycopg"):
                return True
            if callee.attr in RUNNER_CONNECTORS:
                return (value is PARAMETER and callee.value.id == "runner") or (
                    isinstance(value, tuple) and value[0] == "module"
                    and value[1] in RUNNER_MODULES)
        if isinstance(callee, ast.Name) and callee.id in RUNNER_CONNECTORS:
            value = self.scope.lookup(callee.id)
            return isinstance(value, tuple) and value[0] == "from" and value[1] in RUNNER_MODULES
        return False

    def _hit(self, double, part: str, how: str, name: str = "") -> None:
        end = getattr(double, "end_lineno", double.lineno)
        members = ()
        if isinstance(double, ast.Call):
            members = tuple((item.arg, self.resolve(item.value) or item.value)
                            for item in double.keywords if item.arg)
        self.hits.append(Hit(self.origin.get(id(double), self.file), double.lineno, end, part,
                             how, double, name, frozenset(self.saved.get(name, set())),
                             frozenset(self.real), members, self.tree))
        # A lambda that hands back a test-defined wrapper of the real value: the wrapper is
        # a double too, listed and shape-checked at its own lines.
        if isinstance(double, ast.Lambda) and isinstance(double.body, ast.Call):
            wrapper = self.resolve(double.body)
            if isinstance(wrapper, ast.ClassDef):
                self._hit(wrapper, part, f"the wrapper {wrapper.name} {how}", name)

    def _replaced(self, target: str, name: str, value: ast.AST | None, node: ast.AST,
                  how: str) -> None:
        part = forbidden_part(target, name, self.file)
        if part is None or (value is not None and self.restoring(value, target, name)):
            return
        found = self.doubles(value) if value is not None else []
        for double in found or [value or node]:
            self._hit(double, part, how, name)

    def _assigned(self, target: ast.Attribute, value: ast.AST) -> None:
        owner, name = text(target.value), target.attr
        found = self.doubles(value)
        if name in DOUBLE_ATTRIBUTES and found:
            part = {"repository": "an owner's repository",
                    "transactions": "backend.transactions.OwnerTransactions",
                    "connect": "a driver's, a wiring's or a tool's connect",
                    "_connect": "a driver's, a wiring's or a tool's connect",
                    "connection": CONNECTION_PART, "conn": CONNECTION_PART}.get(name)
            if name == "ledger" and self.journey:
                part = "the operations ledger in an integration test or a journey"
            if part is not None:
                for double in found:
                    self._hit(double, part, f"assigned to {owner}.{name}", name)
                return
        if name in ("system", "run") and "repository" in owner.lower() and found:
            for double in found:
                self._hit(double, "an owner's repository", f"a wrapper set as {owner}.{name}",
                          name)
            return
        # An unresolved value (a `MagicMock()`, a `partial`) is left open for a generic
        # driver, wiring or tool `connect`, which many helpers set to real parts; never for
        # psycopg's own `connect`, a psycopg connection or a bounded connection.
        if name not in DOUBLE_ATTRIBUTES or (
                not found and forbidden_part(owner, name, self.file) in DRIVER_PARTS):
            self._replaced(owner, name, value, target, f"assigned to {owner}.{name}")

    def visit_Call(self, node: ast.Call) -> None:
        self.generic_visit(node)
        callee = text(node.func)
        last = callee.split(".")[-1]
        arguments = node.args
        # monkeypatch.setattr(target, "name", value), setattr(...), and its string form.
        if last == "setattr" and arguments:
            if len(arguments) >= 3 and isinstance(arguments[1], ast.Constant):
                self._replaced(text(arguments[0]), str(arguments[1].value), arguments[2],
                               node, f"{callee}({text(arguments[0])}, {arguments[1].value!r})")
            elif (len(arguments) == 2 and isinstance(arguments[0], ast.Constant)
                  and isinstance(arguments[0].value, str) and "." in arguments[0].value):
                target, _, name = arguments[0].value.rpartition(".")
                self._replaced(target, name, arguments[1], node, f"{callee}({target}.{name})")
            return
        # mock.patch("a.b.c", ...) and patch.object(target, "name", ...).
        if last == "patch" and arguments and isinstance(arguments[0], ast.Constant):
            target, _, name = str(arguments[0].value).rpartition(".")
            value = arguments[1] if len(arguments) > 1 else None
            self._replaced(target, name, value, node, f"{callee}({arguments[0].value!r})")
            return
        if callee.endswith("patch.object") and len(arguments) >= 2:
            value = arguments[2] if len(arguments) > 2 else None
            self._replaced(text(arguments[0]), str(getattr(arguments[1], "value", "")), value,
                           node, f"{callee}({text(arguments[0])})")
            return
        self._passed(node, last)

    def _passed(self, node: ast.Call, last: str) -> None:
        """A double passed for a sensitive parameter, by keyword or by position."""
        candidates = self.candidates(node.func)
        bound = node.func.value if isinstance(node.func, ast.Attribute) else node.func
        uncertain = isinstance(bound, ast.Name) and self.scope.lookup(bound.id) is PARAMETER
        named: list[tuple[str, ast.AST]] = []
        for keyword in node.keywords:
            if keyword.arg in SENSITIVE_PARAMETERS:
                named.append((keyword.arg, keyword.value))
        for index, argument in enumerate(node.args):
            if isinstance(argument, ast.Starred):
                break
            # By position: a stand-in object (a test-defined class's instance or a
            # `SimpleNamespace`) for any definition of the callee's name that names the
            # parameter so; a function or lambda only when every definition does.
            names = {positional[index] if index < len(positional) else None
                     for positional, _ in candidates}
            sensitive = names & SENSITIVE_PARAMETERS
            objects = [double for double in self.doubles(argument)
                       if isinstance(double, ast.ClassDef | ast.Call)]
            if sensitive and uncertain:
                # Every definition of a parameter-bound callee's name was read: any double
                # counts when every one of them names the position so (the rule a known
                # callee's functions follow), and a stand-in object with the part's own
                # surface counts when one of them does.
                every = len(names) == 1
                named.extend((name, argument) for name in sorted(sensitive)
                             if every or any(surface_of(double, name, self.tree)
                                             for double in objects))
            elif sensitive and (objects or len(names) == 1):
                named.extend((name, argument) for name in sorted(sensitive))
            elif not sensitive and (uncertain or not any(positional
                                                         for positional, _ in candidates)):
                # A callee nothing is known of (a callback a fixture hands, `action(...)`):
                # a test-defined class with a connection's `execute` (a `def` method or an
                # offered callable) stands in for one.
                if any(isinstance(double, ast.ClassDef)
                       and "execute" in offered_names(double, self.tree)
                       for double in self.doubles(argument)):
                    named.append(("conn", argument))
        for name, value in named:
            if name == "ledger" and not self.journey:
                continue
            part = {"connect": "a database connection", "conn": "a database connection",
                    "connection": "a database connection",
                    "transactions": "backend.transactions.OwnerTransactions",
                    "repository": "an owner's repository",
                    "ledger": "the operations ledger in an integration test or a journey"}[name]
            for double in self.doubles(value):
                if receives_the_part(double):
                    continue  # a callback the real part is handed, not the part
                if name in ("connect", "conn", "connection") and self.real_connector(double):
                    continue  # the runner's own connector, or psycopg's, handed as is
                self._hit(double, part, f"passed to {last}() for {name!r}", name)


def scan(files: dict[str, str], definitions: dict | None = None) -> list[Hit]:
    """Every hit in `files` (path: source); the callees' parameters are read from the
    repository, and from `files` themselves."""
    trees = {path: ast.parse(source) for path, source in files.items()}
    index = dict(definitions if definitions is not None else repository_definitions())
    planted = {path: tree for path, tree in trees.items() if not (ROOT / path).is_file()}
    for name, entries in definitions_of(planted).items():
        index[name] = [*index.get(name, []), *entries]
    modules = {**repository_modules(), **modules_of(planted)}
    test_nodes = {**helper_nodes(), **scanned_nodes_of(trees)}
    hits: set[Hit] = set()
    ordered: list[Hit] = []
    for path, tree in trees.items():
        scanner = Scanner(path, index, modules, test_nodes)
        scanner.visit(tree)
        for hit in scanner.hits:
            if hit not in hits:
                hits.add(hit)
                ordered.append(hit)
    return ordered


# --- each allowed double's shape --------------------------------------------------------------


def _body(node) -> list[ast.stmt]:
    body = list(node.body)
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
        body = body[1:]  # its docstring
    return body


def _unwrap(value: ast.AST | None) -> ast.AST | None:
    return value.value if isinstance(value, ast.Await) else value


class Through:
    """Whether a double hands back the replaced callable's own value: each value it
    returns is a call of the replaced callable (its name, or a name its original was saved
    under), of the wrapped object's same method, or a name bound to such a call."""

    def __init__(self, name: str, saved: frozenset, real: frozenset = frozenset(),
                 module: ast.Module | None = None):
        self.name, self.saved, self.real, self.module = name, saved, real, module

    def callee_ok(self, callee: ast.AST, *, method: str | None = None) -> bool:
        dotted = text(callee)
        parts = dotted.split(".")
        if method is not None:
            # `self.<wrapped>.<same method>(...)`, or `self.<wrapped>(...)` for `__call__`.
            return (len(parts) == 3 and parts[0] == "self" and parts[2] == method) or (
                method == "__call__" and len(parts) == 2 and parts[0] == "self")
        # A name its original was saved under, or a real (non-test) module's own callable of
        # the replaced name or its module default (`psycopg.connect`, `tool._connect` for
        # `connect`); never a test helper's or a test object's callable of that name.
        if isinstance(callee, ast.Name):
            return callee.id in self.saved
        return (bool(self.name) and len(parts) == 2 and parts[0] in self.real
                and parts[1] in (self.name, "_" + self.name))

    def calls_through(self, function, method: str) -> bool:
        """The method's body calls the wrapped object's same method."""
        return any(isinstance(item, ast.Call) and self.callee_ok(item.func, method=method)
                   for item in ast.walk(function))

    def returns_ok(self, function, *, method: str | None = None) -> bool:
        bound = set()
        for item in ast.walk(function):
            if isinstance(item, ast.Assign):
                value = _unwrap(item.value)
                if isinstance(value, ast.Call) and self.call_ok(value, method=method):
                    bound |= {target.id for target in item.targets
                              if isinstance(target, ast.Name)}
        returns = [item for item in ast.walk(function) if isinstance(item, ast.Return)
                   and not _nested_return(function, item)]
        if not returns:
            # Only `__init__`, or a method that calls the wrapped object's same method, may
            # return nothing.
            return method == "__init__" or (method is not None
                                            and self.calls_through(function, method))
        if _falls_off(_body(function)):
            return False  # a path that ends without a return answers None
        for item in returns:
            value = _unwrap(item.value)
            if isinstance(value, ast.Call) and self.call_ok(value, method=method):
                continue
            if isinstance(value, ast.Name) and value.id in bound:
                continue
            if method == "__enter__" and isinstance(value, ast.Name) and value.id == "self":
                continue
            return False
        return True

    def offered_through(self, name: str, item: ast.AST) -> bool:
        """A class's offered callable under `name` calls through: a lambda whose value is
        the wrapped object's same method or the replaced callable, or a function whose
        every return is such a call."""
        through = Through(name, self.saved, self.real, self.module)
        if isinstance(item, ast.Lambda):
            body = _unwrap(item.body)
            return (isinstance(body, ast.Call) and self.call_ok(body, method=name)) or (
                through.holds(item))
        return isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef) and through.returns_ok(
            item, method=name)

    def call_ok(self, call: ast.Call, *, method: str | None = None) -> bool:
        if method == "__getattr__":
            # `getattr(self.<wrapped>, name)`: every other attribute is the wrapped one's.
            return (text(call.func) == "getattr" and bool(call.args)
                    and text(call.args[0]).startswith("self."))
        return self.callee_ok(call.func, method=method)

    def holds(self, node: ast.AST) -> bool:
        if isinstance(node, ast.Lambda):
            body = node.body
            if isinstance(body, ast.BoolOp):
                body = body.values[-1]
            body = _unwrap(body)
            if not isinstance(body, ast.Call):
                return False
            # The real call, or a test-defined wrapper (`Wrapper(original(...))`) handed the
            # real call's value; the wrapper is its own listed, shape-checked double.
            return self.call_ok(body) or (isinstance(body.func, ast.Name) and any(
                isinstance(_unwrap(item), ast.Call) and self.call_ok(_unwrap(item))
                for item in body.args))
        if isinstance(node, ast.ClassDef):
            methods = _methods(node)
            if not (methods and all(self.returns_ok(item, method=item.name)
                                    for item in methods)):
                return False
            # Every other callable it offers (a class attribute, a `self.<name>` set in
            # `__init__`) calls through too, as a namespace's members do; one whose answer
            # the scan cannot show fails.
            return all(offer.nodes and all(self.offered_through(offer.name, item)
                                           for item in offer.nodes)
                       for offer in _attribute_callables(node, self.module))
        if isinstance(node, ast.Call):
            # A `SimpleNamespace` whose callables are the real part's own bound methods of
            # the same names, or lambdas that call those through.
            # Plain data beside them (a constant, or a namespace of constants) answers no
            # statement.
            return bool(node.keywords) and all(
                (isinstance(item.value, ast.Attribute) and item.value.attr == item.arg)
                or (isinstance(item.value, ast.Lambda)
                    and Through(item.arg or "", self.saved, self.real).holds(item.value))
                or _data(item.value)
                for item in node.keywords)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            return self.returns_ok(node)
        return False


def _data(value: ast.AST) -> bool:
    """A constant, or a `SimpleNamespace` of constants: data, not a callable."""
    if isinstance(value, ast.Constant):
        return True
    return (isinstance(value, ast.Call) and text(value.func).split(".")[-1] == "SimpleNamespace"
            and not value.args and all(_data(item.value) for item in value.keywords))


def _falls_off(body: list[ast.stmt]) -> bool:
    """Whether a path through `body` can end without a return or a raise."""
    if not body:
        return True
    last = body[-1]
    if isinstance(last, ast.Return | ast.Raise):
        return False
    if isinstance(last, ast.If):
        return _falls_off(last.body) or _falls_off(last.orelse)
    if isinstance(last, ast.With | ast.AsyncWith):
        return _falls_off(last.body)
    if isinstance(last, ast.Try):
        if last.finalbody and not _falls_off(last.finalbody):
            return False
        main = last.orelse or last.body
        return _falls_off(main) or any(_falls_off(handler.body) for handler in last.handlers)
    return True


def _nested_return(function, item: ast.Return) -> bool:
    """A return that belongs to a function defined inside `function`."""
    for inner in ast.walk(function):
        if inner is not function and isinstance(
                inner, ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda) and any(
                    found is item for found in ast.walk(inner)):
            return True
    return False


def _raises(node) -> bool:
    return any(isinstance(item, ast.Raise) for item in ast.walk(node))


def _calls_with(node, fragment: str) -> bool:
    return any(isinstance(item, ast.Constant) and isinstance(item.value, str)
               and fragment in item.value for item in ast.walk(node))


def _sets_deadline(node) -> bool:
    return any(isinstance(item, ast.Assign) and any(
        isinstance(target, ast.Attribute) and target.attr == "deadline"
        for target in item.targets) for item in ast.walk(node))


def _only_raises(function) -> bool:
    body = _body(function)
    return bool(body) and all(isinstance(item, ast.Raise) for item in body)


def _only_assigns(function) -> bool:
    """An `__init__` that only stores attributes: no return, no other work."""
    return all(isinstance(item, ast.Assign | ast.AnnAssign) for item in _body(function))


def _methods(node: ast.ClassDef) -> list:
    return [item for item in node.body if isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef)]


def _plain_data(value: ast.AST | None) -> bool:
    """Plain data, never a callable: a constant, a list, tuple, set or dict of plain data,
    or a `SimpleNamespace` of plain data."""
    if isinstance(value, ast.Constant):
        return True
    if isinstance(value, ast.List | ast.Tuple | ast.Set):
        return all(_plain_data(item) for item in value.elts)
    if isinstance(value, ast.Dict):
        return all(key is not None and _plain_data(key) for key in value.keys) and all(
            _plain_data(item) for item in value.values)
    return (isinstance(value, ast.Call) and text(value.func).split(".")[-1] == "SimpleNamespace"
            and not value.args and all(_plain_data(item.value) for item in value.keywords))


def _module_functions(module: ast.Module | None, name: str) -> list:
    """Every function of that name the module defines, at any depth."""
    if module is None:
        return []
    return [item for item in ast.walk(module)
            if isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef) and item.name == name]


def _offered_value(name: str, value: ast.AST | None, module: ast.Module | None,
                   methods: frozenset) -> tuple[str, tuple]:
    """What a double offers under `name` (a class attribute, a `self.<name>` set in
    `__init__`, or a namespace member), as one of:
    - "data": plain data, or a value it holds under a name no part calls and no method of
      its own has (a wrapped object, a profile);
    - "method": an alias of one of its own methods, which is checked as a method;
    - "check": callables whose answers the scan reads (a lambda, a `staticmethod` or
      `classmethod` of a lambda, a function the scanned module defines);
    - "refused": a callable whose answer the scan cannot show (a `partial(...)`, any other
      `staticmethod` or `classmethod`, a bound method of an object made here), or any
      value it cannot read (a parameter, an import, a call) offered under a name a part
      calls (`CALLED_NAMES`) or under the name of one of its own methods."""
    value = _unwrap(value) if value is not None else None
    if value is None or _plain_data(value):
        return "data", ()
    if isinstance(value, ast.Lambda | ast.FunctionDef | ast.AsyncFunctionDef):
        return "check", (value,)
    if isinstance(value, ast.Call):
        last = text(value.func).split(".")[-1]
        if last in ("staticmethod", "classmethod"):
            inner = value.args[0] if len(value.args) == 1 else None
            return ("check", (inner,)) if isinstance(inner, ast.Lambda) else ("refused", ())
        if last == "partial":
            return "refused", ()
    if isinstance(value, ast.Name):
        if value.id in methods:
            return "method", ()
        found = _module_functions(module, value.id)
        if found:
            return "check", tuple(found)
    if isinstance(value, ast.Attribute):
        root = value
        while isinstance(root, ast.Attribute):
            root = root.value
        if isinstance(root, ast.Call):
            return "refused", ()  # `Rows().run`: a bound method of an object made here
    if name in CALLED_NAMES or name in methods:
        return "refused", ()
    return "data", ()


@dataclass(frozen=True)
class Offered:
    """A callable a test-defined class offers beside its `def` methods: its name, the
    callables the scan checks for it (none when its answer cannot be shown, which refuses
    it), and its line."""

    name: str
    nodes: tuple
    line: int


def _pairs(targets: list, value: ast.AST | None) -> list:
    """Each (target, value) of an assignment, a tuple's items paired one by one; a target
    of a tuple unpacked from one value gets that whole value."""
    pairs = []
    for target in targets:
        if isinstance(target, ast.Tuple | ast.List):
            values = (value.elts if isinstance(value, ast.Tuple | ast.List)
                      and len(value.elts) == len(target.elts) else [value] * len(target.elts))
            pairs += list(zip(target.elts, values, strict=True))
        else:
            pairs.append((target, value))
    return pairs


def _attribute_callables(node: ast.ClassDef, module: ast.Module | None = None) -> list[Offered]:
    """Every callable a test-defined class offers beside its `def` methods: each class
    attribute and each `self.<name>` set in `__init__` that is not plain data or a value
    it holds (see `_offered_value`). A name is resolved through the scanned module to the
    functions it defines; an alias of one of its own methods is checked as that method."""
    methods = frozenset(item.name for item in _methods(node))
    pairs: list = []
    for item in node.body:
        if isinstance(item, ast.Assign):
            pairs += [(target.id, value, item.lineno)
                      for target, value in _pairs(item.targets, item.value)
                      if isinstance(target, ast.Name)]
        elif isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
            pairs.append((item.target.id, item.value, item.lineno))
    for method in _methods(node):
        if method.name != "__init__":
            continue
        for item in ast.walk(method):
            found = []
            if isinstance(item, ast.Assign):
                found = _pairs(item.targets, item.value)
            elif isinstance(item, ast.AnnAssign):
                found = [(item.target, item.value)]
            pairs += [(target.attr, value, item.lineno) for target, value in found
                      if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name)
                      and target.value.id == "self"]
    offered = []
    for name, value, line in pairs:
        verdict, nodes = _offered_value(name, value, module, methods)
        if verdict in ("check", "refused"):
            offered.append(Offered(name, nodes, line))
    return offered


def _raise_only(node, module: ast.Module | None = None) -> bool:
    """A function whose body only raises, or a class whose `__init__` only stores
    attributes (no callable among them, see `_attribute_callables`) and whose every other
    method only raises."""
    if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
        return _only_raises(node)
    if isinstance(node, ast.ClassDef):
        methods = [item for item in _methods(node) if item.name != "__init__"]
        return (bool(methods) and all(_only_raises(item) for item in methods)
                and all(_only_assigns(item) for item in _methods(node)
                        if item.name == "__init__")
                and not _attribute_callables(node, module))
    return False


def _no_answer(function) -> bool:
    """A callable that answers nothing in place of the work's answer: each value it can
    return is None, or the answer of a work it was handed (a call of its own parameter);
    a body that only raises, or returns nothing, qualifies."""
    arguments = function.args
    own = {item.arg for item in (*arguments.posonlyargs, *arguments.args,
                                 *arguments.kwonlyargs)}

    def handed_back(value) -> bool:
        value = _unwrap(value)
        if value is None or (isinstance(value, ast.Constant) and value.value is None):
            return True
        return (isinstance(value, ast.Call) and isinstance(value.func, ast.Name)
                and value.func.id in own)

    if isinstance(function, ast.Lambda):
        return handed_back(function.body)
    return all(handed_back(item.value) for item in ast.walk(function)
               if isinstance(item, ast.Return) and not _nested_return(function, item))


def stub_problem(node: ast.AST, members: tuple = (), module: ast.Module | None = None,
                 ) -> str | None:
    """Step 98(d)'s stub shape (your answer of 2026-11-11, "Rewrite, keep two"): a stub
    refuses or raises, or never returns a value in place of the work's answer. Every
    callable it offers (itself, its methods, a class's attributes and `__init__`
    assignments, a `SimpleNamespace`'s members) is checked, a name through the scanned
    module's functions; one whose answer the scan cannot show (a `partial`, a
    `staticmethod` of anything but a lambda, a bound method, a parameter offered under a
    name a part calls or one of its own methods) refuses the stub. Plain data, and a value
    it holds under another name, answers no statement."""
    callables: list = []
    refused: list[int] = []

    def take(cls: ast.ClassDef) -> None:
        callables.extend(_methods(cls))
        for offer in _attribute_callables(cls, module):
            if offer.nodes:
                callables.extend(offer.nodes)
            else:
                refused.append(offer.line)

    if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda):
        callables.append(node)
    elif isinstance(node, ast.ClassDef):
        take(node)
    elif isinstance(node, ast.Call):
        for name, value in members:
            if isinstance(value, ast.ClassDef):
                take(value)
                continue
            verdict, nodes = _offered_value(name, value, module, frozenset())
            if verdict == "check":
                callables.extend(nodes)
            elif verdict == "refused":
                refused.append(getattr(value, "lineno", node.lineno))
    else:
        return "a stub is a test-defined function, class, lambda or namespace"
    lines = refused + [function.lineno for function in callables if not _no_answer(function)]
    if lines:
        return (f"a stub refuses or raises, or never returns a value in place of the "
                f"work's answer (line {min(lines)})")
    return None


@functools.cache
def _module_tree(dotted: str) -> ast.Module | None:
    """A real module's parsed tree, by its dotted name, when it is a file of this
    repository."""
    path = ROOT / (dotted.replace(".", "/") + ".py")
    if not path.is_file():
        return None
    try:
        return ast.parse(path.read_text())
    except (SyntaxError, UnicodeDecodeError):
        return None


def _literal_binding(name: str, module: ast.Module,
                     depth: int = 0) -> tuple[ast.AST, ast.Module] | None:
    """The value an upper-case name is bound to at module level, and that module: an
    assignment in the module itself, or in the real (non-test) module it imports the name
    from."""
    if depth > 4:
        return None
    for item in module.body:
        if (isinstance(item, ast.Assign) and len(item.targets) == 1
                and isinstance(item.targets[0], ast.Name) and item.targets[0].id == name):
            return item.value, module
        if (isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name)
                and item.target.id == name and item.value is not None):
            return item.value, module
    for item in module.body:
        if not (isinstance(item, ast.ImportFrom) and item.level == 0 and item.module
                and not item.module.startswith("tests")):
            continue
        for alias in item.names:
            if (alias.asname or alias.name) != name:
                continue
            source = _module_tree(item.module)
            if source is not None:
                return _literal_binding(alias.name, source, depth + 1)
    return None


def _fixed(value: ast.AST | None, module: ast.Module | None, depth: int = 0) -> bool:
    """One scalar made only of constants and upper-case names bound at module level to
    such a scalar (`410 * MIB`, with `MIB = 1024**2`): never a list, a dict or a row set."""
    if depth > 8:
        return False
    if isinstance(value, ast.Constant):
        return value.value is None or isinstance(value.value, str | int | float)
    if isinstance(value, ast.Name):
        if not value.id.isupper() or module is None:
            return False
        bound = _literal_binding(value.id, module)
        return bound is not None and _fixed(bound[0], bound[1], depth + 1)
    if isinstance(value, ast.UnaryOp):
        return _fixed(value.operand, module, depth + 1)
    if isinstance(value, ast.BinOp):
        return _fixed(value.left, module, depth + 1) and _fixed(value.right, module, depth + 1)
    return False


def _fixed_answer(value: ast.AST | None, declared: str, module: ast.Module) -> bool:
    """The method's answer is one fixed scalar, or exactly the answer its entry declares,
    which is itself a scalar or a dict or tuple of fixed scalars."""
    if not declared:
        return _fixed(value, module)
    try:
        expected = ast.parse(declared, mode="eval").body
    except SyntaxError:
        return False
    if value is None or ast.dump(value) != ast.dump(expected):
        return False
    if isinstance(expected, ast.Dict):
        return all(key is not None and _fixed(key, module) for key in expected.keys) and all(
            _fixed(item, module) for item in expected.values)
    if isinstance(expected, ast.Tuple):
        return all(_fixed(item, module) for item in expected.elts)
    return _fixed(expected, module)


def _statement_list(holder: ast.AST | None, statement: ast.stmt) -> list | None:
    """The statement list of `holder` that holds `statement`."""
    for name in ("body", "orelse", "finalbody"):
        items = getattr(holder, name, None)
        if isinstance(items, list) and any(item is statement for item in items):
            return items
    return None


def _refusal_asserted(call: ast.Call, parents: dict, refused: str, match: str) -> bool:
    """The refusal the entry names is asserted on this call, and nothing else can satisfy
    it: with a `match`, the call's statement is the only statement of a `with
    pytest.raises(<refused>, match=<match>)`; otherwise the call is bound once to a name,
    never rebound in its function, and a later statement of the same block is exactly
    `assert not <name>.<refused>`."""
    if not refused:
        return False
    statement = call
    while statement in parents and not isinstance(statement, ast.stmt):
        statement = parents[statement]
    holder = parents.get(statement)
    if match:
        if not (isinstance(holder, ast.With | ast.AsyncWith) and len(holder.body) == 1
                and holder.body[0] is statement and len(holder.items) == 1):
            return False
        raised = holder.items[0].context_expr
        return (isinstance(raised, ast.Call) and text(raised.func).endswith("raises")
                and len(raised.args) == 1 and text(raised.args[0]) == refused
                and any(item.arg == "match" and isinstance(item.value, ast.Constant)
                        and item.value.value == match for item in raised.keywords))
    if not (isinstance(statement, ast.Assign) and statement.value is call
            and len(statement.targets) == 1 and isinstance(statement.targets[0], ast.Name)):
        return False
    bound, scope = statement.targets[0].id, statement
    while scope in parents and not isinstance(scope, ast.FunctionDef | ast.AsyncFunctionDef):
        scope = parents[scope]
    if not isinstance(scope, ast.FunctionDef | ast.AsyncFunctionDef):
        return False
    stores = [item for item in ast.walk(scope) if isinstance(item, ast.Name)
              and item.id == bound and isinstance(item.ctx, ast.Store | ast.Del)]
    block = _statement_list(holder, statement)
    if len(stores) != 1 or block is None:
        return False
    later = block[[index for index, item in enumerate(block) if item is statement][0] + 1:]
    return any(isinstance(item, ast.Assert) and isinstance(item.test, ast.UnaryOp)
               and isinstance(item.test.op, ast.Not)
               and isinstance(item.test.operand, ast.Attribute)
               and item.test.operand.attr == refused
               and isinstance(item.test.operand.value, ast.Name)
               and item.test.operand.value.id == bound
               for item in later)


def fixed_problem(node: ast.AST, module: ast.Module | None,
                  entry: Listed | None = None) -> str | None:
    """Step 98(d)'s fixed-answer stub for a refusal that real data cannot reach (your
    answer of 2026-11-11, "Rewrite, keep two"): a class with no state, whose every method
    only asserts on its input and returns one fixed scalar, or the answer its entry
    declares; and it is made once, passed only to the call whose refusal, as the entry
    names it, the test asserts."""
    if not isinstance(node, ast.ClassDef) or module is None:
        return "a fixed-answer stub is a test-defined class in its own module"
    methods = _methods(node)
    if not methods:
        return "a fixed-answer stub answers through its methods"
    declared = entry.answer if entry is not None else ""
    refused = entry.refused if entry is not None else ""
    match = entry.match if entry is not None else ""
    for index, item in enumerate(node.body):
        docstring = (index == 0 and isinstance(item, ast.Expr)
                     and isinstance(item.value, ast.Constant))
        if not docstring and not isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef):
            return ("a fixed-answer stub's answer is only the fixed value the refusal needs; "
                    f"it holds no state (line {item.lineno})")
    for method in methods:
        body = _body(method)
        if (method.name == "__init__" or not body or not isinstance(body[-1], ast.Return)
                or not all(isinstance(item, ast.Assert) for item in body[:-1])
                or not _fixed_answer(body[-1].value, declared, module)):
            return ("a fixed-answer stub's answer is only the fixed value the refusal needs "
                    f"(line {method.lineno})")
    parents = {child: parent for parent in ast.walk(module)
               for child in ast.iter_child_nodes(parent)}
    uses = [item for item in ast.walk(module) if isinstance(item, ast.Name)
            and item.id == node.name and isinstance(item.ctx, ast.Load)]
    if len(uses) != 1:
        return f"a fixed-answer stub is made once ({len(uses)} uses of {node.name})"
    made = parents.get(uses[0])
    passed = parents.get(made)
    if isinstance(passed, ast.keyword):
        passed = parents.get(passed)
    if not (isinstance(made, ast.Call) and made.func is uses[0] and isinstance(passed, ast.Call)
            and (made in passed.args or any(item.value is made for item in passed.keywords))):
        return "a fixed-answer stub is passed straight to the call whose refusal is asserted"
    if not _refusal_asserted(passed, parents, refused, match):
        return ("a fixed-answer stub is passed only to a call whose refusal the test asserts "
                f"({refused or 'no refusal named'})")
    return None


def shape_problem(kind: str, node: ast.AST, name: str = "",
                  saved: frozenset = frozenset(), real: frozenset = frozenset(),
                  members: tuple = (), module: ast.Module | None = None,
                  entry: Listed | None = None) -> str | None:
    """Why a listed double's body is not of its kind (each of its "+"-joined kinds), or
    None. `name` is the replaced callable's, `saved` the names its original is under,
    `real` the names its module binds to real (non-test) modules, `members` a namespace's
    resolved members, `module` the scanned module and `entry` the double's listing."""
    if "+" in kind:
        for part in kind.split("+"):
            problem = shape_problem(part, node, name, saved, real, members, module, entry)
            if problem is not None:
                return problem
        return None
    through = Through(name, saved, real, module)
    if kind == "raise-only":
        if _raise_only(node, module):
            return None
        return "a raise-only double's body only raises"
    if kind == "raise-injection":
        if isinstance(node, ast.Lambda):
            return None if through.holds(node) else "an injection calls through"
        if _raises(node) and through.holds(node):
            return None
        return "a raise-only injection raises and otherwise calls through"
    if kind == "sleep-spy":
        # L1-75: one more real statement, `SELECT pg_sleep(...)`, then the real call.
        if _calls_with(node, "pg_sleep(") and through.holds(node):
            return None
        return "a sleep spy runs pg_sleep through the real connection and calls through"
    if kind == "deadline-injection":
        if _sets_deadline(node) and through.holds(node):
            return None
        return "a deadline injection moves the deadline and calls through"
    if kind == "call-through":
        if through.holds(node):
            return None
        return "a call-through spy returns the replaced callable's value"
    if kind == "stub":
        return stub_problem(node, members, module)
    if kind == "fixed-answer":
        return fixed_problem(node, module, entry)
    return f"unknown kind {kind}"


def problems(hits: list[Hit], allowed: tuple[Listed, ...]) -> dict:
    """Unlisted hits, listed doubles that match no hit (their lines changed), and listed
    doubles whose body is not of their kind."""
    by_lines = {(item.file, item.start, item.end): item for item in allowed}
    unlisted = [hit for hit in hits if (hit.file, hit.start, hit.end) not in by_lines]
    matched = {(hit.file, hit.start, hit.end) for hit in hits}
    stale = [item for item in allowed if (item.file, item.start, item.end) not in matched]
    shapes = []
    for hit in hits:
        entry = by_lines.get((hit.file, hit.start, hit.end))
        if entry is not None and hit.node is not None:
            problem = shape_problem(entry.kind, hit.node, hit.name, hit.saved, hit.real,
                                    hit.members, hit.module, entry)
            if problem is not None:
                shapes.append((entry, problem))
    return {"unlisted": unlisted, "stale": stale, "shapes": shapes,
            "kinds": [item for item in allowed
                      if not set(item.kind.split("+")) <= KINDS]}


T = TESTS + "/"
RAISE_ONLY, INJECTION, STUB, THROUGH = "raise-only", "raise-injection", "stub", "call-through"
SLEEP, DEADLINE = "sleep-spy", "deadline-injection"
FIXED = "fixed-answer"
ALLOWED: tuple[Listed, ...] = (
    # U6's lane_flows.OwnDue (tests/u6_approved_export/lane_flows.py:59-74) has no entry:
    # by your answer of 2026-11-11 ("Own database"), integration/test_first_effects.py no
    # longer passes it and runs that case on a production stand-in of its own, where the
    # real `due_items` query answers only its rows. The scan still reads other units' test
    # trees, so a later use of such a double in U8 is a hit.
    # Raise-only spies and crash injections.
    Listed(T + "component/test_registry.py", 93, 94, RAISE_ONLY,
           "a refused manifest never reaches connect_database"),
    Listed(T + "operations/test_assemblies_alone.py", 143, 144, RAISE_ONLY,
           "a gate that let the realm reach its owners fails at OwnerTransactions"),
    Listed(T + "repository/test_catalogue.py", 68, 69, RAISE_ONLY,
           "the catalogue's crash between the line sync and the head replacement"),
    Listed(T + "operations/test_credential_release.py", 141, 142, RAISE_ONLY,
           "a connect that refuses: the released login is still wiped"),
    Listed(T + "operations/test_production_tool.py", 85, 87, RAISE_ONLY,
           "the tool's raise-only connect for cases refused before any connection "
           "(Step 98(d))"),
    Listed(T + "operations/test_scram_sites.py", 65, 67, RAISE_ONLY,
           "refusing_connect, set in the driver's place by Step 164's tests of each "
           "connection site: it refuses before any connection and carries the options it "
           "was asked for in its exception, where the test reads `require_auth`"),
    # Raise-only statement-failure injections: they raise where they intervene and call
    # through everywhere else.
    Listed(T + "operations/test_production_tool.py", 451, 451, INJECTION,
           "the connect that hands back FailingStatement over the real connection "
           "(Step 98(d))"),
    Listed(T + "operations/test_production_tool.py", 420, 440, INJECTION,
           "FailingStatement: the second pending file's own text raises; every other "
           "statement runs on the instance (Step 98(d))"),
    Listed(T + "component/test_account_mail.py", 490, 505, INJECTION,
           "RecordingConnection: it records each statement and calls through, and raises "
           "once right after the statement `fail_after` names has run. Its one raise "
           "serves both of Step 98(d)'s raise-only crash injections: after the outbox "
           "insert (Step 54(n), L1-69) and after the per-account count's upsert (Step "
           "54(q), L1-71)"),
    Listed(T + "integration/test_first_effects.py", 456, 457, INJECTION,
           "the system wrapper that hands its work Raising over the real connection "
           "(Step 98(d))"),
    Listed(T + "integration/test_first_effects.py", 438, 451, INJECTION,
           "Raising: the send-log insert raises after the reservation; every other "
           "statement runs on the realm (Step 98(d))"),
    Listed(T + "integration/test_sign_in_limits.py", 878, 888, INJECTION,
           "the denial's own write raises Busy; every other run calls through"),
    Listed(T + "integration/test_sign_in_limits.py", 1050, 1062, INJECTION,
           "each start meets a serialization failure on the real transactions"),
    Listed(T + "integration/test_u5_seams.py", 244, 254, INJECTION,
           "the first run of the work raises after it ran, so the real transaction rolls "
           "back and is retried"),
    Listed(T + "repository/test_owner_imports.py", 409, 413, INJECTION,
           "Step 69(h) (L1-75): the failing commit after the version's write, raise-only "
           "while armed"),
    Listed(T + "v1_flows.py", 91, 100, f"{INJECTION}+{SLEEP}+{DEADLINE}",
           "Step 69(h) (L1-75), Step 98(h): DeadlineConnection.execute before the "
           "projection INSERT of one version: `sleep`, a spy that first runs SELECT "
           "pg_sleep(3.5) through the same bounded connection, which the realm's 3 s "
           "statement bound cancels; `deadline`, a spy that moves the deadline into the "
           "past so the real remaining() raises; an exception, raise-only (OperationalError "
           "and Busy). The first two are L1-75's new kinds; every path calls through"),
    # Your answer of 2026-11-11 ("Rewrite, keep two"): the accepted realms' raise-only spy.
    # Its run records the owner in the sentinel it raises.
    Listed(T + "integration/test_signed_in_search.py", 155, 164, RAISE_ONLY,
           "AcceptedRealm: an accepted realm's admit reaches run, which records the owner "
           "in the sentinel it raises; no statement runs"),
    # Stubs that refuse before any connection or receive no statement. Each refuses or
    # raises, or never returns a value in place of the work's answer (the stub shape).
    Listed(T + "component/test_capacity.py", 69, 69, STUB,
           "a profile only: complete_capacity chooses U2's capacity without a store"),
    Listed(T + "component/test_capacity.py", 81, 81, STUB,
           "a profile only: the budgeted capacity refuses an earlier realm before any run"),
    Listed(T + "component/test_capacity.py", 157, 161, STUB,
           "a store that raises before any connection"),
    Listed(T + "component/test_corpus_limits.py", 311, 319, STUB,
           "RaiseOnlyTransactions raises before any connection"),
    Listed(T + "component/test_identity_providers.py", 311, 317, STUB,
           "Unwritten fails the test if anything would be written"),
    Listed(T + "component/test_outward_wiring.py", 168, 173, STUB,
           "Due: an unbounded preview batch is refused before any call; its due_items "
           "only raises"),
    Listed(T + "component/test_provider_activation.py", 151, 151, STUB,
           "a malformed id is refused before any transaction"),
    Listed(T + "component/test_u2_seam_defaults.py", 70, 70, STUB,
           "a profile only: no run exists"),
    Listed(T + "component/test_u2_seam_defaults.py", 78, 78, STUB,
           "capacity's rule without a store: no run exists"),
    Listed(T + "component/test_u2_seam_defaults.py", 141, 141, STUB,
           "a profile only: no run exists"),
    Listed(T + "component/test_u2_seam_defaults.py", 234, 238, STUB,
           "Unwritten fails the test on any write"),
    Listed(T + "component/test_u2_seam_defaults.py", 348, 352, STUB,
           "Unwritten fails the test on any write"),
    Listed(T + "database/test_composed_chain.py", 104, 111, STUB,
           "RecordingConnection for apply_migrations' conn: the drift refusal comes before "
           "any statement, and the test asserts it received none (Step 98(d))"),
    Listed(T + "component/test_u5_seam_defaults.py", 143, 143, STUB,
           "unconnected_repository: U5's allocation check refuses before any statement"),
    Listed(T + "integration/test_signed_in_search.py", 145, 145, STUB,
           "the realm check refuses before run is reached"),
    Listed(T + "integration/test_u2_fail_closed.py", 207, 208, STUB,
           "a profile only: refused on its realm before any run"),
    Listed(T + "integration/test_u2_fail_closed.py", 230, 230, STUB,
           "a profile only: refused on its realm before any run"),
    # Fixed-answer stubs for a refusal that real data cannot reach (your answer of
    # 2026-11-11, "Rewrite, keep two"): each answers only the fixed value its refusal
    # needs, and is made once, passed only to the call whose refusal the test asserts.
    Listed(T + "component/test_capacity.py", 55, 63, FIXED,
           "FootprintTransactions: the 410 MiB footprint U2's synthetic rule refuses, which "
           "a realm's own small database never holds; passed only to the refresh the test "
           "asserts refused",
           refused="admitting", answer="{'database_bytes': 410 * MIB, 'wal_bytes': 0}"),
    Listed(T + "integration/test_u5_seams.py", 273, 280, FIXED,
           "Ignoring: a sending row without its allowance reservation, which U5's real "
           "begin_send never answers; passed only to the start the test asserts refused",
           refused="ValueError", match="without its allowance reservation",
           answer="{'state': 'sending'}"),
    # Call-through spies and pass-through observers: they return the replaced callable's
    # value and replace nothing.
    Listed(T + "component/test_account_mail.py", 508, 524, THROUGH,
           "the pass-through recorder of the accounts transactions' statements (Steps "
           "54(k)-(n), (q)); its RecordingConnection is listed at its own lines (490-505)"),
    Listed(T + "component/test_complete_search.py", 223, 232, THROUGH,
           "the pass-through recorder of the discovery transaction (Step 55(c))"),
    Listed(T + "component/test_complete_search.py", 207, 220, THROUGH,
           "_ObservedConnection, the recorder's connection: it notes each statement and "
           "calls through (Step 55(c))"),
    Listed(T + "component/test_u2_seam_defaults.py", 190, 200, THROUGH,
           "Recorder: a pass-through recorder over the realm's own connection (Step 98(d))"),
    Listed(T + "component/test_u5_seam_defaults.py", 93, 95, THROUGH,
           "prepared_runs, recorded and answered by the real repository (Step 98(d))"),
    Listed(T + "component/test_u5_seam_defaults.py", 97, 99, THROUGH,
           "begin_send, recorded and answered by the real repository (Step 98(d))"),
    Listed(T + "integration/test_complete_usage.py", 150, 151, THROUGH,
           "the real transactions' run under an earlier realm's name"),
    Listed(T + "integration/test_first_effects.py", 625, 628, THROUGH,
           "begin_send, then the hold lands; the real answer is returned"),
    Listed(T + "integration/test_production_import_runner.py", 276, 278, THROUGH,
           "OwnerTransactions.close, counted and called through"),
    Listed(T + "integration/test_rehearsal_bound.py", 226, 239, THROUGH,
           "the real export store, the gate installed just after its claim"),
    Listed(T + "operations/test_credential_release.py", 96, 100, THROUGH,
           "the default psycopg.connect, its options recorded"),
    Listed(T + "operations/test_drivers.py", 426, 428, THROUGH,
           "the realm driver's own _connect, each login recorded (Step 98(d))"),
    Listed(T + "operations/test_drivers.py", 861, 863, THROUGH,
           "the arrangement driver's default psycopg.connect, its options recorded "
           "(Step 98(d))"),
    Listed(T + "operations/test_production_cutover_wiring.py", 283, 285, THROUGH,
           "v1_account_reader's connect: psycopg.connect, its options recorded (Step 98(d))"),
    Listed(T + "operations/test_production_tool.py", 120, 123, THROUGH,
           "the tool's default connect on the production-shaped instance, each login "
           "recorded (Step 98(d))"),
    Listed(T + "operations/test_production_tool.py", 2739, 2741, THROUGH,
           "the tool's default connect around every test of the file: each connection's "
           "`require_auth` is noted and the real connect answers (Step 164(d))"),
    Listed(T + "component/test_transactions_scram.py", 249, 260, THROUGH,
           "CountingConnection, set as OwnerTransactions' bounded connection's `connection`: "
           "it counts each execute and calls through to the raw connection (Step 52(a))"),
    Listed(T + "repository/test_search_candidates.py", 284, 302, THROUGH,
           "the settings wrapper's connection proxy (Step 50(c)): it forwards every call "
           "and adds two current_setting reads on the same connection"),
    Listed(T + "repository/test_search_candidates.py", 305, 314, THROUGH,
           "the settings wrapper (Step 50(c)): its proxy forwards every call and adds two "
           "current_setting reads"),
)
# `scripts/u8_phases.py`'s `lambda: runner.connect_admin(value)` passed for `connect` are the
# realm's real admin connector, not doubles, so the scan no longer reports them
# (`REAL_CONNECTORS`) and they need no entry.
# Step 98(h): where L1-75's injections are used, by file and line (each line names the
# injection it holds); the injection itself is v1_flows.py's entry above, and the raise-only
# database error at a v1 read is the last line, a stub on V1Source, which is not on the
# never-mocked list.
TIME_REFUSAL_USES = (
    (T + "repository/test_owner_imports.py", 366, "vf.refusing(source.version, how)"),
    (T + "repository/test_owner_imports.py", 395, "vf.refusing(source.version, error)"),
    (T + "repository/test_owner_imports.py", 417, 'vf.refusing(source.version, "sleep"'),
    (T + "integration/test_import_operations.py", 254, 'vf.refusing("arxiv:2101.00006@v1"'),
    (T + "integration/test_migration_run.py", 385, 'vf.refusing("arxiv:2101.00006@v1"'),
    (T + "integration/test_production_import_runner.py", 414,
     'v1_flows.refusing("arxiv:2101.00006@v1", "sleep")'),
    (T + "integration/test_production_import_runner.py", 450,
     'v1_flows.refusing("arxiv:2101.00006@v1", error)'),
    (T + "integration/test_migration_run.py", 410, 'monkeypatch.setattr(V1Source, "saved"'),
)


def describe(found: dict) -> str:
    lines = [f"unlisted {hit.file}:{hit.start}-{hit.end} {hit.part} ({hit.how})"
             for hit in found["unlisted"]]
    lines += [f"stale entry {item.file}:{item.start}-{item.end}" for item in found["stale"]]
    lines += [f"shape {entry.file}:{entry.start}-{entry.end}: {problem}"
              for entry, problem in found["shapes"]]
    lines += [f"kind {item.file}:{item.start}" for item in found["kinds"]]
    return "\n".join(lines)


def refusal_sites(files: dict[str, str]) -> set[tuple[str, int]]:
    """Every call of `v1_flows.refusing(...)` (L1-75's injections), by file and line."""
    sites = set()
    for path, source in files.items():
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Call) and text(node.func).split(".")[-1] == "refusing":
                sites.add((path, node.lineno))
    return sites


@pytest.fixture(scope="module", autouse=True)
def parsed_trees_released():
    """The scan's parsed trees are freed when this module ends, so the rest of the part
    does not carry them."""
    yield
    release_caches()


def test_no_test_replaces_a_part_the_instructions_never_mock():
    files = scanned_files()
    found = problems(scan(files), ALLOWED)
    assert not any(found.values()), describe(found)
    # Step 98(h): L1-75's injections are used where they are listed, and nowhere else.
    for file, line, used in TIME_REFUSAL_USES:
        assert used in (ROOT / file).read_text().splitlines()[line - 1], (file, line)
    assert refusal_sites(files) == {(file, line) for file, line, used in TIME_REFUSAL_USES
                                    if "refusing(" in used}


PLANTED = {
    "recording OwnerTransactions": (f"{T}operations/planted_a.py", (
        "from backend import transactions\n"
        "class Recording:\n"
        "    def run(self, owner, action):\n"
        "        return action(None)\n"
        "def test_x(monkeypatch):\n"
        "    monkeypatch.setattr(transactions, 'OwnerTransactions', Recording)\n")),
    "stub ledger in integration": (f"{T}integration/planted_b.py", (
        "class StubLedger:\n"
        "    def records(self, kind):\n"
        "        return []\n"
        "    def revision(self):\n"
        "        return 0\n"
        "    def get(self, kind, key):\n"
        "        return None\n")),
    "double by position for a connection": (f"{T}operations/planted_d.py", (
        "def build(connection, name):\n"
        "    return connection, name\n"
        "class Fake:\n"
        "    def execute(self, query):\n"
        "        return []\n"
        "def test_x():\n"
        "    build(Fake(), 'x')\n")),
    "double assigned to a repository attribute": (f"{T}component/planted_e.py", (
        "from types import SimpleNamespace\n"
        "def test_x(scheduler):\n"
        "    scheduler.repository = SimpleNamespace(begin_send=lambda *a: None)\n")),
    "system wrapper answering no row": (f"{T}integration/planted_f.py", (
        "def test_x(monkeypatch, repository):\n"
        "    monkeypatch.setattr(repository, 'system', lambda work: None)\n")),
    "recording connection for connect in operations": (f"{T}operations/planted_g.py", (
        "from docsuri_ops import production_tool as tool\n"
        "class Connection:\n"
        "    def execute(self, statement):\n"
        "        return []\n"
        "def connect(**options):\n"
        "    return Connection()\n"
        "def test_x():\n"
        "    tool.ToolContext(connect=connect)\n")),
    # The review of build batch 9b: each path the first scan could not see.
    "connection by position to a fixture-bound callee": (f"{T}database/planted_i.py", (
        "class Recording:\n"
        "    def execute(self, statement):\n"
        "        return []\n"
        "def test_x(runner):\n"
        "    runner.apply_migrations(Recording(), {})\n")),
    "connection to a callback nothing is known of": (f"{T}component/planted_j.py", (
        "class Recording:\n"
        "    def execute(self, statement):\n"
        "        return []\n"
        "def test_x(callback):\n"
        "    callback(Recording())\n")),
    "connection assigned to a connection attribute": (f"{T}component/planted_k.py", (
        "class Counting:\n"
        "    def execute(self, statement):\n"
        "        return []\n"
        "def work(bounded):\n"
        "    bounded.connection = Counting()\n")),
    "the archive writer replaced": (f"{T}operations/planted_l.py", (
        "from docsuri_ops.backup_agent import writing\n"
        "class Fake:\n"
        "    def write(self, data):\n"
        "        return None\n"
        "def test_x(monkeypatch):\n"
        "    monkeypatch.setattr(writing, 'ArchiveWriter', Fake)\n")),
    "the archive writer's write replaced": (f"{T}operations/planted_m.py", (
        "from docsuri_ops.backup_agent import writing\n"
        "def test_x(monkeypatch):\n"
        "    monkeypatch.setattr(writing.ArchiveWriter, 'write', lambda *a: None)\n")),
    "the transactions fixture's run replaced": (f"{T}component/planted_n.py", (
        "def test_x(monkeypatch, transactions):\n"
        "    monkeypatch.setattr(transactions, 'run', lambda owner, work: None)\n")),
    "a connection's execute replaced": (f"{T}component/planted_o.py", (
        "def test_x(monkeypatch, conn):\n"
        "    monkeypatch.setattr(conn, 'execute', lambda *a: [])\n")),
    "connect replaced by another attribute": (f"{T}operations/planted_p.py", (
        "import psycopg\n"
        "from tests.u8_service_operations_integration import host_flows as helpers\n"
        "def test_x(monkeypatch):\n"
        "    monkeypatch.setattr(psycopg, 'connect', helpers.fake_connect)\n")),
    "the conftest connect fixture defined again": (f"{T}operations/planted_q.py", (
        "import pytest\n"
        "@pytest.fixture\n"
        "def connect(realm):\n"
        "    return None\n")),
    # The re-review of build batch 9b: each path the fix pass still let through.
    "psycopg.connect replaced by a test helper's connect": (f"{T}operations/planted_u.py", (
        "import psycopg\n"
        "from tests.u8_service_operations_integration import host_flows as helpers\n"
        "def test_x(monkeypatch):\n"
        "    monkeypatch.setattr(psycopg, 'connect', helpers.connect)\n")),
    "a tool's connect set to the runner's admin login": (f"{T}operations/planted_v.py", (
        "from docsuri_ops import production_tool as tool\n"
        "def test_x(monkeypatch, runner, value):\n"
        "    monkeypatch.setattr(tool, '_connect', lambda **o: runner.connect_admin(value))\n")),
    "a driver's connect assigned the runner's admin login": (f"{T}operations/planted_w.py", (
        "from scripts.verify_docsuri_u8 import connect_admin\n"
        "def work(driver, value):\n"
        "    driver._connect = lambda **o: connect_admin(value)\n")),
    "psycopg.connect assigned an unresolved value": (f"{T}operations/planted_x.py", (
        "import psycopg\n"
        "from unittest.mock import MagicMock\n"
        "def work():\n"
        "    psycopg.connect = MagicMock()\n")),
    "a bounded connection assigned an unresolved value": (f"{T}component/planted_y.py", (
        "from unittest.mock import MagicMock\n"
        "def work(bounded):\n"
        "    bounded.connection = MagicMock()\n")),
    "a function connect by position to a fixture-bound callee": (f"{T}database/planted_z.py", (
        "def planted_open(connect, name):\n"
        "    return connect, name\n"
        "def fake_connect(**options):\n"
        "    return None\n"
        "def test_x(helper):\n"
        "    helper.planted_open(fake_connect, 'x')\n")),
    "an OwnDue-shaped repository by position to a fixture-bound callee": (
        f"{T}integration/planted_aa.py", (
            "class OwnDue:\n"
            "    def __init__(self, repository, ids):\n"
            "        self._repository, self._ids = repository, set(ids)\n"
            "    def due_items(self, now, limit=None):\n"
            "        rows = self._repository.due_items(now)\n"
            "        return [row for row in rows if row['id'] in self._ids]\n"
            "    def __getattr__(self, name):\n"
            "        return getattr(self._repository, name)\n"
            "def planted_pass(repository, lane):\n"
            "    return repository, lane\n"
            "def test_x(helper, repo):\n"
            "    helper.planted_pass(OwnDue(repo, []), None)\n")),
    # The re-review of build batch 10a: the ledger's surface, and a connection's `execute`,
    # offered as class-attribute lambdas.
    "a ledger offered as lambdas in integration": (f"{T}integration/planted_ab.py", (
        "class Book:\n"
        "    records = lambda self, kind: []\n"
        "    revision = lambda self: 0\n"
        "    get = lambda self, kind, key: None\n")),
    "an execute lambda to a callback nothing is known of": (f"{T}component/planted_ac.py", (
        "class Recording:\n"
        "    execute = lambda self, statement: []\n"
        "def test_x(callback):\n"
        "    callback(Recording())\n")),
}


def test_each_planted_replacement_fails_the_scan():
    """Step 98(d)'s planted cases, built in memory: each is a hit no entry allows."""
    for name, (path, source) in PLANTED.items():
        found = problems(scan({path: source}), ())
        assert found["unlisted"], name
        assert all(hit.file == path for hit in found["unlisted"]), name
    # A listed spy that returns: listed raise-only, its body returns, so its shape fails.
    path = f"{T}operations/planted_c.py"
    source = ("import psycopg\n"
              "def spy(**options):\n"
              "    return None\n"
              "def test_x(monkeypatch):\n"
              "    monkeypatch.setattr(psycopg, 'connect', spy)\n")
    (hit,) = scan({path: source})
    listed = (Listed(path, hit.start, hit.end, RAISE_ONLY, "planted"),)
    found = problems([hit], listed)
    assert found["unlisted"] == [] and found["shapes"], found
    # The same spy listed as what it is, call-through, still fails: it returns no call.
    assert problems([hit], (Listed(path, hit.start, hit.end, THROUGH, "planted"),))["shapes"]
    # A listed double whose lines moved fails until its entry is updated.
    moved = (Listed(path, hit.start + 1, hit.end + 1, RAISE_ONLY, "planted"),)
    found = problems([hit], moved)
    assert found["unlisted"] and found["stale"]
    # A double imported from another test module is found at its own file and lines.
    helper = f"{T}planted_helpers.py"
    found = problems(scan({
        helper: ("class FakeTransactions:\n"
                 "    def run(self, owner, work):\n"
                 "        return work(None)\n"),
        f"{T}operations/planted_r.py": (
            "from tests.u8_service_operations_integration.planted_helpers import "
            "FakeTransactions\n"
            "def build(transactions):\n"
            "    return transactions\n"
            "def test_x():\n"
            "    build(transactions=FakeTransactions())\n")}), ())
    assert [(item.file, item.start) for item in found["unlisted"]] == [(helper, 1)]
    # So is a double another unit's test helpers define (the re-review of build batch 9b:
    # U6's lane_flows.OwnDue is the case in today's tree).
    other_unit = "tests/u6_approved_export/planted_helpers.py"
    found = problems(scan({
        other_unit: ("class OwnDue:\n"
                     "    def due_items(self, now):\n"
                     "        return []\n"),
        f"{T}integration/planted_t.py": (
            "from tests.u6_approved_export.planted_helpers import OwnDue\n"
            "def build(repository):\n"
            "    return repository\n"
            "def test_x():\n"
            "    build(OwnDue())\n")}), ())
    assert [(item.file, item.start) for item in found["unlisted"]] == [(other_unit, 1)]
    # A listed class whose `execute` only records, and a spy that can fall off its end,
    # fail their call-through shape; so does a spy calling a test helper's `connect`.
    shaped = {
        "a recorder that never calls through": ("import psycopg\n"
                                                "class Recording:\n"
                                                "    def __init__(self, conn):\n"
                                                "        self.conn, self.seen = conn, []\n"
                                                "    def execute(self, query):\n"
                                                "        self.seen.append(query)\n"
                                                "real = psycopg.connect\n"
                                                "def test_x(monkeypatch):\n"
                                                "    monkeypatch.setattr(psycopg, 'connect', "
                                                "lambda **o: Recording(real(**o)))\n", 2),
        "a spy that falls off its end": ("import psycopg\n"
                                         "real = psycopg.connect\n"
                                         "def spy(**options):\n"
                                         "    if options:\n"
                                         "        return real(**options)\n"
                                         "def test_x(monkeypatch):\n"
                                         "    monkeypatch.setattr(psycopg, 'connect', spy)\n", 3),
        "a spy calling a test helper's connect": (
            "import psycopg\n"
            "from tests.u8_service_operations_integration import host_flows as fakes\n"
            "def spy(**options):\n"
            "    return fakes.connect(**options)\n"
            "def test_x(monkeypatch):\n"
            "    monkeypatch.setattr(psycopg, 'connect', spy)\n", 3),
    }
    for label, (source, line) in shaped.items():
        hits = scan({path: source})
        listed = tuple(Listed(path, item.start, item.end, THROUGH, "planted") for item in hits)
        assert [entry.start for entry, _ in problems(hits, listed)["shapes"]] == [line], label
    # Listed call-through doubles that answer in place of the part fail their shape: a spy
    # returning a test-defined class's instance, and a lambda returning a fake connection.
    for source in ("import psycopg\n"
                   "class Recording:\n"
                   "    def execute(self, statement):\n"
                   "        return []\n"
                   "def spy(**options):\n"
                   "    return Recording()\n"
                   "def test_x(monkeypatch):\n"
                   "    monkeypatch.setattr(psycopg, 'connect', spy)\n",
                   "import psycopg\n"
                   "class FakeConnection:\n"
                   "    def execute(self, statement):\n"
                   "        return []\n"
                   "def test_x(monkeypatch):\n"
                   "    monkeypatch.setattr(psycopg, 'connect', lambda **o: FakeConnection())\n"):
        hits = scan({path: source})
        assert hits, source
        listed = tuple(Listed(path, item.start, item.end, THROUGH, "planted") for item in hits)
        assert problems(hits, listed)["shapes"], source
    # The same spy that returns the real call passes as call-through.
    hits = scan({path: ("import psycopg\n"
                        "def spy(**options):\n"
                        "    return psycopg.connect(**options)\n"
                        "def test_x(monkeypatch):\n"
                        "    monkeypatch.setattr(psycopg, 'connect', spy)\n")})
    listed = tuple(Listed(path, item.start, item.end, THROUGH, "planted") for item in hits)
    assert hits and not problems(hits, listed)["shapes"]
    # L1-75's kinds: a spy listed as a sleep spy without its pg_sleep, or as a deadline
    # injection that moves no deadline, fails its shape.
    for kind in (SLEEP, DEADLINE):
        listed = tuple(Listed(path, item.start, item.end, kind, "planted") for item in hits)
        assert problems(hits, listed)["shapes"], kind
    # A use of L1-75's injections that TIME_REFUSAL_USES does not list is found.
    planted = {f"{T}integration/planted_s.py": ("from tests.u8_service_operations_integration "
                                                "import v1_flows\n"
                                                "def test_x():\n"
                                                "    with v1_flows.refusing('v', 'sleep'):\n"
                                                "        pass\n")}
    assert refusal_sites(planted) == {(f"{T}integration/planted_s.py", 3)}


def shapes_of(source: str, kind: str, **declared: str) -> list:
    """Each hit of a planted module, listed under `kind` (with a fixed-answer entry's
    `refused`, `match` and `answer`): the shape problems found."""
    path = f"{T}component/planted_shape.py"
    hits = scan({path: source})
    assert hits, source
    listed = tuple(Listed(path, item.start, item.end, kind, "planted", **declared)
                   for item in hits)
    found = problems(hits, listed)
    assert found["unlisted"] == [] and found["stale"] == [], found
    return found["shapes"]


# Your answer of 2026-11-11 ("Rewrite, keep two"): one well-shaped double of each rule and
# one planted break of each.
STUB_SOURCES = {
    "a store that raises": ("class Failing:\n"
                            "    def run(self, owner, work):\n"
                            "        raise ValueError('store unavailable')\n"
                            "def test_x(build):\n"
                            "    build(transactions=Failing())\n"),
    "a run handing its work no connection": (
        "from types import SimpleNamespace\n"
        "def test_x(build):\n"
        "    build(transactions=SimpleNamespace(run=lambda owner, work: work(None)))\n"),
    "a recorder that answers nothing": ("class Recording:\n"
                                        "    def __init__(self):\n"
                                        "        self.seen = []\n"
                                        "    def execute(self, statement):\n"
                                        "        self.seen.append(statement)\n"
                                        "def test_x(build):\n"
                                        "    build(conn=Recording())\n"),
}
BROKEN_STUBS = {
    "a due list in place of the store's answer": (
        "class Due:\n"
        "    def __init__(self, rows):\n"
        "        self.rows = rows\n"
        "    def due_items(self, now, *, limit):\n"
        "        return self.rows[:limit]\n"
        "def test_x(build):\n"
        "    build(repository=Due([]))\n"),
    "a namespace whose run answers 7": (
        "from types import SimpleNamespace\n"
        "def test_x(build):\n"
        "    build(transactions=SimpleNamespace(run=lambda owner, work: 7))\n"),
    "a namespace whose named run answers rows": (
        "from types import SimpleNamespace\n"
        "def test_x(build):\n"
        "    def run(owner, work):\n"
        "        return []\n"
        "    build(transactions=SimpleNamespace(run=run))\n"),
    "a class-attribute lambda that answers rows": (
        "class Due:\n"
        "    due_items = lambda self, now, *, limit: [{'kind': 'execute', 'id': 'x'}]\n"
        "def test_x(build):\n"
        "    build(repository=Due())\n"),
    # The re-review of build batch 10a: the four shapes the first fix still let through.
    "a class attribute bound to a module-level function": (
        "def answer(self, now, *, limit):\n"
        "    return [{'kind': 'execute'}]\n"
        "class Due:\n"
        "    due_items = answer\n"
        "def test_x(build):\n"
        "    build(repository=Due())\n"),
    "a staticmethod lambda that answers rows": (
        "class Due:\n"
        "    due_items = staticmethod(lambda now, *, limit: [{'kind': 'execute'}])\n"
        "def test_x(build):\n"
        "    build(repository=Due())\n"),
    "a parameter its __init__ sets as run over the raising method": (
        "class Accepted:\n"
        "    def __init__(self, answer):\n"
        "        self.run = answer\n"
        "    def run(self, owner, work):\n"
        "        raise ValueError(owner)\n"
        "def test_x(build, answer):\n"
        "    build(transactions=Accepted(answer))\n"),
    "a namespace member that is a bound method": (
        "from types import SimpleNamespace\n"
        "class Rows:\n"
        "    def run(self, owner, work):\n"
        "        return [{'id': 1}]\n"
        "def test_x(build):\n"
        "    build(transactions=SimpleNamespace(run=Rows().run))\n"),
}
# A call-through wrapper: its one method returns the wrapped connection's own answer.
THROUGH_SOURCE = ("class Spy:\n"
                  "    def __init__(self, inner):\n"
                  "        self.inner = inner\n"
                  "    def execute(self, statement):\n"
                  "        return self.inner.execute(statement)\n"
                  "def test_x(build, raw):\n"
                  "    build(conn=Spy(raw))\n")
BROKEN_THROUGH = {
    "an answering class-attribute lambda": THROUGH_SOURCE.replace(
        "class Spy:\n", "class Spy:\n    fetchall = lambda self: [{'id': 1}]\n"),
    "an answering lambda its __init__ assigns": THROUGH_SOURCE.replace(
        "        self.inner = inner\n",
        "        self.inner = inner\n        self.fetchall = lambda: [{'id': 1}]\n"),
}
FIXED_SOURCE =("import pytest\n"
                "MIB = 1024 * 1024\n"
                "class Footprint:\n"
                "    def run(self, owner, action):\n"
                "        assert owner == 'operations'\n"
                "        return {'database_bytes': 410 * MIB, 'wal_bytes': 0}\n"
                "def test_x(Capacity):\n"
                "    above = Capacity(transactions=Footprint())\n"
                "    above.refresh()\n"
                "    assert not above.admitting\n")
# The planted entry names the refusal and the answer, as each real fixed-answer entry does.
FIXED_DECLARED = {"refused": "admitting",
                  "answer": "{'database_bytes': 410 * MIB, 'wal_bytes': 0}"}
RAISES_SOURCE = FIXED_SOURCE.replace(
    "    above = Capacity(transactions=Footprint())\n    above.refresh()\n"
    "    assert not above.admitting\n",
    "    with pytest.raises(ValueError, match='refused'):\n"
    "        Capacity(transactions=Footprint())\n")
RAISES_DECLARED = {**FIXED_DECLARED, "refused": "ValueError", "match": "refused"}
BROKEN_FIXED = {
    "an answer that is not one fixed value": (FIXED_SOURCE.replace(
        "410 * MIB", "owner.footprint"), "only the fixed value", FIXED_DECLARED),
    "a stub with state that can vary its answer": (FIXED_SOURCE.replace(
        "class Footprint:\n", "class Footprint:\n"
        "    def __init__(self, footprint=410):\n"
        "        self.footprint = footprint\n"), "only the fixed value", FIXED_DECLARED),
    "a row-list answer": (FIXED_SOURCE.replace(
        "{'database_bytes': 410 * MIB, 'wal_bytes': 0}", "[{'kind': 'execute', 'id': 'x'}]"),
        "only the fixed value", FIXED_DECLARED),
    "a row-list answer with no declared answer": (FIXED_SOURCE.replace(
        "{'database_bytes': 410 * MIB, 'wal_bytes': 0}", "[{'kind': 'execute', 'id': 'x'}]"),
        "only the fixed value", {"refused": "admitting"}),
    "made for two calls": (FIXED_SOURCE.replace(
        "    above.refresh()\n", "    above.refresh()\n"
        "    Capacity(transactions=Footprint()).refresh()\n"), "made once", FIXED_DECLARED),
    "passed to a call whose refusal is not asserted": (FIXED_SOURCE.replace(
        "    assert not above.admitting\n", "    assert above.admitting\n"),
        "whose refusal the test asserts", FIXED_DECLARED),
    "a success-shaped negation": (FIXED_SOURCE.replace(
        "    assert not above.admitting\n", "    assert not above.failed\n"),
        "whose refusal the test asserts", FIXED_DECLARED),
    "a name rebound before the assert": (FIXED_SOURCE.replace(
        "    assert not above.admitting\n",
        "    above = Capacity(transactions=None)\n    assert not above.admitting\n"),
        "whose refusal the test asserts", FIXED_DECLARED),
    "a raises block whose later statement raises": (RAISES_SOURCE.replace(
        "        Capacity(transactions=Footprint())\n",
        "        Capacity(transactions=Footprint())\n        raise ValueError('refused')\n"),
        "whose refusal the test asserts", RAISES_DECLARED),
    "passed through a name, not to the refused call": (FIXED_SOURCE.replace(
        "    above = Capacity(transactions=Footprint())\n",
        "    footprint = Footprint()\n"
        "    above = Capacity(transactions=footprint)\n"), "passed straight", FIXED_DECLARED),
}


def test_the_stub_raise_only_and_fixed_answer_shapes_hold_and_each_break_fails():
    """Step 98(d)'s shapes, by your answer of 2026-11-11: a stub refuses or raises, or never
    returns a value in place of the work's answer; a raise-only class only raises; a
    fixed-answer stub answers only the fixed value its refusal needs and is passed only to
    the call whose refusal the test asserts. Each rule holds for a well-shaped double, and
    a planted break of each fails, naming the rule."""
    for label, source in STUB_SOURCES.items():
        assert shapes_of(source, STUB) == [], label
    for label, source in BROKEN_STUBS.items():
        found = shapes_of(source, STUB)
        assert [problem for _, problem in found] and all(
            "a stub refuses or raises" in problem for _, problem in found), label
    # The raise-only kind takes a class whose `__init__` only stores attributes and whose
    # other methods only raise; a method that records and returns fails it.
    raising = ("class Reached(Exception):\n"
               "    pass\n"
               "class Accepted:\n"
               "    def __init__(self, realm):\n"
               "        self.realm = realm\n"
               "    def run(self, owner, work):\n"
               "        raise Reached(owner)\n"
               "def test_x(build):\n"
               "    build(transactions=Accepted('production'))\n")
    assert shapes_of(raising, RAISE_ONLY) == []
    recording = raising.replace("        raise Reached(owner)\n",
                                "        self.realm.append(owner)\n        return 7\n")
    assert [problem for _, problem in shapes_of(recording, RAISE_ONLY)] == [
        "a raise-only double's body only raises"]
    # A callable its `__init__` assigns is offered too: an answering lambda fails it.
    assigning = raising.replace("        self.realm = realm\n",
                                "        self.realm = realm\n"
                                "        self.answer = lambda owner, work: ['row']\n")
    assert [problem for _, problem in shapes_of(assigning, RAISE_ONLY)] == [
        "a raise-only double's body only raises"]
    # A parameter its `__init__` sets over the raising method answers in its place.
    shadowing = raising.replace("    def __init__(self, realm):\n        self.realm = realm\n",
                                "    def __init__(self, realm, answer):\n"
                                "        self.realm = realm\n        self.run = answer\n"
                                ).replace("Accepted('production')",
                                          "Accepted('production', answer)").replace(
                                    "def test_x(build):", "def test_x(build, answer):")
    assert "self.run = answer" in shadowing
    assert [problem for _, problem in shapes_of(shadowing, RAISE_ONLY)] == [
        "a raise-only double's body only raises"]
    # A call-through wrapper calls through with every callable it offers.
    assert shapes_of(THROUGH_SOURCE, THROUGH) == []
    for label, source in BROKEN_THROUGH.items():
        assert source != THROUGH_SOURCE, label
        assert [problem for _, problem in shapes_of(source, THROUGH)] == [
            "a call-through spy returns the replaced callable's value"], label
    # A class-attribute or `__init__` lambda is the surface it offers, and so is a module
    # function a class attribute names.
    named = ast.parse("def answer(self, owner, work):\n"
                      "    return None\n"
                      "class Store:\n"
                      "    run = answer\n")
    assert surface_of(named.body[1], "transactions", named)
    plain = ast.parse("class Holder:\n"
                      "    def __init__(self, inner):\n"
                      "        self.inner, self.seen = inner, []\n")
    assert not surface_of(plain.body[0], "transactions", plain)  # a value it only holds
    offering = ast.parse("class Store:\n"
                         "    run = lambda self, owner, work: work(None)\n"
                         "class Assigned:\n"
                         "    def __init__(self):\n"
                         "        self.execute = lambda statement: None\n")
    assert surface_of(offering.body[0], "transactions")
    assert surface_of(offering.body[1], "conn")
    # The fixed-answer kind: its entry names the refusal and the answer.
    assert shapes_of(FIXED_SOURCE, FIXED, **FIXED_DECLARED) == []
    assert shapes_of(RAISES_SOURCE, FIXED, **RAISES_DECLARED) == []
    # An entry that names no refusal is never satisfied.
    assert shapes_of(FIXED_SOURCE, FIXED, answer=FIXED_DECLARED["answer"])
    for label, (source, rule, declared) in BROKEN_FIXED.items():
        found = shapes_of(source, FIXED, **declared)
        assert [problem for _, problem in found] and all(
            "fixed-answer stub" in problem and rule in problem for _, problem in found), label
    # A fixed-answer stub is a kind of its own: listed as a stub, its answer fails.
    assert shapes_of(FIXED_SOURCE, STUB)
