"""BR9.2's evaluation: the switch starts only when every precondition holds (U8 plan Step
33; BR9.2, BR9.3, BR9.11, BR9.16, BR6.6, BR6.12, reliability-design § 12).

`missing` reads the ledger and the evidence the operator tool can see and names every
precondition that does not hold, in BR9.2's order, so the cutover stays in rehearsing or
ready-to-switch with the missing item named:

1. `verification-not-passed`: the whole-application verification passed on the exact
   release tag (BR10.5); `release-not-linked`: that tag is the release the links point
   to, where the links are read (production);
2. `soak-not-clean`: the soak ran clean for its full period on that tag (BR9.3);
3. `dry-run-not-accepted`, `dry-run-not-current`, `misfits-undecided`,
   `rehearsal-database-not-the-accepted-runs`: the latest dry run's report is accepted,
   that run used the decisions current now, every misfit kind and reason BR8.9 requires
   is decided, and the profile's rehearsal database is the database that run imported
   into (its target copy), so the soak's evidence and the restore verification are
   earned on the accepted run's own database;
4. `rehearsal-verification-missing`: a restore verification of the rehearsal database
   the profile names, with result verified (BR4.5);
5. `inventory-incomplete`: the consumer inventory is complete with every disposition
   approved (BR9.11); `inventory-window-short`: it covers at least the consumer window
   (14 days); `inventory-not-recent`: it ends within 24 hours before the switch's check,
   and not after it (your decision of 2026-11-01, L1-21; `cutover.inventory_gap`);
6. `incident-unresolved`: no incident in either environment, the abort's included;
7. v1 runs from a fixed checkout and its restart rehearsal passed within its window
   (`restart-rehearsal-missing`, `-void`, `-expired`, `v1-checkout-not-fixed`, BR9.16);
8. `backup-volume-unfit`: the volume check passes from both sides with free space of at
   least the backup floor plus the sizes the accepted dry run measured for its snapshot
   and for a backup of its rehearsal database (BR6.6);
9. the latest runtime isolation evidence passed within its freshness bound (the gate's
   own reason, BR6.12);
10. `final-snapshot-awaiting-date`: after an abort, the aborted attempt's open, completed
    final snapshot is dated no later than 30 days after the abort by your disposal-date
    decision (`cutover date-final-snapshot`; your decision of 2026-11-01, L1-66, "Start
    waits"; `awaiting_final_snapshot`). This key amends BR9.2's list.

The last, your decision approving the start, is the machine's (`Cutover.approve_start`).
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable
from dataclasses import dataclass

from backend.modules.operations.cutover import inventory_gap, rehearsal_current, soak_verdict
from backend.modules.operations.migration_records import MigrationRuns


@dataclass
class SwitchEvidence:
    """What the operator tool reads beside the ledger."""

    verification: Callable[[str], dict | None]
    v1_checkout: Callable[[], dict | None]
    rehearsal_fingerprint: Callable[[str], str | None]
    agent_status: Callable[[], dict]
    service_volume: Callable[[], str]
    isolation: object
    rehearsal_database: Callable[[], str | None]
    # The tag of the release the links point to (production's `release.linked_tag`);
    # None where there are no release links (the composed realm). Wired, a record whose
    # tag is not the linked release's meets no precondition (1) (review finding, Major,
    # R13): a verification recorded for one release never starts a switch on another.
    linked_release: Callable[[], str | None] | None = None


def linked_differs(record: dict, evidence: SwitchEvidence | None) -> str | None:
    """The linked release's tag when it is not the record's (or cannot be read), else
    None; always None where no reader is wired."""
    reader = getattr(evidence, "linked_release", None)
    if reader is None:
        return None
    linked = reader()
    return None if linked == record["releaseTag"] else (linked or "none")


def _verification(record: dict, evidence: SwitchEvidence) -> str | None:
    run = record.get("verificationRunId")
    found = None if run is None else evidence.verification(run)
    if found is None or found.get("passed") is not True or (
        found.get("releaseTag") != record["releaseTag"]
    ):
        return "verification-not-passed"
    if linked_differs(record, evidence) is not None:
        return "release-not-linked"
    return None


def _dry_run(ledger, record: dict) -> list[str]:
    from backend.modules.operations.migration.misfits import Decisions

    runs = MigrationRuns(ledger)
    accepted = runs.latest_accepted("dry")
    if accepted is None or accepted["runId"] != record.get("acceptedDryRunId"):
        return ["dry-run-not-accepted"]
    gaps = []
    if not runs.dry_run_current():
        gaps.append("dry-run-not-current")
    if Decisions.from_ledger(ledger).undecided(runs.required_pairs()):
        gaps.append("misfits-undecided")
    return gaps


def _accepted_database(ledger, record: dict, database: str | None) -> str | None:
    """The accepted dry run's own database is the one the profile names: the run's
    target copy (recorded when the run started copying) names it. A run without one, or
    a profile on another database, is refused."""
    run = ledger.get("migration-run", record.get("acceptedDryRunId"))
    if run is None:
        return None  # `dry-run-not-accepted` already names it
    copy = ledger.get("retained-copy", run.get("targetCopyId")) if run.get(
        "targetCopyId") else None
    locations = [] if copy is None else [item.removeprefix("database/")
                                         for item in copy.get("locations", ())
                                         if item.startswith("database/")]
    if database is None or locations != [database]:
        return "rehearsal-database-not-the-accepted-runs"
    return None


def _rehearsal_verification(ledger, database: str | None) -> str | None:
    if database is not None:
        for item in ledger.records("restore-verification"):
            if item["environment"] != "rehearsal" or item.get("result") != "verified":
                continue
            backup = ledger.get("backup-set", item["backupId"])
            if backup is not None and str(backup["databaseIncarnation"]).split(":", 1)[
                0
            ] == database:
                return None
    return "rehearsal-verification-missing"


def _volume_room(ledger, record: dict, evidence: SwitchEvidence, policy,
                 database: str | None) -> str | None:
    status = evidence.agent_status() or {}
    if not status.get("available") or evidence.service_volume() == "unavailable":
        return "backup-volume-unfit"
    run = ledger.get("migration-run", record.get("acceptedDryRunId"))
    snapshot = None if run is None or not run.get("snapshotCopyId") else ledger.get(
        "retained-copy", run["snapshotCopyId"])
    # The accepted run's snapshot counts as the sum of its parts' sizes (U8 plan Step
    # 70(b)); a copy with no part sizes counts 0.
    measured = sum(int(size) for size in ((snapshot or {}).get("partSizes") or {}).values())
    sets = [item for item in ledger.records("backup-set")
            if item["environment"] == "rehearsal"
            and str(item["databaseIncarnation"]).split(":", 1)[0] == database]
    measured += max((int(item["sizeBytes"]) for item in sets), default=0)
    if int(status.get("freeBytes", 0)) < policy.backup_volume_floor_bytes + measured:
        return "backup-volume-unfit"
    return None


def _parse(text: str) -> dt.datetime:
    return dt.datetime.fromisoformat(text.replace("Z", "+00:00"))


def awaiting_final_snapshot(ledger, record: dict, policy) -> str | None:
    """The aborted attempt's final snapshot that still waits for your disposal-date
    decision, by its copy id, else None (U8 plan Step 70(a), L1-66): the record holds
    `abortStartedAt`, the copy its `finalSnapshotCopyId` names is open and completed,
    and it is dated later than `abortStartedAt` plus `final_snapshot_disposal_seconds`.
    The same lookup admits `decide("disposal-date")`, so the key holds only while the
    decision can be taken."""
    from .decide import aborted_final_snapshot

    copy = aborted_final_snapshot(ledger, record)
    if copy is None:
        return None
    limit = _parse(record["abortStartedAt"]) + dt.timedelta(
        seconds=policy.final_snapshot_disposal_seconds)
    return copy["copyId"] if _parse(copy["disposeAfter"]) > limit else None


def missing(ledger, record: dict, evidence: SwitchEvidence, policy,
            now: dt.datetime) -> list[str]:
    """Every BR9.2 precondition that does not hold at `now` (the switch's check instant
    when the start asks), named."""
    gaps: list[str] = []
    found = _verification(record, evidence)
    if found:
        gaps.append(found)
    clean, _ = soak_verdict(ledger, record, now)
    if not clean or not record.get("soakClean"):
        gaps.append("soak-not-clean")
    dry_run = _dry_run(ledger, record)
    gaps.extend(dry_run)
    database = evidence.rehearsal_database()
    if "dry-run-not-accepted" not in dry_run:
        found = _accepted_database(ledger, record, database)
        if found:
            gaps.append(found)
    found = _rehearsal_verification(ledger, database)
    if found:
        gaps.append(found)
    found = inventory_gap(ledger.get("consumer-inventory", record.get("consumerInventoryId")),
                          policy=policy, switch_at=now)
    if found:
        gaps.append(found)
    if any(item["state"] != "resolved" for item in ledger.records("service-incident")):
        gaps.append("incident-unresolved")
    checkout = evidence.v1_checkout()
    recorded = evidence.rehearsal_fingerprint(record["cutoverId"])
    reason = rehearsal_current(
        record, now, window_seconds=policy.restart_rehearsal_seconds,
        commit=None if checkout is None else checkout.get("commit"),
        fingerprint_matches=checkout is not None and recorded is not None
        and checkout.get("fingerprint") == recorded,
    )
    if reason:
        gaps.append(reason)
    found = _volume_room(ledger, record, evidence, policy, database)
    if found:
        gaps.append(found)
    reading = evidence.isolation.read()
    if not reading.passed:
        gaps.append(reading.reason)
    if awaiting_final_snapshot(ledger, record, policy) is not None:
        gaps.append("final-snapshot-awaiting-date")
    return gaps
