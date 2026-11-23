"""In-person service control for the tests of the person's decision of 2026-10-25 ("Add
an in-person stop command").

`FixedServices` is a run effect for `Operator`: once PlatformControl has bound the
receipt (in the composed realm's store), it reads the bound input and runs production's
fixed program (`fixed.service_stop` / `fixed.service_start`) under a test prefix, with
launchctl answered by a recorder and the test's injected clock, so a stop record is
written exactly as `docsuri-service-stop` writes it, citing the bound operation. It
records whether each receipt was already in the store and the stop record not yet
written when the program ran.
"""

from __future__ import annotations

import datetime as dt
import os
import subprocess
from collections.abc import Callable
from pathlib import Path

from docsuri_ops.arrangement.paths import ArrangementPaths
from docsuri_ops.platform_control.executor import STATUS_APPLIED, EffectOutcome
from docsuri_ops.u8_platform import fixed
from docsuri_ops.u8_platform.drivers import read_input
from docsuri_ops.u8_platform.u8_protocols import Operator, ReceiptReader


class RecordingStore:
    """U7's store, with each evidence record and binding counted, so a case can show a
    refusal came before anything was bound."""

    def __init__(self, store):
        self.store, self.bound = store, []

    def record_evidence(self, **fields):
        self.bound.append(("evidence", fields["target"]))
        return self.store.record_evidence(**fields)

    def begin_operation(self, **fields):
        self.bound.append(("operation", fields["operation"]))
        return self.store.begin_operation(**fields)

    def __getattr__(self, name):
        return getattr(self.store, name)


class FixedServices:
    def __init__(self, paths: ArrangementPaths, clock: Callable[[], dt.datetime]):
        self.paths, self.clock = paths, clock
        self.launchctl: list[list[str]] = []
        self.seen: list[dict] = []
        self.operator: Operator | None = None
        # launchd's state as the recorder answers it: every job loaded until booted out.
        self.unloaded: set[str] = set()
        # How far the injected clock ran ahead of the store's real clock when each
        # operation was bound, by operation: the store cannot follow an injected clock.
        self.offsets: dict[str, dt.timedelta] = {}

    def aligned(self):
        """The isolation check's receipt-time window with the store's clock read as the
        injected one: each receipt's bind time shifted by its own bind-time offset, so a
        test that advances the clock days keeps receipt and record on one clock, as they
        are in production. The window itself is unchanged."""
        from unittest import mock

        from docsuri_ops import isolation_check

        real = isolation_check._receipt_time_fits

        def fits(receipt: dict, record: dict) -> bool:
            offset = self.offsets.get(str(record.get("receiptId")), dt.timedelta(0))
            try:
                shifted = dt.datetime.fromisoformat(str(receipt["recordedAt"])) + offset
            except (KeyError, TypeError, ValueError):
                return real(receipt, record)
            return real({**receipt, "recordedAt": shifted.isoformat()}, record)

        return mock.patch.object(isolation_check, "_receipt_time_fits", fits)

    def context(self) -> fixed.FixedContext:
        def run(argv, **options):
            self.launchctl.append(list(argv))
            return subprocess.CompletedProcess(argv, self._answer(list(argv)), b"", b"")

        return fixed.FixedContext(paths=self.paths, run=run, clock=self.clock,
                                  owner_uid=os.getuid())

    def _answer(self, argv: list[str]) -> int:
        """launchctl's exit status: bootout of a job not loaded answers 3, bootstrap of a
        job already loaded answers 37, as launchd does."""
        if argv[1] == "bootout":
            label = argv[2].rsplit("/", 1)[-1]
            if label in self.unloaded:
                return 3
            self.unloaded.add(label)
        elif argv[1] == "bootstrap":
            label = Path(argv[3]).stem
            if label not in self.unloaded:
                return 37
            self.unloaded.discard(label)
        return 0

    def __call__(self, *, target_root: Path, operation_id: str, target_id: str, token: str,
                 input_hash: str, **options) -> EffectOutcome:
        inputs = read_input(target_root / target_id, token, input_hash)
        self.offsets[operation_id] = self.clock() - dt.datetime.now(dt.UTC)
        record = fixed.stop_record_path(self.paths, target_id)
        bound = self.operator is not None and bool(self.operator._read_named(operation_id))
        before = fixed.read_stop_record(record, owner_uid=os.getuid(), now=self.clock())
        self.seen.append({"operationId": operation_id, "bound": bound,
                          "recordCitedIt": bool(before and before["receiptId"] == operation_id)})
        handler = fixed.service_stop if inputs["action"] == "stop" else fixed.service_start
        handler(target_id, {"receiptId": operation_id}, self.context())
        return EffectOutcome(STATUS_APPLIED, [f"service/{target_id}/{inputs['action']}"])


def in_person(base: Operator, services: FixedServices) -> Operator:
    """The realm's in-person operator (its own store, actor and grants) whose service
    control runs production's fixed programs through `services`."""
    operator = Operator(base.profile, base.store, actor=base.actor,
                        authorities=base.authorities, facts=base.facts,
                        run_effect=services)
    services.operator = operator
    return operator


def held_as_root(operator: Operator, paths: ArrangementPaths, *,
                 owner_uid: int | None = None) -> Callable[[dict], bool]:
    """The isolation check's own question, built as `docsuri-isolation-check` builds it
    when it runs as root: `isolation_check.production_receipt_held` with the binding's
    owner named (the service account's UID; here the test's own, `owner_uid` overriding
    it), over the realm's store through the service account's `ReceiptReader`.

    The reading account is not the binding's owner: U7's `private_bytes` (which wants the
    reading process's own UID) is made to refuse the reader binding exactly as it does
    under root, so only a read naming the owner can open it."""
    from unittest import mock

    from docsuri_ops import isolation_check
    from docsuri_ops.u8_platform import platform_profile

    real = platform_profile.private_bytes

    def as_root(path, **options):
        if Path(path).name == platform_profile.READER_FILE:
            raise ValueError("private record must be a bounded owned regular file")
        return real(path, **options)

    with mock.patch.object(platform_profile, "private_bytes", as_root):
        return isolation_check.production_receipt_held(
            paths, owner_uid=os.getuid() if owner_uid is None else owner_uid,
            profile=operator.profile)


def receipt_held(operator: Operator) -> Callable[[dict], bool]:
    """The isolation check's question, asked of the realm's store: a succeeded
    `platform.service.control` on the record's label under the cited operation."""

    def held(record: dict) -> bool:
        try:
            receipt = operator._read_named(str(record["receiptId"]))
        except Exception:  # noqa: BLE001 - not in the store
            return False
        return (receipt.get("operation") == "platform.service.control"
                and str(receipt.get("targetId")) == record["label"]
                and ReceiptReader.outcome(receipt) == "succeeded")

    return held
