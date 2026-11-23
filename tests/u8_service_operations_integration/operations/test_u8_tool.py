"""The composed realm tool's own rules (U8 plan Step 43, `operations/test_u8_tool.py`).

The supervision of a browser phase (the person's decision of 2026-10-23, "Two 1 GiB
limits"): Playwright with its Chromium and the served realm are two trees, each under
its own `MAX_RSS`; either over its budget fails the phase, and the served realm exiting
before Playwright finishes fails it too. The corpus (the person's decision of
2026-10-23, "Load over two runs"): `performance` and `verification-run` refuse an
incomplete one. A phase's JUnit report fails it on zero tests, a skip, an error or a
failure.

Every child here is a short-lived `python -c` process of the test's own; memory figures
are injected at the one measuring seam, so no test needs a gigabyte.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import selectors
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

GIB = 1024**3


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


def child(seconds: float = 30) -> subprocess.Popen:
    return subprocess.Popen(
        [sys.executable, "-c", f"import time; time.sleep({seconds})"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, start_new_session=True)


def supervised(runner, monkeypatch, memory, *, companion=None, companion_log=None,
               seconds: float = 3):
    """`supervise` over a real sleeping child, with each observation's per-tree memory
    from `memory(trees)`."""
    monkeypatch.setattr(runner, "separate_tree_memory",
                        lambda trees, deadline: memory(trees))
    process = child()
    totals = {"count": 0, "peak": 0, "peakPss": None, "observations": 0, "slowest": 0.0}
    try:
        with selectors.DefaultSelector() as selector:
            os.set_blocking(process.stdout.fileno(), False)
            selector.register(process.stdout, selectors.EVENT_READ)
            code = runner.supervise(process, selector, io.BytesIO(),
                                    time.monotonic() + seconds, totals,
                                    (companion, companion_log))
        return code, totals
    finally:
        process.kill()
        process.wait()
        process.stdout.close()


@pytest.fixture
def realm_tree(tmp_path):
    process = child()
    log = tmp_path / "realm.log"
    log.write_bytes(b"")
    yield process, log
    process.kill()
    process.wait()
    process.stdout.close()


# --- 1. the two budgets ------------------------------------------------------------------


def test_each_tree_under_its_own_budget_passes_though_together_they_are_over(
        runner, monkeypatch, realm_tree):
    companion, log = realm_tree
    # 700 MiB of Playwright and Chromium beside 650 MiB of served realm: the measured
    # shape of `browser-journeys`, over one combined budget but inside two.
    code, totals = supervised(
        runner, monkeypatch, lambda trees: [(700 * 1024**2, None), (650 * 1024**2, None)],
        companion=companion, companion_log=log, seconds=1)
    assert code is None  # it ran to the observation bound, refused nothing
    assert totals["peak"] == 700 * 1024**2 and totals["companionPeak"] == 650 * 1024**2
    record = runner.supervision_record("deadline", time.monotonic(), totals, stopped=True)
    assert record["companionPeakRssBytes"] == 650 * 1024**2


def test_the_browser_tree_over_its_budget_fails_the_phase(runner, monkeypatch, realm_tree):
    companion, log = realm_tree
    with pytest.raises(runner.Refused, match="process tree exceeded RSS safety budget"):
        supervised(runner, monkeypatch, lambda trees: [(GIB + 1, None), (1024, None)],
                   companion=companion, companion_log=log)
    assert runner.SUPERVISION_REASONS["process tree exceeded RSS safety budget"] == "rss-limit"


def test_the_served_realm_over_its_budget_fails_the_phase(runner, monkeypatch, realm_tree):
    companion, log = realm_tree
    with pytest.raises(runner.Refused, match="application tree exceeded RSS safety budget"):
        supervised(runner, monkeypatch, lambda trees: [(1024, None), (GIB + 1, None)],
                   companion=companion, companion_log=log)
    assert runner.SUPERVISION_REASONS[
        "application tree exceeded RSS safety budget"] == "companion-rss-limit"


def test_proportional_memory_is_what_each_budget_enforces_where_linux_has_it(
        runner, monkeypatch, realm_tree):
    companion, log = realm_tree
    # RSS over the budget, PSS under it: the PSS figure decides, per tree.
    code, totals = supervised(
        runner, monkeypatch, lambda trees: [(2 * GIB, GIB // 2), (2 * GIB, GIB // 2)],
        companion=companion, companion_log=log, seconds=1)
    assert code is None and totals["companionPeakPss"] == GIB // 2
    with pytest.raises(runner.Refused, match="application tree"):
        supervised(runner, monkeypatch,
                   lambda trees: [(2 * GIB, GIB // 2), (2 * GIB, GIB + 1)],
                   companion=companion, companion_log=log)


def test_the_served_realm_exiting_before_playwright_finishes_fails_the_phase(
        runner, monkeypatch, tmp_path):
    companion = subprocess.Popen([sys.executable, "-c", "pass"])
    companion.wait()
    log = tmp_path / "realm.log"
    log.write_bytes(b"")
    with pytest.raises(runner.Refused, match="owned application exited"):
        supervised(runner, monkeypatch, lambda trees: [(1024, None)] * len(trees),
                   companion=companion, companion_log=log)
    assert runner.SUPERVISION_REASONS[
        "owned application exited during browser verification"] == "companion-exit"


def test_a_phase_without_a_served_realm_keeps_its_one_tree(runner, monkeypatch):
    seen = []

    def memory(trees):
        seen.append(len(trees))
        return [(1024, None)] * len(trees)

    supervised(runner, monkeypatch, memory, seconds=0.5)
    assert seen and set(seen) == {1}


def test_one_snapshot_measures_both_trees_apart(runner, monkeypatch):
    rows = [(10, 1, 100), (11, 10, 200), (20, 1, 300), (21, 20, 400), (30, 1, 999)]
    monkeypatch.setattr(runner, "process_snapshot", lambda deadline: rows)
    monkeypatch.setattr(runner.sys, "platform", "darwin")
    measured = runner.separate_tree_memory(((10,), (20,)), time.monotonic() + 5)
    assert measured == [(300 * 1024, None), (700 * 1024, None)]


# --- 2. zero tests or a skip fails a phase --------------------------------------------------


def junit(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "report.xml"
    path.write_text(f"<testsuites><testsuite>{body}</testsuite></testsuites>")
    os.chmod(path, 0o600)
    return path


@pytest.mark.parametrize("body", [
    "",
    '<testcase name="a"/><testcase name="b"><skipped/></testcase>',
    '<testcase name="a"><failure/></testcase>',
    '<testcase name="a"><error/></testcase>',
])
def test_zero_tests_a_skip_an_error_or_a_failure_fails_the_phase(runner, tmp_path, body):
    evidence = {"exitCode": 0}
    runner.junit_counts(junit(tmp_path, body), evidence)
    assert evidence["exitCode"] == 1


def test_a_missing_report_fails_the_phase(runner, tmp_path):
    evidence = {"exitCode": 0}
    runner.junit_counts(tmp_path / "absent.xml", evidence)
    assert evidence["exitCode"] == 1 and evidence["missingTestReport"] is True


def test_every_passing_case_passes(runner, tmp_path):
    evidence = {"exitCode": 0}
    runner.junit_counts(junit(tmp_path, '<testcase name="a"/><testcase name="b"/>'), evidence)
    assert evidence == {"exitCode": 0, "tests": 2, "failures": 0, "errors": 0, "skipped": 0}


# --- the corpus over two runs --------------------------------------------------------------


class FakeRunner:
    """The few runner names the corpus refusal reads."""

    def __init__(self, run: Path, runner):
        self.RUN, self.Refused = run, runner.Refused


def corpus(run: Path, **value) -> None:
    folder = run / "fixtures"
    folder.mkdir(mode=0o700, exist_ok=True)
    path = folder / "corpus.json"
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        json.dump({"version": "u8-corpus-v1", "chunksPerPaper": 100, **value}, stream)


def test_an_incomplete_corpus_is_refused_with_its_counts(runner, phases, tmp_path):
    corpus(tmp_path, papers=300, target=600, complete=False, remaining=300,
           presentAtStart=0, importedThisRun=300)
    with pytest.raises(runner.Refused, match=r"incomplete \(300 of 600 papers\)"):
        phases.require_complete_corpus(FakeRunner(tmp_path, runner))


def test_a_corpus_never_loaded_is_refused(runner, phases, tmp_path):
    with pytest.raises(runner.Refused, match="has not been loaded"):
        phases.require_complete_corpus(FakeRunner(tmp_path, runner))


def test_a_complete_corpus_is_accepted_and_reported(runner, phases, tmp_path):
    corpus(tmp_path, papers=600, target=600, complete=True, remaining=0,
           presentAtStart=300, importedThisRun=300)
    value = phases.require_complete_corpus(FakeRunner(tmp_path, runner))
    assert value["papers"] == 600 and value["presentAtStart"] == 300


def test_performance_refuses_an_incomplete_corpus(runner, phases, tmp_path):
    corpus(tmp_path, papers=10, target=600, complete=False, remaining=590,
           presentAtStart=0, importedThisRun=10)
    fake = FakeRunner(tmp_path, runner)
    fake.prepare_phase = lambda path: ({"runId": "r"}, {})
    with pytest.raises(runner.Refused, match="incomplete"):
        phases.PHASES["performance"](fake, tmp_path / "environment.json")


def test_the_verification_run_tolerates_only_the_operations_lanes_evidence(
        runner, phases, tmp_path):
    fake = FakeRunner(tmp_path, runner)
    fake.EVIDENCE_PATTERN = runner.EVIDENCE_PATTERN
    # Every operations part's evidence (the person's decision of 2026-10-26; the third
    # part since U8 plan Step 46(b)).
    (tmp_path / "operations-1-evidence-1.json").write_text("{}")
    (tmp_path / "operations-2-evidence-1.json").write_text("{}")
    (tmp_path / "operations-3-evidence-1.json").write_text("{}")
    with pytest.raises(runner.Refused, match="needs the fixtures phase first"):
        phases.run_verification(fake, tmp_path / "environment.json")
    (tmp_path / "integration-1-evidence-2.json").write_text("{}")
    with pytest.raises(runner.Refused, match=r"fresh environment.*integration-1-evidence"):
        phases.run_verification(fake, tmp_path / "environment.json")


def test_the_verification_run_puts_the_whole_database_copies_before_the_corpus(phases):
    assert phases.VERIFICATION_ORDER[:2] == ("restore-paths", "browser-recovery")
    assert phases.JOURNEYS["J09"][1] == "browser-recovery"
    assert phases.BROWSER_SPECS["browser-recovery"] == ("recovery.spec.ts",)
    assert "recovery.spec.ts" not in phases.BROWSER_SPECS["browser-lifecycle"]


def test_a_failed_corpus_leaves_the_later_journeys_unrun_and_the_run_incomplete(
        runner, phases, tmp_path, monkeypatch):
    ran = []
    for name in phases.VERIFICATION_ORDER:
        monkeypatch.setitem(phases.PHASE_RUNNERS, name,
                            lambda r, p, name=name: ran.append(name) or {"state": "passed"})
    monkeypatch.setattr(phases, "complete_corpus",
                        lambda r, p: {"state": "failed", "reason": "corpus incomplete"})
    written = {}
    monkeypatch.setattr("u8_fixtures.write_private",
                        lambda path, value: written.update(value=value))
    fake = FakeRunner(tmp_path, runner)
    fake.EVIDENCE_PATTERN = runner.EVIDENCE_PATTERN
    fake.require = lambda args: SimpleNamespace(stdout="abc\n" if "HEAD" in args else "")
    fake.source_identity = lambda: {"sha256": "s"}
    fake.v1_serving = lambda: True
    fake.private_bytes, fake.MAX_LOG = runner.private_bytes, runner.MAX_LOG
    (tmp_path / "fixtures").mkdir(mode=0o700)
    (tmp_path / "fixtures" / "phase.json").write_text("{}")
    with pytest.raises(runner.Refused, match="incomplete"):
        phases.run_verification(fake, tmp_path / "environment.json")
    assert ran == list(phases.BEFORE_CORPUS)
    assert written["value"]["corpus"]["state"] == "failed"


# --- build batch 9a's review fixes (2026-11-11) ------------------------------------------------
# Placed before the VerificationRun tests, so they run on the realm while Step 97(b) item 17
# still owes the rewrite of that section's first test.


def private_file(path: Path, text: str, at: float | None = None) -> Path:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        stream.write(text)
    if at is not None:
        os.utime(path, (at, at))
    return path


def test_a_phases_kept_evidence_is_found_through_an_evidence_file_past_16_kib(
        runner, phases, tmp_path):
    # A real phase's evidence carries the whole source identity (a digest per file).
    source = {"sha256": "a" * 64,
              "files": {f"backend/module_{index}.py": "b" * 64 for index in range(2000)}}
    evidence = private_file(tmp_path / "accessibility-evidence-1.json", json.dumps(
        {"phase": "accessibility", "source": source, "keptEvidence": "kept-accessibility"}))
    assert evidence.stat().st_size > 16384
    (tmp_path / "kept-accessibility").mkdir(mode=0o700)
    found = phases.kept_folder(ReportRunner(tmp_path, runner), {
        "accessibility": {"state": "passed", "evidence": evidence.name}}, "accessibility")
    assert found == tmp_path / "kept-accessibility"


SOURCE_A, SOURCE_B = "a" * 64, "b" * 64


def coverage_run(run: Path, part: str, at: float, *, sha: str = SOURCE_A,
                 data: str | None = None, changed: bool = False,
                 before: str | None = None) -> None:
    value = {"exitCode": 0, "runId": "r", "source": {"sha256": sha},
             "coverageDataSha256Before": before, "coverageDataSha256": data}
    if changed:
        value["sourceChangedDuringRun"] = True
    private_file(run / f"{part}-evidence-{int(at * 1000)}.json", json.dumps(value), at)


def coverage_data(run: Path, runner, text: str) -> tuple[Path, str]:
    data = private_file(run / runner.COVERAGE_DATA, text)
    return data, runner.coverage_data_sha256(data)


def chain_digest(index: int) -> str:
    """The digest a part's run left in a recorded chain (any distinct text serves)."""
    return f"{index:064x}"


def every_part_on_a(run: Path, runner, start: float, digest_: str,
                    starts: dict[int, str | None] | None = None) -> None:
    """Every part run once on source A, each starting from the data file the run before
    it left (`starts` overrides the digest a part's run found), the last leaving
    `digest_`."""
    last = len(runner.COVERAGE_PARTS) - 1
    for offset, part in enumerate(runner.COVERAGE_PARTS):
        before = None if offset == 0 else chain_digest(offset - 1)
        before = (starts or {}).get(offset, before)
        coverage_run(run, part, start + offset, before=before,
                     data=digest_ if offset == last else chain_digest(offset))


def test_a_superseded_part_run_on_another_source_refuses_the_report(runner, tmp_path):
    data, digest_ = coverage_data(tmp_path, runner, "lines of A and B")
    now = time.time()
    first, second, third = runner.COVERAGE_PARTS[:3]
    coverage_run(tmp_path, first, now - 100)
    coverage_run(tmp_path, second, now - 99)
    coverage_run(tmp_path, third, now - 98, sha=SOURCE_B)       # appended, then replaced
    every_part_on_a(tmp_path, runner, now, digest_)              # every latest names A
    state = runner.coverage_parts_state(tmp_path, "r")
    assert all(item["sourceSha256"] == SOURCE_A for item in state["parts"].values())
    problems = runner.coverage_source_problems(state, data, {"sha256": SOURCE_A})
    # The first part was run again at `now`, so the B run is older than it and harmless:
    assert problems == {"otherSourceParts": [], "dataFileUnbound": False}
    # ...but a B run after the latest first part stays in the data file and refuses it.
    coverage_run(tmp_path, third, now + 0.5, sha=SOURCE_B)
    state = runner.coverage_parts_state(tmp_path, "r")
    assert state["parts"][third]["sourceSha256"] == SOURCE_A
    problems = runner.coverage_source_problems(state, data, {"sha256": SOURCE_A})
    assert problems["otherSourceParts"] == [third]


def test_a_part_run_that_recorded_a_source_change_refuses_the_report(runner, tmp_path):
    data, digest_ = coverage_data(tmp_path, runner, "lines")
    now = time.time()
    every_part_on_a(tmp_path, runner, now, digest_)
    coverage_run(tmp_path, runner.COVERAGE_PARTS[1], now + 0.5, changed=True)
    coverage_run(tmp_path, runner.COVERAGE_PARTS[1], now + 0.7)
    state = runner.coverage_parts_state(tmp_path, "r")
    problems = runner.coverage_source_problems(state, data, {"sha256": SOURCE_A})
    assert problems["otherSourceParts"] == [runner.COVERAGE_PARTS[1]]


def test_a_data_file_changed_by_a_run_without_evidence_refuses_the_report(runner, tmp_path):
    data, digest_ = coverage_data(tmp_path, runner, "the parts' lines")
    every_part_on_a(tmp_path, runner, time.time(), digest_)
    state = runner.coverage_parts_state(tmp_path, "r")
    assert runner.coverage_source_problems(state, data, {"sha256": SOURCE_A}) == {
        "otherSourceParts": [], "dataFileUnbound": False}
    private_file(data, "the parts' lines and an interrupted run's")
    assert runner.coverage_source_problems(state, data, {"sha256": SOURCE_A})[
        "dataFileUnbound"] is True


def test_a_run_without_evidence_between_two_parts_refuses_the_report(runner, tmp_path):
    # An orphaned child on source B appended to the data file after the second part; the
    # third part then found a file its predecessor never left. The last digest matches the
    # file, and every piece of evidence names A, so only the chain shows it.
    data, digest_ = coverage_data(tmp_path, runner, "A's lines and B's")
    every_part_on_a(tmp_path, runner, time.time(), digest_, starts={2: "b" * 64})
    state = runner.coverage_parts_state(tmp_path, "r")
    problems = runner.coverage_source_problems(state, data, {"sha256": SOURCE_A})
    assert problems == {"otherSourceParts": [], "dataFileUnbound": True}


def test_a_first_part_run_without_evidence_partway_refuses_the_report(runner, tmp_path):
    # An orphaned first-part child restarted the file with B's lines after the second
    # part; later parts appended A. The third part's starting digest is that fresh file's.
    data, digest_ = coverage_data(tmp_path, runner, "B's fresh lines, then A's")
    fresh = hashlib.sha256(b"B's fresh lines").hexdigest()
    every_part_on_a(tmp_path, runner, time.time(), digest_, starts={2: fresh})
    state = runner.coverage_parts_state(tmp_path, "r")
    assert runner.coverage_source_problems(state, data, {"sha256": SOURCE_A})[
        "dataFileUnbound"] is True


def test_a_run_since_the_first_part_without_its_starting_digest_refuses_the_report(
        runner, tmp_path):
    data, digest_ = coverage_data(tmp_path, runner, "lines")
    every_part_on_a(tmp_path, runner, time.time(), digest_, starts={1: None})
    state = runner.coverage_parts_state(tmp_path, "r")
    assert runner.coverage_source_problems(state, data, {"sha256": SOURCE_A})[
        "dataFileUnbound"] is True


def test_the_first_parts_own_starting_digest_is_never_checked(runner, tmp_path):
    data, digest_ = coverage_data(tmp_path, runner, "lines")
    every_part_on_a(tmp_path, runner, time.time(), digest_, starts={0: "c" * 64})
    state = runner.coverage_parts_state(tmp_path, "r")
    assert runner.coverage_source_problems(state, data, {"sha256": SOURCE_A}) == {
        "otherSourceParts": [], "dataFileUnbound": False}


def test_the_report_runs_no_child_over_a_superseded_run_on_another_source(
        runner, tmp_path, monkeypatch):
    data, digest_ = coverage_data(tmp_path, runner, "lines")
    now = time.time()
    every_part_on_a(tmp_path, runner, now, digest_)
    coverage_run(tmp_path, runner.COVERAGE_PARTS[2], now + 0.5, sha=SOURCE_B)
    coverage_run(tmp_path, runner.COVERAGE_PARTS[2], now + 0.6)
    written = {}
    monkeypatch.setattr(runner, "RUN", tmp_path)
    monkeypatch.setattr(runner, "prepare_phase", lambda path: ({"runId": "r"}, {}))
    monkeypatch.setattr(runner, "source_identity", lambda: {"sha256": SOURCE_A})
    monkeypatch.setattr(runner, "private_json", lambda path, value: written.update(value))

    def no_child(*args, **kwargs):
        raise AssertionError("no report child runs")

    monkeypatch.setattr(runner, "bounded_process", no_child)
    with pytest.raises(runner.Refused, match="coverage report failed"):
        runner.run_coverage_report(tmp_path / "environment.json")
    assert written["exitCode"] == 1 and written["sourceChangedDuringRun"] is True
    assert written["otherSourceParts"] == [runner.COVERAGE_PARTS[2]]
    assert "supervision" not in written


def test_a_coverage_part_records_the_data_file_it_left(runner, tmp_path, monkeypatch):
    manifest = private_file(tmp_path / "environment.json", "{}")
    written = {}
    monkeypatch.setattr(runner, "RUN", tmp_path)
    monkeypatch.setattr(runner, "prepare_phase", lambda path: (
        {"runId": "r", "locks": {}, "policy": "p"}, {}))
    monkeypatch.setattr(runner, "preserve_prior_report", lambda phase: None)
    monkeypatch.setattr(runner, "source_identity", lambda: {"sha256": SOURCE_A})
    monkeypatch.setattr(runner, "junit_counts", lambda report, evidence: None)
    monkeypatch.setattr(runner, "private_json", lambda path, value: written.update(value))

    def part(args, log, *, environment):
        private_file(Path(environment["COVERAGE_FILE"]), "the part's lines")
        return {"exitCode": 0}

    monkeypatch.setattr(runner, "bounded_process", part)
    found = private_file(tmp_path / runner.COVERAGE_DATA, "the earlier parts' lines")
    found_digest = runner.coverage_data_sha256(found)
    runner.run_phase(runner.COVERAGE_PARTS[0], manifest)
    assert written["coverageDataSha256Before"] == found_digest
    assert written["coverageDataSha256"] == runner.coverage_data_sha256(
        tmp_path / runner.COVERAGE_DATA)
    assert written["coverageDataSha256"] != found_digest


class Clock:
    """A monotonic clock that moves only when a test or a sleep moves it."""

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


@pytest.mark.parametrize(("answer_at", "passes"), [(179.875, True), (180.0, False),
                                                   (181.0, False)])
def test_the_restart_figure_is_read_after_the_ready_answer_and_180_s_fails(
        phases, monkeypatch, answer_at, passes):
    from backend.u8_registry import REQUIRED

    clock = Clock()
    clocked(phases, monkeypatch, clock)
    monkeypatch.setattr(phases, "observed_afresh", lambda runner, value, horizon: set(REQUIRED))
    clock.now = 179.875  # the loop's check passes here; the answer arrives at `answer_at`

    def ready() -> bool:
        clock.now = answer_at
        return True

    monkeypatch.setattr(phases, "local_ready", ready)
    figure = phases.wait_ready_afresh(SimpleNamespace(), {}, None, 1, 0.0, 300.0)
    if passes:
        assert figure is not None and 179.8 < figure < phases.RESTART_READY_SECONDS
    else:
        assert figure is None


def test_a_figure_just_below_the_bound_is_never_written_as_the_bound(phases, monkeypatch):
    clock = Clock(179.996)
    clocked(phases, monkeypatch, clock)
    assert phases.ready_figure(0.0) == 179.99


def test_a_first_ready_answer_after_the_margin_sends_no_kill(phases, monkeypatch):
    clock = Clock(85.0)  # 215 s of a 300 s deadline remain
    clocked(phases, monkeypatch, clock)

    def ready() -> bool:
        clock.now = 95.0  # 205 s remain: less than the wait and its margin
        return True

    monkeypatch.setattr(phases, "local_ready", ready)
    process = SimpleNamespace(poll=lambda: None)
    assert phases.wait_first_ready(SimpleNamespace(), process, 300.0) is False


class Killed:
    pid = 4242

    def wait(self, timeout=None):
        return -9

    def poll(self):
        return -9


def restart_runner(runner, phases, monkeypatch, tmp_path, stopped):
    monkeypatch.setattr(phases, "source_rule_start", lambda runner_: {})
    monkeypatch.setattr(phases, "source_rule_end", lambda runner_, source, evidence: evidence)
    monkeypatch.setattr(phases, "record", lambda runner_, phase, evidence: evidence)
    monkeypatch.setattr(phases, "wait_first_ready", lambda runner_, process, deadline: True)
    return SimpleNamespace(
        RUN=tmp_path, Refused=runner.Refused, PHASE_SECONDS=300,
        prepare_phase=lambda path: ({"runId": "r", "container": "c"}, {}),
        native=lambda value: False, stop=stopped.append,
        signal_group=lambda pid, signum: None, group_states=lambda pid: [])


def test_a_relaunch_refused_after_the_kill_never_stops_the_reaped_group(
        runner, phases, monkeypatch, tmp_path):
    stopped, killed, calls = [], Killed(), []

    def start(runner_, path, log, *, staged):
        calls.append(log)
        if len(calls) == 1:
            return killed
        raise runner.Refused("the served realm was not ready within 60 seconds")

    fake = restart_runner(runner, phases, monkeypatch, tmp_path, stopped)
    monkeypatch.setattr(phases, "start_realm", start)
    monkeypatch.setattr(phases, "read_horizon", lambda runner_, value: 7)
    evidence = phases.run_restart(fake, tmp_path / "environment.json", "host")
    assert evidence["exitCode"] == 1 and "not ready within 60" in evidence["failureReason"]
    assert stopped == [] and len(calls) == 2


def test_a_database_error_after_the_kill_is_recorded_not_raised(
        runner, phases, monkeypatch, tmp_path):
    import psycopg

    stopped = []
    fake = restart_runner(runner, phases, monkeypatch, tmp_path, stopped)
    monkeypatch.setattr(phases, "start_realm", lambda *args, **kwargs: Killed())

    def horizon(runner_, value):
        raise psycopg.OperationalError("the database went away")

    monkeypatch.setattr(phases, "read_horizon", horizon)
    evidence = phases.run_restart(fake, tmp_path / "environment.json", "host")
    assert evidence["exitCode"] == 1 and evidence["failureCategory"] == "OperationalError"
    assert evidence["failureReason"] is None and stopped == []


@pytest.mark.parametrize(("ready", "code"), [(180.0, 1), (179.99, 0)])
def test_the_restart_verdict_fails_a_figure_at_the_bound(
        runner, phases, monkeypatch, tmp_path, ready, code):
    stopped = []
    fake = restart_runner(runner, phases, monkeypatch, tmp_path, stopped)
    live = Killed()
    monkeypatch.setattr(phases, "start_realm", lambda *args, **kwargs: live)
    monkeypatch.setattr(phases, "restart_host",
                        lambda *args: args[-1].update(readySeconds=ready))
    evidence = phases.run_restart(fake, tmp_path / "environment.json", "host")
    assert evidence["exitCode"] == code and stopped == [live]


def test_the_database_restart_is_timed_from_before_docker_start_and_holds_the_tree(
        runner, phases, monkeypatch):
    import psycopg

    from backend.u8_registry import REQUIRED

    clock = Clock()
    monkeypatch.setattr(phases, "time", SimpleNamespace(
        monotonic=clock.monotonic, sleep=clock.sleep, time=time.time, time_ns=time.time_ns))
    held = []
    monkeypatch.setattr(phases, "hold_tree", lambda *args: held.append(clock.now))

    def require(args, timeout):
        assert timeout > 0
        if args[1] == "start":
            clock.now += 5.0
        return SimpleNamespace(stdout='[{"State": {"StartedAt": "2026-11-11T00:00:00Z"}}]')

    answers = iter([psycopg.OperationalError("starting"), 7])

    def horizon(runner_, value):
        answer = next(answers)
        if isinstance(answer, Exception):
            raise answer
        return answer

    monkeypatch.setattr(phases, "read_horizon", horizon)
    monkeypatch.setattr(phases, "observed_afresh", lambda runner_, value, h: set(REQUIRED))
    monkeypatch.setattr(phases, "local_ready", lambda: True)
    fake = SimpleNamespace(Refused=runner.Refused, require=require, command=lambda args, timeout:
                           SimpleNamespace(stdout=phases.CRASH_RECOVERY, stderr=""))
    evidence: dict = {}
    phases.restart_database(fake, {"container": "c"}, {"process": None}, 300.0, evidence)
    assert evidence["readySeconds"] >= 5.0 and evidence["crashRecovery"] is True
    assert len(held) >= 3  # two horizon polls, then the readiness wait's own


@pytest.mark.parametrize("answer", ["[]", "{}", "not json", '[{"State": {}}]',
                                    '[{"State": {"StartedAt": 3}}]'])
def test_an_unreadable_docker_inspect_answer_is_a_recorded_refusal(runner, phases, answer):
    with pytest.raises(runner.Refused, match="no start time"):
        phases.started_at_of(SimpleNamespace(Refused=runner.Refused), answer)


@pytest.fixture
def workspace(phases):
    import u8_build_workspace

    return u8_build_workspace


@pytest.mark.parametrize("markup", [
    "<p><![CDATA[ > <script>alert(1)</script> ]]></p>",
    "<svg><style><script>alert(1)</script></style></svg>",
    "<math><style><img src=x onerror=alert(1)></style></math>",
    '<a href="\x01javascript:alert(1)">x</a>',
    '<a href="\x1b java\tscript:alert(1)">x</a>',
    # html.parser reads title and textarea as RCDATA; inside svg or math a browser does not.
    "<svg><title><img src=x onerror=alert(1)></title></svg>",
    "<math><textarea><img src=x onerror=alert(1)></textarea></math>",
    # A browser ignores the other namespace's end tag, so math is still open here.
    "<math></svg><style><img src=x onerror=alert(1)></style></math>",
    # Raw text to a browser, markup to html.parser.
    '<noscript><p title="</noscript><img src=x onerror=alert(1)>"></noscript>',
    "<xmp></xmp><p>x</p>",
    '<iframe srcdoc="&lt;script&gt;alert(1)&lt;/script&gt;"></iframe>',
    "<noembed></noembed>",
    "<noframes></noframes>",
    "<plaintext>",
])
def test_markup_a_browser_runs_but_html_parser_hides_is_refused(workspace, tmp_path, markup):
    (tmp_path / "index.html").write_text(f"<!doctype html><html><body>{markup}</body></html>")
    with pytest.raises(workspace.BuildRefused, match=workspace.INLINE_SCRIPT):
        workspace.refuse_inline_scripts(tmp_path)


def test_a_page_with_a_style_and_a_drawing_but_no_script_passes(workspace, tmp_path):
    (tmp_path / "index.html").write_text(
        "<!doctype html><html><head><style>p { color: red }</style></head><body>"
        '<svg><path d="M0 0"/></svg><a href="https://docsuri.example/">x</a>'
        '<script type="module" src="/assets/index-AbCdEf12.js"></script></body></html>')
    workspace.refuse_inline_scripts(tmp_path)


def test_a_title_a_textarea_and_a_style_after_a_closed_drawing_pass(workspace, tmp_path):
    (tmp_path / "index.html").write_text(
        "<!doctype html><html><head><title>DocSuri</title></head><body>"
        '<svg><path d="M0 0"/></svg><math><mi>x</mi></math>'
        "<textarea>note</textarea><style>p { color: red }</style></body></html>")
    workspace.refuse_inline_scripts(tmp_path)


def vite_stand_in(index: str, files: dict[str, bytes]):
    def run(frontend: Path) -> dict:
        dist = frontend / "dist"
        dist.mkdir(parents=True, exist_ok=True)
        (dist / "index.html").write_text(index)
        for page in ("privacy.html", "terms.html", "maintenance.html"):
            (dist / page).write_text("<!doctype html><p>page</p>")
        for name, raw in files.items():
            (dist / name).parent.mkdir(parents=True, exist_ok=True)
            (dist / name).write_bytes(raw)
        return {}

    return run


ENTRY = '<!doctype html><script type="module" src="/assets/index-AbCdEf12.js"></script>'


@pytest.mark.parametrize(("files", "reason"), [
    ({"assets/index-AbCdEf12.js": os.urandom(350_000)}, "passes its budget"),
    ({}, "names a file the build lacks"),
])
def test_a_build_refused_for_its_first_load_leaves_no_manifest(workspace, tmp_path, files,
                                                              reason):
    (tmp_path / "dist").mkdir()
    (tmp_path / "dist" / workspace.MANIFEST).write_text("{}")  # an earlier build's
    with pytest.raises(workspace.BuildRefused, match=reason):
        workspace.build(tmp_path, run=vite_stand_in(ENTRY, files))
    assert not (tmp_path / "dist" / workspace.MANIFEST).exists()


def test_a_build_within_its_budget_writes_its_manifest(workspace, tmp_path):
    result = workspace.build(tmp_path, run=vite_stand_in(
        ENTRY, {"assets/index-AbCdEf12.js": b"export const a = 1;\n"}))
    assert result["state"] == "built" and result["firstLoad"]["withinBudget"] is True
    listed = json.loads((tmp_path / "dist" / workspace.MANIFEST).read_text())
    assert {item["path"] for item in listed["files"]} >= {"index.html",
                                                          "assets/index-AbCdEf12.js"}


# --- 1. a wrong or expired environment -------------------------------------------------------


def test_every_phase_refuses_an_environment_other_than_the_realms_own(
        runner, tmp_path, monkeypatch):
    other = tmp_path / "environment.json"
    other.write_text("{}")
    for phase in runner.PHASES:
        monkeypatch.setattr(sys, "argv", ["verify_docsuri_u8.py", "--phase", phase,
                                          "--profile", "synthetic-local",
                                          "--environment-file", str(other)])
        with pytest.raises(runner.Refused, match="only the explicit U8 owned manifest"):
            runner.main()


def test_an_expired_environment_is_refused_before_any_phase_runs(runner, monkeypatch):
    import backend.local_profile as local_profile

    manifest = Path(runner.RUN) / "environment.json"
    if not manifest.exists():
        pytest.fail("the realm's environment is set up before the operations phase")
    expires = json.loads(manifest.read_text())["expiresAt"]
    later = expires + 1
    monkeypatch.setattr(local_profile.time, "time", lambda: later)
    with pytest.raises(ValueError, match="retention expired"):
        runner.prepare_phase(manifest)


def test_the_preserved_identity_admits_the_realm_where_a_runtime_profile_would_not(
        runner, tmp_path):
    manifest = Path(runner.RUN) / "environment.json"
    if not manifest.exists():
        pytest.fail("the realm's environment is set up before the operations phase")
    value = runner.preservation_manifest(manifest)
    assert value["unit"] == runner.UNIT and value["realm"] == runner.REALM
    assert value["database"] == runner.DATABASE
    assert value["container"] == value["runId"]
    with pytest.raises(ValueError):
        runner.preservation_manifest(tmp_path / "environment.json")


def test_the_v1_stop_runs_on_the_preserved_identity_where_v1_up_is_refused(
        runner, tmp_path, monkeypatch):
    import backend.local_profile as local_profile

    manifest = Path(runner.RUN) / "environment.json"
    if not manifest.exists():
        pytest.fail("the realm's environment is set up before the operations phase")
    expires = json.loads(manifest.read_text())["expiresAt"]
    monkeypatch.setattr(local_profile.time, "time", lambda: expires + 1)
    # Starting v1 on the expired realm is refused before anything runs...
    with pytest.raises(ValueError, match="retention expired"):
        runner.run_v1("v1-up", manifest)
    # ...while the stop proceeds on the realm's preserved identity, with the
    # lighter check set (custody and a stopped application, no memory preflight
    # or frozen locks). The child is the only piece faked: no test stops the
    # realm's real v1.
    value = runner.preservation_manifest(manifest)
    asked = []
    monkeypatch.setattr(runner, "preservation_manifest",
                        lambda path: asked.append(path) or value)
    monkeypatch.setattr(runner, "require_resources", lambda value: None)
    monkeypatch.setattr(runner, "require_key_folders", lambda: None)
    monkeypatch.setattr(runner, "RUN", tmp_path)
    tmp_path.chmod(0o700)
    real_private_json = runner.private_json
    monkeypatch.setattr(runner, "private_json",
                        lambda path, value: real_private_json(path, value, root=tmp_path))

    def fake_child(args, log, *, seconds):
        descriptor = os.open(log, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w") as stream:
            stream.write(json.dumps({"state": "v1-down"}) + "\n")
        return {"exitCode": 0, "reason": "process-exit", "peakRssBytes": 0, "logBytes": 0}

    monkeypatch.setattr(runner, "bounded_process", fake_child)
    result = runner.run_v1("v1-down", manifest)
    assert result == {"state": "passed", "phase": "v1-down"}
    assert asked == [manifest]
    (evidence,) = tmp_path.glob("v1-down-evidence-*.json")
    recorded = json.loads(evidence.read_text())
    assert recorded["exitCode"] == 0 and recorded["resources"] is None


# --- 3. the VerificationRun -------------------------------------------------------------------


class ReportRunner:
    """The runner names the VerificationRun reads: its run root and the private reader."""

    def __init__(self, run: Path, runner):
        self.RUN, self.MAX_LOG = run, runner.MAX_LOG
        self.private_bytes = runner.private_bytes


def journey_report(path: Path, cases: dict[str, str]) -> None:
    body = "".join(
        f'<testcase name="{name}">' + ("<failure/>" if result == "failed" else
                                       "<skipped/>" if result == "skipped" else "")
        + "</testcase>" for name, result in cases.items())
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        stream.write(f"<testsuites><testsuite>{body}</testsuite></testsuites>")


def kept_a11y_evidence(run: Path, phases_module, phase: str) -> str:
    """The phase's evidence file, whose kept folder holds, for each screen `A11Y_SCREENS`
    gives that phase, a passing check record (with `appShell` and passing `liveRegions`,
    Step 95(g)), its capture and both visit records (Step 97(b) item 17)."""
    kept = run / f"kept-evidence/{phase}-1"
    test = kept / "a-test"
    test.mkdir(mode=0o700, parents=True, exist_ok=True)
    for screen, owner in phases_module.A11Y_SCREENS.items():
        if owner != phase:
            continue
        capture = private_file(test / f"320-{screen}.png", f"capture of {screen}")
        private_file(test / f"a11y-check-{screen}.json", json.dumps({
            "violations": [], "colorContrastEvaluated": True, "sidewaysScroll": False,
            "capture": capture.name, "captureSha256": phases_module.file_sha256(capture),
            "appShell": True, "liveRegions": [
                {"role": "status", "ariaLive": "polite", "testId": "announcer",
                 "insideMain": False}]}))
        for kind in ("keyboard", "focus"):
            private_file(test / f"a11y-{kind}-{screen}.json", "{}")
    name = f"{phase}-evidence.json"
    private_file(run / name, json.dumps({"phase": phase,
                                         "keptEvidence": f"kept-evidence/{phase}-1"}))
    return name


def every_report(run: Path, phases_module, *, failing: str | None = None) -> dict:
    """A passing report for every journey in its phase, `failing` failed; and, for each
    phase of `A11Y_PHASES`, the state `passed` with its evidence file's name, its report
    holding a passing `[A11Y]` test. Each phase `A11Y_SCREENS` names (the three
    accessibility phases, `security`, `browser-migration` and `browser-cutover`) writes its
    evidence file and kept records (Step 97(b) item 17)."""
    by_report: dict[str, dict[str, str]] = {}
    for journey, (_, phase) in phases_module.JOURNEYS.items():
        for report in phases_module.PHASE_REPORTS.get(phase, ())[-1:]:
            by_report.setdefault(report, {})[f"[{journey}] a journey"] = (
                "failed" if journey == failing else "passed")
    for phase in phases_module.A11Y_PHASES:
        by_report.setdefault(f"{phase}.xml", {})["[A11Y] a screen"] = "passed"
    for report, cases in by_report.items():
        journey_report(run / report, cases)
    value = {phase: {"state": "passed", "evidence": f"{phase}-evidence.json"}
             for phase in (*phases_module.VERIFICATION_ORDER, *phases_module.A11Y_PHASES)}
    for phase in {*phases_module.A11Y_PHASES, "security", "browser-migration",
                  "browser-cutover", *phases_module.A11Y_SCREENS.values()}:
        value[phase]["evidence"] = kept_a11y_evidence(run, phases_module, phase)
    return value


def record_of(runner, phases_module, run: Path, phases: dict) -> dict:
    import datetime as dt

    return phases_module.verification_record(
        ReportRunner(run, runner), phases, commit="0" * 40, source={"sha256": "a" * 64},
        started=dt.datetime.now(dt.UTC), committed=True)


def test_the_verification_run_names_every_journey_with_its_result_and_evidence(
        runner, phases, tmp_path):
    value = record_of(runner, phases, tmp_path, every_report(tmp_path, phases))
    assert value["result"] == "passed" and value["passed"] is True
    assert value["failedPhases"] == [] and value["a11yProblems"] == []
    assert set(value) >= {"runId", "commit", "sourceSha256", "sourceState", "journeys",
                          "gaps", "result", "startedAt", "finishedAt", "phases"}
    assert [item["journeyId"] for item in value["journeys"]] == list(phases.JOURNEYS)
    for item in value["journeys"]:
        assert set(item) == {"journeyId", "name", "result", "phase", "evidenceRef"}
        assert item["evidenceRef"] == f"{item['phase']}-evidence.json"
    # Drafts as they ship are recorded as the gap owed before release.
    assert value["gaps"] == [{"journeyId": "J06", "gap": "durable-drafts-switched-off",
                              "owedBefore": "release"}]


def test_the_verification_run_refuses_passed_with_a_phase_missing_skipped_or_failed(
        runner, phases, tmp_path):
    complete = every_report(tmp_path, phases)
    missing = {name: value for name, value in complete.items() if name != "browser-cutover"}
    assert record_of(runner, phases, tmp_path, missing)["result"] == "incomplete"
    failed = {**complete, "accessibility": {"state": "failed", "reason": "refused"}}
    value = record_of(runner, phases, tmp_path, failed)
    assert value["result"] == "failed"
    assert next(item for item in value["journeys"]
                if item["journeyId"] == "A11Y")["result"] == "failed"
    # With every accessibility phase's evidence written (Step 97(b) item 17), A11Y passes,
    # so the run's failure below is J11's own.
    every_report(tmp_path, phases, failing="J11")
    value = record_of(runner, phases, tmp_path, complete)
    results = {item["journeyId"]: item["result"] for item in value["journeys"]}
    assert value["result"] == "failed" and value["failedPhases"] == []
    assert results["J11"] == "failed" and results["A11Y"] == "passed"
    # A skipped test is never a pass.
    journey_report(tmp_path / "browser-cutover.xml", {"[J11] a journey": "skipped"})
    value = record_of(runner, phases, tmp_path, complete)
    results = {item["journeyId"]: item["result"] for item in value["journeys"]}
    assert value["result"] == "failed"
    assert results["J11"] == "failed" and results["A11Y"] == "passed"


# --- 4. compatibility's skip -------------------------------------------------------------------


def test_compatibility_says_it_is_skipped_while_no_v2_tag_exists(
        runner, phases, tmp_path, monkeypatch, capsys):
    recorded = {}
    fake = FakeRunner(tmp_path, runner)
    fake.prepare_phase = lambda path: ({"runId": "docsuri-u8-0000000000000000"}, {})
    monkeypatch.setattr(phases, "previous_tag", lambda: None)
    monkeypatch.setattr(phases, "record",
                        lambda runner_, phase, evidence: recorded.setdefault(phase, evidence))
    phases.run_compatibility(fake, tmp_path / "environment.json")
    assert "compatibility skipped: no v2 tag exists yet" in capsys.readouterr().out
    evidence = recorded["compatibility"]
    assert (evidence["skipped"], evidence["skippedReason"], evidence["exitCode"]) == (
        True, "no v2 tag exists yet", 0)


# --- 5. the repair exercise's record ---------------------------------------------------------


def trace(path: Path, lines: list[dict]) -> Path:
    path.write_text("".join(json.dumps(line) + "\n" for line in lines))
    return path


def test_the_repair_exercise_follows_the_failing_request_to_the_resolver(phases, tmp_path):
    found = phases.follow_request(trace(tmp_path / "trace.jsonl", [
        {"kind": "failing-request", "requestId": "r-2"},
        {"kind": "log", "requestId": "r-1", "event": "navigation.resolved",
         "location": "elsewhere"},
        {"kind": "log", "requestId": "r-2", "event": "navigation.resolved",
         "location": "u8_routes.navigation_items"},
    ]))
    assert found == {"requestId": "r-2", "location": "u8_routes.navigation_items",
                     "event": "navigation.resolved"}
    assert phases.follow_request(tmp_path / "missing.jsonl") is None
    assert phases.follow_request(trace(tmp_path / "none.jsonl", [{"kind": "log"}])) is None


def test_the_repair_exercise_passes_only_on_a_failure_traced_to_the_resolver_then_a_repair(
        phases):
    traced = {"location": "u8_routes.navigation_items"}
    broken = {"exitCode": 1, "failures": 2, "traced": traced}
    repaired = {"exitCode": 0, "tests": 3, "failures": 0, "errors": 0}
    assert phases.repair_passed(broken, repaired)
    # The defect must make the checks fail, and the failure must lead to the resolver.
    assert not phases.repair_passed({**broken, "exitCode": 0, "failures": 0}, repaired)
    assert not phases.repair_passed({**broken, "traced": None}, repaired)
    assert not phases.repair_passed({**broken, "traced": {"location": "u8_registry"}},
                                    repaired)
    # The repair must pass, with tests that ran.
    assert not phases.repair_passed(broken, {**repaired, "exitCode": 1, "failures": 1})
    assert not phases.repair_passed(broken, {**repaired, "tests": 0})


# --- 6. the stand-ins refuse the production profile ------------------------------------------


def test_every_stand_in_refuses_the_production_profile(phases):
    import serve_docsuri_u8
    import u8_identity_standin
    import u8_tunnel_standin

    production = SimpleNamespace(is_production=True, realm="production",
                                 database_name="docsuri_v2")
    disguised = SimpleNamespace(is_production=True, realm="service-operations",
                                database_name="docsuri_u8")
    for profile in (production, disguised):
        for refuse in (u8_tunnel_standin.require_realm, u8_identity_standin.require_realm,
                       serve_docsuri_u8.require_realm):
            with pytest.raises(ValueError):
                refuse(profile)


def test_the_cutover_stage_refuses_every_environment_but_the_composed_realms(
        monkeypatch, capsys):
    from tests.u8_service_operations_integration import cutover_stage

    monkeypatch.setattr(cutover_stage, "_paths", lambda: None)
    import backend.local_profile as local_profile

    monkeypatch.setattr(local_profile.LocalProfile, "load", staticmethod(
        lambda path: SimpleNamespace(is_production=True, realm="production",
                                     database_name="docsuri_v2", root=Path("/nowhere"))))
    assert cutover_stage.main(["--environment-file", "/tmp/docsuri-u8-run/environment.json"]) == 1
    assert json.loads(capsys.readouterr().out)["state"] == "refused"


# --- the split lanes (the person's decision of 2026-10-23, "Split into parts") ---------------


def folder_files(runner, folder: str) -> set[str]:
    return {path.name for path in
            (Path(runner.ROOT) / runner.TEST_ROOT / folder).glob("test_*.py")}


def part_names(runner, parts: dict) -> list[str]:
    return [Path(item).name for part in parts for item in runner.lane_paths(part)]


def test_the_integration_halves_hold_every_integration_file_exactly_once(runner):
    # Build and Test loop-back 1 (U8 plan Step 46(a)): four parts.
    assert list(runner.INTEGRATION_HALVES) == [
        "integration-1", "integration-2", "integration-3", "integration-4"]
    named = part_names(runner, runner.INTEGRATION_HALVES)
    assert sorted(named) == sorted(folder_files(runner, "integration"))
    assert len(named) == len(set(named))
    assert [Path(item).name for item in runner.lane_paths("integration-3")] == [
        "test_account_mail_routes.py", "test_cutover_journeys.py", "test_health_api.py"]
    assert [Path(item).name for item in runner.lane_paths("integration-4")][:4] == [
        "test_migration_run.py", "test_production_migration_platform.py",
        "test_start_checks.py", "test_production_composition.py"]


def test_the_component_halves_hold_every_component_file_exactly_once(runner):
    # U8 plan Step 46(b): the Stage and journey-database files run in a part of their own.
    assert list(runner.COMPONENT_HALVES) == ["component-1", "component-2"]
    assert [Path(item).name for item in runner.lane_paths("component-1")] == [
        "test_cutover_machine.py", "test_cutover_words.py", "test_disposal_pass.py",
        "test_soak_and_rehearsal.py", "test_volume_retirement.py"]
    named = part_names(runner, runner.COMPONENT_HALVES)
    assert sorted(named) == sorted(folder_files(runner, "component"))
    assert len(named) == len(set(named))


def test_the_assistance_journey_runs_first_in_its_part(runner):
    # PaperAssistance admits at most four open or running items realm-wide, and later
    # integration files leave open admissions behind.
    first = runner.lane_paths("integration-1")
    assert Path(first[0]).name == "test_complete_assistance.py"


@pytest.mark.parametrize("folder", ["component", "integration", "operations"])
@pytest.mark.parametrize("change", ["drop", "repeat", "absent"])
def test_lane_paths_refuses_overlapping_or_missing_parts(runner, monkeypatch, change,
                                                         folder):
    halves = runner.LANE_HALVES[folder]
    parts = [list(files) for files in halves.values()]
    last = parts[-1]
    if change == "drop":
        parts[-1] = last[1:]                 # its first file is in no part
    elif change == "repeat":
        parts[-1] = [*last, parts[0][0]]     # the first part's first file is in two parts
    else:
        parts[-1] = [*last, "test_not_there.py"]  # a file the folder lacks
    monkeypatch.setitem(runner.LANE_HALVES, folder, dict(zip(
        halves, (tuple(files) for files in parts), strict=True)))
    for part in halves:
        with pytest.raises(runner.Refused, match=f"every {folder} file once"):
            runner.lane_paths(part)


def test_each_part_names_exactly_its_files(runner, tmp_path):
    """The expected paths come from each part's own tuple, never from `lane_paths`, which
    `phase_command` calls itself: a path that never reaches the command fails here."""
    for folder, parts in (("component", runner.COMPONENT_HALVES),
                          ("integration", runner.INTEGRATION_HALVES),
                          ("operations", runner.OPERATIONS_HALVES)):
        for part in parts:
            expected = [f"{runner.TEST_ROOT}/{folder}/{name}" for name in parts[part]]
            for phase in (part, f"coverage-{part}"):
                args, _paths = runner.phase_command(phase, tmp_path / f"{phase}.xml")
                assert [item for item in args if item.startswith(runner.TEST_ROOT)] == expected
                assert ("--cov" in args) is (phase in runner.COVERAGE_PARTS)
                assert ("--cov" in args) is phase.startswith("coverage-")


# --- the operations halves (the person's decision of 2026-10-26, "Split it in two") ---------


def test_the_operations_halves_hold_every_operations_file_exactly_once(runner):
    assert list(runner.OPERATIONS_HALVES) == ["operations-1", "operations-2", "operations-3"]
    first, second, third = (runner.lane_paths(half) for half in runner.OPERATIONS_HALVES)
    named = [Path(item).name for item in (*first, *second, *third)]
    assert sorted(named) == sorted(folder_files(runner, "operations"))
    assert len(named) == len(set(named))
    assert all(Path(item).parent.name == "operations" for item in (*first, *second, *third))
    # This file itself is in a part, so the runner's own tests run.
    assert Path(__file__).name in named
    # The slowest file (141 s of the 2026-10-26 run's 245.6 s) still leads its own part.
    assert Path(first[0]).name == "test_production_cutover_wiring.py"
    assert "test_release_install.py" in {Path(item).name for item in second}
    # U8 plan Step 46(b): the five files later steps change moved to `operations-3`.
    assert [Path(item).name for item in third][:5] == [
        "test_backup_agent_commands.py", "test_backup_agent_disposal.py",
        "test_backup_agent_writing.py", "test_production_wiring.py",
        "test_standing_lanes.py"]


def test_the_composite_and_coverage_names_carry_every_part(runner):
    assert runner.COMPOSITE_PHASES["component"] == ("component-1", "component-2")
    assert runner.COMPOSITE_PHASES["integration"] == (
        "integration-1", "integration-2", "integration-3", "integration-4")
    assert runner.COMPOSITE_PHASES["operations"] == (
        "operations-1", "operations-2", "operations-3")
    coverage = (
        "coverage-database", "coverage-repository",
        "coverage-component-1", "coverage-component-2",
        "coverage-integration-1", "coverage-integration-2",
        "coverage-integration-3", "coverage-integration-4",
        "coverage-operations-1", "coverage-operations-2", "coverage-operations-3")
    assert runner.COMPOSITE_PHASES["coverage"] == (*coverage, "coverage-report")
    assert runner.COVERAGE_PARTS == coverage
    assert runner.COVERAGE_PARTS[-3:] == (
        "coverage-operations-1", "coverage-operations-2", "coverage-operations-3")
    parts = (*runner.COMPONENT_HALVES, *runner.INTEGRATION_HALVES, *runner.OPERATIONS_HALVES)
    for name in (*parts, *coverage):
        assert name in runner.TEST_PHASES and name in runner.PHASES
    for name in ("coverage-component", "coverage-operations"):
        assert name not in runner.TEST_PHASES and name not in runner.PHASES
    # Only the integration parts send real mail, so only they need the synthetic v1 and
    # the send headroom.
    assert runner.SENDING_PHASES == (
        "integration-1", "integration-2", "integration-3", "integration-4",
        "coverage-integration-1", "coverage-integration-2",
        "coverage-integration-3", "coverage-integration-4")


def phase_fakes(runner, monkeypatch, tmp_path) -> tuple[list[dict], dict]:
    """`run_phase` with its realm checks faked: each child call and each evidence file
    is recorded, and the child writes a one-test report."""
    calls, written = [], {}

    def child(args, log, **options):
        calls.append({"args": args, "options": options})
        report = Path(next(item for item in args if item.startswith("--junitxml="))
                      .removeprefix("--junitxml="))
        report.write_text('<testsuite><testcase classname="c" name="n"/></testsuite>')
        os.chmod(report, 0o600)  # the runner reads only a private report
        return {"exitCode": 0}

    monkeypatch.setattr(runner, "RUN", tmp_path)
    monkeypatch.setattr(runner, "prepare_phase", lambda path: (
        {"runId": "r", "locks": {}, "policy": "p"}, {}))
    monkeypatch.setattr(runner, "require_test_paths", lambda paths: None)
    monkeypatch.setattr(runner, "preserve_prior_report", lambda phase: [])
    monkeypatch.setattr(runner, "source_identity", lambda: {"sha256": "s"})
    monkeypatch.setattr(runner, "digest", lambda path: "d")
    monkeypatch.setattr(runner, "bounded_process", child)
    monkeypatch.setattr(runner, "private_json",
                        lambda path, value: written.__setitem__(path.name, value))
    monkeypatch.setattr(runner, "safe_phase_summary", lambda evidence: {})
    # Step 98(d), G3: no Docker call; the two removal tests stub `command` instead.
    monkeypatch.setattr(runner, "remove_production_instances", lambda: [])
    monkeypatch.setattr(runner, "remove_peer_proofs", lambda: [])
    return calls, written


def test_the_operations_phase_runs_each_half_under_its_own_bound(runner, monkeypatch,
                                                                 tmp_path):
    import inspect

    # The real supervisor's bound, read before the fakes replace it.
    bound = inspect.signature(runner.bounded_process).parameters["seconds"].default
    assert bound == runner.PHASE_SECONDS == 300
    for folder, parts in (("component", runner.COMPONENT_HALVES),
                          ("operations", runner.OPERATIONS_HALVES)):
        calls, written = phase_fakes(runner, monkeypatch, tmp_path)
        assert runner.run_test_phase(folder, Path("e")) == {
            "state": "passed", "phase": folder, "parts": list(parts)}
        # One child per part, in order, each naming only its part's files.
        assert len(calls) == len(parts)
        for call, half in zip(calls, parts, strict=True):
            assert [item for item in call["args"] if item.startswith(runner.TEST_ROOT)] == [
                f"{runner.TEST_ROOT}/{folder}/{name}" for name in parts[half]]
            assert f"--junitxml={tmp_path / f'{half}.xml'}" in call["args"]
            assert "--cov" not in call["args"]
            # No bound is passed, so each child has the supervisor's own 300 s bound.
            assert "seconds" not in call["options"]
        # Each part writes one evidence file, under its own name and bound.
        evidence = sorted(written.values(), key=lambda item: item["phase"])
        assert [item["phase"] for item in evidence] == list(parts)
        assert all(item["phaseBoundSeconds"] == 300 and item["exitCode"] == 0 and
                   item["tests"] == 1 for item in evidence)
        assert all(name.startswith(f"{item['phase']}-evidence-")
                   for name, item in written.items())


def test_a_failed_first_operations_half_leaves_the_second_unrun(runner, monkeypatch,
                                                                tmp_path):
    calls, _written = phase_fakes(runner, monkeypatch, tmp_path)
    monkeypatch.setattr(runner, "bounded_process", lambda args, log, **options: (
        calls.append(args), {"exitCode": 1})[1])
    with pytest.raises(runner.Refused, match="U8 phase failed"):
        runner.run_test_phase("operations", Path("e"))
    assert len(calls) == 1


def test_the_coverage_operations_halves_append_to_the_one_data_file(runner, monkeypatch,
                                                                     tmp_path):
    calls, written = phase_fakes(runner, monkeypatch, tmp_path)
    halves = (*runner.OPERATIONS_HALVES, *runner.COMPONENT_HALVES)
    for half in halves:
        part = f"coverage-{half}"
        assert runner.run_test_phase(part, Path("e")) == {"state": "passed", "phase": part}
    for call, half in zip(calls, halves, strict=True):
        assert [item for item in call["args"] if item.startswith(runner.TEST_ROOT)] == list(
            runner.lane_paths(half))
        assert "--cov-append" in call["args"] and "--cov-fail-under=0" in call["args"]
        assert call["options"]["environment"]["COVERAGE_FILE"] == str(
            tmp_path / runner.COVERAGE_DATA)
        assert "seconds" not in call["options"]
    assert sorted(item["phase"] for item in written.values()) == [
        "coverage-component-1", "coverage-component-2", "coverage-operations-1",
        "coverage-operations-2", "coverage-operations-3"]


def test_coverage_parts_append_to_one_data_file_after_the_first(runner, tmp_path):
    commands = {part: runner.phase_command(part, tmp_path / f"{part}.xml")[0]
                for part in runner.COVERAGE_PARTS}
    assert "--cov-append" not in commands[runner.COVERAGE_PARTS[0]]
    assert all("--cov-append" in commands[part] for part in runner.COVERAGE_PARTS[1:])
    assert all("--cov" in args and "--cov-report=" in args for args in commands.values())
    # The floor is the report's, on the combined data, never a part's own slice.
    assert all("--cov-fail-under=0" in args for args in commands.values())


def test_the_composite_names_run_their_parts_in_order_and_stop_at_a_failure(
        runner, monkeypatch, tmp_path):
    ran = []

    def part(phase, path):
        ran.append(phase)
        if phase == "coverage-component-1":
            raise runner.Refused("U8 phase failed; evidence preserved")
        return {"state": "passed", "phase": phase}

    # A run root of its own: this test also runs in a realm where `fixtures` ran.
    monkeypatch.setattr(runner, "RUN", tmp_path)
    monkeypatch.setattr(runner, "run_phase", part)
    monkeypatch.setattr(runner, "run_coverage_report", lambda path: part("coverage-report", path))
    assert runner.run_test_phase("integration", Path("e"))["parts"] == [
        "integration-1", "integration-2", "integration-3", "integration-4"]
    assert ran == ["integration-1", "integration-2", "integration-3", "integration-4"]
    ran.clear()
    with pytest.raises(runner.Refused):
        runner.run_test_phase("coverage", Path("e"))
    assert ran == list(runner.COVERAGE_PARTS[:3])


def test_coverage_refuses_up_front_in_a_realm_where_the_fixtures_phase_ran(
        runner, monkeypatch, tmp_path):
    """The fixtures' accounts count against the realm's 20 synthetic accounts, so U8's
    coverage phase, and each of its parts, refuses before any part runs, with its fixed
    reason, once `fixtures` has run; every other phase still runs. A fresh realm (no
    `fixtures/` folder) runs coverage as before."""
    ran = []

    def part(phase, path):
        ran.append(phase)
        return {"state": "passed", "phase": phase}

    monkeypatch.setattr(runner, "RUN", tmp_path)
    monkeypatch.setattr(runner, "run_phase", part)
    monkeypatch.setattr(runner, "run_coverage_report", lambda path: part("coverage-report", path))
    # A fresh realm: the parts and the report run in order.
    assert runner.run_test_phase("coverage", Path("e"))["parts"] == [
        *runner.COVERAGE_PARTS, "coverage-report"]
    # The fixtures phase ran (its record, or only the accounts its child wrote).
    for record in ("phase.json", "browser.json"):
        folder = tmp_path / "fixtures"
        folder.mkdir(mode=0o700, exist_ok=True)
        (folder / record).write_text("{}")
        for phase in ("coverage", *runner.COVERAGE_PARTS):
            ran.clear()
            with pytest.raises(runner.Refused) as refused:
                runner.run_test_phase(phase, Path("e"))
            assert str(refused.value) == runner.COVERAGE_AFTER_FIXTURES
            assert str(refused.value).startswith("coverage-after-fixtures:")
            assert ran == []
        (folder / record).unlink()
    # Other phases are not refused by it (`operations` runs its three parts and
    # `component` its two).
    ran.clear()
    assert runner.run_test_phase("operations", Path("e"))["parts"] == [
        "operations-1", "operations-2", "operations-3"]
    assert runner.run_test_phase("component", Path("e"))["parts"] == [
        "component-1", "component-2"]
    assert runner.run_test_phase("coverage-report", Path("e"))["phase"] == "coverage-report"
    assert ran == ["operations-1", "operations-2", "operations-3", "component-1",
                   "component-2", "coverage-report"]


def part_evidence(run: Path, part: str, *, exit_code: int = 0, run_id: str = "r",
                  at: float | None = None) -> None:
    path = run / f"{part}-evidence-{time.time_ns()}.json"
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        json.dump({"exitCode": exit_code, "runId": run_id}, stream)
    if at is not None:
        os.utime(path, (at, at))


def test_the_report_accepts_only_every_part_passed_in_this_realm(runner, tmp_path):
    now = time.time()
    for offset, part in enumerate(runner.COVERAGE_PARTS):
        part_evidence(tmp_path, part, at=now + offset)
    state = runner.coverage_parts_state(tmp_path, "r")
    assert not (state["missingParts"] or state["staleParts"] or state["failedParts"])


# --- the release's performance phase (your decision of 2026-10-24, Step 43) --------------------


@pytest.fixture
def native(phases):
    import u8_native

    return u8_native


def release_tree(root: Path, commit: str = "c" * 40) -> Path:
    (root / "frontend").mkdir(parents=True)
    (root / "frontend" / "pnpm-lock.yaml").write_text("lock: 1\n")
    (root / ".docsuri-release.json").write_text(json.dumps({"tag": "v2.1.0",
                                                            "commit": commit}))
    return root


def test_the_native_database_starts_and_stops_from_the_pinned_runtime(native, tmp_path):
    runtime = Path("/Library/DocSuri/runtimes/postgresql-16.14")
    commands = native.native_commands(tmp_path, port=15509,
                                      password_file=tmp_path / "pwfile")
    assert commands["initdb"][:3] == [str(runtime / "bin" / "initdb"), "-D",
                                      str(tmp_path / "pgdata")]
    assert f"--pwfile={tmp_path / 'pwfile'}" in commands["initdb"]
    assert "--auth-host=scram-sha-256" in commands["initdb"]
    start = commands["start"]
    assert start[0] == str(runtime / "bin" / "pg_ctl") and start[-1] == "start"
    options = start[start.index("-o") + 1]
    assert "-p 15509" in options and f"-k {tmp_path / 'pgsocket'}" in options
    assert "-c max_connections=50" in options and "-c shared_buffers=512MB" in options
    assert "-c listen_addresses=127.0.0.1" in options
    # security-design § 7.2's log settings (Step 79(d)).
    for setting in LOG_SETTINGS:
        assert f"-c {setting}" in options
    assert commands["stop"][-1] == "stop" and "fast" in commands["stop"]
    assert commands["status"][-1] == "status"
    assert "initdb" not in native.native_commands(tmp_path, port=15509)
    assert native.runtime_present(tmp_path / "absent") is False


LOG_SETTINGS = (
    "log_min_messages=log", "log_error_verbosity=terse", "log_min_error_statement=panic",
    "log_statement=none", "log_min_duration_statement=-1", "log_parameter_max_length=0",
    "log_parameter_max_length_on_error=0",
)
EARLIER_SETTINGS = (
    "shared_buffers=512MB", "max_connections=50", "work_mem=16MB",
    "maintenance_work_mem=256MB", "password_encryption=scram-sha-256",
    "statement_timeout=3000", "lock_timeout=1000", "idle_in_transaction_session_timeout=5000",
    "max_wal_size=1GB", "wal_keep_size=0", "archive_mode=off", "max_replication_slots=0",
    "max_wal_senders=0",
)


def test_the_realm_database_runs_with_section_7_2s_log_settings(runner):
    """Step 79(d): the realm's PostgreSQL logs with security-design § 7.2's settings,
    after its thirteen earlier settings, which stay as they were."""
    command = runner.database_command(
        {"container": "c", "runId": "r", "volume": "v", "databaseImage": "image"}
    )
    after = command[command.index("image") + 1:]
    pairs = [after[index + 1] for index in range(0, len(after), 2) if after[index] == "-c"]
    assert len(pairs) * 2 == len(after)
    assert tuple(pairs) == EARLIER_SETTINGS + LOG_SETTINGS
    for setting in LOG_SETTINGS:
        assert pairs.count(setting) == 1


def test_the_interpreter_falls_back_to_the_releases_own_environment(native, tmp_path):
    assert native.python_for(tmp_path) == tmp_path / ".venv" / "bin" / "python"
    development = tmp_path / "backend" / ".venv" / "bin"
    development.mkdir(parents=True)
    (development / "python").write_text("")
    assert native.python_for(tmp_path) == development / "python"


def test_a_release_environment_runs_only_its_performance_phases(native, tmp_path):
    native.require_release_phase("component", tmp_path)  # a development tree runs any
    release_tree(tmp_path)
    for phase in native.RELEASE_PHASES:
        native.require_release_phase(phase, tmp_path)
    for phase in ("component", "integration-1", "coverage-report", "database"):
        with pytest.raises(native.NativeRefused, match="needs pytest"):
            native.require_release_phase(phase, tmp_path)
    (tmp_path / ".docsuri-release.json").write_text(json.dumps({"tag": "v2.1.0"}))
    with pytest.raises(native.NativeRefused, match="outside its form"):
        native.release_identity(tmp_path)


def test_the_native_database_is_refused_outside_the_release_phases(runner, monkeypatch):
    monkeypatch.setattr(sys, "argv", [
        "verify_docsuri_u8.py", "--phase", "component", "--profile", "synthetic-local",
        "--environment-file", str(runner.RUN / "environment.json"), "--database", "native"])
    with pytest.raises(runner.Refused, match="--database native runs only"):
        runner.main()
    monkeypatch.setattr(sys, "argv", [
        "verify_docsuri_u8.py", "--phase", "performance", "--profile", "synthetic-local",
        "--environment-file", str(runner.RUN / "environment.json"), "--playwright", "/x"])
    with pytest.raises(runner.Refused, match="only from a release environment"):
        runner.main()  # this tree is a development tree


def test_the_playwright_checkout_must_measure_the_release(native, tmp_path):
    root = release_tree(tmp_path / "release")
    checkout = release_tree(tmp_path / "checkout")
    (checkout / ".git").mkdir()

    def git(head: str = "c" * 40, porcelain: str = ""):
        return lambda arguments: (0, head + "\n" if "rev-parse" in arguments else porcelain)

    with pytest.raises(native.NativeRefused, match="playwright-checkout-has-no-playwright"):
        native.playwright_checkout(checkout, root, git=git())
    binary = checkout / "frontend" / "node_modules" / ".bin"
    binary.mkdir(parents=True)
    (binary / "playwright").write_text("")
    assert native.playwright_checkout(checkout, root, git=git()) == checkout / "frontend"
    with pytest.raises(native.NativeRefused, match="playwright-checkout-commit-differs"):
        native.playwright_checkout(checkout, root, git=git(head="d" * 40))
    with pytest.raises(native.NativeRefused, match="playwright-checkout-not-clean"):
        native.playwright_checkout(checkout, root, git=git(porcelain=" M x\n"))
    (checkout / "frontend" / "pnpm-lock.yaml").write_text("lock: 2\n")
    with pytest.raises(native.NativeRefused, match="playwright-lockfile-differs"):
        native.playwright_checkout(checkout, root, git=git())
    with pytest.raises(native.NativeRefused, match="only from a release environment"):
        native.playwright_checkout(checkout, tmp_path / "development", git=git())


def test_the_release_performance_phase_is_named_with_its_fixture_runs(runner):
    assert "release-performance" in runner.PHASES
    assert runner.RELEASE_FIXTURE_RUNS == 4


def test_the_report_names_a_missing_failed_stale_or_foreign_part(runner, tmp_path):
    now = time.time()
    first, second, third, fourth, *_ = runner.COVERAGE_PARTS
    part_evidence(tmp_path, second, at=now - 60)            # older than the first part
    part_evidence(tmp_path, first, at=now)
    part_evidence(tmp_path, third, exit_code=1, at=now + 1)
    part_evidence(tmp_path, fourth, run_id="other", at=now + 2)
    state = runner.coverage_parts_state(tmp_path, "r")
    assert state["missingParts"] == list(runner.COVERAGE_PARTS[4:])
    assert state["staleParts"] == [second, fourth]
    assert state["failedParts"] == [third]


# --- the stop after a browser phase (the PermissionError after `accessibility`) -----------


def exited_but_unreaped() -> subprocess.Popen:
    """A group leader that has exited and waits to be reaped: its group holds only a
    zombie, the state the realm's children can be in after `stop` reaps the leader."""
    process = child()
    os.kill(process.pid, 9)
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        states = subprocess.run(["ps", "-o", "stat=", "-p", str(process.pid)],
                                capture_output=True, text=True, check=False).stdout.split()
        if states and states[0].startswith("Z"):
            return process
        time.sleep(0.05)
    raise AssertionError("the leader never became a zombie")


def test_a_group_left_with_only_an_exited_member_is_stopped(runner):
    process = exited_but_unreaped()
    try:
        assert runner.group_states(process.pid)[0].startswith("Z")
        runner.signal_group(process.pid, 9)     # macOS answers EPERM here; Linux, success
        runner.stop(process)
        assert process.returncode == -9
        assert runner.group_states(process.pid) == []
    finally:
        process.stdout.close()


def test_eperm_with_a_live_member_left_is_raised(runner, monkeypatch):
    def refused(pgid, signum):
        raise PermissionError(1, "Operation not permitted")

    monkeypatch.setattr(runner.os, "killpg", refused)
    monkeypatch.setattr(runner, "group_states", lambda pgid: ["Z", "S"])
    with pytest.raises(PermissionError):
        runner.signal_group(4242, 15)
    monkeypatch.setattr(runner, "group_states", lambda pgid: ["Z", "Z+"])
    runner.signal_group(4242, 15)
    monkeypatch.setattr(runner, "group_states", lambda pgid: [])
    runner.signal_group(4242, 15)


def test_the_browser_phases_stop_their_realm_with_the_runners_own_stop(runner, phases):
    # `run_browser` stops the served realm through `runner.stop`, which is U8's, not U3's.
    assert runner.stop.__module__ == runner.__name__
    assert "runner.stop(companion)" in Path(phases.__file__).read_text()


def test_the_top_level_refusal_names_the_operation_and_the_path(runner):
    def keep_evidence():
        raise PermissionError(1, "Operation not permitted", "/tmp/docsuri-u8-run/x")

    try:
        keep_evidence()
    except PermissionError as error:
        value = runner.refusal(error)
    assert value == {
        "state": "refused", "category": "PermissionError",
        "reason": "owned prerequisite unavailable",
        "operation": {"function": "keep_evidence", "file": "test_u8_tool.py",
                      "line": value["operation"]["line"]},
        "errno": "EPERM", "path": "/tmp/docsuri-u8-run/x"}
    assert "Operation not permitted" not in json.dumps(value)


def test_a_refusal_keeps_its_own_reason_and_a_value_error_names_its_operation(runner):
    assert runner.refusal(runner.Refused("the corpus is incomplete")) == {
        "state": "refused", "category": "Refused", "reason": "the corpus is incomplete"}

    def parse():
        raise ValueError("secret-ish detail")

    try:
        parse()
    except ValueError as error:
        value = runner.refusal(error)
    assert value["operation"]["function"] == "parse"
    assert "path" not in value and "secret-ish" not in json.dumps(value)


# --- the platform store's digest (the person's decision of 2026-10-25, "After the move,
# same build") ---------------------------------------------------------------------------------

# Step 97(b) item 16 (L1-35): the four store tests use the realm's own platform store
# through the real `connect_admin`. The fresh-install branch cannot run there, since its
# `CREATE ROLE` statements would meet the realm's roles, which exist across the whole
# cluster; the tests check what `migrate` installed and run the other branches on it.

IDENTITY = "public.docsuri_u8_platform_identity"


def platform_store(runner):
    """The live realm's manifest and a connection maker for its platform store."""
    value = live_value()
    return value, lambda: runner.connect_admin(value, dbname=runner.PLATFORM_DATABASE)


def identity_row(connect) -> tuple:
    with connect() as conn:
        return tuple(conn.execute(f"SELECT run_id,inventory_hash FROM {IDENTITY}").fetchone())


def protocol_count(connect) -> int:
    with connect() as conn:
        return conn.execute("SELECT count(*) FROM platform_control.protocol").fetchone()[0]


def record_digest(connect, digest: str) -> None:
    with connect() as conn:
        conn.execute(f"UPDATE {IDENTITY} SET inventory_hash=%s WHERE singleton", (digest,))


def test_the_store_logins_and_the_reader_role_come_before_the_amendment(runner):
    """Your decision of 2026-10-26, "Bind each login to its actor": the reader role and the
    three store logins (the operator's and the scheduler's in the runtime role, the
    reader's in the reader role only) exist, and the amendment, which grants the reader
    role its read functions only when the role already exists (u8_store.sql), granted
    them: so the logins and the role came first."""
    from docsuri_ops.u8_platform.platform_profile import store_digest

    value, connect = platform_store(runner)
    assert identity_row(connect) == (value["runId"], store_digest(runner.ROOT))
    with connect() as conn:
        groups = dict(conn.execute(
            "SELECT member.rolname, array_agg(grp.rolname ORDER BY grp.rolname) "
            "FROM pg_auth_members m JOIN pg_roles member ON member.oid=m.member "
            "JOIN pg_roles grp ON grp.oid=m.roleid WHERE member.rolname = ANY(%s) "
            "GROUP BY member.rolname",
            (["docsuri_u8_platform_reader", "docsuri_u8_platform_operator",
              "docsuri_u8_platform_scheduler"],)).fetchall())
        usage = conn.execute("SELECT has_schema_privilege('platform_control_u8_reader', "
                             "'platform_control', 'USAGE')").fetchone()[0]
        granted = sorted(row[0] for row in conn.execute(
            "SELECT p.proname FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
            "CROSS JOIN LATERAL aclexplode(p.proacl) acl "
            "WHERE n.nspname='platform_control' AND acl.privilege_type='EXECUTE' "
            "AND acl.grantee='platform_control_u8_reader'::regrole").fetchall())
    assert groups == {"docsuri_u8_platform_reader": ["platform_control_u8_reader"],
                      "docsuri_u8_platform_operator": ["platform_control_runtime"],
                      "docsuri_u8_platform_scheduler": ["platform_control_runtime"]}
    assert usage is True
    assert set(granted) >= {"u8_read_receipt", "u8_read_receipt_named", "u8_latest_evidence",
                            "u8_list_unresolved", "u8_status_counts"}
    text = (runner.ROOT / "ops/src/docsuri_ops/u8_platform/u8_store.sql").read_text()
    assert "TO platform_control_u8_reader" in text


def test_a_fresh_store_records_the_store_digest_so_the_next_migrate_verifies_it(runner):
    from docsuri_ops.u8_platform.platform_profile import store_digest

    value, connect = platform_store(runner)
    before, rows = identity_row(connect), protocol_count(connect)
    assert runner.install_platform_store(value) == {"state": "verified",
                                                     "storeDigest": store_digest(runner.ROOT)}
    assert identity_row(connect) == before and protocol_count(connect) == rows


def test_a_store_recorded_before_a_change_to_the_amendment_alone_is_migrated(
        runner, monkeypatch, tmp_path):
    from docsuri_ops.u8_platform.platform_profile import STORE_AMENDMENT, STORE_FILES, store_digest

    value, connect = platform_store(runner)
    before, rows = identity_row(connect), protocol_count(connect)
    assert before[1] == store_digest(runner.ROOT)
    inventory = "ops/src/docsuri_ops/platform_control/inventory.json"
    for file in {*STORE_FILES, inventory}:
        target = tmp_path / file
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((runner.ROOT / file).read_bytes()
                           + (b"\n-- a later amendment\n" if file == STORE_AMENDMENT else b""))
    try:
        monkeypatch.setattr(runner, "ROOT", tmp_path)
        after = store_digest(tmp_path)
        assert after != before[1]
        # The recorded digest is the one from before the change; every protocol row is
        # present, so none is added.
        assert runner.install_platform_store(value) == {"state": "migrated",
                                                         "storeDigest": after, "added": []}
        assert identity_row(connect) == (value["runId"], after)
        assert protocol_count(connect) == rows
    finally:
        record_digest(connect, before[1])
    assert identity_row(connect) == before


def test_a_store_recording_the_inventorys_digest_alone_is_migrated(runner):
    """A store recorded before the amendment joined the digest holds the inventory's own
    digest: the next `migrate` applies the amendment again and records the store's."""
    import hashlib

    from docsuri_ops.u8_platform.platform_profile import STORE_INVENTORY, store_digest

    value, connect = platform_store(runner)
    before = identity_row(connect)
    inventory = hashlib.sha256((runner.ROOT / STORE_INVENTORY).read_bytes()).hexdigest()
    try:
        record_digest(connect, inventory)
        result = runner.install_platform_store(value)
        assert result["state"] == "migrated"
        assert result["storeDigest"] == store_digest(runner.ROOT) and result["added"] == []
        assert identity_row(connect) == (value["runId"], store_digest(runner.ROOT))
    finally:
        record_digest(connect, before[1])
    assert identity_row(connect) == before


# --- the Docker the tools reach (L1-76, L1-77) ----------------------------------------------

PLANTED = ("DATABASE_URL", "OPENAI_API_KEY")


def plant(monkeypatch, tmp_path, *names: str) -> tuple[str, dict]:
    """DOCKER_HOST set to a socket path of the test's own, and each planted name given a
    value generated for this run."""
    import secrets

    socket = f"unix://{tmp_path}/docker-{secrets.token_hex(4)}.sock"
    monkeypatch.setenv("DOCKER_HOST", socket)
    values = {name: f"planted-{secrets.token_hex(8)}" for name in names}
    for name, value in values.items():
        monkeypatch.setenv(name, value)
    return socket, values


def held(*names: str) -> dict:
    return {name: os.environ[name] for name in names if name in os.environ}


def env_keys(output: str) -> list[str]:
    return [line.split("=", 1)[0] for line in output.splitlines() if "=" in line]


def test_the_tools_pass_docker_host_only_when_it_is_set(runner, monkeypatch, tmp_path):
    import verify_docsuri_u1

    socket, planted = plant(monkeypatch, tmp_path, *PLANTED, "DOCKER_CONFIG")
    monkeypatch.setenv("HOME", str(tmp_path))
    u1_built = ("PATH", "LANG", "LC_ALL", "TMPDIR", "SYSTEMROOT")
    set_by_runner = {"PYTHONPATH": str(runner.ROOT),
                     "DOCSURI_U8_ENVIRONMENT_FILE": str(runner.RUN / "environment.json"),
                     "CI": "true", "COREPACK_ENABLE_DOWNLOAD_PROMPT": "0",
                     "COREPACK_ENABLE_NETWORK": "0"}
    child_built = ("PATH", "HOME", "TMPDIR", "LANG")

    assert verify_docsuri_u1.clean_environment() == {**held(*u1_built), "DOCKER_HOST": socket}
    assert runner.child_environment() == {**held(*child_built), **set_by_runner,
                                          "DOCKER_HOST": socket}
    assert runner.child_environment({"EXTRA": "1"}) == {
        **held(*child_built), **set_by_runner, "DOCKER_HOST": socket, "EXTRA": "1"}
    shown = verify_docsuri_u1.command(["/usr/bin/env"])
    assert shown.returncode == 0
    assert [line for line in shown.stdout.splitlines() if line.startswith("DOCKER_HOST=")] == [
        f"DOCKER_HOST={socket}"]

    monkeypatch.delenv("DOCKER_HOST", raising=False)
    assert verify_docsuri_u1.clean_environment() == held(*u1_built)
    assert runner.child_environment() == {**held(*child_built), **set_by_runner}
    assert runner.child_environment({"EXTRA": "1"}) == {
        **held(*child_built), **set_by_runner, "EXTRA": "1"}
    shown = verify_docsuri_u1.command(["/usr/bin/env"])
    assert shown.returncode == 0 and "DOCKER_HOST" not in env_keys(shown.stdout)
    for environment in (verify_docsuri_u1.clean_environment(), runner.child_environment()):
        assert not set(planted) & set(environment)
    assert not {"HOME", "DOCKER_CONFIG"} & set(verify_docsuri_u1.clean_environment())


def test_u2s_launcher_and_u7s_runner_pass_docker_host_only_when_it_is_set(
        runner, monkeypatch, tmp_path):
    import prepare_docsuri_u2_browser
    import verify_docsuri_u7

    socket, planted = plant(monkeypatch, tmp_path, *PLANTED, "DOCKER_CONFIG")
    u7_built = ("PATH", "LANG", "LC_ALL", "TMPDIR", "SYSTEMROOT")

    # U7: its own copy of the helper, and a real child that runs no Docker.
    assert verify_docsuri_u7.clean_environment() == {**held(*u7_built), "DOCKER_HOST": socket}
    shown = verify_docsuri_u7.command(["/usr/bin/env"])
    assert shown.returncode == 0
    assert [line for line in shown.stdout.splitlines() if line.startswith("DOCKER_HOST=")] == [
        f"DOCKER_HOST={socket}"]

    # U2: every child its tool supervises.
    u2_set = ["PYTHONPATH", "DOCSURI_U2_ENVIRONMENT_FILE", "CI",
              "COREPACK_ENABLE_DOWNLOAD_PROMPT", "COREPACK_ENABLE_NETWORK"]
    u2_built = sorted([*held("PATH", "HOME", "TMPDIR", "LANG"), *u2_set])
    set_log = tmp_path / "browser-env-set.log"
    assert prepare_docsuri_u2_browser.bounded_process(
        ["/usr/bin/env"], set_log, seconds=5)["exitCode"] == 0
    set_text = set_log.read_text()
    assert sorted(env_keys(set_text)) == sorted([*u2_built, "DOCKER_HOST"])
    assert f"DOCKER_HOST={socket}" in set_text.splitlines()

    monkeypatch.delenv("DOCKER_HOST", raising=False)
    assert verify_docsuri_u7.clean_environment() == held(*u7_built)
    shown = verify_docsuri_u7.command(["/usr/bin/env"])
    assert shown.returncode == 0 and "DOCKER_HOST" not in env_keys(shown.stdout)
    unset_log = tmp_path / "browser-env-unset.log"
    assert prepare_docsuri_u2_browser.bounded_process(
        ["/usr/bin/env"], unset_log, seconds=5)["exitCode"] == 0
    unset_text = unset_log.read_text()
    assert sorted(env_keys(unset_text)) == u2_built

    assert not {"HOME", *planted} & set(verify_docsuri_u7.clean_environment())
    for text in (set_text, unset_text):
        assert not [value for value in planted.values() if value in text]


def test_u6s_runner_passes_docker_host_only_when_it_is_set(runner, monkeypatch, tmp_path):
    """U6's coverage child reaches the realm's Docker only through DOCKER_HOST: the
    person's answer of 2026-11-10 keeps it beside U6's built names."""
    import verify_docsuri_u6

    socket, planted = plant(monkeypatch, tmp_path, *PLANTED, "DOCKER_CONFIG")
    monkeypatch.setenv("HOME", str(tmp_path))
    u6_built = ("PATH", "HOME", "TMPDIR", "LANG")
    set_by_runner = {"PYTHONPATH": str(verify_docsuri_u6.ROOT),
                     "DOCSURI_U6_ENVIRONMENT_FILE": str(verify_docsuri_u6.RUN / "environment.json"),
                     "PLAYWRIGHT_JUNIT_OUTPUT_FILE": str(verify_docsuri_u6.RUN / "browser.xml"),
                     "CI": "true", "COREPACK_ENABLE_DOWNLOAD_PROMPT": "0",
                     "COREPACK_ENABLE_NETWORK": "0"}

    assert verify_docsuri_u6.child_environment() == {**held(*u6_built), **set_by_runner,
                                                     "DOCKER_HOST": socket}

    monkeypatch.delenv("DOCKER_HOST", raising=False)
    unset = verify_docsuri_u6.child_environment()
    assert unset == {**held(*u6_built), **set_by_runner}
    assert "DOCKER_HOST" not in unset
    assert not set(planted) & set(unset)


# --- Step 97(b): the tool's failure rules, paths, key files and realm lifetime -----------------
#
# Build batch 9a's fix passes wrote, ahead of the VerificationRun section, the coverage
# report's chained-digest cases, the restart clock's cases and the build gate's planted
# markup and first-load cases. Each stays where it is and runs once; item 3 of (b), item 4
# of (c), and (d) and (e), add only the cases those do not hold.

LIVE_RUN = Path("/tmp/docsuri-u8-run")
PASSING_REPORT = '<testsuite><testcase classname="c" name="n"/></testsuite>'


def private_text(path: Path, text: str, mode: int = 0o600) -> Path:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        stream.write(text)
    os.chmod(path, mode)
    return path


def live_value() -> dict:
    manifest = LIVE_RUN / "environment.json"
    if not manifest.exists():
        pytest.fail("the realm's environment is set up before the operations phase")
    return json.loads(manifest.read_text())


def git_repository(root: Path):
    """A temporary git repository set up without hooks, signing or templates, as
    test_built_file_pins.py does; the answer runs one git command in it."""
    import shutil

    git = shutil.which("git")
    assert git is not None
    root.mkdir(parents=True, exist_ok=True)
    isolated = ["-c", "core.hooksPath=/dev/null", "-c", "commit.gpgsign=false",
                "-c", "tag.gpgsign=false", "-c", "init.templateDir=",
                "-c", "user.email=u8@test.invalid", "-c", "user.name=u8"]

    def run(*args: str) -> str:
        return subprocess.run([git, *isolated, *args], cwd=root, check=True,
                              capture_output=True, text=True, timeout=60).stdout.strip()

    run("init", "-q")
    return run


def in_repository(runner, monkeypatch, repository: Path) -> None:
    """`runner.ROOT` and `runner.command`'s working directory at a temporary repository."""
    real = runner.command
    monkeypatch.setattr(runner, "ROOT", repository)
    monkeypatch.setattr(runner, "command",
                        lambda args, **options: real(args, **{**options, "cwd": repository}))


@pytest.mark.parametrize("kind", ["malformed", "loose", "fifo", "oversized"])
def test_an_invalid_or_linked_report_fails_the_phase(runner, monkeypatch, tmp_path, kind):
    report = tmp_path / "report.xml"
    if kind == "malformed":
        private_text(report, "<testsuite><testcase")
    elif kind == "loose":
        private_text(report, PASSING_REPORT, 0o644)
    elif kind == "fifo":
        os.mkfifo(report, 0o600)
    else:
        private_text(report, PASSING_REPORT)
        with report.open("r+b") as stream:
            stream.seek(16 * 1024**2)
            stream.write(b" ")
        assert report.stat().st_size == 16 * 1024**2 + 1
    evidence = {"exitCode": 0}
    runner.junit_counts(report, evidence)
    assert evidence["invalidTestReport"] is True and evidence["exitCode"] == 1
    # A link to a passing private report is a missing report.
    target = private_text(tmp_path / "target.xml", PASSING_REPORT)
    linked = tmp_path / "linked.xml"
    linked.symlink_to(target)
    evidence = {"exitCode": 0}
    runner.junit_counts(linked, evidence)
    assert evidence["missingTestReport"] is True and evidence["exitCode"] == 1
    # `run_phase` refuses a linked report before any child.
    calls, written = phase_fakes(runner, monkeypatch, tmp_path / "run")
    (tmp_path / "run").mkdir(mode=0o700)
    (tmp_path / "run" / "database.xml").symlink_to(target)
    with pytest.raises(runner.Refused, match="test report cannot be a symlink"):
        runner.run_phase("database", Path("e"))
    assert calls == [] and written == {}


BAD_REPORTS = {
    "zero tests": ("<testsuite></testsuite>", "tests", 0),
    "a skip": ('<testsuite><testcase name="n"><skipped/></testcase></testsuite>', "skipped", 1),
    "an error": ('<testsuite><testcase name="n"><error/></testcase></testsuite>', "errors", 1),
    "a failure": ('<testsuite><testcase name="n"><failure/></testcase></testsuite>',
                  "failures", 1),
    "malformed": ("<testsuite><testcase", "invalidTestReport", True),
    "no report": (None, "missingTestReport", True),
}


@pytest.mark.parametrize("case", sorted(BAD_REPORTS))
def test_a_child_that_exits_zero_still_fails_on_its_report(runner, phases, monkeypatch,
                                                            tmp_path, case):
    body, key, expected = BAD_REPORTS[case]
    _calls, written = phase_fakes(runner, monkeypatch, tmp_path)

    def child(args, log, **options):
        report = Path(next(item for item in args if item.startswith("--junitxml="))
                      .removeprefix("--junitxml="))
        if body is not None:
            private_text(report, body)
        return {"exitCode": 0}

    monkeypatch.setattr(runner, "bounded_process", child)
    with pytest.raises(runner.Refused, match=r"^U8 phase failed; evidence preserved$"):
        runner.run_test_phase("database", Path("e"))
    (evidence,) = written.values()
    assert evidence["exitCode"] == 1 and evidence[key] == expected
    written.clear()
    with pytest.raises(runner.Refused,
                       match=r"^U8 phase restore-paths failed; evidence preserved$"):
        phases.run_restore_paths(runner, Path("e"))
    (evidence,) = written.values()
    assert evidence["exitCode"] == 1 and evidence[key] == expected


def test_a_source_change_during_the_run_fails_the_phase(runner, monkeypatch, tmp_path):
    calls, written = phase_fakes(runner, monkeypatch, tmp_path)
    monkeypatch.setattr(runner, "source_identity",
                        lambda: {"sha256": "after" if calls else "before"})
    with pytest.raises(runner.Refused):
        runner.run_phase("database", Path("e"))
    (evidence,) = written.values()
    assert evidence["sourceChangedDuringRun"] is True and evidence["exitCode"] == 1
    # The report over every part's evidence, one part on another source: no report child.
    run = tmp_path / "report"
    run.mkdir(mode=0o700)
    data, digest_ = coverage_data(run, runner, "lines")
    every_part_on_a(run, runner, time.time(), digest_)
    coverage_run(run, runner.COVERAGE_PARTS[4], time.time() + 1, sha=SOURCE_B,
                 before=digest_, data=digest_)
    report = {}
    monkeypatch.setattr(runner, "RUN", run)
    monkeypatch.setattr(runner, "source_identity", lambda: {"sha256": SOURCE_A})
    monkeypatch.setattr(runner, "private_json", lambda path, value: report.update(value))

    def no_child(*args, **kwargs):
        raise AssertionError("no report child runs")

    monkeypatch.setattr(runner, "bounded_process", no_child)
    with pytest.raises(runner.Refused, match="coverage report failed"):
        runner.run_coverage_report(run / "environment.json")
    assert report["sourceChangedDuringRun"] is True and report["exitCode"] == 1
    assert report["otherSourceParts"] == [runner.COVERAGE_PARTS[4]]


def test_source_identity_detects_a_changed_listed_file(runner, monkeypatch, tmp_path):
    repository = tmp_path / "repository"
    git = git_repository(repository)
    (repository / "backend").mkdir()
    (repository / "backend" / "module.py").write_text("one = 1\n")
    (repository / ".gitignore").write_text("backend/ignored.py\n")
    git("add", "-A")
    git("commit", "-q", "--no-verify", "-m", "planted")
    in_repository(runner, monkeypatch, repository)
    first = runner.source_identity()
    (repository / "backend" / "module.py").write_text("one = 2\n")
    tracked = runner.source_identity()
    assert tracked["sha256"] != first["sha256"]
    (repository / "backend" / "new.py").write_text("new = 1\n")
    untracked = runner.source_identity()
    assert untracked["sha256"] != tracked["sha256"]
    (repository / "backend" / "ignored.py").write_text("ignored = 1\n")
    assert runner.source_identity()["sha256"] == untracked["sha256"]
    (repository / "backend" / "ignored.py").write_text("ignored = 2\n")
    assert runner.source_identity()["sha256"] == untracked["sha256"]


def verification_ready(runner, phases, monkeypatch, tmp_path, identities) -> tuple:
    """`run_verification` with its phases faked as the corpus test fakes them, every phase
    passing with its report and evidence, and the accessibility phases of Step 101(d) in
    the run; the written VerificationRun."""
    complete = every_report(tmp_path, phases)
    order = (*phases.AFTER_CORPUS, *(p for p in phases.A11Y_PHASES
                                     if p not in phases.AFTER_CORPUS))
    monkeypatch.setattr(phases, "AFTER_CORPUS", order)
    for name in {*phases.VERIFICATION_ORDER, *order}:
        monkeypatch.setitem(phases.PHASE_RUNNERS, name,
                            lambda r, p, name=name: complete[name])
    monkeypatch.setattr(phases, "complete_corpus", lambda r, p: {"state": "passed",
                                                                 "papers": 600})
    written = {}
    monkeypatch.setattr("u8_fixtures.write_private",
                        lambda path, value: written.update(value=value))
    fake = FakeRunner(tmp_path, runner)
    fake.EVIDENCE_PATTERN = runner.EVIDENCE_PATTERN
    fake.require = lambda args: SimpleNamespace(stdout="abc\n" if "HEAD" in args else "")
    answers = iter(identities)
    fake.source_identity = lambda: {"sha256": next(answers)}
    fake.v1_serving = lambda: True
    fake.private_bytes, fake.MAX_LOG = runner.private_bytes, runner.MAX_LOG
    (tmp_path / "fixtures").mkdir(mode=0o700, exist_ok=True)
    (tmp_path / "fixtures" / "phase.json").write_text("{}")
    return fake, written


def test_a_source_change_fails_the_verification_run(runner, phases, monkeypatch, tmp_path):
    same = tmp_path / "same"
    same.mkdir(mode=0o700)
    fake, written = verification_ready(runner, phases, monkeypatch, same, ("a", "a"))
    assert phases.run_verification(fake, same / "environment.json")["state"] == "passed"
    assert written["value"]["passed"] is True
    assert written["value"]["sourceChangedDuringRun"] is False
    changed = tmp_path / "changed"
    changed.mkdir(mode=0o700)
    fake, written = verification_ready(runner, phases, monkeypatch, changed, ("a", "b"))
    with pytest.raises(runner.Refused, match="verification-run is failed"):
        phases.run_verification(fake, changed / "environment.json")
    assert written["value"]["sourceChangedDuringRun"] is True
    assert written["value"]["passed"] is False


def test_a_test_path_must_list_a_tracked_or_unignored_file(runner, tmp_path):
    repository = tmp_path / "repository"
    git = git_repository(repository)
    (repository / ".gitignore").write_text("ignored.py\nonly-ignored/\n")
    (repository / "tracked.py").write_text("")
    git("add", "-A")
    git("commit", "-q", "--no-verify", "-m", "planted")
    (repository / "untracked.py").write_text("")
    (repository / "ignored.py").write_text("")
    (repository / "only-ignored").mkdir()
    (repository / "only-ignored" / "x.py").write_text("")
    runner.require_test_paths(("tracked.py", "untracked.py"), root=repository)
    for name in ("ignored.py", "only-ignored", "missing.py"):
        with pytest.raises(runner.Refused,
                           match="phase test path lists no tracked or untracked-unignored file"):
            runner.require_test_paths((name,), root=repository)
    elsewhere = tmp_path / "not-a-repository"
    elsewhere.mkdir()
    (elsewhere / "x.py").write_text("")
    with pytest.raises(runner.Refused):
        runner.require_test_paths(("x.py",), root=elsewhere)


def guarded_runner(runner, phases, monkeypatch, tmp_path, missing: str, *,
                   root: Path | None = None) -> list:
    """The runner with its realm checks faked, the real `require_test_paths`, and
    `listed_files` answering nothing for `missing` (or for any path of the checkout
    `root`). No child may start; the evidence written is answered."""
    written = []

    def listed(*paths, root=None):
        if (root is not None and root == expected) or (paths and paths[0] == missing):
            return []
        return list(paths)

    expected = root

    def no_child(*args, **kwargs):
        raise AssertionError("no child starts before the paths are checked")

    run = tmp_path / "run"
    run.mkdir(mode=0o700, exist_ok=True)
    monkeypatch.setattr(runner, "RUN", run)
    monkeypatch.setattr(runner, "listed_files", listed)
    monkeypatch.setattr(runner, "prepare_phase", lambda path: (
        {"runId": "r", "locks": {}, "policy": "p"}, {}))
    monkeypatch.setattr(runner, "preserve_prior_report", lambda phase: [])
    monkeypatch.setattr(runner, "source_identity", lambda *extra: {"sha256": "s"})
    monkeypatch.setattr(runner, "release_identity", lambda root: None)
    monkeypatch.setattr(runner, "v1_serving", lambda: True)
    monkeypatch.setattr(runner, "bounded_process", no_child)
    monkeypatch.setattr(runner, "require", no_child)
    monkeypatch.setattr(runner, "private_json", lambda path, value: written.append(path))
    monkeypatch.setattr(phases, "repair_tree", no_child)
    return written


def test_every_phase_checks_its_paths_before_any_test_child_starts(
        runner, phases, monkeypatch, tmp_path):
    reason = "phase test path lists no tracked or untracked-unignored file"
    e2e, root = phases.E2E, phases.TEST_ROOT
    cases = [
        ("run_phase", f"{root}/database", lambda: runner.run_phase("database", Path("e"))),
        ("run_browser", f"{e2e}/journeys.spec.ts",
         lambda: phases.run_browser(runner, "browser-journeys", Path("e"))),
        ("run_restore_paths", phases.RESTORE_TESTS[0],
         lambda: phases.run_restore_paths(runner, Path("e"))),
        ("run_security", phases.SECURITY_TESTS[0],
         lambda: phases.run_security(runner, Path("e"))),
        ("run_frontend", "frontend/test/u8-complete",
         lambda: phases.run_frontend(runner, Path("e"))),
        ("run_arrangement", f"{root}/arrangement",
         lambda: phases.run_arrangement(runner, Path("e"))),
        ("u2_regression", runner.U2_TEST_ROOT, lambda: runner.u2_regression(Path("e"))),
        ("run_repair_exercise", phases.REGRESSION,
         lambda: phases.run_repair_exercise(runner, Path("e"))),
        ("run_performance", f"{e2e}/navigation.spec.ts",
         lambda: phases.run_performance(runner, Path("e"))),
    ]
    for name, missing, call in cases:
        written = guarded_runner(runner, phases, monkeypatch, tmp_path, missing)
        monkeypatch.setattr(phases.sys, "platform", "darwin")
        monkeypatch.setattr(runner, "require_u2_environment_absent", lambda: None)
        monkeypatch.setattr(runner, "u2_regression_image", lambda: "sha256:image")
        monkeypatch.setattr(runner, "docker_available_memory", lambda image: 8 * GIB)
        corpus(runner.RUN, papers=600, target=600, complete=True, remaining=0,
               presentAtStart=600, importedThisRun=0)
        with pytest.raises(runner.Refused, match=reason):
            call()
        assert written == [], name
    # Compatibility, with a tag answered and a stand-in worktree whose listing lacks the
    # spec (L1-49).
    monkeypatch.setattr(phases, "previous_tag", lambda: "v2.0.0")
    monkeypatch.setenv("HOME", str(tmp_path))
    tree = tmp_path / ".docsuri-u8" / "compatibility-v2.0.0"
    tree.mkdir(parents=True)
    written = guarded_runner(runner, phases, monkeypatch, tmp_path, "", root=tree)
    with pytest.raises(runner.Refused, match=reason):
        phases.run_compatibility(runner, Path("e"))
    assert written == []


def test_every_path_a_phase_names_lists_a_file_now(runner, phases):
    paths = [f"{runner.TEST_ROOT}/{layer}" for layer in (
        "database", "repository", "component", "integration", "operations", "arrangement")]
    for halves in runner.LANE_HALVES.values():
        for part in halves:
            paths.extend(runner.lane_paths(part))
    paths.extend(f"{phases.E2E}/{spec}" for specs in phases.BROWSER_SPECS.values()
                 for spec in specs)
    paths.extend((*phases.SECURITY_TESTS, *phases.RESTORE_TESTS, phases.REGRESSION,
                  *(check.split("::")[0] for check in phases.REPAIR_CHECKS),
                  "frontend/test/u8-complete", f"frontend/{phases.VITEST_CONFIG}",
                  runner.U2_TEST_ROOT, runner.U2_PYTEST_INI))
    for path in paths:
        assert runner.listed_files(path), path


def archive_root(tmp_path: Path) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    run = tmp_path / "docsuri-u8-run"
    run.mkdir(mode=0o700)
    for name in ("export-keys", "control-keys", "verifier-key", "cursor-key"):
        (run / name).mkdir(mode=0o700)
        private_text(run / name / "key", "k")
    return run


def key_files(run: Path) -> list[str]:
    return sorted(str(path.relative_to(run)) for name in (
        "export-keys", "control-keys", "verifier-key", "cursor-key")
        for path in (run / name).iterdir())


def test_archive_owned_deletes_the_key_files_only_after_every_check_passed(
        runner, monkeypatch, tmp_path):
    import secrets as secrets_module

    real_keys = sorted(map(str, runner.key_entries(LIVE_RUN)))
    run_id = "docsuri-u8-0123456789abcdef"
    value = {"runId": run_id, "expiresAt": 1.0, "volume": run_id + "-pgdata"}
    stopped = []
    resources = {"calls": 0, "fail": None}

    def require_resources(value_):
        resources["calls"] += 1
        if resources["calls"] == resources["fail"]:
            raise runner.Refused("resources")

    def failing(reason):
        def fail(*args, **kwargs):
            raise runner.Refused(reason)
        return fail

    def lsof_free(args, **options):
        return subprocess.CompletedProcess(args, 1, "", "")

    def setup_case(index: int, **overrides) -> Path:
        run = archive_root(tmp_path / f"case-{index}")
        monkeypatch.setattr(runner, "RUN", run)
        monkeypatch.setattr(runner, "archive_identity", lambda path: value)
        monkeypatch.setattr(runner, "require_resources", require_resources)
        monkeypatch.setattr(runner, "run_v1", lambda word, path: None)
        monkeypatch.setattr(runner, "require_stopped", lambda port: None)
        monkeypatch.setattr(runner, "command", lsof_free)
        monkeypatch.setattr(runner, "remove_production_instances", lambda: [])
        monkeypatch.setattr(runner, "remove_peer_proofs", lambda: [])
        monkeypatch.setattr(runner, "check_preservation_database", lambda value_: None)
        monkeypatch.setattr(runner, "stop_database",
                            lambda value_: stopped.append(key_files(run)))
        monkeypatch.setattr(secrets_module, "token_hex", lambda size=None: "feedbeef")
        resources.update(calls=0, fail=None)
        for name, replacement in overrides.items():
            if name == "fail_resources":
                resources["fail"] = replacement
            else:
                monkeypatch.setattr(runner, name, replacement)
        return run

    failures = [
        ("the first resources check", {"fail_resources": 1}),
        ("v1-down", {"run_v1": failing("v1-down failed")}),
        ("a port", {"require_stopped": failing("stop the application before this phase")}),
        ("lsof busy", {"command": lambda args, **o: subprocess.CompletedProcess(
            args, 0, "python 1 user cwd DIR\n", "")}),
        ("a 0644 file", {}),
        ("the database check", {"check_preservation_database": failing("database")}),
        ("an existing destination", {}),
        ("the second resources check", {"fail_resources": 2}),
    ]
    for index, (name, overrides) in enumerate(failures):
        run = setup_case(index, **overrides)
        if name == "v1-down":
            private_text(run / "v1" / "supervisor.json", "{}")
        if name == "a 0644 file":
            private_text(run / "loose.json", "{}", 0o644)
        if name == "an existing destination":
            run.with_name(f"docsuri-u8-preserved-{run_id}-feedbeef").mkdir(mode=0o700)
        with pytest.raises(runner.Refused):
            runner.archive_owned(run / "environment.json")
        assert len(key_files(run)) == 4, name
        assert stopped == [], name
    run = setup_case(len(failures))
    result = runner.archive_owned(run / "environment.json")
    assert stopped == [[]] and result["keyFilesDeleted"] == 4
    assert result["state"] == "preserved"
    assert sorted(map(str, runner.key_entries(LIVE_RUN))) == real_keys


def test_a_left_production_instance_is_removed_by_the_runner(runner, monkeypatch, tmp_path):
    """Step 98(d): a container the production tool's module left (its run killed at the
    part's bound skips the module's `finally`) is stopped and removed by its label key,
    whatever run ID the label names: after a finished child of the part that holds the
    module, after one stopped at its bound, and by `archive-owned`. A container without
    the key, and a part without the module, leave it untouched."""
    remove = runner.remove_production_instances
    containers: dict = {}
    removed: list = []
    key = runner.PRODUCTION_INSTANCE_LABEL

    def leave() -> None:
        containers.clear()
        containers.update({"left": {key: "docsuri-u8-ffffffffffffffff"},
                           "unrelated": {runner.LABEL: "docsuri-u8-ffffffffffffffff"}})

    def command(args, **options):
        if args[:3] == ["docker", "ps", "-a"]:
            label = args[args.index("--filter") + 1].removeprefix("label=")
            listed = "".join(f"{name}\n" for name, labels in containers.items()
                             if label in labels)
            return subprocess.CompletedProcess(args, 0, listed, "")
        if args[:4] == ["docker", "rm", "-f", "-v"]:
            containers.pop(args[4])
            removed.append(args[4])
            return subprocess.CompletedProcess(args, 0, "", "")
        if args[0] == "lsof":
            return subprocess.CompletedProcess(args, 1, "", "")
        raise AssertionError(args)

    assert runner.production_instance_phases() == {"operations-2", "coverage-operations-2"}
    # A finished `operations-2` child; a part without the module first.
    _calls, written = phase_fakes(runner, monkeypatch, tmp_path / "run")
    (tmp_path / "run").mkdir(mode=0o700)
    monkeypatch.setattr(runner, "remove_production_instances", remove)
    monkeypatch.setattr(runner, "command", command)
    leave()
    runner.run_phase("operations-1", Path("e"))
    assert set(containers) == {"left", "unrelated"} and removed == []
    runner.run_phase("operations-2", Path("e"))
    assert set(containers) == {"unrelated"} and removed == ["left"]
    evidence = next(value for value in written.values() if value["phase"] == "operations-2")
    assert evidence["productionInstancesRemoved"] == ["left"]
    # One stopped at its bound: the supervisor ends the child, the phase fails, and the
    # container is still removed.
    leave()
    removed.clear()

    def stopped_at_bound(args, log, **options):
        error = runner.Refused("phase bound reached")
        error.supervision = {"exitCode": -9, "timedOut": True}
        raise error

    monkeypatch.setattr(runner, "bounded_process", stopped_at_bound)
    with pytest.raises(runner.Refused, match="U8 phase failed; evidence preserved"):
        runner.run_phase("coverage-operations-2", Path("e"))
    assert set(containers) == {"unrelated"} and removed == ["left"]
    # `archive-owned`.
    leave()
    removed.clear()
    run = archive_root(tmp_path / "archive")
    value = {"runId": "docsuri-u8-0123456789abcdef", "expiresAt": 1.0,
             "volume": "docsuri-u8-0123456789abcdef-pgdata"}
    monkeypatch.setattr(runner, "RUN", run)
    monkeypatch.setattr(runner, "archive_identity", lambda path: value)
    monkeypatch.setattr(runner, "require_resources", lambda value_: None)
    monkeypatch.setattr(runner, "require_stopped", lambda port: None)
    monkeypatch.setattr(runner, "check_preservation_database", lambda value_: None)
    monkeypatch.setattr(runner, "stop_database", lambda value_: None)
    result = runner.archive_owned(run / "environment.json")
    assert result["productionInstancesRemoved"] == ["left"]
    assert set(containers) == {"unrelated"} and removed == ["left"]


def test_a_left_peer_map_proof_is_removed_by_the_runner(runner, monkeypatch, tmp_path):
    """Package G3 (your answer of 2026-11-11, "Scratch container"): the peer map proof's
    scratch container, under its own label key, is removed as Step 98(d) removes the
    production instance: after a finished child of the part that holds the proof, after one
    stopped at its bound, and by `archive-owned`, whatever run ID the label names. A part
    without the proof leaves it, and neither removal touches a container under another key."""
    remove = runner.remove_peer_proofs
    containers: dict = {}
    removed: list = []
    key = runner.PEER_PROOF_LABEL

    def leave() -> None:
        containers.clear()
        containers.update({
            "proof": {key: "docsuri-u8-ffffffffffffffff"},
            "instance": {runner.PRODUCTION_INSTANCE_LABEL: "docsuri-u8-ffffffffffffffff"},
            "unrelated": {runner.LABEL: "docsuri-u8-ffffffffffffffff"}})

    def command(args, **options):
        if args[:3] == ["docker", "ps", "-a"]:
            label = args[args.index("--filter") + 1].removeprefix("label=")
            listed = "".join(f"{name}\n" for name, labels in containers.items()
                             if label in labels)
            return subprocess.CompletedProcess(args, 0, listed, "")
        if args[:4] == ["docker", "rm", "-f", "-v"]:
            containers.pop(args[4])
            removed.append(args[4])
            return subprocess.CompletedProcess(args, 0, "", "")
        if args[0] == "lsof":
            return subprocess.CompletedProcess(args, 1, "", "")
        raise AssertionError(args)

    assert key == "dev.docsuri.u8.peer-proof" and key != runner.PRODUCTION_INSTANCE_LABEL
    assert "test_peer_map_proof.py" in runner.OPERATIONS_HALVES["operations-3"]
    assert runner.peer_proof_phases() == {"operations-3", "coverage-operations-3"}
    # A finished `operations-3` child; a part without the proof first.
    _calls, written = phase_fakes(runner, monkeypatch, tmp_path / "run")
    child = runner.bounded_process  # the fakes' child, which writes a passing report
    (tmp_path / "run").mkdir(mode=0o700)
    monkeypatch.setattr(runner, "remove_peer_proofs", remove)
    monkeypatch.setattr(runner, "command", command)
    leave()
    runner.run_phase("operations-2", Path("e"))
    assert set(containers) == {"proof", "instance", "unrelated"} and removed == []
    runner.run_phase("operations-3", Path("e"))
    assert set(containers) == {"instance", "unrelated"} and removed == ["proof"]
    evidence = next(value for value in written.values() if value["phase"] == "operations-3")
    assert evidence["peerProofsRemoved"] == ["proof"]
    # One stopped at its bound: the phase fails, and the container is still removed.
    leave()
    removed.clear()

    def stopped_at_bound(args, log, **options):
        error = runner.Refused("phase bound reached")
        error.supervision = {"exitCode": -9, "timedOut": True}
        raise error

    monkeypatch.setattr(runner, "bounded_process", stopped_at_bound)
    with pytest.raises(runner.Refused, match="U8 phase failed; evidence preserved"):
        runner.run_phase("coverage-operations-3", Path("e"))
    assert set(containers) == {"instance", "unrelated"} and removed == ["proof"]
    # A removal Docker refuses fails a child that passed with its report.
    leave()
    removed.clear()
    monkeypatch.setattr(runner, "bounded_process", child)
    monkeypatch.setattr(runner, "command", lambda args, **options: (
        subprocess.CompletedProcess(args, 1, "", "refused")))
    with pytest.raises(runner.Refused, match="U8 phase failed; evidence preserved"):
        runner.run_phase("operations-3", Path("e"))
    refused = [value for value in written.values() if value.get("peerProofRemovalFailed")]
    assert len(refused) == 1 and refused[0]["tests"] == 1
    assert refused[0]["peerProofRemovalFailed"] == "the peer map proofs could not be listed"
    assert refused[0]["supervision"] == {"exitCode": 0}
    assert refused[0]["failureCategory"] == "Refused" and refused[0]["exitCode"] == 1
    # `archive-owned`, with both removals real: each takes only its own key's container.
    monkeypatch.setattr(runner, "command", command)
    monkeypatch.setattr(runner, "remove_production_instances",
                        lambda: runner._remove_labelled(runner.PRODUCTION_INSTANCE_LABEL,
                                                        "production instance"))
    leave()
    run = archive_root(tmp_path / "archive")
    value = {"runId": "docsuri-u8-0123456789abcdef", "expiresAt": 1.0,
             "volume": "docsuri-u8-0123456789abcdef-pgdata"}
    monkeypatch.setattr(runner, "RUN", run)
    monkeypatch.setattr(runner, "archive_identity", lambda path: value)
    monkeypatch.setattr(runner, "require_resources", lambda value_: None)
    monkeypatch.setattr(runner, "require_stopped", lambda port: None)
    monkeypatch.setattr(runner, "check_preservation_database", lambda value_: None)
    monkeypatch.setattr(runner, "stop_database", lambda value_: None)
    result = runner.archive_owned(run / "environment.json")
    assert result["peerProofsRemoved"] == ["proof"]
    assert result["productionInstancesRemoved"] == ["instance"]
    assert set(containers) == {"unrelated"} and removed == ["instance", "proof"]


def test_teardown_refuses_while_a_key_file_exists(runner, monkeypatch, tmp_path):
    run = archive_root(tmp_path)
    monkeypatch.setattr(runner, "RUN", run)
    monkeypatch.setattr(runner, "archive_identity", lambda path: {"runId": "r"})
    for name in ("export-keys", "control-keys", "verifier-key", "cursor-key"):
        with pytest.raises(runner.Refused, match=(
                "teardown refuses while a key folder holds a file; run archive-owned")):
            runner.teardown(run / "environment.json")
        (run / name / "key").unlink()
    assert runner.teardown(run / "environment.json")["state"] == "preserved"


def realm_copy(runner, monkeypatch, tmp_path, *, created: float | None = None,
               expires: float | None = None, regenerate: bool = True) -> Path:
    """A copy of the live run root's manifest under `tmp_path/docsuri-u8-run` (folder 0700,
    files 0600), `ownership.json` regenerated, with `RUN_PARENT` and `runner.RUN` at it."""
    import hashlib as hashes

    import backend.local_profile as local_profile

    value = live_value()
    original = (LIVE_RUN / "ownership.json").read_text()
    if created is not None:
        value["createdAt"] = created
    if expires is not None:
        value["expiresAt"] = expires
    tmp_path.mkdir(parents=True, exist_ok=True)
    root = tmp_path / "docsuri-u8-run"
    root.mkdir(mode=0o700)
    raw = json.dumps(value)
    private_text(root / "environment.json", raw)
    marker = json.dumps({"runId": value["runId"],
                         "manifestSha256": hashes.sha256(raw.encode()).hexdigest()})
    private_text(root / "ownership.json", marker if regenerate else original)
    monkeypatch.setattr(local_profile, "RUN_PARENT", tmp_path)
    monkeypatch.setattr(runner, "RUN", root.resolve())
    return root / "environment.json"


def test_the_realm_lives_24_hours_from_setup_and_is_never_extended(
        runner, monkeypatch, tmp_path):
    value = live_value()
    assert value["expiresAt"] == value["createdAt"] + 86400
    now = time.time()
    path = realm_copy(runner, monkeypatch, tmp_path / "accepted")
    runner.manifest(path)  # the copy as setup wrote it
    created = now - 7200
    path = realm_copy(runner, monkeypatch, tmp_path / "longer", created=created,
                      expires=created + 86400 + 3600)
    with pytest.raises(runner.Refused, match="U8 manifest retention differs from setup's 24 h"):
        runner.manifest(path)
    path = realm_copy(runner, monkeypatch, tmp_path / "past", created=now - 60,
                      expires=now + 86400 + 60)
    with pytest.raises(ValueError, match="wrong U8 finite retention"):
        runner.manifest(path)
    path = realm_copy(runner, monkeypatch, tmp_path / "edited", created=now - 60,
                      regenerate=False)
    with pytest.raises(ValueError, match="manifest identity mismatch"):
        runner.manifest(path)


def test_a_refused_prerequisite_exits_nonzero_not_skipped(runner, tmp_path):
    before = sorted(item.name for item in LIVE_RUN.glob("*-evidence-*.json"))
    completed = subprocess.run(
        [sys.executable, str(Path(runner.ROOT) / "scripts/verify_docsuri_u8.py"),
         "--phase", "database", "--profile", "synthetic-local", "--environment-file",
         str(tmp_path / "environment.json")],
        cwd=runner.ROOT, capture_output=True, text=True, timeout=120)
    assert completed.returncode == 1
    assert json.loads(completed.stdout.strip().splitlines()[-1]) == {
        "state": "refused", "category": "Refused",
        "reason": "only the explicit U8 owned manifest is accepted"}
    assert sorted(item.name for item in LIVE_RUN.glob("*-evidence-*.json")) == before


def test_a_foreign_consumed_or_other_units_environment_is_a_failed_prerequisite(
        runner, phases, monkeypatch, tmp_path):
    def no_child(*args, **kwargs):
        raise AssertionError("no child starts")

    monkeypatch.setattr(runner, "bounded_process", no_child)
    monkeypatch.setattr(sys, "argv", [
        "verify_docsuri_u8.py", "--phase", "database", "--profile", "synthetic-local",
        "--environment-file", "/tmp/docsuri-u6-run/environment.json"])
    with pytest.raises(runner.Refused, match="only the explicit U8 owned manifest is accepted"):
        runner.main()
    path = realm_copy(runner, monkeypatch, tmp_path / "credentials")
    private_text(path.parent / "owner-credentials.json",
                 json.dumps({"runId": "docsuri-u8-ffffffffffffffff"}))
    with pytest.raises(runner.Refused, match="^owner credential identity mismatch$"):
        runner.prepare_phase(path)
    path = realm_copy(runner, monkeypatch, tmp_path / "consumed")
    private_text(path.parent / "integration-1-evidence-1.json", "{}")
    with pytest.raises(runner.Refused, match="verification-run needs a fresh environment"):
        phases.run_verification(runner, path)
    path = realm_copy(runner, monkeypatch, tmp_path / "fixtures")
    (path.parent / "fixtures").mkdir(mode=0o700)
    for phase in ("coverage", "coverage-database"):
        with pytest.raises(runner.Refused, match="^coverage-after-fixtures"):
            runner.run_test_phase(phase, path)


def test_an_edited_applied_migration_is_a_failed_prerequisite(runner, monkeypatch, tmp_path):
    value = live_value()
    with runner.connect_admin(value) as conn:
        known = dict(conn.execute(
            "SELECT schema_hashes FROM public.docsuri_local_identity WHERE singleton"
        ).fetchone()[0])
    files, replaced = runner.chain()
    applied = [file for _, file in files if file in known and "/u8_" in file]
    assert applied
    edited = applied[0]
    with pytest.raises(runner.Refused, match="applied migration changed; append a new migration"):
        runner.validate_chain(files, replaced, {**known, edited: "0" * 64})
    # A tree whose applied U8 file differs by one byte refuses the next phase, from the
    # realm's real digests.
    tree = tmp_path / "tree"
    for name in (*runner.LOCKS, *(file for _, file in files)):
        target = tree / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((Path(runner.ROOT) / name).read_bytes())
    changed = tree / edited
    changed.write_bytes(changed.read_bytes() + b"\n")
    monkeypatch.setattr(runner, "ROOT", tree)
    with pytest.raises(runner.Refused, match="applied migration changed; append a new migration"):
        runner.prepare_phase(LIVE_RUN / "environment.json")


def test_setup_on_the_realm_preserves_its_manifest(runner):
    manifest, ownership = LIVE_RUN / "environment.json", LIVE_RUN / "ownership.json"
    before = (manifest.read_bytes(), ownership.read_bytes())
    value = live_value()
    assert runner.setup(manifest) == {"state": "preserved", "runId": value["runId"]}
    assert (manifest.read_bytes(), ownership.read_bytes()) == before
    after = json.loads(manifest.read_text())
    assert (after["createdAt"], after["expiresAt"]) == (value["createdAt"],
                                                        value["expiresAt"])


def test_the_unverified_fixture_accounts_are_planned_unverified_with_no_usage(phases):
    import u8_fixtures

    assert len(u8_fixtures.V2_ACCOUNTS) == 8 <= u8_fixtures.MAX_ACCOUNTS
    record = {"accounts": {key: {} for key in u8_fixtures.V2_ACCOUNTS}}
    plan = u8_fixtures.account_plan(record)
    assert set(plan) == set(u8_fixtures.V2_ACCOUNTS)
    for key in ("unverifiedA", "unverifiedB"):
        assert plan[key] == {"verified": False, "usage": False}
    for key in ("memberA", "memberB", "memberC", "memberD", "memberE", "administrator"):
        assert plan[key] == {"verified": True, "usage": True}


# --- Step 97(j): the compatibility phase's non-skip path on a planted tag (L1-60) ----------------


def planted_tags(tmp_path: Path):
    repository = tmp_path / "repository"
    git = git_repository(repository)
    for name, text in (("frontend/e2e/u8-complete/journeys.spec.ts", "// the tag's spec\n"),
                       ("frontend/playwright.u8-complete.config.ts", "// config\n"),
                       ("frontend/pnpm-lock.yaml", "lockfileVersion: '9.0'\n")):
        (repository / name).parent.mkdir(parents=True, exist_ok=True)
        (repository / name).write_text(text)
    git("add", "-A")
    git("commit", "-q", "--no-verify", "-m", "release")
    git("tag", "-a", "v2.0.0", "-m", "v2.0.0")
    git("tag", "v1.19.0")
    # The candidate sits above every tagged commit, as a push after a release does.
    git("commit", "-q", "--no-verify", "--allow-empty", "-m", "candidate")
    return repository, git


def compatibility_fakes(runner, phases, monkeypatch, tmp_path, repository, *,
                        report: str = PASSING_REPORT) -> tuple[list, dict, list]:
    run = tmp_path / "run"
    run.mkdir(mode=0o700, exist_ok=True)
    calls, written, realms = [], {}, []

    def child(args, log, *, seconds, environment, **options):
        calls.append(args)
        if "PLAYWRIGHT_JUNIT_OUTPUT_FILE" in environment:
            private_text(Path(environment["PLAYWRIGHT_JUNIT_OUTPUT_FILE"]), report)
        return {"exitCode": 0}

    monkeypatch.setattr(phases, "ROOT", repository)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(runner, "RUN", run)
    monkeypatch.setattr(runner, "prepare_phase", lambda path: ({"runId": "r"}, {}))
    monkeypatch.setattr(runner, "source_identity", lambda: {"sha256": "s"})
    monkeypatch.setattr(runner, "bounded_process", child)
    monkeypatch.setattr(runner, "private_json",
                        lambda path, value: written.__setitem__("evidence", value))
    monkeypatch.setattr(phases, "start_realm", lambda runner_, path, log, *, staged: (
        realms.append("started") or SimpleNamespace(pid=4242)))
    monkeypatch.setattr(runner, "stop", lambda process: realms.append("stopped"))
    return calls, written, realms


def test_compatibility_runs_a_planted_v2_tags_own_spec_from_its_own_worktree(
        runner, phases, monkeypatch, tmp_path):
    own = (subprocess.run(["git", "tag", "--list"], cwd=runner.ROOT, capture_output=True,
                          text=True, check=True, timeout=30).stdout,
           subprocess.run(["git", "worktree", "list", "--porcelain"], cwd=runner.ROOT,
                          capture_output=True, text=True, check=True, timeout=30).stdout)
    repository, git = planted_tags(tmp_path)
    calls, written, realms = compatibility_fakes(runner, phases, monkeypatch, tmp_path,
                                                 repository)
    assert phases.previous_tag() == "v2.0.0"
    phases.run_compatibility(runner, tmp_path / "environment.json")
    tree = tmp_path / ".docsuri-u8" / "compatibility-v2.0.0"
    head = subprocess.run(["git", "-C", str(tree), "rev-parse", "HEAD"], capture_output=True,
                          text=True, check=True, timeout=30).stdout.strip()
    assert head == git("rev-parse", "v2.0.0^{commit}")
    spec = "frontend/e2e/u8-complete/journeys.spec.ts"
    assert runner.listed_files(spec, root=tree) == [spec]
    install, playwright = calls
    assert install == ["corepack", "pnpm@9.15.9", "--dir", str(tree / "frontend"), "install",
                       "--frozen-lockfile", "--offline", "--ignore-scripts"]
    assert playwright[0] == str(tree / "frontend/node_modules/.bin/playwright")
    assert playwright[playwright.index("--config") + 1] == str(
        tree / "frontend/playwright.u8-complete.config.ts")
    assert str(tree / spec) in playwright
    assert all(len(arg) > 1 for arg in (*install, *playwright))
    evidence = written["evidence"]
    # No skip: the skip's flag and reason are absent; `skipped` is the report's count, 0.
    assert evidence["previousTag"] == "v2.0.0" and "skippedReason" not in evidence
    assert evidence["skipped"] == 0 and evidence["tests"] == 1
    assert evidence["exitCode"] == 0 and realms == ["started", "stopped"]
    # With the stand-in's report failing, the phase is refused.
    compatibility_fakes(runner, phases, monkeypatch, tmp_path, repository,
                        report='<testsuite><testcase name="n"><failure/></testcase>'
                               "</testsuite>")
    with pytest.raises(runner.Refused, match="U8 phase compatibility failed"):
        phases.run_compatibility(runner, tmp_path / "environment.json")
    # A newer tag on a commit without the spec is refused before any bounded child.
    git("rm", "-q", spec)
    git("commit", "-q", "--no-verify", "-m", "no spec")
    git("tag", "-a", "v2.0.1", "-m", "v2.0.1")
    # The newest tag on the candidate itself (a push the release job tagged first) is never
    # the previous release: the tag before it is answered.
    assert phases.previous_tag() == "v2.0.0"
    git("commit", "-q", "--no-verify", "--allow-empty", "-m", "candidate")
    assert phases.previous_tag() == "v2.0.1"
    calls, written, realms = compatibility_fakes(runner, phases, monkeypatch, tmp_path,
                                                 repository)
    with pytest.raises(runner.Refused,
                       match="phase test path lists no tracked or untracked-unignored file"):
        phases.run_compatibility(runner, tmp_path / "environment.json")
    assert calls == [] and realms == []
    assert (subprocess.run(["git", "tag", "--list"], cwd=runner.ROOT, capture_output=True,
                           text=True, check=True, timeout=30).stdout,
            subprocess.run(["git", "worktree", "list", "--porcelain"], cwd=runner.ROOT,
                           capture_output=True, text=True, check=True, timeout=30).stdout) == own


# --- Step 97(k) and the lead's check after build batch 9a: the realm's own versions ---------------


def test_the_measured_versions_are_read_from_the_realms_own_database(runner, phases):
    value = live_value()
    found = phases.measured_versions(lambda: runner.connect_admin(value), release=None)
    assert found == {
        "postgresql": "16.14", "pgvector": "0.8.7", "python": sys.version.split()[0],
        "ollama": "stand-in", "cloudflared": "stand-in", "release": None,
        "pins": {"postgresql": "16.14", "pgvector": "0.8.7", "ollama": "0.40.7",
                 "cloudflared": "2026.10.3", "python": "3.13.7"}}


def test_require_versions_refuses_a_database_off_the_pins(runner, monkeypatch):
    """cicd-pipeline § 11 `ci/4`: `migrate` runs only on the pinned PostgreSQL and
    pgvector. The realm's real database is read; a pin moved off it refuses with its
    exact reason, and the pins' own values are the accepted case."""
    import dataclasses

    from docsuri_ops.arrangement import runtimes

    value = live_value()
    with runner.connect_admin(value) as conn:
        assert runner.require_versions(conn) == {
            "serverVersion": "16.14", "pgvectorAvailable": "0.8.7",
            "availableExtensions": ["plpgsql", "vector"]}
        installed = conn.execute(
            "SELECT extversion FROM pg_extension WHERE extname='vector'").fetchone()[0]
        assert installed == runtimes.PGVECTOR.version == "0.8.7"
        # A pin off the real version, and look-alikes a prefix, suffix or substring
        # comparison would accept (16.1 is a prefix of 16.14, 6.14 a suffix; 0.8 a prefix
        # of 0.8.7, 8.7 a suffix): each is refused with its exact reason.
        for pin in ("16.13", "16.1", "6.14"):
            monkeypatch.setattr(runtimes, "POSTGRESQL_VERSION", pin)
            with pytest.raises(runner.Refused, match="^pinned PostgreSQL version mismatch$"):
                runner.require_versions(conn)
            monkeypatch.undo()
        for pin in ("0.8.6", "0.8", "8.7"):
            monkeypatch.setattr(runtimes, "PGVECTOR",
                                dataclasses.replace(runtimes.PGVECTOR, version=pin))
            with pytest.raises(runner.Refused, match="^pinned pgvector version unavailable$"):
                runner.require_versions(conn)
            monkeypatch.undo()
