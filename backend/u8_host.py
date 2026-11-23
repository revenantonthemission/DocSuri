"""The complete assembly: its composition, start checks and process roles (U8 plan Step 11).

`compose(profile)` builds the shared composition once per process: the owner
transactions, every owner's services, the registry's activations and ServiceOperations.
It first runs Workflow 1's checks, each refusal named by its check:

1. `root`: the profile root (the loader's checks, repeated for the running process);
2. `ledger`: the operations ledger reaches its head (it is opened here, because the
   next check reads it);
3. `restore-authorization`: no production restore of the live environment is active
   without `startAuthorizedAt` (BR4.7);
4. `release`: production runs from a root-owned real path under `releases/`, reached
   through `release` (BR6.5);
5. `key-folders`: each key folder is the profile's own; a missing one refuses once the
   database shows that accounts exist (BR6.2);
6. `service-secrets`: the service's own secrets are present; a missing provider secret
   only leaves that provider unconfigured (BR6.7);
7. the backup volume as the service account sees it, which only degrades (BR6.6), and
   the release tag and commit, recorded;
8. `database`: the database identity through SCRAM. While the instance does not answer
   the process stays live and not ready, retrying after 1, 2, 4, 8 and 16 seconds and
   then every 30 seconds, and never gives up (R3);
9. `schema`: the applied digests equal the composed chain (BR1.5).

Registration follows, in dependency order: each contribution's revision and schema
digest are compared with the manifest, and it is activated or marked unavailable with
`missing`, `incompatible`, `dependency-unavailable` or `policy-unresolved` (BR1.2). Then
every capability is registered, and the lifecycle manifest is configured with
AccountAccess when its control policy resolves.

A refused start leaves a process that serves only `/health/live` and `/health/ready`,
naming the check; it starts no worker or producer and never exits (R2, `HostProcess`).
The three roles are `host_app`, `run_workers` and `run_scheduler`.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import json
import os
import stat
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from . import u8_migrations
from .local_profile import KEY_FOLDERS, LocalProfile, private_bytes
from .u8_policy import PRODUCTION_OPERATIONS, SYNTHETIC_OPERATIONS, require_policy
from .u8_profile import ProfileRefused, custody_failure
from .u8_registry import (
    LIFECYCLE_MANIFEST,
    LIFECYCLE_REVISION,
    MANIFEST,
    Manifest,
    chain_files_of,
    dependency_order,
    release_digests,
    schema_digest_of,
    verify_import_boundaries,
)

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "frontend/dist"
DATABASE_WAITS = (1, 2, 4, 8, 16)
DATABASE_WAIT_AFTER = 30
SERVICE_SECRETS = ("owner-credentials.json",)
PROVIDER_ENVIRONMENT = "private-environment.json"
PROVIDER_SECRETS = {
    "provider.google": "googleClientSecret",
    "provider.orcid": "orcidClientSecret",
    "provider.resend": "resendApiKey",
}
RELEASE_IDENTITY = ".docsuri-release.json"
CLOCK_FILE = "u8-fixture-clock.json"
LEDGER_FOLDER = "ledger"
BACKUP_STANDIN = "backup-volume"
RECOVERY_KIND = "recovery-request"
ACTIVE_RESTORE_STATES = frozenset(
    {"awaiting-operator", "running", "verifying", "unknown", "post-restore-pending", "held"}
)
# The environment the composition's records name: the production profile's mode, and
# `live` for the composed realm, which stands in for the production database.


def environment_of(profile: LocalProfile) -> str:
    return profile.mode if profile.is_production else "live"


# Each role's connection gate (performance-design § 3.1). v2's scheduler process takes
# the maintenance gate of 2, a row of § 3.1 in its own right (L1-13).
PROCESS_GATES = {"host": "api", "workers": "worker", "scheduler": "maintenance"}
SCHEDULER_SECONDS = 30
CLOCK_AHEAD = dt.timedelta(days=2)
# The assistance history's page in both complete realms: performance-design § 2.3's 50
# rows for lists, read with their metadata in one assistance transaction (L1-8).
ASSISTANCE_HISTORY_ROWS = 50


def _control_policies() -> dict[str, object]:
    """AccountAccess's control policy for each complete realm (Step 19, D1): the
    composed realm runs `u8-synthetic-v1`, D1's shape with the synthetic lengths, and
    production `docsuri-production-v1`. Each policy refuses the other's realm."""
    from .modules.accounts.u8_control_policy import COMPLETE_POLICIES

    return dict(COMPLETE_POLICIES)


CONTROL_POLICIES: dict[str, object] = _control_policies()


class StartRefused(Exception):
    """A start check failed; `check` names it and `detail` is a fixed reason."""

    def __init__(self, check: str, detail: str | None = None):
        super().__init__(check if detail is None else f"{check}: {detail}")
        self.check, self.detail = check, detail


class PolicyUnresolved(RuntimeError):
    """A contribution's policy is not resolved for this profile (BR1.2)."""


class LifecycleManifestRefused(ValueError):
    """AccountAccess's lifecycle manifest configuration refuses a manifest that lacks a
    participant or scope of BR2.1, or names one it lacks (BR2.1); no request starts."""


def configure_lifecycle(entry, pairs, *, revision: str = LIFECYCLE_REVISION):
    """`CompleteLifecycleService(entry, LIFECYCLE_MANIFEST, revision="u8-owners-v1")`
    (U8's lifecycle service, the person's decision of 2026-10-24), after the manifest is
    checked against BR2.1's participants and scopes."""
    from .modules.accounts.u8_lifecycle import CompleteLifecycleService

    given = tuple(tuple(pair) for pair in pairs)
    if len(set(given)) != len(given) or set(given) != set(LIFECYCLE_MANIFEST):
        raise LifecycleManifestRefused("the lifecycle manifest differs from BR2.1")
    return CompleteLifecycleService(entry, given, revision=revision)


# --- Start checks ---------------------------------------------------------------------


def check_root(profile: LocalProfile) -> None:
    from .transactions import complete_realm

    if not complete_realm(profile.database_name, profile.realm):
        raise StartRefused("root", "not-a-complete-realm")
    try:
        info = profile.root.lstat()
    except FileNotFoundError:
        raise StartRefused("root", "root-missing") from None
    failure = custody_failure(info, uid=os.getuid(), exact_mode=0o700)
    if failure is not None or not stat.S_ISDIR(info.st_mode):
        raise StartRefused("root", f"root-{failure or 'missing'}")


def open_ledger(profile: LocalProfile, clock):
    """The ledger component over the profile's `ledger/` folder; a ledger that does not
    reach its head, or holds a record outside its schema, refuses the start."""
    from .modules.operations.errors import LedgerDamaged
    from .modules.operations.ledger import Ledger

    folder = profile.root / LEDGER_FOLDER
    if not folder.exists() and not folder.is_symlink():
        if profile.is_production:
            raise StartRefused("ledger", "ledger-missing")
        folder.mkdir(mode=0o700)
    try:
        return Ledger.open(folder, clock=clock)
    except LedgerDamaged as error:
        raise StartRefused("ledger", str(error)) from None


def unauthorized_restore(requests) -> str | None:
    """The identifier of an active production restore of the live environment that has
    not recorded `startAuthorizedAt`, from the current version of each RecoveryRequest
    (the ledger component's fold)."""
    latest = {
        record["recoveryRequestId"]: record for record in requests
        if isinstance(record.get("recoveryRequestId"), str)
    }
    for request, record in sorted(latest.items()):
        if (
            record.get("operation") == "restore.production"
            and record.get("environment") == "live"
            and record.get("state") in ACTIVE_RESTORE_STATES
            and not record.get("startAuthorizedAt")
        ):
            return request
    return None


def arrangement_for(profile: LocalProfile, arrangement=None):
    """The one arrangement value (your decision of 2026-10-24): `ArrangementPaths()` for
    the production profile unless a test gives one under its own prefix, and none for
    the composed realm. Every production branch reads its paths from it."""
    if not getattr(profile, "is_production", False):
        return None
    if arrangement is not None:
        return arrangement
    from docsuri_ops.arrangement.paths import ArrangementPaths

    return ArrangementPaths()


def release_owner(arrangement) -> int:
    """Who must own the release: root for the installed arrangement, and this process's
    own user for one a test built under its prefix (`ArrangementPaths.under`)."""
    return 0 if arrangement.is_production else os.getuid()


def check_release(profile: LocalProfile, release_root: Path, arrangement=None) -> dict:
    """Production runs from a real folder under `releases/`, reached through `release`,
    owned by root (by this process's user for a test arrangement) and writable by nobody
    else; the composed realm runs from the development tree."""
    if not profile.is_production:
        return {"kind": "development"}
    paths = arrangement_for(profile, arrangement)
    owner = release_owner(paths)
    real = release_root.resolve()
    if (
        not paths.release.is_symlink()
        or paths.release.resolve() != real
        or real.parent != paths.releases.resolve()
    ):
        raise StartRefused("release", "release-path")
    for path in (real, *real.parents):
        info = path.stat()
        if info.st_uid != owner or stat.S_IMODE(info.st_mode) & 0o022:
            raise StartRefused("release", "release-not-root-owned")
        if path == Path(paths.prefix).resolve():
            break
    return {"kind": "release", "path": str(real)}


def key_folder_state(profile: LocalProfile) -> tuple[str, ...]:
    """The missing key folders; a present one that is not the profile's own refuses."""
    missing = []
    for name in KEY_FOLDERS:
        path = profile.root / name
        try:
            info = path.lstat()
        except FileNotFoundError:
            missing.append(name)
            continue
        if not stat.S_ISDIR(info.st_mode) or custody_failure(
            info, uid=os.getuid(), exact_mode=0o700
        ):
            raise StartRefused("key-folders", f"{name}-custody")
    return tuple(missing)


def private_environment(profile: LocalProfile) -> dict:
    """The profile's private environment (provider clients and secrets), or none."""
    path = profile.root / PROVIDER_ENVIRONMENT
    values: dict = {}
    if path.exists() or path.is_symlink():
        try:
            values = json.loads(private_bytes(path))
        except (OSError, ValueError):
            raise StartRefused("service-secrets", "private-environment") from None
        if not isinstance(values, dict):
            raise StartRefused("service-secrets", "private-environment")
    return values


def provider_secrets(profile: LocalProfile) -> dict[str, str]:
    """Each service secret must be present; each provider is configured or not."""
    for name in SERVICE_SECRETS:
        if not (profile.root / name).is_file():
            raise StartRefused("service-secrets", Path(name).stem)
    values = private_environment(profile)
    return {
        capability: (
            "configured"
            if isinstance(values.get(key), str) and len(values[key]) >= 16
            else "unconfigured"
        )
        for capability, key in PROVIDER_SECRETS.items()
    }


def backup_volume_state(profile: LocalProfile) -> str:
    """What the service account can see of the backup volume; never refuses."""
    if profile.is_production:
        mount = Path(profile.backup_mount)
        return "mounted" if mount.is_dir() and os.path.ismount(mount) else "unavailable"
    folder = profile.root / BACKUP_STANDIN
    return "stand-in" if folder.is_dir() and not folder.is_symlink() else "unavailable"


def release_identity(profile: LocalProfile, release_root: Path) -> dict:
    path = release_root / RELEASE_IDENTITY
    if not path.is_file():
        if profile.is_production:
            raise StartRefused("release", "release-identity-missing")
        return {"tag": None, "commit": None}
    try:
        value = json.loads(path.read_bytes())
    except ValueError:  # includes UnicodeDecodeError (Step 79(c))
        raise StartRefused("release", "release-identity-malformed") from None
    if not isinstance(value, dict) or set(value) != {"tag", "commit"}:
        raise StartRefused("release", "release-identity-malformed")
    return value


def connect_database(profile: LocalProfile, role: str, *, policy, clock, sleep, on_wait):
    """Owner transactions whose identity check has succeeded through SCRAM; retries
    while the instance does not answer (R3). The role's process (`host`, `workers` or
    `scheduler`) counts its failed connections and transactions in the profile's
    `evidence/` folder (Step 51(b), L1-29)."""
    import psycopg

    from .transactions import Busy
    from .u8_counts import ProcessCounts
    from .u8_transactions import CompleteTransactions

    transactions = CompleteTransactions(
        profile, process=PROCESS_GATES[role],
        counts=ProcessCounts(profile.root / "evidence", role, policy=policy, clock=clock),
    )
    attempt = 0
    while True:
        try:
            transactions.run(
                "operations", lambda conn: conn.execute("SELECT 1 AS answered").fetchone()
            )
            return transactions
        except ValueError as error:
            transactions.close()
            raise StartRefused("database", "identity-mismatch") from error
        except (psycopg.OperationalError, psycopg.InterfaceError, Busy):
            seconds = DATABASE_WAITS[attempt] if attempt < len(DATABASE_WAITS) else (
                DATABASE_WAIT_AFTER
            )
            attempt += 1
            on_wait(seconds)
            sleep(seconds)
        except BaseException:
            transactions.close()
            raise


def applied_digests(transactions) -> dict:
    return transactions.run(
        "operations",
        lambda conn: conn.execute(
            "SELECT schema_hashes FROM public.docsuri_local_identity"
        ).fetchone()["schema_hashes"],
    )


def accounts_exist(transactions) -> bool:
    return transactions.run(
        "accounts",
        lambda conn: conn.execute(
            "SELECT EXISTS(SELECT 1 FROM accounts.account) AS occupied"
        ).fetchone()["occupied"],
    )


CURSOR_KEY = "search-cursor.key"
_CURSOR_KEY_BYTES = 32


def cursor_key_path(profile: LocalProfile) -> Path:
    """The search cursor key's file: `cursor-key/search-cursor.key` in the composed realm
    and production (L1-4, Step 72(a)). U3's own realm keeps its key at the run root
    (`u3_host._cursor_key`), as built."""
    from .local_profile import key_folder

    return key_folder(profile, "cursor-key") / CURSOR_KEY


def read_cursor_key(profile: LocalProfile) -> bytes:
    """The search cursor key, read and never created (L1-4): a regular file of this
    process's user, mode 0600, one link and exactly 32 bytes, opened without following a
    link or blocking on a substituted FIFO. Anything else, a missing file included,
    raises `ValueError`; only a start (`start_keys`), the realm's `migrate` and the
    production tool's `replace-cursor-key` write the key."""
    path = cursor_key_path(profile)
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError as error:
        raise ValueError("search cursor key missing or not readable") from error
    with os.fdopen(descriptor, "rb") as stream:
        info = os.fstat(stream.fileno())
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) != 0o600
            or info.st_nlink != 1
        ):
            raise ValueError("search cursor key custody invalid")
        raw = stream.read(_CURSOR_KEY_BYTES + 1)
    if len(raw) != _CURSOR_KEY_BYTES:
        raise ValueError("search cursor key is not the exact private allocation")
    return raw


def start_keys(profile: LocalProfile, *, occupied: bool) -> None:
    """Start keys and the verifier key's custody (BR6.2; your decision of 2026-10-24),
    once the database answers and before any builder runs: with accounts present and the
    verifier key missing, the start is refused (a new key would silently end every
    signed proof); after that check, with accounts present and the search cursor key
    missing, it is refused too (L1-4: `replace-cursor-key` is the way out). Otherwise any
    missing verifier key and search cursor key are created, each through a staging file
    linked into place, so concurrent starts keep one key and none reads a partial one."""
    from .local_profile import verifier_key_path
    from .modules.accounts.u8_verifier_key import ensure_key_file, ensure_verifier_key

    path = verifier_key_path(profile)
    if occupied and not (path.exists() or path.is_symlink()):
        raise StartRefused("key-folders", "verifier-key-missing-with-accounts")
    cursor = cursor_key_path(profile)
    if occupied and not (cursor.exists() or cursor.is_symlink()):
        raise StartRefused("key-folders", "cursor-key-missing-with-accounts")
    try:
        ensure_verifier_key(profile)
        ensure_key_file(cursor)
    except ValueError:
        raise StartRefused("key-folders", "start-key-custody") from None


def applied_file_digests(known: dict) -> dict[str, str]:
    """The applied digest of each chain file; base schemas are recorded by owner."""
    by_file = {file: known.get(owner) for owner, file in u8_migrations.BASE}
    by_file.update({file: value for file, value in known.items() if "/" in file})
    return by_file


def fixture_clock(profile: LocalProfile) -> Callable[[], dt.datetime]:
    """The one clock: the real time in production; in the composed realm, the
    delegated, run-bound `u8-fixture-clock.json` when present (decision "One clock"),
    holding still while it stands ahead of now and following now once now passes it.

    A clock that stood behind now made every issue time count from the past: a sign-in's
    second-factor continuation was born expired, and the factor answered 403 (the
    intermittent refusal the browser journeys met once a journey's advance had been
    overtaken by real time). The delegated instant only ever moves the clock forward."""

    def now() -> dt.datetime:
        current = dt.datetime.now(dt.UTC)
        if profile.is_production:
            return current
        path = profile.root / CLOCK_FILE
        if not path.exists():
            return current
        value = json.loads(private_bytes(path))
        instant = dt.datetime.fromisoformat(value["instant"])
        if (
            value.get("runId") != profile.run_id
            or instant.tzinfo is None
            or instant > current + CLOCK_AHEAD
        ):
            raise ValueError("u8 fixture clock binding differs")
        return max(instant, current)

    return now


# --- Contributions ------------------------------------------------------------------


@dataclass
class BuildContext:
    profile: LocalProfile
    transactions: object
    clock: Callable[[], dt.datetime]
    parts: dict = field(default_factory=dict)
    manifest: Manifest = MANIFEST
    # The start check's `provider.<name>` configuration (BR6.7).
    providers: dict = field(default_factory=dict)
    # The process role this composition serves (`PROCESS_GATES`).
    process: str = "host"
    # The one arrangement value (Step 11): `ArrangementPaths()` in production, None in
    # the composed realm.
    arrangement: object | None = None


def build_paper_journey(ctx: BuildContext) -> dict:
    # The same parts in production (your decision of 2026-10-24, the leftover refusals):
    # the entry's mail root and the assistance files come from the profile.
    from .artifacts import PrivateArtifacts
    from .modules.accounts.preauthentication import Preauthentication
    from .modules.accounts.services.guarded_entry import GuardedEntryService

    entry = GuardedEntryService(ctx.transactions)
    return {
        "entry": entry,
        "anonymous": Preauthentication(entry),
        "assistance_files": PrivateArtifacts.for_profile(ctx.profile, "assistance-files"),
    }


def process_counts(transactions):
    """The process's u8_counts writer, the counts its `CompleteTransactions` holds
    (Step 51(b)), or None."""
    return getattr(transactions, "_counts", None)


def identity_client_factories(profile, transactions) -> dict | None:
    """Production's Google and ORCID client factories: the counting wrapper over the
    adapters' one guarded builder (Step 56(c), L1-12). None for a synthetic profile."""
    if not getattr(profile, "is_production", False):
        return None
    from .u8_provider_probes import counting_client_factory, identity_client

    counts = process_counts(transactions)
    return {name: counting_client_factory(identity_client, "provider." + name, counts)
            for name in ("google", "orcid")}


def build_account_controls(ctx: BuildContext) -> dict:
    policy = CONTROL_POLICIES.get(ctx.profile.realm)
    if policy is None:
        raise PolicyUnresolved("no AccountAccess control policy is bound to this realm")
    from .modules.accounts.control_cursor import ControlCursor
    from .modules.accounts.u8_control_policy import Admission
    from .modules.accounts.u8_entry import CompleteControlEntryService
    from .modules.personalization.control_service import (
        PersonalizationControlService,
        ProducerBinding,
    )

    # Step 19: the composition's clock, and admission as a policy input from the profile.
    entry = CompleteControlEntryService(
        ctx.transactions, policy, clock=ctx.clock, admission=Admission.from_profile(ctx.profile)
    )
    # Step 21: the real Google and ORCID adapters, selected by the production profile
    # alone; a synthetic profile keeps the fixtures (BR7.1).
    from .modules.accounts.integrations.identity_providers import (
        production_identity_providers,
    )

    entry.identity_providers = production_identity_providers(
        ctx.profile, private_environment(ctx.profile),
        client_factories=identity_client_factories(ctx.profile, ctx.transactions),
    )
    if ctx.profile.is_production:
        require_no_fixture(entry.identity_providers)
    lifecycle = configure_lifecycle(entry, ctx.manifest.lifecycle)
    # As U2's assembly builds them (`local_host.assemble_journey`).
    personalization = PersonalizationControlService(
        ctx.transactions, policy,
        ControlCursor(bytes.fromhex(entry.verifier("cursor", "u2-controls-v1"))),
        producers=(ProducerBinding("Library"), ProducerBinding("CorpusContent")),
    )
    return {"entry": entry, "lifecycle": lifecycle, "personalization": personalization}


def require_no_fixture(providers: dict) -> None:
    """No fixture sign-in in production (BR7.1, NFR4.5; your decision of 2026-10-24):
    each of Google and ORCID must have the real adapter or the unconfigured one; a
    fixture, or a provider with neither, leaves account-controls `policy-unresolved`."""
    from .modules.accounts.services.control_identity import FixtureIdentityProvider

    if set(providers) != {"google", "orcid"} or any(
        isinstance(adapter, FixtureIdentityProvider) or "Fixture" in type(adapter).__name__
        for adapter in providers.values()
    ):
        raise PolicyUnresolved("a fixture identity provider in production")


def build_paper_corpus(ctx: BuildContext) -> dict:
    # Step 31: production's corpus grows only through the migration's imports, searches
    # with the pinned query embedder and assists with the real executor on the shared
    # model runtime (`u8_outward.production_corpus`); a fixture never runs there (BR7.1).
    if ctx.profile.is_production:
        from .u8_outward import production_corpus

        return production_corpus(ctx)
    from .artifacts import PrivateArtifacts
    from .modules.corpus.limits import for_profile
    from .modules.corpus.maintenance import CorpusMaintenance
    from .modules.corpus.reading import CorpusReading
    from .modules.corpus.repository import CorpusRepository
    from .modules.discovery.citations import CitationExplorer
    from .modules.discovery.guarded_repository import GuardedDiscoveryRepository
    from .modules.discovery.u8_search import CompleteSearch, StandinEmbeddings
    from .modules.library.u3_dispositions import SavedReferenceDispositions
    from .modules.library.u3_history import U3HistoryConsumer
    from .modules.summarization.u3_provider import SyntheticAssistanceExecutor
    from .u3_host import (
        FixtureSourceProvider,
        U3ControlWorker,
        fixture_citation_provider,
    )

    transactions, profile = ctx.transactions, ctx.profile
    limits = for_profile(profile)
    files = PrivateArtifacts.for_profile(profile, "corpus-files",
                                         maximum_bytes=limits.max_source_bytes)
    maintenance = CorpusMaintenance(transactions, files, FixtureSourceProvider(profile.root),
                                    limits=limits)
    # The composed realm embeds queries with the deterministic stand-in (BR7.1).
    search = CompleteSearch(
        transactions, GuardedDiscoveryRepository(transactions), U3HistoryConsumer(transactions),
        cursor_key=read_cursor_key(profile), embedder=StandinEmbeddings(),
    )
    from .modules.plans.u8_usage import use_complete_usage
    from .u8_job_lines import CompleteAssistanceDispatch

    # U2's controls for all usage (your decision of 2026-10-23): no self-granted usage.
    # The workers' job lines (Step 51(d), L1-6) come from the dispatch's per-item hook.
    dispatch = use_complete_usage(
        CompleteAssistanceDispatch(transactions, files, SyntheticAssistanceExecutor()),
        transactions,
    )
    dispositions = SavedReferenceDispositions(transactions)
    return {
        "files": files,
        "maintenance": maintenance,
        "reading": CorpusReading(transactions),
        "search": search,
        "citations": CitationExplorer(transactions, fixture_citation_provider(profile)),
        "dispatch": dispatch,
        "dispositions": dispositions,
        "corpus_repository": CorpusRepository(transactions, files=None),
        "worker": U3ControlWorker(maintenance, dispatch, dispositions, dispatch.admission),
    }


def build_research_workspace(ctx: BuildContext) -> dict:
    # Step 21 (your decision of 2026-10-24, "Build the research executor"): production's
    # research runs on the shared model runtime (`u8_research.production_research`);
    # every synthetic profile keeps U4's contribution as built (BR7.1).
    if ctx.profile.is_production:
        from .u8_research import production_research

        return production_research(ctx)
    from .modules.plans.u8_usage import use_complete_usage
    from .u4_host import research_contribution

    corpus = ctx.parts["paper-corpus"]
    part = research_contribution(
        ctx.transactions, ctx.parts["paper-journey"]["entry"], corpus["corpus_repository"],
        corpus["worker"],
    )
    # U2's controls for all usage (your decision of 2026-10-23): research and novelty
    # reserve through `CompleteUsage` under the realm's policy.
    use_complete_usage(part["execution"], ctx.transactions)
    return part


def build_topics_digests(ctx: BuildContext) -> dict:
    if ctx.profile.is_production:
        # Step 21: its live or rehearsal policy, Resend behind the provider gate.
        from .u8_outward import production_topics

        return production_topics(ctx)
    from .u5_host import topics_contribution

    return topics_contribution(
        ctx.transactions, ctx.parts["paper-journey"]["entry"],
        ctx.parts["paper-corpus"]["corpus_repository"],
        ctx.parts["research-workspace"]["worker"], clock=ctx.clock,
    )


def build_approved_export(ctx: BuildContext) -> dict:
    if ctx.profile.is_production:
        # Step 21: its live or rehearsal policy, the network transport behind the gate.
        from .u8_outward import production_export

        return production_export(ctx)
    from .u6_host import ACTIVATION_FILE, export_contribution, synthetic_notion

    if (ctx.profile.root / ACTIVATION_FILE).exists():
        raise PolicyUnresolved("a synthetic export refuses real-export settings")
    from .u8_job_lines import with_export_item_lines

    fake = synthetic_notion(ctx.profile, ctx.clock)
    role_page_reads(fake, ctx.profile, ctx.process)
    # The workers' job lines (Step 51(d), L1-6) on the lane the contribution returns.
    return with_export_item_lines(export_contribution(
        ctx.transactions, ctx.parts["paper-journey"]["entry"],
        ctx.parts["paper-corpus"]["corpus_repository"],
        ctx.parts["topics-digests"]["worker"],
        research=ctx.parts["research-workspace"]["service"],
        transport_factory=lambda: fake, clock=ctx.clock,
    ), ctx.transactions)


ROLE_PAGE_READS = "u8RolePageReads"


def role_page_reads(fake, profile: LocalProfile, process: str) -> dict[str, int]:
    """The composed realm's per-role page-read limits on the fake Notion.

    U6 served its export lane in one process, so one fake counted every read of a page.
    The composed realm runs host and workers apart, each with its own fake from the same
    scenario: the host's counts the preview and the approval's binding reads, the
    workers' starts again at zero. The scenario's `u8RolePageReads` (written by
    `scripts/u8_fixtures.py`, ignored by U6's loader) gives a role its own limit through
    U6's `limit_page_reads`, so a page that stops answering after the approval does so in
    the worker's pre-write check too. Returns the limits applied."""
    from .u6_host import SCENARIO_FILE

    path = profile.root / SCENARIO_FILE
    if not path.exists():
        return {}
    limits = json.loads(private_bytes(path)).get(ROLE_PAGE_READS, {}).get(process, {})
    applied = {}
    for page_id, normal in limits.items():
        if not isinstance(normal, int) or isinstance(normal, bool) or normal < 0:
            raise ValueError("a role page-read limit must be a count")
        fake.limit_page_reads(page_id, normal)
        applied[page_id] = normal
    return applied


def build_platform_control(ctx: BuildContext) -> dict:
    """PlatformControl's parts for the service account: U7's evidence module and, once
    the profile's store has a reader provisioned (Step 27), the three bounded readers:
    receipts for `ledger_cli`, the latest evidence for the backup agent's status, and the
    inspect reader for `platform.status`. Each reader only reads (BR3.5, NFR1.5)."""
    from docsuri_ops.platform_control import evidence
    from docsuri_ops.u8_platform.u8_protocols import readers_for

    parts: dict = {"evidence": evidence}
    control = None if ctx.arrangement is None else ctx.arrangement.control
    bound = readers_for(ctx.profile, control=control)
    if bound is not None:
        parts["receipt_reader"], parts["evidence_reader"], parts["inspect"] = bound
    return parts


def build_service_operations(ctx: BuildContext) -> dict:
    """ServiceOperations: the ledger component, the observation store, the tombstone
    register, the email allowance and ProviderActivation (the provider gate and the
    rehearsal recipients), the ports the composition hands to the adapters. Each
    provider is evaluated for the profile now starting. The recipients read a Notion
    connection's owner, pending rows included, through ApprovedExport's definer function
    under ServiceOperations' login (your answer of 2026-11-11, "Wire the owner read"), so
    the maintainer's first configure is known as the maintainer's own."""
    from .modules.operations.allowance import LedgerAllowance
    from .modules.operations.observation_store import ObservationStore
    from .modules.operations.provider_activation import (
        ActivationSettings,
        ProviderActivation,
        connection_owner_reader,
    )
    from .modules.operations.tombstones import Tombstones

    ledger = ctx.parts["ledger"]
    policy = PRODUCTION_OPERATIONS if ctx.profile.is_production else SYNTHETIC_OPERATIONS
    activation = ProviderActivation(
        ledger, ActivationSettings.from_profile(ctx.profile, ctx.providers), clock=ctx.clock,
        connection_owner=connection_owner_reader(ctx.transactions),
    )
    activation.start()
    return {
        "ledger": ledger,
        "observations": ObservationStore(ctx.transactions),
        "tombstones": Tombstones(ledger),
        "allowance": LedgerAllowance(ledger, policy),
        "activation": activation,
    }


BUILDERS: dict[str, tuple[str, Callable[[BuildContext], dict]]] = {
    "paper-journey": ("u1-paper-journey-1", build_paper_journey),
    "account-controls": ("u2-account-controls-1", build_account_controls),
    "paper-corpus": ("u3-paper-corpus-1", build_paper_corpus),
    "research-workspace": ("u4-research-workspace-1", build_research_workspace),
    "topics-digests": ("u5-topics-digests-1", build_topics_digests),
    "approved-export": ("u6-approved-export-1", build_approved_export),
    "platform-control": ("u7-platform-control-1", build_platform_control),
    "service-operations": ("u8-service-operations-1", build_service_operations),
}


@dataclass(frozen=True)
class Activation:
    contribution_id: str
    activation: str  # active | unavailable
    reason: str | None = None


def register(manifest: Manifest, ctx: BuildContext, known: dict, *, builders=None,
             release_root: Path = ROOT) -> dict[str, Activation]:
    """BR1.2, in dependency order. Registration writes no domain data."""
    builders = BUILDERS if builders is None else builders
    applied = applied_file_digests(known)
    activations: dict[str, Activation] = {}
    for contribution in dependency_order(manifest):
        name = contribution.contribution_id
        reason = None
        if any(activations[need].activation != "active" for need in contribution.requires):
            reason = "dependency-unavailable"
        elif name not in builders:
            reason = "missing"
        else:
            revision, build = builders[name]
            digests = (
                release_digests(name, release_root) if name == "platform-control" else applied
            )
            if revision != contribution.revision or contribution.schema_digest != (
                schema_digest_of(chain_files_of(name), digests)
            ):
                reason = "incompatible"
            else:
                try:
                    ctx.parts[name] = build(ctx)
                except ImportError:
                    reason = "missing"
                except PolicyUnresolved:
                    reason = "policy-unresolved"
                except LifecycleManifestRefused:
                    reason = "incompatible"
                except Exception as error:
                    from .modules.accounts.control_policy import PolicyUnavailable

                    if not isinstance(error, PolicyUnavailable):
                        raise
                    reason = "policy-unresolved"
        activations[name] = Activation(name, "unavailable" if reason else "active", reason)
    return activations


# --- The composition --------------------------------------------------------------------


@dataclass
class Composition:
    profile: LocalProfile
    process: str
    policy: object
    transactions: object
    ledger: object
    clock: Callable[[], dt.datetime]
    manifest: Manifest
    activations: dict[str, Activation]
    parts: dict
    report: dict
    worker: object | None = None
    # The host's own capacity admission, once `host_app` has built it (BR3.1).
    admission: Callable[[], bool] | None = None
    # The one arrangement value (Step 11): every production branch reads its paths here.
    arrangement: object | None = None

    @property
    def environment(self) -> str:
        return environment_of(self.profile)

    def readiness_view(self):
        """The readiness module over this composition's activations and observations:
        every read derives each state from the latest observation and its age (BR3.2)."""
        from .modules.operations.observation_store import ObservationStore
        from .modules.operations.readiness import Readiness, offers_held_sign_in

        # BR6.5: the release's tag and commit only, never its kind or path (Step 79(c)):
        # in production the path would publish the release folder on `/health/ready`.
        release = self.report.get("release") or {}
        return Readiness(
            self.manifest, self.activations, self.report["providers"],
            ObservationStore(self.transactions), self.policy, self.clock,
            admission=self.admission,
            release={"tag": release.get("tag"), "commit": release.get("commit")},
            # A held sign-in provider reads as not serving signed out once admission
            # opens (U8 plan Step 106(h), BR7.8).
            held_sign_in_offered=offers_held_sign_in(self.profile),
        )

    def capability_states(self) -> dict[str, dict]:
        """Each capability's derived state and reason (BR1.2, BR1.3, BR3.2)."""
        return {name: state.brief() for name, state in self.readiness_view().states().items()}

    def readiness(self) -> dict:
        """BR3.1, from one short read of the latest observations; no producer is asked."""
        return self.readiness_view().report()

    def active(self, capability: str) -> bool:
        for contribution in self.manifest.contributions:
            if capability in contribution.provides:
                return self.activations[contribution.contribution_id].activation == "active"
        return False

    def close(self) -> None:
        self.ledger.close()
        self.transactions.close()


def compose(
    profile: LocalProfile,
    *,
    process: str = "host",
    manifest: Manifest = MANIFEST,
    release_root: Path = ROOT,
    clock: Callable[[], dt.datetime] | None = None,
    sleep: Callable[[float], None] = time.sleep,
    on_wait: Callable[[float], None] = lambda seconds: None,
    builders=None,
    arrangement=None,
) -> Composition:
    """Workflow 1's checks, then registration (module docstring). `arrangement` is for
    tests only, under their own prefix; a running role never passes one, so it gets
    `ArrangementPaths()` and the root-owned rule (`u8_main`)."""
    manifest.verify()
    verify_import_boundaries(release_root)
    if process not in PROCESS_GATES:
        raise ValueError("unknown process role")
    policy = require_policy(
        PRODUCTION_OPERATIONS if profile.is_production else SYNTHETIC_OPERATIONS,
        production=profile.is_production,
    )
    arrangement = arrangement_for(profile, arrangement)
    check_root(profile)
    clock = clock or fixture_clock(profile)
    ledger = open_ledger(profile, clock)
    transactions = None
    try:
        request = unauthorized_restore(ledger.records(RECOVERY_KIND))
        if request is not None:
            raise StartRefused("restore-authorization", "start-not-authorized")
        release = check_release(profile, release_root, arrangement)
        missing_keys = key_folder_state(profile)
        providers = provider_secrets(profile)
        report = {
            "release": {**release, **release_identity(profile, release_root)},
            "backupVolume": backup_volume_state(profile),
            "providers": providers,
            "missingKeyFolders": list(missing_keys),
        }
        transactions = connect_database(
            profile, process, policy=policy, clock=clock, sleep=sleep, on_wait=on_wait
        )
        occupied = accounts_exist(transactions)
        if missing_keys and occupied:
            raise StartRefused("key-folders", "missing-with-accounts")
        known = applied_digests(transactions)
        difference = u8_migrations.applied_difference(known, release_root)
        if difference:
            raise StartRefused("schema", ",".join(difference[:8]))
        start_keys(profile, occupied=occupied)
        ctx = BuildContext(profile, transactions, clock, {"ledger": ledger}, manifest,
                           providers=providers, process=process, arrangement=arrangement)
        activations = register(
            manifest, ctx, known, builders=builders, release_root=release_root
        )
        parts = {name: value for name, value in ctx.parts.items() if name != "ledger"}
        # The composition comes first, so production's account mail reads provider.resend's
        # state as 운영 shows it (U8 plan Step 53(g), L1-53).
        composition = Composition(
            profile, process, policy, transactions, ledger, clock, manifest, activations,
            parts, report, arrangement=arrangement,
        )
        wire_adapters(parts, profile, capability_states=composition.capability_states,
                      counts=process_counts(transactions))
        composition.worker = complete_worker(composition)
        require_complete_parts(composition)
        return composition
    except BaseException:
        ledger.close()
        if transactions is not None:
            transactions.close()
        raise


def require_complete_parts(composition: Composition) -> None:
    """Production fails closed without U8's parts (the person's decision of 2026-10-24,
    "Move, scope tools, test U2"): in both complete realms the start is refused unless
    the entry, the lifecycle service, the lifecycle worker and every usage authority the
    composition built are U8's. A part that is not composed is not checked."""
    if composition.profile.realm not in ("service-operations", "production"):
        return
    from .modules.accounts.u8_entry import CompleteControlEntryService
    from .modules.accounts.u8_lifecycle import CompleteLifecycleService
    from .modules.plans.u8_usage import CompleteUsage
    from .u8_workers import CompleteLifecycleWorker

    parts = composition.parts
    controls = parts.get("account-controls")
    if controls is not None:
        if not isinstance(controls["entry"], CompleteControlEntryService):
            raise StartRefused("composition", "account-entry")
        if not isinstance(controls["lifecycle"], CompleteLifecycleService):
            raise StartRefused("composition", "lifecycle-service")
        lifecycle = getattr(composition.worker, "lifecycle", None)
        if composition.worker is not None and not isinstance(lifecycle, CompleteLifecycleWorker):
            raise StartRefused("composition", "lifecycle-worker")
    authorities = []
    execution = (parts.get("research-workspace") or {}).get("execution")
    if execution is not None:
        authorities.append(("research-usage", execution.usage))
    dispatch = (parts.get("paper-corpus") or {}).get("dispatch")
    if dispatch is not None:
        authorities += [("assistance-usage", dispatch.usage),
                        ("assistance-admission-usage", dispatch.admission.usage)]
    for name, usage in authorities:
        if not isinstance(usage, CompleteUsage):
            raise StartRefused("composition", name)


ACCOUNT_MAIL_SENDER = "accountMailSender"


def wire_adapters(
    parts: dict,
    profile: LocalProfile | None = None,
    *,
    capability_states: Callable[[], dict[str, dict]] | None = None,
    counts=None,
) -> None:
    """The composition wires ServiceOperations' ports into the owners' adapters, so no
    owner imports ServiceOperations (security-design § 13).

    - Every profile: the email allowance into AccountAccess's account mail.
    - The production profile (Step 21): ProviderActivation as the provider gate and the
      rehearsal recipients. Account mail goes through Resend when its key and sender are
      configured, and stays held (no adapter sends) when they are not (BR6.7, BR7.2);
      U6's Notion session reads Notion's circuit breaker over the same activation
      (`u8_outward.notion_gate`, L2-13) before every operation, and the entry's
      `identity_gate`, which Google and ORCID sign-in read at call time (U8 plan Step
      106(g), BR7.8), is the same ProviderActivation. A synthetic profile keeps its
      built adapters and no gate, so its fakes run unchanged (BR7.1).
    - A production profile whose ServiceOperations is unavailable fails closed: account
      mail is held (nothing is sent, not even to the local mailbox), the entry's
      `identity_gate` is None (provider sign-in in production then refuses), and any
      gate left in this process is removed, so U6's live policy holds every operation,
      and the outward builders themselves refused (`u8_outward.production_gate`).
    - `capability_states` (Step 53(g), L1-53): the composition's own derived states.
      Production's Resend account mail reads provider.resend's state through it, so mail
      requests are refused up front while Resend is observed down; without it only the
      gate counts. U6's Notion session reads provider.notion's state through the same
      callable, so no export operation opens a token or builds a client while Notion is
      observed unavailable.
    - `counts` (Step 56(c), L1-12): the process's u8_counts writer. Production's Resend
      account mail posts through the counting wrapper over the shared Resend client.
    - Every production profile (L3-7): the paper corpus's search embeds through search's
      breaker over provider.models (`u8_outward.install_search_breaker`), installed
      whether or not ServiceOperations is composed; while nothing is observed the
      breaker reads `unknown` and so stays closed.
    - Every production profile (L4-11): the shared model runtime's own breaker over
      provider.models (`u8_outward.install_models_breaker`), which research, paper
      assistance and the corpus embedder all pass, and the digest gate's reader over
      provider.resend (`u8_outward.install_digest_breaker`). With ServiceOperations
      composed and the derived states given, the entry's `identity_gate` is the sign-in
      breaker over the activation (`u8_outward.sign_in_gate`), so no start is written
      and no exchange is called while Google or ORCID is observed unavailable. A
      synthetic profile gets none of these.
    - A state read that raises reads `unknown` at every breaker, account mail's
      included (`u8_outward.read_state`, review 08's R-17).
    """
    from .modules.accounts.integrations.account_mail import HeldAccountMail, LocalAccountMail

    controls = parts.get("account-controls")
    operations = parts.get("service-operations")
    production = getattr(profile, "is_production", False)
    if production:
        from .u8_outward import (
            install_digest_breaker,
            install_models_breaker,
            install_search_breaker,
        )

        install_search_breaker(parts, capability_states)
        install_models_breaker(parts, capability_states)
        install_digest_breaker(parts, capability_states)
    if production and operations is None:
        from .modules.export.notion_session import install_provider_gate

        install_provider_gate(None, None)
        if controls is not None:
            controls["entry"].account_mail = HeldAccountMail()
            # No identity gate: provider sign-in in production refuses without one.
            controls["entry"].identity_gate = None
        return
    if controls is None or operations is None:
        return
    entry = controls["entry"]
    if production:
        _wire_production(entry, operations, profile, capability_states=capability_states,
                         counts=counts)
    elif isinstance(entry.account_mail, LocalAccountMail):
        entry.account_mail = LocalAccountMail(
            entry.mail, allowance=operations["allowance"],
            gate=entry.account_mail.gate, recipients=entry.account_mail.recipients,
        )


def _wire_production(
    entry,
    operations: dict,
    profile: LocalProfile,
    *,
    capability_states: Callable[[], dict[str, dict]] | None = None,
    counts=None,
) -> None:
    from .modules.accounts.integrations.account_mail import (
        HeldAccountMail,
        ResendAccountMail,
    )
    from .modules.export.notion_session import install_provider_gate
    from .u8_outward import ObservedState, notion_gate, sign_in_gate
    from .u8_provider_probes import counting_client_factory, resend_client

    activation = operations["activation"]
    environment = private_environment(profile)
    key, sender = environment.get(PROVIDER_SECRETS["provider.resend"]), environment.get(
        ACCOUNT_MAIL_SENDER)
    if activation.state("resend") != "unavailable" and isinstance(sender, str) and sender:
        # provider.resend's state as 운영 shows it, derived from the rows the probes
        # write (never `producers.latest_state`, which keeps a stopped process's row at
        # any age); the adapter sees only this callable (security-design § 13). It reads
        # through the breakers' one helper, so a read that raises reads `unknown` and
        # holds no mail (L4-11, review 08's R-17).
        observed = None if capability_states is None else ObservedState(
            "provider.resend", capability_states)
        entry.account_mail = ResendAccountMail(
            api_key=key, sender=sender, origin=profile.origin,
            allowance=operations["allowance"], gate=activation, recipients=activation,
            observed_state=observed,
            # Its answered calls counted under provider.resend (Step 56(c), L1-12).
            client_factory=counting_client_factory(resend_client, "provider.resend", counts),
        )
    else:
        entry.account_mail = HeldAccountMail()
    # Notion's circuit breaker over the activation (L2-13); the rehearsal recipients stay
    # the activation.
    install_provider_gate(notion_gate(activation, capability_states), activation)
    # Google and ORCID sign-in read the same activation at call time (U8 plan Step
    # 106(g), BR7.8), behind the sign-in breaker when the derived states are given (L4-11).
    entry.identity_gate = sign_in_gate(activation, capability_states)


def complete_worker(composition: Composition):
    """The chained worker of the active contributions, then the lifecycle worker."""
    from .u8_workers import CompleteWorker

    chained = None
    for name in ("approved-export", "topics-digests", "research-workspace", "paper-corpus"):
        part = composition.parts.get(name)
        if part is not None and part.get("worker") is not None:
            chained = part["worker"]
            break
    if chained is None:
        return None
    from .u8_outward import first_export_previews

    controls = composition.parts.get("account-controls")
    lifecycle = None if controls is None else lifecycle_worker(composition, controls)
    # Step 21 (the model lane's place): in production, model work is the lane's
    # (`u8_model_lane`), so the pass runs research's housekeeping and no assistance
    # dispatch, and its chained half always runs step by step.
    production = getattr(composition.profile, "is_production", False)
    return CompleteWorker(chained, lifecycle, previews=first_export_previews(composition),
                          set_aside=lane_set_aside(composition) if production
                          else item_set_aside(composition),
                          model_work_in_lane=production)


def lane_set_aside(composition: Composition):
    """The production recorder of a set-aside item: ServiceOperations' incident when it
    is composed, and while it is unavailable a recorder that only logs, so the chained
    half still runs step by step and the model lane keeps turning."""
    recorder = item_set_aside(composition)
    if recorder is not None:
        return recorder
    from .log_events import current as current_log

    def log_only(kind: str, identity: str, error: BaseException) -> None:
        current_log().exception("workers", "item.set-aside", error, state=kind)

    return log_only


SET_ASIDE_CAPABILITY = "background.work"


def item_set_aside(composition: Composition):
    """The recorder of a worker item set aside for its turn (the person's decision of
    2026-10-23, "Set it aside, record it"), in the two complete realms only: one log line
    with the error's type and location, and an operations incident on `background.work`
    whose correlation is the item's kind and identity, never its content. A ledger that
    cannot take the incident is logged and does not stop the pass. None elsewhere."""
    from .log_events import current as current_log
    from .modules.operations.incidents import Incidents

    operations = composition.parts.get("service-operations")
    if operations is None or composition.profile.realm not in (
            "service-operations", "production"):
        return None
    incidents = Incidents(operations["ledger"], environment=composition.environment)

    def record(kind: str, identity: str, error: BaseException) -> None:
        current_log().exception("workers", "item.set-aside", error, state=kind)
        try:
            incidents.signal(SET_ASIDE_CAPABILITY, "worker-item-set-aside",
                             correlation=f"worker-item:{kind}:{identity}"[:160])
        except Exception as failure:  # noqa: BLE001 - the pass carries on regardless
            current_log().exception("workers", "item.unrecorded", failure, state=kind)

    return record


def lifecycle_worker(composition: Composition, controls: dict):
    """The lifecycle `CompleteLifecycleWorker` with all ten participants (BR2.1), claiming
    each scope through `GatedLifecycle` so a waiting participant spends no attempts."""
    from .modules.operations.lifecycle import GatedLifecycle, OperationsLifecycleParticipant
    from .u8_workers import CompleteLifecycleWorker

    operations = composition.parts.get("service-operations")
    participant = None
    if operations is not None:
        # The backups scope waits while a set or a ledger copy is written and names the
        # volume files from the agent's status (L1-2, L1-51; U8 plan Step 64(f)-(g)): the
        # platform part's readers, None when it binds none.
        platform = composition.parts.get("platform-control") or {}
        inspect = platform.get("inspect")
        participant = OperationsLifecycleParticipant(
            composition.transactions, operations["ledger"], composition.policy,
            schedule_active=lambda: backup_schedule_active(composition.profile),
            open_operations=None if inspect is None else inspect.open_operations,
            agent_status=platform.get("evidence_reader"),
            status_required=composition.profile.is_production,
        )
    gated = GatedLifecycle(controls["lifecycle"])
    worker = CompleteLifecycleWorker(
        controls["entry"], gated, controls["personalization"],
        composition.parts["paper-journey"]["assistance_files"],
        clock=composition.clock, operations=participant,
    )
    gated.participants = worker.participants
    return worker


def backup_schedule_active(profile: LocalProfile) -> bool:
    """Whether a live backup schedule with its retention runs (BR2.5): in production,
    from the switch's live start (rehearsal sets are not live sets); in the composed
    realm, whose database stands in for production's, always."""
    return profile.mode == "live" if profile.is_production else True


# --- The start, and the process that serves while it runs --------------------------------


class _Stopped(Exception):
    pass


class Startup:
    """Load the profile and compose, recording the state the health routes report.

    A refused check keeps R2's rule: the process stays, serving only its health routes,
    and never exits. Any other error from loading or composing (your decision of
    2026-10-24) is logged as `start.refused` with the error's type only, the state reads
    `failed`, and `on_failure` is called with that type: the role then exits with status
    1 (the host after stopping its server), so launchd relaunches it, and a crash loop
    shows in readiness and the log rather than as a process stuck at `starting`."""

    def __init__(self, load_profile: Callable[[], LocalProfile], *, role: str = "host",
                 on_failure: Callable[[str], None] | None = None, **options):
        if role not in PROCESS_GATES:
            raise ValueError("unknown process role")
        self.load_profile, self.role, self.options = load_profile, role, options
        self.on_failure = on_failure
        self.state, self.check, self.detail = "starting", None, None
        self.profile: LocalProfile | None = None
        self.composition: Composition | None = None
        self.waits: list[float] = []
        self._stopping = threading.Event()

    def _sleep(self, seconds: float) -> None:
        if self._stopping.wait(seconds):
            raise _Stopped

    def _waiting(self, seconds: float) -> None:
        self.state = "waiting-database"
        self.waits.append(seconds)

    def run(self) -> Composition | None:
        try:
            self.profile = self.load_profile()
        except ProfileRefused as error:
            return self._refuse(StartRefused("root", error.check))
        except (OSError, ValueError):
            return self._refuse(StartRefused("root", "profile-unreadable"))
        except Exception as error:  # noqa: BLE001 - an unexpected start fails the role
            return self._fail(error)
        options = {"sleep": self._sleep, "on_wait": self._waiting, **self.options}
        try:
            self.composition = compose(self.profile, process=self.role, **options)
        except StartRefused as error:
            return self._refuse(error)
        except _Stopped:
            self.state = "stopped"
            return None
        except Exception as error:  # noqa: BLE001 - an unexpected start fails the role
            return self._fail(error)
        self.state = "composed"
        return self.composition

    def _fail(self, error: BaseException) -> None:
        """The start failed unexpectedly: logged by the error's type only (never its
        message), then the role is told to exit."""
        kind = type(error).__name__
        self.state, self.check, self.detail = "failed", "start", kind
        from .log_events import current

        current().event("host", "start.refused", "error", reason="start-failed",
                        errorType=kind)
        if self.on_failure is not None:
            self.on_failure(kind)
        return None

    def _refuse(self, error: StartRefused) -> None:
        self.state, self.check, self.detail = "refused", error.check, error.detail
        from .log_events import current

        current().event("host", "start.refused", "error", reason=error.check)
        return None

    def stop(self) -> None:
        self._stopping.set()


async def _answer(send, status: int, value: dict, *, public: bool = False) -> None:
    """A health-only answer, with the composed boundary's fixed headers (Step 79(b)):
    `no-store`, `production_boundary.FIXED_HEADERS` (`nosniff` once among them) and, on
    the public authority, `Strict-Transport-Security`."""
    from .production_boundary import FIXED_HEADERS, HSTS, NO_STORE

    body = json.dumps(value).encode()
    headers = [
        (b"content-type", b"application/json"),
        (b"content-length", str(len(body)).encode()),
        (b"cache-control", NO_STORE.encode()),
        *FIXED_HEADERS,
    ]
    if public:
        headers.append((b"strict-transport-security", HSTS.encode()))
    await send({"type": "http.response.start", "status": status, "headers": headers})
    await send({"type": "http.response.body", "body": body})


class HostProcess:
    """The host role's ASGI application. While the start runs, or after it refused, it
    serves only `/health/live` and `/health/ready`; once composed, it serves `host_app`."""

    def __init__(self, startup: Startup, *, hosts,
                 prepare: Callable[[Composition], None] | None = None):
        """`hosts` are the host names accepted before the composition is served
        (`u8_main.boundary_hosts`, Step 79(b)). `prepare`, when given, adjusts the
        composition before its routes are built: the composed realm's serve script wires
        the identity stand-in's recorded answers into the real adapters there, in the
        process that redeems its codes (Step 39)."""
        self.startup = startup
        self.hosts = hosts
        self.prepare = prepare
        self.app = None
        self.thread: threading.Thread | None = None
        self.watcher: asyncio.Task | None = None
        self.background: list = []

    def drain(self) -> None:
        """The host begins to drain (R7): open event streams close with a retry hint."""
        if self.app is not None:
            self.app.state.draining.set()

    async def __call__(self, scope, receive, send):
        if scope["type"] == "lifespan":
            return await self._lifespan(receive, send)
        if self.app is None and self.startup.state == "composed":
            await self._serve_composition()
        if self.app is not None:
            return await self.app(scope, receive, send)
        if scope["type"] != "http":
            return None
        return await self._health_only(scope, send)

    async def _health_only(self, scope, send):
        from .local_browser import request_identifier

        startup = self.startup
        # The `Host` check runs first, as the composed boundary's does (Step 79(b)).
        names = [value for key, value in scope.get("headers", ()) if key.lower() == b"host"]
        host = names[0].decode("latin-1") if len(names) == 1 else None
        if host not in self.hosts.accepted:
            return await _answer(send, 400, {"code": "FORBIDDEN", "messageKey": "request.host",
                                             "requestId": request_identifier(),
                                             "retryable": False})
        public = host == self.hosts.public_authority
        if scope["method"] == "GET" and scope["path"] == "/health/live":
            return await _answer(send, 200, {"process": "alive", "state": startup.state},
                                 public=public)
        if scope["method"] == "GET" and scope["path"] == "/health/ready":
            missing = [startup.check] if startup.check else [
                "database" if startup.state == "waiting-database" else "assembly"
            ]
            return await _answer(send, 503, {"ready": False, "state": startup.state,
                                             "missing": missing}, public=public)
        if startup.state == "refused":
            return await _answer(send, 404, {"code": "NOT_FOUND",
                                             "messageKey": "resource.notFound"}, public=public)
        return await _answer(send, 503, {"code": "NOT_READY", "messageKey": "capability.notReady"},
                             public=public)

    async def _serve_composition(self):
        if self.prepare is not None:
            self.prepare(self.startup.composition)
        app = host_app(self.startup.composition)
        refresher = app.state.capacity_refresher
        refresher.start()
        stopping = asyncio.Event()
        self.background = [
            (refresher.close, None),
            (stopping.set, asyncio.create_task(app.state.latency.run(stopping))),
        ]
        if app.state.host_producers is not None:
            self.background.append(
                (stopping.set, asyncio.create_task(app.state.host_producers.run(stopping)))
            )
        sender = app.state.account_mail_sender
        if sender is not None:
            # The account-mail outbox's sender (Step 53(h), L1-69); `close()` awaits its
            # `stop()` before the composition closes.
            sender.start()
            self.background.append((sender.stop, None))
        self.app = app

    def start(self) -> None:
        self.thread = threading.Thread(target=self.startup.run, daemon=True)
        self.thread.start()

    async def watch(self, interval: float = 0.1) -> None:
        """Serve the composition as soon as the start completes."""
        while self.app is None and self.startup.state in ("starting", "waiting-database"):
            await asyncio.sleep(interval)
        if self.app is None and self.startup.state == "composed":
            await self._serve_composition()

    async def close(self) -> None:
        self.startup.stop()
        if self.watcher is not None:
            await self.watcher
        for stop, task in self.background:
            result = stop()
            if asyncio.iscoroutine(result):
                await result
            if task is not None:
                await task
        if self.thread is not None:
            await asyncio.to_thread(self.thread.join, 60)
        if self.startup.composition is not None:
            await asyncio.to_thread(self.startup.composition.close)

    async def _lifespan(self, receive, send):
        while True:
            message = await receive()
            if message["type"] == "lifespan.startup":
                self.start()
                self.watcher = asyncio.create_task(self.watch())
                await send({"type": "lifespan.startup.complete"})
            elif message["type"] == "lifespan.shutdown":
                await self.close()
                await send({"type": "lifespan.shutdown.complete"})
                return


def draining_server(process: HostProcess, config):
    """Uvicorn's server for the host role: when its shutdown begins, the host drains
    first, so open event streams close with their retry hint before Uvicorn's 10-second
    graceful bound (R7, `SERVER_SETTINGS`)."""
    import uvicorn

    class DrainingServer(uvicorn.Server):
        async def shutdown(self, *args, **options):
            process.drain()
            await super().shutdown(*args, **options)

    return DrainingServer(config)


def route_classes():
    """The host's route classes (performance-design § 10); `host_app` registers the class
    of every route it mounts (Step 39). The static catch-all, `GET /{path:path}`, is not
    registered here: `register_classes` gives it its class where `assemble` mounts it,
    last, after every router, so `RouteClasses.classify`'s first match follows the order
    Starlette serves by and a request is recorded under its own route's class (Step 129,
    record 102)."""
    from .request_context import RouteClasses

    classes = RouteClasses()
    classes.register("/health/live", "health", methods=("GET",))
    classes.register("/health/ready", "health", methods=("GET",))
    classes.register("/api/v2/capabilities", "navigation", methods=("GET",))
    return classes


def control_rows(controls: dict, profile: LocalProfile) -> list[dict]:
    """AccountAccess's control capability rows, as U2's assembly publishes them, under
    the realm's control policy."""
    reference = controls["entry"].control_policy.reference
    rows = [
        {"id": name, "state": "available", "modeIds": modes, "languageIds": ["ko"],
         "levelIds": ["complete"], "formatIds": ["json"], "policy": reference}
        for name, modes in (
            ("account.controls", ["profile", "consent", "credentials", "mfa", "lifecycle"]),
            ("personalization.reset", ["delete_behavior", "reset_profile"]),
        )
    ]
    rows.append({"id": "account.public-activation", "state": "policy_pending", "modeIds": [],
                 "languageIds": ["ko"], "levelIds": ["G1-G8-evidence-required"],
                 "formatIds": ["json"], "policy": reference})
    return rows


def operations_row(composition: Composition) -> dict:
    from .modules.operations.http import policy_reference

    return {"id": "operations.ledger", "state": "available", "modeIds": [
        "backup.create", "restore.verify", "restore.production"], "languageIds": ["ko"],
        "levelIds": ["administrator-mfa"], "formatIds": ["json"],
        "policy": policy_reference(composition.policy)}


def _corpus_routers(transactions, entry, anonymous, corpus: dict) -> list:
    from .modules.corpus.u3_http import corpus_router
    from .modules.discovery.u3_http import discovery_router
    from .modules.summarization.u3_http import assistance_router
    from .u8_asset_bytes import AssetBytes, asset_router

    return [
        corpus_router(transactions, entry=entry, maintenance=corpus["maintenance"],
                      reading=corpus["reading"]),
        discovery_router(transactions, entry=entry, anonymous=anonymous,
                         search=corpus["search"], citations=corpus["citations"]),
        # Production's large-paper source rule (Step 23); the composed realm has none, so
        # it keeps U3's built 256-chunk, unique-anchor rule.
        assistance_router(transactions, entry=entry, files=corpus["files"],
                          dispatch=corpus["dispatch"],
                          corpus_repository=corpus["corpus_repository"],
                          source_rule=corpus.get("assistance_rule"),
                          history_bound=ASSISTANCE_HISTORY_ROWS, history_in_one_read=True),
        # C13's byte route (Step 127): after assistance's, so `owned[2]` stays assistance.
        asset_router(transactions, entry=entry, assets=AssetBytes(transactions, corpus["files"])),
    ]


def _research_routers(composition: Composition, entry, research: dict) -> list:
    from .modules.research.http import job_list_router
    from .modules.research.job_list import JobListCursor
    from .modules.research.repository import ResearchRepository
    from .u8_routes import job_list_key

    cursor = JobListCursor(job_list_key(read_cursor_key(composition.profile)),
                           clock=composition.clock)
    repository = ResearchRepository(composition.transactions, job_list_cursor=cursor)
    return [research["router"], job_list_router(composition.transactions, entry=entry,
                                                repository=repository,
                                                clock=composition.clock)]


def availability_folder(composition: Composition) -> Path:
    """The heartbeat's availability record: the arrangement's in production (the
    composition's one arrangement value), the run root's in the composed realm. Read by
    the dashboard and by `operations.cutover`'s counts (Step 58(e))."""
    profile = composition.profile
    if profile.is_production:
        return arrangement_for(profile, composition.arrangement).availability
    return profile.root / "availability"


def operations_dashboard(composition: Composition, operations: dict):
    """The host's dashboard (U8 plan Step 60): the composition's operations policy, the
    availability folder (Step 58(e)), the isolation evidence folder, and the lanes' counts
    over the host's own owner logins, each lane one short transaction, the export lane
    through `export.status_counts` (Step 58(f)); it opens no connection of its own."""
    from .modules.operations import producers as p
    from .modules.operations.dashboard import Dashboard
    from .request_context import LATENCY_FOLDER

    profile = composition.profile
    return Dashboard(
        composition.readiness_view(), operations["ledger"], environment=composition.environment,
        clock=composition.clock, allowance=operations.get("allowance"),
        latency_folder=profile.root.joinpath(*LATENCY_FOLDER),
        availability_folder=availability_folder(composition), policy=composition.policy,
        isolation_folder=p.isolation_folder(profile, composition.arrangement),
        lane_counts=p.LaneCounts(composition.transactions, composition.policy),
    )


def _operations_router(composition: Composition, entry, operations: dict):
    from .modules.operations.http import operations_router

    dashboard = operations_dashboard(composition, operations)
    return operations_router(composition.transactions, entry=entry, dashboard=dashboard,
                             ledger=operations["ledger"], policy=composition.policy,
                             environment=composition.environment, clock=composition.clock)


def complete_routers(composition: Composition) -> tuple[list, list[dict]]:
    """Every active contribution's routes and the capability rows they publish (Step 39).
    The account controls' entry serves every router the host builds; a contribution's
    own router keeps the entry it was built with."""
    from .local_host import assistance_readiness, journey_capabilities
    from .modules.accounts.local_http import account_router
    from .modules.accounts.preauthentication import Preauthentication
    from .modules.library.local_http import library_router
    from .modules.personalization.activity import ActivityRelay
    from .modules.personalization.local_http import settings_router
    from .modules.plans.local_http import usage_router
    from .u3_host import u3_capabilities
    from .u8_routes import capability_router, navigation_router, static_router

    parts, transactions, profile = composition.parts, composition.transactions, composition.profile
    controls = parts.get("account-controls")
    if controls is None and profile.is_production:
        # No synthetic sign-in in production (BR6.4; your decision of 2026-10-24):
        # without account-controls, only the static shell, the legal pages, the health
        # routes and the capabilities' public projection; never paper-journey's entry.
        from .u8_routes import public_capability_router

        return [static_router(BUILD), public_capability_router(
            transactions, readiness=lambda: composition.readiness_view())], []
    entry = (controls or parts["paper-journey"])["entry"]
    anonymous = Preauthentication(entry)
    rows = journey_capabilities(assistance_readiness(profile))
    # D1's routes (U8's own, your decision of 2026-10-24) with the account controls; the
    # built router on paper-journey's entry otherwise.
    if controls is not None:
        from .modules.accounts.u8_local_http import d1_account_router

        routers = [static_router(BUILD), d1_account_router(entry)]
    else:
        routers = [static_router(BUILD), account_router(entry)]
    personalization = None
    if controls is not None:
        from .modules.accounts.u8_control_http import d1_control_router

        routers.append(d1_control_router(entry, controls["lifecycle"]))
        rows += control_rows(controls, profile)
        personalization = controls["personalization"]
    library = ActivityRelay(personalization, personalization.producers[0]) if (
        personalization is not None) else None
    routers += [
        library_router(transactions, entry=entry, activity=library),
        settings_router(transactions, entry=entry, controls=personalization),
        usage_router(transactions, entry=entry),
    ]
    research = parts.get("research-workspace")
    if (corpus := parts.get("paper-corpus")) is not None:
        owned = _corpus_routers(transactions, entry, anonymous, corpus)
        if research is not None:
            from .u8_routes import job_registry_router

            # Mounted first: its job routes resolve research jobs, then assistance's.
            routers.append(job_registry_router(transactions, entry=entry,
                                               research=research["service"],
                                               assistance=owned[2]))
        routers += owned
        rows += u3_capabilities(provider_installed=True)
    if research is not None:
        routers += _research_routers(composition, entry, research)
        rows += research["capabilities"]
    for name in ("topics-digests", "approved-export"):
        if (part := parts.get(name)) is not None:
            routers.append(part["router"])
            rows += part["capabilities"]
    if (operations := parts.get("service-operations")) is not None:
        routers.append(_operations_router(composition, entry, operations))
        rows.append(operations_row(composition))
    unique = list({row["id"]: row for row in rows}.values())
    if profile.is_production:
        unique = production_rows(unique, profile)
    routers[1:1] = [
        navigation_router(transactions, entry=entry, anonymous=anonymous,
                          states=lambda: composition.readiness_view().states(),
                          revision=composition.manifest.revision),
        capability_router(transactions, entry=entry,
                          readiness=lambda: composition.readiness_view(), rows=unique),
    ]
    return routers, unique


# Production's own labels for the U1 and U3 rows' synthetic ones (your decision of
# 2026-10-24): the corpus grows only through the migration's imports, eligibility is
# recorded with its evidence, and usage is each account's grant per period.
PRODUCTION_LABELS = {
    "synthetic-four-no-reset": "granted-per-period",
    "synthetic-only": "migration-imports",
    "synthetic-extractive": "key-sections",
}
ASSISTANCE_ROWS = ("assistance.summary", "assistance.translation")


def production_rows(rows: list[dict], profile: LocalProfile) -> list[dict]:
    """Production's capability rows (your decision of 2026-10-24): no row carries a
    `synthetic-*` mode or level, and the assistance rows come from the one readiness
    marker (`u8_outward.model_readiness`, purpose `assistance`)."""
    from .u8_outward import model_readiness

    ready = model_readiness(profile, "assistance")
    result = []
    for row in rows:
        row = {**row, "modeIds": [PRODUCTION_LABELS.get(item, item) for item in row["modeIds"]],
               "levelIds": [PRODUCTION_LABELS.get(item, item) for item in row["levelIds"]]}
        if row["id"] in ASSISTANCE_ROWS:
            row = {**row, "state": "available" if ready else "policy_pending",
                   "modeIds": ["key-sections"] if ready else []}
        if row["id"] == "assistance.model":
            row = {**row, "state": "available" if ready else "policy_pending",
                   "levelIds": ["reviewed-evidence"] if ready else row["levelIds"]}
        if any("synthetic" in item for item in (*row["modeIds"], *row["levelIds"])):
            raise PolicyUnresolved("a synthetic capability row in production")
        result.append(row)
    return result


def _without_built_catalog(app) -> None:
    """The shared host's own capability route lists only the built catalog; the complete
    assembly answers that path from the registry instead (BR5.9), so the built one goes."""
    for route in list(app.router.routes):
        if getattr(route, "path", None) == "/api/v2/capabilities" and (
            getattr(route, "name", None) == "capability_catalog"
        ):
            app.router.routes.remove(route)
            return


def host_app(composition: Composition):
    """The host role: every owner's routes in one application behind D7's boundary, then
    `ControlAdmission`, then the shared host's `local_boundary` and `TrustedHostMiddleware`
    with the profile's host list (Step 39). It runs no lane; event streams close with a
    retry hint when the host drains (R7)."""
    import asyncio

    from .control_runtime import ControlAdmission
    from .local_host import assemble
    from .production_boundary import BoundaryHosts, BuildManifest, ProductionBoundary
    from .request_context import LatencyRecorder, RequestContext
    from .u8_capacity import CapacityRefresher, complete_capacity
    from .u8_routes import StreamDrain, check_routes, combined, register_classes

    profile = composition.profile
    classes = route_classes()
    latency = LatencyRecorder(profile.root, policy=composition.policy, clock=composition.clock)
    build = (
        BuildManifest.load(BUILD) if (BUILD / ".docsuri-build.json").is_file()
        else BuildManifest.empty(BUILD)
    )
    boundary = ProductionBoundary(
        BoundaryHosts.for_profile(profile), build, context=RequestContext(latency, classes)
    )
    routers, rows = complete_routers(composition)
    app = assemble(profile, routers=(combined(routers),), boundary=boundary)
    _without_built_catalog(app)
    register_classes(classes, app.router.routes)
    app.state.route_inventory = check_routes(app.router.routes, classes)
    app.state.capability_catalog = rows
    draining = asyncio.Event()
    app.add_middleware(StreamDrain, draining=draining)
    app.state.draining = draining
    capacity = complete_capacity(composition.transactions)
    app.add_middleware(ControlAdmission, capacity=capacity)
    app.state.control_capacity = capacity
    app.state.capacity_refresher = CapacityRefresher(capacity)
    app.state.latency = latency
    app.state.transactions = composition.transactions
    app.state.composition = composition
    composition.admission = lambda: capacity.admitting
    app.state.readiness = composition.readiness
    app.state.host_producers = host_producers(composition, latency.folder)
    app.state.account_mail_sender = account_mail_sender(composition)
    return app


def account_mail_sender(composition: Composition):
    """The account-mail outbox's sender over the account controls' entry (Step 53(h),
    L1-69), or None without account-controls. Its failed runs count on the host's own
    `ProcessCounts`, the counts its `CompleteTransactions` holds (L1-70); with no counts
    it records nothing. Building it starts nothing: `HostProcess` starts it."""
    from .modules.accounts.u8_mail_outbox import AccountMailSender

    controls = composition.parts.get("account-controls")
    if controls is None:
        return None
    counts = getattr(composition.transactions, "_counts", None)
    record = None if counts is None else (
        lambda: counts.record("mail.sender", failed=True)
    )
    return AccountMailSender(controls["entry"], record_failure=record)


def host_producers(composition: Composition, latency_folder: Path):
    """The host's one producer: its own 5xx rate, from its latency summaries."""
    from .modules.operations.observation_store import ObservationStore
    from .modules.operations.observations import Observations
    from .modules.operations.producers import HostErrorRateProducer, ProducerSchedule

    if not composition.active("operations.ledger"):
        return None
    return ProducerSchedule(
        [HostErrorRateProducer(latency_folder)],
        Observations(ObservationStore(composition.transactions)),
        composition.policy, composition.clock,
    )


def sender_beat_reader(composition: Composition):
    """The outbox module's beat reader when account-controls is composed, else None."""
    if composition.parts.get("account-controls") is None:
        return None
    from .modules.accounts.u8_mail_outbox import beat_reader

    return beat_reader(composition.transactions)


def worker_producers(composition: Composition, loop_status=None) -> list:
    """One producer per registered capability whose contribution is active (BR3.3)."""
    from .modules.operations import producers as p

    if not composition.active("operations.ledger"):
        return []
    profile, policy, transactions = (
        composition.profile, composition.policy, composition.transactions
    )
    operations = composition.parts["service-operations"]
    ledger = operations["ledger"]
    evidence = profile.root / "evidence"
    # Step 58(d) and (f): failed jobs per lane, read through each owner's login.
    lanes = p.LaneCounts(transactions, policy)
    chosen = p.owner_probes(transactions, composition.active)
    models_state = None
    if profile.is_production:
        # Step 21: research and novelty wait for the model runtime and the marker, and
        # the assistance producer reads `provider.models` too.
        models_state = p.latest_state(operations["observations"], "provider.models")
        chosen = [item for item in chosen if item.capability not in ("research", "novelty")]
        chosen += [p.ResearchProducer(capability, transactions, profile, models_state)
                   for capability in ("research", "novelty") if composition.active(capability)]
    if composition.active("export"):
        chosen.append(p.ExportProducer(transactions, policy))
    if composition.active("topics.digest"):
        topics = composition.parts.get("topics-digests") or {}
        chosen.append(p.DigestProducer(
            transactions, policy, limitation=topics.get("limitation"),
            recipient=getattr(topics.get("delivery"), "recipient_scope", None)))
    chosen += [
        p.LedgerProducer(ledger),
        p.CapacityProducer(
            transactions, policy, disk_path=p.disk_path(profile),
            volume_state=lambda: backup_volume_state(profile),
            # The backup agent's status, through PlatformControl's evidence reader.
            agent_status=agent_status_reader(composition),
            expected_volume=getattr(profile, "backup_identity", None) or None,
            # Step 58(g) (L1-29): every process's PostgreSQL failure counts.
            counts=counts_reader(evidence, POSTGRESQL_KINDS),
        ),
        # The account-mail sender's beat whenever account-controls is composed (Step
        # 53(h)), read through a callable, so the producer imports nothing of it; the
        # scheduler's pass file and the lanes' counts in every profile (Step 58(f)); the
        # sender's failed runs whenever account-controls is composed (L1-70).
        p.BackgroundWorkProducer(
            loop_status, sender_beat=sender_beat_reader(composition),
            scheduler_pass=lambda: p.read_scheduler_pass(evidence), lane_counts=lanes,
            sender_counts=(counts_reader(evidence, ("mail.sender",))
                           if composition.parts.get("account-controls") is not None
                           else None),
        ),
        p.CutoverProducer(ledger, routing=cutover_routing(composition),
                          availability=availability_folder(composition)),
    ]
    for capability in ("assistance.summary", "assistance.translation"):
        if composition.active(capability):
            chosen.append(p.AssistanceProducer(capability, profile, models_state))
    if composition.active("platform.status"):
        platform = composition.parts.get("platform-control") or {}
        chosen += [p.PlatformStatusProducer(
                       platform.get("inspect"), agent_status=agent_status_reader(composition),
                       ledger=ledger, environment=composition.environment, policy=policy),
                   p.IsolationProducer(p.isolation_folder(profile, composition.arrangement))]
    reachability = provider_reachability(composition)
    from .u8_provider_probes import count_reader, production_probe

    for capability in p.PROVIDERS:
        if composition.active(capability) and (
            composition.report["providers"].get(capability) != "unconfigured"
        ):
            chosen.append(p.ProviderProducer(
                capability, ledger,
                allowance=operations["allowance"] if capability == "provider.resend" else None,
                reachable=reachability.get(capability),
                # Step 56(a) (L1-11): only the production profile probes; a synthetic
                # profile keeps the passive check and the ledger.
                probe=production_probe(capability) if profile.is_production else None,
                # Step 56(d) (L1-12): every process's 24-hour counts for its kind.
                counts=count_reader(profile.root / "evidence", capability,
                                    composition.clock),
            ))
    if composition.active("provider.models"):
        source = p.OllamaTags() if profile.is_production else None
        chosen.append(p.ModelsProducer(source, policy, lane_counts=lanes))
    return chosen


POSTGRESQL_KINDS = ("postgresql.connection", "postgresql.transaction")


def counts_reader(folder: Path, kinds: tuple[str, ...]):
    """u8_counts' 24-hour sum of `kinds` over every process's count files, at the
    producer's `now` (Steps 58(f) and (g))."""
    from .u8_counts import counts_over

    def read(now: dt.datetime) -> tuple[int, int]:
        sums = counts_over(folder, kinds, now)
        return (sum(failed for failed, _ in sums.values()),
                sum(total for _, total in sums.values()))

    return read


def cutover_routing(composition: Composition):
    """PlatformControl's routing evidence for `operations.cutover` (Step 33): the public
    address's active origin and the count of unresolved effects, through the bounded
    status reader. None while the platform part binds no reader for this profile, so the
    capability reads unknown rather than guessing."""
    platform = composition.parts.get("platform-control") or {}
    inspect = platform.get("inspect")
    if inspect is None:
        return None
    from .modules.operations.cutover import routing_reader

    return routing_reader(composition.profile, inspect, composition.arrangement)


def agent_status_reader(composition: Composition):
    """The backup agent's latest status as the service account may see it (Step 25;
    BR6.6, NFR1.5): the observations the standing job recorded for the backup volume,
    read through PlatformControl's bounded evidence reader, never by running the agent.
    None while the platform part binds no evidence reader for this profile."""
    platform = composition.parts.get("platform-control") or {}
    latest = platform.get("evidence_reader")
    if latest is None:
        return None
    from docsuri_ops.backup_agent.status import EvidenceStatus

    return EvidenceStatus(latest)


def provider_reachability(composition: Composition) -> dict:
    """Each real adapter's own `reachable` check, by capability (Step 21): the Google and
    ORCID adapters the production profile selected, and a real account-mail adapter. A
    fixture or the local mailbox has none, so its producer reads the ledger alone."""
    controls = composition.parts.get("account-controls")
    if controls is None:
        return {}
    entry = controls["entry"]
    checks = {
        "provider." + name: adapter.reachable
        for name, adapter in (getattr(entry, "identity_providers", None) or {}).items()
        if callable(getattr(adapter, "reachable", None))
    }
    if callable(getattr(entry.account_mail, "reachable", None)):
        checks["provider.resend"] = entry.account_mail.reachable
    return checks


def operations_runtime(composition: Composition, loop_status=None):
    """The workers' producer schedule and tolerance watcher, or None while
    ServiceOperations is unavailable."""
    from .modules.operations.incidents import Incidents, ToleranceWatcher
    from .modules.operations.observation_store import ObservationStore
    from .modules.operations.observations import Observations
    from .modules.operations.producers import ProducerSchedule

    chosen = worker_producers(composition, loop_status)
    if not chosen:
        return None
    observations = Observations(ObservationStore(composition.transactions))
    schedule = ProducerSchedule(chosen, observations, composition.policy, composition.clock)
    incidents = Incidents(composition.parts["service-operations"]["ledger"],
                          environment=composition.environment)
    watcher = ToleranceWatcher(incidents, composition.readiness_view(), composition.policy,
                               composition.clock)
    return schedule, watcher


async def run_workers(composition: Composition, stopping: asyncio.Event, *,
                      watch_seconds: float | None = None) -> None:
    """The workers role: the control loop over the complete worker, the export lane,
    every producer on its timer and the tolerance watcher (BR3.3, BR3.7)."""
    from .control_runtime import ControlLoop
    from .modules.operations.incidents import WATCH_SECONDS
    from .u8_capacity import complete_capacity
    from .u8_model_lane import model_lane

    loop = lane = models = None
    if composition.worker is not None:
        lane = (composition.parts.get("approved-export") or {}).get("lane")
        # Step 21: the one-model-job lane, beside the export lane, in production only.
        models = model_lane(composition)
        loop = ControlLoop(composition.worker,
                           capacity=complete_capacity(composition.transactions))
        if lane is not None:
            lane.start()
        if models is not None:
            models.start()
        loop.start()

    def loop_status() -> dict:
        status = dict(loop.status)
        # A model lane that stopped without being asked is background work behind its
        # deadline (`lane-behind-deadline`).
        if models is not None and models.status()["state"] == "deadline":
            status["state"] = "deadline"
        return status

    runtime = operations_runtime(composition, loop_status if loop is not None else None)
    tasks = []
    if runtime is not None:
        schedule, watcher = runtime
        tasks = [
            asyncio.create_task(schedule.run(stopping)),
            asyncio.create_task(watcher.run(stopping, seconds=watch_seconds or WATCH_SECONDS)),
        ]
    try:
        await stopping.wait()
    finally:
        for task in tasks:
            await task
        if loop is not None:
            await loop.close()
        if lane is not None:
            await asyncio.to_thread(lane.stop)
        if models is not None:
            await asyncio.to_thread(models.stop)


def scheduler_tasks(composition: Composition) -> list[tuple[str, Callable[[], object]]]:
    """The scheduler role's tasks: the topics scheduler, U6's housekeeping and
    ServiceOperations' housekeeping, each one bounded call."""
    tasks = []
    topics = composition.parts.get("topics-digests")
    if topics is not None:
        tasks.append(("topics", lambda: topics["scheduler"].run_once(limit=1)))
    export = composition.parts.get("approved-export")
    if export is not None:
        repository = export["repository"]

        def export_housekeeping():
            now = composition.clock()
            return {
                "trimmed": repository.trim_settled_revisions(now),
                "purged": repository.purge_unapproved_previews(now),
                "swept": repository.sweep_stale_pending(now),
            }

        tasks.append(("export-housekeeping", export_housekeeping))
    operations = composition.parts.get("service-operations")
    if operations is not None:
        tasks.append((
            "operations-housekeeping",
            lambda: operations["observations"].delete_old(composition.clock()),
        ))
    controls = composition.parts.get("account-controls")
    limits = getattr(controls["entry"].control_policy, "entry_limits", None) if controls else None
    if limits is not None:
        from .modules.accounts.entry_limits import EntryLimits

        store = EntryLimits(composition.transactions, limits)
        # D2: finished sign-in limit rows go when their minute or wait ends (§ 3.2).
        tasks.append(("entry-limits", lambda: store.expire(now=composition.clock())))
        from .modules.accounts.u8_identity import expire_flows

        # Provider sign-in flows, with their address digests, go a minute after they
        # expire, through AccountAccess's definer function (§ 3.2).
        tasks.append(("identity-flows", lambda: expire_flows(composition.transactions)))
    return tasks


def record_scheduler_pass(folder: Path, *,
                          wall_clock: Callable[[], dt.datetime] | None = None) -> bool:
    """The scheduler's pass file (Step 58(f), L1-41), at the wall clock's real UTC time
    in every profile, never the composition's clock. A missing folder is made at 0700, a
    linked one refused. A write that fails is logged once (`scheduler`,
    `pass.unrecorded`) and gives False; it never raises."""
    from .log_events import current
    from .modules.operations.producers import write_scheduler_pass

    try:
        if folder.is_symlink():
            raise ValueError("the evidence folder cannot be a link")
        if not folder.exists():
            os.mkdir(folder, 0o700)
        write_scheduler_pass(folder, (wall_clock or (lambda: dt.datetime.now(dt.UTC)))())
        return True
    except Exception as error:  # noqa: BLE001 - the missed pass shows on background.work
        current().exception("scheduler", "pass.unrecorded", error)
        return False


def run_scheduler_once(composition: Composition) -> dict[str, str]:
    """One pass over the scheduler's tasks; a failing task never stops the others. The
    pass is then recorded for background.work's check (Step 58(f))."""
    from .log_events import current

    outcomes = {}
    for name, task in scheduler_tasks(composition):
        try:
            task()
            outcomes[name] = "done"
        except Exception as error:  # noqa: BLE001 - reduced to its type in the log
            outcomes[name] = "failed"
            current().exception("scheduler", "task.failed", error, state=name)
    record_scheduler_pass(composition.profile.root / "evidence")
    return outcomes


async def run_scheduler(composition: Composition, stopping: asyncio.Event,
                        *, seconds: float = SCHEDULER_SECONDS) -> None:
    while not stopping.is_set():
        await asyncio.to_thread(run_scheduler_once, composition)
        try:
            await asyncio.wait_for(stopping.wait(), seconds)
        except TimeoutError:
            pass
