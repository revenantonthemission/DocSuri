"""U6:NFR4.10/check-schedule: `next_check_time` reads the policy's rows exactly (L1-5).

Pure: the walk derives every expected point from the policy fields, so a change to the
schedule in `u6_policy` or `store_support` has to change these lists with it.
"""

import datetime as dt

import pytest

from backend.modules.export.store_support import next_check_time
from backend.u6_policy import SYNTHETIC_EXPORT, ExportPolicy

BASE = dt.datetime(2026, 10, 28, 12, 0, tzinfo=dt.UTC)
SCHEDULE = [
    180, 600, 1800, 5400, 9000, 12600, 16200, 19800, 30600, 41400, 52200, 63000, 73800, 84600
]


def at(seconds: float) -> dt.datetime:
    return BASE + dt.timedelta(seconds=seconds)


def walk(policy: ExportPolicy) -> list[int]:
    points, now = [], at(0)
    while True:
        point = next_check_time(BASE, now, policy)
        if point is None:
            return points
        points.append(int((point - BASE).total_seconds()))
        now = point


def test_the_synthetic_walk_yields_the_fourteen_points_then_none():
    assert walk(SYNTHETIC_EXPORT) == SCHEDULE
    assert next_check_time(BASE, at(84600), SYNTHETIC_EXPORT) is None
    pairs = list(zip(SCHEDULE, SCHEDULE[1:], strict=False))
    hourly_until = SYNTHETIC_EXPORT.check_hourly_until_seconds
    assert all(
        later - earlier == 3600
        for earlier, later in pairs
        if 1800 <= earlier and later <= hourly_until
    )
    assert all(later - earlier == 10800 for earlier, later in pairs if later > hourly_until)


@pytest.mark.parametrize(
    ("now", "expected"),
    [(700, 1800), (1800, 5400), (19800, 30600), (84600, None), (-30, 180)],
)
def test_a_late_scan_skips_to_the_first_point_strictly_after_now(now, expected):
    point = next_check_time(BASE, at(now), SYNTHETIC_EXPORT)
    assert (None if point is None else int((point - BASE).total_seconds())) == expected


def test_a_small_policy_walks_its_own_points():
    policy = ExportPolicy(
        check_offsets_seconds=(60, 120),
        check_hourly_seconds=300,
        check_hourly_until_seconds=900,
        check_late_interval_seconds=600,
        check_total_seconds=2400,
    )
    assert walk(policy) == [60, 120, 420, 720, 1320, 1920]
    edge = ExportPolicy(
        check_offsets_seconds=(60, 120),
        check_hourly_seconds=300,
        check_hourly_until_seconds=900,
        check_late_interval_seconds=600,
        check_total_seconds=1920,
    )
    assert walk(edge) == [60, 120, 420, 720, 1320, 1920]
