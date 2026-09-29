"""Synthetic owner observations for pure tests; no production authority or signing setup."""

from docsuri_platform_integrity.contracts.codec import canonical, digest
from docsuri_platform_integrity.contracts.models import (
    CurrentEvidenceContext,
    EvidenceCheck,
    EvidenceHeadSelection,
    SubjectSnapshot,
    ValidityWindow,
    VerificationAttestation,
    VerificationRequest,
)

D = digest(b"evidence-fixture")
SUBJECT = SubjectSnapshot(subject="unit", artifact=D, incarnation="install-1", policy=D)


def request(identity="verify-1", *, subject=SUBJECT, slot="schema"):
    return VerificationRequest(verification_id=identity, subject=subject, slot=slot, inputs=D)


def result(reservation, *, outcome="PASS", **fields):
    return VerificationAttestation(
        evidence_id=f"e-{reservation.request.verification_id}",
        subject=reservation.request.subject, slot=reservation.request.slot,
        revision=reservation.revision, verification_id=reservation.request.verification_id,
        outcome=outcome, validity=ValidityWindow(valid_from="0", valid_until="1000"), **fields,
    )


def selected(record):
    return EvidenceHeadSelection(
        subject=record.subject, slot=record.slot, revision=record.revision,
        verification_id=record.verification_id, state="RESOLVED", evidence_id=record.evidence_id,
    )


def verified_context(subject, records, *, exceptions=()):
    return CurrentEvidenceContext(
        subject=subject,
        checks=tuple(
            EvidenceCheck(
                evidence_id=record.evidence_id,
                record_digest=digest(canonical(record.model_dump(mode="json"))),
                status="VERIFIED", trust_ref=D,
                trust_validity=ValidityWindow(valid_from="0", valid_until="1000"),
            ) for record in records
        ),
        exceptions=exceptions,
    )
