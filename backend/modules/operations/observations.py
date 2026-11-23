"""Admitting and recording capability observations (U8 plan Step 15; BR3.3, BR3.4, O1).

An observation is admitted only from its capability's registered producer, with a
registered outcome, a reason key registered for that capability and registered
limitation keys. Every value has the fixed key form, so no private text, credential,
email address, title or content can be carried (BR3.4). A refusal raises
`ObservationRefused` to the producer, whose own loop counts it; it never reaches a job,
an effect or a request.

Recording never fails its caller. Each producer has a buffer of up to 60 observations
(observability-design § 3.1): an observation the store cannot take stays buffered and
is written with the next one, in inserts of at most 60 rows. Only while the store
refuses and more than 60 remain is the oldest dropped and counted (Step 58(a)). A
chunk whose commit outcome is unknown is written once more at once, before any trim:
the store skips ids it holds, so a stored row is counted as dropped only when that
second write fails too. Every row written carries the producer's running dropped count
(`dropped_count`, L1-46), and 운영 shows the count as missing evidence. Before a
capability's first write in a process, one read of its newest stored revision seeds the
numbering, so a renewal at a held instant outranks the rows a process before wrote; a
failed seed read writes nothing and is read again on the next pass.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import itertools
from collections import deque
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from backend.u8_registry import CAPABILITY_BY_ID, ISOLATION_ITEMS, Capability

from .observation_store import MAX_INSERT, ObservationRow

# Reasons any producer may give: it could not observe, or its store refused it.
COMMON_REASONS = frozenset({
    "producer-failed", "store-unavailable", "store-denied", "store-busy",
    "evidence-unavailable",
})
# Limitations any capability may carry (the functional spec's examples).
COMMON_LIMITATIONS = frozenset({"pre-switch-recipient-bound"})
BUFFER = 60


class ObservationRefused(ValueError):
    """An observation outside the registry. The category is fixed; no value travels."""

    def __init__(self, category: str):
        super().__init__(category)
        self.category = category


def registered_reasons(capability: Capability) -> frozenset[str]:
    return frozenset(capability.degraded) | frozenset(capability.unavailable) | COMMON_REASONS


def registered_limitations(capability: Capability) -> frozenset[str]:
    extra = ISOLATION_ITEMS if capability.capability_id == "platform.isolation" else ()
    return frozenset(capability.degraded) | frozenset(extra) | COMMON_LIMITATIONS


@dataclass
class ProducerBuffer:
    """One producer's bounded memory while the store is down. `dropped` lasts as long as
    the producing process (L1-46)."""

    maximum: int = BUFFER

    def __post_init__(self) -> None:
        self.items: deque[ObservationRow] = deque()
        self.dropped = 0

    def add(self, row: ObservationRow) -> None:
        self.items.append(row)

    def trim(self) -> None:
        """Drop the oldest rows beyond the maximum, counting them: only after the store
        refused a write (Step 58(a))."""
        while len(self.items) > self.maximum:
            self.items.popleft()
            self.dropped += 1


class Observations:
    """The admission rule and every producer's buffer, over the observation store."""

    def __init__(self, store, *, registry: Mapping[str, Capability] = CAPABILITY_BY_ID,
                 buffer_size: int = BUFFER, log=None):
        self.store, self.registry = store, registry
        self.buffer_size = buffer_size
        self.buffers: dict[str, ProducerBuffer] = {}
        self._revisions: dict[str, int] = {}
        # Capabilities whose stored revision this process has read (`_seed`).
        self._seeded: set[str] = set()
        self.refused = 0
        self.log = log

    def make(
        self, capability: str, producer: str, outcome: str, *, observed_at: dt.datetime,
        reason: str | None = None, limitations: Iterable[str] = (), error_count: int = 0,
        total_count: int = 0,
    ) -> ObservationRow:
        """Build and admit one observation; refused unless every value is registered."""
        registered = self.registry.get(capability)
        if registered is None:
            raise ObservationRefused("capability-unregistered")
        if producer != registered.producer:
            raise ObservationRefused("producer-differs")
        limitations = tuple(limitations)
        if reason is not None and (
            not isinstance(reason, str) or reason not in registered_reasons(registered)
        ):
            raise ObservationRefused("reason-unregistered")
        if not all(
            isinstance(item, str) and item in registered_limitations(registered)
            for item in limitations
        ):
            raise ObservationRefused("limitation-unregistered")
        stamp = int(observed_at.timestamp() * 1000)
        revision = max(self._revisions.get(capability, 0) + 1, stamp)
        try:
            row = ObservationRow(
                capability=capability, producer=producer, outcome=outcome,
                observed_at=observed_at, revision=revision, reason_key=reason,
                limitation_keys=limitations, error_count=error_count, total_count=total_count,
            )
        except (TypeError, ValueError):
            raise ObservationRefused("value-form") from None
        self._revisions[capability] = revision
        return row

    def record(self, producer: str, rows: Iterable[ObservationRow]) -> dict:
        """Write what is buffered and the new rows together, oldest first, in inserts of
        at most `MAX_INSERT` rows, each written row carrying the producer's running
        dropped count (Step 58(a), NFR9.2, L1-46). A refused insert stops the writing;
        only then, while more than the buffer's maximum remain, are the oldest dropped
        and counted. The rows not written stay buffered unchanged, ids included: the
        store skips a row id it already holds, so a chunk whose commit outcome was unknown
        (`UnknownCommit`) is written again at once, once, before anything is trimmed;
        only when that second write fails too can a row the first one stored be trimmed
        and counted as dropped. Before a capability's first write in this process its
        buffered rows are numbered above the revision already stored (`_seed`); a failed
        seed read is handled as a refused insert, so no row is written unseeded. Never
        raises."""
        buffer = self.buffers.setdefault(producer, ProducerBuffer(self.buffer_size))
        for row in rows:
            buffer.add(row)
        written = 0
        try:
            self._seed(buffer)
            while buffer.items:
                chunk = list(itertools.islice(buffer.items, MAX_INSERT))
                written += self._insert_once_more_if_unknown([
                    dataclasses.replace(row, dropped_count=buffer.dropped) for row in chunk
                ])
                for _ in chunk:
                    buffer.items.popleft()
        except Exception as error:  # noqa: BLE001 - never reaches a domain outcome
            from backend.log_events import current

            (self.log or current()).exception(
                "operations", "observation.unrecorded", error, state=producer
            )
            buffer.trim()
        return {"written": written, "buffered": len(buffer.items), "dropped": buffer.dropped}

    def _seed(self, buffer: ProducerBuffer) -> None:
        """Number each capability's buffered rows above the newest revision already
        stored for it, before its first write in this process (decision 9222ed3d; the
        lead's option A of 2026-11-13). `make` numbers from `max(prev + 1, stamp)` and
        starts empty in each process, so without this a renewal written after a restart
        at the held instant of the row before it ties or loses `ObservationStore.latest`'s
        revision tie-break. One read, through the store's own owner, for the capabilities
        not yet seeded; a capability with no stored row seeds from 0. A failed read raises
        to `record`, which writes nothing and keeps the rows buffered; nothing is
        remembered, so the next pass reads again."""
        pending = sorted({row.capability for row in buffer.items} - self._seeded)
        if not pending:
            return
        stored = self.store.latest(pending)
        for capability in pending:
            newest = stored.get(capability)
            self._renumber(buffer, capability, 0 if newest is None else int(newest["revision"]))
            self._seeded.add(capability)

    def _renumber(self, buffer: ProducerBuffer, capability: str, floor: int) -> None:
        """Raise the capability's buffered revisions above `floor`, oldest first, keeping
        each row's id and its order; later `make` calls number on from the last."""
        items: deque[ObservationRow] = deque()
        for row in buffer.items:
            if row.capability == capability:
                floor = max(floor + 1, row.revision)
                if floor != row.revision:
                    row = dataclasses.replace(row, revision=floor)
            items.append(row)
        buffer.items = items
        self._revisions[capability] = max(self._revisions.get(capability, 0), floor)

    def _insert_once_more_if_unknown(self, chunk: list[ObservationRow]) -> int:
        """One insert; after an unknown commit outcome, the same rows once more. The
        store's insert is idempotent per row id, so the second write stores only what the
        first did not."""
        from backend.transactions import UnknownCommit

        try:
            return self.store.insert(chunk)
        except UnknownCommit:
            return self.store.insert(chunk)

    def missing(self) -> dict[str, int]:
        """Dropped observations per producer: the evidence 운영 shows as missing."""
        return {name: buffer.dropped for name, buffer in self.buffers.items() if buffer.dropped}
