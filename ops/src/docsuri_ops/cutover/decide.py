"""`docsuri-ops cutover decide <kind>`: your decisions for the cutover commands (the
person's decision of 2026-10-24, "Add decision commands"; Workflows 12–14, Workflow 18,
BR9.14, NFR1.4).

Each approval a cutover command takes is recorded here, in two calls, as the migration
decisions are:

1. Without `confirm`, the subject is rendered from the current records exactly as it is
   shown (`u8_platform.decisions.render`), with its digest; nothing is recorded.
2. With `confirm` set to that digest, the subject is rendered again; only when it is
   unchanged is your decision recorded through `platform.decision.record`, and the
   approval's identifier and its subject are returned. A subject that changed in
   between is refused and the new one is shown.

Each kind is one approval step, taken by one command and refused by every other (each
command checks the approval's step and subject reference against its own):

| kind | taken by | while the cutover is | its subject adds |
|---|---|---|---|
| `switch-start` | `start` | ready-to-switch | `finalSnapshotBackstopSeconds`, (1) |
| `final-report` | `start` (again) | switching, final run reported | the report's digest |
| `admission-opening` | `open` | switching | `v1StoresDisposalSeconds`, (2) |
| `rollback` | `rollback` | switched | `rolledBackDisposalSeconds` |
| `rollback-cancel` | `cancel-rollback` | rolling-back | — |
| `rollback-copy-waiver` | `waive-copy` | rolling-back, copy pending | v2's writes (3) |
| `settlement` | `settle` | switched | `finalSnapshotDisposalSeconds`, (4) |
| `v1-restart-rehearsal` | `rehearse-restart` | before the switch, or rolled back | — |
| `disposal-date` | `date-final-snapshot` | rehearsing or ready-to-switch | (5) |
| `provider-sign-in` | `provider-decision` | switching | `provider` (6) |
| `provider-first-effect` | `provider-decision` | switching, switched, settled | (6), (7) |

(1) `acceptedDryRun`, the accepted dry run's durations, and `soak`, the soak's 95th
percentiles (Step 70(d)); (2) `providersAcceptedUnavailable`; (3) what v2 made since
opening; (4) `finalSnapshotCopyId`; (5) after an abort, `finalSnapshotCopyId` and
`finalSnapshotDisposeAfter`; (6) `provider`: `google` or `orcid` for a sign-in, `resend`
or `notion` for a first effect (U8 plan Step 106(c), CP-3); (7) `provider` and
`previewDigest`. A first effect's subject names its preview's digest, not its content: a
preview may hold up to 2,000,000 bytes, more than a cutover word reads, so you read the
content with `cutover provider-previews` before you decide, and the digest must be among
the previews held since the switch's check. In production each of a first effect's two
calls asks for your password once more, for that listing.

A decided disposal date is never typed (U8 plan Step 70(a), your decision of 2026-11-01,
L1-3, "Event plus offset"): each subject names the policy's offset its command applies
at its event, so the call that shows a subject and the call that confirms it render the
same bytes. The only date a subject carries, `disposal-date`'s, is fixed by the record's
stored `abortStartedAt`. An opening takes only `providersAcceptedUnavailable`.

The subject always names the cutover, its state and its revision, so a decision shown
before the record moved is refused when you confirm it. A command that takes a subject
(`start`, `open`, `rollback`, `waive-copy`, `settle`, `date-final-snapshot`,
`provider-decision`) is run with exactly the subject returned here; its digest is the one
the approval binds. The provider kinds' subject reference is `provider:<name>`, the one
`ProviderActivation.approve` checks.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable
from dataclasses import dataclass

from backend.modules.operations.cutover import KIND as CUTOVER
from backend.modules.operations.errors import OperationsError
from backend.modules.operations.ledger import utc_text
from backend.modules.operations.migration_records import REPORT
from backend.modules.operations.provider_activation import OUTWARD, SIGN_IN
from backend.modules.operations.retained_copies import is_open


@dataclass(frozen=True)
class Kind:
    command: str
    states: tuple[str, ...]
    fields: frozenset[str] = frozenset()


KINDS = {
    "switch-start": Kind("start", ("ready-to-switch",)),
    "final-report": Kind("start", ("switching",)),
    "admission-opening": Kind("open", ("switching",), frozenset({"providersAcceptedUnavailable"})),
    "rollback": Kind("rollback", ("switched",)),
    "rollback-cancel": Kind("cancel-rollback", ("rolling-back",)),
    "rollback-copy-waiver": Kind("waive-copy", ("rolling-back",)),
    "settlement": Kind("settle", ("switched",)),
    "v1-restart-rehearsal": Kind("rehearse-restart",
                                 ("preparing", "rehearsing", "ready-to-switch", "rolled-back")),
    "disposal-date": Kind("date-final-snapshot", ("rehearsing", "ready-to-switch")),
    # U8 plan Step 106(c), CP-3; a first effect also after opening by reading CP-3(a).
    "provider-sign-in": Kind("provider-decision", ("switching",), frozenset({"provider"})),
    "provider-first-effect": Kind("provider-decision", ("switching", "switched", "settled"),
                                  frozenset({"provider", "previewDigest"})),
}
PROVIDER_KINDS = {"provider-sign-in": SIGN_IN, "provider-first-effect": OUTWARD}
DECISIONS = ("approved", "declined")
TAKES_SUBJECT = frozenset({"start", "open", "rollback", "waive-copy", "settle",
                           "date-final-snapshot", "provider-decision"})
# The rule each kind's subject names: the policy's offset its command applies.
RULES = {
    "switch-start": ("finalSnapshotBackstopSeconds", "final_snapshot_backstop_seconds"),
    "admission-opening": ("v1StoresDisposalSeconds", "v1_stores_disposal_seconds"),
    "rollback": ("rolledBackDisposalSeconds", "rolled_back_disposal_seconds"),
    "settlement": ("finalSnapshotDisposalSeconds", "final_snapshot_disposal_seconds"),
}
ACCEPTED_RUN_FIELDS = ("durationSeconds", "phaseSeconds", "interruptions")


def _refused(reason: str, **current) -> OperationsError:
    return OperationsError("INVALID_INPUT", current={"reasonKey": reason, **current})


def _parse(text: str) -> dt.datetime:
    return dt.datetime.fromisoformat(text.replace("Z", "+00:00"))


def aborted_final_snapshot(ledger, record: dict) -> dict | None:
    """The aborted attempt's final snapshot a disposal-date decision can date: the record
    holds `abortStartedAt` and the copy its `finalSnapshotCopyId` names is an open,
    completed v1-final-snapshot copy; else None."""
    if not record.get("abortStartedAt") or not record.get("finalSnapshotCopyId"):
        return None
    copy = ledger.get("retained-copy", record["finalSnapshotCopyId"])
    if copy is None or copy.get("kind") != "v1-final-snapshot" or not is_open(copy) or (
        "completedAt" not in copy
    ):
        return None
    return copy


class CutoverDecisions:
    def __init__(self, tool, in_person):
        """`tool` is the CutoverTool, `in_person` the migration words' `InPerson`."""
        self.tool, self.in_person = tool, in_person
        self.ledger = tool.ledger

    def run(self, kind: str | None, document: dict) -> dict:
        if kind not in KINDS:
            raise _refused("decision-kind-outside-its-set")
        spec = KINDS[kind]
        allowed = {"decision", "confirm", *spec.fields}
        if not set(document) <= allowed:
            raise _refused("word-or-input-refused")
        decision = document.get("decision", "approved")
        if decision not in DECISIONS:
            raise _refused("decision-outside-its-set")
        confirm = document.get("confirm")
        if confirm is not None and (not isinstance(confirm, str) or len(confirm) != 64):
            raise _refused("confirm-is-the-shown-digest")
        record = self.tool.machine.require()
        if record["state"] not in spec.states:
            raise OperationsError("CONFLICT", current={"reasonKey": "cutover-state-differs",
                                                       "state": record["state"]})
        subject_ref, subject = self._subject(kind, spec, record, document)
        decided = self.in_person.decide(kind, subject_ref, subject, decision, confirm)
        if "shown" in decided:
            return decided["shown"]
        answer = {"state": "decided", "kind": kind, "decision": decision,
                  "approvalId": decided["approvalId"], "command": spec.command}
        if spec.command in TAKES_SUBJECT:
            answer["subject"] = subject
        return answer

    def _subject(self, kind: str, spec: Kind, record: dict, document: dict):
        subject = {"step": kind, "cutoverId": record["cutoverId"],
                   "cutoverState": record["state"],
                   "cutoverRevision": self.ledger.revision(CUTOVER, record["cutoverId"]),
                   "releaseTag": record.get("releaseTag")}
        if "providersAcceptedUnavailable" in spec.fields and (
            "providersAcceptedUnavailable" in document
        ):
            subject["providersAcceptedUnavailable"] = self._accepted_unavailable(
                document["providersAcceptedUnavailable"])
        if kind in PROVIDER_KINDS:
            return self._provider_subject(kind, subject, document)
        if kind in RULES:
            name, attribute = RULES[kind]
            subject[name] = getattr(self.tool.policy, attribute)
        if kind == "switch-start":
            subject["acceptedDryRun"] = self._accepted_dry_run(record)
            subject["soak"] = self._soak(record)
        if kind == "settlement":
            subject["finalSnapshotCopyId"] = record.get("finalSnapshotCopyId")
        if kind == "disposal-date":
            copy = aborted_final_snapshot(self.ledger, record)
            if copy is None:
                raise OperationsError("CONFLICT",
                                      current={"reasonKey": "no-aborted-final-snapshot"})
            subject["finalSnapshotCopyId"] = copy["copyId"]
            subject["finalSnapshotDisposeAfter"] = utc_text(
                _parse(record["abortStartedAt"]) + dt.timedelta(
                    seconds=self.tool.policy.final_snapshot_disposal_seconds))
        if kind == "final-report":
            return self._final_report(record, subject)
        if kind == "rollback-copy-waiver":
            if "rollbackCopyPendingSince" not in record:
                raise OperationsError("CONFLICT",
                                      current={"reasonKey": "rollback-copy-not-pending"})
            writes: Callable | None = self.tool.platform.v2_writes
            if writes is not None and record.get("admissionOpenedAt"):
                opened = dt.datetime.fromisoformat(
                    record["admissionOpenedAt"].replace("Z", "+00:00"))
                subject["v2WritesSinceOpening"] = writes(opened)
        return record["cutoverId"], subject

    def _provider_subject(self, kind: str, subject: dict, document: dict):
        """A provider decision's subject (U8 plan Step 106(c)): the provider and, for a
        first effect, a preview held since the switch's check. Without the provider words
        the decision is refused before any subject is rendered."""
        words = self.tool.platform.provider_word
        if words is None:
            raise OperationsError("DEPENDENCY_UNAVAILABLE",
                                  current={"reasonKey": "provider-words-unwired"})
        provider = document.get("provider")
        if not isinstance(provider, str) or provider not in PROVIDER_KINDS[kind]:
            raise _refused("provider-outside-its-step")
        subject["provider"] = provider
        if kind == "provider-first-effect":
            digest = document.get("previewDigest")
            if not isinstance(digest, str) or len(digest) != 64 or not all(
                character in "0123456789abcdef" for character in digest
            ):
                raise _refused("previewDigest-form")
            held = words("provider-previews", {"provider": provider})
            if digest not in {item["digest"] for item in held.get("previews", [])}:
                raise OperationsError("CONFLICT", current={"reasonKey": "preview-not-recorded"})
            subject["previewDigest"] = digest
        return "provider:" + provider, subject

    def _accepted_dry_run(self, record: dict) -> dict:
        """The accepted dry run's measures (Step 68(g)), each null where it holds none
        (U8 plan Step 70(d), NFR8.8, L1-59)."""
        run_id = record.get("acceptedDryRunId")
        run = (None if run_id is None else self.tool.runs.get(run_id)) or {}
        return {"runId": run_id, **{name: run.get(name) for name in ACCEPTED_RUN_FIELDS}}

    def _soak(self, record: dict) -> dict:
        """The soak's period and its latency lines' summary (performance-design § 10,
        L1-59): fixed once the record is ready-to-switch, since the soak's period has
        ended and only windows that end by `until` count. Without a reader the decision
        is refused as an unwired part is; a reader that fails refuses it with
        `soak-latency-unreadable`."""
        from docsuri_ops.production_tool import Refused

        reader = self.tool.platform.soak_latency
        if reader is None:
            raise OperationsError("DEPENDENCY_UNAVAILABLE",
                                  current={"reasonKey": "soak-latency-unwired"})
        started = record.get("soakStartedAt")
        if not started:
            raise OperationsError("CONFLICT", current={"reasonKey": "soak-not-started"})
        start = _parse(started)
        until = start + dt.timedelta(seconds=record["soakPeriodSeconds"])
        try:
            summary = reader(start, until)
        except (OSError, ValueError, Refused):
            raise OperationsError("CONFLICT",
                                  current={"reasonKey": "soak-latency-unreadable"}) from None
        return {"from": started, "until": utc_text(until), "windows": summary["windows"],
                "p95Ms": summary["p95Ms"], "requests": summary["requests"]}

    @staticmethod
    def _accepted_unavailable(value) -> list[str]:
        if not isinstance(value, list) or not all(
            isinstance(item, str) and item.replace("-", "").replace(".", "").isalnum()
            for item in value
        ) or len(value) > 32:
            raise _refused("providersAcceptedUnavailable-form")
        return sorted(set(value))

    def _final_report(self, record: dict, subject: dict):
        run_id = record.get("finalRunId")
        run = None if run_id is None else self.tool.runs.get(run_id)
        if run is None or run["state"] != "reported":
            raise OperationsError("CONFLICT", current={"reasonKey": "final-run-not-reported"})
        report = self.ledger.get(REPORT, run_id)
        if report is None:
            raise OperationsError("CONFLICT", current={"reasonKey": "report-missing"})
        new_in_final = sorted({(item["kind"], item["reasonKey"])
                               for item in self.ledger.records("misfit-record")
                               if item["runId"] == run_id and item.get("newInFinal")})
        subject.update({"finalRunId": run_id, "report": {key: report.get(key) for key in (
            "reportRef", "reportDigest", "kinds", "reconciles")},
            "newInFinal": [list(pair) for pair in new_in_final]})
        return run_id, subject
