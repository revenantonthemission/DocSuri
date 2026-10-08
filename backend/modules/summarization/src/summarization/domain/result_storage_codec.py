"""Private canonical-json-ascii-v2 for opaque, parameter-bound PostgreSQL TEXT.

Only prepared content/identity use this codec. Server input canonical-json-v1 and
the browser's UTF-8 owner-prefixed JSON.stringify hash MUST remain independent.
No SQL JSON parser/adapter is needed. A reversible string layer escapes literal
backslashes and individual surrogate code points BEFORE standard ASCII JSON.
Thus a Python high/low-surrogate pair cannot collapse into the corresponding
astral scalar during json.loads. The layer applies equally to string keys/values;
its strict inverse restores the original code points, never normalizes them.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
from collections.abc import Callable

from .job_protocol import JobProtocolError, JsonValue, json_value

CONTENT_ENCODING = "json-ascii"
CANONICAL_VERSION = 2
_DIGEST = re.compile(r"[a-f0-9]{64}\Z")
_SURROGATE_HEX = re.compile(r"d[89a-f][0-9a-f]{2}\Z")


def _encode_string(value: str) -> str:
    encoded: list[str] = []
    for char in value:
        if char == "\\":
            encoded.append("\\\\")
        elif 0xD800 <= ord(char) <= 0xDFFF:
            encoded.append(f"\\u{ord(char):04x}")
        else:
            encoded.append(char)
    return "".join(encoded)


def _decode_string(value: str) -> str:
    decoded: list[str] = []
    index = 0
    while index < len(value):
        char = value[index]
        if 0xD800 <= ord(char) <= 0xDFFF:
            # Encoder output never contains a raw surrogate. Old/coalesced or
            # malformed records cannot be guessed into the new representation.
            raise JobProtocolError("result_unavailable")
        if char != "\\":
            decoded.append(char)
            index += 1
        elif value.startswith("\\\\", index):
            decoded.append("\\")
            index += 2
        elif (value.startswith("\\u", index)
              and _SURROGATE_HEX.fullmatch(value[index + 2:index + 6])):
            decoded.append(chr(int(value[index + 2:index + 6], 16)))
            index += 6
        else:
            raise JobProtocolError("result_unavailable")
    return "".join(decoded)


def _transform_strings(value: JsonValue, transform: Callable[[str], str]) -> JsonValue:
    if isinstance(value, str):
        return transform(value)
    if isinstance(value, list):
        return [_transform_strings(item, transform) for item in value]
    if isinstance(value, dict):
        result: dict[str, JsonValue] = {}
        for key, item in value.items():
            mapped_key = transform(key)
            if mapped_key in result:
                raise JobProtocolError("result_unavailable")
            result[mapped_key] = _transform_strings(item, transform)
        return result
    return value


def canonical_content(value: object) -> str:
    """Detach finite JSON; sort encoded keys; preserve arrays and original strings.

    String-layer grammar is ``\\\\`` for a literal backslash and ``\\uXXXX``
    (lowercase surrogate hex only) for one original surrogate code point. Scalar
    characters remain scalar until JSON escaping; inverse processing occurs only
    AFTER JSON parsing. No two admitted strings/keys share this representation.
    """
    try:
        layered = _transform_strings(json_value(value), _encode_string)
        return json.dumps(layered, sort_keys=True, ensure_ascii=True,
                          allow_nan=False, separators=(",", ":"))
    except (ValueError, TypeError, RecursionError, OverflowError) as exc:
        raise JobProtocolError("content_invalid") from exc


def prepared_content_digest(value: object) -> str:
    return hashlib.sha256(canonical_content(value).encode("ascii")).hexdigest()


def _unique_object(pairs: list[tuple[str, JsonValue]]) -> dict[str, JsonValue]:
    result: dict[str, JsonValue] = {}
    for key, value in pairs:
        if key in result:
            raise JobProtocolError("result_unavailable")
        result[key] = value
    return result


def _reject_constant(_value: str) -> None:
    raise JobProtocolError("result_unavailable")


def decode_canonical_content(serialized: object) -> JsonValue:
    """Refuse corruption/noncanonical bytes; never silently recanonicalize a record."""
    if not isinstance(serialized, str) or not serialized.isascii() or "\x00" in serialized:
        raise JobProtocolError("result_unavailable")
    try:
        layered = json.loads(serialized, object_pairs_hook=_unique_object,
                             parse_constant=_reject_constant)
        value = _transform_strings(layered, _decode_string)
        if canonical_content(value) != serialized:
            raise JobProtocolError("result_unavailable")
        return json_value(value)
    except (ValueError, TypeError, RecursionError, JobProtocolError) as exc:
        raise JobProtocolError("result_unavailable") from exc


def decode_prepared_content(serialized: object, *, content_encoding: object,
                            canonical_version: object, digest: object) -> JsonValue:
    """Explicit versions and exact-byte integrity are mandatory, including on restore."""
    if (content_encoding != CONTENT_ENCODING or type(canonical_version) is not int
            or canonical_version != CANONICAL_VERSION or not isinstance(digest, str)
            or not _DIGEST.fullmatch(digest)):
        raise JobProtocolError("result_unavailable")
    value = decode_canonical_content(serialized)
    actual = hashlib.sha256(serialized.encode("ascii")).hexdigest()
    if not hmac.compare_digest(actual, digest):
        raise JobProtocolError("result_unavailable")
    return value
