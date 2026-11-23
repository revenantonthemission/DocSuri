"""The complete assembly's outward providers in production (U8 plan Step 21; BR7.1–BR7.6,
BR9.4, D12).

The digest and export production builders select their policy by the profile's mode:

- rehearsal: `PRODUCTION_REHEARSAL_TOPICS` (only the maintainer's address, within the
  1–100 check) and U6's real activation (only its activation page);
- live: `PRODUCTION_LIVE_TOPICS` (every consenting subscriber once Resend is active,
  each send spending the email allowance) and `production_live_export` (any page the
  owner's own connection can read).

Either way ServiceOperations' `ProviderActivation` is the provider gate, the rehearsal
recipients and the first-effects port, so U5's and U6's bounds lift only in live mode,
once the provider is active there (BR7.6), and nothing leaves while it is held (BR7.3).
Notion's process-wide gate is that activation behind `ObservedNotionGate`, the circuit
breaker that answers `unavailable` for Notion while provider.notion is observed
unavailable (reliability-design § 10, L2-13). Search's embedder sits behind a breaker
over provider.models in the same way (`install_search_breaker`, L3-7). By L4-11 every
other call site follows its provider's observed state too: the shared model runtime's own
client (`install_models_breaker`), Google and ORCID sign-in (`sign_in_gate`) and digests
(`digest_gate`, `install_digest_breaker`). Every breaker reads its state through
`read_state`, where a read that raises reads `unknown` and holds nothing.

U6's first export is held by the session (its background work waits) and previewed by
this module's `FirstExportPreviews`: a U8-owned pass that, while Notion is held in live
mode, records each of the maintainer's waiting exports as the held first effect's
preview, from the effect's bound content (`StoreContentPort`), the exact frozen tree the
one write would send. U5's held first effect is recorded by its own scheduler.

A synthetic profile never reaches this module (BR7.1).
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable
from dataclasses import dataclass

from .modules.accounts.integrations.provider_gate import preview_bytes

# Settings read from the profile's private environment, beside the provider secrets.
DIGEST_SENDER = "digestSender"
# How long one digest's cancellation link stays valid from its send. The approved files
# fix no production value; this matches the longest receipt retention (30 days).
UNSUBSCRIBE_LIFETIME = dt.timedelta(days=30)
PREVIEW_BATCH = 10


def _refused(reason: str):
    from .u8_host import PolicyUnresolved

    return PolicyUnresolved(reason)


def production_gate(ctx) -> dict:
    """ServiceOperations' parts that carry the provider gate, the rehearsal recipients,
    the first-effects port and the email allowance. Every outward production builder
    calls it first and fails closed: without the gate it raises `PolicyUnresolved`, so
    its contribution is unavailable and nothing it would send can leave (U6's re-check,
    Major)."""
    operations = ctx.parts.get("service-operations")
    if (
        operations is None
        or operations.get("activation") is None
        or operations.get("allowance") is None
    ):
        raise _refused("the provider gate is not composed")
    return operations


def read_state(capability: str, capability_states: Callable[[], dict[str, dict]]) -> str:
    """The one way a circuit breaker reads its capability's derived state (L4-11; review
    08's R-17): a read that raises reads `unknown`, which holds nothing, and logs one
    event with the capability and the error's type, never its content."""
    try:
        return capability_states()[capability]["state"]
    except Exception as error:  # noqa: BLE001 - an unreadable state shows no outage
        from .log_events import log_exception

        log_exception("operations", "breaker.state-unreadable", error, reason=capability)
        return "unknown"


@dataclass(frozen=True)
class ObservedState:
    """One capability's state through `read_state`, as a breaker's reader. Two readers of
    the same capability over the same states are equal, so a second wiring installs
    nothing new."""

    capability: str
    states: Callable[[], dict[str, dict]]

    def __call__(self) -> str:
        return read_state(self.capability, self.states)


class ObservedNotionGate:
    """Notion's circuit breaker over the activation (reliability-design § 10, lines
    131-137; L2-13), the `ProviderGate` port: for `notion` it answers `unavailable` while
    provider.notion is observed `unavailable`, and otherwise, and for every other
    provider, the activation's own answer. The observation is read afresh on each ask
    about `notion` only, so calls resume once the probe passes; `unknown` and `stale`
    fail open, as Resend's rule does."""

    def __init__(self, activation, observed: Callable[[], str]) -> None:
        self.activation = activation
        self._observed = observed

    @property
    def mode(self) -> str:
        return self.activation.mode

    def state(self, provider: str) -> str:
        if provider == "notion" and self._observed() == "unavailable":
            return "unavailable"
        return self.activation.state(provider)


def notion_gate(activation, capability_states: Callable[[], dict[str, dict]] | None):
    """Notion's process-wide gate: the activation itself without the composition's
    derived states, else the breaker reading provider.notion's state as the operations
    page shows it."""
    if capability_states is None:
        return activation
    return ObservedNotionGate(activation, ObservedState("provider.notion", capability_states))


# The providers whose gate follows its capability's observed state (L4-11).
SIGN_IN_PROVIDERS = ("google", "orcid")
DIGEST_PROVIDERS = ("resend",)


class ObservedProviderGate:
    """A circuit breaker over the activation for the providers it names
    (reliability-design § 10, lines 133-137 and 141-143; L4-11), the `ProviderGate` port.
    For one of its providers it answers `unavailable` while that provider's capability is
    observed `unavailable`; otherwise, for every other provider, and for everything else
    the activation offers (the rehearsal recipients, the first-effects port), it is the
    activation. The observation is read afresh on each ask, so calls resume once the
    probe passes; `unknown` and `stale` fail open, as Notion's breaker does. `observed`
    takes a capability's name; without one (not bound yet, or no derived states) the gate
    is the activation's own answer."""

    def __init__(self, activation, providers: tuple[str, ...],
                 observed: Callable[[str], str] | None = None) -> None:
        self.activation = activation
        self.providers = frozenset(providers)
        self._observed = observed

    def bind(self, observed: Callable[[str], str] | None) -> None:
        """The reader, set once the composition's derived states exist (the digest gate
        is built before them)."""
        self._observed = observed

    @property
    def mode(self) -> str:
        return self.activation.mode

    def state(self, provider: str) -> str:
        if (provider in self.providers and self._observed is not None
                and self._observed("provider." + provider) == "unavailable"):
            return "unavailable"
        return self.activation.state(provider)

    def __getattr__(self, name: str):
        if name == "activation":
            raise AttributeError(name)
        return getattr(self.activation, name)


def state_reader(capability_states: Callable[[], dict[str, dict]]) -> Callable[[str], str]:
    """A named capability's state through `read_state`, as `ObservedProviderGate` reads."""
    return lambda capability: read_state(capability, capability_states)


def sign_in_gate(activation, capability_states: Callable[[], dict[str, dict]] | None):
    """The entry's `identity_gate`: the activation itself without the composition's
    derived states, else the breaker that answers `unavailable` for Google or ORCID while
    provider.google or provider.orcid is observed unavailable, so a sign-in or link is
    refused at its start before anything is written, and at its completion before the
    token exchange (`ArrivalIdentityService`)."""
    if capability_states is None:
        return activation
    return ObservedProviderGate(activation, SIGN_IN_PROVIDERS, state_reader(capability_states))


def digest_gate(activation) -> ObservedProviderGate:
    """Resend's gate for digests, one object for the adapter and the scheduler. It is
    built with the contribution, before the composition's derived states exist, so its
    reader is bound afterwards (`install_digest_breaker`); until then it is the
    activation's own answer."""
    return ObservedProviderGate(activation, DIGEST_PROVIDERS)


def install_digest_breaker(parts: dict, capability_states) -> None:
    """Binds the digest gate to provider.resend's derived state, so due digests stay
    prepared and nothing is reserved while Resend is observed unavailable."""
    gate = (parts.get("topics-digests") or {}).get("gate")
    if capability_states and isinstance(gate, ObservedProviderGate):
        gate.bind(state_reader(capability_states))


def install_models_breaker(parts: dict, capability_states) -> None:
    """Sets the shared model runtime's reader to provider.models' derived state, so every
    request to the runtime (research, paper assistance, the corpus embedder) passes the
    one breaker in the client (`SharedModelRuntime.held`). A second wiring over the same
    states installs nothing new."""
    runtime = (parts.get("paper-corpus") or {}).get("runtime")
    if not capability_states or not callable(getattr(runtime, "held", None)):
        return
    reader = ObservedState("provider.models", capability_states)
    if runtime.observed != reader:
        runtime.observed = reader


class ObservedSearchEmbeddings:
    """Search's circuit breaker over the model runtime (reliability-design § 10, lines
    133-137 and 145; L3-7): while provider.models is observed `unavailable`, a query
    embedding raises `ModelUnavailable` before any runtime call, so `CompleteSearch`
    answers by words (`semantic-search-unavailable`). The observation is read afresh on
    every semantic query, so calls resume once the probe passes; `unknown` and `stale`
    fail open, as Notion's breaker does. Search never embeds batches, so none is
    offered. The embedder's runtime carries a breaker of its own over the same state
    (L4-11); this call is marked as already checked (`SharedModelRuntime.checked`), so a
    semantic query still costs one state read."""

    def __init__(self, embedder, observed: Callable[[], str]) -> None:
        self.embedder = embedder
        self._observed = observed

    def embed_query(self, text: str) -> list[float]:
        if self._observed() == "unavailable":
            from docsuri_ops.local_models import ModelUnavailable

            raise ModelUnavailable("provider.models is observed unavailable")
        checked = getattr(getattr(self.embedder, "runtime", None), "checked", None)
        if not callable(checked):
            return self.embedder.embed_query(text)
        with checked():
            return self.embedder.embed_query(text)


def search_breaker(embedder, capability_states: Callable[[], dict[str, dict]] | None):
    """Search's embedder: the embedder itself without the composition's derived states,
    else the breaker reading provider.models' state as the operations page shows it."""
    if capability_states is None:
        return embedder
    return ObservedSearchEmbeddings(embedder, ObservedState("provider.models", capability_states))


def install_search_breaker(parts: dict, capability_states) -> None:
    """Puts the paper corpus's search behind the breaker over its bare embedder, so a
    second wiring never stacks a second layer; the corpus's own `embedder`, which
    research's ranking and imports use, stays bare."""
    corpus = parts.get("paper-corpus") or {}
    if not (capability_states and corpus.get("search") and corpus.get("embedder")):
        return
    corpus["search"].embedder = search_breaker(corpus["embedder"], capability_states)


# --- CorpusContent, DiscoveryCitations and PaperAssistance --------------------------------

# Production embeds with the pinned model, resident, within 2 s for a query and in
# batches of 16 for an import (performance-design § 3.3, U8 plan Step 31).
EMBEDDING_KEEP_ALIVE, QUERY_SECONDS, EMBEDDING_BATCH = -1, 2.0, 16
# Where the production environment tool's `readiness-evidence` word records PaperAssistance's
# reviewed real-model evidence (BR7.7, Step 37); the executor runs only once it is there.
READINESS_MARKER = ("evidence", "model-readiness.json")


class ImportedSources:
    """Production's corpus sources: the corpus grows only through the migration's
    imports (`importPaper`, A4); no outward source is fetched ($0, BR7.1)."""

    def read(self, source_id: str):
        from .modules.corpus.maintenance import SourceUnavailable

        raise SourceUnavailable("production corpus sources are the migration's imports")


class NoCitationProvider:
    """Production has no external citation provider ($0): exploration answers that the
    citation coverage is unavailable."""

    def read(self, root_version, direction, *, max_nodes, max_depth, max_requests) -> dict:
        from .modules.discovery.citations import ProviderUnavailable

        raise ProviderUnavailable("no citation provider is configured")


MARKER_PURPOSES = frozenset({"assistance", "research"})
MARKER_BYTES = 4096


def model_readiness(profile, purpose: str, *, now: dt.datetime | None = None) -> bool:
    """The one readiness marker (BR7.7; your decision of 2026-10-24). The reviewed
    real-model evidence is ready for `purpose` only when `evidence/model-readiness.json`
    holds exactly `models`, `purposes` and `recordedAt`; `models` equals the release's
    pins; `purposes` is a non-empty object mapping `assistance` and/or `research`, each to
    its own 64-hex evidence digest (the two reviews are separate evidence), and names the
    purpose asked; and `recordedAt` is a timezone-aware time not in the future. Any other
    shape, or a marker that cannot be read privately, is not ready."""
    import json
    import re

    from docsuri_ops.local_models import MODEL_PINS

    from .local_profile import private_bytes

    if purpose not in MARKER_PURPOSES:
        raise ValueError("unknown readiness purpose")
    try:
        value = json.loads(private_bytes(profile.root.joinpath(*READINESS_MARKER),
                                         maximum=MARKER_BYTES))
    except (OSError, ValueError, TypeError):
        return False
    if not isinstance(value, dict) or set(value) != {"models", "purposes", "recordedAt"}:
        return False
    if value["models"] != MODEL_PINS:
        return False
    purposes = value["purposes"]
    if (
        not isinstance(purposes, dict)
        or not purposes
        or not set(purposes) <= MARKER_PURPOSES
        or purpose not in purposes
        or not all(isinstance(item, str) and re.fullmatch(r"[0-9a-f]{64}", item)
                   for item in purposes.values())
    ):
        return False
    try:
        recorded = dt.datetime.fromisoformat(value["recordedAt"])
    except (TypeError, ValueError):
        return False
    if recorded.tzinfo is None or recorded.utcoffset() is None:
        return False
    return recorded <= (now or dt.datetime.now(dt.UTC))


def readiness_recorded(profile, purpose: str = "assistance") -> Callable[[], bool]:
    """The marker read for one purpose, as the executors and producers take it."""

    def ready() -> bool:
        return model_readiness(profile, purpose)

    return ready


def production_corpus(ctx, *, runtime=None) -> dict:
    """The production corpus: production limits, imports as its only sources, search on
    the pinned query embedder, and PaperAssistance's real executor on the shared model
    runtime (A7, BR7.7, P1, P2)."""
    from .artifacts import PrivateArtifacts
    from .modules.corpus.limits import PRODUCTION_LIMITS
    from .modules.corpus.maintenance import CorpusMaintenance
    from .modules.corpus.reading import CorpusReading
    from .modules.corpus.repository import CorpusRepository
    from .modules.discovery.citations import CitationExplorer
    from .modules.discovery.guarded_repository import GuardedDiscoveryRepository
    from .modules.discovery.local_embedding import LocalEmbeddings
    from .modules.discovery.u8_search import CompleteSearch
    from .modules.library.u3_dispositions import SavedReferenceDispositions
    from .modules.library.u3_history import U3HistoryConsumer
    from .modules.summarization.model_runtime import (
        ProductionAssistanceExecutor,
        SharedModelRuntime,
    )
    from .modules.summarization.u8_assistance_sources import ProductionAssistanceRule
    from .u3_host import U3ControlWorker
    from .u8_host import read_cursor_key

    if not getattr(ctx.profile, "is_production", False):
        raise _refused("a synthetic profile composes no production corpus")
    transactions, profile = ctx.transactions, ctx.profile
    runtime = runtime or SharedModelRuntime()
    files = PrivateArtifacts.for_profile(profile, "corpus-files",
                                         maximum_bytes=PRODUCTION_LIMITS.max_source_bytes)
    maintenance = CorpusMaintenance(transactions, files, ImportedSources(),
                                    limits=PRODUCTION_LIMITS)
    embedder = LocalEmbeddings(runtime, keep_alive=EMBEDDING_KEEP_ALIVE,
                               query_seconds=QUERY_SECONDS, batch=EMBEDDING_BATCH)
    search = CompleteSearch(
        transactions, GuardedDiscoveryRepository(transactions), U3HistoryConsumer(transactions),
        cursor_key=read_cursor_key(profile), embedder=embedder,
    )
    # Paper assistance at production's corpus limits (Step 23, "Fix it in U8"): up to
    # 200 chunks per paper (lowered by your decision of 2026-11-08, L1-74, measured again
    # by your answer of 2026-11-09, L1-81, provisional until the first dry run), a split
    # block's pieces offered and cited as that block.
    ready = readiness_recorded(profile, "assistance")
    rule = ProductionAssistanceRule(ready)
    from .modules.plans.u8_usage import use_complete_usage
    from .u8_job_lines import CompleteAssistanceDispatch

    # U2's controls for all usage (your decision of 2026-10-23): no self-granted usage.
    # The workers' job lines (Step 51(d), L1-6) come from the dispatch's per-item hook.
    dispatch = use_complete_usage(CompleteAssistanceDispatch(
        transactions, files, ProductionAssistanceExecutor(runtime, ready=ready),
        payload_rule=rule.payload), transactions)
    dispositions = SavedReferenceDispositions(transactions)
    return {
        "assistance_rule": rule,
        "files": files, "maintenance": maintenance, "reading": CorpusReading(transactions),
        "search": search, "citations": CitationExplorer(transactions, NoCitationProvider()),
        "dispatch": dispatch, "dispositions": dispositions,
        "corpus_repository": CorpusRepository(transactions, files=None),
        "worker": U3ControlWorker(maintenance, dispatch, dispositions, dispatch.admission),
        "embedder": embedder, "runtime": runtime,
    }


# --- TopicsDigests ------------------------------------------------------------------------


def topics_policy(profile):
    from .u8_topics import PRODUCTION_LIVE_TOPICS, PRODUCTION_REHEARSAL_TOPICS

    if not getattr(profile, "is_production", False):
        raise _refused("a synthetic profile composes no production policy")
    return PRODUCTION_LIVE_TOPICS if profile.mode == "live" else PRODUCTION_REHEARSAL_TOPICS


def _rolling_unsubscribe():
    from .modules.topics.unsubscribe import EmailUnsubscribe

    class RollingUnsubscribe(EmailUnsubscribe):
        """U5's cancellation capability, each link valid for `lifetime` from its send:
        the production process runs without an end, unlike a realm."""

        def __init__(self, transactions, *, origin: str, clock: Callable[[], dt.datetime],
                     lifetime: dt.timedelta = UNSUBSCRIBE_LIFETIME):
            super().__init__(transactions, origin=origin, expires_at=clock() + lifetime)
            self._clock, self._lifetime = clock, lifetime

        def issue(self, run_id):
            self.expires_at = self._clock() + self._lifetime
            return super().issue(run_id)

    return RollingUnsubscribe


def maintainer_address(transactions, profile, *, required: bool = True) -> str | None:
    """The maintainer's verified address, found by the v2 account the profile names; the
    rehearsal bound compares accounts, and this address only scopes U5's own queue.
    Without one, `required` refuses (live mode) and otherwise None is returned (rehearsal
    holds every run until it exists)."""
    from .modules.topics.repository import TopicsRepository

    account = getattr(profile, "maintainer_account", None)
    recipient = None if account is None else TopicsRepository(transactions).digest_recipient(
        account)
    if recipient is None or not recipient["email"]:
        if required:
            raise _refused("the maintainer's account has no address yet")
        return None
    return recipient["email"]


def digest_mail(environment: dict, *, origin: str, maintainer: str, activation, account_of,
                client_factory=None, gate=None):
    """U5's Resend adapter behind the gate, or the held adapter while Resend is
    unconfigured (BR6.7, BR7.2). `client_factory` (Step 56(c), L1-12) is the counting
    wrapper over the shared Resend client, which the adapter already takes. `gate` is the
    gate the adapter reads (the digest breaker in production, L4-11; the activation
    without one). Which adapter is built is decided on the bare activation, so a start
    during an observed outage does not keep the held adapter afterwards."""
    from .modules.accounts.integrations.u8_digest_mail import (
        GatedResendDigestMail,
        HeldDigestMail,
    )
    from .u8_host import PROVIDER_SECRETS

    key = environment.get(PROVIDER_SECRETS["provider.resend"])
    sender = environment.get(DIGEST_SENDER)
    gate = activation if gate is None else gate
    if activation.state("resend") == "unavailable" or not (
        isinstance(key, str) and key and isinstance(sender, str) and sender
    ):
        return HeldDigestMail(permitted_recipient=maintainer, gate=gate)
    return GatedResendDigestMail(
        api_key=key, sender=sender, unsubscribe_url=origin, permitted_recipient=maintainer,
        gate=gate, recipients=activation, account_of=account_of,
        client_factory=client_factory,
    )


def topics_parts(transactions, entry, corpus, inherited_worker, *, policy, mail, unsubscribe,
                 activation, allowance=None, gate=None) -> dict:
    """U5's contribution parts, as `u5_host.topics_contribution` builds them, with U8's
    live parts: `LiveDigestDelivery` under the live policy (U5's `DigestDelivery`
    otherwise), then `GatedTopicsScheduler` with the gate and the first-effects port.
    `gate` is the gate the scheduler reads, the same object as the adapter's (the digest
    breaker in production; the activation without one)."""
    from fastapi import APIRouter

    from .modules.personalization.local_http import settings_router
    from .modules.topics.delivery import DigestDelivery
    from .modules.topics.http import topics_router
    from .modules.topics.preparation import DigestPreparation
    from .modules.topics.service import TopicsService
    from .modules.topics.unsubscribe import unsubscribe_router
    from .u5_host import TopicsWorker, digest_capability
    from .u8_topics import GatedTopicsScheduler, LiveDigestDelivery, is_live

    service = TopicsService(transactions)
    preparation = DigestPreparation(transactions, corpus, policy=policy)
    if is_live(policy):
        delivery = LiveDigestDelivery(transactions, corpus, policy=policy, mail=mail,
                                      unsubscribe=unsubscribe, allowance=allowance)
    else:
        delivery = DigestDelivery(transactions, corpus, policy=policy, mail=mail,
                                  unsubscribe=unsubscribe)
    scheduler = GatedTopicsScheduler(
        transactions, preparation, delivery, policy=policy,
        gate=activation if gate is None else gate, recipients=activation,
        first_effects=activation,
    )
    router = APIRouter()
    router.include_router(topics_router(transactions, entry=entry, service=service))
    router.include_router(settings_router(transactions, entry=entry))
    router.include_router(unsubscribe_router(unsubscribe))
    return {
        "service": service,
        "delivery": delivery,
        "scheduler": scheduler,
        "capabilities": [digest_capability(policy, delivery)],
        "router": router,
        "worker": TopicsWorker(inherited_worker, scheduler),
    }


def production_topics(ctx) -> dict:
    """The production TopicsDigests: its policy for the mode, Resend behind the gate. The
    adapter and the scheduler read one digest gate (`digest_gate`), returned as the
    contribution's `gate` for the composition to bind to provider.resend's state."""
    from .u8_host import private_environment

    operations = production_gate(ctx)
    controls = ctx.parts.get("account-controls")
    if controls is None:
        raise _refused("the account controls are not composed")
    policy = topics_policy(ctx.profile)
    activation = operations["activation"]
    gate = digest_gate(activation)
    live = ctx.profile.mode == "live"
    maintainer = maintainer_address(ctx.transactions, ctx.profile, required=live)
    if maintainer is None:
        # Rehearsal before the maintainer has an address (BR7.5; your decision of
        # 2026-10-24): the held adapter that permits nobody, so every run stays prepared
        # and `topics.digest` reads degraded with `maintainer-address-pending`.
        from .modules.accounts.integrations.u8_digest_mail import AddressPendingDigestMail

        mail = AddressPendingDigestMail(gate=gate)
    else:
        from .u8_host import process_counts
        from .u8_provider_probes import counting_client_factory, resend_client

        mail = digest_mail(
            private_environment(ctx.profile), origin=ctx.profile.origin,
            maintainer=maintainer, activation=activation,
            account_of=controls["entry"].account_of,
            client_factory=counting_client_factory(
                resend_client, "provider.resend", process_counts(ctx.transactions)),
            gate=gate,
        )
    unsubscribe = _rolling_unsubscribe()(ctx.transactions, origin=ctx.profile.origin,
                                          clock=ctx.clock)
    parts = topics_parts(
        ctx.transactions, ctx.parts["paper-journey"]["entry"],
        ctx.parts["paper-corpus"]["corpus_repository"],
        ctx.parts["research-workspace"]["worker"],
        policy=policy, mail=mail, unsubscribe=unsubscribe, activation=activation,
        allowance=operations["allowance"], gate=gate,
    )
    parts["limitation"] = getattr(mail, "limitation", None)
    parts["gate"] = gate
    return parts


# --- ApprovedExport -----------------------------------------------------------------------


def export_policy(profile, activation_settings):
    """U6's bounded real activation in rehearsal; the live policy in live mode."""
    from .u6_policy import production_live_export
    from .u6_real_export import real_policy

    if not getattr(profile, "is_production", False):
        raise _refused("a synthetic profile composes no production policy")
    if profile.mode == "live":
        return production_live_export(
            free_terms_reference=activation_settings.free_terms_reference)
    return real_policy(activation_settings)


def production_export(ctx) -> dict:
    """The production ApprovedExport over the network transport: its settings are U6's
    run-bound `real-export.json` in the profile (its activation page, used in rehearsal
    only, and the free-terms evidence); the session reads the provider gate. It requires
    only `research-workspace` and `topics-digests`, so it checks the gate itself: without
    ServiceOperations it is unavailable, never an export the gate cannot hold."""
    from .modules.export.errors import ExportError
    from .u6_host import export_contribution
    from .u6_real_export import load_activation

    if not getattr(ctx.profile, "is_production", False):
        raise _refused("a synthetic profile composes no production export")
    production_gate(ctx)
    try:
        settings = load_activation(ctx.profile)
        policy = export_policy(ctx.profile, settings)
    except ExportError:
        raise _refused("the export settings are not resolved") from None
    from .u8_host import process_counts
    from .u8_job_lines import with_export_item_lines
    from .u8_provider_probes import counting_transport_factory, notion_transport

    # Step 56(c) (L1-12): a new counting transport over Notion's one network builder for
    # every operation, through U6's documented seam, which the real policy accepts
    # (`u6_host.bound_transport`); the session still wraps each in `GuardedTransport`.
    factory = counting_transport_factory(notion_transport, "provider.notion",
                                         process_counts(ctx.transactions))
    # The workers' job lines (Step 51(d), L1-6) on the lane the contribution returns.
    return with_export_item_lines(export_contribution(
        ctx.transactions, ctx.parts["paper-journey"]["entry"],
        ctx.parts["paper-corpus"]["corpus_repository"],
        ctx.parts["topics-digests"]["worker"],
        research=ctx.parts["research-workspace"]["service"],
        policy=policy, transport_factory=factory, clock=ctx.clock,
    ), ctx.transactions)


def export_preview(bound) -> bytes:
    """The exact content the one write would send: the bound destination, marker, content
    hash and frozen block tree (D12), canonical."""
    return preview_bytes({
        "provider": "notion",
        "destinationId": bound.destination_id,
        "marker": bound.marker,
        "contentHash": bound.content_hash,
        "body": bound.body,
    })


class FirstExportPreviews:
    """The U8-owned pass of the held first export (BR7.3): while Notion is held in live
    mode, each of the maintainer's waiting exports is recorded as a preview from its bound
    content. It runs in the workers' pass, reads only U6's own store and content port,
    and writes only the owner-only preview file."""

    def __init__(self, repository, content, activation, *, clock: Callable[[], dt.datetime],
                 batch: int = PREVIEW_BATCH):
        if not 1 <= batch <= 100:
            raise ValueError("a bounded preview batch is required")
        self.repository, self.content, self.activation = repository, content, activation
        self.clock, self.batch = clock, batch

    def run_once(self, limit: int = 1) -> dict:
        del limit  # bounded by its own batch
        if self.activation.mode != "live" or self.activation.state("notion") != "held":
            return {"recorded": 0}
        recorded = []
        for row in self.repository.due_items(self.clock(), limit=self.batch):
            if row["kind"] != "execute" or not self.activation.is_maintainer_account(
                row["account_id"]
            ):
                continue
            bound = self.content.bound_content(row["id"])
            if bound is not None:
                recorded.append(self.activation.record_preview("notion", export_preview(bound)))
        return {"recorded": len(recorded)}


def first_export_previews(composition):
    """The pass for a production composition with ApprovedExport, else None."""
    if not getattr(composition.profile, "is_production", False):
        return None
    export = composition.parts.get("approved-export")
    operations = composition.parts.get("service-operations")
    if export is None or operations is None:
        return None
    from .modules.export.notion_adapter import StoreContentPort

    repository = export["repository"]
    return FirstExportPreviews(repository, StoreContentPort(repository), operations["activation"],
                               clock=composition.clock)
