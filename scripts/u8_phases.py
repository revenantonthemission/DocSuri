"""Step 43's phases of the composed realm tool (`scripts/verify_docsuri_u8.py`).

The runner passes itself in (`runner`), so every phase shares its one lock, run root,
bounded process, JUnit checks and evidence format. Each phase runs under the one 300 s
bound (`PHASE_SECONDS`); an overrun fails it, and nothing here is split, skipped or
excluded to fit.

- `fixtures`: the v2 fixtures, the synthetic v1 dataset record and the production-size
  corpus (`scripts/u8_fixtures.py`, `scripts/u8_corpus.py`);
- `serve`: the served realm (`scripts/serve_docsuri_u8.py`) for a bounded demonstration;
- `browser-*`, `security`, `accessibility`, `accessibility-signed-out`,
  `accessibility-keyboard`, `accessibility-screens`: the workspace build, the served
  realm (for migration and cutover, the cutover stage), and Playwright on the phase's
  specs;
- `restore-paths`: both restores as logins that are not superusers;
- `build-gate`: `scripts/u8_build_workspace.py`;
- `compatibility`: the previous v2 tag's critical journeys, through the tag's own
  frontend, against the candidate's schema; skipped, saying so, while no v2 tag exists.
  It serves the candidate's own app, so a pass shows that the candidate's app passes the
  previous release's journeys on the candidate's schema; serving the previous release's
  own app on the migrated database is built at the second v2 release (L1-60);
- `performance`: the EXPLAIN check on the corpus, 20 concurrent synthetic users reading by
  POST and by GET, NFR8.1–NFR8.5; the host's `read` count checked against the reads its
  users were answered (a lower bound); then, with the served realm stopped, 20 SCRAM
  logins of each of the eleven owner logins timed against 20 ms (NFR8.3), the figure
  counting only where the phase counts;
- `repair-exercise`: the recorded defect in a clean checkout, its failing checks, its
  repair;
- `restart-host`, `restart-database`: NFR8.6's crashed host and crashed PostgreSQL, each
  timed from its relaunch to the first ready answer with every required capability
  observed afresh;
- `frontend`: U8's Vitest lane with coverage;
- `arrangement`: the macOS-only folder with sudo; refuses anywhere else;
- `verification-run`: v1, `restore-paths` and `browser-recovery` before the corpus, the
  corpus to completion, the other journey phases in order, then the VerificationRun;
- `capacity-burst` (Step 114, record-only, run on demand): 20 signed-in users load their
  작업 page together beside 0, 4 and 8 open job streams, three runs of each, with the
  host's gate waits and holds observed. Refusals are its record and never fail it; it
  runs after `verification-run`, because its evidence file makes a later
  `verification-run` on that realm refuse the realm as not fresh (`FRESH_EVIDENCE`).

Every browser test's title starts with its BR10.3 journey identifier (`[J01]` …), so the
VerificationRun reads each journey's result from the phase reports.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import hashlib
import json
import os
import random
import re
import secrets
import subprocess
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST_ROOT = "tests/u8_service_operations_integration"
E2E = "frontend/e2e/u8-complete"
PLAYWRIGHT_CONFIG = "playwright.u8-complete.config.ts"
VITEST_CONFIG = "vitest.u8-complete.config.ts"
PUBLIC_ORIGIN = "https://127.0.0.1:18110"
# The sign-in's entry policy, as the workspace sends it (`modules/accounts/local_http`).
ENTRY_POLICY = {"policyId": "synthetic-local-entry", "revision": "1"}
START_SECONDS = 60
# The journey phases, each with its own specs, in verification order.
BROWSER_SPECS = {
    # Journeys and navigation together ran to 282 s of the 300 s bound, which is never
    # raised: J12 rides with the isolation journeys (the split the phase list allows).
    "browser-journeys": ("journeys.spec.ts",),
    # J09 alone, on the realm's database before the corpus loads (the person's decision
    # of 2026-10-23, "Smaller database"): its backup and restore verification copy the
    # whole database, which at production size passed the bound.
    "browser-recovery": ("recovery.spec.ts",),
    "browser-lifecycle": ("lifecycle.spec.ts",),
    "browser-migration": ("migration.spec.ts",),
    "browser-cutover": ("cutover.spec.ts",),
    "browser-isolation": ("isolation.spec.ts", "navigation.spec.ts"),
    "security": ("security.spec.ts",),
    "accessibility": ("accessibility.spec.ts",),
    # Step 99(h)'s split rule through Step 101(e): `accessibility` peaked at 1,031,192,576 B,
    # above 90% of 1 GiB, so its signed-out and keyboard tests run as a phase of their own.
    "accessibility-signed-out": ("accessibility-signed-out.spec.ts",),
    "accessibility-keyboard": ("accessibility-keyboard.spec.ts",),
    "accessibility-screens": ("accessibility-screens.spec.ts",),
}
STAGED = frozenset({"browser-migration", "browser-cutover"})
V1_PHASES = frozenset({"browser-migration", "browser-cutover"})
# The security phase's backend half: the route inventory, the production headers and
# forged forwarded headers, the sign-in limits, and the cross-site arrival.
SECURITY_TESTS = (
    f"{TEST_ROOT}/integration/test_route_inventory.py",
    f"{TEST_ROOT}/integration/test_boundary.py",
    f"{TEST_ROOT}/integration/test_sign_in_limits.py",
    f"{TEST_ROOT}/integration/test_first_sign_in.py",
)
RESTORE_TESTS = (
    f"{TEST_ROOT}/integration/test_production_restore.py",
    f"{TEST_ROOT}/integration/test_restore_verification.py",
)
# The person's decision of 2026-10-23 ("Smaller database"): the two phases that copy the
# whole database run before the corpus loads; the corpus is then completed, and the other
# journey phases follow in order.
BEFORE_CORPUS = ("restore-paths", "browser-recovery")
AFTER_CORPUS = (
    "browser-journeys", "browser-lifecycle", "browser-migration", "browser-cutover",
    "browser-isolation", "security", "accessibility", "accessibility-signed-out",
    "accessibility-keyboard", "accessibility-screens", "repair-exercise",
    # NFR8.6's crash clauses (Step 95(f)).
    "restart-host", "restart-database",
)
VERIFICATION_ORDER = (*BEFORE_CORPUS, *AFTER_CORPUS)
# Bounded corpus runs the verification run allows before it gives up (each its own 300 s
# phase; "Load over two runs" needed two).
CORPUS_RUNS = 4
# BR10.3's journeys (and BR10.6's accessibility), each with the phase that proves it.
JOURNEYS = {
    "J01": ("sign-in-library-search-paper-research-novelty-export", "browser-journeys"),
    "J02": ("topics-to-digest", "browser-journeys"),
    "J03": ("public-and-private-isolation", "browser-isolation"),
    "J04": ("current-authority", "browser-lifecycle"),
    "J05": ("late-effects", "browser-lifecycle"),
    "J06": ("drafts-switched-off", "browser-journeys"),
    "J07": ("job-lifecycle", "browser-journeys"),
    "J08": ("withdrawal-reactivation-erasure", "browser-lifecycle"),
    "J09": ("backup-and-restore-verification", "browser-recovery"),
    "J10": ("migration-of-the-synthetic-v1", "browser-migration"),
    "J11": ("cutover-procedures", "browser-cutover"),
    "J12": ("navigation-states", "browser-isolation"),
    "J13": ("owner-isolation", "browser-isolation"),
    "J14": ("repair-exercise", "repair-exercise"),
    "A11Y": ("accessibility-of-the-complete-application", "accessibility"),
    "SEC": ("security-boundaries", "security"),
}
TITLE = re.compile(r"\[(J\d\d|A11Y|SEC)\]")
DEFECT = f"{TEST_ROOT}/repair_exercise/defect.patch"
REGRESSION = f"{TEST_ROOT}/repair_exercise/test_stale_capability.py"
# The checks run in a clean checkout, where the realm's owned manifest names another
# repository: the regression module and the navigation suite's database-free check. The
# navigation suite's HTTP checks of the same rule run in the `integration` phase.
REPAIR_CHECKS = (
    REGRESSION,
    (f"{TEST_ROOT}/integration/test_navigation_api.py"
     "::test_navigation_items_follow_the_access_rules_without_a_host"),
)


def now() -> str:
    return dt.datetime.now(dt.UTC).isoformat()


def remaining(started: float, runner) -> float:
    return max(0.01, runner.PHASE_SECONDS - (time.monotonic() - started))


def environment(runner, extra: dict | None = None) -> dict:
    value = runner.child_environment(extra or {})
    value.setdefault("PYTHONPATH", str(ROOT))
    return value


def record(runner, phase: str, evidence: dict) -> dict:
    """The phase's evidence file, its one-line summary, and its refusal on failure."""
    path = runner.RUN / f"{phase}-evidence-{time.time_ns()}.json"
    runner.private_json(path, evidence)
    summary = {key: evidence.get(key) for key in (
        "phase", "exitCode", "tests", "failures", "errors", "skipped", "failureCategory",
        "durationSeconds", "skippedReason", "sourceChangedDuringRun", "missingCaptures")}
    print(json.dumps({key: value for key, value in summary.items() if value is not None}))
    if evidence["exitCode"]:
        raise runner.Refused(f"U8 phase {phase} failed; evidence preserved")
    return {"state": "passed", "phase": phase, "evidence": path.name}


def source_rule_start(runner, *, release: dict | None = None) -> dict:
    """The source rule's identity, taken right after `prepare_phase` (U8 plan Step 95(a)):
    the listed bytes the phase exercises, or, for `run_performance` in a release
    environment, the release's identity (tag and commit), so no git listing runs in the
    installer's release folder."""
    if release is not None:
        return {"release": release}
    return runner.source_identity()


def same_source(before: dict, after: dict) -> bool:
    if "release" in before or "release" in after:
        return before.get("release") == after.get("release")
    return before.get("sha256") == after.get("sha256")


def source_rule_end(runner, before: dict, evidence: dict) -> dict:
    """The evidence's `source` is the identity taken at the start; a different identity
    at the end records `sourceChangedDuringRun` and fails the phase (Step 95(a))."""
    evidence["source"] = before
    after = ({"release": runner.release_identity(ROOT)} if "release" in before
             else runner.source_identity())
    if not same_source(before, after):
        evidence.update(sourceChangedDuringRun=True, exitCode=1)
    return evidence


def run_child(runner, phase: str, args: list[str], started: float, *,
              extra: dict | None = None, report: Path | None = None, **options) -> dict:
    """One bounded child with its JUnit report checked (zero tests, a skip, an error or a
    failure fails it); the result is the evidence's supervision part."""
    log = runner.RUN / f"u8-phase-{phase}-{time.time_ns()}.log"
    failure, supervision = None, {}
    try:
        supervision = runner.bounded_process(args, log, seconds=remaining(started, runner),
                                             environment=environment(runner, extra), **options)
    except (runner.Refused, RuntimeError, OSError, subprocess.SubprocessError) as error:
        failure = type(error).__name__
        supervision = getattr(error, "supervision", {})
    evidence = {"command": args, "exitCode": 1 if failure else supervision.get("exitCode", 1),
                "supervision": supervision, "failureCategory": failure, "log": log.name}
    if report is not None:
        runner.junit_counts(report, evidence)
    return evidence


# --- fixtures -------------------------------------------------------------------------------


def run_fixtures(runner, path: Path, *, corpus_mode: str | None = None) -> dict:
    """The fixtures, in a bounded child of their own. Their record is `fixtures/`, never
    an evidence file, so `verification-run` still finds a fresh environment. The corpus
    mode is the runner's `--corpus` (`load`, or `skip` to stop before the corpus), or
    `only` from the verification run; `fixtures/phase.json` records it."""
    mode = corpus_mode or getattr(runner, "FIXTURES_CORPUS", "load")
    value, _resources = runner.prepare_phase(path)
    started = time.monotonic()
    args = [str(runner.PYTHON), str(ROOT / "scripts/u8_fixtures.py"), "prepare",
            "--environment-file", str(path), "--corpus", mode]
    result = run_child(runner, "fixtures", args, started)
    loaded = not result["exitCode"] and mode != "skip"
    corpus = corpus_state(runner) if loaded else None
    state = {"phase": "fixtures", "runId": value["runId"], "finishedAt": now(),
             "exitCode": result["exitCode"], "supervision": result["supervision"],
             "corpusMode": mode, "corpus": corpus if mode != "skip" else "skipped"}
    from u8_fixtures import write_private

    write_private(runner.RUN / "fixtures" / "phase.json", state)
    print(json.dumps({"phase": "fixtures", "exitCode": result["exitCode"], "corpusMode": mode,
                      "seconds": round(time.monotonic() - started, 1), "corpus": corpus}))
    if result["exitCode"]:
        raise runner.Refused("U8 fixtures failed; their log is preserved")
    if mode == "skip":
        return {"state": "corpus-skipped", "phase": "fixtures"}
    if not corpus["complete"]:
        # The person's decision of 2026-10-23 ("Load over two runs"): run `fixtures` again.
        return {"state": "corpus-incomplete", "phase": "fixtures",
                "papers": corpus["papers"], "target": corpus["target"],
                "remaining": corpus["remaining"]}
    return {"state": "fixtures-ready", "phase": "fixtures", "papers": corpus["papers"]}


def corpus_state(runner) -> dict:
    """The corpus record the fixtures child wrote (`fixtures/corpus.json`)."""
    from backend.local_profile import private_bytes

    value = json.loads(private_bytes(runner.RUN / "fixtures" / "corpus.json"))
    keys = ("papers", "target", "complete", "remaining", "presentAtStart", "importedThisRun",
            "chunksPerPaper", "version")
    return {key: value.get(key) for key in keys}


def require_complete_corpus(runner) -> dict:
    """`performance` and `verification-run` refuse an incomplete corpus (the person's
    decision of 2026-10-23)."""
    path = runner.RUN / "fixtures" / "corpus.json"
    if not path.exists():
        raise runner.Refused("the corpus has not been loaded; run `fixtures`")
    corpus = corpus_state(runner)
    if not corpus["complete"] or corpus["papers"] != corpus["target"]:
        raise runner.Refused(f"the corpus is incomplete ({corpus['papers']} of "
                             f"{corpus['target']} papers); run `fixtures` again")
    return corpus


# --- the served realm and the cutover stage --------------------------------------------------


def serve_command(runner, path: Path, *, staged: bool, observe_gates: bool = False) -> list[str]:
    """The served realm's command (or the cutover stage's); `observe_gates` (Step 114(d),
    the `capacity-burst` phase only) adds `--observe-gates` as its last argument."""
    if staged and observe_gates:
        raise ValueError("the cutover stage observes no gates")
    if staged:
        return [str(runner.PYTHON), "-m",
                "tests.u8_service_operations_integration.cutover_stage",
                "--environment-file", str(path)]
    args = [str(runner.PYTHON), str(ROOT / "scripts/serve_docsuri_u8.py"),
            "--environment-file", str(path)]
    scenario = runner.RUN / "identity-scenario.json"
    if scenario.exists():  # the fixtures' identity stand-in scenario
        args += ["--identity-scenario", str(scenario)]
    if observe_gates:
        args.append("--observe-gates")
    return args


def public_answer(path: str, certificate: Path) -> int | None:
    import ssl
    import urllib.error
    import urllib.request

    context = ssl.create_default_context(cafile=str(certificate))
    try:
        with urllib.request.urlopen(PUBLIC_ORIGIN + path, context=context, timeout=2) as answer:
            return answer.status
    except urllib.error.HTTPError as error:
        return error.code
    except (OSError, ValueError):
        return None


def stage_ready(path: Path) -> bool:
    import socket

    if not path.exists():
        return False
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
            connection.settimeout(2)
            connection.connect(str(path))
            connection.sendall(b'{"word": "ready"}\n')
            return json.loads(connection.recv(4096) or b"{}").get("ok") is True
    except (OSError, ValueError):
        return False


def start_realm(runner, path: Path, log: Path, *, staged: bool, observe_gates: bool = False):
    """The served realm (or the cutover stage), waited for through the public address;
    `observe_gates` is handed to `serve_command`."""
    for port in (runner.APPLICATION_PORT, runner.PUBLIC_PORT, runner.MAINTENANCE_PORT,
                 runner.IDENTITY_PORT):
        runner.require_stopped(port)
    descriptor = os.open(log, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        process = subprocess.Popen(
            serve_command(runner, path, staged=staged, observe_gates=observe_gates),
            cwd=ROOT, env=environment(runner),
            stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.STDOUT,
            start_new_session=True, umask=0o077)
    certificate = runner.RUN / "service-operations-tls.crt"
    deadline = time.monotonic() + START_SECONDS

    def ready() -> bool:
        # The stage answers `ready` on its private socket; the served realm, through the
        # public address.
        if staged:
            return stage_ready(runner.RUN / "cutover-stage.sock")
        return public_answer("/health/live", certificate) == 200

    try:
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise runner.Refused("the served realm exited before it was ready")
            if runner.enforced_bytes(*runner.process_tree_memory(
                    (process.pid,), deadline)) > runner.MAX_RSS:
                raise runner.Refused("the served realm exceeded its startup bounds")
            if ready():
                return process
            time.sleep(0.2)
        raise runner.Refused("the served realm was not ready within 60 seconds")
    except BaseException:
        runner.stop(process)
        raise


def run_serve(runner, path: Path) -> dict:
    """The served realm for its bounded demonstration; reaching the bound is its end."""
    value, resources = runner.prepare_phase(path)
    started = time.monotonic()
    args = serve_command(runner, path, staged=False)
    result = run_child(runner, "serve", args, started, allow_bounded_stop=True)
    reason = result["supervision"].get("reason")
    exit_code = 0 if result["exitCode"] == 0 and reason == "bounded-stop" else 1
    return record(runner, "serve", {
        "phase": "serve", "runId": value["runId"], **result, "exitCode": exit_code,
        "durationSeconds": time.monotonic() - started, "resources": resources,
        "completionVerification": False})


# --- browser phases ---------------------------------------------------------------------------


def build_assets(runner, started: float) -> dict:
    args = [str(runner.PYTHON), str(ROOT / "scripts/u8_build_workspace.py")]
    result = run_child(runner, "build", args, started)
    if result["exitCode"]:
        raise runner.Refused("the workspace build failed")
    return result


PERF = r"\[PERF\]"


def playwright_args(specs: tuple[str, ...], *, perf: bool = False,
                    frontend: Path | None = None) -> list[str]:
    # The child runs from the repository root; the config is named by its full path, and
    # its own paths (testDir, output) resolve beside it. The `[PERF]` measurement runs in
    # the `performance` phase only; every journey phase leaves it out. `frontend` is your
    # checkout's (`--playwright`, the release's performance phase, Step 43): its binary,
    # configuration and specs measure the release's code.
    folder = frontend or ROOT / "frontend"
    if frontend is not None:
        specs = tuple(str(frontend.parent / spec) for spec in specs)
    return [str(folder / "node_modules/.bin/playwright"), "test", "--config",
            str(folder / PLAYWRIGHT_CONFIG), *specs,
            *(("--grep", PERF) if perf else ("--grep-invert", PERF))]


def release_build(runner) -> dict:
    """In a release environment the workspace build is the release's own, downloaded and
    checked at staging (`frontend/dist` with its build manifest); nothing is built."""
    manifest = ROOT / "frontend" / "dist" / ".docsuri-build.json"
    if not manifest.is_file():
        raise runner.Refused("the release's workspace build is missing")
    return {"source": "release-dist", "exitCode": 0,
            "manifestSha256": runner.digest(manifest)}


def run_browser(runner, phase: str, path: Path, *, before: dict | None = None) -> dict:
    """Build, serve (or stage), then Playwright on the phase's specs: one shared bound.
    `before` is the source identity `run_security` took before its backend half."""
    if phase in V1_PHASES and not runner.v1_serving():
        runner.run_v1("v1-up", path)
    value, resources = runner.prepare_phase(path)
    specs = BROWSER_SPECS[phase]
    runner.require_test_paths(tuple(f"{E2E}/{spec}" for spec in specs))
    report = runner.RUN / f"{phase}.xml"
    preserved = runner.preserve_prior_report(phase)
    before = before if before is not None else runner.source_identity()
    started = time.monotonic()
    evidence = {"phase": phase, "runId": value["runId"], "specs": list(specs),
                "resources": resources, "preservedEvidence": preserved, "source": before}
    companion, companion_log = None, runner.RUN / f"u8-realm-{phase}-{time.time_ns()}.log"
    try:
        evidence["build"] = build_assets(runner, started)
        companion = start_realm(runner, path, companion_log, staged=phase in STAGED)
        result = run_child(
            runner, phase, playwright_args(specs), started, report=report,
            extra={"PLAYWRIGHT_JUNIT_OUTPUT_FILE": str(report),
                   "NODE_OPTIONS": "--max-old-space-size=128 --max-semi-space-size=8"},
            companion=companion, companion_log=companion_log)
        evidence.update(result)
    except (runner.Refused, OSError) as error:
        evidence.update(exitCode=1, failureCategory=type(error).__name__,
                        failureReason=str(error) if isinstance(error, runner.Refused) else None)
    finally:
        if companion is not None:
            runner.stop(companion)
    evidence["realmLog"] = companion_log.name
    evidence["keptEvidence"] = keep_browser_evidence(runner, phase)
    evidence["captures"] = browser_captures(runner, evidence["keptEvidence"])
    missing = missing_captures(phase, evidence["captures"])
    if missing:
        evidence.update(missingCaptures=missing, exitCode=1)
    evidence["durationSeconds"] = time.monotonic() - started
    if runner.source_identity()["sha256"] != before["sha256"]:
        evidence.update(sourceChangedDuringRun=True, exitCode=1)
    return record(runner, phase, evidence)


BROWSER_OUTPUT = "browser-evidence"
KEPT_EVIDENCE = "kept-evidence"
# The 320 px captures each phase must keep (U8 plan Step 95(i)): each entry is added by the
# step whose spec first saves those captures (Steps 100(i), 101(a), 101(d), 102(b),
# 102(c), 133(d)), so no phase fails for a capture its spec does not take yet.
CAPTURES: dict[str, tuple[str, ...]] = {
    "security": ("email-link-fresh-browser",),
    "browser-migration": ("consent-step", "admin-mfa-prompt", "reset-required"),
    "browser-cutover": ("maintenance-notice",),
    # Step 101(a)'s 17 screens over the two phases of its split (Step 101(e)).
    "accessibility": (
        "search", "paper", "library", "research", "novelty", "jobs", "topics", "export",
        "settings", "usage", "account", "operations", "recovery-dialog",
    ),
    "accessibility-signed-out": ("entry", "privacy", "terms", "callback-cancelled"),
    "accessibility-screens": (
        "navigation-loading", "navigation-error", "navigation-disabled-entry",
        "navigation-menu-guest", "navigation-menu-member", "entry-maintenance-banner",
        "callback-pending", "provider-unavailable", "provider-start-limit",
        "moved-notice-open", "mfa-form", "proof-password-reset", "proof-verify-email",
        "proof-reactivate", "proof-email-change", "lifecycle-retained", "research-limit",
        "maintenance-18111", "privacy-18111", "terms-18111", "callback-maintenance-banner",
    ),
}
CAPTURE_NAME = re.compile(r"320-([a-z0-9]+(?:-[a-z0-9]+)*)\.png")


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def browser_captures(runner, kept: str | None) -> list[dict]:
    """Every `320-<screen>.png` under the phase's kept folder: the screen, its path
    relative to the run root and its SHA-256."""
    if kept is None:
        return []
    folder = runner.RUN / kept
    found = []
    for item in sorted(folder.rglob("320-*.png")):
        match = CAPTURE_NAME.fullmatch(item.name)
        if match is None or item.is_symlink() or not item.is_file():
            continue
        found.append({"screen": match.group(1),
                      "path": str(item.relative_to(runner.RUN)),
                      "sha256": file_sha256(item)})
    return found


def missing_captures(phase: str, captures: list[dict]) -> list[str]:
    """The screens the phase's `CAPTURES` entry lists that have no capture."""
    taken = {item["screen"] for item in captures}
    return [screen for screen in CAPTURES.get(phase, ()) if screen not in taken]


def keep_browser_evidence(runner, phase: str) -> str | None:
    """The phase's Playwright output (error contexts, traces, screenshots), moved out of
    `browser-evidence/`, which the next Playwright run empties, to
    `kept-evidence/<phase>-<ns>/` in the run root (the coordinator's instruction of
    2026-10-24). Nothing is kept when the phase left no output."""
    source = runner.RUN / BROWSER_OUTPUT
    if not source.is_dir() or source.is_symlink() or not any(source.iterdir()):
        return None
    kept = runner.RUN / KEPT_EVIDENCE
    kept.mkdir(mode=0o700, exist_ok=True)
    if kept.is_symlink() or not kept.is_dir():
        raise runner.Refused("the kept evidence folder is not a private folder")
    target = kept / f"{phase}-{time.time_ns()}"
    os.rename(source, target)
    return str(target.relative_to(runner.RUN))


def run_pytest_part(runner, phase: str, tests: tuple[str, ...], started: float) -> dict:
    report = runner.RUN / f"{phase}-backend.xml"
    runner.require_test_paths(tests)
    args = [str(runner.PYTHON), "-m", "pytest", "-c", runner.PYTEST_INI, *tests, "-q",
            "--tb=short", "--maxfail=1", f"--junitxml={report}"]
    return run_child(runner, phase, args, started, report=report)


def run_security(runner, path: Path) -> dict:
    """The backend's security checks, then the browser's (cross-site arrival, a provider
    error return, an email link opened in a fresh browser)."""
    value, _resources = runner.prepare_phase(path)
    before = runner.source_identity()
    started = time.monotonic()
    backend = run_pytest_part(runner, "security", SECURITY_TESTS, started)
    if backend["exitCode"]:
        return record(runner, "security", source_rule_end(runner, before, {
            "phase": "security", "runId": value["runId"], "backend": backend, "exitCode": 1,
            "durationSeconds": time.monotonic() - started}))
    return run_browser(runner, "security", path, before=before)


def run_restore_paths(runner, path: Path) -> dict:
    value, resources = runner.prepare_phase(path)
    source = source_rule_start(runner)
    started = time.monotonic()
    result = run_pytest_part(runner, "restore-paths", RESTORE_TESTS, started)
    return record(runner, "restore-paths", source_rule_end(runner, source, {
        "phase": "restore-paths", "runId": value["runId"], **result,
        "durationSeconds": time.monotonic() - started, "resources": resources,
        "logins": ["docsuri_restore", "docsuri_scheduler"], "superuser": False}))


# --- build gate, compatibility, frontend, arrangement -----------------------------------------


def run_build_gate(runner, path: Path) -> dict:
    value, _resources = runner.prepare_phase(path)
    source = source_rule_start(runner)
    started = time.monotonic()
    result = run_child(runner, "build-gate", [str(runner.PYTHON),
                                              str(ROOT / "scripts/u8_build_workspace.py")],
                       started)
    built = None
    try:
        built = json.loads(runner.private_bytes(runner.RUN / result["log"]).decode()
                           .strip().splitlines()[-1])
    except (OSError, ValueError, IndexError):
        result["exitCode"] = 1
    return record(runner, "build-gate", source_rule_end(runner, source, {
        "phase": "build-gate", "runId": value["runId"], **result, "build": built,
        "durationSeconds": time.monotonic() - started}))


def previous_tag() -> str | None:
    """The newest v2 tag that is not on the candidate commit: a push to `main` is tagged by
    the release job, often before this checkout, and the candidate is never compared with
    its own tag (Step 95(b), L1-60, "the previous release's own journeys")."""
    completed = subprocess.run(["git", "-C", str(ROOT), "tag", "--list", "v2.*",
                                "--no-contains", "HEAD", "--sort=-v:refname"],
                               capture_output=True, text=True,
                               timeout=30, check=True)
    tags = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
    return tags[0] if tags else None


OFFLINE_INSTALL_FAILED = "the previous release's frontend could not be installed offline"


def run_compatibility(runner, path: Path) -> dict:
    """The previous v2 tag's critical journeys (its own `journeys.spec.ts`, run through
    its own frontend from a worktree at the tag, installed offline from the tag's frozen
    lockfile) against the candidate's schema; with no v2 tag yet, skipped.

    What a pass shows (L1-60, "Fix the path and hand on the rest"): the phase serves the
    candidate's own app (`start_realm` runs this checkout's `serve_docsuri_u8.py`), so a
    pass shows that the candidate's app passes the previous release's own journeys on the
    candidate's schema. Serving the previous release's own app on the migrated database
    (cicd-pipeline C2 and § 3.2) is built at the second v2 release, with the packages the
    tag's lockfile names but the candidate's offline store lacks, and the tag's own
    Playwright Chromium."""
    value, _resources = runner.prepare_phase(path)
    tag = previous_tag()
    if tag is None:
        evidence = {"phase": "compatibility", "runId": value["runId"], "exitCode": 0,
                    "skipped": True, "skippedReason": "no v2 tag exists yet",
                    "checkedAt": now()}
        print("compatibility skipped: no v2 tag exists yet")
        return record(runner, "compatibility", evidence)
    source = source_rule_start(runner)
    started = time.monotonic()
    tree = Path.home() / ".docsuri-u8" / f"compatibility-{tag}"
    if not tree.exists():
        subprocess.run(["git", "-C", str(ROOT), "worktree", "add", "--detach", str(tree), tag],
                       check=True, capture_output=True, timeout=120)
    spec = f"{E2E}/journeys.spec.ts"
    # L1-49: the spec is checked against the tag worktree's own listing, before any child.
    runner.require_test_paths((spec,), root=tree)
    report = runner.RUN / "compatibility.xml"
    evidence = {"phase": "compatibility", "runId": value["runId"], "previousTag": tag,
                "specs": [spec]}
    install = run_child(runner, "compatibility-install", [
        "corepack", "pnpm@9.15.9", "--dir", str(tree / "frontend"), "install",
        "--frozen-lockfile", "--offline", "--ignore-scripts"], started)
    evidence["install"] = install
    if install["exitCode"]:
        evidence.update(exitCode=1, failureCategory="failed-prerequisite",
                        failureReason=OFFLINE_INSTALL_FAILED,
                        durationSeconds=time.monotonic() - started)
        return record(runner, "compatibility", source_rule_end(runner, source, evidence))
    companion_log = runner.RUN / f"u8-realm-compatibility-{time.time_ns()}.log"
    companion = start_realm(runner, path, companion_log, staged=False)
    try:
        result = run_child(runner, "compatibility",
                           playwright_args((spec,), frontend=tree / "frontend"), started,
                           report=report, extra={"PLAYWRIGHT_JUNIT_OUTPUT_FILE": str(report)},
                           companion=companion, companion_log=companion_log)
    finally:
        runner.stop(companion)
    evidence.update(result, durationSeconds=time.monotonic() - started)
    return record(runner, "compatibility", source_rule_end(runner, source, evidence))


def run_frontend(runner, path: Path) -> dict:
    value, _resources = runner.prepare_phase(path)
    # Step 95(b): an ignored test file could pass here and be missing from a fresh checkout.
    runner.require_test_paths(("frontend/test/u8-complete", f"frontend/{VITEST_CONFIG}"))
    source = source_rule_start(runner)
    started = time.monotonic()
    report = runner.RUN / "frontend.xml"
    args = ["corepack", "pnpm@9.15.9", "--dir", "frontend", "exec", "vitest", "run",
            "--config", VITEST_CONFIG, "--coverage", "--reporter=junit",
            f"--outputFile={report}"]
    result = run_child(runner, "frontend", args, started, report=report)
    return record(runner, "frontend", source_rule_end(runner, source, {
        "phase": "frontend", "runId": value["runId"], **result,
        "durationSeconds": time.monotonic() - started}))


def run_arrangement(runner, path: Path) -> dict:
    """The macOS-only folder, with sudo, under `DOCSURI_U8_ARRANGEMENT=1`, then the
    `.coveragerc.u8-macos` report at its 80% floor. Refused anywhere but macOS."""
    if sys.platform != "darwin":
        raise runner.Refused("the arrangement phase runs only on macOS")
    value, _resources = runner.prepare_phase(path)
    source = source_rule_start(runner)
    started = time.monotonic()
    report = runner.RUN / "arrangement.xml"
    coverage = runner.RUN / ".coverage-u8-macos"
    tests = f"{TEST_ROOT}/arrangement"
    runner.require_test_paths((tests,))
    # Step 95(e): the root child writes coverage's data in the run root and no bytecode
    # or pytest cache in the tree, so nothing it leaves is root-owned outside the run.
    args = ["sudo", "-n", "env", "DOCSURI_U8_ARRANGEMENT=1",
            f"DOCSURI_U8_ENVIRONMENT_FILE={path}", f"PYTHONPATH={ROOT}",
            f"COVERAGE_FILE={coverage}", "PYTHONDONTWRITEBYTECODE=1",
            str(runner.PYTHON), "-m", "pytest", "-c", runner.PYTEST_INI, tests, "-q",
            "--tb=short", "--maxfail=1", "-p", "no:cacheprovider", f"--junitxml={report}",
            "--cov", "--cov-config=backend/.coveragerc.u8-macos", "--cov-report=term-missing",
            "--cov-fail-under=80"]
    result = run_child(runner, "arrangement", args, started)
    owned = take_report_ownership(runner, (report, coverage))
    if owned is not None:
        result.update(exitCode=1, failureCategory="report-owner-unchanged", chown=owned)
    runner.junit_counts(report, result)
    evidence = {"phase": "arrangement", "runId": value["runId"], **result,
                "durationSeconds": time.monotonic() - started}
    return record(runner, "arrangement", source_rule_end(runner, source, evidence))


def take_report_ownership(runner, paths: tuple[Path, ...]) -> dict | None:
    """One fixed `sudo -n chown <uid>` of the root child's report and coverage data, each
    only when `lstat` shows a regular file, so no link is followed (Step 95(e)). None when
    it succeeded or nothing was written; otherwise the chown's record, never raised."""
    import stat

    files = []
    for item in paths:
        try:
            if stat.S_ISREG(item.lstat().st_mode):
                files.append(str(item))
        except FileNotFoundError:
            continue
    if not files:
        return None
    try:
        completed = runner.command(["sudo", "-n", "/usr/sbin/chown", str(os.getuid()), *files])
    except (runner.Refused, OSError, subprocess.SubprocessError) as error:
        return {"files": files, "exitCode": None, "error": type(error).__name__}
    if completed.returncode:
        return {"files": files, "exitCode": completed.returncode}
    return None


# --- performance --------------------------------------------------------------------------------

# NFR8.1–NFR8.5 (performance-requirements.md), each in milliseconds at the 95th percentile.
TARGETS_MS = {"health": 200, "first-load": 2000, "navigation": 1000, "api-read": 500,
              "search": 3000, "accept": 1000}
USERS = 20
LOAD_SECONDS = 60
# The person's decision of 2026-10-24 ("Pace users like people"): each user acts about
# every 5 seconds, so twenty make about 4 requests a second.
ACT_SECONDS = 5.0
READINESS_SAMPLE_SECONDS = 1.0
# The members no journey consumes (memberC is erased by J09, memberD by J08), so the load
# measures the service, not a fixture account the verification run has already ended.
LOAD_ACCOUNTS = ("memberA", "memberB", "memberE")
# L2-3: a read and a search in turn, half the reads the GET session read every page sends
# when it mounts, both reads timed as `api-read`.
LOAD_TURNS = ("settings-read", "search", "session-read", "search")


def load_request(kind: str, search: dict) -> tuple[str, str, dict | None]:
    """One user turn's `(method, path, body)`."""
    if kind == "settings-read":
        return "POST", "/api/v2/c03/settings-read", {}
    if kind == "session-read":
        return "GET", "/api/v2/session", None
    if kind == "search":
        return "POST", "/api/v2/c05/search", search
    raise ValueError(f"unknown load turn: {kind}")
# The production arrangement's planner-relevant settings (arrangement/templates/
# postgresql.conf); every other planner setting is PostgreSQL's default there too.
PLANNER_SETTINGS = ("work_mem", "random_page_cost", "effective_cache_size", "seq_page_cost",
                    "enable_seqscan", "enable_indexscan", "enable_bitmapscan")


def production_planner() -> dict[str, str]:
    template = (ROOT / "ops/src/docsuri_ops/arrangement/templates/postgresql.conf").read_text()
    found = {}
    for line in template.splitlines():
        match = re.match(r"\s*([a-z_]+)\s*=\s*('?)([^'#]*)\2", line)
        if match and match.group(1) in PLANNER_SETTINGS:
            found[match.group(1)] = match.group(3).strip()
    return found


def plan_uses(plan: object, index: str) -> bool:
    if isinstance(plan, dict):
        if plan.get("Index Name") == index:
            return True
        return any(plan_uses(item, index) for item in plan.values())
    if isinstance(plan, list):
        return any(plan_uses(item, index) for item in plan)
    return False


def explain_check(connect, *, query: str = "attention transformer retrieval") -> dict:
    """The decision of 2026-10-22 ("Force it in the tests"): on the production-size
    corpus, with production's planner settings, both queries are planned and both plans
    are recorded, with whether each uses its index (`meaningUsesHnsw` for the HNSW
    index, `wordsUsesGin` for the GIN index). The plans are recorded, not enforced: the
    performance phase fails on neither answer."""
    from backend.modules.discovery.u8_search import (
        EF_SEARCH,
        ELIGIBLE_SQL,
        MEANING_LIMIT,
        MEANING_SQL,
        WORDS_LIMIT,
        WORDS_SQL,
        StandinEmbeddings,
        _vector_literal,
    )

    settings = production_planner()
    vector = _vector_literal(StandinEmbeddings().embed_query(query))
    with connect() as conn, conn.transaction():
        for name, value in settings.items():
            conn.execute(f"SET LOCAL {name} = '{value}'")
        conn.execute(f"SET LOCAL hnsw.ef_search = {int(EF_SEARCH)}")
        conn.execute("SET LOCAL hnsw.iterative_scan = relaxed_order")
        shown = {name: conn.execute(f"SHOW {name}").fetchone()[0]
                 for name in (*PLANNER_SETTINGS, "shared_buffers", "hnsw.ef_search")}
        chunks = conn.execute("SELECT count(*) FROM corpus.projection WHERE "
                              "embedding_vector IS NOT NULL").fetchone()[0]
        # The eligible versions, read as the production query reads them first.
        eligible = list(conn.execute(ELIGIBLE_SQL).fetchone()[0])
        meaning = conn.execute("EXPLAIN (FORMAT JSON) " + MEANING_SQL,
                               {"vector": vector, "limit": MEANING_LIMIT,
                                "eligible": eligible}).fetchone()[0]
        words = conn.execute("EXPLAIN (FORMAT JSON) " + WORDS_SQL,
                             {"text": query, "limit": WORDS_LIMIT}).fetchone()[0]
    return {"settings": shown, "fromTemplate": settings, "embeddedChunks": chunks,
            "meaningUsesHnsw": plan_uses(meaning, "projection_embedding_hnsw"),
            "wordsUsesGin": plan_uses(words, "version_lexical_all"),
            "meaningPlan": meaning, "wordsPlan": words}


# Q5 as the person corrected it on 2026-11-22 (L4-2 (a)): a single-precision value is
# 4,100 B and the HNSW index takes one 8 KiB page a chunk and one page more, so vectors
# plus index are 12,292 B a chunk plus 8,192 B (737,528,192 B at 60,000 chunks), and the
# phase fails past 105% of that (774,404,601 B at 60,000 chunks).
VECTOR_BYTES_PER_CHUNK = 12_292
VECTOR_INDEX_EXTRA_BYTES = 8_192
VECTOR_TOLERANCE_PERCENT = 105
VECTOR_DESIGN_CHUNKS = 60_000
# One read-only statement: the chunks that hold a vector, the vectors' own bytes, the
# HNSW index, the kept double-precision array's own bytes, the table on disk with its
# out-of-line storage, and the database and the write-ahead log as A10 counts them.
VECTOR_STORAGE = """
SELECT (SELECT count(*) FROM corpus.projection WHERE embedding_vector IS NOT NULL),
       (SELECT coalesce(sum(pg_column_size(embedding_vector)), 0) FROM corpus.projection),
       pg_relation_size('corpus.projection_embedding_hnsw'),
       (SELECT coalesce(sum(pg_column_size(embedding)), 0) FROM corpus.projection),
       pg_table_size('corpus.projection'),
       footprint.database_bytes, footprint.wal_bytes
  FROM operations.capacity_footprint() AS footprint
"""
VECTOR_FIGURES = ("chunks", "vectorBytes", "indexBytes", "arrayBytes", "tableBytes",
                  "databaseBytes", "walBytes")


def vector_storage(connect) -> dict:
    """Vector storage as the measured database holds it (Q5, NFR8.13), read at its own
    source in one statement. The figures do not depend on load or machine."""
    with connect() as conn:
        row = conn.execute(VECTOR_STORAGE).fetchone()
    return {name: int(value) for name, value in zip(VECTOR_FIGURES, row, strict=True)}


def vector_storage_check(figures: dict, policy) -> dict:
    """The check of `vector_storage`'s figures, a pure function. `failedChecks` holds
    `vector-storage-past-its-figure` when vectors plus index pass 105% of 12,292 B a
    chunk plus 8,192 B, and `footprint-past-its-budget` when the database plus the
    write-ahead log pass the footprint budget (NFR8.13). Any chunk count is judged per
    chunk; `atDesignChunks` marks whether it is exactly the 60,000 Q5 is stated at."""
    used = figures["vectorBytes"] + figures["indexBytes"]
    figure = figures["chunks"] * VECTOR_BYTES_PER_CHUNK + VECTOR_INDEX_EXTRA_BYTES
    footprint = figures["databaseBytes"] + figures["walBytes"]
    failed = []
    if used * 100 > figure * VECTOR_TOLERANCE_PERCENT:
        failed.append("vector-storage-past-its-figure")
    if footprint > policy.footprint_budget_bytes:
        failed.append("footprint-past-its-budget")
    return {"vectorsAndIndexBytes": used,
            "boundBytes": figure * VECTOR_TOLERANCE_PERCENT // 100,
            "footprintBytes": footprint, "budgetBytes": policy.footprint_budget_bytes,
            "atDesignChunks": figures["chunks"] == VECTOR_DESIGN_CHUNKS,
            "failedChecks": failed}


def percentile(values: list[float], fraction: float = 0.95) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round(fraction * (len(ordered) - 1)))]


# performance-design § 2.3 and L2-5: 20 SCRAM logins of each owner login, within 20 s,
# with the served realm stopped; a p95 past 20 ms is where a pool per owner login is
# reconsidered (a figure for the person, never a target).
SCRAM_RECONSIDER_MS = 20.0
SCRAM_LOGINS_PER_OWNER = 20
SCRAM_SECONDS = 20


def scram_summary(samples: list[tuple[str, float]], failures: dict[str, int], *,
                  planned: int, stopped_early: bool) -> dict:
    """The SCRAM logins' figures, a pure function: `samples` are `(owner, milliseconds)`
    in the order taken, `failures` counts by exception type name. Every login counts, the
    first included: a slow first login is a finding to explain, never a cold start to set
    aside (project.md, Testing Posture)."""
    values = [milliseconds for _, milliseconds in samples]
    per_owner: dict[str, int] = {}
    for owner, _ in samples:
        per_owner[owner] = per_owner.get(owner, 0) + 1
    p95 = percentile(values)
    return {"planned": planned, "logins": len(values),
            "failedLogins": sum(failures.values()), "failures": dict(failures),
            "perOwner": per_owner, "firstMs": values[0] if values else None,
            "p50Ms": percentile(values, 0.5), "p95Ms": p95,
            "maxMs": max(values) if values else None, "boundMs": SCRAM_RECONSIDER_MS,
            "reconsiderPool": p95 is not None and p95 > SCRAM_RECONSIDER_MS,
            "stoppedEarly": stopped_early, "measured": bool(values)}


def scram_logins(source, *, per_owner: int = SCRAM_LOGINS_PER_OWNER,
                 seconds: float = SCRAM_SECONDS, clock=time.monotonic) -> dict:
    """NFR8.3's SCRAM login cost (L2-5): `per_owner` logins of each owner login, taken in
    turn through each owner's own pool by `CompleteTransactions.login_seconds`, starting
    none once `seconds` have passed. `source` is the realm's environment file or a loaded
    profile. A failed login is counted by its exception type's name only, never its
    message, so no address or port is kept (NFR3.9); a refused realm (`ValueError`) fails
    the phase as a failed prerequisite."""
    import psycopg

    from backend.local_profile import LocalProfile
    from backend.transactions import REQUIRE_AUTH
    from backend.u8_transactions import CompleteTransactions

    profile = (LocalProfile.load(Path(source)) if isinstance(source, (str, Path))
               else source)
    transactions = CompleteTransactions(profile, process="maintenance")
    try:
        owners = transactions.owners
        planned = per_owner * len(owners)
        samples: list[tuple[str, float]] = []
        failures: dict[str, int] = {}
        start = clock()
        taken = 0
        stopped_early = False
        while taken < planned:
            if clock() >= start + seconds:
                stopped_early = True
                break
            owner = owners[taken % len(owners)]
            taken += 1
            try:
                samples.append((owner, transactions.login_seconds(owner) * 1000))
            except psycopg.Error as error:
                name = type(error).__name__
                failures[name] = failures.get(name, 0) + 1
    finally:
        transactions.close()
    return {**scram_summary(samples, failures, planned=planned, stopped_early=stopped_early),
            "owners": list(owners), "requireAuth": REQUIRE_AUTH}


def load(runner, fixtures: dict, search_body: dict | None, *, seconds: float,
         sample_memory=None) -> dict:
    """20 concurrent synthetic users through the public address, each signed in as one of
    the members: the local health route, signed-in reads by POST (the settings read) and
    by GET (the session read every page sends when it mounts) and searches (the search
    request as the page sends it), each timed client-side; the host times them too, and
    `run_performance` compares the host's `read` count with the reads answered here (a
    lower bound, `read_class_check`). With
    `sample_memory`, the served realm's memory is watched beside them (`memory`, NFR8.7;
    null without a sampler)."""
    import asyncio
    import ssl

    import httpx

    context = ssl.create_default_context(cafile=str(runner.RUN / "service-operations-tls.crt"))
    timings: dict[str, list[float]] = {name: [] for name in ("health", "api-read", "search")}
    refusals: dict[str, int] = {}
    accounts = [fixtures["accounts"][key] for key in LOAD_ACCOUNTS]
    readiness: dict[str, object] = {"samples": 0, "notReady": 0, "admissionClosed": 0,
                                    "missing": {}, "unanswered": 0}
    search = search_body or {"query": {"query": "attention transformer"}, "page": {}}

    def headers(csrf: str | None) -> dict:
        return {"origin": PUBLIC_ORIGIN, "x-csrf-token": csrf or "",
                "idempotency-key": str(uuid.uuid4())}

    async def signed_in(client, account: dict) -> str | None:
        """One sign-in per account, its session shared by that account's users: twenty
        sign-ins at once would meet D2's sign-in limits, which are not what is measured."""
        csrf = (await client.get("/api/v2/session")).json().get("csrfToken")
        signed = await client.post("/api/v2/c02/access-login", json={
            "email": account["email"], "password": account["password"],
            "policyRef": ENTRY_POLICY}, headers=headers(csrf))
        if signed.status_code != 200:
            refusals[f"sign-in:{signed.status_code}"] = refusals.get(
                f"sign-in:{signed.status_code}", 0) + 1
            return None
        return (await client.get("/api/v2/session")).json().get("csrfToken")

    sent = {kind: 0 for kind in dict.fromkeys(LOAD_TURNS)}

    async def timed(name: str, call) -> None:
        """One request, timed client-side; a refusal is counted by its status and fixed
        code, never its content."""
        begun = time.monotonic()
        try:
            answer = await call()
        except httpx.HTTPError as error:
            # A refused or timed-out connection is a refusal, counted by kind.
            key = f"{name}:{type(error).__name__}"
            refusals[key] = refusals.get(key, 0) + 1
            return
        elapsed = (time.monotonic() - begun) * 1000
        if answer.status_code < 400:
            timings[name].append(elapsed)
            return
        try:
            value = answer.json()
            code = (f"{str(value.get('code', ''))[:40]}:"
                    f"{str(value.get('messageKey', ''))[:60]}")
        except (ValueError, AttributeError):
            code = ""
        key = f"{name}:{answer.status_code}:{code}"
        refusals[key] = refusals.get(key, 0) + 1

    async def user(index: int, client, csrf: str) -> None:
        """One person (the person's decision of 2026-10-24, "Pace users like people"):
        an action about every `ACT_SECONDS`, a read and a search in turn (`LOAD_TURNS`:
        the POST settings read, then after a search the GET session read, as `signed_in`
        reads the session, with no body and no headers). The twenty start spread over one
        period, so together they make about USERS / ACT_SECONDS requests a second rather
        than bursts."""
        await asyncio.sleep(index * ACT_SECONDS / USERS)
        deadline = time.monotonic() + seconds
        turn = index
        while time.monotonic() < deadline:
            begun = time.monotonic()
            kind = LOAD_TURNS[turn % len(LOAD_TURNS)]
            method, path, body = load_request(kind, search)
            name = "search" if kind == "search" else "api-read"
            if method == "GET":
                await timed(name, lambda path=path: client.get(path))
            else:
                await timed(name, lambda path=path, body=body: client.post(
                    path, json=body, headers=headers(csrf)))
            sent[kind] += 1
            turn += 1
            await asyncio.sleep(max(0.0, ACT_SECONDS - (time.monotonic() - begun)))

    async def watch_readiness(stop: asyncio.Event) -> None:
        """The host's own readiness while the load runs (`/health/ready`): whether it
        marked itself not ready, with the capabilities it named, and whether its capacity
        admission was closed. A closed admission refuses every normal request with the
        same `capacity.exhausted` key the eight-slot limit uses, so this is what tells
        the two apart."""
        async with httpx.AsyncClient(base_url="http://127.0.0.1:18109", timeout=2) as local:
            while not stop.is_set():
                # NFR8.1's local health route, as a monitor reads it: a probe beside the
                # users, not one of their requests.
                await timed("health", lambda: local.get("/health/live"))
                try:
                    report = (await local.get("/health/ready")).json()
                except (httpx.HTTPError, ValueError):
                    readiness["unanswered"] += 1
                else:
                    readiness["samples"] += 1
                    if not report.get("ready"):
                        readiness["notReady"] += 1
                    if report.get("admission") == "closed":
                        readiness["admissionClosed"] += 1
                    for name in report.get("missing") or ():
                        missing = readiness["missing"]
                        missing[name] = missing.get(name, 0) + 1
                try:
                    await asyncio.wait_for(stop.wait(), READINESS_SAMPLE_SECONDS)
                except TimeoutError:
                    pass

    memory: dict[str, object] = {"record": None}

    async def everyone() -> None:
        stop = asyncio.Event()
        watcher = asyncio.create_task(watch_readiness(stop))
        memory_watch = (asyncio.create_task(
            watch_memory(sample_memory, stop, every=READINESS_SAMPLE_SECONDS))
            if sample_memory is not None else None)
        try:
            await load_users()
        finally:
            stop.set()
            await watcher
            if memory_watch is not None:
                memory["record"] = await memory_watch

    async def load_users() -> None:
        clients = [httpx.AsyncClient(base_url=PUBLIC_ORIGIN, verify=context, timeout=15)
                   for _ in accounts]
        try:
            sessions = []
            for client, account in zip(clients, accounts, strict=True):
                try:
                    sessions.append(await signed_in(client, account))
                except httpx.HTTPError as error:
                    key = f"sign-in:{type(error).__name__}"
                    refusals[key] = refusals.get(key, 0) + 1
                    sessions.append(None)
            ready = [(client, csrf) for client, csrf in zip(clients, sessions, strict=True)
                     if csrf is not None]
            if ready:
                await asyncio.gather(*(user(index, *ready[index % len(ready)])
                                       for index in range(USERS)))
        finally:
            for client in clients:
                await client.aclose()

    begun = time.monotonic()
    asyncio.run(everyone())
    elapsed = max(time.monotonic() - begun, 1e-6)
    return {"users": USERS, "seconds": seconds, "actSeconds": ACT_SECONDS,
            "p95Ms": {name: percentile(values) for name, values in timings.items()},
            "samples": {name: len(values) for name, values in timings.items()},
            "refusals": refusals, "readiness": readiness, "memory": memory["record"],
            # Each kind the users sent (L2-3), and their own requests a second, the
            # test's rate set beside v1's.
            "sent": dict(sent),
            "requestsPerSecond": round(sum(sent.values()) / elapsed, 2)}


def run_performance(runner, path: Path) -> dict:
    """NFR8.1–NFR8.5 with 20 concurrent synthetic users on the production-size corpus,
    reading by POST and by GET, and the EXPLAIN check. The host's `read` count is compared
    with the reads its users were answered, a lower bound (L2-3); then, with the served
    realm stopped, 20 SCRAM logins of each of the eleven owner logins are timed and
    recorded against 20 ms (NFR8.3, L2-5). Its result counts only when the install's step
    3 runs it from `releases/<tag>/`; anywhere else it is recorded with `counts: false`."""
    value, resources = runner.prepare_phase(path)
    corpus = require_complete_corpus(runner)
    release = runner.release_identity(ROOT)
    source = source_rule_start(runner, release=release)
    playwright_frontend = getattr(runner, "PLAYWRIGHT_FRONTEND", None)
    # Step 95(b): the spec against this tree's listing, or in a release environment the
    # `--playwright` checkout's own, before the EXPLAIN check, the backup and the build.
    runner.require_test_paths(
        (f"{E2E}/navigation.spec.ts",),
        root=playwright_frontend.parent if release is not None and playwright_frontend
        else None)
    started = time.monotonic()
    fixtures = json.loads(runner.private_bytes(runner.RUN / "fixtures" / "browser.json"))
    evidence = {"phase": "performance", "runId": value["runId"], "resources": resources,
                "corpus": corpus,
                "counts": ROOT.parent.name == "releases", "targetsMs": TARGETS_MS}
    explained = explain_check(lambda: runner.connect_admin(value))
    evidence["explain"] = explained
    # Q5 and NFR8.13 (L4-2 (a)): vector storage read at its own source and checked.
    from backend.u8_policy import PRODUCTION_OPERATIONS

    storage = vector_storage(lambda: runner.connect_admin(value))
    evidence["vectorStorage"] = {**storage,
                                 **vector_storage_check(storage, PRODUCTION_OPERATIONS)}
    # NFR8.11 (L1-59): the versions the measurement ran on; nothing is judged.
    evidence["versions"] = measured_versions(lambda: runner.connect_admin(value),
                                             release=release)
    # The person's decision of 2026-10-23: one backup of the production-size database,
    # its duration against the backup protocol's deadline in the inventory.
    evidence["backup"] = measure_backup(runner)
    released = release is not None
    evidence["build"] = release_build(runner) if released else build_assets(runner, started)
    measured = runner.RUN / "perf-browser.json"
    measured.unlink(missing_ok=True)
    companion_log = runner.RUN / f"u8-realm-performance-{time.time_ns()}.log"
    companion = start_realm(runner, path, companion_log, staged=False)
    offsets: dict[str, int] = {}
    try:
        # NFR8.2 and NFR8.5 from a real browser first; its search request's shape is what
        # the 20 users then send.
        browser = run_child(runner, "performance-browser",
                            playwright_args((f"{E2E}/navigation.spec.ts",), perf=True,
                                            frontend=playwright_frontend),
                            started, report=runner.RUN / "performance-browser.xml",
                            extra={"PLAYWRIGHT_JUNIT_OUTPUT_FILE":
                                   str(runner.RUN / "performance-browser.xml")},
                            companion=companion, companion_log=companion_log)
        evidence["browser"] = browser
        timings = json.loads(runner.private_bytes(measured)) if measured.exists() else {}
        # The host flushes its current window when it stops, so the load's windows are
        # the lines written from here on.
        offsets = latency_offsets(runner.RUN)
        # NFR8.7 (L1-59): the served realm's memory, sampled beside the 20 users.
        evidence["load"] = load(
            runner, fixtures, timings.get("searchBody"),
            seconds=min(LOAD_SECONDS, remaining(started, runner) - 40 - SCRAM_SECONDS),
            sample_memory=lambda: served_tree(runner, companion.pid,
                                              started + runner.PHASE_SECONDS))
    finally:
        runner.stop(companion)
    server = latency_summaries(runner.RUN, offsets=offsets)
    # L2-3: the host's own counts per class, and (L2-5) the SCRAM logins, with no host,
    # worker or scheduler holding an owner connection: each owner login allows at most
    # `CONNECTION LIMIT 4`, so logins beside the users could refuse the host's own. On a
    # forwarded port they are recorded under this phase's `counts`.
    evidence["serverCounts"] = latency_counts(runner.RUN, offsets=offsets)
    evidence["scramLogins"] = scram_logins(path)
    evidence["readClassCheck"] = read_class_check(
        evidence["load"]["samples"]["api-read"], evidence["serverCounts"])
    p95 = {
        "health": evidence["load"]["p95Ms"]["health"],                     # NFR8.1, local
        "first-load": percentile(timings.get("firstLoadMs", [])),         # NFR8.2
        "navigation": percentile(timings.get("navigationMs", [])),        # NFR8.2
        "api-read": server.get("read"),                                    # NFR8.3, server
        "search": evidence["load"]["p95Ms"]["search"],                     # NFR8.4
        "accept": percentile(timings.get("acceptMs", [])),                 # NFR8.5
    }
    evidence.update(p95Ms=p95, serverP95Ms=server)
    # The person's decisions of 2026-10-24: v1's real production rate beside the test's;
    # at the install the phase fails if v1's is higher or its count is missing; locally,
    # before the install, it is recorded as not yet available.
    evidence["v1RequestRate"] = v1_request_rate(install=evidence["counts"])
    evidence["rateCheck"] = rate_check(evidence["load"]["requestsPerSecond"],
                                       evidence["v1RequestRate"])
    evidence.update(performance_verdict(
        p95, evidence["load"]["refusals"], evidence["load"]["readiness"],
        evidence["rateCheck"], browser.get("exitCode", 1), evidence["backup"],
        scram=evidence["scramLogins"], read_check=evidence["readClassCheck"],
        storage_checks=evidence["vectorStorage"]["failedChecks"]))
    evidence["durationSeconds"] = time.monotonic() - started
    return record(runner, "performance", source_rule_end(runner, source, evidence))


def performance_verdict(p95: dict, refusals: dict, readiness: dict, rate_check: str | None,
                        browser_exit: int, backup: dict, *, scram: dict,
                        read_check: str | None, storage_checks: tuple | list = ()) -> dict:
    """The performance phase's verdict (Step 95(j), Step 134(f)), a pure function of its
    figures.

    A target met only by the requests the service did not refuse is not met: every
    refusal (a 5xx, a refused connection or a limit) fails the phase, counted by kind. The
    host stays ready under the load: a sample not ready, or with its admission closed,
    fails the phase as a refusal does. The natural plans are recorded at this size, not
    judged (the person's decision of 2026-10-23). A refusal, a missed target, an unready
    host, a rate check, a failed browser measurement or a backup that failed or passed its
    deadline fails the phase. Every target is stated as "under" (NFR8.1-NFR8.5), so a p95
    at its target misses it; the backup's deadline is "within", so it may be met exactly.

    `failedChecks` lists, in this order: `scram-logins-unmeasured` when no SCRAM login was
    timed, `scram-logins-failed` when any SCRAM login failed (L2-5), `read_check` when
    the host counted fewer reads than its users were answered (L2-3), and each of
    `storage_checks`, the failed checks of `vector_storage_check` (Q5, NFR8.13; L4-2);
    each fails the phase. `reconsiderPool` fails nothing: 20 ms is where a pool per owner login is
    reconsidered (performance-design § 2.3), not a target, so a p95 past it goes to the
    person with R-10's note."""
    missed = [name for name, value in p95.items()
              if value is None or value >= TARGETS_MS[name]]
    refused = sum(refusals.values())
    host_unready = bool(readiness["notReady"] or readiness["admissionClosed"]
                        or not readiness["samples"])
    failed_checks = []
    if not scram["measured"]:
        failed_checks.append("scram-logins-unmeasured")
    if scram["failedLogins"] > 0:
        failed_checks.append("scram-logins-failed")
    if read_check is not None:
        failed_checks.append(read_check)
    failed_checks.extend(storage_checks)
    exit_code = int(bool(missed) or bool(refused) or host_unready
                    or rate_check is not None
                    or browser_exit != 0
                    or backup.get("outcome") != "succeeded"
                    or backup["seconds"] > backup["deadlineSeconds"]
                    or bool(failed_checks))
    return {"missedTargets": missed, "refusedRequests": refused,
            "failedChecks": failed_checks, "exitCode": exit_code}


def measured_versions(connect, *, release: dict | None) -> dict:
    """The versions a performance measurement ran on (NFR8.11, L1-59; performance-design
    § 9): PostgreSQL and pgvector as the measured database answers, Python, the two
    runtimes the composed realm stands in for, the release identity, and the
    arrangement's pins. A version that cannot be read raises."""
    from docsuri_ops.arrangement import runtimes

    with connect() as conn:
        server = conn.execute("SHOW server_version").fetchone()[0]
        row = conn.execute(
            "SELECT extversion FROM pg_extension WHERE extname = 'vector'").fetchone()
    if not server or row is None or not row[0]:
        raise RuntimeError("the measured database's versions could not be read")
    return {
        "postgresql": str(server).split()[0],
        "pgvector": row[0],
        "python": sys.version.split()[0],
        # The composed realm embeds with `StandinEmbeddings` and serves through the
        # tunnel stand-in, so the measurement ran on neither runtime.
        "ollama": "stand-in",
        "cloudflared": "stand-in",
        "release": release,
        "pins": {
            "postgresql": runtimes.POSTGRESQL_VERSION,
            "pgvector": runtimes.PGVECTOR.version,
            "ollama": runtimes.OLLAMA.version,
            "cloudflared": runtimes.CLOUDFLARED.version,
            "python": runtimes.PYTHON_VERSION,
        },
    }


def served_tree(runner, pid: int, deadline: float) -> tuple[int, int | None, int] | None:
    """One snapshot of the served realm's process tree (Step 95(o)): its RSS sum, its PSS
    sum where Linux gives one, and its process count; None when the snapshot fails."""
    try:
        rows = runner.process_tree_rows((pid,), deadline)
        rss, pss = runner.tree_memory(rows)
    except (OSError, subprocess.SubprocessError, runner.Refused):
        return None
    return rss, pss, len(rows)


def memory_record(snapshots: list) -> dict:
    """The memory watch's record: the snapshots read and unread, the peak RSS and PSS sums,
    and the tree's process count at the RSS peak (null when nothing was read)."""
    read = [item for item in snapshots if item is not None]
    peak = max(read, key=lambda item: item[0]) if read else None
    pss = [item[1] for item in read if item[1] is not None]
    return {"samples": len(read), "unread": len(snapshots) - len(read),
            "peakRssBytes": peak[0] if peak else None,
            "peakPssBytes": max(pss) if pss else None,
            "processes": peak[2] if peak else None}


async def watch_memory(sample, stop, *, every: float) -> dict:
    """Until `stop` is set, one snapshot every `every` seconds through a worker thread, so
    the `ps` call never holds the users' requests on the event loop."""
    import asyncio

    snapshots = []
    while not stop.is_set():
        snapshots.append(await asyncio.to_thread(sample))
        try:
            await asyncio.wait_for(stop.wait(), every)
        except TimeoutError:
            pass
    return memory_record(snapshots)


# The install wiring's hand-over of the newest consumer inventory's count
# (`production_wiring.v1_inventory`), never read from the live v1 site.
V1_INVENTORY_ENV = "DOCSURI_U8_V1_INVENTORY"
NOT_YET = "v1-rate-not-yet-available"


def v1_request_rate(*, install: bool, environ=os.environ) -> dict:
    """v1's real production request rate (the person's decision of 2026-10-24, "Compare
    at the install").

    - Locally, before the install, it is recorded as not yet available (`NOT_YET`).
    - At the install (`install`, a run from `releases/<tag>/`), it is v1's peak rate
      from the consumer inventory taken from your Cloudflare export (Workflow 11, made
      by the operator before the switch): the busiest interval's requests over its
      length, handed over by the install wiring. A missing or malformed hand-over is
      recorded as missing, and the phase then fails."""
    if not install:
        return {"state": NOT_YET, "requestsPerSecond": None, "source": None}
    raw = environ.get(V1_INVENTORY_ENV)
    try:
        value = json.loads(raw) if raw else None
        peak, interval = value["peakRequests"], value["intervalSeconds"]
        for number in (peak, interval):
            if not isinstance(number, int) or isinstance(number, bool) or number < 0:
                raise ValueError("inventory count outside its form")
        if interval <= 0:
            raise ValueError("inventory interval outside its form")
    except (TypeError, ValueError, KeyError, AttributeError):
        return {"state": "v1-rate-missing", "requestsPerSecond": None, "source": None}
    return {"state": "measured", "requestsPerSecond": round(peak / interval, 4),
            "source": {"inventoryId": value.get("inventoryId"), "peakRequests": peak,
                       "peakAt": value.get("peakAt"), "intervalSeconds": interval,
                       "requests": value.get("requests"),
                       "observedFrom": value.get("observedFrom"),
                       "observedUntil": value.get("observedUntil")}}


def rate_check(test_rate: float, v1: dict) -> str | None:
    """Why the test's pace does not cover v1's (a reason key), or None when it does.
    Locally the rate is not yet available, which alone never fails the phase."""
    if v1["state"] == NOT_YET:
        return None
    rate = v1.get("requestsPerSecond")
    if rate is None:
        return "v1-rate-missing"
    return "v1-rate-higher" if float(rate) > test_rate else None


BACKUP_PROTOCOL = "platform.database.backup"


def backup_deadline() -> int:
    """The backup protocol's deadline, as the platform inventory states it."""
    inventory = json.loads((ROOT / "ops/src/docsuri_ops/platform_control/inventory.json")
                           .read_text())
    found = [item for item in inventory.get("u8Protocols", [])
             if item.get("name") == BACKUP_PROTOCOL]
    if len(found) != 1:
        raise RuntimeError("the inventory names no single backup protocol")
    return int(found[0]["deadlineSeconds"])


def measure_backup(runner) -> dict:
    """One backup of the realm's production-size database through the realm's standing
    scheduler and the backup protocol, as the standing job takes it, timed."""
    from backend.modules.operations.ledger import Ledger
    from docsuri_ops.u8_platform.platform_profile import U8PlatformProfile
    from docsuri_ops.u8_platform.u8_protocols import realm_operator

    deadline = backup_deadline()

    def clock() -> dt.datetime:
        return dt.datetime.now(dt.UTC)

    ledger = Ledger.open(runner.RUN / "ledger", clock=clock)
    try:
        scheduler = realm_operator(U8PlatformProfile.realm(runner.RUN), "scheduler", ledger,
                                   clock=clock)
        begun = time.monotonic()
        receipt = scheduler.execute(BACKUP_PROTOCOL, "database-production", {
            "database": "docsuri_u8", "recordId": str(uuid.uuid4()), "via": "standing"},
            key=f"performance-backup-{uuid.uuid4().hex}")
        seconds = time.monotonic() - begun
    finally:
        ledger.close()
    sizes = [ref.split("=", 1)[1] for ref in receipt.get("effectRefs", [])
             if str(ref).startswith("fact:databaseBytes=")]
    return {"outcome": receipt.get("outcome"), "seconds": round(seconds, 1),
            "deadlineSeconds": deadline, "databaseBytes": int(sizes[0]) if sizes else None}


def latency_offsets(run: Path) -> dict[str, int]:
    """Each latency day file's length now, so `latency_summaries` reads only the windows
    the host writes after this moment."""
    folder = run / "evidence" / "latency"
    return {path.name: path.stat().st_size
            for path in (sorted(folder.glob("*.jsonl")) if folder.is_dir() else ())}


def latency_summaries(run: Path, *, offsets: dict[str, int]) -> dict[str, float | None]:
    """The host's own server timing per route class (`request_context.LatencyRecorder`'s
    windows) written after `offsets` were taken: each class's largest window p95, the
    cautious reading of windows whose samples are not kept (NFR8.3, identifiers only).

    The lines are chosen by where they sit in the file, never by their `window` time: the
    host stamps windows with the realm's clock, which the fixtures hold a day ahead for
    U5, so a time filter took in every window the realm had written, earlier journeys'
    slow reads among them (the 2000 ms `read` of 2026-10-23, against 73 ms measured)."""
    found: dict[str, float | None] = {}
    for value in _latency_lines(run, offsets=offsets):
        try:
            route_class, count = value["class"], value.get("count")
        except (KeyError, TypeError):
            continue
        p95 = value.get("p95Ms")
        if count and p95 is not None:
            found[route_class] = max(found.get(route_class) or 0, float(p95))
    return found


def _latency_lines(run: Path, *, offsets: dict[str, int]):
    """Each whole JSON line of the latency day files written after `offsets`, chosen by
    its place in the file (as `latency_summaries` explains); a line that is not JSON is
    skipped."""
    folder = run / "evidence" / "latency"
    for path in sorted(folder.glob("*.jsonl")) if folder.is_dir() else ():
        with path.open("rb") as stream:
            stream.seek(offsets.get(path.name, 0))
            text = stream.read().decode(errors="replace")
        for line in text.splitlines():
            try:
                yield json.loads(line)
            except ValueError:
                continue


def latency_counts(run: Path, *, offsets: dict[str, int]) -> dict[str, int]:
    """Each route class's summed `count` over the windows the host wrote after `offsets`
    (L2-3), leaving out classes that sum to 0."""
    counts: dict[str, int] = {}
    for value in _latency_lines(run, offsets=offsets):
        try:
            route_class, count = value["class"], value.get("count")
            counts[route_class] = counts.get(route_class, 0) + int(count or 0)
        except (KeyError, TypeError, ValueError):
            continue
    return {name: total for name, total in counts.items() if total}


def read_class_check(read_samples: int, counts: dict[str, int]) -> str | None:
    """`read-class-short` when the host counted fewer `read` requests than the reads its
    users were answered (L2-3): such a read was recorded under another class or lost with
    its window, missing evidence that never counts as success. A lower bound: the counted
    windows also hold the browser child's last reads and the load's six sign-in reads, so
    it catches a route-class defect only while those are fewer than the users' GET reads,
    and it rests on the host's last flush within `runner.stop`'s 3 s."""
    return "read-class-short" if counts.get("read", 0) < read_samples else None


# --- the capacity burst (Step 114, record-only) --------------------------------------------------

# NFR8.12's 20 concurrent signed-in users, the same number as `USERS`.
BURST_USERS = 20
# No stream, then half, then all of ControlAdmission's eight normal slots
# (`backend/control_runtime.py:117-119`).
BURST_STREAM_SIZES = (0, 4, 8)
BURST_RUNS = 3
# The three sizes in turn for each run number, so no size's first run is the phase's first.
BURST_ORDER = ((0, 1), (4, 1), (8, 1), (0, 2), (4, 2), (8, 2), (0, 3), (4, 3), (8, 3))
# Each account signed in once, its users sharing its session, as `load` does; the fixtures
# give each the `local-research` consent every job read checks (`u8_fixtures.py:425-428`).
BURST_ACCOUNTS = LOAD_ACCOUNTS
# The shell's first-load bodies: chain A's and B's navigation (`frontend/src/App.tsx:369-371`)
# and the 작업 read (`frontend/src/u8-jobs/api.ts:35-36`, `:65-69`).
NAVIGATION_BODY = {"routeId": "search"}
JOBS_BODY = {"limit": 20}
CAPABILITIES_PATH = "/api/v2/capabilities"
SESSION_PATH = "/api/v2/session"
NAVIGATION_PATH = "/api/v2/c01/host-resolve-navigation"
JOBS_PATH = "/api/v2/c07/list-research-jobs"
# `retryTransient`'s two retries (`frontend/src/api.ts:83-99`).
SHELL_RETRY_WAITS = (0.25, 0.5)
# The served host's first ready answer after its start.
READY_SECONDS = 60.0
# A stream counts as open once its first snapshot frame parses within this.
STREAM_OPEN_SECONDS = 5.0
# Every stream of a run open within this.
STREAMS_OPEN_SECONDS = 15.0
# A gate snapshot taken wholly after its mark (the writer writes every 0.5 s).
SNAPSHOT_WAIT_SECONDS = 3.0
GATE_POLL_SECONDS = 0.1
# `JOB_POLL_SECONDS` plus 4 s (`backend/u8_routes.py:396`).
STREAM_END_SECONDS = 5.0
# The navigation resolve answering 200 again after a burst.
SETTLE_SECONDS = 10.0
SETTLE_POLL_SECONDS = 0.25
# Each run needs this much of the phase's 300 s left before it starts.
BURST_RUN_RESERVE_SECONDS = 60.0
CERTIFICATE = "service-operations-tls.crt"
# The first load's kinds, in the order a chain's failure is named.
CALL_KINDS = ("capabilities", "session", "navigation", "jobs-list")
CHAIN_KINDS = {"capabilities": "capabilities", "session": "session",
               "navigation-a": "navigation", "jobs-list": "jobs-list",
               "navigation-b": "navigation", "capabilities-owner": "capabilities"}
NOT_SENT = "not-sent"
# What the first-load model leaves out, recorded with the parameters.
UNMODELLED = (
    ("the refetch the shell may make when the authority generation changes "
     "(frontend/src/u8-jobs/jobs-view.tsx:52)"),
    "the open page's 5 s list refresh (frontend/src/u8-jobs/jobs-view.tsx:57-60)",
)
BURST_FAILURES = {
    "sign-in": "a load account's sign-in was refused",
    "ready": "the served realm was not ready",
    "gates": "the gate waits were not observed",
    "streams": "a run's streams did not end",
    "memory": "the served realm passed its memory bound",
    "bound": "the phase bound left no room for a run",
}


def burst_values(token: str, streams: int, run: int, accounts: int) -> dict:
    """One run's values of its own (project.md's measurement rule), drawn from a seed of
    the measurement's token, the users, the size and the run number: per account a
    context, a session and a title; per stream a job owned by account i mod `accounts`."""
    seed = hashlib.sha256(f"{token}:u{BURST_USERS}:s{streams}:r{run}".encode()).hexdigest()
    draw = random.Random(seed)

    def identifier() -> str:
        return str(uuid.UUID(int=draw.getrandbits(128), version=4))

    owners = [{"contextId": identifier(), "sessionId": identifier(),
               "title": f"용량 측정 {seed[:12]} {number}"}
              for number in range(1, accounts + 1)]
    jobs = [{"jobId": identifier(), "operationKey": identifier(),
             "inputHash": f"{draw.getrandbits(256):064x}", "usageId": identifier(),
             "authoritySession": identifier(), "account": index % accounts}
            for index in range(streams)]
    return {"seed": seed[:16], "streams": streams, "run": run, "accounts": owners,
            "jobs": jobs}


def transient(code: str | None, message_key: str | None) -> bool:
    """`retryTransient`'s rule (`frontend/src/api.ts:90-95`)."""
    return code in ("DEPENDENCY_UNAVAILABLE", "RATE_LIMITED") or (
        code == "NOT_READY" and message_key == "capacity.exhausted")


def refusal_of(value: object) -> tuple[str, str]:
    if not isinstance(value, dict):
        return "", ""
    return str(value.get("code", "")), str(value.get("messageKey", ""))


def answer_key(status: int, value: object) -> str:
    """`'200'` for any 2xx, otherwise the status with the fixed code and message key, as
    `load`'s `timed` keys a refusal; never the body's content."""
    if 200 <= status < 300:
        return "200"
    code, message_key = refusal_of(value)
    return f"{status}:{code[:40]}:{message_key[:60]}"


def error_key(error: BaseException) -> str:
    return f"error:{type(error).__name__}"


def call_summary(calls: list[dict]) -> dict:
    """Each call kind's attempts, answers by key and client-side latency over the
    requests the host answered."""
    summary = {}
    for kind in CALL_KINDS:
        own = [call for call in calls if call["kind"] == kind]
        answers: dict[str, int] = {}
        for call in own:
            answers[call["answer"]] = answers.get(call["answer"], 0) + 1
        answered = [call["ms"] for call in own if not call["answer"].startswith("error:")]
        summary[kind] = {"attempts": len(own), "answers": answers, "latencyMs": {
            "p50": percentile(answered, 0.5), "p95": percentile(answered),
            "max": max(answered) if answered else None}}
    return summary


GATE_COUNTS = ("granted", "refused", "released", "waitMsTotal", "holdMsTotal")


def bucket_order(bucket: str | int | None) -> float:
    return float("inf") if bucket == "over" else float(bucket) if bucket is not None else -1.0


def gate_delta(before: dict, after: dict) -> dict:
    """Each gate's takes between two snapshots of one host process: the counts' and
    buckets' differences, the bucket under which 95% of the granted takes fall, the
    highest bucket holding a take and the mean hold."""
    if before.get("pid") != after.get("pid"):
        raise ValueError("the gate record belongs to another host process")
    delta = {}
    for key, now_ in after.get("gates", {}).items():
        then = before.get("gates", {}).get(key, {})
        entry = {name: now_.get(name, 0) - then.get(name, 0) for name in GATE_COUNTS}
        buckets = {name: count - then.get("buckets", {}).get(name, 0)
                   for name, count in now_.get("buckets", {}).items()}
        if any(value < 0 for value in (*entry.values(), *buckets.values())):
            raise ValueError("the gate record belongs to another host process")
        granted, cumulative, p95 = entry["granted"], 0, None
        for name, count in buckets.items():
            cumulative += count
            if granted and p95 is None and cumulative >= 0.95 * granted:
                p95 = name if name == "over" else int(name)
        held = [name for name, count in buckets.items() if count]
        top = max(held, key=bucket_order) if held else None
        delta[key] = {**entry, "buckets": buckets, "p95BucketMs": p95,
                      "maxBucketMs": top if top in (None, "over") else int(top),
                      "holdMsMean": (entry["holdMsTotal"] / entry["released"]
                                     if entry["released"] else None)}
    return delta


def run_ready(run: dict) -> bool:
    """Every readiness sample of the run answered ready with the admission open."""
    samples = run.get("readiness") or []
    return bool(samples) and all(
        sample.get("ready") is True and sample.get("admissionClosed") is False
        for sample in samples)


def run_refusals(run: dict) -> dict[str, int]:
    refusals: dict[str, int] = {}
    for kind, summary in (run.get("calls") or {}).items():
        for key, count in summary.get("answers", {}).items():
            if key != "200":
                refusals[f"{kind}:{key}"] = refusals.get(f"{kind}:{key}", 0) + count
    return refusals


def burst_findings(runs: list[dict]) -> dict:
    """The record's findings per size, and whether any refusal was seen in a run whose
    host was ready with its admission open."""
    sizes, seen, sizes_refused, gates_refused = {}, False, [], set()
    for size in BURST_STREAM_SIZES:
        own = [run for run in runs if run["streams"] == size]
        refusals: dict[str, int] = {}
        gate_refusals: dict[str, int] = {}
        gate_p95: dict[str, object] = {}
        holds: dict[str, list[float]] = {}
        counted = False
        for run in own:
            refused = run_refusals(run)
            for key, count in refused.items():
                refusals[key] = refusals.get(key, 0) + count
            if refused and run_ready(run):
                counted = True
            for part in ("streams", "burst"):
                for key, gate in ((run.get("gates") or {}).get(part) or {}).items():
                    if gate["refused"]:
                        gate_refusals[key] = gate_refusals.get(key, 0) + gate["refused"]
                        gates_refused.add(key)
                    if bucket_order(gate["p95BucketMs"]) > bucket_order(gate_p95.get(key)):
                        gate_p95[key] = gate["p95BucketMs"]
                    total = holds.setdefault(key, [0.0, 0])
                    total[0] += gate["holdMsTotal"]
                    total[1] += gate["released"]
        seen = seen or counted
        if counted:
            sizes_refused.append(size)
        sizes[str(size)] = {
            "runs": [run["run"] for run in own], "refusals": refusals,
            "usersNotLoaded": [run["users"]["notLoaded"] for run in own],
            "streamsOpened": [run["streamsOpened"] for run in own],
            "streamEnds": [run["streamEnds"] for run in own],
            "runsNotReady": [run["run"] for run in own if not run_ready(run)],
            "runsBelowSize": [run["run"] for run in own if run.get("sizeNotReached")],
            "gateRefusals": gate_refusals, "gateP95BucketMs": gate_p95,
            "gateHoldMsMean": {key: (total / count if count else None)
                               for key, (total, count) in holds.items()},
        }
    return {"sizes": sizes, "refusalsSeen": seen, "sizesWithRefusals": sizes_refused,
            "gatesWithRefusals": sorted(gates_refused)}


class BurstJobs:
    """The unfinished synthetic research jobs the streams follow, written and ended
    through ResearchWorkspace's own login under the realm's maintenance gate, the way the
    fixtures write their rows (`scripts/u8_fixtures.py:635`). No admission or dispatch
    row is written, so the research worker never takes them
    (`backend/modules/research/execution.py:372-380`)."""

    def __init__(self, profile):
        from backend.transactions import OwnerTransactions

        self.transactions = OwnerTransactions(profile, process="maintenance")

    @classmethod
    def open(cls, path: Path) -> BurstJobs:
        from backend.local_profile import LocalProfile

        return cls(LocalProfile.load(path))

    def write(self, account_ids: list[uuid.UUID], values: dict) -> list[tuple[int, uuid.UUID]]:
        """One run's rows, as `host_flows.make_jobs` writes them; each job with its
        account's index."""
        from backend.u4_policy import SYNTHETIC_RESEARCH

        def action(conn) -> list[tuple[int, uuid.UUID]]:
            now_ = dt.datetime.now(dt.UTC)
            for account_id, owner in zip(account_ids, values["accounts"], strict=True):
                scope = {"contextId": owner["contextId"], "publicPapers": [],
                         "attachmentIds": [], "webReferences": [],
                         "scopePolicy": SYNTHETIC_RESEARCH.reference()}
                conn.execute("INSERT INTO research.context(id,owner_id,purpose) "
                             "VALUES(%s,%s,'research')", (owner["contextId"], account_id))
                conn.execute("INSERT INTO research.session(id,owner_id,context_id,title,scope) "
                             "VALUES(%s,%s,%s,%s,%s::jsonb)",
                             (owner["sessionId"], account_id, owner["contextId"],
                              owner["title"], json.dumps(scope)))
            written = []
            for job in values["jobs"]:
                owner = values["accounts"][job["account"]]
                conn.execute(
                    "INSERT INTO research.job(id,owner_id,context_id,session_id,"
                    "authority_session,kind,operation_key,input_hash,input,scope,policy,"
                    "accepted_at,updated_at,usage_id) VALUES(%s,%s,%s,%s,%s,'research-turn',"
                    "%s,%s,'{}','{}','{}',%s,%s,%s)",
                    (job["jobId"], account_ids[job["account"]], owner["contextId"],
                     owner["sessionId"], job["authoritySession"], job["operationKey"],
                     job["inputHash"], now_, now_, job["usageId"]))
                written.append((job["account"], uuid.UUID(job["jobId"])))
            return written

        return self.transactions.run("research", action)

    def end(self, job_ids: list[uuid.UUID]) -> int:
        """The research worker's statement for a job it cannot run (`execution.py:403-413`):
        the number of rows it moved to `failed` (a research turn cannot be cancelled)."""
        if not job_ids:
            return 0
        return self.transactions.run("research", lambda conn: conn.execute(
            "UPDATE research.job SET state='failed',error_code='SOURCE_INELIGIBLE',"
            "revision=revision+1,seq=seq+1 WHERE id = ANY(%s) AND state IN "
            "('accepted','running','cancel_requested')", (list(job_ids),)).rowcount)

    def close(self) -> None:
        self.transactions.close()


def burst_headers(csrf: str | None) -> dict:
    """The headers `load` sends with each POST."""
    return {"origin": PUBLIC_ORIGIN, "x-csrf-token": csrf or "",
            "idempotency-key": str(uuid.uuid4())}


def answer_json(answer) -> object:
    try:
        return answer.json()
    except ValueError:
        return None


async def sign_in(client, account: dict) -> str | None:
    """One sign-in per account, as `load`'s `signed_in` does; the session's CSRF token, or
    None when the sign-in was refused."""
    import httpx

    try:
        csrf = (await client.get(SESSION_PATH)).json().get("csrfToken")
        signed = await client.post("/api/v2/c02/access-login", json={
            "email": account["email"], "password": account["password"],
            "policyRef": ENTRY_POLICY}, headers=burst_headers(csrf))
        if signed.status_code != 200:
            return None
        return (await client.get(SESSION_PATH)).json().get("csrfToken")
    except (httpx.HTTPError, ValueError, AttributeError):
        return None


async def first_load(client, *, sleep, clock) -> dict:
    """One person reopening their 작업 page as the complete shell loads it (Step 114(g)):
    capabilities and the session read together; once the session answers 200, chain A's
    navigation and the 작업 read, and, signed in, chain B's navigation and a second
    capabilities read for the change of owner. A refused session read sends no 작업 read;
    chain A retries, reading the session again while it holds no CSRF token."""
    import httpx

    calls: list[dict] = []
    csrf: dict[str, str | None] = {"token": None}

    async def send(kind: str, chain: str, attempt: int, path: str, body=None):
        begun = clock()
        try:
            if body is None:
                answer = await client.get(path)
            else:
                answer = await client.post(path, json=body, headers=burst_headers(csrf["token"]))
        except httpx.HTTPError as error:
            status, value, key = None, None, error_key(error)
        else:
            status, value = answer.status_code, answer_json(answer)
            key = answer_key(status, value)
        calls.append({"kind": kind, "chain": chain, "attempt": attempt, "answer": key,
                      "ms": round((clock() - begun) * 1000, 3)})
        return status, value, key

    async def read_session(chain: str, attempt: int):
        answered = await send("session", chain, attempt, SESSION_PATH)
        status, value, _ = answered
        if status == 200 and isinstance(value, dict):
            csrf["token"] = value.get("csrfToken") or None
        return answered

    async def navigation(chain: str, shared=None) -> str:
        for attempt in range(1, len(SHELL_RETRY_WAITS) + 2):
            if attempt == 1 and shared is not None:
                # The CSRF wait shares the refused bootstrap flight.
                status, value, key = shared
            else:
                status, value, key = 200, None, "200"
                if csrf["token"] is None:
                    status, value, key = await read_session(chain, attempt)
                if status == 200:
                    status, value, key = await send("navigation", chain, attempt,
                                                    NAVIGATION_PATH, NAVIGATION_BODY)
            if key == "200":
                return key
            if attempt > len(SHELL_RETRY_WAITS) or status is None or not transient(
                    *refusal_of(value)):
                return key
            await sleep(SHELL_RETRY_WAITS[attempt - 1])
        return key

    async def jobs_list() -> str:
        # Never retried (`jobs-view.tsx:56`).
        return (await send("jobs-list", "jobs-list", 1, JOBS_PATH, JOBS_BODY))[2]

    async def owner_capabilities() -> str:
        return (await send("capabilities", "capabilities-owner", 1, CAPABILITIES_PATH))[2]

    mounted, session = await asyncio.gather(
        send("capabilities", "capabilities", 1, CAPABILITIES_PATH), read_session("session", 1))
    chains = {"capabilities": mounted[2], "session": session[2]}
    if session[0] == 200:
        signed = isinstance(session[1], dict) and session[1].get("signedIn") is True
        work = {"navigation-a": navigation("navigation-a"), "jobs-list": jobs_list()}
        if signed:
            work.update({"navigation-b": navigation("navigation-b"),
                         "capabilities-owner": owner_capabilities()})
        chains.update(zip(work, await asyncio.gather(*work.values()), strict=True))
    else:
        chains["jobs-list"] = NOT_SENT
        chains["navigation-a"] = await navigation("navigation-a", shared=session)
    failed = [chain for chain in CHAIN_KINDS if chain in chains and chains[chain] != "200"]
    return {"loaded": not failed, "firstFailure": CHAIN_KINDS[failed[0]] if failed else None,
            "chains": chains, "calls": calls}


async def fire_burst(clients, *, users: int = BURST_USERS, sleep, clock) -> list[dict]:
    """Every user's first load, user i on client i mod the clients, all started together
    by one event."""
    start = asyncio.Event()

    async def user(index: int) -> dict:
        await start.wait()
        return await first_load(clients[index % len(clients)], sleep=sleep, clock=clock)

    tasks = [asyncio.create_task(user(index)) for index in range(users)]
    await asyncio.sleep(0)
    start.set()
    return list(await asyncio.gather(*tasks))


def ready_sample() -> dict:
    """`/health/ready` once on the host's local address, as `load`'s readiness watch
    reads it. Never read while a burst runs: it takes one of the two recovery slots."""
    import urllib.error
    import urllib.request

    try:
        with urllib.request.urlopen(LOCAL_ORIGIN + "/health/ready", timeout=2) as answer:
            report = json.loads(answer.read() or b"{}")
    except urllib.error.HTTPError as error:
        try:
            report = json.loads(error.read() or b"{}")
        except ValueError:
            report = {}
    except (OSError, ValueError):
        return {"answered": False, "ready": None, "admissionClosed": None}
    if not isinstance(report, dict):
        report = {}
    return {"answered": True, "ready": report.get("ready") is True,
            "admissionClosed": report.get("admission") == "closed"}


def gate_record(runner) -> dict | None:
    from backend.u8_gate_waits import GATE_WAITS_FILE

    try:
        value = json.loads(runner.private_bytes(runner.RUN / GATE_WAITS_FILE,
                                                maximum=runner.MAX_LOG))
    except (OSError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def gate_mark(runner, pid: int) -> int:
    """The sequence of the served host's snapshot on disk now (-2 without one)."""
    value = gate_record(runner)
    if value is None or value.get("pid") != pid or not isinstance(value.get("sequence"), int):
        return -2
    return value["sequence"]


async def next_gate_snapshot(runner, pid: int, mark: int, *, sleep) -> dict | None:
    """The first snapshot from the served host's `pid` with `sequence >= mark + 2`, which
    was taken wholly after the mark, read every 0.1 s for at most
    `SNAPSHOT_WAIT_SECONDS`; otherwise None."""
    for _ in range(round(SNAPSHOT_WAIT_SECONDS / GATE_POLL_SECONDS) + 1):
        value = gate_record(runner)
        if value is not None and value.get("pid") == pid and isinstance(
                value.get("sequence"), int) and value["sequence"] >= mark + 2:
            return value
        await sleep(GATE_POLL_SECONDS)
    return None


async def next_frame(lines) -> dict | None:
    """The next event-stream frame (`event`, `data`), or None once the stream ended."""
    fields: dict[str, str] = {}
    async for line in lines:
        if not line:
            if fields:
                return fields
            continue
        if line.startswith(":"):
            continue
        name, _, value = line.partition(":")
        value = value.removeprefix(" ")
        fields[name] = fields[name] + "\n" + value if name in fields else value
    return fields or None


async def open_stream(client, job_id: uuid.UUID, *, clock) -> dict:
    """One job page's stream, asked for as the browser's `EventSource` asks
    (`job-live-status.tsx:21`, `:100`); open once its first snapshot frame parses."""
    import httpx

    begun = clock()
    stream = {"jobId": str(job_id), "answer": None, "response": None, "lines": None,
              "openedAt": None, "openMs": None}
    request = client.build_request("GET", f"/api/v2/jobs/{job_id}/events",
                                   headers={"accept": "text/event-stream"})
    try:
        response = await asyncio.wait_for(client.send(request, stream=True),
                                          STREAM_OPEN_SECONDS)
    except (httpx.HTTPError, TimeoutError) as error:
        stream["answer"] = error_key(error)
        return stream
    if response.status_code != 200:
        try:
            await response.aread()
            stream["answer"] = answer_key(response.status_code, answer_json(response))
        except httpx.HTTPError as error:
            stream["answer"] = error_key(error)
        await response.aclose()
        return stream
    lines = response.aiter_lines()
    try:
        frame = await asyncio.wait_for(
            next_frame(lines), max(0.01, STREAM_OPEN_SECONDS - (clock() - begun)))
        data = json.loads(frame["data"]) if frame and frame.get("event") == "snapshot" else None
    except (httpx.HTTPError, TimeoutError, ValueError, KeyError) as error:
        data = None
        stream["answer"] = error_key(error)
    if not isinstance(data, dict):
        stream["answer"] = stream["answer"] or "200:no-snapshot"
        await response.aclose()
        return stream
    stream.update(answer="200", response=response, lines=lines, openedAt=clock(),
                  openMs=round((clock() - begun) * 1000, 3))
    return stream


async def read_to_end(stream: dict) -> dict:
    """The stream read to its end: the last frame's event and the last snapshot's state."""
    import httpx

    last = {"event": None, "state": None}
    try:
        while True:
            frame = await next_frame(stream["lines"])
            if frame is None:
                return last
            last["event"] = frame.get("event")
            if frame.get("event") == "snapshot":
                try:
                    last["state"] = json.loads(frame.get("data", "")).get("state")
                except (ValueError, AttributeError):
                    last["state"] = None
    except httpx.HTTPError:
        last["event"] = "transport-error"
        return last


async def end_streams(streams: list[dict], ended: bool, *, clock) -> list[str]:
    """Each open stream read to its end once its job is ended: `job-ended` when it ends
    with its job's terminal snapshot within `STREAM_END_SECONDS`, `early` when it ended
    otherwise; when the jobs' end failed or a stream's end did not come in time, it is
    read on to its own end (`deadline`), and a stream still open after that is
    `not-ended`."""
    from backend.u8_routes import JOB_POLL_SECONDS, JOB_STREAM_SECONDS

    tasks = [asyncio.create_task(read_to_end(stream)) for stream in streams]
    if not tasks:
        return []
    ends: list[str | None] = [None] * len(tasks)
    if ended:
        await asyncio.wait(tasks, timeout=STREAM_END_SECONDS)
        for index, task in enumerate(tasks):
            if task.done():
                last = task.result()
                ends[index] = ("job-ended" if last["event"] == "snapshot"
                               and last["state"] == "failed" else "early")
    for index, (stream, task) in enumerate(zip(streams, tasks, strict=True)):
        if ends[index] is not None:
            continue
        left = stream["openedAt"] + JOB_STREAM_SECONDS + JOB_POLL_SECONDS - clock()
        if not task.done() and left > 0:
            await asyncio.wait([task], timeout=left)
        if task.done():
            ends[index] = "deadline"
        else:
            task.cancel()
            ends[index] = "not-ended"
    return [end or "not-ended" for end in ends]


async def settle(client, *, sleep, clock) -> tuple[bool, float]:
    """The navigation resolve posted every 0.25 s until one answers 200, for at most
    `SETTLE_SECONDS`."""
    import httpx

    begun, csrf = clock(), None
    while clock() - begun < SETTLE_SECONDS:
        try:
            if csrf is None:
                csrf = answer_json(await client.get(SESSION_PATH))
                csrf = csrf.get("csrfToken") if isinstance(csrf, dict) else None
            answer = await client.post(NAVIGATION_PATH, json=NAVIGATION_BODY,
                                       headers=burst_headers(csrf))
            if answer.status_code == 200:
                return True, round((clock() - begun) * 1000, 3)
        except httpx.HTTPError:
            pass
        await sleep(SETTLE_POLL_SECONDS)
    return False, round((clock() - begun) * 1000, 3)


async def gate_snapshot(runner, pid: int, *, sleep) -> dict | None:
    return await next_gate_snapshot(runner, pid, gate_mark(runner, pid), sleep=sleep)


def gate_deltas(first, second, third) -> dict | None:
    if first is None or second is None or third is None:
        return None
    try:
        return {"streams": gate_delta(first, second), "burst": gate_delta(second, third)}
    except ValueError:
        return None


async def open_streams(clients, run_jobs, *, clock) -> list[dict]:
    """The run's streams, opened one by one through each job owner's client, all within
    `STREAMS_OPEN_SECONDS`."""
    begun, streams = clock(), []
    for account, job_id in run_jobs:
        if clock() - begun >= STREAMS_OPEN_SECONDS:
            break
        streams.append(await open_stream(clients[account], job_id, clock=clock))
    return streams


def users_record(loads: list[dict]) -> dict:
    failures: dict[str, int] = {}
    for item in loads:
        if not item["loaded"]:
            failures[item["firstFailure"]] = failures.get(item["firstFailure"], 0) + 1
    loaded = sum(1 for item in loads if item["loaded"])
    return {"loaded": loaded, "notLoaded": len(loads) - loaded, "firstFailure": failures}


async def run_burst(runner, clients, jobs, run_jobs, *, streams: int, pid: int, ready_sample,
                    sleep, clock) -> dict:
    """One run (Step 114(g)): readiness and a gate snapshot; the run's streams, opened one
    by one and kept open unread; a snapshot and readiness; every user's first load
    together; a snapshot and readiness; the run's jobs ended and every stream read to its
    end; the navigation resolve answering again."""
    begun, started_at = clock(), now()
    readiness = [await asyncio.to_thread(ready_sample)]
    first = await gate_snapshot(runner, pid, sleep=sleep)
    opened = await open_streams(clients, run_jobs, clock=clock)
    live = [stream for stream in opened if stream["response"] is not None]
    second = await gate_snapshot(runner, pid, sleep=sleep)
    readiness.append(await asyncio.to_thread(ready_sample))
    loads = await fire_burst(clients, sleep=sleep, clock=clock)
    third = await gate_snapshot(runner, pid, sleep=sleep)
    readiness.append(await asyncio.to_thread(ready_sample))
    job_ids = [job_id for _, job_id in run_jobs]
    try:
        jobs_ended: int | str = await asyncio.to_thread(jobs.end, job_ids)
    except Exception as error:  # noqa: BLE001 - recorded; the streams are read on
        jobs_ended = type(error).__name__
    try:
        ends = await end_streams(live, isinstance(jobs_ended, int), clock=clock)
    finally:
        for stream in live:
            await stream["response"].aclose()
    settled, settle_ms = await settle(clients[0], sleep=sleep, clock=clock)
    open_ms = [stream["openMs"] for stream in live]
    answers: dict[str, int] = {}
    for stream in opened:
        answers[stream["answer"]] = answers.get(stream["answer"], 0) + 1
    return {
        "streams": streams, "startedAt": started_at, "streamsOpened": len(live),
        "sizeNotReached": len(live) < streams, "streamAnswers": answers,
        "streamOpenMs": {"p50": percentile(open_ms, 0.5),
                         "max": max(open_ms) if open_ms else None},
        "streamEnds": ends, "readiness": readiness,
        "calls": call_summary([call for item in loads for call in item["calls"]]),
        "users": users_record(loads), "gates": gate_deltas(first, second, third),
        "jobsEnded": jobs_ended, "settled": settled, "settleMs": settle_ms,
        "durationSeconds": round(clock() - begun, 3),
    }


def burst_failure(record_: dict) -> str | None:
    """A run's failed prerequisite, or None."""
    gates = record_.get("gates")
    accounts = ((gates or {}).get("burst") or {}).get("owner:accounts") or {}
    if gates is None or not accounts.get("granted"):
        return BURST_FAILURES["gates"]
    if "not-ended" in record_["streamEnds"]:
        return BURST_FAILURES["streams"]
    return None


async def drive_bursts(runner, fixtures: dict, plan: list[dict], jobs, companion,
                       started: float) -> tuple[list[dict], str | None]:
    """The three clients signed in, then one `run_burst` per plan item in `BURST_ORDER`,
    each with its memory snapshot; it stops at the first failed prerequisite."""
    import ssl

    import httpx

    context = ssl.create_default_context(cafile=str(runner.RUN / CERTIFICATE))
    clients = [httpx.AsyncClient(base_url=PUBLIC_ORIGIN, verify=context, timeout=15)
               for _ in BURST_ACCOUNTS]
    runs: list[dict] = []
    try:
        for client, key in zip(clients, BURST_ACCOUNTS, strict=True):
            if await sign_in(client, fixtures["accounts"][key]) is None:
                return runs, BURST_FAILURES["sign-in"]
        for item in plan:
            if remaining(started, runner) < BURST_RUN_RESERVE_SECONDS:
                return runs, BURST_FAILURES["bound"]
            record_ = await run_burst(runner, clients, jobs, item["jobs"],
                                      streams=item["streams"], pid=companion.pid,
                                      ready_sample=ready_sample, sleep=asyncio.sleep,
                                      clock=time.monotonic)
            record_.update(run=item["run"], seed=item["values"]["seed"])
            tree = await asyncio.to_thread(served_tree, runner, companion.pid,
                                           started + runner.PHASE_SECONDS)
            record_["memory"] = (None if tree is None else
                                 {"rssBytes": tree[0], "pssBytes": tree[1],
                                  "processes": tree[2]})
            runs.append(record_)
            if tree is not None and runner.enforced_bytes(tree[0], tree[1]) > runner.MAX_RSS:
                return runs, BURST_FAILURES["memory"]
            failure = burst_failure(record_)
            if failure is not None:
                return runs, failure
        return runs, None
    finally:
        for client in clients:
            await client.aclose()


def wait_ready(runner, companion, deadline: float) -> float | None:
    """The seconds until the host's first ready answer, polled every `POLL_SECONDS` for at
    most `READY_SECONDS` with the served tree held to its bound; None without one."""
    begun = time.monotonic()
    end = min(begun + READY_SECONDS, deadline)
    while time.monotonic() < end:
        hold_tree(runner, companion, deadline)
        if local_ready():
            return round(time.monotonic() - begun, 3)
        time.sleep(POLL_SECONDS)
    return None


def burst_parameters() -> dict:
    from backend.u8_routes import JOB_POLL_SECONDS, JOB_STREAM_SECONDS

    return {
        "users": BURST_USERS, "streamSizes": list(BURST_STREAM_SIZES), "runs": BURST_RUNS,
        "order": [list(item) for item in BURST_ORDER], "accounts": list(BURST_ACCOUNTS),
        "sessions": "one shared session per account",
        "firstLoad": {"mount": ["GET " + CAPABILITIES_PATH, "GET " + SESSION_PATH],
                      "signedIn": ["POST " + NAVIGATION_PATH + " (chain A)",
                                   "POST " + JOBS_PATH, "POST " + NAVIGATION_PATH
                                   + " (chain B)", "GET " + CAPABILITIES_PATH],
                      "navigationBody": NAVIGATION_BODY, "jobsBody": JOBS_BODY},
        "shellRetryWaits": list(SHELL_RETRY_WAITS),
        "jobStreamSeconds": JOB_STREAM_SECONDS, "jobPollSeconds": JOB_POLL_SECONDS,
        # ControlAdmission (`backend/control_runtime.py`) and the owner gates
        # (`backend/transactions.py:194`, `:238-243`), as built.
        "controlAdmission": {"normalSlots": 8, "recoverySlots": 2, "queue": None},
        "ownerGates": {"normalSlotsPerOwner": 1, "sharedSlotsPerOwner": 2,
                       "queueSeconds": 1},
        "unmodelled": list(UNMODELLED),
    }


def end_left(jobs, plan: list[dict], runs: list[dict]) -> int | str:
    """Every job no run ended, ended now; the count, or the error's type (never raised)."""
    done = {(run["run"], run["streams"]) for run in runs
            if isinstance(run.get("jobsEnded"), int)}
    left = [job_id for item in plan if (item["run"], item["streams"]) not in done
            for _, job_id in item.get("jobs", ())]
    try:
        return jobs.end(left)
    except Exception as error:  # noqa: BLE001 - recorded beside the runs' own counts
        return type(error).__name__


def run_capacity_burst(runner, path: Path) -> dict:
    """The record-only capacity burst (Step 114(h)): every run's jobs written, the served
    realm started with its gate observer, then the nine runs in `BURST_ORDER`. It fails
    only on a failed prerequisite or a change of source; refusals, waits and holds are
    its record."""
    from backend.u8_gate_waits import GATE_WAITS_FILE

    value, resources = runner.prepare_phase(path)
    browser = runner.RUN / "fixtures" / "browser.json"
    if not browser.exists():
        raise runner.Refused("the capacity burst needs the fixtures phase first")
    source = source_rule_start(runner)
    started = time.monotonic()
    token = secrets.token_hex(8)
    fixtures = json.loads(runner.private_bytes(browser))
    account_ids = [uuid.UUID(fixtures["accounts"][key]["accountId"]) for key in BURST_ACCOUNTS]
    drawn = [{"streams": streams, "run": run,
              "values": burst_values(token, streams, run, len(BURST_ACCOUNTS))}
             for streams, run in BURST_ORDER]
    evidence = {"phase": "capacity-burst", "runId": value["runId"], "resources": resources,
                "recordOnly": True, "token": token, "parameters": burst_parameters()}
    jobs = BurstJobs.open(path)
    companion, runs, failure, offsets, plan = None, [], None, {}, []
    try:
        for item in drawn:
            # Appended one by one, so a later failure still ends what was written.
            plan.append({**item, "jobs": jobs.write(account_ids, item["values"])})
        evidence["jobsWritten"] = sum(len(item["jobs"]) for item in plan)
        evidence["versions"] = measured_versions(lambda: runner.connect_admin(value),
                                                 release=None)
        for name in (GATE_WAITS_FILE, GATE_WAITS_FILE + ".pending"):
            (runner.RUN / name).unlink(missing_ok=True)
        offsets = latency_offsets(runner.RUN)
        log = runner.RUN / f"u8-realm-capacity-burst-{time.time_ns()}.log"
        companion = start_realm(runner, path, log, staged=False, observe_gates=True)
        evidence["realmLog"] = log.name
        evidence["readySeconds"] = wait_ready(runner, companion,
                                              started + runner.PHASE_SECONDS)
        if evidence["readySeconds"] is None:
            failure = BURST_FAILURES["ready"]
        else:
            runs, failure = asyncio.run(drive_bursts(runner, fixtures, plan, jobs, companion,
                                                     started))
    finally:
        if companion is not None:
            runner.stop(companion)
        evidence["jobsEnded"] = {"runs": [run.get("jobsEnded") for run in runs],
                                 "afterStop": end_left(jobs, plan, runs)}
        jobs.close()
    evidence.update(runs=runs, summary=burst_findings(runs),
                    serverP95Ms=latency_summaries(runner.RUN, offsets=offsets),
                    exitCode=int(failure is not None), failureReason=failure,
                    durationSeconds=time.monotonic() - started)
    return record(runner, "capacity-burst", source_rule_end(runner, source, evidence))


# --- the repair exercise ---------------------------------------------------------------------


def repair_tree(runner) -> tuple[Path, str]:
    """A clean checkout of the commit with `git worktree`; while the source under test is
    not yet committed, the run's own listed source files are laid over it, so the exercise
    runs on exactly the source the VerificationRun binds (recorded as `overlay`)."""
    import shutil

    head = runner.require(["git", "rev-parse", "HEAD"]).stdout.strip()
    tree = Path.home() / ".docsuri-u8" / f"repair-{head[:12]}-{uuid.uuid4().hex[:8]}"
    runner.require(["git", "-C", str(ROOT), "worktree", "add", "--detach", str(tree), head],
                   timeout=120)
    changed = runner.require(["git", "status", "--porcelain"]).stdout.strip()
    state = "clean"
    if changed:
        for name in runner.listed_files("backend", "frontend/src", "shared", "scripts", "ops",
                                        "ingestion", "platform_integrity", TEST_ROOT):
            source = ROOT / name
            if source.is_file() and not source.is_symlink():
                target = tree / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
        state = "overlay"
    return tree, state


def run_repair_exercise(runner, path: Path) -> dict:
    """The recorded defect: navigation resolution treats a stale capability as available
    (BR1.3, BR3.2). Applied in the clean checkout, the affected checks fail and the
    failing request's identifier is followed through the log to the resolver; removed,
    the regression test and the affected checks pass."""
    value, _resources = runner.prepare_phase(path)
    runner.require_test_paths((REGRESSION, f"{TEST_ROOT}/integration/test_navigation_api.py"))
    source = source_rule_start(runner)
    started = time.monotonic()
    tree, state = repair_tree(runner)
    evidence = {"phase": "repair-exercise", "runId": value["runId"], "checkout": state,
                "defect": DEFECT, "regression": REGRESSION}
    try:
        runner.require(["git", "-C", str(tree), "apply", str(ROOT / DEFECT)])
        broken = run_repair_checks(runner, tree, started, "repair-defect")
        evidence["withDefect"] = broken
        runner.require(["git", "-C", str(tree), "apply", "-R", str(ROOT / DEFECT)])
        repaired = run_repair_checks(runner, tree, started, "repair-fixed")
        evidence["repaired"] = repaired
        evidence["exitCode"] = int(not repair_passed(broken, repaired))
    finally:
        subprocess.run(["git", "-C", str(ROOT), "worktree", "remove", "--force", str(tree)],
                       capture_output=True, timeout=120, check=False)
    evidence["durationSeconds"] = time.monotonic() - started
    return record(runner, "repair-exercise", source_rule_end(runner, source, evidence))


RESOLVER = "u8_routes.navigation_items"


def repair_passed(broken: dict, repaired: dict) -> bool:
    """The exercise passed: with the defect the checks failed, the failing request was
    followed to the resolver (`u8_routes.navigation_items`, over the registry's entries),
    and without it they pass."""
    diagnosed = broken.get("traced") or {}
    return (broken.get("exitCode", 0) != 0 and broken.get("failures", 0) > 0
            and diagnosed.get("location", "") == RESOLVER
            and repaired.get("exitCode") == 0 and repaired.get("tests", 0) > 0
            and not repaired.get("failures") and not repaired.get("errors"))


def run_repair_checks(runner, tree: Path, started: float, name: str) -> dict:
    report = runner.RUN / f"{name}.xml"
    trace = runner.RUN / f"{name}-trace.jsonl"
    trace.unlink(missing_ok=True)  # this run's lines only, never an earlier run's
    args = [str(runner.PYTHON), "-m", "pytest", "-c", str(tree / runner.PYTEST_INI),
            *[str(tree / check) for check in REPAIR_CHECKS], "-q", "--tb=line",
            "-p", "no:cacheprovider", f"--junitxml={report}"]
    log = runner.RUN / f"u8-phase-{name}-{time.time_ns()}.log"
    supervision = runner.bounded_process(
        args, log, seconds=remaining(started, runner),
        environment=environment(runner, {"PYTHONPATH": str(tree),
                                         "DOCSURI_U8_REPAIR_TRACE": str(trace)}))
    result = {"exitCode": supervision["exitCode"], "log": log.name}
    runner.junit_counts(report, result)
    result["exitCode"] = supervision["exitCode"] or result["exitCode"]
    result["traced"] = follow_request(trace)
    return result


def follow_request(trace: Path) -> dict | None:
    """The failing request's identifier, followed through the log lines the run kept to
    the log event naming where the resolver decided."""
    try:
        lines = [json.loads(line) for line in trace.read_text().splitlines() if line.strip()]
    except (OSError, ValueError):
        return None
    failing = next((line for line in lines if line.get("kind") == "failing-request"), None)
    if failing is None:
        return None
    for line in lines:
        if line.get("requestId") == failing["requestId"] and line.get("event") == (
            "navigation.resolved"):
            return {"requestId": failing["requestId"], "location": line.get("location", ""),
                    "event": line["event"]}
    return {"requestId": failing["requestId"], "location": ""}


# --- the restart phases (NFR8.6's crash clauses) -----------------------------------------------

# U8 plan Step 95(f): one deadline per phase (its start plus `PHASE_SECONDS`). The wait for
# the first ready answer ends once only the restart's own wait and the margin (the reap,
# the docker commands, the final stop and the evidence) remain.
RESTART_READY_SECONDS = 180
RESTART_MARGIN_SECONDS = 30
LOCAL_ORIGIN = "http://127.0.0.1:18109"
RESTART_NOT_READY = "the realm was not ready before the restart"
RESTART_NATIVE = "the restart phases run on the realm's docker database only"
CRASH_RECOVERY = ("database system was not properly shut down; "
                  "automatic recovery in progress")
POLL_SECONDS = 0.5


def local_ready() -> bool:
    """Whether `/health/ready` on the host's local address answers ready."""
    import urllib.error
    import urllib.request

    try:
        with urllib.request.urlopen(LOCAL_ORIGIN + "/health/ready", timeout=2) as answer:
            return json.loads(answer.read() or b"{}").get("ready") is True
    except urllib.error.HTTPError:
        return False
    except (OSError, ValueError):
        return False


def hold_tree(runner, process, deadline: float) -> None:
    """The served realm's tree within `MAX_RSS`, as `start_realm` holds it."""
    if runner.enforced_bytes(*runner.process_tree_memory((process.pid,), deadline)) > (
            runner.MAX_RSS):
        raise runner.Refused("the served realm exceeded its memory bound")


def read_horizon(runner, value: dict) -> int:
    """`pg_current_xact_id()` through the admin login: rows written at or after it are
    the restart's. The realm is fresh, so its transaction epoch is still 0 and a row's
    `xmin` compares with the horizon as a number."""
    with runner.connect_admin(value) as conn:
        horizon = int(conn.execute("SELECT pg_current_xact_id()::text").fetchone()[0])
    if horizon >= 2**32:
        raise runner.Refused("the realm's transaction epoch advanced; set up a fresh realm")
    return horizon


def observed_afresh(runner, value: dict, horizon: int) -> set[str]:
    """The capabilities with an observation row whose `xmin` is at or after the horizon.
    A row written just before this read can only be left out, which lengthens the
    measured time and never shortens it."""
    with runner.connect_admin(value) as conn:
        conn.execute("SET LOCAL statement_timeout=3000")
        rows = conn.execute(
            "SELECT DISTINCT capability FROM operations.observation_record "
            "WHERE xmin::text::bigint >= %s", (horizon,)).fetchall()
    return {row[0] for row in rows}


# The margin's parts (Step 95(f)): the final stop and the evidence, and `restart-database`'s
# `docker logs` after its wait. What the margin leaves before the clock starts holds the
# reap, the horizon read and `docker kill`; when it cannot, the phase records a refusal
# rather than a readiness window shorter than `RESTART_READY_SECONDS`.
RESTART_STOP_SECONDS = 10
RESTART_LOGS_SECONDS = 10
RESTART_MARGIN_REFUSED = "the margin could not hold the reap and the docker commands"
RESTART_WINDOW_PASSED = "the restart's readiness window passed during a docker command"


def bounded(runner, by: float, own: float, reason: str) -> float:
    """A command's timeout: its own, cut to the time left before `by`; none left refuses."""
    left = by - time.monotonic()
    if left <= 0:
        raise runner.Refused(reason)
    return min(own, left)


def ready_figure(begun: float) -> float | None:
    """One clock reading after the ready answer: the seconds since `begun`, or None at or
    past `RESTART_READY_SECONDS`. The record keeps hundredths cut, never rounded up, so a
    figure below the bound is never written as the bound."""
    elapsed = time.monotonic() - begun
    if elapsed >= RESTART_READY_SECONDS:
        return None
    return int(elapsed * 100) / 100


def wait_first_ready(runner, process, deadline: float) -> bool:
    """The first ready answer before the kill, while more than the restart's wait and its
    margin remain of the phase's deadline; a ready answer that arrives once they no longer
    remain sends no kill."""
    while deadline - time.monotonic() > RESTART_READY_SECONDS + RESTART_MARGIN_SECONDS:
        if process.poll() is not None:
            raise runner.Refused("the served realm exited before it was ready")
        hold_tree(runner, process, deadline)
        if local_ready():
            return deadline - time.monotonic() > RESTART_READY_SECONDS + RESTART_MARGIN_SECONDS
        time.sleep(POLL_SECONDS)
    return False


def wait_ready_afresh(runner, value: dict, process, horizon: int, begun: float,
                      deadline: float) -> float | None:
    """Seconds from `begun` to the first ready answer given while every required
    capability is observed afresh, or None once `RESTART_READY_SECONDS` have passed,
    including for a ready answer that arrives after them. The caller has made sure the
    window ends before the stop's and the evidence's allowance."""
    import psycopg

    from backend.u8_registry import REQUIRED

    end = begun + RESTART_READY_SECONDS
    while time.monotonic() < end:
        hold_tree(runner, process, deadline)
        try:
            fresh = observed_afresh(runner, value, horizon)
        except psycopg.Error:
            fresh = set()
        if REQUIRED <= fresh and local_ready():
            return ready_figure(begun)
        time.sleep(POLL_SECONDS)
    return None


def require_window(runner, begun: float, deadline: float, reserve: float) -> None:
    """The full readiness window, then `reserve`, still fit before the deadline."""
    if deadline - begun < RESTART_READY_SECONDS + reserve:
        raise runner.Refused(RESTART_MARGIN_REFUSED)


def restart_host(runner, path: Path, value: dict, state: dict, deadline: float,
                 evidence: dict) -> None:
    """SIGKILL to the served realm's process group (the host and its workers, scheduler,
    maintenance server and tunnel stand-in), the leader reaped and the group gone within
    one bound from the margin, then the relaunch. Once the group is gone its ID is free
    for reuse, so nothing stops it again."""
    import signal

    process = state["process"]
    reap_by = deadline - RESTART_READY_SECONDS - RESTART_STOP_SECONDS
    runner.signal_group(process.pid, signal.SIGKILL)
    process.wait(timeout=bounded(runner, reap_by, RESTART_MARGIN_SECONDS,
                                 RESTART_MARGIN_REFUSED))
    while any(not item.startswith("Z") for item in runner.group_states(process.pid)):
        if time.monotonic() > reap_by:
            raise runner.Refused("the killed realm's processes outlived the margin")
        time.sleep(0.2)
    state["process"] = None
    horizon = read_horizon(runner, value)
    evidence["horizon"] = horizon
    begun = time.monotonic()
    require_window(runner, begun, deadline, RESTART_STOP_SECONDS)
    log = runner.RUN / f"u8-realm-restart-host-relaunch-{time.time_ns()}.log"
    state["process"] = start_realm(runner, path, log, staged=False)
    evidence["relaunchLog"] = log.name
    evidence["readySeconds"] = wait_ready_afresh(runner, value, state["process"], horizon,
                                                 begun, deadline)


def started_at_of(runner, stdout: str) -> str:
    """The container's `State.StartedAt` from `docker inspect`'s answer."""
    try:
        started_at = json.loads(stdout)[0]["State"]["StartedAt"]
    except (ValueError, KeyError, IndexError, TypeError) as error:
        raise runner.Refused(
            f"docker inspect answered no start time ({type(error).__name__})") from error
    if not isinstance(started_at, str) or not started_at:
        raise runner.Refused("docker inspect answered no start time")
    return started_at


def restart_database(runner, value: dict, state: dict, deadline: float,
                     evidence: dict) -> None:
    """`docker kill -s KILL`, then `docker start`, timed from before `docker start`; the
    crash-recovery line read from the daemon's own clock (the container's
    `State.StartedAt`, inside Colima, never this Mac's), and the horizon read as soon as
    the restarted database accepts the login, the served realm's tree held on each poll."""
    import psycopg

    container = value["container"]
    reserve = RESTART_STOP_SECONDS + RESTART_LOGS_SECONDS
    runner.require(["docker", "kill", "-s", "KILL", container],
                   timeout=bounded(runner, deadline - RESTART_READY_SECONDS - reserve, 30,
                                   RESTART_MARGIN_REFUSED))
    begun = time.monotonic()
    require_window(runner, begun, deadline, reserve)
    end = begun + RESTART_READY_SECONDS
    runner.require(["docker", "start", container],
                   timeout=bounded(runner, end, 60, RESTART_WINDOW_PASSED))
    started_at = started_at_of(runner, runner.require(
        ["docker", "inspect", container],
        timeout=bounded(runner, end, 30, RESTART_WINDOW_PASSED)).stdout)
    evidence["startedAt"] = started_at
    horizon = None
    while horizon is None and time.monotonic() < end:
        hold_tree(runner, state["process"], deadline)
        try:
            horizon = read_horizon(runner, value)
        except psycopg.Error:
            time.sleep(POLL_SECONDS)
    evidence["horizon"] = horizon
    if horizon is not None:
        evidence["readySeconds"] = wait_ready_afresh(runner, value, state["process"],
                                                     horizon, begun, deadline)
    logs = runner.command(["docker", "logs", "--since", started_at, container],
                          timeout=bounded(runner, deadline - RESTART_STOP_SECONDS, 30,
                                          RESTART_MARGIN_REFUSED))
    evidence["crashRecovery"] = CRASH_RECOVERY in (logs.stdout or "") + (logs.stderr or "")


def run_restart(runner, path: Path, kind: str) -> dict:
    """`restart-host` or `restart-database`: NFR8.6's crashed host or crashed PostgreSQL in
    the complete verification, measured as `readySeconds` from the relaunch (or `docker
    start`) to the first ready answer with every required capability observed afresh."""
    import psycopg

    phase = f"restart-{kind}"
    value, resources = runner.prepare_phase(path)
    source = source_rule_start(runner)
    if runner.native(value):
        raise runner.Refused(RESTART_NATIVE)
    started = time.monotonic()
    deadline = started + runner.PHASE_SECONDS
    evidence = {"phase": phase, "runId": value["runId"], "restart": kind,
                "readySeconds": None, "resources": resources}
    log = runner.RUN / f"u8-realm-{phase}-{time.time_ns()}.log"
    state: dict = {"process": None}
    try:
        state["process"] = start_realm(runner, path, log, staged=False)
        evidence["realmLog"] = log.name
        if not wait_first_ready(runner, state["process"], deadline):
            evidence.update(exitCode=1, failureReason=RESTART_NOT_READY)
        elif kind == "host":
            restart_host(runner, path, value, state, deadline, evidence)
        else:
            restart_database(runner, value, state, deadline, evidence)
    except (runner.Refused, OSError, subprocess.SubprocessError, psycopg.Error) as error:
        # A database error (the horizon read) is recorded by its category alone.
        evidence.update(exitCode=1, failureCategory=type(error).__name__,
                        failureReason=str(error) if isinstance(error, runner.Refused) else None)
    finally:
        # `restart_host` clears the killed realm once its group is gone, so only a live
        # realm process is stopped here.
        if state["process"] is not None:
            runner.stop(state["process"])
    if "exitCode" not in evidence:
        ready = evidence["readySeconds"]
        failed = ready is None or ready >= RESTART_READY_SECONDS or (
            kind == "database" and evidence.get("crashRecovery") is not True)
        evidence["exitCode"] = int(failed)
    evidence["durationSeconds"] = time.monotonic() - started
    return record(runner, phase, source_rule_end(runner, source, evidence))


def run_restart_host(runner, path: Path) -> dict:
    return run_restart(runner, path, "host")


def run_restart_database(runner, path: Path) -> dict:
    return run_restart(runner, path, "database")


# --- the complete verification ----------------------------------------------------------------


def journeys_of(report: Path, runner) -> dict[str, str]:
    """Each journey identifier's result in one phase report: passed only when every test
    naming it passed."""
    from defusedxml import ElementTree as ET

    results: dict[str, str] = {}
    try:
        cases = list(ET.fromstring(runner.private_bytes(report, maximum=runner.MAX_LOG))
                     .iter("testcase"))
    except (OSError, ValueError, ET.ParseError):
        return results
    for case in cases:
        for journey in TITLE.findall(case.get("name", "")):
            failed = any(case.find(tag) is not None for tag in ("failure", "error", "skipped"))
            if failed:
                results[journey] = "failed"
            else:
                results.setdefault(journey, "passed")
    return results


PHASE_REPORTS = {**{phase: (f"{phase}.xml",) for phase in BROWSER_SPECS},
                 "security": ("security-backend.xml", "security.xml"),
                 "restore-paths": ("restore-paths-backend.xml",)}


# Evidence a fresh environment may already hold: the realm's `operations` lane runs before
# the fixtures, because it invalidates the administrator's factor through U2's restore
# (realm B's order: setup, migrate, operations, fixtures without the corpus). By the
# person's decision of 2026-10-26 ("Split it in two"), `operations` runs in parts, each
# writing its own evidence: three since Build and Test loop-back 1 (U8 plan Step 46(c)).
FRESH_EVIDENCE = ("operations-1-evidence-", "operations-2-evidence-",
                  "operations-3-evidence-")


def foreign_evidence(runner) -> list[str]:
    return sorted(item.name for item in runner.RUN.glob(runner.EVIDENCE_PATTERN)
                  if not item.name.startswith(FRESH_EVIDENCE))


def complete_corpus(runner, path: Path) -> dict:
    """The corpus alone, run by bounded run until it is complete (`--corpus only`, each
    its own phase), or the failed state after `CORPUS_RUNS` runs."""
    for _ in range(CORPUS_RUNS):
        result = run_fixtures(runner, path, corpus_mode="only")
        if result["state"] == "fixtures-ready":
            return {"state": "passed", "papers": result["papers"]}
    corpus = corpus_state(runner)
    return {"state": "failed", "reason": f"corpus incomplete after {CORPUS_RUNS} runs "
            f"({corpus['papers']} of {corpus['target']} papers)"}


def run_phases(runner, path: Path, names: tuple[str, ...], phases: dict[str, dict]) -> None:
    for phase in names:
        try:
            phases[phase] = PHASE_RUNNERS[phase](runner, path)
        except runner.Refused as refused:
            phases[phase] = {"state": "failed", "reason": str(refused)}


def run_verification(runner, path: Path) -> dict:
    """v1, then `restore-paths` and `browser-recovery` on the realm's database before the
    corpus, the corpus to completion, then the other journey phases in order, each under
    its own bound; then the VerificationRun for the commit. It refuses to report passed
    if any required phase is missing, skipped or failed (BR10.3, BR10.5). It needs a
    fresh environment holding at most the operations lane's evidence."""
    foreign = foreign_evidence(runner)
    if foreign:
        raise runner.Refused("verification-run needs a fresh environment: this one holds "
                             f"evidence files ({', '.join(foreign[:3])}); archive-owned, then "
                             "setup, migrate, operations, fixtures --corpus skip")
    if not (runner.RUN / "fixtures" / "phase.json").exists():
        raise runner.Refused("verification-run needs the fixtures phase first")
    started = dt.datetime.now(dt.UTC)
    head = runner.require(["git", "rev-parse", "HEAD"]).stdout.strip()
    source = runner.source_identity()
    if not runner.v1_serving():
        runner.run_v1("v1-up", path)
    phases: dict[str, dict] = {}
    run_phases(runner, path, BEFORE_CORPUS, phases)
    try:
        corpus = complete_corpus(runner, path)
    except runner.Refused as refused:
        corpus = {"state": "failed", "reason": str(refused)}
    if corpus["state"] == "passed":
        run_phases(runner, path, AFTER_CORPUS, phases)
    phases_note = {"corpus": corpus}
    run = {**verification_record(
        runner, phases, commit=head, source=source, started=started,
        committed=not runner.require(["git", "status", "--porcelain"]).stdout.strip()),
        **phases_note}
    # Step 95(a): the identity at the end against the one taken at the start; a run whose
    # source changed is never `passed`.
    changed = runner.source_identity()["sha256"] != source["sha256"]
    run["sourceChangedDuringRun"] = changed
    if changed and run["passed"]:
        run.update(passed=False, result="failed")
    from u8_fixtures import write_private

    write_private(runner.RUN / "verification" / f"{run['runId']}.json", run)
    print(json.dumps({"verificationRun": run["runId"], "result": run["result"],
                      "journeys": {item["journeyId"]: item["result"]
                                   for item in run["journeys"]}}))
    if not run["passed"]:
        raise runner.Refused(f"verification-run is {run['result']}; evidence preserved")
    return {"state": "passed", "phase": "verification-run", "verificationRun": run["runId"]}


def verification_record(runner, phases: dict[str, dict], *, commit: str, source: dict,
                        started: dt.datetime, committed: bool) -> dict:
    """The VerificationRun for one commit from its phases' results and reports: each
    journey with its result and evidence reference. It is `passed` only when every
    journey passed; a journey whose phase is missing, skipped or failed makes it
    `incomplete` or `failed` (BR10.3, BR10.5)."""
    journeys = []
    a11y_problems = a11y_evidence(runner, phases)
    for journey, (name, phase) in JOURNEYS.items():
        passed_phase = phases.get(phase, {}).get("state") == "passed"
        if phase == "repair-exercise":
            result = "passed" if passed_phase else "failed"
        elif journey == "A11Y":
            result = a11y_result(runner, phases, a11y_problems)
        else:
            found = {}
            for report in PHASE_REPORTS.get(phase, ()):
                found.update(journeys_of(runner.RUN / report, runner))
            result = found.get(journey, "not-run")
            if result == "passed" and not passed_phase:
                result = "failed"
        journeys.append({"journeyId": journey, "name": name, "result": result,
                         "phase": phase, "evidenceRef": phases.get(phase, {}).get("evidence")})
    complete = all(item["result"] != "not-run" for item in journeys) and all(
        phase in phases for phase in VERIFICATION_ORDER)
    # Step 95(g): every phase of the run passed, as well as every journey.
    failed_phases = [phase for phase in (*VERIFICATION_ORDER,
                                         *(p for p in phases if p not in VERIFICATION_ORDER))
                     if phase in phases and phases[phase].get("state") != "passed"]
    passed = (complete and not failed_phases
              and all(item["result"] == "passed" for item in journeys))
    return {"runId": str(uuid.uuid4()), "commit": commit, "failedPhases": failed_phases,
            "a11yProblems": a11y_problems,
            "sourceSha256": source["sha256"],
            "sourceState": "committed" if committed else "uncommitted",
            "journeys": journeys,
            # The person's decision of 2026-10-23 ("Test that drafts are off"): J06 proves
            # drafts as they ship, switched off by U4; durable drafts are a gap owed
            # before release.
            "gaps": [{"journeyId": "J06", "gap": "durable-drafts-switched-off",
                      "owedBefore": "release"}],
            "result": "passed" if passed else ("failed" if complete else "incomplete"),
            "passed": passed, "startedAt": started.isoformat(), "finishedAt": now(),
            "phases": {name: value.get("state") for name, value in phases.items()}}


# Step 95(g): A11Y needs every accessibility phase (Step 101(d) registers the keyboard and
# screens phases, Step 101(e) the signed-out half of `accessibility`'s split) and every
# screen's records in the kept evidence of the phase that checks it.
A11Y_PHASES = ("accessibility", "accessibility-signed-out", "accessibility-keyboard",
               "accessibility-screens")
NAV_REGIONS = frozenset({"nav-loading", "nav-error"})


def a11y_screens(captures: dict[str, tuple[str, ...]]) -> dict[str, str]:
    """Each screen of every `CAPTURES` entry, with that entry's phase; a screen is listed
    under one phase only."""
    screens: dict[str, str] = {}
    for phase, names in captures.items():
        for screen in names:
            if screens.setdefault(screen, phase) != phase:
                raise ValueError(f"screen {screen} is listed under two phases")
    return screens


A11Y_SCREENS = a11y_screens(CAPTURES)


def a11y_result(runner, phases: dict[str, dict], problems: list[str]) -> str:
    """A11Y's journey result: `passed` only when each of `A11Y_PHASES` passed, every
    `[A11Y]` test in their reports passed, and every screen's records hold."""
    found = []
    for phase in A11Y_PHASES:
        found.append(journeys_of(runner.RUN / f"{phase}.xml", runner).get("A11Y"))
    if all(result is None for result in found):
        return "not-run"
    if (all(result == "passed" for result in found) and not problems
            and all(phases.get(phase, {}).get("state") == "passed" for phase in A11Y_PHASES)):
        return "passed"
    return "failed"


def kept_folder(runner, phases: dict[str, dict], phase: str) -> Path | None:
    """The phase's `keptEvidence` folder, named by its evidence file."""
    name = phases.get(phase, {}).get("evidence")
    if not name:
        return None
    try:
        # A phase's evidence carries the whole source identity, far past the reader's
        # 16 KiB default, so it is read up to `MAX_LOG` as the coverage parts' is.
        evidence = json.loads(runner.private_bytes(runner.RUN / name,
                                                   maximum=runner.MAX_LOG))
    except (OSError, ValueError):
        return None
    kept = evidence.get("keptEvidence") if isinstance(evidence, dict) else None
    return runner.RUN / kept if kept else None


def read_record(runner, path: Path) -> dict | None:
    try:
        value = json.loads(runner.private_bytes(path))
    except (OSError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def check_record_problems(runner, screen: str, path: Path) -> list[str]:
    """One `a11y-check-<screen>.json` against Step 95(g): no violation, contrast
    evaluated, no sideways scroll, its capture kept beside it with the same SHA-256, and
    its live regions (L1-55)."""
    record_ = read_record(runner, path)
    if record_ is None:
        return [f"{screen}: unreadable check record"]
    problems = []
    if record_.get("violations") != []:
        problems.append(f"{screen}: violations")
    if record_.get("colorContrastEvaluated") is not True:
        problems.append(f"{screen}: color contrast not evaluated")
    if record_.get("sidewaysScroll") is not False:
        problems.append(f"{screen}: sideways scroll")
    capture = record_.get("capture")
    kept = path.parent / capture if isinstance(capture, str) and "/" not in capture else None
    if (kept is None or kept.is_symlink() or not kept.is_file()
            or file_sha256(kept) != record_.get("captureSha256")):
        problems.append(f"{screen}: capture missing or changed")
    problems.extend(live_region_problems(screen, record_))
    return problems


def live_region_problems(screen: str, record_: dict) -> list[str]:
    """With the app shell, exactly one live region outside `#main` is the announcer
    (`status`, `polite`), and every other one there is `nav-loading` or `nav-error`;
    regions inside `#main` are kept and not judged. Without it, no announcer is needed."""
    shell, regions = record_.get("appShell"), record_.get("liveRegions")
    if not isinstance(shell, bool) or not isinstance(regions, list):
        return [f"{screen}: no live regions record"]
    if not shell:
        return []
    outside = [item for item in regions
               if isinstance(item, dict) and item.get("insideMain") is not True]
    announcers = [item for item in outside if item.get("testId") == "announcer"]
    if len(announcers) != 1 or announcers[0].get("role") != "status" or (
            announcers[0].get("ariaLive") != "polite"):
        return [f"{screen}: announcer missing or not a polite status"]
    if any(item.get("testId") not in NAV_REGIONS for item in outside
           if item is not announcers[0]):
        return [f"{screen}: another live region outside #main"]
    return []


def a11y_evidence(runner, phases: dict[str, dict]) -> list[str]:
    """Every screen of `A11Y_SCREENS` in its phase's kept evidence: at least one check
    record, every check record of that name passing, and at least one keyboard and one
    focus visit record. The problems found; none means the records hold."""
    problems = []
    for screen, phase in sorted(A11Y_SCREENS.items()):
        folder = kept_folder(runner, phases, phase)
        if folder is None or folder.is_symlink() or not folder.is_dir():
            problems.append(f"{screen}: no kept evidence of {phase}")
            continue
        checks = sorted(folder.rglob(f"a11y-check-{screen}.json"))
        if not checks:
            problems.append(f"{screen}: no check record")
        for path in checks:
            problems.extend(check_record_problems(runner, screen, path))
        for kind in ("keyboard", "focus"):
            if not any(folder.rglob(f"a11y-{kind}-{screen}.json")):
                problems.append(f"{screen}: no {kind} visit record")
    return problems


def browser_phase(name: str):
    def run(runner, path: Path) -> dict:
        return run_browser(runner, name, path)

    return run


PHASE_RUNNERS = {
    **{phase: browser_phase(phase) for phase in BROWSER_SPECS if phase != "security"},
    "security": run_security,
    "restore-paths": run_restore_paths,
    "repair-exercise": run_repair_exercise,
    "restart-host": run_restart_host,
    "restart-database": run_restart_database,
}
PHASES = {
    "fixtures": run_fixtures, "serve": run_serve, **PHASE_RUNNERS,
    "build-gate": run_build_gate, "compatibility": run_compatibility,
    "performance": run_performance, "frontend": run_frontend,
    "arrangement": run_arrangement, "verification-run": run_verification,
    # Step 114(h): on demand only, in neither `PHASE_RUNNERS` nor `VERIFICATION_ORDER`.
    "capacity-burst": run_capacity_burst,
}
