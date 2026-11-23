"""Step 43's phase programs (`scripts/u8_phases.py`) under a stand-in runner.

Every phase program takes the runner as an argument, so here the runner is a stand-in
that keeps the real one's constants and JUnit check but stands in at the two outward
seams: the bounded child (`bounded_process`, which here writes the report or record the
child would have written and answers with its supervision) and the private evidence
writer. Each phase's own decisions — what it runs, what it records, when it fails — run
for real. Nothing here starts a process, a browser or a database; three tests use the
live realm: the operations store's horizon test reads and writes the realm's own
operations store, so the restart's horizon rule runs on PostgreSQL itself; the capacity
burst's jobs test writes and ends its research rows; and the SCRAM logins test times
logins through the realm's owner logins (Step 135(b)), running no statement.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import hashlib
import json
import os
import re
import secrets
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

PASSING = ('<testsuite><testcase classname="c" name="[J09] journey"/></testsuite>')
FAILING = ('<testsuite><testcase classname="c" name="[J09] journey">'
           "<failure>no</failure></testcase></testsuite>")


@pytest.fixture
def runner():
    from scripts import verify_docsuri_u8

    return verify_docsuri_u8


@pytest.fixture
def phases(runner):
    scripts = str(Path(runner.ROOT) / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    import u8_phases

    return u8_phases


def private(path: Path, text: str) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        stream.write(text)


class StandIn:
    """The runner's names the phase programs read, with the process seam scripted."""

    def __init__(self, run: Path, runner, *, exit_code: int = 0, report: str = PASSING,
                 log_line: str | None = None, on_run=None):
        self.RUN, self.Refused, self.PYTHON = run, runner.Refused, runner.PYTHON
        self.PHASE_SECONDS, self.PYTEST_INI = runner.PHASE_SECONDS, runner.PYTEST_INI
        self.MAX_LOG, self.private_bytes = runner.MAX_LOG, runner.private_bytes
        self.junit_counts, self.EVIDENCE_PATTERN = runner.junit_counts, runner.EVIDENCE_PATTERN
        self.child_environment = runner.child_environment
        self.exit_code, self.report, self.log_line, self.on_run = (
            exit_code, report, log_line, on_run)
        self.commands: list[list[str]] = []
        self.evidence: dict[str, dict] = {}
        self.stopped = []

    def prepare_phase(self, path):
        return {"runId": "run-1", "container": "docsuri-u8-run-1"}, {"hostFreeBytes": 1}

    def bounded_process(self, args, log, *, seconds, environment, **options):
        assert 0 < seconds <= self.PHASE_SECONDS and "PYTHONPATH" in environment
        self.commands.append(args)
        for arg in args:
            if arg.startswith("--junitxml=") or arg.startswith("--outputFile="):
                private(Path(arg.split("=", 1)[1]), self.report)
        if "PLAYWRIGHT_JUNIT_OUTPUT_FILE" in environment:
            private(Path(environment["PLAYWRIGHT_JUNIT_OUTPUT_FILE"]), self.report)
        if self.on_run is not None:
            self.on_run(args)
        private(log, (self.log_line or "") + "\n")
        return {"reason": options.get("allow_bounded_stop") and "bounded-stop"
                or "process-exit", "exitCode": self.exit_code}

    def private_json(self, path, value):
        self.evidence[path.name.split("-evidence-")[0]] = value
        private(path, json.dumps(value))

    def require_test_paths(self, paths, *, root=None):
        if root is not None:
            # Another checkout's listing (a tag worktree): faked as holding the paths.
            self.commands.append(["listed", str(root), *paths])
            return
        missing = [item for item in paths if not (self_root() / item.split("::")[0]).exists()]
        if missing:
            raise self.Refused(f"missing test paths: {missing}")

    def release_identity(self, root):
        return None

    def native(self, value):
        return False

    def command(self, args, **options):
        self.commands.append(args)
        return subprocess.CompletedProcess(args, 0, "", "")

    def require(self, args, **options):
        self.commands.append(args)
        stdout = ('[{"State": {"StartedAt": "2026-11-11T00:00:00.5Z"}}]'
                  if args[:2] == ["docker", "inspect"] else "")
        return subprocess.CompletedProcess(args, 0, stdout, "")

    def signal_group(self, pid, signum):
        self.commands.append(["signal", str(pid), str(int(signum))])

    def group_states(self, pid):
        return []

    def preserve_prior_report(self, phase):
        return []

    def source_identity(self):
        return {"sha256": "same"}

    def v1_serving(self):
        return True

    def stop(self, process):
        self.stopped.append(process)


def self_root() -> Path:
    from scripts import verify_docsuri_u8

    return Path(verify_docsuri_u8.ROOT)


# --- the record and the bounded child --------------------------------------------------------


def test_a_passing_record_names_its_evidence_and_a_failing_one_refuses(runner, phases, tmp_path):
    stand_in = StandIn(tmp_path, runner)
    assert phases.record(stand_in, "frontend", {"phase": "frontend", "exitCode": 0})[
        "state"] == "passed"
    with pytest.raises(runner.Refused, match="U8 phase frontend failed"):
        phases.record(stand_in, "frontend", {"phase": "frontend", "exitCode": 1})


def test_a_child_that_raises_is_a_failure_with_its_category(runner, phases, tmp_path):
    stand_in = StandIn(tmp_path, runner)

    def refusing(args, log, **options):
        error = runner.Refused("over budget")
        error.supervision = {"reason": "rss"}
        raise error

    stand_in.bounded_process = refusing
    result = phases.run_child(stand_in, "frontend", ["x"], 0.0 + phases.time.monotonic())
    assert result["exitCode"] == 1 and result["failureCategory"] == "Refused"
    assert result["supervision"] == {"reason": "rss"}


# --- fixtures and the corpus -----------------------------------------------------------------


def corpus_record(run: Path, *, papers: int, target: int = 600) -> None:
    private(run / "fixtures" / "corpus.json", json.dumps({
        "version": "u8-corpus-v1", "papers": papers, "target": target,
        "complete": papers == target, "remaining": target - papers, "presentAtStart": 0,
        "importedThisRun": papers, "chunksPerPaper": 100}))


@pytest.mark.parametrize("mode", ["load", "skip", "only"])
def test_the_fixtures_run_names_its_corpus_mode_to_the_child_and_records_it(
        runner, phases, tmp_path, mode):
    corpus_record(tmp_path, papers=600)
    stand_in = StandIn(tmp_path, runner)
    stand_in.FIXTURES_CORPUS = "load"
    result = phases.run_fixtures(stand_in, tmp_path / "environment.json",
                                 corpus_mode=None if mode == "load" else mode)
    assert stand_in.commands[0][-2:] == ["--corpus", mode]
    recorded = json.loads((tmp_path / "fixtures" / "phase.json").read_text())
    assert recorded["corpusMode"] == mode
    if mode == "skip":
        assert result["state"] == "corpus-skipped" and recorded["corpus"] == "skipped"
    else:
        assert result["state"] == "fixtures-ready" and recorded["corpus"]["papers"] == 600


def test_an_unfinished_corpus_is_counted_and_a_failed_fixtures_child_refuses(
        runner, phases, tmp_path):
    corpus_record(tmp_path, papers=250)
    stand_in = StandIn(tmp_path, runner)
    result = phases.run_fixtures(stand_in, tmp_path / "environment.json")
    assert result == {"state": "corpus-incomplete", "phase": "fixtures", "papers": 250,
                      "target": 600, "remaining": 350}
    with pytest.raises(runner.Refused, match="fixtures failed"):
        phases.run_fixtures(StandIn(tmp_path, runner, exit_code=1),
                            tmp_path / "environment.json")


def test_the_corpus_is_resumed_run_by_run_until_complete(runner, phases, tmp_path):
    corpus_record(tmp_path, papers=300)
    runs = iter((450, 600))
    stand_in = StandIn(tmp_path, runner,
                       on_run=lambda args: corpus_record(tmp_path, papers=next(runs)))
    assert phases.complete_corpus(stand_in, tmp_path / "environment.json") == {
        "state": "passed", "papers": 600}
    assert len(stand_in.commands) == 2
    assert all(command[-1] == "only" for command in stand_in.commands)


def test_a_corpus_still_incomplete_after_its_runs_fails_with_its_counts(
        runner, phases, tmp_path):
    corpus_record(tmp_path, papers=10)
    stand_in = StandIn(tmp_path, runner)
    result = phases.complete_corpus(stand_in, tmp_path / "environment.json")
    assert result["state"] == "failed" and "(10 of 600 papers)" in result["reason"]
    assert len(stand_in.commands) == phases.CORPUS_RUNS


# --- the pytest-backed phases ----------------------------------------------------------------


def test_restore_paths_records_its_logins_and_no_superuser(runner, phases, tmp_path):
    stand_in = StandIn(tmp_path, runner)
    phases.run_restore_paths(stand_in, tmp_path / "environment.json")
    evidence = stand_in.evidence["restore-paths"]
    assert evidence["superuser"] is False and evidence["tests"] == 1
    assert evidence["logins"] == ["docsuri_restore", "docsuri_scheduler"]


def test_restore_paths_fails_on_a_failing_report(runner, phases, tmp_path):
    with pytest.raises(runner.Refused):
        phases.run_restore_paths(StandIn(tmp_path, runner, report=FAILING),
                                 tmp_path / "environment.json")


def test_security_stops_at_a_failing_backend_half_before_any_browser(runner, phases, tmp_path):
    stand_in = StandIn(tmp_path, runner, exit_code=1)
    with pytest.raises(runner.Refused, match="security failed"):
        phases.run_security(stand_in, tmp_path / "environment.json")
    assert stand_in.evidence["security"]["backend"]["exitCode"] == 1
    assert len(stand_in.commands) == 1  # the backend half only


def test_the_frontend_lane_runs_vitest_with_coverage_under_its_config(runner, phases, tmp_path):
    stand_in = StandIn(tmp_path, runner)
    phases.run_frontend(stand_in, tmp_path / "environment.json")
    command = stand_in.commands[0]
    assert "vitest" in command and "--coverage" in command
    assert command[command.index("--config") + 1] == phases.VITEST_CONFIG


def test_the_build_gate_reads_the_builds_last_line_and_fails_without_one(
        runner, phases, tmp_path):
    stand_in = StandIn(tmp_path, runner, log_line=json.dumps({"state": "built"}))
    phases.run_build_gate(stand_in, tmp_path / "environment.json")
    assert stand_in.evidence["build-gate"]["build"] == {"state": "built"}
    with pytest.raises(runner.Refused):
        phases.run_build_gate(StandIn(tmp_path, runner, log_line="not json"),
                              tmp_path / "environment.json")


def test_compatibility_is_skipped_saying_so_while_no_v2_tag_exists(
        runner, phases, tmp_path, monkeypatch):
    monkeypatch.setattr(phases, "previous_tag", lambda: None)
    stand_in = StandIn(tmp_path, runner)
    phases.run_compatibility(stand_in, tmp_path / "environment.json")
    evidence = stand_in.evidence["compatibility"]
    assert evidence["skipped"] is True and evidence["skippedReason"] == "no v2 tag exists yet"
    assert not stand_in.commands


def test_the_arrangement_is_refused_anywhere_but_macos(runner, phases, tmp_path, monkeypatch):
    monkeypatch.setattr(phases.sys, "platform", "linux")
    with pytest.raises(runner.Refused, match="only on macOS"):
        phases.run_arrangement(StandIn(tmp_path, runner), tmp_path / "environment.json")


# --- the served realm and the browser phases ---------------------------------------------------


def test_the_serve_phase_passes_only_on_reaching_its_bound(runner, phases, tmp_path):
    stand_in = StandIn(tmp_path, runner)
    phases.run_serve(stand_in, tmp_path / "environment.json")
    assert stand_in.evidence["serve"]["completionVerification"] is False


def test_the_served_realm_takes_the_identity_scenario_only_when_the_fixtures_wrote_one(
        runner, phases, tmp_path):
    stand_in = StandIn(tmp_path, runner)
    path = tmp_path / "environment.json"
    assert "--identity-scenario" not in phases.serve_command(stand_in, path, staged=False)
    private(tmp_path / "identity-scenario.json", "{}")
    args = phases.serve_command(stand_in, path, staged=False)
    assert args[args.index("--identity-scenario") + 1] == str(
        tmp_path / "identity-scenario.json")
    assert "tests.u8_service_operations_integration.cutover_stage" in phases.serve_command(
        stand_in, path, staged=True)


def test_every_journey_phase_leaves_out_the_perf_measurement_and_performance_runs_it_alone(
        phases):
    journeys = phases.playwright_args(("journeys.spec.ts",))
    measured = phases.playwright_args(("navigation.spec.ts",), perf=True)
    assert journeys[-2:] == ["--grep-invert", phases.PERF]
    assert measured[-2:] == ["--grep", phases.PERF]


def test_a_browser_phase_whose_build_fails_records_the_failure_and_starts_no_realm(
        runner, phases, tmp_path):
    stand_in = StandIn(tmp_path, runner, exit_code=1)
    with pytest.raises(runner.Refused, match="browser-recovery failed"):
        phases.run_browser(stand_in, "browser-recovery", tmp_path / "environment.json")
    evidence = stand_in.evidence["browser-recovery"]
    assert evidence["failureReason"] == "the workspace build failed"
    assert evidence["specs"] == ["recovery.spec.ts"] and not stand_in.stopped


def test_a_browser_phases_output_is_kept_out_of_the_folder_the_next_run_empties(
        runner, phases, tmp_path):
    stand_in = StandIn(tmp_path, runner)
    assert phases.keep_browser_evidence(stand_in, "browser-lifecycle") is None
    private(tmp_path / "browser-evidence" / "j08" / "error-context.md", "the page")
    kept = phases.keep_browser_evidence(stand_in, "browser-lifecycle")
    assert kept.startswith("kept-evidence/browser-lifecycle-")
    assert (tmp_path / kept / "j08" / "error-context.md").read_text() == "the page"
    assert not (tmp_path / "browser-evidence").exists()


def test_the_stage_is_not_ready_without_its_socket(phases, tmp_path):
    assert phases.stage_ready(tmp_path / "absent.sock") is False


# --- performance -------------------------------------------------------------------------------


def test_the_95th_percentile_is_nearest_rank_and_empty_is_none(phases):
    assert phases.percentile([]) is None
    assert phases.percentile([5.0]) == 5.0
    assert phases.percentile([float(value) for value in range(1, 101)]) == 95.0


def test_a_plan_uses_an_index_found_anywhere_in_its_tree(phases):
    plan = [{"Plan": {"Node Type": "Limit", "Plans": [
        {"Node Type": "Index Scan", "Index Name": "projection_embedding_hnsw"}]}}]
    assert phases.plan_uses(plan, "projection_embedding_hnsw")
    assert not phases.plan_uses(plan, "version_lexical_all")
    assert not phases.plan_uses("text", "projection_embedding_hnsw")


def test_the_planner_settings_are_read_from_the_production_template(phases):
    settings = phases.production_planner()
    assert settings and set(settings) <= set(phases.PLANNER_SETTINGS)


WINDOW = {"observedFrom": "2026-10-10T00:00:00Z", "observedUntil": "2026-10-24T00:00:00Z",
          "requests": 9000, "peakAt": "2026-10-20T09:00:00Z"}
HOUR = 3600


def handed_over(**value) -> dict:
    return {"DOCSURI_U8_V1_INVENTORY": json.dumps({"inventoryId": "inv-1", **WINDOW, **value})}


def test_the_local_mode_records_v1s_rate_as_not_yet_available_and_passes(phases):
    v1 = phases.v1_request_rate(install=False, environ={})
    assert v1["state"] == "v1-rate-not-yet-available" and v1["requestsPerSecond"] is None
    assert phases.rate_check(3.69, v1) is None
    # Twenty users acting every five seconds: about four requests a second.
    assert phases.USERS / phases.ACT_SECONDS == 4.0


@pytest.mark.parametrize("environ", [
    {},
    {"DOCSURI_U8_V1_INVENTORY": "not json"},
    {"DOCSURI_U8_V1_INVENTORY": json.dumps({"inventoryId": "inv-1", **WINDOW})},
    handed_over(peakRequests=-1, intervalSeconds=HOUR),
    handed_over(peakRequests=True, intervalSeconds=HOUR),
    handed_over(peakRequests=9, intervalSeconds=0),
])
def test_the_install_mode_fails_without_the_inventorys_count(phases, environ):
    v1 = phases.v1_request_rate(install=True, environ=environ)
    assert v1["state"] == "v1-rate-missing"
    assert phases.rate_check(3.69, v1) == "v1-rate-missing"


def test_the_install_mode_fails_when_v1s_peak_is_higher_and_passes_when_lower(phases):
    busy = phases.v1_request_rate(install=True, environ=handed_over(
        peakRequests=5 * HOUR, intervalSeconds=HOUR))
    assert busy["requestsPerSecond"] == 5.0
    assert busy["source"]["peakRequests"] == 5 * HOUR
    assert busy["source"]["intervalSeconds"] == HOUR
    assert phases.rate_check(3.69, busy) == "v1-rate-higher"
    quiet = phases.v1_request_rate(install=True, environ=handed_over(
        peakRequests=36, intervalSeconds=HOUR))
    assert quiet["requestsPerSecond"] == 0.01 and phases.rate_check(3.69, quiet) is None


def test_the_install_wiring_hands_over_the_newest_inventory_from_an_export():
    from docsuri_ops.production_wiring import v1_inventory

    def counted(identifier, until, peak):
        return {"inventoryId": identifier, "source": "cloudflare-export",
                "observedFrom": "2026-10-01T00:00:00Z", "observedUntil": until,
                "requests": 100, "peakRequests": peak, "peakAt": "2026-10-02T00:00:00Z",
                "intervalSeconds": HOUR, "consumers": [], "complete": True}

    older, newer = counted("a", "2026-10-15T00:00:00Z", 5), counted("b", "2026-10-24T00:00:00Z", 9)
    known_only = {"inventoryId": "c", "observedFrom": "2026-10-11T00:00:00Z",
                  "observedUntil": "2026-10-25T00:00:00Z", "consumers": [], "complete": True}
    ledger = SimpleNamespace(records=lambda kind: [older, newer, known_only]
                             if kind == "consumer-inventory" else [])
    handed = v1_inventory(ledger)
    assert handed["inventoryId"] == "b" and handed["peakRequests"] == 9
    assert "consumers" not in handed
    assert v1_inventory(SimpleNamespace(records=lambda kind: [known_only])) is None


def test_the_backup_deadline_is_the_inventorys_single_backup_protocol(phases):
    assert phases.backup_deadline() == 1800


def test_the_host_latency_is_each_classs_largest_window_written_during_the_load(
        phases, tmp_path):
    # Every window carries the same realm-clock stamp, a day ahead, as the fixture clock
    # leaves it: only where a line sits in the file says whether the load wrote it.
    stamp = "2026-10-24T15:49:34Z"
    folder = tmp_path / "evidence" / "latency"
    folder.mkdir(parents=True)

    def window(cls: str, p95: float | None, count: int = 5) -> str:
        return json.dumps({"window": stamp, "class": cls, "p95Ms": p95, "count": count}) + "\n"

    day = folder / "2026-10-24.jsonl"
    day.write_text(window("read", 2000.0) + window("search", 9000.0))  # earlier journeys
    offsets = phases.latency_offsets(tmp_path)
    with day.open("a") as stream:
        stream.write(window("read", 50.0) + window("read", 100.0) + window("search", 2000.0)
                     + window("health", 25.0) + window("accept", 500.0, count=0)
                     + window("navigation", None) + "not json\n")
    (folder / "2026-10-25.jsonl").write_text(window("health", 10.0))  # a new day's file
    assert phases.latency_summaries(tmp_path, offsets=offsets) == {
        "read": 100.0, "search": 2000.0, "health": 25.0}
    assert phases.latency_summaries(tmp_path / "absent", offsets={}) == {}
    assert phases.latency_offsets(tmp_path / "absent") == {}


# --- the verification run's journeys -------------------------------------------------------


def test_a_journey_passes_only_when_every_test_naming_it_passed(runner, phases, tmp_path):
    private(tmp_path / "r.xml", (
        '<testsuite><testcase name="[J04] one"/><testcase name="[J04] two">'
        '<failure>no</failure></testcase><testcase name="[J05] three"/></testsuite>'))
    assert phases.journeys_of(tmp_path / "r.xml", SimpleNamespace(
        private_bytes=runner.private_bytes, MAX_LOG=runner.MAX_LOG)) == {
        "J04": "failed", "J05": "passed"}
    assert phases.journeys_of(tmp_path / "absent.xml", SimpleNamespace(
        private_bytes=runner.private_bytes, MAX_LOG=runner.MAX_LOG)) == {}


# --- Step 97(c): the phase helpers ---------------------------------------------------------------


class Changing(StandIn):
    """A `StandIn` whose source identity answers one digest on its first call and another
    from its second call on, which comes at the phase's end (Step 97(c) item 1)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.identities = 0

    def source_identity(self):
        self.identities += 1
        return {"sha256": "first" if self.identities == 1 else "second"}


class Realm:
    """A stand-in served realm process."""

    def __init__(self, pid: int = 4242):
        self.pid = pid

    def poll(self):
        return None

    def wait(self, timeout=None):
        return -9


LOAD = {"users": 20, "seconds": 60, "actSeconds": 5.0,
        "p95Ms": {"health": 20.0, "api-read": 100.0, "search": 900.0},
        "samples": {"health": 50, "api-read": 120, "search": 120}, "refusals": {},
        "readiness": {"samples": 50, "notReady": 0, "admissionClosed": 0, "missing": {},
                      "unanswered": 0},
        "sent": {"settings-read": 60, "session-read": 60, "search": 120},
        "requestsPerSecond": 4.0}
# The SCRAM logins' measured summary the stand-in phase is given (Step 135(d)).
SCRAM = {"planned": 220, "logins": 220, "failedLogins": 0, "failures": {}, "p95Ms": 4.0,
         "reconsiderPool": False, "measured": True}
# Vector storage as run 5 measured it at 60,000 chunks (Step 166): 4,100 B a value, one
# 8,192 B index page a chunk and one more, and that run's database size.
STORAGE = {"chunks": 60_000, "vectorBytes": 246_000_000, "indexBytes": 491_528_192,
           "arrayBytes": 492_000_000, "tableBytes": 1_000_000_000,
           "databaseBytes": 1_569_127_447, "walBytes": 16_777_216}
VERSIONS = {"postgresql": "16.14", "pgvector": "0.8.7", "python": "3.13.7",
            "ollama": "stand-in", "cloudflared": "stand-in", "release": None,
            "pins": {"postgresql": "16.14", "pgvector": "0.8.7", "ollama": "0.40.7",
                     "cloudflared": "2026.10.3", "python": "3.13.7"}}


def browser_ready(phases, monkeypatch, stand_in) -> list:
    """`run_browser`'s build and served realm faked; the realms it started."""
    started = []
    monkeypatch.setattr(phases, "build_assets", lambda runner_, at: {"exitCode": 0})
    monkeypatch.setattr(phases, "start_realm", lambda runner_, path, log, *, staged: (
        started.append(log) or Realm()))
    return started


def performance_ready(phases, monkeypatch, tmp_path, *, load=None, versions=None,
                      scram_logins=None, latency_counts=None, storage=None) -> dict:
    """`run_performance`'s corpus, EXPLAIN, versions, backup, build and served realm faked,
    with the load faked to keep the `sample_memory` it is given (Step 97(c) item 1, (k),
    (l)); the SCRAM logins answer a measured summary, recording the source they were
    given, and the host's counts answer the load's answered reads (Step 135(d)), each
    replaceable by a keyword. The calls each fake received."""
    corpus_record(tmp_path, papers=600)
    private(tmp_path / "fixtures" / "browser.json", json.dumps({"accounts": {}}))
    seen: dict = {"versions": [], "load": [], "scram": []}

    def scram(source):
        seen["scram"].append(source)
        return dict(SCRAM)

    monkeypatch.setattr(phases, "scram_logins", scram_logins or scram)
    monkeypatch.setattr(phases, "latency_counts", latency_counts or (
        lambda run, *, offsets: {"read": LOAD["samples"]["api-read"]}))
    monkeypatch.setattr(phases, "explain_check", lambda connect: {"meaningUsesHnsw": True})
    # Step 165: the vector-storage reading, faked like the EXPLAIN check beside it; the
    # check of its figures is the phase's own.
    monkeypatch.setattr(phases, "vector_storage", lambda connect: dict(storage or STORAGE))

    def measured(connect, *, release):
        seen["versions"].append(release)
        return versions or VERSIONS

    def loaded(runner_, fixtures, search, *, seconds, sample_memory=None):
        seen["load"].append(sample_memory)
        return load or {**LOAD, "memory": None}

    monkeypatch.setattr(phases, "measured_versions", measured)
    monkeypatch.setattr(phases, "measure_backup", lambda runner_: {
        "outcome": "succeeded", "seconds": 10.0, "deadlineSeconds": 1800})
    monkeypatch.setattr(phases, "build_assets", lambda runner_, at: {"exitCode": 0})
    monkeypatch.setattr(phases, "release_build", lambda runner_: {"source": "release-dist"})
    monkeypatch.setattr(phases, "start_realm", lambda runner_, path, log, *, staged: Realm())
    monkeypatch.setattr(phases, "load", loaded)
    return seen


def browser_timings(run: Path):
    """The performance phase's browser child writes its timings (`perf-browser.json`)."""
    def write(args):
        if any("navigation.spec.ts" in arg for arg in args):
            private(run / "perf-browser.json", json.dumps({
                "firstLoadMs": [900.0], "navigationMs": [300.0], "acceptMs": [400.0]}))
    return write


def restart_ready(phases, monkeypatch) -> None:
    """The restart phases' readiness, horizon and tree steps faked."""
    monkeypatch.setattr(phases, "wait_first_ready", lambda runner_, process, deadline: True)
    monkeypatch.setattr(phases, "read_horizon", lambda runner_, value: 7)
    monkeypatch.setattr(phases, "wait_ready_afresh",
                        lambda runner_, value, process, horizon, begun, deadline: 12.5)
    monkeypatch.setattr(phases, "hold_tree", lambda *args: None)


def test_every_test_running_phase_fails_on_a_source_change(
        runner, phases, tmp_path, monkeypatch):
    path = tmp_path / "environment.json"

    def refused(name: str, run, phase: str, stand_in) -> None:
        with pytest.raises(runner.Refused):
            run(stand_in, path)
        evidence = stand_in.evidence[phase]
        assert evidence["sourceChangedDuringRun"] is True, name
        assert evidence["exitCode"] == 1, name

    stand_in = Changing(tmp_path, runner)
    browser_ready(phases, monkeypatch, stand_in)
    monkeypatch.setattr(phases, "keep_browser_evidence", lambda runner_, phase: None)
    refused("browser", lambda r, p: phases.run_browser(r, "browser-journeys", p),
            "browser-journeys", stand_in)
    refused("restore-paths", phases.run_restore_paths, "restore-paths",
            Changing(tmp_path, runner))
    # The security phase: the change is seen at the end of either half.
    refused("security, its backend half failing", phases.run_security, "security",
            Changing(tmp_path, runner, exit_code=1))
    refused("security, its backend half passing", phases.run_security, "security",
            Changing(tmp_path, runner))
    refused("frontend", phases.run_frontend, "frontend", Changing(tmp_path, runner))
    monkeypatch.setattr(phases.sys, "platform", "darwin")
    refused("arrangement", phases.run_arrangement, "arrangement", Changing(tmp_path, runner))
    monkeypatch.setattr(phases, "previous_tag", lambda: "v2.0.0")
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / ".docsuri-u8" / "compatibility-v2.0.0").mkdir(parents=True)
    refused("compatibility", phases.run_compatibility, "compatibility",
            Changing(tmp_path, runner))
    refused("build-gate", phases.run_build_gate, "build-gate",
            Changing(tmp_path, runner, log_line=json.dumps({"state": "built"})))
    performance_ready(phases, monkeypatch, tmp_path)
    refused("performance", phases.run_performance, "performance",
            Changing(tmp_path, runner, on_run=browser_timings(tmp_path)))
    # The repair exercise, with its checkout and checks faked; its worktree removal names
    # a folder outside any repository.
    monkeypatch.setattr(phases, "ROOT", tmp_path)
    monkeypatch.setattr(phases, "repair_tree", lambda runner_: (tmp_path / "tree", "clean"))
    monkeypatch.setattr(phases, "run_repair_checks", lambda runner_, tree, started, name: {
        "exitCode": 1, "failures": 1, "traced": {"location": phases.RESOLVER}}
        if name == "repair-defect" else {"exitCode": 0, "tests": 3, "failures": 0})
    refused("repair-exercise", phases.run_repair_exercise, "repair-exercise",
            Changing(tmp_path, runner))
    restart_ready(phases, monkeypatch)
    for kind in ("host", "database"):
        stand_in = Changing(tmp_path, runner)
        stand_in.command = lambda args, **options: subprocess.CompletedProcess(
            args, 0, phases.CRASH_RECOVERY, "")
        refused(f"restart-{kind}", lambda r, p, kind=kind: phases.run_restart(r, p, kind),
                f"restart-{kind}", stand_in)


class Arrangement(StandIn):
    """The arrangement's runner: every command and the report's read, in order."""

    def __init__(self, *args, chown: int = 0, **kwargs):
        super().__init__(*args, **kwargs)
        self.events: list[str] = []
        self.chown = chown
        read = self.junit_counts

        def counted(report, evidence):
            self.events.append("read")
            read(report, evidence)

        self.junit_counts = counted

    def command(self, args, **options):
        self.commands.append(args)
        self.events.append("chown")
        return subprocess.CompletedProcess(args, self.chown, "", "")


def arrangement(runner, tmp_path, **options) -> Arrangement:
    return Arrangement(tmp_path, runner, **options)


def test_the_arrangement_report_is_the_runners_before_it_is_read(
        runner, phases, tmp_path, monkeypatch):
    monkeypatch.setattr(phases.sys, "platform", "darwin")
    path = tmp_path / "environment.json"
    report, coverage = tmp_path / "arrangement.xml", tmp_path / ".coverage-u8-macos"
    stand_in = arrangement(runner, tmp_path)
    phases.run_arrangement(stand_in, path)
    child = stand_in.commands[0]
    assert child[:3] == ["sudo", "-n", "env"]
    assert f"COVERAGE_FILE={coverage}" in child and "PYTHONDONTWRITEBYTECODE=1" in child
    assert child[child.index("-p") + 1] == "no:cacheprovider"
    assert stand_in.commands[1] == ["sudo", "-n", "/usr/sbin/chown", str(os.getuid()),
                                    str(report)]
    assert stand_in.events == ["chown", "read"]
    assert stand_in.evidence["arrangement"]["exitCode"] == 0
    # With the coverage data written too, both files are handed back in one chown.
    stand_in = arrangement(runner, tmp_path, on_run=lambda args: private(coverage, "data"))
    phases.run_arrangement(stand_in, path)
    assert stand_in.commands[1] == ["sudo", "-n", "/usr/sbin/chown", str(os.getuid()),
                                    str(report), str(coverage)]
    coverage.unlink()
    # A report `private_bytes` refuses (mode 0644) is an invalid report.
    stand_in = arrangement(runner, tmp_path, on_run=lambda args: report.chmod(0o644))
    with pytest.raises(runner.Refused):
        phases.run_arrangement(stand_in, path)
    evidence = stand_in.evidence["arrangement"]
    assert evidence["invalidTestReport"] is True and evidence["exitCode"] == 1
    # A child that wrote no report: no chown of it, and a missing report.
    stand_in = arrangement(runner, tmp_path, on_run=lambda args: report.unlink())
    with pytest.raises(runner.Refused):
        phases.run_arrangement(stand_in, path)
    assert len(stand_in.commands) == 1 and stand_in.events == ["read"]
    evidence = stand_in.evidence["arrangement"]
    assert evidence["missingTestReport"] is True and evidence["exitCode"] == 1
    # A chown answering 1 is recorded, never raised.
    stand_in = arrangement(runner, tmp_path, chown=1)
    with pytest.raises(runner.Refused):
        phases.run_arrangement(stand_in, path)
    evidence = stand_in.evidence["arrangement"]
    assert evidence["failureCategory"] == "report-owner-unchanged"
    assert evidence["exitCode"] == 1 and stand_in.events == ["chown", "read"]


def captures_child(run: Path, screens: tuple[str, ...]):
    def write(args):
        for screen in screens:
            private(run / "browser-evidence" / "a-test" / f"320-{screen}.png", f"png {screen}")
    return write


def test_the_accessibility_phase_fails_without_every_320_capture(
        runner, phases, tmp_path, monkeypatch):
    monkeypatch.setattr(phases, "CAPTURES", {"accessibility": ("entry", "privacy"),
                                             "browser-migration": ("consent-step",),
                                             "browser-cutover": ("maintenance-notice",)})
    path = tmp_path / "environment.json"
    stand_in = StandIn(tmp_path, runner, on_run=captures_child(tmp_path, ("entry", "privacy")))
    browser_ready(phases, monkeypatch, stand_in)
    phases.run_browser(stand_in, "accessibility", path)
    evidence = stand_in.evidence["accessibility"]
    kept = evidence["keptEvidence"]
    assert re.fullmatch(r"kept-evidence/accessibility-\d+", kept)
    assert evidence["captures"] == [
        {"screen": screen, "path": f"{kept}/a-test/320-{screen}.png",
         "sha256": hashlib.sha256(f"png {screen}".encode()).hexdigest()}
        for screen in ("entry", "privacy")]
    for phase, screens, written in (("accessibility", ("privacy",), ("entry",)),
                                    ("browser-migration", ("consent-step",), ()),
                                    ("browser-cutover", ("maintenance-notice",), ())):
        stand_in = StandIn(tmp_path, runner, on_run=captures_child(tmp_path, written))
        with pytest.raises(runner.Refused):
            phases.run_browser(stand_in, phase, path)
        evidence = stand_in.evidence[phase]
        assert evidence["missingCaptures"] == list(screens) and evidence["exitCode"] == 1
    monkeypatch.undo()
    assert all(re.fullmatch(r"[a-z0-9-]+", screen)
               for screens in phases.CAPTURES.values() for screen in screens)


ACCESSIBILITY_PHASES = ("accessibility", "accessibility-signed-out", "accessibility-keyboard",
                        "accessibility-screens")
# Step 101(a)'s 17 screens over the two phases of its split.
SPLIT_SCREENS = {
    "accessibility": ("search", "paper", "library", "research", "novelty", "jobs", "topics",
                      "export", "settings", "usage", "account", "operations",
                      "recovery-dialog"),
    "accessibility-signed-out": ("entry", "privacy", "terms", "callback-cancelled"),
}


def test_every_accessibility_phase_is_registered_in_every_list(runner, phases):
    """Step 99(h)'s split rule through Step 101(e): `accessibility` was split, so its
    signed-out half is a phase of its own in each list Step 101(d) names, and A11Y needs
    every accessibility phase (Step 95(g))."""
    assert {phase: phases.BROWSER_SPECS[phase] for phase in ACCESSIBILITY_PHASES} == {
        "accessibility": ("accessibility.spec.ts",),
        "accessibility-signed-out": ("accessibility-signed-out.spec.ts",),
        "accessibility-keyboard": ("accessibility-keyboard.spec.ts",),
        "accessibility-screens": ("accessibility-screens.spec.ts",),
    }
    after = phases.AFTER_CORPUS
    assert after[after.index("security") + 1:after.index("repair-exercise")] == (
        ACCESSIBILITY_PHASES)
    assert phases.A11Y_PHASES == ACCESSIBILITY_PHASES
    step43 = runner.STEP43_PHASES
    start = step43.index("accessibility")
    assert step43[start:start + len(ACCESSIBILITY_PHASES)] == ACCESSIBILITY_PHASES
    assert set(ACCESSIBILITY_PHASES) <= set(runner.PHASES)
    # Step 101(a)'s 17 screens, each once, over the split's two phases.
    assert {phase: phases.CAPTURES[phase] for phase in SPLIT_SCREENS} == SPLIT_SCREENS
    assert sum(len(screens) for screens in SPLIT_SCREENS.values()) == 17
    assert len(phases.CAPTURES["accessibility-screens"]) == 21
    for phase, screens in SPLIT_SCREENS.items():
        assert {phases.A11Y_SCREENS[screen] for screen in screens} == {phase}
    # Each phase's spec exists, and the runner accepts the phase.
    for phase in ACCESSIBILITY_PHASES:
        assert (phases.ROOT / phases.E2E / phases.BROWSER_SPECS[phase][0]).is_file(), phase
        assert phase in phases.PHASE_RUNNERS


class Clock:
    """A monotonic clock moved only by the test and by sleeps."""

    def __init__(self, now: float = 0.0):
        self.now = now

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


def clocked(phases, monkeypatch, clock: Clock) -> None:
    monkeypatch.setattr(phases, "time", SimpleNamespace(
        monotonic=clock.monotonic, sleep=clock.sleep, time=time.time, time_ns=time.time_ns))
    monkeypatch.setattr(phases, "hold_tree", lambda *args: None)


def test_restart_readiness_fails_at_three_minutes(runner, phases, tmp_path, monkeypatch):
    from backend.u8_registry import REQUIRED

    clock = Clock()
    clocked(phases, monkeypatch, clock)
    # 179.9 s passes and 180.0 s fails.
    for answer_at, passes in ((179.9, True), (180.0, False)):
        clock.now = 0.0

        def answer(answer_at=answer_at) -> bool:
            clock.now = answer_at
            return True

        monkeypatch.setattr(phases, "observed_afresh", lambda r, v, h: set(REQUIRED))
        monkeypatch.setattr(phases, "local_ready", answer)
        figure = phases.wait_ready_afresh(SimpleNamespace(), {}, None, 1, 0.0, 300.0)
        if passes:
            assert figure is not None and 179.88 <= figure < phases.RESTART_READY_SECONDS
        else:
            assert figure is None
    # A realm never ready gives up at 180 s, not at the phase's 300 s.
    clock.now = 0.0
    monkeypatch.setattr(phases, "local_ready", lambda: False)
    assert phases.wait_ready_afresh(SimpleNamespace(), {}, None, 1, 0.0, 300.0) is None
    assert phases.RESTART_READY_SECONDS <= clock.now < phases.RESTART_READY_SECONDS + 1
    # A ready answer does not count while a required capability has no row at or after the
    # horizon, rows sharing one `observed_at` with those from before the kill included.
    clock.now = 0.0
    missing = sorted(REQUIRED)[0]
    monkeypatch.setattr(phases, "observed_afresh", lambda r, v, h: set(REQUIRED) - {missing})
    monkeypatch.setattr(phases, "local_ready", lambda: True)
    assert phases.wait_ready_afresh(SimpleNamespace(), {}, None, 1, 0.0, 300.0) is None
    # With less than the wait and its margin left before the deadline, no kill is sent and
    # the phase fails as not ready before the restart.
    stand_in = StandIn(tmp_path, runner)
    clock.now = 0.0
    monkeypatch.setattr(phases, "start_realm", lambda runner_, path, log, *, staged: (
        setattr(clock, "now", 91.0) or Realm()))  # 209 s of 300 s remain
    with pytest.raises(runner.Refused):
        phases.run_restart(stand_in, tmp_path / "environment.json", "host")
    evidence = stand_in.evidence["restart-host"]
    assert evidence["failureReason"] == phases.RESTART_NOT_READY
    assert evidence["restart"] == "host" and evidence["readySeconds"] is None
    assert not any(command[0] == "signal" for command in stand_in.commands)
    monkeypatch.undo()
    # The evidence names the restart and its seconds; for the database, `docker logs
    # --since` takes the container's `State.StartedAt`, and the recovery line decides.
    restart_ready(phases, monkeypatch)
    monkeypatch.setattr(phases, "start_realm", lambda runner_, path, log, *, staged: Realm())
    for line, code in ((phases.CRASH_RECOVERY, 0), ("database system is ready", 1)):
        stand_in = StandIn(tmp_path, runner)
        logs = []
        stand_in.command = lambda args, line=line, logs=logs, **options: (
            logs.append(args) or subprocess.CompletedProcess(args, 0, "", line))
        if code:
            with pytest.raises(runner.Refused):
                phases.run_restart(stand_in, tmp_path / "environment.json", "database")
        else:
            phases.run_restart(stand_in, tmp_path / "environment.json", "database")
        evidence = stand_in.evidence["restart-database"]
        assert evidence["restart"] == "database" and evidence["readySeconds"] == 12.5
        assert evidence["startedAt"] == "2026-11-11T00:00:00.5Z"
        assert logs == [["docker", "logs", "--since", "2026-11-11T00:00:00.5Z",
                         "docsuri-u8-run-1"]]
        assert evidence["crashRecovery"] is (code == 0) and evidence["exitCode"] == code
    stand_in = StandIn(tmp_path, runner)
    phases.run_restart(stand_in, tmp_path / "environment.json", "host")
    evidence = stand_in.evidence["restart-host"]
    assert evidence["restart"] == "host" and evidence["readySeconds"] == 12.5
    assert ["signal", "4242", "9"] in stand_in.commands


def test_only_rows_written_after_the_horizon_count_even_at_one_shared_observed_at(
        runner, phases, transactions, monkeypatch):
    """Step 97(c) item 4 and Step 95(f) on the realm's own store: the real `read_horizon`
    and `observed_afresh` (an `xmin` compare, never `observed_at` or wall time). Rows the
    operations owner writes before and after the horizon share one `observed_at`, as the
    delegated clock gives rows on both sides of a kill; only the later ones count, and a
    ready answer waits while a required capability has only earlier rows. The clock and
    readiness stay injected; the required set is this test's own capabilities, so no other
    test's rows change the result."""
    import secrets as token_source

    import backend.u8_registry as registry
    from backend.modules.operations.observation_store import ObservationRow, ObservationStore

    value = json.loads((runner.RUN / "environment.json").read_text())
    token = token_source.token_hex(4)
    before, after = f"test-{token}-before", f"test-{token}-after"
    shared = dt.datetime.now(dt.UTC).replace(microsecond=0)

    def rows(*names: str) -> list:
        return [ObservationRow(capability=name, producer="test.producer", outcome="available",
                               reason_key=None, observed_at=shared, revision=1,
                               error_count=0, total_count=1) for name in names]

    store = ObservationStore(transactions)
    store.insert(rows(before, after))  # before the "kill"
    horizon = phases.read_horizon(runner, value)
    assert 0 < horizon < 2**32
    assert {before, after} & phases.observed_afresh(runner, value, horizon) == set()
    store.insert(rows(after))  # after it, at the same observed_at
    assert {before, after} & phases.observed_afresh(runner, value, horizon) == {after}
    # A ready answer does not count while `before` has only pre-horizon rows.
    clock = SimpleNamespace(now=0.0)
    monkeypatch.setattr(phases, "time", SimpleNamespace(
        monotonic=lambda: clock.now, sleep=lambda seconds: setattr(clock, "now",
                                                                   clock.now + 60.0),
        time=time.time, time_ns=time.time_ns))
    monkeypatch.setattr(phases, "hold_tree", lambda *args: None)
    monkeypatch.setattr(phases, "local_ready", lambda: True)
    monkeypatch.setattr(registry, "REQUIRED", frozenset({before, after}))
    assert phases.wait_ready_afresh(runner, value, None, horizon, 0.0, 300.0) is None
    assert clock.now >= phases.RESTART_READY_SECONDS
    # Once `before` is observed afresh too, the first ready answer counts.
    store.insert(rows(before))
    clock.now = 0.0
    assert phases.wait_ready_afresh(runner, value, None, horizon, 0.0, 300.0) == 0.0


def journey_reports(run: Path, phases, *, extra: dict[str, str] | None = None) -> None:
    """A passing report for every journey and every accessibility phase."""
    by_report: dict[str, list[str]] = {}
    for journey, (_, phase) in phases.JOURNEYS.items():
        for report in phases.PHASE_REPORTS.get(phase, ())[-1:]:
            by_report.setdefault(report, []).append(journey)
    for phase in phases.A11Y_PHASES:
        by_report.setdefault(f"{phase}.xml", []).append("A11Y")
    for report, journeys in by_report.items():
        cases = "".join(f'<testcase name="[{journey}] one"/>' for journey in journeys)
        private(run / report, f"<testsuite>{cases}</testsuite>")


def every_phase_passed(run: Path, phases) -> dict:
    """Every phase of the run passed, each with an evidence file naming its kept folder."""
    value = {}
    for phase in (*phases.VERIFICATION_ORDER, *phases.A11Y_PHASES):
        name = f"{phase}-evidence.json"
        (run / "kept" / phase).mkdir(parents=True, exist_ok=True, mode=0o700)
        private(run / name, json.dumps({"keptEvidence": f"kept/{phase}"}))
        value[phase] = {"state": "passed", "evidence": name}
    return value


def record_of(runner, phases, run: Path, value: dict) -> dict:
    return phases.verification_record(
        SimpleNamespace(RUN=run, MAX_LOG=runner.MAX_LOG, private_bytes=runner.private_bytes),
        value, commit="0" * 40, source={"sha256": "a" * 64},
        started=dt.datetime.now(dt.UTC), committed=True)


def test_a_failed_required_phase_fails_the_verification_run(runner, phases, tmp_path):
    journey_reports(tmp_path, phases)
    passed = every_phase_passed(tmp_path, phases)
    # Each screen `A11Y_SCREENS` names keeps its records in its phase's kept evidence
    # (Step 97(b) item 17), so A11Y passes and the failed phase alone decides the run.
    for screen, phase in phases.A11Y_SCREENS.items():
        kept_screen(tmp_path / "kept" / phase, "t1", screen)
    assert record_of(runner, phases, tmp_path, passed)["result"] == "passed"
    for phase in ("restart-host", "restore-paths"):
        value = {**passed, phase: {"state": "failed", "reason": "refused"}}
        found = record_of(runner, phases, tmp_path, value)
        assert found["result"] == "failed" and found["passed"] is False
        assert found["failedPhases"] == [phase]
        # Every journey passed; the failed phase alone fails the run.
        assert all(item["result"] == "passed" for item in found["journeys"]
                   if item["phase"] != phase)


SCREENS = {"entry": "accessibility", "email-link-fresh-browser": "security"}
ANNOUNCER = {"role": "status", "ariaLive": "polite", "testId": "announcer",
             "insideMain": False}


def check_record(**changes) -> dict:
    return {"violations": [], "colorContrastEvaluated": True, "sidewaysScroll": False,
            "appShell": True, "liveRegions": [ANNOUNCER], **changes}


def kept_screen(folder: Path, test: str, screen: str, record_: dict | None = None,
                *, visits: tuple[str, ...] = ("keyboard", "focus")) -> None:
    capture = folder / test / f"320-{screen}.png"
    private(capture, f"capture {screen} {test}")
    value = {"capture": capture.name,
             "captureSha256": hashlib.sha256(capture.read_bytes()).hexdigest(),
             **(record_ if record_ is not None else check_record())}
    private(folder / test / f"a11y-check-{screen}.json", json.dumps(value))
    for kind in visits:
        private(folder / test / f"a11y-{kind}-{screen}.json", "{}")


def a11y_run(run: Path, phases) -> tuple[dict, dict[str, Path]]:
    journey_reports(run, phases)
    value = every_phase_passed(run, phases)
    folders = {phase: run / "kept" / phase for phase in value}
    for screen, phase in SCREENS.items():
        kept_screen(folders[phase], "t1", screen)
    return value, folders


def a11y_outcome(runner, phases, run: Path, value: dict) -> tuple[str, list[str]]:
    stand_in = SimpleNamespace(RUN=run, MAX_LOG=runner.MAX_LOG,
                               private_bytes=runner.private_bytes)
    problems = phases.a11y_evidence(stand_in, value)
    return phases.a11y_result(stand_in, value, problems), problems


def test_the_a11y_journey_needs_every_accessibility_phase_and_every_screens_records(
        runner, phases, tmp_path, monkeypatch):
    monkeypatch.setattr(phases, "A11Y_SCREENS", SCREENS)
    entry = "a11y-check-entry.json"

    def case(index: int):
        run = tmp_path / f"case-{index}"
        run.mkdir(mode=0o700)
        return (run, *a11y_run(run, phases))

    def rewrite(folder: Path, **changes) -> None:
        path = folder / "t1" / entry
        value = {**json.loads(path.read_text()), **changes}
        path.unlink()
        private(path, json.dumps(value))

    run, value, folders = case(0)
    assert a11y_outcome(runner, phases, run, value) == ("passed", [])
    failing = [
        lambda r, v, f: v.pop("accessibility-keyboard"),
        lambda r, v, f: v.__setitem__("accessibility-screens", {"state": "failed"}),
        lambda r, v, f: (f["accessibility"] / "t1" / entry).unlink(),
        lambda r, v, f: rewrite(f["accessibility"], violations=[{"rule": "label"}]),
        lambda r, v, f: rewrite(f["accessibility"], colorContrastEvaluated=False),
        lambda r, v, f: rewrite(f["accessibility"], sidewaysScroll=True),
        lambda r, v, f: (f["accessibility"] / "t1" / "320-entry.png").unlink(),
        lambda r, v, f: (f["accessibility"] / "t1" / "320-entry.png").write_text("changed"),
        lambda r, v, f: (f["accessibility"] / "t1" / "a11y-keyboard-entry.json").unlink(),
        lambda r, v, f: (f["accessibility"] / "t1" / "a11y-focus-entry.json").unlink(),
        lambda r, v, f: kept_screen(f["accessibility"], "t2", "entry",
                                    check_record(violations=[{"rule": "region"}])),
        # L1-55: the live regions.
        lambda r, v, f: rewrite(f["accessibility"], liveRegions=None),
        lambda r, v, f: rewrite(f["accessibility"], liveRegions=[]),
        lambda r, v, f: rewrite(f["accessibility"], liveRegions=[{**ANNOUNCER,
                                                                 "role": "alert"}]),
        lambda r, v, f: rewrite(f["accessibility"], liveRegions=[{**ANNOUNCER,
                                                                 "ariaLive": "assertive"}]),
        lambda r, v, f: rewrite(f["accessibility"], liveRegions=[
            ANNOUNCER, {"role": "status", "ariaLive": "polite",
                        "testId": "provider-notice-mail", "insideMain": False}]),
    ]
    for index, change in enumerate(failing, start=1):
        run, value, folders = case(index)
        change(run, value, folders)
        assert a11y_outcome(runner, phases, run, value)[0] == "failed", index
    # A screen whose records sit only in another phase's kept evidence has no check record.
    run, value, folders = case(len(failing) + 1)
    for item in (folders["security"] / "t1").iterdir():
        os.replace(item, folders["accessibility"] / "t1" / item.name)
    outcome, problems = a11y_outcome(runner, phases, run, value)
    assert outcome == "failed"
    assert "email-link-fresh-browser: no check record" in problems
    # These pass: two passing records of one screen in two tests; the announcer and
    # `nav-error` outside `#main` beside an alert inside it; no app shell and no entry.
    run, value, folders = case(len(failing) + 2)
    kept_screen(folders["accessibility"], "t2", "entry")
    assert a11y_outcome(runner, phases, run, value) == ("passed", [])
    run, value, folders = case(len(failing) + 3)
    rewrite(folders["accessibility"], liveRegions=[
        ANNOUNCER, {"role": None, "ariaLive": "polite", "testId": "nav-error",
                    "insideMain": False},
        {"role": "alert", "ariaLive": None, "testId": None, "insideMain": True}])
    assert a11y_outcome(runner, phases, run, value) == ("passed", [])
    run, value, folders = case(len(failing) + 4)
    rewrite(folders["accessibility"], appShell=False, liveRegions=[])
    assert a11y_outcome(runner, phases, run, value) == ("passed", [])


def test_the_corpus_dates_end_on_the_realm_s_creation_day(phases, tmp_path):
    import u8_corpus

    private(tmp_path / "environment.json", json.dumps({"createdAt": 1793489400.0}))
    # 2026-10-31T23:30:00Z, already 2026-11-01 in Seoul.
    assert dt.datetime.fromtimestamp(1793489400.0, dt.UTC) == dt.datetime(
        2026, 10, 31, 23, 30, tzinfo=dt.UTC)
    anchor = u8_corpus.anchor(tmp_path)
    assert anchor == dt.date(2026, 10, 31)
    assert u8_corpus.source(0, anchor).published_on == dt.date(2026, 10, 31)
    assert u8_corpus.source(364, anchor).published_on == dt.date(2025, 11, 1)
    assert u8_corpus.source(365, anchor).published_on == dt.date(2026, 10, 31)
    assert u8_corpus.anchor(tmp_path) == anchor
    assert all(u8_corpus.source(index, anchor).published_on <= anchor
               for index in range(600))


def test_compatibility_runs_the_tags_spec_through_the_tags_own_frontend(
        runner, phases, tmp_path, monkeypatch):
    monkeypatch.setattr(phases, "previous_tag", lambda: "v2.0.0")
    monkeypatch.setenv("HOME", str(tmp_path))
    tree = tmp_path / ".docsuri-u8" / "compatibility-v2.0.0"
    tree.mkdir(parents=True)
    started = []
    monkeypatch.setattr(phases, "start_realm", lambda runner_, path, log, *, staged: (
        started.append(log) or Realm()))
    stand_in = StandIn(tmp_path, runner)
    phases.run_compatibility(stand_in, tmp_path / "environment.json")
    install, playwright = [command for command in stand_in.commands
                           if command[0] not in ("listed",)]
    assert install == ["corepack", "pnpm@9.15.9", "--dir", str(tree / "frontend"), "install",
                       "--frozen-lockfile", "--offline", "--ignore-scripts"]
    assert playwright[0] == str(tree / "frontend/node_modules/.bin/playwright")
    assert playwright[playwright.index("--config") + 1] == str(
        tree / "frontend/playwright.u8-complete.config.ts")
    assert str(tree / "frontend/e2e/u8-complete/journeys.spec.ts") in playwright
    assert len(started) == 1
    # A failed install is a failed prerequisite, and no realm starts.
    started.clear()
    stand_in = StandIn(tmp_path, runner, exit_code=1)
    with pytest.raises(runner.Refused):
        phases.run_compatibility(stand_in, tmp_path / "environment.json")
    evidence = stand_in.evidence["compatibility"]
    assert evidence["failureReason"] == (
        "the previous release's frontend could not be installed offline")
    assert started == []


def test_the_performance_evidence_records_the_versions_it_ran_on(
        runner, phases, tmp_path, monkeypatch):
    seen = performance_ready(phases, monkeypatch, tmp_path)
    stand_in = StandIn(tmp_path, runner, on_run=browser_timings(tmp_path))
    monkeypatch.setattr(phases, "latency_summaries", lambda run, offsets: {"read": 100.0})
    phases.run_performance(stand_in, tmp_path / "environment.json")
    assert stand_in.evidence["performance"]["versions"] == VERSIONS
    assert seen["versions"] == [None]  # a development tree
    release = {"tag": "v2.1.0", "commit": "c" * 40}
    stand_in = StandIn(tmp_path, runner, on_run=browser_timings(tmp_path))
    stand_in.release_identity = lambda root: release
    phases.run_performance(stand_in, tmp_path / "environment.json")
    assert seen["versions"] == [None, release]
    assert stand_in.evidence["performance"]["source"] == {"release": release}


def test_the_memory_watch_keeps_the_served_trees_peak_from_recorded_snapshots(phases):
    assert phases.memory_record([(1_200_000_000, None, 5), None, (1_350_000_000, None, 5),
                                 (1_300_000_000, None, 5)]) == {
        "samples": 3, "unread": 1, "peakRssBytes": 1_350_000_000, "peakPssBytes": None,
        "processes": 5}
    assert phases.memory_record([(1_200_000_000, 900_000_000, 5),
                                 (1_100_000_000, 950_000_000, 6)]) == {
        "samples": 2, "unread": 0, "peakRssBytes": 1_200_000_000,
        "peakPssBytes": 950_000_000, "processes": 5}
    for snapshots in ([], [None, None]):
        record_ = phases.memory_record(snapshots)
        assert (record_["peakRssBytes"], record_["peakPssBytes"], record_["processes"]) == (
            None, None, None)
    snapshots = [(1_200_000_000, None, 5), (1_350_000_000, None, 5), (1_300_000_000, None, 5)]

    async def watched() -> tuple[dict, set[int], int]:
        loop, stop, threads = asyncio.get_running_loop(), asyncio.Event(), set()
        answers = iter(snapshots)

        def sample():
            threads.add(threading.get_ident())
            answer = next(answers)
            if answer is snapshots[-1]:
                loop.call_soon_threadsafe(stop.set)
            return answer

        record_ = await phases.watch_memory(sample, stop, every=0)
        return record_, threads, threading.get_ident()

    record_, threads, loop_thread = asyncio.run(watched())
    assert record_ == phases.memory_record(snapshots)
    assert threads and loop_thread not in threads


def test_the_performance_evidence_records_the_served_realms_peak_memory_under_the_load(
        runner, phases, tmp_path, monkeypatch):
    memory = {"samples": 60, "unread": 0, "peakRssBytes": 5 * 1024**3,
              "peakPssBytes": None, "processes": 6}
    seen = performance_ready(phases, monkeypatch, tmp_path, load={**LOAD, "memory": memory})
    monkeypatch.setattr(phases, "latency_summaries", lambda run, offsets: {"read": 100.0})
    stand_in = StandIn(tmp_path, runner, on_run=browser_timings(tmp_path))
    rows_asked = []

    def rows(roots, deadline):
        rows_asked.append((roots, deadline - time.monotonic()))
        return [(4242, 400_000), (4243, 900_000), (4244, 120_000), (4245, 40_000),
                (4246, 35_000)]

    stand_in.process_tree_rows, stand_in.tree_memory = rows, runner.tree_memory
    monkeypatch.setattr(runner.sys, "platform", "darwin")
    result = phases.run_performance(stand_in, tmp_path / "environment.json")
    evidence = stand_in.evidence["performance"]
    assert evidence["load"]["memory"] == memory
    assert evidence["exitCode"] == 0 and result["state"] == "passed"  # nothing judges it
    (sample_memory,) = seen["load"]
    assert sample_memory() == (1_530_880_000, None, 5)
    ((roots, left),) = rows_asked
    assert roots == (4242,) and 0 < left <= runner.PHASE_SECONDS

    def refused(roots, deadline):
        raise runner.Refused("process deadline reached")

    stand_in.process_tree_rows = refused
    assert sample_memory() is None


# --- Step 115(c)-(e): the capacity burst (CP-6, record-only) -------------------------------------
CSRF_TOKEN = secrets.token_hex(8)  # one per run, shared by both session answers
SIGNED = {"signedIn": True, "accountId": "account-1", "authorityRevision": "1",
          "csrfToken": CSRF_TOKEN}
GUEST = {"signedIn": False, "csrfToken": CSRF_TOKEN}
CAPACITY = (503, {"code": "NOT_READY", "messageKey": "capacity.exhausted"})
FORBIDDEN = (403, {"code": "FORBIDDEN", "messageKey": "access.denied"})
OK = (200, {})


def scripted(answers: dict[str, list[tuple[int, dict]]]):
    """A handler answering each path from its own script (the last answer repeats), and
    the requests in the order they arrived."""
    arrivals: list[tuple[str, str]] = []
    queues = {path: list(items) for path, items in answers.items()}

    def handler(request):
        arrivals.append((request.method, request.url.path))
        queue = queues[request.url.path]
        answer = queue.pop(0) if len(queue) > 1 else queue[0]
        status, body = (200, answer) if isinstance(answer, dict) else answer
        return httpx.Response(status, json=body)

    return handler, arrivals


def recording_sleep():
    slept: list[float] = []

    async def sleep(seconds: float) -> None:
        slept.append(seconds)

    return sleep, slept


def loaded_once(phases, answers):
    handler, arrivals = scripted(answers)
    sleep, slept = recording_sleep()

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler),
                                     base_url=phases.PUBLIC_ORIGIN) as client:
            return await phases.first_load(client, sleep=sleep, clock=time.monotonic)

    return asyncio.run(run()), arrivals, slept


def first_load_answers(phases, *, session, navigation=(OK,), jobs=(OK,)):
    return {phases.CAPABILITIES_PATH: [OK], phases.SESSION_PATH: list(session),
            phases.NAVIGATION_PATH: list(navigation), phases.JOBS_PATH: list(jobs)}


def test_each_run_of_each_size_draws_values_of_its_own(phases):
    token = secrets.token_hex(8)
    drawn = [phases.burst_values(token, streams, run, 3) for streams, run in phases.BURST_ORDER]
    assert len({item["seed"] for item in drawn}) == 9
    titles = [owner["title"] for item in drawn for owner in item["accounts"]]
    assert len(titles) == 27 and len(set(titles)) == 27
    for field in ("jobId", "operationKey", "usageId", "inputHash"):
        values = [job[field] for item in drawn for job in item["jobs"]]
        assert len(values) == 36 and len(set(values)) == 36, field
    assert all(re.fullmatch(r"[0-9a-f]{64}", job["inputHash"])
               for item in drawn for job in item["jobs"])
    assert phases.burst_values(token, 4, 2, 3) == drawn[4]
    assert [job["account"] for job in drawn[2]["jobs"]] == [0, 1, 2, 0, 1, 2, 0, 1]
    assert [item["jobs"] for item in drawn if item["streams"] == 0] == [[], [], []]
    assert phases.BURST_ORDER == ((0, 1), (4, 1), (8, 1), (0, 2), (4, 2), (8, 2), (0, 3),
                                  (4, 3), (8, 3))
    assert phases.BURST_USERS == 20 and phases.BURST_STREAM_SIZES == (0, 4, 8)
    assert phases.BURST_RUNS == 3 and phases.SHELL_RETRY_WAITS == (0.25, 0.5)
    assert phases.NAVIGATION_BODY == {"routeId": "search"}
    assert phases.JOBS_BODY == {"limit": 20}


def test_a_first_load_follows_the_shells_chains_and_retry_rule(phases):
    capabilities = ("GET", phases.CAPABILITIES_PATH)
    session = ("GET", phases.SESSION_PATH)
    navigation = ("POST", phases.NAVIGATION_PATH)
    jobs = ("POST", phases.JOBS_PATH)

    # Signed in: chains A and B, the 작업 read and the owner's capabilities follow.
    result, arrivals, slept = loaded_once(phases, first_load_answers(phases, session=[SIGNED]))
    assert set(arrivals[:2]) == {capabilities, session}
    assert sorted(arrivals[2:]) == sorted([navigation, navigation, jobs, capabilities])
    assert result["loaded"] is True and result["firstFailure"] is None and slept == []
    assert set(result["chains"]) == set(phases.CHAIN_KINDS)

    # Chain A's navigation refused for capacity twice, then answered: three attempts.
    result, arrivals, slept = loaded_once(phases, first_load_answers(
        phases, session=[GUEST], navigation=[CAPACITY, CAPACITY, OK]))
    assert arrivals.count(navigation) == 3 and slept == [0.25, 0.5]
    assert result["loaded"] is True
    assert [call["attempt"] for call in result["calls"] if call["kind"] == "navigation"] == [
        1, 2, 3]

    # Three such answers: chain A refused, the user not loaded.
    result, arrivals, slept = loaded_once(phases, first_load_answers(
        phases, session=[GUEST], navigation=[CAPACITY]))
    assert arrivals.count(navigation) == 3 and slept == [0.25, 0.5]
    assert result["loaded"] is False and result["firstFailure"] == "navigation"
    assert result["chains"]["navigation-a"] == "503:NOT_READY:capacity.exhausted"

    # A refused session read: no 작업 read, no chain B; chain A reads the session again.
    result, arrivals, slept = loaded_once(phases, first_load_answers(
        phases, session=[CAPACITY, SIGNED]))
    assert set(arrivals[:2]) == {capabilities, session}
    assert arrivals[2:] == [session, navigation]
    assert jobs not in arrivals and slept == [0.25]
    assert result["chains"]["jobs-list"] == phases.NOT_SENT
    assert result["loaded"] is False and result["firstFailure"] == "session"

    # A refusal that is not transient: one attempt, no wait.
    result, arrivals, slept = loaded_once(phases, first_load_answers(
        phases, session=[GUEST], navigation=[FORBIDDEN]))
    assert arrivals.count(navigation) == 1 and slept == []
    assert result["firstFailure"] == "navigation"

    # The 작업 read is never retried.
    result, arrivals, slept = loaded_once(phases, first_load_answers(
        phases, session=[SIGNED], jobs=[CAPACITY]))
    assert arrivals.count(jobs) == 1 and slept == []
    assert result["firstFailure"] == "jobs-list"

    assert phases.transient("DEPENDENCY_UNAVAILABLE", "") is True
    assert phases.transient("RATE_LIMITED", "rate.limited") is True
    assert phases.transient("NOT_READY", "capacity.exhausted") is True
    assert phases.transient("NOT_READY", "capability.notReady") is False
    assert phases.transient("FORBIDDEN", "access.denied") is False


def gate_snapshot_of(sequence: int, granted: int, *, pid: int = 4242) -> dict:
    buckets = {**{str(bound): 0 for bound in (1, 5, 10, 50, 100, 250, 500, 1000)}, "over": 0}
    buckets["5"] = granted
    return {"version": 1, "pid": pid, "sequence": sequence, "writtenAt": 0.0, "gates": {
        "owner:accounts": {"granted": granted, "refused": 0, "released": granted,
                           "waitMsTotal": 2.0 * granted, "waitMsMax": 2.0,
                           "refusedWaitMsMax": 0.0, "holdMsTotal": 3.0 * granted,
                           "holdMsMax": 3.0, "buckets": buckets}}}


class BurstHost:
    """One handler for the three clients: twenty capabilities requests held until all
    have arrived (or 599 after 1 s), each stream answered with one snapshot frame and
    ended only once the jobs double ends this run's jobs."""

    def __init__(self, phases, job_ids):
        self.phases, self.job_ids = phases, [str(job) for job in job_ids]
        self.events: list[tuple[str, str]] = []
        self.capabilities = 0
        self.arrived = asyncio.Event()
        self.ended = threading.Event()
        self.frames_sent: list[int] = []
        self.streams_asked = 0
        self.second_after_first_frame = None

    def end(self, job_ids):
        self.events.append(("end", ",".join(str(job) for job in job_ids)))
        assert [str(job) for job in job_ids] == self.job_ids
        self.ended.set()
        return len(job_ids)

    def stream(self, index: int, job_id: str):
        async def body():
            self.frames_sent.append(index)
            yield self.frame(job_id, "accepted", 1)
            deadline = time.monotonic() + 5
            while not self.ended.is_set() and time.monotonic() < deadline:
                await asyncio.sleep(0.01)
            yield self.frame(job_id, "failed", 2)
            self.events.append(("stream-ended", job_id))

        return body()

    @staticmethod
    def frame(job_id: str, state: str, seq: int) -> bytes:
        data = json.dumps({"jobId": job_id, "state": state, "seq": seq})
        return f"id: {seq}\nevent: snapshot\ndata: {data}\n\n".encode()

    async def handle(self, request):
        path = request.url.path
        if path.endswith("/events"):
            index = self.streams_asked
            self.streams_asked += 1
            if index == 1:
                self.second_after_first_frame = 0 in self.frames_sent
            return httpx.Response(200, headers={"content-type": "text/event-stream"},
                                  content=self.stream(index, path.split("/")[4]))
        self.events.append(("arrive", path))
        if path == self.phases.CAPABILITIES_PATH:
            self.capabilities += 1
            if self.capabilities <= 20:
                if self.capabilities == 20:
                    self.arrived.set()
                try:
                    await asyncio.wait_for(self.arrived.wait(), 1)
                except TimeoutError:
                    self.events.append(("answer", path))
                    return httpx.Response(599, json={})
        self.events.append(("answer", path))
        if path == self.phases.SESSION_PATH:
            return httpx.Response(200, json=SIGNED)
        return httpx.Response(200, json={})


def test_a_run_opens_its_streams_then_fires_every_user_then_ends_its_jobs(
        runner, phases, tmp_path, monkeypatch):
    job_ids = [uuid.uuid4(), uuid.uuid4()]
    host = BurstHost(phases, job_ids)
    snapshots = [gate_snapshot_of(1, 0), gate_snapshot_of(3, 1), gate_snapshot_of(5, 21)]
    reads = []

    async def next_gate_snapshot(runner_, pid, mark, *, sleep):
        reads.append((pid, mark))
        return snapshots[len(reads) - 1]

    def ready_sample():
        host.events.append(("ready", ""))
        return {"answered": True, "ready": True, "admissionClosed": False}

    monkeypatch.setattr(phases, "next_gate_snapshot", next_gate_snapshot)
    sleep, _ = recording_sleep()
    stand_in = StandIn(tmp_path, runner)
    jobs = SimpleNamespace(end=host.end)

    async def run():
        clients = [httpx.AsyncClient(transport=httpx.MockTransport(host.handle),
                                     base_url=phases.PUBLIC_ORIGIN) for _ in range(3)]
        try:
            return await phases.run_burst(
                stand_in, clients, jobs, [(0, job_ids[0]), (1, job_ids[1])], streams=2,
                pid=4242, ready_sample=ready_sample, sleep=sleep, clock=time.monotonic)
        finally:
            for client in clients:
                await client.aclose()

    record_ = asyncio.run(run())
    assert host.second_after_first_frame is True
    assert record_["streamsOpened"] == 2 and record_["sizeNotReached"] is False
    assert record_["users"] == {"loaded": 20, "notLoaded": 0, "firstFailure": {}}
    assert not any(key.startswith("599") for summary in record_["calls"].values()
                   for key in summary["answers"])
    assert len(reads) == 3 and all(pid == 4242 for pid, _ in reads)
    assert record_["gates"] == {"streams": phases.gate_delta(snapshots[0], snapshots[1]),
                                "burst": phases.gate_delta(snapshots[1], snapshots[2])}
    events = host.events
    end = events.index(("end", ",".join(str(job) for job in job_ids)))
    assert all(events.index(("stream-ended", str(job))) > end for job in job_ids)
    first = events.index(("arrive", phases.CAPABILITIES_PATH))
    last = max(index for index, item in enumerate(events[:end]) if item[0] == "answer")
    readies = [index for index, item in enumerate(events) if item[0] == "ready"]
    assert readies and min(readies) < first and max(readies) > last
    assert not [index for index in readies if first <= index <= last]
    assert record_["streamEnds"] == ["job-ended", "job-ended"]
    assert record_["jobsEnded"] == 2 and record_["settled"] is True


def burst_run(streams: int, run: int, *, refusals: int = 0, closed: bool = False) -> dict:
    answers = {"200": 20 - refusals}
    if refusals:
        answers["503:NOT_READY:capacity.exhausted"] = refusals
    gate = {"granted": 20, "refused": 0, "released": 20, "waitMsTotal": 40.0,
            "holdMsTotal": 60.0, "buckets": {}, "p95BucketMs": 5, "maxBucketMs": 5,
            "holdMsMean": 3.0}
    return {"streams": streams, "run": run, "streamsOpened": streams, "sizeNotReached": False,
            "streamEnds": ["job-ended"] * streams,
            "readiness": [{"answered": True, "ready": True, "admissionClosed": closed}] * 3,
            "calls": {"navigation": {"attempts": 20, "answers": answers,
                                     "latencyMs": {"p50": 1, "p95": 2, "max": 3}}},
            "users": {"loaded": 20 - refusals, "notLoaded": refusals, "firstFailure": {}},
            "gates": {"streams": {}, "burst": {"owner:accounts": gate}}, "jobsEnded": streams}


def test_the_burst_record_counts_answers_waits_and_holds(phases):
    assert phases.answer_key(200, {}) == "200" and phases.answer_key(204, None) == "200"
    assert phases.answer_key(*CAPACITY) == "503:NOT_READY:capacity.exhausted"
    assert phases.answer_key(429, {"code": "RATE_LIMITED", "messageKey": "rate.limited"}) == (
        "429:RATE_LIMITED:rate.limited")
    assert phases.error_key(httpx.ConnectError("refused")) == "error:ConnectError"

    summary = phases.call_summary([
        {"kind": "navigation", "answer": "200", "ms": 10.0},
        {"kind": "navigation", "answer": "503:NOT_READY:capacity.exhausted", "ms": 30.0},
        {"kind": "navigation", "answer": "error:ConnectError", "ms": 900.0},
        {"kind": "session", "answer": "200", "ms": 5.0}])
    assert summary["navigation"]["attempts"] == 3
    assert summary["navigation"]["answers"] == {
        "200": 1, "503:NOT_READY:capacity.exhausted": 1, "error:ConnectError": 1}
    # Over the two the host answered (nearest rank), the transport error left out.
    assert summary["navigation"]["latencyMs"] == {"p50": 10.0, "p95": 30.0, "max": 30.0}
    assert summary["jobs-list"] == {"attempts": 0, "answers": {},
                                    "latencyMs": {"p50": None, "p95": None, "max": None}}

    before = gate_snapshot_of(1, 2)
    after = gate_snapshot_of(3, 22)
    waits = after["gates"]["normal-owner:accounts"] = json.loads(json.dumps(
        after["gates"]["owner:accounts"]))
    waits.update(granted=20, refused=1, released=19, holdMsTotal=380.0)
    waits["buckets"].update({"5": 18, "250": 1, "over": 1})
    delta = phases.gate_delta(before, after)
    assert delta["owner:accounts"]["granted"] == 20
    assert delta["owner:accounts"]["holdMsTotal"] == 60.0
    assert delta["owner:accounts"]["buckets"]["5"] == 20
    assert delta["owner:accounts"]["p95BucketMs"] == 5
    assert delta["normal-owner:accounts"]["granted"] == 20  # new: counted from zero
    assert delta["normal-owner:accounts"]["refused"] == 1
    assert delta["normal-owner:accounts"]["p95BucketMs"] == 250
    assert delta["normal-owner:accounts"]["maxBucketMs"] == "over"
    assert delta["normal-owner:accounts"]["holdMsMean"] == 20.0
    with pytest.raises(ValueError, match="another host process"):
        phases.gate_delta(before, gate_snapshot_of(3, 22, pid=4343))
    with pytest.raises(ValueError, match="another host process"):
        phases.gate_delta(after, before)

    refused = phases.burst_findings([burst_run(0, 1), burst_run(4, 1, refusals=3)])
    assert refused["refusalsSeen"] is True and refused["sizesWithRefusals"] == [4]
    assert refused["sizes"]["4"]["refusals"] == {"navigation:503:NOT_READY:capacity.exhausted": 3}
    assert refused["sizes"]["4"]["usersNotLoaded"] == [3]
    assert refused["sizes"]["0"]["gateHoldMsMean"] == {"owner:accounts": 3.0}
    assert phases.burst_findings([burst_run(0, 1), burst_run(4, 1)])["refusalsSeen"] is False
    closed = phases.burst_findings([burst_run(0, 1), burst_run(8, 1, refusals=2, closed=True)])
    assert closed["refusalsSeen"] is False and closed["sizes"]["8"]["runsNotReady"] == [1]


def test_the_next_gate_snapshot_is_one_taken_after_its_mark(runner, phases, tmp_path):
    stand_in = StandIn(tmp_path, runner)
    path = tmp_path / "gate-waits.json"
    planted = [gate_snapshot_of(10, 1, pid=999), gate_snapshot_of(6, 1), gate_snapshot_of(7, 1)]
    private(path, json.dumps(planted[0]))
    slept: list[float] = []

    async def sleep(seconds: float) -> None:
        slept.append(seconds)
        if len(slept) < len(planted):
            private(path, json.dumps(planted[len(slept)]))

    found = asyncio.run(phases.next_gate_snapshot(stand_in, 4242, 5, sleep=sleep))
    assert found == planted[2] and slept == [0.1, 0.1]
    slept.clear()
    planted = planted[2:]
    assert asyncio.run(phases.next_gate_snapshot(stand_in, 4242, 7, sleep=sleep)) is None
    assert slept == [0.1] * (round(phases.SNAPSHOT_WAIT_SECONDS / 0.1) + 1)


class BurstRealm:
    pid = 4242


def burst_phase(runner, phases, tmp_path, monkeypatch, *, ready=True, failure=None,
                end_error=None, fixtures=True):
    """`run_capacity_burst` on the stand-in runner with its realm, readiness, versions,
    jobs and runs replaced; the order of the start, the stop and the jobs' ends."""
    order: list[object] = []
    starts: list[dict] = []
    stand_in = StandIn(tmp_path, runner)
    stand_in.MAX_RSS, stand_in.enforced_bytes = runner.MAX_RSS, runner.enforced_bytes
    stand_in.process_tree_memory = lambda roots, deadline: (1, None)
    stand_in.stop = lambda process: order.append("stop")
    if fixtures:
        private(tmp_path / "fixtures" / "browser.json", json.dumps({"accounts": {
            key: {"accountId": str(uuid.uuid4()), "email": f"{key}@example.test",
                  "password": secrets.token_hex(8)} for key in phases.BURST_ACCOUNTS}}))
    private(tmp_path / "gate-waits.json", json.dumps(gate_snapshot_of(1, 0, pid=1)))

    def start_realm(runner_, path, log, *, staged, observe_gates=False):
        starts.append({"staged": staged, "observeGates": observe_gates,
                       "oldRecord": (tmp_path / "gate-waits.json").exists()})
        order.append("start")
        return BurstRealm()

    class Jobs:
        def __init__(self):
            self.written = []

        @classmethod
        def open(cls, path):
            return cls()

        def write(self, account_ids, values):
            assert len(account_ids) == 3
            self.written.append(values["seed"])
            return [(job["account"], uuid.UUID(job["jobId"])) for job in values["jobs"]]

        def end(self, job_ids):
            order.append(("end", len(job_ids)))
            if end_error is not None:
                raise end_error
            return len(job_ids)

        def close(self):
            order.append("close")

    async def drive_bursts(runner_, fixtures_, plan, jobs, companion, started):
        runs = [burst_run(item["streams"], item["run"], refusals=2 if index == 4 else 0)
                for index, item in enumerate(plan)]
        runs[1]["jobsEnded"] = "OperationalError"  # that run's 4 jobs are ended after the stop
        return runs, failure

    monkeypatch.setattr(phases, "start_realm", start_realm)
    monkeypatch.setattr(phases, "local_ready", lambda: ready)
    monkeypatch.setattr(phases, "READY_SECONDS", 0.2)
    monkeypatch.setattr(phases, "POLL_SECONDS", 0.01)
    monkeypatch.setattr(phases, "measured_versions", lambda connect, *, release: {
        "postgresql": "17.0", "release": release})
    monkeypatch.setattr(phases, "BurstJobs", Jobs)
    monkeypatch.setattr(phases, "drive_bursts", drive_bursts)
    return stand_in, order, starts


def test_the_capacity_burst_records_every_run_and_fails_only_on_a_prerequisite(
        runner, phases, tmp_path, monkeypatch):
    environment = tmp_path / "environment.json"
    stand_in, order, starts = burst_phase(runner, phases, tmp_path, monkeypatch, fixtures=False)
    with pytest.raises(runner.Refused, match="the capacity burst needs the fixtures phase first"):
        phases.run_capacity_burst(stand_in, environment)
    assert order == [] and starts == []

    stand_in, order, starts = burst_phase(runner, phases, tmp_path, monkeypatch)
    result = phases.run_capacity_burst(stand_in, environment)
    evidence = stand_in.evidence["capacity-burst"]
    assert result["state"] == "passed" and evidence["exitCode"] == 0
    assert evidence["recordOnly"] is True and evidence["failureReason"] is None
    assert [(run["streams"], run["run"]) for run in evidence["runs"]] == list(
        phases.BURST_ORDER)
    assert evidence["summary"]["refusalsSeen"] is True
    assert evidence["readySeconds"] is not None and evidence["jobsWritten"] == 36
    assert evidence["jobsEnded"]["afterStop"] == 4
    assert starts == [{"staged": False, "observeGates": True, "oldRecord": False}]
    assert order == ["start", "stop", ("end", 4), "close"]

    stand_in, order, starts = burst_phase(runner, phases, tmp_path, monkeypatch, ready=False)
    with pytest.raises(runner.Refused, match="U8 phase capacity-burst failed; evidence preserved"):
        phases.run_capacity_burst(stand_in, environment)
    evidence = stand_in.evidence["capacity-burst"]
    assert evidence["failureReason"] == "the served realm was not ready"
    assert evidence["exitCode"] == 1 and evidence["runs"] == []
    assert order == ["start", "stop", ("end", 36), "close"]

    for reason in ("the gate waits were not observed", "a run's streams did not end"):
        stand_in, order, _ = burst_phase(runner, phases, tmp_path, monkeypatch, failure=reason)
        with pytest.raises(runner.Refused, match="capacity-burst failed"):
            phases.run_capacity_burst(stand_in, environment)
        evidence = stand_in.evidence["capacity-burst"]
        assert evidence["failureReason"] == reason and evidence["exitCode"] == 1

    stand_in, order, _ = burst_phase(runner, phases, tmp_path, monkeypatch,
                                     end_error=RuntimeError("lost"))
    phases.run_capacity_burst(stand_in, environment)
    evidence = stand_in.evidence["capacity-burst"]
    assert evidence["jobsEnded"]["afterStop"] == "RuntimeError" and evidence["exitCode"] == 0

    stand_in, order, _ = burst_phase(runner, phases, tmp_path, monkeypatch)
    identities = iter([{"sha256": "before"}, {"sha256": "after"}])
    stand_in.source_identity = lambda: next(identities)
    with pytest.raises(runner.Refused, match="capacity-burst failed"):
        phases.run_capacity_burst(stand_in, environment)
    evidence = stand_in.evidence["capacity-burst"]
    assert evidence["sourceChangedDuringRun"] is True and evidence["exitCode"] == 1


def test_the_served_realm_observes_its_gates_only_when_asked(runner, phases, tmp_path):
    from scripts import serve_docsuri_u8

    stand_in = StandIn(tmp_path, runner)
    path = tmp_path / "environment.json"
    assert "--observe-gates" not in phases.serve_command(stand_in, path, staged=False)
    assert phases.serve_command(stand_in, path, staged=False,
                                observe_gates=True)[-1] == "--observe-gates"
    with pytest.raises(ValueError, match="the cutover stage observes no gates"):
        phases.serve_command(stand_in, path, staged=True, observe_gates=True)
    assert serve_docsuri_u8.arguments(
        ["--environment-file", "x", "--observe-gates"]).observe_gates is True
    assert serve_docsuri_u8.arguments(["--environment-file", "x"]).observe_gates is False
    prepare = serve_docsuri_u8.prepare_with(None, observe=True, observed=[object()])
    with pytest.raises(ValueError, match="the host gates are observed once"):
        prepare(SimpleNamespace(parts={}, profile=None))


def test_the_burst_jobs_stay_unclaimed_and_end_as_the_worker_ends_one(phases, realm, connect):
    owner = uuid.uuid4()  # the research rows name no account row (u4_schema.sql:2-39)
    values = phases.burst_values(secrets.token_hex(8), 3, 1, 1)
    jobs = phases.BurstJobs(realm)
    try:
        written = jobs.write([owner], values)
        ids = [job_id for _, job_id in written]
        assert [index for index, _ in written] == [0, 0, 0] and len(set(ids)) == 3
        with connect("research") as conn:
            rows = conn.execute("SELECT id,state,seq FROM research.job WHERE id = ANY(%s)",
                                (ids,)).fetchall()
            assert sorted((row["state"], row["seq"]) for row in rows) == [("accepted", 1)] * 3
            assert conn.execute("SELECT count(*) AS n FROM research.admission "
                                "WHERE operation_id = ANY(%s)", (ids,)).fetchone()["n"] == 0
            assert conn.execute("SELECT count(*) AS n FROM research.dispatch "
                                "WHERE job_id = ANY(%s)", (ids,)).fetchone()["n"] == 0
            # The research worker's selection (execution.py:375-379), limited to these ids.
            assert conn.execute(
                "SELECT j.id FROM research.job j JOIN research.admission a ON "
                "a.operation_id=j.id WHERE a.state='accepted' AND j.state IN "
                "('accepted','running','cancel_requested') AND (lease_until IS NULL OR "
                "lease_until<=clock_timestamp()) AND j.id = ANY(%s)", (ids,)).fetchall() == []
        assert jobs.end(ids) == 3
        with connect("research") as conn:
            rows = conn.execute(
                "SELECT state,error_code,revision,seq FROM research.job WHERE id = ANY(%s)",
                (ids,)).fetchall()
        assert [tuple(row.values()) for row in rows] == [
            ("failed", "SOURCE_INELIGIBLE", 2, 2)] * 3
        assert jobs.end(ids) == 0
        with connect("research") as conn:
            again = conn.execute(
                "SELECT state,error_code,revision,seq FROM research.job WHERE id = ANY(%s)",
                (ids,)).fetchall()
        assert again == rows
    finally:
        jobs.close()


# --- Step 135(b)-(d): the performance phase's SCRAM logins, GET reads and read check ------------


def test_the_scram_summary_counts_every_login_and_flags_a_pool_only_past_20_ms(phases):
    first = [("accounts", 40.0)] + [("corpus", 4.0)] * 19
    summary = phases.scram_summary(first, {}, planned=220, stopped_early=True)
    assert (summary["logins"], summary["firstMs"], summary["maxMs"], summary["p50Ms"],
            summary["p95Ms"], summary["reconsiderPool"]) == (20, 40.0, 40.0, 4.0, 4.0, False)
    assert summary["planned"] == 220 and summary["stoppedEarly"] is True
    assert summary["perOwner"] == {"accounts": 1, "corpus": 19}
    assert summary["measured"] is True and summary["failedLogins"] == 0
    assert summary["boundMs"] == 20.0
    at_bound = phases.scram_summary([("library", 3.0)] * 18 + [("library", 20.0)] * 2, {},
                                    planned=20, stopped_early=False)
    assert (at_bound["p95Ms"], at_bound["reconsiderPool"]) == (20.0, False)
    assert at_bound["stoppedEarly"] is False and at_bound["perOwner"] == {"library": 20}
    past = phases.scram_summary([("library", 3.0)] * 18 + [("library", 20.5)] * 2, {},
                                planned=20, stopped_early=False)
    assert past["reconsiderPool"] is True
    none = phases.scram_summary([], {"OperationalError": 3}, planned=3, stopped_early=False)
    assert (none["logins"], none["measured"], none["p95Ms"], none["failedLogins"]) == (
        0, False, None, 3)
    assert none["failures"] == {"OperationalError": 3} and none["planned"] == 3


def test_the_scram_logins_take_every_owner_login_in_turn_on_the_realm(phases, realm):
    import dataclasses
    import itertools
    import socket

    from backend.transactions import REQUIRE_AUTH

    ticks = itertools.count()
    stopped = phases.scram_logins(realm, per_owner=2, seconds=12,
                                  clock=lambda: float(next(ticks)))
    owners = stopped["owners"]
    assert len(owners) == 11 and owners == sorted(owners)
    assert stopped["perOwner"] == dict.fromkeys(owners, 1)
    assert stopped["logins"] == 11 and stopped["planned"] == 22
    assert stopped["stoppedEarly"] is True and stopped["failedLogins"] == 0
    assert stopped["firstMs"] > 0 and stopped["p50Ms"] > 0

    full = phases.scram_logins(realm, per_owner=2, seconds=60)
    assert full["logins"] == 22 and full["perOwner"] == dict.fromkeys(owners, 2)
    assert full["stoppedEarly"] is False and full["failedLogins"] == 0
    assert full["requireAuth"] == REQUIRE_AUTH

    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    dead = phases.scram_logins(dataclasses.replace(realm, database_port=port),
                               per_owner=1, seconds=30)
    assert dead["logins"] == 0 and dead["failedLogins"] == 11
    assert dead["failures"] and set(dead["failures"]) <= {"OperationalError", "PoolTimeout"}
    assert dead["measured"] is False
    text = json.dumps(dead)
    assert "127.0.0.1" not in text and str(port) not in text


def test_the_users_read_by_post_and_by_get_and_search_in_turn(phases):
    assert phases.LOAD_TURNS == ("settings-read", "search", "session-read", "search")
    search = {"query": {"query": "attention"}, "page": {}}
    assert phases.load_request("settings-read", search) == (
        "POST", "/api/v2/c03/settings-read", {})
    assert phases.load_request("session-read", search) == ("GET", "/api/v2/session", None)
    assert phases.load_request("search", search) == ("POST", "/api/v2/c05/search", search)
    with pytest.raises(ValueError):
        phases.load_request("accept", search)
    kinds: dict[str, int] = {}
    for index in range(phases.USERS):
        for turn in range(index, index + 12):
            kind = phases.LOAD_TURNS[turn % len(phases.LOAD_TURNS)]
            kinds[kind] = kinds.get(kind, 0) + 1
    assert kinds == {"settings-read": 60, "session-read": 60, "search": 120}


def test_the_host_counts_each_class_from_the_lines_written_after_the_offsets(
        phases, tmp_path):
    stamp = "2026-10-24T15:49:34Z"
    folder = tmp_path / "evidence" / "latency"
    folder.mkdir(parents=True)

    def window(cls: str, p95: float | None, count: int) -> str:
        return json.dumps({"window": stamp, "class": cls, "p95Ms": p95, "count": count}) + "\n"

    day = folder / "2026-10-24.jsonl"
    day.write_text(window("read", 2000.0, 9) + window("search", 9000.0, 4))
    offsets = phases.latency_offsets(tmp_path)
    with day.open("a") as stream:
        stream.write(window("read", 50.0, 5) + window("read", 100.0, 7)
                     + window("search", 2000.0, 3) + window("accept", 500.0, 0)
                     + "not json\n")
    (folder / "2026-10-25.jsonl").write_text(window("health", 25.0, 2))
    assert phases.latency_counts(tmp_path, offsets=offsets) == {
        "read": 12, "search": 3, "health": 2}
    assert phases.latency_counts(tmp_path / "absent", offsets={}) == {}
    assert phases.latency_summaries(tmp_path, offsets=offsets) == {
        "read": 100.0, "search": 2000.0, "health": 25.0}


def test_the_read_class_check_fails_when_the_host_counted_fewer_reads_than_answered(phases):
    assert phases.read_class_check(10, {"read": 10}) is None
    assert phases.read_class_check(10, {"read": 12}) is None
    for counts in ({"read": 9}, {"static": 10}, {}):
        assert phases.read_class_check(10, counts) == "read-class-short", counts


def test_the_performance_phase_times_the_logins_once_the_realm_stops_and_fails_on_either_check(
        runner, phases, tmp_path, monkeypatch):
    path = tmp_path / "environment.json"
    performance_ready(phases, monkeypatch, tmp_path)
    monkeypatch.setattr(phases, "latency_summaries", lambda run, offsets: {"read": 100.0})
    calls = []

    def recording(summary):
        def scram(source):
            calls.append((source, list(stand_in.stopped)))
            return dict(summary)
        return scram

    stand_in = StandIn(tmp_path, runner, on_run=browser_timings(tmp_path))
    monkeypatch.setattr(phases, "scram_logins", recording(SCRAM))
    result = phases.run_performance(stand_in, path)
    evidence = stand_in.evidence["performance"]
    assert result["state"] == "passed"
    assert evidence["serverCounts"] == {"read": 120}
    assert evidence["readClassCheck"] is None
    assert evidence["scramLogins"] == SCRAM
    assert evidence["failedChecks"] == [] and evidence["exitCode"] == 0
    ((source, stopped),) = calls
    assert source == path
    assert len(stopped) == 1 and isinstance(stopped[0], Realm)

    monkeypatch.setattr(phases, "latency_counts", lambda run, *, offsets: {"read": 119})
    stand_in = StandIn(tmp_path, runner, on_run=browser_timings(tmp_path))
    with pytest.raises(runner.Refused):
        phases.run_performance(stand_in, path)
    evidence = stand_in.evidence["performance"]
    assert evidence["readClassCheck"] == "read-class-short"
    assert evidence["failedChecks"] == ["read-class-short"] and evidence["exitCode"] == 1

    monkeypatch.setattr(phases, "latency_counts", lambda run, *, offsets: {"read": 120})
    monkeypatch.setattr(phases, "scram_logins", recording(
        {**SCRAM, "logins": 219, "failedLogins": 1, "failures": {"OperationalError": 1}}))
    stand_in = StandIn(tmp_path, runner, on_run=browser_timings(tmp_path))
    with pytest.raises(runner.Refused):
        phases.run_performance(stand_in, path)
    evidence = stand_in.evidence["performance"]
    assert evidence["failedChecks"] == ["scram-logins-failed"] and evidence["exitCode"] == 1


def test_the_scram_logins_load_the_realm_from_its_environment_file(phases, realm):
    """The performance phase hands `scram_logins` the realm's environment file, as a
    path: it loads the profile itself and takes one login of each owner login."""
    source = Path(os.environ["DOCSURI_U8_ENVIRONMENT_FILE"])
    found = phases.scram_logins(source, per_owner=1, seconds=60)
    owners = found["owners"]
    assert len(owners) == 11 and found["perOwner"] == dict.fromkeys(owners, 1)
    assert found["logins"] == 11 and found["failedLogins"] == 0
    assert found["stoppedEarly"] is False


# --- Step 166: the vector-storage check (Q5 as corrected, NFR8.13; L4-2 (a)) ----------------

GIB = 1024**3


def test_the_vector_storage_check_passes_at_the_measured_figure_and_fails_past_its_bound(
        phases):
    """The measured figures pass; vectors plus index pass up to 774,404,601 B at 60,000
    chunks and fail one byte past it; another chunk count is judged per chunk and marked.
    Every number here is written out, none is computed from the phase's constants."""
    from backend.u8_policy import PRODUCTION_OPERATIONS as policy

    checked = phases.vector_storage_check(STORAGE, policy)
    assert checked == {
        "vectorsAndIndexBytes": 737_528_192, "boundBytes": 774_404_601,
        "footprintBytes": 1_585_904_663, "budgetBytes": 8_589_934_592,
        "atDesignChunks": True, "failedChecks": []}
    at_bound = {**STORAGE, "indexBytes": 774_404_601 - 246_000_000}
    assert phases.vector_storage_check(at_bound, policy)["failedChecks"] == []
    past = {**at_bound, "indexBytes": at_bound["indexBytes"] + 1}
    assert phases.vector_storage_check(past, policy)["failedChecks"] == [
        "vector-storage-past-its-figure"]
    # 1,000 chunks: 12,292,000 B + 8,192 B is 12,300,192 B, and 105% of it 12,915,201 B.
    small = {**STORAGE, "chunks": 1_000, "vectorBytes": 4_100_000, "indexBytes": 8_815_201}
    checked = phases.vector_storage_check(small, policy)
    assert (checked["boundBytes"], checked["atDesignChunks"], checked["failedChecks"]) == (
        12_915_201, False, [])
    assert phases.vector_storage_check({**small, "indexBytes": 8_815_202}, policy)[
        "failedChecks"] == ["vector-storage-past-its-figure"]
    # The same bytes on fewer chunks: 59,000 chunks' bound is 761,498,001 B, which they
    # still pass, and 56,000 chunks' is 722,778,201 B, which they do not.
    assert phases.vector_storage_check({**STORAGE, "chunks": 59_000}, policy) == {
        **phases.vector_storage_check(STORAGE, policy), "boundBytes": 761_498_001,
        "atDesignChunks": False, "failedChecks": []}
    assert phases.vector_storage_check({**STORAGE, "chunks": 56_000}, policy)[
        "failedChecks"] == ["vector-storage-past-its-figure"]
    # No chunk at all: the index's one page is the whole figure (8,192 B, 8,601 B at 105%).
    empty = {**STORAGE, "chunks": 0, "vectorBytes": 0, "indexBytes": 8_192}
    assert phases.vector_storage_check(empty, policy)["failedChecks"] == []
    assert phases.vector_storage_check({**empty, "indexBytes": 8_602}, policy)[
        "failedChecks"] == ["vector-storage-past-its-figure"]


def test_the_vector_storage_check_counts_the_log_in_the_budget(phases):
    """NFR8.13 counts the database plus the write-ahead log against 8 GiB: at the budget
    it passes, one byte past it fails, and the log alone can take it past."""
    from backend.u8_policy import PRODUCTION_OPERATIONS as policy

    assert policy.footprint_budget_bytes == 8 * GIB
    at_budget = {**STORAGE, "databaseBytes": 8 * GIB - 1_000, "walBytes": 1_000}
    checked = phases.vector_storage_check(at_budget, policy)
    assert (checked["footprintBytes"], checked["failedChecks"]) == (8 * GIB, [])
    assert phases.vector_storage_check({**at_budget, "walBytes": 1_001}, policy)[
        "failedChecks"] == ["footprint-past-its-budget"]
    assert phases.vector_storage_check({**at_budget, "walBytes": 0}, policy)[
        "failedChecks"] == []
    both = {**at_budget, "walBytes": 1_001, "indexBytes": STORAGE["indexBytes"] * 2}
    assert phases.vector_storage_check(both, policy)["failedChecks"] == [
        "vector-storage-past-its-figure", "footprint-past-its-budget"]


def test_the_vector_storage_reading_gives_each_figure_of_the_realm(phases, realm):
    """On a production stand-in of the realm with a few chunks written through
    CorpusContent's own import, three with a vector and one without, each figure equals
    its own single query. The reading is the product's; the admin login is the realm's."""
    import functools

    from backend.modules.discovery.u8_search import StandinEmbeddings
    from tests.u8_service_operations_integration import host_flows
    from tests.u8_service_operations_integration import recovery_flows as rf

    token = secrets.token_hex(6)
    chunks = [{"anchor": f"a{index}", "section": "Body", "text": f"storage {token} {index}"}
              for index in range(4)]
    with host_flows.production_stand_in(realm) as standin:
        host_flows.import_paper(standin, chunks[:3], embed=StandinEmbeddings().embed_query)
        host_flows.import_paper(standin, chunks[3:])
        connect = functools.partial(rf.admin, realm, standin.database)
        figures = phases.vector_storage(connect)
        with connect() as conn:
            def one(statement: str) -> int:
                return int(conn.execute(statement).fetchone()[0])

            assert list(figures) == ["chunks", "vectorBytes", "indexBytes", "arrayBytes",
                                     "tableBytes", "databaseBytes", "walBytes"]
            assert one("SELECT count(*) FROM corpus.projection") == 4
            assert figures["chunks"] == 3 == one(
                "SELECT count(*) FROM corpus.projection WHERE embedding_vector IS NOT NULL")
            assert figures["vectorBytes"] == one(
                "SELECT sum(pg_column_size(embedding_vector)) FROM corpus.projection") > 0
            assert figures["indexBytes"] == one(
                "SELECT pg_relation_size('corpus.projection_embedding_hnsw')") > 0
            assert figures["arrayBytes"] == one(
                "SELECT sum(pg_column_size(embedding)) FROM corpus.projection") > 0
            assert figures["arrayBytes"] != figures["vectorBytes"]
            assert figures["tableBytes"] == one("SELECT pg_table_size('corpus.projection')")
            assert figures["databaseBytes"] == one(
                "SELECT pg_database_size(current_database())")
            assert figures["walBytes"] > 0
            # The log is the instance's and moves between two reads, so it is bounded,
            # not shown equal: above 0, and no more than a second reading plus 64 MiB.
            assert figures["walBytes"] <= one(
                "SELECT wal_bytes + 64 * 1024 * 1024 FROM operations.capacity_footprint()")


def test_a_failed_vector_storage_check_fails_the_performance_phase(
        runner, phases, tmp_path, monkeypatch):
    """The phase records `vectorStorage` and passes at the measured figures; one byte past
    the figure's bound, or past the budget, it fails with the check named in
    `failedChecks`. The verdict alone, a pure function, fails on a storage check too."""
    path = tmp_path / "environment.json"

    def run(storage) -> dict:
        performance_ready(phases, monkeypatch, tmp_path, storage=storage)
        monkeypatch.setattr(phases, "latency_summaries", lambda run, offsets: {"read": 100.0})
        stand_in = StandIn(tmp_path, runner, on_run=browser_timings(tmp_path))
        try:
            return {"state": phases.run_performance(stand_in, path)["state"],
                    **stand_in.evidence["performance"]}
        except runner.Refused:
            return {"state": "refused", **stand_in.evidence["performance"]}

    passed = run(None)
    assert passed["state"] == "passed" and passed["exitCode"] == 0
    assert passed["failedChecks"] == [] and passed["missedTargets"] == []
    assert passed["vectorStorage"] == {
        **STORAGE, "vectorsAndIndexBytes": 737_528_192, "boundBytes": 774_404_601,
        "footprintBytes": 1_585_904_663, "budgetBytes": 8 * GIB, "atDesignChunks": True,
        "failedChecks": []}
    past = run({**STORAGE, "indexBytes": 774_404_601 - 246_000_000 + 1})
    assert (past["state"], past["exitCode"]) == ("refused", 1)
    assert past["failedChecks"] == ["vector-storage-past-its-figure"]
    assert past["vectorStorage"]["failedChecks"] == ["vector-storage-past-its-figure"]
    assert past["missedTargets"] == [] and past["refusedRequests"] == 0
    over = run({**STORAGE, "databaseBytes": 8 * GIB})
    assert (over["state"], over["failedChecks"]) == ("refused", ["footprint-past-its-budget"])
    verdict = phases.performance_verdict(
        {name: 1.0 for name in phases.TARGETS_MS}, {}, LOAD["readiness"], None, 0,
        {"outcome": "succeeded", "seconds": 10.0, "deadlineSeconds": 1800},
        scram=SCRAM, read_check=None, storage_checks=["footprint-past-its-budget"])
    assert verdict["failedChecks"] == ["footprint-past-its-budget"]
    assert verdict["exitCode"] == 1
