"""The complete application's built inputs (BR1.1; U8 plan Step 11).

Nothing here changes at runtime. The module holds:

- `CONTRIBUTIONS`: the eight entries of BR1.1, each with its revision, the digest of its
  files in the composed chain (its schema digest), its components, the contributions it
  requires, the capabilities it provides, its routes and its lifecycle participants.
  `platform-control` is the separately authorized operator surface and mounts no
  browser route.
- `CAPABILITIES`: the functional spec's capability registry (BR3.11).
- `NAVIGATION`: the one navigation set (decision "Navigation set", BR5.1-BR5.3, A1).
- `LIFECYCLE_MANIFEST`: BR2.1's 21 pairs, revision `u8-owners-v1`.
- `MODEL_EVIDENCE`: the model pins, taken from `docsuri_ops.local_models.MODEL_PINS` so
  one place holds them (BR6.11).
- `MANIFEST_REVISION`: the digest of all of the above.

`Manifest.verify` refuses a manifest that lacks a contribution, repeats one or whose
revision differs from the digest of its entries; it runs when this module is imported
and again before any composition, so no partial application is ever produced.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from docsuri_ops.local_models import MODEL_PINS

from . import u8_migrations

ROOT = Path(__file__).resolve().parents[1]
LIFECYCLE_REVISION = "u8-owners-v1"
LIFECYCLE_PAIR_BOUND = 32  # AccountAccess's bound (entities.md LifecycleParticipantEntry)
# PlatformControl's store: U7's schema and inventory, and U8's store amendment (the
# person's decision of 2026-10-25, "After the move, same build"), so a change to the
# amendment alone changes the contribution's schema digest. The amendment is named as a
# literal path, the one `platform_profile.STORE_AMENDMENT` holds: this module imports
# nothing from U8's PlatformControl package, so without that package the registry still
# loads and registration reports PlatformControl `missing`.
PLATFORM_FILES = (
    "ops/src/docsuri_ops/platform_control/schema.sql",
    "ops/src/docsuri_ops/platform_control/inventory.json",
    "ops/src/docsuri_ops/u8_platform/u8_store.sql",
)
CONTRIBUTION_IDS = (
    "paper-journey", "account-controls", "paper-corpus", "research-workspace",
    "topics-digests", "approved-export", "platform-control", "service-operations",
)
UNAVAILABLE_REASONS = ("missing", "incompatible", "dependency-unavailable", "policy-unresolved")


class ManifestRefused(ValueError):
    """The registration manifest is not the complete, verified build input (BR1.1)."""


def digest(value) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


def _unit_of(file: str) -> str:
    """The unit that wrote one chain file, by its name; U1's files are its base and
    amendments."""
    name = Path(file).name
    for unit in ("u2", "u3", "u4", "u5", "u6", "u8"):
        if name.startswith(unit + "_"):
            return unit
    return "u1"


UNIT_OF_CONTRIBUTION = {
    "paper-journey": "u1", "account-controls": "u2", "paper-corpus": "u3",
    "research-workspace": "u4", "topics-digests": "u5", "approved-export": "u6",
    "platform-control": "u7", "service-operations": "u8",
}


def chain_files_of(contribution_id: str) -> tuple[str, ...]:
    """The files a contribution brings to the composed chain (PlatformControl's store
    for `platform-control`)."""
    if contribution_id == "platform-control":
        return PLATFORM_FILES
    unit = UNIT_OF_CONTRIBUTION[contribution_id]
    return tuple(file for file in u8_migrations.chain_files() if _unit_of(file) == unit)


def schema_digest_of(files, digests: dict[str, str]) -> str:
    """The digest of a contribution's files, from `{file: sha256}`."""
    return digest([[file, digests.get(file)] for file in files])


def release_digests(contribution_id: str, root: Path = ROOT) -> dict[str, str]:
    return {
        file: hashlib.sha256((root / file).read_bytes()).hexdigest()
        for file in chain_files_of(contribution_id)
    }


@dataclass(frozen=True)
class Contribution:
    contribution_id: str
    unit: str
    revision: str
    schema_digest: str
    components: tuple[str, ...]
    requires: tuple[str, ...]
    provides: tuple[str, ...]
    routes: tuple[str, ...]
    lifecycle_participants: tuple[str, ...]
    required: bool = True


def _contribution(contribution_id, components, requires, provides, routes, participants):
    unit = UNIT_OF_CONTRIBUTION[contribution_id]
    return Contribution(
        contribution_id, unit.upper(), f"{unit}-{contribution_id}-1",
        schema_digest_of(chain_files_of(contribution_id), release_digests(contribution_id)),
        tuple(components), tuple(requires), tuple(provides), tuple(routes), tuple(participants),
    )


# The browser routes each contribution mounts, by path prefix.
CONTRIBUTIONS: tuple[Contribution, ...] = (
    _contribution(
        "paper-journey",
        ("AccountAccess", "Library", "Personalization", "UsageEntitlements", "WebWorkspace"),
        (),
        ("account.entry", "library.saved-work", "personalization.settings", "usage.wallet",
         "public.static"),
        ("/api/v2/session", "/api/v2/c01/", "/api/v2/c02/access-", "/api/v2/c03/",
         "/privacy", "/terms", "/"),
        (),
    ),
    _contribution(
        "account-controls",
        ("AccountAccess", "Personalization", "UsageEntitlements"),
        ("paper-journey",),
        ("account.controls", "provider.google", "provider.orcid", "provider.resend"),
        ("/api/v2/c02/", "/api/v2/identity/"),
        ("AccountAccess", "Library", "Personalization", "UsageEntitlements", "PaperAssistance",
         "DiscoveryCitations"),
    ),
    _contribution(
        "paper-corpus",
        ("CorpusContent", "Discovery", "PaperAssistance", "Library"),
        ("paper-journey",),
        ("corpus.content", "discovery.search", "assistance.summary", "assistance.translation",
         "provider.models"),
        ("/api/v2/c04/", "/api/v2/c05/", "/api/v2/c06/", "/api/v2/papers/"),
        (),
    ),
    _contribution(
        "research-workspace",
        ("ResearchWorkspace",),
        ("paper-corpus",),
        ("research", "novelty"),
        ("/api/v2/c07/",),
        ("ResearchWorkspace",),
    ),
    _contribution(
        "topics-digests",
        ("TopicsDigests",),
        ("research-workspace",),
        ("topics.digest",),
        ("/api/v2/c08/", "/api/v2/unsubscribe/"),
        ("TopicsDigests",),
    ),
    _contribution(
        "approved-export",
        ("ApprovedExport",),
        ("research-workspace", "topics-digests"),
        ("export", "provider.notion"),
        ("/api/v2/c09/",),
        ("ApprovedExport",),
    ),
    _contribution(
        "platform-control",
        ("PlatformControl",),
        (),
        ("platform.status", "platform.isolation"),
        (),
        (),
    ),
    _contribution(
        "service-operations",
        ("ServiceOperations",),
        ("paper-journey", "platform-control"),
        ("operations.ledger", "storage.capacity", "background.work", "operations.cutover"),
        ("/api/v2/c11/", "/health/"),
        ("ServiceOperations",),
    ),
)


@dataclass(frozen=True)
class Capability:
    """One row of the capability registry (functional-spec.md, BR3.11)."""

    capability_id: str
    owner: str
    producer: str
    required: bool
    timing: str  # required | provider | cutover | isolation | static
    degraded: tuple[str, ...] = ()
    unavailable: tuple[str, ...] = ()
    backs: tuple[str, ...] = ()


ISOLATION_ITEMS = (
    "isolation-programs", "isolation-files", "isolation-accounts", "isolation-database",
    "isolation-filter", "isolation-volume", "isolation-backups", "isolation-boot",
)

CAPABILITIES: tuple[Capability, ...] = (
    Capability("account.entry", "AccountAccess", "accounts", True, "required", backs=("sign-in",)),
    Capability("account.controls", "AccountAccess", "accounts", True, "required",
               backs=("account",)),
    Capability("library.saved-work", "Library", "library", True, "required", backs=("library",)),
    Capability("personalization.settings", "Personalization", "personalization", True,
               "required", backs=("settings",)),
    Capability("usage.wallet", "UsageEntitlements", "usage", True, "required", backs=("usage",)),
    Capability("corpus.content", "CorpusContent", "corpus", True, "required", backs=("paper",)),
    Capability("discovery.search", "Discovery", "discovery", True, "required",
               degraded=("semantic-search-unavailable",), backs=("search",)),
    Capability("research", "ResearchWorkspace", "research", True, "required",
               degraded=("model-runtime-waiting",), backs=("research", "jobs")),
    Capability("novelty", "ResearchWorkspace", "research", True, "required",
               degraded=("model-runtime-waiting",), backs=("novelty",)),
    Capability("topics.digest", "TopicsDigests", "topics", True, "required",
               degraded=("digest-delivery-late", "maintainer-address-pending"),
               backs=("topics",)),
    Capability("export", "ApprovedExport", "export", True, "required",
               degraded=("export-effect-late",), backs=("export",)),
    Capability("operations.ledger", "ServiceOperations", "ledger", True, "required",
               unavailable=("ledger-damaged",), backs=("operations",)),
    Capability(
        "storage.capacity", "ServiceOperations", "capacity", True, "required",
        degraded=(
            "capacity-approaching", "internal-disk-low", "backup-volume-unavailable",
            "backup-volume-low", "backup-volume-shared-cleanup", "backup-catalogue-damaged",
            "backup-volume-mismatch", "last-backup-held",
        ),
        unavailable=("capacity-exhausted", "internal-disk-critical"),
    ),
    # `scheduler-pass-unrecorded`: the scheduler wrote no pass file (Step 58(f), L1-41).
    Capability("background.work", "ServiceOperations", "control-loop", True, "required",
               degraded=("lane-behind-deadline", "scheduler-pass-unrecorded")),
    Capability("assistance.summary", "PaperAssistance", "assistance", False, "required",
               degraded=("assistance-readiness-pending",),
               unavailable=("model-runtime-unavailable",), backs=("paper",)),
    Capability("assistance.translation", "PaperAssistance", "assistance", False, "required",
               degraded=("assistance-readiness-pending",),
               unavailable=("model-runtime-unavailable",), backs=("paper",)),
    # The backup agent's findings and the standing job's own (Step 58(b), NFR9.7).
    Capability("platform.status", "PlatformControl", "platform-status", False, "provider",
               degraded=(
                   "backup-volume-unavailable", "backup-volume-mismatch",
                   "backup-volume-ownership", "backup-volume-unencrypted",
                   "backup-volume-unwritable", "backup-volume-unreadable",
                   "backup-volume-shared-cleanup", "backup-catalogue-damaged",
                   "backup-volume-low", "backup-agent-unreachable",
               )),
    Capability("platform.isolation", "PlatformControl", "isolation", False, "isolation",
               degraded=ISOLATION_ITEMS, unavailable=("runtime-isolation-lapsed",)),
    Capability("operations.cutover", "ServiceOperations", "cutover", False, "cutover",
               unavailable=("cutover-effect-unknown", "cutover-route-differs")),
    Capability("provider.google", "AccountAccess", "provider-google", False, "provider",
               degraded=("sign-in-unverified",), unavailable=("provider-unreachable",),
               backs=("sign-in",)),
    Capability("provider.orcid", "AccountAccess", "provider-orcid", False, "provider",
               degraded=("sign-in-unverified",), unavailable=("provider-unreachable",),
               backs=("sign-in",)),
    Capability("provider.resend", "AccountAccess", "provider-resend", False, "provider",
               degraded=("first-effect-pending", "allowance-exhausted"),
               unavailable=("provider-unreachable",)),
    Capability("provider.models", "PaperAssistance", "provider-models", False, "provider",
               unavailable=("model-evidence-mismatch", "runtime-unreachable")),
    Capability("provider.notion", "ApprovedExport", "provider-notion", False, "provider",
               degraded=("first-effect-pending",), unavailable=("provider-unreachable",),
               backs=("export",)),
    Capability("public.static", "WebWorkspace", "host", False, "static",
               backs=("privacy", "terms")),
)
# BR3.11's required list, stated once to be compared with the registry.
REQUIRED = frozenset({
    "account.entry", "account.controls", "library.saved-work", "personalization.settings",
    "usage.wallet", "corpus.content", "discovery.search", "research", "novelty",
    "topics.digest", "export", "operations.ledger", "storage.capacity", "background.work",
})


def timing(capability: Capability, policy) -> tuple[int, int, int]:
    """(renewal, freshness, incident tolerance) seconds from the operations policy
    (observability-design § 3.2); `public.static` needs none."""
    if capability.timing == "required":
        return (policy.required_renewal_seconds, policy.required_stale_seconds,
                policy.required_incident_seconds)
    if capability.timing == "provider":
        return (policy.provider_renewal_seconds, policy.provider_stale_seconds,
                policy.required_incident_seconds)
    if capability.timing == "cutover":
        return (policy.cutover_renewal_seconds, policy.cutover_stale_seconds,
                policy.cutover_incident_seconds)
    if capability.timing == "isolation":
        return (policy.isolation_renewal_seconds, policy.isolation_stale_seconds,
                policy.isolation_incident_seconds)
    return (0, 0, 0)


@dataclass(frozen=True)
class NavigationEntry:
    """One entry of the navigation set: its capability, access rule and placement."""

    route_id: str
    title_key: str
    label: str
    path: str
    capability_id: str
    access: str  # anonymous | session | administrator
    placement: str  # primary | contextual | footer
    order: int


NAVIGATION: tuple[NavigationEntry, ...] = tuple(
    NavigationEntry(route, f"nav.{route}", label, path, capability, access, placement, order)
    for order, (route, label, path, capability, access, placement) in enumerate((
        ("search", "검색", "/search", "discovery.search", "anonymous", "primary"),
        ("library", "내 서재", "/library", "library.saved-work", "session", "primary"),
        ("research", "연구", "/research", "research", "session", "primary"),
        ("novelty", "참신성 분석", "/novelty", "novelty", "session", "primary"),
        ("jobs", "작업", "/jobs", "research", "session", "primary"),
        ("topics", "주제 구독", "/topics", "topics.digest", "session", "primary"),
        ("export", "내보내기", "/export", "export", "session", "primary"),
        ("settings", "설정", "/settings", "personalization.settings", "session", "primary"),
        ("usage", "사용량", "/usage", "usage.wallet", "session", "primary"),
        ("account", "계정", "/account", "account.controls", "session", "primary"),
        ("operations", "운영", "/operations", "operations.ledger", "administrator", "primary"),
        ("paper", "논문", "/paper", "corpus.content", "anonymous", "contextual"),
        ("privacy", "개인정보 처리방침", "/privacy", "public.static", "anonymous", "footer"),
        ("terms", "이용약관", "/terms", "public.static", "anonymous", "footer"),
    ))
)
PRIMARY_ORDER = ("검색", "내 서재", "연구", "참신성 분석", "작업", "주제 구독", "내보내기",
                 "설정", "사용량", "계정")

# BR2.1: 21 (participant, scope) pairs.
LIFECYCLE_MANIFEST: tuple[tuple[str, str], ...] = (
    ("AccountAccess", "live_records"), ("AccountAccess", "derived_artifacts"),
    ("Library", "live_records"),
    ("Personalization", "live_records"), ("Personalization", "derived_artifacts"),
    ("Personalization", "pending_work"),
    ("UsageEntitlements", "live_records"),
    ("PaperAssistance", "live_records"), ("PaperAssistance", "derived_artifacts"),
    ("PaperAssistance", "pending_work"),
    ("DiscoveryCitations", "live_records"),
    ("ResearchWorkspace", "live_records"), ("ResearchWorkspace", "derived_artifacts"),
    ("ResearchWorkspace", "pending_work"),
    ("TopicsDigests", "live_records"), ("TopicsDigests", "pending_work"),
    ("ApprovedExport", "live_records"), ("ApprovedExport", "pending_work"),
    ("ApprovedExport", "external_copies"),
    ("ServiceOperations", "backups"), ("ServiceOperations", "restore_enforcement"),
)

# Each participant's C02 `LifecycleParticipant.component`. The participant identifiers
# are BR2.1's and the lifecycle guard's (`DiscoveryCitations`); C02 names that owner's
# component `Discovery`, so the participant keeps its identifier and projects onto the
# contract's component name.
PARTICIPANT_COMPONENTS = {
    participant: ("Discovery" if participant == "DiscoveryCitations" else participant)
    for participant in dict.fromkeys(name for name, _ in LIFECYCLE_MANIFEST)
}

# ModelEvidence (BR6.11): the purpose of each pinned model.
MODEL_PURPOSES = {"bge-m3:latest": "embedding", "qwen3:8b": "assistance"}
MODEL_EVIDENCE: tuple[tuple[str, str, str], ...] = tuple(
    (model, MODEL_PURPOSES[model], MODEL_PINS[model]) for model in sorted(MODEL_PINS)
)


@dataclass(frozen=True)
class Manifest:
    contributions: tuple[Contribution, ...]
    capabilities: tuple[Capability, ...]
    navigation: tuple[NavigationEntry, ...]
    lifecycle: tuple[tuple[str, str], ...]
    model_evidence: tuple[tuple[str, str, str], ...]
    revision: str = field(default="")

    def entries(self) -> dict:
        return {
            "contributions": [asdict(entry) for entry in self.contributions],
            "capabilities": [asdict(entry) for entry in self.capabilities],
            "navigation": [asdict(entry) for entry in self.navigation],
            "lifecycle": [list(pair) for pair in self.lifecycle],
            "lifecycleRevision": LIFECYCLE_REVISION,
            "modelEvidence": [list(item) for item in self.model_evidence],
        }

    def computed_revision(self) -> str:
        return digest(self.entries())

    def sealed(self) -> Manifest:
        return Manifest(
            self.contributions, self.capabilities, self.navigation, self.lifecycle,
            self.model_evidence, self.computed_revision(),
        )

    def contribution(self, contribution_id: str) -> Contribution:
        for entry in self.contributions:
            if entry.contribution_id == contribution_id:
                return entry
        raise KeyError(contribution_id)

    def verify(self) -> Manifest:
        """BR1.1: every contribution exactly once, every capability with one owning
        contribution, and a revision equal to the digest of all entries."""
        ids = [entry.contribution_id for entry in self.contributions]
        if len(ids) != len(set(ids)):
            raise ManifestRefused("the manifest repeats a contribution")
        if set(ids) != set(CONTRIBUTION_IDS):
            raise ManifestRefused("the manifest lacks a contribution or names an unknown one")
        if self.revision != self.computed_revision():
            raise ManifestRefused("the manifest revision differs from its entries' digest")
        provided = [cap for entry in self.contributions for cap in entry.provides]
        registered = [cap.capability_id for cap in self.capabilities]
        if len(provided) != len(set(provided)) or sorted(provided) != sorted(registered):
            raise ManifestRefused("each capability belongs to exactly one contribution")
        for entry in self.contributions:
            if any(name not in ids for name in entry.requires):
                raise ManifestRefused("a contribution requires one the manifest lacks")
        if any(entry.routes for entry in self.contributions
               if entry.contribution_id == "platform-control"):
            raise ManifestRefused("platform-control mounts no browser route")
        if len(self.lifecycle) > LIFECYCLE_PAIR_BOUND or len(set(self.lifecycle)) != len(
            self.lifecycle
        ):
            raise ManifestRefused("the lifecycle manifest exceeds its bound or repeats a pair")
        if any(nav.capability_id not in registered for nav in self.navigation):
            raise ManifestRefused("a navigation entry names an unregistered capability")
        dependency_order(self)
        return self


def dependency_order(manifest: Manifest) -> tuple[Contribution, ...]:
    """The contributions in dependency order; a cycle is refused."""
    ordered, placed = [], set()
    pending = list(manifest.contributions)
    while pending:
        ready = [entry for entry in pending if set(entry.requires) <= placed]
        if not ready:
            raise ManifestRefused("the contributions' requirements form a cycle")
        for entry in ready:
            ordered.append(entry)
            placed.add(entry.contribution_id)
            pending.remove(entry)
    return tuple(ordered)


# The owners that hand ServiceOperations work through ports and must never import it
# (security-design § 13, D12): the component graph stays as components.md has it.
# `backend/u8_topics.py` does TopicsDigests' live work, so it is held to the same rule,
# and so are the three modules that do ResearchWorkspace's production work and run the
# model lane (your decision of 2026-10-24, "Build the research executor").
PORT_OWNERS = (
    "backend/modules/accounts", "backend/modules/topics", "backend/u8_topics.py",
    "backend/u8_research.py", "backend/u8_research_model.py", "backend/u8_model_lane.py",
)
OPERATIONS_MODULE = "backend.modules.operations"


def _imported_names(tree, module: str) -> set[str]:
    """Every module name a parsed file imports, relative imports resolved, plus string
    literals that name a module (an `importlib` call)."""
    import ast

    package = module.rsplit(".", 1)[0]
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                parts = package.split(".")
                base = parts[: len(parts) - node.level + 1]
                origin = ".".join(base + ([node.module] if node.module else []))
            else:
                origin = node.module or ""
            names.add(origin)
            names.update(f"{origin}.{alias.name}" for alias in node.names)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            names.add(node.value)
    return names


def import_boundary_violations(root: Path = ROOT) -> list[str]:
    """The files under the port owners that import ServiceOperations, sorted."""
    import ast

    violations = []
    for entry in PORT_OWNERS:
        place = root / entry
        # As an absent folder yields no file, an absent file imports nothing.
        if entry.endswith(".py"):
            paths = [place] if place.is_file() else []
        else:
            paths = sorted(place.rglob("*.py"))
        for path in paths:
            relative = path.relative_to(root)
            module = ".".join(relative.with_suffix("").parts)
            names = _imported_names(ast.parse(path.read_bytes(), str(relative)), module)
            if any(name == OPERATIONS_MODULE or name.startswith(OPERATIONS_MODULE + ".")
                   for name in names):
                violations.append(str(relative))
    return violations


def verify_import_boundaries(root: Path = ROOT) -> None:
    """The complete assembly's import check: refused when an owner that reaches
    ServiceOperations only through a port imports it."""
    violations = import_boundary_violations(root)
    if violations:
        raise ManifestRefused("an owner imports ServiceOperations: " + ", ".join(violations))


MANIFEST = Manifest(CONTRIBUTIONS, CAPABILITIES, NAVIGATION, LIFECYCLE_MANIFEST, MODEL_EVIDENCE)
MANIFEST = MANIFEST.sealed().verify()
MANIFEST_REVISION = MANIFEST.revision
CAPABILITY_BY_ID = {capability.capability_id: capability for capability in CAPABILITIES}
