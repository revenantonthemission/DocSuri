"""Readonly capability probes: the only honest source of a capability receipt.

The verifier in :mod:`.receipt` decides whether a receipt counts; these probes are the only
thing that may produce the underlying observation. Every probe is strictly readonly — it
opens, reads and connects, and never installs, enables, restarts or writes. Each returns an
:class:`Outcome` and never raises, because a probe that crashed must not be mistaken for a
probe that passed: an unavailable capability is ``proven=False`` with a reason.

Evidence is a digest of what was observed, never the observed bytes. Private key material is
not hashed, logged or returned — only public certificates and identifiers are.
"""

import itertools
from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated

from pydantic import Field

from ..adapters.credentials import (
    TLSReference,
    host_encryption_enabled,
    validate_bundle,
)
from ..adapters.keychain import KeychainReader
from ..adapters.nts import ProtectedClock
from ..adapters.postgres_tls import PostgresTarget, PostgresTLS
from ..contracts.codec import canonical, decode, digest
from ..contracts.models import (
    U64,
    Digest,
    Ref,
    TargetRef,
    ValidityWindow,
    Value,
)
from .receipt import Capability, Receipt

DAY_US = 86400 * 1_000_000
# A restore older than this is history, not evidence that this release can restore.
MAX_RESTORE_AGE_US = 30 * DAY_US
# The adapter's frozen-plan membership refusal. Matched exactly: a guard that refuses for any
# other reason (revoked, expired, wrong scope) has not proven that it fails closed.
OUT_OF_PLAN_REFUSAL = "effect is outside the frozen operator plan"


class Outcome(Value):
    """Why a capability is or is not proven, and what was observed when it is."""

    capability: Capability
    proven: bool
    reason: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")]
    artifact: Digest | None = None
    evidence: Digest | None = None


class RestoreReceipt(Value):
    """Operator-produced proof that an encrypted backup was restored to a new incarnation.

    Restoring into the *same* incarnation proves nothing, so the two are compared rather
    than merely recorded.
    """

    host: Ref
    release: Ref
    source: TargetRef
    restored: TargetRef
    encrypted: bool
    verified: bool
    completed_utc_us: U64


def _fail(capability, reason: str) -> Outcome:
    return Outcome(capability=capability, proven=False, reason=reason)


def _pass(capability, artifact: str, evidence: str) -> Outcome:
    return Outcome(capability=capability, proven=True, reason="verified",
                   artifact=artifact, evidence=evidence)


def probe_keychain_roles(
    references, *, reader_factory=KeychainReader, encryption_check=host_encryption_enabled,
) -> Outcome:
    """Every declared purpose key must be readable noninteractively and be real TLS material."""
    capability = Capability.KEYCHAIN_ROLES
    if not references:
        return _fail(capability, "no_role_declared")
    if encryption_check() is not True:
        return _fail(capability, "host_encryption_unavailable")
    observed = []
    for reference in references:
        try:
            bundle = validate_bundle(
                reader_factory(reference.keychain).get(reference.service, reference.account)
            )
        except Exception:
            return _fail(capability, "purpose_key_unavailable")
        # Fingerprint the public certificate only. Hashing the private key would turn this
        # receipt into a key-verification oracle.
        observed.append({"account": reference.account, "service": reference.service,
                         "certificate": digest(bundle["certificate"].encode())})
    declared = sorted(
        ({"keychain": str(r.keychain), "service": r.service, "account": r.account}
         for r in references), key=lambda item: (item["service"], item["account"])
    )
    return _pass(capability, digest(canonical(declared)), digest(canonical(observed)))


def probe_tls_roles(target: PostgresTarget, credentials, *, connect=None) -> Outcome:
    """The scoped database role must actually log in over negotiated mTLS, unprivileged."""
    capability = Capability.TLS_ROLES
    opener = connect or PostgresTLS(target, credentials).connect
    try:
        with opener() as connection:
            if connection.pgconn.ssl_in_use is not True:
                return _fail(capability, "tls_not_negotiated")
            row = connection.execute("SELECT session_user").fetchone()
    except Exception:
        return _fail(capability, "role_login_failed")
    if row is None or row[0] != target.user:
        return _fail(capability, "unexpected_identity")
    return _pass(capability, digest(canonical(target.model_dump(mode="json"))),
                 digest(canonical({"sessionUser": target.user, "tls": True})))


def probe_nts_clock(frame: Path, *, writer_uid: int, config_digest: str, **kwargs) -> Outcome:
    """The published frame must pass the same protected-clock checks the reader relies on."""
    capability = Capability.NTS_CLOCK
    try:
        clock = ProtectedClock(frame, writer_uid=writer_uid, config_digest=config_digest,
                               **kwargs)
        lower, upper = clock()
    except Exception:
        return _fail(capability, "protected_clock_unavailable")
    observed = {"lowerUs": str(lower), "upperUs": str(upper), "frame": digest(
        canonical({"path": str(frame), "configDigest": config_digest}))}
    return _pass(capability, config_digest, digest(canonical(observed)))


def probe_native_commit_guard(authority, *, connection, identity: str,
                              definition_digest: str) -> Outcome:
    """Prove the guard is real, fails closed, and is actually wired to a live plan.

    Two separate observations are required, because either alone is misleading:

    1. **Fails closed.** An identity outside the frozen plan must be refused at the membership
       boundary, which the adapter checks before it reads any authority state. If the guard
       admits it, nothing else matters.
    2. **Wired.** The *planned* identity must get past that boundary and reach the authority
       check. A guard that refuses everything would pass observation 1 alone while being
       incapable of ever applying an effect.

    Observation 2 enters the guard body and performs no effect at all; the adapter's own
    post-yield check then refuses the finalization, which is itself part of the proof.
    """
    capability = Capability.NATIVE_COMMIT_GUARD
    from psycopg.pq import TransactionStatus

    from ..adapters.authority import MutationUnavailable

    definitions = getattr(authority, "definitions", None)
    if not isinstance(definitions, dict) or not definitions:
        return _fail(capability, "guard_not_provisioned")
    if getattr(authority, "binding", None) is None:
        return _fail(capability, "operator_binding_absent")
    if definitions.get(identity) != definition_digest:
        return _fail(capability, "planned_identity_not_in_frozen_plan")

    # An identity that provably is not in the plan, without assuming a naming scheme.
    unplanned = next(f"unplanned:{index}" for index in itertools.count()
                     if f"unplanned:{index}" not in definitions)
    # The adapter refuses finalization *after* the yield, so the body must not be exited with
    # a bare return: that would let the post-yield exception discard the verdict. The entered
    # flag, not the exception, is what decides whether the guard refused or admitted.
    entered, authority_refused, refusal = False, False, None
    try:
        with authority.guard(connection, unplanned, "0" * 64):
            entered = True
    except MutationUnavailable as error:
        refusal = str(error)
    except PermissionError:
        authority_refused = True
    except Exception:
        return _fail(capability, "guard_raised_unexpectedly")
    # `entered` is checked first: a guard that admits and then refuses finalization raises the
    # same MutationUnavailable as one that refused up front, and only `entered` separates them.
    if entered or authority_refused:
        # Reaching the authority check at all means the plan boundary did not refuse, so the
        # guard did not fail closed. Which check rejected it afterwards does not matter.
        return _fail(capability, "unplanned_effect_admitted")
    if refusal != OUT_OF_PLAN_REFUSAL:
        return _fail(capability, "guard_refused_for_the_wrong_reason")

    admitted = False
    try:
        with authority.guard(connection, identity, definition_digest):
            admitted = True
    except (MutationUnavailable, PermissionError):
        # A revoked, expired or out-of-scope approval is a legitimate refusal, not a crash.
        pass
    except Exception:
        return _fail(capability, "guard_raised_unexpectedly")
    if not admitted:
        return _fail(capability, "planned_effect_not_admitted")
    return _pass(
        capability,
        digest(canonical({"identities": sorted(definitions)})),
        digest(canonical({"refused": unplanned, "admitted": identity, "performedEffect": False,
                          "transactionStatus": str(TransactionStatus.IDLE)})),
    )


def probe_restore_receipt(
    path: Path, *, host: str, release: str, lower: int, upper: int,
) -> Outcome:
    """A recent, encrypted, host- and release-bound restore into a *new* target incarnation."""
    capability = Capability.RESTORE_RECEIPT
    try:
        receipt = RestoreReceipt.model_validate_json(canonical(decode(path.read_bytes())))
    except Exception:
        return _fail(capability, "receipt_unreadable")
    if receipt.host != host:
        return _fail(capability, "host_mismatch")
    if receipt.release != release:
        return _fail(capability, "release_mismatch")
    if receipt.encrypted is not True or receipt.verified is not True:
        return _fail(capability, "restore_not_encrypted_or_unverified")
    if (receipt.restored.target_id, receipt.restored.namespace,
            receipt.restored.incarnation) == (
            receipt.source.target_id, receipt.source.namespace, receipt.source.incarnation):
        return _fail(capability, "restored_into_same_incarnation")
    completed = int(receipt.completed_utc_us)
    # Not from the future, and not so old that it describes a different release state. The
    # observation window is a single instant, so a restore that just finished is valid.
    if completed > upper or lower - completed > MAX_RESTORE_AGE_US:
        return _fail(capability, "restore_stale")
    return _pass(capability, digest(canonical(receipt.model_dump(mode="json"))),
                 digest(canonical({"completedUtcUs": receipt.completed_utc_us,
                                   "incarnation": receipt.restored.incarnation})))


@dataclass(frozen=True)
class ProbeSet:
    """Everything the five probes need, in one injectable value.

    Absent configuration is not a pass and not a crash: it reports
    ``<capability>_not_configured`` so an operator can tell "not installed" from
    "installed and broken".
    """

    release: Ref
    host: Ref
    keychain_references: tuple[TLSReference, ...] = ()
    database: PostgresTarget | None = None
    credentials: object = None
    clock_frame: Path | None = None
    clock_uid: int | None = None
    clock_config_digest: Digest | None = None
    clock_kwargs: dict = field(default_factory=dict)
    authority: object = None
    guard_connection: object = None
    guard_identity: str | None = None
    guard_definition_digest: Digest | None = None
    restore_receipt: Path | None = None

    def run(self, *, window: tuple[int, int] | None = None) -> dict[Capability, Outcome]:
        outcomes = {}
        if self.keychain_references:
            outcomes[Capability.KEYCHAIN_ROLES] = probe_keychain_roles(
                self.keychain_references)
        else:
            outcomes[Capability.KEYCHAIN_ROLES] = _fail(
                Capability.KEYCHAIN_ROLES, "not_configured")
        if self.database is not None and self.credentials is not None:
            outcomes[Capability.TLS_ROLES] = probe_tls_roles(self.database, self.credentials)
        else:
            outcomes[Capability.TLS_ROLES] = _fail(Capability.TLS_ROLES, "not_configured")
        if (self.clock_frame is not None and self.clock_uid is not None
                and self.clock_config_digest is not None):
            outcomes[Capability.NTS_CLOCK] = probe_nts_clock(
                self.clock_frame, writer_uid=self.clock_uid,
                config_digest=self.clock_config_digest, **self.clock_kwargs)
        else:
            outcomes[Capability.NTS_CLOCK] = _fail(Capability.NTS_CLOCK, "not_configured")
        if (self.authority is not None and self.guard_connection is not None
                and self.guard_identity is not None
                and self.guard_definition_digest is not None):
            outcomes[Capability.NATIVE_COMMIT_GUARD] = probe_native_commit_guard(
                self.authority, connection=self.guard_connection, identity=self.guard_identity,
                definition_digest=self.guard_definition_digest)
        else:
            outcomes[Capability.NATIVE_COMMIT_GUARD] = _fail(
                Capability.NATIVE_COMMIT_GUARD, "not_configured")
        if self.restore_receipt is not None:
            if window is None and self.clock_frame is not None:
                try:
                    window = ProtectedClock(self.clock_frame, writer_uid=self.clock_uid,
                                            config_digest=self.clock_config_digest,
                                            **self.clock_kwargs)()
                except Exception:
                    pass
            if (not isinstance(window, tuple) or len(window) != 2
                or any(type(value) is not int for value in window)
                or not 0 <= window[0] <= window[1] < 2**64
                or window[1] - window[0] > 2_000_000):
                outcomes[Capability.RESTORE_RECEIPT] = _fail(
                    Capability.RESTORE_RECEIPT, "trusted_clock_required")
            else:
                outcomes[Capability.RESTORE_RECEIPT] = probe_restore_receipt(
                    self.restore_receipt, host=self.host, release=self.release,
                    lower=window[0], upper=window[1])
        else:
            outcomes[Capability.RESTORE_RECEIPT] = _fail(
                Capability.RESTORE_RECEIPT, "not_configured")
        return outcomes


def receipt_from(outcome: Outcome, *, host: str, release: str, days: int = 1,
                  lower: int, upper: int) -> Receipt:
    """Build a signable receipt, or refuse. Only a proven outcome can become a receipt."""
    if outcome.proven is not True or outcome.artifact is None or outcome.evidence is None:
        raise PermissionError(f"capability not proven: {outcome.capability.value}")
    if type(days) is not int or not 0 < days * DAY_US <= 7 * DAY_US:
        raise ValueError("receipt window must be within seven days")
    if (type(lower) is not int or type(upper) is not int or not 0 <= lower <= upper < 2**64
        or upper - lower > 2_000_000):
        raise ValueError("authenticated clock window required")
    return Receipt(
        capability=outcome.capability,
        host=host,
        release=release,
        validity=ValidityWindow(valid_from=str(lower), valid_until=str(lower + days * DAY_US)),
        artifact=outcome.artifact,
        evidence=outcome.evidence,
    )
