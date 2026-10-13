"""The U7 local operator CLI: one stdin/stdout JSON envelope per invocation.

Every effect-bearing request is validated against C10's wire types, admitted
only through the retained-inventory vocabulary, bound and settled through the
guarded store, and answered with the C10 error vocabulary. The actor is always
derived from the local OS user, never from the request. Reads create no effect.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

from . import enums
from .errors import (
    DEPENDENCY_UNAVAILABLE,
    FORBIDDEN,
    INVALID_INPUT,
    POLICY_UNRESOLVED,
    ControlError,
)
from .profile import ENVIRONMENT_FILE, PlatformProfile
from .store import Store

OPS = (
    "inspectEvidence",
    "executeControlled",
    "readReceipt",
    "provisionAuthority",
    "revokeAuthority",
    "provisionTarget",
    "recordEvidence",
    "reconcile",
    "status",
)

_UNSAFE = re.compile(r"[\s;|&`$(){}<>\\\"'*]|\.\.")


def _unsafe(value: str) -> bool:
    return bool(_UNSAFE.search(value))


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _emit(payload: dict[str, Any]) -> None:
    """Write exactly one JSON document to stdout; the operator's only output."""
    sys.stdout.write(json.dumps(payload, sort_keys=True))


def effect_token(target: str, input_hash: str, idempotency_key: str) -> str:
    """A deterministic, path-free effect token derived from the operation identity."""
    return _sha256(f"{target}:{input_hash}:{idempotency_key}")[:16]


def environment_binding(profile: PlatformProfile, override: str | None = None) -> str:
    if override is not None:
        if not override or len(override) > 256:
            raise ControlError(INVALID_INPUT, "invalid environment binding")
        return override
    return f"synthetic-local:{profile.run_id}"


def _wire() -> Any:
    try:
        from docsuri_shared.workspace import execution
    except ImportError as exc:  # pragma: no cover - shared bindings absent
        raise ControlError(
            DEPENDENCY_UNAVAILABLE, "shared contract bindings are unavailable"
        ) from exc
    return execution


def _validate(model_name: str, request: Any) -> Any:
    from pydantic import ValidationError

    model = getattr(_wire(), model_name)
    try:
        return model.model_validate(request)
    except ValidationError as exc:
        fields = sorted({str(err["loc"][0]) for err in exc.errors() if err.get("loc")})
        raise ControlError(
            INVALID_INPUT,
            "request does not conform to the C10 wire type",
            details={"fieldNames": fields},
        ) from exc


def _principal(request: dict[str, Any], actor: str) -> str:
    principal = (request.get("context") or {}).get("principal") or {}
    if principal.get("kind") != "operator":
        raise ControlError(FORBIDDEN, "an application principal is not a platform operator")
    if principal.get("actorId") != actor:
        raise ControlError(FORBIDDEN, "operator actor substitution refused")
    authority_ref = principal.get("authorityRef")
    if not isinstance(authority_ref, str) or not authority_ref:
        raise ControlError(FORBIDDEN, "missing operator authority reference")
    return authority_ref


def _idempotency(request: dict[str, Any]) -> str:
    key = (request.get("context") or {}).get("idempotencyKey")
    if not isinstance(key, str) or not (1 <= len(key) <= 128):
        raise ControlError(INVALID_INPUT, "executeControlled requires an idempotency key")
    return key


def _parse_evidence_generation(value: Any) -> int:
    """A non-numeric or non-positive generation is INVALID_INPUT, never a store error."""
    from . import evidence as evidence_module

    return evidence_module.parse_generation(value)


def project_receipt(internal: dict[str, Any]) -> dict[str, Any]:
    """Project the internal receipt onto C10's ``OperatorReceipt``."""
    state = internal.get("operationState", enums.STATE_AUTHORIZED)
    return {
        "operationId": str(internal["operationId"]),
        "receiptId": str(internal["receiptId"]),
        "targetId": str(internal["targetId"]),
        "inputHash": str(internal["inputHash"]),
        "authorityRef": str(internal["authorityRef"]),
        "evidenceId": str(internal["evidenceId"]),
        "revision": str(internal["revision"]),
        "outcome": enums.wire_outcome(state),
        "effectRefs": [str(ref) for ref in internal.get("effectRefs", [])],
        "reconciliationEvidence": [
            str(item) for item in internal.get("reconciliationEvidence", [])
        ],
    }


def _response(model_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    return _validate(model_name, payload).model_dump(mode="json")


# --- operations -------------------------------------------------------------


def _inspect_evidence(
    request: dict[str, Any], actor: str, profile: PlatformProfile, store: Store
) -> dict[str, Any]:
    from . import evidence as evidence_module

    _validate("OperatorEvidenceRequest", request)
    authority_ref = _principal(request, actor)
    target = str(request["targetId"])
    if _unsafe(target):
        raise ControlError(INVALID_INPUT, "target identity contains an unsafe value")
    required = evidence_module.parse_generation(request["requiredGeneration"])
    # the store function enforces target-scope bounding internally
    current = store.latest_evidence(actor, authority_ref, target)
    internal, checks = evidence_module.classify(
        evidence=current,
        target=target,
        input_hash=str(request["inputHash"]),
        environment=environment_binding(profile),
        required_generation=required,
    )
    projected = evidence_module.to_wire_evidence(
        evidence=current,
        target=target,
        input_hash=str(request["inputHash"]),
        required_generation=required,
        internal=internal,
        checks=checks,
    )
    return _response("OperatorEvidence", projected)


def _execute_controlled(
    request: dict[str, Any], actor: str, profile: PlatformProfile, store: Store
) -> dict[str, Any]:
    from .executor import run_effect
    from .inventory import load_inventory

    _validate("OperatorExecuteRequest", request)
    authority_ref = _principal(request, actor)
    operation = str(request["operation"])
    target = str(request["targetId"])
    if _unsafe(operation) or _unsafe(target):
        raise ControlError(INVALID_INPUT, "raw command, path or shell input is not admissible")
    protocol = load_inventory().by_name(operation)
    if protocol is None or not protocol.is_executable:
        raise ControlError(POLICY_UNRESOLVED, "operation is not an admitted retained protocol")
    key = _idempotency(request)
    token = effect_token(target, str(request["inputHash"]), key)
    binding = store.begin_operation(
        actor=actor,
        authority_id=authority_ref,
        operation=operation,
        target=target,
        input_hash=str(request["inputHash"]),
        environment=        environment_binding(profile),
        evidence_id=str(request["evidenceId"]),
        generation=_parse_evidence_generation(request["evidenceGeneration"]),
        idempotency_key=key,
        effect_reference=f"{target}/effect-{token}.json",
    )
    if binding.get("replayed"):
        return _response("OperatorReceipt", project_receipt(binding))
    store.mark_executing(str(binding["operationId"]))
    outcome = run_effect(
        target_root=profile.target_root,
        operation_id=str(binding["operationId"]),
        operation_name=operation,
        target_id=target,
        token=token,
        effect_kind=protocol.effect_kind,
        input_hash=str(request["inputHash"]),
        deadline_seconds=protocol.deadline_seconds,
    )
    settle_outcome, disposition, refs = outcome.as_receipt_fields()
    settled = store.settle_operation(
        operation_id=str(binding["operationId"]),
        outcome=settle_outcome,
        disposition=disposition,
        effect_refs=refs,
    )
    return _response("OperatorReceipt", project_receipt(settled))


def _read_receipt(
    request: dict[str, Any], actor: str, profile: PlatformProfile, store: Store
) -> dict[str, Any]:
    from .reconciler import promote_stale, reconcile_unknown

    _validate("OperatorReceiptRequest", request)
    authority_ref = _principal(request, actor)
    operation_id = str(request["operationId"])
    # a receipt read promotes any over-deadline in-flight operation to unknown
    # before it is returned, so an interrupted effect is never shown in flight.
    promote_stale(store)
    receipt = store.read_receipt(actor, authority_ref, operation_id)
    receipt = reconcile_unknown(store, profile.target_root, operation_id, actor, authority_ref)
    return _response("OperatorReceipt", project_receipt(receipt))


def _provision_authority(
    request: dict[str, Any], actor: str, store: Store
) -> dict[str, Any]:
    from .authority import explicit_scope
    from .inventory import load_inventory

    scope = explicit_scope(list(request.get("scope") or []))
    operations = list(request.get("operations") or [])
    authority_class = request.get("authorityClass")
    if authority_class not in enums.AUTHORITY_CLASSES:
        raise ControlError(INVALID_INPUT, "invalid authority class")
    if authority_class != enums.CLASS_READER:
        known = set(load_inventory().admitted_names())
        if not operations or any(op not in known for op in operations):
            raise ControlError(INVALID_INPUT, "operation is not a retained executable protocol")
    authority_id = request.get("authorityId")
    if not isinstance(authority_id, str) or not authority_id:
        raise ControlError(INVALID_INPUT, "provisionAuthority requires an authorityId")
    return store.provision_authority(
        authority_id=authority_id,
        actor=actor,
        scope=list(scope),
        operations=operations,
        authority_class=authority_class,
        binding=dict(request.get("binding") or {}),
    )


def _record_evidence(
    request: dict[str, Any], profile: PlatformProfile, store: Store
) -> dict[str, Any]:
    target = str(request.get("targetId", ""))
    input_hash = str(request.get("inputHash", ""))
    if _unsafe(target) or not re.fullmatch(r"[0-9a-f]{64}", input_hash):
        raise ControlError(INVALID_INPUT, "recordEvidence requires a valid target and input digest")
    max_age = request.get("maxAgeSeconds")
    if not isinstance(max_age, int) or max_age <= 0:
        raise ControlError(INVALID_INPUT, "recordEvidence requires a finite maxAgeSeconds")
    observations = dict(request.get("observations") or {"status": "observed"})
    return store.record_evidence(
        target=target,
        input_hash=input_hash,
        environment=environment_binding(profile, request.get("environment")),
        observations=observations,
        max_age_seconds=max_age,
    )


# --- dispatch ---------------------------------------------------------------


def dispatch(op: str, request: dict[str, Any], profile: PlatformProfile) -> dict[str, Any]:
    from .authority import local_actor
    from .observations import status_summary
    from .reconciler import reconcile_unknown

    actor = local_actor()
    if op in ("provisionAuthority", "revokeAuthority", "provisionTarget"):
        store = Store.provisioner(profile)
        if op == "provisionAuthority":
            return _provision_authority(request, actor, store)
        if op == "revokeAuthority":
            authority_id = request.get("authorityId")
            if not isinstance(authority_id, str) or not authority_id:
                raise ControlError(INVALID_INPUT, "revokeAuthority requires an authorityId")
            return store.revoke_authority(authority_id)
        target = str(request.get("targetId", ""))
        if _unsafe(target):
            raise ControlError(INVALID_INPUT, "invalid target identity")
        return store.provision_target(target)

    store = Store.runtime(profile)
    if op == "inspectEvidence":
        return _inspect_evidence(request, actor, profile, store)
    if op == "executeControlled":
        return _execute_controlled(request, actor, profile, store)
    if op == "readReceipt":
        return _read_receipt(request, actor, profile, store)
    if op == "recordEvidence":
        return _record_evidence(request, profile, store)
    if op == "reconcile":
        from .reconciler import promote_stale

        operation_id = request.get("operationId")
        if not isinstance(operation_id, str) or not operation_id:
            raise ControlError(INVALID_INPUT, "reconcile requires an operationId")
        authority_ref = _principal(request, actor)
        promote_stale(store)
        return reconcile_unknown(store, profile.target_root, operation_id, actor, authority_ref)
    if op == "status":
        # the operator-facing view is bounded to the caller's authority scope
        authority_ref = _principal(request, actor)
        return status_summary(store, actor, authority_ref)
    raise ControlError(INVALID_INPUT, "unknown operator request")


def run(document: dict[str, Any], profile: PlatformProfile) -> tuple[dict[str, Any], int]:
    op = document.get("op")
    request = document.get("request") or {}
    if op not in OPS:
        error = ControlError(INVALID_INPUT, "unknown operator operation")
        return {"ok": False, "op": op, "error": error.as_wire_error()}, 1
    try:
        result = dispatch(str(op), request, profile)
    except ControlError as exc:
        return {"ok": False, "op": op, "error": exc.as_wire_error()}, 1
    return {"ok": True, "op": op, "result": result}, 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="U7 local controlled-operator envelope")
    parser.add_argument("--environment-file", type=Path, default=ENVIRONMENT_FILE)
    args = parser.parse_args(argv)
    raw = sys.stdin.buffer.read(1 << 20)
    try:
        document = json.loads(raw)
    except ValueError:
        error = ControlError(INVALID_INPUT, "invalid envelope")
        _emit({"ok": False, "op": None, "error": error.as_wire_error()})
        return 2
    try:
        profile = PlatformProfile.load(args.environment_file)
    except (OSError, ValueError) as exc:
        error = ControlError(DEPENDENCY_UNAVAILABLE, f"synthetic environment unavailable: {exc}")
        _emit({"ok": False, "op": document.get("op"), "error": error.as_wire_error()})
        return 2
    try:
        response, status = run(document, profile)
    except Exception as exc:  # noqa: BLE001 - the CLI boundary must still emit one JSON error
        error = ControlError(DEPENDENCY_UNAVAILABLE, f"operator failure: {type(exc).__name__}")
        _emit({"ok": False, "op": document.get("op"), "error": error.as_wire_error()})
        return 1
    _emit(response)
    return status


if __name__ == "__main__":
    raise SystemExit(main())
