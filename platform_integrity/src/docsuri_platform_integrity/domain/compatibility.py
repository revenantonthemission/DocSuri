"""Exact release compatibility is an observation, never a mutation grant."""

from dataclasses import dataclass

from ..contracts.codec import canonical, digest
from ..contracts.models import CompatibilityManifest, GateVerdict


@dataclass(frozen=True)
class RuntimeObservation:
    artifact: str
    registry: str
    generation: str
    operations: frozenset[str]
    capabilities: frozenset[str]
    writer_epoch: str
    schema_versions: tuple[tuple[str, str], ...]
    role_artifacts: tuple[tuple[str, str], ...]
    config_digest: str


@dataclass(frozen=True)
class CompatibilityPolicy:
    manifest_digests: frozenset[str]
    writer_epoch: str
    schema_versions: tuple[tuple[str, str], ...]
    role_artifacts: tuple[tuple[str, str], ...]
    config_digest: str


def evaluate_compatibility(manifest: CompatibilityManifest, policy: CompatibilityPolicy, observed):
    fingerprint = digest(canonical(manifest.model_dump(mode="json")))
    if not policy.manifest_digests or fingerprint not in policy.manifest_digests:
        return GateVerdict.BLOCKED, ("unsupported_manifest",)
    if observed is None:
        return GateVerdict.INCOMPLETE, ("runtime_observation_unavailable",)
    reasons = set()
    if observed.writer_epoch != policy.writer_epoch:
        reasons.add("unsupported_writer_epoch")
    if sorted(observed.schema_versions) != sorted(policy.schema_versions):
        reasons.add("unsupported_schema_versions")
    if not set(manifest.operations) <= observed.operations:
        reasons.add("unsupported_operations")
    if not set(manifest.required_capabilities) <= observed.capabilities:
        reasons.add("missing_capabilities")
    if reasons:
        return GateVerdict.BLOCKED, tuple(sorted(reasons))
    if (
        (observed.artifact, observed.registry, observed.generation)
        != (manifest.artifact, manifest.registry, manifest.generation)
        or sorted(observed.role_artifacts) != sorted(policy.role_artifacts)
        or observed.config_digest != policy.config_digest
    ):
        return GateVerdict.STALE, ("runtime_binding_changed",)
    return GateVerdict.ELIGIBLE, ()
