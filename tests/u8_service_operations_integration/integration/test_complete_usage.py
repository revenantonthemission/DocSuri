"""One usage authority in the complete realms (U8 plan Step 24; the person's decision of
2026-10-23, "U2's controls for all usage").

In the composed realm every usage call runs through U2's controls under the realm's own
policy, counted per policy period:

1. research, novelty and assistance reservations count together within a period, and a
   new period allows them again;
2. an ungranted account's refused request closes with nothing to release, and the
   worker's next pass completes;
3. settlement and release of each kind go through the same ledger rows the usage
   records show.
"""

from __future__ import annotations

import secrets
from uuid import uuid4

import pytest
from psycopg.types.json import Jsonb

from backend.modules.accounts.u8_control_policy import U8_SYNTHETIC_POLICY
from backend.modules.plans.control_service import ControlUsageService
from backend.modules.plans.guarded_repository import GuardedUsageRepository, UsageQuotaExceeded
from backend.modules.plans.u8_usage import (
    CompleteUsage,
    ImportedUsage,
    ResearchUsageService,
    usage_for,
)
from backend.transactions import Authority
from tests.u8_service_operations_integration import recovery_flows as rf
from tests.u8_service_operations_integration.host_flows import (
    MEMBER,
    OTHER_MEMBER,
    call,
    complete_host,
    member,
    session_of,
)

pytestmark = pytest.mark.usefixtures("own_address")
POLICY = U8_SYNTHETIC_POLICY


@pytest.fixture
def host(realm, own_address):
    with complete_host(realm, address=own_address) as value:
        yield value


def admin(host):
    realm = host.composition.profile
    return rf.admin(realm, realm.database_name)


def clear_usage(host, account_id) -> None:
    with admin(host) as conn, conn.transaction():
        for table in ("rejected_operation", "reservation", "entitlement"):
            conn.execute(f"DELETE FROM usage.{table} WHERE account_id=%s", (account_id,))


def live(host, sign_in_account, connect, suffix: str) -> Authority:
    signed, _ = member(host, sign_in_account, suffix)
    return Authority(signed.account_id, session_of(connect, signed.account_id))


def granted(host, sign_in_account, connect, suffix: str = MEMBER) -> Authority:
    owner = live(host, sign_in_account, connect, suffix)
    clear_usage(host, owner.account_id)
    usage = ImportedUsage(host.composition.transactions, POLICY)
    assert usage.grant_imported(owner.account_id, source="realm_fixture")["disposition"] == (
        "imported")
    return owner


def assistance_reserve(host, connect, owner) -> dict:
    """Paper assistance's reservation, through the same control service (the admission
    row as PaperAssistance's owner leaves it before the reservation)."""
    transactions = host.composition.transactions
    control = ControlUsageService(transactions, POLICY)
    period = ResearchUsageService(transactions, POLICY).current_period()
    with connect("assistance") as conn:
        row = conn.execute(
            "INSERT INTO assistance.admission(operation_id,account_id,intent_hash,intent,"
            "disposition,period_id,policy_ref) VALUES(%s,%s,%s,'{}','open',%s,%s) RETURNING *",
            (uuid4(), owner.account_id, secrets.token_hex(32), period,
             Jsonb(POLICY.reference))).fetchone()
    return control.reserve(owner, row)


def test_the_complete_realm_uses_u2s_controls_for_every_usage_call(host):
    usage = usage_for(host.composition.transactions)
    assert isinstance(usage, CompleteUsage)
    assert usage.control.policy is POLICY
    research = host.composition.parts["research-workspace"]["execution"]
    assert isinstance(research.usage, CompleteUsage)


def test_research_novelty_and_assistance_count_together_within_a_period(
        host, sign_in_account, connect):
    owner = granted(host, sign_in_account, connect)
    usage = usage_for(host.composition.transactions)
    research = usage.reserve(owner, uuid4(), secrets.token_hex(32))
    novelty = usage.reserve(owner, uuid4(), secrets.token_hex(32))
    assistance = assistance_reserve(host, connect, owner)
    assert {research["operation_owner"], novelty["operation_owner"]} == {"ResearchWorkspace"}
    assert assistance["operation_owner"] == "PaperAssistance"
    assert {row["period_id"] for row in (research, novelty, assistance)} == {
        usage.control.current_period()}
    # The grant's quota of 3 is spent by the three kinds together.
    with pytest.raises(UsageQuotaExceeded):
        usage.reserve(owner, uuid4(), secrets.token_hex(32))
    # A new period allows them again: the period's reservations moved one period back.
    current = int(usage.control.current_period().split(":")[1])
    with admin(host) as conn, conn.transaction():
        conn.execute("UPDATE usage.reservation SET period_id=%s WHERE account_id=%s",
                     (f"u2-period:{current - 1}", owner.account_id))
    again = usage.reserve(owner, uuid4(), secrets.token_hex(32))
    assert again["period_id"] == f"u2-period:{current}"


def test_an_ungranted_accounts_refused_request_closes_with_nothing_to_release(
        host, sign_in_account, connect):
    owner = live(host, sign_in_account, connect, OTHER_MEMBER)
    clear_usage(host, owner.account_id)
    usage = usage_for(host.composition.transactions)
    operation = uuid4()
    with pytest.raises(UsageQuotaExceeded):
        usage.reserve(owner, operation, secrets.token_hex(32))
    # The refusal clean-up: nothing to release, no usage row written, no error.
    usage.reject_operation({"accountId": str(owner.account_id), "operationId": str(operation),
                            "intentHash": "a" * 64, "proofHash": "b" * 64})
    with admin(host) as conn:
        for table in ("reservation", "rejected_operation"):
            assert conn.execute(f"SELECT count(*) FROM usage.{table} WHERE account_id=%s",
                                (owner.account_id,)).fetchone()[0] == 0
    # The worker's next pass completes (no half fails on the closure).
    summaries = host.composition.worker.run_once(4)
    assert set(summaries) >= {"chained", "lifecycle"}


def test_an_earlier_realm_keeps_the_built_refusal_rule(host, sign_in_account, connect):
    from types import SimpleNamespace

    owner = live(host, sign_in_account, connect, OTHER_MEMBER)
    clear_usage(host, owner.account_id)
    # The same database, read as an earlier realm's repository: U1's rule refuses.
    earlier = SimpleNamespace(profile=SimpleNamespace(realm="research-workspace"),
                              run=host.composition.transactions.run)
    repository = GuardedUsageRepository(earlier)
    assert not isinstance(usage_for(earlier), CompleteUsage)
    with pytest.raises(ValueError, match="usage participant not initialized"):
        repository.reject_operation({"accountId": str(owner.account_id),
                                     "operationId": str(uuid4()), "intentHash": "a" * 64,
                                     "proofHash": "b" * 64})


def test_settlement_and_release_go_through_the_rows_the_records_show(
        host, sign_in_account, connect):
    owner = granted(host, sign_in_account, connect)
    usage = usage_for(host.composition.transactions)
    committed = usage.reserve(owner, uuid4(), secrets.token_hex(32))
    released = assistance_reserve(host, connect, owner)
    usage.settle(committed["id"], committed["operation_id"], disposition="committed",
                 proof_hash="c" * 64)
    usage.settle(released["id"], released["operation_id"], disposition="released",
                 proof_hash="d" * 64)
    records = call(host.client, "/api/v2/c03/usage-list-records", {"page": {"limit": 10}})
    assert records.status_code == 200, records.text
    shown = {item["usageRecordId"]: item for item in records.json()["items"]}
    assert str(committed["id"]) in shown and str(released["id"]) in shown
    # Each record names the owner its reservation was made for (your decision of
    # 2026-10-24, "Fix usage now, record ORCID"): research's is ResearchWorkspace.
    assert shown[str(committed["id"])]["operation"]["operationOwner"] == "ResearchWorkspace"
    assert shown[str(released["id"])]["operation"]["operationOwner"] == "PaperAssistance"
    with admin(host) as conn:
        dispositions = dict(conn.execute(
            "SELECT id,disposition FROM usage.reservation WHERE id = ANY(%s)",
            ([committed["id"], released["id"]],)).fetchall())
    assert dispositions == {committed["id"]: "committed", released["id"]: "released"}
