"""Validate the declared supply-chain targets. Static check: no scanner, no network.

A declared image that is not pinned to an immutable digest is a mutable deployment input, so it
is rejected here. Image *findings* are deliberately not judged: CVE disposition is a separate,
explicitly-operator-gated concern, and folding it into this check would turn a known, tracked
finding into an untracked CI failure.

    python validate_supply_chain.py ops/platform-integrity/sbom-targets.json
"""

import json
import sys
from pathlib import Path

DIGEST_PREFIX = "@sha256:"


def image_references(targets: dict) -> dict[str, str]:
    """Flatten images/derivedImages/localDevImages into {logical_name: reference}.

    Entries are either a bare reference string or a dict carrying a ``digest`` key. derivedImages
    also carry ``base``, which names another entry, so bases are resolved to their own reference.

    ``localDevImages`` is included because it holds real, runnable image references. Leaving it out
    made a mutable tag there pass unnoticed: a developer could pin by hand in one place and drift in
    another. Non-production status stays a separate concern — this check judges pinning, not
    release relevance.
    """
    resolved: dict[str, str] = {}
    for section in ("images", "derivedImages", "localDevImages"):
        entries = targets.get(section) or {}
        if not isinstance(entries, dict):
            raise TypeError(f"{section} must be a mapping of name to reference")
        for name, value in entries.items():
            if name == "note":
                continue
            reference = value if isinstance(value, str) else (value or {}).get("digest", "")
            resolved[f"{section}.{name}"] = reference or ""
            if isinstance(value, dict) and value.get("base"):
                resolved[f"{section}.{name}.base"] = str(value["base"])
    return resolved


def unpinned_images(targets: dict) -> list[str]:
    """Return ``logical_name: reference`` for every reference lacking an immutable digest.

    A declared image with no reference at all is unpinned: absence of a pin is not a pass. A base
    name that merely points at another declared entry is a cross-reference, not a literal
    reference, so it is resolved through that entry instead of being reported here.
    """
    resolved = image_references(targets)
    names = {key.split(".")[-1] for key in resolved}
    unpinned = []
    for name, reference in sorted(resolved.items()):
        if DIGEST_PREFIX in reference:
            continue
        if reference and (reference in resolved or reference in names):
            # A pointer at another declared entry, not a literal reference.
            continue
        unpinned.append(f"{name}: {reference or '<no digest declared>'}")
    return unpinned


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    targets = json.loads(Path(argv[1]).read_bytes())
    references = image_references(targets)
    unpinned = unpinned_images(targets)
    if unpinned:
        for entry in unpinned:
            print(f"not digest-pinned: {entry}", file=sys.stderr)
        return 1
    print(f"all {len(references)} declared image references are digest-pinned")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
