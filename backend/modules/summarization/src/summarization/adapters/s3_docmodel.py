"""S3DocModelReader — real ``DocModelReadPort`` (BR-30). Reads U1's cached doc-model.

The object layout mirrors U1's ``S3DocModelStore`` writer (``doc-model/{paperId}/v{ver}.json``);
a miss (NoSuchKey — not yet lazily built) or a license-disallowed object returns None so the
router surfaces ``source_unavailable``. Read-only: building/caching is U1's role (D6).

REM-2 F01 (SECURITY-08): this reader has TWO key spaces and never mixes them. ``get_doc_model``
is the **corpus** read and refuses the reserved ``userdoc:`` private namespace outright — a
private document can never be resolved out of the shared public prefix, even if a caller reaches
this adapter directly. ``get_private_doc_model`` is the **owner-scoped** read: it probes only the
caller's own ``private/userdoc/{owner}/{docId}/`` prefix, so a non-owner request resolves in its
own empty prefix and cannot distinguish "exists but not yours" from "does not exist".
"""

from __future__ import annotations

import json
import logging
from typing import Any

from docsuri_shared.docmodel_contract import DOCMODEL_SCHEMA_VERSION
from docsuri_shared.dtos import DocModel
from docsuri_shared.private_docs import is_private_paper_id, private_docmodel_key

from ._paper_ref import bare_paper_id

logger = logging.getLogger(__name__)

# Mirrors U1's doc-model object layout (read-only capability).
_DOCMODEL_PREFIX = "doc-model"
# S3 error codes that mean a genuine lazy-miss (not-yet-built) → source_unavailable.
_MISS_CODES = {"NoSuchKey", "NoSuchBucket", "404"}


class S3DocModelReader:
    def __init__(
        self,
        *,
        bucket: str,
        region_name: str | None = None,
        client: Any | None = None,
        prefix: str = _DOCMODEL_PREFIX,
    ) -> None:
        if client is None:
            import boto3  # lazy

            client = boto3.client("s3", region_name=region_name)
        self._s3 = client
        self._bucket = bucket
        self._prefix = prefix.strip("/")

    def get_doc_model(self, paper_id: str, version: int) -> DocModel | None:
        """Corpus read. Refuses the private ``userdoc:`` namespace (REM-2 F01).

        Defense in depth behind the HTTP boundary: a private document is stored under the
        separate owner-scoped prefix, so resolving one here would mean falling back to the public
        corpus prefix — the cross-tenant read SECURITY-08 is about. Returns ``None`` (→ the
        caller's source_unavailable / 404 surface) WITHOUT touching S3, so a rejected private id
        cannot even be used as an existence oracle.
        """
        if is_private_paper_id(paper_id):
            logger.info(
                "private document id refused by the corpus doc-model reader (%s); "
                "private reads must go through the owner-scoped path",
                paper_id,
            )
            return None

        key = f"{self._prefix}/{bare_paper_id(paper_id)}/v{version}.json"
        return self._read_key(key)

    def get_private_doc_model(self, owner_id: str, doc_id: str, version: int) -> DocModel | None:
        """Owner-scoped private read (REM-2 F01 / FD-Q1 / ID-Q1).

        Probes ONLY ``private/userdoc/{owner}/{docId}/v{version}.json`` for the given owner, so
        ownership is enforced by the key itself: a caller asking for another tenant's ``docId``
        resolves in their own (empty) prefix and gets a miss, indistinguishable from a document
        that does not exist. Returns ``None`` on any unverifiable input or a genuine miss.
        """
        try:
            key = private_docmodel_key(owner_id=owner_id, doc_id=doc_id, version=version)
        except ValueError:
            # Unverifiable owner or a non-UUID doc id — fail closed rather than probe a key we
            # cannot attribute to this caller.
            logger.info("private doc-model read refused for unverifiable owner/doc id")
            return None
        return self._read_key(key)

    def _read_key(self, key: str) -> DocModel | None:
        """Shared read of one resolved key (corpus and private share the validation rules)."""
        from botocore.exceptions import ClientError

        try:
            obj = self._s3.get_object(Bucket=self._bucket, Key=key)
            payload = json.loads(obj["Body"].read())
            if not _is_servable_doc_model(payload):
                logger.info("unservable doc-model ignored (rebuild will heal) for %s", key)
                return None
            return DocModel.model_validate(payload)
        except ClientError as exc:
            # Only a genuine miss (not yet lazily built) is None → source_unavailable.
            # AccessDenied / throttling etc. must NOT masquerade as a miss — log + propagate
            # so a corpus-wide config failure is observable instead of silently degrading.
            if exc.response.get("Error", {}).get("Code") in _MISS_CODES:
                return None
            logger.warning("doc-model read failed for %s", key, exc_info=True)
            raise
        except Exception:
            # Parse / schema-version drift on a corrupt object — surface, don't mask as a miss.
            logger.exception("doc-model parse failed for %s", key)
            raise


# Doc-models built by parser generation >= this floor are SERVED (clean-enough text). @2 first
# sanitized formula LaTeX, so @0/@1 are rejected (a miss → rebuild). Using a floor rather than an
# explicit {@2,@3,@4} set keeps a future DOCMODEL_PARSER_VERSION bump from silently dropping the
# prior generation out of the servable set (which would force-blank every not-yet-healed doc).
# The floor is age-agnostic on the upper end: an older-but-clean doc is served immediately (no
# blank screen) and SummaryOrchestrator.doc_model enqueues a background rebuild to heal it.
_MIN_SERVABLE_PARSER_GENERATION = 2
# Source tiers refused regardless of parser generation: native arXiv HTML leaks raw TeX/pgf into
# fullText (the parser sanitizer targets ar5iv/LaTeXML), so a native_html doc reads as a miss →
# None → U7 re-triggers a build, which is now ar5iv/PDF-sourced (never native_html again).
_REJECTED_SOURCE_TIERS = frozenset({"native_html"})


def _parser_generation(parser_version: object) -> int | None:
    """Integer generation N from a ``docmodel-parser@N`` string, or None if unparseable."""
    if not isinstance(parser_version, str):
        return None
    _, sep, gen = parser_version.rpartition("@")
    return int(gen) if sep and gen.isdigit() else None


def _is_servable_doc_model(payload: object) -> bool:
    if not isinstance(payload, dict):
        return True
    meta = payload.get("meta")
    provenance = meta.get("provenance") if isinstance(meta, dict) else None
    if not isinstance(provenance, dict):
        return False
    if provenance.get("sourceTier") in _REJECTED_SOURCE_TIERS:
        return False
    generation = _parser_generation(provenance.get("parserVersion"))
    return (
        generation is not None
        and generation >= _MIN_SERVABLE_PARSER_GENERATION
        and provenance.get("schemaVersion") == DOCMODEL_SCHEMA_VERSION
    )
