"""U3 assembled corpus workspace: capability catalogue, owner routers and the
single supervised control loop.

One local application release hosts the embedded U3 contribution (CorpusContent,
Discovery, PaperAssistance) on the shared host; no second service, broker or
store is introduced. Capability states distinguish the installed synthetic
provider from the real model/permission gates that remain unresolved, so no
placeholder ever claims real readiness (NFR7.1, NFR9.2).
"""

from __future__ import annotations

import hashlib
import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from .local_observation import observe_all, record
from .local_profile import LocalProfile, private_bytes
from .transactions import OWNERS
from .u3_policy import (
    ASSISTANCE_POLICY,
    CITATION_POLICY,
    CORPUS_POLICY,
    ELIGIBILITY_POLICY,
    GLOSSARY_POLICY,
    READING_POLICY,
    SEARCH_POLICY,
    limits_document,
)

U3_POLICY = {"policyId": "u3-synthetic-v1", "revision": "1"}


def catalog_revision(catalog) -> str:
    return hashlib.sha256(
        json.dumps(catalog, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def u3_capabilities(*, provider_installed: bool) -> list[dict]:
    """Safe public capability states; unresolved real gates stay explicit."""
    return [
        {
            "id": "corpus.maintenance",
            "state": "available",
            "modeIds": ["ingest", "incremental-refresh", "rebuild", "reprocess"],
            "languageIds": ["en", "ko"],
            "levelIds": ["synthetic-only"],
            "formatIds": ["json"],
            "policy": CORPUS_POLICY,
        },
        {
            "id": "corpus.eligibility",
            "state": "available",
            "modeIds": ["withdrawal", "license-change", "access-change"],
            "languageIds": ["en", "ko"],
            "levelIds": ["synthetic-only"],
            "formatIds": ["json"],
            "policy": ELIGIBILITY_POLICY,
        },
        {
            "id": "discovery.search",
            "state": "available",
            "modeIds": ["lexical", "semantic"],
            "languageIds": ["en", "ko"],
            "levelIds": ["list"],
            "formatIds": ["json"],
            "policy": SEARCH_POLICY,
        },
        {
            "id": "corpus.reading",
            "state": "available",
            "modeIds": ["section"],
            "languageIds": ["en"],
            "levelIds": ["full"],
            "formatIds": ["json"],
            "policy": READING_POLICY,
        },
        {
            "id": "discovery.citations",
            "state": "available",
            "modeIds": ["cited", "citing", "both"],
            "languageIds": ["en"],
            "levelIds": ["bounded"],
            "formatIds": ["json"],
            "policy": CITATION_POLICY,
        },
        {
            "id": "assistance.summary",
            "state": "available" if provider_installed else "unavailable",
            "modeIds": ["synthetic-extractive"] if provider_installed else [],
            "languageIds": ["en"],
            "levelIds": ["selected-source"],
            "formatIds": ["json"],
            "policy": ASSISTANCE_POLICY,
        },
        {
            "id": "assistance.translation",
            "state": "available" if provider_installed else "unavailable",
            "modeIds": ["synthetic-extractive"] if provider_installed else [],
            "languageIds": ["en", "ko"],
            "levelIds": ["selected-source"],
            "formatIds": ["json"],
            "policy": ASSISTANCE_POLICY,
        },
        {
            "id": "assistance.glossary",
            "state": "available",
            "modeIds": ["normalized-cas"],
            "languageIds": ["en", "ko"],
            "levelIds": ["owner"],
            "formatIds": ["json"],
            "policy": GLOSSARY_POLICY,
        },
        {
            # The real model path remains gated behind P1/P2 evidence; this row
            # never becomes available from the synthetic provider fixture.
            "id": "assistance.model",
            "state": "policy_pending",
            "modeIds": [],
            "languageIds": ["en", "ko"],
            "levelIds": ["P1-P2-evidence-required"],
            "formatIds": ["json"],
            "policy": ASSISTANCE_POLICY,
        },
        {
            "id": "corpus.public",
            "state": "policy_pending",
            "modeIds": [],
            "languageIds": ["en", "ko"],
            "levelIds": ["permission-evidence-required"],
            "formatIds": ["json"],
            "policy": CORPUS_POLICY,
        },
    ]


class FixtureSourceProvider:
    """Private run-owned source fixtures with recorded identity and checksums.

    This is the synthetic realm's source adapter. The manifest records the
    fixture set and its checksums; a record whose bytes no longer match is a
    failed prerequisite, never a silent substitute.
    """

    def __init__(self, root: Path):
        self.root = root
        self.manifest = self._load_manifest()

    def _load_manifest(self) -> dict:
        directory = self.root / "corpus-sources"
        manifest_path = directory / "manifest.json"
        if not manifest_path.exists():
            return {"revision": "empty", "sources": {}}
        value = json.loads(private_bytes(manifest_path, maximum=65536))
        if not isinstance(value, dict) or not isinstance(value.get("sources"), dict):
            raise ValueError("source fixture manifest malformed")
        return value

    def read(self, source_id: str) -> dict | None:
        if not isinstance(source_id, str) or not 1 <= len(source_id) <= 160:
            return None
        entry = self.manifest["sources"].get(source_id)
        if entry is None:
            return None
        path = self.root / "corpus-sources" / entry["file"]
        raw = private_bytes(path, maximum=2097152)
        if hashlib.sha256(raw).hexdigest() != entry["sha256"]:
            raise ValueError("source fixture checksum changed")
        return json.loads(raw)


def fixture_citation_provider(profile: LocalProfile):
    """Load the deterministic citation adjacency fixture for this run, if any."""
    from .modules.discovery.citations import FixtureCitationProvider

    path = profile.root / "citations.json"
    if not path.exists():
        return FixtureCitationProvider({})
    value = json.loads(private_bytes(path, maximum=1048576))
    return FixtureCitationProvider(
        value.get("records", {}),
        freshness=value.get("freshness", "fresh"),
        fail=bool(value.get("fail", False)),
    )


class U3ControlWorker:
    """One bounded pass: corpus runs, assistance dispatch, dispositions, accounting."""

    def __init__(self, maintenance, dispatch, dispositions, admission):
        self.maintenance = maintenance
        self.dispatch = dispatch
        self.dispositions = dispositions
        self.admission = admission

    def run_once(self, limit=1):
        summary = {"runsExecuted": 0, "jobsExecuted": 0, "dispositionsApplied": 0}
        for run in self.maintenance.pending_runs(limit=limit):
            try:
                self.maintenance.execute(run["id"])
                summary["runsExecuted"] += 1
            except (PermissionError, ValueError):
                continue  # not claimable; the durable row stays inspectable
        dispatched = self.dispatch.run_once(limit=limit)
        summary["jobsExecuted"] = dispatched["executed"]
        try:
            consumed = self.dispositions.consume(limit=50)
            summary["dispositionsApplied"] = consumed["applied"]
        except (PermissionError, ValueError):
            summary["dispositionsApplied"] = 0
        self.admission.reconcile_admissions(limit=limit)
        self.admission.recover_execution(limit=limit)
        return summary


def assemble_u3(profile: LocalProfile) -> FastAPI:
    """Explicit owned composition; no ambient settings or startup migrations."""
    from .artifacts import PrivateArtifacts
    from .control_runtime import ControlAdmission, ControlCapacity, ControlLoop
    from .local_browser import CORPUS_ORIGIN
    from .local_host import assemble, host_router
    from .modules.accounts.preauthentication import Preauthentication
    from .modules.accounts.services.guarded_entry import GuardedEntryService
    from .modules.corpus.maintenance import CorpusMaintenance
    from .modules.corpus.reading import CorpusReading
    from .modules.corpus.repository import CorpusRepository
    from .modules.corpus.u3_http import corpus_router
    from .modules.discovery.citations import CitationExplorer
    from .modules.discovery.guarded_repository import GuardedDiscoveryRepository
    from .modules.discovery.u3_http import discovery_router
    from .modules.discovery.u3_search import U3Search
    from .modules.library.repository.guarded import GuardedLibraryRepository
    from .modules.library.u3_dispositions import SavedReferenceDispositions
    from .modules.summarization.u3_dispatch import AssistanceDispatch
    from .modules.summarization.u3_http import assistance_router
    from .modules.summarization.u3_provider import SyntheticAssistanceExecutor
    from .transactions import OwnerTransactions

    if profile.realm != "corpus-maintenance" or profile.origin != CORPUS_ORIGIN:
        raise ValueError("U3 assembly requires the owned corpus-maintenance realm")
    transactions = OwnerTransactions(profile)
    try:
        entry = GuardedEntryService(transactions)
        anonymous = Preauthentication(entry)
        sources = FixtureSourceProvider(profile.root)
        files = PrivateArtifacts(profile.root / "corpus-files", maximum_bytes=2097152)
        maintenance = CorpusMaintenance(transactions, files, sources)
        reading = CorpusReading(transactions)
        cursor_key = _cursor_key(profile)
        discovery_repository = GuardedDiscoveryRepository(transactions)
        library = GuardedLibraryRepository(transactions)
        search = U3Search(
            transactions, discovery_repository, library, cursor_key=cursor_key
        )
        citations = CitationExplorer(transactions, fixture_citation_provider(profile))
        executor = SyntheticAssistanceExecutor()
        executor_source = json.loads(
            private_bytes(profile.root / "assistance-executor.json")
        ) if (profile.root / "assistance-executor.json").exists() else {}
        if executor_source.get("mode") == "unavailable":
            executor = SyntheticAssistanceExecutor(fail_with="dependency-unavailable")
        dispatch = AssistanceDispatch(transactions, files, executor)
        dispositions = SavedReferenceDispositions(transactions)
        corpus_repository = CorpusRepository(transactions, files=None)
        catalog = u3_capabilities(provider_installed=True)
        routers = (
            host_router(transactions, entry=entry, anonymous=anonymous, catalog=catalog),
            corpus_router(
                transactions,
                entry=entry,
                anonymous=anonymous,
                maintenance=maintenance,
                reading=reading,
            ),
            discovery_router(
                transactions,
                entry=entry,
                anonymous=anonymous,
                search=search,
                citations=citations,
            ),
            assistance_router(
                transactions,
                entry=entry,
                files=files,
                dispatch=dispatch,
                corpus_repository=corpus_repository,
            ),
        )
        worker = U3ControlWorker(
            maintenance, dispatch, dispositions, dispatch.admission
        )

        @asynccontextmanager
        async def lifetime(app):
            loop = ControlLoop(app.state.control_worker, capacity=app.state.control_capacity)
            app.state.control_loop = loop
            loop.start()
            try:
                yield
            finally:
                await loop.close()
                transactions.close()

        app = assemble(profile, routers=routers, lifespan=lifetime)
        app.state.control_capacity = ControlCapacity(transactions)
        app.add_middleware(ControlAdmission, capacity=app.state.control_capacity)
        app.state.entry = entry
        app.state.transactions = transactions
        app.state.maintenance = maintenance
        app.state.search = search
        app.state.citations = citations
        app.state.assistance = dispatch
        app.state.dispositions = dispositions
        app.state.control_worker = worker
        app.state.capability_catalog = catalog
        app.state.required_capabilities = set(OWNERS)
        app.state.limits = limits_document()
        observations = observe_all(transactions)
        record(transactions, observations)
        app.state.capabilities = {
            owner: row["disposition"] in ("available", "degraded")
            for owner, row in observations.items()
        }
        return app
    except BaseException:
        transactions.close()
        raise


def _cursor_key(profile: LocalProfile) -> bytes:
    """Owner-created signing key for snapshot-bound cursors; never leaves the root."""
    import os
    import secrets

    path = profile.root / "search-cursor.key"
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        descriptor = os.open(
            path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600
        )
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(secrets.token_bytes(32))
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, "rb") as stream:
        raw = stream.read(33)
    if len(raw) != 32:
        raise ValueError("cursor signing key is not the exact private allocation")
    return raw
