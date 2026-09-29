"""Conservative clock-window arithmetic; unverified/native source absence is unavailable."""

import math
from dataclasses import dataclass


class ClockUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class ClockSample:
    utc_us: int
    continuous_ns: int
    uncertainty_us: int
    drift_ppm: float
    boot_id: str
    resume_id: str
    authenticated: bool

    def window(self, *, continuous_ns: int, boot_id: str, resume_id: str) -> tuple[int, int]:
        elapsed_ns = continuous_ns - self.continuous_ns
        if (
            not self.authenticated
            or boot_id != self.boot_id
            or resume_id != self.resume_id
            or not 0 <= elapsed_ns < 30_000_000_000
            or self.uncertainty_us < 0
            or not math.isfinite(self.drift_ppm)
            or self.drift_ppm < 0
        ):
            raise ClockUnavailable("current clock evidence unavailable")
        elapsed_us = elapsed_ns // 1000
        uncertainty = self.uncertainty_us + math.ceil(elapsed_us * self.drift_ppm / 1_000_000)
        if uncertainty > 1_000_000:
            raise ClockUnavailable("clock uncertainty exceeds policy")
        now = self.utc_us + elapsed_us
        return now - uncertainty, now + uncertainty


def unavailable_clock() -> tuple[int, int]:
    # The default never turns local wall time into a trusted source. Deployment must wire a
    # verified native NTS/boot/resume collector; its absence is exposed by /readyz.
    raise ClockUnavailable("native NTS clock provider is not provisioned")
