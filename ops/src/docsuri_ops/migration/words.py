"""The operator tool's migration and inventory words (U8 plan Step 31; the person's
decisions of 2026-10-24, "Add operator commands" and "Cloudflare's numbers"; BR8.9,
BR8.11, BR8.15, BR9.11, BR9.14, Workflows 9–11).

`docsuri-ops migration <word>` and `docsuri-ops inventory <word>` (routed here from the
operator tool's `operator_tool.main`), with bounded JSON on standard input and one JSON result on
standard output, as the recovery words are:

- `migration dry-run` `{confirm?}`: your go-ahead to copy v1, then the dry run to its
  report (or until it is interrupted or fails) — Workflow 9;
- `migration resume` `{runId}`: an interrupted run, from exactly the phase it stopped in;
- `migration abandon` `{runId}`: an interrupted dry run fails, and its copies are
  disposed;
- `migration decide` `{runId}` lists the misfit kinds and reasons a run met;
  `{kind, reasonKey, decision, confirm?}` records your decision on one — Workflow 10;
- `migration accept` / `reject` `{runId, confirm?}`: your decision on a dry run's report.
  An acceptance moves the cutover when a CutoverRecord exists (BR9.3; your decision of
  2026-10-24): `Cutover.dry_run_accepted`, the run's rehearsal database set through
  `platform.profile.rehearsal-database`, v2's three roles restarted through
  `platform.service.control`, readiness waited for (up to 10 minutes), and the soak
  started or restarted once the release's verification has passed.
- `inventory take --cloudflare-export <file>` `{known?}`: the consumer inventory from your
  Cloudflare export, counts only (`cloudflare_export`) — Workflow 11;
- `inventory record` `{inventoryId, clientRef, disposition, confirm?}`: your decision
  on one consumer's disposition; once the inventory is complete it is linked to the
  CutoverRecord (`Cutover.inventory_taken`).

The final run stays reachable only inside `cutover start` (Workflow 13).

With `--production`, the migration words run on the production migration platform
(`production`; the person's decision of 2026-10-24, "Build it, test on test v1"): v1 is
read only at the addresses the operator's environment file names, and v2's side runs
through the production environment tool and the import program, in person.

**Your decisions, in two calls.** A word that takes a decision first answers `shown`:
the subject exactly as you are shown it, rendered as `u8_platform.decisions`
renders it, with its digest, and nothing is recorded. Run it again with `confirm` set to
that digest: the subject is rendered again from the current records, and only when it
is unchanged is your decision recorded through `platform.decision.record` (Workflow 18)
and the word goes on. A subject that changed in between is refused, and the new one is
shown. In person: on this Mac the operator tool runs under `sudo -k` with your login's
PlatformControl login released in person; in the composed realm its synthetic operator
stands in.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import stat
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from backend.modules.operations.errors import OperationsError

MIGRATION_WORDS = ("dry-run", "resume", "abandon", "decide", "accept", "reject")
INVENTORY_WORDS = ("take", "record")
MISFIT_DECISIONS = ("map", "archive-only", "drop")
MAX_INPUT = 64 * 1024
GO_AHEAD_REF = "v1"


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


class Refused(Exception):
    """A word's refusal: a fixed code and reason key, never content."""

    def __init__(self, code: str, reason: str):
        super().__init__(reason)
        self.code, self.reason = code, reason


# --- your decisions, in two calls -----------------------------------------------------------


@dataclass
class InPerson:
    """Shows a subject, or records your decision on exactly what you were shown."""

    decisions: object  # u8_platform.decisions.Decisions

    def decide(self, step: str, subject_ref: str, subject: dict, decision: str,
               confirm: str | None) -> dict:
        """`{"shown": ...}` without `confirm`; `{"approvalId": ...}` with it."""
        shown = self.decisions.show(step, subject_ref, subject)
        if confirm is None:
            return {"shown": {"state": "shown", "step": step, "subjectRef": subject_ref,
                              "subject": subject, "digest": shown.digest}}
        if confirm != shown.digest:
            return {"shown": {"state": "subject-changed", "step": step,
                              "subjectRef": subject_ref, "subject": subject,
                              "digest": shown.digest}}
        recorded = self.decisions.record(shown, decision, current=lambda: subject)
        return {"approvalId": recorded["approvalId"]}


def _confirm(document: dict) -> str | None:
    value = document.get("confirm")
    if value is not None and (not isinstance(value, str) or len(value) != 64):
        raise Refused("INVALID_INPUT", "confirm-is-the-shown-digest")
    return value


def _only(document: dict, allowed: set[str], required: set[str] = frozenset()) -> None:
    if not set(document) <= allowed or not required <= set(document):
        raise Refused("INVALID_INPUT", "word-or-input-refused")


# --- the migration words ------------------------------------------------------------------


class MigrationWords:
    def __init__(self, tool, misfits, in_person: InPerson, *,
                 cutover: Callable[[], object] | None = None):
        """`tool` is the MigrationTool, `misfits` the MisfitDecisions over its ledger,
        `cutover` the cutover commands' tool, built only when an accepted dry run moves
        the cutover (BR9.3)."""
        self.tool, self.misfits, self.in_person = tool, misfits, in_person
        self.ledger = tool.ledger
        self.cutover = cutover

    def run(self, word: str, document: dict) -> dict:
        if word not in MIGRATION_WORDS:
            raise Refused("INVALID_INPUT", "migration-word-outside-its-set")
        return getattr(self, word.replace("-", "_"))(document)

    def dry_run(self, document: dict) -> dict:
        _only(document, {"confirm"})
        from backend.modules.operations.migration.misfits import Decisions

        subject = {"step": "dry-run-go-ahead", "source": GO_AHEAD_REF,
                   "toolCommit": self.tool.tool_commit,
                   "decisionsDigest": Decisions.from_ledger(self.ledger).digest()}
        decided = self.in_person.decide("dry-run-go-ahead", GO_AHEAD_REF, subject, "approved",
                                        _confirm(document))
        if "shown" in decided:
            return decided["shown"]
        run = self.tool.start_dry(decided["approvalId"])
        return self._ended(self.tool.run(run["runId"]))

    def resume(self, document: dict) -> dict:
        _only(document, {"runId"}, {"runId"})
        return self._ended(self.tool.resume(str(document["runId"])))

    def abandon(self, document: dict) -> dict:
        _only(document, {"runId"}, {"runId"})
        return self._ended(self.tool.abandon(str(document["runId"])))

    def decide(self, document: dict) -> dict:
        from docsuri_ops.migration.decisions import STEP, listing, subject

        if set(document) == {"runId"}:
            return {"state": "listed", "misfits": listing(self.tool.runs, document["runId"])}
        _only(document, {"kind", "reasonKey", "decision", "confirm"},
              {"kind", "reasonKey", "decision"})
        kind, reason, decision = (str(document[key]) for key in ("kind", "reasonKey",
                                                                 "decision"))
        if decision not in MISFIT_DECISIONS:
            raise Refused("INVALID_INPUT", "misfit-decision-outside-its-set")
        shown_subject = subject(kind, reason, decision)
        decided = self.in_person.decide(STEP, f"{kind}:{reason}", shown_subject, "approved",
                                        _confirm(document))
        if "shown" in decided:
            return decided["shown"]
        record = self.misfits.decide(kind, reason, decision, approval_id=decided["approvalId"],
                                     mapping_rule=shown_subject["mappingRule"])
        return {"state": "decided", "kind": kind, "reasonKey": reason,
                "decision": record["decision"], "approvalId": decided["approvalId"]}

    def accept(self, document: dict) -> dict:
        return self._report(document, "approved")

    def reject(self, document: dict) -> dict:
        return self._report(document, "rejected")

    def _report(self, document: dict, decision: str) -> dict:
        from backend.modules.operations.migration_records import REPORT

        _only(document, {"runId", "confirm"}, {"runId"})
        run_id = str(document["runId"])
        run = self.tool.runs.require(run_id)
        if run["kind"] != "dry":
            # A final run's report is decided inside the switch (`cutover start`).
            raise Refused("CONFLICT", "final-report-is-the-switchs")
        if run["state"] != "reported":
            raise Refused("CONFLICT", f"run-is-{run['state']}")
        report = self.ledger.get(REPORT, run_id)
        if report is None:
            raise Refused("CONFLICT", "report-missing")
        if decision == "approved" and self.tool.target_disposed(run):
            # Its rehearsal database was removed (a rollback or opening's disposal):
            # accepting it would set the profile onto a database that does not exist.
            raise Refused("CONFLICT", "rehearsal-database-disposed")
        shown_subject = {"step": "dry-run-report", "runId": run_id, "decision": decision,
                         "report": {key: report.get(key) for key in (
                             "reportRef", "reportDigest", "kinds", "reconciles")}}
        confirm = _confirm(document)
        # The cutover's tool is put together before your decision is recorded: a part of
        # its wiring that is not in place refuses here, with nothing recorded, so the
        # same word runs again once it is (an acceptance cannot be decided twice).
        cutover = self._cutover() if (confirm is not None and decision == "approved") else None
        decided = self.in_person.decide("dry-run-report", run_id, shown_subject, decision,
                                        confirm)
        if "shown" in decided:
            return decided["shown"]
        ended = self.tool.decide(run_id, decided["approvalId"])
        result = self._ended(ended)
        if ended["state"] == "accepted" and cutover is not None:
            # The migration words move the cutover (BR9.3; your decision of 2026-10-24):
            # the acceptance on the record, the run's rehearsal database set, v2's roles
            # restarted, readiness waited for, then the soak started or restarted. A move
            # that stops answers why; `cutover check` runs it again.
            result["cutover"] = cutover.after_dry_run(run_id, self.tool.target_of(ended))
        return result

    def _cutover(self):
        """The cutover commands' tool, or a refusal naming the part not in place."""
        if self.cutover is None:
            return None
        try:
            return self.cutover()
        except Refused:
            raise
        except Exception as error:  # noqa: BLE001 - a wiring part not in place, by its key
            raise Refused("POLICY_UNRESOLVED", _wiring_reason(error)) from None

    @staticmethod
    def _ended(run: dict) -> dict:
        keys = ("runId", "kind", "state", "interruptedPhase", "reason", "acceptedAt")
        return {key: run[key] for key in keys if run.get(key) is not None}


# --- the inventory words --------------------------------------------------------------------


MAX_EXPORT_OPEN = 4 * 1024 * 1024


def read_export(path: Path) -> bytes:
    """Your export file: a regular file, never through a link, within its bound."""
    from docsuri_ops.migration.cloudflare_export import ExportRefused

    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError:
        raise ExportRefused("export-unreadable") from None
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode):
            raise ExportRefused("export-unreadable")
        if info.st_size > MAX_EXPORT_OPEN:
            raise ExportRefused("export-too-large")
        raw = os.read(descriptor, MAX_EXPORT_OPEN + 1)
    finally:
        os.close(descriptor)
    if len(raw) > MAX_EXPORT_OPEN:
        raise ExportRefused("export-too-large")
    return raw


class InventoryWords:
    def __init__(self, inventory, in_person: InPerson, *, cutover=None):
        """`inventory` is the ConsumerInventory over the ledger; `cutover` the
        CutoverRecord machine a complete inventory is linked to (`inventory_taken`)."""
        self.inventory, self.in_person, self.cutover = inventory, in_person, cutover

    def run(self, word: str, document: dict, *, export: Path | None = None) -> dict:
        if word not in INVENTORY_WORDS:
            raise Refused("INVALID_INPUT", "inventory-word-outside-its-set")
        if word == "take":
            return self.take(document, export)
        if export is not None:
            raise Refused("INVALID_INPUT", "the-export-is-takes")
        return self.record(document)

    def take(self, document: dict, export: Path | None) -> dict:
        from docsuri_ops.migration import cloudflare_export

        _only(document, {"known"})
        if export is None:
            raise Refused("INVALID_INPUT", "cloudflare-export-required")
        known = document.get("known") or []
        if not isinstance(known, list) or not all(
                isinstance(item, dict) and isinstance(item.get("clientRef"), str)
                for item in known):
            raise Refused("INVALID_INPUT", "known-integrations-form")
        try:
            parsed = cloudflare_export.read(read_export(export))
        except cloudflare_export.ExportRefused as refused:
            raise Refused("INVALID_INPUT", str(refused)) from None
        observed = self.inventory.observe(parsed)
        record = self.inventory.record(observed, known=known)
        # Each client's user agent is shown to you here, once; the ledger keeps its
        # opaque reference only.
        return {"state": "taken", "inventoryId": record["inventoryId"],
                "observedFrom": record["observedFrom"], "observedUntil": record["observedUntil"],
                "requests": record["requests"], "peakRequests": record["peakRequests"],
                "peakAt": record["peakAt"], "intervalSeconds": record["intervalSeconds"],
                "peakRequestsPerSecond": round(parsed.peak_rate, 4),
                "consumers": [{key: item[key] for key in (
                    "clientRef", "userAgent", "routesUsed", "requests")} for item in observed]
                + [{"clientRef": item["clientRef"], "source": "known"}
                   for item in record["consumers"] if item["source"] == "known"],
                "complete": record["complete"]}

    def record(self, document: dict) -> dict:
        from docsuri_ops.migration.inventory import DISPOSITIONS, KIND, STEP

        _only(document, {"inventoryId", "clientRef", "disposition", "confirm"},
              {"inventoryId", "clientRef", "disposition"})
        inventory_id, client, disposition = (str(document[key]) for key in (
            "inventoryId", "clientRef", "disposition"))
        if disposition not in DISPOSITIONS:
            raise Refused("INVALID_INPUT", "disposition-outside-its-set")
        current = self.inventory.ledger.get(KIND, inventory_id)
        consumer = None if current is None else next(
            (item for item in current["consumers"] if item["clientRef"] == client), None)
        if consumer is None:
            raise Refused("NOT_FOUND", "consumer-unknown")
        shown_subject = {"step": STEP, "inventoryId": inventory_id, "clientRef": client,
                         "routesUsed": consumer["routesUsed"], "source": consumer["source"],
                         "requests": consumer.get("requests"), "disposition": disposition}
        decided = self.in_person.decide(STEP, client, shown_subject, "approved",
                                        _confirm(document))
        if "shown" in decided:
            return decided["shown"]
        record = self.inventory.dispose(inventory_id, client, disposition,
                                        decided["approvalId"])
        result = {"state": "recorded", "inventoryId": inventory_id, "clientRef": client,
                  "disposition": disposition, "complete": record["complete"]}
        if self.cutover is not None and record.get("complete") and (
                self.cutover.current() is not None):
            # A complete inventory is linked to the CutoverRecord (your decision of
            # 2026-10-24): `Cutover.inventory_taken`.
            linked = self.cutover.inventory_taken(inventory_id)
            result["cutover"] = linked.get("consumerInventoryId")
        return result


# --- wiring -----------------------------------------------------------------------------------


def realm_appender(ledger, clock: Callable[[], dt.datetime]) -> Callable[[dict], dict]:
    """The ledger component's `append`, run in process in the composed realm: the
    decision's receipt is confirmed as the fixed command confirms it."""
    from backend.modules.operations.ledger import utc_text

    def append(document: dict) -> dict:
        receipts = tuple({**item, "confirmedAt": utc_text(clock())}
                         for item in document["receipts"])
        ledger.append(document["kind"], document["record"],
                      expect_revision=document["expectRevision"], receipts=receipts)
        return {"ok": True}

    return append


def production_appender(ledger) -> Callable[[dict], dict]:
    """The ledger component's fixed command (`docsuri-ledger append`), which confirms the
    decision's receipt itself."""

    def append(document: dict) -> dict:
        return ledger.append(document["kind"], document["record"],
                             expect_revision=document["expectRevision"],
                             receipts=document["receipts"])

    return append


def _commit(root: Path) -> str:
    completed = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"],
                               capture_output=True, text=True, timeout=30, check=False)
    value = completed.stdout.strip()
    return value if completed.returncode == 0 and len(value) == 40 else "0" * 40


# The composed realm's synthetic v1 stores (Step 34): its search index and object store
# on the realm's own ports, never v1's live ones.
REALM_V1_INDEX = "http://127.0.0.1:19209"
REALM_V1_OBJECTS = "http://127.0.0.1:19009"


def realm_migration_tool(profile, ledger, *, clock: Callable[[], dt.datetime]):
    """The migration tool over the composed realm, as the realm's cutover journeys wire
    it: its operator and store, the realm driver's backup agent, the synthetic v1's
    stores, the realm's own PostgreSQL for the run's databases, its isolation evidence
    and this Mac's free space."""
    import boto3
    from backend.local_profile import LocalProfile
    from backend.modules.operations.migration_records import MigrationRuns
    from backend.modules.operations.retained_copies import RetainedCopies
    from backend.u8_policy import SYNTHETIC_OPERATIONS
    from botocore.config import Config

    from docsuri_ops.arrangement.paths import REALM_DATABASES
    from docsuri_ops.migration.disk_guard import DiskGuard
    from docsuri_ops.migration.isolation_gate import IsolationGate
    from docsuri_ops.migration.realm import RealmDatabases, owners_for
    from docsuri_ops.migration.snapshot import BucketObjects, OpenSearchDocuments, Snapshot
    from docsuri_ops.migration.tool import MigrationPlatform, MigrationTool
    from docsuri_ops.platform_control.profile import private_bytes
    from docsuri_ops.u8_platform.drivers import load_config
    from docsuri_ops.u8_platform.drivers.realm import RealmDriver
    from docsuri_ops.u8_platform.u8_protocols import realm_operator

    root = profile.run_root
    operator = realm_operator(profile, "operator", ledger, clock=clock)
    driver = RealmDriver(load_config(profile.effects_root))
    dataset = json.loads(private_bytes(root / "v1" / "dataset.json"))
    secret = json.loads(private_bytes(root / "v1" / "credentials.json"))
    s3 = boto3.client("s3", endpoint_url=REALM_V1_OBJECTS,
                      aws_access_key_id=secret["objectsUser"],
                      aws_secret_access_key=secret["objectsPassword"],
                      region_name="ap-northeast-2", config=Config(signature_version="s3v4"))
    evidence, spool = root / "evidence" / "migration", root / "migration-spool"
    spool.mkdir(mode=0o700, exist_ok=True)

    def dump(kind, record, decided):
        document = {"kind": kind, "recordId": record}
        if decided is not None:
            document["decided"] = decided
        return driver.agent_word("snapshot", document, via="in-person")

    copies = RetainedCopies(ledger, SYNTHETIC_OPERATIONS, clock=clock)
    snapshot = Snapshot(copies, dump=dump, stream=driver.snapshot_stream,
                        index=OpenSearchDocuments(REALM_V1_INDEX, dataset["index"]),
                        objects=BucketObjects(s3, dataset["bucket"]), evidence=evidence)
    databases = RealmDatabases.for_realm(root)
    local = LocalProfile.load(root / "environment.json")
    platform = MigrationPlatform(
        operator=operator, names=REALM_DATABASES, snapshot=snapshot,
        create_rehearsal=databases.create_rehearsal, create_import=databases.create_import,
        restore_import=databases.restore_import, import_reader=databases.import_reader,
        owners_for=owners_for(local), stream_back=driver.stream_back,
        isolation=IsolationGate(profile.state_root / "isolation",
                                freshness_seconds=SYNTHETIC_OPERATIONS
                                .isolation_freshness_seconds, clock=clock),
        disk=DiskGuard(lambda: shutil.disk_usage(root).free,
                       SYNTHETIC_OPERATIONS.internal_disk_threshold_bytes,
                       SYNTHETIC_OPERATIONS.internal_disk_critical_bytes),
        spool=spool, evidence=evidence, installed=lambda: True,
        database_bytes=databases.database_bytes,
        prepare_production=databases.prepare_production,
    )
    return MigrationTool(MigrationRuns(ledger, clock=clock), copies, platform, clock=clock,
                         tool_commit=_commit(Path(__file__).resolve().parents[4]))


def _wiring_reason(error: Exception) -> str:
    """A production part not in place, as a fixed key."""
    if isinstance(error, OSError):
        return "operator-environment-unreadable"
    return getattr(error, "reason", None) or str(error)


def _words(kind: str, args, clock):
    """The words and the ledger to close, over the realm or, in person, this Mac."""
    from backend.modules.operations.migration_records import MisfitDecisions
    from backend.u8_policy import PRODUCTION_OPERATIONS, SYNTHETIC_OPERATIONS

    from docsuri_ops.migration.inventory import ConsumerInventory
    from docsuri_ops.u8_platform.decisions import Decisions

    if args.production:
        from docsuri_ops.arrangement.paths import ArrangementPaths
        from docsuri_ops.production_wiring import (
            LedgerClient,
            WiringRefused,
            production_operator,
        )
        from docsuri_ops.u8_platform.drivers import DriverRefused

        from .production import SourcesRefused, production_migration_tool

        ledger = LedgerClient(via="in-person", clock=clock)
        try:
            operator = production_operator(ledger, clock=clock)
            in_person = InPerson(Decisions(operator, production_appender(ledger), clock=clock))
            if kind == "migration":
                # v1's own stores, read only at the addresses the operator's environment
                # file names (the person's decision of 2026-10-24, "Build it, test on
                # test v1").
                tool = production_migration_tool(ledger, operator, clock=clock)

                def cutover():
                    from docsuri_ops.cutover.tool import CutoverTool
                    from docsuri_ops.production_wiring import production_cutover_platform

                    return CutoverTool(ledger, PRODUCTION_OPERATIONS,
                                       production_cutover_platform(ledger, operator,
                                                                   clock=clock),
                                       clock=clock)

                return MigrationWords(tool, MisfitDecisions(ledger, clock=clock),
                                      in_person, cutover=cutover), ledger
        except (WiringRefused, SourcesRefused, DriverRefused, OSError) as refused:
            ledger.close()
            raise Refused("POLICY_UNRESOLVED", _wiring_reason(refused)) from None
        inventory = ConsumerInventory(
            ledger, window_seconds=PRODUCTION_OPERATIONS.consumer_window_seconds, clock=clock,
            evidence=ArrangementPaths().profile / "evidence" / "inventory")
        return InventoryWords(inventory, in_person,
                              cutover=_machine(ledger, PRODUCTION_OPERATIONS, clock)), ledger
    from backend.modules.operations.ledger import Ledger

    from docsuri_ops.u8_platform.platform_profile import U8PlatformProfile
    from docsuri_ops.u8_platform.u8_protocols import realm_operator

    profile = U8PlatformProfile.realm(args.environment_file.parent)
    ledger = Ledger.open(profile.run_root / "ledger", clock=clock)
    try:
        operator = realm_operator(profile, "operator", ledger, clock=clock)
        in_person = InPerson(Decisions(operator, realm_appender(ledger, clock), clock=clock))
        if kind == "migration":
            tool = realm_migration_tool(profile, ledger, clock=clock)

            def cutover():
                from docsuri_ops.cutover.tool import CutoverTool, realm_platform

                return CutoverTool(ledger, SYNTHETIC_OPERATIONS,
                                   realm_platform(profile, ledger, clock=clock,
                                                  policy=SYNTHETIC_OPERATIONS), clock=clock)

            return MigrationWords(tool, MisfitDecisions(ledger, clock=clock), in_person,
                                  cutover=cutover), ledger
        inventory = ConsumerInventory(
            ledger, window_seconds=SYNTHETIC_OPERATIONS.consumer_window_seconds, clock=clock,
            evidence=profile.run_root / "evidence" / "inventory")
        return InventoryWords(inventory, in_person,
                              cutover=_machine(ledger, SYNTHETIC_OPERATIONS, clock)), ledger
    except BaseException:
        ledger.close()
        raise


def _machine(ledger, policy, clock):
    """The CutoverRecord machine a complete inventory is linked to."""
    from backend.modules.operations.cutover import Cutover

    return Cutover(ledger, policy, clock=clock)


def main(kind: str, argv: list[str]) -> int:
    """`docsuri-ops migration <word>` or `docsuri-ops inventory <word>` on the composed
    realm (`--environment-file`), or in person on this Mac (`--production`)."""
    from docsuri_ops.platform_control.errors import ControlError
    from docsuri_ops.production_wiring import WiringRefused

    words = MIGRATION_WORDS if kind == "migration" else INVENTORY_WORDS
    parser = argparse.ArgumentParser(prog=f"docsuri-ops {kind}")
    parser.add_argument("word", choices=words)
    parser.add_argument("--environment-file", type=Path)
    parser.add_argument("--production", action="store_true")
    if kind == "inventory":
        parser.add_argument("--cloudflare-export", type=Path)
    args = parser.parse_args(argv)
    raw = sys.stdin.buffer.read(MAX_INPUT + 1)
    ledger = None
    try:
        if len(raw) > MAX_INPUT:
            raise Refused("INVALID_INPUT", "input-exceeds-its-bound")
        document = json.loads(raw or b"{}")
        if not isinstance(document, dict):
            raise Refused("INVALID_INPUT", "input-must-be-one-object")
        if args.production == (args.environment_file is not None):
            raise Refused("POLICY_UNRESOLVED", "name-production-or-the-realms-environment")
        handler, ledger = _words(kind, args, _now)
        if kind == "inventory":
            result = handler.run(args.word, document, export=args.cloudflare_export)
        else:
            result = handler.run(args.word, document)
    except Refused as refused:
        sys.stdout.write(json.dumps({"ok": False, "code": refused.code,
                                     "reasonKey": refused.reason}))
        return 1
    except WiringRefused as refused:
        # A production part not in place, met during a word (its wiring is lazy).
        sys.stdout.write(json.dumps({"ok": False, "code": "POLICY_UNRESOLVED",
                                     "reasonKey": _wiring_reason(refused)}))
        return 1
    except ControlError as error:
        sys.stdout.write(json.dumps({"ok": False, "error": error.as_wire_error()}))
        return 1
    except OperationsError as error:
        sys.stdout.write(json.dumps({"ok": False, "code": error.code, "current": error.current}))
        return 1
    except ValueError:
        sys.stdout.write(json.dumps({"ok": False, "code": "INVALID_INPUT",
                                     "reasonKey": "input-unreadable"}))
        return 1
    finally:
        if ledger is not None:
            ledger.close()
    sys.stdout.write(json.dumps({"ok": True, "result": result}, sort_keys=True))
    return 0
