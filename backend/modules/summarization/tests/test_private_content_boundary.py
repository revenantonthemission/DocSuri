"""F01 — a private ``userdoc:`` document must never be served by a public corpus route.

REM-2 corrective, Phase 0/1 (SECURITY-08). Regression for the cross-tenant exposure: the
public read routes keyed directly on the caller-supplied ``paperId`` and read
``doc-model/{paperId}/v{N}.json`` from the SHARED corpus prefix, so any authenticated
session could read another tenant's uploaded-PDF doc-model by supplying their
``userdoc:{uuid}`` id. The owner binding that did exist lived only on the mint/poll side.

Contract encoded here (FD-Q1 / ID-Q1):
  * the public corpus routes reject the private namespace with an *indistinguishable* 404
    and never reach the orchestrator — no existence oracle, no cross-tenant read;
  * the corpus reader refuses to read a private id out of the corpus prefix;
  * a private read is owner-scoped: the owner's key resolves, a non-owner's does not;
  * corpus and private prefixes are disjoint, so IAM can isolate them.
"""

from __future__ import annotations

import io
import json
from typing import Any

from docsuri_shared.docmodel_contract import DOCMODEL_PARSER_VERSION, DOCMODEL_SCHEMA_VERSION
from docsuri_shared.dtos import DocModel

from summarization.adapters.s3_docmodel import S3DocModelReader
from summarization.api.router import build_router
from summarization.domain.models import AssetRef, DocModelLookup

# A private id minted for owner ``u-owner`` by the evidence/novelty upload flow. The value is
# arbitrary here — the whole point is that a session that is NOT the owner must not read it.
OTHER_TENANT_USERDOC = "userdoc:11111111-1111-4111-8111-111111111111"


# --- doubles (mirrors test_docmodel_endpoint.py: routes are invoked directly with a fake
# --- Request carrying state.principal + query_params, the gateway stand-in) ---------------


class _FakeState:
    def __init__(self, principal: Any) -> None:
        self.principal = principal


class _FakeQuery:
    def __init__(self, params: dict[str, str]) -> None:
        self._p = params

    def get(self, key: str, default: str | None = None) -> str | None:
        return self._p.get(key, default)


class _FakeRequest:
    def __init__(self, principal: Any, query: dict[str, str] | None = None) -> None:
        self.state = _FakeState(principal)
        self.headers: dict[str, str] = {}
        self.query_params = _FakeQuery(query or {})


def _doc_model(paper_id: str = "2401.00001", version: int = 1) -> DocModel:
    return DocModel.model_validate(
        {
            "meta": {
                "paperId": paper_id,
                "version": version,
                "title": "Private Manuscript",
                "provenance": {
                    "sourceTier": "pdf",
                    "parserVersion": DOCMODEL_PARSER_VERSION,
                    "schemaVersion": DOCMODEL_SCHEMA_VERSION,
                    "generatedAt": "2026-06-23T00:00:00Z",
                },
            },
            "fullText": "CONFIDENTIAL unpublished findings.",
            "sections": [
                {
                    "id": "s1",
                    "title": "Introduction",
                    "blocks": [{"id": "s1.p1", "type": "paragraph", "text": "CONFIDENTIAL."}],
                }
            ],
        }
    )


class _SpyOrchestrator:
    """Records every delegation so a test can assert the boundary rejected *before* the read."""

    def __init__(self, lookup: DocModelLookup | None = None, assets: list | None = None) -> None:
        self._lookup = lookup if lookup is not None else DocModelLookup()
        self._assets = assets
        self.doc_model_calls: list[tuple] = []
        self.asset_calls: list[tuple] = []

    def doc_model(self, paper_id: str, version: int) -> DocModelLookup:
        self.doc_model_calls.append((paper_id, version))
        return self._lookup

    def list_assets(self, paper_id: str, version: int) -> list[AssetRef] | None:
        self.asset_calls.append((paper_id, version))
        return self._assets


def _endpoint(orch: Any, path: str):
    router = build_router(orch, docmodel_enabled=True, assets_enabled=True)
    for route in router.routes:
        if getattr(route, "path", None) == path and "GET" in getattr(route, "methods", set()):
            return route.endpoint
    raise AssertionError(f"GET {path} not found")


def _call_doc_model(orch: Any, *, paper_id: str, principal: Any, version: str = "1"):
    endpoint = _endpoint(orch, "/api/papers/{paper_id}/doc-model")
    resp = endpoint(_FakeRequest(principal, {"version": version}), paper_id)
    return resp.status_code, json.loads(resp.body)


def _call_assets(orch: Any, *, paper_id: str, principal: Any, version: str = "1"):
    endpoint = _endpoint(orch, "/api/papers/{paper_id}/assets")
    resp = endpoint(_FakeRequest(principal, {"version": version}), paper_id)
    return resp.status_code, json.loads(resp.body)


class _FakeS3:
    def __init__(self, objects: dict[str, bytes]) -> None:
        self.objects = objects
        self.calls: list[str] = []

    def get_object(self, *, Bucket: str, Key: str) -> dict:  # noqa: N803 - boto3 casing
        self.calls.append(Key)
        if Key not in self.objects:
            from botocore.exceptions import ClientError

            raise ClientError({"Error": {"Code": "NoSuchKey"}}, "GetObject")
        return {"Body": io.BytesIO(self.objects[Key])}


# --- Phase 0.1 / Phase 1: the public corpus route must refuse the private namespace --------


def test_public_doc_model_route_rejects_private_id_before_any_read() -> None:
    # The orchestrator WOULD return another tenant's doc-model — the read must never happen.
    orch = _SpyOrchestrator(DocModelLookup(doc=_doc_model(OTHER_TENANT_USERDOC)))

    status, body = _call_doc_model(orch, paper_id=OTHER_TENANT_USERDOC, principal={"user_id": "u1"})

    assert status == 404
    assert orch.doc_model_calls == [], "private id reached the reader before being rejected"


def test_public_doc_model_route_rejects_private_id_that_exists_for_the_owner_too() -> None:
    # Indistinguishable: the same 404 whether or not the object exists. An owner-scoped 403/404
    # pair would leak existence, so the private namespace is refused before any lookup.
    orch = _SpyOrchestrator(DocModelLookup())  # would have been a miss anyway

    status, _ = _call_doc_model(
        orch, paper_id=OTHER_TENANT_USERDOC, principal={"user_id": "u-owner"}
    )

    assert status == 404
    assert orch.doc_model_calls == []


def test_public_doc_model_route_refuses_private_id_even_when_the_license_gate_is_off() -> None:
    # The refusal must not be reachable-behind a flag: a deployment with doc-model disabled
    # otherwise answers the private namespace with 200 "license_unavailable", which resolves it
    # (and its licence state) instead of hiding it.
    orch = _SpyOrchestrator(DocModelLookup(doc=_doc_model(OTHER_TENANT_USERDOC)))
    router = build_router(orch, docmodel_enabled=False, assets_enabled=False)
    for route in router.routes:
        if getattr(route, "path", None) == "/api/papers/{paper_id}/doc-model":
            resp = route.endpoint(
                _FakeRequest({"user_id": "u1"}, {"version": "1"}), OTHER_TENANT_USERDOC
            )
            break
    else:  # pragma: no cover - route always exists
        raise AssertionError("doc-model route not found")

    assert resp.status_code == 404
    assert json.loads(resp.body) == {"status": "not_found"}
    assert orch.doc_model_calls == []


def test_summarize_refuses_a_private_id_before_entering_the_pipeline() -> None:
    # Summarization is a corpus capability keyed on a caller-supplied id. Refusing the private
    # namespace here stops a private doc-model from being resolved as the summary SOURCE and a
    # derived artifact cached under a caller-chosen id.
    class _RefusingOrchestrator(_SpyOrchestrator):
        def summarize(self, request, ctx):  # pragma: no cover - must never be reached
            raise AssertionError("a private id reached the summarization pipeline")

    orch = _RefusingOrchestrator()
    router = build_router(orch, docmodel_enabled=True, assets_enabled=True)
    for route in router.routes:
        if getattr(route, "path", None) == "/api/summarize":
            payload = {"paperId": OTHER_TENANT_USERDOC, "version": 1, "task": "summary"}
            resp = route.endpoint(_FakeRequest({"user_id": "u1"}), payload)
            break
    else:  # pragma: no cover - route always exists
        raise AssertionError("summarize route not found")

    assert resp.status_code == 404
    assert json.loads(resp.body) == {"status": "not_found"}


def test_public_assets_route_rejects_private_id_before_any_read() -> None:
    # F07 shares this boundary: the asset manifest is keyed on the same caller-supplied id.
    orch = _SpyOrchestrator(assets=[AssetRef("a1", "figure", 1, "Fig", "structured", "https://x/y")])

    status, _ = _call_assets(orch, paper_id=OTHER_TENANT_USERDOC, principal={"user_id": "u1"})

    assert status == 404
    assert orch.asset_calls == [], "private id reached the asset manifest before being rejected"


def test_public_doc_model_route_still_serves_a_corpus_paper() -> None:
    # Guard against over-blocking: the corpus route must keep working for arXiv ids.
    orch = _SpyOrchestrator(DocModelLookup(doc=_doc_model()))

    status, body = _call_doc_model(orch, paper_id="2401.00001", principal={"user_id": "u1"})

    assert status == 200
    assert body["docModel"]["meta"]["paperId"] == "2401.00001"
    assert orch.doc_model_calls == [("2401.00001", 1)]


def test_public_doc_model_route_requires_a_principal_even_for_corpus_papers() -> None:
    # 401 still precedes the 404 so an anonymous caller learns nothing about the namespace.
    orch = _SpyOrchestrator(DocModelLookup(doc=_doc_model()))

    status, _ = _call_doc_model(orch, paper_id="2401.00001", principal=None)

    assert status == 401


# --- Phase 1: the corpus reader must not read a private id out of the corpus prefix --------


def test_corpus_reader_never_reads_a_private_id_from_the_corpus_prefix() -> None:
    # Even if a caller reaches an adapter directly, the shared-prefix read is refused: the
    # corpus prefix is public data and must never hold (or surface) a private document.
    body = _doc_model(OTHER_TENANT_USERDOC).model_dump_json(exclude_none=True).encode("utf-8")
    s3 = _FakeS3({f"doc-model/{OTHER_TENANT_USERDOC}/v1.json": body})
    reader = S3DocModelReader(bucket="papers", client=s3)

    assert reader.get_doc_model(OTHER_TENANT_USERDOC, 1) is None
    assert s3.calls == [], "a private id must not be resolved against the shared corpus prefix"


def test_corpus_reader_still_reads_a_corpus_paper() -> None:
    body = _doc_model().model_dump_json(exclude_none=True).encode("utf-8")
    s3 = _FakeS3({"doc-model/2401.00001/v1.json": body})
    reader = S3DocModelReader(bucket="papers", client=s3)

    assert reader.get_doc_model("2401.00001", 1) is not None


# --- Phase 1: owner-scoped private read (ID-Q1 separate prefix) ----------------------------


def test_private_read_resolves_the_owners_own_prefix() -> None:
    doc_id = "11111111-1111-4111-8111-111111111111"
    body = _doc_model(OTHER_TENANT_USERDOC).model_dump_json(exclude_none=True).encode("utf-8")
    key = f"private/userdoc/u-owner/{doc_id}/v1.json"
    s3 = _FakeS3({key: body})
    reader = S3DocModelReader(bucket="papers", client=s3)

    doc = reader.get_private_doc_model("u-owner", doc_id, 1)

    assert doc is not None
    assert s3.calls == [key]


def test_private_read_for_a_non_owner_is_a_miss_not_a_disclosure() -> None:
    # Only the owner's prefix is probed, so another tenant's request resolves to their OWN
    # (empty) prefix. A non-owner can never distinguish "exists but not yours" from "absent".
    doc_id = "11111111-1111-4111-8111-111111111111"
    body = _doc_model(OTHER_TENANT_USERDOC).model_dump_json(exclude_none=True).encode("utf-8")
    s3 = _FakeS3({f"private/userdoc/u-owner/{doc_id}/v1.json": body})
    reader = S3DocModelReader(bucket="papers", client=s3)

    assert reader.get_private_doc_model("u-attacker", doc_id, 1) is None
    assert s3.calls == [f"private/userdoc/u-attacker/{doc_id}/v1.json"]


def test_private_and_corpus_prefixes_are_disjoint() -> None:
    # ID-Q1: a separate prefix is what makes IAM isolation (and therefore any future audit)
    # possible. Assert the two key spaces cannot collide for the same document id.
    doc_id = "11111111-1111-4111-8111-111111111111"
    s3 = _FakeS3({})
    reader = S3DocModelReader(bucket="papers", client=s3)

    reader.get_private_doc_model("u-owner", doc_id, 1)
    reader.get_doc_model(f"userdoc:{doc_id}", 1)

    private_keys = [k for k in s3.calls if k.startswith("private/")]
    corpus_keys = [k for k in s3.calls if k.startswith("doc-model/")]
    assert private_keys and not corpus_keys
    assert not set(private_keys) & set(corpus_keys)
