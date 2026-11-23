"""Every required item names a collected test, a phase or a boundaries row (U8 plan Step
98(b), written and registered in Step 98(f)).

It checks the required items (`required_items.py`, Step 96(g)) and the demand for E2E,
performance and security tests together. Each entry resolves through `lane_map.py` (Step
96(h)) to exactly one of:

- a pytest node found by AST in a file a phase collects;
- a tagged title in a spec the resolver gives a phase (`[PERF]` only in `performance`);
- a Vitest test in `frontend/test/u8-complete`;
- a row of the plan's "Completion and evidence boundaries" whose first cell names the item
  (a range such as NFR8.1–NFR8.5 names each item in it); the rows are parsed from
  `code-generation-plan.md` and the table is pinned by SHA-256;
- for NFR8.6's two crash clauses only, `restart-host` or `restart-database` in
  `VERIFICATION_ORDER`.

Beside that: each section's SHA-256 and bullet count (48, 8, 13, 20) equal the record's,
and each bullet has its entry; `u8_phases.JOURNEYS` holds exactly the module's literal
journeys, and BR10.3's and BR10.6's texts equal their pins; D3's fourth entry names the
security spec's fresh-browser title (Step 100(c)); no entry is marked open, pending or
skipped; and each split item's entries name exactly its clauses, at least one of them on
no row and at most one on a row (L1-59). The boundaries rows stand as your answers of
2026-11-02 accepted them (L1-59, L1-60).

A row "names the item" when its first cell holds the item's NFR number (alone or inside a
range), or, for the other items, the phrase `ROW_NAMES` gives it, which the item's own
bullet (or its group's heading) holds as well.
"""

from __future__ import annotations

import dataclasses
import hashlib
import re
import types
from pathlib import Path

import pytest

from tests.u8_service_operations_integration import lane_map
from tests.u8_service_operations_integration import required_items as ri

ROOT = Path(__file__).resolve().parents[3]
PLAN = f"{ri.RECORD}/code-generation/code-generation-plan.md"
BOUNDARIES = "## Completion and evidence boundaries"
BOUNDARIES_SHA256 = "1d417cc884308b3726273bbe8e042fcfdd0a518232e35a0eb966d2ab20d83de9"
PLAN_BULLETS = {"security-design-15": 48, "code-summary-starts": 8,
                "security-requirements": 13, "cicd-pipeline-11": 20}
TARGETS = ("pytest", "playwright", "vitest", "row", "phase")
NOTES = frozenset({"wording", "settled"})
MARKS = frozenset({"open", "pending", "skipped", "status"})
CRASH_CLAUSES = {"nfr8/NFR8.6/crashed-host": "restart-host",
                 "nfr8/NFR8.6/crashed-database": "restart-database"}
D3_FOURTH = ("security.spec.ts",
             "[SEC] each email link opened in a fresh browser explains it and asks again here")
# Kept unedited in the table and superseded by the NFR8.1–NFR8.5 row: no item maps to it
# (plan Step 96(g); the table's own note).
SUPERSEDED_ROW = "NFR8.1–NFR8.6 at the production scale on this Mac"

# Each section's groups, by the marker its top-level bullet holds; `None` takes every
# top-level bullet of the block as one group.
GROUPS = {
    "security-design-15": {name: f"({name})" for name in (
        "D1", "D2", "D3", "D4", "D5", "D6", "D7", "D11", "D14", "D12")},
    "code-summary-starts": {"provider-starts": "Provider sign-in starts"},
    "security-requirements": {"required": None},
    "cicd-pipeline-11": {
        "ci": "CI and the release workflow",
        "refusals": "Refusals before production changes",
        "failures": "Failures during an install",
        "compatibility": "Compatibility and the arrangement",
        "release-folders": "Release folders",
        "after-install": "After an install",
    },
}

# The split items and their clauses (Step 96(g), L1-59, and the lead's checks after build
# batches 8 and 9a).
SPLIT_CLAUSES = {
    "security-design-15/D1/1": {"lengths", "no-extension"},
    "code-summary-starts/provider-starts/6": {"open-flows", "starts"},
    "code-summary-starts/provider-starts/8": {"d2", "digest"},
    "security-requirements/required/3": {"scram", "listener-and-superuser"},
    "security-requirements/required/9": {"signed-out", "other-owner"},
    "cicd-pipeline-11/ci/3": {"guard", "first-release"},
    "cicd-pipeline-11/ci/5": {"write-token", "budget"},
    "cicd-pipeline-11/compatibility/1": {"planted-tag", "real-release"},
    "cicd-pipeline-11/after-install/1": {"readiness", "ledger"},
    "nfr8/NFR8.6": {"crashed-host", "crashed-database", "installation-and-rehearsal"},
    "nfr8/NFR8.7": {"settings", "served-peak", "production-scale"},
    "nfr8/NFR8.8": {"run-durations", "switch-start-subject", "real-v1-data"},
    "nfr8/NFR8.11": {"pinned-versions", "runtime-upgrade"},
    "nfr8/NFR8.12": {"twenty-users", "only-migrated-accounts", "account-cap"},
}

# The phrase by which a row's first cell names an item that is not an NFR8 item; the
# item's bullet, or its group's heading, holds it too.
ROW_NAMES = {
    **{f"security-design-15/D4/{position}": "(D4)" for position in range(1, 6)},
    "security-design-15/D5/1": "D5",
    "security-design-15/D7/6": ("the shell fetched through the public address equals the "
                                "release's build byte for byte"),
    "security-requirements/required/1": "NFR1.5",
    "security-requirements/required/3": "NFR3.3",
    "security-requirements/required/4": "operator tool's",
    "security-requirements/required/6": "NFR3.8",
    "cicd-pipeline-11/ci/1": "required check",
    "cicd-pipeline-11/ci/3": "`v2.0.0` through `custom_tag`",
    "cicd-pipeline-11/compatibility/1": "The previous release's critical journeys",
}


# --- reading the record ------------------------------------------------------------------


def table_block(text: str, heading: str) -> str:
    """The first table after `heading` (an exact line): its contiguous `|` lines."""
    lines = text.splitlines(keepends=True)
    start = next(index for index, line in enumerate(lines) if line.rstrip("\n") == heading)
    first = next(index for index in range(start + 1, len(lines))
                 if lines[index].startswith("|"))
    block = []
    for line in lines[first:]:
        if not line.startswith("|"):
            break
        block.append(line)
    return "".join(block)


def first_cells(table: str) -> list[str]:
    """Each body row's first cell, the header and its separator left out."""
    rows = table.splitlines()[2:]
    return [row[2:].split(" | ", 1)[0].strip() for row in rows]


def groups_of(block: str, markers: dict) -> dict[str, list[str]]:
    """Each group's leaf bullets: the children of the top-level bullet that holds its
    marker, or that bullet itself when it has none; `None` takes every top-level bullet."""
    lines = [line for line in block.splitlines() if line.lstrip().startswith("- ")]
    tops = [index for index, line in enumerate(lines) if line.startswith("- ")]
    found = {}
    for name, marker in markers.items():
        if marker is None:
            found[name] = [lines[index] for index in tops]
            continue
        top = next((index for index in tops if marker in lines[index]), None)
        if top is None:
            found[name] = []
            continue
        end = next((index for index in tops if index > top), len(lines))
        children = lines[top + 1:end]
        depths = [len(line) - len(line.lstrip()) for line in children]
        leaves = [line for index, line in enumerate(children)
                  if index + 1 == len(children) or depths[index + 1] <= depths[index]]
        found[name] = leaves or [lines[top]]
    return found


def heading_of(block: str, marker: str | None) -> str:
    return next((line for line in block.splitlines()
                 if line.startswith("- ") and marker and marker in line), "")


@dataclasses.dataclass(frozen=True)
class Tree:
    """What the checker reads; a planted variant replaces one field."""

    entries: dict
    texts: dict
    sections: dict
    rules: str
    table: str
    journeys: dict
    phases: object
    runner: object
    root: Path = ROOT


def phases_view(phases, **changes) -> types.SimpleNamespace:
    """The phases module's lists the checker and the resolver read, with `changes`."""
    names = ("BROWSER_SPECS", "SECURITY_TESTS", "RESTORE_TESTS", "REPAIR_CHECKS",
             "JOURNEYS", "VERIFICATION_ORDER")
    return types.SimpleNamespace(**{**{name: getattr(phases, name) for name in names},
                                    **changes})


def current_tree() -> Tree:
    runner, phases = lane_map.modules()
    texts = {key: (ROOT / section["path"]).read_text(encoding="utf-8")
             for key, section in ri.SECTIONS.items()}
    plan = (ROOT / PLAN).read_text(encoding="utf-8")
    return Tree(
        entries=dict(ri.ENTRIES), texts=texts, sections=dict(ri.SECTIONS),
        rules=(ROOT / ri.RULES["path"]).read_text(encoding="utf-8"),
        table=table_block(plan, BOUNDARIES), journeys=dict(ri.JOURNEYS),
        phases=phases_view(phases), runner=runner)


# --- the checks --------------------------------------------------------------------------


def item_of(key: str) -> tuple[str, str | None]:
    """An entry's item key and its clause (None for an unsplit item)."""
    parts = key.split("/")
    size = 2 if parts[0] == "nfr8" else 3
    return "/".join(parts[:size]), ("/".join(parts[size:]) or None)


def nfr_named(cell: str, number: int) -> bool:
    """Whether a first cell names NFR8.<number>, alone or inside a range."""
    for match in re.finditer(r"NFR8\.(\d+)(?!\d)(?:–NFR8\.(\d+)(?!\d))?", cell):
        low = int(match.group(1))
        high = int(match.group(2) or low)
        if low <= number <= high:
            return True
    return False


def section_problems(tree: Tree) -> list[str]:
    problems = []
    for key, section in tree.sections.items():
        block = ri.bullet_block(tree.texts[key], section["heading"])
        if ri.sha256(block) != section["sha256"]:
            problems.append(f"{key}: the section's SHA-256 differs from the record's")
        if ri.leaf_count(block) != section["bullets"]:
            problems.append(f"{key}: {ri.leaf_count(block)} bullets, the record says "
                            f"{section['bullets']}")
        if section["bullets"] != PLAN_BULLETS.get(key):
            problems.append(f"{key}: the record's bullet count is not the plan's")
    for rule in ("BR10.3", "BR10.6"):
        if ri.sha256(ri.rule_text(tree.rules, rule)) != ri.RULES[rule]:
            problems.append(f"{rule}: the rule's text differs from its pin")
    if hashlib.sha256(tree.table.encode("utf-8")).hexdigest() != BOUNDARIES_SHA256:
        problems.append("the boundaries table differs from its pin")
    return problems


def expected_items(tree: Tree) -> dict[str, str]:
    """Each item the record holds, with the text its row-name is read from."""
    items = {}
    for source, markers in GROUPS.items():
        block = ri.bullet_block(tree.texts[source], tree.sections[source]["heading"])
        for group, leaves in groups_of(block, markers).items():
            heading = heading_of(block, markers[group])
            for position, leaf in enumerate(leaves, start=1):
                items[f"{source}/{group}/{position}"] = f"{heading}\n{leaf}"
    items.update({f"nfr8/NFR8.{number}": f"NFR8.{number}" for number in range(1, 13)})
    items.update({f"br10-3/journeys/{name}": name for name in tree.journeys})
    return items


def coverage_problems(tree: Tree, items: dict[str, str]) -> list[str]:
    problems = []
    named = {item_of(key)[0] for key in tree.entries}
    for item in sorted(set(items) - named):
        problems.append(f"{item}: no mapping")
    for item in sorted(named - set(items)):
        problems.append(f"{item}: names no bullet of the record")
    for source, section in tree.sections.items():
        count = sum(1 for item in items if item.startswith(source + "/"))
        if count != section["bullets"]:
            problems.append(f"{source}: {count} bullets have a place, the record says "
                            f"{section['bullets']}")
    return problems


def journey_problems(tree: Tree) -> list[str]:
    problems = []
    built = {name: value[0] for name, value in tree.phases.JOURNEYS.items()}
    for name in sorted(set(built) | set(tree.journeys)):
        if built.get(name) != tree.journeys.get(name):
            problems.append(f"br10-3/journeys/{name}: JOURNEYS holds {built.get(name)!r}, "
                            f"the module {tree.journeys.get(name)!r}")
    return problems


def target_problem(tree: Tree, key: str, entry: dict) -> str | None:
    """Why an entry's one target does not resolve, or None."""
    kinds = [kind for kind in TARGETS if kind in entry]
    if len(kinds) != 1:
        return f"{key}: names {len(kinds)} targets"
    kind = kinds[0]
    if kind == "pytest" and not lane_map.pytest_phases(
            entry["pytest"], runner=tree.runner, phases=tree.phases, root=tree.root):
        return f"{key}: {entry['pytest']} is in no file a phase collects"
    if kind == "playwright" and not lane_map.playwright_phases(
            *entry["playwright"], phases=tree.phases, root=tree.root):
        return f"{key}: {entry['playwright'][1]!r} runs in no phase"
    if kind == "vitest" and not lane_map.vitest_runs(*entry["vitest"], root=tree.root):
        return f"{key}: {entry['vitest'][1]!r} is not in U8's Vitest lane"
    if kind == "phase" and (CRASH_CLAUSES.get(key) != entry["phase"]
                            or entry["phase"] not in tree.phases.VERIFICATION_ORDER):
        return f"{key}: only NFR8.6's crash clauses name a phase"
    return None


def row_problem(tree: Tree, key: str, row: str, items: dict[str, str]) -> str | None:
    cells = first_cells(tree.table)
    if row not in cells:
        return f"{key}: the boundaries table has no row {row[:40]!r}"
    if row == SUPERSEDED_ROW:
        return f"{key}: the superseded row names no item"
    item = item_of(key)[0]
    if item.startswith("nfr8/"):
        number = int(item.removeprefix("nfr8/NFR8."))
        return None if nfr_named(row, number) else f"{key}: the row does not name the item"
    name = ROW_NAMES.get(item)
    if name is None or name not in row or name not in items.get(item, ""):
        return f"{key}: the row does not name the item"
    return None


def entry_problems(tree: Tree, items: dict[str, str]) -> list[str]:
    problems = []
    for key, entry in tree.entries.items():
        marked = MARKS & set(entry) or any(
            isinstance(value, str) and value.lower() in MARKS for value in entry.values())
        if marked:
            problems.append(f"{key}: marked open, pending or skipped")
        if set(entry) - set(TARGETS) - NOTES - MARKS:
            problems.append(f"{key}: carries an unknown field")
        problem = target_problem(tree, key, entry)
        if problem is None and "row" in entry:
            problem = row_problem(tree, key, entry["row"], items)
        if key in CRASH_CLAUSES and "phase" not in entry:
            problem = problem or f"{key}: NFR8.6's crash clause names no phase"
        if problem:
            problems.append(problem)
    fourth = tree.entries.get(f"{ri.SD}/D3/4", {})
    if fourth.get("playwright") != (f"{ri.SPECS}/{D3_FOURTH[0]}", D3_FOURTH[1]) or not (
            fourth.get("wording") and fourth.get("settled")):
        problems.append(f"{ri.SD}/D3/4: does not name the fresh-browser [SEC] title with "
                        "its settled wording")
    return problems


def split_problems(tree: Tree) -> list[str]:
    problems = []
    clauses: dict[str, list[tuple[str | None, dict]]] = {}
    for key, entry in tree.entries.items():
        item, clause = item_of(key)
        clauses.setdefault(item, []).append((clause, entry))
    for item, found in sorted(clauses.items()):
        names = [clause for clause, _ in found]
        if item not in SPLIT_CLAUSES:
            if names != [None]:
                problems.append(f"{item}: split, but not a split item")
            continue
        if None in names or set(names) != SPLIT_CLAUSES[item] or len(names) != len(set(names)):
            problems.append(f"{item}: its clauses are not each mapped once")
        rows = sum(1 for _, entry in found if "row" in entry)
        if rows > 1 or rows == len(found):
            problems.append(f"{item}: needs a clause off a row and at most one on a row")
    for item in sorted(set(SPLIT_CLAUSES) - set(clauses)):
        problems.append(f"{item}: a split item with no entry")
    return problems


def check(tree: Tree) -> list[str]:
    """Every problem found, each naming its item, section or table."""
    problems = section_problems(tree)
    items = expected_items(tree)
    problems += coverage_problems(tree, items)
    problems += journey_problems(tree)
    problems += entry_problems(tree, items)
    problems += split_problems(tree)
    return problems


@pytest.fixture(scope="module")
def tree() -> Tree:
    return current_tree()


# --- the tests ---------------------------------------------------------------------------


def test_every_pre_installation_required_item_names_a_collected_test(tree):
    problems = check(tree)
    assert problems == [], "\n".join(problems)
    # The sections' counts are the plan's, and the journeys are BR10.3's sixteen.
    assert [section["bullets"] for section in tree.sections.values()] == [48, 8, 13, 20]
    assert list(tree.journeys) == [*(f"J{number:02d}" for number in range(1, 15)),
                                   "A11Y", "SEC"]
    # D3's fourth entry runs in the security phase.
    assert lane_map.playwright_phases(f"{ri.SPECS}/{D3_FOURTH[0]}", D3_FOURTH[1],
                                      phases=tree.phases) == {"security"}
    # NFR8.6's crash clauses rest on the two restart phases, never on a row.
    for key, phase in CRASH_CLAUSES.items():
        assert tree.entries[key] == {"phase": phase}
    # Every row an entry names is a row of the table, with each split item's one row.
    rows = {entry["row"] for entry in tree.entries.values() if "row" in entry}
    assert rows <= set(first_cells(tree.table))
    assert len(first_cells(tree.table)) == 25


def planted(tree: Tree, **changes) -> Tree:
    return dataclasses.replace(tree, **changes)


def with_entry(tree: Tree, key: str, entry: dict | None) -> Tree:
    entries = dict(tree.entries)
    if entry is None:
        entries.pop(key)
    else:
        entries[key] = entry
    return planted(tree, entries=entries)


def named(problems: list[str], text: str) -> bool:
    return any(text in problem for problem in problems)


def variants(tree: Tree) -> dict[str, tuple[Tree, str]]:
    """Each planted variant, built in memory, with the item the checker must name."""
    t = ri.T
    sd_text = tree.texts[ri.SD].replace("ends 12 hours after", "ends 13 hours after", 1)
    renamed = {**tree.journeys, "J07": "job-lifecycles"}
    dropped = {name: value for name, value in tree.journeys.items() if name != "J07"}
    built_renamed = {name: (("job-lifecycles", *value[1:]) if name == "J07" else value)
                     for name, value in tree.phases.JOURNEYS.items()}
    no_security = {phase: specs for phase, specs in tree.phases.BROWSER_SPECS.items()
                   if phase != "security"}
    return {
        "no mapping": (with_entry(tree, "nfr8/NFR8.10", None), "nfr8/NFR8.10"),
        "a missing function": (with_entry(tree, f"{ri.SD}/D1/2", {
            "pytest": f"{t}/component/test_production_policy.py::test_no_such_test"}),
            f"{ri.SD}/D1/2"),
        "a file no phase collects": (with_entry(tree, f"{ri.SD}/D1/3", {
            "pytest": f"{t}/host_flows.py::production_instance"}), f"{ri.SD}/D1/3"),
        "an untagged title": (with_entry(tree, f"{ri.SD}/D3/1", {
            "playwright": (f"{ri.SPECS}/security.spec.ts", "a Google sign-in arrives back "
                           "cross-site and signs the linked account in")}), f"{ri.SD}/D3/1"),
        "a spec outside BROWSER_SPECS": (planted(tree, phases=phases_view(
            tree.phases, BROWSER_SPECS=no_security)), f"{ri.SD}/D3/1"),
        "a row the table lacks": (with_entry(tree, "nfr8/NFR8.9", {
            "row": "NFR8.9 somewhere the table does not say"}), "nfr8/NFR8.9"),
        "a row that does not name the item": (with_entry(tree, "nfr8/NFR8.9", {
            "row": ri.ROW_MEMORY}), "nfr8/NFR8.9"),
        "a row that does not name a non-NFR8 item": (with_entry(tree, f"{ri.SD}/D5/1", {
            "row": ri.ROW_SUDO}), f"{ri.SD}/D5/1"),
        "an entry on the superseded row": (with_entry(tree, "nfr8/NFR8.3", {
            "row": SUPERSEDED_ROW}), "nfr8/NFR8.3"),
        "a changed section digest": (planted(tree, texts={**tree.texts, ri.SD: sd_text}),
                                     ri.SD),
        "a changed bullet count": (planted(tree, sections={
            **tree.sections, ri.SD: {**tree.sections[ri.SD], "bullets": 47}}), ri.SD),
        "a journey dropped": (planted(tree, phases=phases_view(tree.phases, JOURNEYS={
            name: value for name, value in tree.phases.JOURNEYS.items() if name != "J07"})),
            "br10-3/journeys/J07"),
        "a journey renamed in JOURNEYS": (planted(tree, phases=phases_view(
            tree.phases, JOURNEYS=built_renamed)), "br10-3/journeys/J07"),
        "a journey renamed in the module": (planted(tree, journeys=renamed),
                                            "br10-3/journeys/J07"),
        "a journey dropped from the module": (planted(tree, journeys=dropped),
                                              "br10-3/journeys/J07"),
        "a crash clause on a row": (with_entry(tree, "nfr8/NFR8.6/crashed-host", {
            "row": ri.ROW_RESTART}), "nfr8/NFR8.6/crashed-host"),
        "a split item's clause unmapped": (with_entry(
            tree, "nfr8/NFR8.8/run-durations", None), "nfr8/NFR8.8"),
        "a split item with every clause on a row": (planted(tree, entries={
            **{key: value for key, value in tree.entries.items()
               if not key.startswith("nfr8/NFR8.11/")},
            "nfr8/NFR8.11/runtime-upgrade": {"row": ri.ROW_UPGRADE},
            "nfr8/NFR8.11/pinned-versions": {"row": ri.ROW_UPGRADE}}), "nfr8/NFR8.11"),
        "an entry marked pending": (with_entry(tree, "nfr8/NFR8.10", {
            **tree.entries["nfr8/NFR8.10"], "status": "pending"}), "nfr8/NFR8.10"),
        "D3's fourth entry on its old title": (with_entry(tree, f"{ri.SD}/D3/4", {
            **tree.entries[f"{ri.SD}/D3/4"],
            "playwright": (f"{ri.SPECS}/security.spec.ts", "[SEC] a password-reset link "
                           "opened in a fresh browser is refused with guidance")}),
            f"{ri.SD}/D3/4"),
    }


def test_an_unmapped_or_uncollected_required_item_fails(tree):
    for name, (variant, item) in variants(tree).items():
        problems = check(variant)
        assert problems, name
        assert named(problems, item), f"{name}: {problems}"
    # A range in a first cell names each item inside it, and nothing outside it.
    assert nfr_named(ri.ROW_SCALE, 3) and nfr_named(ri.ROW_SCALE, 12)
    assert not nfr_named(ri.ROW_SCALE, 6) and not nfr_named(ri.ROW_SCALE, 11)


PLANTED_PYTEST = '''\
import pytest

pytestmark = []


def row():
    pass


def test_runs():
    pass


@pytest.mark.skip(reason="planted")
def test_skipped():
    pass
'''
PLANTED_SKIPPED_MODULE = ("import pytest\n\npytestmark = [pytest.mark.skip]\n\n\n"
                          "def test_any():\n    pass\n")
PLANTED_SPEC = '''\
import { test } from '@playwright/test';

test('[SEC] runs', async () => {});
// test('[SEC] commented out', async () => {});
/* test('[SEC] in a block comment', async () => {}); */
test.describe.skip('a skipped block', () => {
  test('[SEC] inside a skipped describe', async () => {});
});
test.skip('[SEC] skipped itself', async () => {});
test('[PERF] measured outside navigation', async () => {});
const sheet = /\\brel\\s*=\\s*["']?stylesheet/i;
const link = /\\bhref\\s*=\\s*["']([^"']+)["']/i;
// test('[SEC] commented out after a quote-holding regex', async () => {});
test('[SEC] runs after the regexes', async () => {});
const half = total / 2; // test('[SEC] commented out after a division', async () => {});
'''
PLANTED_VITEST = '''\
import { describe, it } from 'vitest';

describe('planted', () => {
  it('runs', () => {});
  // it('commented out', () => {});
  it.skip('skipped itself', () => {});
  const view = <p>Don't stop</p>;
  // it('commented out after JSX text', () => {});
  it('runs after JSX text', () => {});
});
describe.skip('a skipped block', () => {
  it('inside a skipped describe', () => {});
});
'''


def test_the_resolver_accepts_only_a_test_that_runs(tmp_path):
    """Planted in a scratch tree: a helper function, a skipped pytest test or module, a
    commented-out or skipped title, and a `[PERF]` title outside `navigation.spec.ts` each
    resolve to nothing, while the running test beside each one resolves."""
    folder = tmp_path / lane_map.TEST_ROOT / "component"
    folder.mkdir(parents=True)
    (folder / "test_planted.py").write_text(PLANTED_PYTEST, encoding="utf-8")
    (folder / "test_skipped_module.py").write_text(PLANTED_SKIPPED_MODULE, encoding="utf-8")
    specs = tmp_path / lane_map.SPEC_ROOT
    specs.mkdir(parents=True)
    (specs / "security.spec.ts").write_text(PLANTED_SPEC, encoding="utf-8")
    vitest = tmp_path / lane_map.VITEST_ROOT
    vitest.mkdir(parents=True)
    (vitest / "planted.test.tsx").write_text(PLANTED_VITEST, encoding="utf-8")
    runner = types.SimpleNamespace(LANE_HALVES={"component": {
        "component-1": ("test_planted.py", "test_skipped_module.py")}})
    phases = types.SimpleNamespace(SECURITY_TESTS=(), RESTORE_TESTS=(), REPAIR_CHECKS=(),
                                   BROWSER_SPECS={"security": ("security.spec.ts",)})
    node = f"{lane_map.TEST_ROOT}/component/test_planted.py"

    def collected(target):
        return lane_map.pytest_phases(target, runner=runner, phases=phases, root=tmp_path)

    assert collected(f"{node}::test_runs") == {"component-1"}
    assert collected(f"{node}::row") == set()
    assert collected(f"{node}::test_skipped") == set()
    assert collected(f"{lane_map.TEST_ROOT}/component/test_skipped_module.py::test_any") == set()

    spec = f"{lane_map.SPEC_ROOT}/security.spec.ts"

    def runs_in(title):
        return lane_map.playwright_phases(spec, title, phases=phases, root=tmp_path)

    assert runs_in("[SEC] runs") == {"security"}
    # The build batch 10c re-review: a quote inside a regex literal opens no string.
    assert runs_in("[SEC] runs after the regexes") == {"security"}
    for title in ("[SEC] commented out", "[SEC] in a block comment",
                  "[SEC] inside a skipped describe", "[SEC] skipped itself",
                  "[PERF] measured outside navigation",
                  "[SEC] commented out after a quote-holding regex",
                  "[SEC] commented out after a division"):
        assert runs_in(title) == set(), title

    file = f"{lane_map.VITEST_ROOT}/planted.test.tsx"
    assert lane_map.vitest_runs(file, "runs", root=tmp_path)
    assert lane_map.vitest_runs(file, "runs after JSX text", root=tmp_path)
    for title in ("commented out", "skipped itself", "inside a skipped describe",
                  "commented out after JSX text"):
        assert not lane_map.vitest_runs(file, title, root=tmp_path), title
