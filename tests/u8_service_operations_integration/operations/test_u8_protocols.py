"""Every precondition of A6's compatibility column (U8 plan Step 28; A6, BR9.15, BR9.17,
NFR8.15).

The preconditions are checked from the facts read just before each effect: the
platform profile, the ledger's recovery requests, cutover record and decisions, and the
instance's databases. Cases 1-6 state those facts exactly; case 7 and the live cases run
through the composed realm's PlatformControl store, where a wrong actor or target, or a
changed input under the same key, causes no effect.
"""

from __future__ import annotations

import json
import uuid

import psycopg
import pytest

from backend.local_profile import private_bytes
from docsuri_ops.platform_control import enums
from docsuri_ops.platform_control.errors import ControlError
from docsuri_ops.u8_platform import effect_kinds
from docsuri_ops.u8_platform.u8_protocols import (
    Operator,
    PreconditionRefused,
    admit_new_database,
    check,
    load_revision,
    refusal_error,
)
from tests.u8_service_operations_integration import platform_flows as pf
from tests.u8_service_operations_integration.service_flows import RecordingStore

PRODUCTION = pf.NAMES.production
PASSED_SET = {"backupId": "b-1", "integrity": "passed"}


def refused(name: str, target: str, inputs: dict, facts, reason: str) -> PreconditionRefused:
    with pytest.raises(PreconditionRefused) as caught:
        check(pf.protocol(name), target, inputs, facts)
    assert caught.value.reason == reason
    return caught.value


def admitted(name: str, target: str, inputs: dict, facts) -> None:
    check(pf.protocol(name), target, inputs, facts)


def restore(state: str, **extra) -> dict:
    return {"recoveryRequestId": "r-1", "operation": "restore.production", "state": state,
            "targetId": PRODUCTION, "evidenceRefs": [], "preRestoreBackupId": "b-1", **extra}


def ledger(*requests: dict, sets=(PASSED_SET,), approvals=(), cutovers=()) -> pf.Records:
    return pf.Records(recovery_request=list(requests), backup_set=list(sets),
                      maintainer_approval=list(approvals), cutover_record=list(cutovers))


RECREATE = {"database": PRODUCTION, "recoveryRequestId": "r-1"}
LIVE_OPEN = {"mode": "live", "admission": "open"}


# --- 0. the revision ---------------------------------------------------------------------


def test_the_revision_adds_a6s_fifteen_protocols_and_keeps_u7s_unchanged():
    revision = load_revision()
    assert revision.version == 2
    assert {p.name for p in revision.u8} == {
        "platform.database.backup", "platform.database.restore", "platform.database.recreate",
        "platform.database.remove", "platform.service.control", "platform.tunnel.route",
        "platform.isolation.check", "platform.profile.mode", "platform.profile.admission",
        "platform.profile.rehearsal-database", "platform.profile.backup-volume",
        "platform.copy.dispose", "platform.v1.lifecycle.apply", "platform.decision.record",
        "platform.ledger.copy"}
    assert all(p.effect_kind in effect_kinds.U8_EFFECT_KINDS for p in revision.u8)
    assert {p.effect_kind for p in revision.u7.protocols if p.effect_kind} <= set(
        enums.EFFECT_KINDS)
    # U7's loader still reads only `protocols`: none of A6's names reach it.
    assert not {p.name for p in revision.u7.protocols} & {p.name for p in revision.u8}
    # So U7's CLI (`executeControlled` admits by U7's loader) never runs one of A6's
    # protocols: they are reached only through the operator and its preconditions.
    from docsuri_ops.platform_control.inventory import load_inventory

    assert all(load_inventory().by_name(p.name) is None for p in revision.u8)
    assert pf.protocol("platform.database.recreate").authority_class == enums.CLASS_DESTRUCTIVE
    assert pf.protocol("platform.isolation.check").authority_class == enums.CLASS_ROUTINE


# --- 0b. C10's text names the scheduler's grants as the code holds them (the person's
# decision of 2026-10-25, "After the move, same build") -------------------------------------


def c10_inventory_description() -> str:
    """C10's inventory description, read from the canonical contract source."""
    import re
    from pathlib import Path

    import yaml

    source = (Path(__file__).resolve().parents[3] / "aidlc/spaces/default/intents/"
              "261010-docsuri-v2-rebuild/inception/contract-design/contract-summary.md")
    for body in re.findall(r"```yaml contract\n(.*?)\n```", source.read_text(), re.S):
        contract = yaml.safe_load(body)
        if contract["id"] == "C10":
            return contract["inventory"]["description"]
    raise AssertionError("no C10 contract in the canonical source")


def stated_grants(description: str) -> dict[str, tuple[tuple[str, ...], tuple[str, ...]]]:
    """Each grant the description states: `<grant>` runs <operations> on the targets
    <targets>, each name in backquotes, as {grant: (operations, targets)}."""
    import re

    def names(text: str) -> tuple[str, ...]:
        return tuple(re.findall(r"`([^`]+)`", text))

    return {grant: (names(operations), names(targets)) for grant, operations, targets in
            re.findall(r"`(\w+)` runs (.*?) on the targets (.*?)(?:;|\. |\.$)", description)}


def held_grants() -> dict[str, tuple[tuple[str, ...], tuple[str, ...]]]:
    from docsuri_ops.u8_platform.u8_protocols import SCHEDULER_GRANTS

    return {grant: (tuple(operations), tuple(scope))
            for grant, (scope, operations, _class) in SCHEDULER_GRANTS.items()}


def test_c10s_description_names_the_schedulers_grants_as_scheduler_grants_holds_them():
    description = c10_inventory_description()
    assert stated_grants(description) == held_grants()
    assert set(held_grants()) == {"schedulerRoutine", "schedulerRestore", "schedulerRemoval"}
    # The person's decision of 2026-10-26 ("Drop it"): the routine grant holds no
    # `platform.copy.dispose`, no grant does, and C10 says so.
    assert held_grants()["schedulerRoutine"] == (
        ("platform.database.backup", "platform.isolation.check", "platform.ledger.copy"),
        ("database-production", "database-rehearsal", "database-scratch", "copies",
         "isolation", "backup-volume", "ledger-copy"))
    assert all("platform.copy.dispose" not in operations
               for operations, _targets in held_grants().values())
    assert "No grant of the scheduler holds platform.copy.dispose" in description
    assert held_grants()["schedulerRemoval"] == (
        ("platform.database.remove",),
        ("database-rehearsal", "database-import", "database-scratch"))
    assert "only in the disposal pass, at its backstop" in description
    # The person's decisions of 2026-10-25 ("Production restore only in person") and
    # 2026-10-26 ("Give restore its own grant"): the scheduler's restore is a grant of its
    # own, over the scratch database alone, and C10 says so.
    assert held_grants()["schedulerRestore"] == (("platform.database.restore",),
                                                 ("database-scratch",))
    assert "standing authority is three grants" in description
    assert "A production restore runs only with the operator in person" in description
    assert "production-restore-in-person" in description
    # A planted mismatch, in a target, an operation or a grant, is found.
    restore_clause = ("`schedulerRestore` runs `platform.database.restore` on the targets "
                      "`database-scratch`")
    assert restore_clause in description
    for planted in (
        description.replace("`database-import`", "`database-production`"),
        description.replace(restore_clause, restore_clause.replace(
            "`database-scratch`", "`database-scratch` and `database-production`")),
        description.replace("`platform.isolation.check` and `platform.ledger.copy`",
                            "`platform.isolation.check`, `platform.database.restore` and "
                            "`platform.ledger.copy`"),
        # The grant before "Drop it", with the disposal, is a mismatch now.
        description.replace("`platform.isolation.check` and `platform.ledger.copy`",
                            "`platform.isolation.check`, `platform.copy.dispose` and "
                            "`platform.ledger.copy`"),
        description.replace("`schedulerRestore` runs", "`schedulerRestores` runs"),
    ):
        assert planted != description
        assert stated_grants(planted) != held_grants()


# --- 1. the recreate rules (seven cases) -------------------------------------------------


def test_recreate_case_1_is_refused_while_live_with_admission_open_and_no_restore():
    refused("platform.database.recreate", "database-production", {"database": PRODUCTION},
            pf.facts(**LIVE_OPEN), "recreate-refused-while-live-and-open")
    admitted("platform.database.recreate", "database-production", {"database": PRODUCTION},
             pf.facts(mode="live", admission="maintainer-only"))
    refused("platform.database.recreate", "database-production",
            {"database": pf.NAMES.new("rehearsal")}, pf.facts(), "database-refused")


def test_recreate_case_2_is_admitted_as_an_active_restores_bound_step_while_live_and_open():
    admitted("platform.database.recreate", "database-production", RECREATE,
             pf.facts(**LIVE_OPEN, ledger=ledger(restore("running"))))


@pytest.mark.parametrize("state", ["awaiting-operator", "verifying", "post-restore-pending"])
def test_recreate_case_3_is_refused_for_a_restore_not_at_its_step(state):
    refused("platform.database.recreate", "database-production", RECREATE,
            pf.facts(**LIVE_OPEN, ledger=ledger(restore(state))), "restore-not-at-its-step")


def test_recreate_case_4_is_refused_before_the_pre_restore_set_has_passed():
    for sets in ((), ({"backupId": "b-1", "integrity": "unchecked"},)):
        refused("platform.database.recreate", "database-production", RECREATE,
                pf.facts(**LIVE_OPEN, ledger=ledger(restore("running"), sets=sets)),
                "pre-restore-set-not-passed")
    # A successor request starts from its predecessor's verified point instead.
    admitted("platform.database.recreate", "database-production", RECREATE,
             pf.facts(**LIVE_OPEN, ledger=ledger(restore("running", predecessorRequestId="r-0"),
                                                 sets=())))


def test_recreate_case_5_is_refused_a_second_time_under_the_restore_exception():
    request = restore("running", evidenceRefs=["recreate:op-1"])
    refused("platform.database.recreate", "database-production", RECREATE,
            pf.facts(**LIVE_OPEN, ledger=ledger(request)), "recreate-already-done")


ABANDON = {**RECREATE, "abandonment": True}
DECIDED = {"approvalId": "a-1", "step": "restore-abandonment", "decision": "approved"}


def test_recreate_case_6_an_abandonments_recreate_may_follow_an_earlier_recreate():
    request = restore("held", evidenceRefs=["recreate:op-1"], abandonmentApprovalId="a-1")
    admitted("platform.database.recreate", "database-production", ABANDON,
             pf.facts(**LIVE_OPEN, ledger=ledger(request, approvals=(DECIDED,))))
    # Your decision is required, and no successor may be waiting.
    refused("platform.database.recreate", "database-production", ABANDON,
            pf.facts(**LIVE_OPEN, ledger=ledger(request)), "abandonment-not-decided")
    successor = {**restore("requested"), "recoveryRequestId": "r-2",
                 "predecessorRequestId": "r-1"}
    refused("platform.database.recreate", "database-production", ABANDON,
            pf.facts(**LIVE_OPEN, ledger=ledger(request, successor, approvals=(DECIDED,))),
            "successor-waiting")
    refused("platform.database.recreate", "database-production", ABANDON,
            pf.facts(**LIVE_OPEN, ledger=ledger({**request, "state": "running"},
                                                approvals=(DECIDED,))),
            "abandonment-not-held")


def test_recreate_case_7_an_abandonments_recreate_repeats_only_as_a_retry_after_a_failure():
    # A failed recreate settles not-applied and leaves no reference: the retry is admitted.
    failed = restore("held", evidenceRefs=["recreate:op-1"], abandonmentApprovalId="a-1")
    admitted("platform.database.recreate", "database-production", ABANDON,
             pf.facts(**LIVE_OPEN, ledger=ledger(failed, approvals=(DECIDED,))))
    done = {**failed, "evidenceRefs": ["recreate:op-1", "abandon-recreate:op-2"]}
    refused("platform.database.recreate", "database-production", ABANDON,
            pf.facts(**LIVE_OPEN, ledger=ledger(done, approvals=(DECIDED,))),
            "abandonment-recreated")


# --- 2. remove refuses the production and the current rehearsal database ----------------


def test_remove_refuses_the_production_and_the_current_rehearsal_database():
    current, other = pf.NAMES.new("rehearsal"), pf.NAMES.new("rehearsal")
    facts = pf.facts(rehearsal=current)
    refused("platform.database.remove", "database-production",
            {"database": PRODUCTION, "via": "in-person"}, facts, "target-refused")
    refused("platform.database.remove", "database-rehearsal",
            {"database": PRODUCTION, "via": "in-person"}, facts, "database-refused")
    refused("platform.database.remove", "database-rehearsal",
            {"database": current, "via": "in-person"}, facts, "current-rehearsal-database")
    admitted("platform.database.remove", "database-rehearsal",
             {"database": other, "via": "in-person"}, facts)
    refused("platform.database.remove", "database-scratch",
            {"database": other, "via": "standing"}, facts, "database-refused")


# --- 3. remove waits for an active rehearsal backup and admits none meanwhile ------------


@pytest.mark.parametrize("operation", ["backup.create", "restore.verify"])
def test_remove_waits_while_a_rehearsal_backup_or_verification_is_active(operation):
    name = pf.NAMES.new("rehearsal")
    active = {"recoveryRequestId": "r-9", "operation": operation, "state": "running",
              "targetId": name, "evidenceRefs": []}
    inputs = {"database": name, "via": "in-person"}
    waiting = refused("platform.database.remove", "database-rehearsal", inputs,
                      pf.facts(ledger=ledger(active)), "rehearsal-database-in-use")
    assert waiting.waiting is True
    error = refusal_error(waiting)
    assert error.retryable is True and error.details == {"messageKey": "rehearsal-database-in-use"}
    admitted("platform.database.remove", "database-rehearsal", inputs,
             pf.facts(ledger=ledger({**active, "state": "succeeded"})))


# --- the standing authority's one removal (BR4.2, BR9.17) -------------------------------


def database_copy(name: str, kind: str = "rehearsal-database", *,
                  dispose_after: str = "2026-10-22T11:00:00Z", **extra) -> dict:
    return {"copyId": f"copy-{name}", "kind": kind, "locations": [f"database/{name}"],
            "disposeAfter": dispose_after, **extra}


def standing_removal(name: str, copy_id: str | None = None) -> dict:
    return {"database": name, "via": "standing", "pass": "disposal",
            "copyId": copy_id or f"copy-{name}"}


def test_the_standing_removal_runs_only_in_the_disposal_pass_at_its_backstop():
    name = pf.NAMES.new("rehearsal")
    at_backstop = pf.facts(ledger=pf.Records(retained_copy=[database_copy(name)]))
    admitted("platform.database.remove", "database-rehearsal", standing_removal(name),
             at_backstop)
    # Outside the disposal pass: no pass named, another pass, or input beyond its own.
    for inputs in ({"database": name, "via": "standing"},
                   {**standing_removal(name), "pass": "housekeeping"},
                   {**standing_removal(name), "event": "settlement"}):
        refused("platform.database.remove", "database-rehearsal", inputs, at_backstop,
                "standing-removal-outside-disposal-pass")
    # Only for the copy that records this database there, still open.
    refused("platform.database.remove", "database-rehearsal",
            standing_removal(name, "copy-unknown"), at_backstop,
            "standing-removal-copy-unrecorded")
    other = pf.NAMES.new("rehearsal")
    refused("platform.database.remove", "database-rehearsal",
            standing_removal(other, f"copy-{name}"), at_backstop,
            "standing-removal-copy-unrecorded")
    for closed in ("disposedAt", "retiredWithVolumeAt", "returnedToServiceAt"):
        records = pf.Records(retained_copy=[database_copy(name, **{closed: "2026-10-22"})])
        refused("platform.database.remove", "database-rehearsal", standing_removal(name),
                pf.facts(ledger=records), "standing-removal-copy-unrecorded")
    wrong_kind = pf.Records(retained_copy=[database_copy(name, "import-database")])
    refused("platform.database.remove", "database-rehearsal", standing_removal(name),
            pf.facts(ledger=wrong_kind), "standing-removal-copy-unrecorded")
    # Never before its backstop date.
    early = pf.Records(retained_copy=[database_copy(name, dispose_after="2026-10-22T12:00:01Z")])
    refused("platform.database.remove", "database-rehearsal", standing_removal(name),
            pf.facts(ledger=early), "standing-removal-before-backstop")


def test_the_standing_removal_keeps_the_operations_own_refusals():
    name = pf.NAMES.new("rehearsal")
    records = pf.Records(retained_copy=[database_copy(name)])
    # Never the current rehearsal database, read from the latest profile receipt.
    refused("platform.database.remove", "database-rehearsal", standing_removal(name),
            pf.facts(ledger=records, rehearsal=name), "current-rehearsal-database")
    # Only the rehearsal, import and scratch patterns: never production, the store or
    # any other name.
    for database in (PRODUCTION, pf.NAMES.platform, "postgres", "docsuri_v2_rehearsal_"
                     + "a" * 12):
        refused("platform.database.remove", "database-rehearsal",
                standing_removal(database), pf.facts(ledger=records), "database-refused")
    refused("platform.database.remove", "database-production", standing_removal(PRODUCTION),
            pf.facts(ledger=records), "target-refused")


def test_the_standing_authority_is_refused_every_other_destructive_operation(tmp_path, realm):
    journey = pf.journey(tmp_path, realm, mode="live", admission="open")
    scheduler = journey.operator("scheduler")
    assert scheduler.standing is True
    destructive = [p for p in load_revision().u8
                   if p.authority_class == enums.CLASS_DESTRUCTIVE
                   and p.name != "platform.database.remove"]
    assert {p.name for p in destructive} == {
        "platform.database.recreate", "platform.service.control", "platform.tunnel.route",
        "platform.profile.mode", "platform.profile.admission",
        "platform.profile.rehearsal-database", "platform.profile.backup-volume",
        "platform.v1.lifecycle.apply",
    }
    for protocol in destructive:
        target = protocol.targets[0] if protocol.targets else pf.REALM_LABELS[0]
        for inputs in ({"via": "standing"}, {}):
            with pytest.raises(ControlError, match="no grant"):
                scheduler.execute(protocol.name, target, inputs,
                                  key=f"standing-{protocol.name}-{tmp_path.name}-{pf.RUN}")
    # Nothing in person either, not even its own removal.
    name = pf.NAMES.new("rehearsal")
    with pytest.raises(ControlError, match="only unattended"):
        scheduler.execute("platform.database.remove", "database-rehearsal",
                          {"database": name, "via": "in-person"},
                          key=f"standing-in-person-{tmp_path.name}-{pf.RUN}")
    # Outside the disposal pass, its removal is refused before anything is bound.
    with pytest.raises(PreconditionRefused, match="standing-removal-outside-disposal-pass"):
        scheduler.execute("platform.database.remove", "database-rehearsal",
                          {"database": name, "via": "standing"},
                          key=f"standing-outside-{tmp_path.name}-{pf.RUN}")
    assert not journey.profile.effects_root.joinpath("tunnel").exists()
    assert journey.tunnel() is None and journey.read_state("services") is None
    assert journey.read_state("profile.json")["mode"] == "live"


def production_restore(**extra) -> dict:
    return {"mode": "production", "database": PRODUCTION, "recoveryRequestId": "r-1",
            "setPath": "live/b-1.dump", "setSha256": "a" * 64, **extra}


def test_a_production_restore_runs_only_in_person(tmp_path, realm):
    """The person's decision of 2026-10-25, "Production restore only in person" (BR4.7):
    the standing authority's restore is refused with `production-restore-in-person`
    before anything is bound; the operator's in-person restore is admitted at its step."""
    running = ledger(restore("running", evidenceRefs=["recreate:x"]))
    # The precondition itself: only the in-person path, at the running request's step.
    admitted("platform.database.restore", "database-production",
             production_restore(via="in-person"), pf.facts(**LIVE_OPEN, ledger=running))
    for via in ("standing", None):
        inputs = production_restore(**({} if via is None else {"via": via}))
        refused("platform.database.restore", "database-production", inputs,
                pf.facts(**LIVE_OPEN, ledger=running), "production-restore-in-person")
    # In person still waits for its step: no running request, no restore.
    refused("platform.database.restore", "database-production",
            production_restore(via="in-person"), pf.facts(**LIVE_OPEN),
            "restore-not-at-its-step")
    # The standing authority, through the realm's store: refused before anything is bound,
    # whatever its input says.
    journey = pf.journey(tmp_path, realm, mode="live", admission="open")
    base = journey.operator("scheduler", ledger=running)
    store = RecordingStore(base.store)
    scheduler = Operator(journey.profile, store, actor=base.actor,
                         authorities=base.authorities, facts=base.facts, standing=True)
    for via in ("standing", "in-person"):
        with pytest.raises(PreconditionRefused) as caught:
            scheduler.execute("platform.database.restore", "database-production",
                              production_restore(via=via),
                              key=f"standing-restore-{via}-{tmp_path.name}-{pf.RUN}")
        assert caught.value.reason == "production-restore-in-person"
        assert refusal_error(caught.value).as_wire_error()["messageKey"] == (
            "production-restore-in-person")
    assert store.bound == []


def test_the_schedulers_restore_grant_restores_a_scratch_database_only(tmp_path, realm):
    """`SCHEDULER_GRANTS`' restore grant (the person's decision of 2026-10-26, "Give
    restore its own grant") covers `platform.database.restore` of a scratch database (the
    restore verification) and no other target; the routine grant holds no restore."""
    from docsuri_ops.u8_platform.u8_protocols import (
        SCHEDULER_GRANTS,
        STANDING_RESTORE_TARGETS,
    )

    assert STANDING_RESTORE_TARGETS == ("database-scratch",)
    assert SCHEDULER_GRANTS["schedulerRestore"][:2] == (("database-scratch",),
                                                        ("platform.database.restore",))
    assert "platform.database.restore" not in SCHEDULER_GRANTS["schedulerRoutine"][1]
    journey = pf.journey(tmp_path, realm)
    base = journey.operator("scheduler")
    grants = json.loads(private_bytes(journey.profile.run_root / "platform-authorities.json"))
    assert base.operation_grants == {
        "platform.database.restore": grants["authorities"]["schedulerRestore"]}
    store = RecordingStore(base.store)
    scheduler = Operator(journey.profile, store, actor=base.actor,
                         authorities=base.authorities, operation_grants=base.operation_grants,
                         facts=base.facts, standing=True)
    # A scratch restore is bound under the restore grant (U7's injected permission fault
    # settles it failed without running the effect, so no database is created).
    receipt = scheduler.execute("platform.database.restore", "database-scratch",
                                scratch_restore(pf.NAMES),
                                key=f"scratch-restore-{tmp_path.name}-{pf.RUN}",
                                injected_fault="permission")
    assert receipt["outcome"] == "failed"
    assert ("operation", "platform.database.restore") in store.bound
    assert receipt["authorityRef"] == grants["authorities"]["schedulerRestore"]
    store.bound.clear()
    with pytest.raises(PreconditionRefused, match="production-restore-in-person"):
        scheduler.execute("platform.database.restore", "database-production",
                          production_restore(via="standing"),
                          key=f"scheduler-production-{tmp_path.name}-{pf.RUN}")
    assert store.bound == []


def test_the_removal_grant_covers_nothing_else_in_the_store(tmp_path, realm):
    """Below the operator's own guard, U7's store holds the grant to its one operation
    and its three targets."""
    journey = pf.journey(tmp_path, realm)
    base = journey.operator("scheduler")
    grants = json.loads(private_bytes(journey.profile.run_root / "platform-authorities.json"))
    removal = grants["authorities"]["schedulerRemoval"]
    unguarded = Operator(journey.profile, base.store, actor=base.actor,
                         authorities={enums.CLASS_DESTRUCTIVE: removal}, facts=base.facts)
    with pytest.raises(ControlError):
        unguarded.execute("platform.tunnel.route", "tunnel", {"origin": "v2-host"},
                          key=f"removal-tunnel-{tmp_path.name}-{pf.RUN}")
    assert journey.tunnel() is None
    label = "dev.docsuri.u8.run.workers"
    with pytest.raises(ControlError):
        unguarded.execute("platform.service.control", label,
                          {"label": label, "action": "stop"},
                          key=f"removal-service-{tmp_path.name}-{pf.RUN}")
    assert journey.read_state("services", f"{label}.json") is None


def test_the_store_refuses_the_scheduler_a_production_restore_under_either_grant(
        tmp_path, realm):
    """The person's decision of 2026-10-26 ("Give restore its own grant"): below the
    operator's own guard (an operator that is not standing, so `production-restore-in-
    person` never runs), U7's store holds the restore grant to the scratch database
    alone and the routine grant to no restore at all, so neither binds a production
    restore that every precondition admits, nor the routine grant a scratch restore."""
    running = ledger(restore("running", evidenceRefs=["recreate:x"]))
    journey = pf.journey(tmp_path, realm, mode="live", admission="open")
    base = journey.operator("scheduler", ledger=running)
    grants = json.loads(private_bytes(journey.profile.run_root / "platform-authorities.json"))
    held = grants["authorities"]
    # The store's own refusal, by its message (review finding, Minor, R15): the restore
    # grant does not hold production as a target; the routine grant holds production as
    # a target (its backups) but no restore.
    for name, refusal in (("schedulerRestore", "target outside authority scope"),
                          ("schedulerRoutine", "operation outside authority scope")):
        store = RecordingStore(base.store)
        unguarded = Operator(journey.profile, store, actor=base.actor,
                             authorities={enums.CLASS_ROUTINE: held[name]}, facts=base.facts)
        # Every precondition admits it: the refusal is the store's.
        check(pf.protocol("platform.database.restore"), "database-production",
              production_restore(via="in-person"), base.facts())
        with pytest.raises(ControlError) as caught:
            unguarded.execute("platform.database.restore", "database-production",
                              production_restore(via="in-person"),
                              key=f"store-production-{name}-{tmp_path.name}-{pf.RUN}")
        assert caught.value.code == "FORBIDDEN", caught.value.code
        assert refusal in str(caught.value.__cause__), caught.value.__cause__
        assert ("operation", "platform.database.restore") in store.bound
    # The routine grant no longer covers even the restore verification's scratch restore:
    # the binding was reached, and the store refused the operation.
    store = RecordingStore(base.store)
    routine = Operator(journey.profile, store, actor=base.actor,
                       authorities={enums.CLASS_ROUTINE: held["schedulerRoutine"]},
                       facts=journey.operator("scheduler").facts, standing=True)
    with pytest.raises(ControlError) as caught:
        routine.execute("platform.database.restore", "database-scratch",
                        scratch_restore(pf.NAMES),
                        key=f"store-scratch-routine-{tmp_path.name}-{pf.RUN}",
                        injected_fault="permission")
    assert caught.value.code == "FORBIDDEN"
    assert "operation outside authority scope" in str(caught.value.__cause__)
    assert ("operation", "platform.database.restore") in store.bound
    # Nothing was restored: production's database is as the realm made it.
    assert journey.read_state("profile.json")["mode"] == "live"


# --- 4. a rehearsal database's disposal: profile, database, sets ------------------------


def test_a_rehearsal_databases_disposal_completes_in_the_order_profile_database_sets():
    name = pf.NAMES.new("rehearsal")
    a_set = {"backupId": "b-7", "databaseIncarnation": f"{name}:1",
             "retainUntil": "2026-10-01T00:00:00Z", "integrity": "passed"}
    records = ledger(sets=(a_set,))
    dispose = {"recordKind": "BackupSet", "recordId": "b-7", "place": "backup-volume",
               "location": "live/b-7.dump"}
    remove = {"database": name, "via": "in-person"}
    # The profile still names it: neither the database nor its sets may go.
    named = pf.facts(rehearsal=name, ledger=records, databases={name})
    refused("platform.database.remove", "database-rehearsal", remove, named,
            "current-rehearsal-database")
    refused("platform.copy.dispose", "copies", dispose, named, "current-rehearsal-database")
    # The profile no longer names it: the database goes first, then its sets.
    cleared = pf.facts(ledger=records, databases={name})
    refused("platform.copy.dispose", "copies", dispose, cleared, "rehearsal-database-not-removed")
    admitted("platform.database.remove", "database-rehearsal", remove, cleared)
    admitted("platform.copy.dispose", "copies", dispose, pf.facts(ledger=records))


def test_disposal_goes_through_each_places_one_path_at_its_point():
    a_copy = {"copyId": "c-1", "disposeAfter": "2026-10-23T00:00:00Z"}
    records = pf.Records(retained_copy=[a_copy])
    inputs = {"recordKind": "RetainedCopy", "recordId": "c-1", "place": "backup-volume",
              "location": "copies/c-1.tar"}
    refused("platform.copy.dispose", "copies", inputs, pf.facts(ledger=records),
            "disposal-point-not-reached")
    admitted("platform.copy.dispose", "copies", {**inputs, "event": "settlement"},
             pf.facts(ledger=records))
    refused("platform.copy.dispose", "copies", {**inputs, "place": "elsewhere"},
            pf.facts(ledger=records), "place-refused")
    refused("platform.copy.dispose", "copies", {**inputs, "recordKind": "Other"},
            pf.facts(ledger=records), "record-kind-refused")
    switching = records.with_record("cutover-record", {"cutoverId": "x", "state": "switching"})
    held = refused("platform.copy.dispose", "copies", {**inputs, "event": "settlement"},
                   pf.facts(ledger=switching), "live-exclusion-held")
    assert held.waiting is True


def recorded(names, *, disposed: bool = False) -> tuple[pf.Records, str, str, dict]:
    """A ledger holding one rehearsal database's copy and set, and one scratch database
    kept as a retained copy (its drop failed), as production's ledger records them."""
    rehearsal, scratch = names.new("rehearsal"), names.new("scratch")
    closed = {"disposedAt": "2026-10-21T00:00:00Z"} if disposed else {}
    copies = [{"copyId": "c-r", "kind": "rehearsal-database",
               "locations": [f"database/{rehearsal}"], **closed},
              {"copyId": "c-s", "kind": "scratch-restore",
               "locations": [f"database/{scratch}"], **closed},
              {"copyId": "c-o", "kind": "rehearsal-database",
               "locations": [f"database/{names.new('rehearsal')}"],
               "disposedAt": "2026-10-20T00:00:00Z"}]
    a_set = {"backupId": "b-7", "databaseIncarnation": f"{rehearsal}:1",
             "retainUntil": "2026-10-01T00:00:00Z", "integrity": "passed"}
    dispose = {"recordKind": "BackupSet", "recordId": "b-7", "place": "backup-volume",
               "location": "rehearsal/b-7.dump"}
    return pf.Records(retained_copy=copies, backup_set=[a_set]), rehearsal, scratch, dispose


def scratch_restore(names) -> dict:
    return {"scratchDatabase": names.new("scratch"), "mode": "scratch",
            "setKind": "live-set", "via": "standing"}


def test_productions_facts_list_the_recorded_databases_so_the_guards_refuse():
    """Built as `production_wiring` builds them: A6's "profile, database, sets" guard and
    NFR8.15's scratch limit read the ledger's open database copies, so both refuse while a
    rehearsal database or a kept scratch database is still recorded, and admit once each
    copy is disposed."""
    from docsuri_ops.arrangement.paths import PRODUCTION_DATABASES
    from docsuri_ops.production_wiring import production_facts

    records, rehearsal, scratch, dispose = recorded(PRODUCTION_DATABASES)
    facts = production_facts(records, clock=lambda: pf.NOW)()
    assert facts.current_rehearsal is None and facts.databases() == {rehearsal, scratch}
    refused("platform.copy.dispose", "copies", dispose, facts, "rehearsal-database-not-removed")
    refused("platform.database.restore", "database-scratch",
            scratch_restore(PRODUCTION_DATABASES), facts, "scratch-database-limit")
    closed, *_ = recorded(PRODUCTION_DATABASES, disposed=True)
    facts = production_facts(closed, clock=lambda: pf.NOW)()
    assert facts.databases() == set()
    admitted("platform.database.restore", "database-scratch",
             scratch_restore(PRODUCTION_DATABASES), facts)


def test_the_realms_facts_list_the_recorded_databases_too(tmp_path, realm):
    from docsuri_ops.u8_platform.u8_protocols import realm_facts

    journey = pf.journey(tmp_path, realm)
    records, rehearsal, scratch, dispose = recorded(pf.NAMES)
    facts = realm_facts(journey.profile, records, clock=lambda: pf.NOW)()
    assert facts.databases() == {rehearsal, scratch}
    refused("platform.copy.dispose", "copies", dispose, facts, "rehearsal-database-not-removed")
    refused("platform.database.restore", "database-scratch", scratch_restore(pf.NAMES), facts,
            "scratch-database-limit")
    # A caller's own lister still takes precedence.
    named = realm_facts(journey.profile, records, clock=lambda: pf.NOW,
                        databases=lambda: set())()
    assert named.databases() == set()


# --- 5. the database counts (NFR8.15) ----------------------------------------------------


def test_the_database_counts_admit_two_rehearsal_one_import_and_one_scratch():
    two = {pf.NAMES.new("rehearsal") for _ in range(2)}
    admit_new_database("rehearsal", {next(iter(two))}, pf.NAMES)
    with pytest.raises(PreconditionRefused, match="rehearsal-database-limit"):
        admit_new_database("rehearsal", two, pf.NAMES)
    admit_new_database("import", two, pf.NAMES)
    with pytest.raises(PreconditionRefused, match="import-database-limit"):
        admit_new_database("import", {pf.NAMES.new("import")}, pf.NAMES)
    scratch = pf.NAMES.new("scratch")
    inputs = {"scratchDatabase": pf.NAMES.new("scratch"), "mode": "scratch",
              "setKind": "live-set", "via": "standing"}
    admitted("platform.database.restore", "database-scratch", inputs, pf.facts())
    refused("platform.database.restore", "database-scratch", inputs,
            pf.facts(databases={scratch}), "scratch-database-limit")
    refused("platform.database.restore", "database-scratch",
            {**inputs, "scratchDatabase": PRODUCTION}, pf.facts(), "scratch-name-refused")


# --- 6. profile changes outside their step ------------------------------------------------


def cutover(state: str) -> pf.Records:
    return pf.Records(cutover_record=[{"cutoverId": "c-1", "state": state}],
                      maintainer_approval=[
                          {"approvalId": "a-open", "step": "admission-opening",
                           "decision": "approved"},
                          {"approvalId": "a-vol", "step": "backup-volume-retirement",
                           "decision": "approved"}])


def test_profile_changes_are_refused_outside_their_step():
    mode = {"field": "mode", "value": "live"}
    refused("platform.profile.mode", "profile", mode, pf.facts(), "profile-change-outside-step")
    refused("platform.profile.mode", "profile", mode, pf.facts(ledger=cutover("rehearsing")),
            "profile-change-outside-step")
    admitted("platform.profile.mode", "profile", mode, pf.facts(ledger=cutover("switching")))
    admitted("platform.profile.mode", "profile", {"field": "mode", "value": "rehearsal"},
             pf.facts(ledger=cutover("rolling-back")))
    # A protocol changes only its own field, and only to a value it knows.
    refused("platform.profile.mode", "profile", {"field": "admission", "value": "open"},
            pf.facts(ledger=cutover("switching")), "profile-field-refused")
    refused("platform.profile.mode", "profile", {"field": "mode", "value": "chaos"},
            pf.facts(ledger=cutover("switching")), "profile-value-refused")


def test_the_rehearsal_database_may_change_while_a_rollback_runs():
    """Your decision of 2026-10-24 ("Create a fresh rehearsal database"): at v1's serving
    the rollback sets its new rehearsal database, so that change is admitted while a
    rollback runs, and still refused during the switch and the abort."""
    change = {"field": "rehearsalDatabase", "value": pf.NAMES.new("rehearsal")}
    admitted("platform.profile.rehearsal-database", "profile", change,
             pf.facts(ledger=cutover("rolling-back")))
    for state in ("switching", "aborting", "settled"):
        refused("platform.profile.rehearsal-database", "profile", change,
                pf.facts(ledger=cutover(state)), "profile-change-outside-step")
    # Only a rehearsal database's name, even while a rollback runs.
    refused("platform.profile.rehearsal-database", "profile",
            {"field": "rehearsalDatabase", "value": PRODUCTION},
            pf.facts(ledger=cutover("rolling-back")), "profile-value-refused")


def test_opening_admission_and_retiring_the_volume_need_your_decision():
    opening = {"field": "admission", "value": "open"}
    refused("platform.profile.admission", "profile", opening,
            pf.facts(ledger=cutover("switching")), "admission-not-decided")
    admitted("platform.profile.admission", "profile", {**opening, "approvalId": "a-open"},
             pf.facts(ledger=cutover("switching")))
    volume = {"field": "backupVolume", "value": {"identity": "new"}}
    refused("platform.profile.backup-volume", "profile", volume,
            pf.facts(ledger=cutover("switched")), "retirement-not-decided")
    admitted("platform.profile.backup-volume", "profile", {**volume, "approvalId": "a-vol"},
             pf.facts(ledger=cutover("switched")))
    refused("platform.profile.rehearsal-database", "profile",
            {"field": "rehearsalDatabase", "value": PRODUCTION},
            pf.facts(ledger=cutover("rehearsing")), "profile-value-refused")
    admitted("platform.profile.rehearsal-database", "profile",
             {"field": "rehearsalDatabase", "value": None}, pf.facts(ledger=cutover("switched")))


def test_service_control_acts_on_one_label_and_tunnel_routing_on_one_of_three_origins():
    label = "dev.docsuri.u8.run.host"
    admitted("platform.service.control", label, {"label": label, "action": "stop"}, pf.facts())
    refused("platform.service.control", "org.docsuri.v2.host",
            {"label": "org.docsuri.v2.host", "action": "stop"}, pf.facts(), "target-refused")
    refused("platform.service.control", label, {"label": "dev.docsuri.u8.run.workers",
                                                "action": "stop"}, pf.facts(), "label-refused")
    refused("platform.service.control", label, {"label": label, "action": "restart"},
            pf.facts(), "action-refused")
    # During a production restore, v2's jobs start only once their start is authorised.
    active = restore("running")
    refused("platform.service.control", label, {"label": label, "action": "start"},
            pf.facts(ledger=ledger(active)), "restore-active-without-start-authorization")
    admitted("platform.service.control", label, {"label": label, "action": "start"},
             pf.facts(ledger=ledger({**active, "startAuthorizedAt": "2026-10-22T12:00:00Z"})))
    for origin in ("v1-web", "v2-host", "maintenance"):
        admitted("platform.tunnel.route", "tunnel", {"origin": origin}, pf.facts())
    refused("platform.tunnel.route", "tunnel", {"origin": "elsewhere"}, pf.facts(),
            "origin-refused")


def test_v1_lifecycle_apply_runs_only_during_a_rollback():
    inputs = {"outcomes": [], "accounts": []}
    refused("platform.v1.lifecycle.apply", "v1-accounts", inputs, pf.facts(), "not-rolling-back")
    admitted("platform.v1.lifecycle.apply", "v1-accounts", inputs,
             pf.facts(ledger=cutover("rolling-back")))
    refused("platform.v1.lifecycle.apply", "v1-accounts", {"outcomes": {}, "accounts": []},
            pf.facts(ledger=cutover("rolling-back")), "input-refused")


def test_backups_and_isolation_checks_name_their_database_and_authority():
    admitted("platform.database.backup", "database-production",
             {"database": PRODUCTION, "via": "standing", "recordId": "b"}, pf.facts())
    refused("platform.database.backup", "database-rehearsal",
            {"database": PRODUCTION, "via": "standing"}, pf.facts(), "database-refused")
    refused("platform.database.backup", "database-production",
            {"database": PRODUCTION, "via": "anyone"}, pf.facts(), "authority-refused")
    admitted("platform.isolation.check", "isolation", {"via": "standing"}, pf.facts())
    refused("platform.isolation.check", "isolation", {"via": "standing", "extra": 1},
            pf.facts(), "input-refused")


# --- 7. a wrong actor or target, or a changed input, causes no effect --------------------


def isolation_results(journey) -> list:
    folder = journey.state / "isolation"
    return sorted(folder.iterdir()) if folder.exists() else []


def test_a_wrong_target_causes_no_effect(tmp_path, realm):
    journey = pf.journey(tmp_path, realm)
    with pytest.raises(PreconditionRefused, match="target-refused"):
        journey.operator().execute("platform.isolation.check", "tunnel",
                                   {"via": "in-person"}, key=f"target-{tmp_path.name}-{pf.RUN}")
    with pytest.raises(ControlError):
        journey.operator().execute("platform.unknown", "isolation", {"via": "in-person"},
                                   key=f"unknown-{tmp_path.name}-{pf.RUN}")
    assert isolation_results(journey) == []
    assert not (journey.profile.effects_root / "tunnel").exists()


def test_a_wrong_actor_causes_no_effect(tmp_path, realm):
    journey = pf.journey(tmp_path, realm)
    recorded = json.loads(private_bytes(journey.profile.run_root / "platform-authorities.json"))
    grants = recorded["authorities"]
    base = journey.operator()
    # The operator's name with the scheduler's grant: U7's store refuses the binding.
    impostor = Operator(journey.profile, base.store, actor=recorded["actors"]["operator"],
                        authorities={enums.CLASS_ROUTINE: grants["schedulerRoutine"]},
                        facts=base.facts)
    with pytest.raises(ControlError):
        impostor.execute("platform.isolation.check", "isolation", {"via": "in-person"},
                         key=f"actor-{tmp_path.name}-{pf.RUN}")
    # The scheduler's standing grant covers no destructive effect.
    with pytest.raises(ControlError, match="no grant"):
        journey.operator("scheduler").execute("platform.tunnel.route", "tunnel",
                                              {"origin": "v2-host"},
                                              key=f"scheduler-{tmp_path.name}-{pf.RUN}")
    assert isolation_results(journey) == [] and journey.tunnel() is None


def test_a_changed_input_under_the_same_key_causes_no_effect(tmp_path, realm):
    journey = pf.journey(tmp_path, realm)
    operator = journey.operator()
    key = f"same-key-{tmp_path.name}-{pf.RUN}"
    first = operator.execute("platform.isolation.check", "isolation", {"via": "in-person"},
                             key=key)
    assert first["outcome"] == "succeeded" and len(isolation_results(journey)) == 1
    # The same input under the same key replays the receipt and runs nothing again.
    again = operator.execute("platform.isolation.check", "isolation", {"via": "in-person"},
                             key=key)
    assert again["receiptId"] == first["receiptId"] and len(isolation_results(journey)) == 1
    # Named as a replay, so a caller retrying a failed step can tell it from a new one.
    assert again["replayed"] is True and "replayed" not in first
    with pytest.raises(ControlError):
        operator.execute("platform.isolation.check", "isolation", {"via": "standing"}, key=key)
    assert len(isolation_results(journey)) == 1


# --- the live effects of the realm driver -------------------------------------------------


def test_service_control_writes_the_wanted_state_and_a_bounded_stop_record(tmp_path, realm):
    journey = pf.journey(tmp_path, realm)
    label = "dev.docsuri.u8.run.workers"
    stopped = journey.operator().execute("platform.service.control", label,
                                         {"label": label, "action": "stop"},
                                         key=f"stop-{tmp_path.name}-{pf.RUN}")
    assert stopped["outcome"] == "succeeded"
    assert journey.read_state("services", f"{label}.json")["state"] == "stopped"
    record = journey.read_state("stops", f"{label}.json")
    assert record["operationId"] == stopped["operationId"]
    from datetime import datetime

    span = (datetime.fromisoformat(record["expiresAt"])
            - datetime.fromisoformat(record["stoppedAt"]))
    assert span.days == 14
    started = journey.operator().execute("platform.service.control", label,
                                         {"label": label, "action": "start"},
                                         key=f"start-{tmp_path.name}-{pf.RUN}")
    assert started["outcome"] == "succeeded"
    assert journey.read_state("services", f"{label}.json")["state"] == "running"
    assert journey.read_state("stops", f"{label}.json") is None


def test_a_profile_change_applies_at_its_step_with_its_receipt(tmp_path, realm):
    journey = pf.journey(tmp_path, realm, mode="rehearsal", admission="maintainer-only")
    operator = journey.operator(ledger=cutover("switching"))
    receipt = operator.execute("platform.profile.mode", "profile",
                               {"field": "mode", "value": "live"},
                               key=f"mode-{tmp_path.name}-{pf.RUN}")
    state = journey.read_state("profile.json")
    assert state["mode"] == "live" and state["receiptOperationId"] == receipt["operationId"]
    with pytest.raises(PreconditionRefused, match="profile-change-outside-step"):
        journey.operator(ledger=cutover("rehearsing")).execute(
            "platform.profile.mode", "profile", {"field": "mode", "value": "rehearsal"},
            key=f"mode-again-{tmp_path.name}-{pf.RUN}")
    assert journey.read_state("profile.json")["mode"] == "live"


def _admin(realm):
    password = json.loads(private_bytes(realm.root / "migration-credentials.json"))[
        "databaseAdminPassword"]
    return psycopg.connect(host="127.0.0.1", port=realm.database_port, dbname="postgres",
                           user="postgres", password=password, autocommit=True,
                           connect_timeout=5)


def test_a_rehearsal_database_leaves_the_profile_before_it_is_removed(tmp_path, realm):
    name = pf.NAMES.new("rehearsal")
    with _admin(realm) as conn:
        conn.execute(f'CREATE DATABASE "{name}" OWNER docsuri_disposable')
    journey = pf.journey(tmp_path, realm, rehearsal=name)
    try:
        remove = {"database": name, "via": "in-person"}
        with pytest.raises(PreconditionRefused, match="current-rehearsal-database"):
            journey.operator().execute("platform.database.remove", "database-rehearsal", remove,
                                       key=f"remove-early-{tmp_path.name}-{pf.RUN}")
        journey.operator(ledger=cutover("switched")).execute(
            "platform.profile.rehearsal-database", "profile",
            {"field": "rehearsalDatabase", "value": None}, key=f"clear-{tmp_path.name}-{pf.RUN}")
        removed = journey.operator().execute("platform.database.remove", "database-rehearsal",
                                             remove, key=f"remove-{tmp_path.name}-{pf.RUN}")
        assert removed["outcome"] == "succeeded", removed
        with _admin(realm) as conn:
            assert conn.execute("SELECT 1 FROM pg_database WHERE datname = %s",
                                (name,)).fetchone() is None
    finally:
        with _admin(realm) as conn:
            conn.execute(f'DROP DATABASE IF EXISTS "{name}"')


# --- each login bound to its actor (your decision of 2026-10-26) ------------------------------


def _authorities(journey) -> dict:
    return json.loads(private_bytes(journey.profile.run_root / "platform-authorities.json"))


def _raw(store, function: str, params: tuple):
    """One of U7's own functions called by name, past U8's guarded ones."""
    from docsuri_ops.platform_control.store import Store

    return Store.call_committed(store, function, params)


def test_the_scheduler_login_naming_your_actor_is_refused_at_the_store(tmp_path, realm):
    """The scheduler's own login cannot bind under your actor and grant, nor reach U7's
    own `begin_operation` past U8's guard; the store refuses before anything is bound,
    and the operator's login binding under its own actor still works. This case is
    refused by the grant check and U7's revokes as well; the cases that only the login's
    binding can refuse follow (review finding, Major, R17)."""
    journey = pf.journey(tmp_path, realm)
    scheduler, operator = journey.operator("scheduler"), journey.operator()
    recorded = _authorities(journey)
    yours = recorded["authorities"]["operatorRoutine"]
    forged = Operator(journey.profile, scheduler.store, actor=recorded["actors"]["operator"],
                      authorities={enums.CLASS_ROUTINE: yours}, facts=scheduler.facts)
    with pytest.raises(ControlError) as caught:
        forged.execute("platform.tunnel.route", "tunnel", {"origin": "v2-host"},
                       key=f"forged-{tmp_path.name}-{pf.RUN}")
    assert caught.value.code == "FORBIDDEN"
    assert journey.tunnel() is None
    # Past U8's guard, U7's own functions are not the runtime role's in this store.
    evidence = scheduler.store.record_evidence(
        target="tunnel", input_hash="a" * 64, environment=journey.profile.environment,
        observations={"preconditions": "passed"}, max_age_seconds=60)
    with pytest.raises(ControlError):
        _raw(scheduler.store, "begin_operation", (
            recorded["actors"]["operator"], yours, "platform.tunnel.route", "tunnel", "a" * 64,
            journey.profile.environment, str(evidence["evidenceId"]),
            int(evidence["generation"]), f"raw-{tmp_path.name}", "tunnel/effect-x.json"))
    receipt = operator.execute("platform.tunnel.route", "tunnel", {"origin": "v1-web"},
                               key=f"yours-{tmp_path.name}-{pf.RUN}")
    assert receipt["outcome"] == "succeeded", receipt
    # Nor may the scheduler settle, reconcile or mark your operation.
    with pytest.raises(ControlError):
        scheduler.store.settle_operation(operation_id=str(receipt["operationId"]),
                                         outcome="failed", disposition="not-applied",
                                         effect_refs=[])
    with pytest.raises(ControlError):
        scheduler.store.reconcile_receipt(operation_id=str(receipt["operationId"]),
                                          applied=False, evidence=["forged"])
    with pytest.raises(ControlError):
        _raw(scheduler.store, "settle_operation", (str(receipt["operationId"]), "failed",
                                                   "not-applied", psycopg.types.json.Jsonb([])))


DECISION = "platform.decision.record"


def _store_rows(realm, journey, query: str, params: tuple) -> list[tuple]:
    """Rows of PlatformControl's own tables, read as the instance's administrator."""
    password = json.loads(private_bytes(realm.root / "migration-credentials.json"))[
        "databaseAdminPassword"]
    with psycopg.connect(host="127.0.0.1", port=journey.profile.port,
                         dbname=journey.profile.database, user="postgres", password=password,
                         autocommit=True, connect_timeout=5) as conn:
        return conn.execute(query, params).fetchall()


def _operation(realm, journey, operation_id: str) -> tuple:
    (row,) = _store_rows(realm, journey, (
        "SELECT o.state, o.effect_disposition, r.outcome, r.reconciliation_state "
        "FROM platform_control.operation o JOIN platform_control.receipt r USING "
        "(operation_id) WHERE o.operation_id = %s"), (operation_id,))
    return row


def _refused_by_binding(call, message: str) -> None:
    """The store refuses with FORBIDDEN (42501), and the refusal is U8's binding's own."""
    with pytest.raises(ControlError) as caught:
        call()
    assert caught.value.code == "FORBIDDEN", caught.value
    cause = caught.value.__cause__
    assert getattr(cause, "sqlstate", None) == "42501", cause
    assert message in str(cause), cause


def _begin(store, journey, actor: str, authority: str, key: str, inputs: dict) -> dict:
    """One decision bound on `decisions` through `store`'s own login: its evidence, then
    the binding, under `actor` and `authority`."""
    from docsuri_ops.u8_platform.drivers import input_hash

    digest = input_hash(inputs)
    evidence = store.record_evidence(
        target="decisions", input_hash=digest, environment=journey.profile.environment,
        observations={"preconditions": "passed", "operation": DECISION}, max_age_seconds=60)
    return store.begin_operation(
        actor=actor, authority_id=authority, operation=DECISION, target="decisions",
        input_hash=digest, environment=journey.profile.environment,
        evidence_id=str(evidence["evidenceId"]), generation=int(evidence["generation"]),
        idempotency_key=key, effect_reference=f"decisions/effect-{key}.json")


def _settle_left(operator, realm, journey, operation: str) -> None:
    """A test's own operation left authorized or executing is settled failed through your
    login, so it never holds the `decisions` target's lease for a later test."""
    state = _operation(realm, journey, operation)[0]
    if state == "authorized":
        operator.store.mark_executing(operation)
        state = "executing"
    if state == "executing":
        operator.store.settle_operation(operation_id=operation, outcome="failed",
                                        disposition="not-applied", effect_refs=[])


def test_the_scheduler_login_cannot_bind_under_your_actor_with_a_grant_that_covers_it(
        tmp_path, realm):
    """Only the login's binding can refuse this (review finding, Major, R17): the scheduler
    login calls `u8_begin_operation` naming your actor and your routine grant, which covers
    `platform.decision.record` on `decisions`. U7's guard would admit it (the same call
    through your login binds), so the refusal is the binding's, and nothing is bound."""
    journey = pf.journey(tmp_path, realm)
    scheduler, operator = journey.operator("scheduler"), journey.operator()
    recorded = _authorities(journey)
    yours, actor = recorded["authorities"]["operatorRoutine"], recorded["actors"]["operator"]
    inputs = {**pf.DECISION_INPUTS, "subjectRef": f"binding-{tmp_path.name}"}
    forged = f"forged-begin-{tmp_path.name}-{pf.RUN}"
    _refused_by_binding(lambda: _begin(scheduler.store, journey, actor, yours, forged, inputs),
                        "actor is not the calling login's")
    assert _store_rows(realm, journey, "SELECT 1 FROM platform_control.operation "
                       "WHERE idempotency_key = %s", (forged,)) == []
    # The same binding through your own login is admitted: the grant covers it.
    own = f"own-begin-{tmp_path.name}-{pf.RUN}"
    bound = _begin(operator.store, journey, actor, yours, own, inputs)
    operation = str(bound["operationId"])
    try:
        assert _operation(realm, journey, operation)[0] == "authorized"
    finally:
        _settle_left(operator, realm, journey, operation)


def test_the_scheduler_login_cannot_mark_settle_or_reconcile_your_live_operation(
        tmp_path, realm):
    """Only the login's binding can refuse these (review finding, Major, R17): while your
    operation is authorized, then executing, then unknown and unresolved, U7 would admit
    each call, yet the scheduler login's `u8_mark_executing`, `u8_settle_operation` and
    `u8_reconcile_receipt` are refused as another actor's, and the operation is unchanged;
    your own login then moves it each time."""
    journey = pf.journey(tmp_path, realm)
    scheduler, operator = journey.operator("scheduler"), journey.operator()
    recorded = _authorities(journey)
    inputs = {**pf.DECISION_INPUTS, "subjectRef": f"live-{tmp_path.name}"}
    bound = _begin(operator.store, journey, recorded["actors"]["operator"],
                   recorded["authorities"]["operatorRoutine"],
                   f"live-{tmp_path.name}-{pf.RUN}", inputs)
    operation = str(bound["operationId"])
    another = "operation bound by another actor"

    def settle(store, outcome: str, disposition: str):
        return lambda: store.settle_operation(operation_id=operation, outcome=outcome,
                                              disposition=disposition, effect_refs=[])

    try:
        # Authorized: no mark, no settle.
        before = _operation(realm, journey, operation)
        assert before[0] == "authorized"
        _refused_by_binding(lambda: scheduler.store.mark_executing(operation), another)
        _refused_by_binding(settle(scheduler.store, "failed", "not-applied"), another)
        assert _operation(realm, journey, operation) == before
        # Executing: no settle.
        operator.store.mark_executing(operation)
        before = _operation(realm, journey, operation)
        _refused_by_binding(settle(scheduler.store, "unknown", "unknown"), another)
        assert _operation(realm, journey, operation) == before and before[0] == "executing"
        # Unknown and unresolved: no reconciliation.
        settle(operator.store, "unknown", "unknown")()
        _refused_by_binding(lambda: scheduler.store.reconcile_receipt(
            operation_id=operation, applied=True, evidence=["forged"]), another)
        assert _operation(realm, journey, operation) == ("unknown", "unknown", "unknown",
                                                         "unresolved")
        operator.store.reconcile_receipt(operation_id=operation, applied=False,
                                         evidence=["test-cleanup"])
        assert _operation(realm, journey, operation)[3] == "reconciled-not-applied"
    finally:
        _settle_left(operator, realm, journey, operation)


def test_an_unbound_login_is_refused_by_every_guarded_function(tmp_path, realm):
    """A login bound to no actor (the realm's shared runtime login, a member of U7's
    runtime role) holds EXECUTE on U8's guarded functions, and every one refuses it
    (review finding, Major, R17), changing nothing: no evidence, no binding, and your
    live operation untouched."""
    journey = pf.journey(tmp_path, realm)
    operator = journey.operator()
    recorded = _authorities(journey)
    actor, yours = recorded["actors"]["operator"], recorded["authorities"]["operatorRoutine"]
    inputs = {**pf.DECISION_INPUTS, "subjectRef": f"unbound-{tmp_path.name}"}
    bound = _begin(operator.store, journey, actor, yours, f"unbound-{tmp_path.name}-{pf.RUN}",
                   inputs)
    operation = str(bound["operationId"])
    try:
        _every_guarded_function_refuses(realm, journey, operation, actor, yours,
                                        f"unbound-forged-{tmp_path.name}-{pf.RUN}")
    finally:
        _settle_left(operator, realm, journey, operation)


def _every_guarded_function_refuses(realm, journey, operation: str, actor: str, yours: str,
                                    key: str) -> None:
    from docsuri_ops.platform_control import RUNTIME_ROLE
    from docsuri_ops.u8_platform.platform_profile import GUARDED_FUNCTIONS

    shared = journey.profile.store(RUNTIME_ROLE, journey.profile.realm_password("runtime"))
    evidence_before = _store_rows(realm, journey, "SELECT count(*) FROM "
                                  "platform_control.evidence", ())
    before = _operation(realm, journey, operation)
    calls = {
        "record_evidence": ("decisions", "a" * 64, journey.profile.environment,
                            psycopg.types.json.Jsonb({}), 60),
        "begin_operation": (actor, yours, DECISION, "decisions", "a" * 64,
                            journey.profile.environment, str(uuid.uuid4()), 1, key,
                            "decisions/effect-x.json"),
        "mark_executing": (operation,),
        "settle_operation": (operation, "failed", "not-applied", psycopg.types.json.Jsonb([])),
        "reconcile_receipt": (operation, False, psycopg.types.json.Jsonb([])),
        "promote_in_flight": (),
        "read_receipt": (actor, yours, operation),
        "read_receipt_named": (actor, yours, operation),
        "latest_evidence": (actor, yours, "decisions"),
        "list_unresolved": (actor, yours),
        "status_counts": (actor, yours),
    }
    assert set(calls) == set(GUARDED_FUNCTIONS)
    for name, params in calls.items():
        _refused_by_binding(lambda name=name, params=params: shared.call_committed(
            GUARDED_FUNCTIONS[name], params), "login bound to no actor")
    assert _store_rows(realm, journey, "SELECT count(*) FROM platform_control.evidence",
                       ()) == evidence_before
    assert _store_rows(realm, journey, "SELECT 1 FROM platform_control.operation "
                       "WHERE idempotency_key = %s", (key,)) == []
    assert _operation(realm, journey, operation) == before and before[0] == "authorized"


def test_the_reader_login_reads_and_cannot_act(tmp_path, realm):
    """The reader login holds only the read functions: it reads a receipt as its own actor,
    is refused reading as another, and cannot record evidence, bind or settle, through
    U8's functions or U7's own; and a login is never rebound to another actor."""
    from docsuri_ops.platform_control import PROVISIONER_ROLE
    from docsuri_ops.u8_platform.platform_profile import store_logins
    from docsuri_ops.u8_platform.u8_protocols import bind_store_logins, readers

    journey = pf.journey(tmp_path, realm)
    operator = journey.operator()
    receipt = operator.execute("platform.tunnel.route", "tunnel", {"origin": "v1-web"},
                               key=f"read-{tmp_path.name}-{pf.RUN}")
    reader = readers(journey.profile)[0]
    assert reader.read(str(receipt["operationId"]))["operation"] == "platform.tunnel.route"
    recorded = _authorities(journey)
    with pytest.raises(ControlError):
        reader.store.call_committed("read_receipt_named", (
            recorded["actors"]["operator"], recorded["authorities"]["operatorRoutine"],
            str(receipt["operationId"])))
    with pytest.raises(ControlError):
        reader.store.record_evidence(target="tunnel", input_hash="b" * 64,
                                     environment=journey.profile.environment,
                                     observations={}, max_age_seconds=60)
    with pytest.raises(ControlError):
        reader.store.settle_operation(operation_id=str(receipt["operationId"]),
                                      outcome="failed", disposition="not-applied",
                                      effect_refs=[])
    for function, params in (
            ("record_evidence", ("tunnel", "b" * 64, journey.profile.environment,
                                 psycopg.types.json.Jsonb({}), 60)),
            ("u8_promote_in_flight", ())):
        with pytest.raises(ControlError):
            _raw(reader.store, function, params)
    # The binding holds: rebinding the reader's login to your actor is refused.
    provisioner = journey.profile.store(PROVISIONER_ROLE,
                                        journey.profile.realm_password("provisioner"))
    actors = recorded["actors"]
    assert len(bind_store_logins(provisioner, store_logins("realm"), actors)) == 3
    with pytest.raises(ControlError):
        bind_store_logins(provisioner, {"reader": store_logins("realm")["reader"]},
                          {**actors, "service": actors["operator"]})


def test_the_provisioner_reads_each_logins_binding_back(tmp_path, realm):
    """Review findings (Minor, R16 and R17): the provisioner reads each store login's
    binding back (`u8_login_bindings`): the realm's three logins are bound to their
    actors with their kinds, the reader is no member of the runtime role while the
    acting logins are, an unknown login is unbound, and `login_binding_drift` answers
    nothing for the installed bindings and names a login bound to another actor; the
    runtime login holds no such read."""
    from docsuri_ops.platform_control import PROVISIONER_ROLE, RUNTIME_ROLE
    from docsuri_ops.u8_platform.platform_profile import store_logins
    from docsuri_ops.u8_platform.u8_protocols import login_binding_drift

    journey = pf.journey(tmp_path, realm)
    actors = _authorities(journey)["actors"]
    logins = store_logins("realm")
    provisioner = journey.profile.store(PROVISIONER_ROLE,
                                        journey.profile.realm_password("provisioner"))
    held = provisioner.call_committed("u8_login_bindings",
                                      ([*logins.values(), "docsuri_nobody"],))
    assert held[logins["operator"]] == {"bound": True, "actor": actors["operator"],
                                        "kind": "operator", "runtimeMember": True}
    assert held[logins["scheduler"]] == {"bound": True, "actor": actors["scheduler"],
                                         "kind": "scheduler", "runtimeMember": True}
    assert held[logins["reader"]] == {"bound": True, "actor": actors["service"],
                                      "kind": "reader", "runtimeMember": False}
    assert held["docsuri_nobody"] == {"bound": False, "actor": None, "kind": None,
                                      "runtimeMember": False}
    assert login_binding_drift(provisioner, logins, actors) == []
    assert login_binding_drift(provisioner, logins, {**actors, "scheduler": "x"}) == [
        "scheduler"]
    assert login_binding_drift(provisioner, {**logins, "reader": "docsuri_nobody"},
                               actors) == ["reader"]
    shared = journey.profile.store(RUNTIME_ROLE, journey.profile.realm_password("runtime"))
    with pytest.raises(ControlError):
        shared.call_committed("u8_login_bindings", ([logins["reader"]],))


class StubReceipts:
    def __init__(self, receipt: dict):
        self.receipt = receipt

    def read(self, operation_id: str) -> dict:
        return self.receipt


def test_a_decision_confirmation_citing_a_scheduler_receipt_is_refused(tmp_path):
    """The ledger's decision confirmation requires the receipt's grant to be your
    in-person grant: a decision receipt bound under the scheduler's grant is refused,
    one under yours is admitted, and with no grants known no decision is confirmed."""
    import io
    import uuid

    from backend.modules.operations.ledger_cli import (
        LedgerCommand,
        decision_input_hash,
        in_person_authorities,
        run,
    )

    grants = tmp_path / "platform-authorities.json"
    yours, theirs = str(uuid.uuid4()), str(uuid.uuid4())
    grants.write_text(json.dumps({"authorities": {
        "operatorRoutine": yours, "operatorDestructive": str(uuid.uuid4()),
        "schedulerRoutine": theirs}}))
    assert yours in in_person_authorities(grants)
    assert theirs not in in_person_authorities(grants)
    assert in_person_authorities(tmp_path / "absent.json") == frozenset()

    def attempt(authority: str, authorities) -> dict:
        folder = tmp_path / f"ledger-{uuid.uuid4().hex[:8]}"
        folder.mkdir(mode=0o700)
        receipt_id = str(uuid.uuid4())
        record = {"approvalId": str(uuid.uuid4()), "step": "production-restore",
                  "subjectRef": "restore:r-1", "subjectDigest": "d" * 64,
                  "decision": "approved", "recordedAt": "2026-10-26T00:00:00.000Z",
                  "operatorReceiptRef": receipt_id}
        # The receipt binds this decision's inputs (review finding, Major, R17).
        facts = {"receiptId": receipt_id, "operationId": str(uuid.uuid4()),
                 "operation": "platform.decision.record", "targetId": "decisions",
                 "inputHash": decision_input_hash(record), "outcome": "succeeded"}
        command = LedgerCommand(folder=folder, evidence=tmp_path,
                                receipts=StubReceipts({**facts, "authorityRef": authority}),
                                decision_authorities=authorities)
        stdout = io.BytesIO()
        run(["append"], command, environ={}, stdin=io.BytesIO(json.dumps({
            "kind": "maintainer-approval", "record": record, "expectRevision": 0,
            "receipts": [facts]}).encode()), stdout=stdout, stderr=io.BytesIO())
        return json.loads(stdout.getvalue().decode().splitlines()[-1])

    held = in_person_authorities(grants)
    assert attempt(theirs, held)["reason"] == "decision-receipt-not-in-person"
    assert attempt(yours, None)["reason"] == "decision-receipt-not-in-person"
    admitted_answer = attempt(yours, held)
    assert admitted_answer["ok"] is True, admitted_answer


# --- the second review's findings of 2026-10-26 (Minor, R13 and R15) ---------------------


@pytest.mark.parametrize("inputs", [
    {"place": "database", "location": "x"},
    {"place": "v1-stores", "locations": []},
    {"place": "backup-volume", "location": "x", "event": "run-ended"},
    {"place": "backup-volume", "location": "x", "event": "settlement"},
    # The two cases the routine grant admitted before the person's decision of
    # 2026-10-26 ("Drop it"): a backup-volume copy at its disposal point, and the
    # rehearsal-database-removed event.
    {"place": "backup-volume", "location": "x"},
    {"place": "backup-volume", "location": "x", "event": "rehearsal-database-removed"},
])
def test_the_standing_authority_disposes_of_no_copy(tmp_path, realm, inputs):
    """The person's decision of 2026-10-26 ("Drop it"; Step 44 test item 1): a standing
    `platform.copy.dispose` is refused whatever its place or event, before anything is
    bound, and the store's routine grant (provisioned from `SCHEDULER_GRANTS`) holds no
    disposal either, so an operator built without the guard is refused by the store."""
    from docsuri_ops.u8_platform.u8_protocols import SCHEDULER_GRANTS

    journey = pf.journey(tmp_path, realm)
    base = journey.operator("scheduler")
    store = RecordingStore(base.store)
    scheduler = Operator(journey.profile, store, actor=base.actor,
                         authorities=base.authorities, operation_grants=base.operation_grants,
                         facts=base.facts, standing=True)
    disposal = {"recordKind": "BackupSet", "recordId": "b-1", "via": "standing", **inputs}
    with pytest.raises(ControlError) as caught:
        scheduler.execute("platform.copy.dispose", "copies", disposal,
                          key=f"standing-dispose-{tmp_path.name}-{pf.RUN}")
    assert caught.value.code == "FORBIDDEN" and "disposes of no copy" in str(caught.value)
    assert store.bound == []
    assert "platform.copy.dispose" not in SCHEDULER_GRANTS["schedulerRoutine"][1]
    # Below the guard: the store's own routine grant refuses the scheduler the operation
    # (U7's permission fault binds nothing: the grant check comes first).
    a_copy = {"copyId": "c-1", "disposeAfter": "2026-10-01T00:00:00Z"}
    unguarded = Operator(journey.profile, store, actor=base.actor,
                         authorities=base.authorities, operation_grants=base.operation_grants,
                         facts=lambda: pf.facts(ledger=pf.Records(retained_copy=[a_copy])))
    with pytest.raises(ControlError) as refused:
        unguarded.execute("platform.copy.dispose", "copies",
                          {"recordKind": "RetainedCopy", "recordId": "c-1",
                           "place": "backup-volume", "location": "copies/c-1.tar"},
                          key=f"store-dispose-{tmp_path.name}-{pf.RUN}")
    assert refused.value.code == "FORBIDDEN"
    assert "operation outside authority scope" in str(refused.value.__cause__)


def test_the_rehearsal_database_removed_event_covers_only_a_rehearsal_set():
    """The event disposes only of a BackupSet whose source is a rehearsal database that is
    removed; a retained copy, or a set of another database, cited with it is refused."""
    name = pf.NAMES.new("rehearsal")
    a_copy = {"copyId": "c-1", "disposeAfter": "2030-01-01T00:00:00Z"}
    live_set = {"backupId": "b-2", "databaseIncarnation": f"{PRODUCTION}:1",
                "retainUntil": "2030-01-01T00:00:00Z", "integrity": "passed"}
    rehearsal_set = {"backupId": "b-3", "databaseIncarnation": f"{name}:1",
                     "retainUntil": "2030-01-01T00:00:00Z", "integrity": "passed"}
    records = pf.Records(retained_copy=[a_copy], backup_set=[live_set, rehearsal_set])
    event = {"place": "backup-volume", "location": "x", "event": "rehearsal-database-removed"}
    refused("platform.copy.dispose", "copies",
            {"recordKind": "RetainedCopy", "recordId": "c-1", **event},
            pf.facts(ledger=records), "disposal-event-refused")
    refused("platform.copy.dispose", "copies",
            {"recordKind": "BackupSet", "recordId": "b-2", **event},
            pf.facts(ledger=records), "disposal-event-refused")
    admitted("platform.copy.dispose", "copies",
             {"recordKind": "BackupSet", "recordId": "b-3", **event}, pf.facts(ledger=records))


def test_no_disposal_starts_while_an_install_holds_the_live_exclusion():
    """Review finding (Minor, R13; BR4.4): the disposal's precondition waits on a release
    record holding the exclusion, as it waits on a cutover's switch, abort or rollback."""
    a_copy = {"copyId": "c-1", "disposeAfter": "2026-10-01T00:00:00Z"}
    inputs = {"recordKind": "RetainedCopy", "recordId": "c-1", "place": "backup-volume",
              "location": "copies/c-1.tar"}
    records = pf.Records(retained_copy=[a_copy])
    admitted("platform.copy.dispose", "copies", inputs, pf.facts(ledger=records))
    for state in ("installing", "rolling-back"):
        holding = records.with_record("release-record", {"releaseTag": "v2.1.0",
                                                         "state": state})
        caught = refused("platform.copy.dispose", "copies", inputs, pf.facts(ledger=holding),
                         "live-exclusion-held")
        assert caught.waiting is True
    ended = records.with_record("release-record", {"releaseTag": "v2.1.0", "state": "failed"})
    admitted("platform.copy.dispose", "copies", inputs, pf.facts(ledger=ended))


class Authorities:
    """`read_authority` as the provisioner reads it, over stated grants."""

    def __init__(self, held: dict):
        self.held = held

    def read_authority(self, authority_id):
        if authority_id not in self.held:
            raise ControlError("NOT_FOUND", "unknown authority")
        return self.held[authority_id]


def store_grants(actor: str) -> tuple[dict, dict]:
    from docsuri_ops.u8_platform.u8_protocols import SCHEDULER_GRANTS

    authorities, held = {}, {}
    for name, (scope, operations, authority_class) in SCHEDULER_GRANTS.items():
        identity = f"id-{name}"
        authorities[name] = identity
        held[identity] = {"actorReference": actor, "targetScope": list(scope),
                          "permittedOperation": list(operations),
                          "authorityClass": authority_class, "revokedAt": None}
    return authorities, held


def test_a_store_whose_scheduler_grants_differ_is_found(tmp_path, realm):
    """Review finding (Minor, R15): `grant_drift` compares each provisioned scheduler
    grant with `SCHEDULER_GRANTS`: a routine grant that still holds a restore, a missing
    restore grant, a revoked grant, another actor's or another class's are each named;
    the realm's own store, as migrate provisioned it, holds exactly them."""
    from pathlib import Path

    from docsuri_ops.platform_control import PROVISIONER_ROLE
    from docsuri_ops.u8_platform.platform_profile import U8PlatformProfile
    from docsuri_ops.u8_platform.u8_protocols import grant_drift

    authorities, held = store_grants("scheduler")
    assert grant_drift(Authorities(held), authorities, "scheduler") == []
    old = {**held, "id-schedulerRoutine": {
        **held["id-schedulerRoutine"],
        "permittedOperation": [*held["id-schedulerRoutine"]["permittedOperation"],
                               "platform.database.restore"]}}
    assert grant_drift(Authorities(old), authorities, "scheduler") == ["schedulerRoutine"]
    # A store provisioned before the person's decision of 2026-10-26 ("Drop it"), whose
    # routine grant still holds the disposal, is found too (Step 44 test item 1).
    disposing = {**held, "id-schedulerRoutine": {
        **held["id-schedulerRoutine"],
        "permittedOperation": [*held["id-schedulerRoutine"]["permittedOperation"],
                               "platform.copy.dispose"]}}
    assert grant_drift(Authorities(disposing), authorities, "scheduler") == ["schedulerRoutine"]
    missing = {name: value for name, value in authorities.items()
               if name != "schedulerRestore"}
    assert grant_drift(Authorities(held), missing, "scheduler") == ["schedulerRestore"]
    revoked = {**held, "id-schedulerRemoval": {**held["id-schedulerRemoval"],
                                               "revokedAt": "2026-10-26T00:00:00Z"}}
    assert grant_drift(Authorities(revoked), authorities, "scheduler") == ["schedulerRemoval"]
    assert grant_drift(Authorities(held), authorities, "someone-else") == list(authorities)
    wider = {**held, "id-schedulerRestore": {**held["id-schedulerRestore"],
                                             "targetScope": ["database-scratch",
                                                             "database-production"]}}
    assert grant_drift(Authorities(wider), authorities, "scheduler") == ["schedulerRestore"]
    # The realm's store, read as its provisioner.
    profile = U8PlatformProfile.realm(Path(realm.root))
    recorded = json.loads(private_bytes(profile.run_root / "platform-authorities.json"))
    provisioner = profile.store(PROVISIONER_ROLE, profile.realm_password("provisioner"))
    assert grant_drift(provisioner, recorded["authorities"],
                       recorded["actors"]["scheduler"]) == []


def test_credentials_without_the_restore_grant_give_the_scheduler_no_restore(tmp_path, realm):
    """P17's deviation, now covered (review finding, Minor, R15): a credentials record
    provisioned before the restore grant (no `schedulerRestore`) gives the scheduler no
    restore; its scratch restore falls to the routine grant, and the store refuses it."""
    from docsuri_ops.u8_platform.u8_protocols import scheduler_authorities

    journey = pf.journey(tmp_path, realm)
    grants = json.loads(private_bytes(journey.profile.run_root / "platform-authorities.json"))
    older = {name: value for name, value in grants["authorities"].items()
             if name != "schedulerRestore"}
    held = scheduler_authorities(older)
    assert held["operation_grants"] == {}
    base = journey.operator("scheduler")
    store = RecordingStore(base.store)
    scheduler = Operator(journey.profile, store, actor=base.actor, facts=base.facts,
                         standing=True, **held)
    with pytest.raises(ControlError) as caught:
        scheduler.execute("platform.database.restore", "database-scratch",
                          scratch_restore(pf.NAMES),
                          key=f"older-credentials-{tmp_path.name}-{pf.RUN}",
                          injected_fault="permission")
    assert caught.value.code == "FORBIDDEN"
    assert "operation outside authority scope" in str(caught.value.__cause__)
    assert ("operation", "platform.database.restore") in store.bound


# --- Step 65(g) and (i): the scratch place, the lone copy and the open-operations reader ----


def test_a_scratch_restore_admits_its_own_recorded_database_and_refuses_a_second():
    own, other = pf.NAMES.new("scratch"), pf.NAMES.new("scratch")
    inputs = {"scratchDatabase": own, "mode": "scratch", "setKind": "live-set",
              "via": "standing"}
    admitted("platform.database.restore", "database-scratch", inputs, pf.facts(databases={own}))
    refused("platform.database.restore", "database-scratch", inputs,
            pf.facts(databases={own, other}), "scratch-database-limit")


LONE = {"via": "standing", "environment": "live"}


def test_the_lone_ledger_copy_is_admitted_while_the_environment_is_held():
    held = ledger(restore("running"), cutovers=({"cutoverId": "c-1", "state": "switching"},))
    admitted("platform.ledger.copy", "ledger-copy", LONE, pf.facts(mode="live", ledger=held))
    admitted("platform.ledger.copy", "ledger-copy", {"via": "in-person",
                                                     "environment": "rehearsal"}, pf.facts())
    refused("platform.ledger.copy", "ledger-copy", {**LONE, "database": PRODUCTION},
            pf.facts(), "input-refused")
    refused("platform.ledger.copy", "ledger-copy", {"via": "standing"}, pf.facts(),
            "input-refused")
    refused("platform.ledger.copy", "ledger-copy", {**LONE, "environment": "staging"},
            pf.facts(), "environment-refused")
    refused("platform.ledger.copy", "backup-volume", LONE, pf.facts(), "target-refused")
    # The standing scope admits it before anything is bound.
    Operator._standing_scope(pf.protocol("platform.ledger.copy"), "ledger-copy", dict(LONE))


class Cut(BaseException):
    """A process stopped in the middle of an effect: the operation stays executing."""


def _outcome(status: str):
    from docsuri_ops.platform_control.executor import EffectOutcome

    return EffectOutcome(status, effect_refs=[] if status != "applied" else ["x/applied"])


def _settle_open(operator, realm, journey, operation: str) -> None:
    """A test's own operation left open is settled through the login that bound it: one
    still authorized or executing failed and not applied, one already promoted or unknown
    reconciled not applied, so no later erase waits on it."""
    state = _operation(realm, journey, operation)
    if state[0] in ("authorized", "executing"):
        _settle_left(operator, realm, journey, operation)
    elif state[3] == "unresolved":
        operator.store.reconcile_receipt(operation_id=operation, applied=False,
                                         evidence=["test-cleanup"])


OPEN = ("platform.database.backup", "platform.ledger.copy")


def test_the_reader_lists_open_backup_and_ledger_copy_operations(tmp_path, realm):
    from docsuri_ops.u8_platform.u8_protocols import readers

    journey = pf.journey(tmp_path, realm)
    inspector = readers(journey.profile)[2]
    seen: list[list[dict]] = []
    status = "applied"

    def run_effect(**request):
        seen.append(inspector.open_operations(OPEN))
        return _outcome(status)

    operator = journey.operator(run_effect=run_effect)
    backup = {"database": PRODUCTION, "recordId": str(uuid.uuid4()), "via": "in-person"}
    receipt = operator.execute("platform.database.backup", "database-production", backup,
                               key=f"open-{tmp_path.name}-{pf.RUN}")
    operation = str(receipt["operationId"])
    try:
        [during] = seen
        assert operation in {item["operationId"] for item in during}
        assert all(item["operation"] in OPEN for item in during)
        assert operation not in {item["operationId"] for item in inspector.open_operations(OPEN)}
        # An unknown outcome stays listed until it is reconciled.
        status = "unknown"
        unknown = operator.execute("platform.database.backup", "database-production",
                                   {**backup, "recordId": str(uuid.uuid4())},
                                   key=f"open-unknown-{tmp_path.name}-{pf.RUN}")
        left = str(unknown["operationId"])
        try:
            assert left in {item["operationId"] for item in inspector.open_operations(OPEN)}
        finally:
            _settle_open(operator, realm, journey, left)
        assert left not in {item["operationId"] for item in inspector.open_operations(OPEN)}
        # Another protocol is never listed, and the reader still cannot act.
        status = "applied"
        isolation = operator.execute("platform.isolation.check", "isolation",
                                     {"via": "in-person"},
                                     key=f"open-isolation-{tmp_path.name}-{pf.RUN}")
        assert str(isolation["operationId"]) not in {
            item["operationId"] for item in seen[-1]}
        assert all(item["operation"] in OPEN for item in inspector.open_operations(OPEN))
        with pytest.raises(ControlError):
            inspector.store.record_evidence(target="ledger-copy", input_hash="b" * 64,
                                            environment=journey.profile.environment,
                                            observations={}, max_age_seconds=60)
    finally:
        _settle_open(operator, realm, journey, operation)


def test_a_lone_copy_leaves_the_agents_status_where_capacity_reads_it(tmp_path, realm):
    from docsuri_ops.backup_agent.status import EvidenceStatus
    from docsuri_ops.u8_platform.u8_protocols import readers

    journey = pf.journey(tmp_path, realm)
    scheduler = journey.operator("scheduler", run_effect=lambda **request: _outcome("applied"))
    observations = {"available": True, "volumeIdentity": f"standin-{tmp_path.name}",
                    "deletionAllowed": True, "findings": []}
    scheduler.store.record_evidence(target="backup-volume", input_hash="a" * 64,
                                    environment=journey.profile.environment,
                                    observations=observations, max_age_seconds=600)
    receipt = scheduler.execute("platform.ledger.copy", "ledger-copy", dict(LONE),
                                key=f"lone-status-{tmp_path.name}-{pf.RUN}")
    assert receipt["outcome"] == "succeeded", receipt
    evidence = readers(journey.profile)[1]
    assert evidence("ledger-copy")["observations"]["operation"] == "platform.ledger.copy"
    assert EvidenceStatus(evidence)() == observations


def test_an_interrupted_lone_copy_is_settled_by_the_actor_that_bound_it(tmp_path, realm, clock):
    from docsuri_ops.u8_platform.recovery_words import realm_procedures
    from docsuri_ops.u8_platform.u8_protocols import readers, reconcile_unresolved
    from tests.u8_service_operations_integration import recovery_flows as rf

    journey = pf.journey(tmp_path, realm)
    inspector = readers(journey.profile)[2]

    def cut(**request):
        raise Cut()

    scheduler = journey.operator("scheduler", run_effect=cut)
    key = f"lone-cut-{tmp_path.name}-{pf.RUN}"
    with pytest.raises(Cut):
        scheduler.execute("platform.ledger.copy", "ledger-copy", dict(LONE), key=key)
    # The try opens before the lookup (review fix, batch 4).
    try:
        [(operation,)] = _store_rows(realm, journey, (
            "SELECT operation_id::text FROM platform_control.operation "
            "WHERE idempotency_key = %s"), (key,))
        _store_rows(realm, journey, (
            "UPDATE platform_control.target_lease SET deadline_at = clock_timestamp() - "
            "interval '1 second' WHERE operation_id = %s RETURNING operation_id"), (operation,))
        assert operation in {item["operationId"] for item in inspector.open_operations(OPEN)}
        # Your login promotes it and cannot settle it: it is the scheduler's.
        reconcile_unresolved(journey.operator(), "ledger-copy")
        assert _operation(realm, journey, operation)[3] == "unresolved"
        ledger = rf.open_ledger(tmp_path, clock)
        try:
            standing = realm_procedures(journey.profile, ledger, clock=clock, role="scheduler")
            standing.procedures.reconcile_interrupted(("ledger-copy",))
        finally:
            ledger.close()
        assert _operation(realm, journey, operation)[3] == "reconciled-not-applied"
        assert operation not in {item["operationId"] for item in inspector.open_operations(OPEN)}
    finally:
        for (bound,) in _store_rows(realm, journey, (
                "SELECT operation_id::text FROM platform_control.operation "
                "WHERE starts_with(idempotency_key, %s)"), (key,)):
            _settle_open(journey.operator("scheduler"), realm, journey, bound)


def test_an_unbound_login_cannot_list_open_operations(tmp_path, realm):
    from docsuri_ops.platform_control import RUNTIME_ROLE

    journey = pf.journey(tmp_path, realm)
    recorded = _authorities(journey)
    shared = journey.profile.store(RUNTIME_ROLE, journey.profile.realm_password("runtime"))
    _refused_by_binding(lambda: shared.call_committed("u8_open_operations", (
        recorded["actors"]["service"], recorded["authorities"]["serviceReader"], list(OPEN))),
        "login bound to no actor")


# --- Step 164(a): every PlatformControl store login demands SCRAM (NFR3.3; L4-12) --------


def _production_stores(port: int, password: str) -> dict:
    """Production's store for each login, aimed at `port`: the operator's, the
    scheduler's and the reader's bound logins, the profile's fallback for one of U7's own
    roles, and the provisioner's store as the installer builds it."""
    import dataclasses

    from docsuri_ops.arrangement.installer import ProductionDatabase
    from docsuri_ops.platform_control import PROVISIONER_ROLE
    from docsuri_ops.u8_platform.platform_profile import U8PlatformProfile, store_logins

    production = U8PlatformProfile.production()
    assert (production.port, production.database) == (15432, "docsuri_v2_platform")
    aimed = dataclasses.replace(production, port=port)
    stores = {kind: aimed.store(login, password)
              for kind, login in store_logins("production").items()}
    stores["fallback"] = aimed.store(PROVISIONER_ROLE, password)
    provisioner = ProductionDatabase(None).store(password)
    assert (provisioner.target.host, provisioner.target.port, provisioner.target.dbname,
            provisioner.role) == ("127.0.0.1", 15432, "docsuri_v2_platform", PROVISIONER_ROLE)
    provisioner.target = dataclasses.replace(provisioner.target, port=port)
    stores["provisioner"] = provisioner
    return stores


def test_every_platform_store_login_refuses_a_listener_that_skips_scram(tmp_path, realm):
    """NFR3.3: a listener in the instance's place that asks for a cleartext password,
    for MD5 or for nothing is refused by every store login before any password is sent,
    with U7's own error. The composed realm's three logins complete the exchange."""
    import secrets

    from docsuri_ops.platform_control.errors import DEPENDENCY_UNAVAILABLE
    from docsuri_ops.u8_platform.platform_profile import store_logins
    from tests.u8_service_operations_integration.component.test_transactions_scram import (
        CLEARTEXT,
        MD5,
        STANDIN_PORT,
        TRUST,
        WeakAuthStandin,
    )

    stores = _production_stores(STANDIN_PORT, secrets.token_hex(16))  # made per run (L1-36)
    assert set(stores) == {"operator", "scheduler", "reader", "fallback", "provisioner"}
    assert {stores[kind].role for kind in ("operator", "scheduler", "reader")} == set(
        store_logins("production").values())
    for kind, store in stores.items():
        for request in (CLEARTEXT, MD5, TRUST):
            with WeakAuthStandin(request) as standin:
                with pytest.raises(ControlError) as caught:
                    with store.connection():
                        pass
            assert standin.passwords_seen == 0, (kind, request)
            assert caught.value.code == DEPENDENCY_UNAVAILABLE and caught.value.retryable
            assert isinstance(caught.value.__cause__, psycopg.OperationalError), kind
            assert "scram-sha-256" in str(caught.value.__cause__), (kind, request)
    # The realm's own logins authenticate with the option: nothing but SCRAM is asked.
    profile = pf.journey(tmp_path, realm).profile
    for kind, login in store_logins("realm").items():
        with profile.store(login, profile.realm_password(kind)).connection() as conn:
            assert conn.execute("SELECT current_user::text").fetchone()[0] == login
