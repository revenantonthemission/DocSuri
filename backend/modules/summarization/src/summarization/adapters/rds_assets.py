"""RdsS3AssetReader — real ``AssetReadPort`` (FR-17, BR-S15).

Reads the figure/table manifest from ``paper_asset`` on the shared RDS PostgreSQL
(written by U1; read-only here) and resolves an asset's bytes from S3 **server-side**.

REM-2 F07: this reader used to hand the browser a presigned GET URL, which put the object key
(``assets/{paper}/v{n}/{assetId}.webp``) and the storage host — including ``AWS_ENDPOINT_URL_S3``,
which is MinIO locally — into a caller-visible string, and moved the fetch outside every check this
process makes. ``presign`` is therefore gone rather than merely unused: the reader now looks the
object up in the manifest by (paper, version, asset_id) and returns the bytes, and the same-origin
delivery endpoint serves them. ``object_ref`` still never leaves this module (SEC-9).
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from typing import Any

from ..domain.models import AssetObject, StoredAsset
from ._paper_ref import bare_paper_id

# Object suffix → media type. U1 writes ``.webp`` crops today; anything unrecognized is served as an
# opaque byte stream rather than guessed at, so an unexpected format can't be delivered under a
# content type the browser will not sniff around.
_CONTENT_TYPES = {
    "webp": "image/webp",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
}
_FALLBACK_CONTENT_TYPE = "application/octet-stream"


class RdsS3AssetReader:
    def __init__(
        self,
        *,
        dsn: str | None = None,
        connection: Any | None = None,
        s3_client: Any | None = None,
        signed_url_ttl_seconds: int = 600,
    ) -> None:
        self._dsn = dsn
        self._conn = connection
        self._s3 = s3_client
        # Kept only so an existing caller's construction keeps working; presigning is gone, so the
        # value no longer has a purpose. Deleting the parameter is a separate breaking change to
        # the adapter's signature and its wiring.
        self._ttl = signed_url_ttl_seconds

    def _connect(self) -> Any:
        if self._conn is not None:
            # Injected connection (tests use a fake). The call site's ``with self._connect()``
            # drives its context manager — for a real psycopg connection that commits/closes on
            # exit, so inject a fresh (or fake) connection, not a long-lived shared one.
            return self._conn
        from ._pg import connection  # lazy: only the `real` extra needs psycopg

        return connection(self._dsn)  # pooled (graceful fallback to direct connect)

    def _client(self) -> Any:
        if self._s3 is None:
            import boto3  # lazy

            # The client is now used only to fetch bytes inside this process, so the endpoint is an
            # internal detail (local MinIO included) and never reaches a browser.
            region = os.getenv("AWS_REGION") or os.getenv("DOCSURI_AWS_REGION") or "ap-northeast-2"
            endpoint = os.getenv("AWS_ENDPOINT_URL_S3") or f"https://s3.{region}.amazonaws.com"
            self._s3 = boto3.client("s3", region_name=region, endpoint_url=endpoint)
        return self._s3

    def list_assets(self, paper_id: str, version: int) -> Sequence[StoredAsset]:
        # Restrict to the summary asset gallery's kinds (AssetView = figure | table). U1 also
        # writes type="formula" page-crop rows for the doc-model viewer's image-fallback equations
        # (display-only); those must not surface here or they break GET /assets validation and
        # pollute the U5 figure gallery. The literal IN list mirrors the AssetView enum.
        sql = (
            "SELECT asset_id, type, ordinal, caption, source_mode, object_ref, page_ref, bbox "
            "FROM paper_asset WHERE paper_id = %s AND version = %s "
            "AND type IN ('figure', 'table') ORDER BY type, ordinal"
        )
        # U1 writes the manifest under the bare paper_id (version is a separate column); strip
        # the version suffix the app carries so the lookup matches (else no figures/tables).
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(sql, (bare_paper_id(paper_id), version))
            return [
                StoredAsset(
                    asset_id=row[0],
                    type=row[1],
                    ordinal=int(row[2]),
                    caption=row[3] or "",
                    source_mode=row[4],
                    object_ref=row[5],
                    page_ref=int(row[6]) if row[6] is not None else None,
                    bbox=row[7],
                )
                for row in cur.fetchall()
            ]

    def get_asset_object(self, paper_id: str, version: int, asset_id: str) -> AssetObject | None:
        """The asset's bytes, or ``None`` when the manifest has no such row.

        The manifest lookup is the object re-check (F07): the caller's ``asset_id`` is not a
        capability, so the row must exist for this exact (paper, version, asset) triple before the
        object store is touched at all. A miss therefore costs one indexed query and leaks nothing
        — not even whether some other paper happens to own that id.
        """
        sql = (
            "SELECT object_ref FROM paper_asset "
            "WHERE paper_id = %s AND version = %s AND asset_id = %s "
            "AND type IN ('figure', 'table')"
        )
        with self._connect() as conn, conn.cursor() as cur:
            # Parameterized (no string building) — the ids are caller-supplied.
            cur.execute(sql, (bare_paper_id(paper_id), version, asset_id))
            row = cur.fetchone()
        if row is None:
            return None
        bucket, key = _split_s3_ref(row[0])
        if bucket is None:
            # A row whose object_ref is not an S3 URI cannot be delivered. Skipping it here keeps
            # the raw ref out of the response (SEC-9); the manifest entry simply 404s on delivery.
            return None
        payload = self._client().get_object(Bucket=bucket, Key=key)["Body"].read()
        return AssetObject(payload=payload, content_type=_content_type_for(key))


def _content_type_for(key: str) -> str:
    """Media type from the object's extension; opaque bytes when unrecognized."""
    _, _, suffix = key.rpartition(".")
    return _CONTENT_TYPES.get(suffix.lower(), _FALLBACK_CONTENT_TYPE)


def _split_s3_ref(object_ref: str) -> tuple[str | None, str | None]:
    if not object_ref or not object_ref.startswith("s3://"):
        return None, None
    rest = object_ref[len("s3://") :]
    bucket, _, key = rest.partition("/")
    if not bucket or not key:
        return None, None
    return bucket, key