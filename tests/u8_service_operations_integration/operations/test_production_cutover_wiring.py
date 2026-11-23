"""The production cutover's wiring, `cutover begin` / `check` and the readiness waits (U8 plan
Step 34; your decisions of 2026-10-24; BR9.1–BR9.7).

The cutover commands run over the composed realm's PlatformControl store and realm driver
on the journey's own platform state (the component suite's `Stage`), with the clock and
the readiness waits' sleep injected, so no real wait runs. Production's wiring is put
together from installer-shaped files under a temporary prefix; its readers are driven
with recorded answers, and nothing reaches this Mac's arrangement, v1 or the network.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import secrets
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from backend.modules.operations.errors import OperationsError
from backend.modules.operations.incidents import Incidents
from backend.modules.operations.provider_activation import (
    ActivationSettings,
    ProviderActivation,
)
from docsuri_ops import production_wiring as wiring
from docsuri_ops.cutover.tool import READY_BOUND_SECONDS, StepFailed, run_word
from docsuri_ops.u8_platform.u8_protocols import PreconditionRefused, admit_new_database
from tests.u8_service_operations_integration import cutover_flows as cf
from tests.u8_service_operations_integration import recovery_flows as rf
from tests.u8_service_operations_integration.component.test_cutover_words import Stage
from tests.u8_service_operations_integration.operations.test_production_wiring import (
    NOW,
    installed,
    stub_ledger,
)

OUTWARD = ("resend", "notion")


@pytest.fixture
def stage(tmp_path, realm, clock):
    value = Stage(tmp_path, realm, clock)
    value.platform.sleep = clock.advance  # the readiness waits' sleep moves the clock
    value.platform.release_tag = lambda: cf.TAG
    value.named = value.database.names.new("rehearsal")
    value.platform.named_rehearsal = lambda: value.named
    value.created = []
    value.platform.create_rehearsal = value.created.append
    yield value
    value.close()


def ready_after(stage, seconds: float) -> None:
    """v2 answers ready once `seconds` have passed on the test's clock."""
    since = stage.clock()
    stage.platform.v2_ready = lambda: (stage.clock() - since).total_seconds() >= seconds


def aborted_for(stage, reason: str) -> bool:
    record = stage.tool.machine.current()
    incident = Incidents(stage.ledger, environment="live").get(record["abortIncidentId"])
    return f"cutover:{record['cutoverId']}:{reason}" in incident["correlationIds"]


# --- 1. begin creates one record ------------------------------------------------------------


def test_status_answers_none_before_any_record(stage):
    assert run_word(stage.tool, "status", {}) == {"state": "none"}


def test_begin_creates_one_record_and_refuses_a_second(stage):
    result = run_word(stage.tool, "begin", {})
    assert result["state"] == "preparing" and result["releaseTag"] == cf.TAG
    assert result["rehearsalDatabase"] == stage.named and result["ready"] is True
    assert stage.created == [stage.named]
    copy = stage.tool.copies.get(result["copyId"])
    assert copy["kind"] == "rehearsal-database"
    assert copy["locations"] == [f"database/{stage.named}"]
    # The profile's receipt names it: the ledger knows the database v2 runs on.
    assert wiring.ledger_profile_state(stage.ledger)["rehearsalDatabase"] == stage.named
    with pytest.raises(OperationsError) as refused:
        run_word(stage.tool, "begin", {})
    assert refused.value.current == {"reasonKey": "cutover-record-exists"}
    assert len(stage.ledger.records("cutover-record")) == 1 and stage.created == [stage.named]


def test_begin_refuses_without_an_installed_release_or_a_named_database(stage):
    stage.platform.release_tag = lambda: None
    with pytest.raises(OperationsError) as untagged:
        stage.tool.begin()
    assert untagged.value.current == {"reasonKey": "release-not-installed"}
    stage.platform.release_tag = lambda: cf.TAG
    for name in (None, stage.database.name, "docsuri_v2_rehearsal_" + "a" * 12):
        stage.platform.named_rehearsal = lambda name=name: name
        with pytest.raises(OperationsError) as refused:
            stage.tool.begin()
        assert refused.value.current == {"reasonKey": "rehearsal-database-unnamed"}, name
    assert stage.ledger.records("cutover-record") == [] and stage.created == []


def test_begin_in_person_only(stage):
    stage.platform.operator = SimpleNamespace(standing=True, facts=stage.operator.facts)
    with pytest.raises(OperationsError) as refused:
        run_word(stage.tool, "begin", {})
    assert refused.value.current == {"reasonKey": "in-person-required"}


# --- 2. check moves rehearsing ⇄ ready-to-switch ----------------------------------------------


def test_check_moves_between_rehearsing_and_ready_to_switch(stage):
    record = stage.ready()  # ends with `check` reaching ready-to-switch on real evidence
    assert record["state"] == "ready-to-switch"
    stage.platform.evidence.verification = lambda run: None  # the precondition lapses
    checked = run_word(stage.tool, "check", {})
    assert checked["state"] == "rehearsing"
    assert "verification-not-passed" in checked["missing"]
    stage.platform.evidence.verification = lambda run: {"passed": True, "releaseTag": cf.TAG}
    assert run_word(stage.tool, "check", {}) == {"state": "ready-to-switch", "missing": []}


def test_check_before_the_soak_only_names_what_is_missing(stage):
    stage.tool.machine.begin(cf.TAG)
    checked = run_word(stage.tool, "check", {})
    assert checked["state"] == "preparing" and "dry-run-not-accepted" in checked["missing"]
    assert stage.tool.machine.current()["state"] == "preparing"


# --- 3. a passed VerificationRun for the tag satisfies precondition 1 --------------------------


def test_a_passed_verification_run_for_the_tag_and_no_other_satisfies_precondition_1(
        tmp_path, stage):
    paths = installed(tmp_path / "arranged")
    folder = wiring.release_evidence_folder(paths)
    folder.mkdir(parents=True)
    passed, failed, other, misnamed = (str(uuid4()) for _ in range(4))
    for run, ok, tag, named in ((passed, True, cf.TAG, passed), (failed, False, cf.TAG, failed),
                                (other, True, "v9.9.9", other), (passed, True, cf.TAG, misnamed)):
        (folder / f"verification-run-{named}.json").write_text(json.dumps({
            "verificationRunId": run, "releaseTag": tag, "commit": "c" * 40, "passed": ok}))
    stage.platform.evidence.verification = wiring.verification_reader(paths)
    machine = stage.tool.machine
    machine.begin(cf.TAG)
    for run, satisfied in ((passed, True), (failed, False), (other, False),
                           (misnamed, False), (str(uuid4()), False)):
        machine.verification_passed(run, cf.TAG)
        assert ("verification-not-passed" not in stage.tool.missing()) is satisfied, run
    reader = wiring.verification_reader(paths)
    assert reader("not-an-id") is None and reader(misnamed) is None
    assert reader(passed)["releaseTag"] == cf.TAG


# --- 4. no part the switch, abort or rollback uses is unwired ----------------------------------

PARTS = ("final_run", "final_decide", "fail_final", "first_backup", "agent",
         "lifecycle_outcomes", "v1_accounts", "v1_states", "v2_writes", "activation",
         "v1_store_present", "create_rehearsal", "release_tag", "named_rehearsal", "provider_word")


def test_no_part_of_the_production_cutover_stops_at_an_unwired_reason(tmp_path, monkeypatch):
    paths = installed(tmp_path)
    operator = SimpleNamespace(facts=lambda: SimpleNamespace(current_rehearsal=None))
    platform = wiring.production_cutover_platform(
        stub_ledger(), operator, paths=paths, clock=lambda: NOW,
        release=lambda login: bytearray(secrets.token_hex(32).encode()))
    assert all(getattr(platform, name) is not None for name in PARTS)
    # The installer's driver file names no v1 sources here: v1's reads refuse with that
    # wiring's own key, never an `*-unwired` one.
    with pytest.raises(StepFailed) as refused:
        platform.v1_accounts()
    assert refused.value.reason == "v1-sources-unconfigured"
    assert platform.release_tag() is None and platform.named_rehearsal() is None
    # The release the installer staged has no install record: its identity file names it.
    from docsuri_ops import release

    staged = paths.releases / "v2.0.0"
    staged.mkdir(parents=True)
    os.symlink(staged, paths.release)
    release.write_identity(staged, "v2.0.0", "c" * 40, owner_uid=os.getuid())
    assert platform.release_tag() == "v2.0.0"
    named = "docsuri_v2_rehearsal_" + "e" * 12
    (paths.control / wiring.FIRST_REHEARSAL).write_text(json.dumps({"database": named}))
    assert platform.named_rehearsal() == named
    (paths.control / wiring.FIRST_REHEARSAL).write_text(json.dumps({"database": "docsuri_v2"}))
    assert platform.named_rehearsal() is None
    # The providers' words (U8 plan Step 107(i)): the production tool's word of the same
    # name, in person, with no login; its refusal reaches the caller by its reason.
    from docsuri_ops import production_tool

    seen, answers = [], [{"result": {"provider": "orcid", "state": "unavailable"}}]

    def recorded(word, document, **options):
        seen.append((word, document, options.get("login")))
        answer = answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer

    monkeypatch.setattr(production_tool, "invoke", recorded)
    document = {"provider": "orcid"}
    assert platform.provider_word("provider-failed", document) == {
        "provider": "orcid", "state": "unavailable"}
    assert seen == [("provider-failed", document, None)]
    answers.append(production_tool.Refused("approval-superseded"))
    with pytest.raises(OperationsError) as superseded:
        platform.provider_word("provider-decision", {"provider": "google"})
    assert superseded.value.code == "CONFLICT"
    assert superseded.value.current == {"reasonKey": "approval-superseded"}


def private_login(path, user: str, password: str) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        json.dump({"user": user, "password": password}, stream)


def granted_synthetic_v1(realm, operator: str):
    """A synthetic v1 database of the test's in the realm's instance: no `PUBLIC` CONNECT;
    CONNECT and SELECT for the realm's operator stand-in alone (as Step 52(g)'s fixture
    grants its import database)."""
    from psycopg import sql

    from tests.u8_service_operations_integration import v1_flows

    v1 = v1_flows.SyntheticV1(realm).create()
    name = sql.Identifier(v1.name)
    with rf.admin(realm) as conn:
        conn.execute(sql.SQL("REVOKE CONNECT ON DATABASE {} FROM PUBLIC").format(name))
        conn.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
            name, sql.Identifier(operator)))
    with rf.admin(realm, v1.name) as conn:
        conn.execute(sql.SQL("GRANT SELECT ON ALL TABLES IN SCHEMA public TO {}").format(
            sql.Identifier(operator)))
    return v1


def test_the_rollbacks_facts_are_read_only_reads(tmp_path, realm):
    """Step 98(d) (L1-56): on a production stand-in of its own. The operator transactions
    take the realm's own connector for its restore stand-in, the realm login that holds
    every owner role as production's operator does; v1's reader reads a synthetic v1
    database of the test's through the operator stand-in, under a call-through spy."""
    import psycopg

    from docsuri_ops.u8_platform import recovery_words
    from docsuri_ops.u8_platform.platform_profile import U8PlatformProfile
    from tests.u8_service_operations_integration import host_flows

    roles = rf.credentials(realm, "standin-credentials.json")["roles"]
    platform = U8PlatformProfile.realm(Path(realm.root))
    with host_flows.production_stand_in(realm) as standin:
        owners = wiring.OperatorTransactions(
            recovery_words._connector(platform, "docsuri_restore", roles["restore"]),
            standin.database)
        facts = owners.run("accounts", lambda conn: conn.execute(
            "SELECT current_database() AS database,current_user AS role,"
            "current_setting('transaction_read_only') AS read_only").fetchall())
        assert facts == [{"database": standin.database, "role": "docsuri_accounts_owner",
                          "read_only": "on"}]
        with pytest.raises(psycopg.errors.ReadOnlySqlTransaction):
            owners.run("accounts", lambda conn: conn.execute(
                "UPDATE accounts.account SET display_name=display_name WHERE false"))
    # v1's accounts, read only at the named address with your private login file.
    operator = "docsuri_operator"
    v1 = granted_synthetic_v1(realm, operator)
    try:
        login = tmp_path / "v1-login.json"
        private_login(login, operator, roles["operator"])
        config = {"v1Sources": {
            "database": {"host": "127.0.0.1", "port": realm.database_port,
                         "database": v1.name},
            "index": {"url": "http://127.0.0.1:19209", "name": "papers"},
            "objects": {"url": "http://127.0.0.1:19009", "bucket": "docsuri-papers",
                        "credentials": str(tmp_path / "objects.json")}},
            "v1Accounts": {"credentials": str(login)}}
        opened = []

        def recorded_connect(**options):
            opened.append({key: value for key, value in options.items() if key != "password"})
            return psycopg.connect(**options)

        with rf.admin(realm, v1.name) as conn:
            statuses = dict(conn.execute("SELECT id::text,status FROM accounts").fetchall())
        accounts, states = wiring.v1_account_reader(config, connect=recorded_connect)
        listed = accounts()
        assert listed == sorted(statuses) and len(set(listed)) == len(listed)
        assert set(v1.ids.values()) <= set(statuses)
        named = v1.ids["deactivated"]
        assert states([named, "v1-unknown"]) == {named: statuses[named], "v1-unknown": None}
        assert {(item["host"], item["port"], item["dbname"]) for item in opened} == {
            ("127.0.0.1", realm.database_port, v1.name)}
        assert all(item["options"] == "-c default_transaction_read_only=on" for item in opened)
        os.chmod(login, 0o644)
        with pytest.raises(wiring.WiringRefused, match="v1-accounts-credentials-refused"):
            wiring.v1_account_reader(config, connect=recorded_connect)[0]()
        with pytest.raises(wiring.WiringRefused, match="v1-accounts-credentials-unconfigured"):
            wiring.v1_account_reader({**config, "v1Accounts": {}})
    finally:
        v1.drop()


# --- 5. the readiness waits --------------------------------------------------------------------


def to_second_half(stage) -> None:
    stage.start()
    run = stage.ledger.get("migration-run", stage.tool.machine.current()["finalRunId"])
    cf.accept(stage.ledger, run, now=stage.clock())


def test_a_v2_ready_after_30_seconds_passes_the_switchs_wait(stage):
    to_second_half(stage)
    ready_after(stage, 30)
    before = stage.clock()
    assert stage.tool.start()["waiting"] == "maintainer-window"
    waited = (stage.clock() - before).total_seconds()
    assert 30 <= waited < 60  # polled every 5 s on the injected clock


def test_a_v2_that_never_becomes_ready_aborts_with_admission_maintainer_only(stage):
    to_second_half(stage)
    stage.platform.v2_ready = lambda: False
    before = stage.clock()
    result = stage.tool.start()
    assert result["state"] == "rehearsing", result
    assert (stage.clock() - before).total_seconds() >= READY_BOUND_SECONDS
    assert aborted_for(stage, "v2-not-ready")
    profile = stage.journey.read_state("profile.json")
    assert profile["mode"] == "rehearsal" and profile["admission"] == "maintainer-only"


def test_opening_restarts_v2_and_requires_readiness(stage):
    to_second_half(stage)
    assert stage.tool.start()["waiting"] == "maintainer-window"
    restarts, restart = [], stage.tool.restart_v2
    stage.tool.restart_v2 = lambda record, step: restarts.append(step) or restart(record, step)
    stage.platform.v2_ready = lambda: False
    subject = stage.opening_subject()  # the opening's rule (L1-3)
    result = stage.tool.open(stage.decide("admission-opening", subject), subject)
    assert result["state"] == "rehearsing", result  # the switch aborted
    assert restarts == ["opening"]
    assert aborted_for(stage, "v2-not-ready-after-opening")
    profile = stage.journey.read_state("profile.json")
    assert profile["admission"] == "maintainer-only" and profile["mode"] == "rehearsal"


def test_opening_with_a_ready_v2_switches(stage):
    restarts, restart = [], stage.tool.restart_v2
    stage.tool.restart_v2 = lambda record, step: restarts.append(step) or restart(record, step)
    assert stage.switched()["state"] == "switched"
    assert restarts == ["opening"]


# --- 6. an abort and a rollback clear the provider approvals ------------------------------------


def approve_outward(stage) -> None:
    """Both outward providers active on a recorded approval, as a live window leaves them."""
    activation = ProviderActivation(
        stage.ledger, ActivationSettings("live", uuid4(), frozenset({*OUTWARD, "models"})),
        clock=stage.clock)
    activation.start()
    for provider in OUTWARD:
        current = activation.record(provider)
        activation._write(provider, {**current, "state": "active", "approvalId": str(uuid4()),
                                     "approvedAt": "2026-10-24T00:00:00.000Z"})
    assert all("approvedAt" in activation.record(provider) for provider in OUTWARD)


def cleared(stage) -> bool:
    return all("approvedAt" not in stage.ledger.get("provider-activation", provider)
               and "approvalId" not in stage.ledger.get("provider-activation", provider)
               for provider in OUTWARD)


def test_an_abort_clears_the_provider_approvals(stage):
    stage.platform.activation = wiring.OperatorActivation(stage.ledger, clock=stage.clock)
    approve_outward(stage)
    stage.start()
    assert run_word(stage.tool, "abort", {"reason": "operator-abort"})["state"] == "rehearsing"
    assert cleared(stage)
    # Which providers are configured is read from their own records.
    configured = wiring.operator_activation(stage.ledger, clock=stage.clock).settings.configured
    assert configured >= frozenset(OUTWARD)


def test_a_rollback_clears_the_provider_approvals(stage):
    stage.platform.activation = wiring.OperatorActivation(stage.ledger, clock=stage.clock)
    approve_outward(stage)
    stage.switched()
    subject = stage.rollback_subject()
    result = stage.tool.rollback(stage.decide("rollback", subject), subject)
    assert result["state"] == "rolled-back", result
    assert cleared(stage)


# --- 7. the rollback's return to rehearsal (your decision of 2026-10-24, "Create a fresh
# rehearsal database") and an accepted dry run's disposal of the database it replaces ------


def rolled_back(stage) -> dict:
    stage.switched()
    assert "acceptedDryRunId" in stage.tool.machine.current()  # the soak's, before the switch
    subject = stage.rollback_subject()
    result = stage.tool.rollback(stage.decide("rollback", subject), subject)
    assert result["state"] == "rolled-back", result
    return stage.tool.machine.current()


def rollback_copies(stage, record: dict) -> list[dict]:
    prefix = f"cutover:{record['cutoverId']}:rollback:"
    return [copy for copy in stage.ledger.records("retained-copy")
            if copy["kind"] == "rehearsal-database" and copy["sourceRef"].startswith(prefix)]


def database_of(copy: dict) -> str:
    return copy["locations"][0].removeprefix("database/")


def v2_states(stage) -> set[str]:
    return {stage.journey.read_state("services", f"{label}.json")["state"]
            for label in stage.platform.v2_labels}


def accepted_run(stage) -> tuple[dict, str]:
    """A dry run accepted on its own new rehearsal database, recorded as the migration
    tool's preparing phase records it."""
    from backend.modules.operations.migration.misfits import Decisions

    name = stage.database.names.new("rehearsal")
    run = cf.accepted_dry_run(stage.ledger, now=stage.clock(), database=name,
                              decisionsDigest=Decisions.from_ledger(stage.ledger).digest())
    return run, name


def rehearsal_set(stage, database: str) -> dict:
    """A rehearsal backup set of one named database (its incarnation names it)."""
    now = stage.clock()
    facts = rf.receipt(now=now)
    backup = str(uuid4())
    revision = sum(1 for item in stage.ledger.records("backup-set")
                   if item["environment"] == "rehearsal") + 1
    record = {
        "backupId": backup, "environment": "rehearsal", "revision": revision,
        "trigger": "scheduled", "takenAt": rf.utc_text(now), "checksum": "e" * 64,
        "sizeBytes": 1024, "sourceDatabaseBytes": 4096,
        "location": f"archives/live-set-20261022T120000-{backup}.archive",
        "databaseIncarnation": f"{database}:16385",
        "stagingLocation": f"staging/live-set-20261022T120000-{backup}",
        "retainUntil": rf.utc_text(now + dt.timedelta(days=14)), "integrity": "passed",
        "operatorReceiptRef": facts["receiptId"],
    }
    stage.ledger.append("backup-set", record, expect_revision=0, receipts=(facts,))
    return record


def test_a_rollback_returns_to_rehearsal_on_a_new_empty_rehearsal_database(stage):
    from backend.modules.operations.retained_copies import RetainedCopies
    from backend.u8_policy import SYNTHETIC_OPERATIONS

    # A spy on the stage's agent (Step 71(d), L1-3): when `rollback-copy` is called, the
    # ledger already holds the copy, recorded before its first byte.
    held: list[dict] = []
    agent = stage.platform.agent

    def spy(word: str, document: dict, *, via: str) -> dict:
        if word == "rollback-copy":
            held.append(stage.ledger.get("retained-copy", document["recordId"]))
        return agent(word, document, via=via)

    stage.platform.agent = spy
    record = rolled_back(stage)
    (rolled,) = held
    assert rolled["kind"] == "rolled-back-v2-database"
    assert rolled["locations"] == ["backup-volume:rolled-back-database"]
    assert rolled["disposeAfter"] == rf.utc_text(dt.datetime.fromisoformat(
        record["rollbackV1ServingAt"].replace("Z", "+00:00")) + dt.timedelta(seconds=2592000))
    rollback = next(item for item in (stage.ledger.get("maintainer-approval", ref)
                                      for ref in record["approvals"])
                    if item["step"] == "rollback")
    assert rolled["disposalApprovalId"] == rollback["approvalId"]
    copies = RetainedCopies(stage.ledger, SYNTHETIC_OPERATIONS)
    assert copies.backstop_of(rolled) == dt.datetime.fromisoformat(
        rolled["createdAt"].replace("Z", "+00:00")) + dt.timedelta(days=90)
    (copy,) = rollback_copies(stage, record)
    name = database_of(copy)
    assert stage.database.names.kind_of(name) == "rehearsal"
    # Named with the instance's naming, recorded first, then created once, empty.
    assert stage.created == [name] and "completedAt" in copy
    profile = stage.journey.read_state("profile.json")
    assert (profile["mode"], profile["admission"], profile["rehearsalDatabase"]) == (
        "rehearsal", "maintainer-only", name)
    # The ledger knows it too, from the profile receipts (production's reading).
    assert wiring.ledger_profile_state(stage.ledger) == {
        "mode": "rehearsal", "admission": "maintainer-only", "rehearsalDatabase": name}
    # The accepted dry run is cleared: its database went with opening.
    assert record["state"] == "rolled-back" and "acceptedDryRunId" not in record
    # v2 stays stopped until a dry run accepted after the rollback replaces that database.
    assert v2_states(stage) == {"stopped"}


SERVING_STEPS = ("create", "rollback-rehearsal-database", "rollback-profile-admission",
                 "rollback-profile-mode")


@pytest.mark.parametrize("failing", SERVING_STEPS)
def test_a_failed_serving_step_keeps_v1_serving_and_its_retry_completes_it(stage, failing):
    stage.switched()
    failed: list[str] = []
    if failing == "create":
        def create(name: str) -> None:
            if not failed:
                failed.append(name)
                raise RuntimeError("instance-unavailable")
            stage.created.append(name)

        stage.platform.create_rehearsal = create
    else:
        profile = stage.tool._profile

        def flaky(record, field_name, value, step, **extra):
            if step == failing and not failed:
                failed.append(step)
                raise StepFailed("profile-change-failed")
            return profile(record, field_name, value, step, **extra)

        stage.tool._profile = flaky
    subject = stage.rollback_subject()
    result = stage.tool.rollback(stage.decide("rollback", subject), subject)
    assert result["state"] == "rolling-back" and result["v1Serving"] is True, result
    assert result["reason"] == ("rehearsal-creation-failed" if failing == "create"
                                else "profile-change-failed")
    record = stage.tool.machine.current()
    assert record["state"] == "rolling-back" and "rollbackV1ServingAt" in record
    # v1 keeps serving, and the copy has not started: nothing of v2's is touched.
    assert stage.journey.tunnel()["origin"] == "v1-web"
    assert not any(word == "rollback-copy" for word, _ in stage.agent.calls)
    assert stage.tool.copies.undisposed("rolled-back-v2-database") == []
    assert stage.database.tables() != []
    (copy,) = rollback_copies(stage, record)
    name = database_of(copy)
    # The retry runs the serving step's missing steps first, then the copy.
    word = "retry-copy" if failing == "create" else "rollback"
    done = run_word(stage.tool, word, {})
    assert done["state"] == "rolled-back", done
    (again,) = rollback_copies(stage, record)
    assert again["copyId"] == copy["copyId"] and stage.created == [name]  # created once
    profile = stage.journey.read_state("profile.json")
    assert (profile["mode"], profile["admission"], profile["rehearsalDatabase"]) == (
        "rehearsal", "maintainer-only", name)
    assert "acceptedDryRunId" not in stage.tool.machine.current()
    assert stage.database.tables() == []  # copied, then recreated, only after the retry


def test_a_verification_passed_after_the_rollback_starts_no_soak_until_a_new_dry_run(stage):
    rolled_back(stage)
    machine = stage.tool.machine
    machine.verification_passed(uuid4(), cf.TAG)
    assert stage.tool.soak_after_verification() is None
    with pytest.raises(OperationsError) as refused:
        machine.start_soak()
    assert refused.value.current["reasonKey"] == "dry-run-not-accepted"
    assert machine.current()["state"] == "rolled-back"
    run, name = accepted_run(stage)
    result = stage.tool.after_dry_run(run["runId"], name)
    assert result["soak"] == "started", result
    record = machine.current()
    assert record["state"] == "rehearsing" and record["acceptedDryRunId"] == run["runId"]


def test_each_accepted_dry_run_removes_the_rehearsal_database_it_replaces(stage):
    record = rolled_back(stage)
    (rollback_copy,) = rollback_copies(stage, record)
    rollback_name = database_of(rollback_copy)
    rollback_set = rehearsal_set(stage, rollback_name)
    # 1. A dry run accepted after the rollback: the rollback's database, then its sets.
    first, first_name = accepted_run(stage)
    result = stage.tool.after_dry_run(first["runId"], first_name)
    assert result["replacedRehearsalDatabase"] == rollback_name, result
    assert result["rehearsalDatabasesRemoved"] == [rollback_copy["copyId"]]
    assert result["rehearsalDatabasesPending"] == []
    assert "disposedAt" in stage.tool.copies.get(rollback_copy["copyId"])
    addressed = {*result["rehearsalSetsDisposed"],
                 *(item["backupId"] for item in result["rehearsalSetsWaiting"])}
    # Only that database's sets; this stand-in set has no file, so it waits for the pass.
    assert addressed == {rollback_set["backupId"]}
    assert stage.journey.read_state("profile.json")["rehearsalDatabase"] == first_name
    # 2. A second accepted dry run removes the first's.
    second, second_name = accepted_run(stage)
    result = stage.tool.after_dry_run(second["runId"], second_name)
    first_copy = next(copy for copy in stage.ledger.records("retained-copy")
                      if copy["sourceRef"] == f"run:{first['runId']}")
    assert result["replacedRehearsalDatabase"] == first_name
    assert result["rehearsalDatabasesRemoved"] == [first_copy["copyId"]]
    open_names = {database_of(copy) for copy in stage.tool.copies.undisposed(
        "rehearsal-database")}
    assert open_names == {second_name}
    # 3. A third dry run is admitted, through the migration tool's own start: one
    # rehearsal database is open, within NFR8.15's two. The three databases kept without
    # these removals would have exceeded it.
    third = dry_run_start(stage)()
    assert third["state"] == "preparing" and third["kind"] == "dry", third
    with pytest.raises(PreconditionRefused, match="rehearsal-database-limit"):
        admit_new_database("rehearsal", {rollback_name, first_name, second_name},
                           stage.database.names)


# --- 7b. NFR8.15 at each creation (Step 33's accepted-dry-run box; Step 34 item 4) --------


def dry_run_start(stage):
    """`MigrationTool.start_dry` on the stage's ledger, with your go-ahead recorded and the
    arrangement installed and isolation passing: the dry run's real start, which records
    the run (and, when the run is driven, creates its rehearsal database)."""
    from backend.modules.operations.migration_records import MigrationRuns
    from docsuri_ops.migration.tool import MigrationPlatform, MigrationTool
    from tests.u8_service_operations_integration.operations.test_migration_words import Gate

    unreached = SimpleNamespace()
    platform = MigrationPlatform(
        operator=stage.operator, names=stage.database.names, snapshot=unreached,
        create_rehearsal=stage.created.append, create_import=unreached,
        restore_import=unreached, import_reader=unreached, owners_for=unreached,
        stream_back=unreached, isolation=Gate(passes=10**6), disk=unreached,
        spool=stage.tmp, evidence=stage.tmp / "migration-evidence",
        installed=lambda: True, database_bytes=unreached)
    tool = MigrationTool(MigrationRuns(stage.ledger, clock=stage.clock), stage.tool.copies,
                         platform, clock=stage.clock, tool_commit="0" * 40)

    def start() -> dict:
        go_ahead = cf.decision(stage.ledger, "dry-run-go-ahead", "v1", now=stage.clock())
        return tool.start_dry(go_ahead)

    return start


def open_rehearsal_databases(stage, count: int) -> list[str]:
    """`count` rehearsal databases open in the ledger: retained copies, recorded before
    their creation and not disposed (an accepted run's, or a removal still pending)."""
    names = [stage.database.names.new("rehearsal") for _ in range(count)]
    for name in names:
        stage.tool.copies.record("rehearsal-database", f"run:{uuid4()}", [f"database/{name}"])
    return names


def written(stage) -> dict:
    """What a refused creation must leave as it found: every ledger record kind it could
    write, every database it could create."""
    return {kind: [json.dumps(item, sort_keys=True) for item in stage.ledger.records(kind)]
            for kind in ("cutover-record", "retained-copy", "migration-run")} | {
        "created": list(stage.created), "profile": stage.journey.read_state("profile.json")}


def test_a_dry_runs_start_is_refused_while_two_rehearsal_databases_are_open(stage):
    open_rehearsal_databases(stage, 2)
    start = dry_run_start(stage)
    before = written(stage)
    with pytest.raises(OperationsError) as refused:
        start()
    assert refused.value.current == {"reasonKey": "rehearsal-database-limit"}
    after = written(stage)
    # Your go-ahead is your own record; the start itself wrote nothing.
    assert after == before


def test_a_dry_runs_start_is_admitted_with_one_rehearsal_database_open(stage):
    open_rehearsal_databases(stage, 1)
    run = dry_run_start(stage)()
    assert run["state"] == "preparing" and run["kind"] == "dry"


def test_begin_is_refused_while_two_rehearsal_databases_are_open(stage):
    open_rehearsal_databases(stage, 2)
    before = written(stage)
    with pytest.raises(OperationsError) as refused:
        run_word(stage.tool, "begin", {})
    assert refused.value.current == {"reasonKey": "rehearsal-database-limit"}
    assert written(stage) == before
    assert stage.ledger.records("cutover-record") == [] and stage.created == []


def test_begin_is_admitted_with_one_rehearsal_database_open(stage):
    open_rehearsal_databases(stage, 1)
    result = run_word(stage.tool, "begin", {})
    assert result["state"] == "preparing" and stage.created == [stage.named]


class FailRemovals:
    """The operator, with every `platform.database.remove` failed through U7's injected
    permission fault (a failed receipt bound under its key) while `failing` holds (only
    the databases in `only`, when it names any), and each effect it is asked for recorded
    in order, with the CutoverRecord's state when it was asked (`states`)."""

    def __init__(self, operator, ledger=None):
        self.operator, self.failing, self.order = operator, True, []
        self.only: set[str] = set()
        self.ledger, self.states = ledger, []

    def __getattr__(self, name):
        return getattr(self.operator, name)

    def execute(self, operation, target, inputs, *, key, **options):
        self.order.append((operation, inputs.get("database") or inputs.get("recordId")
                           or inputs.get("field")))
        if self.ledger is not None:
            records = self.ledger.records("cutover-record")
            self.states.append(records[-1]["state"] if records else None)
        if self.failing and operation == "platform.database.remove" and (
                not self.only or inputs.get("database") in self.only):
            return self.operator.execute(operation, target, inputs, key=key,
                                         injected_fault="permission", **options)
        return self.operator.execute(operation, target, inputs, key=key, **options)


def switched_with_two_left_pending(stage) -> tuple[FailRemovals, list[str], dict]:
    """The switch opened with two rehearsal databases open (the soak's and an earlier
    one) whose removals at opening both failed: opening left them pending."""
    (earlier,) = open_rehearsal_databases(stage, 1)
    log = FailRemovals(stage.operator, stage.ledger)
    stage.platform.operator = log
    stage.switched()
    left = stage.tool.copies.undisposed("rehearsal-database")
    assert len(left) == 2 and all("disposalPendingSince" in copy for copy in left), left
    assert {database_of(copy) for copy in left} == {earlier, stage.soak_database}
    backup = rehearsal_set(stage, earlier)
    return log, [database_of(copy) for copy in left], backup


def test_a_rollback_with_two_rehearsal_databases_left_pending_by_opening_is_not_refused(
        stage):
    """Your decision of 2026-10-25 ("Never block a rollback"; Step 34 item 4): the start
    is not refused for NFR8.15's count. At v1's serving the rollback removes the two
    databases opening left pending and creates its own; their sets are disposed once the
    rollback has ended, because A6 refuses every disposal while it is rolling-back."""
    log, left, backup = switched_with_two_left_pending(stage)
    log.failing = False
    log.order.clear()
    log.states.clear()
    subject = stage.rollback_subject()
    result = stage.tool.rollback(stage.decide("rollback", subject), subject)
    assert result["state"] == "rolled-back", result
    record = stage.tool.machine.current()
    assert all("disposedAt" in stage.tool.copies.get(copy["copyId"])
               for copy in stage.ledger.records("retained-copy")
               if copy["kind"] == "rehearsal-database" and database_of(copy) in left)
    (own,) = rollback_copies(stage, record)
    assert stage.created == [database_of(own)]
    open_names = {database_of(copy) for copy in stage.tool.copies.undisposed(
        "rehearsal-database")}
    assert open_names == {database_of(own)}
    # Database, then sets: both removals come before the rollback's own database is set
    # on the profile, and the left set's disposal is asked for only after the record is
    # rolled-back, where A6 admits it (never refused as `live-exclusion-held`).
    removals = [index for index, (operation, name) in enumerate(log.order)
                if operation == "platform.database.remove" and name in left]
    disposals = [index for index, item in enumerate(log.order)
                 if item == ("platform.copy.dispose", backup["backupId"])]
    profile = log.order.index(("platform.profile.rehearsal-database", "rehearsalDatabase"))
    assert len(removals) == 2 and max(removals) < profile < disposals[0], log.order
    assert [log.states[index] for index in disposals] == ["rolled-back"], log.states
    assert set(result["rehearsalDatabasesLeft"]) == set(left)
    assert_set_addressed(stage, result, backup)
    assert stage.journey.read_state("profile.json")["rehearsalDatabase"] == database_of(own)


def assert_set_addressed(stage, result: dict, backup: dict) -> None:
    """A left database's set is disposed after the rollback, or waits for the disposal
    pass with a reason of its own: never the live exclusion, which no longer holds. This
    stand-in set has no archive on the journey's volume, so the realm's disposal fails and
    it waits; the ledger then still holds it, undisposed, for the pass at its date."""
    waiting = {item["backupId"]: item["reason"] for item in result["rehearsalSetsWaiting"]}
    disposed = set(result["rehearsalSetsDisposed"])
    assert backup["backupId"] in disposed | set(waiting), result
    if backup["backupId"] in disposed:
        assert "disposedAt" in stage.ledger.get("backup-set", backup["backupId"])
    else:
        assert waiting[backup["backupId"]] != "live-exclusion-held", waiting
        assert "disposedAt" not in stage.ledger.get("backup-set", backup["backupId"])


def test_the_sets_of_a_database_an_earlier_rollback_run_removed_are_disposed_too(stage):
    """The first of two left databases is removed and the second's removal fails: v1
    keeps serving. The next `rollback` removes the second, and once the rollback ends the
    sets of both are addressed, the first's included, though its copy was already
    disposed when the retry ran."""
    log, left, earlier_set = switched_with_two_left_pending(stage)
    soak_set = rehearsal_set(stage, stage.soak_database)
    # The order the rollback removes them in: the second one's removal fails.
    first, second = (database_of(copy) for copy in stage.tool._opening_addressed(
        stage.tool.machine.current()))
    assert {first, second} == set(left)
    log.only = {second}
    subject = stage.rollback_subject()
    waiting = stage.tool.rollback(stage.decide("rollback", subject), subject)
    assert waiting["reason"] == "rehearsal-database-removal-failed", waiting
    assert {database_of(copy) for copy in stage.tool.copies.undisposed(
        "rehearsal-database")} == {second}
    log.failing = False
    done = run_word(stage.tool, "rollback", {})
    assert done["state"] == "rolled-back", done
    assert set(done["rehearsalDatabasesLeft"]) == {first, second}
    for backup in (earlier_set, soak_set):
        assert_set_addressed(stage, done, backup)


def test_ten_failed_left_removals_then_one_that_succeeds_completes_the_rollback(stage):
    """Each run of `rollback` is one new attempt of a left database's removal, under keys
    of its own: ten failed runs exhaust nothing, and the eleventh, once the cause is
    fixed, removes it and completes the rollback (a fixed key would have answered
    `step-retries-exhausted` after nine)."""
    log, left, backup = switched_with_two_left_pending(stage)
    subject = stage.rollback_subject()
    answer = stage.tool.rollback(stage.decide("rollback", subject), subject)
    for _ in range(9):
        assert answer["reason"] == "rehearsal-database-removal-failed", answer
        answer = run_word(stage.tool, "rollback", {})
    assert answer["reason"] == "rehearsal-database-removal-failed", answer
    assert stage.tool.machine.current()["state"] == "rolling-back"
    log.failing = False
    done = run_word(stage.tool, "rollback", {})
    assert done["state"] == "rolled-back", done
    assert not {database_of(copy) for copy in stage.tool.copies.undisposed(
        "rehearsal-database")} & set(left)
    assert_set_addressed(stage, done, backup)


class Interrupted(BaseException):
    """The run's process ending inside an effect (killed, Ctrl-C, a closed terminal)."""


class RemovalEffects:
    """The rollback's operator, with each left database's removal run through a run
    effect of the case's own (`effect`), so a removal can be interrupted after its
    receipt was bound, or report an unknown outcome after it applied; every other
    operation, and every removal once `effect` is None, runs as usual. `ran` counts the
    removal effects that ran."""

    def __init__(self, operator, effect, *, dies_reconciling: bool = False):
        from docsuri_ops.u8_platform.u8_protocols import Operator

        self.operator, self.effect, self.ran = operator, effect, []
        self.dies_reconciling = dies_reconciling
        inner = getattr(operator, "operator", operator)
        self.clone = Operator(inner.profile, inner.store, actor=inner.actor,
                              authorities=inner.authorities, facts=inner.facts,
                              run_effect=self._run)

    def _run(self, **options):
        self.ran.append(options["operation_id"])
        return self.effect(**options)

    def __getattr__(self, name):
        return getattr(self.operator, name)

    def execute(self, operation, target, inputs, *, key, **options):
        if operation == "platform.database.remove" and self.effect is not None:
            return self.clone.execute(operation, target, inputs, key=key, **options)
        return self.operator.execute(operation, target, inputs, key=key, **options)

    def reconcile(self, operation_id):
        if self.dies_reconciling:
            raise Interrupted()  # the run's process ended before it reconciled
        return self.operator.reconcile(operation_id)


def test_a_removal_an_earlier_run_left_in_its_lease_is_not_run_beside(stage):
    """Review finding (Major, R12): the first `rollback`'s removal of a left database is
    interrupted after its receipt was bound. The next `rollback` settles that run's key
    before opening its own: the operation is still within its lease, so it answers
    `effect-in-progress` and runs no second removal beside it."""
    log, left, _ = switched_with_two_left_pending(stage)
    log.failing = False

    def interrupted(**options):
        raise Interrupted()

    removals = RemovalEffects(log, interrupted)
    stage.platform.operator = removals
    subject = stage.rollback_subject()
    with pytest.raises(Interrupted):
        stage.tool.rollback(stage.decide("rollback", subject), subject)
    assert len(removals.ran) == 1
    removals.effect = None  # the cause is gone: a removal that ran now would succeed
    try:
        answer = run_word(stage.tool, "rollback", {})
        assert answer["reason"] == "effect-in-progress", answer
        assert len(removals.ran) == 1  # nothing ran beside the bound one
        assert stage.tool.machine.current()["state"] == "rolling-back"
        assert {database_of(copy) for copy in stage.tool.copies.undisposed(
            "rehearsal-database")} >= set(left)
    finally:
        # The interrupted operation settled as nothing applied, as its own process would
        # have, so the realm's store holds nothing in flight for later tests.
        removals.clone.store.settle_operation(operation_id=removals.ran[0], outcome="failed",
                                              disposition="not-applied", effect_refs=[])


def test_an_unknown_removal_reconciled_applied_on_the_next_run_is_taken_as_done(stage):
    """The first run's removal applied, but its outcome was reported unknown and the run
    ended before it reconciled it, leaving the receipt unresolved. The next run settles
    that key, reconciles it from its target (the database is gone: applied), takes it as
    done, so no second removal of that database runs, and completes the rollback."""
    from docsuri_ops.platform_control.executor import STATUS_UNKNOWN, EffectOutcome

    log, left, backup = switched_with_two_left_pending(stage)
    log.failing = False
    bounded = getattr(log, "operator", log).run_effect  # the realm's own run effect

    def unknown(**options):
        applied = bounded(**options)
        return EffectOutcome(STATUS_UNKNOWN, applied.effect_refs)

    log.order.clear()
    removals = RemovalEffects(log, unknown, dies_reconciling=True)
    stage.platform.operator = removals
    subject = stage.rollback_subject()
    with pytest.raises(Interrupted):
        stage.tool.rollback(stage.decide("rollback", subject), subject)
    assert len(removals.ran) == 1
    unresolved = removals.clone._read_named(removals.ran[0])
    assert unresolved["reconciliationState"] == "unresolved", unresolved
    removals.effect, removals.dies_reconciling = None, False
    done = run_word(stage.tool, "rollback", {})
    assert done["state"] == "rolled-back", done
    assert not {database_of(copy) for copy in stage.tool.copies.undisposed(
        "rehearsal-database")} & set(left)
    # The first database's removal ran once (the unknown one): the second run replayed
    # its receipt and reconciled it applied, so no second removal of it ran.
    assert len(removals.ran) == 1
    removes = [name for operation, name in log.order if operation == "platform.database.remove"]
    assert len(removes) == 2 and len(set(removes)) == 2, removes  # the replay, the other one
    from docsuri_ops.cutover import tool as cutover_tool

    assert "step-retries-exhausted" not in cutover_tool.SURFACED_REMOVAL_REASONS
    assert_set_addressed(stage, done, backup)


def test_a_dry_runs_start_is_refused_while_the_cutover_is_switched(stage):
    stage.switched()
    start = dry_run_start(stage)
    before = written(stage)
    with pytest.raises(OperationsError) as refused:
        start()
    assert refused.value.current == {"reasonKey": "cutover-switched"}
    assert written(stage) == before


def test_a_rehearsal_database_recorded_after_opening_is_left_alone_by_the_rollback(stage):
    """Only the databases opening addressed (recorded at or before admission opened) are
    the rollback's to remove: one recorded later, as a dry run's would be, stays open,
    and the rollback never removes it."""
    stage.switched()
    stage.clock.advance(60)
    (later,) = open_rehearsal_databases(stage, 1)
    log = FailRemovals(stage.operator, stage.ledger)
    log.failing = False
    stage.platform.operator = log
    subject = stage.rollback_subject()
    result = stage.tool.rollback(stage.decide("rollback", subject), subject)
    assert result["state"] == "rolled-back", result
    assert ("platform.database.remove", later) not in log.order
    assert later in {database_of(copy) for copy in stage.tool.copies.undisposed(
        "rehearsal-database")}
    # Nor would an `open` re-run on the switched record have addressed it.
    assert later not in {database_of(copy) for copy in stage.tool._opening_addressed(
        stage.tool.machine.current())}


def test_a_dry_run_whose_database_was_removed_cannot_be_accepted_onto_the_record(stage):
    """`Cutover.dry_run_accepted` refuses a run whose target copy is disposed: after a
    rollback the soak cannot move onto a database that does not exist."""
    record = rolled_back(stage)
    run, name = accepted_run(stage)
    copy = stage.tool.copies.get(run["targetCopyId"])
    stage.tool.copies.disposed(copy["copyId"], rf.receipt(
        "platform.database.remove", "database-rehearsal", now=stage.clock()))
    with pytest.raises(OperationsError) as refused:
        stage.tool.machine.dry_run_accepted(run["runId"])
    assert refused.value.current["reasonKey"] == "rehearsal-database-disposed"
    assert "acceptedDryRunId" not in stage.tool.machine.current()
    assert stage.tool.machine.current()["state"] == record["state"]


def test_a_failed_removal_of_a_left_database_keeps_v1_serving_until_the_next_rollback(stage):
    """A removal that fails at the serving step leaves v1 serving and the rollback
    retryable: nothing of the rollback's own database is recorded, the copy does not
    start, and `rollback` run again removes the databases, then completes."""
    log, left, _ = switched_with_two_left_pending(stage)
    subject = stage.rollback_subject()
    waiting = stage.tool.rollback(stage.decide("rollback", subject), subject)
    assert waiting["state"] == "rolling-back" and waiting["v1Serving"] is True, waiting
    assert waiting["reason"] == "rehearsal-database-removal-failed"
    assert waiting["offered"] == ["rollback"]
    record = stage.tool.machine.current()
    assert stage.journey.tunnel()["origin"] == "v1-web"
    assert rollback_copies(stage, record) == [] and stage.created == []
    assert not any(word == "rollback-copy" for word, _ in stage.agent.calls)
    assert stage.database.tables() != []
    log.failing = False
    done = run_word(stage.tool, "rollback", {})
    assert done["state"] == "rolled-back", done
    (own,) = rollback_copies(stage, record)
    assert stage.created == [database_of(own)]
    assert {database_of(copy) for copy in stage.tool.copies.undisposed(
        "rehearsal-database")} == {database_of(own)}
    assert stage.database.tables() == []


def test_a_rollback_clears_a_profile_still_naming_a_left_database_before_removing_it(stage):
    """An opening whose clear failed left the profile naming the soak's database: the
    rollback clears the profile first, then removes it (profile, database, sets)."""
    from tests.u8_service_operations_integration.component.test_cutover_words import (
        OperationLog,
    )

    log = OperationLog(stage.operator, fail_once="platform.profile.rehearsal-database")
    stage.platform.operator = log
    opened = stage.switched()
    assert opened["rehearsalDatabaseCleared"] is False, opened
    assert stage.journey.read_state("profile.json")["rehearsalDatabase"] == stage.soak_database
    log.order.clear()
    subject = stage.rollback_subject()
    result = stage.tool.rollback(stage.decide("rollback", subject), subject)
    assert result["state"] == "rolled-back", result
    # OperationLog keys a profile change by no database: the first is the clear.
    cleared = log.order.index(("platform.profile.rehearsal-database", None))
    removed = log.order.index(("platform.database.remove", stage.soak_database))
    assert cleared < removed
    (own,) = rollback_copies(stage, stage.tool.machine.current())
    assert stage.journey.read_state("profile.json")["rehearsalDatabase"] == database_of(own)


# --- 7c. after a rollback v2 stays stopped until the soak (your decision of 2026-10-25,
# "Follow the design"; Step 34 item 5) --------------------------------------------------


def test_a_dry_run_accepted_after_a_rollback_leaves_v2_stopped_until_the_soak(stage):
    record = rolled_back(stage)
    (rollback_copy,) = rollback_copies(stage, record)
    # A new release after the rollback: its verification has not passed yet.
    stage.tool.machine.new_release("v2.0.1")
    run, name = accepted_run(stage)
    result = stage.tool.after_dry_run(run["runId"], name)
    # The profile names the run's database; v2 stays stopped; no soak yet.
    assert result["v2"] == "stopped" and result["soak"] is None, result
    assert "ready" not in result
    assert stage.journey.read_state("profile.json")["rehearsalDatabase"] == name
    assert wiring.ledger_profile_state(stage.ledger)["rehearsalDatabase"] == name
    assert v2_states(stage) == {"stopped"}
    assert result["rehearsalDatabasesRemoved"] == [rollback_copy["copyId"]]
    assert stage.tool.machine.current()["state"] == "rolled-back"
    # The verification passes: the soak's start starts v2's three roles and waits.
    stage.tool.machine.verification_passed(uuid4(), "v2.0.1")
    ready_after(stage, 30)
    checked = run_word(stage.tool, "check", {})
    soak = checked["soak"]
    assert soak["soak"] == "started" and soak["v2Start"]["ready"] is True, checked
    assert soak["v2Start"]["waitedSeconds"] >= 30
    assert v2_states(stage) == {"running"}
    current = stage.tool.machine.current()
    assert current["state"] in ("rehearsing", "ready-to-switch") and "soakStartedAt" in current


def test_after_a_rollback_a_soak_whose_v2_start_failed_is_started_by_check(stage):
    from tests.u8_service_operations_integration.component.test_cutover_words import (
        OperationLog,
    )

    before = rolled_back(stage)
    run, name = accepted_run(stage)
    stage.platform.operator = OperationLog(stage.operator, fail_once="platform.service.control")
    # The verification already passed before the switch: the soak starts with the move.
    result = stage.tool.after_dry_run(run["runId"], name)
    assert result["soak"] is None and result["v2Start"]["reason"] == "service-control-failed"
    assert result["v2Start"]["offered"] == ["check"]
    record = stage.tool.machine.current()
    # No soak started: the record stays rolled-back, its soak time the earlier soak's.
    assert record["state"] == "rolled-back"
    assert record.get("soakStartedAt") == before.get("soakStartedAt")
    assert v2_states(stage) == {"stopped"}
    checked = run_word(stage.tool, "check", {})
    assert checked["soak"]["soak"] == "started", checked
    assert stage.tool.machine.current()["state"] in ("rehearsing", "ready-to-switch")
    assert v2_states(stage) == {"running"}
    assert "soak" not in run_word(stage.tool, "check", {})  # started: not again


def test_after_a_rollback_a_v2_that_never_becomes_ready_starts_no_soak(stage):
    """The soak waits for v2's readiness (Step 33's readiness note): from rolled-back,
    v2's roles start and the 10-minute wait runs out, so no soak starts, the record stays
    rolled-back and `check` answers `v2-not-ready`; once v2 is ready, `check` starts it."""
    rolled_back(stage)
    stage.tool.machine.new_release("v2.0.1")
    run, name = accepted_run(stage)
    assert stage.tool.after_dry_run(run["runId"], name)["v2"] == "stopped"
    stage.tool.machine.verification_passed(uuid4(), "v2.0.1")
    stage.probes.v2 = False
    checked = run_word(stage.tool, "check", {})
    start = checked["soak"]["v2Start"]
    assert checked["soak"]["soak"] is None and start["reason"] == "v2-not-ready", checked
    assert start["ready"] is False and start["waitedSeconds"] >= READY_BOUND_SECONDS
    assert start["offered"] == ["check"]
    record = stage.tool.machine.current()
    # The new release cleared the earlier soak's start, and none started since.
    assert record["state"] == "rolled-back" and "soakStartedAt" not in record
    stage.probes.v2 = True
    again = run_word(stage.tool, "check", {})
    assert again["soak"]["soak"] == "started", again
    assert stage.tool.machine.current()["state"] in ("rehearsing", "ready-to-switch")


def test_a_stop_after_a_not_ready_start_is_followed_by_a_new_start_at_the_soaks_start(stage):
    """The review's fix of 2026-10-26: the soak's start replays its succeeded starts by
    their keys, so after a start that was not ready and a later in-person `service stop`,
    the next `cutover check` runs a new start for each label the stop superseded (its
    stop record is there), rather than replaying the start and answering `v2-not-ready`
    for ever. A label no later stop touched replays its receipt: no new start."""
    from docsuri_ops.u8_platform.service_words import run_service

    labels = stage.platform.v2_labels

    def stopped_labels() -> dict:
        found = {}
        for label in labels:
            record = stage.journey.read_state("stops", f"{label}.json")
            if record is not None:
                found[label] = str(record["operationId"])
        return found

    stage.platform.stopped_labels = stopped_labels
    rolled_back(stage)
    stage.tool.machine.new_release("v2.0.1")
    run, name = accepted_run(stage)
    stage.tool.after_dry_run(run["runId"], name)
    stage.tool.machine.verification_passed(uuid4(), "v2.0.1")
    stage.probes.v2 = False
    first = run_word(stage.tool, "check", {})["soak"]
    assert first["v2Start"]["reason"] == "v2-not-ready" and v2_states(stage) == {"running"}
    # The operator stops two of the three roles in person while v2 is not ready.
    for label in labels[:2]:
        run_service("stop", label, stage.operator, ledger=stage.ledger)
    assert set(stopped_labels()) == set(labels[:2])
    # v2 is ready only once its three roles run.
    stage.platform.v2_ready = lambda: v2_states(stage) == {"running"}
    log = []
    real = stage.platform.operator

    class Logged:
        def __getattr__(self, attribute):
            return getattr(real, attribute)

        def execute(self, operation, target, inputs, *, key, **options):
            receipt = real.execute(operation, target, inputs, key=key, **options)
            if operation == "platform.service.control":
                log.append((target, bool(receipt.get("replayed"))))
            return receipt

    stage.platform.operator = Logged()
    checked = run_word(stage.tool, "check", {})
    assert checked["soak"]["soak"] == "started", checked
    assert v2_states(stage) == {"running"} and stopped_labels() == {}
    started = [target for target, replayed in log if not replayed]
    assert sorted(started) == sorted(labels[:2]), log  # a new start for each stopped one
    assert (labels[2], True) in log  # the untouched role replayed its start


def test_a_dry_runs_acceptance_removes_the_replaced_database_then_its_real_sets(
        tmp_path, realm, clock):
    """Through the realm's agent and instance: the profile moves to the accepted run's
    database, the database it named before is removed, and only then is that database's
    real set disposed (profile, database, sets; BR9.17)."""
    from psycopg import sql

    from backend.modules.operations.retained_copies import RetainedCopies
    from backend.u8_policy import SYNTHETIC_OPERATIONS
    from docsuri_ops.cutover.preconditions import SwitchEvidence
    from docsuri_ops.cutover.tool import CutoverPlatform, CutoverTool
    from docsuri_ops.u8_platform.recovery_words import realm_procedures
    from tests.u8_service_operations_integration.component.test_disposal_pass import (
        Recording,
        disposable,
        operator_for,
        realm_databases,
    )

    ledger = rf.open_ledger(tmp_path, clock)  # the operations ledger
    database = rf.JourneyDatabase(realm).create()
    replaced = disposable(realm, "rehearsal", database.names)
    with rf.admin(realm) as conn:
        conn.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO docsuri_backup_agent").format(
            sql.Identifier(replaced)))
    with rf.admin(realm, replaced) as conn:
        conn.execute("CREATE TABLE rehearsal_rows(id int PRIMARY KEY)")
        conn.execute("INSERT INTO rehearsal_rows VALUES (1)")
    try:
        agent = rf.journey_agent(tmp_path, realm, database, clock)
        journey, facts, operator = operator_for(tmp_path, realm, ledger, clock,
                                                names=database.names, rehearsal=replaced,
                                                role="operator", agentFolder=str(agent))
        rf.cutover_record(ledger, "preparing")
        procedures = realm_procedures(journey.profile, ledger, clock=clock, ready=lambda: True,
                                      names=database.names).procedures
        request = procedures.requests.request(
            origin="schedule", operation="backup.create", environment="rehearsal",
            target_id=replaced, expected_revision=0, submission_id=uuid4())
        procedures.requests.admit(request["recoveryRequestId"])
        assert procedures.backup(request["recoveryRequestId"],
                                 via="in-person")["state"] == "succeeded"
        backup = next(item for item in ledger.records("backup-set")
                      if item["environment"] == "rehearsal")
        copies = RetainedCopies(ledger, SYNTHETIC_OPERATIONS, clock=clock)
        earlier = copies.record("rehearsal-database", "run:earlier", [f"database/{replaced}"])
        accepted = database.names.new("rehearsal")
        run = cf.accepted_dry_run(ledger, now=clock(), database=accepted)
        recording = Recording(operator)
        evidence = SwitchEvidence(lambda run: None, lambda: None, lambda cutover: None,
                                  lambda: {}, lambda: "stand-in", None, lambda: accepted)
        tool = CutoverTool(ledger, SYNTHETIC_OPERATIONS, CutoverPlatform(
            operator=recording, production=database.name, v1_labels=(), v2_labels=(),
            v2_ready=lambda: True, v1_ready=lambda: True, public=lambda kind: True,
            evidence=evidence, evidence_folder=tmp_path / "cutover-evidence"), clock=clock)
        result = tool.after_dry_run(run["runId"], accepted)
        assert recording.order == ["profile.rehearsal-database", "database.remove",
                                   "copy.dispose"], recording.order
        assert result["rehearsalDatabasesRemoved"] == [earlier["copyId"]], result
        assert result["rehearsalSetsDisposed"] == [backup["backupId"]]
        assert replaced not in realm_databases(realm)
        assert "disposedAt" in ledger.get("backup-set", backup["backupId"])
        assert "disposedAt" in copies.get(earlier["copyId"])
        assert journey.read_state("profile.json")["rehearsalDatabase"] == accepted
        assert tool.machine.current()["acceptedDryRunId"] == run["runId"]
        assert not (tmp_path / "volume" / "docsuri-v2" / backup["location"]).exists()
    finally:
        ledger.close()
        rf.drop_database(realm, replaced)
        database.drop()


# --- 8. a begin, a dry run's move and a rollback's creation that stopped, run again --------


def test_a_begin_whose_creation_was_refused_runs_again_on_the_same_record_and_name(stage):
    """Production's creation refuses with the tool's own `Refused` (not a step failure):
    `begin` answers with its key, and run again it completes the same record."""
    from docsuri_ops.production_tool import Refused

    calls: list[str] = []

    def create(name: str) -> None:
        calls.append(name)
        if len(calls) == 1:
            raise Refused("template-not-current")

    stage.platform.create_rehearsal = create
    failed = run_word(stage.tool, "begin", {})
    assert failed["reason"] == "template-not-current" and failed["offered"] == ["begin"]
    record = stage.tool.machine.current()
    assert record["state"] == "preparing"
    assert "completedAt" not in stage.tool.copies.get(failed["copyId"])
    assert wiring.ledger_profile_state(stage.ledger)["rehearsalDatabase"] is None
    done = run_word(stage.tool, "begin", {})
    assert done["cutoverId"] == record["cutoverId"] and done["copyId"] == failed["copyId"]
    assert done["rehearsalDatabase"] == stage.named and done["ready"] is True, done
    assert calls == [stage.named, stage.named]  # the same recorded name, asked again
    assert "completedAt" in stage.tool.copies.get(done["copyId"])
    assert wiring.ledger_profile_state(stage.ledger)["rehearsalDatabase"] == stage.named
    assert len(stage.ledger.records("cutover-record")) == 1
    with pytest.raises(OperationsError) as refused:
        run_word(stage.tool, "begin", {})
    assert refused.value.current == {"reasonKey": "cutover-record-exists"}


def test_a_begin_whose_restart_failed_runs_again_and_completes(stage):
    """v2's restart fails with a bound failed receipt: `begin` answers, and run again it
    creates nothing, replays the profile's receipt and retries the restart."""
    from tests.u8_service_operations_integration.component.test_cutover_words import (
        OperationLog,
    )

    log = OperationLog(stage.operator, fail_once="platform.service.control")
    stage.platform.operator = log
    failed = run_word(stage.tool, "begin", {})
    assert failed["reason"] == "service-control-failed", failed
    assert stage.created == [stage.named]
    done = run_word(stage.tool, "begin", {})
    assert done["ready"] is True and done["cutoverId"] == failed["cutoverId"], done
    assert stage.created == [stage.named]  # its creation was confirmed: not asked again
    assert v2_states(stage) == {"running"}
    assert wiring.ledger_profile_state(stage.ledger)["rehearsalDatabase"] == stage.named


def test_a_failed_create_in_begin_is_answered_by_the_cutover_command(stage, monkeypatch,
                                                                    capsys):
    """Through `cutover.tool.main`: a step failure is answered with its key, never a
    traceback."""
    import io
    import sys

    from docsuri_ops.cutover import tool as cutover_tool

    def failing(name):
        raise RuntimeError("instance-unavailable")

    stage.platform.create_rehearsal = failing
    # The command closes the ledger it was handed; the stage keeps its own open.
    handed = SimpleNamespace(append=stage.ledger.append, close=lambda: None)
    monkeypatch.setattr(cutover_tool, "production_tool",
                        lambda clock, steps: (stage.tool, handed))
    monkeypatch.setattr(sys, "stdin", type("In", (), {"buffer": io.BytesIO(b"{}")})())
    assert cutover_tool.main(["begin", "--production"]) == 0
    answer = json.loads(capsys.readouterr().out)
    assert answer["ok"] is True and answer["result"]["reason"] == "rehearsal-creation-failed"


def test_a_dry_runs_move_that_stopped_is_run_again_by_check(stage):
    """After `migration accept` following a rollback, the profile step fails (a bound
    failed receipt): nothing is replaced and no soak starts; BR9.2 names the profile's gap
    while the profile is not on the accepted run's database; `cutover check` runs the
    move again under the same keys and finishes it once. After a rollback the move
    starts no v2 itself: the soak's start does (your decision of 2026-10-25)."""
    from tests.u8_service_operations_integration.component.test_cutover_words import (
        OperationLog,
    )

    record = rolled_back(stage)
    (rollback_copy,) = rollback_copies(stage, record)
    run, name = accepted_run(stage)
    stage.platform.operator = OperationLog(
        stage.operator, fail_once="platform.profile.rehearsal-database")
    moved = stage.tool.after_dry_run(run["runId"], name)
    assert moved["reason"] == "profile-rehearsal-database-failed", moved
    assert moved["offered"] == ["check"]
    before, record = record, stage.tool.machine.current()
    # No soak started: the record stays rolled-back, its soak time the earlier soak's.
    assert record["acceptedDryRunId"] == run["runId"] and record["state"] == "rolled-back"
    assert record.get("soakStartedAt") == before.get("soakStartedAt")
    assert "disposedAt" not in stage.tool.copies.get(rollback_copy["copyId"])
    gap = "rehearsal-database-not-the-accepted-runs"
    assert gap in stage.tool.missing()
    assert v2_states(stage) == {"stopped"}
    checked = run_word(stage.tool, "check", {})
    move = checked["dryRunMove"]
    assert move["rehearsalDatabase"] == name and move["soak"] == "started", move
    assert move["replacedRehearsalDatabase"] == database_of(rollback_copy)
    assert move["rehearsalDatabasesRemoved"] == [rollback_copy["copyId"]]
    assert wiring.ledger_profile_state(stage.ledger)["rehearsalDatabase"] == name
    assert v2_states(stage) == {"running"}
    assert gap not in stage.tool.missing()
    assert "dryRunMove" not in run_word(stage.tool, "check", {})  # finished: not again


def test_a_dry_runs_move_whose_restart_stopped_before_any_rollback_is_run_again(stage):
    """Before any rollback the move restarts v2 on the accepted run's database; a failed
    restart replaces nothing, and `cutover check` runs the move again once."""
    from tests.u8_service_operations_integration.component.test_cutover_words import (
        OperationLog,
    )

    begun = run_word(stage.tool, "begin", {})
    assert v2_states(stage) == {"running"}
    run, name = accepted_run(stage)
    stage.platform.operator = OperationLog(stage.operator, fail_once="platform.service.control")
    moved = stage.tool.after_dry_run(run["runId"], name)
    assert moved["reason"] == "service-control-failed" and moved["offered"] == ["check"]
    assert "disposedAt" not in stage.tool.copies.get(begun["copyId"])
    checked = run_word(stage.tool, "check", {})
    move = checked["dryRunMove"]
    assert move["rehearsalDatabase"] == name and move["ready"] is True, move
    assert move["replacedRehearsalDatabase"] == stage.named
    assert move["rehearsalDatabasesRemoved"] == [begun["copyId"]]
    assert v2_states(stage) == {"running"}
    assert "dryRunMove" not in run_word(stage.tool, "check", {})


def test_brs_precondition_names_a_profile_not_on_the_accepted_runs_database(stage):
    stage.tool.machine.begin(cf.TAG)
    run, name = accepted_run(stage)
    stage.tool.machine.dry_run_accepted(run["runId"])
    gap = "rehearsal-database-not-the-accepted-runs"
    assert gap in stage.tool.missing()  # the profile names no rehearsal database
    stage.journey.set_profile(rehearsalDatabase=stage.database.names.new("rehearsal"))
    assert gap in stage.tool.missing()  # another database
    stage.journey.set_profile(rehearsalDatabase=name)
    assert gap not in stage.tool.missing()
    # A run without its target copy is refused too.
    bare = cf.accepted_dry_run(stage.ledger, now=stage.clock())
    stage.tool.machine.dry_run_accepted(bare["runId"])
    assert gap in stage.tool.missing()


class ReplayLog:
    """The operator, with each bound operation recorded with whether its receipt was a
    replay (no effect ran) and its receipt id."""

    def __init__(self, operator):
        self.operator, self.calls = operator, []

    def __getattr__(self, name):
        return getattr(self.operator, name)

    def execute(self, operation, target, inputs, *, key, **options):
        receipt = self.operator.execute(operation, target, inputs, key=key, **options)
        self.calls.append((operation, bool(receipt.get("replayed")), receipt["receiptId"]))
        return receipt


def test_the_serving_steps_after_a_retry_copy_replay_their_receipts(stage):
    """Review finding (Minor, R-04; the person's decision of 2026-10-27, "Fix it now"):
    `retry-copy` onto a replacement volume records your retirement decision on the
    record, so the later runs key the serving step's profile changes under it. Each
    settles the earlier runs' receipts first: the changes the rollback applied are
    replayed, recorded as done, and no second effect runs for them."""
    stage.switched()
    stage.agent.copies = False
    subject = stage.rollback_subject()
    waiting = stage.tool.rollback(stage.decide("rollback", subject), subject)
    assert waiting["copyPending"] is True, waiting
    record = stage.tool.machine.current()
    (copy,) = rollback_copies(stage, record)
    name = database_of(copy)
    served = set(record["effectReceipts"])
    # Your retirement decision: the copy is retried onto a replacement volume, which
    # cannot be written either, so the copy waits again under that decision.
    retire = stage.decide("backup-volume-retirement")
    again = run_word(stage.tool, "retry-copy", {"replacementApprovalId": retire})
    assert again["copyPending"] is True, again
    record = stage.tool.machine.current()
    assert record["approvals"][-1] == retire and "rollbackV1ServingAt" in record
    assert stage.tool._key(record, "rollback-profile-mode") != stage.tool._key(
        {**record, "approvals": record["approvals"][:-1]}, "rollback-profile-mode")
    log = ReplayLog(stage.operator)
    stage.platform.operator = log
    stage.agent.copies = True
    done = run_word(stage.tool, "retry-copy", {})
    assert done["state"] == "rolled-back", done
    profile = [(operation, replayed, receipt) for operation, replayed, receipt in log.calls
               if operation.startswith("platform.profile.")]
    assert [operation for operation, _, _ in profile] == [
        "platform.profile.rehearsal-database", "platform.profile.admission",
        "platform.profile.mode"]
    # Every serving step replayed the receipt the rollback bound: no second effect.
    assert all(replayed for _, replayed, _ in profile), profile
    assert {receipt for _, _, receipt in profile} <= served
    assert stage.created == [name]
    state = stage.journey.read_state("profile.json")
    assert (state["mode"], state["admission"], state["rehearsalDatabase"]) == (
        "rehearsal", "maintainer-only", name)
    assert stage.database.tables() == []  # copied, then recreated


def test_a_rollback_creation_whose_answer_was_lost_completes_on_its_retry(stage):
    """The rollback's create succeeded on the server, but its answer was lost: v1 keeps
    serving, and the retry asks for the same recorded name again, which the creation
    accepts for its own name (`create-disposable`, `RealmDatabases.create_rehearsal`)."""
    stage.switched()
    calls: list[str] = []

    def create(name: str) -> None:
        calls.append(name)  # made on the server
        if len(calls) == 1:
            raise TimeoutError("the answer was lost")

    stage.platform.create_rehearsal = create
    subject = stage.rollback_subject()
    waiting = stage.tool.rollback(stage.decide("rollback", subject), subject)
    assert waiting["v1Serving"] is True and waiting["reason"] == "rehearsal-creation-failed"
    done = run_word(stage.tool, "retry-copy", {})
    assert done["state"] == "rolled-back", done
    (copy,) = rollback_copies(stage, stage.tool.machine.current())
    assert calls == [database_of(copy)] * 2 and "completedAt" in copy


# --- 7d. v2 kept stopped after a rollback: its stops renewed in person (the person's
# decision of 2026-10-25, "Add an in-person stop command"; Step 44 test item 3) -------------


def on_one_clock(services, held):
    """The isolation check's question with the store's clock read as the stage's injected
    one (`FixedServices.aligned`): the stage's clock is not the store's real one, and the
    receipt-time window compares a receipt's bind time with its record's `stoppedAt`."""

    def aligned_held(record: dict) -> bool:
        with services.aligned():
            return held(record)

    return aligned_held


def kept_stopped(stage, tmp_path):
    """The rolled-back record, with v2's three roles stopped in person through the
    operator tool's service control, their stop records written by production's fixed
    program under a test prefix, on the stage's injected clock."""
    from docsuri_ops.arrangement.paths import ArrangementPaths
    from tests.u8_service_operations_integration import service_flows as sf

    rolled_back(stage)
    services = sf.FixedServices(ArrangementPaths.under(tmp_path / "prefix"), stage.clock)
    operator = sf.in_person(stage.operator, services)
    labels = stage.platform.v2_labels
    from docsuri_ops.isolation_check import receipt_held_by
    from docsuri_ops.u8_platform.service_words import (
        OperatorReceipts,
        planned_by_check,
        run_service,
        stop_expiries,
    )

    for label in labels:
        run_service("stop", label, operator)
    # As production's wiring shows them: each record's `planned`, computed as the
    # isolation check computes it, its receipt read through the operator's own grants.
    planned = planned_by_check(owner_uid=os.getuid(),
                               held=on_one_clock(services,
                                                 receipt_held_by(OperatorReceipts(operator))),
                               now=stage.clock)
    stage.platform.stop_records = lambda: stop_expiries(services.paths.control_stops, labels,
                                                        now=stage.clock(), planned=planned)
    return services, operator, labels


def boot_item(stage, services, operator, labels):
    """The isolation check's `boot` item on the stage's clock: the jobs stopped, each
    stop record read under the prefix and its receipt asked of the realm's store through
    the check's own production reader (`isolation_check.production_receipt_held` over
    `receipt_held_by(ReceiptReader)`), built as the root-run check builds it: the binding
    read with its owner named (review finding, Critical, R10)."""
    from types import SimpleNamespace

    from docsuri_ops.arrangement.paths import Accounts
    from docsuri_ops.isolation_check import CheckContext, IsolationCheck, ItemFailed
    from tests.u8_service_operations_integration import service_flows as sf

    tools = SimpleNamespace(disabled=lambda: {label: True for label in labels},
                            job=lambda label: {"state": "not running"})
    check = IsolationCheck(CheckContext(
        paths=services.paths, accounts=Accounts.for_tests(), tools=tools, clock=stage.clock,
        owner_uid=os.getuid(), boot_labels=labels,
        receipt_held=on_one_clock(services, sf.held_as_root(operator, services.paths))))
    try:
        check.boot()
    except ItemFailed as failure:
        return failure.reason, check.stop_records
    return "passed", check.stop_records


def test_a_record_kept_rolled_back_15_days_passes_once_its_stops_are_renewed(stage, tmp_path):
    from docsuri_ops.u8_platform.service_words import run_service

    services, operator, labels = kept_stopped(stage, tmp_path)
    assert boot_item(stage, services, operator, labels)[0] == "passed"
    first = {item["label"]: item for item in run_word(stage.tool, "status", {})[
        "v2StopRecords"]}
    # Day 13: the operator renews each stop in person with `service stop`.
    stage.clock.advance(13 * 86400)
    for label in labels:
        run_service("stop", label, operator)
    stage.clock.advance(2 * 86400)  # day 15
    assert stage.tool.machine.current()["state"] == "rolled-back"
    passed, records = boot_item(stage, services, operator, labels)
    assert passed == "passed" and sorted(record["label"] for record in records) == sorted(labels)
    # `cutover status` shows each v2 stop record's expiry while the record is rolled-back.
    status = run_word(stage.tool, "status", {})
    shown = {item["label"]: item for item in status["v2StopRecords"]}
    assert set(shown) == set(labels)
    for label in labels:
        assert shown[label]["lapsed"] is False and shown[label]["planned"] is True
        assert first[label]["planned"] is True
        assert shown[label]["expiresAt"] > first[label]["expiresAt"]
        assert dt.datetime.fromisoformat(shown[label]["expiresAt"]) == (
            stage.clock() - dt.timedelta(days=2) + dt.timedelta(days=14))


def test_a_record_kept_rolled_back_15_days_lapses_when_its_stops_are_not_renewed(stage,
                                                                                tmp_path):
    services, operator, labels = kept_stopped(stage, tmp_path)
    stage.clock.advance(15 * 86400)
    assert boot_item(stage, services, operator, labels)[0] == "boot-item-lapsed"
    shown = run_word(stage.tool, "status", {})["v2StopRecords"]
    assert [item["lapsed"] for item in shown] == [True] * len(labels)
    assert [item["planned"] for item in shown] == [False] * len(labels)
    assert all(item["expiresAt"] is not None for item in shown)


def test_status_shows_a_record_the_isolation_check_would_not_count_as_not_planned(
        stage, tmp_path):
    """The review's fix of 2026-10-26: `cutover status` shows each stop record's
    `planned` computed the way the isolation check computes it, so a record within its
    expiry that cites a start receipt (the first role), is not the fixed program's
    account's (the second), or is altered past its bound (the third) shows `planned:
    false` though `lapsed` is false."""
    import json

    from docsuri_ops.u8_platform import fixed
    from docsuri_ops.u8_platform.service_words import run_service

    services, operator, labels = kept_stopped(stage, tmp_path)
    shown = {item["label"]: item for item in run_word(stage.tool, "status", {})[
        "v2StopRecords"]}
    assert all(shown[label]["planned"] is True for label in labels)
    paths = [fixed.stop_record_path(services.paths, label) for label in labels]
    records = [json.loads(path.read_bytes()) for path in paths]
    started = run_service("start", labels[0], operator)
    services.unloaded.add(labels[0])  # as if stopped again outside the service control
    paths[0].write_text(json.dumps({**records[0], "receiptId": started["operationId"]}))
    paths[1].chmod(0o666)
    stopped = dt.datetime.fromisoformat(records[2]["stoppedAt"])
    paths[2].write_text(json.dumps({**records[2], "expiresAt": (
        stopped + dt.timedelta(days=30)).isoformat()}))
    shown = {item["label"]: item for item in run_word(stage.tool, "status", {})[
        "v2StopRecords"]}
    for label in labels:
        assert shown[label]["planned"] is False and shown[label]["lapsed"] is False, shown


def test_a_soak_waiting_for_an_unprobed_release_starts_no_v2_from_check(stage):
    """The person's decision of 2026-10-25 ("Probe it when the soak starts"): a release
    installed while v2 was kept stopped is probed when the soak starts, by the release
    command (`docsuri-release verify`), which holds the links; `cutover check` leaves v2
    stopped and the record rolled-back until then."""
    rolled_back(stage)
    stage.tool.machine.new_release("v2.0.1")
    run, name = accepted_run(stage)
    stage.tool.after_dry_run(run["runId"], name)
    stage.tool.machine.verification_passed(uuid4(), "v2.0.1")
    stage.platform.release_unprobed = lambda: "v2.0.1"
    checked = run_word(stage.tool, "check", {})
    assert checked["soak"] == {"soak": None, "v2Start": {
        "reason": "release-not-probed", "releaseTag": "v2.0.1",
        "offered": ["echo '{\"tag\": \"v2.0.1\"}' | sudo -k "
                    "/Library/DocSuri/release/ops/bin/docsuri-release verify"]}}, checked
    assert v2_states(stage) == {"stopped"}
    assert stage.tool.machine.current()["state"] == "rolled-back"
    # Once the release command probed it, `check` starts v2 and the soak.
    stage.platform.release_unprobed = lambda: None
    assert run_word(stage.tool, "check", {})["soak"]["soak"] == "started"
    assert v2_states(stage) == {"running"}


def test_productions_cutover_names_an_unprobed_release_from_its_install_record(tmp_path):
    from docsuri_ops.arrangement.paths import ArrangementPaths
    from tests.u8_service_operations_integration import recovery_flows as recovery

    paths = ArrangementPaths.under(tmp_path / "prefix")
    ledger = recovery.open_ledger(tmp_path, lambda: NOW)
    try:
        from backend.modules.operations.release_records import ReleaseRecords

        records = ReleaseRecords(ledger, clock=lambda: NOW)
        records.begin("v2.0.1", "c" * 40, previous_tag=None)
        records.finish("v2.0.1", "installed", probe_pending=True)
        assert wiring.unprobed_release(ledger, paths, clock=lambda: NOW) == "v2.0.1"
        records.finish("v2.0.1", "installed", probe_pending=False)
        assert wiring.unprobed_release(ledger, paths, clock=lambda: NOW) is None
    finally:
        ledger.close()


def released(stage, tmp_path, realm):
    """The release command on the cutover stage's own ledger, operator, clock and v2 (its
    links under a temporary prefix, `release` at the record's tag), with production's
    readers on the cutover tool: the release the links point to
    (`wiring.linked_release`) and the one waiting for its probe
    (`wiring.unprobed_release`)."""
    from tests.u8_service_operations_integration.operations.test_release_install import (
        stage_for,
    )

    release = stage_for(tmp_path / "release", realm, ledger=stage.ledger, clock=stage.clock,
                        journey=stage.journey, operator=stage.operator,
                        labels=stage.platform.v2_labels)
    release.platform.mode = lambda: "rehearsal"  # as the cutover rollback leaves it
    stage.platform.release_unprobed = lambda: wiring.unprobed_release(
        stage.ledger, release.paths, clock=stage.clock)
    stage.platform.evidence.linked_release = lambda: wiring.linked_release(release.paths)
    return release


def installed_while_stopped(stage, tmp_path, realm):
    """A cutover rolled back, a release installed while v2 is kept stopped (no dry run
    accepted since), then a dry run accepted onto its own rehearsal database."""
    rolled_back(stage)
    release = released(stage, tmp_path, realm)
    result = release.install.install(release.tag)
    assert result["state"] == "installed" and result["v2"] == "stopped", result
    record = stage.tool.machine.current()
    # Review finding (Major, R13): no verification for a release that has not been probed.
    assert result["verification"]["cutover"] == {"state": "rolled-back",
                                                 "reason": "release-not-probed"}
    assert record["releaseTag"] == release.tag and "verificationRunId" not in record
    assert "soak" not in run_word(stage.tool, "check", {})
    run, name = accepted_run(stage)
    assert stage.tool.after_dry_run(run["runId"], name)["soak"] is None
    assert v2_states(stage) == {"stopped"}
    return release


def no_soak_from_check(stage) -> dict:
    checked = run_word(stage.tool, "check", {})
    record = stage.tool.machine.current()
    assert record["state"] == "rolled-back" and "soakStartedAt" not in record, checked
    assert v2_states(stage) == {"stopped"}
    return checked


def test_a_failed_probe_at_the_soaks_start_through_productions_readers(stage, tmp_path,
                                                                       realm):
    """Your decision of 2026-10-26 ("Leave v2 stopped"; box item 1) on production's
    readers: the release installed while v2 was kept stopped fails its probe when
    `docsuri-release verify` starts the soak. v2's three roles are left stopped with
    held receipts, the ReleaseRecord ends switched-back with `probePending` cleared, the
    CutoverRecord stays rolled-back named for the linked tag with no verification, and
    `cutover check` starts no soak; `verify` on the linked tag then starts it."""
    from docsuri_ops import release as release_module
    from docsuri_ops.release import ReleaseInstall
    from docsuri_ops.u8_platform.u8_protocols import ReceiptReader

    release = installed_while_stopped(stage, tmp_path, realm)
    release.state["probe"] = False
    moved = release.install.verify(release.tag)["verification"]["cutover"]
    assert moved["probe"] == "failed" and moved["reason"] == "release-probe-failed", moved
    assert moved["switchedBack"]["state"] == "switched-back"
    assert moved["cutoverRelease"] == {"state": "rolled-back", "releaseTag": cf.TAG}
    assert release.link() == cf.TAG and v2_states(stage) == {"stopped"}
    for label in stage.platform.v2_labels:
        stop = stage.journey.read_state("stops", f"{label}.json")
        held = stage.operator._read_named(stop["operationId"])
        assert held["operation"] == "platform.service.control"
        assert ReceiptReader.outcome(held) == "succeeded"
    failed = release.install.records.get(release.tag)
    assert failed["state"] == "switched-back" and "probePending" not in failed
    assert wiring.unprobed_release(stage.ledger, release.paths, clock=stage.clock) is None
    record = stage.tool.machine.current()
    assert record["releaseTag"] == cf.TAG and "verificationRunId" not in record
    assert "soak" not in no_soak_from_check(stage)
    # The linked tag's `verify` starts v2 and the soak.
    release_module.write_identity(release.paths.releases / cf.TAG, cf.TAG,
                                  release.github.commit, owner_uid=os.getuid())
    release.github.tags[cf.TAG] = dict(release.github.tags[release.tag])
    release.state["probe"] = True
    verified = ReleaseInstall(release.paths, release.platform, clock=stage.clock).verify(cf.TAG)
    assert verified["verification"]["cutover"]["soak"] == "started", verified
    assert v2_states(stage) == {"running"}
    assert stage.tool.machine.current()["state"] in ("rehearsing", "ready-to-switch")


def test_a_failed_probe_whose_cutover_naming_fails_starts_no_soak(stage, tmp_path, realm,
                                                                  monkeypatch):
    """Review finding (Major, R13 (a)): after the failed probe, naming the CutoverRecord
    for the linked tag fails (a ledger failure). The record keeps the failed release's
    tag, but it never held a verification for it, so `cutover check` starts no soak.
    Even a record that did hold one (as an earlier version could leave it) starts none:
    production's linked-release reader refuses it `release-not-linked`, in the soak and
    in BR9.2's precondition (1)."""
    from docsuri_ops.release import ReleaseInstall

    release = installed_while_stopped(stage, tmp_path, realm)

    def broken(self):
        raise wiring.WiringRefused("ledger-contended")

    monkeypatch.setattr(ReleaseInstall, "_name_cutover_release", broken)
    release.state["probe"] = False
    moved = release.install.verify(release.tag)["verification"]["cutover"]
    assert moved["probe"] == "failed" and moved["switchedBack"]["state"] == "switched-back"
    assert moved["cutoverRelease"] == {"reason": "cutover-release-unnamed"}, moved
    record = stage.tool.machine.current()
    assert record["releaseTag"] == release.tag and "verificationRunId" not in record
    assert release.link() == cf.TAG
    assert "soak" not in no_soak_from_check(stage)
    # Defence in depth: a verification held for a release the links do not point to.
    stage.tool.machine.verification_passed(uuid4(), release.tag)
    checked = no_soak_from_check(stage)
    start = checked["soak"]["v2Start"]
    assert (start["reason"], start["releaseTag"], start["linkedTag"]) == (
        "release-not-linked", release.tag, cf.TAG), checked
    stage.platform.evidence.verification = lambda run: {"passed": True,
                                                        "releaseTag": release.tag}
    assert "release-not-linked" in stage.tool.missing()
    assert "verification-not-passed" not in stage.tool.missing()


def test_a_failed_probe_whose_relink_fails_keeps_the_record_waiting_for_recover(
        stage, tmp_path, realm):
    """Review finding (Major, R13 (b)): the failed probe's switch back cannot relink (no
    kept release), so the links still point at the failed release. Its record stays
    `installed` and waiting for its probe (`switch-back-failed`), so production's reader
    still names it unprobed and `cutover check` starts no soak on it; `recover`, once the
    kept release is back, points the links back and ends the record switched-back."""
    from docsuri_ops.release import ReleaseInstall

    release = installed_while_stopped(stage, tmp_path, realm)
    kept = Path(os.readlink(release.paths.release_previous))
    release.paths.release_previous.unlink()
    release.state["probe"] = False
    moved = release.install.verify(release.tag)["verification"]["cutover"]
    switched = moved["switchedBack"]
    assert switched["state"] == "failed" and switched["step"] == "no-kept-release", moved
    assert release.link() == release.tag
    record = release.install.records.get(release.tag)
    assert record["state"] == "installed" and record["probePending"] is True
    assert record["reasonKey"] == "switch-back-failed"
    assert wiring.unprobed_release(stage.ledger, release.paths,
                                   clock=stage.clock) == release.tag
    cutover = stage.tool.machine.current()
    assert cutover["releaseTag"] == release.tag and "verificationRunId" not in cutover
    assert "soak" not in no_soak_from_check(stage)
    os.symlink(kept, release.paths.release_previous)
    result = ReleaseInstall(release.paths, release.platform, clock=stage.clock).recover()
    assert result["record"] == "switched-back" and result["v2"] == "stopped", result
    assert release.link() == cf.TAG
    ended = release.install.records.get(release.tag)
    assert ended["state"] == "switched-back" and "probePending" not in ended
    assert wiring.unprobed_release(stage.ledger, release.paths, clock=stage.clock) is None
    assert stage.tool.machine.current()["releaseTag"] == cf.TAG
    assert "soak" not in no_soak_from_check(stage)


def test_status_shows_no_stop_records_outside_rolled_back(stage):
    stage.platform.stop_records = lambda: pytest.fail("read outside rolled-back")
    stage.switched()
    assert "v2StopRecords" not in run_word(stage.tool, "status", {})


def test_the_cutover_command_answers_a_refused_release(monkeypatch, capsys):
    """The maintainer's decision of 2026-11-16 ("Fix the test and answer refusals"): a
    credential release that refuses is one JSON refusal, never a traceback. A stand-in
    keychain for the release refuses, so nothing reaches this Mac's sudo or ledger."""
    import io
    import sys

    from docsuri_ops.cutover import tool as cutover_tool
    from docsuri_ops.u8_platform.credential_release import ReleaseRefused

    monkeypatch.setattr(wiring, "_authorities",
                        lambda paths: {"actors": {"operator": "someone-else"}})
    asked = []

    def refused(login):
        asked.append(login)
        raise ReleaseRefused("the credential was not released")

    monkeypatch.setattr("docsuri_ops.u8_platform.credential_release.release_with_actor",
                        refused)
    monkeypatch.setattr(sys, "stdin", type("In", (), {"buffer": io.BytesIO(b"{}")})())
    assert cutover_tool.main(["status", "--production"]) == 1
    captured = capsys.readouterr()
    assert json.loads(captured.out) == {"ok": False, "reason": "credential-not-released"}
    assert "Traceback" not in captured.err and asked == ["platform"]
