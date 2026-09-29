"""Generation-bound readonly circuit breaker with exactly one half-open probe."""

import threading
import time


class DependencyUnavailable(RuntimeError):
    pass


class ReadBreaker:
    def __init__(self, clock=time.monotonic):
        self._clock = clock
        self._lock = threading.Lock()
        self.generation = 0
        self.failures = 0
        self.open_until = None
        self.probing = False

    def acquire(self) -> tuple[int, bool]:
        with self._lock:
            probe = self.open_until is not None
            if probe:
                if self._clock() < self.open_until or self.probing:
                    raise DependencyUnavailable("dependency circuit open")
                self.probing = True
            return self.generation, probe

    def finish(self, ticket: tuple[int, bool], *, success: bool) -> None:
        generation, probe = ticket
        with self._lock:
            if generation != self.generation:
                return
            if success:
                self.failures = 0
                if probe:
                    self.open_until = None
                    self.probing = False
                    self.generation += 1
            else:
                self.failures += 1
                if probe or self.failures >= 3:
                    self.open_until = self._clock() + 10
                    self.probing = False
                    self.generation += 1

    def call(self, function, *args):
        ticket = self.acquire()
        try:
            value = function(*args)
        except BaseException:
            self.finish(ticket, success=False)
            raise
        self.finish(ticket, success=True)
        return value
