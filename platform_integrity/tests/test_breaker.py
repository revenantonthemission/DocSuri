import pytest

from docsuri_platform_integrity.adapters.breaker import DependencyUnavailable, ReadBreaker


def test_late_success_cannot_close_new_generation_and_one_probe_only():
    time = [0]
    breaker = ReadBreaker(lambda: time[0])
    late = breaker.acquire()
    for _ in range(3):
        breaker.finish(breaker.acquire(), success=False)
    breaker.finish(late, success=True)
    with pytest.raises(DependencyUnavailable):
        breaker.acquire()
    time[0] = 10
    probe = breaker.acquire()
    with pytest.raises(DependencyUnavailable):
        breaker.acquire()
    breaker.finish(probe, success=True)
    assert breaker.acquire()[1] is False
