"""The pinned built files fail on any change, committed or not (U8 plan Steps 22, 24 and 44).

The "unchanged" guards of U3's, U4's and U5's coverage scopes, U4's and U5's restored
files and U2's key recovery compare each file with its SHA-256 pinned at the branch base
(`built_files`). Unlike `git diff HEAD`, which is empty in CI because the checkout is the
pull request's own commit, a pin catches a change that is already committed. These
tests plant such changes in a copy of the tree and show the check names each one.
"""

from __future__ import annotations

import hashlib
import shutil
import subprocess

import pytest

from tests.u8_service_operations_integration.built_files import (
    BASE_COMMIT,
    BUILT_DIGESTS,
    ROOT,
    SEAM_DIGESTS,
    U1_TEST_DIGESTS,
    changed_from_built,
)


def copy_of_pinned(tmp_path):
    root = tmp_path / "tree"
    for relative in BUILT_DIGESTS:
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, target)
    return root


def test_every_pinned_file_holds_its_built_bytes_now():
    # 62 (Step 97(h)): Step 82(f)'s 52 with U6's history.tsx, copy.ts and history.test.tsx
    # (L1-61, L1-62), plus Step 91(d)'s ui.tsx and api.ts (L1-53) and Step 91(m)'s
    # account-controls.tsx (L1-58), plus Step 96(f)'s five lane configurations,
    # backend/.coveragerc.u6 and U2's cumulative lane. U7's runner sits at its bytes after
    # Step 46(i)'s one DOCKER_HOST line (L1-77), a re-pin that changes no count.
    assert len(BUILT_DIGESTS) == 62
    for pinned in ("frontend/src/u6-export/history.tsx", "frontend/src/u6-export/copy.ts",
                   "frontend/test/u6-export/history.test.tsx", "frontend/src/ui.tsx",
                   "frontend/src/api.ts", "frontend/src/account-controls.tsx",
                   "scripts/verify_docsuri_u7.py"):
        assert pinned in BUILT_DIGESTS
    assert changed_from_built(BUILT_DIGESTS) == {}


def test_u7s_two_seam_files_hold_their_seam_bytes_now():
    """U7's `executor.py` and `native_adapter.py` hold only U8's two seams over their
    built text (Step 44), and `executor.py` one name more in its child's environment,
    DOCKER_HOST (L1-78); U7's runner is pinned at its bytes after its one DOCKER_HOST
    line (L1-77), and every other U7 file is pinned at the branch base."""
    assert sorted(SEAM_DIGESTS) == ["ops/src/docsuri_ops/platform_control/executor.py",
                                    "ops/src/docsuri_ops/platform_control/native_adapter.py"]
    assert not set(SEAM_DIGESTS) & set(BUILT_DIGESTS)
    assert changed_from_built(SEAM_DIGESTS, pins=SEAM_DIGESTS) == {}


def test_u1s_tests_hold_their_built_bytes_but_the_one_fixed_test_file(tmp_path):
    """U1's 46 tracked test files are pinned (L1-33): 45 at the branch base and
    `component/test_local_search.py` at its bytes after "Fix U1's test"."""
    git = shutil.which("git")
    assert git is not None
    listed = subprocess.run(
        [git, "ls-files", "-z", "tests/u1_integrated_paper_journey"], cwd=ROOT, check=True,
        capture_output=True, timeout=30).stdout.decode().split("\0")
    tracked = sorted(path for path in listed if path)
    assert len(tracked) == 46
    assert sorted(U1_TEST_DIGESTS) == tracked
    assert not set(U1_TEST_DIGESTS) & set(BUILT_DIGESTS)
    assert changed_from_built(U1_TEST_DIGESTS, pins=U1_TEST_DIGESTS) == {}
    root = tmp_path / "tree"
    for relative in U1_TEST_DIGESTS:
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, target)
    assert changed_from_built(U1_TEST_DIGESTS, root=root, pins=U1_TEST_DIGESTS) == {}
    for planted in (tracked[0], "tests/u1_integrated_paper_journey/component/"
                    "test_local_search.py", tracked[-1]):
        target = root / planted
        original = target.read_bytes()
        target.write_bytes(original + b"\n# planted\n")
        found = changed_from_built(U1_TEST_DIGESTS, root=root, pins=U1_TEST_DIGESTS)
        assert set(found) == {planted}
        target.write_bytes(original)


def test_a_planted_change_in_a_seam_file_fails_its_pin(tmp_path):
    root = tmp_path / "tree"
    for relative in SEAM_DIGESTS:
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, target)
    assert changed_from_built(SEAM_DIGESTS, root=root, pins=SEAM_DIGESTS) == {}
    executor = root / "ops/src/docsuri_ops/platform_control/executor.py"
    executor.write_text(executor.read_text().replace(
        'NATIVE_ADAPTER = "docsuri_ops.platform_control.native_adapter"',
        'NATIVE_ADAPTER = "docsuri_ops.elsewhere"'))
    found = changed_from_built(SEAM_DIGESTS, root=root, pins=SEAM_DIGESTS)
    assert set(found) == {"ops/src/docsuri_ops/platform_control/executor.py"}


def test_a_planted_change_fails_the_check_even_once_committed(tmp_path):
    root = copy_of_pinned(tmp_path)
    assert changed_from_built(BUILT_DIGESTS, root=root) == {}
    # A rewrite of U5's policy and a lowered U5 floor, committed in a repository of its
    # own: `git diff HEAD` is then empty, and the pins still name both files.
    policy, rc = root / "backend/u5_policy.py", root / "backend/.coveragerc.u5"
    policy.write_bytes(policy.read_bytes() + b"\n# a later rewrite\n")
    rc.write_text(rc.read_text().replace("fail_under = 80", "fail_under = 79"))
    git = shutil.which("git")
    assert git is not None
    # No hook, signing or template of this machine's configuration takes part.
    isolated = ["-c", "core.hooksPath=/dev/null", "-c", "commit.gpgsign=false",
                "-c", "init.templateDir=", "-c", "user.email=pin@test.invalid",
                "-c", "user.name=pin"]
    for argv in (["init", "-q"], ["add", "-A"], ["commit", "-q", "--no-verify", "-m",
                                                  "planted"]):
        subprocess.run([git, *isolated, *argv], cwd=root, check=True, capture_output=True,
                       timeout=30)
    head = subprocess.run([git, "diff", "--quiet", "HEAD"], cwd=root, timeout=30)
    assert head.returncode == 0  # what the old guard saw: nothing
    found = changed_from_built(BUILT_DIGESTS, root=root)
    assert set(found) == {"backend/u5_policy.py", "backend/.coveragerc.u5"}
    assert found["backend/u5_policy.py"] == hashlib.sha256(policy.read_bytes()).hexdigest()


def test_a_missing_file_and_an_unpinned_path_never_pass(tmp_path):
    root = copy_of_pinned(tmp_path)
    (root / "backend/.coveragerc.u3").unlink()
    assert changed_from_built(["backend/.coveragerc.u3"], root=root) == {
        "backend/.coveragerc.u3": None}
    with pytest.raises(KeyError, match="no pinned digest"):
        changed_from_built(["backend/u6_policy.py"], root=root)


def test_the_pins_name_the_branch_base():
    assert len(BASE_COMMIT) == 40 and all(c in "0123456789abcdef" for c in BASE_COMMIT)
    assert all(len(value) == 64 for value in BUILT_DIGESTS.values())
    assert all(len(value) == 64 for value in SEAM_DIGESTS.values())
