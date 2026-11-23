"""Recording your decision (U8 plan Step 27; Workflow 18, BR9.14, NFR1.4, security-design
§ 5.5).

1. The subject is rendered exactly as it is shown (`render`), and the digest is taken of
   those bytes.
2. When you decide, the subject is rendered again: if it changed since it was shown,
   the decision is refused and the new subject is returned to be shown.
3. `platform.decision.record` binds the operator, the step, the subject reference and
   the digest through its receipt.
4. An unknown outcome is reconciled before anything relies on it; while it stays
   unknown no approval is appended.
5. The MaintainerApproval is appended through the ledger component's fixed command
   (`docsuri-ledger append`), which admits it only with that confirmed receipt.

The web application has no route that records a decision (A5): only this module does.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from uuid import uuid4

from .u8_protocols import APPROVAL_STEPS, Operator

DECISIONS_TARGET = "decisions"


def render(subject: dict) -> bytes:
    """The exact bytes shown: canonical, readable JSON."""
    return json.dumps(subject, sort_keys=True, indent=2, ensure_ascii=False).encode() + b"\n"


def digest(shown: bytes) -> str:
    return hashlib.sha256(shown).hexdigest()


class SubjectChanged(Exception):
    """The subject changed after it was shown; `shown` is what to show now."""

    def __init__(self, shown: bytes):
        super().__init__("the subject changed since it was shown")
        self.shown = shown


class DecisionUnsettled(Exception):
    """The decision's outcome is unknown and could not be reconciled."""


@dataclass
class Shown:
    step: str
    subject_ref: str
    shown: bytes

    @property
    def digest(self) -> str:
        return digest(self.shown)


def _ledger_time(moment: dt.datetime) -> str:
    from backend.modules.operations.ledger import utc_text

    return utc_text(moment)


class Decisions:
    def __init__(self, operator: Operator, append: Callable[[dict], dict], *,
                 clock: Callable[[], dt.datetime]):
        """`append` is the ledger component's `append` word (its fixed command in
        production, the same command run in process in the realm)."""
        self.operator, self.append, self.clock = operator, append, clock

    def show(self, step: str, subject_ref: str, subject: dict) -> Shown:
        if step not in APPROVAL_STEPS:
            raise ValueError("decision step outside the registered steps")
        return Shown(step, subject_ref, render(subject))

    def record(self, shown: Shown, decision: str, *, current: Callable[[], dict]) -> dict:
        """Your decision on exactly what you were shown."""
        now_shown = render(current())
        if now_shown != shown.shown:
            raise SubjectChanged(now_shown)
        inputs = {"step": shown.step, "subjectRef": shown.subject_ref,
                  "subjectDigest": shown.digest, "decision": decision}
        receipt = self.operator.execute("platform.decision.record", DECISIONS_TARGET, inputs,
                                        key=f"decision:{uuid4()}")
        if receipt["outcome"] == "unknown":
            receipt = self.operator.reconcile(receipt["operationId"])
            if receipt.get("reconciliationState") != "reconciled-applied":
                raise DecisionUnsettled(receipt["operationId"])
        elif receipt["outcome"] != "succeeded":
            raise DecisionUnsettled(receipt["operationId"])
        approval = str(uuid4())
        moment = _ledger_time(self.clock())
        result = self.append({
            "kind": "maintainer-approval", "expectRevision": 0,
            "record": {
                "approvalId": approval, "step": shown.step, "subjectRef": shown.subject_ref,
                "subjectDigest": shown.digest, "decision": decision, "recordedAt": moment,
                "operatorReceiptRef": receipt["receiptId"],
            },
            "receipts": [{
                "receiptId": receipt["receiptId"], "operationId": receipt["operationId"],
                "operation": "platform.decision.record", "targetId": DECISIONS_TARGET,
                "inputHash": receipt["inputHash"], "outcome": "succeeded",
            }],
        })
        if not result.get("ok"):
            raise DecisionUnsettled(str(result.get("reason")))
        return {"approvalId": approval, "receipt": receipt, "subjectDigest": shown.digest}
