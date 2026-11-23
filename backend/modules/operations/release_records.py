"""Release records in the operations ledger (U8 plan Step 37; cicd-pipeline § 5.1 step 12,
§ 5.1 "One at a time", § 6, BR4.4, BR6.5).

An install is recorded as a ReleaseRecord from its preflight: `installing` holds the live
environment's production-affecting exclusion, like a production restore, so no backup,
verification or disposal pass starts during it, and no second install. It ends
`installed` with the backup set, the arrangement version, the VerificationRun and each
step's time; `failed` when a migration or an apply failed and the current release was kept;
or `switched-back` when v2 was not ready within 10 minutes. A later rollback is
`rolling-back` while it runs, which holds the same exclusion, and ends `rolled-back` (or
`installed` again when it stopped before the links were switched).

`exclusion_blocker` answers why an install or a release rollback may not start now: a
production restore, a switch, an abort or a cutover rollback holds the exclusion, or
another install or release rollback does.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable

from .errors import OperationsError
from .ledger import utc_text

KIND = "release-record"
LIVE_EXCLUSION = ("switching", "aborting", "rolling-back")
# A ReleaseRecord in one of these states holds the live exclusion (BR4.4).
HOLDING = {"installing": "release-install-active", "rolling-back": "release-rollback-active"}


# The reason keys a record carries when its run left something for `docsuri-release
# recover`: v2 may be running a release the links no longer name, a role may still run
# that a stop could not stop, or the address may not be where the record says.
# `recover-required` (the person's decision of 2026-10-26, "Stay put, v2 stopped"): a
# failed probe whose switch back found the kept release closed (its record rolled-back,
# failed or switched-back), so the links stayed on the failed release with v2 stopped;
# `recover` answers what remains for it and changes nothing.
RECOVERABLE = frozenset({"release-interrupted", "route-back-failed", "switch-back-failed",
                         "release-rollback-failed", "resume-failed", "recover-required"})
# A kept release in one of these states is closed: never switched back to, never rolled
# back to (the person's decision of 2026-10-26, "Stay put, v2 stopped").
CLOSED = ("rolled-back", "failed", "switched-back")


def recover_blocker(reader) -> str | None:
    """`recover-required` while any ReleaseRecord carries a reason `recover` completes,
    else None. No soak starts or moves meanwhile (review finding, Major, R15): a switch
    back whose stops failed leaves v2 on the failed release's processes, which a soak
    would otherwise run on."""
    if any(record.get("reasonKey") in RECOVERABLE for record in reader.records(KIND)):
        return "recover-required"
    return None


def install_active(reader) -> dict | None:
    """The install or release rollback that holds the live exclusion now, if any."""
    return next((record for record in reader.records(KIND) if record["state"] in HOLDING),
                None)


def release_blocker(reader) -> str | None:
    """The reason key of the install or release rollback holding the exclusion, or None."""
    active = install_active(reader)
    return None if active is None else HOLDING[active["state"]]


def exclusion_blocker_of(reader) -> str | None:
    """Why an install or a release rollback may not start, read from one view of the
    ledger: a switch, an abort or a cutover rollback (`cutover-<state>`), a live
    production restore, or another install or release rollback. `begin` and
    `begin_rollback` ask it inside their atomic step, so the exclusion holds both ways
    (the review's fix of 2026-10-26)."""
    from .recovery import TERMINAL, WAITING

    cutovers = reader.records("cutover-record")
    if cutovers and cutovers[-1]["state"] in LIVE_EXCLUSION:
        return f"cutover-{cutovers[-1]['state']}"
    restores = [item for item in reader.records("recovery-request")
                if item["operation"] == "restore.production"
                and item["environment"] == "live"
                and item["state"] not in TERMINAL | WAITING]
    if restores:
        return "production-restore-active"
    return release_blocker(reader)


class ReleaseRecords:
    def __init__(self, ledger, *, clock: Callable[[], dt.datetime]):
        self.ledger, self.clock = ledger, clock

    def get(self, tag: str) -> dict | None:
        return self.ledger.get(KIND, tag)

    def installed(self) -> dict | None:
        """The release that runs now: the latest installed record."""
        records = [item for item in self.ledger.records(KIND) if item["state"] == "installed"]
        return max(records, key=lambda item: item["updatedAt"], default=None)

    def exclusion_blocker(self) -> str | None:
        return exclusion_blocker_of(self.ledger)

    def begin_rollback(self, tag: str) -> dict:
        """The installed release's record, `rolling-back`, under the ledger's lock, so a
        release rollback holds the live exclusion while it runs: refused while anything
        holds the exclusion (`exclusion_blocker_of`), or when `tag` is not the installed
        release."""
        now = utc_text(self.clock())

        def step(view):
            blocker = exclusion_blocker_of(view)
            if blocker is not None:
                raise OperationsError("CONFLICT", current={"reasonKey": blocker})
            current = view.get(KIND, tag)
            if current is None or current["state"] != "installed":
                raise OperationsError("CONFLICT", current={"reasonKey": "no-installed-release"})
            record = {key: value for key, value in current.items() if key != "reasonKey"}
            record.update(state="rolling-back", updatedAt=now)
            view.append(KIND, record, expect_revision=view.revision(KIND, tag))
            return record

        return self.ledger.atomic(step)

    def begin(self, tag: str, commit: str, *, previous_tag: str | None) -> dict:
        """The install's record, `installing`, under the ledger's lock: refused while
        anything holds the exclusion (`exclusion_blocker_of`, inside the step)."""
        now = utc_text(self.clock())

        def step(view):
            blocker = exclusion_blocker_of(view)
            if blocker is not None:
                raise OperationsError("CONFLICT", current={"reasonKey": blocker})
            current = view.get(KIND, tag)
            if current is not None and current["releaseCommit"] != commit:
                raise OperationsError("CONFLICT", current={"reasonKey": "tag-commit-differs"})
            record = {"releaseTag": tag, "releaseCommit": commit, "state": "installing",
                      "installedAt": current["installedAt"] if current else now,
                      "updatedAt": now}
            if previous_tag is not None and previous_tag != tag:
                record["previousTag"] = previous_tag
            view.append(KIND, record, expect_revision=view.revision(KIND, tag))
            return record

        return self.ledger.atomic(step)

    def finish(self, tag: str, state: str, *, backup_id=None, arrangement_version=None,
               steps: dict | None = None, verification: dict | None = None,
               ready_wait_seconds: int | None = None, reason: str | None = None,
               probe_pending: bool | None = None, clear_probe: bool = False,
               switch_back_wait_seconds: int | None = None,
               v2_stopped: bool | None = None, kept_tag: str | None = None,
               step: str | None = None) -> dict:
        """`probe_pending` True records a release installed while v2 was kept stopped as
        not yet probed (`probePending`); False records its probe journey passed (the
        person's decision of 2026-10-25, "Probe it when the soak starts"). `clear_probe`
        clears `probePending` without recording a probe: a release whose probe failed at
        the soak's start and was switched back (your decision of 2026-10-26, "Leave v2
        stopped"). `v2_stopped` True marks that switch back as having left v2 stopped on
        the kept release `kept_tag` (the person's decision of 2026-10-26, "Only for a
        pending probe": `docsuri-release verify` on that tag then starts v2 for the
        soak, and nothing else does); False clears the mark once v2 started. `step` is
        the first step of a switch back that did not complete (`switchBackStep`), kept
        beside the reason and cleared with it (review finding, Major, R20)."""
        now = utc_text(self.clock())

        def step_(view):
            current = view.get(KIND, tag)
            if current is None:
                raise OperationsError("NOT_FOUND")
            record = {key: value for key, value in current.items()
                      if key not in ("reasonKey", "switchBackStep")}
            record.update(state=state, updatedAt=now)
            if step is not None:
                record["switchBackStep"] = step
            if backup_id is not None:
                record["backupId"] = str(backup_id)
            if arrangement_version is not None:
                record["arrangementVersion"] = int(arrangement_version)
            if steps:
                record["stepMilliseconds"] = {name: int(value) for name, value in steps.items()}
            if verification is not None:
                record["verificationRunRef"] = f"github:{verification['commit']}"
            if ready_wait_seconds is not None:
                record["readyWaitSeconds"] = int(ready_wait_seconds)
            if switch_back_wait_seconds is not None:
                record["switchBackWaitSeconds"] = int(switch_back_wait_seconds)
            if reason is not None:
                record["reasonKey"] = reason
            if probe_pending is True:
                record["probePending"] = True
                record.pop("probeSuperseded", None)
            elif probe_pending is False:
                record.pop("probePending", None)
                record.pop("probeSuperseded", None)
                record["probedAt"] = now
            if clear_probe:
                record.pop("probePending", None)
            if v2_stopped is True:
                record["v2Stopped"] = True
                if kept_tag is not None:
                    record["keptTag"] = kept_tag
            elif v2_stopped is False:
                record.pop("v2Stopped", None)
                record.pop("keptTag", None)
            view.append(KIND, record, expect_revision=view.revision(KIND, tag))
            return record

        return self.ledger.atomic(step_)

    def stopped_on(self, kept_tag: str) -> dict | None:
        """The switched-back record whose switch back left v2 stopped on the kept release
        `kept_tag` (`v2Stopped`), else None: the one case, outside a cutover rollback, in
        which `docsuri-release verify` on that tag starts v2 for the soak (the person's
        decision of 2026-10-26, "Only for a pending probe")."""
        return next((item for item in self.ledger.records(KIND)
                     if item["state"] == "switched-back" and item.get("v2Stopped") is True
                     and item.get("keptTag") == kept_tag), None)

    def unprobed(self) -> dict | None:
        """The latest installed record still waiting for its probe journey, whichever
        installed record is the latest (review finding, Minor, R13), else None."""
        records = [item for item in self.ledger.records(KIND)
                   if item["state"] == "installed" and item.get("probePending") is True]
        return max(records, key=lambda item: item["updatedAt"], default=None)

    def settle_others(self, tag: str) -> list[str]:
        """Once `tag`'s install completed (v2 stopped, migrated and switched to it, and
        started, routed and probed or kept stopped), what earlier runs left on other
        records no longer needs `recover` (review finding, Minor, R14): their reasons in
        `RECOVERABLE` are cleared, and an earlier release still waiting for its probe is
        no longer linked, so its `probePending` becomes `probeSuperseded` (a release
        rollback to it makes it pending again); a switch back's mark that v2 was left
        stopped (`v2Stopped`) is cleared too, since v2 runs on `tag` now. One atomic step;
        answers the tags it changed."""
        def step(view):
            # Each record keeps its `updatedAt`, so the latest installed record (the
            # release that runs, `installed`) stays `tag`'s.
            changed = []
            for current in view.records(KIND):
                if current["releaseTag"] == tag:
                    continue
                stale = current.get("reasonKey") in RECOVERABLE
                pending = current["state"] == "installed" and current.get("probePending")
                marked = current.get("v2Stopped") is True
                if not stale and not pending and not marked:
                    continue
                record = {key: value for key, value in current.items()
                          if not (key == "reasonKey" and stale)
                          and key not in ("probePending", "v2Stopped", "keptTag")}
                if pending:
                    record["probeSuperseded"] = True
                view.append(KIND, record,
                            expect_revision=view.revision(KIND, current["releaseTag"]))
                changed.append(current["releaseTag"])
            return changed

        return self.ledger.atomic(step)
