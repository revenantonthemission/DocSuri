"""The composed realm's per-role page-read limits on the fake Notion (J12's late export).

U6 served its export lane in one process, so one fake counted every read of the stuck
page: the preview's, the approval's and the worker's pre-write read, which then met 503
and left the export accepted. The composed realm runs host and workers apart, each with
its own fake from the same scenario, so the workers' count started again at zero and the
export went through (realm B's verification run of 2026-10-23: all three exports
succeeded, the stuck one at the advanced instant). `u8_host.role_page_reads` gives each
role its limit from the scenario's `u8RolePageReads`, through U6's own
`limit_page_reads`.
"""

from __future__ import annotations

import json
import os
import secrets
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

RUN_ID = "docsuri-u8-test-role-page-reads"


def scenario_file(root: Path, value: dict) -> None:
    descriptor = os.open(root / "fake-notion.json", os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
                         0o600)
    with os.fdopen(descriptor, "w") as stream:
        json.dump(value, stream)


@pytest.fixture
def fixtures_module():
    from scripts import verify_docsuri_u8

    scripts = str(Path(verify_docsuri_u8.ROOT) / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    import u8_fixtures

    return u8_fixtures


def synthetic_token() -> str:
    """The fake Notion's token, generated per run (L1-36), as `u8_fixtures` makes it."""
    return "u8-synthetic-" + secrets.token_hex(20)


def busy(fake, page_id: str) -> bool:
    return fake._counted_busy(page_id.replace("-", ""), page_request=True)


def test_the_workers_fake_refuses_the_stuck_page_from_its_first_read(fixtures_module, tmp_path):
    from backend.modules.export.fake_notion import FakeNotion
    from backend.u8_host import role_page_reads

    value = fixtures_module.notion_scenario(RUN_ID, synthetic_token())
    scenario_file(tmp_path, value)
    stuck = next(page["id"] for page in value["pages"]
                 if page["title"] == fixtures_module.NOTION_STUCK)
    profile = SimpleNamespace(root=tmp_path, run_id=RUN_ID)

    host = FakeNotion.from_scenario(value, run_id=RUN_ID)
    assert role_page_reads(host, profile, "host") == {}
    # The host's fake: the preview's and the approval's reads answer, a third would not.
    assert [busy(host, stuck) for _ in range(3)] == [False, False, True]

    workers = FakeNotion.from_scenario(value, run_id=RUN_ID)
    assert role_page_reads(workers, profile, "workers") == {stuck: 0}
    # The workers' fake: the pre-write read is its first, and it meets 503.
    assert busy(workers, stuck) is True


def test_no_scenario_or_no_role_entry_changes_nothing(fixtures_module, tmp_path):
    from backend.modules.export.fake_notion import FakeNotion
    from backend.u8_host import role_page_reads

    profile = SimpleNamespace(root=tmp_path, run_id=RUN_ID)
    assert role_page_reads(FakeNotion(), profile, "workers") == {}
    value = fixtures_module.notion_scenario(RUN_ID, synthetic_token())
    scenario_file(tmp_path, value)
    assert role_page_reads(FakeNotion.from_scenario(value, run_id=RUN_ID), profile,
                           "scheduler") == {}


@pytest.mark.parametrize("limit", [-1, "0", True])
def test_a_role_limit_that_is_not_a_count_is_refused(fixtures_module, tmp_path, limit):
    from backend.modules.export.fake_notion import FakeNotion
    from backend.u8_host import role_page_reads

    value = {**fixtures_module.notion_scenario(RUN_ID, synthetic_token()),
             "u8RolePageReads": {"workers": {"0" * 32: limit}}}
    scenario_file(tmp_path, value)
    with pytest.raises(ValueError, match="must be a count"):
        role_page_reads(FakeNotion(), SimpleNamespace(root=tmp_path, run_id=RUN_ID), "workers")
