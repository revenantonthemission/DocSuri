"""The operator tool's in-person service control (the person's decision of 2026-10-25,
"Add an in-person stop command"; U8 plan Step 44, test item 1; Workflow 20 step 9,
BR6.12, NFR7.19).

`service stop` and `service start` run only in person, only on v2's three labels, each
through `platform.service.control` on the composed realm's PlatformControl store, so the
receipt is bound before the fixed program writes or removes the stop record, and the
record cites a receipt the store holds. `service stop` on a stopped job renews its record.
"""

from __future__ import annotations

import datetime as dt
import io
import json
import sys
from types import SimpleNamespace
from uuid import uuid4

import pytest

from docsuri_ops.arrangement.paths import ArrangementPaths
from docsuri_ops.platform_control.errors import ControlError
from docsuri_ops.u8_platform import fixed, operator_tool, service_words
from docsuri_ops.u8_platform.service_words import run_service, stop_expiries, v2_labels
from docsuri_ops.u8_platform.u8_protocols import Operator
from tests.u8_service_operations_integration import platform_flows as pf
from tests.u8_service_operations_integration.service_flows import (
    FixedServices,
    RecordingStore,
    in_person,
    receipt_held,
)

HOST = "dev.docsuri.u8.run.host"
WORKERS = "dev.docsuri.u8.run.workers"


@pytest.fixture
def journey(tmp_path, realm):
    return pf.journey(tmp_path, realm)


def services_for(tmp_path, clock) -> FixedServices:
    return FixedServices(ArrangementPaths.under(tmp_path / "prefix"), clock)


def test_v2s_three_labels_are_the_only_ones(journey):
    assert v2_labels(journey.profile.labels) == (
        "dev.docsuri.u8.run.host", "dev.docsuri.u8.run.workers",
        "dev.docsuri.u8.run.scheduler")
    from docsuri_ops.u8_platform.platform_profile import PRODUCTION_LABELS

    assert v2_labels(PRODUCTION_LABELS) == ("org.docsuri.v2.host", "org.docsuri.v2.workers",
                                            "org.docsuri.v2.scheduler")


def test_a_stop_binds_its_receipt_before_the_record_and_the_record_cites_it(
        tmp_path, journey, clock):
    services = services_for(tmp_path, clock)
    operator = in_person(journey.operator(clock=clock), services)
    stopped = run_service("stop", WORKERS, operator)
    assert stopped["outcome"] == "succeeded" and stopped["action"] == "stop"
    # When the fixed program ran, the store already held the receipt and no record
    # cited it yet.
    assert services.seen == [{"operationId": stopped["operationId"], "bound": True,
                              "recordCitedIt": False}]
    record = fixed.read_stop_record(fixed.stop_record_path(services.paths, WORKERS),
                                    owner_uid=services.context().owner_uid, now=clock())
    assert record["receiptId"] == stopped["operationId"]
    assert receipt_held(operator)(record) is True
    assert services.launchctl == [["/bin/launchctl", "disable", f"system/{WORKERS}"],
                                  ["/bin/launchctl", "bootout", f"system/{WORKERS}"]]


def test_a_stop_of_a_stopped_job_renews_its_record_under_a_new_receipt(
        tmp_path, journey, clock):
    services = services_for(tmp_path, clock)
    operator = in_person(journey.operator(clock=clock), services)
    path = fixed.stop_record_path(services.paths, HOST)
    first = run_service("stop", HOST, operator)
    before = json.loads(path.read_bytes())
    clock.advance(13 * 86400)
    services.launchctl.clear()
    renewed = run_service("stop", HOST, operator)
    after = json.loads(path.read_bytes())
    assert renewed["operationId"] != first["operationId"]
    assert after["receiptId"] == renewed["operationId"]
    assert dt.datetime.fromisoformat(after["expiresAt"]) == clock() + dt.timedelta(days=14)
    assert after["expiresAt"] > before["expiresAt"]
    # Decided from launchd's state: the bootout answers not loaded (3), so the record
    # is renewed rather than the stop failing.
    assert services.launchctl == [["/bin/launchctl", "disable", f"system/{HOST}"],
                                  ["/bin/launchctl", "bootout", f"system/{HOST}"]]
    assert services.unloaded == {HOST}
    assert receipt_held(operator)(after) is True


def test_the_root_run_check_reads_the_service_accounts_binding_and_holds_real_stops(
        tmp_path, journey, clock):
    """Review finding (Critical, R10): `docsuri-isolation-check` runs as root and the
    binding is the service account's own (0600). The check names that account as the
    binding's owner, so a stop bound in the store is held; a read that wants the reading
    account's own file (U7's `private_bytes`), or names another owner, holds nothing."""
    from unittest import mock

    from docsuri_ops import isolation_check
    from docsuri_ops.u8_platform import platform_profile
    from docsuri_ops.u8_platform.u8_protocols import readers
    from tests.u8_service_operations_integration.service_flows import held_as_root

    services = services_for(tmp_path, clock)
    operator = in_person(journey.operator(clock=clock), services)
    stopped = run_service("stop", HOST, operator)
    record = fixed.read_stop_record(fixed.stop_record_path(services.paths, HOST),
                                    owner_uid=services.context().owner_uid, now=clock())
    held = held_as_root(operator, services.paths)
    assert held(record) is True
    assert held({**record, "label": WORKERS}) is False  # another label's stop
    # The read before the fix: U7's own-account check refuses the binding under root.
    real = platform_profile.private_bytes

    def as_root(path, **options):
        if path.name == platform_profile.READER_FILE:
            raise ValueError("not the reading account's own")
        return real(path, **options)

    with mock.patch.object(platform_profile, "private_bytes", as_root), pytest.raises(
            ValueError):
        readers(operator.profile)
    # Another owner named: refused, nothing held (fail closed).
    import os

    assert held_as_root(operator, services.paths, owner_uid=os.getuid() + 1)(record) is False
    # Through the isolation check's boot item, on the injected clock.
    tools = SimpleNamespace(disabled=lambda: {HOST: True},
                            job=lambda label: {"state": "not running"})
    from docsuri_ops.arrangement.paths import Accounts

    check = isolation_check.IsolationCheck(isolation_check.CheckContext(
        paths=services.paths, accounts=Accounts.for_tests(), tools=tools, clock=clock,
        owner_uid=os.getuid(), boot_labels=(HOST,), receipt_held=held))
    check.boot()
    assert [item["receiptId"] for item in check.stop_records] == [stopped["operationId"]]


def test_an_owned_private_read_refuses_a_loose_mode_a_link_and_another_owner(tmp_path):
    import os

    from docsuri_ops.u8_platform.platform_profile import owned_private_bytes

    path = tmp_path / "binding.json"
    path.write_bytes(b"{}")
    path.chmod(0o600)
    assert owned_private_bytes(path, owner_uid=os.getuid()) == b"{}"
    with pytest.raises(ValueError):
        owned_private_bytes(path, owner_uid=os.getuid() + 1)
    path.chmod(0o640)
    with pytest.raises(ValueError):
        owned_private_bytes(path, owner_uid=os.getuid())
    path.chmod(0o600)
    link = tmp_path / "link.json"
    link.symlink_to(path)
    with pytest.raises(OSError):
        owned_private_bytes(link, owner_uid=os.getuid())


def test_a_start_removes_the_record_through_its_own_bound_receipt(tmp_path, journey, clock):
    services = services_for(tmp_path, clock)
    operator = in_person(journey.operator(clock=clock), services)
    run_service("stop", HOST, operator)
    started = run_service("start", HOST, operator)
    assert started["outcome"] == "succeeded"
    assert services.seen[-1]["bound"] is True
    assert not fixed.stop_record_path(services.paths, HOST).exists()


def test_the_realms_own_driver_leaves_a_record_citing_a_receipt_the_store_holds(journey):
    """Through the realm driver (U7's bounded child), as the realm's `service stop` runs."""
    operator = journey.operator()
    stopped = run_service("stop", WORKERS, operator)
    record = journey.read_state("stops", f"{WORKERS}.json")
    assert record["operationId"] == stopped["operationId"]
    held = operator._read_named(stopped["operationId"])
    assert held["operation"] == "platform.service.control" and str(held["targetId"]) == WORKERS
    started = run_service("start", WORKERS, operator)
    assert started["outcome"] == "succeeded"
    assert journey.read_state("stops", f"{WORKERS}.json") is None


def recording(journey, *, standing: bool = False):
    base = journey.operator("scheduler" if standing else "operator")
    store = RecordingStore(base.store)
    return Operator(base.profile, store, actor=base.actor, authorities=base.authorities,
                    facts=base.facts, standing=standing), store


def test_service_control_runs_only_in_person(journey):
    scheduler, store = recording(journey, standing=True)
    with pytest.raises(ControlError) as caught:
        run_service("stop", HOST, scheduler)
    assert caught.value.code == "FORBIDDEN" and store.bound == []
    assert journey.read_state("stops", f"{HOST}.json") is None


@pytest.mark.parametrize("label", ["dev.docsuri.u8.run.v1-api", "dev.docsuri.u8.run.standing",
                                   "org.docsuri.v2.host", "", "../host"])
def test_a_label_outside_v2s_three_is_refused_before_anything_is_bound(journey, label):
    operator, store = recording(journey)
    with pytest.raises(ControlError) as caught:
        run_service("stop", label, operator)
    assert caught.value.as_wire_error()["messageKey"] == "label-refused"
    assert store.bound == []


@pytest.mark.parametrize("word", ["restart", "kill", ""])
def test_an_unknown_word_is_refused_before_anything_is_bound(journey, word):
    operator, store = recording(journey)
    with pytest.raises(ControlError) as caught:
        run_service(word, HOST, operator)
    assert caught.value.code == "INVALID_INPUT" and store.bound == []


def tool(monkeypatch, argv: list[str], payload: bytes = b"{}", operator=None) -> tuple:
    """The operator tool's `service` command in-process, its realm operator the test's."""
    if operator is not None:
        monkeypatch.setattr(service_words, "realm_operator_for",
                            lambda path, **options: (operator, service_words._NoLedger()))
    monkeypatch.setattr(sys, "stdin", SimpleNamespace(buffer=io.BytesIO(payload)))
    out = io.StringIO()
    monkeypatch.setattr(sys, "stdout", out)
    code = operator_tool.main(["service", *argv])
    return code, out.getvalue()


def test_the_operator_tool_routes_service_and_answers_one_json_result(
        tmp_path, journey, clock, monkeypatch):
    services = services_for(tmp_path, clock)
    operator = in_person(journey.operator(clock=clock), services)
    environment = ["--environment-file", str(tmp_path / "environment.json")]
    code, out = tool(monkeypatch, ["stop", HOST, *environment], operator=operator)
    assert code == 0, out
    answer = json.loads(out)
    assert answer["ok"] is True and answer["result"]["label"] == HOST
    record = json.loads(fixed.stop_record_path(services.paths, HOST).read_bytes())
    assert record["receiptId"] == answer["result"]["operationId"]


def test_the_operator_tool_refuses_its_inputs_outside_their_form(
        tmp_path, journey, monkeypatch):
    operator, store = recording(journey)
    environment = ["--environment-file", str(tmp_path / "environment.json")]
    for payload, code_name in ((b'{"label": "x"}', "INVALID_INPUT"),
                               (b"[]", "INVALID_INPUT"), (b"{" + b" " * 2048 + b"}",
                                                          "INVALID_INPUT")):
        code, out = tool(monkeypatch, ["stop", HOST, *environment], payload, operator=operator)
        assert code == 1 and json.loads(out)["error"]["code"] == code_name
    code, out = tool(monkeypatch, ["stop", HOST, *environment], b"not json", operator=operator)
    assert code == 1 and json.loads(out) == {"ok": False, "reason": "input-not-json"}
    # Neither production nor the realm named, or both: refused before any wiring.
    for argv in (["stop", HOST], ["stop", HOST, "--production", *environment]):
        code, out = tool(monkeypatch, argv, operator=operator)
        assert code == 1 and json.loads(out)["error"]["code"] == "POLICY_UNRESOLVED"
    # A label outside v2's three through the tool.
    code, out = tool(monkeypatch, ["stop", "dev.docsuri.u8.run.v1-api", *environment],
                     operator=operator)
    assert code == 1 and json.loads(out)["error"]["messageKey"] == "label-refused"
    assert store.bound == []


def test_the_operator_tool_refuses_an_unknown_service_word(monkeypatch):
    with pytest.raises(SystemExit) as exited:
        tool(monkeypatch, ["restart", HOST, "--production"])
    assert exited.value.code == 2


@pytest.mark.parametrize(("raised", "reason"), [
    (ValueError("private record must be a bounded owned regular file"), "profile-unreadable"),
    (OSError("gone"), "profile-unreadable"),
    (RuntimeError("anything else"), "service-control-failed"),
])
def test_only_a_json_error_answers_input_not_json(tmp_path, monkeypatch, raised, reason):
    """The review's fix of 2026-10-26: `input-not-json` answers a JSON error only; a
    failure of the wiring or the run (a profile or binding that cannot be read, anything
    else) answers its own fixed reason, never a path, value or traceback."""

    def wiring(path, **options):
        raise raised

    monkeypatch.setattr(service_words, "realm_operator_for", wiring)
    environment = ["--environment-file", str(tmp_path / "environment.json")]
    code, out = tool(monkeypatch, ["stop", HOST, *environment])
    assert code == 1 and json.loads(out) == {"ok": False, "reason": reason}
    assert str(tmp_path) not in out


def test_a_driver_refusal_through_the_tool_answers_its_own_reason(tmp_path, monkeypatch):
    from docsuri_ops.u8_platform.drivers import DriverRefused

    def wiring(path, **options):
        raise DriverRefused("config-unreadable")

    monkeypatch.setattr(service_words, "realm_operator_for", wiring)
    code, out = tool(monkeypatch, ["start", HOST, "--environment-file",
                                   str(tmp_path / "environment.json")])
    assert code == 1 and json.loads(out) == {"ok": False, "reason": "config-unreadable"}


def unresolved_on(operator, target: str) -> list:
    """PlatformControl's unresolved receipts on one target, through each of the
    operator's grants (what keeps its status degraded)."""
    found = []
    for authority in set(operator.authorities.values()):
        found += [item for item in operator.store.list_unresolved(operator.actor, authority)
                  if str(item["targetId"]) == target]
    return found


def lease_passed(realm, target: str) -> None:
    """The interrupted operation's lease deadline moved into the past, as time would."""
    from tests.u8_service_operations_integration import recovery_flows as rf

    with rf.admin(realm, "docsuri_u8_platform") as conn:
        conn.execute("UPDATE platform_control.target_lease SET deadline_at=clock_timestamp()"
                     "-interval '1 hour' WHERE target_id=%s", (target,))


def test_an_interrupted_service_control_is_reconciled_before_the_next_one_binds(
        journey, clock, realm):
    """The review's fix of 2026-10-26: a `service` run interrupted after its receipt was
    bound (Ctrl-C, a kill) leaves an operation under a key no later run walks. Within its
    lease the next run is refused by PlatformControl's target lease; once the lease has
    passed, the next run reconciles it from its target first (not applied: the effect
    never ran), so PlatformControl's status is no longer degraded, then binds its own."""

    def killed(**request):
        raise KeyboardInterrupt

    interrupted = journey.operator(clock=clock, run_effect=killed)
    with pytest.raises(KeyboardInterrupt):
        run_service("stop", WORKERS, interrupted)
    operator = journey.operator(clock=clock)
    with pytest.raises(ControlError) as caught:
        run_service("stop", WORKERS, operator)  # within the lease
    assert caught.value.code == "CONFLICT"
    lease_passed(realm, WORKERS)
    stopped = run_service("stop", WORKERS, operator)
    assert stopped["outcome"] == "succeeded"
    assert unresolved_on(operator, WORKERS) == []
    record = journey.read_state("stops", f"{WORKERS}.json")
    assert record["operationId"] == stopped["operationId"]


def test_an_effect_bound_but_stopped_before_its_input_is_reconciled_not_applied(
        journey, clock, monkeypatch, realm):
    """The review's fix of 2026-10-26 ("an effect bound but stopped before its input was
    written"): the run stopped between PlatformControl's binding and the input's write.
    The earlier run's key is then settled (`settle_earlier`): no input, so nothing runs
    for it, and once its lease has passed its operation is reconciled not applied, so
    PlatformControl's status is no longer degraded by it."""
    from docsuri_ops.u8_platform import u8_protocols
    from docsuri_ops.u8_platform.u8_protocols import settle_earlier

    operator = journey.operator(clock=clock)
    inputs = {"label": HOST, "action": "stop"}
    # A key of this run's own: pytest's temporary folder names repeat between sessions,
    # and a realm that already ran this test holds a receipt under such a key, which
    # `execute` would answer without binding (so nothing would stop before the input).
    key = f"service:stop:{HOST}:bound-before-input-{uuid4().hex}"
    real = u8_protocols.write_input

    def stopped(*args, **options):
        raise KeyboardInterrupt

    monkeypatch.setattr(u8_protocols, "write_input", stopped)
    with pytest.raises(KeyboardInterrupt):
        operator.execute("platform.service.control", HOST, inputs, key=key)
    monkeypatch.setattr(u8_protocols, "write_input", real)
    # Within its lease nothing can be bound beside it; once the lease has passed, the
    # earlier run's key is settled.
    lease_passed(realm, HOST)
    assert settle_earlier(operator, "platform.service.control", HOST, inputs, key=key) is None
    assert unresolved_on(operator, HOST) == []
    assert journey.read_state("stops", f"{HOST}.json") is None  # the effect never ran
    # The key's receipt reads as reconciled not applied, and a new run binds beside it.
    assert run_service("stop", HOST, operator)["outcome"] == "succeeded"


def test_stop_expiries_show_each_v2_record_and_its_lapse(tmp_path, clock):
    folder = tmp_path / "stops"
    folder.mkdir()
    now = clock()
    (folder / f"{HOST}.json").write_text(json.dumps(
        {"label": HOST, "operationId": "op-1", "stoppedAt": now.isoformat(),
         "expiresAt": (now + dt.timedelta(days=14)).isoformat()}))
    (folder / f"{WORKERS}.json").write_text("{not json")
    shown = stop_expiries(folder, (HOST, WORKERS, "dev.docsuri.u8.run.v1-api"),
                          now=now + dt.timedelta(days=15))
    assert shown == [
        {"label": HOST, "expiresAt": (now + dt.timedelta(days=14)).isoformat(),
         "receipt": "op-1", "lapsed": True},
        {"label": WORKERS, "expiresAt": None, "lapsed": True}]
