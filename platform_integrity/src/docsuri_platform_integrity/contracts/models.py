"""REM-1 control values. Immutable, extra-forbidden, bounded and lossless on the wire."""

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, field_validator, model_validator

Ref = Annotated[str, Field(min_length=1, max_length=200, pattern=r"^[A-Za-z0-9_.:@/-]+$")]
Digest = Annotated[str, Field(pattern=r"^sha256:[0-9a-f]{64}$")]


def _uint64(value: str) -> str:
    if int(value) > 2**64 - 1:
        raise ValueError("integer exceeds uint64")
    return value


U64 = Annotated[str, Field(pattern=r"^(0|[1-9][0-9]{0,19})$"), AfterValidator(_uint64)]


class Value(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    @field_validator("*", mode="after")
    @classmethod
    def valid_unicode(cls, value):
        if isinstance(value, str):
            value.encode("utf-8", errors="strict")
        return value


class TargetRef(Value):
    target_id: Ref
    namespace: Ref
    incarnation: Ref


class ValidityWindow(Value):
    valid_from: U64
    valid_until: U64

    @model_validator(mode="after")
    def nonempty_interval(self):
        if int(self.valid_from) >= int(self.valid_until):
            raise ValueError("empty validity interval")
        return self

    @field_validator("valid_from", "valid_until")
    @classmethod
    def uint64(cls, value):
        if int(value) > 2**64 - 1:
            raise ValueError("instant exceeds uint64")
        return value

    def contains(self, lower: int, upper: int) -> bool:
        return 0 <= lower <= upper and int(self.valid_from) <= lower <= upper < int(
            self.valid_until
        )


class EffectAssurance(StrEnum):
    NOT_STARTED = "NOT_STARTED"
    UNKNOWN = "UNKNOWN"
    COMMITTED = "COMMITTED"
    NO_EFFECT_CONFIRMED = "NO_EFFECT_CONFIRMED"


class Assurance(StrEnum):
    VERIFIED = "VERIFIED_EXECUTION"
    ADOPTED = "ADOPTED_BASELINE"


class GateVerdict(StrEnum):
    BLOCKED = "BLOCKED"
    INCOMPLETE = "INCOMPLETE"
    STALE = "STALE"
    EXCEPTIONS = "ELIGIBLE_WITH_EXCEPTIONS"
    ELIGIBLE = "ELIGIBLE"


class SubjectSnapshot(Value):
    subject: Ref
    artifact: Digest
    incarnation: Ref
    policy: Digest
    kind: Literal["artifact", "target"] = "artifact"
    target: TargetRef | None = None
    state: Digest | None = None

    @model_validator(mode="after")
    def mutable_subject_binding(self):
        if self.kind == "target" and (self.target is None or self.state is None):
            raise ValueError("mutable subject requires target and state")
        if self.target is not None and self.target.incarnation != self.incarnation:
            raise ValueError("subject target incarnation mismatch")
        if self.kind == "artifact" and self.target is not None:
            raise ValueError("artifact subject cannot hide a mutable target")
        return self


class PolicySnapshot(Value):
    policy_id: Ref
    revision: U64
    required_slots: Annotated[tuple[Ref, ...], Field(min_length=1, max_length=100)]


class ApprovalBinding(Value):
    approval_id: Ref
    actor: Ref
    purpose: Ref
    target: TargetRef
    plan: Digest
    artifact: Digest
    policy: Digest
    validity: ValidityWindow
    authority_revision: U64


class MigrationSpec(Value):
    owner: Ref
    local_id: Ref
    path: Ref
    digest: Digest
    order: Annotated[int, Field(ge=0, le=100_000)]
    prerequisites: Annotated[tuple[Ref, ...], Field(max_length=2_000)] = ()
    effect_class: str = Field(default="ATOMIC_STEP", pattern=r"^ATOMIC_STEP$")

    @property
    def identity(self) -> str:
        return f"{self.owner}:{self.local_id}"


class RegistrySnapshot(Value):
    specs: Annotated[tuple[MigrationSpec, ...], Field(max_length=2_000)]
    digest: Digest


class MigrationSatisfaction(Value):
    target: TargetRef
    migration_id: Ref
    definition_digest: Digest
    assurance: Assurance
    receipt: Ref


class LedgerObservation(Value):
    target: TargetRef
    state: str = Field(pattern=r"^(ABSENT|AVAILABLE|UNAVAILABLE|INCONSISTENT)$")
    proofs: tuple[MigrationSatisfaction, ...] = ()
    legacy_names: tuple[Ref, ...] = ()


class LegacyReconciliationDecision(Value):
    target: TargetRef
    legacy_name: Ref
    candidates: tuple[Ref, ...]
    approved_definition: Digest
    approval: Ref
    assurance: Assurance = Assurance.ADOPTED


class PlannedEffect(Value):
    step: Ref
    definition_digest: Digest
    expected_before: Digest
    expected_after: Digest


class ExecutionPlan(Value):
    action: Ref
    target: TargetRef
    registry_digest: Digest
    artifact_digest: Digest
    policy_digest: Digest
    recovery_digest: Digest
    steps: Annotated[tuple[PlannedEffect, ...], Field(min_length=1, max_length=2_000)]

    @model_validator(mode="after")
    def unique_effects(self):
        if len({effect.step for effect in self.steps}) != len(self.steps):
            raise ValueError("duplicate planned effect")
        return self


class RunIntent(Value):
    run_id: Ref
    semantic_key: Digest
    plan: Digest
    target: TargetRef


class RunAttempt(Value):
    run_id: Ref
    attempt_id: Ref
    ordinal: Annotated[int, Field(ge=1, le=2**53 - 1)]
    outcome: str = Field(pattern=r"^(RUNNING|PAUSED|RECONCILE_REQUIRED|SUCCEEDED|REJECTED)$")
    actor: Ref
    approval: Ref
    invocation: Ref
    started_at: U64


class EffectCheckpoint(Value):
    run_id: Ref
    step: Ref
    sequence: U64
    assurance: EffectAssurance
    receipt: Ref | None = None


class TargetFence(Value):
    target: TargetRef
    epoch: U64
    holder: Ref
    validity: ValidityWindow


class CommandContext(Value):
    """Safe audit context, supplied by protected composition; not an authorization token."""

    actor: Ref
    purpose: Literal["plan", "run", "reconcile", "verify"]
    correlation: Ref
    recorded_at: U64
    time_quality: Literal["trusted", "unknown"]


class EffectBinding(Value):
    run_id: Ref
    attempt_id: Ref
    target: TargetRef
    plan: Digest
    step: Ref
    definition_digest: Digest
    expected_before: Digest
    expected_after: Digest
    fence_epoch: U64

    @field_validator("fence_epoch")
    @classmethod
    def positive_epoch(cls, value):
        if value == "0":
            raise ValueError("fence epoch must be positive")
        return value


class BoundCheckpoint(Value):
    binding: EffectBinding
    checkpoint: EffectCheckpoint
    recorded_at: U64
    completion_verified: bool = False

    @model_validator(mode="after")
    def consistent_effect(self):
        if (self.binding.run_id, self.binding.step) != (
            self.checkpoint.run_id, self.checkpoint.step
        ):
            raise ValueError("checkpoint binding mismatch")
        known = self.checkpoint.assurance in (
            EffectAssurance.COMMITTED, EffectAssurance.NO_EFFECT_CONFIRMED
        )
        if known != (self.checkpoint.receipt is not None):
            raise ValueError("checkpoint receipt does not match assurance")
        if self.completion_verified and self.checkpoint.assurance != EffectAssurance.COMMITTED:
            raise ValueError("only committed effects can have verified completion")
        return self


class EffectObservation(Value):
    """Normalized native-adapter facts, never accepted directly from a public request."""

    binding: EffectBinding
    authoritative: bool = False
    receipt: Ref | None = None
    committed: bool = False
    aborted: bool = False
    quiescent: bool = False
    observed_state: Digest | None = None
    authorization_verified: bool = False
    durability_verified: bool = False


class CheckpointReceipt(Value):
    """Acknowledged control record; does not grant permission to dispatch an effect."""

    record: BoundCheckpoint
    record_digest: Digest
    event_id: Digest
    # One-use private handoff, returned only by acknowledged native preparation. Never audit,
    # serialize as history, or reconstruct it from a readonly checkpoint.
    dispatch_token: Ref | None = Field(default=None, repr=False, exclude=True)


class RunRecord(Value):
    intent: RunIntent
    plan: ExecutionPlan
    state: Literal["PLANNED", "RUNNING", "PAUSED", "SUCCEEDED", "RECONCILE_REQUIRED"]
    revision: U64
    attempt_id: Ref | None


class SchemaResource(Value):
    resource_id: Ref
    path: Ref
    digest: Digest
    visibility: str = Field(pattern=r"^(public|server|internal)$")


class SchemaCatalog(Value):
    resources: Annotated[tuple[SchemaResource, ...], Field(max_length=1_000)]
    digest: Digest


class ConsumerManifest(Value):
    consumer: Ref
    roots: tuple[Ref, ...]
    exports: tuple[Ref, ...]
    visibility: str = Field(pattern=r"^(public|server|internal)$")
    adapters: tuple[Ref, ...] = ()


class BindingCandidate(Value):
    generation: Digest
    catalog: Digest
    consumer_manifest: Digest
    toolchain: Digest
    files: tuple[Ref, ...]


class BindingActivation(Value):
    target: TargetRef
    revision: U64
    generation: Digest
    previous: Digest | None
    receipt: Ref


class InventoryOccurrence(Value):
    occurrence: Ref
    name: Ref
    version: Ref
    ecosystem: str = Field(pattern=r"^(python|npm|image|native|first-party)$")
    artifact: Digest


class DependencyInventory(Value):
    artifact: Digest
    components: Annotated[tuple[InventoryOccurrence, ...], Field(max_length=100_000)]
    required_scopes: tuple[Ref, ...]


class Finding(Value):
    advisory: Ref
    occurrence: Ref
    severity: str = Field(pattern=r"^(critical|high|moderate|low|unknown)$")
    source: Ref


class AdvisoryObservationSet(Value):
    artifact: Digest
    scope: Ref
    complete: bool
    observed_at: U64
    findings: tuple[Finding, ...]
    report_digest: Digest


class ReachabilityException(Value):
    exception_id: Ref
    artifact: Digest
    closure: Digest
    advisory: Ref
    occurrence: Ref
    assumptions: Digest
    policy: Digest
    validity: ValidityWindow
    approver: Ref


class VerificationAttestation(Value):
    evidence_id: Ref
    subject: SubjectSnapshot
    slot: Ref
    revision: U64
    outcome: str = Field(pattern=r"^(PASS|FAIL|UNKNOWN)$")
    reasons: Annotated[tuple[Ref, ...], Field(max_length=100)] = ()
    validity: ValidityWindow
    exceptions: Annotated[tuple[Ref, ...], Field(max_length=100)] = ()
    # Unbound legacy records remain observable history, never eligible current evidence.
    verification_id: Ref | None = None
    closure: Digest | None = None
    assumptions: Digest | None = None


class EvidenceHeadSelection(Value):
    slot: Ref
    revision: U64
    state: str = Field(pattern=r"^(PENDING|RESOLVED)$")
    evidence_id: Ref | None = None
    subject: SubjectSnapshot | None = None
    verification_id: Ref | None = None


class VerificationRequest(Value):
    verification_id: Ref
    subject: SubjectSnapshot
    slot: Ref
    inputs: Digest


class VerificationReservation(Value):
    request: VerificationRequest
    revision: U64
    previous_revision: U64

    @model_validator(mode="after")
    def contiguous_revision(self):
        if int(self.revision) != int(self.previous_revision) + 1:
            raise ValueError("noncontiguous verification reservation")
        return self


class EvidencePublication(Value):
    evidence_id: Ref
    record_digest: Digest
    selected: bool
    head_revision: U64


class EvidenceCheck(Value):
    """Current protected-verifier result, not a claim accepted from an HTTP caller."""

    evidence_id: Ref
    record_digest: Digest
    status: Literal["VERIFIED", "INVALID", "REVOKED", "UNKNOWN"]
    trust_ref: Digest | None = None
    trust_validity: ValidityWindow | None = None


class CurrentException(Value):
    exception: ReachabilityException
    finding: Finding
    closure: Digest
    assumptions: Digest
    authorized: bool = False
    revoked: bool = True


class CurrentEvidenceContext(Value):
    subject: SubjectSnapshot
    checks: Annotated[tuple[EvidenceCheck, ...], Field(max_length=100)]
    exceptions: Annotated[tuple[CurrentException, ...], Field(max_length=100)] = ()


class GateDiagnostic(Value):
    slot: Ref | None
    code: Ref


class SelectedRevision(Value):
    slot: Ref
    revision: U64


class GateEvaluation(Value):
    verdict: GateVerdict
    reasons: tuple[Ref, ...]
    evidence_ids: tuple[Ref, ...]
    exception_ids: tuple[Ref, ...] = ()
    diagnostics: tuple[GateDiagnostic, ...] = ()
    selections: tuple[SelectedRevision, ...] = ()
    evaluation_window: tuple[U64, U64] | None = None
    input_fingerprint: Digest | None = None

    @property
    def eligible(self) -> bool:
        return self.verdict in (GateVerdict.ELIGIBLE, GateVerdict.EXCEPTIONS)


class SafeObservation(Value):
    event_time: U64
    time_quality: str = Field(pattern=r"^(trusted|unknown)$")
    level: str = Field(pattern=r"^(info|warning|error)$")
    code: Ref
    role: Ref
    correlation: Ref
    duration_ms: Annotated[int, Field(ge=0)] | None = None


class CompatibilityManifest(Value):
    artifact: Digest
    registry: Digest
    generation: Digest
    operations: tuple[Ref, ...]
    required_capabilities: tuple[Ref, ...]


class CompatibilityResult(Value):
    """An observation of exact-release compatibility. Never a grant to act on a new release."""

    release: Ref
    verdict: GateVerdict
    reasons: tuple[Ref, ...] = ()
