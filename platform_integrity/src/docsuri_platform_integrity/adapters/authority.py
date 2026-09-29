"""Purpose-bound local operator grants. Caller mTLS identity alone grants no object access."""

from contextlib import contextmanager
from dataclasses import dataclass
from time import monotonic

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from pydantic import TypeAdapter

from ..contracts.codec import canonical, digest, verify
from ..contracts.models import (
    ApprovalBinding,
    CurrentEvidenceContext,
    EvidenceCheck,
    Ref,
    SubjectSnapshot,
    ValidityWindow,
    VerificationAttestation,
)

_REFERENCE = TypeAdapter(Ref)


class MutationUnavailable(PermissionError):
    pass


class DenyMutationAuthority:
    @contextmanager
    def guard(self, *args, **kwargs):
        # Deployable default until native source-revocation/commit proof has passed EV-R1-06.
        raise MutationUnavailable("native commit-guard capability not provisioned")
        yield  # pragma: no cover - contextmanager protocol, no effect path


@dataclass(frozen=True)
class ReadGrant:
    certificate_fingerprint: str
    subjects: frozenset[str]
    valid_until_us: int


class CurrentReadAuthority:
    def __init__(self, lookup, clock):
        # lookup is a readonly owner projection that must re-check revocation each call.
        self._lookup = lookup
        self._clock = clock

    def permits(self, fingerprint: str | None, subject: str) -> bool:
        if not fingerprint:
            return False
        try:
            grant = self._lookup(fingerprint)
            lower, upper = self._clock()
            return bool(
                grant
                and type(lower) is int and type(upper) is int
                and 0 <= lower <= upper < 2**64
                and type(grant.valid_until_us) is int and grant.valid_until_us < 2**64
                and grant.certificate_fingerprint == fingerprint
                and subject in grant.subjects
                and upper < grant.valid_until_us
            )
        except Exception:
            return False


def check_binding(
    binding: ApprovalBinding,
    *,
    target,
    plan,
    artifact,
    policy,
    purpose: str,
    revision: str,
    lower: int,
    upper: int,
    revoked: bool,
) -> None:
    if (
        revoked is not False
        or binding.purpose != purpose
        or type(lower) is not int or type(upper) is not int
        or not 0 <= lower <= upper < 2**64
        or binding.target != target
        or binding.plan != plan
        or binding.artifact != artifact
        or binding.policy != policy
        or binding.authority_revision != revision
        or not binding.validity.contains(lower, upper)
        or int(binding.validity.valid_until) - int(binding.validity.valid_from) > 1800 * 1_000_000
    ):
        raise PermissionError("current authority binding rejected")


@dataclass(frozen=True)
class EvidenceVerificationKey:
    """Owner-supplied CURRENT acceptance decision, not a signer's self-declared validity."""

    key_id: str
    public_key: Ed25519PublicKey
    subjects: frozenset[str]
    revision: str
    validity: ValidityWindow
    revoked: bool

    def __post_init__(self):
        _REFERENCE.validate_python(self.key_id, strict=True)
        _REFERENCE.validate_python(self.revision, strict=True)
        if (
            type(self.revoked) is not bool or not isinstance(self.public_key, Ed25519PublicKey)
            or not isinstance(self.validity, ValidityWindow)
            or not isinstance(self.subjects, frozenset) or len(self.subjects) > 100
        ):
            raise ValueError("invalid current evidence-key decision")
        for subject in self.subjects:
            _REFERENCE.validate_python(subject, strict=True)


class CurrentEvidenceVerifier:
    """Read-only signature/current-trust adapter. No fallback key or cached trust decisions.

    Callbacks are protected owner ports: registered evidence IDs resolve immutable envelopes;
    subject/key/exception observations come from current sources. The key port receives the
    exact record so historical acceptance can use protected publication provenance, not a
    signer's self-declared timestamp. These callbacks are not HTTP parameters.
    Production composition must provision those ports; an unavailable source cannot pass.
    """

    def __init__(self, observe_subject, load_envelope, current_key, current_exceptions=None):
        self._observe_subject = observe_subject
        self._load_envelope = load_envelope
        self._current_key = current_key
        self._current_exceptions = current_exceptions

    def _check(self, record: VerificationAttestation, deadline: float) -> EvidenceCheck:
        record_digest = digest(canonical(record.model_dump(mode="json")))
        status, trust_ref, validity = "UNKNOWN", None, None
        try:
            envelope = self._load_envelope(record.evidence_id)
            if monotonic() >= deadline:
                raise TimeoutError("evidence trust deadline")
            if not isinstance(envelope, dict) or not isinstance(envelope.get("keyId"), str):
                raise ValueError("invalid evidence envelope")
            _REFERENCE.validate_python(envelope["keyId"], strict=True)
            try:
                key = self._current_key(envelope["keyId"], record)
            except Exception:
                key = None
            if monotonic() >= deadline:
                raise TimeoutError("evidence trust deadline")
            if isinstance(key, EvidenceVerificationKey):
                trust_ref = digest(canonical({
                    "key": digest(key.public_key.public_bytes_raw()), "revision": key.revision,
                    "subjects": sorted(key.subjects),
                    "validity": key.validity.model_dump(mode="json"),
                    "revoked": key.revoked,
                }))
                validity = key.validity
                if key.revoked:
                    status = "REVOKED"
                elif key.key_id != envelope["keyId"] or record.subject.subject not in key.subjects:
                    status = "INVALID"
                else:
                    payload = verify(
                        envelope, kind="evidence", purpose="attest", key_id=key.key_id,
                        key=key.public_key,
                    )
                    status = "VERIFIED" if payload == record.model_dump(mode="json") else "INVALID"
        except (ValueError, TypeError, InvalidSignature):
            status = "INVALID"
        except Exception:
            # Source outages are uncertainty, not proof of either integrity or revocation.
            status = "UNKNOWN"
        return EvidenceCheck(
            evidence_id=record.evidence_id, record_digest=record_digest, status=status,
            trust_ref=trust_ref, trust_validity=validity,
        )

    def inspect(
        self, subject: SubjectSnapshot, records: tuple[VerificationAttestation, ...],
        *, deadline: float | None = None,
    ) -> CurrentEvidenceContext | None:
        deadline = min(deadline, monotonic() + 2.5) if deadline is not None else monotonic() + 2.5

        def within_budget():
            if monotonic() >= deadline:
                raise TimeoutError("evidence trust deadline")

        within_budget()
        if len(records) > 100:
            raise ValueError("evidence observation limit")
        try:
            observed = self._observe_subject(subject.subject)
        except Exception:
            return None
        if not isinstance(observed, SubjectSnapshot):
            return None
        within_budget()
        requested = tuple(sorted({ref for record in records for ref in record.exceptions}))
        if len(requested) > 100:
            raise ValueError("exception observation limit")
        exceptions = ()
        if requested and self._current_exceptions is not None:
            try:
                exceptions = self._current_exceptions(subject, requested)
            except Exception:
                exceptions = ()
        checks = []
        for record in records:
            within_budget()
            checks.append(self._check(record, deadline))
        within_budget()
        return CurrentEvidenceContext(
            subject=observed, checks=tuple(checks),
            exceptions=exceptions,
        )
