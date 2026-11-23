"""Step 20 (g) and (h): the U5 tool's verdict on a phase, and the evidence it keeps.

`run_phase` runs in an owned temporary run directory. Only what such a directory cannot
supply is stood in for: the realm manifest and its container checks, the host preflight
and port check, and the source fingerprint (the real one, taken once). The supervised
child is replaced by one that exits 0 and writes the JUnit report the phase told it to
write, so every verdict below is the tool's own reading of that report:

- (g) zero test cases, a skip, an error or a failure, and a missing, malformed or
  wrongly owned report each fail the phase although the child exited 0;
- (h) the evidence file records the exact command, the run identity, the source, lock,
  manifest and fixture digests and the counts, while the child's output, which here
  names a recipient address and private digest text, reaches neither the evidence nor
  the printed summary.
"""

import hashlib
import json
import os
import stat
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import verify_docsuri_u5 as runner

RUN_ID = "docsuri-u5-0123456789abcdef"
RECIPIENT = "owner-private@fixture.invalid"
PRIVATE_TEXT = "Confidential digest body for one owner"
PASSED = '<testcase classname="u5" name="passes" time="0.01"/>'
SKIPPED = '<testcase classname="u5" name="skips"><skipped message="skipped"/></testcase>'
ERRORED = '<testcase classname="u5" name="errors"><error message="setup error"/></testcase>'
FAILED = '<testcase classname="u5" name="fails"><failure message="assertion"/></testcase>'
PRIVATE = (
    '<testcase classname="u5" name="private">'
    f"<system-out>{RECIPIENT} {PRIVATE_TEXT}</system-out></testcase>"
)
SUMMARY_KEYS = {
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
    "coverageFloorPercent",
    "supervision",
}


def junit(*cases):
    return (
        '<?xml version="1.0" encoding="utf-8"?><testsuites>'
        f'<testsuite name="pytest" tests="{len(cases)}">{"".join(cases)}</testsuite>'
        "</testsuites>"
    )


def write_private(path: Path, data: bytes, mode: int = 0o600) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(data)
    os.chmod(path, mode)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture(scope="module")
def identity():
    return runner.source_identity()


@pytest.fixture
def tool(tmp_path, monkeypatch, identity):
    run = tmp_path / "run"
    run.mkdir(mode=0o700)
    monkeypatch.setattr(runner, "RUN", run)
    manifest = run / "environment.json"
    write_private(manifest, json.dumps({"unit": runner.UNIT, "runId": RUN_ID}).encode())
    value = {
        "runId": RUN_ID,
        "policy": runner.POLICY,
        "locks": {name: runner.digest(runner.ROOT / name) for name in runner.LOCKS},
    }
    state = SimpleNamespace(
        run=run, manifest=manifest, value=value, identity=identity,
        commands=[], report=None, mode=0o600, log=b"",
    )

    def child(args, log, *, clock_capability=None, **companion):
        assert clock_capability is None and companion == {}
        state.commands.append(list(args))
        write_private(log, state.log)
        [target] = [arg.removeprefix("--junitxml=") for arg in args if arg.startswith("--junitxml=")]
        if state.report is not None:
            write_private(Path(target), state.report.encode(), state.mode)
        return {
            "exitCode": 0,
            "reason": "process-exit",
            "elapsedSeconds": 0.1,
            "peakRssBytes": 1024,
            "peakPssBytes": None,
            "logBytes": len(state.log),
            "processStopped": True,
            "observations": 1,
            "slowestObservationSeconds": 0.0,
        }

    monkeypatch.setattr(runner, "manifest", lambda path: (None, value))
    monkeypatch.setattr(runner, "require_resources", lambda value: None)
    monkeypatch.setattr(runner, "preflight", lambda established=False: {"hostFreeBytes": 1})
    monkeypatch.setattr(runner, "require_stopped", lambda port=runner.APPLICATION_PORT: None)
    monkeypatch.setattr(runner, "source_identity", lambda: identity)
    monkeypatch.setattr(runner, "bounded_process", child)
    return state


def run_phase(tool, phase="database"):
    try:
        outcome = runner.run_phase(phase, tool.manifest)
    except runner.Refused as refused:
        outcome = refused
    [path] = tool.run.glob(f"{phase}-evidence-*.json")
    return outcome, json.loads(path.read_text()), path


@pytest.mark.parametrize(
    "report,mode,verdict",
    [
        pytest.param(junit(), 0o600, ("tests", 0), id="zero-test-cases"),
        pytest.param(junit(PASSED, SKIPPED), 0o600, ("skipped", 1), id="a-skip"),
        pytest.param(junit(PASSED, ERRORED), 0o600, ("errors", 1), id="an-error"),
        pytest.param(junit(PASSED, FAILED), 0o600, ("failures", 1), id="a-failure"),
        pytest.param(None, 0o600, ("missingTestReport", True), id="no-report"),
        pytest.param("<testsuites><testcase", 0o600, ("invalidTestReport", True), id="malformed"),
        pytest.param(junit(PASSED), 0o644, ("invalidTestReport", True), id="wrongly-owned"),
    ],
)
def test_a_phase_fails_unless_its_report_shows_only_passing_tests(
    tool, capsys, report, mode, verdict
):
    tool.report, tool.mode = report, mode
    outcome, evidence, _ = run_phase(tool)
    assert isinstance(outcome, runner.Refused)
    assert str(outcome) == "U5 phase failed; evidence preserved"
    # The child itself exited 0: the verdict is the tool's reading of the report.
    assert evidence["supervision"]["exitCode"] == 0
    key, expected = verdict
    assert evidence["exitCode"] == 1 and evidence[key] == expected
    summary = json.loads(capsys.readouterr().out)
    assert summary["exitCode"] == 1 and summary[key] == expected


def test_a_report_of_only_passing_tests_passes_the_phase(tool, capsys):
    tool.report = junit(PASSED, PASSED)
    outcome, evidence, _ = run_phase(tool)
    assert outcome == {"state": "passed", "phase": "database"}
    counts = tuple(evidence[key] for key in ("exitCode", "tests", "failures", "errors", "skipped"))
    assert counts == (0, 2, 0, 0, 0)
    assert not {"missingTestReport", "invalidTestReport", "sourceChangedDuringRun"} & set(evidence)
    assert json.loads(capsys.readouterr().out)["exitCode"] == 0


def test_a_source_change_during_the_run_fails_a_phase_whose_report_passes(
    tool, capsys, monkeypatch
):
    """Plan Step 38: the verdict the four tests above leave unchecked. The tool reads the
    source identity before and after the child; a change between the two readings fails
    the phase although its report shows only passing tests."""
    tool.report = junit(PASSED, PASSED)
    changed = dict(tool.identity, sha256="0" * 64)
    readings = iter([tool.identity, changed])
    monkeypatch.setattr(runner, "source_identity", lambda: next(readings))
    outcome, evidence, _ = run_phase(tool)
    assert isinstance(outcome, runner.Refused)
    assert str(outcome) == "U5 phase failed; evidence preserved"
    counts = tuple(evidence[key] for key in ("tests", "failures", "errors", "skipped"))
    assert counts == (2, 0, 0, 0) and evidence["supervision"]["exitCode"] == 0
    assert evidence["sourceChangedDuringRun"] is True and evidence["exitCode"] == 1
    # The evidence keeps the identity read before the run, not the changed one.
    assert evidence["source"] == tool.identity
    summary = json.loads(capsys.readouterr().out)
    assert summary["sourceChangedDuringRun"] is True and summary["exitCode"] == 1
    assert next(readings, None) is None


@pytest.mark.parametrize(
    "phase,folders",
    [
        ("database", ["tests/u5_topics_digests/database"]),
        ("component", ["tests/u5_topics_digests/component", "tests/u5_topics_digests/runtime"]),
    ],
)
def test_evidence_records_command_identity_digests_and_counts_without_private_output(
    tool, capsys, phase, folders
):
    tool.report = junit(PASSED, PASSED, PRIVATE)
    tool.log = f"digest for {RECIPIENT}: {PRIVATE_TEXT}\n3 passed\n".encode()
    outcome, evidence, path = run_phase(tool, phase)
    assert outcome == {"state": "passed", "phase": phase}
    command = [
        str(runner.PYTHON),
        "-m",
        "pytest",
        "-c",
        "backend/pytest.u5-topics-digests.ini",
        folders[0],
        "-q",
        "--tb=short",
        "--maxfail=1",
        f"--junitxml={tool.run / f'{phase}.xml'}",
        *folders[1:],
    ]
    # The exact command, as the child was started with it.
    assert tool.commands == [command] and evidence["command"] == command
    assert (evidence["phase"], evidence["runId"], evidence["policy"]) == (
        phase,
        RUN_ID,
        runner.POLICY,
    )
    assert evidence["source"] == tool.identity
    assert evidence["locks"] == tool.value["locks"] and set(evidence["locks"]) == set(runner.LOCKS)
    assert evidence["manifestSha256"] == sha256(tool.manifest)
    assert evidence["fixtureSourceSha256"] == sha256(
        runner.ROOT / "tests/u5_topics_digests/conftest.py"
    )
    counts = tuple(evidence[key] for key in ("tests", "failures", "errors", "skipped"))
    assert counts == (3, 0, 0, 0)
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    printed = capsys.readouterr().out
    for text in (path.read_text(), printed):
        assert RECIPIENT not in text and PRIVATE_TEXT not in text
    assert set(json.loads(printed)) <= SUMMARY_KEYS


def test_the_source_identity_digests_the_units_own_files(identity):
    files = identity["files"]
    for name in (
        "tests/u5_topics_digests/conftest.py",
        ".github/workflows/u5-topics-digests.yml",
        "scripts/verify_docsuri_u5.py",
        "backend/u5_host.py",
        "backend/modules/topics/delivery.py",
    ):
        assert files[name] == sha256(runner.ROOT / name), name
    assert identity["sha256"] == hashlib.sha256(
        json.dumps(files, sort_keys=True).encode()
    ).hexdigest()
    assert len(identity["head"]) == 40
