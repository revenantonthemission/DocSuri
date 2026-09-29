"""Closed-world JSON Schema 2020-12 profile. Schema keywords never reinterpret literal data."""

from __future__ import annotations

import copy
import json
import math
import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urldefrag, urljoin, urlsplit

_MAPS = {"$defs", "definitions", "properties", "patternProperties", "dependentSchemas"}
_ARRAYS = {"allOf", "anyOf", "oneOf", "prefixItems"}
_SINGLE = {
    "items", "contains", "additionalProperties", "unevaluatedProperties", "unevaluatedItems",
    "propertyNames", "not", "if", "then", "else",
}
_DEFINITIONS = {"$defs", "definitions"}
_ANNOTATIONS = {
    "$id", "$schema", "$anchor", "$comment", "$defs", "definitions", "title", "description",
    "examples", "default", "deprecated", "readOnly", "writeOnly", "x-docsuri-visibility",
}
_UNSUPPORTED = {"$dynamicRef", "$dynamicAnchor", "$recursiveRef", "$recursiveAnchor", "$vocabulary"}
_VISIBILITY = {"public": 0, "server": 1, "internal": 2}
_DIALECT = "https://json-schema.org/draft/2020-12/schema"
_LIMIT = 16 * 1024**2


def _pairs(pairs):
    output = {}
    for key, value in pairs:
        if key in output:
            raise ValueError("duplicate JSON key")
        output[key] = value
    return output


def _bounds(value, depth=0):
    if depth > 64:
        raise ValueError("schema nesting limit")
    if isinstance(value, str):
        value.encode("utf-8", errors="strict")
    elif isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError("schema object key must be a string")
            _bounds(key, depth + 1)
            _bounds(item, depth + 1)
    elif isinstance(value, list):
        for item in value:
            _bounds(item, depth + 1)
    elif type(value) in (int, float):
        if abs(value) > 2**53 - 1 or not math.isfinite(value):
            raise ValueError("unsupported schema number")
    elif value is not None and type(value) is not bool:
        raise ValueError("invalid JSON value")


def parse_json(raw: bytes):
    if len(raw) > _LIMIT:
        raise ValueError("schema byte limit")
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs)
        _bounds(value)
        return value
    except (RecursionError, UnicodeError, OverflowError) as exc:
        raise ValueError("invalid schema encoding or depth") from exc


def _read_source(path):
    def opener(name, flags):
        return os.open(name, flags | os.O_NOFOLLOW | os.O_NONBLOCK)

    with open(path, "rb", opener=opener) as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError("schema source is not a regular file")
        raw = stream.read(_LIMIT + 1)
    if len(raw) > _LIMIT:
        raise ValueError("schema byte limit")
    return raw


@dataclass(frozen=True)
class Location:
    document: str
    path: tuple[str, ...] = ()

    @property
    def pointer(self) -> str:
        return "".join("/" + part.replace("~", "~0").replace("/", "~1") for part in self.path)


def _identity(value):
    if not isinstance(value, str) or not 1 <= len(value) <= 4096 or "#" in value:
        raise ValueError("invalid schema identity")
    parts = urlsplit(value)
    if (
        parts.scheme not in {"http", "https"} or not parts.hostname or parts.username is not None
        or parts.password is not None or any(c.isspace() for c in value)
        or any(part in {".", ".."} for part in unquote(parts.path).split("/"))
        or parts.netloc != parts.netloc.lower()
        or not parts.path.startswith("/") or not value.startswith(parts.scheme + "://")
        or not value.isascii() or "\\" in value
        or parts.port == {"http": 80, "https": 443}[parts.scheme]
    ):
        raise ValueError("unsupported or noncanonical schema identity")
    return value


def _children(value):
    for key, item in value.items():
        if key in _MAPS:
            if not isinstance(item, dict):
                raise ValueError("invalid schema map")
            for name, schema in item.items():
                yield (key, name), schema
        elif key in _ARRAYS:
            if not isinstance(item, list):
                raise ValueError("invalid schema array")
            for index, schema in enumerate(item):
                yield (key, str(index)), schema
        elif key in _SINGLE:
            yield (key,), item


class Catalog:
    def __init__(self, documents, *, visibility=None, paths=None, consumers=None):
        if not documents or len(documents) > 1000:
            raise ValueError("empty or oversized schema catalog")
        self.documents = {}
        self.resources = {}
        self.anchors = {}
        self.nodes = {}
        self.references = {}
        self.paths = dict(paths or {})
        self.consumers = copy.deepcopy(consumers or {})
        total = 0
        for source in documents:
            if not isinstance(source, dict):
                raise ValueError("schema document must declare an identity")
            _bounds(source)
            raw = json.dumps(source, ensure_ascii=False, allow_nan=False).encode()
            total += len(raw)
            if len(raw) > _LIMIT or total > 64 * 1024**2:
                raise ValueError("schema catalog byte limit")
            identity = _identity(source.get("$id"))
            if identity in self.documents:
                raise ValueError("duplicate schema identity")
            self.documents[identity] = copy.deepcopy(source)
        for identity, document in self.documents.items():
            self._index(
                Location(identity), document, identity, (visibility or {}).get(identity, "internal")
            )
        for location, (value, base, _) in self.nodes.items():
            if isinstance(value, dict) and "$ref" in value:
                if len(self.references) >= 20000:
                    raise ValueError("schema edge limit")
                self.references[location] = self.resolve(base, value["$ref"])

    def _index(self, location, value, base, visibility):
        if len(self.nodes) >= 100000 or visibility not in _VISIBILITY:
            raise ValueError("schema node limit or visibility invalid")
        if type(value) is not bool and not isinstance(value, dict):
            raise ValueError("schema node must be object or boolean")
        if isinstance(value, dict):
            if value.get("$schema", _DIALECT) != _DIALECT or _UNSUPPORTED.intersection(value):
                raise ValueError("unsupported schema dialect or dynamic feature")
            if "$id" in value:
                if not isinstance(value["$id"], str):
                    raise ValueError("invalid schema identity")
                base = _identity(urljoin(base, value["$id"]))
                if base in self.resources or len(self.resources) >= 1000:
                    raise ValueError("duplicate or oversized schema resources")
                self.resources[base] = location
            if "$anchor" in value:
                anchor = value["$anchor"]
                if (
                    not isinstance(anchor, str)
                    or not re.fullmatch(r"[A-Za-z_][-A-Za-z0-9._]*", anchor)
                    or (base, anchor) in self.anchors
                ):
                    raise ValueError("invalid or duplicate schema anchor")
                self.anchors[base, anchor] = location
            declared = value.get("x-docsuri-visibility", visibility)
            if declared not in _VISIBILITY or _VISIBILITY[declared] < _VISIBILITY[visibility]:
                raise ValueError("schema visibility escalation")
            visibility = declared
        self.nodes[location] = value, base, visibility
        if isinstance(value, dict):
            for path, child in _children(value):
                self._index(
                    Location(location.document, location.path + path), child, base, visibility
                )

    def resolve(self, base: str, reference: str) -> Location:
        if not isinstance(reference, str) or len(reference) > 4096:
            raise ValueError("invalid local reference")
        identity, fragment = urldefrag(urljoin(base, reference))
        resource = self.resources.get(identity)
        if resource is None:
            raise ValueError("unresolved local reference")
        if re.search(r"%(?![0-9A-Fa-f]{2})", fragment):
            raise ValueError("invalid reference encoding")
        fragment = unquote(fragment, encoding="utf-8", errors="strict")
        if not fragment:
            target = resource
        elif fragment.startswith("/"):
            tokens = fragment[1:].split("/")
            if any(re.search(r"~(?:[^01]|$)", token) for token in tokens):
                raise ValueError("invalid JSON pointer escape")
            path = tuple(token.replace("~1", "/").replace("~0", "~") for token in tokens)
            target = Location(resource.document, resource.path + path)
        else:
            target = self.anchors.get((identity, fragment))
        if target not in self.nodes:
            raise ValueError("unresolved local fragment or non-schema target")
        return target

    def exports(self, roots, visibility):
        if not roots or len(set(roots)) != len(roots) or visibility not in _VISIBILITY:
            raise ValueError("invalid consumer roots or visibility")
        exports = []
        for identity in roots:
            if identity not in self.documents:
                raise ValueError("unregistered consumer root")
            root = Location(identity)
            value = self.documents[identity]
            definitions = [
                Location(identity, (key, name)) for key in ("$defs", "definitions")
                for name in value.get(key, {})
            ]
            exports.extend(definitions)
            if not definitions or set(value).difference(_ANNOTATIONS):
                exports.append(root)
        self.closure(exports, visibility)
        return tuple(exports)

    def closure(self, roots, visibility):
        pending, visited = list(roots), set()
        while pending:
            location = pending.pop()
            if location in visited:
                continue
            value, _, exposure = self.nodes[location]
            if _VISIBILITY[exposure] > _VISIBILITY[visibility]:
                raise ValueError("consumer visibility violation")
            visited.add(location)
            if location in self.references:
                pending.append(self.references[location])
            if isinstance(value, dict):
                pending.extend(
                    Location(location.document, location.path + path)
                    for path, _ in _children(value) if path[0] not in _DEFINITIONS
                )
        return frozenset(visited)

    def rewrite(self, identity, encode_reference):
        return self.rewrite_node(Location(identity), encode_reference)

    def rewrite_node(self, location, encode_reference):
        value, _, _ = self.nodes[location]
        if type(value) is bool:
            return value
        output = copy.deepcopy(value)
        for key in ("$id", "$anchor", "x-docsuri-visibility"):
            output.pop(key, None)
        if location in self.references:
            output["$ref"] = encode_reference(self.references[location])
        for path, _ in _children(value):
            child = self.rewrite_node(
                Location(location.document, location.path + path), encode_reference
            )
            if len(path) == 1:
                output[path[0]] = child
            elif path[0] in _ARRAYS:
                output[path[0]][int(path[1])] = child
            else:
                output[path[0]][path[1]] = child
        return output

    def consumer_roots(self, name):
        consumer = self.consumers.get(name)
        if not isinstance(consumer, dict) or set(consumer) != {"visibility", "roots"}:
            raise ValueError("unregistered consumer")
        self.exports(consumer["roots"], consumer["visibility"])
        return tuple(consumer["roots"])


def _safe_relative(value):
    if not isinstance(value, str) or not value or len(value) > 4096 or "\\" in value:
        raise ValueError("invalid schema path")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or path.as_posix() != value or value == ".":
        raise ValueError("schema path escape or alias")
    return path


def load_catalog(root: Path) -> Catalog:
    root = root.resolve(strict=True)
    manifest = parse_json(_read_source(root / "schema-catalog.json"))
    if (
        not isinstance(manifest, dict)
        or set(manifest) != {"version", "excludedDirectories", "resources", "consumers"}
        or type(manifest["version"]) not in (int, float) or manifest["version"] != 1
    ):
        raise ValueError("unsupported schema catalog manifest")
    excluded = set()
    for entry in manifest["excludedDirectories"]:
        path = _safe_relative(entry["path"])
        if len(path.parts) != 1 or not isinstance(entry.get("reason"), str) or not entry["reason"]:
            raise ValueError("invalid schema inventory exclusion")
        excluded.add(path.as_posix())
    declared = {}
    for entry in manifest["resources"]:
        if not isinstance(entry, dict) or set(entry) != {"id", "path", "visibility"}:
            raise ValueError("invalid schema resource declaration")
        path = _safe_relative(entry["path"])
        if path.as_posix() in declared or path.parts[0] in excluded or path.suffix != ".json":
            raise ValueError("duplicate or excluded schema path")
        declared[path.as_posix()] = entry
    discovered = set()
    for directory, names, files in os.walk(root, followlinks=False):
        names[:] = sorted(name for name in names if Path(directory) != root or name not in excluded)
        if any((Path(directory) / name).is_symlink() for name in names):
            raise ValueError("schema directory symlink")
        for name in files:
            if (Path(directory) / name).is_symlink():
                raise ValueError("schema inventory symlink")
            if name.endswith(".schema.json"):
                path = Path(directory) / name
                discovered.add(path.relative_to(root).as_posix())
                if len(discovered) > 1000:
                    raise ValueError("schema inventory limit")
    if discovered != set(declared):
        raise ValueError("schema inventory mismatch")
    documents, visibility, paths = [], {}, {}
    total = 0
    for relative in sorted(declared):
        entry = declared[relative]
        raw = _read_source(root / relative)
        total += len(raw)
        if total > 64 * 1024**2:
            raise ValueError("schema catalog byte limit")
        document = parse_json(raw)
        if not isinstance(document, dict) or document.get("$id") != entry["id"]:
            raise ValueError("schema identity differs from manifest")
        documents.append(document)
        visibility[entry["id"]] = entry["visibility"]
        paths[entry["id"]] = relative
    catalog = Catalog(
        documents, visibility=visibility, paths=paths, consumers=manifest["consumers"]
    )
    covered = set()
    for name in catalog.consumers:
        covered.update(catalog.consumer_roots(name))
    if covered != set(catalog.documents):
        raise ValueError("unclassified schema consumer coverage")
    return catalog
