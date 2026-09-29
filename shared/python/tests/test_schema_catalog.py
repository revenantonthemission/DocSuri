"""F13 / PROP-R1-09: schema positions, local resource scope and literal-data preservation."""

import json
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from docsuri_schema import Catalog, load_catalog

ROOT = "https://schema.test/root"
CASES = json.loads((Path(__file__).resolve().parents[2] / "schema-conformance.json").read_text())


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["name"])
def test_shared_cross_language_conformance(case):
    def validate():
        catalog = Catalog(tuple(case["documents"]), visibility=case.get("visibility"))
        if "consumer" in case:
            catalog.exports(case["consumer"]["roots"], case["consumer"]["visibility"])
        for ref in case.get("references", []):
            resolved = catalog.resolve(ref["base"], ref["ref"])
            assert (resolved.document, resolved.pointer) == (ref["document"], ref["pointer"])
    if case["valid"]:
        validate()
    else:
        with pytest.raises(ValueError):
            validate()


def test_literals_and_schema_property_names_are_not_interpreted_as_keywords():
    literal = {"$id": "literal", "$ref": "https://not-a-schema.test/data", "$dynamicRef": "data"}
    document = {
        "$id": ROOT, "type": "object", "default": literal, "examples": [literal],
        "properties": {"$id": {"type": "string"}, "$ref": {"const": literal}},
    }
    catalog = Catalog((document,))
    rewritten = catalog.rewrite(ROOT, lambda _: "unused")
    assert rewritten["default"] == literal and rewritten["examples"] == [literal]
    assert rewritten["properties"]["$ref"]["const"] == literal
    assert rewritten["properties"]["$id"] == {"type": "string"}
    assert "$id" not in rewritten


def test_nested_resource_anchor_and_escaped_pointer_resolve_to_schema_locations():
    document = {
        "$id": ROOT,
        "$defs": {
            "A/B": {"$id": "child", "$anchor": "Entry", "type": "object",
                    "properties": {"next": {"$ref": "#Entry"}}},
            "ById": {"$ref": "child#Entry"},
            "ByPointer": {"$ref": "#/$defs/A~1B"},
        },
    }
    catalog = Catalog((document,))
    target = catalog.resolve(ROOT, "child#Entry")
    assert target.document == ROOT and target.path == ("$defs", "A/B")
    assert catalog.resolve(ROOT, "#/$defs/A~1B") == target
    rewritten = catalog.rewrite(ROOT, lambda location: "#" + location.pointer)
    assert rewritten["$defs"]["A/B"]["properties"]["next"]["$ref"] == "#/$defs/A~1B"


@pytest.mark.parametrize("fragment", ["#/$defs/A~2B", "#/examples/0", "#/%zz", "#/prefixItems/01"])
def test_invalid_pointer_or_literal_target_is_rejected(fragment):
    document = {
        "$id": ROOT, "$defs": {"A~2B": {}}, "examples": [{}],
        "prefixItems": [{}, {}], "allOf": [{"$ref": fragment}],
    }
    with pytest.raises(ValueError):
        Catalog((document,))


@pytest.mark.parametrize("document", [
    {"$id": ROOT, "$defs": {"a": {"$id": ROOT}}},
    {"$id": ROOT, "$defs": {"a": {"$anchor": "x"}, "b": {"$anchor": "x"}}},
    {"$id": ROOT, "$dynamicRef": "#x"},
    {"$id": ROOT, "$schema": "https://unsupported.test/schema"},
])
def test_ambiguous_or_unsupported_resources_fail_closed(document):
    with pytest.raises(ValueError):
        Catalog((document,))


def test_public_closure_cannot_include_internal_resource_or_definition():
    public = {"$id": ROOT, "$defs": {"Public": {"$ref": "internal"}}}
    internal = {"$id": "https://schema.test/internal", "type": "object"}
    catalog = Catalog((public, internal), visibility={ROOT: "public", internal["$id"]: "internal"})
    with pytest.raises(ValueError, match="visibility"):
        catalog.exports((ROOT,), "public")
    assert catalog.exports((ROOT, internal["$id"]), "internal")


@given(st.lists(st.integers(0, 5), min_size=1, max_size=6))
def test_recursive_reference_graph_matches_declared_edges(edges):
    count = len(edges)
    documents = tuple(
        {"$id": f"https://schema.test/{i}", "$ref": f"https://schema.test/{edge % count}"}
        for i, edge in enumerate(edges)
    )
    catalog = Catalog(documents)
    for i, edge in enumerate(edges):
        target = catalog.resolve(documents[i]["$id"], documents[i]["$ref"])
        assert target.document == documents[edge % count]["$id"]
    assert set(catalog.resources) == {document["$id"] for document in documents}


def test_manifest_inventory_detects_unregistered_missing_and_symlinked_sources(tmp_path):
    (tmp_path / "dtos").mkdir()
    schema = tmp_path / "dtos/one.schema.json"
    schema.write_text(json.dumps({"$id": ROOT, "type": "string"}))
    manifest = {
        "version": 1, "excludedDirectories": [],
        "resources": [{"id": ROOT, "path": "dtos/one.schema.json", "visibility": "public"}],
        "consumers": {"test": {"visibility": "public", "roots": [ROOT]}},
    }
    (tmp_path / "schema-catalog.json").write_text(json.dumps(manifest))
    assert load_catalog(tmp_path).consumer_roots("test") == (ROOT,)
    extra = tmp_path / "extra.schema.json"
    extra.write_text(json.dumps({"$id": "https://schema.test/extra"}))
    with pytest.raises(ValueError, match="inventory"):
        load_catalog(tmp_path)
    extra.unlink()
    schema.unlink()
    with pytest.raises(ValueError, match="inventory"):
        load_catalog(tmp_path)
    extra.write_text(json.dumps({"$id": ROOT}))
    schema.symlink_to(extra)
    with pytest.raises(ValueError):
        load_catalog(tmp_path)
