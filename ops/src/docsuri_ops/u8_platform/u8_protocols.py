"""A6's bound operations (U8 plan Step 27; A6, BR4.2, BR6.12, BR9.10, BR9.13–BR9.17,
NFR4.2, NFR7.19).

- `load_revision` reads `inventory.json` version 2: U7's `protocols`, unchanged, and
  A6's `u8Protocols`, each with its authority class, deadline, address-space bound,
  effect kind and fixed targets. U7's loader and bootstrap read only `protocols`.
- `check` holds every A6 precondition (`PRECONDITIONS`), checked again before each
  effect from the facts the operator reads at that moment (`Facts`): the profile's
  mode, admission and current rehearsal database, the ledger's recovery requests,
  cutover record and decisions, and the instance's databases.
- `Operator.execute` keeps U7's path: the preconditions, then the receipt bound to
  actor, operation, target and input hash with its evidence (U7's store), then one
  effect under U7's bounded executor (`executor.run_effect`), whose child is U8's
  `adapter` (`BOUNDED_CHILD`, through the executor's `adapter_module` seam), which hands
  the effect kind to the driver the profile names. A wrong actor or target, or a changed
  input under the same key, causes no effect: U7's store refuses it. `Operator` refuses
  to build when either of U7's two seams is missing.
- `Operator.reconcile` settles an unknown outcome from its target, without running the
  effect again.
- `execute_settled` runs one fixed-key operation to a settled outcome for the words and
  passes that run again (the cutover, the release command, the disposal pass, the
  migration tool's disposal): a replayed failure, an interrupted operation reconciled not
  applied, or an unknown one reconciled not applied runs again under the next retry key.
- `ReceiptReader`, `EvidenceReader` and `Inspector` are the bounded readers: the ledger
  component's receipt confirmation (with the operation's name, `read_receipt_named`),
  the backup agent's status for the service account, and PlatformControl's status for
  `platform.status`, none of which can execute anything.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import inspect
import json
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

from docsuri_ops.arrangement.paths import DatabaseNames
from docsuri_ops.platform_control import enums
from docsuri_ops.platform_control.errors import (
    CONFLICT,
    FORBIDDEN,
    INVALID_INPUT,
    POLICY_UNRESOLVED,
    ControlError,
)
from docsuri_ops.platform_control.inventory import _INVENTORY_PATH, Inventory, load_inventory

from .drivers import input_hash, input_path, write_caller, write_input
from .effect_kinds import U8_EFFECT_KINDS
from .platform_profile import TUNNEL_ORIGINS, U8PlatformProfile

# U8's bounded child, named through U7's executor seam (`run_effect`'s `adapter_module`).
BOUNDED_CHILD = "docsuri_ops.u8_platform.adapter"

PROFILE_FIELDS = {
    "platform.profile.mode": "mode",
    "platform.profile.admission": "admission",
    "platform.profile.rehearsal-database": "rehearsalDatabase",
    "platform.profile.backup-volume": "backupVolume",
}
ACTIVE_RECOVERY = frozenset(
    {"awaiting-operator", "running", "verifying", "unknown", "post-restore-pending", "held"}
)
WAITING_RECOVERY = frozenset({"requested", "awaiting-operator"})
RECONCILED = {"reconciled-applied": "succeeded", "reconciled-not-applied": "failed"}
DATABASE_LIMITS = {"rehearsal": 2, "import": 1, "scratch": 1}
# The standing authority's grants (BR4.2, BR9.17): the routine set (the scheduled backup
# and the isolation check; by the person's decision of 2026-10-26, "Drop it", no
# `platform.copy.dispose`: no unattended path disposes of a copy through PlatformControl,
# since the disposal pass uses the backup agent's unattended `dispose-due` and every
# disposal by event runs in person); the restore verification's restore, of a scratch
# database only; and exactly one destructive operation, `platform.database.remove` of a
# disposable database at its backstop during the disposal pass. Each is (target scope,
# permitted operations, authority class); U7's store refuses anything outside them, and
# `Operator` refuses a standing actor every other destructive operation, any copy
# disposal, and a restore of any other target, before anything is bound.
STANDING_REMOVAL = "platform.database.remove"
STANDING_REMOVAL_TARGETS = ("database-rehearsal", "database-import", "database-scratch")
# The person's decisions of 2026-10-25 ("Production restore only in person") and of
# 2026-10-26 ("Give restore its own grant"): the scheduler's restore is a grant of its own
# whose scope is the scratch database alone, so the store itself, as well as `Operator`,
# refuses the scheduler a production restore.
STANDING_RESTORE = "platform.database.restore"
STANDING_RESTORE_TARGETS = ("database-scratch",)
PRODUCTION_RESTORE_IN_PERSON = "production-restore-in-person"
SCHEDULER_GRANTS = {
    "schedulerRoutine": (
        ("database-production", "database-rehearsal", "database-scratch", "copies",
         "isolation", "backup-volume", "ledger-copy"),
        # The lone ledger copy, last (L1-5, U8 plan Step 64(c)).
        ("platform.database.backup", "platform.isolation.check", "platform.ledger.copy"),
        enums.CLASS_ROUTINE,
    ),
    "schedulerRestore": (STANDING_RESTORE_TARGETS, (STANDING_RESTORE,), enums.CLASS_ROUTINE),
    "schedulerRemoval": (STANDING_REMOVAL_TARGETS, (STANDING_REMOVAL,),
                         enums.CLASS_DESTRUCTIVE),
}
# The retained-copy kind of each disposable database kind (retained_copies.BACKSTOPS).
DATABASE_COPY_KINDS = {"rehearsal": "rehearsal-database", "import": "import-database",
                       "scratch": "scratch-restore"}
STANDING_REMOVAL_INPUTS = frozenset({"database", "via", "pass", "copyId"})
# Production's store logins, each a member of the runtime role (installer phase 3).
PRODUCTION_READER = "docsuri_platform_reader"
PRODUCTION_OPERATOR = "docsuri_platform_operator"
PRODUCTION_SCHEDULER = "docsuri_platform_scheduler"
APPROVAL_STEPS = (
    "dry-run-go-ahead", "dry-run-report", "misfit-decision", "consumer-disposition",
    "v1-restart-rehearsal", "switch-start", "final-report", "provider-sign-in",
    "provider-first-effect", "admission-opening", "abort-review", "rollback", "rollback-cancel",
    "rollback-copy-waiver", "settlement", "production-restore", "restore-abandonment",
    "disposal-date", "backup-volume-retirement",
)


class PreconditionRefused(Exception):
    """An A6 precondition does not hold and no effect runs. Raised before anything is
    bound by the precondition checks (`check`, `_standing_scope`), and after a receipt
    was bound by `Operator.execute`'s `recheck`: then the receipt is settled failed and
    not applied first (`waiting`), so the refusal leaves a settled receipt behind, never
    an open one (review finding, Minor, R18)."""

    def __init__(self, reason: str, *, waiting: bool = False):
        super().__init__(reason)
        self.reason, self.waiting = reason, waiting


# --- the revision ----------------------------------------------------------------------


@dataclass(frozen=True)
class U8Protocol:
    name: str
    authority_class: str
    max_age_seconds: int
    deadline_seconds: int
    address_space_bytes: int
    effect_kind: str
    targets: tuple[str, ...]


@dataclass(frozen=True)
class Revision:
    version: int
    u7: Inventory
    u8: tuple[U8Protocol, ...]

    def by_name(self, name: str) -> U8Protocol | None:
        return next((item for item in self.u8 if item.name == name), None)

    def all_names(self) -> tuple[str, ...]:
        return tuple(p.name for p in self.u7.retained()) + tuple(p.name for p in self.u8)


def load_revision(path: Path | None = None) -> Revision:
    source = path or _INVENTORY_PATH
    raw = json.loads(source.read_text(encoding="utf-8"))
    if raw.get("version") != 2:
        raise ValueError("A6's protocols need inventory version 2")
    u7 = load_inventory(source)
    seen = {p.name for p in u7.protocols}
    protocols = []
    for item in raw.get("u8Protocols", []):
        name = item.get("name")
        if not isinstance(name, str) or name in seen or not name.startswith("platform."):
            raise ValueError(f"protocol {name!r} is duplicated or outside A6's names")
        seen.add(name)
        if item.get("disposition") != enums.DISPOSITION_RETAINED or item.get(
            "nativeVerified"
        ) is not True:
            raise ValueError(f"protocol {name!r} must be retained-local and native")
        if item.get("authorityClass") not in (enums.CLASS_ROUTINE, enums.CLASS_DESTRUCTIVE):
            raise ValueError(f"protocol {name!r} has an invalid authority class")
        if item.get("effectKind") not in U8_EFFECT_KINDS:
            raise ValueError(f"protocol {name!r} has an invalid effect kind")
        numbers = [item.get(key) for key in ("maxAgeSeconds", "deadlineSeconds",
                                             "addressSpaceBytes")]
        if any(type(value) is not int or value <= 0 for value in numbers):
            raise ValueError(f"protocol {name!r} needs finite positive bounds")
        protocols.append(U8Protocol(
            name=name, authority_class=item["authorityClass"], max_age_seconds=numbers[0],
            deadline_seconds=numbers[1], address_space_bytes=numbers[2],
            effect_kind=item["effectKind"], targets=tuple(item.get("targets", ())),
        ))
    return Revision(raw["version"], u7, tuple(protocols))


# --- the facts the preconditions read --------------------------------------------------


@dataclass
class Facts:
    """What the operator reads before each effect."""

    names: DatabaseNames
    mode: str
    admission: str
    current_rehearsal: str | None
    ledger: object
    now: dt.datetime
    databases: Callable[[], set[str]] = field(default=lambda: set())
    labels: tuple[str, ...] = ()

    def requests(self) -> list[dict]:
        return list(self.ledger.records("recovery-request"))

    def request(self, request_id: str | None) -> dict | None:
        return None if request_id is None else self.ledger.get("recovery-request", request_id)

    def cutover(self) -> dict | None:
        records = list(self.ledger.records("cutover-record"))
        return records[-1] if records else None

    def approval(self, approval_id: str | None) -> dict | None:
        return None if approval_id is None else self.ledger.get("maintainer-approval",
                                                                approval_id)


def _require(condition: bool, reason: str, *, waiting: bool = False) -> None:
    if not condition:
        raise PreconditionRefused(reason, waiting=waiting)


def _instant(text: str) -> dt.datetime:
    return dt.datetime.fromisoformat(text.replace("Z", "+00:00"))


def _backup_passed(facts: Facts, backup_id: str | None) -> bool:
    record = None if backup_id is None else facts.ledger.get("backup-set", backup_id)
    return record is not None and record.get("integrity") == "passed"


# --- the preconditions, one per protocol -----------------------------------------------


def _database_backup(target, inputs, facts):
    kind = facts.names.kind_of(str(inputs.get("database")))
    _require({"database-production": "production", "database-rehearsal": "rehearsal"}
             .get(target) == kind, "database-refused")
    _require(inputs.get("via") in ("standing", "in-person"), "authority-refused")


def recorded_databases(ledger) -> Callable[[], set[str]]:
    """The instance's disposable databases as the ledger records them: every location of
    a retained copy of a database kind (rehearsal, import, scratch) that is neither
    disposed, retired nor returned to service. Each such database is recorded before it
    is created and disposed only on its removal's receipt (BR9.12, BR9.17), so a removal
    that failed or is pending keeps it listed. This is what A6's "profile, database,
    sets" guard and NFR8.15's scratch limit read in production and in the composed realm
    (`production_facts`, `realm_facts`)."""
    kinds = frozenset(DATABASE_COPY_KINDS.values())
    closed = ("disposedAt", "retiredWithVolumeAt", "returnedToServiceAt")

    def read() -> set[str]:
        return {location.removeprefix("database/")
                for record in ledger.records("retained-copy")
                if record.get("kind") in kinds and not any(name in record for name in closed)
                for location in record.get("locations", ())
                if location.startswith("database/")}

    return read


def admit_new_database(kind: str, existing: set[str], names: DatabaseNames) -> None:
    """NFR8.15: at most two rehearsal databases, one import and one scratch database."""
    count = sum(1 for name in existing if names.kind_of(name) == kind)
    _require(count < DATABASE_LIMITS[kind], f"{kind}-database-limit")


def database_limit_reason(kind: str, ledger, names: DatabaseNames) -> str | None:
    """NFR8.15 at a creation (a dry run's start, `cutover begin`, the rollback): the
    reason a new `kind` database is refused, counted from the ledger's open retained
    copies (`recorded_databases`), or None. Each caller asks before it writes anything."""
    try:
        admit_new_database(kind, recorded_databases(ledger)(), names)
    except PreconditionRefused as refused:
        return refused.reason
    return None


def _database_restore(target, inputs, facts):
    if target == "database-scratch":
        name = str(inputs.get("scratchDatabase"))
        _require(facts.names.kind_of(name) == "scratch", "scratch-name-refused")
        # The verification records its scratch copy before this restore (U8 plan Step
        # 64(d)): its own recorded database is admitted, a second open one is not.
        admit_new_database("scratch", facts.databases() - {name}, facts.names)
        _require(inputs.get("mode") == "scratch", "restore-mode-refused")
        return
    # A production restore runs only with the operator in person (BR4.7, BR4.2, C11; the
    # person's decision of 2026-10-25, "Production restore only in person").
    _require(inputs.get("via") == "in-person", PRODUCTION_RESTORE_IN_PERSON)
    request = facts.request(inputs.get("recoveryRequestId"))
    _require(request is not None and request["operation"] == "restore.production"
             and request["state"] == "running", "restore-not-at-its-step")
    _require(any(ref.startswith("recreate:") for ref in request.get("evidenceRefs", [])),
             "restore-before-recreate")


def _database_recreate(target, inputs, facts):
    _require(inputs.get("database") == facts.names.production, "database-refused")
    request = facts.request(inputs.get("recoveryRequestId"))
    live_open = facts.mode == "live" and facts.admission == "open"
    if request is None:
        _require(not live_open, "recreate-refused-while-live-and-open")
        return
    _require(request["operation"] == "restore.production", "recreate-refused")
    refs = request.get("evidenceRefs", [])
    if inputs.get("abandonment"):
        # A restore abandonment: your decision, the request held, no successor waiting;
        # it may follow an earlier recreate and repeats only as a retry after a failure.
        _require(request["state"] == "held", "abandonment-not-held")
        approval = facts.approval(request.get("abandonmentApprovalId"))
        _require(approval is not None and approval["step"] == "restore-abandonment"
                 and approval["decision"] == "approved", "abandonment-not-decided")
        _require(not any(
            other.get("predecessorRequestId") == request["recoveryRequestId"]
            and other["state"] in WAITING_RECOVERY for other in facts.requests()
        ), "successor-waiting")
        _require(not any(ref.startswith("abandon-recreate:") for ref in refs),
                 "abandonment-recreated")
        return
    _require(request["state"] == "running", "restore-not-at-its-step")
    _require("predecessorRequestId" in request or _backup_passed(
        facts, request.get("preRestoreBackupId")), "pre-restore-set-not-passed")
    _require(not any(ref.startswith("recreate:") for ref in refs), "recreate-already-done")


def _database_remove(target, inputs, facts):
    name = str(inputs.get("database"))
    kind = facts.names.kind_of(name)
    _require(kind in ("rehearsal", "import", "scratch")
             and target == f"database-{kind}", "database-refused")
    _require(name != facts.current_rehearsal, "current-rehearsal-database")
    busy = any(
        request.get("targetId") == name and request["state"] in ACTIVE_RECOVERY
        and request["operation"] in ("backup.create", "restore.verify")
        for request in facts.requests()
    )
    _require(not busy, "rehearsal-database-in-use", waiting=True)
    _require(inputs.get("via") in ("standing", "in-person"), "authority-refused")
    if inputs["via"] == "standing":
        _standing_removal(name, kind, inputs, facts)


def _standing_removal(name: str, kind: str, inputs, facts) -> None:
    """BR9.17: unattended, a disposable database is removed only by the disposal pass,
    at its backstop date, for the retained copy that records it there. The copy's
    disposal point is its backstop for these kinds (retained_copies.record)."""
    _require(set(inputs) == STANDING_REMOVAL_INPUTS and inputs.get("pass") == "disposal",
             "standing-removal-outside-disposal-pass")
    record = facts.ledger.get("retained-copy", str(inputs.get("copyId")))
    _require(record is not None and record.get("kind") == DATABASE_COPY_KINDS[kind]
             and f"database/{name}" in record.get("locations", ())
             and not any(closed in record for closed in
                         ("disposedAt", "retiredWithVolumeAt", "returnedToServiceAt")),
             "standing-removal-copy-unrecorded")
    point = record.get("disposeAfter")
    _require(point is not None and _instant(point) <= facts.now,
             "standing-removal-before-backstop")


def _service_control(target, inputs, facts):
    _require(target in facts.labels and inputs.get("label") == target, "label-refused")
    _require(inputs.get("action") in ("start", "stop"), "action-refused")
    if inputs["action"] == "start" and target.endswith((".host", ".workers", ".scheduler")):
        blocked = any(
            request["operation"] == "restore.production" and request["state"] in ACTIVE_RECOVERY
            and "startAuthorizedAt" not in request for request in facts.requests()
        )
        _require(not blocked, "restore-active-without-start-authorization")


def _tunnel_route(target, inputs, facts):
    _require(inputs.get("origin") in TUNNEL_ORIGINS, "origin-refused")


def _isolation_check(target, inputs, facts):
    _require(set(inputs) == {"via"} and inputs["via"] in ("standing", "in-person"),
             "input-refused")


# Each profile change only at its step (BR9.15): the cutover states it may happen in.
PROFILE_STEPS = {
    "mode": {"live": ("switching",), "rehearsal": ("aborting", "rolling-back", "switching")},
    "admission": {"open": ("switching",), "maintainer-only": ("switching", "aborting",
                                                              "rolling-back")},
    # A dry run accepted after a rollback sets it too (CutoverRecord row "rolled-back").
    # By your decision of 2026-10-24 ("Create a fresh rehearsal database") it may also
    # change while a rollback runs: at v1's serving the rollback sets its new, empty
    # rehearsal database before the mode returns to rehearsal, since opening removed
    # every rehearsal database (U8 plan Step 33).
    "rehearsalDatabase": {"*": ("preparing", "rehearsing", "ready-to-switch", "switched",
                                "rolling-back", "rolled-back")},
    "backupVolume": {"*": ("preparing", "rehearsing", "ready-to-switch", "switched",
                           "rolling-back")},
}


def _profile_change(target, inputs, facts):
    field_name = inputs.get("field")
    _require(field_name in PROFILE_STEPS, "profile-field-refused")
    value = inputs.get("value")
    steps = PROFILE_STEPS[field_name]
    # Values may be objects (the backup volume's identity); only scalars name a step.
    keyed = value if value is None or isinstance(value, (str, int, bool)) else None
    allowed = steps.get(keyed, steps.get("*")) if keyed is not None else steps.get("*")
    _require(allowed is not None, "profile-value-refused")
    cutover = facts.cutover()
    _require(cutover is not None and cutover["state"] in allowed, "profile-change-outside-step")
    if field_name == "admission" and value == "open":
        approval = facts.approval(inputs.get("approvalId"))
        _require(approval is not None and approval["step"] == "admission-opening"
                 and approval["decision"] == "approved", "admission-not-decided")
    if field_name == "backupVolume":
        approval = facts.approval(inputs.get("approvalId"))
        _require(approval is not None and approval["step"] == "backup-volume-retirement"
                 and approval["decision"] == "approved", "retirement-not-decided")
    if field_name == "rehearsalDatabase" and value is not None:
        _require(facts.names.kind_of(str(value)) == "rehearsal", "profile-value-refused")


COPY_RECORDS = {"RetainedCopy": "retained-copy", "BackupSet": "backup-set",
                "LedgerCopy": "ledger-copy"}
# The one disposal event `_copy_dispose` admits by event: a rehearsal set whose database
# was removed, disposed of in person by `cutover check` or `cutover open` (the person's
# decision of 2026-10-26, "Only in person"); no standing actor cites it (`_standing_scope`).
STANDING_DISPOSAL_EVENT = "rehearsal-database-removed"


def _release_blocker(ledger) -> str | None:
    """The install or release rollback holding the live exclusion
    (`release_records.release_blocker`), or None."""
    from backend.modules.operations.release_records import release_blocker

    return release_blocker(ledger)


def _copy_dispose(target, inputs, facts):
    kind = COPY_RECORDS.get(inputs.get("recordKind"))
    _require(kind is not None, "record-kind-refused")
    record = facts.ledger.get(kind, inputs.get("recordId"))
    _require(record is not None and "disposedAt" not in record, "copy-not-recorded")
    _require(inputs.get("place") in ("backup-volume", "database", "v1-stores"),
             "place-refused")
    if inputs["place"] == "v1-stores":
        _v1_stores_deleted(kind, record, inputs, facts)
        return
    if inputs["place"] == "database":
        _require(facts.names.kind_of(str(inputs.get("location"))) in
                 ("rehearsal", "import", "scratch"), "database-refused")
        _require(inputs.get("location") != facts.current_rehearsal,
                 "current-rehearsal-database")
    if kind == "backup-set":
        # A rehearsal database's disposal completes in the order profile, database, sets:
        # its sets go only once the profile no longer names it and it is removed.
        source = str(record.get("databaseIncarnation", "")).split(":", 1)[0]
        if facts.names.kind_of(source) == "rehearsal":
            _require(source != facts.current_rehearsal, "current-rehearsal-database")
            _require(source not in facts.databases(), "rehearsal-database-not-removed")
    if inputs.get("event") == STANDING_DISPOSAL_EVENT:
        # Only a rehearsal BackupSet whose source database is removed is disposed of on
        # this event (review finding, Minor, R13); the source checks are above.
        source = str(record.get("databaseIncarnation", "")).split(":", 1)[0]
        _require(kind == "backup-set" and facts.names.kind_of(source) == "rehearsal",
                 "disposal-event-refused")
    point = record.get("disposeAfter") or record.get("retainUntil")
    _require(inputs.get("event") is not None or (
        point is not None and _instant(point) <= facts.now), "disposal-point-not-reached")
    live = facts.cutover()
    _require(live is None or live["state"] not in ("switching", "aborting", "rolling-back"),
             "live-exclusion-held", waiting=True)
    # An install or a release rollback holds the live exclusion too (BR4.4; review
    # finding, Minor, R13): no disposal starts during either.
    _require(_release_blocker(facts.ledger) is None, "live-exclusion-held", waiting=True)


V1_STORES_INPUTS = frozenset({"recordKind", "recordId", "place", "locations", "via"})


def _v1_stores_deleted(kind: str, record: dict, inputs, facts) -> None:
    """v1's stores are deleted only by the operator in person, by hand, at the date
    your decision approved; this records it after a read-only check that each location
    is gone, and never deletes anything (the person's decision of 2026-10-22, BR9.17)."""
    _require(set(inputs) == V1_STORES_INPUTS and kind == "retained-copy"
             and record.get("kind") == "v1-stores", "v1-stores-input-refused")
    _require(inputs.get("via") == "in-person", "v1-stores-in-person-only")
    _require(not any(name in record for name in
                     ("retiredWithVolumeAt", "returnedToServiceAt")), "copy-not-recorded")
    _require(list(inputs.get("locations") or ()) == list(record["locations"]),
             "v1-stores-locations-differ")
    _require(_instant(record["disposeAfter"]) <= facts.now, "disposal-point-not-reached")
    live = facts.cutover()
    _require(live is None or live["state"] not in ("switching", "aborting", "rolling-back"),
             "live-exclusion-held", waiting=True)


def _v1_lifecycle_apply(target, inputs, facts):
    cutover = facts.cutover()
    _require(cutover is not None and cutover["state"] == "rolling-back", "not-rolling-back")
    _require(isinstance(inputs.get("outcomes"), list) and isinstance(
        inputs.get("accounts"), list), "input-refused")


def _decision_record(target, inputs, facts):
    _require(inputs.get("step") in APPROVAL_STEPS, "step-refused")
    _require(inputs.get("decision") in ("approved", "declined"), "decision-refused")
    digest = str(inputs.get("subjectDigest", ""))
    _require(len(digest) == 64 and all(c in "0123456789abcdef" for c in digest),
             "subject-digest-refused")
    _require(isinstance(inputs.get("subjectRef"), str) and 0 < len(inputs["subjectRef"]) <= 256,
             "subject-refused")


LEDGER_COPY_INPUTS = frozenset({"via", "environment"})


def _ledger_copy(target, inputs, facts):
    """A lone ledger copy (L1-5, L1-48): exactly `{via, environment}`, and no exclusion,
    since it writes only the ledger's copy to the volume and touches no database, so it
    runs while a switch or a production restore holds the environment."""
    _require(set(inputs) == LEDGER_COPY_INPUTS, "input-refused")
    _require(inputs.get("via") in ("standing", "in-person"), "authority-refused")
    _require(inputs.get("environment") in ("live", "rehearsal"), "environment-refused")


PRECONDITIONS: dict[str, Callable] = {
    "platform.database.backup": _database_backup,
    "platform.database.restore": _database_restore,
    "platform.database.recreate": _database_recreate,
    "platform.database.remove": _database_remove,
    "platform.service.control": _service_control,
    "platform.tunnel.route": _tunnel_route,
    "platform.isolation.check": _isolation_check,
    "platform.profile.mode": _profile_change,
    "platform.profile.admission": _profile_change,
    "platform.profile.rehearsal-database": _profile_change,
    "platform.profile.backup-volume": _profile_change,
    "platform.copy.dispose": _copy_dispose,
    "platform.v1.lifecycle.apply": _v1_lifecycle_apply,
    "platform.decision.record": _decision_record,
    "platform.ledger.copy": _ledger_copy,
}


def check(protocol: U8Protocol, target: str, inputs: Mapping, facts: Facts) -> None:
    """Every A6 precondition for one effect, from the facts read now."""
    allowed = facts.labels if protocol.name == "platform.service.control" else protocol.targets
    _require(target in allowed, "target-refused")
    if protocol.name in PROFILE_FIELDS:
        _require(inputs.get("field") == PROFILE_FIELDS[protocol.name], "profile-field-refused")
    PRECONDITIONS[protocol.name](target, inputs, facts)


# --- the shared path ----------------------------------------------------------------------


def effect_token(target: str, inputs_hash: str, key: str) -> str:
    from docsuri_ops.platform_control.cli import effect_token as u7_token

    return u7_token(target, inputs_hash, key)


def _require_seams() -> None:
    """U7's two seams U8's parts reach U7's through: the executor's `adapter_module` and
    `native_adapter.main`'s `effect`. Without either, no operator is built."""
    from docsuri_ops.platform_control import executor, native_adapter

    for function, name in ((executor.run_effect, "adapter_module"),
                           (native_adapter.main, "effect")):
        if name not in inspect.signature(function).parameters:
            raise ControlError(POLICY_UNRESOLVED,
                               f"U7's bounded child has no `{name}` seam")


class Operator:
    """One actor's bound operations over U8's platform profile and U7's store."""

    def __init__(self, profile: U8PlatformProfile, store, *, actor: str,
                 authorities: Mapping[str, str], facts: Callable[[], Facts],
                 revision: Revision | None = None, run_effect: Callable | None = None,
                 standing: bool = False, operation_grants: Mapping[str, str] | None = None):
        """`authorities` holds this actor's grant for each authority class it has
        (`routine`, `destructive-release`); a routine grant never covers a destructive
        effect (U7). `operation_grants` names a grant of its own for an operation, used
        for it instead of its class's grant (the scheduler's restore grant). `standing`
        marks the scheduler's standing authority: it acts only unattended (`via:
        standing`), and its one destructive grant covers only `platform.database.remove`
        (BR4.2, BR9.17)."""
        _require_seams()
        if not actor or not authorities:
            raise ControlError(FORBIDDEN, "an operator identity and authority are required")
        self.profile, self.store, self.actor = profile, store, actor
        self.standing = standing
        self.authorities = dict(authorities)
        self.operation_grants = dict(operation_grants or {})
        self.authority = next(iter(self.authorities.values()))
        self.facts, self.revision = facts, revision or load_revision()
        if run_effect is None:
            from docsuri_ops.platform_control.executor import run_effect as bounded

            run_effect = bounded
        self.run_effect = run_effect

    def _protocol(self, operation: str) -> U8Protocol:
        protocol = self.revision.by_name(operation)
        if protocol is None:
            raise ControlError(POLICY_UNRESOLVED, "operation is not one of A6's protocols")
        return protocol

    def execute(self, operation: str, target: str, inputs: dict, *, key: str,
                injected_fault: str | None = None,
                recheck: Callable[[], str | None] | None = None) -> dict:
        """Check the preconditions, bind the receipt, then run one effect.

        `recheck` is asked again once the receipt is bound, so under the target's lease,
        before the effect's input is written: a reason it answers settles the receipt as
        not applied (its effect never ran) and refuses (`PreconditionRefused`, waiting).
        An in-person service control, the soak's start and `cutover check`'s set retry
        ask it (review finding, Minor, R13; the person's decision of 2026-10-26, "Check
        the release run lock"): it reads the release command's run lock, which a release
        command holds from its start, so a release command that began between the first
        check and the binding is seen. The ledger alone would not show it: in production
        the ledger view is a copy taken before the first check, and a re-read of that
        copy sees nothing new. A release command that begins after the binding finds
        this operation's lease."""
        protocol = self._protocol(operation)
        if not isinstance(inputs, dict):
            raise ControlError(INVALID_INPUT, "an operation's input is one object")
        if self.standing:
            self._standing_scope(protocol, target, inputs)
        check(protocol, target, inputs, self.facts())
        digest = input_hash(inputs)
        evidence = self.store.record_evidence(
            target=target, input_hash=digest, environment=self.profile.environment,
            observations={"preconditions": "passed", "operation": operation},
            max_age_seconds=protocol.max_age_seconds,
        )
        token = effect_token(target, digest, key)
        authority = self.operation_grants.get(protocol.name) or self.authorities.get(
            protocol.authority_class)
        if authority is None:
            raise ControlError(FORBIDDEN, "no grant of this operation's authority class")
        binding = self.store.begin_operation(
            actor=self.actor, authority_id=authority, operation=operation, target=target,
            input_hash=digest, environment=self.profile.environment,
            evidence_id=str(evidence["evidenceId"]), generation=int(evidence["generation"]),
            idempotency_key=key, effect_reference=f"{target}/effect-{token}.json",
        )
        if binding.get("replayed"):
            # The receipt an earlier call bound under this key, named as such so a caller
            # can tell a failure it is retrying from one that just happened.
            return {**self._named(binding, operation), "replayed": True}
        reason = recheck() if recheck is not None else None
        if reason is not None:
            self.store.mark_executing(str(binding["operationId"]))
            self.store.settle_operation(operation_id=str(binding["operationId"]),
                                        outcome="failed", disposition="not-applied",
                                        effect_refs=[])
            raise PreconditionRefused(reason, waiting=True)
        write_input(self.profile.effects_root / target, token, inputs)
        if not self.profile.is_production:
            # The realm's driver runs a standing request under the scheduler's identity
            # (your decision of 2026-10-26, "Only in person"); production's actors each
            # have their own effects folder and grants.
            write_caller(self.profile.effects_root / target, token,
                         "scheduler" if self.standing else "operator")
        self.store.mark_executing(str(binding["operationId"]))
        outcome = self.run_effect(
            target_root=self.profile.effects_root, operation_id=str(binding["operationId"]),
            operation_name=operation, target_id=target, token=token,
            effect_kind=protocol.effect_kind, input_hash=digest,
            deadline_seconds=protocol.deadline_seconds, injected_fault=injected_fault,
            address_space_bytes=protocol.address_space_bytes, adapter_module=BOUNDED_CHILD,
        )
        settle, disposition, refs = outcome.as_receipt_fields()
        settled = self.store.settle_operation(operation_id=str(binding["operationId"]),
                                              outcome=settle, disposition=disposition,
                                              effect_refs=refs)
        result = self._named(settled, operation)
        if outcome.error:
            result["refusal"] = str(outcome.error.get("message", "refused"))
        return result

    @staticmethod
    def _standing_scope(protocol: U8Protocol, target: str, inputs: dict) -> None:
        """The standing authority holds nothing in person, no restore but a scratch
        database's, no copy disposal at all, and no destructive operation but the
        disposal pass's database removal; refused before anything is bound."""
        if protocol.name == STANDING_RESTORE and target not in STANDING_RESTORE_TARGETS:
            raise PreconditionRefused(PRODUCTION_RESTORE_IN_PERSON)
        if "via" in inputs and inputs["via"] != "standing":
            raise ControlError(FORBIDDEN, "the standing authority acts only unattended")
        if protocol.name == "platform.copy.dispose":
            # No standing disposal of any copy, at any place or on any event (the
            # person's decision of 2026-10-26, "Drop it"): the disposal pass disposes of
            # due files through the backup agent's own unattended word, a database leaves
            # only through the removal grant, and a disposal by event runs in person.
            raise ControlError(FORBIDDEN, "the standing authority disposes of no copy")
        if protocol.authority_class == enums.CLASS_DESTRUCTIVE and (
            protocol.name != STANDING_REMOVAL or inputs.get("via") != "standing"
        ):
            raise ControlError(FORBIDDEN,
                               "no grant of this destructive operation to the standing authority")

    @staticmethod
    def _named(receipt: dict, operation: str) -> dict:
        from docsuri_ops.platform_control.cli import project_receipt

        return {**project_receipt(receipt), "operation": operation,
                "reconciliationState": receipt.get("reconciliationState")}

    def _read_named(self, operation_id: str) -> dict:
        """The receipt through whichever of this actor's grants covers its target (a
        standing removal's receipt is in its removal grant's scope, not the routine's)."""
        refused: ControlError | None = None
        for authority in dict.fromkeys([*self.authorities.values(),
                                        *self.operation_grants.values()]):
            try:
                return self.store.call_committed("read_receipt_named",
                                                 (self.actor, authority, operation_id))
            except ControlError as error:
                refused = error
        assert refused is not None
        raise refused

    def reconcile(self, operation_id: str) -> dict:
        """An unknown outcome is settled from its target alone; the effect never runs
        again (BR9.10, NFR4.2)."""
        from docsuri_ops.platform_control.reconciler import promote_stale

        from .drivers import observe

        promote_stale(self.store)
        receipt = self._read_named(operation_id)
        if receipt.get("outcome") != "unknown" or receipt.get(
            "reconciliationState"
        ) != "unresolved":
            return self._reconciled(receipt, receipt)
        protocol = self._protocol(receipt["operation"])
        reference = str(receipt["effectReference"])
        target, name = reference.split("/", 1)
        token = name.removeprefix("effect-").removesuffix(".json")
        directory = self.profile.effects_root / target
        if not (directory / name).is_file() and not input_path(directory, token).exists():
            # Bound, but stopped before its input was written (the review's fix of
            # 2026-10-26): the effect reads its input from that file, so it never ran.
            applied = False
        else:
            applied = observe(self.profile.effects_root, target, token,
                              protocol.effect_kind, receipt["inputHash"])
        settled = self.store.reconcile_receipt(
            operation_id=operation_id, applied=applied,
            evidence=[f"target:{reference}:{'present' if applied else 'absent'}"],
        )
        return self._reconciled(settled, receipt)

    def _reconciled(self, settled: dict, receipt: dict) -> dict:
        """The settled receipt as `_named` projects it, plus its `effectReference`, which
        U7's projection drops: a caller rebuilds an applied effect from what lies beside
        it (U8 plan Step 64(a))."""
        named = self._named(settled, receipt["operation"])
        reference = settled.get("effectReference") or receipt.get("effectReference")
        if reference is not None:
            named["effectReference"] = str(reference)
        return named


# --- a fixed-key effect run to a settled outcome -------------------------------------------

# A step whose earlier attempt left nothing applied runs again under the next of these
# keys, so a word or pass run again retries it instead of replaying the failure.
EFFECT_RETRIES = 8
IN_FLIGHT = ("accepted", "running")
UNSETTLED_REASONS = {"unknown": "effect-outcome-unknown", "in-progress": "effect-in-progress",
                     "exhausted": "step-retries-exhausted"}


class EffectUnsettled(Exception):
    """A bound effect that did not settle as applied. `kind` is `failed` (it ran in this
    call and failed), `unknown` (its outcome could not be proven from its target),
    `in-progress` (an earlier call's operation is still within its lease) or `exhausted`
    (every retry key already holds a failure)."""

    def __init__(self, kind: str, receipt: Mapping | None = None):
        super().__init__(kind)
        self.kind, self.receipt = kind, receipt

    @property
    def reason(self) -> str | None:
        """The fixed reason key, or None for `failed` (each caller names its own)."""
        return UNSETTLED_REASONS.get(self.kind)


def retry_key(key: str, attempt: int) -> str:
    """The key of a step's `attempt`th retry: the key itself first, then a digest under
    the key's own prefix, within U7's 128 characters (the cutover's keys keep the form
    `CutoverTool` always gave them)."""
    if attempt == 0:
        return key
    prefix = key.split(":", 1)[0][:32]
    return f"{prefix}:" + hashlib.sha256(f"{key}:retry:{attempt}".encode()).hexdigest()


def settled_outcome(receipt: Mapping) -> str:
    """A receipt's outcome as reconciliation settled it (`ReceiptReader.outcome`)."""
    outcome = str(receipt.get("outcome"))
    if outcome != "unknown":
        return outcome
    return RECONCILED.get(str(receipt.get("reconciliationState")), "unknown")


def execute_settled(operator, operation: str, target: str, inputs: dict, *, key: str,
                    retries: int = EFFECT_RETRIES,
                    recheck: Callable[[], str | None] | None = None) -> dict:
    """One fixed-key bound operation run to a settled outcome, so a word or pass run
    again completes a step instead of replaying what an earlier run left behind.

    - A succeeded receipt, this call's or replayed, or an unknown one reconciled applied,
      is the step's result (`outcome: succeeded`).
    - A replayed receipt that left nothing applied (failed, or unknown reconciled not
      applied) runs again under the next retry key.
    - A replayed operation still accepted or running (its process interrupted after the
      receipt was bound: killed, Ctrl-C, a closed terminal) is promoted once its lease's
      deadline passed and reconciled from its target (`Operator.reconcile`), then settled
      as above; within the lease it is `in-progress`, and nothing runs beside it.
    - A failure or an unprovable outcome in this call fails the step at once.

    A6's preconditions and U7's refusals (`PreconditionRefused`, `ControlError`) pass
    through: nothing was bound for them, or (`recheck`, `Operator.execute`) what was bound
    settled as not applied."""
    options = {} if recheck is None else {"recheck": recheck}
    for attempt in range(retries + 1):
        receipt = operator.execute(operation, target, inputs, key=retry_key(key, attempt),
                                   **options)
        replayed = bool(receipt.get("replayed"))
        if settled_outcome(receipt) in ("unknown", *IN_FLIGHT):
            receipt = {**operator.reconcile(str(receipt["operationId"])), "replayed": replayed}
        outcome = settled_outcome(receipt)
        if outcome == "succeeded":
            return {**receipt, "outcome": "succeeded"}
        if outcome == "failed" and replayed:
            continue
        if outcome in IN_FLIGHT:
            raise EffectUnsettled("in-progress", receipt)
        if outcome == "unknown" or receipt.get("reconciliationState") == (
                "reconciled-not-applied"):
            raise EffectUnsettled("unknown", receipt)
        raise EffectUnsettled("failed", receipt)
    raise EffectUnsettled("exhausted")


def reconcile_unresolved(operator, target: str) -> list[dict]:
    """Every unresolved receipt on `target` that this actor's grants can read, settled
    from its target (`Operator.reconcile`), after PlatformControl has promoted operations
    whose lease passed (the review's fixes of 2026-10-26). This covers an earlier run's
    operation bound under a key no later run walks: one interrupted after binding, and
    one bound but stopped before its input was written (reconciled not applied, since
    its effect never ran). An operation still within its lease is not yet unresolved,
    and PlatformControl's target lease refuses a new binding beside it. Nothing runs
    again."""
    from docsuri_ops.platform_control.reconciler import promote_stale

    promote_stale(operator.store)
    settled: list[dict] = []
    seen: set[str] = set()
    own = list(dict.fromkeys([*operator.authorities.values(),
                              *getattr(operator, "operation_grants", {}).values()]))
    for authority in own:
        try:
            unresolved = operator.store.list_unresolved(operator.actor, authority)
        except ControlError:
            continue
        for receipt in unresolved or []:
            operation_id = str(receipt.get("operationId"))
            # Only this actor's own operations: the store refuses settling another
            # actor's (your decision of 2026-10-26, "Bind each login to its actor").
            if (str(receipt.get("targetId")) != target or operation_id in seen
                    or str(receipt.get("authorityRef")) not in own):
                continue
            seen.add(operation_id)
            settled.append(operator.reconcile(operation_id))
    return settled


def settle_earlier(operator, operation: str, target: str, inputs: dict, *,
                   key: str) -> dict | None:
    """An earlier run's step, under the key that run gave it, settled before a new run
    opens a key of its own for the same step (review finding, Major, R12), so a run's own
    keys never skip what an earlier run left behind:

    - its effect never ran (its bound input, written once the receipt is bound, is
      absent): None, and nothing is replayed or run for it;
    - its receipt applied (succeeded, or unknown and reconciled applied from its target):
      that receipt, the step's result;
    - it left nothing applied (failed, or reconciled not applied): None, so the new key
      may open;
    - its operation is still within its lease (`in-progress`), or its outcome cannot be
      proven (`unknown`): `EffectUnsettled`, and nothing runs beside it.

    The receipt is replayed by its key, so no effect runs again; an unknown or
    interrupted one is reconciled from its target (`Operator.reconcile`), which also
    clears PlatformControl's degraded status for it."""
    token = effect_token(target, input_hash(inputs), key)
    if not input_path(operator.profile.effects_root / target, token).exists():
        # Its effect never ran. If it was bound and stopped before its input was
        # written, its operation is reconciled not applied once its lease has passed.
        reconcile_unresolved(operator, target)
        return None
    receipt = operator.execute(operation, target, inputs, key=key)
    replayed = bool(receipt.get("replayed"))
    if settled_outcome(receipt) in ("unknown", *IN_FLIGHT):
        receipt = {**operator.reconcile(str(receipt["operationId"])), "replayed": replayed}
    outcome = settled_outcome(receipt)
    if outcome == "succeeded":
        return {**receipt, "outcome": "succeeded"}
    if outcome in IN_FLIGHT:
        raise EffectUnsettled("in-progress", receipt)
    if outcome == "unknown":
        raise EffectUnsettled("unknown", receipt)
    return None


# --- the bounded readers --------------------------------------------------------------------


class ReceiptReader:
    """`ledger_cli`'s receipt confirmation: C10's `readReceipt` plus the operation's
    name (`read_receipt_named`), through an evidence-reader authority."""

    def __init__(self, store, *, actor: str, authority: str):
        self.store, self.actor, self.authority = store, actor, authority

    def read(self, operation_id: str) -> Mapping:
        from backend.modules.operations.ledger_cli import ReceiptUnavailable

        try:
            receipt = self.store.call_committed("read_receipt_named",
                                                (self.actor, self.authority, operation_id))
        except ControlError as error:
            raise ReceiptUnavailable(error.code) from None
        if not receipt:
            raise ReceiptUnavailable("no receipt")
        return {
            "receiptId": str(receipt["receiptId"]), "operationId": str(receipt["operationId"]),
            "targetId": str(receipt["targetId"]), "inputHash": str(receipt["inputHash"]),
            "outcome": self.outcome(receipt), "operation": str(receipt["operation"]),
            "recordedAt": None if receipt.get("recordedAt") is None else str(
                receipt["recordedAt"]),
            # The grant the operation was bound under: a decision confirmation requires
            # your in-person grant (your decision of 2026-10-26).
            "authorityRef": str(receipt.get("authorityRef")),
        }

    @staticmethod
    def outcome(receipt: Mapping) -> str:
        """C10's outcome, as reconciliation settled it: U7 keeps an unknown receipt's
        observed state and records the reconciliation beside it, so an unknown outcome
        reconciled from its target reads as what the target showed (BR9.10)."""
        observed = enums.wire_outcome(receipt["operationState"])
        if observed != "unknown":
            return observed
        return RECONCILED.get(str(receipt.get("reconciliationState")), "unknown")


class EvidenceReader:
    """The latest recorded evidence for one target, read-only (the backup agent's
    status for `storage.capacity`, BR6.6)."""

    def __init__(self, store, *, actor: str, authority: str):
        self.store, self.actor, self.authority = store, actor, authority

    def __call__(self, target: str) -> dict | None:
        return self.store.latest_evidence(self.actor, self.authority, target)


class Inspector:
    """PlatformControl's status for `platform.status`, read-only (BR3.5): available
    while the store answers and no unknown outcome is unresolved; degraded otherwise."""

    def __init__(self, store, *, actor: str, authority: str):
        self.store, self.actor, self.authority = store, actor, authority

    def __call__(self) -> dict:
        counts = self.store.status_counts(self.actor, self.authority)
        unresolved = int(counts.get("unresolved", 0))
        return {"outcome": "degraded" if unresolved else "available",
                "unresolved": unresolved, "unknown": int(counts.get("unknown", 0))}

    def open_operations(self, names: Iterable[str]) -> list[dict]:
        """The operations of the named protocols in this reader's target scope that are
        bound but unsettled, or unknown and not yet reconciled (`u8_open_operations`): an
        erasure's backups scope waits while one of them writes a set or a ledger copy
        (L1-2, U8 plan Step 64(g)). A `ControlError` from the store passes through."""
        listed = self.store.call_committed("u8_open_operations",
                                           (self.actor, self.authority, list(names)))
        return [dict(item) for item in (listed or [])]


def readers(profile: U8PlatformProfile, *, password: str | None = None,
            root: Path | None = None, owner_uid: int | None = None):
    """The three readers for the service account, or None while no reader binding is
    provisioned. The realm reads its own store login; production's comes with the
    service account's reader file in the profile root it started under (Step 37).
    `owner_uid` is the binding's owner when another account reads it (the isolation
    check, as root, reads the service account's binding)."""
    binding = profile.reader(root, owner_uid=owner_uid)
    if binding is None:
        return None
    from .platform_profile import store_logins

    login = password or binding.password
    if login is None:
        if profile.kind != "realm":
            return None
        login = profile.realm_password("reader")
    # The service account's own reader login, bound to its actor and holding only the
    # read functions (your decision of 2026-10-26, "Bind each login to its actor").
    store = profile.store(store_logins(profile.kind)["reader"], login)
    options = {"actor": binding.actor, "authority": binding.authority_id}
    return ReceiptReader(store, **options), EvidenceReader(store, **options), Inspector(
        store, **options)


def readers_for(local_profile, *, control: Path | None = None) -> tuple | None:
    """The service account's readers for the profile the host or `ledger_cli` started
    under: production's store (its effects under `control`, the composition's one
    arrangement value, and its reader file in the profile's own root), or the composed
    realm's when the profile's root is the realm's run root and its tool provisioned a
    reader; None otherwise (a diagnostic realm, or a store not yet provisioned), so
    status reads `unknown`."""
    if getattr(local_profile, "is_production", False):
        production = (U8PlatformProfile.production() if control is None
                      else U8PlatformProfile.production(control=control))
        return readers(production, root=Path(local_profile.root))
    if getattr(local_profile, "realm", None) != "service-operations":
        return None
    root = Path(local_profile.root)
    if not (root / "platform-reader.json").exists():
        return None
    return readers(U8PlatformProfile.realm(root))


def realm_facts(profile: U8PlatformProfile, ledger, *, clock: Callable[[], dt.datetime],
                databases: Callable[[], set[str]] | None = None) -> Callable[[], Facts]:
    """The composed realm's facts: its platform profile (`platform/profile.json`), its
    ledger and its instance's database names, read afresh before each effect. The
    databases are the ledger's recorded ones (`recorded_databases`) unless a caller
    names its own lister."""
    names = DatabaseNames("docsuri_u8")
    listed = databases or recorded_databases(ledger)

    def read() -> Facts:
        state = json.loads((profile.state_root / "profile.json").read_bytes())
        return Facts(names, state["mode"], state["admission"], state.get("rehearsalDatabase"),
                     ledger, clock(), listed, profile.labels)

    return read


def realm_operator(profile: U8PlatformProfile, role: str, ledger, *,
                   clock: Callable[[], dt.datetime], **options) -> Operator:
    """The realm's operator (`operator`, both grants) or standing scheduler
    (`scheduler`: `SCHEDULER_GRANTS`' three), from the authorities the realm's tool
    provisioned."""
    from docsuri_ops.platform_control.profile import private_bytes

    from .platform_profile import store_logins

    recorded = json.loads(private_bytes(profile.run_root / "platform-authorities.json"))
    grants = recorded["authorities"]
    if role == "operator":
        held = {"authorities": {enums.CLASS_ROUTINE: grants["operatorRoutine"],
                                enums.CLASS_DESTRUCTIVE: grants["operatorDestructive"]}}
    else:
        held = scheduler_authorities(grants)
    # The realm's login of this role, bound to its actor in the store as production's
    # are (your decision of 2026-10-26, "Bind each login to its actor").
    kind = "operator" if role == "operator" else "scheduler"
    store = profile.store(store_logins("realm")[kind], profile.realm_password(kind))
    return Operator(profile, store, actor=recorded["actors"][role], **held,
                    facts=options.pop("facts", None) or realm_facts(profile, ledger, clock=clock),
                    standing=role != "operator", **options)


LOGIN_ACTORS = {"operator": "operator", "scheduler": "scheduler", "reader": "service"}


def bind_store_logins(provisioner, logins: Mapping[str, str],
                      actors: Mapping[str, str]) -> list[dict]:
    """Each store login bound to its actor in the store (`u8_bind_login`, your decision of
    2026-10-26, "Bind each login to its actor"): the operator's login to you, the
    scheduler's to the scheduler, the reader's to the service account. Idempotent; a
    login already bound to another actor is refused by the store."""
    return [provisioner.call_committed("u8_bind_login", (login, actors[LOGIN_ACTORS[kind]],
                                                          kind))
            for kind, login in logins.items()]


def login_binding_drift(provisioner, logins: Mapping[str, str],
                        actors: Mapping[str, str]) -> list[str]:
    """Each store login read back as the provisioner (`u8_login_bindings`) and compared
    with the binding the installation makes (review findings, Minor, R16 and R17): the
    login must be bound to its actor with its kind, and the reader login must be no
    member of the runtime role. Answers each login kind that differs, in `logins`'
    order (empty when every login is as installed), so an install made before the
    binding, or one whose reader still holds the runtime role, is bound by the
    installer's next apply and refused by its verify until then."""
    held = provisioner.call_committed("u8_login_bindings", (list(logins.values()),))
    held = held if isinstance(held, dict) else {}
    drift = []
    for kind, login in logins.items():
        state = held.get(login) or {}
        if (state.get("bound") is not True or state.get("actor") != actors[LOGIN_ACTORS[kind]]
                or state.get("kind") != kind
                or (kind == "reader" and state.get("runtimeMember") is not False)):
            drift.append(kind)
    return drift


def grant_drift(provisioner, authorities: Mapping[str, str], actor: str) -> list[str]:
    """The scheduler's grants a store holds, compared with `SCHEDULER_GRANTS` (review
    finding, Minor, R15): each provisioned authority is read as the provisioner
    (`read_authority`) and must be the scheduler's, unrevoked, with exactly the scope,
    operations and class `SCHEDULER_GRANTS` names. Answers each grant that is missing
    or differs, in `SCHEDULER_GRANTS`' order (empty when the store holds exactly them),
    so migrate and the installer's verify refuse a store provisioned before a grant
    changed (a routine grant that still holds a restore) instead of reporting it
    verified."""
    drift = []
    for name, (scope, operations, authority_class) in SCHEDULER_GRANTS.items():
        identity = authorities.get(name)
        if not identity:
            drift.append(name)
            continue
        try:
            held = provisioner.read_authority(str(identity))
        except ControlError:
            drift.append(name)
            continue
        if (held.get("actorReference") != actor or held.get("revokedAt") is not None
                or held.get("authorityClass") != authority_class
                or sorted(held.get("targetScope") or []) != sorted(scope)
                or sorted(held.get("permittedOperation") or []) != sorted(operations)):
            drift.append(name)
    return drift


def scheduler_authorities(grants: Mapping[str, str]) -> dict:
    """The scheduler's three grants as `Operator` takes them: the routine and removal
    grants by authority class, and the restore grant for `platform.database.restore`
    alone. A record without the restore grant (one provisioned before it) gives the
    scheduler no restore: the routine grant no longer covers one."""
    restore = grants.get("schedulerRestore")
    return {"authorities": {enums.CLASS_ROUTINE: grants["schedulerRoutine"],
                            enums.CLASS_DESTRUCTIVE: grants["schedulerRemoval"]},
            "operation_grants": {STANDING_RESTORE: restore} if restore else {}}


def refusal_error(refused: PreconditionRefused) -> ControlError:
    return ControlError(CONFLICT, refused.reason, retryable=refused.waiting,
                        details={"messageKey": refused.reason})
