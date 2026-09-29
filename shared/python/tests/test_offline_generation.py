"""F13: local-only refs and immutable consumer pinning."""

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def generator():
    spec = importlib.util.spec_from_file_location("binding_generator", ROOT / "tools/generate.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_python_local_absolute_reference_never_survives_staging(tmp_path):
    from docsuri_schema import load_catalog

    module = generator()
    module._stage_schemas(tmp_path)
    catalog = load_catalog(module.SHARED_ROOT)
    staged = {
        identity: json.loads((tmp_path / path).read_text())
        for identity, path in catalog.paths.items()
    }
    for location in catalog.references:
        value = staged[location.document]
        for part in location.path:
            value = value[int(part)] if isinstance(value, list) else value[part]
        assert not value["$ref"].startswith(("http:", "https:"))


def test_unknown_reference_fails_before_generator_or_publication(tmp_path):
    module = generator()
    source = tmp_path / "source"
    for group in module.SCHEMA_DIRS:
        (source / group).mkdir(parents=True)
    (source / "dtos/bad.schema.json").write_text(
        json.dumps({"$id": "https://local.test/bad", "$ref": "https://missing.test/remote"})
    )
    (source / "schema-catalog.json").write_text(json.dumps({
        "version": 1, "excludedDirectories": [],
        "resources": [{"id": "https://local.test/bad", "path": "dtos/bad.schema.json",
                       "visibility": "internal"}],
        "consumers": {"python": {"visibility": "internal", "roots": ["https://local.test/bad"]}},
    }))
    module.SHARED_ROOT = source
    with pytest.raises(ValueError, match="unresolved"):
        module._stage_schemas(tmp_path / "staged")


def test_import_namespace_is_pinned_to_managed_generation():
    import docsuri_shared._generated as generated

    head = json.loads((ROOT / "src/docsuri_shared/_binding_head.json").read_text())
    assert Path(generated.__path__[0]).name == head["generation"]
    assert Path(generated.__path__[0]).parent.name == "_binding_generations"


def test_unlisted_python_module_is_rejected(tmp_path, monkeypatch):
    import hashlib

    from docsuri_shared import _binding_loader

    files = {"__init__.py": hashlib.sha256(b"").hexdigest()}
    manifest = json.dumps(files, sort_keys=True, separators=(",", ":")).encode()
    generation = hashlib.sha256(manifest).hexdigest()
    directory = tmp_path / "_binding_generations" / generation
    directory.mkdir(parents=True)
    (directory / "__init__.py").write_bytes(b"")
    (tmp_path / "_binding_head.json").write_text(
        json.dumps({"generation": generation, "files": files})
    )
    monkeypatch.setattr(_binding_loader, "__file__", str(tmp_path / "_binding_loader.py"))
    assert _binding_loader.pinned_path() == str(directory)
    (directory / "unregistered.py").write_text("unexpected = True\n")
    with pytest.raises(ImportError, match="file set"):
        _binding_loader.pinned_path()


def test_one_generator_target_failure_preserves_published_generation(tmp_path, monkeypatch):
    module = generator()
    head = tmp_path / "head.json"
    original = b'{"generation":"known-good"}'
    head.write_bytes(original)
    monkeypatch.setattr(module, "HEAD", head)
    monkeypatch.setattr(module, "GENERATIONS", tmp_path / "generations")

    def partial_failure(output):
        output.mkdir(parents=True)
        (output / "first.py").write_text("completed_first_target = True\n")
        raise RuntimeError("second target failed")

    monkeypatch.setattr(module, "_build", partial_failure)
    with pytest.raises(RuntimeError, match="second target"):
        module.generate(announce=False)
    assert head.read_bytes() == original
    assert not module.GENERATIONS.exists()


def test_staged_json_pointer_preserves_literal_percent_in_definition_name(tmp_path, monkeypatch):
    module = generator()
    source = tmp_path / "source"
    (source / "dtos").mkdir(parents=True)
    identity = "https://schema.test/percent"
    (source / "dtos/percent.schema.json").write_text(json.dumps({
        "$id": identity, "$defs": {"%2F": {"type": "string"}}, "$ref": "#/$defs/%252F",
    }))
    (source / "schema-catalog.json").write_text(json.dumps({
        "version": 1, "excludedDirectories": [],
        "resources": [{"id": identity, "path": "dtos/percent.schema.json", "visibility": "public"}],
        "consumers": {"python": {"visibility": "internal", "roots": [identity]}},
    }))
    monkeypatch.setattr(module, "SHARED_ROOT", source)
    module._stage_schemas(tmp_path / "staged")
    staged = json.loads((tmp_path / "staged/dtos/percent.schema.json").read_text())
    assert staged["$ref"] == "#/$defs/%252F"
