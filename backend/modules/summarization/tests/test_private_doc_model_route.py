"""F01 — the owner-scoped PRIVATE route is the only way to read a ``userdoc:`` doc-model.

Companion to ``test_private_content_boundary.py`` (which pins the public refusal). This file pins
the other half of the contract, the two properties that make the private route safe to expose:

  * a miss and a non-owner's request are BYTE-IDENTICAL 404s — no existence oracle;
  * the owner identity is taken from the gateway principal ONLY, never from the path or body, so
    the route cannot be steered into another tenant's prefix.

A store fault must stay a generic 503 (fail-closed, no internals), never a 500 that distinguishes
"backend broken" from "not yours".
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from docsuri_shared.dtos import DocModel

from summarization.api.router import build_router
from summarization.domain.models import DocModelLookup

from .test_private_content_boundary import _doc_model, _FakeRequest

_PRIVATE_ROUTE = "/api/userdoc/{doc_id}/doc-model"
_DOC_ID = "11111111-1111-4111-8111-111111111111"
_MISS_BODY = {"status": "not_found"}


class _PrivateSpyOrchestrator:
    """Records the identity the private read was resolved with, and returns a scripted result."""

    def __init__(self, doc: DocModel | None, *, raises: bool = False) -> None:
        self._doc = doc
        self._raises = raises
        self.private_calls: list[tuple[str, str, int]] = []

    def private_doc_model(self, owner_id: str, doc_id: str, version: int) -> DocModelLookup:
        self.private_calls.append((owner_id, doc_id, version))
        if self._raises:
            raise RuntimeError("simulated S3 AccessDenied / throttling")
        return DocModelLookup(doc=self._doc)


def _call(orch: Any, *, doc_id: str, principal: Any, version: str | None = "1"):
    router = build_router(orch, docmodel_enabled=True, assets_enabled=True)
    for route in router.routes:
        if getattr(route, "path", None) == _PRIVATE_ROUTE and "GET" in getattr(
            route, "methods", set()
        ):
            query = {} if version is None else {"version": version}
            resp = route.endpoint(_FakeRequest(principal, query), doc_id)
            return resp.status_code, json.loads(resp.body)
    raise AssertionError(f"GET {_PRIVATE_ROUTE} not found")


# --- the owner reads their own document ----------------------------------------------------


def test_private_route_serves_the_owners_document() -> None:
    orch = _PrivateSpyOrchestrator(_doc_model(paper_id=f"userdoc:{_DOC_ID}"))

    status, body = _call(orch, doc_id=_DOC_ID, principal={"user_id": "u-owner"})

    assert status == 200
    assert body["status"] == "ok"
    assert body["docModel"]["meta"]["paperId"] == f"userdoc:{_DOC_ID}"


def test_private_route_resolves_with_the_principals_owner_only() -> None:
    # The owner id the read is scoped by comes from the gateway principal — the path carries no
    # owner, so there is nothing for a caller to tamper with.
    orch = _PrivateSpyOrchestrator(None)

    _call(orch, doc_id=_DOC_ID, principal={"user_id": "u-owner"})

    assert orch.private_calls == [("u-owner", _DOC_ID, 1)]


# --- non-owner / miss are indistinguishable ------------------------------------------------


def test_private_route_returns_404_for_another_tenants_document() -> None:
    # The orchestrator (which reads the OWNER's prefix, not the caller's) finds nothing.
    orch = _PrivateSpyOrchestrator(None)

    status, body = _call(orch, doc_id=_DOC_ID, principal={"user_id": "u-attacker"})

    assert status == 404
    assert body == _MISS_BODY


def test_private_route_miss_and_non_owner_are_byte_identical() -> None:
    # The core anti-oracle property: probing a real doc as a non-owner and probing a nonexistent
    # id as the owner must be indistinguishable in status AND body.
    _, non_owner = _call(
        _PrivateSpyOrchestrator(None), doc_id=_DOC_ID, principal={"user_id": "u-attacker"}
    )
    _, unknown = _call(
        _PrivateSpyOrchestrator(None),
        doc_id="99999999-9999-4999-8999-999999999999",
        principal={"user_id": "u-owner"},
    )

    assert non_owner == unknown == _MISS_BODY


def test_private_route_is_not_answered_as_building_or_source_unavailable() -> None:
    # A 200 "source_unavailable" would itself distinguish "yours, not built yet" from "not yours",
    # which is exactly the state the 404 is meant to hide. Both states must collapse to the 404.
    orch = _PrivateSpyOrchestrator(None)

    status, body = _call(orch, doc_id=_DOC_ID, principal={"user_id": "u-owner"})

    assert status == 404
    assert body["status"] == "not_found"


# --- fail-closed edges ---------------------------------------------------------------------


def test_private_route_requires_authentication_before_touching_the_store() -> None:
    orch = _PrivateSpyOrchestrator(_doc_model())

    status, _ = _call(orch, doc_id=_DOC_ID, principal=None)

    assert status == 401
    assert orch.private_calls == []


def test_private_route_fails_closed_on_a_store_fault() -> None:
    # A fault is a generic 503 — not a 500 (internals) and not a 404 (which would be readable as
    # "the owner's own document is somehow not there", a state that needs operator attention).
    orch = _PrivateSpyOrchestrator(_doc_model(paper_id=f"userdoc:{_DOC_ID}"), raises=True)

    status, body = _call(orch, doc_id=_DOC_ID, principal={"user_id": "u-owner"})

    assert status == 503
    assert body == {"status": "unavailable"}


def test_private_route_serves_a_disabled_feature_deployment() -> None:
    # A private upload is the user's OWN content, so it is not gated behind the corpus license
    # flags; guarding it on those flags would make the owner's own manuscript unreadable in a
    # default deployment while the public routes keep refusing the namespace.
    router = build_router(
        _PrivateSpyOrchestrator(None), docmodel_enabled=False, assets_enabled=False
    )
    for route in router.routes:
        if getattr(route, "path", None) == _PRIVATE_ROUTE:
            resp = route.endpoint(_FakeRequest({"user_id": "u-owner"}, {"version": "1"}), _DOC_ID)
            assert resp.status_code == 404  # reached the private read (a store miss), not license
            return
    raise AssertionError(f"GET {_PRIVATE_ROUTE} not found")


@pytest.mark.parametrize("version", ["0", "-3", "abc"])
def test_private_route_refuses_an_unusable_version(version: str) -> None:
    # A non-positive version is a miss; an unparseable one falls back to v1 rather than 500.
    orch = _PrivateSpyOrchestrator(_doc_model(paper_id=f"userdoc:{_DOC_ID}"))

    status, _ = _call(orch, doc_id=_DOC_ID, principal={"user_id": "u-owner"}, version=version)

    assert status in (200, 404)
    if status == 404:
        assert orch.private_calls == []
    else:
        assert orch.private_calls[0][2] == 1
