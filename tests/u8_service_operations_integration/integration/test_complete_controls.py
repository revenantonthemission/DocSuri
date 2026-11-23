"""U2's controls in the complete app (U8 plan Step 24; the person's decisions of 2026-10-23,
"Route through U2's controls" and "Grant migrated accounts").

In the composed and production realms the eight checks of the plan's row "U2's controls
in the complete app" take U2's control path with the realm's own policy, through the
complete host:

1. the five usage administration routes answer for the administrator, and the three that
   act on another account refuse an owner;
2. the five personal-control routes answer for their owner;
3. the library routes apply U2's control service (its page shape and policy);
4. an assistance admission reserves usage through the same control service the usage
   records show;
5. after an erasure, the erased operation cannot reopen an assistance admission;
6. the policy in force is the composed realm's own, a production profile selects
   `PRODUCTION_POLICY`, and `SYNTHETIC_POLICY` reaches neither;
7. an account without a grant is refused paper assistance until an administrator grants
   it, and the database accepts a grant under each complete realm's policy.
"""

from __future__ import annotations

import secrets
from types import SimpleNamespace
from uuid import uuid4

import pytest
from psycopg.types.json import Jsonb

from backend.modules.accounts.control_policy import SYNTHETIC_POLICY, for_realm
from backend.modules.accounts.u8_control_policy import PRODUCTION_POLICY, U8_SYNTHETIC_POLICY
from backend.modules.plans.control_service import ControlUsageService
from backend.modules.plans.guarded_repository import GuardedUsageRepository, UsageQuotaExceeded
from backend.modules.plans.u8_usage import ImportedUsage
from backend.modules.summarization.admission import AssistanceAdmission
from backend.modules.summarization.guarded_repository import GuardedAssistanceRepository
from backend.transactions import Authority
from tests.u8_service_operations_integration import recovery_flows as rf
from tests.u8_service_operations_integration.conftest import SIGN_IN_PASSWORD
from tests.u8_service_operations_integration.host_flows import (
    MEMBER,
    OTHER_MEMBER,
    call,
    complete_host,
    fresh_client,
    member,
    session_of,
)
from tests.u8_service_operations_integration.host_flows import (
    administrator as admin_sign_in,
)

pytestmark = pytest.mark.usefixtures("own_address")
POLICY = U8_SYNTHETIC_POLICY.reference


@pytest.fixture
def host(realm, own_address):
    with complete_host(realm, address=own_address) as value:
        yield value


def c03(client, name: str, body: dict):
    return call(client, f"/api/v2/c03/{name}", body)


def clear_usage(host, account_id) -> None:
    """A reused account's usage back to none: its ledger rows, then its entitlement, as
    the realm's database administrator (the owner's login never deletes a ledger row)."""
    realm = host.composition.profile
    with rf.admin(realm, realm.database_name) as conn, conn.transaction():
        for table in ("rejected_operation", "reservation", "entitlement"):
            conn.execute(f"DELETE FROM usage.{table} WHERE account_id=%s", (account_id,))


# --- 1. usage administration ---------------------------------------------------------------


def test_the_usage_administration_routes_answer_the_administrator_and_refuse_an_owner(
        host, sign_in_account, connect):
    owner, _ = sign_in_account(OTHER_MEMBER)
    clear_usage(host, owner.account_id)
    admin_sign_in(host, sign_in_account, connect)
    target = {"accountId": str(owner.account_id)}
    read = c03(host.client, "usage-read-assignment", target)
    assert read.status_code == 200, read.text
    assert read.json()["entitlement"] is None
    granted = c03(host.client, "usage-grant-entitlement", dict(
        target, tierId="synthetic-free", reasonKey="u8-complete-controls",
        expectedRevision=read.json()["revision"], policyRef=POLICY))
    assert granted.status_code == 200, granted.text
    assert granted.json()["policyRef"] == POLICY and granted.json()["disposition"] == "active"
    again = c03(host.client, "usage-read-assignment", target).json()
    revoked = c03(host.client, "usage-revoke-entitlement", dict(
        target, entitlementId=str(owner.account_id), reasonKey="u8-complete-controls",
        expectedRevision=again["revision"], policyRef=POLICY))
    assert revoked.status_code == 200, revoked.text
    assert revoked.json()["disposition"] == "revoked"
    records = c03(host.client, "usage-list-records", {"page": {"limit": 5}})
    assert records.status_code == 200, records.text
    assert records.json()["policyRef"] == POLICY
    plan = c03(host.client, "usage-read-plan", {})
    assert plan.status_code == 200, plan.text
    assert plan.json()["policyRef"] == POLICY
    # An owner never acts on another account's assignment.
    with fresh_client(host) as other:
        member(SimpleNamespace(client=other), sign_in_account, MEMBER)
        for name, body in (
            ("usage-read-assignment", target),
            ("usage-grant-entitlement", dict(target, tierId="synthetic-free",
                                             reasonKey="x", expectedRevision=again["revision"],
                                             policyRef=POLICY)),
            ("usage-revoke-entitlement", dict(target, entitlementId=str(owner.account_id),
                                              reasonKey="x", expectedRevision=again["revision"],
                                              policyRef=POLICY)),
        ):
            assert c03(other, name, body).status_code in (403, 404), name


# --- 2. personal controls ----------------------------------------------------------------------


def test_the_personal_control_routes_answer_for_their_owner(host, sign_in_account, connect):
    owner, _ = member(host, sign_in_account, MEMBER)
    suggestions = c03(host.client, "settings-list-suggestions", {"page": {"limit": 1}})
    assert suggestions.status_code == 200, suggestions.text
    # U2's rule: recent papers are personalized activity, refused like a missing resource
    # while the owner's personalization consent is declined, and read once it is given.
    declined = c03(host.client, "settings-list-recent-papers", {"page": {"limit": 2}})
    assert declined.status_code == 404, declined.text
    with connect("accounts") as conn:
        conn.execute("UPDATE accounts.consent SET granted=true WHERE account_id=%s AND "
                     "purpose='personalization'", (owner.account_id,))
    recent = c03(host.client, "settings-list-recent-papers", {"page": {"limit": 2}})
    assert recent.status_code == 200, recent.text
    settings = c03(host.client, "settings-read", {}).json()
    prepared = c03(host.client, "settings-prepare-reset", {
        "action": "delete_behavior", "currentProof": SIGN_IN_PASSWORD,
        "expectedRevision": settings["revision"], "policyRef": POLICY})
    assert prepared.status_code == 200, prepared.text
    accepted = c03(host.client, "settings-reset", {
        "action": "delete_behavior", "confirmationRef": prepared.json()["confirmationRef"],
        "expectedRevision": settings["revision"], "policyRef": POLICY})
    assert accepted.status_code == 200, accepted.text
    listed = host.client.get("/api/v2/c03/settings-resets?view=history&limit=5")
    assert listed.status_code == 200, listed.text
    one = host.client.get("/api/v2/c03/settings-resets/" + accepted.json()["resetId"])
    assert one.status_code == 200, one.text


# --- 3. the library's control service --------------------------------------------------------


def test_the_library_routes_apply_the_control_service(host, sign_in_account):
    member(host, sign_in_account, MEMBER)
    for name in ("library-list-saved-papers", "library-list-saved-searches",
                 "library-list-history"):
        page = c03(host.client, name, {"page": {"limit": 2}})
        assert page.status_code == 200, (name, page.text)
        # U2's control service pages under the realm's own policy.
        assert page.json()["policyRef"] == POLICY, name
    # A write under another policy is refused before it reaches the library.
    refused = c03(host.client, "library-clear-history", {
        "expectedRevision": str(uuid4()),
        "policyRef": {"policyId": "synthetic-local-library", "revision": "1"}})
    assert refused.status_code >= 400


# --- 4, 5 and 7. paper assistance and usage ------------------------------------------------


class Accepting:
    """PaperAssistance's side of an admission, as its owner leaves the row before the
    usage reservation: the reservation goes through `AssistanceAdmission`'s realm path."""

    def __init__(self, row: dict):
        self.row, self.rejected = row, False

    def prepare(self, authority, operation, payload):
        return self.row

    def accept(self, authority, operation, reservation):
        return {"reservation": reservation}

    def reject_open(self, authority, operation):
        self.rejected = True


def live(host, sign_in_account, connect, suffix: str) -> Authority:
    """An owner signed in through the complete host: the authority of its live session
    (`sign_in_account` ends the fixture's own sessions first)."""
    with fresh_client(host) as client:
        owner, _ = member(SimpleNamespace(client=client), sign_in_account, suffix)
        return Authority(owner.account_id, session_of(connect, owner.account_id))


def open_admission(transactions, connect, authority) -> dict:
    """An open assistance admission of `authority` under the realm's policy and period."""
    usage = ControlUsageService(transactions, U8_SYNTHETIC_POLICY)
    period = transactions.run("usage", usage._period)
    with connect("assistance") as conn:
        return conn.execute(
            "INSERT INTO assistance.admission(operation_id,account_id,intent_hash,intent,"
            "disposition,period_id,policy_ref) VALUES(%s,%s,%s,'{}','open',%s,%s) RETURNING *",
            (uuid4(), authority.account_id, secrets.token_hex(32), period, Jsonb(POLICY)),
        ).fetchone()


def test_an_assistance_admission_reserves_usage_the_usage_records_show(
        host, sign_in_account, connect, transactions):
    signed, _ = member(host, sign_in_account, MEMBER)
    owner = Authority(signed.account_id, session_of(connect, signed.account_id))
    clear_usage(host, owner.account_id)
    usage = ImportedUsage(transactions, U8_SYNTHETIC_POLICY)
    assert usage.grant_imported(owner.account_id, source="realm_fixture")["disposition"] == (
        "imported")
    admission = open_admission(transactions, connect, owner)
    accepted = AssistanceAdmission(Accepting(admission), GuardedUsageRepository(transactions)
                                   ).accept(owner, admission["operation_id"], {})
    records = c03(host.client, "usage-list-records", {"page": {"limit": 10}})
    assert records.status_code == 200, records.text
    shown = {item["usageRecordId"] for item in records.json()["items"]}
    assert str(accepted["reservation"]) in shown
    with connect("usage") as conn:
        row = conn.execute("SELECT * FROM usage.reservation WHERE id=%s",
                           (accepted["reservation"],)).fetchone()
    assert row["policy_ref"] == POLICY and row["period_id"] == admission["period_id"]


def test_an_account_without_a_grant_is_refused_until_an_administrator_grants_it(
        host, sign_in_account, connect, transactions):
    owner = live(host, sign_in_account, connect, OTHER_MEMBER)
    clear_usage(host, owner.account_id)
    side = Accepting(open_admission(transactions, connect, owner))
    admission = AssistanceAdmission(side, GuardedUsageRepository(transactions))
    with pytest.raises(UsageQuotaExceeded):
        admission.accept(owner, side.row["operation_id"], {})
    assert side.rejected
    # The administrator grants it through the mounted route; then it is admitted.
    admin_sign_in(host, sign_in_account, connect)
    target = {"accountId": str(owner.account_id)}
    read = c03(host.client, "usage-read-assignment", target).json()
    assert c03(host.client, "usage-grant-entitlement", dict(
        target, tierId="synthetic-free", reasonKey="u8-complete-controls",
        expectedRevision=read["revision"], policyRef=POLICY)).status_code == 200
    fresh = Accepting(open_admission(transactions, connect, owner))
    assert AssistanceAdmission(fresh, GuardedUsageRepository(transactions)).accept(
        owner, fresh.row["operation_id"], {})["reservation"]


@pytest.mark.parametrize("policy", [U8_SYNTHETIC_POLICY, PRODUCTION_POLICY],
                         ids=lambda value: value.policy_id)
def test_the_database_accepts_a_grant_under_each_complete_realms_policy(
        host, realm, sign_in_account, policy):
    owner, _ = sign_in_account(OTHER_MEMBER)
    clear_usage(host, owner.account_id)
    with rf.admin(realm, realm.database_name) as conn, conn.transaction():
        conn.execute("INSERT INTO usage.entitlement(account_id,allocation,policy) "
                     "VALUES(%s,%s,%s)", (owner.account_id, policy.quota, policy.policy_id))
        stored = conn.execute("SELECT policy FROM usage.entitlement WHERE account_id=%s",
                              (owner.account_id,)).fetchone()
        assert (stored["policy"] if isinstance(stored, dict) else stored[0]) == policy.policy_id
        conn.execute("DELETE FROM usage.entitlement WHERE account_id=%s", (owner.account_id,))


def test_an_erased_operation_cannot_reopen_an_assistance_admission(
        host, realm, sign_in_account, connect, transactions):
    owner = live(host, sign_in_account, connect, MEMBER)
    token = secrets.token_hex(4)
    version = f"u8cc-{token}-v1"
    with connect("corpus") as conn:
        conn.execute("INSERT INTO corpus.paper(id,title,authors,metadata) "
                     "VALUES(%s,'Synthetic','[\"A\"]','{}')", (version + "-paper",))
        conn.execute(
            "INSERT INTO corpus.version(id,paper_id,source_url,source_hash,version_label,"
            "private_path,eligible,purpose,provenance,content) VALUES(%s,%s,"
            "'https://example.invalid/p',%s,'v1','synthetic',true,'local-research','{}','{}')",
            (version, version + "-paper", secrets.token_hex(32)))
    operation = uuid4()
    try:
        # As an erasure leaves it (`assistance.erase_private_controls`): the fence row.
        with rf.admin(realm, realm.database_name) as conn, conn.transaction():
            conn.execute(
                "INSERT INTO assistance.erased_admission(operation_id,account_id,intent_hash,"
                "generation,disposition,erased_by) VALUES(%s,%s,%s,1,'accepted',%s)",
                (operation, owner.account_id, secrets.token_hex(32), uuid4()))
        with pytest.raises(PermissionError, match="erased acceptance identity cannot reopen"):
            GuardedAssistanceRepository(
                transactions, host.composition.parts["paper-journey"]["assistance_files"]
            ).prepare(
                owner, operation, {"versionId": version, "action": "summary"})
    finally:
        with rf.admin(realm, realm.database_name) as conn, conn.transaction():
            conn.execute("DELETE FROM assistance.erased_admission WHERE operation_id=%s",
                         (operation,))
            conn.execute("DELETE FROM corpus.version WHERE id=%s", (version,))
            conn.execute("DELETE FROM corpus.paper WHERE id=%s", (version + "-paper",))


# --- 6. the policy in force ------------------------------------------------------------------


def test_the_policy_in_force_is_the_realms_own_and_never_the_synthetic_one(host, realm):
    assert for_realm(realm.realm) is U8_SYNTHETIC_POLICY
    assert for_realm("production") is PRODUCTION_POLICY
    assert for_realm("account-controls") is SYNTHETIC_POLICY
    assert for_realm("research-workspace") is None
    assert SYNTHETIC_POLICY not in (for_realm("service-operations"), for_realm("production"))
    entry = host.composition.parts["account-controls"]["entry"]
    assert entry.control_policy is U8_SYNTHETIC_POLICY
    # A control service under another realm's policy refuses this realm.
    from backend.modules.accounts.control_policy import PolicyUnavailable

    for other in (SYNTHETIC_POLICY, PRODUCTION_POLICY):
        with pytest.raises(PolicyUnavailable):
            ControlUsageService(host.composition.transactions, other)
