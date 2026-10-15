"""Checkpoint identity/hashing contract only; these tests do not authorize restore."""

import dataclasses
import json
from uuid import UUID, uuid4

import pytest

from docsuri_ops.u2_restore_context import (
    MAX_FRAGMENT_BYTES,
    RestoreContext,
    canonical_json_bytes,
    compute_checkpoint_digest,
    context_from_json,
    context_to_json,
    fragment_digest,
    read_json_record,
    validate_fragment,
    verify_checkpoint_digest,
)

pytestmark = pytest.mark.u2_operations


@pytest.fixture(scope="session", autouse=True)
def exclusive_environment():
    yield


@pytest.fixture
def context():
    return RestoreContext(run_id="docsuri-u2-0123456789abcdef", checkpoint_id=uuid4(),
        sequence=1, previous_digest=None, checkpoint_digest="0" * 64,
        backup_digest="1" * 64, source_digest="2" * 64, schema_digest="3" * 64,
        policy_digest="4" * 64, manifest_digest="5" * 64)


def envelope(context, owner="Library"):
    return {"owner": owner, "version": 1, "runId": context.run_id,
        "checkpointId": str(context.checkpoint_id), "sequence": context.sequence,
        "records": [{"accountId": str(uuid4()), "generation": 3}]}


def test_context_is_immutable_and_json_roundtrips_exactly(context):
    assert context_from_json(context_to_json(context)) == context
    assert context_to_json(context)["restoreDatabase"] == "docsuri_u2_restore"
    with pytest.raises(dataclasses.FrozenInstanceError):
        context.sequence = 2


@pytest.mark.parametrize("changed", [
    {"run_id": "docsuri-u1-0123456789abcdef"}, {"run_id": "../../other"},
    {"checkpoint_id": "not-a-uuid"}, {"checkpoint_id": UUID(int=0)},
    {"sequence": 0}, {"sequence": True}, {"sequence": 2**63},
    {"restore_database": "docsuri_u2"}, {"restore_database": "postgres"},
    {"schema_digest": "Z" * 64}, {"policy_digest": ""},
    {"manifest_digest": "a" * 63}, {"previous_digest": "6" * 64}, {"sequence": 2},
])
def test_invalid_context_bindings_refuse(context, changed):
    with pytest.raises(ValueError):
        dataclasses.replace(context, **changed)


def test_later_checkpoint_requires_predecessor_digest(context):
    later = dataclasses.replace(context, sequence=2, previous_digest="6" * 64)
    assert context_from_json(context_to_json(later)) == later


@pytest.mark.parametrize("change", ["unknown", "missing", "uuid-type", "uuid-invalid", "uuid-noncanonical"])
def test_external_context_is_strict(context, change):
    value = context_to_json(context)
    if change == "unknown":
        value["allowRestore"] = True
    elif change == "missing":
        del value["schemaDigest"]
    elif change == "uuid-type":
        value["checkpointId"] = 1
    elif change == "uuid-invalid":
        value["checkpointId"] = "invalid"
    else:
        value["checkpointId"] = value["checkpointId"].upper()
    with pytest.raises(ValueError):
        context_from_json(value)


def test_fragment_digest_is_stable_for_key_order_and_changes_for_records(context):
    fragment = envelope(context)
    original = fragment_digest(context, fragment)
    assert fragment_digest(context, dict(reversed(list(fragment.items())))) == original
    fragment["records"][0]["generation"] += 1
    assert fragment_digest(context, fragment) != original
    assert canonical_json_bytes({"한글": "정상", "a": 1}) == '{"a":1,"한글":"정상"}'.encode()


@pytest.mark.parametrize("field,value", [
    ("owner", "unknown"), ("owner", []), ("version", True), ("version", 2),
    ("runId", "docsuri-u2-ffffffffffffffff"), ("checkpointId", str(uuid4())),
    ("sequence", True), ("sequence", 2), ("records", "not-a-list"),
    ("records", ["not-an-object"]), ("records", [{}] * 2001),
    ("records", [{"payload": "x" * MAX_FRAGMENT_BYTES}]),
])
def test_foreign_or_unbounded_fragment_refuses(context, field, value):
    fragment = envelope(context)
    fragment[field] = value
    with pytest.raises(ValueError):
        validate_fragment(context, fragment)


def test_extra_fragment_key_is_not_accepted_as_authority(context):
    fragment = envelope(context)
    fragment["activate"] = True
    with pytest.raises(ValueError, match="envelope"):
        validate_fragment(context, fragment)


def test_checkpoint_hash_is_order_independent_and_self_digest_excluded(context):
    fragments = [envelope(context, "Library"), envelope(context, "Personalization")]
    owners = frozenset(("Library", "Personalization"))
    digest = compute_checkpoint_digest(context, fragments, required_owners=owners)
    bound = dataclasses.replace(context, checkpoint_digest=digest)
    verify_checkpoint_digest(bound, list(reversed(fragments)), required_owners=owners)
    fragments[0]["records"][0]["generation"] += 1
    with pytest.raises(ValueError, match="digest differs"):
        verify_checkpoint_digest(bound, fragments, required_owners=owners)


@pytest.mark.parametrize("case", ["empty", "missing", "repeated", "unknown"])
def test_checkpoint_requires_complete_explicit_owner_set(context, case):
    fragments = [envelope(context)]
    owners = frozenset(("Library",))
    if case == "empty":
        owners = frozenset()
    elif case == "missing":
        owners = frozenset(("Library", "Personalization"))
    elif case == "repeated":
        owners = frozenset(("Library", "Personalization"))
        fragments.append(envelope(context))
    else:
        owners = frozenset(("unknown",))
    with pytest.raises(ValueError):
        compute_checkpoint_digest(context, fragments, required_owners=owners)


@pytest.mark.parametrize("raw", [b'{"a":1,"a":2}', b'{"a":{"b":1,"b":2}}',
    b'{"value":NaN}', b'{"value":Infinity}', b'{"value":1e999}', b'[]',
    b'{"a":1}' + b' ' * MAX_FRAGMENT_BYTES, b'\xff'])
def test_ambiguous_or_unbounded_json_is_not_admitted(raw):
    with pytest.raises(ValueError):
        read_json_record(raw)


def test_json_record_roundtrip_does_not_claim_authenticity(context):
    value = context_to_json(context)
    parsed = read_json_record(json.dumps(value).encode())
    assert parsed == value and "allowRestore" not in parsed and "authenticated" not in parsed
