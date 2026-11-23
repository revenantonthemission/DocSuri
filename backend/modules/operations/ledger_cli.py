"""`docsuri-ledger`: the ledger component's fixed command (U8 plan Step 13; BR6.10, D6).

It runs as the service account, so the operator tool (in person) and the standing
authority (unattended) write the ledger through the same component, under the same lock,
while v2 is stopped (BR6.10). Its one argument is a word from a closed set, which it
checks again itself; any further input is bounded JSON on standard input, validated
before use. It refuses to run when the environment holds `PYTHON*`, `DYLD_*` or `LD_*`
variables, and writes one JSON result to standard output (D6). `copy` is the one word
whose standard output is a byte stream: its JSON result goes to standard error.

- `append` takes `{kind, record, expectRevision, receipts}`, or one step's appends as a
  batch, `{appends: [...], expectHead}`, checked as one under one lock (a refusal writes
  none) and written with signals held back; only a disk error between its writes can
  leave a prefix, which the next open adopts (`Ledger.append_all`). A
  receipt-bearing kind is admitted only when every receipt it cites is confirmed by
  PlatformControl's `readReceipt` (through `ReceiptReader`) or is already in the ledger;
  a MaintainerApproval only with a confirmed `platform.decision.record` receipt that
  succeeded under your in-person grant, whose input hash binds this approval's step,
  subject and decision, and that no other approval cites (BR9.14).
- `copy` streams a consistent copy up to the head and reports its digest.
- `verify` re-reads the whole chain.
- `read` answers a bounded query, `{kind, key?, limit?}`.
- `repair`, in person, replaces a damaged ledger from a verified copy streamed in. The
  damaged files are kept aside in the evidence folder and the repair is recorded; a
  ledger that still verifies is never replaced. A damaged ledger cannot hold its own
  incident, so the repair records it (your decision of 2026-10-22, BR6.10): an
  `operations.ledger` incident opened at the time the damage was first found, read from
  the marker the ledger component keeps beside the ledger (`damage.json`), or the
  repair's own finding when no process found it first. The marker then moves aside with
  the damaged files. A repair interrupted after the replacement finishes on its next
  run, and the incident's identity comes from the finding, so it is never recorded
  twice; with no damage and no marker left, a repair records nothing.

The receipt reader is PlatformControl's (`u8_protocols.ReceiptReader`, Step 27), bound
through the profile's reader file; while none is provisioned `UnboundReceiptReader`
confirms nothing, so a receipt-bearing record is refused.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import secrets
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Protocol
from uuid import NAMESPACE_URL, uuid5

from .errors import LedgerDamaged, OperationsError
from .ledger import (
    DAMAGE_MARKER,
    FOLDER_MODE,
    REPAIRED,
    Ledger,
    LedgerStore,
    canonical,
    entry_digest,
    read_damage,
    record_damage,
)
from .ledger_records import (
    RECEIPT_BEARING,
    RECOVERY_KINDS,
    RecordRefused,
    schema_of,
)

WORDS = ("append", "copy", "verify", "read", "repair")
# The standing authority's unattended words (security-design § 5.2); repair is in person.
UNATTENDED_WORDS = ("append", "copy", "verify", "read")
REFUSED_ENVIRONMENT = ("PYTHON", "DYLD_", "LD_")
MAX_INPUT = 64 * 1024
# `append` takes one step's appends as one batch (review finding, Major, R14): a step such
# as a run's misfits may hold many records, so its input has its own, larger bound.
MAX_APPEND_INPUT = 16 * 1024 * 1024
MAX_BATCH = 4096
MAX_COPY = 512 * 1024 * 1024
MAX_READ = 100
DECISION_OPERATION = "platform.decision.record"
PRODUCTION_PROFILE = Path("/Library/DocSuri/profile")


class ReceiptUnavailable(RuntimeError):
    """PlatformControl could not confirm a receipt; the record is refused."""


class ReceiptReader(Protocol):
    def read(self, operation_id: str) -> Mapping:
        """The receipt of one operation: at least `receiptId`, `operationId`, `targetId`,
        `inputHash`, `outcome` (C10 OperatorReceipt) and the bound `operation`."""


class UnboundReceiptReader:
    """No PlatformControl profile is bound yet: nothing is confirmed."""

    def read(self, operation_id: str) -> Mapping:
        raise ReceiptUnavailable("no receipt reader is bound")


class Refusal(Exception):
    def __init__(self, reason: str, *, status: int = 1, **facts):
        super().__init__(reason)
        self.reason, self.status, self.facts = reason, status, facts


def refused_environment(environ: Mapping[str, str]) -> bool:
    return any(name.startswith(REFUSED_ENVIRONMENT) for name in environ)


def _bounded_json(stream: BinaryIO, maximum: int = MAX_INPUT) -> dict:
    raw = stream.read(maximum + 1)
    if len(raw) > maximum:
        raise Refusal("input-too-large", status=2)
    try:
        value = json.loads(raw or b"{}")
    except ValueError:
        raise Refusal("input-not-json", status=2) from None
    if not isinstance(value, dict):
        raise Refusal("input-not-an-object", status=2)
    return value


def _utc_now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


@dataclass
class LedgerCommand:
    """The command's work, given the ledger folder, the evidence folder kept for a
    repair, the clock, PlatformControl's receipt reader and the profile's environment
    (`rehearsal` or `live`), which the repair's incident is recorded under."""

    folder: Path
    evidence: Path
    receipts: ReceiptReader
    clock: Callable[[], dt.datetime] = _utc_now
    environment: str | None = None
    # Your in-person grants (the operator's routine and destructive grants): a decision
    # receipt is confirmed only when it was bound under one of them (your decision of
    # 2026-10-26, "Bind each login to its actor"). None confirms no decision.
    decision_authorities: frozenset[str] | None = None

    def run(self, word: str, stdin: BinaryIO, stdout: BinaryIO, stderr: BinaryIO) -> int:
        if word not in WORDS:
            return _emit(stdout, {"ok": False, "reason": "word-refused"}, 2)
        try:
            if word == "copy":
                result = self.copy(stdout)
                return _emit(stderr, result, 0)
            if word == "repair":
                result = self.repair(stdin)
            else:
                document = _bounded_json(stdin, MAX_APPEND_INPUT if word == "append"
                                         else MAX_INPUT)
                result = getattr(self, word)(document)
            return _emit(stdout, result, 0)
        except Refusal as refusal:
            target = stderr if word == "copy" else stdout
            return _emit(target, {"ok": False, "reason": refusal.reason, **refusal.facts},
                         refusal.status)
        except LedgerDamaged as damage:
            target = stderr if word == "copy" else stdout
            return _emit(target, {"ok": False, "reason": "ledger-damaged",
                                  "category": damage.category}, 1)

    # --- words -----------------------------------------------------------------------

    def _open(self) -> Ledger:
        return Ledger.open(self.folder, clock=self.clock)

    def append(self, document: dict) -> dict:
        """One append (`{kind, record, expectRevision, receipts}`), or one step's appends
        as a batch (`{appends: [...]}`, each of that form, in order), refused
        `stale-revision` when an entity moved, and, when the caller names `expectHead`
        (`{count, head}`, the chain's head its reads saw), refused `stale-head` when
        anything was appended since. A batch is one ledger step, under one lock
        (`append_all`): every append is checked before any is written, so a guard that
        spans records (the live exclusion, a run already active, a held predecessor) is
        checked and acted on as one step for every process, and a refusal writes
        nothing; the writes then run with SIGINT, SIGTERM and SIGHUP held back, so no
        signal leaves a step half applied (review findings, Major, R12 and R14; Minor,
        R18). A disk error between two writes is the one way a prefix can remain, and
        the next open adopts it as the chain's crash rule says."""
        if not set(document) <= {"kind", "record", "expectRevision", "receipts",
                                 "expectHead", "appends"}:
            raise Refusal("input-field-refused", status=2)
        expected_head = document.get("expectHead")
        if expected_head is not None and not (
                isinstance(expected_head, dict) and set(expected_head) == {"count", "head"}
                and type(expected_head["count"]) is int and expected_head["count"] >= 0
                and isinstance(expected_head["head"], str)
                and re.fullmatch(r"[0-9a-f]{64}", expected_head["head"])):
            raise Refusal("input-field-refused", status=2)
        batch = "appends" in document
        if batch:
            items = document["appends"]
            if set(document) - {"appends", "expectHead"} or not isinstance(items, list) or not (
                    1 <= len(items) <= MAX_BATCH):
                raise Refusal("input-field-refused", status=2)
        else:
            items = [{name: document[name] for name in document if name != "expectHead"}]
        parsed = [self._parsed(item) for item in items]
        ledger = self._open()
        try:
            prepared, confirmed, cited = [], {}, set()
            for kind, record, expected, receipts, schema in parsed:
                facts = self._confirm(ledger, schema, record, receipts, confirmed) if (
                    kind in RECEIPT_BEARING
                ) else []
                if kind == "maintainer-approval":
                    self._require_decision(ledger, record, [*confirmed.values(), *facts],
                                           cited)
                    cited.add(record.get("operatorReceiptRef"))
                confirmed.update((item["receiptId"], item) for item in facts)
                prepared.append((kind, record, expected, facts))

            def step(view):
                if expected_head is not None:
                    current = view.head()
                    if (current.count, current.head) != (expected_head["count"],
                                                         expected_head["head"]):
                        raise Refusal("stale-head", current={"count": current.count,
                                                             "head": current.head})
                return view.append_all(prepared)

            try:
                appended = ledger.atomic(step)
            except RecordRefused as refusal:
                raise Refusal("record-refused", category=refusal.category) from None
            except OperationsError as error:
                raise Refusal("stale-revision", current=error.current) from None
            except ValueError:
                raise Refusal("record-refused", category="entry-form") from None
            head = {"count": ledger.store.head.count, "head": ledger.store.head.head}
            if batch:
                # A bounded answer whatever the batch's size (review finding, Major, R15):
                # its count and its first and last appends, never one item per append, so
                # a client reading the answer's last line always reads all of it.
                return {"ok": True, "head": head, "count": len(appended),
                        "first": {"seq": appended[0].seq, "revision": appended[0].revision},
                        "last": {"seq": appended[-1].seq, "revision": appended[-1].revision}}
            return {"ok": True, "seq": appended[0].seq, "revision": appended[0].revision,
                    "head": head}
        finally:
            ledger.close()

    @staticmethod
    def _parsed(item) -> tuple:
        """One append's fields checked: a kind the command may append, an integer
        expected revision, at most 32 receipts, and a record its schema accepts."""
        if not isinstance(item, dict) or not set(item) <= {"kind", "record", "expectRevision",
                                                           "receipts"}:
            raise Refusal("input-field-refused", status=2)
        kind, record = item.get("kind"), item.get("record")
        receipts = item.get("receipts", [])
        expected = item.get("expectRevision")
        if not isinstance(kind, str) or kind in RECOVERY_KINDS or kind == "receipt-facts":
            raise Refusal("kind-refused", status=2)
        if type(expected) is not int or not isinstance(receipts, list) or len(receipts) > 32:
            raise Refusal("input-field-refused", status=2)
        try:
            schema = schema_of(kind)
            schema.validate(record)
        except RecordRefused as refusal:
            raise Refusal("record-refused", category=refusal.category) from None
        return kind, record, expected, receipts, schema

    def _confirm(self, ledger: Ledger, schema, record: dict, receipts: list,
                 earlier: Mapping[str, dict] | None = None) -> list[dict]:
        """Every cited receipt not yet in the ledger, nor confirmed for an earlier append
        of the same batch, is confirmed by PlatformControl."""
        given = {item.get("receiptId"): item for item in receipts if isinstance(item, dict)}
        confirmed = []
        for ref in schema.cited_receipts(record):
            if ledger.get("receipt-facts", ref) is not None or ref in (earlier or {}):
                continue
            facts = given.get(ref)
            if facts is None:
                raise Refusal("receipt-unconfirmed")
            try:
                receipt = self.receipts.read(str(facts.get("operationId")))
            except ReceiptUnavailable:
                raise Refusal("receipt-unconfirmed") from None
            for name in ("receiptId", "operationId", "targetId", "inputHash", "outcome",
                         "operation"):
                if str(receipt.get(name)) != str(facts.get(name)):
                    raise Refusal("receipt-unconfirmed")
            if (receipt.get("operation") == DECISION_OPERATION
                    and receipt.get("outcome") == "succeeded" and str(
                        receipt.get("authorityRef")) not in (self.decision_authorities or ())):
                # A decision is yours only: bound under your in-person grant, never the
                # scheduler's (your decision of 2026-10-26). A failed one is refused below
                # as no decision at all.
                raise Refusal("decision-receipt-not-in-person")
            confirmed.append({**{name: facts[name] for name in (
                "receiptId", "operationId", "operation", "targetId", "inputHash", "outcome",
            )}, "confirmedAt": _ledger_time(self.clock())})
        return confirmed

    def _require_decision(self, ledger: Ledger, record: dict, facts: list[dict],
                          cited: set) -> None:
        """A MaintainerApproval is admitted only on a decision receipt that is this
        decision's own (review finding, Major, R17):

        - a succeeded `platform.decision.record` receipt;
        - whose bound input hash is this approval's step, subject reference, subject
          digest and decision (`decision_input_hash`, what `Decisions.record` binds), so
          a receipt for one step or subject never approves another;
        - that no other approval cites, in the ledger or earlier in this batch, so an
          earlier receipt of yours is never reused;
        - bound under your in-person grant, checked again with PlatformControl when the
          receipt is already in the ledger (`_confirm` checks one it confirms now), so
          the unattended scheduler cannot cite a receipt the ledger holds for another
          record."""
        ref = record.get("operatorReceiptRef")
        stored = ledger.get("receipt-facts", ref)
        known = stored or next((item for item in facts if item["receiptId"] == ref), None)
        if (
            known is None
            or known["operation"] != DECISION_OPERATION
            or known["outcome"] != "succeeded"
        ):
            raise Refusal("decision-receipt-required")
        if decision_input_hash(record) != known["inputHash"]:
            raise Refusal("decision-receipt-mismatch")
        if ref in cited or any(
            item.get("operatorReceiptRef") == ref
            and item.get("approvalId") != record.get("approvalId")
            for item in ledger.records("maintainer-approval")
        ):
            raise Refusal("decision-receipt-reused")
        if stored is not None:
            self._decision_in_person(stored)

    def _decision_in_person(self, stored: Mapping) -> None:
        """A decision receipt the ledger already holds, read again from PlatformControl:
        the same receipt, bound under your in-person grant."""
        try:
            receipt = self.receipts.read(str(stored.get("operationId")))
        except ReceiptUnavailable:
            raise Refusal("receipt-unconfirmed") from None
        for name in ("receiptId", "operationId", "inputHash", "outcome", "operation"):
            if str(receipt.get(name)) != str(stored.get(name)):
                raise Refusal("receipt-unconfirmed")
        if str(receipt.get("authorityRef")) not in (self.decision_authorities or ()):
            raise Refusal("decision-receipt-not-in-person")

    def copy(self, stdout: BinaryIO) -> dict:
        ledger = self._open()
        try:
            result = ledger.copy(stdout)
            stdout.flush()
            return {"ok": True, **result}
        finally:
            ledger.close()

    def verify(self, document: dict) -> dict:
        if document:
            raise Refusal("input-field-refused", status=2)
        ledger = self._open()
        try:
            head = ledger.store.verify()
            return {"ok": True, "count": head.count, "head": head.head}
        finally:
            ledger.close()

    def read(self, document: dict) -> dict:
        if not set(document) <= {"kind", "key", "limit"}:
            raise Refusal("input-field-refused", status=2)
        limit = document.get("limit", MAX_READ)
        if type(limit) is not int or not 1 <= limit <= MAX_READ:
            raise Refusal("input-field-refused", status=2)
        try:
            schema = schema_of(str(document.get("kind")))
        except RecordRefused:
            raise Refusal("kind-refused", status=2) from None
        ledger = self._open()
        try:
            if "key" in document:
                key = document["key"]
                if not isinstance(key, list) or len(key) != len(schema.key) or not schema.keyed:
                    raise Refusal("input-field-refused", status=2)
                record = ledger.get(schema.kind, tuple(key))
                return {"ok": True, "records": [] if record is None else [record],
                        "revision": ledger.revision(schema.kind, tuple(key))}
            records = ledger.records(schema.kind) if schema.keyed else ledger.events(schema.kind)
            return {"ok": True, "records": records[-limit:], "total": len(records)}
        finally:
            ledger.close()

    def repair(self, stdin: BinaryIO) -> dict:
        """Replace a damaged ledger by a verified copy streamed in, then record the
        damage's incident (BR6.10)."""
        if self.environment not in ("rehearsal", "live"):
            raise Refusal("environment-unknown")
        damage = self._damage()
        if damage is None:
            if read_damage(self.folder) is None:
                raise Refusal("ledger-not-damaged")
            # A repair interrupted after the replacement: finish recording its incident.
            return self._record_incident(read_damage(self.folder))
        # The first finding, kept by a process that found it earlier, or this one.
        finding = record_damage(self.folder, damage, self.clock())
        payload = stdin.read(MAX_COPY + 1)
        if len(payload) > MAX_COPY or not payload.endswith(b"\n"):
            raise Refusal("copy-refused")
        staging = self.folder.parent / f".ledger-repair-{secrets.token_hex(8)}"
        os.mkdir(staging, FOLDER_MODE)
        try:
            count, head = _copy_head(payload)
            _write_new(staging / LedgerStore.LOG, payload)
            _write_new(staging / LedgerStore.HEAD, canonical({"count": count, "head": head}))
            try:
                Ledger.open(staging, clock=self.clock).close()
            except (LedgerDamaged, RecordRefused):
                raise Refusal("copy-refused") from None
            moment = self.clock().astimezone(dt.UTC).strftime("%Y%m%dT%H%M%S%fZ")
            aside = self.evidence / "ledger-repair" / moment
            aside.mkdir(mode=FOLDER_MODE, parents=True)
            for name in (LedgerStore.LOG, LedgerStore.HEAD):
                if (self.folder / name).exists():
                    os.rename(self.folder / name, aside / name)
            for name in (LedgerStore.LOG, LedgerStore.HEAD):
                os.rename(staging / name, self.folder / name)
        finally:
            for leftover in staging.iterdir():
                leftover.unlink()
            staging.rmdir()
        store = LedgerStore.open(self.folder, clock=self.clock)
        try:
            store.append_entry(REPAIRED, {
                "copySha256": entry_digest(payload), "copyCount": count, "copyHead": head,
                "asideRef": f"evidence/ledger-repair/{moment}", "damage": damage,
            })
        finally:
            store.close()
        return self._record_incident(finding)

    def _record_incident(self, finding: dict | None) -> dict:
        """The damage's `operations.ledger` incident, opened at its first finding, in
        the repaired ledger; then the marker moves aside with the damaged files. The
        incident's identity comes from the finding, so a finished repair's next run
        records nothing again."""
        from .incidents import KIND as INCIDENT
        from .incidents import LEDGER, LEDGER_DAMAGED

        if finding is None:
            raise Refusal("ledger-not-damaged")
        ledger = self._open()
        try:
            repairs = ledger.events(REPAIRED)
            if not repairs:
                raise Refusal("ledger-not-damaged")
            aside = repairs[-1]["asideRef"]
            incident = str(uuid5(NAMESPACE_URL, "docsuri-ledger-damage:"
                                 f"{finding['foundAt']}:{finding['category']}"))
            if ledger.get(INCIDENT, incident) is None:
                ledger.append(INCIDENT, {
                    "incidentId": incident, "environment": self.environment,
                    "revision": 1, "capabilities": [LEDGER],
                    "correlationIds": [f"ledger:{finding['category']}"], "state": "open",
                    "openedAt": finding["foundAt"], "openedBy": LEDGER_DAMAGED,
                    "recoveryRequestIds": [], "evidenceRefs": [aside],
                }, expect_revision=0)
            marker = self.folder / DAMAGE_MARKER
            if marker.exists():
                os.rename(marker, self.evidence / aside.removeprefix("evidence/")
                          / DAMAGE_MARKER)
            head = ledger.store.head
            return {"ok": True, "count": head.count, "head": head.head, "aside": aside,
                    "incidentId": incident}
        finally:
            ledger.close()

    def _damage(self) -> str | None:
        try:
            ledger = self._open()
        except LedgerDamaged as error:
            return error.category
        try:
            ledger.store.verify()
            return None
        except LedgerDamaged as error:
            return error.category
        finally:
            ledger.close()


DECISION_INPUTS = ("step", "subjectRef", "subjectDigest", "decision")


def decision_input_hash(record: Mapping) -> str:
    """The input hash `platform.decision.record` binds for this approval: the digest of
    the canonical JSON of its step, subject reference, subject digest and decision, as
    `Decisions.record` hands them and PlatformControl's operator hashes them
    (`docsuri_ops.u8_platform.drivers.input_hash`; a test pins the two together)."""
    inputs = {name: record.get(name) for name in DECISION_INPUTS}
    return hashlib.sha256(json.dumps(inputs, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False).encode()).hexdigest()


def _copy_head(payload: bytes) -> tuple[int, str]:
    lines = payload[:-1].split(b"\n")
    if not lines or not lines[-1]:
        raise Refusal("copy-refused")
    return len(lines), entry_digest(lines[-1])


def _write_new(path: Path, payload: bytes) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())


def _ledger_time(moment: dt.datetime) -> str:
    from .ledger import utc_text

    return utc_text(moment)


def _emit(stream: BinaryIO, value: dict, status: int) -> int:
    stream.write(json.dumps(value, sort_keys=True, separators=(",", ":")).encode() + b"\n")
    stream.flush()
    return status


def run(argv: list[str], command: LedgerCommand, *, environ: Mapping[str, str],
        stdin: BinaryIO, stdout: BinaryIO, stderr: BinaryIO) -> int:
    """The fixed shape: an untouched environment, then exactly one word."""
    if refused_environment(environ):
        return _emit(stdout, {"ok": False, "reason": "environment-refused"}, 2)
    if len(argv) != 1 or argv[0] not in WORDS:
        return _emit(stdout, {"ok": False, "reason": "word-refused"}, 2)
    return command.run(argv[0], stdin, stdout, stderr)


def profile_environment(root: Path = PRODUCTION_PROFILE) -> str | None:
    """The production profile's mode, which a repair's incident is recorded under; None
    when the profile does not load, so a repair is refused (`environment-unknown`)
    rather than recorded under a guessed environment. Every other word works without
    it."""
    from backend.u8_profile import ProductionProfile, ProfileRefused

    try:
        return ProductionProfile.load(root / "environment.json", service_uid=os.getuid()).mode
    except (ProfileRefused, OSError, ValueError):
        return None


def _production_receipts() -> ReceiptReader:
    """PlatformControl's receipt reader (Step 27): `readReceipt` with the operation's
    name, through the service account's evidence-reader authority. While production's
    store has no reader provisioned (Step 37), nothing is confirmed."""
    from docsuri_ops.u8_platform.platform_profile import U8PlatformProfile
    from docsuri_ops.u8_platform.u8_protocols import readers

    try:
        bound = readers(U8PlatformProfile.production())
    except (OSError, ValueError):
        return UnboundReceiptReader()
    return UnboundReceiptReader() if bound is None else bound[0]


IN_PERSON_GRANTS = ("operatorRoutine", "operatorDestructive")


def in_person_authorities(path: Path) -> frozenset[str]:
    """Your in-person grants from the installation's authority record
    (`platform-authorities.json`, no secret); none when it does not load, so no decision
    is confirmed."""
    try:
        value = json.loads(path.read_bytes())
        grants = value["authorities"]
        return frozenset(str(grants[name]) for name in IN_PERSON_GRANTS)
    except (OSError, ValueError, KeyError, TypeError):
        return frozenset()


def production_command() -> LedgerCommand:
    """The installed release's command over the production profile's ledger."""
    from docsuri_ops.u8_platform.platform_profile import U8_PRODUCTION_CONTROL

    return LedgerCommand(
        folder=PRODUCTION_PROFILE / "ledger", evidence=PRODUCTION_PROFILE / "evidence",
        receipts=_production_receipts(), environment=profile_environment(),
        decision_authorities=in_person_authorities(
            U8_PRODUCTION_CONTROL / "platform-authorities.json"),
    )


def main_fixed(argv: list[str] | None = None) -> int:
    """`ops/bin/docsuri-ledger`'s entry: one word, the production profile."""
    return run(
        sys.argv[1:] if argv is None else argv, production_command(), environ=os.environ,
        stdin=sys.stdin.buffer, stdout=sys.stdout.buffer, stderr=sys.stderr.buffer,
    )


if __name__ == "__main__":  # pragma: no cover - the fixed program is ops/bin/docsuri-ledger
    raise SystemExit(main_fixed())
