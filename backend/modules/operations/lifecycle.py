"""ServiceOperations' lifecycle participant (U8 plan Step 17; BR2.5, BR2.6, BR4.6).

It answers two scopes for every lifecycle request, under AccountAccess's live,
current-generation ticket (checked through `accounts.lifecycle_effect_action` as the
operations login), and keeps its evidence in the operations ledger as
`lifecycle-evidence`, once per request and scope:

- **`backups` (BR2.5).** While a live backup schedule with its retention runs and at
  least one live set has passed, the evidence is the number of undisposed backup sets
  and retained copies that may hold the owner's data, and the latest date by which each
  is gone: a set's `retainUntil` (a staging file left behind: the day after its write);
  a copy's approved date, or an event copy's backstop, both its `disposeAfter`; for a
  copy on the internal disk, that date plus 24 hours (security-design § 6.7). A set the
  retention floor holds has no date, so the scope waits. A copy retired with a lost
  volume is listed as retired. Every undisposed set and copy is counted, rehearsal and
  v1 copies included: the count may name copies that never held this owner's data, and
  never omits one that did.
- **`restore_enforcement` (BR2.6).** For an erase, the owner's tombstone is appended on
  the scope's first claim; the evidence comes only from a live verified
  RestoreVerification whose register head is at or above that tombstone, and records
  that head after checking that the register still reaches it. A withdraw or a
  reactivate needs no tombstone.

A scope that cannot have evidence yet waits without spending AccountAccess's claim
attempts: `GatedLifecycle` claims a scope only once its participant is `ready`, so a
backup or a restore verification that is hours away never exhausts the scope.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable, Mapping
from uuid import NAMESPACE_URL, uuid5

from psycopg.types.json import Jsonb

from .ledger import Ledger, utc_text
from .tombstones import Tombstones

OWNER = "operations"
PARTICIPANT = "ServiceOperations"
SCOPES = ("backups", "restore_enforcement")
KIND = "lifecycle-evidence"
# Retained copies that live on the internal disk: databases in v2's instance and v1's
# stores; their dates carry +24 hours for the disk's local snapshots.
INTERNAL_DISK_KINDS = frozenset({
    "rehearsal-database", "import-database", "scratch-restore", "v1-stores",
})
# The databases that keep the disk's 24-hour tail after their removal (NFR3.7).
TAILED_AFTER_REMOVAL = frozenset({"rehearsal-database", "import-database", "scratch-restore"})
# The operations an erasure's backups scope waits for while they write (L1-2).
IN_FLIGHT_OPERATIONS = ("platform.database.backup", "platform.ledger.copy")
# At most this many items in each list, within the ledger's entry bound.
EVIDENCE_ITEMS = 256
RETAINED_REASON = "backups-retained-until-disposal"
ENFORCED_REASON = "restore-enforcement-verified"
NO_TOMBSTONE_REASON = "no-tombstone-needed"


class EvidencePending(RuntimeError):
    """The scope cannot have evidence yet; the message is a fixed reason key."""


def _parse(text: str) -> dt.datetime:
    return dt.datetime.fromisoformat(text.replace("Z", "+00:00"))


def _nothing_open(names) -> list:
    return []


def _no_status(target: str) -> None:
    return None


def _reader_error() -> type[Exception]:
    from docsuri_ops.platform_control.errors import ControlError

    return ControlError


def _in_flight(ledger: Ledger, open_operations) -> None:
    """The scope waits while a set or a ledger copy is being written (L1-2, U8 plan Step
    64(g)): a `backup.create` of either environment `running` or `unknown`, or a
    `platform.database.backup` or `platform.ledger.copy` bound but unsettled or unknown
    and not yet reconciled (a lone copy counts)."""
    if any(item["operation"] == "backup.create" and item["state"] in ("running", "unknown")
           for item in ledger.records("recovery-request")):
        raise EvidencePending("backup-in-flight")
    if open_operations is None:
        raise EvidencePending("platform-reader-unbound")
    try:
        listed = open_operations(IN_FLIGHT_OPERATIONS)
    except _reader_error():
        raise EvidencePending("platform-reader-unavailable") from None
    if listed:
        raise EvidencePending("backup-in-flight")


def _retired_volumes(ledger: Ledger, retired: list[dict]) -> list[dict]:
    """One group per retired volume (BR2.5): the retirement decision's `subjectRef`,
    found through each closing version's `retirementReceiptRef`; a record retired without
    one is grouped with `volume` null."""
    volumes = {item["operatorReceiptRef"]: item["subjectRef"]
               for item in ledger.records("maintainer-approval")
               if item.get("step") == "backup-volume-retirement"}
    groups: dict[str | None, dict] = {}
    for item in retired:
        volume = volumes.get(item.get("retirementReceiptRef"))
        group = groups.setdefault(volume, {"volume": volume, "retiredAt": item[
            "retiredWithVolumeAt"], "count": 0})
        group["count"] += 1
        group["retiredAt"] = max(group["retiredAt"], item["retiredWithVolumeAt"])
    return list(groups.values())


def _volume_files(ledger: Ledger, agent_status, status_required: bool,
                  now: dt.datetime) -> tuple[list[dict], bool]:
    """The volume files the ledger records nothing for, from the agent's latest usable
    status (`backup-volume`, Step 66(f)), and whether such a status was recorded. Without
    a usable one, production holds the scope and a realm names no volume file."""
    if agent_status is None:
        raise EvidencePending("platform-reader-unbound")
    try:
        status = agent_status("backup-volume")
    except _reader_error():
        raise EvidencePending("platform-reader-unavailable") from None
    observations = (status or {}).get("observations") or {}
    stale = status is not None and (
        _parse(str(status["observedAt"])) + dt.timedelta(seconds=int(status["maxAgeSeconds"]))
        < now)
    usable = (status is not None and not stale and observations.get("catalogue") == "intact"
              and observations.get("deletionAllowed") is True
              and "unrecordedCount" in observations)
    if not usable:
        if status_required:
            raise EvidencePending("agent-status-stale" if stale else "agent-status-unrecorded")
        return [], False
    listed = list(observations.get("unrecordedFiles") or [])
    if int(observations["unrecordedCount"]) > len(listed):
        raise EvidencePending("volume-files-over-bound")
    recorded = {item["backupId"] for item in ledger.records("backup-set")}
    recorded |= {item["ledgerCopyId"] for item in ledger.records("ledger-copy")}
    recorded |= {item["copyId"] for item in ledger.records("retained-copy")}
    files = []
    for entry in listed:
        if entry.get("recordId") in recorded:
            continue
        if not entry.get("disposeAfter"):
            raise EvidencePending("volume-file-undated")
        files.append({"recordId": str(entry["recordId"]), "kind": "volume-file",
                      "goneAt": utc_text(_parse(str(entry["disposeAfter"])))})
    return files, True


def backups_evidence(ledger: Ledger, policy, *, schedule_active: bool,
                     open_operations=_nothing_open, agent_status=_no_status,
                     status_required: bool = False) -> dict:
    """BR2.5's evidence from the ledger's BackupSets and RetainedCopies, naming each
    undisposed item with its date and each retired volume (NFR3.14, L1-51), and the
    volume files the ledger records nothing for, from the agent's latest status. It
    waits while a set or a ledger copy is being written (L1-2). Its readers default to
    nothing in flight and no status."""
    if not schedule_active:
        raise EvidencePending("backup-schedule-inactive")
    # The in-flight check comes before any set, copy or identity read (review fix, batch
    # 4): a set recorded between a read and the check is then in the reads that follow.
    _in_flight(ledger, open_operations)
    sets = ledger.records("backup-set")
    if not any(item["environment"] == "live" and item["integrity"] == "passed"
               for item in sets):
        raise EvidencePending("no-live-backup-passed")
    now = ledger.clock()
    undisposed: list[dict] = []
    retired: list[dict] = []
    counted = 0
    staging_tail = dt.timedelta(seconds=policy.staging_file_backstop_seconds)
    internal_tail = dt.timedelta(seconds=policy.internal_disk_tail_seconds)
    for item in sets:
        if "retiredWithVolumeAt" in item:
            retired.append(item)
            continue
        if "disposedAt" in item:
            if "stagingRemovedAt" not in item:  # a staging file the write left behind
                counted += 1
                undisposed.append({"recordId": item["backupId"], "kind": "staging-file",
                                   "goneAt": utc_text(_parse(item["takenAt"]) + staging_tail)})
            continue
        if "heldByFloorSince" in item:
            raise EvidencePending("last-backup-held")
        counted += 1
        undisposed.append({"recordId": item["backupId"], "kind": "backup-set",
                           "goneAt": item["retainUntil"]})
    copies = 0
    for item in ledger.records("retained-copy"):
        gone = _copy_gone_at(item, internal_tail, now)
        if gone is RETIRED:
            retired.append(item)
            continue
        if gone is None:
            continue
        copies += 1
        undisposed.append({"recordId": item["copyId"], "kind": item["kind"],
                           "goneAt": utc_text(gone)})
    files, status_recorded = _volume_files(ledger, agent_status, status_required, now)
    undisposed.extend(files)
    # Each retired volume's group also counts the ledger copies closed with it (BR2.5,
    # U8 plan Step 65(e): the set, its copy and the snapshot); `retiredCounted` keeps its
    # built count of sets and retained copies.
    copies_retired = [item for item in ledger.records("ledger-copy")
                      if "retiredWithVolumeAt" in item and "disposedAt" not in item]
    groups = _retired_volumes(ledger, retired + copies_retired)
    if len(undisposed) > EVIDENCE_ITEMS or len(groups) > EVIDENCE_ITEMS:
        raise EvidencePending("backups-evidence-over-bound")
    evidence = {"setsCounted": counted, "copiesCounted": copies,
                "retiredCounted": len(retired), "undisposed": undisposed,
                "retired": groups, "unrecordedCounted": len(files),
                "agentStatusRecorded": status_recorded}
    if undisposed:
        evidence["latestGoneAt"] = utc_text(max(_parse(entry["goneAt"])
                                                for entry in undisposed))
    return evidence


RETIRED = object()


def _copy_gone_at(item: dict, internal_tail: dt.timedelta, now: dt.datetime):
    """A retained copy's date in the evidence (NFR3.7, U8 plan Step 64(e)): `RETIRED` for
    one retired with its volume; None when it no longer counts. An undisposed copy on the
    internal disk is gone 24 hours after its `disposeAfter`; a disposed rehearsal,
    import or scratch database 24 hours after its removal, while that is later than now;
    `v1-stores` stops counting once disposed of in person (L1-43); the volume kinds carry
    no tail."""
    if "returnedToServiceAt" in item:
        return None
    if "retiredWithVolumeAt" in item and "disposedAt" not in item:
        return RETIRED
    if "disposedAt" in item:
        if item["kind"] in TAILED_AFTER_REMOVAL:
            gone = _parse(item["disposedAt"]) + internal_tail
            return gone if gone > now else None
        return None
    moment = _parse(item["disposeAfter"])
    return moment + internal_tail if item["kind"] in INTERNAL_DISK_KINDS else moment


def covering_verification(ledger: Ledger, tombstone: dict) -> dict | None:
    """A live verified RestoreVerification whose register head reaches the tombstone."""
    covering = [
        item for item in ledger.records("restore-verification")
        if item["environment"] == "live" and item.get("result") == "verified"
        and item["registerHeadSequence"] >= tombstone["sequence"]
    ]
    return min(covering, key=lambda item: item["registerHeadSequence"], default=None)


class OperationsLifecycleParticipant:
    scopes = SCOPES

    def __init__(self, transactions, ledger: Ledger, policy, *,
                 schedule_active: Callable[[], bool], open_operations, agent_status,
                 status_required: bool = False):
        """`open_operations` is the platform part's `Inspector.open_operations` and
        `agent_status` its evidence reader, each None when the platform part binds no
        reader; `status_required` holds the scope without a usable agent status
        (production, where the standing job records one every 5 minutes)."""
        self.transactions, self.ledger, self.policy = transactions, ledger, policy
        self.tombstones = Tombstones(ledger)
        self.schedule_active = schedule_active
        self.open_operations, self.agent_status = open_operations, agent_status
        self.status_required = status_required

    def _backups(self) -> dict:
        return backups_evidence(self.ledger, self.policy, schedule_active=self.schedule_active(),
                                open_operations=self.open_operations,
                                agent_status=self.agent_status,
                                status_required=self.status_required)

    @staticmethod
    def evidence_ref(request_id, scope: str) -> str:
        return str(uuid5(NAMESPACE_URL, f"docsuri-lifecycle-evidence:{request_id}:{scope}"))

    # --- readiness ------------------------------------------------------------------

    def ready(self, request: dict, scope: str) -> bool:
        """Claim only a first attempt or one that can have evidence now."""
        prior = self.ledger.get(KIND, (str(request["id"]), scope))
        if prior is not None and prior["state"] == "complete":
            return True
        if scope == "backups":
            if prior is None:
                return True
            try:
                self._backups()
                return True
            except EvidencePending:
                return False
        if request["action"] != "erase":
            return True
        tombstone = self.tombstones.by_request(request["id"])
        return tombstone is None or covering_verification(self.ledger, tombstone) is not None

    # --- the effect ---------------------------------------------------------------------

    def _fence(self, ticket: dict) -> str:
        """AccountAccess's guard: the ticket is live and current, as this owner."""
        return self.transactions.run(OWNER, lambda conn: conn.execute(
            "SELECT accounts.lifecycle_effect_action(%s,%s,%s,%s,%s,%s,%s) AS action",
            (ticket["request_id"], ticket["account_id"], PARTICIPANT, ticket["scope"],
             ticket["generation"], Jsonb(ticket["policy_ref"]), ticket["manifest_revision"]),
        ).fetchone()["action"])

    def apply(self, ticket: dict) -> dict:
        from backend.control_worker import PendingLifecycleEvidence

        if ticket["participant"] != PARTICIPANT or ticket["scope"] not in SCOPES:
            raise PermissionError("unregistered lifecycle participant scope")
        action = self._fence(ticket)
        request, scope = str(ticket["request_id"]), ticket["scope"]
        prior = self.ledger.get(KIND, (request, scope))
        if prior is not None and prior["state"] == "complete":
            return _result(prior)
        try:
            evidence = self._evidence(ticket, action)
        except EvidencePending as pending:
            self._record(request, scope, action, {"state": "waiting",
                                                  "reasonKey": str(pending)})
            raise PendingLifecycleEvidence(str(pending)) from None
        record = self._record(request, scope, action, {
            "state": "complete", "evidenceRef": self.evidence_ref(request, scope), **evidence,
        })
        return _result(record)

    def _evidence(self, ticket: dict, action: str) -> dict:
        if ticket["scope"] == "backups":
            return {"reasonKey": RETAINED_REASON, **self._backups()}
        if action != "erase":
            return {"reasonKey": NO_TOMBSTONE_REASON}
        tombstone = self.tombstones.claim(ticket["account_id"], ticket["request_id"])
        verification = covering_verification(self.ledger, tombstone)
        if verification is None:
            raise EvidencePending("restore-verification-pending")
        recorded = {"sequence": verification["registerHeadSequence"],
                    "digest": verification["registerHeadDigest"]}
        self.tombstones.verify(recorded)
        evidence = {
            "reasonKey": ENFORCED_REASON, "tombstoneSequence": tombstone["sequence"],
            "registerHeadSequence": recorded["sequence"],
            "registerHeadDigest": recorded["digest"],
            "verificationId": verification["verificationId"],
            "verificationStartedAt": verification["startedAt"],
        }
        if "finishedAt" in verification:
            evidence["verificationFinishedAt"] = verification["finishedAt"]
        # L1-42: a covering verification that started more than a day after the
        # tombstone carries the late-start mark.
        limit = _parse(tombstone["appendedAt"]) + dt.timedelta(
            seconds=self.policy.erasure_verification_start_seconds)
        if _parse(verification["startedAt"]) > limit:
            evidence["verificationStartLate"] = True
        return evidence

    def _record(self, request: str, scope: str, action: str, fields: dict) -> dict:
        record = {"requestId": request, "scope": scope, "action": action,
                  "recordedAt": utc_text(self.ledger.clock()), **fields}

        def step(view):
            current = view.get(KIND, (request, scope))
            if current is not None and current["state"] == "complete":
                return current
            if (
                current is not None and fields["state"] == "waiting"
                and current["reasonKey"] == fields["reasonKey"]
            ):
                return current
            view.append(KIND, record, expect_revision=view.revision(KIND, (request, scope)))
            return record

        return self.ledger.atomic(step)


def _result(record: dict) -> dict:
    """The worker's acknowledgement; the backups scope's latest date is reported with its
    reason key, so AccountAccess shows that part retained by policy until then (your
    decision of 2026-10-22, BR2.5)."""
    result = {"evidenceRef": record["evidenceRef"], "reasonKey": record["reasonKey"],
              "disposition": "complete"}
    if record["reasonKey"] == RETAINED_REASON and "latestGoneAt" in record:
        result["retainedUntil"] = _parse(record["latestGoneAt"])
    return result


class GatedLifecycle:
    """AccountAccess's lifecycle service as the control worker sees it: a scope is
    claimed only once its participant says it is `ready`, so a participant waiting for
    evidence never spends the scope's finite claim attempts."""

    def __init__(self, service, participants: Mapping | None = None):
        self.service = service
        self.participants: Mapping = participants or {}

    @property
    def manifest(self):
        return self.service.manifest

    @property
    def revision(self):
        return self.service.revision

    def __getattr__(self, name):
        return getattr(self.service, name)

    def _request(self, request_id) -> dict | None:
        return self.service.transactions.run("accounts", lambda conn: conn.execute(
            "SELECT id,account_id,action FROM accounts.lifecycle_request WHERE id=%s",
            (request_id,),
        ).fetchone())

    def claim(self, request_id, participant: str, scope: str) -> dict:
        ready = getattr(self.participants.get(participant), "ready", None)
        if ready is not None:
            request = self._request(request_id)
            if request is not None and not ready(request, scope):
                raise ValueError("lifecycle participant not ready")
        return self.service.claim(request_id, participant, scope)

    def acknowledge(self, ticket: dict, *, evidence, reason: str, **options) -> dict:
        return self.service.acknowledge(ticket, evidence=evidence, reason=reason, **options)
