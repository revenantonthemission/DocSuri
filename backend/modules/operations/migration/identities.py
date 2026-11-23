"""Deterministic target identities and canonical paper identities (U8 plan Step 31; BR8.3,
BR8.7, A4).

- `target_id(kind, source_id)`: every target identity is the UUIDv5 of (v1, kind, source
  id) under one fixed namespace, so a repeated import finds the same target, and the
  same derivation finds the v2 account of any v1 account in a retained snapshot.
- `canonical_paper` and `version_identity`: CorpusContent's one canonical identity
  (C04 2.1.0): an arXiv identifier without its version, a DOI, or the corpus's
  canonical key, each lower-case prefixed, and `<paper>@v<n>` for a version.
"""

from __future__ import annotations

import hashlib
import re
from uuid import NAMESPACE_URL, UUID, uuid5

NAMESPACE = uuid5(NAMESPACE_URL, "https://docsuri.rvnnt.dev/v1-migration")
KINDS = ("account", "identity-link", "preferences", "paper", "saved-paper")
_ARXIV = re.compile(
    r"(?:arxiv:)?(\d{4}\.\d{4,5}|[a-z][a-z.-]*(?:\.[a-z]{2})?/\d{7})(?:v([1-9]\d{0,3}))?",
    re.IGNORECASE,
)
_DOI = re.compile(r"(?:doi:)?(10\.\d{4,9}/\S{1,200})", re.IGNORECASE)
_KEY = re.compile(r"[a-z0-9][a-z0-9:._/-]{0,200}")


def target_id(kind: str, source_id: str) -> UUID:
    if kind not in KINDS or not isinstance(source_id, str) or not source_id:
        raise ValueError("a target identity needs a migrated kind and its source id")
    return uuid5(NAMESPACE, f"v1:{kind}:{source_id}")


def link_source_id(provider: str, subject: str) -> str:
    """An identity link's source id: v1 keys a link by provider and subject, and the
    subject is the person's identifier at the provider, so the id carries only its
    digest (the parity report names records by source id, BR8.10)."""
    return f"{provider}:{hashlib.sha256(subject.encode()).hexdigest()[:24]}"


def arxiv_parts(value: str) -> tuple[str, int | None] | None:
    """An arXiv identifier's canonical id (lower-case, no version) and its version."""
    match = _ARXIV.fullmatch((value or "").strip())
    if match is None:
        return None
    return match.group(1).lower(), (int(match.group(2)) if match.group(2) else None)


def canonical_paper(*, arxiv: str | None = None, doi: str | None = None,
                    key: str | None = None) -> str:
    """The canonical paper identity, preferring the arXiv identifier, then the DOI."""
    if arxiv:
        parts = arxiv_parts(arxiv)
        if parts is not None:
            return f"arxiv:{parts[0]}"
    if doi:
        match = _DOI.fullmatch(doi.strip())
        if match is not None:
            return f"doi:{match.group(1).lower()}"
    if key and _KEY.fullmatch(key.lower()):
        return f"key:{key.lower()}"
    raise ValueError("no canonical paper identity can be derived")


def version_identity(paper: str, version: int) -> str:
    if type(version) is not int or not 1 <= version <= 9999:
        raise ValueError("version number outside its bound")
    return f"{paper}@v{version}"
