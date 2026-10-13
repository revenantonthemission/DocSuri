"""The bounded executor: run one native effect in a contained child process.

The parent never infers success from a child's exit status: the typed settlement
record the child writes to stdout is the only signal, and a missing, invalid or
contradictory record settles ``unknown`` (never ``completed``). A deadline kills
the child and settles ``unknown`` for reconciliation.
"""

from __future__ import annotations

import json
import os
import resource
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

MAX_RESULT_BYTES = 65536
DEFAULT_ADDRESS_SPACE_BYTES = 512 * 1024 * 1024

STATUS_APPLIED = "applied"
STATUS_NOT_APPLIED = "not-applied"
STATUS_UNKNOWN = "unknown"


@dataclass(frozen=True)
class EffectOutcome:
    status: str
    effect_refs: list[str] = field(default_factory=list)
    error: dict[str, Any] | None = None
    reason: str = ""

    def as_receipt_fields(self) -> tuple[str, str, list[str]]:
        """Map onto (outcome, effect_disposition, effect_refs) for settlement."""
        if self.status == STATUS_APPLIED:
            return "completed", "applied", self.effect_refs
        if self.status == STATUS_NOT_APPLIED:
            return "failed", "not-applied", []
        return "unknown", "unknown", []


def _limit_resources(address_space: int) -> None:  # pragma: no cover - child preexec
    try:
        resource.setrlimit(resource.RLIMIT_AS, (address_space, address_space))
        resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
    except (ValueError, OSError):
        pass


def run_effect(
    *,
    target_root: Path,
    operation_id: str,
    operation_name: str,
    target_id: str,
    token: str,
    effect_kind: str,
    input_hash: str,
    deadline_seconds: int,
    injected_fault: str | None = None,
    address_space_bytes: int = DEFAULT_ADDRESS_SPACE_BYTES,
) -> EffectOutcome:
    request = {
        "operationId": operation_id,
        "operationName": operation_name,
        "targetId": target_id,
        "token": token,
        "effectKind": effect_kind,
        "inputHash": input_hash,
        "targetRoot": str(target_root),
    }
    if injected_fault is not None:
        request["injectedFault"] = injected_fault
    environment = {
        name: os.environ[name]
        for name in ("PATH", "LANG", "LC_ALL", "TMPDIR")
        if name in os.environ
    }
    try:
        child = subprocess.Popen(
            [sys.executable, "-m", "docsuri_ops.platform_control.native_adapter"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=environment,
            cwd=str(target_root.parent),
            preexec_fn=lambda: _limit_resources(address_space_bytes),
        )
    except OSError as exc:  # the host could not spawn the effect
        return EffectOutcome(STATUS_UNKNOWN, reason=f"executor unavailable: {exc}")

    try:
        stdout, _stderr = child.communicate(
            json.dumps(request).encode(), timeout=deadline_seconds
        )
    except subprocess.TimeoutExpired:
        child.kill()
        child.communicate()
        return EffectOutcome(STATUS_UNKNOWN, reason="deadline exceeded")
    except OSError as exc:  # pragma: no cover - pipe failure
        return EffectOutcome(STATUS_UNKNOWN, reason=f"executor channel failed: {exc}")

    if len(stdout) > MAX_RESULT_BYTES or not stdout.strip():
        return EffectOutcome(STATUS_UNKNOWN, reason="no settlement record")
    try:
        result = json.loads(stdout)
    except ValueError:
        return EffectOutcome(STATUS_UNKNOWN, reason="invalid settlement record")
    status = result.get("status")
    if status not in (STATUS_APPLIED, STATUS_NOT_APPLIED, STATUS_UNKNOWN):
        return EffectOutcome(STATUS_UNKNOWN, reason="unknown settlement status")
    if status == STATUS_APPLIED and child.returncode not in (0, None):
        # A successful effect must not contradict its own process exit.
        return EffectOutcome(STATUS_UNKNOWN, reason="effect and exit status disagree")
    refs = [ref for ref in result.get("effectRefs", []) if isinstance(ref, str)]
    return EffectOutcome(status, effect_refs=refs, error=result.get("error"))
