"""Deciding misfits (U8 plan Step 31; BR8.9, BR9.14, Workflow 10).

- `listing(runs, run_id)` lists each misfit kind and reason a run met, with its count,
  its source identifiers and Workflow 10's proposed decision: identifiers and counts
  only, never content.
- `decide` shows you one (kind, reason) with its proposed rule, records your decision
  through PlatformControl's `platform.decision.record` (Workflow 18) and then the
  MisfitDecision. While a final run's freeze holds, a decision is refused; it applies
  from the next dry run onward, and a decision changed after the latest accepted dry run
  started voids that run for the switch until a new one is accepted (BR9.2).
"""

from __future__ import annotations

from collections import Counter

from backend.modules.operations.migration.misfits import MAPPING_RULES, PROPOSALS
from backend.modules.operations.migration_records import MISFIT, MigrationRuns, MisfitDecisions

STEP = "misfit-decision"
MAX_SOURCES = 50


def listing(runs: MigrationRuns, run_id) -> list[dict]:
    met = [item for item in runs.ledger.records(MISFIT) if item["runId"] == str(run_id)]
    counts = Counter((item["kind"], item["reasonKey"]) for item in met)
    current = MisfitDecisions(runs.ledger).current()
    rows = []
    for (kind, reason), count in sorted(counts.items()):
        sources = sorted(item["sourceId"] for item in met
                         if (item["kind"], item["reasonKey"]) == (kind, reason))
        rows.append({
            "kind": kind, "reasonKey": reason, "count": count,
            "sourceIds": sources[:MAX_SOURCES], "proposed": PROPOSALS.get((kind, reason)),
            "mappingRule": MAPPING_RULES.get((kind, reason)),
            "decided": current.of(kind, reason),
            "newInFinal": any(item["newInFinal"] for item in met
                              if (item["kind"], item["reasonKey"]) == (kind, reason)),
        })
    return rows


def subject(kind: str, reason: str, decision: str) -> dict:
    """Exactly what you are shown for one decision."""
    return {"kind": kind, "reasonKey": reason, "decision": decision,
            "mappingRule": MAPPING_RULES.get((kind, reason)) if decision == "map" else None,
            "proposed": PROPOSALS.get((kind, reason))}


def decide(decisions_tool, misfit_decisions: MisfitDecisions, kind: str, reason: str,
           decision: str) -> dict:
    """`decisions_tool` is PlatformControl's `Decisions` (Workflow 18)."""
    shown_subject = subject(kind, reason, decision)
    shown = decisions_tool.show(STEP, f"{kind}:{reason}", shown_subject)
    recorded = decisions_tool.record(shown, "approved", current=lambda: shown_subject)
    return misfit_decisions.decide(kind, reason, decision, approval_id=recorded["approvalId"],
                                   mapping_rule=shown_subject["mappingRule"])
