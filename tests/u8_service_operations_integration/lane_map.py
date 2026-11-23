"""The phase resolver (U8 plan Step 96(h)), shared by `operations/test_required_items.py`
(Step 98(b)) and `operations/test_component_volume.py` (Step 98(c)).

It answers three questions, reading the runner's and the phases' own lists:

- which phases collect a pytest file or node: the layer folders `database` and
  `repository`; the parts of `runner.LANE_HALVES` (component, integration and operations);
  `phases.SECURITY_TESTS` (security); `phases.RESTORE_TESTS` (restore-paths);
  `phases.REPAIR_CHECKS` (repair-exercise); and the `arrangement` folder (arrangement);
- which phases run a tagged Playwright title: the phase whose `phases.BROWSER_SPECS` names
  its spec, except that `[PERF]` runs only in `performance`, and only from
  `navigation.spec.ts`, the one spec `run_performance` runs with `--grep '[PERF]'`
  (`u8_phases.py:999`); every other browser phase leaves `[PERF]` titles out;
- which tests U8's Vitest lane runs: the `frontend` phase runs
  `test/u8-complete/**/*.test.{ts,tsx}`, as `vitest.u8-complete.config.ts` includes them.

A test is found only where it runs. A pytest node is a top-level `test_` function, by AST,
with no unconditional `pytest.mark.skip` on it or on its module (`pytestmark`). A title is
read from its spec or test file with the comments removed and every skipped block
(`describe.skip`, `test.describe.skip`, `describe.fixme`, `test.describe.fixme`,
`xdescribe`) blanked; `test.skip(…)`, `it.skip(…)` and `test.fixme(…)` never match. The
comment stripper reads string, template and regex literals as literals (a `/` opens a regex
after an operator, an opening bracket or a keyword such as `return`), and a `'` or `"` right
after a letter or digit as JSX text, so a quote inside a regex or an apostrophe never hides
a comment.
Nothing is imported from a test module: only the runner and the phases module, which are
scripts.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TEST_ROOT = "tests/u8_service_operations_integration"
SPEC_ROOT = "frontend/e2e/u8-complete"
VITEST_ROOT = "frontend/test/u8-complete"
VITEST_PATTERN = re.compile(r"(?:[^/]+/)*[^/]+\.test\.tsx?")
TAGGED = re.compile(r"^\[(J\d\d|A11Y|SEC|PERF)\] ")
LAYERS = ("database", "repository")
PERF_SPEC = "navigation.spec.ts"
SKIPPED_BLOCK = re.compile(
    r"\b(?:(?:test\.)?describe\.(?:skip|fixme)|xdescribe)\s*(?=\()")
QUOTES = "'\"`"


def modules():
    """The runner (`scripts/verify_docsuri_u8.py`) and the phases (`scripts/u8_phases.py`),
    imported from the repository's scripts folder."""
    for entry in (ROOT, ROOT / "ingestion/src", ROOT / "ops/src", ROOT / "scripts"):
        if str(entry) not in sys.path:
            sys.path.insert(0, str(entry))
    import u8_phases
    import verify_docsuri_u8

    return verify_docsuri_u8, u8_phases


def _skip_mark(node: ast.expr) -> bool:
    """Whether a decorator or mark is an unconditional `pytest.mark.skip` (bare or called)."""
    if isinstance(node, ast.Call):
        node = node.func
    return isinstance(node, ast.Attribute) and node.attr == "skip" and isinstance(
        node.value, ast.Attribute) and node.value.attr == "mark"


def _module_skipped(tree: ast.Module) -> bool:
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
                isinstance(target, ast.Name) and target.id == "pytestmark"
                for target in node.targets):
            marks = node.value.elts if isinstance(node.value, (ast.List, ast.Tuple)) else [
                node.value]
            if any(_skip_mark(mark) for mark in marks):
                return True
    return False


def has_function(path: str, name: str, *, root: Path = ROOT) -> bool:
    """Whether the file defines a top-level pytest test `name` (sync or async) that pytest
    runs, by AST: its name starts with `test_`, and neither it nor its module carries an
    unconditional `pytest.mark.skip`."""
    file = root / path
    if not name.startswith("test_") or not file.is_file():
        return False
    tree = ast.parse(file.read_text(encoding="utf-8"))
    if _module_skipped(tree):
        return False
    return any(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name
               and not any(_skip_mark(mark) for mark in node.decorator_list)
               for node in tree.body)


def _file_phases(path: str, runner, phases) -> set[str]:
    found: set[str] = set()
    if not path.startswith(TEST_ROOT + "/"):
        return found
    relative = path.removeprefix(TEST_ROOT + "/")
    folder, _, name = relative.partition("/")
    if "/" in name or not name.startswith("test_") or not name.endswith(".py"):
        return found
    if folder in LAYERS:
        found.add(folder)
    if folder == "arrangement":
        found.add("arrangement")
    for part, files in runner.LANE_HALVES.get(folder, {}).items():
        if name in files:
            found.add(part)
    if path in phases.SECURITY_TESTS:
        found.add("security")
    if path in phases.RESTORE_TESTS:
        found.add("restore-paths")
    if path in phases.REPAIR_CHECKS:
        found.add("repair-exercise")
    return found


def pytest_phases(target: str, *, runner=None, phases=None, root: Path = ROOT) -> set[str]:
    """The phases that collect a pytest file (`path`) or node (`path::function`), the path
    relative to the repository; empty when no phase collects it or the function is missing.
    A node in `REPAIR_CHECKS` is collected by `repair-exercise` on its own."""
    if runner is None or phases is None:
        runner, phases = modules()
    path, _, function = target.partition("::")
    if function and not has_function(path, function, root=root):
        return set()
    found = _file_phases(path, runner, phases)
    if function and target in phases.REPAIR_CHECKS:
        found.add("repair-exercise")
    return found


# A `/` opens a regex literal, not a division, after one of these characters or keywords
# (the build batch 10c re-review: a quote inside a regex literal no longer opens a string).
REGEX_AFTER = frozenset("(,=:[!&|?{};+-*%<>~^")
REGEX_KEYWORDS = frozenset({"return", "typeof", "case", "do", "else", "in", "of", "new",
                            "delete", "void", "throw", "yield", "await", "instanceof"})


def _string_end(text: str, start: int) -> int:
    """The index just past the string literal that opens at `start`. A `'` or `"` string
    ends at its line's end, as JavaScript requires; a template may span lines."""
    quote, index = text[start], start + 1
    while index < len(text) and text[index] != quote:
        if text[index] == "\n" and quote != "`":
            return index
        index += 2 if text[index] == "\\" else 1
    return index + 1


def _regex_end(text: str, start: int) -> int | None:
    """The index just past the regex literal (flags included) that opens at `start`, or
    None when no closing `/` follows on its line."""
    index, in_class = start + 1, False
    while index < len(text) and text[index] != "\n":
        char = text[index]
        if char == "\\":
            index += 2
            continue
        if char == "[":
            in_class = True
        elif char == "]":
            in_class = False
        elif char == "/" and not in_class:
            index += 1
            while index < len(text) and (text[index].isalnum() or text[index] in "_$"):
                index += 1
            return index
        index += 1
    return None


def _regex_allowed(tail: str) -> bool:
    """Whether a `/` after this code (comments already blanked) opens a regex literal."""
    tail = tail.rstrip()
    if not tail or tail[-1] in REGEX_AFTER:
        return True
    word = re.search(r"[A-Za-z_$][\w$]*$", tail)
    return word is not None and word.group(0) in REGEX_KEYWORDS


def _literal_end(text: str, index: int, tail: str) -> int | None:
    """The index just past the string, template or regex literal that opens at `index`, or
    None when none opens there. A `'` or `"` right after a letter or digit is JSX text (an
    apostrophe, as in `Don't`), since no string literal can follow an identifier."""
    char = text[index]
    if char in QUOTES:
        previous = text[index - 1] if index else ""
        if char != "`" and (previous.isalnum() or previous in ("_", "$")):
            return None
        return _string_end(text, index)
    if char == "/" and text[index + 1:index + 2] not in ("/", "*") and _regex_allowed(tail):
        return _regex_end(text, index)
    return None


def _tail(tail: str, chunk: str) -> str:
    """The last code seen, enough to decide a `/`: whitespace collapsed, at most 32
    characters."""
    return re.sub(r"\s+", " ", tail + chunk)[-32:]


def _without_comments(text: str) -> str:
    """The source with `//` and `/* */` comments blanked; string, template and regex
    literals kept."""
    out, index, tail = [], 0, ""
    while index < len(text):
        end = _literal_end(text, index, tail)
        if end is not None:
            out.append(text[index:end])
            tail = _tail(tail, "0")
            index = end
        elif text.startswith("//", index):
            end = text.find("\n", index)
            end = len(text) if end < 0 else end
            out.append(" " * (end - index))
            tail = _tail(tail, " ")
            index = end
        elif text.startswith("/*", index):
            end = text.find("*/", index + 2)
            end = len(text) if end < 0 else end + 2
            out.append(re.sub(r"[^\n]", " ", text[index:end]))
            tail = _tail(tail, " ")
            index = end
        else:
            out.append(text[index])
            tail = _tail(tail, text[index])
            index += 1
    return "".join(out)


def _call_end(text: str, opening: int) -> int:
    """The index just past the `)` that closes the call whose `(` is at `opening`, in a
    source whose comments are already blanked."""
    depth, index, tail = 0, opening, text[max(0, opening - 32):opening]
    while index < len(text):
        end = _literal_end(text, index, tail)
        if end is not None:
            tail = _tail(tail, "0")
            index = end
            continue
        char = text[index]
        depth += {"(": 1, ")": -1}.get(char, 0)
        tail = _tail(tail, char)
        index += 1
        if depth == 0:
            return index
    return len(text)


def live_source(text: str) -> str:
    """The source as its runner runs it: comments removed, skipped blocks blanked."""
    text = _without_comments(text)
    while (match := SKIPPED_BLOCK.search(text)) is not None:
        end = _call_end(text, match.end())
        text = text[:match.start()] + re.sub(r"[^\n]", " ", text[match.start():end]) + text[end:]
    return text


def _titles(text: str) -> set[str]:
    return set(re.findall(r"""\btest\(\s*(['"`])(.+?)\1""", live_source(text), flags=re.S))


def playwright_phases(spec: str, title: str, *, phases=None, root: Path = ROOT) -> set[str]:
    """The phases that run a tagged title of a spec (`frontend/e2e/u8-complete/<spec>`):
    `[PERF]` only in `performance`, any other tag in the phase whose `BROWSER_SPECS` names
    the spec. Empty for an untagged title, a title the spec does not hold, or a spec no
    phase names."""
    if phases is None:
        _, phases = modules()
    tag = TAGGED.match(title)
    file = root / spec
    if tag is None or not spec.startswith(SPEC_ROOT + "/") or not file.is_file():
        return set()
    if title not in {found for _, found in _titles(file.read_text(encoding="utf-8"))}:
        return set()
    name = spec.removeprefix(SPEC_ROOT + "/")
    if tag.group(1) == "PERF":
        return {"performance"} if name == PERF_SPEC and any(
            name in specs for specs in phases.BROWSER_SPECS.values()) else set()
    return {phase for phase, specs in phases.BROWSER_SPECS.items() if name in specs}


def vitest_runs(file: str, title: str, *, root: Path = ROOT) -> bool:
    """Whether U8's Vitest lane (the `frontend` phase) runs a test of this title: a
    `*.test.ts` or `*.test.tsx` file under `frontend/test/u8-complete` that holds an `it` or
    `test` of exactly this title."""
    path = root / file
    if not file.startswith(VITEST_ROOT + "/") or not path.is_file():
        return False
    if not VITEST_PATTERN.fullmatch(file.removeprefix(VITEST_ROOT + "/")):
        return False
    text = live_source(path.read_text(encoding="utf-8"))
    pattern = r"""\b(?:it|test)(?:\.each\([^)]*\))?\(\s*(['"`])(.+?)\1"""
    return title in {found for _, found in re.findall(pattern, text, flags=re.S)}
