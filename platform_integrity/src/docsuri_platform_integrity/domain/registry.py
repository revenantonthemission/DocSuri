from dataclasses import dataclass
from pathlib import PurePosixPath

from ..contracts.models import Assurance, LedgerObservation, MigrationSpec, TargetRef


def validate_registry(specs: tuple[MigrationSpec, ...]) -> tuple[MigrationSpec, ...]:
    if not specs or len(specs) > 2000:
        raise ValueError("migration count limit")
    indexed = {s.identity: s for s in specs}
    if len(indexed) != len(specs) or len({s.path for s in specs}) != len(specs):
        raise ValueError("duplicate migration identity or path")
    for spec in specs:
        path = PurePosixPath(spec.path)
        if (
            path.is_absolute() or ".." in path.parts or path.suffix != ".sql"
            or path.as_posix() != spec.path or "\\" in spec.path
            or ":" in spec.owner or ":" in spec.local_id or len(spec.identity) > 200
            or len(set(spec.prerequisites)) != len(spec.prerequisites)
        ):
            raise ValueError("invalid migration path")
        for required in spec.prerequisites:
            dependency = indexed.get(required)
            if dependency is None or dependency.order >= spec.order:
                raise ValueError("missing, cyclic or unordered prerequisite")
    return tuple(sorted(specs, key=lambda s: (s.order, s.identity)))


def reconcile_legacy(name: str, specs: tuple[MigrationSpec, ...]) -> tuple[str, tuple[str, ...]]:
    candidates = tuple(sorted(s.identity for s in specs if PurePosixPath(s.path).name == name))
    # Even one candidate proves only an identity match, not the historical SQL bytes/effect.
    return "NEEDS_RECONCILIATION", candidates


@dataclass(frozen=True)
class RegistryAssessment:
    states: tuple[tuple[str, str], ...]
    pending: tuple[str, ...]
    reasons: tuple[str, ...]

    @property
    def ready(self):
        return not self.reasons and not self.pending


def assess_registry(
    specs: tuple[MigrationSpec, ...], observation: LedgerObservation, *, target: TargetRef,
    required_capabilities: frozenset[str], capabilities: frozenset[str] | None,
    allow_adopted: bool = False, fresh_confirmed: bool = False,
) -> RegistryAssessment:
    """Readonly satisfaction from owner observations, never execution permission or DDL."""
    ordered = validate_registry(specs)
    indexed = {spec.identity: spec for spec in ordered}
    states = dict.fromkeys(indexed, "PENDING")
    reasons = set()
    if not required_capabilities:
        reasons.add("required_capabilities_missing")
    if capabilities is None:
        reasons.add("capability_observation_unavailable")
    elif not required_capabilities <= capabilities:
        reasons.add("required_capability_missing")
    if observation.target != target or observation.state in {"UNAVAILABLE", "INCONSISTENT"}:
        reasons.add("ledger_observation_unknown")
        states = dict.fromkeys(indexed, "UNKNOWN")
    elif observation.state == "ABSENT":
        if observation.proofs or observation.legacy_names or not fresh_confirmed:
            reasons.add("fresh_target_unproven")
            states = dict.fromkeys(indexed, "NEEDS_RECONCILIATION")
        else:
            states = dict.fromkeys(indexed, "UNINITIALIZED")
            reasons.add("explicit_bootstrap_required")
    else:
        proofs = {}
        for proof in observation.proofs:
            if proof.migration_id not in indexed or proof.target != target:
                reasons.add("unassigned_or_foreign_ledger_claim")
                continue
            proofs.setdefault(proof.migration_id, []).append(proof)
        for identity, claims in proofs.items():
            if len(claims) > 1:
                reasons.add("duplicate_ledger_claim")
                states[identity] = "NEEDS_RECONCILIATION"
                if any(claim.definition_digest != indexed[identity].digest for claim in claims):
                    reasons.add("changed_definition")
                continue
            proof = claims[0]
            if proof.definition_digest != indexed[proof.migration_id].digest:
                states[proof.migration_id] = "CHANGED_DEFINITION"
                reasons.add("changed_definition")
            elif proof.assurance == Assurance.ADOPTED and not allow_adopted:
                states[proof.migration_id] = "NEEDS_RECONCILIATION"
                reasons.add("adoption_not_accepted_by_policy")
            else:
                states[proof.migration_id] = (
                    "ADOPTED_BASELINE"
                    if proof.assurance == Assurance.ADOPTED else "VERIFIED_APPLIED"
                )
        if observation.legacy_names:
            reasons.add("legacy_reconciliation_required")
        satisfied = {
            key for key, state in states.items()
            if state in {"VERIFIED_APPLIED", "ADOPTED_BASELINE"}
        }
        for identity in satisfied:
            if not set(indexed[identity].prerequisites) <= satisfied:
                states[identity] = "NEEDS_RECONCILIATION"
                reasons.add("satisfied_step_has_missing_prerequisite")
    pending = tuple(spec.identity for spec in ordered if states[spec.identity] == "PENDING")
    return RegistryAssessment(tuple(sorted(states.items())), pending, tuple(sorted(reasons)))
