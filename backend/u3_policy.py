"""Finite U3 policy, limits and vocabulary for corpus, discovery and assistance.

Every bound is a finite local allocation validated before it is used. Numeric
service targets are not selected here: these are safety envelopes that keep the
shared single-process application (PostgreSQL pool, worker slots, host memory)
inside its documented budget. Missing required policy/permission/model/provider
evidence yields an explicit unavailable/degraded state through the owning
service; this module never fabricates availability.
"""

from __future__ import annotations

from typing import Any

# --- policy references (public, safe to render) --------------------------------

CORPUS_POLICY = {"policyId": "u3-corpus-maintenance", "revision": "1"}
ELIGIBILITY_POLICY = {"policyId": "u3-source-eligibility", "revision": "1"}
SEARCH_POLICY = {"policyId": "u3-paper-search", "revision": "1"}
CITATION_POLICY = {"policyId": "u3-citation-traversal", "revision": "1"}
ASSISTANCE_POLICY = {"policyId": "u3-paper-assistance", "revision": "1"}
GLOSSARY_POLICY = {"policyId": "u3-owner-glossary", "revision": "1"}
READING_POLICY = {"policyId": "u3-paper-reading", "revision": "1"}

# Search vocabulary revision shared by browser and service (BR4.1). The
# vocabulary is versioned with the service; unknown values are refused.
QUERY_VOCABULARY = "u3-paper-options-1"
ASSISTANCE_VOCABULARY = "u3-assistance-options-1"
# Compatibility token for the projection payload and result codecs (NFR10.2).
PROJECTION_COMPATIBILITY = "u3-projection-1"
RESULT_COMPATIBILITY = "u3-result-1"

# --- finite limits --------------------------------------------------------------

MAX_RUN_BATCH = 8  # source records per ingestion pass
MAX_RUN_CONCURRENCY = 2  # accepted non-terminal runs processed per pass
MAX_RUN_RETRIES = 2  # retry attempts of reconciled stages per run
MAX_EFFECTS_PER_RUN = 512  # bounded effect rows per run
MAX_PROJECTION_BATCHES = 32  # batches per generation
MAX_PAGE_SIZE = 100
DEFAULT_PAGE_SIZE = 20
MAX_CURSOR_SECONDS = 300  # snapshot window lifetime for a signed cursor
MAX_CITATION_DEPTH = 2
MAX_CITATION_NODES = 32
MAX_CITATION_REQUESTS = 4  # provider requests per traversal
MAX_QUERY_BYTES = 2048
MAX_GLOSSARY_TERMS = 64
MAX_TERM_BYTES = 128
MAX_TERM_LENGTH = 64  # normalized code points per term
MAX_SECTIONS = 512
MAX_SECTION_TEXT_BYTES = 262144
MAX_JOB_PROGRESS_EVENTS = 256
MAX_JOB_FENCES = 3
LEASE_SECONDS = 30
RUN_DEADLINE_SECONDS = 300
WORKSPACE_BYTES = 2 * 1024 * 1024  # single parsed source payload bound
MODEL_CONCURRENCY = 1

# --- dispositions ---------------------------------------------------------------

READ_DISPOSITIONS = (
    "available",
    "source-only",
    "restricted",
    "withdrawn",
    "building",
    "unsupported",
    "failed",
)
SEARCH_DEGRADATIONS = ("none", "semantic-unavailable", "partial", "provider-limited")
CITATION_FRESHNESS = ("fresh", "stale", "unknown")
CITATION_COVERAGE = ("complete", "partial", "unavailable")
RESULT_AVAILABILITY = ("pending", "ready", "expired", "failed", "unauthorized")
RUN_OPERATIONS = ("ingest", "incremental-refresh", "rebuild", "reprocess")
CHANGE_KINDS = (
    "withdrawal",
    "license-change",
    "access-change",
    "canonicalization",
    "version-change",
)
EFFECT_STAGES = ("source", "control", "content", "projection", "publication")
EFFECT_STATES = ("pending", "committed", "failed", "unknown")


def bounded_int(value: Any, *, low: int, high: int, name: str) -> int:
    """Validate one finite integer bound; never coerce silently."""
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"{name} outside finite policy")
    return value


def page_size(value: Any) -> int:
    return bounded_int(
        value if value is not None else DEFAULT_PAGE_SIZE,
        low=1,
        high=MAX_PAGE_SIZE,
        name="page size",
    )


def require_policy(value: Any, expected: dict, *, name: str = "policyRef") -> dict:
    """Refuse an unknown or stale policy reference with POLICY_UNRESOLVED semantics."""
    if not isinstance(value, dict) or value != expected:
        raise ValueError(f"unknown or stale {name}")
    return expected


def limits_document() -> dict:
    """Safe, finite limit inventory for readiness/evidence (no secrets)."""
    return {
        "maxRunBatch": MAX_RUN_BATCH,
        "maxRunConcurrency": MAX_RUN_CONCURRENCY,
        "maxRunRetries": MAX_RUN_RETRIES,
        "maxProjectionBatches": MAX_PROJECTION_BATCHES,
        "maxPageSize": MAX_PAGE_SIZE,
        "cursorWindowSeconds": MAX_CURSOR_SECONDS,
        "maxCitationDepth": MAX_CITATION_DEPTH,
        "maxCitationNodes": MAX_CITATION_NODES,
        "maxCitationRequests": MAX_CITATION_REQUESTS,
        "maxGlossaryTerms": MAX_GLOSSARY_TERMS,
        "maxJobFences": MAX_JOB_FENCES,
        "modelConcurrency": MODEL_CONCURRENCY,
        "runDeadlineSeconds": RUN_DEADLINE_SECONDS,
    }
