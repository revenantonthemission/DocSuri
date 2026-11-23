"""A4's shared arithmetic for the owners' imports and parity reads (U8 plan Step 7).

Each owner keeps its own writes; this module only fixes how every owner digests what it
stored, so the migration tool's source-side checksum and each owner's target-side one
are computed the same way (BR8.3, BR8.10):

- `stored_digest(fields)`: the SHA-256 of the RFC 8785 bytes of one record's compared
  normalized fields;
- `parity_digest(digests)`: an order-independent digest over one kind's records, the
  SHA-256 of their sorted per-record digests;
- `outcome(...)`: A4's `ImportOutcome` shape (`imported`, `unchanged`, `updated` or
  `refused` with a reason key).

No field here is ever a password, verifier, token or raw email address: an owner
passes the digest of such a value when it is compared at all.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable

import rfc8785

DISPOSITIONS = ("imported", "unchanged", "updated", "refused")
REASON = re.compile(r"[a-z][a-z0-9-]{0,63}")
DIGEST = re.compile(r"[0-9a-f]{64}")


def stored_digest(fields: dict) -> str:
    return hashlib.sha256(rfc8785.dumps(fields)).hexdigest()


def parity_digest(digests: Iterable[str]) -> str:
    values = sorted(digests)
    if not all(isinstance(value, str) and DIGEST.fullmatch(value) for value in values):
        raise ValueError("parity input must be record digests")
    return hashlib.sha256("\n".join(values).encode()).hexdigest()


def secret_digest(value: str | None) -> str | None:
    """A compared stand-in for a secret value: its SHA-256, never the value."""
    return None if value is None else hashlib.sha256(value.encode()).hexdigest()


def outcome(disposition: str, digest: str, *, reason: str | None = None) -> dict:
    if disposition not in DISPOSITIONS or DIGEST.fullmatch(digest) is None:
        raise ValueError("import outcome outside A4's shape")
    if (disposition == "refused") != (reason is not None):
        raise ValueError("only a refused import names its reason")
    if reason is not None and REASON.fullmatch(reason) is None:
        raise ValueError("import reason key outside the registered form")
    result = {"disposition": disposition, "storedDigest": digest}
    if reason is not None:
        result["reasonKey"] = reason
    return result


def decide(existing: str | None, incoming: str) -> str:
    """`imported` for a new record, `unchanged` for the same fields, else `updated`."""
    if existing is None:
        return "imported"
    return "unchanged" if existing == incoming else "updated"


def parity(kind: str, digests: list[str], observed_at: str) -> dict:
    return {
        "kind": kind, "count": len(digests), "digest": parity_digest(digests),
        "observedAt": observed_at,
    }
