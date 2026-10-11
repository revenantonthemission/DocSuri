#!/usr/bin/env python3
"""Export canonical workspace schemas into the existing offline catalogue.

Browser and trusted execution shapes have one definition each. The existing
Python/TypeScript generators remain the only language-binding generators.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
SOURCE = (
    ROOT.parent
    / "aidlc/spaces/default/intents/261010-docsuri-v2-rebuild"
    / "inception/contract-design/contract-summary.md"
)
PUBLIC = "https://docsuri.dev/shared/dtos/workspace.schema.json"
INTERNAL = "https://docsuri.dev/shared/events/execution.schema.json"


def references(value):
    if isinstance(value, dict):
        if "$ref" in value:
            yield value["$ref"]
        for child in value.values():
            yield from references(child)
    elif isinstance(value, list):
        for child in value:
            yield from references(child)


def build() -> dict[Path, str]:
    source = SOURCE.read_text()
    blocks = [
        (kind, yaml.safe_load(body))
        for kind, body in re.findall(r"```yaml ([^\n]+)\n(.*?)\n```", source, re.S)
    ]
    definitions = next(value["$defs"] for kind, value in blocks if kind == "shared-schema")
    api = next(
        value
        for kind, value in blocks
        if kind == "openapi" and value["info"]["title"].startswith("DocSuri application")
    )
    public_names = set(api["components"]["schemas"])
    assert {"CommandContext", "ExecutionClaim", "DispatchCommand"}.isdisjoint(public_names)
    for name in public_names:
        assert all(
            reference.split("/")[-1] in public_names for reference in references(definitions[name])
        )

    def rewrite(value, public):
        if isinstance(value, dict):
            result = {}
            for key, item in value.items():
                if key == "$ref":
                    assert item.startswith("#/$defs/")
                    name = item.split("/")[-1]
                    destination = PUBLIC if name in public_names else INTERNAL
                    own = PUBLIC if public else INTERNAL
                    result[key] = ("" if destination == own else destination) + "#/$defs/" + name
                else:
                    result[key] = rewrite(item, public)
            return result
        if isinstance(value, list):
            return [rewrite(item, public) for item in value]
        return value

    outputs = {}
    for public, identity, relative in (
        (True, PUBLIC, "dtos/workspace.schema.json"),
        (False, INTERNAL, "events/execution.schema.json"),
    ):
        selected = {
            name: rewrite(copy.deepcopy(value), public)
            for name, value in definitions.items()
            if (name in public_names) == public
        }
        document = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": identity,
            "$comment": "Generated canonical contract release 2.0.0; source SHA256:"
            + hashlib.sha256(source.encode()).hexdigest(),
            "$defs": selected,
        }
        outputs[ROOT / relative] = json.dumps(document, indent=2, ensure_ascii=False) + "\n"
    return outputs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    for path, content in build().items():
        if args.check:
            if not path.is_file() or path.read_text() != content:
                raise SystemExit(f"canonical schema drift: {path.relative_to(ROOT)}")
        else:
            path.write_text(content)
    print(
        "Canonical public/internal schema partition verified"
        if args.check
        else "Exported canonical workspace schemas"
    )


if __name__ == "__main__":
    main()
