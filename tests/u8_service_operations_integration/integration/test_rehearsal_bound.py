"""The rehearsal bound (U8 plan Step 22; BR7.5, NFR2.2).

In rehearsal mode an outward effect reaches only the maintainer: mail to any other account
is held as not permitted and recorded, and so is a Notion operation through any other
connection. The maintainer's own pass. Each adapter reads the mode through the provider
gate before any effect: AccountAccess's account mail (a reset-required sign-in in the
composed realm, its answer recorded in the entry receipt), U5's digest adapter (the
account it compares found through AccountAccess) and U6's Notion session.

The gate and the maintainer's recipients are the adapters' ports; here they answer for
one maintainer account and one connection (ServiceOperations' activation implements them
in the assembly). Resend and Notion run over fake transports.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from uuid import UUID, uuid4

import httpx
import pytest

from backend.modules.accounts.integrations.account_mail import ResendAccountMail
from backend.modules.accounts.integrations.digest_email import RECIPIENT_NOT_PERMITTED
from backend.modules.accounts.integrations.u8_digest_mail import GatedResendDigestMail
from backend.modules.export import notion_session
from backend.modules.export.classification import (
    COULD_NOT_CHECK,
    PROTECTION_UNAVAILABLE,
    classify_write,
)
from backend.modules.export.lane import ExportLane
from backend.modules.export.notion_session import NotionSession, StoredConnection
from backend.modules.operations.allowance import LedgerAllowance
from backend.modules.operations.ledger import Ledger
from backend.u6_policy import SYNTHETIC_EXPORT
from backend.u8_policy import SYNTHETIC_OPERATIONS
from tests.u6_approved_export import lane_flows as lf
from tests.u8_service_operations_integration.conftest import SIGN_IN_PASSWORD

pytestmark = pytest.mark.usefixtures("own_address")
ORIGIN = "https://127.0.0.1:18110"
UNSUBSCRIBE = ORIGIN + "/api/v2/topics/email-unsubscribe/" + "A" * 43
PRESENTATION = {
    "subject": "주간 논문 요약", "text": "요약", "html": "<html><body>요약</body></html>",
}


class RehearsalGate:
    mode = "rehearsal"

    def state(self, provider):
        return "active"


class Maintainer:
    """The maintainer's account and Notion connection."""

    def __init__(self, account: UUID, connection: UUID | None = None):
        self.account, self.connection = account, connection

    def is_maintainer_account(self, account_id):
        return account_id == self.account

    def is_maintainer_connection(self, connection_id):
        return connection_id == self.connection


class Resend:
    def __init__(self):
        self.posts = []

    def __call__(self, **options):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, endpoint, *, headers, json):
        self.posts.append(json)
        return httpx.Response(200, json={"id": str(uuid4())})


@pytest.fixture
def operations_ledger(tmp_path, clock):
    folder = tmp_path / "operations-ledger"
    folder.mkdir(mode=0o700)
    value = Ledger.open(folder, clock=clock)
    yield value
    value.close()


# Account mail ------------------------------------------------------------------------------


def test_account_mail_to_any_account_but_the_maintainers_is_held_and_recorded(
    connect, d1_entry, sign_in_account, operations_ledger,
):
    maintainer, maintainer_email = sign_in_account("sign-in-admin", role="administrator",
                                                   reset_required=True)
    other, other_email = sign_in_account("sign-in-migrated", consents=False,
                                         reset_required=True)
    resend = Resend()
    d1_entry.account_mail = ResendAccountMail(
        api_key="re_" + uuid4().hex,  # generated per run (L1-36)
        sender="DocSuri <mail@fixture.example.com>",
        origin=ORIGIN, allowance=LedgerAllowance(operations_ledger, SYNTHETIC_OPERATIONS),
        gate=RehearsalGate(), recipients=Maintainer(maintainer.account_id),
        client_factory=resend,
    )
    operation = uuid4()
    held = d1_entry.login(other_email, SIGN_IN_PASSWORD, operation=operation,
                          flow_binding="rehearsal").public
    assert (held["state"], held["delivery"]) == ("reset_required", "held")
    assert resend.posts == []
    with connect("accounts") as conn:  # recorded: the sign-in's own receipt says so
        recorded = conn.execute("SELECT outcome FROM accounts.entry_receipt WHERE "
                                "operation_id=%s", (operation,)).fetchone()["outcome"]
    assert recorded == held
    passed = d1_entry.login(maintainer_email, SIGN_IN_PASSWORD, flow_binding="rehearsal").public
    assert passed["delivery"] == "accepted"
    assert [post["to"] for post in resend.posts] == [[maintainer_email]]
    assert other.account_id != maintainer.account_id


# Digests -------------------------------------------------------------------------------------


def digest_adapter(entry, recipients, permitted: str, resend) -> GatedResendDigestMail:
    return GatedResendDigestMail(
        api_key="re_" + uuid4().hex,  # generated per run (L1-36)
        sender="digest@fixture.example.com", unsubscribe_url=ORIGIN,
        permitted_recipient=permitted, client_factory=resend,
        gate=RehearsalGate(), recipients=recipients, account_of=entry.account_of,
    )


def test_a_digest_to_any_account_but_the_maintainers_is_held_as_not_permitted(
    d1_entry, sign_in_account,
):
    maintainer, maintainer_email = sign_in_account("sign-in-admin", role="administrator")
    _, member_email = sign_in_account("sign-in-member")
    recipients = Maintainer(maintainer.account_id)
    resend = Resend()
    # U5's own single-recipient bound would let this address through; rehearsal holds it.
    refused = asyncio.run(digest_adapter(d1_entry, recipients, member_email, resend).send(
        member_email, PRESENTATION, uuid4(), unsubscribe_url=UNSUBSCRIBE))
    assert (refused.state, refused.refusal_reason) == ("refused", RECIPIENT_NOT_PERMITTED)
    unknown = "nobody-" + uuid4().hex[:12] + "@fixture.example.com"
    assert asyncio.run(digest_adapter(d1_entry, recipients, unknown, resend).send(
        unknown, PRESENTATION, uuid4(), unsubscribe_url=UNSUBSCRIBE)).state == "refused"
    assert resend.posts == []
    accepted = asyncio.run(digest_adapter(d1_entry, recipients, maintainer_email, resend).send(
        maintainer_email, PRESENTATION, uuid4(), unsubscribe_url=UNSUBSCRIBE))
    assert accepted.state == "accepted" and len(resend.posts) == 1


# Notion -------------------------------------------------------------------------------------


class Store:
    def __init__(self):
        self.opened = []

    def reserve_pace_slot(self, connection_id, *, remaining_seconds):
        return SimpleNamespace(wait_seconds=0.0, within_budget=True)

    def open_token_envelope(self, account_id, connection_id):
        self.opened.append(connection_id)
        # Generated per run (L1-36), as is the token the vault opens.
        return {"revision": 1, "state": "active", "sealed_token": uuid4().bytes}


class Vault:
    def open(self, envelope, *, account_id, connection_id, revision):
        return "notion-" + uuid4().hex


@pytest.fixture
def gate_installed(monkeypatch):
    def install(gate, recipients):
        monkeypatch.setattr(notion_session, "_INSTALLED_GATE",
                            {"gate": gate, "recipients": recipients})

    return install


def operate(session, target):
    async def work(sdk, context):
        return "reached"

    return asyncio.run(session.run(target, 5.0, work))


def test_a_notion_operation_through_any_connection_but_the_maintainers_is_held(
    gate_installed,
):
    owner, maintainer_connection, other_connection = uuid4(), uuid4(), uuid4()
    gate_installed(RehearsalGate(), Maintainer(owner, maintainer_connection))
    store, built = Store(), []

    def transport():
        built.append(1)
        return httpx.MockTransport(lambda request: httpx.Response(200, json={}))

    session = NotionSession(store=store, vault=Vault(), policy=SYNTHETIC_EXPORT,
                            transport_factory=transport)
    held = operate(session, StoredConnection(account_id=uuid4(), connection_id=other_connection))
    assert (held.ok, held.cause) == (False, notion_session.CAUSE_NOT_PERMITTED)
    assert store.opened == [] and built == []  # no token opened, no client built
    passed = operate(session, StoredConnection(account_id=owner,
                                               connection_id=maintainer_connection))
    assert passed.ok and passed.value == "reached" and store.opened == [maintainer_connection]
    # A provider that is not active holds every operation, the maintainer's included.
    gate_installed(SimpleNamespace(mode="live", state=lambda provider: "held"),
                   Maintainer(owner, maintainer_connection))
    assert operate(session, StoredConnection(account_id=owner,
                                             connection_id=maintainer_connection)).cause == (
        notion_session.CAUSE_PROVIDER_HELD)


class HoldAfterClaim:
    """The real export store, with the provider gate installed just after the lane's
    claim: the pre-write checks passed, and the hold arrives before the create leaves."""

    def __init__(self, repository, hold):
        self._repository, self._hold = repository, hold

    def claim(self, *args, **kwargs):
        claimed = self._repository.claim(*args, **kwargs)
        self._hold()
        return claimed

    def __getattr__(self, name):
        return getattr(self._repository, name)


@pytest.mark.parametrize("cause", [notion_session.CAUSE_PROVIDER_HELD,
                                   notion_session.CAUSE_NOT_PERMITTED])
def test_a_write_held_after_its_claim_is_never_sent_and_never_may_exist(
    transactions, connect, authority, tmp_path, gate_installed, cause,
):
    """The review's case (U6 re-check, Major): the gate holds the one write after its
    claim. Nothing is sent, the attempt is recorded refused before sending, and the effect
    ends failed, never `unknown` with a page that may exist."""
    lr = lf.build(transactions, connect, authority, tmp_path)
    flow = lf.pressed(lr)
    if cause == notion_session.CAUSE_PROVIDER_HELD:
        gate = SimpleNamespace(mode="live", state=lambda provider: "held")
    else:
        gate = RehearsalGate()  # the maintainer's connection is another one
    lane = ExportLane(
        HoldAfterClaim(lr.repo, lambda: gate_installed(gate, Maintainer(uuid4(), uuid4()))),
        lr.rig.service.adapter, lr.rig.service.binding, policy=lr.rig.policy, clock=lr.clock,
    )
    assert lane.run_item(lf.item(flow["effect"])) == "failed"
    row = lf.row(connect, flow["effect"])
    assert (row["state"], row["outcome_reason"]) == ("failed", "policy-unresolved")
    [attempt] = lf.attempts(connect, flow["effect"])
    assert attempt["response_class"] == "refused" and attempt["ended_at"] is not None
    assert attempt["provider_request_id"] is None
    assert lr.fake.writes == [] and lf.checks(connect, flow["effect"]) == []
    # The session's own answers: the write never left, a read waits; both name the hold.
    target = StoredConnection(account_id=authority.account_id, connection_id=uuid4())

    async def work(sdk, context):
        raise AssertionError("a held operation runs no work")

    store = Store()
    session = NotionSession(store=store, vault=Vault(), policy=SYNTHETIC_EXPORT)
    written = asyncio.run(session.run(target, 5.0, work, classify=classify_write))
    read = asyncio.run(session.run(target, 5.0, work))
    assert (written.category, written.cause) == (PROTECTION_UNAVAILABLE, cause)
    assert (read.category, read.cause) == (COULD_NOT_CHECK, cause)
    assert store.opened == []  # no token opened for either


def test_with_no_gate_installed_the_session_is_u6s(gate_installed):
    notion_session.install_provider_gate(None, None)
    assert notion_session.provider_hold(StoredConnection(account_id=uuid4(),
                                                         connection_id=uuid4())) is None
