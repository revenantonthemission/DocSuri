"""The first v2 release's guard (U8 plan Step 44; cicd-pipeline § 4, step 3)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


@pytest.fixture
def guard():
    from scripts import verify_docsuri_u8

    scripts = str(Path(verify_docsuri_u8.ROOT) / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    import u8_release_guard

    return u8_release_guard


@pytest.mark.parametrize(("previous", "created", "reason"), [
    (0, "v2.0.0", None),               # the first v2 release, as release.yml forces it
    (0, "v2.0.1", "first-v2-release-not-v2.0.0"),
    (0, "v1.20.0", "created-tag-not-v2"),
    (3, "v2.4.1", None),               # every later release, from the newest v2 tag
    (3, "2.4.1", "created-tag-not-v2"),
    (1, "", None),                     # no release this run: nothing is published
    (-1, "v2.0.0", "previous-count-invalid"),
])
def test_the_guard_fails_a_wrong_first_version_and_passes_the_rest(
        guard, previous, created, reason):
    assert guard.verdict(previous, created) == reason


def test_the_guard_prints_one_result_and_fails_the_job_on_a_refusal(guard, capsys):
    assert guard.main(["--previous-v2-tags", "0", "--created", "v2.1.0"]) == 1
    result = json.loads(capsys.readouterr().out)
    assert result == {"created": "v2.1.0", "previousV2Tags": 0, "passed": False,
                      "reason": "first-v2-release-not-v2.0.0"}
    assert guard.main(["--previous-v2-tags", "0", "--created", " v2.0.0\n"]) == 0
    assert json.loads(capsys.readouterr().out)["passed"] is True
