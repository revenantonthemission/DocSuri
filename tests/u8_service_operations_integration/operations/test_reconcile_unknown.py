"""An unknown outcome is reconciled from its receipt without running again (U8 plan
Step 28; BR9.10, NFR4.2).

An effect killed at its deadline settles `unknown`. Reconciliation reads the receipt,
then the effect's target alone: the effect record the child writes after an applied
effect, else the driver's own reading of the target. It settles the receipt applied or
not applied, and the effect never runs a second time.
"""

from __future__ import annotations

import dataclasses
import time

from docsuri_ops.platform_control.executor import EffectOutcome, run_effect
from docsuri_ops.u8_platform.u8_protocols import Revision, load_revision
from tests.u8_service_operations_integration import platform_flows as pf

SHORT_DEADLINE = 2


def short(name: str) -> Revision:
    """The revision with one protocol's deadline cut short, so the kill comes quickly."""
    revision = load_revision()
    return dataclasses.replace(revision, u8=tuple(
        dataclasses.replace(item, deadline_seconds=SHORT_DEADLINE) if item.name == name
        else item for item in revision.u8))


def test_an_effect_killed_at_its_deadline_settles_unknown_and_reconciles_not_applied(
    tmp_path, realm,
):
    journey = pf.journey(tmp_path, realm)
    operator = journey.operator(revision=short("platform.isolation.check"))
    started = time.monotonic()
    receipt = operator.execute("platform.isolation.check", "isolation", {"via": "in-person"},
                               key=f"hang-{tmp_path.name}-{pf.RUN}", injected_fault="hang")
    # Killed at its deadline, well before the hang would have ended.
    assert time.monotonic() - started < 30
    assert receipt["outcome"] == "unknown", receipt
    reconciled = operator.reconcile(receipt["operationId"])
    # U7 keeps the outcome as it was observed and settles the reconciliation beside it.
    assert reconciled["reconciliationState"] == "reconciled-not-applied", reconciled
    assert not (journey.state / "isolation").exists()
    # A second reconciliation reads the settled receipt and changes nothing.
    assert operator.reconcile(receipt["operationId"])["receiptId"] == receipt["receiptId"]


def applied_then_lost(**request) -> EffectOutcome:
    """The effect ran, then the child's answer was lost (killed at its deadline)."""
    outcome = run_effect(**request)
    assert outcome.status == "applied", outcome
    return EffectOutcome("unknown", [], {"kind": "internal", "message": "deadline"})


def test_an_applied_effect_whose_answer_was_lost_reconciles_applied_without_running_again(
    tmp_path, realm,
):
    journey = pf.journey(tmp_path, realm)
    label = "dev.docsuri.u8.run.maintenance"
    operator = journey.operator(run_effect=applied_then_lost)
    receipt = operator.execute("platform.service.control", label,
                               {"label": label, "action": "stop"},
                               key=f"lost-{tmp_path.name}-{pf.RUN}")
    assert receipt["outcome"] == "unknown"
    before = journey.read_state("services", f"{label}.json")
    stop = journey.state / "stops" / f"{label}.json"
    written = stop.stat().st_mtime_ns

    def must_not_run(**_):
        raise AssertionError("reconciliation ran the effect again")

    reconciler = journey.operator(run_effect=must_not_run)
    reconciled = reconciler.reconcile(receipt["operationId"])
    assert reconciled["reconciliationState"] == "reconciled-applied", reconciled
    assert journey.read_state("services", f"{label}.json") == before
    assert stop.stat().st_mtime_ns == written
