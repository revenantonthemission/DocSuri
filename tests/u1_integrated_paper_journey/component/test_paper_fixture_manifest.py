"""Fixture evidence cannot silently change identity or processing scope."""

from copy import deepcopy

import pytest

from scripts import load_docsuri_u1_papers as loader

pytestmark = pytest.mark.u1_component


def manifest():
    return {
        "runId": "owned",
        "purpose": "isolated-local-research",
        "publicRedistribution": False,
        "papers": [
            {
                "paper": paper,
                "version": version,
                "title": title,
                "sourceUrl": f"https://arxiv.org/html/{paper}v{version}",
                "sourceSha256": "a" * 64,
                "rawArtifact": {"sha256": "a" * 64},
            }
            for paper, version, title in loader.PAPERS
        ],
    }


def test_manifest_requires_exact_owned_paper_scope_and_processing_purpose():
    original = manifest()
    loader.validate_manifest(original, "owned")
    changes = [
        {"runId": "foreign"},
        {"purpose": "public"},
        {"publicRedistribution": True},
        {"papers": original["papers"][:1]},
        {"papers": original["papers"] * 2},
    ]
    for change in changes:
        with pytest.raises(ValueError, match="scope or custody"):
            loader.validate_manifest({**original, **change}, "owned")


def test_source_url_and_digest_cannot_be_substituted():
    for key, value in [("sourceUrl", "https://untrusted.invalid/"), ("sourceSha256", "b" * 64)]:
        changed = deepcopy(manifest())
        changed["papers"][0][key] = value
        with pytest.raises(ValueError, match="identity mismatch"):
            loader.validate_manifest(changed, "owned")


def test_parser_identity_binds_current_source_and_dependency_bytes(monkeypatch, tmp_path):
    # This pure hashing fault test avoids production fixture publication.
    paths = [
        tmp_path / "parser.py",
        tmp_path / "backend/modules/corpus/source_parser.py",
        tmp_path / "shared/python/src/docsuri_shared/docmodel_contract.py",
        tmp_path / "backend/uv.lock",
    ]
    monkeypatch.setattr(loader, "ROOT", tmp_path)
    monkeypatch.setattr(type(tmp_path), "glob", lambda self, pattern: [paths[0]])
    content = {str(path): b"initial" for path in paths}
    monkeypatch.setattr(type(tmp_path), "read_bytes", lambda self: content[str(self)])
    first = loader.parser_identity()
    content[str(paths[-1])] = b"dependency change"
    assert loader.parser_identity() != first
