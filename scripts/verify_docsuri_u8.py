"""Bounded, explicitly owned U8 composed-realm experiments.

The composed realm is `service-operations` with database `docsuri_u8`: one PostgreSQL
16.14 instance with pgvector, holding every owner's schema and PlatformControl's store
(`docsuri_u8_platform`). This tool never adopts another realm, extends retention,
changes old containers or treats missing, zero or skipped execution as success.
Setup and migrations are explicit; test phases inspect established resources and
preserve failed evidence. The key folders are created empty at setup; no key exists
until its owner creates the first one on first use.

It imports only identity-free helpers from the earlier tools (U8 plan Step 1). See:
`aidlc/spaces/default/intents/261016-finish-v2-rebuild/construction/u8-service-operations-integration/code-generation/code-generation-plan.md`.
"""

from __future__ import annotations

import argparse
import contextlib
import errno
import fcntl
import hashlib
import itertools
import json
import os
import re
import secrets
import selectors
import shutil
import signal
import socket
import stat
import subprocess
import sys
import time
import traceback
import uuid
from contextlib import contextmanager
from pathlib import Path

from defusedxml import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "ops/src"))

# The repository's own packages resolve only once the paths above are on sys.path.
from backend.local_profile import LocalProfile, private_bytes  # noqa: E402
from bootstrap_docsuri_u1 import SCHEMAS, amend  # noqa: E402
from u8_native import (  # noqa: E402
    NATIVE_RUNTIME,
    RELEASE_PHASES,
    NativeRefused,
    native_commands,
    python_for,
    release_identity,
    require_release_phase,
    runtime_present,
)
from verify_docsuri_u1 import GIB, LOCKS, Refused, command, digest, headroom  # noqa: E402


def group_states(pgid: int) -> list[str]:
    """The `ps` state of every process left in the group."""
    completed = subprocess.run(["ps", "-Ao", "pgid=,stat="], capture_output=True, text=True,
                               timeout=10, check=True)
    states = []
    for line in completed.stdout.splitlines():
        fields = line.split()
        if len(fields) == 2 and fields[0] == str(pgid):
            states.append(fields[1])
    return states


def signal_group(pgid: int, signum: int) -> None:
    """Signal a process group that may already be gone.

    macOS answers EPERM, not ESRCH, when every process left in the group has exited and
    waits to be reaped (a zombie): after `stop` reaps the leader, the realm's exited
    children can sit there until launchd reaps them. That group is gone; EPERM with any
    live member left is a real refusal and is raised.
    """
    try:
        os.killpg(pgid, signum)
    except ProcessLookupError:
        return
    except PermissionError:
        if any(not state.startswith("Z") for state in group_states(pgid)):
            raise


def stop(process: subprocess.Popen) -> None:
    """Terminate the process group before reaping its leader (U3's sequence), tolerating
    a group whose only members left are exited processes."""
    signal_group(process.pid, signal.SIGTERM)
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        pass
    signal_group(process.pid, signal.SIGKILL)
    process.wait(timeout=3)

RUN = Path("/tmp/docsuri-u8-run").resolve()
_RUNNER_OWNED = False
# `backend/.venv` in the development tree, else the release's own `.venv` (Step 43).
PYTHON = python_for(ROOT)
# `--database docker` (the default) or `native`, the arrangement's pinned runtime (the
# release's performance phase); `--playwright <checkout>` names your checkout's frontend.
DATABASE_KIND = "docker"
PLAYWRIGHT_FRONTEND: Path | None = None
UNIT = "u8-service-operations-integration"
REALM = "service-operations"
DATABASE = "docsuri_u8"
PLATFORM_DATABASE = "docsuri_u8_platform"
# Decision "The composed realm's addresses": every listener on 127.0.0.1.
APPLICATION_PORT = 18109  # the v2 host, plain HTTP (production: 18200)
PUBLIC_PORT = 18110  # the public stand-in, TLS (production: Cloudflare and the tunnel)
MAINTENANCE_PORT = 18111  # the maintenance server (production: 18201)
V1_API_PORT = 18112  # the synthetic v1's API (v1: 8000)
V1_WEB_PORT = 18113  # the synthetic v1's web (v1: 3000)
IDENTITY_PORT = 18114  # the identity stand-in, on https://localhost (a different site)
DATABASE_PORT = 15509  # the realm's PostgreSQL with pgvector (production: 15432)
V1_DATABASE_PORT = 15510  # v1's data-plane stand-ins: PostgreSQL,
V1_REDIS_PORT = 16389  # Redis,
V1_OPENSEARCH_PORT = 19209  # OpenSearch
V1_MINIO_PORT = 19009  # and MinIO
REALM_PORTS = (
    APPLICATION_PORT, PUBLIC_PORT, MAINTENANCE_PORT, V1_API_PORT, V1_WEB_PORT,
    IDENTITY_PORT, DATABASE_PORT, V1_DATABASE_PORT, V1_REDIS_PORT, V1_OPENSEARCH_PORT,
    V1_MINIO_PORT,
)
LABEL = "dev.docsuri.u8.run"
POLICY = "u8-synthetic-v1"
# One bound for every supervised phase. An overrun fails the phase; it is never
# escaped by splitting a pass, excluding tests or lowering a floor.
PHASE_SECONDS = 300
# A realm's retention from setup: exactly 24 hours (U8 plan Step 95(d)).
REALM_SECONDS = 86400
MAX_LOG = 16 * 1024**2
MAX_RSS = GIB
# The realm's database: 2 GiB of memory, 512 MB of shared buffers and 50 connections
# (U8 plan Step 1, after performance-design § 3.1 and infrastructure-specification § 2).
DB_MEMORY = 2 * GIB
RECOVERY_MEMORY = 512 * 1024**2
DB_SHM = GIB
IMAGE_BUILD_SECONDS = 600
KEY_FOLDERS = ("export-keys", "control-keys", "verifier-key", "cursor-key")
TEST_ROOT = "tests/u8_service_operations_integration"
PYTEST_INI = "backend/pytest.u8-service-operations-integration.ini"
COVERAGE_RC = "backend/.coveragerc.u8"
WORKFLOW = ".github/workflows/u8-complete-verification.yml"
OWNERS = frozenset(SCHEMAS) | {"research", "topics", "export"}
OWNER_CONNECTION_LIMIT = 4
# The person's decision of 2026-10-23 ("Split into parts"): `integration` runs in parts of
# its files and `coverage` as one part per lane part, each under its own bound, appending
# to one coverage data file; `coverage-report` combines them. The names `integration` and
# `coverage` run their parts in order.
# Build and Test loop-back 1 (U8 plan Step 46(a)): four integration parts, chosen from the
# 2026-10-31 coverage run, where `coverage-integration-1` took 202.7 s (140.5 s of it in
# `test_cutover_journeys.py`) and `coverage-integration-2` took 189.0 s. Files stay whole
# and keep their order; `integration-3` runs before `integration-4`, so the cutover
# journeys still run before the migration files.
INTEGRATION_HALVES = {
    # `test_complete_assistance.py` runs first: PaperAssistance admits at most four open or
    # running items realm-wide, and later files leave open admissions behind.
    "integration-1": (
        "test_complete_assistance.py",
        # Step 87(a): its assistance jobs end terminal and settled, so it runs before
        # every file that leaves an assistance admission open.
        "test_accepting_work.py",
        "test_account_routes.py", "test_admission.py",
        "test_backup_agent_in_the_realm.py", "test_backup_agent_restore.py",
        "test_body_limit.py", "test_boundary.py", "test_complete_controls.py",
        "test_complete_usage.py", "test_first_effects.py",
        "test_first_sign_in.py", "test_host_routes.py",
        "test_import_operations.py", "test_imported_usage.py", "test_jobs_api.py",
        # Step 84(a): a paper's assets through the complete host.
        "test_paper_assets.py",
        # Step 86(a): no secret in any log, observation, incident or ledger record.
        "test_log_exposure.py",
    ),
    "integration-2": (
        "test_complete_library.py",
        "test_lifecycle_manifest.py", "test_navigation_api.py",
        "test_operations_api.py", "test_personal_settings.py",
        "test_production_restore.py",
        "test_reactivation.py", "test_rehearsal_bound.py", "test_restore_verification.py",
        "test_route_inventory.py", "test_sign_in_limits.py", "test_signed_in_search.py",
        "test_static_routes.py", "test_tombstone_replay.py",
        "test_u5_seams.py", "test_waiting_parts.py", "test_worker_isolation.py",
        # Step 44 (your decision of 2026-10-24, "Move, scope tools, test U2"): production
        # fails closed without U8's parts.
        "test_u2_fail_closed.py",
        # Step 22 and Step 24 (your decisions of 2026-10-24): the model lane and paper
        # assistance at production's corpus limits, each on the production stand-in.
        "test_model_lane.py", "test_large_paper_assistance.py",
    ),
    "integration-3": (
        "test_account_mail_routes.py", "test_cutover_journeys.py", "test_health_api.py",
    ),
    "integration-4": (
        "test_migration_run.py", "test_production_migration_platform.py",
        "test_start_checks.py",
        # Step 40 (your decision of 2026-10-24): production composed with every real
        # builder, in live and in rehearsal.
        "test_production_composition.py",
        # Step 52(g): the migration gate and the import's port, on the production stand-in.
        "test_production_import_runner.py",
    ),
}
# The person's decision of 2026-10-26 ("Split it in two"): `operations` runs in parts of
# its files, each under its own bound, with and without coverage. The parts are chosen
# by the files' measured times (the 964-test run of 2026-10-26: 245.6 s of test time, of
# which `test_production_cutover_wiring.py` alone took 141.1 s). Files stay whole.
# Build and Test loop-back 1 (U8 plan Step 46(b)): `operations-1` took 197.4 s on
# 2026-10-31, most of it in `test_production_cutover_wiring.py`, so `operations-3` takes
# the five files later steps change (the three backup-agent files, `test_production_wiring.py`
# and `test_standing_lanes.py`); `operations-1` keeps that file first and 18 others.
OPERATIONS_HALVES = {
    "operations-1": (
        "test_production_cutover_wiring.py",
        "test_backup_agent_status.py",
        "test_built_file_pins.py", "test_credential_release.py",
        "test_exclusion_both_ways.py", "test_fixture_clock.py", "test_logrotate_rules.py",
        "test_production_migration_words.py",
        "test_recovery_words.py", "test_release_guard.py", "test_role_page_reads.py",
        "test_root_jobs.py", "test_snapshot_archives.py",
        "test_templates.py", "test_u2_ci_coverage.py", "test_u2_restore_image.py",
        "test_u3_scope.py", "test_u4_scope.py", "test_u8_phase_helpers.py",
    ),
    "operations-2": (
        "test_allowlist_sites.py", "test_assemblies_alone.py", "test_availability.py",
        "test_cutover_decide_words.py", "test_decisions.py", "test_drivers.py",
        "test_fixed_programs.py", "test_import_boundaries.py", "test_installer.py",
        "test_inventory_words.py", "test_isolation_check.py", "test_ledger_cli.py",
        "test_migration_words.py", "test_production_tool.py", "test_realm_checks.py",
        "test_reconcile_unknown.py", "test_release_install.py", "test_service_words.py",
        "test_u2_scope.py", "test_u5_scope.py", "test_u7_fail_closed.py",
        "test_u7_scope.py", "test_u8_protocols.py", "test_u8_tool.py",
        "test_v1_environment.py",
    ),
    "operations-3": (
        "test_backup_agent_commands.py", "test_backup_agent_disposal.py",
        "test_backup_agent_writing.py", "test_production_wiring.py",
        "test_standing_lanes.py", "test_scram_sites.py",  # Step 164(i), NFR3.3
        # Step 52(h): U6's lane, service and binding import no U8 module.
        "test_u6_scope.py",
        # Step 97(a), (g): Ruff on U8's targets with E,F,I,UP,B at 100 (Step 95(l)).
        "test_lint_gate.py",
        # Step 97(a), (d)-(f): the build's inline-script gate, the floors, bounds, budgets
        # and targets, and the two coverage reports.
        "test_build_workspace_gate.py", "test_u8_quality_floors.py",
        "test_u8_coverage_reports.py",
        # Step 98(a), (d)-(e): nothing the instructions never mock is replaced (L1-35), and
        # every secret a test uses is generated per run (L1-36).
        "test_never_mocked.py", "test_no_real_secrets.py",
        # Package G3 (your answer of 2026-11-11, "Scratch container"): the peer map and the
        # root-owned rule files, proved against a real PostgreSQL 16.
        "test_peer_map_proof.py",
        # Step 98(f), after Step 103(b): the required items (98(b)), the test volume and
        # key boundaries (98(c)), and the macOS report's scope.
        "test_required_items.py", "test_component_volume.py", "test_macos_report_scope.py",
    ),
}
# Build and Test loop-back 1 (U8 plan Step 46(b)): the component folder took 119.1 s on
# 2026-10-31, before the slower cases of later steps, so it runs in two parts.
# `component-1` holds the Stage and journey-database files; `component-2` the others.
COMPONENT_HALVES = {
    "component-1": (
        "test_cutover_machine.py", "test_cutover_words.py", "test_disposal_pass.py",
        "test_soak_and_rehearsal.py", "test_volume_retirement.py",
    ),
    "component-2": (
        "test_account_mail.py", "test_allowance.py", "test_backups_evidence.py",
        "test_capacity.py", "test_complete_search.py", "test_consumer_inventory.py",
        "test_corpus_limits.py", "test_earlier_profile_health.py",
        "test_identity_providers.py", "test_incidents.py", "test_latency_summaries.py",
        "test_ledger_component.py", "test_ledger_damage.py", "test_log_events.py",
        "test_maintenance_server.py", "test_misfit_decisions.py", "test_model_evidence.py",
        "test_observations.py", "test_outward_wiring.py", "test_producers.py",
        "test_production_policy.py", "test_production_profile.py",
        "test_provider_activation.py", "test_readiness.py", "test_recovery_effects.py",
        "test_recovery_requests.py", "test_registry.py", "test_request_context.py",
        "test_research_execution.py", "test_research_model.py",
        "test_research_participant.py", "test_retained_copies.py",
        "test_retention_date.py", "test_tombstones.py", "test_transactions_scram.py",
        "test_u2_seam_defaults.py", "test_u5_seam_defaults.py", "test_u7_seam_defaults.py",
        # Step 52(h): the dispatch's and the export lane's per-item hooks.
        "test_job_hook_defaults.py",
        # Step 54(f): one password check at a time, each waiting at most two seconds.
        "test_password_checks.py",
        # Step 54(t): every refused sign-in reaches the same email wait (L1-85).
        "test_sign_in_failures.py",
    ),
}
# Each split lane's parts, by the folder that holds its files.
LANE_HALVES = {"component": COMPONENT_HALVES, "integration": INTEGRATION_HALVES,
               "operations": OPERATIONS_HALVES}
# One coverage part per lane part (Step 46(c)): eleven parts, all appending to the one
# data file; only `coverage-database` begins it.
COVERAGE_PARTS = (
    "coverage-database", "coverage-repository",
    "coverage-component-1", "coverage-component-2",
    "coverage-integration-1", "coverage-integration-2",
    "coverage-integration-3", "coverage-integration-4",
    "coverage-operations-1", "coverage-operations-2", "coverage-operations-3",
)
COVERAGE_DATA = ".coverage-u8"
TEST_PHASES = (
    "database",
    "repository",
    "component",
    *COMPONENT_HALVES,
    "integration",
    *INTEGRATION_HALVES,
    "operations",
    *OPERATIONS_HALVES,
    "coverage",
    *COVERAGE_PARTS,
    "coverage-report",
)
V1_PHASES = ("v1-up", "v1-down")
# Step 43's phases (`scripts/u8_phases.py`), in the plan's order; Step 114(i) adds the
# record-only `capacity-burst` after `performance`.
STEP43_PHASES = (
    "fixtures", "serve", "browser-recovery", "browser-journeys", "browser-lifecycle",
    "browser-migration",
    "browser-cutover", "browser-isolation", "security", "accessibility",
    "accessibility-signed-out", "accessibility-keyboard", "accessibility-screens",
    "restore-paths",
    "build-gate", "compatibility", "performance", "capacity-burst", "repair-exercise",
    "restart-host",
    "restart-database", "frontend", "arrangement", "verification-run",
)
PHASES = ("setup", "migrate", *TEST_PHASES, *V1_PHASES, *STEP43_PHASES, "u2-regression",
          "archive-owned", "teardown", "release-performance")
# `release-performance` (cicd-pipeline § 5.2; your decision of 2026-10-24): each step under
# its own bound; `fixtures` runs until the corpus is complete, at most this many times.
RELEASE_FIXTURE_RUNS = 4
SYNTHETIC_V1 = "scripts/u8_synthetic_v1.py"
# The realm budget (round 14's choice): U5's per-database 1–100 real-send allocation is
# spent by the integration folder (about 13 sends a run), so an integration-carrying phase
# refuses when fewer than this many remain, naming the fresh realm it needs.
REAL_SEND_LIMIT = 100
REAL_SEND_HEADROOM = 30
SENDING_PHASES = (*INTEGRATION_HALVES, *(f"coverage-{part}" for part in INTEGRATION_HALVES))
EVIDENCE_PATTERN = "*-evidence-*.json"
# Login roles that receive USAGE on schema accounts and EXECUTE on the session guard.
SESSION_GUARD_LOGINS = (
    "library",
    "personalization",
    "discovery",
    "usage",
    "assistance",
    "research",
    "topics",
    "export",
)
CORPUS_GUARD_LOGINS = ("library", "discovery", "assistance", "research", "topics")


def require(args: list[str], **kwargs) -> subprocess.CompletedProcess:
    result = command(args, **kwargs)
    if result.returncode:
        raise Refused(f"command failed ({result.returncode}): {args[0]}")
    return result


def require_private_directory(path: Path, message: str) -> None:
    """A real directory (never a link), owned by this user, at exactly mode 0700."""
    info = path.lstat()
    if (
        not stat.S_ISDIR(info.st_mode)
        or info.st_uid != os.getuid()
        or stat.S_IMODE(info.st_mode) != 0o700
    ):
        raise Refused(message)


def fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def private_json(path: Path, value: object, *, root: Path = RUN) -> None:
    if path.parent != root or path.is_symlink():
        raise Refused("private output outside owned run")
    require_private_directory(root, "run directory custody differs")
    pending = path.with_name(path.name + ".pending-" + secrets.token_hex(8))
    descriptor = os.open(
        pending, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600
    )
    try:
        with os.fdopen(descriptor, "w") as stream:
            json.dump(value, stream, sort_keys=True, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(pending, path)
        fsync_directory(root)
    finally:
        pending.unlink(missing_ok=True)


@contextmanager
def exclusive():
    """One U8 runner phase, including setup, across processes."""
    global _RUNNER_OWNED
    path = RUN.parent / ".docsuri-u8-runner.lock"
    descriptor = os.open(
        path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600
    )
    acquired = False
    try:
        info = os.fstat(descriptor)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) != 0o600
            or info.st_nlink != 1
        ):
            raise Refused("runner lock custody differs")
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise Refused("another U8 phase is active") from error
        os.ftruncate(descriptor, 0)
        os.write(descriptor, str(os.getpid()).encode())
        os.fsync(descriptor)
        _RUNNER_OWNED = True
        acquired = True
        yield
    finally:
        if acquired:
            _RUNNER_OWNED = False
        os.close(descriptor)


# --- The database image (decision "The pgvector pin and the lane's image") ---------------


def image_pins() -> dict:
    from docsuri_ops.arrangement import runtimes

    return {
        "postgresql": runtimes.POSTGRESQL_VERSION,
        "pgvector": runtimes.PGVECTOR.version,
        "pgvectorSha256": runtimes.PGVECTOR.sha256,
        "base": runtimes.POSTGRES_BASE_IMAGE,
        "tag": runtimes.DATABASE_IMAGE_TAG,
        "labels": dict(runtimes.DATABASE_IMAGE_LABELS),
        "official": runtimes.PGVECTOR_OFFICIAL_IMAGE,
    }


def inspect_image(reference: str) -> dict | None:
    result = command(["docker", "image", "inspect", reference])
    if result.returncode:
        return None
    records = json.loads(result.stdout)
    if len(records) != 1:
        raise Refused("ambiguous U8 database image")
    return records[0]


def database_image() -> str:
    """The realm's image ID: pgvector's official digest for the pinned pair if one is
    published, else the fallback build from the `postgres:16.14` digest and pgvector's
    pinned source, built once and then reused. Its labels must carry the pins."""
    from docsuri_ops.arrangement import runtimes

    pins = image_pins()
    if pins["official"] is not None:
        record = inspect_image(pins["official"])
        if record is None:
            raise Refused("pinned pgvector image is not present; pull it by digest")
        return record["Id"]
    record = inspect_image(pins["tag"])
    if record is None:
        args = ["docker", "build", "--quiet", "--tag", pins["tag"]]
        for name, value in (
            ("BASE_IMAGE", runtimes.POSTGRES_BASE_IMAGE),
            ("PGVECTOR_VERSION", runtimes.PGVECTOR.version),
            ("PGVECTOR_URL", runtimes.PGVECTOR.url),
            ("PGVECTOR_SHA1", runtimes.PGVECTOR.published_sha1),
            ("PGVECTOR_SHA256", runtimes.PGVECTOR.sha256),
        ):
            args += ["--build-arg", f"{name}={value}"]
        for name, value in sorted(pins["labels"].items()):
            args += ["--label", f"{name}={value}"]
        args.append(str(ROOT / "scripts/u8_database_image"))
        require(args, timeout=IMAGE_BUILD_SECONDS)
        record = inspect_image(pins["tag"])
        if record is None:
            raise Refused("U8 database image build left no image")
    labels = record.get("Config", {}).get("Labels") or {}
    if any(labels.get(name) != value for name, value in pins["labels"].items()):
        raise Refused("U8 database image labels differ from the pinned runtimes")
    return record["Id"]


# --- Manifest and resources -------------------------------------------------------------


def manifest(path: Path) -> tuple[LocalProfile, dict]:
    profile = LocalProfile.load(path)
    value = json.loads(private_bytes(path))
    if (
        profile.root != RUN
        or profile.realm != REALM
        or profile.database_name != DATABASE
    ):
        raise Refused("U8 requires its own explicit realm")
    require_manifest_identity(value)
    # U8 plan Step 95(d): a realm lives exactly the 24 hours `setup` gives it. The
    # profile bounds expiry only by now + 24 h, so a regenerated marker could carry a
    # later one.
    created, expires = value.get("createdAt"), value.get("expiresAt")
    if (not isinstance(created, int | float) or isinstance(created, bool)
            or created > time.time() or expires != created + REALM_SECONDS):
        raise Refused("U8 manifest retention differs from setup's 24 hours")
    return profile, value


def require_manifest_identity(value: dict, *, current_pins: bool = True) -> None:
    """Bind runtime metadata to this runner's resources and pinned image. Preservation
    accepts an environment built under earlier pins, so it can always be set aside."""
    if value.get("policy") != POLICY or (
        current_pins and value.get("databaseImagePins") != image_pins()
    ):
        raise Refused("U8 image or policy identity differs")
    if (
        value.get("container") != value["runId"]
        or value.get("volume") != value["runId"] + "-pgdata"
        or value.get("platformDatabase") != PLATFORM_DATABASE
        or value.get("publicPort") != PUBLIC_PORT
    ):
        raise Refused("U8 resource names differ from run identity")


def preservation_manifest(path: Path) -> dict:
    """Validated original metadata of U8's own realm for preservation only.

    Unlike manifest(), an expired realm is accepted, because expiry prevents
    execution but must not prevent setting an idle realm aside (its v1's stop
    included). It never yields a runtime profile and never changes the recorded
    expiry.
    """
    value = LocalProfile.preservation_identity(path)
    if (
        path != RUN / "environment.json"
        or value.get("unit") != UNIT
        or value.get("realm") != REALM
        or value.get("database") != DATABASE
    ):
        raise Refused("U8 preservation requires its own explicit realm")
    require_manifest_identity(value, current_pins=False)
    return value


def require_key_folders() -> None:
    """Each key folder exists inside the owned run, private, and is never a link."""
    for name in KEY_FOLDERS:
        require_private_directory(RUN / name, f"{name} folder custody differs")


def native(value: dict | None = None) -> bool:
    """Whether the realm runs on the native database (the manifest's record, or this
    run's `--database` before a manifest exists)."""
    if value is not None:
        return value.get("databaseKind") == "native"
    return DATABASE_KIND == "native"


def require_native_running(value: dict) -> None:
    """The native server is the run's own and answers: its data folder private in the run
    root and `pg_ctl status` reporting it running."""
    data = RUN / "pgdata"
    require_private_directory(data, "native database folder custody differs")
    status = command(native_commands(RUN, port=DATABASE_PORT)["status"], timeout=15)
    if status.returncode != 0:
        raise Refused("the native database is not running; start it or set the realm aside")


def require_resources(value: dict) -> None:
    if native(value):
        require_native_running(value)
        return
    for kind, name in (("container", value["container"]), ("volume", value["volume"])):
        records = json.loads(require(["docker", kind, "inspect", name]).stdout)
        if len(records) != 1:
            raise Refused("ambiguous U8 resource")
        record = records[0]
        labels = (
            record.get("Labels", {})
            if kind == "volume"
            else record["Config"].get("Labels", {})
        )
        if labels.get(LABEL) != value["runId"]:
            raise Refused("missing or foreign U8 resource; preserve for recovery")
        if kind == "container":
            require_container_bounds(record, value)


def require_container_bounds(record: dict, value: dict) -> None:
    host = record["HostConfig"]
    if (
        record["Image"] != value["databaseImage"]
        or host["Memory"] != DB_MEMORY
        or host["MemorySwap"] != DB_MEMORY
        or host["ShmSize"] != DB_SHM
        or host["NanoCpus"] != 2_000_000_000
        or host["PidsLimit"] != 128
        or not host["ReadonlyRootfs"]
        or host["PortBindings"]
        != {"5432/tcp": [{"HostIp": "127.0.0.1", "HostPort": str(DATABASE_PORT)}]}
        or not record["State"]["Running"]
    ):
        raise Refused("owned database bounds or running state differ")
    volumes = [item for item in record["Mounts"] if item["Type"] == "volume"]
    if (
        len(volumes) != 1
        or volumes[0]["Name"] != value["volume"]
        or volumes[0]["Destination"] != "/var/lib/postgresql/data"
    ):
        raise Refused("database volume binding differs")


def memory_available(raw: str) -> int:
    match = re.search(r"^MemAvailable:\s+(\d+) kB$", raw, re.MULTILINE)
    if match is None:
        raise Refused("Docker available memory could not be measured")
    return int(match[1]) * 1024


def docker_available_memory(image: str) -> int:
    """Observe the daemon's kernel rather than macOS RAM. The probe has no network,
    mounts, secrets or writable root and is bounded to 16 MiB/8 PIDs."""
    raw = require(
        [
            "docker", "run", "--rm", "--network", "none", "--read-only",
            "--memory", "16m", "--memory-swap", "16m", "--cpus", "0.1",
            "--pids-limit", "8", "--entrypoint", "cat", image, "/proc/meminfo",
        ],
        timeout=15,
    ).stdout
    return memory_available(raw)


# Step 98(d) (L1-56): `operations/test_production_tool.py` runs its database cases on a
# production-shaped PostgreSQL instance of its own, whose container carries this label key
# valued with the realm's run ID (`host_flows.production_instance`). A part's bound stops a
# module run with SIGTERM and then SIGKILL, which skips the module's own removal, so the
# runner removes every container under the key after each child of the part that holds the
# module, whatever its outcome, and in `archive-owned`.
PRODUCTION_INSTANCE_LABEL = "dev.docsuri.u8.production-instance"
PRODUCTION_INSTANCE_FILE = "test_production_tool.py"
# Package G3 (your answer of 2026-11-11, "Scratch container"): the peer map's proof against
# a real PostgreSQL 16 (`operations/test_peer_map_proof.py`) runs in a short-lived
# container of the realm's image under this label key, valued with the realm's run ID. It
# is removed the same way: after each child of the part that holds the module, and in
# `archive-owned`.
PEER_PROOF_LABEL = "dev.docsuri.u8.peer-proof"
PEER_PROOF_FILE = "test_peer_map_proof.py"


def _parts_holding(name: str) -> frozenset[str]:
    """The operations part that holds the file `name`, and its coverage part."""
    parts = {part for part, files in OPERATIONS_HALVES.items() if name in files}
    return frozenset(parts | {f"coverage-{part}" for part in parts})


def production_instance_phases() -> frozenset[str]:
    """The operations part that holds the production tool's tests, and its coverage part."""
    return _parts_holding(PRODUCTION_INSTANCE_FILE)


def peer_proof_phases() -> frozenset[str]:
    """The operations part that holds the peer map's proof, and its coverage part."""
    return _parts_holding(PEER_PROOF_FILE)


def _remove_labelled(label: str, what: str) -> list[str]:
    """Stop and remove every container under the label key `label`, whatever run ID it
    names (realms run one at a time); a container without the key is untouched."""
    listed = command(["docker", "ps", "-a", "--filter", f"label={label}",
                      "--format", "{{.ID}}"], timeout=30)
    if listed.returncode != 0:
        raise Refused(f"the {what}s could not be listed")
    removed = []
    for container in listed.stdout.split():
        if command(["docker", "rm", "-f", "-v", container], timeout=60).returncode != 0:
            raise Refused(f"a {what} could not be removed")
        removed.append(container)
    return removed


def remove_production_instances() -> list[str]:
    """Every container under the production instance's label key (`_remove_labelled`)."""
    return _remove_labelled(PRODUCTION_INSTANCE_LABEL, "production instance")


def remove_peer_proofs() -> list[str]:
    """Every container under the peer map proof's label key (`_remove_labelled`)."""
    return _remove_labelled(PEER_PROOF_LABEL, "peer map proof")


def preflight(*, established: bool = False) -> dict:
    """The host's disk floor, the pinned image, and room for the database and the
    recovery reserve inside Docker's own kernel. Nothing here is relaxed to fit. On the
    native database: the disk floor and the pinned runtime's programs."""
    headroom(existing=True)
    free = shutil.disk_usage(ROOT).free
    if free < 4 * GIB:
        raise Refused("U8 disk recovery reserve unavailable")
    if native():
        if not runtime_present():
            raise Refused("the pinned PostgreSQL runtime is not installed")
        return {"hostFreeBytes": free, "databaseImage": f"native:{NATIVE_RUNTIME.name}",
                "databaseLimitBytes": None, "recoveryReserveBytes": RECOVERY_MEMORY}
    image = database_image()
    info = json.loads(require(["docker", "info", "--format", "{{json .}}"]).stdout)
    if info["MemTotal"] < DB_MEMORY + RECOVERY_MEMORY:
        raise Refused(
            f"Docker total memory {info['MemTotal']} cannot fit the database "
            f"({DB_MEMORY}) and the recovery reserve ({RECOVERY_MEMORY})"
        )
    available = docker_available_memory(image)
    required = RECOVERY_MEMORY if established else DB_MEMORY + RECOVERY_MEMORY
    if available < required:
        raise Refused(
            f"Docker available bytes {available} below required allocation and reserve {required}"
        )
    return {
        "hostFreeBytes": free,
        "dockerTotalBytes": info["MemTotal"],
        "dockerAvailableBytes": available,
        "databaseLimitBytes": DB_MEMORY,
        "recoveryReserveBytes": RECOVERY_MEMORY,
        "databaseImage": image,
    }


def check_ports() -> None:
    for port in REALM_PORTS:
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", port))


def require_stopped(port: int = APPLICATION_PORT) -> None:
    with socket.socket() as listener:
        if listener.connect_ex(("127.0.0.1", port)) == 0:
            raise Refused("stop the application before this phase")


def database_command(value: dict) -> list[str]:
    return [
        "docker", "run", "-d",
        "--name", value["container"],
        "--label", f"{LABEL}={value['runId']}",
        "--memory", "2g", "--memory-swap", "2g", "--shm-size", "1g",
        "--cpus", "2", "--pids-limit", "128",
        "--read-only",
        "--tmpfs", "/tmp:rw,noexec,nosuid,size=16m",
        "--tmpfs", "/var/run/postgresql:rw,noexec,nosuid,size=16m",
        "-p", f"127.0.0.1:{DATABASE_PORT}:5432",
        "--mount", f"type=volume,src={value['volume']},dst=/var/lib/postgresql/data",
        "-e", "POSTGRES_PASSWORD",
        "-e", f"POSTGRES_DB={DATABASE}",
        # tech-stack-decisions: v2's databases are UTF8 with the C locale everywhere.
        "-e",
        (
            "POSTGRES_INITDB_ARGS=--data-checksums --auth-host=scram-sha-256 "
            "--encoding=UTF8 --locale=C"
        ),
        value["databaseImage"],
        "-c", "shared_buffers=512MB",
        "-c", "max_connections=50",
        "-c", "work_mem=16MB",
        "-c", "maintenance_work_mem=256MB",
        "-c", "password_encryption=scram-sha-256",
        "-c", "statement_timeout=3000",
        "-c", "lock_timeout=1000",
        "-c", "idle_in_transaction_session_timeout=5000",
        "-c", "max_wal_size=1GB",
        "-c", "wal_keep_size=0",
        "-c", "archive_mode=off",
        "-c", "max_replication_slots=0",
        "-c", "max_wal_senders=0",
        # security-design § 7.2's log settings, as production's database has them
        # (Step 79(d)): no statement text or parameter value reaches a log line.
        "-c", "log_min_messages=log",
        "-c", "log_error_verbosity=terse",
        "-c", "log_min_error_statement=panic",
        "-c", "log_statement=none",
        "-c", "log_min_duration_statement=-1",
        "-c", "log_parameter_max_length=0",
        "-c", "log_parameter_max_length_on_error=0",
    ]


def create_key_folders() -> None:
    """The empty, private key folders; no key is created here."""
    for name in KEY_FOLDERS:
        folder = RUN / name
        if folder.exists() or folder.is_symlink():
            raise Refused(f"{name} folder already exists in a fresh run")
        os.mkdir(folder, 0o700)
        os.chmod(folder, 0o700, follow_symlinks=False)
    fsync_directory(RUN)
    require_key_folders()
    for name in KEY_FOLDERS:
        if any((RUN / name).iterdir()):
            raise Refused(f"fresh {name} folder is not empty")


def write_v1_password(root: Path, run_id: str) -> None:
    """The synthetic v1's password, made once per realm (U8 plan Step 96(d), L1-36):
    `v1-password.json` (0600) beside `operator.json`, read by `u8_fixtures.v1_dataset`."""
    private_json(root / "v1-password.json",
                 {"runId": run_id, "password": "V1!" + secrets.token_urlsafe(24)}, root=root)


def write_identity_clients(root: Path, run_id: str) -> None:
    """The identity stand-in clients' secrets, made once per realm (U8 plan Step 96(d)):
    `identity-clients.json` (0600), read by `serve_docsuri_u8.standin_secrets`. A value
    made per process would leave a killed serve's environment file in place."""
    private_json(root / "identity-clients.json", {
        "runId": run_id,
        **{provider: f"realm-{provider}-client-secret-" + secrets.token_hex(8)
           for provider in ("google", "orcid")},
    }, root=root)


def setup(path: Path) -> dict:
    if RUN.exists():
        require_private_directory(RUN, "existing directory custody differs")
        if any(RUN.iterdir()):
            _, value = manifest(path)
            require_resources(value)
            require_key_folders()
            return {"state": "preserved", "runId": value["runId"]}
    resources = preflight()
    check_ports()
    RUN.mkdir(mode=0o700, exist_ok=True)
    run_id = "docsuri-u8-" + secrets.token_hex(8)
    now = time.time()
    value = {
        "unit": UNIT,
        "profile": "synthetic-local",
        "repository": str(ROOT),
        "runId": run_id,
        "container": run_id,
        "volume": run_id + "-pgdata",
        "databaseImage": resources["databaseImage"],
        "databaseImagePins": image_pins(),
        "database": DATABASE,
        "platformDatabase": PLATFORM_DATABASE,
        "realm": REALM,
        "databasePort": DATABASE_PORT,
        "applicationPort": APPLICATION_PORT,
        "publicPort": PUBLIC_PORT,
        "maintenancePort": MAINTENANCE_PORT,
        "createdAt": now,
        "expiresAt": now + 86400,
        "sourceSha": require(["git", "rev-parse", "HEAD"]).stdout.strip(),
        "locks": {name: digest(ROOT / name) for name in LOCKS},
        "policy": POLICY,
        "fixtureAccounts": [],
        "fixturePapers": [],
    }
    if native():
        value["databaseKind"] = "native"
    private_json(path, value)
    private_json(RUN / "ownership.json", {"runId": run_id, "manifestSha256": digest(path)})
    password = secrets.token_urlsafe(32)
    private_json(RUN / "migration-credentials.json", {"databaseAdminPassword": password})
    private_json(RUN / "setup-resources.json", resources)
    # The realm driver's synthetic operator identity (decision "Recording your decisions
    # in the realm"); production reads the actor from SUDO_UID instead.
    private_json(
        RUN / "operator.json",
        {
            "runId": run_id,
            "operatorId": str(uuid.uuid5(uuid.NAMESPACE_URL, run_id + ":operator")),
            "kind": "synthetic-operator",
        },
    )
    write_v1_password(RUN, run_id)
    write_identity_clients(RUN, run_id)
    create_key_folders()
    if native(value):
        start_native(value, password)
    else:
        require(["docker", "volume", "create", "--label", f"{LABEL}={run_id}",
                 value["volume"]])
        require(database_command(value), extra={"POSTGRES_PASSWORD": password})
    wait_database_endpoint(value)
    base = migrate(path, base_only=True)
    return {
        "state": "base-installed",
        "runId": run_id,
        "chainApplied": False,
        "keyFolders": {name: {"mode": "0700", "entries": 0} for name in KEY_FOLDERS},
        "resources": resources,
        "base": base,
    }


def start_native(value: dict, password: str) -> None:
    """The native database (Step 43): `initdb` into the run root with the superuser's
    password from a private file that is removed at once, then the server started as the
    invoking account on the realm's port, and the realm's database created."""
    import psycopg
    from psycopg import sql

    secret = RUN / "native-superuser.pw"
    commands = native_commands(RUN, port=DATABASE_PORT, password_file=secret)
    descriptor = os.open(secret, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(descriptor, "w") as stream:
            stream.write(password + "\n")
        os.mkdir(RUN / "pgsocket", 0o700)
        require(commands["initdb"], timeout=PHASE_SECONDS)
    finally:
        secret.unlink(missing_ok=True)
    os.chmod(RUN / "pgdata", 0o700)
    require(commands["start"], timeout=120)
    deadline = time.monotonic() + 60
    while True:
        try:
            with connect_admin(value, dbname="postgres", autocommit=True) as conn:
                conn.execute(sql.SQL("CREATE DATABASE {} ENCODING 'UTF8' LOCALE 'C' "
                                     "TEMPLATE template0").format(sql.Identifier(DATABASE)))
            return
        except (psycopg.OperationalError, psycopg.InterfaceError) as failure:
            if time.monotonic() > deadline:
                raise Refused(
                    "native database startup failed; owned resources preserved"
                ) from failure
            time.sleep(0.5)


def stop_native() -> None:
    """An acknowledged fast stop of the native server; its data folder is kept."""
    require(native_commands(RUN, port=DATABASE_PORT)["stop"], timeout=120)
    if command(native_commands(RUN, port=DATABASE_PORT)["status"], timeout=15).returncode == 0:
        raise Refused("native database stop was not acknowledged; directory retained")


def admin_password(root: Path = RUN) -> str:
    return json.loads(private_bytes(root / "migration-credentials.json"))["databaseAdminPassword"]


def connect_admin(
    value: dict,
    *,
    dbname: str = DATABASE,
    autocommit: bool = False,
    port: int = DATABASE_PORT,
    root: Path = RUN,
):
    import psycopg

    return psycopg.connect(
        host="127.0.0.1",
        port=port,
        dbname=dbname,
        user="postgres",
        password=admin_password(root),
        connect_timeout=3,
        autocommit=autocommit,
    )


def wait_database_endpoint(
    value, *, database: str = DATABASE, port: int = DATABASE_PORT, root: Path = RUN
):
    """Probe the authenticated TCP endpoint migrations actually use, not initdb's socket."""
    import psycopg

    deadline = time.monotonic() + 105  # 30 * (3-second probe + 0.5-second wait).
    for _ in range(30):
        if deadline - time.monotonic() < 4.5:
            break  # Leave room for the bounded connect, query and retry delay.
        try:
            with connect_admin(value, dbname=database, port=port, root=root) as conn:
                conn.execute("SET LOCAL statement_timeout=1000")
                if conn.execute("SELECT current_database()").fetchone() != (database,):
                    raise Refused("database endpoint identity differs; owned resources preserved")
            return
        except (psycopg.OperationalError, psycopg.InterfaceError):
            time.sleep(0.5)
    raise Refused("database TCP startup failed; owned resources preserved")


# --- Versions and the one extension (D14) -----------------------------------------------


def require_versions(conn) -> dict:
    """`server_version` 16.14 and the pinned pgvector, or nothing migrates."""
    from docsuri_ops.arrangement import runtimes

    reported = conn.execute("SHOW server_version").fetchone()[0]
    if not runtimes.server_version_matches(reported):
        raise Refused("pinned PostgreSQL version mismatch")
    row = conn.execute(
        "SELECT default_version FROM pg_available_extensions WHERE name='vector'"
    ).fetchone()
    if row is None or row[0] != runtimes.PGVECTOR.version:
        raise Refused("pinned pgvector version unavailable")
    available = tuple(
        name for (name,) in conn.execute("SELECT name FROM pg_available_extensions ORDER BY 1")
    )
    if available != tuple(sorted(runtimes.DATABASE_EXTENSIONS)):
        raise Refused("the instance offers an extension beside the one extension (D14)")
    return {
        "serverVersion": reported.split()[0],
        "pgvectorAvailable": row[0],
        "availableExtensions": list(available),
    }


def install_extension(
    value: dict, *, database: str = DATABASE, port: int = DATABASE_PORT, root: Path = RUN
) -> dict:
    """pgvector in `template1` and in the realm database, as the container's superuser,
    so every database created later already has it (security-design § 6.3)."""
    from docsuri_ops.arrangement import runtimes

    installed = {}
    for name in ("template1", database):
        with connect_admin(value, dbname=name, port=port, root=root) as conn:
            conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
            version = conn.execute(
                "SELECT extversion FROM pg_extension WHERE extname='vector'"
            ).fetchone()
            if version is None or version[0] != runtimes.PGVECTOR.version:
                raise Refused("installed pgvector version differs from the pin")
            installed[name] = version[0]
    return installed


# --- The base install -------------------------------------------------------------------


def install_base(
    conn,
    value: dict,
    credentials: dict,
    hashes: dict,
    *,
    database: str = DATABASE,
    connection_limit: int = OWNER_CONNECTION_LIMIT,
    template: bool = False,
) -> None:
    """The shared base plus every owner's schema, each owner login at CONNECTION LIMIT 4
    (U2's limit of 2 in the `u2-regression` phase's U2-identity realm). `template`: the
    realm's composed template, in the same instance, whose roles already exist and which
    no login may connect to."""
    from psycopg import sql
    from psycopg.types.json import Jsonb

    unexpected = conn.execute(
        "SELECT nspname FROM pg_namespace WHERE nspname NOT LIKE 'pg_%' "
        "AND nspname NOT IN ('public','information_schema')"
    ).fetchall()
    if unexpected:
        raise Refused("unrecognized schema; no migration attempted")
    conn.execute(sql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC").format(sql.Identifier(database)))
    conn.execute("REVOKE ALL ON SCHEMA public FROM PUBLIC")
    conn.execute(
        "CREATE TABLE public.docsuri_local_identity (singleton boolean PRIMARY KEY "
        "CHECK(singleton),run_id text NOT NULL,schema_hashes jsonb NOT NULL)"
    )
    conn.execute(
        "INSERT INTO public.docsuri_local_identity VALUES(true,%s,%s)",
        (value["runId"], Jsonb(hashes)),
    )
    for name in sorted(OWNERS):
        install_owner(
            conn, name, credentials, database=database, connection_limit=connection_limit,
            template=template,
        )
    for name in SESSION_GUARD_LOGINS:
        role = sql.Identifier(f"docsuri_{name}")
        conn.execute(sql.SQL("GRANT USAGE ON SCHEMA accounts TO {}").format(role))
        conn.execute(
            sql.SQL(
                "GRANT EXECUTE ON FUNCTION accounts.guard_session(uuid,uuid,text) TO {}"
            ).format(role)
        )
    for name in CORPUS_GUARD_LOGINS:
        role = sql.Identifier(f"docsuri_{name}")
        conn.execute(sql.SQL("GRANT USAGE ON SCHEMA corpus TO {}").format(role))
        conn.execute(
            sql.SQL("GRANT EXECUTE ON FUNCTION corpus.guard_version(text,text) TO {}").format(role)
        )
    conn.execute(
        "GRANT EXECUTE ON FUNCTION accounts.guard_execution(uuid,uuid) TO docsuri_assistance"
    )
    conn.execute(
        "GRANT SELECT ON corpus.paper,corpus.version,corpus.projection TO docsuri_discovery"
    )


def install_owner(
    conn,
    name: str,
    credentials: dict,
    *,
    database: str = DATABASE,
    connection_limit: int = OWNER_CONNECTION_LIMIT,
    template: bool = False,
) -> None:
    """One owner: a NOLOGIN schema owner, a bounded login role and the owned schema (in
    the template, the roles already exist and the login gains no CONNECT)."""
    from psycopg import sql

    owner, runtime, schema = (
        sql.Identifier(f"docsuri_{name}_owner"),
        sql.Identifier(f"docsuri_{name}"),
        sql.Identifier(name),
    )
    if not template:
        conn.execute(
            sql.SQL(
                "CREATE ROLE {} NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT "
                "NOBYPASSRLS"
            ).format(owner)
        )
        conn.execute(
            sql.SQL(
                "CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS "
                "CONNECTION LIMIT {} PASSWORD {}"
            ).format(
                runtime,
                sql.Literal(connection_limit),
                sql.Literal(credentials["roles"][name]),
            )
        )
        conn.execute(
            sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(sql.Identifier(database),
                                                                 runtime)
        )
    # pgvector's types and operators live in schema public (D14); owners use them.
    conn.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(owner))
    conn.execute(sql.SQL("CREATE SCHEMA {} AUTHORIZATION {}").format(schema, owner))
    conn.execute(sql.SQL("SET LOCAL ROLE {}").format(owner))
    conn.execute(
        sql.SQL(
            "ALTER DEFAULT PRIVILEGES IN SCHEMA {} REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC"
        ).format(schema)
    )
    if name in SCHEMAS:
        conn.execute((ROOT / SCHEMAS[name]).read_text(), prepare=False)
        conn.execute(
            sql.SQL(
                "CREATE TABLE {}.receipt (account_id uuid NOT NULL,kind text NOT NULL,"
                "key uuid NOT NULL,intent_hash text NOT NULL "
                "CHECK(intent_hash ~ '^[0-9a-f]{{64}}$'),outcome jsonb NOT NULL,"
                "created_at timestamptz NOT NULL DEFAULT clock_timestamp(),"
                "PRIMARY KEY(account_id,kind,key))"
            ).format(schema)
        )
        for statement in (
            "GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA {} TO {}",
            "REVOKE UPDATE,DELETE ON {}.receipt FROM {}",
            "GRANT USAGE,SELECT ON ALL SEQUENCES IN SCHEMA {} TO {}",
            "GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA {} TO {}",
        ):
            conn.execute(sql.SQL(statement).format(schema, runtime))
    conn.execute(sql.SQL("GRANT USAGE ON SCHEMA {} TO {}").format(schema, runtime))
    conn.execute("RESET ROLE")
    conn.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(runtime))
    conn.execute(sql.SQL("GRANT SELECT ON public.docsuri_local_identity TO {}").format(runtime))


def owner_credentials(value: dict) -> dict:
    target = RUN / "owner-credentials.json"
    if target.exists():
        credentials = json.loads(private_bytes(target))
        if (
            credentials.get("runId") != value["runId"]
            or set(credentials.get("roles", {})) != OWNERS
        ):
            raise Refused("owner credential identity mismatch")
        return credentials
    credentials = {
        "runId": value["runId"],
        "roles": {name: secrets.token_urlsafe(32) for name in sorted(OWNERS)},
    }
    private_json(target, credentials)
    return credentials


# --- The realm's stand-ins for production's roles ---------------------------------------


def standin_names() -> dict:
    from docsuri_ops.arrangement.paths import DATABASE_ROLES

    return {
        "disposable": DATABASE_ROLES.disposable,
        "scheduler": DATABASE_ROLES.scheduler,
        "backupAgent": DATABASE_ROLES.backup_agent,
        "operator": DATABASE_ROLES.operator,
        "restore": DATABASE_ROLES.restore,
        "operations": DATABASE_ROLES.operations,
    }


def standin_credentials(value: dict) -> dict:
    """Passwords for the stand-in logins; the operations login is the operations
    owner's own login, whose password is in `owner-credentials.json`."""
    target = RUN / "standin-credentials.json"
    logins = ("scheduler", "backupAgent", "operator", "restore")
    if target.exists():
        credentials = json.loads(private_bytes(target))
        if credentials.get("runId") != value["runId"] or set(credentials.get("roles", {})) != set(
            logins
        ):
            raise Refused("stand-in credential identity mismatch")
        return credentials
    credentials = {
        "runId": value["runId"],
        "roles": {name: secrets.token_urlsafe(32) for name in logins},
    }
    private_json(target, credentials)
    return credentials


def role_exists(conn, name: str) -> bool:
    return conn.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (name,)).fetchone() is not None


def install_standins(conn, credentials: dict) -> dict:
    """The disposable-databases role, the scheduler's login (a member of it only), the
    backup agent's login, the operator tool's login, the restore login (the owner-role
    memberships a restore needs) and the operations login in `pg_monitor`.
    Idempotent: a missing role is created; every role's attributes and memberships are
    asserted again on each run, and an existing password is never changed."""
    from psycopg import sql

    names = standin_names()
    passwords = credentials["roles"]
    created = []

    def create(role: str, clause: str, password: str | None = None) -> None:
        if role_exists(conn, role):
            conn.execute(sql.SQL("ALTER ROLE {} " + clause).format(sql.Identifier(role)))
            return
        statement = sql.SQL("CREATE ROLE {} " + clause).format(sql.Identifier(role))
        if password is not None:
            statement += sql.SQL(" PASSWORD {}").format(sql.Literal(password))
        conn.execute(statement)
        created.append(role)

    # Only the disposable-databases role may create a database, so a database exists
    # under that role exactly when a login created it while acting as that role.
    create(
        names["disposable"],
        "NOLOGIN NOSUPERUSER CREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS",
    )
    create(
        names["scheduler"],
        "LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE INHERIT NOBYPASSRLS CONNECTION LIMIT 3",
        passwords["scheduler"],
    )
    create(
        names["backupAgent"],
        "LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE INHERIT NOBYPASSRLS CONNECTION LIMIT 3",
        passwords["backupAgent"],
    )
    create(
        names["operator"],
        "LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS CONNECTION LIMIT 2",
        passwords["operator"],
    )
    create(
        names["restore"],
        "LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE INHERIT NOBYPASSRLS CONNECTION LIMIT 3",
        passwords["restore"],
    )
    identifier = sql.Identifier
    # The scheduler drops disposable databases through the role's inherited ownership
    # (BR9.17) and cannot act as the role, so it creates none.
    conn.execute(
        sql.SQL("GRANT {} TO {} WITH INHERIT TRUE, SET FALSE").format(
            identifier(names["disposable"]), identifier(names["scheduler"])
        )
    )
    # Step 6 test 7 and the person's decision of 2026-10-22: the agent's login reads the
    # realm's database and the rehearsal-pattern databases, which it backs up
    # (`pg_read_all_data` and CONNECT; Step 25's dump login), and writes or drops none
    # of them. It has no CREATEDB of its own and holds the disposable-databases role
    # with SET but without INHERIT, so it creates a database only while acting as that
    # role, which then owns it, and its own privileges never include that ownership.
    # PlatformControl's store grants it no CONNECT. PostgreSQL cannot limit the names a
    # login creates, nor refuse an explicit SET ROLE to a role it may create as; the
    # agent's fixed command refuses any non-scratch name (Step 26).
    conn.execute(
        sql.SQL("GRANT {} TO {} WITH INHERIT FALSE, SET TRUE").format(
            identifier(names["disposable"]), identifier(names["backupAgent"])
        )
    )
    conn.execute(
        sql.SQL("GRANT pg_read_all_data TO {} WITH INHERIT TRUE, SET FALSE").format(
            identifier(names["backupAgent"])
        )
    )
    for owner in sorted(OWNERS):
        conn.execute(
            sql.SQL("GRANT {} TO {}").format(
                identifier(f"docsuri_{owner}_owner"), identifier(names["restore"])
            )
        )
    conn.execute(sql.SQL("GRANT pg_monitor TO {}").format(identifier(names["operations"])))
    for role in (names["restore"], names["operator"], names["backupAgent"]):
        conn.execute(
            sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                identifier(DATABASE), identifier(role)
            )
        )
    return {"created": created, "roles": names}


# --- PlatformControl's store ------------------------------------------------------------


# The store's roles with a password: U7's two, then the three logins bound to their
# actors (your decision of 2026-10-26, "Bind each login to its actor").
PLATFORM_PASSWORD_ROLES = ("runtime", "provisioner", "operator", "scheduler", "reader")


def platform_credentials(value: dict) -> dict:
    target = RUN / "platform-credentials.json"
    if target.exists():
        credentials = json.loads(private_bytes(target))
        held = set(credentials.get("roles", {}))
        if credentials.get("runId") != value["runId"] or not (
                {"runtime", "provisioner"} <= held <= set(PLATFORM_PASSWORD_ROLES)):
            raise Refused("platform credential identity mismatch")
        if held == set(PLATFORM_PASSWORD_ROLES):
            return credentials
        # A realm set up before the logins were bound gains them once.
        credentials = {"runId": value["runId"], "roles": {
            **{name: secrets.token_urlsafe(32) for name in PLATFORM_PASSWORD_ROLES},
            **credentials["roles"]}}
        private_json(target, credentials)
        return credentials
    credentials = {
        "runId": value["runId"],
        "roles": {name: secrets.token_urlsafe(32) for name in PLATFORM_PASSWORD_ROLES},
    }
    private_json(target, credentials)
    return credentials


def ensure_platform_logins(conn, credentials: dict) -> None:
    """The reader role and the realm's three store logins, as production's installer
    makes them: the operator's and the scheduler's are members of U7's runtime role,
    the reader's only of the reader role, which holds the read functions alone. Each has
    `CONNECTION LIMIT 2`, the limit production's installation script gives its three
    store logins (Step 51(g), L1-67). Run as the administrator before the amendment, each
    time; a login keeps its password, and an existing login keeps its limit."""
    from psycopg import sql

    from docsuri_ops.platform_control import RUNTIME_ROLE
    from docsuri_ops.u8_platform.platform_profile import READER_ROLE, store_logins

    def exists(role: str) -> bool:
        row = conn.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (role,)).fetchone()
        return row is not None

    if not exists(READER_ROLE):
        conn.execute(sql.SQL("CREATE ROLE {} NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE "
                             "NOINHERIT NOBYPASSRLS").format(sql.Identifier(READER_ROLE)))
    for kind, login in store_logins("realm").items():
        if not exists(login):
            conn.execute(sql.SQL(
                "CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE INHERIT NOBYPASSRLS "
                "CONNECTION LIMIT 2 PASSWORD {}").format(
                    sql.Identifier(login), sql.Literal(credentials["roles"][kind])))
        group = READER_ROLE if kind == "reader" else RUNTIME_ROLE
        conn.execute(sql.SQL("GRANT {} TO {} WITH INHERIT TRUE, SET FALSE").format(
            sql.Identifier(group), sql.Identifier(login)))
        conn.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
            sql.Identifier(PLATFORM_DATABASE), sql.Identifier(login)))


def protocol_rows() -> list[tuple]:
    """Every protocol row of inventory version 2: U7's `protocols`, unchanged, and A6's
    `u8Protocols` (U8 plan Step 27), in the protocol table's column order."""
    from docsuri_ops.platform_control.inventory import load_inventory
    from docsuri_ops.u8_platform.u8_protocols import load_revision

    rows = []
    for protocol in load_inventory().protocols:
        row = protocol.as_row()
        rows.append((row["name"], row["disposition"], row["authority_class"],
                     row["max_age_seconds"], row["deadline_seconds"], row["effect_kind"],
                     row["native_verified"], row["consumer_impact"]))
    raw = json.loads((ROOT / "ops/src/docsuri_ops/platform_control/inventory.json").read_text())
    impacts = {item["name"]: item["consumerImpact"] for item in raw["u8Protocols"]}
    for protocol in load_revision().u8:
        rows.append((protocol.name, "retained-local", protocol.authority_class,
                     protocol.max_age_seconds, protocol.deadline_seconds, protocol.effect_kind,
                     True, impacts[protocol.name]))
    return rows


def seed_protocols(conn) -> list[str]:
    """Insert each missing protocol row; an existing row that differs refuses, so U7's
    eight rows and every receipt stay as they are (additive only)."""
    added = []
    for row in protocol_rows():
        existing = conn.execute(
            "SELECT name, disposition, authority_class, max_age_seconds, deadline_seconds, "
            "effect_kind, native_verified, consumer_impact FROM platform_control.protocol "
            "WHERE name=%s", (row[0],),
        ).fetchone()
        if existing is None:
            conn.execute(
                "INSERT INTO platform_control.protocol (name, disposition, authority_class, "
                "max_age_seconds, deadline_seconds, effect_kind, native_verified, consumer_impact) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)", row,
            )
            added.append(row[0])
        elif tuple(existing) != row:
            raise Refused(f"platform protocol {row[0]} differs from the inventory")
    return added


def install_platform_store(value: dict) -> dict:
    """`docsuri_u8_platform` with U7's PlatformControl schema, as
    `scripts/bootstrap_docsuri_u7.py` installs it; each login at CONNECTION LIMIT 2.
    U8's additive amendment (`platform_profile.STORE_AMENDMENT`) follows U7's schema. The
    store records `platform_profile.store_digest` (the inventory and the amendment
    together; the person's decision of 2026-10-25, "After the move, same build"), and an
    existing store whose digest differs is migrated: the amendment again, then each
    missing protocol row (U8 plan Step 27). A store whose digest matches is verified and
    left as it is."""
    from psycopg import sql

    from docsuri_ops.platform_control import OWNER_ROLE, PROVISIONER_ROLE, RUNTIME_ROLE
    from docsuri_ops.u8_platform.platform_profile import STORE_AMENDMENT, store_digest

    digest = store_digest(ROOT)
    amendment = (ROOT / STORE_AMENDMENT).read_text()
    with connect_admin(value, autocommit=True) as conn:
        exists = conn.execute(
            "SELECT 1 FROM pg_database WHERE datname=%s", (PLATFORM_DATABASE,)
        ).fetchone()
        if exists is None:
            conn.execute(
                sql.SQL("CREATE DATABASE {} ENCODING 'UTF8' LOCALE 'C' TEMPLATE template1").format(
                    sql.Identifier(PLATFORM_DATABASE)
                )
            )
    credentials = platform_credentials(value)
    with connect_admin(value, dbname=PLATFORM_DATABASE) as conn:
        row = conn.execute("SELECT to_regclass('public.docsuri_u8_platform_identity')").fetchone()
        if row[0] is not None:
            identity = conn.execute(
                "SELECT run_id,inventory_hash FROM public.docsuri_u8_platform_identity"
            ).fetchone()
            if identity is None or identity[0] != value["runId"]:
                raise Refused("platform store identity mismatch; adoption refused")
            if identity[1] == digest:
                return {"state": "verified", "storeDigest": digest}
            ensure_platform_logins(conn, credentials)
            conn.execute(sql.SQL("SET LOCAL ROLE {}").format(sql.Identifier(OWNER_ROLE)))
            conn.execute(amendment, prepare=False)
            added = seed_protocols(conn)
            conn.execute("RESET ROLE")
            conn.execute(
                "UPDATE public.docsuri_u8_platform_identity SET inventory_hash=%s WHERE singleton",
                (digest,),
            )
            return {"state": "migrated", "storeDigest": digest, "added": added}
        conn.execute(
            sql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC").format(
                sql.Identifier(PLATFORM_DATABASE)
            )
        )
        conn.execute("REVOKE ALL ON SCHEMA public FROM PUBLIC")
        conn.execute(
            "CREATE TABLE public.docsuri_u8_platform_identity (singleton boolean PRIMARY KEY "
            "CHECK(singleton), run_id text NOT NULL, inventory_hash text NOT NULL)"
        )
        for role, password in (
            (OWNER_ROLE, None),
            (RUNTIME_ROLE, credentials["roles"]["runtime"]),
            (PROVISIONER_ROLE, credentials["roles"]["provisioner"]),
        ):
            statement = sql.SQL(
                "CREATE ROLE {} {} NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS"
            ).format(sql.Identifier(role), sql.SQL("NOLOGIN" if password is None else "LOGIN"))
            if password is not None:
                statement += sql.SQL(" CONNECTION LIMIT 2 PASSWORD {}").format(
                    sql.Literal(password)
                )
            conn.execute(statement)
            conn.execute(
                sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                    sql.Identifier(PLATFORM_DATABASE), sql.Identifier(role)
                )
            )
        conn.execute(
            sql.SQL("CREATE SCHEMA platform_control AUTHORIZATION {}").format(
                sql.Identifier(OWNER_ROLE)
            )
        )
        ensure_platform_logins(conn, credentials)
        conn.execute(sql.SQL("SET LOCAL ROLE {}").format(sql.Identifier(OWNER_ROLE)))
        conn.execute(
            (ROOT / "ops/src/docsuri_ops/platform_control/schema.sql").read_text(),
            prepare=False,
        )
        conn.execute(amendment, prepare=False)
        seed_protocols(conn)
        conn.execute("RESET ROLE")
        conn.execute(
            "INSERT INTO public.docsuri_u8_platform_identity(singleton, run_id, inventory_hash) "
            "VALUES (true, %s, %s)",
            (value["runId"], digest),
        )
    return {"state": "installed", "storeDigest": digest}


# --- The realm's platform (U8 plan Step 27) ------------------------------------------------

REALM_SCHEDULER_UID, REALM_OPERATOR_UID, REALM_SERVICE_UID = 711, 712, 710
# The realm's stand-in volume folder shares this Mac's disk and holds a few hundred
# megabytes; production's volume keeps its 64 GiB floor, which its config cannot change.
REALM_SPACE_FLOOR_BYTES = 1024**3
AUTHORITIES_FILE = "platform-authorities.json"
AGENT_FOLDER, VOLUME_FOLDER = "backup-agent", "backup-volume"


def realm_actors(value: dict) -> dict:
    from docsuri_ops.u8_platform.in_person import realm_actor

    return {"operator": realm_actor(RUN), "scheduler": f"realm-scheduler:{value['runId']}",
            "service": f"realm-service:{value['runId']}"}


def realm_targets() -> list[str]:
    from docsuri_ops.u8_platform.platform_profile import REALM_LABELS
    from docsuri_ops.u8_platform.u8_protocols import load_revision

    targets = {target for protocol in load_revision().u8 for target in protocol.targets}
    return sorted(targets | set(REALM_LABELS) | {"backup-volume"})


def realm_grants(actors: dict) -> dict:
    """The realm's authorities: the operator's routine and destructive grants, the
    scheduler's three standing grants (`SCHEDULER_GRANTS`: its routine set, the restore
    grant `schedulerRestore` for a scratch database's restore alone, and the disposal
    pass's database removal) and the service account's evidence reader."""
    from docsuri_ops.u8_platform.u8_protocols import (
        SCHEDULER_GRANTS,
        load_revision,
    )

    revision = load_revision().u8
    every = realm_targets()

    def names(authority_class: str) -> list[str]:
        return [p.name for p in revision if p.authority_class == authority_class]

    grants = {
        "operatorRoutine": (actors["operator"], every, names("routine"), "routine"),
        "operatorDestructive": (actors["operator"], every, names("destructive-release"),
                                "destructive-release"),
        "serviceReader": (actors["service"], every, ["inspectEvidence", "readReceipt"],
                          "evidence-reader"),
    }
    for name, (scope, operations, authority_class) in SCHEDULER_GRANTS.items():
        grants[name] = (actors["scheduler"], list(scope), list(operations), authority_class)
    return grants


def provision_realm_store(value: dict) -> dict:
    """Targets and authorities in the realm's store, once; then the service account's
    reader binding (`platform-reader.json`)."""
    from docsuri_ops.platform_control import PROVISIONER_ROLE
    from docsuri_ops.u8_platform.platform_profile import U8PlatformProfile, store_logins
    from docsuri_ops.u8_platform.u8_protocols import bind_store_logins, grant_drift

    profile = U8PlatformProfile.realm(RUN)
    store = profile.store(PROVISIONER_ROLE, profile.realm_password("provisioner"))
    for target in realm_targets():
        store.provision_target(target)
    actors = realm_actors(value)
    path = RUN / AUTHORITIES_FILE
    authorities: dict[str, str] = {}
    if path.exists():
        recorded = json.loads(private_bytes(path))
        if recorded.get("runId") != value["runId"]:
            raise Refused("platform authorities belong to another realm")
        authorities = dict(recorded["authorities"])
    # Each grant once; a grant a later plan step adds is provisioned on the next migrate.
    missing = {name: grant for name, grant in realm_grants(actors).items()
               if name not in authorities}
    for name, (actor, scope, operations, authority_class) in missing.items():
        authority = str(uuid.uuid4())
        store.provision_authority(authority_id=authority, actor=actor, scope=scope,
                                  operations=operations, authority_class=authority_class,
                                  binding={"realm": value["runId"], "grant": name})
        authorities[name] = authority
    if missing or not path.exists():
        private_json(path, {"runId": value["runId"], "actors": actors,
                            "authorities": authorities})
    bind_store_logins(store, store_logins("realm"), actors)
    # The scheduler's grants the store holds must be exactly `SCHEDULER_GRANTS` (review
    # finding, Minor, R15): a realm provisioned before a grant changed is refused here,
    # never reported verified; archive it and set up a fresh one.
    drift = grant_drift(store, authorities, actors["scheduler"])
    if drift:
        raise Refused(f"platform-grant-drift: {', '.join(drift)} differ from "
                      "SCHEDULER_GRANTS; archive this realm and set up a fresh one")
    private_json(RUN / "platform-reader.json", {
        "authorityId": authorities["serviceReader"], "actor": actors["service"],
    })
    return {"targets": len(realm_targets()), "authorities": sorted(authorities)}


def private_folder(path: Path) -> None:
    if not path.exists():
        os.mkdir(path, 0o700)
    require_private_directory(path, f"{path.name} must be a private folder")


def install_realm_platform(value: dict, standins: dict) -> dict:
    """The realm driver's configuration, the realm's platform profile, the stand-in
    backup volume and the backup agent's own folder (Steps 25 and 27)."""
    from docsuri_ops.backup_agent.config import AgentConfig, Login
    from docsuri_ops.backup_agent.config import write as write_agent
    from docsuri_ops.backup_agent.disposal import prepare_volume

    state = RUN / "platform"
    private_folder(state)
    private_folder(state / "effects")
    import datetime as dt

    private_json(state / "effects" / "driver.json", {
        "kind": "realm", "runRoot": str(RUN), "stateRoot": str(state), "runId": value["runId"],
        "databasePort": DATABASE_PORT, "agentFolder": str(RUN / AGENT_FOLDER),
        "schedulerUid": REALM_SCHEDULER_UID, "operatorUid": REALM_OPERATOR_UID,
        "repository": str(ROOT),
    }, root=state / "effects")
    if not (state / "profile.json").exists():
        private_json(state / "profile.json", {
            "mode": "live", "admission": "open", "rehearsalDatabase": None,
            "backupVolume": {"identity": f"standin-{value['runId']}"},
        }, root=state)
    volume = RUN / VOLUME_FOLDER
    private_folder(volume)
    prepare_volume(volume, clock=lambda: dt.datetime.now(dt.UTC))
    agent = RUN / AGENT_FOLDER
    private_folder(agent)
    if not (agent / "v2-login").exists():
        descriptor = os.open(agent / "v2-login", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w") as stream:
            stream.write(standins["roles"]["backupAgent"])
    native = value.get("databaseKind") == "native"
    write_agent(agent, AgentConfig(
        kind="realm", mount=volume, volume_identity=f"standin-{value['runId']}",
        database_prefix=DATABASE,
        v2_login=Login("127.0.0.1", DATABASE_PORT, "docsuri_backup_agent", "v2-login"),
        scheduler_uid=REALM_SCHEDULER_UID, operator_uid=REALM_OPERATOR_UID,
        service_uid=REALM_SERVICE_UID, container=None if native else value["container"],
        space_floor_bytes=REALM_SPACE_FLOOR_BYTES, native=native,
    ))
    return {"platform": str(state), "volume": str(volume), "agent": str(agent),
            "store": provision_realm_store(value)}


# --- The composed chain -----------------------------------------------------------------


def chain() -> tuple[tuple[tuple[str, str], ...], dict[str, str]]:
    """The composed chain after the base install, and its REPLACED map. U8's copy of U1's
    base and amendments must equal U1's own lists, or nothing migrates."""
    from backend import u8_migrations
    from bootstrap_docsuri_u1 import AMENDMENTS

    if dict(u8_migrations.BASE) != SCHEMAS or u8_migrations.U1_AMENDMENTS != AMENDMENTS:
        raise Refused("composed chain's U1 base differs from U1's own lists")
    return u8_migrations.migrations(), dict(u8_migrations.REPLACED)


def grant_capacity_observation(conn, database: str = DATABASE) -> None:
    """The non-login operations schema owner's CONNECT and pg_ls_waldir(), which the
    capacity definer functions need; no runtime login gains a privilege."""
    from psycopg import sql

    conn.execute(
        sql.SQL("GRANT CONNECT ON DATABASE {} TO docsuri_operations_owner").format(
            sql.Identifier(database)
        )
    )
    conn.execute("GRANT EXECUTE ON FUNCTION pg_catalog.pg_ls_waldir() TO docsuri_operations_owner")


def validate_chain(files: tuple[tuple[str, str], ...], replaced: dict, known: dict) -> None:
    """Before any change: refuse a chain that lists a file twice, still lists a left-out
    file, names an owner outside the realm, or holds a file whose digest differs from
    one already applied (append-only by digest)."""
    names = [file for _, file in files]
    if len(names) != len(set(names)):
        raise Refused("composed chain lists a file twice")
    if set(names) & set(replaced):
        raise Refused("composed chain still lists a left-out file")
    if any(reconciling not in names for reconciling in replaced.values()):
        raise Refused("composed chain lacks a reconciling file it declares")
    if any(owner not in OWNERS for owner, _ in files):
        raise Refused("composed chain names an owner outside the realm")
    if set(replaced) & set(known):
        raise Refused("realm holds a file the composed chain leaves out; set up a fresh realm")
    applied = [file in known for file in names]
    if any(later and not earlier for earlier, later in itertools.pairwise(applied)):
        raise Refused("applied files are not a prefix of the composed chain; set up a fresh realm")
    for _, file in files:
        if file in known and known[file] != digest(ROOT / file):
            raise Refused("applied migration changed; append a new migration")


def apply_migrations(conn, known: dict, *, database: str = DATABASE) -> list[str]:
    """Append-only: an applied file whose bytes changed refuses; new files apply once,
    each under its owner's role."""
    from psycopg import sql

    from backend.u8_migrations import CAPACITY_FILES

    files, replaced = chain()
    validate_chain(files, replaced, known)
    applied = []
    for owner, file in files:
        current = digest(ROOT / file)
        if file in known:
            continue
        if file in CAPACITY_FILES:
            grant_capacity_observation(conn, database)
        conn.execute(sql.SQL("SET LOCAL ROLE {}").format(sql.Identifier(f"docsuri_{owner}_owner")))
        conn.execute((ROOT / file).read_text(), prepare=False)
        conn.execute("RESET ROLE")
        known[file] = current
        applied.append(file)
    return applied


TEMPLATE_DATABASE = "docsuri_u8_template"


def maintain_template(value: dict, credentials: dict, hashes: dict) -> dict:
    """The realm's composed template: the same base install and the same composed chain
    as `docsuri_u8`, in a private database no login may connect to and no test writes,
    so it holds exactly what the chain creates and seeds. The realm's rehearsal and
    production stand-ins are copied from it (`docsuri_ops.migration.realm`), as
    production's databases get the chain itself (U8 plan Step 31)."""
    from psycopg import sql
    from psycopg.types.json import Jsonb

    with connect_admin(value, autocommit=True) as conn:
        if conn.execute("SELECT 1 FROM pg_database WHERE datname=%s",
                        (TEMPLATE_DATABASE,)).fetchone() is None:
            conn.execute(sql.SQL("CREATE DATABASE {} TEMPLATE template1").format(
                sql.Identifier(TEMPLATE_DATABASE)))
            conn.execute(sql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC").format(
                sql.Identifier(TEMPLATE_DATABASE)))
    with connect_admin(value, dbname=TEMPLATE_DATABASE) as conn:
        if not conn.execute("SELECT to_regclass('public.docsuri_local_identity')").fetchone()[0]:
            install_base(conn, value, credentials, hashes, database=TEMPLATE_DATABASE,
                         template=True)
        known = amend(conn, value, hashes)
        applied = apply_migrations(conn, known, database=TEMPLATE_DATABASE)
        # L1-82 ("Stop the grant"): the chain needs the operations owner's CONNECT while it
        # applies a capacity file, because U2's u2_capacity_database.sql runs
        # pg_database_size(current_database()) as that owner; take it back in this same
        # transaction, so the template keeps no CONNECT once the chain has applied.
        conn.execute(sql.SQL("REVOKE CONNECT ON DATABASE {} FROM docsuri_operations_owner").format(
            sql.Identifier(TEMPLATE_DATABASE)))
        conn.execute("UPDATE public.docsuri_local_identity SET schema_hashes=%s WHERE singleton",
                     (Jsonb(known),))
    return {"database": TEMPLATE_DATABASE, "appliedNow": len(applied),
            "migrationCount": len(known)}


def migrate(path: Path, *, base_only: bool = False) -> dict:
    from psycopg.types.json import Jsonb

    _, value = manifest(path)
    require_resources(value)
    require_key_folders()
    require_stopped()
    credentials = owner_credentials(value)
    standins = standin_credentials(value)
    hashes = {name: digest(ROOT / file) for name, file in SCHEMAS.items()}
    with connect_admin(value) as conn:
        versions = require_versions(conn)
    extension = install_extension(value)
    applied: list[str] = []
    with connect_admin(value) as conn:
        if not conn.execute("SELECT to_regclass('public.docsuri_local_identity')").fetchone()[0]:
            install_base(conn, value, credentials, hashes)
        known = amend(conn, value, hashes)
        roles = install_standins(conn, standins)
        if not base_only:
            applied = apply_migrations(conn, known)
            conn.execute(
                "UPDATE public.docsuri_local_identity SET schema_hashes=%s WHERE singleton",
                (Jsonb(known),),
            )
    template = None if base_only else maintain_template(value, credentials, hashes)
    platform = install_platform_store(value)
    platform["realm"] = install_realm_platform(value, standins)
    if not base_only:
        from backend.local_profile import key_folder
        from backend.modules.accounts.services.guarded_entry import GuardedEntryService
        from backend.modules.accounts.u8_verifier_key import ensure_key_file
        from backend.transactions import OwnerTransactions
        from backend.u8_host import CURSOR_KEY, accounts_exist
        from docsuri_ops.local_transport import prepare_transport

        profile = LocalProfile.load(path)
        transactions = OwnerTransactions(profile)
        try:
            GuardedEntryService(transactions)
            # L1-4 (your decision of 2026-11-01, "Use its key folder"): the search cursor
            # key in its own folder, created only while no account exists; with any
            # account present a missing key is never created here.
            if not accounts_exist(transactions):
                ensure_key_file(key_folder(profile, "cursor-key") / CURSOR_KEY)
        finally:
            transactions.close()
        prepare_transport(LocalProfile.load(path))
    return {
        "state": "base-verified" if base_only else "u8-migrated",
        "versions": versions,
        "extension": extension,
        "standins": roles,
        "platform": platform,
        "migrationCount": len(known),
        "appliedNow": applied,
        "template": template,
    }


# --- The realm's privilege inventory (L1-50) --------------------------------------------
#
# L1-50: every realm login's privileges equal a pinned inventory. The pin holds for the
# realm only: nothing in `backend/` or `ops/` reads it, and production's installer gives
# its roles other attributes. Any change that moves a row (a new table, sequence,
# function or column in an owner schema or the store; a grant in the chain or in
# `u8_store.sql`; a change to `install_owner`, `install_standins`,
# `grant_capacity_observation`, `install_platform_store` or `ensure_platform_logins`)
# takes the file and the digest again in the same step, on a fresh realm after `setup`
# and `migrate`.

REALM_PRIVILEGES = "scripts/u8_realm_privileges.txt"
REALM_PRIVILEGES_SHA256 = "e51272c701c15ba0b176b5217b158e9adf3eb0a4de55b5b464e98f3bc4554351"
COVERED_PREFIXES = ("docsuri_", "platform_control_")
PLATFORM_SCHEMAS = ("platform_control", "public")
PRIVILEGE_DATABASES = (DATABASE, TEMPLATE_DATABASE, PLATFORM_DATABASE)
ROLE_ATTRIBUTES = ("rolsuper", "rolinherit", "rolcreaterole", "rolcreatedb", "rolcanlogin",
                   "rolreplication", "rolbypassrls")

_RELATION_KIND = (
    "CASE c.relkind WHEN 'S' THEN 'sequence' WHEN 'v' THEN 'view' "
    "WHEN 'm' THEN 'materialized-view' WHEN 'f' THEN 'foreign-table' ELSE 'table' END"
)
_EXTENSION_OWNED = (
    "EXISTS (SELECT 1 FROM pg_depend d WHERE d.classid={catalog}::regclass "
    "AND d.objid={oid} AND d.deptype='e')"
)
_LISTED_RELATION = (
    "(n.nspname = ANY(%(schemas)s) AND c.relkind IN ('r','p','v','m','S','f') AND NOT "
    + _EXTENSION_OWNED.format(catalog="'pg_class'", oid="c.oid") + ")"
)
_LISTED_FUNCTION = (
    "(n.nspname = ANY(%(schemas)s) AND NOT "
    + _EXTENSION_OWNED.format(catalog="'pg_proc'", oid="p.oid") + ")"
)
_EXPLODED = (
    "SELECT o.kind, o.name, CASE WHEN a.grantee = 0 THEN 'PUBLIC' "
    "ELSE pg_get_userbyid(a.grantee)::text END, a.privilege_type, a.is_grantable "
    "FROM objects o CROSS JOIN LATERAL aclexplode(o.acl) a"
)
# The listed schemas and every relation, sequence, column and function in them that no
# extension owns; a NULL ACL is read as `acldefault` for its kind and owner.
_LISTED_ACLS = (
    "WITH objects(kind, name, acl) AS ("
    " SELECT 'schema', n.nspname::text, coalesce(n.nspacl, acldefault('n', n.nspowner))"
    "   FROM pg_namespace n WHERE n.nspname = ANY(%(schemas)s)"
    " UNION ALL"
    f" SELECT {_RELATION_KIND}, n.nspname || '.' || c.relname,"
    "   coalesce(c.relacl, acldefault(CASE WHEN c.relkind = 'S' THEN 's' ELSE 'r' END::\"char\","
    "   c.relowner))"
    "   FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace"
    f"  WHERE {_LISTED_RELATION}"
    " UNION ALL"
    " SELECT 'column', n.nspname || '.' || c.relname || '.' || a.attname,"
    "   coalesce(a.attacl, acldefault('c', c.relowner))"
    "   FROM pg_attribute a JOIN pg_class c ON c.oid = a.attrelid"
    "   JOIN pg_namespace n ON n.oid = c.relnamespace"
    f"  WHERE a.attnum > 0 AND NOT a.attisdropped AND {_LISTED_RELATION}"
    " UNION ALL"
    " SELECT 'function', n.nspname || '.' || p.proname || '('"
    "   || pg_get_function_identity_arguments(p.oid) || ')',"
    "   coalesce(p.proacl, acldefault('f', p.proowner))"
    "   FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace"
    f"  WHERE {_LISTED_FUNCTION}"
    f") {_EXPLODED}"
)
# Every other object of the database with an explicit ACL; only those whose ACL names a
# covered role (never just PUBLIC) count (today `pg_catalog.pg_ls_waldir()`).
_OTHER_ACLS = (
    "WITH objects(kind, name, acl) AS ("
    " SELECT 'schema', n.nspname::text, n.nspacl FROM pg_namespace n"
    "  WHERE n.nspacl IS NOT NULL AND NOT n.nspname = ANY(%(schemas)s)"
    " UNION ALL"
    f" SELECT {_RELATION_KIND}, n.nspname || '.' || c.relname, c.relacl"
    "   FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace"
    f"  WHERE c.relacl IS NOT NULL AND NOT {_LISTED_RELATION}"
    " UNION ALL"
    " SELECT 'column', n.nspname || '.' || c.relname || '.' || a.attname, a.attacl"
    "   FROM pg_attribute a JOIN pg_class c ON c.oid = a.attrelid"
    "   JOIN pg_namespace n ON n.oid = c.relnamespace"
    f"  WHERE a.attacl IS NOT NULL AND NOT {_LISTED_RELATION}"
    " UNION ALL"
    " SELECT 'function', n.nspname || '.' || p.proname || '('"
    "   || pg_get_function_identity_arguments(p.oid) || ')', p.proacl"
    "   FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace"
    f"  WHERE p.proacl IS NOT NULL AND NOT {_LISTED_FUNCTION}"
    " UNION ALL"
    " SELECT 'type', format_type(t.oid, NULL), t.typacl FROM pg_type t"
    "  WHERE t.typacl IS NOT NULL"
    " UNION ALL"
    " SELECT 'language', l.lanname::text, l.lanacl FROM pg_language l"
    "  WHERE l.lanacl IS NOT NULL"
    " UNION ALL"
    " SELECT 'foreign-data-wrapper', w.fdwname::text, w.fdwacl FROM pg_foreign_data_wrapper w"
    "  WHERE w.fdwacl IS NOT NULL"
    " UNION ALL"
    " SELECT 'foreign-server', s.srvname::text, s.srvacl FROM pg_foreign_server s"
    "  WHERE s.srvacl IS NOT NULL"
    f") {_EXPLODED}"
)
_DEFAULT_ACLS = (
    "SELECT pg_get_userbyid(d.defaclrole)::text,"
    " CASE WHEN d.defaclnamespace = 0 THEN '*' ELSE d.defaclnamespace::regnamespace::text END,"
    " d.defaclobjtype::text, CASE WHEN a.grantee = 0 THEN 'PUBLIC'"
    " ELSE pg_get_userbyid(a.grantee)::text END, a.privilege_type, a.is_grantable"
    " FROM pg_default_acl d LEFT JOIN LATERAL aclexplode(d.defaclacl) a ON true"
)
# The shared catalogues, read once: the three databases' ACLs, and every other shared
# object whose ACL names a covered role.
_SHARED_ACLS = (
    "WITH objects(kind, name, acl) AS ("
    " SELECT 'database', d.datname::text, coalesce(d.datacl, acldefault('d', d.datdba))"
    "   FROM pg_database d WHERE d.datname = ANY(%(databases)s)"
    " UNION ALL"
    " SELECT 'tablespace', t.spcname::text, t.spcacl FROM pg_tablespace t"
    "  WHERE t.spcacl IS NOT NULL"
    " UNION ALL"
    " SELECT 'parameter', p.parname, p.paracl FROM pg_parameter_acl p"
    "  WHERE p.paracl IS NOT NULL"
    f") {_EXPLODED}"
)
_MEMBERSHIPS = (
    "SELECT r.rolname::text, m.rolname::text, am.admin_option, am.inherit_option,"
    " am.set_option FROM pg_auth_members am JOIN pg_roles r ON r.oid = am.roleid"
    " JOIN pg_roles m ON m.oid = am.member"
)


def covered_role(name: str) -> bool:
    """PUBLIC and every role whose name starts with `docsuri_` or `platform_control_`."""
    return name == "PUBLIC" or name.startswith(COVERED_PREFIXES)


def _flag(value: bool) -> str:
    return "t" if value else "f"


def _privilege(privilege: str, grantable: bool) -> str:
    return privilege + (" WITH GRANT OPTION" if grantable else "")


def _rows(conn, statement: str, params: dict | None = None) -> list[tuple]:
    from psycopg.rows import tuple_row

    return conn.cursor(row_factory=tuple_row).execute(statement, params).fetchall()


def _object_rows(conn, schemas: tuple[str, ...]) -> set[str]:
    """One database's object privileges: the listed objects' covered entries, and the
    covered entries of every other object whose ACL names a covered role explicitly."""
    database = _rows(conn, "SELECT current_database()::text")[0][0]
    params = {"schemas": list(schemas)}
    rows = {
        f"{database}|{kind}|{name}|{grantee}|{_privilege(privilege, grantable)}"
        for kind, name, grantee, privilege, grantable in _rows(conn, _LISTED_ACLS, params)
        if covered_role(grantee)
    }
    others = _rows(conn, _OTHER_ACLS, params)
    named = {(kind, name) for kind, name, grantee, _, _ in others
             if grantee != "PUBLIC" and covered_role(grantee)}
    rows |= {
        f"{database}|{kind}|{name}|{grantee}|{_privilege(privilege, grantable)}"
        for kind, name, grantee, privilege, grantable in others
        if (kind, name) in named and covered_role(grantee)
    }
    for role, schema, kind, grantee, privilege, grantable in _rows(conn, _DEFAULT_ACLS):
        if not covered_role(role):
            continue
        entry = f"{database}|default-acl|{role}:{schema}:{kind}"
        rows.add(f"{entry}|{role}|entry")
        if grantee is not None and covered_role(grantee):
            rows.add(f"{entry}|{grantee}|{_privilege(privilege, grantable)}")
    return rows


def _cluster_rows(conn) -> set[str]:
    """The shared catalogues: the three databases' ACLs, other shared ACLs that name a
    covered role, memberships and the covered roles' attributes (`rolconnlimit` is left
    out: Step 52(c) asserts it)."""
    shared = _rows(conn, _SHARED_ACLS, {"databases": list(PRIVILEGE_DATABASES)})
    named = {(kind, name) for kind, name, grantee, _, _ in shared
             if kind == "database" or (grantee != "PUBLIC" and covered_role(grantee))}
    rows = {
        f"cluster|{kind}|{name}|{grantee}|{_privilege(privilege, grantable)}"
        for kind, name, grantee, privilege, grantable in shared
        if (kind, name) in named and covered_role(grantee)
    }
    for role, member, admin, inherit, settable in _rows(conn, _MEMBERSHIPS):
        if covered_role(role) or covered_role(member):
            rows.add(f"cluster|membership|{role}|{member}|admin={_flag(admin)},"
                     f"inherit={_flag(inherit)},set={_flag(settable)}")
    attributes = ", ".join(ROLE_ATTRIBUTES)
    for name, *flags in _rows(conn, f"SELECT rolname::text, {attributes} FROM pg_roles"):
        if covered_role(name):
            described = ",".join(f"{column.removeprefix('rol')}={_flag(flag)}"
                                 for column, flag in zip(ROLE_ATTRIBUTES, flags, strict=True))
            rows.add(f"cluster|role|{name}|{name}|{described}")
    return rows


def privilege_inventory(realm, store) -> tuple[str, ...]:
    """L1-50: the realm's privilege inventory, sorted text, one row per privilege, each
    naming the database, the object, the grantee and the privilege; objects by schema and
    name, a column with its table, a function with its identity arguments, never an OID.

    `realm` and `store` are the realm's superuser connected to `docsuri_u8` and to
    `docsuri_u8_platform`, each read inside the caller's transaction. The shared
    catalogues are read once, through `realm`."""
    rows = _object_rows(realm, (*sorted(OWNERS), "public"))
    rows |= _object_rows(store, PLATFORM_SCHEMAS)
    rows |= _cluster_rows(realm)
    return tuple(sorted(rows))


def realm_privilege_rows(path: Path) -> tuple[str, ...]:
    """The inventory of the realm the environment file names, read in one rolled-back
    transaction on each database (the command that takes the pin prints these rows)."""
    _, value = manifest(path)
    with connect_admin(value) as realm, connect_admin(value, dbname=PLATFORM_DATABASE) as store:
        try:
            return privilege_inventory(realm, store)
        finally:
            realm.rollback()
            store.rollback()


# --- Test phases ------------------------------------------------------------------------


def listed_files(*paths: str, root: Path | None = None) -> list[str]:
    """Files git tracks or would track: the `--cached --others --exclude-standard` listing,
    of this tree or, with `root`, of that checkout (`git -C <root>`; Step 95(b))."""
    location = [] if root is None else ["-C", str(root)]
    result = require(
        ["git", *location, "ls-files", "-z", "--cached", "--others", "--exclude-standard",
         "--", *paths]
    )
    return sorted(set(result.stdout.split("\0")) - {""})


def require_test_paths(paths: tuple[str, ...], *, root: Path | None = None) -> None:
    """Every test path a phase names resolves to at least one listed file, so a phase can
    never pass by naming a path a fresh checkout lacks. `root` names another checkout
    (the compatibility phase's tag worktree, the release's `--playwright` checkout)."""
    for name in paths:
        if not listed_files(name, root=root):
            raise Refused("phase test path lists no tracked or untracked-unignored file")


def source_identity(*extra_paths: str) -> dict:
    """Bind evidence to the actual listed bytes of every source the phases exercise."""
    files = {}
    for name in listed_files(
        "backend",
        "frontend",
        "shared",
        "scripts",
        "ops",
        "ingestion",
        "platform_integrity",
        TEST_ROOT,
        WORKFLOW,
        *extra_paths,
    ):
        path = ROOT / name
        if path.is_symlink():
            raise Refused("source inventory contains symlink")
        files[name] = digest(path) if path.is_file() else None
    return {
        "head": require(["git", "rev-parse", "HEAD"]).stdout.strip(),
        "sha256": hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest(),
        "files": files,
    }


def child_environment(extra: dict | None = None) -> dict:
    environment = {
        # DOCKER_HOST, when set, names the Docker the caller chose (L1-76).
        key: os.environ[key]
        for key in ("PATH", "HOME", "TMPDIR", "LANG", "DOCKER_HOST")
        if key in os.environ
    }
    environment.update(
        PYTHONPATH=str(ROOT),
        DOCSURI_U8_ENVIRONMENT_FILE=str(RUN / "environment.json"),
        CI="true",
        COREPACK_ENABLE_DOWNLOAD_PROMPT="0",
        COREPACK_ENABLE_NETWORK="0",
    )
    environment.update(extra or {})
    return environment


OBSERVATION_SECONDS = 1
SMAPS_ROLLUP = "/proc/{pid}/smaps_rollup"


def process_snapshot(deadline: float) -> list[tuple[int, int, int]]:
    """(pid, ppid, RSS KiB) of every process, from ONE `ps` snapshot."""
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise Refused("process deadline reached")
    result = subprocess.run(
        ["ps", "-Ao", "pid=,ppid=,rss="],
        capture_output=True,
        text=True,
        timeout=min(OBSERVATION_SECONDS, remaining),
        check=True,
    )
    return [
        tuple(map(int, line.split()))
        for line in result.stdout.splitlines()
        if len(line.split()) == 3
    ]


def process_tree_rows(roots: tuple[int, ...], deadline: float) -> list[tuple[int, int]]:
    """(pid, RSS KiB) of every supervised root's tree from ONE process snapshot."""
    return tree_rows(process_snapshot(deadline), roots)


def tree_rows(rows: list[tuple[int, int, int]], roots: tuple[int, ...]) -> list[tuple[int, int]]:
    """(pid, RSS KiB) of the trees under `roots` within one snapshot."""
    included = set(roots)
    while True:
        expanded = included | {child for child, parent, _ in rows if parent in included}
        if expanded == included:
            break
        included = expanded
    return [(child, rss) for child, _, rss in rows if child in included]


def proportional_bytes(pid: int, rss_kib: int) -> int:
    """One process's proportional set size from its Linux `smaps_rollup`; a process that
    exited or cannot be read counts its full RSS instead."""
    try:
        with open(SMAPS_ROLLUP.format(pid=pid), encoding="ascii") as rollup:
            for line in rollup:
                if line.startswith("Pss:"):
                    return int(line.split()[1]) * 1024
    except (OSError, ValueError, IndexError):
        pass
    return rss_kib * 1024


def process_tree_memory(roots: tuple[int, ...], deadline: float) -> tuple[int, int | None]:
    """(RSS sum, PSS sum) of the supervised trees from ONE process snapshot. The budget
    is enforced on the PSS sum where Linux provides it, elsewhere on the stricter RSS."""
    return tree_memory(process_tree_rows(roots, deadline))


def tree_memory(rows: list[tuple[int, int]]) -> tuple[int, int | None]:
    """(RSS sum, PSS sum where Linux provides it) of one tree's rows."""
    rss = sum(kib * 1024 for _, kib in rows)
    if not sys.platform.startswith("linux"):
        return rss, None
    return rss, sum(proportional_bytes(pid, kib) for pid, kib in rows)


def separate_tree_memory(trees: tuple[tuple[int, ...], ...],
                         deadline: float) -> list[tuple[int, int | None]]:
    """(RSS, PSS) of each tree from ONE snapshot: a browser phase's two trees, each with
    its own budget (the person's decision of 2026-10-23, "Two 1 GiB limits"). A process
    in both trees (never expected: they start in separate sessions) counts in both."""
    rows = process_snapshot(deadline)
    return [tree_memory(tree_rows(rows, roots)) for roots in trees]


def enforced_bytes(rss: int, pss: int | None) -> int:
    return rss if pss is None else pss


def supervision_record(reason: str, beginning: float, totals: dict, *, stopped: bool) -> dict:
    return {
        "exitCode": 1,
        "reason": reason,
        "elapsedSeconds": time.monotonic() - beginning,
        "peakRssBytes": totals["peak"],
        "peakPssBytes": totals["peakPss"],
        "logBytes": totals["count"],
        "processStopped": stopped,
        "observations": totals["observations"],
        "slowestObservationSeconds": totals["slowest"],
        **({"companionPeakRssBytes": totals["companionPeak"],
            "companionPeakPssBytes": totals.get("companionPeakPss")}
           if "companionPeak" in totals else {}),
    }


SUPERVISION_REASONS = {
    "private process log exceeded 16 MiB": "log-limit",
    "private application log exceeded 16 MiB": "companion-log-limit",
    "owned application exited during browser verification": "companion-exit",
    "process tree exceeded RSS safety budget": "rss-limit",
    "application tree exceeded RSS safety budget": "companion-rss-limit",
    "owned process supervision interrupted": "interrupted",
}


def bounded_process(
    args: list[str],
    log: Path,
    *,
    seconds: float = PHASE_SECONDS,
    environment: dict | None = None,
    companion=None,
    companion_log: Path | None = None,
    allow_bounded_stop: bool = False,
) -> dict:
    """Run one child under the phase bound, an RSS budget and a private 16 MiB log.

    A browser phase supervises Playwright together with its `companion`, the served realm,
    in one supervision. Deviation by the person's decision of 2026-10-23 ("Two 1 GiB
    limits"): unlike U6's one combined budget, each tree has its own MAX_RSS, and either
    over its budget fails the phase; the realm exiting early fails the run. `serve` expects
    its child still running at the bound."""
    if not 0 < seconds <= PHASE_SECONDS or log.parent != RUN:
        raise Refused("finite owned process bound required")
    descriptor = os.open(log, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    process, code, failure = None, None, None
    beginning = time.monotonic()
    observation_end = beginning + seconds - min(7, seconds / 2)
    totals = {"count": 0, "peak": 0, "peakPss": None, "observations": 0, "slowest": 0.0}
    previous = {value: signal.getsignal(value) for value in (signal.SIGTERM, signal.SIGINT)}

    def interrupted(signum, frame):
        raise RuntimeError("owned process supervision interrupted")

    for value in previous:
        signal.signal(value, interrupted)
    try:
        with os.fdopen(descriptor, "wb") as stream, selectors.DefaultSelector() as selector:
            process = subprocess.Popen(
                args,
                cwd=ROOT,
                env=child_environment() if environment is None else environment,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                start_new_session=True,
                umask=0o077,
            )
            os.set_blocking(process.stdout.fileno(), False)
            selector.register(process.stdout, selectors.EVENT_READ)
            code = supervise(process, selector, stream, observation_end, totals,
                             (companion, companion_log))
            stream.flush()
            os.fsync(stream.fileno())
    except (Refused, RuntimeError, OSError, subprocess.SubprocessError) as error:
        reason = SUPERVISION_REASONS.get(str(error), "supervision-error")
        failure = supervision_record(reason, beginning, totals, stopped=False)
        error.supervision = failure
        raise
    finally:
        try:
            if process is not None:
                stop(process)
                process.stdout.close()
            if failure is not None:
                failure["processStopped"] = process is None or process.poll() is not None
        finally:
            for value, previous_handler in previous.items():
                signal.signal(value, previous_handler)
    if code is None and not allow_bounded_stop:
        error = Refused("owned process exceeded its deadline")
        error.supervision = supervision_record("deadline", beginning, totals, stopped=True)
        raise error
    reason = "bounded-stop" if code is None else "process-exit"
    return {
        **supervision_record(reason, beginning, totals, stopped=True),
        "exitCode": 0 if code is None else code,
    }


def observe_tree(totals: dict, prefix: str, rss: int, pss: int | None) -> None:
    """One tree's observation into its own peaks (`peak`/`peakPss`, or the companion's
    `companionPeak`/`companionPeakPss`)."""
    peak = f"{prefix}Peak" if prefix else "peak"
    proportional = f"{prefix}PeakPss" if prefix else "peakPss"
    totals[peak] = max(totals.get(peak) or 0, rss)
    if pss is not None:
        totals[proportional] = max(totals.get(proportional) or 0, pss)
    else:
        totals.setdefault(proportional, None)


def supervise(process, selector, stream, observation_end: float, totals: dict,
              watched=(None, None)) -> int | None:
    """Copy bounded output and observe the process trees until exit or time runs out."""
    companion, companion_log = watched
    code = None
    while time.monotonic() < observation_end:
        for key, _ in selector.select(timeout=0.05):
            chunk = os.read(key.fileobj.fileno(), 65536)
            if not chunk:
                selector.unregister(key.fileobj)
                continue
            totals["count"] += len(chunk)
            if totals["count"] > MAX_LOG:
                raise Refused("private process log exceeded 16 MiB")
            stream.write(chunk)
        trees: tuple[tuple[int, ...], ...] = ((process.pid,),)
        if companion is not None:
            if companion.poll() is not None:
                raise Refused("owned application exited during browser verification")
            if companion_log.stat().st_size > MAX_LOG:
                raise Refused("private application log exceeded 16 MiB")
            # The person's decision of 2026-10-23, "Two 1 GiB limits": Playwright with its
            # Chromium and the served realm are two trees, each under its own MAX_RSS.
            trees = ((process.pid,), (companion.pid,))
        observed = time.monotonic()
        # Each observation has its own short allowance, so the last one before the bound
        # never fails for the bound alone (`serve` ends at the bound by design).
        measured = separate_tree_memory(trees, observed + OBSERVATION_SECONDS)
        totals["observations"] += 1
        totals["slowest"] = max(totals["slowest"], time.monotonic() - observed)
        observe_tree(totals, "", *measured[0])
        if len(measured) > 1:
            observe_tree(totals, "companion", *measured[1])
        if enforced_bytes(totals["peak"], totals["peakPss"]) > MAX_RSS:
            raise Refused("process tree exceeded RSS safety budget")
        if len(measured) > 1 and enforced_bytes(
                totals["companionPeak"], totals["companionPeakPss"]) > MAX_RSS:
            raise Refused("application tree exceeded RSS safety budget")
        code = process.poll()
        if code is not None and not selector.get_map():
            return code
    return None


def phase_command(phase: str, report: Path) -> tuple[list[str], tuple[str, ...]]:
    """The command a verification phase runs, and the test paths it names."""
    lane = phase.removeprefix("coverage-")
    paths = lane_paths(lane)
    args = [
        str(PYTHON), "-m", "pytest", "-c", PYTEST_INI,
        *paths, "-q", "--tb=short", "--maxfail=1", f"--junitxml={report}",
    ]
    if phase in COVERAGE_PARTS:
        # One data file in the run root, begun by the first part and appended by the
        # rest (`COVERAGE_FILE`, set in `run_phase`); `coverage-report` reports it. A part
        # holds only its slice of the lines, so the 80% floor is judged once, on the
        # combined data, by `coverage-report` (`--fail-under=80`), never per part.
        args.extend(["--cov", f"--cov-config={COVERAGE_RC}", "--cov-report=",
                     "--cov-fail-under=0"])
        if phase != COVERAGE_PARTS[0]:
            args.append("--cov-append")
    return args, paths


def lane_paths(lane: str) -> tuple[str, ...]:
    """A lane's test paths; a component, integration or operations part names its files,
    and the parts of a folder, however many, must hold every file of that folder exactly
    once."""
    folder = next((name for name, halves in LANE_HALVES.items() if lane in halves), None)
    if folder is None:
        return (f"{TEST_ROOT}/{lane}",)
    present = {path.name for path in (ROOT / TEST_ROOT / folder).glob("test_*.py")}
    named = [name for files in LANE_HALVES[folder].values() for name in files]
    if len(named) != len(set(named)) or set(named) != present:
        raise Refused(f"the {folder} halves do not hold every {folder} file once")
    return tuple(f"{TEST_ROOT}/{folder}/{name}" for name in LANE_HALVES[folder][lane])


def junit_counts(report: Path, evidence: dict) -> None:
    """Zero tests, any skip, any error or failure, or a missing/invalid report fails."""
    cases = None
    if report.exists() and not report.is_symlink():
        try:
            cases = list(ET.fromstring(private_bytes(report, maximum=MAX_LOG)).iter("testcase"))
        except (ValueError, OSError, ET.ParseError):
            evidence["invalidTestReport"] = True
            evidence["exitCode"] = evidence["exitCode"] or 1
    if cases is not None:
        evidence.update(
            tests=len(cases),
            failures=sum(c.find("failure") is not None for c in cases),
            errors=sum(c.find("error") is not None for c in cases),
            skipped=sum(c.find("skipped") is not None for c in cases),
        )
        if not cases or evidence["skipped"] or evidence["errors"] or evidence["failures"]:
            evidence["exitCode"] = evidence["exitCode"] or 1
    elif "invalidTestReport" not in evidence:
        evidence["missingTestReport"] = True
        evidence["exitCode"] = evidence["exitCode"] or 1


COVERAGE_LINE = re.compile(r"^TOTAL\s+\d+\s+\d+\s+(\d+(?:\.\d+)?)%", re.MULTILINE)


def coverage_percent(log: Path) -> float | None:
    """The last TOTAL line coverage figure a report printed."""
    try:
        text = private_bytes(log, maximum=MAX_LOG).decode(errors="replace")
    except (OSError, ValueError):
        return None
    found = COVERAGE_LINE.findall(text)
    return float(found[-1]) if found else None


def preserve_prior_report(phase: str) -> list[dict]:
    """Preserve the exact owned report before a phase can replace it."""
    require_private_directory(RUN, "report preservation root custody differs")
    source = RUN / f"{phase}.xml"
    try:
        info = source.lstat()
    except FileNotFoundError:
        return []
    if (
        not stat.S_ISREG(info.st_mode)
        or info.st_uid != os.getuid()
        or stat.S_IMODE(info.st_mode) != 0o600
        or info.st_nlink != 1
    ):
        raise Refused("prior report custody differs")
    before = hashlib.sha256(private_bytes(source, maximum=MAX_LOG)).hexdigest()
    destination = source.with_name(
        f"{source.stem}-preserved-{time.time_ns()}-{secrets.token_hex(4)}{source.suffix}"
    )
    if destination.exists() or destination.is_symlink():
        raise Refused("prior evidence preservation destination exists")
    os.rename(source, destination)
    if hashlib.sha256(private_bytes(destination, maximum=MAX_LOG)).hexdigest() != before:
        raise Refused("preserved evidence checksum differs")
    fsync_directory(RUN)
    return [{"original": source.name, "preserved": destination.name, "sha256": before}]


CREDENTIAL_FILES = (
    ("owner-credentials.json", "owner credential identity mismatch"),
    ("standin-credentials.json", "stand-in credential identity mismatch"),
    ("platform-credentials.json", "platform credential identity mismatch"),
)


def require_credential_identity(value: dict) -> None:
    """Each credential file in the run root names this realm's run (L1-50), with the
    reasons `migrate` gives; it only reads them."""
    for name, reason in CREDENTIAL_FILES:
        target = RUN / name
        if not target.exists():
            continue
        try:
            held = json.loads(private_bytes(target))
        except (OSError, ValueError):
            raise Refused(reason) from None
        if not isinstance(held, dict) or held.get("runId") != value["runId"]:
            raise Refused(reason)


def require_applied_chain(value: dict) -> None:
    """The realm's applied digests (`schema_hashes`, recorded by `migrate`) against the
    composed chain, so a changed applied file refuses the next phase as it refuses
    `migrate` (L1-50)."""
    with connect_admin(value) as conn:
        conn.execute("SET LOCAL statement_timeout=3000")
        if not conn.execute("SELECT to_regclass('public.docsuri_local_identity')").fetchone()[0]:
            raise Refused("the realm holds no applied chain; run migrate first")
        row = conn.execute(
            "SELECT schema_hashes FROM public.docsuri_local_identity WHERE singleton"
        ).fetchone()
    if row is None or not isinstance(row[0], dict):
        raise Refused("the realm holds no applied chain; run migrate first")
    validate_chain(*chain(), dict(row[0]))


def prepare_phase(path: Path) -> tuple[dict, dict]:
    """The checks every verification phase runs first."""
    _, value = manifest(path)
    require_credential_identity(value)
    require_resources(value)
    require_key_folders()
    resources = preflight(established=True)
    if {name: digest(ROOT / name) for name in LOCKS} != value["locks"]:
        raise Refused("frozen dependency identity changed")
    require_stopped()
    require_applied_chain(value)
    return value, resources


def real_sends_spent(value: dict) -> int:
    with connect_admin(value) as conn:
        conn.execute("SET LOCAL statement_timeout=3000")
        return conn.execute(
            "SELECT count(*) FROM topics.send_log_entry WHERE path_kind='real'"
        ).fetchone()[0]


def require_send_headroom(value: dict) -> int:
    """Refuse before the run, not inside it, when the realm's real-send allocation is
    nearly spent: the next integration run needs a fresh realm."""
    spent = real_sends_spent(value)
    if REAL_SEND_LIMIT - spent < REAL_SEND_HEADROOM:
        raise Refused("the realm's real-send allocation is nearly spent; archive-owned, "
                      "then setup a fresh realm")
    return spent


def prepare_web(path: Path) -> dict:
    """`build-web` in its own process under the phase bound; its result is evidence."""
    started = time.monotonic()
    completed = command([str(PYTHON), str(ROOT / SYNTHETIC_V1), "build-web",
                         "--environment-file", str(path)], timeout=PHASE_SECONDS)
    try:
        result = json.loads(completed.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        result = None
    if completed.returncode or not isinstance(result, dict) or result.get("state") not in (
        "built", "present"
    ):
        raise Refused("v1's web build failed; its log is v1/web-build.log")
    return {**result, "seconds": round(time.monotonic() - started, 1)}


def run_v1(word: str, path: Path) -> dict:
    """`v1-up` or `v1-down`: the synthetic v1 (`scripts/u8_synthetic_v1.py`) under the
    phase bound, with its evidence; the supervisor it starts outlives the phase."""
    if word == "v1-down":
        # The stop still runs for a realm being set aside that has outlived its
        # retention: expiry prevents execution, not preservation, and the archive
        # that follows cannot succeed while v1 holds the realm. The live-only
        # checks (memory preflight, frozen locks) belong to a run, not a stop.
        value = preservation_manifest(path)
        require_resources(value)
        require_key_folders()
        require_stopped()
        resources = None
    else:
        value, resources = prepare_phase(path)
    require_test_paths((SYNTHETIC_V1,))
    log = RUN / f"u8-phase-{word}-{time.time_ns()}.log"
    args = [str(PYTHON), str(ROOT / SYNTHETIC_V1), word, "--environment-file", str(path)]
    started, failure, supervision, build = time.monotonic(), None, {}, None
    if word == "v1-up":
        # v1's web is built once per commit outside the bounded child, as `setup` builds
        # the database image: `next build` needs more than the child's 1 GiB tree budget.
        # It still counts against this phase's one bound.
        build = prepare_web(path)
    try:
        remaining = PHASE_SECONDS - (time.monotonic() - started)
        if remaining < 30:
            raise Refused("the web build left too little of the phase bound")
        supervision = bounded_process(args, log, seconds=remaining)
    except (Refused, RuntimeError, OSError, subprocess.SubprocessError) as error:
        failure = type(error).__name__
        supervision = getattr(error, "supervision", {})
    result = None
    with contextlib.suppress(OSError, ValueError, IndexError):
        result = json.loads(private_bytes(log, maximum=MAX_LOG).decode().strip().splitlines()[-1])
    evidence = {
        "phase": word, "runId": value["runId"], "command": args,
        "exitCode": 1 if failure else supervision["exitCode"], "supervision": supervision,
        "failureCategory": failure, "durationSeconds": time.monotonic() - started,
        "phaseBoundSeconds": PHASE_SECONDS, "resources": resources, "result": result,
        "manifestSha256": digest(path), "webBuild": build,
    }
    if not isinstance(result, dict) or result.get("state") != word:
        evidence["exitCode"] = evidence["exitCode"] or 1
    private_json(RUN / f"{word}-evidence-{time.time_ns()}.json", evidence)
    print(json.dumps({key: evidence[key] for key in ("phase", "exitCode", "failureCategory",
                                                        "durationSeconds")}
                     | {"result": result}))
    if evidence["exitCode"]:
        raise Refused(f"{word} failed; evidence preserved")
    return {"state": "passed", "phase": word}


def v1_serving() -> bool:
    """The synthetic v1's supervisor is alive and v1's API answers its health address."""
    sys.path.insert(0, str(ROOT / "scripts"))
    import u8_synthetic_v1

    if u8_synthetic_v1.supervisor_pid() is None:
        return False
    with contextlib.suppress(OSError, ValueError):
        import urllib.request

        with urllib.request.urlopen(u8_synthetic_v1.API_HEALTH, timeout=3) as answer:
            return answer.status == 200
    return False


FIXTURES_CORPUS = "load"
COMPOSITE_PHASES = {"component": tuple(COMPONENT_HALVES),
                    "integration": tuple(INTEGRATION_HALVES),
                    "operations": tuple(OPERATIONS_HALVES),
                    "coverage": (*COVERAGE_PARTS, "coverage-report")}


def run_parts(phase: str, path: Path) -> dict:
    """A composite name's parts in order, each its own phase with its own bound and
    evidence; the first failed part ends it."""
    results = []
    for part in COMPOSITE_PHASES[phase]:
        results.append(run_test_phase(part, path))
    return {"state": "passed", "phase": phase, "parts": [item["phase"] for item in results]}


def coverage_data_sha256(data: Path) -> str | None:
    """The coverage data file's SHA-256, or None when there is no regular file."""
    if data.is_symlink() or not data.is_file():
        return None
    return digest(data)


def part_run(part: str, path: Path) -> dict:
    """One coverage part run's evidence, as the report's source rule reads it."""
    value = json.loads(private_bytes(path, maximum=MAX_LOG))
    source = value.get("source")
    return {"part": part, "evidence": path.name, "at": path.stat().st_mtime,
            "exitCode": value.get("exitCode"), "runId": value.get("runId"),
            "sourceSha256": source.get("sha256") if isinstance(source, dict) else None,
            "sourceChangedDuringRun": value.get("sourceChangedDuringRun") is True,
            "dataBeforeSha256": value.get("coverageDataSha256Before"),
            "dataSha256": value.get("coverageDataSha256")}


def coverage_parts_state(run: Path, run_id: str) -> dict:
    """Each coverage part's latest evidence in `run`. A part is missing without evidence,
    stale when its evidence is from another realm or older than the latest first part
    (which began the data file afresh), and failed on any nonzero exit. Every part run at
    or after that first part appended to the data file, so all of them are listed in
    order (`runsSinceFirstPart`), superseded and failed runs included."""
    parts, missing, every = {}, [], []
    for part in COVERAGE_PARTS:
        found = sorted(run.glob(f"{part}-evidence-*.json"),
                       key=lambda item: (item.stat().st_mtime, item.name))
        if not found:
            missing.append(part)
            continue
        runs = [part_run(part, item) for item in found]
        every.extend(runs)
        latest = runs[-1]
        parts[part] = {key: latest[key] for key in (
            "exitCode", "evidence", "runId", "at", "sourceSha256")}
    begun = parts.get(COVERAGE_PARTS[0], {}).get("at")
    stale = [part for part, item in parts.items()
             if begun is None or item["at"] < begun or item["runId"] != run_id]
    failed = [part for part, item in parts.items() if item["exitCode"] != 0]
    since = sorted((item for item in every if begun is not None and item["at"] >= begun),
                   key=lambda item: (item["at"], item["evidence"]))
    return {"parts": parts, "missingParts": missing, "staleParts": stale,
            "failedParts": failed, "runsSinceFirstPart": since}


def coverage_data_chain_broken(runs: list[dict]) -> bool:
    """True unless every run since the first part started from the data file the run
    before it left. The first part's own run is the exception: it begins the file afresh.
    A run that wrote no evidence anywhere in the sequence (an orphaned child after the
    runner was killed, say) changes the file between two recorded digests, so the next
    run's starting digest no longer matches."""
    for index, item in enumerate(runs):
        if index == 0 and item["part"] == COVERAGE_PARTS[0]:
            continue
        if index == 0:
            return True
        left = runs[index - 1]["dataSha256"]
        if item.get("dataBeforeSha256") is None or left is None:
            return True
        if item["dataBeforeSha256"] != left:
            return True
    return False


def coverage_source_problems(state: dict, data: Path, before: dict) -> dict:
    """Step 95(a): the parts whose runs since the first part name another source or
    recorded a change during their run, and whether the data file is bound to the
    recorded runs: each run since the first part started from the digest the run before
    it left, and the file is the one the last of those runs left (a run that wrote no
    evidence, at the end or between two parts, leaves it changed)."""
    runs = state.get("runsSinceFirstPart", [])
    other = {item["part"] for item in runs
             if item["sourceSha256"] != before["sha256"] or item["sourceChangedDuringRun"]}
    other |= {part for part, item in state["parts"].items()
              if item.get("sourceSha256") != before["sha256"]}
    unbound = bool(runs) and (runs[-1]["dataSha256"] is None
                              or runs[-1]["dataSha256"] != coverage_data_sha256(data)
                              or coverage_data_chain_broken(runs))
    return {"otherSourceParts": sorted(other), "dataFileUnbound": unbound}


def run_coverage_report(path: Path) -> dict:
    """`coverage-report`: every part of this run passed, then one combined report from
    the run root's data file against decision "Coverage scope"'s 80% floor. A missing,
    stale or failed part fails it without reporting."""
    value, _resources = prepare_phase(path)
    data = RUN / COVERAGE_DATA
    before = source_identity()
    started = time.monotonic()
    state = coverage_parts_state(RUN, value["runId"])
    evidence = {"phase": "coverage-report", "runId": value["runId"], **state, "source": before}
    # Step 95(a): the combined figure is never measured over two sources. A part run since
    # the first part on another digest than the report's (superseded runs included), a
    # data file no part's evidence left as it is, or a change during the report, runs no
    # report child.
    problems = coverage_source_problems(state, data, before)
    other = problems["otherSourceParts"]
    changed = bool(other) or source_identity()["sha256"] != before["sha256"]
    if other:
        evidence["otherSourceParts"] = other
    if problems["dataFileUnbound"]:
        evidence["dataFileUnbound"] = True
    if changed:
        evidence["sourceChangedDuringRun"] = True
    code = 1
    if (not (state["missingParts"] or state["staleParts"] or state["failedParts"] or changed
             or problems["dataFileUnbound"])
            and data.is_file() and not data.is_symlink()):
        log = RUN / f"u8-phase-coverage-report-{time.time_ns()}.log"
        args = [str(PYTHON), "-m", "coverage", "report", f"--rcfile={COVERAGE_RC}",
                # Two decimals: coverage.py rounds the total to `precision` before it
                # compares with the floor, so at 0 a 79.56% total passed as "80%".
                "--show-missing", "--precision=2", "--fail-under=80"]
        supervision = bounded_process(
            args, log, environment=child_environment({"COVERAGE_FILE": str(data)}))
        code = supervision["exitCode"]
        evidence.update(supervision=supervision, log=log.name,
                        coverageTotalPercent=coverage_percent(log))
    elif not data.is_file() or data.is_symlink():
        evidence["missingDataFile"] = True
    if not changed and source_identity()["sha256"] != before["sha256"]:
        evidence["sourceChangedDuringRun"] = True
        code = 1
    evidence.update(exitCode=code, durationSeconds=time.monotonic() - started)
    private_json(RUN / f"coverage-report-evidence-{time.time_ns()}.json", evidence)
    print(json.dumps({key: evidence.get(key) for key in (
        "phase", "exitCode", "coverageTotalPercent", "missingParts", "staleParts",
        "failedParts", "sourceChangedDuringRun", "durationSeconds")}))
    if code:
        raise Refused("U8 coverage report failed; evidence preserved")
    return {"state": "passed", "phase": "coverage-report"}


# The fixtures phase's record (`u8_phases.run_fixtures` writes `fixtures/phase.json`, and
# its child the accounts it made, under this folder).
FIXTURES_FOLDER = "fixtures"
COVERAGE_AFTER_FIXTURES = (
    "coverage-after-fixtures: the fixtures phase ran in this realm, so its synthetic "
    "accounts leave too few of the 20 for the coverage parts; run coverage straight "
    "after migrate on a fresh realm"
)


def refuse_coverage_after_fixtures(run: Path, phase: str) -> None:
    """U8's coverage phase, and each of its parts, refuses up front in a realm where the
    fixtures phase ran: the fixtures' accounts count against the realm's 20 synthetic
    accounts (`MAX_SYNTHETIC_ACCOUNTS`), which the coverage parts need, so a later part
    would fail midway. Nothing runs, and no evidence is written."""
    if (phase == "coverage" or phase in COVERAGE_PARTS) and (run / FIXTURES_FOLDER).exists():
        raise Refused(COVERAGE_AFTER_FIXTURES)


def run_test_phase(phase: str, path: Path) -> dict:
    refuse_coverage_after_fixtures(RUN, phase)
    if phase in COMPOSITE_PHASES:
        return run_parts(phase, path)
    if phase == "coverage-report":
        return run_coverage_report(path)
    return run_phase(phase, path)


def run_phase(phase: str, path: Path) -> dict:
    if phase in SENDING_PHASES and not v1_serving():
        # The cutover journeys run against the synthetic v1 (Step 34): it is started
        # first, as its own phase with its own bound and evidence.
        run_v1("v1-up", path)
    value, resources = prepare_phase(path)
    if phase in SENDING_PHASES:
        resources = {**resources, "realSendsSpent": require_send_headroom(value)}
    report = RUN / f"{phase}.xml"
    if report.is_symlink():
        raise Refused("test report cannot be a symlink")
    args, paths = phase_command(phase, report)
    require_test_paths(paths)
    preserved = preserve_prior_report(phase)
    before = source_identity()
    started = time.monotonic()
    supervision, failure, extra = {}, None, {}
    log = RUN / f"u8-phase-{phase}-{time.time_ns()}.log"
    environment = child_environment(
        {"COVERAGE_FILE": str(RUN / COVERAGE_DATA)} if phase in COVERAGE_PARTS else None)
    if phase in COVERAGE_PARTS:
        # Step 95(a): the data file as this part found it, so `coverage-report` can see a
        # run without evidence that changed it between two parts.
        extra["coverageDataSha256Before"] = coverage_data_sha256(RUN / COVERAGE_DATA)
    try:
        supervision = bounded_process(args, log, environment=environment)
    except (Refused, RuntimeError, OSError, subprocess.SubprocessError) as error:
        failure = type(error).__name__
        supervision = getattr(error, "supervision", {})
    if phase in production_instance_phases() and not native(value):
        # Step 98(d): whatever the child's outcome, a bound's SIGKILL included.
        try:
            extra["productionInstancesRemoved"] = remove_production_instances()
        except Refused as error:
            extra["productionInstanceRemovalFailed"] = str(error)
            failure = failure or "Refused"
    if phase in peer_proof_phases() and not native(value):
        # Package G3: the same for the peer map proof's scratch container.
        try:
            extra["peerProofsRemoved"] = remove_peer_proofs()
        except Refused as error:
            extra["peerProofRemovalFailed"] = str(error)
            failure = failure or "Refused"
    evidence = {
        "phase": phase,
        "runId": value["runId"],
        "command": args,
        "testPaths": list(paths),
        "exitCode": 1 if failure else supervision["exitCode"],
        "supervision": supervision,
        "failureCategory": failure,
        "durationSeconds": time.monotonic() - started,
        "phaseBoundSeconds": PHASE_SECONDS,
        "source": before,
        "locks": value["locks"],
        "policy": value["policy"],
        "manifestSha256": digest(path),
        "fixtureSourceSha256": digest(ROOT / TEST_ROOT / "conftest.py"),
        "resources": resources,
        "preservedEvidence": preserved,
        **extra,
    }
    junit_counts(report, evidence)
    if phase in COVERAGE_PARTS:
        # Step 95(a): the data file as this part left it, so `coverage-report` refuses a
        # file that a run without evidence changed afterwards.
        evidence["coverageDataSha256"] = coverage_data_sha256(RUN / COVERAGE_DATA)
    if source_identity()["sha256"] != before["sha256"]:
        evidence["sourceChangedDuringRun"] = True
        evidence["exitCode"] = evidence["exitCode"] or 1
    private_json(RUN / f"{phase}-evidence-{time.time_ns()}.json", evidence)
    print(json.dumps(safe_phase_summary(evidence)))
    if evidence["exitCode"]:
        raise Refused("U8 phase failed; evidence preserved")
    return {"state": "passed", "phase": phase}


def safe_phase_summary(evidence):
    """Only fixed classifications and numeric supervision; never private log content."""
    result = {
        key: evidence[key]
        for key in (
            "phase",
            "exitCode",
            "tests",
            "failures",
            "errors",
            "skipped",
            "failureCategory",
            "missingTestReport",
            "invalidTestReport",
            "sourceChangedDuringRun",
            "coverageTotalPercent",
            "durationSeconds",
        )
        if key in evidence
    }
    result["supervision"] = {
        key: evidence.get("supervision", {}).get(key)
        for key in (
            "reason",
            "exitCode",
            "elapsedSeconds",
            "peakRssBytes",
            "peakPssBytes",
            "logBytes",
            "processStopped",
        )
    }
    return result


# --- Closing an environment -------------------------------------------------------------

PRESERVED_PREFIX = "docsuri-u8-preserved-"
FOLDER_MODE = 0o700
FILE_MODE = 0o600


def archive_identity(path: Path) -> dict:
    """Preservation identity (an expired environment is accepted), bound to this tool."""
    value = LocalProfile.preservation_identity(path)
    if path != RUN / "environment.json" or value.get("unit") != UNIT:
        raise Refused("U8 preservation requires its own explicit realm")
    require_manifest_identity(value, current_pins=False)
    return value


def key_entries(run: Path | None = None) -> list[Path]:
    """Every entry in the four key folders; a missing folder counts as empty. The run
    root is the one current when this is called (U8 plan Step 95(c))."""
    run = RUN if run is None else run
    entries = []
    for name in KEY_FOLDERS:
        folder = run / name
        if folder.is_dir() and not folder.is_symlink():
            entries.extend(folder.iterdir())
    return entries


def check_preservation_inventory(root: Path) -> None:
    """Folders 0700 and regular files 0600 with one link, owned by this user, at most
    4096 entries, the key folders holding only such files."""
    entries = [root]
    for entry in root.rglob("*"):
        entries.append(entry)
        if len(entries) > 4096:
            raise Refused("preservation inventory exceeds its bounded allocation")
    for entry in entries:
        info = entry.lstat()
        directory = stat.S_ISDIR(info.st_mode)
        if (
            info.st_uid != os.getuid()
            or not (directory or stat.S_ISREG(info.st_mode))
            or stat.S_IMODE(info.st_mode) != (FOLDER_MODE if directory else FILE_MODE)
            or (not directory and info.st_nlink != 1)
        ):
            raise Refused("preservation entry custody differs")
    if any(not entry.is_file() or entry.is_symlink() for entry in key_entries(root)):
        raise Refused("a key folder holds an entry that is not a regular file")


def delete_key_files(root: Path | None = None) -> int:
    """Step 43's key deletion, built early (round 4): after every check has passed, each
    key file is removed, so no realm key outlives its environment and `teardown`, which
    refuses while one exists, can follow. Only regular owner files are removed. The run
    root is the one current when this is called (U8 plan Step 95(c))."""
    root = RUN if root is None else root
    removed = 0
    for entry in key_entries(root):
        info = entry.lstat()
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) != FILE_MODE
            or info.st_nlink != 1
        ):
            raise Refused("key file custody differs; nothing deleted")
    for name in KEY_FOLDERS:
        folder = root / name
        for entry in sorted(folder.iterdir()):
            entry.unlink()
            removed += 1
        fsync_directory(folder)
    return removed


def check_preservation_database(value: dict) -> None:
    with connect_admin(value) as conn:
        identity = conn.execute(
            "SELECT run_id,current_database() FROM public.docsuri_local_identity"
        ).fetchone()
        if tuple(identity or ()) != (value["runId"], DATABASE):
            raise Refused("preservation database identity differs")
        active = conn.execute(
            "SELECT count(*) FROM pg_stat_activity WHERE pid<>pg_backend_pid() "
            "AND backend_type='client backend'"
        ).fetchone()[0]
        if active:
            raise Refused("other database clients prevent safe preservation")


def stop_database(value: dict) -> None:
    """An acknowledged `docker stop --time 10` of the owned database container (or the
    native server's fast stop)."""
    if native(value):
        stop_native()
        return
    require(["docker", "stop", "--time", "10", value["container"]], timeout=15)
    stopped = json.loads(require(["docker", "container", "inspect", value["container"]]).stdout)
    if len(stopped) != 1 or stopped[0]["State"]["Running"]:
        raise Refused("database stop was not acknowledged; directory retained")


def archive_owned(path: Path) -> dict:
    """Every check first, then an acknowledged database stop, then the rename of the run
    root aside. Nothing is deleted: the stopped container, its volume and every file are
    kept, so the next `setup` starts a fresh realm beside the preserved one."""
    value = archive_identity(path)
    require_resources(value)
    if (RUN / "v1" / "supervisor.json").exists():
        # The synthetic v1 stops first; its stopped containers and volumes are kept.
        run_v1("v1-down", path)
    for port in (APPLICATION_PORT, PUBLIC_PORT, MAINTENANCE_PORT, V1_API_PORT, V1_WEB_PORT):
        require_stopped(port)
    # Step 98(d): a production instance a killed module run left holds no evidence (its
    # data lives on a tmpfs), so it is removed, never preserved.
    instances = [] if native(value) else remove_production_instances()
    # Package G3: the peer map proof's scratch container, likewise.
    proofs = [] if native(value) else remove_peer_proofs()
    opened = command(["lsof", "+D", str(RUN)], timeout=10)
    if opened.returncode != 1 or opened.stdout.strip():
        raise Refused("owned directory is in use or custody could not be checked")
    check_preservation_inventory(RUN)
    check_preservation_database(value)
    destination = RUN.with_name(f"{PRESERVED_PREFIX}{value['runId']}-{secrets.token_hex(4)}")
    if destination.exists() or destination.is_symlink():
        raise Refused("preservation destination exists")
    require_resources(value)
    keys_deleted = delete_key_files(RUN)
    stop_database(value)
    try:
        os.rename(RUN, destination)
    except OSError:
        raise Refused(
            "the environment folder could not be renamed; it stays stopped under its own name"
        ) from None
    fsync_directory(destination.parent)
    return {
        "state": "preserved",
        "path": str(destination),
        "runId": value["runId"],
        "expiresAt": value["expiresAt"],
        "containerStopped": True,
        "volumePreserved": value["volume"],
        "keyFilesDeleted": keys_deleted,
        "productionInstancesRemoved": instances,
        "peerProofsRemoved": proofs,
    }


def teardown(path: Path) -> dict:
    """Disposes of nothing; refuses while a key file exists, so a teardown can never leave
    a key behind."""
    value = archive_identity(path)
    if key_entries():
        raise Refused("teardown refuses while a key folder holds a file; run archive-owned")
    return {
        "state": "preserved",
        "runId": value["runId"],
        "note": "automatic disposal disabled; retain evidence and resources",
    }


# --- U2's tests on the composed chain (Step 6, BR1.5) -----------------------------------
#
# A U2-identity environment, built from U8's database image with U2's own limits and the
# eleven owners the composed chain needs, migrated with the full chain, running U2's five
# layer folders with U2's own configuration, and archived afterwards. It uses U2's run
# root and addresses, so it refuses while U2's own environment exists.

U2_RUN = Path("/tmp/docsuri-u2-run").resolve()
U2_UNIT = "u2-account-personal-controls"
U2_REALM = "account-controls"
U2_DATABASE = "docsuri_u2"
U2_DATABASE_PORT = 15449
U2_APPLICATION_PORT = 18049
U2_LABEL = "dev.docsuri.u2.run"
U2_REGRESSION_LABEL = "dev.docsuri.u8.u2-regression"
U2_MEMORY = GIB  # U2's own container limit
U2_CONNECTION_LIMIT = 2  # U2's own owner-login limit
U2_POLICY = "u2-synthetic-v1"
U2_PYTEST_INI = "backend/pytest.u2-account-personal-controls.ini"
U2_TEST_ROOT = "tests/u2_account_personal_controls"
U2_LAYERS = ("database", "repository", "component", "integration", "operations")
U2_PRESERVED_PREFIX = PRESERVED_PREFIX + "u2-regression-"


def require_u2_environment_absent() -> None:
    """U2's run root and its two listeners are free, or nothing is prepared."""
    if U2_RUN.exists() or U2_RUN.is_symlink():
        raise Refused("U2's own environment exists; u2-regression refuses while it does")
    for port in (U2_APPLICATION_PORT, U2_DATABASE_PORT):
        with socket.socket() as listener:
            try:
                listener.bind(("127.0.0.1", port))
            except OSError:
                raise Refused("a U2 listener is in use; u2-regression refuses") from None


def u2_regression_image() -> str:
    """U8's pinned database image by its one tag, which U2's restore rehearsal accepts
    exactly; the tag must name the image whose labels carry the pins."""
    from docsuri_ops.arrangement import runtimes

    verified = database_image()
    record = inspect_image(runtimes.DATABASE_IMAGE_TAG)
    if record is None or record["Id"] != verified:
        raise Refused("U8's database image tag does not name the verified image")
    return runtimes.DATABASE_IMAGE_TAG


def u2_regression_manifest(image: str, u8_run_id: str) -> dict:
    """U2's own manifest fields, with U8's image and a record of who prepared it."""
    run_id = "docsuri-u2-" + secrets.token_hex(8)
    now = time.time()
    return {
        "unit": U2_UNIT,
        "profile": "synthetic-local",
        "repository": str(ROOT),
        "runId": run_id,
        "container": run_id,
        "volume": run_id + "-pgdata",
        "databaseImage": image,
        "database": U2_DATABASE,
        "realm": U2_REALM,
        "databasePort": U2_DATABASE_PORT,
        "applicationPort": U2_APPLICATION_PORT,
        "createdAt": now,
        "expiresAt": now + 86400,
        "sourceSha": require(["git", "rev-parse", "HEAD"]).stdout.strip(),
        "locks": {name: digest(ROOT / name) for name in LOCKS},
        "policy": U2_POLICY,
        "fixtureAccounts": [],
        "fixturePapers": [],
        "preparedBy": {"unit": UNIT, "phase": "u2-regression", "runId": u8_run_id},
    }


def u2_database_command(value: dict, u8_run_id: str) -> list[str]:
    """U2's own container limits and settings (`scripts/verify_docsuri_u2.py`), on U8's
    image, labelled for U2 and for this phase."""
    return [
        "docker", "run", "-d",
        "--name", value["container"],
        "--label", f"{U2_LABEL}={value['runId']}",
        "--label", f"{U2_REGRESSION_LABEL}={u8_run_id}",
        "--memory", "1g", "--memory-swap", "1g", "--cpus", "1", "--pids-limit", "64",
        "--read-only",
        "--tmpfs", "/tmp:rw,noexec,nosuid,size=16m",
        "--tmpfs", "/var/run/postgresql:rw,noexec,nosuid,size=16m",
        "-p", f"127.0.0.1:{U2_DATABASE_PORT}:5432",
        "--mount", f"type=volume,src={value['volume']},dst=/var/lib/postgresql/data",
        "-e", "POSTGRES_PASSWORD",
        "-e", f"POSTGRES_DB={U2_DATABASE}",
        "-e", "POSTGRES_INITDB_ARGS=--data-checksums --auth-host=scram-sha-256",
        value["databaseImage"],
        "-c", "shared_buffers=64MB",
        "-c", "work_mem=2MB",
        "-c", "max_connections=12",
        "-c", "statement_timeout=3000",
        "-c", "lock_timeout=1000",
        "-c", "idle_in_transaction_session_timeout=5000",
        "-c", "max_wal_size=128MB",
    ]


def prepare_u2_regression(image: str, u8_run_id: str) -> tuple[dict, dict]:
    """The run root, U2's private files (U2's setup writes the same ones), the eleven
    owners' credentials and the bounded database container."""
    os.mkdir(U2_RUN, FOLDER_MODE)
    os.chmod(U2_RUN, FOLDER_MODE, follow_symlinks=False)
    value = u2_regression_manifest(image, u8_run_id)
    manifest_path = U2_RUN / "environment.json"
    private_json(manifest_path, value, root=U2_RUN)
    private_json(
        U2_RUN / "ownership.json",
        {"runId": value["runId"], "manifestSha256": digest(manifest_path)},
        root=U2_RUN,
    )
    password = secrets.token_urlsafe(32)
    private_json(
        U2_RUN / "migration-credentials.json", {"databaseAdminPassword": password}, root=U2_RUN
    )
    private_json(
        U2_RUN / "control-keys.json",
        {
            "runId": value["runId"],
            "version": "synthetic-key-v1",
            "seed": secrets.token_hex(32),
            "cursor": secrets.token_hex(32),
            "proof": secrets.token_hex(32),
        },
        root=U2_RUN,
    )
    # The database holds all eleven owners, which the composed chain needs. U2's realm
    # reads `owner-credentials.json` and requires exactly U2's own owners there, so the
    # three later owners' logins are kept in a file of their own that U2's code never reads.
    credentials = {
        "runId": value["runId"],
        "roles": {name: secrets.token_urlsafe(32) for name in sorted(OWNERS)},
    }
    private_json(
        U2_RUN / "owner-credentials.json",
        {"runId": value["runId"], "roles": {
            name: password for name, password in credentials["roles"].items() if name in SCHEMAS
        }},
        root=U2_RUN,
    )
    private_json(
        U2_RUN / "composed-owner-credentials.json",
        {"runId": value["runId"], "roles": {
            name: password for name, password in credentials["roles"].items()
            if name not in SCHEMAS
        }},
        root=U2_RUN,
    )
    require(
        [
            "docker", "volume", "create",
            "--label", f"{U2_LABEL}={value['runId']}",
            "--label", f"{U2_REGRESSION_LABEL}={u8_run_id}",
            value["volume"],
        ]
    )
    require(u2_database_command(value, u8_run_id), extra={"POSTGRES_PASSWORD": password})
    wait_database_endpoint(value, database=U2_DATABASE, port=U2_DATABASE_PORT, root=U2_RUN)
    return value, credentials


def migrate_u2_regression(value: dict, credentials: dict) -> dict:
    """The base install at U2's owner-login limit, U1's amendments, then the full composed
    chain (`u8_search.sql` included), and the verifier custody U2's migrate establishes."""
    from psycopg.types.json import Jsonb

    from backend.modules.accounts.control_policy import SYNTHETIC_POLICY
    from backend.modules.accounts.services.control_entry import ControlEntryService
    from backend.transactions import OwnerTransactions

    target = {"port": U2_DATABASE_PORT, "root": U2_RUN}
    hashes = {name: digest(ROOT / file) for name, file in SCHEMAS.items()}
    with connect_admin(value, dbname=U2_DATABASE, **target) as conn:
        versions = require_versions(conn)
    extension = install_extension(value, database=U2_DATABASE, **target)
    with connect_admin(value, dbname=U2_DATABASE, **target) as conn:
        install_base(
            conn, value, credentials, hashes,
            database=U2_DATABASE, connection_limit=U2_CONNECTION_LIMIT,
        )
        known = amend(conn, value, hashes)
        applied = apply_migrations(conn, known, database=U2_DATABASE)
        conn.execute(
            "UPDATE public.docsuri_local_identity SET schema_hashes=%s WHERE singleton",
            (Jsonb(known),),
        )
    transactions = OwnerTransactions(LocalProfile.load(U2_RUN / "environment.json"))
    try:
        ControlEntryService(transactions, SYNTHETIC_POLICY)
    finally:
        transactions.close()
    return {
        "versions": versions,
        "extension": extension,
        "migrationCount": len(known),
        "appliedNow": len(applied),
        "searchApplied": "backend/modules/corpus/u8_search.sql" in known,
    }


def run_u2_layer(layer: str) -> dict:
    """One of U2's layer folders in U2's own form (`--maxfail=1`, U2's ini unchanged),
    under this tool's bound, RSS budget and JUnit checks."""
    environment = child_environment(
        {"DOCSURI_U2_ENVIRONMENT_FILE": str(U2_RUN / "environment.json")}
    )
    test_path = f"{U2_TEST_ROOT}/{layer}"
    require_test_paths((test_path,))
    name = f"u2-regression-{layer}"
    preserved = preserve_prior_report(name)
    report = RUN / f"{name}.xml"
    args = [
        str(PYTHON), "-m", "pytest", "-c", U2_PYTEST_INI, test_path,
        "-q", "--maxfail=1", f"--junitxml={report}",
    ]
    failure, supervision = None, {}
    try:
        supervision = bounded_process(
            args, RUN / f"u8-phase-{name}-{time.time_ns()}.log", environment=environment
        )
    except (Refused, RuntimeError, OSError, subprocess.SubprocessError) as error:
        failure = type(error).__name__
        supervision = getattr(error, "supervision", {})
    evidence = {
        "layer": layer,
        "command": args,
        "exitCode": 1 if failure else supervision["exitCode"],
        "supervision": supervision,
        "failureCategory": failure,
        "preservedEvidence": preserved,
    }
    junit_counts(report, evidence)
    return evidence


U2_PORT_WAIT_SECONDS = 120


def wait_u2_database_port() -> None:
    """After an archive, the stopped listener's TIME_WAIT sockets hold 15449 briefly;
    wait for it within a fixed bound, never past it."""
    deadline = time.monotonic() + U2_PORT_WAIT_SECONDS
    while True:
        with socket.socket() as listener:
            try:
                listener.bind(("127.0.0.1", U2_DATABASE_PORT))
                return
            except OSError:
                pass
        if time.monotonic() >= deadline:
            raise Refused("U2's database port did not become free")
        time.sleep(2)


def u2_layer_in_fresh_realm(layer: str, image: str, u8_run_id: str) -> dict:
    """As U2's own CI runs each layer: a fresh U2-identity realm, migrated with the full
    composed chain, then that one layer, then the archive."""
    import psycopg

    value, migration, result, failure, reason = None, {}, None, None, None
    archive, archive_failure = None, None
    try:
        wait_u2_database_port()
        value, credentials = prepare_u2_regression(image, u8_run_id)
        migration = migrate_u2_regression(value, credentials)
        result = run_u2_layer(layer)
    except (Refused, RuntimeError, OSError, ValueError, psycopg.Error) as error:
        failure = type(error).__name__
        # Refusals and the profile loader's ValueErrors carry fixed reasons, no secrets.
        reason = str(error) if isinstance(error, (Refused, ValueError)) else None
    finally:
        try:
            archive = archive_u2_regression(value, u8_run_id)
        except (Refused, OSError) as error:
            archive_failure = str(error) if isinstance(error, Refused) else type(error).__name__
    result = result or {"layer": layer, "exitCode": 1}
    result.update(
        u2RunId=None if value is None else value["runId"],
        migration=migration,
        setupFailureCategory=failure,
        setupFailureReason=reason,
        archive=archive,
        archiveFailure=archive_failure,
    )
    if failure is not None or archive_failure is not None:
        result["exitCode"] = 1
    return result


def u2_regression_owned(kind: str, name: str, run_id: str, u8_run_id: str) -> bool:
    result = command(["docker", kind, "inspect", name])
    if result.returncode:
        return False
    records = json.loads(result.stdout)
    labels = (records[0].get("Labels") if kind == "volume" else records[0]["Config"].get(
        "Labels")) or {}
    return (
        len(records) == 1
        and labels.get(U2_LABEL) == run_id
        and labels.get(U2_REGRESSION_LABEL) == u8_run_id
    )


def archive_u2_regression(value: dict | None, u8_run_id: str) -> dict | None:
    """An acknowledged stop of this phase's own container, then the rename of U2's run root
    aside. Nothing is deleted: the stopped container, its volume and every file are kept."""
    if not U2_RUN.exists():
        return None
    require_private_directory(U2_RUN, "U2-identity run root custody differs")
    run_id = (value or {}).get("runId")
    written = U2_RUN / "environment.json"
    if run_id is None and written.is_file() and not written.is_symlink():
        # Preparation stopped after writing the manifest: its container may exist.
        run_id = json.loads(private_bytes(written)).get("runId")
    stopped = False
    if run_id is not None and u2_regression_owned("container", run_id, run_id, u8_run_id):
        stop_database({"container": run_id})
        stopped = True
    opened = command(["lsof", "+D", str(U2_RUN)], timeout=10)
    if opened.returncode != 1 or opened.stdout.strip():
        raise Refused("the U2-identity run root is in use; it stays under its own name")
    destination = U2_RUN.with_name(
        f"{U2_PRESERVED_PREFIX}{run_id or 'unprepared'}-{secrets.token_hex(4)}"
    )
    if destination.exists() or destination.is_symlink():
        raise Refused("preservation destination exists")
    os.rename(U2_RUN, destination)
    fsync_directory(destination.parent)
    return {
        "state": "preserved",
        "path": str(destination),
        "runId": run_id,
        "containerStopped": stopped,
        "volumePreserved": None if run_id is None else run_id + "-pgdata",
    }


def u2_regression(path: Path) -> dict:
    """BR1.5: U2's five test layers, each on a fresh U2-identity realm built from the
    composed chain, as U2's own CI gives each layer a fresh environment."""
    u8_value, resources = prepare_phase(path)
    require_u2_environment_absent()
    image = u2_regression_image()
    available = docker_available_memory(image)
    if available < U2_MEMORY + RECOVERY_MEMORY:
        raise Refused(
            f"Docker available bytes {available} below the U2-identity database "
            f"({U2_MEMORY}) and the recovery reserve ({RECOVERY_MEMORY})"
        )
    require_test_paths((U2_TEST_ROOT, U2_PYTEST_INI))
    before = source_identity(U2_TEST_ROOT)
    started = time.monotonic()
    layers = []
    for layer in U2_LAYERS:
        layers.append(u2_layer_in_fresh_realm(layer, image, u8_value["runId"]))
        if layers[-1].get("archiveFailure") is not None:
            break  # U2's run root is still in place; no further realm can be prepared.
    evidence = {
        "phase": "u2-regression",
        "runId": u8_value["runId"],
        "databaseImage": image,
        "containerMemoryBytes": U2_MEMORY,
        "ownerConnectionLimit": U2_CONNECTION_LIMIT,
        "owners": sorted(OWNERS),
        "layers": layers,
        "tests": sum(layer.get("tests", 0) for layer in layers),
        "failures": sum(layer.get("failures", 0) for layer in layers),
        "errors": sum(layer.get("errors", 0) for layer in layers),
        "skipped": sum(layer.get("skipped", 0) for layer in layers),
        "durationSeconds": time.monotonic() - started,
        "phaseBoundSeconds": PHASE_SECONDS,
        "source": before,
        "locks": u8_value["locks"],
        "resources": resources,
        "dockerAvailableBytes": available,
    }
    evidence["exitCode"] = int(
        len(layers) != len(U2_LAYERS) or any(layer["exitCode"] for layer in layers)
    )
    if source_identity(U2_TEST_ROOT)["sha256"] != before["sha256"]:
        evidence["sourceChangedDuringRun"] = True
        evidence["exitCode"] = 1
    private_json(RUN / f"u2-regression-evidence-{time.time_ns()}.json", evidence)
    print(json.dumps({
        **{key: evidence[key] for key in (
            "phase", "exitCode", "tests", "failures", "errors", "skipped", "durationSeconds",
        )},
        "layers": [
            {
                **{key: layer.get(key) for key in (
                    "layer", "exitCode", "tests", "failures", "errors", "skipped",
                    "failureCategory", "u2RunId", "setupFailureCategory",
                    "setupFailureReason", "archiveFailure",
                )},
                "migrationCount": layer.get("migration", {}).get("migrationCount"),
                "searchApplied": layer.get("migration", {}).get("searchApplied"),
                "serverVersion": layer.get("migration", {}).get("versions", {}).get(
                    "serverVersion"),
                "preserved": (layer.get("archive") or {}).get("path"),
            }
            for layer in layers
        ],
    }))
    if evidence["exitCode"]:
        raise Refused("U2's tests did not pass on the composed chain; evidence preserved")
    return {"state": "passed", "phase": "u2-regression"}


def release_performance(path: Path) -> dict:
    """`release-performance` (cicd-pipeline § 5.2; your decision of 2026-10-24): `setup`,
    `migrate`, `fixtures` until the corpus is complete, `serve`, `performance`, each under
    its own bound, and then the realm set aside (`archive-owned`, which stops the native
    database and keeps its folder; `teardown` refuses while a key file exists)."""
    import u8_phases

    steps: list[dict] = [{"step": "setup", **setup(path)}, {"step": "migrate", **migrate(path)}]
    module = sys.modules[__name__]
    for _ in range(RELEASE_FIXTURE_RUNS):
        loaded = u8_phases.PHASES["fixtures"](module, path)
        steps.append({"step": "fixtures", **loaded})
        if loaded["state"] == "fixtures-ready":
            break
    else:
        raise Refused("the corpus did not complete within its fixture runs")
    for phase in ("serve", "performance"):
        steps.append({"step": phase, **u8_phases.PHASES[phase](module, path)})
    steps.append({"step": "archive-owned", **archive_owned(path)})
    return {"state": "passed", "phase": "release-performance", "steps": steps}


def dispatch(phase: str, path: Path) -> tuple[dict, int]:
    """One phase under the runner lock."""
    if phase == "release-performance":
        return release_performance(path), 0
    if phase == "setup":
        return setup(path), 0
    if phase == "migrate":
        return migrate(path), 0
    if phase == "archive-owned":
        return archive_owned(path), 0
    if phase == "teardown":
        return teardown(path), 0
    if phase == "u2-regression":
        return u2_regression(path), 0
    if phase in V1_PHASES:
        return run_v1(phase, path), 0
    if phase in STEP43_PHASES:
        import u8_phases

        return u8_phases.PHASES[phase](sys.modules[__name__], path), 0
    return run_test_phase(phase, path), 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", required=True, choices=PHASES)
    parser.add_argument("--profile", required=True, choices=["synthetic-local"])
    parser.add_argument("--environment-file", required=True, type=Path)
    # `fixtures` only (the person's decision of 2026-10-23, "Smaller database"): `skip`
    # stops before the corpus; `only` loads the corpus alone, as the verification run's
    # `complete_corpus` does after `browser-recovery` has erased memberC (U8 plan Step 102,
    # the verification run's order); the run records the mode in `fixtures/phase.json`.
    parser.add_argument("--corpus", choices=("load", "skip", "only"), default=None)
    # The release's performance phase (Step 43): the native database and your checkout's
    # Playwright.
    parser.add_argument("--database", choices=("docker", "native"), default="docker")
    parser.add_argument("--playwright", type=Path, default=None)
    args = parser.parse_args()
    if args.corpus is not None and args.phase != "fixtures":
        raise Refused("--corpus applies to the fixtures phase only")
    global FIXTURES_CORPUS, DATABASE_KIND, PLAYWRIGHT_FRONTEND
    FIXTURES_CORPUS = args.corpus or "load"
    try:
        require_release_phase(args.phase, ROOT)
        if args.database == "native" and args.phase not in RELEASE_PHASES:
            raise NativeRefused("--database native runs only the release's performance phases")
        DATABASE_KIND = args.database
        if args.playwright is not None:
            from u8_native import playwright_checkout

            PLAYWRIGHT_FRONTEND = playwright_checkout(args.playwright.resolve(), ROOT)
        elif release_identity(ROOT) is not None and args.phase in (
                "performance", "release-performance"):
            raise NativeRefused("a release's performance phase needs --playwright <checkout>")
    except NativeRefused as refused:
        raise Refused(str(refused)) from None
    if (
        args.environment_file.is_symlink()
        or args.environment_file.parent.is_symlink()
        or args.environment_file.resolve() != RUN / "environment.json"
    ):
        raise Refused("only the explicit U8 owned manifest is accepted")
    path = args.environment_file.resolve()
    with exclusive():
        result, code = dispatch(args.phase, path)
    print(json.dumps(result))
    return code


def refusal(error: BaseException) -> dict:
    """The top-level refusal's record. A refusal carries its own reason; any other error
    names the operation that raised it (the innermost frame: function, file and line) and,
    for an OSError, the path and the error number's name, never a message or a value."""
    if isinstance(error, Refused):
        return {"state": "refused", "category": type(error).__name__, "reason": str(error)}
    frames = traceback.extract_tb(error.__traceback__)
    innermost = frames[-1] if frames else None
    value = {
        "state": "refused",
        "category": type(error).__name__,
        "reason": "owned prerequisite unavailable",
        "operation": None if innermost is None else {
            "function": innermost.name,
            "file": Path(innermost.filename).name,
            "line": innermost.lineno,
        },
    }
    if isinstance(error, OSError):
        value["errno"] = errno.errorcode.get(error.errno) if error.errno else None
        value["path"] = None if error.filename is None else str(error.filename)
    return value


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (Refused, ValueError, OSError) as error:
        print(json.dumps(refusal(error)))
        raise SystemExit(1) from None
