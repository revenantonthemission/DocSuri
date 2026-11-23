"""A6's bounded child (U8 plan Step 27; the person's decision of 2026-10-25).

U8's `Operator` names this module through U7's executor seam (`run_effect`'s
`adapter_module`), so each of A6's effects runs under U7's deadline, resource limits and
settlement parsing. It reuses U7's request and settlement framing (`native_adapter.main`'s
`effect` seam):

- an unknown injected fault is refused, as U7's child refuses it;
- a kind outside A6's goes to U7's `apply_effect`, unchanged;
- for an A6 kind, U7's injected faults and its hang apply first, then U7's target and
  token checks, then the driver the effects root's `driver.json` names.
"""

from __future__ import annotations

import time
from pathlib import Path

from docsuri_ops.platform_control import native_adapter

from .effect_kinds import U8_EFFECT_KINDS

HANG_SECONDS = 60


def _driver_effect(request: dict) -> dict:
    """One of A6's effects: U7's target and token checks, then its driver."""
    try:
        directory, _ = native_adapter._resolve(
            Path(request["targetRoot"]), request["targetId"], request["token"]
        )
    except (ValueError, OSError, KeyError):
        return native_adapter._result(
            "not-applied", error=native_adapter._error("internal", "target not reachable")
        )
    from .drivers import apply

    return apply(request, directory)


def apply_effect(request: dict, *, injected_fault: str | None = None) -> dict:
    """Perform exactly one bounded effect; return a typed settlement record."""
    if injected_fault not in (None, *native_adapter.INJECTED_FAULTS):
        raise ValueError("unknown injected fault")
    if request.get("effectKind") not in U8_EFFECT_KINDS:
        return native_adapter.apply_effect(request, injected_fault=injected_fault)
    # U7's injected faults apply to A6's effects too, before the driver is reached.
    injected = native_adapter._injected(injected_fault)
    if injected is not None:
        return injected
    if injected_fault == "hang":
        time.sleep(HANG_SECONDS)
        return native_adapter._result(
            "unknown", error=native_adapter._error("internal", "injected hang")
        )
    return _driver_effect(request)


def main(argv: list[str] | None = None) -> int:
    return native_adapter.main(argv, effect=apply_effect)


if __name__ == "__main__":
    raise SystemExit(main())
