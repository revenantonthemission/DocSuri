"""The composed realm's one clock (`u8_host.fixture_clock`, decision "One clock").

The delegated instant holds the clock still while it stands ahead of now, and once real
time passes it the clock follows now: a clock left behind now made every issue time count
from the past, so a sign-in's second-factor continuation was born expired (the
intermittent 403 the browser journeys met).
"""

from __future__ import annotations

import datetime as dt
import json
import os
from types import SimpleNamespace

import pytest

from backend.u8_host import CLOCK_AHEAD, CLOCK_FILE, fixture_clock

RUN_ID = "docsuri-u8-0123456789abcdef"


def realm(tmp_path):
    folder = tmp_path / "run"
    folder.mkdir(mode=0o700)
    return SimpleNamespace(is_production=False, root=folder, run_id=RUN_ID)


def delegate(profile, instant: dt.datetime, run_id: str = RUN_ID) -> None:
    path = profile.root / CLOCK_FILE
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        json.dump({"runId": run_id, "instant": instant.isoformat()}, stream)


def test_without_a_delegated_instant_the_clock_is_now(tmp_path):
    before = dt.datetime.now(dt.UTC)
    assert before <= fixture_clock(realm(tmp_path))() <= dt.datetime.now(dt.UTC)


def test_an_instant_ahead_holds_the_clock_still(tmp_path):
    profile = realm(tmp_path)
    ahead = dt.datetime.now(dt.UTC) + dt.timedelta(hours=3)
    delegate(profile, ahead)
    clock = fixture_clock(profile)
    assert clock() == ahead == clock()


@pytest.mark.parametrize("behind", [dt.timedelta(minutes=10), dt.timedelta(hours=5)])
def test_an_instant_real_time_has_passed_is_overtaken_by_now(tmp_path, behind):
    profile = realm(tmp_path)
    delegate(profile, dt.datetime.now(dt.UTC) - behind)
    before = dt.datetime.now(dt.UTC)
    # Never the past instant, and never a refusal however long ago it was left.
    assert before <= fixture_clock(profile)() <= dt.datetime.now(dt.UTC)


def test_another_runs_instant_or_one_beyond_the_allocation_is_refused(tmp_path):
    profile = realm(tmp_path)
    delegate(profile, dt.datetime.now(dt.UTC), run_id="docsuri-u8-ffffffffffffffff")
    with pytest.raises(ValueError):
        fixture_clock(profile)()
    delegate(profile, dt.datetime.now(dt.UTC) + CLOCK_AHEAD + dt.timedelta(hours=1))
    with pytest.raises(ValueError):
        fixture_clock(profile)()


def test_the_production_profile_reads_real_time_only(tmp_path):
    profile = realm(tmp_path)
    delegate(profile, dt.datetime.now(dt.UTC) + dt.timedelta(hours=3))
    production = SimpleNamespace(**{**vars(profile), "is_production": True})
    assert fixture_clock(production)() < dt.datetime.now(dt.UTC) + dt.timedelta(minutes=1)
