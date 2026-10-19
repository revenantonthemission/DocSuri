"""Active RFC3339 and local model boundaries, explicitly NOT real-store TTL proof."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from summarization.domain import job_protocol
from summarization.domain.job_protocol import JobProtocolError, JobTask, instant, rfc3339_instant
from tests.test_u1_job_model import capture, translation_payload


@pytest.mark.parametrize("text", [
    "2024-02-29T23:59:59Z", "2026-10-06T09:45:00+09:00",
    "2026-10-05t00:00:00.123456789z", "2026-10-05T01:00:00-00:00",
    "2016-12-31T23:59:60Z", "2017-01-01T08:59:60+09:00",
])
def test_valid_utc_offset_fraction_and_known_leap_content_is_preserved(text) -> None:
    assert rfc3339_instant(text).utcoffset() is not None
    payload = translation_payload()
    payload["translation"]["docModel"]["meta"]["provenance"]["generatedAt"] = text
    result = capture(JobTask.TRANSLATE, payload)
    assert result.content()["translation"]["docModel"]["meta"]["provenance"]["generatedAt"] == text


@pytest.mark.parametrize("text", [
    "2026-02-29T00:00:00Z", "2026-02-30T00:00:00Z", "2026-13-01T00:00:00Z",
    "0000-01-01T00:00:00Z", "2026-10-06T24:00:00Z", "2026-10-06T00:60:00Z",
    "2026-10-06T00:00:60Z", "2026-10-06T00:00:00+24:00",
    "2026-10-06T00:00:00+09:60", "2026-10-06T00:00:00", "2026-10-06",
    "2026-10-06 00:00:00Z", "2026-10-06T00:00:00Z\n", 1791244800, None,
])
def test_calendar_time_offset_and_timezone_omission_are_rejected_before_capture(text) -> None:
    with pytest.raises(JobProtocolError, match="timestamp_invalid"):
        rfc3339_instant(text)
    payload = translation_payload()
    payload["translation"]["docModel"]["meta"]["provenance"]["generatedAt"] = text
    with pytest.raises(JobProtocolError):
        capture(JobTask.TRANSLATE, payload)


@pytest.mark.parametrize("checker", [None, lambda _value: True,
                                    lambda _value: datetime(2026, 1, 1, tzinfo=UTC)])
def test_missing_or_annotation_only_checker_fails_evidence(monkeypatch, checker) -> None:
    result = capture().initialize_expiry(200)
    monkeypatch.setattr(job_protocol, "TIMESTAMP_CHECKER", checker)
    with pytest.raises(JobProtocolError, match="checker_unavailable"):
        job_protocol.require_timestamp_checker()
    with pytest.raises(JobProtocolError, match="checker_unavailable"):
        result.envelope(101)


def test_checker_cannot_return_an_unaware_result_for_an_actual_value(monkeypatch) -> None:
    original = job_protocol.TIMESTAMP_CHECKER
    monkeypatch.setattr(job_protocol, "TIMESTAMP_CHECKER",
                        lambda value: datetime(2026, 1, 1) if value == "wrong" else original(value))
    with pytest.raises(JobProtocolError, match="timestamp_invalid"):
        rfc3339_instant("wrong")


@pytest.mark.parametrize("value", [True, -1, float("inf"), float("nan"), 10**20])
def test_preparation_and_expiry_epoch_values_must_be_calendar_representable(value) -> None:
    with pytest.raises(JobProtocolError, match="instant_invalid"):
        instant(value)
    with pytest.raises(JobProtocolError):
        replace(capture(), prepared_at=value)
    with pytest.raises(JobProtocolError):
        capture().initialize_expiry(value)


def test_local_before_at_after_expiry_and_duplicate_publication_never_renew() -> None:
    result = capture().initialize_expiry(200)
    envelope = result.envelope(199.999)
    assert rfc3339_instant(envelope["preparedResult"]["preparedAt"]).timestamp() == 100
    assert rfc3339_instant(envelope["preparedResult"]["expiresAt"]).timestamp() == 200
    assert result.initialize_expiry(200) == result
    for now in (200, 200.001):
        with pytest.raises(JobProtocolError, match="expired"):
            result.envelope(now)
    with pytest.raises(JobProtocolError, match="immutable"):
        result.initialize_expiry(300)


def test_expiry_cannot_precede_preparation_and_missing_expiry_is_not_ready() -> None:
    result = capture()
    with pytest.raises(JobProtocolError, match="not_ready"):
        result.envelope(101)
    for expires_at in (99, 100):
        with pytest.raises(JobProtocolError, match="expiry_invalid"):
            result.initialize_expiry(expires_at)


def test_instants_are_compared_as_instants_not_lexicographic_offsets() -> None:
    assert rfc3339_instant("2026-10-06T09:00:00+09:00") == rfc3339_instant("2026-10-06T00:00:00Z")
