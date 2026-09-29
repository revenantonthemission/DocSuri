import threading
import time
from collections import OrderedDict

from ..adapters.breaker import DependencyUnavailable, ReadBreaker
from ..contracts.codec import canonical
from ..contracts.models import (
    CompatibilityManifest,
    CompatibilityResult,
    GateEvaluation,
    GateVerdict,
    SubjectSnapshot,
)
from ..domain.compatibility import CompatibilityPolicy, evaluate_compatibility
from ..domain.gate import evaluate


class EvidenceService:
    def __init__(
        self, reader, authority, clock,
        policies: dict[str, tuple[SubjectSnapshot, tuple[str, ...]]],
        *, current=None, compatibility=None,
    ):
        self.reader = reader
        self.authority = authority
        self.clock = clock
        self.policies = dict(policies)
        self.current = current
        # Owner port returning (manifest, policy, observed) for a release. Not an HTTP parameter.
        # Stored under a distinct name so it cannot shadow the compatibility() method.
        self.compatibility_source = compatibility
        self._breaker = ReadBreaker()
        # Retain the worker admission until synchronous I/O really ends, even if HTTP times out.
        self._workers = threading.BoundedSemaphore(8)

    def _observe(self, snapshot, subject, deadline):
        def within_budget():
            if time.monotonic() >= deadline:
                raise TimeoutError("evidence observation deadline")

        within_budget()
        heads, evidence = self.reader.snapshot(subject)
        within_budget()
        if len(heads) > 100 or len(evidence) > 100:
            raise ValueError("evidence snapshot limit")
        current = self.current.inspect(
            snapshot, evidence, deadline=deadline
        ) if self.current is not None else None
        within_budget()
        if current is not None:
            after_heads, after_records = self.reader.snapshot(subject)
            within_budget()
            if len(after_heads) > 100 or len(after_records) > 100:
                raise ValueError("evidence snapshot limit")

            def fingerprint(values):
                return sorted(canonical(value.model_dump(mode="json")) for value in values)

            if (
                fingerprint(heads) != fingerprint(after_heads)
                or fingerprint(evidence) != fingerprint(after_records)
            ):
                return None
            fresh = self.current.inspect(snapshot, evidence, deadline=deadline)
            within_budget()
            if (
                fresh is None or fresh.subject != current.subject
                or fingerprint(fresh.checks) != fingerprint(current.checks)
                or fingerprint(fresh.exceptions) != fingerprint(current.exceptions)
            ):
                return None
        return heads, evidence, current

    def read(self, fingerprint: str | None, subject: str):
        if not self._workers.acquire(blocking=False):
            raise OSError("evidence workers busy")
        try:
            deadline = time.monotonic() + 2.5
            if not self.authority.permits(fingerprint, subject):
                raise PermissionError("not found")
            snapshot, required = self.policies[subject]
            observed = self._breaker.call(self._observe, snapshot, subject, deadline)
            lower, upper = self.clock()
            # Re-check caller grant after I/O; a revoked caller must not receive a result.
            if not self.authority.permits(fingerprint, subject):
                raise PermissionError("not found")
            if time.monotonic() >= deadline:
                raise TimeoutError("evidence observation deadline")
            if observed is None:
                return GateEvaluation(
                    verdict=GateVerdict.INCOMPLETE, reasons=("evidence_observation_changed",),
                    evidence_ids=(),
                )
            heads, evidence, current = observed
            return evaluate(
                snapshot, required, heads, evidence, lower=lower, upper=upper,
                trusted=True, current=current,
            )
        finally:
            self._workers.release()


    def readiness(self, fingerprint: str | None = None, subject: str | None = None):
        """Three separately reported depths, so a probe can distinguish them.

        shallow: the clock and the reader answer at all.
        deep:    a real bounded observation of a known subject completed.
        subject: whether this caller may read that subject. Absent subject or caller is False,
                 never unknown, so a caller cannot infer subject existence from readiness.
        """
        shallow, deep, eligible = False, False, False
        reasons = []
        try:
            lower, upper = self.clock()
            shallow = type(lower) is int and type(upper) is int and 0 <= lower <= upper < 2**64
        except Exception:
            reasons.append("clock_unavailable")
        if not shallow:
            reasons.append("shallow_not_ready")
        deep = False
        if shallow and self.policies:
            subject_key = subject if subject in self.policies else next(iter(self.policies))
            if not self._workers.acquire(blocking=False):
                reasons.append("workers_busy")
            else:
                try:
                    deadline = time.monotonic() + 2.5
                    snapshot, required = self.policies[subject_key]
                    observed = self._breaker.call(self._observe, snapshot, subject_key, deadline)
                    deep = observed is not None
                    if not deep:
                        reasons.append("evidence_observation_changed")
                    if fingerprint is not None and subject is not None:
                        eligible = self.authority.permits(fingerprint, subject)
                except Exception:
                    reasons.append("deep_observation_unavailable")
                finally:
                    self._workers.release()
        elif shallow:
            reasons.append("no_policies")
        if subject is not None and not eligible:
            reasons.append("subject_not_permitted")
        return {
            "shallow": shallow,
            "deep": deep,
            "subjectEligible": eligible,
            "reasons": sorted(set(reasons)),
        }

    def compatibility(self, fingerprint: str | None, release: str) -> CompatibilityResult:
        if self.compatibility_source is None:
            raise DependencyUnavailable("compatibility source not provisioned")
        if not self._workers.acquire(blocking=False):
            raise OSError("evidence workers busy")
        try:
            deadline = time.monotonic() + 2.5
            if time.monotonic() >= deadline:
                raise TimeoutError("compatibility deadline")
            manifest, policy, observed = self.compatibility_source(release)
            if not isinstance(manifest, CompatibilityManifest) or not isinstance(
                policy, CompatibilityPolicy
            ):
                raise ValueError("invalid compatibility source")
            if not self.authority.permits(fingerprint, release):
                # A release the caller may not read is indistinguishable from one that is absent.
                raise PermissionError("not found")
            if time.monotonic() >= deadline:
                raise TimeoutError("compatibility deadline")
            verdict, reasons = evaluate_compatibility(manifest, policy, observed)
            # Compatibility is an observation of one exact release; it never widens any grant.
            return CompatibilityResult(
                release=release, verdict=verdict, reasons=tuple(reasons)
            )
        finally:
            self._workers.release()


class ImmutableByteCache:
    """Cache immutable bytes only. Current grant/heads/verdicts are never valid cache entries."""

    def __init__(self, limit=64 * 1024**2):
        self.limit = limit
        self.size = 0
        self._items = OrderedDict()
        self._lock = threading.Lock()

    def put(self, key: str, value: bytes):
        if not isinstance(value, bytes) or not key.startswith("sha256:"):
            raise ValueError("only digest-addressed immutable bytes can be cached")
        weight = len(value) + len(key) * 4 + 256
        with self._lock:
            old = self._items.pop(key, None)
            if old:
                self.size -= old[1]
            if weight > self.limit:
                return
            while self.size + weight > self.limit:
                _, (_, removed_weight) = self._items.popitem(last=False)
                self.size -= removed_weight
            self._items[key] = value, weight
            self.size += weight

    def get(self, key):
        with self._lock:
            item = self._items.get(key)
            if item is None:
                return None
            self._items.move_to_end(key)
            return item[0]
