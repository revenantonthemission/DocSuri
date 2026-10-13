"""The retained controlled-operator protocol inventory and consumer matrix.

The inventory is the operation vocabulary (BR3.1): no operation outside it is
callable, and no generic command/path/shell is admissible. Every retained
protocol carries an explicit disposition (BR5.1/BR5.2); cloud- and
paid-dependent protocols are recorded dispositions, never runtime dependencies.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import enums

_INVENTORY_PATH = Path(__file__).with_name("inventory.json")


@dataclass(frozen=True)
class Protocol:
    name: str
    display_name: str
    disposition: str
    authority_class: str
    max_age_seconds: int
    deadline_seconds: int
    effect_kind: str
    native_verified: bool
    consumer: str
    consumer_impact: str
    notes: str

    @property
    def is_retained(self) -> bool:
        return self.disposition == enums.DISPOSITION_RETAINED

    @property
    def is_executable(self) -> bool:
        return self.is_retained and self.native_verified

    def as_row(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "disposition": self.disposition,
            "authority_class": self.authority_class,
            "max_age_seconds": self.max_age_seconds,
            "deadline_seconds": self.deadline_seconds,
            "effect_kind": self.effect_kind,
            "native_verified": self.native_verified,
            "consumer_impact": self.consumer_impact,
        }


@dataclass(frozen=True)
class Consumer:
    consumer: str
    legacy_surface: str
    compatibility: str
    notes: str


@dataclass(frozen=True)
class Inventory:
    version: int
    reconciled_from: tuple[str, ...]
    protocols: tuple[Protocol, ...]
    consumers: tuple[Consumer, ...]

    def by_name(self, name: str) -> Protocol | None:
        for protocol in self.protocols:
            if protocol.name == name:
                return protocol
        return None

    def retained(self) -> tuple[Protocol, ...]:
        return tuple(p for p in self.protocols if p.is_retained)

    def admitted_names(self) -> tuple[str, ...]:
        return tuple(p.name for p in self.retained())


def _require(value: Any, field: str, expected_type: type) -> Any:
    if not isinstance(value, expected_type):
        raise ValueError(f"inventory field {field!r} has wrong type")
    return value


def load_inventory(path: Path | None = None) -> Inventory:
    """Load and validate the packaged inventory; an unrecorded protocol is an error."""
    raw = json.loads((path or _INVENTORY_PATH).read_text(encoding="utf-8"))
    protocols = []
    seen: set[str] = set()
    for item in _require(raw.get("protocols"), "protocols", list):
        disposition = item.get("disposition")
        if disposition not in enums.PROTOCOL_DISPOSITIONS:
            raise ValueError(f"protocol {item.get('name')!r} has an unknown disposition")
        authority_class = item.get("authorityClass")
        if authority_class not in (enums.CLASS_ROUTINE, enums.CLASS_DESTRUCTIVE):
            raise ValueError(f"protocol {item.get('name')!r} has an invalid authority class")
        effect_kind = item.get("effectKind")
        if effect_kind not in enums.EFFECT_KINDS:
            raise ValueError(f"protocol {item.get('name')!r} has an invalid effect kind")
        name = _require(item.get("name"), "name", str)
        if name in seen:
            raise ValueError(f"duplicate protocol name {name!r}")
        seen.add(name)
        for numeric in ("maxAgeSeconds", "deadlineSeconds"):
            value = item.get(numeric)
            if not isinstance(value, int) or value <= 0:
                raise ValueError(f"protocol {name!r} needs a finite positive {numeric}")
        if not isinstance(item.get("nativeVerified"), bool):
            raise ValueError(f"protocol {name!r} needs an explicit nativeVerified flag")
        protocols.append(
            Protocol(
                name=name,
                display_name=item.get("displayName", name),
                disposition=disposition,
                authority_class=authority_class,
                max_age_seconds=item["maxAgeSeconds"],
                deadline_seconds=item["deadlineSeconds"],
                effect_kind=effect_kind,
                native_verified=item["nativeVerified"],
                consumer=item.get("consumer", "unknown"),
                consumer_impact=item.get("consumerImpact", ""),
                notes=item.get("notes", ""),
            )
        )
    consumers = tuple(
        Consumer(
            consumer=item["consumer"],
            legacy_surface=item.get("legacySurface", ""),
            compatibility=item.get("compatibility", "recorded-only"),
            notes=item.get("notes", ""),
        )
        for item in raw.get("consumers", [])
    )
    return Inventory(
        version=raw.get("version", 1),
        reconciled_from=tuple(raw.get("reconciledFrom", [])),
        protocols=tuple(protocols),
        consumers=consumers,
    )


def dispositions_summary(inventory: Inventory) -> dict[str, int]:
    """Count protocols per disposition so an unrecorded protocol is visible."""
    summary = {disposition: 0 for disposition in enums.PROTOCOL_DISPOSITIONS}
    for protocol in inventory.protocols:
        summary[protocol.disposition] += 1
    return summary
