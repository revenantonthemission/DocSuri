"""Your decisions on misfits and the final run's freeze (U8 plan Step 32; BR8.9, BR8.12,
BR9.2, Workflow 10).

The records are the test ledger's own: runs moved through the MigrationRun machine,
the misfits they met, your decisions bound to MaintainerApprovals, and the cutover the
final run needs. One decision goes through PlatformControl's decision operation on the
realm's store, as Workflow 18 records it.
"""

from __future__ import annotations

import pytest

from backend.modules.operations.errors import OperationsError
from backend.modules.operations.migration.misfits import (
    MAPPING_RULES,
    NOT_IN_SCOPE_KINDS,
    PROPOSALS,
    Decision,
    Decisions,
    disposition,
)
from backend.modules.operations.migration_records import MigrationRuns, MisfitDecisions
from tests.u8_service_operations_integration import recovery_flows as rf

COMMIT = "1" * 40


@pytest.fixture
def ledger(tmp_path, clock):
    value = rf.open_ledger(tmp_path, clock)
    yield value
    value.close()


@pytest.fixture
def runs(ledger, clock):
    return MigrationRuns(ledger, clock=clock)


@pytest.fixture
def decisions(ledger, clock):
    return MisfitDecisions(ledger, clock=clock)


def decide(ledger, decisions, clock, kind, reason, decision=None):
    decision = decision or PROPOSALS[(kind, reason)]
    approval = rf.approval_record(ledger, "misfit-decision", f"{kind}:{reason}", now=clock())
    return decisions.decide(kind, reason, decision, approval_id=approval["approvalId"],
                            mapping_rule=MAPPING_RULES.get((kind, reason))
                            if decision == "map" else None)


def reported(runs, ledger, clock, kind="dry", reconciles=True) -> dict:
    go = (rf.approval_record(ledger, "dry-run-go-ahead", "v1", now=clock())["approvalId"]
          if kind == "dry" else None)
    run = runs.start(kind, tool_commit=COMMIT, go_ahead=go)
    for state in ("copying", "importing", "verifying", "reported"):
        run = runs.move(run["runId"], state)
    runs.record_report(run["runId"], reference=f"evidence/migration/parity-{run['runId']}.json",
                       digest="a" * 64, kinds=1, reconciles=reconciles)
    return run


def accept(runs, ledger, clock, run) -> dict:
    step = "dry-run-report" if run["kind"] == "dry" else "final-report"
    approval = rf.approval_record(ledger, step, run["runId"], now=clock())
    return runs.decide_report(run["runId"], approval["approvalId"])


def switching(ledger) -> dict:
    record = rf.cutover_record(ledger, "preparing")
    for state in ("rehearsing", "ready-to-switch", "switching"):
        record = rf.advance_cutover(ledger, record, state)
    return record


def test_a_final_run_refuses_to_start_with_an_undecided_kind_and_reason(runs, ledger,
                                                                        decisions, clock):
    decide(ledger, decisions, clock, "account", "no-email")
    dry = reported(runs, ledger, clock)
    runs.record_misfits(dry["runId"], [("account", "v1-a", "no-email"),
                                       ("account", "v1-b", "closed-in-v1"),
                                       ("glossary", "1", "not-in-scope")])
    accept(runs, ledger, clock, dry)
    with pytest.raises(OperationsError) as not_switching:
        runs.start("final", tool_commit=COMMIT)
    assert not_switching.value.current == {"reasonKey": "not-switching"}
    switching(ledger)
    with pytest.raises(OperationsError) as undecided:
        runs.start("final", tool_commit=COMMIT)
    assert undecided.value.current == {"reasonKey": "misfits-undecided",
                                       "undecided": ["account:closed-in-v1"]}
    # A kind Q13 did not name defaults to archive-only and needs no decision.
    decide(ledger, decisions, clock, "account", "closed-in-v1")
    with pytest.raises(OperationsError) as stale:
        runs.start("final", tool_commit=COMMIT)
    # That decision came after the accepted dry run started: it ran under other ones.
    assert stale.value.current == {"reasonKey": "dry-run-not-current"}


def test_the_freeze_and_its_end_on_rejection_failure_abort_or_rollback(runs, ledger,
                                                                       decisions, clock):
    decide(ledger, decisions, clock, "account", "no-email")
    dry = reported(runs, ledger, clock)
    accept(runs, ledger, clock, dry)
    switching(ledger)
    final = runs.start("final", tool_commit=COMMIT)
    assert all(item["frozen"] for item in ledger.records("misfit-decision"))
    with pytest.raises(OperationsError) as frozen:
        decide(ledger, decisions, clock, "account", "no-email", "drop")
    assert frozen.value.current == {"reasonKey": "decisions-frozen"}
    # A rejected final run ends the freeze.
    for state in ("copying", "importing", "verifying", "reported"):
        runs.move(final["runId"], state)
    declined = rf.approval_record(ledger, "final-report", final["runId"], now=clock(),
                                  decision="declined")
    assert runs.decide_report(final["runId"], declined["approvalId"])["state"] == "rejected"
    assert not any(item["frozen"] for item in ledger.records("misfit-decision"))
    # A failed one too.
    again = runs.start("final", tool_commit=COMMIT)
    assert all(item["frozen"] for item in ledger.records("misfit-decision"))
    runs.move(again["runId"], "failed")
    assert not any(item["frozen"] for item in ledger.records("misfit-decision"))
    # An abort or a rollback after a final run started, even an accepted one.
    third = runs.start("final", tool_commit=COMMIT)
    for state in ("copying", "importing", "verifying", "reported"):
        runs.move(third["runId"], state)
    runs.record_report(third["runId"], reference="evidence/migration/parity-3.json",
                       digest="b" * 64, kinds=1, reconciles=True)
    assert accept(runs, ledger, clock, third)["state"] == "accepted"
    assert all(item["frozen"] for item in ledger.records("misfit-decision"))
    runs.end_freeze()
    assert not any(item["frozen"] for item in ledger.records("misfit-decision"))
    assert decide(ledger, decisions, clock, "account", "no-email", "drop")["decision"] == "drop"


def test_new_in_final_items_take_archive_only_and_need_your_explicit_approval(runs, ledger,
                                                                             clock):
    current = Decisions({("account", "no-email"): Decision("drop")})
    final = current.for_final_run()
    assert final.of("paper", "exceeds-v2-limit") == "archive-only"
    assert current.of("paper", "exceeds-v2-limit") is None
    assert disposition(final, "paper", "exceeds-v2-limit") == "excluded"
    assert disposition(current, "paper", "exceeds-v2-limit") == "skipped"
    run = reported(runs, ledger, clock)
    runs.record_misfits(run["runId"], [("paper", "p1", "exceeds-v2-limit")],
                        new_in_final={("paper", "exceeds-v2-limit")})
    [record] = ledger.records("misfit-record")
    assert record["newInFinal"] is True
    # Your decision on the report is the explicit approval; no other step stands for it.
    wrong = rf.approval_record(ledger, "dry-run-go-ahead", run["runId"], now=clock())
    with pytest.raises(OperationsError) as refused:
        runs.decide_report(run["runId"], wrong["approvalId"])
    assert refused.value.code == "FORBIDDEN"
    assert accept(runs, ledger, clock, run)["state"] == "accepted"


def test_a_report_that_does_not_reconcile_cannot_be_accepted(runs, ledger, clock):
    run = reported(runs, ledger, clock, reconciles=False)
    with pytest.raises(OperationsError) as refused:
        accept(runs, ledger, clock, run)
    assert refused.value.current == {"reasonKey": "report-not-reconciled"}
    assert runs.require(run["runId"])["state"] == "reported"


def test_a_decision_changed_after_the_accepted_dry_run_started_voids_it(runs, ledger,
                                                                        decisions, clock):
    decide(ledger, decisions, clock, "account", "no-email")
    dry = reported(runs, ledger, clock)
    accept(runs, ledger, clock, dry)
    assert runs.dry_run_current()
    decide(ledger, decisions, clock, "account", "no-email", "drop")
    assert not runs.dry_run_current()
    newer = reported(runs, ledger, clock)
    accept(runs, ledger, clock, newer)
    assert runs.dry_run_current()


def test_decisions_need_their_approval_and_a_known_rule(ledger, decisions, clock):
    wrong = rf.approval_record(ledger, "misfit-decision", "account:no-email", now=clock())
    with pytest.raises(OperationsError):
        decisions.decide("account", "closed-in-v1", "archive-only",
                         approval_id=wrong["approvalId"])
    with pytest.raises(OperationsError) as rule:
        decisions.decide("account", "no-email", "map", approval_id=wrong["approvalId"],
                         mapping_rule="guess-an-email")
    assert rule.value.current == {"reasonKey": "mapping-rule-unknown"}
    with pytest.raises(OperationsError):
        decisions.decide("account", "no-email", "keep", approval_id=wrong["approvalId"])
    assert set(NOT_IN_SCOPE_KINDS) <= {kind for kind, _ in PROPOSALS}
    assert Decisions().of("glossary", "not-in-scope") == "archive-only"
    assert len(Decisions().digest()) == 64


def test_the_listing_and_your_decision_through_platform_control(tmp_path, realm, ledger,
                                                               decisions, runs, clock):
    from docsuri_ops.migration.decisions import decide as record_decision
    from docsuri_ops.migration.decisions import listing, subject
    from docsuri_ops.u8_platform.decisions import Decisions as PlatformDecisions
    from tests.u8_service_operations_integration import platform_flows as pf

    run = reported(runs, ledger, clock)
    runs.record_misfits(run["runId"], [("account", "v1-a", "locked-in-v1"),
                                       ("account", "v1-b", "locked-in-v1"),
                                       ("glossary", "1", "not-in-scope"),
                                       ("glossary", "2", "not-in-scope")])
    rows = listing(runs, run["runId"])
    assert [(row["kind"], row["reasonKey"], row["count"]) for row in rows] == [
        ("account", "locked-in-v1", 2), ("glossary", "not-in-scope", 1)]
    assert rows[0]["sourceIds"] == ["v1-a", "v1-b"] and rows[0]["proposed"] == "map"
    assert rows[1]["sourceIds"] == ["count:2"] and rows[1]["decided"] == "archive-only"
    assert subject("account", "locked-in-v1", "map")["mappingRule"] == "import-reset-required"
    operator = pf.journey(tmp_path, realm).operator(ledger=ledger, clock=clock)

    def append(document):
        facts = tuple({**item, "confirmedAt": "2026-10-22T12:00:00.000Z"}
                      for item in document["receipts"])
        ledger.append(document["kind"], document["record"],
                      expect_revision=document["expectRevision"], receipts=facts)
        return {"ok": True}

    recorded = record_decision(PlatformDecisions(operator, append, clock=clock), decisions,
                               "account", "locked-in-v1", "map")
    assert recorded["decision"] == "map" and recorded["mappingRule"] == "import-reset-required"
    approval = ledger.get("maintainer-approval", recorded["approvalId"])
    assert approval["step"] == "misfit-decision"
    assert listing(runs, run["runId"])[0]["decided"] == "map"


# --- the table, the durations and CorpusContent's refusals (U8 plan Step 69(d), (g), (h)) ------

# functional-spec.md's table (:251-268), written out here and never derived from the code.
TABLE_KINDS = ("followed-topic", "digest-settings", "glossary", "saved-search",
               "search-history", "behavior-event", "plan-record", "private-upload",
               "research-history", "novelty-history", "summary")
TABLE = {
    ("account", "required-field-without-source"): "map",
    ("account", "unverified-in-v1"): "archive-only",
    ("account", "locked-in-v1"): "map",
    ("account", "closed-in-v1"): "archive-only",
    ("account", "no-email"): "archive-only",
    ("account", "email-case-conflict"): "archive-only",
    ("identity-link", "unconfirmed-link"): "drop",
    ("identity-link", "duplicate-provider-link"): "archive-only",
    ("preferences", "no-v2-home"): "archive-only",
    ("paper", "exceeds-v2-limit"): "archive-only",
    ("paper", "ineligible-in-v2"): "archive-only",
    ("paper-content", "content-shape-unconvertible"): "archive-only",
    ("paper-embedding", "embedding-provenance-unproven"): "map",
    ("paper-figure", "no-v2-home"): "archive-only",
    ("saved-paper", "duplicate-by-version"): "map",
    **{(kind, "not-in-scope"): "archive-only" for kind in TABLE_KINDS},
}


def test_the_misfit_table_is_the_functional_specs():
    assert len(TABLE) == 26
    assert set(PROPOSALS) == set(TABLE)
    assert dict(PROPOSALS) == TABLE
    assert [pair for pair, decision in TABLE.items() if decision == "map"] == [
        ("account", "required-field-without-source"), ("account", "locked-in-v1"),
        ("paper-embedding", "embedding-provenance-unproven"),
        ("saved-paper", "duplicate-by-version")]
    assert set(MAPPING_RULES) == {pair for pair, decision in TABLE.items()
                                  if decision == "map"}
    assert sum(decision == "archive-only" for decision in TABLE.values()) == 21
    assert tuple(NOT_IN_SCOPE_KINDS) == TABLE_KINDS


def test_a_run_records_each_phases_start_and_its_duration_from_snapshot_to_report(
    runs, ledger, clock,
):
    from backend.modules.operations.ledger import utc_text

    def at(seconds: float) -> str:
        return utc_text(t0 + __import__("datetime").timedelta(seconds=seconds))

    t0 = clock()
    go = rf.approval_record(ledger, "dry-run-go-ahead", "v1", now=clock())["approvalId"]
    run = runs.start("dry", tool_commit=COMMIT, go_ahead=go)
    first = runs.require(run["runId"])
    assert first["phaseStartedAt"] == {"preparing": at(0)} and first["interruptions"] == 0
    clock.advance(10)
    runs.move(run["runId"], "copying")
    clock.advance(2)
    runs.move(run["runId"], "copying", snapshotStartedAt=at(12))
    clock.advance(18)
    runs.move(run["runId"], "importing")
    clock.advance(30)
    runs.move(run["runId"], "verifying")
    clock.advance(40)
    runs.move(run["runId"], "reported")
    done = runs.require(run["runId"])
    assert done["phaseStartedAt"] == {"preparing": at(0), "copying": at(10),
                                      "importing": at(30), "verifying": at(60),
                                      "reported": at(100)}
    assert done["phaseSeconds"] == {"preparing": 10, "copying": 20, "importing": 30,
                                    "verifying": 40}
    assert done["reportedAt"] == at(100) and done["durationSeconds"] == 88
    runs.record_report(run["runId"], reference=f"evidence/migration/parity-{run['runId']}.json",
                       digest="a" * 64, kinds=1, reconciles=True)
    accept(runs, ledger, clock, run)

    # A second run, interrupted 5 s into importing and resumed 60 s later.
    go = rf.approval_record(ledger, "dry-run-go-ahead", "v1", now=clock())["approvalId"]
    second = runs.start("dry", tool_commit=COMMIT, go_ahead=go)["runId"]
    start = clock()
    runs.move(second, "copying")
    runs.move(second, "copying", snapshotStartedAt=utc_text(start))
    runs.move(second, "importing")
    clock.advance(5)
    runs.interrupt(second, "importing")
    clock.advance(60)
    runs.resume(second)
    clock.advance(7)
    runs.move(second, "verifying")
    runs.move(second, "reported")
    resumed = runs.require(second)
    assert resumed["interruptions"] == 1 and resumed["phaseSeconds"]["importing"] == 7
    assert resumed["durationSeconds"] == 72 >= 60
    runs.record_report(second, reference=f"evidence/migration/parity-{second}.json",
                       digest="a" * 64, kinds=1, reconciles=True)
    accept(runs, ledger, clock, resumed)

    # A run reported without `snapshotStartedAt`: its report time, no duration.
    bare = reported(runs, ledger, clock)
    assert "reportedAt" in runs.require(bare["runId"])
    assert "durationSeconds" not in runs.require(bare["runId"])


def test_corpus_contents_refusals_are_yours_to_decide(runs, ledger, clock):
    from docsuri_ops.migration.decisions import listing

    reason = "refused-by-database-time-limits"
    run = reported(runs, ledger, clock)
    added = runs.record_misfits(run["runId"], [
        ("paper", "2101.00006:v1", reason), ("paper", "2101.00001:v2", "paper-metadata-changed"),
        ("paper", "2101.00001:v1", "version-content-changed")])
    assert added == 3
    assert Decisions().of("paper", reason) is None
    assert Decisions().for_final_run().of("paper", reason) == "archive-only"
    assert disposition(Decisions(), "paper", reason) == "skipped"
    assert disposition(Decisions().for_final_run(), "paper", reason) == "excluded"
    row = next(item for item in listing(runs, run["runId"]) if item["reasonKey"] == reason)
    assert row["proposed"] is None and row["newInFinal"] is False
    # Met first by a final run, it is recorded new (`_import` passes the run's fresh
    # pairs, as `test_new_in_final_items_take_archive_only...` records them).
    accept(runs, ledger, clock, run)
    later = reported(runs, ledger, clock)
    runs.record_misfits(later["runId"], [("paper", "2101.00009:v1", reason)],
                        new_in_final={("paper", reason)})
    [row] = listing(runs, later["runId"])
    assert row["proposed"] is None and row["newInFinal"] is True
    assert ("paper", reason) not in PROPOSALS
