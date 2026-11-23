"""Shared arrangements for the cutover tests (U8 plan Step 34).

- `ledger_with_cutover`: a private ledger with the one CutoverRecord in a chosen state,
  reached only through the machine's own moves.
- `accepted_dry_run`, `final_run`: MigrationRun records in the ledger, through every
  state of their machine, as the migration tool leaves them.
- `decision`: your decision on one of the record's steps (a MaintainerApproval with its
  binding facts), optionally on a shown subject whose digest it binds.
- `provider_decision`: your `provider-sign-in` or `provider-first-effect` decision on the
  subject `cutover decide` renders from the last CutoverRecord (U8 plan Step 107(a)).
- `scheduled_sets`, `verified_restore`: the soak's ledger evidence.
- `complete_inventory`: a consumer inventory with every disposition approved.
"""

from __future__ import annotations

import datetime as dt
import secrets
from uuid import uuid4

from backend.modules.operations.cutover import Cutover, subject_digest
from backend.modules.operations.ledger import utc_text
from backend.u8_policy import SYNTHETIC_OPERATIONS
from tests.u8_service_operations_integration import recovery_flows as rf

TAG = "v2.0.0"


def decision(ledger, step: str, subject_ref: str, *, now: dt.datetime,
             decision: str = "approved", subject: dict | None = None) -> str:
    facts = rf.receipt("platform.decision.record", "decisions", now=now)
    record = {"approvalId": str(uuid4()), "step": step, "subjectRef": subject_ref,
              "subjectDigest": subject_digest(subject) if subject is not None
              else secrets.token_hex(32),
              "decision": decision, "recordedAt": utc_text(now),
              "operatorReceiptRef": facts["receiptId"]}
    ledger.append("maintainer-approval", record, expect_revision=0, receipts=(facts,))
    return record["approvalId"]


_record_decision = decision  # `provider_decision`'s own `decision` argument shadows it


def provider_decision(ledger, provider: str, *, now: dt.datetime, decision: str = "approved",
                      preview_digest: str | None = None) -> tuple[str, dict]:
    """Your `provider-sign-in` or `provider-first-effect` decision, on the subject exactly
    as `cutover decide` renders it from the last CutoverRecord (U8 plan Step 107(a)),
    under subject reference `provider:<name>`; answers the approval id and the subject."""
    from backend.modules.operations.provider_activation import STEPS

    record = ledger.records("cutover-record")[-1]
    step = STEPS[provider]
    subject = {"step": step, "cutoverId": record["cutoverId"],
               "cutoverState": record["state"],
               "cutoverRevision": ledger.revision("cutover-record", record["cutoverId"]),
               "releaseTag": record.get("releaseTag"), "provider": provider}
    if step == "provider-first-effect":
        subject["previewDigest"] = preview_digest
    approval = _record_decision(ledger, step, "provider:" + provider, now=now, decision=decision,
                           subject=subject)
    return approval, subject


def _run(ledger, kind: str, states: tuple[str, ...], *, now: dt.datetime, **fields) -> dict:
    record = {"runId": str(uuid4()), "kind": kind,
              "target": "rehearsal" if kind == "dry" else "production",
              "toolCommit": "a" * 40, "decisionsDigest": secrets.token_hex(32),
              "state": "preparing", "startedAt": utc_text(now), **fields}
    ledger.append("migration-run", record, expect_revision=0)
    for revision, state in enumerate(states, start=1):
        record = {**record, "state": state}
        if state == "accepted":
            record["acceptedAt"] = utc_text(now)
        if state in ("accepted", "rejected", "failed"):
            record["finishedAt"] = utc_text(now)
        ledger.append("migration-run", record, expect_revision=revision)
    return record


def accepted_dry_run(ledger, *, now: dt.datetime, database: str | None = None,
                     **fields) -> dict:
    """An accepted dry run. With `database`, it carries the target copy the migration
    tool records when the run starts copying (`targetCopyId`, a rehearsal-database copy
    naming that database), which BR9.2 compares with the profile's rehearsal database."""
    from backend.modules.operations.retained_copies import RetainedCopies

    if database is None:
        return _run(ledger, "dry",
                    ("copying", "importing", "verifying", "reported", "accepted"),
                    now=now, **fields)
    run_id = str(uuid4())
    copy = RetainedCopies(ledger, SYNTHETIC_OPERATIONS, clock=lambda: now).record(
        "rehearsal-database", f"run:{run_id}", [f"database/{database}"])
    return _run(ledger, "dry", ("copying", "importing", "verifying", "reported", "accepted"),
                now=now, runId=run_id, targetCopyId=copy["copyId"], **fields)


def final_run(ledger, *, now: dt.datetime, state: str = "accepted", **fields) -> dict:
    """A final run in `state`; `fields` adds its other fields (`runId`,
    `snapshotCopyId`)."""
    path = {"reported": ("copying", "importing", "verifying", "reported"),
            "accepted": ("copying", "importing", "verifying", "reported", "accepted"),
            "rejected": ("copying", "importing", "verifying", "reported", "rejected"),
            "importing": ("copying", "importing")}[state]
    return _run(ledger, "final", path, now=now, **fields)


def accept(ledger, run: dict, *, now: dt.datetime) -> dict:
    """Your decision accepted a reported run (the migration tool's `decide`)."""
    record = {**run, "state": "accepted", "acceptedAt": utc_text(now),
              "finishedAt": utc_text(now)}
    ledger.append("migration-run", record,
                  expect_revision=ledger.revision("migration-run", run["runId"]))
    return record


def first_live(ledger, *, now: dt.datetime) -> dict:
    """The switch's first live backup, passed, as Workflow 5 records it."""
    facts = rf.receipt(now=now)
    backup = str(uuid4())
    revision = sum(1 for item in ledger.records("backup-set") if item["environment"] == "live")
    record = {
        "backupId": backup, "environment": "live", "revision": revision + 1,
        "trigger": "first-live", "takenAt": utc_text(now), "checksum": "c" * 64,
        "sizeBytes": 1, "sourceDatabaseBytes": 1,
        "location": f"archives/live-set-20261022T120000-{backup}.archive",
        "databaseIncarnation": "docsuri_u8:1", "stagingLocation": f"staging/{backup}",
        "retainUntil": utc_text(now + dt.timedelta(days=14)), "integrity": "passed",
        "operatorReceiptRef": facts["receiptId"]}
    ledger.append("backup-set", record, expect_revision=0, receipts=(facts,))
    return record


def machine(ledger, clock, incidents=None) -> Cutover:
    return Cutover(ledger, SYNTHETIC_OPERATIONS, clock=clock, incidents=incidents)


def rehearsing(ledger, clock) -> tuple[Cutover, dict]:
    """A cutover rehearsing: begun, a dry run accepted, the verification passed."""
    cutover = machine(ledger, clock)
    cutover.begin(TAG)
    run = accepted_dry_run(ledger, now=clock())
    cutover.dry_run_accepted(run["runId"])
    cutover.verification_passed(uuid4(), TAG)
    return cutover, cutover.start_soak()


def scheduled_sets(ledger, start: dt.datetime, days: int, *, integrity: str = "passed",
                   database: str = "docsuri_u8") -> list[dict]:
    """One scheduled rehearsal set a day, each of `database` (its incarnation names it)."""
    sets = []
    for day in range(days):
        moment = start + dt.timedelta(days=day, hours=1)
        record = rf.set_record(ledger, environment="rehearsal", integrity=integrity, now=moment,
                               database=database)
        sets.append(record)
    return sets


def verified_restore(ledger, backup: dict, *, now: dt.datetime,
                     environment: str = "rehearsal") -> dict:
    record = {"verificationId": str(uuid4()), "environment": environment,
              "backupId": backup["backupId"], "startedAt": utc_text(now),
              "finishedAt": utc_text(now), "registerHeadSequence": 0,
              "registerHeadDigest": "0" * 64, "integrity": "passed",
              "erasedOwnersSurviving": 0, "result": "verified",
              "evidenceRef": "verification:fixture", "scratchRemovedAt": utc_text(now)}
    ledger.append("restore-verification", record, expect_revision=0)
    return record


def complete_inventory(ledger, *, now: dt.datetime, approved: bool = True,
                       seconds: int = 14 * 86400) -> dict:
    """A complete inventory whose window of `seconds` (14 days by default) ends at
    `now`."""
    consumer = {"clientRef": "client-fixture", "routesUsed": ["/api/search"],
                "source": "observed"}
    if approved:
        consumer.update(disposition="moves-with-v2", approvalId=str(uuid4()))
    record = {"inventoryId": str(uuid4()),
              "observedFrom": utc_text(now - dt.timedelta(seconds=seconds)),
              "observedUntil": utc_text(now), "consumers": [consumer], "complete": True}
    ledger.append("consumer-inventory", record, expect_revision=0)
    return record


def final_snapshot(ledger, run_id: str, *, approval: str, dispose_after: dt.datetime,
                   now: dt.datetime) -> dict:
    """A completed v1-final-snapshot copy of a final run, with its three
    `backup-volume:<copyId>:<part>` locations, as the migration tool records it."""
    from backend.modules.operations.retained_copies import RetainedCopies

    copies = RetainedCopies(ledger, SYNTHETIC_OPERATIONS, clock=lambda: now)
    copy_id = str(uuid4())
    copies.record("v1-final-snapshot", f"run:{run_id}",
                  [f"backup-volume:{copy_id}:{part}" for part in ("database", "index", "objects")],
                  dispose_after=dispose_after, approval_id=approval, copy_id=copy_id)
    return copies.complete(copy_id, checksum="d" * 64)


def switching(ledger, clock) -> tuple[Cutover, dict]:
    """A cutover switching: a clean soak on ledger evidence, BR9.2 holding, your
    decision approving the start."""
    cutover, record = rehearsing(ledger, clock)
    start = dt.datetime.fromisoformat(record["soakStartedAt"].replace("Z", "+00:00"))
    sets = scheduled_sets(ledger, start, 7)
    verified_restore(ledger, sets[0], now=start + dt.timedelta(days=1))
    clock.advance(7 * 86400 + 60)
    cutover.evaluate_soak()
    record = cutover.check_ready([])
    approval = decision(ledger, "switch-start", record["cutoverId"], now=clock())
    return cutover, cutover.approve_start(approval, [])
