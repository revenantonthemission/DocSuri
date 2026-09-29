"""Pure current-evidence selection. Stored assertions never establish current trust."""

from pydantic import TypeAdapter

from ..contracts.codec import canonical, digest
from ..contracts.models import (
    U64,
    CurrentEvidenceContext,
    EvidenceHeadSelection,
    GateDiagnostic,
    GateEvaluation,
    GateVerdict,
    Ref,
    SelectedRevision,
    SubjectSnapshot,
    VerificationAttestation,
    VerificationRequest,
    VerificationReservation,
)
from .supply_chain import exception_matches

_REF = TypeAdapter(Ref)
_REVISION = TypeAdapter(U64)


def reserve_selection(
    request: VerificationRequest, current: EvidenceHeadSelection | None, *, expected_revision: str
) -> VerificationReservation:
    _REVISION.validate_python(expected_revision, strict=True)
    observed = current.revision if current else "0"
    if observed != expected_revision or int(observed) == 2**64 - 1:
        raise ValueError("verification revision conflict or exhaustion")
    if current and (
        current.subject is None or current.verification_id is None
        or current.subject.subject != request.subject.subject or current.slot != request.slot
    ):
        raise ValueError("unbound or different verification scope")
    return VerificationReservation(
        request=request, revision=str(int(observed) + 1), previous_revision=observed
    )


def pending_selection(reservation: VerificationReservation) -> EvidenceHeadSelection:
    return EvidenceHeadSelection(
        subject=reservation.request.subject, slot=reservation.request.slot,
        verification_id=reservation.request.verification_id,
        revision=reservation.revision, state="PENDING",
    )


def resolve_selection(
    reservation: VerificationReservation, current: EvidenceHeadSelection,
    record: VerificationAttestation, *, existing: VerificationAttestation | None = None,
) -> EvidenceHeadSelection:
    """A late, correctly bound record remains history and cannot replace a newer selection."""
    expected = pending_selection(reservation)
    if (
        current.subject is None or current.verification_id is None
        or current.subject.subject != reservation.request.subject.subject
        or current.slot != reservation.request.slot
    ):
        raise ValueError("verification selection scope mismatch")
    if existing is not None and existing != record:
        raise ValueError("conflicting immutable verification result")
    if (
        record.subject != expected.subject or record.slot != expected.slot
        or record.revision != expected.revision
        or record.verification_id != expected.verification_id
    ):
        raise ValueError("verification result binding mismatch")
    if current == expected:
        if existing is not None:
            raise ValueError("published result has a pending selection")
        return current.model_copy(update={"state": "RESOLVED", "evidence_id": record.evidence_id})
    if current.revision == reservation.revision and existing is None:
        raise ValueError("terminal verification evidence missing")
    if current.revision == reservation.revision and (
        current.subject != expected.subject or current.slot != expected.slot
        or current.verification_id != expected.verification_id
        or current.state != "RESOLVED" or current.evidence_id != record.evidence_id
    ):
        raise ValueError("conflicting verification result")
    if int(current.revision) < int(reservation.revision):
        raise ValueError("verification head regression")
    return current


def evaluate(
    subject: SubjectSnapshot,
    required: tuple[str, ...],
    heads: tuple[EvidenceHeadSelection, ...],
    evidence: tuple[VerificationAttestation, ...],
    *,
    lower: int,
    upper: int,
    trusted: bool = False,
    current: CurrentEvidenceContext | None = None,
) -> GateEvaluation:
    """Observe a trusted policy's slots using fresh provider facts, never a cached PASS.

    Current context is supplied by protected read adapters, not by the request payload.
    Only safe diagnostic codes are projected; original producer reasons remain in history.
    """
    if (
        not required or len(required) > 100 or len(set(required)) != len(required)
        or len(heads) > 100 or len(evidence) > 100
    ):
        return GateEvaluation(
            verdict=GateVerdict.INCOMPLETE, reasons=("invalid_gate_inputs",), evidence_ids=()
        )
    for slot in required:
        _REF.validate_python(slot, strict=True)
    clock_ok = (
        trusted is True and type(lower) is int and type(upper) is int
        and 0 <= lower <= upper < 2**64
    )
    problems: set[tuple[str | None, str, GateVerdict]] = set()
    used, exception_ids, selections = set(), set(), []

    def note(slot, code, verdict):
        problems.add((slot, code, verdict))

    if not clock_ok:
        note(None, "clock_unavailable", GateVerdict.INCOMPLETE)
    if current is None:
        note(None, "current_evidence_unavailable", GateVerdict.INCOMPLETE)
    elif current.subject != subject:
        note(None, "current_subject_changed", GateVerdict.STALE)
    selected_heads = tuple(head for head in heads if head.slot in required)
    selected_ids = {head.evidence_id for head in selected_heads}
    selected_records = tuple(record for record in evidence if record.evidence_id in selected_ids)
    referenced_exceptions = {ref for record in selected_records for ref in record.exceptions}
    checks = tuple(c for c in current.checks if c.evidence_id in selected_ids) if current else ()
    exceptions = tuple(
        item for item in current.exceptions if item.exception.exception_id in referenced_exceptions
    ) if current else ()

    for slot in sorted(required):
        selected = [head for head in selected_heads if head.slot == slot]
        if len(selected) != 1:
            note(slot, "missing_or_conflicting_head", GateVerdict.INCOMPLETE)
            continue
        head = selected[0]
        selections.append(SelectedRevision(slot=slot, revision=head.revision))
        if head.subject is None or head.verification_id is None:
            note(slot, "unbound_selection", GateVerdict.INCOMPLETE)
            continue
        if head.subject != subject:
            note(slot, "selection_binding_changed", GateVerdict.STALE)
        if head.state != "RESOLVED":
            note(slot, "verification_pending", GateVerdict.INCOMPLETE)
            continue
        records = [record for record in selected_records if record.evidence_id == head.evidence_id]
        if len(records) != 1:
            note(slot, "missing_or_conflicting_evidence", GateVerdict.INCOMPLETE)
            continue
        record = records[0]
        used.add(record.evidence_id)
        exception_ids.update(record.exceptions)
        if (
            record.slot != slot or record.revision != head.revision or record.subject != subject
            or record.verification_id != head.verification_id
        ):
            note(slot, "evidence_binding_changed", GateVerdict.STALE)
            continue
        proof = [check for check in checks if check.evidence_id == record.evidence_id]
        if len(proof) != 1 or proof[0].record_digest != digest(
            canonical(record.model_dump(mode="json"))
        ):
            note(slot, "evidence_trust_unavailable", GateVerdict.INCOMPLETE)
            continue
        check = proof[0]
        if check.status in {"INVALID", "REVOKED"}:
            note(slot, "evidence_trust_rejected", GateVerdict.BLOCKED)
            continue
        if check.status != "VERIFIED" or check.trust_ref is None or check.trust_validity is None:
            note(slot, "evidence_trust_unavailable", GateVerdict.INCOMPLETE)
            continue
        if clock_ok and (
            not record.validity.contains(lower, upper)
            or not check.trust_validity.contains(lower, upper)
        ):
            note(slot, "evidence_or_trust_expired", GateVerdict.STALE)
        if record.outcome == "FAIL":
            note(slot, "verification_failed", GateVerdict.BLOCKED)
        elif record.outcome == "UNKNOWN":
            note(slot, "verification_incomplete", GateVerdict.INCOMPLETE)
        for identity in record.exceptions:
            matches = [item for item in exceptions if item.exception.exception_id == identity]
            if (
                len(matches) != 1 or record.closure is None or record.assumptions is None
                or matches[0].finding.severity == "unknown"
            ):
                note(slot, "exception_currentness_unavailable", GateVerdict.INCOMPLETE)
                continue
            item = matches[0]
            if not clock_ok:
                continue
            if (
                item.closure != record.closure or item.assumptions != record.assumptions
                or not exception_matches(
                    item.exception, item.finding, artifact=subject.artifact,
                    closure=item.closure, assumptions=item.assumptions, policy=subject.policy,
                    lower=lower, upper=upper, authorized=item.authorized, revoked=item.revoked,
                )
            ):
                note(slot, "exception_not_applicable", GateVerdict.BLOCKED)

    precedence = tuple(GateVerdict)
    verdict = min((item[2] for item in problems), key=precedence.index) if problems else (
        GateVerdict.EXCEPTIONS if exception_ids else GateVerdict.ELIGIBLE
    )
    window = (str(lower), str(upper)) if clock_ok else None
    # Sort by canonical bytes, including duplicate/conflict inputs, to make replay independent
    # of enumeration order. Unrelated history is deliberately outside the evaluation cut.
    def ordered(values):
        return sorted((value.model_dump(mode="json") for value in values), key=canonical)

    fingerprint = digest(canonical({
        "subject": subject.model_dump(mode="json"), "required": sorted(required),
        "heads": ordered(selected_heads), "evidence": ordered(selected_records),
        "current_subject": current.subject.model_dump(mode="json") if current else None,
        "checks": ordered(checks), "exceptions": ordered(exceptions),
        "window": list(window) if window else None,
    }))
    return GateEvaluation(
        verdict=verdict, reasons=tuple(sorted({item[1] for item in problems})),
        evidence_ids=tuple(sorted(used)), exception_ids=tuple(sorted(exception_ids)),
        diagnostics=tuple(
            GateDiagnostic(slot=slot, code=code)
            for slot, code, _ in sorted(problems, key=lambda item: (item[0] or "", item[1]))
        ),
        selections=tuple(selections), evaluation_window=window, input_fingerprint=fingerprint,
    )
