"""A participant's retention date reaches AccountAccess as an aware time (U8, BR2.5).

`CompleteLifecycleWorker.run_once` hands each participant's `retainedUntil` to
AccountAccess's `acknowledge`, which stores only an aware datetime. `retention_date` parses an
ISO 8601 string with its offset and refuses anything else as a pending reason, so a pass never
crashes on what a participant reported (re-check note of U5's reviewer). The worker path
itself is `integration/test_lifecycle_manifest.py`'s eighth test.
"""

from __future__ import annotations

import datetime as dt

import pytest

from backend.control_worker import PendingLifecycleEvidence
from backend.u8_workers import INVALID_RETENTION_DATE, retention_date

MOMENT = dt.datetime(2026, 11, 21, 3, 4, 5, 678000, tzinfo=dt.UTC)


@pytest.mark.parametrize("value", [
    MOMENT,
    MOMENT.isoformat(),
    MOMENT.isoformat().replace("+00:00", "Z"),
    MOMENT.astimezone(dt.timezone(dt.timedelta(hours=9))).isoformat(),
])
def test_an_aware_time_or_an_iso_string_with_its_offset_is_the_same_instant(value):
    parsed = retention_date(value)
    assert parsed.tzinfo is not None and parsed == MOMENT


@pytest.mark.parametrize("value", [
    MOMENT.replace(tzinfo=None),
    MOMENT.replace(tzinfo=None).isoformat(),
    "2026-11-21",
    "not-a-date",
    "",
    1795143845,
    None,
])
def test_a_naive_malformed_or_foreign_value_is_refused_as_a_pending_reason(value):
    with pytest.raises(PendingLifecycleEvidence) as refused:
        retention_date(value)
    assert str(refused.value) == INVALID_RETENTION_DATE
