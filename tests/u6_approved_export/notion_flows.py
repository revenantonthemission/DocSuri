"""Shared flows for the Notion-boundary tests: the real SDK over the fake Notion.

Every token here is a synthetic string the fake alone accepts. Policies are smaller
than production (a 1 ms pace, short budgets), so no test waits in real time; only the
pace test keeps the real 500 ms. The store is the real `ExportRepository` over the
realm; the token keyring lives in the test's own temporary folder, with a stub witness
that reports no sealed tokens (the key-decision table's first-start row).
"""

import datetime as dt
from uuid import uuid4

from backend.modules.export.fake_notion import FakeNotion
from backend.modules.export.notion_adapter import NotionAdapter, StoreContentPort, WriteRequest
from backend.modules.export.notion_session import (
    CandidateToken,
    InteractiveGate,
    NotionSession,
    StoredConnection,
)
from backend.modules.export.rendering import content_hash, marker_for, project_text
from backend.modules.export.repository import ExportRepository, RenderedRevision, SealedToken
from backend.modules.export.store_support import canonical_digest
from backend.modules.export.token_keyring import TokenKeyring
from backend.modules.export.token_vault import TokenVault
from backend.u6_policy import ExportPolicy

from tests.u6_approved_export import store_flows as flows

WORKSPACE_ID = "0b7d2a51c4e94f36a8e1d2c3b4a59687"
WORKSPACE_NAME = "Synthetic Workspace"


def policy(**overrides) -> ExportPolicy:
    values = {"pace_interval_ms": 1, **overrides}
    return ExportPolicy(**values)


def synthetic_token() -> str:
    return "synthetic-notion-token-" + uuid4().hex


def bot_id() -> str:
    return uuid4().hex


class NoSealedTokens:
    """The key-decision witness for a test keyring: no sealed token exists (first start)."""

    def token_key_counts(self):
        return []


def vault(tmp_path) -> TokenVault:
    root = tmp_path / "export-keys"
    root.mkdir(mode=0o700)
    return TokenVault(TokenKeyring(root, "u6-notion-test", NoSealedTokens()))


def repository(transactions, chosen: ExportPolicy) -> ExportRepository:
    return ExportRepository(transactions, chosen)


def fake_with(token: str, bot: str, *, clock=None) -> FakeNotion:
    fake = FakeNotion(clock=clock)
    fake.add_token(token, bot_id=bot, workspace_id=WORKSPACE_ID, workspace_name=WORKSPACE_NAME)
    return fake


def session(repo, opener, fake, chosen, *, gate=None) -> NotionSession:
    return NotionSession(
        store=repo,
        vault=opener,
        policy=chosen,
        gate=gate or InteractiveGate.for_policy(chosen),
        transport_factory=lambda: fake,
    )


def adapter(repo, opener, fake, chosen, *, gate=None, clock=None) -> NotionAdapter:
    kwargs = {"clock": clock} if clock is not None else {}
    return NotionAdapter(
        session(repo, opener, fake, chosen, gate=gate),
        repo,
        content=StoreContentPort(repo),
        **kwargs,
    )


def now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def seal_and_store(repo, authority, opener, token, slot, *, user, at=None):
    """Seal `token` for the revision the store is about to create, and store it."""
    at = at or now()
    envelope, version = opener.seal(
        token,
        account_id=authority.account_id,
        connection_id=slot.connection_id,
        revision=slot.next_revision,
    )
    sealed = SealedToken(envelope, version, WORKSPACE_NAME, WORKSPACE_ID, user, at)
    request = flows.configure_request(slot.expected_revision or None, token)
    return repo.store_configured(authority, slot, sealed, flows.replay_for(request), now=at)


def stored_connection(repo, connect, authority, opener, token, *, user):
    """A fresh owner whose connection holds `token` sealed; returns the target and row."""
    flows.fresh(connect, authority.account_id)
    slot = repo.reserve_connection(authority, None, now=now())
    seal_and_store(repo, authority, opener, token, slot, user=user)
    return StoredConnection(authority.account_id, slot.connection_id), repo.read_connection(
        authority
    )


def replace_token(repo, authority, opener, token, *, user) -> dict:
    """Replace the owner's token at its current revision (BR1.3)."""
    current = repo.read_connection(authority)
    slot = repo.reserve_connection(authority, current["revision"], now=now())
    seal_and_store(repo, authority, opener, token, slot, user=user)
    return repo.read_connection(authority)


def pending_candidate(repo, connect, authority, token):
    """A first configure: the pending row and its pace row, and the candidate target."""
    flows.fresh(connect, authority.account_id)
    slot = repo.reserve_connection(authority, None, now=now())
    return CandidateToken(slot.connection_id, token), slot


def page_body(marker: str, *, text: str = "요약: 합성 결과입니다.") -> dict:
    def paragraph(content: str) -> dict:
        return {
            "object": "block",
            "type": "paragraph",
            "paragraph": {"rich_text": [{"type": "text", "text": {"content": content}}]},
        }

    return {
        "properties": {"title": [{"type": "text", "text": {"content": "신규성 분석 — 합성"}}]},
        "children": [paragraph(text), paragraph(marker)],
    }


def _render(preview_id, revision) -> RenderedRevision:
    marker = marker_for(preview_id, revision)
    body = page_body(marker)
    return RenderedRevision(
        marker=marker,
        rendered_blocks=body,
        rendered_text=project_text(body),
        rendered_content_hash=content_hash(body),
        binding_hash=canonical_digest({"preview": str(preview_id), "revision": revision}),
    )


def bound_effect(repo, authority, connection, destination: str) -> dict:
    """A preview revision with a real page body, its approval and its accepted effect."""
    at = now()
    preview = repo.add_preview_revision(
        authority, flows.facts(connection, destination=destination), _render, now=at
    )
    approval = flows.approve(repo, authority, preview, at)
    effect = repo.bind_effect(authority, approval["id"], uuid4(), now=at)["effect"]
    return {"preview": preview, "approval": approval, "effect": effect}


def write_request(bound: dict, connection: dict, writer: str, **overrides) -> WriteRequest:
    effect = bound["effect"]
    values = {
        "effect_id": effect["id"],
        "approval_id": bound["approval"]["id"],
        "connection_id": connection["id"],
        "destination_id": effect["destination_id"],
        "artifact": {
            "resultId": str(effect["artifact_id"]),
            "revision": "1",
            "contentHash": "0" * 64,
            "mediaType": "application/json",
        },
        "preview_hash": effect["binding_hash"],
        "writer_identity": writer,
    }
    return WriteRequest(**{**values, **overrides})
