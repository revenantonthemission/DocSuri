"""No test holds a real secret, address, v1 record or production value, and every secret a
test uses is generated per run (U8 plan Step 98(e), L1-36).

Both tests scan `tests/u8_service_operations_integration`, `scripts/u8_*.py`,
`scripts/serve_docsuri_u8.py`, `frontend/e2e/u8-complete` and `frontend/test/u8-complete`,
except this module, which is excluded by path because it holds the rules' own patterns;
its planted samples are built in memory.

Rules (i) and (iv) are read as the lead's checks after build batch 9a settled them under
L1-36 ("every secret a test uses is generated per run"; "a scan fails any literal
secret"): a value built from constants alone fails wherever it sits and at any length,
and a constant prefix joined to a part generated per run (`secrets`, `uuid4`,
`os.urandom`, or a per-run record) passes, because it is generated per run. By the same
reading a key-bytes rule refuses key material made only of constants: a bytes constant, or
an expression of bytes constants alone, bound to a key-named target, passed to a key-file
writer, or returned by a `release=` callback.

After the review of build batch 9b the reading is applied as written, with no reading of
this module's own beyond it:
- rule (i) reports every constant-only text or bytes part of a value bound to a
  secret-named target, call and method-call arguments and literal containers included, and
  a constant passed by position to a parameter the callee's definitions all name
  secret-named (their parameters read by AST, as `test_never_mocked.py` reads them);
- a key is read by its form, so a dotted key (`"db.password"`) is a name, and a key or
  subscript target built from `PROVIDER_SECRETS` is secret-named;
- a constant passes a join only when another part of it is generated per run: a call of
  `secrets`, `uuid4`, `os.urandom` or `crypto.randomUUID` (or a value derived from one), or
  a name bound to one, the per-run record; a join with any other part fails, on the
  TypeScript side too;
- rule (i)'s `/` exception holds only for routes, paths and URLs, and rule (ii)'s test-id
  exception takes no digits;
- rules (ii) and (iv) read bytes constants too, and a constant a credential stand-in
  answers with (`stdout=` in a test of `docsuri-credential-release` or the keychain's
  `find-generic-password`) is released key material;
- each remaining constant that holds no secret is listed in `EXEMPT` by file, line and
  its own text.

After the re-review of build batch 9b, a credential stand-in's answer is read wherever the
keychain is reached: by `stdout=` or by position (`Done(...)`, `Tools(...)`), under the
`security` key of an answers map, or in a test that names the credential programs or the
keychain's `security` tool (outside an entry keyed by another tool), through a name the test
or the module binds; any constant text or bytes it holds is released key material, as is a
constant bound to, or passed as, `released`. A parameter's default is a binding, a dotted
key is read by its form for the key-bytes rule too, and on the TypeScript side every literal
operand of a `+` join bound to a secret-named target is read, and the generator look-back
stops at the join's own operand.

By batch 10b's second fix pass (recorded for Step 98(e), an addition for Step 104 under
L1-36), the field rule also reads a field reached by a CSS selector (`page.locator('#…')`,
`$`, `querySelector`): a secret field when the selector names one itself, or when the
application's element with that `id` or `name` carries a label, `aria-label`,
placeholder, name or type naming one, the `secret` flag, or a `<label htmlFor>` naming one.
A literal typed into such a field with a locator's `type` or `pressSequentially` is a hit
as `.fill(` is, and so is literal text typed with `page.keyboard.type` (or `insertText`)
while the field the file reached last is a secret field.

By the build batch 10c review and its re-review (additions for Step 104 under L1-36), the
field rule reads further shapes:
- a name bound again later holds what its latest binding reached, read by position;
- every Testing Library query (`getBy`, `findBy`, `queryBy` and their `All` forms) reaches
  a field, and `getByRole` names it by its role and its `name` option (text or regex);
- `user.type(field, '<literal>')` types its second argument, `user.keyboard` types as
  `page.keyboard` does, and a run of key descriptors such as `{Enter}` types no text;
- a Tab or Shift+Tab press (`.press(…'Tab'…)`, `user.tab()`) reaches a field the source does
  not name, whatever locator carries it, so a literal typed after it is a hit;
- a focus helper (`reach(…)`, `focus…(…)`) names its field by test id, and the keyboard
  spec's `press(page, '<id>', key)` is read by its key (Tab or Shift+Tab reaches an unnamed
  field) and otherwise by its test id;
- a page's or frame's `fill(selector, literal)` and `type(selector, literal)` are read
  through the CSS selector rule above, and their first argument is never read as the text.

A failure goes through `require_none`, which fails with `describe` alone and no comparison
of pytest's own, and `Found.text` is kept out of the repr, so a matched value never reaches
the test output, the part's junit XML or a preserved realm.
"""

from __future__ import annotations

import ast
import functools
import re
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from tests.u8_service_operations_integration.operations import test_never_mocked as nm

ROOT = Path(__file__).resolve().parents[3]
TESTS = "tests/u8_service_operations_integration"
SELF = f"{TESTS}/operations/test_no_real_secrets.py"
T = TESTS + "/"


def scanned_files(root: Path = ROOT) -> dict[str, str]:
    paths = sorted((root / TESTS).rglob("*.py"))
    paths += sorted((root / "scripts").glob("u8_*.py"))
    paths.append(root / "scripts" / "serve_docsuri_u8.py")
    for folder in ("frontend/e2e/u8-complete", "frontend/test/u8-complete"):
        paths += sorted(path for path in (root / folder).rglob("*")
                        if path.suffix in (".ts", ".tsx"))
    return {str(path.relative_to(root)): path.read_text() for path in paths
            if "__pycache__" not in path.parts and str(path.relative_to(root)) != SELF}


@dataclass(frozen=True)
class Found:
    """One finding. Its matched text is kept out of its repr, so pytest's own explanation of
    a failed comparison never prints a real key, address, iD or typed password."""

    file: str
    line: int
    rule: str
    text: str = field(repr=False)


# --- test 1: real secrets, addresses, v1 records and production values -----------------------

PROVIDER_PATTERNS = {
    "Resend key": r"\bre_[A-Za-z0-9]{20,}\b",
    "Notion token": r"\bntn_[A-Za-z0-9]{40,}\b",
    "Notion legacy token": r"\bsecret_[A-Za-z0-9]{43}\b",
    "Google client secret": r"\bGOCSPX-[A-Za-z0-9_-]{28}",
    "Google access token": r"ya29\.",
    "Google API key": r"\bAIza[0-9A-Za-z_-]{35}",
    "GitHub token": r"\bghp_[A-Za-z0-9]{36}\b",
    "GitHub fine-grained token": r"\bgithub_pat_",
    "AWS access key": r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b",
    "Cloudflare tunnel token": r"eyJhIjoi",
    "healthchecks.io ping": (r"hc-ping\.com/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-"
                             r"[0-9a-f]{12}"),
    "private key": r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
}
# A literal local part, or a generated one (`f"{name}@…"`, `${name}@…`).
EMAIL = re.compile(r"(?:[A-Za-z0-9._%+-]+|\})@((?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,})\b")
CONNINFO_HOST = re.compile(r"\bhost=(\S+)")
CONNINFO_PORT = re.compile(r"\bport=(\d+)")
URL_ADDRESS = re.compile(r"^[a-z][a-z0-9+.-]*://(?:[^@/\s]*@)?(127\.0\.0\.1|localhost):(\d+)")
ALLOWED_DOMAINS = ("example.com", "example.net", "example.org")
ALLOWED_SUFFIXES = (".example", ".invalid", ".test")
ORCID = re.compile(r"\b(\d{4})-(\d{4})-(\d{4})-(\d{3}[\dX])\b")
V1_PORTS = frozenset({3000, 8000, 5432, 6379, 9200, 9000})
V1_HOSTS = frozenset({"127.0.0.1", "localhost"})
ADDRESS = re.compile(r"^[a-z][a-z0-9+.-]*://(127\.0\.0\.1|localhost):(\d+)(?:[/?#]|$)")


def allowed_email(domain: str) -> bool:
    domain = domain.lower()
    return (domain in ALLOWED_DOMAINS or domain.endswith(tuple("." + d for d in ALLOWED_DOMAINS))
            or domain.endswith(ALLOWED_SUFFIXES))


def orcid_valid(digits: str) -> bool:
    """ISO 7064 11-2 over the first fifteen digits, against the sixteenth."""
    total = 0
    for digit in digits[:15]:
        total = (total + int(digit)) * 2
    check = (12 - total % 11) % 11
    return digits[15] == ("X" if check == 10 else str(check))


def text_findings(file: str, source: str) -> list[Found]:
    found = []
    for number, line in enumerate(source.splitlines(), 1):
        for name, pattern in PROVIDER_PATTERNS.items():
            if re.search(pattern, line):
                found.append(Found(file, number, name, line.strip()))
        for match in EMAIL.finditer(line):
            if not allowed_email(match.group(1)):
                found.append(Found(file, number, "email outside the reserved names",
                                   match.group(0)))
        for match in ORCID.finditer(line):
            if orcid_valid("".join(match.groups())):
                found.append(Found(file, number, "ORCID iD with a valid check digit",
                                   match.group(0)))
    return found


def literal(node: ast.AST) -> str | None:
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def path_text(node: ast.AST) -> str | None:
    """A literal path: a string, `Path("…")`, or `Path("…") / "…"`."""
    value = literal(node)
    if value is not None:
        return value
    if isinstance(node, ast.Call) and ast.unparse(node.func).split(".")[-1] in (
            "Path", "PurePath") and node.args:
        return path_text(node.args[0])
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        left, right = path_text(node.left), path_text(node.right)
        if left is not None and right is not None:
            return left.rstrip("/") + "/" + right
    return None


def v1_address(node: ast.Call) -> str | None:
    """A literal real v1 address a call connects to or requests."""
    callee = ast.unparse(node.func)
    last = callee.split(".")[-1]
    keywords = {item.arg: item.value for item in node.keywords if item.arg}
    if last == "connect" and "psycopg" in callee:
        host, port = literal(keywords.get("host")), keywords.get("port")
        if host in V1_HOSTS and isinstance(port, ast.Constant) and port.value in V1_PORTS:
            return f"{host}:{port.value}"
        # A conninfo string or URL, by position or as `conninfo=`.
        for argument in (*node.args[:1], keywords.get("conninfo")):
            value = literal(argument) if argument is not None else None
            if not value:
                continue
            match = URL_ADDRESS.match(value)
            if match and int(match.group(2)) in V1_PORTS:
                return value
            host_match, port_match = CONNINFO_HOST.search(value), CONNINFO_PORT.search(value)
            if (host_match and port_match and host_match.group(1) in V1_HOSTS
                    and int(port_match.group(1)) in V1_PORTS):
                return value
    if last in ("connect", "create_connection", "connect_ex") and node.args:
        first = node.args[0]
        if isinstance(first, ast.Tuple) and len(first.elts) == 2:
            host, port = literal(first.elts[0]), first.elts[1]
            if host in V1_HOSTS and isinstance(port, ast.Constant) and port.value in V1_PORTS:
                return f"{host}:{port.value}"
    if last in ("get", "post", "put", "patch", "delete", "request", "stream", "urlopen",
                "Request", "goto", "head") and (node.args or "url" in keywords):
        for argument in (*node.args[:2], keywords.get("url")):
            value = literal(argument) if argument is not None else None
            match = ADDRESS.match(value or "")
            if match and int(match.group(2)) in V1_PORTS:
                return value
    return None


def python_findings(file: str, tree: ast.Module) -> list[Found]:
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        last = ast.unparse(node.func).split(".")[-1]
        if last in ("open", "read_text", "read_bytes", "private_bytes"):
            candidates = list(node.args[:1])
            if isinstance(node.func, ast.Attribute) and last in ("read_text", "read_bytes",
                                                                 "open"):
                candidates.append(node.func.value)  # `Path("…").open()` too
            for candidate in candidates:
                value = path_text(candidate)
                if value is not None and value.startswith("/Library/DocSuri/"):
                    found.append(Found(file, node.lineno, "a read under /Library/DocSuri/",
                                       value))
        address = v1_address(node)
        if address is not None:
            found.append(Found(file, node.lineno, "a connection to a real v1 address", address))
    return found


TS_ADDRESS = re.compile(r"\b(?:goto|get|post|put|fetch|request)\(\s*['\"`]"
                        r"(?:https?|wss?)://(?:127\.0\.0\.1|localhost):(\d+)")


def typescript_findings(file: str, source: str) -> list[Found]:
    found = []
    for number, line in enumerate(source.splitlines(), 1):
        for match in TS_ADDRESS.finditer(line):
            if int(match.group(1)) in V1_PORTS:
                found.append(Found(file, number, "a request to a real v1 address", line.strip()))
    return found


def real_values(files: dict[str, str]) -> list[Found]:
    found = []
    for file, source in files.items():
        found += text_findings(file, source)
        if file.endswith(".py"):
            found += python_findings(file, ast.parse(source))
        else:
            found += typescript_findings(file, source)
    return found


# --- test 2: every secret is generated per run ------------------------------------------------

SECRET_WORDS = ("password", "secret", "token", "seed", "apikey")
NOT_SECRET_ENDINGS = ("url", "path", "file", "name")
PROVIDER_SECRET_KEYS = frozenset({"googleClientSecret", "orcidClientSecret", "resendApiKey"})
PREFIXES = ("re_", "ntn_", "secret_", "GOCSPX-")
URL_PASSWORD = re.compile(r"[a-z][a-z0-9+.-]*://[^/\s:@]+:([^/\s@]+)@")
GENERATED = "\0"  # an f-string's generated part, where a literal password is looked for
CONVERSIONS = frozenset({"bytes", "bytearray", "str", "encode", "decode"})
# What generates a value per run (L1-36): these calls, and values derived from them.
GENERATORS = frozenset({"token_hex", "token_bytes", "token_urlsafe", "uuid4", "urandom"})
DERIVATIONS = frozenset({*CONVERSIONS, "hex", "upper", "lower"})
# The programs a credential stand-in answers for: its answer is released key material.
CREDENTIAL_PROGRAMS = ("docsuri-credential-release", "find-generic-password")
# The keychain's tool: a test naming it, or an answers map keyed by it, reaches the keychain.
KEYCHAIN_TOOL = "security"
# A stand-in's answer constructors: their first positional argument is what is answered.
ANSWER_CALLS = frozenset({"Done", "Tools"})
ROUTE = re.compile(r"^(?:/|\./|\.\./|~/|[a-z][a-z0-9+.-]*://)")
KEY_WRITERS = frozenset({"write_private", "write_bytes", "key_file", "_private_file",
                         "write_key", "private_write"})


def form(name: str) -> str:
    return name.lower().replace("_", "").replace("-", "")


def secret_named(name: str | None) -> bool:
    """A name, attribute, keyword or dict key whose form names a secret; a dotted key is
    read by its form too. A key holding `/` or whitespace is a route or a text."""
    if not name or re.search(r"[/\s]", name):
        return False
    shape = form(name)
    return any(word in shape for word in SECRET_WORDS) and not shape.endswith(NOT_SECRET_ENDINGS)


def key_named(name: str | None) -> bool:
    """A key-named target; a dotted key (`"cursor.key"`) is read by its form too."""
    if not name or re.search(r"[/\s]", name):
        return False
    shape = form(name)
    return "key" in shape and not shape.endswith(NOT_SECRET_ENDINGS)


def constant_only(node: ast.AST) -> bool:
    """An expression of constants alone: a constant, an arithmetic or f-string of constant
    parts, or a conversion (`bytes`, `bytearray`, `str`, `.encode()`) of one."""
    if isinstance(node, ast.Constant):
        return True
    if isinstance(node, ast.BinOp):
        return constant_only(node.left) and constant_only(node.right)
    if isinstance(node, ast.UnaryOp):
        return constant_only(node.operand)
    if isinstance(node, ast.JoinedStr):
        return all(isinstance(item, ast.Constant) or (
            isinstance(item, ast.FormattedValue) and constant_only(item.value))
            for item in node.values)
    if isinstance(node, ast.Call) and not node.keywords:
        callee = ast.unparse(node.func).split(".")[-1]
        if callee in CONVERSIONS:
            parts = list(node.args)
            if isinstance(node.func, ast.Attribute):
                parts.append(node.func.value)
            return bool(parts) and all(constant_only(part) for part in parts)
    return False


def textual(node: ast.AST) -> bool:
    """The constant-only expression builds text or bytes (not a number)."""
    return any(isinstance(item, ast.Constant) and isinstance(item.value, str | bytes)
               for item in ast.walk(node)) or isinstance(node, ast.JoinedStr)


def generated(node: ast.AST, names: frozenset = frozenset()) -> bool:
    """A value generated per run: a call of `secrets`, `uuid4` or `os.urandom`, a value
    derived from one (`uuid4().hex[:12]`, `.encode()`, `str(...)`), a join holding one, or
    a name bound to one (`names`, the per-run record)."""
    if isinstance(node, ast.Call):
        callee = ast.unparse(node.func)
        last = callee.split(".")[-1]
        if callee.startswith("secrets.") or last in GENERATORS:
            return True
        if isinstance(node.func, ast.Attribute) and last in DERIVATIONS:
            return generated(node.func.value, names)
        return last in DERIVATIONS and bool(node.args) and generated(node.args[0], names)
    if isinstance(node, ast.Attribute | ast.Subscript | ast.Starred | ast.Await):
        return generated(node.value, names)
    if isinstance(node, ast.Name):
        return node.id in names
    if isinstance(node, ast.BinOp):
        return generated(node.left, names) or generated(node.right, names)
    if isinstance(node, ast.JoinedStr):
        return any(isinstance(item, ast.FormattedValue) and generated(item.value, names)
                   for item in node.values)
    if isinstance(node, ast.FormattedValue):
        return generated(node.value, names)
    return False


def generated_names(tree: ast.Module) -> frozenset:
    """Every name bound to a generated value in `tree` (two passes, so a name derived from
    another generated name counts)."""
    names: frozenset = frozenset()
    for _ in range(2):
        found = set(names)
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and generated(node.value, names):
                found |= {target.id for target in node.targets if isinstance(target, ast.Name)}
        names = frozenset(found)
    return names


def route_like(value: str) -> bool:
    """A route, a path or a URL (its literal password is rule (iii)'s)."""
    return bool(ROUTE.match(value))


def maximal_constant_parts(node: ast.AST, names: frozenset = frozenset()) -> list[ast.AST]:
    """Every largest constant-only text or bytes sub-expression of a value: what the value
    holds that is built from constants alone, containers and call and method-call
    arguments included. A join (an arithmetic or an f-string) with a part generated per
    run is generated per run, and so is a generated call; a join with any other part keeps
    its constant parts. Empty text, and a route, path or URL, hold nothing. A subscript's
    index and an attribute's name are not values; an element read from a literal container
    is that element."""
    if constant_only(node):
        if not textual(node):
            return []
        if isinstance(node, ast.Constant) and (
                node.value in ("", b"")
                or isinstance(node.value, str) and route_like(node.value)):
            return []
        return [node]
    if isinstance(node, ast.BinOp | ast.JoinedStr | ast.Call) and generated(node, names):
        return []
    if isinstance(node, ast.BinOp):
        children = [node.left, node.right]
    elif isinstance(node, ast.JoinedStr):
        children = [item.value if isinstance(item, ast.FormattedValue) else item
                    for item in node.values]
    elif isinstance(node, ast.Subscript):
        if not isinstance(node.value, ast.Dict | ast.List | ast.Tuple):
            return []  # a lookup is a reference
        children = [node.value]
    elif isinstance(node, ast.Call):
        children = [*node.args, *(item.value for item in node.keywords)]
        if isinstance(node.func, ast.Attribute):
            children.append(node.func.value)
    elif isinstance(node, ast.Tuple | ast.List | ast.Set):
        children = node.elts
    elif isinstance(node, ast.Dict):
        children = [value for value in node.values if value is not None]
    elif isinstance(node, ast.BoolOp):
        children = node.values
    elif isinstance(node, ast.IfExp):
        children = [node.body, node.orelse]
    elif isinstance(node, ast.Starred | ast.Await):
        children = [node.value]
    else:
        return []
    return [part for child in children for part in maximal_constant_parts(child, names)]


def released_named(name: str | None) -> bool:
    """A target or parameter named for released key material (`released`)."""
    return bool(name) and "released" in form(name)


def secret_positions(callee: ast.AST, definitions: dict) -> dict[int, str]:
    """The positions every definition of the callee's name (functions and methods, `self`
    dropped) names secret-named or released, with that name: read by AST, as
    `test_never_mocked.py` reads a callee's parameters."""
    name = callee.attr if isinstance(callee, ast.Attribute) else (
        callee.id if isinstance(callee, ast.Name) else None)
    entries = definitions.get(name or "", [])
    found: dict[int, str] = {}
    width = max((len(positional) for positional, _ in entries), default=0)
    for index in range(width):
        named = {positional[index] for positional, _ in entries if index < len(positional)}
        if named and (all(secret_named(item) for item in named)
                      or all(released_named(item) for item in named)):
            found[index] = sorted(named)[0]
    return found


def docstrings(tree: ast.Module) -> set[int]:
    """The ids of every docstring constant (they are not values)."""
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                found.add(id(body[0].value))
    return found


class Rules(ast.NodeVisitor):
    def __init__(self, file: str, tree: ast.Module, definitions: dict | None = None):
        self.file, self.found = file, []
        self.definitions = definitions if definitions is not None else (
            nm.repository_definitions())
        self.skip = docstrings(tree)
        self.keys: set[int] = set()  # dict keys and subscript indexes: not values
        self.joined: set[int] = set()  # constants inside a join with a generated part
        self.names = generated_names(tree)  # names bound to a per-run value
        self.provider_names = {
            target.id for node in ast.walk(tree) if isinstance(node, ast.Assign)
            and isinstance(node.value, ast.Subscript)
            and ast.unparse(node.value.value) == "PROVIDER_SECRETS"
            for target in node.targets if isinstance(target, ast.Name)}
        # Tests of a credential stand-in: what the stand-in answers is released key material.
        # The keychain is reached through the credential programs or the `security` tool.
        self.credential_tests = {
            id(item) for item in ast.walk(tree)
            if isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef) and any(
                isinstance(found, ast.Constant) and isinstance(found.value, str) and (
                    any(program in found.value for program in CREDENTIAL_PROGRAMS)
                    or found.value == KEYCHAIN_TOOL
                    or found.value.endswith("/" + KEYCHAIN_TOOL))
                for found in ast.walk(item))}
        # Module constants an answer may name.
        self.module_values = {
            target.id: node.value for node in tree.body if isinstance(node, ast.Assign)
            for target in node.targets if isinstance(target, ast.Name)}
        # Answer constructors inside an answers map: under the keychain's tool, the answer
        # is released key material; under another tool, it answers that tool only.
        self.keychain_answers: set[int] = set()
        self.other_answers: set[int] = set()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Dict):
                continue
            for key, value in zip(node.keys, node.values, strict=True):
                if key is None or literal(key) is None:
                    continue
                into = (self.keychain_answers if literal(key) == KEYCHAIN_TOOL
                        else self.other_answers)
                into |= {id(item) for item in ast.walk(value) if isinstance(item, ast.Call)}
        self.function: list[ast.AST] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Dict):
                self.keys |= {id(key) for key in node.keys if key is not None}
            elif isinstance(node, ast.Subscript):
                self.keys |= {id(item) for item in ast.walk(node.slice)}
            elif (isinstance(node, ast.BinOp | ast.JoinedStr) and not constant_only(node)
                  and generated(node, self.names)):
                self.joined |= {id(item) for item in ast.walk(node)}

    def provider_key(self, key: ast.AST | None) -> bool:
        """A key or index taken from `PROVIDER_SECRETS`, directly or through a name."""
        if key is None:
            return False
        if isinstance(key, ast.Subscript) and ast.unparse(key.value) == "PROVIDER_SECRETS":
            return True
        return (literal(key) in PROVIDER_SECRET_KEYS
                or isinstance(key, ast.Name) and key.id in self.provider_names)

    def visit_FunctionDef(self, node) -> None:
        # A parameter's default is a binding of that parameter.
        arguments = node.args
        positional = [*arguments.posonlyargs, *arguments.args]
        for item, default in zip(positional[len(positional) - len(arguments.defaults):],
                                 arguments.defaults, strict=True):
            self.bound(item.arg, default)
        for item, default in zip(arguments.kwonlyargs, arguments.kw_defaults, strict=True):
            if default is not None:
                self.bound(item.arg, default)
        self.function.append(node)
        self.generic_visit(node)
        self.function.pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    def add(self, node: ast.AST, rule: str, text: str) -> None:
        self.found.append(Found(self.file, node.lineno, rule, text[:80]))

    # Rule (i), and the key-bytes rule, at each binding.

    def bound(self, name: str | None, value: ast.AST) -> None:
        if secret_named(name):
            for part in maximal_constant_parts(value, self.names):
                self.add(part, "rule (i): a constant bound to a secret-named target",
                         f"{name} = {ast.unparse(part)}")
        if key_named(name):
            for part in maximal_constant_parts(value, self.names):
                if self.bytes_part(part):
                    self.add(part, "key bytes made only of constants",
                             f"{name} = {ast.unparse(part)}")
        if released_named(name):
            for part in maximal_constant_parts(value, self.names):
                if self.bytes_part(part):
                    self.add(part, "released key material made only of constants",
                             f"{name} = {ast.unparse(part)}")

    @staticmethod
    def bytes_part(node: ast.AST) -> bool:
        return any(isinstance(item, ast.Constant) and isinstance(item.value, bytes)
                   for item in ast.walk(node))

    def target_name(self, target: ast.AST) -> str | None:
        if isinstance(target, ast.Name):
            return target.id
        if isinstance(target, ast.Attribute):
            return target.attr
        if isinstance(target, ast.Subscript):
            if self.provider_key(target.slice):
                return "providerSecret"  # `env[PROVIDER_SECRETS[...]] = ...`
            return literal(target.slice)
        return None

    def visit_Assign(self, node: ast.Assign) -> None:
        for target in node.targets:
            if isinstance(target, ast.Tuple) and isinstance(node.value, ast.Tuple):
                for item, value in zip(target.elts, node.value.elts, strict=False):
                    self.bound(self.target_name(item), value)
            else:
                self.bound(self.target_name(target), node.value)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if node.value is not None:
            self.bound(self.target_name(node.target), node.value)
        self.generic_visit(node)

    def visit_Dict(self, node: ast.Dict) -> None:
        for key, value in zip(node.keys, node.values, strict=True):
            if key is None:
                continue
            name = "providerSecret" if self.provider_key(key) else literal(key)
            self.bound(name, value)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        callee = ast.unparse(node.func).split(".")[-1]
        for keyword in node.keywords:
            self.bound(keyword.arg, keyword.value)
            if keyword.arg == "release":
                self.release(keyword.value)
            # What a credential stand-in answers with is released key material.
            if keyword.arg == "stdout" and self.keychain_answer(node):
                self.answered(keyword.value)
        # An answer passed by position (`Done(...)`, `Tools(...)`) too.
        if callee in ANSWER_CALLS and node.args and self.keychain_answer(node):
            self.answered(node.args[0])
        # Rule (i) by position: a parameter every definition of the callee names so.
        for index, name in secret_positions(node.func, self.definitions).items():
            if index < len(node.args) and not isinstance(node.args[index], ast.Starred):
                self.bound(name, node.args[index])
        data = self.key_file_data(node, callee)
        if data is not None:
            for part in maximal_constant_parts(data, self.names):
                if self.bytes_part(part):
                    self.add(part, "key bytes made only of constants",
                             f"{callee}({ast.unparse(part)})")
        self.generic_visit(node)

    def keychain_answer(self, node: ast.Call) -> bool:
        """An answer the keychain gives: under the `security` key of an answers map, or in
        a test of a credential stand-in, outside an entry keyed by another tool."""
        if id(node) in self.keychain_answers:
            return True
        return (bool(self.function) and id(self.function[-1]) in self.credential_tests
                and id(node) not in self.other_answers)

    def answered(self, answer: ast.AST) -> None:
        """A stand-in's answer, read through a name the test or the module bound it to; a
        finding is reported at the answer's own line."""
        at = answer
        if isinstance(answer, ast.Name):
            local = next((item.value for item in ast.walk(self.function[-1])
                          if isinstance(item, ast.Assign) and any(
                              isinstance(target, ast.Name) and target.id == answer.id
                              for target in item.targets)), None) if self.function else None
            answer = local if local is not None else self.module_values.get(answer.id, answer)
        for part in maximal_constant_parts(answer, self.names):
            self.add(at, "released key material made only of constants",
                     f"a credential stand-in answers {ast.unparse(part)}")

    @staticmethod
    def key_file_data(node: ast.Call, callee: str) -> ast.AST | None:
        """The bytes a key-file writer writes: `write_bytes` on a key-named path,
        `write_private(<key path>, data)`, or a writer named for keys."""
        if callee == "write_bytes" and isinstance(node.func, ast.Attribute) and node.args:
            if "key" in ast.unparse(node.func.value).lower():
                return node.args[0]
            return None
        if callee in ("write_private", "_private_file") and len(node.args) >= 2:
            if "key" in ast.unparse(node.args[0]).lower():
                return node.args[1]
            return None
        if "key" in callee.lower() and callee.startswith(("write", "key_file")):
            return next(iter([*node.args[1:], *(item.value for item in node.keywords
                                                if item.arg == "content")]), None)
        return None

    def release(self, value: ast.AST) -> None:
        """A `release=` callback that answers key material made only of constants."""
        returns = []
        if isinstance(value, ast.Lambda):
            returns = [value.body]
        elif isinstance(value, ast.Name):
            returns = self.function_returns.get(value.id, [])
        for item in returns:
            for part in maximal_constant_parts(item, self.names):
                if self.bytes_part(part):
                    self.add(part, "key bytes made only of constants",
                             f"release returns {ast.unparse(part)}")

    function_returns: dict[str, list[ast.AST]] = {}

    def visit_Module(self, node: ast.Module) -> None:
        self.function_returns = {
            item.name: [ret.value for ret in ast.walk(item)
                        if isinstance(ret, ast.Return) and ret.value is not None]
            for item in ast.walk(node) if isinstance(item, ast.FunctionDef)}
        self.generic_visit(node)

    # Rules (ii)-(iv) at each constant used as a value.

    def visit_Constant(self, node: ast.Constant) -> None:
        if id(node) in self.skip or not isinstance(node.value, str | bytes):
            return
        # Bytes are read as their text (rules (ii) to (iv) reach them too).
        value = node.value if isinstance(node.value, str) else node.value.decode("latin-1")
        is_value = id(node) not in self.keys
        lowered = value.lower()
        if is_value and ("password" in lowered or "secret" in lowered) and not (
                re.search(r"[/\s]", value) or re.fullmatch(r"[A-Za-z_-]+", value)):
            self.add(node, "rule (ii): a value holding password or secret", value)
        match = URL_PASSWORD.search(value)
        if match and GENERATED not in match.group(1):
            self.add(node, "rule (iii): a URL with a literal password", value)
        if is_value and value.startswith(PREFIXES) and id(node) not in self.joined:
            self.add(node, "rule (iv): a provider prefix built from constants alone", value)

    def visit_JoinedStr(self, node: ast.JoinedStr) -> None:
        text = "".join(item.value if isinstance(item, ast.Constant) else GENERATED
                       for item in node.values)
        match = URL_PASSWORD.search(text)
        if match and GENERATED not in match.group(1):
            self.add(node, "rule (iii): a URL with a literal password", text)
        if (text.startswith(PREFIXES) and not generated(node, self.names)
                and id(node) not in self.keys and id(node) not in self.joined):
            self.add(node, "rule (iv): a provider prefix built from constants alone", text)
        for item in node.values:
            if isinstance(item, ast.FormattedValue):
                self.visit(item)


# The TypeScript side, read as tokens.
TS_STRING = re.compile(r"'((?:[^'\\\n]|\\.)*)'|\"((?:[^\"\\\n]|\\.)*)\"|`((?:[^`\\]|\\.)*)`")
SENSITIVE_FIELD = re.compile(r"password|token|secret|seed|비밀번호|토큰", re.IGNORECASE)
LOCATOR = re.compile(r"(?:get|find|query)(?:All)?By(?:TestId|Label|LabelText|Placeholder|"
                     r"PlaceholderText|Role)\(\s*(?:'([^']*)'|\"([^\"]*)\"|`([^`]*)`)")
FILL = re.compile(r"\.(?:fill|type|pressSequentially)\(\s*(?:'([^']*)'|\"([^\"]*)\"|`([^`$]*)`)"
                  r"\s*[,)]")
# Batch 10b's second fix pass, for Step 98(e) (L1-36; Step 104's addition): a field reached
# by a CSS selector, and literal text typed with the keyboard into the field last reached.
CSS_LOCATOR = re.compile(r"(?:\.locator|\.\$\$?|querySelector(?:All)?)\(\s*"
                         r"(?:'([^']*)'|\"([^\"]*)\"|`([^`$]*)`)")
SELECTOR_ID = re.compile(r"#([A-Za-z][\w-]*)")
SELECTOR_NAME = re.compile(r"\[\s*name\s*[~|^$*]?=\s*['\"]?([\w-]+)")
KEYBOARD_TYPE = re.compile(r"\.keyboard(?:\.(?:type|insertText))?\(\s*"
                           r"(?:'([^']*)'|\"([^\"]*)\"|`([^`$]*)`)\s*[,)]")
# The build batch 10c review: Testing Library's `user.type(field, '<literal>')`, whose
# literal is the second argument; a Tab press, which moves focus to a field the source does
# not name; and a focus helper (`reach(…)`, `focus…(…)`), which names its field by test id.
TYPE_INTO = re.compile(r"\.type\(\s*([^;]+?)\s*,\s*(?:'([^']*)'|\"([^\"]*)\"|`([^`$]*)`)"
                       r"\s*[,)]")
TAB_PRESS = re.compile(r"\.press\([^;)]*['\"`](?:Shift\+)?Tab['\"`]|\.tab\(")
FOCUS_HELPER = re.compile(r"(?<![\w$.])(?:reach|focus)\w*\(")
# The build batch 10c re-review: the keyboard spec's own `press(page, '<id>', key)`, which
# reaches its field by test id and then presses the key; getByRole's `name` option; and
# Playwright's `page.fill(selector, literal)` and `page.type(selector, literal)`.
PRESS_HELPER = re.compile(r"(?<![\w$.])press\(\s*[\w$.]+\s*,\s*([^,;]+?)\s*,\s*([^,;)]+?)\s*\)")
TAB_KEY = re.compile(r"(?:Shift\+)?Tab")
ROLE_NAME = re.compile(r"\s*,\s*\{[^}]*?\bname:\s*(?:'([^']*)'|\"([^\"]*)\"|`([^`$]*)`|"
                       r"/((?:[^/\\\n]|\\.)*)/)")
PAGE_FILL = re.compile(r"\b(?:page|frame|[A-Za-z_$][\w$]*Frame)\.(?:fill|type)\(\s*"
                       r"(?:'([^']*)'|\"([^\"]*)\"|`([^`$]*)`)\s*,\s*"
                       r"(?:'([^']*)'|\"([^\"]*)\"|`([^`$]*)`)\s*[,)]")
PAGE_RECEIVER = re.compile(r"\b(?:page|frame|[A-Za-z_$][\w$]*Frame)$")
KEY_DESCRIPTORS = re.compile(r"(?:\{[^{}]*\})+")
SOURCE_UI = "frontend/src"
FIELD_TAG = re.compile(r"<[A-Za-z][\w.]*")
FIELD_TEXT = re.compile(r"\b(?:label|aria-label|placeholder|name|type)=\s*\{?\s*"
                        r"(?:'([^']*)'|\"([^\"]*)\"|`([^`$]*)`)")
CHANGE_VALUE = re.compile(r"target:\s*\{\s*value:\s*(?:'([^']*)'|\"([^\"]*)\"|`([^`$]*)`)")
TS_BINDING = re.compile(r"\b([A-Za-z_$][\w$]*)\s*[:=]\s*(?:'([^']*)'|\"([^\"]*)\"|`([^`]*)`)"
                        r"\s*(\.repeat\(\s*\d+\s*\)|[,;)}\n+]|$)")
NAMED_LOCATOR = re.compile(r"\b(?:const|let)\s+([A-Za-z_$][\w$]*)\s*=\s*([^;]*)")


TS_GENERATOR = re.compile(r"(?:crypto\.)?randomUUID\(|getRandomValues\(|randomBytes\(")


def ts_template_generated(value: str) -> bool:
    """A template whose `${}` parts hold a generator."""
    return any(TS_GENERATOR.search(part) for part in re.findall(r"\$\{([^}]*)\}", value))


def ts_join_generated(source: str, start: int, end: int) -> bool:
    """A literal at `source[start:end]` joined by `+` to a generated operand: the text
    after the `+` begins with a generator, or the operand before it ends in one."""
    after = source[end:].lstrip()
    if after.startswith("+") and TS_GENERATOR.match(after[1:].lstrip()):
        return True
    before = source[:start].rstrip()
    if before.endswith("+"):
        return bool(TS_GENERATOR.search(ts_operand_before(before[:-1].rstrip())))
    return False


def ts_operand_before(text: str) -> str:
    """The call operand `text` ends with (`crypto.randomUUID()`, `make(a, b)`), and no
    more: the look-back stops at the call's own opening parenthesis and its callee."""
    if not text.endswith(")"):
        return ""
    depth = 0
    for index in range(len(text) - 1, -1, -1):
        depth += {")": 1, "(": -1}.get(text[index], 0)
        if depth == 0:
            callee = re.search(r"[\w$.]*$", text[:index])
            return text[callee.start() if callee else index:]
    return ""


TS_JOIN_BINDING = re.compile(r"\b([A-Za-z_$][\w$]*)\s*[:=]\s*([^;\n{}]*\+[^;\n{}]*)")
TS_OPERAND_LITERAL = re.compile(r"^\s*(?:'([^']*)'|\"([^\"]*)\"|`([^`$]*)`)\s*$")


def ts_join_literals(source: str, file: str, line_of) -> list[Found]:
    """Rule (i) on a `+` join bound to a secret-named target: every literal operand, unless
    another operand is generated per run."""
    found = []
    for match in TS_JOIN_BINDING.finditer(source):
        if not secret_named(match.group(1)):
            continue
        expression = re.split(r",\s*[A-Za-z_$][\w$]*\s*:", match.group(2))[0]
        operands = expression.split("+")
        if any(TS_GENERATOR.search(operand) for operand in operands):
            continue
        for operand in operands:
            literal_match = TS_OPERAND_LITERAL.match(operand.rstrip(" )"))
            if literal_match and next(item for item in literal_match.groups()
                                      if item is not None):
                found.append(Found(file, line_of(match.start()), "rule (i)",
                                   f"{match.group(1)}: {expression.strip()}"[:80]))
    return found


def ts_key(source: str, start: int, end: int) -> bool:
    """A literal used as an object key (`{ 'k': …`, `, 'k': …`) or an index (`x['k']`); a
    literal before `:` elsewhere, such as a ternary's first branch, is a value."""
    after = source[end:end + 3].lstrip()
    line = source[:start].rstrip(" \t")
    before = line.rstrip()
    if before.endswith("["):
        return True
    return after.startswith(":") and (not line or line.endswith("\n") or before[-1] in "{,(")


@functools.cache
def ui_sources() -> tuple[str, ...]:
    """The application's own TSX and TS sources, where a CSS selector's field is found."""
    return tuple(path.read_text(encoding="utf-8")
                 for path in sorted((ROOT / SOURCE_UI).rglob("*.ts*"))
                 if path.suffix in {".ts", ".tsx"})


def field_names_secret(key: str, kind: str, sources: tuple[str, ...]) -> bool:
    """Whether the element whose `kind` attribute (`id` or `name`) is `key` is a secret
    field: its tag (from its opening `<` to the next `<`) carries a label, `aria-label`,
    placeholder, name or type naming a secret, or the `secret` flag, or, for an id, a
    `<label htmlFor>` names one."""
    attribute = re.compile(rf"(?<![\w-]){kind}=\s*\{{?\s*['\"`]{re.escape(key)}['\"`]")
    label_for = re.compile(rf"htmlFor=\s*\{{?\s*['\"`]{re.escape(key)}['\"`][^>]*>([^<]*)"
                           if kind == "id" else r"(?!)")
    for source in sources:
        for match in attribute.finditer(source):
            opening = [tag.start() for tag in FIELD_TAG.finditer(source, 0, match.start())]
            start = opening[-1] if opening else match.start()
            end = source.find("<", match.end())
            tag = source[start:end if end != -1 else len(source)]
            texts = [next(item for item in found.groups() if item is not None)
                     for found in FIELD_TEXT.finditer(tag)]
            if re.search(r"\bsecret\b(?!\s*[=:])", tag) or any(
                    SENSITIVE_FIELD.search(text) for text in texts):
                return True
        if any(SENSITIVE_FIELD.search(found.group(1)) for found in label_for.finditer(source)):
            return True
    return False


def selector_secret(selector: str, sources: tuple[str, ...]) -> bool:
    """A CSS selector reaches a secret field: the selector names one itself, or an `id` or
    `name` it selects belongs to a secret field of the application."""
    if SENSITIVE_FIELD.search(selector):
        return True
    keys = [(key, "id") for key in SELECTOR_ID.findall(selector)]
    keys += [(key, "name") for key in SELECTOR_NAME.findall(selector)]
    return any(field_names_secret(key, kind, sources) for key, kind in keys)


def quoted(match: re.Match) -> str:
    """The one quoted group a pattern of alternative quotes matched."""
    return next(item for item in match.groups() if item is not None)


def locator_text(found: re.Match, statement: str) -> str:
    """What a `getBy…` locator names its field by: its first argument, and for a role
    query also its `name` option (`getByRole('textbox', { name: 'Notion 토큰' })`)."""
    text = quoted(found)
    if "ByRole(" in found.group(0):
        name = ROLE_NAME.match(statement, found.end())
        if name:
            text += " " + quoted(name)
    return text


def page_fill_selector(found: re.Match) -> str:
    """The selector of a `page.fill(selector, literal)` or `page.type(…)` match."""
    return next(item for item in found.groups()[:3] if item is not None)


def statement_fields(statement: str, named: dict[str, bool],
                     sources: tuple[str, ...]) -> list[bool]:
    """For each field a statement reaches, by `getBy…`, by a CSS selector, by a page's
    `fill` or `type` selector or through a bound locator, whether it is a secret field."""
    fields = [bool(SENSITIVE_FIELD.search(locator_text(found, statement)))
              for found in LOCATOR.finditer(statement)]
    fields += [selector_secret(quoted(found), sources)
               for found in CSS_LOCATOR.finditer(statement)]
    fields += [selector_secret(page_fill_selector(found), sources)
               for found in PAGE_FILL.finditer(statement)]
    fields += [secret for name, secret in named.items()
               if re.search(rf"(?<![\w$.]){re.escape(name)}\b", statement)]
    return fields


def typed_literals(statement: str, last_field_secret: bool, named: dict[str, bool],
                   sources: tuple[str, ...]) -> list[re.Match]:
    """The literals a statement types where the field may be secret: by the keyboard while
    the last field reached may be secret (a run of key descriptors such as `{Enter}` types
    no text), and as `type(field, '<literal>')`'s second argument into a secret field."""
    hits = []
    if last_field_secret:
        hits += [match for match in KEYBOARD_TYPE.finditer(statement)
                 if not KEY_DESCRIPTORS.fullmatch(quoted(match))]
    hits += [match for match in TYPE_INTO.finditer(statement)
             if any(statement_fields(match.group(1), named, sources))]
    hits += [match for match in PAGE_FILL.finditer(statement)
             if selector_secret(page_fill_selector(match), sources)]
    return hits


def press_helper_focus(helper: re.Match) -> bool:
    """Whether `press(page, '<id>', key)` leaves focus on a field that may be secret: a Tab
    or Shift+Tab key reaches a field the source does not name; any other key stays on the
    field the test id names, secret when the id names one or is not a literal."""
    key = TS_STRING.fullmatch(helper.group(2))
    if key and TAB_KEY.fullmatch(quoted(key)):
        return True
    target = TS_STRING.fullmatch(helper.group(1))
    return target is None or bool(SENSITIVE_FIELD.search(quoted(target)))


def focus_after(statement: str, fields: list[bool], last_field_secret: bool) -> bool:
    """Whether the field focused after a statement may be secret. A Tab or Shift+Tab press
    reaches a field the source does not name, whatever locator carries it, so it is secret;
    `press(page, '<id>', key)` is read by its key and test id; otherwise a statement that
    reaches a field decides by that field, and a focus helper names its field by a test id."""
    if TAB_PRESS.search(statement):
        return True
    helper = PRESS_HELPER.search(statement)
    if helper:
        return press_helper_focus(helper)
    if fields:
        return any(fields)
    if FOCUS_HELPER.search(statement):
        names = [quoted(match) for match in TS_STRING.finditer(statement)]
        return not names or any(SENSITIVE_FIELD.search(name) for name in names)
    return last_field_secret


def field_rule(file: str, source: str, sources: tuple[str, ...]) -> list[Found]:
    """The field rule: a literal filled, typed or pressed into a secret field, or set as a
    change event's value on one; and a literal typed with the keyboard while the field the
    file reached last may be a secret field. A bound locator holds what its latest binding
    before the statement reached, so a name bound again later is read by position."""
    found = []
    named: dict[str, bool] = {}
    last_field_secret = False
    for statement_match in re.finditer(r"[^;]+", source):
        statement, offset = statement_match.group(0), statement_match.start()
        hits = typed_literals(statement, last_field_secret, named, sources)
        # A binding's own name is not a field its statement reaches: only its value is.
        reading = NAMED_LOCATOR.sub(lambda binding: binding.group(2), statement)
        fields = statement_fields(reading, named, sources)
        if any(fields):
            # A page's `fill(selector, …)` is read by PAGE_FILL: its first argument is the
            # selector, not the text typed.
            hits += [match for pattern in (FILL, CHANGE_VALUE)
                     for match in pattern.finditer(statement)
                     if not PAGE_RECEIVER.search(statement, 0, match.start())]
        for binding in NAMED_LOCATOR.finditer(statement):
            bound = statement_fields(binding.group(2), named, sources)
            if bound:
                named[binding.group(1)] = any(bound)
        last_field_secret = focus_after(statement, fields, last_field_secret)
        found += [Found(file, source.count("\n", 0, offset + match.start()) + 1,
                        "the field rule", statement.strip()[:80]) for match in hits]
    return found


def typescript_rules(file: str, source: str, sources: tuple[str, ...] | None = None
                     ) -> list[Found]:
    found = []

    def line_of(index: int) -> int:
        return source.count("\n", 0, index) + 1

    def first(groups) -> str:
        return next(item for item in groups if item is not None)

    # Rules (ii)-(iv) on each string literal; a template's `${}` part is a join, generated
    # only when it holds a generator.
    for match in TS_STRING.finditer(source):
        value = first(match.groups())
        if match.group(3) is not None and "${" in value:
            text = re.sub(r"\$\{[^}]*\}", GENERATED, value)
            url = URL_PASSWORD.search(text)
            if url and GENERATED not in url.group(1):
                found.append(Found(file, line_of(match.start()), "rule (iii)", text[:80]))
            if value.startswith(PREFIXES) and not ts_template_generated(value):
                found.append(Found(file, line_of(match.start()), "rule (iv)", value[:80]))
            continue
        key = ts_key(source, match.start(), match.end())
        lowered = value.lower()
        if not key and ("password" in lowered or "secret" in lowered) and not (
                re.search(r"[/\s]", value) or re.fullmatch(r"[A-Za-z_-]+", value)):
            found.append(Found(file, line_of(match.start()), "rule (ii)", value[:80]))
        url = URL_PASSWORD.search(value)
        if url:
            found.append(Found(file, line_of(match.start()), "rule (iii)", value[:80]))
        if (not key and value.startswith(PREFIXES)
                and not ts_join_generated(source, match.start(), match.end())):
            found.append(Found(file, line_of(match.start()), "rule (iv)", value[:80]))
    # Rule (i): a literal bound to a secret-named name or property, unless it is joined to
    # a generated part.
    for match in TS_BINDING.finditer(source):
        name = match.group(1)
        literal_group = next(index for index in (2, 3, 4) if match.group(index) is not None)
        value = match.group(literal_group)
        start, end = match.start(literal_group) - 1, match.end(literal_group) + 1
        if not secret_named(name):
            continue
        if "${" in value and ts_template_generated(value):
            continue
        if ts_join_generated(source, start, end):
            continue
        found.append(Found(file, line_of(match.start()), "rule (i)", match.group(0)[:80]))
    found += ts_join_literals(source, file, line_of)
    # The field rule: a literal filled, typed or pressed into, or changed on, a secret field.
    found += field_rule(file, source, ui_sources() if sources is None else sources)
    return found


def generated_findings(files: dict[str, str]) -> list[Found]:
    found = []
    trees = {file: ast.parse(source) for file, source in files.items() if file.endswith(".py")}
    # The callees' parameters: the repository's, and a planted module's own.
    definitions = dict(nm.repository_definitions())
    planted = {file: tree for file, tree in trees.items() if not (ROOT / file).is_file()}
    for name, entries in nm.definitions_of(planted).items():
        definitions[name] = [*definitions.get(name, []), *entries]
    for file, source in files.items():
        if file.endswith(".py"):
            tree = trees[file]
            rules = Rules(file, tree, definitions)
            rules.visit(tree)
            found += rules.found
        else:
            found += typescript_rules(file, source)
    return found


# Constants that hold no secret, by file and line, kept in step with the code as Step
# 98(d)'s doubles are: an exemption that matches nothing fails the test.
# Each is keyed by file, line and the exempted text itself (a fragment of the finding's
# text), so another finding on the same line is not exempted with it.
_O, _I, _C, _A = T + "operations/", T + "integration/", T + "component/", T + "arrangement/"
EXEMPT = {
    (_O + "test_drivers.py", 923, "fact:password=x"): "the refused fact name under test",
    (_I + "test_account_routes.py", 424, "password.policy"): "the refusal's message key",
    (_O + "test_u8_tool.py", 1408, "password_encryption=scram-sha-256"):
        "the database setting the realm container is started with",
    (_O + "test_installer.py", 1505, "secret.json"): "the name of the holder's file under test",
    ("scripts/u8_fixtures.py", 46, "v1-password.json"):
        "V1_PASSWORD_FILE, the name of the file the per-realm synthetic v1 password is kept in",
    # The same message key as test_account_routes.py's, in the frontend's own tests.
    ("frontend/test/u8-complete/password-policy.test.tsx", 3, "password.policy"):
        "the refusal's message key",
    ("frontend/test/u8-complete/password-policy.test.tsx", 26, "password.policy"):
        "the refusal's message key",
    # The review of build batch 9b: what the full reading of rules (i) and (ii) reaches
    # that holds no secret. File names and folders joined to a path:
    (_A + "test_logrotate.py", 58, "'host.log'"): "a log file's name in a path",
    (_O + "test_logrotate_rules.py", 54, "'host.log'"): "a log file's name in a path",
    (_O + "test_fixed_programs.py", 519, "'secret'"): "a file's name in a path",
    (_O + "test_installer.py", 2277, "'secret'"): "a file's name in a path",
    (_O + "test_installer.py", 2928, "b'Client Key'"):
        "RFC 5802's fixed HMAC label for ClientKey; the key derives from a per-run password",
    (_I + "test_backup_agent_restore.py", 48, "'v2-login'"):
        "the login file's name in a path (its content is generated per run)",
    (_I + "test_cutover_journeys.py", 186, "'v1'"): "a folder's name in a path",
    (_I + "test_cutover_journeys.py", 186, "'credentials.json'"):
        "the realm's credentials file's name in a path",
    (_I + "test_production_composition.py", 1095, "'export-keys'"):
        "the key folder a key file belongs to (a dotted file-name key)",
    (_I + "test_production_composition.py", 1096, "'export-keys'"):
        "the key folder a key file belongs to (a dotted file-name key)",
    (_I + "test_production_composition.py", 1094, "'export-keys'"):
        "the key folder a key file belongs to (a dotted file-name key)",
    # Labels, purposes and keys a derivation or lookup is given:
    (_C + "test_account_mail.py", 1646, "'reset-required'"): "the verifier's purpose label",
    (_C + "test_identity_providers.py", 464, "'n'"): "the claims' nonce label",
    (_C + "test_identity_providers.py", 464, "'rotated-key'"): "the signing key's id",
    (_C + "test_recovery_effects.py", 107, "'database-production'"): "the effect's kind",
    (_C + "test_recovery_effects.py", 107, "'recovery:r:backup:1'"): "the effect's reference",
    (_C + "test_recovery_effects.py", 417, "'database-production'"): "the effect's kind",
    (_C + "test_recovery_effects.py", 417, "'recovery:x:backup:1'"): "the effect's reference",
    (T + "conftest.py", 219, "'SIGN_IN_PASSWORD'"):
        "the process value's name; the password itself is generated per run",
    (T + "conftest.py", 518, "'accounts'"): "the owner the read runs as",
    (_I + "test_backup_agent_in_the_realm.py", 157, "u2-controls-v1"):
        "the derivation label of a key derived from the realm's per-run verifier",
    (_O + "test_drivers.py", 852, "'scheduler'"): "a key of the realm's credentials record",
    (_O + "test_drivers.py", 852, "'roles'"): "a key of the realm's credentials record",
    (_O + "test_production_tool.py", 122, "'password'"):
        "the option's name, read to record only whether a password was given",
    (_O + "test_standing_lanes.py", 1782, "'ledger-copy-'"):
        "the effect token's kind prefix, joined to the receipt's per-run operation ID",
    ("scripts/u8_corpus.py", 39, "':'"): "the corpus's deterministic seed separator",
    ("scripts/u8_fixtures.py", 207, "'password'"): "the record's field name",
    ("scripts/u8_fixtures.py", 611, "'workspace'"): "the stable ID's purpose label",
    ("scripts/u8_fixtures.py", 675, "'notionToken'"):
        "the record's field name; the token is generated per run",
    # The session answer's field the capacity burst reads its CSRF token from:
    ("scripts/u8_phases.py", 1851, "'csrfToken'"):
        "the session answer's field name; the token is the realm's own answer",
    # The re-review of build batch 9b: `diskutil info` answers a keychain test builds before
    # it places them under the `diskutil info` key (they are volume states, not the
    # keychain's answer; the keychain's own answer in that test is generated per run):
    (_O + "test_root_jobs.py", 173, "Could not find disk"): "diskutil's absent-volume answer",
    (_O + "test_root_jobs.py", 173, "Locked:                    Yes"):
        "diskutil's locked-volume answer, the base of the unlocked one",
    (_O + "test_root_jobs.py", 173, "Locked:                    No"):
        "diskutil's unlocked-volume answer",
    # A refused value under test, and a test id (rule (ii) takes no digits):
    (_A + "test_template_lint.py", 141, "not hex"):
        "the refused non-hex value the keychain helper must reject",
    (T + "required_items.py", 218,
     "test_the_21st_attempt_from_one_address_is_refused_before_any_password"):
        "a test's own name",
}


def exemption(item: Found) -> tuple | None:
    return next((key for key in EXEMPT
                 if key[:2] == (item.file, item.line) and key[2] in item.text), None)


def unexempted(found: list[Found]) -> tuple[list[Found], list]:
    hits = [item for item in found if exemption(item) is None]
    matched = {exemption(item) for item in found} - {None}
    stale = [key for key in EXEMPT if key not in matched]
    return hits, stale


def describe(items) -> str:
    """Each finding by its file, line and rule, its matched text masked to its length, so a
    real key, address, iD or typed password never reaches the test output or a CI log. A
    stale exemption is named by its key, whose text the scan already accepted."""
    return "\n".join(f"{item.file}:{item.line} {item.rule} [{len(item.text)} characters "
                     "masked]" if isinstance(item, Found) else f"stale exemption {item}"
                     for item in items)


def require_none(items: list) -> None:
    """Fail with `describe(items)` alone when there is any finding or stale exemption. The
    failure goes through `pytest.fail` with no traceback, not an `assert`, so pytest adds no
    comparison of its own after the message."""
    if items:
        pytest.fail(describe(items), pytrace=False)


def failure_shows(items: list) -> str:
    """The text a failure over `items` shows: the real failure path, caught."""
    with pytest.raises(pytest.fail.Exception) as failure:
        require_none(items)
    return str(failure.value)


def masked_everywhere(found: list[Found], *samples: str) -> bool:
    """No planted sample, and no finding's matched text, reaches the failure or a repr."""
    shown = failure_shows(found) + repr(found)
    return all(sample not in shown for sample in samples) and all(
        item.text not in shown for item in found)


@pytest.fixture(scope="module", autouse=True)
def parsed_trees_released():
    """The callees' parsed trees are freed when this module ends."""
    yield
    nm.release_caches()


def test_no_test_holds_a_real_secret_address_v1_record_or_production_value():
    require_none(real_values(scanned_files()))
    # A planted sample of each, in memory, fails.
    planted = {
        **{f"{T}planted_{index}.py": f"VALUE = {sample!r}\n" for index, sample in enumerate((
            "re_" + "A1b2C3d4E5f6G7h8I9j0K",
            "ntn_" + "a" * 40,
            "secret_" + "b" * 43,
            "GOCSPX-" + "c" * 28,
            "ya29." + "d" * 10,
            "AIza" + "e" * 35,
            "ghp_" + "f" * 36,
            "github_pat_" + "g" * 10,
            "AKIA" + "ABCDEFGHIJKLMNOP",
            "eyJhIjoi" + "h" * 10,
            "https://hc-ping.com/" + "12345678-1234-1234-1234-123456789abc",
            "-----BEGIN " + "RSA PRIVATE KEY-----",
            "person@" + "gmail.com",
            "0000-0002-" + "0000-0006",
        ))},
        f"{T}planted_read.py": "open('/Library/DocSuri/" + "profile/environment.json')\n",
        f"{T}planted_path.py": "Path('/Library/DocSuri') / 'release' \nPath('/Library/"
                               "DocSuri/x').read_text()\n",
        f"{T}planted_connect.py": "import psycopg\npsycopg.connect(host='127.0.0.1', "
                                  "port=5432)\n",
        f"{T}planted_socket.py": "socket.create_connection(('localhost', 6379))\n",
        f"{T}planted_http.py": "httpx.get('http://127.0.0.1:" + "8000/health')\n",
        "frontend/e2e/u8-complete/planted.spec.ts": "await page.goto('http://localhost:"
                                                    "3000/');\n",
        # The review of build batch 9b: a generated local part, a `Path(...).open()`, and
        # a conninfo string or URL to a v1 address.
        f"{T}planted_email.py": 'VALUE = f"{name}@' + 'gmail.com"\n',
        f"{T}planted_open.py": "Path('/Library/DocSuri/" + "x').open()\n",
        f"{T}planted_conninfo.py": "import psycopg\npsycopg.connect('host=127.0.0.1 "
                                   "port=5432 dbname=x')\n",
        f"{T}planted_url.py": "import psycopg\npsycopg.connect('postgresql://u@localhost:"
                              "5432/x')\n",
    }
    for path, source in planted.items():
        found = real_values({path: source})
        assert found, path
        # The failure names file, line and rule, never the planted value: checked on the
        # real failure path (`require_none` caught) and on the findings' repr.
        assert masked_everywhere(found), path
    # The iDs the tree holds after Step 96(d) are invalid; `-0006` would be valid.
    assert not orcid_valid("0000000200000001") and not orcid_valid("0000000200000002")
    assert orcid_valid("0000000200000006")
    # An address passed as data to the environment checks is not a connection.
    assert real_values({f"{T}planted_data.py": "check({'host': '127.0.0.1', "
                                                "'port': 5432})\n"}) == []


def test_every_secret_a_test_uses_is_generated_per_run():
    hits, stale = unexempted(generated_findings(scanned_files()))
    require_none([*hits, *stale])
    failing = {
        # Rule (i): a whole constant at any length, a constant joined only to another
        # constant, an f-string of constants alone, and a constant inside a container or a
        # call argument under a secret-named target.
        "a whole constant": "API_TOKEN = 're_' 'abc'\n",
        "a constant joined to a constant": "password = 'V1!' + 'abcdef'\n",
        "a repeated constant": "seed = 'f' * 64\n",
        "an f-string of constants": "secret = f\"{'x'}y\"\n",
        "a constant in a container": "tokens = ['abc', make()]\n",
        "a constant call argument": "client_secret = bytearray('abc'.encode())\n",
        "a keyword": "connect(password='hunter')\n",
        "a dict key": "{'apiKey': 'abc'}\n",
        "a provider secret key": "KEY = PROVIDER_SECRETS['provider.resend']\n{KEY: 'abc'}\n",
        # Rule (ii): a positional password.
        "a positional password": "refusal(entry, member, 'wrong-password-u8')\n",
        # Rule (iii): a URL with a literal password, also in an f-string.
        "a URL": "url = 'postgresql://v1:hunter2@127.0.0.1:15510/db'\n",
        "an f-string URL": "url = f'postgresql://v1:hunter2@127.0.0.1:{port}/db'\n",
        # Rule (iv): each provider prefix, built from constants alone.
        "re_": "value = 're_abc'\n", "ntn_": "value = 'ntn_x'\n",
        "secret_": "value = 'secret_x'\n", "GOCSPX-": "value = 'GOCSPX-x'\n",
        "a prefix joined to a constant": "value = 're_' + 'abc'\n",
        # The key-bytes rule: the old cursor keys and released passwords.
        "a constant cursor key": "cursor_key = b'k' * 32\n",
        "a constant key file": "write_private(root / 'cursor-key' / 'search-cursor.key', "
                               "b'k' * 32)\n",
        "a constant verifier key": "(folder / VERIFIER_KEY).write_bytes(b'k')\n",
        "a constant released password": "driver(release=lambda login: bytearray(b'x' * 64))\n",
        "a released password function": ("def released(login):\n"
                                         "    return bytearray(b'x' * 64)\n"
                                         "driver(release=released)\n"),
        # The review of build batch 9b: each shape the narrower reading let through.
        "a constant method-call argument": "password_hash = hasher.hash('hunter2')\n",
        "a constant environment default": "password = os.environ.get(KEY, 'hunter2')\n",
        "a join of a literal list": "password = ''.join(['hunter', '2'])\n",
        "a dotted key": "{'db.password': 'hunter2'}\n",
        "a prefix joined to a module constant": "value = 're_' + FIXED_TAIL\n",
        "a constant joined to a part not generated": "password = 'hunter2' + suffix\n",
        "an f-string with a part not generated": "password = f'pw-{index}'\n",
        "a prefix f-string with a part not generated": "value = f're_{index}'\n",
        "a base64-looking constant with a slash": "client_secret = 'Zm9v/YmFy'\n",
        "a provider key as a dict key": "{PROVIDER_SECRETS['provider.google']: 'literal'}\n",
        "a provider key as a subscript target": ("env[PROVIDER_SECRETS['provider.google']] = "
                                                 "'literal'\n"),
        "a constant passed by position": ("def planted_sign_in(email, password):\n"
                                          "    return email\n"
                                          "planted_sign_in(email, 'any-password-at-all')\n"),
        "a constant passed by position to a method": (
            "class Entry:\n"
            "    def planted_login(self, email, password):\n"
            "        return email\n"
            "entry.planted_login(email, 'x')\n"),
        "rule (ii) on bytes": "value = b'secret1'\n",
        "rule (iv) on bytes": "value = b're_abc'\n",
        "a credential stand-in's answer": (
            "def test_x(context):\n"
            "    context.run = Tools(stdout=b's3cret-value\\n')\n"
            "    call('docsuri-credential-release', ['restore'], context)\n"),
        "a credential stand-in's answer through a name": (
            "def test_x(context):\n"
            "    released = b's3cret-value\\n'\n"
            "    context.run = Tools(stdout=released)\n"
            "    call('docsuri-credential-release', ['restore'], context)\n"),
        # The re-review of build batch 9b: positional answers, the keychain's own tool,
        # module constants, released values, parameter defaults and dotted key names.
        "a keychain answer by position in an answers map": (
            "run = Recorded({'security': [Done(b'hunter2\\n')]})\n"),
        "a module constant a keychain answer names": (
            "PASS = b'correct horse'\n"
            "def test_x():\n"
            "    run = Recorded({'diskutil info': [Done('ok')], 'security': [Done(PASS)]})\n"),
        "a positional answer in a test of the keychain tool": (
            "def test_x():\n"
            "    run = Tools(b'hunter2')\n"
            "    assert run.calls == [['/usr/bin/security', '-w']]\n"),
        "a module constant answered through stdout": (
            "PASS = b'hunter2'\n"
            "def test_x(context):\n"
            "    context.run = Tools(stdout=PASS)\n"
            "    call('docsuri-credential-release', ['restore'], context)\n"),
        "a released value bound": "released = bytearray(b'wrong-password')\n",
        "a released value passed by keyword": (
            "one_connection('restore', released=bytearray(b'abc'))\n"),
        "a released value passed by position": ("def planted_use(login, released):\n"
                                                "    return login\n"
                                                "planted_use('restore', b'abc')\n"),
        "a parameter default": ("def planted_sign_in(password='hunter2'):\n"
                                "    return password\n"),
        "a keyword-only parameter default": ("def planted_sign_in(*, token='abc'):\n"
                                             "    return token\n"),
        "a dotted key holding key bytes": "{'cursor.key': b'k' * 32}\n",
    }
    for name, source in failing.items():
        assert generated_findings({f"{T}planted.py": source}), name
    passing = {
        "a prefix joined to a generated part": ("import secrets\n"
                                                "key = 're_' + secrets.token_hex(16)\n"),
        "a prefix in an f-string with a generated part": "token = f're_{uuid4().hex}'\n",
        "a generated password": "password = 'V1!' + secrets.token_urlsafe(24)\n",
        "a generated key": "cursor_key = secrets.token_bytes(32)\n",
        "a generated release": ("driver(release=lambda login: bytearray(secrets.token_hex(32)"
                                ".encode()))\n"),
        "a route": "post('/api/account/password-reset')\n",
        "an environment variable": "name = 'GOOGLE_CLIENT_SECRET'\n",
        "a URL name": "GOOGLE_TOKEN_URL = 'https://oauth2.googleapis.com/token'\n",
        "a subscript": "value = settings['re_x']\n",
        "a prefix joined to a slice of uuid4": "token = 'probe-' + uuid4().hex[:12]\n",
        "a name bound to a generated value": ("tail = secrets.token_hex(8)\n"
                                              "password = 'V1!' + tail\n"),
        "a generated credential answer": (
            "def test_x(context):\n"
            "    context.run = Tools(stdout=secrets.token_hex(16).encode() + b'\\n')\n"
            "    call('docsuri-credential-release', ['restore'], context)\n"),
        "a generated keychain answer": (
            "run = Recorded({'security': [Done(secrets.token_hex(8).encode())]})\n"),
        "another tool's answer in a test of the keychain tool": (
            "def test_x():\n"
            "    run = Recorded({'diskutil info': [Done('Locked: Yes')],\n"
            "                    'security': [Done(secrets.token_hex(8).encode())]})\n"
            "    assert run.calls == [['/usr/bin/security']]\n"),
        "a generated released value": "released = bytearray(uuid4().hex.encode())\n",
    }
    for name, source in passing.items():
        assert generated_findings({f"{T}planted.py": source}) == [], name
    # An exemption covers its own text only: another finding on its line is not exempted.
    key = next(iter(EXEMPT))
    other = Found(key[0], key[1], "rule (i): a constant bound to a secret-named target",
                  "password = 'hunter2'")
    assert unexempted([other])[0] == [other]
    # The field rule, TypeScript: a literal filled into, or changed on, a secret field.
    ts_failing = {
        "fill by test id": "await page.getByTestId('entry-password').fill('pass-word-1');\n",
        "fill by Korean label": "await page.getByLabel('현재 비밀번호').fill('abc-1');\n",
        "fill through a name": ("const field = page.getByTestId('connect-token');\n"
                                "await field.fill('abc');\n"),
        "a change event": ("fireEvent.change(screen.getByLabelText('새 비밀번호'), "
                           "{ target: { value: 'pass-word-1' } });\n"),
        "rule (iv) in TypeScript": "const key = 're_abc';\n",
        "a repeated constant in TypeScript": "const session = { csrfToken: 'c'.repeat(64) };\n",
        "rule (ii) in TypeScript": "const value = 'my-secret-1';\n",
        "rule (iii) in TypeScript": "const url = 'postgresql://v1:hunter2@127.0.0.1:15510/db';\n",
        "a join of two constants in TypeScript": "const key = 're_' + 'abc';\n",
        "a password join of two constants": "const login = { password: 'a' + 'b' };\n",
        "a ternary's first branch": "const value = flag ? 're_abc' : other;\n",
        # The re-review of build batch 9b: a literal after the join's first operand, and a
        # generator in the previous statement that is not the join's own operand.
        "a literal later in a password join": "const password = prefix + 'hunter2';\n",
        "a generator outside the join's operand": ("const id = crypto.randomUUID(); "
                                                   "const key = make() + 're_abc';\n"),
    }
    for name, source in ts_failing.items():
        assert generated_findings({"frontend/test/u8-complete/planted.test.tsx": source}), name
    assert generated_findings({"frontend/test/u8-complete/planted.test.tsx": (
        "await page.getByTestId('proof-password').fill(`U8-${randomUUID()}-1!`);\n"
        "await page.getByTestId('search-query').fill('attention transformer');\n"
        "const login = { password: 'U8-' + crypto.randomUUID() };\n")}) == []
    # Batch 10b's second fix pass (an addition for Step 104 under L1-36): a field reached by
    # a CSS selector, matched by its id, name or label, and literal text typed with the
    # keyboard, a locator's `type` or `pressSequentially`.
    css_failing = {
        # `#lifecycle-proof` names no secret; its label, '계정 처리용 현재 비밀번호', does
        # (frontend/src/account-controls.tsx).
        "a CSS id whose field's label names a secret": (
            "await page.locator('#lifecycle-proof').fill('u8-placeholder');\n"),
        "a CSS id that names a secret": "await page.locator('#entry-password').fill('x1');\n",
        "a CSS name that names a secret": (
            "await page.locator('input[name=\"password\"]').fill('x1');\n"),
        "a CSS selector through a bound locator": (
            "const proof = page.locator('#lifecycle-proof');\nawait proof.fill('x1');\n"),
        "a locator's type": "await page.getByLabel('새 비밀번호').type('x1');\n",
        "a locator's pressSequentially": (
            "await page.locator('#lifecycle-proof').pressSequentially('x1');\n"),
        "the keyboard after a secret field": (
            "await page.getByTestId('entry-password').focus();\n"
            "await page.keyboard.type('x1');\n"),
        "the keyboard after a CSS-selected secret field": (
            "await page.locator('#lifecycle-proof').click();\n"
            "await page.keyboard.insertText('x1');\n"),
    }
    # The build batch 10c review: a name bound again later, the other Testing Library
    # queries, `user.type`'s second argument, `user.keyboard`, and focus moved by Tab or by
    # a focus helper (keyboardSignIn's shape).
    css_failing |= {
        "fill through a name bound again later": (
            "const field = page.getByTestId('connect-token');\n"
            "await field.fill('abc');\n"
            "const field = page.getByTestId('search-query');\n"),
        "a change event through findByTestId": (
            "fireEvent.change(await screen.findByTestId('proof-password'), "
            "{ target: { value: 'pass-word-1' } });\n"),
        "a fill through queryByLabelText": (
            "await screen.queryByLabelText('새 비밀번호').fill('x1');\n"),
        "a fill through getAllByTestId": (
            "await page.getAllByTestId('entry-password').fill('x1');\n"),
        "a fill through findAllByTestId": (
            "await page.findAllByTestId('entry-password').fill('x1');\n"),
        "user.type's second argument": (
            "await user.type(screen.getByLabelText('새 비밀번호'), 'pass-word-1');\n"),
        "userEvent.type through a name": (
            "const field = screen.getByTestId('entry-password');\n"
            "await userEvent.type(field, 'pass-word-1');\n"),
        "user.keyboard after a secret field": (
            "await user.click(screen.getByTestId('entry-password'));\n"
            "await user.keyboard('pass-word-1');\n"),
        "the keyboard after a Tab press (keyboardSignIn's shape)": (
            "await reach(page, page.getByTestId('entry-email'), 'entry-email');\n"
            "await page.keyboard.type(account.email);\n"
            "await page.keyboard.press('Tab');\n"
            "await page.keyboard.type('pass-word-1');\n"),
        "the keyboard after Shift+Tab": (
            "await page.getByTestId('search-query').focus();\n"
            "await page.keyboard.press('Shift+Tab');\n"
            "await page.keyboard.type('pass-word-1');\n"),
        "the keyboard after user.tab": (
            "await user.tab();\nawait user.keyboard('pass-word-1');\n"),
        "the keyboard after a focus helper naming a secret field": (
            "await focusTestId(page, 'entry-password');\n"
            "await page.keyboard.type('pass-word-1');\n"),
    }
    # The build batch 10c re-review: a Tab press whatever locator carries it, the keyboard
    # spec's `press(page, '<id>', key)`, getByRole's `name` option, and a page's or frame's
    # `fill` or `type` with a selector.
    css_failing |= {
        "a Tab press carried by a locator that is no secret": (
            "await page.getByTestId('entry-email').press('Tab');\n"
            "await page.keyboard.type('pass-word-1');\n"),
        "a Tab press with a computed key": (
            "await page.keyboard.press(back ? 'Shift+Tab' : 'Tab');\n"
            "await page.keyboard.type('pass-word-1');\n"),
        "the press helper with Tab": (
            "await press(page, 'entry-email', 'Tab');\n"
            "await page.keyboard.type('pass-word-1');\n"),
        "the press helper on a secret field": (
            "await press(page, 'entry-password', 'End');\n"
            "await page.keyboard.type('pass-word-1');\n"),
        "getByRole's name option": (
            "await page.getByRole('textbox', { name: 'Notion 토큰' }).fill('x1');\n"),
        "getByRole's name option as a regex": (
            "await page.getByRole('textbox', { name: /비밀번호/ }).fill('x1');\n"),
        "page.fill with a selector naming a secret": (
            "await page.fill('#entry-password', 'x1');\n"),
        "page.type into a field its label names": (
            "await page.type('#lifecycle-proof', 'x1');\n"),
        "frame.fill with a secret name": (
            "await frame.fill('input[name=\"password\"]', 'x1');\n"),
    }
    for name, source in css_failing.items():
        found = generated_findings({"frontend/e2e/u8-complete/planted.spec.ts": source})
        assert "the field rule" in [item.rule for item in found], name
        # Checked on the real failure path and on the findings' repr, not on describe alone.
        assert masked_everywhere(found, "pass-word-1", "'x1'"), name
    css_passing = {
        "a CSS id of a field that is no secret": (
            "await page.locator('#main summary').click();\n"
            "await page.keyboard.type('attention transformer');\n"),
        "a generated value typed into a CSS-selected secret field": (
            "await page.locator('#lifecycle-proof').fill(`u8-${randomUUID()}`);\n"),
        "a value from a record typed with the keyboard": (
            "await page.getByTestId('entry-password').focus();\n"
            "await page.keyboard.type(account.password);\n"),
        "the keyboard after leaving the secret field": (
            "await page.getByTestId('entry-password').focus();\n"
            "await page.getByTestId('search-query').focus();\n"
            "await page.keyboard.type('attention transformer');\n"),
        "a name bound to a secret field, then to another before its fill": (
            "const field = page.getByTestId('connect-token');\n"
            "const field = page.getByTestId('search-query');\n"
            "await field.fill('attention transformer');\n"),
        "user.type's literal into a field that is no secret": (
            "await user.type(screen.getByTestId('entry-email'), 'member@example.com');\n"),
        "key descriptors after a secret field": (
            "await user.click(screen.getByTestId('entry-password'));\n"
            "await user.keyboard('{Enter}');\n"),
        "a focus helper naming a field that is no secret": (
            "await reach(page, page.getByTestId('entry-email'), 'entry-email');\n"
            "await page.keyboard.type('member@example.com');\n"),
        # The build batch 10c re-review: the helper branch with no locator in the statement,
        # after a secret field; the press helper leaving one; getByRole's name naming no
        # secret; a page's fill into a field that is no secret, and a page's fill whose
        # selector names a secret field but whose value comes from a record.
        "a focus helper with no locator, after a secret field": (
            "await page.getByTestId('entry-password').focus();\n"
            "await focusTestId(page, 'entry-email');\n"
            "await page.keyboard.type('member@example.com');\n"),
        "the press helper leaving a secret field": (
            "await page.getByTestId('entry-password').focus();\n"
            "await press(page, 'search-query', 'End');\n"
            "await page.keyboard.type('attention transformer');\n"),
        "getByRole's name naming no secret": (
            "await page.getByRole('textbox', { name: '검색어' }).fill('attention transformer');\n"),
        "page.fill into a field that is no secret": (
            "await page.fill('#u8-planted-search', 'attention transformer');\n"),
        "page.fill of a record's value into a secret field": (
            "await page.fill('#lifecycle-proof', account.password);\n"),
    }
    for name, source in css_passing.items():
        assert generated_findings({"frontend/e2e/u8-complete/planted.spec.ts": source}) == [], (
            name)
    # The field's label, `aria-label`, flag or `<label htmlFor>` names it, as the
    # application writes it.
    sources = ('<Field id="u8-planted-a" label="새 비밀번호" value={a} />',
               '<input name="u8-planted-b" aria-label="Notion 토큰" />',
               '<label htmlFor="u8-planted-c">Recovery seed</label><input id="u8-planted-c"/>',
               '<input id="u8-planted-d" type="text" aria-label="검색어" />')
    assert [selector_secret(f"#u8-planted-{key}", sources) for key in "abcd"] == [
        True, False, True, False]
    assert selector_secret('[name="u8-planted-b"]', sources)
