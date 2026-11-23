"""The realm-check scan of decision "Allowlist sites" (U8 plan Step 24, the person's
decision of 2026-10-23, "Fix it, widen the check").

In the files the allowlist test scans (`test_allowlist_sites.listed`, outside U8's own
new files), every comparison of a profile's realm with an earlier unit's realm name
(`==`, `!=`, `in` or `not in`, against a literal or a literal tuple, list or set) is
found from the syntax tree. A site passes when it names the composed realm, or when
`LIMITED` lists it as limited to its unit on purpose, with the reason and the test that
proves the composed realm's own path there. A new comparison fails until it is one or
the other.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from backend import local_profile
from tests.u8_service_operations_integration.operations import test_allowlist_sites as sites

ROOT = Path(__file__).resolve().parents[3]
COMPOSED = "service-operations"
EARLIER = frozenset(realm for unit, (_, realm) in local_profile.REALMS.items() if unit != "u8")
OPERATORS = (ast.Eq, ast.NotEq, ast.In, ast.NotIn)
T = "tests/u8_service_operations_integration"

# (file, line) -> (reason, the test that proves the composed realm's own path there).
SELF = f"{T}/operations/test_realm_checks.py"
LIMITED: dict[tuple[str, int], tuple[str, str]] = {
    ("backend/local_host.py", 467): (
        "assemble_journey, U1's and U2's own assembly; the complete assembly never calls it",
        SELF),
    ("backend/local_profile.py", 110): (
        "U1's journey database selector, called only by U1's scripts", SELF),
    ("backend/modules/accounts/control_policy.py", 35): (
        "U2's synthetic policy binds only U2's realm; U8's `CompletePolicy` binds the "
        "complete realms (the person's decision of 2026-10-24, \"Move, scope tools, test U2\")",
        f"{T}/component/test_u2_seam_defaults.py"),
    ("ops/src/docsuri_ops/u2_restore.py", 196): (
        "U2's restore rehearsal is bound to U2's own environment (the plan's table changes "
        "only its two image checks)", f"{T}/operations/test_u2_restore_image.py"),
    ("backend/u3_host.py", 250): (
        "assemble_u3's contribution gates; the complete assembly never calls assemble_u3",
        f"{T}/operations/test_assemblies_alone.py"),
    ("backend/modules/discovery/local_http.py", 56): (
        "U1's and U2's discovery router; the complete assembly mounts U3's (`u3_http`), "
        "whose signed-in search goes through row 11", f"{T}/integration/test_signed_in_search.py"),
    ("backend/modules/discovery/local_http.py", 79): (
        "U1's and U2's discovery router; the complete assembly mounts U3's (`u3_http`), "
        "whose signed-in search goes through row 11", f"{T}/integration/test_signed_in_search.py"),
}


# The eight checks the person's decision of 2026-10-23 ("Route through U2's controls")
# gives the composed path: U2's control path in the composed and production realms, with
# each realm's own policy (the plan's row "U2's controls in the complete app").
# file -> how many such checks it holds; proved by `integration/test_complete_controls.py`.
GIVEN: dict[str, int] = {
    "backend/modules/plans/local_http.py": 1,  # the usage router
    "backend/modules/plans/guarded_repository.py": 1,  # inspect_assignment
    "backend/modules/personalization/local_http.py": 1,  # the controls block
    "backend/modules/library/local_http.py": 1,  # the library router
    "backend/modules/library/repository/guarded.py": 1,  # the guard purpose
    "backend/modules/summarization/guarded_repository.py": 2,  # erased admission, period
    "backend/modules/summarization/admission.py": 1,  # the usage reservation
}
GIVEN_PROOF = f"{T}/integration/test_complete_controls.py"


def strings(node) -> frozenset[str] | None:
    """The literal strings a comparator names, or None when it is not all literals."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return frozenset({node.value})
    if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        found: set[str] = set()
        for element in node.elts:
            value = strings(element)
            if value is None:
                return None
            found |= value
        return frozenset(found)
    return None


def is_realm(node) -> bool:
    return (isinstance(node, ast.Attribute) and node.attr == "realm") or (
        isinstance(node, ast.Name) and node.id == "realm")


def comparisons(source: str) -> list[tuple[int, frozenset[str]]]:
    found = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Compare) or len(node.ops) != 1:
            continue
        if not isinstance(node.ops[0], OPERATORS):
            continue
        left, right = node.left, node.comparators[0]
        for subject, other in ((left, right), (right, left)):
            if is_realm(subject):
                named = strings(other)
                if named and named & EARLIER:
                    found.append((node.lineno, named))
    return found


def scan() -> dict[tuple[str, int], frozenset[str]]:
    result = {}
    for name in sites.listed():
        if sites.own(name):
            continue
        for line, named in comparisons((ROOT / name).read_text()):
            result[(name, line)] = named
    return result


def test_every_realm_check_names_the_composed_realm_or_is_listed_as_limited():
    unlisted = sorted(key for key, named in scan().items()
                      if COMPOSED not in named and key not in LIMITED)
    assert unlisted == [], unlisted


def test_every_listed_site_still_exists_and_still_leaves_the_composed_realm_out():
    found = scan()
    stale = sorted(key for key in LIMITED if key not in found or COMPOSED in found[key])
    assert stale == [], stale


@pytest.mark.parametrize("site", sorted(LIMITED))
def test_each_listed_site_has_its_reason_and_an_existing_proving_test(site):
    reason, proof = LIMITED[site]
    assert reason and (ROOT / proof).is_file(), (site, proof)


def test_the_scan_reads_every_comparison_form():
    source = (
        'a = profile.realm == "account-controls"\n'
        'b = "corpus-maintenance" != self.realm\n'
        'c = realm in ("topics-digests", "service-operations")\n'
        'd = x.profile.realm not in ["approved-export"]\n'
        'e = profile.realm == "journey"\n'
        'f = profile.name == "account-controls"\n'
    )
    assert [line for line, _ in comparisons(source)] == [1, 2, 3, 4]
    assert COMPOSED in dict(comparisons(source))[3]


def test_the_complete_assembly_never_reaches_the_entry_points_limited_to_earlier_units():
    """The proof for the listed U1/U2/U3-only entry points: no module of the complete
    assembly calls U1's and U2's journey assembly, U1's journey selector, U3's own
    assembly, or U1's and U2's discovery router."""
    names = {"assemble_journey", "assemble_u3", "journey"}
    for path in sorted((ROOT / "backend").glob("u8_*.py")):
        reached = []
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Name) and node.id in names:
                reached.append(node.id)
            elif isinstance(node, ast.Attribute) and node.attr in names:
                reached.append(node.attr)
            elif isinstance(node, ast.ImportFrom) and (node.module or "").endswith(
                    "discovery.local_http"):
                reached.append(node.module)
            elif isinstance(node, ast.alias) and node.name in names:
                reached.append(node.name)
        assert reached == [], (path.name, reached)


def test_the_eight_checks_take_u2s_control_path_in_the_composed_and_production_realms():
    found = scan()
    assert sum(GIVEN.values()) == 8
    for path, count in GIVEN.items():
        sites_here = [named for (name, _), named in found.items() if name == path]
        given = [named for named in sites_here
                 if {"account-controls", COMPOSED, "production"} <= named]
        assert len(given) == count, (path, sites_here)
    assert (ROOT / GIVEN_PROOF).is_file()


def test_the_flow_cap_seam_is_chosen_by_the_service_not_by_a_realm_check():
    """The person's decisions of 2026-10-25 ("Cap per address, raise site cap", "Count
    every start, free places at once"): U2's `begin` holds no realm comparison for its
    open-flow cap. U2's realm keeps 20 because it builds U2's `ControlIdentityService`;
    the complete realms get U2's cap at 201, one above the site's 200 that U8 counts after
    the flow is written, and the start limits, because only they build U8's
    `ArrivalIdentityService`, which refuses an entry that is not a complete realm's."""
    from backend.modules.accounts.services.control_identity import ControlIdentityService
    from backend.modules.accounts.u8_identity import ArrivalIdentityService

    identity = "backend/modules/accounts/services/control_identity.py"
    assert identity in sites.listed() and not sites.own(identity)
    assert [key for key in scan() if key[0] == identity] == []
    assert comparisons((ROOT / identity).read_text()) == []
    assert ControlIdentityService.flow_capacity == 20
    assert ArrivalIdentityService.flow_capacity == 201
    source = (ROOT / "backend/modules/accounts/u8_identity.py").read_text()
    assert comparisons(source) == []  # nor does U8's service compare realms
    assert "d1_shaped" in source


def test_row_11_names_the_composed_realm_and_production_at_both_sites():
    found = scan()
    row = [named for (name, _), named in found.items()
           if name == "backend/modules/discovery/guarded_repository.py"]
    assert len(row) == 2
    for named in row:
        assert named == {"account-controls", "corpus-maintenance", COMPOSED, "production"}
