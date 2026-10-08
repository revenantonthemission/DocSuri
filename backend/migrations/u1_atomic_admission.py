"""Narrow owner/registry/full-byte policy for the UNAPPLIED U1 TEXT candidate.

This literal pin is a source-review input, NOT a review/operational receipt. The
coordinator must obtain independent review of this pair and the inherited guarded
commit before any procedural execution. Editing SQL requires a new reviewed pin;
registry discovery or hashing arbitrary current bytes never updates this policy.
"""

from __future__ import annotations

import hashlib

from .registry import ROOT, MigrationDefinition, registry

OWNER = "summarization"
LOCAL_ID = "003_content_job_authority_prepared.sql"
RELATIVE_PATH = "backend/modules/summarization/migrations/" + LOCAL_ID
EXPECTED_DIGEST = "sha256:c19a2f0dada8c012fae76e6a1737379d5783be7f7f561e558fd6e0459eb4c0e2"


def admits_u1_atomic_script(payload: bytes, definition: MigrationDefinition) -> bool:
    """A supplied lookalike definition is insufficient: verify actual registration."""
    if (type(definition) is not MigrationDefinition or definition.owner != OWNER
            or definition.local_id != LOCAL_ID or definition.digest != EXPECTED_DIGEST
            or definition.path != ROOT / RELATIVE_PATH or definition.path.is_symlink()
            or "sha256:" + hashlib.sha256(payload).hexdigest() != EXPECTED_DIGEST):
        return False
    try:
        actual = [item for item in registry(owners={OWNER}) if item.local_id == LOCAL_ID]
        return (len(actual) == 1 and actual[0] == definition
                and definition.path.read_bytes() == payload)
    except (OSError, ValueError):
        return False
