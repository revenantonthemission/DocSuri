"""F07 — assets are delivered same-origin, re-checked, and leak nothing (SECURITY-08).

REM-2 corrective, Phase 0.4 / Phase 4. The manifest handed the browser a **presigned object-storage
URL**, which meant:

  * the **object key** travelled inside every URL (``assets/<paper>/v<n>/<assetId>.webp``), so
    the internal storage layout was readable by any authenticated caller and forever after in
    logs, referrers and caches;
  * the **internal host** travelled with it — ``AWS_ENDPOINT_URL_S3`` (MinIO locally) would be
    published to browsers verbatim;
  * authorization was decided **once**, at manifest time. A URL signed for 600s kept working after
    the decision it was based on, and the browser's direct GET could never be re-checked.

These regressions pin the replacement: a same-origin path that names no key and no host, and a
delivery endpoint that re-runs every check — principal, namespace, license gate, and the object
itself — before a single byte leaves the process.

They also pin the CSP consequence: with delivery same-origin, the object host must no longer be
allowlisted, which is what makes "no internal endpoint exposure" enforceable rather than
aspirational.
"""

from __future__ import annotations

import json

import pytest

from summarization.adapters.rds_assets import RdsS3AssetReader
from summarization.api.router import build_router
from summarization.domain.models import AssetObject, AssetRef, StoredAsset
from summarization.service.orchestrator import SummarizationOrchestrationService

from .test_assets_endpoint import _FakeConn, _FakeRequest


class _Principal:
    def __init__(self, user_id: str) -> None:
        self.user_id = user_id


class _FakeS3:
    """Records ``get_object`` calls and returns fixed bytes."""

    def __init__(self, payload: bytes = b"\x00fake-webp") -> None:
        self.calls: list[dict] = []
        self._payload = payload

    def get_object(self, **kwargs):
        self.calls.append(kwargs)
        return {"Body": _FakeBody(self._payload)}


class _FakeBody:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def read(self) -> bytes:
        return self._payload


class _AssetOrchestrator:
    """Orchestrator double for the delivery route (object re-check lives behind it)."""

    def __init__(self, *, object_rows: dict[str, StoredAsset] | None = None, fault: bool = False):
        self._rows = object_rows or {}
        self._fault = fault
        self.delivered: list[tuple[str, int, str]] = []

    def list_assets(self, paper_id: str, version: int):
        return [
            AssetRef(
                asset_id=a.asset_id,
                type=a.type,
                ordinal=a.ordinal,
                caption=a.caption,
                source_mode=a.source_mode,
                url=f"/api/papers/{paper_id}/assets/{a.asset_id}",
            )
            for a in self._rows.values()
        ]

    def get_asset_object(self, paper_id: str, version: int, asset_id: str):
        self.delivered.append((paper_id, version, asset_id))
        if self._fault:
            raise RuntimeError("object store unavailable")
        row = self._rows.get(asset_id)
        if row is None:
            return None
        return AssetObject(payload=b"\x00fake-webp", content_type="image/webp")


def _endpoint(orch, path: str, *, assets_enabled: bool = True):
    router = build_router(orch, assets_enabled=assets_enabled)
    for route in router.routes:
        if getattr(route, "path", None) == path:
            return route.endpoint
    raise AssertionError(f"GET {path} not found")


_DEFAULT_PRINCIPAL = _Principal("u1")


def _deliver(
    orch,
    *,
    principal=_DEFAULT_PRINCIPAL,
    paper_id: str = "2401.00001",
    asset_id: str = "a0",
    version: str = "1",
    assets_enabled: bool = True,
):
    endpoint = _endpoint(
        orch, "/api/papers/{paper_id}/assets/{asset_id}", assets_enabled=assets_enabled
    )
    resp = endpoint(_FakeRequest(principal, {"version": version}), paper_id, asset_id)
    return resp


# --- the manifest leaks neither the object key nor the storage host ------------------------


def test_manifest_urls_are_same_origin_and_name_no_object_key() -> None:
    orch = SummarizationOrchestrationService.__new__(SummarizationOrchestrationService)
    orch._asset_reader = _PartialReader()
    body = [r.to_dict() for r in orch.list_assets("2401.00001", 1)]

    assert body, "the manifest must still list its assets"
    for entry in body:
        url = entry["url"]
        assert url.startswith("/"), f"asset url must be a same-origin path, got {url!r}"
        assert "://" not in url, f"asset url must not name a host, got {url!r}"
        # The object key is ``assets/{paper}/v{n}/{assetId}.webp`` — none of it may appear.
        assert "/assets/2401.00001/v1/" not in url
        assert not url.endswith(".webp"), f"the object key must not be reachable, got {url!r}"


def test_manifest_never_contains_the_object_ref_or_a_presigned_signature() -> None:
    orch = SummarizationOrchestrationService.__new__(SummarizationOrchestrationService)
    orch._asset_reader = _PartialReader()
    serialized = json.dumps([r.to_dict() for r in orch.list_assets("2401.00001", 1)])

    for leak in ("s3://", "X-Amz-Signature", "X-Amz-Credential", "object_ref", "objectRef"):
        assert leak not in serialized, f"{leak} must not appear in an asset response"


class _PartialReader:
    """Two manifest rows with real ``object_ref`` values — the internal truth."""

    def list_assets(self, paper_id: str, version: int):
        return [
            StoredAsset(
                "a1", "figure", 0, "F1", "page-crop", "s3://bkt/assets/p/v1/a1.webp", 1, None
            ),
            StoredAsset("a2", "table", 1, "T1", "page-crop", "/internal/leak.webp", 2, None),
        ]

    def get_asset_object(self, paper_id: str, version: int, asset_id: str):
        if asset_id != "a1":
            return None
        return AssetObject(payload=b"\x00fake-webp", content_type="image/webp")


# --- the delivery endpoint re-checks, then serves bytes --------------------------------------


def test_a_manifest_asset_is_delivered_as_bytes_with_an_image_content_type() -> None:
    orch = _AssetOrchestrator(
        object_rows={"a0": StoredAsset("a0", "figure", 0, "F", "page-crop", "s3://b/k.webp")}
    )

    resp = _deliver(orch)

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("image/")
    assert b"fake-webp" in bytes(resp.body)
    assert orch.delivered == [("2401.00001", 1, "a0")]


def test_delivery_requires_a_principal() -> None:
    orch = _AssetOrchestrator(
        object_rows={"a0": StoredAsset("a0", "figure", 0, "F", "page-crop", "s3://b/k.webp")}
    )

    resp = _deliver(orch, principal=None)

    assert resp.status_code == 401
    assert orch.delivered == [], "an unauthenticated delivery must not reach the object store"


def test_an_asset_id_that_is_not_in_the_manifest_is_not_delivered() -> None:
    # The object re-check: a caller naming someone else's / any asset id gets nothing, because the
    # lookup is keyed on (paper, version, asset_id) in the manifest — not on the id alone.
    orch = _AssetOrchestrator(
        object_rows={"a0": StoredAsset("a0", "figure", 0, "F", "page-crop", "s3://b/k.webp")}
    )

    resp = _deliver(orch, asset_id="someone-elses-asset")

    assert resp.status_code == 404
    assert json.loads(resp.body) == {"status": "not_found"}


def test_delivery_never_redirects_to_object_storage() -> None:
    orch = _AssetOrchestrator(
        object_rows={"a0": StoredAsset("a0", "figure", 0, "F", "page-crop", "s3://b/k.webp")}
    )

    resp = _deliver(orch)

    # A 30x would hand the browser a storage URL and move the fetch out of this authorization
    # boundary entirely — the exact shape F07 removes.
    assert not (300 <= resp.status_code < 400), "delivery must not redirect to object storage"
    assert "location" not in {k.lower() for k in resp.headers}


def test_the_private_namespace_is_refused_before_any_object_read() -> None:
    orch = _AssetOrchestrator(object_rows={})

    resp = _deliver(orch, paper_id="userdoc:123e4567-e89b-12d3-a456-426614174000", asset_id="a0")

    assert resp.status_code == 404
    assert json.loads(resp.body) == {"status": "not_found"}
    assert orch.delivered == [], "the private namespace must be refused without touching the store"


def test_the_private_namespace_refusal_precedes_the_license_gate() -> None:
    # With assets disabled the corpus manifest answers a 200 "license_unavailable"; if that also
    # answered for a private id, the response itself would make the namespace resolvable.
    orch = _AssetOrchestrator(object_rows={})

    resp = _deliver(
        orch,
        paper_id="userdoc:123e4567-e89b-12d3-a456-426614174000",
        assets_enabled=False,
    )

    assert resp.status_code == 404


def test_the_license_gate_is_re_checked_at_delivery_not_only_at_manifest_time() -> None:
    # A manifest URL outlives the decision that produced it (600s presign TTL did exactly that).
    # Delivery re-reads the gate.
    orch = _AssetOrchestrator(
        object_rows={"a0": StoredAsset("a0", "figure", 0, "F", "page-crop", "s3://b/k.webp")}
    )

    resp = _deliver(orch, assets_enabled=False)

    assert resp.status_code == 200
    assert json.loads(resp.body) == {"status": "license_unavailable"}
    assert orch.delivered == []


def test_a_store_fault_fails_closed_with_a_generic_503() -> None:
    orch = _AssetOrchestrator(fault=True)

    resp = _deliver(orch)

    assert resp.status_code == 503
    body = resp.body if isinstance(resp.body, bytes) else resp.body.encode()
    assert b"RuntimeError" not in body and b"object store" not in body


def test_delivered_bytes_are_not_cacheable_by_a_shared_cache() -> None:
    # Corpus assets are same-origin and authenticated; a shared/proxy cache holding them would
    # serve one caller another caller's authorized bytes.
    orch = _AssetOrchestrator(
        object_rows={"a0": StoredAsset("a0", "figure", 0, "F", "page-crop", "s3://b/k.webp")}
    )

    resp = _deliver(orch)

    cache_control = resp.headers.get("cache-control", "")
    assert "public" not in cache_control
    assert "private" in cache_control or "no-store" in cache_control


# --- the reader looks the object up in the manifest before fetching it ---------------------


def test_the_reader_resolves_the_object_through_the_manifest_query() -> None:
    conn = _FakeConn([("s3://bkt/assets/2401.00001/v1/a0.webp",)])
    s3 = _FakeS3()
    reader = RdsS3AssetReader(connection=conn, s3_client=s3)

    payload = reader.get_asset_object("2401.00001", 1, "a0")

    assert payload.payload == b"\x00fake-webp"
    assert payload.content_type == "image/webp"
    sql, params = conn._cur.executed
    # The lookup is scoped by paper AND version AND asset_id, parameterized (no string building).
    assert "%s" in sql
    assert set(params).issuperset({"2401.00001", "a0"})
    assert s3.calls == [{"Bucket": "bkt", "Key": "assets/2401.00001/v1/a0.webp"}]


def test_the_reader_returns_nothing_when_the_asset_is_not_in_the_manifest() -> None:
    conn = _FakeConn([])
    s3 = _FakeS3()
    reader = RdsS3AssetReader(connection=conn, s3_client=s3)

    assert reader.get_asset_object("2401.00001", 1, "a0") is None
    assert s3.calls == [], "a missing manifest row must not reach the object store"


def test_the_reader_never_exposes_a_storage_url() -> None:
    """The presign capability is gone from the reader surface.

    It is the thing that produced the leaked key and host, so leaving it available would only be
    waiting for the next caller to put it back on a response.
    """
    assert not hasattr(RdsS3AssetReader, "presign")


@pytest.mark.parametrize(
    "attr",
    ["presign", "generate_presigned_url"],
)
def test_no_presign_helper_survives_on_the_reader(attr: str) -> None:
    assert not hasattr(RdsS3AssetReader, attr)


# --- the CSP consequence -------------------------------------------------------------------


def test_the_csp_no_longer_allowlists_an_object_storage_host() -> None:
    from pathlib import Path

    middleware = Path(__file__).resolve().parents[4] / "frontend" / "middleware.ts"
    csp_lines = [
        line
        for line in middleware.read_text().splitlines()
        if "img-src" in line and not line.strip().startswith("//")
    ]
    assert csp_lines, "the CSP must still declare img-src"
    directive = csp_lines[0]
    assert "'self'" in directive, directive
    # Same-origin delivery is the point: any external image host here re-opens the leak.
    assert "amazonaws.com" not in directive, directive
    assert "minio" not in directive.lower(), directive