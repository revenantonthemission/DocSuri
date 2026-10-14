"""Immutable U2 restore-checkpoint bindings, without database or activation authority.

Canonical hashes establish content identity only. The restore coordinator must
authenticate the independently retained journal and prove its current high-water
checkpoint before handing these values to owner reconciliation hooks. A successful
hash check never permits application traffic or clears quarantine.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
from dataclasses import dataclass
from typing import Any
from uuid import UUID

RESTORE_DATABASE = "docsuri_u2_restore"
MAX_FRAGMENT_BYTES = 256 * 1024
MAX_RECORDS = 2000  # At most 20 synthetic accounts, 100 records per account.
OWNERS = frozenset(
    (
        "AccountAccess",
        "CorpusContent",
        "DiscoveryCitations",
        "Library",
        "Personalization",
        "PaperAssistance",
        "UsageEntitlements",
        "ServiceOperations",
    )
)
DIGEST_FIELDS = (
    "checkpoint_digest",
    "backup_digest",
    "source_digest",
    "schema_digest",
    "policy_digest",
    "manifest_digest",
)
JSON_FIELDS = {
    "run_id": "runId",
    "checkpoint_id": "checkpointId",
    "sequence": "sequence",
    "previous_digest": "previousDigest",
    "checkpoint_digest": "checkpointDigest",
    "backup_digest": "backupDigest",
    "source_digest": "sourceDigest",
    "schema_digest": "schemaDigest",
    "policy_digest": "policyDigest",
    "manifest_digest": "manifestDigest",
    "restore_database": "restoreDatabase",
}


def _digest(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


@dataclass(frozen=True)
class RestoreContext:
    run_id: str
    checkpoint_id: UUID
    sequence: int
    previous_digest: str | None
    checkpoint_digest: str
    backup_digest: str
    source_digest: str
    schema_digest: str
    policy_digest: str
    manifest_digest: str
    restore_database: str = RESTORE_DATABASE

    def __post_init__(self) -> None:
        if not isinstance(self.run_id, str) or not re.fullmatch(
            r"docsuri-u2-[0-9a-f]{16}", self.run_id
        ):
            raise ValueError("explicit U2 run identity required")
        if not isinstance(self.checkpoint_id, UUID) or self.checkpoint_id.int == 0:
            raise ValueError("nonzero checkpoint UUID required")
        if type(self.sequence) is not int or not 1 <= self.sequence <= 2**63 - 1:
            raise ValueError("positive bounded checkpoint sequence required")
        if self.restore_database != RESTORE_DATABASE:
            raise ValueError("only the quarantined U2 restore database is supported")
        if any(not _digest(getattr(self, name)) for name in DIGEST_FIELDS):
            raise ValueError("lowercase SHA-256 digest required")
        if (self.sequence == 1 and self.previous_digest is not None) or (
            self.sequence > 1 and not _digest(self.previous_digest)
        ):
            raise ValueError("checkpoint predecessor binding required")


def context_to_json(context: RestoreContext) -> dict:
    result = {target: getattr(context, source) for source, target in JSON_FIELDS.items()}
    result["checkpointId"] = str(context.checkpoint_id)
    return result


def context_from_json(value: dict) -> RestoreContext:
    if not isinstance(value, dict) or set(value) != set(JSON_FIELDS.values()):
        raise ValueError("exact restore context fields required")
    if not isinstance(value["checkpointId"], str):
        raise ValueError("checkpointId must be a UUID string")
    try:
        identifier = UUID(value["checkpointId"])
    except ValueError as exc:
        raise ValueError("checkpointId must be a UUID string") from exc
    if str(identifier) != value["checkpointId"]:
        raise ValueError("canonical checkpoint UUID required")
    arguments = {source: value[target] for source, target in JSON_FIELDS.items()}
    arguments["checkpoint_id"] = identifier
    return RestoreContext(**arguments)


def canonical_json_bytes(value: Any) -> bytes:
    """Hash UTF-8 JSON with sorted keys, no whitespace, NaN or Infinity."""
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def validate_fragment(context: RestoreContext, fragment: dict) -> None:
    keys = {"owner", "version", "runId", "checkpointId", "sequence", "records"}
    if not isinstance(fragment, dict) or set(fragment) != keys:
        raise ValueError("exact owner fragment envelope required")
    if (
        not isinstance(fragment["owner"], str)
        or fragment["owner"] not in OWNERS
        or type(fragment["version"]) is not int
        or fragment["version"] != 1
        or type(fragment["sequence"]) is not int
        or fragment["sequence"] != context.sequence
        or fragment["runId"] != context.run_id
        or fragment["checkpointId"] != str(context.checkpoint_id)
    ):
        raise ValueError("owner fragment checkpoint identity differs")
    records = fragment["records"]
    if (
        not isinstance(records, list)
        or len(records) > MAX_RECORDS
        or any(not isinstance(row, dict) for row in records)
    ):
        raise ValueError("bounded owner records required")
    if len(canonical_json_bytes(fragment)) > MAX_FRAGMENT_BYTES:
        raise ValueError("owner fragment exceeds checkpoint allocation")


def fragment_digest(context: RestoreContext, fragment: dict) -> str:
    validate_fragment(context, fragment)
    return sha256_json(fragment)


def checkpoint_payload(
    context: RestoreContext, fragments: list[dict], *, required_owners: frozenset[str]
) -> dict:
    """Canonical digest payload excludes its own digest and authentication tag."""
    if (
        not required_owners
        or not required_owners <= OWNERS
        or len(fragments) != len(required_owners)
    ):
        raise ValueError("complete explicit owner set required")
    for fragment in fragments:
        validate_fragment(context, fragment)
    if {fragment["owner"] for fragment in fragments} != required_owners:
        raise ValueError("missing, repeated or incompatible owner fragment")
    metadata = context_to_json(context)
    del metadata["checkpointDigest"]
    return {
        "version": 1,
        "context": metadata,
        "fragments": sorted(fragments, key=lambda item: item["owner"]),
    }


def compute_checkpoint_digest(
    context: RestoreContext, fragments: list[dict], *, required_owners: frozenset[str]
) -> str:
    return sha256_json(checkpoint_payload(context, fragments, required_owners=required_owners))


def verify_checkpoint_digest(
    context: RestoreContext, fragments: list[dict], *, required_owners: frozenset[str]
) -> None:
    expected = compute_checkpoint_digest(context, fragments, required_owners=required_owners)
    if not hmac.compare_digest(expected, context.checkpoint_digest):
        raise ValueError("checkpoint content digest differs")


def read_json_record(raw: bytes, *, maximum: int = MAX_FRAGMENT_BYTES) -> dict:
    """Parse bounded external JSON without duplicate keys or non-finite numbers."""
    if (
        not isinstance(raw, bytes)
        or not 1 <= maximum <= 8 * MAX_FRAGMENT_BYTES
        or len(raw) > maximum
    ):
        raise ValueError("bounded checkpoint bytes required")

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate checkpoint key")
            result[key] = value
        return result

    def invalid_constant(value):
        raise ValueError("non-finite checkpoint number")

    result = json.loads(
        raw.decode("utf-8"), object_pairs_hook=unique, parse_constant=invalid_constant
    )
    if not isinstance(result, dict):
        raise ValueError("checkpoint object required")
    canonical_json_bytes(result)  # Also rejects exponent overflow (for example 1e999).
    return result
