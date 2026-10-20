"""Mounted C09 routes over the realm, as U5's `test_http.py` mounts its own: the real
export router behind the shared browser boundary, real session verification through
`GuardedEntryService`, and the real `ExportService` over the fake Notion.

Each owner gets a browser session of the conftest's two synthetic accounts (no account
is ever added), with its cookie, Origin and CSRF header; every POST carries its own
Idempotency-Key. Every token is a synthetic string only the fake accepts.
"""

import secrets
from dataclasses import dataclass
from uuid import uuid4

from backend.modules.accounts.services.guarded_entry import GuardedEntryService
from backend.modules.export.http import ERROR_STATUS, PREFIX, export_router
from backend.transactions import Authority
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.u6_approved_export import service_flows as sf
from tests.u6_approved_export import store_flows as flows

# The route of each service operation, so a refusal can be checked against its own list.
ROUTE = {
    "configure": "configure-notion-connection",
    "read_connection": "read-notion-connection",
    "disconnect": "disconnect-notion",
    "list_destinations": "list-export-destinations",
    "prepare_preview": "prepare-export-preview",
    "approve": "approve-export-preview",
    "execute": "execute-approved-export",
    "read_effect": "read-export-effect",
    "cancel": "cancel-export-approval",
    "history": "list-export-history",
    "settle": "settle-export-effect",
}
# The shared boundary's own answers, which every operation's list carries.
BOUNDARY_STATUS = {"NOT_FOUND": 404, "INVALID_ARGUMENT": 422, "UNAUTHENTICATED": 401}


@dataclass(frozen=True)
class BrowserSession:
    token: str
    csrf: str
    authority: Authority


def browser_session(transactions, entry, account_id) -> BrowserSession:
    """A current session of an existing conftest account, verifiable by the entry."""
    token = secrets.token_hex(32)
    csrf = entry.verifier("session-csrf", token)
    session = uuid4()

    def seed(conn):
        revision = conn.execute(
            "SELECT authority_revision FROM accounts.account WHERE id=%s", (account_id,)
        ).fetchone()["authority_revision"]
        conn.execute(
            "INSERT INTO accounts.session(id,account_id,token_hash,csrf_hash,"
            "authority_revision,expires_at) VALUES(%s,%s,%s,%s,%s,"
            "clock_timestamp()+interval '30 minutes')",
            (
                session,
                account_id,
                entry.verifier("session", token),
                entry.verifier("csrf", csrf),
                revision,
            ),
        )

    transactions.run("accounts", seed)
    return BrowserSession(token, csrf, Authority(account_id, session))


def browser(app, realm, session: BrowserSession | None) -> TestClient:
    client = TestClient(app, base_url=realm.origin)
    client.headers.update({"Origin": realm.origin})
    if session is not None:
        client.cookies.set("session_id", session.token)
        client.headers.update({"X-CSRF-Token": session.csrf})
    return client


@dataclass
class Mounted:
    rig: sf.Rig
    app: FastAPI
    realm: object
    entry: GuardedEntryService
    own: BrowserSession
    other_session: BrowserSession
    client: TestClient
    other: TestClient

    @property
    def authority(self) -> Authority:
        return self.own.authority

    @property
    def other_authority(self) -> Authority:
        return self.other_session.authority

    def browser(self, session: BrowserSession | None) -> TestClient:
        """Another browser for the same app (one per thread in concurrency tests)."""
        return browser(self.app, self.realm, session)

    def post(self, operation: str, body: dict, *, key=None, client=None):
        return (client or self.client).post(
            PREFIX + ROUTE[operation],
            json=body,
            headers={"Idempotency-Key": str(key or uuid4())},
        )

    def ok(self, operation: str, body: dict, *, key=None, client=None) -> dict:
        response = self.post(operation, body, key=key, client=client)
        assert response.status_code == 200, (operation, response.status_code, response.json())
        return response.json()

    def refused(self, operation: str, body: dict, *, key=None, client=None) -> str:
        """The refusal's code: its status is the router's mapping, and the code lies in
        the operation's own frozen list."""
        response = self.post(operation, body, key=key, client=client)
        code = response.json()["code"]
        assert code in sf.OPERATION_ERRORS[operation], (operation, code)
        expected = ERROR_STATUS.get(code, BOUNDARY_STATUS.get(code))
        assert response.status_code == expected, (operation, code, response.status_code)
        return code

    def configure_body(self, token: str | None = None, expected=None) -> dict:
        return {
            "token": token or self.rig.token,
            "expectedRevision": None if expected is None else str(expected),
            "credentialPolicy": self.rig.policy.reference(),
        }

    def connect_owner(self, *, client=None, token: str | None = None) -> dict:
        return self.ok("configure", self.configure_body(token), client=client)

    def close(self) -> None:
        self.client.close()
        self.other.close()

    def __enter__(self) -> "Mounted":
        return self

    def __exit__(self, *_exc) -> None:
        self.close()


def mount(realm, transactions, connect, authority, authority_b, tmp_path, **options) -> Mounted:
    """The export router over a fresh rig for owner A, with a browser for A and for B.

    Both owners start from `store_flows.fresh()`; B shares A's service, gate and fake.
    """
    entry = GuardedEntryService(transactions)
    own = browser_session(transactions, entry, authority.account_id)
    other = browser_session(transactions, entry, authority_b.account_id)
    rig = sf.build(transactions, connect, own.authority, tmp_path, **options)
    flows.fresh(connect, other.authority.account_id)
    app = FastAPI()
    app.include_router(export_router(transactions, entry=entry, service=rig.service))
    return Mounted(
        rig,
        app,
        realm,
        entry,
        own,
        other,
        browser(app, realm, own),
        browser(app, realm, other),
    )


def press(mounted: Mounted, page: str, *, source: dict | None = None, client=None) -> dict:
    """One press through the routes: preview, then approve and execute with one key."""
    preview = mounted.ok(
        "prepare_preview", mounted.rig.preview_value(page, source), client=client
    )
    key = uuid4()
    approval = mounted.ok(
        "approve", mounted.rig.approval_value(preview), key=key, client=client
    )
    body = {"approvalId": approval["approvalId"], "bindingHash": approval["bindingHash"]}
    effect = mounted.ok("execute", body, key=key, client=client)
    return {"preview": preview, "approval": approval, "effect": effect, "key": key}
