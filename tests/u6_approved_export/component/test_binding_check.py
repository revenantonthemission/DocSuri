"""The shared binding check: definite change versus could-not-check for every fact, the
42501 mapping, and the gate slot taken only for approve (BR3.1, BR3.3)."""

from uuid import UUID, uuid4

import psycopg
import pytest

from backend.modules.export.binding import BindingCheck, BoundFacts
from backend.modules.export.fake_notion import Answer
from backend.modules.research.errors import ResearchError
from backend.u6_policy import real_activation_export
from tests.u6_approved_export import service_flows as sf
from tests.u6_approved_export import store_flows as flows


def prepared(rig, *, session=None):
    """A connected owner, one preview revision, and the facts an approval would bind."""
    rig.configure()
    page = rig.page()
    preview = rig.preview(page)
    row = rig.repo.read_preview(rig.authority, UUID(preview["previewId"]))
    facts = BoundFacts.of(
        row,
        account_id=rig.authority.account_id,
        approving_session=session or rig.authority.session_id,
        artifact_id=row["artifact_id"],
        destination_id=row["destination_id"],
    )
    return facts, page


def verdict_of(verdict) -> tuple:
    return verdict.status, verdict.reason, verdict.code


def test_unchanged_facts_answer_unchanged_and_the_lane_takes_no_gate_slot(
    transactions, connect, authority, tmp_path
):
    rig = sf.build(transactions, connect, authority, tmp_path)
    facts, _ = prepared(rig)
    asked = len(rig.gate.asked)

    assert rig.service.binding.check(facts).unchanged
    assert len(rig.gate.asked) == asked
    assert rig.service.binding.check(facts, gate_key=facts.connection_id).unchanged
    assert rig.gate.asked[asked:] == [facts.connection_id]
    assert rig.gate.held == 0


def test_the_session_fact(transactions, connect, authority, tmp_path):
    rig = sf.build(transactions, connect, authority, tmp_path)
    other = flows.second_session(connect, authority)
    facts, _ = prepared(rig, session=other.session_id)
    flows.end_session(connect, other)

    assert verdict_of(rig.service.binding.check(facts)) == (
        "changed",
        "authority-revoked",
        "UNAUTHENTICATED",
    )
    # The real guard fails for real: a held session row runs it into the realm's lock bound.
    again = sf.build(transactions, connect, authority, tmp_path, keys="again")
    waiting = flows.second_session(connect, authority)
    live, _ = prepared(again, session=waiting.session_id)
    with flows.held_session(connect, waiting):
        with pytest.raises(psycopg.errors.LockNotAvailable):
            again.repo.session_is_current(waiting.account_id, waiting.session_id)
        held = again.service.binding.check(live)
    assert verdict_of(held) == (
        "could-not-check",
        "dependency-unavailable",
        "DEPENDENCY_UNAVAILABLE",
    )
    assert again.service.binding.check(live).unchanged


def test_the_connection_fact(transactions, connect, authority, tmp_path):
    rig = sf.build(transactions, connect, authority, tmp_path)
    facts, _ = prepared(rig)
    account, connection = authority.account_id, facts.connection_id
    asked = len(rig.fake.requests)

    assert rig.repo.set_availability(account, connection, 1, available=False)
    assert verdict_of(rig.service.binding.check(facts)) == (
        "could-not-check",
        "policy-unresolved",
        "POLICY_UNRESOLVED",
    )
    assert len(rig.fake.requests) == asked  # no Notion read while the token cannot open
    assert rig.repo.set_availability(account, connection, 1, available=True)
    token, _ = rig.new_token()
    rig.configure(token=token, expected=1)
    assert verdict_of(rig.service.binding.check(facts)) == (
        "changed",
        "connection-changed",
        "CONFLICT",
    )


def test_the_real_allowance_fact(transactions, connect, authority, tmp_path):
    rig = sf.build(transactions, connect, authority, tmp_path)
    facts, _ = prepared(rig)
    real = real_activation_export(
        activation_destination_id=uuid4().hex, free_terms_reference="free-terms-2026-10"
    )
    bounded = BindingCheck(rig.repo, rig.service.adapter, rig.research, real)

    assert verdict_of(bounded.check(facts)) == ("changed", "destination-changed", "FORBIDDEN")


@pytest.mark.parametrize(
    ("failure", "expected"),
    [
        (ResearchError("NOT_FOUND"), ("changed", "source-changed", "NOT_FOUND")),
        (ResearchError("CONFLICT"), ("changed", "source-changed", "CONFLICT")),
        (
            ResearchError("SOURCE_INELIGIBLE"),
            ("changed", "source-changed", "SOURCE_INELIGIBLE"),
        ),
        (
            psycopg.errors.InsufficientPrivilege("session refused"),
            ("changed", "authority-revoked", "UNAUTHENTICATED"),
        ),
        (
            ResearchError("POLICY_UNRESOLVED"),
            ("could-not-check", "policy-unresolved", "POLICY_UNRESOLVED"),
        ),
        (
            ResearchError("DEPENDENCY_UNAVAILABLE"),
            ("could-not-check", "dependency-unavailable", "DEPENDENCY_UNAVAILABLE"),
        ),
        (
            RuntimeError("unreachable"),
            ("could-not-check", "dependency-unavailable", "DEPENDENCY_UNAVAILABLE"),
        ),
    ],
)
def test_the_source_fact(transactions, connect, authority, tmp_path, failure, expected):
    rig = sf.build(transactions, connect, authority, tmp_path)
    facts, _ = prepared(rig)
    rig.research.failure = failure

    assert verdict_of(rig.service.binding.check(facts)) == expected
    approving = rig.research.calls[-1][0]
    assert (approving.account_id, approving.session_id) == (
        facts.account_id,
        facts.approving_session,
    )


def test_a_changed_eligibility_revision_is_a_changed_source(
    transactions, connect, authority, tmp_path
):
    rig = sf.build(transactions, connect, authority, tmp_path)
    facts, _ = prepared(rig)
    rig.research.set_eligibility(facts.source, "2")

    assert verdict_of(rig.service.binding.check(facts)) == (
        "changed",
        "source-changed",
        "CONFLICT",
    )


def test_the_destination_fact_and_a_definite_change_wins(
    transactions, connect, authority, tmp_path
):
    rig = sf.build(transactions, connect, authority, tmp_path)
    facts, page = prepared(rig)

    rig.fake.queue("pages.retrieve", Answer.error(503), target=page)
    assert verdict_of(rig.service.binding.check(facts)) == (
        "could-not-check",
        "dependency-unavailable",
        "DEPENDENCY_UNAVAILABLE",
    )
    rig.research.failure = ResearchError("DEPENDENCY_UNAVAILABLE")
    rig.fake.page(page).readable = False
    assert verdict_of(rig.service.binding.check(facts)) == (
        "changed",
        "destination-changed",
        "CONFLICT",
    )


def page_reads(rig) -> int:
    return sum(1 for entry in rig.fake.requests if entry.path.startswith("/v1/pages/"))


def test_approve_takes_a_gate_slot_a_continue_reads_no_destination_and_a_refused_slot_cannot_check(
    transactions, connect, authority, tmp_path
):
    rig = sf.build(transactions, connect, authority, tmp_path)
    facts, page = prepared(rig)
    connection = facts.connection_id

    asked = len(rig.gate.asked)
    approval = rig.approve(rig.preview(page))
    assert rig.gate.asked[asked + 1 :] == [connection]  # the preview's read, then approve's
    asked, reads = len(rig.gate.asked), page_reads(rig)
    rig.execute(approval)  # a continue: another key than the approval's
    assert rig.gate.asked[asked:] == []
    assert page_reads(rig) == reads
    assert rig.gate.try_acquire(connection)
    try:
        refused = rig.service.binding.check(facts, gate_key=connection)
    finally:
        rig.gate.release(connection)
    assert verdict_of(refused) == (
        "could-not-check",
        "dependency-unavailable",
        "DEPENDENCY_UNAVAILABLE",
    )

    rig.fake.page(page).readable = False
    asked, reads = len(rig.gate.asked), page_reads(rig)
    assert rig.service.binding.check(facts, destination=False).unchanged
    assert page_reads(rig) == reads
    assert rig.gate.asked[asked:] == []
    assert verdict_of(rig.service.binding.check(facts)) == (
        "changed",
        "destination-changed",
        "CONFLICT",
    )
