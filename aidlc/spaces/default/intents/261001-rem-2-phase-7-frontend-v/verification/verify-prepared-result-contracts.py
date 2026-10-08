"""Validate persisted C2 fixtures and their original-defect regression sensitivity.

Run from the workspace root in an isolated environment with pyyaml, jsonschema
and pydantic. Only synthetic DTOs and local schemas are loaded; no artifact,
application, database or runtime configuration is written.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

ROOT = Path(__file__).resolve().parents[6]
RECORD = Path(__file__).resolve().parent.parent
DOCUMENT = RECORD / "inception/contract-design/contract-summary.md"
ARCHIVE = RECORD / "archive/2026-10-05T14-45-11Z-contract-design/contract-summary.md"
sys.path[:0] = [
    str(ROOT / "backend/modules/summarization/src"),
    str(ROOT / "shared/python/src"),
]

from summarization.domain.models import SummaryDraft, SummaryResultDTO, Task


def yaml_blocks(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8")
    if "\ufffd" in text:
        raise ValueError(f"Replacement character in {path.name}")
    blocks = [
        yaml.safe_load(block)
        for block in re.findall(r"```yaml\n(.*?)\n```", text, re.S)
    ]
    if not all(isinstance(block, dict) for block in blocks):
        raise ValueError("Every YAML block must be a mapping")
    return blocks


def validator(spec: dict) -> Draft202012Validator:
    base = DOCUMENT.as_uri()
    resources = [(base, Resource(contents=spec, specification=DRAFT202012))]
    for name in ("summarization", "docmodel"):
        path = ROOT / f"shared/dtos/{name}.schema.json"
        schema = json.loads(path.read_text(encoding="utf-8"))
        resource = Resource.from_contents(schema)
        resources.extend(((path.as_uri(), resource), (schema["$id"], resource)))
    registry = Registry().with_resources(resources)
    for schema in spec["components"]["schemas"].values():
        Draft202012Validator.check_schema(schema)
    return Draft202012Validator(
        {"$ref": base + "#/components/schemas/ResultResponse"},
        registry=registry,
        format_checker=FormatChecker(),
    )


def require_rejection(check: Draft202012Validator, envelope: dict, label: str) -> None:
    if not list(check.iter_errors(envelope)):
        raise AssertionError(f"Invalid complete envelope accepted: {label}")


def main() -> None:
    blocks = yaml_blocks(DOCUMENT)
    archived = yaml_blocks(ARCHIVE)
    spec = next(block for block in blocks if "openapi" in block)
    old_spec = next(block for block in archived if "openapi" in block)
    summary = next(block for block in blocks
                   if block.get("contract-fixtures") == "prepared-summary-v1")
    translation = next(block for block in blocks
                       if block.get("contract-fixtures") == "prepared-translation-v1")
    expected_spec = copy.deepcopy(old_spec)
    properties = expected_spec["components"]["schemas"]["SummaryContent"]["properties"]["summary"]["properties"]
    properties["reproducibility"] = {
        "$ref": "../../../../../../../shared/dtos/summarization.schema.json#/$defs/Reproducibility"
    }
    if spec != expected_spec:
        raise AssertionError("OpenAPI changed outside the authorized reproducibility property")
    if [block for block in blocks if block is not spec and block is not summary] != [
        block for block in archived if block is not old_spec
    ]:
        raise AssertionError("An existing non-OpenAPI YAML contract or fixture changed")
    current = validator(spec)
    positive = summary["validEnvelope"]
    actual_content = SummaryResultDTO(
        task=Task.SUMMARY,
        summary=SummaryDraft(
            tldr="Synthetic summary",
            contributions=("Synthetic contribution",),
            method="Synthetic method",
            results="Synthetic result",
            limitations="Synthetic limitation",
            reproducibility={
                "code": "Synthetic code availability",
                "data": "Synthetic data availability",
            },
            anchors=(),
        ),
    ).to_dict()
    if positive["preparedResult"]["content"] != actual_content:
        raise AssertionError("Persisted positive fixture differs from the actual safe summary DTO")
    current.validate(positive)
    for index, replacement in enumerate(summary["rejectReproducibilityReplacements"], 1):
        candidate = copy.deepcopy(positive)
        candidate["preparedResult"]["content"]["summary"]["reproducibility"] = replacement
        require_rejection(current, candidate, f"summary substitution {index}")
    original = validator(old_spec)
    require_rejection(original, positive, "original contract with actual summary object")
    flattened = copy.deepcopy(positive)
    flattened["preparedResult"]["content"]["summary"]["reproducibility"] = "Flattened legacy text"
    original.validate(flattened)

    translation_positive = translation["validEnvelope"]
    current.validate(translation_positive)
    for index, replacement in enumerate(translation["rejectDocModelReplacements"], 1):
        candidate = copy.deepcopy(translation_positive)
        candidate["preparedResult"]["content"]["translation"]["docModel"] = replacement
        require_rejection(current, candidate, f"translation substitution {index}")
    malformed = copy.deepcopy(translation_positive)
    del malformed["preparedResult"]["content"]["translation"]["docModel"]["meta"]["provenance"]
    require_rejection(current, malformed, "translation missing provenance")
    legacy_translation_spec = copy.deepcopy(spec)
    docmodel = legacy_translation_spec["components"]["schemas"]["TranslationContent"]["properties"]["translation"]["properties"]["docModel"]
    docmodel["$ref"] = docmodel["$ref"].split("#")[0]
    legacy_translation = validator(legacy_translation_spec)
    require_rejection(legacy_translation, translation_positive, "original root DocModel reference")
    for replacement in translation["rejectDocModelReplacements"][:3]:
        candidate = copy.deepcopy(translation_positive)
        candidate["preparedResult"]["content"]["translation"]["docModel"] = replacement
        legacy_translation.validate(candidate)

    print(json.dumps({
        "contract_sha256": hashlib.sha256(DOCUMENT.read_bytes()).hexdigest(),
        "archive_sha256": hashlib.sha256(ARCHIVE.read_bytes()).hexdigest(),
        "yaml_blocks_parsed": len(blocks),
        "openapi_change_limited_to_reproducibility": True,
        "existing_yaml_contracts_preserved": True,
        "actual_summary_dto_fixture_matches": True,
        "positive_complete_envelopes_passed": 2,
        "negative_summary_envelopes_rejected": len(summary["rejectReproducibilityReplacements"]),
        "negative_translation_envelopes_rejected": len(translation["rejectDocModelReplacements"]) + 1,
        "both_original_schema_defects_reproduced": True,
        "application_or_operational_acceptance": False,
    }))


if __name__ == "__main__":
    main()
